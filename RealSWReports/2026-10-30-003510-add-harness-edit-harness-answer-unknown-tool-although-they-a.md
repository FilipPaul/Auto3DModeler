# add_harness / edit_harness answer 'Unknown tool' although they are listed

- **Kind:** bug
- **Date:** 2026-10-30 00:35:10
- **App version:** 0.9.0 (main @ 92d0e37, 2026-10-29)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

In the assembly 'Robotické rameno' (harness H1 exists, get_assembly lists it), edit_harness {id: H1, points: [...]} and add_harness {...} both fail with 'Unknown tool edit_harness / add_harness'. The MCP tool list offers them.

## What was expected

The harness re-routed / created as described in the tool schema.

## Steps

open_part P5; edit_harness {id:"H1", points:[{part:"I1", point:[135,60,1.5]}, ..., {part:"I4", point:[12,2,12]}], r_min:4}; add_harness same points

## Workaround

Re-routing in the GUI (🔌 Kabelový svazek, ✎ Upravit body, clicks on faces).
