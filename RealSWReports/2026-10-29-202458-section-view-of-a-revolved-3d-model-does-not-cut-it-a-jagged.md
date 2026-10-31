# Section view of a revolved 3D model does not cut it; a jagged pink ring is drawn instead

- **Kind:** bug
- **Date:** 2026-10-29 20:24:58
- **App version:** 0.9.0 (main @ 92d0e37, 2026-10-29)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

set_view {section: {axis: "y", offset: 0}} on a 360° revolved model (Tělo pumpy, Píst s tryskou), then get_screenshot view front: the model is shown whole and uncut. A large pink ring with jagged edges appears near z = 0, much bigger than the part.

## What was expected

The model is cut at y = 0, so its inner bores, valve seats and channels show, with the cut faces capped.

## Steps

new_model; sketch on XZ with a closed profile; revolve axis y; set_view section {axis: y, offset: 0}; get_screenshot {view: front}

## Workaround

Checked the inside from the model's numbers (volume, bbox) instead of a picture.
