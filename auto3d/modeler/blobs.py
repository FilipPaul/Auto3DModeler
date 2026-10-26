"""Big files a 3D model uses (an imported STEP), kept on disk by their SHA-256: a model step names the file by its
hash, so a 40 MB STEP is not sent with every rebuild. The project file carries them (saved / opened by the browser)."""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

DIR = Path(os.environ.get("AUTO3D_BLOBS") or Path.home() / ".auto3d" / "blobs")
_SHA = re.compile(r"^[0-9a-f]{64}$")


class Missing(KeyError):
    pass


def put(data: bytes) -> str:
    sha = hashlib.sha256(data).hexdigest()
    p = DIR / sha
    if not p.exists():
        DIR.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".part")
        tmp.write_bytes(data)
        os.replace(tmp, p)
    return sha


def path(sha: str) -> Path:
    if not _SHA.match(str(sha or "")):
        raise Missing(sha)
    p = DIR / sha
    if not p.exists():
        raise Missing(sha)
    return p


def get(sha: str) -> bytes:
    return path(sha).read_bytes()
