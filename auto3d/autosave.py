"""Autosave: the project on screen kept on the server (data/projects/) a few seconds after each change, so a closed tab
or a browser crash loses nothing — and the recent projects to open again. One file per project (the latest state) and
a small meta file for the list; the oldest go beyond MAX_PROJECTS.
"""
import json
import os
import re
import threading
import time
from pathlib import Path

MAX_PROJECTS = 40
_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")
_LOCKS = {}  # project id -> its lock: two saves of one project at once go one after the other
_LOCKS_LOCK = threading.Lock()


class AutosaveError(Exception):
    pass


def _check(pid):
    if not isinstance(pid, str) or not _ID.match(pid):
        raise AutosaveError("No such project.")
    return pid


def _lock(pid):
    with _LOCKS_LOCK:
        return _LOCKS.setdefault(pid, threading.Lock())


def _pause(i):
    """The wait before try i+1 after a sharing violation: short at first, longer under load (~8 s in all over 40 tries)."""
    return min(0.02 * (1.25 ** i), 0.25)


def _write(path: Path, text: str, tries=40):
    """Write whole or not at all: a temp file of this thread, then replace. On Windows the replace fails while
    another reader has the file open (WinError 32 / 5, a sharing violation): try again for up to ~8 s (a busy
    machine can hold a reader that long)."""
    tmp = path.with_name(f"{path.name}.{os.getpid()}-{threading.get_ident()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    try:
        for i in range(tries):
            try:
                tmp.replace(path)
                return
            except PermissionError:
                if i == tries - 1:
                    raise
                time.sleep(_pause(i))
    finally:
        tmp.unlink(missing_ok=True)


def _read(path: Path, tries=40) -> str:
    for i in range(tries):  # (a replace under way can deny the read for a moment on Windows)
        try:
            return path.read_text(encoding="utf-8")
        except PermissionError:
            if i == tries - 1:
                raise
            time.sleep(_pause(i))


def save(folder: Path, pid: str, project: dict) -> dict:
    """Keep the project (as the Save project file, without its imported files: those are in the blob store) -> its meta."""
    _check(pid)
    if not isinstance(project, dict) or not isinstance(project.get("parts"), list) or not project["parts"]:
        raise AutosaveError("A project with parts is kept.")
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    text = json.dumps(project)
    meta = {"id": pid, "name": project.get("project_name") or (project["parts"][0].get("name") if project["parts"] else "") or "Project",
            "time": time.time(), "size": len(text),
            "parts": [{"name": p.get("name", ""), "kind": p.get("kind", "")} for p in project["parts"] if isinstance(p, dict)]}
    with _lock(pid):  # (whole or not at all: a crash while writing keeps the last one)
        _write(folder / f"{pid}.json", text)
        _write(folder / f"{pid}.meta.json", json.dumps(meta))
    for old in recent(folder)[MAX_PROJECTS:]:
        delete(folder, old["id"])
    return meta


def recent(folder: Path) -> list:
    """The kept projects, the latest first (their meta)."""
    out = []
    for p in Path(folder).glob("*.meta.json"):
        try:
            m = json.loads(_read(p))
        except (OSError, ValueError):
            continue
        if (Path(folder) / f"{m.get('id')}.json").exists():
            out.append(m)
    return sorted(out, key=lambda m: m.get("time", 0), reverse=True)


def load(folder: Path, pid: str) -> dict:
    p = Path(folder) / f"{_check(pid)}.json"
    if not p.exists():
        raise AutosaveError("No such project.")
    return json.loads(_read(p))


# names the app gives by itself (English / Czech): a project or part not named by the user
_DEFAULT_NAME = re.compile(r"^\s*(project|projekt|3d model|3d modelu|assembly|sestava|drawing|výkres|untitled|nový projekt)?\s*\d*\s*$", re.I)


def _empty_part(p: dict) -> bool:
    """A part with nothing in it: a 3D model without steps, an assembly without parts, a drawing without shapes."""
    kind = p.get("kind")
    data = p.get("classic" if kind == "classic" else kind) or {}
    if kind == "model":
        return not data.get("features")
    if kind == "assembly":
        return not data.get("instances")
    if kind == "drawing":
        return not data.get("entities")
    if kind == "sheet":
        return False  # (a drawing sheet is of something)
    return not data  # a quick part: its drawing / picture / file


def empty_default(project: dict) -> bool:
    """A project worth nothing to keep: every part empty, and it and its parts still have the names the app gave."""
    parts = [p for p in project.get("parts") or [] if isinstance(p, dict)]
    names = [project.get("project_name") or ""] + [p.get("name") or "" for p in parts]
    return all(_empty_part(p) for p in parts) and all(_DEFAULT_NAME.match(n) for n in names)


def cleanup(folder: Path, keep=None, dry_run=False) -> list:
    """🧹 Delete the empty projects with default names (not `keep`: the one on screen) -> their metas."""
    out = []
    for m in recent(folder):
        if m.get("id") == keep:
            continue
        try:
            project = load(folder, m["id"])
        except (AutosaveError, OSError, ValueError):
            continue
        if empty_default(project):
            out.append(m)
            if not dry_run:
                delete(folder, m["id"])
    return out


def delete(folder: Path, pid: str) -> None:
    for suffix in (".json", ".meta.json"):
        (Path(folder) / f"{_check(pid)}{suffix}").unlink(missing_ok=True)
