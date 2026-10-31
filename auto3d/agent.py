"""The in-app AI chat: Claude Code (the user's own installation and sign-in) working on the open part
through the app's MCP server.

* `find_claude()` – the Claude Code executable: $AUTO3D_CLAUDE, PATH, ~/.local/bin, or the newest copy
  bundled with the VS Code / Cursor extension.
* `Relay` – tool calls that act on the part are queued for the browser page, which long-polls for them,
  applies them and posts the result back (the app state lives in the page). A call made for a window (its client
  id, `ROUTE` – set by the server from the chat's MCP server) goes to that window only; closed: the call fails.
* `ChatSession` – one `claude -p` process per chat, kept open with stream-json input, restricted to the
  app's MCP tools (no built-in file / shell tools, no user hooks or settings). Its output is turned into
  chat events for the page (Server-Sent Events). Each app window has its own chat (and process, started with its
  first message), whose tool calls act in that window. Its conversation is kept (auto3d/chat_history.py) and can be
  opened again and continued: Claude Code's own session resumed (`--resume`), or a new one told the conversation in short.

The app never sees the user's Claude credentials: Claude Code signs in through Anthropic's own flow.
"""
from __future__ import annotations

import contextvars
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

from . import chat_history
from .agent_tools import SYSTEM_PROMPT
from .guides import PLUGIN_DIR

MCP_SCRIPT = Path(__file__).resolve().parent / "mcp_server.py"
WORKDIR = Path(os.environ.get("A3D_DATA") or Path(__file__).resolve().parent.parent / "data") / "agent"


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


def run_claude(exe: str) -> list[str]:
    """The command start for Claude Code at `exe` (a .py: a stand-in for it run with this Python — tools/fake_claude.py,
    the browser tests' AI without a model)."""
    return [sys.executable, exe] if exe.endswith(".py") else [exe]


SESSION_VARS = {"CLAUDECODE", "CLAUDE_PID", "CLAUDE_EFFORT", "CLAUDE_AGENT_SDK_VERSION"}


def clean_env() -> dict:
    """The environment for the chat's Claude Code: without the variables of a Claude Code session the
    app itself may have been started from (a terminal inside Claude Code), so the chat is a fresh,
    independent session. The user's own settings (ANTHROPIC_*, proxies …) are kept."""
    return {k: v for k, v in os.environ.items() if k not in SESSION_VARS and not k.startswith("CLAUDE_CODE_")}


def session_exists(sid: str | None) -> bool:
    """Whether Claude Code still has the session `sid` (its transcript under ~/.claude/projects, or $CLAUDE_CONFIG_DIR):
    then `--resume` gives the AI the whole conversation back."""
    if not sid or not re.match(r"^[\w-]{8,80}$", sid):
        return False
    base = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "projects"
    return any(base.glob(f"*/{sid}.jsonl"))


# --------------------------------------------------------------------------- browser relay
# the window a tool call is for (its client id): set by the server for the request of a chat's MCP call
ROUTE: contextvars.ContextVar[str | None] = contextvars.ContextVar("route", default=None)
GONE_TEXT = ("The app window this chat belongs to was closed — nothing was changed. Open the project again and ask in "
             "the chat of its window.")


