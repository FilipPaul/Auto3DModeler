"""🎬 The demo projects (demos/*.a3d, auto3d/demos.py): each opens as a valid project with its assembly ready —
joints between its placed parts, Czech motion names, a named mechanism, its picture — and the server serves them read-only."""
import math
import tempfile
import unittest
from pathlib import Path

from auto3d import demos, package

ROOT = Path(__file__).resolve().parent.parent
DEMOS = ROOT / "demos"
BIG = {"velka-sestava-150.a3d": (97, 5), "velka-sestava-500.a3d": (521, 0)}  # placed parts, sub-assemblies placed (no mechanism)


class TestDemoFiles(unittest.TestCase):
    def test_listing(self):
        lst = demos.listing(DEMOS)
        self.assertGreaterEqual(len(lst), 3)
        self.assertEqual([d["file"] for d in lst][:3], ["klikovy-mechanismus.a3d", "ctyrkloubovy-mechanismus.a3d", "roboticke-rameno.a3d"])
        for d in lst:
            self.assertTrue(d["name"] and d["name_cs"] and d["text"] and d["text_cs"], d)
            self.assertNotEqual(d["name"], d["name_cs"])
            self.assertTrue(d["thumb"], d)  # (its card's picture)
            self.assertEqual(demos.thumbnail(DEMOS, d["file"])[:8], b"\x89PNG\r\n\x1a\n")

    def test_each_loads_with_its_mechanism(self):
        for d in demos.listing(DEMOS):
            if d["file"] in BIG:
                continue
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

    def test_big_assemblies(self):
        """The big assemblies (tools/make_big_assembly.py): every placed part's part there (a sub-assembly's too), each
        joint between placed parts, one part fixed; small files — the parts are steps, rebuilt when opened."""
        for f, (placed, subs) in BIG.items():
            with self.subTest(demo=f):
                proj = demos.load(DEMOS, f)
                parts = {p["id"]: p for p in proj["parts"]}
                asm = parts[proj["active"]["part"]]["assembly"]
                ids = {i["id"] for i in asm["instances"]}
                self.assertEqual(len(asm["instances"]), placed)
                self.assertEqual(sum(parts[i["part"]]["kind"] == "assembly" for i in asm["instances"]), subs)
                self.assertTrue(all(parts[i["part"]]["kind"] in ("model", "assembly") for i in asm["instances"]))
                self.assertTrue(any(i.get("fixed") for i in asm["instances"]))
                self.assertTrue(asm["mates"] and all(m["move"] in ids and m["onto"] in ids for m in asm["mates"]))
                self.assertLess((DEMOS / f).stat().st_size, 60_000)

    def test_crank_slider_closes_its_loop(self):
        asm = next(p for p in demos.load(DEMOS, "klikovy-mechanismus.a3d")["parts"] if p["kind"] == "assembly")["assembly"]
        rod = [m for m in asm["mates"] if m["move"] == "I3" and m["type"] == "axis"]
        self.assertEqual({m["onto"] for m in rod}, {"I2", "I4"})  # (the rod on the crank's pin and on the slider's pin)

    def test_four_bar_closes_its_loop(self):
        asm = next(p for p in demos.load(DEMOS, "ctyrkloubovy-mechanismus.a3d")["parts"] if p["kind"] == "assembly")["assembly"]
        coupler = [m for m in asm["mates"] if m["move"] == "I3" and m["type"] == "axis"]
        self.assertEqual({m["onto"] for m in coupler}, {"I2", "I4"})
        self.assertEqual(sorted(m["onto"] for m in asm["mates"] if m["move"] in ("I2", "I4") and m["type"] == "axis"), ["I1", "I1"])

    def test_gearbox_couples_its_wheels(self):
        asm = next(p for p in demos.load(DEMOS, "prevodovka-s-hrebenem.a3d")["parts"] if p["kind"] == "assembly")["assembly"]
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
        asm = next(p for p in demos.load(DEMOS, "pumpicka.a3d")["parts"] if p["kind"] == "assembly")["assembly"]
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

    def test_gantry_routes_its_cable_through_the_chain(self):
        """🎬 Portálový pojezd: an igus chain whose moving end goes with the carriage, a 🔒 cable from the box through it
        to the motor, held by P-clips (the carriage's clip joined to the carriage: it goes along)."""
        proj = demos.load(DEMOS, "portalovy-pojezd.a3d")
        asm = next(p for p in proj["parts"] if p["kind"] == "assembly")["assembly"]
        inst = {i["id"]: i for i in asm["instances"]}
        (ch,) = asm["chains"]
        self.assertIn("E2.15", ch["dims"]["pn"])
        self.assertEqual(ch["follow"]["inst"], "I3")  # (the carriage)
        (h,) = asm["harnesses"]
        self.assertGreater(h["length_locked"], 0)
        self.assertEqual([s.get("chain") for s in h["spans"]], [ch["id"]])
        clips = [p["clip"] for p in h["points"] if p.get("clip")]
        self.assertEqual(len(clips), 3)
        names = {p["id"]: p["name"] for p in proj["parts"]}
        for c in clips:
            self.assertIn("P-clamp", names[inst[c]["part"]])
        for p in h["points"]:
            self.assertIn(p["inst"], inst)  # (every point locked to a part)
        rigid = {m["move"]: m["onto"] for m in asm["mates"] if m["type"] == "rigid"}
        self.assertEqual(rigid.get(clips[-1]), "I3")
        (lim,) = inst["I3"]["travel"].values()
        self.assertEqual((lim["min"], lim["max"]), (-150, 150))

    def test_arm_has_a_service_loop_across_its_hinge(self):
        """🎬 Otočné rameno s kabelem: 4 coloured loose wires from the controller to the sensor, a ➰ span of its own
        length from the controller to the arm, tie mounts joined to the arm, the arm's swing −90 … 90°."""
        proj = demos.load(DEMOS, "otocne-rameno-s-kabelem.a3d")
        asm = next(p for p in proj["parts"] if p["kind"] == "assembly")["assembly"]
        inst = {i["id"]: i for i in asm["instances"]}
        (h,) = asm["harnesses"]
        self.assertEqual(h["kind"], "wires")
        self.assertEqual([w["color"] for w in h["wires"]], ["brown", "blue", "black", "white"])
        (span,) = h["spans"]
        self.assertEqual(span["from"], 0)
        self.assertGreater(span["length"], 100)
        rigid = {m["move"]: m["onto"] for m in asm["mates"] if m["type"] == "rigid"}
        clips = [p["clip"] for p in h["points"] if p.get("clip")]
        self.assertEqual(len(clips), 2)
        self.assertTrue(all(rigid.get(c) == "I2" for c in clips))  # (on the arm: they swing with it)
        (lim,) = inst["I2"]["travel"].values()
        self.assertEqual((lim["min"], lim["max"]), (-90, 90))

    def test_bad_names_refused(self):
        for bad in ("../server.py", "nope.a3d", "klikovy-mechanismus.json", "klikovy-mechanismus.a3d.json", "sub/x.a3d", None):
            with self.subTest(name=bad), self.assertRaises(demos.DemoError):
                demos.load(DEMOS, bad)

    def test_a_folder_without_demos(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(demos.listing(tmp), [])
            self.assertEqual(demos.listing(Path(tmp) / "none"), [])
            (Path(tmp) / "broken.a3d").write_text("{not a zip", encoding="utf-8")
            self.assertEqual(demos.listing(tmp), [])
            (Path(tmp) / "x.a3d").write_bytes(package.write({"app": "nope"}, None)[0])
            with self.assertRaises(demos.DemoError):
                demos.load(tmp, "x.a3d")
            self.assertIsNone(demos.thumbnail(tmp, "x.a3d"))  # (no picture in it)


class TestDemoRoutes(unittest.TestCase):
    def test_served_read_only(self):
        import server
        c = server.app.test_client()
        lst = c.get("/api/demos").get_json()["demos"]
        self.assertGreaterEqual(len(lst), 3)
        proj = c.get(f"/api/demos/{lst[0]['file']}").get_json()
        self.assertEqual(proj["version"], 3)
        self.assertEqual(c.get("/api/demos/..%2Fserver.py").status_code, 404)
        self.assertEqual(c.get("/api/demos/nope.a3d").status_code, 404)
        pic = c.get(f"/api/demos/{lst[0]['file']}/thumb")
        self.assertEqual((pic.status_code, pic.mimetype, pic.data[1:4]), (200, "image/png", b"PNG"))
        self.assertEqual(c.get("/api/demos/nope.a3d/thumb").status_code, 404)
        self.assertIn(c.post(f"/api/demos/{lst[0]['file']}", json={}).status_code, (405,))  # (no writing)


if __name__ == "__main__":
    unittest.main()
