---
name: print-functional
description: Use for a functional 3D-printed part (FDM) — a bracket, a holder, a clip, a housing, a jig, a gear, a mount — that must carry load, fit other parts and print without supports. Best print practice plus strength.
---

# Functional printed parts (FDM)

Use with mechanical-design (bought parts, fasteners, assemblies) and model-a-part (building it); fits from
fits-and-tolerances ("printed fits").

## Orientation first — it decides the strength
- Decide how it lies on the bed **before** modelling: the biggest flat face down, no supports. Layers are weakest
  across (≈ 50–70 % of the strength along them): a load that pulls layers apart is the one that breaks it — turn
  the part so the main load runs along the layers (a hook printed lying down, not standing).
- Holes along Z (printed upright) are round and exact; holes across Z sag at the top — give them a teardrop
  (`add_feature` hole `teardrop: true`: a 45° point on top, the Ø stays) or make them smaller than 8 mm, or drill them after.

## Shape rules
- **Walls** ≥ 3 perimeters for load (≈ 1.2–1.6 mm with a 0.4 nozzle; 2–3 mm for screws and load paths), never thinner
  than 0.8 mm. Wall thickness a multiple of ≈ 0.4–0.45 mm prints clean.
- **Overhangs** ≤ 45° (chamfers instead of fillets on downward edges), **bridges** ≤ 10–20 mm. A **chamfer 0.4–0.6
  mm** on the bottom edges (elephant foot), fillets on top and on vertical edges.
- **Corners that carry load**: fillet r ≥ 1–2 mm (a sharp inner corner cracks), **ribs** 0.5–0.8 × the wall,
  gussets in brackets instead of thicker plates.
- **Thin features**: pins / posts ≥ 4 mm Ø (or a metal pin from the library), snap-fit arms long (L ≥ 10 × t) with
  the bend along the layers, strain ≤ 2–3 % (PLA) / 4–5 % (PETG).
- **Screws into plastic**: a heat-set insert (library ruthex: hole as the item says, wall ≥ 1.6 mm), a nut in a hex
  pocket (s + 0.3), or a thread-forming screw into a core hole ≈ 0.8 d — never a cut thread below M6.
- Text / labels: embossed or engraved ≥ 0.6 mm deep, strokes ≥ 0.6 mm.

## Material (say it, set it with `set_material {…}`)
- **PLA**: stiff, easy, indoors below ≈ 50 °C. **PETG**: tougher, a little flexible, up to ≈ 70 °C — the usual
  choice for functional parts. **ASA / ABS**: outdoors, warm (≈ 90 °C), warps — needs an enclosure. **PA / CF**: strong,
  wear, hard to print. Strength: more perimeters help more than more infill (4 walls, 30–40 % gyroid for load).

## Check before you say it is done
- `get_model` (every step ok), `get_screenshot` from below and the side: no overhang over 45° without a reason.
- `check_print {…}`: it fits the printer; big parts split (print-prep).
- In an assembly: fits with the bought parts (no collisions, the clearances above), the moving parts free.
- Tell the user the orientation, the material, walls / infill and which sizes to adjust after a test print.
