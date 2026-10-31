# Cable harness GUI: points can't be placed exactly (no point list, no coordinates, hidden faces, clicks land off-axis)

- **Kind:** ui
- **Date:** 2026-10-30 00:38:24
- **App version:** 0.9.0 (main @ 92d0e37, 2026-10-29)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

Re-routing 'Svazek 1' on a robot arm so the cable crosses each joint ON its axis (pin tops / a hole through the pin): (1) the harness panel shows only 'Body 7' — no list of points (which part / face / xyz), so you can't see or edit a single point; (2) the only way to drop old points is '↶ Odebrat poslední bod' clicked 7× — no 'clear all' / delete one from a list; (3) a click on a pin's top lands where clicked: on an annular face (pin with a cable hole) it sits on the rim, 5 mm off the axis, so the length changes as the joint turns (139.6 → 142.8 mm over a turn); (4) faces underneath (the groove on the base's bottom, the inside of the axis hole) are 'not in sight' — no way to start the cable in the base's bottom groove; (5) dragging a point (as the hint says) to snap it to the hole centre did not work; (6) through_parts says which part but not where (which segment / at which point), so finding the clash is guessing; (7) on ✎ Upravit body the length label jumped 145 → 206 mm before anything changed; (8) English text in the Czech UI: 'Click the edge (or another hole) to measure the ↔ distance from…', '↕ mm in the middle of the lower and upper edges'.

## What was expected

A points list in the harness panel (part, face, x/y/z editable, ✕ per row, ↑↓ order), 'on the axis' snapping for round faces / annular faces (centre of a pin top, hole centre), a 'point at the centre of this hole/face' row in the suggestions, a view from below / section to pick hidden faces, and through_parts per segment with the clash point shown in the view.

## Steps

Assembly Robotické rameno → Svazek 1 → ✎ Upravit body → ↶ ×7 → clicks on I1 F4:end, I2 F8:hole:0, I2 F5:end, I3 F8:hole:0, I3 F5:end → Hotovo; drive M1 88→270, M2 -103→0→110

## Workaround

Picked pin tops by name (gui_action pick); accepted the base point on the pin rim.
