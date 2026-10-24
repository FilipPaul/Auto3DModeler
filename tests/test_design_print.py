"""3D design layers (emboss / engrave / cut through), exports and printer splitting.

Run:  python -m unittest discover -s tests -v
"""
import base64
import io
import struct
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from auto3d.design import trace_image
from auto3d.export import build_solid, to_step, to_stl
from auto3d.printing import BUILTIN_PRINTERS, PrinterStore, plan
from auto3d.sketch import build_model
from auto3d.solver import solve

SAMPLE = Path(__file__).resolve().parent.parent / "initial draft.pdf"


def mesh_stats(solid):
    """(volume, number of unmatched directed edges) of the triangle mesh; 0 unmatched = watertight."""
    tris, _ = solid.triangles()
    edges, vol = Counter(), 0.0
    for a, b, c in tris:
        vol += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0])
                + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6
        for p, q in ((a, b), (b, c), (c, a)):
            edges[(tuple(round(v, 7) for v in p), tuple(round(v, 7) for v in q))] += 1
    bad = sum(1 for (p, q), k in edges.items() if edges.get((q, p), 0) != k)
    return vol, bad


def grid(op="emboss", depth=0.2, use="lines", pattern="square", **mask):
    return {"id": f"{op}-{pattern}", "name": f"{op} {pattern}", "face": "top", "op": op, "depth": depth, "margin": 0.5,
            "mask": {"kind": "face", **mask}, "fill": {"pattern": pattern, "sx": 1, "width": 0.1, "use": use}}


class DesignLayerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model, _, _ = build_model(SAMPLE.read_bytes())
        cls.unit = cls.model["unit"]
        cls.sol = solve(cls.model)
        cls.base_volume = build_solid(cls.sol, cls.unit).volume()

    def solid(self, *layers):
        return build_solid(self.sol, self.unit, list(layers))

    def test_base_volume(self):
        self.assertAlmostEqual(self.base_volume, 787 * 11 / 10 - 29.8 * 1.5 - 2 * 4 * 1.5, places=6)

    def test_emboss_adds_engrave_removes_material(self):
        emb = self.solid(grid("emboss", 0.2))
        eng = self.solid(grid("engrave", 0.2))
        self.assertGreater(emb.volume(), self.base_volume)
        self.assertLess(eng.volume(), self.base_volume)
        self.assertAlmostEqual(emb.volume() - self.base_volume, self.base_volume - eng.volume(), places=6)
        self.assertEqual(emb.z_range(), (0.0, 1.2))

    def test_all_operations_are_watertight(self):
        layers = [
            grid("emboss", 0.2),
            {"id": "r", "name": "Pocket", "face": "top", "op": "engrave", "depth": 0.3,
             "mask": {"kind": "rect", "x": 30, "y": 5, "w": 8, "h": 4}, "fill": {"pattern": "solid"}},
            {"id": "h", "name": "Lattice", "face": "top", "op": "cut", "mask": {"kind": "ellipse", "x": 55, "y": 5.5, "w": 12, "h": 7},
             "fill": {"pattern": "hex", "sx": 1.2, "width": 0.25, "use": "cells"}},
            {"id": "b", "name": "Back", "face": "bottom", "op": "emboss", "depth": 0.1,
             "mask": {"kind": "ellipse", "x": 10, "y": 6, "w": 5, "h": 3}, "fill": {"pattern": "solid"}},
        ]
        s = self.solid(*layers)
        vol, bad = mesh_stats(s)
        self.assertEqual(bad, 0, "mesh is not watertight")
        self.assertAlmostEqual(vol, s.volume(), delta=s.volume() * 1e-6)
        self.assertEqual(s.issues, [])

    def test_every_pattern_builds_a_valid_mesh(self):
        for pat in ("square", "rect", "diamond", "triangle", "hex", "dots", "columns", "radial"):
            with self.subTest(pattern=pat):
                s = self.solid(grid("engrave", 0.2, pattern=pat))
                vol, bad = mesh_stats(s)
                self.assertEqual(bad, 0)
                self.assertLess(s.volume(), self.base_volume)

    def test_guide_layer_adds_no_geometry(self):
        s = self.solid(grid("guide"))
        self.assertAlmostEqual(s.volume(), self.base_volume, places=9)
        self.assertTrue(s.guide_rings())

    def test_invalid_layers_are_reported(self):
        too_deep = self.solid(grid("engrave", 1.0))
        self.assertTrue(any("Cut through" in i["message"] and i["severity"] == "error" for i in too_deep.issues))
        zero = self.solid(grid("emboss", 0))
        self.assertTrue(any(i["severity"] == "error" for i in zero.issues))
        outside = self.solid({"id": "o", "name": "Off part", "op": "emboss", "depth": 0.1, "face": "top",
                              "mask": {"kind": "rect", "x": 200, "y": 200, "w": 2, "h": 2}, "fill": {"pattern": "solid"}})
        self.assertTrue(any("no effect" in i["message"] for i in outside.issues))
        thin = self.solid({**grid("emboss", 0.1), "fill": {"pattern": "square", "sx": 1, "width": 0.01}})
        self.assertTrue(any("thinner than" in i["message"] for i in thin.issues))

    def test_step_with_design_is_one_solid_per_piece(self):
        text = to_step(self.solid(grid("emboss", 0.2)), self.unit).decode()
        self.assertEqual(text.count("MANIFOLD_SOLID_BREP"), 1)
        # a cut through the full width separates the part into two bodies
        split = {"id": "c", "name": "Slot", "face": "top", "op": "cut",
                 "mask": {"kind": "rect", "x": 60, "y": 5.5, "w": 1, "h": 20}, "fill": {"pattern": "solid"}}
        text = to_step(self.solid(split), self.unit).decode()
        self.assertEqual(text.count("MANIFOLD_SOLID_BREP"), 2)

    def test_stl_is_in_mm(self):
        data = to_stl(self.solid(grid("emboss", 0.2)), self.unit)
        n = struct.unpack("<I", data[80:84])[0]
        zs = {round(struct.unpack("<f", data[84 + 50 * i + 12 + 4 * k + 8: 84 + 50 * i + 12 + 4 * k + 12])[0], 4)
              for i in range(n) for k in (0, 3, 6)}
        self.assertEqual(max(zs), 12.0)  # 1 cm + 2 mm emboss


