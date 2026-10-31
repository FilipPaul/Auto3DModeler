---
name: design-principles
description: Use before the first sketch of any part or assembly a person will change or have made (automation, test fixtures, machine parts, functional prints). Design intent — origin and datums, dimensions from functional faces, one idea per sketch, parameters, step names and order, mirror / pattern, robust references — so a changed size changes the part the right way. The tool calls are in model-a-part.
---

# Design intent: a part that is easy to change

Build the part the way its function defines it. A colleague opens it in a year, changes the plate width or the
hole pitch in one place, and everything follows. Tool mechanics: model-a-part (do not repeat them here).

## 1. Datums first, then the origin on them
- Before sketching, name the functional datums: **A** the face it is mounted on, **B / C** the edge or the dowel
  pins that locate it, the axis of the bore that matters. Every important size is measured from them — as the
  drawing will be (production-drawing) and as the machinist will measure.
- Put the origin on them: the mounting face on XY (z = 0); a symmetric part centred on the origin (symmetric about
  YZ and XZ); a turned part's axis on the origin (revolve on `"XZ"`, axis `"y"`).
- Base shape centred (`{rect: {x: -w/2, y: -h/2, w, h}}` with numbers or parameters) or from the datum corner
  (x = 0, y = 0) — never floating at arbitrary coordinates.
- Mid-plane extrude (`symmetric: true`) only when the mid-plane is the datum (a lever, a rib); a plate grows up
  from its mounting face.

## 2. Order of the steps
1. **Base body** — one sketch + extrude / revolve: the stock shape (plate, block, bar).
2. **Main functional features** — pockets, bosses, steps, slots: each its own sketch + extrude (cut / add).
3. **Holes** — `add_feature {type: "hole", standard: "M4", …}` steps, then their pattern / mirror.
4. **Fillets and chamfers last** (pocket corner radii may live in the pocket sketch: `rect` with `r`).
5. Text (`decal`) at the very end.
A step that must come earlier later: `rollback {to: "<id>"}`, add it, `rollback {to: "end"}` (change-a-model).

## 3. One idea per sketch, few sizes
- A sketch is one rectangle, circle, slot or simple L: 2–4 sizes. A plate with a pocket and six holes is at least
  four steps (plate, pocket, hole, pattern), not one detailed outline.
- Holes are hole steps, not circles in the base sketch — they carry standard, thread, fit and become callouts.
- Round numbers: whole mm (0.5 mm where needed); pitches as the bought part dictates (a sensor's 2 × M3 at 22 mm).
- Exception: when the brief says "any way that reaches the goal", one detailed profile is fine; still keep its key
  sizes locked and named.

## 4. Dimension from the functional datums
- Hole positions from the datum edge or pin, not from the face centre when the face may grow:
  `from: [{x: {edge: <ref>, d: 10}, y: {edge: <ref>, d: 8}}]` or `origin: "corner"`; a hole on the centre line:
  `from: [{x: {mid: [<edge>, <edge>]}}]` — it stays centred when the part gets wider.
- Holes that must match another part: one from the datum, the rest as a pitch (pattern `spacing`) — the pitch is the
  functional size, the mating part has the same parameter.
- A feature that follows another: `up_to` / `upto_next` (a boss up to the plate above), a sketch on
  `{face, mid: <face across>}` (a centred rib), a hole `from: [{x: {axis: <round face>, d}}]` — never a typed number
  that only matches today's sizes.
- `lock: true` on hole positions the user gave as sizes, so a drag in the GUI cannot move them.

## 5. Parameters for shared sizes
- A size used by ≥ 2 steps or ≥ 2 parts (plate thickness, PCB size, pitch, probe grid, screw size) →
  `set_parameter {name: "t_plate", value: 10}` and expressions in the steps (`d: "t_plate"`, `spacing: "pitch"`,
  `depth: "t_plate - 2"`). Derived sizes as expressions, not as second parameters.
- Short names that say what it is: `t_plate`, `pcb_w`, `pcb_h`, `pitch`, `grid`. Do not make parameters for sizes
  nothing else uses.
- Read `set_parameter`'s answer: every part rebuilt ok, volumes plausible.

## 6. Name the steps
- Give `name` on add_feature (later `edit_feature {id, fields: {name}}`) to every step whose purpose is not obvious:
  "PCB pocket", "Ø4 H7 dowel holes", "4× M4 mounting", "Probe field". Put a fit or a bought part in the name
  ("Ø22 H7 — 608 bearing").
- Name the parts and assemblies by what they are ("Probe plate", "Top plate"), never "Part 3".

## 7. Repeat and mirror — do not copy
- One hole / boss / pocket + `pattern` (linear `dir`, `spacing`, `count`; circular `axis`, `count`). Change the count
  and the copies follow.
- A symmetric part: model the half that carries the idea and `mirror` (`plane: "YZ"`), or mirror single steps
  (`of: "<id>"`) — only when the halves must stay equal.
- Equal parts in an assembly: `insert_part` the same part again (one part, n placements; the BOM counts them).
  `duplicate_part` only for a part that will differ.

## 8. Robust references
- Faces and edges only from `find_refs` (by normal, extreme, feature, near), never guessed names.
- Reference the base body and datum planes rather than small late features; do not sketch on a face a later step
  removes; do not build on a filleted edge.
- After every change `get_model`: all steps `ok`, no broken references. Repair the reference (`edit_feature`)
  instead of deleting and redrawing.

## 9. Prove it is easy to change
Before hand-over flex it: change the one or two sizes the user will most likely change (`set_parameter` or
`edit_feature`), check `get_model` (all ok) and `get_screenshot`, then `undo`. Tell the user the parameters and
steps that drive the part ("t_plate = 10, pitch = 2.54 — change them in 𝑥 Parameters").
