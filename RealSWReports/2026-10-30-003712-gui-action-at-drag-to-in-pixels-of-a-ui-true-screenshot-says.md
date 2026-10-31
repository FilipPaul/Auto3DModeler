# gui_action at / drag_to in pixels of a ui:true screenshot says 'That point is off the screen'

- **Kind:** bug
- **Date:** 2026-10-30 00:37:12
- **App version:** 0.9.0 (main @ 92d0e37, 2026-10-29)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

Assembly, harness in ✎ Upravit body mode. get_screenshot {ui:true} (1400×791) shows a harness point at px (542,383). gui_action {at:[542,383], drag_to:[558,393]} -> 'That point is off the screen'. Same with the fitted get_screenshot (1200×900) pixels (585,393). With fractions [0.387,0.484] it dragged, but it orbited the view instead of moving the point (fractions are of the 3D view, not of the window picture).

## What was expected

Pixels read off the last screenshot (ui or fitted) hit that spot: dragging a harness point moves it (snapping to a hole centre).

## Steps

Svazek 1 -> Upravit body; get_screenshot ui:true; gui_action {at:[542,383], drag_to:[558,393]}

## Workaround

None reliable — re-picking faces instead.
