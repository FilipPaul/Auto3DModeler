"""Fillet, chamfer and hole on a model part, and named faces: exact volumes, and a rounding that stays on
the same edge when an earlier size changes. Skipped without the CAD kernel.

Run:  python -m unittest discover -s tests -v
"""
import math
import unittest

from auto3d.modeler import available

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

    def test_round_then_hole_and_errors(self):
        fil = {"id": "F1", "type": "fillet", "edges": [{"a": "E1:side:l1", "b": "E1:side:l2", "fp": [40, 0, 5]}], "r": 50}
        r, v = vol(*box(), fil)
        self.assertFalse(r["features"][-1]["ok"])
        self.assertIn("does not fit", r["features"][-1]["issues"][0])
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


if __name__ == "__main__":
    unittest.main()
