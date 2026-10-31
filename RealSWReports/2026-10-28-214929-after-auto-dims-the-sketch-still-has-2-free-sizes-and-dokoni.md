# After Auto-dims the sketch still has 2 free sizes, and 'Dokončit skicu' still says some sizes are free

- **Kind:** bug
- **Date:** 2026-10-28 21:49:29
- **App version:** 0.9.0 (main @ fe12e22, 2026-10-28)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

On a clean sketch (a rect plus an overlapping slot), clicking 🪄 Automatické kóty still left two 🔓 'Volné' rows in the panel, and the tooltip of ✓ Dokončit skicu still said 'Některé rozměry jsou ještě volné'. After that, get_model showed 14 locked sizes for 2 simple shapes. That looks like too many: a rect needs 4 and a slot needs 5. Also, finishing the sketch changed the volume slightly (59942.538 → 59942.76).

## What was expected

After auto-dims the sketch is fully defined: no free rows, the Finish tooltip says it is fully defined, and there are no extra (redundant) locks. The geometry does not move when the sketch is finished.

## Steps

edit_feature F1 shapes [rect, slot] → extrude → double-click the sketch → 🪄 Automatické kóty → gui_state panel (2× 🔓 Volné) → Dokončit skicu → get_model locked_sizes 14.
