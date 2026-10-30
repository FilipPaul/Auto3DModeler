"""Built parts kept on disk in the data folder (cache/parts), by what they are made of, so a server start does not
build them again: the big benchmark's 160-hole base took 4.7 s in every kernel process that needed it after each
start — read from here it takes a few ms, in any process (they share it through the disk). Nothing in it is needed:
a missing, old or damaged entry is built again.

An entry's key is a hash of the part's steps (doc._key: the features with their sizes as sent — parameters already
put in — and an imported file's blob sha) and of the stamp of what built it: this cache's VERSION, the code of the
whole modeler (every auto3d/modeler/*.py: a changed step, a new version of the app) and the OpenCASCADE package's
version. So an edited step, another file, other code is another key; old entries are not used again and leave as
the least used ones.

  <key>.state         the evaluated doc.State and the steps' status, pickled, its shapes as indices into …
  <key>.brep          … its shapes, all in one binary B-rep (kernel.write_shapes): the body and its named faces stay
                      the same faces (the names are the very ones built: F2:side:l1 …), sketch faces, tools, refs
  <key>.<lod>.mesh    kernel.tessellate's answer for the body (the browser's mesh: 0.8 s for the base)
  p<key>.pair         a pair of placed parts checked for collisions (kernel.interference): the overlap's volume, and
  p<key>.brep         the overlaps as shapes in the first part's frame when they overlap

It is used in the kernel processes (worker._main turns it ON; A3D_PARTCACHE=0: not), not where doc is called directly
(the tests: a step mocked to fail must not be read back built). Only parts that took MIN_SECONDS to build are kept, and none bigger than kernel.HEAVY_FACES faces (an imported board
is kept by filecache already); the folder is kept under LIMIT_MB, the entries used least lately dropped first.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import io
import marshal
import os
import pickle
from pathlib import Path

VERSION = 1
ON = False  # (the kernel processes: worker._main)
DIR = Path(os.environ.get("A3D_DATA") or Path(__file__).resolve().parents[2] / "data") / "cache" / "parts"
LIMIT_MB = 500
MIN_SECONDS = 0.05  # a part built quicker than this is built again (a file would not be quicker)

_stamp = None
_since = None  # bytes written since the folder's size was last looked at (None: not yet in this process)


def stamp():
    """What built the entries: VERSION, the modeler's code, the kernel's version — changed, and every key is new."""
    global _stamp
    if _stamp is None:
        here = Path(__file__).parent
        h = hashlib.sha1(f"{VERSION}".encode())
        for p in sorted(here.glob("*.py")):
            h.update(p.name.encode() + p.read_bytes())
        try:
            h.update(importlib.metadata.version("cadquery-ocp-novtk").encode())
        except importlib.metadata.PackageNotFoundError:
            pass
        _stamp = h.hexdigest()[:16]
    return _stamp


def key(steps_key):
    """The entry's key of a part's steps (doc._key of them)."""
    return hashlib.sha1(f"{stamp()}:{steps_key}".encode()).hexdigest()


# ------------------------------------------------------------------ shapes inside plain data
class _Pickler(pickle.Pickler):
    def __init__(self, f, shapes):
        super().__init__(f, protocol=pickle.HIGHEST_PROTOCOL)
        self.shapes, self.seen = shapes, {}

    def persistent_id(self, obj):
        from . import kernel as K
        if not K.is_shape(obj):
            return None
        i = self.seen.get(id(obj))
        if i is None:
            i = self.seen[id(obj)] = len(self.shapes)
            self.shapes.append(obj)
        return i


class _Unpickler(pickle.Unpickler):
    def __init__(self, f, shapes):
        super().__init__(f)
        self.shapes = shapes

    def persistent_load(self, pid):
        return self.shapes[pid]


def _dump(obj, base):
    """obj (plain data and shapes) to base.brep + the bytes of the rest; the brep is written first."""
    from . import kernel as K
    shapes, buf = [], io.BytesIO()
    _Pickler(buf, shapes).dump(obj)
    kinds = []
    if shapes:
        tmp = base.with_name(f"{base.name}.brep.{os.getpid()}.part")
        kinds = K.write_shapes(shapes, tmp)
        os.replace(tmp, base.with_name(base.name + ".brep"))
    return pickle.dumps((kinds, buf.getvalue()), protocol=pickle.HIGHEST_PROTOCOL)


def _load(data, base):
    from . import kernel as K
    kinds, rest = pickle.loads(data)
    shapes = K.read_shapes(base.with_name(base.name + ".brep"), kinds) if kinds else []
    return _Unpickler(io.BytesIO(rest), shapes).load()


def _write(path, data: bytes):
    global _since
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.part")  # (several kernel processes may write the same entry)
    tmp.write_bytes(data)
    os.replace(tmp, path)
    if _since is not None:
        _since += len(data)


def _read(path):
    try:
        data = path.read_bytes()
    except OSError:
        return None
    try:
        os.utime(path)  # (used now: the last to go)
    except OSError:
        pass
    return data


# ------------------------------------------------------------------ built parts
def state(k):
    """The kept (doc.State, status) of entry k, or None (not kept, or damaged: removed)."""
    data = _read(DIR / f"{k}.state") if ON else None
    if data is None:
        return None
    try:
        return _load(data, DIR / k)
    except Exception:  # noqa: BLE001 — damaged or half-removed: built again
        drop(k)
        return None


def keep_state(k, obj):
    """Keep (doc.State, status) as entry k. Never fails: something that cannot be kept (a full disk) means no cache."""
    if not ON:
        return False
    try:
        DIR.mkdir(parents=True, exist_ok=True)
        _write(DIR / f"{k}.state", _dump(obj, DIR / k))
    except Exception:  # noqa: BLE001 — (OSError, a shape pickle cannot keep …)
        return False
    _prune()
    return True


def mesh(k, light=False):
    """The kept mesh (kernel.tessellate's answer) of entry k's body, or None."""
    data = _read(DIR / f"{k}.{'light' if light else 'full'}.mesh") if ON else None
    try:
        return marshal.loads(data) if data is not None else None
    except (ValueError, EOFError, TypeError):
        return None


def keep_mesh(k, light, m):
    if not ON:
        return False
    try:
        _write(DIR / f"{k}.{'light' if light else 'full'}.mesh", marshal.dumps(m))
    except (OSError, ValueError):  # (ValueError: something marshal cannot keep)
        return False
    _prune()
    return True


# ------------------------------------------------------------------ pairs of parts checked for collisions
def _pair_key(ck):
    return "p" + hashlib.sha1(f"{stamp()}:{ck!r}".encode()).hexdigest()


def pair(ck):
    """A pair of placed parts checked before (kernel._pair_key ck) -> (volume, [overlaps in the first's frame]), or
    None."""
    if not ON:
        return None
    k = _pair_key(ck)
    data = _read(DIR / f"{k}.pair")
    if data is None:
        return None
    try:
        return _load(data, DIR / k)
    except Exception:  # noqa: BLE001
        drop(k)
        return None


def keep_pair(ck, v, overlaps):
    if not ON:
        return False
    k = _pair_key(ck)
    try:
        DIR.mkdir(parents=True, exist_ok=True)
        _write(DIR / f"{k}.pair", _dump((v, list(overlaps)), DIR / k))
    except Exception:  # noqa: BLE001
        return False
    _prune()
    return True


# ------------------------------------------------------------------ the folder
def drop(k):
    """Remove all of an entry's files."""
    for p in DIR.glob(f"{k}.*"):
        try:
            p.unlink()
        except OSError:
            pass


def clear():
    """Remove every entry."""
    for p in DIR.glob("*"):
        try:
            p.unlink()
        except OSError:
            pass


def _prune():
    """The folder kept under LIMIT_MB: the entries used least lately (their newest file) go first, whole. The folder
    is looked at once a process has written a twentieth of the limit since (and on its first write)."""
    global _since
    limit = LIMIT_MB * (1 << 20)
    if _since is not None and _since < limit / 20:
        return
    _since = 0
    try:
        files = [(e.name, e.stat()) for e in os.scandir(DIR) if e.is_file()]
    except OSError:
        return
    total = sum(s.st_size for _, s in files)
    if total <= limit:
        return
    entries = {}
    for name, s in files:
        e = entries.setdefault(name.split(".", 1)[0], [0, 0])
        e[0] += s.st_size
        e[1] = max(e[1], s.st_mtime_ns)
    for k, (size, _) in sorted(entries.items(), key=lambda kv: kv[1][1]):
        if total <= limit:
            break
        drop(k)
        total -= size
