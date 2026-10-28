"""Imports (STL / OBJ / STEP meshes, DXF drawings) and the objects / shapes every part supports.

Run:  python -m unittest discover -s tests -v
"""
import io
import math
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np

from auto3d.export import build_solid, to_step, to_stl
from auto3d.export3mf import to_3mf
from auto3d.importers import ImportError_, orient, read_3mf, read_3mf_groups, read_dxf, read_mesh, slice_mesh, _dwg_converter, dwg_to_dxf
from auto3d.meshpart import mesh_model, solve_mesh
from auto3d.modeler import available
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


def mesh_volume(tris):
    """A closed mesh's volume (signed tetrahedra from the origin)."""
    return float(np.einsum("ij,ij->i", tris[:, 0], np.cross(tris[:, 1], tris[:, 2])).sum() / 6)


SAMPLES_IN = ROOT / "samples" / "ToImportToOurApp" / "mesh"
SAMPLES_OUT = ROOT / "samples" / "ExportFromOurApp"


class Test3MFImport(unittest.TestCase):
    """3MF (a zip with the model's XML) opens as a mesh quick part, like STL / OBJ: its objects, the build items'
    and components' transforms, the unit, base material colours; the 3MF Consortium's samples and our own export."""

    def test_box_quick_part(self):
        data = (SAMPLES_IN / "box.3mf").read_bytes()
        groups = read_3mf_groups(data)
        self.assertEqual([(g["name"], g["color"], len(g["triangles"])) for g in groups], [("object 1", None, 12)])
        m = mesh_model(data, "box.3mf")
        sol, solid = solve_mesh(m)
        self.assertTrue(sol["ok"], sol["issues"])
        self.assertAlmostEqual(solid.volume(), 10 * 20 * 30, places=4)
        self.assertEqual(mesh_stats(solid)[1], 0)
        self.assertEqual([round(sol["values"][k], 6) for k in ("size_x", "size_y", "size_z")], [10, 20, 30])

    def test_cube_gears_placed(self):
        """17 objects (a cube and 16 gears), each build item moved by its transform."""
        groups = read_3mf_groups((SAMPLES_IN / "cube_gears.3mf").read_bytes())
        self.assertEqual(len(groups), 17)
        self.assertEqual(groups[6]["name"], "cube 7")
        tris = np.concatenate([g["triangles"] for g in groups])
        self.assertEqual(len(tris), 25692)
        lo, hi = tris.reshape(-1, 3).min(0), tris.reshape(-1, 3).max(0)
        np.testing.assert_allclose(lo, [2.612, 2.617, 2.249], atol=0.01)  # (moved by -1.24, 1.20, -20.01)
        np.testing.assert_allclose(hi, [170.61, 127.72, 35.85], atol=0.01)
        self.assertGreater(mesh_volume(tris), 0)
        sol, _ = solve_mesh(mesh_model((SAMPLES_IN / "cube_gears.3mf").read_bytes(), "cube_gears.3mf"))
        self.assertTrue(sol["ok"], sol["issues"])

    def test_our_export_round_trip(self):
        """Our own 3MF exports read back: the plate (two colours) as its STL, the Frame (9 parts) its volume."""
        plate = read_3mf_groups((SAMPLES_OUT / "part_base_plate.3mf").read_bytes())
        self.assertEqual([g["color"] for g in plate], ["#d9dee6", "#d9822b"])
        v3 = mesh_volume(read_3mf((SAMPLES_OUT / "part_base_plate.3mf").read_bytes()))
        self.assertAlmostEqual(v3, mesh_volume(read_mesh((SAMPLES_OUT / "part_base_plate.stl").read_bytes(), "p.stl")), delta=0.5)
        self.assertAlmostEqual(v3, 37864.76, delta=37864.76 * 0.01)  # (the exact solid; the holes are faceted)
        frame = read_3mf((SAMPLES_OUT / "assembly_frame.3mf").read_bytes())
        self.assertAlmostEqual(mesh_volume(frame), 57697.89, delta=57697.89 * 0.01)
        # written by export3mf, read back: the same objects, colours and triangles
        box = read_mesh(box_stl(4, 3, 2), "b.stl")
        data = to_3mf([{"name": "body", "color": "#ffd400", "positions": box.ravel().tolist()},
                       {"name": "lid", "color": "#FF8800", "positions": (box + [0, 0, 2]).ravel().tolist()}], "Box")
        back = read_3mf_groups(data)
        self.assertEqual([(g["name"], g["color"], len(g["triangles"])) for g in back], [("body", "#ffd400", 12), ("lid", "#ff8800", 12)])
        np.testing.assert_allclose(back[1]["triangles"], box + [0, 0, 2])
        self.assertAlmostEqual(mesh_volume(read_mesh(data, "box.3mf")), 2 * 24, places=6)

    def test_components_units_and_errors(self):
        """An object made of another one moved (components), an item turned, the file in inches; bad files refused."""
        tri = '<vertices><vertex x="0" y="0" z="0"/><vertex x="1" y="0" z="0"/><vertex x="0" y="1" z="0"/></vertices><triangles><triangle v1="0" v2="1" v3="2"/></triangles>'
        model = ('<?xml version="1.0"?><model unit="inch" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"><resources>'
                 f'<object id="1" type="model"><mesh>{tri}</mesh></object>'
                 '<object id="2" type="model" name="pair"><components><component objectid="1"/><component objectid="1" transform="1 0 0 0 1 0 0 0 1 0 0 5"/></components></object>'
                 '</resources><build><item objectid="2" transform="0 1 0 -1 0 0 0 0 1 10 0 0"/></build></model>')
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("3D/other.model", model)  # (no _rels: the one .model file)
        groups = read_3mf_groups(buf.getvalue())
        self.assertEqual([g["name"] for g in groups], ["pair", "pair"])
        # turned 90° about z (x -> y), moved 10 along x, in inches
        np.testing.assert_allclose(groups[0]["triangles"][0], np.array([[10, 0, 0], [10, 1, 0], [9, 0, 0]]) * 25.4)
        np.testing.assert_allclose(groups[1]["triangles"][0][:, 2], [5 * 25.4] * 3)
        for bad in (b"not a zip", _zip({"3D/3dmodel.model": model.replace("<item objectid=\"2\"", "<item objectid=\"9\"")}), _zip({"a.txt": "x"})):
            with self.assertRaises(ImportError_):
                read_3mf(bad)


