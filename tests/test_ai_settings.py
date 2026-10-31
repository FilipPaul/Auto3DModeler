"""✨ AI settings (auto3d/ai_settings.py): the line the AI gets before a message, the #tags of one message, when the
chat sends the line (only when it changed), ⚡ Lean mode's tool groups (the MCP server lists fewer; another group: the
process starts again, its session resumed) and the settings kept in the project file.

Run:  py -m unittest tests.test_ai_settings -v
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from auto3d import ai_settings  # noqa: E402
from auto3d.ai_settings import clean, parse_tags, settings_line  # noqa: E402

DEFAULT_LINE = ("[Nastavení: profil=automatizace; výroba=CNC; ptát=klíčové; odpovědi=stručně; "
                "zásady=standard-parts,machined-part,easy-assembly,design-review; režimy=-; internet=ano]")


class Proc:
    """A running claude process that records what it is sent."""

    def __init__(self):
        self.lines, self.stdin, self.ended = [], self, False

    def poll(self):
        return 0 if self.ended else None

    def write(self, b):
        self.lines.append(json.loads(b.decode("utf-8")))

    def flush(self):
        pass

    def terminate(self):
        self.ended = True

    def wait(self, timeout=None):
        return 0

    def text(self, i=-1):
        return self.lines[i]["message"]["content"][-1]["text"]


class LineTest(unittest.TestCase):
    def test_default_line(self):
        self.assertEqual(settings_line({}), DEFAULT_LINE)
        self.assertEqual(settings_line(None), DEFAULT_LINE)

    def test_profiles_and_choices(self):
        deco = {**ai_settings.DEFAULTS, "profile": "deco", **ai_settings.PROFILES["deco"]}
        self.assertEqual(settings_line(deco), "[Nastavení: profil=dekorace; výroba=3D-tisk; ptát=klíčové; odpovědi=stručně; "
                                              "zásady=-; režimy=-; internet=ano]")
        s = {"profile": "custom", "make": ["cnc", "laser"], "ask": "none", "answers": "explain", "standard": False,
             "dfm": True, "dfa": False, "review": False, "teach": True, "bugs": True, "lean": True, "internet": False}
        line = settings_line(s)
        self.assertIn("profil=vlastní", line)
        self.assertIn("výroba=CNC,laser", line)
        self.assertIn("ptát=neptat; odpovědi=vysvětlit", line)
        self.assertIn("zásady=machined-part,easy-manufacture;", line)
        self.assertIn("režimy=teach-me,bug-hunter,lean; internet=ne]", line)
        # short: well under ~100 tokens (≈ 3 characters a token for Czech words), everything on
        full = settings_line({**s, "make": list(ai_settings.MAKES), "standard": True, "dfa": True, "review": True})
        self.assertLess(len(full), 300, full)

    def test_clean_takes_only_valid_values(self):
        s = clean({"profile": "spaceship", "make": ["cnc", "wood", "print"], "ask": 3, "review": "yes", "lean": True, "x": 1})
        self.assertEqual(s["profile"], "automation")
        self.assertEqual(s["make"], ["cnc", "print"])
        self.assertEqual(s["ask"], "key")
        self.assertTrue(s["review"])  # (not a bool: the default)
        self.assertTrue(s["lean"])
        self.assertNotIn("x", s)


class TagTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_tags("Udělej držák senzoru #uc #cnc"), ("Udělej držák senzoru", ["uc", "cnc"]))
        self.assertEqual(parse_tags("#rychle díra Ø5 #RYCHLE"), ("díra Ø5", ["rychle"]))
        self.assertEqual(parse_tags("#uč mě #bez-otázek"), ("mě", ["uc", "bez-otazek"]))
        self.assertEqual(parse_tags("šroub #5 a#uc #neznamy"), ("šroub #5 a#uc #neznamy", []))
        self.assertEqual(parse_tags("první řádek #tisk\n#kontrola druhý"), ("první řádek\ndruhý", ["tisk", "kontrola"]))
        self.assertEqual(parse_tags("#chyby"), ("", ["chyby"]))

    def test_tags_change_the_line(self):
        line = settings_line({}, ["uc", "tisk"])
        self.assertIn("výroba=3D-tisk", line)
        self.assertIn("zásady=standard-parts,print-functional,easy-assembly,design-review", line)
        self.assertIn("režimy=teach-me;", line)
        quick = settings_line({"answers": "explain"}, ["rychle"])
        self.assertIn("odpovědi=stručně", quick)
        self.assertNotIn("design-review", quick)
        self.assertIn("režimy=lean", quick)
        self.assertIn("ptát=neptat", settings_line({}, ["bez-otazek"]))
        self.assertIn("design-review", settings_line({"review": False}, ["kontrola"]))
        self.assertIn("režimy=bug-hunter", settings_line({}, ["chyby"]))
        self.assertTrue(ai_settings.lean({}, ["rychle"]))
        self.assertFalse(ai_settings.lean({}))


class ToolGroupTest(unittest.TestCase):
    def test_groups_are_real_tools_and_smaller(self):
        from auto3d.agent_tools import TOOL_GROUPS, TOOL_NAMES, mcp_tool_list
        full = mcp_tool_list()
        size = lambda tools: sum(len(json.dumps(t)) for t in tools)  # noqa: E731
        for g, names in TOOL_GROUPS.items():
            self.assertLessEqual(set(names), TOOL_NAMES, g)
            lean = mcp_tool_list(g)
            self.assertLess(len(lean), len(full), g)
            self.assertLess(size(lean), size(full) * 0.6, g)  # (⚡ saves ≥ 40 % of the schemas)
            self.assertIn("get_guide", {t["name"] for t in lean})  # (the general ones always)
        self.assertIn("add_feature", {t["name"] for t in mcp_tool_list("model")})
        self.assertNotIn("add_feature", {t["name"] for t in mcp_tool_list("assembly")})
        self.assertEqual(len(mcp_tool_list("nonsense")), len(full))
        self.assertEqual(ai_settings.tool_group("assembly"), "assembly")
        self.assertEqual(ai_settings.tool_group("start"), "general")

    def test_mcp_server_lists_its_group(self):
        from auto3d import mcp_server
        full = len(mcp_server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, "")["result"]["tools"])
        mcp_server.GROUP = "drawing"
        try:
            tools = mcp_server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, "")["result"]["tools"]
        finally:
            mcp_server.GROUP = None
        self.assertLess(len(tools), full)
        self.assertIn("drawing_add", {t["name"] for t in tools})


class ChatTest(unittest.TestCase):
    def chat(self):
        from auto3d.agent import ChatSession
        s = ChatSession("http://127.0.0.1:1", "win-A")
        s.started = []

        def start(resume=True):  # (no Claude Code here: a recording process; its command kept)
            s.started.append(s.command("claude", s.conv.get("session") if s.conv else None))
            s.proc = Proc()
            return ""
        s.start = start
        return s

    def test_line_only_when_it_changes(self):
        s = self.chat()
        s.send("Udělej desku", settings={})
        self.assertTrue(s.proc.text().startswith(DEFAULT_LINE + "\n\nUdělej desku"), s.proc.text())
        s.send("Přidej díru", settings={})
        self.assertEqual(s.proc.text(), "Přidej díru")  # (the AI has it)
        s.send("Zaobli hrany #uc #cnc", settings={})
        self.assertTrue(s.proc.text().startswith("[Nastavení:") and "režimy=teach-me" in s.proc.text(), s.proc.text())
        self.assertTrue(s.proc.text().endswith("\n\nZaobli hrany"), s.proc.text())  # (the tags out of the text)
        user = [e for e in s.history if e["type"] == "user"]
        self.assertEqual((user[-1]["text"], user[-1]["tags"]), ("Zaobli hrany", ["uc", "cnc"]))
        self.assertNotIn("tags", user[0])
        s.send("A ještě", settings={})
        self.assertEqual(s.proc.text(), DEFAULT_LINE + "\n\nA ještě")  # (back to the project's settings: told again)
        s.send("Další", settings={"answers": "normal"})
        self.assertIn("odpovědi=normálně", s.proc.text())
        s.send("Bez nastavení")  # (a page / client that sends none: no line)
        self.assertEqual(s.proc.text(), "Bez nastavení")
        s.reset()
        s.send("Nová", settings={"answers": "normal"})
        self.assertIn("odpovědi=normálně", s.proc.text())  # (a new conversation: told again)
        # the conversation keeps the tags (🕘 a reopened one shows its chips)
        from auto3d import chat_history
        self.assertEqual(chat_history.keep({"type": "user", "text": "x", "tags": ["uc"]})["tags"], ["uc"])

    def test_tags_with_attached_files(self):
        """📎 a file and #tags in one message: the line, the text, the file's text; the event (and the kept
        conversation) has both the files and the tags."""
        from auto3d import chat_history
        s = self.chat()
        s.send("Podívej #cnc", files=[{"name": "a.csv", "size": 12, "path": "C:\\x\\a.csv", "text": "[Attached file a.csv]\nx,y"}],
               settings={})
        got = s.proc.text()
        self.assertTrue(got.startswith("[Nastavení: profil=automatizace; výroba=CNC;"), got)
        self.assertIn("\n\nPodívej\n\n[Attached file a.csv]\nx,y", got)
        ev = [e for e in s.history if e["type"] == "user"][-1]
        self.assertEqual((ev["text"], ev["tags"], ev["files"][0]["name"]), ("Podívej", ["cnc"], "a.csv"))
        kept = chat_history.keep(ev)
        self.assertEqual((kept["tags"], kept["files"]), (["cnc"], [{"name": "a.csv", "size": 12, "path": "C:\\x\\a.csv"}]))
        s.send("#cnc", files=[{"name": "b.txt", "size": 1, "path": "C:\\x\\b.txt", "text": "[Attached file b.txt]"}], settings={})
        self.assertEqual(s.proc.text(), "[Attached file b.txt]")  # (the line unchanged: not again, the file goes)

    def test_lean_mode_restarts_with_the_workspace_group(self):
        s = self.chat()
        s.send("Ahoj", settings={}, workspace="model")
        self.assertNotIn("--group", s.started[-1][s.started[-1].index("--mcp-config") + 1])
        first = s.proc
        s.conv["session"] = "sess-1234"
        s.send("Úsporně", settings={"lean": True}, workspace="model")
        self.assertTrue(first.ended)  # (another tool list: the process starts again …)
        self.assertEqual(len(s.started), 2)
        mcp = json.loads(s.started[-1][s.started[-1].index("--mcp-config") + 1])["mcpServers"]["auto3d"]["args"]
        self.assertEqual(mcp[mcp.index("--group") + 1], "model")
        self.assertEqual(s.started[-1][s.started[-1].index("--resume") + 1], "sess-1234")  # (… its session resumed)
        exits = [e for e in s.history if e["type"] == "exit"]
        self.assertEqual(exits, [])  # (unseen: no "Claude Code stopped")
        s.send("Dál", settings={"lean": True}, workspace="model")
        self.assertEqual(len(s.started), 2)  # (the same group: the same process)
        s.send("Sestava", settings={"lean": True}, workspace="assembly")
        self.assertEqual(len(s.started), 3)
        s.send("#rychle jen rychle", settings={}, workspace="assembly")  # (lean for one message by its tag)
        self.assertEqual(len(s.started), 3)
        s.send("Normálně", settings={}, workspace="assembly")
        self.assertEqual(len(s.started), 4)
        self.assertNotIn("--group", s.started[-1][s.started[-1].index("--mcp-config") + 1])

    def test_internet_setting_for_the_server(self):
        """🌐 kept in <data>/ai/settings.json (what the chat's start reads); a change restarts the process unseen."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "ai" / "settings.json"
            self.assertFalse(ai_settings.save_internet(tmp, True))  # (none there: on already)
            self.assertFalse(f.exists())
            self.assertTrue(ai_settings.save_internet(tmp, False))
            self.assertEqual(json.loads(f.read_text(encoding="utf-8")), {"internet": False})
            self.assertFalse(ai_settings.save_internet(tmp, False))
            f.write_text(json.dumps({"internet": False, "other": 1}), encoding="utf-8")
            self.assertTrue(ai_settings.save_internet(tmp, True))
            self.assertEqual(json.loads(f.read_text(encoding="utf-8")), {"internet": True, "other": 1})  # (other keys kept)
        s = self.chat()
        s.send("Ahoj", settings={})
        s.send("Dál", settings={"internet": True})
        self.assertEqual(len(s.started), 1)
        s.send("Bez internetu", settings={"internet": False})
        self.assertEqual(len(s.started), 2)  # (its flags are fixed at the start: started again)
        s.send("Pořád bez", settings={"internet": False})
        self.assertEqual(len(s.started), 2)

    def test_server_passes_settings_and_workspace(self):
        import server
        sent = []

        class Stub:
            def send(self, text, photos, files=None, settings=None, workspace=None):
                sent.append((text, settings, workspace))

        orig = server._chat
        server._chat = lambda client="": Stub()
        try:
            c = server.app.test_client()
            c.post("/api/chat/send", json={"text": "hi #uc", "settings": {"lean": True}, "workspace": "model"})
            c.post("/api/chat/send", json={"text": "old page"})
        finally:
            server._chat = orig
        self.assertEqual(sent, [("hi #uc", {"lean": True}, "model"), ("old page", None, None)])


class ProjectTest(unittest.TestCase):
    def test_project_keeps_the_settings(self):
        from auto3d.project import migrate
        base = {"app": "Auto3DModeler", "version": 3, "project_name": "P", "parts": [{"id": "P1", "kind": "model", "name": "A", "model": {}}]}
        self.assertEqual(migrate({**base, "ai_settings": {"profile": "deco"}})["ai_settings"], {"profile": "deco"})
        self.assertNotIn("ai_settings", migrate({**base, "ai_settings": "nonsense"}))
        self.assertNotIn("ai_settings", migrate(base))  # (an older project: the app's default applies)


if __name__ == "__main__":
    unittest.main()
