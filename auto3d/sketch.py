"""Turn raw PDF primitives into a parametric sketch model.

Key idea: drawings are frequently *not to scale*, so the drawn coordinates are
only used for topology (which corners share an x / y position, what is left of
what).  Every coordinate "level" (a shared x or y position) becomes a node and
every dimension becomes a distance constraint between two levels.  Dimensions
are the source of truth; drawing proportions are used only to estimate values
the drawing does not specify, and every such estimate is reported.

The resulting model is plain JSON so the browser can keep it and send it back
to :func:`auto3d.solver.solve` whenever the user edits a parameter.
"""
from __future__ import annotations

import math
import re
from collections import defaultdict
from statistics import median

import fitz
from shapely.geometry import Polygon

from .extract import Arrow, PageExtract, TextLabel, extract_page

MERGE_TOL = 2.5          # pt, endpoints closer than this are the same corner
ALIGN_TOL = 1.5          # pt, levels closer than this are assumed aligned
AXIS_COS = 0.995         # how axis-aligned an arrow / edge must be
PT_PER_UNIT = {"mm": 72 / 25.4, "cm": 72 / 2.54, "m": 72 / 0.0254, "in": 72.0}
UNIT_IN_MM = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4}

_NUM = r"(\d+(?:[.,]\d+)?)"
DIM_RE = re.compile(
    rf"^(?P<prefix>[ØøR⌀∅]|DIA\.?)?\s*(?P<num>{_NUM[1:-1]})\s*(?P<unit>mm|cm|m|in|\"|'')?\s*"
    rf"(?P<tol>(±|\+/-)\s*\d+(?:[.,]\d+)?\s*(mm|cm|m|in)?)?$",
    re.IGNORECASE,
)
THICKNESS_RE = re.compile(
    rf"(?:\bt\s*=|thk\.?|thickness|tl\.?|tloušťka)\s*:?\s*{_NUM}\s*(mm|cm|m|in)?", re.IGNORECASE)


# --------------------------------------------------------------------------- helpers
class _UF:
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


class _WeightedUF:
    """Union-find that tracks pos(node) - pos(root)."""

    def __init__(self):
        self.p, self.off = {}, {}

    def find(self, a):
        if a not in self.p:
            self.p[a], self.off[a] = a, 0.0
        if self.p[a] == a:
            return a, 0.0
        root, o = self.find(self.p[a])
        self.p[a], self.off[a] = root, self.off[a] + o
        return root, self.off[a]

    def union(self, lo, hi, value):
        """Constrain pos(hi) - pos(lo) = value. Returns None or the implied value if redundant."""
        (rl, ol), (rh, oh) = self.find(lo), self.find(hi)
        if rl == rh:
            return oh - ol
        # pos(hi) = pos(lo) + value  ->  pos(rh) = pos(rl) + ol + value - oh
        self.p[rh], self.off[rh] = rl, ol + value - oh
        return None


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _fmt(v: float) -> str:
    return f"{v:.3f}".rstrip("0").rstrip(".")


def parse_dimension_text(text: str):
    """Return (value, unit|None, prefix, error|None)."""
    t = text.strip().replace(" ", "")
    m = DIM_RE.match(t)
    if not m:
        return None, None, None, f"label '{text}' is not a valid dimension value"
    value = float(m.group("num").replace(",", "."))
    unit = (m.group("unit") or "").lower() or None
    if unit in ('"', "''"):
        unit = "in"
    prefix = (m.group("prefix") or "").upper() or None
    if value <= 0:
        return value, unit, prefix, f"dimension value '{text}' must be greater than zero"
    return value, unit, prefix, None


def _label_score(p, q, bbox) -> float:
    """How well a text box fits as the label of the dimension line pq.

    Labels sit beside (or on) their dimension line, so the gap perpendicular
    to the line counts normally while a label lying beyond the line's ends is
    penalised -- that is usually the label of a neighbouring dimension.
    """
    x0, y0, x1, y1 = bbox
    length = _dist(p, q)
    u = ((q[0] - p[0]) / length, (q[1] - p[1]) / length)
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    along = [(c[0] - p[0]) * u[0] + (c[1] - p[1]) * u[1] for c in corners]
    perp = [(c[0] - p[0]) * u[1] - (c[1] - p[1]) * u[0] for c in corners]
    perp_gap = 0.0 if min(perp) <= 0 <= max(perp) else min(abs(v) for v in perp)
    center_along = sum(along) / 4
    overflow = max(0.0, -center_along, center_along - length)
    return perp_gap + 3 * overflow


