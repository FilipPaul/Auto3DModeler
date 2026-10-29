"""🎬 A mechanism's animation: frames posted one by one made into one looping GIF (one palette for all, the frames as
sent, their time from the fps), a video kept as recorded; the file named after the mechanism in plain letters; bad ids,
too few frames, frames that are not pictures or too big, an empty video refused; a cancelled GIF leaves no frames; the
routes."""
import io
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image, ImageChops, ImageDraw

from auto3d import animation as AN
from auto3d import progress


def png(k, w=160, h=100):
    """A frame: a grey plate with a blue block moved k × 6 px right (a slider)."""
    im = Image.new("RGB", (w, h), (22, 27, 34))
    dr = ImageDraw.Draw(im)
    dr.rectangle([10, 60, w - 10, 80], fill=(185, 190, 200))
    dr.rectangle([10 + 6 * k, 40, 40 + 6 * k, 60], fill=(70, 130, 220))
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


class TestAnimation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "animations"

    def tearDown(self):
        self.tmp.cleanup()

    def test_gif_of_the_frames(self):
        for k in range(20):
            self.assertEqual(AN.add_frame(self.root, "a1", k, png(k)), k + 1)
        r = AN.write_gif(self.root, "a1", "Klikový mechanismus", fps=20)
        self.assertRegex(r["file"], r"^klikovy-mechanismus-\d{8}-\d{6}\.gif$")
        self.assertEqual((r["frames"], r["width"], r["height"], r["fps"]), (20, 160, 100, 20.0))
        with Image.open(r["path"]) as g:
            self.assertEqual((g.n_frames, g.size, g.info["loop"], g.info["duration"]), (20, (160, 100), 0, 50))
            frames = []
            for k in range(g.n_frames):
                g.seek(k)
                frames.append(g.convert("RGB"))
        self.assertTrue(all(ImageChops.difference(a, b).getbbox() for a, b in zip(frames, frames[1:])))  # (the block moves)
        # the frames as sent: the block's colour where it is, the plate's under it (one palette, no dither)
        self.assertEqual(frames[5].getpixel((10 + 30 + 15, 50)), (70, 130, 220))
        self.assertEqual(frames[5].getpixel((150, 70)), (185, 190, 200))
        self.assertFalse((self.root / ".frames" / "a1").exists())  # (the frames gone once made into the file)
        self.assertEqual(r["bytes"], Path(r["path"]).stat().st_size)
        # the same name again in the same second: another file
        for k in range(3):
            AN.add_frame(self.root, "a2", k, png(k))
        r2 = AN.write_gif(self.root, "a2", "Klikový mechanismus", fps=25)
        self.assertNotEqual(r2["file"], r["file"])
        with Image.open(r2["path"]) as g:
            self.assertEqual(g.info["duration"], 40)

    def test_refused(self):
        with self.assertRaises(AN.AnimationError):
            AN.add_frame(self.root, "../x", 0, png(0))
        with self.assertRaises(AN.AnimationError):
            AN.add_frame(self.root, "a1", AN.MAX_FRAMES, png(0))
        with self.assertRaisesRegex(AN.AnimationError, "not a picture"):
            AN.add_frame(self.root, "a1", 0, b"no picture")
        with self.assertRaisesRegex(AN.AnimationError, "at most"):
            AN.add_frame(self.root, "a1", 0, png(0, w=AN.MAX_SIDE + 2))
        AN.add_frame(self.root, "a1", 0, png(0))
        with self.assertRaisesRegex(AN.AnimationError, "No frames"):
            AN.write_gif(self.root, "a1", "x")
        with self.assertRaisesRegex(AN.AnimationError, "empty"):
            AN.save_file(self.root, "x", "webm", b"")
        with self.assertRaises(AN.AnimationError):
            AN.save_file(self.root, "x", "avi", b"x" * 100)
        self.assertEqual(AN.file_name("", "gif")[:10], "mechanism-")

    def test_video_kept(self):
        r = AN.save_file(self.root, "Čtyřkloubový mechanismus", "webm", b"\x1a\x45\xdf\xa3" + b"\0" * 200)
        self.assertRegex(r["file"], r"^ctyrkloubovy-mechanismus-.*\.webm$")
        self.assertEqual(Path(r["path"]).read_bytes()[:4], b"\x1a\x45\xdf\xa3")

    def test_cancelled(self):
        for k in range(5):
            AN.add_frame(self.root, "a3", k, png(k))
        progress.cancel("rid-anim-test")
        out = {}

        def run():  # (a request's thread)
            with progress.operation("rid-anim-test", "Making an animation"):
                try:
                    AN.write_gif(self.root, "a3", "x")
                except progress.Cancelled:
                    out["cancelled"] = True
        th = threading.Thread(target=run)
        th.start()
        th.join()
        self.assertTrue(out.get("cancelled"))
        self.assertEqual(list(self.root.glob("*.gif")), [])

    def test_routes(self):
        import server
        with mock.patch.object(server, "ANIMATIONS", self.root):
            c = server.app.test_client()
            for k in range(4):
                r = c.post(f"/api/anim/abc/frame/{k}", data=png(k), content_type="image/png")
                self.assertEqual(r.get_json()["frames"], k + 1)
            self.assertEqual(c.post("/api/anim/abc/frame/9", data=b"x").status_code, 400)
            r = c.post("/api/anim/abc/gif", json={"name": "Rameno", "fps": 20, "rid": "rid-anim-route"}).get_json()
            self.assertEqual((r["frames"], r["url"]), (4, f"/api/anim/file/{r['file']}"))
            f = c.get(r["url"])
            self.assertEqual((f.status_code, f.data[:6]), (200, b"GIF89a"))
            self.assertIn("attachment", f.headers["Content-Disposition"])
            f.close()
            self.assertEqual(c.post("/api/anim/abc/gif", json={"name": "x"}).status_code, 400)  # (its frames used up)
            v = c.post("/api/anim/abd/video/webm?name=Rameno", data=b"\x1a\x45\xdf\xa3" + b"\0" * 100).get_json()
            self.assertTrue(v["file"].startswith("rameno-") and v["file"].endswith(".webm"))
            c.post("/api/anim/abe/frame/0", data=png(0))
            self.assertTrue(c.delete("/api/anim/abe").get_json()["ok"])
            self.assertFalse((self.root / ".frames" / "abe").exists())
            self.assertEqual(c.delete("/api/anim/a.b").status_code, 400)


if __name__ == "__main__":
    unittest.main()
