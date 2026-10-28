"""Booleans on all cores (kernel.bop, A3D_PARALLEL_BOOL): every representative part built serially and in parallel
gives the same solid — the volume to 1e-9, the same faces and the same face names (the _carry history), the same
clashes and print pieces. Skipped without the CAD kernel."""
import math
import unittest

from auto3d.modeler import available
from test_sheet_speed import plate

OCC = available("occ")
if OCC:
    from auto3d.modeler import doc, kernel as K, sheet as S


def box(w=40, h=20, d=10):
    pts = {"p1": [0, 0], "p2": [w, 0], "p3": [w, h], "p4": [0, h]}
    lines = [{"id": f"l{i + 1}", "t": "line", "a": f"p{i + 1}", "b": f"p{(i + 1) % 4 + 1}"} for i in range(4)]
    return [{"id": "S1", "type": "sketch", "plane": {"datum": "XY"}, "points": pts, "entities": lines},
            {"id": "E1", "type": "extrude", "sketch": "S1", "op": "add", "d": d}]


TOP = {"face": {"name": "E1:end"}, "frame": {"o": [20, 10, 10], "x": [1, 0, 0], "n": [0, 0, 1]}}


def parts():
    """name -> features: holes, threads, a pattern, fillets, a shell, a split, a rib, the plate with 171 holes."""
    wall = [{"id": "S2", "type": "sketch", "plane": {"datum": "XY"}, "points": {"q1": [0, 15], "q2": [40, 15], "q3": [40, 20], "q4": [0, 20]},
             "entities": [{"id": f"m{i + 1}", "t": "line", "a": f"q{i + 1}", "b": f"q{(i + 1) % 4 + 1}"} for i in range(4)]},
            {"id": "E2", "type": "extrude", "sketch": "S2", "op": "add", "d": 30}]
    rib = [{"id": "S3", "type": "sketch", "plane": {"datum": "YZ", "offset": 20}, "points": {"r1": [15, 25], "r2": [0, 5]},
            "entities": [{"id": "k1", "t": "line", "a": "r1", "b": "r2"}]}, {"id": "R1", "type": "rib", "sketch": "S3", "t": 4}]
    return {
        "holes": [*box(), {"id": "H1", "type": "hole", "plane": TOP, "points": [[-10, 0], [10, 0]], "d": 6, "through": True},
                  {"id": "H2", "type": "hole", "plane": TOP, "points": [[0, 4]], "d": 4, "depth": 5}],
        "threads": [*box(), {"id": "H1", "type": "hole", "plane": TOP, "points": [[0, 0], [10, 0]], "through": True, "thread": "M5"},
                    {"id": "H2", "type": "hole", "plane": TOP, "points": [[-12, 0]], "through": True, "thread": "M3", "head": "csk"}],
        "pattern": [*box(), {"id": "H1", "type": "hole", "plane": TOP, "points": [[-15, -5]], "d": 3, "through": True},
                    {"id": "P1", "type": "pattern", "features": ["H1"], "kind": "linear", "dir": [1, 0, 0], "count": 6, "spacing": 6},
                    {"id": "P2", "type": "pattern", "features": ["H1"], "kind": "circular", "axis": {"o": [20, 10, 0], "d": [0, 0, 1]}, "count": 5}],
        "fillets": [*box(), {"id": "F1", "type": "fillet", "edges": [{"a": "E1:side:l1", "b": "E1:side:l2", "fp": [40, 0, 5]}], "r": 2},
                    {"id": "F2", "type": "fillet", "edges": [{"a": "E1:end", "b": "E1:side:l1", "fp": [20, 0, 10]}], "r": 1},
                    {"id": "C1", "type": "chamfer", "edges": [{"a": "E1:side:l3", "b": "E1:side:l4", "fp": [0, 20, 5]}], "d": 1}],
        "shell": [*box(), {"id": "H1", "type": "hole", "plane": TOP, "points": [[0, 0]], "d": 6, "through": True},
                  {"id": "SH", "type": "shell", "faces": [{"name": "E1:end", "fp": [20, 15, 10]}], "t": 2}],
        "split": [*box(), {"id": "H1", "type": "hole", "plane": TOP, "points": [[-10, 0], [10, 0]], "d": 4, "through": True},
                  {"id": "X1", "type": "split", "plane": {"datum": "YZ", "offset": 20}, "keep": "both"}],
        "rib": [*box(d=5), *wall, *rib],
        "plate171": plate()["features"],
    }


