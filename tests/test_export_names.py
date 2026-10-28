"""Names and colours in the exported files, as another CAD program reads them: "×" (and other non-ASCII) names exact in
STEP (as STEP's own \\X2\\ escapes: an ASCII file) and glTF, ASCII in IGES; a part's STEP named after the part even
right after an assembly's export in the same process (the writers' settings are put back); a part's STEP / IGES / glTF
in its colour with its 🎨 painted faces; an assembly's IGES a named body per placed part; the BOM's "Bought / made" by
the material. The CAD tests are skipped without the CAD kernel.
"""
import json
import struct
import unittest
from collections import Counter

from auto3d.modeler import available
from auto3d.modeler.materials import made_how
from test_step_assembly import I16, machine

OCC = available("occ")
if OCC:
    from OCP.Interface import Interface_Static
    from auto3d.modeler import doc, kernel as K
    from test_exchange_formats import plate_with_hole

ORANGE = "#d9822b"


def glb(data):
    n = struct.unpack("<I", data[12:16])[0]
    return json.loads(data[20:20 + n])


def painted_plate(**more):
    """The 40 × 20 × 10 plate with a hole, aluminium, its top face (E1:end) painted orange."""
    return {"features": plate_with_hole(), "material": "aluminium", "paint": [{"name": "E1:end", "fp": [20, 10, 10], "color": ORANGE}], **more}


def names(data, kind="step"):
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


def coloured_at(shape, colours, colour):
    """The middles (rounded) of the faces read back in this colour."""
    fm = K._face_map(shape)
    return [[round(v, 6) for v in K._centroid(fm.FindKey(k + 1))] for k, c in colours.items() if c == colour]


@unittest.skipUnless(OCC, "OCP not installed")
class TestNames(unittest.TestCase):
    def tree(self):
        t = machine()
        t["parts"]["P2"]["name"] = "ISO 10642 M6×16"
        return t

    def test_times_sign_exact_in_step_and_glb(self):
        step = doc.assembly_step(tree=self.tree(), name="Machine")
        self.assertTrue(step.decode("latin-1").isascii())  # (no raw UTF-8 bytes: older readers showed them as "Ã—")
        self.assertIn(b"ISO 10642 M6\\X2\\00D7\\X0\\16", step)
        self.assertIn("ISO 10642 M6×16", names(step))
        self.assertIn("ISO 10642 M6×16-1", names(step))  # (its placement)
        self.assertNotIn("Ã", "".join(names(step)))
        nodes = [n.get("name") for n in glb(doc.assembly_step(tree=self.tree(), name="Machine", fmt="glb"))["nodes"]]
        self.assertIn("ISO 10642 M6×16-1", nodes)
        self.assertEqual([n["name"] for n in glb(doc.export({"features": plate_with_hole()}, "glb", "Deska Ø8 × 2"))["nodes"]], ["Deska Ø8 × 2"])
        self.assertEqual(names(doc.export({"features": plate_with_hole()}, "step", "Deska Ø8 × 2")), ["Deska Ø8 × 2"])

    def test_part_step_named_after_the_part_after_an_assembly_export(self):
        before = Interface_Static.CVal_s("write.step.product.name")
        doc.assembly_step(tree=self.tree(), name="Frame 2")
        self.assertEqual(Interface_Static.CVal_s("write.step.product.name"), before)  # (put back after the export)
        step = doc.export({"features": plate_with_hole()}, "step", "Base plate")
        self.assertEqual(names(step), ["Base plate"])
        self.assertNotIn(b"Frame 2", step)
        _, _, built = K.read_step_colours(step, summary=True)
        self.assertEqual(built, {"parts": 1, "placements": 1, "subs": 0})  # (still one plain part)
        doc.export({"features": plate_with_hole()}, "iges", "Base plate")
        self.assertEqual(Interface_Static.IVal_s("write.iges.brep.mode"), 0)  # (IGES: its setting put back too)

    def test_assembly_iges_a_named_body_per_placement(self):
        data = doc.assembly_step(tree=self.tree(), name="Machine", fmt="iges")
        self.assertEqual(names(data, "iges"), ["Plate-1", "ISO 10642 M6x16-1", "Sub-1/ISO 10642 M6x16-1", "Sub-1/Plate-1"])  # (ASCII)
        shape, colours, how = K.read_iges(data)
        self.assertEqual((how, K.solids(shape)), ("solid", 4))
        self.assertEqual(set(colours.values()), {"#ff0000", "#00ff00"})  # the Plate's red (twice), the turned Post's green
        self.assertEqual(Counter(colours.values()), {"#ff0000": 12, "#00ff00": 6})  # (the other Post: no colour of its own)
        tree = self.tree()
        tree["parts"]["P2"]["colour"] = "#8b9097"  # a grey Post: one placement green, the other grey (not both green)
        _, colours, _ = K.read_iges(doc.assembly_step(tree=tree, name="Machine", fmt="iges"))
        self.assertEqual(Counter(colours.values()), {"#ff0000": 12, "#00ff00": 6, "#8b9097": 6})
        self.assertEqual(K._ascii("Šroubek M6×16 – ok"), "Sroubek M6x16  ok")


