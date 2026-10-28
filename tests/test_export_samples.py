"""samples/ExportFromOurApp (made by tools/make_export_samples.py through the app's own export paths) read back as other
programs read them: the base plate (80 × 50 × 10, a Ø10 hole, 4× M6 countersunk Ø12 × 90°) as STEP / IGES / STL / OBJ /
GLB / 3MF with its exact volume and size, and as a STEP with 🔩 real threads; the assembly "Frame" (the plate, the sub-assembly "Post pair" twice, 4 ISO
10642 screws) as a STEP tree, one IGES, a GLB of nested nodes, a 3MF and a BOM; the sheets as PDF (A4, true scale, the
callouts) and DXF (mm, layers, real dimensions); the project file opens (version 3, every kind of part).
The STEP / IGES checks are skipped without the CAD kernel.
"""
import csv
import io
import json
import math
import struct
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from unittest import mock

import ezdxf
import fitz
import numpy as np

from auto3d import importers
from auto3d.modeler import available
from auto3d.project import migrate

OCC = available("occ")
if OCC:
    from auto3d.modeler import blobs, doc, kernel as K

DIR = Path(__file__).resolve().parents[1] / "samples" / "ExportFromOurApp"
NS = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
# the plate less its Ø10 hole, the 4 tap drills (M6: Ø5) and the 4 countersinks (Ø12 × 90°: 3.5 deep, beyond the drill)
CSK = math.pi * 3.5 / 3 * (6 ** 2 + 6 * 2.5 + 2.5 ** 2) - math.pi * 2.5 ** 2 * 3.5
PLATE = 80 * 50 * 10 - math.pi * 5 ** 2 * 10 - 4 * math.pi * 2.5 ** 2 * 10 - 4 * CSK
POST = math.pi * 6 ** 2 * 40 - math.pi * 2.1 ** 2 * 12  # Ø12 × 40, a blind M5 (tap drill Ø4.2) 12 deep
SCREW = 600.641  # ISO 10642 M6×16 as the library draws it
FRAME = PLATE + 4 * POST + 4 * SCREW


def read(name):
    return (DIR / name).read_bytes()


def volume(tri):
    return float(np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum() / 6)


def closed(tri):
    """Every triangle edge shared by exactly two triangles."""
    keys = np.round(tri.astype(float), 4)
    edges = Counter(tuple(sorted((tuple(t[a]), tuple(t[b])))) for t in keys for a, b in ((0, 1), (1, 2), (2, 0)))
    return all(c == 2 for c in edges.values())


def glb(data):
    magic, version, length = struct.unpack("<4sII", data[:12])
    assert (magic, version, length) == (b"glTF", 2, len(data))
    n = struct.unpack("<I", data[12:16])[0]
    return json.loads(data[20:20 + n])


def dims_of(data):
    dx = ezdxf.read(io.StringIO(data.decode("utf-8")))
    dims = list(dx.modelspace().query("DIMENSION"))
    sizes = [round(dm.get_measurement() * dx.dimstyles.get(dm.dxf.dimstyle).dxf.dimlfac, 4) for dm in dims if dm.dxf.dimtype & 7 == 0]
    return dx, dims, sizes


