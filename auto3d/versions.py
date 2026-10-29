"""🕘 Versions of a project: its states kept on the server to look at, compare and restore — without git, so it works
in the built app too. A content-addressed store per project in the data folder (`<data>/versions/<project id>/`):

  objects/ab/cdef…   each part's JSON (and the project-level bits, a thumbnail) zlib-compressed, stored once under the
                     SHA-256 of its bytes — a part that did not change costs nothing in the next version
  versions/<id>.json a version: a small manifest {id, parent, variant, time, label, auto, parts: {part id: hash},
                     project: hash (name, parameters, order …), thumb: hash, names, kinds, changed, volumes, note}
  state.json         the variants (branches: "main" and the user's, each with its head) and the one on screen

Imported files are not copied: the parts name them by their hash in the blob store (auto3d/modeler/blobs.py).
Automatic versions are thinned (all of the last 24 h, one an hour for a week, one a day after that); named versions,
the variants' heads and bases are kept. Objects no manifest uses are deleted (gc). Everything is written whole (a temp
file, then replace — autosave's retries on a Windows sharing violation).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import threading
import time
import zlib
from pathlib import Path

from auto3d.autosave import _pause

AUTO_GAP = 180          # s: at most one automatic version per this while editing
DAY, WEEK = 86400, 7 * 86400
MAX_LABEL = 120
MAX_THUMB = 200_000     # bytes of a thumbnail JPEG
_PID = re.compile(r"^[A-Za-z0-9-]{8,64}$")
_VID = re.compile(r"^[0-9]{8}-[0-9]{6}-[0-9a-f]{6}(-[0-9]+)?$")
_VAR = re.compile(r"^(main|v-[0-9a-f]{8})$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_LOCKS = {}
_LOCKS_LOCK = threading.Lock()


class VersionError(Exception):
    pass


def _lock(pid):
    with _LOCKS_LOCK:
        return _LOCKS.setdefault(pid, threading.Lock())


def _folder(root, pid) -> Path:
    if not isinstance(pid, str) or not _PID.match(pid):
        raise VersionError("No such project.")
    return Path(root) / pid


def _vid(vid) -> str:
    if not isinstance(vid, str) or not _VID.match(vid):
        raise VersionError("No such version.")
    return vid


def _var(var) -> str:
    if not isinstance(var, str) or not _VAR.match(var):
        raise VersionError("No such variant.")
    return var


def _sha(sha) -> str:
    if not isinstance(sha, str) or not _SHA.match(sha):
        raise VersionError("No such object.")
    return sha


def _write(path: Path, data: bytes, tries=40):
    """Whole or not at all: a temp file of this thread, then replace (a reader holding it on Windows: tried again)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}-{threading.get_ident()}.tmp")
    tmp.write_bytes(data)
    try:
        for i in range(tries):
            try:
                tmp.replace(path)
                return
            except PermissionError:
                if i == tries - 1:
                    raise
                time.sleep(_pause(i))
    finally:
        tmp.unlink(missing_ok=True)


def _read(path: Path, tries=40) -> bytes:
    for i in range(tries):
        try:
            return path.read_bytes()
        except PermissionError:
            if i == tries - 1:
                raise
            time.sleep(_pause(i))


def _canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


# ---------------------------------------------------------------------------------------------- objects
def _obj_path(folder: Path, sha: str) -> Path:
    return folder / "objects" / sha[:2] / sha[2:]


def _put(folder: Path, data: bytes) -> str:
    sha = hashlib.sha256(data).hexdigest()
    p = _obj_path(folder, sha)
    if not p.exists():
        _write(p, zlib.compress(data, 9))
    return sha


def _get(folder: Path, sha: str) -> bytes:
    p = _obj_path(folder, _sha(sha))
    if not p.exists():
        raise VersionError("A part of this version is missing from the store.")
    return zlib.decompress(_read(p))


def _get_json(folder: Path, sha: str):
    return json.loads(_get(folder, sha).decode("utf-8"))


def _objects(folder: Path):
    """Every object in the store: (sha, path)."""
    base = folder / "objects"
    if not base.exists():
        return
    for d in base.iterdir():
        if not d.is_dir() or not re.fullmatch(r"[0-9a-f]{2}", d.name):
            continue
        for f in d.iterdir():
            sha = d.name + f.name
            if _SHA.match(sha):
                yield sha, f


