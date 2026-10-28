"""Drawing sheets that cannot be made say why, readably (422 with the reason, not a bare 500): a reference body, a body
with no box (a tessellated STEP); an exact drawing that takes too long is stopped and drawn from the mesh; a big
assembly is drawn from its mesh at once (MIT E-Vent's exact top view never ended); Cancel answers 409."""
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from auto3d.modeler import available

OCC = available("occ")
if OCC:
    from auto3d.modeler import blobs, doc, kernel as K, sheet as S

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples" / "ToImportToOurApp"


def box(w=40, d=20, h=10):
    pts = {"p1": [0, 0], "p2": [w, 0], "p3": [w, d], "p4": [0, d]}
    lines = [{"id": f"l{i + 1}", "t": "line", "a": f"p{i + 1}", "b": f"p{(i + 1) % 4 + 1}"} for i in range(4)]
    return {"features": [{"id": "S1", "type": "sketch", "plane": {"datum": "XY"}, "points": pts, "entities": lines},
                         {"id": "E1", "type": "extrude", "sketch": "S1", "op": "add", "d": h}]}


@unittest.skipUnless(OCC, "OCP not installed")
class TestSheetErrors(unittest.TestCase):
    def test_reference_body_says_why(self):
        """An IGES of surfaces that do not close (a reference body): no solid to draw — said so (it said "sketch a
        shape and extrude it")."""
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(blobs, "DIR", Path(tmp)):
            r = doc.import_solid({"blob": blobs.put((SAMPLES / "occt" / "hammer.iges").read_bytes()), "name": "hammer.iges"})
            self.assertEqual(r["op"], "ref")
            part = {"features": [{"id": "F1", "type": "solid", "blob": r["blob"], "file": "hammer.iges", "op": "ref"}]}
            with self.assertRaisesRegex(K.KernelError, "only a reference body"):
                doc.sheet(part)

    def test_no_box_says_why(self):
        """A body whose box is void (a tessellated STEP's faces) is not drawn: a clear message, not a TypeError."""
        class Flat:
            shape = K.compound([])
            names = {}
        with self.assertRaisesRegex(K.KernelError, "no size to draw"):
            S.geometry(Flat())
        p = SAMPLES / "nist" / "nist_ftc_08_asme1_ap242-e1-tg.stp"  # (NIST's tessellated AP242)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(blobs, "DIR", Path(tmp)):
            r = doc.import_solid({"blob": blobs.put(p.read_bytes()), "name": p.name})
            part = {"features": [{"id": "F1", "type": "solid", "blob": r["blob"], "file": p.name, "op": "add"}]}
            with self.assertRaisesRegex(K.KernelError, "no size to draw"):
                doc.sheet(part)

    def test_big_assembly_drawn_from_its_mesh(self):
        """An assembly over ASSEMBLY_EXACT_FACES faces is drawn from its mesh (geometry.simple, no hidden lines); a
        small one exactly; the parts' balloons either way."""
        part = box()
        insts = [{"id": f"I{k}", "part": part, "matrix": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 50 * k, 0, 0, 1]} for k in range(3)]
        exact = doc.assembly_sheet(insts)
        self.assertNotIn("simple", exact["geometry"])
        self.assertTrue(exact["geometry"]["views"]["Front"]["visible"])
        with mock.patch.object(S, "ASSEMBLY_EXACT_FACES", 10):  # (3 boxes: 18 faces)
            rough = doc.assembly_sheet(insts, explode=0.5)
        self.assertIn("simple", rough["geometry"])
        self.assertEqual(rough["geometry"]["views"]["Front"]["hidden"], [])
        self.assertEqual(sorted(rough["marks"]), ["I0", "I1", "I2"])
        bb = rough["geometry"]["bbox"]
        self.assertAlmostEqual(bb[3] - bb[0], 140, delta=0.5)  # (3 boxes 40 long, 50 apart)
        # a part asked to be drawn from its mesh (the server's fallback)
        r = doc.sheet(part, simple=True)
        self.assertIn("simple", r["geometry"])
        self.assertAlmostEqual(r["geometry"]["bbox"][3] - r["geometry"]["bbox"][0], 40, delta=0.1)


@unittest.skipUnless(OCC, "OCP not installed")
class TestSheetRoutes(unittest.TestCase):
    def setUp(self):
        import server
        self.server = server
        self.c = server.app.test_client()

    def test_readable_errors(self):
        """A part that cannot be drawn: 422 with the kernel's reason; nothing to draw in an assembly: 422 too."""
        r = self.c.post("/api/sheet/build", json={"part": {"features": []}})
        self.assertEqual(r.status_code, 422)
        self.assertIn("no solid", r.get_json()["error"])
        r = self.c.post("/api/sheet/assembly", json={"instances": []})
        self.assertEqual((r.status_code, r.get_json()["error"]), (422, "The assembly has no solids to draw."))

    def test_too_slow_exact_drawing_falls_back_to_the_mesh(self):
        """The exact drawing over its limit is stopped (the kernel process killed) and made again from the mesh."""
        pool, run, asked = self.server.MODEL_WORKER, self.server.MODEL_WORKER.run, []

        def slow_exact(op, arg, timeout=120, key=...):  # (the exact pass "takes too long", as the worker says)
            asked.append((op, bool(arg.get("simple")), timeout))
            if not arg.get("simple"):
                raise self.server.KernelFailed(f"Building took longer than {timeout} s and was stopped.")
            return run(op, arg, timeout, key)
        with mock.patch.object(pool, "run", slow_exact):
            t0 = time.time()
            r = self.c.post("/api/sheet/build", json={"part": box(30, 30, 5), "rid": "test-sheet-fallback"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertIn("simple", r.get_json()["geometry"])
        self.assertEqual(asked, [("sheet", False, self.server.EXACT_SHEET_TIMEOUT), ("sheet", True, self.server.SHEET_TIMEOUT)])
        self.assertLess(time.time() - t0, 120)
        ok = self.c.post("/api/sheet/build", json={"part": box(30, 30, 5)})  # (and exactly when there is time)
        self.assertNotIn("simple", ok.get_json()["geometry"])

    def test_cancel(self):
        """Cancelled (the page's busy box): 409, the sheet says so — no error toast."""
        from auto3d import progress

        def cancelled():
            raise progress.Cancelled()
        with mock.patch.object(progress, "check", cancelled):
            r = self.c.post("/api/sheet/build", json={"part": box(), "rid": "test-sheet-cancel"})
        self.assertEqual(r.status_code, 409)
        self.assertTrue(r.get_json()["cancelled"])


if __name__ == "__main__":
    unittest.main()
