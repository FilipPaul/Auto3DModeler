"""A drawing sheet of a 3D model part: the views (front, top, right, iso) with their exact lines, circles and arcs, the
points a dimension can hang on (each with a key from the part's face names, so a dimension stays on its edge or hole
when the part changes), the automatic dimensions for a preset — light (the overall sizes and the holes), medium (+ where
the holes are, the radii, the heights), full (+ every level) — and where the views go on the paper.

Holes alike are dimensioned once: "200× Ø5", the first one's position and the pitch of the row / grid.

The browser draws and edits the sheet (web/js/sheet/sheet.js); its SVG becomes the PDF (sheet_pdf).
Dimension JSON (in view coordinates, mm of the part):
  {id, view, kind: "linear", a: "<point key>", b: "<point key>", dir: "h" | "v", side: "b" | "t" | "l" | "r", off: paper mm,
   pre: "4× " (text before the value)}
  {id, view, kind: "dia" | "rad", a: "<circle key>", count, ang: degrees, len: paper mm, post: " H7"}
"""
from __future__ import annotations

import hashlib
import math

import numpy as np
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Cylinder, GeomAbs_Line
from OCP.TopoDS import TopoDS

from . import kernel as K
from .drawing import SCALES, VIEWS, _extent, _iso, _project

PRESETS = ("light", "medium", "full")
PAPERS = {"A4": (297, 210), "A3": (420, 297)}
TOL = 1e-3


def _r(v, n=4):
    return round(float(v), n)


def _key(*names):
    return "+".join(sorted(set(names)))


def geometry(body):
    """The views of the part -> {bbox, views: {name: {look, right, up, visible, hidden, lines, circles, points, box}},
    iso}. lines: [{a, b, key}], circles: [{key, c, r, full, p0, p1, pm, face}], points: {key: [x, y]}."""
    shape = body.shape
    fm, em, adj = K._adjacency(shape)
    names = K._face_names(body, fm)
    cyl = {i for i in range(fm.Extent()) if BRepAdaptor_Surface(TopoDS.Face(fm.FindKey(i + 1))).GetType() == GeomAbs_Cylinder}
    name = lambda fi: (names.get(fi) or [f"#{fi}"])[-1]  # noqa: E731
    edges = []  # (kind, data, key, cylinder face)
    for ei in range(1, em.Extent() + 1):
        e = TopoDS.Edge(em.FindKey(ei))
        try:
            c = BRepAdaptor_Curve(e)
        except Exception:  # noqa: BLE001 — a degenerate edge
            continue
        fs = sorted(adj.get(ei, ()))
        key = _key(*(name(f) for f in fs))
        t0, t1 = c.FirstParameter(), c.LastParameter()
        P = lambda t: np.array([c.Value(t).X(), c.Value(t).Y(), c.Value(t).Z()])  # noqa: E731
        if c.GetType() == GeomAbs_Line:
            edges.append(("line", (P(t0), P(t1)), key, None))
        elif c.GetType() == GeomAbs_Circle:
            ci = c.Circle()
            ax, lo = ci.Axis().Direction(), ci.Location()
            face = next((name(f) for f in fs if f in cyl), None)
            edges.append(("circle", (np.array([lo.X(), lo.Y(), lo.Z()]), np.array([ax.X(), ax.Y(), ax.Z()]), ci.Radius(),
                                     abs(t1 - t0 - 2 * math.pi) < 1e-6, P(t0), P(t1), P((t0 + t1) / 2)), key, face))
    bb = K.bbox(shape)
    out = {"bbox": [_r(v) for v in bb], "views": {}, "iso": [[[_r(x, 3), _r(y, 3)] for x, y in pl] for pl in _iso(shape)]}
    for vname, (look, right, up) in VIEWS.items():
        L, R, U = (np.asarray(v, float) for v in (look, right, up))
        pr = lambda p: [_r(p @ R), _r(p @ U)]  # noqa: E731
        vis, hid = _project(shape, look, right, up)
        lines, seen, circles, ckeys, points = [], {}, [], {}, {}
        for kind, d, key, face in edges:
            if kind == "line":
                a, b = pr(d[0]), pr(d[1])
                if math.dist(a, b) < TOL:
                    continue
                sig = tuple(sorted((tuple(round(v, 2) for v in a), tuple(round(v, 2) for v in b))))
                depth = -float((d[0] + d[1]) @ L) / 2  # nearer the viewer: bigger
                if sig in seen and seen[sig][0] >= depth:
                    continue
                seen[sig] = (depth, len(lines))
                lines.append({"a": a, "b": b, "key": key})
            else:
                c0, ax, r, full, p0, p1, pm = d
                if abs(float(ax @ L)) < 0.999:  # seen from the side: lines in the projection, no circle
                    continue
                c = pr(c0)
                ck = face or key
                sig = (round(c[0], 2), round(c[1], 2), round(r, 3))
                if sig in ckeys:  # a hole's top and bottom circles: one
                    prev = circles[ckeys[sig]]
                    if full and not prev["full"]:
                        prev.update(full=True)
                    continue
                ckeys[sig] = len(circles)
                circles.append({"key": ck, "c": c, "r": _r(r), "full": bool(full), "p0": pr(p0), "p1": pr(p1), "pm": pr(pm)})
        # one line per projected segment (the one nearest the viewer)
        lines = [lines[i] for _, i in sorted(seen.values(), key=lambda q: q[1])]
        keys = {}
        for ln in lines:  # the ends of lines (a key used twice gets a number)
            k = ln["key"]
            keys[k] = keys.get(k, 0) + 1
            if keys[k] > 1:
                ln["key"] = k = f"{k}~{keys[k]}"
            points[f"{k}#0"], points[f"{k}#1"] = ln["a"], ln["b"]
        for ci in circles:
            k = ci["key"]
            keys[k] = keys.get(k, 0) + 1
            if keys[k] > 1:
                ci["key"] = k = f"{k}~{keys[k]}"
            points[f"{k}#c"], points[f"{k}#m"] = ci["c"], ci["pm"]
        x0, y0, x1, y1 = _extent(vis + hid)
        box = [_r(x0), _r(y0), _r(x1), _r(y1)]
        points.update({"box#x0": [box[0], box[1]], "box#x1": [box[2], box[1]], "box#y0": [box[2], box[1]], "box#y1": [box[2], box[3]]})
        out["views"][vname] = {"look": list(look), "right": list(right), "up": list(up), "box": box, "lines": lines, "circles": circles, "points": points,
                               "visible": [[[_r(x, 3), _r(y, 3)] for x, y in pl] for pl in vis], "hidden": [[[_r(x, 3), _r(y, 3)] for x, y in pl] for pl in hid]}
    return out


