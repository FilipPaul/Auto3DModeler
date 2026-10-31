---
name: assemble-parts
description: Use when the user wants several parts put together — an assembly, "how do these fit", a parts list with masses, or one STEP of the whole thing.
---

# Put 3D model parts together

Before adding bought parts: standard-parts (reuse what the BOM has). Joints between different materials and load
paths: materials-and-strength. Test fixtures: ict-fixture. Before hand-over: design-review.

🔒 Parts and sub-assemblies with `ai_locked` (get_assembly; library parts always) stay as they are: no editing or
recolouring them, nothing moved, removed or re-joined inside a locked sub-assembly — but inserting them and joints to
them and into them (snap_faces, fix_together …) are fine: to make a mechanism move, add joints, not change a locked part.

Only 3D model parts go into an assembly (quick parts do not). Build each made part first (skill model-a-part);
**bought parts come from the library**: `library_add {item, size, length, to: "assembly"}` (find them with
`library_search {query}`) — screws, nuts, inserts, bearings, standoffs, cylinders, sensors, motors, with their part numbers.
Test fixtures (ICT / FCT): spring-loaded **test probes** and their **receptacles** are there too — INGUN GKS-100 /
GKS-075 / GKS-050, KS-100 / KS-050, KESACON MPI — found by maker, grid (`"probe 1.27"`), head style (`"crown"`,
`"korunka"`) or order code (`"GKS-100 214 130 A 2000"`, `"GKS-100-0008"`); each size is an exact order code, all its
sizes per the maker's datasheet. Cable clips (HellermannTyton P-clamps, MB tie mounts, T…R ties) and igus energy
chains (E2.10, E2.15, 14, 10) are there too — `library_search {query: "P-clamp"}` / `{query: "e-chain"}`.
**What goes with a library part** (library_search's `goes_with`): `library_pair {part: "I3", role: "nut"}` (or
`"washer"`, `"insert"`, `"screw"`, `"receptacle"`, `"probe"`), `{part, set: true}` = a nut and two washers for a screw —
each put on the part's axis where it goes (a washer under the head, the nut under the parts the screw holds; a probe
seated in its receptacle, its stroke as its slide's limits), joined Concentric.

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
   facing ends, e.g. two plates with holes 30 mm apart; `lock_rotation: true` keeps the turn), `axis_distance` (two round
   faces — pins, probes, holes, cones — with their axes parallel, `distance` mm apart, e.g. two test probes 20 mm apart;
   without `distance`: as far apart as they are now; its swing round the other axis is kept unless `lock_rotation:
   false`; a round face and a flat face: the axis along the face, `distance` mm from it; the same height: add a `flush`
   on their ends; `edit_joint {id, distance}` changes it), `parallel`, `perp`, `angle` (`value` degrees between
   the faces' directions), `tangent` (a round face on a flat one: a roller on a plate), `ball` (a ball's spherical face —
   a revolved half circle — with its centre on the axis of a hole or a cone: it slides along it and turns; onto another
   ball: a ball joint, 3 turns), `seat` (the ball seated in a conical seat or on the edge of a smaller hole: a valve
   ball — on the axis, touching), `rigid` (🔗 fixed together as they are now: `{move: {part}, onto: {part}}`, no faces —
   a part that rides on another one, e.g. a ball carried by a piston), `spring` (〰 a spring part — keep it its own part,
   joined where it sits — from its end face `move` to the face it pushes on `onto`, `value` = k N/mm: it is drawn as long
   as it reaches while the mechanism moves; get_assembly `springs`: free / now / compressed, force). A part's joints apply in order: `axis` first, then
   `touch` from the head to the face it sits on, seats a pin. Joints hold: the part follows when the other one moves
   or changes size (`get_assembly` lists the `joints`); `place_part` on a joined part removes its joints.
   The user does the same by clicking: a part or a face selected, the **suggestions table** in the view's corner
   offers its joints (Touch…, Gap…, Concentric…), two faces picked offer what joins them. To show them how, select it
   (`gui_action {pick: "I2"}` or `{pick: "I2 F2:end"}`), read `gui_state {where: "suggest"}` and point at the row
   with `gui_highlight {control: <its n>}`.
   A part in the way of what you want to show or check: `set_visibility {hide: ["I3"]}` (or `transparent: [...]`,
   `isolate: ["I2"]`, `show_all: true`) — display only, saved with the assembly; get_assembly `hidden` / `transparent`.
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
   its limits (where along it: get_assembly `at`; `min: "here"` / `max: "here"` = that end where the part is now — the
   app's ⇤ Set min here / Set max here ⇥, after `move_free {part, motion, to}`), then `check_travel {part, motion}` tells whether it hits anything
   on the way; `move_free {part, motion, to}` puts it at a position (it stops at the limits). `lock_motion {part,
   motion}` keeps one free motion where it is — also a touch's slides on the face (one by one) and a ball's turns.
   Many parts that must move as one (a gate frame with its screws, nuts, handle …): one call, `fix_together {parts:
   [...] | all_except: [...], to: <the base, also "I3/I2" inside a sub-assembly>, name}` — one 🔗 rigid group (get_assembly
   `groups`), not a rigid snap_faces per part; `remove_joint {id: "R1"}` dissolves it.
   A check valve's ball (or a pawl) that sits at one stop or the other by the way the piston goes: join it so it has one
   slide (`ball` on its seat's axis), `set_travel {part, motion, min, max}` = its two stops (seated / lifted), then
   `set_travel {part, motion, follow: {part: <the piston>, at: "max" | "min"}}` — where it sits while the piston moves
   forward (its value grows); back: the other stop. It then moves with the piston's mechanism (drive_mechanism, ▶, trace).
   A part that only rides along: `rigid`. A crank's full turn always goes forward — the rule is for a to-and-fro driver.
   A sub-assembly placed in this one keeps its own motions: get_assembly lists them in its `inner` (part "I3/I2");
   `move_free {part: "I3/I2", …}` moves that part here only — the sub-assembly's own tab stays as it is. Its own
   mechanisms (a crank loop, gears) are in get_assembly `mechanisms` too (`inside: "I3"`, parts "I3/I2"):
   `drive_mechanism {mechanism: "I3", to}` drives the first inside it; the parts here joined to its parts follow and
   a loop through both levels is solved together. `place_part {part: "I3", rigid: true}` = 🧱 one body, no inner motion.
   A closed loop (a crank – rod – slider: the rod joined to the crank's pin and to the slider's pin) is solved as one
   mechanism: get_assembly `loops` gives its parts, `free_motions` (1 for a crank-slider) and the motions that
   `drive` it — move_free the crank (or the slider), set_travel 0 … 360 + check_travel it: the rest follows. Place
   the parts near where they go before the last joint (it closes the loop the shortest way). `closed: false` /
   "cannot close": a part is too short or too long for that place. get_assembly `missing_joint` {hole, pin}: the
   parts almost make a loop and one pin in a hole would close it — `add_missing_joint` adds that ◎ Concentric.
   A joint with `broken: true` lost a face (a part's edit took it — `gone_face` names it; get_assembly `mechanisms`
   lists them as `broken_joints`): its part is not held there. Tell the user; the app's 🔧 Opravit vazbu (the joint
   row, the mechanism row) re-picks the face, or `snap_faces` the joint again with the new face.
   How a follower moves over the driver's travel (a slider's stroke, a rocker's swing): `drive_mechanism {mechanism,
   trace: true}` -> [[driver, follower], …] (the app's 📈 Trace). `place_part {part, fixed: true}` = 📌 fixed in place.
   The whole mechanism by one value: get_assembly `mechanisms` (each with its driver — a crank's full turn by default —
   where it is and its travel) -> `drive_mechanism {mechanism, to}` (every part follows; `play: true` runs it on and on
   in the app's ⚙ Mechanism, `driver` picks another driver). When the user wants to see where it hits something:
   `drive_mechanism {mechanism, collisions: true}` (the widget's ⚠, off by default) — the parts in a collision glow red
   while it moves and it answers the collision bands over the travel; `stop_at_collision: true` pauses ▶ at the first
   one. Name the motions in the user's words
   (`name_motion {part, motion, name: "Otáčení kliky"}`, `drive_mechanism {name}` for the mechanism) — the names show
   everywhere and work as `motion` in move_free / set_travel. To show it moving: `set_view` as it should be seen, then
   `record_animation {mechanism, format: "gif" | "video"}` saves one full cycle in the data folder (it answers the path).
   Ready-made mechanisms (a crank – rod – slider, a four-bar, gears with a rack, a robot arm, a pump: a spring and check valves) to show or start from:
   `list_demos`, `open_demo {name: "crank"}` — only when the user asks (a new project; the one on screen is kept in
   🕘 Recent projects). A saved project file (.a3d) opens with `open_file {path}` the same way.
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
8. **Cables and wires** (🔌 Cable harness): `add_harness {type, points, …}` routes one through points — `{part: "I2",
   face: "F2:end"}` (it lies on that face's middle, Ø/2 off it; a round face: through the hole's centre), `{part, point:
   [x, y, z]}` (the part's own coordinates) or `{xyz: [x, y, z]}` (in space, to lead it round things). type `"wires"`
   (loose wires: `count` + `wire_d`, or `wires: [{color, d}]` — IEC colours black, brown, red, orange, yellow, green,
   blue, violet, grey, white, pink, green-yellow), `"cable"` (`d`, `color`), `"ribbon"` (`count` × `pitch`) or
   `"sleeve"` (`d`). `r_min` (mm) is the minimum bend radius (default 5 × Ø): every corner is rounded to it; a corner
   whose legs are too short for it is reported (`bends_too_tight`: add a point further out or lower r_min), and
   `through_parts` names parts its centre line goes through (add a point round them). Points on a part move with it.
   The answer and get_assembly `harnesses` give its length; get_bom lists a line per wire with its length + the
   reserve (5 %). `edit_harness {id, …}` changes any of these (`points` replaces them, `add_points` appends, `remove:
   true` deletes it); one point by its number (as `point_list`): `set_points: [{n: 2, part, face}]` moves it (a flat
   face: its centre; a round face: the hole's axis), `remove_points: [3]`, `insert_points: {after: 2, points: [{xyz}]}`
   (0 = before the first), `order: [1, 3, 2, 4]` — a span's own length stays with its two points. Corners are shaped to r_min (two close corners moved apart), so `bends_too_tight` is only the
   exception. To test moving parts with a real cable, lock its length: `edit_harness {id, length_locked: true}` (as it
   is now) or `{length: 400}` — then drag / drive_mechanism: the slack sags, and a cable pulled too far is reported
   `taut: {short_mm}` (a limit of the motion). The answer's `point_list` names each point's part, face and lock: a
   point on a part is 🔒 locked (moves with it); `edit_harness {id, unlock_points: [3]}` leaves it in space,
   `lock_points` sticks it back. A flat face given as `{part, face}` puts the point on its centre (a pin's top: on its
   axis, so the length holds as the joint turns). `through_at` says where it goes through a part (the span between
   two points, the spot) — add a point there to lead it round. A service loop between two points:
   `edit_harness {id, spans: [{from: 3, length: 180}]}` (the cable from point 3 to 4 that long: slack that keeps
   r_min and holds as the parts move; no length: as it is now; null: none). The cable keeps clear of the parts by
   itself (its ends leave their faces straight out, a span goes round a part in its way): `detour_points` says how
   many it put in, `still_hits` names parts it could not get clear of — add a point to lead it round those.
   Fix it down with a clip: `edit_harness {id, clip: {point: 3}}` (a point on a face; the snuggest clip for its Ø, the
   point then on the clip's axis; the clip is 🔗 fixed to that part, so it moves with a carriage or an arm; `item` /
   `size` pick one — any size that holds the bundle; on a point that has a clip it is swapped, the point kept). Where
   the cable plugs into a part (a connector, a probe's tail, a gland) that point is a connection point — the ends on a
   part are by default (`point_list` `connection`); `edit_harness {id, connect_points: [3]}` / `disconnect_points`.
   The cable may enter that part near it: no `through_at` / `still_hits` / `too_close` for it there. A harness with
   warnings (taut, bends_too_tight, through_parts, too_close): `edit_harness {id, auto_fix: true}` fixes what it can
   without moving locked or connection points and says what is left. get_assembly's `span_slack_mm` (and each
   `spans` entry's `slack_mm`) is how much longer each span is than the tightest it could be (0: taut). Through
   an energy chain: `edit_harness {id, chain: {span: 2, id: "C1"}}` (no id:
   one sized for the bundle is put in) — the cable then follows the chain's moving end. The chain itself (library_add
   an e-chain: its first link at the fixed end — join it to the frame; one put in by edit_harness chain is joined for you): `edit_chain {id: "C1", links, travel, moves_with:
   "I5"}` (the carriage: its moving end goes along as that part moves; null: its own travel), get_assembly `chains`
   (reach_ok false: add links). STEP / GLB exports and the assembly drawing include it.
   The joints' symbols in the view: `set_view {joints: false}` hides them (the bottom row's 🔗 Joints) — for a clean
   screenshot.

Files for the user: `export {format: "step"}` (the whole assembly as a STEP assembly — SolidWorks, CATIA and Solid
Edge open it as an assembly tree, a product per part, sub-assemblies nested), `"iges"` (every part placed in one IGES —
only for a program that asks for IGES; it has no assembly tree), `"glb"` (glTF for viewers and rendering: a node
per placed part, colours, metal / plastic materials), `"3mf"` (in colours, an object per colour for multi-material printing), `"bom"` (the parts list as CSV).

**Missing a tool?** When no tool fits and you work around it (several calls for one thing, guessing, asking the user
to click for you), file it at once: `list_reports {search: "<the words>"}`, and if it is not there
`report_problem {kind: "tool request", …}` (the tool you would want: name, inputs, result; your workaround) —
then tell the user in one line and carry on. A wrong result is `{kind: "bug"}`; each thing reported once.
