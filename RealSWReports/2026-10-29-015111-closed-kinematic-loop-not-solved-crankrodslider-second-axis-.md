# Closed kinematic loop not solved (crank–rod–slider): second axis joint overrides the first

- **Kind:** bug
- **Date:** 2026-10-29 01:51:11
- **App version:** 0.9.0 (main @ 63d5c3a, 2026-10-28)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

Assembly "Klikový mechanismus": crank I3 turns in bearing (J3 axis + J4 touch), rod I4 on crank pin (J5 axis + J6 gap), slider I5 in a groove (J7 touch floor + J8 touch side = free along X). Adding J9 (rod's 2nd eye axis onto slider pin) makes J5 not_held ("J9 holds Ojnice elsewhere"), the rod is solved from J9 only. move_free I3 by 90° turns the crank, but the slider stays and the rod swings about the slider pin, 198 mm off the crank pin.

## What was expected

Joints forming a closed loop are solved together (a 1-DOF crank-slider): turning the crank moves the rod and slides the slider (x = r·cosθ + √(L² − r²sin²θ)); get_assembly reports the mechanism's single free motion; check_travel / ▶ play it through a full turn.

## Steps

snap_faces J1..J8 as above, snap_faces {move: I4 F2:side:c4, onto: I5 F4:side:c1, type: axis}; move_free I5 +17.5 (both joints consistent at 0°); move_free I3 motion 0 amount 90; get_assembly -> J5 not_held 197.99 mm.

## Workaround

Remove J9 and leave the slider free along X; positions set by hand per crank angle.
