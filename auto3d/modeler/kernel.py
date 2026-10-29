"""The CAD kernel: OpenCASCADE through OCP. The ONLY module that imports OCP (see docs/ARCHITECTURE-modeler.md).

Shapes stay inside the worker process (`worker.py`); everything returned to the server is plain data
(numbers, lists, bytes). Sketch coordinates are (u, v) on a plane frame {o, x, n} (origin, x axis,
normal; y = n × x), all in mm.

Faces have names, so later steps keep pointing at the same face when earlier sizes change: "F2:end" (the
top of extrude F2), "F2:start", "F2:side:l3" (the wall made by sketch line l3), "F5:round:0" (a rounding),
"F6:hole:0". A `Body` is a solid plus {name: [faces]}; every operation carries the names over through
OpenCASCADE's history (a face that is cut in two keeps its name on both pieces). An edge is named by the
two faces it joins.
"""
from __future__ import annotations

import contextlib
import math
import os
import re
import tempfile

import numpy as np
import OCP.collections as _C
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import (BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon,
                                BRepBuilderAPI_MakeWire, BRepBuilderAPI_Transform)
from OCP.BRepFilletAPI import BRepFilletAPI_MakeChamfer, BRepFilletAPI_MakeFillet
from OCP.BRepGProp import BRepGProp
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeThickSolid
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism, BRepPrimAPI_MakeRevol
from OCP.BRepTools import BRepTools_WireExplorer
from OCP.GC import GC_MakeArcOfCircle
from OCP.Bnd import Bnd_Box
from OCP.GCPnts import GCPnts_TangentialDeflection
from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Cylinder, GeomAbs_Line, GeomAbs_Plane
from OCP.GProp import GProp_GProps
from OCP.gp import gp_Ax1, gp_Ax2, gp_Circ, gp_Dir, gp_Pln, gp_Pnt, gp_Trsf, gp_Vec
from OCP.IFSelect import IFSelect_RetDone
from OCP.Interface import Interface_Static
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Reader
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_FORWARD, TopAbs_REVERSED, TopAbs_SOLID, TopAbs_VERTEX
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS

ShapeMap = _C.IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher


class KernelError(Exception):
    """A modelling step that cannot be built (shown to the user as the feature's issue)."""


# ------------------------------------------------------------------ booleans (on all cores)
PARALLEL = os.environ.get("A3D_PARALLEL_BOOL", "1").strip().lower() not in ("0", "false", "no", "off")
"""OpenCASCADE's booleans run their intersections on all cores; A3D_PARALLEL_BOOL=0 runs them on one (the results
are the same: tests/test_parallel_bool.py)."""
_BOPS = {"common": BRepAlgoAPI_Common, "cut": BRepAlgoAPI_Cut, "fuse": BRepAlgoAPI_Fuse}


def bop(op, args, tools):
    """args ∩ / − / ∪ tools: op "common" / "cut" / "fuse", args and tools a shape or a list of shapes -> the built
    BRepAlgoAPI operation (IsDone, Shape and its history for _carry). Every boolean of the kernel goes through here."""
    mk = _BOPS[op]()
    a, b = _C.List_TopoDS_Shape(), _C.List_TopoDS_Shape()
    for s in args if isinstance(args, (list, tuple)) else [args]:
        a.Append(s)
    for s in tools if isinstance(tools, (list, tuple)) else [tools]:
        b.Append(s)
    mk.SetArguments(a)
    mk.SetTools(b)
    mk.SetRunParallel(PARALLEL)
    mk.Build()
    return mk


# ------------------------------------------------------------------ frames
def _v(a):
    return np.asarray(a, float)


def frame_y(fr):
    return np.cross(_v(fr["n"]), _v(fr["x"]))


def to_3d(fr, u, v):
    p = _v(fr["o"]) + u * _v(fr["x"]) + v * frame_y(fr)
    return gp_Pnt(*map(float, p))


# ------------------------------------------------------------------ sketch -> faces (with the sketch name of each edge)
def _wire_edges(w):
    ex, out = BRepTools_WireExplorer(w), []
    while ex.More():
        out.append(ex.Current())
        ex.Next()
    return out


def _rect_wire(fr, e):
    hw, hh = e["w"] / 2, e["h"] / 2
    poly = BRepBuilderAPI_MakePolygon()
    for u, v in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)):
        poly.Add(to_3d(fr, e["cx"] + u, e["cy"] + v))
    poly.Close()
    w = poly.Wire()
    return w, [(ed, f"{e.get('id', 'r')}:{i}") for i, ed in enumerate(_wire_edges(w))]


def _circle_wire(fr, e):
    r = e["d"] / 2
    ax = gp_Ax2(to_3d(fr, e["cx"], e["cy"]), gp_Dir(*map(float, fr["n"])), gp_Dir(*map(float, fr["x"])))
    edge = BRepBuilderAPI_MakeEdge(gp_Circ(ax, r)).Edge()
    w = BRepBuilderAPI_MakeWire(edge).Wire()
    return w, [(ed, e.get("id", "c")) for ed in _wire_edges(w)]


def _poly_wire(fr, ring, names):
    poly = BRepBuilderAPI_MakePolygon()
    for u, v in ring:
        poly.Add(to_3d(fr, u, v))
    poly.Close()
    w = poly.Wire()
    return w, list(zip(_wire_edges(w), names))


def arc_points(c, a, b, step_deg=5.0):
    """An arc (centre c, from a counter-clockwise to b; the radius is |a - c|) as points from a to b, on the circle."""
    r = math.hypot(a[0] - c[0], a[1] - c[1])
    t0 = math.atan2(a[1] - c[1], a[0] - c[0])
    sweep = (math.atan2(b[1] - c[1], b[0] - c[0]) - t0) % (2 * math.pi) or 2 * math.pi
    n = max(2, int(math.ceil(math.degrees(sweep) / step_deg)))
    pts = [(c[0] + r * math.cos(t0 + sweep * i / n), c[1] + r * math.sin(t0 + sweep * i / n)) for i in range(n + 1)]
    pts[0], pts[-1] = tuple(a), tuple(b)  # the ends exactly where the sketch points are (they join lines there)
    return pts


def spline_curve(pts3):
    """A smooth curve (B-spline, C2) exactly through points (gp_Pnt) in their order."""
    from OCP.GeomAPI import GeomAPI_Interpolate
    from OCP.collections import HArray1_gp_Pnt
    arr = HArray1_gp_Pnt(1, len(pts3))
    for i, q in enumerate(pts3):
        arr.SetValue(i + 1, q)
    it = GeomAPI_Interpolate(arr, False, 1e-7)
    it.Perform()
    if not it.IsDone():
        raise KernelError("A smooth curve could not go through its points (two of them in one place?).")
    return it.Curve()


def spline_points(pts, per=16):
    """A smooth curve through 2D points -> points along it (for finding the loops), its ends exactly the given ones."""
    c = spline_curve([gp_Pnt(float(x), float(y), 0.0) for x, y in pts])
    u0, u1 = c.FirstParameter(), c.LastParameter()
    n = max(2, per * (len(pts) - 1))
    out = []
    for i in range(n + 1):
        q = c.Value(u0 + (u1 - u0) * i / n)
        out.append((q.X(), q.Y()))
    out[0], out[-1] = tuple(pts[0]), tuple(pts[-1])
    return out


def _spline_edge(fr, pts, a, b):
    """The part of the smooth curve through `pts` (sketch points) between the sketch points a and b -> an edge."""
    from OCP.GeomAPI import GeomAPI_ProjectPointOnCurve
    c = spline_curve([to_3d(fr, *q) for q in pts])
    u = []
    for q in (a, b):
        pj = GeomAPI_ProjectPointOnCurve(to_3d(fr, *q), c)
        u.append(pj.LowerDistanceParameter() if pj.NbPoints() else c.FirstParameter())
    u0, u1 = sorted(u)
    if abs(u1 - u0) < 1e-12:
        u0, u1 = c.FirstParameter(), c.LastParameter()
    return BRepBuilderAPI_MakeEdge(c, u0, u1).Edge()


def _mixed_wire(fr, ring, owners, arcs, splines=None):
    """A closed ring of points whose sides belong to lines, arcs or smooth curves -> a wire of straight edges, true
    circular arcs and B-spline edges (a run of sides on the same arc / curve becomes one edge)."""
    splines = splines or {}
    n = len(ring)
    # start at a side whose owner differs from the one before it, so no run wraps around the end
    s0 = next((i for i in range(n) if owners[i] != owners[i - 1]), 0)
    order = [(s0 + i) % n for i in range(n)]
    mk, names, i = BRepBuilderAPI_MakeWire(), [], 0
    while i < n:
        k = order[i]
        o = owners[k]
        if o in splines:
            j = i
            while j + 1 < n and owners[order[j + 1]] == o:
                j += 1
            edge = _spline_edge(fr, splines[o], ring[order[i]], ring[(order[j] + 1) % n])
            if i == 0 and j == n - 1:  # one closed curve all round: counter-clockwise, as the ring (holes are put in reversed)
                q = spline_points(splines[o], 4)
                if sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(q, q[1:] + q[:1])) < 0:
                    edge = TopoDS.Edge(edge.Reversed())
            i = j + 1
        elif o in arcs:
            j = i
            while j + 1 < n and owners[order[j + 1]] == o:
                j += 1
            run = [ring[order[x]] for x in range(i, j + 1)] + [ring[(order[j] + 1) % n]]
            c, r = arcs[o]
            if len(run) > 2:
                m = run[len(run) // 2]
            else:  # one side: the middle of the arc over it
                mx, my = (run[0][0] + run[1][0]) / 2 - c[0], (run[0][1] + run[1][1]) / 2 - c[1]
                L = math.hypot(mx, my) or 1.0
                m = (c[0] + mx / L * r, c[1] + my / L * r)
            arc = GC_MakeArcOfCircle(to_3d(fr, *run[0]), to_3d(fr, *m), to_3d(fr, *run[-1]))
            edge = BRepBuilderAPI_MakeEdge(arc.Value()).Edge()
            i = j + 1
        else:
            p, q = ring[k], ring[(k + 1) % n]
            edge = BRepBuilderAPI_MakeEdge(to_3d(fr, *p), to_3d(fr, *q)).Edge()
            i += 1
        mk.Add(edge)
        if not mk.IsDone():
            raise KernelError("A sketch shape could not be joined into a closed outline.")
        names.append(o)
    w = mk.Wire()
    return w, list(zip(_wire_edges(w), names))


def face_loops(face, fr, per=24):
    """⬆ A flat face of the part -> its loops (the outer one and its holes) on the sketch plane fr: [(wire, ring)] —
    each wire a copy of the face's edges (moved square onto the plane when the face lies off it), counter-clockwise
    seen along fr's normal; ring its [u, v] points (a straight edge its two ends, a curve `per` points)."""
    from OCP.TopAbs import TopAbs_WIRE
    face = TopoDS.Face(face)
    pl = plane_of(face)
    n = _v(fr["n"])
    if pl is None or abs(abs(float(pl[1] @ n)) - 1) > 1e-6:
        raise KernelError("Its face is not flat and parallel to the sketch any more — pick the face again.")
    t = gp_Trsf()
    t.SetTranslation(gp_Vec(*map(float, -float((pl[0] - _v(fr["o"])) @ n) * n)))
    o, x, y = _v(fr["o"]), _v(fr["x"]), frame_y(fr)
    out = []
    ex = TopExp_Explorer(face, TopAbs_WIRE)
    while ex.More():
        w = TopoDS.Wire(BRepBuilderAPI_Transform(ex.Current(), t, True).Shape())  # (a copy: the part's own edges stay its own)
        ring = []
        for e in _wire_edges(w):
            c = BRepAdaptor_Curve(e)
            k = 1 if c.GetType() == GeomAbs_Line else per
            us = [c.FirstParameter() + (c.LastParameter() - c.FirstParameter()) * i / k for i in range(k + 1)]
            pts = [c.Value(u) for u in us]
            uv = [(float((np.array([q.X(), q.Y(), q.Z()]) - o) @ x), float((np.array([q.X(), q.Y(), q.Z()]) - o) @ y)) for q in pts]
            if e.Orientation() == TopAbs_REVERSED:
                uv.reverse()
            ring += uv[:-1]
        if len(ring) >= 2:
            area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:] + ring[:1]))
            if area < 0:  # (clockwise: a hole's wire, or the face turned away from the sketch)
                w, ring = TopoDS.Wire(w.Reversed()), ring[::-1]
            out.append((w, ring))
        ex.Next()
    if not out:
        raise KernelError("Its face has no outline to use.")
    return out


def _outline(e, n=96):
    if e["t"] == "rect":
        hw, hh = e["w"] / 2, e["h"] / 2
        return [(e["cx"] - hw, e["cy"] - hh), (e["cx"] + hw, e["cy"] - hh), (e["cx"] + hw, e["cy"] + hh), (e["cx"] - hw, e["cy"] + hh)]
    r = e["d"] / 2
    return [(e["cx"] + r * math.cos(a), e["cy"] + r * math.sin(a)) for a in np.linspace(0, 2 * math.pi, n, endpoint=False)]


def _loops(sk):
    """The closed loops of a sketch -> [(shapely polygon for "what is inside what", wire maker -> (wire, [(edge, name)]))].
    Rectangles / circles (first sketches) and connected lines (loops found where lines meet) + circles."""
    from shapely.geometry import LineString, Point, Polygon
    from shapely.geometry.polygon import orient
    from shapely.ops import polygonize, unary_union

    pts = sk.get("points") or {}
    end = lambda i: (0.0, 0.0) if i == "O" else pts.get(i)  # noqa: E731
    loops, segs, lines, arcs, splines = [], [], [], {}, {}
    for e in sk.get("entities") or []:
        if e.get("construction"):
            continue
        t = e.get("t")
        if t == "rect" or (t == "circle" and "c" not in e):  # first-version shapes: own size and centre
            loops.append((Polygon(_outline(e)), lambda fr, e=e: _rect_wire(fr, e) if e["t"] == "rect" else _circle_wire(fr, e)))
        elif t == "circle":
            c = end(e["c"])
            if c is None:
                continue
            ce = {"t": "circle", "cx": c[0], "cy": c[1], "d": 2 * float(e.get("r", 0)), "id": e.get("id")}
            if ce["d"] > 0:
                loops.append((Polygon(_outline(ce)), lambda fr, ce=ce: _circle_wire(fr, ce)))
        elif t == "block":
            # an outline taken from a picture / DXF / PDF part: rigid, placed at `at`, sized by `scale`
            at, k = e.get("at") or (0, 0), float(e.get("scale") or 1)
            ring_no = 0
            for poly in e.get("polys") or []:
                for r in poly:
                    pts2 = [(at[0] + k * x, at[1] + k * y) for x, y in r]
                    if len(pts2) < 3:
                        continue
                    ring = list(orient(Polygon(pts2), 1.0).exterior.coords)[:-1]
                    nm = [f"{e.get('id', 'b')}:{ring_no}:{i}" for i in range(len(ring))]
                    loops.append((Polygon(ring), lambda fr, ring=ring, nm=nm: _poly_wire(fr, ring, nm)))
                    ring_no += 1
        elif t == "outline":
            # ⬆ the outline of a face of the part (its loops found by doc._face_outlines this rebuild): the face's own
            # edges, each named "<id>:<loop>:<k>"
            for j, (w, ring) in enumerate(e.get("_loops") or []):
                loops.append((Polygon(ring), lambda fr, w=w, j=j, i=e.get("id", "o"): (w, [(ed, f"{i}:{j}:{k}") for k, ed in enumerate(_wire_edges(w))])))
        elif t == "arc":
            c, a, b = end(e.get("c")), end(e.get("a")), end(e.get("b"))
            if c is None or a is None or b is None or (a[0] == b[0] and a[1] == b[1]):
                continue
            r = math.hypot(a[0] - c[0], a[1] - c[1])
            if r <= 1e-9:
                continue
            seg = LineString(arc_points(c, a, b))
            segs.append(seg)
            lines.append((seg, e.get("id")))
            arcs[e.get("id")] = (tuple(c), r)
        elif t == "spline":
            # a smooth curve through its points (in order): one B-spline edge in the solid
            P = [end(i) for i in e.get("pts") or []]
            if len(P) < 2 or any(q is None for q in P):
                continue
            P = [tuple(q) for k, q in enumerate(P) if k == 0 or q != P[k - 1]]
            if len(P) < 2:
                continue
            seg = LineString(spline_points(P) if len(P) > 2 else P)
            segs.append(seg)
            lines.append((seg, e.get("id")))
            splines[e.get("id")] = P
        elif t == "line":
            a, b = end(e.get("a")), end(e.get("b"))
            if a is not None and b is not None and (a[0] != b[0] or a[1] != b[1]):
                seg = LineString([a, b])
                segs.append(seg)
                lines.append((seg, e.get("id")))
    if segs:
        for poly in polygonize(unary_union(segs)):
            ring = list(orient(Polygon(poly.exterior), 1.0).exterior.coords)[:-1]  # counter-clockwise, like circles
            if poly.area <= 1e-9:
                continue
            # each side of the loop: the sketch line it lies on (a line split by a crossing keeps its name)
            names = []
            for i, p in enumerate(ring):
                q = ring[(i + 1) % len(ring)]
                mid = Point((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
                hit = next((n for seg, n in lines if seg.distance(mid) < 1e-6), None)
                names.append(hit or f"edge{i}")
            if any(nm in arcs or nm in splines for nm in names):
                loops.append((Polygon(ring), lambda fr, ring=ring, names=names: _mixed_wire(fr, ring, names, arcs, splines)))
            else:
                loops.append((Polygon(ring), lambda fr, ring=ring, names=names: _poly_wire(fr, ring, names)))
    return loops


def sketch_faces(fr, sk):
    """Closed sketch loops -> [(planar face, [(edge, sketch name)])]. A loop inside another one is a hole in
    it; a loop inside a hole is an island again (even-odd), so a circle in a rectangle is a plate with a hole."""
    if isinstance(sk, list):  # just the entities (first-version sketches)
        sk = {"entities": sk}
    for e in sk.get("entities") or []:
        if e.get("t") == "rect" and not (e.get("w", 0) > 0 and e.get("h", 0) > 0):
            raise KernelError("A rectangle needs a width and a height greater than zero.")
        if e.get("t") == "circle" and not ((e.get("d") or 2 * float(e.get("r") or 0)) > 0):
            raise KernelError("A circle needs a diameter greater than zero.")
    loops = _loops(sk)
    if not loops:
        raise KernelError("The sketch has no closed shape to use (draw a rectangle or a circle).")
    polys = [p for p, _ in loops]
    wires = [mk(fr) for _, mk in loops]
    parent, depth = [], []
    for i, p in enumerate(polys):
        cands = [j for j, q in enumerate(polys) if j != i and q.area > p.area and q.buffer(1e-9).contains(p)]
        parent.append(min(cands, key=lambda j: polys[j].area) if cands else None)
    for i in range(len(polys)):
        d, j = 0, parent[i]
        while j is not None:
            d, j = d + 1, parent[j]
        depth.append(d)
    out = []
    for i in range(len(polys)):
        if depth[i] % 2:
            continue
        w, names = wires[i]
        mk = BRepBuilderAPI_MakeFace(w, True)
        names = list(names)
        for k in range(len(polys)):
            if parent[k] == i and depth[k] % 2:
                wk, nk = wires[k]
                wk.Reverse()
                mk.Add(TopoDS.Wire(wk))
                names += nk
        if not mk.IsDone():
            raise KernelError("A sketch shape could not be turned into a face.")
        out.append((mk.Face(), names))
    return out


def circle_face(fr, u, v, d):
    """A round face on a plane frame (for holes) with its edge."""
    w, names = _circle_wire(fr, {"cx": u, "cy": v, "d": d, "id": "c"})
    return BRepBuilderAPI_MakeFace(w, True).Face(), names


def teardrop_face(fr, u, v, d):
    """A teardrop at (u, v) of a plane frame whose normal lies flat (a hole printed sideways): the circle Ø d with its
    top (toward +Z, up on the bed) replaced by a point, its two sides tangent at 45°, so nothing overhangs more than
    45°. Edges named "c" (the round part, 270°) and "t" (the two flat sides)."""
    n = np.asarray(fr["n"], float)
    if abs(n[2]) > 1e-4:
        raise KernelError("A teardrop is for a hole that goes sideways (its axis level with the print bed) — "
                          "this one goes up / down: untick Teardrop.")
    x, y = _v(fr["x"]), frame_y(fr)
    up = np.array([x[2], y[2]], float)
    up /= np.linalg.norm(up)
    side = np.array([up[1], -up[0]])  # (the up direction turned a quarter, in the face's u / v)
    r, c = d / 2, np.array([u, v], float)
    t1, t2 = c + r * (up + side) / math.sqrt(2), c + r * (up - side) / math.sqrt(2)  # where the sides touch the circle
    tip, bottom = c + r * math.sqrt(2) * up, c - r * up
    arc = BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(to_3d(fr, *t1), to_3d(fr, *bottom), to_3d(fr, *t2)).Value()).Edge()
    s2 = BRepBuilderAPI_MakeEdge(to_3d(fr, *t2), to_3d(fr, *tip)).Edge()
    s1 = BRepBuilderAPI_MakeEdge(to_3d(fr, *tip), to_3d(fr, *t1)).Edge()
    w = BRepBuilderAPI_MakeWire(arc, s2, s1).Wire()
    names = [(e, "c" if BRepAdaptor_Curve(e).GetType() == GeomAbs_Circle else "t") for e in _wire_edges(w)]
    return BRepBuilderAPI_MakeFace(w, True).Face(), names


def dflat_face(fr, u, v, d, flat, angle=0.0):
    """A D hole at (u, v) of a plane frame: the circle Ø d with a flat `flat` from the far side (a D-shaft's size across
    the flat), the flat facing the frame's x turned by `angle` degrees. Edges named "c" (the round part) and "f" (the
    flat)."""
    r = d / 2
    a = flat - r  # (the flat's distance from the centre)
    if not r < flat < d:
        raise KernelError(f"The flat of a Ø{d:g} D hole must be between {r:g} and {d:g} across (from the flat to the far side).")
    t = math.radians(float(angle or 0))
    dr, side, c = np.array([math.cos(t), math.sin(t)]), np.array([-math.sin(t), math.cos(t)]), np.array([u, v], float)
    h = math.sqrt(r * r - a * a)
    p1, p2, far = c + a * dr - h * side, c + a * dr + h * side, c - r * dr
    arc = BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(to_3d(fr, *p2), to_3d(fr, *far), to_3d(fr, *p1)).Value()).Edge()
    line = BRepBuilderAPI_MakeEdge(to_3d(fr, *p1), to_3d(fr, *p2)).Edge()
    w = BRepBuilderAPI_MakeWire(arc, line).Wire()
    names = [(e, "c" if BRepAdaptor_Curve(e).GetType() == GeomAbs_Circle else "f") for e in _wire_edges(w)]
    return BRepBuilderAPI_MakeFace(w, True).Face(), names


