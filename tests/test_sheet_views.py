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


LONG = {"bbox": [0, 0, 0, 357.5, 60, 13]}  # (an assembly of parts in a row: its front and top views long)
LIST = [[170, 28], [180, 28 + 56]]  # (title block D, a C parts list of 5 rows on it)


def boxes(lay, size, at=True):
    """The views' boxes on the paper (y down): the front, top and (at) the iso view in the right one's place."""
    s, out = lay["scale"][0] / lay["scale"][1], {}
    for v, (w, h) in {"Front": (size[0], size[2]), "Top": (size[0], size[1])}.items():
        x, y = lay["views"][v]
        out[v] = (x - w * s / 2, y - h * s / 2, x + w * s / 2, y + h * s / 2)
    x, y, k = lay["iso"] if not at else [*lay["views"]["Right"], lay["iso"][2]]
    out["Iso"] = (x - k / 2, y - k / 2, x + k / 2, y + k / 2)
    return out


def over(b, keep, pw=297, ph=210, m=10):
    return any(b[0] < pw - m and pw - m - w < b[2] and b[1] < ph - m and ph - m - h < b[3] for w, h in keep)


class TestLayoutKeepOut(unittest.TestCase):
    """An assembly's sheet: the views keep off its parts list + title block (frame keep, iso_at Right)."""
    SIZE = (357.5, 60, 13)

    def test_views_move_off_the_list(self):
        plain = layout(LONG, "A4", frame={"title": 28})
        lay = layout(LONG, "A4", frame={"title": 28, "keep": LIST, "iso_at": "Right"})
        self.assertTrue(over(boxes(plain, self.SIZE)["Top"], LIST))  # (as before: the top view's end under the list)
        self.assertEqual(lay["scale"], plain["scale"])  # (room enough: the same scale, moved left)
        for v, b in boxes(lay, self.SIZE).items():
            self.assertFalse(over(b, LIST), v)
            self.assertGreaterEqual(b[0], 10, v)
        self.assertEqual(lay["views"]["Front"][0], lay["views"]["Top"][0])  # (the front and the top view still line up)
        self.assertLess(lay["views"]["Top"][0], plain["views"]["Top"][0])
        self.assertEqual(lay["iso"][:2], lay["views"]["Right"])

    def test_no_room_takes_a_smaller_scale(self):
        tall = [[170, 28], [200, 110]]
        lay = layout(LONG, "A4", frame={"title": 28, "keep": tall, "iso_at": "Right"})
        self.assertEqual(lay["scale"], [1, 10])  # (a step under 1:5)
        self.assertFalse(any(over(b, tall) for b in boxes(lay, self.SIZE).values()))

    def test_own_scale_and_no_list_stay(self):
        self.assertEqual(layout(LONG, "A4", "1:2", {"title": 28, "keep": LIST, "iso_at": "Right"})["views"],
                         layout(LONG, "A4", "1:2", {"title": 28})["views"])  # (no room at 1:2: kept, the editor warns)
        self.assertEqual(layout(BOX, frame={"keep": []}), layout(BOX))
        self.assertEqual(layout(BOX, frame={"keep": [["x", 1], [5], None]}), layout(BOX))  # (bad entries left out)

    def test_keep_per_paper(self):
        keep = {"A4": LIST, "A3": [[180, 28], [180, 200]]}
        a4 = layout(LONG, "A4", frame={"title": 28, "keep": keep, "iso_at": "Right"})
        a3 = layout(LONG, "A3", frame={"title": 28, "keep": keep, "iso_at": "Right"})
        self.assertFalse(any(over(b, LIST) for b in boxes(a4, self.SIZE).values()))
        self.assertFalse(any(over(b, keep["A3"], 420, 297) for b in boxes(a3, self.SIZE).values()))

    def test_tall_list_beside_the_iso_moves_it(self):
        e = [[90, 56], [90, 56 + 13 + 7 * 10.2]]  # (title block E, a 7-row E list: up beside the iso view)
        plain = layout(LONG, "A4", frame={"title": 56})
        lay = layout(LONG, "A4", frame={"title": 56, "keep": e, "iso_at": "Right"})
        self.assertTrue(over(boxes(plain, self.SIZE)["Iso"], e))
        self.assertFalse(over(boxes(lay, self.SIZE)["Iso"], e))
        self.assertLess(lay["views"]["Right"][0], plain["views"]["Right"][0])


if __name__ == "__main__":
    unittest.main()
