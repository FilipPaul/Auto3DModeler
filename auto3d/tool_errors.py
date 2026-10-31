"""Every AI tool call that failed, logged for the developers on its own (no AI tokens, nothing for the AI to remember):
one digest a day next to the AI's reports — RealSWReports/<date>-tool-errors.md, the errors most frequent first —
written from its data, <date>-tool-errors.json. The same tool with the same message (its numbers, ids and quoted names
left out) counts up instead of a new entry; a day holds at most MAX_ENTRIES different ones. Deliberate refusals (the
🔒 AI lock, the internet switched off — EXPECTED) are not errors and are left out.

record() only queues the entry: a thread writes it, so a tool call never waits for the disk and a write that fails
never breaks it. Standard library only.
"""
from __future__ import annotations

import json
import queue
import re
import threading
import time
from pathlib import Path

SUFFIX = "-tool-errors"   # <date>-tool-errors.md (the digest) / .json (its data)
MAX_ENTRIES = 500         # different errors a day (more: only counted as left out)
ARGS_MAX = 2000           # characters of a call's arguments kept
STR_MAX = 300             # characters of one string argument kept (a picture, a long sketch: its length only)
# refusals that are the tool doing its job, not a fault (the message, without "<tool> failed: ", starts with one)
EXPECTED = ("🔒", "internet je vypnut", "the internet is off", "internet is off")

_queue: queue.Queue = queue.Queue()
_lock = threading.Lock()
_thread: threading.Thread | None = None


def message(tool: str, text: str) -> str:
    """The error's own words: without the "<tool> failed: " the relay puts before it."""
    text = str(text or "").strip()
    return text[len(tool) + 9:].strip() if text.startswith(f"{tool} failed: ") else text


def expected(tool: str, text: str, result: dict | None = None) -> bool:
    """True for a deliberate refusal (correct behaviour): the result says expected: true, or its message starts with one
    of EXPECTED."""
    if isinstance(result, dict) and result.get("expected"):
        return True
    return message(tool, text).lower().startswith(EXPECTED)


def key(tool: str, text: str) -> str:
    """What makes two errors the same one: the tool and its message without numbers, ids and quoted names."""
    m = message(tool, text).lower()
    m = re.sub(r"([\"'“‘`])[^\"'”’`\n]{0,80}[\"'”’`]", "…", m)            # "Bracket", 'f3', “Part 1”
    m = re.sub(r"\b[\w-]*\d[\w.-]*", "#", m)                            # f12, s3, 4.5, 2026-10-31, a1b2c3d4
    m = re.sub(r"#(?:[\s,;/]+#)+", "#", m)                              # (steps: f1, f2, f3) ~ (steps: f1)
    return f"{tool}: {re.sub(r'\s+', ' ', m).strip()[:300]}"


def _small(v, depth=0):
    """The arguments without their bulk: a long string -> its start and length, a picture -> its length only."""
    if isinstance(v, str):
        if len(v) > STR_MAX:
            if v.startswith("data:") or " " not in v[:200]:  # (base64 pictures, blobs)
                return f"<{len(v)} characters of data>"
            return f"{v[:STR_MAX]}… ({len(v)} characters)"
        return v
    if depth > 6:
        return "…"
    if isinstance(v, dict):
        return {str(k): _small(x, depth + 1) for k, x in list(v.items())[:40]}
    if isinstance(v, list):
        return [_small(x, depth + 1) for x in v[:40]] + ([f"… {len(v) - 40} more"] if len(v) > 40 else [])
    return v


def shorten_args(args) -> str:
    """A call's arguments as kept in the log: JSON, the bulk left out, at most ARGS_MAX characters."""
    try:
        s = json.dumps(_small(args), ensure_ascii=False)
    except (TypeError, ValueError):
        s = repr(args)
    return s if len(s) <= ARGS_MAX else s[:ARGS_MAX] + f"… ({len(s)} characters)"


def record(folder: Path, tool: str, args, text: str, version="", where: dict | None = None, conversation: str = "",
           result: dict | None = None) -> bool:
    """Log a failed tool call (queued: written by a thread). version: the app's version line, or a function giving it
    (asked in that thread: it may ask git). -> False when it is not logged (a deliberate refusal)."""
    try:
        if expected(tool, text, result):
            return False
        entry = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "tool": str(tool), "error": message(tool, text)[:2000],
                 "key": key(tool, text), "args": shorten_args(args), "version": version,
                 "where": {k: str(v)[:120] for k, v in (where or {}).items() if v} if isinstance(where, dict) else {},
                 "conversation": str(conversation or "")}
        _start()
        _queue.put((Path(folder), entry))
        return True
    except Exception:  # (logging never breaks the call)
        return False


def flush(timeout: float = 10.0):
    """Wait until what is queued is written (tests, the app quitting)."""
    end = time.time() + timeout
    while _queue.unfinished_tasks and time.time() < end:
        time.sleep(0.02)


