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

import math
import os
import tempfile

import numpy as np
import OCP.collections as _C
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
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
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
from OCP.GProp import GProp_GProps
from OCP.gp import gp_Ax1, gp_Ax2, gp_Circ, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
from OCP.IFSelect import IFSelect_RetDone
from OCP.Interface import Interface_Static
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Reader, STEPControl_Writer
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_REVERSED, TopAbs_SOLID, TopAbs_VERTEX
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS

ShapeMap = _C.IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher


class KernelError(Exception):
    """A modelling step that cannot be built (shown to the user as the feature's issue)."""


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


def combine(body, tool, op):
    """body ∪ tool or body − tool, names of both carried over."""
    if body is None:
        if op == "cut":
            raise KernelError("There is nothing to cut yet — make the first extrude “Add material”.")
        return tool
    mk = (BRepAlgoAPI_Cut if op == "cut" else BRepAlgoAPI_Fuse)(body.shape, tool.shape)
    if not mk.IsDone():
        raise KernelError("The solid operation failed.")
    res = mk.Shape()
    names = _carry(mk, body.names, res)
    for n, fs in _carry(mk, tool.names, res).items():
        names.setdefault(n, []).extend(fs)
    return Body(res, names)


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
    rm = _face_map(res)
    for k, e in enumerate(edges):
        for f in mk.Generated(e):
            if rm.Contains(f):
                names.setdefault(f"{fid}:{kind}:{k}", []).append(f)
    return Body(res, names)


def plane_of(face):
    """A planar face -> (its centre, outward normal) or None."""
    face = TopoDS.Face(face)  # names hold faces as plain shapes (from OpenCASCADE's history)
    s = BRepAdaptor_Surface(face, True)
    if s.GetType() != GeomAbs_Plane:
        return None
    d = s.Plane().Axis().Direction()
    n = np.array([d.X(), d.Y(), d.Z()])
    if face.Orientation() == TopAbs_REVERSED:
        n = -n
    p = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, p)
    c = p.CentreOfMass()
    return np.array([c.X(), c.Y(), c.Z()]), n


# ------------------------------------------------------------------ queries
def volume(shape):
    p = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, p)
    return p.Mass()


HEAVY_FACES = 3000  # an imported model with more faces than this is handled more roughly (else minutes per step)


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


def tessellate(body):
    """Triangles for the viewer with one face id per triangle, every face (name, plane frame for sketching),
    and every edge (polyline, the two faces it joins, its middle)."""
    shape = body.shape
    bb = bbox(shape) or [0, 0, 0, 1, 1, 1]
    size = max(bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2], 1e-6)
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
    # a big imported model (thousands of faces): a coarser mesh, and only the edges that show at this size —
    # millions of triangles would freeze the browser (and take minutes here)
    heavy = fm.Extent() > HEAVY_FACES
    BRepMesh_IncrementalMesh(shape, max(size * (0.004 if heavy else 0.0008), 0.002), False, 0.6 if heavy else 0.25, True)
    names = _face_names(body, fm)
    pos, ids, faces = [], [], []
    for fi in range(fm.Extent()):
        f = TopoDS.Face(fm.FindKey(fi + 1))
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(f, loc)
        rev = f.Orientation() == TopAbs_REVERSED
        if tri is not None:
            tr = loc.Transformation()
            nodes = []
            for i in range(1, tri.NbNodes() + 1):
                p = tri.Node(i).Transformed(tr)
                nodes.append((p.X(), p.Y(), p.Z()))
            for i in range(1, tri.NbTriangles() + 1):
                a, b, c = tri.Triangle(i).Get()
                if rev:
                    b, c = c, b
                pos.extend(nodes[a - 1] + nodes[b - 1] + nodes[c - 1])
                ids.append(fi)
        on_face = None  # a point on the face (a triangle's middle — a ring's centre is not on it)
        if tri is not None and tri.NbTriangles():
            a, b, c = tri.Triangle(1).Get()
            on_face = np.mean([nodes[a - 1], nodes[b - 1], nodes[c - 1]], axis=0)
        if heavy:  # the face's area and middle from its triangles (the exact ones take long on 100 000 faces)
            t = np.asarray(pos[len(pos) - 9 * tri.NbTriangles():] if tri is not None else [], float).reshape(-1, 3, 3)
            ar = np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1) / 2 if len(t) else np.zeros(0)
            cm = (ar[:, None] * t.mean(axis=1)).sum(axis=0) / ar.sum() if ar.sum() > 0 else (t.reshape(-1, 3).mean(axis=0) if len(t) else np.zeros(3))
            info = _face_info(f, fi, rev, (float(ar.sum()), cm))
        else:
            info = _face_info(f, fi, rev)
        if info.get("type") == "plane" and on_face is not None and not heavy:
            _outward(shape, info, on_face, size)
        if fi in solid_of:
            info["solid"] = solid_of[fi]
        nm = names.get(fi, [])
        if nm:
            info["name"] = nm[-1]  # the latest name (e.g. the hole wall rather than the plate it was cut from)
            info["names"] = nm
            info["ref"] = {"name": nm[-1]}
        faces.append(info)
    edges = []
    for ei in range(1, em.Extent() + 1):
        e = TopoDS.Edge(em.FindKey(ei))
        try:
            c = BRepAdaptor_Curve(e)
            if heavy and _edge_len(c) < size * 0.01:
                continue
            d = GCPnts_TangentialDeflection(c, 0.5 if heavy else 0.2, max(size * (0.004 if heavy else 0.001), 0.002))
            pts = [d.Value(i) for i in range(1, d.NbPoints() + 1)]
        except Exception:  # noqa: BLE001 — a degenerate edge: nothing to draw
            continue
        if len(pts) < 2:
            continue
        edges.append({"pts": [round(v, 5) for p in pts for v in (p.X(), p.Y(), p.Z())], "faces": sorted(adj.get(ei, ())),
                      "mid": _round(_edge_mid(e), 5)})
    return {"positions": np.asarray(pos, np.float32).tobytes(), "face_ids": np.asarray(ids, np.uint32).tobytes(),
            "faces": faces, "edges": edges, "bbox": bb, "volume": volume(shape), "solids": solids(shape)}


