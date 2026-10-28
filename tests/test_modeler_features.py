"""Fillet, chamfer and hole on a model part, and named faces: exact volumes, and a rounding that stays on
the same edge when an earlier size changes. Skipped without the CAD kernel.

Run:  python -m unittest discover -s tests -v
"""
import math
import unittest

from auto3d.modeler import available
from test_modeler_kernel import watertight

OCC = available("occ")
if OCC:
    from auto3d.modeler import doc


def box(w=40, h=20, d=10):
    pts = {"p1": [0, 0], "p2": [w, 0], "p3": [w, h], "p4": [0, h]}
    lines = [{"id": f"l{i + 1}", "t": "line", "a": f"p{i + 1}", "b": f"p{(i + 1) % 4 + 1}"} for i in range(4)]
    return [{"id": "S1", "type": "sketch", "plane": {"datum": "XY"}, "points": pts, "entities": lines},
            {"id": "E1", "type": "extrude", "sketch": "S1", "op": "add", "d": d}]


def vol(*features):
    r = doc.rebuild({"features": list(features)})
    return r, (r["body"] or {}).get("volume")


@unittest.skipUnless(OCC, "OCP not installed")
class TestFeatures(unittest.TestCase):
    def test_faces_are_named(self):
        r, _ = vol(*box())
        names = sorted(f.get("name") for f in r["body"]["faces"])
        self.assertEqual(names, ["E1:end", "E1:side:l1", "E1:side:l2", "E1:side:l3", "E1:side:l4", "E1:start"])
        edge = next(e for e in r["body"]["edges"] if {r["body"]["faces"][i]["name"] for i in e["faces"]} == {"E1:side:l1", "E1:side:l2"})
        self.assertEqual(edge["mid"], [40, 0, 5])

    def test_fillet_follows_its_edge(self):
        # the vertical edge where the front (l1) and right (l2) walls meet, r 2
        fil = {"id": "F1", "type": "fillet", "edges": [{"a": "E1:side:l1", "b": "E1:side:l2", "fp": [40, 0, 5]}], "r": 2}
        r, v = vol(*box(), fil)
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, 8000 - (4 - math.pi) * 10, delta=1e-4)
        self.assertTrue(any(f.get("name") == "F1:round:0" for f in r["body"]["faces"]))
        # the box gets wider: the same edge (now at x 60) is rounded, found by its faces' names
        r, v = vol(*box(w=60), fil)
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, 12000 - (4 - math.pi) * 10, delta=1e-4)
        self.assertEqual(r["features"][-1]["warnings"], [])
        # a top edge (between the top and the front wall, 40 long)
        top = {"id": "F1", "type": "fillet", "edges": [{"a": "E1:end", "b": "E1:side:l1", "fp": [20, 0, 10]}], "r": 2}
        _, v = vol(*box(), top)
        self.assertAlmostEqual(v, 8000 - (4 - math.pi) * 40, delta=1e-4)

    def test_chamfer(self):
        ch = {"id": "C1", "type": "chamfer", "edges": [{"a": "E1:side:l1", "b": "E1:side:l2", "fp": [40, 0, 5]}], "d": 1}
        r, v = vol(*box(), ch)
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, 8000 - 0.5 * 10, delta=1e-4)

    def test_holes(self):
        top = {"face": {"name": "E1:end"}, "frame": {"o": [20, 10, 10], "x": [1, 0, 0], "n": [0, 0, 1]}}
        hole = {"id": "H1", "type": "hole", "plane": top, "points": [[0, 0], [12, 0]], "d": 6, "through": True}
        r, v = vol(*box(), hole)
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, 8000 - 2 * math.pi * 9 * 10, delta=1e-3)
        self.assertEqual(sorted(f["name"] for f in r["body"]["faces"] if f["name"].startswith("H1")), ["H1:hole:0", "H1:hole:1"])
        blind = {**hole, "points": [[0, 0]], "through": False, "depth": 4}
        r, v = vol(*box(), blind)
        self.assertAlmostEqual(v, 8000 - math.pi * 9 * 4, delta=1e-3)
        # a taller box: the hole goes from the (moved) top face
        r, v = vol(*box(d=15), blind)
        self.assertAlmostEqual(v, 12000 - math.pi * 9 * 4, delta=1e-3)
        self.assertAlmostEqual(r["frames"]["H1"]["o"][2], 15)

    def test_face_origin(self):
        """A hole / sketch on a face measured from the part's origin (world), the face's corner or a • point: at world
        (30, 10) it lands there and stays when the block grows the other way (−x); a corner origin follows the corner."""
        def block(x0=0, w=40, d=10):
            f = box(w, 20, d)
            f[0] = {**f[0], "points": {k: [u + x0, v] for k, (u, v) in f[0]["points"].items()}}
            return f

        def at(r, name):  # where a hole's wall is (its axis), x / y
            c = next(f["centroid"] for f in r["body"]["faces"] if f["name"] == name)
            return [round(c[0], 6), round(c[1], 6)]

        top = {"face": {"name": "E1:end"}, "frame": {"o": [20, 10, 10], "x": [1, 0, 0], "n": [0, 0, 1]}}
        hole = {"id": "H1", "type": "hole", "plane": {**top, "origin": "world"}, "points": [[30, 10]], "d": 4, "through": True}
        r, v = vol(*block(), hole)
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, 8000 - math.pi * 4 * 10, delta=1e-3)
        self.assertEqual(at(r, "H1:hole:0"), [30, 10])
        self.assertEqual(r["frames"]["H1"]["o"], [0, 0, 10])
        self.assertEqual(r["frames"]["H1"]["origin"], "world")
        r, v = vol(*block(x0=-20, w=60, d=25), hole)  # longer to −x, taller: the hole stays at (30, 10)
        self.assertEqual(at(r, "H1:hole:0"), [30, 10])
        self.assertAlmostEqual(v, 60 * 20 * 25 - math.pi * 4 * 25, delta=1e-3)
        # from the corner (the face's smallest u and v): (10, 5) from it — the corner moves to x −20, the hole with it
        hc = {**hole, "plane": {**top, "origin": "corner"}, "points": [[10, 5]]}
        r, _ = vol(*block(), hc)
        self.assertEqual(at(r, "H1:hole:0"), [10, 5])
        self.assertEqual(r["frames"]["H1"]["o"], [0, 0, 10])
        r, _ = vol(*block(x0=-20, w=60), hc)
        self.assertEqual(at(r, "H1:hole:0"), [-10, 5])
        # a sketch from the corner: a circle cut there
        sk = {"id": "S2", "type": "sketch", "plane": {**top, "origin": "corner"}, "points": {"c": [10, 10]},
              "entities": [{"id": "k", "t": "circle", "c": "c", "r": 3}]}
        cut = {"id": "E2", "type": "extrude", "sketch": "S2", "op": "cut", "through": True}
        r, v = vol(*block(x0=5), sk, cut)
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, 8000 - math.pi * 9 * 10, delta=1e-3)
        self.assertEqual(at(r, "E2:side:k"), [15, 10])
        # from a • reference point (the top's corner at x 40, y 0)
        pt = {"id": "P1", "type": "point", "at": {"vertex": {"faces": ["E1:end", "E1:side:l1", "E1:side:l2"], "fp": [40, 0, 10]}}}
        hp = {**hole, "plane": {**top, "origin": {"point": "P1"}}, "points": [[-5, 5]]}
        r, _ = vol(*block(), pt, hp)
        self.assertEqual(at(r, "H1:hole:0"), [35, 5])
        r, _ = vol(*block(w=60), pt, hp)
        self.assertEqual(at(r, "H1:hole:0"), [55, 5])
        # a STEP write -> read keeps the drilled solid
        from auto3d.modeler import kernel as K
        step = doc.export({"features": [*block(), hole]}, "step")
        self.assertAlmostEqual(K.volume(K.from_step(step)), 8000 - math.pi * 4 * 10, delta=1e-3)
        r, _ = vol(*block(), hc, {"id": "H2", "type": "hole", "plane": {**top, "origin": "corner"}, "points": [[5, 5]], "d": 2})
        self.assertEqual(r["frames"]["H2"]["o"], [0, 0, 10])  # (the top split by H1 still has the block's corner)
        self.assertTrue(r["ok"], r["features"])
        # error paths: an unknown point, an unknown kind, a corner of a face that is not there
        for origin, says in (({"point": "P9"}, "is not there"), ("middle", "origin:")):
            r, _ = vol(*block(), {**hole, "plane": {**top, "origin": origin}})
            self.assertFalse(r["features"][-1]["ok"])
            self.assertIn(says, r["features"][-1]["issues"][0])
        r, _ = vol(*block(), {**hole, "plane": {**top, "face": {"name": "E9:end"}, "origin": "corner"}})
        self.assertIn("corner", r["features"][-1]["issues"][0])

    def test_mid_plane(self):
        """A sketch midway between the front (y 0) and back (y 20) walls: at y 10; the box 30 deep: at y 15 — it follows
        both faces. A face that is gone keeps the place it had."""
        mid = {"face": {"name": "E1:side:l1"}, "mid": {"name": "E1:side:l3"}, "frame": {"o": [20, 10, 5], "x": [1, 0, 0], "n": [0, -1, 0]}}
        sk = {"id": "S2", "type": "sketch", "plane": mid, "points": {}, "entities": []}
        r, _ = vol(*box(), sk)
        self.assertAlmostEqual(r["frames"]["S2"]["o"][1], 10)
        r, _ = vol(*box(h=30), sk)
        self.assertAlmostEqual(r["frames"]["S2"]["o"][1], 15)
        r, _ = vol(*box(), {**sk, "plane": {**mid, "mid": {"name": "E9:end"}}})
        self.assertAlmostEqual(r["frames"]["S2"]["o"][1], 10)

    def test_hole_heads(self):
        """⌴ A counterbore (Ø10 × 4 over a Ø6 through hole) and ⌵ a countersink (Ø12 at 90° over Ø6: a cone 3 deep):
        exact volumes, the head's faces named; a head narrower than the hole refused."""
        top = {"face": {"name": "E1:end"}, "frame": {"o": [20, 10, 10], "x": [1, 0, 0], "n": [0, 0, 1]}}
        hole = {"id": "H1", "type": "hole", "plane": top, "points": [[0, 0]], "d": 6, "through": True}
        r, v = vol(*box(), {**hole, "head": "cbore", "head_d": 10, "head_depth": 4})
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, 8000 - math.pi * 9 * 10 - math.pi * (25 - 9) * 4, delta=1e-3)
        names = {n for f in r["body"]["faces"] for n in f.get("names") or [f.get("name")] if n and n.startswith("H1")}
        self.assertTrue({"H1:hole:0", "H1:cbore:0", "H1:cbore_floor:0"} <= names, names)
        r, v = vol(*box(), {**hole, "head": "csk", "head_d": 12})
        self.assertTrue(r["ok"], r["features"])
        cone = math.pi * 3 / 3 * (36 + 9 + 18) - math.pi * 9 * 3  # the frustum Ø12 -> Ø6 over 3, less the hole in it
        self.assertAlmostEqual(v, 8000 - math.pi * 9 * 10 - cone, delta=0.05)
        self.assertIn("H1:csk:0", {f.get("name") for f in r["body"]["faces"]})
        r, _ = vol(*box(), {**hole, "head": "cbore", "head_d": 5})
        self.assertFalse(r["ok"])
        self.assertIn("wider", r["features"][-1]["issues"][0])

    def test_threaded_hole(self):
        """A hole with thread M5: drilled Ø4.2 (its tap drill) whatever d says; the sheet labels it M5; an unknown
        thread refused."""
        top = {"face": {"name": "E1:end"}, "frame": {"o": [20, 10, 10], "x": [1, 0, 0], "n": [0, 0, 1]}}
        hole = {"id": "H1", "type": "hole", "plane": top, "points": [[0, 0], [10, 0]], "d": 9, "through": True, "thread": "M5"}
        r, v = vol(*box(), hole)
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, 8000 - 2 * math.pi * 2.1 ** 2 * 10, delta=1e-3)
        dims = [d for d in doc.sheet({"features": box() + [hole]}, "medium")["dims"] if d["kind"] == "dia"]
        self.assertTrue(dims and all(d.get("thread") == "M5" and d["count"] == 2 for d in dims), dims)
        r, _ = vol(*box(), {**hole, "thread": "M7"})
        self.assertFalse(r["ok"])

    def test_teardrop_hole(self):
        """▲ A teardrop (a sideways hole printed without support): Ø6 through the 20 deep block from its front face, its
        top a 45° point — the circle and the kite beyond it, (¾π + 1) r² × 20; watertight, the faces named, the STEP
        round trip; a thread keeps its tap drill; a counterbore gets the point too; a hole going down and a countersink
        refused; the drawing still says Ø6 and sizes no edge of the point."""
        front = {"face": {"name": "E1:side:l1"}, "frame": {"o": [20, 0, 5], "x": [1, 0, 0], "n": [0, -1, 0]}}
        hole = {"id": "H1", "type": "hole", "plane": front, "points": [[0, 0]], "d": 6, "through": True, "teardrop": True}
        tear = lambda r, depth: (0.75 * math.pi + 1) * r * r * depth  # noqa: E731
        r, v = vol(*box(), hole)
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, 8000 - tear(3, 20), delta=1e-3)
        self.assertTrue(watertight(r["body"]))
        faces = {f["name"]: f for f in r["body"]["faces"] if f["name"].startswith("H1")}
        self.assertEqual(sorted(faces), ["H1:hole:0", "H1:tear:0"])
        tops = [f["centroid"] for f in r["body"]["faces"] if f["name"] == "H1:tear:0"]
        self.assertEqual(len(tops), 2)
        self.assertTrue(all(c[2] > 5 + 3 / math.sqrt(2) for c in tops))  # the point is up (+z), above the round part
        from auto3d.modeler import kernel as K
        step = doc.export({"features": [*box(), hole]}, "step")
        self.assertAlmostEqual(K.volume(K.from_step(step)), 8000 - tear(3, 20), delta=1e-3)
        # a blind one, a thread (its tap drill round, the point added), a counterbore with its point
        r, v = vol(*box(), {**hole, "through": False, "depth": 8})
        self.assertAlmostEqual(v, 8000 - tear(3, 8), delta=1e-3)
        r, v = vol(*box(), {**hole, "thread": "M5"})
        self.assertAlmostEqual(v, 8000 - tear(2.1, 20), delta=1e-3)
        r, v = vol(*box(), {**hole, "d": 4, "head": "cbore", "head_d": 7, "head_depth": 3})
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, 8000 - tear(2, 20) - (tear(3.5, 3) - tear(2, 3)), delta=1e-3)
        names = {n for f in r["body"]["faces"] for n in f.get("names") or [f.get("name")] if n and n.startswith("H1")}
        self.assertTrue({"H1:hole:0", "H1:tear:0", "H1:cbore:0", "H1:cbore_tear:0", "H1:cbore_floor:0"} <= names, names)
        r, _ = vol(*box(), {**hole, "head": "csk", "head_d": 10})
        self.assertFalse(r["ok"])
        self.assertIn("countersink", r["features"][-1]["issues"][0])
        top = {"face": {"name": "E1:end"}, "frame": {"o": [20, 10, 10], "x": [1, 0, 0], "n": [0, 0, 1]}}
        r, v = vol(*box(), {**hole, "plane": top})
        self.assertFalse(r["ok"])
        self.assertIn("sideways", r["features"][-1]["issues"][0])
        self.assertAlmostEqual(v, 8000, delta=1e-6)
        # the drawing: Ø6 with its place, no R, no level / column at the point's edges (also in the full preset)
        for preset in ("medium", "full"):
            dims = doc.sheet({"features": box() + [hole]}, preset)["dims"]
            self.assertEqual([(x["kind"], x["a"]) for x in dims if x["kind"] in ("dia", "rad")], [("dia", "H1:hole:0")])
            self.assertTrue(any(x.get("b") == "H1:hole:0#c" for x in dims))
            self.assertFalse(any("tear:" in (x.get("a", "") + x.get("b", "")) for x in dims), dims)

    def test_round_then_hole_and_errors(self):
        fil = {"id": "F1", "type": "fillet", "edges": [{"a": "E1:side:l1", "b": "E1:side:l2", "fp": [40, 0, 5]}], "r": 50}
        r, v = vol(*box(), fil)
        self.assertFalse(r["features"][-1]["ok"])
        self.assertIn("does not fit here — at most 19.99 mm", r["features"][-1]["issues"][0])  # says how much does
        self.assertAlmostEqual(v, 8000, delta=1e-6)  # the rest still builds
        gone = {"id": "F1", "type": "fillet", "edges": [{"a": "X:1", "b": "X:2", "fp": [500, 500, 500]}], "r": 1}
        r, _ = vol(*box(), gone)
        self.assertIn("no longer there", r["features"][-1]["issues"][0])
        empty = {"id": "F1", "type": "fillet", "edges": [], "r": 1}
        r, _ = vol(*box(), empty)
        self.assertIn("at least one edge", r["features"][-1]["issues"][0])
        # rounding, then a sketch on a wall of the rounded body still finds its face
        ok = {**fil, "r": 2}
        side = {"face": {"name": "E1:side:l1"}, "frame": {"o": [20, 0, 5], "x": [1, 0, 0], "n": [0, -1, 0]}}
        sk = {"id": "S2", "type": "sketch", "plane": side, "points": {"c": [0, 0]}, "entities": [{"id": "k", "t": "circle", "c": "c", "r": 2}]}
        cut = {"id": "E2", "type": "extrude", "sketch": "S2", "op": "cut", "d": 3}
        r, v = vol(*box(), ok, sk, cut)
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, 8000 - (4 - math.pi) * 10 - math.pi * 4 * 3, delta=1e-3)


    def test_flush_faces_merge(self):
        """A wall standing flush on a plate (front, left and right walls in the plate's planes): each of those planes
        is one face after the add — no seam, no name on two faces (from the AI's report)."""
        pts = {"q1": [0, 0], "q2": [40, 0], "q3": [40, 5], "q4": [0, 5]}
        lines = [{"id": f"m{i + 1}", "t": "line", "a": f"q{i + 1}", "b": f"q{(i + 1) % 4 + 1}"} for i in range(4)]
        wall = [{"id": "S2", "type": "sketch", "plane": {"datum": "XY"}, "points": pts, "entities": lines},
                {"id": "E2", "type": "extrude", "sketch": "S2", "op": "add", "d": 30}]
        r, v = vol(*box(), *wall)
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, 40 * 20 * 10 + 40 * 5 * 20, delta=0.01)
        faces = r["body"]["faces"]
        front = [f for f in faces if f["type"] == "plane" and f.get("normal") and [round(c, 6) for c in f["normal"]] == [0, -1, 0]]
        self.assertEqual(len(front), 1, front)
        named = [f.get("name") for f in faces if f.get("name")]
        self.assertEqual(len(named), len(set(named)), named)

    def test_extrude_says_where_it_went(self):
        """An extrude's status says where it went: up from the XY plane +z 0 … 10; flipped -z -10 … 0; on the Front
        plane (its normal -y) -y."""
        r, _ = vol(*box())
        self.assertEqual(r["features"][-1]["went"], {"along": "+z", "range": [0, 10]})
        b = box()
        b[1] = {**b[1], "flip": True}
        r, _ = vol(*b)
        self.assertEqual(r["features"][-1]["went"], {"along": "-z", "range": [-10, 0]})
        b = box()
        b[0] = {**b[0], "plane": {"datum": "XZ"}}
        r, _ = vol(*b)
        self.assertEqual(r["features"][-1]["went"], {"along": "-y", "range": [-10, 0]})

    def test_rib(self):
        """A rib in an L bracket: a plate 40 × 20 × 5 and a wall 5 thick at its back (y 15 … 20) 30 tall; on the Right
        plane (YZ, x = 20 the middle) a line from the wall (y 15, z 25) to the plate (y 0, z 5) — the triangle below it
        filled, 4 thick: + ½ · 15 · 20 · 4."""
        pts = {"q1": [0, 15], "q2": [40, 15], "q3": [40, 20], "q4": [0, 20]}
        lines = [{"id": f"m{i + 1}", "t": "line", "a": f"q{i + 1}", "b": f"q{(i + 1) % 4 + 1}"} for i in range(4)]
        wall = [{"id": "S2", "type": "sketch", "plane": {"datum": "XY"}, "points": pts, "entities": lines},
                {"id": "E2", "type": "extrude", "sketch": "S2", "op": "add", "d": 30}]
        ln = {"id": "S3", "type": "sketch", "plane": {"datum": "YZ", "offset": 20}, "points": {"r1": [15, 25], "r2": [0, 5]},
              "entities": [{"id": "k1", "t": "line", "a": "r1", "b": "r2"}]}
        r0, v0 = vol(*box(d=5), *wall)
        r, v = vol(*box(d=5), *wall, ln, {"id": "R1", "type": "rib", "sketch": "S3", "t": 4})
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v - v0, 0.5 * 15 * 20 * 4, delta=0.01)
        names = {n for f in r["body"]["faces"] for n in f.get("names") or [f.get("name")] if n}
        self.assertTrue({"R1:side:k1", "R1:start", "R1:end"} <= names, names)
        # a line in the air (nothing to close against): refused
        air = {**ln, "points": {"r1": [15, 60], "r2": [0, 45]}}
        r, _ = vol(*box(d=5), *wall, air, {"id": "R1", "type": "rib", "sketch": "S3", "t": 4})
        self.assertFalse(r["ok"])

    def test_draft(self):
        """⟋ Draft: a 40 × 20 × 10 block's walls leaning in 5° — a frustum (top 2 × 10·tan 5° smaller each way)."""
        r, v = vol(*box(), {"id": "D1", "type": "draft", "of": "E1", "angle": 5})
        self.assertTrue(r["ok"], r["features"])
        k = 10 * math.tan(math.radians(5))
        a0, a1 = 40 * 20, (40 - 2 * k) * (20 - 2 * k)
        self.assertAlmostEqual(v, 10 / 3 * (a0 + a1 + math.sqrt(a0 * a1)), delta=1)
        r, _ = vol(*box(), {"id": "D1", "type": "draft", "of": "E1", "angle": 50})
        self.assertFalse(r["ok"])
        r, _ = vol(*box(), {"id": "D1", "type": "draft", "of": "NOPE", "angle": 5})
        self.assertIn("walls", r["features"][-1]["issues"][0])

    def test_revolve(self):
        # a 10 x 20 rectangle beside the vertical axis (x 5..15) spun a full turn: a tube
        pts = {"a": [5, 0], "b": [15, 0], "c": [15, 20], "d": [5, 20]}
        lines = [{"id": f"l{i}", "t": "line", "a": k, "b": "bcda"[i]} for i, k in enumerate("abcd")]
        sk = {"id": "S1", "type": "sketch", "plane": {"datum": "XZ"}, "points": pts, "entities": lines}
        rev = {"id": "R1", "type": "revolve", "sketch": "S1", "axis": "y", "angle": 360, "op": "add"}
        r, v = vol(sk, rev)
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, math.pi * (15 ** 2 - 5 ** 2) * 20, delta=1e-3)
        self.assertEqual([round(c, 6) for c in r["body"]["bbox"]], [-15, -15, 0, 15, 15, 20])  # around the world z axis
        _, v = vol(sk, {**rev, "angle": 90})
        self.assertAlmostEqual(v, math.pi * (15 ** 2 - 5 ** 2) * 20 / 4, delta=1e-3)
        # around one of its own lines (the left side, x 5): a solid cylinder r 10
        _, v = vol(sk, {**rev, "axis": "l3"})
        self.assertAlmostEqual(v, math.pi * 100 * 20, delta=1e-3)
        # crossing the axis is refused
        bad = {**sk, "points": {"a": [-5, 0], "b": [15, 0], "c": [15, 20], "d": [-5, 20]}}
        r, _ = vol(bad, rev)
        self.assertIn("crosses the axis", r["features"][-1]["issues"][0])
        # a construction line as the axis (x 25, away from the shape): not part of the outline, the shape spun round it
        cons = {**sk, "points": {**pts, "e": [25, -5], "f": [25, 30]}, "entities": lines + [{"id": "ax", "t": "line", "a": "e", "b": "f", "construction": True}]}
        r, v = vol(cons, {**rev, "axis": "ax"})
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, math.pi * (20 ** 2 - 10 ** 2) * 20, delta=1e-3)
        r, v = vol(cons, rev)  # (the extra line does not change the outline itself)
        self.assertAlmostEqual(v, math.pi * (15 ** 2 - 5 ** 2) * 20, delta=1e-3)

    def test_block_from_an_outline(self):
        # an L-shaped outline with a square hole, placed at (10, 5) and drawn twice as big
        L = [[[0, 0], [30, 0], [30, 10], [10, 10], [10, 25], [0, 25]], [[2, 2], [6, 2], [6, 6], [2, 6]]]
        sk = {"id": "S1", "type": "sketch", "plane": {"datum": "XY"}, "points": {},
              "entities": [{"id": "b1", "t": "block", "polys": [L], "at": [10, 5], "scale": 2}]}
        r, v = vol(sk, {"id": "E1", "type": "extrude", "sketch": "S1", "op": "add", "d": 3})
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, (30 * 10 + 10 * 15 - 16) * 4 * 3, delta=1e-6)
        self.assertEqual([round(c, 6) for c in r["body"]["bbox"]], [10, 5, 0, 70, 55, 3])

    def test_offset_endpoint(self):
        import server
        c = server.app.test_client()
        sq = [[[0, 0], [10, 0], [10, 10], [0, 10]]]
        r = c.post("/api/model/sketch/offset", json={"polys": [sq], "d": 2}).get_json()
        xs = [p[0] for p in r["polys"][0][0]]
        self.assertEqual((min(xs), max(xs), len(r["polys"][0][0])), (-2, 12, 4))  # sharp corners stay sharp
        r = c.post("/api/model/sketch/offset", json={"polys": [sq], "d": -6})
        self.assertEqual(r.status_code, 400)

    def test_profile_endpoint(self):
        import server
        from auto3d.outline import outline_model
        c = server.app.test_client()
        # the sample PDF: 78.7 cm long -> 787 mm, with its cutouts as holes or notches
        data = c.get("/api/sample").get_json()
        vals = {p["id"]: p["value"] for p in data["model"]["params"]}
        r = c.post("/api/model/profile", json={"model": data["model"], "values": vals}).get_json()
        self.assertAlmostEqual(r["width"], 787, delta=1e-6)
        self.assertEqual(r["name"], "initial draft")
        pts = [p for poly in r["polygons"] for p in poly[0]]
        self.assertEqual(min(p[0] for p in pts), 0)
        # a picture outline: a 100 x 50 px rectangle at 40 mm wide -> 40 x 20 mm
        m = outline_model([[[[0, 0], [100, 0], [100, 50], [0, 50]]]], 200, 100, width=40)
        m["preset"] = "solid"
        r = c.post("/api/model/profile", json={"model": m, "values": {p["id"]: p["value"] for p in m["params"]}}).get_json()
        self.assertAlmostEqual(r["width"], 40, delta=1e-6)
        self.assertAlmostEqual(r["height"], 20, delta=1e-6)
        bad = c.post("/api/model/profile", json={"model": {"kind": "outline"}})
        self.assertEqual(bad.status_code, 400)

    def test_assembly_step(self):
        from auto3d.modeler import kernel
        part = {"features": box()}
        # the box, and the same box turned 90° about z and moved 100 along x
        turned = [0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1, 0, 100, 0, 0, 1]
        step = doc.assembly_step([{"part": part, "matrix": None}, {"part": part, "matrix": turned}])
        shape = kernel.from_step(step)
        self.assertEqual(kernel.solids(shape), 2)
        self.assertAlmostEqual(kernel.volume(shape), 16000, delta=1e-3)
        bb = kernel.bbox(shape)
        self.assertAlmostEqual(bb[3], 100, delta=1e-6)   # turned: x from 80 to 100
        self.assertAlmostEqual(bb[4], 40, delta=1e-6)    # and y up to 40

    def test_shell(self):
        top = [{"name": "E1:end", "fp": [20, 10, 10]}]
        r, v = vol(*box(), {"id": "SH", "type": "shell", "faces": top, "t": 2})
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, 8000 - 36 * 16 * 8, delta=1e-3)  # an open box: inside 36 x 16 x 8
        r, _ = vol(*box(), {"id": "SH", "type": "shell", "faces": [], "t": 2})
        self.assertIn("leave open", r["features"][-1]["issues"][0])
        r, _ = vol(*box(), {"id": "SH", "type": "shell", "faces": top, "t": 30})
        self.assertFalse(r["features"][-1]["ok"])

    def test_mirror(self):
        # the box (0..40 in x) mirrored across YZ: a copy at -40..0, joined -> twice the volume, 80 wide
        r, v = vol(*box(), {"id": "M1", "type": "mirror", "of": "body", "plane": {"datum": "YZ"}, "copy": True})
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, 16000, delta=1e-3)
        self.assertAlmostEqual(r["body"]["bbox"][0], -40, delta=1e-6)
        # mirror only: the same volume, on the other side, its faces keep their names
        r, v = vol(*box(), {"id": "M1", "type": "mirror", "of": "body", "plane": {"datum": "YZ"}, "copy": False})
        self.assertAlmostEqual(v, 8000, delta=1e-3)
        self.assertAlmostEqual(r["body"]["bbox"][3], 0, delta=1e-6)
        self.assertIn("E1:end", {f["name"] for f in r["body"]["faces"]})
        # one step: a hole at x 10 mirrored across the box's middle (a face's plane at x = 20 → YZ offset) -> at x 30
        top = {"face": {"name": "E1:end"}, "frame": {"o": [20, 10, 10], "x": [1, 0, 0], "n": [0, 0, 1]}}
        hole = {"id": "H1", "type": "hole", "plane": top, "points": [[-10, 0]], "d": 4, "through": True}
        mid = {"datum": "YZ", "offset": 20}
        r, v = vol(*box(), hole, {"id": "M1", "type": "mirror", "of": "H1", "plane": mid})
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, 8000 - 2 * math.pi * 4 * 10, delta=1e-3)
        self.assertIn("M1:H1:hole:0", {f["name"] for f in r["body"]["faces"]})
        # across a face: the box's right wall (x = 40) -> the copy at 40..80
        r, v = vol(*box(), {"id": "M1", "type": "mirror", "plane": {"face": {"name": "E1:side:l2"}, "frame": {"o": [40, 10, 5], "x": [0, 1, 0], "n": [1, 0, 0]}}})
        self.assertAlmostEqual(v, 16000, delta=1e-3)
        self.assertAlmostEqual(r["body"]["bbox"][3], 80, delta=1e-6)
        # on itself: a warning
        r, _ = vol(*box(), {"id": "M1", "type": "mirror", "plane": mid})
        self.assertTrue(r["features"][-1]["warnings"])

    def test_split(self):
        """✂ Split: the 40 × 20 × 10 block cut at x = 20 -> two bodies of 4000 each, the cut faces named X1:cut:0 / :1;
        one side kept; a ⇳ Midway plane that follows the block; a STEP round trip with both; a plane that misses."""
        from auto3d.modeler import kernel as K
        import numpy as np
        mid = {"datum": "YZ", "offset": 20}
        r, v = vol(*box(), {"id": "X1", "type": "split", "plane": mid, "keep": "both"})
        self.assertTrue(r["ok"], r["features"])
        self.assertEqual(r["body"]["solids"], 2)
        self.assertEqual(r["features"][-1]["bodies"], 2)
        self.assertAlmostEqual(v, 8000, delta=1e-6)
        names = {f["name"] for f in r["body"]["faces"]}
        self.assertTrue({"X1:cut:0", "X1:cut:1", "E1:end"} <= names)
        # each piece on its own: 4000 mm³, closed (the two pieces touch, so the mesh is checked solid by solid)
        tri = np.frombuffer(r["body"]["positions"], np.float32).reshape(-1, 9)
        ids = np.frombuffer(r["body"]["face_ids"], np.uint32)
        solid = np.array([r["body"]["faces"][i]["solid"] for i in ids])
        for k in (0, 1):
            t = tri[solid == k].reshape(-1, 3, 3).astype(float)
            vk = abs(np.einsum("ij,ij->i", t[:, 0], np.cross(t[:, 1], t[:, 2])).sum()) / 6
            self.assertAlmostEqual(vk, 4000, delta=1e-2)
            self.assertTrue(watertight({"positions": tri[solid == k].tobytes()}))
        # keep one side: above = where the plane's normal (+x) points
        r, v = vol(*box(), {"id": "X1", "type": "split", "plane": {"datum": "YZ", "offset": 10}, "keep": "above"})
        self.assertAlmostEqual(v, 6000, delta=1e-6)
        self.assertEqual(r["body"]["solids"], 1)
        self.assertAlmostEqual(r["body"]["bbox"][0], 10, delta=1e-6)
        self.assertTrue(watertight(r["body"]))
        self.assertIn("X1:cut:0", {f["name"] for f in r["body"]["faces"]})
        r, v = vol(*box(), {"id": "X1", "type": "split", "plane": {"datum": "YZ", "offset": 10}, "keep": "below"})
        self.assertAlmostEqual(v, 2000, delta=1e-6)
        self.assertIn("X1:cut:1", {f["name"] for f in r["body"]["faces"]})
        # ⇳ Midway between the front and back walls (y 0 / 20): half the block; the block 30 deep -> still half
        between = {"face": {"name": "E1:side:l1"}, "mid": {"name": "E1:side:l3"}, "frame": {"o": [20, 10, 5], "x": [1, 0, 0], "n": [0, -1, 0]}}
        split = {"id": "X1", "type": "split", "plane": between, "keep": "above"}  # (above: towards -y, the front)
        r, v = vol(*box(), split)
        self.assertAlmostEqual(v, 4000, delta=1e-6)
        self.assertAlmostEqual(r["body"]["bbox"][4], 10, delta=1e-6)
        r, v = vol(*box(h=30), split)
        self.assertAlmostEqual(v, 6000, delta=1e-6)
        self.assertAlmostEqual(r["body"]["bbox"][4], 15, delta=1e-6)
        # a face's plane moved along its normal: the top (z 10) 4 mm down -> keep below: 40 × 20 × 6
        top = {"face": {"name": "E1:end"}, "frame": {"o": [20, 10, 10], "x": [1, 0, 0], "n": [0, 0, 1]}, "offset": -4}
        r, v = vol(*box(), {"id": "X1", "type": "split", "plane": top, "keep": "below"})
        self.assertAlmostEqual(v, 4800, delta=1e-6)
        # later steps see both bodies: a hole through both, a STEP file with two solids
        hole = {"id": "H1", "type": "hole", "plane": {**top, "offset": 0}, "points": [[-10, 0], [10, 0]], "d": 4, "through": True}
        feats = [*box(), {"id": "X1", "type": "split", "plane": mid, "keep": "both"}, hole]
        r, v = vol(*feats)
        self.assertTrue(r["ok"], r["features"])
        self.assertEqual(r["body"]["solids"], 2)
        self.assertAlmostEqual(v, 8000 - 2 * math.pi * 4 * 10, delta=1e-3)
        back = K.from_step(doc.export({"features": feats}, "step"))
        self.assertEqual(K.solids(back), 2)
        self.assertAlmostEqual(K.volume(back), v, delta=1e-3)
        # a plane that misses the part, and an unknown keep: clear issues
        r, _ = vol(*box(), {"id": "X1", "type": "split", "plane": {"datum": "YZ", "offset": 50}})
        self.assertFalse(r["ok"])
        self.assertIn("does not cross the part", r["features"][-1]["issues"][0])
        r, _ = vol(*box(), {"id": "X1", "type": "split", "plane": mid, "keep": "left"})
        self.assertIn("keep", r["features"][-1]["issues"][0])

    def test_patterns(self):
        top = {"face": {"name": "E1:end"}, "frame": {"o": [5, 10, 10], "x": [1, 0, 0], "n": [0, 0, 1]}}
        hole = {"id": "H1", "type": "hole", "plane": top, "points": [[0, 0]], "d": 4, "through": True}
        row = {"id": "P1", "type": "pattern", "features": ["H1"], "kind": "linear", "dir": [1, 0, 0], "count": 4, "spacing": 10}
        r, v = vol(*box(), hole, row)
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, 8000 - 4 * math.pi * 4 * 10, delta=1e-3)
        self.assertIn("P1:3:H1:hole:0", {f["name"] for f in r["body"]["faces"]})
        # the pattern follows when the hole moves; a row of bosses (add)
        boss = {"id": "S2", "type": "sketch", "plane": top, "points": {"c": [0, 0]}, "entities": [{"id": "c1", "t": "circle", "c": "c", "r": 2}]}
        bump = {"id": "E2", "type": "extrude", "sketch": "S2", "op": "add", "d": 3}
        r, v = vol(*box(), boss, bump, {**row, "features": ["E2"], "count": 3})
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, 8000 + 3 * math.pi * 4 * 3, delta=1e-3)
        # around the centre of a disc: 6 holes on a circle, evenly
        disc = [{"id": "S1", "type": "sketch", "plane": {"datum": "XY"}, "points": {"c": [0, 0]}, "entities": [{"id": "c1", "t": "circle", "c": "c", "r": 30}]},
                {"id": "E1", "type": "extrude", "sketch": "S1", "op": "add", "d": 5}]
        dtop = {"face": {"name": "E1:end"}, "frame": {"o": [0, 0, 5], "x": [1, 0, 0], "n": [0, 0, 1]}}
        h = {"id": "H1", "type": "hole", "plane": dtop, "points": [[20, 0]], "d": 6, "through": True}
        ring = {"id": "P1", "type": "pattern", "features": ["H1"], "kind": "circular", "axis": {"o": [0, 0, 0], "d": [0, 0, 1]}, "count": 6}
        r, v = vol(*disc, h, ring)
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, math.pi * 900 * 5 - 6 * math.pi * 9 * 5, delta=1e-2)
        # a pattern of a pattern: the row repeated 2 times along y
        r, v = vol(*box(), hole, row, {"id": "P2", "type": "pattern", "features": ["H1", "P1"], "dir": [0, 1, 0], "count": 2, "spacing": 5})
        self.assertAlmostEqual(v, 8000 - 8 * math.pi * 4 * 10, delta=1e-3)
        # copies that land outside the part: a warning
        r, v = vol(*box(), hole, {**row, "dir": [0, 1, 0], "spacing": 50, "count": 2})
        self.assertTrue(r["ok"])
        self.assertIn("changed nothing", r["features"][-1]["warnings"][0])
        # refusals
        for bad, msg in [({**row, "features": []}, "Choose what"), ({**row, "features": ["S1"]}, "cannot be repeated"),
                         ({**row, "count": 1}, "at least 2"), ({**row, "count": 500}, "too many")]:
            r, _ = vol(*box(), hole, bad)
            self.assertFalse(r["features"][-1]["ok"])
            self.assertIn(msg, r["features"][-1]["issues"][0])

    def test_dimensions_follow_the_part_edges(self):
        top = {"face": {"name": "E1:end"}, "frame": {"o": [20, 10, 10], "x": [1, 0, 0], "n": [0, 0, 1]}}
        right = {"a": "E1:end", "b": "E1:side:l2", "fp": [40, 10, 10]}
        corner = {"faces": ["E1:end", "E1:side:l1", "E1:side:l2"], "fp": [40, 0, 10]}
        # a sketch circle 10 from the right edge and 5 from the front-right corner
        sk = {"id": "S2", "type": "sketch", "plane": top, "points": {"c": [10, -5]}, "entities": [{"id": "k", "t": "circle", "c": "c", "r": 3}],
              "dims": [{"id": "d1", "t": "dx", "a": {"ref": [20, 0], "edge": right}, "b": "c", "v": -10},
                       {"id": "d2", "t": "dy", "a": {"ref": [20, -10], "vertex": corner}, "b": "c", "v": 5}, {"id": "d3", "t": "dia", "e": "k", "v": 6}]}
        cut = {"id": "E2", "type": "extrude", "sketch": "S2", "op": "cut", "through": True}
        hole = lambda r: next(f for f in r["body"]["faces"] if f["type"] == "cylinder")["centroid"]  # noqa: E731
        r, _ = vol(*box(), sk, cut)
        self.assertEqual(hole(r)[:2], [30, 5])
        self.assertNotIn("update", r["features"][2])  # nothing moved
        r, _ = vol(*box(w=60, h=30), sk, cut)  # wider and deeper: still 10 from the right, 5 from the front
        self.assertEqual(hole(r)[:2], [50, 5])
        up = r["features"][2]["update"]
        self.assertEqual(up["points"]["c"], [30, -5])
        self.assertEqual(up["dims"][0]["a"]["ref"], [40, 5])  # the edge's middle, now
        self.assertEqual(r["features"][2]["warnings"], [])
        # a hole step placed from the face's edges
        hf = {"id": "H1", "type": "hole", "plane": top, "points": [[10, -5]], "d": 4, "through": True,
              "from": [{"x": {"edge": right, "d": -10}, "y": {"edge": {"a": "E1:end", "b": "E1:side:l1", "fp": [20, 0, 10]}, "d": 5}}]}
        r, v = vol(*box(w=60, h=30), hf)
        self.assertEqual(hole(r)[:2], [50, 5])
        self.assertEqual(r["features"][-1]["update"], {"points": [[30, -5]]})
        self.assertAlmostEqual(v, 60 * 30 * 10 - math.pi * 4 * 10, delta=1e-3)
        # the edge is gone (a different first sketch): the hole stays and says so
        r, _ = vol(*box(), {**hf, "from": [{"x": {"edge": {"a": "X:end", "b": "X:side", "fp": [999, 0, 0]}, "d": 3}}]})
        self.assertTrue(r["ok"])
        self.assertIn("edge is gone", r["features"][-1]["warnings"][0])

    def test_extrude_up_to_a_face(self):
        # a pin from the bed (XY) up to the box's top + 5 mm: it follows the top when the box gets taller
        sk = {"id": "S2", "type": "sketch", "plane": {"datum": "XY"}, "points": {"c": [10, 10]}, "entities": [{"id": "k", "t": "circle", "c": "c", "r": 3}]}
        pin = {"id": "E2", "type": "extrude", "sketch": "S2", "op": "add", "upto": {"name": "E1:end", "fp": [20, 10, 10]}, "offset": 5}
        r, v = vol(*box(), sk, pin)
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, 8000 + math.pi * 9 * 5, delta=1e-3)
        r, v = vol(*box(d=20), sk, pin)
        self.assertAlmostEqual(v, 16000 + math.pi * 9 * 5, delta=1e-3)
        self.assertAlmostEqual(r["body"]["bbox"][5], 25)
        # a pocket cut from the top down to 2 mm above the bottom (offset -2 = short of the bottom face)
        top = {"face": {"name": "E1:end"}, "frame": {"o": [20, 10, 10], "x": [1, 0, 0], "n": [0, 0, 1]}}
        sk3 = {"id": "S3", "type": "sketch", "plane": top, "points": {"c": [0, 0]}, "entities": [{"id": "k", "t": "circle", "c": "c", "r": 4}]}
        pocket = {"id": "E3", "type": "extrude", "sketch": "S3", "op": "cut", "upto": {"name": "E1:start", "fp": [20, 10, 0]}, "offset": -2}
        r, v = vol(*box(), sk3, pocket)
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, 8000 - math.pi * 16 * 8, delta=1e-3)
        # a wall is not parallel to the sketch: refused
        r, _ = vol(*box(), sk, {**pin, "upto": {"name": "E1:side:l1", "fp": [20, 0, 5]}})
        self.assertIn("parallel", r["features"][-1]["issues"][0])

    def two_plates(self):
        """Plate B 40 × 40 at z 0 … 10, plate A above it at z 20 … 30 (a 10 mm gap), a wall x 0 … 5 joining them; and
        a circle r 5 at (20, 20) sketched on the XY plane moved to z."""
        def rect(i, w, z):
            pts = {"p1": [0, 0], "p2": [w, 0], "p3": [w, 40], "p4": [0, 40]}
            lines = [{"id": f"l{k + 1}", "t": "line", "a": f"p{k + 1}", "b": f"p{(k + 1) % 4 + 1}"} for k in range(4)]
            return [{"id": f"S{i}", "type": "sketch", "plane": {"datum": "XY", "offset": z} if z else {"datum": "XY"}, "points": pts, "entities": lines},
                    {"id": f"E{i}", "type": "extrude", "sketch": f"S{i}", "op": "add", "d": 10}]
        circle = lambda z: {"id": "S9", "type": "sketch", "plane": {"datum": "XY", "offset": z}, "points": {"c": [20, 20]},  # noqa: E731
                            "entities": [{"id": "k", "t": "circle", "c": "c", "r": 5}]}
        return [*rect(1, 40, 0), *rect(2, 5, 10), *rect(3, 40, 20)], circle, 2 * 16000 + 5 * 40 * 10

    def test_extrude_up_to_next(self):
        """Up to next: a cut from plate A's top goes through A only (it stops at A's underside, not in B); a boss from
        B's top fills the gap up to A's underside; the mesh stays watertight; nothing in the way -> an issue."""
        from auto3d.modeler import kernel as K
        plates, circle, v0 = self.two_plates()
        cut = {"id": "C1", "type": "extrude", "sketch": "S9", "op": "cut", "upto_next": True}
        r, v = vol(*plates, circle(30), cut)
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, v0 - math.pi * 25 * 10, delta=1e-3)
        self.assertEqual(r["features"][-1]["went"], {"along": "-z", "range": [20, 30]})
        self.assertTrue(watertight(r["body"]))
        boss = {**cut, "op": "add"}
        r, v = vol(*plates, circle(10), boss)
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, v0 + math.pi * 25 * 10, delta=1e-3)
        self.assertEqual(r["features"][-1]["went"], {"along": "+z", "range": [10, 20]})
        self.assertIn("C1:side:k", {f.get("name") for f in r["body"]["faces"]})
        self.assertTrue(watertight(r["body"]))
        # it follows the part: the gap 15 tall (plate A moved up 5) -> the boss 15 tall
        moved = [*plates[:4], {**plates[4], "plane": {"datum": "XY", "offset": 25}}, plates[5]]
        moved[3] = {**moved[3], "d": 15}
        r, v = vol(*moved, circle(10), boss)
        self.assertAlmostEqual(v, v0 + 5 * 40 * 5 + math.pi * 25 * 15, delta=1e-3)
        # STEP write -> read: the same solid
        step = doc.export({"features": [*plates, circle(10), boss]}, "step")
        self.assertAlmostEqual(K.volume(K.from_step(step)), v0 + math.pi * 25 * 10, delta=1e-3)
        # nothing in the way: a boss up from A's top, a cut from A's top going up (flipped)
        r, _ = vol(*plates, circle(30), boss)
        self.assertFalse(r["ok"])
        self.assertIn("Up to next", r["features"][-1]["issues"][0])
        r, _ = vol(*plates, circle(30), {**cut, "flip": True})
        self.assertIn("meets no part", r["features"][-1]["issues"][0])
        # no part yet
        r, _ = vol(circle(0), {**boss, "op": "add"})
        self.assertIn("no part", r["features"][-1]["issues"][0])

    def test_extrude_other_side(self):
        """＋ Other side: 10 up and d2 4 down -> 40 × 20 × 14, its range said for both sides; a cut 3 down from the
        top and 2 up (nothing there); symmetric wins over d2; d2 not > 0 -> an issue."""
        from auto3d.modeler import kernel as K
        b = box()
        b[1] = {**b[1], "d2": 4}
        r, v = vol(*b)
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, 40 * 20 * 14, delta=1e-6)
        self.assertEqual(r["features"][-1]["went"], {"along": "+z", "range": [0, 10], "other_side": [-4, 0]})
        self.assertEqual(r["body"]["bbox"][2], -4)
        names = sorted(f.get("name") for f in r["body"]["faces"])
        self.assertEqual(names, ["E1:end", "E1:side:l1", "E1:side:l2", "E1:side:l3", "E1:side:l4", "E1:start"])
        self.assertTrue(watertight(r["body"]))
        step = doc.export({"features": b}, "step")
        self.assertAlmostEqual(K.volume(K.from_step(step)), 40 * 20 * 14, delta=1e-3)
        # a pocket from the top: 3 down into the part, 2 up (above it: nothing more)
        top = {"face": {"name": "E1:end"}, "frame": {"o": [20, 10, 10], "x": [1, 0, 0], "n": [0, 0, 1]}}
        sk = {"id": "S2", "type": "sketch", "plane": top, "points": {"c": [0, 0]}, "entities": [{"id": "k", "t": "circle", "c": "c", "r": 4}]}
        r, v = vol(*box(), sk, {"id": "E2", "type": "extrude", "sketch": "S2", "op": "cut", "d": 3, "d2": 2})
        self.assertAlmostEqual(v, 8000 - math.pi * 16 * 3, delta=1e-3)
        self.assertEqual(r["features"][-1]["went"]["other_side"], [10, 12])
        # symmetric: d2 is not used
        b[1] = {**b[1], "symmetric": True}
        _, v = vol(*b)
        self.assertAlmostEqual(v, 8000, delta=1e-6)
        b[1] = {**b[1], "symmetric": False, "d2": -3}
        r, _ = vol(*b)
        self.assertIn("greater than zero", r["features"][-1]["issues"][0])

    def test_hole_measured_from_another_hole(self):
        top = {"face": {"name": "E1:end"}, "frame": {"o": [20, 10, 10], "x": [1, 0, 0], "n": [0, 0, 1]}}
        h1 = {"id": "H1", "type": "hole", "plane": top, "points": [[-10, 0]], "d": 4, "through": True}
        rim = {"a": "H1:hole:0", "b": "E1:end", "fp": [8, 10, 10]}
        h2 = {"id": "H2", "type": "hole", "plane": top, "points": [[5, 0]], "d": 3, "through": True, "from": [{"x": {"edge": rim, "d": 15, "round": True}}]}
        r, _ = vol(*box(), h1, h2)
        self.assertNotIn("update", r["features"][-1])  # already 15 from H1's centre
        r, _ = vol(*box(), {**h1, "points": [[-5, 0]]}, h2)  # H1 moves 5 to the right: H2 goes along
        self.assertEqual(r["features"][-1]["update"], {"points": [[10, 0]]})
        xs = sorted(round(f["centroid"][0], 3) for f in r["body"]["faces"] if f["type"] == "cylinder")
        self.assertEqual(xs, [15, 30])
        # a hole measured from another hole of the same step: placed after it, follows it
        two = {"id": "H1", "type": "hole", "plane": top, "points": [[-10, 0], [0, 0]], "d": 3, "through": True, "from": [{}, {"x": {"hole": 0, "d": 12}}]}
        r, _ = vol(*box(), two)
        self.assertEqual(r["features"][-1]["update"], {"points": [[-10, 0], [2, 0]]})

    def test_hole_midway_between_two_edges(self):
        """A hole in the middle of a 40 × 40 block's top ({mid: [edge, edge]} on x and y) stays in the middle when the
        block becomes 60 wide; an edge gone: it stays and says so."""
        from auto3d.modeler import kernel as K
        top = {"face": {"name": "E1:end"}, "frame": {"o": [20, 20, 10], "x": [1, 0, 0], "n": [0, 0, 1]}}
        edge = lambda side, fp: {"a": "E1:end", "b": f"E1:side:{side}", "fp": fp}  # noqa: E731
        mid = {"x": {"mid": [edge("l4", [0, 20, 10]), edge("l2", [40, 20, 10])], "d": 0},
               "y": {"mid": [edge("l1", [20, 0, 10]), edge("l3", [20, 40, 10])], "d": 0}}
        hole = {"id": "H1", "type": "hole", "plane": top, "points": [[0, 0]], "d": 5, "through": True, "from": [mid]}
        r, v = vol(*box(h=40), hole)
        self.assertTrue(r["ok"], r["features"])
        self.assertNotIn("update", r["features"][-1])  # already in the middle
        self.assertAlmostEqual(v, 40 * 40 * 10 - math.pi * 6.25 * 10, delta=1e-3)
        r, v = vol(*box(w=60, h=40), hole)  # 60 wide: the top's frame stays put (its centre was at x 20) — the hole goes to x 30
        self.assertEqual(r["features"][-1]["update"], {"points": [[10, 0]]})
        x = next(f for f in r["body"]["faces"] if f["type"] == "cylinder")["centroid"]
        self.assertEqual([round(c, 9) for c in x[:2]], [30, 20])
        self.assertEqual(r["features"][-1]["warnings"], [])
        self.assertAlmostEqual(v, 60 * 40 * 10 - math.pi * 6.25 * 10, delta=1e-3)
        self.assertTrue(watertight(r["body"]))
        step = doc.export({"features": [*box(w=60, h=40), hole]}, "step")
        self.assertAlmostEqual(K.volume(K.from_step(step)), v, delta=1e-3)
        # an edge gone: the hole stays where it was, with a warning
        gone = {"x": {"mid": [edge("l4", [0, 20, 10]), {"a": "X:end", "b": "X:side", "fp": [999, 0, 0]}], "d": 0}}
        r, _ = vol(*box(h=40), {**hole, "points": [[3, 0]], "from": [gone]})
        self.assertTrue(r["ok"])
        self.assertIn("midway between is gone", r["features"][-1]["warnings"][0])
        self.assertNotIn("update", r["features"][-1])

    def test_distances_from_a_round_face_axis(self):
        def cross(x=30):  # a cross hole along y (an extrude cut on the front plane): its axis runs along the top face
            sk = {"id": "S2", "type": "sketch", "plane": {"datum": "XZ"}, "points": {"o": [x, 10]}, "entities": [{"id": "k", "t": "circle", "c": "o", "r": 4}]}
            return [sk, {"id": "E2", "type": "extrude", "sketch": "S2", "op": "cut", "d": 100, "symmetric": True}]
        top = {"face": {"name": "E1:end"}, "frame": {"o": [30, 20, 20], "x": [1, 0, 0], "n": [0, 0, 1]}}
        axis = {"face": "E2:side:k", "fp": [30, 20, 10]}
        # a circle on the top 15 to the right of the cross hole's axis (seen from above: a line along v at u 0)
        sk = {"id": "S3", "type": "sketch", "plane": top, "points": {"c": [15, 5]}, "entities": [{"id": "k2", "t": "circle", "c": "c", "r": 3}],
              "dims": [{"id": "d1", "t": "dx", "a": {"ref": [0, 0], "axis": axis}, "b": "c", "v": 15},
                       {"id": "d2", "t": "dy", "a": "O", "b": "c", "v": 5}, {"id": "d3", "t": "dia", "e": "k2", "v": 6}]}
        cut = {"id": "E3", "type": "extrude", "sketch": "S3", "op": "cut", "through": True}
        bore = lambda r: next(f for f in r["body"]["faces"] if f.get("name") == "E3:side:k2")["centroid"]  # noqa: E731
        r, v = vol(*box(60, 40, 20), *cross(), sk, cut)
        self.assertTrue(r["ok"], r["features"])
        self.assertEqual(bore(r)[:2], [45, 25])
        self.assertNotIn("update", r["features"][4])  # already 15 from it
        self.assertAlmostEqual(v, 60 * 40 * 20 - math.pi * 16 * 40 - math.pi * 9 * 20, delta=1e-3)
        self.assertTrue(watertight(r["body"]))
        # the cross hole moves 10 to the right: the circle follows its axis
        r, v = vol(*box(60, 40, 20), *cross(40), sk, cut)
        self.assertEqual(r["features"][4]["warnings"], [])
        self.assertEqual(r["features"][4]["update"]["dims"][0]["a"]["ref"], [10, 0])
        if available("planegcs"):
            self.assertEqual(r["features"][4]["update"]["points"]["c"], [25, 5])
            self.assertEqual(bore(r)[:2], [55, 25])
            self.assertAlmostEqual(v, 60 * 40 * 20 - math.pi * 16 * 40 - math.pi * 9 * 20, delta=1e-3)
        # STEP written and read back: the same solid
        from auto3d.modeler import kernel as K
        step = doc.export({"features": [*box(60, 40, 20), *cross(40), sk, cut]}, "step")
        self.assertAlmostEqual(K.volume(K.from_step(step)), v, delta=1e-3)
        # a hole 15 from the axis (the AI's form: just the face's name), and one 10 left of the vertical bore's axis
        # (square to the top: a point there)
        h1 = {"id": "H1", "type": "hole", "plane": top, "points": [[0, -10]], "d": 4, "through": True, "from": [{"x": {"axis": "E2:side:k", "d": 15}}]}
        h2 = {"id": "H2", "type": "hole", "plane": top, "points": [[0, 5]], "d": 2, "through": True,
              "from": [{"x": {"axis": {"face": "E3:side:k2", "fp": [45, 25, 10]}, "d": -10}}]}
        r, v = vol(*box(60, 40, 20), *cross(), sk, cut, h1, h2)
        self.assertTrue(r["ok"], r["features"])
        self.assertEqual(r["features"][-2]["update"], {"points": [[15, -10]]})
        self.assertEqual(r["features"][-1]["update"], {"points": [[5, 5]]})
        self.assertAlmostEqual(v, 60 * 40 * 20 - math.pi * (16 * 40 + 9 * 20 + 4 * 20 + 1 * 20), delta=1e-3)
        r, _ = vol(*box(60, 40, 20), *cross(40), {**h1, "points": [[15, -10]]})
        self.assertEqual(r["features"][-1]["update"], {"points": [[25, -10]]})
        # the axis runs along y: it gives no y; the round face is gone: the hole and the sketch stay and say so
        r, _ = vol(*box(60, 40, 20), *cross(), {**h1, "from": [{"y": {"axis": "E2:side:k", "d": 3}}]})
        self.assertIn("does not run straight across", r["features"][-1]["warnings"][0])
        r, _ = vol(*box(60, 40, 20), *cross(), {**h1, "from": [{"x": {"axis": "E9:side:k", "d": 3}}]})
        self.assertTrue(r["ok"])
        self.assertIn("round face is gone", r["features"][-1]["warnings"][0])
        self.assertEqual(r["features"][-1].get("update"), None)
        r, _ = vol(*box(60, 40, 20), sk)
        self.assertTrue(r["ok"])
        self.assertIn("round face of the part is gone", r["features"][-1]["warnings"][0])
        # a flat face picked as an axis: no axis
        r, _ = vol(*box(60, 40, 20), {**h1, "from": [{"x": {"axis": "E1:side:l2", "d": 3}}]})
        self.assertIn("round face is gone", r["features"][-1]["warnings"][0])

    def test_reference_point(self):
        corner = {"vertex": {"faces": ["E1:end", "E1:side:l1", "E1:side:l2"], "fp": [40, 0, 10]}}
        pt = {"id": "P1", "type": "point", "at": corner}
        r, v = vol(*box(), pt)
        self.assertTrue(r["ok"], r["features"])
        self.assertEqual(r["features"][-1]["point"], [40, 0, 10])
        self.assertEqual(r["points"], {"P1": [40, 0, 10]})
        self.assertNotIn("update", r["features"][-1])
        self.assertAlmostEqual(v, 8000, delta=1e-6)  # a reference only: no geometry
        # the extrude gets taller: the point follows its corner (and hands its new place back)
        r, v = vol(*box(d=25), pt)
        self.assertEqual(r["features"][-1]["point"], [40, 0, 25])
        self.assertEqual(r["features"][-1]["update"], {"at": {"vertex": {**corner["vertex"], "fp": [40, 0, 25]}}})
        self.assertAlmostEqual(v, 20000, delta=1e-6)
        # a round edge's centre and an edge's middle
        top = {"face": {"name": "E1:end"}, "frame": {"o": [20, 10, 10], "x": [1, 0, 0], "n": [0, 0, 1]}}
        h1 = {"id": "H1", "type": "hole", "plane": top, "points": [[-10, 0]], "d": 4, "through": True}
        c = {"id": "P2", "type": "point", "at": {"centre": {"a": "H1:hole:0", "b": "E1:end", "fp": [8, 10, 10]}}}
        m = {"id": "P3", "type": "point", "at": {"mid": {"a": "E1:end", "b": "E1:side:l2", "fp": [40, 10, 10]}}}
        r, _ = vol(*box(h=30), h1, c, m)
        self.assertTrue(r["ok"], r["features"])
        self.assertEqual(r["points"]["P2"], [10, 10, 10])  # the hole rim's centre
        self.assertEqual(r["points"]["P3"], [40, 15, 10])
        # a sketch dimension to the point: follows it (seen square onto the sketch's plane)
        sk = {"id": "S2", "type": "sketch", "plane": {"datum": "XY", "offset": 10}, "points": {"c": [30, 5]},
              "entities": [{"id": "k", "t": "circle", "c": "c", "r": 2}],
              "dims": [{"id": "d1", "t": "dx", "a": {"ref": [40, 0], "point": "P1"}, "b": "c", "v": -10}, {"id": "d2", "t": "dia", "e": "k", "v": 4}]}
        r, _ = vol(*box(), pt, sk)
        self.assertNotIn("update", r["features"][-1])  # already 10 from it
        r, _ = vol(*box(w=60), pt, sk)  # wider: the corner goes to x 60, the circle with it
        self.assertEqual(r["points"]["P1"], [60, 0, 10])
        if available("planegcs"):
            self.assertEqual(r["features"][-1]["update"]["points"]["c"], [50, 5])
        # a fixed place, and the STEP round trip leaves the solid as it is
        r, v = vol(*box(), {"id": "P4", "type": "point", "at": {"xyz": [1, 2, 3]}})
        self.assertEqual(r["points"]["P4"], [1, 2, 3])
        from auto3d.modeler import kernel as K
        step = doc.export({"features": [*box(), pt]}, "step")
        self.assertAlmostEqual(K.volume(K.from_step(step)), 8000, delta=1e-3)
        # its corner is gone (the pocket it sat in is turned off): an issue, the last place kept
        sk3 = {"id": "S3", "type": "sketch", "plane": top, "points": {"p1": [-5, -5], "p2": [5, -5], "p3": [5, 5], "p4": [-5, 5]},
               "entities": [{"id": f"m{i + 1}", "t": "line", "a": f"p{i + 1}", "b": f"p{(i + 1) % 4 + 1}"} for i in range(4)]}
        pocket = {"id": "E3", "type": "extrude", "sketch": "S3", "op": "cut", "d": 4}
        pp = {"id": "P5", "type": "point", "at": {"vertex": {"faces": ["E3:end", "E3:side:m1", "E3:side:m2"], "fp": [25, 5, 6]}}}
        r, _ = vol(*box(), sk3, pocket, pp)
        self.assertTrue(r["ok"], r["features"])
        self.assertEqual(r["points"]["P5"], [25, 5, 6])
        r, _ = vol(*box(), sk3, {**pocket, "suppressed": True}, pp)
        s = r["features"][-1]
        self.assertFalse(s["ok"])
        self.assertIn("corner of the part is gone", s["issues"][0])
        self.assertEqual(s["point"], [25, 5, 6])
        self.assertEqual(r["points"]["P5"], [25, 5, 6])
        r, _ = vol({"id": "P6", "type": "point", "at": {}})
        self.assertIn("needs a place", r["features"][0]["issues"][0])

    def test_solid_from_step(self):
        # a ready solid (a quick part's STEP export, base64) as a step: its faces get names, it can be built on
        import base64
        step = doc.export({"features": box()}, "step")
        solid = {"id": "Q1", "type": "solid", "step": base64.b64encode(step).decode()}
        r, v = vol(solid)
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, 8000, delta=1e-3)
        self.assertEqual(len({f["name"] for f in r["body"]["faces"]}), 6)
        self.assertTrue(all(f["name"].startswith("Q1:f") for f in r["body"]["faces"]))
        top = next(f for f in r["body"]["faces"] if f["type"] == "plane" and f["normal"] == [0, 0, 1])
        hole = {"id": "H1", "type": "hole", "plane": {"face": {"name": top["name"]}, "frame": top["frame"]}, "points": [[0, 0]], "d": 4, "through": True}
        r, v = vol(solid, hole)
        self.assertAlmostEqual(v, 8000 - math.pi * 4 * 10, delta=1e-3)
        r, _ = vol({**solid, "step": "not base64!"})
        self.assertFalse(r["ok"])

    def test_offset_sketch_plane(self):
        f = box()
        f[0] = {**f[0], "plane": {"datum": "XY", "offset": 30}}
        r, v = vol(*f)
        self.assertAlmostEqual(v, 8000, delta=1e-6)
        self.assertEqual(r["body"]["bbox"][2], 30)
        self.assertEqual(r["frames"]["S1"]["o"], [0, 0, 30])
        f[0] = {**f[0], "plane": {"datum": "XZ", "offset": 5}}  # the front plane, 5 mm towards the viewer (−y)
        r, _ = vol(*f)
        self.assertEqual(r["frames"]["S1"]["o"], [0, -5, 0])

    def test_loft(self):
        def square(fid, a, plane):
            h = a / 2
            pts = {"p1": [-h, -h], "p2": [h, -h], "p3": [h, h], "p4": [-h, h]}
            return {"id": fid, "type": "sketch", "plane": plane, "points": pts,
                    "entities": [{"id": f"l{i + 1}", "t": "line", "a": f"p{i + 1}", "b": f"p{(i + 1) % 4 + 1}"} for i in range(4)]}
        s1, s2 = square("S1", 20, {"datum": "XY"}), square("S2", 10, {"datum": "XY", "offset": 30})
        loft = {"id": "L1", "type": "loft", "sketches": ["S1", "S2"], "op": "add"}
        r, v = vol(s1, s2, loft)
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, 30 / 3 * (400 + 100 + 200), delta=1e-3)  # a frustum
        names = {f["name"] for f in r["body"]["faces"]}
        self.assertTrue({"L1:start", "L1:end", "L1:side:l1"} <= names, names)
        # a circle up to a square works too; one sketch is not enough; a sketch with a hole is refused
        circ = {"id": "S2", "type": "sketch", "plane": {"datum": "XY", "offset": 20}, "points": {"c": [0, 0]}, "entities": [{"id": "k", "t": "circle", "c": "c", "r": 6}]}
        r, v = vol(s1, circ, loft)
        self.assertTrue(r["ok"], r["features"])
        self.assertGreater(v, 20 * math.pi * 36)
        r, _ = vol(s1, {**loft, "sketches": ["S1"]})
        self.assertIn("at least two", r["features"][-1]["issues"][0])
        holed = {**s1, "points": {**s1["points"], "c": [0, 0]}, "entities": s1["entities"] + [{"id": "k", "t": "circle", "c": "c", "r": 3}]}
        r, _ = vol(holed, s2, loft)
        self.assertIn("exactly one closed outline", r["features"][-1]["issues"][0])

    def test_sweep(self):
        prof = {"id": "S1", "type": "sketch", "plane": {"datum": "XZ"}, "points": {"c": [0, 0]}, "entities": [{"id": "k", "t": "circle", "c": "c", "r": 2}]}
        # a path on the bed: up y 30, a quarter turn R10 to the right, then 30 along x
        path = {"id": "S2", "type": "sketch", "plane": {"datum": "XY"},
                "points": {"p1": [0, 30], "c": [10, 30], "p2": [10, 40], "p3": [40, 40]},
                "entities": [{"id": "l1", "t": "line", "a": "O", "b": "p1"}, {"id": "a1", "t": "arc", "c": "c", "a": "p2", "b": "p1"},
                             {"id": "l2", "t": "line", "a": "p2", "b": "p3"}]}
        sweep = {"id": "W1", "type": "sweep", "profile": "S1", "path": "S2", "op": "add"}
        r, v = vol(prof, path, sweep)
        self.assertTrue(r["ok"], r["features"])
        self.assertEqual(r["features"][1]["issues"], [])  # an open path sketch is fine by itself
        self.assertAlmostEqual(v, math.pi * 4 * (30 + math.pi * 10 / 2 + 30), delta=1e-2)
        self.assertIn("W1:side:k", {f["name"] for f in r["body"]["faces"]})
        # a sharp corner (no arc): mitred, the whole length
        sharp = {**path, "points": {"p1": [0, 30], "p3": [30, 30]}, "entities": [{"id": "l1", "t": "line", "a": "O", "b": "p1"}, {"id": "l2", "t": "line", "a": "p1", "b": "p3"}]}
        r, v = vol(prof, sharp, sweep)
        self.assertAlmostEqual(v, math.pi * 4 * 60, delta=1e-3)
        # a tube: a profile with a hole
        tube = {**prof, "points": {"c": [0, 0]}, "entities": [{"id": "k", "t": "circle", "c": "c", "r": 2}, {"id": "k2", "t": "circle", "c": "c", "r": 1}]}
        r, v = vol(tube, sharp, sweep)
        self.assertAlmostEqual(v, math.pi * 3 * 60, delta=1e-2)
        # an extrude of the open path says why it cannot
        r, _ = vol(prof, path, {"id": "E1", "type": "extrude", "sketch": "S2", "op": "add", "d": 5})
        self.assertIn("no closed shape", r["features"][-1]["issues"][0])
        # a branching path
        branch = {**path, "points": {**path["points"], "p4": [5, 5]}, "entities": path["entities"] + [{"id": "l3", "t": "line", "a": "p1", "b": "p4"}]}
        r, _ = vol(prof, branch, sweep)
        self.assertIn("branches", r["features"][-1]["issues"][0])

    def test_decal(self):
        # a picture outline (a unit square centred on 0) 20 x 10 mm on the box's top: raised 1 mm, then engraved
        top = {"face": {"name": "E1:end"}, "frame": {"o": [20, 10, 10], "x": [1, 0, 0], "n": [0, 0, 1]}}
        sq = [[[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5]]]
        dec = {"id": "D1", "type": "decal", "plane": top, "polys": [sq], "aspect": 2, "h": 10, "depth": 1, "op": "add", "at": [0, 0]}
        r, v = vol(*box(), dec)
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, 8000 + 200, delta=1e-3)
        self.assertEqual(r["body"]["bbox"][5], 11)
        r, v = vol(*box(), {**dec, "op": "cut"})
        self.assertAlmostEqual(v, 8000 - 200, delta=1e-3)
        # a letter with a hole (an "O"): the hole stays open
        ring = [sq[0], [[-0.25, -0.25], [-0.25, 0.25], [0.25, 0.25], [0.25, -0.25]]]
        r, v = vol(*box(), {**dec, "polys": [ring]})
        self.assertAlmostEqual(v, 8000 + 200 - 50, delta=1e-3)
        # the box gets taller: the decoration stays on its top
        r, _ = vol(*box(d=15), dec)
        self.assertEqual(r["body"]["bbox"][5], 16)
        r, _ = vol(*box(), {**dec, "polys": []})
        self.assertIn("text", r["features"][-1]["issues"][0])

    def test_drawing_pdf(self):
        import fitz
        top = {"face": {"name": "E1:end"}, "frame": {"o": [20, 10, 10], "x": [1, 0, 0], "n": [0, 0, 1]}}
        part = {"features": box() + [{"id": "H1", "type": "hole", "plane": top, "points": [[-10, -5], [10, 5]], "d": 4, "through": True}], "material": "PETG"}
        data = doc.export(part, "pdf", "Bracket")
        self.assertTrue(data.startswith(b"%PDF"))
        page = fitz.open(stream=data, filetype="pdf")[0]
        text = page.get_text()
        for want in ("Front", "Top", "Right", "Bracket", "40", "20", "10", "Ø4 ×2", "PETG", "(10, 5)", "(30, 15)", "Scale 2:1"):
            self.assertIn(want, text)
        self.assertGreater(len(page.get_drawings()), 20)  # the views' lines, dimensions, the title block

    def test_drawing_fits_and_tolerances(self):
        """A hole with a fit: "Ø8 H7" at the hole and with its deviations in the title block; ISO 2768-m below."""
        import fitz
        top = {"face": {"name": "E1:end"}, "frame": {"o": [20, 10, 10], "x": [1, 0, 0], "n": [0, 0, 1]}}
        part = {"features": box() + [{"id": "H1", "type": "hole", "plane": top, "points": [[-10, -5], [10, 5]], "d": 8, "through": True, "fit": "H7"},
                                     {"id": "H2", "type": "hole", "plane": top, "points": [[0, 0]], "d": 3.4, "through": True}],
                "material": "aluminium", "tolerance": "m"}
        text = fitz.open(stream=doc.export(part, "pdf", "Plate"), filetype="pdf")[0].get_text()
        for want in ("Ø8 H7", "Fits: Ø8 H7 (+0.015 / 0)", "General tolerances ISO 2768-m (medium)", "aluminium", "Ø3.4"):
            self.assertIn(want, text)
        self.assertNotIn("Ø3.4 H", text)  # a hole without a fit stays plain
        plain = fitz.open(stream=doc.export({**part, "tolerance": None, "features": box()}, "pdf", "P"), filetype="pdf")[0].get_text()
        self.assertNotIn("ISO 2768", plain)
        self.assertNotIn("Fits:", plain)


    def test_limits(self):
        top = {"face": {"name": "E1:end"}, "frame": {"o": [20, 10, 10], "x": [1, 0, 0], "n": [0, 0, 1]}}
        fil = {"id": "F1", "type": "fillet", "edges": [{"a": "E1:end", "b": "E1:side:l1", "fp": [20, 0, 10]}], "r": 2}
        self.assertEqual(doc.limits(box() + [fil], "F1"), {"r": [0.01, 9.99]})  # a 10 mm high edge
        sh = {"id": "F1", "type": "shell", "faces": [{"name": "E1:end", "fp": [20, 10, 10]}], "t": 2}
        self.assertEqual(doc.limits(box() + [sh], "F1"), {"t": [0.01, 4.99]})
        hole = {"id": "F1", "type": "hole", "plane": top, "points": [[0, 0]], "d": 5, "through": False, "depth": 4}
        self.assertEqual(doc.limits(box() + [hole], "F1"), {"d": [0.01, 20], "depth": [0.01, 10]})  # through the 10 mm part
        h = {"id": "H1", "type": "hole", "plane": top, "points": [[-15, 0]], "d": 4, "through": True}
        pat = {"id": "F1", "type": "pattern", "features": ["H1"], "kind": "linear", "dir": [1, 0, 0], "count": 3, "spacing": 10}
        self.assertEqual(doc.limits(box() + [h, pat], "F1"), {"count": [2, 4], "spacing": [0.01, 18.5]})
        # no wall works at all (a rounding next to the open face): said so, not "thinner"
        r, _ = vol(*box(), {**fil, "id": "R1"}, {**sh, "id": "S9"})
        self.assertIn("cannot be hollowed out", r["features"][-1]["issues"][0])
        r, _ = vol(*box(), {**sh, "t": 7})
        self.assertIn("at most 4.99 mm", r["features"][-1]["issues"][0])


