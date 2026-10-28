"""Exchange formats for other CAD programs (SolidWorks, CATIA, Solid Edge …) beside STEP: IGES in and out (a part, an
assembly as one file; surfaces-only files sewn into a solid, or a reference body when they do not close).
Skipped without the CAD kernel.
"""
import math
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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


if __name__ == "__main__":
    unittest.main()
