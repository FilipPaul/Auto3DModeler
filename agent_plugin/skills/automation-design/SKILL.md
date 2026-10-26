---
name: automation-design
description: Use for industrial automation designs — pneumatic cylinders and valves (SMC), sensors (SICK inductive), stepper motors, control panels with LEDs, buttons and connectors; grippers, pushers, stops, sensor brackets, motor mounts, panel layouts.
---

# Industrial automation parts (with mechanical-design)

Load mechanical-design too; this adds what automation parts need. All bought parts come from the library
(`library_search {query}`, `library_add {item, size, length}`), so the BOM has their SMC / SICK / maker numbers.

## Pneumatic cylinders (SMC CJ2 in the library)
- **Force** = pressure × area: at 6 bar a Ø10 pushes ≈ 47 N, a Ø16 ≈ 120 N (pull less: the rod area is lost). Take
  ~50 % reserve for friction and speed: choose the bore from the force needed.
- **Stroke**: the movement needed + a little; choose a standard stroke of the library item (15, 30, 45 … mm).
- Mount the CJ2 by its front thread (M8 × 1 for Ø10, M10 × 1 for Ø16) through a plate hole Ø thread + 0.3 with the
  mounting nut, or with a bracket; the rod end (M4 / M5) takes the tool. Leave the M5 ports free for fittings
  (SMC KQ2H…-M5A: ≈ Ø10–12 around them) and the tubes (bend radius ≥ 15 mm for Ø4).
- A moving cylinder rod: in the assembly the cylinder body is held (touch + axis on its mount hole), the tool on the
  rod moves along the axis — check it with `get_assembly` (free) and at both ends of the stroke with check_collisions.
- **Valves** (SMC SY3000, 10 mm wide): on a plate or DIN rail, near the cylinders (short tubes), with room for the
  connector.

## Sensors (SICK IME12 / IME18, inductive)
- **Sensing range** Sn (IME12: 4 mm, IME18: 8 mm, flush): place the steel target within ≈ 0.8 × Sn of the face.
  Inductive sensors see metal only — a printed target needs a steel plate or screw head.
- Mount by the thread through a hole Ø thread + 0.5 (M12: Ø12.5, M18: Ø18.5) in a 2–4 mm plate, two nuts (SW17 /
  SW24) clamp it: make the hole slotted (10–20 mm) when the switching point must be adjusted. Leave ≥ 35 mm behind
  the connector for the M12 cable plug and its bend.
- Flush sensors may sit flush in metal; keep other metal ≥ 1 × Ø away from the face sideways, two sensors ≥ 2 × Ø apart.

## Stepper motors (NEMA 17 / 23)
- NEMA 17: 42.3 mm square, centring boss Ø22 × 2, 4 × M3 at 31 mm; NEMA 23: 56.4 mm, boss Ø38.1, 4 × Ø5.1 at 47.14.
  A mount plate: a Ø22.2 (Ø38.3) hole for the boss, M3 clearance holes (Ø3.4) at the pattern, 4–6 mm thick printed;
  slots instead of holes where a belt is tensioned.
- Torque: 17HS19-2004S1 ≈ 0.59 N·m holding; through a GT2 pulley Ø12.7 (20 teeth) that is ≈ 90 N belt pull at best —
  plan 30–50 %.

## Control panels
- Hole sizes: APEM Q8 LED Ø8, Eaton M22 push buttons / E-stop Ø22.3, Neutrik D-size Ø24 + 2 × M3, sensors' M12
  connectors Ø16. Keep 30 mm between M22 centres (40 mm next to an E-stop), panel thickness within the part's range
  (1–6 mm for M22). An E-stop is red on yellow and easy to reach.
- Leave the depth behind the panel the library part shows (M22 ≈ 43 mm) and room for the wires.

## Check
- Joints: every part held as in reality; the moving ones keep their way free (`get_assembly` free / fully_held).
- `check_collisions` at the end positions of moving parts. Then the BOM from `get_assembly` (part numbers).
