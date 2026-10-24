"""3D printer profiles, build-volume fit check and splitting a part into printable pieces."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from shapely.geometry import LineString, box

from .joints import Seam, apply_joints, pocket_faces, protrusion_mm
from .solid import Solid

UNIT_IN_MM = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4}

BUILTIN_PRINTERS = [
    {"id": "creality-ender3-pro", "name": "Creality Ender-3 Pro", "x": 220, "y": 220, "z": 250, "builtin": True},
    {"id": "bambulab-p1s", "name": "Bambu Lab P1S", "x": 256, "y": 256, "z": 256, "builtin": True},
]


class PrinterStore:
    """Built-in printers plus user-defined ones persisted in a JSON file."""

    def __init__(self, path: Path):
        self.path = path

    def _custom(self) -> list[dict]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []

    def all(self) -> list[dict]:
        return BUILTIN_PRINTERS + self._custom()

    def get(self, pid: str) -> dict | None:
        return next((p for p in self.all() if p["id"] == pid), None)

    def save(self, printer: dict) -> dict:
        name = str(printer.get("name", "")).strip()
        if not name:
            raise ValueError("Printer name is required.")
        dims = {}
        for k in ("x", "y", "z"):
            try:
                v = float(printer.get(k))
            except (TypeError, ValueError):
                raise ValueError(f"Build volume {k.upper()} must be a number (mm).") from None
            if not 10 <= v <= 5000:
                raise ValueError(f"Build volume {k.upper()} must be between 10 and 5000 mm.")
            dims[k] = v
        pid = printer.get("id") or "custom-" + (re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "printer")
        if any(p["id"] == pid for p in BUILTIN_PRINTERS):
            raise ValueError("Built-in printers cannot be modified.")
        custom = [p for p in self._custom() if p["id"] != pid]
        entry = {"id": pid, "name": name, **dims, "builtin": False}
        custom.append(entry)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(custom, indent=2), encoding="utf-8")
        return entry

    def delete(self, pid: str):
        if any(p["id"] == pid for p in BUILTIN_PRINTERS):
            raise ValueError("Built-in printers cannot be deleted.")
        custom = [p for p in self._custom() if p["id"] != pid]
        self.path.write_text(json.dumps(custom, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- planning
def _cut_positions(lo, hi, n, max_lens, quality, min_gap):
    """Choose n-1 cut positions in (lo, hi) so that piece k is <= max_lens[k] long.

    Candidates are scored by closeness to a split proportional to each piece's allowance and by
    `quality(pos)` (e.g. how much material the cut goes through -> glue area).
    """
    cuts, prev = [], lo
    step = max((hi - lo) / 2000, 1e-4)
    for k in range(1, n):
        a = max(prev + min_gap, hi - sum(max_lens[k:]))
        b = min(prev + max_lens[k - 1], hi - min_gap)
        if a > b:
            return None
        target = prev + (hi - prev) * max_lens[k - 1] / sum(max_lens[k - 1:])
        best, best_score = None, -math.inf
        steps = max(1, int((b - a) / step))
        for i in range(steps + 1):
            x = a + (b - a) * i / steps
            score = quality(x) - abs(x - target) / max_lens[k - 1]
            if score > best_score:
                best, best_score = x, score
        cuts.append(best)
        prev = best
    if hi - prev > max_lens[-1] + 1e-9:
        return None
    return cuts


def _piece_limits(n, bed_len, joint, single_row):
    """Allowed length (mm) of each of n pieces in a row, given how far the joint reaches into it.

    Through dovetails / one-way knobs grow a piece on its right side only; hidden dovetails grow
    male pieces (every other one) on both sides and leave female pieces as they are; alternating
    knobs may grow any piece on both sides.
    """
    kind = (joint or {}).get("type", "none")
    sides = lambda k: (k > 0) + (k < n - 1)
    reach = protrusion_mm(joint)
    if kind == "hidden_dovetail":
        d = reach / 2
        if single_row:
            return [bed_len - sides(k) * d if k % 2 == 0 else bed_len for k in range(n)]
        return [bed_len - sides(k) * d for k in range(n)]
    if kind == "dovetail" or (kind == "puzzle" and not (joint or {}).get("alternate", True)):
        return [bed_len - (reach if k < n - 1 else 0) for k in range(n)]
    if kind == "puzzle":
        return [bed_len - sides(k) * reach / 2 for k in range(n)]
    return [bed_len] * n


def _pieces_needed(length, bed_len, joint, single_row):
    """Fewest pieces whose allowances add up to the part length (None if the joint is too big)."""
    n = max(1, math.ceil(length / bed_len - 1e-9))
    while n < 200:
        limits = _piece_limits(n, bed_len, joint, single_row) if n > 1 else [bed_len]
        if min(limits) <= 0:
            return None, None
        if sum(limits) >= length - 1e-9:
            return n, limits
        n += 1
    return None, None


def plan(solid: Solid, unit: str, printer: dict, margin_mm: float = 5.0, split: bool = False,
         joint: dict | None = None, avoid=(), bend_zones=()) -> dict:
    """Fit check and (optionally) split into printable pieces.

    avoid: [(axis, from, to), ...] ranges where cuts should not go (e.g. bend zones).
    bend_zones: [(axis, from, to, neutral_radius), ...] so joints on curved seams can be compensated.
    """
    s = UNIT_IN_MM[unit]
    x0, y0, x1, y1 = solid.xy_bounds()
    z0, z1 = solid.z_range()
    size = ((x1 - x0) * s, (y1 - y0) * s, (z1 - z0) * s)
    bed = (printer["x"] - 2 * margin_mm, printer["y"] - 2 * margin_mm, printer["z"])
    issues = []

    def fits(w, h):
        if w <= bed[0] + 1e-9 and h <= bed[1] + 1e-9:
            return "flat"
        if h <= bed[0] + 1e-9 and w <= bed[1] + 1e-9:
            return "rotated"
        return None

    result = {"printer": printer, "margin": margin_mm, "size_mm": size, "usable_mm": bed,
              "fits": bool(fits(size[0], size[1])) and size[2] <= bed[2] + 1e-9, "pieces": [], "issues": issues}
    if size[2] > bed[2] + 1e-9:
        issues.append({"severity": "error", "message": f"The part is {size[2]:.1f} mm tall (lying flat) but the "
                       f"{printer['name']} can only print {bed[2]:.0f} mm high."})
        return result
    if z0 < -1e-9:
        issues.append({"severity": "warning", "message": "The back face has embossed design, so the part will not lie "
                       "flat on the bed — print it face-up with supports, or move the design to the front."})
    if not split:
        return result

    # pick the orientation needing the fewest pieces; integral joints reach into the neighbour
    W, H = size[0], size[1]
    options = []
    for rot, (bx, by) in (("flat", (bed[0], bed[1])), ("rotated", (bed[1], bed[0]))):
        ny0 = max(1, math.ceil(H / by - 1e-9))
        nx0 = max(1, math.ceil(W / bx - 1e-9))
        nx, lx = _pieces_needed(W, bx, joint, single_row=ny0 == 1)
        ny, ly = _pieces_needed(H, by, joint, single_row=nx0 == 1)
        if nx is None or ny is None:
            continue
        options.append((nx * ny, nx, ny, lx, ly, rot))
    if not options:
        issues.append({"severity": "error", "message": "The joint is larger than the build plate."})
        return result
    _, nx, ny, lx, ly, rot = min(options, key=lambda o: o[:3])

    # cut quality looks at the mid-thickness core: surface engraving does not weaken a joint,
    # while cutouts and cut-through design do (and it keeps the search fast on dense patterns)
    base = solid.material_between(0.25 * solid.t, 0.75 * solid.t)
    base = base if not base.is_empty else solid.profile
    edges_x = sorted({c[0] for p in base.geoms for r in (p.exterior, *p.interiors) for c in r.coords})
    edges_y = sorted({c[1] for p in base.geoms for r in (p.exterior, *p.interiors) for c in r.coords})
    span = max(x1 - x0, y1 - y0)

    def quality(axis):
        coords = edges_x if axis == "x" else edges_y
        full = (y1 - y0) if axis == "x" else (x1 - x0)

        def q(v):
            line = LineString([(v, y0 - 1), (v, y1 + 1)]) if axis == "x" else LineString([(x0 - 1, v), (x1 + 1, v)])
            material = base.intersection(line).length / full
            near = min((abs(v - c) for c in coords), default=span)
            sliver = 1.0 if near < 0.01 * span else 0.0  # avoid hairline slivers next to an edge
            in_bend = 2.0 if any(ax == axis and a - 0.01 * span <= v <= b + 0.01 * span for ax, a, b in avoid) else 0.0
            return material - sliver - in_bend
        return q

    min_gap = 0.02 * span
    cx = _cut_positions(x0, x1, nx, [v / s for v in lx], quality("x"), min_gap) if nx > 1 else []
    cy = _cut_positions(y0, y1, ny, [v / s for v in ly], quality("y"), min_gap) if ny > 1 else []
    if cx is None or cy is None:
        issues.append({"severity": "error", "message": "Could not find cut positions that fit the build plate."})
        return result
    xs, ys = [x0] + cx + [x1], [y0] + cy + [y1]

    # cells (grid of pieces) and the seams between neighbours;
    # outer cells extend past the part so nothing is lost at the border
    big = span

    def ext(v, arr, k):
        return v - big if k == 0 else v + big if k == len(arr) - 1 else v

    cells = {}
    for j in range(len(ys) - 1):
        for i in range(len(xs) - 1):
            cells[(i, j)] = box(ext(xs[i], xs, i), ext(ys[j], ys, j), ext(xs[i + 1], xs, i + 1), ext(ys[j + 1], ys, j + 1))
    seams = []
    for j in range(len(ys) - 1):
        for i in range(1, len(xs) - 1):
            seams.append(Seam("x", xs[i], (ys[j], ys[j + 1]), (i - 1, j), (i, j)))
    for j in range(1, len(ys) - 1):
        for i in range(len(xs) - 1):
            seams.append(Seam("y", ys[j], (xs[i], xs[i + 1]), (i, j - 1), (i, j)))

    regions, voids, parts, j_issues, notes, flips = apply_joints(solid, cells, seams, joint, s, bend_zones)
    issues += j_issues

    # print orientation: pockets must open upwards (no unsupported ceilings)
    flip_all = pocket_faces(joint) == "bottom"
    if (flip_all or any(flips.values())) and z1 > solid.t + 1e-9:
        issues.append({"severity": "warning", "message": "Some pieces must print front-face down for the joint, but the "
                       "front has embossed design, so they would need supports. Move the design or print with supports."})
        flip_all, flips = False, {}

    n = 0
    index_of = {}
    for key in cells:
        region = regions[key]
        piece = (solid.clipped_layers(region) if isinstance(region, list) else solid.clipped(region)).carved(voids[key])
        if not piece.slabs:
            continue
        n += 1
        index_of[key] = n
        px0, py0, px1, py1 = piece.xy_bounds()
        w, h = (px1 - px0) * s, (py1 - py0) * s
        i, j = key
        result["pieces"].append({"index": n, "rect": [xs[i], ys[j], xs[i + 1], ys[j + 1]], "cell": [i, j],
                                 "size_mm": (w, h, size[2]), "orientation": fits(w, h) or "too big",
                                 "flip": flip_all or flips.get(key, False), "solid": piece})

    # connector parts, grouped into identical printable parts
    groups = {}
    for part in parts:
        key = (part["kind"], tuple(round(v, 2) for v in sorted(part["size_mm"][:2])), round(part["size_mm"][2], 2))
        g = groups.setdefault(key, {"kind": part["kind"], "name": part["name"], "size_mm": part["size_mm"],
                                    "qty": 0, "instances": []})
        g["qty"] += 1
        g["instances"].append({"solid": Solid.prism(part["shape"], part["z0"], part["z1"], like=solid),
                               "seam": part["seam"], "lift": part["lift"]})
    result["connectors"] = list(groups.values())
    result["seams"] = [{"axis": sm.axis, "pos": sm.pos, "span": sm.span,
                        "pieces": [index_of.get(sm.a), index_of.get(sm.b)]} for sm in seams]
    result["notes"] = sorted(set(notes))
    if flip_all:
        result["notes"].append("Print the pieces back-face up (they are exported that way) so the joint pockets open "
                               "upwards and need no supports.")

    if len(result["pieces"]) > 1:
        kind = (joint or {}).get("type", "none")
        how = {"none": "Glue the pieces together.",
               "dovetail": "Slide the dovetails together (add glue for a permanent joint).",
               "hidden_dovetail": "Slide each male piece's dovetails into the female neighbours (from the back), "
                                  "front faces flush.",
               "puzzle": "Press the puzzle knobs together (add glue for a permanent joint).",
               "butterfly": "Press the butterfly keys into their pockets across each seam.",
               "dowel": "Insert the dowel pins into one piece, then push the next piece on.",
               "plate": "Fit the splice plates into the recesses across each seam (screw or glue)."}.get(kind, "")
        extra = sum(g["qty"] for g in result["connectors"])
        plus = f", plus {extra} connector part(s)" if extra else ""
        issues.append({"severity": "info", "message": f"Split into {len(result['pieces'])} pieces ({nx} × {ny}) to fit "
                       f"the {printer['name']} with a {margin_mm:g} mm bed margin{plus}. {how}"})
    for pc in result["pieces"]:
        if pc["orientation"] == "too big":
            issues.append({"severity": "error", "message": f"Piece {pc['index']} ({pc['size_mm'][0]:.0f} × "
                           f"{pc['size_mm'][1]:.0f} mm) does not fit — reduce the joint size or the bed margin."})
    return result


def assembly_text(result, name):
    """Plain-text assembly sheet included in the export ZIP."""
    lines = [f"{name} — {result['printer']['name']}", "=" * 60, "", "Pieces (print flat):"]
    for p in result["pieces"]:
        w, h, z = p["size_mm"]
        rot = "  (rotate 90 deg on the plate)" if p["orientation"] == "rotated" else ""
        flip = "  (back face up)" if p["flip"] else ""
        lines.append(f"  part{p['index']}: {w:.1f} x {h:.1f} x {z:.1f} mm{rot}{flip}")
    if result.get("connectors"):
        lines += ["", "Connector parts:"]
        for g in result["connectors"]:
            a, b, c = g["size_mm"]
            lines.append(f"  {g['qty']} x {g['name']}: {a:.1f} x {b:.1f} x {c:.1f} mm")
    lines += ["", "Seams:"]
    for k, sm in enumerate(result.get("seams", [])):
        lines.append(f"  cut {k + 1}: part{sm['pieces'][0]} + part{sm['pieces'][1]}")
    lines += [""] + [f"- {n}" for n in result.get("notes", [])]
    lines += [f"- {i['message']}" for i in result["issues"]]
    return "\n".join(lines) + "\n"


def bend_pieces(result, bender, unit, margin_mm, frame=None):
    """Bend the split pieces and their connectors like the whole part, then re-check the printer.

    Each piece / connector gets two bent versions: `solid` levelled on its own (what is printed and
    exported) and `assembled`, placed with the whole part's `frame` (for the exploded preview).
    Connectors on curved seams are bent too, so they fit their curved pockets; identical ones are
    regrouped by curvature.
    """
    from .bend import BentSolid

    s = UNIT_IN_MM[unit]
    ux, uy, uz = result["usable_mm"]
    for p in result["pieces"]:
        flat = p["solid"]
        bent = BentSolid.of(flat, bender)
        p["assembled"] = BentSolid.of(flat, bender, frame) if frame else bent
        x0, y0, x1, y1 = bent.xy_bounds()
        z0, z1 = bent.z_range()
        w, h, z = (x1 - x0) * s, (y1 - y0) * s, (z1 - z0) * s
        p["solid"], p["flip"], p["size_mm"] = bent, False, (w, h, z)
        fits = z <= uz + 1e-9 and ((w <= ux + 1e-9 and h <= uy + 1e-9) or (h <= ux + 1e-9 and w <= uy + 1e-9))
        p["orientation"] = ("flat" if w <= ux + 1e-9 and h <= uy + 1e-9 else "rotated") if fits else "too big"
        if not fits:
            result["issues"].append({"severity": "error", "message": f"Bent piece {p['index']} "
                                     f"({w:.0f} × {h:.0f} × {z:.0f} mm) does not fit the printer."})

    seams = result.get("seams", [])

    def seam_rn(si):
        sm = seams[si]
        return next((op["rn"] for op in bender.ops if sm["axis"] == bender.axis and op["s"] < sm["pos"] < op["e"]), None)

    groups = {}
    curved_parts = 0
    for g in result.get("connectors", []):
        for inst in g["instances"]:
            rn = seam_rn(inst["seam"])
            flat = inst["solid"]
            if rn:
                curved_parts += 1
                printed = BentSolid.of(flat, bender)
                inst["solid"] = printed
                inst["assembled"] = BentSolid.of(flat, bender, frame) if frame else printed
            else:
                inst["assembled"] = BentSolid.of(flat, bender, frame) if frame else flat
            key = (g["kind"], tuple(g["size_mm"]), round(rn, 6) if rn else None)
            grp = groups.setdefault(key, {**{k: v for k, v in g.items() if k not in ("instances", "qty")},
                                          "qty": 0, "instances": [], "curved": bool(rn)})
            if rn:
                grp["name"] = f"{g['name']} (curved)"
            grp["qty"] += 1
            grp["instances"].append(inst)
    if groups:
        result["connectors"] = list(groups.values())

    in_zone = sum(1 for si in range(len(seams)) if seam_rn(si))
    if in_zone:
        result["issues"].append({"severity": "info", "message": f"{in_zone} cut(s) lie in a bend (unavoidable here). "
                                 "The joints there are shaped along the curve"
                                 + (f" and {curved_parts} connector part(s) are printed curved to fit their pockets"
                                    if curved_parts else "")
                                 + "; assemble those pieces by sliding them together along the bend."})
    result["notes"].append("Bent pieces are exported in their bent shape, each levelled at its middle. Curved parts "
                           "usually need supports — or print the flat version (hide the bends) and heat-bend it.")
