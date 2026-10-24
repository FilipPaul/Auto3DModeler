"""3D printer profiles, build-volume fit check and splitting a part into printable pieces."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from shapely.geometry import LineString, box

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
def _cut_positions(lo, hi, n, max_len, quality, min_gap):
    """Choose n-1 cut positions in (lo, hi) so that every piece is <= max_len.

    Candidates are scored by closeness to a uniform split and by `quality(pos)`
    (e.g. how much material the cut goes through -> glue area).
    """
    cuts, prev = [], lo
    step = max((hi - lo) / 2000, 1e-4)
    for k in range(1, n):
        remaining = n - k
        a = max(prev + min_gap, hi - remaining * max_len)
        b = min(prev + max_len, hi - min_gap)
        if a > b:
            return None
        target = prev + (hi - prev) / (remaining + 1)
        best, best_score = None, -math.inf
        steps = max(1, int((b - a) / step))
        for i in range(steps + 1):
            x = a + (b - a) * i / steps
            score = quality(x) - abs(x - target) / max_len
            if score > best_score:
                best, best_score = x, score
        cuts.append(best)
        prev = best
    if hi - prev > max_len + 1e-9:
        return None
    return cuts


def plan(solid: Solid, unit: str, printer: dict, margin_mm: float = 5.0, split: bool = False) -> dict:
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

    # pick the orientation needing the fewest pieces
    W, H = size[0], size[1]
    options = []
    for rot, (bx, by) in (("flat", (bed[0], bed[1])), ("rotated", (bed[1], bed[0]))):
        nx, ny = max(1, math.ceil(W / bx - 1e-9)), max(1, math.ceil(H / by - 1e-9))
        options.append((nx * ny, nx, ny, bx, by, rot))
    _, nx, ny, bx, by, rot = min(options)

    base = None
    for a, b, sec in solid.slabs:
        if a >= -1e-9 and b <= solid.t + 1e-9:
            base = sec if base is None else base.intersection(sec)
    base = base if base is not None else solid.profile
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
            return material - sliver
        return q

    min_gap = 0.02 * span
    cx = _cut_positions(x0, x1, nx, bx / s, quality("x"), min_gap) if nx > 1 else []
    cy = _cut_positions(y0, y1, ny, by / s, quality("y"), min_gap) if ny > 1 else []
    if cx is None or cy is None:
        issues.append({"severity": "error", "message": "Could not find cut positions that fit the build plate."})
        return result
    xs, ys = [x0] + cx + [x1], [y0] + cy + [y1]
    n = 0
    for j in range(len(ys) - 1):
        for i in range(len(xs) - 1):
            rect = box(xs[i], ys[j], xs[i + 1], ys[j + 1])
            piece = solid.clipped(rect)
            if not piece.slabs:
                continue
            n += 1
            px0, py0, px1, py1 = piece.xy_bounds()
            w, h = (px1 - px0) * s, (py1 - py0) * s
            result["pieces"].append({"index": n, "rect": [xs[i], ys[j], xs[i + 1], ys[j + 1]],
                                     "size_mm": (w, h, size[2]), "orientation": fits(w, h) or "too big",
                                     "solid": piece})
    if len(result["pieces"]) > 1:
        issues.append({"severity": "info", "message": f"Split into {len(result['pieces'])} pieces "
                       f"({nx} × {ny}) to fit the {printer['name']} with a {margin_mm:g} mm bed margin. "
                       "Glue or join the pieces after printing."})
    return result
