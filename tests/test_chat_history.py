"""🕘 Previous conversations: the chat's conversations kept (auto3d/chat_history.py), opened again and continued — the
Claude Code session resumed, or a new one told the conversation in short. Claude Code is tools/fake_claude.py here.

Run:  python -m unittest tests.test_chat_history -v
"""
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from auto3d import agent, chat_history
from auto3d.agent import ChatSession

ROOT = Path(__file__).resolve().parent.parent
FAKE = ROOT / "tools" / "fake_claude.py"


class TestStore(unittest.TestCase):
    def test_keep_list_load_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = chat_history.new("P1", "Plate")
            self.assertEqual(chat_history.save(tmp, c)["messages"], 0)
            self.assertEqual(chat_history.list_convs(tmp), [])  # (no message: not kept)
            for ev in ({"type": "user", "text": "Make a 60 × 40 plate\nwith holes", "photos": [{"name": "a.png", "url": "/u"}]},
                       {"type": "delta", "text": "Su"}, {"type": "status", "text": "…"}, {"type": "tool", "name": "add_feature", "input": {"d": 5}},
                       {"type": "tool_result", "error": False, "text": "ok"}, {"type": "tool_result", "error": True, "text": "bad"},
                       {"type": "text", "text": "Sure — done."}, {"type": "done", "error": False}):
                chat_history.add(c, ev)
            self.assertEqual(c["title"], "Make a 60 × 40 plate")
            self.assertEqual(c["messages"], 2)  # the user's and the AI's
            self.assertEqual([e["type"] for e in c["events"]], ["user", "tool", "tool_result", "text"])
            chat_history.save(tmp, c)
            time.sleep(0.01)
            d = chat_history.new("P2", "Other")
            chat_history.add(d, {"type": "user", "text": "x" * 100})
            chat_history.save(tmp, d)
            self.assertTrue(d["title"].endswith("…") and len(d["title"]) == chat_history.MAX_TITLE + 1)
            self.assertEqual([m["id"] for m in chat_history.list_convs(tmp)], [d["id"], c["id"]])  # the newest first
            self.assertEqual([m["id"] for m in chat_history.list_convs(tmp, "P1")], [c["id"]])
            got = chat_history.load(tmp, c["id"])
            self.assertEqual((got["project_name"], got["events"][0]["photos"][0]["url"]), ("Plate", "/u"))
            chat_history.delete(tmp, c["id"])
            self.assertEqual([m["id"] for m in chat_history.list_convs(tmp)], [d["id"]])
            for bad in (c["id"], "../x", "nope"):
                with self.assertRaises(chat_history.ChatHistoryError):
                    chat_history.load(tmp, bad)

    def test_summary(self):
        evs = [{"type": "user", "text": "Make a plate"}, {"type": "tool", "name": "add_feature"}, {"type": "tool", "name": "add_feature"},
               {"type": "tool", "name": "get_model"}, {"type": "text", "text": "Done: 60 × 40 × 5."}, {"type": "user", "text": "Thanks", "photos": [{}]}]
        self.assertEqual(chat_history.summary(evs), "User: Make a plate\n(AI used: add_feature, get_model)\nAI: Done: 60 × 40 × 5.\n"
                                                    "User: Thanks [1 photo(s)]")
        long = [{"type": "user", "text": f"message {i} " + "x" * 280} for i in range(40)]
        s = chat_history.summary(long, limit=1000)
        self.assertTrue(s.startswith("… (earlier messages left out)") and "message 39" in s and "message 0 " not in s and len(s) < 1100)


