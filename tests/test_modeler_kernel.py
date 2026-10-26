"""3D model parts (sketch -> extrude) on the OpenCASCADE kernel: exact volumes, holes from nested sketch
shapes, sketches on faces that follow their face, cut through all, symmetric extrudes, failing steps,
STEP / STL export, watertight meshes and the rebuild cache. Skipped when the kernel is not installed
(`py -m pip install -r requirements-modeler.txt`).

Run:  python -m unittest discover -s tests -v
"""
import math
import time
import unittest
from collections import Counter

import numpy as np

from auto3d.modeler import available

OCC = available("occ")
if OCC:
    from auto3d.modeler import doc, kernel


def sketch(fid, entities, plane=None):
    return {"id": fid, "type": "sketch", "name": fid, "plane": plane or {"datum": "XY"}, "entities": entities}


def extrude(fid, sk, d=10, op="add", **kw):
    return {"id": fid, "type": "extrude", "name": fid, "sketch": sk, "op": op, "d": d, **kw}


RECT = {"id": "e1", "t": "rect", "cx": 20, "cy": 10, "w": 40, "h": 20}


def watertight(body):
    """Every triangle edge is shared by exactly two triangles (vertices compared after rounding)."""
    tri = np.frombuffer(body["positions"], np.float32).reshape(-1, 3, 3)
    keys = np.round(tri.astype(float), 4)
    edges = Counter()
    for t in keys:
        for a, b in ((0, 1), (1, 2), (2, 0)):
            edges[tuple(sorted((tuple(t[a]), tuple(t[b]))))] += 1
    return all(c == 2 for c in edges.values())


