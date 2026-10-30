"""j-separse probe: Parasolid partition (.P_B from a .par) -> OCCT solid, via parasolid-kit's parsed B-rep.

usage: python -I j-separse-xt2occ.py <x_b file> <schema dir> [out.step|out.brep] [stl to compare]
Units: XT is in metres; output in mm.
"""
import sys, math, struct, os
sys.stdout.reconfigure(encoding="utf-8")
from parasolid_kit import read_brep
from OCP.gp import gp_Pnt, gp_Dir, gp_Ax3, gp_Ax2, gp_Circ, gp_Elips, gp_Lin, gp_Vec, gp_Trsf
from OCP.Geom import (Geom_Plane, Geom_CylindricalSurface, Geom_ConicalSurface, Geom_SphericalSurface,
                      Geom_ToroidalSurface, Geom_Circle, Geom_Ellipse, Geom_Line, Geom_BSplineCurve,
                      Geom_BSplineSurface)
from OCP.GeomAbs import GeomAbs_C2
from OCP.GeomAPI import GeomAPI_ProjectPointOnCurve, GeomAPI_ProjectPointOnSurf, GeomAPI_PointsToBSpline
from OCP.collections import Array1_gp_Pnt as TColgp_Array1OfPnt, Array2_gp_Pnt as TColgp_Array2OfPnt
from OCP.collections import Array1_double as TColStd_Array1OfReal, Array1_int as TColStd_Array1OfInteger, Array2_double as TColStd_Array2OfReal
from OCP.BRepBuilderAPI import (BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeWire,
                                BRepBuilderAPI_Sewing, BRepBuilderAPI_MakeSolid, BRepBuilderAPI_Transform)
from OCP.ShapeFix import ShapeFix_Face, ShapeFix_Shape, ShapeFix_Solid, ShapeFix_Wire
from OCP.TopoDS import TopoDS, TopoDS_Shape
from OCP.TopAbs import TopAbs_SHELL, TopAbs_FACE, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRep import BRep_Builder
from OCP.TopoDS import TopoDS_Shell, TopoDS_Compound

S = 1000.0  # m -> mm


def P(v):
    return gp_Pnt(v.x * S, v.y * S, v.z * S)


def D(v):
    return gp_Dir(v.x, v.y, v.z)


def ax3(o, z, x):
    return gp_Ax3(P(o), D(z), D(x))


def make_surface(sg, brep):
    d = sg.definition
    k = sg.kind.value
    if k == "plane":
        return Geom_Plane(ax3(d.point, d.normal, d.x_axis))
    if k == "cylinder":
        return Geom_CylindricalSurface(ax3(d.point, d.axis, d.x_axis), d.radius * S)
    if k == "cone":
        ang = math.atan2(d.sin_half_angle, d.cos_half_angle)
        return Geom_ConicalSurface(ax3(d.point, d.axis, d.x_axis), ang, d.radius * S)
    if k == "sphere":
        return Geom_SphericalSurface(ax3(d.center, d.axis, d.x_axis), d.radius * S)
    if k == "torus":
        return Geom_ToroidalSurface(ax3(d.center, d.axis, d.x_axis), d.major_radius * S, d.minor_radius * S)
    if k == "nurbs":
        return nurbs_surface(d)
    raise NotImplementedError(f"surface {k} {getattr(d, 'type_name', '')}")


def _knots(knots, mults):
    ka = TColStd_Array1OfReal(1, len(knots))
    ma = TColStd_Array1OfInteger(1, len(knots))
    for i, (kv, m) in enumerate(zip(knots, mults), 1):
        ka.SetValue(i, kv)
        ma.SetValue(i, m)
    return ka, ma


def nurbs_curve(d):
    n = d.control_vertex_count
    pts = TColgp_Array1OfPnt(1, n)
    w = TColStd_Array1OfReal(1, n)
    for i, cv in enumerate(d.control_vertices, 1):
        if d.rational:
            ww = cv[-1]
            pts.SetValue(i, gp_Pnt(cv[0] / ww * S, cv[1] / ww * S, cv[2] / ww * S))
            w.SetValue(i, ww)
        else:
            pts.SetValue(i, gp_Pnt(cv[0] * S, cv[1] * S, cv[2] * S))
    ka, ma = _knots(d.knots, d.knot_multiplicities)
    if d.rational:
        return Geom_BSplineCurve(pts, w, ka, ma, d.degree, d.periodic)
    return Geom_BSplineCurve(pts, ka, ma, d.degree, d.periodic)


