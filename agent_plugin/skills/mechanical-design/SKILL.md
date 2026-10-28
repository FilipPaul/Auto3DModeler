---
name: mechanical-design
description: Use for any real design — a device, a mechanism, a housing or bracket for bought parts, a jig, a machine part, "design me a …". How a good mechanical designer works here: bought parts from the library first, then the printed parts around them, fits, fasteners, joints, collisions, the BOM.
---

# Design like a mechanical engineer

## 1. Understand, then decide the concept
- What must it do, carry, hold, move? The key sizes and the parts it must fit (the user's photo, a drawing, a model)?
  Ask only for what you cannot sensibly choose (e.g. the size of the thing it holds); otherwise choose and say so.
- Sketch the idea in words first: which parts are **bought** (screws, bearings, motors, sensors…) and which are
  **made** (printed). Fewer, simpler made parts are better; put functions in one part when it prints well.

## 2. Bought parts first — the library
- For every bought part: `library_search {query}` (e.g. "M3 socket", "608", "LM8UU", "cylinder 16", "inductive M12",
  "NEMA 17", "insert M3", "LED 8"), then `library_add {item, size, length}` — into the assembly (`to: "assembly"`)
  or as a model to design around (`to: "model"`). They carry their part numbers into the BOM.
- Take the real sizes from them (the library answer's description, `get_assembly` boxes), never invent a bearing's
  Ø or a cylinder's thread. A part marked `outline_only` is drawn as its envelope: keep a few mm free around it.
- Not in the library? Say so, draw a plain stand-in of its outside sizes (a box / cylinder) named after it.

## 3. Made parts — designed around the bought ones (printed in PLA / PETG unless told)
- **Walls** ≥ 1.6 mm (2–3 mm for parts that carry load), **ribs** 0.5–0.8 × the wall, **fillets** at load corners
  (r ≥ 1 mm), chamfer the bottom edges 0.5 mm (elephant foot). Avoid overhangs > 45° and bridges > 20 mm, or turn the
  part so they print flat; think of the print orientation (layers are weak across: load along the layers).
- **Holes for screws** (clearance, ISO 273 medium + print): M2 Ø2.4 · M2.5 Ø2.9 · M3 Ø3.4 · M4 Ø4.5 · M5 Ø5.5 · M6 Ø6.6.
  Counterbore for a socket head: Ø dk + 0.6, depth k + 0.3 (M3: Ø6.1 × 3.3). Countersunk 90°: Ø dk + 0.3.
- **Threads into plastic**: a heat-set insert — the hole as the library item says (ruthex M3: Ø4.0, wall ≥ 1.6 mm,
  hole 1 mm deeper than the insert); or a thread-forming plastic screw into a core hole (library: Ø ≈ 0.8 d);
  or a nut in a hex pocket (s + 0.3 mm across the flats, depth m + 0.2) / a square nut slot (s + 0.3).
- **Bearings**: a press fit seat Ø D + 0.1 … 0.15 mm for a printed hole (608: Ø22.1, depth B + 0.2), a shoulder of
  1–1.5 mm for the outer ring to rest on (not touching the shields), the shaft Ø d − 0 … 0.05 (8 mm rod for a 608).
  Linear bearings LMxUU: a seat Ø D + 0.15 with the retaining grooves free, or clamp them.
- **Fits between printed parts**: sliding 0.3 mm gap per side, a snug fit 0.15 mm, a press fit 0 … −0.1 mm (small
  pins only). Dowel pin holes Ø d + 0.1.
- **Standoffs for PCBs**: the library's M3 hex standoffs (Würth 9700LL0321) on M3 screws; PCB holes usually Ø3.2.

## 4. Assemble and check like on a real drawing
- `new_assembly`, `insert_part` / `library_add {item, to: "assembly"}`, then **joints** with `snap_faces`:
  screws, pins, shafts, bearings in holes = `axis` (concentric) + `touch` on the seat face; plates on plates = `touch`
  / `gap`. A real assembly is joined, not just placed.
- `get_assembly`: each joined part says how it can still **move** (`free`) or that it is `fully_held`. A part that
  should move (a slide, a hinge, a cylinder rod) must keep exactly that way free; a fixed part should be fully held.
- `check_collisions`: no overlaps (touching is fine). An overlap = a missing hole, a too small pocket, a wrong joint
  — fix the made part, never the bought one.
- `get_screenshot` to look at it, then say what is bought (with part numbers) and what is printed.

## 5. Hand over
- The BOM: `get_bom {assembly, mode}` (every level rolled up: total, maker, part number, mass, make / buy). Tell the
  user the assembly's **📋 BOM** shows it (Summary / Structured, ⬇ CSV / Excel).
- Name the parts and the assembly clearly (what they are), say the key sizes and why (e.g. "Ø22.1 seat for the
  608-2Z bearing").
