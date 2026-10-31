"""Every AI tool call that fails is logged for the developers on its own (auto3d/tool_errors.py, through
/api/agent/call): one digest a day in the reports folder, the same error counted, deliberate refusals left out."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from auto3d import reports, tool_errors


class TestToolErrorLog(unittest.TestCase):
    def setUp(self):
        import server
        self.server = server
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name) / "RealSWReports"
        for p in (mock.patch.object(server, "REPORTS", self.folder), mock.patch.object(server, "LOG_TOOL_ERRORS", True)):
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)
        self.c = server.app.test_client()

    def call(self, tool, args, page=None):
        """A tool call through the relay; page: what the browser answers (else the server tool runs)."""
        if page is None:
            r = self.c.post("/api/agent/call", json={"tool": tool, "args": args, "client": "W1"}).get_json()
        else:
            with mock.patch.object(self.server.RELAY, "call", return_value=page):
                r = self.c.post("/api/agent/call", json={"tool": tool, "args": args, "client": "W1"}).get_json()
        tool_errors.flush()
        return r

    def log(self):
        days = sorted(self.folder.glob(f"*{tool_errors.SUFFIX}.json"))
        return json.loads(days[-1].read_text(encoding="utf-8")) if days else {"entries": []}

    def test_failed_calls_logged_and_counted(self):
        r = self.call("open_file", {"path": str(Path(self.tmp.name) / "nope1.stl")})
        self.assertTrue(r["isError"])
        data = self.log()
        self.assertEqual(len(data["entries"]), 1)
        e = data["entries"][0]
        self.assertEqual((e["tool"], e["count"]), ("open_file", 1))
        self.assertIn("No such file", e["error"])
        self.assertIn("nope1.stl", e["args"])
        self.assertTrue(data["version"])  # (the app's version line, as reports have it)
        # the same error with another number in it: counted, not a new entry
        self.call("open_file", {"path": str(Path(self.tmp.name) / "nope2.stl")})
        data = self.log()
        self.assertEqual([x["count"] for x in data["entries"]], [2])
        # a browser tool's error result (the page says where it happened)
        page = {"text": "No step f99 in the model (steps: f1, f2).", "error": True, "where": {"workspace": "model", "part": "Bracket"}}
        self.call("edit_feature", {"id": "f99", "distance": 5}, page)
        self.call("edit_feature", {"id": "f42"}, {**page, "text": "No step f42 in the model (steps: f1)."})
        data = self.log()
        ed = next(x for x in data["entries"] if x["tool"] == "edit_feature")
        self.assertEqual((ed["count"], ed["where"]), (2, {"workspace": "model", "part": "Bracket"}))
        md = next(self.folder.glob(f"*{tool_errors.SUFFIX}.md")).read_text(encoding="utf-8")
        self.assertIn("- **Kind:** tool errors", md)
        self.assertIn("## 1. open_file — ×2", md)
        self.assertIn("workspace model · part Bracket", md)
        # a good call is not logged
        self.call("get_part", {}, {"text": "ok"})
        self.assertEqual(sum(x["count"] for x in self.log()["entries"]), 4)

    def test_refusals_not_logged(self):
        self.call("edit_feature", {"id": "f1"}, {"text": "🔒 The AI may not change this part (locked by the user).", "error": True})
        self.call("library_search", {"text": "x"}, {"text": "library_search failed: Internet je vypnutý — zapněte ho v nastavení.", "error": True})
        self.call("edit_feature", {"id": "f1"}, {"text": "Use a smaller fillet.", "error": True, "expected": True})
        self.assertEqual(self.log()["entries"], [])
        self.assertFalse(self.folder.exists() and any(self.folder.iterdir()))

    def test_args_shortened(self):
        big = {"image": "iVBORw0KGgo" + "A" * 50000, "note": "word " * 200, "points": list(range(1000))}
        self.call("add_feature", big, {"text": "The sketch does not close.", "error": True})
        args = self.log()["entries"][0]["args"]
        self.assertLessEqual(len(args), tool_errors.ARGS_MAX + 40)
        self.assertIn("<50011 characters of data>", args)
        self.assertNotIn("AAAAAAAAAA", args)
        self.assertIn("characters)", args)  # (the note: its start and its length)

    def test_cap_and_reports(self):
        with mock.patch.object(tool_errors, "MAX_ENTRIES", 3):
            for i, word in enumerate(["alpha", "beta", "gamma", "delta", "epsilon"]):
                tool_errors.write(self.folder, {"time": "2026-10-31 10:00:0%d" % i, "tool": "t", "error": f"{word} broke",
                                                "key": tool_errors.key("t", f"{word} broke"), "args": "{}", "version": "1.0",
                                                "where": {}, "conversation": "c1"})
        data = json.loads((self.folder / f"2026-10-31{tool_errors.SUFFIX}.json").read_text(encoding="utf-8"))
        self.assertEqual((len(data["entries"]), data["left_out"]), (3, 2))
        self.assertEqual(data["entries"][0]["conversations"], ["c1"])
        # the digest is not a report (report_problem's look-alike check, list_reports' rows leave it out)
        self.assertEqual(reports.read(self.folder), [])
        self.assertEqual(self.server.tool_list_reports({"search": "alpha"})["text"], "No reports match.")

    def test_list_reports_shows_top_errors(self):
        for n in (1, 2, 3):
            self.call("open_file", {"path": f"nope{n}.stl"})
        self.call("edit_feature", {"id": "f9"}, {"text": "No step f9.", "error": True})
        text = self.server.tool_list_reports({})["text"]
        self.assertTrue(text.startswith("No reports yet."))
        top = json.loads(text.rsplit(".md): ", 1)[1])
        self.assertEqual([(r["tool"], r["count"]) for r in top], [("open_file", 3), ("edit_feature", 1)])
        self.assertIn("open_file", self.server.tool_list_reports({"kind": "tool errors"})["text"])

    def test_key_and_failures_never_break(self):
        self.assertEqual(tool_errors.key("x", "x failed: No step f12 in “Part 3”"), tool_errors.key("x", "No step s4 in “Bracket”"))
        self.assertNotEqual(tool_errors.key("x", "No step f1"), tool_errors.key("y", "No step f1"))
        # a folder that cannot be written (a file in its place): the call still answers
        self.folder.parent.mkdir(parents=True, exist_ok=True)
        self.folder.write_text("not a folder")
        r = self.call("open_file", {"path": "nope.stl"})
        self.assertTrue(r["isError"])
        self.assertIn("No such file", r["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