@unittest.skipUnless(OCC, "OCP not installed")
class TestSheet(unittest.TestCase):
    """A drawing sheet: exact circles with their face names, the holes alike dimensioned once, the presets."""

    def setUp(self):
        top = {"face": {"name": "E1:end"}, "frame": {"o": [20, 10, 10], "x": [1, 0, 0], "n": [0, 0, 1]}}
        self.part = {"features": box() + [
            {"id": "H1", "type": "hole", "plane": top, "points": [[x, y] for x in (-15, -5, 5, 15) for y in (-5, 5)], "d": 3, "through": True, "fit": "H7"},
            {"id": "R1", "type": "fillet", "edges": [{"a": "E1:end", "b": "E1:side:l1", "fp": [20, 0, 10]}], "r": 2}]}

    def test_views_and_points(self):
        from auto3d.modeler import sheet
        r = doc.sheet(self.part, "medium")
        top = r["geometry"]["views"]["Top"]
        self.assertEqual(top["box"], [0, 0, 40, 20])
        holes = [c for c in top["circles"] if c["full"]]
        self.assertEqual(len(holes), 8)                       # a hole's two circles: one
        self.assertTrue(all(c["key"].startswith("H1:hole:") and c["r"] == 1.5 for c in holes))
        self.assertIn("H1:hole:0#c", top["points"])
        self.assertEqual(r["layout"]["paper"], "A4")
        self.assertEqual(sheet.value(r["geometry"], {"view": "Front", "kind": "linear", "a": "box#x0", "b": "box#x1", "dir": "h"}), 40)

    def test_holes_alike_once(self):
        from auto3d.modeler import sheet
        r = doc.sheet(self.part, "medium")
        g, dims = r["geometry"], r["dims"]
        dia = [d for d in dims if d["kind"] == "dia"]
        self.assertEqual([(d["count"], d.get("post")) for d in dia], [(8, " H7")])  # "8× Ø3 H7", once
        vals = sorted((d.get("pre", ""), sheet.value(g, d)) for d in dims if d["kind"] == "linear" and d["view"] == "Top")
        self.assertIn(("3× ", 10), vals)                     # the row's pitch, 4 holes
        self.assertIn(("", 5), vals)                         # the first hole from the left / bottom
        self.assertEqual(sum(1 for d in dims if "H1:hole" in d.get("b", "")), 4)  # not 8 × 2 positions
        self.assertTrue(any(d["kind"] == "rad" and sheet.value(g, d) == 2 for d in dims))
        self.assertFalse(any(":round:" in d.get("b", "") for d in dims if d["kind"] == "linear"))  # no "level" where a rounding begins
        ids = [d["id"] for d in dims]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids, [d["id"] for d in doc.sheet(self.part, "medium")["dims"]])  # the same ids again (the user's moves stay)

    def test_no_distance_twice(self):
        """Concentric circles (a boss with a hole) and holes on one line: each distance is dimensioned once."""
        from auto3d.modeler import sheet
        top = {"face": {"name": "E1:end"}, "frame": {"o": [20, 10, 10], "x": [1, 0, 0], "n": [0, 0, 1]}}
        part = {"features": box() + [{"id": "H1", "type": "hole", "plane": top, "points": [[-10, 0]], "d": 6, "through": False, "depth": 3},
                                     {"id": "H2", "type": "hole", "plane": top, "points": [[-10, 0]], "d": 3, "through": True},
                                     {"id": "H3", "type": "hole", "plane": top, "points": [[10, 0]], "d": 4, "through": True}]}
        r = doc.sheet(part, "medium")
        g, lin = r["geometry"], [d for d in r["dims"] if d["kind"] == "linear"]
        sigs = [(d["view"], d["dir"], round(sheet.value(g, d), 2), d["a"]) for d in lin]
        top_h = sorted(sheet.value(g, d) for d in lin if d["view"] == "Top" and d["dir"] == "h")
        top_v = sorted(sheet.value(g, d) for d in lin if d["view"] == "Top" and d["dir"] == "v")
        self.assertEqual(top_h, [10, 30])          # the two places from the left — not 10 twice for the Ø6 / Ø3 pair
        self.assertEqual(top_v, [10, 20])          # their height once (both holes on one line) + the depth
        self.assertEqual(len(sigs), len(set(sigs)))
        self.assertEqual(sorted(d["kind"] for d in r["dims"] if d["kind"] == "dia"), ["dia"] * 3)

    def test_a_view_with_all_its_sizes(self):
        """"all": the Right view gets its own outer sizes (given in the Front and Top already) — by default none."""
        from auto3d.modeler import sheet
        r = doc.sheet(self.part, "medium")
        self.assertFalse([d for d in r["dims"] if d["view"] == "Right" and d["kind"] == "linear"])
        r = doc.sheet(self.part, "medium", per_view={"Right": "all"})
        right = sorted(sheet.value(r["geometry"], d) for d in r["dims"] if d["view"] == "Right" and d["kind"] == "linear")
        self.assertIn(20, right)  # its width: the part's depth
        self.assertIn(10, right)  # its height
        self.assertEqual(len([d for d in r["dims"] if d["view"] == "Front"]), len([d for d in doc.sheet(self.part, "medium")["dims"] if d["view"] == "Front"]))

    def test_view_presets(self):
        """A view's own preset: the top medium while the sheet is light (the rest of the sheet stays light)."""
        light = doc.sheet(self.part, "light")["dims"]
        mixed = doc.sheet(self.part, "light", per_view={"Top": "medium"})["dims"]
        self.assertGreater(sum(1 for d in mixed if d["view"] == "Top"), sum(1 for d in light if d["view"] == "Top"))
        self.assertEqual([d["id"] for d in mixed if d["view"] == "Front"], [d["id"] for d in light if d["view"] == "Front"])

    def test_presets(self):
        n = {p: len(doc.sheet(self.part, p)["dims"]) for p in ("light", "medium", "full")}
        self.assertLess(n["light"], n["medium"])
        self.assertLessEqual(n["medium"], n["full"])
        light = doc.sheet(self.part, "light")["dims"]
        self.assertEqual({d["kind"] for d in light}, {"linear", "dia", "rad"})
        self.assertEqual(sum(1 for d in light if d["kind"] == "linear"), 3)  # the overall sizes only

    def test_pdf_from_svg(self):
        import fitz
        from auto3d.modeler import sheet
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="297mm" height="210mm" viewBox="0 0 297 210"><line x1="10" y1="10" x2="100" y2="50" '
               'stroke="black" stroke-width="0.35"/><text x="60" y="60" font-size="3.5">8× Ø3 H7 — Rev 2</text></svg>')
        page = fitz.open("pdf", sheet.pdf(svg))[0]
        self.assertAlmostEqual(page.rect.width, 297 * 72 / 25.4, places=0)
        self.assertIn("8× Ø3 H7", page.get_text())


