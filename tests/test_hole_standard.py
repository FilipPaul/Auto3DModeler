"""Standard holes (auto3d/modeler/holes.py): a hole step's hole_type + standard fill its sizes from the ISO tables —
the table itself (and the browser's copy in web/js/modeler/holes.js), then the solids: an M5 counterbore, countersink
and tapped hole against their formulas, watertight, read back from STEP, and their drawing callouts.

Run:  py -m unittest tests.test_hole_standard -v
"""
import json
import math
import re
import unittest
from pathlib import Path

from auto3d.modeler import available, holes
from test_modeler_kernel import watertight

OCC = available("occ")
if OCC:
    from auto3d.modeler import doc, kernel as K, sheet
    from test_modeler_features import box, vol

JS = Path(__file__).resolve().parent.parent / "web" / "js" / "modeler" / "holes.js"
TOP = {"face": {"name": "E1:end"}, "frame": {"o": [20, 10, 10], "x": [1, 0, 0], "n": [0, 0, 1]}}


class TestHoleTable(unittest.TestCase):
    def test_presets(self):
        """M5: clearance Ø5.5 (ISO 273 medium), counterbore Ø10 ↧ 5.4 over it, countersink Ø11.2 at 90°, tapped M5 at
        Ø4.2; every size has all four, the heads wider than the hole; unknown type / size refused."""
        self.assertEqual(holes.preset("clearance", "M5"), {"d": 5.5})
        self.assertEqual(holes.preset("counterbore", "M5"), {"d": 5.5, "head": "cbore", "head_d": 10, "head_depth": 5.4})
        self.assertEqual(holes.preset("countersink", "M5"), {"d": 5.5, "head": "csk", "head_d": 11.2, "head_angle": 90})
        self.assertEqual(holes.preset("tapped", "M5"), {"d": 4.2, "thread": "M5"})
        self.assertEqual(list(holes.SIZES), list(holes.THREADS))
        for size, s in holes.SIZES.items():
            nominal = float(size[1:])
            self.assertTrue(holes.THREADS[size] < nominal < s["clearance"] < s["cbore_d"] < s["csk_d"] + 1, size)
            self.assertGreater(s["cbore_depth"], nominal * 0.9, size)  # (deep enough for the head: k = d)
        for bad in (("spot", "M5"), ("clearance", "M7")):
            with self.assertRaises(ValueError):
                holes.preset(*bad)

    def test_resolve(self):
        """A step's own size wins over the table (not a tapped hole's drill); its head / thread are the type's; no type:
        the step as it is; a type with no size refused."""
        f = {"id": "H1", "type": "hole", "hole_type": "counterbore", "standard": "M5", "head_depth": 4, "thread": "M3"}
        self.assertEqual(holes.resolve(f), {"id": "H1", "type": "hole", "hole_type": "counterbore", "standard": "M5", "head_depth": 4,
                                             "d": 5.5, "head": "cbore", "head_d": 10})
        self.assertEqual(holes.resolve({"hole_type": "tapped", "standard": "M6", "d": 9, "head": "csk"}),
                         {"hole_type": "tapped", "standard": "M6", "d": 5.0, "thread": "M6"})
        self.assertEqual(holes.resolve({"hole_type": "clearance", "standard": "M3", "head_d": 6}), {"hole_type": "clearance", "standard": "M3", "d": 3.4})
        plain = {"d": 5, "head": "cbore"}
        self.assertIs(holes.resolve(plain), plain)
        with self.assertRaises(ValueError):
            holes.resolve({"hole_type": "counterbore"})

    def test_browser_table_matches(self):
        """web/js/modeler/holes.js has the same sizes and tap drills."""
        text = JS.read_text(encoding="utf-8")
        table = re.search(r"HOLE_SIZES = (\{.*?\n\});", text, re.S).group(1)
        self.assertEqual(json.loads(re.sub(r",\s*\}$", "}", table)), holes.SIZES)
        threads = re.search(r"THREADS = \{(.*?)\};", text).group(1)
        got = {k.strip("' "): float(v) for k, v in (x.split(":") for x in threads.split(","))}
        self.assertEqual(got, holes.THREADS)


