"""⬆ Extrude this face: a sketch whose only shape is a face's outline ({t: "outline", face: {name, fp}} — the face's own
edges, found again each rebuild, as projected edges) and an extrude of it. The top of the 40 × 20 × 10 box pulled up
10 (volume 16000), a face with a hole keeps the hole (the bore goes on up), the cut variant (into the body), the outline
following the face when the box gets taller, a side face, watertight, STEP round trip, a missing face an issue.

Run:  py -m unittest tests.test_face_extrude -v
"""
import math
import unittest

from auto3d.modeler import available
from test_modeler_kernel import watertight

OCC = available("occ")
if OCC:
    from auto3d.modeler import doc, kernel as K
    from test_modeler_features import box, vol

TOP = {"face": {"name": "E1:end"}, "frame": {"o": [20, 10, 10], "x": [1, 0, 0], "n": [0, 0, 1]}}


def face_sketch(sid="S2", plane=TOP, name="E1:end", fp=(20, 10, 10)):
    return {"id": sid, "type": "sketch", "plane": plane, "points": {}, "entities": [{"id": "o1", "t": "outline", "face": {"name": name, "fp": list(fp)}}]}


def ext(sid="S2", **kw):
    return {"id": "E2", "type": "extrude", "sketch": sid, "op": "add", "d": 10, **kw}


@unittest.skipUnless(OCC, "OCP not installed")
class TestFaceExtrude(unittest.TestCase):
    def test_top_face_up(self):
        """The box's top pulled up 10: 40 × 20 × 20 = 16000; the new sides named E2:side:o1:0:k; the browser gets the
        outline's ring (the 4 corners round the face's centre); watertight; STEP round trip."""
        fs = [*box(), face_sketch(), ext()]
        r, v = vol(*fs)
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, 16000, delta=1e-6)
        self.assertTrue(watertight(r["body"]))
        names = {f.get("name") for f in r["body"]["faces"]}
        self.assertTrue({f"E2:side:o1:0:{k}" for k in range(4)} <= names, names)
        self.assertIn("E2:end", names)
        ring = next(s for s in r["features"] if s["id"] == "S2")["outline"]["o1"]
        self.assertEqual(len(ring), 1)
        self.assertEqual(sorted(map(tuple, ring[0])), [(-20, -10), (-20, 10), (20, -10), (20, 10)])
        self.assertAlmostEqual(K.volume(K.from_step(doc.export({"features": fs}, "step"))), v, delta=0.05)

    def test_hole_kept(self):
        """A Ø6 hole through the box: its top face has the hole as a loop; pulled up 10 the hole goes on up:
        16000 − 20 π 3²; the hole's new wall is a round face of E2."""
        hole = {"id": "H1", "type": "hole", "plane": TOP, "points": [[0, 0]], "d": 6, "through": True}
        fs = [*box(), hole, face_sketch(), ext()]
        r, v = vol(*fs)
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, 16000 - 20 * math.pi * 9, delta=1e-3)
        self.assertTrue(watertight(r["body"]))
        self.assertEqual(len(next(s for s in r["features"] if s["id"] == "S2")["outline"]["o1"]), 2)
        self.assertTrue(any(f.get("type") == "cylinder" and f.get("name", "").startswith("E2:side:o1:1:") for f in r["body"]["faces"]))
        self.assertAlmostEqual(K.volume(K.from_step(doc.export({"features": fs}, "step"))), v, delta=0.05)

    def test_cut_into_body(self):
        """⇅ the cut variant: the whole top cut 4 deep into the box -> 40 × 20 × 6."""
        r, v = vol(*box(), face_sketch(), ext(op="cut", d=4))
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, 4800, delta=1e-6)
        self.assertTrue(watertight(r["body"]))

    def test_follows_the_face(self):
        """The box 15 tall: the sketch moves up with its face, the outline is found again: 40 × 20 × 25."""
        fs = [*box(d=15), face_sketch(), ext()]
        r, v = vol(*fs)
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, 20000, delta=1e-6)

    def test_side_face(self):
        """The box's x = 40 side (E1:side:l2) pulled out 5 along +x: 8000 + 5 × 20 × 10."""
        side = {"face": {"name": "E1:side:l2"}, "frame": {"o": [40, 10, 5], "x": [0, 1, 0], "n": [1, 0, 0]}}
        r, v = vol(*box(), face_sketch(plane=side, name="E1:side:l2", fp=(40, 10, 5)), ext(d=5))
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, 9000, delta=1e-6)
        self.assertAlmostEqual(r["body"]["bbox"][3], 45, delta=1e-6)

    def test_missing_face(self):
        """A face that is not there: the sketch has an issue, its extrude too; the box stays."""
        r, v = vol(*box(), face_sketch(name="E9:end"), ext())
        self.assertFalse(r["ok"])
        bad = {s["id"]: s["ok"] for s in r["features"]}
        self.assertEqual((bad["S2"], bad["E2"]), (False, False))
        self.assertAlmostEqual(v, 8000, delta=1e-6)


if __name__ == "__main__":
    unittest.main()
