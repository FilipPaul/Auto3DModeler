"""A 3D model part: an ordered list of features (sketch, extrude, fillet, chamfer, hole) evaluated into one
solid body with named faces (see kernel.py).

Part JSON (in the project file, `parts[].model`):
  {"features": [
     {"id": "F1", "type": "sketch", "name": "Sketch 1", "plane": {"datum": "XY"}, "points": {...}, "entities": [...]},
     {"id": "F2", "type": "extrude", "sketch": "F1", "op": "add" | "cut", "d": 10, "symmetric": false, "flip": false, "through": false},
      (or "upto": {name, fp} + "offset": up to a face; "upto_next": true: up to the next face its whole sketch meets;
      "d2": 5 = also 5 mm to the other side of the sketch)
     {"id": "F3", "type": "sketch", "plane": {"face": {"name": "F2:end"}, "frame": {"o", "x", "n"}}, ...},
     {"id": "F4", "type": "fillet", "edges": [{"a": "F2:end", "b": "F2:side:l1", "fp": [x, y, z]}], "r": 2},
     {"id": "F5", "type": "chamfer", "edges": [...], "d": 1},
     {"id": "F7", "type": "revolve", "sketch": "F1", "axis": "y" | "x" | <a line of the sketch>, "angle": 360, "op": "add"},
     {"id": "F8", "type": "shell", "faces": [{"name": "F2:end", "fp": [x, y, z]}], "t": 2},
     {"id": "F9", "type": "mirror", "of": "body" | <a step's id>, "plane": {"datum": "YZ"} | {"face": ..., "frame": ...},
      "copy": true},   (copy: the part and its mirror image; false: the part moved to its mirror image)
     {"id": "F11", "type": "split", "plane": {"datum": "XY", "offset": 5} | {"face": ..., "frame": ..., "mid"?, "offset"?},
      "keep": "both" | "above" | "below"},   (both: two bodies; above: the side the plane's normal points to)
     {"id": "F6", "type": "hole", "plane": {"face": {"name": "F2:end"}, "frame": ...}, "points": [[u, v]], "d": 5,
      "through": true, "depth": 10},   (+ "teardrop": true: a sideways hole with a 45° point on top, printable)
     {"id": "F10", "type": "point", "at": {"vertex": {"faces": [...], "fp": [x, y, z]}} | {"centre": <edge ref>} |
      {"mid": <edge ref>} | {"xyz": [x, y, z]}}]}   (a reference point: a corner, a round edge's centre, an edge's middle)

A sketch or a hole on a face stores the face's frame and its name: when the face moves (the extrude gets
longer), the sketch moves with it. Its 0, 0 is the face's centre (when it was picked), or plane.origin: "corner" (the
face's lower-left corner in its u / v, following it), "world" (the part's origin) or {point: <a point step>}.
An edge is stored as the two faces it joins (+ where it was).
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
FEATURE_TYPES = ("sketch", "extrude", "revolve", "fillet", "chamfer", "hole", "shell", "pattern", "solid", "loft", "sweep", "decal", "mirror", "draft", "rib", "point", "split")

_cache: OrderedDict = OrderedDict()  # prefix hash -> state after that feature (only in the worker process)
CACHE_SIZE = 48


def _key(features):
    return hashlib.sha1(json.dumps(features, sort_keys=True).encode()).hexdigest()


# ISO metric coarse threads: the tap drill a threaded hole is drilled with (ISO 2306)
THREADS = {"M2": 1.6, "M2.5": 2.05, "M3": 2.5, "M4": 3.3, "M5": 4.2, "M6": 5.0, "M8": 6.8, "M10": 8.5, "M12": 10.2,
           "M16": 14.0, "M20": 17.5}


def _threads(part):
    """{tap drill Ø: "M5"} of the part's threaded holes (the drawing labels them M5, not Ø4.2)."""
    return {THREADS[f["thread"]]: f["thread"] for f in (part or {}).get("features") or []
            if f.get("type") == "hole" and f.get("thread") in THREADS and not (f.get("off") or f.get("suppressed"))}


def _head_sizes(f, dia):
    """A hole head's Ø and depth (a counterbore: 1.8 × d, d deep; a countersink: 2 × d, its depth from the angle)."""
    if f.get("head") == "cbore":
        return _num(f, "head_d", round(dia * 1.8, 1), what="counterbore diameter"), _num(f, "head_depth", round(dia, 1), what="counterbore depth")
    return _num(f, "head_d", round(dia * 2, 1), what="countersink diameter"), None


