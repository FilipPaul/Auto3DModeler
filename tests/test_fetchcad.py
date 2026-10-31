"""🌐 fetch_cad: a maker's CAD file by its link — only CAD content passes (STEP, IGES, STL, a ZIP of one; a web page is
refused with why), at most the size limit, https only, kept in the download cache (the same part number / URL again: no
download); the AI's tool makes it a library part with its part number (the kernel tests: its volume, watertight, a STEP
round trip). A local http server stands in for the makers' sites — no internet."""
import io
import json
import math
import struct
import tempfile
import threading
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from auto3d import fetchcad as F
from auto3d.modeler import available

STEP = b"ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION(('part'),'2;1');\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n"
IGES = ((" " * 72 + "S0000001\n") + ("1H,,1H;" + " " * 65 + "G0000001\n")).encode()
STL_BIN = b"solid but binary".ljust(80, b" ") + struct.pack("<I", 1) + struct.pack("<12fH", *([0.0] * 12), 0)
STL_TXT = b"solid cube\n facet normal 0 0 1\n  outer loop\n   vertex 0 0 0\n   vertex 1 0 0\n   vertex 0 1 0\n  endloop\n endfacet\nendsolid cube\n"
HTML = b"<!DOCTYPE html><html><head><title>Login</title></head><body>Sign in to download</body></html>"


