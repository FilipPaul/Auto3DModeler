"""Exact print pieces (auto3d/printexact.py, modeler/printsplit.py): a 3D model part's printing copy (a STEP quick
part) split for the printer is cut from the exact solid — smooth curved walls, few faces, exact volumes, the joints'
pockets as B-rep prisms; STL / STEP files from it. Parts without an exact model (an STL, 3D objects added, no kernel)
keep the slab pieces as before. Skipped when the kernel is not installed.

Run:  py -m unittest tests.test_print_exact -v
"""
import io
import math
import unittest
import zipfile
from unittest import mock

import numpy as np

from auto3d import printexact
from auto3d.meshpart import mesh_model, solve_mesh
from auto3d.modeler import available
from auto3d.printing import plan

from test_design_print import mesh_stats

OCC = available("occ")
if OCC:
    from auto3d.modeler import doc, kernel as K, printsplit
    from test_modeler_kernel import watertight

P200 = {"id": "p200", "name": "P200", "x": 200, "y": 200, "z": 200}
R, L = 50.0, 300.0
V = math.pi * R * R * L
DOWEL_POCKET = 15.2 * 8.4 * 4.4  # half of a 30 × 8 × 4 pin's pocket (0.2 clearance all round) in each piece


class Local:
    """The kernel worker, run in this process."""

    def run(self, op, arg, timeout=0):
        return {"print_pieces": printsplit.pieces}[op](arg)


class Broken:
    def run(self, op, arg, timeout=0):
        from auto3d.modeler.worker import KernelFailed
        raise KernelFailed("The CAD kernel failed (test).")


def cylinder_step(d=100.0, length=300.0):
    """A round bar Ø d × length lying along x (a 3D model part) as its STEP."""
    part = {"features": [
        {"id": "S1", "type": "sketch", "name": "S1", "plane": {"datum": "YZ"},
         "entities": [{"id": "c", "t": "circle", "cx": 0, "cy": d / 2, "d": d}]},
        {"id": "E1", "type": "extrude", "name": "E1", "sketch": "S1", "op": "add", "d": length}]}
    return doc.export(part, "step")


def tris_of(g):
    return np.frombuffer(g["positions"], np.float32).reshape(-1, 3, 3).astype(float)


