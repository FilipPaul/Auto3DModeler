"""Build the Windows app (docs/DISTRIBUTION.md): a clean venv from the requirements, PyInstaller's one-folder build
(tools/build/auto3d.spec), the portable zip, the installer when Inno Setup is installed, and a smoke test of the result.

usage:  py tools/build/build.py [--reuse-venv] [--no-smoke] [--port 5194]
  build/venv            the build's own Python packages (made anew unless --reuse-venv)
  dist/Auto3DModeler/   the app: Auto3DModeler.exe + _internal/
  dist/Auto3DModeler-<version>-win64-portable.zip
  dist/Auto3DModeler-<version>-setup.exe   (only with Inno Setup 6: ISCC.exe on PATH or in Program Files)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "tools" / "build"
BUILD, DIST = ROOT / "build", ROOT / "dist"
STAGE = BUILD / "stage"
APP = "Auto3DModeler"


def version() -> str:
    return re.search(r'VERSION = "([^"]+)"', (ROOT / "auto3d" / "version.py").read_text(encoding="utf-8")).group(1)


def run(*cmd, **kw):
    print(">", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def git(*args) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def make_venv(venv: Path, reuse: bool) -> Path:
    py = venv / "Scripts" / "python.exe"
    if not (reuse and py.exists()):
        if venv.exists():
            shutil.rmtree(venv)
        run(sys.executable, "-m", "venv", venv)
        run(py, "-m", "pip", "install", "--upgrade", "pip")
        run(py, "-m", "pip", "install", "-r", ROOT / "requirements.txt", "-r", ROOT / "requirements-modeler.txt",
            "-r", HERE / "requirements-build.txt", "-c", HERE / "constraints.txt")
    return py


def stage(py: Path):
    """build/stage: BUILD.json (which commit; auto3d/version.py reads it) and the icon."""
    STAGE.mkdir(parents=True, exist_ok=True)
    commit = git("rev-parse", "--short", "HEAD")
    stamp = {"version": version(), "commit": commit, "date": git("log", "-1", "--format=%cs") if commit else "",
             "branch": git("rev-parse", "--abbrev-ref", "HEAD") if commit else "",
             "dirty": bool(git("status", "--porcelain", "--untracked-files=no")), "built": datetime.now().isoformat(timespec="seconds")}
    (STAGE / "BUILD.json").write_text(json.dumps(stamp, indent=1), encoding="utf-8")
    run(py, HERE / "icon.py", STAGE / "auto3d.ico")


def folder_size(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def portable_zip(app: Path) -> Path:
    out = DIST / f"{APP}-{version()}-win64-portable.zip"
    out.unlink(missing_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in sorted(app.rglob("*")):
            if f.is_file():
                z.write(f, Path(APP) / f.relative_to(app))
    return out


def find_iscc() -> str | None:
    hit = shutil.which("ISCC") or shutil.which("ISCC.exe")
    if hit:
        return hit
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA") and
                 str(Path(os.environ["LOCALAPPDATA"]) / "Programs")):
        if base and (Path(base) / "Inno Setup 6" / "ISCC.exe").exists():
            return str(Path(base) / "Inno Setup 6" / "ISCC.exe")
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--venv", default=str(BUILD / "venv"))
    ap.add_argument("--reuse-venv", action="store_true", help="keep build/venv when it is there (faster)")
    ap.add_argument("--no-smoke", action="store_true")
    ap.add_argument("--port", type=int, default=5194, help="the smoke test's port")
    args = ap.parse_args()
    t0 = time.time()
    py = make_venv(Path(args.venv), args.reuse_venv)
    stage(py)
    app = DIST / APP
    if app.exists():
        shutil.rmtree(app)
    t1 = time.time()
    run(py, "-m", "PyInstaller", HERE / "auto3d.spec", "--distpath", DIST, "--workpath", BUILD / "pyi", "--noconfirm")
    print(f"PyInstaller: {time.time() - t1:.0f} s; {app}: {folder_size(app) / 1e6:.0f} MB")
    z = portable_zip(app)
    print(f"portable zip: {z} ({z.stat().st_size / 1e6:.0f} MB)")
    iscc = find_iscc()
    if iscc:
        run(iscc, f"/DAppVersion={version()}", f"/DSourceDir={app}", f"/O{DIST}", HERE / "installer.iss")
    else:
        print("Inno Setup 6 (ISCC.exe) not found: no installer, the portable zip only (docs/DISTRIBUTION.md).")
    if not args.no_smoke:
        data = BUILD / "smoke-data"
        shutil.rmtree(data, ignore_errors=True)
        run(sys.executable, HERE / "smoke.py", app / f"{APP}.exe", data, str(args.port))
    print(f"done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
