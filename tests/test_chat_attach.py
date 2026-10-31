"""📎 Files attached to an AI chat message (auto3d/chat_attach.py): the type by the name, text read in its encoding
(UTF-8, Czech cp1250, Western cp1252 — never mojibake), the size caps (whole / its head / the message's total), and
the server's /api/chat/send passing them to the chat.

Run:  python -m unittest discover -s tests -v
"""
import base64
import json
import tempfile
import unittest
from pathlib import Path

from auto3d import chat_attach as ca

CZECH = "Příliš žluťoučký kůň úpěl ďábelské ódy — ěščřžýáíé ůň ĚŠČŘŽ"


class TestDecode(unittest.TestCase):
    def test_utf8(self):
        self.assertEqual(ca.decode_text(CZECH.encode("utf-8")), (CZECH, "utf-8"))

    def test_utf8_bom_and_utf16(self):
        self.assertEqual(ca.decode_text(b"\xef\xbb\xbf" + CZECH.encode("utf-8")), (CZECH, "utf-8"))
        self.assertEqual(ca.decode_text(CZECH.encode("utf-16")), (CZECH, "utf-16"))

    def test_cp1250_czech(self):
        self.assertEqual(ca.decode_text(CZECH.encode("cp1250")), (CZECH, "cp1250"))

    def test_cp1252_western(self):
        text = "Crème brûlée, Größe, façade, señor, ñandú"
        self.assertEqual(ca.decode_text(text.encode("cp1252")), (text, "cp1252"))

    def test_ascii(self):
        self.assertEqual(ca.decode_text(b"plain,csv\n1,2\n"), ("plain,csv\n1,2\n", "utf-8"))


class TestKindsAndCaps(unittest.TestCase):
    def test_kind(self):
        self.assertEqual([ca.kind(n) for n in ("a.TXT", "b.csv", "c.py", "d.step", "e.dxf", "f.zip", "g.exe", "h")],
                         ["text", "text", "text", "file", "file", "file", None, None])

    def test_size_label(self):
        self.assertEqual([ca.size_label(n) for n in (300, 2048, 200 * 1024, 3 * 1048576)], ["300 B", "2 kB", "200 kB", "3.0 MB"])

    def test_small_text_whole_in_a_fence(self):
        text, used = ca.block("notes.md", "C:\\x\\notes.md", "a ``` b\nline 2".encode("utf-8"), ca.TEXT_TOTAL_CAP)
        self.assertTrue(text.startswith("[Attached file: C:\\x\\notes.md, 14 B]\nnotes.md:\n````md\n"))
        self.assertTrue(text.endswith("line 2\n````"))  # (a fence longer than the backticks inside)
        self.assertEqual(used, 14)

    def test_large_text_its_head(self):
        raw = "".join(f"line {i} of the log\n" for i in range(12000)).encode("utf-8")  # ≈ 250 kB
        text, used = ca.block("run.log", "C:\\x\\run.log", raw, ca.TEXT_TOTAL_CAP)
        self.assertIn(f"[Attached file: C:\\x\\run.log, {ca.size_label(len(raw))}, first 200 lines included]", text)
        self.assertIn("line 199 of the log\n```", text)
        self.assertNotIn("line 200 of", text)
        self.assertLessEqual(used, ca.HEAD_BYTES)

    def test_head_cut_by_bytes(self):
        raw = ("x" * 500 + "\n").encode() * 300  # 200 lines would be 100 kB: cut to HEAD_BYTES of whole lines
        head, n = ca.head(raw.decode())
        self.assertEqual(n, ca.HEAD_BYTES // 501)
        self.assertLessEqual(len(head.encode()), ca.HEAD_BYTES)

    def test_total_cap_over_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            one = ("y" * 99 + "\n").encode() * 550  # 55 kB each: two whole, the third over the 150 kB total -> its head
            got = ca.attach(Path(tmp), [("a.txt", one), ("b.txt", one), ("c.txt", one)])
            self.assertEqual([("first" in g["text"]) for g in got], [False, False, True])
            self.assertTrue(all(Path(g["path"]).read_bytes() == one for g in got))
            inline = sum(len(g["text"].encode()) for g in got)
            self.assertLess(inline, ca.TEXT_TOTAL_CAP + 1024)

    def test_cad_file_by_path_and_refusals(self):
        with tempfile.TemporaryDirectory() as tmp:
            got = ca.attach(Path(tmp), [("Držák 1.STEP", b"ISO-10303-21;")])[0]
            self.assertEqual(got["text"], f"[Attached file: {got['path']}]")
            self.assertTrue(got["path"].endswith("-Držák_1.step") and Path(got["path"]).exists())
            with self.assertRaisesRegex(ValueError, "cannot be attached yet"):
                ca.attach(Path(tmp), [("ok.txt", b"x"), ("setup.exe", b"MZ")])
            self.assertEqual(len(list(Path(tmp).iterdir())), 1)  # (refused before any was saved)


class TestServerAndChat(unittest.TestCase):
    def test_server_passes_files_to_the_chat(self):
        import server
        sent = []

        class Stub:
            def send(self, text, photos, files=None):
                sent.append((text, photos, files))

        orig, folder = server._chat, server.CHAT_FILES
        server._chat = lambda client="": Stub()
        with tempfile.TemporaryDirectory() as tmp:
            server.CHAT_FILES = Path(tmp)
            try:
                c = server.app.test_client()
                data = "data:text/plain;base64," + base64.b64encode(CZECH.encode("cp1250")).decode()
                r = c.post("/api/chat/send", json={"text": "", "files": [{"name": "pozn.txt", "data": data}]})
                self.assertEqual(r.get_json(), {"ok": True})
                f = sent[0][2][0]
                self.assertIn(CZECH, f["text"])
                self.assertIn("cp1250", f["text"])
                r = c.post("/api/chat/send", json={"text": "hi", "files": [{"name": "a.exe", "data": "TVo="}]})
                self.assertEqual(r.status_code, 400)
                self.assertIn("cannot be attached yet", r.get_json()["error"])
            finally:
                server._chat, server.CHAT_FILES = orig, folder

    def test_chat_message_and_event(self):
        from auto3d.agent import ChatSession

        class Proc:
            def __init__(self):
                self.lines, self.stdin = [], self

            def poll(self):
                return None

            def write(self, b):
                self.lines.append(json.loads(b.decode("utf-8")))

            def flush(self):
                pass

        s = ChatSession("http://127.0.0.1:1")
        s.proc = Proc()
        events = s.subscribe()
        s.send("read this", [], [{"name": "a.csv", "size": 4, "path": "C:\\x\\a.csv", "text": "[Attached file: C:\\x\\a.csv]\n…"}])
        text = s.proc.lines[0]["message"]["content"][-1]["text"]
        self.assertTrue(text.startswith("read this\n\n[Attached file: C:\\x\\a.csv]"))
        ev = events.get(timeout=1)
        while ev.get("type") != "user":
            ev = events.get(timeout=1)
        self.assertEqual(ev["files"], [{"name": "a.csv", "size": 4, "path": "C:\\x\\a.csv"}])


if __name__ == "__main__":
    unittest.main()
