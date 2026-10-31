# Wishlist from a test drawing session (bracket + revolved knob)

- **Kind:** tool request
- **Date:** 2026-10-28 04:30:48
- **App version:** 0.9.0 (main @ 5f7e65b, 2026-10-28)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

Built "Test – úhelník" (plate, wall, holes + linear pattern, slot cut, rib + mirror, engraved text, fillet, chamfer, sheet) and "Test – knoflík" (smooth revolve profile, grip cut + circular pattern 8×, D-shaft cut on the bottom face). All steps ok. What was missing or needed workarounds:
1) Datum-plane direction: {datum: "XZ", offset: 20} went to y = −20 and the extrude went outward; I had to guess and then flip. A cut sketched on XY at z = 0 removed nothing until flipped. Wish: add_feature results say where the new solid lies ("extruded y −25…−20, outside the body / adds 0 mm³ inside"), and an extrude option dir: "into_body" / "+y" (a world direction) instead of guessing flip.
2) A hole shape: the hole feature does only round holes. Wish: hole {shape: "d_flat", flat: 5.4} or a counterbore / countersink option (hole {cbore_d, cbore_depth} / {csk_d, angle}) and threaded holes (thread: "M5" → tap drill + cosmetic thread on the drawing). The D-shaft needed a hand-computed profile with an arc.
3) Sketch on a face with world coordinates: on face sketches the origin is the face's centroid, which moves when the face changes (e.g. the wall's face split by the decal / slot), so hole positions measured from the centroid are fragile. Wish: sketch {face, origin: "corner" | "world"} or hole points in world coordinates (world: true).
4) Screenshot control: get_screenshot {view, fit: true, zoom, highlight: [face names]} to check one feature, and a screenshot of a drawing sheet.
5) measure for 3D models (not only assemblies): measure {a: face/edge, b: face/edge} → distance / wall thickness, and a check_model {min_wall: 1.2, overhang: 45} → thin walls and overhangs for printing.
6) find_refs by step: find_refs {of_step: "F10"} → all faces / edges a step made (to fillet a rib's edges at once), and edges {between_steps: ["F2", "F10"]} (the joint edge rib↔plate for a fillet).
7) Sheet check: "missing" lists 30 entries "Front: an edge (x)" without coordinates; most come from the engraved text. Wish: ignore decal / text edges and give each missing item its point (key) so sheet_edit add can use it directly.
8) Loft / sweep exist but no "rib" feature: rib {sketch: an open line, t: 4} (as in SolidWorks) would make gussets with one line instead of a closed triangle.
9) A step's name on add: name works for sketches; good — but returned default names "Extrude 1", "Pattern 1" could take the sketch's name ("Extrude – Drážka").

## What was expected

Tools as listed above; most important 1) direction feedback / world direction for extrude, 2) counterbore / thread / D holes, 4) fit-to-view screenshots, 6) find_refs of_step.

## Workaround

Flipped extrudes after reading bbox / volume change; computed the D profile by hand; checked the rib with a section view; picked edges one by one with near.
