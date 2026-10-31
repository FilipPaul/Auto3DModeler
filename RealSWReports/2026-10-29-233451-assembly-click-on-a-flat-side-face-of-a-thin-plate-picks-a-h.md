# Assembly click on a flat side face of a thin plate picks a hole's cylinder hidden behind it

- **Kind:** bug
- **Date:** 2026-10-29 23:34:51
- **App version:** 0.9.0 (main @ 92d0e37, 2026-10-29)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

In "Robotické rameno", clicking the visible flat side face (F2:side:l3, 22×4 mm) of the pink plate I5/I2 ("3D model 7", a 4 mm plate with holes Ø8.49 and Ø5.66) selects I2/F2:side:c1 or c2 (the holes' cylinders, inside the plate and hidden) instead. The user hit the same thing ("selected I5 I2/F2:side:c2 (válcová)") and could not select the face they wanted. Two clicks at different spots on the face both gave hole cylinders. Maybe the ◎ Středy (centres) snap or a round-face preference beats the face actually under the cursor.

## What was expected

A click selects the front-most face under the cursor. A hidden hole should only be picked if the user asks for it (e.g. Alt+click cycles through the faces behind).

## Steps

gui_action at [0.49, 0.467] and at [0.55, 0.43] on the pink plate's side face -> suggestions about "I5 plocha I2/F2:side:c1 (válcová)" / c2.

## Workaround

snap_faces / measure by face name through the tools.
