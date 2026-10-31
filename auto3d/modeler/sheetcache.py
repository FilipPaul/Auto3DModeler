"""Drawings made for a drawing set kept on disk in the data folder (cache/sheets), by what they were made from, so the
next "PDF of all sheets" only makes the ones it does not have yet — a set cancelled part-way (✕ Cancel, "Save the
finished drawings?" Yes) goes on where it stopped, also after a reload or a server start. Nothing in it is needed: a
missing, old or damaged entry is made again.

  <key>.json   the answer of /api/sheet/build or /api/sheet/assembly (geometry, layout, dims …), as sent

An entry's key is a hash of the request as it reaches the server (the part's steps with their sizes, an imported
file's blob sha, the preset, paper, scale, frame …; an assembly's placed parts) and of the code that drew it (this
cache's VERSION and partcache.stamp(): every auto3d/modeler/*.py and the kernel's version). So an edited part, another
paper or a new version of the app is another key: made again; old entries leave as the least used ones. Used only
when the page asks for it (the request's "cache"): a sheet open in the editor is made as before. The folder is kept
under LIMIT_MB, the entries used least lately dropped first.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from . import partcache

VERSION = 1
DIR = Path(os.environ.get("A3D_DATA") or Path(__file__).resolve().parents[2] / "data") / "cache" / "sheets"  # (server.py: its DATA)
LIMIT_MB = 300
SKIP = ("rid", "cache")  # (not what the drawing is made from)

_since = None  # bytes written since the folder's size was last looked at (None: not yet in this process)


def key(op, body):
    """The entry's key of a request (op: "sheet" | "assembly", body: its JSON)."""
    what = json.dumps({k: v for k, v in body.items() if k not in SKIP}, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha1(f"{VERSION}:{partcache.stamp()}:{op}:{what}".encode()).hexdigest()


def get(k):
    """The kept answer of key k, or None (not kept, or damaged: removed)."""
    p = DIR / f"{k}.json"
    try:
        data = p.read_bytes()
    except OSError:
        return None
    try:
        os.utime(p)  # (used now: the last to go)
    except OSError:
        pass
    try:
        return json.loads(data)
    except ValueError:
        drop([k])
        return None


def keep(k, data):
    """Keep the answer data as key k. Never fails: something that cannot be kept (a full disk) means no cache."""
    global _since
    try:
        raw = json.dumps(data, separators=(",", ":")).encode()
        DIR.mkdir(parents=True, exist_ok=True)
        tmp = DIR / f"{k}.json.{os.getpid()}.part"
        tmp.write_bytes(raw)
        os.replace(tmp, DIR / f"{k}.json")
    except (OSError, TypeError, ValueError):
        return False
    if _since is not None:
        _since += len(raw)
    _prune()
    return True


def drop(keys):
    """Remove these entries (the page's "No, discard": the drawings this run made) -> how many were there."""
    n = 0
    for k in keys:
        if not isinstance(k, str) or not re.fullmatch(r"[0-9a-f]{40}", k):
            continue  # (only a key: never a path)
        try:
            (DIR / f"{k}.json").unlink()
            n += 1
        except OSError:
            pass
    return n


def _prune():
    """The folder kept under LIMIT_MB: the entries used least lately go first. Looked at once a twentieth of the
    limit was written since (and on the first write of the process)."""
    global _since
    limit = LIMIT_MB * (1 << 20)
    if _since is not None and _since < limit / 20:
        return
    _since = 0
    try:
        files = [(e.path, e.stat()) for e in os.scandir(DIR) if e.is_file() and e.name.endswith(".json")]
    except OSError:
        return
    total = sum(s.st_size for _, s in files)
    for path, s in sorted(files, key=lambda f: f[1].st_mtime_ns):
        if total <= limit:
            break
        try:
            os.unlink(path)
            total -= s.st_size
        except OSError:
            pass
