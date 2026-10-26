"""The in-app AI chat: Claude Code (the user's own installation and sign-in) working on the open part
through the app's MCP server.

* `find_claude()` – the Claude Code executable: $AUTO3D_CLAUDE, PATH, ~/.local/bin, or the newest copy
  bundled with the VS Code / Cursor extension.
* `Relay` – tool calls that act on the part are queued for the browser page, which long-polls for them,
  applies them and posts the result back (the app state lives in the page).
* `ChatSession` – one `claude -p` process per chat, kept open with stream-json input, restricted to the
  app's MCP tools (no built-in file / shell tools, no user hooks or settings). Its output is turned into
  chat events for the page (Server-Sent Events).

The app never sees the user's Claude credentials: Claude Code signs in through Anthropic's own flow.
"""
from __future__ import annotations

import glob
import itertools
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from .agent_tools import SYSTEM_PROMPT
from .guides import PLUGIN_DIR

MCP_SCRIPT = Path(__file__).resolve().parent / "mcp_server.py"
WORKDIR = Path(__file__).resolve().parent.parent / "data" / "agent"


# --------------------------------------------------------------------------- Claude Code
def _version_key(path: str):
    m = re.search(r"claude-code-(\d+(?:\.\d+)*)", path.replace("\\", "/"))
    return tuple(int(x) for x in m.group(1).split(".")) if m else ()


def find_claude() -> str | None:
    env = os.environ.get("AUTO3D_CLAUDE")
    if env and Path(env).exists():
        return env
    for name in ("claude", "claude.exe", "claude.cmd"):
        hit = shutil.which(name)
        if hit:
            return hit
    home = Path.home()
    for p in (home / ".local" / "bin" / "claude.exe", home / ".local" / "bin" / "claude", home / ".claude" / "local" / "claude"):
        if p.exists():
            return str(p)
    hits = []
    for editor in (".vscode", ".vscode-insiders", ".cursor", ".windsurf"):
        for exe in ("claude.exe", "claude"):
            hits += glob.glob(str(home / editor / "extensions" / "anthropic.claude-code-*" / "resources" / "native-binary" / exe))
    return max(hits, key=_version_key) if hits else None


SESSION_VARS = {"CLAUDECODE", "CLAUDE_PID", "CLAUDE_EFFORT", "CLAUDE_AGENT_SDK_VERSION"}


def clean_env() -> dict:
    """The environment for the chat's Claude Code: without the variables of a Claude Code session the
    app itself may have been started from (a terminal inside Claude Code), so the chat is a fresh,
    independent session. The user's own settings (ANTHROPIC_*, proxies …) are kept."""
    return {k: v for k, v in os.environ.items() if k not in SESSION_VARS and not k.startswith("CLAUDE_CODE_")}


# --------------------------------------------------------------------------- browser relay
class Relay:
    """Server <-> page: commands queued for the page, results waited for.

    A command stays queued until its result arrives: if the page that took it goes away (reload, closed
    tab — its pending long-poll still takes the command), it is handed out again after `lease` seconds.
    The page ignores a command id it has already run (and posts that result again).

    With several pages open, commands go to the one the user works in (the last page that polled while
    visible: the owner); other pages get them only when the owner has not polled for `owner_timeout`."""

    def __init__(self, lease: float = 10.0):
        self.outbox: dict[str, dict] = {}   # id -> {"cmd", "args", "taken": time | None}
        self.order: list[str] = []
        self.results: dict[str, dict] = {}
        self.cv = threading.Condition()
        self.lease = lease
        self.last_poll = 0.0
        self.owner, self.owner_seen, self.owner_timeout = None, 0.0, 30.0

    def connected(self) -> bool:
        return time.time() - self.last_poll < 45

    def call(self, cmd: str, args: dict | None = None, timeout: float = 150.0) -> dict:
        if not self.connected():
            raise RuntimeError("The app is not open in a browser — open it so the part can be changed.")
        cid = uuid.uuid4().hex
        with self.cv:
            self.outbox[cid] = {"id": cid, "cmd": cmd, "args": args or {}, "taken": None}
            self.order.append(cid)
            self.cv.notify_all()
            end = time.time() + timeout
            try:
                while cid not in self.results:
                    left = end - time.time()
                    if left <= 0:
                        raise TimeoutError(f"The page did not answer '{cmd}' within {int(timeout)} s.")
                    self.cv.wait(min(left, 1.0))
                return self.results.pop(cid)
            finally:
                self.outbox.pop(cid, None)
                if cid in self.order:
                    self.order.remove(cid)

    def _next(self):
        now = time.time()
        for cid in self.order:
            c = self.outbox.get(cid)
            if c and (c["taken"] is None or now - c["taken"] > self.lease):
                c["taken"] = now
                return {k: c[k] for k in ("id", "cmd", "args")}
        return None

    def _may_take(self, client) -> bool:
        return (client is None or self.owner is None or client == self.owner
                or time.time() - self.owner_seen > self.owner_timeout)

    def poll(self, timeout: float = 20.0, client: str | None = None, active: bool = True):
        self.last_poll = time.time()
        end = self.last_poll + timeout
        with self.cv:
            if client and (active or self.owner is None):
                if client != self.owner:
                    self.cv.notify_all()  # the previous owner's waiting poll stops taking commands
                self.owner = client
            if client == self.owner:
                self.owner_seen = time.time()
            try:
                while True:
                    c = self._next() if self._may_take(client) else None
                    if c or time.time() >= end:
                        return c
                    self.cv.wait(min(end - time.time(), 1.0))
            finally:
                self.last_poll = time.time()
                if client == self.owner:
                    self.owner_seen = time.time()

    def resolve(self, cid: str, result: dict):
        with self.cv:
            if cid in self.outbox:
                self.results[cid] = result
                self.cv.notify_all()