class TestMeshes(unittest.TestCase):
    def test_stl(self):
        data = read("part_base_plate.stl")
        n = struct.unpack("<I", data[80:84])[0]
        self.assertEqual(len(data), 84 + 50 * n)  # binary STL
        tri = importers.read_stl(data)
        self.assertTrue(closed(tri))
        self.assertAlmostEqual(volume(tri), PLATE, delta=PLATE * 1e-3)  # (the round walls: facets)
        self.assertEqual([round(v, 4) for v in (*tri.reshape(-1, 3).min(0), *tri.reshape(-1, 3).max(0))], [-40, -25, 0, 40, 25, 10])

    def test_obj(self):
        tri = importers.read_obj(read("part_base_plate.obj").decode("utf-8"))
        self.assertTrue(closed(tri))
        self.assertAlmostEqual(volume(tri), PLATE, delta=PLATE * 1e-3)
        self.assertIn("o Base_plate", read("part_base_plate.obj").decode("utf-8"))

    def test_3mf(self):
        def model(name):
            root = ET.fromstring(zipfile.ZipFile(io.BytesIO(read(name))).read("3D/3dmodel.model"))
            self.assertEqual(root.get("unit"), "millimeter")
            tri = []
            for o in root.findall(".//m:object", NS):
                v = np.array([[float(q.get(k)) for k in "xyz"] for q in o.findall(".//m:vertex", NS)])
                tri += [v[[int(t.get(k)) for k in ("v1", "v2", "v3")]] for t in o.findall(".//m:triangle", NS)]
            return root, np.array(tri)
        root, tri = model("part_base_plate.3mf")
        self.assertIn("#D9822BFF", [b.get("displaycolor") for b in root.findall(".//m:base", NS)])  # the painted top face
        self.assertTrue(closed(tri))  # (an object per colour: together closed)
        self.assertAlmostEqual(volume(tri), PLATE, delta=PLATE * 1e-3)
        root, tri = model("assembly_frame.3mf")
        self.assertAlmostEqual(volume(tri), FRAME, delta=FRAME * 2e-3)
        self.assertEqual([round(v, 3) for v in (*tri.reshape(-1, 3).min(0), *tri.reshape(-1, 3).max(0))], [-40, -25, -6, 40, 25, 50])

    def test_glb(self):
        g = glb(read("part_base_plate.glb"))
        self.assertEqual([n.get("name") for n in g["nodes"]], ["Base plate"])
        self.assertGreater(g["materials"][0]["pbrMetallicRoughness"]["metallicFactor"], 0.5)  # aluminium
        pos = [g["accessors"][p["attributes"]["POSITION"]] for p in g["meshes"][0]["primitives"]]
        span = [round(max(a["max"][k] for a in pos) - min(a["min"][k] for a in pos), 6) for k in range(3)]
        self.assertEqual(span, [0.08, 0.01, 0.05])  # metres, Y up
        g = glb(read("assembly_frame.glb"))
        nodes = g["nodes"]
        root = nodes[g["scenes"][g.get("scene", 0)]["nodes"][0]]
        kids = [nodes[k] for k in root["children"]]
        self.assertEqual(root["name"], "Frame")
        self.assertEqual([k["name"] for k in kids[:3]], ["Base plate-1", "Post pair-1", "Post pair-2"])
        self.assertEqual(len(kids), 7)  # the plate, the pair twice, 4 screws
        self.assertEqual([nodes[k]["name"] for k in kids[1]["children"]], ["Post-1", "Post-2"])  # nested
        self.assertEqual(sum(1 for n in nodes if "mesh" in n), 9)


class TestBom(unittest.TestCase):
    def test_rows(self):
        rows = list(csv.DictReader(io.StringIO(read("assembly_frame_BOM.csv").decode("utf-8-sig")), delimiter=";"))
        self.assertEqual([(r["Pos"], r["Qty"], r["Name"]) for r in rows], [("1", "1", "Base plate"), ("2", "4", "Post"), ("3", "4", "ISO 10642 M6×16")])
        self.assertEqual(rows[2]["Part number"], "ISO 10642 M6x16")
        self.assertEqual(rows[2]["Bought / made"], "bought")
        self.assertAlmostEqual(float(rows[0]["Mass each (g)"].replace(",", ".")), PLATE / 1000 * 2.7, delta=0.01)  # aluminium


class TestSheets(unittest.TestCase):
    def test_pdf(self):
        mm = 72 / 25.4
        page = fitz.open(stream=read("sheet_base_plate.pdf"), filetype="pdf")[0]
        self.assertEqual((round(page.rect.width / mm), round(page.rect.height / mm)), (297, 210))  # A4 landscape, true scale
        text = page.get_text()
        for s in ("4× M6 ⌵ Ø12 × 90°", "Ø10 THRU", "1:1", "aluminium", "ISO 2768-m"):
            self.assertIn(s, text)
        frame = fitz.open(stream=read("sheet_frame.pdf"), filetype="pdf")[0].get_text()
        for s in ("Post pair", "ISO 10642 M6x16", "1:2"):  # the parts list, its scale
            self.assertIn(s, frame)

    def test_dxf(self):
        dx, dims, sizes = dims_of(read("sheet_base_plate.dxf"))
        self.assertEqual(dx.header["$INSUNITS"], 4)  # mm
        self.assertTrue({"visible", "hidden", "dims", "text", "frame"} <= {e.dxf.layer for e in dx.modelspace()})
        self.assertTrue({80, 50, 10, 60, 34} <= set(sizes), sizes)  # true sizes (the paper × DIMLFAC)
        self.assertIn("4× M6 ⌵ Ø12 × 90°", [dm.dxf.text for dm in dims])
        _, _, sizes = dims_of(read("sheet_frame.dxf"))
        self.assertTrue({80, 50, 56} <= set(sizes), sizes)