class Relay:
    """Server <-> page: commands queued for the page, results waited for.

    A command stays queued until its result arrives: if the page that took it goes away (reload, closed
    tab — its pending long-poll still takes the command), it is handed out again after `lease` seconds.
    The page ignores a command id it has already run (and posts that result again).

    A command for a window (`to`: its client id — the chat of that window, ROUTE) is taken by that window only. The
    window closed (it said goodbye and did not come back within `grace` seconds — a reload comes back —, or it has not
    polled for `gone_after` seconds — while it runs a long call it says it is there, `alive`): the call fails with
    GONE_TEXT, it never goes to another window. A command for no window in particular (an MCP client of its own) goes to the one the user works in (the
    last page that polled while visible: the owner); other pages get it only when the owner has not polled for
    `owner_timeout`."""

    def __init__(self, lease: float = 10.0, grace: float = 10.0, gone_after: float = 90.0):
        self.outbox: dict[str, dict] = {}   # id -> {"cmd", "args", "to": client | None, "taken": time | None}
        self.order: list[str] = []
        self.results: dict[str, dict] = {}
        self.cv = threading.Condition()
        self.lease, self.grace, self.gone_after = lease, grace, gone_after
        self.last_poll = 0.0
        self.owner, self.owner_seen, self.owner_timeout = None, 0.0, 30.0
        self.seen: dict[str, float] = {}    # client -> when it last polled
        self.left: dict[str, float] = {}    # client -> when it said goodbye (its page closed or reloaded)

    def connected(self) -> bool:
        return time.time() - self.last_poll < 45

    def gone(self, client: str) -> bool:
        """True when the window `client` is closed (or was never open)."""
        now = time.time()
        if client in self.left and now - self.left[client] > self.grace:
            return True
        return client not in self.seen or now - self.seen[client] > self.gone_after

    def alive(self, client: str):
        """The window `client` is there (running a long call: it does not poll meanwhile)."""
        self.seen[client] = time.time()

    def bye(self, client: str):
        """The window `client` is closing (or reloading: it polls again at once and is back)."""
        with self.cv:
            self.left[client] = time.time()
            self.cv.notify_all()

    def call(self, cmd: str, args: dict | None = None, timeout: float = 150.0, client: str | None = None) -> dict:
        to = client or ROUTE.get()
        if to and self.gone(to):
            raise RuntimeError(GONE_TEXT)
        if not to and not self.connected():
            raise RuntimeError("The app is not open in a browser — open it so the part can be changed.")
        cid = uuid.uuid4().hex
        with self.cv:
            self.outbox[cid] = {"id": cid, "cmd": cmd, "args": args or {}, "to": to, "taken": None}
            self.order.append(cid)
            self.cv.notify_all()
            end = time.time() + timeout
            try:
                while cid not in self.results:
                    left = end - time.time()
                    if left <= 0:
                        raise TimeoutError(f"The page did not answer '{cmd}' within {int(timeout)} s.")
                    if to and self.gone(to):
                        raise RuntimeError(GONE_TEXT)
                    self.cv.wait(min(left, 1.0))
                return self.results.pop(cid)
            finally:
                self.outbox.pop(cid, None)
                if cid in self.order:
                    self.order.remove(cid)

    def _next(self, client=None, anyone=True):
        """The next command `client` may take: its own window's; the others' (for no window) when `anyone`."""
        now = time.time()
        for cid in self.order:
            c = self.outbox.get(cid)
            if not c or (c["to"] != client if c["to"] else not anyone):
                continue
            if c["taken"] is None or now - c["taken"] > self.lease:
                c["taken"] = now
                return {k: c[k] for k in ("id", "cmd", "args")}
        return None

    def _may_take(self, client) -> bool:
        return (client is None or self.owner is None or client == self.owner
                or time.time() - self.owner_seen > self.owner_timeout)

    def poll(self, timeout: float = 20.0, client: str | None = None, active: bool = True, hung_up=None):
        """The next command for `client`, else None after `timeout` s — or as soon as `hung_up()` says the page has
        gone (its request closed: a reload), so a call is not handed to a page that cannot run it."""
        self.last_poll = time.time()
        end = self.last_poll + timeout
        with self.cv:
            if client:
                self.seen[client] = self.last_poll
                self.left.pop(client, None)  # (back after a reload)
            if client and (active or self.owner is None):
                if client != self.owner:
                    self.cv.notify_all()  # the previous owner's waiting poll stops taking commands
                self.owner = client
            if client == self.owner:
                self.owner_seen = time.time()
            try:
                while True:
                    if hung_up is not None and hung_up():
                        return None
                    c = self._next(client, self._may_take(client))
                    if c or time.time() >= end:
                        return c
                    self.cv.wait(min(end - time.time(), 1.0))
            finally:
                self.last_poll = time.time()
                if client:
                    self.seen[client] = self.last_poll
                if client == self.owner:
                    self.owner_seen = time.time()

    def resolve(self, cid: str, result: dict):
        with self.cv:
            if cid in self.outbox:
                self.results[cid] = result
                self.cv.notify_all()