def _holes(part):
    """{step id: {d, thread, through, depth, head, head_d, head_depth, head_angle, fit, teardrop}} of the part's hole
    steps — what the drawing's hole callout says ("4× M3 ⌵ Ø5 × 90°", sheet.callout)."""
    out = {}
    for f in (part or {}).get("features") or []:
        if f.get("type") != "hole" or f.get("off") or f.get("suppressed"):
            continue
        try:
            dia = THREADS[f["thread"]] if f.get("thread") in THREADS else _num(f, "d", 5)
            h = {"d": dia, "through": bool(f.get("through", True)), "teardrop": bool(f.get("teardrop"))}
            if not h["through"]:
                h["depth"] = _num(f, "depth", 10)
            if f.get("thread") in THREADS:
                h["thread"] = f["thread"]
            if f.get("fit"):
                h["fit"] = f["fit"]
            if f.get("head") in ("cbore", "csk"):
                h["head"] = f["head"]
                h["head_d"], hdep = _head_sizes(f, dia)
                if f["head"] == "cbore":
                    h["head_depth"] = hdep
                else:
                    h["head_angle"] = float(f.get("head_angle") or 90)
        except K.KernelError:
            continue  # (a step that did not build: no callout)
        out[f["id"]] = h
    return out


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
        self.points = {}    # id -> [x, y, z]: reference points (point steps), where they are now

    def copy(self):
        s = State()
        s.body, s.sketches, s.frames, s.tools = self.body, dict(self.sketches), dict(self.frames), dict(self.tools)
        s.sketch_src, s.refs, s.colours, s.points = dict(self.sketch_src), dict(self.refs), dict(self.colours), dict(self.points)
        return s


def _face_name(plane):
    ref = (plane or {}).get("face") or {}
    if ref.get("name"):
        return ref["name"]
    if ref.get("feature"):  # first-version files: {feature, role}
        return f"{ref['feature']}:{ref.get('role', 'end')}"
    return None


def _plane_offset(name, n0, o0, st: State):
    """How far along n0 from o0 the flat face `name` (square to n0) lies now; None when it is not there."""
    if not name or st.body is None:
        return None
    for face in st.body.faces_of(name):
        pl = K.plane_of(face)
        if pl is not None and abs(abs(pl[1] @ n0) - 1) <= 1e-6:
            return float((pl[0] - o0) @ n0)
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
    fr = {k: [float(x) for x in fr[k]] for k in ("o", "x", "n")}
    name = _face_name(plane)
    if plane.get("mid"):  # midway between two parallel faces: wherever both are now
        n0, o0 = np.asarray(fr["n"], float), np.asarray(fr["o"], float)
        offs = [_plane_offset(nm, n0, o0, st) for nm in (name, _face_name({"face": plane["mid"]}))]
        if None not in offs:
            fr["o"] = [round(float(x), 9) for x in o0 + (sum(offs) / 2) * n0]
        return _origin(plane, fr, name, st)
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
    return _origin(plane, fr, name, st)


