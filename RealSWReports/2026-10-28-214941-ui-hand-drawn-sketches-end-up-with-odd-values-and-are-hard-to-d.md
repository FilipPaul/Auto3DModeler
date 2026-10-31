# Hand-drawn sketches end up with odd values and are hard to dimension — ideas

- **Kind:** ui
- **Date:** 2026-10-28 21:49:41
- **App version:** 0.9.0 (main @ fe12e22, 2026-10-28)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

The user drew a rect plus a slot-like outline using single lines and arcs, with tangent and equal constraints. The solver gave odd values (r 23.2155, centre y 8.94), and then auto-dims failed. The panel also shows two lists of dimension rows (shape sizes and custom dims) with no names, so the user cannot tell which row is which.

## What was expected

1) Auto-dims: round to the grid or nice values as an option ('lock to rounded values'), with a preview. 2) Recognise standard shapes (a rect, a slot, a circle) in lines and arcs and offer 'convert to slot'. 3) Show conflicts in colour on the shapes (red = over-defined, blue = free) with a list explaining why. 4) Give panel rows the name and value of the dimension, and highlight the dimension in the view on hover. 5) Let overlapping closed shapes be unioned on purpose (rect + slot), with a hint, so a user doesn't have to trace the outer outline.
