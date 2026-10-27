# Concentric joint on a library screw: no free motions (free: []), Moves empty

- **Date:** 2026-10-27 12:42:48
- **App version:** 0.9.0 (main @ 4d79ca0, 2026-10-27)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

User added ISO 4762 M1.6×5 (I4, library part P8) and joined it with a concentric joint J5 (axis, I4 F2:side:l2 onto I1 Stojan s čepem F8:side:c1, distance null, rotation free). The axis holds (measure: axes_apart 0). But get_assembly gives I4 free: [] and at: [], and it is not fully_held either. The GUI 'Moves' section is empty, and move_free I4 fails with 'motion is one of: .' (an empty list). Running edit_joint J5 distance null, lock_rotation false again changes nothing. For comparison, the bearing I2 (also a library part) on its axis joints does get its free turn.

## What was expected

One axis joint with distance null and rotation free leaves two free motions: sliding along the axis and turning about it. Both should be listed in free / Moves and work with move_free.

## Steps

User: library ISO 4762 M1.6×5 into the assembly, Joint ▾ Concentric, screw shank → Ø8 round face of Stojan s čepem. AI: get_assembly (I4 free []), measure I4 F2:side:l2 / I1 F8:side:c1 (axes 0), move_free I4 amount 5 → error 'motion is one of: .', edit_joint J5 distance null → still free [].

## Resolved

2026-10-27 (after 0.9.0 @ 4d79ca0): the joint J5 had `flip: true` (⇅). A concentric joint's flip was taken against
the way the part lay at that moment, so every hold turned the screw over again: it never settled, and none of its
ways could be told (3 "ways", none known). Now a concentric joint keeps the way round its part is, and ⇅ turns the
part over once. The user's project: the screw has its two ways again (along the axis, about it).
tools/e2e_assembly_lever.py (⇅ on a lone concentric joint: over once, its 2 ways stay).
