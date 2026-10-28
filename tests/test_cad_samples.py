"""Real CAD files from other programs (samples/ToImportToOurApp, listed with their source, licence and program in samples.json:
CATIA V5, NX, Creo, SolidWorks, Inventor / Fusion, I-DEAS, CoCreate, AutoCAD, ACIS, EUCLID …): each opens as the app
opens it — a part as one solid (its faces, volume, bbox, how the file is built), a STEP's assembly tree (its parts,
placements and total volume), an IGES as a solid / sewn / a reference — with the values measured when the file was
added; and goes back out: a part's STEP / IGES keeps its volume, an assembly's STEP keeps its parts, placements and
volume. Files over 3 MB (and those marked slow) run only with A3D_SLOW_SAMPLES=1. Skipped without the CAD kernel.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from auto3d.modeler import available

OCC = available("occ")
if OCC:
    from auto3d.modeler import blobs, doc, kernel as K

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples" / "ToImportToOurApp"
MANIFEST = json.loads((SAMPLES / "samples.json").read_text(encoding="utf-8")) if (SAMPLES / "samples.json").exists() else {"files": []}
SLOW = bool(os.environ.get("A3D_SLOW_SAMPLES"))
SIZE_LIMIT = 3_000_000  # bytes: bigger files only with A3D_SLOW_SAMPLES=1
REL = 1e-6


def skip_reason(item):
    p = SAMPLES / item["path"]
    if not p.exists():
        return f"{item['path']} is not here"
    if not SLOW and (item.get("slow") or p.stat().st_size > SIZE_LIMIT):
        return f"{item['path']} is big (A3D_SLOW_SAMPLES=1 runs it)"
    return None


def total(imp, k=None, n=1):
    """An imported tree's total volume and placements: (volume, count)."""
    parts, asms = imp["parts"], imp["assemblies"]
    k = imp["root"] if k is None else k
    if k in parts:
        return n * parts[k]["volume"], n
    v, c = 0.0, 0
    for i in asms[k]["instances"]:
        dv, dc = total(imp, i["ref"], n)
        v, c = v + dv, c + dc
    return v, c


