"""The AI agent plumbing: the MCP server (stdio JSON-RPC), the browser relay, Claude Code's stream-json
events -> chat events, and the server-side tools.

Run:  python -m unittest discover -s tests -v
"""
import base64
import json
import subprocess
import sys
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from auto3d.agent import Relay, find_claude, translate
from auto3d.agent_tools import BROWSER_TOOLS, TOOLS, mcp_tool_list

ROOT = Path(__file__).resolve().parent.parent
MCP = ROOT / "auto3d" / "mcp_server.py"


class StubApp(BaseHTTPRequestHandler):
    """Stands in for /api/agent/call: echoes the tool call back as the result text."""
    calls = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        StubApp.calls.append(body)
        out = json.dumps({"content": [{"type": "text", "text": f"ran {body['tool']} {json.dumps(body['args'])}"}],
                          "isError": False}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


class TestMcpServer(unittest.TestCase):
    def test_protocol_over_stdio(self):
        srv = HTTPServer(("127.0.0.1", 0), StubApp)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{srv.server_address[1]}"
        p = subprocess.Popen([sys.executable, str(MCP), "--url", url], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                                                                            "clientInfo": {"name": "test", "version": "1"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "add_object", "arguments": {"kind": "cylinder", "x": 5}}},
            {"jsonrpc": "2.0", "id": 4, "method": "ping"},
            {"jsonrpc": "2.0", "id": 5, "method": "nope"},
        ]
        out, _ = p.communicate(("\n".join(json.dumps(m) for m in msgs) + "\n").encode(), timeout=30)
        srv.shutdown()
        resps = {r["id"]: r for r in map(json.loads, out.decode().splitlines())}
        self.assertEqual(sorted(resps), [1, 2, 3, 4, 5])  # no answer to the notification
        self.assertEqual(resps[1]["result"]["protocolVersion"], "2025-06-18")
        self.assertIn("tools", resps[1]["result"]["capabilities"])
        names = [t["name"] for t in resps[2]["result"]["tools"]]
        self.assertEqual(names, [t["name"] for t in TOOLS])
        self.assertTrue(all("inputSchema" in t and "where" not in t for t in resps[2]["result"]["tools"]))
        self.assertEqual(resps[3]["result"]["content"][0]["text"], 'ran add_object {"kind": "cylinder", "x": 5}')
        self.assertEqual(resps[4]["result"], {})
        self.assertEqual(resps[5]["error"]["code"], -32601)
        self.assertEqual(StubApp.calls[-1], {"tool": "add_object", "args": {"kind": "cylinder", "x": 5}})

    def test_app_not_running_is_a_tool_error(self):
        import socket
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))  # a port nothing listens on (fixed ports may be taken, e.g. 9 = discard)
        port = sock.getsockname()[1]
        sock.close()
        p = subprocess.Popen([sys.executable, str(MCP), "--url", f"http://127.0.0.1:{port}"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        msg = {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "get_part", "arguments": {}}}
        out, _ = p.communicate((json.dumps(msg) + "\n").encode(), timeout=60)
        r = json.loads(out.decode().splitlines()[0])["result"]
        self.assertTrue(r["isError"])
        self.assertIn("not reachable", r["content"][0]["text"])

    def test_guides_and_prompts_without_the_app(self):
        # nothing listens on this url: guides are answered by the MCP server itself
        p = subprocess.Popen([sys.executable, str(MCP), "--url", "http://127.0.0.1:1"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "get_guide", "arguments": {"topic": "model-a-part"}}},
                {"jsonrpc": "2.0", "id": 3, "method": "prompts/list"},
                {"jsonrpc": "2.0", "id": 4, "method": "prompts/get", "params": {"name": "print-prep"}},
                {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "get_guide", "arguments": {"topic": "x"}}}]
        out, _ = p.communicate(("\n".join(json.dumps(m) for m in msgs) + "\n").encode(), timeout=30)
        r = {x["id"]: x for x in map(json.loads, out.decode().splitlines())}
        self.assertIn("prompts", r[1]["result"]["capabilities"])
        self.assertIn("get_guide", r[1]["result"]["instructions"])
        self.assertIn("find_refs", r[2]["result"]["content"][0]["text"])
        self.assertEqual(sorted(x["name"] for x in r[3]["result"]["prompts"]), ["assemble-parts", "automation-design", "change-a-model", "from-picture", "mechanical-design", "model-a-part", "print-prep"])
        self.assertIn("check_print", r[4]["result"]["messages"][0]["content"]["text"])
        self.assertTrue(r[5]["result"]["isError"])

    def test_chat_loads_the_skills(self):
        from auto3d.agent import ChatSession
        from auto3d.guides import PLUGIN_DIR
        cmd = ChatSession("http://127.0.0.1:1").command("claude")
        self.assertEqual(cmd[cmd.index("--tools") + 1], "Skill")  # no files, no shell: only the skills
        self.assertIn("Skill", cmd[cmd.index("--allowedTools") + 1])
        self.assertEqual(cmd[cmd.index("--plugin-dir") + 1], str(PLUGIN_DIR))
        self.assertTrue((PLUGIN_DIR / ".claude-plugin" / "plugin.json").exists())
        for name in ("model-a-part", "from-picture", "print-prep", "change-a-model", "assemble-parts", "mechanical-design", "automation-design"):
            text = (PLUGIN_DIR / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\nname: " + name), name)
        # every tool a skill tells the AI to use exists
        import re
        names = {t["name"] for t in TOOLS}
        for f in (PLUGIN_DIR / "skills").glob("*/SKILL.md"):
            for used in set(re.findall(r"`([a-z_]+) \{", f.read_text(encoding="utf-8"))):
                self.assertIn(used, names, f"{f.parent.name} uses {used}")

    def test_report_problem(self):
        """The AI's report of something that did not behave as expected: a dated Markdown file in RealSWReports."""
        import tempfile
        from pathlib import Path
        from unittest import mock
        import server
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(server, "REPORTS", Path(tmp) / "RealSWReports"), mock.patch.object(server, "ROOT", Path(tmp)):
            r = server.tool_report_problem({"title": "Paint does not show in the assembly", "what": "paint_faces said ok, the face stayed grey",
                                            "expected": "an orange beak", "steps": "paint_faces {faces: [\"F6\"], color: \"#FF8800\"}"})
            files = list((Path(tmp) / "RealSWReports").glob("*.md"))
            self.assertEqual(len(files), 1)
            self.assertRegex(files[0].name, r"^\d{4}-\d{2}-\d{2}-\d{6}-paint-does-not-show-in-the-assembly\.md$")
            text = files[0].read_text(encoding="utf-8")
            for part in ("# Paint does not show in the assembly", "**Date:**", "## What happened", "## What was expected", "## Steps"):
                self.assertIn(part, text)
            self.assertIn("RealSWReports/", r["text"])
            with self.assertRaises(ValueError):
                server.tool_report_problem({"title": "", "what": "x"})

    def test_tool_schemas(self):
        for t in mcp_tool_list():
            self.assertEqual(t["inputSchema"]["type"], "object", t["name"])
            self.assertTrue(t["description"])
        self.assertIn("get_part", BROWSER_TOOLS)
        for name in ("set_look", "paint_faces", "move_free", "save_to_library", "library_search", "library_add", "check_collisions"):
            self.assertIn(name, BROWSER_TOOLS)
        self.assertNotIn("report_problem", BROWSER_TOOLS)  # the server writes it
        self.assertNotIn("trace_picture", BROWSER_TOOLS)


class TestRelay(unittest.TestCase):
    def test_round_trip_and_not_connected(self):
        relay = Relay()
        with self.assertRaises(RuntimeError):
            relay.call("get_part")  # no page has polled yet

        def page():
            cmd = relay.poll(5)
            relay.resolve(cmd["id"], {"text": f"page did {cmd['cmd']} with {cmd['args']['n']}"})

        relay.last_poll = time.time()
        threading.Thread(target=page, daemon=True).start()
        self.assertEqual(relay.call("get_part", {"n": 3}, timeout=5), {"text": "page did get_part with 3"})

    def test_lost_command_is_handed_out_again(self):
        """A page that took a command and went away (reload): another poll gets it after the lease."""
        relay = Relay(lease=0.3)
        relay.last_poll = time.time()
        got = []

        def pages():
            got.append(relay.poll(5))          # the old page takes it and never answers
            cmd = relay.poll(5)                # the reloaded page gets it again after the lease
            got.append(cmd)
            relay.resolve(cmd["id"], {"text": "done"})

        threading.Thread(target=pages, daemon=True).start()
        self.assertEqual(relay.call("get_part", timeout=5), {"text": "done"})
        self.assertEqual(got[0]["id"], got[1]["id"])

    def test_commands_go_to_the_tab_in_use(self):
        """Two app tabs: the visible one (owner) gets the tool calls, a background tab does not."""
        relay = Relay()
        relay.last_poll = time.time()
        relay.poll(0.01, client="visible", active=True)       # the tab in use
        got = {}

        def background():
            got["background"] = relay.poll(0.6, client="hidden", active=False)

        def visible():
            time.sleep(0.2)
            cmd = relay.poll(3, client="visible", active=True)
            got["visible"] = cmd
            relay.resolve(cmd["id"], {"text": "from the visible tab"})

        threading.Thread(target=background, daemon=True).start()
        threading.Thread(target=visible, daemon=True).start()
        self.assertEqual(relay.call("get_part", timeout=5), {"text": "from the visible tab"})
        time.sleep(0.7)
        self.assertIsNone(got["background"])
        # the owner went quiet: any tab may take commands
        relay.owner_seen -= 60
        self.assertTrue(relay._may_take("hidden"))

    def test_timeout(self):
        relay = Relay()
        relay.last_poll = time.time()
        with self.assertRaises(TimeoutError):
            relay.call("get_part", timeout=0.2)


class TestTranslate(unittest.TestCase):
    def test_stream_json_events(self):
        self.assertEqual(translate({"type": "system", "subtype": "init", "model": "claude-x", "mcp_servers": [{"name": "auto3d", "status": "connected"}]}),
                         [{"type": "ready", "model": "claude-x", "mcp": "connected"}])
        self.assertEqual(translate({"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hi"}}}),
                         [{"type": "delta", "text": "Hi"}])
        self.assertEqual(translate({"type": "assistant", "message": {"content": [
            {"type": "text", "text": "Ok"}, {"type": "tool_use", "name": "mcp__auto3d__add_object", "input": {"kind": "box"}}]}}),
            [{"type": "text", "text": "Ok"}, {"type": "tool", "name": "add_object", "input": {"kind": "box"}}])
        self.assertEqual(translate({"type": "user", "message": {"content": [{"type": "tool_result", "is_error": True, "content": [{"type": "text", "text": "bad"}]}]}}),
                         [{"type": "tool_result", "error": True, "text": "bad"}])
        done = translate({"type": "result", "is_error": False, "result": "x", "total_cost_usd": 0.01, "duration_ms": 5})[0]
        self.assertEqual((done["type"], done["error"], done["text"]), ("done", False, None))
        self.assertEqual(translate({"type": "something_else"}), [])