def countersink(fr, u, v, top_d, d, angle, name):
    """A countersink's cone at (u, v) of a plane frame: Ø top_d at the face narrowing at `angle` (90°: a flat-head
    screw's) into the face, down to Ø d; its cone named `name` (a hair above the face, so it cuts clean)."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCone
    from OCP.GeomAbs import GeomAbs_Cone
    half = math.radians(float(angle)) / 2
    if not 0 < half < math.pi / 2:
        raise KernelError("A countersink's angle is between 0 and 180° (90° for most screws).")
    if top_d <= d:
        raise KernelError("The countersink has to be wider than the hole.")
    h, eps = (top_d - d) / 2 / math.tan(half), 0.01
    n = -np.asarray(fr["n"], float)
    p = to_3d(fr, u, v)
    p0 = gp_Pnt(p.X() - n[0] * eps, p.Y() - n[1] * eps, p.Z() - n[2] * eps)
    mk = BRepPrimAPI_MakeCone(gp_Ax2(p0, gp_Dir(*n)), top_d / 2 + eps * math.tan(half), d / 2, h + eps)
    shape = mk.Shape()
    fm = _face_map(shape)
    cone = [fm.FindKey(i) for i in range(1, fm.Extent() + 1) if BRepAdaptor_Surface(TopoDS.Face(fm.FindKey(i))).GetType() == GeomAbs_Cone]
    return Body(shape, {name: cone})


def material_along(shape, fr, u, v):
    """How deep the part is under (u, v) of a plane frame, into it (along −n) from the face: the length of its first
    piece of solid on that line (a hole's head must stay inside it), or None (no solid there)."""
    p, n = _v(fr["o"]) + u * _v(fr["x"]) + v * frame_y(fr), _v(fr["n"])
    bb = bbox(shape)
    a, b = p + n * 0.01, p - n * (2 * math.dist(bb[:3], bb[3:]) + 10)
    mk = bop("common", shape, BRepBuilderAPI_MakeEdge(gp_Pnt(*map(float, a)), gp_Pnt(*map(float, b))).Edge())
    if not mk.IsDone():
        return None
    segs, ex = [], TopExp_Explorer(mk.Shape(), TopAbs_EDGE)
    while ex.More():  # (the line's pieces inside the solid, as distances from the face)
        c = BRepAdaptor_Curve(TopoDS.Edge(ex.Current()))
        ts = sorted(float((p - _v([q.X(), q.Y(), q.Z()])) @ n) for q in (c.Value(c.FirstParameter()), c.Value(c.LastParameter())))
        segs.append(ts)
        ex.Next()
    segs.sort()
    if not segs or segs[0][0] > 0.05:
        return None
    end = segs[0][1]
    for t0, t1 in segs[1:]:  # (one piece split by an inner face: joined)
        if t0 > end + 1e-6:
            break
        end = max(end, t1)
    return end


def head_room(shape, fr, u, v, d, n=48):
    """Does a hole's head Ø d at (u, v) sit on the face — its rim just under the face inside the part all round? None:
    it does; else the widest Ø that does (halved until it fits, then narrowed down to 0.05 mm)."""
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.TopAbs import TopAbs_IN
    p, xx = _v(fr["o"]) + u * _v(fr["x"]) + v * frame_y(fr) - _v(fr["n"]) * 0.02, _v(fr["x"])  # (just under the face)
    yy = frame_y(fr)
    cl = BRepClass3d_SolidClassifier(shape)

    def inside(r):
        for k in range(n):
            a = 2 * math.pi * k / n
            q = p + r * (math.cos(a) * xx + math.sin(a) * yy)
            cl.Perform(gp_Pnt(*map(float, q)), 1e-6)
            if cl.State() != TopAbs_IN:
                return False
        return True

    if inside(d / 2):
        return None
    lo, hi = 0.0, d / 2
    while hi - lo > 0.025:
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if inside(mid) else (lo, mid)
    return 2 * lo


# ------------------------------------------------------------------ bodies with named faces
class Body:
    """A solid and the names of its faces {name: [faces]}."""

    def __init__(self, shape, names=None):
        self.shape = shape
        self.names = names or {}

    def faces_of(self, name):
        return self.names.get(name, [])


def _face_map(shape):
    m = ShapeMap()
    TopExp.MapShapes_s(shape, TopAbs_FACE, m)
    return m


def _carry(op, names, result):
    """The names of faces after an operation (op has OpenCASCADE's Modified / IsDeleted history)."""
    rm = _face_map(result)
    out = {}
    for n, faces in names.items():
        new = []
        for f in faces:
            mods = op.Modified(f)
            if mods.Size():
                new.extend(m for m in mods if rm.Contains(m))
            elif not op.IsDeleted(f) and rm.Contains(f):
                new.append(f)
        if new:
            out[n] = new
    return out


def prism_body(face, edge_names, vec, fid, start=None):
    """Extrude a face along vec: faces named start / end / side:<sketch name>. start: move it first."""
    if start is not None and np.any(start):
        t = gp_Trsf()
        t.SetTranslation(gp_Vec(*map(float, start)))
        tr = BRepBuilderAPI_Transform(face, t, False)
        face = TopoDS.Face(tr.Shape())
        edge_names = [(tr.ModifiedShape(e), n) for e, n in edge_names]
    mk = BRepPrimAPI_MakePrism(face, gp_Vec(*map(float, vec)), True)
    shape = mk.Shape()
    names = {f"{fid}:start": [mk.FirstShape()], f"{fid}:end": [mk.LastShape()]}
    for e, n in edge_names:
        gen = list(mk.Generated(e))
        if gen:
            names.setdefault(f"{fid}:side:{n}", []).extend(gen)
    return Body(shape, names)


def prism_up_to_next(face, edge_names, u, body, fid, op):
    """Extrude a face along the unit vector u up to the next face of the body its whole profile meets ("up to next"):
    the profile extruded far, then an add keeps what of it is outside the body from the sketch to there (a boss up to
    an overhang), a cut what is inside it (through the first wall only; a sketch off the part: the nearest piece).
    Faces named as prism_body's; its end: the faces of the part it stops at."""
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    if body is None:
        raise KernelError("Up to next: there is no part to go up to yet.")
    bb, fb = bbox(body.shape), bbox(face)
    far = 2 * math.dist([min(a, b) for a, b in zip(bb[:3], fb[:3])], [max(a, b) for a, b in zip(bb[3:], fb[3:])]) + 10
    tool = prism_body(face, edge_names, np.asarray(u, float) * far, fid)
    mk = bop("common" if op == "cut" else "cut", tool.shape, body.shape)
    if not mk.IsDone():
        raise KernelError("The solid operation failed.")
    res = mk.Shape()
    names = _carry(mk, tool.names, res)
    pieces, ex = [], TopExp_Explorer(res, TopAbs_SOLID)
    while ex.More():
        sol = ex.Current()
        dist = BRepExtrema_DistShapeShape(sol, face)
        pieces.append((dist.Value() if dist.IsDone() else math.inf, sol))
        ex.Next()
    near = min((d for d, _ in pieces), default=math.inf)
    keep = [sol for d, sol in pieces if d < 1e-6 or (op == "cut" and d < near + 1e-6)]
    if op != "cut" and not keep:
        raise KernelError("Up to next: that way it goes straight into the part — nothing to fill (⇅ flip its direction).")
    fm = _face_map(compound(keep)) if keep else None
    if not keep or (op != "cut" and any(fm.Contains(f) for f in names.get(f"{fid}:end", []))):
        raise KernelError(f"Up to next: {'the cut meets no part of the part' if op == 'cut' else 'no face of the part is across the whole sketch'} "
                          "that way — ⇅ flip its direction, or extrude a distance.")
    own = {k: [f for f in fs if fm.Contains(f)] for k, fs in names.items() if k != f"{fid}:end"}
    named = ShapeMap()
    for fs in own.values():
        for f in fs:
            named.Add(f)
    shape = keep[0] if len(keep) == 1 else compound(keep)
    ends = [f for f in (fm.FindKey(i) for i in range(1, fm.Extent() + 1)) if not named.Contains(f)]
    return Body(shape, {**{k: fs for k, fs in own.items() if fs}, **({f"{fid}:end": ends} if ends else {})})


def outline_count(face):
    """How many outlines a face has (1 = no holes)."""
    from OCP.TopAbs import TopAbs_WIRE
    ex, n = TopExp_Explorer(face, TopAbs_WIRE), 0
    while ex.More():
        n += 1
        ex.Next()
    return n


def loft_body(sections, fid):
    """A solid through closed profiles, in order: sections [(face, [(edge, name)])] (each one outline, no holes).
    Faces: start (the first profile), end (the last), side:<name of the first profile's edge>."""
    from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
    from OCP.BRepTools import BRepTools
    mk = BRepOffsetAPI_ThruSections(True, False)
    for face, _ in sections:
        mk.AddWire(BRepTools.OuterWire_s(face))
    mk.Build()
    if not mk.IsDone():
        raise KernelError("The loft could not be made — are the profiles one closed outline each, and not crossing?")
    names = {f"{fid}:start": [mk.FirstShape()], f"{fid}:end": [mk.LastShape()]}
    for e, n in sections[0][1]:
        try:
            g = mk.GeneratedFace(e)
        except Exception:  # noqa: BLE001 — an edge with no side of its own (merged): no name for it
            continue
        if not g.IsNull():
            names.setdefault(f"{fid}:side:{n}", []).append(g)
    return Body(mk.Shape(), names)


def sweep_body(face, edge_names, path, fid):
    """A profile (face) swept along a path (a wire); sharp corners of the path are mitred. A profile with holes is
    swept outline by outline and the holes cut out. Faces: start, end, side:<name of the profile's edge>."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_TransitionMode
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell
    from OCP.BRepTools import BRepTools
    from OCP.TopAbs import TopAbs_WIRE

    def pipe(wire, names):
        mk = BRepOffsetAPI_MakePipeShell(path)
        mk.SetTransitionMode(BRepBuilderAPI_TransitionMode.BRepBuilderAPI_RightCorner)
        mk.Add(wire)
        mk.Build()
        if not mk.IsDone() or not mk.MakeSolid():
            raise KernelError("The sweep could not be made — is the profile small enough for the path's bends, and across its start?")
        out = {f"{fid}:start": [mk.FirstShape()], f"{fid}:end": [mk.LastShape()]}
        edges = _wire_edges(wire)
        for e, n in names:
            if any(e.IsSame(x) for x in edges):
                gen = [g for g in mk.Generated(e) if g.ShapeType() == TopAbs_FACE]
                if gen:
                    out.setdefault(f"{fid}:side:{n}", []).extend(gen)
        return Body(mk.Shape(), out)

    outer = BRepTools.OuterWire_s(face)
    body = pipe(outer, edge_names)
    ex = TopExp_Explorer(face, TopAbs_WIRE)
    while ex.More():
        w = TopoDS.Wire(ex.Current())
        if not w.IsSame(outer):
            body = combine(body, pipe(w, edge_names), "cut")
        ex.Next()
    return body


def path_wire(fr, sk):
    """The lines and arcs of a sketch as one connected path (open or closed), in the order they join."""
    pts = sk.get("points") or {}
    P = lambda i: (0.0, 0.0) if i == "O" else pts.get(i)  # noqa: E731
    segs = [e for e in sk.get("entities") or [] if e.get("t") in ("line", "arc") and not e.get("construction")]
    if not segs:
        raise KernelError("The path sketch has no lines or arcs — draw the path with ⟋ Line / ◠ Arc.")
    ends = lambda e: (e["a"], e["b"])  # noqa: E731
    count = {}
    for e in segs:
        for p in ends(e):
            count[p] = count.get(p, 0) + 1
    if any(c > 2 for c in count.values()):
        raise KernelError("The path branches — a path is one line of connected lines and arcs.")
    start = next((p for p, c in count.items() if c == 1), segs[0]["a"])
    left, at, mk = list(segs), start, BRepBuilderAPI_MakeWire()
    while left:
        e = next((x for x in left if at in ends(x)), None)
        if e is None:
            raise KernelError("The path is not connected — its lines and arcs must join end to end.")
        left.remove(e)
        nxt = e["b"] if e["a"] == at else e["a"]
        if e["t"] == "line":
            edge = BRepBuilderAPI_MakeEdge(to_3d(fr, *P(at)), to_3d(fr, *P(nxt))).Edge()
        else:
            c, a, b = P(e["c"]), P(e["a"]), P(e["b"])
            r = math.hypot(a[0] - c[0], a[1] - c[1])
            t0 = math.atan2(a[1] - c[1], a[0] - c[0])
            sweep = (math.atan2(b[1] - c[1], b[0] - c[0]) - t0) % (2 * math.pi) or 2 * math.pi
            m = (c[0] + r * math.cos(t0 + sweep / 2), c[1] + r * math.sin(t0 + sweep / 2))
            edge = BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(to_3d(fr, *a), to_3d(fr, *m), to_3d(fr, *b)).Value()).Edge()
        mk.Add(edge)
        if not mk.IsDone():
            raise KernelError("The path's lines and arcs do not join.")
        at = nxt
    return mk.Wire()


def pipe_body(segments, profiles, fid):
    """🔌 A cable harness (harness.py): profiles swept along a route of lines and arcs. segments [("line", a, b) |
    ("arc", a, m, b)] (points [x, y, z]); profiles at the route's start [("circle", centre, direction, r) | ("rect",
    centre, direction, x, w, h)]. One solid per profile, kept apart in one compound (wires side by side are not fused).
    Faces: <fid>:start, <fid>:end, <fid>:side; several profiles also <fid>:w<k>:start … (each wire's own)."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_TransitionMode
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell

    P = lambda p: gp_Pnt(*map(float, p))  # noqa: E731
    mk = BRepBuilderAPI_MakeWire()
    for s in segments:
        mk.Add(BRepBuilderAPI_MakeEdge(P(s[1]), P(s[2])).Edge() if s[0] == "line"
               else BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(P(s[1]), P(s[2]), P(s[3])).Value()).Edge())
        if not mk.IsDone():
            raise KernelError("The harness's route does not join up.")
    path = mk.Wire()
    solids, names = [], {}
    for pr in profiles:
        if pr[0] == "circle":
            prof = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(P(pr[1]), gp_Dir(*map(float, pr[2]))), float(pr[3]))).Edge()).Wire()
        else:
            c, t, x = (np.asarray(v, float) for v in pr[1:4])
            w, h = float(pr[4]), float(pr[5])
            y = np.cross(t, x)
            poly = BRepBuilderAPI_MakePolygon()
            for u, v in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
                poly.Add(P(c + x * u + y * v))
            poly.Close()
            prof = poly.Wire()
        pipe = BRepOffsetAPI_MakePipeShell(path)
        pipe.SetTransitionMode(BRepBuilderAPI_TransitionMode.BRepBuilderAPI_RightCorner)
        pipe.Add(prof)
        pipe.Build()
        if not pipe.IsDone() or not pipe.MakeSolid():
            raise KernelError("The harness could not be made solid — are its bends wide enough for its Ø?")
        side = [g for e in _wire_edges(prof) for g in pipe.Generated(e) if g.ShapeType() == TopAbs_FACE]
        for pre in [fid] + ([f"{fid}:w{len(solids)}"] if len(profiles) > 1 else []):  # (a wire's own: its colour)
            names.setdefault(f"{pre}:start", []).append(pipe.FirstShape())
            names.setdefault(f"{pre}:end", []).append(pipe.LastShape())
            names.setdefault(f"{pre}:side", []).extend(side)
        solids.append(pipe.Shape())
    return Body(solids[0] if len(solids) == 1 else compound(solids), names)


