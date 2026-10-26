"""Sketches with locked sizes (planegcs): a lock holds when other sizes change, dragging moves only what is
free, contradicting locks are reported, connected lines make faces (also L-shapes and plates with holes).
Skipped when the optional packages are missing (`py -m pip install -r requirements-modeler.txt`).

Run:  python -m unittest discover -s tests -v
"""
import math
import unittest

from auto3d.modeler import available

GCS, OCC = available("planegcs"), available("occ")
if GCS:
    from auto3d.modeler.constraints import SketchError, solve
if OCC:
    from auto3d.modeler import doc


def plate(w=40, h=20, dims=()):
    """A rectangle drawn from the origin (4 points, 4 lines, H / V), a circle at (10, 10), and the locks."""
    return {
        "points": {"p1": [0, 0], "p2": [w, 0], "p3": [w, h], "p4": [0, h], "p5": [10, 10]},
        "entities": [{"id": "l1", "t": "line", "a": "p1", "b": "p2", "g": "r1"}, {"id": "l2", "t": "line", "a": "p2", "b": "p3", "g": "r1"},
                     {"id": "l3", "t": "line", "a": "p3", "b": "p4", "g": "r1"}, {"id": "l4", "t": "line", "a": "p4", "b": "p1", "g": "r1"},
                     {"id": "c1", "t": "circle", "c": "p5", "r": 3}],
        "constraints": [{"id": "k1", "t": "h", "e": "l1"}, {"id": "k2", "t": "v", "e": "l2"}, {"id": "k3", "t": "h", "e": "l3"}, {"id": "k4", "t": "v", "e": "l4"}],
        "dims": list(dims),
    }


LOCK_CORNER = [{"id": "d1", "t": "dx", "a": "O", "b": "p1", "v": 0}, {"id": "d2", "t": "dy", "a": "O", "b": "p1", "v": 0}]


def slot(r=5, L=30):
    """A slot: two lines and two half circles (arcs, counter-clockwise), centres L apart."""
    return {"points": {"p1": [0, -r], "p2": [L, -r], "p3": [L, r], "p4": [0, r], "c1": [L, 0], "c2": [0, 0]},
            "entities": [{"id": "l1", "t": "line", "a": "p1", "b": "p2"}, {"id": "a1", "t": "arc", "c": "c1", "a": "p2", "b": "p3"},
                         {"id": "l2", "t": "line", "a": "p3", "b": "p4"}, {"id": "a2", "t": "arc", "c": "c2", "a": "p4", "b": "p1"}],
            "constraints": [{"id": "k1", "t": "h", "e": "l1"}, {"id": "k2", "t": "h", "e": "l2"}], "dims": []}


@unittest.skipUnless(GCS, "planegcs not installed")
class TestSketchSolve(unittest.TestCase):
    def test_lock_holds_when_the_plate_grows(self):
        dims = LOCK_CORNER + [{"id": "d3", "t": "len", "e": "l1", "v": 60}, {"id": "d4", "t": "dx", "a": "p1", "b": "p5", "v": 10}]
        r = solve(plate(dims=dims))
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["points"]["p2"], [60, 0])
        self.assertEqual(r["points"]["p5"][0], 10)  # the hole stays 10 mm from the left edge
        dims[2]["v"] = 90
        r = solve(plate(dims=dims))
        self.assertEqual(r["points"]["p3"][0], 90)
        self.assertEqual(r["points"]["p5"][0], 10)

    def test_diameter_lock_and_free_radius(self):
        r = solve(plate(dims=[{"id": "d1", "t": "dia", "e": "c1", "v": 8}]))
        self.assertAlmostEqual(r["radii"]["c1"], 4)
        r = solve(plate())
        self.assertAlmostEqual(r["radii"]["c1"], 3)  # not locked: kept as drawn

    def test_drag_moves_only_what_is_free(self):
        dims = LOCK_CORNER + [{"id": "d3", "t": "len", "e": "l1", "v": 40}]
        # drag the top-right corner: the width is locked, the height is free
        r = solve(plate(dims=dims), drag={"p3": [55, 30]})
        self.assertTrue(r["ok"], r)
        self.assertAlmostEqual(r["points"]["p3"][0], 40, places=6)
        self.assertAlmostEqual(r["points"]["p3"][1], 30, places=6)
        self.assertAlmostEqual(r["points"]["p4"][1], 30, places=6)  # stays a rectangle
        # free: the corner follows the mouse
        r = solve(plate(), drag={"p3": [55, 30]})
        self.assertEqual([round(v, 6) for v in r["points"]["p3"]], [55, 30])

    def test_degrees_of_freedom(self):
        self.assertEqual(solve(plate())["dof"], 4 + 3)  # rectangle: position 2 + size 2; circle: centre 2 + radius 1
        dims = LOCK_CORNER + [{"id": "d3", "t": "len", "e": "l1", "v": 40}, {"id": "d4", "t": "len", "e": "l2", "v": 20},
                              {"id": "d5", "t": "dx", "a": "O", "b": "p5", "v": 10}, {"id": "d6", "t": "dy", "a": "O", "b": "p5", "v": 10},
                              {"id": "d7", "t": "dia", "e": "c1", "v": 6}]
        r = solve(plate(dims=dims))
        self.assertEqual(r["dof"], 0)  # fully locked

    def test_conflicting_locks_are_named(self):
        dims = [{"id": "d1", "t": "len", "e": "l1", "v": 40}, {"id": "d2", "t": "len", "e": "l3", "v": 50}]  # top ≠ bottom
        r = solve(plate(dims=dims))
        self.assertFalse(r["ok"])
        self.assertEqual(set(r["conflicts"]), {"d1", "d2"})
        with self.assertRaises(SketchError):
            solve(plate(dims=[{"id": "d1", "t": "len", "e": "l1", "v": 0}]))
        with self.assertRaises(SketchError):
            solve(plate(dims=[{"id": "d1", "t": "dia", "e": "c1", "v": "abc"}]))

    def test_dimension_from_a_part_edge(self):
        # a hole 6 mm below a part edge at v = 20 and 8 mm left of an edge at u = 30 (fixed references)
        sk = plate()
        sk["dims"] = [{"id": "d1", "t": "dy", "a": "p5", "b": {"ref": [0, 20]}, "v": 6},
                      {"id": "d2", "t": "dx", "a": "p5", "b": {"ref": [30, -5]}, "v": 8}]
        r = solve(sk)
        self.assertTrue(r["ok"], r)
        self.assertEqual([round(c, 6) for c in r["points"]["p5"]], [22, 14])
        # a straight distance between two points
        sk["dims"] = [{"id": "d1", "t": "dist", "a": "p1", "b": "p5", "v": 5}]
        r = solve(sk, drag={"p1": [0, 0]})
        p5 = r["points"]["p5"]
        self.assertAlmostEqual(math.hypot(*p5), 5, places=6)

    def test_free_dimension_only_measures(self):
        sk = plate()
        sk["dims"] = [{"id": "d1", "t": "dx", "a": "O", "b": "p5", "v": 25, "free": True}]
        r = solve(sk)
        self.assertEqual(r["points"]["p5"], [10, 10])  # not moved to 25: it only measures
        sk["dims"][0].pop("free")
        r = solve(sk)
        self.assertEqual([round(c, 6) for c in r["points"]["p5"]], [25, 10])

    def test_arc_radius_lock(self):
        sk = slot()
        sk["dims"] = [{"id": "d1", "t": "rad", "e": "a1", "v": 8}]
        r = solve(sk)
        self.assertTrue(r["ok"], r)
        c, a, b = (r["points"][k] for k in ("c1", "p2", "p3"))
        self.assertAlmostEqual(math.dist(c, a), 8, places=6)
        self.assertAlmostEqual(math.dist(c, b), 8, places=6)  # both ends stay on the arc
        sk["dims"][0]["v"] = -1
        with self.assertRaises(SketchError):
            solve(sk)

    def test_endpoint(self):
        import server
        c = server.app.test_client()
        # typing a width: the corner it was drawn from is held (drag) while the new size is solved
        r = c.post("/api/model/sketch/solve", json={"sketch": plate(dims=[{"id": "d1", "t": "len", "e": "l1", "v": 25}]),
                                                    "drag": {"p1": [0, 0]}}).get_json()
        self.assertEqual([round(v, 6) for v in r["points"]["p2"]], [25, 0])
        e = c.post("/api/model/sketch/solve", json={"sketch": plate(dims=[{"id": "d1", "t": "len", "e": "l1", "v": -1}])})
        self.assertEqual(e.status_code, 400)