@unittest.skipUnless(OCC, "OCP not installed")
@unittest.skipUnless(MANIFEST["files"], "samples/ToImportToOurApp is not here")
class TestCadSamples(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.blobs = mock.patch.object(blobs, "DIR", Path(self.tmp.name))
        self.blobs.start()

    def tearDown(self):
        self.blobs.stop()
        self.tmp.cleanup()

    def near(self, got, want, rel=REL, what=""):
        self.assertLessEqual(abs(got - want), rel * max(1.0, abs(want)), f"{what}: {got} != {want}")

    def check(self, item):
        p, e = SAMPLES / item["path"], item["expect"]
        sha = blobs.put(p.read_bytes())
        if e.get("error"):  # (a file the app cannot open: it says why, it does not break)
            with self.assertRaises(K.KernelError) as cm:
                doc.import_solid({"blob": sha, "name": p.name})
            self.assertIn(e["error"], str(cm.exception))
            return
        r = doc.import_solid({"blob": sha, "name": p.name})
        self.assertEqual(r["faces"], e["faces"], "faces")
        self.near(r["volume"], e["volume"], what="volume")
        if e.get("bbox"):
            for a, b in zip(r["bbox"], e["bbox"]):
                self.assertAlmostEqual(a, b, delta=1e-3)
        self.assertEqual(r.get("structure"), e.get("structure"))
        self.assertEqual(r.get("iges"), e.get("iges"))
        self.assertEqual(r.get("op"), e.get("op"))
        solid = {"features": [{"id": "F1", "type": "solid", "blob": r["blob"], "file": p.name, "op": "add"}]}
        if item["kind"] == "iges":  # back out as IGES: the same solid (a reference body is not one)
            if r.get("op") != "ref":
                shape, _, how = K.read_iges(doc.export(solid, "iges"))
                self.assertEqual(how, "solid")
                self.near(K.volume(shape), r["volume"], 1e-5, "IGES round trip")
            return
        if e.get("tree_crash") or item.get("known", {}).get("tessellated"):
            return  # (tests below)
        imp = doc.import_assembly({"blob": sha, "name": p.name})
        vol, n = total(imp)
        self.assertEqual((len(imp["parts"]), n), (e["parts"], e["placements"]), "parts, placements")
        self.near(vol, e["asm_volume"], what="assembly volume")
        if item["kind"] == "part":  # back out as STEP: the same volume
            self.near(K.volume(K.from_step(doc.export(solid, "step"))), r["volume"], 1e-5, "STEP round trip")
            return
        # an assembly back out as a STEP assembly (a product per part, the placements, sub-assemblies) and in again
        tree = {"root": imp["root"],
                "parts": {k: {"name": q["name"], "features": [{"id": "F1", "type": "solid", "blob": q["blob"], "file": q["name"] + ".step", "op": "add"}]}
                          for k, q in imp["parts"].items()},
                "assemblies": {k: {"name": a["name"], "instances": [{"ref": i["ref"], "matrix": i["matrix"], **({"colour": i["colour"]} if i.get("colour") else {})}
                                                                     for i in a["instances"]]} for k, a in imp["assemblies"].items()}}
        out = doc.assembly_step(tree=tree, name=imp["assemblies"][imp["root"]]["name"] or p.stem)
        _, _, built = K.read_step_colours(out, summary=True)
        self.assertEqual(built, {"parts": e["parts"], "placements": e["placements"], "subs": e["asms"] - 1}, "the exported STEP's structure")
        back = doc.import_assembly({"blob": blobs.put(out), "name": "back.step"})
        vol2, n2 = total(back)
        self.assertEqual((len(back["parts"]), n2), (e["parts"], e["placements"]), "round trip parts, placements")
        ascii_names = lambda t: sorted(q["name"] for q in t["parts"].values() if q["name"].isascii())  # noqa: E731 — (others: the known bug below)
        self.assertEqual(ascii_names(back), ascii_names(imp), "part names")
        self.near(vol2, vol, 1e-5, "round trip volume")


def _make(item):
    def test(self):
        reason = skip_reason(item)
        if reason:
            self.skipTest(reason)
        self.check(item)
    test.__doc__ = f"{item['path']} ({item['program']}, {item['format']}, {item['kind']})"
    return test


for _item in MANIFEST["files"]:
    _name = "test_" + "".join(c if c.isalnum() else "_" for c in Path(_item["path"]).stem).lower()
    setattr(TestCadSamples, _name, _make(_item))


@unittest.skipUnless(OCC, "OCP not installed")
class TestCadSampleKnownBugs(unittest.TestCase):
    """App bugs these files show (unexpected success = fixed: drop the expectedFailure)."""

    @unittest.expectedFailure
    def test_assembly_tree_of_a_step_with_unnamed_labels(self):
        """CATIA's AP242 with supplemental geometry: its assembly tree read in a process of its own must not crash (it
        segfaults in kernel._label_name on a label with no name: TDF_Label.FindAttribute on a missing attribute)."""
        item = next((i for i in MANIFEST["files"] if (i["expect"].get("tree_crash"))), None)
        if item is None or not (SAMPLES / item["path"]).exists():
            self.skipTest("the sample is not here")
        code = ("import sys; sys.path.insert(0, sys.argv[1]); from auto3d.modeler import kernel as K; "
                "t = K.read_step_tree(open(sys.argv[2], 'rb').read()); print(len(t['parts']))")
        r = subprocess.run([sys.executable, "-c", code, str(ROOT), str(SAMPLES / item["path"])], capture_output=True, timeout=300)
        self.assertEqual(r.returncode, 0, f"read_step_tree crashed ({r.returncode})")

    @unittest.expectedFailure
    def test_the_question_counts_the_parts_the_assembly_gets(self):
        """Pro/ENGINEER's AS1 (AP203): "Open as an assembly?" says 10 different parts placed 36 times (step_structure)
        but the assembly opened has 5 parts placed 18 times (import_assembly) — the file's 5 products with no faces (empty
        shapes beside each solid) are counted too."""
        p = SAMPLES / "occt-import-js" / "as1_pe_203.stp"
        if not p.exists():
            self.skipTest("the sample is not here")
        data = p.read_bytes()
        _, _, built = K.read_step_colours(data, summary=True)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(blobs, "DIR", Path(tmp)):
            imp = doc.import_assembly({"blob": blobs.put(data), "name": "as1.stp"})
        self.assertEqual((built["parts"], built["placements"]), (len(imp["parts"]), total(imp)[1]))

    def test_non_ascii_names_go_out_and_back_in(self):
        """A part named "Držák čep Ø8" in an assembly's STEP comes back as "DrÅ¾Ã¡k Ä\\x8dep Ã\\x988": the names are
        written UTF-8 encoded twice (kernel._xcaf_tree's TCollection_ExtendedString of a Python str?), not as \\X2\\ escapes."""
        pts = {"p1": [0, 0], "p2": [10, 0], "p3": [10, 10], "p4": [0, 10]}
        lines = [{"id": f"l{i + 1}", "t": "line", "a": f"p{i + 1}", "b": f"p{(i + 1) % 4 + 1}"} for i in range(4)]
        box = [{"id": "S1", "type": "sketch", "plane": {"datum": "XY"}, "points": pts, "entities": lines},
               {"id": "E1", "type": "extrude", "sketch": "S1", "op": "add", "d": 5}]
        tree = {"root": "A", "parts": {"P": {"name": "Držák čep Ø8", "features": box}},
                "assemblies": {"A": {"name": "Sestava", "instances": [{"ref": "P", "matrix": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]}]}}}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(blobs, "DIR", Path(tmp)):
            imp = doc.import_assembly({"blob": blobs.put(doc.assembly_step(tree=tree, name="Sestava")), "name": "x.step"})
        self.assertEqual([p["name"] for p in imp["parts"].values()], ["Držák čep Ø8"])

    def _solid_of(self, rel_path, tmp):
        p = SAMPLES / rel_path
        if not p.exists():
            self.skipTest("the sample is not here")
        with mock.patch.object(blobs, "DIR", Path(tmp)):
            r = doc.import_solid({"blob": blobs.put(p.read_bytes()), "name": p.name})
            part = {"features": [{"id": "F1", "type": "solid", "blob": r["blob"], "file": p.name, "op": "add"}]}
            return r, part, doc.export(part, "step")

    @unittest.expectedFailure
    def test_volume_counts_the_solid_only(self):
        """CATIA's AP242 (NIST CTC-02) holds a solid and two loose faces (supplemental geometry): the solid is
        47 106 788 mm³, the part opens as 45 468 680 mm³ (kernel.volume of the compound counts the open faces too) — the
        mass and the volume shown are 3.5 % off."""
        from OCP.TopAbs import TopAbs_SOLID
        from OCP.TopExp import TopExp_Explorer
        with tempfile.TemporaryDirectory() as tmp:
            r, _, _ = self._solid_of("nist/nist_ctc_02_asme1_ap242-e2.stp", tmp)
            shape, _ = K.read_step_colours((SAMPLES / "nist/nist_ctc_02_asme1_ap242-e2.stp").read_bytes())
        ex, solid = TopExp_Explorer(shape, TopAbs_SOLID), 0.0
        while ex.More():
            solid += K.volume(ex.Current())
            ex.Next()
        self.assertAlmostEqual(r["volume"], solid, delta=solid * 1e-6)

    def test_part_step_export_keeps_the_files_colours(self):
        """CATIA V5's SG1 has its 16 faces coloured; opened as a 3D model and exported as STEP (doc.export -> K.to_step)
        the colours are gone (the GLB and the assembly STEP keep them)."""
        with tempfile.TemporaryDirectory() as tmp:
            r, _, out = self._solid_of("stepcode/sg1-c5-214.stp", tmp)
        self.assertEqual(r["coloured"], 16)
        _, cols = K.read_step_colours(out)
        self.assertEqual(len(cols), 16)

    @unittest.expectedFailure
    def test_tessellated_step_is_not_a_solid_with_a_negative_volume(self):
        """A tessellated AP242 (faceted surfaces, no B-rep): it opens as faces with a negative volume and no box — it
        should be refused or made a mesh solid / reference."""
        item = next((i for i in MANIFEST["files"] if i.get("known", {}).get("tessellated")), None)
        if item is None or not (SAMPLES / item["path"]).exists():
            self.skipTest("the sample is not here")
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(blobs, "DIR", Path(tmp)):
            r = doc.import_solid({"blob": blobs.put((SAMPLES / item["path"]).read_bytes()), "name": "tg.stp"})
        self.assertTrue(r["volume"] > 0 and r["bbox"], f"volume {r['volume']}, bbox {r['bbox']}")


if __name__ == "__main__":
    unittest.main()
