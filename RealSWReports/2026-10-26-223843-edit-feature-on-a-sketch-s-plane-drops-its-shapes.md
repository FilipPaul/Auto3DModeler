# edit_feature on a sketch's plane drops its shapes

- **Date:** 2026-10-26 22:38:43
- **Reported by:** the AI agent (MCP report_problem)

## What happened

edit_feature F8 {plane: "XZ"} (was {datum: "XZ", offset: -4}, with a profile shape) left the sketch empty: "The sketch has no closed shape to use".

## What was expected

Only the plane changes; the shapes stay.

## Steps

add_feature sketch plane {datum:"XZ", offset:-4} with a profile shape (smooth parts) -> extrude symmetric -> edit_feature {plane: "XZ"}

## Workaround

Sent plane and shapes together in one edit_feature.

## Resolved

- **2026-10-26** — Fixed: edit_feature with a new plane only keeps the sketch's shapes (web/js/modeler/agent_model.js). Test: tools/e2e_reported.py (1).
