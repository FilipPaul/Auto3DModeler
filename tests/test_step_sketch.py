"""⇱ Shapes taken from the part's faces / edges into a sketch ({t: "proj", face | edges} in its constraints — doc.
_projections): a face's outline and holes become lines, arcs and circles held to it (constraints.py fixes them), found
again each rebuild, so they follow the face; also a face of a 👁 reference solid (an imported STEP, op "ref"), the
typical "build a cover around a bought part". A 40 × 20 × 10 box with a Ø8 hole: its top's outline extruded 5 ->
(800 − 16 π) × 5, watertight, STEP round trip; the same plate as an imported reference solid; the file replaced by a
moved copy -> the sketch and its shapes follow; a deleted shape stays deleted; edges; the solver holds them; a gone face;
a curve drawn the other way round in a hole's loop (kernel._mixed_wire).

Run:  py -m unittest tests.test_step_sketch -v
"""
import math
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from auto3d.modeler import available
from test_modeler_kernel import watertight

OCC = available("occ")
if OCC:
    from auto3d.modeler import blobs, doc, kernel as K
    from test_modeler_features import box, vol

TOP = {"face": {"name": "E1:end"}, "frame": {"o": [20, 10, 10], "x": [1, 0, 0], "n": [0, 0, 1]}}
HOLE = {"id": "H1", "type": "hole", "plane": TOP, "points": [[0, 0]], "d": 8, "through": True}
PLATE = 800 - 16 * math.pi  # (the top's area: 40 × 20 less the Ø8 hole)


def taken(sid="S2", plane=TOP, face="E1:end", fp=(20, 10, 10), **k):
    return {"id": sid, "type": "sketch", "plane": plane, "points": {}, "entities": [], "dims": [],
            "constraints": [{"t": "proj", "face": {"name": face, "fp": list(fp)}, **k}]}


def ext(sid="S2", **kw):
    return {"id": "E2", "type": "extrude", "sketch": sid, "op": "add", "d": 5, **kw}


def status(r, sid):
    return next(s for s in r["features"] if s["id"] == sid)


def kinds(sk):
    out = {}
    for e in sk["entities"]:
        out[e["t"]] = out.get(e["t"], 0) + 1
    return out