def built(features):
    """A fresh build (no cached step) -> (volume, faces, sorted face names, every step's ok and issues)."""
    doc._cache.clear()
    del doc._tess[:]
    r = doc.rebuild({"features": features})
    b = r["body"]
    names = sorted(tuple(sorted(f.get("names") or [f.get("name") or ""])) for f in b["faces"])  # ("": a face of no step)
    return b["volume"], len(b["faces"]), names, [(s["ok"], s["issues"]) for s in r["features"]]


@unittest.skipUnless(OCC, "OCP not installed")
class TestParallelBooleans(unittest.TestCase):
    def setUp(self):
        self.was = K.PARALLEL

    def tearDown(self):
        K.PARALLEL = self.was
        doc._cache.clear()
        del doc._tess[:]

    def both(self, make):
        out = []
        for on in (False, True):
            K.PARALLEL = on
            out.append(make())
        return out

    def test_parts_the_same_both_ways(self):
        for name, features in parts().items():
            with self.subTest(part=name):
                (v0, n0, f0, s0), (v1, n1, f1, s1) = self.both(lambda: built(features))
                self.assertTrue(all(ok for ok, _ in s0), s0)
                self.assertEqual(s1, s0)
                self.assertLessEqual(abs(v1 - v0), 1e-9 * abs(v0))
                self.assertEqual(n1, n0)
                self.assertEqual(f1, f0)
        v = built(parts()["plate171"])[0]  # (and right: 200 × 100 × 5 less 171 Ø3 holes, less the R2 rounding's corner)
        self.assertAlmostEqual(v, 200 * 100 * 5 - 171 * math.pi * 1.5 ** 2 * 5 - (4 - math.pi) * 200, delta=1e-3)

    def test_clashes_print_pieces_and_section_the_same(self):
        """The assembly's clashes (Common), the exact print split's pieces (Common / Cut / Fuse of many) and a
        drawing's section (Common): the same both ways."""
        a = doc.body_of({"features": parts()["holes"]}).body.shape
        b = K.placed(a, [1, 0, 0, 15, 0, 1, 0, 5, 0, 0, 1, 3, 0, 0, 0, 1])
        c0, c1 = self.both(lambda: K.interference([("A", a), ("B", b)]))
        self.assertEqual(c1, c0)
        self.assertTrue(c0 and c0[0]["volume"] > 100)
        cells = K.prisms([[[(0, 0), (20, 0), (20, 20), (0, 20)]]], -1, 11) + K.prisms([[[(20, 0), (25, 0), (25, 20), (20, 20)]]], 2, 8)
        void = K.prisms([[[(8, 8), (12, 8), (12, 12), (8, 12)]]], 4, 11)

        def pieces():
            fused = K.unified(K.boolean("fuse", cells[:1], cells[1:]))
            piece = K.boolean("cut", [K.boolean("common", [a], [fused])], void)
            return K.volume(piece), K.face_count(piece)
        (v0, n0), (v1, n1) = self.both(pieces)
        self.assertLessEqual(abs(v1 - v0), 1e-9 * v0)
        self.assertEqual(n1, n0)
        part = {"features": parts()["holes"]}

        def section():
            S._cache.clear()
            return doc.sheet(part, "medium", section=True)["geometry"]["views"]["Section"]
        s0, s1 = self.both(section)
        self.assertEqual(s1, s0)


if __name__ == "__main__":
    unittest.main()
