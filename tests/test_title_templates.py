"""Title-block templates of drawing sheets, kept next to the server (auto3d/title_templates.py)."""
import json
import tempfile
import unittest
from pathlib import Path

from auto3d import title_templates as TT

PNG = "data:image/png;base64,iVBORw0KGgo="


class TestTitleTemplates(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_apps_own_come_first(self):
        names = [t["name"] for t in TT.load(self.dir)]
        self.assertEqual(names[0], "Modern")
        self.assertIn("ISO 5457", names)

    def test_save_load_replace_delete(self):
        kept = TT.save(self.dir, {"name": " ACME  ", "texts": {"company": "ACME s.r.o.", "drawn": "F. Paul", "bogus": "x", "note": "  "},
                                  "hide": ["note", "nope"], "logo": PNG, "layout": "block"})
        self.assertEqual(kept["name"], "ACME")
        self.assertEqual(kept["texts"], {"company": "ACME s.r.o.", "drawn": "F. Paul"})
        self.assertEqual(kept["hide"], ["note"])
        self.assertEqual(kept["frame"]["preset"], "simple")
        on_disk = json.loads((self.dir / TT.FILE).read_text(encoding="utf-8"))
        self.assertEqual([t["name"] for t in on_disk["templates"]], ["ACME"])
        TT.save(self.dir, {"name": "acme", "texts": {"company": "ACME a.s."}})  # (the same name, any case: replaced)
        mine = [t for t in TT.load(self.dir) if not t.get("builtin")]
        self.assertEqual([(t["name"], t["texts"]["company"]) for t in mine], [("acme", "ACME a.s.")])
        TT.delete(self.dir, "ACME")
        self.assertEqual([t for t in TT.load(self.dir) if not t.get("builtin")], [])

    def test_refused(self):
        for bad in ({"name": ""}, {"name": "x" * 61}, {"name": "Modern"}, {"name": "A", "layout": "round"},
                    {"name": "A", "logo": "javascript:alert(1)"}, {"name": "A", "logo": "data:image/png;base64," + "A" * TT.LOGO_MAX},
                    {"name": "A", "frame": {"preset": "custom", "m": ["x"]}}, "not a dict"):
            with self.assertRaises(TT.TemplateError, msg=repr(bad)[:60]):
                TT.save(self.dir, bad)
        with self.assertRaises(TT.TemplateError):
            TT.delete(self.dir, "Modern")
        with self.assertRaises(TT.TemplateError):
            TT.delete(self.dir, "nothing")

    def test_frames(self):
        iso = TT.save(self.dir, {"name": "F", "frame": {"preset": "iso", "m": [1, 1, 1, 1]}})["frame"]
        self.assertEqual((iso["m"], iso["zones"], iso["marks"]), ([20, 10, 10, 10], True, True))  # (a preset's own values)
        own = TT.save(self.dir, {"name": "G", "frame": {"preset": "custom", "m": [25, 5, 5, 99], "line": 9, "zones": 1}})["frame"]
        self.assertEqual((own["m"], own["line"], own["zones"], own["marks"]), ([25, 5, 5, 40], 2.0, True, False))
        self.assertEqual(TT.save(self.dir, {"name": "H", "frame": {"preset": "custom", "m": [12]}})["frame"]["m"], [12, 12, 12, 12])

    def test_a_broken_file_is_no_templates_of_the_user(self):
        (self.dir / TT.FILE).write_text("{oops", encoding="utf-8")
        self.assertTrue(all(t.get("builtin") for t in TT.load(self.dir)))


if __name__ == "__main__":
    unittest.main()