# --------------------------------------------------------------------------- slash commands
# a chat message starting with one of these runs the app's skill for it (the chat shows what the user typed; Claude
# gets the instruction, and the rest of the message as what the user added)
COMMANDS = {
    "uitester": ("bug-hunter", "Test the app's GUI now: load the skill auto3d:bug-hunter (or get_guide topic \"bug-hunter\") and follow "
                               "it — do the task (or its test designs) through the GUI only, verify with the read tools, report each "
                               "problem once, end with the summary table."),
    "suggest": ("suggest-features", "Suggest new features for the app: load the skill auto3d:suggest-features (or get_guide topic "
                                    "\"suggest-features\") and follow it — propose them, file the ones I agree to."),
    "teachme": ("teach-me", "Teach me: load the skill auto3d:teach-me (or get_guide topic \"teach-me\") and guide me step by step "
                            "through the app's controls — I do the clicking, you show where, say why and check."),
}
COMMANDS["bughunter"] = COMMANDS["uitester"]  # /bugHunter: the same mode under its own name


def expand_command(text: str) -> str:
    """"/uiTester …" -> the instruction for Claude (the words after the command kept as the user's own); other text as it is."""
    m = re.match(r"^/([A-Za-z][\w-]*)\b\s*(.*)$", text.strip(), re.S)
    cmd = COMMANDS.get(m.group(1).lower().replace("-", "").replace("_", "")) if m else None
    if not cmd:
        return text
    rest = m.group(2).strip()
    return f"[/{m.group(1)}] {cmd[1]}" + (f"\n\nThe user adds: {rest}" if rest else "")