def _origin(plane, fr, name, st: State):
    """The sketch's (or holes') 0, 0 on a face: plane.origin "corner" = the face's corner with the smallest u and v
    (its box in its own u / v — found again each rebuild, so it follows that corner), "world" = the part's origin seen
    square onto the plane (fixed), {point: <id>} = a • reference point seen square onto it; none = where the frame says
    (the face's centre when it was picked). The answer carries `origin` (the browser tells its frames apart by it)."""
    how = plane.get("origin")
    if not how or how == "centre":
        return fr
    o, x, n = (np.asarray(fr[k], float) for k in ("o", "x", "n"))
    if how == "world":
        p = np.zeros(3)
    elif how == "corner":
        faces = [f for f in (st.body.faces_of(name) if name and st.body is not None else [])
                 if (pl := K.plane_of(f)) is not None and abs(abs(pl[1] @ n) - 1) <= 1e-6]
        span = K.face_span(faces, fr) if faces else None
        if span is None:
            raise K.KernelError("The face whose corner is the sketch's origin is gone — choose another origin.")
        p = o + span[0] * x + span[2] * K.frame_y(fr)
    elif isinstance(how, dict) and how.get("point"):
        if how["point"] not in st.points:
            raise K.KernelError(f"The origin's reference point {how['point']} is not there (it has to come before this step).")
        p = np.asarray(st.points[how["point"]], float)
    else:
        raise K.KernelError("origin: \"centre\", \"corner\", \"world\" or {point: <a point step>}.")
    fr["o"] = [round(float(v), 9) for v in p + ((o - p) @ n) * n]  # (in the plane: only along it)
    fr["origin"] = how
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
        sign = (-1 if op == "cut" else 1) * (-1 if f.get("flip") else 1)
        nxt = f.get("upto_next") and not through
        if nxt:
            vec, start = n * sign, None  # (only its direction: it goes as far as the next face)
        elif f.get("upto") and not through:
            vec, start = _up_to_face(f, fr, st), None
        else:
            d = _through_depth(st) if through else _num(f, "d", 10)
            vec = n * d * sign
            start = -vec / 2 if f.get("symmetric") else None
        # ＋ Other side: d2 more on the other side of the sketch plane (not with symmetric)
        d2 = _num(f, "d2", what="other side's distance") if f.get("d2") and not f.get("symmetric") else 0
        if not faces:
            raise K.KernelError("Its sketch has no closed shape to extrude.")
        before = K.volume(st.body.shape) if op == "cut" and st.body is not None else None
        body0 = st.body
        for face, names in faces:
            _use(st, fid, K.prism_up_to_next(face, names, vec, body0, fid, op) if nxt else K.prism_body(face, names, vec, fid, start), op)
        main = [t for t, _ in st.tools.get(fid, [])]
        if d2:
            back = -vec / float(np.linalg.norm(vec)) * d2
            for face, names in faces:
                b = K.prism_body(face, names, back, fid)
                b.names[f"{fid}:start"] = b.names.pop(f"{fid}:end")  # (its far face starts the extrude; the one on the plane is inside)
                _use(st, fid, b, op)
        _cut_check(s, st, before)
        s["went"] = _went(vec, main)
        if d2 and s["went"]:
            other = _went(-vec, [t for t, _ in st.tools.get(fid, [])][len(main):])
            if other and other.get("range"):
                s["went"]["other_side"] = other["range"]
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
    if t == "rib":  # a gusset: an open line of a sketch filled up to the part, t thick about its plane
        src = st.sketch_src.get(f.get("sketch"))
        if src is None or f.get("sketch") not in st.frames:
            raise K.KernelError("Choose the rib's sketch: a line from the part to the part (e.g. wall to plate).")
        chain, ids = K.open_chain(src)
        _use(st, fid, K.rib(st.body, st.frames[f["sketch"]], chain, ids, _num(f, "t", 3, what="thickness"), fid), "add")
        return
    if t == "draft":  # the side walls of an extrude tilted (moulding, casting)
        if st.body is None:
            raise K.KernelError("There is no solid yet to draft.")
        body = st.body
        st.body = _sized(lambda v: K.draft(body, f.get("of"), v, fid), _num(f, "angle", 3, what="draft angle"), "angle", "°",
                         "The walls could not be tilted by that angle here — try a smaller angle, or draft before rounding the edges.")
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
        if f.get("thread") and f["thread"] not in THREADS:
            raise K.KernelError(f"Unknown thread “{f['thread']}” — one of {', '.join(THREADS)}.")
        dia = THREADS[f["thread"]] if f.get("thread") else _num(f, "d", 5, what="diameter")  # (a thread: its tap drill)
        depth = _through_depth(st) if f.get("through", True) else _num(f, "depth", 10, what="depth")
        n = np.asarray(fr["n"], float)
        head = f.get("head")  # ⌴ a counterbore (a screw head sunk in) / ⌵ a countersink (a flat head flush)
        if head == "cbore":
            hd, hdep = _head_sizes(f, dia)
            if hd <= dia:
                raise K.KernelError("The counterbore has to be wider than the hole.")
            if not f.get("through", True) and hdep >= depth:
                raise K.KernelError("The counterbore has to be less deep than the hole.")
        elif head == "csk":
            hd, _ = _head_sizes(f, dia)
        tear = bool(f.get("teardrop"))  # ▲ printed sideways: the top of the round becomes a 45° point (a counterbore too)
        if tear and head == "csk":
            raise K.KernelError("A countersink cannot be a teardrop (its cone would hang over) — use a counterbore, or untick Teardrop.")
        prof = K.teardrop_face if tear else K.circle_face
        for k, (u, v) in enumerate(pts):
            face, names = prof(fr, float(u), float(v), dia)
            tool = K.prism_body(face, names, -n * depth, fid)
            tool.names = {f"{fid}:hole:{k}": tool.names.get(f"{fid}:side:c", []), f"{fid}:bottom:{k}": tool.names.get(f"{fid}:end", []),
                          **({f"{fid}:tear:{k}": tool.names.get(f"{fid}:side:t", [])} if tear else {})}
            _use(st, fid, tool, "cut")
            if head == "cbore":
                face, names = prof(fr, float(u), float(v), hd)
                tool = K.prism_body(face, names, -n * hdep, fid)
                tool.names = {f"{fid}:cbore:{k}": tool.names.get(f"{fid}:side:c", []), f"{fid}:cbore_floor:{k}": tool.names.get(f"{fid}:end", []),
                              **({f"{fid}:cbore_tear:{k}": tool.names.get(f"{fid}:side:t", [])} if tear else {})}
                _use(st, fid, tool, "cut")
            elif head == "csk":
                _use(st, fid, K.countersink(fr, float(u), float(v), hd, dia, float(f.get("head_angle") or 90), f"{fid}:csk:{k}"), "cut")
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
    if t == "split":  # ✂ the part cut in two along a plane: both pieces kept (two bodies), or one side
        if st.body is None:
            raise K.KernelError("There is no solid yet to split.")
        plane = f.get("plane") or {"datum": "XY"}
        fr = plane_frame(plane, st)
        if "datum" not in plane and plane.get("offset"):  # a face's plane moved along its normal
            fr["o"] = [o + float(plane["offset"]) * n for o, n in zip(fr["o"], fr["n"])]
        st.frames[fid] = fr
        st.body = K.split(st.body, fr["o"], fr["n"], fid, f.get("keep") or "both")
        s["bodies"] = K.solids(st.body.shape)
        return
    if t == "pattern":
        before = K.volume(st.body.shape) if st.body is not None else 0
        _pattern(f, st)
        if st.body is not None and abs(K.volume(st.body.shape) - before) < 1e-6 * (1 + before):
            s["warnings"].append("The copies changed nothing — they may land outside the part or on top of each other. Check the direction and the spacing.")
        return
    if t == "point":
        _point(f, st, s)
        return
    raise K.KernelError(f"Unknown feature type “{t}”.")


