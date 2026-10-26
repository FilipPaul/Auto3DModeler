"""Progress / cancel of slow work, the automatic slice height of curved imports, and the features the
measure tool recognises (holes, cylinders, faces).

Run:  python -m unittest discover -s tests -v
"""
import math
import threading
import time
import unittest

import numpy as np

from auto3d import progress
from auto3d.importers import auto_layer, orient, slice_mesh
from auto3d.outline import outline_model, solve_outline


def torus(R=30, r=10, nu=160, nv=80):
    u = np.linspace(0, 2 * np.pi, nu, endpoint=False)
    v = np.linspace(0, 2 * np.pi, nv, endpoint=False)
    U, V = np.meshgrid(u, v, indexing="ij")
    P = np.stack([(R + r * np.cos(V)) * np.cos(U), (R + r * np.cos(V)) * np.sin(U), r * np.sin(V)], -1)
    i, j = np.meshgrid(np.arange(nu), np.arange(nv), indexing="ij")
    a, b, c, d = P[i, j], P[(i + 1) % nu, j], P[(i + 1) % nu, (j + 1) % nv], P[i, (j + 1) % nv]
    return orient(np.concatenate([np.stack([a, b, c], -2).reshape(-1, 3, 3), np.stack([a, c, d], -2).reshape(-1, 3, 3)]))


class TestProgress(unittest.TestCase):
    def test_report_and_cancel_while_slicing(self):
        tris = torus()
        rid = "t1"
        seen, out = [], {}

        def work():
            try:
                with progress.operation(rid):
                    out["slabs"] = slice_mesh(tris, 0.05)  # 400 slices
            except progress.Cancelled:
                out["cancelled"] = True

        th = threading.Thread(target=work)
        th.start()
        for _ in range(200):
            st = progress.status(rid)
            if st.get("total") and st["done"] > 5:
                seen.append(st)
                break
            time.sleep(0.01)
        progress.cancel(rid)
        th.join(30)
        self.assertTrue(seen and seen[0]["stage"] == "Slicing" and seen[0]["total"] == 400, seen)
        self.assertTrue(out.get("cancelled"))
        self.assertTrue(progress.status(rid)["finished"])

    def test_no_op_outside_an_operation(self):
        progress.report("anything", 1, 2)  # no request: nothing happens
        progress.check()

    def test_auto_layer(self):
        layer, count, stepped = auto_layer(torus(), target=50)
        self.assertTrue(stepped)
        self.assertLessEqual(count, 50)
        self.assertGreaterEqual(layer, 0.5)
        flat = orient(np.array([[[0, 0, 0], [10, 0, 0], [10, 10, 0]], [[0, 0, 0], [10, 10, 0], [0, 10, 0]],
                                [[0, 0, 5], [10, 10, 5], [10, 0, 5]], [[0, 0, 5], [0, 10, 5], [10, 10, 5]]], float))
        self.assertEqual(auto_layer(flat)[0], 0.5)  # nothing slanted: nothing to choose

    def test_sliced_torus_volume(self):
        slabs, stepped = slice_mesh(torus(), 0.25)
        vol = sum((z1 - z0) * s.area for z0, z1, s in slabs)
        exact = 2 * math.pi ** 2 * 30 * 10 ** 2
        self.assertAlmostEqual(vol, exact, delta=exact * 0.01)


class TestFeatures(unittest.TestCase):
    def test_holes_cylinders_faces(self):
        poly = [[[10, 10], [110, 10], [110, 60], [10, 60]]]
        m = {**outline_model([poly], 200, 100, width=100), "preset": "solid", "preset_opts": {"thickness": 5, "offset": 0}}
        m["extras"] = [{"source": "circle", "x": 30, "y": 25, "w": 10, "h": 10, "z0": 0, "z1": 5, "op": "subtract", "id": "H"},
                       {"source": "circle", "x": 70, "y": 25, "w": 8, "h": 8, "z0": 5, "z1": 12, "op": "union", "id": "P"},
                       {"source": "rect", "x": 50, "y": 45, "w": 6, "h": 6, "z0": 0, "z1": 5, "op": "subtract", "id": "S"}]
        _, solid = solve_outline(m)
        f = solid.features()
        holes = [c for c in f["circles"] if c["hole"]]
        bosses = [c for c in f["circles"] if not c["hole"]]
        self.assertEqual(len(holes), 1)   # the square hole is not a circle
        self.assertEqual(len(bosses), 1)
        self.assertAlmostEqual(holes[0]["r"], 5, places=3)
        self.assertEqual((holes[0]["x"], holes[0]["y"], holes[0]["z0"], holes[0]["z1"]), (30, 25, 0, 5))
        self.assertAlmostEqual(bosses[0]["r"], 4, places=3)
        self.assertEqual((bosses[0]["z0"], bosses[0]["z1"]), (5, 12))
        top = [x for x in f["faces"] if x["up"] and x["z"] == 5][0]
        circle = math.pi * 25 * (1 - 0.0004)  # a 128-gon (32 segments per quarter)
        self.assertAlmostEqual(top["area"], 5000 - circle - 36 - math.pi * 16 * (1 - 0.0004), delta=0.05)


class TestServerCancel(unittest.TestCase):
    def test_cancel_a_rebuild(self):
        import io
        import struct

        import server
        c = server.app.test_client()
        tris = torus().astype(np.float32)
        stl = bytearray(b"torus".ljust(80, b" ")) + struct.pack("<I", len(tris))
        for t3 in tris:
            stl += struct.pack("<3f", 0, 0, 0) + t3.tobytes() + b"\0\0"
        model = c.post("/api/import", data={"file": (io.BytesIO(bytes(stl)), "torus.stl"), "rid": "imp"},
                       content_type="multipart/form-data").get_json()["model"]
        model["mesh_opts"]["layer"] = 0.02  # 1000 slices: slow enough to cancel
        out = {}
        th = threading.Thread(target=lambda: out.update(r=c.post("/api/solve", json={"model": model, "values": {}, "rid": "cx"}).get_json()))
        th.start()
        for _ in range(500):
            if c.get("/api/progress/cx").get_json().get("total"):
                break
            time.sleep(0.01)
        self.assertEqual(c.post("/api/progress/cx/cancel").get_json(), {"ok": True})
        th.join(60)
        self.assertTrue(out["r"].get("cancelled"), out["r"])


if __name__ == "__main__":
    unittest.main()
