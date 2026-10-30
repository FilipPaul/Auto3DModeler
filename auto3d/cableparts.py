"""📎 Cable clips and ⛓ energy chains of the parts library (library/cableparts.json) — the same math as
web/js/library/cableparts.js, for the tests and the server: a clip's frames (the cable axis it holds, the face it is
mounted by) worked out for a size, the clips that fit a bundle Ø, and an energy chain laid out as a U.

A clip item carries, in its own coordinates (numbers or formulas of the size's values; `dc`: the cable's Ø):
  "cable": {"axis": {"o": [x, y, z], "d": [x, y, z], "d2": [x, y, z] (a second way it may run: 4-way tie mounts)},
            "dmin": …, "dmax": …, "tie": true (held by a cable tie)}
  "mount": {"kind": "screw" | "adhesive" | "tie", "o": [x, y, z], "n": [x, y, z] (out of the part into the face it is
            fixed on), "screw": "M4", "hole": Ø, "seat": z (where the screw head sits), "holes": [[x, y]…]}
A chain item: "chain": {"pitch", "Bi", "Ba", "hi", "ha", "R", "dmax"} (names of its values; R: the bend radius to the
centre line, the second choice). A link spans x 0…pitch on the centre line, y across, z up.

The U of a chain (its own frame: the fixed end at the origin, the lower run along +x, the bend above it): a chain of
L = links × pitch whose moving end is `travel` along x from the fixed end (on the upper run, 2R up) has a lower run
a = (L − πR + travel) / 2, the half circle of radius R, and an upper run a − travel back to the moving end. Its path
is always L long; the moving end may go ±(L − πR).
"""
from __future__ import annotations

import math

from .modeler.params import ParamError, eval_text

CLIP_KINDS = ("clip", "tie mount")


def vars_of(item: dict, size: str, length=None) -> dict:
    """The values of a choice: the item's vars, the size's values, the second choice (as build.js varsOf)."""
    v = {**(item.get("vars") or {}), **((item.get("sizes") or {}).get(size) or {})}
    ls = item.get("lengths")
    if ls:
        vals = ls["values"] if isinstance(ls.get("values"), list) else (ls.get("values") or {}).get(size, [])
        if vals:
            v[ls.get("param", "L")] = vals[0] if length is None else length
    return v


def num(expr, values: dict) -> float:
    """A number, or a formula of the values (+ − * / and brackets)."""
    if isinstance(expr, (int, float)):
        return float(expr)
    nums = {k: float(x) for k, x in values.items() if isinstance(x, (int, float)) and not isinstance(x, bool)}
    return float(eval_text(str(expr), nums))


def _text(v, values):
    """A mount's word (a screw size): a value's name gives that value, else the word itself."""
    return values.get(v, v) if isinstance(v, str) else v


def cable_range(item: dict, size: str) -> tuple:
    """(dmin, dmax) of the cable a clip of this size holds: its own, or for a clip that gives only its largest Ø (a
    P-clamp) from the next smaller size's largest (below it the smaller size holds it)."""
    keys = list(item["sizes"])
    v, cab = vars_of(item, size), item.get("cable") or {}
    dmax = num(cab["dmax"], v)
    if "dmin" in cab:
        return num(cab["dmin"], v), dmax
    k = keys.index(size)
    return (num(cab["dmax"], vars_of(item, keys[k - 1])) if k else 0.0), dmax


def clip_frames(item: dict, size: str, dc: float | None = None) -> dict:
    """A clip's frames for a size (its own coordinates): {axis: {o, d, d2?}, mount: {kind, o, n, screw, hole, seat?},
    dmin, dmax}; dc: the cable's Ø (a tie mount: where it lies on top) — not said: the largest it holds."""
    dmin, dmax = cable_range(item, size)
    v = {**vars_of(item, size), "dc": dmax if dc is None else float(dc)}
    cab, mo = item.get("cable") or {}, item.get("mount") or {}
    out = {"dmin": dmin, "dmax": dmax, "mount": {"kind": mo.get("kind", "screw")}}
    if cab.get("axis"):
        out["axis"] = {k: [num(x, v) for x in cab["axis"][k]] for k in ("o", "d", "d2") if k in cab["axis"]}
    for k in ("o", "n"):
        if k in mo:
            out["mount"][k] = [num(x, v) for x in mo[k]]
    for k in ("screw",):
        if k in mo:
            out["mount"][k] = _text(mo[k], v)
    for k in ("hole", "seat"):
        if k in mo:
            out["mount"][k] = num(mo[k], v)
    if "holes" in mo:
        out["mount"]["holes"] = [[num(x, v) for x in p] for p in mo["holes"]]
    return out