@unittest.skipUnless(OCC, "OCP not installed")
class TestModelKernel(unittest.TestCase):
    def rebuild(self, *features):
        return doc.rebuild({"features": list(features)})

    def test_box(self):
        r = self.rebuild(sketch("S1", [RECT]), extrude("E1", "S1", 10))
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(r["body"]["volume"], 8000, delta=8000 * 1e-6)
        self.assertEqual([round(v, 6) for v in r["body"]["bbox"]], [0, 0, 0, 40, 20, 10])
        self.assertEqual(len(r["body"]["faces"]), 6)
        self.assertEqual(len(r["body"]["edges"]), 12)
        self.assertTrue(watertight(r["body"]))
        ids = np.frombuffer(r["body"]["face_ids"], np.uint32)
        self.assertEqual(len(ids) * 9 * 4, len(r["body"]["positions"]))  # one face id per triangle
        top = [f for f in r["body"]["faces"] if f.get("normal") == [0, 0, 1]][0]
        self.assertEqual(top["ref"], {"name": "E1:end"})
        self.assertEqual(top["frame"]["o"], [20, 10, 10])
        bottom = [f for f in r["body"]["faces"] if f.get("normal") == [0, 0, -1]][0]
        self.assertEqual(bottom["ref"], {"name": "E1:start"})

    def test_circle_inside_is_a_hole(self):
        hole = {"id": "e2", "t": "circle", "cx": 20, "cy": 10, "d": 6}
        island = {"id": "e3", "t": "circle", "cx": 20, "cy": 10, "d": 2}
        r = self.rebuild(sketch("S1", [RECT, hole]), extrude("E1", "S1", 10))
        self.assertAlmostEqual(r["body"]["volume"], 8000 - math.pi * 9 * 10, delta=1e-3)
        self.assertTrue(watertight(r["body"]))
        self.assertIn(3.0, [f.get("radius") for f in r["body"]["faces"]])
        r = self.rebuild(sketch("S1", [RECT, hole, island]), extrude("E1", "S1", 10))  # even-odd: an island
        self.assertAlmostEqual(r["body"]["volume"], 8000 - math.pi * 9 * 10 + math.pi * 10, delta=1e-3)
        self.assertEqual(r["body"]["solids"], 2)

    def test_sketch_on_face_follows_it(self):
        base = [sketch("S1", [RECT]), extrude("E1", "S1", 10)]
        top = [f for f in self.rebuild(*base)["body"]["faces"] if f.get("normal") == [0, 0, 1]][0]
        plane = {"face": top["ref"], "frame": top["frame"]}
        pocket = [sketch("S2", [{"id": "c", "t": "circle", "cx": 0, "cy": 0, "d": 6}], plane), extrude("E2", "S2", 4, "cut")]
        r = self.rebuild(*base, *pocket)
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(r["body"]["volume"], 8000 - math.pi * 9 * 4, delta=1e-3)
        self.assertEqual(r["frames"]["S2"]["o"], [20, 10, 10])
        # the first extrude gets taller: the pocket stays on the top face
        base[1] = extrude("E1", "S1", 15)
        r = self.rebuild(*base, *pocket)
        self.assertAlmostEqual(r["body"]["volume"], 12000 - math.pi * 9 * 4, delta=1e-3)
        self.assertAlmostEqual(r["frames"]["S2"]["o"][2], 15)
        self.assertTrue(watertight(r["body"]))

    def test_boss_cut_through_and_symmetric(self):
        base = [sketch("S1", [RECT]), extrude("E1", "S1", 10)]
        top = {"face": {"feature": "E1", "role": "end"}, "frame": {"o": [20, 10, 10], "x": [1, 0, 0], "n": [0, 0, 1]}}
        boss = [sketch("S2", [{"id": "c", "t": "circle", "cx": 0, "cy": 0, "d": 8}], top), extrude("E2", "S2", 5)]
        r = self.rebuild(*base, *boss)
        self.assertAlmostEqual(r["body"]["volume"], 8000 + math.pi * 16 * 5, delta=1e-3)
        self.assertEqual(r["body"]["solids"], 1)
        hole = [sketch("S3", [{"id": "c", "t": "circle", "cx": -15, "cy": 0, "d": 4}], top), extrude("E3", "S3", op="cut", through=True)]
        r = self.rebuild(*base, *hole)
        self.assertAlmostEqual(r["body"]["volume"], 8000 - math.pi * 4 * 10, delta=1e-3)
        r = self.rebuild(sketch("S1", [RECT]), extrude("E1", "S1", 10, symmetric=True))
        self.assertEqual([round(v, 6) for v in r["body"]["bbox"]], [0, 0, -5, 40, 20, 5])
        r = self.rebuild(sketch("S1", [RECT], {"datum": "XZ"}), extrude("E1", "S1", 10))
        bb = [round(v, 6) for v in r["body"]["bbox"]]
        self.assertEqual(bb, [0, -10, 0, 40, 0, 20])  # front plane: sketch y = world z, extruded towards the viewer (−y)

    def test_failures_are_issues(self):
        r = self.rebuild(sketch("S1", [RECT]), extrude("E1", "S1", 5, "cut"))
        self.assertFalse(r["ok"])
        self.assertIn("nothing to cut", r["features"][1]["issues"][0])
        r = self.rebuild(sketch("S1", []), extrude("E1", "S1", 5), sketch("S2", [RECT]), extrude("E2", "S2", 2))
        self.assertEqual([s["ok"] for s in r["features"]], [False, False, True, True])
        self.assertIn("no closed shape", r["features"][0]["issues"][0])
        self.assertAlmostEqual(r["body"]["volume"], 1600, delta=1e-3)  # the rest still builds
        r = self.rebuild(sketch("S1", [{**RECT, "w": 0}]), extrude("E1", "S1", 0))
        self.assertIn("greater than zero", r["features"][0]["issues"][0])
        r = self.rebuild(sketch("S1", [RECT]), extrude("E1", "S1", 10, suppressed=True))
        self.assertIsNone(r["body"])
        self.assertTrue(r["features"][1]["suppressed"])

    def test_exports(self):
        part = {"features": [sketch("S1", [RECT, {"id": "e2", "t": "circle", "cx": 20, "cy": 10, "d": 6}]), extrude("E1", "S1", 10)]}
        step = doc.export(part, "step")
        self.assertIn(b"ISO-10303-21", step[:40])
        self.assertAlmostEqual(kernel.volume(kernel.from_step(step)), 8000 - math.pi * 90, delta=1e-3)  # exact circle kept
        stl = doc.export(part, "stl")
        n = int.from_bytes(stl[80:84], "little")
        self.assertEqual(len(stl), 84 + 50 * n)
        with self.assertRaises(kernel.KernelError):
            doc.export({"features": []}, "stl")

    def test_cache_reuses_earlier_steps(self):
        doc._cache.clear()
        f1 = [sketch("S1", [RECT]), extrude("E1", "S1", 10)]
        doc.rebuild({"features": f1})
        self.assertEqual(len(doc._cache), 2)
        f2 = f1 + [sketch("S2", [{"id": "c", "t": "circle", "cx": 0, "cy": 0, "d": 4}],
                          {"face": {"feature": "E1", "role": "end"}, "frame": {"o": [20, 10, 10], "x": [1, 0, 0], "n": [0, 0, 1]}}),
                   extrude("E2", "S2", 3, "cut")]
        doc.rebuild({"features": f2})
        self.assertEqual(len(doc._cache), 4)  # only the two new steps were built and added