class TestServerTools(unittest.TestCase):
    def test_trace_picture_and_no_browser(self):
        import server
        c = server.app.test_client()
        r = c.post("/api/agent/call", json={"tool": "trace_picture", "args": {"path": str(ROOT / "pernicek.png"), "count": 3}}).get_json()
        self.assertFalse(r["isError"], r)
        self.assertIn("1. confidence", r["content"][0]["text"])
        self.assertEqual(r["content"][1]["type"], "image")
        base64.b64decode(r["content"][1]["data"])  # a valid PNG payload
        # the page is not open: tools that act on the part say so
        server.RELAY.last_poll = 0
        r = c.post("/api/agent/call", json={"tool": "use_outline", "args": {"candidate": 1, "width": 100}}).get_json()
        self.assertTrue(r["isError"])
        self.assertIn("not open in a browser", r["content"][0]["text"])
        r = c.post("/api/agent/call", json={"tool": "bogus", "args": {}}).get_json()
        self.assertTrue(r["isError"])
        r = c.post("/api/agent/call", json={"tool": "open_file", "args": {"path": str(ROOT / "nope.stl")}}).get_json()
        self.assertIn("No such file", r["content"][0]["text"])

    def test_find_claude(self):
        exe = find_claude()
        if exe is None:
            self.skipTest("Claude Code is not installed here")
        self.assertTrue(Path(exe).exists())