def _point(f, st, s):
    """A reference point (no geometry): a corner {vertex: {faces, fp}}, the centre of a round edge {centre: {a, b, fp}},
    an edge's middle {mid: {a, b, fp}} or a fixed place {xyz}. Found again each rebuild by the names of its faces, so it
    follows the part; the new place goes back to the browser (s["update"]: its fp). Gone: an issue, the last place kept."""
    fid, at = f["id"], f.get("at") or {}
    kind = next((k for k in ("vertex", "centre", "mid", "xyz") if at.get(k)), None)
    if kind is None:
        raise K.KernelError("A point needs a place: a corner, the centre of a round edge or an edge's middle.")
    last = at["xyz"] if kind == "xyz" else at[kind].get("fp")
    if last is not None:
        st.points[fid] = s["point"] = [float(v) for v in last]  # (also when it is not found below: its last place)
    if kind == "xyz":
        return
    gone = {"vertex": "Its corner of the part is gone", "centre": "Its round edge is gone", "mid": "Its edge is gone"}[kind]
    gone += " — it stays where it was. Delete it, or make it again on the part as it is now."
    if st.body is None:
        raise K.KernelError(gone)
    bb = K.bbox(st.body.shape) or [0, 0, 0, 1, 1, 1]
    size = max(bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2], 1e-6)
    if kind == "vertex":
        p, guessed = K.find_vertex(st.body, at["vertex"].get("faces"), last)
        if guessed and (last is None or np.linalg.norm(p - np.asarray(last, float)) > size * 0.05):
            raise K.KernelError(gone)
    else:
        try:
            edges, guessed = K.find_edges(st.body, [at[kind]])
        except K.KernelError:
            raise K.KernelError(gone) from None
        p = K.edge_centre(edges[0]) if kind == "centre" else K._edge_mid(edges[0])
        if p is None:
            raise K.KernelError("Its edge is not round any more — it has no centre. Delete the point or make it again.")
    if guessed:
        s["warnings"].append("Its place on the part was found again by the position only — check that it is the right one.")
    p = [round(float(v), 6) for v in p]
    st.points[fid] = p
    s["point"] = p
    if last is None or any(abs(a - b) > 1e-7 for a, b in zip(p, last)):
        s["update"] = {"at": {kind: {**at[kind], "fp": p}}}


def _uv(fr, p):
    o, x, y = np.asarray(fr["o"], float), np.asarray(fr["x"], float), K.frame_y(fr)
    d = np.asarray(p, float) - o
    return [round(float(d @ x), 9), round(float(d @ y), 9)]


def _axis_of(ref, st):
    """{face, fp} (or just a face's name) -> the axis (a point, its direction) of that round face as it is now."""
    ref = {"face": ref} if isinstance(ref, str) else ref or {}
    if st.body is None:
        raise K.KernelError("Its round face is gone.")
    face = K.find_faces(st.body, [{"name": ref.get("face"), "fp": ref.get("fp")}])[0]
    ax = K.face_axis(face)
    if ax is None:
        raise K.KernelError("Its face is not round any more — it has no axis.")
    return ax


def _axis_in(fr, ax):
    """An axis seen square onto a sketch plane -> ([u, v] of a point of it, its unit direction [du, dv]) — None for the
    direction when the axis is square to the plane (it is a point there)."""
    c = np.asarray(_uv(fr, ax[0]), float)
    d = np.array([float(ax[1] @ np.asarray(fr["x"], float)), float(ax[1] @ K.frame_y(fr))])
    L = float(np.linalg.norm(d))
    return c, (d / L if L > 1e-6 else None)


