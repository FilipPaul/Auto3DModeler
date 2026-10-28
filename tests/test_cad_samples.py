"""Real CAD files from other programs (samples/ToImportToOurApp, listed with their source, licence and program in samples.json:
CATIA V5, NX, Creo, SolidWorks, Inventor / Fusion, I-DEAS, CoCreate, AutoCAD, ACIS, EUCLID …): each opens as the app
opens it — a part as one solid (its faces, volume, bbox, how the file is built), a STEP's assembly tree (its parts,
placements and total volume), an IGES as a solid / sewn / a reference — with the values measured when the file was
added; and goes back out: a part's STEP / IGES keeps its volume, an assembly's STEP keeps its parts, placements and
volume. Files over 3 MB (and those marked slow) run only with A3D_SLOW_SAMPLES=1. Skipped without the CAD kernel.
"""
import json
import math
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
        if e.get("error") or e.get("alone_error"):  # (a file the app cannot open alone: it says why, it does not break)
            with self.assertRaises(K.KernelError) as cm:
                doc.import_solid({"blob": sha, "name": p.name})
            self.assertIn(e.get("error") or e["alone_error"], str(cm.exception))
            if e.get("error"):
                return
        if item.get("with_files"):  # an assembly whose parts are files of their own: opened with the files beside it
            r = doc.import_solid({"files": {f.name: blobs.put(f.read_bytes()) for f in sorted(p.parent.iterdir())}})
            self.assertEqual(r["name"], p.name, "the top file")
            sha = r["blob"]  # (one STEP holding them all)
        else:
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
    """App bugs these files showed, fixed (each test: what went wrong; a known bug still open: expectedFailure)."""

    def sample(self, rel_path):
        p = SAMPLES / rel_path
        if not p.exists():
            self.skipTest("the sample is not here")
        return p

    def test_assembly_tree_of_a_step_with_unnamed_labels(self):
        """CATIA's AP242 with supplemental geometry: its assembly tree read in a process of its own must not crash (it
        segfaulted in kernel._label_name on a label with no name: TDF_Label.FindAttribute on a missing attribute)."""
        p = self.sample("nist/nist_ctc_02_asme1_ap242-e2.stp")
        code = ("import sys; sys.path.insert(0, sys.argv[1]); from auto3d.modeler import kernel as K; "
                "t = K.read_step_tree(open(sys.argv[2], 'rb').read()); print(sum(1 for p in t['parts'].values() if K.face_count(p['shape'])))")
        r = subprocess.run([sys.executable, "-c", code, str(ROOT), str(p)], capture_output=True, timeout=300)
        self.assertEqual(r.returncode, 0, f"read_step_tree crashed ({r.returncode})")
        self.assertEqual(r.stdout.decode().strip().splitlines()[-1], "3")  # (the solid and the two sheets of supplemental faces)

    def test_the_question_counts_the_parts_the_assembly_gets(self):
        """Pro/ENGINEER's AS1 (AP203): "Open as an assembly?" said 10 different parts placed 36 times (step_structure)
        but the assembly opened has 5 parts placed 18 times (import_assembly) — the file's 5 products with no faces (empty
        shapes beside each solid) were counted too."""
        data = self.sample("occt-import-js/as1_pe_203.stp").read_bytes()
        _, _, built = K.read_step_colours(data, summary=True)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(blobs, "DIR", Path(tmp)):
            imp = doc.import_assembly({"blob": blobs.put(data), "name": "as1.stp"})
        self.assertEqual((built["parts"], built["placements"]), (len(imp["parts"]), total(imp)[1]))
        self.assertEqual((built["parts"], built["placements"]), (5, 18))

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
        p = self.sample(rel_path)
        with mock.patch.object(blobs, "DIR", Path(tmp)):
            r = doc.import_solid({"blob": blobs.put(p.read_bytes()), "name": p.name})
            part = {"features": [{"id": "F1", "type": "solid", "blob": r["blob"], "file": p.name, "op": "add"}]}
            return r, part, doc.export(part, "step")

    def test_volume_counts_the_solid_only(self):
        """CATIA's AP242 (NIST CTC-02) holds a solid and two loose faces (supplemental geometry): the solid is
        47 106 842 mm³, the part opened as 45 468 680 mm³ (kernel.volume of the compound counted the open faces too) and
        a cut raised it. Now: the solid's volume; the loose faces shown as a reference; a Ø10 × 5 cut takes 392.7 mm³ off."""
        from OCP.TopAbs import TopAbs_SOLID
        from OCP.TopExp import TopExp_Explorer
        with tempfile.TemporaryDirectory() as tmp:
            r, part, out = self._solid_of("nist/nist_ctc_02_asme1_ap242-e2.stp", tmp)
            shape, _ = K.read_step_colours((SAMPLES / "nist/nist_ctc_02_asme1_ap242-e2.stp").read_bytes())
            built = doc.rebuild(part)
            top = max((f for f in built["body"]["faces"] if f.get("type") == "plane" and f["normal"] == [0, 0, 1]), key=lambda f: f["area"])
            cut = doc.rebuild({"features": part["features"] + [
                {"id": "S1", "type": "sketch", "plane": {"face": {"name": top["name"]}, "frame": top["frame"]}, "points": {"c": [0, 0]},
                 "entities": [{"id": "c1", "t": "circle", "c": "c", "r": 5}]},
                {"id": "E1", "type": "extrude", "sketch": "S1", "op": "cut", "d": 5}]})
        ex, solid = TopExp_Explorer(shape, TopAbs_SOLID), 0.0
        while ex.More():
            solid += K.volume(ex.Current())
            ex.Next()
        self.assertAlmostEqual(r["volume"], solid, delta=solid * 1e-6)
        self.assertAlmostEqual(r["volume"], 47106842.252, delta=1)
        self.assertEqual([x["id"] for x in built["refs"]], ["F1:surfaces"])  # (the loose faces: see-through)
        self.assertTrue(cut["ok"], cut["features"])
        # (to the volume's precision on a 47 · 10⁶ mm³ solid with B-spline faces: 1e-7 of it)
        self.assertAlmostEqual(built["body"]["volume"] - cut["body"]["volume"], math.pi * 25 * 5, delta=r["volume"] * 1e-7)
        self.assertAlmostEqual(K.volume(K.from_step(out)), solid, delta=solid * 1e-6)  # (STEP out: the solid only)

    def test_part_step_export_keeps_the_files_colours(self):
        """CATIA V5's SG1 has its 16 faces coloured; opened as a 3D model and exported as STEP (doc.export -> K.to_step)
        the colours are gone (the GLB and the assembly STEP keep them)."""
        with tempfile.TemporaryDirectory() as tmp:
            r, _, out = self._solid_of("stepcode/sg1-c5-214.stp", tmp)
        self.assertEqual(r["coloured"], 16)
        _, cols = K.read_step_colours(out)
        self.assertEqual(len(cols), 16)

    def test_tessellated_step_is_not_a_solid_with_a_negative_volume(self):
        """A tessellated AP242 (NIST FTC-08: faceted surfaces, no B-rep) opened as faces with a negative volume and no
        box. Now its closed triangle set is made a solid of flat facets (as an STL is), with a note: a positive volume, a
        box, a closed mesh, a cut that takes material off, and a STEP round trip."""
        with tempfile.TemporaryDirectory() as tmp:
            r, part, out = self._solid_of("nist/nist_ftc_08_asme1_ap242-e1-tg.stp", tmp)
            built = doc.rebuild(part)
            top = max((f for f in built["body"]["faces"] if f.get("type") == "plane" and f["normal"] == [0, 0, 1]), key=lambda f: f["area"])
            hole = doc.rebuild({"features": part["features"] + [{"id": "H1", "type": "hole", "plane": {"face": {"name": top["name"]}, "frame": top["frame"]},
                                                                 "points": [on_face(built["body"], top)], "d": 4, "depth": 2, "through": False}]})
        self.assertTrue(r.get("faceted"))
        self.assertIn("tessellated", r["warning"])
        self.assertAlmostEqual(r["volume"], 503280.82, delta=0.01)
        self.assertEqual(r["bbox"], [-155.797, -111.347, 0.0, 155.797, 111.347, 48.26])
        self.assertEqual(open_edges(built["body"]), 0)
        self.assertTrue(hole["ok"], hole["features"])
        self.assertAlmostEqual(built["body"]["volume"] - hole["body"]["volume"], math.pi * 4 * 2, delta=1e-6)
        self.assertAlmostEqual(K.volume(K.from_step(out)), r["volume"], delta=r["volume"] * 1e-6)

    def test_flat_bspline_faces_count_as_flat(self):
        """Inventor's IGES cube and I-DEAS's DM1 store flat faces as B-spline surfaces: none counted as flat, so no
        sketch or hole could go on them. Now they are planes with a frame: a Ø2 hole 4 deep into the cube's top takes
        π · 1² · 4 off; its STEP goes out and back in with that volume."""
        with tempfile.TemporaryDirectory() as tmp:
            r, part, _ = self._solid_of("occt-import-js/Cube 10x10.igs", tmp)
            built = doc.rebuild(part)
            flat = [f for f in built["body"]["faces"] if f.get("type") == "plane"]
            top = next(f for f in flat if f["normal"] == [0, 1, 0])
            hole = {"features": part["features"] + [{"id": "H1", "type": "hole", "plane": {"face": {"name": top["name"]}, "frame": top["frame"]},
                                                     "points": [[0, 0]], "d": 2, "depth": 4, "through": False}]}
            holed = doc.rebuild(hole)
            back = K.volume(K.from_step(doc.export(hole, "step")))
            _, dm1, _ = self._solid_of("stepcode/dm1-id-214.stp", tmp)
            dm1_flat = [f for f in doc.rebuild(dm1)["body"]["faces"] if f.get("type") == "plane"]
        self.assertEqual(len(flat), 6)
        self.assertTrue(holed["ok"], holed["features"])
        self.assertAlmostEqual(built["body"]["volume"] - holed["body"]["volume"], math.pi * 4, delta=1e-4)
        self.assertAlmostEqual(back, holed["body"]["volume"], delta=1e-4)
        self.assertEqual(len(dm1_flat), 35)

    def test_a_cut_on_a_bspline_solid_takes_material_off(self):
        """Reespirator's balloon (one B-spline solid of 8 faces): a Ø3 × 1 cut raised its volume by ~4 000 mm³ — not a
        wrong orientation but the volume's quick integration rule, hundreds of mm³ off on B-spline faces. Now the volume
        goes down by what the cut takes (the common of the solid and the cutter, the same rule)."""
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
        from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
        tree = K.read_step_tree(self.sample("freecad-library/Reespirator23 v7.step").read_bytes())
        balloon = next(p["shape"] for p in tree["parts"].values() if p["name"] == "balloon")
        before = K.volume(balloon)
        for z0 in (62.0, 63.0, 63.5):  # (cutters reaching into the balloon's side, 1 mm into it and more)
            tool = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 145.5, z0), gp_Dir(0, 0, 1)), 1.5, 3).Shape()
            took = K.volume(K.bop("common", balloon, tool).Shape())
            after = K.volume(K.bop("cut", balloon, tool).Shape())
            self.assertGreater(took, 0)
            self.assertAlmostEqual(before - after, took, delta=before * 2e-6)  # (the volume's precision on B-splines)

    def test_a_smooth_edge_says_why_it_cannot_be_rounded(self):
        """NIST FTC-07: every fillet tried on the longest edges of its biggest faces was refused "cannot be rounded here
        (whatever the size)" — those edges are smooth (a flat face running into a rounding): the message says so now; a
        sharp edge of it rounds."""
        with tempfile.TemporaryDirectory() as tmp:
            _, part, _ = self._solid_of("nist/nist_ftc_07_asme1_rd.stp", tmp)
            built = doc.rebuild(part)
            faces, edges = built["body"]["faces"], built["body"]["edges"]
            ref = lambda e: {"a": faces[e["faces"][0]]["name"], "b": faces[e["faces"][1]]["name"], "fp": e["mid"]}  # noqa: E731
            pair = lambda e: {faces[i]["type"] for i in e["faces"]}  # noqa: E731
            st, _ = doc.evaluate(part["features"])
            smooth = next(e for e in edges if len(e["faces"]) == 2 and pair(e) == {"plane", "cylinder"}
                          and K.smooth_edges(st.body, K.find_edges(st.body, [ref(e)])[0]))
            sharp = next(e for e in edges if len(e["faces"]) == 2 and pair(e) == {"plane"}
                         and abs(sum(a * b for a, b in zip(faces[e["faces"][0]]["normal"], faces[e["faces"][1]]["normal"]))) < 0.9)
            r1 = doc.rebuild({"features": part["features"] + [{"id": "R1", "type": "fillet", "edges": [ref(smooth)], "r": 0.3}]})
            r2 = doc.rebuild({"features": part["features"] + [{"id": "R1", "type": "fillet", "edges": [ref(sharp)], "r": 0.3}]})
        self.assertFalse(r1["ok"])
        self.assertIn("This edge is smooth", r1["features"][-1]["issues"][0])
        self.assertTrue(r2["ok"], r2["features"][-1])
        self.assertLess(r2["body"]["volume"], built["body"]["volume"])

    def test_an_iges_of_several_bodies_opens_as_solids(self):
        """An IGES assembly of surfaces (SolidWorks' valve, EUCLID's hammer) came in only as a reference body: one open
        piece kept every body from closing. Now each piece that closes is a solid, the rest stay loose faces shown for
        reference (how "partly"); a model drawn huge (the hammer) is sewn again at 1 / 10 000 of its size."""
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
        a = BRepPrimAPI_MakeBox(gp(0, 0, 0), 10, 10, 10).Shape()
        b = BRepPrimAPI_MakeBox(gp(20, 0, 0), 5, 5, 5).Shape()
        lid = K.compound([f for f in K._subshapes(BRepPrimAPI_MakeBox(gp(40, 0, 0), 4, 4, 4).Shape(), K.TopAbs_FACE)][:5])  # (an open box)
        shape, _, how = K.read_iges(K.to_iges(K.compound([a, b, lid]), surfaces=True))
        self.assertEqual(how, "partly")
        self.assertEqual(K.solids(shape), 2)
        self.assertAlmostEqual(K.volume(shape), 1000 + 125, delta=1e-6)
        self.assertEqual(K.face_count(K.loose_faces(shape)), 5)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(blobs, "DIR", Path(tmp)):
            r = doc.import_solid({"blob": blobs.put(K.to_iges(K.compound([a, b, lid]), surfaces=True)), "name": "three.igs"})
            built = doc.rebuild({"features": [{"id": "F1", "type": "solid", "blob": r["blob"], "file": "three.igs", "op": "add"}]})
        self.assertNotIn("op", r)
        self.assertIn("2 closed solid(s); 5 face(s)", r["warning"])
        self.assertAlmostEqual(built["body"]["volume"], 1125, delta=1e-6)
        self.assertEqual([x["id"] for x in built["refs"]], ["F1:surfaces"])
        hammer, _, how = K.read_iges(self.sample("occt/hammer.iges").read_bytes())
        self.assertEqual((how, K.solids(hammer)), ("sewn", 1))

    def test_external_references_open_with_their_files(self):
        """CATIA's S1: an assembly whose parts are STEP files of their own (external references) said "no solid". Alone
        it says which files it needs; picked together with them it opens: 8 parts placed 11 times."""
        p = self.sample("stepcode/s1-c5-214/s1-c5-214.stp")
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(blobs, "DIR", Path(tmp)):
            with self.assertRaises(K.KernelError) as cm:
                doc.import_solid({"blob": blobs.put(p.read_bytes()), "name": p.name})
            files = {f.name: blobs.put(f.read_bytes()) for f in sorted(p.parent.iterdir()) if f.name != "HEAD_BACK.stp"}
            with self.assertRaises(K.KernelError) as cm2:  # (one part file missing: named)
                doc.import_solid({"files": files})
            files["HEAD_BACK.stp"] = blobs.put((p.parent / "HEAD_BACK.stp").read_bytes())
            r = doc.import_solid({"files": dict(reversed(list(files.items())))})  # (the top file found whatever the order)
            imp = doc.import_assembly({"blob": r["blob"], "name": r["name"]})
        self.assertIn("refers to 4 part file(s) of its own (TAIL.stp, HEAD.stp, MAINBODY.stp, FOOT.stp)", str(cm.exception))
        self.assertIn("HEAD_BACK.stp", str(cm2.exception))
        self.assertEqual(r["name"], "s1-c5-214.stp")
        self.assertEqual(r["structure"], {"parts": 8, "placements": 11, "subs": 4})
        self.assertGreater(r["volume"], 0)
        self.assertEqual((len(imp["parts"]), total(imp)[1]), (8, 11))
        self.assertAlmostEqual(total(imp)[0], r["volume"], delta=r["volume"] * 1e-6)


