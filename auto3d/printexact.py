"""Exact print pieces for parts that have an exact model: the printing copy of a 3D model part (🖨 Prepare for 3D
print opens it as a STEP quick part) and any STEP file opened as a quick part.

The planner (printing.plan, joints.py) works on the part's slices as before — where to cut, the bed fit, the joints'
places — and gives every piece its cell and pockets as shapely polygons; the kernel worker (modeler/printsplit.py)
cuts the exact B-rep with the same polygons as prisms, so curved walls stay smooth (no stairs). Without the kernel,
for a part with 3D objects added, bends, or an STL / OBJ the slab pieces stay as they are.
"""
from __future__ import annotations

import base64
import math

import numpy as np
from shapely.geometry.polygon import orient

from .design import polygons_of
from .importers import UP_AXES


def source(model, solution, bender=None):
    """The exact model a quick part's pieces can be cut from ({file, m, k}), or None (the slab pieces stay)."""
    from . import meshpart
    from .modeler import available
    mid = str(model.get("mesh_id") or "")
    if model.get("kind") != "mesh" or not mid.lower().endswith((".step", ".stp")) or bender is not None:
        return None
    if model.get("extras") or not available("occ"):
        return None
    path = meshpart.STORE / mid
    if not path.exists():
        return None
    o = model.get("mesh_opts") or {}
    m = UP_AXES.get(o.get("up", "z"), np.eye(3))
    if o.get("rot"):
        a = math.radians(float(o["rot"]))
        m = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1.0]]) @ m
    if o.get("mirror"):
        m = np.diag([-1.0, 1.0, 1.0]) @ m
    k = float((solution.get("values") or {}).get("scale", 100.0)) / 100.0
    return {"file": str(path), "m": np.asarray(m, float).tolist(), "k": k}


def _rings(geom):
    """A shapely region -> [[outer ring, hole rings …], …] (counter-clockwise outside, clockwise holes)."""
    out = []
    for p in polygons_of(geom):
        p = orient(p, 1.0)
        out.append([[list(c) for c in p.exterior.coords[:-1]]] + [[list(c) for c in r.coords[:-1]] for r in p.interiors])
    return out


def request(piece, z_range):
    """A planned piece's cell and pockets as the kernel takes them. A pocket open to the part's bottom or top (the
    slices' z_range) goes through the exact part's face (None): the slices end a hair inside a curved one."""
    lo, hi = z_range
    eps = 1e-6 * max(1.0, hi - lo)
    region = piece["cell_region"]
    keep = [[z0, z1, _rings(g)] for z0, z1, g in region] if isinstance(region, list) else [[None, None, _rings(region)]]
    voids = [[_rings(g), None if z0 <= lo + eps else z0, None if z1 >= hi - eps else z1]
             for g, z0, z1 in piece.get("voids") or [] if g is not None and not g.is_empty and z1 > z0]
    return {"keep": keep, "voids": voids, "flip": bool(piece.get("flip"))}


def cut(result, src, worker, out="mesh"):
    """Cut the planned pieces from the exact model (in place): each piece's mesh / file, its size and fit from the exact
    shape. Returns the pieces' answers from the kernel, or None when it could not (the slab pieces stay, with a
    warning in the result's issues)."""
    from .modeler.worker import KernelFailed, KernelUnavailable
    pieces = result["pieces"]
    if not pieces:
        return None
    try:
        got = worker.run("print_pieces", {**src, "pieces": [request(p, result["z_range"]) for p in pieces], "out": out}, timeout=300)
    except (KernelFailed, KernelUnavailable) as exc:
        result["issues"].append({"severity": "warning", "message": f"The exact split did not work ({exc}) — the pieces "
                                 "are built from slices, so curved walls are steps."})
        return None
    ux, uy, uz = result["usable_mm"]
    for p, g in zip(pieces, got):
        if g is None:  # (a sliver the slices had, the exact part has not)
            continue
        x0, y0, z0, x1, y1, z1 = g["bbox"]
        w, h, z = x1 - x0, y1 - y0, z1 - z0
        if out == "mesh":  # (exported pieces may be turned over: the size as it lies in the part)
            p["size_mm"] = (w, h, z)
            fits = z <= uz + 1e-9 and ((w <= ux + 1e-9 and h <= uy + 1e-9) or (h <= ux + 1e-9 and w <= uy + 1e-9))
            p["orientation"] = ("flat" if w <= ux + 1e-9 and h <= uy + 1e-9 else "rotated") if fits else "too big"
        p["exact"] = {"faces": g["faces"], "triangles": len(g["positions"]) // 36, "volume": g["volume"], "tol": g["tol"]}
    result["exact"] = True
    tol = max((g["tol"] for g in got if g), default=0.01)
    result["issues"].insert(0, {"severity": "info", "message": f"Exact split: the pieces are cut from the exact model, "
                                f"so curved walls stay smooth (meshed within {tol:g} mm)."})
    return got


def whole(src, worker, fmt):
    """The whole part as an exact file (fine STL / STEP), or None when the kernel could not (the slab one is used)."""
    from .modeler.worker import KernelFailed, KernelUnavailable
    try:
        got = worker.run("print_pieces", {**src, "pieces": [{"keep": None, "voids": []}], "out": fmt}, timeout=300)
    except (KernelFailed, KernelUnavailable):
        return None
    return got[0]["data"] if got and got[0] else None


def mesh_payload(g):
    """A piece's fine mesh in the viewer's format (export.mesh_payload)."""
    n = len(g["positions"]) // 36
    return {"positions": base64.b64encode(g["positions"]).decode(), "tags": base64.b64encode(bytes(n)).decode(), "count": n}