def _start():
    global _thread
    with _lock:
        if _thread is None or not _thread.is_alive():
            _thread = threading.Thread(target=_run, name="tool-errors", daemon=True)
            _thread.start()


def _run():
    while True:
        folder, entry = _queue.get()
        try:
            write(folder, entry)
        except Exception:  # (a full disk, a folder that cannot be made: the entry is lost, the app goes on)
            pass
        finally:
            _queue.task_done()


def day_files(folder: Path, day: str) -> tuple[Path, Path]:
    """(the digest .md, its data .json) of a day (YYYY-MM-DD)."""
    return folder / f"{day}{SUFFIX}.md", folder / f"{day}{SUFFIX}.json"


def load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) and isinstance(data.get("entries"), list) else {"entries": [], "left_out": 0}
    except (OSError, ValueError):
        return {"entries": [], "left_out": 0}


def write(folder: Path, entry: dict):
    """Add one failed call to its day's log (now, in this thread): counted with the same error, else a new entry."""
    if callable(entry.get("version")):
        try:
            entry = {**entry, "version": str(entry["version"]() or "")}
        except Exception:
            entry = {**entry, "version": ""}
    entry["version"] = str(entry.get("version") or "")
    day = entry["time"][:10]
    md, js = day_files(folder, day)
    with _lock:
        data = load(js)
        same = next((e for e in data["entries"] if e.get("key") == entry["key"]), None)
        if same:
            same["count"] = int(same.get("count", 1)) + 1
            same["last"] = entry["time"]
            convs = same.setdefault("conversations", [])
            if entry["conversation"] and entry["conversation"] not in convs and len(convs) < 5:
                convs.append(entry["conversation"])
        elif len(data["entries"]) >= MAX_ENTRIES:
            data["left_out"] = int(data.get("left_out", 0)) + 1
        else:
            data["entries"].append({"key": entry["key"], "tool": entry["tool"], "error": entry["error"], "count": 1,
                                    "first": entry["time"], "last": entry["time"], "version": entry["version"],
                                    "args": entry["args"], "where": entry["where"],
                                    "conversations": [entry["conversation"]] if entry["conversation"] else []})
        data["version"] = entry["version"] or data.get("version", "")
        folder.mkdir(parents=True, exist_ok=True)
        js.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        md.write_text(digest(day, data), encoding="utf-8")


def digest(day: str, data: dict) -> str:
    """A day's log as Markdown: a head like a report's, then each error (the most frequent first)."""
    rows = sorted(data["entries"], key=lambda e: (-int(e.get("count", 1)), e.get("first", "")))
    calls = sum(int(e.get("count", 1)) for e in rows)
    out = [f"# Tool errors {day}", "", "- **Kind:** tool errors", f"- **Date:** {day}",
           f"- **App version:** {data.get('version') or '?'}",
           "- **Reported by:** the app, on its own (every AI tool call that failed; the same tool and message counted)",
           f"- **Errors:** {len(rows)} different, {calls} call{'s' if calls != 1 else ''}"
           + (f"; {data['left_out']} more left out (over {MAX_ENTRIES} different)" if data.get("left_out") else "")]
    for i, e in enumerate(rows, 1):
        where = " · ".join(f"{k} {v}" for k, v in (e.get("where") or {}).items())
        when = e["first"][11:] + (f" … {e['last'][11:]}" if e.get("last") != e.get("first") else "")
        out += ["", f"## {i}. {e['tool']} — ×{e.get('count', 1)}", "", f"- **Error:** {' '.join(e['error'].split())}", f"- **When:** {when}"]
        if e.get("version") and e["version"] != data.get("version"):
            out.append(f"- **App version:** {e['version']}")
        if where:
            out.append(f"- **Where:** {where}")
        if e.get("conversations"):
            out.append(f"- **Conversation:** {', '.join(e['conversations'])}")
        out += [f"- **Arguments:** `{e['args'].replace('`', 'ˋ')}`"]
    return "\n".join(out) + "\n"


def top(folder: Path, days: int = 7, limit: int = 10) -> list[dict]:
    """The most frequent tool errors of the last `days` days (merged over days): [{tool, error, count, last, days}]."""
    if not folder.is_dir():
        return []
    since = time.strftime("%Y-%m-%d", time.localtime(time.time() - (days - 1) * 86400))
    merged: dict[str, dict] = {}
    for f in sorted(folder.glob(f"*{SUFFIX}.json")):
        day = f.name[:10]
        if day < since:
            continue
        for e in load(f)["entries"]:
            m = merged.setdefault(e.get("key", ""), {"tool": e.get("tool", ""), "error": e.get("error", ""), "count": 0, "last": "", "days": 0})
            m["count"] += int(e.get("count", 1))
            m["last"] = max(m["last"], str(e.get("last", "")))
            m["days"] += 1
    rows = sorted(merged.values(), key=lambda r: (r["count"], r["last"]), reverse=True)
    return rows[:limit]