# --------------------------------------------------------------------------- chat session
class ChatSession:
    """One Claude Code process for the chat; events fan out to all subscribed pages. client: the app window it
    belongs to (its MCP server sends its tool calls there), None: any (the window in use)."""

    def __init__(self, app_url: str, client: str | None = None, store: Path | None = None):
        self.app_url = app_url
        self.client = client
        self.store = store                 # where its conversations are kept (None: not kept)
        self.conv: dict | None = None      # the conversation (chat_history): made with the first message
        self.project = {}                  # the project the page has open ({id, name}): a new conversation's
        self.resumed = None                # the session id the process was started to resume (not confirmed yet)
        self.pending: list | None = None   # the content of the last message sent (sent again when a resume fails)
        self.reader: threading.Thread | None = None  # the process's output -> events (its end: the 'exit' event)
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
        # kept first: whoever sees the event (a page, the list) finds the conversation saved with it
        kept = self.conv is not None and not ev.get("old") and chat_history.add(self.conv, ev)
        if kept and ev["type"] in ("user", "text", "note", "done") or ev["type"] == "exit":
            self.keep()
        with self.lock:
            self.history.append(ev)
            del self.history[:-800]
            subs = list(self.subscribers)
        for q in subs:
            q.put(ev)

    def keep(self):
        """Write the conversation to the store (when it has one and a message)."""
        if self.store and self.conv:
            try:
                chat_history.save(self.store, self.conv)
            except OSError:
                pass  # (a full disk: the chat goes on)

    def conv_meta(self) -> dict | None:
        return {k: self.conv.get(k) for k in chat_history.META} if self.conv else None

    def open(self, cid: str):
        """The kept conversation `cid` on screen again (its events replayed, marked old) — the next message goes on with
        it: its Claude Code session resumed, or a new session told it in short."""
        conv = chat_history.load(self.store, cid)
        self.stop()
        self.proc = None
        with self.lock:
            self.history = []
        self.conv = conv
        self.emit({"type": "reset"})
        for ev in conv["events"]:
            self.emit({**ev, "old": True})
        self.emit({"type": "conv", **self.conv_meta(), "opened": True})

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

    def command(self, exe: str, resume: str | None = None) -> list[str]:
        # (the built app has no Python: its own exe is the MCP server, auto3d/launcher.py)
        script = ["--mcp-server"] if getattr(sys, "frozen", False) else [str(MCP_SCRIPT)]
        mcp = {"mcpServers": {"auto3d": {"type": "stdio", "command": sys.executable,
                                         "args": [*script, "--url", self.app_url,
                                                  *(["--client", self.client] if self.client else [])]}}}
        from .fetchcad import internet_on
        web = ",WebSearch" if internet_on(WORKDIR.parent) else ""  # 🌐 parts on the internet (AI settings): search only
        cmd = [*run_claude(exe), "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
               "--include-partial-messages",
               "--mcp-config", json.dumps(mcp), "--strict-mcp-config",
               "--tools", "Skill" + web,                       # only the Skill tool (the app's guides): no files, no shell
               "--allowedTools", "mcp__auto3d,Skill" + web,    # the app's tools and its skills run without prompts
               "--plugin-dir", str(PLUGIN_DIR),                # the app's skills (agent_plugin/skills), this session only
               "--permission-mode", "dontAsk",                 # anything else is refused, not asked
               "--setting-sources", "local",                   # not the user's global hooks / settings
               "--append-system-prompt", SYSTEM_PROMPT]          # (its session kept: a conversation goes on with --resume)
        if resume:
            cmd += ["--resume", resume]
        model = os.environ.get("AUTO3D_CLAUDE_MODEL")
        if model:
            cmd += ["--model", model]
        return cmd

    def start(self, resume: bool = True) -> str:
        """Start Claude Code -> what goes before the next message: "" — or the conversation in short, when it has one
        but its session cannot be resumed (a note in the chat says so)."""
        exe = find_claude()
        if not exe:
            raise RuntimeError("Claude Code was not found. Install it (claude.com/claude-code) and sign in once, "
                               "or set AUTO3D_CLAUDE to the path of the claude executable.")
        WORKDIR.mkdir(parents=True, exist_ok=True)  # an empty folder: no project CLAUDE.md / .mcp.json
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.stderr_tail = []
        from . import ai_access
        conv = self.conv
        sid = conv.get("session") if conv else None
        self.resumed = sid if resume and session_exists(sid) else None
        prime = ""
        if conv and conv["messages"] and not self.resumed:
            told = conv["events"]
            if not resume:  # (a resume that failed: the message being sent is not part of what came before)
                told = told[:max((i for i, e in enumerate(told) if e["type"] == "user"), default=0)]
            if told:
                prime = ("[This continues an earlier conversation with the user; your session of it could not be resumed. "
                         f"The conversation so far, in short:\n{chat_history.summary(told)}]\n\n")
                self.emit({"type": "note", "key": "summary"})
        self.proc = subprocess.Popen(self.command(exe, self.resumed), cwd=WORKDIR, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, creationflags=flags, bufsize=0,
                                     env=ai_access.chat_env(clean_env()))  # (the API key set up in the ✨ AI panel)
        self.emit({"type": "status", "text": "Starting Claude Code…", "exe": exe})
        self.reader = threading.Thread(target=self._read_out, args=(self.proc,), daemon=True)
        self.reader.start()
        threading.Thread(target=self._read_err, args=(self.proc,), daemon=True).start()
        return prime

    def send(self, text: str, photos: list | None = None, files: list | None = None):
        """A user message, optionally with photos: [{"name", "media_type", "data" (base64), "path"}]. Claude
        sees each photo and is told where it was saved (so it can trace it with trace_picture). files: other
        attachments (chat_attach.attach: [{"name", "size", "path", "text"}]) — their `text` goes into the message."""
        photos, files = photos or [], files or []
        if self.conv is None:
            self.conv = chat_history.new(self.project.get("id", ""), self.project.get("name", ""))
            self.emit({"type": "conv", **self.conv_meta()})
        self.pending = None
        prime = "" if self.running() else self.start()
        self.busy = True
        self.emit({"type": "user", "text": text, "photos": [{"name": p["name"], "url": p["url"]} for p in photos],
                   **({"files": [{k: f[k] for k in ("name", "size", "path")} for f in files]} if files else {})})
        content = [{"type": "image", "source": {"type": "base64", "media_type": p["media_type"], "data": p["data"]}} for p in photos]
        note = "\n".join([*(f"[Attached photo: {p['path']}]" for p in photos), *(f["text"] for f in files)])
        content.append({"type": "text", "text": "\n\n".join(x for x in (expand_command(text), note) if x)})
        self.pending = content
        self._write(content, prime)

    def _write(self, content: list, prime: str = ""):
        """A user message to the running process (prime: the earlier conversation in short, before its text)."""
        if prime:
            content = [*content[:-1], {"type": "text", "text": prime + content[-1]["text"]}]
        line = json.dumps({"type": "user", "message": {"role": "user", "content": content}})
        try:
            self.proc.stdin.write((line + "\n").encode("utf-8"))
            self.proc.stdin.flush()
        except OSError as exc:
            self.busy = False
            raise RuntimeError(f"Claude Code stopped unexpectedly ({exc}).") from exc

    def stop(self):
        """Stop the current answer (ends the process; the next message resumes its session)."""
        p = self.proc
        self.pending = self.resumed = None  # (its end is not a resume that failed)
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()
        # its 'exit' event (and the conversation's save) before this returns — not later, into the next turn
        r = self.reader
        if p and r and r is not threading.current_thread():
            r.join(5)
        self.busy = False

    def reset(self):
        """＋ New conversation: the process ends, the next message starts a new one (the old one stays kept)."""
        self.conv = None  # (first: the process's end must not keep it again — it may have just been deleted)
        self.stop()
        with self.lock:
            self.history = []
        self.emit({"type": "reset"})
        self.emit({"type": "conv", "id": None})

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
            if msg.get("type") == "system" and msg.get("subtype") == "init" and proc is self.proc:
                self.resumed = None  # (started: a resume worked)
                if self.conv is not None and msg.get("session_id"):
                    self.conv["session"] = msg["session_id"]
            for ev in translate(msg):
                if ev["type"] == "done":
                    self.busy = False
                    if ev.get("auth"):
                        self._access_refused()
                self.emit(ev)
        code = proc.wait()
        if proc is self.proc and code and self.resumed and self.pending is not None:
            # the session to resume was not there after all: a new one, told the conversation in short, gets the message
            if self.conv is not None:
                self.conv["session"] = None
            try:
                self._write(self.pending, self.start(resume=False))
                return
            except (RuntimeError, OSError):
                pass
        self.busy = False
        if proc is self.proc:
            stderr = "\n".join(self.stderr_tail[-6:])
            auth = bool(code) and ai_access_error(stderr)
            if auth:
                self._access_refused()
            self.emit({"type": "exit", "code": code, "stderr": stderr, "auth": auth})

    def _access_refused(self):
        """Claude refused the access (a bad / expired key, signed out): the stored key is marked invalid, so the
        ✨ AI panel shows its set-up screen; the next message starts a fresh process (with the new access)."""
        from . import ai_access
        ai_access.mark_invalid(ai_access.load_key())
        ai_access._status_cache.clear()


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
        text = msg.get("result") if msg.get("is_error") else None
        return [{"type": "done", "error": bool(msg.get("is_error")), "text": text, "auth": ai_access_error(text),
                 "cost": msg.get("total_cost_usd"), "ms": msg.get("duration_ms")}]
    return []


def ai_access_error(text) -> bool:
    from .ai_access import auth_error
    return auth_error(text)


def _short(name: str) -> str:
    return name.split("__")[-1] if name.startswith("mcp__") else name
