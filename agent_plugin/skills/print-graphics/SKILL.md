---
name: print-graphics
description: Use for a graphic or decorative 3D model that is printed — a figure, a toy, a sign or plaque with text, a vase, a gift, a model to look at. Best print practice for looks: smooth shapes, details that print, colours, few supports.
---

# Decorative printed models

The look matters; strength only so far as it survives handling. Build it with model-a-part (smooth `profile`
shapes and revolve for round bodies, `decal` steps for text and pictures, `set_look {…}` / `paint_faces {…}` for
colours); the brief may allow building it "any way" — then a detailed profile is fine.

## Details that print (FDM, 0.4 mm nozzle)
- Smallest feature ≈ 0.8 mm (two lines); embossed / engraved detail ≥ 0.4–0.6 mm high / deep; text strokes ≥ 0.6
  mm, text height ≥ 5 mm (bold) on a flat face. Very fine detail → resin printer (ask the user).
- Thin parts (ears, tails, beaks, leaves): ≥ 1.2–2 mm thick, rounded where they join the body.
- Smooth surfaces: smooth profiles (one B-spline face) instead of many small facets; layer lines show most on
  shallow slopes — the top of a dome prints in steps.

## Printable without (many) supports
- A flat base: cut the model flat where it stands (a flat bottom of 1/3 of its width or more so it does not tip).
- Overhangs ≤ 45°; chins, noses and arms that stick out are the problem spots — tilt them up, split the model into
  pieces that print flat (and glue / peg them), or accept supports and say so.
- Hollow big figures: `shell` with walls 1.6–2.4 mm and a hole in the bottom saves material; vases: one wall
  (vase mode) — keep the shape without overhangs over ≈ 60° and no inner details.

## Colours
- One colour per part prints on any printer; several colours: paint faces (`paint_faces {…}`) and export **3MF**
  (`export {format: "3mf"}`, an object per colour for multi-material printers) — or split into parts per colour.
- Light colours show details and layer lines; dark ones hide them.

## Check
- `get_screenshot` from several sides — the look is the result; then `check_print {…}` (size, pieces).
- Tell the user the orientation, where supports are still needed, and the colours / filaments.
