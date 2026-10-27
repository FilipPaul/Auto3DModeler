# Pevně spojený díl nejde otočit – pohyb se nepředá na díl, na kterém sedí

- **Date:** 2026-10-27 11:47:02
- **Reported by:** the AI agent (MCP report_problem)

## What happened

Rameno (I3) je na ložisku (I2) přes axis s lock_rotation:true + touch, ložisko se otáčí na čepu (axis + touch). move_free na I3 vrací „fully held — cannot move“. Pohnout jde jen ložiskem (I2) a rameno ho sleduje. Uživatel to nepovažuje za intuitivní: chce chytit za páku a točit.

## What was expected

Když je díl plně držený dílem, který se sám může pohybovat, má jít táhnout nebo pohánět i za něj. Pohyb se předá dolů řetězem (rameno → ložisko → otáčení na čepu) a zobrazí se u ramene jako jeho volný pohyb.

## Steps

snap_faces I2 axis na čep + touch na osazení; snap_faces I3 axis na vnější plochu I2 lock_rotation:true + touch; move_free I3 → chyba fully held; move_free I2 → I3 se otočí s ním.

## Workaround

Pohánět se musí ložisko (I2).

## Resolved

2026-10-27: a part fully held on one part that can still move now has that part's motions ("Turn about … — with
Bearing"): its slider, ▶, the limits and move_free move the bearing and the arm goes along. tools/e2e_assembly_lever.py.