def revolve_body(face, edge_names, origin, direction, angle_deg, fid):
    """Spin a face around an axis: faces named side:<sketch name> (and start / end when not a full turn)."""
    full = abs(angle_deg) >= 360 - 1e-9
    ax = gp_Ax1(gp_Pnt(*map(float, origin)), gp_Dir(*map(float, direction)))
    mk = BRepPrimAPI_MakeRevol(face, ax, math.radians(360 if full else angle_deg), True)
    mk.Build()
    if not mk.IsDone():
        raise KernelError("The shape could not be revolved.")
    names = {}
    if not full:
        names[f"{fid}:start"] = [mk.FirstShape()]
        names[f"{fid}:end"] = [mk.LastShape()]
    for e, n in edge_names:
        gen = list(mk.Generated(e))
        if gen:
            names.setdefault(f"{fid}:side:{n}", []).extend(gen)
    return Body(mk.Shape(), names)


def moved_body(body, prefix, shift=None, axis=None, angle_deg=0.0):
    """A copy of a body moved by shift (mm) or turned about axis (origin, direction) by angle_deg; its face
    names get prefix ("F7:2:" + "F3:hole:0")."""
    t = gp_Trsf()
    if axis is not None:
        o, d = axis
        t.SetRotation(gp_Ax1(gp_Pnt(*map(float, o)), gp_Dir(*map(float, d))), math.radians(angle_deg))
    else:
        t.SetTranslation(gp_Vec(*map(float, shift)))
    tr = BRepBuilderAPI_Transform(body.shape, t, True)
    names = {f"{prefix}{n}": [tr.ModifiedShape(f) for f in fs] for n, fs in body.names.items()}
    return Body(tr.Shape(), names)


def mirrored_body(body, prefix, o, n):
    """A copy of a body mirrored across the plane through o with normal n; its face names get prefix."""
    t = gp_Trsf()
    t.SetMirror(gp_Ax2(gp_Pnt(*map(float, o)), gp_Dir(*map(float, n))))
    tr = BRepBuilderAPI_Transform(body.shape, t, True)
    names = {f"{prefix}{n_}": [tr.ModifiedShape(f) for f in fs] for n_, fs in body.names.items()}
    return Body(tr.Shape(), names)


def find_faces(body, refs):
    """Face references {name, fp} -> the faces now (the nearest one of that name to where it was)."""
    out = []
    for ref in refs:
        cands = body.faces_of(ref.get("name"))
        if not cands:
            raise KernelError("A face it uses is no longer there — change this step and pick the faces again.")
        fp = np.asarray(ref.get("fp") or [0, 0, 0], float)

        def dist(f):
            p = GProp_GProps()
            BRepGProp.SurfaceProperties_s(TopoDS.Face(f), p)
            c = p.CentreOfMass()
            return np.linalg.norm(np.array([c.X(), c.Y(), c.Z()]) - fp)
        f = min(cands, key=dist)
        if not any(f.IsSame(u) for u in out):
            out.append(f)
    return out


def shell(body, faces, t, fid):
    """Hollow the body out to walls of thickness t, open at the given faces; inner walls named inner:k."""
    if not t > 0:
        raise KernelError("The wall thickness must be greater than zero.")
    if not faces:
        raise KernelError("Click the face(s) to leave open (e.g. the top of a cup).")
    bb = bbox(body.shape)
    if bb and 2 * t >= min(bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2]) - 1e-9:
        raise KernelError("The wall is too thick for this part — at most half its smallest size.")
    lst = _C.List_TopoDS_Shape()
    for f in faces:
        lst.Append(f)
    mk = BRepOffsetAPI_MakeThickSolid()
    try:
        mk.MakeThickSolidByJoin(body.shape, lst, -float(t), 1e-3)
        mk.Build()
        ok = mk.IsDone()
    except Exception:  # noqa: BLE001 — OpenCASCADE throws when the walls cannot be made
        ok = False
    if not ok:
        raise KernelError("The walls could not be made this thick here — try a thinner wall.")
    res = mk.Shape()
    v0, v1 = volume(body.shape), volume(res)
    if not (0 < v1 < v0):
        raise KernelError("The walls could not be made this thick here — try a thinner wall.")
    names = _carry(mk, body.names, res)
    rm = _face_map(res)
    k = 0
    for fs in body.names.values():
        for f in fs:
            for g in mk.Generated(f):
                if rm.Contains(g):
                    names.setdefault(f"{fid}:inner:{k}", []).append(g)
                    k += 1
    return Body(res, names)


def _centroid(face):
    """A face's centre (of its area) -> (x, y, z)."""
    p = GProp_GProps()
    BRepGProp.SurfaceProperties_s(TopoDS.Face(face), p)
    c = p.CentreOfMass()
    return c.X(), c.Y(), c.Z()


def draft(body, of, angle, fid):
    """Tilt the side walls of step `of` (its faces named of:side…) by `angle` degrees about the plane of its start face:
    they lean in going away from it (a mould's draft; negative: out). The walls keep their names."""
    from OCP.BRepOffsetAPI import BRepOffsetAPI_DraftAngle
    a = float(angle)
    if not 0 < abs(a) < 45:
        raise KernelError("A draft angle is between 0 and 45°.")
    sides = [f for n, fs in body.names.items() if n.startswith(f"{of}:side") for f in fs]
    start, end = (body.names.get(f"{of}:start") or [None])[0], (body.names.get(f"{of}:end") or [None])[0]
    if not sides or start is None:
        raise KernelError("Draft tilts the side walls of an extrude — that extrude's walls are not on the part (any more).")
    s = BRepAdaptor_Surface(TopoDS.Face(start))
    if s.GetType() != GeomAbs_Plane:
        raise KernelError("Draft needs the extrude's start face flat.")
    pln = s.Plane()
    c0 = np.asarray(_centroid(start), float)
    c1 = np.asarray(_centroid(end), float) if end is not None else c0 + np.asarray([pln.Axis().Direction().X(), pln.Axis().Direction().Y(), pln.Axis().Direction().Z()])
    pull = c1 - c0
    if np.linalg.norm(pull) < 1e-9:
        raise KernelError("Draft: the extrude has no height.")
    pull /= np.linalg.norm(pull)
    mk = BRepOffsetAPI_DraftAngle(body.shape)
    for f in sides:
        mk.Add(TopoDS.Face(f), gp_Dir(*pull), math.radians(a), pln, True)
        if not mk.AddDone():
            raise KernelError("This wall cannot be tilted (it is not straight along the extrude, or is rounded already) — draft before rounding the edges.")
    try:
        mk.Build()
        ok = mk.IsDone()
    except Exception:  # noqa: BLE001 — OpenCASCADE throws when the walls cannot be tilted
        ok = False
    if not ok:
        raise KernelError("The walls could not be tilted by that angle here — try a smaller angle, or draft before rounding the edges.")
    res = mk.Shape()
    # (a tilted wall is not in Modified's history — ModifiedShape has every face, tilted or not)
    rm, names = _face_map(res), {}
    for n, fs in body.names.items():
        new = []
        for f in fs:
            try:
                g = mk.ModifiedShape(f)
            except Exception:  # noqa: BLE001 — a face the draft did not see
                continue
            if rm.Contains(g):
                new.append(g)
        if new:
            names[n] = new
    return Body(res, names)


def open_chain(sk):
    """The straight lines of a sketch (not construction) as one open chain of points [(u, v)…] and their ids."""
    pts = sk.get("points") or {}
    P = lambda i: (0.0, 0.0) if i == "O" else tuple(map(float, pts.get(i)))  # noqa: E731
    segs = [e for e in sk.get("entities") or [] if e.get("t") == "line" and not e.get("construction")]
    if not segs:
        raise KernelError("A rib needs a line in its sketch — draw where its edge goes (e.g. from the wall to the plate).")
    count = {}
    for e in segs:
        for p in (e["a"], e["b"]):
            count[p] = count.get(p, 0) + 1
    if any(c > 2 for c in count.values()) or not any(c == 1 for c in count.values()):
        raise KernelError("A rib's lines are one open line (or lines joined end to end, not closed).")
    at = next(p for p, c in count.items() if c == 1)
    left, chain, ids = list(segs), [P(at)], []
    while left:
        e = next((x for x in left if at in (x["a"], x["b"])), None)
        if e is None:
            raise KernelError("A rib's lines have to join end to end.")
        left.remove(e)
        at = e["b"] if e["a"] == at else e["a"]
        chain.append(P(at))
        ids.append(e.get("id", "l"))
    return chain, ids


def rib(body, fr, chain, ids, t, fid, flip=False):
    """A rib: the open line `chain` (sketch coordinates) filled up to the part on whichever side it closes against
    it (both do — a chord across a bore —: the smaller piece; flip: the other side's), `t` thick about the sketch plane
    -> the rib alone (a Body, to add). Faces: fid:start / fid:end (its two flat sides), fid:side:<line id> (its edge
    along the line)."""
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.TopAbs import TopAbs_IN
    if body is None:
        raise KernelError("A rib goes onto a part — make the part first.")
    if not t > 0:
        raise KernelError("A rib's thickness is more than 0.")
    bb = bbox(body.shape)
    D = 2 * math.dist(bb[:3], bb[3:]) + 10
    a, b = np.asarray(chain[0]), np.asarray(chain[-1])
    ch = b - a
    if np.linalg.norm(ch) < 1e-9:
        raise KernelError("A rib's line has no length.")
    nrm = np.array([-ch[1], ch[0]]) / np.linalg.norm(ch)
    n = np.asarray(fr["n"], float)
    best = {}  # side -> (volume, the rib that way)
    for side in (1, -1):
        d = nrm * side * D
        ring = [tuple(p) for p in chain] + [tuple(b + d), tuple(a + d)]
        w, en = _poly_wire(fr, ring, list(ids) + ["far_b", "far", "far_a"])
        tool = prism_body(BRepBuilderAPI_MakeFace(w, True).Face(), en, n * t, fid, start=-n * t / 2)
        mk = bop("cut", tool.shape, body.shape)
        if not mk.IsDone():
            continue
        res = mk.Shape()
        names = _carry(mk, tool.names, res)
        m0 = (np.asarray(chain[0]) + np.asarray(chain[1])) / 2
        probe = m0 + nrm * side * min(0.05, t / 4)  # (just off the line, in the rib)
        ex = TopExp_Explorer(res, TopAbs_SOLID)
        while ex.More():
            sol = ex.Current()
            cl = BRepClass3d_SolidClassifier(sol, to_3d(fr, *probe), 1e-6)
            if cl.State() == TopAbs_IN:
                sb = bbox(sol)
                corners = np.array([[x, y, z] for x in (sb[0], sb[3]) for y in (sb[1], sb[4]) for z in (sb[2], sb[5])])
                o = np.array([to_3d(fr, *a).X(), to_3d(fr, *a).Y(), to_3d(fr, *a).Z()])
                d3 = np.array([to_3d(fr, *(a + nrm * side)).X(), to_3d(fr, *(a + nrm * side)).Y(), to_3d(fr, *(a + nrm * side)).Z()]) - o
                if max((corners - o) @ d3) < 0.9 * D:  # (it closes against the part — not out to the far side)
                    fm = _face_map(sol)
                    own = {k: [f for f in fs if fm.Contains(f)] for k, fs in names.items()}
                    v = volume(sol)
                    if side not in best or v < best[side][0]:
                        best[side] = (v, Body(sol, {k: fs for k, fs in own.items() if fs}))
                break
            ex.Next()
    if not best:
        raise KernelError("The rib does not close against the part — draw its line with the part on one side (e.g. from the wall to the plate), its ends touching the part.")
    auto = min(best, key=lambda k: best[k][0])
    if flip:
        if -auto not in best:
            raise KernelError("On the other side of the line the rib does not close against the part — ⇅ flip it back.")
        return best[-auto][1]
    return best[auto][1]


def split(body, o, n, fid, keep="both"):
    """✂ Cut a body in two along the plane through o with normal n: keep "above" (the side n points to), "below", or
    "both" (the two pieces as separate solids of one body). Each piece keeps its faces' names; the new flat faces are
    fid:cut:0 (on the piece above) and fid:cut:1 (below). A plane that does not cross the part raises."""
    if keep not in ("both", "above", "below"):
        raise KernelError("keep: \"both\", \"above\" (the side the plane's normal points to) or \"below\".")
    o, n = _v(o), _v(n) / np.linalg.norm(_v(n))
    bb = bbox(body.shape)
    D = 2 * math.dist(bb[:3], bb[3:]) + 10
    c = (_v(bb[:3]) + _v(bb[3:])) / 2
    c = c - ((c - o) @ n) * n  # (the middle of the part seen square onto the plane)
    fr = {"o": c, "x": _v([1, 0, 0]) if abs(n[0]) < 0.9 else _v([0, 1, 0]), "n": n}
    fr["x"] = fr["x"] - (fr["x"] @ n) * n
    fr["x"] /= np.linalg.norm(fr["x"])
    w, _ = _poly_wire(fr, [(-D, -D), (D, -D), (D, D), (-D, D)], ["s0", "s1", "s2", "s3"])
    half = prism_body(BRepBuilderAPI_MakeFace(w, True).Face(), [], n * D, fid)  # everything above the plane
    total = volume(body.shape)
    pieces = []
    for k, op in enumerate(("common", "cut")):
        mk = bop(op, body.shape, half.shape)
        if not mk.IsDone():
            raise KernelError("The part could not be split here.")
        res = mk.Shape()
        names = _carry(mk, body.names, res)
        cut = _carry(mk, {f"{fid}:cut:{k}": half.faces_of(f"{fid}:start")}, res)
        names.update(cut)
        pieces.append((Body(res, names), volume(res)))
    if min(v for _, v in pieces) <= 1e-7 * (1 + total):
        raise KernelError("The plane does not cross the part — move it (Offset), or pick a plane or face through the part.")
    if keep == "above":
        return pieces[0][0]
    if keep == "below":
        return pieces[1][0]
    shapes, names = [], {}
    for b, _ in pieces:
        ex = TopExp_Explorer(b.shape, TopAbs_SOLID)
        while ex.More():
            shapes.append(ex.Current())
            ex.Next()
        for k, fs in b.names.items():
            names.setdefault(k, []).extend(fs)
    return Body(compound(shapes), names)


# ------------------------------------------------------------------ 🔩 real threads in threaded holes
_thread_tools: dict = {}  # (major, minor, pitch, length) -> the groove's solid (built once: 8 holes of one size share it)
TAN30 = math.tan(math.radians(30))


def thread_reach(major, minor, pitch):
    """How far the groove's profile reaches along the axis either side of its helix: half its width at its inner end (a
    hair inside the tap drill: 0.1 × pitch, so the cut leaves no sliver)."""
    return (pitch / 8 + 2 * (major / 2 - (minor / 2 - 0.1 * pitch)) * TAN30) / 2


def thread_tool(major, minor, pitch, length):
    """An internal ISO metric thread's groove (the basic profile of ISO 68-1: 60° flanks, P/8 flat at the major Ø) as a
    solid along +z: its trapezoid (from a hair inside the tap drill Ø minor out to Ø major) swept along a right-hand
    helix of `pitch` from z = 0 to `length`, the profile kept in the axis's plane (a fixed binormal). The helix is one
    edge a turn — a cut of one long helical face with the hole's cylinder fails (OCCT finds no intersection)."""
    from OCP.BRepLib import BRepLib
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell
    from OCP.Geom import Geom_CylindricalSurface
    from OCP.Geom2d import Geom2d_Line
    from OCP.GeomAbs import GeomAbs_C2
    from OCP.gp import gp_Ax3, gp_Dir2d, gp_Pnt2d
    key = tuple(round(float(v), 4) for v in (major, minor, pitch, length))
    if key in _thread_tools:
        return _thread_tools[key]
    R, r0 = major / 2, minor / 2 - 0.1 * pitch
    if not 0 < r0 < R or length <= 0:
        raise KernelError("This thread does not fit its hole.")
    half = thread_reach(major, minor, pitch)
    surf = Geom_CylindricalSurface(gp_Ax3(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), R)
    line = Geom2d_Line(gp_Pnt2d(0, 0), gp_Dir2d(2 * math.pi, pitch))  # (u: the angle, v: the height)
    per_turn, turns = math.hypot(2 * math.pi, pitch), length / pitch
    spine = BRepBuilderAPI_MakeWire()
    for k in range(math.ceil(turns - 1e-9)):
        e = BRepBuilderAPI_MakeEdge(line, surf, k * per_turn, min(k + 1, turns) * per_turn).Edge()
        BRepLib.BuildCurves3d_s(e, 1e-6, GeomAbs_C2, 9, 200)
        spine.Add(e)
    poly = BRepBuilderAPI_MakePolygon()
    for r, z in ((r0, -half), (R, -pitch / 16), (R, pitch / 16), (r0, half)):
        poly.Add(gp_Pnt(r, 0, z))
    poly.Close()
    mk = BRepOffsetAPI_MakePipeShell(spine.Wire())
    mk.SetMode(gp_Dir(0, 0, 1))
    mk.Add(poly.Wire(), False, False)
    mk.Build()
    if not mk.IsDone() or not mk.MakeSolid():
        raise KernelError("The thread could not be built.")
    shape = mk.Shape()
    if len(_thread_tools) > 32:
        _thread_tools.clear()
    _thread_tools[key] = shape
    return shape


def along(shape, at, axis):
    """A shape built along +z from the origin, put at `at` along `axis` (a location, not a copy)."""
    from OCP.gp import gp_Ax3
    a = _v(axis) / np.linalg.norm(_v(axis))
    t = gp_Trsf()
    t.SetDisplacement(gp_Ax3(), gp_Ax3(gp_Pnt(*map(float, at)), gp_Dir(*map(float, a))))
    return shape.Moved(TopLoc_Location(t))


