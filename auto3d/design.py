"""Surface design layers -> 2D regions on a face of the part.

A layer is ``mask x fill``:

* mask  – where the layer applies: the whole face (inset by a margin), a
  rectangle, an ellipse or a traced image (logo); optionally inverted;
* fill  – ``solid`` or a grid pattern (square, hex, ...), using either the
  pattern *lines* or the *cells* between them.

The resulting region is turned into geometry by :mod:`auto3d.solid` according
to the layer operation (emboss / engrave / cut through / guide).
All values are in model units.
"""
from __future__ import annotations

import base64
import io
import math
import random

import shapely
from shapely import affinity
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

OPS = ("emboss", "engrave", "cut", "guide")


def _fmt(v: float) -> str:
    return f"{v:.3f}".rstrip("0").rstrip(".")


def precision_grid(size: float) -> float:
    """Snapping grid for boolean results: a power of ten (~1e-6 of the part) so that
    typical dimension values such as 78.7 stay exactly representable."""
    return 10.0 ** math.floor(math.log10(max(size, 1e-9) * 1e-6))


def profile_polygon(solution: dict) -> Polygon:
    if solution.get("_profile") is not None:  # free-form outline (image models): any (multi)polygon
        return solution["_profile"]
    loops = solution["loops"]
    return Polygon(loops[0]["points"], [l["points"] for l in loops[1:]])