def _ref_uv(end, fr, st):
    """A dimension end that points at the part -> where that point is now, in sketch coordinates (or None).
    {ref: [u, v], vertex: {faces, fp}} = a corner, {ref, edge: {a, b, fp}} = a straight edge (its middle),
    {ref, point: <id>} = a reference point (a point step; seen square onto the sketch), {ref, axis: {face, fp}} = the
    axis of a round face (a shaft, a hole): square to the sketch a point, else a line — the point of it nearest ref."""
    if isinstance(end, dict) and end.get("axis") and st.body is not None:
        c, along = _axis_in(fr, _axis_of(end["axis"], st))
        if along is None:
            return [round(float(v), 9) for v in c], False
        r = np.asarray(end.get("ref") or c, float) - c
        t = float(r @ along)
        return [round(float(c[0] + t * along[0]), 9), round(float(c[1] + t * along[1]), 9)], False
    if isinstance(end, dict) and end.get("point"):
        if end["point"] not in st.points:
            raise K.KernelError("Its reference point is gone.")
        return _uv(fr, st.points[end["point"]]), False
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
                s["warnings"].append("A dimension's round face of the part is gone — its distance is kept from where its axis was."
                                     if isinstance(d.get(k), dict) and d[k].get("axis") else
                                     "A dimension's edge of the part is gone — its distance is kept from where the edge was.")
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
    along the face's x + d (the edge runs along y), likewise y; {axis: {face, fp}, d}: from a round face's axis; {mid: [edge a,
    edge b], d}: midway between two parallel straight edges (the middle line of a block: it stays in the middle when the
    part gets wider). The edges are found again by their faces' names,
    so the holes keep their distance when the part changes. Without an edge: the stored [u, v] (from the centre)."""
    pts = [list(map(float, p)) for p in f.get("points") or []]
    froms = f.get("from") or []
    changed = False
    for i, p in enumerate(pts):
        spec = froms[i] if i < len(froms) and isinstance(froms[i], dict) else {}
        for axis, k in (("x", 0), ("y", 1)):
            ref = spec.get(axis)
            if ref and ref.get("axis"):  # from a round face's axis (a shaft, a cross hole): square to the face or across
                try:
                    c, along = _axis_in(fr, _axis_of(ref["axis"], st))
                except K.KernelError:
                    s["warnings"].append(f"Hole {i + 1}: its round face is gone — it stays where it was.")
                    continue
                if along is not None and abs(along[k]) > 1e-6:
                    s["warnings"].append(f"Hole {i + 1}: its axis does not run straight across any more — it stays where it was.")
                    continue
                v = c[k] + float(ref.get("d", 0))
                if abs(v - p[k]) > 1e-9:
                    p[k] = round(v, 9)
                    changed = True
                continue
            if ref and isinstance(ref.get("mid"), list) and len(ref["mid"]) == 2:  # midway between two straight edges
                try:
                    cs = []
                    for e in ref["mid"]:
                        edges, _ = K.find_edges(st.body, [e])
                        a, b = (_uv(fr, q) for q in K.edge_ends(edges[0]))
                        if K.edge_centre(edges[0]) is not None or abs(a[k] - b[k]) > 1e-6 * (1 + abs(a[k])):
                            raise ValueError
                        cs.append((a[k] + b[k]) / 2)
                except K.KernelError:
                    s["warnings"].append(f"Hole {i + 1}: an edge it is midway between is gone — it stays where it was.")
                    continue
                except ValueError:
                    s["warnings"].append(f"Hole {i + 1}: an edge it is midway between is not straight across any more — it stays where it was.")
                    continue
                v = (cs[0] + cs[1]) / 2 + float(ref.get("d", 0))
                if abs(v - p[k]) > 1e-9:
                    p[k] = round(v, 9)
                    changed = True
                continue
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


def _went(vec, tools):
    """Where an extrude went, for the AI: {along: "+z" / "-y" … (or the direction), range: [from, to] along that
    axis (mm) of what it added / cut}."""
    v = np.asarray(vec, float)
    L = float(np.linalg.norm(v))
    if L < 1e-12:
        return None
    u = v / L
    k = int(np.argmax(np.abs(u)))
    out = {"along": f"{'+' if u[k] > 0 else '-'}{'xyz'[k]}" if abs(u[k]) > 0.9999 else [round(float(c), 4) for c in u]}
    bbs = [b for b in (K.bbox(t.shape) for t in tools) if b]
    if bbs and abs(u[k]) > 0.9999:
        out["range"] = [round(min(b[k] for b in bbs), 3), round(max(b[k + 3] for b in bbs), 3)]
    return out


def _cut_check(s, st, before):
    """A cut that took nothing away says so (it goes away from the part, or misses it)."""
    if before is not None and st.body is not None and abs(K.volume(st.body.shape) - before) < 1e-6 * (1 + before):
        s["warnings"].append("The cut removes nothing — it goes away from the part (⇅ flip its direction) or misses it.")


def _use(st, fid, tool, op):
    st.body = K.combine(st.body, tool, op)
    st.tools.setdefault(fid, []).append((tool, op))


MAX_COPIES = 200


_shapes: OrderedDict = OrderedDict()  # an imported file read once (a big STEP takes seconds)
SHAPES_FACES = 200000  # kept read: the last 8 files, or more while their faces add up to less (an assembly's parts)


def _keep(sha, shape, cols):
    _shapes[sha] = (shape, cols, K.face_count(shape))
    _shapes.move_to_end(sha)
    while len(_shapes) > 8 and sum(v[2] for v in _shapes.values()) > SHAPES_FACES:
        _shapes.popitem(last=False)


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
            _keep(sha, *K.read_step_colours(data))
        _shapes.move_to_end(sha)
        return _shapes[sha][:2]
    try:
        return K.from_step(base64.b64decode(f.get("step") or "")), {}
    except (ValueError, TypeError):
        raise K.KernelError("The solid's data is damaged.") from None


MESH_LIMIT = 60000  # triangles: a bigger STL / OBJ takes too long to become a solid


def import_solid(a):
    """A STEP / IGES / STL / OBJ file (kept as a blob) -> a solid for a `solid` step: {blob, faces, bbox, volume,
    triangles?, op?, warning?}. A STEP is used as it is; an IGES is kept as a STEP (its surfaces sewn into a solid when
    they close; else op "ref": a reference body, with a warning); a mesh is made a solid (its triangles sewn) and kept
    as a STEP."""
    from . import blobs
    from .. import importers
    sha, name = a["blob"], a.get("name") or "part"
    data = blobs.get(sha)
    ext = name.lower().rsplit(".", 1)[-1]
    if ext in ("step", "stp"):
        shape, cols, built = K.read_step_colours(data, summary=True)
        _keep(sha, shape, cols)
        out = {"blob": sha, "coloured": len(cols), "structure": built}
    elif ext in ("igs", "iges"):
        shape, cols, how = K.read_iges(data)
        out = {"blob": blobs.put(K.to_step_coloured(shape, cols, name) if cols else K.to_step(shape, name)), "iges": how}
        _keep(out["blob"], shape, cols)
        if how == "sewn":
            out["warning"] = "The IGES file held surfaces only — they were sewn into a closed solid."
        elif how == "surfaces":
            out["op"] = "ref"  # (not closed: it cannot be joined or cut — shown to build around)
            out["warning"] = ("The IGES file holds surfaces that do not close into a solid (a gap or a missing face) — "
                              "it came in as a reference body: shown see-through to build around, not part of the solid.")
    elif ext in ("stl", "obj"):
        tris = importers.read_stl(data) if ext == "stl" else importers.read_obj(data.decode("utf-8", "ignore"))
        if len(tris) > MESH_LIMIT:
            raise K.KernelError(f"MESH_TOO_BIG This mesh has {len(tris)} triangles — more than {MESH_LIMIT} take too long to become an exact solid.")
        shape = K.mesh_solid(tris)
        out = {"blob": blobs.put(K.to_step(shape, name)), "triangles": len(tris)}
        _keep(out["blob"], shape, {})
    else:
        raise K.KernelError("A solid comes from a STEP, IGES, STL or OBJ file.")
    if K.face_count(shape) == 0:
        raise K.KernelError("The file has no solid in it.")
    bb = K.bbox(shape)
    return {**out, "faces": K.face_count(shape), "bbox": [round(v, 3) for v in bb] if bb else None, "volume": round(K.volume(shape), 3)}


def import_assembly(a):
    """A STEP assembly (kept as a blob) -> its tree for the browser: {root, parts: {key: {name, blob, faces, bbox,
    volume, coloured}}, assemblies: {key: {name, instances: [{ref, matrix, name, colour?}]}}}. Each different part is
    kept as a STEP of its own (with its colours), used by a `solid` step as an imported file is."""
    from . import blobs
    try:
        tree = K.read_step_tree(blobs.get(a["blob"]))
    except blobs.Missing:
        raise K.KernelError("BLOB_MISSING — the file is not here any more; open it again.") from None
    parts = {}
    for k, p in tree["parts"].items():
        shape, faces = p["shape"], K.face_count(p["shape"])
        if not faces:
            continue
        bb = K.bbox(shape)
        sha = blobs.put(K.to_step_coloured(shape, p["colours"], p["name"]))
        _keep(sha, shape, p["colours"])  # (read back, the file gives the same faces in the same order)
        parts[k] = {"name": p["name"], "blob": sha, "faces": faces, "bbox": [round(v, 3) for v in bb] if bb else None,
                    "volume": round(K.volume(shape), 3), "coloured": len(p["colours"])}
    asms = {k: {"name": v["name"], "instances": [i for i in v["instances"] if i["ref"] in parts or i["ref"] in tree["assemblies"]]}
            for k, v in tree["assemblies"].items()}
    if not parts:
        raise K.KernelError("The file has no solid in it.")
    return {"root": tree["root"], "parts": parts, "assemblies": asms}


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
    used = {q for e in sk.get("entities") or [] if not e.get("construction") for k in ("a", "b", "c") if (q := e.get(k)) and q != "O"}
    for p in (v for k, v in pts.items() if k in used or not used):
        side = (np.asarray(p, float) - a2) @ nrm
        if abs(side) > 1e-7:
            sides.add(bool(side > 0))
    for e in sk.get("entities") or []:
        if e.get("t") == "circle" and "c" in e and not e.get("construction"):
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
LIMIT_FIELDS = {"extrude": ("d", "offset", "d2"), "revolve": ("angle",), "fillet": ("r",), "chamfer": ("d",), "hole": ("d", "depth"),
                "shell": ("t",), "pattern": ("count", "spacing"), "decal": ("h", "depth"), "draft": ("angle",), "rib": ("t",)}
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


_tess: list = []  # [((body, light), mesh)]: a body that did not change (a sketch was added) is not meshed again


def _tessellated(body, light=False):
    for (b, lt), mesh in _tess:
        if b is body and lt == light:
            return dict(mesh)
    mesh = K.tessellate(body, light)
    _tess.insert(0, ((body, light), mesh))
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


_packed: list = []  # [((body, light, colours, id), packed.Mesh)]: an unchanged body is not encoded again either


def _packed_mesh(body, light=False, colours=None, rid=None):
    """The body's mesh as packed.Mesh (its JSON made once, kept like the mesh); rid: a reference solid's id."""
    from . import packed
    colours = colours or {}
    for (b, lt, c, r), m in _packed:
        if b is body and lt == light and r == rid and c == colours:
            return m
    mesh = _with_colours(_tessellated(body, light), colours)
    m = packed.Mesh({"id": rid, **mesh} if rid is not None else mesh)
    _packed.insert(0, ((body, light, dict(colours), rid), m))
    del _packed[4:]  # (a big board's is 80 MB)
    return m


def rebuild(part, binary=False):
    """The part -> what the browser shows: the body's mesh, faces (with names) and edges, every feature's
    status, the sketch frames. binary: the meshes as packed.Mesh (for packed.pack, the browser's binary answer)."""
    features = (part or {}).get("features") or []
    st, status = evaluate(features)
    out = {"ok": all(s["ok"] for s in status), "features": status, "frames": st.frames, "body": None}
    if st.body is not None:
        # 🪶 lod: "light" (simplified), "full", "auto" (light when it is a big imported model)
        lod = (part or {}).get("lod")
        light = lod == "light" or (lod == "auto" and K.face_count(st.body.shape) > K.HEAVY_FACES)
        out["body"] = _packed_mesh(st.body, light, st.colours) if binary else _with_colours(_tessellated(st.body, light), st.colours)
    # reference solids: shown see-through, not part of the part
    out["refs"] = [_packed_mesh(b, rid=fid) if binary else {"id": fid, **_tessellated(b)} for fid, b in st.refs.items()]
    out["points"] = st.points  # reference points: id -> [x, y, z]
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
        from .materials import DENSITY as mats  # g / cm³, as in the browser
        mat = (part or {}).get("material") or "PLA"
        fits = {f["d"]: f["fit"] for f in (part or {}).get("features") or [] if f.get("type") == "hole" and f.get("fit") and not (f.get("off") or f.get("suppressed"))}
        return drawing.pdf(st.body, name=name, material=mat, mass_g=K.volume(st.body.shape) / 1000 * mats.get(mat, 1.24), fits=fits,
                           tolerance=(part or {}).get("tolerance"))
    if fmt == "step":
        return K.to_step(st.body.shape)
    if fmt == "iges":
        return K.to_iges(st.body.shape)
    if fmt == "stl":
        return K.to_stl(K.tessellate(st.body))
    if fmt == "obj":
        return K.to_obj(K.tessellate(st.body), name)
    if fmt == "glb":  # the part in its colour and material's finish (and an imported file's face colours)
        from .materials import finish_of, look_colour
        colours = [(face, c) for n, c in st.colours.items() for face in st.body.faces_of(n)]
        return K.write_gltf_tree({"p": {"name": name, "shape": st.body.shape, "colour": look_colour(part), "colours": colours,
                                        "finish": finish_of((part or {}).get("material"))}}, {}, "p")
    raise K.KernelError(f"Unknown export format “{fmt}”.")


def sheet(part, preset="medium", paper=None, per_view=None, section=False):
    """A drawing sheet of the part: its views, the points to dimension, the automatic dimensions of the preset, the
    layout (sheet.py)."""
    from . import sheet as S
    st = body_of(part)
    fits = {f["d"]: f["fit"] for f in (part or {}).get("features") or [] if f.get("type") == "hole" and f.get("fit") and not (f.get("off") or f.get("suppressed"))}
    return S.build(st.body, preset, fits, paper, per_view, _threads(part), section, key=_key((part or {}).get("features") or []), holes=_holes(part))


def _exploded(placed, k):
    """The placed parts pulled apart for an exploded view: each top-level part (a sub-assembly's parts together, ids
    "I2/I1") moved away from the middle of all by 1.2 × k × its distance (one right at the middle: up)."""
    groups = {}
    for key, s in placed:
        bb = K.bbox(s)
        if bb:
            g = groups.setdefault(str(key).split("/")[0], [np.inf] * 3 + [-np.inf] * 3)
            groups[str(key).split("/")[0]] = [*np.minimum(g[:3], bb[:3]), *np.maximum(g[3:], bb[3:])]
    if len(groups) < 2:
        return None
    centre = {g: (np.asarray(b[:3]) + np.asarray(b[3:])) / 2 for g, b in groups.items()}
    mid = np.mean(list(centre.values()), axis=0)
    size = max(float(np.linalg.norm(np.asarray(b[3:]) - np.asarray(b[:3]))) for b in groups.values())
    out = []
    for key, s in placed:
        c = centre.get(str(key).split("/")[0])
        if c is None:
            continue
        v = c - mid
        v = v * 1.2 * k if np.linalg.norm(v) > 1e-6 * (1 + size) else np.array([0, 0, max(size, 10) * 0.5 * k])
        out.append((key, K.placed(s, [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, float(v[0]), float(v[1]), float(v[2]), 1])))
    return out


def assembly_sheet(instances, paper=None, explode=0):
    """An assembly's drawing sheet: instances as for assembly_clashes (placed) -> sheet.build_assembly. explode
    (0 … 1): its iso view drawn with the parts pulled apart."""
    from . import sheet as S
    placed = []
    for inst in instances or []:
        try:
            st = body_of(inst.get("part"))
        except K.KernelError:
            continue
        placed.append((inst.get("id"), K.placed(st.body.shape, inst.get("matrix") or [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1])))
    key = _key([float(explode or 0)] + [[i.get("id"), (i.get("part") or {}).get("features") or [], i.get("matrix")] for i in instances or []])
    return S.build_assembly(placed, paper, _exploded(placed, float(explode)) if explode else None, key=key)


def assembly_clashes(instances, quick=False):
    """Where the placed parts of an assembly overlap: instances [{id, part: {features}, matrix: [16]}] ->
    [{a, b (their ids), volume, bbox}]. A part without a solid is left out."""
    shapes = []
    for inst in instances or []:
        try:
            st = body_of(inst.get("part"))
        except K.KernelError:
            continue
        shapes.append((inst.get("id"), K.placed(st.body.shape, inst.get("matrix") or [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1])))
    return K.interference(shapes, quick=quick)


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


def assembly_step(instances=None, tree=None, name="assembly", fmt="step"):
    """An assembly -> a STEP file (fmt "iges": an IGES; "glb": a binary glTF, a node per placed part). tree {root,
    parts: {id: {name, features, colour?, material?}}, assemblies: {id: {name, instances: [{ref, matrix: [16],
    colour?}]}}}: a structured one (a product per part, placed instances, sub-assemblies nested, names and colours;
    kernel.write_step_tree / write_iges_tree / write_gltf_tree). Else instances [{part: {features}, matrix: [16]}]: the
    placed bodies in one compound (STEP / IGES)."""
    if fmt not in ("step", "iges", "glb"):
        raise K.KernelError(f"Unknown export format “{fmt}”.")
    if fmt == "glb" and not tree:
        raise K.KernelError("A glTF of an assembly is made from its tree (its parts, placed).")
    if tree:
        return _tree_step(tree, name, fmt)
    shapes = []
    for inst in instances or []:
        st = body_of(inst.get("part"))
        shapes.append(K.placed(st.body.shape, inst.get("matrix") or [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]))
    if not shapes:
        raise K.KernelError("The assembly is empty — insert parts first.")
    return K.to_iges(K.compound(shapes)) if fmt == "iges" else K.to_step(K.compound(shapes))


def _tree_step(tree, name, fmt="step"):
    from .materials import finish_of
    parts, asms = {}, {}
    for pid, p in (tree.get("parts") or {}).items():
        try:
            st = body_of(p)
        except K.KernelError:
            continue  # (a part without a solid yet is left out, as in the collisions)
        body = st.body
        colours = [(face, c) for n, c in st.colours.items() for face in body.faces_of(n)]
        parts[pid] = {"name": p.get("name") or pid, "shape": body.shape, "colour": p.get("colour"), "colours": colours,
                      "finish": finish_of(p.get("material"))}
    for aid, a in (tree.get("assemblies") or {}).items():
        seen, insts = {}, []
        for inst in a.get("instances") or []:
            ref = inst.get("ref")
            if ref not in parts and ref not in (tree.get("assemblies") or {}):
                continue
            label = (parts.get(ref) or (tree["assemblies"].get(ref) or {})).get("name") or ref
            seen[ref] = seen.get(ref, 0) + 1
            insts.append({**inst, "name": inst.get("name") or f"{label}-{seen[ref]}"})  # SolidWorks-like: "Bolt-2"
        asms[aid] = {"name": a.get("name") or aid, "instances": insts}
    if not parts:
        raise K.KernelError("The assembly is empty — insert parts first.")
    if fmt == "iges":
        return K.write_iges_tree(parts, asms, tree.get("root"))
    if fmt == "glb":
        return K.write_gltf_tree(parts, asms, tree.get("root"))
    return K.write_step_tree(parts, asms, tree.get("root"), name)
