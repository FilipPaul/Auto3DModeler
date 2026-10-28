"""Sketch clean-up (auto3d/modeler/sketchclean.py): ends welded, crumbs absorbed, collinear lines and arcs on one
circle joined, a flattened curve fitted by a spline within the tolerance, the closed regions kept (area) — on small
made-up sketches and on the sample drawings Finger.dxf / Drive Gear.dxf; with the CAD kernel also the extruded
volume, a watertight mesh and a STEP write -> read.

Run:  python -m unittest discover -s tests -v
"""
import math
import time
import unittest
from collections import Counter
from pathlib import Path

import numpy as np

from auto3d.modeler import available, sketchclean as sc

OCC = available("occ")
if OCC:
    from auto3d.modeler import doc, kernel as K
    from test_modeler_kernel import watertight

DRAWINGS = Path(__file__).resolve().parent.parent / "samples" / "ToImportToOurApp" / "drawings"


def lines(*pts, closed=False):
    """A sketch of lines through points in order (each its own point ids)."""
    P = {f"p{i + 1}": list(map(float, p)) for i, p in enumerate(pts)}
    n = len(pts)
    ents = [{"id": f"l{i + 1}", "t": "line", "a": f"p{i + 1}", "b": f"p{i + 2}"} for i in range(n - 1)]
    if closed:
        ents.append({"id": f"l{n}", "t": "line", "a": f"p{n}", "b": "p1"})
    return {"points": P, "entities": ents, "constraints": [], "dims": []}


def kinds(sk):
    return Counter(e["t"] for e in sk["entities"])


def naive(drawing):
    """The drawing as the old browser conversion gave it (each polyline side a line; ends joined only when equal to
    5 decimals) — what the owner had: hundreds of shapes."""
    points, ents, key = {}, [], {}

    def pt(p):
        k = f"{p[0]:.5f},{p[1]:.5f}"
        if k not in key:
            key[k] = f"p{len(key) + 1}"
            points[key[k]] = [round(p[0], 6), round(p[1], 6)]
        return key[k]
    for e in drawing["entities"]:
        if e["t"] == "line":
            ents.append({"id": f"l{len(ents) + 1}", "t": "line", "a": pt(e["a"]), "b": pt(e["b"])})
        elif e["t"] == "circle":
            ents.append({"id": f"c{len(ents) + 1}", "t": "circle", "c": pt(e["c"]), "r": e["r"]})
        elif e["t"] == "arc":
            a0 = math.radians(e["a0"])
            a1 = a0 + (math.radians(e["a1"] - e["a0"]) % (2 * math.pi) or 2 * math.pi)
            ents.append({"id": f"a{len(ents) + 1}", "t": "arc", "c": pt(e["c"]), "a": pt([e["c"][0] + e["r"] * math.cos(a0), e["c"][1] + e["r"] * math.sin(a0)]),
                         "b": pt([e["c"][0] + e["r"] * math.cos(a1), e["c"][1] + e["r"] * math.sin(a1)])})
        elif e["t"] == "poly":
            q = e["pts"] + ([e["pts"][0]] if e["closed"] else [])
            for a, b in zip(q, q[1:]):
                if pt(a) != pt(b):
                    ents.append({"id": f"l{len(ents) + 1}", "t": "line", "a": pt(a), "b": pt(b)})
    return {"points": points, "entities": ents, "constraints": [], "dims": []}


def extruded(sk, d=5):
    """The sketch extruded d mm -> the kernel's result."""
    return doc.rebuild({"features": [{"id": "S1", "type": "sketch", "plane": {"datum": "XY"}, **sk},
                                     {"id": "E1", "type": "extrude", "sketch": "S1", "op": "add", "d": d}]})


def step_volume(sk, d=5):
    return K.volume(K.from_step(doc.export({"features": [{"id": "S1", "type": "sketch", "plane": {"datum": "XY"}, **sk},
                                                         {"id": "E1", "type": "extrude", "sketch": "S1", "op": "add", "d": d}]}, "step")))