# ---------------------------------------------------------------------------------------------- the project split
def _split(project: dict):
    """The project file -> (its project-level bits with the parts' order, [(part id, part)])."""
    if not isinstance(project, dict) or not isinstance(project.get("parts"), list) or not project["parts"]:
        raise VersionError("A version needs the project's parts.")
    parts, seen = [], set()
    for p in project["parts"]:
        if not isinstance(p, dict) or not isinstance(p.get("id"), str) or not p["id"] or p["id"] in seen:
            raise VersionError("A version needs the project's parts.")
        seen.add(p["id"])
        parts.append((p["id"], p))
    top = {k: v for k, v in project.items() if k not in ("parts", "versions", "blobs")}
    top["order"] = [pid for pid, _ in parts]
    return top, parts


def _project(folder: Path, m: dict) -> dict:
    """A version's manifest -> its project file."""
    top = _get_json(folder, m["project"])
    order = top.pop("order", list(m["parts"]))
    return {**top, "parts": [_get_json(folder, m["parts"][pid]) for pid in order if pid in m["parts"]]}


# ---------------------------------------------------------------------------------------------- manifests, state
def _manifest(folder: Path, vid: str) -> dict:
    p = folder / "versions" / f"{_vid(vid)}.json"
    if not p.exists():
        raise VersionError("No such version.")
    return json.loads(_read(p))


def _manifests(folder: Path) -> list:
    """Every version, the newest first."""
    out = []
    base = folder / "versions"
    if base.exists():
        for p in base.glob("*.json"):
            if not _VID.match(p.stem):
                continue
            try:
                out.append(json.loads(_read(p)))
            except (OSError, ValueError):
                continue
    return sorted(out, key=lambda m: (m.get("time", 0), m.get("id", "")), reverse=True)


def _state(folder: Path) -> dict:
    p = folder / "state.json"
    st = None
    if p.exists():
        try:
            st = json.loads(_read(p))
        except (OSError, ValueError):
            st = None
    if not isinstance(st, dict) or not isinstance(st.get("variants"), list):
        st = {"current": "main", "variants": []}
    if not any(v.get("id") == "main" for v in st["variants"]):
        st["variants"].insert(0, {"id": "main", "name": "", "head": None, "base": None, "time": time.time()})
    if not any(v.get("id") == st.get("current") for v in st["variants"]):
        st["current"] = "main"
    return st


def _put_state(folder: Path, st: dict):
    _write(folder / "state.json", json.dumps(st).encode("utf-8"))


def _variant(st: dict, var: str) -> dict:
    v = next((x for x in st["variants"] if x["id"] == var), None)
    if not v:
        raise VersionError("No such variant.")
    return v


def _new_vid(folder: Path, now: float, digest: str) -> str:
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now))
    vid, n = f"{stamp}-{digest[:6]}", 1
    while (folder / "versions" / f"{vid}.json").exists():
        n += 1
        vid = f"{stamp}-{digest[:6]}-{n}"
    return vid


