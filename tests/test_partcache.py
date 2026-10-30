"""Built parts kept on disk (auto3d/modeler/partcache.py): a part read back after a restart is the part as built — the
same face names on the same faces, volume and bbox, its mesh, a later step on it names its faces as on a fresh build,
a STEP write → read keeps its volume; an edited step, another file (blob), other code make a new key; the folder kept
under its limit; the collision check's pairs kept too.

Run:  py -m unittest tests.test_partcache -v
"""
import math
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from auto3d.modeler import available
from test_modeler_kernel import RECT, extrude, sketch, watertight

OCC = available("occ")
if OCC:
    from auto3d.modeler import blobs, doc, filecache, kernel as K, partcache

TOP = {"face": {"name": "E1:end"}, "frame": {"o": [20, 10, 10], "x": [1, 0, 0], "n": [0, 0, 1]}}
HOLES = [[x, y] for x in (-15, -5, 5, 15) for y in (-5, 5)]  # 8 holes Ø3 through the 40 × 20 × 10 block
PLATE = [sketch("S1", [RECT]), extrude("E1", "S1", 10), {"id": "H1", "type": "hole", "plane": TOP, "points": HOLES, "d": 3, "through": True}]
R = 3
ROUNDED = [sketch("S1", [RECT]), extrude("E1", "S1", 10), {"id": "C", "type": "fillet", "r": R, "edges": [
    {"a": f"E1:side:l{i}", "b": f"E1:side:l{i % 4 + 1}", "fp": p} for i, p in zip(range(1, 5), ([40, 0, 5], [40, 20, 5], [0, 20, 5], [0, 0, 5]))]}]
# a later step on the kept part: a pocket in its top face
POCKET = [sketch("S2", [{"id": "c", "t": "circle", "cx": 0, "cy": 0, "d": 4}], TOP), extrude("E2", "S2", 3, "cut")]


def forget():
    """The kernel process's own memory cleared (as a new process: a restart, another worker)."""
    doc._shapes.clear()
    doc._tess.clear()
    doc._packed.clear()
    doc._cache.clear()
    K._volumes.clear()
    K._PAIRS = None


def named(body):
    """{face name: [the faces' places in the body]} — what a step finding a face by its name gets."""
    fm = K._face_map(body.shape)
    return {n: sorted(fm.FindIndex(f) for f in fs) for n, fs in body.names.items()}