@unittest.skipUnless(OCC, "OCP not installed")
class TestAssemblySheet(unittest.TestCase):
    """An assembly's sheet: the views of the placed parts together, their overall sizes, a mark for each part."""

    def test_section_view(self):
        """Section A–A of a 40 × 20 × 10 block with a Ø6 hole through it at x 20 (the middle): the cut face is the block's
        20 × 10 cross-section split by the hole (two rectangles 7 wide); the section view's box is the Right view's; its
        cut line on the Front view at x 20."""
        top = {"face": {"name": "E1:end"}, "frame": {"o": [20, 10, 10], "x": [1, 0, 0], "n": [0, 0, 1]}}
        part = {"features": box() + [{"id": "H1", "type": "hole", "plane": top, "points": [[0, 0]], "d": 6, "through": True}]}
        r = doc.sheet(part, "medium", section=True)
        sec = r["geometry"]["views"]["Section"]
        self.assertEqual(sec["box"], r["geometry"]["views"]["Right"]["box"])
        area = lambda pl: abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pl, pl[1:] + pl[:1]))) / 2  # noqa: E731
        self.assertEqual(len(sec["hatch"]), 2)
        self.assertAlmostEqual(sum(area(pl) for pl in sec["hatch"]), (20 - 6) * 10, delta=0.01)
        self.assertEqual([p[0] for p in sec["cut"]], [20, 20])
        self.assertNotIn("Section", doc.sheet(part, "medium")["geometry"]["views"])

    def test_assembly_sheet(self):
        part = {"features": box(20, 20, 10)}
        at = lambda x, y=0, z=0: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, z, 1]  # noqa: E731
        r = doc.assembly_sheet([{"id": "I1", "part": part, "matrix": at(0)}, {"id": "I2", "part": part, "matrix": at(0, 0, 10)}])
        self.assertEqual(r["geometry"]["views"]["Front"]["box"], [0, 0, 20, 20])  # two blocks stacked
        self.assertEqual(sorted(r["marks"]), ["I1", "I2"])
        self.assertEqual(r["marks"]["I2"]["Front"], [10, 15])
        self.assertEqual(len(r["dims"]), 3)  # its overall sizes
        self.assertIn("Iso", r["marks"]["I1"])

    def test_assembly_sheet_exploded(self):
        """explode 1: the iso view drawn with the two stacked blocks pulled apart (its outline taller, the marks apart
        in it), the front view as assembled."""
        part = {"features": box(20, 20, 10)}
        at = lambda x, y=0, z=0: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, z, 1]  # noqa: E731
        inst = [{"id": "I1", "part": part, "matrix": at(0)}, {"id": "I2", "part": part, "matrix": at(0, 0, 10)}]
        r0, r1 = doc.assembly_sheet(inst), doc.assembly_sheet(inst, explode=1)
        self.assertEqual(r1["geometry"]["views"]["Front"]["box"], r0["geometry"]["views"]["Front"]["box"])
        tall = lambda r: (lambda ys: max(ys) - min(ys))([p[1] for pl in r["geometry"]["iso"] for p in pl])  # noqa: E731
        self.assertGreater(tall(r1), tall(r0) + 5)  # (12 more along z: 2 × 1.2 × 5, foreshortened in the iso)
        gap = lambda r: abs(r["marks"]["I2"]["Iso"][1] - r["marks"]["I1"]["Iso"][1])  # noqa: E731
        self.assertGreater(gap(r1), gap(r0) + 5)
        self.assertEqual(r1["marks"]["I2"]["Front"], r0["marks"]["I2"]["Front"])

    def test_drawing_set_pdf(self):
        import fitz
        from auto3d.modeler import sheet
        page = lambda t: f'<svg xmlns="http://www.w3.org/2000/svg" width="297mm" height="210mm" viewBox="0 0 297 210"><text x="20" y="20" font-size="5">{t}</text></svg>'  # noqa: E731
        d = fitz.open("pdf", sheet.pdf([page("ASSEMBLY"), page("Sub"), page("Part A")]))
        self.assertEqual(d.page_count, 3)
        self.assertEqual([p.get_text().strip() for p in d], ["ASSEMBLY", "Sub", "Part A"])