class TestChatPhotos(unittest.TestCase):
    PNG = "data:image/png;base64," + base64.b64encode(
        bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                      "1f15c4890000000d49444154789c6300010000050001")).decode()

    def test_photo_reaches_claude_as_image_and_path(self):
        from auto3d.agent import ChatSession

        class Proc:  # a running claude process that records what it is sent
            def __init__(self):
                self.lines = []
                self.stdin = self

            def poll(self):
                return None

            def write(self, b):
                self.lines.append(json.loads(b.decode("utf-8")))

            def flush(self):
                pass

        s = ChatSession("http://127.0.0.1:1")
        s.proc = Proc()
        events = s.subscribe()
        s.send("make a cutter from this", [{"name": "star.png", "media_type": "image/png", "data": "QUJD",
                                            "path": "C:\\x\\star.png", "url": "/api/chat/photo/star.png"}])
        content = s.proc.lines[0]["message"]["content"]
        self.assertEqual(content[0], {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "QUJD"}})
        self.assertEqual(content[1]["type"], "text")
        self.assertIn("make a cutter from this", content[1]["text"])
        self.assertIn("[Attached photo: C:\\x\\star.png]", content[1]["text"])
        ev = events.get(timeout=1)
        while ev.get("type") != "user":
            ev = events.get(timeout=1)
        self.assertEqual(ev["photos"], [{"name": "star.png", "url": "/api/chat/photo/star.png"}])

    def test_server_saves_and_validates_photos(self):
        import server
        sent = []

        class Stub:
            def send(self, text, photos):
                sent.append((text, photos))

        orig = server._chat
        server._chat = lambda: Stub()
        try:
            c = server.app.test_client()
            r = c.post("/api/chat/send", json={"text": "", "photos": [{"name": "my star.png", "data": self.PNG}]})
            self.assertEqual(r.get_json(), {"ok": True})
            text, photos = sent[0]
            self.assertEqual(text, "")
            p = photos[0]
            self.assertEqual((p["name"], p["media_type"]), ("my star.png", "image/png"))
            self.assertTrue(Path(p["path"]).exists() and p["path"].endswith("-my_star.png"))
            got = c.get(p["url"])
            self.assertEqual(got.data, base64.b64decode(self.PNG.split(",")[1]))  # the chat shows it
            got.close()
            Path(p["path"]).unlink()
            r = c.post("/api/chat/send", json={"text": "hi", "photos": [{"name": "a.txt", "data": "data:text/plain;base64,QQ=="}]})
            self.assertEqual(r.status_code, 400)
            self.assertIn("not a photo", r.get_json()["error"])
            self.assertEqual(c.post("/api/chat/send", json={"text": " ", "photos": []}).status_code, 400)
        finally:
            server._chat = orig


if __name__ == "__main__":
    unittest.main()