# --------------------------------------------------------------------------- masks
def mask_region(layer: dict, face_area, bbox) -> shapely.Geometry:
    m = layer.get("mask") or {"kind": "face"}
    kind = m.get("kind", "face")
    if kind == "face":
        region = face_area
    else:
        cx, cy = float(m.get("x", 0)), float(m.get("y", 0))
        w, h = max(float(m.get("w", 1)), 1e-6), max(float(m.get("h", 1)), 1e-6)
        if kind == "rect":
            region = box(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
        elif kind == "ellipse":
            region = affinity.scale(Point(cx, cy).buffer(0.5, quad_segs=32), w, h)
        elif kind == "image":
            polys = []
            for shell, *holes in m.get("polygons") or []:
                polys.append(Polygon(shell, holes))
            unit = unary_union(polys) if polys else Polygon()
            region = affinity.translate(affinity.scale(unit, w, h, origin=(0, 0)), cx, cy)
        else:
            raise ValueError(f"unknown mask '{kind}'")
        rot = float(m.get("rot", 0) or 0)
        if rot:
            region = affinity.rotate(region, rot, origin=(cx, cy))
    if m.get("invert"):
        region = face_area.difference(region)
    return region


# --------------------------------------------------------------------------- patterns
# Line patterns produce centre-lines (buffered to `width`); motif patterns produce
# filled shapes. "use = lines" gives ribs (line pattern) / outlines (motifs),
# "use = cells" gives the areas between lines / the filled motifs.
LINE_PATTERNS = {"square", "rect", "columns", "diamond", "triangle", "hex", "radial", "waves", "zigzag", "chevron",
                 "brick", "scales", "voronoi", "contour", "spiral"}
MOTIF_PATTERNS = {"dots", "checker", "circles", "stars", "crosses"}


def _pattern(fill, bbox, mask):
    """Return (lines, motifs) for a pattern, in model coordinates (either may be None)."""
    kind = fill.get("pattern", "square")
    sx = max(float(fill.get("sx") or 1), 1e-3)
    sy = max(float(fill.get("sy") or sx), 1e-3)
    angle = float(fill.get("angle") or 0)
    amp = float(fill.get("amp") if fill.get("amp") is not None else 0.25) * sx
    size = min(max(float(fill.get("size") or 0.6), 0.05), 1.0)
    x0, y0, x1, y1 = bbox
    if fill.get("origin", "center") == "corner":
        ox, oy = x0, y0
    else:
        ox, oy = (x0 + x1) / 2, (y0 + y1) / 2
    ox += float(fill.get("ox") or 0)
    oy += float(fill.get("oy") or 0)
    # Work only over the target box, expressed in the pattern's own (rotated, shifted) frame.
    pad = 2 * max(sx, sy) + amp
    a = math.radians(angle)
    local = [((cx - ox) * math.cos(a) + (cy - oy) * math.sin(a), -(cx - ox) * math.sin(a) + (cy - oy) * math.cos(a))
             for cx, cy in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    lx0, lx1 = min(p[0] for p in local) - pad, max(p[0] for p in local) + pad
    ly0, ly1 = min(p[1] for p in local) - pad, max(p[1] for p in local) + pad
    R = max(math.hypot(px, py) for px, py in ((lx0, ly0), (lx1, ly0), (lx1, ly1), (lx0, ly1)))

    lines: list = []
    motifs: list = []

    def family(step, deg):
        """Parallel lines with spacing `step`, at `deg` from the local y axis, covering the local box."""
        t = math.radians(deg)
        n = (math.cos(t), math.sin(t))   # line normal
        d = (-n[1], n[0])                 # line direction
        corners = ((lx0, ly0), (lx1, ly0), (lx1, ly1), (lx0, ly1))
        proj = [c[0] * n[0] + c[1] * n[1] for c in corners]
        along = [c[0] * d[0] + c[1] * d[1] for c in corners]
        a0, a1 = min(along), max(along)
        for i in range(math.floor(min(proj) / step), math.ceil(max(proj) / step) + 1):
            p = (n[0] * i * step, n[1] * i * step)
            lines.append(LineString([(p[0] + d[0] * a0, p[1] + d[1] * a0), (p[0] + d[0] * a1, p[1] + d[1] * a1)]))

    def wavy(step, shape):
        """Horizontal rows (spacing `step`) of a periodic curve; shape(t) in [-1, 1] for t in [0, 1)."""
        samples = max(8, int((lx1 - lx0) / sx * 16))
        xs = [lx0 + (lx1 - lx0) * i / samples for i in range(samples + 1)]
        for j in range(math.floor(ly0 / step), math.ceil(ly1 / step) + 1):
            lines.append(LineString([(x, j * step + amp * shape((x / sx) % 1.0)) for x in xs]))

    def grid_centres(stx, sty, stagger=False):
        for j in range(math.floor(ly0 / sty), math.ceil(ly1 / sty) + 1):
            off = stx / 2 if stagger and j & 1 else 0
            for i in range(math.floor(lx0 / stx) - 1, math.ceil(lx1 / stx) + 1):
                yield i * stx + off, j * sty, i, j

    tri = lambda t: 4 * t - 1 if t < 0.5 else 3 - 4 * t

    if kind == "square":
        family(sx, 0), family(sx, 90)
    elif kind == "rect":
        family(sx, 0), family(sy, 90)
    elif kind == "columns":
        family(sx, 0)
    elif kind == "diamond":
        family(sx, 45), family(sx, -45)
    elif kind == "triangle":
        h = sx * math.sqrt(3) / 2
        family(h, 0), family(h, 60), family(h, 120)
    elif kind == "hex":
        r = sx / 2
        w, hh = 1.5 * r, math.sqrt(3) * r
        segs = set()
        for i in range(math.floor(lx0 / w) - 1, math.ceil(lx1 / w) + 2):
            for j in range(math.floor(ly0 / hh) - 1, math.ceil(ly1 / hh) + 2):
                cx, cy = i * w, j * hh + (hh / 2 if i & 1 else 0)
                pts = [(round(cx + r * math.cos(math.pi / 3 * k), 9), round(cy + r * math.sin(math.pi / 3 * k), 9))
                       for k in range(6)]
                for k in range(6):
                    a, b = pts[k], pts[(k + 1) % 6]
                    segs.add((min(a, b), max(a, b)))
        lines += [LineString(s) for s in segs]
    elif kind == "radial":
        r = sx
        while r <= R:
            lines.append(Point(0, 0).buffer(r, quad_segs=24).exterior)
            r += sx
        rays = int(fill.get("rays") or 24)
        for k in range(rays):
            a = 2 * math.pi * k / rays
            lines.append(LineString([(0, 0), (R * math.cos(a), R * math.sin(a))]))
    elif kind == "waves":
        wavy(sy, lambda t: math.sin(2 * math.pi * t))
    elif kind == "zigzag":
        wavy(sy, tri)
    elif kind == "chevron":
        wavy(sy, tri)  # zigzag rows split into columns at every apex -> herringbone / chevron look
        family(sx / 2, 0)
    elif kind == "brick":
        for j in range(math.floor(ly0 / sy), math.ceil(ly1 / sy) + 1):
            lines.append(LineString([(lx0, j * sy), (lx1, j * sy)]))
            off = sx / 2 if j & 1 else 0
            for i in range(math.floor(lx0 / sx) - 1, math.ceil(lx1 / sx) + 1):
                lines.append(LineString([(i * sx + off, j * sy), (i * sx + off, (j + 1) * sy)]))
    elif kind == "scales":
        r = sx / 2
        for cx, cy, _, _ in grid_centres(sx, r, stagger=True):
            lines.append(LineString([(cx + r * math.cos(a), cy + r * math.sin(a))
                                     for a in (math.pi + math.pi * k / 10 for k in range(11))]))
    elif kind == "voronoi":
        rng = random.Random(int(fill.get("seed") or 1))
        jitter = min(max(float(fill.get("jitter") if fill.get("jitter") is not None else 0.8), 0.0), 1.0)
        pts = [(cx + (rng.random() - 0.5) * jitter * sx, cy + (rng.random() - 0.5) * jitter * sy)
               for cx, cy, _, _ in grid_centres(sx, sy, stagger=True)]
        cells = shapely.voronoi_polygons(shapely.MultiPoint(pts))
        lines += [c.exterior for c in cells.geoms]
    elif kind == "spiral":
        turns = R / sx
        steps = int(turns * 64) + 2
        lines.append(LineString([(sx * th / (2 * math.pi) * math.cos(th), sx * th / (2 * math.pi) * math.sin(th))
                                 for th in (2 * math.pi * turns * k / steps for k in range(steps + 1))]))
    elif kind == "contour":
        pass  # built below in absolute coordinates: rings that follow the mask outline
    elif kind == "dots":
        for cx, cy, _, _ in grid_centres(sx, sy):
            motifs.append(Point(cx, cy).buffer(size * min(sx, sy) / 2, quad_segs=8))
    elif kind == "circles":
        for cx, cy, _, _ in grid_centres(sx, sx * math.sqrt(3) / 2, stagger=True):
            motifs.append(Point(cx, cy).buffer(size * sx / 2, quad_segs=8))
    elif kind == "checker":
        for cx, cy, i, j in grid_centres(sx, sy):
            if (i + j) & 1 == 0:
                motifs.append(box(cx - sx / 2, cy - sy / 2, cx + sx / 2, cy + sy / 2))
    elif kind == "stars":
        n = max(3, int(fill.get("points") or 5))
        ro = size * sx / 2
        ri = ro * 0.45
        star = Polygon([((ro if k % 2 == 0 else ri) * math.cos(math.pi / 2 + math.pi * k / n),
                         (ro if k % 2 == 0 else ri) * math.sin(math.pi / 2 + math.pi * k / n)) for k in range(2 * n)])
        for cx, cy, _, _ in grid_centres(sx, sy, stagger=True):
            motifs.append(affinity.translate(star, cx, cy))
    elif kind == "crosses":
        a, b = size * sx / 2, size * sx / 6
        cross = box(-a, -b, a, b).union(box(-b, -a, b, a))
        for cx, cy, _, _ in grid_centres(sx, sy):
            motifs.append(affinity.translate(cross, cx, cy))
    else:
        raise ValueError(f"unknown pattern '{kind}'")

    def place(g):
        return affinity.translate(affinity.rotate(g, angle, origin=(0, 0)), ox, oy)

    clip = box(*bbox).buffer(max(sx, sy))
    geo_lines = place(MultiLineString(lines)).intersection(clip) if lines else None
    geo_motifs = place(unary_union(motifs)).intersection(clip) if motifs else None
    if kind == "contour" and not mask.is_empty:
        rings, d = [], sx / 2
        while len(rings) < 2000:
            inner = mask.buffer(-d, join_style="mitre")
            if inner.is_empty:
                break
            rings.append(inner.boundary)
            d += sx
        geo_lines = unary_union(rings) if rings else None
    return geo_lines, geo_motifs


def fill_region(layer: dict, mask, bbox):
    fill = layer.get("fill") or {"pattern": "solid"}
    kind = fill.get("pattern", "solid")
    if kind == "solid":
        return mask
    width = max(float(fill.get("width") or 0.1), 1e-4)
    lines, motifs = _pattern(fill, mask.bounds if not mask.is_empty else bbox, mask)
    use_cells = fill.get("use", "lines") == "cells"
    rib = lambda g: g.buffer(width / 2, cap_style="flat", join_style="mitre", quad_segs=4)
    if kind in MOTIF_PATTERNS:
        if motifs is None or motifs.is_empty:
            return Polygon()
        # cells = the filled shapes, lines = their outlines as ribs
        filled = MultiPolygon(polygons_of(motifs))
        return mask.intersection(filled if use_cells else rib(filled.boundary))
    pattern = rib(lines) if lines is not None and not lines.is_empty else Polygon()
    return mask.difference(pattern) if use_cells else mask.intersection(pattern)


def polygons_of(g) -> list[Polygon]:
    """All non-degenerate polygons in any geometry (drops stray lines/points from booleans)."""
    if g is None or g.is_empty:
        return []
    if not g.is_valid:
        g = g.buffer(0)
    if isinstance(g, Polygon):
        return [g] if g.area > 1e-12 else []
    return [p for part in getattr(g, "geoms", []) for p in polygons_of(part)]


def _clean(g):
    polys = polygons_of(g)
    return MultiPolygon(polys) if polys else MultiPolygon()


def layer_regions(solution: dict, layers: list[dict], unit: str = "mm"):
    """Compute each visible layer's final 2D region. Returns (regions, issues)."""
    profile = profile_polygon(solution)
    bbox = solution["bbox"]
    t = solution["thickness"]
    size = max(bbox[2] - bbox[0], bbox[3] - bbox[1])
    grid = precision_grid(size)
    issues, out = [], []
    min_feature_mm = 0.4
    mm = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4}.get(unit, 1.0)

    for layer in layers:
        if not layer.get("visible", True):
            continue
        name = layer.get("name") or "Layer"
        op = layer.get("op", "emboss")
        depth = float(layer.get("depth") or 0)

        def issue(sev, msg):
            issues.append({"severity": sev, "code": "design", "message": f"{name}: {msg}", "layer": layer.get("id"),
                           "params": []})

        if op not in OPS:
            issue("error", f"unknown operation '{op}'.")
            continue
        if op in ("emboss", "engrave") and not depth > 0:
            issue("error", "height/depth must be greater than zero.")
            continue
        if op == "engrave" and depth >= t - 1e-9:
            issue("error", f"engrave depth {_fmt(depth)} {unit} is not less than the thickness "
                           f"{_fmt(t)} {unit} — use 'Cut through' instead.")
            continue
        margin = float(layer.get("margin") or 0)
        face_area = profile.buffer(-margin, join_style="mitre") if margin > 0 else profile
        try:
            mask = mask_region(layer, face_area, bbox)
            region = fill_region(layer, mask, bbox).intersection(face_area)
        except (ValueError, shapely.errors.GEOSException) as exc:
            issue("error", f"could not build the pattern ({exc}).")
            continue
        # 0.02 mm is far below any FDM resolution (~0.1 mm); dropping finer detail keeps meshes small
        region = _clean(shapely.set_precision(region.simplify(0.02 / mm), grid))
        if region.is_empty:
            issue("warning", "has no effect — it lies outside the face (check its mask, position and margin).")
            continue
        if op != "guide":
            r = min_feature_mm / 2 / mm
            opened = region.buffer(-r).buffer(r)
            if region.area > 0 and (region.area - opened.area) / region.area > 0.05:
                issue("warning", f"contains features thinner than {min_feature_mm} mm that may not 3D-print "
                                 "(increase line width / spacing).")
        out.append({"id": layer.get("id"), "name": name, "face": layer.get("face", "top"), "op": op,
                    "depth": depth, "geom": region})
    return out, issues


# --------------------------------------------------------------------------- image tracing
def trace_image(data_url: str, threshold: int = 128, invert: bool = False, max_px: int = 256):
    """Trace a raster logo into polygons normalised to a unit box centred at 0 (y up).

    Transparent images use the alpha channel; opaque images treat dark pixels as the shape.
    Returns {"polygons": [[shell, hole, ...], ...], "aspect": w/h}.
    """
    from PIL import Image

    raw = base64.b64decode(data_url.split(",", 1)[-1])
    im = Image.open(io.BytesIO(raw))
    im.load()
    im = im.convert("RGBA")
    scale = max_px / max(im.size)
    if scale < 1:
        im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.LANCZOS)
    w, h = im.size
    px = im.load()
    alpha_used = any(px[x, y][3] < 250 for x in range(0, w, max(1, w // 64)) for y in range(0, h, max(1, h // 64)))

    def on(x, y):
        r, g, b, a = px[x, y]
        v = a >= threshold if alpha_used else (0.299 * r + 0.587 * g + 0.114 * b) < threshold and a > 0
        return v != invert

    boxes = []
    for y in range(h):
        x = 0
        while x < w:
            if on(x, y):
                s = x
                while x < w and on(x, y):
                    x += 1
                boxes.append(box(s, h - y - 1, x, h - y))
            else:
                x += 1
    if not boxes:
        return {"polygons": [], "aspect": w / h}
    shape = unary_union(boxes).simplify(0.6)
    shape = affinity.translate(shape, -w / 2, -h / 2)
    shape = affinity.scale(shape, 1 / w, 1 / h, origin=(0, 0))
    polys = []
    for p in getattr(shape, "geoms", [shape]):
        if isinstance(p, Polygon) and p.area > 1e-5:
            polys.append([[list(c) for c in p.exterior.coords[:-1]]] +
                         [[list(c) for c in r.coords[:-1]] for r in p.interiors])
    return {"polygons": polys, "aspect": w / h}