@unittest.skipUnless(OCC, "OCP not installed")
class TestLineSketchFaces(unittest.TestCase):
    def test_plate_with_hole_from_lines(self):
        sk = {"id": "S1", "type": "sketch", "plane": {"datum": "XY"}, **plate()}
        r = doc.rebuild({"features": [sk, {"id": "E1", "type": "extrude", "sketch": "S1", "op": "add", "d": 5}]})
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(r["body"]["volume"], (800 - math.pi * 9) * 5, delta=1e-3)

    def test_slot_with_arcs(self):
        f = [{"id": "S1", "type": "sketch", "plane": {"datum": "XY"}, **slot()}, {"id": "E1", "type": "extrude", "sketch": "S1", "op": "add", "d": 2}]
        r = doc.rebuild({"features": f})
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(r["body"]["volume"], 2 * (300 + math.pi * 25), delta=1e-6)  # true arcs, not polygons
        rounds = [x for x in r["body"]["faces"] if x["type"] == "cylinder"]
        self.assertEqual(sorted(x["name"] for x in rounds), ["E1:side:a1", "E1:side:a2"])
        self.assertAlmostEqual(rounds[0]["radius"], 5)
        # a slot cut out of a plate (arcs inside a rectangle -> a hole)
        sk = slot()
        sk["points"].update({"q1": [-20, -20], "q2": [50, -20], "q3": [50, 20], "q4": [-20, 20]})
        sk["entities"] += [{"id": f"m{i}", "t": "line", "a": f"q{i}", "b": f"q{i % 4 + 1}"} for i in range(1, 5)]
        f[0] = {"id": "S1", "type": "sketch", "plane": {"datum": "XY"}, **sk}
        r = doc.rebuild({"features": f})
        self.assertAlmostEqual(r["body"]["volume"], 2 * (70 * 40 - 300 - math.pi * 25), delta=1e-6)

    def test_l_shape_polyline(self):
        pts = {"a": [0, 0], "b": [30, 0], "c": [30, 10], "d": [10, 10], "e": [10, 25], "f": [0, 25]}
        names = list(pts)
        lines = [{"id": f"l{i}", "t": "line", "a": names[i], "b": names[(i + 1) % 6]} for i in range(6)]
        sk = {"id": "S1", "type": "sketch", "plane": {"datum": "XY"}, "points": pts, "entities": lines}
        r = doc.rebuild({"features": [sk, {"id": "E1", "type": "extrude", "sketch": "S1", "op": "add", "d": 2}]})
        self.assertAlmostEqual(r["body"]["volume"], (30 * 10 + 10 * 15) * 2, delta=1e-6)
        # an open chain makes no face
        sk["entities"] = lines[:4]
        r = doc.rebuild({"features": [sk]})
        self.assertIn("no closed shape", r["features"][0]["issues"][0])


if __name__ == "__main__":
    unittest.main()
