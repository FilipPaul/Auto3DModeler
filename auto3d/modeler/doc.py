"""A 3D model part: an ordered list of features (sketch, extrude, fillet, chamfer, hole) evaluated into one
solid body with named faces (see kernel.py).

Part JSON (in the project file, `parts[].model`):
  {"features": [
     {"id": "F1", "type": "sketch", "name": "Sketch 1", "plane": {"datum": "XY"}, "points": {...}, "entities": [...]},
     {"id": "F2", "type": "extrude", "sketch": "F1", "op": "add" | "cut", "d": 10, "symmetric": false, "flip": false, "through": false},
     {"id": "F3", "type": "sketch", "plane": {"face": {"name": "F2:end"}, "frame": {"o", "x", "n"}}, ...},
     {"id": "F4", "type": "fillet", "edges": [{"a": "F2:end", "b": "F2:side:l1", "fp": [x, y, z]}], "r": 2},
     {"id": "F5", "type": "chamfer", "edges": [...], "d": 1},
     {"id": "F7", "type": "revolve", "sketch": "F1", "axis": "y" | "x" | <a line of the sketch>, "angle": 360, "op": "add"},
     {"id": "F8", "type": "shell", "faces": [{"name": "F2:end", "fp": [x, y, z]}], "t": 2},
     {"id": "F6", "type": "hole", "plane": {"face": {"name": "F2:end"}, "frame": ...}, "points": [[u, v]], "d": 5,
      "through": true, "depth": 10}]}

A sketch or a hole on a face stores the face's frame and its name: when the face moves (the extrude gets
longer), the sketch moves with it. An edge is stored as the two faces it joins (+ where it was).
Features are evaluated in order; one that fails gets an issue and is skipped, the rest still build.
"""
from __future__ import annotations

import hashlib
import json
from collections import OrderedDict

import numpy as np

from . import kernel as K

DATUMS = {
    "XY": {"o": [0, 0, 0], "x": [1, 0, 0], "n": [0, 0, 1]},   # Top
    "XZ": {"o": [0, 0, 0], "x": [1, 0, 0], "n": [0, -1, 0]},  # Front
    "YZ": {"o": [0, 0, 0], "x": [0, 1, 0], "n": [1, 0, 0]},   # Right
}
FEATURE_TYPES = ("sketch", "extrude", "revolve", "fillet", "chamfer", "hole", "shell")

_cache: OrderedDict = OrderedDict()  # prefix hash -> state after that feature (only in the worker process)
CACHE_SIZE = 48


def _key(features):
    return hashlib.sha1(json.dumps(features, sort_keys=True).encode()).hexdigest()


def _num(f, k, default=None, positive=True, what=None):
    v = f.get(k, default)
    try:
        v = float(v)
    except (TypeError, ValueError):
        raise K.KernelError(f"“{what or k}” must be a number.") from None
    if positive and v <= 0:
        raise K.KernelError(f"The {what or 'distance'} must be greater than zero.")
    return v


class State:
    """What the features built so far: the body (with named faces), sketch frames and faces."""

    def __init__(self):
        self.body = None
        self.sketches = {}  # id -> (frame, [(face, edge names)])
        self.frames = {}    # id -> frame (also for the browser)
        self.tools = {}     # id -> [(tool Body, "add" | "cut")]: what the feature added / cut, for patterns

    def copy(self):
        s = State()
        s.body, s.sketches, s.frames, s.tools = self.body, dict(self.sketches), dict(self.frames), dict(self.tools)
        return s


def _face_name(plane):
    ref = (plane or {}).get("face") or {}
    if ref.get("name"):
        return ref["name"]
    if ref.get("feature"):  # first-version files: {feature, role}
        return f"{ref['feature']}:{ref.get('role', 'end')}"
    return None


