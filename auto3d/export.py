"""Export the solid (profile + 3D design layers) as STL and STEP AP214, both in mm.

All faces are planar (horizontal caps and vertical walls) so the STEP B-rep is
written directly, without a CAD kernel.
"""
from __future__ import annotations

import base64
import struct
from datetime import datetime, timezone

from .solid import Solid

UNIT_IN_MM = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4}


def build_solid(solution: dict, unit: str, layers=None) -> Solid:
    return Solid(solution, layers, unit)


def mesh_payload(solid) -> dict:
    """Compact mesh for the viewer (model units): base64 float32 positions + uint8 tags."""
    tris, tags = solid.triangles()
    flat = [c for tri in tris for p in tri for c in p]
    return {
        "positions": base64.b64encode(struct.pack(f"<{len(flat)}f", *flat)).decode(),
        "tags": base64.b64encode(bytes(tags)).decode(),
        "count": len(tris),
    }


# --------------------------------------------------------------------------- STL
def to_stl(solid, unit: str, name: str = "part") -> bytes:
    s = UNIT_IN_MM[unit]
    tris, _ = solid.triangles()
    out = bytearray(name.encode()[:80].ljust(80, b" "))
    out += struct.pack("<I", len(tris))
    for a, b, c in tris:
        a, b, c = ([v * s for v in p] for p in (a, b, c))
        u = [b[i] - a[i] for i in range(3)]
        v = [c[i] - a[i] for i in range(3)]
        n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
        ln = sum(x * x for x in n) ** 0.5 or 1.0
        out += struct.pack("<3f", *(x / ln for x in n))
        for p in (a, b, c):
            out += struct.pack("<3f", *p)
        out += b"\0\0"
    return bytes(out)


# --------------------------------------------------------------------------- STEP
def _f(v: float) -> str:
    s = f"{v:.6f}".rstrip("0")
    return s + "0" if s.endswith(".") else s