# ---------------------------------------------------------------------------------------------- saving
def _record(folder: Path, st: dict, project: dict, *, label="", auto=False, thumb=None, volumes=None, note=None,
            now=None, force=False) -> dict:
    """A new version of the project in the variant on screen (the lock held) -> its manifest; {…head, same: True}
    when nothing changed (an automatic one also when the last version is younger than AUTO_GAP)."""
    now = time.time() if now is None else float(now)
    label = str(label or "").strip()[:MAX_LABEL]
    if thumb and (not isinstance(thumb, (bytes, bytearray)) or len(thumb) > MAX_THUMB or bytes(thumb[:2]) != b"\xff\xd8"):
        raise VersionError("The thumbnail is not a small JPEG picture.")
    top, parts = _split(project)
    hashes = {pid: hashlib.sha256(_canon(p)).hexdigest() for pid, p in parts}
    top_hash = hashlib.sha256(_canon(top)).hexdigest()
    var = _variant(st, st["current"])
    head = _manifest(folder, var["head"]) if var.get("head") else None
    if head and not label and not note:
        same = head["parts"] == hashes and head["project"] == top_hash
        if same or (auto and not force and now - head.get("time", 0) < AUTO_GAP and set(head["parts"]) == set(hashes)):
            return {**head, "same": True}
    for pid, p in parts:
        _put(folder, _canon(p))
    _put(folder, _canon(top))
    th = None
    if thumb:
        th = _put(folder, bytes(thumb))
    old = head["parts"] if head else {}
    changed = [p.get("name") or pid for pid, p in parts if old.get(pid) != hashes[pid]]
    changed += [(head.get("names") or {}).get(pid) or pid for pid in old if pid not in hashes]
    vols = {pid: v for pid, v in ((head or {}).get("volumes") or {}).items() if old.get(pid) == hashes.get(pid)}
    vols.update({pid: float(v) for pid, v in (volumes or {}).items() if pid in hashes and isinstance(v, (int, float)) and not isinstance(v, bool)})
    digest = hashlib.sha256(_canon([hashes, top_hash, now])).hexdigest()
    m = {"id": _new_vid(folder, now, digest), "parent": head["id"] if head else None,
         "variant": var["id"], "time": now, "label": label, "auto": bool(auto) and not label,
         "parts": hashes, "project": top_hash, "thumb": th,
         "names": {pid: p.get("name") or pid for pid, p in parts}, "kinds": {pid: p.get("kind") or "" for pid, p in parts},
         "changed": changed if head else [], "volumes": vols, "name": project.get("project_name") or ""}
    if note:
        m["note"] = note
    _write(folder / "versions" / f"{m['id']}.json", json.dumps(m).encode("utf-8"))
    var["head"] = m["id"]
    _put_state(folder, st)
    return m


def save(root, pid, project, label="", auto=False, thumb=None, volumes=None, force=False, now=None) -> dict:
    """Keep the project as a version of the variant on screen -> its manifest (same: True when not kept: nothing
    changed, or an automatic one too soon after the last). label: a named version (never thinned)."""
    folder = _folder(root, pid)
    with _lock(pid):
        st = _state(folder)
        m = _record(folder, st, project, label=label, auto=auto, thumb=thumb, volumes=volumes, now=now, force=force)
        if auto and not m.get("same"):
            _thin(folder, st, now)
            _gc(folder)
    return m


def versions(root, pid, variant=None, every=False) -> dict:
    """The variants and the timeline of one (default: the one on screen), the newest first; base: the version (of
    another variant) it was made from. every: also `all`, every variant's versions (the newest first: the graph)."""
    folder = _folder(root, pid)
    st = _state(folder)
    var = _variant(st, _var(variant) if variant else st["current"])
    every_m = _manifests(folder)
    out = [m for m in every_m if m.get("variant") == var["id"]]
    count = {}
    for m in every_m:
        count[m.get("variant")] = count.get(m.get("variant"), 0) + 1
    base = None
    if var.get("base"):
        try:
            base = _manifest(folder, var["base"])
        except VersionError:
            base = None
    res = {"current": st["current"], "variant": var["id"], "versions": out, "base": base,
           "variants": [{**v, "count": count.get(v["id"], 0)} for v in st["variants"]]}
    if every:
        res["all"] = every_m
    return res


def get(root, pid, vid) -> dict:
    """{version: its manifest, project: the project file as it was}."""
    folder = _folder(root, pid)
    m = _manifest(folder, vid)
    return {"version": m, "project": _project(folder, m)}


def thumb(root, pid, vid) -> bytes:
    folder = _folder(root, pid)
    m = _manifest(folder, vid)
    if not m.get("thumb"):
        raise VersionError("This version has no picture.")
    return _get(folder, m["thumb"])


def restore(root, pid, vid, current=None, thumb=None, volumes=None, now=None) -> dict:
    """Back to version vid: the project as it is now kept first (a version "before restoring"), then the old one as a
    new version on top (the timeline keeps everything; restoring the first one undoes it). -> {version, before,
    project}."""
    folder = _folder(root, pid)
    now = time.time() if now is None else float(now)
    with _lock(pid):
        st = _state(folder)
        old = _manifest(folder, vid)
        proj = _project(folder, old)
        before = None
        if current is not None:
            before = _record(folder, st, current, thumb=thumb, volumes=volumes, note={"what": "before-restore"}, now=now)
        m = _record(folder, st, proj, note={"what": "restored", "from": old["id"], "label": old.get("label") or "", "time": old.get("time")},
                    now=now + 0.001, volumes=old.get("volumes"))
        if old.get("thumb") and not m.get("thumb"):
            m["thumb"] = old["thumb"]
            _write(folder / "versions" / f"{m['id']}.json", json.dumps(m).encode("utf-8"))
    return {"version": m, "before": before, "project": proj}