def plane_frame(plane, st: State):
    if not plane or "datum" in plane:
        fr = DATUMS.get((plane or {}).get("datum", "XY"))
        if not fr:
            raise K.KernelError("Unknown sketch plane.")
        return {k: list(v) for k, v in fr.items()}
    fr = plane.get("frame")
    if not fr:
        raise K.KernelError("The sketch has no plane.")
    fr = {k: [float(x) for x in v] for k, v in fr.items()}
    name = _face_name(plane)
    if name and st.body is not None:
        # follow the face: wherever it is now (its plane), the sketch keeps its place on it
        for face in st.body.faces_of(name):
            pl = K.plane_of(face)
            if pl is None:
                continue
            c, n = pl
            n0 = np.asarray(fr["n"], float)
            if abs(abs(n @ n0) - 1) > 1e-6:
                continue
            o0 = np.asarray(fr["o"], float)
            fr["o"] = [round(float(x), 9) for x in o0 + ((c - o0) @ n0) * n0]
            break
    return fr


def _through_depth(st):
    bb = K.bbox(st.body.shape) if st.body is not None else None
    return (float(np.linalg.norm(np.subtract(bb[3:], bb[:3]))) * 2 + 10) if bb else 1000.0


def _apply(f, st: State, s):
    t = f.get("type")
    fid = f["id"]
    if t == "sketch":
        fr = plane_frame(f.get("plane"), st)
        st.frames[fid] = fr
        f = _follow_refs(f, fr, st, s)
        st.sketches[fid] = (fr, K.sketch_faces(fr, f))
        return
    if t == "extrude":
        sk = st.sketches.get(f.get("sketch"))
        if not sk:
            raise K.KernelError("Its sketch is missing or has a problem.")
        fr, faces = sk
        n = np.asarray(fr["n"], float)
        op = f.get("op", "add")
        through = op == "cut" and f.get("through")
        d = _through_depth(st) if through else _num(f, "d", 10)
        sign = (-1 if op == "cut" else 1) * (-1 if f.get("flip") else 1)
        vec = n * d * sign
        start = -vec / 2 if (f.get("symmetric") and not through) else (-vec / 2 if (through and f.get("symmetric")) else None)
        for face, names in faces:
            _use(st, fid, K.prism_body(face, names, vec, fid, start), op)
        return
    if t == "revolve":
        sk = st.sketches.get(f.get("sketch"))
        if not sk:
            raise K.KernelError("Its sketch is missing or has a problem.")
        fr, faces = sk
        origin, direction = _revolve_axis(f, fr)
        _check_one_side(f, fr, origin, direction)
        angle = _num(f, "angle", 360, what="angle")
        for face, names in faces:
            _use(st, fid, K.revolve_body(face, names, origin, direction, angle, fid), f.get("op", "add"))
        return
    if t == "shell":
        if st.body is None:
            raise K.KernelError("There is no solid yet to hollow out.")
        st.body = K.shell(st.body, K.find_faces(st.body, f.get("faces") or []), _num(f, "t", 2, what="wall thickness"), fid)
        return
    if t in ("fillet", "chamfer"):
        if st.body is None:
            raise K.KernelError("There is no solid yet to round.")
        edges, guessed = K.find_edges(st.body, f.get("edges") or [])
        size = _num(f, "r" if t == "fillet" else "d", 1, what="radius" if t == "fillet" else "size")
        st.body = K.round_edges(st.body, edges, size, fid, chamfer=t == "chamfer")
        if guessed:
            s["warnings"].append(f"{guessed} edge(s) were found again by their position only — check that the right edges are {'rounded' if t == 'fillet' else 'bevelled'}.")
        return
    if t == "hole":
        if st.body is None:
            raise K.KernelError("There is no solid yet to drill into.")
        if not (f.get("plane") or {}).get("frame") or not f.get("points"):
            raise K.KernelError("Click on a face where the hole goes.")
        fr = plane_frame(f.get("plane"), st)
        st.frames[fid] = fr
        pts = f.get("points") or []
        if not pts:
            raise K.KernelError("Click on a face where the hole goes.")
        pts = _hole_from_edges(f, fr, st, s)
        dia = _num(f, "d", 5, what="diameter")
        depth = _through_depth(st) if f.get("through", True) else _num(f, "depth", 10, what="depth")
        n = np.asarray(fr["n"], float)
        for k, (u, v) in enumerate(pts):
            face, names = K.circle_face(fr, float(u), float(v), dia)
            tool = K.prism_body(face, names, -n * depth, fid)
            tool.names = {f"{fid}:hole:{k}": tool.names.get(f"{fid}:side:c", []), f"{fid}:bottom:{k}": tool.names.get(f"{fid}:end", [])}
            _use(st, fid, tool, "cut")
        return
    if t == "pattern":
        before = K.volume(st.body.shape) if st.body is not None else 0
        _pattern(f, st)
        if st.body is not None and abs(K.volume(st.body.shape) - before) < 1e-6 * (1 + before):
            s["warnings"].append("The copies changed nothing — they may land outside the part or on top of each other. Check the direction and the spacing.")
        return
    raise K.KernelError(f"Unknown feature type “{t}”.")


