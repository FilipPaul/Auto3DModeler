"""🌐 A maker's CAD file from the internet (the AI's fetch_cad): "use part number X" -> the part's STEP downloaded,
checked, cached and put in like a file the user dragged in.

* `download(url)` – https only (a redirect to http is refused), at most MAX_BYTES, a timeout; -> (bytes, file name).
* `check(data, name)` – only CAD content passes: STEP (its ISO-10303-21 header), IGES, STL (binary or ASCII), or a ZIP
  holding one (its first CAD file, a STEP first). A web page is refused with a plain why (a login or a configurator).
* `fetch(cache_dir, url, pn, maker, name)` – the file kept in the CAD download cache (<data>/cad_downloads/<sha>.<ext>)
  with where it came from (url, maker, part number) in index.json; the same part number or URL again comes from it.

The maker's models are for use in the design, not to pass on: the source is kept with the file (and in the library
part made from it). Standard library only.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

MAX_BYTES = 100 * 1024 * 1024  # a big assembly STEP is 20–60 MB
TIMEOUT = 60                    # s, connecting and each read
CAD_EXT = (".step", ".stp", ".igs", ".iges", ".stl")
AGENT = "Auto3DModeler (CAD download for the user's design)"
HTML_TEXT = ("This is a web page, not a CAD file — a login or configurator is probably needed. Give the user the page "
             "link and ask them to download the STEP there and drag it into the app.")
OFF_TEXT = ("The internet is off in the AI settings (internet je vypnutý v nastavení AI) — ask the user to download the "
            "file and drag it in, or to turn 🌐 on in the ✨ AI settings.")


class FetchError(Exception):
    pass


def internet_on(data_dir: Path) -> bool:
    """🌐 Hledat díly na internetu (the ✨ AI settings; default on): <data>/ai/settings.json {"internet": false} turns it
    off; A3D_AI_INTERNET=0 too (a test server)."""
    if os.environ.get("A3D_AI_INTERNET", "").strip() in ("0", "false", "ne", "off"):
        return False
    try:
        return json.loads((Path(data_dir) / "ai" / "settings.json").read_text(encoding="utf-8")).get("internet", True) is not False
    except (OSError, ValueError, AttributeError):
        return True


# --------------------------------------------------------------------------- content
def _is_step(head: bytes) -> bool:
    return head.lstrip(b"\xef\xbb\xbf \t\r\n").upper().startswith(b"ISO-10303-21")


def _is_iges(head: bytes) -> bool:
    """IGES: 80-column records, the first a Start record ('S' in column 73), then a Global one ('G')."""
    lines = head.replace(b"\r\n", b"\n").split(b"\n")
    return len(lines) > 1 and len(lines[0]) >= 73 and lines[0][72:73] == b"S" and any(len(x) >= 73 and x[72:73] == b"G" for x in lines[1:6])


def _is_stl(data: bytes) -> bool:
    if len(data) >= 84 and len(data) == 84 + 50 * int.from_bytes(data[80:84], "little"):
        return True  # binary: 80-byte header, the count, 50 bytes a triangle
    head = data[:4096].lstrip().lower()
    return head.startswith(b"solid") and b"facet" in data[:200_000].lower()


def _is_html(data: bytes, ctype: str = "") -> bool:
    head = data[:1024].lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    return "html" in ctype.lower() or head.startswith((b"<!doctype", b"<html", b"<head")) or b"<html" in head


def kind_of(data: bytes) -> str | None:
    """The CAD kind of a file's bytes: "step" | "iges" | "stl" | None."""
    head = data[:8192]
    if _is_step(head):
        return "step"
    if _is_iges(head):
        return "iges"
    if _is_stl(data):
        return "stl"
    return None


EXT = {"step": ".step", "iges": ".igs", "stl": ".stl"}