@unittest.skipUnless(OCC, "OCP not installed")
class TestLightMesh(unittest.TestCase):
    """🪶 simplified: a coarser mesh, no edges, a lean face list (no sketch frames); auto only for big parts."""

    def test_light(self):
        top = {"face": {"name": "E1:end"}, "frame": {"o": [20, 10, 10], "x": [1, 0, 0], "n": [0, 0, 1]}}
        part = {"features": box() + [{"id": "H1", "type": "hole", "plane": top, "points": [[0, 0]], "d": 6, "through": True}]}
        full = doc.rebuild({**part, "lod": "full"})["body"]
        light = doc.rebuild({**part, "lod": "light"})["body"]
        auto = doc.rebuild({**part, "lod": "auto"})["body"]
        self.assertTrue(light["light"])
        self.assertNotIn("light", auto)                       # a small part stays full by itself
        self.assertEqual(light["edges"], [])
        self.assertTrue(full["edges"])
        self.assertLessEqual(len(light["face_ids"]), len(full["face_ids"]))
        self.assertEqual(len(light["faces"]), len(full["faces"]))  # every face still there (joints find them)
        plane = next(f for f in light["faces"] if f["type"] == "plane")
        self.assertNotIn("frame", plane)
        self.assertIn("normal", plane)
        hole = next(f for f in light["faces"] if f["type"] == "cylinder")
        self.assertEqual(hole["radius"], 3)
        self.assertEqual(hole["name"], "H1:hole:0")
        self.assertIn("frame", next(f for f in doc.rebuild({**part, "lod": "full"})["body"]["faces"] if f["type"] == "plane"))  # (the full one kept apart)


