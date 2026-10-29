"""🔌 Cable harnesses (auto3d/modeler/harness.py; the browser's live preview does the same math in
web/js/assembly/harness.js): the route's length — straight, an L rounded at R (the straight parts + πR/2) —, a corner
too tight for the minimum bend radius reported, a bundle's Ø from its wires' circle packing, and the solid: a cable's
volume π(d/2)²·length, a watertight mesh, a STEP written and read back; loose wires one solid each.

Run:  py -m unittest tests.test_harness -v
"""
import math
import unittest

from auto3d.modeler import available
from auto3d.modeler import harness as H
from test_modeler_kernel import watertight

OCC = available("occ")
if OCC:
    from auto3d.modeler import doc
    from auto3d.modeler import kernel as K


class TestRoute(unittest.TestCase):
    def test_straight(self):
        r = H.route([[0, 0, 0], [30, 40, 0]], 15)
        self.assertAlmostEqual(r["length"], 50)
        self.assertEqual(r["bends"], [])
        self.assertEqual([s[0] for s in r["segments"]], ["line"])

    def test_points_in_a_line_and_twice(self):
        r = H.route([[0, 0, 0], [10, 0, 0], [10, 0, 0], [25, 0, 0]], 5)
        self.assertAlmostEqual(r["length"], 25)
        self.assertEqual(r["bends"], [])

    def test_l_rounded(self):
        R = 10
        r = H.route([[0, 0, 0], [100, 0, 0], [100, 0, 80]], R)
        self.assertAlmostEqual(r["length"], (100 - R) + (80 - R) + math.pi * R / 2, places=9)
        self.assertEqual(len(r["bends"]), 1)
        b = r["bends"][0]
        self.assertTrue(b["ok"])
        self.assertAlmostEqual(b["r"], R)
        self.assertAlmostEqual(b["angle"], 90)
        arc = next(s for s in r["segments"] if s[0] == "arc")
        self.assertTrue(all(abs(a - e) < 1e-9 for a, e in zip(arc[4], [90, 0, 10])))  # (its centre: R in from both legs)

    def test_tight_corner_flagged(self):
        """A 6 mm long leg between two right angles leaves room for R 3 (half of it each), not the minimum 15."""
        r = H.route([[0, 0, 0], [50, 0, 0], [50, 6, 0], [100, 6, 0]], 15)
        self.assertEqual([b["ok"] for b in r["bends"]], [False, False])
        self.assertAlmostEqual(r["bends"][0]["r"], 3)
        self.assertLess(r["length"], 106)  # (still a route: the largest bends that fit)
        wide = H.route([[0, 0, 0], [50, 0, 0], [50, 40, 0], [100, 40, 0]], 15)
        self.assertEqual([b["ok"] for b in wide["bends"]], [True, True])

    def test_first_leg_short(self):
        """A short first leg is all the corner's (its other end is no corner)."""
        r = H.route([[0, 0, 0], [5, 0, 0], [5, 50, 0]], 15)
        self.assertAlmostEqual(r["bends"][0]["r"], 5)
        self.assertFalse(r["bends"][0]["ok"])

    def test_bundle(self):
        for n, k in ((1, 1), (3, 2.155), (7, 3)):
            self.assertAlmostEqual(H.bundle_d(n, 1.5), k * 1.5, places=2)
        for n in range(1, 25):  # every wire inside the bundle, none on another
            d, pts = 1.5, H.wire_layout(n, 1.5)
            self.assertEqual(len(pts), n)
            self.assertTrue(all(math.hypot(*p) + d / 2 <= H.bundle_d(n, d) / 2 + 1e-9 for p in pts), n)
            self.assertTrue(all(math.dist(p, q) >= d - 1e-9 for i, p in enumerate(pts) for q in pts[i + 1:]), n)
        self.assertAlmostEqual(H.outer_d({"kind": "ribbon", "wires": [{}] * 10, "pitch": 1.27}), 12.7)


@unittest.skipUnless(OCC, "OCP not installed")
class TestSolid(unittest.TestCase):
    L_ROUTE = [[0, 0, 0], [100, 0, 0], [100, 0, 80], [100, 60, 80]]

    def build(self, **f):
        return doc.rebuild({"features": [{"id": "H1", "type": "harness", **f}]})

    def test_cable_volume_and_step(self):
        d, R = 6, 30
        r = self.build(kind="cable", points=self.L_ROUTE, d=d, r_min=R)
        self.assertTrue(r["ok"], r["features"])
        length = H.route(self.L_ROUTE, R)["length"]
        self.assertAlmostEqual(length, 100 + 80 + 60 - 4 * R + math.pi * R)
        v = math.pi * (d / 2) ** 2 * length
        self.assertAlmostEqual(r["body"]["volume"], v, delta=v * 1e-3)
        self.assertTrue(watertight(r["body"]))
        st, _ = doc.evaluate([{"id": "H1", "type": "harness", "kind": "cable", "points": self.L_ROUTE, "d": d, "r_min": R}])
        self.assertAlmostEqual(K.volume(K.from_step(K.to_step(st.body.shape))), v, delta=v * 1e-3)
        names = {f["name"] for f in r["body"]["faces"]}
        self.assertTrue({"H1:start", "H1:end", "H1:side"} <= names, names)

    def test_loose_wires(self):
        wires = [{"d": 1.5, "color": c} for c in ("red", "black", "blue", "brown")]
        r = self.build(kind="wires", points=self.L_ROUTE, wires=wires, r_min=20)
        self.assertTrue(r["ok"], r["features"])
        length = H.route(self.L_ROUTE, 20)["length"]
        v = 4 * math.pi * 0.75 ** 2 * length  # (off the centre line the arcs are longer or shorter: they even out)
        self.assertAlmostEqual(r["body"]["volume"], v, delta=v * 0.02)
        st, _ = doc.evaluate([{"id": "H1", "type": "harness", "kind": "wires", "points": self.L_ROUTE, "wires": wires, "r_min": 20}])
        self.assertEqual(K.solids(st.body.shape), 4)

    def test_ribbon_and_sleeve(self):
        r = self.build(kind="ribbon", points=self.L_ROUTE[:2], wires=[{}] * 10, pitch=1.27, d=1, r_min=10)
        self.assertAlmostEqual(r["body"]["volume"], 12.7 * 1 * 100, delta=1e-3)
        r = self.build(kind="sleeve", points=self.L_ROUTE[:3], d=10, r_min=50)
        self.assertTrue(r["ok"], r["features"])

    def test_errors(self):
        for f, why in (({"kind": "cable", "points": [[0, 0, 0]], "d": 5}, "at least two points"),
                       ({"kind": "rope", "points": self.L_ROUTE, "d": 5}, "cable, loose wires"),
                       ({"kind": "cable", "points": [[0, 0, 0], [50, 0, 0], [0, 0, 0]], "d": 5}, "turns back"),
                       ({"kind": "cable", "points": [[0, 0, 0], [50, 0, 0], [50, 2, 0], [0, 2, 0]], "d": 5, "r_min": 20}, "tighter than half its")):
            r = self.build(**f)
            self.assertFalse(r["ok"])
            self.assertIn(why, " ".join(r["features"][0]["issues"]))


if __name__ == "__main__":
    unittest.main()
