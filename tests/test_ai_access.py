"""The AI chat's access, set up at any time while the app runs (auto3d/ai_access.py): the API key kept per user
(Windows DPAPI: the file does not hold the key), its check with Anthropic (refused / offline / ok — the network faked
here), the states the ✨ AI panel shows (no_claude / signed_out / invalid / ok), a chat error about the access, the key
given to the chat's Claude Code, and the routes (/api/ai/access, /key, /logout)."""
import io
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from auto3d import ai_access as A

KEY = "sk-ant-api03-" + "x" * 40


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name)
        self.env = mock.patch.dict(os.environ, {"A3D_DATA": str(self.data)})
        self.env.start()
        A._invalid.clear()
        A._status_cache.clear()

    def tearDown(self):
        self.env.stop()
        A._invalid.clear()
        A._status_cache.clear()
        self.tmp.cleanup()


class TestKey(Base):
    def test_keep_load_forget(self):
        """Kept in <data>/ai/key.bin, not as plain text on Windows (DPAPI); read back; forgotten."""
        self.assertIsNone(A.load_key())
        A.save_key(f"  {KEY}\n")
        self.assertEqual(A.key_file(), self.data / "ai" / "key.bin")
        if os.name == "nt":
            self.assertNotIn(KEY.encode(), A.key_file().read_bytes())
        self.assertEqual(A.load_key(), KEY)
        A.forget_key()
        self.assertIsNone(A.load_key())
        A.forget_key()  # (nothing to forget: fine)

    def test_unreadable(self):
        """A file this user cannot decrypt (another user's, damaged) counts as no key."""
        A.key_file().parent.mkdir(parents=True)
        A.key_file().write_bytes(b"\x00garbage")
        if os.name == "nt":
            self.assertIsNone(A.load_key())

    def test_check(self):
        """Anthropic refuses (401 / 403) -> invalid; no connection or another error -> offline; else ok. Not a key at
        all -> invalid without asking."""
        def http(code):
            return urllib.error.HTTPError(A.API_URL, code, "x", {}, io.BytesIO(b""))
        with mock.patch("urllib.request.urlopen") as op:
            self.assertEqual(A.check_key("hello"), "invalid")
            op.assert_not_called()
            op.side_effect = http(401)
            self.assertEqual(A.check_key(KEY), "invalid")
            req = op.call_args[0][0]
            self.assertTrue(req.full_url.startswith("https://api.anthropic.com/v1/models"))  # only ever to Anthropic
            self.assertEqual(req.get_header("X-api-key"), KEY)
            op.side_effect = http(529)
            self.assertEqual(A.check_key(KEY), "offline")
            op.side_effect = urllib.error.URLError("no network")
            self.assertEqual(A.check_key(KEY), "offline")
            op.side_effect = None
            self.assertEqual(A.check_key(KEY), "ok")

    def test_auth_errors(self):
        for text in ("Invalid API key · Please run /login", "API Error: 401 {\"type\":\"authentication_error\"}",
                     "OAuth token has expired", "Not logged in · Please run /login"):
            self.assertTrue(A.auth_error(text), text)
        for text in (None, "", "The CAD kernel failed.", "Rate limited, retrying"):
            self.assertFalse(A.auth_error(text), text)

    def test_chat_env(self):
        self.assertNotIn("ANTHROPIC_API_KEY", A.chat_env({"PATH": "x"}))
        A.save_key(KEY)
        self.assertEqual(A.chat_env({"PATH": "x"}), {"PATH": "x", "ANTHROPIC_API_KEY": KEY})


class TestState(Base):
    def test_states(self):
        """no Claude Code -> no_claude; signed out -> signed_out; signed in -> ok (claude, its e-mail); a kept key ->
        ok (key, its last 4); refused in a chat -> invalid; a new key -> ok again."""
        none = lambda: None
        exe = lambda: "C:/claude.exe"
        out = lambda *_: {"loggedIn": False}
        self.assertEqual(A.state(none)["state"], "no_claude")
        s = A.state(exe, status=out)
        self.assertEqual((s["state"], s["method"]), ("signed_out", None))
        self.assertIn("console.anthropic.com", s["links"]["console"])
        A._status_cache.clear()
        s = A.state(exe, status=lambda *_: {"loggedIn": True, "email": "a@b.cz", "authMethod": "claude.ai"})
        self.assertEqual((s["state"], s["method"], s["email"]), ("ok", "claude", "a@b.cz"))
        A.save_key(KEY)
        s = A.state(exe, status=out)
        self.assertEqual((s["state"], s["method"], s["key_end"]), ("ok", "key", "xxxx"))
        A.mark_invalid(KEY)
        self.assertEqual(A.state(exe, status=out)["state"], "invalid")
        A.save_key(KEY[:-1] + "y")
        self.assertEqual(A.state(exe, status=out)["state"], "ok")

    def test_status_asked_seldom(self):
        """`claude auth status` (about a second) at most every few seconds."""
        calls = []
        st = lambda *_: calls.append(1) or {"loggedIn": False}
        for _ in range(3):
            A.state(lambda: "C:/claude.exe", status=st)
        self.assertEqual(len(calls), 1)

    def test_refused_in_chat(self):
        """A chat turn that ends with an access error marks the kept key invalid (the panel's set-up screen)."""
        from auto3d.agent import ChatSession, translate
        ev = translate({"type": "result", "is_error": True, "result": "Invalid API key · Please run /login"})[0]
        self.assertTrue(ev["auth"])
        self.assertFalse(translate({"type": "result", "is_error": False, "result": "done"})[0]["auth"])
        A.save_key(KEY)
        ChatSession("http://127.0.0.1:1")._access_refused()
        self.assertEqual(A.state(lambda: "C:/claude.exe", status=lambda *_: {})["state"], "invalid")


class TestRoutes(Base):
    def test_routes(self):
        import server
        c = server.app.test_client()
        with mock.patch("auto3d.agent.find_claude", return_value=None):
            self.assertEqual(c.get("/api/ai/access").get_json()["state"], "no_claude")
        r = c.post("/api/ai/key", json={"key": "nonsense"})
        self.assertEqual((r.status_code, r.get_json()["code"]), (400, "invalid"))
        with mock.patch.object(A, "check_key", return_value="invalid"):
            r = c.post("/api/ai/key", json={"key": KEY})
        self.assertEqual(r.status_code, 400)
        self.assertIn("refused", r.get_json()["error"])
        self.assertIsNone(A.load_key())  # a refused key is not kept
        with mock.patch.object(A, "check_key", return_value="ok"), mock.patch("auto3d.agent.find_claude", return_value="C:/claude.exe"):
            r = c.post("/api/ai/key", json={"key": KEY})
            self.assertEqual((r.status_code, r.get_json()["state"], r.get_json()["checked"]), (200, "ok", True))
            self.assertEqual(A.load_key(), KEY)
            with mock.patch.object(A, "claude_status", return_value={}), mock.patch("server.find_claude", return_value=None):
                r = c.post("/api/ai/logout", json={})
            self.assertEqual(r.get_json()["state"], "signed_out")
        self.assertIsNone(A.load_key())


if __name__ == "__main__":
    unittest.main()
