"""Import CAD / mesh files.

* DXF (and DWG through an installed converter) -> closed 2D regions in mm -> an outline model
  (the same tools as an outline traced from a picture: cookie cutter, solid shape, objects, clean-up).
* STL / OBJ / STEP -> triangles -> sliced into z-slabs (the app's 2.5D solid): exact for parts whose
  walls are vertical between flat faces (most plates, brackets, cutters), a stepped approximation of
  slanted / curved walls (slab height = `layer`).
"""
from __future__ import annotations

import glob
import hashlib
import math
import os
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import LineString, MultiPolygon, Polygon
from shapely.ops import polygonize, unary_union

from .design import polygons_of

MESH_FORMATS = {".stl", ".obj", ".step", ".stp"}
DRAWING_FORMATS = {".dxf", ".dwg"}
DXF_UNITS_MM = {0: 1.0, 1: 25.4, 2: 304.8, 4: 1.0, 5: 10.0, 6: 1000.0, 8: 0.0254, 9: 0.0254e-3, 10: 914.4,
                13: 1e-3, 14: 100.0}


class ImportError_(ValueError):
    pass


# =========================================================================== meshes
def read_stl(data: bytes) -> np.ndarray:
    """Binary or ASCII STL -> (n, 3, 3) float64 triangles."""
    if len(data) >= 84:
        n = struct.unpack_from("<I", data, 80)[0]
        if 84 + n * 50 == len(data):
            rec = np.frombuffer(data, dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]),
                                count=n, offset=84)
            return rec["v"].astype(np.float64)
    text = data.decode("utf-8", "ignore")
    verts = [list(map(float, line.split()[1:4])) for line in text.splitlines() if line.strip().startswith("vertex")]
    if not verts or len(verts) % 3:
        raise ImportError_("not a valid STL file")
    return np.array(verts, np.float64).reshape(-1, 3, 3)


def read_obj(text: str) -> np.ndarray:
    v, tris = [], []
    for line in text.splitlines():
        if line.startswith("v "):
            v.append([float(c) for c in line.split()[1:4]])
        elif line.startswith("f "):
            idx = [int(tok.split("/")[0]) for tok in line.split()[1:]]
            idx = [i - 1 if i > 0 else len(v) + i for i in idx]
            for k in range(1, len(idx) - 1):  # fan
                tris.append((idx[0], idx[k], idx[k + 1]))
    if not tris:
        raise ImportError_("the file contains no surfaces")
    return np.asarray(v, np.float64)[np.asarray(tris)]


def read_step(data: bytes) -> np.ndarray:
    try:
        import cascadio
    except ImportError as exc:
        raise ImportError_("STEP import needs the 'cascadio' package (pip install cascadio).") from exc
    with tempfile.TemporaryDirectory() as tmp:
        src, out = Path(tmp) / "in.step", Path(tmp) / "out.obj"
        src.write_bytes(data)
        # 0.01 mm chord tolerance: fine enough for printing, the slicer works on flat faces anyway
        cascadio.step_to_obj(str(src), str(out), tol_linear=0.01, tol_angular=0.3, use_colors=False)
        if not out.exists():
            raise ImportError_("could not read the STEP file")
        return read_obj(out.read_text(errors="ignore"))


def read_mesh(data: bytes, name: str) -> np.ndarray:
    from . import progress
    ext = Path(name).suffix.lower()
    progress.report("Reading the STEP file (tessellating)" if ext in (".step", ".stp") else f"Reading {Path(name).name}")
    if ext == ".stl":
        tris = read_stl(data)
    elif ext == ".obj":
        tris = read_obj(data.decode("utf-8", "ignore"))
    elif ext in (".step", ".stp"):
        tris = read_step(data)
    else:
        raise ImportError_(f"unsupported mesh format {ext}")
    tris = tris[np.isfinite(tris).all(axis=(1, 2))]
    if not len(tris):
        raise ImportError_("the file contains no triangles")
    return tris