def _components(faces):
    """Group faces into connected shells (faces sharing an edge)."""
    parent = list(range(len(faces)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    owner = {}
    for fi, loops in enumerate(faces):
        for loop in loops:
            for i in range(len(loop)):
                a, b = loop[i], loop[(i + 1) % len(loop)]
                key = (a, b) if a < b else (b, a)
                if key in owner:
                    parent[find(fi)] = find(owner[key])
                else:
                    owner[key] = fi
    groups = {}
    for i in range(len(faces)):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def to_step(solid, unit: str, name: str = "part") -> bytes:
    s = UNIT_IN_MM[unit]
    r = lambda p: (round(p[0] * s, 9), round(p[1] * s, 9), round(p[2] * s, 9))

    faces, normals = [], []
    for kind, z, rings, normal, _tag in solid.faces():
        if kind == "cap":
            loops = [[r((x, y, z)) for x, y in ring] for ring in rings]
        else:
            loops = [[r(p) for p in rings[0]]]
        # drop consecutive duplicates (can appear after rounding)
        loops = [[p for i, p in enumerate(l) if p != l[i - 1]] for l in loops]
        faces.append(loops)
        normals.append(normal)

    lines: list[str] = []

    def A(text):
        lines.append(text)
        return f"#{len(lines)}"

    pts, vtx, edges = {}, {}, {}

    def cpt(p):
        if p not in pts:
            pts[p] = A(f"CARTESIAN_POINT('',({_f(p[0])},{_f(p[1])},{_f(p[2])}))")
        return pts[p]

    def vertex(p):
        if p not in vtx:
            vtx[p] = A(f"VERTEX_POINT('',{cpt(p)})")
        return vtx[p]

    def direction(d):
        return A(f"DIRECTION('',({_f(d[0])},{_f(d[1])},{_f(d[2])}))")

    def edge(p, q):
        if (q, p) in edges:
            return edges[(q, p)], False
        if (p, q) not in edges:
            d = [q[i] - p[i] for i in range(3)]
            ln = sum(x * x for x in d) ** 0.5
            vec = A(f"VECTOR('',{direction([x / ln for x in d])},{_f(ln)})")
            line = A(f"LINE('',{cpt(p)},{vec})")
            edges[(p, q)] = A(f"EDGE_CURVE('',{vertex(p)},{vertex(q)},{line},.T.)")
        return edges[(p, q)], True

    def loop(points):
        oes = []
        for i in range(len(points)):
            e, sense = edge(points[i], points[(i + 1) % len(points)])
            oes.append(A(f"ORIENTED_EDGE('',*,*,{e},{'.T.' if sense else '.F.'})"))
        return A(f"EDGE_LOOP('',({','.join(oes)}))")

    def plane(origin, normal, xdir):
        ax = A(f"AXIS2_PLACEMENT_3D('',{cpt(origin)},{direction(normal)},{direction(xdir)})")
        return A(f"PLANE('',{ax})")

    face_ids = []
    for loops, n in zip(faces, normals):
        bounds = [A(f"{'FACE_OUTER_BOUND' if i == 0 else 'FACE_BOUND'}('',{loop(l)},.T.)") for i, l in enumerate(loops)]
        o = loops[0][0]
        # reference direction in the face plane (must be perpendicular to the normal; faces of a
        # bent part can face any way)
        ref = (1.0, 0.0, 0.0) if abs(n[0]) < 0.9 else (0.0, 1.0, 0.0)
        d = sum(ref[i] * n[i] for i in range(3))
        xdir = tuple(ref[i] - d * n[i] for i in range(3))
        ln = sum(v * v for v in xdir) ** 0.5
        xdir = tuple(v / ln for v in xdir)
        face_ids.append(A(f"ADVANCED_FACE('',({','.join(bounds)}),{plane(o, n, xdir)},.T.)"))

    breps = []
    for i, comp in enumerate(_components(faces)):
        shell = A(f"CLOSED_SHELL('',({','.join(face_ids[j] for j in comp)}))")
        breps.append(A(f"MANIFOLD_SOLID_BREP('{name}{'' if i == 0 else f'_{i + 1}'}',{shell})"))

    length_u = A("(LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.))")
    angle_u = A("(NAMED_UNIT(*) PLANE_ANGLE_UNIT() SI_UNIT($,.RADIAN.))")
    solid_u = A("(NAMED_UNIT(*) SI_UNIT($,.STERADIAN.) SOLID_ANGLE_UNIT())")
    unc = A(f"UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-04),{length_u},'distance_accuracy_value','')")
    ctx = A(f"(GEOMETRIC_REPRESENTATION_CONTEXT(3) GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT(({unc})) "
            f"GLOBAL_UNIT_ASSIGNED_CONTEXT(({length_u},{angle_u},{solid_u})) "
            f"REPRESENTATION_CONTEXT('Context3D','3D Context with 0.0001 mm uncertainty'))")
    origin = A(f"AXIS2_PLACEMENT_3D('',{cpt((0.0, 0.0, 0.0))},{direction((0, 0, 1))},{direction((1, 0, 0))})")
    shape_rep = A(f"ADVANCED_BREP_SHAPE_REPRESENTATION('{name}',({','.join([origin] + breps)}),{ctx})")
    app = A("APPLICATION_CONTEXT('core data for automotive mechanical design processes')")
    A(f"APPLICATION_PROTOCOL_DEFINITION('international standard','automotive_design',2000,{app})")
    pctx = A(f"PRODUCT_CONTEXT('',{app},'mechanical')")
    prod = A(f"PRODUCT('{name}','{name}','',({pctx}))")
    A(f"PRODUCT_RELATED_PRODUCT_CATEGORY('part',$,({prod}))")
    pdctx = A(f"PRODUCT_DEFINITION_CONTEXT('part definition',{app},'design')")
    form = A(f"PRODUCT_DEFINITION_FORMATION('','',{prod})")
    pdef = A(f"PRODUCT_DEFINITION('design','',{form},{pdctx})")
    pds = A(f"PRODUCT_DEFINITION_SHAPE('','',{pdef})")
    A(f"SHAPE_DEFINITION_REPRESENTATION({pds},{shape_rep})")

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    header = (
        "ISO-10303-21;\nHEADER;\n"
        "FILE_DESCRIPTION(('Auto3DModeler part'),'2;1');\n"
        f"FILE_NAME('{name}.step','{stamp}',(''),(''),'Auto3DModeler','Auto3DModeler','');\n"
        "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));\nENDSEC;\nDATA;\n"
    )
    body = "".join(f"#{i + 1}={text};\n" for i, text in enumerate(lines))
    return (header + body + "ENDSEC;\nEND-ISO-10303-21;\n").encode("ascii")
