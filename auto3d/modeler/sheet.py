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
from collections import OrderedDict

import numpy as np
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Cylinder, GeomAbs_Line
from OCP.TopoDS import TopoDS

from . import kernel as K
from .drawing import SCALES, VIEWS, _extent, _iso, _project

PRESETS = ("light", "medium", "full")
PAPERS = {"A4": (297, 210), "A3": (420, 297)}
TOL = 1e-3
FINE, SMALL = 0.05, 0.25  # paper mm: a big part's lines kept to FINE; its solids, edges and holes under SMALL left out
CACHE_SIZE = 8
_cache: OrderedDict = OrderedDict()  # (the part's hash, what) -> its views, projected once (only in the worker process)


def _cached(key, make):
    """make() once per key (None: not kept) — a sheet built again with another preset / paper, or its section turned on,
    does not project the part again."""
    if key is None:
        return make()
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]
    out = _cache[key] = make()
    while len(_cache) > CACHE_SIZE:
        _cache.popitem(last=False)
    return out


def _r(v, n=4):
    return round(float(v), n)


def _key(*names):
    return "+".join(sorted(set(names)))


def _deco(key):
    """An edge no one dimensions: where a rounding begins (its R gives it), a teardrop hole's point (its Ø gives it)."""
    return ":round:" in key or ":tear:" in key or "_tear:" in key


def _scale(bb):
    """The biggest scale (paper mm per mm) the layout may give a part of this box (A4 or A3)."""
    return max(a / b for a, b in (layout({"bbox": bb}, p)["scale"] for p in PAPERS))


def _iso_view(shape, heavy):
    """The iso view's lines; a big model's as its cell shows it (drawn smaller than the views: more left out)."""
    fine = None
    if heavy:
        bb = K.bbox(shape)
        s = max(layout({"bbox": bb}, p)["iso"][2] for p in PAPERS) / max(math.dist(bb[:3], bb[3:]), 1e-6)
        shape, fine = _small_left_out(shape, SMALL / s)[0], FINE / s
    return [[[_r(x, 3), _r(y, 3)] for x, y in pl] for pl in _iso(shape, fine)]


def _small_left_out(shape, small):
    """A big imported model without its solids smaller than `small` (an 0402 resistor on a board drawn 1:5: a dot) ->
    (the shape drawn, how many were left out). A third of the time each view takes."""
    solids = K._solid_boxes(shape)
    kept = [x for x, b in solids if max(b[3] - b[0], b[4] - b[1], b[5] - b[2]) >= small]
    if not kept or len(kept) == len(solids):
        return shape, 0
    return K.compound(kept), len(solids) - len(kept)


def geometry(body, views=None, iso=True, scale=None):
    """The views of the part -> {bbox, views: {name: {look, right, up, visible, hidden, lines, circles, points, box}},
    iso, simple?}. lines: [{a, b, key}], circles: [{key, c, r, full, p0, p1, pm, face}], points: {key: [x, y]}.
    views: only these (names of VIEWS); iso False: no iso view (each projection is a hidden-line pass — seconds on a
    big part). A big imported model (over HEAVY_FACES, or given its `scale`) is drawn as the paper shows it at that scale
    (else the layout's): its solids, edges and holes smaller than SMALL paper mm left out, its lines simplified to FINE
    (and no hidden lines, kernel.project_edges) — simple: {left_out (solids), under (mm)}."""
    shape, bb = body.shape, K.bbox(body.shape)
    fine = small = 0
    simple = None
    if scale or K.face_count(shape) > K.HEAVY_FACES:
        s = scale or _scale(bb)
        fine, small = FINE / s, SMALL / s
        shape, n = _small_left_out(shape, small)
        simple = {"left_out": n, "under": _r(small, 2)}
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
            if len(fs) == 1 and fs[0] in cyl:  # a round face's seam: not an edge anyone dimensions
                continue
            a, b = P(t0), P(t1)
            if small and np.linalg.norm(b - a) < small:
                continue
            edges.append(("line", (a, b), key, None))
        elif c.GetType() == GeomAbs_Circle:
            ci = c.Circle()
            if small and 2 * ci.Radius() < small:
                continue
            ax, lo = ci.Axis().Direction(), ci.Location()
            face = next((name(f) for f in fs if f in cyl), None)
            # a teardrop hole's round part (270°, its top a point) is still a hole: dimensioned Ø d
            tear = face is not None and t1 - t0 > 1.5 * math.pi - 1e-6 and (":hole:" in face or ":cbore:" in face)
            edges.append(("circle", (np.array([lo.X(), lo.Y(), lo.Z()]), np.array([ax.X(), ax.Y(), ax.Z()]), ci.Radius(),
                                     abs(t1 - t0 - 2 * math.pi) < 1e-6 or tear, P(t0), P(t1), P((t0 + t1) / 2)), key, face))
    out = {"bbox": [_r(v) for v in bb], "views": {}, "iso": _iso_view(body.shape, bool(simple)) if iso else []}
    if simple:
        out["simple"] = simple
    for vname, (look, right, up) in VIEWS.items():
        if views is not None and vname not in views:
            continue
        L, R, U = (np.asarray(v, float) for v in (look, right, up))
        pr = lambda p: [_r(p @ R), _r(p @ U)]  # noqa: E731
        vis, hid = _project(shape, look, right, up, fine)
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


