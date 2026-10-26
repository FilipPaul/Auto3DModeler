"""Autosave: the project kept on the server under its id (the latest state replaces the one before), listed latest first,
loaded back, forgotten; bad ids and empty projects refused; the oldest dropped; the routes."""
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from auto3d import autosave as A


def project(name="Duck", n=1):
    return {"project_name": name, "parts": [{"id": f"P{i}", "kind": "model", "name": f"part {i}", "model": {"features": []}} for i in range(1, n + 1)]}


class TestAutosave(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "projects"

    def tearDown(self):
        self.tmp.cleanup()

    def test_keep_list_load_forget(self):
        A.save(self.dir, "aaaaaaaa-1", project("Duck", 1))
        time.sleep(0.01)
        m = A.save(self.dir, "bbbbbbbb-2", project("Pond", 2))
        self.assertEqual((m["name"], len(m["parts"])), ("Pond", 2))
        time.sleep(0.01)
        A.save(self.dir, "aaaaaaaa-1", project("Duck", 3))  # the same project again: its latest state
        rec = A.recent(self.dir)
        self.assertEqual([(r["id"], len(r["parts"])) for r in rec], [("aaaaaaaa-1", 3), ("bbbbbbbb-2", 2)])
        self.assertEqual(len(A.load(self.dir, "aaaaaaaa-1")["parts"]), 3)
        A.delete(self.dir, "aaaaaaaa-1")
        self.assertEqual([r["id"] for r in A.recent(self.dir)], ["bbbbbbbb-2"])
        self.assertFalse(list(self.dir.glob("*.tmp")))

    def test_refused_and_pruned(self):
        for bad in ("../x", "short", "a" * 80):
            with self.assertRaises(A.AutosaveError):
                A.save(self.dir, bad, project())
        with self.assertRaises(A.AutosaveError):
            A.save(self.dir, "cccccccc-3", {"parts": []})
        with mock.patch.object(A, "MAX_PROJECTS", 2):
            for k in range(4):
                A.save(self.dir, f"dddddddd-{k}", project(f"p{k}"))
                time.sleep(0.01)
        self.assertEqual([r["id"] for r in A.recent(self.dir)], ["dddddddd-3", "dddddddd-2"])

    def test_routes(self):
        import server
        with mock.patch.object(server, "PROJECTS", self.dir):
            c = server.app.test_client()
            self.assertEqual(c.post("/api/projects/eeeeeeee-5", json={"project": project("Box")}).get_json()["name"], "Box")
            self.assertEqual(c.get("/api/projects").get_json()["projects"][0]["id"], "eeeeeeee-5")
            self.assertEqual(c.get("/api/projects/eeeeeeee-5").get_json()["project_name"], "Box")
            self.assertEqual(c.get("/api/projects/..%2Fx").status_code, 404)
            self.assertTrue(c.delete("/api/projects/eeeeeeee-5").get_json()["ok"])


if __name__ == "__main__":
    unittest.main()
