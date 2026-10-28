---
name: change-a-model
description: Use when the user wants to change an existing 3D model part (make it bigger, move a hole, add or remove a rounding, cut a slot, hollow it out) — or asks what the model is made of.
---

# Change a 3D model part

1. `list_parts` and `open_part` if the model is not on screen; then `get_model` — its steps (id, type,
   values, ok / issues), the body's size and volume.
2. Change the step that holds the value instead of adding new ones:
   - a size of the base shape → `edit_feature {id: "<sketch id>", fields: {shapes: [...]}}` (the whole shape
     list again, as in add_feature) or the extrude's `{d}`;
   - a hole → `edit_feature {id, fields: {d: 6, points: [[u, v]]}}`; a rounding → `{r}`; a bevel → `{d}`. The changes
     always go inside `fields` (a key next to it is refused); the hole keeps its place unless you give new points.
   Later steps keep their faces and edges (names follow), so they move with the change.
3. New details: find faces / edges with `find_refs` (top face: `{kind: "face", normal: [0, 0, 1], extreme:
   "max"}`; its edges: `{kind: "edge", of_face: "<name>"}`), then `add_feature`.
4. Remove: `delete_feature {id}` (steps that need it go too) or keep it but `turn_off_feature {id}`.
5. If a step shows a warning that an edge was "found again by its position only", look at a screenshot and
   re-pick the edges with `edit_feature {id, fields: {edges: [...]}}`.
6. Check `get_model` (all ok) and `get_screenshot`. Everything can be undone (`undo`).
