"""A drawing sheet (📄) as a DXF for drafting programs (AutoCAD, SolidWorks / Solid Edge drafting, DraftSight …).

The paper in true size (mm, 1:1: an A4 sheet is 297 × 210 in the DXF), the views where they are on the sheet, drawn
at the sheet's scale. Everything but the dimensions comes from the SVG the editor draws (the same one the PDF is made
of: web/js/sheet/sheet.js svg(true)) — lines, polylines, circles, rectangles, simple paths, texts — on a layer per
kind: visible, hidden (dashed as on the sheet), hatch, text (view names, title block, parts list) and frame (the border, the title
block's and parts list's cells, the section's cutting line). The dimensions are real DXF dimensions (layer dims),
from the editor's list (SheetEditor.dxfDims): they measure the paper and show the part's size (DIMLFAC = 1 / the
sheet's scale), so a drafter can move them and they stay right.
"""
from __future__ import annotations

import io
import math
import re
import xml.etree.ElementTree as ET

# layer -> (ACI colour, line weight in 1/100 mm, line type)
LAYERS = {"visible": (7, 50, "CONTINUOUS"), "hidden": (8, 25, "HIDDEN"), "dims": (5, 18, "CONTINUOUS"),
          "hatch": (8, 13, "CONTINUOUS"), "text": (7, 18, "CONTINUOUS"), "frame": (7, 35, "CONTINUOUS")}
WEIGHTS = (0, 5, 9, 13, 15, 18, 20, 25, 30, 35, 40, 50, 53, 60, 70, 80, 90, 100, 106, 120, 140, 158, 200, 211)
CAP = 0.7  # a DXF text's height is its capital letters'; an SVG font-size is the whole em


def _tag(el):
    return el.tag.rsplit("}", 1)[-1]


def _num(el, k, default=0.0):
    try:
        return float(el.get(k, default))
    except (TypeError, ValueError):
        return default


def _fmt(v):
    """A value as the editor writes it (sheet.js fmt: at most 2 decimals, no trailing zeros)."""
    s = f"{round(float(v), 2):.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _weight(sw):
    """An SVG stroke width (mm) -> the nearest DXF line weight."""
    return min(WEIGHTS, key=lambda w: abs(w - sw * 100))


def _kind(el, ctx):
    """Which layer an SVG element goes on: by the group it is in and how it is drawn."""
    t = _tag(el)
    if t == "text":
        return "text"
    if ctx == "view":
        if el.get("stroke-dasharray"):
            return "hidden"
        if t == "line" and _num(el, "stroke-width", 0.5) < 0.2:
            return "hatch"  # (a section's 45° lines: 0.18 mm)
        return "visible"
    if ctx == "balloons":
        return "dims"
    return "frame"


def _path_points(d):
    """A simple path (M / L / H / V / Z, absolute — the arrowheads the editor draws) -> (points, closed); None for
    curves."""
    if re.search(r"[AaCcQqSsTt]", d or ""):
        return None
    pts, closed, x, y = [], False, 0.0, 0.0
    for cmd, args in re.findall(r"([MLHVZmlhvz])([^MLHVZmlhvz]*)", d or ""):
        nums = [float(v) for v in re.findall(r"-?\d*\.?\d+(?:e-?\d+)?", args)]
        if cmd in "Zz":
            closed = True
            continue
        if cmd in "ML":
            for i in range(0, len(nums) - 1, 2):
                x, y = nums[i], nums[i + 1]
                pts.append((x, y))
        elif cmd == "H":
            for v in nums:
                x = v
                pts.append((x, y))
        elif cmd == "V":
            for v in nums:
                y = v
                pts.append((x, y))
    return (pts, closed) if len(pts) >= 2 else None