UP_AXES = {  # rotation that puts the chosen axis up (z), as a 3x3 matrix
    "z": np.eye(3), "-z": np.diag([1.0, -1.0, -1.0]),
    "y": np.array([[1.0, 0, 0], [0, 0, -1.0], [0, 1.0, 0]]), "-y": np.array([[1.0, 0, 0], [0, 0, 1.0], [0, -1.0, 0]]),
    "x": np.array([[0, 0, -1.0], [0, 1.0, 0], [1.0, 0, 0]]), "-x": np.array([[0, 0, 1.0], [0, 1.0, 0], [-1.0, 0, 0]]),
}


def orient(tris: np.ndarray, up: str = "z", rot: float = 0.0, mirror: bool = False) -> np.ndarray:
    """Rotate so `up` points up, turn by `rot` degrees about z, optionally mirror x; then put the
    bounding box corner at the origin (bottom on z = 0)."""
    t = tris @ UP_AXES.get(up, np.eye(3)).T
    if rot:
        a = math.radians(rot)
        t = t @ np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1.0]]).T
    if mirror:
        t = t * np.array([-1.0, 1.0, 1.0])
        t = t[:, ::-1]  # keep the winding consistent
    return t - t.reshape(-1, 3).min(0)


def _section(tris: np.ndarray, z: float, grid: float):
    """Cross-section of a closed mesh at height z (even-odd), as a (multi)polygon — vectorised."""
    z = z + grid * 0.37  # never exactly on a vertex height (a vertex on the plane would leave a gap)
    zs = tris[:, :, 2]
    T = tris[(zs.min(1) < z) & (zs.max(1) > z)]
    if not len(T):
        return MultiPolygon()
    A, B = T, np.roll(T, -1, axis=1)  # the 3 edges of every triangle
    # order each edge's ends the same way, so the two triangles sharing an edge compute the same point
    swap = (A[..., 0] > B[..., 0]) | ((A[..., 0] == B[..., 0]) & ((A[..., 1] > B[..., 1]) |
                                                                   ((A[..., 1] == B[..., 1]) & (A[..., 2] > B[..., 2]))))
    P, Q = np.where(swap[..., None], B, A), np.where(swap[..., None], A, B)
    cross = (P[..., 2] - z) * (Q[..., 2] - z) < 0
    t = (z - P[..., 2]) / np.where(cross, Q[..., 2] - P[..., 2], 1.0)
    pts = P[..., :2] + t[..., None] * (Q[..., :2] - P[..., :2])
    two = cross.sum(1) == 2
    order = np.argsort(~cross[two], axis=1, kind="stable")[:, :2]  # the two crossing edges
    seg = np.take_along_axis(pts[two], order[..., None], axis=1)
    seg = seg[np.any(seg[:, 0] != seg[:, 1], axis=1)]
    if not len(seg):
        return MultiPolygon()
    lines = shapely.set_precision(shapely.linestrings(seg), grid)
    return MultiPolygon(polygons_of(_even_odd(shapely.union_all(lines))))


def plan_slices(tris: np.ndarray, layer: float = 0.5):
    """Where to cut: (clean triangles, grid, [(z0, z1)], stepped).

    Slab boundaries are the heights of all flat (horizontal) faces; a slab whose walls are all
    vertical has a constant section and is exact. Slabs crossing slanted walls are split every
    `layer` (stepped approximation)."""
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    ln = np.linalg.norm(n, axis=1)
    keep = ln > 1e-12
    tris, n = tris[keep], n[keep] / ln[keep, None]
    size = float(np.ptp(tris.reshape(-1, 3), axis=0).max())
    grid = 10.0 ** math.floor(math.log10(max(size, 1e-6) * 1e-6))
    zr = lambda v: round(float(v) / grid) * grid
    flat = np.abs(n[:, 2]) > 1 - 1e-6
    levels = sorted({zr(z) for z in tris[flat][:, :, 2].ravel()} | {zr(tris[:, :, 2].min()), zr(tris[:, :, 2].max())})
    zs = tris[(~flat) & (np.abs(n[:, 2]) > 1e-6)][:, :, 2]
    zlo, zhi = (zs.min(1), zs.max(1)) if len(zs) else (np.zeros(0), np.zeros(0))
    bounds, stepped = [], False
    for z0, z1 in zip(levels, levels[1:]):
        if z1 - z0 < grid * 10:
            continue
        crosses = bool(((zlo < z1 - grid) & (zhi > z0 + grid)).any())
        k = max(1, math.ceil((z1 - z0) / max(layer, 1e-3))) if crosses else 1
        stepped |= crosses
        bounds += [(z0 + (z1 - z0) * i / k, z0 + (z1 - z0) * (i + 1) / k) for i in range(k)]
    return tris, grid, bounds, stepped


