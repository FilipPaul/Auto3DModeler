"""Imports (STL / OBJ / STEP meshes, DXF drawings) and the objects / shapes every part supports.

Run:  python -m unittest discover -s tests -v
"""
import io
import math
import tempfile
import unittest
from pathlib import Path

import numpy as np

from auto3d.export import build_solid, to_step, to_stl
from auto3d.importers import ImportError_, orient, read_dxf, read_mesh, slice_mesh, _dwg_converter, dwg_to_dxf
from auto3d.meshpart import mesh_model, solve_mesh
from auto3d.outline import outline_model, solve_outline
from auto3d.sketch import build_model
from auto3d.solver import solve
from test_design_print import mesh_stats

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "initial draft.pdf"
SAMPLE_MM3 = 809.0 * 1000  # the sample part: 809 cm³


def sample_files():
    model, _, _ = build_model(SAMPLE.read_bytes(), 0)
    solid = build_solid(solve(model), model["unit"])
    return to_stl(solid, model["unit"], "sample"), to_step(solid, model["unit"], "sample")


def box_stl(w, d, h):
    """A closed box as ASCII STL."""
    v = np.array([[0, 0, 0], [w, 0, 0], [w, d, 0], [0, d, 0], [0, 0, h], [w, 0, h], [w, d, h], [0, d, h]], float)
    faces = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6),
             (3, 0, 4), (3, 4, 7)]
    out = ["solid box"]
    for f in faces:
        out += ["facet normal 0 0 0", "outer loop", *[f"vertex {' '.join(map(str, v[i]))}" for i in f], "endloop", "endfacet"]
    return ("\n".join(out + ["endsolid box"])).encode()


class TestMeshImport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stl, cls.step = sample_files()

    def test_stl_and_step_slice_exactly(self):
        for name, data in (("p.stl", self.stl), ("p.step", self.step)):
            tris = orient(read_mesh(data, name))
            slabs, stepped = slice_mesh(tris)
            self.assertFalse(stepped, name)
            vol = sum((z1 - z0) * s.area for z0, z1, s in slabs)
            self.assertAlmostEqual(vol, SAMPLE_MM3, delta=SAMPLE_MM3 * 1e-6, msg=name)  # the two cutouts are holes

    def test_slanted_walls_are_stepped(self):
        # a square pyramid 20 x 20 x 10: V = 1333.3
        a = [[0, 0, 0], [20, 0, 0], [20, 20, 0], [0, 20, 0]]
        top = [10, 10, 10]
        tris = np.array([[a[0], a[2], a[1]], [a[0], a[3], a[2]]] + [[a[i], a[(i + 1) % 4], top] for i in range(4)], float)
        slabs, stepped = slice_mesh(orient(tris), layer=0.25)
        self.assertTrue(stepped)
        self.assertEqual(len(slabs), 40)
        vol = sum((z1 - z0) * s.area for z0, z1, s in slabs)
        self.assertAlmostEqual(vol, 4000 / 3, delta=4000 / 3 * 0.01)

    def test_mesh_part(self):
        m = mesh_model(box_stl(40, 20, 5), "box.stl")
        sol, solid = solve_mesh(m)
        self.assertTrue(sol["ok"], sol["issues"])
        self.assertAlmostEqual(solid.volume(), 40 * 20 * 5, places=4)
        self.assertEqual(mesh_stats(solid)[1], 0)
        self.assertEqual([round(sol["values"][k], 6) for k in ("size_x", "size_y", "size_z")], [40, 20, 5])
        # up axis: the 20 mm side up
        m["mesh_opts"]["up"] = "y"
        sol, solid = solve_mesh(m)
        self.assertEqual(round(sol["z_range"][1], 6), 20)
        # scale 50 % (uniform)
        m["mesh_opts"]["up"] = "z"
        sol, solid = solve_mesh(m, {"scale": 50})
        self.assertAlmostEqual(solid.volume(), 40 * 20 * 5 / 8, places=4)
        # extra objects: a hole through it and a post on top
        m["extras"] = [{"source": "circle", "x": 10, "y": 10, "w": 4, "h": 4, "z0": 0, "z1": 5, "op": "subtract", "name": "Hole"},
                       {"source": "rect", "x": 30, "y": 10, "w": 4, "h": 4, "z0": 5, "z1": 8, "op": "union", "name": "Post"}]
        sol, solid = solve_mesh(m)
        hole = math.pi * 4 * (1 - 0.0016)  # 32-gon
        self.assertAlmostEqual(solid.volume(), 4000 - hole * 5 + 16 * 3, delta=0.1)
        self.assertEqual(mesh_stats(solid)[1], 0)


