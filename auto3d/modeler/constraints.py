"""Sketch solving with planegcs (FreeCAD's sketch solver): locked sizes drive the sketch.

A sketch (in the feature JSON):
  "points":      {"p1": [u, v], ...}                    (the origin "O" is always (0, 0) and fixed)
  "entities":    [{"id": "l1", "t": "line", "a": "p1", "b": "p2", "g": "r1"},   g = drawn together (a rectangle)
                  {"id": "c1", "t": "circle", "c": "p5", "r": 3},
                  {"id": "a1", "t": "arc", "c": "p6", "a": "p2", "b": "p7"}]   centre, from a counter-clockwise to b
  "constraints": [{"id": "k1", "t": "h", "e": "l1"}, {"t": "v", "e": "l2"}]       horizontal / vertical
                 {"t": "tan", "e": "l1", "arc": "a1", "p": "p7"}   line l1 tangent to arc a1 at their common point p7
                 {"t": "corner", "p": "p2", "lines": ["l1", "l2"]} a rounded corner's sharp point (on both lines)
                 {"t": "on", "p": "p9", "e": "c1"}                  point p9 stays on line / circle / arc c1 (a trimmed end)
  "dims":        [{"id": "d1", "t": "len", "e": "l1", "v": 40},                  locked sizes 🔒
                  {"t": "dia", "e": "c1", "v": 6}, {"t": "rad", "e": "a1", "v": 5},   an arc's radius
                  {"t": "dx", "a": "O", "b": "p5", "v": 10}, {"t": "dy", ...},   distance along x / y
                  {"t": "dist", "a": "p1", "b": "p5", "v": 12}]                   straight distance
  A dimension with "free": true only measures (shown with its live value, not held).
  An end of a distance may be a fixed reference instead of a sketch point: {"ref": [u, v]} — a point of an
  edge of the part the sketch is on (so a hole can be dimensioned from the part's edge).
Lines that share a point are connected. Only what is locked (dims) and the drawn H / V rules hold; the
rest is free, so dragging moves it.
"""
from __future__ import annotations

import math

ORIGIN = "O"


class SketchError(ValueError):
    pass


def _num(v, what):
    try:
        v = float(v)
    except (TypeError, ValueError):
        raise SketchError(f"{what} must be a number.") from None
    if not math.isfinite(v):
        raise SketchError(f"{what} must be a number.")
    return v


