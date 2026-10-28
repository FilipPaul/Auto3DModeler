"""STEP assemblies, as SolidWorks / CATIA / Solid Edge exchange them: a STEP with an assembly tree opens as parts +
an assembly (a part placed twice is one part, sub-assemblies nested, names, colours, exact placements); an assembly
is written back as a structured STEP that reads back the same. A plain one-body STEP opens as before.
Skipped without the CAD kernel.
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from auto3d.modeler import available
from test_modeler_kernel import watertight

OCC = available("occ")
if OCC:
    from auto3d.modeler import blobs, doc, kernel as K

ROOT = Path(__file__).resolve().parents[1]
# the owner's real files (not in git): here, or in the main folder when this runs in a git worktree
FRAME = next((f for p in [ROOT, *ROOT.parents] if (f := p / "data" / "imports" / "ccec1f2fa5948fdf.stp").exists()), None)
I16 = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
TURNED = [0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1, 0, 100, 0, 0, 1]  # 90° about z, 100 along x
TILTED = [1, 0, 0, 0, 0, 0.6, 0.8, 0, 0, -0.8, 0.6, 0, 5, -6, 7.25, 1]  # turned about x (3-4-5), moved


def box(w, h, d):
    pts = {"p1": [0, 0], "p2": [w, 0], "p3": [w, h], "p4": [0, h]}
    lines = [{"id": f"l{i + 1}", "t": "line", "a": f"p{i + 1}", "b": f"p{(i + 1) % 4 + 1}"} for i in range(4)]
    return [{"id": "S1", "type": "sketch", "plane": {"datum": "XY"}, "points": pts, "entities": lines},
            {"id": "E1", "type": "extrude", "sketch": "S1", "op": "add", "d": d}]


def machine():
    """Machine: Plate (red) + Post turned + Sub (Post moved and tilted, Plate up 50) — Post used twice, Plate twice."""
    return {"root": "A1", "parts": {"P1": {"name": "Plate", "features": box(40, 20, 10), "colour": "#ff0000"},
                                    "P2": {"name": "Post", "features": box(10, 10, 30)}},
            "assemblies": {"A1": {"name": "Machine", "instances": [{"ref": "P1", "matrix": I16},
                                                                   {"ref": "P2", "matrix": TURNED, "colour": "#00ff00"},
                                                                   {"ref": "A2", "matrix": [*I16[:12], 0, 0, 50, 1]}]},
                           "A2": {"name": "Sub", "instances": [{"ref": "P2", "matrix": TILTED}, {"ref": "P1", "matrix": [*I16[:12], 0, 0, 30, 1]}]}}}


@unittest.skipUnless(OCC, "OCP not installed")
class TestStepAssembly(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.blobs = mock.patch.object(blobs, "DIR", Path(self.tmp.name))
        self.blobs.start()

    def tearDown(self):
        self.blobs.stop()
        self.tmp.cleanup()

    def solid(self, p):
        """A part of an imported tree as the browser makes it: one `solid` step on its blob -> the rebuild."""
        return doc.rebuild({"features": [{"id": "F1", "type": "solid", "blob": p["blob"], "file": p["name"] + ".step", "op": "add"}]})

    def test_export_reads_back_the_same_tree(self):
        step = doc.assembly_step(tree=machine(), name="Machine")
        text = step.decode("latin-1")
        self.assertIn("AUTOMOTIVE_DESIGN", text)  # AP214
        self.assertEqual(text.count("NEXT_ASSEMBLY_USAGE_OCCURRENCE"), 5)
        self.assertEqual(text.count("PRODUCT('Post'"), 1)  # one product per part, placed twice
        self.assertIn("'Post-1'", text)  # instance names as SolidWorks gives them
        # the whole file, read as one body (as before): every placement, nothing lost
        shape, cols, built = K.read_step_colours(step, summary=True)
        self.assertEqual(built, {"parts": 2, "placements": 4, "subs": 1})
        self.assertAlmostEqual(K.volume(shape), 2 * 8000 + 2 * 3000, delta=1e-6)

        imp = doc.import_assembly({"blob": blobs.put(step), "name": "machine.step"})
        parts, asms = imp["parts"], imp["assemblies"]
        self.assertEqual(sorted(p["name"] for p in parts.values()), ["Plate", "Post"])
        self.assertEqual(sorted(a["name"] for a in asms.values()), ["Machine", "Sub"])
        name = lambda k: (parts.get(k) or asms.get(k))["name"]  # noqa: E731
        root = asms[imp["root"]]
        self.assertEqual(root["name"], "Machine")
        self.assertEqual([name(i["ref"]) for i in root["instances"]], ["Plate", "Post", "Sub"])
        sub = asms[root["instances"][2]["ref"]]
        self.assertEqual([name(i["ref"]) for i in sub["instances"]], ["Post", "Plate"])
        self.assertEqual(root["instances"][1]["ref"], sub["instances"][0]["ref"])  # the same Post, twice
        want = [I16, TURNED, [*I16[:12], 0, 0, 50, 1], TILTED, [*I16[:12], 0, 0, 30, 1]]
        for got, m in zip([i["matrix"] for i in root["instances"] + sub["instances"]], want):
            for a, b in zip(got, m):
                self.assertAlmostEqual(a, b, delta=1e-12)
        self.assertEqual(root["instances"][1].get("colour"), "#00ff00")
        self.assertEqual(root["instances"][1]["name"], "Post-1")
        # each part is a STEP of its own: built by a solid step, exact volume, watertight, its colour kept
        for p in parts.values():
            r = self.solid(p)
            self.assertTrue(r["ok"], r["features"])
            self.assertAlmostEqual(r["body"]["volume"], {"Plate": 8000, "Post": 3000}[p["name"]], delta=1e-6)
            self.assertTrue(watertight(r["body"]))
            self.assertAlmostEqual(p["volume"], r["body"]["volume"], delta=1e-3)
            colours = {f.get("color") for f in r["body"]["faces"]}
            self.assertEqual(colours, {"#ff0000"} if p["name"] == "Plate" else {None})

    def test_imported_parts_keep_their_face_colours_and_go_back_out(self):
        """A part made of an imported coloured STEP keeps those colours in the assembly's STEP (round trip)."""
        plate = doc.body_of({"features": box(40, 20, 10)}).body
        top = next(f for n, fs in plate.names.items() if n == "E1:end" for f in fs)
        fm = K._face_map(plate.shape)
        cols = {fm.FindIndex(top) - 1: "#123456"}
        sha = blobs.put(K.to_step_coloured(plate.shape, cols, "Lid"))
        tree = {"root": "A1", "parts": {"P1": {"name": "Lid", "features": [{"id": "F1", "type": "solid", "blob": sha, "file": "lid.step"}]}},
                "assemblies": {"A1": {"name": "Box", "instances": [{"ref": "P1", "matrix": I16}, {"ref": "P1", "matrix": [*I16[:12], 0, 0, 20, 1]}]}}}
        imp = doc.import_assembly({"blob": blobs.put(doc.assembly_step(tree=tree, name="Box")), "name": "box.step"})
        (p,) = imp["parts"].values()
        self.assertEqual(p["name"], "Lid")
        self.assertEqual(len(imp["assemblies"][imp["root"]]["instances"]), 2)
        r = self.solid(p)
        self.assertEqual(sorted(f.get("color") or "" for f in r["body"]["faces"]), [""] * 5 + ["#123456"])

    def test_flexible_sub_assembly_placements_are_products_of_their_own(self):
        """A sub-assembly placed twice, one placement with its parts moved inside it (`inner`, as the browser sends it:
        "Lever (I2)"): two products, each with its own placements; the plain one shared."""
        tree = {"root": "A1", "parts": {"P1": {"name": "Arm", "features": box(80, 16, 5)}},
                "assemblies": {"A1": {"name": "Machine", "instances": [{"ref": "A2", "matrix": I16}, {"ref": "A2@I2", "matrix": [*I16[:12], 0, 100, 0, 1]},
                                                                       {"ref": "A2", "matrix": [*I16[:12], 0, 200, 0, 1]}]},
                               "A2": {"name": "Lever", "instances": [{"ref": "P1", "matrix": I16}, {"ref": "P1", "matrix": [*I16[:12], 0, 0, 5, 1]}]},
                               "A2@I2": {"name": "Lever (I2)", "instances": [{"ref": "P1", "matrix": I16}, {"ref": "P1", "matrix": TURNED}]}}}
        imp = doc.import_assembly({"blob": blobs.put(doc.assembly_step(tree=tree)), "name": "m.step"})
        asms = imp["assemblies"]
        root = asms[imp["root"]]
        self.assertEqual([asms[i["ref"]]["name"] for i in root["instances"]], ["Lever", "Lever (I2)", "Lever"])
        self.assertEqual(root["instances"][0]["ref"], root["instances"][2]["ref"])
        self.assertEqual(len(imp["parts"]), 1)
        turned = asms[root["instances"][1]["ref"]]["instances"][1]["matrix"]
        for a, b in zip(turned, TURNED):
            self.assertAlmostEqual(a, b, delta=1e-12)

    def test_plain_step_is_one_body(self):
        step = doc.export({"features": box(40, 20, 10)}, "step")
        sha = blobs.put(step)
        r = doc.import_solid({"blob": sha, "name": "box.step"})
        self.assertEqual(r["structure"], {"parts": 1, "placements": 1, "subs": 0})
        self.assertEqual((r["faces"], r["volume"]), (6, 8000))
        imp = doc.import_assembly({"blob": sha, "name": "box.step"})
        root = imp["assemblies"][imp["root"]]
        self.assertEqual(len(root["instances"]), 1)
        self.assertEqual(root["instances"][0]["matrix"], [float(v) for v in I16])

    def test_single_placement_wrappers_are_folded(self):
        """A sub-assembly holding one placement (as ECAD boards wrap each component) is not kept: the part goes into the
        parent with the two placements multiplied."""
        tree = {"root": "A1", "parts": {"P1": {"name": "Chip", "features": box(4, 4, 1)}, "P2": {"name": "Board", "features": box(50, 30, 1.6)}},
                "assemblies": {"A1": {"name": "PCB", "instances": [{"ref": "P2", "matrix": I16}, {"ref": "A2", "matrix": TURNED}]},
                               "A2": {"name": "U1", "instances": [{"ref": "P1", "matrix": [*I16[:12], 1, 2, 1.6, 1]}]}}}
        imp = doc.import_assembly({"blob": blobs.put(doc.assembly_step(tree=tree)), "name": "pcb.step"})
        self.assertEqual([a["name"] for a in imp["assemblies"].values()], ["PCB"])
        chip = imp["assemblies"][imp["root"]]["instances"][1]
        self.assertEqual(imp["parts"][chip["ref"]]["name"], "Chip")
        self.assertEqual(chip["name"], "U1-1")  # (the wrapper's placement keeps its name)
        for a, b in zip(chip["matrix"], [0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1, 0, 98, 1, 1.6, 1]):
            self.assertAlmostEqual(a, b, delta=1e-12)

    def test_errors(self):
        with self.assertRaises(K.KernelError):
            doc.assembly_step(tree={"root": "A1", "parts": {}, "assemblies": {"A1": {"name": "Empty", "instances": []}}})
        with self.assertRaises(K.KernelError):  # a part with no solid yet is left out; nothing left
            doc.assembly_step(tree={"root": "A1", "parts": {"P1": {"name": "Blank", "features": []}},
                                    "assemblies": {"A1": {"name": "A", "instances": [{"ref": "P1", "matrix": I16}]}}})
        with self.assertRaises(K.KernelError):
            doc.import_assembly({"blob": "0" * 64, "name": "gone.step"})
        with self.assertRaises(K.KernelError):
            doc.import_assembly({"blob": blobs.put(b"not a STEP file"), "name": "x.step"})
        # the flat export (no tree) is as before: placed bodies in one compound
        flat = doc.assembly_step([{"part": {"features": box(40, 20, 10)}, "matrix": None}, {"part": {"features": box(40, 20, 10)}, "matrix": TURNED}])
        self.assertEqual(K.solids(K.from_step(flat)), 2)

    @unittest.skipUnless(FRAME, "the owner's sample STEP is not here")
    def test_real_assembly_from_data_imports(self):
        """A real STEP assembly (44 placements, two sub-assemblies with weld studs): the same parts, the same total
        volume as the file read as one body."""
        data = FRAME.read_bytes()
        shape, _, built = K.read_step_colours(data, summary=True)
        imp = doc.import_assembly({"blob": blobs.put(data), "name": "frame.stp"})
        parts, asms = imp["parts"], imp["assemblies"]
        self.assertEqual(len(parts), built["parts"])
        self.assertEqual(asms[imp["root"]]["name"], "M6219279")
        self.assertEqual(len(asms), 3)
        self.assertTrue({"M4x8 Stud (B)", "M4x20 WeldStud"} <= {p["name"] for p in parts.values()})

        def total(k, n=1):
            if k in parts:
                return n * parts[k]["volume"]
            return sum(total(i["ref"], n) for i in asms[k]["instances"])
        self.assertAlmostEqual(total(imp["root"]), K.volume(shape), delta=K.volume(shape) * 1e-6)
        counts = {}
        for i in asms[imp["root"]]["instances"]:
            counts[i["ref"]] = counts.get(i["ref"], 0) + 1
        self.assertGreater(max(counts.values()), 1)  # a part placed several times is one part


if __name__ == "__main__":
    unittest.main()
