"""A drawing set's drawings kept on disk (auto3d/modeler/sheetcache.py, A3D_DATA/cache/sheets): /api/sheet/build and
/api/sheet/assembly with "cache" keep what they made and answer it again without the kernel (hit / miss, "only": a
miss makes nothing), a changed part or paper is another key (made again), /api/sheet/forget drops a run's drawings
(the page's "No, discard"), the folder kept under its limit (the least used go first), a damaged entry is made again.
The kernel is mocked: these are the server's routes and the cache, not the drawing."""
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import server
from auto3d.modeler import sheetcache


def box(w=40):
    return {"features": [{"id": "S1", "type": "sketch", "plane": {"datum": "XY"}, "points": {"p1": [0, 0], "p2": [w, 0]}},
                         {"id": "E1", "type": "extrude", "sketch": "S1", "op": "add", "d": 10}]}


class TestSheetCache(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "cache" / "sheets"
        self.calls = []

        def run(op, arg, timeout=None, key=None):
            self.calls.append((op, arg))
            return {"geometry": {"views": {}, "bbox": [0, 0, 0, 1, 1, 1], "n": len(self.calls)}, "layout": {"views": {}}, "dims": []}
        self.patches = [mock.patch.object(sheetcache, "DIR", self.dir), mock.patch.object(server.MODEL_WORKER, "run", run),
                        mock.patch.object(sheetcache, "_since", None)]
        for p in self.patches:
            p.start()
        self.c = server.app.test_client()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def build(self, **body):
        r = self.c.post("/api/sheet/build", json={"part": box(), "preset": "medium", "paper": "A4", **body})
        self.assertEqual(r.status_code, 200, r.get_json())
        return r.get_json()

    def test_hit_and_miss(self):
        """Made once and kept (hit: false, its key), then answered from the disk (hit: true, the same drawing, no
        kernel); "only" answers a miss without making anything; without "cache" nothing is kept or read."""
        self.assertEqual(self.build(cache="only"), {"miss": True, "ck": self.build(cache="only")["ck"]})
        self.assertEqual(self.calls, [])
        first = self.build(cache=True)
        self.assertEqual((first["hit"], len(self.calls)), (False, 1))
        self.assertTrue((self.dir / f"{first['ck']}.json").is_file())
        again = self.build(cache=True, rid="another-request")  # (the rid is not what it is made from)
        self.assertEqual((again["hit"], again["ck"], again["geometry"], len(self.calls)), (True, first["ck"], first["geometry"], 1))
        self.assertTrue(self.build(cache="only")["hit"])
        plain = self.build()
        self.assertNotIn("ck", plain)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(len(list(self.dir.glob("*.json"))), 1)

    def test_changed_part_or_paper_is_made_again(self):
        """Another size of the part, another paper, another preset: another key, made again; the code's stamp is in
        the key too (a new version of the app draws anew)."""
        a = self.build(cache=True)
        b = self.c.post("/api/sheet/build", json={"part": box(41), "preset": "medium", "paper": "A4", "cache": True}).get_json()
        c = self.build(cache=True, paper="A3")
        d = self.build(cache=True, preset="full")
        self.assertEqual(len({a["ck"], b["ck"], c["ck"], d["ck"]}), 4)
        self.assertFalse(any(x["hit"] for x in (b, c, d)))
        self.assertEqual(len(self.calls), 4)
        with mock.patch.object(sheetcache.partcache, "_stamp", "other-code"):
            self.assertEqual(self.build(cache="only").get("miss"), True)

    def test_assembly_pages_too(self):
        """An assembly's page is kept the same way; a moved part is another key."""
        inst = [{"id": "I1", "part": box(), "matrix": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]}]
        r1 = self.c.post("/api/sheet/assembly", json={"instances": inst, "cache": True}).get_json()
        r2 = self.c.post("/api/sheet/assembly", json={"instances": inst, "cache": True}).get_json()
        self.assertEqual((r1["hit"], r2["hit"], len(self.calls)), (False, True, 1))
        inst[0]["matrix"][12] = 5
        self.assertTrue(self.c.post("/api/sheet/assembly", json={"instances": inst, "cache": "only"}).get_json()["miss"])

    def test_forget(self):
        """/api/sheet/forget drops the given drawings (only keys: a path is ignored); then they are made again."""
        a, b = self.build(cache=True), self.build(cache=True, paper="A3")
        r = self.c.post("/api/sheet/forget", json={"keys": [a["ck"], "../../server", "nope"]}).get_json()
        self.assertEqual(r, {"dropped": 1})
        self.assertTrue(self.build(cache="only")["miss"])
        self.assertTrue(self.build(cache=True, paper="A3")["hit"])
        self.assertEqual(self.c.post("/api/sheet/forget", json={"keys": "x"}).get_json(), {"dropped": 0})
        self.assertTrue(b["ck"])

    def test_eviction_least_used_first(self):
        """Over LIMIT_MB the entries used least lately go: one read just now stays, the oldest unread one goes."""
        keys = [self.build(cache=True, paper=f"P{i}")["ck"] for i in range(3)]
        old = time.time() - 1000
        for i, k in enumerate(keys):
            os.utime(self.dir / f"{k}.json", (old + i, old + i))
        self.assertTrue(self.build(cache=True, paper="P0")["hit"])  # (read: used now)
        size = (self.dir / f"{keys[0]}.json").stat().st_size
        with mock.patch.object(sheetcache, "LIMIT_MB", 3.5 * size / (1 << 20)), mock.patch.object(sheetcache, "_since", None):
            self.build(cache=True, paper="P3")  # (a 4th: one must go)
        left = {p.stem for p in self.dir.glob("*.json")}
        self.assertIn(keys[0], left)
        self.assertNotIn(keys[1], left)
        self.assertEqual(len(left), 3)

    def test_damaged_entry_made_again(self):
        a = self.build(cache=True)
        (self.dir / f"{a['ck']}.json").write_text("{broken", encoding="utf-8")
        again = self.build(cache=True)
        self.assertEqual((again["hit"], len(self.calls)), (False, 2))
        self.assertTrue(self.build(cache=True)["hit"])


if __name__ == "__main__":
    unittest.main()
