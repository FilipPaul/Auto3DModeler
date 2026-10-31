# Suggestion '⚙ Ovládat mechanismus' does nothing visible when the Mechanismus widget is already open

- **Kind:** ui
- **Date:** 2026-10-30 11:24:02
- **App version:** 0.9.0 (server started at main @ a059fa4, 2026-10-30; checkout now at c043d7d — restart the app to run it)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

In the assembly 'Otočné rameno s kabelem' the suggestions row ⚙ Ovládat mechanismus (rank 1) was clicked: no toast, no change on screen. The ⚙ Mechanismus widget was already open, docked low in the left panel (under Sestava and Projekt), so the user thinks the button does nothing. Moreover the mechanism was half broken: joint J1 'rameno na čepu' is broken (its hole face F8:hole:0 is gone after Hole 2 was edited: Ø16 → M3 counterbore elsewhere, which also fails) — the arm then also slides in X/Y, and nothing told the user while driving it.

## What was expected

The row should bring the widget to the user: scroll / unfold it, briefly highlight it (pulse 2 s) and focus its slider; if it is folded or hidden, open it. When the mechanism has a broken joint, the widget should say so (⚠ 'vazba rameno na čepu nedrží — plocha díry zmizela') with a link to the joint.

## Steps

gui_action {suggest: 'Ovládat mechanismus'} in the assembly with the widget open → nothing changes (screenshot: widget at the bottom left, unchanged). get_assembly: J1 broken: true, I2 free also 'Posuv podél X/Y'.
