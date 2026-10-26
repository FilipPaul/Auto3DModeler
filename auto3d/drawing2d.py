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


PCB_EXT = (".zip", ".tgz", ".tar.gz", ".tar", ".gbr", ".ger", ".gtl", ".gbl", ".gto", ".gbo", ".gts", ".gbs", ".gtp", ".gbp",
           ".gko", ".gm1", ".gml", ".gm", ".g1", ".g2", ".g3", ".g4", ".cmp", ".sol", ".plc", ".pls", ".stc", ".sts", ".art",
           ".pho", ".drl", ".xln", ".drd", ".exc", ".ncd")


def read_drawing(data: bytes, name: str) -> dict:
    """A DXF (or DWG, converted), a Gerber set / ODB++ job (pcb.py) -> the drawing JSON above."""
    if name.lower().endswith(PCB_EXT):
        from .pcb import read_pcb
        d = read_pcb(data, name)
        if d is None:
            raise ImportError_("there are no Gerber, drill or ODB++ files in it")
        return {**d, "source": name}
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


def _layer_name(name, used):
    """A DXF layer name (no < > / \\ " : ; ? * | = `), unique."""
    import re
    base = re.sub(r'[<>/\\":;?*|=`]+', "_", name).strip() or "0"
    out, k = base, 2
    while out.lower() in used:
        out, k = f"{base}_{k}", k + 1
    used.add(out.lower())
    return out


def to_dxf(drawing: dict, fills: bool = True) -> bytes:
    """The drawing's shown layers -> a DXF (R2010, mm): its layers with their colours; a trace with a width -> a
    polyline of that width; pads and areas -> closed outlines (+ a solid hatch: fills); clear ones on "<layer>_CLEAR"."""
    import io
    import ezdxf
    from ezdxf import colors as dxfcolors
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    doc.header["$MEASUREMENT"] = 1
    msp = doc.modelspace()
    used, names = {"0"}, {}
    rgb = lambda h: tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) if isinstance(h, str) and len(h) == 7 else (255, 255, 255)  # noqa: E731
    for ly in drawing.get("layers") or []:
        if ly.get("visible") is False:
            continue
        for clear in (False, True):
            nm = _layer_name(ly["name"] + ("_CLEAR" if clear else ""), used)
            doc.layers.add(nm).rgb = rgb(ly.get("color")) if not clear else (60, 60, 60)
            names[(ly["name"], clear)] = nm
    n = 0
    for e in drawing.get("entities") or []:
        nm = names.get((e.get("layer"), bool(e.get("clear"))))
        if nm is None:
            continue
        at = {"layer": nm}
        if e.get("color"):
            at["true_color"] = dxfcolors.rgb2int(rgb(e["color"]))
        w = float(e.get("w") or 0)
        t = e.get("t")
        if t == "line":
            if w:
                msp.add_lwpolyline([e["a"], e["b"]], dxfattribs={**at, "const_width": w})
            else:
                msp.add_line(e["a"], e["b"], dxfattribs=at)
        elif t == "circle":
            c, r = e["c"], e["r"]
            if w and not e.get("fill"):  # a ring of that width: two half arcs
                msp.add_lwpolyline([(c[0] + r, c[1], 0, 0, 1), (c[0] - r, c[1], 0, 0, 1)], format="xyseb", close=True, dxfattribs={**at, "const_width": w})
            else:
                msp.add_circle(c, r, dxfattribs=at)
                if e.get("fill") and fills:
                    h = msp.add_hatch(dxfattribs=at)
                    h.set_solid_fill(rgb=rgb(e.get("color")) if e.get("color") else None)
                    h.paths.add_edge_path().add_arc(c, r, 0, 360)
        elif t == "arc":
            if w:
                sw = (e["a1"] - e["a0"]) % 360 or 360
                a0, a1 = math.radians(e["a0"]), math.radians(e["a0"] + sw)
                p0 = (e["c"][0] + e["r"] * math.cos(a0), e["c"][1] + e["r"] * math.sin(a0))
                p1 = (e["c"][0] + e["r"] * math.cos(a1), e["c"][1] + e["r"] * math.sin(a1))
                msp.add_lwpolyline([(p0[0], p0[1], 0, 0, math.tan(math.radians(sw) / 4)), (p1[0], p1[1], 0, 0, 0)], format="xyseb", dxfattribs={**at, "const_width": w})
            else:
                msp.add_arc(e["c"], e["r"], e["a0"], e["a1"], dxfattribs=at)
        elif t == "poly" and len(e.get("pts") or []) >= 2:
            closed = bool(e.get("closed"))
            msp.add_lwpolyline(e["pts"], close=closed, dxfattribs={**at, **({"const_width": w} if w else {})})
            if closed and e.get("fill") and fills and len(e["pts"]) >= 3:
                h = msp.add_hatch(dxfattribs=at)
                h.set_solid_fill()
                h.paths.add_polyline_path(e["pts"], is_closed=True)
        elif t == "text":
            msp.add_text(str(e.get("text", "")), height=float(e.get("h") or 2.5), rotation=float(e.get("rot") or 0), dxfattribs={**at, "insert": e["at"]})
        else:
            continue
        n += 1
    if not n:
        raise ImportError_("nothing to export on the shown layers")
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


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