# --------------------------------------------------------------------------- chat session
class ChatSession:
    """One Claude Code process for the chat; events fan out to all subscribed pages."""

    def __init__(self, app_url: str):
        self.app_url = app_url
        self.proc: subprocess.Popen | None = None
        self.subscribers: list[queue.Queue] = []
        self.history: list[dict] = []      # events of this chat (replayed to a page that reconnects)
        self.lock = threading.Lock()
        self.stderr_tail: list[str] = []
        self.busy = False
        self._seq = itertools.count(1)

    # ---------------------------------------------------------------- events
    def emit(self, ev: dict):
        ev = {"seq": next(self._seq), **ev}
        with self.lock:
            self.history.append(ev)
            del self.history[:-800]
            subs = list(self.subscribers)
        for q in subs:
            q.put(ev)

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        with self.lock:
            for ev in self.history:
                q.put(ev)
            self.subscribers.append(q)
        return q

    def unsubscribe(self, q):
        with self.lock:
            if q in self.subscribers:
                self.subscribers.remove(q)

    # ---------------------------------------------------------------- process
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def command(self, exe: str) -> list[str]:
        mcp = {"mcpServers": {"auto3d": {"type": "stdio", "command": sys.executable,
                                         "args": [str(MCP_SCRIPT), "--url", self.app_url]}}}
        cmd = [exe, "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
               "--include-partial-messages",
               "--mcp-config", json.dumps(mcp), "--strict-mcp-config",
               "--tools", "Skill",                             # only the Skill tool (the app's guides): no files, no shell
               "--allowedTools", "mcp__auto3d,Skill",          # the app's tools and its skills run without prompts
               "--plugin-dir", str(PLUGIN_DIR),                # the app's skills (agent_plugin/skills), this session only
               "--permission-mode", "dontAsk",                 # anything else is refused, not asked
               "--setting-sources", "local",                   # not the user's global hooks / settings
               "--no-session-persistence",
               "--append-system-prompt", SYSTEM_PROMPT]
        model = os.environ.get("AUTO3D_CLAUDE_MODEL")
        if model:
            cmd += ["--model", model]
        return cmd

    def start(self):
        exe = find_claude()
        if not exe:
            raise RuntimeError("Claude Code was not found. Install it (claude.com/claude-code) and sign in once, "
                               "or set AUTO3D_CLAUDE to the path of the claude executable.")
        WORKDIR.mkdir(parents=True, exist_ok=True)  # an empty folder: no project CLAUDE.md / .mcp.json
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.stderr_tail = []
        self.proc = subprocess.Popen(self.command(exe), cwd=WORKDIR, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, creationflags=flags, bufsize=0, env=clean_env())
        self.emit({"type": "status", "text": "Starting Claude Code…", "exe": exe})
        threading.Thread(target=self._read_out, args=(self.proc,), daemon=True).start()
        threading.Thread(target=self._read_err, args=(self.proc,), daemon=True).start()

    def send(self, text: str, photos: list | None = None):
        """A user message, optionally with photos: [{"name", "media_type", "data" (base64), "path"}]. Claude
        sees each photo and is told where it was saved (so it can trace it with trace_picture)."""
        photos = photos or []
        if not self.running():
            self.start()
        self.busy = True
        self.emit({"type": "user", "text": text, "photos": [{"name": p["name"], "url": p["url"]} for p in photos]})
        content = [{"type": "image", "source": {"type": "base64", "media_type": p["media_type"], "data": p["data"]}} for p in photos]
        note = "\n".join(f"[Attached photo: {p['path']}]" for p in photos)
        content.append({"type": "text", "text": "\n\n".join(x for x in (text, note) if x)})
        line = json.dumps({"type": "user", "message": {"role": "user", "content": content}})
        try:
            self.proc.stdin.write((line + "\n").encode("utf-8"))
            self.proc.stdin.flush()
        except OSError as exc:
            self.busy = False
            raise RuntimeError(f"Claude Code stopped unexpectedly ({exc}).") from exc

    def stop(self):
        """Stop the current answer (ends the process; the next message starts a fresh session)."""
        p = self.proc
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()
        self.busy = False

    def reset(self):
        self.stop()
        with self.lock:
            self.history = []
        self.emit({"type": "reset"})

    # ---------------------------------------------------------------- output -> chat events
    def _read_err(self, proc):
        for raw in proc.stderr:
            line = raw.decode("utf-8", "replace").rstrip()
            if line:
                self.stderr_tail = (self.stderr_tail + [line])[-20:]

    def _read_out(self, proc):
        for raw in proc.stdout:
            line = raw.decode("utf-8", "replace").strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            for ev in translate(msg):
                if ev["type"] == "done":
                    self.busy = False
                self.emit(ev)
        code = proc.wait()
        self.busy = False
        if proc is self.proc:
            self.emit({"type": "exit", "code": code, "stderr": "\n".join(self.stderr_tail[-6:])})


