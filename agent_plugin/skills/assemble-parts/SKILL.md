---
name: assemble-parts
description: Use when the user wants several parts put together — an assembly, "how do these fit", a parts list with masses, or one STEP of the whole thing.
---

# Put 3D model parts together

Only 3D model parts go into an assembly (quick parts do not). Build each made part first (skill model-a-part);
**bought parts come from the library**: `library_add {item, size, length, to: "assembly"}` (find them with
`library_search {query}`) — screws, nuts, inserts, bearings, standoffs, cylinders, sensors, motors, with their part numbers.

1. `list_parts` — the 3D model parts there are. `new_assembly {name}` opens an empty assembly tab
   (or `open_part` an existing assembly). An assembly from SolidWorks, CATIA or Solid Edge comes as a STEP:
   `open_file {path, as: "assembly"}` makes its parts (once each) and the assembly, placed as in the file.
2. `insert_part {part}` for each part — it lands beside the others. The result lists the placed parts
   (I1, I2 …) with positions and bounding boxes in mm. The same part may be inserted again (a second screw).
3. Join them with `snap_faces {move: {part: "I2", face}, onto: {part: "I1", face}}`: the moved part turns so
   the two flat faces touch, centred on each other. Face names are the part's own: `F2:end` is the top of the
   first extrude, `F2:start` its bottom; `find_refs` in the part (open_part it) tells the rest. A wrong name
   answers with the list of faces. `type` picks the joint: `touch` (default), `gap` (with `gap` mm), `flush`, `axis`
   (concentric round faces — a pin / screw / shaft in a hole; with `gap` the distance along the axis between their
   facing ends, e.g. two plates with holes 30 mm apart; `lock_rotation: true` keeps the turn), `parallel`, `perp`, `angle` (`value` degrees between
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
6. Check it: `get_assembly` tells for each joined part how it can still move (`free`: e.g. "Turn: Crank",
   "Slide: Slider" — two of a kind say how: "Slide: Lid (along X)") or that it is `fully_held` — a hinge or slide keeps its one way free, the rest is held.
   `check_collisions` lists parts that go into each other (fix the made part: a hole, a pocket).
   A part that moves (a cylinder's rod, a slide, a door): `set_travel {part, motion, min, max}` gives its free motion
   its limits (where along it: get_assembly `at`), then `check_travel {part, motion}` tells whether it hits anything
   on the way; `move_free {part, motion, to}` puts it at a position (it stops at the limits).
   A sub-assembly placed in this one keeps its own motions: get_assembly lists them in its `inner` (part "I3/I2");
   `move_free {part: "I3/I2", …}` moves that part here only — the sub-assembly's own tab stays as it is.
   A closed loop (a crank – rod – slider: the rod joined to the crank's pin and to the slider's pin) is solved as one
   mechanism: get_assembly `loops` gives its parts, `free_motions` (1 for a crank-slider) and the motions that
   `drive` it — move_free the crank (or the slider), set_travel 0 … 360 + check_travel it: the rest follows. Place
   the parts near where they go before the last joint (it closes the loop the shortest way). `closed: false` /
   "cannot close": a part is too short or too long for that place. get_assembly `missing_joint` {hole, pin}: the
   parts almost make a loop and one pin in a hole would close it — `add_missing_joint` adds that ◎ Concentric.
   How a follower moves over the driver's travel (a slider's stroke, a rocker's swing): `drive_mechanism {mechanism,
   trace: true}` -> [[driver, follower], …] (the app's 📈 Trace). `place_part {part, fixed: true}` = 📌 fixed in place.
   The whole mechanism by one value: get_assembly `mechanisms` (each with its driver — a crank's full turn by default —
   where it is and its travel) -> `drive_mechanism {mechanism, to}` (every part follows; `play: true` runs it on and on
   in the app's ⚙ Mechanism, `driver` picks another driver). Name the motions in the user's words
   (`name_motion {part, motion, name: "Otáčení kliky"}`, `drive_mechanism {name}` for the mechanism) — the names show
   everywhere and work as `motion` in move_free / set_travel. To show it moving: `set_view` as it should be seen, then
   `record_animation {mechanism, format: "gif" | "video"}` saves one full cycle in the data folder (it answers the path).
   Ready-made mechanisms (a crank – rod – slider, a four-bar, gears with a rack, a robot arm) to show or start from:
   `list_demos`, `open_demo {name: "crank"}` — only when the user asks (a new project; the one on screen is kept in
   🕘 Recent projects). A saved project file (.a3d.json) opens with `open_file {path}` the same way.
   **Gears, belts, a rack**: two parts that each turn on their own pin are coupled by `snap_faces {type: "gear" |
   "belt", move: {part, face: its rim}, onto: {part, face: the other rim}}` (the rims: the pitch circles; a gear pair
   turns opposite ways, a belt the same way; `value` = the ratio, default Ø onto / Ø move), a pinion and a sliding rack
   by `type: "rack"` (move = the pinion's rim, onto = the rack's flat side along its axis: π·Ø per turn). Then
   move_free / drive_mechanism one of them — the other follows, the coupled parts are one mechanism. get_assembly
   `couplings` (G…): `edit_joint {id, ratio, flip}`, `remove_joint {id}`.
   A joint with `not_held` is overridden by another joint of that part (it names it): change or `remove_joint` one
   of the two — never leave a joint that does not hold. Joining the same two faces again changes that joint.
   `remove_from_assembly` on a fastener's screw or nut takes out the whole fastener and the holes drilled for it.
   Change a joint with `edit_joint {id, gap | distance | lock_rotation | angle | flip | locked}` (ids from
   get_assembly), take one away with `remove_joint {id}`; `measure {a: {part, face}, b: {part, face}}` gives gaps and
   axis distances; `set_view {view, section, explode}` before `get_screenshot` to look inside or pull it apart.
7. `get_assembly` gives the parts list (quantity, material, mass, maker and part number of bought parts; `total`: how many in
   all, the ones inside sub-assemblies counted in), each placed part's `mass_g`, and `mass_g` / `cog_mm`: the whole assembly's mass and centre of mass
   where the parts are now (it moves with a mechanism: drive it and ask again). The whole BOM: `get_bom {assembly, mode}` — any assembly of the
   hierarchy, summary (a row per part: total, pos = the drawings' balloon number, make_buy, `from`: where the count
   comes from) or structured (the tree: qty_per_parent, total). Screws placed both in the assembly and in a
   sub-assembly are counted in both; the user sees the same in 📋 BOM (⬇ CSV / Excel) and can add a BOM page to the
   assembly's drawing (📋 Add BOM page). To change a part, `open_part` it — every
   assembly that uses it follows. The user exports the assembly (STL or STEP) from its Export buttons.

Files for the user: `export {format: "step"}` (the whole assembly as a STEP assembly — SolidWorks, CATIA and Solid
Edge open it as an assembly tree, a product per part, sub-assemblies nested), `"iges"` (every part placed in one IGES —
only for a program that asks for IGES; it has no assembly tree), `"glb"` (glTF for viewers and rendering: a node
per placed part, colours, metal / plastic materials), `"3mf"` (in colours, an object per colour for multi-material printing), `"bom"` (the parts list as CSV).

**Missing a tool?** When no tool fits and you work around it (several calls for one thing, guessing, asking the user
to click for you), file it at once: `list_reports {search: "<the words>"}`, and if it is not there
`report_problem {kind: "tool request", …}` (the tool you would want: name, inputs, result; your workaround) —
then tell the user in one line and carry on. A wrong result is `{kind: "bug"}`; each thing reported once.