def zipped(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n, d in files.items():
            z.writestr(n, d)
    return buf.getvalue()


class Site:
    """A local web server: path -> (bytes, content type, extra headers); counts the requests per path."""

    def __init__(self, pages: dict):
        self.pages, self.hits = pages, {}
        site = self

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                site.hits[self.path] = site.hits.get(self.path, 0) + 1
                page = site.pages.get(self.path)
                if page is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                data, ctype, extra = page[0], page[1], dict(page[2])
                code = int(extra.pop("status", 200)) if "status" in extra else 200
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                for k, v in extra.items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()


class TestContent(unittest.TestCase):
    def test_cad_kinds_pass(self):
        self.assertEqual(F.check(STEP, "MISUMI_SFJ8-100.STEP")[1:], ("step", "MISUMI_SFJ8-100.STEP"))
        self.assertEqual(F.check(b"\xef\xbb\xbf  " + STEP, "x")[1], "step")  # (a BOM and spaces before the header)
        self.assertEqual(F.check(IGES, "part.igs")[1:], ("iges", "part.igs"))
        self.assertEqual(F.check(STL_BIN, "p.stl")[1], "stl")  # (a binary STL whose header says "solid")
        self.assertEqual(F.check(STL_TXT, "")[1:], ("stl", "part.stl"))
        self.assertEqual(F.check(STEP, "download.php")[2], "download.php.step")  # (named for what it is)
        self.assertEqual(F.check(STEP, "a.stl")[2], "a.step")

    def test_a_zip_gives_its_cad_file_a_step_first(self):
        data, kind, name = F.check(zipped({"readme.txt": b"hi", "doc/drawing.pdf": b"%PDF", "cad/x.stl": STL_TXT, "cad/DSNU-16-50.stp": STEP}))
        self.assertEqual((data, kind, name), (STEP, "step", "DSNU-16-50.stp"))
        with self.assertRaisesRegex(F.FetchError, "no STEP, IGES or STL.*readme.txt"):
            F.check(zipped({"readme.txt": b"hi"}))
        with self.assertRaisesRegex(F.FetchError, "broken ZIP"):
            F.check(b"PK\x03\x04garbage")

    def test_web_pages_and_other_files_are_refused(self):
        with self.assertRaisesRegex(F.FetchError, "web page, not a CAD file — a login or configurator"):
            F.check(HTML, "SFJ8-100")
        with self.assertRaisesRegex(F.FetchError, "web page"):
            F.check(b"Please wait ...", "x", "text/html; charset=utf-8")
        with self.assertRaisesRegex(F.FetchError, "not a CAD file.*application/pdf"):
            F.check(b"%PDF-1.7 ...", "x.pdf", "application/pdf")
        with self.assertRaisesRegex(F.FetchError, "empty"):
            F.check(b"")


class TestDownload(unittest.TestCase):
    def setUp(self):
        self.site = Site({"/f/part.step": (STEP, "application/octet-stream", {}),
                          "/dl?id=7": (zipped({"E2/x.STEP": STEP.replace(b"part", b"chain")}), "application/zip", {"Content-Disposition": 'attachment; filename="E2-15.zip"'}),
                          "/model.igs": (IGES, "application/iges", {}), "/m.stl": (STL_BIN, "model/stl", {}),
                          "/configurator": (HTML, "text/html", {}),
                          "/big.step": (STEP + b"x" * 5000, "application/octet-stream", {}),
                          "/login": (b"no", "text/plain", {"status": 403}),
                          "/to-http": (b"", "text/plain", {"status": 302, "Location": "http://example.com/x.step"}),
                          "/moved": (b"", "text/plain", {"status": 302, "Location": "/f/part.step"})})
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self.tmp.name) / "cad_downloads"

    def tearDown(self):
        self.site.close()
        self.tmp.cleanup()

    def get(self, path, **kw):
        return F.fetch(self.cache, self.site.url + path, local=True, **kw)

    def test_each_kind_downloads_and_is_kept(self):
        a = self.get("/f/part.step", pn="SFJ8-100", maker="MISUMI")
        self.assertEqual((a["kind"], a["file"], a["pn"], a["maker"], a["cached"]), ("step", "part.step", "SFJ8-100", "MISUMI", False))
        self.assertEqual(Path(a["path"]).read_bytes(), STEP)
        self.assertEqual(self.get("/dl?id=7")["file"], "x.STEP")
        self.assertEqual(self.get("/model.igs")["kind"], "iges")
        self.assertEqual(self.get("/m.stl")["kind"], "stl")
        self.assertEqual(self.get("/moved", pn="X1")["kind"], "step")  # (a redirect followed)
        idx = json.loads((self.cache / "index.json").read_text(encoding="utf-8"))["files"][a["sha"]]
        self.assertIn(self.site.url + "/f/part.step", idx["urls"])  # where it came from, kept with it
        self.assertEqual((idx["pn"], idx["maker"]), ("SFJ8-100", "MISUMI"))

    def test_the_same_part_or_url_again_comes_from_the_cache(self):
        self.get("/f/part.step", pn="SFJ8-100", maker="MISUMI")
        for again in (lambda: self.get("/f/part.step"), lambda: F.fetch(self.cache, pn="SFJ8-100", maker="MISUMI"),
                      lambda: F.fetch(self.cache, pn="sfj8-100"), lambda: F.fetch(self.cache, pn="SFJ8-100", url="https://elsewhere.example/a.step")):
            r = again()
            self.assertTrue(r["cached"])
            self.assertEqual(Path(r["path"]).read_bytes(), STEP)
        self.assertEqual(self.site.hits["/f/part.step"], 1)  # downloaded once
        with self.assertRaisesRegex(F.FetchError, "give its url"):
            F.fetch(self.cache, pn="SFJ8-200")
        with self.assertRaisesRegex(F.FetchError, "give its url"):
            F.fetch(self.cache, pn="SFJ8-100", maker="Festo")  # (another maker's part number)

    def test_refused(self):
        with self.assertRaisesRegex(F.FetchError, "web page, not a CAD file"):
            self.get("/configurator")
        with self.assertRaisesRegex(F.FetchError, "over the 0 MB limit|limit"):
            self.get("/big.step", max_bytes=1000)
        with self.assertRaisesRegex(F.FetchError, "403.*login"):
            self.get("/login")
        with self.assertRaisesRegex(F.FetchError, "Only https"):
            self.get("/to-http")  # (a redirect away to http: not followed)
        with self.assertRaisesRegex(F.FetchError, "Only https"):
            F.fetch(self.cache, self.site.url + "/f/part.step")  # (http, not allowed outside the tests)
        for bad in ("file:///C:/Windows/win.ini", "ftp://x/y.step", "javascript:alert(1)", "https://"):
            with self.assertRaisesRegex(F.FetchError, "Only https"):
                F.fetch(self.cache, bad)
        self.assertFalse((self.cache / "index.json").exists())  # nothing kept

    def test_internet_setting(self):
        data = Path(self.tmp.name)
        self.assertTrue(F.internet_on(data))  # default on
        (data / "ai").mkdir()
        (data / "ai" / "settings.json").write_text('{"internet": false}', encoding="utf-8")
        self.assertFalse(F.internet_on(data))
        (data / "ai" / "settings.json").write_text('{"internet": true}', encoding="utf-8")
        self.assertTrue(F.internet_on(data))
        with mock.patch.dict("os.environ", {"A3D_AI_INTERNET": "0"}):
            self.assertFalse(F.internet_on(data))


