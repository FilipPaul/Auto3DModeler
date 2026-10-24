"""Bending: folds (roof / gutter / U), rolls, validation, export and printing of bent parts.

Run:  python -m unittest discover -s tests -v
"""
import math
import unittest
from pathlib import Path

from auto3d.bend import bend_solid
from auto3d.export import build_solid, to_step
from auto3d.printing import BUILTIN_PRINTERS, plan, bend_pieces
from auto3d.sketch import build_model
from auto3d.solver import solve

from test_design_print import mesh_stats

SAMPLE = Path(__file__).resolve().parent.parent / "initial draft.pdf"


def fold(pos, angle, radius=0.5, toward="back", axis="x", **kw):
    return {"id": f"b{pos}", "name": f"Bend at {pos}", "axis": axis, "pos": pos, "angle": angle, "radius": radius,
            "toward": toward, **kw}


class BendTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        model, _, _ = build_model(SAMPLE.read_bytes())
        cls.unit = model["unit"]
        cls.solid = build_solid(solve(model), cls.unit)
        cls.flat_volume = cls.solid.volume()

    def bend(self, *bends):
        out, bender, issues = bend_solid(self.solid, list(bends), self.unit)
        return out, bender, issues

    def check_solid(self, b):
        vol, bad = mesh_stats(b)
        self.assertEqual(bad, 0, "bent mesh is not watertight")
        # neutral-axis bending keeps the volume (facet chords lose a tiny bit)
        self.assertAlmostEqual(vol, self.flat_volume, delta=self.flat_volume * 0.002)

    def test_roof(self):
        b, bender, issues = self.bend(fold(39.35, 60))
        self.assertEqual(issues, [])
        self.check_solid(b)
        x0, _, x1, _ = b.xy_bounds()
        z0, z1 = b.z_range()
        self.assertEqual(z0, 0.0)
        # two 39 cm wings tilted by 30° each: rise ≈ 39 * sin(30°)
        self.assertGreater(z1, 15)
        self.assertLess(x1 - x0, 78.7)
        # symmetric: the ridge is in the middle
        self.assertAlmostEqual((x0 + x1) / 2, 78.7 / 2, delta=0.5)

    def test_u_profile_and_gutter(self):
        b, _, issues = self.bend(fold(20, 90, 1, "front"), fold(60, 90, 1, "front"))
        self.assertEqual(issues, [])
        self.check_solid(b)
        x0, _, x1, _ = b.xy_bounds()
        # each 90° bend zone is π/2 · (r + t/2) long, centred on its line, so half of each zone comes off
        # the straight base between the lines; outer width = base + 2 · (r + t)
        zone = math.pi / 2 * (1 + 0.5)
        self.assertAlmostEqual(x1 - x0, (60 - 20) - zone + 2 * (1 + 1), delta=0.05)

    def test_roll(self):
        b, bender, issues = self.bend({"id": "r", "axis": "x", "angle": 180, "mode": "roll", "toward": "back"})
        self.assertEqual(issues, [])
        self.check_solid(b)
        rn = 78.7 / math.pi  # neutral radius of a half circle
        x0, _, x1, _ = b.xy_bounds()
        self.assertAlmostEqual(x1 - x0, 2 * (rn + 0.5), delta=0.2)
        self.assertAlmostEqual(bender.ops[0]["r"], rn - 0.5, places=6)

    def test_bend_across_the_other_axis(self):
        b, _, issues = self.bend(fold(5.5, 45, 1, axis="y"))
        self.assertEqual(issues, [])
        self.check_solid(b)
        self.assertAlmostEqual(b.xy_bounds()[2] - b.xy_bounds()[0], 78.7, places=6)  # x untouched

    def test_validation(self):
        cases = {
            "overlap": [fold(20, 90, 5), fold(24, 90, 5)],
            "same direction": [fold(20, 90), fold(5, 30, axis="y")],
            "past the end": [fold(1, 90, 5)],
            "between 0 and 360": [fold(30, 0)],
        }
        for key, bends in cases.items():
            with self.subTest(case=key):
                out, bender, issues = self.bend(*bends)
                self.assertIsNone(bender)
                self.assertTrue(any(key in i["message"] for i in issues), issues)
                self.assertIs(out, self.solid)

    def test_radius_vs_embossed_design(self):
        layer = {"id": "g", "name": "Grid", "op": "emboss", "depth": 0.2, "margin": 0.5, "face": "top",
                 "fill": {"pattern": "square", "sx": 1, "width": 0.1}}
        model, _, _ = build_model(SAMPLE.read_bytes())
        ribbed = build_solid(solve(model), self.unit, [layer])
        _, bender, issues = bend_solid(ribbed, [fold(39, 90, 0.1, "front")], self.unit)
        self.assertIsNone(bender)
        self.assertTrue(any("embossed" in i["message"] for i in issues))
        out, bender, issues = bend_solid(ribbed, [fold(39, 90, 0.5, "front")], self.unit)
        self.assertIsNotNone(bender)
        self.assertEqual(mesh_stats(out)[1], 0)

    def test_faceted_step(self):
        b, _, _ = self.bend(fold(39.35, 60))
        text = to_step(b, self.unit).decode()
        self.assertEqual(text.count("MANIFOLD_SOLID_BREP"), 1)
        self.assertGreater(text.count("ADVANCED_FACE("), 100)

    def test_printing_bent_part(self):
        b, bender, _ = self.bend(fold(39.35, 40))
        printer = BUILTIN_PRINTERS[1]
        r = plan(self.solid, self.unit, printer, 5, True, {"type": "hidden_dovetail"},
                 avoid=[(bender.axis, op["s"], op["e"]) for op in bender.ops])
        bend_pieces(r, bender, self.unit, 5)
        zone = (bender.ops[0]["s"], bender.ops[0]["e"])
        for sm in r["seams"]:
            self.assertFalse(zone[0] < sm["pos"] < zone[1], "a cut was placed inside the bend")
        for p in r["pieces"]:
            self.assertEqual(mesh_stats(p["solid"])[1], 0)
            self.assertNotEqual(p["orientation"], "too big")
        self.assertTrue(any(p["size_mm"][2] > 10.5 for p in r["pieces"]))  # the bent piece is no longer flat


if __name__ == "__main__":
    unittest.main()
