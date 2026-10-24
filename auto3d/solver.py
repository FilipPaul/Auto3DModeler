"""Solve the parametric sketch for given parameter values and validate the result."""
from __future__ import annotations

from collections import defaultdict

from shapely.geometry import Polygon
from shapely.validation import explain_validity


class SolveError(ValueError):
    pass


def _fmt(v: float) -> str:
    return f"{v:.3f}".rstrip("0").rstrip(".")


def param_values(model: dict, overrides: dict | None = None) -> dict:
    values = {p["id"]: p["value"] for p in model["params"]}
    for pid, v in (overrides or {}).items():
        if pid in values:
            values[pid] = float(v)
    return values


def solve(model: dict, overrides: dict | None = None) -> dict:
    """Return model-space geometry (y up, model units) or issues explaining why it is invalid."""
    values = param_values(model, overrides)
    params = {p["id"]: p for p in model["params"]}
    issues: list[dict] = []

    def err(msg, pids=()):
        issues.append({"severity": "error", "code": "invalid_value", "message": msg, "params": list(pids)})

    for p in model["params"]:
        v = values[p["id"]]
        if p["role"] != "driving":
            continue
        if p["source"] == "aligned":
            continue  # signed offset, any value allowed
        if not (v > 0):
            err(f"{p['name']} must be greater than zero (got {_fmt(v)}).", [p["id"]])

    pos: dict[str, float] = {}
    for axis in "xy":
        adj = defaultdict(list)
        for p in model["params"]:
            if p.get("kind") == "linear" and p["axis"] == axis and p["role"] == "driving":
                adj[p["lo"]].append((p["hi"], values[p["id"]]))
                adj[p["hi"]].append((p["lo"], -values[p["id"]]))
        levels = [l["id"] for l in model["levels"][axis]]
        for start in levels:
            if start in pos:
                continue
            if pos and any(l in pos for l in levels):
                issues.append({"severity": "error", "code": "underconstrained",
                               "message": f"Some {axis}-positions are not connected to the rest of the sketch.",
                               "params": []})
            pos[start] = 0.0
            stack = [start]
            while stack:
                n = stack.pop()
                for m, d in adj[n]:
                    if m not in pos:
                        pos[m] = pos[n] + d
                        stack.append(m)

    # normalise so the outline's lower-left corner is the origin
    outer = next(l for l in model["loops"] if l["kind"] == "outer")
    verts = {v["id"]: v for v in model["vertices"]}
    ox = min(pos[verts[i]["x"]] for i in outer["vertices"])
    oy = min(pos[verts[i]["y"]] for i in outer["vertices"])
    for lid in pos:
        pos[lid] -= ox if lid[0] == "x" else oy

    loops = []
    for loop in model["loops"]:
        pts = [[pos[verts[i]["x"]], pos[verts[i]["y"]]] for i in loop["vertices"]]
        loops.append({"id": loop["id"], "kind": loop["kind"], "name": loop["name"], "points": pts,
                      "vertices": loop["vertices"]})

    issues += validate(loops, model)

    thickness = values.get("thickness", 1.0)
    if not thickness > 0:
        err("Thickness must be greater than zero.", ["thickness"])

    for p in model["params"]:
        if p["role"] == "reference" and p.get("kind") == "linear":
            values[p["id"]] = pos[p["hi"]] - pos[p["lo"]]

    xs = [pt[0] for pt in loops[0]["points"]]
    ys = [pt[1] for pt in loops[0]["points"]]
    return {
        "ok": not any(i["severity"] == "error" for i in issues),
        "issues": issues,
        "values": values,
        "levels": pos,
        "loops": loops,
        "thickness": thickness,
        "bbox": [min(xs), min(ys), max(xs), max(ys)],
        "annotations": annotations(model, pos, values, [min(xs), min(ys), max(xs), max(ys)]),
    }


def validate(loops: list[dict], model: dict) -> list[dict]:
    issues = []

    def err(msg, loop_ids=()):
        issues.append({"severity": "error", "code": "invalid_geometry", "message": msg,
                       "params": [], "loops": list(loop_ids)})

    polys = []
    for loop in loops:
        poly = Polygon(loop["points"])
        if not poly.is_valid or poly.area <= 1e-9:
            reason = explain_validity(poly) if poly.area > 1e-9 else "zero area"
            err(f"{loop['name']} would be self-intersecting or collapsed ({reason.split('[')[0].strip()}).",
                [loop["id"]])
        elif not poly.exterior.is_ccw:
            err(f"{loop['name']} would be turned inside out — a value made one side cross the other.", [loop["id"]])
        polys.append(poly)
    if issues:
        return issues

    outer = polys[0]
    for loop, poly in zip(loops[1:], polys[1:]):
        if not outer.contains(poly):
            err(f"{loop['name']} would extend outside (or touch) the outer profile.", [loop["id"]])
    for i in range(1, len(polys)):
        for j in range(i + 1, len(polys)):
            if polys[i].intersects(polys[j]):
                err(f"{loops[i]['name']} and {loops[j]['name']} would overlap.", [loops[i]["id"], loops[j]["id"]])
    return issues