class TestTool(unittest.TestCase):
    """The AI's fetch_cad through /api/agent/call (to: library needs no page)."""

    def setUp(self):
        import server
        self.server = server
        self.tmp = tempfile.TemporaryDirectory()
        data = Path(self.tmp.name)
        self.patches = [mock.patch.object(server, "DATA", data), mock.patch.object(server, "CAD_CACHE", data / "cad_downloads"),
                        mock.patch.object(server, "LIBRARY_USER", data / "library"), mock.patch.dict("os.environ", {"A3D_FETCH_LOCAL": "1"})]
        for p in self.patches:
            p.start()
        self.c = server.app.test_client()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def call(self, **args):
        return self.c.post("/api/agent/call", json={"tool": "fetch_cad", "args": args}).get_json()

    def test_internet_off_refuses(self):
        (self.server.DATA / "ai").mkdir()
        (self.server.DATA / "ai" / "settings.json").write_text('{"internet": false}', encoding="utf-8")
        r = self.call(url="https://example.com/x.step", part_number="X")
        self.assertTrue(r["isError"])
        self.assertIn("internet je vypnutý v nastavení AI", r["content"][0]["text"])

    def test_a_web_page_is_refused_plainly(self):
        site = Site({"/p": (HTML, "text/html", {})})
        try:
            r = self.call(url=site.url + "/p", part_number="X", to="library")
        finally:
            site.close()
        self.assertTrue(r["isError"])
        self.assertIn("web page, not a CAD file", r["content"][0]["text"])

    @unittest.skipUnless(available("occ"), "OCP not installed")
    def test_a_step_becomes_a_library_part_with_its_part_number(self):
        from auto3d.modeler import doc, kernel as K
        from test_exchange_formats import PLATE_HOLE, plate_with_hole
        from test_modeler_kernel import watertight
        step = doc.export({"features": plate_with_hole()}, "step")
        site = Site({"/files/PLATE-40.STEP": (step, "application/octet-stream", {}),
                     "/files/plate.zip": (zipped({"PLATE-40.igs": doc.export({"features": plate_with_hole()}, "iges")}), "application/zip", {})})
        try:
            r = self.call(url=site.url + "/files/PLATE-40.STEP", part_number="PLATE-40", maker="ACME", to="library")
            self.assertFalse(r["isError"], r)
            got = json.loads(r["content"][0]["text"])
            self.assertEqual((got["item"], got["pn"], got["maker"], got["from_cache"]), ("dl-acme-plate-40", "PLATE-40", "ACME", False))
            self.assertAlmostEqual(got["volume_mm3"], PLATE_HOLE, delta=PLATE_HOLE * 1e-6)
            items = {i["id"]: i for i in self.c.get("/api/library").get_json()["items"]}
            it = items["dl-acme-plate-40"]
            self.assertEqual((it["pn"], it["maker"], it["category"], it["source"]), ("PLATE-40", "ACME", "My parts", "user"))
            self.assertEqual(it["source_url"], site.url + "/files/PLATE-40.STEP")
            # the library part's solid: the plate's volume, watertight, and a STEP written and read back the same
            built = doc.rebuild({"features": it["features"]})
            self.assertTrue(built["ok"], built["features"])
            self.assertAlmostEqual(built["body"]["volume"], PLATE_HOLE, delta=PLATE_HOLE * 1e-6)
            self.assertTrue(watertight(built["body"]))
            st = doc.body_of({"features": it["features"]})
            self.assertAlmostEqual(K.volume(K.from_step(K.to_step(st.body.shape))), PLATE_HOLE, delta=PLATE_HOLE * 1e-6)
            # again by its part number: from the cache, no download
            again = json.loads(self.call(part_number="PLATE-40", maker="ACME", to="library")["content"][0]["text"])
            self.assertTrue(again["from_cache"])
            self.assertEqual(site.hits["/files/PLATE-40.STEP"], 1)
            # an IGES in a ZIP: read like a dragged-in file (sewn into the same solid)
            z = json.loads(self.call(url=site.url + "/files/plate.zip", part_number="PLATE-40-IGS", maker="ACME", to="library")["content"][0]["text"])
            self.assertEqual(z["kind"], "iges")
            self.assertAlmostEqual(z["volume_mm3"], PLATE_HOLE, delta=PLATE_HOLE * 1e-6)
        finally:
            site.close()


if __name__ == "__main__":
    unittest.main()
