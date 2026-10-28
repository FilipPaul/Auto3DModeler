"""Exchange formats for other CAD programs (SolidWorks, CATIA, Solid Edge …) beside STEP: IGES in and out (a part, an
assembly as one file; surfaces-only files sewn into a solid, or a reference body when they do not close); a drawing
sheet as a DXF (the paper 1:1, a layer per kind, real dimensions) and its PDF in true scale; glTF (.glb: a node per
placed part, names, PBR materials) and OBJ for viewers and rendering.
The IGES / glTF / OBJ tests are skipped without the CAD kernel.
"""
import io
import json
import math
import struct
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

import ezdxf

from auto3d.modeler import available
from test_modeler_kernel import watertight
from test_step_assembly import box, machine

OCC = available("occ")
if OCC:
    from auto3d.modeler import blobs, doc, kernel as K


def plate_with_hole():
    """A 40 × 20 × 10 plate with a Ø8 hole through it: 8000 − π·4²·10 mm³."""
    top = {"face": {"name": "E1:end"}, "frame": {"o": [20, 10, 10], "x": [1, 0, 0], "n": [0, 0, 1]}}
    return box(40, 20, 10) + [{"id": "H1", "type": "hole", "plane": top, "points": [[0, 0]], "d": 8, "through": True}]


PLATE_HOLE = 8000 - math.pi * 16 * 10


