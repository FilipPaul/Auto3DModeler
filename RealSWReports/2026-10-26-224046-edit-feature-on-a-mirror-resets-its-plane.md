# edit_feature on a mirror resets its plane

- **Date:** 2026-10-26 22:40:46
- **Reported by:** the AI agent (MCP report_problem)

## What happened

Mirror F19 was made with {of: "F17", plane: "XZ"}. edit_feature F19 {of: "body"} mirrored left-right (YZ): the part became 102 mm long.

## What was expected

Only 'of' changes; the plane stays XZ.

## Steps

add_feature mirror {of: "F17", plane: "XZ"} -> edit_feature {of: "body"}

## Workaround

edit_feature {of: "body", plane: "XZ"} together.

## Resolved

- **2026-10-26** — Fixed: a mirror edited with a new `of` only keeps its plane — the step's own plane ({datum}) was read as a name and fell back to YZ (agent_model.js build). Test: tools/e2e_reported.py (2).