def gp(x, y, z):
    from OCP.gp import gp_Pnt
    return gp_Pnt(x, y, z)


def on_face(mesh, face):
    """A point well inside a flat face (the middle of its roundest triangle — its centre may be in a hole) as (u, v) of
    the face's sketch frame."""
    import numpy as np
    tri = np.frombuffer(mesh["positions"], np.float32).reshape(-1, 3, 3).astype(float)
    ids = np.frombuffer(mesh["face_ids"], np.uint32)
    t = tri[ids == face["id"]]
    a, b, c = (np.linalg.norm(t[:, i] - t[:, (i + 1) % 3], axis=1) for i in range(3))
    s = (a + b + c) / 2
    best = t[int(np.argmax(np.sqrt(np.maximum(s * (s - a) * (s - b) * (s - c), 0)) / s))].mean(axis=0)
    fr = face["frame"]
    o, x, n = (np.asarray(fr[k], float) for k in ("o", "x", "n"))
    return [float((best - o) @ x), float((best - o) @ np.cross(n, x))]


def open_edges(mesh):
    """How many triangle edges of a tessellated body have no partner the other way round (0: a closed mesh)."""
    import numpy as np
    from collections import Counter
    tri = np.frombuffer(mesh["positions"], np.float32).reshape(-1, 3, 3) if isinstance(mesh["positions"], bytes) else None
    edges = Counter()
    for a, b, c in np.round(tri.astype(float), 4).tolist():
        for p, q in ((a, b), (b, c), (c, a)):
            edges[(tuple(p), tuple(q))] += 1
    return sum(1 for (p, q), k in edges.items() if edges.get((q, p), 0) != k)


if __name__ == "__main__":
    unittest.main()
