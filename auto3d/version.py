"""The app's version: VERSION (raised with each release) and, when it runs from a git checkout, the commit it is at —
written into the AI's problem reports and shown by /api/version, so a report says which build it came from.

The server keeps running while the checkout moves on (a merge, a pull): build() is the commit the server started at,
head() the checkout's commit now (asked again every 30 s). When they differ the server runs older code than the
files — a report says both and the page shows ⟳ New version — restart the app."""
from __future__ import annotations

import json
import os
import subprocess
import time
from functools import lru_cache
from pathlib import Path

VERSION = "0.9.0"
ROOT = Path(__file__).resolve().parent.parent


def _git(*args: str) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


@lru_cache(maxsize=1)
def build() -> dict:
    """{version, commit, date, branch, dirty} — the commit fields empty when git is not there. The built app
    (tools/build) has no git: its BUILD.json, written by the build, says which commit it was made from."""
    stamp = ROOT / "BUILD.json"
    if stamp.exists():
        try:
            return {"version": VERSION, "commit": "", "date": "", "branch": "", "dirty": False,
                    **json.loads(stamp.read_text(encoding="utf-8"))}
        except (OSError, ValueError):
            pass
    commit = _git("rev-parse", "--short", "HEAD")
    return {"version": VERSION, "commit": commit, "date": _git("log", "-1", "--format=%cs") if commit else "",
            "branch": _git("rev-parse", "--abbrev-ref", "HEAD") if commit else "",
            "dirty": bool(_git("status", "--porcelain", "--untracked-files=no")) if commit else False}


HEAD_TTL = 30.0  # s: how long head() trusts its last `git rev-parse`
_head = {"at": -HEAD_TTL, "commit": ""}


def head() -> str:
    """The checkout's commit now ('' in the built app: BUILD.json, no git). A3D_FAKE_HEAD: a test's moved checkout."""
    if (ROOT / "BUILD.json").exists():
        return ""
    if os.environ.get("A3D_FAKE_HEAD"):
        return os.environ["A3D_FAKE_HEAD"]
    now = time.monotonic()
    if now - _head["at"] >= HEAD_TTL:
        _head.update(at=now, commit=_git("rev-parse", "--short", "HEAD"))
    return _head["commit"]


def stale() -> str:
    """The checkout's commit when it moved on since the server started (restart the app to run it), else ''."""
    started, now = build()["commit"], head()
    return now if started and now and now != started else ""


def text(page: str = "") -> str:
    """'0.9.0 (main @ 2900fde, 2026-10-27, with local changes)' or '0.9.0'; the checkout moved on since the server
    started: '0.9.0 (server started at main @ 92d0e37, …; checkout now at 1e35a8d — restart the app to run it)'.
    page: the commit the browser page was loaded with — said too when it is not the server's."""
    b = build()
    if not b["commit"]:
        return b["version"]
    moved = stale()
    out = (f"{b['version']} ({'server started at ' if moved else ''}{b['branch']} @ {b['commit']}, {b['date']}"
           f"{', with local changes' if b['dirty'] else ''}")
    if moved:
        out += f"; checkout now at {moved} — restart the app to run it"
    if page and page != b["commit"]:
        out += f"; page loaded at {page} — reload it"
    return out + ")"
