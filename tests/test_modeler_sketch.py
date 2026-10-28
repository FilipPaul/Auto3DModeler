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


def rounded(w=40, r=5):
    """A 40 x 20 rectangle from the origin whose top-right corner p3 is rounded (as the ◜ Round corner tool leaves
    it): the lines end at the tangent points t1 / t2, an arc joins them, p3 stays as the sharp corner on both lines."""
    return {"points": {"p1": [0, 0], "p2": [w, 0], "p3": [w, 20], "p4": [0, 20], "t1": [w, 20 - r], "t2": [w - r, 20], "c": [w - r, 20 - r]},
            "entities": [{"id": "l1", "t": "line", "a": "p1", "b": "p2"}, {"id": "l2", "t": "line", "a": "p2", "b": "t1"},
                         {"id": "a1", "t": "arc", "c": "c", "a": "t1", "b": "t2"},
                         {"id": "l3", "t": "line", "a": "t2", "b": "p4"}, {"id": "l4", "t": "line", "a": "p4", "b": "p1"}],
            "constraints": [{"id": "k1", "t": "h", "e": "l1"}, {"id": "k2", "t": "v", "e": "l2"}, {"id": "k3", "t": "h", "e": "l3"},
                            {"id": "k4", "t": "v", "e": "l4"}, {"id": "k5", "t": "tan", "e": "l2", "arc": "a1", "p": "t1"},
                            {"id": "k6", "t": "tan", "e": "l3", "arc": "a1", "p": "t2"}, {"id": "k7", "t": "corner", "p": "p3", "lines": ["l2", "l3"]}],
            "dims": [{"id": "d1", "t": "dx", "a": "O", "b": "p1", "v": 0}, {"id": "d2", "t": "dy", "a": "O", "b": "p1", "v": 0},
                     {"id": "d3", "t": "len", "e": "l1", "v": w}, {"id": "d4", "t": "dist", "a": "p3", "b": "p2", "v": 20},
                     {"id": "d6", "t": "rad", "e": "a1", "v": r}]}