class TestDxf(unittest.TestCase):
    def dxf(self, units=4):
        import ezdxf
        doc = ezdxf.new()
        doc.header["$INSUNITS"] = units
        msp = doc.modelspace()
        msp.add_lwpolyline([(0, 0), (100, 0), (100, 60), (0, 60)], close=True)
        msp.add_circle((30, 30), 10)
        msp.add_line((60, 20), (80, 20))
        msp.add_line((60, 40), (80, 40))
        msp.add_arc((60, 30), 10, 90, 270)
        msp.add_arc((80, 30), 10, 270, 90)
        msp.add_line((120, 0), (130, 10))  # open: reported, ignored
        buf = io.StringIO()
        doc.write(buf)
        return buf.getvalue().encode()

    def test_regions_and_units(self):
        polys, issues = read_dxf(self.dxf())
        self.assertEqual(len(polys), 1)
        self.assertEqual(len(polys[0]), 3)  # outline + circle + slot
        self.assertTrue(any(i["code"] == "open_contour" for i in issues))
        polys_cm, _ = read_dxf(self.dxf(units=5))  # drawn in cm -> 10x in mm
        xs = [p[0] for p in polys_cm[0][0]]
        self.assertAlmostEqual(max(xs) - min(xs), 1000, places=3)

    def test_dxf_outline_model_real_size(self):
        polys, _ = read_dxf(self.dxf())
        m = outline_model(polys, 100, 60, preset="solid", source="plate.dxf", space="mm")
        self.assertEqual([round(p["value"], 6) for p in m["params"]], [100, 60])
        sol, solid = solve_outline({**m, "preset_opts": {"thickness": 3, "offset": 0}})
        self.assertTrue(sol["ok"])
        area = 6000 - math.pi * 100 - (400 + math.pi * 100)
        self.assertAlmostEqual(solid.volume(), area * 3, delta=area * 3 * 1e-3)
        # y is up in a drawing: the circle (y = 30 of 60) stays in the middle, x = 30 stays left
        hole = [r for r in sol["loops"] if r["kind"] == "hole"]
        cx = [sum(p[0] for p in h["points"]) / len(h["points"]) for h in hole]
        self.assertTrue(any(abs(c - 30) < 0.5 for c in cx))

    def test_extras_on_a_preset(self):
        polys, _ = read_dxf(self.dxf())
        m = outline_model(polys, 100, 60, preset="solid", source="plate.dxf", space="mm")
        m["preset_opts"] = {"thickness": 3, "offset": 0}
        base = solve_outline(m)[1].volume()
        m["extras"] = [{"source": "rect", "x": 90, "y": 50, "w": 10, "h": 10, "z0": 3, "z1": 13, "op": "union", "name": "Post"}]
        sol, solid = solve_outline(m)
        self.assertAlmostEqual(solid.volume(), base + 100 * 10, delta=0.01)
        self.assertEqual(sol["z_range"], [0.0, 13.0])

    def test_dwg_needs_a_converter(self):
        if _dwg_converter() is not None:
            self.skipTest("a DWG converter is installed")
        with self.assertRaises(ImportError_) as ctx:
            dwg_to_dxf(b"AC1032....")
        self.assertIn("ODA File Converter", str(ctx.exception))


class TestServerImport(unittest.TestCase):
    def test_endpoints_and_pdf_objects(self):
        from server import app
        c = app.test_client()
        stl, _ = sample_files()
        r = c.post("/api/import", data={"file": (io.BytesIO(stl), "sample.stl")}, content_type="multipart/form-data").get_json()
        model = r["model"]
        self.assertEqual(model["kind"], "mesh")
        sol = c.post("/api/solve", json={"model": model, "values": {}}).get_json()
        self.assertTrue(sol["ok"], sol.get("issues"))
        self.assertAlmostEqual(sol["volume"], SAMPLE_MM3, delta=1)
        self.assertEqual(c.post("/api/import/register", json=r["import_file"]).get_json()["mesh_id"], model["mesh_id"])
        self.assertEqual(c.post("/api/export/step", json={"model": model, "values": {}}).status_code, 200)
        bad = c.post("/api/import", data={"file": (io.BytesIO(b"x"), "a.xyz")}, content_type="multipart/form-data")
        self.assertEqual(bad.status_code, 400)

        # a PDF part with a 2D shape cut from its profile and an extra 3D object (units: cm)
        pdf = c.get("/api/sample").get_json()["model"]
        base = c.post("/api/solve", json={"model": pdf, "values": {}}).get_json()["volume"]
        pdf["shapes"] = [{"kind": "circle", "x": 5, "y": 5, "w": 2, "h": 2, "op": "subtract"}]
        pdf["extras"] = [{"source": "rect", "x": 70, "y": 5, "w": 2, "h": 2, "z0": 1, "z1": 3, "op": "union", "name": "Post"}]
        sol = c.post("/api/solve", json={"model": pdf, "values": {}}).get_json()
        self.assertTrue(sol["ok"], sol["issues"])
        self.assertAlmostEqual(sol["volume"], base - math.pi * (1 - 0.0016) * 1 + 4 * 2, delta=0.01)
        self.assertIn(3.0, sol["z_levels"])


if __name__ == "__main__":
    unittest.main()