@unittest.skipUnless(OCC, "OCP not installed")
class TestTakeFromFace(unittest.TestCase):
    def test_outline_with_hole(self):
        """The top of the box with its Ø8 hole: 4 lines and the hole (a circle, or arcs), one proj relation holding
        them all; extruded 5 -> (800 − 16 π) × 5 more; watertight; STEP round trip."""
        fs = [*box(), HOLE, taken(), ext()]
        r, v = vol(*fs)
        self.assertTrue(r["ok"], r["features"])
        up = status(r, "S2")["update"]
        k = kinds(up)
        self.assertEqual(k.get("line"), 4)
        self.assertTrue(k.get("circle", 0) == 1 or k.get("arc", 0) >= 2, k)
        proj = up["constraints"][0]
        self.assertEqual(proj["t"], "proj")
        self.assertEqual(sorted(proj["ents"]), sorted(e["id"] for e in up["entities"]))
        self.assertTrue(all(p.startswith(proj["id"] + "p") for p in up["points"]))
        # (the sketch is on the face: its points round the face's centre)
        us = [p[0] for p in up["points"].values()]
        self.assertAlmostEqual(min(us), -20, places=6)
        self.assertAlmostEqual(max(us), 20, places=6)
        self.assertAlmostEqual(v, 8000 - 10 * 16 * math.pi + 5 * PLATE, delta=1e-3)
        self.assertTrue(watertight(r["body"]))
        self.assertAlmostEqual(K.volume(K.from_step(doc.export({"features": fs}, "step"))), v, delta=0.05)
        # built again from what the browser keeps (the update applied): the same shapes, no update now
        s2 = {**taken(), **up}
        r2, v2 = vol(*box(), HOLE, s2, ext())
        self.assertAlmostEqual(v2, v, delta=1e-6)
        self.assertNotIn("update", status(r2, "S2"))

    def test_follows_the_face(self):
        """The box made 15 tall: the face moves up, the shapes go with it (the same ids), the extrude starts at 15."""
        r, _ = vol(*box(), HOLE, taken(), ext())
        s2 = {**taken(), **status(r, "S2")["update"]}
        r2, v2 = vol(*box(d=15), {**HOLE, "plane": {**TOP, "frame": {**TOP["frame"], "o": [20, 10, 15]}}}, s2, ext())
        self.assertTrue(r2["ok"], r2["features"])
        self.assertAlmostEqual(r2["frames"]["S2"]["o"][2], 15, places=6)
        self.assertAlmostEqual(r2["body"]["bbox"][5], 20, places=6)
        self.assertAlmostEqual(v2, 800 * 15 - 15 * 16 * math.pi + 5 * PLATE, delta=1e-3)

    def test_deleted_shape_stays_deleted(self):
        """The hole's circle deleted in the sketch (taken out of the relation's ents): not taken again — the extrude is
        the full 40 × 20."""
        r, _ = vol(*box(), HOLE, taken(), ext())
        up = status(r, "S2")["update"]
        hole = [e["id"] for e in up["entities"] if e["t"] != "line"]
        k = {**up["constraints"][0], "ents": [i for i in up["constraints"][0]["ents"] if i not in hole]}
        s2 = {**taken(), "points": up["points"], "entities": [e for e in up["entities"] if e["id"] not in hole], "constraints": [k]}
        r2, v2 = vol(*box(), HOLE, s2, ext())
        self.assertTrue(r2["ok"], r2["features"])
        self.assertAlmostEqual(v2, 8000 - 10 * 16 * math.pi + 5 * 800, delta=1e-3)

    def test_edges(self):
        """One edge of the top (between the top and a side): one line, held; on another sketch plane above it too."""
        r, _ = vol(*box())
        edge = next(e for e in r["body"]["edges"] if {r["body"]["faces"][i]["name"] for i in e["faces"]} == {"E1:end", "E1:side:l1"})
        sk = {"id": "S2", "type": "sketch", "plane": {"datum": "XY", "offset": 30}, "points": {}, "entities": [], "dims": [],
              "constraints": [{"t": "proj", "edges": [{"a": "E1:end", "b": "E1:side:l1", "fp": edge["mid"]}]}]}
        r2, _ = vol(*box(), sk)
        up = status(r2, "S2")["update"]
        self.assertEqual(kinds(up), {"line": 1})
        self.assertEqual(sorted(map(tuple, up["points"].values())), [(0, 0), (40, 0)])

    def test_solver_holds_them(self):
        """The solver: the taken shapes have no free size (dof 0) and a drag of one of their points is refused."""
        if not available("planegcs"):
            self.skipTest("planegcs not installed")
        from auto3d.modeler.constraints import solve
        r, _ = vol(*box(), HOLE, taken())
        sk = {**taken(), **status(r, "S2")["update"]}
        s = solve(sk)
        self.assertTrue(s["ok"])
        self.assertEqual(s["dof"], 0)
        p = sk["constraints"][0]["pts"][0]
        moved = solve(sk, {p: [sk["points"][p][0] + 3, sk["points"][p][1]]})
        self.assertFalse(moved["held"]["ok"])

    def test_gone_face(self):
        """A face that is not there: an issue for a new relation; one that had its shapes keeps them (a warning)."""
        r, _ = vol(*box(), taken(face="E9:end"))
        self.assertFalse(status(r, "S2")["ok"])
        r, _ = vol(*box(), HOLE, taken(), ext())
        s2 = {**taken(), **status(r, "S2")["update"]}
        s2["constraints"] = [{**s2["constraints"][0], "face": {"name": "E9:end", "fp": [0, 0, 0]}}]
        r2, v2 = vol(*box(), HOLE, s2, ext())
        st = status(r2, "S2")
        self.assertTrue(st["ok"], st)
        self.assertTrue(any("gone" in w for w in st["warnings"]), st["warnings"])
        self.assertAlmostEqual(v2, 8000 - 10 * 16 * math.pi + 5 * PLATE, delta=1e-3)

    def test_nothing_seen_edge_on(self):
        """The top's outline taken into a sketch on a side plane (XZ: seen edge-on): only lines along it — no closed
        shape, the sketch reports it rather than failing the whole part."""
        sk = taken(plane={"datum": "XZ"})
        r, _ = vol(*box(), sk)
        self.assertTrue(r["body"])
        self.assertIn("update", status(r, "S2"))


