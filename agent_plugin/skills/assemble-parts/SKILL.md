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
   answers with the list of flat faces. A snap holds: the moved part follows the other one when it moves or a part
   changes size (`get_assembly` lists the `links`); `place_part` on the snapped part ends its link.
4. Fine-tune with `place_part {part, x, y, z}` (its origin in mm) and `turn: "x" | "y" | "z"` (90° about its
   centre). Check the bounding boxes from `get_assembly` and look with `get_screenshot`.
5. `get_assembly` gives the parts list (quantity, material, mass). To change a part, `open_part` it — every
   assembly that uses it follows. The user exports the assembly (STL or STEP) from its Export buttons.
