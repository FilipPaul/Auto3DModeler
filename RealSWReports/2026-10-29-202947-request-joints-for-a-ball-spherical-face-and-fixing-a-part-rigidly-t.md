# Joints for a ball (spherical face), and fixing a part rigidly to a moving part

- **Kind:** tool request
- **Date:** 2026-10-29 20:29:47
- **App version:** 0.9.0 (main @ 92d0e37, 2026-10-29)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

A valve ball (a revolved sphere) could not be joined to the piston it rides in. snap_faces tangent refuses a sphere ("Tangent joins a round face and a flat face"), and axis needs a cylinder. After a touch joint on a cut-off flat, the ball still slid freely in X / Y. lock_motion could not lock those motions: "Nenašla se vazba, která by tento pohyb zamkla".

## What was expected

Either snap_faces type "ball" / "point" (a sphere's centre on an axis or on a point of another part), or a "rigid" joint (fix part A to part B as they are now — it moves along with B). lock_motion should also lock the in-plane slides a touch joint leaves free.

## Steps

Assembly Parfém jablko: snap_faces tangent I6 F2:side:a1 onto I3 F2:side:l1, which failed. Cut a 0.05 mm flat on the ball, touch I6 F4:start onto I3 F2:side:l1, move_free to centre it, then lock_motion I6 motion 0, which failed.

## Workaround

Cut a 0.05 mm flat on the ball, used a touch joint and centred it with move_free; the X / Y slides stay free.