@unittest.skipUnless(OCC, "OCP not installed")
class TestImportedFace(unittest.TestCase):
    """The plate with its hole written to a STEP and imported: a ▣ solid step (F1), faces F1:f<n>."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.blobs = mock.patch.object(blobs, "DIR", Path(self.tmp.name))
        self.blobs.start()
        st = doc.body_of({"features": [*box(), HOLE]})
        self.shape = st.body.shape
        self.r = doc.import_solid({"blob": blobs.put(K.to_step(self.shape)), "name": "plate.step"})
        out = doc.rebuild({"features": [self.solid("ref")]})
        self.top = next(f for f in out["refs"][0]["faces"] if f["type"] == "plane" and f["normal"] == [0, 0, 1] and f["centroid"][2] > 9)

    def tearDown(self):
        self.blobs.stop()
        self.tmp.cleanup()

    def solid(self, op, blob=None):
        return {"id": "F1", "type": "solid", "blob": blob or self.r["blob"], "file": "plate.step", "op": op}

    def sketch(self):
        f = self.top
        return taken(plane={"face": {"name": f["name"]}, "frame": f["frame"]}, face=f["name"], fp=f["centroid"])

    def test_reference_face(self):
        """👁 reference: its top face named F1:f<n> with a frame; its outline taken and extruded 5 -> the new body is
        (800 − 16 π) × 5 (the reference is not in it); watertight; STEP round trip."""
        self.assertRegex(self.top["name"], r"^F1:f\d+$")
        fs = [self.solid("ref"), self.sketch(), ext()]
        r, v = vol(*fs)
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, 5 * PLATE, delta=1e-3)
        self.assertAlmostEqual(r["body"]["bbox"][2], 10, places=6)
        self.assertTrue(watertight(r["body"]))
        self.assertAlmostEqual(K.volume(K.from_step(doc.export({"features": fs}, "step"))), v, delta=0.05)

    def test_joined_face(self):
        """▣ joined (op add): the same face, the plate made 5 taller: 8000 − 10·16π + 5·PLATE."""
        r, v = vol(self.solid("add"), self.sketch(), ext())
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, 8000 - 10 * 16 * math.pi + 5 * PLATE, delta=1e-3)
        self.assertTrue(watertight(r["body"]))

    def test_follows_a_moved_file(self):
        """The bought part's file replaced by one moved 7 up and 3 along x (the same faces): the sketch on its face
        and the taken shapes follow — the extrude sits on top of it at 17."""
        r, _ = vol(self.solid("ref"), self.sketch(), ext())
        s2 = {**self.sketch(), **status(r, "S2")["update"]}
        moved = K.moved_body(K.Body(self.shape), "", shift=[3, 0, 7]).shape
        blob = doc.import_solid({"blob": blobs.put(K.to_step(moved)), "name": "plate.step"})["blob"]
        r2, v2 = vol(self.solid("ref", blob), s2, ext())
        self.assertTrue(r2["ok"], r2["features"])
        self.assertAlmostEqual(r2["frames"]["S2"]["o"][2], 17, places=6)
        self.assertAlmostEqual(v2, 5 * PLATE, delta=1e-3)
        bb = r2["body"]["bbox"]
        self.assertEqual([round(x, 6) for x in bb], [3, 0, 17, 43, 20, 22])

    def test_project_endpoint(self):
        """doc.project (the sketcher's ⇱ From the part): the steps before the sketch, the sketch, the face -> the sketch
        with the shapes and their relation."""
        f = self.top
        out = doc.project({"features": [self.solid("ref")], "sketch": {"plane": {"face": {"name": f["name"]}, "frame": f["frame"]}, "points": {"q1": [0, 0]},
                           "entities": [], "constraints": []}, "face": {"name": f["name"], "fp": f["centroid"]}})
        sk = out["sketch"]
        self.assertEqual(kinds(sk).get("line"), 4)
        self.assertIn("q1", sk["points"])  # (what the sketch had is kept)
        self.assertEqual([k["t"] for k in sk["constraints"]], ["proj"])


@unittest.skipUnless(OCC, "OCP not installed")
class TestCurveTheOtherWay(unittest.TestCase):
    def test_spline_drawn_backwards_in_a_hole(self):
        """A hole's loop with a smooth curve drawn against the loop's way round (kernel._mixed_wire turns its edge): the
        plate keeps the hole — 100 × 60 less the hole's area, not plus it."""
        pts = {"a": [0, 0], "b": [100, 0], "c": [100, 60], "d": [0, 60], "p1": [20, 20], "p2": [60, 20], "p3": [60, 40], "m": [35, 38]}
        ents = [{"id": f"l{i}", "t": "line", "a": a, "b": b} for i, (a, b) in enumerate([("a", "b"), ("b", "c"), ("c", "d"), ("d", "a"), ("p1", "p2"), ("p2", "p3")])]
        ents.append({"id": "s1", "t": "spline", "pts": ["p1", "m", "p3"]})  # (the loop goes p1 -> p2 -> p3 -> back to p1)
        sk = {"id": "S1", "type": "sketch", "plane": {"datum": "XY"}, "points": pts, "entities": ents}
        r, v = vol(sk, {"id": "E1", "type": "extrude", "sketch": "S1", "op": "add", "d": 1})
        self.assertTrue(r["ok"], r["features"])
        from shapely.geometry import Polygon
        hole = Polygon([(20, 20), (60, 20), *K.spline_points([(60, 40), (35, 38), (20, 20)], 64)[:-1]]).area
        self.assertAlmostEqual(v, 6000 - hole, delta=hole * 0.01)


if __name__ == "__main__":
    unittest.main()
