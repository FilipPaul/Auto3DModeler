# Vazba gap zamkne otáčení dílu na ose, touch ne

- **Date:** 2026-10-27 11:47:05
- **Reported by:** the AI agent (MCP report_problem)

## What happened

Ložisko I2: J1 axis na čep (rotation_locked false) + J2 typu gap (5 mm) vůči čelu osazení → get_assembly hlásí fully_held. Po změně J2 na touch (gap 0) je otáčení kolem osy znovu volné.

## What was expected

Gap mezi rovnoběžnými plochami má držet stejné stupně volnosti jako touch, tedy otáčení kolem osy zůstane volné.

## Steps

Uživatel změnil J2 na gap 5 → I2 fully_held; snap_faces touch na tytéž plochy → free: Turn about…

## Resolved

2026-10-27: a gap joint does not lock the turn (edit_joint gap 5 keeps "Turn about …" free). What locked it was the
joint's ↻ slider in the panel: sliding it locks the turn there, without telling — and the touch snapped again on the
same faces cleared that lock. Every ↻ slider now has 🔓 free / 🔒 locked next to it (click to free the turn again),
and get_assembly gives rotation_locked for flat joints too. tools/e2e_assembly_lever.py.