@unittest.skipUnless(OCC, "OCP not installed")
class TestModelServer(unittest.TestCase):
    """The HTTP endpoints and the kernel worker process (crash isolation)."""

    PART = {"features": [sketch("S1", [RECT]), extrude("E1", "S1", 10)]}

    def test_rebuild_export_and_worker_restart(self):
        import base64

        import server
        c = server.app.test_client()
        r = c.post("/api/model/rebuild", json={"part": self.PART, "rid": "m1"}).get_json()
        self.assertTrue(r["ok"])
        self.assertAlmostEqual(r["body"]["volume"], 8000, delta=1e-3)
        n = len(base64.b64decode(r["body"]["face_ids"])) // 4
        self.assertEqual(len(base64.b64decode(r["body"]["positions"])), n * 36)
        stl = c.post("/api/model/export/stl", json={"part": self.PART, "name": "Box"})
        self.assertEqual(stl.headers["Content-Disposition"], 'attachment; filename="Box.stl"')
        self.assertEqual(c.post("/api/model/export/step", json={"part": self.PART}).data[:13], b"ISO-10303-21;")
        e = c.post("/api/model/export/stl", json={"part": {"features": []}})
        self.assertEqual(e.status_code, 500)
        self.assertIn("no solid yet", e.get_json()["error"])
        # the kernel process dies: the next call starts a new one
        server.MODEL_WORKER.proc.kill()
        server.MODEL_WORKER.proc.join(10)
        r = c.post("/api/model/rebuild", json={"part": self.PART}).get_json()
        self.assertAlmostEqual(r["body"]["volume"], 8000, delta=1e-3)

    def test_cancel_stops_the_kernel(self):
        import threading

        from auto3d import progress
        from auto3d.modeler.worker import Worker
        w = Worker()
        w.run("rebuild", self.PART)  # started and warm
        pid = w.proc.pid
        # a slow call: many fillet-free but heavy cuts (a 60 x 60 grid of holes)
        holes = [{"id": f"h{i}", "t": "circle", "cx": 1 + (i % 60) * 2, "cy": 1 + (i // 60) * 2, "d": 1} for i in range(3600)]
        big = {"features": [sketch("S1", [{"id": "e1", "t": "rect", "cx": 60, "cy": 60, "w": 122, "h": 122}, *holes]), extrude("E1", "S1", 5)]}
        out = {}

        def go():
            try:
                with progress.operation("mc"):
                    out["r"] = w.run("rebuild", big)
            except progress.Cancelled:
                out["cancelled"] = True

        th = threading.Thread(target=go)
        th.start()
        time.sleep(1.0)
        progress.cancel("mc")
        th.join(30)
        self.assertTrue(out.get("cancelled"), out.keys())
        self.assertIsNone(w.proc)  # stopped
        w.run("rebuild", self.PART)
        self.assertNotEqual(w.proc.pid, pid)
        w.close()


if __name__ == "__main__":
    unittest.main()