@unittest.skipUnless(OCC, "OCP not installed")
class TestStandardHoles(unittest.TestCase):
    def hole(self, **kw):
        return {"id": "H1", "type": "hole", "plane": TOP, "points": [[0, 0]], "through": True, **kw}

    def check(self, f, want, callout, delta=1e-3):
        r, v = vol(*box(), f)
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, want, delta=delta)
        self.assertTrue(watertight(r["body"]))
        self.assertAlmostEqual(K.volume(K.from_step(doc.export({"features": [*box(), f]}, "step"))), v, delta=0.05)
        s = doc.sheet({"features": [*box(), f]}, "medium")
        self.assertEqual([sheet.callout(s["geometry"], d) for d in s["dims"] if d.get("hole")], [callout])
        return r

    def test_counterbore(self):
        """M5 counterbore through the 10 block: Ø5.5 + Ø10 × 5.4 — "Ø5.5 ⌴ Ø10 ↧ 5.4"; its depth given (4) wins."""
        r = self.check(self.hole(hole_type="counterbore", standard="M5"), 8000 - math.pi * (2.75 ** 2 * 10 + (25 - 2.75 ** 2) * 5.4), "Ø5.5 ⌴ Ø10 ↧ 5.4")
        names = {n for f in r["body"]["faces"] for n in f.get("names") or [f.get("name")] if n and n.startswith("H1")}
        self.assertTrue({"H1:hole:0", "H1:cbore:0", "H1:cbore_floor:0"} <= names, names)
        _, v = vol(*box(), self.hole(hole_type="counterbore", standard="M5", head_depth=4))
        self.assertAlmostEqual(v, 8000 - math.pi * (2.75 ** 2 * 10 + (25 - 2.75 ** 2) * 4), delta=1e-3)

    def test_countersink(self):
        """M5 countersink: Ø5.5 through, a 90° cone Ø11.2 -> Ø5.5, (11.2 - 5.5) / 2 = 2.85 deep — "Ø5.5 ⌵ Ø11.2 × 90°"."""
        h, R, r = 2.85, 5.6, 2.75
        cone = math.pi * h / 3 * (R * R + R * r + r * r) - math.pi * r * r * h
        self.check(self.hole(hole_type="countersink", standard="M5"), 8000 - math.pi * r * r * 10 - cone, "Ø5.5 ⌵ Ø11.2 × 90°", delta=0.05)

    def test_tapped(self):
        """M5 tapped 8 deep: the Ø4.2 tap drill, "M5 ↧ 8"; listed as a threaded hole (cosmetic / real threads)."""
        f = self.hole(hole_type="tapped", standard="M5", through=False, depth=8)
        self.check(f, 8000 - math.pi * 2.1 ** 2 * 8, "M5 ↧ 8")
        r = doc.rebuild({"features": [*box(), f], "threads": "cosmetic"})
        self.assertEqual([(h["thread"], h["minor"]) for h in r["threads"]["holes"]], [("M5", 4.2)])

    def test_clearance_and_errors(self):
        """M4 clearance: Ø4.5 through "Ø4.5 THRU"; an unknown size or a type without one is an issue, the part kept."""
        self.check(self.hole(hole_type="clearance", standard="M4"), 8000 - math.pi * 2.25 ** 2 * 10, "Ø4.5 THRU")
        for bad in ({"hole_type": "tapped", "standard": "M7"}, {"hole_type": "countersink"}, {"hole_type": "spot", "standard": "M5"}):
            r, v = vol(*box(), self.hole(**bad))
            self.assertFalse(r["ok"], bad)
            self.assertAlmostEqual(v, 8000, delta=1e-6)
            self.assertTrue(r["features"][-1]["issues"], bad)


if __name__ == "__main__":
    unittest.main()
