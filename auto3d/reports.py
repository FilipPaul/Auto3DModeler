"""The AI's problem reports (RealSWReports/*.md, written by the server's report_problem): what is reported already,
and whether a new report says the same as one of them — so the AI does not file one thing twice. Standard library only.

Next to a report: the project on screen when it was written (<base>.a3d — the Save project file, compacted, so
someone else can open it and reproduce the problem), a ⏺ recording of the user's moves (<base>.recording.json) and the
screenshots the AI chose to show the state of the app (<base>.shot-1.png …, shown in the .md).
"""
from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from pathlib import Path

from auto3d import package

# words that say nothing about which problem it is
STOP = set("a an the of in on at to for and or with without is are be not no does do it its this that from by as when "
           "can cannot should into than then one".split())
SIMILAR = 0.6  # how alike two titles must be to count as the same report
KEEP_FILE = 3 << 20  # bytes: an imported file (a blob) larger than this is left out of an attached project
CAP = 5 << 20        # bytes: about how large an attached project (.a3d) may get — the largest imported files go first
PROJECT_EXT, RECORDING_EXT, SHOT_EXT = ".a3d", ".recording.json", ".shot-"  # (<base>.shot-1.png / .webp)
SHOTS_MAX, SHOT_PX, SHOT_BYTES = 4, 1600, 1 << 20  # screenshots: at most this many per report, px across, bytes each


def _stem(w: str) -> str:
    """A word without its ending: holes ~ hole, painted ~ paint, assemblies ~ assembly, shown ~ show."""
    for end, to in (("ies", "y"), ("ing", ""), ("ed", ""), ("es", "e"), ("s", ""), ("own", "ow")):
        if w.endswith(end) and len(w) - len(end) >= 3 and not w.endswith("ss"):
            return w[: len(w) - len(end)] + to
    return w


def _words(text: str) -> set[str]:
    """A title's telling words, lower case, without their endings."""
    return {_stem(w) for w in re.findall(r"[a-z0-9áčďéěíňóřšťúůýž]+", text.lower()) if w not in STOP and len(w) >= 2}


def similarity(a: str, b: str) -> float:
    """0 … 1: the shared telling words (of the shorter title) and the letters in order, the higher of the two."""
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return 0.0
    shared = len(wa & wb) / max(len(wa | wb), 1)            # Jaccard of the words
    cover = len(wa & wb) / min(len(wa), len(wb))            # how much of the shorter one the other says
    seq = SequenceMatcher(None, " ".join(sorted(wa)), " ".join(sorted(wb))).ratio()
    return max(shared, 0.85 * cover if min(len(wa), len(wb)) >= 3 else 0.0, seq if seq > 0.85 else 0.0)


def read(folder: Path) -> list[dict]:
    """Every report in the folder, newest first: [{file, title, kind, date, project, recording, shots}] (project /
    recording: the file attached to it, else ''; shots: its screenshots' files, in order)."""
    out = []
    if not folder.is_dir():
        return out
    for f in folder.glob("*.md"):
        try:
            head = f.read_text(encoding="utf-8", errors="replace")[:2000]
        except OSError:
            continue
        title = next((ln[2:].strip() for ln in head.splitlines() if ln.startswith("# ")), f.stem)
        kind = re.search(r"\*\*Kind:\*\*\s*([^\n]+)", head)
        date = re.search(r"\*\*Date:\*\*\s*([^\n]+)", head)
        proj, rec = f.with_name(f.stem + PROJECT_EXT), f.with_name(f.stem + RECORDING_EXT)
        out.append({"file": f.name, "title": title, "kind": kind.group(1).strip() if kind else "bug",
                    "date": date.group(1).strip() if date else f.name[:10],
                    "project": proj.name if proj.exists() else "", "recording": rec.name if rec.exists() else "",
                    "shots": sorted((s.name for s in folder.glob(f"{f.stem}{SHOT_EXT}*") if s.suffix in (".png", ".webp")),
                                    key=lambda n: int(re.sub(r"\D", "", n.rsplit(SHOT_EXT, 1)[1]) or 0))})
    out.sort(key=lambda r: r["file"], reverse=True)
    return out


def similar(folder: Path, title: str, limit: int = 3) -> list[dict]:
    """The reports whose title says (nearly) the same as `title`, the most alike first: [{…, score}]."""
    scored = [{**r, "score": round(similarity(title, r["title"]), 2)} for r in read(folder)]
    hits = [r for r in scored if r["score"] >= SIMILAR]
    hits.sort(key=lambda r: -r["score"])
    return hits[:limit]


def search(folder: Path, query: str = "", kind: str = "", limit: int = 40) -> list[dict]:
    """The reports (newest first), those of a kind, those that share a word with `query` (the most alike first)."""
    rows = [r for r in read(folder) if not kind or r["kind"] == kind]
    if query.strip():
        q = _words(query)
        rows = [r for r in rows if q & _words(r["title"])]
        rows.sort(key=lambda r: -similarity(query, r["title"]))
    return rows[:limit]


def compact_project(proj: dict, get, keep_file: int | None = None, cap: int | None = None, thumbnail: bytes | None = None) -> tuple[bytes, list[dict]]:
    """A project (as Save project writes it) for a report -> (its .a3d bytes, what was left out). Everything that
    rebuilds it stays (parts, features, sketches, assemblies, cables, joints, sheets); left out: the version history
    and an imported file over `keep_file` bytes (KEEP_FILE) — then the largest ones until it is under about `cap` (CAP) — each replaced
    by a note in the file's "left_out" (its name and size). The imported files come from `get(sha) -> bytes` (the blob store);
    `thumbnail`: its picture (PNG bytes)."""
    keep_file, cap = KEEP_FILE if keep_file is None else keep_file, CAP if cap is None else cap
    names, files = package.files(proj), {}
    for sha in names:
        try:
            files[sha] = get(sha)
        except (KeyError, OSError, ValueError):
            continue
    size = {sha: len(b) for sha, b in files.items()}
    left = []

    def leave(sha):
        files.pop(sha, None)
        left.append({"what": "imported file", "blob": sha, "name": names.get(sha, ""), "bytes": size.get(sha, 0)})

    for sha in [s for s, n in size.items() if n > keep_file]:
        leave(sha)
    while True:
        data, _ = package.write({**proj, **({"left_out": left} if left else {})}, files.get, thumbnail=thumbnail)
        if len(data) <= cap or not files:
            return data, left
        leave(max(files, key=lambda s: size.get(s, 0)))
