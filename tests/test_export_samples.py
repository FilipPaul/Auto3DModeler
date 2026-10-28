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
ORANGE, GREEN = "#d9822b", "#2e9e4f"  # the plate's painted top, the green post


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


def colours_of(g):
    """A glTF's materials' colours -> ["#rrggbb"]."""
    return ["#%02x%02x%02x" % tuple(round(c * 255) for c in m["pbrMetallicRoughness"]["baseColorFactor"][:3]) for m in g["materials"]]


def file_names(data, kind="step"):
    """The names in a STEP / IGES file: its products and placements, as a CAD program's tree lists them."""
    d, st = K._read_xcaf(data, kind)  # noqa: F841 — (the document holds the labels)
    out = []

    def walk(label):
        out.append(K._label_name(label))
        for comp, ref in K._components(st, label):
            out.append(K._label_name(comp))
            walk(ref)
    for label in K._free_labels(st):
        walk(label)
    return out


def painted(shape, colours):
    """The faces read back in each colour -> {colour: how many} — the orange one: [x, y, z] of its middle (one face)."""
    fm, out = K._face_map(shape), Counter(colours.values())
    at = [k for k, c in colours.items() if c == ORANGE]
    return {**out, **({ORANGE: [round(v, 6) + 0 for v in K._centroid(fm.FindKey(at[0] + 1))]} if len(at) == 1 else {})}


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
        self.assertEqual(colours_of(g), ["#c3c8cd", ORANGE])  # aluminium, the painted top
        g = glb(read("assembly_frame.glb"))
        nodes = g["nodes"]
        root = nodes[g["scenes"][g.get("scene", 0)]["nodes"][0]]
        kids = [nodes[k] for k in root["children"]]
        self.assertEqual(root["name"], "Frame")
        self.assertEqual([k["name"] for k in kids[:3]], ["Base plate-1", "Post pair-1", "Post pair-2"])
        self.assertEqual(len(kids), 7)  # the plate, the pair twice, 4 screws
        self.assertEqual([nodes[k]["name"] for k in kids[1]["children"]], ["Post-1", "Post-2"])  # nested
        self.assertEqual(sum(1 for n in nodes if "mesh" in n), 9)
        self.assertEqual([k["name"] for k in kids[3:]], [f"ISO 10642 M6×16-{i}" for i in range(1, 5)])  # (not "Ã—")
        self.assertTrue({ORANGE, GREEN} <= set(colours_of(g)))  # the painted top, the green post


class TestBom(unittest.TestCase):
    def test_rows(self):
        rows = list(csv.DictReader(io.StringIO(read("assembly_frame_BOM.csv").decode("utf-8-sig")), delimiter=";"))
        self.assertEqual([(r["Pos"], r["Qty"], r["Name"]) for r in rows], [("1", "1", "Base plate"), ("2", "4", "Post"), ("3", "4", "ISO 10642 M6×16")])
        self.assertEqual(rows[2]["Part number"], "ISO 10642 M6x16")
        self.assertEqual([r["Bought / made"] for r in rows], ["made", "made", "bought"])  # (aluminium, steel: not 3D printed)
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
        self.assertNotIn("PLA", frame)  # (the title block's material: "—"; the parts' are in the list)

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
        shape, colours, built = K.read_step_colours(read("part_base_plate.step"), summary=True)
        self.assertEqual(built, {"parts": 1, "placements": 1, "subs": 0})
        self.assertAlmostEqual(K.volume(shape), PLATE, delta=1e-3)
        self.assertEqual([round(v, 6) for v in K.bbox(shape)], [-40, -25, 0, 40, 25, 10])
        self.assertEqual(K.face_count(shape), 15)  # 6 sides, the Ø10 wall, 4 × (drill + cone)
        self.assertEqual(file_names(read("part_base_plate.step")), ["Base plate"])  # (exported after the assembly: still its own name)
        self.assertEqual(painted(shape, colours), {"#c3c8cd": 14, ORANGE: [0, 0, 10]})  # aluminium, the top painted
        shape, colours, how = K.read_iges(read("part_base_plate.igs"))
        self.assertEqual(how, "solid")
        self.assertAlmostEqual(K.volume(shape), PLATE, delta=1e-3)
        self.assertEqual(file_names(read("part_base_plate.igs"), "iges"), ["Base plate"])
        self.assertEqual(painted(shape, colours), {"#c3c8cd": 14, ORANGE: [0, 0, 10]})
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
        self.assertIn("ISO 10642 M6×16", [p["name"] for p in parts.values()])  # (not "Ã—")
        self.assertTrue(read("assembly_frame.step").isascii())  # (× as STEP's \X2\00D7\X0\, which every reader decodes)
        shape, colours, built = K.read_step_colours(read("assembly_frame.step"), summary=True)
        self.assertEqual(built, {"parts": 3, "placements": 9, "subs": 1})
        self.assertAlmostEqual(K.volume(shape), FRAME, delta=0.01)
        self.assertEqual(painted(shape, colours)[ORANGE], [0, 0, 10])  # the plate's painted top
        self.assertEqual(painted(shape, colours)[GREEN], 2 * 5)  # Post-2 of both pairs: 5 faces each (side, ends, the M5 drill: wall, tip)
        shape, colours, how = K.read_iges(read("assembly_frame.igs"))
        self.assertEqual((how, K.solids(shape)), ("solid", 9))
        self.assertAlmostEqual(K.volume(shape), FRAME, delta=0.01)
        self.assertEqual(file_names(read("assembly_frame.igs"), "iges"), ["Base plate-1", "Post pair-1/Post-1", "Post pair-1/Post-2", "Post pair-2/Post-1",
                                                                     "Post pair-2/Post-2", *[f"ISO 10642 M6x16-{i}" for i in range(1, 5)]])  # (IGES: ASCII)
        self.assertEqual(painted(shape, colours)[ORANGE], [0, 0, 10])
        self.assertEqual(painted(shape, colours)[GREEN], 2 * 5)


if __name__ == "__main__":
    unittest.main()