def nurbs_surface(d):
    nu, nv = d.u_control_vertex_count, d.v_control_vertex_count
    pts = TColgp_Array2OfPnt(1, nu, 1, nv)
    w = TColStd_Array2OfReal(1, nu, 1, nv)
    cvs = d.control_vertices
    for i in range(nu):
        for j in range(nv):
            cv = cvs[i * nv + j]
            ww = cv[-1] if d.rational else 1.0
            pts.SetValue(i + 1, j + 1, gp_Pnt(cv[0] / ww * S, cv[1] / ww * S, cv[2] / ww * S))
            w.SetValue(i + 1, j + 1, ww)
    uk, um = _knots(d.u_knots, d.u_knot_multiplicities)
    vk, vm = _knots(d.v_knots, d.v_knot_multiplicities)
    return Geom_BSplineSurface(pts, w, uk, vk, um, vm, d.u_degree, d.v_degree, d.u_periodic, d.v_periodic)


def make_curve(cg):
    d = cg.definition
    k = cg.kind.value
    neg = cg.sense.value == "negative"
    if k == "line":
        dirv = gp_Dir(-d.direction.x, -d.direction.y, -d.direction.z) if neg else D(d.direction)
        return Geom_Line(P(d.point), dirv), False
    if k == "circle":
        n = gp_Dir(-d.normal.x, -d.normal.y, -d.normal.z) if neg else D(d.normal)
        return Geom_Circle(gp_Ax2(P(d.center), n, D(d.x_axis)), d.radius * S), True
    if k == "ellipse":
        n = gp_Dir(-d.normal.x, -d.normal.y, -d.normal.z) if neg else D(d.normal)
        return Geom_Ellipse(gp_Ax2(P(d.center), n, D(d.x_axis)), d.major_radius * S, d.minor_radius * S), True
    if k == "nurbs":
        c = nurbs_curve(d)
        if neg:
            c.Reverse()
        return c, c.IsPeriodic()
    if k == "intersection":
        pts = list(d.chart_points)
        if neg:
            pts = pts[::-1]
        arr = TColgp_Array1OfPnt(1, len(pts))
        for i, p in enumerate(pts, 1):
            arr.SetValue(i, P(p))
        return GeomAPI_PointsToBSpline(arr, 3, 8, GeomAbs_C2, 1e-4).Curve(), False
    raise NotImplementedError(f"curve {k}")


def build(path, schema_dir):
    pb = read_brep(open(path, "rb").read(), source_format="x-b", schema_dir=schema_dir)
    b = pb.brep
    stats = {"faces": 0, "face_fail": 0, "edge_fail": 0, "unsupported": [], "max_vtx_dev": 0.0}
    vpt = {v.id: P(b.points[v.point].position) for v in b.vertices}
    edges = {}
    for e in b.edges:
        try:
            c, periodic = make_curve(b.curves[e.curve])
            if e.start_vertex is None:
                me = BRepBuilderAPI_MakeEdge(c)
            else:
                p0, p1 = vpt[e.start_vertex], vpt[e.end_vertex]
                u0 = GeomAPI_ProjectPointOnCurve(p0, c).LowerDistanceParameter()
                u1 = GeomAPI_ProjectPointOnCurve(p1, c).LowerDistanceParameter()
                for p in (p0, p1):
                    stats["max_vtx_dev"] = max(stats["max_vtx_dev"], GeomAPI_ProjectPointOnCurve(p, c).LowerDistance())
                if periodic:
                    per = c.Period()
                    while u1 <= u0 + 1e-9:
                        u1 += per
                me = BRepBuilderAPI_MakeEdge(c, u0, u1)
            edges[e.id] = me.Edge() if me.IsDone() else None
            if not me.IsDone():
                stats["edge_fail"] += 1
        except NotImplementedError as ex:
            edges[e.id] = None
            stats["edge_fail"] += 1
            stats["unsupported"].append(str(ex))
    sew = BRepBuilderAPI_Sewing(1e-3)
    nfaces = 0
    for f in b.faces:
        sg = b.surfaces[f.surface]
        try:
            surf = make_surface(sg, b)
        except NotImplementedError as ex:
            stats["face_fail"] += 1
            stats["unsupported"].append(str(ex))
            continue
        # vertices must lie on the surface: checks our reading of the surface parameters
        for li in f.loops:
            for hi in b.loops[li].half_edges:
                e = b.edges[b.half_edges[hi].edge]
                for vi in (e.start_vertex, e.end_vertex):
                    if vi is not None:
                        stats["max_vtx_dev"] = max(stats["max_vtx_dev"], GeomAPI_ProjectPointOnSurf(vpt[vi], surf).LowerDistance())
        wires = []
        ok = True
        for li in f.loops:
            mw = BRepBuilderAPI_MakeWire()
            for hi in b.loops[li].half_edges:
                he = b.half_edges[hi]
                ed = edges.get(he.edge)
                if ed is None:
                    ok = False
                    break
                if he.sense.value == "negative":
                    ed = TopoDS.Edge(ed.Reversed())
                mw.Add(ed)
            if not ok or not mw.IsDone():
                ok = False
                break
            wires.append(mw.Wire())
        if not ok:
            stats["face_fail"] += 1
            continue
        if wires:
            mf = BRepBuilderAPI_MakeFace(surf, wires[0], True)
            for w in wires[1:]:
                mf.Add(w)
        else:
            mf = BRepBuilderAPI_MakeFace(surf, 1e-6)
        if not mf.IsDone():
            stats["face_fail"] += 1
            continue
        fx = ShapeFix_Face(mf.Face())
        try:
            fx.Perform()
            face = fx.Face()
        except Exception:
            stats['fix_fail'] = stats.get('fix_fail', 0) + 1
            face = mf.Face()
        if (f.sense.value == "negative") != (sg.sense.value == "negative"):
            face = TopoDS.Face(face.Reversed())
        # only faces of solid bodies' solid regions
        sew.Add(face)
        nfaces += 1
    stats["faces"] = nfaces
    sew.Perform()
    shp = sew.SewedShape()
    builder = BRep_Builder()
    comp = TopoDS_Compound()
    builder.MakeCompound(comp)
    exp = TopExp_Explorer(shp, TopAbs_SHELL)
    nsol = 0
    while exp.More():
        ms = BRepBuilderAPI_MakeSolid(TopoDS.Shell(exp.Current()))
        sf = ShapeFix_Solid(ms.Solid())
        sf.Perform()
        builder.Add(comp, sf.Solid())
        nsol += 1
        exp.Next()
    if nsol == 0:
        comp = shp
    return pb, comp, stats