def layout(geo, paper=None):
    """Where the views go: {paper, size [w, h] mm, scale [a, b], views: {name: [x, y] (the view box's centre on the paper)},
    iso: [x, y, k]} — front top-left, top below it, right beside the front, iso bottom-right (first-angle as in drawing.py)."""
    bb = geo["bbox"]
    size = (bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2])
    need_w, need_h = max(size[0] + size[1], 1), max(size[2] + size[1], 1)
    for pname in ([paper] if paper in PAPERS else ["A4", "A3"]):
        pw, ph = PAPERS[pname]
        title, margin = 38, 10
        fit = [(a, b) for a, b in SCALES if a / b * need_w <= (pw - 2 * margin) * 0.62 and a / b * need_h <= (ph - 2 * margin - title) * 0.62]
        if fit or pname == "A3" or paper:
            break
    scale = fit[0] if fit else SCALES[-1]
    cw, ch = (pw - 2 * margin) / 2, (ph - 2 * margin - title) / 2
    return {"paper": pname, "size": [pw, ph], "scale": list(scale), "margin": margin, "title": title,
            "views": {"Front": [margin + cw / 2, margin + ch / 2], "Right": [margin + cw * 1.5, margin + ch / 2], "Top": [margin + cw / 2, margin + ch * 1.5]},
            "iso": [margin + cw * 1.5, margin + ch * 1.5, 0.55 * min(cw, ch)]}


def _id(*parts):
    return "a" + hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:10]


def _grid(cs):
    """Circles alike in a regular row / grid -> (nx, ny, px, py) or None."""
    xs = sorted({round(c["c"][0], 2) for c in cs})
    ys = sorted({round(c["c"][1], 2) for c in cs})
    if len(xs) * len(ys) != len(cs):
        return None
    step = lambda v: (len(v) < 2 or max(abs((v[i + 1] - v[i]) - (v[1] - v[0])) for i in range(len(v) - 1)) < 0.02)  # noqa: E731
    if not (step(xs) and step(ys)):
        return None
    return len(xs), len(ys), (xs[1] - xs[0]) if len(xs) > 1 else 0, (ys[1] - ys[0]) if len(ys) > 1 else 0


