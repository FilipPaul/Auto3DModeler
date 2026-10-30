"""The desktop start (auto3d/launcher.py, the built Auto3DModeler.exe): the data folder (A3D_DATA, else
%LOCALAPPDATA%\\Auto3DModeler when built, else the checkout's data/), the port (--port / A3D_PORT, 5173 when free, else
any), one copy per data folder (instance.json + a probe of /api/version; the mutex), the Edge app window's command,
the log kept small, and the AI chat's MCP server through the exe itself when built."""
import json
import os
import socket
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

from auto3d import launcher as L


class Fake(BaseHTTPRequestHandler):
    """Answers /api/version like the app does."""

    def do_GET(self):
        body = json.dumps({"version": "9.9"}).encode()
        self.send_response(200 if self.path == "/api/version" else 404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class TestWhere(unittest.TestCase):
    def test_data_dir(self):
        """A3D_DATA wins; the built app: %LOCALAPPDATA%\\Auto3DModeler (never the install folder); a checkout: data/."""
        self.assertEqual(L.data_dir({"A3D_DATA": "X:/mine", "LOCALAPPDATA": "C:/L"}, True), Path("X:/mine"))
        self.assertEqual(L.data_dir({"LOCALAPPDATA": "C:/Users/u/AppData/Local"}, True),
                         Path("C:/Users/u/AppData/Local/Auto3DModeler"))
        self.assertEqual(L.data_dir({}, True).parts[-3:], ("AppData", "Local", "Auto3DModeler"))
        self.assertEqual(L.data_dir({}, False), L.ROOT / "data")

    def test_port(self):
        """--port, then A3D_PORT, as given; else 5173 when free; taken -> one the system hands out."""
        self.assertEqual(L.pick_port(5194, {"A3D_PORT": "5000"}), 5194)
        self.assertEqual(L.pick_port(None, {"A3D_PORT": "5000"}), 5000)
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            s.listen()
            taken = s.getsockname()[1]
            self.assertFalse(L.port_free(taken))
            other = L.pick_port(None, {}, preferred=taken)
            self.assertNotEqual(other, taken)
            self.assertTrue(L.port_free(other))
        free = L.pick_port(None, {}, preferred=other)
        self.assertEqual(free, other)


class TestOneCopy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_running_url(self):
        """instance.json alone is not enough: the url must answer as our app (a crash leaves the file behind)."""
        self.assertIsNone(L.running_url(self.data))  # no file
        httpd = HTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            url = f"http://127.0.0.1:{httpd.server_address[1]}"
            L.write_instance(self.data, url)
            self.assertEqual(json.loads(L.instance_file(self.data).read_text())["pid"], os.getpid())
            self.assertEqual(L.running_url(self.data), url)
        finally:
            httpd.shutdown()
            httpd.server_close()
        self.assertIsNone(L.running_url(self.data))  # left behind: nobody answers
        L.instance_file(self.data).write_text("not json")
        self.assertIsNone(L.running_url(self.data))

    def test_clear_only_own(self):
        L.instance_file(self.data).write_text(json.dumps({"url": "http://x", "pid": os.getpid() + 1}))
        L.clear_instance(self.data)
        self.assertTrue(L.instance_file(self.data).exists())  # another process's
        L.write_instance(self.data, "http://x")
        L.clear_instance(self.data)
        self.assertFalse(L.instance_file(self.data).exists())

    @unittest.skipUnless(os.name == "nt", "a Windows mutex")
    def test_lock(self):
        """The first copy on a data folder gets the lock, a second one does not; another data folder is separate."""
        import ctypes
        h1, first = L.take_lock(self.data)
        h2, second = L.take_lock(self.data)
        with tempfile.TemporaryDirectory() as other:
            h3, third = L.take_lock(Path(other))
        self.assertEqual((first, second, third), (True, False, True))
        for h in (h1, h2, h3):
            ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(h))

    def test_second_start_opens_the_window(self):
        """A second start finds the running copy and only opens its window: no server, exit code 0."""
        with mock.patch.dict(os.environ, {"A3D_DATA": str(self.data)}), \
                mock.patch.object(L, "take_lock", return_value=(None, False)), \
                mock.patch.object(L, "wait_for_running", return_value="http://127.0.0.1:1"), \
                mock.patch.object(L, "open_window") as opened, mock.patch.object(L, "App") as app, \
                mock.patch.object(L, "frozen", return_value=False):
            self.assertEqual(L.main([]), 0)
        opened.assert_called_once_with("http://127.0.0.1:1", self.data, False)
        app.assert_not_called()

    def test_stale_instance_file_with_the_lock(self):
        """The first copy (it holds the folder's mutex) starts its own server even when an old instance.json names a
        port some other program answers on — that was a smoke test's leftover pointing at another server."""
        with mock.patch.dict(os.environ, {"A3D_DATA": str(self.data)}), \
                mock.patch.object(L, "take_lock", return_value=(1, True)), \
                mock.patch.object(L, "running_url", return_value="http://127.0.0.1:1") as asked, \
                mock.patch.object(L, "open_window") as opened, mock.patch.object(L, "App") as app, \
                mock.patch.object(L, "frozen", return_value=False):
            app.return_value.wait.return_value = 0
            L.main(["--no-browser"])
        asked.assert_not_called()
        opened.assert_not_called()
        app.assert_called_once()