def props(shape):
    g = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, g)
    bb = Bnd_Box()
    BRepBndLib.Add_s(shape, bb, False)
    nf = 0
    e = TopExp_Explorer(shape, TopAbs_FACE)
    while e.More():
        nf += 1
        e.Next()
    a, b = bb.CornerMin(), bb.CornerMax()
    return g.Mass(), (a.X(), a.Y(), a.Z(), b.X(), b.Y(), b.Z()), nf


def stl_props(path):
    d = open(path, "rb").read()
    n = struct.unpack_from("<I", d, 80)[0]
    vol = 0.0
    mn = [1e30] * 3
    mx = [-1e30] * 3
    for i in range(n):
        v = struct.unpack_from("<12f", d, 84 + 50 * i)
        a, b_, c = v[3:6], v[6:9], v[9:12]
        vol += (a[0] * (b_[1] * c[2] - b_[2] * c[1]) - a[1] * (b_[0] * c[2] - b_[2] * c[0]) + a[2] * (b_[0] * c[1] - b_[1] * c[0])) / 6
        for p in (a, b_, c):
            for k in range(3):
                mn[k] = min(mn[k], p[k]); mx[k] = max(mx[k], p[k])
    return vol, mn + mx, n


if __name__ == "__main__":
    pb, shape, stats = build(sys.argv[1], sys.argv[2])
    print("stats", stats)
    vol, bb, nf = props(shape)
    valid = BRepCheck_Analyzer(shape).IsValid()
    print(f"{os.path.basename(sys.argv[1])}: source faces={pb.summary.to_dict()['counts']['faces']} built faces={nf} "
          f"face_fail={stats['face_fail']} edge_fail={stats['edge_fail']} valid={valid} "
          f"volume={vol:.3f} mm3 bbox=({', '.join(f'{x:.3f}' for x in bb)}) max_vertex_dev={stats['max_vtx_dev']:.2e} mm "
          f"unsupported={sorted(set(stats['unsupported']))[:4]}")
    if len(sys.argv) > 3 and sys.argv[3] not in ("-", ""):
        out = sys.argv[3]
        if out.endswith(".step"):
            from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
            w = STEPControl_Writer()
            w.Transfer(shape, STEPControl_AsIs)
            w.Write(out)
        else:
            from OCP.BRepTools import BRepTools
            BRepTools.Write_s(shape, out)
    if len(sys.argv) > 4:
        v, bbs, n = stl_props(sys.argv[4])
        print(f"   STL: triangles={n} volume={v:.3f} mm3 bbox=({', '.join(f'{x:.3f}' for x in bbs)})")