def _uv(fr, p):
    o, x, y = np.asarray(fr["o"], float), np.asarray(fr["x"], float), K.frame_y(fr)
    d = np.asarray(p, float) - o
    return [round(float(d @ x), 9), round(float(d @ y), 9)]


def _ref_uv(end, fr, st):
    """A dimension end that points at the part -> where that point is now, in sketch coordinates (or None).
    {ref: [u, v], vertex: {faces, fp}} = a corner, {ref, edge: {a, b, fp}} = a straight edge (its middle)."""
    if not isinstance(end, dict) or st.body is None:
        return None, False
    if end.get("vertex"):
        p, guessed = K.find_vertex(st.body, end["vertex"].get("faces"), end["vertex"].get("fp"))
        return _uv(fr, p), guessed
    if end.get("edge"):
        edges, guessed = K.find_edges(st.body, [end["edge"]])
        a, b = K.edge_ends(edges[0])
        return _uv(fr, (a + b) / 2), bool(guessed)
    return None, False


def _follow_refs(f, fr, st, s):
    """Dimensions from the part's corners and edges follow them when earlier steps change: the reference points
    are found again (by the names of their faces), the sketch is solved again with them, and the new positions
    are handed back to the browser (s["update"])."""
    dims = f.get("dims") or []
    moved, guessed, new_dims = False, 0, []
    for d in dims:
        d2 = dict(d)
        for k in ("a", "b"):
            try:
                uv, g = _ref_uv(d.get(k), fr, st)
            except K.KernelError:
                s["warnings"].append("A dimension's edge of the part is gone — its distance is kept from where the edge was.")
                uv, g = None, False
            if uv is None:
                continue
            guessed += g
            if any(abs(p - q) > 1e-7 for p, q in zip(uv, d[k]["ref"])):
                d2[k] = {**d[k], "ref": uv}
                moved = True
        new_dims.append(d2)
    if guessed:
        s["warnings"].append(f"{guessed} reference(s) to the part were found again by their position only — check the sketch's dimensions.")
    if not moved:
        return f
    f = {**f, "dims": new_dims}
    from . import available
    if available("planegcs"):
        from .constraints import solve
        r = solve(f)
        if r["ok"]:
            f["points"] = {**(f.get("points") or {}), **r["points"]}
            ents = [{**e, "r": r["radii"][e["id"]]} if e.get("id") in r["radii"] else e for e in f.get("entities") or []]
            f["entities"] = ents
        else:
            s["warnings"].append("The sketch's sizes no longer fit the part's new shape — open the sketch and unlock one.")
    s["update"] = {"dims": f["dims"], "points": f.get("points"), "entities": f.get("entities")}
    return f