def _outward(shape, info, point, size):
    """A flat face's normal made to point out of the solid: a point a hair along it, from a point on the face, must
    be outside (a revolved solid can come with its faces' orientation the other way round)."""
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.TopAbs import TopAbs_IN
    n = np.asarray(info["normal"], float)
    eps = max(size * 1e-4, 1e-4)
    q = np.asarray(point, float) + n * eps
    try:
        inside = BRepClass3d_SolidClassifier(shape, gp_Pnt(*map(float, q)), eps * 0.1).State() == TopAbs_IN
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


def _face_info(f, fi, rev, rough=None):
    s = BRepAdaptor_Surface(f, True)
    if rough:  # (area, centre) from the mesh
        info = {"id": fi, "area": rough[0], "centroid": _round(tuple(rough[1]))}
    else:
        p = GProp_GProps()
        BRepGProp.SurfaceProperties_s(f, p)
        c = p.CentreOfMass()
        info = {"id": fi, "area": p.Mass(), "centroid": _round((c.X(), c.Y(), c.Z()))}
    kind = s.GetType()
    if kind == GeomAbs_Plane:
        d = s.Plane().Axis().Direction()
        n = np.array([d.X(), d.Y(), d.Z()])
        if rev:
            n = -n
        info["type"] = "plane"
        info["normal"] = _round(n)
        # a sketch frame on this face: origin at its centre, x along the world axis closest to the face
        axes = np.eye(3)
        x = axes[int(np.argmin(np.abs(axes @ n)))]
        x = x - (x @ n) * n
        x /= np.linalg.norm(x)
        info["frame"] = {"o": info["centroid"], "x": _round(x), "n": _round(n)}
    elif kind == GeomAbs_Cylinder:
        info["type"] = "cylinder"
        cyl = s.Cylinder()
        info["radius"] = round(cyl.Radius(), 6)
        a = cyl.Axis()
        info["axis"] = {"o": _round((a.Location().X(), a.Location().Y(), a.Location().Z())), "d": _round((a.Direction().X(), a.Direction().Y(), a.Direction().Z()))}
    else:
        info["type"] = "other"
    return info


def project_edges(shape, look, right, up):
    """The visible and hidden edges of the shape seen along `look` (hidden-line removal) -> ([[(x, y)…]…], [[…]…])
    in mm, in the view's axes: x along `right`, y along `up`."""
    from OCP.BRepLib import BRepLib
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    from OCP.HLRAlgo import HLRAlgo_Projector
    from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
    from OCP.GeomAbs import GeomAbs_Line

    algo = HLRBRep_Algo()
    algo.Add(shape)
    # the projector looks against its axis' direction: the axis points at the viewer
    ax = gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(*[-c for c in look]), gp_Dir(*right))
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
            out.append(pts)
            ex.Next()
        return out

    visible = lines(hl.VCompound()) + lines(hl.OutLineVCompound()) + lines(hl.Rg1LineVCompound())
    hidden = lines(hl.HCompound()) + lines(hl.OutLineHCompound())
    return visible, hidden


def placed(shape, m16):
    """A shape moved by a 4 x 4 placement matrix (column-major, as three.js stores it; only rotation + move)."""
    m = list(map(float, m16))
    t = gp_Trsf()
    t.SetValues(m[0], m[4], m[8], m[12], m[1], m[5], m[9], m[13], m[2], m[6], m[10], m[14])
    return BRepBuilderAPI_Transform(shape, t, True).Shape()