class TestSimplify(unittest.TestCase):
    def test_ends_near_each_other_are_welded(self):
        sk = lines((0, 0), (10, 0))
        sk["points"]["p3"] = [10.004, 0.003]
        sk["points"]["p4"] = [10, 10]
        sk["entities"].append({"id": "l2", "t": "line", "a": "p3", "b": "p4"})
        new, rep = sc.simplify(sk, tol=0.01)
        self.assertEqual(rep["before"]["points"], 4)
        self.assertEqual(rep["after"]["points"], 3)  # (one shared corner)
        a, b = new["entities"]
        self.assertEqual(len({a["a"], a["b"], b["a"], b["b"]}), 3)

    def test_a_crumb_is_absorbed(self):
        sk = lines((0, 0), (10, 0), (10.006, 0.004), (10, 10))  # (a 0.007 mm piece between two sides)
        new, rep = sc.simplify(sk, tol=0.01)
        self.assertEqual(kinds(new), {"line": 2})
        self.assertEqual(rep["after"]["points"], 3)

    def test_collinear_lines_become_one(self):
        new, rep = sc.simplify(lines((0, 0), (3, 0), (7, 0.001), (10, 0)), tol=0.01)
        self.assertEqual(kinds(new), {"line": 1})
        ln = new["entities"][0]
        self.assertEqual(sorted(map(tuple, (new["points"][ln["a"]], new["points"][ln["b"]]))), [(0, 0), (10, 0)])

    def test_a_rectangle_stays_as_it_was(self):
        sk = lines((0, 0), (40, 0), (40, 20), (0, 20), closed=True)
        sk["constraints"] = [{"id": "k1", "t": "h", "e": "l1"}]
        sk["dims"] = [{"id": "d1", "t": "len", "e": "l2", "v": 20}]
        new, rep = sc.simplify(sk)
        self.assertEqual(sorted(e["id"] for e in new["entities"]), ["l1", "l2", "l3", "l4"])
        self.assertEqual(new["constraints"], sk["constraints"])
        self.assertEqual(new["dims"], sk["dims"])
        self.assertEqual(rep["dropped"], 0)
        self.assertAlmostEqual(rep["area"][1], 800, places=6)

    def test_arcs_on_one_circle_become_one_arc_or_a_circle(self):
        pts = {"c": [0, 0], **{f"q{i}": [10 * math.cos(i * math.pi / 2), 10 * math.sin(i * math.pi / 2)] for i in range(4)}}
        arcs = [{"id": f"a{i}", "t": "arc", "c": "c", "a": f"q{i}", "b": f"q{(i + 1) % 4}"} for i in range(4)]
        new, _ = sc.simplify({"points": pts, "entities": arcs[:2], "constraints": [], "dims": []})
        self.assertEqual(kinds(new), {"arc": 1})
        a = new["entities"][0]
        self.assertEqual((new["points"][a["a"]], new["points"][a["b"]]), ([10, 0], [-10, 0]))  # (half way round)
        new, rep = sc.simplify({"points": pts, "entities": arcs, "constraints": [], "dims": []})
        self.assertEqual(kinds(new), {"circle": 1})
        self.assertAlmostEqual(new["entities"][0]["r"], 10)
        self.assertAlmostEqual(rep["area"][1], math.pi * 100, delta=0.05)

    def test_a_flattened_circle_becomes_a_circle(self):
        sk = lines(*[(5 + 8 * math.cos(2 * math.pi * i / 90), 8 * math.sin(2 * math.pi * i / 90)) for i in range(90)], closed=True)
        new, rep = sc.simplify(sk, tol=0.01)
        self.assertEqual(kinds(new), {"circle": 1})
        self.assertAlmostEqual(new["entities"][0]["r"], 8, delta=0.01)
        self.assertEqual((rep["before"]["entities"], rep["after"]["entities"]), (90, 1))
        self.assertAlmostEqual(rep["area"][1], rep["area"][0], delta=rep["area"][0] * 0.005)

    def test_a_flattened_curve_becomes_few_shapes_within_the_tolerance(self):
        xs = np.linspace(0, 30, 301)
        sk = lines(*zip(xs, 4 * np.sin(xs / 5)), (30, -10), (0, -10), closed=True)
        new, rep = sc.simplify(sk, tol=0.01)
        self.assertLess(rep["after"]["entities"], 20)
        self.assertLess(abs(rep["area"][1] - rep["area"][0]), rep["area"][0] * 0.005)

    def test_locked_shapes_and_their_sizes_stay(self):
        sk = lines((0, 0), (5, 0), (10, 0), (20, 0))
        sk["dims"] = [{"id": "d1", "t": "len", "e": "l2", "v": 5}]
        new, rep = sc.simplify(sk)
        self.assertIn("l2", [e["id"] for e in new["entities"]])
        self.assertEqual(new["dims"], sk["dims"])
        self.assertEqual(rep["dropped"], 0)

    def test_only_the_picked_shapes(self):
        sk = lines((0, 0), (3, 0), (6, 0), (6, 5), (6, 10))
        new, _ = sc.simplify(sk, ["l1", "l2"])
        ids = [e["id"] for e in new["entities"]]
        self.assertEqual(len(ids), 3)
        self.assertIn("l3", ids)  # (the others untouched)
        self.assertIn("l4", ids)

    def test_errors(self):
        with self.assertRaises(ValueError):
            sc.simplify(lines((0, 0), (1, 0)), tol="much")
        with self.assertRaises(ValueError):
            sc.simplify(lines((0, 0), (1, 0)), tol=-1)