def _hole_from_edges(f, fr, st, s):
    """Hole centres placed from the face's edges ({x: {edge, d}, y: {edge, d}} per hole): x = the edge's place
    along the face's x + d (the edge runs along y), likewise y. The edges are found again by their faces' names,
    so the holes keep their distance when the part changes. Without an edge: the stored [u, v] (from the centre)."""
    pts = [list(map(float, p)) for p in f.get("points") or []]
    froms = f.get("from") or []
    changed = False
    for i, p in enumerate(pts):
        spec = froms[i] if i < len(froms) and isinstance(froms[i], dict) else {}
        for axis, k in (("x", 0), ("y", 1)):
            ref = spec.get(axis)
            if not ref or not ref.get("edge"):
                continue
            try:
                edges, _ = K.find_edges(st.body, [ref["edge"]])
            except K.KernelError:
                s["warnings"].append(f"Hole {i + 1}: its edge is gone — it stays where it was.")
                continue
            a, b = (_uv(fr, q) for q in K.edge_ends(edges[0]))
            if abs(a[k] - b[k]) > 1e-6 * (1 + abs(a[k])):
                s["warnings"].append(f"Hole {i + 1}: its edge is not straight across any more — it stays where it was.")
                continue
            v = (a[k] + b[k]) / 2 + float(ref.get("d", 0))
            if abs(v - p[k]) > 1e-9:
                p[k] = round(v, 9)
                changed = True
    if changed:
        s["update"] = {"points": pts}
    return pts


def _use(st, fid, tool, op):
    st.body = K.combine(st.body, tool, op)
    st.tools.setdefault(fid, []).append((tool, op))


MAX_COPIES = 200


def _pattern(f, st):
    """Repeat what other features added or cut: in a row (dir, spacing) or around an axis (evenly over angle)."""
    of = [x for x in (f.get("features") or []) if x]
    if not of:
        raise K.KernelError("Choose what to repeat.")
    tools = []
    for x in of:
        if x not in st.tools:
            raise K.KernelError(f"{x} cannot be repeated (only extrudes, revolves, holes and patterns) — or it comes later.")
        tools.extend(st.tools[x])
    count = int(_num(f, "count", 2, what="count"))
    if count < 2:
        raise K.KernelError("The count must be at least 2 (the original is one of them).")
    if count * len(tools) > MAX_COPIES:
        raise K.KernelError(f"That is too many copies (at most {MAX_COPIES}).")
    fid = f["id"]
    if f.get("kind", "linear") == "circular":
        ax = f.get("axis") or {}
        o, d = np.asarray(ax.get("o", [0, 0, 0]), float), np.asarray(ax.get("d", [0, 0, 1]), float)
        if np.linalg.norm(d) < 1e-9:
            raise K.KernelError("The axis has no direction.")
        angle = _num(f, "angle", 360, what="angle")
        step = angle / count if abs(angle) >= 360 - 1e-9 else angle / (count - 1)
        moves = [dict(axis=(o, d / np.linalg.norm(d)), angle_deg=step * k) for k in range(1, count)]
    else:
        d = np.asarray(f.get("dir") or [1, 0, 0], float)
        if np.linalg.norm(d) < 1e-9:
            raise K.KernelError("The direction has no length.")
        d = d / np.linalg.norm(d) * _num(f, "spacing", 10, what="spacing")
        moves = [dict(shift=d * k) for k in range(1, count)]
    for k, mv in enumerate(moves, 1):
        for tool, op in tools:
            _use(st, fid, K.moved_body(tool, f"{fid}:{k}:", **mv), op)


def _revolve_axis(f, fr):
    """The axis of a revolve in 3D: the sketch's vertical (y) or horizontal (x) axis through its origin, or one
    of its lines."""
    o, x = np.asarray(fr["o"], float), np.asarray(fr["x"], float)
    y = K.frame_y(fr)
    ax = f.get("axis", "y")
    if ax in ("x", "y"):
        return o, (x if ax == "x" else y)
    sk = f.get("_sketch") or {}
    line = next((e for e in sk.get("entities") or [] if e.get("id") == ax and e.get("t") == "line"), None)
    pts = sk.get("points") or {}
    end = lambda i: (0.0, 0.0) if i == "O" else pts.get(i)  # noqa: E731
    if not line or end(line["a"]) is None or end(line["b"]) is None:
        raise K.KernelError("The axis line is no longer in the sketch — choose the axis again.")
    a, b = end(line["a"]), end(line["b"])
    pa = o + a[0] * x + a[1] * y
    d = (b[0] - a[0]) * x + (b[1] - a[1]) * y
    if np.linalg.norm(d) < 1e-9:
        raise K.KernelError("The axis line has no length.")
    return pa, d / np.linalg.norm(d)