def round_span(shape, faces, n=None):
    """A hole's wall (round faces of one axis, maybe in pieces) -> {at, axis, depth, r, open: [entry, far end]}: where
    it starts (on the axis, at its entry: an open end — of two, the one n points to), its unit direction into the part,
    how long it is and its radius; or None (not round). Open: on the axis just past that end is not inside the part."""
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.TopAbs import TopAbs_IN
    ax = face_axis(faces[0])
    s = BRepAdaptor_Surface(TopoDS.Face(faces[0]), True)
    if ax is None or s.GetType() != GeomAbs_Cylinder:
        return None
    p, d = ax
    x = np.cross(d, [1, 0, 0] if abs(d[0]) < 0.9 else [0, 1, 0])
    x /= np.linalg.norm(x)
    y = np.cross(d, x)
    t, b = gp_Trsf(), Bnd_Box()
    t.SetValues(*x, -float(x @ p), *y, -float(y @ p), *d, -float(d @ p))  # world -> along the axis (w)
    for face in faces:
        BRepBndLib.AddOptimal_s(face.Moved(TopLoc_Location(t)), b, False, False)
    w0, w1 = b.CornerMin().Z(), b.CornerMax().Z()
    cl = BRepClass3d_SolidClassifier(shape)
    opened = []
    for w in (w0 - 0.05, w1 + 0.05):
        cl.Perform(gp_Pnt(*map(float, p + w * d)), 1e-6)
        opened.append(cl.State() != TopAbs_IN)
    if opened[1] and (not opened[0] or (n is not None and d @ _v(n) > 0)):  # (the entry at w1: going in along −d)
        return {"at": p + w1 * d, "axis": -d, "depth": w1 - w0, "r": s.Cylinder().Radius(), "open": opened[::-1]}
    return {"at": p + w0 * d, "axis": d, "depth": w1 - w0, "r": s.Cylinder().Radius(), "open": opened}


def cut_threads(body, tools):
    """body − thread solids [(shape, name)] in one cut: the body's names carried (a hole's wall, cut into strips, keeps
    its name: a rounding on its rim still finds it), each thread's faces named `name`."""
    mk = bop("cut", body.shape, [s for s, _ in tools])  # (in parallel: 8 holes M6 × 12 4.6 -> 1.5 s)
    if not mk.IsDone():
        raise KernelError("The threads could not be cut.")
    res = mk.Shape()
    names = _carry(mk, body.names, res)
    for s, name in tools:
        fm = _face_map(s)
        for n, fs in _carry(mk, {name: [fm.FindKey(i) for i in range(1, fm.Extent() + 1)]}, res).items():
            names.setdefault(n, []).extend(fs)
    out = Body(res, names)
    out.plain, out.grooves = body.shape, sorted({name for _, name in tools})  # (for its mesh: tessellate)
    return out


# ------------------------------------------------------------------ printing: exact pieces (printsplit.py)
def transformed(shape, m, shift=(0, 0, 0)):
    """A copy of a shape mapped by x -> m x + shift: m a 3 x 3 rotation / mirror times a uniform scale (mm)."""
    m, t = np.asarray(m, float), gp_Trsf()
    t.SetValues(*m[0], float(shift[0]), *m[1], float(shift[1]), *m[2], float(shift[2]))
    return BRepBuilderAPI_Transform(shape, t, True).Shape()


def prisms(polys, z0, z1):
    """Vertical prisms from z0 to z1 of polygons [[outer ring, hole ring …], …] on the XY plane (rings of (x, y) in mm,
    the outer ones counter-clockwise, the holes clockwise, as shapely's orient gives them) -> [solid]."""
    from OCP.gp import gp_Pln
    out, pln = [], gp_Pln(gp_Pnt(0, 0, float(z0)), gp_Dir(0, 0, 1))
    for rings in polys:
        mk = None
        for ring in rings:
            poly = BRepBuilderAPI_MakePolygon()
            for x, y in ring:
                poly.Add(gp_Pnt(float(x), float(y), float(z0)))
            poly.Close()
            if not poly.IsDone():
                continue
            if mk is None:
                mk = BRepBuilderAPI_MakeFace(pln, poly.Wire(), True)
            else:
                mk.Add(poly.Wire())
        if mk is not None and mk.IsDone():
            out.append(BRepPrimAPI_MakePrism(mk.Face(), gp_Vec(0, 0, float(z1 - z0)), True).Shape())
    return out


def boolean(op, objects, tools):
    """objects ∩ / − / ∪ tools ("common", "cut", "fuse") — each a list of shapes, the tools may overlap each other."""
    mk = bop(op, list(objects), list(tools))
    if not mk.IsDone():
        raise KernelError("The part could not be cut into pieces here.")
    return mk.Shape()


def unified(shape):
    """Faces of one plane / cylinder side by side merged into one (a cut leaves no seams on a wall)."""
    return _unify(Body(shape)).shape


def turned_over(shape):
    """Turned upside down: 180° about the x axis (a piece whose pockets must open upwards)."""
    t = gp_Trsf()
    t.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(1, 0, 0)), math.pi)
    return BRepBuilderAPI_Transform(shape, t, True).Shape()


def print_triangles(shape, tol=0.01, angle=0.2):
    """Fine triangles (n, 3, 3) of a shape for printing: no chord further than tol (mm) from the true surface."""
    from OCP.BRepTools import BRepTools
    BRepTools.Clean_s(shape)
    BRepMesh_IncrementalMesh(shape, float(tol), False, float(angle), True)
    fm = _face_map(shape)
    tris = [_face_triangles(TopoDS.Face(fm.FindKey(i))) for i in range(1, fm.Extent() + 1)]
    return np.concatenate(tris) if tris else np.zeros((0, 3, 3))


def view_triangles(shape, tol):
    """Coarse triangles (n, 3, 3) of a shape as placed, for what a view sees of it (a finer mesh it has is kept, not
    cleaned away as print_triangles does)."""
    BRepMesh_IncrementalMesh(shape, float(tol), False, 0.5, True)
    fm = _face_map(shape)
    tris = [_face_triangles(TopoDS.Face(fm.FindKey(i))) for i in range(1, fm.Extent() + 1)]
    return np.concatenate(tris) if tris else np.zeros((0, 3, 3))


def combine(body, tool, op):
    """body ∪ tool or body − tool, names of both carried over."""
    if body is None:
        if op == "cut":
            raise KernelError("There is nothing to cut yet — make the first extrude “Add material”.")
        return tool
    mk = bop("cut" if op == "cut" else "fuse", body.shape, tool.shape)
    if not mk.IsDone():
        raise KernelError("The solid operation failed.")
    res = mk.Shape()
    names = _carry(mk, body.names, res)
    for n, fs in _carry(mk, tool.names, res).items():
        names.setdefault(n, []).extend(fs)
    return _unify(Body(res, names))


def _unify(body):
    """Faces of one plane (or one cylinder) side by side merged into one — a wall flush with the plate it stands on is
    one face, with the names of both (no seam, no two faces of one name)."""
    from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
    u = ShapeUpgrade_UnifySameDomain(body.shape, True, True, False)
    u.Build()
    res, h = u.Shape(), u.History()
    rm, out = _face_map(res), {}
    for n, faces in body.names.items():
        idx = []
        for f in faces:
            mods = h.Modified(f)
            got = list(mods) if mods.Size() else ([] if h.IsRemoved(f) else [f])
            idx.extend(i for i in (rm.FindIndex(g) for g in got) if i and i not in idx)
        if idx:
            out[n] = [rm.FindKey(i) for i in idx]
    return Body(res, out)


def _edges_of(shape):
    em = ShapeMap()
    TopExp.MapShapes_s(shape, TopAbs_EDGE, em)
    return em


def _adjacency(shape):
    """edge index (1-based in the edge map) -> face indices (0-based in the face map)."""
    fm, em = _face_map(shape), _edges_of(shape)
    adj = {}
    for i in range(1, fm.Extent() + 1):
        ex = TopExp_Explorer(fm.FindKey(i), TopAbs_EDGE)
        while ex.More():
            adj.setdefault(em.FindIndex(ex.Current()), set()).add(i - 1)
            ex.Next()
    return fm, em, adj


def _face_names(body, fm):
    """face index (0-based) -> its names."""
    out = {}
    for n, faces in body.names.items():
        for f in faces:
            i = fm.FindIndex(f)
            if i:
                out.setdefault(i - 1, []).append(n)
    return out


def _edge_mid(e):
    c = BRepAdaptor_Curve(e)
    p = c.Value((c.FirstParameter() + c.LastParameter()) / 2)
    return np.array([p.X(), p.Y(), p.Z()])


def find_edges(body, refs):
    """Edge references {a, b, fp} (the names of the two faces it joins, and its middle point) -> the edges now,
    and how many were found again only by their position (a warning)."""
    fm, em, adj = _adjacency(body.shape)
    names = _face_names(body, fm)
    bb = bbox(body.shape) or [0, 0, 0, 1, 1, 1]
    size = max(bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2], 1e-6)
    mids = {ei: _edge_mid(TopoDS.Edge(em.FindKey(ei))) for ei in adj}
    out, guessed = [], 0
    for ref in refs:
        fp = np.asarray(ref.get("fp") or [0, 0, 0], float)
        cands = []
        for ei, fs in adj.items():
            fl = list(fs)
            if len(fl) != 2:
                continue
            na, nb = set(names.get(fl[0], [])), set(names.get(fl[1], []))
            if (ref.get("a") in na and ref.get("b") in nb) or (ref.get("a") in nb and ref.get("b") in na):
                cands.append(ei)
        if not cands:  # not by name: the nearest edge to where it was, if close
            guessed += 1
            cands = list(adj)
            best = min(cands, key=lambda ei: np.linalg.norm(mids[ei] - fp))
            if np.linalg.norm(mids[best] - fp) > size * 0.05:
                raise KernelError("An edge it uses is no longer there — change this step and pick the edges again.")
        else:
            best = min(cands, key=lambda ei: np.linalg.norm(mids[ei] - fp))
        e = TopoDS.Edge(em.FindKey(best))
        if not any(e.IsSame(u) for u in out):  # two references to one edge count once
            out.append(e)
    return out, guessed


def edge_ends(e):
    """The two end points of an edge (numpy, mm)."""
    c = BRepAdaptor_Curve(e)
    p, q = c.Value(c.FirstParameter()), c.Value(c.LastParameter())
    return np.array([p.X(), p.Y(), p.Z()]), np.array([q.X(), q.Y(), q.Z()])


def edge_centre(e):
    """The centre of a round edge (a circle or an arc), or None for any other edge."""
    from OCP.GeomAbs import GeomAbs_Circle
    c = BRepAdaptor_Curve(e)
    if c.GetType() != GeomAbs_Circle:
        return None
    p = c.Circle().Location()
    return np.array([p.X(), p.Y(), p.Z()])


def find_vertex(body, faces, fp):
    """A corner of the part named by the faces that meet there (e.g. the top and two walls of a box) and where it
    was -> its position now. -> (point, guessed): guessed when no corner has all those faces any more."""
    vm = _C.IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher()
    TopExp.MapShapesAndAncestors_s(body.shape, TopAbs_VERTEX, TopAbs_FACE, vm)
    fm = _face_map(body.shape)
    names = _face_names(body, fm)
    want, fp = set(faces or []), np.asarray(fp or [0, 0, 0], float)
    scored = []
    for i in range(1, vm.Extent() + 1):
        v = TopoDS.Vertex(vm.FindKey(i))
        p = BRep_Tool.Pnt_s(v)
        pt = np.array([p.X(), p.Y(), p.Z()])
        have = set()
        for f in vm.FindFromIndex(i):
            have.update(names.get(fm.FindIndex(f) - 1, []))
        scored.append((len(want & have), -np.linalg.norm(pt - fp), pt))
    if not scored:
        raise KernelError("The part has no corners to measure from.")
    full = [s for s in scored if s[0] == len(want) and want]
    best = max(full or scored, key=lambda s: (s[0], s[1]))
    return best[2], not full


def round_edges(body, edges, r, fid, chamfer=False):
    """Fillet (round) or chamfer (bevel) edges; the new faces are named round:k / bevel:k."""
    if not r > 0:
        raise KernelError("The size must be greater than zero.")
    if not edges:
        raise KernelError("Pick at least one edge.")
    mk = BRepFilletAPI_MakeChamfer(body.shape) if chamfer else BRepFilletAPI_MakeFillet(body.shape)
    for e in edges:
        mk.Add(float(r), e)
    try:
        mk.Build()
        ok = mk.IsDone()
    except Exception:  # noqa: BLE001 — OpenCASCADE throws on impossible roundings
        ok = False
    if not ok:
        raise KernelError(f"{'This bevel' if chamfer else 'This rounding'} does not fit (too big for the edges or faces next to it) — try a smaller size.")
    res = mk.Shape()
    names = _carry(mk, body.names, res)
    kind = "bevel" if chamfer else "round"
    rm, done = _face_map(res), set()
    for k, e in enumerate(edges):  # (OpenCASCADE rounds the whole tangent chain of an edge: its faces all get the name)
        for x in _run(mk, e):
            for f in mk.Generated(x):
                i = rm.FindIndex(f)
                if i and i not in done:
                    done.add(i)
                    names.setdefault(f"{fid}:{kind}:{k}", []).append(f)
    return Body(res, names)


def _run(mk, e):
    """The edges a fillet / chamfer builder rounds for edge e: its contour — e and the edges that go on smoothly
    (tangent) from it."""
    ic = mk.Contour(e)
    return [mk.Edge(ic, j) for j in range(1, mk.NbEdges(ic) + 1)] if ic else [e]


def tangent_chains(shape, em=None, adj=None, skip=frozenset()):
    """⛓ The tangent chains of a shape: edge index (1-based in the edge map) -> chain number, for every edge that
    goes on smoothly into another (a rounded box's top outline, a hole's two half circles) — as OpenCASCADE's fillet
    finds them (it always rounds a chain whole). Edges alone in their chain are left out. Only an edge that meets
    another one nearly in line (_smooth_ends) is given to the fillet builder (each takes it ~4 ms: 7 s of the 1 800 edges
    of a 29-step part, most of them sharp corners). skip: face indices (0-based) whose edges are not looked at (🔩 real
    threads' grooves: no step can round them — they are cut after all the steps)."""
    if em is None or adj is None:
        _, em, adj = _adjacency(shape)
    mk, out = BRepFilletAPI_MakeFillet(shape), {}
    smooth = _smooth_ends(em, [ei for ei in range(1, em.Extent() + 1) if len(adj.get(ei, ())) == 2 and not adj[ei] & skip])
    for ei in smooth:
        e = TopoDS.Edge(em.FindKey(ei))
        if mk.Contour(e):
            continue
        try:
            mk.Add(1.0, e)  # (only the contour is built here, no rounding)
        except Exception:  # noqa: BLE001 — an edge it cannot take (a smooth one): no chain
            continue
    for ic in range(1, mk.NbContours() + 1):
        if mk.NbEdges(ic) > 1:
            for j in range(1, mk.NbEdges(ic) + 1):
                out[em.FindIndex(mk.Edge(ic, j))] = ic - 1
    return out


SMOOTH_COS = math.cos(math.radians(20))  # two edges meeting more in line than this may be one tangent chain


def _smooth_ends(em, edges):
    """Of the edges (indices in em), those that at one of their ends meet another of them nearly in line (their
    tangents within 20°: a superset of what a tangent chain joins) — in their order."""
    at, vm = {}, ShapeMap()  # vertex index -> [(edge, unit tangent there)]
    for ei in edges:
        e = TopoDS.Edge(em.FindKey(ei))
        c = BRepAdaptor_Curve(e)
        for t, v in ((c.FirstParameter(), TopExp.FirstVertex_s(e)), (c.LastParameter(), TopExp.LastVertex_s(e))):  # (not
            # cumulating the edge's orientation: its first vertex is at the curve's first parameter)
            p, d = gp_Pnt(), gp_Vec()
            c.D1(t, p, d)
            n = d.Magnitude()
            at.setdefault(vm.Add(v) if not v.IsNull() else -ei, []).append((ei, (d.X() / n, d.Y() / n, d.Z() / n) if n > 1e-12 else None))
    keep = set()
    for ends in at.values():
        for i, (a, ta) in enumerate(ends):
            for b, tb in ends[i + 1:]:
                if a != b and (ta is None or tb is None or abs(ta[0] * tb[0] + ta[1] * tb[1] + ta[2] * tb[2]) > SMOOTH_COS):
                    keep.update((a, b))
    return [ei for ei in edges if ei in keep]


def chain_size(body, edges):
    """How many edges rounding `edges` takes: each with its whole tangent chain."""
    mk, seen = BRepFilletAPI_MakeFillet(body.shape), []
    for e in edges:
        if not mk.Contour(e):
            try:
                mk.Add(1.0, e)
            except Exception:  # noqa: BLE001 — (counted alone)
                pass
        for x in _run(mk, e):
            if not any(x.IsSame(u) for u in seen):
                seen.append(x)
    return len(seen)


FLAT_TOL = 1e-5  # mm: a free-form face (a B-spline) this close to a plane counts as flat


def flat_plane(face, s=None):
    """A flat face's plane (gp_Pln, its normal as the surface's own — before the face's orientation), or None: a plane,
    or a B-spline / Bézier surface flat within FLAT_TOL (I-DEAS, Inventor's IGES store flat faces so)."""
    from OCP.GeomAbs import GeomAbs_BezierSurface, GeomAbs_BSplineSurface
    s = s or BRepAdaptor_Surface(face, True)
    kind = s.GetType()
    if kind == GeomAbs_Plane:
        return s.Plane()
    if kind not in (GeomAbs_BSplineSurface, GeomAbs_BezierSurface):
        return None
    from OCP.GeomLib import GeomLib_IsPlanarSurface
    try:
        surf = BRep_Tool.Surface_s(face)
        if surf is None:
            return None
        test = GeomLib_IsPlanarSurface(surf, FLAT_TOL)
        if not test.IsPlanar():
            return None
        pln = test.Plan()
        u, v = (s.FirstUParameter() + s.LastUParameter()) / 2, (s.FirstVParameter() + s.LastVParameter()) / 2
        p, du, dv = gp_Pnt(), gp_Vec(), gp_Vec()
        s.D1(u, v, p, du, dv)
        own = du.Crossed(dv)
    except Exception:  # noqa: BLE001 — a degenerate surface: not flat
        return None
    if own.Magnitude() > 1e-12 and own.Dot(gp_Vec(pln.Axis().Direction())) < 0:
        pln = gp_Pln(pln.Location(), pln.Axis().Direction().Reversed())
    return pln


def smooth_edges(body, edges):
    """How many of the edges are smooth: the two faces meet there without a corner (tangent: a rounding the file
    already has) — no fillet or chamfer can go on such an edge."""
    from OCP.BRepLib import BRepLib
    from OCP.GeomAbs import GeomAbs_C0
    em = _C.IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher()
    TopExp.MapShapesAndAncestors_s(body.shape, TopAbs_EDGE, TopAbs_FACE, em)
    n = 0
    for e in edges:
        k = em.FindIndex(e)
        faces = list(em.FindFromIndex(k)) if k else []
        if len(faces) != 2:
            continue
        try:
            if BRepLib.ContinuityOfFaces_s(TopoDS.Edge(e), TopoDS.Face(faces[0]), TopoDS.Face(faces[1]), math.radians(1)) != GeomAbs_C0:
                n += 1
        except Exception:  # noqa: BLE001 — (cannot tell: counted as sharp)
            pass
    return n


