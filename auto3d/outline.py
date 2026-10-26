"""Image outlines -> 2D shape -> 3D bodies (cookie cutters, solid shapes, offset stacks).

1. Detection (:func:`detect_outlines`): several independent segmentations of the picture
   (background colour model, GrabCut, colour clustering, luminance / saturation thresholds,
   edges) each give foreground masks; their connected regions become candidates.  Candidates
   that several methods agree on, with a strong colour edge along their boundary, rank first.
   The user can steer it with object / background colours and a click inside the object.
2. Model (:func:`outline_model`): the chosen outline (image pixels) plus the real-life size,
   extra 2D shapes (circles, rectangles, lines) and the 3D build (bodies).
3. Solve (:func:`solve_outline`): outline scaled to size, shapes added / subtracted, then every
   body is an extruded region — a fill (outline grown / shrunk by an offset) or a band between
   two offsets of the outline — between two heights.  The first body is the base part that
   design layers apply to; the others and extruded shapes are merged into it.
"""
from __future__ import annotations

import base64
import math

import cv2
import numpy as np
import shapely
from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

from .design import polygons_of, precision_grid
from .solid import Solid

MAX_PX = 640          # detection works on images scaled down to this size
SHAPE_OPS = ("add", "subtract", "extrude", "cut")


def _fmt(v: float) -> str:
    return f"{v:.3f}".rstrip("0").rstrip(".")


# =========================================================================== detection
def decode_image(data_url: str) -> np.ndarray:
    """Data URL / base64 -> RGB uint8 array (transparent pixels composited on white)."""
    raw = base64.b64decode(data_url.split(",", 1)[-1])
    im = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_UNCHANGED)
    if im is None:
        raise ValueError("unsupported image format")
    if im.ndim == 2:
        im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGR)
    if im.shape[2] == 4:
        a = im[:, :, 3:4].astype(np.float32) / 255
        im = (im[:, :, :3] * a + 255 * (1 - a)).astype(np.uint8)
    return cv2.cvtColor(im, cv2.COLOR_BGR2RGB)


def _lab(rgb: np.ndarray) -> np.ndarray:
    """CIE Lab in float (L 0..100, a/b roughly -128..127) — distances are perceptual."""
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    lab[..., 0] *= 100 / 255
    lab[..., 1:] -= 128
    return lab


def _border_pixels(lab: np.ndarray, frac=0.04) -> np.ndarray:
    h, w = lab.shape[:2]
    # skip the outermost pixels: photos often have a thin frame / scan edge
    s = max(1, int(min(h, w) * 0.01))
    b = max(s + 2, int(min(h, w) * frac))
    parts = [lab[s:b, s:w - s], lab[h - b:h - s, s:w - s], lab[s:h - s, s:b], lab[s:h - s, w - b:w - s]]
    return np.concatenate([p.reshape(-1, 3) for p in parts])


