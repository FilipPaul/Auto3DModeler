"""The app's version: VERSION (raised with each release) and, when it runs from a git checkout, the commit it is at —
written into the AI's problem reports and shown by /api/version, so a report says which build it came from."""
from __future__ import annotations

import subprocess
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
    """{version, commit, date, branch, dirty} — the commit fields empty when git is not there."""
    commit = _git("rev-parse", "--short", "HEAD")
    return {"version": VERSION, "commit": commit, "date": _git("log", "-1", "--format=%cs") if commit else "",
            "branch": _git("rev-parse", "--abbrev-ref", "HEAD") if commit else "",
            "dirty": bool(_git("status", "--porcelain", "--untracked-files=no")) if commit else False}


def text() -> str:
    """'0.9.0 (main @ 2900fde, 2026-10-27, with local changes)' or '0.9.0'."""
    b = build()
    if not b["commit"]:
        return b["version"]
    return f"{b['version']} ({b['branch']} @ {b['commit']}, {b['date']}{', with local changes' if b['dirty'] else ''})"
