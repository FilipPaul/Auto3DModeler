# MCP: read a sketch (entities, constraints, dims, free DOF) + run auto-dims

- **Kind:** tool request
- **Date:** 2026-10-28 21:49:33
- **App version:** 0.9.0 (main @ fe12e22, 2026-10-28)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

To fix a sketch, I had to guess its geometry from find_refs corners and axes of the extrude preview. get_model only gives counts (line 5, arc 2, locked 4). The dimension values are not in gui_state (only 🔓/🔒 buttons with no value or name), and they are not in get_screenshot either (the dimension labels are not drawn). There is no tool for auto-dims, so I had to click it with gui_action, and its errors are not returned anywhere.

## What was expected

get_sketch {id} → entities with coordinates and ids, constraints (tangent, equal, coincident…), dimensions {id, kind, value, locked, between}, free DOF per entity, and the solver's conflicts or redundancies. sketch_auto_dims {id} → which dims were added, or why it failed. sketch_dim {id, dim, value / locked}. gui_state should list each dim's label and value, and screenshots should show the dim labels.

## Workaround

I read corners and axes with find_refs from the extrude preview, worked out the geometry (rect ∪ slot) and rewrote the sketch with edit_feature.
