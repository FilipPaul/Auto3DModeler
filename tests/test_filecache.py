"""Big imported files open fast (auto3d/modeler/filecache.py, kernel.tessellate): a file read and meshed once is kept
in the data folder — opened again, its STEP is not read and its solid not meshed, with the same answer, the same mesh
and an exact STEP export; a file changed in place, other code or a damaged entry: read again. The mesh of a part
placed many times (a board's components) is made once per part and moved into each place — the same triangles,
faces and edges as copies meshed one by one.
"""
import math
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from auto3d.modeler import available

OCC = available("occ")
if OCC:
    from auto3d.modeler import blobs, doc, filecache, kernel as K

from test_modeler_kernel import RECT, extrude, sketch, watertight

W, H, T, D = 40, 20, 10, 6  # the block (RECT, 10 high) and its hole's Ø
BLOCK = W * H * T - math.pi * (D / 2) ** 2 * T
# three places of a part (4 × 4, column-major as three.js keeps it): moved, turned 90° about z, turned about x and moved
PLACES = [[1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 100, 0, 0, 1],
          [0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1, 0, 0, 100, 5, 1],
          [1, 0, 0, 0, 0, 0, 1, 0, 0, -1, 0, 0, -60, 30, 20, 1]]


def block():
    """The 40 × 20 × 10 block with a Ø6 hole through it (planes and a cylinder)."""
    top = {"face": {"name": "E1:end"}, "frame": {"o": [20, 10, 10], "x": [1, 0, 0], "n": [0, 0, 1]}}
    return doc.body_of({"features": [sketch("S1", [RECT]), extrude("E1", "S1", T),
                                     {"id": "H1", "type": "hole", "plane": top, "points": [[0, 0]], "d": D, "through": True}]}).body.shape


def forget():
    """The kernel process's own memory of files and meshes cleared (as a new process: a restart, another worker)."""
    doc._shapes.clear()
    doc._tess.clear()
    doc._packed.clear()
    doc._cache.clear()
    K._volumes.clear()


@unittest.skipUnless(OCC, "OCP not installed")
class TestFileCache(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="a3d-filecache-"))
        self.patches = [mock.patch.object(blobs, "DIR", self.tmp / "blobs"), mock.patch.object(filecache, "DIR", self.tmp / "cache"),
                        mock.patch.object(filecache, "MIN_FACES", 0)]  # (a small file is kept too, here)
        for p in self.patches:
            p.start()
        forget()
        shape = block()
        self.board = K.compound([K.placed(shape, m) for m in PLACES])  # one part placed three times
        top = next(f for f in map(K.TopoDS.Face, K._subshapes(self.board, K.TopAbs_FACE)) if K.flat_plane(f) is not None)
        self.sha = blobs.put(K.to_step(self.board, "board", colours=[(top, "#ff0000")]))
        self.feats = [{"id": "B1", "type": "solid", "blob": self.sha}]

    def tearDown(self):
        for p in self.patches:
            p.stop()
        forget()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_second_open_from_the_cache(self):
        """Opened again (a new kernel process): neither read nor meshed — the same answer and mesh, its colours; the
        volume as the block's, a watertight mesh, and its STEP export reads back with the same volume."""
        first = doc.import_solid({"blob": self.sha, "name": "board.step"})
        self.assertAlmostEqual(first["volume"], 3 * BLOCK, places=3)
        self.assertEqual(first["coloured"], 1)
        body = doc.rebuild({"features": self.feats})["body"]
        self.assertTrue((filecache.DIR / f"{self.sha}.brep").exists())
        self.assertEqual(len(list(filecache.DIR.glob(f"{self.sha}.*.mesh"))), 1)
        forget()
        with mock.patch.object(K, "read_step_colours", side_effect=AssertionError("read again")), \
                mock.patch.object(K, "tessellate", side_effect=AssertionError("meshed again")):
            again = doc.import_solid({"blob": self.sha, "name": "board.step"})
            forget()  # (the rebuild in a process of its own: the shape from the cache too)
            res = doc.rebuild({"features": self.feats})
        self.assertEqual(again, first)
        kept = res["body"]
        self.assertEqual(kept["positions"], body["positions"])
        self.assertEqual(kept["faces"], body["faces"])
        self.assertEqual(kept["edges"], body["edges"])
        self.assertEqual(sum(1 for f in kept["faces"] if f.get("color") == "#ff0000"), 1)
        self.assertAlmostEqual(kept["volume"], 3 * BLOCK, places=3)
        self.assertTrue(watertight(kept))
        self.assertEqual(res["features"][0]["bbox"], doc.rebuild({"features": self.feats})["features"][0]["bbox"])
        step = doc.export({"features": self.feats}, "step", "board")  # (the exact shape: from the cache's B-rep)
        self.assertAlmostEqual(K.volume(K.from_step(step)), 3 * BLOCK, places=3)
        self.assertEqual(K.face_count(K.from_step(step)), first["faces"])

    def test_file_changed_or_other_code(self):
        """The file changed in place (the same name, other bytes) or other code: read and meshed again."""
        doc.import_solid({"blob": self.sha, "name": "board.step"})
        doc.rebuild({"features": self.feats})
        other = K.compound([K.placed(block(), m) for m in PLACES[:2]])
        blobs.path(self.sha).write_bytes(K.to_step(other, "board"))
        forget()
        reads = mock.patch.object(K, "read_step_colours", wraps=K.read_step_colours)
        with reads as read:
            r = doc.import_solid({"blob": self.sha, "name": "board.step"})
        self.assertEqual(read.call_count, 1)
        self.assertAlmostEqual(r["volume"], 2 * BLOCK, places=3)
        self.assertFalse(list(filecache.DIR.glob(f"{self.sha}.*.mesh")))  # (the old mesh went with it)
        self.assertAlmostEqual(doc.rebuild({"features": self.feats})["body"]["volume"], 2 * BLOCK, places=3)
        forget()
        with mock.patch.object(filecache, "_code", "other code"), reads as read:
            doc.import_solid({"blob": self.sha, "name": "board.step"})
        self.assertEqual(read.call_count, 1)

    def test_damaged_entry_and_small_files(self):
        """A damaged entry: the file is read again (and kept anew); a small file (MIN_FACES) is not kept at all."""
        doc.import_solid({"blob": self.sha, "name": "board.step"})
        (filecache.DIR / f"{self.sha}.brep").write_bytes(b"not a shape")
        forget()
        r = doc.rebuild({"features": self.feats})
        self.assertAlmostEqual(r["body"]["volume"], 3 * BLOCK, places=3)
        self.assertIsNotNone(filecache.shape(self.sha))
        with mock.patch.object(filecache, "MIN_FACES", 3000):
            small = blobs.put(K.to_step(block(), "block"))
            doc.import_solid({"blob": small, "name": "block.step"})
            self.assertFalse(list(filecache.DIR.glob(f"{small}.*")))

    def test_kept_under_the_limit(self):
        """The folder over LIMIT_MB: the files used least lately go, whole."""
        doc.import_solid({"blob": self.sha, "name": "board.step"})
        other = blobs.put(K.to_step(block(), "block"))
        os.utime(filecache.DIR / f"{self.sha}.json", (1, 1))  # (used long ago)
        with mock.patch.object(filecache, "LIMIT_MB", 1e-6):
            doc.import_solid({"blob": other, "name": "block.step"})
        self.assertFalse(list(filecache.DIR.glob(f"{self.sha}.*")))