def to_dxf(svg: str, dims=(), scale: float = 1.0) -> bytes:
    """The sheet's SVG (mm, y down; as svg(true) draws it) + its dimensions [{kind: linear | dia | rad | ang, …} in
    paper mm, y down] + its scale (paper mm per part mm) -> a DXF (R2010, mm, the paper 1:1)."""
    import ezdxf
    from ezdxf.enums import TextEntityAlignment
    root = ET.fromstring(svg)
    vb = [float(v) for v in (root.get("viewBox") or "0 0 297 210").replace(",", " ").split()]
    ph = vb[3]
    Y = lambda p: (float(p[0]), ph - float(p[1]))  # noqa: E731 — paper (y down) -> DXF (y up)

    doc = ezdxf.new("R2010", setup=True)  # (setup: the standard line types and text styles)
    doc.header["$INSUNITS"] = 4  # mm
    doc.header["$MEASUREMENT"] = 1
    doc.header["$LUNITS"] = 2
    doc.header["$EXTMIN"], doc.header["$EXTMAX"] = (vb[0], 0, 0), (vb[0] + vb[2], ph, 0)
    doc.styles.get("Standard").dxf.font = "arial.ttf"  # (Ø, ×, ° and Czech letters)
    doc.linetypes.add("HIDDEN", pattern=[2.5, 1.5, -1.0], description="Hidden __ __ __")  # (the sheet's: 1.5 mm, 1 mm apart)
    for name, (colour, lw, lt) in LAYERS.items():
        doc.layers.add(name, color=colour, lineweight=lw, linetype=lt)
    ds = doc.dimstyles.new("A3D")
    ds.dxf.update({"dimtxt": 2.5, "dimasz": 2.2, "dimexo": 1.0, "dimexe": 1.5, "dimgap": 0.8, "dimdec": 2, "dimzin": 8,
                   "dimadec": 1, "dimazin": 2, "dimlfac": 1.0 / (scale or 1.0), "dimtad": 1, "dimtih": 0, "dimtoh": 0,
                   "dimclrd": 5, "dimclre": 5, "dimclrt": 5, "dimtxsty": "Standard", "dimdsep": ord(".")})
    msp = doc.modelspace()

    def walk(el, ctx):
        t = _tag(el)
        if t == "g":
            if el.get("data-dim") is not None:
                return  # (dimensions: from the list, as DXF dimensions)
            cls = el.get("class") or ""
            ctx = "view" if "sh-view" in cls else "balloons" if "sh-balloon" in cls else ctx
            for ch in el:
                walk(ch, ctx)
            return
        if el.get("fill-opacity") == "0" and t == "rect" and el.get("stroke") in (None, "none"):
            return  # (a place to click, not drawn)
        at = {"layer": _kind(el, ctx)}
        if el.get("stroke-width") and at["layer"] in ("frame", "visible"):
            at["lineweight"] = _weight(_num(el, "stroke-width"))
        if t == "line":
            msp.add_line(Y((_num(el, "x1"), _num(el, "y1"))), Y((_num(el, "x2"), _num(el, "y2"))), dxfattribs=at)
        elif t == "polyline":
            nums = [float(v) for v in re.findall(r"-?\d*\.?\d+(?:e-?\d+)?", el.get("points") or "")]
            pts = [Y(nums[i:i + 2]) for i in range(0, len(nums) - 1, 2)]
            if len(pts) >= 2:
                msp.add_lwpolyline(pts, dxfattribs=at)
        elif t == "rect":
            x, y, w, h = (_num(el, k) for k in ("x", "y", "width", "height"))
            if x <= vb[0] and y <= vb[1] and w >= vb[2] and h >= ph:
                return  # (the white paper)
            msp.add_lwpolyline([Y((x, y)), Y((x + w, y)), Y((x + w, y + h)), Y((x, y + h))], close=True, dxfattribs=at)
        elif t == "circle":
            msp.add_circle(Y((_num(el, "cx"), _num(el, "cy"))), _num(el, "r"), dxfattribs=at)
        elif t == "path":
            pp = _path_points(el.get("d"))
            if pp:
                msp.add_lwpolyline([Y(p) for p in pp[0]], close=pp[1], dxfattribs=at)
        elif t == "text":
            txt = "".join(el.itertext()).strip()
            if not txt:
                return
            fs = _num(el, "font-size", 3.5)
            rot = re.search(r"rotate\(\s*(-?[\d.]+)", el.get("transform") or "")
            e = msp.add_text(txt, height=fs * CAP, rotation=-float(rot.group(1)) if rot else 0, dxfattribs={**at, "style": "Standard"})
            align = {"middle": TextEntityAlignment.CENTER, "end": TextEntityAlignment.RIGHT}.get(el.get("text-anchor"), TextEntityAlignment.LEFT)
            e.set_placement(Y((_num(el, "x"), _num(el, "y"))), align=align)

    for ch in root:
        walk(ch, "frame")

    for dm in dims or []:
        _dimension(msp, dm, Y, scale or 1.0)
    out = io.StringIO()
    doc.write(out)
    return out.getvalue().encode("utf-8")


def _dimension(msp, dm, Y, scale=1.0):
    """One of the editor's dimensions (paper mm, y down) as a DXF dimension on layer dims. Its text: the measurement
    ("<>", the part's size through DIMLFAC) with the editor's prefix / suffix ("3× ", " H7"), or the editor's own text
    when it is not a plain number (a thread "M5"). A dimension of a view at its own scale (dm.scale, not the sheet's)
    gets its own DIMLFAC."""
    kind, text, value = dm.get("kind"), str(dm.get("text") or ""), dm.get("value")
    num = _fmt(value) if value is not None else None
    if num is not None and kind == "linear" and num in text:
        text = text.replace(num, "<>", 1)
    at = {"layer": "dims"}
    try:
        own = float(dm.get("scale") or scale)
        lfac = {"dimlfac": 1.0 / own} if own > 0 and abs(own - scale) > 1e-12 else {}
    except (TypeError, ValueError):
        lfac = {}
    try:
        if kind == "linear":
            a, b, h = Y(dm["a"]), Y(dm["b"]), dm.get("dir") == "h"
            base = (a[0], Y((0, dm["at"]))[1]) if h else (float(dm["at"]), a[1])
            msp.add_linear_dim(base=base, p1=a, p2=b, angle=0 if h else 90, text=text, dimstyle="A3D", override=lfac or None, dxfattribs=at).render()
        elif kind in ("dia", "rad"):
            c, r, u = Y(dm["c"]), float(dm["r"]), dm.get("u") or [1, 0]
            deg = math.degrees(math.atan2(-float(u[1]), float(u[0])))  # (paper y down -> DXF y up)
            make = msp.add_diameter_dim if kind == "dia" else msp.add_radius_dim
            loc = Y(dm["end"]) if dm.get("end") else None
            make(center=c, radius=r, angle=deg, location=loc, text=text, dimstyle="A3D", override={"dimtmove": 0, **lfac}, dxfattribs=at).render()
        elif kind == "ang":
            x, u1, u2 = Y(dm["X"]), dm["u1"], dm["u2"]
            a1, a2 = (math.degrees(math.atan2(-float(u[1]), float(u[0]))) for u in (u1, u2))
            if (a2 - a1) % 360 > 180:  # (counter-clockwise from the first: the smaller side)
                a1, a2 = a2, a1
            msp.add_angular_dim_cra(center=x, radius=float(dm.get("r") or 15), start_angle=a1, end_angle=a2, distance=0, text=text,
                                    dimstyle="A3D", dxfattribs=at).render()
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        pass  # (a dimension that lost its points: left out, as on the sheet)
