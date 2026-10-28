---
name: model-a-part
description: Use when the user wants a new mechanical or functional part built in the app's 3D model workspace (a bracket, a box, a spacer, a knob, a holder, an adapter…) — sketches turned into a solid with extrude / revolve, then holes, roundings, bevels and shells.
---

# Model a part in Auto3DModeler

Everything is in mm. x right, y up, z up from the printer bed. The 3D printer bed is the XY plane (z = 0).

## Simple shapes, easy to edit (the default)

A person must be able to read the steps and change the part. Unless the user said it may be built any way:
- **One idea per sketch**: a rectangle, a circle, a slot, an L — not a whole outline with every detail in it.
  As few sizes in a sketch as possible (a rectangle: its width and height; place it by the origin / its centre).
- **The rest by features**: holes with `hole` (not circles in the base sketch when they are holes of their own),
  repeats with `pattern`, symmetry with `mirror`, roundings and bevels with `fillet` / `chamfer` (not arcs in the
  sketch), pockets and bosses as their own sketch + extrude.
- **Sizes that mean something**: the plate's width, the hole's Ø, the distance between holes — round numbers, from
  the part's centre or edge, the way a drawing would give them. Name steps by what they are when you can.
- Fewer, bigger steps that each do one thing beat many tiny ones; complex profiles only where the shape needs them
  (a smooth vase, a cam).
If the brief says "any way that reaches the goal", you may use one detailed profile — still keep its key sizes.

## Steps

1. **The brief** (auto3d:start-a-design): what it is for, printed or not, easy to edit or not — ask with `ask_user {…}`
   what the user has not said. Its key sizes are the user's decision; otherwise pick defaults (printed: walls ≥ 1.2 mm,
   hole clearance +0.2 mm, roundings 1–2 mm).
