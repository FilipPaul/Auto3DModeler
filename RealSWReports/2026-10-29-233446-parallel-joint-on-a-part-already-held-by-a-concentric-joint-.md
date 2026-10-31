# Parallel joint on a part already held by a concentric joint moves it off that axis (J7 not held, 24.7 mm)

- **Kind:** bug
- **Date:** 2026-10-29 23:34:46
- **App version:** 0.9.0 (main @ 92d0e37, 2026-10-29)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

Assembly "Robotické rameno": I5 (sub-assembly "Sestava 2") hangs on I4 by J7 axis (I2/F2:side:c1 onto I4 F5:side:c2, distance -27, turn free). Adding a parallel joint I5 I2/F2:side:l3 ∥ I4 F2:side:l3 (faces only 1.976° off parallel) moved I5 so that J7 reported not_held, 24.73 mm off. Same via the GUI path.

## What was expected

A parallel joint only removes rotation: it should turn the part about its existing free axis (J7) by the 1.98° needed and keep the concentric joint held, like SolidWorks' parallel mate.

## Steps

snap_faces {type: parallel, move: {part: I5, face: "I2/F2:side:l3"}, onto: {part: I4, face: "F2:side:l3"}} -> get_assembly J7 not_held 24.73 mm.

## Workaround

Undo; measure the angle (1.976°), then edit_joint J7 {angle: 1.976, lock_rotation: true}. The faces are now parallel at 180° and J7 holds.