def interference(shapes, min_volume=1e-3):
    """Where placed solids overlap: shapes [(key, shape)] -> [{a, b, volume (mm³), bbox (of the overlap)}], the
    biggest first. Parts whose boxes do not meet are not computed; touching faces (no volume) are not a clash."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    boxes = [(k, s, bbox(s)) for k, s in shapes]
    out = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            (ka, sa, ba), (kb, sb, bb) = boxes[i], boxes[j]
            if not ba or not bb or any(ba[k] >= bb[k + 3] - 1e-6 or bb[k] >= ba[k + 3] - 1e-6 for k in range(3)):
                continue
            mk = BRepAlgoAPI_Common(sa, sb)
            if not mk.IsDone():
                continue
            common = mk.Shape()
            v = volume(common)
            if v > min_volume:
                out.append({"a": ka, "b": kb, "volume": round(v, 3), "bbox": _round(bbox(common) or [], 3)})
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


def to_step(shape, name="part"):
    w = STEPControl_Writer()
    Interface_Static.SetCVal_s("write.step.schema", "AP214")
    Interface_Static.SetCVal_s("write.step.unit", "MM")
    w.Transfer(shape, STEPControl_AsIs)
    fd, path = tempfile.mkstemp(suffix=".step")
    os.close(fd)
    try:
        if w.Write(path) != IFSelect_RetDone:
            raise KernelError("The STEP file could not be written.")
        with open(path, "rb") as fh:
            return fh.read()
    finally:
        os.unlink(path)


def solid_body(shape, fid):
    """A solid made elsewhere (a STEP file, a quick part) as a body; its faces are named <fid>:f<k>."""
    fm = _face_map(shape)
    return Body(shape, {f"{fid}:f{k}": [fm.FindKey(k + 1)] for k in range(fm.Extent())})


def from_step(data: bytes):
    fd, path = tempfile.mkstemp(suffix=".step")
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    try:
        r = STEPControl_Reader()
        if r.ReadFile(path) != IFSelect_RetDone:
            raise KernelError("The STEP file could not be read.")
        r.TransferRoots()
        return r.OneShape()
    finally:
        os.unlink(path)


def read_step_colours(data: bytes):
    """A STEP with its colours: (shape, {face index (0-based, in _face_map(shape)): "#rrggbb"}). The colours of
    components, bodies and faces are followed down the file's assembly tree (a face's own colour wins)."""
    from OCP.collections import Sequence_TDF_Label
    from OCP.Quantity import Quantity_Color
    from OCP.STEPCAFControl import STEPCAFControl_Reader
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDF import TDF_Label
    from OCP.TDocStd import TDocStd_Document
    from OCP.TopoDS import TopoDS_Compound
    from OCP.BRep import BRep_Builder
    from OCP.XCAFDoc import XCAFDoc_ColorTool, XCAFDoc_ColorType, XCAFDoc_DocumentTool
    fd, path = tempfile.mkstemp(suffix=".step")
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    try:
        doc = TDocStd_Document(TCollection_ExtendedString("step"))
        r = STEPCAFControl_Reader()
        r.SetColorMode(True)
        if r.ReadFile(path) != IFSelect_RetDone:
            raise KernelError("The STEP file could not be read.")
        r.Transfer(doc)
    finally:
        os.unlink(path)
    st, ct = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main()), XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
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
    col = Quantity_Color()

    def own(label):
        for kind in (XCAFDoc_ColorType.XCAFDoc_ColorSurf, XCAFDoc_ColorType.XCAFDoc_ColorGen):
            if XCAFDoc_ColorTool.GetColor_s(label, kind, col):
                return "#%02x%02x%02x" % tuple(round(max(0.0, min(1.0, v)) * 255) for v in (col.Red(), col.Green(), col.Blue()))
        return None

    found = []  # (located shape, colour): later (deeper) ones win

    def walk(label, inherited, loc):
        c = own(label) or inherited
        if st.IsReference_s(label):  # a component: placed, its own colour over its part's
            ref = TDF_Label()
            st.GetReferredShape_s(label, ref)
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
    fm, colours = _face_map(shape), {}
    for s, c in found:
        ex = TopExp_Explorer(s, TopAbs_FACE)
        while ex.More():
            k = fm.FindIndex(ex.Current())
            if k:
                colours[k - 1] = c
            ex.Next()
    return shape, colours


def to_stl(tess) -> bytes:
    """Binary STL from tessellate() output."""
    tri = np.frombuffer(tess["positions"], np.float32).reshape(-1, 3, 3)
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    n = np.divide(n, ln, out=np.zeros_like(n), where=ln > 0)
    rec = np.zeros(len(tri), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    rec["n"], rec["v"] = n, tri
    return b"Auto3DModeler".ljust(80, b" ") + np.uint32(len(tri)).tobytes() + rec.tobytes()
