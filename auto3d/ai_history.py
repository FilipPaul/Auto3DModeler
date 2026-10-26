"""AI history: the whole project (every part) as it was after each AI turn, kept on the server to browse and load back.

Each state is two files in the folder: `<id>.json` (the project, as the Save project file without its imported files —
those stay in the blob store) and `<id>.meta.json` (when, the message that made it, the parts), so the list is quick.
A state the same as the newest one is not saved again; the oldest go beyond MAX_STATES.
"""
import hashlib
import json
import re
import time
from pathlib import Path

MAX_STATES = 300
MAX_PROMPT = 500
_ID = re.compile(r"^[0-9]{8}-[0-9]{6}-[0-9a-f]{6}(-[0-9]+)?$")


class HistoryError(Exception):
    pass


def _digest(project: dict) -> str:
    return hashlib.sha256(json.dumps(project, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _path(folder: Path, sid: str, suffix: str) -> Path:
    if not isinstance(sid, str) or not _ID.match(sid):
        raise HistoryError("No such state.")
    return Path(folder) / f"{sid}{suffix}"


def list_states(folder: Path) -> list:
    """The saved states, newest first (their meta only)."""
    out = []
    for p in Path(folder).glob("*.meta.json"):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return sorted(out, key=lambda m: (m.get("time", 0), m.get("id", "")), reverse=True)


def save_state(folder: Path, project: dict, prompt: str = "", tools: int = 0, kind: str = "ai") -> dict:
    """Keep the project -> its meta ({..., "same": True} when it equals the newest state, which is then not saved again).
    kind: "ai" (after an AI turn) or "before-load" (the project as it was before a state was loaded back)."""
    if not isinstance(project, dict) or not isinstance(project.get("parts"), list):
        raise HistoryError("The state needs the project's parts.")
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    digest = _digest(project)
    states = list_states(folder)
    if states and states[0].get("digest") == digest:
        return {**states[0], "same": True}
    now = time.time()
    sid = f"{time.strftime('%Y%m%d-%H%M%S', time.localtime(now))}-{digest[:6]}"
    n = 1
    while (folder / f"{sid}.json").exists():
        n += 1
        sid = f"{time.strftime('%Y%m%d-%H%M%S', time.localtime(now))}-{digest[:6]}-{n}"
    meta = {
        "id": sid, "time": now, "kind": kind if kind in ("ai", "before-load") else "ai",
        "prompt": str(prompt or "")[:MAX_PROMPT], "tools": int(tools or 0), "digest": digest,
        "name": project.get("project_name") or "",
        "parts": [{"name": p.get("name", ""), "kind": p.get("kind", "")} for p in project["parts"] if isinstance(p, dict)],
    }
    (folder / f"{sid}.json").write_text(json.dumps(project), encoding="utf-8")
    (folder / f"{sid}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    for old in ([meta] + states)[MAX_STATES:]:  # (states is newest first; the new one is the newest of all)
        for suffix in (".json", ".meta.json"):
            _path(folder, old["id"], suffix).unlink(missing_ok=True)
    return meta


def load_state(folder: Path, sid: str) -> dict:
    p = _path(folder, sid, ".json")
    if not p.exists():
        raise HistoryError("No such state.")
    return json.loads(p.read_text(encoding="utf-8"))


def delete_state(folder: Path, sid: str) -> None:
    for suffix in (".json", ".meta.json"):
        _path(folder, sid, suffix).unlink(missing_ok=True)
