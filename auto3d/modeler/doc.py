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
     {"id": "F9", "type": "mirror", "of": "body" | <a step's id>, "plane": {"datum": "YZ"} | {"face": ..., "frame": ...},
      "copy": true},   (copy: the part and its mirror image; false: the part moved to its mirror image)
     {"id": "F6", "type": "hole", "plane": {"face": {"name": "F2:end"}, "frame": ...}, "points": [[u, v]], "d": 5,
      "through": true, "depth": 10}]}

A sketch or a hole on a face stores the face's frame and its name: when the face moves (the extrude gets
longer), the sketch moves with it. An edge is stored as the two faces it joins (+ where it was).
Features are evaluated in order; one that fails gets an issue and is skipped, the rest still build.
"""
from __future__ import annotations

import hashlib
import math
import json
from collections import OrderedDict

import numpy as np

from . import kernel as K

DATUMS = {
    "XY": {"o": [0, 0, 0], "x": [1, 0, 0], "n": [0, 0, 1]},   # Top
    "XZ": {"o": [0, 0, 0], "x": [1, 0, 0], "n": [0, -1, 0]},  # Front
    "YZ": {"o": [0, 0, 0], "x": [0, 1, 0], "n": [1, 0, 0]},   # Right
}
FEATURE_TYPES = ("sketch", "extrude", "revolve", "fillet", "chamfer", "hole", "shell", "pattern", "solid", "loft", "sweep", "decal", "mirror")

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
        self.sketch_src = {}  # id -> the sketch feature as built (its lines, for a sweep's path)
        self.refs = {}      # id -> Body: solids shown for reference only (not in the part)
        self.colours = {}   # face name -> "#rrggbb": the colours of imported STEP files

    def copy(self):
        s = State()
        s.body, s.sketches, s.frames, s.tools = self.body, dict(self.sketches), dict(self.frames), dict(self.tools)
        s.sketch_src, s.refs, s.colours = dict(self.sketch_src), dict(self.refs), dict(self.colours)
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
        fr = {k: list(v) for k, v in fr.items()}
        off = float((plane or {}).get("offset") or 0)  # a base plane moved along its normal (e.g. 30 mm above the bed)
        fr["o"] = [o + off * n for o, n in zip(fr["o"], fr["n"])]
        return fr
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
        st.sketch_src[fid] = f
        try:
            st.sketches[fid] = (fr, K.sketch_faces(fr, f))
        except K.KernelError as e:
            if "no closed shape" not in str(e) or not any(x.get("t") in ("line", "arc") for x in f.get("entities") or []):
                raise
            st.sketches[fid] = (fr, [])  # open lines: a path for a sweep (a step that needs a closed shape says so)
        return
    if t == "extrude":
        sk = st.sketches.get(f.get("sketch"))
        if not sk:
            raise K.KernelError("Its sketch is missing or has a problem.")
        fr, faces = sk
        n = np.asarray(fr["n"], float)
        op = f.get("op", "add")
        through = op == "cut" and f.get("through")
        if f.get("upto") and not through:
            vec, start = _up_to_face(f, fr, st), None
        else:
            d = _through_depth(st) if through else _num(f, "d", 10)
            sign = (-1 if op == "cut" else 1) * (-1 if f.get("flip") else 1)
            vec = n * d * sign
            start = -vec / 2 if f.get("symmetric") else None
        if not faces:
            raise K.KernelError("Its sketch has no closed shape to extrude.")
        before = K.volume(st.body.shape) if op == "cut" and st.body is not None else None
        for face, names in faces:
            _use(st, fid, K.prism_body(face, names, vec, fid, start), op)
        _cut_check(s, st, before)
        return
    if t == "revolve":
        sk = st.sketches.get(f.get("sketch"))
        if not sk:
            raise K.KernelError("Its sketch is missing or has a problem.")
        fr, faces = sk
        origin, direction = _revolve_axis(f, fr)
        _check_one_side(f, fr, origin, direction)
        angle = _num(f, "angle", 360, what="angle")
        if not faces:
            raise K.KernelError("Its sketch has no closed shape to revolve.")
        before = K.volume(st.body.shape) if f.get("op") == "cut" and st.body is not None else None
        for face, names in faces:
            _use(st, fid, K.revolve_body(face, names, origin, direction, angle, fid), f.get("op", "add"))
        _cut_check(s, st, before)
        return
    if t == "loft":
        ids = [x for x in f.get("sketches") or [] if x]
        if len(ids) < 2:
            raise K.KernelError("A loft goes through at least two sketches — choose them.")
        sections = []
        for x in ids:
            sk = st.sketches.get(x)
            if not sk:
                raise K.KernelError("A sketch of the loft is missing or has a problem.")
            if len(sk[1]) != 1 or K.outline_count(sk[1][0][0]) != 1:
                raise K.KernelError("Each sketch of a loft needs exactly one closed outline (no holes in it).")
            sections.append(sk[1][0])
        _use(st, fid, K.loft_body(sections, fid), f.get("op", "add"))
        return
    if t == "sweep":
        prof, path = st.sketches.get(f.get("profile")), st.sketch_src.get(f.get("path"))
        if not prof or not prof[1]:
            raise K.KernelError("Choose the profile: a sketch with a closed shape.")
        if path is None:
            raise K.KernelError("Choose the path: a sketch of connected lines / arcs.")
        if f.get("path") == f.get("profile"):
            raise K.KernelError("The profile and the path are two different sketches.")
        wire = K.path_wire(st.frames[f["path"]], path)
        for face, names in prof[1]:
            _use(st, fid, K.sweep_body(face, names, wire, fid), f.get("op", "add"))
        return
    if t == "shell":
        if st.body is None:
            raise K.KernelError("There is no solid yet to hollow out.")
        faces, t_ = K.find_faces(st.body, f.get("faces") or []), _num(f, "t", 2, what="wall thickness")
        if not faces:
            raise K.KernelError("Click the face(s) to leave open (e.g. the top of a cup).")
        body = st.body
        st.body = _sized(lambda v: K.shell(body, faces, v, fid), t_, "wall", "mm",
                         "This part cannot be hollowed out with that face open (a rounding or bevel next to it?) — open another face, "
                         "or hollow it out before rounding the edges.")
        return
    if t in ("fillet", "chamfer"):
        if st.body is None:
            raise K.KernelError("There is no solid yet to round.")
        edges, guessed = K.find_edges(st.body, f.get("edges") or [])
        size = _num(f, "r" if t == "fillet" else "d", 1, what="radius" if t == "fillet" else "size")
        if not edges:
            raise K.KernelError("Pick at least one edge.")
        body = st.body
        st.body = _sized(lambda v: K.round_edges(body, edges, v, fid, chamfer=t == "chamfer"), size, "radius" if t == "fillet" else "size", "mm",
                         f"These edges cannot be {'rounded' if t == 'fillet' else 'bevelled'} here (whatever the size) — pick other edges, "
                         "or do it before the steps that changed them.")
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
    if t == "decal":
        # text or a picture outline on a flat face: raised (add) or cut in, depth mm
        if st.body is None:
            raise K.KernelError("There is no solid yet to decorate.")
        if not (f.get("plane") or {}).get("frame"):
            raise K.KernelError("Click on a flat face where it goes.")
        if not f.get("polys"):
            raise K.KernelError("Type some text, or choose a picture.")
        fr = plane_frame(f.get("plane"), st)
        st.frames[fid] = fr
        h = _num(f, "h", 10, what="height")
        w = h * float(f.get("aspect") or 1)
        a = math.radians(float(f.get("angle") or 0))  # turned on the face, about its own middle
        ca, sa = math.cos(a), math.sin(a)
        polys = [[[[x * w * ca - y * h * sa, x * w * sa + y * h * ca] for x, y in ring] for ring in poly] for poly in f["polys"]]
        faces = K.sketch_faces(fr, {"entities": [{"id": fid, "t": "block", "polys": polys, "at": f.get("at") or [0, 0], "scale": 1}]})
        depth = _num(f, "depth", 1, what="depth")
        n = np.asarray(fr["n"], float)
        op = "cut" if f.get("op") == "cut" else "add"
        for face, names in faces:
            _use(st, fid, K.prism_body(face, names, n * depth * (-1 if op == "cut" else 1), fid), op)
        return
    if t == "solid":
        # a ready solid: a quick part placed in an assembly ("step", base64), or an imported STEP / STL ("blob": its
        # file kept by the server). op: add (joined to the part), cut (cut out of it: a cavity it fits in), ref (shown
        # only, for sizing what is made around it)
        shape, cols = _solid_shape(f)
        body = K.solid_body(shape, fid)
        if f.get("colours", True):  # the file's own colours (off: the part's colour)
            st.colours.update({f"{fid}:f{k}": c for k, c in cols.items()})
        bb = K.bbox(body.shape)
        if bb:
            s["bbox"] = [round(v, 3) for v in bb]
        op = f.get("op") or "add"
        if op == "ref":
            st.refs[fid] = body
            return
        if op == "cut" and st.body is None:
            raise K.KernelError("There is nothing to cut it out of yet — make the part first (or show it as a reference).")
        _use(st, fid, body, "cut" if op == "cut" else "add")
        return
    if t == "mirror":
        if st.body is None:
            raise K.KernelError("There is no solid yet to mirror.")
        fr = plane_frame(f.get("plane"), st)
        st.frames[fid] = fr
        o, n = np.asarray(fr["o"], float), np.asarray(fr["n"], float)
        of = f.get("of") or "body"
        before = K.volume(st.body.shape)
        if of == "body":
            if f.get("copy", True):
                _use(st, fid, K.mirrored_body(st.body, f"{fid}:", o, n), "add")
            else:  # the part itself moves to its mirror image (its faces keep their names)
                st.body = K.mirrored_body(st.body, "", o, n)
                return
        else:
            if of not in st.tools:
                raise K.KernelError(f"{of} cannot be mirrored (only extrudes, revolves, holes, patterns…) — or it comes later.")
            for tool, op in list(st.tools[of]):
                _use(st, fid, K.mirrored_body(tool, f"{fid}:", o, n), op)
        if abs(K.volume(st.body.shape) - before) < 1e-6 * (1 + before):
            s["warnings"].append("The mirror image changes nothing — it lands on the part itself (already symmetric there) or outside it. Choose another plane.")
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


def _up_to_face(f, fr, st):
    """Extrude up to a face: as far as the flat face {upto: {name, fp}} is from the sketch (it follows that face when
    earlier steps move it), plus offset (mm; more = past the face, less = short of it)."""
    if st.body is None:
        raise K.KernelError("There is no face to go up to yet.")
    face = K.find_faces(st.body, [f["upto"]])[0]
    pl = K.plane_of(face)
    n = np.asarray(fr["n"], float)
    if pl is None or abs(abs(float(pl[1] @ n)) - 1) > 1e-6:
        raise K.KernelError("Up to a face: pick a flat face parallel to the sketch.")
    dist = float((pl[0] - np.asarray(fr["o"], float)) @ n)
    off = float(f.get("offset") or 0)
    total = dist + (off if dist >= 0 else -off)
    if abs(total) < 1e-6:
        raise K.KernelError("Up to a face: the face is in the sketch's plane — pick another face or give an offset.")
    return n * total


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
                continue  # (a hole of this step: placed below, once the edges have placed the others)
            try:
                edges, _ = K.find_edges(st.body, [ref["edge"]])
            except K.KernelError:
                s["warnings"].append(f"Hole {i + 1}: its edge is gone — it stays where it was.")
                continue
            centre = K.edge_centre(edges[0])
            if centre is not None:  # measured from another hole (a round edge): from its centre
                c = _uv(fr, centre)[k]
                v = c + float(ref.get("d", 0))
                if abs(v - p[k]) > 1e-9:
                    p[k] = round(v, 9)
                    changed = True
                continue
            a, b = (_uv(fr, q) for q in K.edge_ends(edges[0]))
            if abs(a[k] - b[k]) > 1e-6 * (1 + abs(a[k])):
                s["warnings"].append(f"Hole {i + 1}: its edge is not straight across any more — it stays where it was.")
                continue
            v = (a[k] + b[k]) / 2 + float(ref.get("d", 0))
            if abs(v - p[k]) > 1e-9:
                p[k] = round(v, 9)
                changed = True
    # measured from another hole of this step ({hole: j, d}): after that one is placed (chains settle in a few rounds)
    for _ in range(len(pts)):
        moved = False
        for i, p in enumerate(pts):
            spec = froms[i] if i < len(froms) and isinstance(froms[i], dict) else {}
            for axis, k in (("x", 0), ("y", 1)):
                ref = spec.get(axis)
                j = ref.get("hole") if isinstance(ref, dict) else None
                if not isinstance(j, int) or j == i or not 0 <= j < len(pts):
                    continue
                v = pts[j][k] + float(ref.get("d", 0))
                if abs(v - p[k]) > 1e-9:
                    p[k] = round(v, 9)
                    moved = changed = True
        if not moved:
            break
    if changed:
        s["update"] = {"points": pts}
    return pts


def _sized(make, v, what, unit, impossible):
    """make(v) -> a body; when it fails, say why: no size works at all, or this one is too big (and the most that
    works, found by trying)."""
    try:
        return make(v)
    except K.KernelError:
        pass

    def ok(x):
        try:
            make(x)
            return True
        except K.KernelError:
            return False
        except Exception:  # noqa: BLE001
            return False
    small = min(v, 0.05)
    if not ok(small):
        raise K.KernelError(impossible) from None
    lo, hi = small, v
    for _ in range(18):
        mid = (lo + hi) / 2
        if ok(mid):
            lo = mid
        else:
            hi = mid
    raise K.KernelError(f"The {what} {v:g} {unit} does not fit here — at most {math.floor(lo * 100) / 100:g} {unit}.") from None


def _cut_check(s, st, before):
    """A cut that took nothing away says so (it goes away from the part, or misses it)."""
    if before is not None and st.body is not None and abs(K.volume(st.body.shape) - before) < 1e-6 * (1 + before):
        s["warnings"].append("The cut removes nothing — it goes away from the part (⇅ flip its direction) or misses it.")


def _use(st, fid, tool, op):
    st.body = K.combine(st.body, tool, op)
    st.tools.setdefault(fid, []).append((tool, op))


MAX_COPIES = 200


_shapes: OrderedDict = OrderedDict()  # an imported file read once (a big STEP takes seconds)


def _solid_shape(f):
    import base64
    from . import blobs
    if f.get("blob"):
        sha = f["blob"]
        if sha not in _shapes:
            try:
                data = blobs.get(sha)
            except blobs.Missing:
                raise K.KernelError(f"BLOB_MISSING {sha} — the file of this step is not here; open the project file again.") from None
            _shapes[sha] = K.read_step_colours(data)
            while len(_shapes) > 8:
                _shapes.popitem(last=False)
        _shapes.move_to_end(sha)
        return _shapes[sha]
    try:
        return K.from_step(base64.b64decode(f.get("step") or "")), {}
    except (ValueError, TypeError):
        raise K.KernelError("The solid's data is damaged.") from None


MESH_LIMIT = 60000  # triangles: a bigger STL / OBJ takes too long to become a solid


def import_solid(a):
    """A STEP / STL / OBJ file (kept as a blob) -> a solid for a `solid` step: {blob, faces, bbox, volume, triangles?}.
    A STEP is used as it is; a mesh is made a solid (its triangles sewn) and kept as a STEP."""
    from . import blobs
    from .. import importers
    sha, name = a["blob"], a.get("name") or "part"
    data = blobs.get(sha)
    ext = name.lower().rsplit(".", 1)[-1]
    if ext in ("step", "stp"):
        shape, cols = K.read_step_colours(data)
        _shapes[sha] = (shape, cols)
        out = {"blob": sha, "coloured": len(cols)}
    elif ext in ("stl", "obj"):
        tris = importers.read_stl(data) if ext == "stl" else importers.read_obj(data.decode("utf-8", "ignore"))
        if len(tris) > MESH_LIMIT:
            raise K.KernelError(f"MESH_TOO_BIG This mesh has {len(tris)} triangles — more than {MESH_LIMIT} take too long to become an exact solid.")
        shape = K.mesh_solid(tris)
        out = {"blob": blobs.put(K.to_step(shape, name)), "triangles": len(tris)}
        _shapes[out["blob"]] = (shape, {})
    else:
        raise K.KernelError("A solid comes from a STEP, STL or OBJ file.")
    if K.face_count(shape) == 0:
        raise K.KernelError("The file has no solid in it.")
    bb = K.bbox(shape)
    return {**out, "faces": K.face_count(shape), "bbox": [round(v, 3) for v in bb] if bb else None, "volume": round(K.volume(shape), 3)}


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


# ------------------------------------------------------------------ the sizes a step can take
LIMIT_FIELDS = {"extrude": ("d", "offset"), "revolve": ("angle",), "fillet": ("r",), "chamfer": ("d",), "hole": ("d", "depth"),
                "shell": ("t",), "pattern": ("count", "spacing"), "decal": ("h", "depth")}
_limit_cache: OrderedDict = OrderedDict()


def limits(features, fid):
    """The range each number of step `fid` can take with the steps before it as they are: {field: [min, max]}.
    Found by building the step at trial values (it fails, or — a pattern — changes nothing, outside the range).
    A field with no limit up to a generous size gets that size as its max."""
    i = next((k for k, f in enumerate(features) if f.get("id") == fid), None)
    if i is None:
        raise K.KernelError("No such step.")
    f = features[i]
    key = _key(features[: i + 1])
    if key in _limit_cache:
        return _limit_cache[key]
    st0, _ = evaluate(features[:i])
    if f.get("type") == "revolve":
        f = {**f, "_sketch": next((g for g in features if g.get("id") == f.get("sketch")), None)}
    bb = K.bbox(st0.body.shape) if st0.body is not None else None
    size = max((bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2])) if bb else 100.0
    base_vol = K.volume(st0.body.shape) if st0.body is not None else 0.0

    def works(field, v):
        st, s = st0.copy(), {"warnings": [], "issues": []}
        try:
            _apply({**f, field: v}, st, s)
        except Exception:  # noqa: BLE001 — any failure: this value does not work
            return False
        if st.body is None:
            return False
        if f.get("type") == "pattern" and abs(K.volume(st.body.shape) - base_vol) < 1e-9:
            return False
        if any("changed nothing" in w for w in s["warnings"]):
            return False
        return True

    out = {}
    if f.get("type") == "pattern":  # from where the copies still overlap the part (building 200 copies to find out is slow)
        out = _pattern_limits(f, st0)
        _limit_cache[key] = out
        return out
    for field in LIMIT_FIELDS.get(f.get("type"), ()):
        if field not in f or not isinstance(f.get(field), (int, float)) or isinstance(f.get(field), bool):
            continue
        if field == "depth" and f.get("type") == "hole" and f.get("through", True):
            continue
        integer = field == "count"
        lo_cap = 2 if integer else (-size * 2 if field == "offset" else 0.01)
        hi_cap = 360 if field == "angle" else 200 if integer else max(10.0, size * 4)
        v0 = f[field]
        good = v0 if works(field, v0) else None
        if good is None:  # look for any value that works, from small up
            for v in ([lo_cap + k for k in range(0, 40)] if integer else [lo_cap + (hi_cap - lo_cap) * q for q in (0.001, 0.01, 0.05, 0.1, 0.25, 0.5)]):
                if works(field, v):
                    good = v
                    break
        if good is None:
            continue

        def edge(bad, ok):  # the last value that works between ok (works) and bad (does not)
            for _ in range(16 if not integer else 12):
                if integer and abs(bad - ok) <= 1:
                    break
                mid = (ok + bad) // 2 if integer else (ok + bad) / 2
                if works(field, mid):
                    ok = mid
                else:
                    bad = mid
            return ok

        hi = hi_cap if works(field, hi_cap) else edge(hi_cap, good)
        lo = lo_cap if works(field, lo_cap) else edge(lo_cap, good)
        if integer:
            out[field] = [int(lo), int(hi)]
        else:
            out[field] = [round(math.ceil(lo * 100) / 100, 2), round(math.floor(hi * 100) / 100, 2)]
    _cap_by_thickness(f, st0, out)
    _limit_cache[key] = out
    while len(_limit_cache) > CACHE_SIZE:
        _limit_cache.popitem(last=False)
    return out


def _cap_by_thickness(f, st0, out):
    """A blind hole or a cut goes at most through the part (deeper is the same as through); a hole at most as wide
    as the part across its face."""
    if st0.body is None:
        return
    if f.get("type") == "hole" and (f.get("plane") or {}).get("frame"):
        fr = plane_frame(f["plane"], st0)
    elif f.get("type") == "extrude" and f.get("op") == "cut" and not f.get("upto") and st0.sketches.get(f.get("sketch")):
        fr = st0.sketches[f["sketch"]][0]
    else:
        return
    o, n = np.asarray(fr["o"], float), np.asarray(fr["n"], float)
    bb = K.bbox(st0.body.shape)
    corners = [np.array([x, y, z]) for x in (bb[0], bb[3]) for y in (bb[1], bb[4]) for z in (bb[2], bb[5])]
    sign = -1 if f.get("type") == "hole" or not f.get("flip") else 1
    thick = max(((c - o) @ n) * sign for c in corners)
    for k in ("depth", "d") if f.get("type") == "extrude" else ("depth",):
        if k in out and thick > 0:
            out[k][1] = round(min(out[k][1], math.ceil(thick * 100) / 100), 2)
    if f.get("type") == "hole" and "d" in out:
        x = np.asarray(fr["x"], float)
        y = K.frame_y(fr)
        across = min(max(c @ x for c in corners) - min(c @ x for c in corners), max(c @ y for c in corners) - min(c @ y for c in corners))
        out["d"][1] = round(min(out["d"][1], math.floor(across * 100) / 100), 2)


def _pattern_limits(f, st0):
    """A row: how many copies (at this spacing) and how far apart (with this count) they still reach the part."""
    if f.get("kind") == "circular":
        return {"count": [2, 72]}
    tools = [t for x in f.get("features") or [] for t, _ in st0.tools.get(x, [])]
    if not tools or st0.body is None:
        return {}
    d = np.asarray(f.get("dir") or [1, 0, 0], float)
    d = d / (np.linalg.norm(d) or 1)
    corners = lambda bb: [np.array([x, y, z]) for x in (bb[0], bb[3]) for y in (bb[1], bb[4]) for z in (bb[2], bb[5])]  # noqa: E731
    tb = [c @ d for t in tools for c in corners(K.bbox(t.shape))]
    pb = [c @ d for c in corners(K.bbox(st0.body.shape))]
    reach = max(pb) - min(tb)  # how far along the row a copy can still start and touch the part
    spacing, count = float(f.get("spacing") or 10), int(f.get("count") or 2)
    out = {}
    if spacing > 0:
        out["count"] = [2, max(2, min(200, int(math.floor(reach / spacing + 1e-9)) + 1))]
    if count > 1:
        out["spacing"] = [0.01, round(math.floor(reach / (count - 1) * 100) / 100, 2)]
    return out


_tess: list = []  # [(body, mesh)]: a body that did not change (a sketch was added) is not meshed again


def _tessellated(body):
    for b, mesh in _tess:
        if b is body:
            return dict(mesh)
    mesh = K.tessellate(body)
    _tess.insert(0, (body, mesh))
    del _tess[6:]
    return dict(mesh)


def _with_colours(mesh, colours):
    """The faces that came from a coloured STEP file get their colour ("color")."""
    if not colours:
        return mesh
    faces = []
    for f in mesh["faces"]:
        c = next((colours[n] for n in [f.get("name"), *(f.get("names") or [])][::-1] if n in colours), None)
        faces.append({**f, "color": c} if c else f)
    return {**mesh, "faces": faces}


def rebuild(part):
    """The part -> what the browser shows: the body's mesh, faces (with names) and edges, every feature's
    status, the sketch frames."""
    features = (part or {}).get("features") or []
    st, status = evaluate(features)
    out = {"ok": all(s["ok"] for s in status), "features": status, "frames": st.frames, "body": None}
    if st.body is not None:
        out["body"] = _with_colours(_tessellated(st.body), st.colours)
    # reference solids: shown see-through, not part of the part
    out["refs"] = [{"id": fid, **_tessellated(b)} for fid, b in st.refs.items()]
    return out


def body_of(part):
    st, _ = evaluate((part or {}).get("features") or [])
    if st.body is None:
        raise K.KernelError("The model has no solid yet — sketch a shape and extrude it.")
    return st


def export(part, fmt, name="part"):
    st = body_of(part)
    if fmt == "pdf":  # a 2D drawing: three views, sizes, title block
        from . import drawing
        mats = {"PLA": 1.24, "PETG": 1.27, "ABS": 1.04, "ASA": 1.07, "TPU": 1.21, "PA": 1.14, "POM": 1.41,  # g / cm³, as in the browser
                "aluminium": 2.70, "steel": 7.85, "stainless steel": 7.93, "brass": 8.5}
        mat = (part or {}).get("material") or "PLA"
        fits = {f["d"]: f["fit"] for f in (part or {}).get("features") or [] if f.get("type") == "hole" and f.get("fit") and not f.get("off")}
        return drawing.pdf(st.body, name=name, material=mat, mass_g=K.volume(st.body.shape) / 1000 * mats.get(mat, 1.24), fits=fits,
                           tolerance=(part or {}).get("tolerance"))
    if fmt == "step":
        return K.to_step(st.body.shape)
    if fmt == "stl":
        return K.to_stl(K.tessellate(st.body))
    raise K.KernelError(f"Unknown export format “{fmt}”.")


def assembly_clashes(instances):
    """Where the placed parts of an assembly overlap: instances [{id, part: {features}, matrix: [16]}] ->
    [{a, b (their ids), volume, bbox}]. A part without a solid is left out."""
    shapes = []
    for inst in instances or []:
        try:
            st = body_of(inst.get("part"))
        except K.KernelError:
            continue
        shapes.append((inst.get("id"), K.placed(st.body.shape, inst.get("matrix") or [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1])))
    return K.interference(shapes)


def assembly_sweep(instances, steps):
    """Collisions along a motion: instances as for assembly_clashes (where they are at the start), steps [{at,
    matrices: {id: [16]}}] (the parts that moved, where they are at that step) -> [{at, clashes}] — only the
    clashes of a part that moved. Each solid is built once."""
    base = {}
    for inst in instances or []:
        try:
            base[inst.get("id")] = body_of(inst.get("part")).body.shape
        except K.KernelError:
            continue
    start = {inst.get("id"): inst.get("matrix") or [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1] for inst in instances or []}
    still = {k: K.placed(s, start[k]) for k, s in base.items()}
    out = []
    for step in steps or []:
        moved = {k: m for k, m in (step.get("matrices") or {}).items() if k in base}
        shapes = [(k, K.placed(base[k], moved[k]) if k in moved else s) for k, s in still.items()]
        out.append({"at": step.get("at"), "clashes": K.interference(shapes, only=set(moved))})
    return out


def assembly_step(instances):
    """An assembly -> one STEP file with every placed part: instances [{part: {features}, matrix: [16]}]."""
    shapes = []
    for inst in instances or []:
        st = body_of(inst.get("part"))
        shapes.append(K.placed(st.body.shape, inst.get("matrix") or [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]))
    if not shapes:
        raise K.KernelError("The assembly is empty — insert parts first.")
    return K.to_step(K.compound(shapes))
