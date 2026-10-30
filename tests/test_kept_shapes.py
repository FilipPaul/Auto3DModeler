"""Booleans leave their arguments as they were (kernel.bop is non-destructive): the steps' shapes are kept and cut again
(doc's prefix cache — every preview of a step cuts the same earlier body), so a boolean that grew their tolerances in
place spoiled every later step. The app report's part: a 120 × 120 × 8 plate with a Ø12 pin 16 high; two hole previews
grazing the pin's rim (as the mouse moves over it) grew its top edge 12 mm "thick" — then a Ø4 hole down the pin's
axis cut nothing (24 deep: −891 mm³ and two solids), a Ø4 cut through gave −227.9 mm³ and two solids, a 3 mm slot
cut *added* 189.8 mm³. Now: the kept body's tolerance is untouched; the hole, the cut and the slot take their analytic
volumes, one watertight solid, read back from STEP. Skipped without the CAD kernel.

Run:  py -m unittest tests.test_kept_shapes -v
"""
import copy
import math
import unittest

from auto3d.modeler import available
from test_modeler_kernel import watertight

OCC = available("occ")
if OCC:
    from OCP.ShapeAnalysis import ShapeAnalysis_ShapeTolerance
    from auto3d.modeler import doc, kernel as K


def rect(fid, w, h):
    pts = {"p1": [0, 0], "p2": [w, 0], "p3": [w, h], "p4": [0, h]}
    lines = [{"id": f"l{i + 1}", "t": "line", "a": f"p{i + 1}", "b": f"p{(i + 1) % 4 + 1}"} for i in range(4)]
    return {"id": fid, "type": "sketch", "plane": {"datum": "XY"}, "points": pts, "entities": lines}


def circle(fid, plane, c, r):
    return {"id": fid, "type": "sketch", "plane": plane, "points": {"p1": c}, "entities": [{"id": "c1", "t": "circle", "c": "p1", "r": r}]}


TOP = {"face": {"name": "F2:end"}, "frame": {"o": [60, 60, 8], "x": [1, 0, 0], "n": [0, 0, 1]}}
PIN_TOP = {"face": {"name": "F4:end"}, "frame": {"o": [60, 60, 24], "x": [1, 0, 0], "n": [0, 0, 1]}}
BASE = [rect("F1", 120, 120), {"id": "F2", "type": "extrude", "sketch": "F1", "op": "add", "d": 8},
        circle("F3", TOP, [0, 0], 6), {"id": "F4", "type": "extrude", "sketch": "F3", "op": "add", "d": 16}]
V0 = 120 * 120 * 8 + math.pi * 36 * 16
HOLE = {"id": "F5", "type": "hole", "plane": PIN_TOP, "points": [[0, 0]], "d": 4, "through": True}
# the slot of the report: round ends at (60, 60) and (125, 60), 4 wide — out past the plate's side
SLOT = {"id": "F7", "type": "sketch", "plane": {"datum": "XY"},
        "points": {"p1": [60, 60], "p2": [125, 60], "p3": [60, 58], "p4": [125, 58], "p5": [125, 62], "p6": [60, 62]},
        "entities": [{"id": "l1", "t": "line", "a": "p3", "b": "p4"}, {"id": "c1", "t": "arc", "c": "p2", "a": "p4", "b": "p5"},
                     {"id": "l2", "t": "line", "a": "p5", "b": "p6"}, {"id": "c2", "t": "arc", "c": "p1", "a": "p6", "b": "p3"}]}
CUTS = [circle("F5", {"datum": "XY"}, [60, 60], 2), {"id": "F6", "type": "extrude", "sketch": "F5", "op": "cut", "d": 10, "through": True, "flip": True},
        SLOT, {"id": "F8", "type": "extrude", "sketch": "F7", "op": "cut", "d": 3, "flip": True}]


def tolerance(shape):
    return ShapeAnalysis_ShapeTolerance().Tolerance(shape, 1)  # (the largest of its vertices', edges', faces')


def graze():
    """Two hole previews on the pin's top as the mouse passes its rim: Ø12 just off its axis, then Ø12 just inside the
    rim (the report's own part, a fresh cache) -> (the pin step's kept body before them, its tolerance then)."""
    doc._cache.clear()
    kept = doc.evaluate(copy.deepcopy(BASE))[0].body
    t0 = tolerance(kept.shape)
    for p in ([0, 1e-5], [11.99999, 0]):
        doc.evaluate(copy.deepcopy([*BASE, {**HOLE, "points": [p], "d": 12}]))
    return kept, t0


@unittest.skipUnless(OCC, "OCP not installed")
class TestKeptShapes(unittest.TestCase):
    def test_kept_body_untouched(self):
        """The pin step's body, cut by the previews, has the tolerance it had (1e-7 mm; it grew to 12 mm)."""
        body, t0 = graze()
        self.assertIs(doc.evaluate(copy.deepcopy(BASE))[0].body, body)  # (the same kept body: cut again by each preview)
        self.assertLess(tolerance(body.shape), 1e-6)
        self.assertAlmostEqual(tolerance(body.shape), t0, delta=1e-9)

    def test_hole_down_the_pin(self):
        """After the previews, a Ø4 hole on the pin's top: through all and 24 deep both take π·2²·(8 + 16) (the pin and the
        plate under it; was 0 and −891 with two solids) — one watertight solid, the same read back from STEP."""
        want = V0 - math.pi * 4 * 24
        for hole in (HOLE, {**HOLE, "through": False, "depth": 24}):
            graze()
            r = doc.rebuild({"features": copy.deepcopy([*BASE, hole])})
            self.assertTrue(r["ok"], r["features"])
            b = r["body"]
            self.assertAlmostEqual(b["volume"], want, delta=1e-3)
            self.assertEqual(b["solids"], 1)
            self.assertTrue(watertight(b))
            self.assertEqual(r["features"][-1]["warnings"], [])
        step = doc.export({"features": [*BASE, HOLE]}, "step")
        self.assertAlmostEqual(K.volume(K.from_step(step)), want, delta=1e-3)

    def test_cut_and_slot(self):
        """After the previews, the report's cuts from the bottom: the Ø4 cut through −301.6 mm³ (was −227.9, two solids),
        the 3 mm slot out past the side −(its area in the plate less the Ø4 already cut) × 3 = −701.2 (was +189.8)."""
        graze()
        r = doc.rebuild({"features": copy.deepcopy([*BASE, *CUTS[:2]])})
        self.assertAlmostEqual(r["body"]["volume"], V0 - math.pi * 4 * 24, delta=1e-3)
        self.assertEqual(r["body"]["solids"], 1)
        graze()
        r = doc.rebuild({"features": copy.deepcopy([*BASE, *CUTS])})
        self.assertTrue(r["ok"], r["features"])
        slot = (60 * 4 + math.pi * 4 / 2 - math.pi * 4) * 3  # (x 60 … 120 × 4, the round end left of x 60, less the Ø4 hole)
        want = V0 - math.pi * 4 * 24 - slot
        self.assertAlmostEqual(r["body"]["volume"], want, delta=1e-3)
        self.assertEqual(r["body"]["solids"], 1)
        self.assertTrue(watertight(r["body"]))
        step = doc.export({"features": [*BASE, *CUTS]}, "step")
        self.assertAlmostEqual(K.volume(K.from_step(step)), want, delta=1e-3)
        self.assertEqual(K.solids(K.from_step(step)), 1)


if __name__ == "__main__":
    unittest.main()