class TestWindowAndLogs(unittest.TestCase):
    def test_window_command(self):
        """Edge as an app window with its own profile in the data folder."""
        cmd = L.window_command("msedge.exe", "http://127.0.0.1:5173", Path("D:/data"))
        self.assertEqual(cmd[:2], ["msedge.exe", "--app=http://127.0.0.1:5173"])
        self.assertIn(f"--user-data-dir={Path('D:/data') / 'window'}", cmd)
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
            exe.parent.mkdir(parents=True)
            exe.write_bytes(b"")
            self.assertEqual(L.find_edge({"ProgramFiles(x86)": tmp}), str(exe))
            self.assertIsNone(L.find_edge({"ProgramFiles(x86)": str(Path(tmp) / "none")}))

    def test_czech_words(self):
        """The tray and the message box speak Czech on a Czech Windows."""
        with mock.patch.object(L, "czech", return_value=True):
            self.assertEqual(L.say("Quit"), "Ukončit")
            self.assertIn("nepodařilo", L.say("{app} could not start.\n\nThe details are in {log}.").format(app="A", log="x"))
        with mock.patch.object(L, "czech", return_value=False):
            self.assertEqual(L.say("Quit"), "Quit")

    def test_browser_without_edge(self):
        with mock.patch.object(L, "find_edge", return_value=None), mock.patch.object(L.webbrowser, "open") as wb:
            self.assertIsNone(L.open_window("http://u", Path("."), False))
        wb.assert_called_once_with("http://u")

    def test_log_kept_small(self):
        """data/logs/auto3d.log; one past LOG_KEEP is moved to auto3d.1.log at the next start."""
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(L, "LOG_KEEP", 10):
            f = L.open_log(Path(tmp))
            f.write("x" * 20)
            f.close()
            f = L.open_log(Path(tmp))
            f.write("new\n")
            f.close()
            logs = Path(tmp) / "logs"
            self.assertEqual((logs / "auto3d.1.log").read_text(), "x" * 20)
            self.assertEqual((logs / "auto3d.log").read_text(), "new\n")


class TestFrozen(unittest.TestCase):
    def test_mcp_through_the_exe(self):
        """Built, the chat's MCP server is the exe itself (`--mcp-server --url …`): there is no Python to run the script."""
        from auto3d.agent import MCP_SCRIPT, ChatSession
        cmd = ChatSession("http://127.0.0.1:7").command("claude")
        mcp = json.loads(cmd[cmd.index("--mcp-config") + 1])["mcpServers"]["auto3d"]
        self.assertEqual(mcp["args"], [str(MCP_SCRIPT), "--url", "http://127.0.0.1:7"])
        with mock.patch.object(sys, "frozen", True, create=True):
            cmd = ChatSession("http://127.0.0.1:7").command("claude")
        mcp = json.loads(cmd[cmd.index("--mcp-config") + 1])["mcpServers"]["auto3d"]
        self.assertEqual((mcp["command"], mcp["args"]), (sys.executable, ["--mcp-server", "--url", "http://127.0.0.1:7"]))

    def test_mcp_mode(self):
        """`--mcp-server …` runs auto3d/mcp_server.py's main with the rest of the arguments."""
        with mock.patch("auto3d.mcp_server.main") as m, mock.patch.object(sys, "argv", ["Auto3DModeler.exe"]):
            self.assertEqual(L.main(["--mcp-server", "--url", "http://127.0.0.1:9"]), 0)
            self.assertEqual(sys.argv[1:], ["--url", "http://127.0.0.1:9"])
        m.assert_called_once()

    def test_build_stamp(self):
        """The built app has no git: BUILD.json says which commit it is."""
        from auto3d import version
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(version, "ROOT", Path(tmp)):
            (Path(tmp) / "BUILD.json").write_text(json.dumps({"commit": "abc1234", "branch": "main", "date": "2026-10-29"}))
            version.build.cache_clear()
            try:
                self.assertEqual(version.text(), f"{version.VERSION} (main @ abc1234, 2026-10-29)")
            finally:
                version.build.cache_clear()
            self.assertEqual(version.head(), "")  # (the built app: no git, never stale)

    def test_moved_head(self):
        """The checkout moved on since the server started: the report's version says both commits (and the page's)."""
        from auto3d import version
        answers = {("rev-parse", "--short", "HEAD"): "92d0e37", ("log", "-1", "--format=%cs"): "2026-10-27",
                   ("rev-parse", "--abbrev-ref", "HEAD"): "main", ("status", "--porcelain", "--untracked-files=no"): ""}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(version, "ROOT", Path(tmp)), \
                mock.patch.object(version, "_git", side_effect=lambda *a: answers[a]), mock.patch.dict("os.environ", {"A3D_FAKE_HEAD": ""}):
            version.build.cache_clear()
            version._head["at"] = -version.HEAD_TTL
            try:
                self.assertEqual(version.text(), f"{version.VERSION} (main @ 92d0e37, 2026-10-27)")
                self.assertEqual(version.stale(), "")
                answers[("rev-parse", "--short", "HEAD")] = "1e35a8d"  # (a merge: the server keeps its start commit)
                self.assertEqual(version.head(), "92d0e37")  # (asked again only after HEAD_TTL)
                version._head["at"] = -version.HEAD_TTL
                self.assertEqual(version.stale(), "1e35a8d")
                self.assertEqual(version.text(), f"{version.VERSION} (server started at main @ 92d0e37, 2026-10-27; "
                                                  f"checkout now at 1e35a8d — restart the app to run it)")
                self.assertTrue(version.text("0aa1111").endswith("; page loaded at 0aa1111 — reload it)"))
                self.assertNotIn("page loaded", version.text("92d0e37"))
                with mock.patch.dict("os.environ", {"A3D_FAKE_HEAD": "fa4e000"}):
                    self.assertEqual(version.stale(), "fa4e000")
            finally:
                version.build.cache_clear()
                version._head["at"] = -version.HEAD_TTL


if __name__ == "__main__":
    unittest.main()