2. `new_model {name}` — a new 3D model tab (or work on the model on screen: `get_model`).
3. **Base sketch** on the plane the part lies on: usually `"XY"` (on the bed). For round parts (a vase, a knob,
   a wheel) sketch half the profile on `"XZ"` (front) beside the vertical axis and revolve it.
   `add_feature {type: "sketch", plane: "XY", shapes: [...]}` with shapes:
   - `{rect: {x, y, w, h}}` — x, y = the lower-left corner
   - `{circle: {x, y, d}}` — centre and diameter (a circle inside a rectangle becomes a hole)
   - `{polyline: {points: [[u, v], ...]}}` — closed automatically (an L-shape, a triangle, a profile)
   - `{profile: {points: [[u, v], {smooth: [[u, v], ...]}, [u, v], {arc: [u, v]}, [u, v], ...]}}` — closed: corners
     `[u, v]` joined by straight lines, `{smooth: [...]}` a smooth curve through those points to the next corner (one
     clean B-spline surface after revolve / extrude, no facets), `{arc: [u, v]}` an arc through that point.
     **Round, organic parts** (a vase, a bottle, a knob, a duck's body): plane `"XZ"`, u = the radius (≥ 0) and
     v = the height, e.g. `[[0, 0], [20, 0], {smooth: [[26, 15], [18, 35], [24, 55]]}, [22, 60], [0, 60]]`, then
     a revolve (`add_feature {type: "revolve", sketch, axis: "y"}`). Put a few more points where the shape bends; keep the axis side straight (u = 0).
   - any shape + `pattern: {count, spacing}` (copies in a row along X) or `pattern: {count, around: [u, v]}`
     (around that point, over 360°) — e.g. six holes on a circle: `{circle: {x: 20, y: 0, d: 5}, pattern: {count: 6,
     around: [0, 0]}}`; the copies stay equal to the shape (a ⁂ Pattern in the sketch the user can change).
   All sizes and positions are locked (the sketch is fully defined), so the user can change them later.
4. **Base solid**: `add_feature {type: "extrude", sketch: "<id>", d: 10}` (op "add"); or
   `{type: "revolve", sketch, axis: "y", angle: 360}`.
5. **Details on faces** — find faces / edges with `find_refs`, never guess names:
   - the top face: `find_refs {kind: "face", normal: [0, 0, 1], extreme: "max"}`
   - a side: `normal: [1, 0, 0]` (right), `[-1, 0, 0]`, `[0, 1, 0]` (back), `[0, -1, 0]` (front)
   - the edges of a face: `find_refs {kind: "edge", of_face: "<face name>"}`; round edges: `circular: true`
   - Holes: `add_feature {type: "hole", face: "<face name>", points: [[u, v], ...], d: 5}` — u, v are measured
     from the face's centre (the middle of its outline, also with holes in it) along the face's own x / y (on a top face: world x / y). Through all by default;
     `through: false, depth: 6` for blind holes. A hole into a side face (across Z) of a printed part: `teardrop: true`
     (a 45° point on top — prints without support).
   - Pockets / bosses: a sketch with `plane: {face: "<face name>"}` (its origin is the face's centre), then
     extrude `op: "cut"` (pocket, `through: true` for a cut through) or `op: "add"` (boss).
     `upto_next: true` instead of `d` goes as far as the first face of the part across the whole sketch (a boss up to
     the plate above it, a cut through the first wall only — it follows the part); `d2: 5` also extrudes 5 mm to the
     other side of the sketch (`went.other_side` says where).
   - **Measure from a corner or the part's origin** instead of the face's centre: `origin: "corner"` (the face's
     min-u min-v corner, followed when the part changes) or `origin: "world"` (points / shapes in world X / Y / Z: a
     hole at world (30, 10) on a top face is `points: [[30, 10]]`), or `origin: {point: "<point step>"}` — on a hole
     step, or in a sketch's plane `{face, origin}`. Prefer these to working out offsets from the centre.
6. **Roundings and bevels last**: `{type: "fillet", edges: [<ref from find_refs>…], r: 2}`,
   `{type: "chamfer", edges: [...], d: 1}`. Prefer a chamfer on edges that touch the bed (no overhang).
   **Shell** (hollow out, e.g. a cup or a box): `{type: "shell", faces: ["<open face name>"], t: 2}`.
   **Text on a face**: `{type: "decal", face: "<flat face name>", text: "AB-12", h: 6, op: "add" | "cut", depth: 0.8}`
   (`at: [u, v]` from the face's centre). Strokes ≥ 0.6 mm wide print well — h ≥ 5 mm for bold text.
   **Repeats**: make ONE hole / boss / cut, then `{type: "pattern", of: ["<its id>"], dir: "x", count: 4, spacing: 15}`
   (a row) or `{type: "pattern", of: [...], kind: "circular", axis: "z", count: 6}` (a bolt circle; `axis` may be
   a round face's name). A warning "changed nothing" means the copies left the part — fix dir / spacing.
   **Around an imported model** (a `solid` step from a STEP / STL the user opened — get_model gives its `bbox`):
   a cover / holder is a box sketched a wall bigger than the bbox, extruded, `shell`ed open on one side; then the user
   switches the solid to ⬚ Cut out (or you `edit_feature` it with `fields: {op: "cut"}`, after it in the steps —
   `op: "ref"` shows it only). Ask the user to add the file with ▣ Solid from a file if it is not there. An IGES
   (`open_file` on a .igs / .iges) opens as such a model; when its surfaces do not close it comes as `op: "ref"` — a
   reference body to build around, say so.
   **Mirror**: `{type: "mirror", plane: "YZ"}` adds the mirror image of the whole part (left ↔ right; "XZ" front ↔
   back, "XY" top ↔ bottom, or `face: "<flat face>"`); `of: "<step id>"` mirrors one step only; `copy: false` turns the
   part over instead. Model half of a symmetric part, then mirror it.
   **Split** (cut the part in two along a plane — a box and its lid, a print too big for the bed):
   `{type: "split", plane: {datum: "XY", offset: 15}, keep: "both"}` (two bodies in one part; get_model's body says
   `solids`), `keep: "above"` (only the side the plane's normal points to: +Z for XY, +X for YZ, −Y for XZ) or
   `"below"`; `plane` may be `{face: "<flat face>", offset}` or `{face, mid: "<the face across>"}` (the middle).
   The cut faces are `<id>:cut:0` (above) and `<id>:cut:1` (below).
   **Reference point** (a place to measure / sketch from that follows the part): `{type: "point", at: {corner: [x, y, z]}}`
   (the nearest corner), `at: {centre: <round edge ref>}` or `at: {mid: <edge ref>}`; `find_refs {kind: "point"}` lists
   them (and corners with ready refs). No geometry — it shows as "• Point 1".
   **From a shaft's or a hole's axis** (a cross hole, a shaft along the face, a boss): `find_refs {kind: "axis"}` lists
   the round faces' axes; a sketch shape's `from: {axis: "<name>"}` (x / y as usual — its place across the axis is kept
   from it) or a hole's `from: [{x: {axis: "<name>", d: 15}}]` — they follow the axis when the part changes.
   **In the middle** of a face (it stays there when the part changes size): a hole's
   `from: [{x: {mid: [<left edge ref>, <right edge ref>]}, y: {mid: [<front edge ref>, <back edge ref>]}}]` (edge refs
   from find_refs; one axis alone = on the middle line).
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

## Colours

`set_look {color: "#FFD400"}` colours the whole model (`opacity` for see-through), `paint_faces {faces: [names], color}`
single faces (names from `find_refs`; a step id such as `"F6"` colours every face that step made — e.g. a beak that is
its own revolve). The model keeps them, also in assemblies. Threaded holes (a hole's `thread: "M5"`) are plain tap
drills on screen; `set_look {threads: "cosmetic"}` draws their threads as thin helix lines (view only), `"real"` cuts
true ISO threads into the solid (exports and 3D prints get them; slower — only when asked), `"hidden"` takes them away.
