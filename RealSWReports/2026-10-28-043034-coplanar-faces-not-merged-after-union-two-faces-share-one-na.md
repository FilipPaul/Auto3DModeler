# Coplanar faces not merged after union: two faces share one name (F4:start)

- **Kind:** bug
- **Date:** 2026-10-28 04:30:34
- **App version:** 0.9.0 (main @ 5f7e65b, 2026-10-28)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

Bracket: base plate (F2, y −20…20) + wall extruded from {datum XZ, offset 20} flipped, so its front face lies in the plate's front plane y = −20. find_refs normal [0,−1,0] returned two faces, both named "F4:start" (centroid z 25 area 2400, and z 2.5 area 300). The plate's front face lost its own name (F2:side:l1) and the face is not merged, so a seam line shows in the view. A sketch {face: "F4:start"} is ambiguous (it happened to use the big one).

## What was expected

Coplanar adjacent faces after an add are merged into one face (one name), or at least every face keeps a unique name (e.g. F4:start and F2:side:l1).

## Steps

sketch XY rect -30,-20 60×40; extrude 5; sketch {datum XZ, offset 20} rect -30,0 60×45; extrude 5 flip; find_refs {kind: face, normal: [0,-1,0]}.
