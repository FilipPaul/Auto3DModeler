# gui_action: value on a button clicks it (control numbers shift with selection); undo of "Make it its own part" leaves th

- **Kind:** bug
- **Date:** 2026-10-29 01:56:35
- **App version:** 0.9.0 (main @ 63d5c3a, 2026-10-28)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

1) gui_state (bearing I2 selected) listed n=63 as the motion slider. After gui_action {control: "Klika I3"} the panel was rebuilt and n=63 became the button "⧉ Udělat z něj vlastní díl". gui_action {control: 63, value: 90} clicked that button (answer: 'button “⧉ Udělat z něj vlastní díl” = 90') — I3 got a copied part "Klika (kopie)" (P8). 2) undo put I3 back on P2, but P8 "Klika (kopie)" stays in the project, used nowhere.

## What was expected

1) A value given for a button / checkbox is refused ("n 63 is a button, not a slider — call gui_state again"); better, gui_action answers with the fresh control list when the panel changed, or numbers stay stable per control. 2) Undo of "make it its own part" also removes the copy it created (or the copy is kept only if edited).

## Steps

Assembly Klikový mechanismus: gui_state (I2 selected, n63 = I2's turn slider) -> gui_action {control: 22} (select I3) -> gui_state panel (I3: n63 = turn slider) -> gui_action {control: "Klika I3"} -> gui_action {control: 63, value: 90} -> toast "I3 má teď vlastní díl: Klika (kopie)" -> undo -> list_parts still has P8.

## Workaround

undo; the orphan copy left in place (deleting a part only when the user asks).
