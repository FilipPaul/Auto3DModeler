# Shell after a side cut hollows only part of the body (wrong cavity, no issue shown)

- **Kind:** bug
- **Date:** 2026-10-29 20:40:46
- **App version:** 0.9.0 (main @ 92d0e37, 2026-10-29)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

Lahvička jablko is a revolved apple (F2) hollowed out by a shell (F3, 2 mm wall, open at the neck's top). The shell alone gives 35 436 mm³. With a cut extrude from the side before it (F5, a scalloped bite, 8 or 13 mm deep), the shell reports ok but the body is 157 000–182 000 mm³. The inner face F3:inner:0 has only 4 023 mm² (the outside has ~19 000), so most of the body stays solid. With a fillet on the cut's floor, the shell fails instead ("cannot be hollowed out with that face open").

## What was expected

A 2 mm wall everywhere, following the bite inside (the cavity has a dent where the bite is), or an issue when the offset cannot be built — not ok with a mostly solid body.

## Steps

rollback to F2; sketch F4 on {datum: YZ, offset: 38} (a profile of 14 arcs); extrude F5 cut d 13 (-x); rollback end → F3 shell ok, volume 182 442 mm³, find_refs of_step F3 → inner face 4 023 mm².

## Workaround

Shell first, then the bite cut, and a plug from inside (extrude add up to the next face) to close the wall behind the bite.