class TraceTest(unittest.TestCase):
    def test_trace_transparent_logo(self):
        from PIL import Image, ImageDraw
        im = Image.new("RGBA", (200, 100), (0, 0, 0, 0))
        ImageDraw.Draw(im).rectangle((20, 20, 79, 79), fill=(0, 0, 0, 255))
        buf = io.BytesIO()
        im.save(buf, "PNG")
        res = trace_image("data:image/png;base64," + base64.b64encode(buf.getvalue()).decode())
        self.assertAlmostEqual(res["aspect"], 2.0)
        self.assertEqual(len(res["polygons"]), 1)
        xs = [p[0] for p in res["polygons"][0][0]]
        self.assertAlmostEqual(min(xs), -0.4, delta=0.01)
        self.assertAlmostEqual(max(xs), -0.1, delta=0.01)


class PrintingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        model, _, _ = build_model(SAMPLE.read_bytes())
        cls.unit = model["unit"]
        cls.solid = build_solid(solve(model), cls.unit)

    def test_builtin_printers(self):
        names = {p["name"]: (p["x"], p["y"], p["z"]) for p in BUILTIN_PRINTERS}
        self.assertEqual(names["Creality Ender-3 Pro"], (220, 220, 250))
        self.assertEqual(names["Bambu Lab P1S"], (256, 256, 256))

    def test_split_fits_every_printer(self):
        for pr in BUILTIN_PRINTERS:
            with self.subTest(printer=pr["name"]):
                r = plan(self.solid, self.unit, pr, margin_mm=5, split=True)
                self.assertFalse(r["fits"])
                self.assertEqual(len(r["pieces"]), 4)
                usable = pr["x"] - 10
                for p in r["pieces"]:
                    self.assertLessEqual(p["size_mm"][0], usable + 1e-6)
                    self.assertNotEqual(p["orientation"], "too big")
                total = sum(p["solid"].volume() for p in r["pieces"])
                self.assertAlmostEqual(total, self.solid.volume(), places=6)
                for p in r["pieces"]:
                    self.assertEqual(mesh_stats(p["solid"])[1], 0)

    def test_big_printer_fits_whole_part(self):
        r = plan(self.solid, self.unit, {"id": "big", "name": "Big", "x": 1000, "y": 400, "z": 300}, split=True)
        self.assertTrue(r["fits"])
        self.assertEqual(len(r["pieces"]), 1)

    def test_too_tall(self):
        r = plan(self.solid, self.unit, {"id": "flat", "name": "Flat", "x": 1000, "y": 1000, "z": 5}, split=True)
        self.assertTrue(any(i["severity"] == "error" for i in r["issues"]))
        self.assertEqual(r["pieces"], [])

    def test_custom_printer_store(self):
        with tempfile.TemporaryDirectory() as d:
            store = PrinterStore(Path(d) / "printers.json")
            p = store.save({"name": "Prusa MK4", "x": 250, "y": 210, "z": 220})
            self.assertEqual(store.get(p["id"])["x"], 250)
            self.assertEqual(len(store.all()), len(BUILTIN_PRINTERS) + 1)
            with self.assertRaises(ValueError):
                store.save({"name": "Bad", "x": "abc", "y": 1, "z": 1})
            with self.assertRaises(ValueError):
                store.delete(BUILTIN_PRINTERS[0]["id"])
            store.delete(p["id"])
            self.assertEqual(len(store.all()), len(BUILTIN_PRINTERS))


if __name__ == "__main__":
    unittest.main()
