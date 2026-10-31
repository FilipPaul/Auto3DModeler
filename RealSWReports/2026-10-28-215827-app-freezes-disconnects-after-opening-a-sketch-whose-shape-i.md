# App freezes / disconnects after opening a sketch whose shape is a profile (lines + arcs), and 🪄 Auto-dims disappears

- **Kind:** bug
- **Date:** 2026-10-28 21:58:27
- **App version:** 0.9.0 (main @ fe12e22, 2026-10-28)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

In 3D model 4, I set F1 with edit_feature to one closed profile (lines plus 2 arcs given as {arc: [u,v]}). The rebuild was OK (volume 59944.9). Then I double-clicked 'Skica 1' to edit it. The toolbar no longer had the 🪄 Automatické kóty button. The next get_screenshot timed out after 150 s, and after that every tool call returned 'The app is not open in a browser'. The page froze or crashed.

## What was expected

The profile opens in the sketch editor as editable lines and arcs (tangent where the profile is tangent), auto-dims is available, and the page does not freeze.

## Steps

edit_feature F1 {shapes: [{profile: {points: [[-20,-30],[45,-30],[45,-14],{arc:[66.5497,0.9621]},[60.06341,26.38085],[30.06341,52.38085],{arc:[5.4461,55.9218]},[-8,35],[-20,35]]}}]} → gui_action double-click 'Skica 1' → gui_state tools (no Auto-dims) → get_screenshot timeout → get_model: app not open.