@unittest.skipUnless(OCC, "OCP not installed")
class ExactPrintSplitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = mesh_model(cylinder_step(), "bar (print).step")
        cls.sol, cls.solid = solve_mesh(cls.model)
        cls.src = printexact.source(cls.model, cls.sol)

    def split(self, joint=None, out="mesh", src=None, worker=None):
        res = plan(self.solid, "mm", P200, 0, True, joint)
        got = printexact.cut(res, src or self.src, worker or Local(), out)
        return res, got

    def test_cylinder_in_two_exact_pieces(self):
        """Ø100 × 300 on a 200 mm bed: 2 pieces, their volumes add up to π r² L, each one watertight solid of 3 faces
        (the round wall, its end, the flat cut) — the slab pieces have thousands; both fit the bed."""
        res, got = self.split()
        self.assertTrue(res["exact"])
        self.assertEqual(len(res["pieces"]), 2)
        self.assertAlmostEqual(sum(g["volume"] for g in got), V, delta=1e-3)
        for p, g in zip(res["pieces"], got):
            self.assertAlmostEqual(g["volume"], V / 2, delta=1e-3)
            self.assertEqual(g["solids"], 1)
            self.assertEqual(g["faces"], 3)
            self.assertTrue(watertight(g))
            self.assertGreater(len(list(p["solid"].faces())), 1000)  # the slab piece it replaces: stairs
            self.assertEqual(p["orientation"], "flat")
            self.assertEqual(p["exact"]["faces"], 3)
            for v, want in zip(p["size_mm"], (150, 100, 100)):
                self.assertAlmostEqual(v, want, delta=1e-6)
        self.assertIn("Exact split", res["issues"][0]["message"])

    def test_no_stairs(self):
        """Every mesh vertex lies on the true cylinder (or on its flat ends), the round wall's triangles stay within the
        tessellation tolerance of it; the slab pieces' vertices are up to 0.25 mm off (steps of 0.5 mm)."""
        res, got = self.split()
        for p, g in zip(res["pieces"], got):
            t = tris_of(g)
            r = np.hypot(t[..., 1] - R, t[..., 2] - R)
            self.assertLess(np.abs(r - R).max(), 1e-4)  # (the float32 mesh)
            n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
            wall = np.abs(n[:, 0]) < 0.5 * np.linalg.norm(n, axis=1)
            c = t[wall].mean(axis=1)
            self.assertLess(np.abs(np.hypot(c[:, 1] - R, c[:, 2] - R) - R).max(), g["tol"])
            self.assertLess(np.count_nonzero(~wall), 600)  # the two flat ends
            slab = np.asarray(p["solid"].triangles()[0], float)
            rs = np.hypot(slab[..., 1] - R, slab[..., 2] - R)
            inner = (slab[..., 0] > 1) & (slab[..., 0] < L - 1)
            self.assertGreater(np.abs(rs[inner] - R).max(), 0.1)

    def test_pin_holes(self):
        """Rectangular dowel pins: each pocket a box half in each piece -> each piece V/2 − pins × 15.2 × 8.4 × 4.4,
        watertight; the pins are connector parts as before."""
        res, got = self.split({"type": "dowel"})
        pins = sum(len(g["instances"]) for g in res["connectors"])
        self.assertEqual(pins, 2)
        for g in got:
            self.assertAlmostEqual(g["volume"], V / 2 - pins * DOWEL_POCKET, delta=1e-3)
            self.assertTrue(watertight(g))
            self.assertEqual(g["solids"], 1)
            self.assertLess(g["faces"], 20)
        pin = res["connectors"][0]["instances"][0]["solid"]
        self.assertAlmostEqual(pin.volume(), 30 * 8 * 4, delta=1e-6)

    def test_every_joint(self):
        """Dovetails, hidden dovetails, puzzle knobs, butterfly keys, splice plates, glue ports: the exact pieces are
        watertight single solids whose volumes match the slab pieces' (cut by the same polygons) to 0.01 %."""
        for joint in ("dovetail", "hidden_dovetail", "puzzle", "butterfly", "plate", "none"):
            with self.subTest(joint=joint):
                res, got = self.split({"type": joint})
                self.assertTrue(res.get("exact"))
                for p, g in zip(res["pieces"], got):
                    self.assertEqual(g["solids"], 1)
                    self.assertTrue(watertight(g))
                    self.assertAlmostEqual(g["volume"], p["solid"].volume(), delta=1e-4 * g["volume"])

    def test_files(self):
        """The STEP of each piece reads back with its volume, its corner at the origin; a piece printed upside down
        (the splice plate's recess on the back) is turned over; the STL is the fine mesh."""
        res, got = self.split({"type": "plate"}, out="step")
        self.assertTrue(all(p["flip"] for p in res["pieces"]))
        for g in got:
            shape = K.from_step(g["data"])
            self.assertAlmostEqual(K.volume(shape), g["volume"], delta=1e-3)
            bb = K.bbox(shape)
            for v in bb[:3]:
                self.assertAlmostEqual(v, 0, delta=1e-6)
        # the recess (3 deep, on the bottom where the piece lies in the part) is on top as printed
        layer = lambda shape, z0, z1: K.volume(K.boolean("common", [shape], K.prisms([[[[-1, -1], [400, -1], [400, 400], [-1, 400]]]], z0, z1)))
        printed = K.from_step(got[0]["data"])
        self.assertLess(layer(printed, 97, 101), layer(printed, -1, 3) - 100)
        res, got = self.split(out="stl")
        for g in got:
            stl = g["data"]
            self.assertEqual(int.from_bytes(stl[80:84], "little"), len(g["positions"]) // 36)

    def test_prisms_with_a_hole(self):
        """A B-rep prism of a shapely polygon with a hole (outer ring anticlockwise, the hole clockwise)."""
        ring = [[0, 0], [10, 0], [10, 10], [0, 10]]
        hole = [[3, 3], [3, 7], [7, 7], [7, 3]]
        (s,) = K.prisms([[ring, hole]], 2, 7)
        self.assertAlmostEqual(K.volume(s), (100 - 16) * 5, delta=1e-9)

    def test_scaled_and_turned(self):
        """The quick part at 50 %, turned by 90° about z (the bar along y): the exact pieces follow the slices' turn and
        scale — Ø50 × 150 on a 100 mm bed: two pieces 50 × 75 × 50, π 25² 150 together."""
        model = {**self.model, "mesh_opts": {**self.model["mesh_opts"], "rot": 90}}
        model["params"] = [{**p, "value": 50.0} if p["id"] == "scale" else p for p in model["params"]]
        sol, solid = solve_mesh(model)
        src = printexact.source(model, sol)
        self.assertAlmostEqual(src["k"], 0.5)
        res = plan(solid, "mm", {**P200, "x": 100, "y": 100}, 0, True, None)
        got = printexact.cut(res, src, Local())
        self.assertEqual(len(got), 2)
        self.assertAlmostEqual(sum(g["volume"] for g in got), V / 8, delta=1e-3)
        for p in res["pieces"]:
            w, h, z = p["size_mm"]
            self.assertAlmostEqual(w, 50, delta=1e-6)
            self.assertAlmostEqual(h, 75, delta=1e-6)
            self.assertAlmostEqual(z, 50, delta=1e-6)

    def test_fallback(self):
        """No exact model -> None (the slab pieces stay): an STL, a STEP part with 3D objects added, a bent part, no
        kernel; a kernel that fails -> the slab pieces with a warning."""
        from test_import import box_stl
        stl = mesh_model(box_stl(40, 20, 5), "box.stl")
        self.assertIsNone(printexact.source(stl, solve_mesh(stl)[0]))
        self.assertIsNone(printexact.source({**self.model, "extras": [{"id": "o1"}]}, self.sol))
        self.assertIsNone(printexact.source(self.model, self.sol, bender=object()))
        with mock.patch("auto3d.modeler.available", return_value=False):
            self.assertIsNone(printexact.source(self.model, self.sol))
        res, got = self.split(worker=Broken())
        self.assertIsNone(got)
        self.assertNotIn("exact", res)
        self.assertTrue(any("did not work" in i["message"] for i in res["issues"]))
        self.assertTrue(all(mesh_stats(p["solid"])[1] == 0 for p in res["pieces"]))


@unittest.skipUnless(OCC, "OCP not installed")
class ExactPrintServerTest(unittest.TestCase):
    """/api/print/plan and /api/export through the server (its kernel worker): the STEP part's pieces are exact, an STL
    part's are the slab pieces as before."""

    @classmethod
    def setUpClass(cls):
        import server
        cls.client = server.app.test_client()

    def body(self, model, **kw):
        return {"model": model, "values": {}, "layers": [], "printer": "bambulab-p1s", "margin": 5, "split": True, **kw}

    def test_plan_and_export(self):
        long = mesh_model(cylinder_step(100, 400), "long (print).step")
        r = self.client.post("/api/print/plan", json=self.body(long)).get_json()
        self.assertTrue(r.get("exact"), r.get("issues"))
        self.assertEqual(len(r["pieces"]), 2)
        for p in r["pieces"]:
            self.assertEqual(p["exact"]["faces"], 3)
            self.assertEqual(p["mesh"]["count"], p["exact"]["triangles"])
            self.assertNotIn("cell_region", p)
            self.assertEqual(p["orientation"], "flat")
        self.assertAlmostEqual(sum(p["exact"]["volume"] for p in r["pieces"]), math.pi * 50 * 50 * 400, delta=1e-3)
        res = self.client.post("/api/export/step", json=self.body(long))
        z = zipfile.ZipFile(io.BytesIO(res.data))
        steps = [n for n in z.namelist() if n.endswith(".step")]
        self.assertEqual(len(steps), 2)
        self.assertAlmostEqual(sum(K.volume(K.from_step(z.read(n))) for n in steps), math.pi * 50 * 50 * 400, delta=1e-3)
        # the whole part (no split): the exact solid too
        res = self.client.post("/api/export/step", json=self.body(long, split=False))
        self.assertAlmostEqual(K.volume(K.from_step(res.data)), math.pi * 50 * 50 * 400, delta=1e-3)

    def test_stl_part_unchanged(self):
        from test_import import box_stl
        box = mesh_model(box_stl(400, 20, 5), "box.stl")
        r = self.client.post("/api/print/plan", json=self.body(box)).get_json()
        self.assertNotIn("exact", r)
        self.assertEqual(len(r["pieces"]), 2)
        self.assertTrue(all("exact" not in p and p["mesh"]["count"] > 0 for p in r["pieces"]))
        self.assertFalse(any("Exact" in i["message"] for i in r["issues"]))


if __name__ == "__main__":
    unittest.main()
