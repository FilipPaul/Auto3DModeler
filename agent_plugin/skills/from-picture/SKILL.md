---
name: from-picture
description: Use when the user gives a photo or picture (a path, or an attached photo) and wants a part from it — a cookie cutter, a plaque, a stencil, a solid shape, or a mechanical part shaped like the object in the picture.
---

# A part from a picture

1. `trace_picture {path}` — numbered candidate outlines (most likely first) and an image with them drawn in.
   If none fits, call it again with hints: `seeds` (points [x, y] in 0..1 inside the object), `bg_seeds`
   (outside it), `rect` (a box around it), `object_colors` / `background_colors`.
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