# ---------------------------------------------------------------------------------------------- variants
def create_variant(root, pid, base, name, now=None) -> dict:
    """A variant (a branch) from version `base`, named `name`; it becomes the one on screen -> {variant, project}."""
    folder = _folder(root, pid)
    name = str(name or "").strip()[:60]
    if not name:
        raise VersionError("A variant needs a name.")
    with _lock(pid):
        st = _state(folder)
        m = _manifest(folder, base)
        if any((v.get("name") or "").lower() == name.lower() for v in st["variants"]):
            raise VersionError("A variant of that name is already there.")
        vid = "v-" + hashlib.sha256(f"{name}{time.time()}{os.getpid()}".encode()).hexdigest()[:8]
        var = {"id": vid, "name": name, "head": m["id"], "base": m["id"], "time": time.time() if now is None else now}
        st["variants"].append(var)
        st["current"] = vid
        _put_state(folder, st)
        return {"variant": var, "project": _project(folder, m), "variants": st["variants"]}


def switch_variant(root, pid, var) -> dict:
    """The variant `var` on screen -> {variant, version: its head, project: the head's project}."""
    folder = _folder(root, pid)
    with _lock(pid):
        st = _state(folder)
        v = _variant(st, _var(var))
        st["current"] = v["id"]
        _put_state(folder, st)
        if not v.get("head"):
            return {"variant": v, "version": None, "project": None}
        m = _manifest(folder, v["head"])
        return {"variant": v, "version": m, "project": _project(folder, m)}


def rename_variant(root, pid, var, name) -> dict:
    folder = _folder(root, pid)
    name = str(name or "").strip()[:60]
    with _lock(pid):
        st = _state(folder)
        v = _variant(st, _var(var))
        if v["id"] == "main" and not name:
            v["name"] = ""
        elif not name:
            raise VersionError("A variant needs a name.")
        elif any(x is not v and (x.get("name") or "").lower() == name.lower() for x in st["variants"]):
            raise VersionError("A variant of that name is already there.")
        else:
            v["name"] = name
        _put_state(folder, st)
        return v


def delete_variant(root, pid, var) -> dict:
    """Variant `var` and its versions deleted (not the main one; not one another variant was made from), the objects
    nobody uses any more too; the one on screen -> main. -> {deleted, versions: n, objects: n, current, variants,
    project: main's head's project when the deleted one was on screen}."""
    folder = _folder(root, pid)
    with _lock(pid):
        st = _state(folder)
        v = _variant(st, _var(var))
        if v["id"] == "main":
            raise VersionError("The main variant cannot be deleted.")
        mine = [m for m in _manifests(folder) if m.get("variant") == v["id"]]
        ids = {m["id"] for m in mine}
        if any(x is not v and x.get("base") in ids for x in st["variants"]):
            raise VersionError("Another variant was made from this one — delete that one first.")
        st["variants"].remove(v)
        on_screen = st["current"] == v["id"]
        if on_screen:
            st["current"] = "main"
        _put_state(folder, st)  # (first: a crash after it leaves only unused files, which the next gc takes)
        for m in mine:
            (folder / "versions" / f"{m['id']}.json").unlink(missing_ok=True)
        out = {"deleted": v["id"], "versions": len(mine), "objects": _gc(folder), "current": st["current"],
               "variants": st["variants"]}
        if on_screen:
            head = _variant(st, "main").get("head")
            out["project"] = _project(folder, _manifest(folder, head)) if head else None
        return out


def take_part(root, pid, var, part) -> dict:
    """One part as it is in the head of variant `var` -> {part: its JSON, version: the head} (the page puts it into the
    project on screen; the next version keeps it)."""
    folder = _folder(root, pid)
    st = _state(folder)
    v = _variant(st, _var(var))
    if not v.get("head"):
        raise VersionError("That variant has no version yet.")
    m = _manifest(folder, v["head"])
    if not isinstance(part, str) or part not in m["parts"]:
        raise VersionError("That variant has no such part.")
    return {"part": _get_json(folder, m["parts"][part]), "version": m}


