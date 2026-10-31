# Snap point previews (quadrants etc.) are shown but the mouse does not grab them – click picks the face instead

- **Kind:** bug
- **Date:** 2026-10-30 19:32:47
- **App version:** 0.9.0 (main @ 5abdf57, 2026-10-30)
- **Reported by:** the AI agent (MCP report_problem)
- **Project:** `2026-10-30-193247-snap-point-previews-quadrants-etc-are-shown-but-the-mouse-do.a3d` (open it in the app: 📂 Open ▾ › File…) — 22 part(s): Base, Plate B, Plate A, Column, Block, Shaft, L bracket, Housing (STEP), ISO 4762 M4×25, ISO 7089 M4 washer, ISO 4032 M4 nut, ISO 4762 M3×12, ISO 7089 M3 washer, ISO 4032 M3 nut, ISO 4762 M5×20, ISO 7089 M5 washer, Bearing 608-2Z, Standoff M3 MF 10 mm, Module A, Bearing block, Machine, SMC CDQ2B12-15DZ; 47 kB
- **Recording:** `2026-10-30-193247-snap-point-previews-quadrants-etc-are-shown-but-the-mouse-do.recording.json` (⏺ the user's moves: 7 events over 11 s, stopped; without screenshots)

## What happened

In the assembly "Machine" (P21), hovering over the round face of the imported STEP housing I87 (F1:f81, cylindrical Ø4.763) shows the previews of its snap points (quadrants, centre…), but clicking at/next to them does not grab the point: the click selects the face (F1:f81, cylindrical face) or a neighbouring flat face (F1:f0). Recording: 0:03 click at px [560,488] -> face F1:f81; 0:05 click at [563,471] -> face F1:f81 again; 0:09 click at [587,475] -> plane face F1:f0. None of the clicks hit a quadrant / centre point although they were shown.

## What was expected

When a snap point (quadrant, centre, midpoint, corner) is shown under/near the cursor, a click should take that point (with a pick tolerance of a few px, priority over faces), the selection / suggestions table should say "quadrant of Ø4.76 …" and offer what fits a point.

## Steps

User recording: assembly Machine (P21), part I87 Housing (STEP import). Hover the cylindrical face F1:f81 -> quadrant previews appear; click on them three times -> the face F1:f81 / F1:f0 gets selected, never the point.