def auto_layer(tris: np.ndarray, target: int = 200, layer: float = 0.5):
    """The finest 'nice' slice height (from `layer` up) that keeps the part within `target` slices."""
    for _ in range(40):
        _, _, bounds, stepped = plan_slices(tris, layer)
        if len(bounds) <= target or not stepped:
            return layer, len(bounds), stepped
        layer = next(v for v in (0.6, 0.8, 1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50, 75, 100)
                     if v > layer * 1.05) if layer < 100 else layer * 1.5
    return layer, len(bounds), stepped


def slice_mesh(tris: np.ndarray, layer: float = 0.5, max_slabs: int = 3000):
    """Triangles (oriented, bottom at z = 0) -> ([(z0, z1, MultiPolygon)], stepped)."""
    from . import progress
    tris, grid, bounds, stepped = plan_slices(tris, layer)
    if len(bounds) > max_slabs:
        raise ImportError_(f"the part would need {len(bounds)} slices — increase the slice height")
    slabs = []
    for i, (z0, z1) in enumerate(bounds):
        progress.report("Slicing", i, len(bounds))
        sec = _section(tris, (z0 + z1) / 2, grid)
        if not sec.is_empty:
            slabs.append((z0, z1, sec))
    if not slabs:
        raise ImportError_("no closed volume found (is the mesh watertight?)")
    return slabs, stepped


def _even_odd(lines):
    """The region enclosed by noded linework, even-odd: holes, and islands inside holes.
    polygonize() gives the faces of the arrangement; a face is material when an odd number of the
    faces' outer rings encloses it (counted with a spatial index — fast with thousands of faces)."""
    faces = shapely.get_parts(shapely.polygonize([lines]))
    if not len(faces):
        return Polygon()
    shells = shapely.polygons(shapely.get_exterior_ring(faces))
    inside = shapely.point_on_surface(faces)
    tree = shapely.STRtree(shells)
    pairs = tree.query(inside, predicate="within")  # [face index, shell index] for each enclosing shell
    depth = np.bincount(pairs[0], minlength=len(faces))
    solid = faces[depth % 2 == 1]
    return MultiPolygon(list(solid)) if len(solid) else Polygon()


def file_id(data: bytes, name: str) -> str:
    return hashlib.sha1(data).hexdigest()[:16] + Path(name).suffix.lower()


# =========================================================================== DXF / DWG
def _dwg_converter():
    for exe in ("ODAFileConverter", "ODAFileConverter.exe"):
        if shutil.which(exe):
            return ("oda", shutil.which(exe))
    for pattern in ("C:/Program Files/ODA/ODAFileConverter*/ODAFileConverter.exe",
                    "C:/Program Files (x86)/ODA/ODAFileConverter*/ODAFileConverter.exe",
                    "/usr/bin/ODAFileConverter", "/Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter"):
        hits = sorted(glob.glob(pattern))
        if hits:
            return ("oda", hits[-1])
    if shutil.which("dwg2dxf"):
        return ("libredwg", shutil.which("dwg2dxf"))
    return None