@unittest.skipUnless(OCC, "OCP not installed")
class TestColours(unittest.TestCase):
    def test_part_step_in_its_colour_with_its_painted_face(self):
        step = doc.export(painted_plate(), "step", "Plate")
        shape, colours = K.read_step_colours(step)
        self.assertAlmostEqual(K.volume(shape), doc.rebuild(painted_plate())["body"]["volume"], delta=1e-6)
        self.assertEqual(coloured_at(shape, colours, ORANGE), [[20, 10, 10]])  # the top face, painted
        self.assertEqual(sum(c == "#c3c8cd" for c in colours.values()), K.face_count(shape) - 1)  # the rest aluminium
        shape, colours, how = K.read_iges(doc.export(painted_plate(), "iges", "Plate"))
        self.assertEqual((how, coloured_at(shape, colours, ORANGE)), ("solid", [[20, 10, 10]]))
        # a painted step: every face it made (the hole's wall)
        shape, colours = K.read_step_colours(doc.export(painted_plate(paint=[{"feature": "H1", "color": "#2e9e4f"}]), "step", "Plate"))
        self.assertEqual(coloured_at(shape, colours, "#2e9e4f"), [[20, 10, 5]])

    def test_part_glb_painted_face(self):
        js = glb(doc.export(painted_plate(), "glb", "Plate"))
        prims = js["meshes"][0]["primitives"]
        orange = [p for p in prims if [round(c * 255) for c in js["materials"][p["material"]]["pbrMetallicRoughness"]["baseColorFactor"][:3]] == [0xd9, 0x82, 0x2b]]
        self.assertEqual(len(orange), 1)
        acc = js["accessors"][orange[0]["attributes"]["POSITION"]]
        self.assertAlmostEqual(acc["min"][1], 0.01, places=6)  # the top (Y up, metres)
        self.assertAlmostEqual(acc["max"][1], 0.01, places=6)
        self.assertGreater(js["materials"][orange[0]["material"]]["pbrMetallicRoughness"]["metallicFactor"], 0.5)  # (still aluminium)

    def test_assembly_painted_face_in_step_iges_glb(self):
        tree = machine()
        tree["parts"]["P1"]["paint"] = [{"name": "E1:end", "fp": [20, 10, 10], "color": ORANGE}]
        shape, colours = K.read_step_colours(doc.assembly_step(tree=tree, name="Machine"))
        self.assertEqual(sorted(coloured_at(shape, colours, ORANGE)), [[20, 10, 10], [20, 10, 90]])  # the Plate twice (in Sub: up 30 + 50)
        shape, colours, _ = K.read_iges(doc.assembly_step(tree=tree, name="Machine", fmt="iges"))
        self.assertEqual(sorted(coloured_at(shape, colours, ORANGE)), [[20, 10, 10], [20, 10, 90]])
        js = glb(doc.assembly_step(tree=tree, name="Machine", fmt="glb"))
        self.assertIn([0xd9, 0x82, 0x2b], [[round(c * 255) for c in m["pbrMetallicRoughness"]["baseColorFactor"][:3]] for m in js["materials"]])

    def test_glb_placement_colour_over_a_coloured_part(self):
        tree = machine()
        tree["parts"]["P2"].update(colour="#8b9097", material="steel")  # (a steel post, one placement in Sub green)
        tree["assemblies"]["A2"]["instances"][0]["colour"] = "#2e9e4f"
        del tree["assemblies"]["A1"]["instances"][1]["colour"]  # (the other post in the part's colour)
        js = glb(doc.assembly_step(tree=tree, name="Machine", fmt="glb"))
        colours = [[round(c * 255) for c in m["pbrMetallicRoughness"]["baseColorFactor"][:3]] for m in js["materials"]]
        self.assertIn([0x2e, 0x9e, 0x4f], colours)  # the green placement (the part's own colour beat it)
        self.assertIn([0x8b, 0x90, 0x97], colours)

    def test_iges_without_colours_and_errors(self):
        shape, colours, how = K.read_iges(doc.export({"features": plate_with_hole()}, "iges", "Plate"))
        self.assertEqual((how, colours), ("solid", {}))  # (no colour of its own: none written)
        with self.assertRaises(K.KernelError):
            doc.assembly_step(tree={"root": "A", "parts": {}, "assemblies": {"A": {"name": "A", "instances": [{"ref": "X", "matrix": I16}]}}}, fmt="iges")


class TestBomMade(unittest.TestCase):
    def test_by_material(self):
        self.assertEqual(made_how({"material": "steel"}), "made")
        self.assertEqual(made_how({"material": "aluminium"}), "made")
        self.assertEqual(made_how({"material": "POM"}), "made")  # (an engineering plastic: machined)
        self.assertEqual(made_how({"material": "PETG"}), "made (3D print)")
        self.assertEqual(made_how({}), "made (3D print)")  # (none chosen: PLA)
        self.assertEqual(made_how({"material": "steel", "library": True}), "bought")
        import server
        lines = server.bom_csv([{"qty": 1, "name": "Base plate", "material": "aluminium", "mass_g": 102.2}], []).decode("utf-8-sig").split("\r\n")
        self.assertTrue(lines[1].endswith(";aluminium;102,2;made"))


if __name__ == "__main__":
    unittest.main()