@unittest.skipUnless(OCC, "OCP not installed")
class TestPartCache(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="a3d-partcache-"))
        self.patches = [mock.patch.object(partcache, "DIR", self.tmp / "parts"), mock.patch.object(partcache, "ON", True),
                        mock.patch.object(partcache, "MIN_SECONDS", 0), mock.patch.object(partcache, "_since", None),
                        mock.patch.object(blobs, "DIR", self.tmp / "blobs"), mock.patch.object(filecache, "DIR", self.tmp / "models")]
        for p in self.patches:
            p.start()
        forget()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        forget()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def not_built(self):
        """No step is built (everything from the cache)."""
        return mock.patch.object(doc, "_apply", side_effect=AssertionError("built again"))

    def step_part(self):
        """An imported STEP: the block with a hole, turned about z, as a file."""
        shape = K.placed(doc.body_of({"features": PLATE}).body.shape, [0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1])
        return [{"id": "B1", "type": "solid", "blob": blobs.put(K.to_step(shape, "block"))}]

    def test_round_trip(self):
        """A plate with holes, a rounded part, an imported STEP: from the cache after a restart, the same names on the
        same faces, volume, bbox, mesh; a step added on it names its faces as a fresh build does; STEP keeps it."""
        for what, feats, expect in (("plate", PLATE, 8000 - 8 * math.pi * 1.5 ** 2 * 10),
                                    ("rounded", ROUNDED, 8000 - 4 * (R * R - math.pi * R * R / 4) * 10),
                                    ("step", self.step_part(), 8000 - 8 * math.pi * 1.5 ** 2 * 10)):
            with self.subTest(what):
                forget()
                st, status = doc.evaluate(feats)
                self.assertTrue(all(s["ok"] for s in status), status)
                first = doc.rebuild({"features": feats})
                names, v, box = named(st.body), K.volume(st.body.shape), K.bbox(st.body.shape)
                self.assertAlmostEqual(v, expect, delta=expect * 1e-6)
                self.assertTrue((partcache.DIR / f"{partcache.key(doc._key(feats))}.state").exists())
                forget()
                with self.not_built():
                    st2, status2 = doc.evaluate(feats)
                    again = doc.rebuild({"features": feats})
                self.assertEqual(status2, status)
                self.assertEqual(named(st2.body), names)
                self.assertEqual(K.volume(st2.body.shape), v)
                self.assertEqual(K.bbox(st2.body.shape), box)
                self.assertEqual([f.get("name") for f in again["body"]["faces"]], [f.get("name") for f in first["body"]["faces"]])
                self.assertEqual(again["body"]["positions"], first["body"]["positions"])
                self.assertTrue(watertight(again["body"]))
                self.assertAlmostEqual(K.volume(K.from_step(K.to_step(st2.body.shape))), v, delta=v * 1e-6)
                if what != "step":  # a step more on the part read back: named as on a fresh build
                    on_kept = doc.evaluate(feats + POCKET)[0].body
                    with mock.patch.object(partcache, "ON", False):
                        forget()
                        fresh = doc.evaluate(feats + POCKET)[0].body
                    self.assertEqual(named(on_kept), named(fresh))
                    self.assertAlmostEqual(K.volume(on_kept.shape), K.volume(fresh.shape), delta=1e-6)

    def test_new_key_on_an_edit(self):
        """An edited size is another part: built (not read back), its own entry; the old one is not used for it."""
        doc.evaluate(PLATE)
        edited = [*PLATE[:2], {**PLATE[2], "d": 4}]
        k0, k1 = (partcache.key(doc._key(f)) for f in (PLATE, edited))
        self.assertNotEqual(k0, k1)
        forget()
        with mock.patch.object(doc, "_apply", wraps=doc._apply) as built:
            st, _ = doc.evaluate(edited)
        self.assertGreater(built.call_count, 0)
        self.assertAlmostEqual(K.volume(st.body.shape), 8000 - 8 * math.pi * 2 ** 2 * 10, delta=1e-3)
        self.assertTrue((partcache.DIR / f"{k1}.state").exists())

    def test_another_file_of_the_same_name(self):
        """Another STEP under the same name is another blob sha: another key, its own solid."""
        a = self.step_part()
        box = doc.body_of({"features": [sketch("S1", [RECT]), extrude("E1", "S1", 5)]}).body.shape
        b = [{**a[0], "blob": blobs.put(K.to_step(box, "block"))}]
        self.assertNotEqual(partcache.key(doc._key(a)), partcache.key(doc._key(b)))
        doc.evaluate(a)
        forget()
        st, _ = doc.evaluate(b)
        self.assertAlmostEqual(K.volume(st.body.shape), 4000, delta=1e-3)

    def test_other_app_version(self):
        """Other code (a new app version) or another kernel: every key is new — nothing old is read."""
        doc.evaluate(PLATE)
        forget()
        with mock.patch.object(partcache, "_stamp", "another version"):
            self.assertIsNone(partcache.state(partcache.key(doc._key(PLATE))))
            with mock.patch.object(doc, "_apply", wraps=doc._apply) as built:
                doc.evaluate(PLATE)
            self.assertEqual(built.call_count, len(PLATE))
        self.assertNotEqual(partcache.stamp(), "another version")

    def test_damaged_entry_is_built_again(self):
        doc.evaluate(PLATE)
        k = partcache.key(doc._key(PLATE))
        (partcache.DIR / f"{k}.brep").write_bytes(b"not a shape")
        forget()
        st, status = doc.evaluate(PLATE)
        self.assertTrue(status[-1]["ok"])
        self.assertAlmostEqual(K.volume(st.body.shape), 8000 - 8 * math.pi * 1.5 ** 2 * 10, delta=1e-3)

    def test_failed_steps_and_off(self):
        """A part with a failing step is not kept (a file not here yet is no lasting failure); off: nothing kept."""
        doc.evaluate([{"id": "B1", "type": "solid", "blob": "0" * 64}])
        self.assertFalse(list(partcache.DIR.glob("*.state")))
        with mock.patch.object(partcache, "ON", False):
            doc.evaluate(PLATE)
        self.assertFalse(list(partcache.DIR.glob("*")))

    def test_kept_under_the_limit(self):
        """Past LIMIT_MB the entries used least lately go first, whole (state, B-rep, meshes)."""
        doc.rebuild({"features": PLATE})
        doc.rebuild({"features": ROUNDED})
        k0, k1 = (partcache.key(doc._key(f)) for f in (PLATE, ROUNDED))
        self.assertTrue(list(partcache.DIR.glob(f"{k0}.*.mesh")))
        size = sum(p.stat().st_size for p in partcache.DIR.glob(f"{k1}.*"))
        for p in partcache.DIR.glob(f"{k0}.*"):
            os.utime(p, (1, 1))  # (used long ago)
        with mock.patch.object(partcache, "LIMIT_MB", (size + 1) / (1 << 20)), mock.patch.object(partcache, "_since", None):
            partcache._prune()
        self.assertFalse(list(partcache.DIR.glob(f"{k0}.*")))
        self.assertEqual(len(list(partcache.DIR.glob(f"{k1}.*"))), 3)  # (its state, B-rep and mesh)
        forget()
        doc.evaluate(PLATE)  # (gone: built again and kept again)
        self.assertTrue((partcache.DIR / f"{k0}.state").exists())

    def test_collision_pairs_kept(self):
        """The collision check's pairs: after a restart the same two parts standing alike are not computed again."""
        part = {"features": PLATE}
        inst = [{"id": "a", "part": part}, {"id": "b", "part": part, "matrix": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 30, 0, 5, 1]}]
        first = doc.assembly_clashes(inst)
        self.assertEqual(len(first), 1)
        self.assertTrue(list(partcache.DIR.glob("p*.pair")))
        forget()
        with self.not_built(), mock.patch.object(K, "bop", side_effect=AssertionError("computed again")):
            again = doc.assembly_clashes(inst)
        self.assertEqual(again, first)
        # moved 10 mm along x: another pair, computed
        forget()
        inst[1]["matrix"] = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 20, 0, 5, 1]
        self.assertGreater(doc.assembly_clashes(inst)[0]["volume"], first[0]["volume"])


if __name__ == "__main__":
    unittest.main()
