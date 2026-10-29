"""A drawing sheet of a 3D model part: the views (front, top, right, iso) with their exact lines, circles and arcs, the
points a dimension can hang on (each with a key from the part's face names, so a dimension stays on its edge or hole
when the part changes), the automatic dimensions for a preset — light (the overall sizes and the holes), medium (+ where
the holes are, the radii, the heights), full (+ every level) — and where the views go on the paper.

Holes alike are dimensioned once: "200× Ø5", the first one's position and the pitch of the row / grid. A hole step's
holes get one callout in the view that shows them round, with all of the step (ISO 129 symbols): "4× Ø3.4 THRU",
"M5 ↧ 8", "Ø3.4 ⌴ Ø6 ↧ 3.2", "M3 ⌵ Ø5 × 90°", "Ø8 H7 THRU", "Ø6 THRU ▲" (a teardrop) — its head's circle not given again.

The browser draws and edits the sheet (web/js/sheet/sheet.js); its SVG becomes the PDF (sheet_pdf).
Dimension JSON (in view coordinates, mm of the part):
  {id, view, kind: "linear", a: "<point key>", b: "<point key>", dir: "h" | "v", side: "b" | "t" | "l" | "r", off: paper mm,
   pre: "4× " (text before the value), pos: "<hole step id>" | "Ø3" (a hole's position), ord: true (an ordinate one: its
   value at the end of its extension line, the edge's 0 on the same row; sh: its text moved along the row, paper mm)}
  {id, view, kind: "dia" | "rad", a: "<circle key>", count, ang: degrees, len: paper mm, post: " H7", thread: "M5",
   hole: "<hole step id>" (a callout: its text from geometry.holes, see callout)}
  {id, view, kind: "pcd", a: "<ring key>" (geometry.views[view].rings), count (its steps), step: degrees, start?: the
   first hole's angle when none is on an axis, ang, len, pos} — "PCD Ø60 · 6× 60°", the pitch circle dash-dotted
Holes' positions are placed (place) so that they keep off the other views, the frame, the title block and each other.
"""
from __future__ import annotations

import hashlib
import math
import re
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
BASELINE_MAX = 3  # holes alike (not a row / grid / bolt circle) each dimensioned from the edges; more: as ordinates
# an assembly with more faces than this is drawn from its mesh (as a big part): the exact hidden-line pass of many placed
# solids can take minutes or never end (MIT E-Vent, 41 placements, 2 150 faces: its top view > 40 min, from the mesh 12 s)
ASSEMBLY_EXACT_FACES = 1000
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


_STEP = re.compile(r"(?:^|[+:])([^:+]+):(hole|cbore|csk):\d+")


def _step(key):
    """A circle of a hole step -> (step id, "hole" | "head"), else None. A pattern's / mirror's copy ("P1:2:H1:hole:0")
    is of its hole step too."""
    m = _STEP.search(key)
    return (m.group(1), "hole" if m.group(2) == "hole" else "head") if m else None


def _n(v):
    return f"{round(float(v), 2):g}"


def callout(geo, dim, thru="THRU"):
    """A hole callout's text (as the editor draws it, web/js/sheet/sheet.js dimText): "4× " the hole's size (its thread,
    else Ø measured) and fit, then its depth (↧, or THRU with neither a thread nor a head), its head (⌴ Ø6 ↧ 3.2 / ⌵ Ø5
    × 90°) and ▲ a teardrop."""
    h = (geo.get("holes") or {}).get(dim.get("hole")) or {}
    d = value(geo, dim)
    size = dim.get("thread") or f"Ø{_n(h.get('d', 0) if d is None else d)}"
    out = (f"{dim['count']}× " if dim.get("count", 1) > 1 else "") + size + (dim.get("post") or "")
    if h.get("flat"):  # a D hole: its size across the flat
        out += f" D{_n(h['flat'])}"
    if not h.get("through", True):
        out += f" ↧ {_n(h['depth'])}"
    elif not h.get("thread") and not h.get("head"):
        out += f" {thru}"
    if h.get("head") == "cbore":
        out += f" ⌴ Ø{_n(h['head_d'])} ↧ {_n(h['head_depth'])}"
    elif h.get("head") == "csk":
        out += f" ⌵ Ø{_n(h['head_d'])} × {_n(h['head_angle'])}°"
    return out + (" ▲" if h.get("teardrop") else "")


def _deco(key):
    """An edge no one dimensions: where a rounding begins (its R gives it), a teardrop hole's point (its Ø gives it), a D
    hole's flat (its callout gives it)."""
    return ":round:" in key or ":tear:" in key or "_tear:" in key or ":flat:" in key


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


def geometry(body, views=None, iso=True, scale=None, from_mesh=False):
    """The views of the part -> {bbox, views: {name: {look, right, up, visible, hidden, lines, circles, points, box}},
    iso, simple?}. lines: [{a, b, key}], circles: [{key, c, r, full, p0, p1, pm, face}], points: {key: [x, y]}.
    views: only these (names of VIEWS); iso False: no iso view (each projection is a hidden-line pass — seconds on a
    big part). A big imported model (over HEAVY_FACES, or given its `scale`) is drawn as the paper shows it at that scale
    (else the layout's): its solids, edges and holes smaller than SMALL paper mm left out, its lines simplified to FINE
    (and no hidden lines, kernel.project_edges) — simple: {left_out (solids), under (mm)}. from_mesh: so is any part
    (the exact pass took too long, see server._sheet_call)."""
    shape, bb = body.shape, K.bbox(body.shape)
    if not bb:  # (a tessellated STEP: faces with no box and a negative volume)
        raise K.KernelError("This body has no size to draw (no box: its faces are not a proper solid — e.g. a tessellated "
                            "STEP, faceted surfaces only). Export it from its CAD program as a B-rep STEP (AP214 / AP242).")
    fine = small = 0
    simple = None
    if from_mesh or scale or K.face_count(shape) > K.HEAVY_FACES:
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
            # a teardrop hole's round part (270°, its top a point) is still a hole: dimensioned Ø d; a D hole's too
            tear = face is not None and (t1 - t0 > 1.5 * math.pi - 1e-6 and (":hole:" in face or ":cbore:" in face)
                                         or t1 - t0 > math.pi + 1e-6 and ":hole:" in face)  # (more than half: Ø, ISO 129)
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
        rings = _rings(circles)
        for rg in rings:  # (a bolt circle's centre: a point its place is measured to)
            points[f"{rg['key']}#c"] = rg["c"]
        x0, y0, x1, y1 = _extent(vis + hid)
        box = [_r(x0), _r(y0), _r(x1), _r(y1)]
        points.update({"box#x0": [box[0], box[1]], "box#x1": [box[2], box[1]], "box#y0": [box[2], box[1]], "box#y1": [box[2], box[3]]})
        out["views"][vname] = {"look": list(look), "right": list(right), "up": list(up), "box": box, "lines": lines, "circles": circles, "points": points, "rings": rings,
                               "visible": [[[_r(x, 3), _r(y, 3)] for x, y in pl] for pl in vis], "hidden": [[[_r(x, 3), _r(y, 3)] for x, y in pl] for pl in hid]}
    return out


