"""Autosave: the project on screen kept on the server (data/projects/) a few seconds after each change, so a closed tab
or a browser crash loses nothing — and the recent projects to open again. One file per project (the latest state) and
a small meta file for the list; the oldest go beyond MAX_PROJECTS.
"""
import json
import re
import time
from pathlib import Path

MAX_PROJECTS = 40
_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")


class AutosaveError(Exception):
    pass


def _check(pid):
    if not isinstance(pid, str) or not _ID.match(pid):
        raise AutosaveError("No such project.")
    return pid


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
    tmp = folder / f"{pid}.json.tmp"
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(folder / f"{pid}.json")  # (whole or not at all: a crash while writing keeps the last one)
    (folder / f"{pid}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    for old in recent(folder)[MAX_PROJECTS:]:
        delete(folder, old["id"])
    return meta


def recent(folder: Path) -> list:
    """The kept projects, the latest first (their meta)."""
    out = []
    for p in Path(folder).glob("*.meta.json"):
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (Path(folder) / f"{m.get('id')}.json").exists():
            out.append(m)
    return sorted(out, key=lambda m: m.get("time", 0), reverse=True)


def load(folder: Path, pid: str) -> dict:
    p = Path(folder) / f"{_check(pid)}.json"
    if not p.exists():
        raise AutosaveError("No such project.")
    return json.loads(p.read_text(encoding="utf-8"))


def delete(folder: Path, pid: str) -> None:
    for suffix in (".json", ".meta.json"):
        (Path(folder) / f"{_check(pid)}{suffix}").unlink(missing_ok=True)
