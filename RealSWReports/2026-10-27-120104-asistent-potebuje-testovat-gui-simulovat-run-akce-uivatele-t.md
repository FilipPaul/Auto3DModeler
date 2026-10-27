# Asistent potřebuje testovat GUI: simulovat ruční akce uživatele (tah, posuvníky, tlačítka)

- **Date:** 2026-10-27 12:01:04
- **Reported by:** the AI agent (MCP report_problem)

## What happened

Asistent přes MCP nevidí ani neovládá GUI. Pracuje jen přes API nástroje (move_free, edit_joint…), které se můžou chovat jinak než ruční ovládání. Příklad z této session: move_free na rameno s zamčenou souosou vazbou správně odmítne pohyb (fully held), ale ruční tah v aplikaci rameno otočí, i s locked:true. Asistent tu chybu sám nenašel, objevil ji až uživatel. Asistent taky neví, jaká tlačítka v GUI jsou (uživatel se ptal na tlačítko kontroly kolizí a asistent nemohl odpovědět jistě).

## What was expected

MCP nástroje pro test GUI:
1) gui_state: seznam viditelných ovládacích prvků aktuálního panelu (tlačítka, posuvníky, vazby v seznamu, jejich stav a popisky), aby asistent mohl uživateli přesně říct, kde co je.
2) gui_action: simulovat ruční akce stejnou cestou jako myš nebo klávesnice: klik na tlačítko podle id nebo popisku, tah dílu v 3D (part, směr nebo úhel), posun posuvníku pohonu, free-move u vazby.
3) Výsledek akce: nový stav sestavy (pozice, úhly) a screenshot, aby šlo porovnat, co dovolí GUI a co API.
Asistent pak může po každé změně ověřit chování v GUI a nesoulad mezi GUI a API reportovat sám, dřív než ho najde uživatel.

## Steps

Session 2026-10-27: sestava „Mechanismus – rameno na ložisku“. Uživatel ručně otočil ramenem přes Concentric J3, i když vazba měla rotation_locked:true a locked:true. Přes API to reprodukovat nešlo.

## Workaround

Uživatel testuje GUI ručně a hlásí asistentovi, co vidí.

## Resolved

2026-10-27 (0.9.0): new tools gui_state (every visible control: its number, label, tooltip, state, greyed out; in the
top bar, the workspace's toolbar or the panels — not the chat) and gui_action (a click, or a slider / box / choice set
to a value, as the mouse does; a greyed control is refused). Dragging in the 3D view is not simulated yet.
tools/e2e_assembly_lever.py.