def parse_scale(text):
    """A drawing scale as people write it — "1:2522", "2:1", "1/5", "1 : 20", a number ("0.5" = 1:2, "2" = 2:1) or
    [a, b] — -> (a, b), both above 0 (paper mm : part mm); ValueError when it is not one."""
    if isinstance(text, (list, tuple)) and len(text) == 2:
        try:
            a, b = (float(v) for v in text)
        except (TypeError, ValueError):
            raise ValueError(f"A scale is two numbers, e.g. [1, 2] — not {text!r}.") from None
    else:
        m = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*(?:[:/]\s*(\d+(?:[.,]\d+)?))?\s*", "" if text is None else str(text))
        if not m:
            raise ValueError(f"A scale is written 1:2, 2:1 or 1:2522 — not {text!r}.")
        a = float(m.group(1).replace(",", "."))
        b = float(m.group(2).replace(",", ".")) if m.group(2) else 1.0
        if not m.group(2) and 0 < a < 1:  # (0.5 -> 1:2)
            a, b = 1.0, 1.0 / a
    if not (a > 0 and b > 0 and math.isfinite(a) and math.isfinite(b)):
        raise ValueError(f"A scale is two numbers above 0, e.g. 1:2 — not {text!r}.")
    return tuple(int(v) if float(v).is_integer() else round(v, 4) for v in (a, b))


TITLE_H = 38  # the title block's height (mm) when the layout is not told another
KEEP_GAP = (14.0, 18.0)  # mm a moved view keeps from the parts list / title block and the other views: beside and above it (its sizes), below it (theirs and its name)


def layout(geo, paper=None, scale=None, frame=None):
    """Where the views go: {paper, size [w, h] mm, scale [a, b], margins [left, top, right, bottom] (the frame's),
    margin (the top one), title (the title block's height), views: {name: [x, y] (the view box's centre on the paper)},
    iso: [x, y, k]} — front top-left, top below it, right beside the front, iso bottom-right (first-angle as in
    drawing.py). scale: the sheet's own ("1:2522", parse_scale), else the biggest standard one the views fit at;
    frame: {m: [left, top, right, bottom] mm, title: mm} (else 10 mm all round, a 38 mm title block), and on an
    assembly's sheet keep: its parts list and title block at the frame's corner, kept free of views (_keep), iso_at:
    "Right" (the iso view in the right view's place). A view in their way moves up or left (_clear); with no room the
    iso view gets smaller, then the auto scale goes a step smaller (an own scale stays: the editor warns)."""
    bb = geo["bbox"]
    size = (bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2])
    need_w, need_h = max(size[0] + size[1], 1), max(size[2] + size[1], 1)
    fr = frame or {}
    ml, mt, mr, mb = (max(0.0, min(60.0, float(v))) for v in ((list(fr.get("m") or [10])) * 4)[:4])
    title = max(0.0, min(80.0, float(fr.get("title") or TITLE_H)))
    fixed = parse_scale(scale) if scale else None
    for pname in ([paper] if paper in PAPERS else ["A4", "A3"]):
        pw, ph = PAPERS[pname]
        iw, ih = pw - ml - mr, ph - mt - mb - title
        fits = lambda a, b: a / b * need_w <= iw * 0.62 and a / b * need_h <= ih * 0.62  # noqa: E731
        fit = ([fixed] if fits(*fixed) else []) if fixed else [(a, b) for a, b in SCALES if fits(a, b)]
        if fit or pname == "A3" or paper:
            break
    scale = fixed or (fit[0] if fit else SCALES[-1])
    cw, ch = iw / 2, ih / 2
    views = {"Front": [ml + cw / 2, mt + ch / 2], "Right": [ml + cw * 1.5, mt + ch / 2], "Top": [ml + cw / 2, mt + ch * 1.5]}
    iso = [ml + cw * 1.5, mt + ch * 1.5, 0.55 * min(cw, ch)]
    keep = _keep(fr.get("keep"), pname, pw, ph, mr, mb)
    if keep:
        at = fr.get("iso_at") == "Right"  # (an assembly's sheet: the iso view where the right one would be)
        tries = ((sc, f) for sc in ([scale] if fixed else fit or [scale]) for f in (1, 0.8, 0.65))  # (the iso view smaller before the scale: it shows, the views measure)
        found = next(((sc, r) for sc, f in tries if (r := _room(size, sc, iso[2] * f, views, iso, keep, (ml, mt, pw - mr, ph - mb), at))), None)
        if found:
            scale, (views, iso) = found[0], found[1]
    return {"paper": pname, "size": [pw, ph], "scale": list(scale), "margin": mt, "margins": [ml, mt, mr, mb], "title": title,
            "views": views, "iso": iso}


def _keep(keep, pname, pw, ph, mr, mb):
    """The frame's keep-out — [[w, h], …] mm, or {paper: [[w, h], …]}: rectangles at the frame's inner bottom-right
    corner, h from the frame's bottom (the title block: [its width, its height]; the parts list on it: [its width,
    both heights]) -> [(x0, y0, x1, y1)] on the paper (y down); the views keep off their union."""
    if isinstance(keep, dict):
        keep = keep.get(pname)
    out = []
    for r in keep if isinstance(keep, list) else []:
        try:
            w, h = (max(0.0, float(v)) for v in r[:2])
        except (TypeError, ValueError, IndexError):
            continue
        if w > 0 and h > 0:
            out.append((pw - mr - w, ph - mb - h, pw - mr, ph - mb))
    return out


def _room(size, sc, k, views, iso, keep, inner, at):
    """The views at scale sc (the iso view k mm) off the keep-out -> (views, iso [x, y, k]), or None (no room)."""
    s = sc[0] / sc[1]
    half = {"Front": (size[0] * s / 2, size[2] * s / 2), "Top": (size[0] * s / 2, size[1] * s / 2), "Right": (size[1] * s / 2, size[2] * s / 2)}
    if at:
        half["Right"] = (k / 2, k / 2)
    else:
        half["Iso"] = (k / 2, k / 2)
    moved = _clear({**views, **({} if at else {"Iso": iso[:2]})}, half, keep, inner, at)
    if not moved:
        return None
    return {v: [round(c, 2) for c in moved[v]] for v in views}, [*(round(c, 2) for c in moved["Right" if at else "Iso"]), round(k, 2)]


