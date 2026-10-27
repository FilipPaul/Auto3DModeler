# Zamčená souosá vazba (lock_rotation) jde v aplikaci ručně otočit, díl pod ní se nepohne

- **Date:** 2026-10-27 11:58:39
- **Reported by:** the AI agent (MCP report_problem)

## What happened

Rameno I3: J3 axis na vnější plochu ložiska I2 s rotation_locked:true + J4 gap. get_assembly hlásí I3 fully_held. Uživatel přesto v aplikaci „free-movem“ otočil rameno kolem J3 (Concentric) a ložisko I2 se neotočilo: I2 zůstalo na −90°, bbox ramene ukazuje, že je pootočené zhruba o 40° vůči ložisku. move_free přes MCP na I3 tentýž pohyb správně odmítá (fully held).

## What was expected

Když je otáčení ve vazbě zamčené, ruční tah v aplikaci nesmí díl kolem té vazby otočit. Buď se pohyb předá řetězem (otočí se ložisko i s ramenem, viz report o předání pohybu), nebo se díl nepohne. Ruční pohyb nemá vazbu porušit, ani bez nastaveného locked.

## Steps

snap_faces I3 F6:side:c1 → I2 F2:side:l2 axis lock_rotation:true; snap_faces I3 F6:end → I2 F2:side:l3; uživatel v UI táhne rameno nebo používá free move u J3 → rameno se točí, ložisko stojí.

## Resolved

2026-10-27 (0.9.0): the ↻ slider of a joint sets the angle its turn is locked at (against the other part) — that is
what turned the arm against the bearing. Its tooltip now says so, and to turn both the arm's Moves now drive the
bearing ("Turn about … — with Bearing", see the lever report). tools/e2e_assembly_lever.py.
