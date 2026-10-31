# get_screenshot view front / back gives the same stale image, highlight ignored

- **Kind:** bug
- **Date:** 2026-10-29 20:56:49
- **App version:** 0.9.0 (main @ 92d0e37, 2026-10-29)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

On the 3D model Lahvička jablko, get_screenshot {view: "front"}, {view: "front", highlight: ["F6"]} and {view: "back"} returned pixel-identical images. The highlight was not lit and front / back were not mirrored. The silhouette did not show a through cut (F6, a Ø44 cylinder along Y removing x > 27 at z 42) that the iso view and the volume do show. A pink, jagged section-like disc is also drawn at the bottom.

## What was expected

The front view looks along +Y and shows the notch in the outline. The back view is its mirror image. highlight lights the faces orange.

## Steps

set_view {view: front}; get_screenshot {view: front, highlight: [F6]}; get_screenshot {view: back}: all three the same; get_screenshot iso is right.

## Workaround

Checked in the iso view.
