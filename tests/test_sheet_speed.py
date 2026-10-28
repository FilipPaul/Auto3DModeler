"""Drawing sheets of big parts: a plate with a hundred and seventy holes in time, a sheet built again from its kept
views, a big imported model drawn as the paper shows it (what is too small to see left out)."""
import base64
import json
import math
import time
import unittest
from unittest import mock

from auto3d.modeler import available

OCC = available("occ")
if OCC:
    from auto3d.modeler import doc, kernel as K, sheet as S


def plate(d=3):
    """A 200 × 100 × 5 plate, a Ø3 hole repeated 19 × 9 (171 holes), one edge rounded."""
    pts = {"p1": [0, 0], "p2": [200, 0], "p3": [200, 100], "p4": [0, 100]}
    lines = [{"id": f"l{i + 1}", "t": "line", "a": f"p{i + 1}", "b": f"p{(i + 1) % 4 + 1}"} for i in range(4)]
    top = {"face": {"name": "E1:end"}, "frame": {"o": [100, 50, 5], "x": [1, 0, 0], "n": [0, 0, 1]}}
    return {"features": [{"id": "S1", "type": "sketch", "plane": {"datum": "XY"}, "points": pts, "entities": lines},
                         {"id": "E1", "type": "extrude", "sketch": "S1", "op": "add", "d": 5},
                         {"id": "H1", "type": "hole", "plane": top, "points": [[-90, -40]], "d": d, "through": True},
                         {"id": "P1", "type": "pattern", "features": ["H1"], "kind": "linear", "dir": [1, 0, 0], "count": 19, "spacing": 10},
                         {"id": "P2", "type": "pattern", "features": ["H1", "P1"], "kind": "linear", "dir": [0, 1, 0], "count": 9, "spacing": 10},
                         {"id": "R1", "type": "fillet", "edges": [{"a": "E1:end", "b": "E1:side:l1", "fp": [100, 0, 5]}], "r": 2}]}


