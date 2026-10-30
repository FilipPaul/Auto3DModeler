"""🔌 Cable harnesses (auto3d/modeler/harness.py; the browser's live preview does the same math in
web/js/assembly/harness.js): the route's length — straight, an L rounded at R (the straight parts + πR/2) —, a corner
too tight for the minimum bend radius reported, a bundle's Ø from its wires' circle packing, and the solid: a cable's
volume π(d/2)²·length, a watertight mesh, a STEP written and read back; loose wires one solid each.

Run:  py -m unittest tests.test_harness -v
"""
import math
import unittest

import numpy as np

from auto3d.modeler import available
from auto3d.modeler import harness as H
from test_modeler_kernel import watertight

OCC = available("occ")
if OCC:
    from auto3d.modeler import doc
    from auto3d.modeler import kernel as K


def sample(r, n):
    """n + 1 points evenly along a route's segments (G1 checked on the way: each piece starts where the last ended,
    in the direction it ended)."""
    pieces, last = [], None
    for s in r["segments"]:
        a, b = np.asarray(s[1]), np.asarray(s[3] if s[0] == "arc" else s[2])
        if s[0] == "line":
            f, ln, t0, t1 = (lambda u, a=a, b=b: a + (b - a) * u), float(np.linalg.norm(b - a)), (b - a), (b - a)
        else:
            c, rad, ang = np.asarray(s[4]), s[5], s[6]
            x, y = (a - c) / rad, (b - c) - ((b - c) @ ((a - c) / rad)) * (a - c) / rad
            y /= np.linalg.norm(y)
            f, ln = (lambda u, c=c, x=x, y=y, rad=rad, ang=ang: c + rad * (x * math.cos(ang * u) + y * math.sin(ang * u))), rad * ang
            t0, t1 = y, -x * math.sin(ang) + y * math.cos(ang)
        if last is not None:
            assert np.linalg.norm(last[0] - a) < 1e-9 and np.dot(last[1] / np.linalg.norm(last[1]), t0 / np.linalg.norm(t0)) > 1 - 1e-9, "not G1"
        last = (b, t1)
        pieces.append((f, ln))
    total, out = sum(ln for _, ln in pieces), []
    for k in range(n + 1):
        s = total * k / n
        for f, ln in pieces:
            if s <= ln + 1e-12 or (f, ln) == pieces[-1]:
                out.append(f(min(1.0, s / ln)))
                break
            s -= ln
    return out