class TestJoin(unittest.TestCase):
    def test_a_chain_becomes_one_spline_within_the_tolerance(self):
        xs = np.linspace(0, 30, 121)
        sk = lines(*zip(xs, 4 * np.sin(xs / 5)))
        new, rep = sc.join(sk, [e["id"] for e in sk["entities"]], tol=0.01)
        self.assertEqual(kinds(new), {"spline": 1})
        s = new["entities"][0]
        self.assertTrue(s.get("fit"))
        F = [new["points"][q] for q in s["pts"]]
        self.assertLess(len(F), 20)
        self.assertEqual(F[0], [0.0, 0.0])
        self.assertAlmostEqual(F[-1][0], 30)
        curve, chain = sc.spline_eval(F), np.array(list(zip(xs, 4 * np.sin(xs / 5))))
        self.assertLessEqual(sc._to_poly(curve, chain).max(), 0.01 + 1e-9)
        self.assertLessEqual(sc._to_poly(chain, curve).max(), 0.01 + 1e-9)
        self.assertEqual((rep["before"]["entities"], rep["after"]["entities"]), (120, 1))

    def test_a_corner_splits_it_and_a_straight_run_stays_a_line(self):
        # a curve, then a sharp turn down a straight side
        xs = np.linspace(0, 20, 81)
        sk = lines(*zip(xs, 2 * np.sin(xs / 4)), (20, -20), (20.0, -30))
        new, _ = sc.join(sk, [e["id"] for e in sk["entities"]])
        self.assertEqual(kinds(new), {"spline": 1, "line": 1})
        ln = next(e for e in new["entities"] if e["t"] == "line")
        self.assertEqual(new["points"][ln["b"]], [20.0, -30.0])

    def test_a_closed_loop_with_a_hole_keeps_its_area(self):
        ring = [(25 * math.cos(t) * (1 + 0.1 * math.cos(5 * t)), 25 * math.sin(t) * (1 + 0.1 * math.cos(5 * t))) for t in np.linspace(0, 2 * math.pi, 200, endpoint=False)]
        sk = lines(*ring, closed=True)
        sk["points"]["h"] = [0, 0]
        sk["entities"].append({"id": "c1", "t": "circle", "c": "h", "r": 5})
        new, rep = sc.join(sk, [e["id"] for e in sk["entities"]])
        self.assertEqual(kinds(new), {"spline": 1, "circle": 1})
        s = next(e for e in new["entities"] if e["t"] == "spline")
        self.assertEqual(s["pts"][0], s["pts"][-1])  # (closed)
        self.assertAlmostEqual(rep["area"][1], rep["area"][0], delta=rep["area"][0] * 0.005)

    def test_its_ends_stay_joined_to_the_rest(self):
        sk = lines((0, 0), (5, 0.5), (10, 1.5), (15, 3))
        sk["points"]["z"] = [15, 20]
        sk["entities"].append({"id": "lz", "t": "line", "a": "p4", "b": "z"})
        new, _ = sc.join(sk, ["l1", "l2", "l3"])
        s = next(e for e in new["entities"] if e["t"] == "spline")
        self.assertEqual((s["pts"][0], s["pts"][-1]), ("p1", "p4"))
        self.assertIn({"id": "lz", "t": "line", "a": "p4", "b": "z"}, new["entities"])

    def test_a_tangent_arc_joins_its_line(self):
        """The arc tool's tangent relation (on the picked line and arc) does not keep their point apart."""
        sk = {"points": {"p1": [0, 0], "p2": [10, 0], "c": [10, 5], "p3": [15, 5]},
              "entities": [{"id": "l1", "t": "line", "a": "p1", "b": "p2"}, {"id": "a1", "t": "arc", "c": "c", "a": "p2", "b": "p3"}],
              "constraints": [{"id": "k1", "t": "tan", "e": "l1", "arc": "a1", "p": "p2"}], "dims": []}
        new, rep = sc.join(sk, ["l1", "a1"])
        self.assertEqual(kinds(new), {"spline": 1})
        self.assertEqual((new["constraints"], rep["dropped"]), ([], 1))

    def test_nothing_picked(self):
        with self.assertRaises(ValueError):
            sc.join(lines((0, 0), (1, 0)), [])


