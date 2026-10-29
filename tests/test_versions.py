"""🕘 Versions (auto3d/versions.py): the content-addressed store keeps a part that did not change once, restores exactly,
names a changed step value in a comparison, thins automatic versions (named ones and variants' heads stay), deletes
only objects nobody uses, keeps each variant's own timeline, takes one part from another variant, refuses bad ids and
goes into / comes out of a project file whole.

Run:  py -m unittest tests.test_versions -v
"""
import copy
import json
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from auto3d import versions as V

PID = "test-project-0001"
JPEG = b"\xff\xd8\xff\xe0" + b"thumb" * 40


def _model(pid, name, d=10.0):
    return {"id": pid, "kind": "model", "name": name, "model": {"features": [
        {"id": "F1", "type": "sketch", "name": "Skica 1", "plane": "XY", "points": {"p1": [0, 0], "p2": [20, 10]},
         "entities": [], "constraints": [], "dims": [{"id": "d1", "t": "len", "e": "l1", "v": 20}]},
        {"id": "F2", "type": "extrude", "name": "Vysunutí 1", "sketch": "F1", "op": "add", "d": d, "symmetric": False}]}}


def _project(n=5, **kw):
    parts = [_model(f"P{i + 1}", f"Díl {i + 1}") for i in range(n)]
    return {"app": "Auto3DModeler", "version": 3, "project_name": "Test", "unit": "mm", "parameters": [],
            "active": {"part": "P1"}, "parts": parts, "assets": {}, "assemblies": [], **kw}


class VersionsTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="a3d-versions-"))
        self.folder = self.root / PID

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def objects(self):
        return {sha for sha, _ in V._objects(self.folder)}

    def test_unchanged_parts_are_stored_once(self):
        p = _project()
        t0 = 1_800_000_000
        for i in range(10):
            p["parts"][2]["model"]["features"][1]["d"] = 10 + i
            m = V.save(self.root, PID, p, label=f"v{i}", now=t0 + i * 60)
            self.assertFalse(m.get("same"))
            self.assertEqual(m["changed"], [] if i == 0 else ["Díl 3"])
        part_hashes = set()
        for m in V.versions(self.root, PID)["versions"]:
            part_hashes.update(m["parts"].values())
        self.assertEqual(len(part_hashes), 10 + 4)  # 10 of the changed part, one each of the other four
        self.assertEqual(len(self.objects()), 10 + 4 + 1)  # + the project-level bits, the same each time
        self.assertEqual(len(V.versions(self.root, PID)["versions"]), 10)

    def test_same_project_is_not_kept_again_and_auto_is_throttled(self):
        p = _project(2)
        t0 = 1_800_000_000
        a = V.save(self.root, PID, p, auto=True, now=t0)
        self.assertTrue(V.save(self.root, PID, p, auto=True, now=t0 + 1000)["same"])  # (nothing changed)
        p["parts"][0]["name"] = "Jiný"
        self.assertTrue(V.save(self.root, PID, p, auto=True, now=t0 + 60)["same"])  # (too soon)
        b = V.save(self.root, PID, p, auto=True, now=t0 + V.AUTO_GAP + 1)
        self.assertEqual(b["parent"], a["id"])
        p["parts"].append(_model("P9", "Nový"))
        c = V.save(self.root, PID, p, auto=True, now=t0 + V.AUTO_GAP + 5)  # (a part added: a bigger change, kept at once)
        self.assertFalse(c.get("same"))
        self.assertEqual(c["changed"], ["Nový"])

    def test_restore_round_trips_exactly(self):
        p = _project(3)
        p["parameters"] = [{"name": "L", "expr": "40"}]
        a = V.save(self.root, PID, p, label="A", thumb=JPEG, volumes={"P1": 2000.0}, now=1_800_000_000)
        before = copy.deepcopy(p)
        p["parts"][0]["model"]["features"][1]["d"] = 15
        p["parts"].pop()
        V.save(self.root, PID, p, label="B", now=1_800_000_100)
        self.assertEqual(V.get(self.root, PID, a["id"])["project"], before)
        r = V.restore(self.root, PID, a["id"], current=p, now=1_800_000_200)
        self.assertEqual(r["project"], before)
        self.assertEqual(r["before"]["note"], {"what": "before-restore"})
        self.assertEqual(r["version"]["note"]["from"], a["id"])
        self.assertEqual(r["version"]["thumb"], a["thumb"])
        labels = [m["label"] for m in V.versions(self.root, PID)["versions"]]
        self.assertEqual(labels[2:], ["B", "A"])  # (B still there, under the two new ones)
        self.assertEqual(V.thumb(self.root, PID, a["id"]), JPEG)
        # the version before restoring brings the changed project back (restore undone)
        self.assertEqual(V.restore(self.root, PID, r["before"]["id"])["project"], p)

    def test_diff_names_the_changed_step_value(self):
        a = _project(2)
        b = copy.deepcopy(a)
        b["parts"][0]["model"]["features"][1]["d"] = 15
        b["parts"][0]["model"]["features"][0]["dims"][0]["v"] = 25
        b["parts"][0]["model"]["features"].append({"id": "F3", "type": "hole", "name": "Díra 1", "d": 5})
        b["parts"].pop()
        b["parts"].append(_model("P7", "Víko"))
        b["parameters"] = [{"name": "L", "expr": "100"}]
        out = V.diff(a, b, {"P1": 2000.0}, {"P1": 3000.0})
        p1 = next(x for x in out["parts"] if x["id"] == "P1")
        self.assertEqual(p1["status"], "changed")
        self.assertEqual(p1["volume"], [2000.0, 3000.0])
        ext = next(s for s in p1["steps"] if s["step"] == "Vysunutí 1")
        self.assertEqual(ext["values"], [{"key": "d", "before": 10.0, "after": 15, "unit": "mm"}])
        sk = next(s for s in p1["steps"] if s["step"] == "Skica 1")
        self.assertEqual(sk["values"], [{"key": "dim d1", "before": 20, "after": 25, "unit": "mm"}])
        self.assertIn({"step": "Díra 1", "id": "F3", "type": "hole", "status": "added"}, p1["steps"])
        self.assertEqual({(x["name"], x["status"]) for x in out["parts"]}, {("Díl 1", "changed"), ("Víko", "added"), ("Díl 2", "removed")})
        self.assertEqual(out["project"], [{"what": "parameter", "name": "L", "before": None, "after": "100"}])
        # through the store: a version against the project on screen
        m = V.save(self.root, PID, a, label="A", volumes={"P1": 2000.0})
        c = V.compare(self.root, PID, m["id"], "current", current=b, volumes={"P1": 3000.0})
        self.assertEqual(next(x for x in c["parts"] if x["id"] == "P1")["volume"], [2000.0, 3000.0])
        with self.assertRaises(V.VersionError):
            V.compare(self.root, PID, m["id"], "current")
        # an assembly: a placed part added, named by its part
        a2 = copy.deepcopy(a)
        a2["parts"].append({"id": "P9", "kind": "assembly", "name": "Sestava", "assembly": {"instances": [{"id": "I1", "part": "P1"}]}})
        b2 = copy.deepcopy(a2)
        b2["parts"][-1]["assembly"]["instances"].append({"id": "I2", "part": "P2", "matrix": [1]})
        asm = next(x for x in V.diff(a2, b2)["parts"] if x["id"] == "P9")
        self.assertEqual(asm["steps"], [{"step": "Díl 2 (I2)", "id": "I2", "type": "instance", "status": "added"}])

    def test_thinning_keeps_named_and_the_expected_auto_versions(self):
        p = _project(1)
        now = 1_800_000_000.0
        # an automatic version every 20 min for 10 days back, a named one 3 days back (kept without thinning as they
        # are made: quicker; the last save thins them all)
        st = V._state(self.folder)
        for k in range(10 * 72, 0, -1):
            p["parts"][0]["model"]["features"][1]["d"] = k
            V._record(self.folder, st, p, auto=True, now=now - k * 1200, label="Named" if k == 3 * 72 else "")
        p["parts"][0]["model"]["features"][1]["d"] = 0
        V.save(self.root, PID, p, auto=True, now=now)  # (thins as it saves)
        kept = V.versions(self.root, PID)["versions"]
        named = [m for m in kept if m["label"] == "Named"]
        self.assertEqual(len(named), 1)
        auto = [m for m in kept if m["auto"]]
        last_day = [m for m in auto if now - m["time"] < V.DAY]
        week = [m for m in auto if V.DAY <= now - m["time"] < V.WEEK]
        older = [m for m in auto if now - m["time"] >= V.WEEK]
        self.assertEqual(len(last_day), 71 + 1)  # every one of the last 24 h (20 min apart) and the new one
        hours = [int(m["time"] // 3600) for m in week]
        self.assertEqual(len(hours), len(set(hours)))  # one an hour
        self.assertGreaterEqual(len(week), 6 * 24 - 1)
        days = [time.strftime("%Y%m%d", time.localtime(m["time"])) for m in older]
        self.assertEqual(len(days), len(set(days)))  # one a day
        self.assertLessEqual(len(older), 4)
        # every object a kept version uses is there, nothing else
        used = {h for m in kept for h in [*m["parts"].values(), m["project"]]}
        self.assertEqual(self.objects(), used)

    def test_gc_removes_only_unreferenced_objects(self):
        p = _project(2)
        a = V.save(self.root, PID, p, label="A", thumb=JPEG)
        stray = V._put(self.folder, b"nobody uses me")
        self.assertIn(stray, self.objects())
        r = V.thin(self.root, PID)
        self.assertEqual(r, {"removed": [], "objects": 1})
        self.assertNotIn(stray, self.objects())
        self.assertEqual(V.get(self.root, PID, a["id"])["project"], p)
        self.assertEqual(V.thumb(self.root, PID, a["id"]), JPEG)

    def test_variants_have_separate_timelines_and_take_part(self):
        p = _project(2)
        a = V.save(self.root, PID, p, label="A", now=1_800_000_000)
        p["parts"][0]["model"]["features"][1]["d"] = 15
        b = V.save(self.root, PID, p, label="B", now=1_800_000_100)
        r = V.create_variant(self.root, PID, b["id"], "delší", now=1_800_000_200)
        var = r["variant"]["id"]
        self.assertEqual(r["project"], p)
        lst = V.versions(self.root, PID)
        self.assertEqual((lst["current"], lst["versions"], lst["base"]["id"]), (var, [], b["id"]))
        long = copy.deepcopy(p)
        long["parts"][0]["model"]["features"][1]["d"] = 40
        c = V.save(self.root, PID, long, label="C", now=1_800_000_300)
        self.assertEqual((c["variant"], c["parent"]), (var, b["id"]))
        self.assertEqual([m["label"] for m in V.versions(self.root, PID)["versions"]], ["C"])
        self.assertEqual([m["label"] for m in V.versions(self.root, PID, "main")["versions"]], ["B", "A"])
        with self.assertRaises(V.VersionError):
            V.create_variant(self.root, PID, a["id"], "Delší")  # (the same name)
        # back on main: its head's project, unchanged
        s = V.switch_variant(self.root, PID, "main")
        self.assertEqual(s["project"]["parts"][0]["model"]["features"][1]["d"], 15)
        # one part taken from "delší"
        t = V.take_part(self.root, PID, var, "P1")
        self.assertEqual(t["part"]["model"]["features"][1]["d"], 40)
        mixed = copy.deepcopy(s["project"])
        mixed["parts"][0] = t["part"]
        d = V.save(self.root, PID, mixed, label="taken", now=1_800_000_400)
        self.assertEqual(d["variant"], "main")
        self.assertEqual(d["changed"], ["Díl 1"])
        self.assertEqual(d["parts"]["P2"], b["parts"]["P2"])
        with self.assertRaises(V.VersionError):
            V.take_part(self.root, PID, var, "P99")

    def test_rename_and_delete_variant_collects_its_objects(self):
        p = _project(2)
        a = V.save(self.root, PID, p, label="A", now=1_800_000_000)
        r = V.create_variant(self.root, PID, a["id"], "delší", now=1_800_000_100)
        var = r["variant"]["id"]
        own = copy.deepcopy(p)
        own["parts"][0]["model"]["features"][1]["d"] = 77  # (an object only this variant uses)
        c = V.save(self.root, PID, own, label="C", now=1_800_000_200, thumb=JPEG)
        only = {c["parts"]["P1"], c["thumb"]}
        self.assertTrue(only <= self.objects())
        # rename: a clash refused, else kept; main may go back to "" (shown as "main")
        V.create_variant(self.root, PID, a["id"], "kratší", now=1_800_000_300)
        with self.assertRaises(V.VersionError):
            V.rename_variant(self.root, PID, var, "Kratší")
        self.assertEqual(V.rename_variant(self.root, PID, var, "dlouhá")["name"], "dlouhá")
        self.assertEqual(V.rename_variant(self.root, PID, "main", "")["name"], "")
        # every variant's versions together, for the graph
        allv = V.versions(self.root, PID, every=True)["all"]
        self.assertEqual([m["label"] for m in allv], ["C", "A"])
        counts = {v["id"]: v["count"] for v in V.versions(self.root, PID)["variants"]}
        self.assertEqual((counts["main"], counts[var]), (1, 1))
        # a variant another one was made from cannot go first; main never
        V.switch_variant(self.root, PID, var)
        kid = V.create_variant(self.root, PID, c["id"], "z dlouhé", now=1_800_000_400)["variant"]["id"]
        with self.assertRaises(V.VersionError):
            V.delete_variant(self.root, PID, var)
        with self.assertRaises(V.VersionError):
            V.delete_variant(self.root, PID, "main")
        V.delete_variant(self.root, PID, kid)
        V.switch_variant(self.root, PID, var)
        d = V.delete_variant(self.root, PID, var)
        self.assertEqual((d["deleted"], d["versions"], d["current"]), (var, 1, "main"))
        self.assertEqual(d["project"], p)  # (it was on screen: main's head comes back)
        self.assertNotIn(var, [v["id"] for v in V.versions(self.root, PID)["variants"]])
        self.assertFalse(only & self.objects())  # (its own objects gone)
        self.assertEqual(set(a["parts"].values()) | {a["project"]}, self.objects())  # (A's all kept)
        self.assertEqual(V.get(self.root, PID, a["id"])["project"], p)
        with self.assertRaises(V.VersionError):
            V.get(self.root, PID, c["id"])

    def test_bad_ids_are_refused(self):
        p = _project(1)
        V.save(self.root, PID, p)
        for bad in ("../x", "..\\..\\etc", "short", "a" * 80, "", None, "x/y-zzzzzzzz"):
            with self.assertRaises(V.VersionError):
                V.versions(self.root, bad)
        for bad in ("../state", "20261029-120000-zzzzzz", "..", "20261029-120000-abcdef/../../x", 5):
            with self.assertRaises(V.VersionError):
                V.get(self.root, PID, bad)
        for bad in ("../main", "v-xyz", "mainx", "v-0123456789"):
            with self.assertRaises(V.VersionError):
                V.switch_variant(self.root, PID, bad)
        with self.assertRaises(V.VersionError):
            V._get(self.folder, "../" + "a" * 61)
        with self.assertRaises(V.VersionError):
            V.save(self.root, PID, {"parts": [{"id": "P1"}, {"id": "P1"}]})
        with self.assertRaises(V.VersionError):
            V.save(self.root, PID, p, thumb=b"not a jpeg")
        self.assertFalse((self.root / "x").exists())

    def test_bundled_history_reloads(self):
        p = _project(3)
        a = V.save(self.root, PID, p, label="A", thumb=JPEG, now=1_800_000_000)
        p["parts"][1]["model"]["features"][1]["d"] = 12
        b = V.save(self.root, PID, p, label="B", now=1_800_000_100)
        V.create_variant(self.root, PID, a["id"], "kratší")
        file = {**p, "versions": V.bundle(self.root, PID)}
        text = json.dumps(file)  # (it goes into the .a3d.json)
        other = "opened-from-file-01"
        n = V.unbundle(self.root, other, json.loads(text)["versions"])
        self.assertEqual(n["versions"], 2)
        lst = V.versions(self.root, other, "main")
        self.assertEqual([m["id"] for m in lst["versions"]], [b["id"], a["id"]])
        self.assertEqual(V.get(self.root, other, a["id"])["project"], V.get(self.root, PID, a["id"])["project"])
        self.assertEqual(V.thumb(self.root, other, a["id"]), JPEG)
        self.assertEqual([v.get("name") for v in V.versions(self.root, other)["variants"]], ["", "kratší"])
        # a damaged one is refused
        bad = json.loads(text)["versions"]
        sha = next(iter(bad["objects"]))
        bad["objects"][sha] = bad["objects"][next(s for s in bad["objects"] if s != sha)]
        with self.assertRaises(V.VersionError):
            V.unbundle(self.root, "another-file-0001", bad)
        self.assertIsNone(V.bundle(self.root, "empty-project-01"))


if __name__ == "__main__":
    unittest.main()
