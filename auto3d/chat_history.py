"""Chat history: the AI chat's past conversations, kept to list, read again and continue (🕘 Previous conversations).

Each conversation is two files in the folder: `<id>.json` (its meta and its events: the user's messages with their
photos' links, the AI's text, its tool lines, notes) and `<id>.meta.json` (the meta only, so the list is quick). The meta
says which project it was about (`project`: the autosave id, `project_name`), when, its first message as the title, how
many messages, and the Claude Code session id (`session`) it ran in — continued with `claude --resume` when that
session is still there, else a new session gets `summary()` of it. The oldest go beyond MAX_CONVS.
"""
import json
import re
import time
import uuid
from pathlib import Path

MAX_CONVS = 200
MAX_TITLE = 80
_ID = re.compile(r"^[0-9]{8}-[0-9]{6}-[0-9a-f]{6}$")
META = ("id", "created", "updated", "title", "messages", "project", "project_name", "session")


class ChatHistoryError(Exception):
    pass


def _path(folder: Path, cid: str, suffix: str) -> Path:
    if not isinstance(cid, str) or not _ID.match(cid):
        raise ChatHistoryError("No such conversation.")
    return Path(folder) / f"{cid}{suffix}"


def new(project: str = "", project_name: str = "") -> dict:
    """A new, empty conversation (saved with its first message)."""
    now = time.time()
    return {"id": f"{time.strftime('%Y%m%d-%H%M%S', time.localtime(now))}-{uuid.uuid4().hex[:6]}", "created": now,
            "updated": now, "title": "", "messages": 0, "project": str(project or "")[:64],
            "project_name": str(project_name or "")[:120], "session": None, "events": []}


def keep(ev: dict) -> dict | None:
    """A chat event as the conversation keeps it (None: not kept — streaming pieces, status lines)."""
    t = ev.get("type")
    if t == "user":
        return {"type": "user", "text": ev.get("text") or "", "photos": ev.get("photos") or [],
                **({"tags": ev["tags"]} if ev.get("tags") else {}),  # (#uc #cnc …: the message's ✨ setting tags)
                **({"files": ev["files"]} if ev.get("files") else {})}  # (📎 attached files: name, size, path)
    if t == "text" and (ev.get("text") or "").strip():
        return {"type": "text", "text": ev["text"]}
    if t == "tool":
        return {"type": "tool", "name": ev.get("name") or "", "input": ev.get("input")}
    if t == "tool_result" and ev.get("error"):
        return {"type": "tool_result", "error": True, "text": (ev.get("text") or "")[:400]}
    if t == "note":
        return {k: ev[k] for k in ("type", "key", "text") if k in ev}
    if t == "done" and ev.get("error"):
        return {"type": "done", "error": True, "text": ev.get("text")}
    return None


def add(conv: dict, ev: dict) -> bool:
    """Put a chat event into the conversation -> whether it was kept. The first message of the user is its title."""
    k = keep(ev)
    if not k:
        return False
    conv["events"].append(k)
    if k["type"] == "user" and not conv["title"]:
        first = (k["text"].strip().splitlines() or [""])[0]
        conv["title"] = first[:MAX_TITLE] + ("…" if len(first) > MAX_TITLE else "") or "📎"
    if k["type"] in ("user", "text"):
        conv["messages"] += 1
    conv["updated"] = time.time()
    return True


def save(folder: Path, conv: dict) -> dict:
    """Write the conversation (one without a message is not kept) -> its meta. The oldest go beyond MAX_CONVS."""
    if not conv.get("messages"):
        return {k: conv.get(k) for k in META}
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    meta = {k: conv.get(k) for k in META}
    _path(folder, conv["id"], ".json").write_text(json.dumps(conv, ensure_ascii=False), encoding="utf-8")
    _path(folder, conv["id"], ".meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    for old in list_convs(folder)[MAX_CONVS:]:
        delete(folder, old["id"])
    return meta


def list_convs(folder: Path, project: str | None = None) -> list:
    """The conversations, the newest (last changed) first — their meta only; project: of that project only."""
    out = []
    for p in Path(folder).glob("*.meta.json"):
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if project is None or m.get("project") == project:
            out.append(m)
    return sorted(out, key=lambda m: (m.get("updated", 0), m.get("id", "")), reverse=True)


def load(folder: Path, cid: str) -> dict:
    p = _path(folder, cid, ".json")
    if not p.exists():
        raise ChatHistoryError("No such conversation.")
    conv = json.loads(p.read_text(encoding="utf-8"))
    return {**new(), **conv}


def delete(folder: Path, cid: str):
    if not _path(folder, cid, ".json").exists():
        raise ChatHistoryError("No such conversation.")
    for suffix in (".json", ".meta.json"):
        _path(folder, cid, suffix).unlink(missing_ok=True)


def summary(events: list, limit: int = 4000) -> str:
    """The conversation in short, for a new Claude session that goes on with it: the user's messages and the AI's
    answers (each cut), the tools it used — the newest kept when it is long."""
    lines, tools = [], []

    def flush():
        if tools:
            lines.append(f"(AI used: {', '.join(dict.fromkeys(tools))})")
            tools.clear()

    for ev in events:
        t = ev.get("type")
        if t == "tool":
            tools.append(ev.get("name") or "?")
            continue
        if t not in ("user", "text"):
            continue
        flush()
        text = re.sub(r"\s+", " ", ev.get("text") or "").strip()
        if t == "user" and ev.get("photos"):
            text = f"{text} [{len(ev['photos'])} photo(s)]".strip()
        if t == "user" and ev.get("files"):
            text = f"{text} [Attached: {', '.join(f.get('path') or f.get('name') or '' for f in ev['files'])}]".strip()
        cut = 300 if t == "user" else 400
        lines.append(f"{'User' if t == 'user' else 'AI'}: {text[:cut]}{'…' if len(text) > cut else ''}")
    flush()
    out, size = [], 0
    for line in reversed(lines):
        if size + len(line) > limit:
            out.append("… (earlier messages left out)")
            break
        out.append(line)
        size += len(line) + 1
    return "\n".join(reversed(out))
