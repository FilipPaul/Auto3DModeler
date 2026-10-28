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

    def test_cleanup_empty_default_projects(self):
        """🧹 only projects with nothing in them and the app's own names go — not a named one, not one with steps,
        not the one on screen."""
        empty = lambda name, part="3D model 1": {"project_name": name, "parts": [{"id": "P1", "kind": "model", "name": part, "model": {"features": []}}]}  # noqa: E731
        A.save(self.dir, "aaaaaaaa-1", empty("3D model 1"))
        A.save(self.dir, "aaaaaaaa-2", {"parts": [{"id": "P1", "kind": "assembly", "name": "Sestava 1", "assembly": {"instances": []}}]})
        A.save(self.dir, "aaaaaaaa-3", empty("Bracket"))                                   # a name of the user's
        A.save(self.dir, "aaaaaaaa-4", {"project_name": "3D model 2", "parts": [{"id": "P1", "kind": "model", "name": "3D model 2", "model": {"features": [{"id": "F1"}]}}]})
        A.save(self.dir, "aaaaaaaa-5", empty("Project"))                                   # the one on screen
        found = A.cleanup(self.dir, keep="aaaaaaaa-5", dry_run=True)
        self.assertEqual(sorted(m["id"] for m in found), ["aaaaaaaa-1", "aaaaaaaa-2"])
        self.assertEqual(len(A.recent(self.dir)), 5)                                       # (only told)
        A.cleanup(self.dir, keep="aaaaaaaa-5")
        self.assertEqual(sorted(m["id"] for m in A.recent(self.dir)), ["aaaaaaaa-3", "aaaaaaaa-4", "aaaaaaaa-5"])

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

    def test_same_project_saved_at_once(self):
        """Saves of one project from several threads at once (two quick autosaves, a reader listing the projects
        meanwhile) all succeed and leave one whole file: the last state of one of them, no temp files (on Windows the
        replace used to fail with WinError 32)."""
        import threading
        errors, stop = [], threading.Event()

        def saver(k):
            try:
                for i in range(15):
                    A.save(self.dir, "ffffffff-6", project(f"T{k}", 1 + (k + i) % 4))
            except Exception as e:  # noqa: BLE001 (any failure fails the test)
                errors.append(e)

        def reader():
            while not stop.is_set():
                try:
                    A.recent(self.dir)
                    if (self.dir / "ffffffff-6.json").exists():
                        A.load(self.dir, "ffffffff-6")
                except Exception as e:  # noqa: BLE001
                    errors.append(e)

        r = threading.Thread(target=reader)
        r.start()
        threads = [threading.Thread(target=saver, args=(k,)) for k in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        stop.set()
        r.join()
        self.assertEqual(errors, [])
        kept = A.load(self.dir, "ffffffff-6")
        self.assertTrue(kept["project_name"].startswith("T"))
        self.assertEqual([m["id"] for m in A.recent(self.dir)], ["ffffffff-6"])
        self.assertFalse(list(self.dir.glob("*.tmp")))

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