# ---------------------------------------------------------------------------------------------- compare
_ANGLE = re.compile(r"(angle|draft|deg|taper|twist|rot)", re.I)
_COUNT = {"n", "count", "copies", "nx", "ny", "teeth", "segments"}
_SKIP_KEYS = {"id", "name", "expr", "rd", "place"}


def _unit(key):
    return "°" if _ANGLE.search(key) else "" if key in _COUNT else "mm"


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _step_changes(f: dict, g: dict) -> list:
    """What changed in one step: [{key, before, after, unit?}] — the numbers and words; a sketch's locked sizes by
    their id; other changes as {key, changed: True}."""
    out = []
    if (f.get("name") or "") != (g.get("name") or ""):
        out.append({"key": "name", "before": f.get("name") or "", "after": g.get("name") or ""})
    for k in sorted(set(f) | set(g)):
        if k in _SKIP_KEYS:
            continue
        a, b = f.get(k), g.get(k)
        if a == b:
            continue
        if k == "dims" and isinstance(a, list) and isinstance(b, list):
            da = {x.get("id"): x for x in a if isinstance(x, dict)}
            db = {x.get("id"): x for x in b if isinstance(x, dict)}
            for i in [i for i in da if i in db] + [i for i in db if i not in da]:
                va, vb = (da.get(i) or {}).get("v"), (db.get(i) or {}).get("v")
                if va != vb and (_num(va) or _num(vb)):
                    t = (db.get(i) or da.get(i)).get("t") or ""
                    out.append({"key": f"dim {i}", "before": va, "after": vb, "unit": "°" if t in ("angle", "ang") else "mm"})
            continue
        if (a is None or _num(a)) and (b is None or _num(b)):
            out.append({"key": k, "before": a, "after": b, "unit": _unit(k)})
        elif isinstance(a, (str, bool, type(None))) and isinstance(b, (str, bool, type(None))):
            out.append({"key": k, "before": a, "after": b})
        else:
            out.append({"key": k, "changed": True})
    return out


def _part_data(p: dict):
    kind = p.get("kind")
    return p.get("classic" if kind == "classic" else kind) or {}


def _part_diff(a: dict, b: dict, names=None) -> list:
    """The steps of a 3D model part: added / removed / changed (with their values); an assembly's placed parts (named
    by their part: names {part id: name})."""
    if a.get("kind") == "model" and b.get("kind") == "model":
        fa = [f for f in _part_data(a).get("features") or [] if isinstance(f, dict)]
        fb = [f for f in _part_data(b).get("features") or [] if isinstance(f, dict)]
        ia, ib = {f.get("id"): f for f in fa}, {f.get("id"): f for f in fb}
        out = [{"step": f.get("name") or f.get("id"), "id": f.get("id"), "type": f.get("type"), "status": "added"} for f in fb if f.get("id") not in ia]
        out += [{"step": f.get("name") or f.get("id"), "id": f.get("id"), "type": f.get("type"), "status": "removed"} for f in fa if f.get("id") not in ib]
        for f in fa:
            g = ib.get(f.get("id"))
            if g is not None and g != f:
                ch = _step_changes(f, g)
                if ch:
                    out.append({"step": g.get("name") or g.get("id"), "id": g.get("id"), "type": g.get("type"), "status": "changed", "values": ch})
        return out
    if a.get("kind") == "assembly" and b.get("kind") == "assembly":
        ia = {x.get("id"): x for x in _part_data(a).get("instances") or [] if isinstance(x, dict)}
        ib = {x.get("id"): x for x in _part_data(b).get("instances") or [] if isinstance(x, dict)}
        names = names or {}

        def label(i, x):
            return x.get("name") or (f"{names[x['part']]} ({i})" if x.get("part") in names else i)

        out = [{"step": label(i, x), "id": i, "type": "instance", "status": "added"} for i, x in ib.items() if i not in ia]
        out += [{"step": label(i, x), "id": i, "type": "instance", "status": "removed"} for i, x in ia.items() if i not in ib]
        out += [{"step": label(i, x), "id": i, "type": "instance", "status": "changed", "values": []}
                for i, x in ia.items() if i in ib and ib[i] != x]
        return out
    return []


