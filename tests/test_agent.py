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
        self.assertEqual(names, [t["name"] for t in TOOLS if not t.get("hidden")])  # (the server's own ones are not offered)
        self.assertTrue(all("inputSchema" in t and "where" not in t for t in resps[2]["result"]["tools"]))
        self.assertEqual(resps[3]["result"]["content"][0]["text"], 'ran add_object {"kind": "cylinder", "x": 5}')
        self.assertEqual(resps[4]["result"], {})
        self.assertEqual(resps[5]["error"]["code"], -32601)
        self.assertEqual(StubApp.calls[-1], {"tool": "add_object", "args": {"kind": "cylinder", "x": 5}, "listed": True})

    def test_the_chat_window_goes_with_each_call(self):
        """--client (a window's chat): every tool call names that window, so the app sends it there only."""
        srv = HTTPServer(("127.0.0.1", 0), StubApp)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{srv.server_address[1]}"
        p = subprocess.Popen([sys.executable, str(MCP), "--url", url, "--client", "win-A"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "get_part", "arguments": {}}}
        p.communicate((json.dumps(msg) + "\n").encode(), timeout=30)
        srv.shutdown()
        self.assertEqual(StubApp.calls[-1], {"tool": "get_part", "args": {}, "listed": True, "client": "win-A"})
        from auto3d.agent import ChatSession
        cmd = ChatSession("http://127.0.0.1:1", "win-A").command("claude")
        args = json.loads(cmd[cmd.index("--mcp-config") + 1])["mcpServers"]["auto3d"]["args"]
        self.assertEqual(args[args.index("--client") + 1], "win-A")
        cmd = ChatSession("http://127.0.0.1:1").command("claude")  # (no window: no --client)
        self.assertNotIn("--client", json.loads(cmd[cmd.index("--mcp-config") + 1])["mcpServers"]["auto3d"]["args"])

    def test_older_app_server(self):
        """A tool the MCP server lists but the app server (started before a merge) does not know: the AI is told to
        have the app restarted, not only "Unknown tool" — said by the app server, and by the MCP server for an old one."""
        from auto3d import mcp_server

        class Old(StubApp):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                out = json.dumps({"content": [{"type": "text", "text": f"Unknown tool {body['tool']}."}], "isError": True}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)
        srv = HTTPServer(("127.0.0.1", 0), Old)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{srv.server_address[1]}"
        try:
            r = mcp_server.call_app(url, "add_harness", {})
            self.assertTrue(r["isError"])
            self.assertIn("this app server is older than the tool list", r["content"][0]["text"])
            self.assertIn("restart the app", r["content"][0]["text"])
            self.assertEqual(mcp_server.call_app(url, "no_such_tool", {})["content"][0]["text"], "Unknown tool no_such_tool.")
        finally:
            srv.shutdown()
        import server
        c = server.app.test_client()
        r = c.post("/api/agent/call", json={"tool": "brand_new_tool", "args": {}, "listed": True}).get_json()
        self.assertTrue(r["isError"])
        self.assertIn("this app server is older than the tool list", r["content"][0]["text"])
        r = c.post("/api/agent/call", json={"tool": "brand_new_tool", "args": {}}).get_json()
        self.assertEqual(r["content"][0]["text"], "Unknown tool brand_new_tool.")

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
        self.assertEqual(sorted(x["name"] for x in r[3]["result"]["prompts"]), ["assemble-parts", "automation-design", "bug-hunter", "change-a-model", "design-principles", "design-review", "easy-assembly", "fits-and-tolerances", "from-picture", "ict-fixture", "machined-part", "materials-and-strength", "mechanical-design", "model-a-part", "print-functional", "print-graphics", "print-prep", "production-drawing", "standard-parts", "start-a-design", "suggest-features", "teach-me", "use-a-drawing"])
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
        for name in ("start-a-design", "model-a-part", "from-picture", "print-prep", "change-a-model", "assemble-parts", "mechanical-design", "automation-design",
                     "fits-and-tolerances", "print-functional", "print-graphics", "use-a-drawing", "teach-me", "bug-hunter", "suggest-features",
                     "design-principles", "standard-parts", "machined-part", "materials-and-strength", "ict-fixture", "design-review",
                     "production-drawing"):
            text = (PLUGIN_DIR / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\nname: " + name), name)
        # every tool a skill tells the AI to use exists
        import re
        names = {t["name"] for t in TOOLS}
        for f in (PLUGIN_DIR / "skills").glob("*/SKILL.md"):
            for used in set(re.findall(r"`([a-z_]+) \{", f.read_text(encoding="utf-8"))):
                self.assertIn(used, names, f"{f.parent.name} uses {used}")

    def test_design_skills_are_routed(self):
        """The engineering skills (design intent, few bought kinds, machining, materials, fixtures, review, drawings) are
        loaded from start-a-design and the system prompt; each stays tight (≤ 150 lines) with a 'Use when' description."""
        from auto3d.agent_tools import SYSTEM_PROMPT
        from auto3d.guides import guides
        g = guides()
        new = ("design-principles", "standard-parts", "machined-part", "materials-and-strength", "ict-fixture", "design-review",
               "production-drawing", "easy-assembly", "teach-me", "bug-hunter")
        for name in new:
            self.assertIn(name, SYSTEM_PROMPT, name)
            self.assertLessEqual(len(g[name]["text"].splitlines()), 150, name)
            self.assertTrue(g[name]["description"].startswith("Use "), name)
        for name in new[:8]:
            self.assertIn(name, g["start-a-design"]["text"], name)
        self.assertIn("library_pair", g["ict-fixture"]["text"])
        self.assertIn("axis_distance", g["ict-fixture"]["text"])
        self.assertIn("get_bom", g["standard-parts"]["text"])
        self.assertIn("ask_user", g["design-review"]["text"])
        self.assertIn("easy-assembly", g["design-review"]["text"])
        self.assertIn("easy-assembly", g["assemble-parts"]["text"])
        self.assertIn("check_travel", g["easy-assembly"]["text"])
        self.assertIn("complete: true", g["production-drawing"]["text"])
        self.assertIn("δ = F · L³ / (3 · E · I)", g["materials-and-strength"]["text"])
        self.assertNotIn("ui-tester", " ".join(g))  # merged into bug-hunter, teach-the-user into teach-me

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
            from auto3d import version
            self.assertIn(f"- **App version:** {version.text()}", text)  # the build it came from, written by the server
            self.assertIn("- **Kind:** bug", text)
            server.tool_report_problem({"title": "A tool to drive a mechanism", "what": "no tool turns a crank", "kind": "tool request"})
            req = [f for f in (Path(tmp) / "RealSWReports").glob("*request-a-tool-to-drive*.md")]
            self.assertEqual(len(req), 1)
            self.assertIn("- **Kind:** tool request", req[0].read_text(encoding="utf-8"))
            self.assertTrue(version.text().startswith(version.VERSION))
            self.assertIn("RealSWReports/", r["text"])
            with self.assertRaises(ValueError):
                server.tool_report_problem({"title": "", "what": "x"})

    def test_report_problem_once(self):
        """A report whose title says the same as an earlier one is not written again: the AI gets the earlier one;
        again: true writes it anyway. list_reports lists them (a kind, words of a title)."""
        import tempfile
        from unittest import mock
        import server
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(server, "REPORTS", Path(tmp) / "RealSWReports"), mock.patch.object(server, "ROOT", Path(tmp)):
            self.assertEqual(server.tool_list_reports({})["text"], "No reports yet.")
            server.tool_report_problem({"title": "Paint does not show in the assembly", "what": "the face stayed grey"})
            server.tool_report_problem({"title": "A tool to drive a mechanism", "what": "no tool turns a crank", "kind": "tool request"})
            r = server.tool_report_problem({"title": "Painted faces are not shown in an assembly", "what": "grey again"})
            self.assertIn("a similar report exists", r["text"])
            self.assertIn("“Paint does not show in the assembly” (bug", r["text"])
            self.assertEqual(len(list((Path(tmp) / "RealSWReports").glob("*.md"))), 2)  # not written
            time.sleep(1.1)  # (a report's file name has the second it was written)
            r = server.tool_report_problem({"title": "Painted faces are not shown in an assembly", "what": "in a sub-assembly", "again": True})
            self.assertIn("Reported:", r["text"])
            self.assertEqual(len(list((Path(tmp) / "RealSWReports").glob("*.md"))), 3)
            # another problem with a word in common is written
            self.assertIn("Reported:", server.tool_report_problem({"title": "Fillet fails on a hole's edge", "what": "x"})["text"])
            rows = json.loads(server.tool_list_reports({})["text"])
            self.assertEqual(len(rows), 4)
            self.assertEqual(set(rows[0]), {"title", "kind", "date"})
            self.assertEqual([x["title"] for x in json.loads(server.tool_list_reports({"kind": "tool request"})["text"])], ["A tool to drive a mechanism"])
            found = json.loads(server.tool_list_reports({"search": "painting in assemblies"})["text"])
            self.assertEqual({x["title"] for x in found}, {"Paint does not show in the assembly", "Painted faces are not shown in an assembly"})
            self.assertEqual(server.tool_list_reports({"search": "screenshot"})["text"], "No reports match.")

    def test_report_with_project(self):
        """A report carries the project on screen (<base>.a3d: the Save project file, compacted — an imported file over
        the limit left out with a note; the others binary, from the blob store) and a recent ⏺ recording
        (<base>.recording.json, no screenshots); the .md points to both, list_reports / reports.read say they are there."""
        import tempfile
        from unittest import mock
        import server
        from auto3d import package, project, reports
        from auto3d.modeler import blobs
        big, small = b"x" * 2000, b"solid"
        store = {"aa11": big, "bb22": small}
        proj = {"app": "Auto3DModeler", "version": 3, "project_name": "Bracket", "unit": "mm", "parameters": [], "active": {"part": "P1"},
                "parts": [{"id": "P1", "kind": "model", "name": "Plate", "model": {"features": [
                              {"id": "F1", "type": "sketch", "plane": "XY"}, {"id": "F2", "type": "extrude", "sketch": "F1", "d": 8},
                              {"id": "F3", "type": "solid", "blob": "aa11", "file": "motor.step"}, {"id": "F4", "type": "solid", "blob": "bb22", "file": "pin.stl"}]}},
                          {"id": "P2", "kind": "assembly", "name": "Assembly 1", "assembly": {"instances": [{"id": "I1", "part": "P1"}], "joints": []}}],
                "assets": {}, "assemblies": [], "versions": [{"id": "v1"}]}
        rec = {"running": False, "started_by": "user", "seconds": 12, "count": 2, "events": [{"i": 0, "t": 0, "kind": "start"}, {"i": 1, "t": 12, "kind": "stop"}],
               "shots": [{"id": "1", "data": "AAAA"}]}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(server, "REPORTS", Path(tmp) / "R"), mock.patch.object(server, "ROOT", Path(tmp)), \
                mock.patch.object(reports, "KEEP_FILE", 1000), mock.patch.object(blobs, "get", lambda sha: store[sha]):
            r = server.tool_report_problem({"title": "Extrude goes the wrong way", "what": "x", "project": proj, "recording": rec})
            self.assertIn("with the project and the recording of moves", r["text"])
            md = next((Path(tmp) / "R").glob("*.md"))
            gz, js = md.with_name(md.stem + ".a3d"), md.with_name(md.stem + ".recording.json")
            self.assertTrue(gz.exists() and js.exists())
            pk = package.load(gz.read_bytes())
            got = pk["project"]
            self.assertEqual(project.migrate(got)["parts"][0]["model"]["features"], proj["parts"][0]["model"]["features"])  # (a valid project)
            self.assertEqual(got["parts"][1]["assembly"], proj["parts"][1]["assembly"])
            self.assertEqual(pk["blobs"], {"bb22": small})  # the big imported file left out, with a note; no version history
            self.assertEqual(got["left_out"], [{"what": "imported file", "blob": "aa11", "name": "motor.step", "bytes": 2000}])
            self.assertIsNone(pk["versions"])
            saved = json.loads(js.read_text(encoding="utf-8"))
            self.assertEqual(saved["events"], rec["events"])
            self.assertNotIn("shots", saved)
            text = md.read_text(encoding="utf-8")
            self.assertIn(f"- **Project:** `{gz.name}` (open it in the app: 📂 Open ▾ › File…) — 2 part(s): Plate, Assembly 1;", text)
            self.assertIn("imported files left out: motor.step (1 kB)", text)
            self.assertIn(f"- **Recording:** `{js.name}` (⏺ the user's moves: 2 events over 12 s, stopped; without screenshots)", text)
            row = json.loads(server.tool_list_reports({})["text"])[0]
            self.assertEqual((row["project"], row["recording"]), (gz.name, js.name))
            # the cap: the largest imported files go first until the file is small enough
            data, left = reports.compact_project(proj, store.get, keep_file=10 ** 9, cap=200)
            self.assertEqual([x["blob"] for x in left], ["aa11", "bb22"])
            self.assertEqual(package.load(data)["blobs"], {})
            # without a page (no project, no recording): only the .md, as before
            r = server.tool_report_problem({"title": "Something else entirely here", "what": "y"})
            self.assertNotIn("with the", r["text"])
            self.assertEqual(len(list((Path(tmp) / "R").glob("*.a3d"))), 1)

    def test_report_with_screenshots(self):
        """report_problem screenshots: the pictures saved next to the report (<base>.shot-1.png …, at most 1600 px
        across, under 1 MB — a large noisy one as WebP; at most 4), shown in the .md with their captions; "last" / an
        id: the AI's own get_screenshot; what cannot be attached is said; list_reports names them."""
        import tempfile
        from unittest import mock
        import cv2
        import numpy as np
        import server
        from auto3d import reports

        def png(w, h, noise=False):
            img = np.random.default_rng(1).integers(0, 255, (h, w, 3), np.uint8) if noise else np.full((h, w, 3), (40, 120, 200), np.uint8)
            return base64.b64encode(cv2.imencode(".png", img)[1].tobytes()).decode()

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(server, "REPORTS", Path(tmp) / "R"), mock.patch.object(server, "ROOT", Path(tmp)), \
                mock.patch.object(server, "SHOTS", {}):
            first, last = server._keep_shot(png(300, 200), ""), server._keep_shot(png(1200, 900), "")
            self.assertEqual(server.SHOTS[""][-1][0], last)
            r = server.tool_report_problem({"title": "The OK button is hidden", "what": "the ⋯ menu covers it", "kind": "ui", "project": None,
                                            "screenshots": ["last", {"shot": first, "caption": "before: the [OK] button"},
                                                            {"shot": "ui", "image": png(3200, 2000, noise=True), "caption": "the whole window"},
                                                            "s999", "garbage"]})
            self.assertIn("with 3 screenshots", r["text"])
            self.assertIn("Not attached: only 4 screenshots go with a report", r["text"])
            self.assertIn("s999: no such screenshot", r["text"])
            md = next((Path(tmp) / "R").glob("*.md"))
            files = [md.with_name(f"{md.stem}.shot-{i}{ext}") for i, ext in ((1, ".png"), (2, ".png"), (3, ".webp"))]
            self.assertTrue(all(f.exists() for f in files), [f.name for f in (Path(tmp) / "R").iterdir()])
            sizes = [cv2.imdecode(np.frombuffer(f.read_bytes(), np.uint8), cv2.IMREAD_COLOR).shape[:2] for f in files]
            self.assertEqual(sizes[:2], [(900, 1200), (200, 300)])
            self.assertLessEqual(max(sizes[2]), 1600)  # (the 3200 px window scaled down, a WebP under 1 MB)
            self.assertTrue(all(f.stat().st_size <= reports.SHOT_BYTES for f in files))
            text = md.read_text(encoding="utf-8")
            self.assertIn(f"- **Screenshots:** 3 (below): `{files[0].name}`, `{files[1].name}`, `{files[2].name}`", text)
            self.assertIn(f"![the AI's screenshot {last}]({files[0].name})", text)
            self.assertIn(f"![before: the OK button]({files[1].name})\n*2. before: the OK button*", text)  # (no brackets in a caption)
            self.assertIn(f"## Screenshots\n\n![", text)
            row = json.loads(server.tool_list_reports({})["text"])[0]
            self.assertEqual(row["screenshots"], [f.name for f in files])
            self.assertEqual(reports.read(Path(tmp) / "R")[0]["shots"], [f.name for f in files])
            # "ui" / "view" with no page open, "last" with none taken: written without them, said why
            server.SHOTS.clear()
            r = server.tool_report_problem({"title": "Something else entirely here", "what": "y", "project": None, "screenshots": ["view", "last"]})
            self.assertNotIn("with", r["text"].split(" — thank you")[0])
            self.assertIn("view: The app is not open in a browser", r["text"])
            self.assertIn("last: you have taken no get_screenshot yet", r["text"])
            self.assertEqual(len(list((Path(tmp) / "R").glob("*.shot-*"))), 3)

    def test_report_titles_alike(self):
        from auto3d.reports import similarity, SIMILAR
        same = [("Paint does not show in the assembly", "Painted faces are not shown in an assembly"),
                ("edit_feature on a mirror resets its plane", "edit_feature on a mirror resets the plane"),
                ("No tool to read a sketch", "A tool to read a sketch")]
        other = [("edit_feature on a mirror resets its plane", "edit_feature on a sketch's plane drops its shapes"),
                 ("Paint does not show in the assembly", "Fillet fails on a hole edge"),
                 ("Concentric joint on a library screw: no free motions", "Joint panel: free-turn slider greyed out on locked joints"),
                 ("", "anything")]
        for a, b in same:
            self.assertGreaterEqual(similarity(a, b), SIMILAR, (a, b))
        for a, b in other:
            self.assertLess(similarity(a, b), SIMILAR, (a, b))

    def test_slash_commands(self):
        """/uiTester (/bugHunter), /teachMe and /suggest in the chat: Claude gets the instruction to load its skill (any case,
        words after it kept)."""
        from auto3d.agent import COMMANDS, ChatSession, expand_command
        from auto3d.guides import guides
        for name, (skill, _) in COMMANDS.items():
            self.assertIn(skill, guides(), name)
        self.assertIn("auto3d:bug-hunter", expand_command("/uiTester"))
        self.assertIn("auto3d:bug-hunter", expand_command("  /UITESTER  "))
        self.assertIn("auto3d:bug-hunter", expand_command("/bugHunter"))
        self.assertIn("auto3d:teach-me", expand_command("/teachMe"))
        r = expand_command("/ui-tester only the drawing sheet")
        self.assertIn("auto3d:bug-hunter", r)
        self.assertTrue(r.endswith("The user adds: only the drawing sheet"))
        self.assertIn("auto3d:suggest-features", expand_command("/suggest"))
        for plain in ("make a /uiTester", "/unknown thing", "hello", "/uitesterx"):
            self.assertEqual(expand_command(plain), plain)
        # the chat shows what the user typed; Claude gets the instruction
        chat = ChatSession("http://127.0.0.1:1")
        sent = []
        chat.proc = type("P", (), {"poll": lambda self: None, "stdin": type("S", (), {"write": lambda self, b: sent.append(b), "flush": lambda self: None})()})()
        chat.send("/uiTester")
        self.assertEqual(chat.history[-1]["text"], "/uiTester")
        self.assertIn("auto3d:bug-hunter", json.loads(sent[0])["message"]["content"][-1]["text"])

    def test_version_route(self):
        import server
        from auto3d import version
        r = server.app.test_client().get("/api/version").get_json()
        self.assertEqual(r["version"], version.VERSION)
        self.assertEqual(r["text"], version.text())
        self.assertEqual(r["stale"], bool(version.stale()))
        from unittest import mock
        with mock.patch.object(version, "head", return_value="fa4e000"), mock.patch.object(version, "build", return_value={
                "version": version.VERSION, "commit": "92d0e37", "date": "2026-10-27", "branch": "main", "dirty": False}):
            r = server.app.test_client().get("/api/version").get_json()  # (the checkout moved on since the server started)
            self.assertTrue(r["stale"])
            self.assertEqual(r["head"], "fa4e000")
            self.assertIn("checkout now at fa4e000 — restart the app", r["text"])

    def test_report_says_the_page_build(self):
        """A report written while a page loaded at another commit polls: its version line says that page's commit."""
        import tempfile
        from unittest import mock
        import server
        from auto3d import version
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(server, "REPORTS", Path(tmp) / "R"), mock.patch.object(server, "ROOT", Path(tmp)),                 mock.patch.dict(server.PAGE_BUILDS, {"win-B": "0aa1111"}), mock.patch.object(version, "build", return_value={
                    "version": version.VERSION, "commit": "92d0e37", "date": "2026-10-27", "branch": "main", "dirty": False}),                 mock.patch.object(version, "head", return_value="92d0e37"):
            from auto3d.agent import ROUTE
            route = ROUTE.set("win-B")
            try:
                server.tool_report_problem({"title": "Stale page", "what": "x"})
            finally:
                ROUTE.reset(route)
            text = next((Path(tmp) / "R").glob("*.md")).read_text(encoding="utf-8")
            self.assertIn("(main @ 92d0e37, 2026-10-27; page loaded at 0aa1111 — reload it)", text)

    def test_tool_schemas(self):
        for t in mcp_tool_list():
            self.assertEqual(t["inputSchema"]["type"], "object", t["name"])
            self.assertTrue(t["description"])
        self.assertIn("get_part", BROWSER_TOOLS)
        for name in ("set_look", "paint_faces", "move_free", "set_travel", "check_travel", "lock_motion", "fix_together", "gui_state", "gui_action", "gui_highlight", "ask_user", "sheet_open", "get_sheet", "sheet_edit", "save_to_library", "library_search", "library_add", "library_pair", "check_collisions",
                     "get_sketch", "sketch_auto_dims", "sketch_dim", "sketch_trim", "sketch_union"):
            self.assertIn(name, BROWSER_TOOLS)
        self.assertNotIn("report_problem", BROWSER_TOOLS)  # the server writes it
        self.assertNotIn("list_reports", BROWSER_TOOLS)    # and reads them
        hl = next(t for t in TOOLS if t["name"] == "gui_highlight")["inputSchema"]["properties"]
        self.assertTrue({"control", "at", "text", "step", "wait", "timeout", "clear"} <= set(hl))
        self.assertIn("again", next(t for t in TOOLS if t["name"] == "report_problem")["inputSchema"]["properties"])
        from auto3d.guides import guides
        topics = next(t for t in TOOLS if t["name"] == "get_guide")["inputSchema"]["properties"]["topic"]["enum"]
        self.assertEqual(sorted(topics), sorted(guides()))  # every skill is a guide topic
        from auto3d.agent_tools import SYSTEM_PROMPT
        for words in ("gui_highlight", "auto3d:teach-me", "/uiTester", "/bugHunter", "auto3d:bug-hunter", "auto3d:suggest-features", "list_reports",
                      "auto3d:design-review"):
            self.assertIn(words, SYSTEM_PROMPT)
        self.assertNotIn("trace_picture", BROWSER_TOOLS)

    def test_the_ai_sees_the_suggestions_table(self):
        """The app is worked through its suggestions table: gui_state returns it (where: suggest = only it), gui_action
        picks a named face / part and runs a row by its label, get_screenshot {ui: true} draws it; the prompt and the
        skills teach the suggestion-first way (the page's side: tools/e2e_ai_suggest.py)."""
        from auto3d.agent_tools import SYSTEM_PROMPT
        from auto3d.guides import guides
        schema = {t["name"]: t["inputSchema"]["properties"] for t in TOOLS}
        self.assertIn("suggest", schema["gui_state"]["where"]["enum"])
        self.assertEqual(schema["gui_action"]["suggest"], {"type": "string"})
        self.assertEqual(schema["gui_action"]["pick"], {"type": "string"})
        self.assertEqual(schema["get_screenshot"]["ui"], {"type": "boolean"})
        desc = {t["name"]: t["description"] for t in TOOLS}
        self.assertIn("suggestions", desc["gui_state"])
        self.assertIn("Show all", desc["gui_action"])
        self.assertIn("suggestions table", SYSTEM_PROMPT)
        self.assertIn('gui_action {suggest:', SYSTEM_PROMPT)
        g = {k: v["text"] for k, v in guides().items()}
        for topic in ("bug-hunter", "teach-me", "model-a-part", "assemble-parts"):
            self.assertIn("suggest", g[topic], topic)
        self.assertIn("gui_state {where: \"suggest\"}", g["bug-hunter"])
        self.assertIn("rank_pos", g["bug-hunter"])

    def test_gui_action_aims_through_the_picture_and_holds_keys(self):
        """gui_action / gui_highlight `at` are pixels of get_screenshot's picture (the AI reads them off it; the page
        aims them through the picture's camera), and a click can hold keys — mods ["ctrl"]: the user's Ctrl+click
        (the page's side: tools/e2e_ai_gui.py)."""
        schema = {t["name"]: t["inputSchema"]["properties"] for t in TOOLS}
        desc = {t["name"]: t["description"] for t in TOOLS}
        self.assertEqual(schema["gui_action"]["mods"]["items"]["enum"], ["ctrl", "shift", "alt", "meta"])
        self.assertIn("Ctrl+click", desc["gui_action"])
        self.assertIn("last get_screenshot picture", desc["gui_action"])
        self.assertIn("camera that drew it", desc["get_screenshot"])
        self.assertIn("last get_screenshot picture", desc["gui_highlight"])


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

    def test_a_windows_chat_acts_in_that_window_only(self):
        """Two windows, B the one in use: a call of A's chat goes to A — B, polling all the while, gets nothing."""
        relay = Relay()
        relay.poll(0.01, client="A", active=False)   # A: in the background
        relay.poll(0.01, client="B", active=True)    # B: the window in use (the owner)
        got = {}

        def window(name, wait):
            cmd = relay.poll(wait, client=name, active=name == "B")
            got[name] = cmd
            if cmd:
                relay.resolve(cmd["id"], {"text": f"done in {name}"})

        tb = threading.Thread(target=window, args=("B", 1.5), daemon=True)
        tb.start()
        time.sleep(0.1)  # (B is waiting first: it would take anything it may)
        threading.Thread(target=window, args=("A", 3), daemon=True).start()
        self.assertEqual(relay.call("get_part", timeout=5, client="A"), {"text": "done in A"})
        tb.join(3)
        self.assertIsNone(got["B"])
        self.assertEqual(got["A"]["cmd"], "get_part")
        # the same through ROUTE (set by the server for a chat's MCP call): also a server tool's calls go there
        from auto3d.agent import ROUTE
        threading.Thread(target=window, args=("A", 3), daemon=True).start()
        token = ROUTE.set("A")
        try:
            self.assertEqual(relay.call("load", {"n": 1}, timeout=5), {"text": "done in A"})
        finally:
            ROUTE.reset(token)

    def test_the_windows_chat_after_it_closed(self):
        """A window closed (its goodbye, not back): its chat's call fails with a clear message, the other window
        gets nothing; a reload (back within the grace) still works; a window never seen fails at once."""
        from auto3d.agent import GONE_TEXT
        relay = Relay(grace=0.3)
        relay.poll(0.01, client="A")
        relay.poll(0.01, client="B")
        relay.bye("A")
        got = {}
        threading.Thread(target=lambda: got.setdefault("B", relay.poll(1.2, client="B")), daemon=True).start()
        time.sleep(0.4)
        t0 = time.time()
        with self.assertRaises(RuntimeError) as e:
            relay.call("get_part", timeout=5, client="A")
        self.assertEqual(str(e.exception), GONE_TEXT)
        self.assertIn("closed", GONE_TEXT)
        self.assertLess(time.time() - t0, 0.5)
        time.sleep(1)
        self.assertIsNone(got["B"])
        self.assertFalse(relay.outbox)  # (nothing left queued for another window)
        # a call waiting while its window closes: it fails, it does not wait the whole timeout
        def close_soon():
            time.sleep(0.2)
            relay.bye("B")
        threading.Thread(target=close_soon, daemon=True).start()
        t0 = time.time()
        with self.assertRaises(RuntimeError):
            relay.call("get_part", timeout=10, client="B")
        self.assertLess(time.time() - t0, 3)
        # a reload: goodbye, then a poll again at once — the call is taken by the window back
        relay.poll(0.01, client="C")
        relay.bye("C")
        threading.Thread(target=lambda: (lambda c: relay.resolve(c["id"], {"text": "reloaded"}))(relay.poll(3, client="C")), daemon=True).start()
        self.assertEqual(relay.call("get_part", timeout=5, client="C"), {"text": "reloaded"})
        with self.assertRaises(RuntimeError):
            relay.call("get_part", timeout=5, client="never-opened")

    def test_a_window_gone_without_a_goodbye(self):
        """The browser killed (no goodbye): its last poll still took the call. While it says it is there (alive) the
        call waits; silent for gone_after: the call fails — it is not handed to another window."""
        relay = Relay(gone_after=0.6)
        relay.poll(0.01, client="A")
        relay.poll(0.01, client="B")

        def a_runs_long():
            cmd = relay.poll(2, client="A")
            for _ in range(5):          # 1 s of work, saying it is there
                time.sleep(0.2)
                relay.alive("A")
            relay.resolve(cmd["id"], {"text": "long one done"})

        threading.Thread(target=a_runs_long, daemon=True).start()
        self.assertEqual(relay.call("get_part", timeout=5, client="A"), {"text": "long one done"})
        threading.Thread(target=lambda: relay.poll(2, client="A"), daemon=True).start()  # takes it, then is gone
        got = {}
        threading.Thread(target=lambda: got.setdefault("B", relay.poll(2.5, client="B")), daemon=True).start()
        t0 = time.time()
        with self.assertRaises(RuntimeError):
            relay.call("get_part", timeout=10, client="A")
        self.assertLess(time.time() - t0, 3)
        time.sleep(2.6 - (time.time() - t0) if time.time() - t0 < 2.6 else 0)
        self.assertIsNone(got.get("B"))

    def test_poll_ends_when_the_page_hangs_up(self):
        """A page gone (reload: its request closed) stops waiting at once and takes no call — the next page gets it."""
        relay = Relay()
        gone = threading.Event()
        threading.Timer(0.3, gone.set).start()
        t0 = time.time()
        self.assertIsNone(relay.poll(10, client="A", hung_up=gone.is_set))
        self.assertLess(time.time() - t0, 2.5)
        relay.outbox["x"] = {"id": "x", "cmd": "get_part", "args": {}, "to": None, "taken": None}
        relay.order.append("x")
        self.assertIsNone(relay.poll(10, client="A", hung_up=lambda: True))  # (hung up: not taken)
        self.assertEqual(relay.poll(1, client="A")["id"], "x")

    def test_hung_up_reads_the_socket(self):
        import socket
        import server
        a, b = socket.socketpair()
        try:
            self.assertFalse(server._hung_up({"werkzeug.socket": a}))  # open, nothing sent
            b.sendall(b"GET")
            self.assertFalse(server._hung_up({"werkzeug.socket": a}))  # data waiting is not a hang-up
            a.recv(3)
            b.close()
            self.assertTrue(server._hung_up({"werkzeug.socket": a}))   # the page closed it
        finally:
            a.close()
        self.assertFalse(server._hung_up({}))                          # no socket (the test client): never

    def test_server_routes_a_chats_call_and_keeps_a_chat_per_window(self):
        import server
        orig = server.RELAY
        server.RELAY = Relay(grace=0.1)
        try:
            server.RELAY.poll(0.01, client="W1")
            server.RELAY.bye("W1")
            time.sleep(0.2)
            c = server.app.test_client()
            r = c.post("/api/agent/call", json={"tool": "get_part", "args": {}, "client": "W1"}).get_json()
            self.assertTrue(r["isError"])
            self.assertIn("window this chat belongs to was closed", r["content"][0]["text"])
            self.assertEqual(c.post("/api/agent/bye?client=W2").get_json(), {"ok": True})
            self.assertIn("W2", server.RELAY.left)
        finally:
            server.RELAY = orig
        a, b = server._chat("wa"), server._chat("wb")
        self.assertIsNot(a, b)
        self.assertIs(server._chat("wa"), a)
        self.assertEqual((a.client, server._chat("").client), ("wa", None))
        for k in ("wa", "wb"):
            server.CHATS.pop(k, None)


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
            def send(self, text, photos, files=None):
                sent.append((text, photos))

        orig = server._chat
        server._chat = lambda client="": Stub()
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