def plane_of(face):
    """A planar face -> (its centre, outward normal) or None."""
    face = TopoDS.Face(face)  # names hold faces as plain shapes (from OpenCASCADE's history)
    pln = flat_plane(face)
    if pln is None:
        return None
    d = pln.Axis().Direction()
    n = np.array([d.X(), d.Y(), d.Z()])
    if face.Orientation() == TopAbs_REVERSED:
        n = -n
    p = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, p)
    c = p.CentreOfMass()
    return np.array([c.X(), c.Y(), c.Z()]), n


def face_axis(face):
    """A round face (a cylinder, a cone, a torus or any turned face) -> (a point on its axis, its unit direction), or
    None (a flat face, a sphere, a free-form one) — a shaft's or a hole's axis to measure from."""
    from OCP.GeomAbs import GeomAbs_Cone, GeomAbs_SurfaceOfRevolution, GeomAbs_Torus
    s = BRepAdaptor_Surface(TopoDS.Face(face), True)
    kind = s.GetType()
    ax = (s.Cylinder().Axis() if kind == GeomAbs_Cylinder else s.Cone().Axis() if kind == GeomAbs_Cone
          else s.Torus().Axis() if kind == GeomAbs_Torus else s.AxeOfRevolution() if kind == GeomAbs_SurfaceOfRevolution else None)
    if ax is None:
        return None
    p, d = ax.Location(), ax.Direction()
    return np.array([p.X(), p.Y(), p.Z()]), np.array([d.X(), d.Y(), d.Z()])


def face_span(faces, fr):
    """How far faces reach along a frame's x and y, from its origin: [u0, u1, v0, v1] (exact; None: no faces) — a
    sketch's ⌜ corner origin is (u0, v0)."""
    o, x, y, n = _v(fr["o"]), _v(fr["x"]), frame_y(fr), _v(fr["n"])
    t, b = gp_Trsf(), Bnd_Box()
    t.SetValues(*x, -float(x @ o), *y, -float(y @ o), *n, -float(n @ o))  # world -> the frame's (u, v, w)
    for face in faces:
        BRepBndLib.AddOptimal_s(face.Moved(TopLoc_Location(t)), b, False, False)
    if b.IsVoid():
        return None
    lo, hi = b.CornerMin(), b.CornerMax()
    return [lo.X(), hi.X(), lo.Y(), hi.Y()]


# ------------------------------------------------------------------ queries
HEAVY_FACES = 3000  # an imported model with more faces than this is handled more roughly (else minutes per step)
_QUICK = (GeomAbs_Plane, GeomAbs_Cylinder)  # the surfaces the quick (fixed Gauss) volume rule gets right


_volumes: list = []  # [(shape, (volume, centre))]: the same shape asked again is not integrated again (real threads: 2.5 s)


def volume(shape):
    """The volume of the shape's solids — loose faces beside them (a file's reference surfaces) do not count; a shape
    with no solid: what its faces enclose (a closed shell). A solid with faces other than planes and cylinders is
    integrated adaptively: the quick fixed rule was hundreds of mm³ off on a B-spline balloon (a cut "raised" its
    volume) and 214 mm³ on the spherical head of CATIA's S1. The last few shapes' volumes are kept (a part with real
    threads: checked after the cut, then again when it is meshed)."""
    return _mass_props(shape)[0]


def centre(shape):
    """⚖ The centre of mass [x, y, z] of the shape's solids (of a uniform material), or None when it has no volume.
    It comes from the same integral as its volume (kept with it: asking both costs one)."""
    return _mass_props(shape)[1]


def _mass_props(shape):
    for s, v in _volumes:
        if s is shape:
            return v
    v = _volume(shape)
    _volumes.insert(0, (shape, v))
    del _volumes[4:]
    return v


def _mass_centre(p):
    m, c = p.Mass(), p.CentreOfMass()
    return m, ([c.X(), c.Y(), c.Z()] if abs(m) > 1e-12 else None)


def _volume(shape):
    """(volume, centre) of the shape's solids (see volume)."""
    solid_list = list(_subshapes(shape, TopAbs_SOLID))
    if len(solid_list) > 1:  # (the solids only, without the loose faces beside them)
        if sum(face_count(s) for s in solid_list) > HEAVY_FACES:  # a big model: the quick rule (exact enough there, 3 x quicker)
            p = GProp_GProps()
            BRepGProp.VolumeProperties_s(compound(solid_list), p)
            return _mass_centre(p)
        each = [_volume(s) for s in solid_list]  # (each on its own: the adaptive rule's error is relative to what it sums)
        m = sum(v for v, _ in each)
        return m, ([sum(v * c[i] for v, c in each if c) / m for i in range(3)] if abs(m) > 1e-12 else None)
    whole = solid_list[0] if solid_list else shape
    if face_count(whole) > HEAVY_FACES:
        p = GProp_GProps()
        BRepGProp.VolumeProperties_s(whole, p)
        return _mass_centre(p)
    other, ex = False, TopExp_Explorer(whole, TopAbs_FACE)
    while ex.More() and not other:
        f = TopoDS.Face(ex.Current())
        other = BRep_Tool.Surface_s(f) is not None and BRepAdaptor_Surface(f, False).GetType() not in _QUICK
        ex.Next()
    p = GProp_GProps()
    if other and _long_spline(whole):  # Gauss-Kronrod over each B-spline span: a plane bounded by one long smooth
        # curve (a joined sketch curve: hundreds of spans, one interval of continuity) was 8 % off with the adaptive rule
        BRepGProp.VolumePropertiesGK_s(whole, p, 1e-6, False, True)
    elif other:  # (the whole solid so: its planes, trimmed by the other faces' curved edges, need it as well)
        BRepGProp.VolumeProperties_s(whole, p, 1e-7, False)
    else:
        BRepGProp.VolumeProperties_s(whole, p)
    return _mass_centre(p)


LONG_SPLINE = 8  # knots: a B-spline edge with more is integrated span by span (volume)


def _long_spline(shape):
    """Has the shape an edge that is a B-spline of more than LONG_SPLINE knots (a sketch's smooth curve)?"""
    from OCP.GeomAbs import GeomAbs_BSplineCurve
    for e in _subshapes(shape, TopAbs_EDGE):
        c = BRepAdaptor_Curve(TopoDS.Edge(e))
        if c.GetType() == GeomAbs_BSplineCurve and c.NbKnots() > LONG_SPLINE:
            return True
    return False


def _subshapes(shape, kind):
    ex = TopExp_Explorer(shape, kind)
    while ex.More():
        yield ex.Current()
        ex.Next()


def face_count(shape):
    ex, n = TopExp_Explorer(shape, TopAbs_FACE), 0
    while ex.More():
        n += 1
        ex.Next()
    return n


def bbox(shape):
    b = Bnd_Box()
    if face_count(shape) > HEAVY_FACES:  # a big imported model: the quick box (a hair bigger); exact takes a minute
        BRepBndLib.Add_s(shape, b, False)
    else:
        BRepBndLib.AddOptimal_s(shape, b, False, False)  # exact: no tolerance padding
    if b.IsVoid():
        return None
    lo, hi = b.CornerMin(), b.CornerMax()
    return [lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z()]


def solids(shape):
    n, ex = 0, TopExp_Explorer(shape, TopAbs_SOLID)
    while ex.More():
        n += 1
        ex.Next()
    return n


def _round(a, k=6):
    return [round(float(x), k) for x in a]


def tessellate(body, light=False):
    """Triangles for the viewer with one face id per triangle, every face (name, plane frame for sketching),
    and every edge (polyline, the two faces it joins, its middle). light: 🪶 simplified — a coarse mesh, the faces'
    sizes from it, no edges (a big imported part in an assembly: quick to send and to show). A body with 🔩 real
    threads (cut_threads) has its flat faces' outward side checked against the part before the cut (the same flat
    faces; classifying past the helical faces took 5 s of 9 threads) and its grooves' edges in no ⛓ chain."""
    shape = body.shape
    bb = bbox(shape) or [0, 0, 0, 1, 1, 1]
    size = max(bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2], 1e-6)
    # a big imported model (thousands of faces): a coarser mesh, and only the edges that show at this size —
    # millions of triangles would freeze the browser (and take minutes here)
    fm = _face_map(shape)
    heavy = light or fm.Extent() > HEAVY_FACES
    if heavy:  # (the faces an edge joins: found for the edges drawn only, see _heavy_edges)
        em, adj = _edges_of(shape), None
    else:
        fm, em, adj = _adjacency(shape)
    # which solid each face belongs to (an imported file can hold several bodies: they can be coloured apart)
    solid_of, ex, k = {}, TopExp_Explorer(shape, TopAbs_SOLID), 0
    while ex.More():
        fx = TopExp_Explorer(ex.Current(), TopAbs_FACE)
        while fx.More():
            solid_of.setdefault(fm.FindIndex(fx.Current()) - 1, k)
            fx.Next()
        k += 1
        ex.Next()
    if light:  # a mesh finer than wanted is kept by OCCT: cleared first
        from OCP.BRepTools import BRepTools
        BRepTools.Clean_s(shape)
        BRepMesh_IncrementalMesh(shape, max(size * 0.015, 0.01), False, 1.0, True)
    else:
        BRepMesh_IncrementalMesh(shape, max(size * (0.004 if heavy else 0.0008), 0.002), False, 0.6 if heavy else 0.25, True)
    names = _face_names(body, fm)
    # every face's triangles as arrays, then all of them at once (a Python step per triangle took most of the time on
    # a big model: 900 000 triangles)
    nf, mesh = fm.Extent(), _face_meshes(fm)
    tris = np.concatenate([t for _, _, t, _ in mesh]) if nf else np.zeros((0, 3, 3))
    ids = np.repeat(np.arange(nf), [len(t) for _, _, t, _ in mesh])
    if heavy:  # the faces' areas and middles from their triangles (the exact ones take long on 100 000 faces)
        ar = np.linalg.norm(np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]), axis=1) / 2
        mid, n_tri = tris.mean(axis=1), np.bincount(ids, minlength=nf)
        area = np.bincount(ids, ar, minlength=nf)
        cms = np.zeros((nf, 3))
        for c in range(3):
            w = np.bincount(ids, ar * mid[:, c], minlength=nf)
            m = np.bincount(ids, mid[:, c], minlength=nf)
            cms[:, c] = np.where(area > 0, w / np.where(area > 0, area, 1), m / np.maximum(n_tri, 1))
    faces, cls, surfs = [], {}, {}  # (cls: the solid's classifier, set up once for all its flat faces)
    plain = getattr(body, "plain", None) or shape  # (real threads not cut yet: flat faces classified against the part before the cut)
    for fi, (f, rev, t, place) in enumerate(mesh):
        if heavy:  # (a face placed again: its surface asked once, moved; the flat faces' centres all at once: _box_centres)
            surf = None
            if place is not None:
                k, bare, m = place
                if k not in surfs:
                    surfs[k] = _surface_of(TopoDS.Face(bare))
                surf = _moved_surface(surfs[k], m.tolist())
            info = _face_info(f, fi, rev, (float(area[fi]), cms[fi]), centre=False, surf=surf)
        else:
            info = _face_info(f, fi, rev)
        if info.get("type") == "plane" and len(t) and not heavy:
            _outward(plain, info, t[0].mean(axis=0), size, cls)  # (a point on the face: a triangle's middle — a ring's centre is not on it)
        if fi in solid_of:
            info["solid"] = solid_of[fi]
        nm = names.get(fi, [])
        if nm:
            info["name"] = nm[-1]  # the latest name (e.g. the hole wall rather than the plate it was cut from)
            info["names"] = nm
            info["ref"] = {"name": nm[-1]}
        faces.append(info)
    if light:  # 🪶 what an assembly needs of a face: its kind, name, size, place; no sketch frame (half the data)
        r3 = lambda v: [round(x, 3) for x in v]  # noqa: E731
        for f in faces:
            f.pop("frame", None)
            f.pop("ref", None)
            if f.get("names") == [f.get("name")]:
                f.pop("names", None)
            f["area"] = round(f.get("area", 0), 3)
            f["centroid"] = r3(f["centroid"])
    elif heavy:
        _box_centres(faces, tris, ids)
    if heavy:  # (🪶: no edges)
        edges = [] if light else _heavy_edges(shape, fm, em, size)
        return {"positions": tris.astype(np.float32).tobytes(), "face_ids": ids.astype(np.uint32).tobytes(),
                "faces": faces, "edges": edges, "bbox": bb, "volume": volume(shape), "solids": solids(shape), **({"light": True} if light else {})}
    edges = []
    grooves = {fm.FindIndex(f) - 1 for n in getattr(body, "grooves", ()) for f in body.faces_of(n)}
    chains = tangent_chains(shape, em, adj, grooves)  # (⛓ a click on a fillet's edge takes its chain; a thread's grooves left out)
    for ei in range(1, em.Extent() + 1):
        e = TopoDS.Edge(em.FindKey(ei))
        try:
            c = BRepAdaptor_Curve(e)
            d = GCPnts_TangentialDeflection(c, 0.2, max(size * 0.001, 0.002))
            pts = [d.Value(i) for i in range(1, d.NbPoints() + 1)]
        except Exception:  # noqa: BLE001 — a degenerate edge: nothing to draw
            continue
        if len(pts) < 2:
            continue
        edges.append({"pts": [round(v, 5) for p in pts for v in (p.X(), p.Y(), p.Z())], "faces": sorted(adj.get(ei, ())),
                      "mid": _round(_edge_mid(e), 5), **({"chain": chains[ei]} if ei in chains else {})})
    return {"positions": tris.astype(np.float32).tobytes(), "face_ids": ids.astype(np.uint32).tobytes(),
            "faces": faces, "edges": edges, "bbox": bb, "volume": volume(shape), "solids": solids(shape), **({"light": True} if light else {}),
            # ⚖ the solids' surface area (their faces': a file's loose faces left out) and centre of mass
            "area": round(sum(f["area"] for f in faces if "solid" in f or not solid_of), 3),
            "cog": _round(centre(shape) or [(bb[i] + bb[i + 3]) / 2 for i in range(3)], 4)}


def _face_triangles(f):
    """The triangles (n, 3, 3) of a meshed face, wound outward."""
    loc = TopLoc_Location()
    tri = BRep_Tool.Triangulation_s(f, loc)
    if tri is None or not tri.NbTriangles():
        return np.zeros((0, 3, 3))
    if loc.IsIdentity():
        nodes = np.array([tri.Node(i).Coord() for i in range(1, tri.NbNodes() + 1)], float)
    else:
        tr = loc.Transformation()
        nodes = np.array([tri.Node(i).Transformed(tr).Coord() for i in range(1, tri.NbNodes() + 1)], float)
    k = np.array([tri.Triangle(i).Get() for i in range(1, tri.NbTriangles() + 1)], np.int64) - 1
    return nodes[k[:, [0, 2, 1]] if f.Orientation() == TopAbs_REVERSED else k]


def _matrix(loc):
    """A location's transformation as a 3 × 4 matrix (rotation and scale | shift)."""
    tr = loc.Transformation()
    return np.array([[tr.Value(r, c) for c in range(1, 5)] for r in range(1, 4)])


def _face_meshes(fm):
    """Every meshed face of the face map -> [(face, reversed, its triangles (n, 3, 3) wound outward, place)]. A face
    placed many times (one part used again and again: a board's 126 000 faces are 19 000 faces placed) is read from its
    mesh once and moved into each place (a Python step per node of each face took 5 s on that board). place: None (where
    it is), else (k, the face without its place, the place's 3 × 4 matrix) — k the same for each placing of one face."""
    out, bare, local = [], ShapeMap(), {}
    here, last = TopLoc_Location(), (None, None)  # (last: the place before and its matrix — a part's faces come together)
    for fi in range(fm.Extent()):
        f = TopoDS.Face(fm.FindKey(fi + 1))
        rev, loc = f.Orientation() == TopAbs_REVERSED, f.Location()
        if loc.IsIdentity():
            out.append((f, rev, _face_triangles(f), None))
            continue
        k = bare.Add(f.Located(here))
        if k not in local:  # its mesh where its part has it (without the placement), its triangles' corners unwound
            t = _face_triangles(TopoDS.Face(bare.FindKey(k).Oriented(TopAbs_FORWARD)))
            local[k] = (t.reshape(-1, 3), len(t))
        if last[0] is None or not loc.IsEqual(last[0]):
            last = (loc, _matrix(loc))
        (p, n), m = local[k], last[1]
        place = (k, bare.FindKey(k), m)
        if not n:
            out.append((f, rev, np.zeros((0, 3, 3)), place))
            continue
        t = (p @ m[:, :3].T + m[:, 3]).reshape(n, 3, 3)
        out.append((f, rev, t[:, [0, 2, 1]] if rev else t, place))
    return out


def _box_centres(faces, tris, ids):
    """_box_centre of every flat face of a big model from its triangles, all at once (one by one: 4 s for the 73 000
    flat faces of a board). faces: _face_info's, in face order; tris, ids: the triangles and their faces' ids."""
    flat = [f for f in faces if "frame" in f]
    if not flat or not len(tris):
        return
    nf = len(faces)
    o, x, n = (np.zeros((nf, 3)) for _ in range(3))
    at = np.array([f["id"] for f in flat])
    o[at] = [f["frame"]["o"] for f in flat]
    x[at] = [f["frame"]["x"] for f in flat]
    n[at] = [f["frame"]["n"] for f in flat]
    y = np.cross(n, x)  # (frame_y)
    vid = np.repeat(ids, 3)  # each triangle corner's face (in face order: the faces' corners one after another)
    p = tris.reshape(-1, 3) - o[vid]
    u, v = np.einsum("ij,ij->i", p, x[vid]), np.einsum("ij,ij->i", p, y[vid])
    count = np.bincount(vid, minlength=nf)
    start = np.concatenate([[0], np.cumsum(count)[:-1]])
    has = count > 0
    lo_u, hi_u = np.full(nf, np.nan), np.full(nf, np.nan)
    lo_v, hi_v = np.full(nf, np.nan), np.full(nf, np.nan)
    for lo, hi, w in ((lo_u, hi_u, u), (lo_v, hi_v, v)):
        lo[has] = np.minimum.reduceat(w, start[has])
        hi[has] = np.maximum.reduceat(w, start[has])
    c = o + ((lo_u + hi_u) / 2)[:, None] * x + ((lo_v + hi_v) / 2)[:, None] * y
    for f in flat:
        if has[f["id"]]:
            f["frame"]["o"] = _round(c[f["id"]])


