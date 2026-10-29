"""🎬 The demo projects (demos/*.a3d.json, auto3d/demos.py): each opens as a valid project with its assembly ready —
joints between its placed parts, Czech motion names, a named mechanism — and the server serves them read-only."""
import json
import math
import tempfile
import unittest
from pathlib import Path

from auto3d import demos

ROOT = Path(__file__).resolve().parent.parent
DEMOS = ROOT / "demos"


class TestDemoFiles(unittest.TestCase):
    def test_listing(self):
        lst = demos.listing(DEMOS)
        self.assertGreaterEqual(len(lst), 3)
        self.assertEqual([d["file"] for d in lst][:3], ["klikovy-mechanismus.a3d.json", "ctyrkloubovy-mechanismus.a3d.json", "roboticke-rameno.a3d.json"])
        for d in lst:
            self.assertTrue(d["name"] and d["name_cs"] and d["text"] and d["text_cs"], d)
            self.assertNotEqual(d["name"], d["name_cs"])

    def test_each_loads_with_its_mechanism(self):
        for d in demos.listing(DEMOS):
            with self.subTest(demo=d["file"]):
                proj = demos.load(DEMOS, d["file"])
                self.assertEqual(proj["version"], 3)
                parts = {p["id"]: p for p in proj["parts"]}
                active = parts[proj["active"]["part"]]
                self.assertEqual(active["kind"], "assembly")  # (it opens on its assembly)
                asm = active["assembly"]
                ids = {i["id"] for i in asm["instances"]}
                for i in asm["instances"]:
                    self.assertEqual(parts[i["part"]]["kind"], "model")
                    self.assertTrue(parts[i["part"]]["model"]["features"])  # (made of steps: small files)
                    self.assertEqual(len(i["matrix"]), 16)
                self.assertTrue(any(i.get("fixed") for i in asm["instances"]))
                self.assertTrue(asm["mates"])
                for m in asm["mates"]:
                    self.assertIn(m["move"], ids)
                    self.assertIn(m["onto"], ids)
                names = [n for i in asm["instances"] for n in (i.get("moveNames") or {}).values()]
                self.assertTrue(names and any(c in "".join(names) for c in "áčďéěíňóřšťúůýž"), names)  # (Czech)
                self.assertTrue(asm.get("mechs") and all(r.get("name") for r in asm["mechs"]), asm.get("mechs"))
                self.assertLess((DEMOS / d["file"]).stat().st_size, 50_000)

    def test_crank_slider_closes_its_loop(self):
        asm = next(p for p in demos.load(DEMOS, "klikovy-mechanismus.a3d.json")["parts"] if p["kind"] == "assembly")["assembly"]
        rod = [m for m in asm["mates"] if m["move"] == "I3" and m["type"] == "axis"]
        self.assertEqual({m["onto"] for m in rod}, {"I2", "I4"})  # (the rod on the crank's pin and on the slider's pin)

    def test_four_bar_closes_its_loop(self):
        asm = next(p for p in demos.load(DEMOS, "ctyrkloubovy-mechanismus.a3d.json")["parts"] if p["kind"] == "assembly")["assembly"]
        coupler = [m for m in asm["mates"] if m["move"] == "I3" and m["type"] == "axis"]
        self.assertEqual({m["onto"] for m in coupler}, {"I2", "I4"})
        self.assertEqual(sorted(m["onto"] for m in asm["mates"] if m["move"] in ("I2", "I4") and m["type"] == "axis"), ["I1", "I1"])

    def test_gearbox_couples_its_wheels(self):
        asm = next(p for p in demos.load(DEMOS, "prevodovka-s-hrebenem.a3d.json")["parts"] if p["kind"] == "assembly")["assembly"]
        ids = {i["id"] for i in asm["instances"]}
        cs = {c["type"]: c for c in asm["couplings"]}
        self.assertEqual(set(cs), {"gear", "rack"})
        for c in cs.values():
            self.assertIn(c["a"], ids)
            self.assertIn(c["b"], ids)
            self.assertNotEqual(c["a"], c["b"])
        self.assertEqual(cs["gear"]["ratio"], 2)  # (Ø60 / Ø30: the wheel turns half as fast)
        self.assertFalse(cs["gear"].get("inner") or cs["gear"].get("flip"))  # (in mesh: opposite ways)
        self.assertAlmostEqual(cs["rack"]["ratio"], math.pi * 30, places=4)  # (π·Ø mm per turn)
        self.assertEqual(cs["rack"]["a"], cs["gear"]["a"])  # (the pinion drives both)

    def test_pump_has_a_spring_and_two_valves(self):
        """🎬 Pumpička: a 〰 spring from the body's bore to the piston, two balls ● on their seats' axes going ↕ by the
        piston's direction — one opening while the piston goes up, the other while it goes down."""
        asm = next(p for p in demos.load(DEMOS, "pumpicka.a3d.json")["parts"] if p["kind"] == "assembly")["assembly"]
        inst = {i["id"]: i for i in asm["instances"]}
        (s,) = asm["springs"]
        self.assertEqual((s["part"], s["onto"]), ("I3", "I2"))
        self.assertGreater(s["k"], 0)
        self.assertEqual(sorted(m["move"] for m in asm["mates"] if m["type"] == "ball"), ["I4", "I5"])
        rules = {}
        for b in ("I4", "I5"):
            (lim,) = inst[b]["travel"].values()
            self.assertAlmostEqual(lim["max"] - lim["min"], 2.5, places=6)  # (seated … lifted)
            self.assertEqual(lim["follow"]["part"], "I2")
            rules[b] = lim["follow"]["at"]
        self.assertNotEqual(rules["I4"], rules["I5"])  # (both seats open upwards: the inlet lifts going up, the outlet going down)

    def test_bad_names_refused(self):
        for bad in ("../server.py", "nope.a3d.json", "klikovy-mechanismus.json", "sub/x.a3d.json", None):
            with self.subTest(name=bad), self.assertRaises(demos.DemoError):
                demos.load(DEMOS, bad)

    def test_a_folder_without_demos(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(demos.listing(tmp), [])
            self.assertEqual(demos.listing(Path(tmp) / "none"), [])
            (Path(tmp) / "broken.a3d.json").write_text("{not json", encoding="utf-8")
            self.assertEqual(demos.listing(tmp), [])
            (Path(tmp) / "x.a3d.json").write_text(json.dumps({"app": "nope"}), encoding="utf-8")
            with self.assertRaises(demos.DemoError):
                demos.load(tmp, "x.a3d.json")


class TestDemoRoutes(unittest.TestCase):
    def test_served_read_only(self):
        import server
        c = server.app.test_client()
        lst = c.get("/api/demos").get_json()["demos"]
        self.assertGreaterEqual(len(lst), 3)
        proj = c.get(f"/api/demos/{lst[0]['file']}").get_json()
        self.assertEqual(proj["version"], 3)
        self.assertEqual(c.get("/api/demos/..%2Fserver.py").status_code, 404)
        self.assertEqual(c.get("/api/demos/nope.a3d.json").status_code, 404)
        self.assertIn(c.post(f"/api/demos/{lst[0]['file']}", json={}).status_code, (405,))  # (no writing)


if __name__ == "__main__":
    unittest.main()
