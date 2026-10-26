"""AI history: the project after each AI turn, kept on the server — saved, listed newest first, the same state not
saved twice, loaded back, deleted, the oldest dropped; and the /api/history routes."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from auto3d import ai_history as H


def project(name="Plate", d=5):
    return {"project_name": name, "active": {"part": "p1"},
            "parts": [{"id": "p1", "kind": "model", "name": name, "model": {"features": [{"id": "F1", "type": "extrude", "d": d}]}}]}


class TestHistory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "history"

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_list_load_delete(self):
        a = H.save_state(self.dir, project(d=5), "Make a plate", 3)
        self.assertEqual((a["prompt"], a["tools"], a["kind"], a["parts"]), ("Make a plate", 3, "ai", [{"name": "Plate", "kind": "model"}]))
        same = H.save_state(self.dir, project(d=5), "Look at it", 1)
        self.assertTrue(same.get("same"))
        self.assertEqual(same["id"], a["id"])
        b = H.save_state(self.dir, project(d=8), "Make it 8 mm", 1)
        self.assertEqual([s["id"] for s in H.list_states(self.dir)], [b["id"], a["id"]])
        self.assertEqual(H.load_state(self.dir, a["id"])["parts"][0]["model"]["features"][0]["d"], 5)
        H.delete_state(self.dir, b["id"])
        self.assertEqual([s["id"] for s in H.list_states(self.dir)], [a["id"]])
        # back to an older state: saved again (it differs from the newest)
        self.assertFalse(H.save_state(self.dir, project(d=8)).get("same"))

    def test_bad_ids_and_projects(self):
        for sid in ("../server", "x", "20260101-000000-zzzzzz"):
            with self.assertRaises(H.HistoryError):
                H.load_state(self.dir, sid)
        with self.assertRaises(H.HistoryError):
            H.save_state(self.dir, {"no": "parts"})

    def test_oldest_dropped(self):
        with mock.patch.object(H, "MAX_STATES", 3):
            ids = [H.save_state(self.dir, project(d=i))["id"] for i in range(5)]
        left = [s["id"] for s in H.list_states(self.dir)]
        self.assertEqual(left, ids[:1:-1])
        self.assertEqual(len(list(self.dir.glob("*.json"))), 6)


class TestRoutes(unittest.TestCase):
    def test_routes(self):
        import server
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(server, "AI_HISTORY", Path(tmp)):
            c = server.app.test_client()
            r = c.post("/api/history", json={"project": project(), "prompt": "a plate", "tools": 2}).get_json()
            self.assertEqual(c.get("/api/history").get_json()["states"][0]["id"], r["id"])
            self.assertEqual(c.get(f"/api/history/{r['id']}").get_json()["project_name"], "Plate")
            self.assertEqual(c.get("/api/history/..%2Fserver").status_code, 404)
            self.assertEqual(c.post("/api/history", json={"project": 1}).status_code, 400)
            self.assertTrue(c.delete(f"/api/history/{r['id']}").get_json()["ok"])
            self.assertEqual(c.get("/api/history").get_json()["states"], [])


if __name__ == "__main__":
    unittest.main()