def _heavy_edges(shape, fm, em, size):
    """The edges of a big model that show at its size (longer than 1 % of it), coarsely: [{pts, faces, mid}] in the
    edge map's order. An edge placed many times (a board's parts) is measured and divided once, then moved into each
    place; the faces each joins are looked up only for those drawn."""
    anc = _C.IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher()
    TopExp.MapShapesAndAncestors_s(shape, TopAbs_EDGE, TopAbs_FACE, anc)
    bare, local, here, out = ShapeMap(), {}, TopLoc_Location(), []
    for ei in range(1, em.Extent() + 1):
        e = TopoDS.Edge(em.FindKey(ei))
        k = bare.Add(e.Located(here))
        if k not in local:  # its points where its part has it: None when too short, degenerate or a single point
            local[k] = None
            try:
                c = BRepAdaptor_Curve(TopoDS.Edge(bare.FindKey(k)))
                if _edge_len(c) >= size * 0.01:
                    d = GCPnts_TangentialDeflection(c, 0.5, max(size * 0.004, 0.002))
                    pts = np.array([d.Value(i).Coord() for i in range(1, d.NbPoints() + 1)], float).reshape(-1, 3)
                    if len(pts) >= 2:
                        local[k] = (pts, _edge_mid(TopoDS.Edge(bare.FindKey(k))))
            except Exception:  # noqa: BLE001 — a degenerate edge: nothing to draw
                pass
        if local[k] is None:
            continue
        pts, mid = local[k]
        if not e.Location().IsIdentity():
            m = _matrix(e.Location())
            pts, mid = pts @ m[:, :3].T + m[:, 3], m[:, :3] @ mid + m[:, 3]
        j, faces = anc.FindIndex(e), set()
        fl = anc.FindFromIndex(j) if j else None
        n = fl.Size() if fl is not None else 0  # (a list walked from Python takes 0.5 ms: its ends, an edge has two faces)
        for f in (() if not n else (fl.First(), fl.Last()) if n <= 2 else list(fl)):
            i = fm.FindIndex(f)
            if i:
                faces.add(i - 1)
        out.append({"pts": [round(float(v), 5) for v in pts.ravel()], "faces": sorted(faces), "mid": _round(mid, 5)})
    return out


def _outward(shape, info, point, size, cls=None):
    """A flat face's normal made to point out of the solid: a point a hair along it, from a point on the face, must
    be outside (a revolved solid can come with its faces' orientation the other way round). cls: a dict keeping the
    solid's classifier for the next face (set up once: per face it took 40 s on a 1 700-face part)."""
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.TopAbs import TopAbs_IN
    n = np.asarray(info["normal"], float)
    eps = max(size * 1e-4, 1e-4)
    q = np.asarray(point, float) + n * eps
    try:
        c = (cls or {}).get("c")
        if c is None:
            c = BRepClass3d_SolidClassifier(shape)
            if cls is not None:
                cls["c"] = c
        c.Perform(gp_Pnt(*map(float, q)), eps * 0.1)
        inside = c.State() == TopAbs_IN
    except Exception:  # noqa: BLE001 — not a closed solid: keep what the face says
        return
    if inside:
        info["normal"] = _round(-n)
        if "frame" in info:
            info["frame"]["n"] = _round(-np.asarray(info["frame"]["n"], float))


def _edge_len(c):
    """About how long an edge is (its ends and middle; enough to skip tiny ones)."""
    a, m, b = (c.Value(t) for t in (c.FirstParameter(), (c.FirstParameter() + c.LastParameter()) / 2, c.LastParameter()))
    return a.Distance(m) + m.Distance(b)


def _surface_of(f):
    """What a face's surface is to the viewer: ("plane", its normal as the surface's own), ("cylinder", radius, a point
    of the axis, its direction) or ("other",)."""
    s = BRepAdaptor_Surface(f, True)
    pln = flat_plane(f, s)
    if pln is not None:
        return ("plane", pln.Axis().Direction().Coord())
    if s.GetType() == GeomAbs_Cylinder:
        cyl = s.Cylinder()
        a = cyl.Axis()
        return ("cylinder", cyl.Radius(), a.Location().Coord(), a.Direction().Coord())
    return ("other",)


def _moved_surface(surf, m):
    """_surface_of's answer for a face placed by the 3 × 4 matrix m (rows as lists: its part's place) — plain floats:
    numpy per face took a second on a board."""
    def turn(v):
        return [m[i][0] * v[0] + m[i][1] * v[1] + m[i][2] * v[2] for i in range(3)]

    def length(v):
        return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if surf[0] == "plane":
        n = turn(surf[1])
        return ("plane", tuple(x / (length(n) or 1.0) for x in n))
    if surf[0] == "cylinder":
        d = turn(surf[3])
        ln = length(d) or 1.0
        return ("cylinder", surf[1] * ln / (length(surf[3]) or 1.0), tuple(a + m[i][3] for i, a in enumerate(turn(surf[2]))),
                tuple(x / ln for x in d))
    return surf


def _face_info(f, fi, rev, rough=None, tris=None, centre=True, surf=None):
    """A face for the viewer: {id, area, centroid, type, normal + frame (flat) / radius + axis (a cylinder)}. rough:
    (area, centre) from the mesh; centre False: a flat face's frame keeps the centroid (_box_centres sets it); surf:
    its _surface_of when known (a face placed again)."""
    if rough:  # (area, centre) from the mesh
        info = {"id": fi, "area": rough[0], "centroid": _round(tuple(rough[1]))}
    else:
        p = GProp_GProps()
        BRepGProp.SurfaceProperties_s(f, p)
        c = p.CentreOfMass()
        info = {"id": fi, "area": p.Mass(), "centroid": _round((c.X(), c.Y(), c.Z()))}
    surf = surf or _surface_of(f)
    if surf[0] == "plane":
        n = surf[1]
        if rev:
            n = tuple(-v for v in n)
        info["type"] = "plane"
        info["normal"] = _round(n)
        # a sketch frame on this face: origin at its centre, x along the world axis closest to the face (plain floats:
        # numpy per face took seconds on a big model)
        k = min(range(3), key=lambda i: abs(n[i]))
        x = [(1.0 if i == k else 0.0) - n[k] * n[i] for i in range(3)]
        ln = math.sqrt(x[0] * x[0] + x[1] * x[1] + x[2] * x[2])
        info["frame"] = {"o": info["centroid"], "x": _round(v / ln for v in x), "n": _round(n)}
        if centre:  # (else the caller sets it: _box_centres)
            info["frame"]["o"] = _box_centre(f, info["frame"], tris if rough else None)
    elif surf[0] == "cylinder":
        info["type"] = "cylinder"
        info["radius"] = round(surf[1], 6)
        info["axis"] = {"o": _round(surf[2]), "d": _round(surf[3])}
    else:
        info["type"] = "other"
    return info


def _box_centre(f, fr, tris=None):
    """A flat face's centre: the middle of its box in its own u / v (not the centre of its area — that moves with
    every hole cut into the face, and a hole placed from it would land off). tris: from the mesh (a heavy model)."""
    o, x, y = _v(fr["o"]), _v(fr["x"]), frame_y(fr)
    if tris is not None:
        if not len(tris):
            return fr["o"]
        p = tris.reshape(-1, 3) - o
        u, v = p @ x, p @ y
        span = [u.min(), u.max(), v.min(), v.max()]
    else:
        span = face_span([f], fr)
        if span is None:
            return fr["o"]
    return _round(o + (span[0] + span[1]) / 2 * x + (span[2] + span[3]) / 2 * y)


def _chain(segs, tol=1e-6, fine=None):
    """Line pieces [[p, q]] -> polylines joining the ones that meet at their ends, in any order (a mesh's outline is
    many pieces). fine: a length too small to see on the paper — each polyline simplified to it (Douglas–Peucker) and
    one smaller than it left out."""
    at = {}  # an end -> the pieces there
    q = lambda p: (round(p[0] / tol), round(p[1] / tol))  # noqa: E731
    for i, (a, b) in enumerate(segs):
        at.setdefault(q(a), []).append(i)
        at.setdefault(q(b), []).append(i)
    used, out = [False] * len(segs), []

    def walk(pl):  # on from pl's last point while one unused piece goes on from it
        while True:
            nxt = next((j for j in at[q(pl[-1])] if not used[j]), None)
            if nxt is None:
                return
            used[nxt] = True
            a, b = segs[nxt]
            pl.append(b if q(a) == q(pl[-1]) else a)

    for i, (a, b) in enumerate(segs):
        if used[i]:
            continue
        used[i] = True
        pl = [a, b]
        walk(pl)
        pl.reverse()
        walk(pl)
        if fine:
            xs, ys = [p[0] for p in pl], [p[1] for p in pl]
            if max(xs) - min(xs) < fine and max(ys) - min(ys) < fine:
                continue
            pl = _simplify(pl, fine / 2)
        out.append(pl)
    return out


def _simplify(pl, tol):
    """A polyline with the points it does not need to stay within tol (Douglas–Peucker)."""
    if len(pl) < 3:
        return pl
    a = np.asarray(pl, float)
    keep, todo = {0, len(a) - 1}, [(0, len(a) - 1)]
    while todo:
        i, j = todo.pop()
        if j - i < 2:
            continue
        d = a[j] - a[i]
        n = math.hypot(*d)
        mid = a[i + 1:j] - a[i]
        dist = np.abs(mid[:, 0] * d[1] - mid[:, 1] * d[0]) / n if n > 1e-12 else np.hypot(mid[:, 0], mid[:, 1])
        k = int(dist.argmax())
        if dist[k] > tol:
            keep.add(i + 1 + k)
            todo += [(i, i + 1 + k), (i + 1 + k, j)]
    return [pl[k] for k in sorted(keep)]


def _project_poly(shape, ax, flip, size, fine=None):
    """Hidden-line removal on the shape's mesh (a big imported model: the exact one takes minutes) -> (visible, no hidden).
    fine: see _chain."""
    from OCP.HLRAlgo import HLRAlgo_Projector
    from OCP.HLRBRep import HLRBRep_PolyAlgo, HLRBRep_PolyHLRToShape
    ex = TopExp_Explorer(shape, TopAbs_FACE)
    if ex.More() and BRep_Tool.Triangulation_s(TopoDS.Face(ex.Current()), TopLoc_Location()) is None:  # (meshed for the view already: kept)
        BRepMesh_IncrementalMesh(shape, max(size * 0.004, 0.002), False, 0.6, True)
    algo = HLRBRep_PolyAlgo()
    algo.Load(shape)
    algo.Projector(HLRAlgo_Projector(ax))
    algo.Update()
    hl = HLRBRep_PolyHLRToShape()
    hl.Update(algo)

    def pieces(comp):
        segs = []
        if comp is None or comp.IsNull():
            return segs
        ex = TopExp_Explorer(comp, TopAbs_EDGE)
        while ex.More():
            e = TopoDS.Edge(ex.Current())
            c = BRepAdaptor_Curve(e)
            p, q = c.Value(c.FirstParameter()), c.Value(c.LastParameter())
            segs.append([(p.X(), -p.Y() if flip else p.Y()), (q.X(), -q.Y() if flip else q.Y())])
            ex.Next()
        return _chain(segs, fine=fine)

    # no hidden lines: on a model this big they are a dense grey wash (and hundreds of thousands of pieces)
    return pieces(hl.VCompound()) + pieces(hl.OutLineVCompound()), []


def _straight(pts, tol=1e-4):
    """A projected curve that is a straight line after all (a hole's outline seen from the side: a spline, not a line)
    -> its two ends; else as it is (48 points each: most of a sheet's payload)."""
    if len(pts) < 3:
        return pts
    a = np.asarray(pts, float)
    d = a[-1] - a[0]
    n = math.hypot(*d)
    if n < tol or np.abs((a[:, 0] - a[0, 0]) * d[1] - (a[:, 1] - a[0, 1]) * d[0]).max() > tol * n:
        return pts
    along = (a - a[0]) @ d
    if along.min() < -tol * n or along.max() > n * n + tol * n:  # (an arc seen edge-on: it goes past its ends)
        return pts
    return [pts[0], pts[-1]]


def project_edges(shape, look, right, up, fine=None):
    """The visible and hidden edges of the shape seen along `look` (hidden-line removal) -> ([[(x, y)…]…], [[…]…])
    in mm, in the view's axes: x along `right`, y along `up`. A big imported model (more than HEAVY_FACES faces) is
    projected from its mesh (seconds, not minutes; its lines a hair less smooth) — so is a shape given `fine`: its
    lines kept to `fine` mm (what the paper shows, see _chain)."""
    from OCP.BRepLib import BRepLib
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    from OCP.HLRAlgo import HLRAlgo_Projector
    from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
    from OCP.GeomAbs import GeomAbs_Line

    # the projector looks against its axis' direction: the axis points at the viewer
    ax = gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(*[-c for c in look]), gp_Dir(*right))
    up_v0 = np.cross(np.asarray([-c for c in look], float), np.asarray(right, float))
    if fine or face_count(shape) > HEAVY_FACES:
        bb = bbox(shape) or [0, 0, 0, 1, 1, 1]
        return _project_poly(shape, ax, float(up_v0 @ np.asarray(up, float)) < 0, max(bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2], 1e-6), fine)
    algo = HLRBRep_Algo()
    algo.Add(shape)
    algo.Projector(HLRAlgo_Projector(ax))
    algo.Update()
    algo.Hide()
    hl = HLRBRep_HLRToShape(algo)
    up_v = np.cross(np.asarray([-c for c in look], float), np.asarray(right, float))
    flip = float(up_v @ np.asarray(up, float)) < 0  # keep "up" up

    def lines(comp):
        out = []
        if comp is None or comp.IsNull():
            return out
        BRepLib.BuildCurves3d_s(comp)
        ex = TopExp_Explorer(comp, TopAbs_EDGE)
        while ex.More():
            e = TopoDS.Edge(ex.Current())
            c = BRepAdaptor_Curve(e)
            t0, t1 = c.FirstParameter(), c.LastParameter()
            n = 2 if c.GetType() == GeomAbs_Line else 48
            pts = []
            for i in range(n + 1):
                p = c.Value(t0 + (t1 - t0) * i / n)
                pts.append((p.X(), -p.Y() if flip else p.Y()))
            out.append(_straight(pts))
            ex.Next()
        return out

    visible = lines(hl.VCompound()) + lines(hl.OutLineVCompound()) + lines(hl.Rg1LineVCompound())
    hidden = lines(hl.HCompound()) + lines(hl.OutLineHCompound())
    return visible, hidden


def _trsf(m16):
    """A 4 x 4 placement matrix (column-major, as three.js stores it; rotation + move) -> gp_Trsf."""
    m = list(map(float, m16))
    t = gp_Trsf()
    t.SetValues(m[0], m[4], m[8], m[12], m[1], m[5], m[9], m[13], m[2], m[6], m[10], m[14])
    return t


def placed(shape, m16):
    """A shape moved by a 4 x 4 placement matrix (column-major, as three.js stores it; only rotation + move) — given a
    location, not copied (a big imported model took a second a copy)."""
    return shape.Moved(TopLoc_Location(_trsf(m16)))


def _solid_boxes(shape):
    """The solids of a shape with their quick boxes: [(solid, [x0 … z1])] (an assembled board holds a thousand)."""
    out, ex = [], TopExp_Explorer(shape, TopAbs_SOLID)
    while ex.More():
        b = Bnd_Box()
        BRepBndLib.Add_s(ex.Current(), b, False)
        if not b.IsVoid():
            lo, hi = b.CornerMin(), b.CornerMax()
            out.append((ex.Current(), [lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z()]))
        ex.Next()
    return out


def _apart(a, b):
    return any(a[k] >= b[k + 3] - 1e-6 or b[k] >= a[k + 3] - 1e-6 for k in range(3))


QUICK_PAIRS = 40  # a quick check: more solids than this meeting in one pair of parts -> an estimate (big boards)


def interference(shapes, min_volume=1e-3, only=None, quick=False):
    """Where placed solids overlap: shapes [(key, shape)] -> [{a, b, volume (mm³), bbox (of the overlap), approx?}], the
    biggest first. Parts whose boxes do not meet are not computed; touching faces (no volume) are not a clash.
    only: a set of keys — just the pairs with one of them. quick: a pair whose solids meet in more than QUICK_PAIRS
    places (two big imported boards) is told by their boxes (`approx`), not computed (that takes half a minute)."""
    boxes = [(k, s, bbox(s)) for k, s in shapes]
    parts = {}  # key -> its solids with their boxes (made when a pair needs them)
    out = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            (ka, sa, ba), (kb, sb, bb) = boxes[i], boxes[j]
            if only is not None and ka not in only and kb not in only:
                continue
            if not ba or not bb or _apart(ba, bb):
                continue
            # solid by solid, only those whose boxes meet (a part of many solids: a board with its components)
            for k, s in ((ka, sa), (kb, sb)):
                if k not in parts:
                    parts[k] = _solid_boxes(s) or [(s, bbox(s) or [0] * 6)]
            v, lo, hi = 0.0, [float("inf")] * 3, [float("-inf")] * 3
            if quick:
                meet = [(bx, by) for _, bx in parts[ka] if not _apart(bx, bb) for _, by in parts[kb] if not _apart(bx, by)]
                if len(meet) > QUICK_PAIRS:
                    for bx, by in meet:  # the boxes' overlaps: an upper bound
                        o = [max(bx[q], by[q]) for q in range(3)] + [min(bx[q + 3], by[q + 3]) for q in range(3)]
                        v += max(0.0, o[3] - o[0]) * max(0.0, o[4] - o[1]) * max(0.0, o[5] - o[2])
                        lo, hi = [min(lo[q], o[q]) for q in range(3)], [max(hi[q], o[q + 3]) for q in range(3)]
                    if v > min_volume:
                        out.append({"a": ka, "b": kb, "volume": round(v, 3), "bbox": _round(lo + hi, 3), "approx": True})
                    continue
            for x, bx in parts[ka]:
                if _apart(bx, bb):
                    continue
                for y, by in parts[kb]:
                    if _apart(bx, by):
                        continue
                    mk = bop("common", x, y)
                    if not mk.IsDone():
                        continue
                    common = mk.Shape()
                    cv = volume(common)
                    if cv <= min_volume / 100:
                        continue
                    v += cv
                    cb = bbox(common)
                    if cb:
                        lo, hi = [min(lo[q], cb[q]) for q in range(3)], [max(hi[q], cb[q + 3]) for q in range(3)]
            if v > min_volume:
                out.append({"a": ka, "b": kb, "volume": round(v, 3), "bbox": _round(lo + hi, 3)})
    return sorted(out, key=lambda c: -c["volume"])


def compound(shapes):
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound
    c, b = TopoDS_Compound(), BRep_Builder()
    b.MakeCompound(c)
    for sh in shapes:
        b.Add(c, sh)
    return c