def _kmeans(pixels: np.ndarray, k: int, seed=1):
    k = max(1, min(k, len(pixels)))
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
    cv2.setRNGSeed(seed)
    _, labels, centers = cv2.kmeans(pixels.astype(np.float32), k, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    return labels.ravel(), centers


L_WEIGHT = 0.5  # lighting / shading mostly changes lightness: weigh it less than the hue


def _dist_to(lab: np.ndarray, colors) -> np.ndarray:
    """Per-pixel distance to the nearest of `colors` (Lab, lightness down-weighted)."""
    wt = np.array([L_WEIGHT, 1, 1], np.float32)
    flat = lab.reshape(-1, 1, 3) * wt
    d = np.sqrt(((flat - (np.asarray(colors, np.float32) * wt).reshape(1, -1, 3)) ** 2).sum(-1)).min(1)
    return d.reshape(lab.shape[:-1])


def _rgb_to_lab(colors) -> np.ndarray:
    arr = np.asarray(colors, np.uint8).reshape(-1, 1, 3)
    return _lab(arr).reshape(-1, 3)


def _clean(mask: np.ndarray, size: int) -> np.ndarray:
    """Close small gaps (icing lines, highlights) and drop speckles."""
    k = max(3, (size // 120) | 1)
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    m = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE, ker)
    return cv2.morphologyEx(m, cv2.MORPH_OPEN, ker)


def _masks(rgb: np.ndarray, lab: np.ndarray, hints: dict):
    """Yield (method, mask) — independent guesses of 'object' pixels."""
    h, w = lab.shape[:2]
    size = max(h, w)
    tol = float(hints.get("tolerance") or 0)
    obj = hints.get("object_colors") or []
    bg = hints.get("background_colors") or []

    def grabcut(name, prior=None):
        res = _grabcut(rgb, hints, prior=prior)
        return (name, res) if res is not None else None

    if obj or bg:
        # the user's colours: nearest-colour classification when both sides are given, else a
        # distance threshold at a few tolerances; GrabCut then refines the best guess
        lo = _rgb_to_lab(obj) if obj else None
        lb = _rgb_to_lab(bg) if bg else None
        guesses = []
        if obj and bg:
            do, db = _dist_to(lab, lo), _dist_to(lab, lb)
            guesses.append(("your colours", do < db))
            if tol:
                guesses.append((f"your colours ±{tol:g}", (do < db) & (do < tol)))
        else:
            for t in ([tol] if tol else [10, 16, 24, 36]):
                guesses.append((f"object colour ±{t:g}", _dist_to(lab, lo) < t) if obj else
                               (f"background colour ±{t:g}", _dist_to(lab, lb) > t))
        yield from guesses
        best = max(guesses, key=lambda g: _clean(g[1], size).sum() if 0.02 < g[1].mean() < 0.95 else -1)
        refined = grabcut("GrabCut + your colours", _clean(best[1], size) > 0)
        if refined:
            yield refined
        return

    # background model from the image border
    border = _border_pixels(lab)
    for k in (1, 2, 3):
        labels, centers = _kmeans(border[:: max(1, len(border) // 4000)], k)
        counts = np.bincount(labels, minlength=len(centers))
        centers = centers[counts > 0.08 * counts.sum()]
        d = _dist_to(lab, centers)
        spread = np.percentile(_dist_to(border, centers), 90)
        for mult in ((tol / max(spread, 1e-3),) if tol else (1.3, 2.0, 3.0)):
            yield f"background ({k} colour{'s' if k > 1 else ''})", d > max(spread * mult, 5)

    gc = grabcut("GrabCut")
    if gc:
        yield gc

    # global colour clusters: clusters mostly found on the border are background
    flat = lab.reshape(-1, 3)
    sample = flat[:: max(1, len(flat) // 20000)]
    for k in (3, 5):
        _, centers = _kmeans(sample, k)
        lab_all = np.argmin(((flat[:, None, :] - centers[None]) ** 2).sum(-1), 1).reshape(h, w)
        edge = np.concatenate([lab_all[0], lab_all[-1], lab_all[:, 0], lab_all[:, -1]])
        on_border = np.bincount(edge, minlength=k) / len(edge)
        yield f"colour clusters ({k})", ~np.isin(lab_all, np.where(on_border > 0.15)[0])

    # luminance / saturation (Otsu) — both polarities; the one darker/lighter than the border wins
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    for name, ch in (("brightness", cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)), ("saturation", hsv[:, :, 1])):
        blur = cv2.GaussianBlur(ch, (5, 5), 0)
        _, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        th = th > 0
        edge = np.concatenate([th[0], th[-1], th[:, 0], th[:, -1]])
        yield name, ~th if edge.mean() > 0.5 else th

    # strong edges, closed and filled
    gray = cv2.GaussianBlur(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY), (5, 5), 0)
    med = float(np.median(gray))
    edges = cv2.Canny(gray, int(max(0, 0.66 * med)), int(min(255, 1.33 * med)))
    k = max(3, (size // 60) | 1)
    edges = cv2.dilate(edges, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    yield "edges", edges > 0


def _fill_holes(m: np.ndarray) -> np.ndarray:
    cnts, _ = cv2.findContours(m.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = np.zeros(m.shape, np.uint8)
    cv2.drawContours(out, cnts, -1, 1, -1)
    return out


def _components(mask: np.ndarray, min_frac=0.01):
    """Connected regions of a mask that are big enough and not just the whole picture:
    yields (hole-filled region, region as found) as uint8 masks."""
    h, w = mask.shape
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    for i in range(1, n):
        x, y, cw, ch, area = stats[i]
        if area < min_frac * h * w:
            continue
        if cw >= w - 2 and ch >= h - 2 and area > 0.9 * h * w:
            continue  # the whole picture
        comp = (labels == i).astype(np.uint8)
        yield _fill_holes(comp), comp


def _edge_strength(lab: np.ndarray, comp: np.ndarray, size: int) -> float:
    """Mean colour difference just inside vs. just outside the boundary (Lab units)."""
    r = max(2, size // 160)
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    inner = comp - cv2.erode(comp, ker)
    outer = cv2.dilate(comp, ker) - comp
    if inner.sum() == 0 or outer.sum() == 0:
        return 0.0
    # compare local means along the contour: blur the image, sample both rings
    blur = cv2.blur(lab, (2 * r + 1, 2 * r + 1))
    cnts, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    pts = np.concatenate([c.reshape(-1, 2) for c in cnts])[:: max(1, sum(len(c) for c in cnts) // 600)]
    m = cv2.moments(comp, binaryImage=True)
    cx, cy = m["m10"] / max(m["m00"], 1), m["m01"] / max(m["m00"], 1)
    h, w = comp.shape
    diffs = []
    # normal direction approximated by the gradient of the blurred mask
    soft = cv2.GaussianBlur(comp.astype(np.float32), (0, 0), r)
    gy, gx = np.gradient(soft)
    for x, y in pts:
        nx, ny = -gx[y, x], -gy[y, x]  # points outwards
        ln = math.hypot(nx, ny)
        if ln < 1e-6:
            nx, ny = x - cx, y - cy
            ln = math.hypot(nx, ny) or 1
        nx, ny = nx / ln, ny / ln
        xi, yi = int(round(x - nx * 2 * r)), int(round(y - ny * 2 * r))
        xo, yo = int(round(x + nx * 2 * r)), int(round(y + ny * 2 * r))
        if 0 <= xi < w and 0 <= yi < h and 0 <= xo < w and 0 <= yo < h:
            diffs.append(float(np.linalg.norm(blur[yi, xi] - blur[yo, xo])))
    return float(np.median(diffs)) if diffs else 0.0


def _contours(comp: np.ndarray, smooth: float, keep_holes: bool, min_hole_frac=0.002):
    """Smooth sub-pixel polygons of a binary region: [[shell, *holes]] in pixel coords (x right, y down)."""
    up = max(1, min(4, 2400 // max(comp.shape)))
    soft = cv2.resize(comp.astype(np.float32), None, fx=up, fy=up, interpolation=cv2.INTER_LINEAR)
    sigma = max(0.6, smooth) * up
    soft = cv2.GaussianBlur(soft, (0, 0), sigma)
    big = (soft > 0.5).astype(np.uint8)
    mode = cv2.RETR_CCOMP if keep_holes else cv2.RETR_EXTERNAL
    cnts, hier = cv2.findContours(big, mode, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return []
    eps = max(0.35, 0.25 * smooth) * up
    area_min = min_hole_frac * comp.shape[0] * comp.shape[1] * up * up
    polys = []
    hier = hier[0]
    for i, c in enumerate(cnts):
        if hier[i][3] != -1:
            continue  # holes are collected with their parent
        shell = cv2.approxPolyDP(c, eps, True).reshape(-1, 2) / up
        if len(shell) < 3:
            continue
        rings = [shell]
        j = hier[i][2]
        while keep_holes and j != -1:
            if cv2.contourArea(cnts[j]) > area_min:
                hole = cv2.approxPolyDP(cnts[j], eps, True).reshape(-1, 2) / up
                if len(hole) >= 3:
                    rings.append(hole)
            j = hier[j][0]
        polys.append([[[round(float(x), 3), round(float(y), 3)] for x, y in r] for r in rings])
    return polys


def _frame_box(rgb: np.ndarray):
    """Crop box (x0, y0, x1, y1) without a thin uniform frame (photo border / passe-partout).

    A side is trimmed while its rows are uniform and the colour of the outermost row; a run
    longer than 8 % of the image is a plain background, not a frame, and is kept.
    """
    h, w = rgb.shape[:2]
    img = rgb.astype(np.float32)
    limit = max(1, int(0.08 * min(h, w)))

    def depth(lines):
        ref = lines[0].mean(0)
        d = 0
        while d < len(lines) and d <= limit:
            ln = lines[d]
            if ln.std(0).max() > 10 or np.abs(ln.mean(0) - ref).max() > 14:
                break
            d += 1
        return 0 if d > limit else d

    top = depth([img[i] for i in range(min(h, limit + 2))])
    bottom = depth([img[h - 1 - i] for i in range(min(h, limit + 2))])
    left = depth([img[:, i] for i in range(min(w, limit + 2))])
    right = depth([img[:, w - 1 - i] for i in range(min(w, limit + 2))])
    if left + right >= w - 8 or top + bottom >= h - 8:
        return 0, 0, w, h
    return left, top, w - right, h - bottom


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    inter = np.logical_and(a, b).sum()
    return float(inter / max(1, np.logical_or(a, b).sum()))


def detect_outlines(data_url: str, hints: dict | None = None) -> dict:
    """Find the most likely object outlines in a picture.

    hints: count (3-10), object_colors / background_colors ([[r,g,b], ...]), tolerance (Lab
    distance, 0 = automatic), seeds ([[x, y], ...] in 0..1 image coordinates — only regions
    containing a seed are kept), bg_seeds ('not this' points — regions containing one are
    dropped and GrabCut treats them as background), rect ([x0, y0, x1, y1] in 0..1 — a box around
    the object: outside is background), smoothing (px), holes (keep inner holes).
    Returns {width, height, candidates: [{id, polygons, score, confidence, methods, area}]}
    with polygons in original image pixels (x right, y down).
    """
    hints = hints or {}
    rgb0 = decode_image(data_url)
    H0, W0 = rgb0.shape[:2]
    scale = min(1.0, MAX_PX / max(H0, W0))
    rgb = cv2.resize(rgb0, (max(1, round(W0 * scale)), max(1, round(H0 * scale))), interpolation=cv2.INTER_AREA) \
        if scale < 1 else rgb0
    sw, sh = rgb.shape[1], rgb.shape[0]
    if hints.get("rect"):
        # a box around the object: only look there — the picture is cropped to the box (plus a
        # small margin, so the background model has a border to learn from)
        bx0, by0, bx1, by1 = (float(v) for v in hints["rect"])
        pad = 0.03 * max(sw, sh)
        fx0, fy0 = max(0, int(bx0 * sw - pad)), max(0, int(by0 * sh - pad))
        fx1, fy1 = min(sw, int(bx1 * sw + pad) + 1), min(sh, int(by1 * sh + pad) + 1)
        if fx1 - fx0 < 8 or fy1 - fy0 < 8:
            fx0, fy0, fx1, fy1 = _frame_box(rgb)
    else:
        fx0, fy0, fx1, fy1 = _frame_box(rgb)
    rgb = rgb[fy0:fy1, fx0:fx1]
    rgb = cv2.bilateralFilter(rgb, 7, 40, 7)  # keep edges, drop texture (icing, crumbs, noise)
    lab = _lab(rgb)
    h, w = lab.shape[:2]
    size = max(h, w)
    count = int(min(max(int(hints.get("count") or 5), 1), 10))
    keep_holes = bool(hints.get("holes"))
    # user points arrive in 0..1 coordinates of the original picture -> pixels of the working image
    inside = lambda x, y: 0 <= x * sw - fx0 < w and 0 <= y * sh - fy0 < h
    px = lambda x, y: (min(w - 1, max(0, int(x * sw - fx0))), min(h - 1, max(0, int(y * sh - fy0))))
    seeds = [px(x, y) for x, y in hints.get("seeds") or [] if inside(x, y)]
    not_seeds = [px(x, y) for x, y in hints.get("bg_seeds") or [] if inside(x, y)]
    hints = {**hints, "_seeds": seeds, "_bg": not_seeds}

    def wanted(filled):
        """Regions must contain one of the 'inside' points and none of the 'not this' points."""
        if seeds and not any(filled[y, x] for x, y in seeds):
            return False
        return not any(filled[y, x] for x, y in not_seeds)

    found = []  # (method, filled region, raw region with holes)
    for method, mask in _masks(rgb, lab, hints):
        for filled, raw in _components(_clean(mask, size)):
            if wanted(filled):
                found.append((method, filled, raw))

    groups = _group(found)
    # refine the strongest outer regions with GrabCut seeded from them: its colour model
    # separates look-alike surroundings (drop shadows, reflections) from the object edge
    for g in sorted(_score(groups, lab, size), key=lambda s: -s[0])[:3]:
        if g[2] < 0.03:
            continue
        r = max(3, size // 40)
        prior = g[1]["comp"]
        res = _grabcut(rgb, hints, prior=prior > 0, sure_bg=cv2.dilate(prior, np.ones((r, r), np.uint8)) == 0)
        if res is not None:
            for filled, raw in _components(_clean(res, size)):
                if filled[prior > 0].mean() > 0.5 and wanted(filled):
                    found.append(("refined (GrabCut)", filled, raw))
    groups = _group(found)
    scored = sorted(_score(groups, lab, size), key=lambda s: -s[0])

    smooth = float(hints.get("smoothing") if hints.get("smoothing") is not None else 1.0)
    cands = []
    for score, g, area, edge in scored[:count]:
        comp = g["raw"] if keep_holes else g["comp"]
        polys = _contours(comp, smooth * scale, keep_holes)
        if not polys:
            continue
        polys = [[[[(x + fx0) / scale, (y + fy0) / scale] for x, y in ring] for ring in poly] for poly in polys]
        cands.append({
            "id": f"c{len(cands) + 1}", "polygons": polys, "score": round(score, 4),
            "confidence": round(100 * min(score, 1.0)), "methods": sorted(g["methods"]),
            "area": round(float(area) * w * h / (sw * sh), 4), "edge": round(edge, 1),  # share of the picture
        })
    return {"width": W0, "height": H0, "candidates": cands}


def outline_from_mask(data_url: str, smoothing: float = 1.0, holes: bool = False, min_frac: float = 0.0005) -> dict:
    """Polygons of a hand-edited mask (white / opaque = object), in the mask's pixels (y down).

    The browser paints the mask at picture resolution (brush, lasso, polygon, combined
    candidates); this turns it into the same smooth outline the detector produces.
    """
    raw = base64.b64decode(data_url.split(",", 1)[-1])
    im = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_UNCHANGED)
    if im is None:
        raise ValueError("unsupported mask image")
    if im.ndim == 3 and im.shape[2] == 4 and im[:, :, 3].min() < 250:
        m = im[:, :, 3] > 127
    else:
        m = (im if im.ndim == 2 else cv2.cvtColor(im[:, :, :3], cv2.COLOR_BGR2GRAY)) > 127
    h, w = m.shape
    # drop specks left by the brush
    n, labels, stats, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), connectivity=8)
    keep = np.zeros(n, bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= max(4, min_frac * h * w)
    comp = keep[labels].astype(np.uint8)
    polys = _contours(comp, float(smoothing), bool(holes)) if comp.any() else []
    return {"width": w, "height": h, "polygons": polys, "area": round(float(comp.mean()), 4)}


def _group(found):
    """Merge near-identical regions; how many independent methods agree = confidence."""
    groups = []
    for method, filled, raw in found:
        for g in groups:
            if _iou(g["comp"], filled) > 0.92:
                g["methods"].add(method)
                break
        else:
            groups.append({"comp": filled, "raw": raw, "methods": {method}})
    return groups


def _score(groups, lab, size):
    """[(score, group, area fraction, edge strength)] — outer, large, well-edged, agreed-on shapes first."""
    h, w = lab.shape[:2]
    families = {m.split(" (")[0] for g in groups for m in g["methods"]}
    out = []
    for g in groups:
        comp = g["comp"]
        area = comp.sum() / (h * w)
        ys, xs = np.nonzero(comp)
        m = 2
        touches = (xs.min() <= m) + (ys.min() <= m) + (xs.max() >= w - 1 - m) + (ys.max() >= h - 1 - m)
        edge = g.setdefault("edge", _edge_strength(lab, comp, size))
        cnts, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        c = max(cnts, key=cv2.contourArea)
        hull = cv2.contourArea(cv2.convexHull(c))
        solidity = cv2.contourArea(c) / hull if hull > 0 else 0
        # method families (e.g. all 'background' variants count once) that found this region
        agreement = len({m.split(" (")[0] for m in g["methods"]}) / max(1, len(families))
        # a region lying inside a clearly bigger candidate is a detail, not the outer shape
        inner = any(o is not g and o["comp"].sum() > 1.3 * comp.sum() and (o["comp"][comp > 0]).mean() > 0.9
                    for o in groups)
        score = (0.4 * min(edge / 35, 1.0) + 0.25 * agreement ** 0.5 + 0.2 * min(area / 0.2, 1.0) ** 0.5
                 + 0.15 * min(solidity / 0.6, 1.0))
        score *= 0.55 ** touches * (0.6 if inner else 1.0)
        if "refined (GrabCut)" in g["methods"]:
            score *= 1.08
        out.append((score, g, area, edge))
    return out


def _grabcut(rgb, hints, prior=None, sure_bg=None, iters=4):
    """GrabCut mask (bool) from the image border (= background), an optional prior foreground
    guess, a sure-background area and the user's seed points; None if it fails."""
    h, w = rgb.shape[:2]
    try:
        gc = np.full((h, w), cv2.GC_PR_FGD, np.uint8)
        if prior is not None:
            gc[~prior] = cv2.GC_PR_BGD
        if sure_bg is not None:
            gc[sure_bg] = cv2.GC_BGD
        m = max(2, int(min(h, w) * 0.02))
        gc[:m], gc[-m:], gc[:, :m], gc[:, -m:] = cv2.GC_BGD, cv2.GC_BGD, cv2.GC_BGD, cv2.GC_BGD
        r = max(3, max(h, w) // 80)
        for x, y in hints.get("_seeds") or []:
            cv2.circle(gc, (x, y), r, cv2.GC_FGD, -1)
        for x, y in hints.get("_bg") or []:
            cv2.circle(gc, (x, y), r, cv2.GC_BGD, -1)
        bgm, fgm = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
        cv2.grabCut(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), gc, None, bgm, fgm, iters, cv2.GC_INIT_WITH_MASK)
        return (gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)
    except cv2.error:
        return None


# =========================================================================== model
PRESETS = {
    # cookie cutter, printed flange-down: flange on the bed, cutting edge on top
    "cutter": {"wall": 1.0, "height": 15.0, "flange_w": 4.0, "flange_t": 2.0, "tip": 0.5, "tip_h": 3.0,
               "clearance": 0.0},
    # the whole shape (e.g. the cookie itself, a plaque, a stencil base)
    "solid": {"thickness": 6.0, "offset": 0.0},
}


def outline_model(polygons, img_w: float, img_h: float, width: float | None = None, height: float | None = None,
                  preset: str = "cutter", source: str = "image.png", space: str = "image") -> dict:
    """A parametric model from an outline: traced from a picture (space 'image': pixels, y down) or
    read from a drawing (space 'mm': real size, y up — DXF / DWG; width / height default to it)."""
    pts = [p for poly in polygons for p in poly[0]]
    if not pts:
        raise ValueError("The outline is empty.")
    bw = max(p[0] for p in pts) - min(p[0] for p in pts)
    bh = max(p[1] for p in pts) - min(p[1] for p in pts)
    if bw <= 0 or bh <= 0:
        raise ValueError("The outline has no area.")
    aspect = bw / bh
    if width and not height:
        height = width / aspect
    elif height and not width:
        width = height * aspect
    elif not width:
        width, height = (bw, bh) if space == "mm" else (100.0, 100.0 / aspect)
    params = [
        {"id": "width", "name": "Width", "value": float(width), "unit": "mm", "role": "driving",
         "source": "outline", "kind": "size", "axis": "x"},
        {"id": "height", "name": "Height", "value": float(height), "unit": "mm", "role": "driving",
         "source": "outline", "kind": "size", "axis": "y"},
    ]
    return {
        "kind": "outline", "unit": "mm", "source": source, "params": params, "loops": [], "issues": [],
        "outline": {"polygons": polygons, "img_w": img_w, "img_h": img_h, "aspect": aspect, "lock": True,
                    "mirror": False, "space": space},
        "shapes": [],           # 2D edits of the outline: add / subtract circles, rectangles, lines
        "preset": preset if preset in PRESETS or preset == "custom" else "cutter",
        "preset_opts": dict(PRESETS.get(preset, PRESETS["cutter"])),
        # 3D objects (used when preset == 'custom'); a custom start is the plain outline
        "objects": preset_objects("solid", PRESETS["solid"]) if preset == "custom" else [],
        "extras": [],           # 3D objects added on top of a preset (holes, handles, text …)
    }


def preset_objects(preset: str, opts: dict) -> list[dict]:
    """The 3D objects a preset stands for (so it can be converted to 'custom' and edited)."""
    o = {**PRESETS.get(preset, {}), **(opts or {})}
    f = lambda k: float(o.get(k) or 0)
    if preset == "solid":
        return [{"id": "o1", "name": "Shape", "op": "union", "source": "outline", "mode": "fill",
                 "offset": f("offset"), "z0": 0.0, "z1": f("thickness"), "visible": True}]
    if preset == "cutter":
        c, wall, tip = f("clearance"), f("wall"), f("tip") or f("wall")
        h, ft = f("height"), f("flange_t")
        th = min(f("tip_h"), h - ft)
        objs = [
            {"id": "o1", "name": "Flange", "op": "union", "source": "outline", "mode": "band",
             "inner": c, "outer": c + wall + f("flange_w"), "z0": 0.0, "z1": ft, "visible": True},
            {"id": "o2", "name": "Wall", "op": "union", "source": "outline", "mode": "band",
             "inner": c, "outer": c + wall, "z0": ft, "z1": h, "visible": True},
        ]
        if th > 0 and tip < wall:
            objs[1]["z1"] = h - th
            objs.append({"id": "o3", "name": "Cutting edge", "op": "union", "source": "outline", "mode": "band",
                         "inner": c, "outer": c + tip, "z0": h - th, "z1": h, "visible": True})
        return objs
    return []


def _shape_geom(s: dict):
    """A 2D primitive (mm): circle / ellipse, rectangle or line; stroke > 0 turns circles and
    rectangles into rings of that width.  2D shapes name the primitive in 'kind', 3D objects in 'source'."""
    kind = s.get("source") if s.get("source") not in (None, "outline") else s.get("kind", "rect")
    x, y = float(s.get("x", 0)), float(s.get("y", 0))
    if kind == "line":
        width = max(float(s.get("width") or 1), 1e-3)
        line = LineString([(x, y), (float(s.get("x2", x + 10)), float(s.get("y2", y)))])
        return line.buffer(width / 2, cap_style="round" if s.get("round") else "flat", quad_segs=8)
    w = max(float(s.get("w") or 1), 1e-3)
    h = max(float(s.get("h") or w), 1e-3)
    if kind == "poly":
        # traced polygons (text, logos) normalised to a unit box centred at 0, y up
        polys = [Polygon(shell, holes) for shell, *holes in s.get("polygons") or [] if len(shell) >= 3]
        unit = unary_union([p if p.is_valid else p.buffer(0) for p in polys])
        if unit.is_empty:
            raise ValueError("the shape has no outline")
        g = affinity.translate(affinity.scale(unit, w, h, origin=(0, 0)), x, y)
    elif kind == "circle":
        g = affinity.scale(Point(x, y).buffer(0.5, quad_segs=32), w, h)
    elif kind == "rect":
        g = box(x - w / 2, y - h / 2, x + w / 2, y + h / 2)
    else:
        raise ValueError(f"unknown shape '{kind}'")
    stroke = float(s.get("stroke") or 0)
    if stroke > 0:
        g = g.difference(g.buffer(-stroke, join_style="mitre"))
    rot = float(s.get("rot") or 0)
    return affinity.rotate(g, rot, origin=(x, y)) if rot else g


def scaled_outline(model: dict, values: dict):
    """The traced outline in mm, lower-left corner of its bounding box at the origin (y up)."""
    o = model["outline"]
    polys = []
    for poly in o["polygons"]:
        rings = [[(float(x), float(y)) for x, y in r] for r in poly]
        if len(rings[0]) >= 3:
            p = Polygon(rings[0], [r for r in rings[1:] if len(r) >= 3])
            polys.append(p if p.is_valid else p.buffer(0))
    g = unary_union(polys)
    x0, y0, x1, y1 = g.bounds
    sx, sy = values["width"] / (x1 - x0), values["height"] / (y1 - y0)
    if o.get("space") == "mm":  # a drawing: already y up
        if o.get("mirror"):
            return affinity.affine_transform(g, [-sx, 0, 0, sy, x1 * sx, -y0 * sy])
        return affinity.affine_transform(g, [sx, 0, 0, sy, -x0 * sx, -y0 * sy])
    # image y points down -> flip; 'mirror' also flips x (a cookie cutter is used upside down)
    if o.get("mirror"):
        return affinity.affine_transform(g, [-sx, 0, 0, -sy, x1 * sx, y1 * sy])
    return affinity.affine_transform(g, [sx, 0, 0, -sy, -x0 * sx, y1 * sy])


def clean_outline(g, cleanup: dict | None):
    """Outline clean-up in mm, in this order:
    fill_holes; close (bridge gaps / notches narrower than 2 x close); smooth (round corners and
    remove spikes / necks thinner than 2 x smooth); keep ('largest' piece only); hull (convex
    hull); simplify (max. deviation)."""
    c = cleanup or {}
    f = lambda k: max(float(c.get(k) or 0), 0.0)
    polys = lambda geom: polygons_of(geom)
    if c.get("fill_holes"):
        g = unary_union([Polygon(p.exterior) for p in polys(g)])
    if f("close"):
        g = g.buffer(f("close"), quad_segs=8).buffer(-f("close"), quad_segs=8)
    if f("smooth"):
        r = f("smooth")
        g = g.buffer(r, quad_segs=8).buffer(-2 * r, quad_segs=8).buffer(r, quad_segs=8)
    if c.get("keep") == "largest" and polys(g):
        g = max(polys(g), key=lambda p: p.area)
    if c.get("hull"):
        g = g.convex_hull
    if f("simplify"):
        g = g.simplify(f("simplify"))
    return g


def _region(obj: dict, base):
    if obj.get("source", "outline") == "outline":
        grow = lambda d: base.buffer(d, quad_segs=8) if d else base
        if obj.get("mode") == "band":
            return grow(float(obj.get("outer") or 0)).difference(grow(float(obj.get("inner") or 0)))
        return grow(float(obj.get("offset") or 0))
    return _shape_geom(obj)


def apply_shapes(base, shapes, issue):
    """2D shapes added to / cut from a profile (any part: outline, PDF profile)."""
    for s in shapes or []:
        if not s.get("visible", True):
            continue
        try:
            g = _shape_geom(s)
        except ValueError as exc:
            issue("error", f"{s.get('name') or 'Shape'}: {exc}", "design")
            continue
        base = base.difference(g) if s.get("op") == "subtract" else base.union(g)
    return MultiPolygon(polygons_of(base))


def object_ops(objects, base, issue):
    """3D objects -> [(op, region, z0, z1, obj)]; 'outline' objects are offsets / bands of `base`
    (the part's 2D profile), the others are primitives."""
    ops = []
    for obj in objects or []:
        if not obj.get("visible", True):
            continue
        name = obj.get("name") or "Object"
        z0, z1 = float(obj.get("z0") or 0), float(obj.get("z1") or 0)
        if not z1 > z0:
            issue("error", f"{name}: the top ({_fmt(z1)} mm) must be above the bottom ({_fmt(z0)} mm).", "design")
            continue
        if obj.get("source", "outline") == "outline" and obj.get("mode") == "band" and \
                not float(obj.get("outer") or 0) > float(obj.get("inner") or 0):
            issue("error", f"{name}: the outer offset must be larger than the inner offset.", "design")
            continue
        try:
            g = MultiPolygon(polygons_of(_region(obj, base)))
        except (ValueError, shapely.errors.GEOSException) as exc:
            issue("error", f"{name}: {exc}", "design")
            continue
        if g.is_empty:
            issue("warning", f"{name} is empty (an inward offset larger than the shape?).", "design")
            continue
        op = obj.get("op", "union")
        ops.append((op if op in ("union", "subtract", "intersect") else "union", g, z0, z1, obj))
    return ops


def object_regions(ops, tol: float, preset_ids=()):
    """Footprints of the objects (simplified), for clicking an object in the 3D view to select it."""
    out = []
    for op, g, z0, z1, obj in ops:
        if not obj.get("id"):
            continue
        rings = [[[round(x, 4), round(y, 4)] for x, y in r.coords[:-1]]
                 for p in polygons_of(g.simplify(tol)) for r in (p.exterior, *p.interiors)]
        out.append({"id": obj["id"], "name": obj.get("name"), "op": op, "z0": z0, "z1": z1, "rings": rings,
                    "preset": obj["id"] in preset_ids})
    return out


def add_objects(solid, objects, base, issue, regions=None):
    """Boolean the extra 3D objects into a finished solid (keeps its design-layer issues / guides);
    their footprints are appended to `regions` when given."""
    ops = object_ops(objects, base, issue)
    if regions is not None:
        regions += object_regions(ops, solid.size * 0.002)
    if not ops:
        return solid
    keep = solid.issues, solid.guides
    out = solid.csg([(op, g, a, b) for op, g, a, b, _ in ops])
    out.issues, out.guides = keep
    return out


def solve_outline(model: dict, overrides: dict | None = None, layers=None):
    """Build an outline model. Returns (solution, solid); solid is None when the model is invalid
    (solution['issues'] says why)."""
    values = {p["id"]: float(p["value"]) for p in model["params"]}
    values.update({k: float(v) for k, v in (overrides or {}).items() if k in values})
    issues = []

    def issue(sev, msg, code="invalid_value", params=()):
        issues.append({"severity": sev, "code": code, "message": msg, "params": list(params)})

    def fail():
        return ({"ok": False, "issues": issues, "values": values, "loops": [], "thickness": 1.0,
                 "bbox": [0, 0, 1, 1], "annotations": []}, None)

    for pid in ("width", "height"):
        if not values[pid] > 0:
            issue("error", f"{pid.capitalize()} must be greater than zero (got {_fmt(values[pid])}).", params=[pid])
    if issues:
        return fail()

    # clean-up acts on the traced outline only; the user's 2D shapes are applied afterwards as drawn
    base = apply_shapes(clean_outline(scaled_outline(model, values), model["outline"].get("cleanup")),
                        model.get("shapes"), issue)
    if base.is_empty:
        issue("error", "The outline is empty after the 2D shapes were applied.", "invalid_geometry")
        return fail()

    preset = model.get("preset", "cutter")
    objects = model.get("objects") or [] if preset == "custom" else preset_objects(preset, model.get("preset_opts"))
    # objects added on top of a preset (in custom mode everything is in `objects`)
    ops = object_ops(objects + ([] if preset == "custom" else model.get("extras") or []), base, issue)
    first = next((i for i, o in enumerate(ops) if o[0] == "union"), None)
    if first is None:
        issue("error", "Nothing to build: add at least one visible object that adds material (union).",
              "invalid_geometry")
        return fail()
    ops = ops[first:]

    # the first object is the base part: design layers apply to its top / bottom face
    _, g0, z0, z1, _ = ops[0]
    solid = Solid({"_profile": g0, "thickness": z1 - z0, "bbox": list(g0.bounds), "loops": []}, layers or [], "mm")
    layer_issues, guides = solid.issues, solid.guides
    if z0:
        solid = solid.translated(dz=z0)
    solid = solid.csg([(op, g, a, b) for op, g, a, b, _ in ops[1:]])
    solid.issues, solid.guides = layer_issues, guides  # reported by the server as design issues
    if not solid.slabs:
        issue("error", "The objects cancel each other out — nothing is left.", "invalid_geometry")
        return fail()

    for op, g, _, _, obj in ops:
        if op == "union" and g.area > 0 and (g.area - g.buffer(-0.2).buffer(0.2).area) / g.area > 0.2:
            issue("warning", f"{obj.get('name') or 'Object'} has walls thinner than 0.4 mm that may not print.",
                  "design")
    if len(base.geoms) > 1:
        issue("info", f"The outline consists of {len(base.geoms)} separate pieces.", "outline_pieces")

    x0, y0, x1, y1 = solid.xy_bounds()
    zlo, zhi = solid.z_range()
    biggest = max(polygons_of(g0), key=lambda p: p.area)
    ring = lambda r: [list(c) for c in r.coords[:-1]]
    loops = [{"id": "outer", "kind": "outer", "name": "Outline", "points": ring(biggest.exterior)}]
    loops += [{"id": f"hole{i}", "kind": "hole", "name": f"Hole {i}", "points": ring(r)}
              for i, r in enumerate(biggest.interiors, 1)]
    ox0, oy0, ox1, oy1 = base.bounds
    gap = 0.06 * max(x1 - x0, y1 - y0)
    solution = {
        "ok": not any(i["severity"] == "error" for i in issues), "issues": issues, "values": values,
        "levels": {}, "loops": loops, "thickness": zhi, "bbox": [x0, y0, x1, y1], "z_range": [zlo, zhi],
        "objects": objects, "outline_bbox": [ox0, oy0, ox1, oy1],
        "object_regions": object_regions(ops, gap * 0.03,
                                         {o.get("id") for o in objects} if preset != "custom" else ()),
        # design layers go on the first object: its top ('front') and bottom ('back') face
        "layer_faces": {"top": z1, "bottom": z0, "object": ops[0][4].get("name") or "Object"},
        "z_levels": list(solid.levels),  # heights of all horizontal faces (picking snaps to them)
        "outline_2d": [[ring(p.exterior)] + [ring(r) for r in p.interiors] for p in base.geoms],
        "annotations": [
            {"param": "width", "p1": [ox0, y0 - gap], "p2": [ox1, y0 - gap], "value": values["width"], "z": zhi},
            {"param": "height", "p1": [x1 + gap, oy0], "p2": [x1 + gap, oy1], "value": values["height"], "z": zhi},
        ],
    }
    return solution, (solid if solution["ok"] else None)
