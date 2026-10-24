"""2.5D solid: the extruded profile plus embossed / engraved / cut-through design regions.

The solid is described as a stack of z-slabs, each with a constant 2D
cross-section.  From that we produce

* a watertight triangle mesh (viewer + STL), and
* planar B-rep faces (STEP):  horizontal caps where the cross-section changes
  and vertical walls along every slab boundary.

To keep the result watertight, every boundary segment at a z-level is split at
all vertices that any face touching that level has on it (no T-junctions).
"""
from __future__ import annotations

from collections import defaultdict

import shapely
from shapely import affinity
from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from .design import layer_regions, polygons_of, precision_grid, profile_polygon

BASE, FEATURE = 0, 1


def _union(geoms):
    geoms = [g for g in geoms if g is not None and not g.is_empty]
    if len(geoms) == 1:
        return geoms[0]  # already a valid (multi)polygon; re-unioning a complex pattern is expensive
    return unary_union(geoms) if geoms else Polygon()


class Solid:
    def __init__(self, solution: dict, layers: list[dict] | None, unit: str):
        self.profile = profile_polygon(solution)
        self.t = float(solution["thickness"])
        bbox = solution["bbox"]
        self.size = max(bbox[2] - bbox[0], bbox[3] - bbox[1], self.t)
        self.grid = precision_grid(self.size)
        self.eps = self.size * 1e-7
        regions, self.issues = layer_regions(solution, layers or [], unit)
        self.guides = [r for r in regions if r["op"] == "guide"]
        self._build_slabs([r for r in regions if r["op"] != "guide"])

    def clipped(self, rect: Polygon) -> "Solid":
        """The part of this solid inside an xy rectangle (used to split for printing)."""
        piece = Solid.__new__(Solid)
        piece.__dict__.update({k: v for k, v in self.__dict__.items() if k not in ("slabs", "levels", "profile")})
        piece.profile = self.profile.intersection(rect)
        piece.issues, piece.guides = [], []
        piece.slabs = []
        for z0, z1, sec in self.slabs:
            # cheap bounding-box clip first: intersecting a dense pattern with a complex region is costly
            local = shapely.clip_by_rect(sec, *rect.bounds)
            polys = [orient(p, 1.0) for p in polygons_of(shapely.set_precision(local.intersection(rect), self.grid))]
            if polys:
                piece.slabs.append((z0, z1, MultiPolygon(polys)))
        piece.levels = sorted({z for s in piece.slabs for z in s[:2]})
        return piece

    def clipped_layers(self, layers) -> "Solid":
        """Like clipped(), but with a different outline per height: layers = [(z0, z1, Polygon), ...].
        Used by joints that change shape through the thickness (hidden dovetails)."""
        zs = set(self.levels)
        lo, hi = self.z_range()
        for a, b, _ in layers:
            zs |= {min(max(a, lo), hi), min(max(b, lo), hi)}
        zs = sorted(zs)
        slabs = []
        for z0, z1 in zip(zs, zs[1:]):
            if z1 - z0 < 1e-9:
                continue
            zm = (z0 + z1) / 2
            sec = next((s for a, b, s in self.slabs if a <= zm < b), None)
            region = next((r for a, b, r in layers if a <= zm < b), None)
            if sec is None or region is None:
                continue
            slabs.append((z0, z1, shapely.clip_by_rect(sec, *region.bounds).intersection(region)))
        outline = unary_union([r for _, _, r in layers])
        return self._derived(slabs, profile=self.profile.intersection(outline))

    def z_range(self):
        return (self.slabs[0][0], self.slabs[-1][1]) if self.slabs else (0.0, self.t)

    def xy_bounds(self):
        bs = [sec.bounds for _, _, sec in self.slabs]
        return (min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs))

    def base_section(self):
        """Material that runs through the full base thickness [0, t]."""
        return self.material_between(0.0, self.t)

    def material_between(self, z0: float, z1: float):
        """Footprint that is solid over the whole height range [z0, z1] (e.g. where a joint sits)."""
        base = None
        for a, b, sec in self.slabs:
            if b > z0 + 1e-12 and a < z1 - 1e-12:
                base = sec if base is None else base.intersection(sec)
        return MultiPolygon(polygons_of(base)) if base is not None else MultiPolygon()

    # ------------------------------------------------------------------ derived solids
    def _derived(self, slabs, profile=None) -> "Solid":
        s = Solid.__new__(Solid)
        s.__dict__.update({k: v for k, v in self.__dict__.items() if k not in ("slabs", "levels", "profile")})
        s.profile = self.profile if profile is None else profile
        s.issues, s.guides = [], []
        s.slabs = [(z0, z1, MultiPolygon([orient(p, 1.0) for p in polygons_of(shapely.set_precision(sec, self.grid))]))
                   for z0, z1, sec in slabs]
        s.slabs = [sl for sl in s.slabs if not sl[2].is_empty]
        s.levels = sorted({z for sl in s.slabs for z in sl[:2]})
        return s

    @classmethod
    def prism(cls, poly, z0: float, z1: float, like: "Solid") -> "Solid":
        """A plain extruded part (e.g. a connector), sharing tolerances with `like`."""
        s = like._derived([(z0, z1, poly)], profile=poly)
        s.t = z1
        return s

    def carved(self, voids) -> "Solid":
        """Remove material: voids = [(region, z_from, z_to), ...] (pockets, recesses, holes)."""
        voids = [(g, a, b) for g, a, b in voids if g is not None and not g.is_empty and b > a]
        if not voids:
            return self
        zs = set(self.levels)
        lo, hi = self.z_range()
        for _, a, b in voids:
            zs |= {min(max(a, lo), hi), min(max(b, lo), hi)}
        zs = sorted(zs)
        slabs = []
        for z0, z1 in zip(zs, zs[1:]):
            if z1 - z0 < 1e-9:
                continue
            zm = (z0 + z1) / 2
            sec = next((s for a, b, s in self.slabs if a <= zm < b), None)
            if sec is None:
                continue
            cut = _union([g for g, a, b in voids if a <= zm < b])
            slabs.append((z0, z1, sec.difference(cut) if not cut.is_empty else sec))
        return self._derived(slabs)

    def flipped(self) -> "Solid":
        """Turned upside down (180° about the x axis) so the back face is on top."""
        lo, hi = self.z_range()
        cy = sum(self.xy_bounds()[1::2]) / 2
        mirror = lambda g: affinity.scale(g, 1, -1, origin=(0, cy))
        s = self._derived([(lo + hi - z1, lo + hi - z0, mirror(sec)) for z0, z1, sec in reversed(self.slabs)],
                          profile=mirror(self.profile))
        return s

    def translated(self, dx=0.0, dy=0.0, dz=0.0) -> "Solid":
        move = lambda g: affinity.translate(g, dx, dy)
        s = self._derived([(z0 + dz, z1 + dz, move(sec)) for z0, z1, sec in self.slabs], profile=move(self.profile))
        s.t = self.t + dz
        return s

    def at_origin(self) -> "Solid":
        """Moved so its bounding box starts at (0, 0, 0) — convenient for slicers."""
        x0, y0, _, _ = self.xy_bounds()
        return self.translated(-x0, -y0, -self.z_range()[0])

    # ------------------------------------------------------------------ slabs
    def _build_slabs(self, regions):
        t = self.t
        by = defaultdict(list)
        for r in regions:
            by[(r["face"], r["op"])].append(r)
        cut = _union(r["geom"] for r in by[("top", "cut")] + by[("bottom", "cut")])
        top_eng = [(r["depth"], r["geom"]) for r in by[("top", "engrave")]]
        bot_eng = [(r["depth"], r["geom"]) for r in by[("bottom", "engrave")]]
        removed_top = _union([cut] + [g for _, g in top_eng])
        removed_bot = _union([cut] + [g for _, g in bot_eng])
        top_emb = [(r["depth"], r["geom"].difference(removed_top)) for r in by[("top", "emboss")]]
        bot_emb = [(r["depth"], r["geom"].difference(removed_bot)) for r in by[("bottom", "emboss")]]

        if top_eng and bot_eng:
            for dt, gt in top_eng:
                for db, gb in bot_eng:
                    if dt + db >= t - 1e-9 and gt.intersects(gb) and gt.intersection(gb).area > 1e-9:
                        self.issues.append({"severity": "warning", "code": "design", "params": [],
                                            "message": "Front and back engravings overlap and together are as deep as "
                                                       "the part — the overlap is cut through."})

        zs = {0.0, t}
        zs |= {t - d for d, _ in top_eng} | {d for d, _ in bot_eng}
        zs |= {t + h for h, g in top_emb if not g.is_empty} | {-h for h, g in bot_emb if not g.is_empty}
        zs = sorted(zs)

        def section(zm):
            if 0 < zm < t:
                rem = [cut] + [g for d, g in top_eng if zm > t - d] + [g for d, g in bot_eng if zm < d]
                return self.profile.difference(_union(rem))
            if zm > t:
                return _union([g for h, g in top_emb if zm < t + h])
            return _union([g for h, g in bot_emb if zm > -h])

        self.slabs = []
        for z0, z1 in zip(zs, zs[1:]):
            if z1 - z0 < 1e-9:
                continue
            sec = shapely.set_precision(section((z0 + z1) / 2), self.grid)
            polys = [orient(p, 1.0) for p in polygons_of(sec)]
            if polys:
                self.slabs.append((z0, z1, MultiPolygon(polys)))
        self.levels = sorted({z for s in self.slabs for z in s[:2]})

    def section_at(self, z, above: bool):
        for z0, z1, sec in self.slabs:
            if (above and abs(z0 - z) < 1e-12) or (not above and abs(z1 - z) < 1e-12):
                return sec
        return MultiPolygon()

    # ------------------------------------------------------------------ faces
    def faces(self):
        """Yield planar faces as (kind, z|None, rings, normal, tag).

        kind 'cap': rings = [outer, *holes] (xy, oriented for the normal), z = height
        kind 'wall': rings = [loop of xyz points]
        """
        # vertices present at each z level
        pts_at = {}
        caps = {}
        for z in self.levels:
            below, above = self.section_at(z, False), self.section_at(z, True)
            up = shapely.set_precision(below.difference(above), self.grid)
            down = shapely.set_precision(above.difference(below), self.grid)
            caps[z] = ([orient(p, 1.0) for p in polygons_of(up)], [orient(p, 1.0) for p in polygons_of(down)])
            coords = set()
            for g in (below, above, *caps[z][0], *caps[z][1]):
                for p in polygons_of(g):
                    for ring in (p.exterior, *p.interiors):
                        coords.update(ring.coords)
            pts_at[z] = _PointGrid(coords, self.size / 200)

        # coordinates are snapped to self.grid, so a point on a segment is within ~half a grid step;
        # a larger tolerance would pull in vertices from the far side of thin slivers
        tol = 2 * self.grid
        cache = {}

        def split(a, b, z):
            """Points of level z lying on segment a-b (exclusive), ordered from a to b."""
            key = (a, b, z)
            if key in cache:
                return cache[key]
            rev = cache.get((b, a, z))
            if rev is not None:
                return rev[::-1]
            dx, dy = b[0] - a[0], b[1] - a[1]
            L2 = dx * dx + dy * dy
            L = L2 ** 0.5
            found = []
            for p in pts_at[z].near_segment(a, b, tol):
                s = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2
                if 1e-9 < s < 1 - 1e-9 and abs((p[0] - a[0]) * dy - (p[1] - a[1]) * dx) / L <= tol:
                    found.append((s, p))
            res = [p for _, p in sorted(found)]
            cache[key] = res
            return res

        def densify(ring_coords, z):
            out = []
            n = len(ring_coords)
            for i in range(n):
                a, b = ring_coords[i], ring_coords[(i + 1) % n]
                out.append(a)
                out += split(a, b, z)
            return out

        profile_edges = self.profile.boundary.buffer(self.eps * 20)

        for z in self.levels:
            ups, downs = caps[z]
            for polys, normal in ((ups, 1), (downs, -1)):
                for p in polys:
                    rings = [densify(list(p.exterior.coords)[:-1], z)] + \
                            [densify(list(r.coords)[:-1], z) for r in p.interiors]
                    if normal < 0:
                        rings = [list(reversed(r)) for r in rings]
                    tag = BASE if (abs(z) < 1e-12 or abs(z - self.t) < 1e-12) else FEATURE
                    yield "cap", z, rings, (0.0, 0.0, float(normal)), tag

        for z0, z1, sec in self.slabs:
            inside = z0 >= -1e-12 and z1 <= self.t + 1e-12
            for p in sec.geoms:
                for ring in (p.exterior, *p.interiors):
                    c = list(ring.coords)[:-1]
                    for i in range(len(c)):
                        a, b = c[i], c[(i + 1) % len(c)]
                        bottom = [a] + split(a, b, z0) + [b]
                        top = [a] + split(a, b, z1) + [b]
                        loop = [(x, y, z0) for x, y in bottom] + [(x, y, z1) for x, y in reversed(top)]
                        dx, dy = b[0] - a[0], b[1] - a[1]
                        ln = (dx * dx + dy * dy) ** 0.5
                        mid = Point((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                        tag = BASE if inside and profile_edges.contains(mid) else FEATURE
                        yield "wall", None, [loop, len(bottom)], (dy / ln, -dx / ln, 0.0), tag

    # ------------------------------------------------------------------ mesh
    def triangles(self):
        """Return (list of ((x,y,z),(x,y,z),(x,y,z)), tags) with outward-facing CCW winding."""
        tris, tags = [], []
        for kind, z, rings, normal, tag in self.faces():
            if kind == "cap":
                for tri in _triangulate(Polygon(rings[0], rings[1:])):
                    a, b, c = list(tri.exterior.coords)[:3]
                    ccw = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) > 0
                    if ccw != (normal[2] > 0):
                        b, c = c, b
                    tris.append(((a[0], a[1], z), (b[0], b[1], z), (c[0], c[1], z)))
                    tags.append(tag)
            else:
                loop, nb = rings
                if nb == 2 and len(loop) == 4:  # plain quad (no split points): the common case
                    b0, b1, t1, t0 = loop
                    tris += [(b0, b1, t0), (b1, t1, t0)]
                    tags += [tag, tag]
                    continue
                bottom = loop[:nb]
                top = list(reversed(loop[nb:]))  # a -> b at z1
                # zip the two polylines (same direction) into triangles
                i = j = 0
                while i < len(bottom) - 1 or j < len(top) - 1:
                    adv_bottom = j >= len(top) - 1 or (i < len(bottom) - 1 and
                                                       _param(bottom[i + 1], bottom) <= _param(top[j + 1], top))
                    if adv_bottom:
                        tris.append((bottom[i], bottom[i + 1], top[j]))
                        i += 1
                    else:
                        tris.append((bottom[i], top[j + 1], top[j]))
                        j += 1
                    tags.append(tag)
        return tris, tags

    def volume(self):
        return sum((z1 - z0) * sec.area for z0, z1, sec in self.slabs)

    def guide_rings(self):
        out = []
        for g in self.guides:
            z = self.t if g["face"] == "top" else 0.0
            for p in polygons_of(g["geom"]):
                for ring in (p.exterior, *p.interiors):
                    out.append({"layer": g["id"], "z": z, "points": [list(c) for c in ring.coords]})
        return out


def _triangulate(poly):
    """Constrained Delaunay triangles of a cap face; repairs the rare degenerate ring first."""
    try:
        return list(shapely.constrained_delaunay_triangles(poly).geoms)
    except shapely.errors.GEOSException:
        tris = []
        for part in polygons_of(shapely.make_valid(poly)):
            try:
                tris += list(shapely.constrained_delaunay_triangles(part).geoms)
            except shapely.errors.GEOSException:
                continue
        return tris


class _PointGrid:
    """Uniform hash grid for 'which points lie near this segment' queries."""

    def __init__(self, points, cell):
        self.cell = cell
        self.buckets = defaultdict(list)
        for p in points:
            self.buckets[(int(p[0] // cell), int(p[1] // cell))].append(p)

    def near_segment(self, a, b, tol):
        c = self.cell
        i0, i1 = int((min(a[0], b[0]) - tol) // c), int((max(a[0], b[0]) + tol) // c)
        j0, j1 = int((min(a[1], b[1]) - tol) // c), int((max(a[1], b[1]) + tol) // c)
        if (i1 - i0 + 1) * (j1 - j0 + 1) > 4 * len(self.buckets):
            cells = [k for k in self.buckets if i0 <= k[0] <= i1 and j0 <= k[1] <= j1]
        else:
            cells = [(i, j) for i in range(i0, i1 + 1) for j in range(j0, j1 + 1)]
        for k in cells:
            yield from self.buckets.get(k, ())


def _param(p, line):
    a, b = line[0], line[-1]
    dx, dy = b[0] - a[0], b[1] - a[1]
    return ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)