class TestFits(unittest.TestCase):
    """ISO 286 deviations by size range, and the labels on the drawing."""

    def test_deviations(self):
        from auto3d.modeler import fits
        self.assertEqual(fits.deviation("H7", 8), (0.015, 0))
        self.assertEqual(fits.deviation("H7", 10), (0.015, 0))   # 10 is still "over 6 to 10"
        self.assertEqual(fits.deviation("H7", 10.01), (0.018, 0))
        self.assertEqual(fits.deviation("g6", 22), (-0.007, -0.02))
        self.assertEqual(fits.deviation("k6", 8), (0.01, 0.001))
        self.assertEqual(fits.deviation("p6", 100), (0.059, 0.037))
        self.assertIsNone(fits.deviation("H7", 200))
        self.assertIsNone(fits.deviation("X9", 8))
        self.assertEqual(fits.label(22, "H7"), "Ø22 H7 (+0.021 / 0)")
        self.assertEqual(fits.label(8, "g6"), "Ø8 g6 (-0.005 / -0.014)")
        self.assertEqual(fits.label(300, "H7"), "Ø300 H7")


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(OCC, "OCP not installed")
class TestAssemblyClashes(unittest.TestCase):
    """Parts of an assembly that overlap: the common volume, only for parts whose boxes meet."""

    def test_overlap_touch_and_apart(self):
        part = {"features": box(20, 20, 10)}
        at = lambda x, y=0, z=0: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, z, 1]  # noqa: E731
        cs = doc.assembly_clashes([{"id": "I1", "part": part, "matrix": at(0)}, {"id": "I2", "part": part, "matrix": at(15, 5)},  # 5 × 15 × 10 overlap
                                   {"id": "I3", "part": part, "matrix": at(0, 0, 10)},   # on top of I1: touching only
                                   {"id": "I4", "part": part, "matrix": at(100)}])       # far away
        self.assertEqual([(c["a"], c["b"]) for c in cs], [("I1", "I2")])
        self.assertAlmostEqual(cs[0]["volume"], 5 * 15 * 10, places=3)
        self.assertEqual(cs[0]["bbox"], [15, 5, 0, 20, 20, 10])

    def test_quick_check_estimates_big_overlaps(self):
        """A part of many solids (a board with its components) over another one: quick: estimated from the boxes, at once;
        else computed (solid by solid)."""
        from auto3d.modeler import kernel as K
        part = {"features": box(20, 20, 10)}
        at = lambda x, y=0, z=0: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, z, 1]  # noqa: E731
        st = doc.body_of(part)
        many = K.compound([K.placed(st.body.shape, at(25 * i)) for i in range(7)])  # 7 blocks in a row: one "board"
        a, b = ("A", many), ("B", K.placed(many, at(5)))
        exact = K.interference([a, b])
        old = K.QUICK_PAIRS
        try:
            K.QUICK_PAIRS = 3
            quick = K.interference([a, b], quick=True)
        finally:
            K.QUICK_PAIRS = old
        self.assertEqual(len(exact), 1)
        self.assertAlmostEqual(exact[0]["volume"], 7 * 15 * 20 * 10, places=1)  # each block 15 × 20 × 10 into the next copy
        self.assertTrue(quick[0]["approx"])
        self.assertGreaterEqual(quick[0]["volume"], exact[0]["volume"] - 1e-6)  # an upper bound
        self.assertNotIn("approx", K.interference([a, b], quick=True)[0])  # (few enough: computed)

    def test_sweep(self):
        """A block slid along X past a still one: it hits it only on the way; a clash of two still parts is not told."""
        part = {"features": box(20, 20, 10)}
        at = lambda x, y=0, z=0: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, z, 1]  # noqa: E731
        inst = [{"id": "I1", "part": part, "matrix": at(0)}, {"id": "I2", "part": part, "matrix": at(-40)},
                {"id": "I3", "part": part, "matrix": at(0, 100)}, {"id": "I4", "part": part, "matrix": at(5, 100)}]  # I3 / I4: still, overlapping
        steps = [{"at": x, "matrices": {"I2": at(-40 + x)}} for x in (0, 10, 30, 50, 80)]
        r = doc.assembly_sweep(inst, steps)
        self.assertEqual([s["at"] for s in r], [0, 10, 30, 50, 80])
        hits = {s["at"]: [(c["a"], c["b"], c["volume"]) for c in s["clashes"]] for s in r}
        self.assertEqual(hits[0], [])
        self.assertEqual(hits[10], [])  # touching
        self.assertEqual(hits[30], [("I1", "I2", 10 * 20 * 10)])
        self.assertEqual(hits[50], [("I1", "I2", 10 * 20 * 10)])
        self.assertEqual(hits[80], [])


