"""Project files: older files (one part) open as version 3 (several parts), version 3 round-trips, and
broken files are refused with a clear message. Also the optional 3D-model packages report.

Run:  python -m unittest discover -s tests -v
"""
import json
import unittest

from auto3d.modeler import available, status
from auto3d.project import ProjectError, migrate

V2 = {"app": "Auto3DModeler", "version": 2, "project_name": "Bracket",
      "model": {"source": "initial draft.pdf", "unit": "cm", "params": []}, "values": {"w": 1}, "userSet": [],
      "layers": [], "bends": [], "snap": 1, "original": {}, "outline_editor": None, "import_file": None, "layer_pictures": {}}


class TestMigrate(unittest.TestCase):
    def test_v2_becomes_one_part(self):
        p = migrate(json.loads(json.dumps(V2)))
        self.assertEqual(p["version"], 3)
        self.assertEqual(p["project_name"], "Bracket")
        self.assertEqual(p["unit"], "cm")
        self.assertEqual(len(p["parts"]), 1)
        part = p["parts"][0]
        self.assertEqual((part["id"], part["kind"], part["name"]), ("P1", "classic", "initial draft"))
        # the payload is exactly what the version-2 file held, so the browser loads it unchanged
        self.assertEqual(part["classic"], {k: V2[k] for k in V2 if k not in ("app", "version", "project_name")})
        self.assertEqual(p["active"], {"part": "P1"})
        self.assertEqual((p["assets"], p["assemblies"]), ({}, []))

    def test_v1_and_no_version(self):
        for v in (1, None):
            old = {**V2, "version": v}
            del old["project_name"]
            p = migrate(old)
            self.assertEqual(p["project_name"], "initial draft")  # named after the file it was made from
            self.assertEqual(p["parts"][0]["classic"]["model"]["source"], "initial draft.pdf")

    def test_v3_round_trip(self):
        p = migrate(V2)
        p["parts"].append({"id": "P2", "kind": "classic", "name": "Cookie", "classic": {"model": {"source": "pernicek.png"}}})
        p["active"] = {"part": "P2"}
        again = migrate(json.loads(json.dumps(p)))
        self.assertEqual(again, p)

    def test_model_parts(self):
        p = migrate(V2)
        p["parts"].append({"id": "P2", "kind": "model", "name": "Bracket", "model": {"features": [{"id": "F1", "type": "sketch"}]}})
        p["parts"].append({"id": "P3", "kind": "model", "name": "Empty"})
        out = migrate(json.loads(json.dumps(p)))
        self.assertEqual(out["parts"][1]["model"]["features"][0]["id"], "F1")
        self.assertEqual(out["parts"][2]["model"], {"features": []})
        p["parts"].append({"id": "P4", "kind": "assembly", "name": "Shelf", "assembly": {"instances": [{"id": "I1", "part": "P2"}]}})
        out = migrate(json.loads(json.dumps(p)))
        self.assertEqual(out["parts"][3]["assembly"]["instances"][0]["part"], "P2")
        bad = migrate(V2)
        bad["parts"].append({"id": "P2", "kind": "drawing"})
        with self.assertRaises(ProjectError):
            migrate(bad)

    def test_active_part_fixed_up(self):
        p = migrate(V2)
        p["active"] = {"part": "P9"}
        self.assertEqual(migrate(p)["active"], {"part": "P1"})

    def test_refused(self):
        for bad, msg in [({"app": "x"}, "Not an Auto3DModeler"), ([], "Not an Auto3DModeler"),
                         ({"app": "Auto3DModeler", "version": 2}, "no part"),
                         ({"app": "Auto3DModeler", "version": 9, "parts": []}, "newer version"),
                         ({"app": "Auto3DModeler", "version": 3, "parts": []}, "no part"),
                         ({"app": "Auto3DModeler", "version": 3, "parts": [{"id": "P1", "classic": {"model": {"source": "a"}}}, {"id": "P1"}]}, "duplicate"),
                         ({"app": "Auto3DModeler", "version": 3, "parts": [{"id": "P1", "classic": {}}]}, "no model")]:
            with self.assertRaises(ProjectError) as cm:
                migrate(bad)
            self.assertIn(msg, str(cm.exception))


class TestServer(unittest.TestCase):
    def test_endpoints(self):
        import server
        c = server.app.test_client()
        r = c.post("/api/project/migrate", json=V2)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["parts"][0]["name"], "initial draft")
        r = c.post("/api/project/migrate", json={"app": "nope"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Not an Auto3DModeler", r.get_json()["error"])
        k = c.get("/api/kernel").get_json()
        self.assertEqual(set(k), {"occ", "planegcs", "ready", "install"})
        self.assertEqual(k["ready"], available("occ") and available("planegcs"))
        self.assertEqual(k, status())


if __name__ == "__main__":
    unittest.main()
