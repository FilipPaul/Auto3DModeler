"""D holes (a shaft's flat on one side: hole_type "d_flat"): the volume of a Ø5 D4.5 hole through the 40 × 20 × 10 box
against the circle minus its segment, its flat facing the face's x (or turned), watertight, read back from STEP, the
D-shaft defaults, the drawing callout "Ø5 D4.5 THRU", and a flat that does not fit refused.

Run:  py -m unittest tests.test_hole_dflat -v
"""
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

TOP = {"face": {"name": "E1:end"}, "frame": {"o": [20, 10, 10], "x": [1, 0, 0], "n": [0, 0, 1]}}


def d_area(d, flat):
    """A D's area: the circle less the segment cut off by a chord flat − r from the centre."""
    r = d / 2
    a = flat - r
    return math.pi * r * r - (r * r * math.acos(a / r) - a * math.sqrt(r * r - a * a))


class TestDefaults(unittest.TestCase):
    def test_d_flat(self):
        """Common D-shafts' sizes across the flat; any other Ø: 0.9 × d (the flat 0.8 × r from the centre)."""
        self.assertEqual([holes.d_flat(d) for d in (3, 4, 5, 6, 8)], [2.5, 3.5, 4.5, 5.5, 7.5])
        self.assertEqual(holes.d_flat(10), 9)
        self.assertEqual(holes.resolve({"hole_type": "d_flat", "d": 5, "head": "cbore", "thread": "M5"}), {"hole_type": "d_flat", "d": 5, "flat": 4.5})
        self.assertEqual(holes.resolve({"hole_type": "d_flat", "d": 5, "flat": 4})["flat"], 4)

    def test_browser_table_matches(self):
        """web/js/modeler/holes.js has the same D-shaft sizes."""
        text = (Path(__file__).resolve().parent.parent / "web" / "js" / "modeler" / "holes.js").read_text(encoding="utf-8")
        got = re.search(r"D_FLATS = \{(.*?)\};", text).group(1)
        self.assertEqual({int(k): float(v) for k, v in (x.split(":") for x in got.split(","))}, holes.D_FLATS)


@unittest.skipUnless(OCC, "OCP not installed")
class TestDHoles(unittest.TestCase):
    def hole(self, **kw):
        return {"id": "H1", "type": "hole", "plane": TOP, "points": [[0, 0]], "through": True, "hole_type": "d_flat", "d": 5, **kw}

    def test_volume_flat_and_step(self):
        """Ø5 D4.5 through 10: 8000 − 10 × (π r² − segment); the flat face H1:flat:0 square to x at x = 20 + 2;
        watertight; STEP round trip; turned 90°: the same volume, the flat square to y."""
        f = self.hole()
        r, v = vol(*box(), f)
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, 8000 - 10 * d_area(5, 4.5), delta=1e-4)
        self.assertTrue(watertight(r["body"]))
        flat = next(x for x in r["body"]["faces"] if x.get("name") == "H1:flat:0")
        self.assertAlmostEqual(abs(flat["normal"][0]), 1, delta=1e-6)
        self.assertAlmostEqual(flat["centroid"][0], 22, delta=1e-6)
        self.assertTrue(any(x.get("name") == "H1:hole:0" for x in r["body"]["faces"]))
        self.assertAlmostEqual(K.volume(K.from_step(doc.export({"features": [*box(), f]}, "step"))), v, delta=0.05)
        r, v2 = vol(*box(), self.hole(flat_angle=90, flat=4, through=False, depth=6))
        self.assertAlmostEqual(v2, 8000 - 6 * d_area(5, 4), delta=1e-4)
        flat = next(x for x in r["body"]["faces"] if x.get("name") == "H1:flat:0")
        self.assertAlmostEqual(flat["centroid"][1], 10 + 1.5, delta=1e-6)

    def test_callout(self):
        """The drawing says "Ø5 D4.5 THRU" (blind: "Ø5 D4 ↧ 6"), and the flat's edge gets no dimension of its own."""
        for f, want in ((self.hole(), "Ø5 D4.5 THRU"), (self.hole(flat=4, through=False, depth=6), "Ø5 D4 ↧ 6")):
            s = doc.sheet({"features": [*box(), f]}, "full")
            self.assertEqual([sheet.callout(s["geometry"], d) for d in s["dims"] if d.get("hole")], [want])
            self.assertFalse(any(":flat:" in (d.get("a", "") + d.get("b", "")) for d in s["dims"]), s["dims"])

    def test_errors(self):
        """A flat not between r and d across, or a D teardrop: an issue, the part kept."""
        for bad in ({"flat": 5}, {"flat": 2.5}, {"flat": 7}, {"teardrop": True}):
            r, v = vol(*box(), self.hole(**bad))
            self.assertFalse(r["ok"], bad)
            self.assertAlmostEqual(v, 8000, delta=1e-6)


if __name__ == "__main__":
    unittest.main()
