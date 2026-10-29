"""🎬 Demo projects: ready-made project files (demos/*.a3d.json, read-only) that show what the app does — whole
mechanisms moving in an assembly. Each file is a normal project (version 3) with a "demo" record:
{"name": "…", "name_cs": "…", "text": "what it shows", "text_cs": "…", "order": 1}. The app opens one as a new
project (a copy: the demo file never changes). tools/make_demos.py builds them through the app.
"""
import json
from pathlib import Path

from auto3d.project import ProjectError, migrate


class DemoError(ValueError):
    pass


def _files(folder):
    return sorted(Path(folder).glob("*.a3d.json")) if Path(folder).is_dir() else []


def listing(folder):
    """The demos in `folder` -> [{file, name, name_cs, text, text_cs, parts}], in their order."""
    out = []
    for f in _files(folder):
        try:
            proj = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        demo = proj.get("demo") if isinstance(proj.get("demo"), dict) else {}
        name = demo.get("name") or proj.get("project_name") or f.name[:-len(".a3d.json")]
        out.append({"file": f.name, "name": name, "name_cs": demo.get("name_cs") or name, "text": demo.get("text") or "",
                    "text_cs": demo.get("text_cs") or demo.get("text") or "", "order": demo.get("order", 99),
                    "parts": [p.get("name") for p in proj.get("parts") or [] if isinstance(p, dict)]})
    out.sort(key=lambda d: (d["order"], d["file"]))
    return out


def load(folder, name):
    """One demo by its file name -> the project (version 3), to open as a copy. Only a file of `folder` itself."""
    if not isinstance(name, str) or "/" in name or "\\" in name or not name.endswith(".a3d.json"):
        raise DemoError("Not a demo file name.")
    f = Path(folder) / name
    if f not in _files(folder):
        raise DemoError(f"No demo “{name}”.")
    try:
        return migrate(json.loads(f.read_text(encoding="utf-8")))
    except (OSError, ValueError, ProjectError) as e:
        raise DemoError(f"The demo “{name}” cannot be read: {e}") from e
