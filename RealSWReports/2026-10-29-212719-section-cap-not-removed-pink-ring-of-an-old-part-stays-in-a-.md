# Section cap not removed: pink ring of an old part stays in a new model's view after section off

- **Kind:** bug
- **Date:** 2026-10-29 21:27:19
- **App version:** 0.9.0 (main @ 92d0e37, 2026-10-29)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

In a new 3D model (3D model 8: Ø70×10 disc, extrude preview) a jagged pink section-cap ring of an earlier revolved part floats above it. set_view {section: "off"} does not remove it; it shows in get_screenshot too. Differs from the earlier report (wrong cap while sectioning): here the cap mesh is never disposed — it survives section off and a tab change.

## What was expected

Turning the section off or switching parts removes the cap meshes from the scene.

## Steps

Section view on a revolved part (perfume / pump tabs); open new 3D model 8, sketch circle Ø70, Extrude -> ring above the part; set_view section off -> still there.
