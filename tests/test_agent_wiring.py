"""Every AI tool is wired all the way: TOOLS (auto3d/agent_tools.py) <-> the MCP server's tools/list <-> the page's
handlers (web/js: the browser tools) <-> the server's own tools (server.py SERVER_TOOLS) <-> the chat's labels
(web/js/agent.js TOOL_LABEL) <-> the skills. A tool added to one place and not the others fails here, not in the chat.

The page's handlers are read from the JS sources (no browser): the `name: async (` keys inside the places that build
`agentHandlers` (app.js) and the handler functions it merges in.

Run:  py -m unittest tests.test_agent_wiring -v
"""
import json
import re
import subprocess
import sys
import unittest
import unittest.mock
from pathlib import Path

from auto3d.agent_tools import BROWSER_TOOLS, LOCAL_TOOLS, SYSTEM_PROMPT, TOOL_NAMES, TOOLS, mcp_tool_list
from auto3d.guides import guides

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "web" / "js"

# where the page's tool handlers are made: (file, the text that opens the object / function holding them)
HANDLER_BLOCKS = [
    ("app.js", "const agentHandlers = {"),
    ("app.js", "Object.assign(agentHandlers, assembly.handlers(), {"),
    ("app.js", "const libraryTools = {"),
    ("app.js", "Object.assign(agentHandlers, {\n  set_look"),
    ("agent_more.js", "export function moreHandlers("),
    ("agent_teach.js", "export function teachHandlers("),
    ("paramsui.js", "export function paramHandlers("),
    ("versions.js", "  handlers() {"),
    ("modeler/agent_model.js", "export function modelHandlers("),
    ("modeler/agent_sketch.js", "export function sketchHandlers("),
    ("assembly/assembly.js", "  handlers() {"),
]
# the page's handlers that are no AI tool of their own: the server's relays (open_file -> load …) and the 3D model's
# versions of the shared tools (app.js SHARED: get_screenshot / undo follow the part on screen)
INTERNAL = {"load", "load_drawing", "load_solid", "load_step_assembly", "load_project", "get_body",
            "model_screenshot", "model_body", "model_undo"}


def _block(text: str, start: str) -> str:
    """The text from `start` to the brace that closes the last one opened on its line (a function's body, not its
    destructured arguments)."""
    i = text.index(start)
    j = text.rindex("{", i, text.index("\n", i))
    depth = 0
    for k in range(j, len(text)):
        c = text[k]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[i:k + 1]
    raise AssertionError(f"unbalanced braces after {start!r}")


def page_handlers() -> set:
    out = set()
    for f, start in HANDLER_BLOCKS:
        body = _block((JS / f).read_text(encoding="utf-8"), start)
        out |= set(re.findall(r"^\s*([a-z_][a-z0-9_]*): async \(", body, re.M))
    return out


def server_tools() -> set:
    src = (ROOT / "server.py").read_text(encoding="utf-8")
    block = re.search(r"^SERVER_TOOLS = \{(.*?)\}\n", src, re.S | re.M).group(1)
    return set(re.findall(r'"([a-z_]+)":', block))


class TestWiring(unittest.TestCase):
    def test_every_browser_tool_has_a_handler_and_back(self):
        found = page_handlers()
        self.assertFalse(BROWSER_TOOLS - found, "browser tools without a handler in the page")
        self.assertFalse(found - BROWSER_TOOLS - INTERNAL, "page handlers that are no tool (add it to TOOLS, or to INTERNAL here)")

    def test_every_server_tool_is_served(self):
        server = {t["name"] for t in TOOLS if t["where"] == "server"}
        self.assertEqual(server, server_tools())
        self.assertEqual(TOOL_NAMES, BROWSER_TOOLS | LOCAL_TOOLS | server)  # (no fourth kind)

    def test_mcp_lists_them(self):
        """The real MCP server process lists every tool that is not hidden — Claude Code (--allowedTools mcp__auto3d)
        may call all of them."""
        p = subprocess.Popen([sys.executable, str(ROOT / "auto3d" / "mcp_server.py"), "--url", "http://127.0.0.1:9"],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        out, _ = p.communicate((json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) + "\n").encode(), timeout=30)
        names = [t["name"] for t in json.loads(out.decode())["result"]["tools"]]
        self.assertEqual(names, [t["name"] for t in mcp_tool_list()])
        self.assertEqual(set(names), {t["name"] for t in TOOLS if not t.get("hidden")})
        self.assertEqual(len(names), len(set(names)))  # (no tool twice)
        src = (ROOT / "auto3d" / "agent.py").read_text(encoding="utf-8")
        self.assertIn('"--allowedTools", "mcp__auto3d', src)  # the whole server: a new tool needs no new permission

    def test_the_chat_names_what_it_does(self):
        """The chat shows "reading the 3D model …" while a tool runs: every tool the AI sees has its words."""
        src = (JS / "agent.js").read_text(encoding="utf-8")
        labels = set(re.findall(r"\b([a-z_]+): '", _block(src, "const TOOL_LABEL = {")))
        missing = {t["name"] for t in mcp_tool_list()} - labels
        self.assertFalse(missing, "tools without a TOOL_LABEL in web/js/agent.js")

    def test_skills_name_the_tools(self):
        """Every tool the AI sees is named in a skill or the system prompt — else it is unlikely to be used."""
        text = SYSTEM_PROMPT + "".join(g["text"] for g in guides().values())
        unnamed = sorted(n for n in (t["name"] for t in mcp_tool_list()) if not re.search(rf"\b{n}\b", text))
        self.assertFalse(unnamed, "tools no skill and not the system prompt names")
        topics = next(t for t in TOOLS if t["name"] == "get_guide")["inputSchema"]["properties"]["topic"]["enum"]
        self.assertEqual(sorted(topics), sorted(guides()))