def _check_one_side(f, fr, origin, direction):
    """A profile must lie on one side of its axis (crossing it makes an impossible solid)."""
    sk = f.get("_sketch")
    if not sk:
        return
    o, x, y = np.asarray(fr["o"], float), np.asarray(fr["x"], float), K.frame_y(fr)
    a2 = np.array([(origin - o) @ x, (origin - o) @ y])
    d2 = np.array([direction @ x, direction @ y])
    nrm = np.array([-d2[1], d2[0]])
    sides = set()
    pts = sk.get("points") or {}
    for p in pts.values():
        side = (np.asarray(p, float) - a2) @ nrm
        if abs(side) > 1e-7:
            sides.add(bool(side > 0))
    for e in sk.get("entities") or []:
        if e.get("t") == "circle" and "c" in e:
            c = pts.get(e["c"]) if e["c"] != "O" else (0, 0)
            if c is not None and abs((np.asarray(c, float) - a2) @ nrm) < float(e.get("r", 0)) - 1e-9:
                sides.update({True, False})
    if len(sides) > 1:
        raise K.KernelError("The shape crosses the axis — for a revolve it must lie on one side of the axis.")


def evaluate(features):
    """features -> (State, [{id, ok, issues, warnings}]). Uses the prefix cache: editing feature 7 reuses 1–6."""
    st, status = State(), []
    start = 0
    for i in range(len(features), 0, -1):
        hit = _cache.get(_key(features[:i]))
        if hit:
            st, status = hit[0].copy(), list(hit[1])
            _cache.move_to_end(_key(features[:i]))
            start = i
            break
    for i in range(start, len(features)):
        f = features[i]
        s = {"id": f.get("id"), "ok": True, "issues": [], "warnings": []}
        if f.get("suppressed"):
            s["suppressed"] = True
        else:
            try:
                if f.get("type") == "revolve":  # it needs its sketch's lines (the axis) and points (one side)
                    f = {**f, "_sketch": next((g for g in features if g.get("id") == f.get("sketch")), None)}
                _apply(f, st, s)
            except K.KernelError as e:
                s["ok"], s["issues"] = False, [str(e)]
            except Exception as e:  # noqa: BLE001 — an OCCT failure on odd input: report it, keep the rest
                s["ok"], s["issues"] = False, [f"Could not build this step ({type(e).__name__})."]
        status.append(s)
        _cache[_key(features[: i + 1])] = (st.copy(), list(status))
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
    return st, status


def rebuild(part):
    """The part -> what the browser shows: the body's mesh, faces (with names) and edges, every feature's
    status, the sketch frames."""
    features = (part or {}).get("features") or []
    st, status = evaluate(features)
    out = {"ok": all(s["ok"] for s in status), "features": status, "frames": st.frames, "body": None}
    if st.body is not None:
        out["body"] = K.tessellate(st.body)
    return out


def body_of(part):
    st, _ = evaluate((part or {}).get("features") or [])
    if st.body is None:
        raise K.KernelError("The model has no solid yet — sketch a shape and extrude it.")
    return st


def export(part, fmt):
    st = body_of(part)
    if fmt == "step":
        return K.to_step(st.body.shape)
    if fmt == "stl":
        return K.to_stl(K.tessellate(st.body))
    raise K.KernelError(f"Unknown export format “{fmt}”.")


def assembly_step(instances):
    """An assembly -> one STEP file with every placed part: instances [{part: {features}, matrix: [16]}]."""
    shapes = []
    for inst in instances or []:
        st = body_of(inst.get("part"))
        shapes.append(K.placed(st.body.shape, inst.get("matrix") or [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]))
    if not shapes:
        raise K.KernelError("The assembly is empty — insert parts first.")
    return K.to_step(K.compound(shapes))