class TestProject(unittest.TestCase):
    def test_opens(self):
        p = migrate(json.loads(read("project_frame.a3d.json")))
        self.assertEqual((p["version"], p["project_name"]), (3, "Frame"))
        self.assertEqual(Counter(x["kind"] for x in p["parts"]), {"model": 3, "assembly": 2, "sheet": 2})
        plate = next(x for x in p["parts"] if x["name"] == "Base plate")["model"]
        hole = [f for f in plate["features"] if f.get("thread")][0]
        self.assertEqual((hole["thread"], hole["head"], hole["head_d"], len(hole["points"])), ("M6", "csk", 12, 4))
        if OCC:  # the saved steps rebuild the same plate
            self.assertAlmostEqual(doc.rebuild(plate)["body"]["volume"], PLATE, delta=1e-3)


@unittest.skipUnless(OCC, "OCP not installed")
class TestCad(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.blobs = mock.patch.object(blobs, "DIR", Path(self.tmp.name))
        self.blobs.start()

    def tearDown(self):
        self.blobs.stop()
        self.tmp.cleanup()

    def test_part(self):
        shape, _, built = K.read_step_colours(read("part_base_plate.step"), summary=True)
        self.assertEqual(built, {"parts": 1, "placements": 1, "subs": 0})
        self.assertAlmostEqual(K.volume(shape), PLATE, delta=1e-3)
        self.assertEqual([round(v, 6) for v in K.bbox(shape)], [-40, -25, 0, 40, 25, 10])
        self.assertEqual(K.face_count(shape), 15)  # 6 sides, the Ø10 wall, 4 × (drill + cone)
        shape, _, how = K.read_iges(read("part_base_plate.igs"))
        self.assertEqual(how, "solid")
        self.assertAlmostEqual(K.volume(shape), PLATE, delta=1e-3)
        # 🔩 real threads: the grooves cut into the 4 holes, as the project's plate rebuilds with them
        shape = K.from_step(read("part_base_plate_real_threads.step"))
        self.assertEqual(K.solids(shape), 1)
        plate = next(x for x in migrate(json.loads(read("project_frame.a3d.json")))["parts"] if x["name"] == "Base plate")["model"]
        real = doc.rebuild({**plate, "threads": "real"})["body"]["volume"]
        self.assertAlmostEqual(K.volume(shape), real, delta=1e-2)
        self.assertTrue(PLATE - 120 < real < PLATE - 60, real)  # (4 × M6 × 10: about 94 mm³ of grooves)

    def test_assembly(self):
        imp = doc.import_assembly({"blob": blobs.put(read("assembly_frame.step")), "name": "assembly_frame.step"})
        parts, asms = imp["parts"], imp["assemblies"]
        vols = sorted(p["volume"] for p in parts.values())
        for got, want in zip(vols, sorted([PLATE, POST, SCREW])):
            self.assertAlmostEqual(got, want, delta=1e-2)
        root = asms[imp["root"]]
        self.assertEqual(root["name"], "Frame")
        names = lambda k: (parts.get(k) or asms.get(k))["name"]  # noqa: E731
        self.assertEqual(Counter(names(i["ref"]) for i in root["instances"][:3]), {"Base plate": 1, "Post pair": 2})
        self.assertEqual(len(root["instances"]), 7)
        pair = asms[root["instances"][1]["ref"]]
        self.assertEqual([names(i["ref"]) for i in pair["instances"]], ["Post", "Post"])  # one part, placed twice
        self.assertEqual(pair["instances"][1].get("colour"), "#2e9e4f")
        self.assertEqual([round(v, 6) for v in pair["instances"][1]["matrix"][12:15]], [40, 0, 0])
        shape, _, built = K.read_step_colours(read("assembly_frame.step"), summary=True)
        self.assertEqual(built, {"parts": 3, "placements": 9, "subs": 1})
        self.assertAlmostEqual(K.volume(shape), FRAME, delta=0.01)
        shape, _, how = K.read_iges(read("assembly_frame.igs"))
        self.assertEqual((how, K.solids(shape)), ("solid", 9))
        self.assertAlmostEqual(K.volume(shape), FRAME, delta=0.01)


if __name__ == "__main__":
    unittest.main()
