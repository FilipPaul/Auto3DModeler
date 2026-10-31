# Joint 'distance between axes': two round faces (pins, probes) parallel at a given distance

- **Kind:** tool request
- **Date:** 2026-10-30 01:02:33
- **App version:** 0.9.0 (main @ 1e35a8d, 2026-10-30)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

User wants two INGUN GKS-100 probes standing parallel 20 mm apart at the same height. The Distance / Gap joint in the GUI only accepts flat faces ('Klikněte na rovnou plochu.'), there is no joint that keeps two axes (cylinders) parallel at a set distance, nor a point/axis-to-axis distance.

## What was expected

Selecting two round faces (Ctrl+click) offers 'Vzdálenost os' in the suggestions table: axes parallel, distance d mm between them (value editable in the joint panel, like gap); optionally direction (along X/Y). Combined with flush of the top faces it gives the 'same height, 20 mm apart' layout in two clicks. snap_faces type 'axis_distance' {move, onto, value} likewise.

## Steps

Assembly with I5, I6 (GKS-100), I7 (KS-100). Picking I5 F2:side:l2 with the distance tool -> toast 'Klikněte na rovnou plochu.'

## Workaround

Model the probe plate with holes at 20 mm pitch and put receptacles/probes concentric into them (the real ICT fixture way).