def check(data: bytes, name: str = "", ctype: str = "") -> tuple[bytes, str, str]:
    """Downloaded bytes -> (the CAD file's bytes, its kind, its file name); a ZIP: its first CAD file (a STEP before an
    IGES before an STL). Anything else raises FetchError saying what it is."""
    if not data:
        raise FetchError("The link gave an empty file.")
    if data[:4] == b"PK\x03\x04":
        try:
            z = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as exc:
            raise FetchError(f"A broken ZIP ({exc}).") from exc
        members = [i for i in z.infolist() if not i.is_dir() and i.filename.lower().endswith(CAD_EXT)]
        members.sort(key=lambda i: (CAD_EXT.index(Path(i.filename).suffix.lower()) // 2, i.filename))
        for info in members:
            if info.file_size > MAX_BYTES:
                raise FetchError(f"{info.filename} in the ZIP is over {MAX_BYTES // 2**20} MB.")
            inner = z.read(info)
            kind = kind_of(inner)
            if kind:
                return inner, kind, Path(info.filename).name
        raise FetchError("The ZIP holds no STEP, IGES or STL file"
                         + (f" (it has {', '.join(i.filename for i in z.infolist()[:6])})" if z.infolist() else "") + ".")
    kind = kind_of(data)
    if kind:
        p = Path(name or "part")  # (its own name, with the right extension: a .txt that is a STEP becomes .step)
        return data, kind, p.name if _ext_kind(p.suffix.lower()) == kind else (p.stem if p.suffix.lower() in CAD_EXT else p.name) + EXT[kind]
    if _is_html(data, ctype):
        raise FetchError(HTML_TEXT)
    raise FetchError("This is not a CAD file (a STEP, IGES or STL, or a ZIP of one)"
                     + (f" — the server says {ctype.split(';')[0]}" if ctype else "") + ". Find a direct link to the file.")


def _ext_kind(ext: str) -> str | None:
    return {".step": "step", ".stp": "step", ".igs": "iges", ".iges": "iges", ".stl": "stl"}.get(ext)


# --------------------------------------------------------------------------- download
class _HttpsOnly(urllib.request.HTTPRedirectHandler):
    """Redirects are followed, to https only (or to the loopback, when that is allowed)."""

    def __init__(self, local: bool):
        self.local = local

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_url(newurl, self.local)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _check_url(url: str, local: bool = False) -> str:
    u = urllib.parse.urlsplit(str(url or "").strip())
    loopback = u.hostname in ("127.0.0.1", "localhost", "::1")
    if u.scheme == "https" and u.hostname:
        return u.geturl()
    if local and u.scheme == "http" and loopback:  # (the tests' local file server)
        return u.geturl()
    raise FetchError(f"Only https:// links are fetched (got {url!r}).")


def _name_from(resp, url: str) -> str:
    cd = resp.headers.get("Content-Disposition") or ""
    m = re.search(r"filename\*=UTF-8''([^;]+)", cd, re.I) or re.search(r'filename="?([^";]+)"?', cd, re.I)
    if m:
        return Path(urllib.parse.unquote(m.group(1)).replace("\\", "/")).name
    return Path(urllib.parse.unquote(urllib.parse.urlsplit(resp.geturl() or url).path)).name


def download(url: str, max_bytes: int = MAX_BYTES, timeout: float = TIMEOUT, local: bool = False) -> tuple[bytes, str, str, str]:
    """GET the link -> (bytes, file name, content type, final url). Over max_bytes, a timeout, an HTTP error: FetchError."""
    url = _check_url(url, local)
    opener = urllib.request.build_opener(_HttpsOnly(local))
    req = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": "*/*"})
    try:
        with opener.open(req, timeout=timeout) as r:
            size = int(r.headers.get("Content-Length") or 0)
            if size > max_bytes:
                raise FetchError(f"The file is {size / 2**20:.0f} MB — over the {max_bytes // 2**20} MB limit.")
            buf, end = io.BytesIO(), time.time() + 4 * timeout
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                buf.write(chunk)
                if buf.tell() > max_bytes:
                    raise FetchError(f"The file is over the {max_bytes // 2**20} MB limit.")
                if time.time() > end:
                    raise FetchError("The download took too long.")
            return buf.getvalue(), _name_from(r, url), r.headers.get("Content-Type") or "", r.geturl() or url
    except urllib.error.HTTPError as exc:
        hint = " — a login is probably needed" if exc.code in (401, 403) else ""
        raise FetchError(f"The server answered {exc.code} {exc.reason}{hint}.") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise FetchError(f"Could not download it ({getattr(exc, 'reason', exc)}).") from exc


# --------------------------------------------------------------------------- cache
def _key(pn: str, maker: str = "") -> str:
    return re.sub(r"[\s_]+", "", f"{maker}|{pn}".lower()) if pn else ""


def _index(cache: Path) -> dict:
    try:
        return json.loads((cache / "index.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"files": {}}


def cached(cache_dir: Path, url: str = "", pn: str = "", maker: str = "") -> dict | None:
    """The cache's entry for that part number (and maker) or URL, its file still there -> the entry, else None."""
    files = _index(Path(cache_dir)).get("files", {})
    want, bare = _key(pn, maker), _key(pn)  # (no maker given: that part number of any maker)
    for e in files.values():
        keys = e.get("keys", [])
        hit = (pn and (want in keys or not maker and any(k.endswith(bare) for k in keys))) or (url and url in e.get("urls", []))
        if hit and (Path(cache_dir) / e["path"]).is_file():
            return e
    return None


def fetch(cache_dir: Path, url: str = "", pn: str = "", maker: str = "", name: str = "", local: bool = False,
          max_bytes: int = MAX_BYTES, timeout: float = TIMEOUT) -> dict:
    """A part's CAD file from the cache, else downloaded and kept -> {sha, path (in the cache), file, kind, size, url,
    maker, pn, name, cached: bool}. Neither in the cache nor a url: FetchError."""
    cache = Path(cache_dir)
    pn, maker, name, url = str(pn or "").strip(), str(maker or "").strip(), str(name or "").strip(), str(url or "").strip()
    hit = cached(cache, url, pn, maker)
    if hit:
        return {**_entry_out(cache, hit, url, pn, maker, name), "cached": True}
    if not url:
        raise FetchError(f"No file for {pn or 'that part'} is downloaded yet — give its url (a direct link to the STEP).")
    raw, fname, ctype, final = download(url, max_bytes, timeout, local)
    data, kind, fname = check(raw, fname, ctype)
    sha = hashlib.sha256(data).hexdigest()
    rel = f"{sha}{EXT[kind]}"
    cache.mkdir(parents=True, exist_ok=True)
    if not (cache / rel).exists():
        tmp = cache / (rel + ".part")
        tmp.write_bytes(data)
        os.replace(tmp, cache / rel)
    idx = _index(cache)
    e = idx["files"].setdefault(sha, {"sha": sha, "path": rel, "file": fname, "kind": kind, "size": len(data), "urls": [], "keys": [],
                                      "added": time.strftime("%Y-%m-%d %H:%M")})
    for u in {url, final}:
        if u not in e["urls"]:
            e["urls"].append(u)
    if pn and _key(pn, maker) not in e["keys"]:
        e["keys"].append(_key(pn, maker))
    for k, v in (("pn", pn), ("maker", maker), ("name", name)):  # (the first one's; another part number for the same file: in keys)
        if v:
            e.setdefault(k, v)
    (cache / "index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
    return {**_entry_out(cache, e, url, pn, maker, name), "cached": False}


def _entry_out(cache: Path, e: dict, url: str, pn: str, maker: str, name: str) -> dict:
    return {"sha": e["sha"], "path": str(cache / e["path"]), "file": e["file"], "kind": e["kind"], "size": e["size"],
            "url": url or e["urls"][0], "maker": maker or e.get("maker", ""), "pn": pn or e.get("pn", ""), "name": name or e.get("name", "")}