@unittest.skipUnless(GCS, "planegcs not installed")
class TestSketchMirror(unittest.TestCase):
    def test_copy_follows_the_original(self):
        # the plate and a circle mirrored across the Y axis: the copy follows when the plate grows to 50
        sk = plate(dims=LOCK_CORNER + [{"id": "d3", "t": "len", "e": "l1", "v": 50}, {"id": "d4", "t": "dia", "e": "c1", "v": 8}])
        sk["points"].update({"q2": [-40, 0], "q3": [-40, 20], "q5": [-10, 10]})
        sk["entities"] += [{"id": "m1", "t": "line", "a": "p1", "b": "q2"}, {"id": "m2", "t": "line", "a": "q2", "b": "q3"},
                           {"id": "m3", "t": "line", "a": "q3", "b": "p4"}, {"id": "c2", "t": "circle", "c": "q5", "r": 3}]
        sk["constraints"].append({"id": "k9", "t": "mir", "axis": "y", "pairs": [["p1", "p1"], ["p2", "q2"], ["p3", "q3"], ["p4", "p4"], ["p5", "q5"]],
                                  "circles": [["c1", "c2"]], "user": True})
        r = solve(sk)
        self.assertTrue(r["ok"], r)
        self.assertAlmostEqual(r["points"]["q2"][0], -50, places=6)
        self.assertAlmostEqual(r["points"]["q3"][0], -r["points"]["p3"][0], places=6)
        self.assertAlmostEqual(r["radii"]["c2"], 4, places=6)
        # across a sketch line: a point mirrored over the line x = y
        sk2 = {"points": {"a": [0, 0], "b": [10, 10], "p": [8, 2], "q": [0, 0]}, "entities": [{"id": "l", "t": "line", "a": "a", "b": "b"}],
               "constraints": [{"id": "k", "t": "mir", "e": "l", "pairs": [["p", "q"]]}],
               "dims": [{"id": "d1", "t": "dx", "a": "O", "b": "a", "v": 0}, {"id": "d2", "t": "dy", "a": "O", "b": "a", "v": 0},
                        {"id": "d3", "t": "dx", "a": "O", "b": "p", "v": 8}, {"id": "d4", "t": "dy", "a": "O", "b": "p", "v": 2},
                        {"id": "d5", "t": "dx", "a": "O", "b": "b", "v": 10}, {"id": "d6", "t": "dy", "a": "O", "b": "b", "v": 10}]}
        r = solve(sk2)
        self.assertTrue(r["ok"], r)
        self.assertAlmostEqual(r["points"]["q"][0], 2, places=5)
        self.assertAlmostEqual(r["points"]["q"][1], 8, places=5)


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

    def test_angle_between_two_lines(self):
        """∠: two lines from a fixed corner, 60° apart (each ray from the corner); the second turns to it."""
        sk = {"points": {"p1": [0, 0], "p2": [10, 0], "p3": [6, 6]},
              "entities": [{"id": "l1", "t": "line", "a": "p1", "b": "p2"}, {"id": "l2", "t": "line", "a": "p1", "b": "p3"}],
              "constraints": [{"id": "k1", "t": "h", "e": "l1"}],
              "dims": [{"id": "d1", "t": "dx", "a": "O", "b": "p1", "v": 0}, {"id": "d2", "t": "dy", "a": "O", "b": "p1", "v": 0},
                       {"id": "d3", "t": "ang", "e": "l1", "e2": "l2", "r1": 0, "r2": 0, "sg": 1, "v": 60}]}
        r = solve(sk)
        self.assertTrue(r["ok"], r)
        u, v = r["points"]["p3"]
        self.assertAlmostEqual(math.degrees(math.atan2(v, u)), 60, places=5)
        sk["dims"][2].update(r2=1, v=30)  # the second line taken from its far end: 30° from the reversed ray
        r = solve(sk)
        u, v = r["points"]["p3"]
        self.assertAlmostEqual(abs(math.degrees(math.atan2(-v, -u))), 30, places=4)
        with self.assertRaises(SketchError):
            sk["dims"][2]["v"] = 180
            solve(sk)

    def test_which_points_are_free(self):
        """detail: a rectangle with its corner and width locked — the far side (and the circle) still free."""
        dims = LOCK_CORNER + [{"id": "d3", "t": "len", "e": "l1", "v": 40}]
        r = solve(plate(dims=dims), detail=True)
        free = set(r["free"]["points"])
        self.assertNotIn("p1", free)                      # the locked corner
        self.assertNotIn("p2", free)                      # the corner the width reaches
        self.assertTrue({"p3", "p4"} <= free)             # the height is free
        self.assertIn("c1", r["free"]["radii"])
        self.assertNotIn("free", solve(plate(dims=dims)))  # (only when asked)

    def test_point_from_a_slanted_line(self):
        sk = {"points": {"p1": [0, 0], "p2": [10, 10], "p3": [0, 8]},
              "entities": [{"id": "l1", "t": "line", "a": "p1", "b": "p2"}, {"id": "c1", "t": "circle", "c": "p3", "r": 1}],
              "constraints": [], "dims": [{"id": "d1", "t": "pl", "a": "p3", "e": "l1", "v": 4}]}
        r = solve(sk)
        self.assertTrue(r["ok"], r)
        (x1, y1), (x2, y2), (px, py) = r["points"]["p1"], r["points"]["p2"], r["points"]["p3"]
        self.assertAlmostEqual(abs((x2 - x1) * (py - y1) - (y2 - y1) * (px - x1)) / math.hypot(x2 - x1, y2 - y1), 4, places=5)

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

    def test_rounded_corner_stays_tangent(self):
        sk = rounded()
        for d in sk["dims"]:
            if d["id"] == "d3":
                d["v"] = 60  # wider: the rounding moves with the corner, still R5 and tangent
        r = solve(sk)
        self.assertTrue(r["ok"], r)
        P = r["points"]
        for k, want in {"p3": [60, 20], "t1": [60, 15], "t2": [55, 20], "c": [55, 15]}.items():
            self.assertAlmostEqual(P[k][0], want[0], places=6)
            self.assertAlmostEqual(P[k][1], want[1], places=6)
        self.assertEqual(r["dof"], 0)
        # without the height locked: a typed width keeps every height (keep="v"); without keep the solver may drift
        free = rounded()
        free["dims"] = [x for x in free["dims"] if x["id"] != "d4"]
        free["dims"][2]["v"] = 60
        r2 = solve(free, {"p1": [0, 0]}, keep="v")
        self.assertTrue(r2["ok"], r2)
        self.assertTrue(all(abs(r2["points"][k][1] - free["points"][k][1]) < 1e-9 for k in free["points"]))
        self.assertAlmostEqual(r2["points"]["p3"][0], 60, places=6)
        sk["dims"][-1]["v"] = 8  # a bigger radius: the tangent points slide along the lines
        r = solve(sk)
        self.assertAlmostEqual(r["points"]["t1"][1], 12, places=6)
        self.assertAlmostEqual(r["points"]["t2"][0], 52, places=6)

    def test_trimmed_end_stays_on_its_cutter(self):
        # a line from the origin, its end trimmed back to a circle (Ø10 at (30, 0)): "on" keeps it on the circle
        sk = {"points": {"c": [30, 0], "e": [25, 0]}, "entities": [{"id": "l1", "t": "line", "a": "O", "b": "e"}, {"id": "k", "t": "circle", "c": "c", "r": 5}],
              "constraints": [{"id": "k1", "t": "h", "e": "l1"}, {"id": "k2", "t": "on", "p": "e", "e": "k"}],
              "dims": [{"id": "d1", "t": "dx", "a": "O", "b": "c", "v": 30}, {"id": "d2", "t": "dy", "a": "O", "b": "c", "v": 0}, {"id": "d3", "t": "dia", "e": "k", "v": 16}]}
        r = solve(sk)
        self.assertTrue(r["ok"], r)
        self.assertAlmostEqual(r["points"]["e"][0], 22, places=6)  # 30 - 8: still on the (bigger) circle
        self.assertAlmostEqual(r["points"]["e"][1], 0, places=6)

    def test_relations(self):
        import math as m
        # two free lines: parallel, then equal in length to the first (which is locked at 30)
        sk = {"points": {"a": [0, 0], "b": [30, 0], "c": [0, 10], "d": [20, 17]},
              "entities": [{"id": "l1", "t": "line", "a": "a", "b": "b"}, {"id": "l2", "t": "line", "a": "c", "b": "d"}],
              "constraints": [{"id": "k1", "t": "par", "e": "l1", "e2": "l2"}, {"id": "k2", "t": "eq", "e": "l1", "e2": "l2"},
                              {"id": "k3", "t": "fix", "p": "a", "at": [0, 0]}, {"id": "k4", "t": "fix", "p": "c", "at": [0, 10]}],
              "dims": [{"id": "d1", "t": "len", "e": "l1", "v": 30}]}
        r = solve(sk)
        self.assertTrue(r["ok"], r)
        a, b, c, d = (r["points"][k] for k in "abcd")
        u, v = [b[0] - a[0], b[1] - a[1]], [d[0] - c[0], d[1] - c[1]]
        self.assertAlmostEqual(u[0] * v[1] - u[1] * v[0], 0, places=6)  # parallel
        self.assertAlmostEqual(m.hypot(*v), 30, places=6)  # equal
        self.assertEqual(r["points"]["a"], [0, 0])  # fixed
        # perpendicular
        sk["constraints"][0]["t"] = "perp"
        r = solve(sk)
        a, b, c, d = (r["points"][k] for k in "abcd")
        self.assertAlmostEqual((b[0] - a[0]) * (d[0] - c[0]) + (b[1] - a[1]) * (d[1] - c[1]), 0, places=6)
        # concentric circles, equal circles, a line tangent to a circle
        sk2 = {"points": {"o1": [0, 0], "o2": [3, 2], "p": [-10, 9], "q": [10, 9]},
               "entities": [{"id": "c1", "t": "circle", "c": "o1", "r": 5}, {"id": "c2", "t": "circle", "c": "o2", "r": 2},
                            {"id": "l1", "t": "line", "a": "p", "b": "q"}],
               "constraints": [{"id": "k1", "t": "conc", "e": "c1", "e2": "c2"}, {"id": "k2", "t": "tang", "e": "l1", "e2": "c1"},
                               {"id": "k3", "t": "fix", "p": "o1", "at": [0, 0]}, {"id": "h", "t": "h", "e": "l1"}],
               "dims": [{"id": "d1", "t": "dia", "e": "c1", "v": 10}]}
        r = solve(sk2)
        self.assertTrue(r["ok"], r)
        self.assertEqual([round(x, 6) for x in r["points"]["o2"]], [0, 0])  # on the same centre
        self.assertAlmostEqual(abs(r["points"]["p"][1]), 5, places=5)  # the horizontal line touches the Ø10 circle
        # a point on a line (coincident)
        sk3 = {"points": {"a": [0, 0], "b": [20, 0], "x": [5, 4]}, "entities": [{"id": "l1", "t": "line", "a": "a", "b": "b"}],
               "constraints": [{"id": "k1", "t": "coin", "p": "x", "e": "l1"}, {"id": "h", "t": "h", "e": "l1"}, {"id": "f", "t": "fix", "p": "a", "at": [0, 0]}], "dims": []}
        r = solve(sk3)
        self.assertAlmostEqual(r["points"]["x"][1], 0, places=6)
        # a relation that contradicts a lock is named in the conflicts
        bad = {**sk, "constraints": sk["constraints"] + [{"id": "k9", "t": "perp", "e": "l1", "e2": "l2"}]}
        r = solve(bad)
        self.assertFalse(r["ok"])
        self.assertTrue({"k1", "k9"} & set(r["conflicts"]), r["conflicts"])

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

    def test_rounded_corner_solid(self):
        f = [{"id": "S1", "type": "sketch", "plane": {"datum": "XY"}, **rounded()}, {"id": "E1", "type": "extrude", "sketch": "S1", "op": "add", "d": 2}]
        r = doc.rebuild({"features": f})
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(r["body"]["volume"], 2 * (800 - (4 - math.pi) / 4 * 25), delta=1e-6)
        self.assertIn("E1:side:a1", {x["name"] for x in r["body"]["faces"]})

    def test_l_shape_polyline(self):
        pts = {"a": [0, 0], "b": [30, 0], "c": [30, 10], "d": [10, 10], "e": [10, 25], "f": [0, 25]}
        names = list(pts)
        lines = [{"id": f"l{i}", "t": "line", "a": names[i], "b": names[(i + 1) % 6]} for i in range(6)]
        sk = {"id": "S1", "type": "sketch", "plane": {"datum": "XY"}, "points": pts, "entities": lines}
        r = doc.rebuild({"features": [sk, {"id": "E1", "type": "extrude", "sketch": "S1", "op": "add", "d": 2}]})
        self.assertAlmostEqual(r["body"]["volume"], (30 * 10 + 10 * 15) * 2, delta=1e-6)
        # an open chain makes no face: fine as a sketch (a sweep's path), the extrude says why it cannot
        sk["entities"] = lines[:4]
        r = doc.rebuild({"features": [sk, {"id": "E1", "type": "extrude", "sketch": "S1", "op": "add", "d": 2}]})
        self.assertTrue(r["features"][0]["ok"])
        self.assertIn("no closed shape", r["features"][1]["issues"][0])


if __name__ == "__main__":
    unittest.main()
