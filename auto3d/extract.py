"""Low-level PDF extraction: geometry strokes, arrowheads and text labels.

Everything is returned in PDF page coordinates (points, y pointing down).
Interpretation (which strokes form the part, which arrows form a dimension)
happens in :mod:`auto3d.sketch`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import fitz  # PyMuPDF
from shapely.geometry import MultiPoint, Polygon

Point = tuple[float, float]


@dataclass
class Segment:
    a: Point
    b: Point
    width: float


@dataclass
class Arrow:
    tip: Point
    direction: Point  # unit vector pointing towards the tip
    size: float


@dataclass
class TextLabel:
    text: str
    bbox: tuple[float, float, float, float]

    @property
    def center(self) -> Point:
        x0, y0, x1, y1 = self.bbox
        return ((x0 + x1) / 2, (y0 + y1) / 2)


@dataclass
class PageExtract:
    width: float
    height: float
    segments: list[Segment] = field(default_factory=list)
    arrows: list[Arrow] = field(default_factory=list)
    texts: list[TextLabel] = field(default_factory=list)
    curve_count: int = 0
    glyph_paths: int = 0


def _pt(p) -> Point:
    return (float(p.x), float(p.y))


def _dist(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _path_points(drawing) -> list[Point]:
    pts: list[Point] = []
    for item in drawing["items"]:
        if item[0] == "re":
            r = item[1]
            pts += [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)]
        elif item[0] == "qu":
            q = item[1]
            pts += [_pt(q.ul), _pt(q.ur), _pt(q.lr), _pt(q.ll)]
        else:
            pts += [_pt(p) for p in item[1:] if hasattr(p, "x")]
    return pts


def _arrow_from_triangle(tri: list[Point]) -> Arrow | None:
    """Interpret a triangle as an arrowhead: apex opposite the shortest side.

    Near-equilateral heads are ambiguous, so among the plausible apexes an
    axis-aligned direction wins (dimensions are almost always horizontal or
    vertical).
    """
    sides = [_dist(tri[(i + 1) % 3], tri[(i + 2) % 3]) for i in range(3)]
    shortest = min(sides)
    best, best_score = None, math.inf
    for i in range(3):
        base, legs = sides[i], [sides[k] for k in range(3) if k != i]
        if base < 0.3 or base > 1.15 * shortest or min(legs) / max(legs) < 0.75:
            continue
        apex = tri[i]
        b1, b2 = tri[(i + 1) % 3], tri[(i + 2) % 3]
        mid = ((b1[0] + b2[0]) / 2, (b1[1] + b2[1]) / 2)
        length = _dist(apex, mid)
        if length < 0.5 * base:  # too blunt to be an arrowhead
            continue
        d = ((apex[0] - mid[0]) / length, (apex[1] - mid[1]) / length)
        score = base / shortest - (1.0 if max(abs(d[0]), abs(d[1])) > 0.998 else 0.0)
        if score < best_score:
            best, best_score = Arrow(tip=apex, direction=d, size=length), score
    return best


def _triangle_hull(points: list[Point]) -> list[Point] | None:
    hull = MultiPoint(points).convex_hull
    if not isinstance(hull, Polygon):
        return None
    coords = list(hull.simplify(0.4).exterior.coords)[:-1]
    return coords if len(coords) == 3 else None


def _open_v_arrow(drawing) -> Arrow | None:
    """Open 'V' arrowheads drawn as two short strokes sharing an apex."""
    lines = [it for it in drawing["items"] if it[0] == "l"]
    if len(lines) != 2 or len(drawing["items"]) != 2:
        return None
    (a1, b1), (a2, b2) = [(_pt(l[1]), _pt(l[2])) for l in lines]
    for apex, p, q in ((b1, a1, b2 if _dist(b1, a2) < 0.5 else a2),
                       (a1, b1, b2 if _dist(a1, a2) < 0.5 else a2)):
        if (_dist(apex, a2) < 0.5 or _dist(apex, b2) < 0.5) and max(_dist(apex, p), _dist(apex, q)) < 15:
            return _arrow_from_triangle([apex, p, q])
    return None


def _inside(p: Point, bbox, pad=1.0) -> bool:
    return bbox[0] - pad <= p[0] <= bbox[2] + pad and bbox[1] - pad <= p[1] <= bbox[3] + pad


def extract_page(page: fitz.Page) -> PageExtract:
    out = PageExtract(width=page.rect.width, height=page.rect.height)

    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            text = "".join(s["text"] for s in line["spans"]).strip()
            if text:
                out.texts.append(TextLabel(text=text, bbox=tuple(line["bbox"])))

    drawings = page.get_drawings()
    page_area = out.width * out.height
    stroke_widths = [d.get("width") or 0 for d in drawings if "s" in d["type"]]
    max_w = max(stroke_widths, default=0)
    geom_threshold = 0.6 * max_w

    arrows: list[Arrow] = []
    for d in drawings:
        pts = _path_points(d)
        if not pts:
            continue
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        bbox = (min(xs), min(ys), max(xs), max(ys))
        extent = max(bbox[2] - bbox[0], bbox[3] - bbox[1])
        filled = "f" in d["type"]
        stroked = "s" in d["type"]
        width = d.get("width") or 0

        # Page background / frame fills.
        if filled and not stroked and (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) > 0.5 * page_area:
            continue
        # Glyph outlines duplicated under real text.
        center = ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
        if filled and extent < 20 and any(_inside(center, t.bbox) for t in out.texts):
            out.glyph_paths += 1
            continue

        if extent < 16:
            if filled:
                tri = _triangle_hull(pts)
                arrow = _arrow_from_triangle(tri) if tri else None
                if arrow:
                    arrows.append(arrow)
                    continue
            elif stroked:
                arrow = _open_v_arrow(d)
                if arrow:
                    arrows.append(arrow)
                    continue

        if stroked and width >= geom_threshold and max_w > 0:
            for item in d["items"]:
                kind = item[0]
                if kind == "l":
                    out.segments.append(Segment(_pt(item[1]), _pt(item[2]), width))
                elif kind == "re":
                    r = item[1]
                    c = [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)]
                    for i in range(4):
                        out.segments.append(Segment(c[i], c[(i + 1) % 4], width))
                elif kind == "qu":
                    q = item[1]
                    c = [_pt(q.ul), _pt(q.ur), _pt(q.lr), _pt(q.ll)]
                    for i in range(4):
                        out.segments.append(Segment(c[i], c[(i + 1) % 4], width))
                elif kind == "c":
                    out.curve_count += 1
            if d.get("closePath") and d["items"] and d["items"][0][0] == "l":
                first, last = _pt(d["items"][0][1]), _pt(d["items"][-1][-1])
                if _dist(first, last) > 0.01:
                    out.segments.append(Segment(last, first, width))

    # Arrowheads are frequently drawn twice (fill + outline); deduplicate.
    for a in arrows:
        if not any(_dist(a.tip, b.tip) < 1.0 and a.direction[0] * b.direction[0] + a.direction[1] * b.direction[1] > 0.9
                   for b in out.arrows):
            out.arrows.append(a)
    return out


def render_page_png(page: fitz.Page, dpi: int = 144) -> bytes:
    return page.get_pixmap(dpi=dpi).tobytes("png")
