"""Project files (.a3d, auto3d/package.py): a ZIP of project.json, the imported files byte for byte under their own
names, the 🕘 version history and a picture; written and read back by the server (Save project, Open, open_file,
export project), and the kept projects' pictures (🕘 Recent projects, the start screen)."""
import base64
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from auto3d import autosave, package
from auto3d.modeler import blobs

ROOT = Path(__file__).resolve().parent.parent
STEP = (ROOT / "samples" / "ExportFromOurApp" / "part_base_plate.step").read_bytes()
STL = b"solid pin\nendsolid pin\n"
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
sha = lambda b: hashlib.sha256(b).hexdigest()


def project(*files):
    """A project with a ▣ Solid step per (bytes, file name) and an assembly of it."""
    feats = [{"id": f"F{i}", "type": "solid", "blob": sha(b), "file": n, "op": "add"} for i, (b, n) in enumerate(files, 1)]
    return {"app": "Auto3DModeler", "version": 3, "project_name": "Bracket", "unit": "mm", "active": {"part": "P1"},
            "parts": [{"id": "P1", "kind": "model", "name": "Plate", "model": {"features": feats}},
                      {"id": "P2", "kind": "model", "name": "Pin", "model": {"features": [{"id": "F1", "type": "sketch"}]}},
                      {"id": "P3", "kind": "assembly", "name": "Assembly", "assembly": {"instances": [{"id": "I1", "part": "P1"}, {"id": "I2", "part": "P2"}]}}]}


class TestPackage(unittest.TestCase):
    def test_round_trip_binary_and_named(self):
        """Every imported file goes in as it was (binary, byte for byte) under its original name; a STEP deflated, a
        picture stored; project.json says what it is; the picture and the 🕘 history come back."""
        files = {sha(STEP): STEP, sha(STL): STL, sha(PNG): PNG}
        proj = project((STEP, "plate.step"), (STL, "pin.stl"), (PNG, "logo.png"))
        hist = {"format": "a3d-versions", "v": 1, "state": {"on": "v2"}, "versions": [{"id": "v1"}],
                "objects": {"ab" * 32: base64.b64encode(b"\x78\x9c zlib").decode()}}
        data, missing = package.write(proj, files.get, hist, PNG)
        self.assertEqual(missing, [])
        z = zipfile.ZipFile(io.BytesIO(data))
        self.assertEqual(set(z.namelist()), {"project.json", "thumbnail.png", "blobs/plate.step", "blobs/pin.stl", "blobs/logo.png",
                                             "versions/index.json", f"versions/objects/{'ab' * 32}"})
        self.assertEqual(z.read("blobs/plate.step"), STEP)  # (rename .a3d -> .zip, take it out: the very file)
        self.assertEqual(z.getinfo("blobs/plate.step").compress_type, zipfile.ZIP_DEFLATED)
        self.assertEqual(z.getinfo("blobs/logo.png").compress_type, zipfile.ZIP_STORED)
        self.assertLess(z.getinfo("blobs/plate.step").compress_size, len(STEP) / 2)  # (no base64: smaller, not 33 % larger)
        man = json.loads(z.read("project.json"))
        self.assertEqual((man["format"], man["package"], man["version"]), ("a3d-package", 1, 3))
        self.assertEqual(man["blob_files"][sha(STEP)], "blobs/plate.step")
        self.assertNotIn("blobs", man)
        got = package.load(data)
        self.assertEqual(got["blobs"], files)
        self.assertEqual(got["thumbnail"], PNG)
        self.assertEqual(got["versions"], hist)
        self.assertEqual(got["project"]["parts"], proj["parts"])
        self.assertEqual(package.manifest(data)["project_name"], "Bracket")
        self.assertEqual(package.thumbnail(data), PNG)

    def test_names_made_safe_and_unique(self):
        a, b, c = b"one", b"two", b"three"
        proj = project((a, "C:\\cad\\motor.step"), (b, "motor.STEP"), (c, ""))
        data, _ = package.write(proj, {sha(a): a, sha(b): b, sha(c): c}.get)
        man = package.manifest(data)
        self.assertEqual(man["blob_files"][sha(a)], "blobs/motor.step")  # (the name only, not its folder)
        self.assertEqual(man["blob_files"][sha(b)], f"blobs/{sha(b)}.step")  # (the same name twice: its hash)
        self.assertEqual(man["blob_files"][sha(c)], f"blobs/{sha(c)}.bin")  # (no name known)
        self.assertEqual(package.load(data)["blobs"], {sha(a): a, sha(b): b, sha(c): c})

    def test_a_missing_file_is_said(self):
        data, missing = package.write(project((STL, "pin.stl")), {}.get)
        self.assertEqual(missing, [sha(STL)])
        self.assertEqual(package.load(data)["blobs"], {})

    def test_a_file_changed_inside_follows(self):
        """A STEP taken out, changed in another CAD and put back: it opens with its new content (its new hash)."""
        data, _ = package.write(project((STL, "pin.stl")), {sha(STL): STL}.get)
        src, out = zipfile.ZipFile(io.BytesIO(data)), io.BytesIO()
        with zipfile.ZipFile(out, "w") as z:
            for n in src.namelist():
                z.writestr(n, b"solid pin2\nendsolid pin2\n" if n == "blobs/pin.stl" else src.read(n))
        kept = {}
        proj = package.store(package.load(out.getvalue()), lambda b: kept.setdefault(sha(b), b) and sha(b))
        new = sha(b"solid pin2\nendsolid pin2\n")
        self.assertEqual(proj["parts"][0]["model"]["features"][0]["blob"], new)
        self.assertIn(new, kept)

    def test_not_a_project(self):
        for bad in (b"{\"app\": \"Auto3DModeler\"}", b"", b"PK\x03\x04 broken"):
            with self.subTest(bad=bad[:12]), self.assertRaises(package.PackageError):
                package.load(bad)
        empty = io.BytesIO()
        with zipfile.ZipFile(empty, "w") as z:
            z.writestr("readme.txt", "hi")
        with self.assertRaisesRegex(package.PackageError, "no project.json"):
            package.load(empty.getvalue())
        newer = io.BytesIO()
        with zipfile.ZipFile(newer, "w") as z:
            z.writestr("project.json", json.dumps({"app": "Auto3DModeler", "version": 3, "package": 2, "parts": []}))
        with self.assertRaisesRegex(package.PackageError, "newer version"):
            package.load(newer.getvalue())


