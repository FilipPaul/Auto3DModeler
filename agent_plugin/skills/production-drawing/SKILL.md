---
name: production-drawing
description: Use when a made part (machined, laser-cut, turned) needs a manufacturing drawing, or the user asks for a "drawing", "výkres", PDF / DXF for the workshop. Minimum views, dimensions from the datums, hole callouts, functional tolerances / fits / roughness only, title block (material, finish, ISO 2768, edge note), a completeness check with get_sheet — on the app's drawing sheet (sheet_open, get_sheet, sheet_edit).
---

# A production drawing on the sheet

The sheet follows the part: put the facts in the **model** first, then the sheet shows them. Mechanics of every
sheet_edit field: its tool description; this skill is what a good drawing needs.

## 1. Prepare the model
- `set_material {material, tolerance: "m"}` — material in the title block, ISO 2768-m as the general tolerance.
- Fits on the holes that need them: `edit_feature {id, fields: {fit: "H7"}}` (dowels, bearings) → "Ø4 H7".
- Holes as standard hole steps (standard, shape, thread, depth): each becomes one callout
  ("4× M4 ↧ 8", "2× Ø4.5 ⌴ Ø8 ↧ 4.4") — no separate depth or head dimensions needed.
- The part's origin on its datums (design-principles): the preset dimensions holes from the left / bottom edges.

## 2. Open and choose the views
- `sheet_open {part}` → views, dimensions, `check`.
- **Minimum views**: a plate = Front + Top (Top shows the holes); Right only when side features exist; a turned
  part = Front (with the axis) alone, + a section for inner bores. Iso only as a picture (`sheet_edit {views:
  {Iso: true}}` on complex parts, off on simple ones); remove an empty view: `sheet_edit {views: {Right: false}}`.
- **A section for inner features** (pockets from below, cross holes, counterbores): Section A–A is a sheet
  suggestion — select the Front view (`gui_action {control: <the view's n from gui_state>}`) and
  `gui_action {suggest: "Section A–A"}`; it takes the Right view's place.
- Paper / scale: `sheet_edit {paper: "A3"}`, `{scale: "1:2"}` only when the automatic fit is unreadable.

## 3. Dimensions
- Preset medium is the start (`sheet_edit {preset: "medium"}`); details only where they are read.
- **Completeness**: `get_sheet` `check` lists the missing sizes → `sheet_edit {complete: true}` or one by one
  `sheet_edit {add: [{missing: "<id>", view: "Top"}]}` (the view where the feature is seen as a true shape).
  Sizes given twice: `sheet_edit {drop_twice: true}`. Repeat until `check` has nothing missing.
- **From the datums**: hole positions from the datum edges (`hole_position` in get_sheet: pitches, PCD, ordinates
  for many holes); a size that the function measures elsewhere (between dowels) added by
  `sheet_edit {add: [{view, a, b}]}` (point keys from `get_sheet {points: "Top"}`) and the automatic one removed
  (`sheet_edit {remove: [id]}`).
- A size in the wrong view: `sheet_edit {move: {<id>: {view: "Right"}}}`; clutter: `remove`.
- No hole table tool: many holes go as callouts + ordinate positions; a missing hole table → `report_problem
  {kind: "tool request", …}` once (after `list_reports`).

## 4. Tolerances, fits, roughness — only functional
- General: ISO 2768-m from the model (title block); `sheet_edit {texts: {tolstd: "ISO 2768-mK"}}` when geometry
  tolerances are general too.
- Own tolerance only on functional sizes: `sheet_edit {dims: {<id>: {tol: "±0.02"}}}` (dowel pitch, a sealing depth,
  a probe-plate thickness); a Ø: `sheet_edit {fits: {<id>: "H7"}}`; reference sizes `{ref: true}`.
- Roughness general: `sheet_edit {texts: {surface: "Ra 3,2"}}`; a surface's own only for fits, sliding or sealing
  faces: `sheet_edit {roughness: [{view, edge, ra: 1.6, process: "remove"}]}` (edge keys from `get_sheet {points:
  "Front"}`).

## 5. Title block and notes
- `sheet_edit {texts: {title: "Probe plate", number: "<drawing no.>", drawn: "<name>",
  note: "Material EN AW-5754 (AlMg3). Edges broken ISO 13715 −0.3. Clear anodised E6/EV1 10 µm, Ø H7 masked."}}`
  — the grade, the finish and the edge note; whatever the material list cannot say.
- The user's own title block: `sheet_edit {template: "<name>"}` (get_sheet lists the templates); a whole assembly's
  set: `template_all: true`.
- Assembly sheets: overall sizes, the base part's mounting holes, balloons and the parts list — `get_sheet`
  `balloons.ok`; part details stay on the parts' sheets.

## 6. Check and hand over
- `get_sheet`: `check` empty, no `lost` dimensions, every fit / tolerance has a reason.
- `get_screenshot` of the sheet: readable, nothing overlaps, every view has its key sizes.
- `export {format: "pdf"}` (and `"dxf"` when the user's CAD should take it: 1:1, real dimensions).
- Tell the user: views, the functional tolerances and why, material and finish, open points.
