"""Standard holes for metric screws. A hole step has independent properties, as in SolidWorks / Solid Edge: its
`shape` (plain, ⌴ counterbore, ⌵ countersink, D), its `thread` (none, or "M5" / {standard, kind}), its depth (`through`
or `depth`) and its size (`standard` "M5", or a plain Ø `d`) — they fill its sizes from ISO tables (the Hole panel;
web/js/modeler/holes.js has the same table). The old single `hole_type` (clearance = plain M5 without a thread, tapped
= plain M5 with one …) is still read. The sizes:
  clearance    Ø per ISO 273 medium (M5: Ø5.5)
  counterbore  that hole + a counterbore for an ISO 4762 socket head (DIN 974-1: M5 Ø10 × 5.4)
  countersink  that hole + a 90° countersink for an ISO 10642 flat head (its theoretical head Ø dk: M5 Ø11.2)
  tapped       the thread (ISO 261 coarse) drilled at its tap drill (ISO 2306: M5 Ø4.2)
A size given on the step (d, head_d, head_depth — the panel's "Edit sizes") wins over the table.
A D hole ("d_flat": for a D-shaft) is no screw size: its Ø d and `flat`, the size across the flat (from the flat to the
far side, a D-shaft's: Ø5 -> 4.5), default from D_FLATS (else 0.9 × d: the flat 0.8 × r from the centre); the flat
faces the face's +x, turned by `flat_angle` degrees."""
from __future__ import annotations

# ISO metric coarse threads: the tap drill a threaded hole is drilled with (ISO 2306)
THREADS = {"M2": 1.6, "M2.5": 2.05, "M3": 2.5, "M4": 3.3, "M5": 4.2, "M6": 5.0, "M8": 6.8, "M10": 8.5, "M12": 10.2,
           "M16": 14.0, "M20": 17.5}
PITCH = {"M2": 0.4, "M2.5": 0.45, "M3": 0.5, "M4": 0.7, "M5": 0.8, "M6": 1.0, "M8": 1.25, "M10": 1.5, "M12": 1.75,
         "M16": 2.0, "M20": 2.5}  # (ISO 261, coarse)
# per size: clearance Ø (ISO 273 medium), counterbore Ø and depth (ISO 4762 head + room), countersink Ø at 90°
# (ISO 10642 dk; M2 / M2.5 have no ISO 10642 screw: ISO 15065's)
SIZES = {
    "M2": {"clearance": 2.4, "cbore_d": 4.3, "cbore_depth": 2.4, "csk_d": 4.4},
    "M2.5": {"clearance": 2.9, "cbore_d": 5, "cbore_depth": 2.9, "csk_d": 5.5},
    "M3": {"clearance": 3.4, "cbore_d": 6.5, "cbore_depth": 3.4, "csk_d": 6.7},
    "M4": {"clearance": 4.5, "cbore_d": 8, "cbore_depth": 4.4, "csk_d": 9},
    "M5": {"clearance": 5.5, "cbore_d": 10, "cbore_depth": 5.4, "csk_d": 11.2},
    "M6": {"clearance": 6.6, "cbore_d": 11, "cbore_depth": 6.4, "csk_d": 13.4},
    "M8": {"clearance": 9, "cbore_d": 15, "cbore_depth": 8.6, "csk_d": 17.9},
    "M10": {"clearance": 11, "cbore_d": 18, "cbore_depth": 10.6, "csk_d": 22.4},
    "M12": {"clearance": 13.5, "cbore_d": 20, "cbore_depth": 12.6, "csk_d": 26.9},
    "M16": {"clearance": 17.5, "cbore_d": 26, "cbore_depth": 16.6, "csk_d": 33.6},
    "M20": {"clearance": 22, "cbore_d": 33, "cbore_depth": 20.6, "csk_d": 40.3},
}
TYPES = ("clearance", "counterbore", "countersink", "tapped")  # (none: a simple hole, sized by its d)
# D-shafts (stepper motors, knobs): Ø -> the size across the flat
D_FLATS = {3: 2.5, 4: 3.5, 5: 4.5, 6: 5.5, 8: 7.5}


def d_flat(d: float) -> float:
    """The size across a D hole's flat for Ø d: a common D-shaft's, else 0.9 × d (the flat 0.8 × r from the centre)."""
    return D_FLATS.get(d, round(0.9 * d, 2))