@unittest.skipUnless(OCC, "OCP not installed")
class TestSheetSpeed(unittest.TestCase):
    def test_plate_with_many_holes(self):
        """171 holes: the sheet in seconds (a generous bound), all 171 dimensioned once, the holes' outlines seen from
        the side two points each (not 48), the payload under a megabyte and a half."""
        part = plate()
        doc.body_of(part)  # (the solid itself is not the sheet's time)
        t0 = time.time()
        r = doc.sheet(part, "medium")
        self.assertLess(time.time() - t0, 30)
        self.assertEqual([d["count"] for d in r["dims"] if d["kind"] == "dia"], [171])
        front = r["geometry"]["views"]["Front"]
        self.assertGreater(len(front["hidden"]), 300)
        self.assertTrue(all(len(pl) == 2 for pl in front["hidden"]))
        self.assertLess(len(json.dumps(r)), 1.5e6)

    def test_built_again_from_its_views(self):
        """Another preset, paper or the section on: the part is not projected again (a hundredth of the time); the
        result as a fresh build's; a changed part is projected anew."""
        part = plate(2.5)
        first = doc.sheet(part, "medium")
        with mock.patch.object(K, "project_edges", side_effect=AssertionError("projected again")):
            t0 = time.time()
            full = doc.sheet(part, "full", "A3")
            self.assertLess(time.time() - t0, 2)
        self.assertEqual(full["geometry"], first["geometry"])
        self.assertEqual(full["layout"]["paper"], "A3")
        S._cache.clear()
        self.assertEqual(doc.sheet(part, "full", "A3"), full)  # (made anew: the same)
        sec = doc.sheet(part, "medium", section=True)
        self.assertIn("Section", sec["geometry"]["views"])
        self.assertNotIn("Section", doc.sheet(part, "medium")["geometry"]["views"])  # (the kept views not changed)
        other = doc.sheet(plate(4), "medium")
        self.assertEqual({c["r"] for c in other["geometry"]["views"]["Top"]["circles"] if c["full"]}, {2})

    def test_assembly_sheet_kept(self):
        part = plate(2)
        at = lambda x: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, 0, 0, 1]  # noqa: E731
        inst = [{"id": "I1", "part": part, "matrix": at(0)}, {"id": "I2", "part": part, "matrix": at(300)}]
        r = doc.assembly_sheet(inst, None, 1)
        with mock.patch.object(K, "project_edges", side_effect=AssertionError("projected again")):
            again = doc.assembly_sheet(inst, "A3", 1)
        self.assertEqual(again["geometry"], r["geometry"])
        self.assertEqual(again["layout"]["paper"], "A3")
        moved = doc.assembly_sheet([inst[0], {**inst[1], "matrix": at(250)}], None, 1)
        self.assertEqual(moved["geometry"]["views"]["Front"]["box"][2], 450)

    def test_big_model_drawn_as_the_paper_shows_it(self):
        """An imported model of many solids (made "big" here: HEAVY_FACES lowered): a 100 × 50 × 2 board, five 5 mm
        blocks and forty 0.2 mm specks (under 0.25 mm on the paper at 1:1) — the specks left out and said so, the
        board's sizes as they are; its section cut solid by solid: the board's 50 × 2 cut hatched."""
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
        from OCP.gp import gp_Pnt
        box = lambda x, y, z, w, d, h: BRepPrimAPI_MakeBox(gp_Pnt(x, y, z), w, d, h).Shape()  # noqa: E731
        shapes = [box(0, 0, 0, 100, 50, 2)] + [box(5 + 18 * i, 20, 2, 5, 5, 5) for i in range(5)]
        shapes += [box(3 + 2 * i, 3 + 10 * (i % 4), 2, 0.2, 0.2, 0.2) for i in range(40)]
        step = base64.b64encode(K.to_step(K.compound(shapes))).decode()
        part = {"features": [{"id": "B1", "type": "solid", "step": step}]}
        with mock.patch.object(K, "HEAVY_FACES", 100):
            r = doc.sheet(part, "light", section=True)
        g = r["geometry"]
        self.assertEqual(g["simple"], {"left_out": 40, "under": 0.25})
        self.assertEqual(r["layout"]["scale"], [1, 1])
        self.assertEqual(g["views"]["Top"]["hidden"], [])
        x0, y0, x1, y1 = g["views"]["Top"]["box"]
        self.assertAlmostEqual(x1 - x0, 100, delta=0.01)
        self.assertAlmostEqual(y1 - y0, 50, delta=0.01)
        self.assertTrue(all(math.dist(ln["a"], ln["b"]) >= 0.25 for ln in g["views"]["Top"]["lines"]))  # (no specks' edges)
        area = lambda pl: abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pl, pl[1:] + pl[:1]))) / 2  # noqa: E731
        sec = g["views"]["Section"]
        self.assertAlmostEqual(sum(area(pl) for pl in sec["hatch"]), 50 * 2, delta=0.01)
        self.assertNotIn("simple", doc.sheet({"features": plate()["features"][:2]}, "light")["geometry"])  # (a normal part: as before)

    def test_mesh_outline_joined_and_kept_to_the_paper(self):
        """A mesh's outline pieces in any order become one polyline; a piece smaller than `fine` is left out and the
        points a straight run does not need are dropped."""
        segs = [[(1, 0), (2, 0)], [(0, 0), (1, 0)], [(2, 0), (2, 1)], [(5, 5), (5.01, 5)]]
        self.assertEqual(K._chain(segs), [[(2, 1), (2, 0), (1, 0), (0, 0)], [(5.01, 5), (5, 5)]])
        self.assertEqual(K._chain(segs, fine=0.1), [[(2, 1), (2, 0), (0, 0)]])
        arc = [(10 * math.cos(t / 48), 10 * math.sin(t / 48)) for t in range(49)]
        self.assertEqual(K._straight(arc), arc)  # a curve stays as it is
        self.assertEqual(K._straight([(0, 0), (0.5, 0), (1, 0)]), [(0, 0), (1, 0)])
        self.assertEqual(len(K._straight([(0, 0), (2, 0), (1, 0)])), 3)  # (it goes past its end: kept)


if __name__ == "__main__":
    unittest.main()
