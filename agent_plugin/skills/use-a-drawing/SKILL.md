---
name: use-a-drawing
description: Use when the user has a 2D drawing (a DXF / DWG, or a PCB's Gerber / Excellon / ODB++ — open or as a file) and wants to look at it, change sizes in it, export it, or make a part from it (a plate with its holes, a front panel, a case for a PCB).
---

# Work with a 2D drawing

0. Not open yet: `open_file {path}` opens a DXF / DWG, a Gerber / drill file, a .zip / .tgz (a Gerber set or an
   ODB++ job) or a folder of loose Gerber files as a 📐 drawing (`as: "part"` makes a DXF a quick part instead).
1. `get_drawing {}` — its layers (shown, how many shapes; a PCB's kinds: copper, outline, holes, silkscreen …), the
   kinds of shapes, its size in mm and its units. If the size looks 25.4× or 10× wrong, the file's units are off —
   `drawing_units {units: "mm" | "cm" | "m" | "in"}` sets what one unit of the file is (ask the user when unsure).
2. Find shapes with `drawing_find {filters: [{field, op, value}]}` — e.g. the Ø8 holes on a layer:
   `[{field: "shape", value: "circle"}, {field: "layer", value: "HOLES"}, {field: "dia", value: 8}]`; a PCB's
   mounting holes: `[{field: "layer", value: "<the holes layer>"}, {field: "dia", op: "≥", value: 3}]`; thin traces:
   `[{field: "w", op: "<", value: 0.3}]`. They are selected.
3. Change them: `drawing_set_size {kind: "dia", value: 10}` (circles keep their centres), `"len"` for lines.
   Tidy it: `drawing_delete {what: "selection" | "found"}`; add lines / circles: `drawing_add {shapes: [{line: {a, b}} |
   {circle: {c, d}}], layer}` (mm).
4. Layers: `drawing_layers {only: [names]}` keeps just those (e.g. the outline and the holes of a board); also
   `drawing_layers {color: {<name>: "#rrggbb"}, new: "<name>" (new shapes go on it), active: "<name>"}`.
5. A part from it: `drawing_use {as: "sketch", what: "all" | "found" | "selection"}` makes the sketch of a new 3D
   model (on screen then): `add_feature {type: "extrude", sketch: "F1", d: 3}` — the closed outline becomes the plate,
   the circles in it its holes. For a PCB case: the board outline + the mounting holes, then design the case around
   them (skill mechanical-design). The sketch comes cleaned (ends welded, crumbs absorbed, lines / arcs joined); still
   too many shapes (get_model's shapes), or a sketch made before: `simplify_sketch {id: "F1"}` (fewer lines and arcs),
   `{op: "join"}` (each chain one smooth curve — teeth, a cam) or `{op: "outline"}` (one rigid outline); check that
   area_mm2 stayed the same.
6. Save it: `export {format: "dxf"}` writes the shown layers (in mm).