@unittest.skipUnless(available("occ"), "OCP not installed")
class Test3MFSolid(unittest.TestCase):
    def test_solid_from_a_3mf(self):
        """▣ Solid from a file takes a 3MF too: the mesh sewn into an exact solid, kept as a STEP (read back the same)."""
        from unittest import mock
        from auto3d.modeler import blobs, doc, kernel as K
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(blobs, "DIR", Path(tmp)):
            r = doc.import_solid({"blob": blobs.put((SAMPLES_IN / "box.3mf").read_bytes()), "name": "box.3mf"})
            self.assertAlmostEqual(r["volume"], 6000, delta=1e-6 * 6000)
            np.testing.assert_allclose(r["bbox"], [0, 0, 0, 10, 20, 30], atol=1e-6)
            part = {"features": [{"id": "F1", "type": "solid", "blob": r["blob"], "file": "box.3mf", "op": "add"}]}
            back = K.from_step(doc.export(part, "step"))
            self.assertAlmostEqual(K.volume(back), 6000, delta=1e-6 * 6000)


def _zip(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for k, v in files.items():
            z.writestr(k, v)
    return buf.getvalue()


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
        # a 3MF: a quick part of its mesh (it used to say "Unsupported file type .3mf")
        r = c.post("/api/import", data={"file": (io.BytesIO((SAMPLES_IN / "box.3mf").read_bytes()), "box.3mf")}, content_type="multipart/form-data").get_json()
        self.assertEqual((r["model"]["kind"], r["import_file"]["name"]), ("mesh", "box.3mf"))
        self.assertAlmostEqual(c.post("/api/solve", json={"model": r["model"], "values": {}}).get_json()["volume"], 6000, delta=1e-3)

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