@unittest.skipUnless(OCC, "OCP not installed")
class TestRevolvedFaces(unittest.TestCase):
    """A revolved solid's flat faces point out of it, whichever way its profile runs (a ring's bottom down, its top up)."""

    def test_normals_point_out(self):
        for prof in ([(4, 0), (11, 0), (11, 7), (4, 7)], [(4, 0), (4, 7), (11, 7), (11, 0)]):
            pts = {f"p{i + 1}": list(p) for i, p in enumerate(prof)}
            lines = [{"id": f"l{i + 1}", "t": "line", "a": f"p{i + 1}", "b": f"p{(i + 1) % 4 + 1}"} for i in range(4)]
            r = doc.rebuild({"features": [{"id": "F1", "type": "sketch", "plane": {"datum": "XZ"}, "points": pts, "entities": lines},
                                          {"id": "F2", "type": "revolve", "sketch": "F1", "axis": "y", "angle": 360, "op": "add"}]})
            flat = sorted((f["centroid"][2], f["normal"][2]) for f in r["body"]["faces"] if f["type"] == "plane")
            self.assertEqual([round(z) for z, _ in flat], [0, 7])
            self.assertEqual([round(n) for _, n in flat], [-1, 1], prof)
            self.assertEqual(flat[0][1], next(f["frame"]["n"][2] for f in r["body"]["faces"] if f["type"] == "plane" and f["centroid"][2] < 1))


