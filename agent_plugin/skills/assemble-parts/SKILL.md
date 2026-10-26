---
name: assemble-parts
description: Use when the user wants several parts put together — an assembly, "how do these fit", a parts list with masses, or one STEP of the whole thing.
---

# Put 3D model parts together

Only 3D model parts go into an assembly (quick parts do not). Build each part first (skill model-a-part).

1. `list_parts` — the 3D model parts there are. `new_assembly {name}` opens an empty assembly tab
   (or `open_part` an existing assembly).
2. `insert_part {part}` for each part — it lands beside the others. The result lists the placed parts
   (I1, I2 …) with positions and bounding boxes in mm. The same part may be inserted again (a second screw).
3. Join them with `snap_faces {move: {part: "I2", face}, onto: {part: "I1", face}}`: the moved part turns so
   the two flat faces touch, centred on each other. Face names are the part's own: `F2:end` is the top of the
   first extrude, `F2:start` its bottom; `find_refs` in the part (open_part it) tells the rest. A wrong name
   answers with the list of faces. `type` picks the joint: `touch` (default), `gap` (with `gap` mm), `flush`, `axis`
   (concentric round faces — a pin / screw / shaft in a hole), `parallel`, `perp`, `angle` (`value` degrees between
   the faces' directions), `tangent` (a round face on a flat one: a roller on a plate). A part's joints apply in order: `axis` first, then
   `touch` from the head to the face it sits on, seats a pin. Joints hold: the part follows when the other one moves
   or changes size (`get_assembly` lists the `joints`); `place_part` on a joined part removes its joints.
4. Fine-tune with `place_part {part, x, y, z}` (its origin in mm) and `turn: "x" | "y" | "z"` (90° about its
   centre). Check the bounding boxes from `get_assembly` and look with `get_screenshot`.
5. **Fasteners through parts with no holes**: join the parts so they touch, then `bolt_parts {part, face, x, y, kind,
   size}` — the screw goes in at x / y (mm from the middle of that flat face) and through the parts under it; the
   holes are drilled into them (a hole step in each part). `kind`: `nut` (default), `insert`, `pin`; `size` M2…M5.
   If it does not fit, the answer says why (e.g. too thin for an insert — use a nut).
   **Fasteners in holes that are there**: make matching holes in both parts (M3: Ø3.4 clearance in the top part, Ø4.0 insert hole about 6 deep
   below; M2…M5 alike; equal holes for a dowel pin), join the parts, then `suggest_fasteners` and `add_fasteners`
   (all, or the ids) — screws, inserts and pins are put in as standard parts, held by joints.
6. `get_assembly` gives the parts list (quantity, material, mass). To change a part, `open_part` it — every
   assembly that uses it follows. The user exports the assembly (STL or STEP) from its Export buttons.
