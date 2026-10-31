# Cut on Základna reports solids: 2 and a 3 mm deep slot cut ADDS +190 mm³

- **Kind:** bug
- **Date:** 2026-10-30 00:33:10
- **App version:** 0.9.0 (main @ 92d0e37, 2026-10-29)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

Základna (plate 8 mm + Ø12 pin, one solid, 117009.6 mm³). Sketch Ø4 circle at (60,60) on XY, extrude cut through (flip) -> -227.9 mm³ (expected -301.6) and body says solids: 2. Then sketch slot (60,60)-(125,60) w4, extrude cut 3 mm from the bottom -> volume_change +189.8 mm³ (a cut can't add volume). Geometry looks right in the side view (the groove exits at the side). Section view y=60 also draws a wrong triangular cut face.

## What was expected

One solid; cuts reduce volume by their real volume (~-302 and ~-195 mm³).

## Steps

open_part Základna; add_feature sketch XY circle 60,60 d4; extrude cut through flip; sketch slot; extrude cut d3 flip; get_model