@unittest.skipUnless(OCC, "OCP not installed")
class TestPlacedParts(unittest.TestCase):
    """A big model (over HEAVY_FACES) whose parts are placed many times is meshed per part, then moved."""

    def mesh(self, shape):
        with mock.patch.object(K, "HEAVY_FACES", 5):  # (this small one meshed as a big one)
            return K.tessellate(K.Body(shape))

    def test_placed_as_copies(self):
        """One part placed three times gives the triangles, faces and edges of three copies made apart."""
        shape = block()
        placed = K.compound([K.placed(shape, m) for m in PLACES])
        copies = K.compound([K.transformed(shape, np.reshape(m, (4, 4)).T[:3, :3], m[12:15]) for m in PLACES])  # (each made apart)
        places = [p for *_, p in K._face_meshes(K._face_map(placed))]
        self.assertEqual(len({p[0] for p in places}), K.face_count(shape))  # (each face's mesh read once)
        a, b = self.mesh(placed), self.mesh(copies)
        np.testing.assert_allclose(np.frombuffer(a["positions"], np.float32), np.frombuffer(b["positions"], np.float32), atol=1e-4)
        self.assertEqual(a["face_ids"], b["face_ids"])
        self.assertEqual(len(a["faces"]), 3 * K.face_count(shape))
        for f, g in zip(a["faces"], b["faces"]):
            self.assertEqual(f["type"], g["type"])
            for k in ("normal", "radius"):
                if k in g:
                    np.testing.assert_allclose(f[k], g[k], atol=1e-6)
            if "axis" in g:
                np.testing.assert_allclose(f["axis"]["o"], g["axis"]["o"], atol=1e-6)
                np.testing.assert_allclose(f["axis"]["d"], g["axis"]["d"], atol=1e-6)
            if "frame" in g:
                np.testing.assert_allclose(f["frame"]["o"], g["frame"]["o"], atol=1e-5)
        self.assertEqual([e["faces"] for e in a["edges"]], [e["faces"] for e in b["edges"]])
        for e, g in zip(a["edges"], b["edges"]):
            np.testing.assert_allclose(e["pts"], g["pts"], atol=1e-5)
            np.testing.assert_allclose(e["mid"], g["mid"], atol=1e-5)
        self.assertTrue(watertight(a))
        self.assertAlmostEqual(a["volume"], 3 * BLOCK, places=3)
        holes = [f for f in a["faces"] if f["type"] == "cylinder"]
        self.assertEqual({f["radius"] for f in holes}, {D / 2})
        turned = [f["axis"]["d"] for f in holes]  # (the third place turned the hole's axis from z to y)
        self.assertTrue(any(abs(abs(d[1]) - 1) < 1e-9 for d in turned) and any(abs(abs(d[2]) - 1) < 1e-9 for d in turned))

    def test_flat_faces_centres(self):
        """A flat face's frame centre from its mesh: the middle of its box (the block's top: its middle, moved)."""
        a = self.mesh(K.compound([K.placed(block(), m) for m in PLACES[:1]]))
        top = next(f for f in a["faces"] if f["type"] == "plane" and f["normal"] == [0, 0, 1])
        np.testing.assert_allclose(top["frame"]["o"], [100 + W / 2, H / 2, T], atol=1e-6)


if __name__ == "__main__":
    unittest.main()
