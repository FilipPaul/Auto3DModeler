# Two-face joint: wrong order refused ("join them the other way round") instead of swapped; Escape keeps the selection

- **Kind:** ui
- **Date:** 2026-10-29 23:34:56
- **App version:** 0.9.0 (main @ 92d0e37, 2026-10-29)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

The user wants to click face A and then Ctrl+click face B to add a joint. With the yellow face of I4 picked first, then ∥ Rovnoběžně…, then the face on I5 (which hangs on I4), the app refused: "Nespojeno: druhý díl už visí na tomto — spojte je obráceně." The user has to know which part is the parent. Other problems: ∥ Rovnoběžně ranks 13th for a flat face, below the top-8 shown. Escape in the 3D view did not clear the two-face selection. gui_action has no Ctrl+click, so the user's own Ctrl+click path cannot be tested.

## What was expected

Click + Ctrl+click in any order. The app moves the part that is free (the child) and never refuses for the order. Once two faces are picked, Parallel / Perpendicular / Angle appear among the top rows. Escape clears the selection. gui_action gets a `mods: ["ctrl"]` for clicks.

## Steps

gui_action at yellow face (I4 F2:side:l3) -> suggest "Rovnoběžně" -> gui_action at the pink plate -> toast "spojte je obráceně".