# ------------------------------------------------------------------ files
def mesh_solid(tris, tol=1e-4):
    """Triangles (n, 3, 3) of a closed mesh (STL / OBJ) -> a solid: the triangles sewn, flat neighbours merged
    into one face."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeSolid, BRepBuilderAPI_Sewing
    from OCP.ShapeFix import ShapeFix_Solid
    from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
    from OCP.TopAbs import TopAbs_SHELL
    sew = BRepBuilderAPI_Sewing(tol)
    for a, b, c in np.asarray(tris, float):
        if np.linalg.norm(np.cross(b - a, c - a)) < 1e-12:
            continue  # no area
        poly = BRepBuilderAPI_MakePolygon(gp_Pnt(*a), gp_Pnt(*b), gp_Pnt(*c), True)
        sew.Add(BRepBuilderAPI_MakeFace(poly.Wire(), True).Face())
    sew.Perform()
    mk, ex, n = BRepBuilderAPI_MakeSolid(), TopExp_Explorer(sew.SewedShape(), TopAbs_SHELL), 0
    while ex.More():
        mk.Add(TopoDS.Shell(ex.Current()))
        n += 1
        ex.Next()
    if not n:
        raise KernelError("The mesh has no closed surface — it cannot become a solid.")
    fix = ShapeFix_Solid(mk.Solid())
    fix.Perform()
    shape = fix.Solid()
    if volume(shape) <= 0:
        raise KernelError("The mesh is not closed (it has holes) — it cannot become a solid.")
    u = ShapeUpgrade_UnifySameDomain(shape, True, True, False)
    u.Build()
    return u.Shape()


def to_step(shape, name="part", colour=None, colours=None):
    """One part as a STEP file (AP214, mm), as other CAD programs read it: a product named `name`, the part's colour
    ("#rrggbb") and its faces' own colours (colours [(face, "#rrggbb")]: an imported file's, 🎨 painted ones)."""
    return write_step_tree({"p": {"name": name, "shape": shape, "colour": colour, "colours": colours or []}}, {}, "p", name)


def to_iges(shape, surfaces=False, name=None, colour=None, colours=None):
    """One part as an IGES file (5.3, its exact B-rep solid as MSBO entities, mm) — for CAD programs that take IGES
    rather than STEP — with its name and colours as for to_step. surfaces: trimmed surfaces only (entity 144, as older
    programs write IGES), no solid."""
    return _iges({"p": {"name": name or "part", "shape": shape, "colour": colour, "colours": colours or []}}, surfaces=surfaces)


@contextlib.contextmanager
def _settings(values):
    """The STEP / IGES writers' settings (Interface_Static: one set for the whole process) for one export, the old
    values back after it — so an export never inherits what an earlier one set (e.g. its product name)."""
    old = {}
    try:
        for k, v in values.items():
            if isinstance(v, int):
                old[k] = Interface_Static.IVal_s(k)
                Interface_Static.SetIVal_s(k, v)
            else:
                old[k] = Interface_Static.CVal_s(k)
                Interface_Static.SetCVal_s(k, v)
        yield
    finally:
        for k, v in old.items():
            if isinstance(v, int):
                Interface_Static.SetIVal_s(k, v)
            elif v:
                Interface_Static.SetCVal_s(k, v)


def _step_ascii(data: bytes) -> bytes:
    r"""A STEP file in plain ASCII: a character beyond it (×, č …) as STEP's own \X2\00D7\X0\ (\X4\ beyond U+FFFF),
    which every STEP reader decodes — OCCT writes the UTF-8 bytes, which older readers show as "Ã—"."""
    text = data.decode("utf-8", errors="replace")
    if text.isascii():
        return data

    def code(m):
        s = m.group(0)
        if all(ord(c) <= 0xFFFF for c in s):
            return "\\X2\\" + "".join("%04X" % ord(c) for c in s) + "\\X0\\"
        return "\\X4\\" + "".join("%08X" % ord(c) for c in s) + "\\X0\\"
    return re.sub(r"[^\x00-\x7f]+", code, text).encode("ascii")


def _ascii(text):
    """A name as IGES holds it (ASCII only: its strings count characters as bytes): accents dropped, "×" -> "x"."""
    import unicodedata
    s = unicodedata.normalize("NFKD", str(text or "").replace("×", "x"))
    return "".join(c for c in s if c.isascii() and not unicodedata.combining(c))


def sewn_solids(faces, tol=0.01):
    """Loose faces (an IGES of trimmed surfaces, as many programs write it) sewn together -> (closed solids, the faces
    left over): each piece that closes (no gap wider than tol mm, no face missing) is a solid of its own — an
    assembly's IGES gives a solid per body — the others (and a closed piece that is not a valid solid) stay faces."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeSolid, BRepBuilderAPI_Sewing
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.ShapeFix import ShapeFix_Solid
    from OCP.TopAbs import TopAbs_SHELL
    sew = BRepBuilderAPI_Sewing(tol)
    for f in faces:
        sew.Add(f)
    sew.Perform()
    sewed, out, left = sew.SewedShape(), [], []
    for shell in _subshapes(sewed, TopAbs_SHELL):
        solid = None
        if BRep_Tool.IsClosed_s(shell):  # (closed: every edge has a face on both sides)
            fix = ShapeFix_Solid(BRepBuilderAPI_MakeSolid(TopoDS.Shell(shell)).Solid())
            fix.Perform()
            # (and valid: a cut through a body that closes but is broken took thousands of mm³ off the valve's IGES)
            if volume(fix.Solid()) > 0 and BRepCheck_Analyzer(fix.Solid()).IsValid():
                solid = fix.Solid()
        if solid is None:
            left += list(_subshapes(shell, TopAbs_FACE))
        else:
            out.append(solid)
    ex = TopExp_Explorer(sewed, TopAbs_FACE, TopAbs_SHELL)  # (a face sewn to nothing)
    while ex.More():
        left.append(ex.Current())
        ex.Next()
    return out, left


def sewn_solid(shape, tol=0.01):
    """Loose faces sewn together -> closed solids (one, or a compound of them), or None when they do not all close."""
    out, left = sewn_solids(list(_subshapes(shape, TopAbs_FACE)), tol)
    if not out or left:
        return None
    return out[0] if len(out) == 1 else compound(out)


def read_iges(data: bytes):
    """An IGES file -> (shape, {face index: "#rrggbb"}, how): its solids as they are (how "solid"); surfaces only
    sewn into closed solids where they close ("sewn"; "partly": some pieces do not close — they stay loose faces beside
    the solids, shown for reference); else the surfaces as they are ("surfaces": not a solid). Pieces that do not close
    at 0.01 mm are sewn again with a tolerance of 1 / 10 000 of the model's size (a model drawn in metres)."""
    shape, colours = read_step_colours(data, kind="iges")
    if face_count(shape) == 0:
        raise KernelError("The IGES file has no faces in it (only curves?) — there is nothing to make a 3D model of.")
    if solids(shape):
        return shape, colours, "solid"
    got, left = sewn_solids(list(_subshapes(shape, TopAbs_FACE)))
    bb = bbox(shape) or [0, 0, 0, 0, 0, 0]
    loose = max(bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2]) * 1e-4
    if left and loose > 0.02:
        more, left = sewn_solids(left, loose)
        got += more
    if not got:
        return shape, colours, "surfaces"
    if not left:
        return (got[0] if len(got) == 1 else compound(got)), {}, "sewn"
    return compound(got + left), {}, "partly"


_loose: list = []  # [(shape, its loose faces)]: one file's asked twice (solid_body, then its step: 0.6 s on a board)


def loose_faces(shape):
    """The faces of a shape that belong to no solid (a STEP's reference surfaces beside its solid, an IGES's surfaces
    that do not close) as one compound, or None. They take no part in the volume, the mass or the booleans."""
    for s, out in _loose:
        if s is shape:
            return out
    if not solids(shape):
        return None
    inside = ShapeMap()
    for s in _subshapes(shape, TopAbs_SOLID):
        TopExp.MapShapes_s(s, TopAbs_FACE, inside)
    out = [f for f in _subshapes(shape, TopAbs_FACE) if not inside.Contains(f)]
    out = compound(out) if out else None
    _loose.insert(0, (shape, out))
    del _loose[2:]
    return out


def solid_body(shape, fid, whole=False):
    """A solid made elsewhere (a STEP file, a quick part) as a body; its faces are named <fid>:f<k> (k: the face's
    place in the whole file's shape — its colours are found by it). Loose faces beside its solids are left out (see
    loose_faces); whole: kept (a reference body)."""
    fm = _face_map(shape)
    names = {f"{fid}:f{k}": [fm.FindKey(k + 1)] for k in range(fm.Extent())}
    loose = None if whole else loose_faces(shape)
    if loose is None:
        return Body(shape, names)
    solid_list = list(_subshapes(shape, TopAbs_SOLID))
    body = solid_list[0] if len(solid_list) == 1 else compound(solid_list)
    known = next((v for s, v in _volumes if s is shape), None)
    if known is not None:  # (its volume is the file's — loose faces count for nothing: not integrated again, 2.5 s on a board)
        _volumes.insert(0, (body, known))
        del _volumes[4:]
    inside = _face_map(body)
    return Body(body, {n: fs for n, fs in names.items() if inside.Contains(fs[0])})


def faceted(shape):
    """Does the shape hold faces with no surface — only triangles (a tessellated AP242 STEP)?"""
    return any(BRep_Tool.Surface_s(TopoDS.Face(f)) is None for f in _subshapes(shape, TopAbs_FACE))


def faceted_solids(shape, limit=None):
    """A tessellated STEP's closed bodies (its triangles, no exact surfaces) -> (solids made of their flat facets
    (mesh_solid), how many pieces did not close). limit: at most so many triangles in all (else KernelError)."""
    from OCP.TopAbs import TopAbs_SHELL
    pieces = list(_subshapes(shape, TopAbs_SOLID))
    ex = TopExp_Explorer(shape, TopAbs_SHELL, TopAbs_SOLID)  # (a shell of its own, not in a solid)
    while ex.More():
        pieces.append(ex.Current())
        ex.Next()
    tris = [np.concatenate([_face_triangles(TopoDS.Face(f)) for f in _subshapes(p, TopAbs_FACE)] or [np.zeros((0, 3, 3))]) for p in pieces]
    n = sum(len(t) for t in tris)
    if limit and n > limit:
        raise KernelError(f"MESH_TOO_BIG This tessellated STEP has {n} triangles — more than {limit} take too long to become a solid.")
    out, skipped = [], 0
    for t in tris:
        try:
            out.append(mesh_solid(t))
        except KernelError:
            skipped += 1
    return out, skipped


def from_step(data: bytes):
    fd, path = tempfile.mkstemp(suffix=".step")
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    try:
        r = STEPControl_Reader()
        if r.ReadFile(path) != IFSelect_RetDone:
            raise KernelError("The STEP file could not be read.")
        r.TransferRoots()
        return turned_out(r.OneShape())
    finally:
        os.unlink(path)


def write_brep(shape, path):
    """The shape to a file in OpenCASCADE's binary B-rep (exact; no mesh): a big file read once (filecache)."""
    from OCP.BinTools import BinTools, BinTools_FormatVersion
    if not BinTools.Write_s(shape, str(path), False, False, BinTools_FormatVersion.BinTools_FormatVersion_CURRENT):
        raise OSError(f"could not write {path}")


def read_brep(path):
    """A shape from write_brep's file: the same faces in the same order (0.3 s for a board whose STEP takes 15 s)."""
    from OCP.BinTools import BinTools
    from OCP.TopoDS import TopoDS_Shape
    shape = TopoDS_Shape()
    if not BinTools.Read_s(shape, str(path)) or shape.IsNull():
        raise OSError(f"could not read {path}")  # (filecache's own file: read the STEP again, nothing to tell)
    return shape


def _read_xcaf(data: bytes, kind="step", files=None):
    """A STEP (or IGES: kind "iges") file read with its names, colours and assembly tree -> (the XCAF document, its
    shape tool). Keep the document while its labels are used. files {name: bytes}: the part files an assembly STEP
    refers to (external references: CATIA writes an assembly so) — put beside it, read with it."""
    from OCP.IGESCAFControl import IGESCAFControl_Reader
    from OCP.STEPCAFControl import STEPCAFControl_Reader
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDocStd import TDocStd_Document
    from OCP.XCAFDoc import XCAFDoc_DocumentTool
    # (a folder of its own: OpenCASCADE looks for referenced files beside the file — only those given are there)
    with tempfile.TemporaryDirectory(prefix="a3d-") as tmp:
        path = os.path.abspath(os.path.join(tmp, "__a3d_main" + (".igs" if kind == "iges" else ".step")))
        with open(path, "wb") as fh:
            fh.write(data)
        for name, blob in (files or {}).items():
            base = os.path.basename(str(name).replace("\\", "/"))
            if base and not base.startswith("__a3d_main"):
                with open(os.path.join(tmp, base), "wb") as fh:
                    fh.write(blob)
        doc = TDocStd_Document(TCollection_ExtendedString(kind))
        r = IGESCAFControl_Reader() if kind == "iges" else STEPCAFControl_Reader()
        r.SetColorMode(True)
        r.SetNameMode(True)
        if r.ReadFile(path) != IFSelect_RetDone:
            raise KernelError(f"The {kind.upper()} file could not be read.")
        r.Transfer(doc)
    return doc, XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())


def external_refs(data: bytes):
    """The part files a STEP refers to (external references: DOCUMENT_FILE('TAIL.stp' …), CATIA's assemblies) ->
    their names, in the file's order; [] for a file that holds all its geometry."""
    text = data.decode("latin-1", errors="replace")
    out = []
    for m in re.finditer(r"DOCUMENT_FILE\s*\(\s*'([^']+)'", text, re.I):
        name = m.group(1).strip()
        if re.search(r"\.(stp|step|p21)$", name, re.I) and name not in out:
            out.append(name)
    return out


def _label_colour(label):
    """A label's own colour (surface, else generic) -> "#rrggbb" or None."""
    from OCP.Quantity import Quantity_Color
    from OCP.XCAFDoc import XCAFDoc_ColorTool, XCAFDoc_ColorType
    if label is None or label.IsNull():
        return None
    col = Quantity_Color()
    for kind in (XCAFDoc_ColorType.XCAFDoc_ColorSurf, XCAFDoc_ColorType.XCAFDoc_ColorGen):
        if XCAFDoc_ColorTool.GetColor_s(label, kind, col):
            return "#%02x%02x%02x" % tuple(round(max(0.0, min(1.0, v)) * 255) for v in (col.Red(), col.Green(), col.Blue()))
    return None


def _label_name(label):
    """A label's name ("" when it has none, or only the text of the program that wrote the file)."""
    from OCP.TDataStd import TDataStd_Name
    if label is None or label.IsNull() or not label.IsAttribute(TDataStd_Name.GetID_s()):
        return ""  # (FindAttribute on a label without a name crashes the process: CATIA's AP242 has such assemblies)
    a = TDataStd_Name()
    if label.FindAttribute(TDataStd_Name.GetID_s(), a):
        n = a.Get().ToExtString().strip()
        return "" if n.startswith("Open CASCADE STEP translator") else n
    return ""


def _label_key(label):
    from OCP.TCollection import TCollection_AsciiString
    from OCP.TDF import TDF_Tool
    e = TCollection_AsciiString()
    TDF_Tool.Entry_s(label, e)
    return e.ToCString()


def _m16(loc):
    """A location -> its 4 x 4 matrix, column-major (as three.js stores it); the inverse of placed()."""
    t = loc.Transformation()
    m = [0.0] * 16
    for r in range(3):
        for c in range(4):
            m[c * 4 + r] = t.Value(r + 1, c + 1)
    m[15] = 1.0
    return [0.0 if abs(v) < 1e-15 else v for v in m]


def _components(st, label):
    from OCP.collections import Sequence_TDF_Label
    from OCP.TDF import TDF_Label
    comps = Sequence_TDF_Label()
    st.GetComponents_s(label, comps, False)
    out = []
    for i in range(1, comps.Length() + 1):
        c, ref = comps.Value(i), TDF_Label()
        if st.GetReferredShape_s(c, ref) and not ref.IsNull():  # (a component pointing nowhere: skipped)
            out.append((c, ref))
    return out


def _free_labels(st):
    from OCP.collections import Sequence_TDF_Label
    free = Sequence_TDF_Label()
    st.GetFreeShapes(free)
    return [free.Value(i) for i in range(1, free.Length() + 1)]


def step_structure(st, free=None):
    """How the file is built: {parts (different ones), placements (of parts, all levels), subs (sub-assemblies)} —
    {parts: 1, placements: 1} for a plain one-body STEP. A product with no faces (Pro/E writes an empty one beside
    each solid) is not counted, nor a sub-assembly holding none: the count is what opening it as an assembly gives."""
    parts, subs, n, empty = set(), set(), [0], {}

    def has_faces(label):
        k = _label_key(label)
        if k not in empty:
            empty[k] = face_count(st.GetShape_s(label)) == 0
        return not empty[k]

    def walk(label):
        if st.IsAssembly_s(label):
            got = 0
            for _, ref in _components(st, label):
                inner = walk(ref)
                if inner and st.IsAssembly_s(ref):
                    subs.add(_label_key(ref))
                got += inner
            return got
        if not has_faces(label):
            return 0
        parts.add(_label_key(label))
        n[0] += 1
        return 1

    for lb in _free_labels(st) if free is None else free:
        walk(lb)
    return {"parts": len(parts), "placements": n[0], "subs": len(subs)}


def read_step_tree(data: bytes, files=None):
    """A STEP assembly as its tree: {root, parts: {key: {name, shape, colours {face index: "#rrggbb"}}},
    assemblies: {key: {name, instances: [{ref, name, matrix: [16], colour?}]}}} — each different part once (placed
    several times: one part, several instances), sub-assemblies nested. Several top shapes go under one root. files:
    the part files it refers to (as for _read_xcaf)."""
    from OCP.collections import Sequence_TDF_Label
    doc, st = _read_xcaf(data, files=files)  # noqa: F841 — (the document holds the labels)
    parts, asms = {}, {}

    def part(label):
        k = _label_key(label)
        if k in parts:
            return k
        shape = turned_out(st.GetShape_s(label))  # (an inside-out solid: turned the right way)
        found = []  # (sub-shape, colour): later ones (a body's, a face's) win
        c = _label_colour(label)
        if c:
            found.append((shape, c))
        subs = Sequence_TDF_Label()
        st.GetSubShapes_s(label, subs)
        for i in range(1, subs.Length() + 1):
            sc = _label_colour(subs.Value(i))
            if sc:
                found.append((st.GetShape_s(subs.Value(i)), sc))
        fm, colours = _face_map(shape), {}
        for s, col in sorted(found, key=lambda x: int(x[0].ShapeType())):  # a solid's colour, then its faces'
            ex = TopExp_Explorer(s, TopAbs_FACE)
            while ex.More():
                j = fm.FindIndex(ex.Current())
                if j:
                    colours[j - 1] = col
                ex.Next()
        parts[k] = {"name": _label_name(label) or f"Part {len(parts) + 1}", "shape": shape, "colours": colours}
        return k

    def assembly(label, name=None):
        k = _label_key(label)
        if k in asms:
            return k
        asms[k] = {"name": name or _label_name(label) or f"Assembly {len(asms) + 1}", "instances": []}
        for comp, ref in _components(st, label):
            sub = assembly(ref) if st.IsAssembly_s(ref) else part(ref)
            own = _label_name(comp)
            inst = {"ref": sub, "matrix": _m16(st.GetLocation_s(comp)), "name": own if own and not own.startswith("=>") else ""}
            c = _label_colour(comp)
            if c:
                inst["colour"] = c
            asms[k]["instances"].append(inst)
        return k

    from OCP.TopLoc import TopLoc_Location
    free = _free_labels(st)
    if len(free) == 1 and st.IsAssembly_s(free[0]):
        root = assembly(free[0])
    else:  # several top shapes (bodies side by side): one root holding them where they are
        root = "root"
        asms[root] = {"name": "", "instances": []}
        for lb in free:
            loc = TopLoc_Location()
            asms[root]["instances"].append({"ref": assembly(lb) if st.IsAssembly_s(lb) else part(lb), "matrix": _m16(loc), "name": ""})
    return _fold({"root": root, "parts": parts, "assemblies": asms})


