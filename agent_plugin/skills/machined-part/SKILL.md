---
name: machined-part
description: Use for a part that will be CNC milled or turned (aluminium, steel, POM, PEEK, FR4 plates, blocks, shafts, fixture plates) — the simplest manufacturing: stock sizes, tool radii, standard drills and threads, few set-ups, only functional tolerances, materials and finishes — and how to model each rule in this app.
---

# A machined part that is cheap to make

Use with design-principles (intent) and model-a-part (tools); fits in fits-and-tolerances. Default: the simplest
part that works — 2.5D milled from one side, from standard stock, ISO 2768-m.

## 1. Stock first
- **Plate thickness = a stock size**: Al 3 · 4 · 5 · 6 · 8 · 10 · 12 · 15 · 20 · 25 mm; steel 2 · 3 · 4 · 5 · 6 · 8 ·
  10 mm; POM / PEEK sheets 5 · 6 · 8 · 10 · 12 · 15 · 20 mm; FR4 / G10 1.6 · 3 · 5 · 6 · 8 · 10 mm. A plate left at
  stock thickness is only contoured — cheapest. Flatness-critical: precision cast plate (EN AW-5083, ± 0.1 mm, no
  facing) or 1–2 mm over and faced.
- Round bar Ø 6 · 8 · 10 · 12 · 16 · 20 · 25 · 30 · 40 · 50 mm: a turned part's largest Ø = bar Ø − 1 or the bar as is.
- Base extrude `d` = the stock (a parameter `t_plate` when shared); overall outline on whole mm.

## 2. Milling rules → how in the app
| Rule | Number | In the app |
|---|---|---|
| Inner vertical corner radius ≥ the cutter's | Ø6 cutter → r ≥ 3 (better 3.5); Ø10 → r ≥ 5; small pockets Ø4 → r 2 | pocket sketch `{rect: {x, y, w, h, r: 3.5}}`, or `fillet` the pocket's vertical edges (`find_refs {kind: "edge", of_step: "<pocket id>"}`) |
| Pocket / slot depth | ≤ 3 × cutter Ø (≤ 4 × with a long cutter) | extrude cut `d`; deeper → a bigger r or a through cut |
| Slot width | a cutter Ø (6 · 8 · 10 · 12), depth ≤ 3 × width | `{slot: {x1, y1, x2, y2, w: 8}}` + cut |
| Pocket floor corners | sharp is fine (flat end mill); r 0.5 only if asked | nothing |
| Walls | Al ≥ 1 mm (≥ 2 mm next to a deep pocket), plastics ≥ 2 mm; height ≤ 8 × wall (Al), ≤ 4 × (plastic) | check with `measure {a: {face}, b: {face}}` |
| No undercuts, no sharp inner corners, no 3D surfaces | — | revolve / loft only on turned parts |
| Features from ≤ 2 sides | top (+Z) first; bottom only for what must be there | count set-ups below |

## 3. Holes and threads
- Holes as hole steps with a standard, never sketched circles: `add_feature {type: "hole", face, points,
  standard: "M4", shape: "plain" | "counterbore" | "countersink", thread: true}`. Plain Ø: a standard drill
  (whole and half mm; 3.3 · 4.2 · 5 · 6.8 · 8.5 · 10.2 for taps). Hole depth ≤ 10 × Ø.
- Tap drills: M2 1.6 · M2.5 2.05 · M3 2.5 · M4 3.3 · M5 4.2 · M6 5.0 · M8 6.8 · M10 8.5 · M12 10.2 (clearance and
  counterbore table: fits-and-tolerances).
- Thread length: Al 1.5 d (2 d where it is opened often — or a helicoil, materials-and-strength), steel 1–1.5 d.
  A blind thread: `through: false, depth:` thread + ≈ 0.5 d run-out (M4: 6 + 2 = 8); through where the plate allows
  it (no blind tapping, no chips).
- Dowel / bearing holes only: `fit: "H7"` (modelled at nominal Ø) — everything else is ISO 2768-m.
- Counterbores from the side the screw comes from; avoid counterbores on the second side when possible (a set-up).

## 4. Tolerances and edges
- `set_material {material, tolerance: "m"}` — ISO 2768-m in the title block for all sizes without their own.
- A size gets its own tolerance only when the function needs it (a fit, a locating distance between dowels ± 0.02,
  a sealing depth); say why in the step's name.
- Edges: no modelled chamfers everywhere — the drawing note "Edges broken ISO 13715 −0.3" covers them
  (production-drawing). Model only functional chamfers: lead-ins on guide holes (0.5–1 × 45°), on PCB support edges,
  edges a hand slides along (1 × 45°): `add_feature {type: "chamfer", edges, d: 1}`.

## 5. Set-ups — count and reduce
- One set-up per direction of the faces that carry features (`get_model` / `find_refs {kind: "face", normal: …}`).
  A plate with everything from the top: 1 (+ contour). Holes from the side: +1 each side — prefer through holes from
  the top, or put the side holes on one side.
- Turned parts: all diameters from one end when possible; keyways / cross holes are a milling set-up.
- Report it: "1 set-up from the top, 1 from the bottom (2 counterbores) — move them up?"

## 6. Materials (set_material value in brackets; name the grade in the drawing note)
| Material | Use |
|---|---|
| AlMg3, EN AW-5754 (`aluminium`) | plates, covers, sheet; good corrosion, anodises well |
| EN AW-6082-T6 (`aluminium`) | general structural parts, profiles, brackets |
| EN AW-5083 cast plate (`aluminium`) | flat, stress-free fixture base plates |
| EN AW-7075-T651 (`aluminium 7075`) | highly loaded small parts, thin levers |
| POM-C (`POM`) | guides, sliders, PCB supports, insulating parts; machines very well |
| PEEK (`PEEK`) | hot (> 100 °C), ESD versions for PCB contact |
| FR4 / G10 (`FR4 (PCB)`) | probe plates, insulating plates (drills well, abrasive) |
| 1.4301 (`stainless steel`) | pins, food / wet areas; slow to machine — only when needed |
| S235 / C45 (`steel`, `steel C45`) | frames (S235), shafts and pins (C45) |

## 7. Finishes
- Al: clear anodising E6/EV1 10–15 µm (the layer grows ≈ half outward: Ø H7 bores and threads masked or toleranced
  for it); hard anodising 25–50 µm for wear; black for optical parts. Steel: zinc plated or blackened; stainless:
  none. POM / PEEK / FR4: none.
- Write the finish into the drawing note; say it in your summary ("AlMg3, clear anodised").

## Check before hand-over
`get_model` all ok; every pocket corner r ≥ the cutter's; every hole a standard step; plate thickness from §1;
set-ups counted; then a drawing (production-drawing).
