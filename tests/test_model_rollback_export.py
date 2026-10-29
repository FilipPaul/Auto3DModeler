"""⏮ Exports, the print copy and drawings follow the rollback bar (as SolidWorks prints / saves the rolled-back part):
a part of three solid steps — a 40×20×10 block, a 10×10×5 boss on it, a Ø4 hole through — with the bar under the
block exports (STEP read back, STL) the block's 8000 mm³; with the bar at the end (none, or a step that is not there)
the whole part. Also through the HTTP endpoint (the server's kernel worker) and the drawing sheet's size.

Run:  py -m unittest tests.test_model_rollback_export -v
"""
import math
import unittest

import numpy as np

from auto3d.modeler import available

OCC = available("occ")
if OCC:
    from auto3d.modeler import doc, kernel

BLOCK, BOSS, HOLE = 40 * 20 * 10, 10 * 10 * 5, math.pi * 2 ** 2 * 15  # the hole goes through the block and the boss


def part(rollback=None):
    p = {"features": [
        {"id": "F1", "type": "sketch", "name": "Sketch 1", "plane": {"datum": "XY"}, "entities": [{"id": "r", "t": "rect", "cx": 20, "cy": 10, "w": 40, "h": 20}]},
        {"id": "F2", "type": "extrude", "name": "Extrude 1", "sketch": "F1", "op": "add", "d": 10},
        {"id": "F3", "type": "sketch", "name": "Sketch 2", "plane": {"datum": "XY", "offset": 10}, "entities": [{"id": "r", "t": "rect", "cx": 20, "cy": 10, "w": 10, "h": 10}]},
        {"id": "F4", "type": "extrude", "name": "Extrude 2", "sketch": "F3", "op": "add", "d": 5},
        {"id": "F5", "type": "sketch", "name": "Sketch 3", "plane": {"datum": "XY"}, "entities": [{"id": "c", "t": "circle", "cx": 20, "cy": 10, "d": 4}]},
        {"id": "F6", "type": "extrude", "name": "Extrude 3", "sketch": "F5", "op": "cut", "through": True, "flip": True, "d": 1}]}
    if rollback:
        p["rollback"] = rollback
    return p


def stl_stats(data):
    """(volume, unmatched directed edges) of a binary STL — 0 unmatched: watertight."""
    n = int(np.frombuffer(data[80:84], np.uint32)[0])
    rec = np.frombuffer(data[84:84 + n * 50], dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    tri = rec["v"].astype(float)
    vol = float(np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum() / 6)
    edges = {}
    for t in np.round(tri, 4):
        for a, b in ((0, 1), (1, 2), (2, 0)):
            k = (tuple(t[a]), tuple(t[b]))
            edges[k] = edges.get(k, 0) + 1
    return vol, sum(1 for (p, q), k in edges.items() if edges.get((q, p), 0) != k)


@unittest.skipUnless(OCC, "OCP not installed")
class TestRollbackExport(unittest.TestCase):
    def step_volume(self, p):
        return kernel.volume(kernel.from_step(doc.export(p, "step", "Rolled")))

    def test_at_bar(self):
        self.assertEqual([f["id"] for f in doc.at_bar(part("F2"))["features"]], ["F1", "F2"])
        self.assertNotIn("rollback", doc.at_bar(part("F2")))
        self.assertEqual(len(doc.at_bar(part())["features"]), 6)
        self.assertEqual(len(doc.at_bar(part("F99"))["features"]), 6)  # (a step that is not there: every step, as the browser)
        self.assertEqual(doc.at_bar(None), {})

    def test_step_export_follows_the_bar(self):
        full = BLOCK + BOSS - HOLE
        self.assertAlmostEqual(self.step_volume(part("F2")), BLOCK, delta=BLOCK * 1e-6)  # the block alone
        self.assertAlmostEqual(self.step_volume(part("F4")), BLOCK + BOSS, delta=1e-2)  # with the boss, no hole
        self.assertAlmostEqual(self.step_volume(part()), full, delta=full * 1e-4)  # the bar at the end: all
        self.assertAlmostEqual(self.step_volume(part("F6")), full, delta=full * 1e-4)  # under the last step: all too

    def test_stl_iges_and_rebuild_follow_the_bar(self):
        vol, bad = stl_stats(doc.export(part("F2"), "stl"))
        self.assertAlmostEqual(vol, BLOCK, delta=1)
        self.assertEqual(bad, 0)
        vol, bad = stl_stats(doc.export(part(), "stl"))
        self.assertAlmostEqual(vol, BLOCK + BOSS - HOLE, delta=5)  # (a mesh: the hole's circle is facetted)
        self.assertEqual(bad, 0)
        iges = kernel.read_step_colours(doc.export(part("F2"), "iges"), kind="iges")[0]
        self.assertAlmostEqual(kernel.volume(iges), BLOCK, delta=BLOCK * 1e-4)
        r = doc.rebuild(part("F4"))  # (the AI / another tab sending the whole part with its bar)
        self.assertAlmostEqual(r["body"]["volume"], BLOCK + BOSS, delta=1e-2)
        self.assertEqual([s["id"] for s in r["features"]], ["F1", "F2", "F3", "F4"])

    def test_sheet_follows_the_bar(self):
        bb = doc.sheet(part("F2"), "light")["geometry"]["bbox"]
        self.assertAlmostEqual(bb[5] - bb[2], 10, delta=1e-3)  # the block: 10 high, no boss
        bb = doc.sheet(part(), "light")["geometry"]["bbox"]
        self.assertAlmostEqual(bb[5] - bb[2], 15, delta=1e-3)

    def test_http_export_follows_the_bar(self):
        """/api/model/export/<fmt> — what the browser's Export menu, the print copy and the AI's export call."""
        import server
        c = server.app.test_client()
        r = c.post("/api/model/export/step", json={"part": part("F2"), "name": "Rolled"})
        self.assertEqual(r.status_code, 200)
        self.assertAlmostEqual(kernel.volume(kernel.from_step(r.data)), BLOCK, delta=BLOCK * 1e-6)
        r = c.post("/api/model/export/step", json={"part": part(), "name": "Full"})
        self.assertAlmostEqual(kernel.volume(kernel.from_step(r.data)), BLOCK + BOSS - HOLE, delta=(BLOCK + BOSS) * 1e-4)
        vol, bad = stl_stats(c.post("/api/model/export/stl", json={"part": part("F4")}).data)
        self.assertAlmostEqual(vol, BLOCK + BOSS, delta=1)
        self.assertEqual(bad, 0)


if __name__ == "__main__":
    unittest.main()
