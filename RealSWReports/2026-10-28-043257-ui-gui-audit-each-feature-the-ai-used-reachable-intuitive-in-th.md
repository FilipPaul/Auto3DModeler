# GUI audit: each feature the AI used — reachable / intuitive in the 3D model workspace

- **Kind:** ui
- **Date:** 2026-10-28 04:32:57
- **App version:** 0.9.0 (main @ 5f7e65b, 2026-10-28)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

Checked with gui_state / gui_action on "Test – úhelník" every feature used through the API (sketch, offset plane, rect, slot, polyline, profile smooth/arc, extrude add/cut/through/symmetric/flip, hole, pattern linear/circular, mirror of a step, decal, fillet, chamfer, revolve, sheet).
OK in the GUI: Sketch on Top/Front/Right or a face + "↕ Plane at mm" offset; Rectangle, Line, Circle, Spline, Arc, Round corner, Mirror, Offset, Trim, Extend, Relations, Dimension; Extrude (Add / Cut, Distance / Up to a face, Through all (only with Cut), Both sides, ⇅ Flip); Hole (Ø, Through all, ISO fit); Pattern (In a row / Around, count, spacing, X/Y/Z, ⇄); Mirror (body / a step, YZ/XZ/XY, copy / move); Fillet (r, Drop all edges); Revolve, Loft, Sweep, Shell, Text / picture, Material, Tolerances, Drawing sheet.
PROBLEMS:
1) BUG: in the Extrude dialog the bottom "Cancel" (n60, no tooltip) closes the dialog but leaves the WHOLE toolbar greyed out; only Escape / the other "Cancel" ("Stop this…") frees it. Two Cancel buttons in every feature panel (58 + 60) — confusing.
2) No Slot tool in the sketch toolbar (the API has {slot}); users must draw 2 lines + 2 arcs + relations.
3) Offset plane "↕ Plane at mm": no hint which way + goes (Front +20 went to y = −20); show an arrow on the plane.
4) Extrude: the "Sketch" choice shows ids (F9) instead of names (Žebro) and pre-selects a sketch already used by an extrude; Pattern "Repeat" also shows ids (F12) and defaults to the last step (a text decal) instead of the last hole/cut; Pattern takes only ONE step (API takes a list).
5) Hole: only Ø + through + fit. No exact position fields (u/v or distance from edges — the API has from: {edge, d}), no counterbore / countersink / thread, no standard sizes (M3/M4/M5 clearance, tap drill).
6) Mirror across a face is only in the tooltip — no visible "pick a face" control.
7) Fillet / Chamfer: no count of picked edges, no "all edges of a face / tangent chain"; a click in the view doesn't say what it picked.
8) The "Measure catches" snap filters (Corners / Edge midpoints / Centres) show in every feature panel even when Measure is not on — clutter.
9) The step tree (history) is not in gui_state — cannot check rename / reorder / suppress from the GUI side; the API's turn_off_feature and step names should be visible there.
10) Default step names "Extrude 1", "Pattern 1": take the sketch's name ("Extrude – Drážka").

## What was expected

Single Cancel that always restores the toolbar; Slot tool; direction arrow for offset planes and extrude; names instead of ids in choices with sensible defaults; multi-step pattern; hole position fields + counterbore / thread / M-size presets; visible face option for mirror; edge count + chain selection; snap filters only with Measure; step tree in gui_state.

## Steps

gui_action ✏ Sketch → Front (inspect) → ✕ Cancel; ⬆ Extrude → ⬇ Cut → Cancel (n60) → toolbar disabled → Escape fixed it; ◎ Hole; ⁂ Pattern; ⇋ Mirror; ◜ Fillet + click in view; gui_state each time.

## Workaround

Escape to unlock the toolbar.