class TestOutline(unittest.TestCase):
    def test_a_plate_with_a_hole_becomes_one_block(self):
        sk = lines((10, 5), (50, 5), (50, 25), (10, 25), closed=True)
        sk["points"]["c"] = [30, 15]
        sk["entities"].append({"id": "c1", "t": "circle", "c": "c", "r": 4})
        sk["dims"] = [{"id": "d1", "t": "len", "e": "l1", "v": 40}]
        new, rep = sc.outline(sk, [e["id"] for e in sk["entities"]])
        self.assertEqual(kinds(new), {"block": 1})
        b = new["entities"][0]
        self.assertEqual((b["at"], b["w0"], b["h0"], b["scale"]), ([10, 5], 40, 20, 1))
        self.assertEqual([len(p) for p in b["polys"]], [2])  # (one outline, one hole)
        self.assertEqual(new["points"], {})
        self.assertEqual(rep["dropped"], 1)  # (the length went with its line)
        self.assertAlmostEqual(rep["area"][1], 800 - math.pi * 16, delta=0.25)  # (the hole: a polygon within 0.01 mm)

    def test_an_open_chain_is_refused(self):
        with self.assertRaises(ValueError):
            sc.outline(lines((0, 0), (10, 0), (10, 10)), ["l1", "l2"])


class TestDrawings(unittest.TestCase):
    """The owner's drawings: hundreds of shapes before, the same regions with far fewer after."""

    @classmethod
    def setUpClass(cls):
        try:
            from auto3d.drawing2d import read_drawing
        except ImportError:  # pragma: no cover
            raise unittest.SkipTest("ezdxf missing")
        cls.d = {n: read_drawing((DRAWINGS / n).read_bytes(), n) for n in ("Finger.dxf", "Drive Gear.dxf")}

    def test_finger(self):
        t0 = time.time()
        sk, rep = sc.from_drawing(self.d["Finger.dxf"])
        self.assertLess(time.time() - t0, 3)
        self.assertEqual(rep["before"], {"points": 827, "entities": 702, "constraints": 0})
        self.assertLess(rep["after"]["entities"], 250)
        self.assertLess(rep["after"]["points"], 400)
        k = kinds(sk)
        self.assertEqual(k["circle"], 3)
        # each of the file's 42 splines (a tooth's flank, flattened into 9-13 points) is one shape again — here an arc
        # (it fits one within the tolerance), else a spline; the keyed bore (a polyline with a bulge): an arc + 3 lines
        self.assertEqual(rep["after"]["entities"], 135 + 47 + 42 + 3 + 4)
        self.assertEqual((k["arc"], k["line"]), (135 + 42 + 1, 47 + 3))
        a0, a1 = rep["area"]
        self.assertAlmostEqual(a0, 7186.806, delta=0.01)  # (the closed outline, as a quick part takes it)
        self.assertAlmostEqual(a1, a0, delta=a0 * 0.005)
        self.assertFalse(rep["issues"])

    def test_old_sketches_close_once_simplified(self):
        old = naive(self.d["Finger.dxf"])
        self.assertLess(sc.region_area(old), 1000)  # (its ends did not meet: no closed outline to extrude)
        new, rep = sc.simplify(old)
        self.assertAlmostEqual(rep["area"][1], 7186.806, delta=7186.806 * 0.005)
        self.assertLess(rep["after"]["entities"], rep["before"]["entities"] / 3)

    def test_the_gear_teeth_join_into_one_curve(self):
        old = naive(self.d["Drive Gear.dxf"])
        teeth = [e["id"] for e in old["entities"] if e["t"] != "circle" and max(abs(v) for q in (e["a"], e["b"]) for v in old["points"][q]) > 15]
        self.assertGreater(len(teeth), 600)
        t0 = time.time()
        new, rep = sc.join(old, teeth)
        self.assertLess(time.time() - t0, 2)
        self.assertEqual(kinds(new)["spline"], 1)
        self.assertLess(rep["after"]["entities"], 20)
        self.assertAlmostEqual(rep["area"][1], 1540.308, delta=1540.308 * 0.005)

    @unittest.skipUnless(OCC, "OCP not installed")
    def test_extruded(self):
        """The cleaned Finger and the joined gear extrude: volume = area × 5, watertight, the same after STEP."""
        sk, rep = sc.from_drawing(self.d["Finger.dxf"])
        r = extruded(sk)
        self.assertTrue(all(f["ok"] for f in r["features"]), r["features"])
        self.assertAlmostEqual(r["body"]["volume"], 7186.806 * 5, delta=7186.806 * 5 * 0.005)
        self.assertTrue(watertight(r["body"]))
        self.assertAlmostEqual(step_volume(sk), r["body"]["volume"], delta=1e-3)
        old = naive(self.d["Drive Gear.dxf"])
        new, _ = sc.join(old, [e["id"] for e in old["entities"] if e["t"] != "circle"])
        r = extruded(new)
        self.assertTrue(all(f["ok"] for f in r["features"]), r["features"])
        # (one closed B-spline of hundreds of spans round the teeth: kernel.volume integrates it span by span)
        self.assertAlmostEqual(r["body"]["volume"], 1540.308 * 5, delta=1540.308 * 5 * 0.005)
        self.assertTrue(watertight(r["body"]))
        self.assertAlmostEqual(step_volume(new), r["body"]["volume"], delta=0.01)

    @unittest.skipUnless(OCC, "OCP not installed")
    def test_outline_block_extrudes(self):
        sk = lines((0, 0), (40, 0), (40, 20), (0, 20), closed=True)
        sk["points"]["c"] = [20, 10]
        sk["entities"].append({"id": "c1", "t": "circle", "c": "c", "r": 4})
        new, _ = sc.outline(sk, [e["id"] for e in sk["entities"]], tol=0.001)
        r = extruded(new, 10)
        self.assertAlmostEqual(r["body"]["volume"], (800 - math.pi * 16) * 10, delta=0.5)  # (the hole as a fine polygon)
        self.assertTrue(watertight(r["body"]))
        self.assertAlmostEqual(step_volume(new, 10), r["body"]["volume"], delta=1e-3)


