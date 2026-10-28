"""Exact print pieces (in the kernel worker): a part with an exact model — the printing copy of a 3D model part, any
STEP file opened as a quick part — cut into the pieces the print planner chose (printing.plan, joints.py). The cells
and the joints' pockets are the same shapely polygons the slab pieces are cut with, built here as B-rep prisms, so
curved walls stay smooth; each piece is meshed finely (STL) or written as it is (STEP).

Request (auto3d/printexact.py):
  {"file": the STEP file, "m": 3 x 3 (the quick part's orientation: up / turn / mirror), "k": its scale,
   "pieces": [{"keep": [[z0, z1, polys], …] (None: the whole part; z None: its whole height),
               "voids": [[polys, z0, z1], …] (z None: through the part's bottom / top), "flip": printed upside down}],
   "out": "mesh" (where it is, for the preview) | "stl" | "step" (turned as printed, at the origin)}
polys = [[outer ring, hole rings …], …] in mm. Answer: per piece {positions (float32 bytes), volume, faces, solids,
bbox, data (the file's bytes for stl / step)} or None (nothing of the part in it).
"""
from __future__ import annotations

import json
from collections import OrderedDict

import numpy as np

from . import kernel as K

_parts: OrderedDict = OrderedDict()  # (file, m, k) -> the part turned, on the bed, scaled (a split is re-run often)


def tolerance(size):
    """The chord tolerance of a printed mesh (mm): 0.01, a little coarser on very big parts."""
    return max(0.01, float(size) * 2e-5)


def part(path, m, k=1.0):
    """The STEP's shape turned by m, its box's corner moved to the origin (bottom on the bed), scaled by k — as the
    quick part's slices are (importers.orient, meshpart.solve_mesh)."""
    key = (path, json.dumps(np.asarray(m, float).round(9).tolist()), round(float(k), 9))
    if key in _parts:
        _parts.move_to_end(key)
        return _parts[key]
    with open(path, "rb") as fh:
        shape = K.from_step(fh.read())
    turned = K.transformed(shape, m)
    lo = K.bbox(turned)[:3]
    shape = K.transformed(turned, np.eye(3) * k, [-k * v for v in lo])
    _parts[key] = shape
    while len(_parts) > 4:
        _parts.popitem(last=False)
    return shape


def cut_piece(shape, keep, voids, zlo, zhi):
    """The part ∩ the piece's cell (layers of prisms) − its pockets; None when nothing is left."""
    piece = shape
    if keep is not None:
        cells = [s for z0, z1, polys in keep for s in K.prisms(polys, zlo if z0 is None else z0, zhi if z1 is None else z1)]
        if not cells:
            return None
        if len(cells) > 1 and len(keep) > 1:  # layers (a hidden dovetail under a straight skin): one cell
            cells = [K.unified(K.boolean("fuse", cells[:1], cells[1:]))]
        piece = K.boolean("common", [piece], cells)
    tools = [s for polys, z0, z1 in voids or [] for s in K.prisms(polys, zlo if z0 is None else z0, zhi if z1 is None else z1)]
    if tools:
        piece = K.boolean("cut", [piece], tools)
    if K.volume(piece) <= 1e-9:
        return None
    return K.unified(piece)


def pieces(a):
    shape = part(a["file"], a.get("m") or np.eye(3).tolist(), float(a.get("k") or 1.0))
    bb = K.bbox(shape)
    zlo, zhi = bb[2] - 1, bb[5] + 1
    tol = float(a.get("tol") or tolerance(max(bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2])))
    out_fmt, out = a.get("out", "mesh"), []
    for p in a["pieces"]:
        piece = cut_piece(shape, p.get("keep"), p.get("voids"), zlo, zhi)
        if piece is None:
            out.append(None)
            continue
        vol = K.volume(piece)
        if out_fmt != "mesh":  # as printed: turned over when its pockets open downwards, its corner at the origin
            if p.get("flip"):
                piece = K.turned_over(piece)
            lo = K.bbox(piece)[:3]
            piece = K.transformed(piece, np.eye(3), [-v for v in lo])
        res = {"volume": vol, "faces": K.face_count(piece), "solids": K.solids(piece), "bbox": K.bbox(piece), "tol": tol}
        if out_fmt == "step":
            res["data"] = K.to_step(piece)
            res["positions"] = b""
        else:
            tris = K.print_triangles(piece, tol)
            res["positions"] = tris.astype(np.float32).tobytes()
            if out_fmt == "stl":
                res["data"] = K.to_stl(tris)
        out.append(res)
    return out