def circum_r(p, q, s):
    """The radius of the circle through three points (inf: in a line)."""
    a, b, c = np.linalg.norm(q - s), np.linalg.norm(p - s), np.linalg.norm(p - q)
    area2 = np.linalg.norm(np.cross(q - p, s - p))
    return math.inf if area2 < 1e-12 else a * b * c / (2 * area2)


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

    def test_l_shaped_curvature(self):
        """An L clicked as 3 points at 90°: the path is G1 (each piece leaves in the direction the last one ended) and
        its curvature radius ≥ R everywhere (sampled: the circle through 3 neighbouring samples); length = the straight
        legs − 2R + πR/2."""
        R = 12
        r = H.route([[0, 0, 0], [60, 0, 0], [60, 45, 0]], R)
        self.assertAlmostEqual(r["length"], 60 + 45 - 2 * R + math.pi * R / 2, places=9)
        self.assertTrue(all(b["ok"] for b in r["bends"]))
        pts = sample(r, 400)
        self.assertGreaterEqual(min(circum_r(*pts[k - 1:k + 2]) for k in range(1, len(pts) - 1)), R * (1 - 1e-3))

    def test_close_corners_shaped(self):
        """A 6 mm step between two right angles (a Z): no longer bent tight — the corners move apart until both arcs
        are R 15, the ends stay, the path is G1 with curvature radius ≥ 15 everywhere, nothing reported."""
        R = 15
        r = H.route([[0, 0, 0], [50, 0, 0], [50, 6, 0], [100, 6, 0]], R)
        self.assertEqual([b["ok"] for b in r["bends"]], [True, True])
        self.assertTrue(all(abs(s[5] - R) < 1e-6 for s in r["segments"] if s[0] == "arc"))
        pts = sample(r, 600)
        self.assertLess(math.dist(pts[0], [0, 0, 0]) + math.dist(pts[-1], [100, 6, 0]), 1e-9)
        self.assertGreaterEqual(min(circum_r(*pts[k - 1:k + 2]) for k in range(1, len(pts) - 1)), R * (1 - 1e-3))
        two45 = H.route([[0, 0, 0], [40, 0, 0], [43, 3, 0], [43, 50, 0]], R)  # (two 45° turns 4 mm apart)
        self.assertEqual([b["ok"] for b in two45["bends"]], [True, True])

    def test_tight_corner_only_the_exception(self):
        """A U turn 6 mm wide cannot bend R 15 whatever moves: R 3 (half the gap), reported; a wide one is not."""
        r = H.route([[0, 0, 0], [50, 0, 0], [50, 6, 0], [0, 6, 0]], 15)
        self.assertEqual([b["ok"] for b in r["bends"]], [False, False])
        self.assertAlmostEqual(r["bends"][0]["r"], 3)
        wide = H.route([[0, 0, 0], [50, 0, 0], [50, 40, 0], [100, 40, 0]], 15)
        self.assertEqual([b["ok"] for b in wide["bends"]], [True, True])

    def test_first_leg_short(self):
        """A short first leg is all the corner's (its other end is no corner)."""
        r = H.route([[0, 0, 0], [5, 0, 0], [5, 50, 0]], 15)
        self.assertAlmostEqual(r["bends"][0]["r"], 5)
        self.assertFalse(r["bends"][0]["ok"])

    def test_locked_length(self):
        """🔒 A cable locked at 400 mm: its ends moved closer, it keeps 400 (± 0.5) — the slack sags down, every bend
        still ≥ R (sampled), its ends where they were; moved farther than it reaches: straight, taut, short by the gap."""
        R, pts = 15, [[0, 0, 100], [120, 0, 100], [120, 0, 180], [200, 40, 180]]
        for moved in (pts, [[40, 0, 100]] + pts[1:], [[60, 0, 100]] + pts[1:3] + [[150, 20, 180]]):
            r = H.shape(moved, R, total=400)
            self.assertAlmostEqual(r["length"], 400, delta=0.5)
            self.assertEqual(r["taut"], [])
            self.assertTrue(all(b["ok"] for b in r["bends"]), r["bends"])
            s = sample(r, 1500)
            self.assertGreaterEqual(min(circum_r(*s[k - 1:k + 2]) for k in range(1, len(s) - 1)), R * (1 - 1e-3))
            self.assertLess(math.dist(s[0], moved[0]) + math.dist(s[-1], moved[-1]), 1e-9)
            self.assertLess(min(q[2] for q in s), 100)  # (it sags: below its lowest point)
        for few in ([], [[1, 2, 3]], [[1, 2, 3], [1, 2, 3]]):  # (fewer than two points: nothing to shape, no error)
            self.assertEqual(H.shape(few, R, total=400)["length"], 0.0)
        far = [[-300, 0, 100]] + pts[1:]
        straight = H.route(far, R)["length"]
        r = H.shape(far, R, total=400)
        self.assertAlmostEqual(r["length"], straight)
        self.assertEqual(len(r["taut"]), 1)
        self.assertAlmostEqual(r["taut"][0]["short"], straight - 400)

    def test_span_length(self):
        """➰ A span given 140 mm with its ends 100 apart: a loop of slack 140 (± 0.5), every bend ≥ R; ends moved to 130
        apart: still 140, shaped again; to 150: straight, taut, short by 10. Its neighbours keep their own lengths."""
        R = 15
        for gap in (100, 130):
            pts = [[-60, 0, 50], [0, 0, 50], [gap, 0, 50], [gap, 0, 120]]
            r = H.shape(pts, R, spans={1: 140})
            self.assertAlmostEqual(r["spans"][1], 140, delta=0.5)
            self.assertAlmostEqual(sum(r["spans"]), r["length"], places=6)
            self.assertEqual(r["taut"], [])
            self.assertTrue(all(b["ok"] for b in r["bends"]), r["bends"])
            s = sample(r, 1500)
            self.assertGreaterEqual(min(circum_r(*s[k - 1:k + 2]) for k in range(1, len(s) - 1)), R * (1 - 1e-3))
        r = H.shape([[-60, 0, 50], [0, 0, 50], [150, 0, 50], [150, 0, 120]], R, spans={1: 140})
        self.assertEqual([t["span"] for t in r["taut"]], [1])
        self.assertAlmostEqual(r["taut"][0]["short"], H.shape([[-60, 0, 50], [0, 0, 50], [150, 0, 50], [150, 0, 120]], R)["spans"][1] - 140)
        both = H.shape([[0, 0, 0], [100, 0, 0]], R, spans={0: 140}, total=300)  # (the span's own length wins)
        self.assertTrue(both["total_ignored"])
        self.assertAlmostEqual(both["length"], 140, delta=0.5)

    def test_span_with_a_lead(self):
        """➰ A span that starts at an end on a face (its lead straight up, then on): its own length kept all the same
        (its slack on its other leg, the lead straight); the whole cable locked: the lead stays straight too."""
        free = lambda p, rad: None  # noqa: E731  (nothing round it)
        pts, R = [[0, 0, 10], [120, 0, 10], [120, 80, 10]], 15
        base = H.avoid(pts, R, 6, free, normals=[[0, 0, 1], None, None])
        r = H.avoid(pts, R, 6, free, normals=[[0, 0, 1], None, None], spans={0: base["spans"][0] + 40})
        self.assertAlmostEqual(r["spans"][0], base["spans"][0] + 40, delta=0.5)
        self.assertEqual(r["dropped"], [])
        self.assertTrue(np.allclose(r["points"][1], base["points"][1]))  # (the lead as it was)
        t = H.avoid(pts, R, 6, free, normals=[[0, 0, 1], None, None], total=base["length"] + 60)
        self.assertAlmostEqual(t["length"], base["length"] + 60, delta=0.5)
        self.assertTrue(all(b["ok"] for b in t["bends"]), t["bends"])

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

    def test_locked_length_solid(self):
        """🔒 A cable locked at 300 mm: the solid is that long — volume π(d/2)²·300 —, watertight, read back from STEP."""
        d = 6
        f = {"id": "H1", "type": "harness", "kind": "cable", "points": self.L_ROUTE, "d": d, "r_min": 30, "length": 300}
        r = doc.rebuild({"features": [f]})
        self.assertTrue(r["ok"], r["features"])
        v = math.pi * (d / 2) ** 2 * 300
        self.assertAlmostEqual(r["body"]["volume"], v, delta=v * 2e-3)
        self.assertTrue(watertight(r["body"]))
        st, _ = doc.evaluate([f])
        self.assertAlmostEqual(K.volume(K.from_step(K.to_step(st.body.shape))), v, delta=v * 2e-3)
        # ➰ its first span 150 mm (100 straight): the solid as long as the shaped route
        g = dict(f, length=None, spans=[{"from": 0, "length": 150}])
        L = H.shape(self.L_ROUTE, 30, spans={0: 150})["length"]
        r = doc.rebuild({"features": [g]})
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(r["body"]["volume"], math.pi * (d / 2) ** 2 * L, delta=L * 30 * 2e-3)
        self.assertTrue(watertight(r["body"]))

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


