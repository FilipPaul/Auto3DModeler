# Ani locked:true na souosé vazbě nezabrání ručnímu otočení dílu

- **Date:** 2026-10-27 12:00:02
- **Reported by:** the AI agent (MCP report_problem)

## What happened

Navazuje na report „Zamčená souosá vazba (lock_rotation) jde v aplikaci ručně otočit“. Na J3 (I3 rameno → I2 ložisko, axis, rotation_locked:true) jsem zapnul edit_joint locked:true. Odpověď edit_joint pole locked nevrací. Uživatel ramenem v aplikaci dál ručně otáčí kolem J3 a ložisko se nehýbe.

## What was expected

Po locked:true (a už po rotation_locked:true) se díl ručně kolem vazby otočit nedá. edit_joint a get_assembly mají stav locked vracet.

## Steps

edit_joint {id: J3, locked: true} → odpověď bez pole locked; uživatel táhne rameno v UI → rameno se otáčí vůči ložisku.

## Resolved

2026-10-27 (0.9.0): a locked 🔒 joint's row is greyed out (its gap, ↻ slider, free / locked, ⇅ — only 🔒 still
works), edit_joint refuses to change a locked joint (unlock it first), and edit_joint / get_assembly give
`locked: true`. tools/e2e_assembly_lever.py.
