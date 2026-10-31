"""Project files (`.a3d.json`).

Version 3 is a small library: several parts in one project. Today every part is a "classic" part (a PDF
drawing, a picture outline, a DXF or an imported 3D file); its payload is exactly what a version-2 file
held, so the browser loads it with the same code. 3D model parts and assemblies come later
(docs/ARCHITECTURE-modeler.md, project file v3).

Older files (version 1, 2 or none) hold one part; `migrate` wraps it as part P1.
"""

from auto3d.modeler.params import apply_project

VERSION = 3
APP = "Auto3DModeler"

# what a classic part's payload holds (the version-2 file without the app / version / project fields)
CLASSIC_KEYS = ("model", "preview", "values", "userSet", "layers", "bends", "snap", "original",
                "outline_editor", "import_file", "layer_pictures")


class ProjectError(ValueError):
    pass


def _part_name(payload, fallback):
    src = ((payload or {}).get("model") or {}).get("source") or ""
    for ext in (".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg", ".dxf", ".dwg", ".stl", ".obj", ".3mf", ".step", ".stp"):
        if src.lower().endswith(ext):
            return src[: -len(ext)]
    return src or fallback


AI_LOCK_REASONS = ("bought", "made", "approved")


def _ai_lock(p):
    """🔒 A part locked for the AI (web/js/ailock.js): `ai_lock` {reason?} kept as {} or {"reason": bought | made |
    approved}; `true` reads as locked, anything else (false, junk) as not locked."""
    lock = p.get("ai_lock")
    if lock is None:
        return
    if lock is True or isinstance(lock, dict):
        reason = lock.get("reason") if isinstance(lock, dict) else None
        p["ai_lock"] = {"reason": reason} if reason in AI_LOCK_REASONS else {}
    else:
        del p["ai_lock"]


def migrate(proj):
    """Any project file -> version 3 (raises ProjectError for something that is not a project)."""
    if not isinstance(proj, dict) or proj.get("app") != APP:
        raise ProjectError("Not an Auto3DModeler project file.")
    version = proj.get("version") or 1
    if version > VERSION:
        raise ProjectError(f"This project was saved by a newer version of the app (file version {version}).")
    if version == VERSION:
        out = dict(proj)
    else:
        if not proj.get("model"):
            raise ProjectError("The project file has no part in it.")
        payload = {k: proj[k] for k in CLASSIC_KEYS if k in proj}
        out = {"app": APP, "version": VERSION, "project_name": proj.get("project_name") or _part_name(payload, "Project"),
               "unit": (proj.get("model") or {}).get("unit", "mm"),
               "active": {"part": "P1"}, "assets": {},
               "parts": [{"id": "P1", "kind": "classic", "name": _part_name(payload, "Part 1"), "classic": payload}],
               "assemblies": []}
    out.setdefault("assets", {})
    out.setdefault("assemblies", [])
    if not isinstance(out.setdefault("parameters", []), list):
        raise ProjectError("The project's parameters are not a list.")
    parts = out.get("parts")
    if not isinstance(parts, list) or not parts:
        raise ProjectError("The project file has no part in it.")
    seen = set()
    for i, p in enumerate(parts):
        if not isinstance(p, dict) or not p.get("id") or p["id"] in seen:
            raise ProjectError(f"Part {i + 1} in the project file has no id or a duplicate one.")
        seen.add(p["id"])
        p.setdefault("kind", "classic")
        if p["kind"] == "classic" and not (p.get("classic") or {}).get("model"):
            raise ProjectError(f"Part “{p.get('name') or p['id']}” has no model in it.")
        if p["kind"] == "model":
            m = p.setdefault("model", {})
            if not isinstance(m, dict) or not isinstance(m.setdefault("features", []), list):
                raise ProjectError(f"Part “{p.get('name') or p['id']}” has no model in it.")
        elif p["kind"] == "assembly":
            a = p.setdefault("assembly", {})
            if not isinstance(a, dict) or not isinstance(a.setdefault("instances", []), list):
                raise ProjectError(f"Assembly “{p.get('name') or p['id']}” has no parts list in it.")
        elif p["kind"] == "drawing":
            dr = p.setdefault("drawing", {})
            if not isinstance(dr, dict) or not isinstance(dr.setdefault("entities", []), list):
                raise ProjectError(f"Drawing “{p.get('name') or p['id']}” has nothing in it.")
        elif p["kind"] == "sheet":
            sh = p.setdefault("sheet", {})
            if not isinstance(sh, dict) or not sh.get("source"):
                raise ProjectError(f"Drawing sheet “{p.get('name') or p['id']}” does not say its part.")
        elif p["kind"] != "classic":
            raise ProjectError(f"Part “{p.get('name') or p['id']}” is of an unknown kind “{p['kind']}”.")
        p.setdefault("name", _part_name(p.get("classic"), p["id"]))
        _ai_lock(p)
    act = (out.get("active") or {}).get("part")
    if act not in seen:
        out["active"] = {"part": parts[0]["id"]}
    apply_project(out)  # (its numbers as its 𝑥 parameters say)
    return out