def dwg_to_dxf(data: bytes) -> bytes:
    conv = _dwg_converter()
    if conv is None:
        raise ImportError_("DWG is a closed format: install the free ODA File Converter "
                           "(opendesign.com/guestfiles/oda_file_converter) or LibreDWG (dwg2dxf), "
                           "or save the drawing as DXF.")
    kind, exe = conv
    with tempfile.TemporaryDirectory() as tmp:
        src_dir, out_dir = Path(tmp) / "in", Path(tmp) / "out"
        src_dir.mkdir()
        out_dir.mkdir()
        (src_dir / "drawing.dwg").write_bytes(data)
        if kind == "oda":
            cmd = [exe, str(src_dir), str(out_dir), "ACAD2018", "DXF", "0", "1", "*.DWG"]
        else:
            cmd = [exe, "-o", str(out_dir / "drawing.dxf"), str(src_dir / "drawing.dwg")]
        subprocess.run(cmd, capture_output=True, timeout=120)
        out = next(out_dir.glob("*.dxf"), None)
        if out is None:
            raise ImportError_("the DWG converter produced no DXF")
        return out.read_bytes()


def read_dxf(data: bytes, flatten: float = 0.01):
    """DXF -> ([[shell, *holes], ...] in mm, y up; issues). Closed regions formed by all lines,
    arcs, circles, polylines, splines and ellipses (also inside blocks), even-odd nested."""
    try:
        import ezdxf
        from ezdxf import path as dxfpath
    except ImportError as exc:
        raise ImportError_("DXF import needs the 'ezdxf' package (pip install ezdxf).") from exc
    from ezdxf import recover
    # from a file: handles ASCII and binary DXF, any encoding, and slightly damaged files
    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
        f.write(data)
        fname = f.name
    try:
        doc, _auditor = recover.readfile(fname)
    except Exception as exc:
        raise ImportError_(f"not a readable DXF file ({exc})") from exc
    finally:
        os.unlink(fname)
    scale = DXF_UNITS_MM.get(int(doc.header.get("$INSUNITS", 0) or 0), 1.0) or 1.0
    issues = []
    CURVES = {"LINE", "LWPOLYLINE", "POLYLINE", "ARC", "CIRCLE", "ELLIPSE", "SPLINE"}

    def entities(container, depth=0):
        for e in container:
            t = e.dxftype()
            if t in CURVES:
                yield e
            elif t == "INSERT" and depth < 8:
                try:
                    yield from entities(e.virtual_entities(), depth + 1)
                except Exception:
                    continue

    lines, skipped = [], 0
    for e in entities(doc.modelspace()):
        try:
            pts = [(v.x * scale, v.y * scale) for v in dxfpath.make_path(e).flattening(flatten / scale)]
        except Exception:
            skipped += 1
            continue
        if len(pts) >= 2:
            lines.append(LineString(pts))
    if not lines:
        raise ImportError_("no lines, arcs or polylines found in the drawing")
    size = max(max(l.bounds[2] for l in lines) - min(l.bounds[0] for l in lines),
               max(l.bounds[3] for l in lines) - min(l.bounds[1] for l in lines))
    grid = 10.0 ** math.floor(math.log10(max(size, 1e-6) * 1e-5))
    noded = shapely.set_precision(unary_union(lines), grid)  # joins ends closer than ~1e-5 of the drawing
    polys = polygons_of(_even_odd(noded))
    if not polys:
        raise ImportError_("the drawing has no closed outline (check for gaps between lines)")
    _faces, cuts, dangles, _invalid = shapely.polygonize_full([noded])
    dangles = len(shapely.get_parts(dangles)) + len(shapely.get_parts(cuts))
    if dangles:
        issues.append({"severity": "warning", "code": "open_contour", "params": [],
                       "message": f"{dangles} open line(s) in the drawing do not form a closed outline and were ignored."})
    if skipped:
        issues.append({"severity": "info", "code": "skipped", "params": [], "message": f"{skipped} entities could not be read."})
    ring = lambda r: [[round(x, 6), round(y, 6)] for x, y in r.coords[:-1]]
    return [[ring(p.exterior)] + [ring(h) for h in p.interiors] for p in polys], issues
