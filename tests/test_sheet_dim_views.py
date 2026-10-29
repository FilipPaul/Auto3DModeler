"""Drawing sheets: one size of the part, every view it can be dimensioned in (sheet.places) — a block's height in the
front and the right view (not the top), its depth in the top and the right, a hole's place only where it is seen round,
not its walls (seen from the side: outlines, not edges); a step's hidden edge said so; the iso view never."""
import unittest

from auto3d.modeler import available

OCC = available("occ")
if OCC:
    from auto3d.modeler import doc, sheet as S


def rect(x0, y0, x1, y1):
    pts = {"p1": [x0, y0], "p2": [x1, y0], "p3": [x1, y1], "p4": [x0, y1]}
    return pts, [{"id": f"l{i + 1}", "t": "line", "a": f"p{i + 1}", "b": f"p{(i + 1) % 4 + 1}"} for i in range(4)]


def block(w=60, d=40, h=30):
    """A 60 × 40 × 30 block with a Ø6 hole through it from the top at x 15, y 12 and a step 10 deep along its back
    (y 30 … 40): the step's floor at z 20 is a hidden edge in the front view, a visible one in the right view."""
    pts, lines = rect(0, 0, w, d)
    top = {"face": {"name": "E1:end"}, "frame": {"o": [w / 2, d / 2, h], "x": [1, 0, 0], "n": [0, 0, 1]}}
    sp, sl = rect(-1, 30, w + 1, d + 1)
    return {"features": [{"id": "S1", "type": "sketch", "plane": {"datum": "XY"}, "points": pts, "entities": lines},
                         {"id": "E1", "type": "extrude", "sketch": "S1", "op": "add", "d": h},
                         {"id": "H1", "type": "hole", "plane": top, "points": [[15 - w / 2, 12 - d / 2]], "d": 6, "through": True},
                         {"id": "S2", "type": "sketch", "plane": {**top, "origin": "corner"}, "points": sp, "entities": sl},
                         {"id": "E2", "type": "extrude", "sketch": "S2", "op": "cut", "d": 10}]}


@unittest.skipUnless(OCC, "OCP not installed")
class TestDimViews(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = doc.sheet(block(), "medium")
        cls.P = cls.r["geometry"]["places"]

    def views(self, ax, at):
        """The views a place can be dimensioned in -> {view: (key, dir, how)}."""
        row = next((vs for v, vs in self.P[ax] if abs(v - at) < 0.01), [])
        return {v: (key, d, how) for v, key, d, how in row}

    def test_overall_sizes(self):
        height, depth, width = self.views("z", 30), self.views("y", 40), self.views("x", 60)
        self.assertEqual(set(height), {"Front", "Right"})
        self.assertEqual(height["Front"], ("box#y1", "v", "b"))
        self.assertEqual(height["Right"][1], "v")
        self.assertEqual(set(depth), {"Top", "Right"})
        self.assertEqual(depth["Right"], ("box#x1", "h", "b"))  # (the right view: the part's y across)
        self.assertEqual(depth["Top"][1], "v")
        self.assertEqual(set(width), {"Front", "Top"})
        for ax in "xyz":  # (each axis's 0: in the same two views as its far end)
            self.assertEqual(len(self.views(ax, 0)), 2)

    def test_the_hole(self):
        """Its place: only where it is seen round (the top view)."""
        x, y = self.views("x", 15), self.views("y", 12)
        self.assertEqual(set(x), {"Top"})
        self.assertEqual(set(y), {"Top"})
        self.assertEqual(x["Top"][2], "c")
        self.assertTrue(x["Top"][0].startswith("H1:hole:") and x["Top"][0].endswith("#c"))
        self.assertEqual(x["Top"][1], "h")
        self.assertEqual(y["Top"][1], "v")
        self.assertEqual(self.views("x", 12), {})  # (its walls seen from the side: outlines, not edges — nothing to hang on)
        self.assertEqual(self.views("y", 9), {})

    def test_the_step(self):
        """The step's floor (z 20): an edge of the front view behind the block's face (hidden) and of the right view
        (seen): both offered, the right one said to show it; where it begins (y 30): the top and the right view."""
        floor = self.views("z", 20)
        self.assertEqual(set(floor), {"Front", "Right"})
        self.assertEqual((floor["Front"][2], floor["Right"][2]), ("h", "e"))
        self.assertEqual({v: dv[1] for v, dv in floor.items()}, {"Front": "v", "Right": "v"})
        self.assertEqual(set(self.views("y", 30)), {"Top", "Right"})

    def test_no_iso_and_slanted_views(self):
        self.assertIsNone(S._axis([0.7071, 0.7071, 0]))
        self.assertEqual(S._axis([0, -1, 0]), (1, -1))
        self.assertNotIn("Iso", {v for ax in "xyz" for _, vs in self.P[ax] for v, *_ in vs})

    def test_section_view(self):
        """Section A–A (seen as the right view): the height and the depth there too."""
        r = doc.sheet(block(), "medium", section=True)
        P = r["geometry"]["places"]
        z = next(vs for v, vs in P["z"] if abs(v - 30) < 0.01)
        self.assertEqual({v for v, *_ in z}, {"Front", "Right", "Section"})


if __name__ == "__main__":
    unittest.main()