def diff(a: dict, b: dict, vol_a=None, vol_b=None) -> dict:
    """Two project files (a: before, b: after) -> {parts: [{id, name, kind, status: added / removed / changed, steps,
    volume: [before, after]}], project: [{what, before, after}]}. vol_*: {part id: mm³} where known."""
    ta, pa = _split(a)
    tb, pb = _split(b)
    da, db = dict(pa), dict(pb)
    vol_a, vol_b = vol_a or {}, vol_b or {}
    names = {pid: x.get("name") or pid for pid, x in pa + pb}
    parts = []
    for pid, p in pb:
        q = da.get(pid)
        if q is None:
            parts.append({"id": pid, "name": p.get("name") or pid, "kind": p.get("kind"), "status": "added", "steps": [],
                          "volume": [None, vol_b.get(pid)]})
        elif _canon(q) != _canon(p):
            ent = {"id": pid, "name": p.get("name") or pid, "kind": p.get("kind"), "status": "changed", "steps": _part_diff(q, p, names),
                   "volume": [vol_a.get(pid), vol_b.get(pid)]}
            if (q.get("name") or "") != (p.get("name") or ""):
                ent["renamed"] = [q.get("name") or "", p.get("name") or ""]
            parts.append(ent)
    for pid, q in pa:
        if pid not in db:
            parts.append({"id": pid, "name": q.get("name") or pid, "kind": q.get("kind"), "status": "removed", "steps": [],
                          "volume": [vol_a.get(pid), None]})
    proj = []
    if (ta.get("project_name") or "") != (tb.get("project_name") or ""):
        proj.append({"what": "name", "before": ta.get("project_name") or "", "after": tb.get("project_name") or ""})
    pa_, pb_ = ({x.get("name"): x.get("expr") for x in t.get("parameters") or [] if isinstance(x, dict)} for t in (ta, tb))
    for n in list(pa_) + [n for n in pb_ if n not in pa_]:
        if pa_.get(n) != pb_.get(n):
            proj.append({"what": "parameter", "name": n, "before": pa_.get(n), "after": pb_.get(n)})
    if [x for x in ta["order"] if x in db] != [x for x in tb["order"] if x in da]:
        proj.append({"what": "order"})
    return {"parts": parts, "project": proj}


def compare(root, pid, a, b="current", current=None, volumes=None) -> dict:
    """Version a against version b (or "current": the project on screen, given) -> diff, with both versions' times."""
    folder = _folder(root, pid)

    def side(x):
        if x == "current":
            if current is None:
                raise VersionError("Compare with the current project: it was not sent.")
            return current, volumes or {}, None
        m = _manifest(folder, x)
        return _project(folder, m), m.get("volumes") or {}, m

    (pa, va, ma), (pb, vb, mb) = side(a), side(b)
    out = diff(pa, pb, va, vb)
    out["a"] = {"id": a, "time": ma and ma["time"], "label": ma and ma.get("label")}
    out["b"] = {"id": b, "time": mb and mb["time"], "label": mb and mb.get("label")}
    return out


# ---------------------------------------------------------------------------------------------- thinning, gc
def _protected(st: dict) -> set:
    return {v.get(k) for v in st["variants"] for k in ("head", "base") if v.get(k)}


