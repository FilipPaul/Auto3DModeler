"""Mechanical joints between split pieces — all designed to print flat without supports.

Integral joints change the cut line itself (the shape is part of the pieces):
  dovetail, puzzle (jigsaw knobs)
Connector joints add pockets to the pieces plus separate printed parts:
  butterfly keys (bow-ties inlaid across the seam), rectangular dowels (pins in
  bridged pockets inside the cut faces), splice plate (recessed backing plate,
  optional screw pilot holes).

Every joint is a vertical extrusion of a 2D shape, so it fits the 2.5D solid model
and prints in the flat orientation. Sizes are given in mm and converted to model units.
"""
from __future__ import annotations

import math

from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

from .design import polygons_of

WALL_MM = 1.2  # minimum material left around a pocket (≈ 3 perimeters of a 0.4 mm nozzle)

# glue features (channel along the seam + injection ports on the back); "glue": none | groove | ports
GLUE = {"glue": "ports", "groove": 1.2, "port": 2.0}
GLUE_OFF = {**GLUE, "glue": "none"}

JOINT_TYPES = {
    "none": {"name": "Butt joint (glue)", "integral": True, "params": {**GLUE}},
    "dovetail": {"name": "Dovetail — through (interlocking, printed in)", "integral": True, "params": {
        "width": 20.0, "depth": 12.0, "angle": 12.0, "count": 0, "clearance": 0.2, **GLUE_OFF}},
    "hidden_dovetail": {"name": "Dovetail — hidden, flat front (male / female)", "integral": True, "params": {
        "width": 20.0, "depth": 12.0, "angle": 12.0, "skin": 3.0, "count": 0, "clearance": 0.15, **GLUE}},
    "puzzle": {"name": "Jigsaw puzzle knobs (printed in)", "integral": True, "params": {
        "size": 14.0, "alternate": True, "count": 0, "clearance": 0.2, **GLUE_OFF}},
    "butterfly": {"name": "Butterfly keys (separate bow-tie parts)", "integral": False, "params": {
        "length": 36.0, "width": 18.0, "depth": 4.0, "face": "top", "count": 0, "clearance": 0.15}},
    "dowel": {"name": "Rectangular dowel pins (separate parts)", "integral": False, "params": {
        "width": 8.0, "height": 4.0, "length": 30.0, "count": 0, "clearance": 0.2, **GLUE_OFF}},
    "plate": {"name": "Splice plate (separate recessed plate)", "integral": False, "params": {
        "width": 40.0, "depth": 3.0, "margin": 6.0, "face": "bottom", "screws": True, "screw": 3.0,
        "clearance": 0.2}},
}


def joint_catalog():
    return [{"id": k, "name": v["name"], "integral": v["integral"], "params": v["params"]} for k, v in JOINT_TYPES.items()]


class Seam:
    """The cut between piece A (lower coordinate) and piece B, with a local frame:
    u = across the cut, positive into B; v = along the cut."""

    def __init__(self, axis, pos, span, a, b):
        self.axis, self.pos, self.span, self.a, self.b = axis, pos, span, a, b

    def to_world(self, g):
        # local (u, v) -> world. Vertical cut (x = pos): (x, y) = (pos + u, v); horizontal: (x, y) = (v, pos + u)
        if self.axis == "x":
            return affinity.translate(g, self.pos, 0)
        return affinity.affine_transform(g, [0, 1, 1, 0, 0, self.pos])

    def line(self):
        lo, hi = self.span
        if self.axis == "x":
            return LineString([(self.pos, lo), (self.pos, hi)])
        return LineString([(lo, self.pos), (hi, self.pos)])

    def intervals(self, base, min_len):
        """Stretches (v ranges) of the cut that go through solid material."""
        out = []
        for part in getattr(base.intersection(self.line()), "geoms", [base.intersection(self.line())]):
            if isinstance(part, LineString) and part.length >= min_len:
                c = [p[1] if self.axis == "x" else p[0] for p in part.coords]
                out.append((min(c), max(c)))
        return sorted(out)