class TestProjectTools(unittest.TestCase):
    """list_demos / open_demo and open_file of a project file: the server reads them and hands the page a version 3
    project (load_project) — the page's side is in tools/e2e_agent.py."""

    def setUp(self):
        import server
        self.server, self.sent = server, []
        self._call = server.RELAY.call
        server.RELAY.call = lambda cmd, args=None, timeout=150.0: (self.sent.append((cmd, args)), {"text": "Opened."})[1]

    def tearDown(self):
        self.server.RELAY.call = self._call

    def call(self, tool, **args):
        r = self.server.app.test_client().post("/api/agent/call", json={"tool": tool, "args": args}).get_json()
        return r["content"][0]["text"], r["isError"]

    def test_demos(self):
        text, err = self.call("list_demos")
        rows = json.loads(text)
        self.assertFalse(err)
        self.assertTrue(any(d["file"] == "klikovy-mechanismus.a3d.json" for d in rows))
        self.assertTrue(all(d["name"] and d["name_cs"] and d["parts"] for d in rows))
        text, err = self.call("open_demo", name="crank")  # (words of its English name)
        self.assertFalse(err, text)
        cmd, args = self.sent[-1]
        self.assertEqual(cmd, "load_project")
        self.assertEqual(args["project"]["version"], 3)
        self.assertTrue(any(p["kind"] == "assembly" for p in args["project"]["parts"]))
        self.call("open_demo", name="Čtyřkloubový mechanismus")  # (its Czech name)
        self.assertEqual(len(self.sent), 2)
        text, err = self.call("open_demo", name="spaceship")
        self.assertTrue(err)
        self.assertIn("klikovy-mechanismus.a3d.json", text)  # (it names the ones there are)
        self.assertEqual(len(self.sent), 2)

    def test_open_a_project_file(self):
        import base64
        import tempfile
        from auto3d.modeler import blobs
        data = b"solid j-aicov test blob\n"
        sha = __import__("hashlib").sha256(data).hexdigest()
        proj = {"app": "Auto3DModeler", "version": 3, "project_name": "Saved", "parts": [{"id": "p1", "name": "Plate", "kind": "model", "data": {"features": []}}],
                "blobs": {sha: base64.b64encode(data).decode()}, "versions": {"x": 1}}
        with tempfile.TemporaryDirectory() as tmp, unittest.mock.patch.object(blobs, "DIR", Path(tmp) / "blobs"):
            f = Path(tmp) / "saved.a3d.json"
            f.write_text(json.dumps(proj), encoding="utf-8")
            text, err = self.call("open_file", path=str(f))
            self.assertFalse(err, text)
            cmd, args = self.sent[-1]
            self.assertEqual(cmd, "load_project")
            self.assertEqual(args["project"]["parts"][0]["name"], "Plate")
            self.assertNotIn("blobs", args["project"])
            self.assertEqual(args["versions"], {"x": 1})  # (the 🕘 history goes along, the page bundles it in)
            self.assertEqual(blobs.get(sha), data)  # (its imported files are in the store again)
            f.write_text("{not json", encoding="utf-8")
            text, err = self.call("open_file", path=str(f))
            self.assertTrue(err)
            self.assertIn("not a project file", text)


if __name__ == "__main__":
    unittest.main()
