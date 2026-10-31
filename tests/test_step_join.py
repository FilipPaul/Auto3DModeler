"""Material joined onto / cut out of an imported STEP solid (the owner designs around bought parts): for each STEP in
samples/ToImportToOurApp (samples.json; files over 1 MB only with A3D_SLOW_SAMPLES=1: 2.5 min), a small circle sketched on its
largest flat face and extruded 5 mm — op add: the volume grows by π r² · 5, the part stays the same number of valid
solids with closed shells, STEP write → read keeps the volume; op cut: what of the part the 5 mm cylinder holds less
(the material under it, kernel.common as the check). The face: the largest flat one whose 5 mm above is free (in an
assembly the largest may be under another part). NIST CTC-01
and STC-06 failed every joined extrude ("The solid operation failed"): their STEP holds curves beside the solid, and
OpenCASCADE's fuse refuses a solid together with edges (kernel._beside_solids). Also kernel.combine's fuzzy second try.

Run:  py -m unittest tests.test_step_join -v
"""
import math
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from auto3d.modeler import available
from test_cad_samples import MANIFEST, SAMPLES, SLOW, skip_reason
from test_modeler_kernel import watertight

OCC = available("occ")
if OCC:
    from auto3d.modeler import blobs, doc, kernel as K

D = 5.0  # mm: the extrude
R = 2.0  # mm: the circle (smaller where the face has no room for it)
SIZE_LIMIT = 1_000_000  # bytes: bigger files only with A3D_SLOW_SAMPLES=1 (NIST FTC-08's 1739 facets alone: 105 s)


def spot(mesh, face):
    """A point well inside a flat face and the room around it: the middle of its roundest triangle as (u, v) of the
    face's sketch frame, and that triangle's inscribed radius."""
    tri = np.frombuffer(mesh["positions"], np.float32).reshape(-1, 3, 3).astype(float)
    t = tri[np.frombuffer(mesh["face_ids"], np.uint32) == face["id"]]
    a, b, c = (np.linalg.norm(t[:, i] - t[:, (i + 1) % 3], axis=1) for i in range(3))
    s = (a + b + c) / 2
    inr = np.sqrt(np.maximum(s * (s - a) * (s - b) * (s - c), 0)) / s
    k = int(np.argmax(inr))
    centre, fr = t[k].mean(axis=0), face["frame"]
    o, x, n = (np.asarray(fr[q], float) for q in ("o", "x", "n"))
    return [float((centre - o) @ x), float((centre - o) @ np.cross(n, x))], float(inr[k])


def steps(op, face, uv, r):
    return [{"id": "S9", "type": "sketch", "plane": {"face": {"name": face["name"]}, "frame": face["frame"]}, "points": {"c": uv},
             "entities": [{"id": "c1", "t": "circle", "c": "c", "r": r}]},
            {"id": "E9", "type": "extrude", "sketch": "S9", "op": op, "d": D}]


def valid(shape):
    from OCP.BRepCheck import BRepCheck_Analyzer
    return BRepCheck_Analyzer(shape).IsValid()


def closed(shape):
    """Every shell of the shape closed: each edge has a face on both sides (the B-rep is watertight)."""
    from OCP.TopAbs import TopAbs_SHELL
    return all(K.BRep_Tool.IsClosed_s(sh) for sh in K._subshapes(shape, TopAbs_SHELL))


def tool(face, uv, r, d):
    """The extrude's cylinder as the kernel makes it: the circle on the face's frame, d along its normal (− : into it)."""
    fr = face["frame"]
    cf, names = K.circle_face(fr, uv[0], uv[1], 2 * r)
    return K.prism_body(cf, names, np.asarray(fr["n"], float) * d, "T").shape


def common(shape, other):
    return K.volume(K.boolean("common", [shape], [other]))