def _positions(intervals, footprint, pitch, count):
    """Evenly spaced connector positions along a seam, keeping `footprint/2` from each interval end."""
    usable = [(a + footprint / 2, b - footprint / 2) for a, b in intervals if b - a > footprint]
    if not usable:
        return []
    total = sum(b - a for a, b in usable)
    want = count if count and count > 0 else max(1, int((total + footprint) // pitch))
    pos = []
    for a, b in usable:
        n = max(1, round(want * (b - a) / total)) if total > 0 else 1
        if b - a < 1e-9:
            pos.append(a)
            continue
        pos += [a + (b - a) * (k + 0.5) / n for k in range(n)]
    return pos


# --------------------------------------------------------------------------- shapes (local u, v)
def _dovetail(v, w, d, ang, e):
    wt = w + 2 * d * math.tan(math.radians(ang))
    return Polygon([(-e, v - w / 2), (d, v - wt / 2), (d, v + wt / 2), (-e, v + w / 2)])


def _knob(v, D, e, sign):
    neck = box(-e, v - 0.275 * D, 0.75 * D, v + 0.275 * D)
    head = Point(0.75 * D, v).buffer(D / 2, quad_segs=12)
    g = neck.union(head)
    return affinity.scale(g, sign, 1, origin=(0, 0)) if sign < 0 else g


def _bowtie(v, L, W):
    w = W / 2
    return Polygon([(-L / 2, v - W / 2), (0, v - w / 2), (L / 2, v - W / 2),
                    (L / 2, v + W / 2), (0, v + w / 2), (-L / 2, v + W / 2)])


# --------------------------------------------------------------------------- planning
def protrusion_mm(joint):
    """How much longer a piece can get because of an integral joint (mm).

    Dovetail tabs all point from piece A into piece B, so a piece grows on one side only;
    puzzle knobs alternate direction, so a piece can grow on both sides."""
    kind = (joint or {}).get("type", "none")
    p = {**JOINT_TYPES.get(kind, JOINT_TYPES["none"])["params"], **(joint or {})}
    if kind == "dovetail":
        return float(p["depth"])
    if kind == "hidden_dovetail":  # male pieces carry tabs on every side
        return 2 * float(p["depth"])
    if kind == "puzzle":
        return (2 if p.get("alternate", True) else 1) * 1.25 * float(p["size"])
    return 0.0


def _seam_bend_radius(seam, bend_zones):
    """Neutral bend radius at a seam, or None if the seam is not inside a bend zone."""
    for axis, s, e, rn in bend_zones:
        if seam.axis == axis and s < seam.pos < e:
            return rn
    return None


def apply_joints(solid, cells, seams, joint, mm, bend_zones=()):
    """Build pieces + connector parts.

    cells: {key: Polygon} piece regions; seams: [Seam]; mm: millimetres per model unit.
    Returns (regions, voids_by_cell, parts, issues, notes, flips) where a region is either a
    Polygon (same outline through the thickness) or a list of (z0, z1, Polygon) layers, and
    flips = {key: True} for pieces that must print front-face down.
    """
    kind = (joint or {}).get("type", "none")
    spec = JOINT_TYPES.get(kind)
    issues, notes, parts = [], [], []
    regions = dict(cells)
    voids = {k: [] for k in cells}
    flips = {}
    if spec is None:
        issues.append({"severity": "error", "message": f"Unknown joint type '{kind}'."})
        return regions, voids, parts, issues, notes, flips
    p = {**spec["params"], **{k: v for k, v in (joint or {}).items() if k != "type"}}
    if not joint:
        p["glue"] = "none"  # no joint requested at all: a plain cut (the UI's butt joint asks for glue explicitly)
    if not seams:
        return regions, voids, parts, issues, notes, flips

    u = lambda v: float(v) / mm  # mm -> model units
    t = solid.t
    lo_z, hi_z = solid.z_range()
    wall = u(WALL_MM)
    c = u(p.get("clearance", 0.2))
    count = int(p.get("count") or 0)
    # The joint only needs solid material over the height it occupies; shallow surface
    # engravings elsewhere in the thickness must not block it (cut-throughs and cutouts do).
    zb = t - u(p.get("skin", 0))  # hidden dovetail: tabs only below the front skin
    if kind in ("none", "dovetail", "puzzle"):
        zr = (0.25 * t, 0.75 * t)
    elif kind == "hidden_dovetail":
        zr = (0.25 * zb, 0.75 * zb)
    elif kind == "dowel":
        zr = (t / 2 - u(p["height"]) / 2 - c - wall, t / 2 + u(p["height"]) / 2 + c + wall)
    else:  # butterfly / plate: the floor under the recess
        d = u(p["depth"])
        on_top = (p.get("face", "top" if kind == "butterfly" else "bottom") == "top")
        zr = (t - d - wall, t - d) if on_top else (d, d + wall)
    base = solid.material_between(max(zr[0], 0.0), min(zr[1], t))
    inner = base.buffer(-wall, join_style="mitre")
    skipped = 0

    def fits(shape):
        return shape.within(inner)

    keepout = {si: [] for si in range(len(seams))}  # joint features the glue channel must avoid
    curved = []  # extra clearance given to joints on curved seams
    if kind == "hidden_dovetail":
        if u(p["skin"]) < wall or zb < 3 * wall:
            issues.append({"severity": "error", "message": f"Front skin {p['skin']} mm does not suit a {t * mm:.1f} mm "
                           f"part: keep it ≥ {WALL_MM} mm and leave ≥ {3 * WALL_MM:.1f} mm below it for the dovetails."})
            return regions, voids, parts, issues, notes, flips
        male = lambda key: (key[0] + key[1]) % 2 == 0
        lower = dict(cells)
        flips = {key: not male(key) for key in cells}

    for si, seam in enumerate(seams):
        label = f"cut {si + 1}"
        # On a seam inside a bend the pieces are pushed together along the curve, not straight down
        # the thickness: the joint walls fan out by (reach / bend radius), so give integral joints that
        # much extra clearance over the full height.
        rn = _seam_bend_radius(seam, bend_zones)
        reach = {"dovetail": u(p.get("depth", 0)), "hidden_dovetail": u(p.get("depth", 0)),
                 "puzzle": 1.25 * u(p.get("size", 0))}.get(kind, 0.0)
        cs = c + ((hi_z - lo_z) * reach / rn if rn else 0.0)
        if rn and reach:
            curved.append(cs - c)
        if kind == "hidden_dovetail":
            w, d, ang = u(p["width"]), u(p["depth"]), float(p["angle"])
            wt = w + 2 * d * math.tan(math.radians(ang))
            vs = _positions(seam.intervals(base, wt + 2 * wall), wt + 2 * wall, max(3 * wt, u(50)), count)
            owner, other = (seam.a, seam.b) if male(seam.a) else (seam.b, seam.a)
            sign = 1 if owner == seam.a else -1  # tabs always point from the male piece into the female one
            tabs = []
            for v in vs:
                tab = seam.to_world(affinity.scale(_dovetail(v, w, d, ang, c), sign, 1, origin=(0, 0)))
                if fits(tab.buffer(cs)):
                    tabs.append(tab)
                else:
                    skipped += 1
            if tabs:
                g = unary_union(tabs)
                lower[owner] = lower[owner].union(g)
                lower[other] = lower[other].difference(g.buffer(cs, join_style="mitre"))
                keepout[si].append(g)
            else:
                issues.append({"severity": "warning", "message": f"No room for a dovetail on {label} — it stays a butt joint."})
        elif kind == "dovetail":
            w, d, ang = u(p["width"]), u(p["depth"]), float(p["angle"])
            wt = w + 2 * d * math.tan(math.radians(ang))
            vs = _positions(seam.intervals(base, wt + 2 * wall), wt + 2 * wall, max(3 * wt, u(50)), count)
            tabs = []
            for v in vs:
                tab = seam.to_world(_dovetail(v, w, d, ang, c))
                if fits(tab.buffer(cs)):
                    tabs.append(tab)
                else:
                    skipped += 1
            if tabs:
                g = unary_union(tabs)
                regions[seam.a] = regions[seam.a].union(g)
                regions[seam.b] = regions[seam.b].difference(g.buffer(cs, join_style="mitre"))
                keepout[si].append(g)
            else:
                issues.append({"severity": "warning", "message": f"No room for a dovetail on {label} — it stays a butt joint."})
        elif kind == "puzzle":
            D = u(p["size"])
            vs = _positions(seam.intervals(base, 1.3 * D + 2 * wall), 1.3 * D + 2 * wall, max(3 * D, u(45)), count)
            plus, minus = [], []
            for i, v in enumerate(vs):
                sign = 1 if i % 2 == 0 or not p.get("alternate", True) else -1
                knob = seam.to_world(_knob(v, D, c, sign))
                if fits(knob.buffer(cs)):
                    (plus if sign > 0 else minus).append(knob)
                else:
                    skipped += 1
            if plus or minus:
                gp, gm = unary_union(plus), unary_union(minus)
                regions[seam.a] = regions[seam.a].union(gp).difference(gm.buffer(cs))
                regions[seam.b] = regions[seam.b].union(gm).difference(gp.buffer(cs))
                keepout[si] += [gp, gm]
            else:
                issues.append({"severity": "warning", "message": f"No room for puzzle knobs on {label} — it stays a butt joint."})
        elif kind == "butterfly":
            L, W, depth = u(p["length"]), u(p["width"]), u(p["depth"])
            if depth > t - 2 * wall:
                issues.append({"severity": "error", "message": f"Butterfly key depth {p['depth']} mm is too deep for a "
                               f"{t * mm:.1f} mm part (leave ≥ {2 * WALL_MM} mm)."})
                break
            vs = _positions(seam.intervals(base, W + 2 * wall), W + 2 * wall, max(2.5 * W, u(50)), count)
            top = p.get("face", "top") != "bottom"
            z0, z1 = (t - depth, hi_z) if top else (lo_z, depth)
            for v in vs:
                pocket = seam.to_world(_bowtie(v, L, W))
                if not fits(pocket):
                    skipped += 1
                    continue
                voids[seam.a].append((pocket, z0, z1))
                voids[seam.b].append((pocket, z0, z1))
                key = pocket.buffer(-c, join_style="mitre")
                parts.append({"kind": "butterfly", "name": "Butterfly key", "shape": key, "z0": t - depth if top else 0.0,
                              "z1": t if top else depth, "seam": si, "lift": 1 if top else -1,
                              "size_mm": (p["length"] - 2 * p["clearance"], p["width"] - 2 * p["clearance"], p["depth"])})
            if not vs:
                issues.append({"severity": "warning", "message": f"No room for butterfly keys on {label}."})
        elif kind == "dowel":
            w, h, L = u(p["width"]), u(p["height"]), u(p["length"])
            if h + 2 * c > t - 2 * wall:
                issues.append({"severity": "error", "message": f"Dowel height {p['height']} mm does not fit in a "
                               f"{t * mm:.1f} mm thick part (max {(t - 2 * wall - 2 * c) * mm:.1f} mm)."})
                break
            vs = _positions(seam.intervals(base, w + 2 * wall + 2 * c), w + 2 * wall + 2 * c, max(4 * w, u(40)), count)
            zc = t / 2
            for v in vs:
                foot = seam.to_world(box(-L / 2 - c, v - w / 2 - c, L / 2 + c, v + w / 2 + c))
                if not fits(foot):
                    skipped += 1
                    continue
                voids[seam.a].append((foot, zc - h / 2 - c, zc + h / 2 + c))
                voids[seam.b].append((foot, zc - h / 2 - c, zc + h / 2 + c))
                keepout[si].append(foot)
                pin = seam.to_world(box(-L / 2, v - w / 2, L / 2, v + w / 2))
                parts.append({"kind": "dowel", "name": "Dowel pin", "shape": pin, "z0": zc - h / 2, "z1": zc + h / 2,
                              "seam": si, "lift": 0, "size_mm": (p["length"], p["width"], p["height"])})
            if not vs:
                issues.append({"severity": "warning", "message": f"No room for dowels on {label}."})
            elif any(pt["seam"] == si for pt in parts) and w + 2 * c > u(12):
                notes.append(f"Dowel pockets bridge {(w + 2 * c) * mm:.1f} mm — keep bridges under ~12 mm for clean FDM prints.")
        elif kind == "plate":
            W, depth, m = u(p["width"]), u(p["depth"]), u(p["margin"])
            if depth > t - 2 * wall:
                issues.append({"severity": "error", "message": f"Splice plate recess {p['depth']} mm is too deep for a "
                               f"{t * mm:.1f} mm part."})
                break
            top = p.get("face", "bottom") == "top"
            z0, z1 = (t - depth, hi_z) if top else (lo_z, depth)
            for a, b in seam.intervals(base, 2 * m + u(10)):
                rect = seam.to_world(box(-W / 2, a + m, W / 2, b - m))
                if not rect.within(base.buffer(1e-9)):
                    rect = rect.intersection(inner)
                    if rect.is_empty or not isinstance(rect, Polygon):
                        skipped += 1
                        continue
                voids[seam.a].append((rect, z0, z1))
                voids[seam.b].append((rect, z0, z1))
                plate = rect.buffer(-c, join_style="mitre")
                if p.get("screws"):
                    dh, dp = u(float(p["screw"]) + 0.4), u(float(p["screw"]) * 0.8)
                    n = max(1, int((b - a - 2 * m) // u(40)))
                    holes, pilots = [], []
                    for k in range(n):
                        v = a + m + (b - a - 2 * m) * (k + 0.5) / n
                        for uu in (-W / 4, W / 4):
                            ctr = seam.to_world(Point(uu, v))
                            holes.append(ctr.buffer(dh / 2, quad_segs=8))
                            pilots.append(ctr.buffer(dp / 2, quad_segs=8))
                    plate = plate.difference(unary_union(holes))
                    # blind pilot holes from the recess floor, stopping 1.5 mm short of the opposite face
                    pz = (u(1.5), t - depth) if top else (depth, t - u(1.5))
                    for g in pilots:
                        voids[seam.a].append((g, *pz))
                        voids[seam.b].append((g, *pz))
                    notes.append(f"Splice plates: {2 * n} × M{p['screw']:g} self-tapping screws per plate "
                                 f"(pilot Ø{float(p['screw']) * 0.8:.1f} mm, plate holes Ø{float(p['screw']) + 0.4:.1f} mm).")
                bx = plate.bounds
                parts.append({"kind": "plate", "name": "Splice plate", "shape": plate, "z0": t - depth if top else 0.0,
                              "z1": t if top else depth, "seam": si, "lift": 1 if top else -1,
                              "size_mm": ((bx[2] - bx[0]) * mm, (bx[3] - bx[1]) * mm, p["depth"])})
    if curved:
        notes.append(f"{len(curved)} cut(s) lie in a bend: the joint clearance there is increased by up to "
                     f"{max(curved) * mm:.2f} mm (thickness × joint depth ÷ bend radius) so the curved pieces can be "
                     "pushed together along the bend.")
    if kind == "hidden_dovetail":
        # below the skin: dovetailed outline; the front skin keeps the straight cut (flat, flush front)
        regions = {key: [(lo_z - 1, zb, lower[key]), (zb, hi_z + 1, cells[key])] for key in cells}
        notes.append(f"Hidden dovetails: the front {p['skin']:g} mm skin is cut straight, so the assembled front is flat "
                     "with a hairline seam. Male pieces print front-up, female pieces front-down (exported that way).")

    if p.get("glue", "none") != "none" and kind in ("none", "dovetail", "hidden_dovetail", "puzzle", "dowel"):
        _glue(solid, seams, p, kind, zb, keepout, voids, issues, notes, u, wall, lo_z)

    if skipped:
        issues.append({"severity": "warning", "message": f"{skipped} connector position(s) were skipped because they "
                       f"would leave less than {WALL_MM} mm of material next to an edge, cutout or design feature "
                       "(make the joint smaller, or the engraving shallower)."})
    return regions, voids, parts, issues, notes, flips


def _glue(solid, seams, p, kind, zb, keepout, voids, issues, notes, u, wall, lo_z):
    """Glue channel along each seam (in piece B's cut face) and injection ports from the back.

    The channel sits inside the thickness (below the skin for hidden dovetails), so glue spreads
    along the joint and excess collects there instead of squeezing out onto the front face. Ports
    are half-holes in both pieces that form a round hole on the back once assembled: inject thin CA
    or slow epoxy into one until it appears at the next.
    """
    g, dp = u(p["groove"]), u(p["port"])
    top = zb if kind == "hidden_dovetail" else solid.t
    zc = top / 2
    z0, z1 = zc - g / 2, zc + g / 2
    if z0 < wall or z1 > top - wall:
        issues.append({"severity": "warning", "message": f"The part is too thin for a {p['groove']} mm glue channel — "
                       "glue channels were left out."})
        return
    channel_base = solid.material_between(z0 - wall, z1 + wall).buffer(-wall, join_style="mitre")
    port_base = solid.material_between(max(lo_z, 0.0), z1).buffer(-wall, join_style="mitre")
    margin = u(3)
    ports = 0
    for si, seam in enumerate(seams):
        avoid = unary_union(keepout[si]).buffer(u(1)) if keepout[si] else None
        for a, b in seam.intervals(channel_base, 2 * margin + 4 * g):
            strip = seam.to_world(box(0, a + margin, g, b - margin)).intersection(channel_base)
            if avoid is not None:
                strip = strip.difference(avoid)
            for part in polygons_of(strip):
                if part.area < g * g:
                    continue
                voids[seam.b].append((part, z0, z1))
                if p.get("glue") != "ports":
                    continue
                # ports at both ends of every channel run, plus one every ~60 mm
                bx = part.bounds
                va, vb = (bx[1], bx[3]) if seam.axis == "x" else (bx[0], bx[2])
                inset = dp / 2 + u(2)
                if vb - va <= 2 * inset:
                    continue
                n = max(2, int((vb - va) // u(60)) + 1)
                for k in range(n):
                    v = va + inset + (vb - va - 2 * inset) * k / (n - 1)
                    hole = seam.to_world(Point(0, v)).buffer(dp / 2, quad_segs=8)
                    if hole.within(port_base):  # straddles the cut (interior), keeps a wall to outer edges
                        voids[seam.a].append((hole, lo_z, z1))
                        voids[seam.b].append((hole, lo_z, z1))
                        ports += 1
    if p.get("glue") == "ports" and ports:
        notes.append(f"Glue: dry-fit the pieces, then inject thin CA or slow-setting epoxy into a Ø{p['port']:g} mm port "
                     "on the back until it appears at the next port. The channel inside the seam spreads the glue and "
                     "keeps it off the front face.")
    elif p.get("glue") == "groove":
        notes.append("Glue: put a bead of glue into the channel in each cut face, then press the pieces together — "
                     "excess collects in the channel instead of squeezing out onto the front.")


def pocket_faces(joint):
    """Which face the joint's pockets open to ('top' / 'bottom' / None) — decides print orientation."""
    kind = (joint or {}).get("type", "none")
    if kind == "butterfly":
        return "bottom" if (joint or {}).get("face", "top") == "bottom" else "top"
    if kind == "plate":
        return "top" if (joint or {}).get("face", "bottom") == "top" else "bottom"
    return None