def sd_cylinder(p, r, h):
    """Signed distance from p to a cylinder round the z axis, radius r, z 0 … h (< 0 inside)."""
    q = (math.hypot(p[0], p[1]) - r, abs(p[2] - h / 2) - h / 2)
    return min(max(q[0], q[1]), 0.0) + math.hypot(max(q[0], 0.0), max(q[1], 0.0))


def sd_box(p, lo, hi):
    """Signed distance from p to an axis-aligned box lo … hi (< 0 inside)."""
    c, e = [(a + b) / 2 for a, b in zip(lo, hi)], [(b - a) / 2 for a, b in zip(lo, hi)]
    q = [abs(p[i] - c[i]) - e[i] for i in range(3)]
    return min(max(q), 0.0) + math.sqrt(sum(max(x, 0.0) ** 2 for x in q))


def prober(sd):
    """probe(p, rad) for avoid from a signed distance: too near -> out along its gradient to rad clear."""
    def probe(p, rad):
        s = sd(p)
        if s >= rad:
            return None
        g = np.array([sd(p + e) - sd(p - e) for e in np.eye(3) * 1e-4]) / 2e-4
        return g / (np.linalg.norm(g) or 1) * (rad - s)
    return probe


@unittest.skipUnless(OCC, "OCP not installed")
class TestAvoid(unittest.TestCase):
    """The cable kept clear of other bodies: its end on a pin's top leaves it square (a lead), a span through a box's
    corner goes round it; the clicked points stay; the tube built from the result does not touch them (the kernel's
    least distance > 0)."""

    def tube(self, r, d):
        st, _ = doc.evaluate([{"id": "H1", "type": "harness", "kind": "cable", "points": [list(map(float, p)) for p in r["points"]], "d": d, "r_min": 15}])
        return st.body.shape

    def body(self, sketch, height):
        """A body extruded from a sketch on XY: points + entities (as the modeller's sketch step)."""
        pts, ents = sketch
        st, _ = doc.evaluate([{"id": "S1", "type": "sketch", "plane": {"datum": "XY"}, "points": pts, "entities": ents},
                              {"id": "E1", "type": "extrude", "sketch": "S1", "op": "add", "d": height}])
        return st.body.shape

    def test_end_on_a_pin(self):
        d, R, lift = 6, 15, 3.5
        start, end = [0, 0, 30 + lift], [60, 0, 5]
        r = H.avoid([start, end], R, d, prober(lambda p: sd_cylinder(p, 10, 30)), normals=[[0, 0, 1], None])
        up = r["points"][1]  # (straight up first, as far as the bend down to the other end needs)
        self.assertTrue(np.allclose(up[:2], [0, 0]) and up[2] - start[2] >= H.lead_of(R, d) and np.isclose(up[2] - start[2], H.lead_of(R, d, np.array(start, float), np.array([0, 0, 1.0]), end)), up)
        self.assertTrue(np.allclose(r["points"][0], start) and np.allclose(r["points"][-1], end))
        self.assertEqual(r["clashes"], [])
        self.assertTrue(all(b["ok"] for b in r["bends"]), r["bends"])
        gap = K.min_distance(self.tube(r, d), self.body(({"c": [0, 0]}, [{"id": "k", "t": "circle", "c": "c", "r": 10}]), 30))
        self.assertGreater(gap["distance"], 0.0)
        self.assertFalse(gap.get("overlap"))
        straight = H.route([start, end], R)  # (without it: the straight cable goes into the pin)
        self.assertTrue(any(sd_cylinder(p, 10, 30) < d / 2 for p in H.samples(straight, 1.0)))

    def test_span_through_a_box_corner(self):
        d, R = 6, 15
        a, b = [-20, 30, 20], [30, -20, 20]  # (straight: through the corner x, y < 10 of the box 0 … 40)
        sd = lambda p: sd_box(p, [0, 0, 0], [40, 40, 40])  # noqa: E731
        self.assertTrue(any(sd(p) < 0 for p in H.samples(H.route([a, b], R), 1.0)))
        r = H.avoid([a, b], R, d, prober(sd))
        self.assertTrue(np.allclose(r["points"][0], a) and np.allclose(r["points"][-1], b))  # (the anchors kept)
        self.assertGreater(len(r["points"]), 2)  # (a detour put in)
        self.assertEqual(r["clashes"], [])
        self.assertTrue(all(b_["ok"] for b_ in r["bends"]), r["bends"])
        s = sample(r, 1500)
        self.assertGreaterEqual(min(circum_r(*s[k - 1:k + 2]) for k in range(1, len(s) - 1)), R * (1 - 1e-3))
        gap = K.min_distance(self.tube(r, d), self.body(({"p1": [0, 0], "p2": [40, 0], "p3": [40, 40], "p4": [0, 40]}, [{"id": f"l{i + 1}", "t": "line", "a": f"p{i + 1}", "b": f"p{(i + 1) % 4 + 1}"} for i in range(4)]), 40))
        self.assertGreater(gap["distance"], 0.0)

if __name__ == "__main__":
    unittest.main()