# --------------------------------------------------------------------------- builder
class SketchBuilder:
    def __init__(self, ex: PageExtract):
        self.ex = ex
        self.issues: list[dict] = []
        self.vertices: list[dict] = []
        self.edges: list[dict] = []
        self.loops: list[dict] = []
        self.levels = {"x": [], "y": []}
        self.params: list[dict] = []
        self.unit = "mm"
        self.open_shapes: list[tuple] = []  # shapes of thick lines that do not close: (corners, bbox on the page, pt)

    def issue(self, severity, code, message, params=None, draw=None):
        self.issues.append({"severity": severity, "code": code, "message": message,
                            "params": params or [], "draw": draw})

    # ------------------------------------------------------------------ outline
    def build_outline(self):
        pts: list[list[float]] = []   # cluster centroids
        members: list[list] = []

        def vid(p):
            for i, c in enumerate(pts):
                if _dist(c, p) <= MERGE_TOL:
                    members[i].append(p)
                    n = len(members[i])
                    c[0] += (p[0] - c[0]) / n
                    c[1] += (p[1] - c[1]) / n
                    return i
            pts.append([p[0], p[1]])
            members.append([p])
            return len(pts) - 1

        raw_edges = set()
        for s in self.ex.segments:
            a, b = vid(s.a), vid(s.b)
            if a != b:
                raw_edges.add((min(a, b), max(a, b)))

        if not raw_edges:
            self.issue("error", "no_geometry",
                       "No part outline found in the PDF (no thick vector lines). Scanned/raster drawings are not supported.")
            return

        adj = defaultdict(set)
        for a, b in raw_edges:
            adj[a].add(b)
            adj[b].add(a)

        seen = set()
        raw_loops = []
        for start in adj:
            if start in seen:
                continue
            comp, stack = [], [start]
            while stack:
                v = stack.pop()
                if v in seen:
                    continue
                seen.add(v)
                comp.append(v)
                stack += adj[v] - seen
            bad = [v for v in comp if len(adj[v]) != 2]
            if bad:
                cx, cy = [pts[v][0] for v in comp], [pts[v][1] for v in comp]
                self.open_shapes.append((len(comp), (min(cx), min(cy), max(cx), max(cy))))
                p = pts[bad[0]]
                kind = "open end" if len(adj[bad[0]]) == 1 else "branch"
                self.issue("warning", "open_outline",
                           f"Outline is not a closed loop ({kind} at x={p[0]:.0f}, y={p[1]:.0f} pt on the page); "
                           f"{len(comp)} corner(s) ignored. Check for gaps in the drawing.",
                           draw={"points": [pts[v] for v in bad]})
                continue
            loop, prev = [start], None
            while True:
                nxt = next(n for n in adj[loop[-1]] if n != prev and (len(loop) < 2 or n != loop[-2]))
                if nxt == start:
                    break
                prev = loop[-1]
                loop.append(nxt)
            raw_loops.append(loop)

        # drop collinear corners (a straight line drawn as several strokes)
        cleaned = []
        for loop in raw_loops:
            changed = True
            while changed and len(loop) > 3:
                changed = False
                for i in range(len(loop)):
                    a, b, c = pts[loop[i - 1]], pts[loop[i]], pts[loop[(i + 1) % len(loop)]]
                    cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
                    if abs(cross) <= 1.0 * max(_dist(a, b), _dist(b, c)):
                        loop.pop(i)
                        changed = True
                        break
            cleaned.append(loop)

        polys = [(loop, Polygon([pts[v] for v in loop])) for loop in cleaned]
        page_area = self.ex.width * self.ex.height
        frames = [lp for lp in polys if lp[1].area > 0.6 * page_area]
        if frames and len(polys) > len(frames):
            polys = [lp for lp in polys if lp not in frames]
            self.issue("info", "frame_ignored", "A drawing frame/border was detected and ignored.")

        kept = sorted(polys, key=lambda lp: -lp[1].area)
        views = self._views_beside(kept[0][1] if kept else None)
        if not kept:
            many = views or len(self.ex.arrows) >= 4 or self.ex.curve_count  # (a dimensioned drawing, not one outline)
            self.issue("error", "no_geometry", "No closed outline found in the drawing." + (
                f" It looks like a dimensioned drawing with several views ({len(self.open_shapes)} shape(s) of its thick "
                f"lines do not close, {self.ex.curve_count} curve(s)) — this reader takes one closed outline of straight "
                "lines. Trace the view you want from a picture of it (📂 Open ▾ → Picture — trace an outline…), or draw "
                "it in a 3D model's sketch." if many else ""),
                draw={"points": [p for _, b in views for p in ((b[0], b[1]), (b[2], b[3]))]} if views else None)
            return
        if views:  # (the largest closed outline is small beside shapes that do not close: probably not the part)
            b = kept[0][1].bounds
            w, h = ((b[2] - b[0]) / PT_PER_UNIT["mm"], (b[3] - b[1]) / PT_PER_UNIT["mm"])
            self.issue("warning", "unsure_outline",
                       f"Unsure which outline is the part: this looks like a dimensioned drawing with several views — "
                       f"{len(views)} bigger shape(s) of its thick lines do not close (curves, lines crossing), and the "
                       f"outline used is the largest closed one, {w:.0f} × {h:.0f} mm on the paper. Check the part; for "
                       "another view trace it from a picture of it (📂 Open ▾ → Picture — trace an outline…).",
                       draw={"points": [p for _, vb in views for p in ((vb[0], vb[1]), (vb[2], vb[3]))]})

        outer_loop, outer_poly = kept[0]
        final = [(outer_loop, outer_poly, "outer")]
        for loop, poly in kept[1:]:
            if outer_poly.contains(poly):
                if any(f[1].contains(poly) for f in final[1:]):
                    self.issue("warning", "island_ignored",
                               "A closed shape inside a cutout was found; islands are not supported and it was ignored.")
                    continue
                final.append((loop, poly, "hole"))
            else:
                self.issue("warning", "extra_outline",
                           "More than one separate part outline found; only the largest one is modelled.",
                           draw={"points": [pts[v] for v in loop]})

        # cutouts numbered left-to-right, then top-to-bottom
        holes = sorted(final[1:], key=lambda f: (round(f[1].bounds[0]), f[1].bounds[1]))
        final = final[:1] + holes

        remap = {}
        for li, (loop, poly, kind) in enumerate(final):
            ids = []
            for v in loop:
                if v not in remap:
                    remap[v] = len(self.vertices)
                    self.vertices.append({"id": remap[v], "draw": pts[v], "loop": li})
                ids.append(remap[v])
            name = "Outer profile" if kind == "outer" else f"Cutout {li}"
            # store loops counter-clockwise in model space (y up) -> clockwise on the page
            if Polygon([pts[v] for v in loop]).exterior.is_ccw:
                ids.reverse()
            self.loops.append({"id": li, "kind": kind, "name": name, "vertices": ids})
            for i in range(len(ids)):
                self.edges.append({"id": len(self.edges), "v": [ids[i], ids[(i + 1) % len(ids)]], "loop": li})

        if self.ex.curve_count:
            self.issue("warning", "curves_unsupported",
                       f"{self.ex.curve_count} curved outline segment(s) (arcs/circles) were found; "
                       "only straight-line outlines are supported, curves were ignored.")

    def _views_beside(self, outline):
        """The shapes that do not close and are bigger than `outline` (a Polygon, or None: all of some size) — the views
        of a multi-view drawing whose curves and crossing lines this reader cannot close; the biggest first."""
        big = [(n, b) for n, b in self.open_shapes if n >= 4 and (b[2] - b[0]) * (b[3] - b[1]) > (
            outline.area * 1.5 if outline is not None else 400)]  # (pt²: about 7 × 7 mm)
        return sorted(big, key=lambda nb: -(nb[1][2] - nb[1][0]) * (nb[1][3] - nb[1][1]))

    # ------------------------------------------------------------------ levels
    def build_levels(self):
        for axis, k in (("x", 0), ("y", 1)):
            uf = _UF()
            for v in self.vertices:
                uf.find(v["id"])
            for e in self.edges:
                a, b = (self.vertices[i]["draw"] for i in e["v"])
                d = _dist(a, b)
                # vertical edge -> shared x ; horizontal edge -> shared y
                along = abs(b[1 - k] - a[1 - k])
                if d > 0 and along / d >= AXIS_COS:
                    uf.union(*e["v"])
            groups = defaultdict(list)
            for v in self.vertices:
                groups[uf.find(v["id"])].append(v)
            for vs in sorted(groups.values(), key=lambda g: sum(v["draw"][k] for v in g) / len(g)):
                lid = f"{axis}{len(self.levels[axis])}"
                pos = sum(v["draw"][k] for v in vs) / len(vs)
                self.levels[axis].append({"id": lid, "draw": pos})
                for v in vs:
                    v[axis] = lid

    def level(self, lid):
        return next(l for l in self.levels[lid[0]] if l["id"] == lid)

    def level_loops(self, lid):
        return {v["loop"] for v in self.vertices if v[lid[0]] == lid}

    # ------------------------------------------------------------------ dimensions
    def _attach(self, tip, axis, arrow_size):
        """Find the level (and edge) that a dimension arrow tip points at."""
        k = 0 if axis == "x" else 1
        best, best_score = None, math.inf
        tol = max(3.0, 1.0 * arrow_size)
        for e in self.edges:
            va, vb = (self.vertices[i] for i in e["v"])
            if va[axis] != vb[axis]:
                continue  # edge is not perpendicular to the measuring direction
            a, b = va["draw"], vb["draw"]
            perp = abs(tip[k] - (a[k] + b[k]) / 2)
            lo, hi = sorted((a[1 - k], b[1 - k]))
            along = max(lo - tip[1 - k], 0, tip[1 - k] - hi)
            if perp > tol:
                continue
            score = along + 5 * perp
            if score < best_score:
                best, best_score = (va[axis], e["id"], perp), score
        return best

    def pair_arrows(self):
        arrows = list(self.ex.arrows)
        used, dims = set(), []
        cands = []
        for i, a in enumerate(arrows):
            for j, b in enumerate(arrows):
                if j <= i:
                    continue
                dot = a.direction[0] * b.direction[0] + a.direction[1] * b.direction[1]
                if dot > -0.98:
                    continue
                v = (b.tip[0] - a.tip[0], b.tip[1] - a.tip[1])
                length = math.hypot(*v)
                if length < 1:
                    continue
                if v[0] * a.direction[0] + v[1] * a.direction[1] >= 0:
                    continue  # b must lie behind a (arrows point away from each other)
                off = abs(v[0] * a.direction[1] - v[1] * a.direction[0])
                if off > 1.5:
                    continue
                cands.append((length, i, j))
        for length, i, j in sorted(cands):
            if i in used or j in used:
                continue
            used |= {i, j}
            dims.append((arrows[i], arrows[j]))
        for i, a in enumerate(arrows):
            if i not in used:
                self.issue("warning", "lonely_arrow",
                           "An arrowhead without a matching opposite arrow was found and ignored.",
                           draw={"points": [a.tip]})
        return dims

    def assign_texts(self, dims):
        pairs = []
        for di, (a, b) in enumerate(dims):
            for ti, t in enumerate(self.ex.texts):
                d = _label_score(a.tip, b.tip, t.bbox)
                if d < 25:
                    pairs.append((d, di, ti))
        dim_text, used = {}, set()
        for d, di, ti in sorted(pairs):
            if di in dim_text or ti in used:
                continue
            dim_text[di] = ti
            used.add(ti)
        return dim_text, used

    def build_dimensions(self):
        dims = self.pair_arrows()
        dim_text, used_texts = self.assign_texts(dims)

        units = []
        parsed = {}
        for di in dim_text:
            value, unit, prefix, err = parse_dimension_text(self.ex.texts[dim_text[di]].text)
            parsed[di] = (value, unit, prefix, err)
            if unit and not err:
                units.append(unit)
        self.unit = max(set(units), key=units.count) if units else "mm"

        raw = []
        for di, (a, b) in enumerate(dims):
            dx, dy = abs(a.direction[0]), abs(a.direction[1])
            axis = "x" if dx >= AXIS_COS else "y" if dy >= AXIS_COS else None
            text = self.ex.texts[dim_text[di]] if di in dim_text else None
            draw = {"tips": [list(a.tip), list(b.tip)], "text_bbox": list(text.bbox) if text else None}
            label = f"'{text.text}'" if text else "(no label)"
            if axis is None:
                self.issue("warning", "angled_dimension",
                           f"Dimension {label} is neither horizontal nor vertical; aligned/angled dimensions are not supported.",
                           draw=draw)
                continue
            k = 0 if axis == "x" else 1
            # order tips so that 'lo' is the smaller model coordinate (y up -> larger page y is lower)
            t1, t2 = sorted((a.tip, b.tip), key=lambda p: p[k] if axis == "x" else -p[k])
            size = (a.size + b.size) / 2
            att1, att2 = self._attach(t1, axis, size), self._attach(t2, axis, size)
            draw["tips"] = [list(t1), list(t2)]
            if not att1 or not att2:
                self.issue("warning", "unattached_dimension",
                           f"Dimension {label} does not point at any edge of the part and was ignored.", draw=draw)
                continue
            if att1[0] == att2[0]:
                self.issue("warning", "degenerate_dimension",
                           f"Both ends of dimension {label} point at the same edge position; ignored.", draw=draw)
                continue
            gap = max(att1[2], att2[2])
            if gap > 2.0:
                self.issue("info", "snapped_dimension",
                           f"Dimension {label} does not quite touch the geometry ({gap:.1f} pt gap); snapped to the nearest edge.",
                           draw=draw)

            value, unit, prefix, err = parsed.get(di, (None, None, None, "has no value label"))
            if text is None:
                err = "has no value label next to it"
            if not err and prefix:
                err = f"is a {'radius' if prefix == 'R' else 'diameter'} dimension, which needs curved geometry (not supported)"
            if not err and unit is None:
                unit = self.unit
                self.issue("warning", "missing_unit",
                           f"Dimension {label} has no unit; assumed {self.unit}.", draw=draw)
            if not err and unit != self.unit:
                value = value * UNIT_IN_MM[unit] / UNIT_IN_MM[self.unit]
            raw.append({"axis": axis, "lo": att1[0], "hi": att2[0], "value": value, "error": err,
                        "text": text.text if text else None, "draw": draw,
                        "attach": [att1[1], att2[1]], "lat_draw": (t1[1 - k] + t2[1 - k]) / 2,
                        "draw_len": abs(t2[k] - t1[k])})

        for ti, t in enumerate(self.ex.texts):
            if ti in used_texts:
                continue
            m = THICKNESS_RE.search(t.text)
            if m:
                continue
            value, unit, prefix, err = parse_dimension_text(t.text)
            if not err:
                self.issue("warning", "orphan_text",
                           f"Text '{t.text}' looks like a dimension but has no dimension line/arrows; ignored.",
                           draw={"text_bbox": list(t.bbox)})
        return raw

    # ------------------------------------------------------------------ constraint graph
    def build_params(self, raw):
        wuf = {"x": _WeightedUF(), "y": _WeightedUF()}
        for ax in "xy":
            for l in self.levels[ax]:
                wuf[ax].find(l["id"])

        valid = [r for r in raw if not r["error"]]
        # overall dimensions first: chained detail dimensions become 'reference' if redundant
        valid.sort(key=lambda r: -r["draw_len"])
        driving_by_axis = defaultdict(list)
        for r in valid:
            p = self._new_param(r, source="drawing")
            implied = wuf[r["axis"]].union(r["lo"], r["hi"], r["value"])
            if implied is None:
                p["role"] = "driving"
                driving_by_axis[r["axis"]].append(p)
            elif abs(implied - r["value"]) <= max(1e-6, 0.0005 * r["value"]):
                p["role"] = "reference"
                self.issue("info", "redundant_dimension",
                           f"{p['name']} ({p['text']}) is already determined by other dimensions; shown as a reference value.",
                           params=[p["id"]], draw=p["draw"])
            else:
                p["role"] = "conflict"
                chain = self._chain(driving_by_axis[r["axis"]], r["lo"], r["hi"])
                names = ", ".join(f"{c['name']} = {_fmt(c['value'])} {self.unit}" for c in chain)
                self.issue("error", "conflicting_dimension",
                           f"Conflicting dimensions: {p['name']} says {_fmt(r['value'])} {self.unit}, but "
                           f"{names} give {_fmt(implied)} {self.unit}. {p['name']} was ignored — fix the drawing or adjust a value.",
                           params=[p["id"]] + [c["id"] for c in chain], draw=p["draw"])

        for r in raw:
            if r["error"]:
                # we know *what* is dimensioned, just not the value -> estimate it
                r = dict(r)
                p = self._new_param(r, source="estimated")
                p["invalid_text"] = r["text"]
                p["_reason"] = r["error"]

        self._infer(wuf)
        self._name_params()

    def _chain(self, driving, lo, hi):
        adj = defaultdict(list)
        for p in driving:
            adj[p["lo"]].append((p["hi"], p))
            adj[p["hi"]].append((p["lo"], p))
        prev, stack = {lo: None}, [lo]
        while stack:
            n = stack.pop()
            for m, p in adj[n]:
                if m not in prev:
                    prev[m] = (n, p)
                    stack.append(m)
        out, n = [], hi
        while prev.get(n):
            n, p = prev[n]
            out.append(p)
        return out

    def _new_param(self, r, source):
        p = {"id": f"p{len(self.params) + 1}", "kind": "linear", "axis": r["axis"], "lo": r["lo"], "hi": r["hi"],
             "value": r.get("value"), "unit": self.unit, "source": source, "role": "driving",
             "text": r.get("text"), "draw": r.get("draw"), "attach": r.get("attach"),
             "lat_draw": r.get("lat_draw"), "name": None}
        self.params.append(p)
        return p

    def _scale(self, axis):
        """Model units per pt, estimated from drawing dimensions (median, robust to non-scale drawings)."""
        def ratios(ax):
            out = []
            for p in self.params:
                if p["source"] == "drawing" and p["role"] in ("driving", "reference") and p["axis"] == ax:
                    d = abs(self.level(p["hi"])["draw"] - self.level(p["lo"])["draw"])
                    if d > 1:
                        out.append(p["value"] / d)
            return out
        r = ratios(axis) or ratios("y" if axis == "x" else "x")
        return median(r) if r else 1 / PT_PER_UNIT[self.unit]

    def _infer(self, wuf):
        """Connect every coordinate level into a single constraint tree per axis.

        Missing relations are filled in (and reported) by, in order of
        preference: assuming alignment with a level at the same drawn
        position, or estimating a distance from the drawing proportions.
        """
        pending = [p for p in self.params if p["source"] == "estimated"]
        for axis in "xy":
            uf = wuf[axis]
            sign = 1 if axis == "x" else -1  # model coordinate grows with page x, against page y
            levels = sorted(self.levels[axis], key=lambda l: sign * l["draw"])
            if not levels:
                continue
            draw = {l["id"]: sign * l["draw"] for l in levels}
            neighbours = defaultdict(set)  # levels joined by an edge perpendicular to the axis
            for e in self.edges:
                a, b = (self.vertices[i][axis] for i in e["v"])
                if a != b:
                    neighbours[a].add(b)
                    neighbours[b].add(a)
            scale = self._scale(axis)

            def comp_of(lid):
                return uf.find(lid)[0]

            root = max({comp_of(l["id"]) for l in levels},
                       key=lambda c: (sum(1 for l in levels if comp_of(l["id"]) == c), -min(
                           draw[l["id"]] for l in levels if comp_of(l["id"]) == c)))
            while True:
                solved = {l["id"]: uf.find(l["id"])[1] for l in levels if comp_of(l["id"]) == root}
                todo = [l["id"] for l in levels if l["id"] not in solved]
                if not todo:
                    break

                # 1) a dimension that exists but has an unreadable value
                p_est = next((p for p in pending if p["axis"] == axis and
                              (p["lo"] in solved) != (p["hi"] in solved)), None)
                # 2) otherwise pick the closest relation, preferring alignment and geometric adjacency
                best = None
                if p_est is None:
                    for l in todo:
                        for s in solved:
                            dd = abs(draw[l] - draw[s])
                            score = (0 if dd <= ALIGN_TOL else 1 if s in neighbours[l] else 2, dd)
                            if best is None or score < best[0]:
                                best = (score, l, s)
                    _, l, s = best
                    lo, hi = (s, l) if draw[s] <= draw[l] else (l, s)
                    p = self._new_param({"axis": axis, "lo": lo, "hi": hi,
                                         "lat_draw": None, "attach": None},
                                        source="aligned" if best[0][0] == 0 else "estimated")
                else:
                    p = p_est
                    pending.remove(p)
                    l, s = (p["hi"], p["lo"]) if p["lo"] in solved else (p["lo"], p["hi"])

                if p["source"] == "aligned":
                    p["value"] = 0.0
                else:
                    est_pos = self._interp(l, draw, solved, scale)
                    value = abs(est_pos - solved[s])
                    step = 1 if self.unit == "mm" else 0.1 if self.unit in ("cm", "in") else 0.001
                    p["value"] = max(step, round(value / step) * step)
                    p["value"] = round(p["value"], 6)
                uf.union(p["lo"], p["hi"], p["value"])

        for p in pending:  # unreadable dimension that turned out redundant
            p["role"] = "reference"

    def _interp(self, lid, draw, solved, scale):
        """Estimate a model coordinate from drawing proportions between dimensioned neighbours."""
        x = draw[lid]
        below = [s for s in solved if draw[s] < x - ALIGN_TOL]
        above = [s for s in solved if draw[s] > x + ALIGN_TOL]
        b = max(below, key=lambda s: draw[s]) if below else None
        a = min(above, key=lambda s: draw[s]) if above else None
        if a and b and solved[a] > solved[b]:
            t = (x - draw[b]) / (draw[a] - draw[b])
            return solved[b] + t * (solved[a] - solved[b])
        if b:
            return solved[b] + (x - draw[b]) * scale
        return solved[a] - (draw[a] - x) * scale

    # ------------------------------------------------------------------ naming
    def _name_params(self):
        outer = next((l for l in self.loops if l["kind"] == "outer"), None)
        if outer is None:
            return
        # solved positions (several levels can share the extreme, e.g. a top edge split by a notch)
        pos = {}
        for ax in "xy":
            adj = defaultdict(list)
            for p in self.params:
                if p["axis"] == ax and p["role"] == "driving":
                    adj[p["lo"]].append((p["hi"], p["value"]))
                    adj[p["hi"]].append((p["lo"], -p["value"]))
            for l in self.levels[ax]:
                if l["id"] in pos:
                    continue
                pos[l["id"]], stack = 0.0, [l["id"]]
                while stack:
                    n = stack.pop()
                    for m, d in adj[n]:
                        if m not in pos:
                            pos[m] = pos[n] + d
                            stack.append(m)
        ext = {}
        for ax in "xy":
            vals = [pos[self.vertices[v][ax]] for v in outer["vertices"]]
            ext[ax] = (min(vals), max(vals))
        counters = defaultdict(int)
        for p in self.params:
            ax = p["axis"]
            wl = "width" if ax == "x" else "height"
            lo_loops, hi_loops = self.level_loops(p["lo"]), self.level_loops(p["hi"])
            holes_lo = sorted(i for i in lo_loops if i != 0)
            holes_hi = sorted(i for i in hi_loops if i != 0)
            if p["source"] == "aligned":
                name = f"{'Vertical' if ax == 'x' else 'Horizontal'} alignment offset"
            elif 0 in lo_loops and 0 in hi_loops and \
                    abs(pos[p["lo"]] - ext[ax][0]) < 1e-9 and abs(pos[p["hi"]] - ext[ax][1]) < 1e-9:
                name = "Overall length" if ax == "x" else "Overall height"
            elif 0 in lo_loops and 0 in hi_loops:
                counters[("outline", ax)] += 1
                name = f"Outline {wl} {counters[('outline', ax)]}"
            elif holes_lo and set(holes_lo) & set(holes_hi):
                h = sorted(set(holes_lo) & set(holes_hi))[0]
                name = f"Cutout {h} {wl}"
            elif holes_hi and 0 in lo_loops:
                side = "left" if ax == "x" else "bottom"
                name = f"Cutout {holes_hi[0]} from {side} edge"
            elif holes_lo and 0 in hi_loops:
                side = "right" if ax == "x" else "top"
                name = f"Cutout {holes_lo[0]} from {side} edge"
            elif holes_lo and holes_hi:
                name = f"Cutout {holes_lo[0]} ↔ cutout {holes_hi[0]} {'spacing' if ax == 'x' else 'vertical spacing'}"
            else:
                counters[("misc", ax)] += 1
                name = f"{'Horizontal' if ax == 'x' else 'Vertical'} distance {counters[('misc', ax)]}"
            p["name"] = name

        # disambiguate duplicates
        seen = defaultdict(int)
        for p in self.params:
            seen[p["name"]] += 1
        dup = defaultdict(int)
        for p in self.params:
            if seen[p["name"]] > 1:
                dup[p["name"]] += 1
                p["name"] = f"{p['name']} ({dup[p['name']]})"

        for p in self.params:
            if p["source"] == "estimated" and p["role"] == "driving":
                reason = p.pop("_reason", None)
                why = f"the dimension {reason}" if reason else "it is not dimensioned in the drawing"
                sev = "error" if reason else "warning"
                self.issue(sev, "invalid_dimension" if reason else "missing_dimension",
                           f"{p['name']}: {why}. Estimated {_fmt(p['value'])} {self.unit} from the drawing "
                           f"proportions — please verify and enter the correct value.",
                           params=[p["id"]], draw=p["draw"] or self._param_draw_hint(p))
            elif p["source"] == "aligned":
                self.issue("info", "assumed_alignment",
                           f"Edges at the same drawn position were assumed to be aligned ({p['name']} = 0). "
                           f"Change it if they should be offset.",
                           params=[p["id"]], draw=self._param_draw_hint(p))
            p.pop("_reason", None)

    def _param_draw_hint(self, p):
        k = 0 if p["axis"] == "x" else 1
        pts = [v["draw"] for v in self.vertices if v[p["axis"]] in (p["lo"], p["hi"])]
        return {"points": pts} if pts else None

    # ------------------------------------------------------------------ thickness
    def build_thickness(self):
        for t in self.ex.texts:
            m = THICKNESS_RE.search(t.text)
            if m:
                value = float(m.group(1).replace(",", "."))
                unit = (m.group(2) or self.unit).lower()
                value = value * UNIT_IN_MM[unit] / UNIT_IN_MM[self.unit]
                self.params.append({"id": "thickness", "kind": "thickness", "name": "Thickness (extrusion)",
                                    "value": round(value, 6), "unit": self.unit, "source": "drawing",
                                    "role": "driving", "text": t.text, "draw": {"text_bbox": list(t.bbox)}})
                return
        default = {"mm": 10, "cm": 1, "m": 0.01, "in": 0.5}[self.unit]
        self.params.append({"id": "thickness", "kind": "thickness", "name": "Thickness (extrusion)",
                            "value": default, "unit": self.unit, "source": "default", "role": "driving",
                            "text": None, "draw": None})
        self.issue("warning", "missing_thickness",
                   f"The drawing does not specify a thickness (e.g. 't=18mm'). A default of {_fmt(default)} {self.unit} "
                   "was used — set the real thickness.", params=["thickness"])

    # ------------------------------------------------------------------ output
    def build(self) -> dict:
        self.build_outline()
        if self.loops:
            self.build_levels()
            raw = self.build_dimensions()
            if not raw:
                self.issue("error", "no_dimensions",
                           "No usable dimensions were found. All sizes were estimated from the drawing scale "
                           f"(assumed 1:1 in {self.unit}) — enter real values for every parameter.")
            self.build_params(raw)
            self.build_thickness()
            self._scale_info()
        order = {"error": 0, "warning": 1, "info": 2}
        self.issues.sort(key=lambda i: order[i["severity"]])
        return {
            "version": 1,
            "unit": self.unit,
            "page": {"width": self.ex.width, "height": self.ex.height},
            "levels": self.levels,
            "vertices": self.vertices,
            "edges": self.edges,
            "loops": self.loops,
            "params": self.params,
            "issues": self.issues,
        }

    def _scale_info(self):
        ratios = []
        for p in self.params:
            if p.get("kind") == "linear" and p["source"] == "drawing" and p["role"] == "driving":
                d = abs(self.level(p["hi"])["draw"] - self.level(p["lo"])["draw"])
                if d > 1:
                    ratios.append(d / p["value"])
        if len(ratios) >= 2 and max(ratios) / min(ratios) > 1.15:
            self.issue("info", "not_to_scale",
                       f"The drawing is not to scale (between {min(ratios):.1f} and {max(ratios):.1f} pt per {self.unit}). "
                       "The model is built from the dimension values; proportions are used only for missing values.")


def build_model(pdf_bytes: bytes, page_index: int = 0) -> tuple[dict, fitz.Page, fitz.Document]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    if doc.page_count == 0:
        raise ValueError("The PDF has no pages.")
    page = doc[page_index]
    ex = extract_page(page)
    model = SketchBuilder(ex).build()
    model["page"]["index"] = page_index
    model["page"]["count"] = doc.page_count
    no_dims = any(i["code"] == "no_dimensions" for i in model["issues"])
    if (not ex.texts and ex.glyph_paths == 0 and ex.arrows) or (no_dims and ex.arrows and ex.outlined_glyphs >= 20):
        model["issues"].insert(0, {"severity": "error", "code": "no_text",
                                   "message": "The PDF contains no readable text; dimension values may be converted to outlines. "
                                              "Re-export the drawing with text kept as text." if not ex.texts else
                                              f"The dimension values are drawn as outlines ({ex.outlined_glyphs} letter shapes), "
                                              "not as text — they cannot be read, so every size is a guess. Re-export the drawing "
                                              "with text kept as text.",
                                   "params": [], "draw": None})
    return model, page, doc