def solve(sketch, drag=None, keep=None):
    """Solve the sketch. drag = {point id: [u, v]}: move these points there (as far as the locks allow).
    keep = "u" | "v": try to keep that coordinate of every other point (a typed width moves nothing up or down);
    dropped when the sketch cannot do it.
    -> {"ok", "points", "radii", "dof", "conflicts": [dim ids], "status"}"""
    import planegcs as g

    pts = {k: [float(x) for x in v] for k, v in (sketch.get("points") or {}).items()}
    for k, v in (drag or {}).items():
        if k in pts:
            pts[k] = [float(x) for x in v]

    def build(with_drag, with_keep=False):
        s = g.Sketch()
        ids = {ORIGIN: s.add_fixed_point(0.0, 0.0)}
        for k, (u, v) in pts.items():
            ids[k] = s.add_point(u, v)
        ents, radius = {}, {}
        for e in sketch.get("entities") or []:
            if e.get("t") == "line":
                if e.get("a") not in ids or e.get("b") not in ids:
                    raise SketchError("A line ends at a point that does not exist.")
                ents[e["id"]] = (e, s.add_line(ids[e["a"]], ids[e["b"]]))
            elif e.get("t") == "circle" and "c" in e:
                if e["c"] not in ids:
                    raise SketchError("A circle has no centre point.")
                r = s.add_param(max(_num(e.get("r"), "A radius"), 1e-6))
                radius[e["id"]] = r
                ents[e["id"]] = (e, s.add_circle(ids[e["c"]], r))
            elif e.get("t") == "arc":
                if any(e.get(k) not in ids for k in ("c", "a", "b")):
                    raise SketchError("An arc ends at a point that does not exist.")
                c, a, b = (pts.get(e[k], [0.0, 0.0]) for k in ("c", "a", "b"))
                r0 = max(math.hypot(a[0] - c[0], a[1] - c[1]), 1e-6)
                t0 = math.atan2(a[1] - c[1], a[0] - c[0])
                sweep = (math.atan2(b[1] - c[1], b[0] - c[0]) - t0) % (2 * math.pi) or 2 * math.pi
                ents[e["id"]] = (e, s.add_arc_cse(ids[e["c"]], ids[e["a"]], ids[e["b"]], r0, t0, t0 + sweep))
        def end(x):
            """A sketch point id, or a fixed reference point {"ref": [u, v]} (an edge of the part)."""
            if isinstance(x, dict) and "ref" in x:
                u, v = (_num(c, "A reference point") for c in x["ref"])
                return s.add_fixed_point(u, v)
            return ids.get(x)

        tags = {}
        for k in sketch.get("constraints") or []:
            ent = ents.get(k.get("e"))
            if k.get("t") == "on":  # a trimmed end stays on the line / circle / arc that cut it
                other = ents.get(k.get("e"))
                if other and k.get("p") in ids:
                    {"line": s.point_on_line, "circle": s.point_on_circle, "arc": s.point_on_arc}[other[0]["t"]](ids[k["p"]], other[1])
                continue
            if k.get("t") == "corner":  # a rounded corner's sharp point stays where its two lines would meet
                for ln in k.get("lines") or []:
                    if ln in ents and k.get("p") in ids:
                        s.point_on_line(ids[k["p"]], ents[ln][1])
                continue
            if not ent or ent[0]["t"] != "line":
                continue
            if k.get("t") == "tan":  # line tangent to an arc where they meet: the radius to that point is square to the line
                arc = ents.get(k.get("arc"))
                if arc and k.get("p") in ids:
                    s.perpendicular(ent[1], s.add_line(ids[arc[0]["c"]], ids[k["p"]]))
                continue
            (s.horizontal if k["t"] == "h" else s.vertical)(ent[1])
        for d in sketch.get("dims") or []:
            if d.get("free"):  # 🔓 a dimension that only measures: shown, not held
                continue
            v = _num(d.get("v"), "A size")
            t = d.get("t")
            if t == "len":
                ent = ents.get(d.get("e"))
                if not ent:
                    continue
                if v <= 0:
                    raise SketchError("A length must be greater than zero.")
                tag = s.set_p2p_distance(ids[ent[0]["a"]], ids[ent[0]["b"]], v)
            elif t == "dia":
                ent = ents.get(d.get("e"))
                if not ent:
                    continue
                if v <= 0:
                    raise SketchError("A diameter must be greater than zero.")
                tag = s.set_circle_diameter(ent[1], v)
            elif t == "rad":
                ent = ents.get(d.get("e"))
                if not ent or ent[0]["t"] != "arc":
                    continue
                if v <= 0:
                    raise SketchError("A radius must be greater than zero.")
                tag = s.set_arc_radius(ent[1], v)
            elif t in ("dx", "dy", "dist"):
                a, b = end(d.get("a")), end(d.get("b"))
                if a is None or b is None:
                    continue
                if t == "dist":
                    if v <= 0:
                        raise SketchError("A distance must be greater than zero.")
                    tag = s.set_p2p_distance(a, b, v)
                else:
                    pa, pb = s.get_point_param_ids(a), s.get_point_param_ids(b)
                    i = 0 if t == "dx" else 1
                    tag = s.difference(pa[i], pb[i], s.add_fixed_param(v))
            else:
                continue
            tags[tag] = d.get("id")
        if with_drag:
            for k in drag or {}:
                if k in ids and k != ORIGIN:
                    s.fix_point(ids[k], *pts[k])
        if with_keep:
            i = 0 if keep == "u" else 1
            for k, p in pts.items():
                if k not in (drag or {}):
                    s.difference(s.add_fixed_param(0.0), s.get_point_param_ids(ids[k])[i], s.add_fixed_param(p[i]))
        return s, ids, ents, radius, tags

    good = (g.SolveStatus.Success, g.SolveStatus.Converged)
    if keep in ("u", "v"):
        # first where the points go when the other coordinate stays; then the plain solve from there (it only
        # checks: the free sizes and the conflicts are those of the sketch itself, not of this extra hold)
        s, ids, ents, radius, tags = build(bool(drag), True)
        if s.solve() in good and not s.diagnose().conflicting:
            for k in pts:
                pts[k] = list(s.get_point(ids[k]))
            for k, r in radius.items():
                next(e for e in sketch.get("entities") or [] if e.get("id") == k)["r"] = s.get_param(r)
    s, ids, ents, radius, tags = build(bool(drag))
    status = s.solve()
    if drag:
        if status in good:
            # where the held points let it go; the final solve (and its check) is without the hold, which itself
            # can make locks look redundant (a held corner on a held line)
            for k in pts:
                pts[k] = list(s.get_point(ids[k]))
            for k, r in radius.items():
                next(e for e in sketch.get("entities") or [] if e.get("id") == k)["r"] = s.get_param(r)
        # (else the drag fights a lock: keep the locks, the dragged points go as close as they can)
        s, ids, ents, radius, tags = build(False)
        status = s.solve()
    ok = status in (g.SolveStatus.Success, g.SolveStatus.Converged)
    diag = s.diagnose()
    conflicts = sorted({tags[t] for t in list(diag.conflicting) + list(diag.redundant) if t in tags and tags[t]})
    out_pts = {k: [round(c, 9) for c in s.get_point(ids[k])] for k in pts}
    radii = {k: round(s.get_param(r), 9) for k, r in radius.items()}
    return {"ok": ok and not conflicts, "status": status.name, "points": out_pts, "radii": radii,
            "dof": diag.dof, "conflicts": conflicts}