def _thin(folder: Path, st: dict, now=None) -> list:
    """Automatic versions thinned: all of the last 24 h, the newest of each hour for a week, of each day after that
    (per variant). Named ones, the variants' heads and bases stay. -> the ids removed."""
    now = time.time() if now is None else float(now)
    keep_ids, seen, gone = _protected(st), set(), []
    for m in _manifests(folder):  # (the newest first: each bucket keeps its newest)
        if not m.get("auto") or m["id"] in keep_ids:
            continue
        age = now - m.get("time", 0)
        if age < DAY:
            continue
        bucket = (m.get("variant"), "h", int(m["time"] // 3600)) if age < WEEK else (m.get("variant"), "d", time.strftime("%Y%m%d", time.localtime(m["time"])))
        if bucket in seen:
            (folder / "versions" / f"{m['id']}.json").unlink(missing_ok=True)
            gone.append(m["id"])
        else:
            seen.add(bucket)
    return gone


def _gc(folder: Path) -> int:
    """Objects no version uses deleted -> how many."""
    used = set()
    for m in _manifests(folder):
        used.update(m.get("parts", {}).values())
        used.update(x for x in (m.get("project"), m.get("thumb")) if x)
    n = 0
    for sha, p in list(_objects(folder)):
        if sha not in used:
            p.unlink(missing_ok=True)
            n += 1
    return n


def thin(root, pid, now=None) -> dict:
    """Thin the automatic versions and drop the objects nobody uses -> {removed: [ids], objects: n deleted}."""
    folder = _folder(root, pid)
    with _lock(pid):
        st = _state(folder)
        gone = _thin(folder, st, now)
        return {"removed": gone, "objects": _gc(folder)}


def size(root, pid) -> dict:
    """The store's size on disk: {bytes, objects, versions}."""
    folder = _folder(root, pid)
    files = [p for p in folder.rglob("*") if p.is_file()] if folder.exists() else []
    return {"bytes": sum(p.stat().st_size for p in files), "objects": sum(1 for _ in _objects(folder)),
            "versions": len(list((folder / "versions").glob("*.json"))) if (folder / "versions").exists() else 0}


def drop(root, pid):
    """The project's whole store deleted (the project forgotten)."""
    folder = _folder(root, pid)
    with _lock(pid):
        shutil.rmtree(folder, ignore_errors=True)


# ---------------------------------------------------------------------------------------------- in the project file
def bundle(root, pid) -> dict | None:
    """The store as one JSON object for the project file ("Save project … with version history"); None: no versions."""
    folder = _folder(root, pid)
    with _lock(pid):
        ms = _manifests(folder)
        if not ms:
            return None
        objs = {sha: base64.b64encode(_read(p)).decode("ascii") for sha, p in _objects(folder)}
        return {"format": "a3d-versions", "v": 1, "state": _state(folder), "versions": ms, "objects": objs}


def unbundle(root, pid, data) -> dict:
    """A project file's version history put into this project's store (each object checked against its hash; the
    versions, variants and the one on screen as in the file; versions already here stay) -> {versions, objects}."""
    folder = _folder(root, pid)
    if not isinstance(data, dict) or data.get("format") != "a3d-versions" or not isinstance(data.get("versions"), list):
        raise VersionError("The project file's version history cannot be read.")
    objs = data.get("objects") or {}
    if not isinstance(objs, dict):
        raise VersionError("The project file's version history cannot be read.")
    with _lock(pid):
        n = 0
        for sha, b64 in objs.items():
            _sha(sha)
            try:
                raw = base64.b64decode(b64, validate=True)
                ok = hashlib.sha256(zlib.decompress(raw)).hexdigest() == sha
            except (ValueError, TypeError, zlib.error):
                ok = False
            if not ok:
                raise VersionError("The project file's version history is damaged.")
            p = _obj_path(folder, sha)
            if not p.exists():
                _write(p, raw)
                n += 1
        have = {sha for sha, _ in _objects(folder)}
        kept = 0
        for m in data["versions"]:
            if not isinstance(m, dict) or not isinstance(m.get("parts"), dict):
                raise VersionError("The project file's version history cannot be read.")
            _vid(m.get("id"))
            refs = list(m["parts"].values()) + [m.get("project")] + ([m["thumb"]] if m.get("thumb") else [])
            if any(not isinstance(r, str) or r not in have for r in refs):
                raise VersionError("The project file's version history is damaged.")
            p = folder / "versions" / f"{m['id']}.json"
            if not p.exists():
                _write(p, json.dumps(m).encode("utf-8"))
                kept += 1
        st_in = data.get("state") if isinstance(data.get("state"), dict) else {}
        st = _state(folder)
        for v in st_in.get("variants") or []:
            if not isinstance(v, dict) or not isinstance(v.get("id"), str) or not _VAR.match(v["id"]):
                continue
            v = {"id": v["id"], "name": str(v.get("name") or "")[:60], "head": v.get("head"), "base": v.get("base"), "time": v.get("time")}
            for k in ("head", "base"):
                if v[k] and not (isinstance(v[k], str) and _VID.match(v[k]) and (folder / "versions" / f"{v[k]}.json").exists()):
                    v[k] = None
            old = next((x for x in st["variants"] if x["id"] == v["id"]), None)
            if old:
                old.update(v)
            else:
                st["variants"].append(v)
        if isinstance(st_in.get("current"), str) and any(x["id"] == st_in["current"] for x in st["variants"]):
            st["current"] = st_in["current"]
        _put_state(folder, st)
        return {"versions": kept, "objects": n}