def annotations(model: dict, pos: dict, values: dict, bbox) -> list[dict]:
    """Where to draw each dimension in model space (for the 3D viewer)."""
    verts = {v["id"]: v for v in model["vertices"]}
    edges = {e["id"]: e for e in model["edges"]}
    size = max(bbox[2] - bbox[0], bbox[3] - bbox[1])
    gap = 0.045 * size
    outer = next(l for l in model["loops"] if l["kind"] == "outer")
    outer_draw = [verts[i]["draw"] for i in outer["vertices"]]
    draw_box = (min(p[0] for p in outer_draw), min(p[1] for p in outer_draw),
                max(p[0] for p in outer_draw), max(p[1] for p in outer_draw))
    out = []
    outside_count = defaultdict(int)
    for p in model["params"]:
        if p.get("kind") != "linear" or p["role"] == "conflict" or p["source"] == "aligned":
            continue
        ax = p["axis"]
        other = "y" if ax == "x" else "x"
        k_other = 1 if ax == "x" else 0
        a, b = pos[p["lo"]], pos[p["hi"]]
        ref = p.get("lat_ref")
        if ref and ref.get("level") in pos:
            # user-placed dimension: offset from a level of the other axis, so it follows the geometry
            lat = pos[ref["level"]] + float(ref.get("offset", 0))
            p1, p2 = ([a, lat], [b, lat]) if ax == "x" else ([lat, a], [lat, b])
            out.append({"param": p["id"], "p1": p1, "p2": p2, "value": values[p["id"]]})
            continue
        lat = None
        candidates = []
        if p.get("attach") and p.get("lat_draw") is not None:
            for eid in p["attach"]:
                e = edges[eid]
                va, vb = (verts[i] for i in e["v"])
                da, db = va["draw"][k_other], vb["draw"][k_other]
                ma, mb = pos[va[other]], pos[vb[other]]
                if abs(db - da) < 1e-6:
                    continue
                t = (p["lat_draw"] - da) / (db - da)
                candidates.append((abs(mb - ma), t, ma, mb))
        inside = [c for c in candidates if 0.0 <= c[1] <= 1.0]
        lo_b, hi_b = (bbox[1], bbox[3]) if ax == "x" else (bbox[0], bbox[2])
        lo_d, hi_d = (draw_box[1], draw_box[3]) if ax == "x" else (draw_box[0], draw_box[2])
        drawn_inside = p.get("lat_draw") is not None and lo_d <= p["lat_draw"] <= hi_d
        if inside:
            _, t, ma, mb = min(inside)
            lat = ma + t * (mb - ma)
        elif candidates and drawn_inside:
            # beside a feature (e.g. above a cutout): just past the end of the nearest edge
            _, t, ma, mb = min(candidates, key=lambda c: min(abs(c[1]), abs(c[1] - 1)))
            end, over = (mb, t - 1) if t > 1 else (ma, -t)
            direction = 1 if (mb - ma) * (1 if t > 1 else -1) > 0 else -1
            lat = end + direction * max(over * abs(mb - ma), 0.012 * size)
        elif candidates:
            # outside the part: put it beyond the bounding box on the side it was drawn
            _, t, ma, mb = min(candidates)
            guess = ma + t * (mb - ma)
            side = "hi" if guess > (lo_b + hi_b) / 2 else "lo"
            outside_count[(ax, side)] += 1
            n = outside_count[(ax, side)]
            lat = hi_b + gap * n if side == "hi" else lo_b - gap * n
        else:
            # no drawn dimension line (estimated/aligned): place on a joining edge or outside
            joined = None
            for e in model["edges"]:
                va, vb = (verts[i] for i in e["v"])
                if {va[ax], vb[ax]} == {p["lo"], p["hi"]} and va[other] == vb[other]:
                    joined = pos[va[other]]
                    break
            if joined is not None:
                if joined >= hi_b - 1e-9:
                    lat = joined - gap * 0.8
                else:  # e.g. a notch floor: sit in the gap between it and the outline extreme
                    lat = joined + min(gap * 0.8, (hi_b - joined) / 2)
            else:
                outside_count[(ax, "hi")] += 1
                lat = hi_b + gap * outside_count[(ax, "hi")]
        if ax == "x":
            p1, p2 = [a, lat], [b, lat]
        else:
            p1, p2 = [lat, a], [lat, b]
        out.append({"param": p["id"], "p1": p1, "p2": p2, "value": values[p["id"]]})
    return out
