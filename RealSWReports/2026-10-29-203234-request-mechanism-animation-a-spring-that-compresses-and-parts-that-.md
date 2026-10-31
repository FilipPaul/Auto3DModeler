# Mechanism animation: a spring that compresses, and parts that follow the motion's direction (valve balls)

- **Kind:** tool request
- **Date:** 2026-10-29 20:32:34
- **App version:** 0.9.0 (main @ 92d0e37, 2026-10-29)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

Pump assembly Parfém jablko (pumpička: piston, TPU spring, 2 valve balls). In the mechanism animation (⚙ Mechanism, the driver "Zmáčknutí tlačítka" 14 … 17 mm) three things cannot be shown:
1) The spring is a rigid part. When the button is pressed it does not shorten; the piston passes through it (overlap ~77 mm³).
2) The upper (outlet) ball rides with the piston, always at the chamber's ceiling (valve open, as when pressing). It cannot drop onto its seat on the return stroke.
3) The lower (inlet) ball always sits on its seat. It cannot lift on the suction stroke (button released) and fall back on pressing.
This follows the earlier report about joints for a ball (2026-10-29-202947): there the ball could not be joined at all.

## What was expected

1) A "spring" / flexible part: snap_faces type "spring" between two faces of two parts (or a part marked flexible between its end faces). Its length follows the distance between them; the part is scaled along its axis in the view and the animation (the spring's free length, the length now, the force when stiffness is given). 2) + 3) A motion that depends on the direction of the driver: e.g. set_travel / a joint "follows: {part, when: "down" | "up"}" — a part moves between two stops (seat / ceiling) by the direction the driver goes (a check valve, a ratchet pawl), or a keyframed motion along the mechanism cycle (driver position → the part's position). Also drive_mechanism trace showing it.

## Steps

Assembly Parfém jablko: I3 Píst s tryskou slides (J3 axis, set_travel 14 … 17); I4 Pružina pumpy joined by axis to the piston and touch to the body (J5, J6); I6 the upper ball touch onto the piston's chamber ceiling (J7); I5 the lower ball placed on its seat (place_part). drive_mechanism Pumpička to 17 → the spring overlaps the piston, the balls do not move as valves do.

## Workaround

None. The user was told what the animation does not show.
