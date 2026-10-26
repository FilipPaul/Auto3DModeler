"""The 3D model workspace (sketches -> features -> B-rep), see docs/ARCHITECTURE-modeler.md.

Its CAD kernel (OpenCASCADE through `cadquery-ocp-novtk`) and sketch solver (`planegcs`) are optional:
`py -m pip install -r requirements-modeler.txt`. Without them the app works as before.
"""
import importlib
import importlib.metadata

_PACKAGES = {"occ": ("OCP", "cadquery-ocp-novtk"), "planegcs": ("planegcs", "planegcs")}
_cache = {}


def available(name):
    """True when the optional dependency `name` ("occ" or "planegcs") can be imported."""
    if name not in _cache:
        try:
            importlib.import_module(_PACKAGES[name][0])
            _cache[name] = True
        except Exception:  # noqa: BLE001 — missing, or a broken install: either way not usable
            _cache[name] = False
    return _cache[name]


def status():
    """What the 3D model workspace can use, for /api/kernel."""
    out = {}
    for name, (_, dist) in _PACKAGES.items():
        ok = available(name)
        try:
            version = importlib.metadata.version(dist) if ok else None
        except importlib.metadata.PackageNotFoundError:
            version = None
        out[name] = {"available": ok, "version": version, "package": dist}
    out["ready"] = all(v["available"] for v in out.values())
    out["install"] = "py -m pip install -r requirements-modeler.txt"
    return out
