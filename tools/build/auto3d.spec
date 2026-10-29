# PyInstaller spec: the one-folder Windows build of Auto3DModeler (docs/DISTRIBUTION.md).
# Run through tools/build/build.py (it makes the venv, BUILD.json and the icon first):
#   <venv>\Scripts\python -m PyInstaller tools/build/auto3d.spec --distpath dist --workpath build/pyi --noconfirm
# Result: dist/Auto3DModeler/Auto3DModeler.exe + _internal/ (Python, the packages, web/, library/, agent_plugin/, demos/).
import importlib.util
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, copy_metadata

ROOT = Path(SPECPATH).resolve().parents[1]
STAGE = ROOT / "build" / "stage"  # BUILD.json and auto3d.ico, written by build.py


def libs_of(package):
    """A delvewheel wheel's DLL folder (<site-packages>/<dist>.libs) -> binaries at the same place beside the package,
    where its __init__ adds it to the DLL search path."""
    spec = importlib.util.find_spec(package)
    if spec is None:
        return []
    site = Path(spec.origin).parent.parent
    out = []
    for libs in site.glob("*.libs"):
        if libs.name.split(".")[0].replace("-", "_").startswith(package.lower()) or (
                package == "OCP" and libs.name.startswith("cadquery_ocp")):
            out += [(str(f), libs.name) for f in libs.iterdir() if f.suffix.lower() == ".dll"]
    return out


datas = [(str(ROOT / "web"), "web"), (str(ROOT / "library"), "library"), (str(ROOT / "agent_plugin"), "agent_plugin"),
         (str(ROOT / "demos"), "demos"),  # 🎬 the demo projects (read-only: opened as a copy)
         (str(ROOT / "initial draft.pdf"), ".")]
if (STAGE / "BUILD.json").exists():
    datas.append((str(STAGE / "BUILD.json"), "."))
for dist in ("cadquery-ocp-novtk", "planegcs", "flask", "werkzeug", "ezdxf", "PyMuPDF", "shapely", "numpy"):
    try:
        datas += copy_metadata(dist)  # auto3d.modeler.status() reads the versions
    except Exception:  # noqa: BLE001 — a package left out of this build
        pass

binaries = libs_of("OCP") + libs_of("planegcs") + libs_of("cascadio")
hiddenimports = ["server", "auto3d.mcp_server", "auto3d.modeler.worker", "auto3d.modeler.doc", "auto3d.modeler.kernel",
                 "auto3d.modeler.packed", "auto3d.modeler.printsplit", "pystray._win32"]
for pkg in ("auto3d", "OCP", "planegcs", "cascadio", "ezdxf"):
    if importlib.util.find_spec(pkg) is not None:
        hiddenimports += collect_submodules(pkg)

a = Analysis(
    [str(ROOT / "tools" / "build" / "Auto3DModeler.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "IPython", "pytest", "selenium", "PyQt5", "PyQt6", "PySide6", "notebook",
              "vtkmodules", "pandas", "scipy"],
    noarchive=False,
)
pyz = PYZ(a.pure)
icon = STAGE / "auto3d.ico"
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Auto3DModeler",
    console=False,  # no console window: the log is in %LOCALAPPDATA%\Auto3DModeler\logs
    icon=str(icon) if icon.exists() else None,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Auto3DModeler", upx=False)