def auto_dims(geo, preset="medium", fits=None, per_view=None):
    """The automatic dimensions of a preset (see the module's docstring). fits: {diameter: "H7"} (holes with a fit).
    per_view: {view: preset} — a view's own preset instead of the sheet's."""
    preset = preset if preset in PRESETS else "medium"
    per_view = {k: v for k, v in (per_view or {}).items() if v in PRESETS}
    pv = lambda view: per_view.get(view, preset)  # noqa: E731
    fits = {round(float(d), 3): f for d, f in (fits or {}).items() if f}
    dims, stack, measured = [], {}, set()

    def lin(view, a, b, d, side, pre="", tag=""):
        # one dimension per distance: the same direction between the same places only once (concentric circles,
        # holes in a row share their places)
        pts = geo["views"][view]["points"]
        if a in pts and b in pts:
            k = 0 if d == "h" else 1
            sig = (view, d, *sorted((round(pts[a][k], 2), round(pts[b][k], 2))))
            if sig in measured or sig[2] == sig[3]:
                return
            measured.add(sig)
        n = stack.get((view, side), 0)
        stack[(view, side)] = n + 1
        dims.append({"id": _id(view, a, b, d, tag), "view": view, "kind": "linear", "a": a, "b": b, "dir": d, "side": side,
                     "off": 8 + 7 * n, **({"pre": pre} if pre else {})})

    v = geo["views"]
    # the overall sizes: width and height in the front, depth in the top
    lin("Front", "box#x0", "box#x1", "h", "b")
    lin("Front", "box#y0", "box#y1", "v", "r")
    lin("Top", "box#y0", "box#y1", "v", "r")
    done_r = set()
    for vname in ("Top", "Front", "Right"):
        view = v[vname]
        full = [c for c in view["circles"] if c["full"]]
        arcs = [c for c in view["circles"] if not c["full"]]
        groups = {}
        for c in full:
            groups.setdefault(round(2 * c["r"], 3), []).append(c)
        # concentric circles: their leaders spread round
        centres = {}
        for d, cs in sorted(groups.items(), key=lambda q: -q[0]):
            if d in done_r:  # already given in another view
                continue
            done_r.add(d)
            first = min(cs, key=lambda c: (round(c["c"][1], 2), round(c["c"][0], 2)))
            at = (round(first["c"][0], 1), round(first["c"][1], 1))
            k = centres[at] = centres.get(at, -1) + 1
            dims.append({"id": _id(vname, "dia", d), "view": vname, "kind": "dia", "a": first["key"], "count": len(cs),
                         "ang": [45, 135, 315, 225, 20, 160, 340, 200][k % 8], "len": 6 + 5 * (k // 4), **({"post": f" {fits[d]}"} if d in fits else {})})
            if pv(vname) == "light":
                continue
            # where they are: the first from the left / bottom of the view, then the pitch of a row / grid
            g = _grid(cs) if len(cs) > 1 else None
            lin(vname, "box#x0", f"{first['key']}#c", "h", "t" if vname == "Top" else "b", tag=f"x{d}")
            lin(vname, "box#y0", f"{first['key']}#c", "v", "l", tag=f"y{d}")
            if g:
                nx, ny, px, py = g
                row = sorted(cs, key=lambda c: (round(c["c"][1], 2), round(c["c"][0], 2)))
                if nx > 1:
                    lin(vname, f"{row[0]['key']}#c", f"{row[1]['key']}#c", "h", "t" if vname == "Top" else "b", pre=f"{nx - 1}× " if nx > 2 else "", tag=f"px{d}")
                if ny > 1:
                    up = next(c for c in row if round(c["c"][1], 2) > round(row[0]["c"][1], 2))
                    lin(vname, f"{row[0]['key']}#c", f"{up['key']}#c", "v", "l", pre=f"{ny - 1}× " if ny > 2 else "", tag=f"py{d}")
            elif len(cs) > 1:
                limit = 6 if pv(vname) == "medium" else 30
                for c in sorted(cs, key=lambda c: (c["c"][1], c["c"][0]))[1:limit]:
                    lin(vname, "box#x0", f"{c['key']}#c", "h", "t" if vname == "Top" else "b", tag=f"x{d}{c['key']}")
                    lin(vname, "box#y0", f"{c['key']}#c", "v", "l", tag=f"y{d}{c['key']}")
        # roundings: one radius per size (the biggest first)
        rg = {}
        for c in arcs:
            rg.setdefault(round(c["r"], 3), []).append(c)
        for r, cs in sorted(rg.items(), key=lambda q: -q[0])[: (1 if pv(vname) == "light" else 5 if pv(vname) == "medium" else 20)]:
            if ("r", r) in done_r:
                continue
            done_r.add(("r", r))
            dims.append({"id": _id(vname, "rad", r), "view": vname, "kind": "rad", "a": cs[0]["key"], "count": len(cs), "ang": 0, "len": 6})
    if pv("Front") != "light":
        # heights in the front: the levels of its horizontal edges, from the bottom
        f = v["Front"]
        y0, y1 = f["box"][1], f["box"][3]
        levels = {}
        for ln in f["lines"]:  # (not where a rounding begins)
            if abs(ln["a"][1] - ln["b"][1]) < TOL and TOL < ln["a"][1] - y0 < (y1 - y0) - TOL and ":round:" not in ln["key"]:
                levels.setdefault(round(ln["a"][1], 2), ln["key"])
        for y, key in sorted(levels.items())[: (3 if pv("Front") == "medium" else 10)]:
            lin("Front", "box#y0", f"{key}#0", "v", "l", tag=f"lv{y}")
    if pv("Top") == "full":
        # widths in the top: the vertical edges' places, from the left
        t = v["Top"]
        x0, x1 = t["box"][0], t["box"][2]
        cols = {}
        for ln in t["lines"]:
            if abs(ln["a"][0] - ln["b"][0]) < TOL and TOL < ln["a"][0] - x0 < (x1 - x0) - TOL and ":round:" not in ln["key"]:
                cols.setdefault(round(ln["a"][0], 2), ln["key"])
        for x, key in sorted(cols.items())[:10]:
            lin("Top", "box#x0", f"{key}#0", "h", "b", tag=f"col{x}")
    return dims


def build(body, preset="medium", fits=None, paper=None, per_view=None):
    """Everything a new / changed sheet needs: {geometry, layout, dims (automatic)}."""
    geo = geometry(body)
    return {"geometry": geo, "layout": layout(geo, paper), "dims": auto_dims(geo, preset, fits, per_view)}


ISO_VIEW = ((-1, 1, -1), (1 / math.sqrt(2), 1 / math.sqrt(2), 0), (-1 / math.sqrt(6), 1 / math.sqrt(6), 2 / math.sqrt(6)))  # as _iso projects


class _Placed:
    """An assembly's placed parts as one body for geometry(): its shape (a compound), no face names."""
    def __init__(self, shape):
        self.shape, self.names = shape, {}


def build_assembly(placed, paper=None):
    """An assembly's sheet: placed [(id, shape placed)] -> {geometry, layout, dims (its overall sizes), marks: {id:
    {Front, Top, Right, Iso: [x, y]} (the middle of each placed part, for its balloon)}}."""
    shapes = [s for _, s in placed]
    if not shapes:
        raise K.KernelError("The assembly has no solids to draw.")
    geo = geometry(_Placed(K.compound(shapes)))
    dims = [d for d in auto_dims(geo, "light") if d["kind"] == "linear" and d["a"].startswith("box#")]
    marks = {}
    for key, s in placed:
        bb = K.bbox(s)
        if not bb:
            continue
        c = np.array([(bb[0] + bb[3]) / 2, (bb[1] + bb[4]) / 2, (bb[2] + bb[5]) / 2])
        m = {v: [_r(c @ np.asarray(R, float)), _r(c @ np.asarray(U, float))] for v, (_, R, U) in VIEWS.items()}
        m["Iso"] = [_r(c @ np.asarray(ISO_VIEW[1], float)), _r(c @ np.asarray(ISO_VIEW[2], float))]
        marks[key] = m
    return {"geometry": geo, "layout": layout(geo, paper), "dims": dims, "marks": marks}


def value(geo, dim):
    """A dimension's value (mm) from the geometry, or None (its points are gone)."""
    view = geo["views"].get(dim.get("view"))
    if not view:
        return None
    if dim["kind"] in ("dia", "rad"):
        c = next((c for c in view["circles"] if c["key"] == dim["a"]), None)
        return None if c is None else (2 * c["r"] if dim["kind"] == "dia" else c["r"])
    a, b = view["points"].get(dim["a"]), view["points"].get(dim["b"])
    if a is None or b is None:
        return None
    return abs(b[0] - a[0]) if dim.get("dir") == "h" else abs(b[1] - a[1]) if dim.get("dir") == "v" else math.dist(a, b)


def pdf(svg) -> bytes:
    """The sheet as the browser drew it (SVG, mm) -> a PDF; several SVGs (a drawing set) -> one PDF, a page each."""
    import fitz
    out = fitz.open()
    for one in [svg] if isinstance(svg, str) else list(svg):
        out.insert_pdf(fitz.open("pdf", fitz.open(stream=str(one).encode("utf-8"), filetype="svg").convert_to_pdf()))
    return out.tobytes()