def clips_for(items: list, d: float) -> list:
    """The clips that hold a bundle of Ø d: per clip item its smallest size that holds it -> [{item, size, dmin, dmax,
    kind, mount}], the snug ones first (a P-clamp of that Ø before a tie mount that takes anything up to 35 mm)."""
    out = []
    for it in items:
        if it.get("kind") not in CLIP_KINDS or not it.get("sizes"):
            continue
        for k in it["sizes"]:
            lo, hi = cable_range(it, k)
            if d > 0 and lo - 1e-9 <= d <= hi + 1e-9:  # (the sizes in order: the smallest that holds it)
                out.append({"item": it["id"], "size": k, "dmin": lo, "dmax": hi, "kind": it["kind"], "mount": (it.get("mount") or {}).get("kind")})
                break
    return sorted(out, key=lambda c: (c["dmax"] - c["dmin"], c["dmax"] - d))


def clip_choices(items: list, d: float) -> list:
    """Every size of every clip, tie mount and tie for a bundle of Ø d (the 📎 pick list) -> [{item, size, dmin, dmax,
    kind, mount, fits, why: None | "small" (dmax < d) | "large" (dmin > d) | "tie" (it goes round the bundle on a tie
    mount)}]: the ones that hold it first, snug first (as clips_for), then the others in their order."""
    fit, rest = [], []
    for it in items:
        if it.get("kind") not in (*CLIP_KINDS, "tie") or not it.get("sizes") or not it.get("cable"):
            continue
        for k in it["sizes"]:
            lo, hi = cable_range(it, k)
            why = "tie" if it["kind"] == "tie" else "small" if d > hi + 1e-9 else "large" if d < lo - 1e-9 else None
            (rest if why else fit).append({"item": it["id"], "size": k, "dmin": lo, "dmax": hi, "kind": it["kind"],
                                           "mount": (it.get("mount") or {}).get("kind"), "fits": not why, "why": why})
    return sorted(fit, key=lambda c: (c["dmax"] - c["dmin"], c["dmax"] - d)) + rest


# ------------------------------------------------------------------ energy chains
def chain_of(item: dict, size: str, R=None, links: int | None = None) -> dict:
    """A chain item's choice -> its numbers {pitch, Bi, Ba, hi, ha, R, dmax, links}."""
    v = vars_of(item, size, R)
    c = {k: num(item["chain"][k], v) for k in ("pitch", "Bi", "Ba", "hi", "ha", "R", "dmax")}
    c["links"] = links or default_links(c)
    return c


def default_links(chain: dict, travel: float = 500.0) -> int:
    """Links for a travel (the fixed end in the middle of it): half the travel + the bend + two links, whole links."""
    return math.ceil((travel / 2 + math.pi * chain["R"] + 2 * chain["pitch"]) / chain["pitch"])


def travel_range(chain: dict) -> tuple:
    """How far the moving end may go from above the fixed end, either way: ±(L − πR)."""
    m = chain["links"] * chain["pitch"] - math.pi * chain["R"]
    return (-m, m) if m > 0 else (0.0, 0.0)


def chain_path(chain: dict, travel: float = 0.0, step_deg: float = 5.0) -> dict:
    """The centre line of a chain laid out as a U, its moving end `travel` along x (clamped to the range) -> {length,
    lower, upper (the runs), travel, ok (in range), points (a polyline: the bend every step_deg), fixed / moving
    {o, d (along the path), n (out of the chain at the end's bracket)}, centre (of the bend)}."""
    L, R = chain["links"] * chain["pitch"], chain["R"]
    lo, hi = travel_range(chain)
    m = min(max(float(travel), lo), hi)
    a = (L - math.pi * R + m) / 2
    u = a - m
    n = max(2, math.ceil(180 / step_deg))
    pts = [[0.0, 0.0, 0.0]] + [[a + R * math.sin(math.pi * i / n), 0.0, R - R * math.cos(math.pi * i / n)] for i in range(n + 1)] + [[m, 0.0, 2 * R]]
    return {"length": a + math.pi * R + u, "lower": a, "upper": u, "travel": m, "ok": lo - 1e-9 <= travel <= hi + 1e-9,
            "points": pts, "centre": [a, 0.0, R],
            "fixed": {"o": [0.0, 0.0, 0.0], "d": [1.0, 0.0, 0.0], "n": [0.0, 0.0, -1.0]},
            "moving": {"o": [m, 0.0, 2 * R], "d": [-1.0, 0.0, 0.0], "n": [0.0, 0.0, 1.0]}}


def point_at(chain: dict, travel: float, s: float) -> tuple:
    """The point and direction s mm along the chain's centre line from its fixed end -> ([x, y, z], [dx, dy, dz])."""
    p = chain_path(chain, travel)
    a, R, m = p["lower"], chain["R"], p["travel"]
    if s <= a:
        return [s, 0.0, 0.0], [1.0, 0.0, 0.0]
    if s <= a + math.pi * R:
        t = (s - a) / R
        return [a + R * math.sin(t), 0.0, R - R * math.cos(t)], [math.cos(t), 0.0, math.sin(t)]
    w = s - a - math.pi * R
    return [a - w, 0.0, 2 * R], [-1.0, 0.0, 0.0]


__all__ = ["vars_of", "num", "cable_range", "clip_frames", "clips_for", "clip_choices", "chain_of", "default_links", "travel_range", "chain_path", "point_at", "ParamError"]