@unittest.skipUnless(OCC, "OCP not installed")
class TestCutWarning(unittest.TestCase):
    """A cut that takes nothing away (it goes away from the part) says so; one into the part does not."""

    def test_cut_away_from_the_part(self):
        hole = lambda flip: [{"id": "S2", "type": "sketch", "plane": {"datum": "XY"}, "points": {"c": [20, 10]},  # noqa: E731
                              "entities": [{"id": "c1", "t": "circle", "c": "c", "r": 2}]},
                             {"id": "E2", "type": "extrude", "sketch": "S2", "op": "cut", "d": 5, "flip": flip}]
        r, _ = vol(*box(), *hole(False))  # from the bed down: away from the part
        self.assertTrue(any("removes nothing" in w for w in r["features"][-1]["warnings"]))
        r, v = vol(*box(), *hole(True))   # up into it
        self.assertFalse(r["features"][-1]["warnings"])
        self.assertAlmostEqual(v, 40 * 20 * 10 - math.pi * 4 * 5, places=3)


@unittest.skipUnless(OCC, "OCP not installed")
class TestSmoothCurves(unittest.TestCase):
    """A sketch's smooth curve (spline through points) is one B-spline edge: a revolved profile gets one smooth face."""

    def test_revolved_vase(self):
        pts = {"o": [0, 0], "b": [20, 0], "s1": [26, 15], "s2": [18, 35], "s3": [24, 55], "t": [22, 60], "a": [0, 60]}
        ents = [{"id": "l1", "t": "line", "a": "o", "b": "b"}, {"id": "s1", "t": "spline", "pts": ["b", "s1", "s2", "s3", "t"]},
                {"id": "l2", "t": "line", "a": "t", "b": "a"}, {"id": "l3", "t": "line", "a": "a", "b": "o"}]
        r = doc.rebuild({"features": [{"id": "F1", "type": "sketch", "plane": {"datum": "XZ"}, "points": pts, "entities": ents},
                                      {"id": "F2", "type": "revolve", "sketch": "F1", "axis": "y", "angle": 360, "op": "add"}]})
        self.assertTrue(all(f["ok"] for f in r["features"]), r["features"])
        faces = r["body"]["faces"]
        self.assertEqual(sorted(f["name"] for f in faces), ["F2:side:l1", "F2:side:l2", "F2:side:s1"])  # bottom, top, ONE side
        self.assertGreater(r["body"]["volume"], math.pi * 18 ** 2 * 60)
        # it goes through its points: Ø36 at z 35, Ø52 at z 15 (the bounding box reaches a little past the widest point)
        self.assertGreaterEqual(r["body"]["bbox"][3], 26 - 1e-6)

    def test_extruded_smooth_outline(self):
        pts = {"p1": [0, 0], "p2": [40, 0], "m1": [45, 15], "m2": [20, 30], "m3": [-5, 15]}
        ents = [{"id": "l1", "t": "line", "a": "p1", "b": "p2"}, {"id": "s1", "t": "spline", "pts": ["p2", "m1", "m2", "m3", "p1"]}]
        r, v = vol({"id": "S1", "type": "sketch", "plane": {"datum": "XY"}, "points": pts, "entities": ents},
                   {"id": "E1", "type": "extrude", "sketch": "S1", "op": "add", "d": 5})
        self.assertTrue(v and v > 40 * 25 * 5 * 0.7, v)
        self.assertEqual(sorted({f["name"] for f in r["body"]["faces"]}), ["E1:end", "E1:side:l1", "E1:side:s1", "E1:start"])
