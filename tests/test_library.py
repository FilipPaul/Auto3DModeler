"""📚 The parts library: the app's own items are all readable and well-formed (unique ids, real shapes), the user's
own items are kept in their folder, win over the app's with the same id, and can be deleted (the app's cannot)."""
import json
import tempfile
import unittest
from pathlib import Path

from auto3d import library as L

APP = Path(__file__).resolve().parent.parent / "library"


class TestAppLibrary(unittest.TestCase):
    def test_every_item_is_well_formed(self):
        out = L.load(APP, Path("/nonexistent"))
        self.assertEqual(out["broken"], [])
        ids = [it["id"] for it in out["items"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreater(len(ids), 20)
        for it in out["items"]:
            self.assertNotIn("problems", it, (it["id"], it.get("problems")))
        cats = {it["category"].split(" / ")[0] for it in out["items"]}
        for want in ("Fasteners", "Bearings", "Inserts", "Standoffs", "Panel", "Pneumatics", "Sensors", "Motors"):
            self.assertIn(want, cats)

    def test_real_part_numbers(self):
        items = {it["id"]: it for it in L.load(APP, Path("/nonexistent"))["items"]}
        self.assertEqual(items["sick-ime"]["sizes"]["M12, 4 mm"]["art"], "1040763")
        self.assertEqual(items["sick-ime"]["sizes"]["M18, 8 mm"]["art"], "1040965")
        self.assertEqual(items["ruthex"]["sizes"]["M3"]["pn"], "RX-M3x5.7")
        self.assertEqual(items["smc-cdj2b"]["pn"], "CDJ2B{bore}-{L}Z-B")
        self.assertEqual(items["wurth-sstii-m3"]["pn"].replace("{LL}", items["wurth-sstii-m3"]["sizes"]["10"]["LL"]), "970100321")


class TestUserLibrary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.user = Path(self.tmp.name) / "library"

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_override_delete(self):
        mine = {"id": "my-bracket", "name": "My bracket", "category": "My parts", "features": [{"id": "F1", "type": "sketch"}], "maker": "Me", "pn": "BR-1"}
        saved = L.save_user_item(self.user, mine)
        self.assertEqual(saved["source"], "user")
        self.assertTrue((self.user / "my-bracket.json").exists())
        # the same id as an app item: the user's wins
        L.save_user_item(self.user, {"id": "ruthex", "name": "My inserts", "category": "Inserts", "features": [{"id": "F1"}]})
        items = {it["id"]: it for it in L.load(APP, self.user)["items"]}
        self.assertEqual(items["ruthex"]["name"], "My inserts")
        self.assertEqual(items["my-bracket"]["pn"], "BR-1")
        L.delete_user_item(self.user, "my-bracket")
        self.assertNotIn("my-bracket", {it["id"] for it in L.load(APP, self.user)["items"]})
        with self.assertRaises(L.LibraryError):
            L.delete_user_item(self.user, "bearing")  # the app's own: stays

    def test_refused(self):
        for bad in ({"id": "../x", "name": "a", "category": "c", "features": [1]}, {"id": "a", "category": "c", "features": [1]},
                    {"id": "a", "name": "a", "category": "c"}, {"id": "a", "name": "a", "category": "c", "shape": [{"loft": 1}]}):
            with self.assertRaises(L.LibraryError):
                L.save_user_item(self.user, bad)
        (self.user).mkdir(parents=True, exist_ok=True)
        (self.user / "broken.json").write_text("{not json", encoding="utf-8")
        self.assertEqual(len(L.load(APP, self.user)["broken"]), 1)

    def test_routes(self):
        import server
        from unittest import mock
        with mock.patch.object(server, "LIBRARY_USER", self.user):
            c = server.app.test_client()
            n = len(c.get("/api/library").get_json()["items"])
            r = c.post("/api/library", json={"item": {"id": "mine", "name": "Mine", "category": "My parts", "features": [{"id": "F1"}]}})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(len(c.get("/api/library").get_json()["items"]), n + 1)
            self.assertEqual(c.post("/api/library", json={"item": {"id": "x"}}).status_code, 400)
            self.assertTrue(c.delete("/api/library/mine").get_json()["ok"])
            self.assertEqual(c.delete("/api/library/bearing").status_code, 404)
            self.assertEqual(json.loads(json.dumps(c.get("/api/library").get_json()))["broken"], [])


if __name__ == "__main__":
    unittest.main()
