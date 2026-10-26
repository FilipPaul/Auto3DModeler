"""2D drawings (DXF / DWG) as they are: every line, circle, arc, polyline and text with its layer and colour, in mm —
for the drawing viewer / editor (web/js/drawing2d). What to make of it is chosen there: a sketch of a 3D model, or
a quick part (the closed outlines, as before).

Drawing JSON (in the project file, `parts[].drawing`):
  {"source": "plate.dxf", "unit": "mm",
   "layers": [{"name": "0", "color": "#ffffff", "visible": true}],
   "entities": [{"id": "e1", "layer": "0", "t": "line", "a": [x, y], "b": [x, y]},
                {"t": "circle", "c": [x, y], "r": 5}, {"t": "arc", "c", "r", "a0": deg, "a1": deg},   (counter-clockwise)
                {"t": "poly", "pts": [[x, y], ...], "closed": true}, {"t": "text", "at": [x, y], "h": 3.5, "text": "…", "rot": 0}],
   "color" on an entity: its own colour (else its layer's)}
"""
from __future__ import annotations

import math
import os
import tempfile

from .importers import DXF_UNITS_MM, ImportError_, dwg_to_dxf, outline_polys


def _hex(rgb):
    return "#%02x%02x%02x" % tuple(int(v) for v in rgb)


def read_drawing(data: bytes, name: str) -> dict:
    """A DXF (or DWG, converted) -> the drawing JSON above."""
    try:
        import ezdxf
        from ezdxf import colors as dxfcolors
        from ezdxf import path as dxfpath
        from ezdxf import recover
    except ImportError as exc:
        raise ImportError_("DXF import needs the 'ezdxf' package (pip install ezdxf).") from exc
    if name.lower().endswith(".dwg"):
        data = dwg_to_dxf(data)
    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
        f.write(data)
        fname = f.name
    try:
        doc, _auditor = recover.readfile(fname)
    except Exception as exc:
        raise ImportError_(f"not a readable DXF file ({exc})") from exc
    finally:
        os.unlink(fname)
    code = int(doc.header.get("$INSUNITS", 0) or 0)
    k = DXF_UNITS_MM.get(code, 1.0) or 1.0
    declared = {1: "in", 4: "mm", 5: "cm", 6: "m"}.get(code)  # None: the file does not say (read as mm)

    def aci(i):
        try:
            return _hex(dxfcolors.aci2rgb(int(i)))
        except Exception:  # noqa: BLE001
            return "#ffffff"

    layers = {}
    for ly in doc.layers:
        c = ly.dxf.get("true_color")
        layers[ly.dxf.name] = {"name": ly.dxf.name, "color": _hex(dxfcolors.int2rgb(c)) if c else aci(abs(ly.dxf.get("color", 7)) or 7),
                               "visible": ly.is_on() and not ly.is_frozen()}

    out, n = [], [0]
    P = lambda v: [round(v.x * k, 6), round(v.y * k, 6)]  # noqa: E731

    def add(e, layer, **geo):
        n[0] += 1
        item = {"id": f"e{n[0]}", "layer": layer, **geo}
        tc, ac = e.dxf.get("true_color"), e.dxf.get("color", 256)
        if tc:
            item["color"] = _hex(dxfcolors.int2rgb(tc))
        elif ac not in (0, 256):  # not BYBLOCK / BYLAYER
            item["color"] = aci(ac)
        out.append(item)

    def walk(container, parent_layer=None, depth=0):
        for e in container:
            t = e.dxftype()
            layer = e.dxf.get("layer", "0")
            if layer == "0" and parent_layer:
                layer = parent_layer  # in a block: on the layer of its insert
            layers.setdefault(layer, {"name": layer, "color": "#ffffff", "visible": True})
            try:
                if t == "LINE":
                    add(e, layer, t="line", a=P(e.dxf.start), b=P(e.dxf.end))
                elif t == "CIRCLE":
                    add(e, layer, t="circle", c=P(e.dxf.center), r=round(e.dxf.radius * k, 6))
                elif t == "ARC":
                    add(e, layer, t="arc", c=P(e.dxf.center), r=round(e.dxf.radius * k, 6),
                        a0=round(e.dxf.start_angle, 6), a1=round(e.dxf.end_angle, 6))
                elif t in ("LWPOLYLINE", "POLYLINE", "SPLINE", "ELLIPSE"):
                    pts = [P(v) for v in dxfpath.make_path(e).flattening(0.01 / k)]
                    if len(pts) >= 2:
                        closed = bool(getattr(e, "closed", False) or getattr(e, "is_closed", False)) or math.dist(pts[0], pts[-1]) < 1e-9
                        add(e, layer, t="poly", pts=pts[:-1] if closed and math.dist(pts[0], pts[-1]) < 1e-9 else pts, closed=closed)
                elif t in ("TEXT", "MTEXT"):
                    txt = e.plain_text() if t == "MTEXT" else e.dxf.text
                    h = e.dxf.get("char_height" if t == "MTEXT" else "height", 2.5)
                    at = e.dxf.insert
                    add(e, layer, t="text", at=P(at), h=round(h * k, 4), text=str(txt)[:500], rot=round(e.dxf.get("rotation", 0), 3))
                elif t == "INSERT" and depth < 8:
                    walk(e.virtual_entities(), layer, depth + 1)
            except Exception:  # noqa: BLE001 — an odd entity: skip it, read the rest
                continue

    walk(doc.modelspace())
    if not out:
        raise ImportError_("the drawing has no lines, circles, arcs, polylines or texts")
    used = {e["layer"] for e in out}
    return {"source": name, "unit": "mm", "file_units": declared or "mm", "units_declared": bool(declared),
            "layers": [ly for ly in layers.values() if ly["name"] in used], "entities": out}


def outline_of(drawing: dict, flatten: float = 0.01):
    """The closed outlines of the drawing's shown layers -> ([[shell, *holes], ...], issues) — for a quick part."""
    from shapely.geometry import LineString
    shown = {ly["name"] for ly in drawing.get("layers") or [] if ly.get("visible", True)}
    lines = []
    for e in drawing.get("entities") or []:
        if e.get("layer") not in shown:
            continue
        t = e.get("t")
        if t == "line":
            lines.append(LineString([e["a"], e["b"]]))
        elif t in ("circle", "arc"):
            c, r = e["c"], e["r"]
            a0, a1 = (0.0, 360.0) if t == "circle" else (e["a0"], e["a1"] if e["a1"] > e["a0"] else e["a1"] + 360)
            n = max(12, int(math.ceil((a1 - a0) / 360 * 2 * math.pi * r / max(flatten * 20, 0.05))))
            n = min(n, 720)
            pts = [(c[0] + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), c[1] + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
            lines.append(LineString(pts))
        elif t == "poly" and len(e.get("pts") or []) >= 2:
            pts = e["pts"] + ([e["pts"][0]] if e.get("closed") else [])
            lines.append(LineString(pts))
    if not lines:
        raise ImportError_("no lines, circles or arcs on the shown layers")
    return outline_polys(lines)
