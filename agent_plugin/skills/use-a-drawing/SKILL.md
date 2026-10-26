---
name: use-a-drawing
description: Use when the user has a 2D drawing open (a DXF / DWG, or a PCB's Gerber / ODB++ opened as a 📐 drawing) and wants to look at it, change sizes in it, export it, or make a part from it (a plate with its holes, a front panel, a case for a PCB).
---

# Work with a 2D drawing

1. `get_drawing {}` — its layers (shown, how many shapes; a PCB's kinds: copper, outline, holes, silkscreen …), the
   kinds of shapes, its size in mm and its units. If the size looks 25.4× or 10× wrong, the file's units are off —
   tell the user (the drawing's panel has the units).
2. Find shapes with `drawing_find {filters: [{field, op, value}]}` — e.g. the Ø8 holes on a layer:
   `[{field: "shape", value: "circle"}, {field: "layer", value: "HOLES"}, {field: "dia", value: 8}]`; a PCB's
   mounting holes: `[{field: "layer", value: "<the holes layer>"}, {field: "dia", op: "≥", value: 3}]`; thin traces:
   `[{field: "w", op: "<", value: 0.3}]`. They are selected.
3. Change them: `drawing_set_size {kind: "dia", value: 10}` (circles keep their centres), `"len"` for lines.
4. Layers: `drawing_layers {only: [names]}` keeps just those (e.g. the outline and the holes of a board).
5. A part from it: `drawing_use {as: "sketch", what: "all" | "found" | "selection"}` makes the sketch of a new 3D
   model (on screen then): `add_feature {type: "extrude", sketch: "F1", d: 3}` — the closed outline becomes the plate,
   the circles in it its holes. For a PCB case: the board outline + the mounting holes, then design the case around
   them (skill mechanical-design).
6. Save it: `export {format: "dxf"}` writes the shown layers (in mm).
