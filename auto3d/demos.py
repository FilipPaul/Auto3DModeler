"""🎬 Demo projects: ready-made project files (demos/*.a3d, read-only) that show what the app does — whole
mechanisms moving in an assembly. Each file is a normal project (an .a3d package: auto3d/package.py) whose project.json
has a "demo" record: {"name": "…", "name_cs": "…", "text": "what it shows", "text_cs": "…", "order": 1}; its picture
(thumbnail.png) is shown on its card. The app opens one as a new project (a copy: the demo file never changes).
tools/make_demos.py builds them through the app.
"""
from pathlib import Path

from auto3d import package
from auto3d.project import ProjectError, migrate


class DemoError(ValueError):
    pass


def _files(folder):
    return sorted(Path(folder).glob("*.a3d")) if Path(folder).is_dir() else []


def listing(folder):
    """The demos in `folder` -> [{file, name, name_cs, text, text_cs, parts, thumb}], in their order."""
    out = []
    for f in _files(folder):
        try:
            proj = package.manifest(f)
            thumb = package.thumbnail(f) is not None
        except (OSError, package.PackageError):
            continue
        demo = proj.get("demo") if isinstance(proj.get("demo"), dict) else {}
        name = demo.get("name") or proj.get("project_name") or f.name[:-len(".a3d")]
        out.append({"file": f.name, "name": name, "name_cs": demo.get("name_cs") or name, "text": demo.get("text") or "",
                    "text_cs": demo.get("text_cs") or demo.get("text") or "", "order": demo.get("order", 99),
                    "parts": [p.get("name") for p in proj.get("parts") or [] if isinstance(p, dict)], "thumb": thumb})
    out.sort(key=lambda d: (d["order"], d["file"]))
    return out


def _file(folder, name) -> Path:
    """A demo by its file name: only a file of `folder` itself."""
    if not isinstance(name, str) or "/" in name or "\\" in name or not name.endswith(".a3d"):
        raise DemoError("Not a demo file name.")
    f = Path(folder) / name
    if f not in _files(folder):
        raise DemoError(f"No demo “{name}”.")
    return f


def load(folder, name, put=None):
    """One demo by its file name -> the project (version 3), to open as a copy; its imported files (if any) into the
    blob store through `put(bytes) -> sha`."""
    f = _file(folder, name)
    try:
        got = package.load(f)
        return migrate(package.store(got, put) if put else got["project"])
    except (OSError, ValueError, ProjectError) as e:
        raise DemoError(f"The demo “{name}” cannot be read: {e}") from e


def thumbnail(folder, name):
    """A demo's picture (PNG bytes) or None."""
    try:
        return package.thumbnail(_file(folder, name))
    except (OSError, package.PackageError):
        return None
