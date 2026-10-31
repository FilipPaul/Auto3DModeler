# get_screenshot of an assembly is a narrow 339×900 strip, not fitted to the whole assembly

- **Kind:** bug
- **Date:** 2026-10-29 01:55:47
- **App version:** 0.9.0 (main @ 63d5c3a, 2026-10-28)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

In the assembly "Klikový mechanismus" (240 mm long, 5 parts) every get_screenshot (default fit, also fit: true; view iso and top; explode 0 and 0.6) returns a 339×900 px image showing only a part of the base plate and the rod — the crank, bearing and slider are cut off. In the top view the parts fill the middle third of the height, the rest is empty.

## What was expected

The picture has the 3D view's real aspect (or a sensible one, e.g. 4:3), and with fit the whole assembly (exploded too) is inside it.

## Steps

set_view {view: iso} -> get_screenshot; set_view {view: top} -> get_screenshot {fit: true}; set_view {view: iso, explode: 0.6} -> get_screenshot. The AI chat panel is open beside the view (the view may be narrow).

## Workaround

None — checked positions via get_assembly bboxes instead of the picture.