class TestContinue(unittest.TestCase):
    """A chat with the stand-in Claude Code: kept, opened in a new session object (the app restarted) and continued."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Path(self.tmp.name) / "claude"
        self.env = mock.patch.dict(os.environ, {"AUTO3D_CLAUDE": str(FAKE), "CLAUDE_CONFIG_DIR": str(self.cfg)})
        self.env.start()
        self.store = Path(self.tmp.name) / "chats"
        self.chats = []

    def tearDown(self):
        for c in self.chats:
            c.stop()
        time.sleep(0.2)  # (the readers see the end)
        for c in self.chats:
            for f in (c.proc.stdin, c.proc.stdout, c.proc.stderr) if c.proc else ():
                try:
                    f.close()
                except OSError:
                    pass
        self.env.stop()
        self.tmp.cleanup()

    def chat(self):
        c = ChatSession("http://127.0.0.1:1", "W1", self.store)
        c.project = {"id": "P1", "name": "Plate"}
        self.chats.append(c)
        return c

    def turn(self, chat, text):
        last = chat.history[-1]["seq"] if chat.history else 0
        q = chat.subscribe()
        chat.send(text)
        got = []
        end = time.time() + 90
        while time.time() < end:
            ev = q.get(timeout=90)
            if ev["seq"] <= last:
                continue  # (the chat so far, replayed)
            got.append(ev)
            if ev["type"] in ("done", "exit"):
                break
        chat.unsubscribe(q)
        return [e["text"] for e in got if e["type"] == "text"][-1], got

    def test_resume_then_summary(self):
        a = self.chat()
        reply, _ = self.turn(a, "Make a plate")
        self.assertEqual(reply, "Echo #1: Make a plate | resumed: no | summary: no")
        reply, _ = self.turn(a, "Now a hole")
        self.assertTrue(reply.startswith("Echo #2: Now a hole"), reply)
        cid, sid = a.conv["id"], a.conv["session"]
        meta = chat_history.list_convs(self.store)[0]
        self.assertEqual((meta["id"], meta["messages"], meta["title"], meta["project"], meta["session"]), (cid, 4, "Make a plate", "P1", sid))
        a.stop()

        b = self.chat()  # (the app started again: the conversation opened from 🕘)
        q = b.subscribe()
        b.open(cid)
        evs = [q.get(timeout=1) for _ in range(q.qsize())]
        self.assertEqual(evs[0]["type"], "reset")
        self.assertEqual([e["type"] for e in evs if e.get("old")], ["user", "tool", "text"] * 2)
        self.assertEqual((evs[-1]["type"], evs[-1]["id"], evs[-1]["opened"]), ("conv", cid, True))
        reply, _ = self.turn(b, "And round the edges")
        self.assertEqual(reply, f"Echo #3: And round the edges | resumed: {sid} | summary: no")  # Claude Code's own session
        b.stop()

        (self.cfg / "projects" / "fake" / f"{sid}.jsonl").unlink()  # (its session gone: a new one, told in short)
        c = self.chat()
        c.open(cid)
        reply, evs = self.turn(c, "Make it red")
        self.assertEqual(reply, "Echo #1: Make it red | resumed: no | summary: yes")
        self.assertIn({"type": "note", "key": "summary"}, [{k: e[k] for k in ("type", "key") if k in e} for e in evs])
        self.assertEqual(chat_history.load(self.store, cid)["messages"], 8)
        self.assertNotEqual(c.conv["session"], sid)

    def test_a_resume_that_fails_goes_on_with_the_summary(self):
        a = self.chat()
        self.turn(a, "Make a plate")
        a.stop()
        a.conv["session"] = "0000aaaa-gone"
        with mock.patch.object(agent, "session_exists", return_value=True):  # (looked there, but Claude Code has it not)
            reply, evs = self.turn(a, "Go on")
        self.assertEqual(reply, "Echo #1: Go on | resumed: no | summary: yes")
        self.assertNotIn("exit", [e["type"] for e in evs])

    def test_new_conversation(self):
        a = self.chat()
        self.turn(a, "One")
        first = a.conv["id"]
        q = a.subscribe()
        a.reset()
        self.assertIsNone(a.conv)
        self.assertIn({"type": "conv", "id": None}, [{k: v for k, v in e.items() if k != "seq"} for e in [q.get(timeout=1) for _ in range(q.qsize())]])
        reply, _ = self.turn(a, "Two")
        self.assertTrue(reply.startswith("Echo #1: Two"), reply)  # (a new session)
        self.assertNotEqual(a.conv["id"], first)
        self.assertEqual(len(chat_history.list_convs(self.store)), 2)


class TestServer(unittest.TestCase):
    def test_list_open_delete(self):
        import server
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(server, "CHAT_STORE", Path(tmp)):
            c = chat_history.new("P1", "Plate")
            chat_history.add(c, {"type": "user", "text": "Hi"})
            chat_history.save(tmp, c)
            cl = server.app.test_client()
            got = cl.get("/api/chat/conversations?client=tw1").get_json()
            self.assertEqual(([m["id"] for m in got["conversations"]], got["current"]), ([c["id"]], None))
            server.CHATS.pop("tw1", None)
            chat = server._chat("tw1")
            chat.store = Path(tmp)
            self.assertEqual(cl.post("/api/chat/open", json={"id": c["id"], "client": "tw1"}).get_json(), {"ok": True})
            self.assertEqual(cl.get("/api/chat/status?client=tw1").get_json()["conversation"]["id"], c["id"])
            self.assertEqual(cl.post("/api/chat/open", json={"id": "nope", "client": "tw1"}).status_code, 404)
            self.assertEqual(cl.delete(f"/api/chat/conversations/{c['id']}").get_json(), {"ok": True})
            self.assertIsNone(chat.conv)  # (its window starts a new one)
            self.assertEqual(cl.get("/api/chat/conversations").get_json()["conversations"], [])
            self.assertEqual(cl.delete(f"/api/chat/conversations/{c['id']}").status_code, 404)
            server.CHATS.pop("tw1", None)

    def test_events_stream_at_once(self):
        """The chat's events reach the page as they come: the request timings must not read the endless stream first
        (they did: the page got nothing — no message of the user, no answer, the chat looked dead)."""
        import threading
        import server
        server.CHATS.pop("tw2", None)
        server._chat("tw2").emit({"type": "status", "text": "hello"})
        got = []

        def read():
            resp = server.app.test_client().get("/api/chat/events?client=tw2", buffered=False)
            it = iter(resp.response)
            while not any(b"hello" in c for c in got):
                got.append(next(it))
            resp.close()

        t = threading.Thread(target=read, daemon=True)
        t.start()
        t.join(10)
        self.assertFalse(t.is_alive(), "the event stream sent nothing")
        self.assertTrue(got[0].startswith(b"retry:"), got)
        self.assertIn(b'"text": "hello"', got[-1])
        server.CHATS.pop("tw2", None)


if __name__ == "__main__":
    unittest.main()
