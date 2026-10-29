---
name: print-prep
description: Use before exporting or when the user wants to 3D print the part — check it fits the printer, split it when too big, choose joints, export STL or STEP.
---

# Prepare a part for 3D printing

1. **A 3D model part**: `prepare_print` — this opens a printing copy as a quick part on the 3D print tab.
   (Make it again after changing the model.) A quick part is ready as it is.
2. `check_print` (optionally `printer: "<id>"` from the result's list) — does it fit, how many pieces.
3. Too big: `check_print {split: true}`; the user picks a joint in the 3D print tab (dovetail, puzzle,
   butterfly keys, dowels, splice plate, or glue). A model's printing copy is split exactly (smooth curved walls,
   the result says "Exact split").
4. Printability rules to mention when they matter: walls ≥ 2 perimeters (≈ 0.8–1.2 mm), holes +0.2 mm,
   overhangs ≤ 45°, bridges ≤ 10 mm, embossed details ≥ 0.4 mm, text strokes ≥ 0.6 mm. A part lies on the bed
   on its largest flat face.
5. `export {format: "stl"}` for printing (or "step" for other CAD programs) — the result names the file.

**Missing a tool?** When no tool fits and you work around it (several calls for one thing, guessing, asking the user
to click for you), file it at once: `list_reports {search: "<the words>"}`, and if it is not there
`report_problem {kind: "tool request", …}` (the tool you would want: name, inputs, result; your workaround) —
then tell the user in one line and carry on. A wrong result is `{kind: "bug"}`; each thing reported once.
