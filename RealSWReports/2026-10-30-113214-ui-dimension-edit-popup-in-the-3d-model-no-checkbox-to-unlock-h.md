# Dimension edit popup in the 3D model: no checkbox to unlock / hide the dimension

- **Kind:** ui
- **Date:** 2026-10-30 11:32:14
- **App version:** 0.9.0 (main @ c043d7d, 2026-10-30)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

The user clicked a dimension label in the 3D model view (Rameno, the 🔒 16 length label). The popup "Délka" that opens has only the value box, a slider, OK / Zrušit / ↺ 16. The user expected to be able to un-check the dimension right there and could not (recording: click on the label, click in the popup, OK). Today, unlocking a size or hiding a single dimension cannot be done from this popup at all.

## What was expected

The popup should have a checkbox row under the value: ☑ 🔒 Zamčeno (when unchecked the size is free / a reference that only measures, as sketch_dim locked:false does; the 🔒 on the label goes away) and ideally ☑ Zobrazit (when unchecked the dimension is hidden in the view; the 'Vše' filter can bring it back). The change should go in at once, or with OK, and Ctrl+Z should undo it.

## Steps

Model "Rameno", Rozměry: Vše → click the 🔒 16 label under the plate → the popup Délka [16] mm, slider, OK / Zrušit / ↺ 16: there is no lock or show checkbox.

## Workaround

None in the GUI from this popup. The AI can unlock a size with sketch_dim {locked:false}.
