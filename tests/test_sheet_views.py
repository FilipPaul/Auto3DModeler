"""Drawing sheets: a scale as people write it, the layout for the sheet's own scale and frame."""
import unittest

from auto3d.modeler.sheet import layout, parse_scale

BOX = {"bbox": [0, 0, 0, 60, 30, 8]}


class TestParseScale(unittest.TestCase):
    def test_written_ratios(self):
        self.assertEqual(parse_scale("1:2522"), (1, 2522))
        self.assertEqual(parse_scale("3:1"), (3, 1))
        self.assertEqual(parse_scale(" 1 : 20 "), (1, 20))
        self.assertEqual(parse_scale("1/5"), (1, 5))
        self.assertEqual(parse_scale("1,5:1"), (1.5, 1))
        self.assertEqual(parse_scale([1, 2]), (1, 2))

    def test_a_number_is_a_factor(self):
        self.assertEqual(parse_scale("2"), (2, 1))
        self.assertEqual(parse_scale("0.5"), (1, 2))

    def test_not_a_scale(self):
        for bad in ("abc", "0:1", "1:0", "", None, "1:2:3", "-1:2", ["a", 1]):
            with self.assertRaises(ValueError, msg=repr(bad)):
                parse_scale(bad)


class TestLayoutScale(unittest.TestCase):
    def test_default_is_as_before(self):
        lay = layout(BOX)
        self.assertEqual((lay["paper"], lay["scale"], lay["margin"], lay["title"]), ("A4", [1, 1], 10, 38))
        self.assertEqual(lay["margins"], [10, 10, 10, 10])
        self.assertEqual(lay["views"]["Front"], [79.25, 48.0])

    def test_own_scale_is_kept(self):
        lay = layout(BOX, scale="1:2522")
        self.assertEqual(lay["scale"], [1, 2522])
        self.assertEqual(lay["paper"], "A4")

    def test_own_scale_too_big_for_a4_takes_a3(self):
        self.assertEqual(layout(BOX, scale="5:1")["paper"], "A3")
        self.assertEqual(layout(BOX, "A4", scale="5:1")["paper"], "A4")  # (asked for: kept — the editor warns)

    def test_the_frames_margins(self):
        lay = layout(BOX, frame={"m": [20, 10, 10, 10]})  # (ISO 5457: 20 mm on the left for filing)
        self.assertEqual(lay["margins"], [20, 10, 10, 10])
        self.assertEqual(lay["views"]["Front"], [20 + 267 / 4, 48.0])
        self.assertEqual(layout(BOX, frame={"m": [12]})["margins"], [12, 12, 12, 12])
        low = layout(BOX, frame={"title": 14})  # (a strip title block: the views get its room)
        self.assertEqual(low["title"], 14)
        self.assertGreater(low["views"]["Top"][1], layout(BOX)["views"]["Top"][1])

    def test_narrow_margins_fit_a_bigger_scale(self):
        big = {"bbox": [0, 0, 0, 110, 60, 40]}
        self.assertEqual(layout(big, "A4", frame={"m": [5, 5, 5, 5], "title": 14})["scale"], [1, 1])  # (the auto-fit counts the margins)
        self.assertEqual(layout(big, "A4", frame={"m": [25, 25, 25, 25]})["scale"], [1, 2])

    def test_bad_scale_raises(self):
        with self.assertRaises(ValueError):
            layout(BOX, scale="big")


if __name__ == "__main__":
    unittest.main()