def translate(msg: dict) -> list[dict]:
    """A stream-json message of Claude Code -> chat events for the page."""
    t = msg.get("type")
    if t == "system" and msg.get("subtype") == "init":
        servers = {s.get("name"): s.get("status") for s in msg.get("mcp_servers") or []}
        return [{"type": "ready", "model": msg.get("model"), "mcp": servers.get("auto3d", "missing")}]
    if t == "system" and msg.get("subtype") == "api_retry":
        return [{"type": "status", "text": f"Retrying ({msg.get('error') or 'API error'})…"}]
    if t == "stream_event":
        e = msg.get("event") or {}
        if e.get("type") == "content_block_delta" and (e.get("delta") or {}).get("type") == "text_delta":
            return [{"type": "delta", "text": e["delta"].get("text", "")}]
        if e.get("type") == "content_block_start" and (e.get("content_block") or {}).get("type") == "tool_use":
            return [{"type": "tool_start", "name": _short(e["content_block"].get("name", ""))}]
        if e.get("type") == "message_start":
            return [{"type": "turn"}]
        return []
    if t == "assistant":
        out = []
        for b in (msg.get("message") or {}).get("content") or []:
            if b.get("type") == "text":
                out.append({"type": "text", "text": b.get("text", "")})
            elif b.get("type") == "tool_use":
                out.append({"type": "tool", "name": _short(b.get("name", "")), "input": b.get("input")})
        return out
    if t == "user":
        out = []
        for b in (msg.get("message") or {}).get("content") or []:
            if isinstance(b, dict) and b.get("type") == "tool_result":
                c = b.get("content")
                text = c if isinstance(c, str) else " ".join(x.get("text", "") for x in c or [] if isinstance(x, dict) and x.get("type") == "text")
                out.append({"type": "tool_result", "error": bool(b.get("is_error")), "text": text[:400]})
        return out
    if t == "result":
        return [{"type": "done", "error": bool(msg.get("is_error")), "text": msg.get("result") if msg.get("is_error") else None,
                 "cost": msg.get("total_cost_usd"), "ms": msg.get("duration_ms")}]
    return []


def _short(name: str) -> str:
    return name.split("__")[-1] if name.startswith("mcp__") else name
