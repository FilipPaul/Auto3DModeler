"""Parts imported from a 3D file (STL / OBJ / STEP): oriented, scaled, sliced into the app's 2.5D
solid, then extra 3D objects (holes, bars, text …) are booleaned in like on any other part.

The triangles are kept on the server (in memory and in data/imports/, keyed by a hash of the file);
the model only refers to them by id, so it stays small (projects carry the file itself).
"""
from __future__ import annotations

import os
import threading
from functools import lru_cache
from pathlib import Path

import numpy as np
from shapely import affinity
from shapely.geometry import MultiPolygon

from .design import polygons_of
from .importers import ImportError_, auto_layer, file_id, orient, read_mesh, slice_mesh
from .outline import add_objects
from .solid import Solid

STORE = Path(os.environ.get("A3D_DATA") or Path(__file__).resolve().parent.parent / "data") / "imports"
_meshes: dict[str, np.ndarray] = {}
_lock = threading.Lock()


def register(data: bytes, name: str) -> str:
    """Remember an imported 3D file; returns its id (the same file always gets the same id)."""
    mid = file_id(data, name)
    with _lock:
        if mid not in _meshes:
            _meshes[mid] = read_mesh(data, name)
            STORE.mkdir(parents=True, exist_ok=True)
            path = STORE / mid
            if not path.exists():
                path.write_bytes(data)
    return mid


def triangles(mid: str) -> np.ndarray:
    with _lock:
        if mid in _meshes:
            return _meshes[mid]
    path = STORE / mid
    if not path.exists():
        raise ImportError_("the imported file is no longer on the server — open the project again")
    return _meshes.setdefault(mid, read_mesh(path.read_bytes(), mid))


@lru_cache(maxsize=16)
def _sliced(mid: str, up: str, rot: float, mirror: bool, layer: float):
    tris = orient(triangles(mid), up, rot, mirror)
    slabs, stepped = slice_mesh(tris, layer)
    return slabs, stepped, tuple(np.ptp(tris.reshape(-1, 3), axis=0))


def mesh_model(data: bytes, name: str) -> dict:
    mid = register(data, name)
    model = {
        "kind": "mesh", "unit": "mm", "source": name, "mesh_id": mid, "loops": [], "issues": [],
        "mesh_opts": {"up": "z", "rot": 0, "mirror": False, "layer": 0.5},
        "params": [{"id": "scale", "name": "Scale", "value": 100.0, "unit": "%", "role": "driving",
                    "source": "outline", "kind": "scale"}] + [
            # measured sizes (driven by the file and the scale)
            {"id": f"size_{a}", "name": f"Size {a.upper()}", "value": 0.0, "unit": "mm", "role": "reference",
             "source": "outline", "kind": "size"} for a in "xyz"],
        "extras": [],   # 3D objects added to the imported part
    }
    # curved / slanted parts: a slice height that keeps the first build quick (finer is one setting away)
    layer, count, stepped = auto_layer(orient(triangles(mid)), target=250)
    model["mesh_opts"]["layer"] = layer
    if stepped:
        model["issues"].append({"severity": "info", "code": "slices", "params": [],
                                "message": f"Slanted / curved walls are built in {count} slices of {layer:g} mm"
                                           + (" (chosen so the part builds quickly — a smaller slice height in the Part tab "
                                              "gives a finer result)." if layer > 0.5 else ".")})
    _, _, size = _sliced(mid, "z", 0.0, False, layer)
    model["size"] = [float(v) for v in size]
    return model


def solve_mesh(model: dict, overrides: dict | None = None, layers=None):
    """Returns (solution, solid) like solve_outline."""
    values = {p["id"]: float(p["value"]) for p in model["params"]}
    values.update({k: float(v) for k, v in (overrides or {}).items() if k in values})
    issues = []

    def issue(sev, msg, code="invalid_value", params=()):
        issues.append({"severity": sev, "code": code, "message": msg, "params": list(params)})

    fail = lambda: ({"ok": False, "issues": issues, "values": values, "loops": [], "thickness": 1.0,
                     "bbox": [0, 0, 1, 1], "annotations": []}, None)
    k = values.get("scale", 100.0) / 100.0
    if not k > 0:
        issue("error", "Scale must be greater than zero.", params=["scale"])
        return fail()
    o = model.get("mesh_opts") or {}
    try:
        slabs, stepped, _ = _sliced(model["mesh_id"], o.get("up", "z"), float(o.get("rot") or 0),
                                    bool(o.get("mirror")), max(float(o.get("layer") or 0.5), 0.05))
    except ImportError_ as exc:
        issue("error", str(exc), "import")
        return fail()
    # uniform scale (x, y and z)
    slabs = [(z0 * k, z1 * k, affinity.scale(sec, k, k, origin=(0, 0))) for z0, z1, sec in slabs]
    solid = Solid.from_slabs(slabs)
    if stepped:
        issue("info", f"Slanted or curved walls are built as steps of {o.get('layer', 0.5)} mm "
                      "(set a smaller slice height for a finer result).", "stepped")
    if layers:
        issue("info", "Design layers apply to flat parts (drawings, outlines); on an imported 3D part use "
                      "3D objects instead (e.g. subtract a text object to engrave it).", "layers")
    foot = solid.profile
    regions = []
    solid = add_objects(solid, model.get("extras"), foot, issue, regions)
    if not solid.slabs:
        issue("error", "Nothing is left of the part.", "invalid_geometry")
        return fail()
    x0, y0, x1, y1 = solid.xy_bounds()
    zlo, zhi = solid.z_range()
    biggest = max(polygons_of(foot), key=lambda p: p.area)
    ring = lambda r: [list(c) for c in r.coords[:-1]]
    gap = 0.06 * max(x1 - x0, y1 - y0)
    values.update({"size_x": x1 - x0, "size_y": y1 - y0, "size_z": zhi - zlo})
    solution = {
        "ok": not any(i["severity"] == "error" for i in issues), "issues": issues, "values": values,
        "levels": {}, "loops": [{"id": "outer", "kind": "outer", "name": "Footprint", "points": ring(biggest.exterior)}],
        "thickness": zhi, "bbox": [x0, y0, x1, y1], "z_range": [zlo, zhi], "z_levels": list(solid.levels),
        "objects": model.get("extras") or [], "outline_bbox": [x0, y0, x1, y1], "object_regions": regions,
        "outline_2d": [[ring(p.exterior)] + [ring(r) for r in p.interiors] for p in polygons_of(foot)],
        "annotations": [
            {"param": "size_x", "p1": [x0, y0 - gap], "p2": [x1, y0 - gap], "value": x1 - x0, "z": zhi},
            {"param": "size_y", "p1": [x1 + gap, y0], "p2": [x1 + gap, y1], "value": y1 - y0, "z": zhi},
        ],
    }
    return solution, (solid if solution["ok"] else None)