class TestServer(unittest.TestCase):
    def setUp(self):
        import server
        self.server = server
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = [mock.patch.object(blobs, "DIR", Path(self.tmp.name) / "blobs"),
                        mock.patch.object(server, "PROJECTS", Path(self.tmp.name) / "projects")]
        for p in self.patches:
            p.start()
        self.c = server.app.test_client()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_save_and_open(self):
        """Save project: the server packs the project with the files from its store (binary); Open: the .a3d's files back
        into the store (byte for byte) and the project as version 3."""
        blobs.put(STEP)
        thumb = "data:image/png;base64," + base64.b64encode(PNG).decode()
        r = self.c.post("/api/project/package", json={"project": project((STEP, "plate.step")), "thumbnail": thumb})
        self.assertEqual((r.status_code, r.mimetype, r.headers["X-Missing-Files"]), (200, "application/zip", "0"))
        self.assertEqual(package.load(r.data)["thumbnail"], PNG)
        data = r.data
        (Path(self.tmp.name) / "blobs" / sha(STEP)).unlink()  # (another computer: not in its store)
        r = self.c.post("/api/project/open", data=data, content_type="application/octet-stream")
        self.assertEqual(r.status_code, 200, r.get_json())
        got = r.get_json()
        self.assertEqual([p["name"] for p in got["project"]["parts"]], ["Plate", "Pin", "Assembly"])
        self.assertEqual(blobs.get(sha(STEP)), STEP)
        self.assertIsNone(got["versions"])
        r = self.c.post("/api/project/open", data=b"{\"app\": \"Auto3DModeler\"}", content_type="application/octet-stream")
        self.assertEqual(r.status_code, 400)
        self.assertIn("not a project file", r.get_json()["error"])
        self.assertEqual(self.c.post("/api/project/package", json={}).status_code, 400)

    def test_a_drawn_box_without_a_picture(self):
        """A project with no 3D part to draw still gets a picture (a box); a file gone from the store is said."""
        r = self.c.post("/api/project/package", json={"project": project((STL, "pin.stl")), "thumbnail": "data:image/svg+xml,<svg/>"})
        self.assertEqual(r.headers["X-Missing-Files"], "1")
        self.assertEqual(package.load(r.data)["thumbnail"][:8], b"\x89PNG\r\n\x1a\n")

    def test_kept_project_pictures(self):
        """🕘 Recent projects: a kept project's picture saved, listed with its time, served, forgotten with it."""
        pid = "aaaaaaaa-thumb"
        self.assertEqual(self.c.post(f"/api/projects/{pid}/thumb", json={"thumbnail": "data:image/png;base64," + base64.b64encode(PNG).decode()}).status_code, 404)
        self.c.post(f"/api/projects/{pid}", json={"project": project()})
        self.assertNotIn("thumb", self.c.get("/api/projects").get_json()["projects"][0])
        self.assertEqual(self.c.post(f"/api/projects/{pid}/thumb", json={"thumbnail": "data:image/png;base64,AAAA"}).status_code, 400)
        r = self.c.post(f"/api/projects/{pid}/thumb", json={"thumbnail": "data:image/png;base64," + base64.b64encode(PNG).decode()})
        self.assertEqual(r.status_code, 200)
        self.assertGreater(self.c.get("/api/projects").get_json()["projects"][0]["thumb"], 0)
        pic = self.c.get(f"/api/projects/{pid}/thumb")
        self.assertEqual((pic.status_code, pic.data), (200, PNG))
        pic.close()
        self.c.delete(f"/api/projects/{pid}")
        self.assertFalse((self.server.PROJECTS / f"{pid}.png").exists())
        self.assertEqual(self.c.get(f"/api/projects/{pid}/thumb").status_code, 404)
        with self.assertRaises(autosave.AutosaveError):
            autosave.save_thumb(self.server.PROJECTS, "../x", PNG)


if __name__ == "__main__":
    unittest.main()