@unittest.skipUnless(OCC, "OCP not installed")
class TestClosedSpline(unittest.TestCase):
    def test_either_way_round_with_a_hole(self):
        """A closed spline drawn clockwise is one edge going clockwise: the face turns it round, so the hole cuts."""
        for sgn in (1, -1):
            pts = {f"q{i}": [20 * math.cos(sgn * i * math.pi / 8), 20 * math.sin(sgn * i * math.pi / 8)] for i in range(16)}
            pts["c"] = [0, 0]
            sk = {"points": pts, "entities": [{"id": "s1", "t": "spline", "pts": [f"q{i}" for i in range(16)] + ["q0"]},
                                              {"id": "c1", "t": "circle", "c": "c", "r": 5}]}
            v = extruded(sk, 1)["body"]["volume"]
            self.assertAlmostEqual(v, math.pi * (400 - 25), delta=2.0)  # (a spline through 16 points of the circle)


class TestEndpoints(unittest.TestCase):
    def test_clean_and_drawing(self):
        import server
        c = server.app.test_client()
        sk = lines((0, 0), (3, 0), (6, 0))
        r = c.post("/api/model/sketch/clean", json={"op": "simplify", "sketch": sk}).get_json()
        self.assertEqual(r["report"]["after"]["entities"], 1)
        r = c.post("/api/model/sketch/clean", json={"op": "join", "sketch": sk, "ids": []})
        self.assertEqual(r.status_code, 400)
        r = c.post("/api/model/sketch/clean", json={"op": "nonsense", "sketch": sk})
        self.assertEqual(r.status_code, 400)
        d = {"entities": [{"t": "line", "a": [0, 0], "b": [10, 0], "layer": "0"}, {"t": "line", "a": [10, 0.002], "b": [10, 10], "layer": "0"},
                          {"t": "text", "at": [0, 0], "text": "x", "layer": "0"}], "layers": [{"name": "0"}]}
        r = c.post("/api/drawing/sketch", json=d).get_json()
        self.assertEqual(kinds(r["sketch"]), {"line": 2})
        self.assertEqual(len(r["sketch"]["points"]), 3)


if __name__ == "__main__":
    unittest.main()
