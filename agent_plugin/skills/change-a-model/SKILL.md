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
   Rolled back (get_model shows `rollback`): the body is as after that step and add_feature inserts there — to insert
   a step before a later one, `rollback {to: "<id>"}`, add it, then `rollback {to: "end"}`. While it is up, exports,
   `prepare_print` / `check_print`, assemblies and drawing sheets use the part as the bar stands (as SolidWorks) — put
   it back at the end before exporting or printing the finished part, unless the user asked for the earlier state.
5. If a step shows a warning that an edge was "found again by its position only", look at a screenshot and
   re-pick the edges with `edit_feature {id, fields: {edges: [...]}}`.
6. Check `get_model` (all ok) and `get_screenshot`. Everything can be undone (`undo`).
   Mass, area and the centre of mass (balance, a stand that must not tip): `get_model`'s body has `mass_g_solid`,
   `area_mm2` and `cog_mm` (`set_material` first for a metal).

**Versions.** The app keeps versions of the project by itself (🕘 Versions). Before a big or risky change call
`save_version {label: "before <what>"}`; `list_versions` lists them (newest first), `compare_versions {a: "<id>"}`
says what changed since (steps, values "Extrude 1: 10 → 15 mm", the volume). `restore_version {id}` puts the whole
project back — only when the user asks; the answer names the version that undoes it. To try another design without
losing this one: `create_variant {name: "longer"}` (a branch with its own versions; the user switches back in 🕘
Versions and can take one part over from a variant there).

**Missing a tool?** When no tool fits and you work around it (several calls for one thing, guessing, asking the user
to click for you), file it at once: `list_reports {search: "<the words>"}`, and if it is not there
`report_problem {kind: "tool request", …}` (the tool you would want: name, inputs, result; your workaround) —
then tell the user in one line and carry on. A wrong result is `{kind: "bug"}`; each thing reported once.