def place(shape, mesh):
    """The largest flat face with room above it -> (face, (u, v), r): a circle of r (≤ R) inside it whose 5 mm cylinder
    out of it meets nothing of the part."""
    faces = sorted((f for f in mesh["faces"] if f.get("type") == "plane" and f.get("frame")), key=lambda f: -f["area"])
    for face in faces[:12]:
        uv, room = spot(mesh, face)
        r = min(R, 0.8 * room)
        if r > 0.05 and common(shape, tool(face, uv, r, D)) < 1e-6:
            return face, uv, r
    raise AssertionError("no flat face with room above it")


@unittest.skipUnless(OCC, "OCP not installed")
@unittest.skipUnless(MANIFEST["files"], "samples/ToImportToOurApp is not here")
class TestJoinOnStep(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.blobs = mock.patch.object(blobs, "DIR", Path(self.tmp.name))
        self.blobs.start()

    def tearDown(self):
        self.blobs.stop()
        self.tmp.cleanup()

    def check(self, item):
        p = SAMPLES / item["path"]
        r = doc.import_solid({"blob": blobs.put(p.read_bytes()), "name": p.name})
        solid = [{"id": "F1", "type": "solid", "blob": r["blob"], "file": p.name, "op": "add"}]
        built = doc.rebuild({"features": solid})
        before = doc.body_of({"features": solid}).body.shape
        v0, n0 = built["body"]["volume"], K.solids(before)
        face, uv, rr = place(before, built["body"])
        self.assertRegex(face["name"], r"^F1:f\d+$")
        area = math.pi * rr * rr
        noise = 2e-7 * v0 + 0.02 * area * D  # (B-spline volumes of a big part: integrated to ≈ 1e-7 of it)
        part = {"features": solid + steps("add", face, uv, rr)}
        added = doc.rebuild(part)
        self.assertTrue(added["ok"], added["features"])
        self.assertAlmostEqual(added["body"]["volume"] - v0, area * D, delta=noise)
        shape = doc.body_of(part).body.shape
        self.assertEqual(K.solids(shape), n0)
        self.assertTrue(valid(shape), "the joined part is a valid solid")
        self.assertTrue(closed(shape), "closed shells")
        if watertight(built["body"], apex=True):  # (the file's own mesh closed: so is the joined one's)
            self.assertTrue(watertight(added["body"], apex=True), "watertight")
        self.assertAlmostEqual(K.volume(K.from_step(doc.export(part, "step"))), added["body"]["volume"], delta=noise + 1e-6 * v0)
        # cut: what of the part the 5 mm cylinder into it holds (all of it under a thick face)
        cut = doc.rebuild({"features": solid + steps("cut", face, uv, rr)})
        self.assertTrue(cut["ok"], cut["features"])
        held = common(before, tool(face, uv, rr, -D))
        self.assertGreater(held, 0.1 * area * D)
        self.assertAlmostEqual(v0 - cut["body"]["volume"], held, delta=noise)
        cut_shape = doc.body_of({"features": solid + steps("cut", face, uv, rr)}).body.shape
        self.assertTrue(valid(cut_shape) and closed(cut_shape), "the cut part is a valid solid")


def _make(item):
    def test(self):
        reason = skip_reason(item)
        if not reason and not SLOW and (SAMPLES / item["path"]).stat().st_size > SIZE_LIMIT:
            reason = f"{item['path']} is over 1 MB (A3D_SLOW_SAMPLES=1 runs it)"
        if reason:
            self.skipTest(reason)
        self.check(item)
    test.__doc__ = f"{item['path']}: a Ø circle on its largest flat face, extruded 5 mm add and cut"
    return test


for _item in MANIFEST["files"]:
    if _item["kind"] in ("part", "assembly") and not (_item["expect"].get("error") or _item["expect"].get("alone_error")):
        _name = "test_" + "".join(c if c.isalnum() else "_" for c in Path(_item["path"]).stem).lower()
        setattr(TestJoinOnStep, _name, _make(_item))


@unittest.skipUnless(OCC, "OCP not installed")
class TestBesideSolids(unittest.TestCase):
    def test_curves_beside_the_solid(self):
        """A box and a loose edge in one compound (a STEP's wireframe beside its solid): the body is the box alone (its
        6 faces named F1:f0 … f5 as before); a joined box on it: one solid of both volumes."""
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
        box = BRepPrimAPI_MakeBox(10, 10, 10).Shape()
        edge = K.BRepBuilderAPI_MakeEdge(K.gp_Pnt(0, 0, 20), K.gp_Pnt(10, 0, 20)).Edge()
        both = K.compound([box, edge])
        with self.assertRaises(K.KernelError):  # (before: the fuse of a solid with an edge is refused)
            K.combine(K.Body(both), K.Body(BRepPrimAPI_MakeBox(K.gp_Pnt(0, 0, 10), 10, 10, 5).Shape()), "add")
        body = K.solid_body(both, "F1")
        self.assertEqual(sorted(body.names), [f"F1:f{k}" for k in range(6)])
        self.assertEqual(K._edges_of(body.shape).Extent(), 12)
        res = K.combine(body, K.Body(BRepPrimAPI_MakeBox(K.gp_Pnt(0, 0, 10), 10, 10, 5).Shape()), "add")
        self.assertEqual(K.solids(res.shape), 1)
        self.assertAlmostEqual(K.volume(res.shape), 1500, delta=1e-6)
        self.assertTrue(valid(res.shape))
        # whole (a 👁 reference body): kept as it is
        self.assertTrue(K.solid_body(both, "F1", whole=True).shape.IsSame(both))

    def test_parts_far_from_the_tool_stay(self):
        """An assembly body of three boxes, two overlapping each other by 250: a box joined on the third only — 3 solids,
        the volume grows by the new 4 × 4 × 5 box's 80 (the two overlapping ones are not merged); also when the tool sits
        inside the big one (it holds the tool: reached though no boundary is near)."""
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
        mk = lambda x, y, z, a, b, c: BRepPrimAPI_MakeBox(K.gp_Pnt(x, y, z), a, b, c).Shape()  # noqa: E731
        parts = K.compound([mk(0, 0, 0, 10, 10, 10), mk(5, 5, 5, 10, 10, 10), mk(30, 0, 0, 10, 10, 10)])
        v0 = sum(K.volume(s) for s in K._subshapes(parts, K.TopAbs_SOLID))
        res = K.combine(K.solid_body(parts, "F1"), K.Body(mk(33, 3, 10, 4, 4, 5)), "add")
        self.assertEqual(K.solids(res.shape), 3)
        self.assertAlmostEqual(sum(K.volume(s) for s in K._subshapes(res.shape, K.TopAbs_SOLID)), v0 + 80, delta=1e-6)
        self.assertEqual(len(res.names), 18)  # (every face of the three boxes keeps its name)
        big = K.compound([mk(0, 0, 0, 100, 100, 100), mk(200, 0, 0, 10, 10, 10)])
        res = K.combine(K.solid_body(big, "F1"), K.Body(mk(40, 40, 40, 10, 10, 10)), "cut")
        self.assertAlmostEqual(K.volume(res.shape), 1e6 - 1000 + 1000, delta=1e-6)
        self.assertEqual(K.solids(res.shape), 2)
        self.assertTrue(valid(res.shape))

    def test_fuzzy_second_try(self):
        """A boolean that fails is tried again with a fuzzy value; one that still fails says so (KernelError)."""
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
        a, b = BRepPrimAPI_MakeBox(10, 10, 10).Shape(), BRepPrimAPI_MakeBox(K.gp_Pnt(0, 0, 10 + 1e-5), 10, 10, 5).Shape()
        mk = K._fuzzy_retry("fuse", a, b)
        self.assertEqual(K.solids(mk.Shape()), 1)  # (1e-5 apart: touching at the fuzzy value)
        self.assertAlmostEqual(K.volume(mk.Shape()), 1500, delta=0.01)
        with self.assertRaises(K.KernelError):
            K._fuzzy_retry("fuse", K.compound([a, K.BRepBuilderAPI_MakeEdge(K.gp_Pnt(0, 0, 20), K.gp_Pnt(10, 0, 20)).Edge()]), b)


if __name__ == "__main__":
    unittest.main()