def _clear(views, half, keep, inner, at=False):
    """The views ({name: [x, y]}, their half sizes {name: (w / 2, h / 2)} on the paper) moved off the keep-out
    rectangles: each one in the way up or left — the shorter move that stays inside the frame (inner: x0, y0, x1, y1)
    and KEEP_GAP from the other views -> {name: [x, y]}, or None (no room). The front and the top view move left
    together, the front and the right one up together (they line up; at: the right one is the iso view, free)."""
    gs, gb = KEEP_GAP
    lines = {"left": ("Front", "Top"), "up": () if at else ("Front", "Right")}
    box = lambda v, c: (c[0] - half[v][0], c[1] - half[v][1], c[0] + half[v][0], c[1] + half[v][1])  # noqa: E731
    pad = lambda b: (b[0] - gs, b[1] - gs, b[2] + gs, b[3] + gb)  # noqa: E731
    meets = lambda a, b: a[0] < b[2] - 1e-6 and b[0] < a[2] - 1e-6 and a[1] < b[3] - 1e-6 and b[1] < a[3] - 1e-6  # noqa: E731
    views = {v: list(c) for v, c in views.items()}
    for _ in range(2 * len(views)):
        hit = next((v for v in views if any(meets(pad(box(v, views[v])), r) for r in keep)), None)
        if hit is None:
            return views
        pb, best = pad(box(hit, views[hit])), None
        dy = min(r[1] for r in keep if r[0] < pb[2] and pb[0] < r[2]) - pb[3]  # (up: over the highest one under it)
        dx = min(r[0] for r in keep if r[1] < pb[3] and pb[1] < r[3]) - pb[2]  # (left: past the widest one beside it)
        for way, d in sorted((("up", dy), ("left", dx)), key=lambda q: abs(q[1])):
            ws = lines[way] if hit in lines[way] else (hit,)
            cand = {v: ([c[0] + d, c[1]] if way == "left" else [c[0], c[1] + d]) if v in ws else c for v, c in views.items()}
            bs = {v: box(v, c) for v, c in cand.items()}
            if all(bs[v][0] >= inner[0] - 1e-6 and bs[v][1] >= inner[1] - 1e-6 and not any(meets(pad(bs[v]), r) for r in keep) for v in ws) \
                    and not any(meets(pad(bs[a]), bs[b]) or meets(pad(bs[b]), bs[a]) for a in ws for b in cand if b not in ws):
                best = cand
                break
        if best is None:
            return None
        views = best
    return None


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


def _ring(cs):
    """Circles alike evenly round a centre — a bolt circle: all round (≥ 3) or an arc of it (≥ 4, one gap wider) ->
    {c, r, n, step, start (the first one's angle, degrees ccw from the view's right), full} or None."""
    if len(cs) < 3:
        return None
    P = np.array([c["c"] for c in cs], float)
    sol = np.linalg.lstsq(np.c_[2 * P, np.ones(len(P))], (P ** 2).sum(1), rcond=None)[0]
    c, rr = sol[:2], sol[2] + sol[:2] @ sol[:2]
    if not (np.isfinite(rr) and rr > 1e-6):
        return None
    r = math.sqrt(rr)
    if r > 1e4 or np.abs(np.hypot(*(P - c).T) - r).max() > 0.01:
        return None
    ang = sorted(math.degrees(math.atan2(p[1] - c[1], p[0] - c[0])) % 360 for p in P)
    gaps = [b - a for a, b in zip(ang, ang[1:])] + [ang[0] + 360 - ang[-1]]
    step = min(gaps)
    same = [abs(g - step) < 0.05 for g in gaps]
    if step < 1 or sum(same) < len(gaps) - 1 or (not all(same) and len(cs) < 4):
        return None
    full = all(same)
    start = ang[0] if full else ang[(gaps.index(max(gaps)) + 1) % len(ang)]
    return {"c": [_r(c[0]), _r(c[1])], "r": _r(r), "n": len(cs), "step": _r(step, 3), "start": _r(start % 360, 3), "full": full}


def _rings(circles):
    """A view's bolt circles: its holes alike (one size, one hole step) evenly round a centre, not in a row / grid ->
    [{key ("pcd:" + its first hole's key), c, r, n, step, start, full, keys}]."""
    groups = {}
    for c in circles:
        st = _step(c["key"])
        if c["full"] and (st is None or st[1] == "hole"):  # (not a counterbore's circles: its holes' ring gives them)
            groups.setdefault((round(c["r"], 3), st[0] if st else ""), []).append(c)
    out = []
    for _, cs in sorted(groups.items()):
        rg = len(cs) >= 3 and not _grid(cs) and _ring(cs)
        if rg:
            first = min(cs, key=lambda c: (round(c["c"][1], 2), round(c["c"][0], 2)))
            out.append({"key": f"pcd:{first['key']}", **rg, "keys": sorted(c["key"] for c in cs)})
    return out


