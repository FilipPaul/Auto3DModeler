---
name: from-picture
description: Use when the user gives a photo or picture (a path, or an attached photo) and wants a part from it — a cookie cutter, a plaque, a stencil, a solid shape, or a mechanical part shaped like the object in the picture; also when the user has the "Outline from picture" window open and talks about its outlines.
---

# A part from a picture

1. `trace_picture {path}` — numbered candidate outlines (most likely first) and an image with them drawn in.
   If none fits, call it again with hints: `seeds` (points [x, y] in 0..1 inside the object), `bg_seeds`
   (outside it), `rect` (a box around it), `object_colors` / `background_colors`. A cookie cutter, wire or line
   drawing photographed on paper (the background shows inside it): `mode: "thin"` (only thin-wall outlines;
   `"solid"` = only filled objects; default `"auto"` tries both and lists a see-through ring first).
2. Decide what to make:
   - **Cookie cutter, plaque, stencil, a simple solid shape** → `use_outline {candidate, width (mm), make:
     "cutter" | "solid" | "custom"}`. This is a quick part: change it with `set_part_options`, add holes and
     text with `add_object` / `add_shape`, decorate with `add_design_layer`.
   - **A part shaped like the picture with real 3D features** (holes from the side, roundings, a boss) →
     first `use_outline` (make "solid"), then the user can click **◆ To 3D model**; or build it in a model
     (`new_model`) with a sketch from simple shapes measured on the picture.
3. Cookie cutters: notches narrower than about twice the wall do not cut — use the outline clean-up
   (`set_part_options {cleanup: {close: 1.5}}`) or round them.
4. Check with `get_part` and `get_screenshot`; tell the user the real size.

**The user has the outline window open** (the message says "[On screen: the “Outline from picture” window …]", or
they talk about "the candidates", "the shadow", "the thin-wall one"): work in that window, do not trace the file
again. `outline_window` — its candidates as the list names them (`#1` …, `edit`, `in use`), the selected one, the
Object mode, hints, size, and the picture with every outline drawn in its colour with its name on a 10 % grid.
Then `outline_window_edit`, one call per wish, e.g.:
- "take the thin-wall one" → `{mode: "thin"}` (or `{select: 2}` when a listed one says `thin_wall`);
- "remove the shadow on the left" → `{not_this: [[0.12, 0.8]]}` (a point on the shadow, read off the grid), or with an
  edit: `{select: 1, cut: [3]}` when the shadow is its own candidate; "the wheels too" → `{add: [4]}`;
- "only this one" → `{inside: [[x, y]]}`; "only in this area" → `{box: [x0, y0, x1, y1]}`;
- "smooth it more" → `{smoothing: 3}` (0..6); "turn it 90°" → `{rotate: 90}`; "keep the holes" → `{holes: true}`;
- "make it 65 mm wide" → `{width: 65}`; "a cookie cutter" → `{make: "cutter"}`;
- "that's it / continue" → `{accept: true}` (the size must be set) — the part is made; go on with `get_part`.
Look at the picture it answers with before you say it is right.

**Missing a tool?** When no tool fits and you work around it (several calls for one thing, guessing, asking the user
to click for you), file it at once: `list_reports {search: "<the words>"}`, and if it is not there
`report_problem {kind: "tool request", …}` (the tool you would want: name, inputs, result; your workaround) —
then tell the user in one line and carry on. A wrong result is `{kind: "bug"}`; each thing reported once.