def preset(kind: str, size: str) -> dict:
    """The fields a standard hole gets: {d, head?, head_d?, head_depth?, head_angle?, thread?} — ValueError for an
    unknown type or size."""
    if kind not in TYPES:
        raise ValueError(f"Unknown hole type “{kind}” — one of simple, {', '.join(TYPES)}, d_flat.")
    if size not in SIZES:
        raise ValueError(f"Unknown size “{size}” — one of {', '.join(SIZES)}.")
    s = SIZES[size]
    if kind == "tapped":
        return {"d": THREADS[size], "thread": size}
    out = {"d": s["clearance"]}
    if kind == "counterbore":
        out.update(head="cbore", head_d=s["cbore_d"], head_depth=s["cbore_depth"])
    elif kind == "countersink":
        out.update(head="csk", head_d=s["csk_d"], head_angle=90)
    return out


# the hole's shape — a property of its own, as its thread, its depth (through / blind) and its size are
SHAPES = ("plain", "counterbore", "countersink", "d_flat")
# the old single "hole_type" -> (shape, threaded); files and AI calls that give it keep working
OLD_TYPES = {"simple": ("plain", False), "clearance": ("plain", False), "counterbore": ("counterbore", False),
             "countersink": ("countersink", False), "tapped": ("plain", True), "d_flat": ("d_flat", False)}


def spec(f: dict):
    """A hole step's properties -> (shape, threaded, standard or None, thread kind or None) — from the new fields
    (shape, thread: false | "M5" | {standard, kind: cosmetic | real}, standard) or the old hole_type; None: a step from
    before either (its d / head / thread as they are). ValueError: an unknown shape / type."""
    thr = f.get("thread")
    if f.get("shape") is not None:
        shape = f["shape"]
        if shape not in SHAPES:
            raise ValueError(f"Unknown hole shape “{shape}” — one of {', '.join(SHAPES)}.")
        if isinstance(thr, dict):
            return shape, True, thr.get("standard") or f.get("standard"), thr.get("kind")
        return shape, bool(thr), f.get("standard") or (thr if isinstance(thr, str) and thr else None), None
    kind = f.get("hole_type")
    if not kind:
        return None
    if kind not in OLD_TYPES:
        raise ValueError(f"Unknown hole type “{kind}” — one of {', '.join(OLD_TYPES)}.")
    shape, threaded = OLD_TYPES[kind]
    if kind == "simple":
        return shape, False, None, None
    return shape, threaded, f.get("standard") or (thr if threaded and isinstance(thr, str) else None), None


def preset_for(shape: str, threaded: bool, size: str) -> dict:
    """The fields of a standard hole of these properties: {d, head?, head_d?, head_depth?, head_angle?, thread?} — the
    hole the tap drill when threaded, else the clearance Ø (ISO 273 medium); the head the size's."""
    if size not in SIZES:
        raise ValueError(f"Unknown size “{size}” — one of {', '.join(SIZES)}.")
    s = SIZES[size]
    out = {"d": THREADS[size], "thread": size} if threaded else {"d": s["clearance"]}
    if shape == "counterbore":
        out.update(head="cbore", head_d=s["cbore_d"], head_depth=s["cbore_depth"])
    elif shape == "countersink":
        out.update(head="csk", head_d=s["csk_d"], head_angle=90)
    return out


def resolve(f: dict) -> dict:
    """A hole step with its standard's sizes filled in (the step's own d / head_d / head_depth / head_angle kept); its
    head and thread are its shape's and thread's — as the kernel and the drawing read them (thread "M5", head
    "cbore" / "csk"; a D hole hole_type "d_flat"). A step with neither the new fields nor a hole_type: as it is.
    ValueError: an unknown shape / type / size, or a screw's hole with no size."""
    sp = spec(f)
    if sp is None:
        return f
    shape, threaded, size, _ = sp
    drop = ("head", "head_d", "head_depth", "head_angle", "thread", "standard", "hole_type")
    if shape == "d_flat":  # (no screw size: its Ø and flat; no head, no thread)
        out = {k: v for k, v in f.items() if k not in drop}
        out["hole_type"] = "d_flat"
        if out.get("flat") is None and isinstance(out.get("d", 5), (int, float)):
            out["flat"] = d_flat(float(out.get("d", 5)))
        return out
    if not size:
        if shape == "plain" and not threaded:  # (a plain Ø d hole)
            return {k: v for k, v in f.items() if k not in drop}
        what = "threaded" if threaded else shape
        raise ValueError(f"A {what} hole needs a size (standard: one of {', '.join(SIZES)}).")
    p = preset_for(shape, threaded, size)
    out = {k: v for k, v in f.items() if k not in ("head", "thread")}
    out["standard"] = size
    for k, v in p.items():
        if k in ("head", "thread") or out.get(k) is None or threaded and k == "d":
            out[k] = v
    if shape == "countersink":
        out.pop("head_depth", None)
    elif shape != "counterbore":
        for k in ("head_d", "head_depth", "head_angle"):
            out.pop(k, None)
    return out
