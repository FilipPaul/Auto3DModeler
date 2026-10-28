"""Title-block templates of drawing sheets (📄): what the title block shows and how, its fixed texts (company,
address, drawn by, a default note, the tolerance standard), a logo and the sheet's frame (margins, line, zones,
centring marks). Kept next to the server (data/title_templates.json), so every project can use them; the app's own
ones (BUILTIN) cannot be changed. web/js/sheet/sheet.js draws them; a sheet names its template (d.template), an
assembly's drawing set takes its top sheet's.

A template: {name, layout: "block" | "strip", titleStyle: "block" | "strip" | "A" … "E", bomStyle: "modern" | "A" …
"E", hide: [field], texts: {company, address, drawn, note, tolstd, surface}, logo: "data:image/…;base64,…" | null,
frame: {preset: simple | iso | narrow | none | custom, m: [left, top, right, bottom] mm, line: mm, zones: bool, marks:
bool}}. The title block's style and the parts list's are apart — any two together (web/js/sheet/tbstyles.js: A strip,
B ISO 7200, C dark band, D minimal, E column; block / strip / modern the app's first ones); an older template without
them: its layout, the modern parts list.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

FILE = "title_templates.json"
LAYOUTS = ("block", "strip")
FIELDS = ("material", "scale", "paper", "tolerances", "created", "changed", "number", "drawn", "note", "company")
TEXTS = ("company", "address", "drawn", "note", "tolstd", "surface")
TITLE_STYLES = ("block", "strip", "A", "B", "C", "D", "E")
BOM_STYLES = ("modern", "A", "B", "C", "D", "E")
PRESETS = ("simple", "iso", "narrow", "none", "custom")
LOGO_MAX = 400_000  # characters of a logo's data URL (a small picture: it goes into every page)

FRAMES = {  # the frame presets (a sheet's frame: its preset's, or custom)
    "simple": {"preset": "simple", "m": [10, 10, 10, 10], "line": 0.5, "zones": False, "marks": False},
    "iso": {"preset": "iso", "m": [20, 10, 10, 10], "line": 0.7, "zones": True, "marks": True},
    "narrow": {"preset": "narrow", "m": [5, 5, 5, 5], "line": 0.35, "zones": False, "marks": False},
    "none": {"preset": "none", "m": [10, 10, 10, 10], "line": 0, "zones": False, "marks": False},
}

BUILTIN = [
    {"name": "Modern", "builtin": True, "layout": "block", "titleStyle": "block", "bomStyle": "modern", "hide": [], "texts": {}, "logo": None, "frame": FRAMES["simple"]},
    {"name": "Compact", "builtin": True, "layout": "strip", "titleStyle": "strip", "bomStyle": "modern", "hide": ["created", "note", "company"], "texts": {}, "logo": None, "frame": FRAMES["narrow"]},
    {"name": "ISO 5457", "builtin": True, "layout": "block", "titleStyle": "block", "bomStyle": "modern", "hide": [], "texts": {"tolstd": "ISO 2768-mK"}, "logo": None, "frame": FRAMES["iso"]},
] + [  # the owner's five designs: each title block with its own parts list (any other pair: a template of the user's)
    {"name": name, "builtin": True, "layout": "block", "titleStyle": k, "bomStyle": k, "hide": [], "texts": {}, "logo": None, "frame": FRAMES[frame]}
    for k, name, frame in (("A", "A — Strip", "simple"), ("B", "B — ISO 7200", "iso"), ("C", "C — Dark band", "simple"),
                           ("D", "D — Minimal", "simple"), ("E", "E — Column", "simple"))
]


class TemplateError(Exception):
    pass


def check_frame(fr) -> dict:
    """A frame as given -> a clean one (a preset's values, or custom with its numbers kept in range)."""
    if not isinstance(fr, dict):
        return dict(FRAMES["simple"])
    preset = fr.get("preset") if fr.get("preset") in PRESETS else "custom"
    if preset != "custom":
        return dict(FRAMES[preset])
    m = fr.get("m") if isinstance(fr.get("m"), list) else [fr.get("m", 10)]
    try:
        m = [max(0.0, min(40.0, float(v))) for v in (m * 4)[:4]]
        line = max(0.0, min(2.0, float(fr.get("line", 0.5))))
    except (TypeError, ValueError):
        raise TemplateError("frame: margins m [left, top, right, bottom] and line are numbers (mm).") from None
    return {"preset": "custom", "m": m, "line": line, "zones": bool(fr.get("zones")), "marks": bool(fr.get("marks"))}


def check(tpl) -> dict:
    """A template as sent -> a clean one; TemplateError says what is wrong."""
    if not isinstance(tpl, dict):
        raise TemplateError("A template is an object {name, layout, hide, texts, logo, frame}.")
    name = re.sub(r"\s+", " ", str(tpl.get("name") or "")).strip()
    if not name or len(name) > 60:
        raise TemplateError("name: 1 to 60 characters.")
    if any(b["name"].lower() == name.lower() for b in BUILTIN):
        raise TemplateError(f"{name} is one of the app's own templates — give yours another name.")
    layout = tpl.get("layout") or "block"
    if layout not in LAYOUTS:
        raise TemplateError(f"layout: {' or '.join(LAYOUTS)}.")
    style = tpl.get("titleStyle") or layout
    if style not in TITLE_STYLES:
        raise TemplateError(f"titleStyle: {', '.join(TITLE_STYLES)}.")
    bom = tpl.get("bomStyle") or "modern"
    if bom not in BOM_STYLES:
        raise TemplateError(f"bomStyle: {', '.join(BOM_STYLES)}.")
    if style in ("block", "strip"):
        layout = style
    hide = [f for f in (tpl.get("hide") or []) if f in FIELDS]
    texts = {k: str(v).strip()[:200] for k, v in (tpl.get("texts") or {}).items() if k in TEXTS and str(v or "").strip()}
    logo = tpl.get("logo") or None
    if logo is not None:
        if not re.match(r"^data:image/(png|jpeg|svg\+xml);base64,[A-Za-z0-9+/=]+$", str(logo)):
            raise TemplateError("logo: a PNG, JPEG or SVG picture (a data URL).")
        if len(logo) > LOGO_MAX:
            raise TemplateError(f"logo: too big ({len(logo) // 1000} kB) — at most {LOGO_MAX // 1000} kB; use a smaller picture.")
    return {"name": name, "layout": layout, "titleStyle": style, "bomStyle": bom, "hide": hide, "texts": texts, "logo": logo, "frame": check_frame(tpl.get("frame"))}


def _read(folder: Path) -> list:
    try:
        data = json.loads((Path(folder) / FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for t in data.get("templates", []) if isinstance(data, dict) else []:
        try:
            out.append(check(t))
        except TemplateError:
            continue  # (a broken one left out)
    return out


def _write(folder: Path, items: list):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    tmp = folder / (FILE + ".tmp")
    tmp.write_text(json.dumps({"templates": items}, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(folder / FILE)


def load(folder: Path) -> list:
    """The app's templates, then the user's (by name)."""
    return [dict(b) for b in BUILTIN] + sorted(_read(folder), key=lambda t: t["name"].lower())


def save(folder: Path, tpl) -> dict:
    """Keep a template (one of the same name is replaced) -> it as kept."""
    clean = check(tpl)
    items = [t for t in _read(folder) if t["name"].lower() != clean["name"].lower()] + [clean]
    _write(folder, items)
    return clean


def delete(folder: Path, name: str):
    """Remove a user's template; the app's own cannot be removed."""
    if any(b["name"].lower() == str(name).lower() for b in BUILTIN):
        raise TemplateError(f"{name} is one of the app's own templates.")
    items = _read(folder)
    keep = [t for t in items if t["name"].lower() != str(name).lower()]
    if len(keep) == len(items):
        raise TemplateError(f"No template {name}.")
    _write(folder, keep)
