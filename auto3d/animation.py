"""🎬 A mechanism's motion saved as an animation (⚙ Mechanism ⋯ → 🎬 Save animation; the AI's record_animation).

The page renders the frames (its 3D view, one full cycle of the mechanism's driver) and posts them here one by one as
PNG pictures; they wait in a folder of their own under <data>/animations/.frames/<id>/ until `write_gif` makes one GIF
of them — one palette for all the frames (no flicker from frame to frame), looping for ever. A video (WebM / MP4) the
browser records itself (MediaRecorder) and only posts the finished file (`save_file`). The files stay in
<data>/animations/, named after the mechanism and the time.

Why the GIF is made here, not in the page: Pillow is already a dependency (no encoder vendored into web/), the file is
in the data folder for the AI as well, and the encoding runs in a server thread — the page stays responsive and the ⚙
jobs list can stop it.
"""
from __future__ import annotations

import io
import re
import shutil
import time
import unicodedata
from pathlib import Path

from PIL import Image

from auto3d import progress

MAX_FRAMES = 400                       # (one cycle at 20 fps is 80 frames at 1×; ½× twice as many)
MAX_SIDE = 1920                        # px — the page sends at most 1280 across
VIDEO_TYPES = {"webm": "video/webm", "mp4": "video/mp4"}
_ID = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


class AnimationError(ValueError):
    pass


def _frames(root: Path, aid: str) -> Path:
    if not _ID.match(aid or ""):
        raise AnimationError("Bad animation id.")
    return root / ".frames" / aid


def file_name(name: str, ext: str, when: float | None = None) -> str:
    """A file name for the mechanism's animation: its name in plain letters, the time — "klikovy-mechanismus-20261029-142501.gif"."""
    plain = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", plain).strip("-")[:48] or "mechanism"
    return f"{slug}-{time.strftime('%Y%m%d-%H%M%S', time.localtime(when))}.{ext}"


def _free(root: Path, name: str, ext: str) -> str:
    """file_name, with -2, -3 … when one of that name is there already (two in the same second)."""
    fn = file_name(name, ext)
    stem, k = fn[: -len(ext) - 1], 2
    while (root / fn).exists():
        fn, k = f"{stem}-{k}.{ext}", k + 1
    return fn


def add_frame(root: Path, aid: str, n: int, data: bytes) -> int:
    """Frame n (from 0) of the animation `aid`, a PNG -> how many frames it has now."""
    if not 0 <= n < MAX_FRAMES:
        raise AnimationError(f"At most {MAX_FRAMES} frames.")
    try:
        with Image.open(io.BytesIO(data)) as im:
            w, h = im.size
            im.verify()
    except Exception as e:  # (not a picture)
        raise AnimationError(f"Frame {n} is not a picture: {e}") from None
    if max(w, h) > MAX_SIDE:
        raise AnimationError(f"Frame {n} is {w} × {h} px — at most {MAX_SIDE} px a side.")
    d = _frames(root, aid)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{n:04d}.png").write_bytes(data)
    return len(list(d.glob("*.png")))


def discard(root: Path, aid: str):
    """The frames of a recording that was cancelled (or has been made into a file) gone."""
    shutil.rmtree(_frames(root, aid), ignore_errors=True)


def write_gif(root: Path, aid: str, name: str, fps: float = 20) -> dict:
    """The frames of `aid` as one looping GIF in root -> {file, path, frames, width, height, bytes, fps}. Reports its
    progress (auto3d.progress) and stops when cancelled (the frames are kept until discard)."""
    d = _frames(root, aid)
    files = sorted(d.glob("*.png")) if d.is_dir() else []
    if len(files) < 2:
        raise AnimationError("No frames to make an animation of.")
    progress.report("Making the GIF", 0, len(files))
    with Image.open(files[0]) as im:
        size = im.size
    # one palette for all: from a strip of frames across the cycle (the parts in all their places)
    picks = [files[int(k * (len(files) - 1) / 3)] for k in range(4)]
    strip = Image.new("RGB", (size[0], size[1] * len(picks)))
    for k, f in enumerate(picks):
        with Image.open(f) as im:
            strip.paste(im.convert("RGB").resize(size), (0, size[1] * k))
    pal = strip.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    out = []
    for k, f in enumerate(files):
        progress.report("Making the GIF", k, len(files))
        with Image.open(f) as im:
            rgb = im.convert("RGB")
            if rgb.size != size:
                rgb = rgb.resize(size)
            out.append(rgb.quantize(palette=pal, dither=Image.Dither.NONE))
    progress.report("Saving the GIF", len(files) - 1, len(files))
    root.mkdir(parents=True, exist_ok=True)
    fn = _free(root, name, "gif")
    path = root / fn
    out[0].save(path, save_all=True, append_images=out[1:], duration=max(20, round(1000 / max(1.0, fps) / 10) * 10),
                loop=0, disposal=1, optimize=False)
    discard(root, aid)
    return {"file": fn, "path": str(path), "frames": len(out), "width": size[0], "height": size[1],
            "bytes": path.stat().st_size, "fps": round(1000 / max(20, round(1000 / max(1.0, fps) / 10) * 10), 2)}


def save_file(root: Path, name: str, kind: str, data: bytes) -> dict:
    """A video the browser recorded (kind webm / mp4) kept in root -> {file, path, bytes}."""
    if kind not in VIDEO_TYPES:
        raise AnimationError(f"A video is {' or '.join(VIDEO_TYPES)}.")
    if len(data) < 64:
        raise AnimationError("The video is empty — the browser recorded nothing.")
    root.mkdir(parents=True, exist_ok=True)
    fn = _free(root, name, kind)
    (root / fn).write_bytes(data)
    return {"file": fn, "path": str(root / fn), "bytes": len(data)}