def auto_dims(geo, preset="medium", fits=None, per_view=None, threads=None):
    """The automatic dimensions of a preset (see the module's docstring). fits: {diameter: "H7"} (holes with a fit),
    threads: {tap drill Ø: "M5"} (threaded holes: labelled M5).
    per_view: {view: preset} — a view's own preset instead of the sheet's; "all": every size of that view, the ones
    given in another view too (its outer sizes, its holes, its edges' places) — as full."""
    preset = preset if preset in PRESETS else "medium"
    per_view = {k: v for k, v in (per_view or {}).items() if v in PRESETS + ("all",)}
    every = {k for k, v in per_view.items() if v == "all"}
    pv = lambda view: "full" if view in every else per_view.get(view, preset)  # noqa: E731
    fits = {round(float(d), 3): f for d, f in (fits or {}).items() if f}
    threads = {round(float(d), 3): m for d, m in (threads or {}).items() if m}
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
    for vname in sorted(every & set(v)):  # (a view with all its sizes: its own outer sizes too)
        lin(vname, "box#x0", "box#x1", "h", "b")
        lin(vname, "box#y0", "box#y1", "v", "r")
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
            if d in done_r and vname not in every:  # already given in another view
                continue
            done_r.add(d)
            first = min(cs, key=lambda c: (round(c["c"][1], 2), round(c["c"][0], 2)))
            at = (round(first["c"][0], 1), round(first["c"][1], 1))
            k = centres[at] = centres.get(at, -1) + 1
            dims.append({"id": _id(vname, "dia", d), "view": vname, "kind": "dia", "a": first["key"], "count": len(cs),
                         "ang": [45, 135, 315, 225, 20, 160, 340, 200][k % 8], "len": 6 + 5 * (k // 4), **({"post": f" {fits[d]}"} if d in fits else {}), **({"thread": threads[d]} if d in threads else {})})
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
            if ("r", r) in done_r and vname not in every:
                continue
            done_r.add(("r", r))
            dims.append({"id": _id(vname, "rad", r), "view": vname, "kind": "rad", "a": cs[0]["key"], "count": len(cs), "ang": 0, "len": 6})
    if pv("Front") != "light":
        # heights in the front: the levels of its horizontal edges, from the bottom
        f = v["Front"]
        y0, y1 = f["box"][1], f["box"][3]
        levels = {}
        for ln in f["lines"]:  # (not where a rounding begins, nor a teardrop's point)
            if abs(ln["a"][1] - ln["b"][1]) < TOL and TOL < ln["a"][1] - y0 < (y1 - y0) - TOL and not _deco(ln["key"]):
                levels.setdefault(round(ln["a"][1], 2), ln["key"])
        for y, key in sorted(levels.items())[: (3 if pv("Front") == "medium" else 10)]:
            lin("Front", "box#y0", f"{key}#0", "v", "l", tag=f"lv{y}")
    if pv("Top") == "full":
        # widths in the top: the vertical edges' places, from the left
        t = v["Top"]
        x0, x1 = t["box"][0], t["box"][2]
        cols = {}
        for ln in t["lines"]:
            if abs(ln["a"][0] - ln["b"][0]) < TOL and TOL < ln["a"][0] - x0 < (x1 - x0) - TOL and not _deco(ln["key"]):
                cols.setdefault(round(ln["a"][0], 2), ln["key"])
        for x, key in sorted(cols.items())[:10]:
            lin("Top", "box#x0", f"{key}#0", "h", "b", tag=f"col{x}")
    for vname in sorted(every & set(v) - {"Front", "Top"}):  # its edges' places too (the Front / Top have theirs)
        w = v[vname]
        x0, y0, x1, y1 = w["box"]
        rows, cols = {}, {}
        for ln in w["lines"]:
            if _deco(ln["key"]):
                continue
            if abs(ln["a"][1] - ln["b"][1]) < TOL and TOL < ln["a"][1] - y0 < (y1 - y0) - TOL:
                rows.setdefault(round(ln["a"][1], 2), ln["key"])
            if abs(ln["a"][0] - ln["b"][0]) < TOL and TOL < ln["a"][0] - x0 < (x1 - x0) - TOL:
                cols.setdefault(round(ln["a"][0], 2), ln["key"])
        for y, key in sorted(rows.items())[:10]:
            lin(vname, "box#y0", f"{key}#0", "v", "l", tag=f"lv{y}")
        for x, key in sorted(cols.items())[:10]:
            lin(vname, "box#x0", f"{key}#0", "h", "b", tag=f"col{x}")
    return dims


def build(body, preset="medium", fits=None, paper=None, per_view=None, threads=None, section=False, key=None):
    """Everything a new / changed sheet needs: {geometry, layout, dims (automatic)}. section: also the section A–A
    (geometry.views.Section). key: the part's hash — its views are kept (_cached), only the dimensions made again."""
    geo = _cached((key, "views"), lambda: geometry(body))
    geo = {**geo, "views": dict(geo["views"])}
    if section:
        geo["views"]["Section"] = _cached((key, "section"), lambda: section_view(body))
    return {"geometry": geo, "layout": layout(geo, paper), "dims": auto_dims(geo, preset, fits, per_view, threads)}


def _wire_points(w, n=24):
    """A wire's points in order (its lines by their ends, its curves n points each)."""
    from OCP.BRepTools import BRepTools_WireExplorer
    from OCP.TopAbs import TopAbs_REVERSED
    out, ex = [], BRepTools_WireExplorer(w)
    while ex.More():
        e = ex.Current()
        c = BRepAdaptor_Curve(e)
        t0, t1 = c.FirstParameter(), c.LastParameter()
        k = 1 if c.GetType() == GeomAbs_Line else n
        ts = [t0 + (t1 - t0) * i / k for i in range(k + 1)]
        if e.Orientation() == TopAbs_REVERSED:
            ts.reverse()
        pts = [np.array([c.Value(t).X(), c.Value(t).Y(), c.Value(t).Z()]) for t in ts]
        out.extend(pts if not out else pts[1:])
        ex.Next()
    return out


def section_view(body):
    """Section A–A: the part cut across x at its middle, the far half seen as the Right view sees it (looking along
    -x) -> that view's geometry (lines, circles, points to dimension) with hatch (the cut faces' outlines [[x, y]…])
    and cut (where the cut is, on the Front view: two points)."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_FACE, TopAbs_WIRE
    from OCP.TopExp import TopExp_Explorer
    from OCP.GeomAbs import GeomAbs_Plane
    bb = K.bbox(body.shape)
    xm = (bb[0] + bb[3]) / 2
    keep = BRepPrimAPI_MakeBox(gp_Pnt(bb[0] - 1, bb[1] - 1, bb[2] - 1), gp_Pnt(xm, bb[4] + 1, bb[5] + 1)).Shape()
    heavy = K.face_count(body.shape) > K.HEAVY_FACES
    scale = _scale(bb) if heavy else None
    solids = K._solid_boxes(_small_left_out(body.shape, SMALL / scale)[0]) if heavy else []
    if len(solids) > 1:  # a big imported model (a board: a thousand solids): only the solids across the cut are cut
        from OCP.BRepMesh import BRepMesh_IncrementalMesh
        kept, size = [], max(bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2], 1e-6)
        for s, b in solids:
            if b[0] >= xm:
                continue
            mk = BRepAlgoAPI_Common(s, keep) if b[3] > xm else None
            if mk is not None and not mk.IsDone():
                raise K.KernelError("The part could not be cut for its section.")
            if mk is not None:  # (its new faces meshed as the rest: the view is drawn from the mesh)
                BRepMesh_IncrementalMesh(mk.Shape(), max(size * 0.004, 0.002), False, 0.6, True)
            kept.append(mk.Shape() if mk is not None else s)
        half = K.compound(kept)
    else:
        mk = BRepAlgoAPI_Common(body.shape, keep)
        if not mk.IsDone():
            raise K.KernelError("The part could not be cut for its section.")
        half = mk.Shape()
    view = geometry(_Placed(half), ("Right",), iso=False, scale=scale)["views"]["Right"]
    _, R, U = VIEWS["Right"]
    R, U = np.asarray(R, float), np.asarray(U, float)
    hatch, fx = [], TopExp_Explorer(half, TopAbs_FACE)
    while fx.More():
        f = TopoDS.Face(fx.Current())
        s = BRepAdaptor_Surface(f)
        if s.GetType() == GeomAbs_Plane and abs(abs(s.Plane().Axis().Direction().X()) - 1) < 1e-9 and abs(s.Plane().Location().X() - xm) < 1e-6:
            wx = TopExp_Explorer(f, TopAbs_WIRE)
            while wx.More():
                hatch.append([[_r(float(p @ R), 3), _r(float(p @ U), 3)] for p in _wire_points(TopoDS.Wire(wx.Current()))])
                wx.Next()
        fx.Next()
    _, RF, UF = VIEWS["Front"]
    a, b = np.array([xm, bb[1], bb[2]]), np.array([xm, bb[1], bb[5]])
    view["hatch"] = hatch
    view["cut"] = [[_r(float(a @ np.asarray(RF, float))), _r(float(a @ np.asarray(UF, float)))], [_r(float(b @ np.asarray(RF, float))), _r(float(b @ np.asarray(UF, float)))]]
    return view


ISO_VIEW = ((-1, 1, -1), (1 / math.sqrt(2), 1 / math.sqrt(2), 0), (-1 / math.sqrt(6), 1 / math.sqrt(6), 2 / math.sqrt(6)))  # as _iso projects


class _Placed:
    """An assembly's placed parts as one body for geometry(): its shape (a compound), no face names."""
    def __init__(self, shape):
        self.shape, self.names = shape, {}


def build_assembly(placed, paper=None, iso_placed=None, key=None):
    """An assembly's sheet: placed [(id, shape placed)] -> {geometry, layout, dims (its overall sizes), marks: {id:
    {Front, Top, Right, Iso: [x, y]} (the middle of each placed part, for its balloon)}}. iso_placed: the same parts
    pulled apart — the iso view drawn exploded (the other views as assembled). key: the placed parts' hash (kept, see
    _cached)."""
    out = _cached((key, "assembly"), lambda: _assembly(placed, iso_placed))
    return {**out, "layout": layout(out["geometry"], paper)}


def _assembly(placed, iso_placed):
    shapes = [s for _, s in placed]
    if not shapes:
        raise K.KernelError("The assembly has no solids to draw.")
    geo = geometry(_Placed(K.compound(shapes)), iso=not iso_placed)  # (exploded: its own iso below)
    if iso_placed:
        geo["iso"] = _iso_view(K.compound([s for _, s in iso_placed]), "simple" in geo)
    iso_at = dict(iso_placed or [])
    dims = [d for d in auto_dims(geo, "light") if d["kind"] == "linear" and d["a"].startswith("box#")]
    marks = {}
    for key, s in placed:
        bb = K.bbox(s)
        if not bb:
            continue
        c = np.array([(bb[0] + bb[3]) / 2, (bb[1] + bb[4]) / 2, (bb[2] + bb[5]) / 2])
        m = {v: [_r(c @ np.asarray(R, float)), _r(c @ np.asarray(U, float))] for v, (_, R, U) in VIEWS.items()}
        if key in iso_at:  # (exploded: where it is drawn in the iso view)
            ib = K.bbox(iso_at[key])
            c = np.array([(ib[0] + ib[3]) / 2, (ib[1] + ib[4]) / 2, (ib[2] + ib[5]) / 2]) if ib else c
        m["Iso"] = [_r(c @ np.asarray(ISO_VIEW[1], float)), _r(c @ np.asarray(ISO_VIEW[2], float))]
        marks[key] = m
    return {"geometry": geo, "dims": dims, "marks": marks}


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
