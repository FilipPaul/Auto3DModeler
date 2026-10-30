"""Project files (`.a3d`): one ZIP, as .3mf / .docx / Fusion's .f3d are — rename it to .zip to look inside.

    project.json         the project (parts, assemblies, sheets, parameters …); "format": "a3d-package", "package": 1
                         (its own "version" stays the project's: 3); "blob_files": {sha: the file's entry below}
    blobs/<name>         each imported file as it was: byte for byte, under its original name (another CAD opens it);
                         blobs/<sha>.<ext> when the name is not known or two files share it
    versions/index.json  🕘 the version history, when saved with it (its manifests) …
    versions/objects/<sha>   … and its objects (zlib already: stored as they are)
    thumbnail.png        an iso picture of the part on screen (the Recent list, the demo cards, file browsers)

One project.json, not a file per part: the app opens a project whole (parts refer to each other: inserts, assemblies,
sheets) and the parts are small next to the imported files — those made the old .a3d.json big. For lazy loading later
a part can move to parts/<id>.json with a stub left in project.json; that is "package": 2 (this reader refuses it).
Standard library only.
"""
from __future__ import annotations

import base64
import io
import json
import re
import zipfile
from pathlib import Path, PurePosixPath

FORMAT, VERSION, EXT = "a3d-package", 1, ".a3d"
PROJECT, THUMB = "project.json", "thumbnail.png"
# kinds of file that are compressed already: stored as they are (deflating them again only costs time)
STORED = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".3mf", ".glb", ".zip", ".gz", ".tgz", ".7z", ".docx", ".xlsx"}


class PackageError(ValueError):
    pass


def files(proj: dict) -> dict:
    """The imported files' names by their hash (the steps that use them: ▣ Solid from a file …)."""
    out = {}
    for p in proj.get("parts") or []:
        for f in ((p.get("model") or {}).get("features") or []) if isinstance(p.get("model"), dict) else []:
            if isinstance(f, dict) and isinstance(f.get("blob"), str) and f["blob"]:
                out.setdefault(f["blob"], f.get("file") or "")
    return out


def _ext(name: str) -> str:
    e = PurePosixPath(str(name or "")).suffix.lower()
    return e if re.fullmatch(r"\.[a-z0-9]{1,8}", e) else ".bin"


def _entry(sha: str, name: str, taken: set) -> str:
    """blobs/<the original name> (made safe for a file name), else blobs/<sha>.<ext>."""
    safe = re.sub(r'[\x00-\x1f\\/:*?"<>|]+', "_", PurePosixPath(str(name or "").replace("\\", "/")).name).strip(" .")
    e = f"blobs/{safe}" if safe else ""
    if not e or e.lower() in taken:
        e = f"blobs/{sha}{_ext(name)}"
    taken.add(e.lower())
    return e


def write(proj: dict, get, versions: dict | None = None, thumbnail: bytes | None = None) -> tuple[bytes, list[str]]:
    """A project (Save project's JSON) -> (the .a3d bytes, the hashes of files `get(sha) -> bytes` could not give)."""
    proj = {k: v for k, v in proj.items() if k not in ("blobs", "versions", "blob_files")}
    names, missing, entries, taken = files(proj), [], {}, set()
    datas = {}
    for sha in names:  # (in the order the steps use them: the first keeps the name)
        try:
            datas[sha] = get(sha)
        except (KeyError, OSError, ValueError):
            datas[sha] = None
        if datas[sha] is None:
            missing.append(sha)
        else:
            entries[sha] = _entry(sha, names[sha], taken)
    proj.update(format=FORMAT, package=VERSION, blob_files=entries)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.writestr(PROJECT, json.dumps(proj, ensure_ascii=False, separators=(",", ":")))
        if thumbnail:
            z.writestr(THUMB, thumbnail, zipfile.ZIP_STORED)
        for sha, e in entries.items():
            z.writestr(e, datas[sha], zipfile.ZIP_STORED if _ext(e) in STORED else zipfile.ZIP_DEFLATED)
        if isinstance(versions, dict):
            objs = versions.get("objects") if isinstance(versions.get("objects"), dict) else {}
            z.writestr("versions/index.json", json.dumps({k: v for k, v in versions.items() if k != "objects"}, ensure_ascii=False))
            for sha, b64 in objs.items():
                z.writestr(f"versions/objects/{sha}", base64.b64decode(b64), zipfile.ZIP_STORED)
    return buf.getvalue(), missing


def _zip(src) -> zipfile.ZipFile:
    """A package from its bytes or its path."""
    try:
        return zipfile.ZipFile(io.BytesIO(src) if isinstance(src, (bytes, bytearray)) else Path(src))
    except (zipfile.BadZipFile, OSError) as e:
        raise PackageError(f"This is not a project file (.a3d): {e}") from e


def _project(z: zipfile.ZipFile) -> dict:
    try:
        proj = json.loads(z.read(PROJECT).decode("utf-8"))
    except KeyError as e:
        raise PackageError("This is not a project file (.a3d): it has no project.json.") from e
    except (ValueError, zipfile.BadZipFile) as e:
        raise PackageError(f"The .a3d file's project.json cannot be read: {e}") from e
    if not isinstance(proj, dict):
        raise PackageError("This is not a project file (.a3d): its project.json is no project.")
    if (proj.get("package") or 1) > VERSION:
        raise PackageError(f"This project was saved by a newer version of the app (package version {proj.get('package')}).")
    return proj


def load(src) -> dict:
    """A package (its bytes or its path) -> {project (its files left out), blobs {sha: bytes}, versions (the 🕘 bundle)
    or None, thumbnail (PNG bytes) or None}. Raises PackageError when it is no project file."""
    with _zip(src) as z:
        proj = _project(z)
        names = set(z.namelist())
        try:
            blobs = {sha: z.read(e) for sha, e in (proj.pop("blob_files", None) or {}).items() if e in names}
            versions = None
            if "versions/index.json" in names:
                versions = json.loads(z.read("versions/index.json").decode("utf-8"))
                objs = {PurePosixPath(n).name: z.read(n) for n in names if n.startswith("versions/objects/") and not n.endswith("/")}
                if objs:  # (the store takes them as its bundle: base64, checked against their hash there)
                    versions["objects"] = {sha: base64.b64encode(b).decode("ascii") for sha, b in objs.items()}
            thumb = z.read(THUMB) if THUMB in names else None
        except (zipfile.BadZipFile, ValueError, OSError) as e:
            raise PackageError(f"The .a3d file cannot be read: {e}") from e
    return {"project": proj, "blobs": blobs, "versions": versions, "thumbnail": thumb}


def manifest(src) -> dict:
    """Only the project.json of a package (a list of projects: their names, parts)."""
    with _zip(src) as z:
        return _project(z)


def thumbnail(src) -> bytes | None:
    """A package's picture (thumbnail.png), if it has one."""
    with _zip(src) as z:
        try:
            return z.read(THUMB)
        except KeyError:
            return None


def store(got: dict, put) -> dict:
    """The files of a loaded package (`load`) into the blob store (`put(bytes) -> sha`) -> the project. A file changed
    inside the package (taken out, changed and put back) gets its new hash: the steps that use it follow."""
    moved = {}
    for sha, data in got["blobs"].items():
        new = put(data)
        if new != sha:
            moved[sha] = new
    proj = got["project"]
    for p in proj.get("parts") or []:
        for f in ((p.get("model") or {}).get("features") or []) if isinstance(p.get("model"), dict) else []:
            if isinstance(f, dict) and f.get("blob") in moved:
                f["blob"] = moved[f["blob"]]
    return proj