@unittest.skipUnless(OCC, "OCP not installed")
class TestIges(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.blobs = mock.patch.object(blobs, "DIR", Path(self.tmp.name))
        self.blobs.start()

    def tearDown(self):
        self.blobs.stop()
        self.tmp.cleanup()

    def imported(self, data, name="part.igs"):
        return doc.import_solid({"blob": blobs.put(data), "name": name})

    def solid_step(self, r, op=None):
        return doc.rebuild({"features": [{"id": "F1", "type": "solid", "blob": r["blob"], "file": "part.igs", "op": op or r.get("op") or "add"}]})

    def test_part_export_reads_back_the_same_solid(self):
        part = {"features": plate_with_hole()}
        self.assertAlmostEqual(doc.rebuild(part)["body"]["volume"], PLATE_HOLE, delta=1e-6)
        data = doc.export(part, "iges")
        text = data.decode("latin-1")
        self.assertTrue(text.startswith(" " * 72 + "S0000001"))  # (fixed 80-column records: Start … Terminate)
        self.assertIn("T0000001", text[-90:])
        self.assertIn("MM", text)
        r = self.imported(data)
        self.assertEqual(r["iges"], "solid")
        self.assertNotIn("op", r)
        self.assertAlmostEqual(r["volume"], PLATE_HOLE, delta=PLATE_HOLE * 1e-6)
        self.assertEqual(r["faces"], 7)  # 6 sides + the hole's wall
        built = self.solid_step(r)
        self.assertTrue(built["ok"], built["features"])
        self.assertTrue(watertight(built["body"]))
        # the imported solid as a STEP: written and read back, the same volume
        st = doc.body_of({"features": [{"id": "F1", "type": "solid", "blob": r["blob"], "op": "add"}]})
        self.assertAlmostEqual(K.volume(K.from_step(K.to_step(st.body.shape))), PLATE_HOLE, delta=PLATE_HOLE * 1e-6)

    def test_assembly_as_one_iges(self):
        data = doc.assembly_step(tree=machine(), name="Machine", fmt="iges")
        shape, _, how = K.read_iges(data)
        self.assertEqual(how, "solid")
        self.assertEqual(K.solids(shape), 4)  # every placement, as placed
        self.assertAlmostEqual(K.volume(shape), 2 * 8000 + 2 * 3000, delta=1e-6)
        bb = K.bbox(shape)
        self.assertAlmostEqual(bb[3], 100, delta=1e-6)  # the turned Post: 90° about z, 100 along x (x from 90 to 100)
        self.assertIn("Plate", data.decode("latin-1"))  # the parts' names
        # the flat form (placed bodies, no tree) too
        flat = doc.assembly_step([{"part": {"features": box(40, 20, 10)}, "matrix": None}], fmt="iges")
        self.assertAlmostEqual(K.volume(K.read_iges(flat)[0]), 8000, delta=1e-6)

    def test_surfaces_only_are_sewn_into_a_solid(self):
        st = doc.body_of({"features": plate_with_hole()})
        data = K.to_iges(st.body.shape, surfaces=True)
        self.assertEqual(K.solids(K.read_step_colours(data, kind="iges")[0]), 0)  # (no solid in the file)
        r = self.imported(data)
        self.assertEqual(r["iges"], "sewn")
        self.assertIn("sewn", r["warning"])
        self.assertAlmostEqual(r["volume"], PLATE_HOLE, delta=PLATE_HOLE * 1e-4)
        built = self.solid_step(r)
        self.assertTrue(built["ok"], built["features"])
        self.assertTrue(watertight(built["body"]))

    def test_open_surfaces_come_in_as_a_reference_body(self):
        st = doc.body_of({"features": box(40, 20, 10)})
        fm = K._face_map(st.body.shape)
        lid_off = K.compound([fm.FindKey(k) for k in range(1, fm.Extent())])  # 5 of the 6 faces: an open box
        r = self.imported(K.to_iges(lid_off, surfaces=True))
        self.assertEqual(r["iges"], "surfaces")
        self.assertEqual(r["op"], "ref")
        self.assertIn("reference body", r["warning"])
        built = self.solid_step(r)
        self.assertIsNone(built["body"])  # not part of the solid …
        self.assertEqual([x["id"] for x in built["refs"]], ["F1"])  # … shown to build around
        self.assertEqual(len(built["refs"][0]["faces"]), 5)

    def test_errors(self):
        with self.assertRaises(K.KernelError):
            self.imported(b"not an IGES file at all", "broken.iges")
        with self.assertRaises(K.KernelError):  # nothing to export yet
            doc.export({"features": []}, "iges")
        with self.assertRaises(K.KernelError):
            doc.assembly_step(tree=machine(), fmt="x_t")
        with self.assertRaises(K.KernelError):
            doc.assembly_step(tree={"root": "A1", "parts": {}, "assemblies": {"A1": {"name": "Empty", "instances": []}}}, fmt="iges")


def glb(data):
    """A binary glTF -> (its JSON, its binary chunk), checking the header: magic, version 2, the whole length."""
    magic, version, length = struct.unpack("<4sII", data[:12])
    assert (magic, version, length) == (b"glTF", 2, len(data)), (magic, version, length, len(data))
    n, kind = struct.unpack("<I4s", data[12:20])
    assert kind == b"JSON"
    m, kind2 = struct.unpack("<I4s", data[20 + n:28 + n])
    assert kind2 == b"BIN\x00"
    return json.loads(data[20:20 + n]), data[28 + n:28 + n + m]


def obj_triangles(data):
    """An OBJ's triangles (n, 3, 3) and its faces' corner indices (0-based)."""
    import numpy as np
    v, f = [], []
    for line in data.decode("utf-8").splitlines():
        if line.startswith("v "):
            v.append([float(x) for x in line.split()[1:4]])
        elif line.startswith("f "):
            f.append([int(c.split("/")[0]) - 1 for c in line.split()[1:4]])
    return np.asarray(v)[np.asarray(f)], f


@unittest.skipUnless(OCC, "OCP not installed")
class TestGltfObj(unittest.TestCase):
    def test_part_glb_in_its_colour_and_finish(self):
        part = {"features": plate_with_hole(), "material": "aluminium"}
        js, binary = glb(doc.export(part, "glb", "Plate"))
        self.assertEqual(js["asset"]["version"], "2.0")
        self.assertEqual([n.get("name") for n in js["nodes"]], ["Plate"])
        mat = js["materials"][0]["pbrMetallicRoughness"]
        self.assertAlmostEqual(mat["metallicFactor"], 0.9, places=5)  # aluminium: metal, a little rough
        self.assertAlmostEqual(mat["roughnessFactor"], 0.38, places=5)
        self.assertEqual([round(c * 255) for c in mat["baseColorFactor"][:3]], [0xc3, 0xc8, 0xcd])  # (its colour)
        # metres, Y up: 40 × 20 × 10 mm -> x 0.04, height (y) 0.01, depth (z) 0.02
        pos = [js["accessors"][p["attributes"]["POSITION"]] for p in js["meshes"][0]["primitives"]]
        lo = [min(a["min"][k] for a in pos) for k in range(3)]
        hi = [max(a["max"][k] for a in pos) for k in range(3)]
        self.assertEqual([round(h - l, 6) for l, h in zip(lo, hi)], [0.04, 0.01, 0.02])
        self.assertEqual(len(binary), js["buffers"][0]["byteLength"])

    def test_assembly_glb_a_node_per_placed_part(self):
        tree = machine()
        tree["parts"]["P2"]["material"] = "brass"
        js, _ = glb(doc.assembly_step(tree=tree, name="Machine", fmt="glb"))
        nodes = js["nodes"]
        root = nodes[js["scenes"][js.get("scene", 0)]["nodes"][0]]
        self.assertEqual(root["name"], "Machine")
        self.assertEqual([nodes[k]["name"] for k in root["children"]], ["Plate-1", "Post-1", "Sub-1"])
        sub = nodes[root["children"][2]]
        self.assertEqual([nodes[k]["name"] for k in sub["children"]], ["Post-1", "Plate-1"])  # (nested, as in the file)
        self.assertEqual(sum(1 for n in nodes if "mesh" in n), 4)  # every placement
        post = nodes[root["children"][1]]
        self.assertEqual([round(v, 6) for v in post["translation"]], [0.1, 0, 0])  # 100 mm along x, in metres
        metals = sorted(round(m["pbrMetallicRoughness"]["metallicFactor"], 2) for m in js["materials"])
        self.assertIn(0.95, metals)  # brass shines
        self.assertIn(0.05, metals)  # a plastic does not
        colours = {tuple(round(c * 255) for c in m["pbrMetallicRoughness"]["baseColorFactor"][:3]) for m in js["materials"]}
        self.assertIn((255, 0, 0), colours)  # Plate's own red
        self.assertIn((0, 255, 0), colours)  # the turned Post's instance colour

    def test_obj_mesh(self):
        data = doc.export({"features": plate_with_hole()}, "obj", "Plate with hole")
        text = data.decode("utf-8")
        self.assertIn("o Plate_with_hole", text)
        tri, faces = obj_triangles(data)
        import numpy as np
        vol = float(np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum() / 6)
        self.assertAlmostEqual(vol, PLATE_HOLE, delta=PLATE_HOLE * 2e-3)  # (the hole's wall: facets)
        edges = Counter(tuple(sorted((f[a], f[b]))) for f in faces for a, b in ((0, 1), (1, 2), (2, 0)))
        self.assertTrue(all(c == 2 for c in edges.values()))  # watertight: corners shared, every edge twice
        self.assertEqual(text.count("\nvn "), len(faces))

    def test_errors(self):
        with self.assertRaises(K.KernelError):  # a glTF of an assembly needs its tree
            doc.assembly_step([{"part": {"features": box(10, 10, 10)}, "matrix": None}], fmt="glb")
        with self.assertRaises(K.KernelError):
            doc.assembly_step(tree={"root": "A1", "parts": {}, "assemblies": {"A1": {"name": "Empty", "instances": []}}}, fmt="glb")
        with self.assertRaises(K.KernelError):
            doc.export({"features": []}, "glb")
        with self.assertRaises(K.KernelError):
            doc.export({"features": box(10, 10, 10)}, "x_b")


# a sheet as the editor draws it (sheet.js svg(true)): A4 landscape, a 1:2 front view of a 40 × 20 plate with a Ø8 hole
# (hidden lines, a section's hatching), its name, a dimension drawn (left out: it comes from the list), the title block
SHEET_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="297mm" height="210mm" viewBox="0 0 297 210" font-family="Helvetica">
<rect x="0" y="0" width="297" height="210" fill="#fff"/>
<rect x="10" y="10" width="277" height="190" fill="none" stroke="#000" stroke-width="0.5"/>
<g data-view="Front" class="sh-view">
<line x1="42" y1="98" x2="48" y2="92" stroke="#000" stroke-width="0.18"/><line x1="44" y1="98" x2="50" y2="92" stroke="#000" stroke-width="0.18"/>
<polyline points="58,100 58,90" fill="none" stroke="#666" stroke-width="0.25" stroke-dasharray="1.5 1"/>
<polyline points="62,100 62,90" fill="none" stroke="#666" stroke-width="0.25" stroke-dasharray="1.5 1"/>
<polyline points="50,100 70,100 70,90 50,90 50,100" fill="none" stroke="#000" stroke-width="0.5" stroke-linejoin="round"/>
<text font-family="Helvetica" x="60" y="118" font-size="3.5" text-anchor="middle" fill="#334">Front</text></g>
<g data-dim="d1" class="sh-dim"><line x1="50" y1="101" x2="50" y2="109.5" stroke="#1b3a8a" stroke-width="0.15"/>
<path d="M50,108 L52.2,107.3 L52.2,108.7 Z" fill="#1b3a8a"/><text font-family="Helvetica" x="60" y="107.1" font-size="3.2">40</text></g>
<g class="sh-title"><rect x="137" y="155" width="150" height="38" fill="#fff" stroke="#000" stroke-width="0.5"/>
<rect x="137" y="155" width="90" height="12" fill="#fff" fill-opacity="0" stroke="#000" stroke-width="0.25" data-tcell="title" class="sh-tcell"/>
<text font-family="Helvetica" x="138.2" y="157.6" font-size="2" fill="#555">Part</text>
<text font-family="Helvetica" x="138.2" y="165.2" font-size="5" fill="#000">Plate Ø8 × 2</text>
<text font-family="Helvetica" x="138.2" y="178" font-size="3.4" fill="#000">1:2</text></g>
</svg>"""
SHEET_DIMS = [{"kind": "linear", "dir": "h", "a": [50, 100], "b": [70, 100], "at": 108, "text": "40", "value": 40},
              {"kind": "linear", "dir": "v", "a": [70, 100], "b": [70, 90], "at": 78, "text": "20", "value": 20},
              {"kind": "dia", "c": [60, 95], "r": 2, "u": [0.7071, -0.7071], "end": [65.66, 89.34], "text": "Ø8 H7", "value": 8},
              {"kind": "ang", "X": [50, 100], "u1": [1, 0], "u2": [0, -1], "r": 12, "text": "90°", "value": 90}]


class TestSheetDxf(unittest.TestCase):
    def read(self, data):
        return ezdxf.read(io.StringIO(data.decode("utf-8")))

    def test_layers_entities_and_dimensions(self):
        from auto3d.modeler.sheetdxf import to_dxf
        doc = self.read(to_dxf(SHEET_SVG, SHEET_DIMS, 0.5))
        self.assertEqual(doc.header["$INSUNITS"], 4)  # mm
        self.assertTrue({"visible", "hidden", "dims", "hatch", "text", "frame"} <= {ly.dxf.name for ly in doc.layers})
        self.assertEqual(doc.layers.get("hidden").dxf.linetype, "HIDDEN")
        msp = doc.modelspace()
        count = Counter(e.dxf.layer for e in msp)
        self.assertEqual(count, {"visible": 1, "hidden": 2, "hatch": 2, "text": 4, "frame": 3, "dims": 4}, count)
        # the paper 1:1, y up: the view's outline where it is on the sheet (210 − 100 = 110)
        outline = msp.query("LWPOLYLINE[layer=='visible']")[0]
        self.assertEqual([tuple(round(c, 6) for c in p[:2]) for p in outline.get_points()], [(50, 110), (70, 110), (70, 120), (50, 120), (50, 110)])
        texts = {t.dxf.text: t for t in msp.query("TEXT")}
        self.assertIn("Plate Ø8 × 2", texts)  # the title block, unicode kept
        self.assertAlmostEqual(texts["Front"].dxf.align_point.y, 210 - 118)
        # real dimensions: they measure the paper, DIMLFAC = 1 / scale gives the part's size
        dims = list(msp.query("DIMENSION"))
        self.assertEqual(len(dims), 4)
        width = dims[0]
        lfac = doc.dimstyles.get(width.dxf.dimstyle).dxf.dimlfac
        self.assertAlmostEqual(lfac, 2.0)
        self.assertEqual(width.dxf.text, "<>")  # (the measured value, so it follows when moved)
        self.assertAlmostEqual(width.get_measurement() * lfac, 40, places=6)
        shown = [e.text for e in doc.blocks.get(width.dxf.geometry) if e.dxftype() == "MTEXT"]
        self.assertEqual(shown, ["40"])
        self.assertEqual(dims[2].dxf.text, "Ø8 H7")  # a fit's text as written on the sheet
        self.assertAlmostEqual(dims[3].get_measurement(), 90, places=6)

    def test_prefix_kept_and_broken_ones_left_out(self):
        from auto3d.modeler.sheetdxf import to_dxf
        dims = [{"kind": "linear", "dir": "h", "a": [50, 100], "b": [70, 100], "at": 108, "text": "3× 40", "value": 40},
                {"kind": "linear", "dir": "h", "a": [50, 100], "at": 108, "text": "lost", "value": 1},  # (no b)
                {"kind": "nonsense"}]
        doc = self.read(to_dxf(SHEET_SVG, dims, 0.5))
        got = list(doc.modelspace().query("DIMENSION"))
        self.assertEqual([d.dxf.text for d in got], ["3× <>"])
        with self.assertRaises(Exception):
            to_dxf("<svg broken", [], 1)

    def test_sheet_pdf_prints_in_true_scale(self):
        """The PDF's page is the paper (A4 landscape: 297 × 210 mm) and 100 mm on the sheet is 100 mm on paper — print it
        at 100 % ("actual size") and the sheet's scale holds."""
        import fitz
        from auto3d.modeler.sheet import pdf
        svg = SHEET_SVG.replace("</svg>", '<line x1="20" y1="30" x2="120" y2="30" stroke="#000" stroke-width="0.5"/></svg>')
        page = fitz.open(stream=pdf(svg), filetype="pdf")[0]
        mm = 72 / 25.4
        self.assertAlmostEqual(page.rect.width / mm, 297, places=2)
        self.assertAlmostEqual(page.rect.height / mm, 210, places=2)
        line = next(d["rect"] for d in page.get_drawings() if abs(d["rect"].y0 - 30 * mm) < 0.1 and abs(d["rect"].y1 - 30 * mm) < 0.1)
        self.assertAlmostEqual(line.width / mm, 100, places=2)
        self.assertAlmostEqual(line.x0 / mm, 20, places=2)


if __name__ == "__main__":
    unittest.main()
