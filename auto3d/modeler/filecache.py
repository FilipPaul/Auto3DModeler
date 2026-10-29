"""Big imported files read and meshed once: kept on disk in the data folder (cache/models), by the file's hash, so
opening the same 44 MB board again takes a second or two, not half a minute (reading its STEP takes 15 s, meshing
it 10 s more). Nothing in it is needed: a missing, old or damaged entry is made again from the file.

  <sha>.brep         the shape as read (kernel.read_step_colours, inside-out solids turned) in OpenCASCADE's binary
                     B-rep: exact, the same faces in the same order — measurements and exports are as from the STEP
  <sha>.json         {stamp, colours, info: import_solid's answer}
  <sha>.<key>.mesh   kernel.tessellate's answer for the file's solid as it is (one per step id, ref or not, 🪶 lod)

An entry holds the stamp of what made it: this cache's VERSION, the code (kernel.py, doc.py and this file's hash: a
changed reader or mesher makes new entries) and the file's size and time — a file changed in place, or other code,
and it is made again. Only files with more than MIN_FACES faces are kept (a small one reads quickly); the folder is
kept under LIMIT_MB, the entries used least lately dropped first.
"""
from __future__ import annotations

import hashlib
import json
import marshal
import os
import re
from pathlib import Path

from . import blobs

VERSION = 1
DIR = Path(os.environ.get("A3D_DATA") or Path(__file__).resolve().parents[2] / "data") / "cache" / "models"
MIN_FACES = 3000  # (kernel.HEAVY_FACES: a model this big takes seconds to read and mesh)
LIMIT_MB = 4096

_code = None


def _stamp(sha):
    """What an entry of this file must have been made with, or None (the file is not here)."""
    global _code
    try:
        st = blobs.path(sha).stat()
    except blobs.Missing:
        return None
    if _code is None:  # (the code that reads, meshes and answers: changed, and the entries are made again)
        here = Path(__file__).parent
        _code = hashlib.sha1(b"".join((here / n).read_bytes() for n in ("kernel.py", "doc.py", "filecache.py"))).hexdigest()[:16]
    return {"v": VERSION, "code": _code, "size": st.st_size, "mtime": st.st_mtime_ns}


def _write(path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.part")  # (several kernel processes may write the same entry)
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _meta(sha):
    """The file's entry {stamp, colours, info} while it is valid, else None (an old one is removed)."""
    p = DIR / f"{sha}.json"
    try:
        meta = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    if meta.get("stamp") != _stamp(sha) or not (DIR / f"{sha}.brep").exists():
        drop(sha)
        return None
    return meta


def shape(sha):
    """The file's shape and colours ({face index: "#rrggbb"}) as first read, or None (not kept)."""
    meta = _meta(sha)
    if meta is None:
        return None
    from . import kernel
    try:
        s = kernel.read_brep(DIR / f"{sha}.brep")
    except Exception:  # noqa: BLE001 — damaged: read the file again
        drop(sha)
        return None
    _touch(sha)
    return s, {int(k): c for k, c in (meta.get("colours") or {}).items()}


def info(sha):
    """import_solid's answer for the file, kept with its shape, or None."""
    meta = _meta(sha)
    return meta.get("info") if meta else None


def keep(sha, shape_, colours, faces, info_=None):
    """Keep the file's shape (and import_solid's answer) when it is big (faces > MIN_FACES). Never fails: a full disk
    only means no cache."""
    stamp = _stamp(sha)
    if faces <= MIN_FACES or stamp is None:
        return False
    from . import kernel
    try:
        if not (DIR / f"{sha}.brep").exists() or _meta(sha) is None:
            DIR.mkdir(parents=True, exist_ok=True)
            tmp = DIR / f"{sha}.brep.{os.getpid()}.part"
            kernel.write_brep(shape_, tmp)
            os.replace(tmp, DIR / f"{sha}.brep")
        old = _meta(sha) or {}
        _write(DIR / f"{sha}.json", json.dumps({"stamp": stamp, "colours": {str(k): c for k, c in colours.items()},
                                                "info": info_ if info_ is not None else old.get("info")}).encode())
        _prune()
        return True
    except (OSError, RuntimeError):
        return False


def _key(src, light):
    sha, fid, whole = src
    return f"{sha}.{re.sub(r'[^A-Za-z0-9_-]', '_', str(fid))}-{'ref' if whole else 'solid'}-{'light' if light else 'full'}"


def mesh(src, light=False):
    """The mesh (kernel.tessellate's answer) of an imported file's solid as it is, or None. src: (sha, step id, ref)."""
    p = DIR / f"{_key(src, light)}.mesh"
    try:
        stamp, m = marshal.loads(p.read_bytes())
    except (OSError, ValueError, EOFError, TypeError):
        return None
    if stamp != _stamp(src[0]):
        p.unlink(missing_ok=True)
        return None
    _touch(src[0])
    return m


def keep_mesh(src, light, m):
    """Keep the mesh of a big file's solid (more than MIN_FACES faces)."""
    stamp = _stamp(src[0])
    if stamp is None or len(m.get("faces") or ()) <= MIN_FACES:
        return False
    try:
        _write(DIR / f"{_key(src, light)}.mesh", marshal.dumps((stamp, m)))
    except (OSError, ValueError):  # (ValueError: something marshal cannot keep)
        return False
    _prune()
    return True


def drop(sha):
    """Remove all of a file's entries."""
    for p in DIR.glob(f"{sha}.*"):
        p.unlink(missing_ok=True)


def _touch(sha):
    try:
        os.utime(DIR / f"{sha}.json")
    except OSError:
        pass


def _prune():
    """The folder kept under LIMIT_MB: the files used least lately (their .json's time) go first, whole."""
    try:
        files = [(p, p.stat()) for p in DIR.iterdir() if p.is_file()]
    except OSError:
        return
    total = sum(s.st_size for _, s in files)
    if total <= LIMIT_MB * (1 << 20):
        return
    by_sha = {}
    for p, s in files:
        sha = p.name.split(".", 1)[0]
        e = by_sha.setdefault(sha, [0, 0])
        e[0] += s.st_size
        if p.suffix == ".json":
            e[1] = s.st_mtime
    for sha, (size, _) in sorted(by_sha.items(), key=lambda kv: kv[1][1]):
        if total <= LIMIT_MB * (1 << 20):
            break
        drop(sha)
        total -= size
