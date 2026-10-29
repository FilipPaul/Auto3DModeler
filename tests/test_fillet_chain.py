"""⛓ Tangent chains for fillet / chamfer: a box with rounded corners has two chains of 8 edges (its top and bottom
outlines); one picked edge of a chain rounds the whole chain (OpenCASCADE's way) — the volume against Pappus, every
new face named, watertight, read back from STEP; ⛓ off (chain: false) warns that the rounding goes on.

Run:  py -m unittest tests.test_fillet_chain -v
"""
import math
import unittest

from auto3d.modeler import available
from test_modeler_kernel import watertight

OCC = available("occ")
if OCC:
    from auto3d.modeler import doc, kernel as K
    from test_modeler_features import box, vol

R = 3  # the box's corners rounded R 3 (40 x 20 x 10)
CORNERS = {"id": "C", "type": "fillet", "r": R, "edges": [
    {"a": f"E1:side:l{i}", "b": f"E1:side:l{i % 4 + 1}", "fp": p} for i, p in zip(range(1, 5), ([40, 0, 5], [40, 20, 5], [0, 20, 5], [0, 0, 5]))]}
TOP_FRONT = {"a": "E1:end", "b": "E1:side:l1", "fp": [20, 0, 10]}
BASE = 8000 - 4 * (R * R - math.pi * R * R / 4) * 10


def removed(area, xbar):
    """What a rounding / bevel of the rounded box's top outline takes: its cross-section along the straight sides
    (2 × 34 + 2 × 14) and turned round the four corners (Pappus: at R − its centroid's distance from the wall)."""
    return area * (2 * (40 - 2 * R) + 2 * (20 - 2 * R) + 2 * math.pi * (R - xbar))


@unittest.skipUnless(OCC, "OCP not installed")
class TestTangentChain(unittest.TestCase):
    def test_chains_in_the_mesh(self):
        """The rounded box's edges: two chains of 8 (top and bottom outlines); a plain box has none."""
        r, v = vol(*box(), CORNERS)
        self.assertAlmostEqual(v, BASE, delta=1e-4)
        ch = [e["chain"] for e in r["body"]["edges"] if "chain" in e]
        self.assertEqual(sorted(ch.count(k) for k in set(ch)), [8, 8])
        r, _ = vol(*box())
        self.assertFalse(any("chain" in e for e in r["body"]["edges"]))

    def test_one_edge_rounds_its_chain(self):
        """A fillet R1 on one top edge rounds all 8 edges of the top outline: (1 − π/4) swept round it; every face of
        it named F:round:0; the same with all 8 edges picked (the ⛓ click); watertight; STEP round trip."""
        fil = {"id": "F", "type": "fillet", "edges": [TOP_FRONT], "r": 1}
        r, v = vol(*box(), CORNERS, fil)
        self.assertTrue(r["ok"], r["features"])
        want = BASE - removed(1 - math.pi / 4, (10 - 3 * math.pi) / (12 - 3 * math.pi))
        self.assertAlmostEqual(v, want, delta=1e-3)
        self.assertTrue(watertight(r["body"]))
        self.assertEqual(sum(1 for f in r["body"]["faces"] if f.get("name") == "F:round:0"), 8)
        self.assertTrue(all(f.get("name") for f in r["body"]["faces"]), [f.get("name") for f in r["body"]["faces"]])
        self.assertEqual(r["features"][-1]["warnings"], [])
        self.assertAlmostEqual(K.volume(K.from_step(doc.export({"features": [*box(), CORNERS, fil]}, "step"))), v, delta=0.05)
        # all the chain's edges picked (as the panel's ⛓ click stores them): the same part
        rc, _ = vol(*box(), CORNERS)
        b = rc["body"]
        k = next(e["chain"] for e in b["edges"] if e["mid"] == [20, 0, 10])
        refs = [{"a": b["faces"][e["faces"][0]]["name"], "b": b["faces"][e["faces"][1]]["name"], "fp": e["mid"]} for e in b["edges"] if e.get("chain") == k]
        self.assertEqual(len(refs), 8)
        r2, v2 = vol(*box(), CORNERS, {**fil, "edges": refs})
        self.assertTrue(r2["ok"], r2["features"])
        self.assertAlmostEqual(v2, v, delta=1e-6)

    def test_chamfer_chain_and_chain_off(self):
        """A chamfer 1 on one top edge bevels the top outline: ½ swept round it (centroid 1/3 in). ⛓ off: the same
        part, and a warning that it goes on along 7 more edges."""
        ch = {"id": "B", "type": "chamfer", "edges": [TOP_FRONT], "d": 1}
        r, v = vol(*box(), CORNERS, ch)
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, BASE - removed(0.5, 1 / 3), delta=1e-3)
        self.assertTrue(watertight(r["body"]))
        r, v2 = vol(*box(), CORNERS, {**ch, "chain": False})
        self.assertAlmostEqual(v2, v, delta=1e-6)
        self.assertIn("7 more edge(s)", r["features"][-1]["warnings"][0])
        # a sharp box edge (no chain): ⛓ off says nothing
        r, _ = vol(*box(), {**ch, "chain": False})
        self.assertEqual(r["features"][-1]["warnings"], [])


if __name__ == "__main__":
    unittest.main()