def auto_dims(geo, preset="medium", fits=None, per_view=None, threads=None, holes=None):
    """The automatic dimensions of a preset (see the module's docstring). fits: {diameter: "H7"} (holes with a fit),
    threads: {tap drill Ø: "M5"} (threaded holes: labelled M5), holes: {step id: what its callout says} (doc._holes —
    each step's holes one callout, in the first view showing them round).
    per_view: {view: preset} — a view's own preset instead of the sheet's; "all": every size of that view, the ones
    given in another view too (its outer sizes, its holes, its edges' places) — as full."""
    preset = preset if preset in PRESETS else "medium"
    per_view = {k: v for k, v in (per_view or {}).items() if v in PRESETS + ("all",)}
    every = {k for k, v in per_view.items() if v == "all"}
    pv = lambda view: "full" if view in every else per_view.get(view, preset)  # noqa: E731
    fits = {round(float(d), 3): f for d, f in (fits or {}).items() if f}
    threads = {round(float(d), 3): m for d, m in (threads or {}).items() if m}
    dims, stack, measured = [], {}, set()

    def lin(view, a, b, d, side, pre="", tag="", pos=None, off=None):
        # one dimension per distance: the same direction between the same places only once (concentric circles,
        # holes in a row share their places). pos: a hole position (of that step / size); off given: an ordinate
        # one on that shared row
        pts = geo["views"][view]["points"]
        if a in pts and b in pts:
            k = 0 if d == "h" else 1
            sig = (view, d, *sorted((round(pts[a][k], 2), round(pts[b][k], 2))))
            if sig in measured or sig[2] == sig[3]:
                return
            measured.add(sig)
        if off is None:
            n = stack.get((view, side), 0)
            stack[(view, side)] = n + 1
        dims.append({"id": _id(view, a, b, d, tag), "view": view, "kind": "linear", "a": a, "b": b, "dir": d, "side": side,
                     "off": 8 + 7 * n if off is None else off, **({"pre": pre} if pre else {}), **({"pos": pos} if pos else {}),
                     **({"ord": True} if off is not None else {})})

    def where(vname, cs, tg, pos):
        # where holes alike are, from the view's left / bottom edge (ISO 129): a row / grid its first one and its
        # pitch "3× 10", a bolt circle its centre and the pitch circle "PCD Ø60 · 6× 60°", a few each from the edges
        # (baseline), more as ordinates (one row a direction, the edge 0)
        sh = "t" if vname == "Top" else "b"
        first = min(cs, key=lambda c: (round(c["c"][1], 2), round(c["c"][0], 2)))
        g = _grid(cs) if len(cs) > 1 else None
        keys = sorted(c["key"] for c in cs)
        ring = None if g else next((r for r in v[vname].get("rings") or () if r["keys"] == keys), None)
        if ring:
            lin(vname, "box#x0", f"{ring['key']}#c", "h", sh, tag=f"x{tg}", pos=pos)
            lin(vname, "box#y0", f"{ring['key']}#c", "v", "l", tag=f"y{tg}", pos=pos)
            on_axis = any(abs((ring["start"] + i * ring["step"] + 45) % 90 - 45) < 0.01 for i in range(ring["n"]))
            dims.append({"id": _id(vname, "pcd", tg), "view": vname, "kind": "pcd", "a": ring["key"], "count": ring["n"] if ring["full"] else ring["n"] - 1,
                         "step": ring["step"], **({} if on_axis else {"start": ring["start"]}), "ang": 45, "len": 6, "pos": pos})
            return
        if g or len(cs) <= BASELINE_MAX:
            lin(vname, "box#x0", f"{first['key']}#c", "h", sh, tag=f"x{tg}", pos=pos)
            lin(vname, "box#y0", f"{first['key']}#c", "v", "l", tag=f"y{tg}", pos=pos)
        if g:
            nx, ny, px, py = g
            row = sorted(cs, key=lambda c: (round(c["c"][1], 2), round(c["c"][0], 2)))
            if nx > 1:
                lin(vname, f"{row[0]['key']}#c", f"{row[1]['key']}#c", "h", sh, pre=f"{nx - 1}× " if nx > 2 else "", tag=f"px{tg}", pos=pos)
            if ny > 1:
                up = next(c for c in row if round(c["c"][1], 2) > round(row[0]["c"][1], 2))
                lin(vname, f"{row[0]['key']}#c", f"{up['key']}#c", "v", "l", pre=f"{ny - 1}× " if ny > 2 else "", tag=f"py{tg}", pos=pos)
        elif len(cs) <= BASELINE_MAX:
            for c in sorted(cs, key=lambda c: (c["c"][1], c["c"][0]))[1:]:
                lin(vname, "box#x0", f"{c['key']}#c", "h", sh, tag=f"x{tg}{c['key']}", pos=pos)
                lin(vname, "box#y0", f"{c['key']}#c", "v", "l", tag=f"y{tg}{c['key']}", pos=pos)
        else:
            limit = 30 if pv(vname) == "medium" else 60
            for d, side, k in (("h", sh, 0), ("v", "l", 1)):
                n = stack.get((vname, side), 0)
                stack[(vname, side)] = n + 2  # (its values stand out past the row)
                for c in sorted(cs, key=lambda c: (c["c"][k], c["c"][1 - k]))[:limit]:
                    lin(vname, f"box#{'xy'[k]}0", f"{c['key']}#c", d, side, tag=f"o{d}{tg}{c['key']}", pos=pos, off=8 + 7 * n)

    v = geo["views"]
    # the overall sizes: width and height in the front, depth in the top
    lin("Front", "box#x0", "box#x1", "h", "b")
    lin("Front", "box#y0", "box#y1", "v", "r")
    lin("Top", "box#y0", "box#y1", "v", "r")
    for vname in sorted(every & set(v)):  # (a view with all its sizes: its own outer sizes too)
        lin(vname, "box#x0", "box#x1", "h", "b")
        lin(vname, "box#y0", "box#y1", "v", "r")
    done_r, called = set(), set()
    ANG = [45, 135, 315, 225, 20, 160, 340, 200]
    for vname in ("Top", "Front", "Right"):
        view = v[vname]
        full = [c for c in view["circles"] if c["full"]]
        arcs = [c for c in view["circles"] if not c["full"]]
        stepped = {st[0]: True for c in full if (st := _step(c["key"])) and st[1] == "hole"}  # (hole steps whose holes are round here)
        groups = {}
        for c in full:
            groups.setdefault(round(2 * c["r"], 3), []).append(c)
        # concentric circles: their leaders spread round
        centres = {}
        covered = set()  # circles a hole callout gives (its holes and their heads)
        for fid, h in (holes or {}).items():
            mine = [c for c in full if _step(c["key"]) == (fid, "hole")]
            if fid in called or not mine:
                continue
            called.add(fid)
            covered |= {c["key"] for c in full if _step(c["key"]) and _step(c["key"])[0] == fid}
            first = min(mine, key=lambda c: (round(c["c"][1], 2), round(c["c"][0], 2)))
            at = (round(first["c"][0], 1), round(first["c"][1], 1))
            k = centres[at] = centres.get(at, -1) + 1
            dims.append({"id": _id(vname, "hole", fid), "view": vname, "kind": "dia", "a": first["key"], "count": len(mine), "hole": fid,
                         "ang": ANG[k % 8], "len": 6 + 5 * (k // 4), **({"post": f" {h['fit']}"} if h.get("fit") else {}), **({"thread": h["thread"]} if h.get("thread") else {})})
        for d, cs in sorted(groups.items(), key=lambda q: -q[0]):
            if d in done_r and vname not in every:  # already given in another view
                continue
            done_r.add(d)
            rest = [c for c in cs if c["key"] not in covered]  # (not the ones a callout gives)
            if rest:
                first = min(rest, key=lambda c: (round(c["c"][1], 2), round(c["c"][0], 2)))
                at = (round(first["c"][0], 1), round(first["c"][1], 1))
                k = centres[at] = centres.get(at, -1) + 1
                dims.append({"id": _id(vname, "dia", d), "view": vname, "kind": "dia", "a": first["key"], "count": len(rest),
                             "ang": ANG[k % 8], "len": 6 + 5 * (k // 4), **({"post": f" {fits[d]}"} if d in fits else {}), **({"thread": threads[d]} if d in threads else {})})
            if pv(vname) == "light":
                continue
            subs = {}  # (one hole step's holes apart from another's of the same size; a counterbore's circles: its holes give their places)
            for c in cs:
                st = _step(c["key"])
                if not (st and st[1] == "head" and stepped.get(st[0])):
                    subs.setdefault(st[0] if st else "", []).append(c)
            for sid, sub in sorted(subs.items()):
                where(vname, sub, f"{d}{sid}" if len(subs) > 1 else f"{d}", sid or f"Ø{_n(d)}")
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


FS = 3.2  # paper mm: the editor's dimension text (sheet.js dimSvg)
TITLE_W = 180  # paper mm: the widest title block (ISO 7200), kept free of dimensions
OPPOSITE = {"t": "b", "b": "t", "l": "r", "r": "l"}


def _text(geo, d, v):
    """A dimension's text as the editor writes it (sheet.js dimText) — how far it reaches."""
    if d["kind"] == "dia":
        return callout(geo, d) if d.get("hole") else (f"{d['count']}× " if d.get("count", 1) > 1 else "") + (d.get("thread") or f"Ø{_n(v)}") + (d.get("post") or "")
    if d["kind"] == "rad":
        return f"R{_n(v)}"
    if d["kind"] == "pcd":
        return f"PCD Ø{_n(v)} · {d['count']}× {_n(d['step'])}°" + (f" ({_n(d['start'])}°)" if "start" in d else "")
    return ("" if d.get("ord") else d.get("pre", "")) + _n(v)


def _meet(a, b):
    """How much two rectangles [x0, y0, x1, y1] cover each other (mm²)."""
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


class _Paper:
    """Where the editor draws a sheet's views and dimensions for a layout (sheet.js P, paperBox, dimSvg): paper mm, y down."""

    def __init__(self, geo, lay):
        self.geo, self.s = geo, lay["scale"][0] / lay["scale"][1]
        self.at = {v: c for v, c in lay["views"].items() if v in geo["views"]}
        self.vs = {v: s[0] / s[1] for v, s in (lay.get("vscale") or {}).items() if s and s[1]}  # (a view at its own scale)

    def sc(self, v):
        return self.vs.get(v, self.s)

    def P(self, v, p):
        b, (cx, cy), s = self.geo["views"][v]["box"], self.at[v], self.sc(v)
        return cx + (p[0] - (b[0] + b[2]) / 2) * s, cy - (p[1] - (b[1] + b[3]) / 2) * s

    def box(self, v):
        b = self.geo["views"][v]["box"]
        (x0, y1), (x1, y0) = self.P(v, b[:2]), self.P(v, b[2:])
        return x0, y0, x1, y1

    def row(self, d):
        """A linear dimension's line: its y (h) / x (v)."""
        pb, off = self.box(d["view"]), d.get("off", 8)
        return {"t": pb[1] - off, "b": pb[3] + off, "l": pb[0] - off, "r": pb[2] + off}[d["side"]]

    def ord_text(self, d, at, L):
        """An ordinate value's rectangle: across the row at `at` (paper x of an h one, y of a v one), L long."""
        r = self.row(d)
        far = (r - 0.5, r + 1 + L) if d["side"] in ("b", "r") else (r - 1 - L, r + 0.5)
        return (at - FS * 0.5, far[0], at + FS * 0.5, far[1]) if d["dir"] == "h" else (far[0], at - FS * 0.5, far[1], at + FS * 0.5)

    def zero(self, d):
        """An ordinate row's 0 at its edge."""
        return self.ord_text(d, self.P(d["view"], self.geo["views"][d["view"]]["points"][d["a"]])[0 if d["dir"] == "h" else 1], FS * 0.6)

    def foot(self, d):
        """The rectangles a dimension's line and text cover (not its thin extension lines / leader) -> [[x0, y0, x1, y1]]."""
        v = d["view"]
        val = value(self.geo, d) if v in self.at else None
        if val is None:
            return []
        g, tw = self.geo["views"][v], len(_text(self.geo, d, val)) * FS * 0.6
        if d["kind"] == "linear":
            A, B, at, k = self.P(v, g["points"][d["a"]]), self.P(v, g["points"][d["b"]]), self.row(d), 0 if d["dir"] == "h" else 1
            if d.get("ord"):
                return [self.ord_text(d, B[k] + d.get("sh", 0), tw)]
            lo, hi = sorted((A[k], B[k]))
            if hi - lo < 8:  # (a short one: its arrows from outside)
                lo, hi = lo - 5, hi + 5
            mid = (lo + hi) / 2
            lo, hi = min(lo, mid - tw / 2), max(hi, mid + tw / 2)
            return [(lo - 0.5, at - FS - 1, hi + 0.5, at + 0.6) if k == 0 else (at - FS - 1.2, lo - 0.5, at + 0.6, hi + 0.5)]
        if d["kind"] in ("dia", "pcd"):
            c = next((c for c in (g["circles"] if d["kind"] == "dia" else g.get("rings") or ()) if c["key"] == d["a"]), None)
            C, R, a = self.P(v, c["c"]), c["r"] * self.sc(v), math.radians(d.get("ang", 45))
            u, ln = (math.cos(a), -math.sin(a)), d.get("len", 6)
            end, w = (C[0] + u[0] * (R + ln), C[1] + u[1] * (R + ln)), len(_text(self.geo, d, val)) * FS * 0.52 + 1
            x0, x1 = (end[0], end[0] + w) if u[0] >= 0 else (end[0] - w, end[0])
            return [(x0, end[1] - FS - 1, x1, end[1] + 0.3)]
        return []


def _obstacles(pp, lay):
    """What dimensions keep off besides each other: outside the frame, the title block, the iso view -> rectangles."""
    pw, ph = lay["size"]
    ml, mt, mr, mb = lay.get("margins") or [lay.get("margin", 10)] * 4
    out = [(-1e4, -1e4, ml, 1e4), (pw - mr, -1e4, 1e4, 1e4), (-1e4, -1e4, 1e4, mt), (-1e4, ph - mb, 1e4, 1e4),
           (pw - mr - TITLE_W, ph - mb - lay.get("title", TITLE_H), pw - mr, ph - mb)]
    if pp.geo.get("iso") and lay.get("iso"):
        x, y, k = lay["iso"]
        out.append((x - k / 2, y - k / 2, x + k / 2, y + k / 2))
    return out


def _rows(dims):
    """The ordinate rows: {(view, dir, side, off): [their dims]}."""
    rows = OrderedDict()
    for d in dims:
        if d.get("ord") and d["kind"] == "linear":
            rows.setdefault((d["view"], d["dir"], d["side"], d.get("off", 8)), []).append(d)
    return rows


def place(geo, lay, dims):
    """The holes' positions and callouts kept clear, as the editor draws them on this layout: an ordinate row's values
    that would touch moved apart along it (sh, from the edge's 0 on); a view's hole positions on a side where they run
    into another view, the frame, the title block or other dimensions moved to the view's other side when they are
    clearer there (after its dimensions); a callout whose text is in the way turned / lengthened to the first clear
    place, outside its own view when it can be. lay.views: where the views are (moved by the user too), lay.vscale:
    {view: [a, b]} a view's own scale. -> the dims (new dicts; the rest as they were)."""
    pp, dims = _Paper(geo, lay), [dict(d) for d in dims]
    for row in _rows([d for d in dims if d["view"] in pp.at]).values():
        k = 0 if row[0]["dir"] == "h" else 1
        z = pp.P(row[0]["view"], geo["views"][row[0]["view"]]["points"][row[0]["a"]])[k]
        q = 0.0
        for d, p in sorted(((d, pp.P(d["view"], geo["views"][d["view"]]["points"][d["b"]])[k]) for d in row if value(geo, d) is not None), key=lambda e: abs(e[1] - z)):
            q = max(abs(p - z), q + FS + 0.8)
            sh = round((q - abs(p - z)) * (1 if p >= z else -1), 2)
            if sh:
                d["sh"] = sh
            else:
                d.pop("sh", None)
    views, walls = {v: pp.box(v) for v in pp.at}, _obstacles(pp, lay)
    lin = [d for d in dims if d["kind"] == "linear" and d["view"] in pp.at]
    groups = OrderedDict()
    for d in lin:
        if d.get("pos"):
            groups.setdefault((d["view"], d["dir"], d["side"]), []).append(d)
    for (v, dr, side), ds in groups.items():
        mine = {id(d) for d in ds}
        others = [b for w, b in views.items() if w != v] + walls + [r for d in lin if id(d) not in mine for r in pp.foot(d)] \
            + [pp.zero(r[0]) for key, r in _rows(lin).items() if not any(id(d) in mine for d in r)]

        def bad(cand):
            rs = [r for d in cand for r in pp.foot(d)] + [pp.zero(r[0]) for r in _rows(cand).values()]
            return sum(_meet(r, o) for r in rs for o in others)

        now = bad(ds)
        if not now:
            continue
        there = [d.get("off", 8) for d in lin if d["view"] == v and d["dir"] == dr and d["side"] == OPPOSITE[side] and id(d) not in mine]
        base, low = (max(there) + 7 if there else 8), min(d.get("off", 8) for d in ds)
        moved = [{**d, "side": OPPOSITE[side], "off": base + d.get("off", 8) - low} for d in ds]
        if bad(moved) < now:
            for d, m in zip(ds, moved):
                d.update(side=m["side"], off=m["off"])
    fixed = [r for d in lin for r in pp.foot(d)] + [pp.zero(r[0]) for r in _rows(lin).values()]
    done = []
    for d in dims:
        if d["kind"] not in ("dia", "pcd") or d["view"] not in pp.at or not pp.foot(d):
            continue
        rest = [b for w, b in views.items() if w != d["view"]] + walls + fixed + done

        def hit(o, inner=True):
            return sum(_meet(r, x) for r in pp.foot({**d, **o}) for x in rest + ([views[d["view"]]] if inner else []))

        cur = {"ang": d.get("ang", 45), "len": d.get("len", 6)}
        if hit(cur):
            tries = [{"ang": a, "len": ln} for ln in (6, 12, 20, 30, 40) for a in (45, 135, 315, 225, 20, 160, 340, 200, 70, 110, 250, 290)]
            d.update(next((o for o in tries if not hit(o)), None) or min([cur] + tries, key=lambda o: hit(o, False)))
        done += pp.foot(d)
    return dims


def overlaps(geo, lay, dims):
    """What covers what on the sheet as drawn: [(dim id, dim id | a view's name | "frame")] — two dimensions' lines /
    texts, a dimension over another view, past the frame or on the title block / iso view."""
    pp, out = _Paper(geo, lay), []
    feet = [(d["id"], r) for d in dims for r in pp.foot(d)] + [(f"0:{k[0]}:{k[1]}:{k[2]}", pp.zero(r[0])) for k, r in _rows(dims).items() if r[0]["view"] in pp.at]
    views, walls = {v: pp.box(v) for v in pp.at}, _obstacles(pp, lay)
    for i, (a, ra) in enumerate(feet):
        out += [(a, b) for b, rb in feet[i + 1:] if a != b and _meet(ra, rb) > 0.01]
        view = next((d["view"] for d in dims if d["id"] == a), a.split(":")[1] if a.startswith("0:") else None)
        out += [(a, v) for v, b in views.items() if v != view and _meet(ra, b) > 0.01]
        out += [(a, "frame") for w in walls if _meet(ra, w) > 0.01]
    return out


def build(body, preset="medium", fits=None, paper=None, per_view=None, threads=None, section=False, key=None, holes=None, simple=False):
    """Everything a new / changed sheet needs: {geometry, layout, dims (automatic)}. section: also the section A–A
    (geometry.views.Section). key: the part's hash — its views are kept (_cached), only the dimensions made again.
    holes: the hole steps (doc._holes) — geometry.holes, for their callouts. simple: drawn from its mesh (geometry)."""
    geo = _cached((key, "views", bool(simple)), lambda: geometry(body, from_mesh=simple))
    geo = {**geo, "views": dict(geo["views"])}
    if holes:
        geo["holes"] = holes
    if section:
        geo["views"]["Section"] = _cached((key, "section"), lambda: section_view(body))
    vol = _cached((key, "volume"), lambda: K.volume(getattr(body, "shape", body)))  # (mm³: the title block's mass, with the part's material)
    lay = layout(geo, paper)
    return {"geometry": geo, "layout": lay, "dims": place(geo, lay, auto_dims(geo, preset, fits, per_view, threads, holes)), "volume": round(vol, 3)}


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
            mk = K.bop("common", s, keep) if b[3] > xm else None
            if mk is not None and not mk.IsDone():
                raise K.KernelError("The part could not be cut for its section.")
            if mk is not None:  # (its new faces meshed as the rest: the view is drawn from the mesh)
                BRepMesh_IncrementalMesh(mk.Shape(), max(size * 0.004, 0.002), False, 0.6, True)
            kept.append(mk.Shape() if mk is not None else s)
        half = K.compound(kept)
    else:
        mk = K.bop("common", body.shape, keep)
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


def build_assembly(placed, paper=None, iso_placed=None, key=None, simple=False, base=None):
    """An assembly's sheet: placed [(id, shape placed)] -> {geometry, layout, dims (its overall sizes; the base part's
    mounting holes' positions), marks: {id: {Front, Top, Right, Iso: [x, y]} (the middle of each placed part; in the iso
    view, for its balloon, a spot on its own faces the others leave bare), seen (how much of it shows there, mm²)}}.
    iso_placed: the same parts pulled apart — the iso view drawn exploded (the other views as assembled). key: the
    placed parts' hash (kept, see _cached). simple: drawn from the mesh (so is one over ASSEMBLY_EXACT_FACES faces).
    base: the id of the part the assembly stands on (see _mounting)."""
    out = _cached((key, "assembly", bool(simple), base), lambda: _assembly(placed, iso_placed, simple, base))
    lay = layout(out["geometry"], paper)
    return {**out, "layout": lay, "dims": place(out["geometry"], lay, out["dims"]) if out["geometry"].get("mount") else out["dims"]}


def _free_holes(shape, others):
    """A part's holes no other part is in (a free mounting hole): its round faces with their axis outside the part,
    none of `others` (placed shapes) at a quarter, half or three quarters of the way along it -> [(centre (at half
    way), axis, r)]."""
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.TopAbs import TopAbs_FACE, TopAbs_IN
    from OCP.TopExp import TopExp_Explorer
    from OCP.gp import gp_Pnt
    near = [(s, K.bbox(s)) for s in others]
    cls, out, ex = {}, [], TopExp_Explorer(shape, TopAbs_FACE)

    def inside(i, s, p):
        if i not in cls:
            cls[i] = BRepClass3d_SolidClassifier(s)
        cls[i].Perform(gp_Pnt(*map(float, p)), 1e-6)
        return cls[i].State() == TopAbs_IN

    while ex.More():
        s = BRepAdaptor_Surface(TopoDS.Face(ex.Current()))
        ex.Next()
        if s.GetType() != GeomAbs_Cylinder:
            continue
        ax, r = s.Cylinder().Axis(), s.Cylinder().Radius()
        o, d = np.array([ax.Location().X(), ax.Location().Y(), ax.Location().Z()]), np.array([ax.Direction().X(), ax.Direction().Y(), ax.Direction().Z()])
        v0, v1 = s.FirstVParameter(), s.LastVParameter()
        ps = [o + d * (v0 + (v1 - v0) * t) for t in (0.25, 0.5, 0.75)]
        if inside("base", shape, ps[1]):  # (a boss, a round outside: its axis in the part)
            continue
        if any(b and all(b[k] - TOL <= p[k] <= b[k + 3] + TOL for k in range(3)) and inside(i, s2, p) for i, (s2, b) in enumerate(near) for p in ps):
            continue  # (a pin, a screw in it)
        out.append((ps[1], d, r))
    return out


def _mounting(geo, base, others):
    """The base part's free holes (no screw / pin of the assembly in them: where the assembly is mounted) dimensioned
    from the base part's own left / bottom edge in the view showing them round, as a part's sheet places its holes
    (auto_dims: a row / grid its first one and pitch, a bolt circle, a few from the edges, more as ordinates) -> those
    dims (pos "Ø6.6"). Adds to geo: each view's base#x0 / base#y0 (the base part's corners, as box#x0 / box#y0) and
    the holes' bolt circles ("mnt:pcd:…"); geo.mount [{view, keys}] (the circles, for the sheet's check)."""
    holes, bb = _free_holes(base, others), K.bbox(base)
    if not holes or not bb:
        return []
    corners = np.array([[x, y, z] for x in (bb[0], bb[3]) for y in (bb[1], bb[4]) for z in (bb[2], bb[5])])
    sub, mine = {}, {}
    for vname, (look, right, up) in VIEWS.items():
        g = geo["views"].get(vname)
        if not g:
            continue
        L, R, U = (np.asarray(v, float) for v in (look, right, up))
        free = {}
        for c3, d, r in holes:
            if abs(float(d @ L)) < 0.999:
                continue
            p = (float(c3 @ R), float(c3 @ U))
            c = next((c for c in g["circles"] if c["full"] and abs(c["r"] - r) < 1e-3 and math.dist(c["c"], p) < 0.01), None)
            if c:
                free[c["key"]] = c
        x0, x1 = _r((corners @ R).min()), _r((corners @ R).max())
        y0 = _r((corners @ U).min())
        rings = [{**rg, "key": f"mnt:{rg['key']}"} for rg in _rings(list(free.values()))]
        pts = {**g["points"], "box#x0": [x0, y0], "box#y0": [x1, y0], **{f"{rg['key']}#c": rg["c"] for rg in rings}}
        sub[vname] = {**g, "circles": list(free.values()), "lines": [], "rings": rings, "points": pts}
        mine[vname] = (x0, x1, y0, rings)
    to = {"box#x0": "base#x0", "box#y0": "base#y0"}
    dims, mount = [], []
    for vname, (x0, x1, y0, rings) in mine.items():
        if not sub[vname]["circles"]:
            continue
        # (each view on its own: holes of one size in two directions positioned in both views)
        alone = {w: g if w == vname else {**g, "circles": [], "rings": []} for w, g in sub.items()}
        ds = [{**d, "id": _id("mount", d["id"]), "a": to.get(d["a"], d["a"]), **({"b": to.get(d["b"], d["b"])} if "b" in d else {})}
              for d in auto_dims({**geo, "views": alone}, "medium") if d.get("pos")]
        if not ds:
            continue
        dims += ds
        g = geo["views"][vname]
        g["points"].update({"base#x0": [x0, y0], "base#y0": [x1, y0], **{f"{rg['key']}#c": rg["c"] for rg in rings}})
        g["rings"] = (g.get("rings") or []) + rings
        mount.append({"view": vname, "keys": sorted(c["key"] for c in sub[vname]["circles"])})
    geo["mount"] = mount
    return dims


def _assembly(placed, iso_placed, simple=False, base=None):
    shapes = [s for _, s in placed]
    if not shapes:
        raise K.KernelError("The assembly has no solids to draw.")
    whole = K.compound(shapes)
    simple = simple or K.face_count(whole) > ASSEMBLY_EXACT_FACES
    geo = geometry(_Placed(whole), iso=not iso_placed, from_mesh=simple)  # (exploded: its own iso below)
    if iso_placed:
        geo["iso"] = _iso_view(K.compound([s for _, s in iso_placed]), "simple" in geo)
    iso_at = dict(iso_placed or [])
    dims = [d for d in auto_dims(geo, "light") if d["kind"] == "linear" and d["a"].startswith("box#")]
    at = dict(placed)
    if base in at:  # (its mounting holes: where the assembly is fastened down)
        dims += _mounting(geo, at[base], [s for k, s in placed if k != base])
    spots = {} if simple else _shown_spots(iso_placed or placed)  # (a big one: the middles, quickly)
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
        if key in spots:  # (on a face of its own the others leave bare; else the middle)
            m["Iso"], m["seen"] = spots[key]
        marks[key] = m
    return {"geometry": geo, "dims": dims, "marks": marks}


SPOT_GRID = 220  # cells across the iso view, for where each part shows


def _shown_spots(placed):
    """Where each placed part shows in the iso view, for its balloon's leader: placed [(id, shape)] -> {id: ([x, y] —
    inside the largest patch of its own faces that no other part hides, apart from the other parts' spots), mm² of
    it seen)}. A depth buffer of points strewn over the parts' coarse triangles; a part hidden all over is left out."""
    R, U = np.asarray(ISO_VIEW[1], float), np.asarray(ISO_VIEW[2], float)
    T = -np.asarray(ISO_VIEW[0], float) / np.linalg.norm(ISO_VIEW[0])  # (towards the viewer)
    tris, own = [], []
    for k, (_, s) in enumerate(placed):
        bb = K.bbox(s)
        if not bb:
            continue
        t = K.view_triangles(s, max(math.dist(bb[:3], bb[3:]) / 150, 0.02))
        if len(t):
            tris.append(t)
            own.append(np.full(len(t), k))
    if not tris:
        return {}
    tri, owner = np.concatenate(tris), np.concatenate(own)
    P, Z = np.stack([tri @ R, tri @ U], -1), tri @ T
    lo, hi = P.reshape(-1, 2).min(0), P.reshape(-1, 2).max(0)
    cell = max(float((hi - lo).max()) / SPOT_GRID, 1e-6)
    W, H = int((hi[0] - lo[0]) / cell) + 1, int((hi[1] - lo[1]) / cell) + 1
    # about 3 points in each cell a triangle covers (one at least); the nearest one in a cell wins it
    e1, e2 = P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]
    n = np.clip(np.ceil(np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]) / 2 / cell ** 2 * 3).astype(int), 1, 4000)
    ti = np.repeat(np.arange(len(tri)), n)
    rng = np.random.default_rng(0)
    a, b = rng.random(len(ti)), rng.random(len(ti))
    out = a + b > 1
    a[out], b[out] = 1 - a[out], 1 - b[out]
    w = np.stack([1 - a - b, a, b], -1)
    xy, z = np.einsum("nk,nkd->nd", w, P[ti]), np.einsum("nk,nk->n", w, Z[ti])
    cx = np.clip(((xy[:, 0] - lo[0]) / cell).astype(int), 0, W - 1)
    cy = np.clip(((xy[:, 1] - lo[1]) / cell).astype(int), 0, H - 1)
    flat = cy * W + cx
    order = np.lexsort((z, flat))
    top = order[np.r_[flat[order][1:] != flat[order][:-1], True]]
    grid = np.full(H * W, -1)
    grid[flat[top]] = owner[ti[top]]
    grid = grid.reshape(H, W)
    seen = {int(k): int(c) for k, c in zip(*np.unique(grid[grid >= 0], return_counts=True))}
    spots, taken = {}, []
    for k in sorted(seen, key=seen.get):  # (the least seen first: they have the least room)
        ys, xs = np.nonzero(grid == k)
        y0, x0 = ys.min(), xs.min()
        mask = np.pad(grid[y0:ys.max() + 1, x0:xs.max() + 1] == k, 1)
        depth, cur = np.zeros(mask.shape), mask
        for _ in range(12):  # how far inside its patch each cell is (cells, up to 12)
            cur = cur & np.roll(cur, 1, 0) & np.roll(cur, -1, 0) & np.roll(cur, 1, 1) & np.roll(cur, -1, 1)
            if not cur.any():
                break
            depth += cur
        gy, gx = np.mgrid[0:mask.shape[0], 0:mask.shape[1]]
        gx, gy = gx + x0 - 1, gy + y0 - 1
        apart = np.full(mask.shape, 40.0)
        for q in taken:
            apart = np.minimum(apart, np.hypot(gx - q[0], gy - q[1]))
        score = np.where(mask, np.minimum(depth, 6) + 0.15 * apart, -1)
        j = np.unravel_index(int(np.argmax(score)), score.shape)
        taken.append((gx[j], gy[j]))
        spots[placed[k][0]] = ([_r(lo[0] + (gx[j] + 0.5) * cell), _r(lo[1] + (gy[j] + 0.5) * cell)], _r(seen[k] * cell ** 2, 1))
    return spots


def value(geo, dim):
    """A dimension's value (mm) from the geometry, or None (its points are gone)."""
    view = geo["views"].get(dim.get("view"))
    if not view:
        return None
    if dim["kind"] in ("dia", "rad"):
        c = next((c for c in view["circles"] if c["key"] == dim["a"]), None)
        return None if c is None else (2 * c["r"] if dim["kind"] == "dia" else c["r"])
    if dim["kind"] == "pcd":  # (a bolt circle's Ø)
        rg = next((r for r in view.get("rings") or () if r["key"] == dim["a"]), None)
        return None if rg is None else 2 * rg["r"]
    a, b = view["points"].get(dim["a"]), view["points"].get(dim["b"])
    if a is None or b is None:
        return None
    return abs(b[0] - a[0]) if dim.get("dir") == "h" else abs(b[1] - a[1]) if dim.get("dir") == "v" else math.dist(a, b)


def pdf(svg) -> bytes:
    """The sheet as the browser drew it (SVG, mm) -> a PDF; several SVGs (a drawing set) -> one PDF, a page each (the
    title-block styles' texts in their own fonts: sheetpdf.py)."""
    from .sheetpdf import pdf as make
    return make(svg)