def merged_step(data: bytes, files, name="assembly"):
    """An assembly STEP whose parts are files of their own (external references) and those files ({name: bytes}) ->
    one STEP that holds them all: its tree, names, placements and colours (then it opens as any other)."""
    tree = read_step_tree(data, files)
    parts = {}
    for k, p in tree["parts"].items():
        if face_count(p["shape"]):
            fm = _face_map(p["shape"])
            parts[k] = {"name": p["name"], "shape": p["shape"], "colours": [(fm.FindKey(i + 1), c) for i, c in p["colours"].items()]}
    if not parts:
        raise KernelError("The file has no solid in it.")
    asms = {k: {**a, "instances": [i for i in a["instances"] if i["ref"] in parts or i["ref"] in tree["assemblies"]]}
            for k, a in tree["assemblies"].items()}
    return write_step_tree(parts, asms, tree["root"], name)


def _fold(tree):
    """A sub-assembly holding a single placement (an ECAD board wraps each component so: 2388 of them) is not kept:
    its part goes straight into the parent, the two placements multiplied; assemblies no longer used are dropped."""
    asms = tree["assemblies"]
    one = lambda k: k in asms and len(asms[k]["instances"]) == 1  # noqa: E731
    for a in asms.values():
        for inst in a["instances"]:
            while one(inst["ref"]):
                child = asms[inst["ref"]]["instances"][0]
                m = np.asarray(inst["matrix"], float).reshape(4, 4, order="F") @ np.asarray(child["matrix"], float).reshape(4, 4, order="F")
                inst.update(ref=child["ref"], matrix=[float(v) for v in m.reshape(-1, order="F")],
                            name=inst.get("name") or child.get("name") or asms[inst["ref"]]["name"])
                if child.get("colour") and not inst.get("colour"):
                    inst["colour"] = child["colour"]
    used, todo = set(), [tree["root"]]
    while todo:
        k = todo.pop()
        if k in used:
            continue
        used.add(k)
        todo += [i["ref"] for i in asms.get(k, {}).get("instances", [])]
    tree["assemblies"] = {k: a for k, a in asms.items() if k in used}
    tree["parts"] = {k: p for k, p in tree["parts"].items() if k in used}
    return tree


def turned_out(shape):
    """The shape with every solid that is inside out (its faces facing in: a negative volume) turned the right way —
    as the STEP reader's healing leaves some (CATIA's S1 head, read back from a STEP made of it). The faces stay the
    same faces, in the same order (their colours are kept); a shape with none comes back as it is. (By the volume's
    sign: OpenCASCADE's "is a far point inside" test is wrong on that head — the cause of the reader's mistake.)"""
    from OCP.BRep import BRep_Builder
    from OCP.BRepTools import BRepTools_ReShape
    from OCP.TopoDS import TopoDS_Iterator, TopoDS_Solid
    rs, b, n = BRepTools_ReShape(), BRep_Builder(), 0
    for s in _subshapes(shape, TopAbs_SOLID):
        it = TopoDS_Iterator(s)
        turned = False
        while it.More() and not turned:  # (only a solid whose shell is stored reversed — as the reader leaves such
            turned = it.Value().Orientation() == TopAbs_REVERSED  # solids — is measured: 5 000 volumes took 25 s)
            it.Next()
        if not turned:
            continue
        p = GProp_GProps()
        BRepGProp.VolumeProperties_s(s, p)  # (the quick rule: its sign is all that counts here)
        if not p.Mass() < 0:
            continue
        bare, new = s.Located(TopLoc_Location()), TopoDS_Solid()
        b.MakeSolid(new)
        it = TopoDS_Iterator(bare, False, False)
        while it.More():
            b.Add(new, it.Value().Reversed())
            it.Next()
        new.Location(s.Location())
        new.Orientation(s.Orientation())
        rs.Replace(s, new)
        n += 1
    return rs.Apply(shape) if n else shape


def _xcaf_tree(parts, assemblies, root, finish=False):
    """An assembly as an XCAF document (what the STEP / IGES / glTF writers take) -> the document. parts {key: {name,
    shape, colour?, colours?: [(face, "#rrggbb")], finish?: (metalness, roughness)}} (one product each), assemblies
    {key: {name, instances: [{ref, name?, matrix: [16], colour?}]}} (sub-assemblies stay nested), root: the top
    assembly's key. finish: each part also gets a PBR material (its colour, metalness, roughness: for glTF)."""
    from OCP.Quantity import Quantity_Color, Quantity_ColorRGBA, Quantity_TOC_RGB
    from OCP.TCollection import TCollection_AsciiString, TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDocStd import TDocStd_Document
    from OCP.XCAFDoc import XCAFDoc_ColorType, XCAFDoc_DocumentTool, XCAFDoc_VisMaterial, XCAFDoc_VisMaterialPBR
    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    st, ct = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main()), XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
    mt = XCAFDoc_DocumentTool.VisMaterialTool_s(doc.Main()) if finish else None

    def colour(hexa):
        h = str(hexa or "").lstrip("#")
        if not re.fullmatch(r"[0-9a-fA-F]{6}", h):
            return None
        return Quantity_Color(*(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)), Quantity_TOC_RGB)

    def named(label, text):
        if text:
            TDataStd_Name.Set_s(label, TCollection_ExtendedString(str(text), True))  # (True: the text is UTF-8, not Latin-1)
        return label

    labels = {}

    def label_of(k, seen=()):
        if k in labels:
            return labels[k]
        if k in parts:
            p = parts[k]
            lb = named(st.AddShape(p["shape"], False, False), p.get("name") or k)
            c = colour(p.get("colour"))
            if c and mt is None:  # (glTF: the colour is in its material — a colour on the part beat a placement's own)
                ct.SetColor(lb, c, XCAFDoc_ColorType.XCAFDoc_ColorGen)
            if mt is not None:  # glTF: the part's look as a PBR material (a metal shines, a plastic does not)
                pbr = XCAFDoc_VisMaterialPBR()
                pbr.BaseColor = Quantity_ColorRGBA(c or Quantity_Color(0.85, 0.87, 0.9, Quantity_TOC_RGB), 1.0)
                pbr.Metallic, pbr.Roughness = map(float, p.get("finish") or (0.05, 0.55))
                pbr.IsDefined = True
                vm = XCAFDoc_VisMaterial()
                vm.SetPbrMaterial(pbr)
                mt.SetShapeMaterial(lb, mt.AddMaterial(vm, TCollection_AsciiString(str(p.get("name") or k))))
            for face, fc in p.get("colours") or []:
                c = colour(fc)
                sub = st.AddSubShape(lb, face) if c else None
                if sub is not None and not sub.IsNull():
                    ct.SetColor(sub, c, XCAFDoc_ColorType.XCAFDoc_ColorSurf)
        elif k in assemblies and k not in seen:
            a = assemblies[k]
            lb = named(st.NewShape(), a.get("name") or k)
            for inst in a.get("instances") or []:
                ref = label_of(inst["ref"], (*seen, k))
                if ref is None:
                    continue
                comp = st.AddComponent(lb, ref, TopLoc_Location(_trsf(inst.get("matrix") or [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1])))
                named(comp, inst.get("name"))
                c = colour(inst.get("colour"))
                if c:
                    ct.SetColor(comp, c, XCAFDoc_ColorType.XCAFDoc_ColorGen)
        else:
            return None
        labels[k] = lb
        return lb

    if root is None:  # no tree: every part a shape of its own (an IGES file's bodies)
        for k in parts:
            label_of(k)
    elif label_of(root) is None:
        raise KernelError("The assembly is empty — insert parts first.")
    st.UpdateAssemblies()
    return doc


def _flat(parts, assemblies, root):
    """An assembly's parts each where it is placed (all levels) -> parts as for _xcaf_tree, one per placement: named by
    the path of its placements ("Post pair-2/Post-1"), copied there, its colour as a STEP reader finds it (the
    placement's own, else the part's, else a sub-assembly placement's around it)."""
    out = {}

    def walk(k, loc, path, inherited, seen):
        for i, inst in enumerate((assemblies.get(k) or {}).get("instances") or []):
            ref, c = inst["ref"], inst.get("colour")
            here = loc.Multiplied(TopLoc_Location(_trsf(inst.get("matrix") or [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1])))
            name = "/".join([*path, str(inst.get("name") or (parts.get(ref) or assemblies.get(ref) or {}).get("name") or ref)])
            if ref in parts:
                p = parts[ref]
                # (copied there, not moved: IGES finds a face's colour only on a face with no location, and the faces a
                # part placed twice shares took one placement's colour for both)
                op = BRepBuilderAPI_Transform(p["shape"], here.Transformation(), True)
                out[f"{len(out)}"] = {"name": name, "shape": op.Shape(), "colour": c or p.get("colour") or inherited,
                                      "colours": [(op.ModifiedShape(f), fc) for f, fc in p.get("colours") or []]}
            elif ref in assemblies and ref not in seen:
                walk(ref, here, [*path, name.rsplit("/", 1)[-1]], c or inherited, (*seen, ref))

    if root in parts:
        return {root: parts[root]}
    walk(root, TopLoc_Location(), [], None, (root,))
    if not out:
        raise KernelError("The assembly is empty — insert parts first.")
    return out


def _written(write, suffix):
    """A writer's file (write(path) -> ok) as bytes."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    try:
        if not write(path):
            raise KernelError(f"The {suffix[1:].upper()} file could not be written.")
        with open(path, "rb") as fh:
            return fh.read()
    finally:
        os.unlink(path)


def write_step_tree(parts, assemblies, root, name="assembly"):
    """An assembly as a structured STEP (AP214, read by SolidWorks, CATIA, Solid Edge as an assembly tree): parts,
    assemblies and root as for _xcaf_tree."""
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    doc = _xcaf_tree(parts, assemblies, root)
    # (the settings set for this file only: they are the whole process's — the next part's STEP kept this one's name)
    with _settings({"write.step.schema": "AP214IS", "write.step.unit": "MM", "write.step.product.name": str(name or "assembly")}):
        w = STEPCAFControl_Writer()
        w.SetColorMode(True)
        w.SetNameMode(True)
        if not w.Transfer(doc, STEPControl_AsIs):
            raise KernelError("The assembly could not be made a STEP file.")
        return _step_ascii(_written(lambda path: w.Write(path) == IFSelect_RetDone, ".step"))


def write_iges_tree(parts, assemblies, root):
    """An assembly as one IGES file (5.3, B-rep solids, mm): every part placed, a body each with its name (the path of
    its placements: "Post pair-2/Post-1") and colours — IGES has no assembly tree, so a CAD program opens it as one
    part of several bodies."""
    return _iges(_flat(parts, assemblies, root))


def _iges(parts, surfaces=False):
    """Parts (as for _xcaf_tree, already placed) as one IGES file, a body each named in ASCII (IGES's strings: the
    entity's label, 8 characters, and its full name as a Name property), with its colour and its faces' colours."""
    from OCP.IGESCAFControl import IGESCAFControl_Writer
    from OCP.IGESControl import IGESControl_Controller
    doc = _xcaf_tree({k: {**p, "name": _ascii(p.get("name")) or "part"} for k, p in parts.items()}, {}, None)
    IGESControl_Controller.Init_s()  # (the IGES settings exist only once it is set up: else B-rep mode is ignored)
    with _settings({"write.iges.brep.mode": 0 if surfaces else 1, "write.iges.unit": "MM"}):
        w = IGESCAFControl_Writer()
        w.SetColorMode(True)
        w.SetNameMode(True)
        if not w.Transfer(doc):
            raise KernelError("The part could not be made an IGES file." if len(parts) == 1 else "The assembly could not be made an IGES file.")
        return _written(lambda path: w.Write(path), ".igs")


def write_gltf_tree(parts, assemblies, root):
    """An assembly (or one part) as a binary glTF (.glb) for viewers and rendering: a node per placed part with its
    name, sub-assemblies nested, a PBR material per part (its colour, metalness, roughness: parts {…, finish}), the
    face colours of an imported file; metres, Y up (glTF's own). Parts, assemblies and root as for _xcaf_tree."""
    from OCP.collections import IndexedDataMap_TCollection_AsciiString_TCollection_AsciiString as FileInfo
    from OCP.Message import Message_ProgressRange
    from OCP.RWGltf import RWGltf_CafWriter, RWGltf_WriterTrsfFormat_Compact
    from OCP.RWMesh import RWMesh_CoordinateSystem_Zup, RWMesh_NameFormat_InstanceOrProduct, RWMesh_NameFormat_Product
    from OCP.TCollection import TCollection_AsciiString
    for p in parts.values():  # each part meshed once, as finely as the viewer's
        bb = bbox(p["shape"]) or [0, 0, 0, 1, 1, 1]
        size = max(bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2], 1e-6)
        BRepMesh_IncrementalMesh(p["shape"], max(size * 0.0008, 0.002), False, 0.25, True)
    doc = _xcaf_tree(parts, assemblies, root, finish=True)

    def write(path):
        w = RWGltf_CafWriter(TCollection_AsciiString(path), True)
        conv = w.ChangeCoordinateSystemConverter()
        conv.SetInputLengthUnit(0.001)  # mm -> m
        conv.SetInputCoordinateSystem(RWMesh_CoordinateSystem_Zup)
        w.SetTransformationFormat(RWGltf_WriterTrsfFormat_Compact)
        w.SetNodeNameFormat(RWMesh_NameFormat_InstanceOrProduct)
        w.SetMeshNameFormat(RWMesh_NameFormat_Product)
        return w.Perform(doc, FileInfo(), Message_ProgressRange())
    return _written(write, ".glb")


def to_step_coloured(shape, colours, name="part"):
    """One part as a STEP file with its face colours ({face index: "#rrggbb"}, as read_step_colours gives them)."""
    fm = _face_map(shape)
    return to_step(shape, name, colours=[(fm.FindKey(k + 1), c) for k, c in colours.items()])


def read_step_colours(data: bytes, summary=False, kind="step", files=None):
    """A STEP with its colours: (shape, {face index (0-based, in _face_map(shape)): "#rrggbb"}). The colours of
    components, bodies and faces are followed down the file's assembly tree (a face's own colour wins). summary:
    also how the file is built (step_structure). kind "iges": an IGES file, read the same way. files: the part files
    it refers to (as for _read_xcaf)."""
    from OCP.collections import Sequence_TDF_Label
    from OCP.TDF import TDF_Label
    from OCP.TopoDS import TopoDS_Compound
    from OCP.BRep import BRep_Builder
    doc, st = _read_xcaf(data, kind, files)  # noqa: F841 — (the document holds the labels)
    free = Sequence_TDF_Label()
    st.GetFreeShapes(free)
    shapes = [st.GetShape_s(free.Value(i)) for i in range(1, free.Length() + 1)]
    if len(shapes) == 1:
        shape = shapes[0]
    else:
        shape, b = TopoDS_Compound(), BRep_Builder()
        b.MakeCompound(shape)
        for s in shapes:
            b.Add(shape, s)
    own = _label_colour
    found = []  # (located shape, colour): later (deeper) ones win

    def walk(label, inherited, loc):
        c = own(label) or inherited
        if st.IsReference_s(label):  # a component: placed, its own colour over its part's
            ref = TDF_Label()
            if not st.GetReferredShape_s(label, ref) or ref.IsNull():
                return
            walk_part(ref, c if own(label) else (own(ref) or inherited), loc.Multiplied(st.GetLocation_s(label)))
        else:
            walk_part(label, c, loc)

    def walk_part(label, c, loc):
        if st.IsAssembly_s(label):
            comps = Sequence_TDF_Label()
            st.GetComponents_s(label, comps, False)
            for i in range(1, comps.Length() + 1):
                walk(comps.Value(i), c, loc)
            return
        if c:
            found.append((st.GetShape_s(label).Moved(loc), c))
        subs = Sequence_TDF_Label()
        st.GetSubShapes_s(label, subs)
        for i in range(1, subs.Length() + 1):
            sc = own(subs.Value(i))
            if sc:
                found.append((st.GetShape_s(subs.Value(i)).Moved(loc), sc))

    from OCP.TopLoc import TopLoc_Location
    for i in range(1, free.Length() + 1):
        walk(free.Value(i), None, TopLoc_Location())
    shape = turned_out(shape)  # (an inside-out solid: turned the right way — the same faces)
    fm, colours = _face_map(shape), {}
    for s, c in found:
        ex = TopExp_Explorer(s, TopAbs_FACE)
        while ex.More():
            k = fm.FindIndex(ex.Current())
            if k:
                colours[k - 1] = c
            ex.Next()
    if summary:
        return shape, colours, step_structure(st, [free.Value(i) for i in range(1, free.Length() + 1)])
    return shape, colours


def to_obj(tess, name="part") -> bytes:
    """Wavefront OBJ (mm) from tessellate() output: one object, its corners shared between triangles, normals per
    corner of each face — for 3D programs, renderers and slicers that take OBJ."""
    tri = np.frombuffer(tess["positions"], np.float32).reshape(-1, 3, 3).astype(float)
    pts, idx = np.unique(np.round(tri.reshape(-1, 3), 6), axis=0, return_inverse=True)
    idx = idx.reshape(-1, 3) + 1
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    n = np.divide(n, ln, out=np.zeros_like(n), where=ln > 0)
    safe = re.sub(r"\s+", "_", str(name or "part")) or "part"
    out = [f"# Auto3DModeler — {len(tri)} triangles, mm", f"o {safe}"]
    out += [f"v {x:.6g} {y:.6g} {z:.6g}" for x, y, z in pts]
    out += [f"vn {x:.5f} {y:.5f} {z:.5f}" for x, y, z in n]
    out += [f"f {a}//{k} {b}//{k} {c}//{k}" for k, (a, b, c) in enumerate(idx.tolist(), 1)]
    return ("\n".join(out) + "\n").encode("utf-8")


def to_stl(tess) -> bytes:
    """Binary STL from tessellate() output (or from triangles (n, 3, 3))."""
    tri = np.asarray(tess, np.float32) if isinstance(tess, np.ndarray) else np.frombuffer(tess["positions"], np.float32).reshape(-1, 3, 3)
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    n = np.divide(n, ln, out=np.zeros_like(n), where=ln > 0)
    rec = np.zeros(len(tri), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    rec["n"], rec["v"] = n, tri
    return b"Auto3DModeler".ljust(80, b" ") + np.uint32(len(tri)).tobytes() + rec.tobytes()
