---
name: model-a-part
description: Use when the user wants a new mechanical or functional part built in the app's 3D model workspace (a bracket, a box, a spacer, a knob, a holder, an adapter…) — sketches turned into a solid with extrude / revolve, then holes, roundings, bevels and shells.
---

# Model a part in Auto3DModeler

Everything is in mm. x right, y up, z up from the printer bed. The 3D printer bed is the XY plane (z = 0).

## Steps

1. **Clarify only what is really the user's decision**: what the part is for and its key sizes. Otherwise
   pick printable defaults (walls ≥ 1.2 mm, hole clearance +0.2 mm, roundings 1–2 mm).
2. `new_model {name}` — a new 3D model tab (or work on the model on screen: `get_model`).
3. **Base sketch** on the plane the part lies on: usually `"XY"` (on the bed). For round parts (a vase, a knob,
   a wheel) sketch half the profile on `"XZ"` (front) beside the vertical axis and revolve it.
   `add_feature {type: "sketch", plane: "XY", shapes: [...]}` with shapes:
   - `{rect: {x, y, w, h}}` — x, y = the lower-left corner
   - `{circle: {x, y, d}}` — centre and diameter (a circle inside a rectangle becomes a hole)
   - `{polyline: {points: [[u, v], ...]}}` — closed automatically (an L-shape, a triangle, a profile)
   All sizes and positions are locked (the sketch is fully defined), so the user can change them later.
4. **Base solid**: `add_feature {type: "extrude", sketch: "<id>", d: 10}` (op "add"); or
   `{type: "revolve", sketch, axis: "y", angle: 360}`.
5. **Details on faces** — find faces / edges with `find_refs`, never guess names:
   - the top face: `find_refs {kind: "face", normal: [0, 0, 1], extreme: "max"}`
   - a side: `normal: [1, 0, 0]` (right), `[-1, 0, 0]`, `[0, 1, 0]` (back), `[0, -1, 0]` (front)
   - the edges of a face: `find_refs {kind: "edge", of_face: "<face name>"}`; round edges: `circular: true`
   - Holes: `add_feature {type: "hole", face: "<face name>", points: [[u, v], ...], d: 5}` — u, v are measured
     from the face's centre along the face's own x / y (on a top face: world x / y). Through all by default;
     `through: false, depth: 6` for blind holes.
   - Pockets / bosses: a sketch with `plane: {face: "<face name>"}` (its origin is the face's centre), then
     extrude `op: "cut"` (pocket, `through: true` for a cut through) or `op: "add"` (boss).
6. **Roundings and bevels last**: `{type: "fillet", edges: [<ref from find_refs>…], r: 2}`,
   `{type: "chamfer", edges: [...], d: 1}`. Prefer a chamfer on edges that touch the bed (no overhang).
   **Shell** (hollow out, e.g. a cup or a box): `{type: "shell", faces: ["<open face name>"], t: 2}`.
   **Text on a face**: `{type: "decal", face: "<flat face name>", text: "AB-12", h: 6, op: "add" | "cut", depth: 0.8}`
   (`at: [u, v]` from the face's centre). Strokes ≥ 0.6 mm wide print well — h ≥ 5 mm for bold text.
   **Repeats**: make ONE hole / boss / cut, then `{type: "pattern", of: ["<its id>"], dir: "x", count: 4, spacing: 15}`
   (a row) or `{type: "pattern", of: [...], kind: "circular", axis: "z", count: 6}` (a bolt circle; `axis` may be
   a round face's name). A warning "changed nothing" means the copies left the part — fix dir / spacing.
   **Mirror**: `{type: "mirror", plane: "YZ"}` adds the mirror image of the whole part (left ↔ right; "XZ" front ↔
   back, "XY" top ↔ bottom, or `face: "<flat face>"`); `of: "<step id>"` mirrors one step only; `copy: false` turns the
   part over instead. Model half of a symmetric part, then mirror it.
7. **Check**: `get_model` — every step `ok: true` (read `issues` / `warnings` and fix them),
   `get_screenshot {view: "iso"}` and another view. Report the size and the steps the user can change
   (double-click a step in the list, or ask you).

## Changing it later

`edit_feature {id, fields}` (e.g. `{d: 15}` for an extrude, `{r: 3}`, `{shapes: [...]}` for a sketch),
`delete_feature {id}` (steps that need it go too), `turn_off_feature {id, off: true}`, `undo`.
Faces and edges keep their names when earlier sizes change, so later steps follow.

## Worked example — a 60 × 40 × 5 plate with 4 corner holes Ø4 and rounded corners

```
new_model {name: "Plate"}
add_feature {type: "sketch", plane: "XY", shapes: [{rect: {x: 0, y: 0, w: 60, h: 40}}]}      -> F1
add_feature {type: "extrude", sketch: "F1", d: 5}                                             -> F2
find_refs {kind: "face", normal: [0, 0, 1], extreme: "max"}                                    -> "F2:end"
add_feature {type: "hole", face: "F2:end", d: 4, points: [[-24, -14], [24, -14], [24, 14], [-24, 14]]}
find_refs {kind: "edge", of_face: "F2:end"} … pick the 4 vertical corner edges: find_refs {kind: "edge", near: [0, 0, 2.5]} etc.
add_feature {type: "fillet", edges: [<4 refs>], r: 3}
get_model, get_screenshot
```

## Pitfalls

- A revolve profile must lie on one side of its axis.
- Sketch on a face: the face's centre is (0, 0) of the sketch.
- A rounding that is too big for its edge fails — try a smaller r.
- Do not open files or the sample on your own.
