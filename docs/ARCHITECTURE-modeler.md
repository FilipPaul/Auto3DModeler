# Auto3DModeler: plan for the 3D modeller workspace

Status: plan only. No code has been changed.
Date: 2026-10-25. Written by the architect agent.

---

## Progress (2026-10-28)

- **☑ 🔒 Locked / ☑ Show in a size's editor on the part (2026-10-30)** (an app report: no way to unlock or hide a
  dimension from its popup). Modeler.openDimEdit: a row under the slider (not for the open tool's own labels). Locked
  (a sketch's size, a hole's distance): unticked + OK = freeDim — a shape's own len / Ø / R loses its dim (as
  Sketcher.toggleLock), a distance becomes `free` (a reference), a hole's `f.lock` axis goes; typing / sliding ticks it
  again (typed = locked). Show: unticked + OK = the label's key (`<sketch id>:[t,e,a,b]`, `<step>:<field>`,
  `<hole>:at<i><axis>`) in `part.hidden_dims` (saved, in the undo snapshot); 🏷 Sizes: All and 📏 switched on clear it
  (an undo step). One undo step per OK; OK marked data-rclick-ok (right-click in the view). tools/e2e_dim_popup.py.
- **⇤⇥ One side of a limit at a time (2026-10-30)** (the owner: clear min and max separately). A motion's `travel`
  record may hold only `min` or only `max`: the other side is open. dof.js clampLim (drag.js, the panel's slider,
  move_free, setTravel's put-back) and travelOf (both ends for what needs them: a turn a full turn from the stop — in
  motionPos the open end left out, so at the stop it reads the stop —, a slide the part's size past where it is):
  ▶ (playTravel), ⚠ Check the travel, the mechanism's range (mechanism.js rangeOf). setTravel takes {min?, max?}
  (`follow` needs both stops: dropped), clearEnd(id, mo, end). UI: ⚙ Mechanism "⇤ −45 ✕ … ∞ ⇥" (✕ by each value; ∞ =
  limitHere), the part panel's min / max with ✕ / ∞, suggestions ✕ Clear min / ✕ Clear max. AI: set_travel min /
  max null clears that side (both null: off). tools/e2e_mech_limits.py extended, e2e_assembly_travel (a slide; its
  motion="axis" calls fixed to motion=0).
- **⚠ Collisions while a mechanism moves (2026-10-30)** (the owner: collisions no longer seemed highlighted while a
  mechanism runs). Found: there never was a live highlight — the ⚠ Collisions panel tints the pairs it last computed
  and checks again only after a change is committed (a drop, ⏸), so during a drag / ▶ / the slider the tints stayed
  where they were. New, off by default (the owner): web/js/assembly/mechclash.js — a row's ⚠ in ⚙ Mechanism (the
  record's `clash`, ⋯ "Zastavit při kolizi" `clashStop`) scans the driver's travel once (driveTo quiet at ≤ 180 steps,
  ~2° / 0.5 mm, POST /api/assembly/sweep with `quick`; again when the still parts, joints or travel change: a
  signature), then Assembly.draw looks up the nearest step (no kernel call per frame): both parts' red glow + the
  overlap box, a `.mc-clashnote` in the view (depth = the overlap box's size along the moving part's way there), red
  bands under the slider (`.mc-clashbar`); ▶ pauses where one starts. Pairs of two moving parts are skipped (as
  checkTravel). Measured: ▶ 60 fps on / off in the crank, robot arm and swinging-arm demos (gantry 48–52, as without);
  scans 1.7–5 s in the background. AI: drive_mechanism `collisions`, `stop_at_collision` (answers the bands),
  get_assembly `collision_bands` / `collisions_now`, check_travel's bands. tools/e2e_mech_collisions.py.
- **📎 A clip goes with its part; a chain span keeps its end (2026-10-30)** (the demo builder's findings). clipAt:
  placeClip, then 🔗 `fixTogether(clip, the point's part)` (HarnessTool.fixOn / hostOf: a clip's point -> the part
  its clip is fixed to), then the point — one undo step (History.mark / squash: the steps since a mark made one).
  chainSpan with a library chain: its first link 🔗 fixed to the span's first point's part, one undo step. A span
  through a chain stores `enter` ('fixed' | 'moving': the end nearer its first point when routed, setSpanChain);
  spanChains takes the path from that end; an older file's is decided once in assembly.load (settleEntries, before
  the history's reset, from the placed matrices). shortLeads: an end on a face whose next point is nearer than
  leadOf (max(r_min, Ø) + Ø) -> a quiet `.hn-note` there ("příliš blízko — kabel potřebuje rovný výstup X mm"),
  get_assembly `too_close`. make_demos.py no longer joins its clips by hand. tools/e2e_harness.py 20–23 (the clip's
  joint; a clip on the motor moved with it, on its axis, deleted with its joint, undo / redo as one step; a span over
  the chain's whole travel in at the fixed end though the moving end came nearer, an older file decided on load; the
  note and get_assembly too_close).
- **🎬 Two cable demos (2026-10-30)** (the owner: two demos that show cable routing nicely). tools/make_demos.py builds
  them through the AI tools, from real library parts: *Portálový pojezd* (portalovy-pojezd) — a carriage on a 60 mm
  beam (a touch, its turn and cross slide locked: ⚙ "Pojezd vozíku" −150 … 150 mm), a NEMA 17 (rigid on it), an igus
  E2.15.16.038 chain of 16 links (its fixed end on the base below the moving end's middle, `followPart` → the
  carriage: the moving end on a block of the carriage, the upper run just above its plate), a Ø7 orange cable from the
  box's gland — two H4P P-clips on pads of the base (a P-clip holds the cable F = 10 mm off its screw: the pads 10 mm
  aside), the span through the chain, an H4P on the carriage — to the motor's side, 🔒 721.2 mm at every travel;
  *Otočné rameno s kabelem* — an arm on a column's pin (⚙ "Otáčení ramene" −90 … 90°), a SICK IME12 in its tip (axis +
  slide locked), 4 loose wires brown / blue / black / white from a gland on the controller's top: ➰ span 1–2 150 mm (it
  leaves the gland upwards, so the slack bows up and comes onto the arm from above — a gland on the box's side made it
  sag through the arm's edge at ±90°), two MB3A tie mounts on the arm. Learned on the way: a clip is put in loose (no
  joint) — on a moving part the demo joins it 🔗 rigid to it, else it stays behind; a span through a chain takes the
  chain's path from the end nearer its first point — that point must stay nearer the fixed end over the whole travel;
  a face end's lead is max(r_min, Ø) + Ø long — the next point (a clip) beyond it (the first two fixed in the app
  since, the third noted: see above). tests/test_demos.py (their chain,
  locks, clips, span, limits), tools/e2e_cable_demos.py (each opened from 🎬; at −max / 0 / max: no taut / through /
  still_hits / too-tight bend, 🔒 length and ➰ span kept, no overlaps; the chain's moving end with the carriage; ▶).
- **AI tools for the new features (2026-10-30)** (the owner: after a batch of features the in-app AI must reach every
  one). The features of 2026-10-29 / 30 checked against agent_tools.py, the page's handlers, the skills and the system
  prompt; gaps a user would plausibly ask for filled (existing tools extended first, three small new ones):

  | Feature | Tool | Status |
  |---|---|---|
  | Hole shape / thread / depth / size as separate properties | add_feature / edit_feature {shape, thread, standard, through, depth} | ok; stale text fixed (hole_type = the old form; head / thread alone = sizes as given) |
  | Hole dimensions (distances from edges / axis / middle) | add_feature / edit_feature `from`; get_model `from` | **added** to get_model (per position {d, from, ref}) |
  | Hole dragged on its face with snap | edit_feature {points, from}; gui_action {at, drag_to} | ok (ui-tester line) |
  | Hole position locks `f.lock[i] = {x, y}` | add_feature / edit_feature `lock` (true / false / per position); get_model `lock` | **added** |
  | Thread rows in the suggestions | gui_action suggest; edit_feature thread / set_look threads | ok |
  | Mechanism min / max, "set min / max here" | set_travel {min, max: number \| "here"} | **added** "here" (Assembly.limitHere) |
  | Ball joints, springs, check valves | snap_faces ball / seat / spring / rigid; set_travel follow | ok |
  | Two-face joint in either order; ∥ on an axis | snap_faces (swaps; turns about the pin) | ok (described) |
  | Probes and receptacles; library_pair; screws + nuts + washers | library_search, library_add, library_pair {role \| set} | ok; system prompt lists them now |
  | Cable clips; igus chains | library_search (clips / chains named), library_add; edit_harness clip | description **fixed** |
  | Chain travel, links, moves with | edit_chain {links, travel, moves_with, name, remove} | **new tool** |
  | Harness points: locks | edit_harness lock_points / unlock_points | ok |
  | Harness points: insert / delete / reorder / move | edit_harness insert_points, remove_points, order, set_points | **added** |
  | Axis snap ("point at the centre of this face") | add_harness / edit_harness {part, face} (a flat face's frame centre, a hole's axis) | ok (described) |
  | Span lengths, loops, locked total, taut | edit_harness spans, length_locked / length; taut | ok |
  | Collisions with their spans | through_at, still_hits, detour_points | ok (description names them now) |
  | Clips at points; chains on spans | edit_harness clip / chain | ok |
  | Tolerance, fit, roughness chips | sheet_edit dims.tol, fits, roughness, texts.surface | ok (drawing lines in automation-design) |
  | Missing dimensions with views | get_sheet check.missing, sheet_edit add {missing, view} | ok |
  | A dimension moved to another view | sheet_edit move {id: {view}} (otherViews / moveDim) | **added** |
  | Title block edits | sheet_edit texts, template, title_style … | ok |
  | Dock widgets: layout, autosize, rows | set_layout {widget, place, at, fold, auto_height, rows, reset} | **new tool** (leftdock.js layoutHandlers) |
  | Suggestions closed / opened, Automatically | set_layout {suggestions: {closed, auto}}; gui_state suggestions | **added** |
  | Bottom row: Joints / Dimensions | set_view {joints} (setShowKind) / set_view {sizes} | **added** joints |
  | 📏 Measurements table | measure, list_measurements, clear_measurements | ok |
  | Versions graph, variants | list_versions … delete_variant | ok |
  | ⏺ Recording | start_recording, stop_recording, get_recording, get_recording_screenshot | ok |
  | 📄 New project | new_project {new_window} (newproject.js newProjectHandlers: answered, then the page starts again) | **new tool** |
  | Right-click OK; mouse side buttons | — (OK / undo tools do it) | no AI need |

  Wiring: TOOL_LABEL + Czech (edit_chain, set_layout, new_project; the missing Czech of routing / changing a cable),
  tests/test_agent_wiring.py HANDLER_BLOCKS (chains.js, leftdock.js, newproject.js), skills — model-a-part (hole
  properties, locks), assemble-parts (min / max here, points, chains, joints shown), automation-design (fits, roughness,
  move to a view), teach-the-user (the screen itself), ui-tester (the newer features' GUI vs tool). Test:
  tools/e2e_ai_features.py (45 checks, through /api/agent/call). Left out: get_sheet listing each dimension's other
  views (the move error lists them); a chain's own MCP tool for adding one (library_add does).

- **⇤⇥ Limits where the owner looks (2026-10-30)** (the owner: "v mechanismech chybí nastavení min max limitů").
  mechanism.js: under each row's slider limHtml — "⇤ min … max ° ⇥" as borderless inputs (typed in place, Enter / Tab
  sets, Esc as it was), "full turn", or "no limits" + ⇤⇥ Limits (MechanismPanel.firstLimits: the free stretch around
  the driver from the last ⚠ Check the travel — `checked[key]` {min, max, n, hits}, a full turn wrapping past 0 —,
  else Assembly.firstLimits ±90° / ±10 mm); ✕ off; ⋯ ⇤ Set min here / Set max here ⇥ (Assembly.limitHere: one end at
  motionPos, the other kept or as far again). Not for a driver inside a ⚙ moving sub-assembly (shown, not editable).
  assembly.js: the part panel's button reads "⇤⇥ Limits" (translated tooltips), ⇤ here / here ⇥ next to min / max;
  partItems → limitItems (the driving motion, else one with limits, else a turn / slide on an axis): Limits of its
  motion… (on + the panel's min focused), Min here / Max here. No new AI tool (set_travel). tools/e2e_mech_limits.py.
- **📎 Cable clips and ⛓ energy chains (2026-10-30)** (the owner: "do toolu kabelů umožni vést kabelovým
  Schlepperem… a taky pro dané body nějaké běžně dostupné komerční chytky na kabely"). library/cableparts.json — only
  parts whose drawn sizes are all in the makers' data (links per part, no vendor CAD files):
  HellermannTyton HP P-clamps H1P–H8P (D, F, WT, W 10, FH 4.2 from the 2024 catalogue p. 232 + the product pages),
  MB3A / MB4A / MB5A tie mounts (L, W, H, G, F, FH: the MB series page), T18R / T30R / T50R ties (L, W, T, the head
  where given, bundle Ø); igus e-chains E2.10, E2.15, 14, 10 (pitch, hi, ha, the Bi and R lists and the article
  numbers from igus.eu / igus.com; Ba = Bi + the side walls of the one fully published article per series — the
  cross-section drawing shows the same side parts at every width). Left out: DIN 3016 / DIN 72571 rubber-lined metal
  clamps (no complete drawing found), igus mounting brackets (their sizes are not on the pages), screw-on tie mounts
  other than MB (the MB ones have holes), profile-slot clamps, E2.26 / 2400 (no cross-section drawing found).
  Item data: `cable` {axis {o, d, d2}, dmin, dmax}, `mount` {kind, o, n, screw, hole, seat, holes}, `chain` {pitch,
  Bi, Ba, hi, ha, R, dmax}; pairs: P-clamp ↔ ISO 7045 M4 (pairs.js: a clip's screw head on its mount `seat`, its
  length seat + 1.5 d), MB mounts ↔ T18R. build.js: `{R:03}` in texts; the second choice's own name (R) kept as the
  part's `library.length`. auto3d/cableparts.py = the same math (tests).
  **The API for the harness** (web/js/library/cableparts.js; app.js calls `useLibrary({items, addPart})`):
  - `clipsFor(d)` -> [{item, size, dmin, dmax, kind, mount, label}] — per clip item its smallest size that holds Ø d,
    the snug ones first (Ø6: H3P, then MB3A); `cableRange(item, size)`, `clipFrames(item, size, dc)`.
  - `placeClip(asm, choice, point, normal, cableDir, {d})` -> {inst, part, size, axis: {o, d}} — the clip's mount
    point on `point`, its mount normal against the face's `normal`, its cable axis along `cableDir` (laid onto the
    face); `axis` is where the cable then runs (world): move the harness point there. `clipMatrix(frames, …)` pure.
  - `chainPath(chain, moving)` -> {segs (line, arc, line), points, pointAt(s), length, lower, upper, travel, ok,
    links [{a, b}], fixed / moving {o, d (along the path), n}} — `moving` a travel or a world point; in the world when
    `chain.matrix` is given. In an assembly: assembly/chains.js `chainRoute(asm, "C1" | first link "I4")` (the same,
    laid out now), `travelOf`, `chainsSummary`.
  - Wiring for the harness job: on a harness point **📎 Clip here** = clipsFor(bundle Ø) -> placeClip(point, its face's
    normal, the cable's direction there) -> the point moved onto `axis.o`; on a span **⛓ Route through an energy chain**
    = the span's points replaced by chainRoute(...).points (fixed end -> moving end), re-read each draw so the cable
    moves with the moving end.
  assembly/chains.js: a chain item put into an assembly (the 📚 window or library_add) is its first link placed + a
  record `chains` [{id, part, links, dims, travel, follow {inst, base, at}}]; the other links drawn as one
  InstancedMesh (chainPath's pins, y across kept in the bend), red when out of reach; its panel: Links, Travel slider,
  Moves with (a part: its moves along the runs move the end), ✕; the BOM counts its links (linksOf, bom.js);
  get_assembly `chains`; undo; the view's fit takes the links. Not done: the other links in STEP / collisions (only the
  first link is a kernel part), a chain MCP tool of its own (library_add puts one in; get_assembly reports it).
  Tests: test_cableparts (frames and ranges of every clip size, clips_for, catalogue numbers, the U = 2 × run + πR and
  its ends for two travels, each part built by the kernel to its sizes), e2e_library_cableparts (ALL OK),
  e2e_library_build 317/317.
- **Booleans leave their arguments alone (2026-10-30)** (app reports: a Ø4 hole down a pin cut nothing, then −891 mm³
  and two solids; a Ø4 cut through −227.9 and two solids; a 3 mm slot cut +189.8). kernel.bop ran OCCT's booleans
  destructively: an argument's edge whose tolerance had to grow was grown in place — on the steps' bodies that doc's
  prefix cache keeps and every preview cuts again. Two hole previews grazing the pin's rim grew its top edge to 12 mm,
  and every later cut of that body went wrong. bop now sets SetNonDestructive (a sub-shape to change is copied into
  the result; the history still names it for _carry). tests/test_kept_shapes.py: the report's part, the previews,
  then the hole (through and 24 deep), the cut and the slot — analytic volumes, one watertight solid, STEP read back;
  the kept body's tolerance unchanged (the three tests reproduce the report's numbers without the fix).

- **🔗 Library parts that go with each other (2026-10-29)** (the owner: "i u šroubů napáruj matice + podložky … a
  projdi knihovnu, jestli tam nejsou další věci k párování"). An item's `pairs` [{ref, role, back, size: "same" | a
  key, qty}], written on one side; auto3d/library.py link_pairs mirrors them (`mirror`, `from_size`) and drops a
  pair to a missing item; check_item checks them. Added: the six machine screws ↔ ISO 4032 / DIN 985 / DIN 562 nuts,
  ISO 7089 washer (not the countersunk ISO 10642), ruthex insert — same thread; standoff M/F ↔ ISO 4032 nut and ISO 4762
  screw; Würth WA-SSTII M3 ↔ ISO 4762 M3 (qty 2); INGUN GKS-100 ↔ KS-100, GKS-050 ↔ KS-050; SMC CDQ2B ↔ D-M9 — 43
  written, 86 links both ways. Not added (not in the library, or not certain): DIN 471 / 472 circlips, shafts / collars,
  ISO 7090 / 7092 / 7091 / DIN 127 washers, T-slot nuts, KQ2 fittings to cylinder ports, CDJ2 + D-M9 (needs a band).
  web/js/library/pairs.js: companions / goesWith (a size the other has), pairRows (the assembly's table for a placed
  library part: ＋ Nut M5, ＋ Washer M5, the rest under ⋯; a screw: ＋ Set: nut + 2 washers), addCompanion (built,
  put in once as a part, placed on the host's Z axis: a washer under the head — the screw's touch joint lifted by it
  —, the second washer and the nut under the parts the screw holds (fasteners.js partsAlong, standard parts and
  companions skipped; nothing held: under the head), a screw with its head on a nut / washer / insert / standoff, a
  probe at the receptacle's zp, a receptacle under a probe — it then holds the probe, 📌 moved to it; joined Concentric
  on the closest round faces; a probe's along slide limited to its max. stroke and named Stroke). Instances keep
  `pair` {host, role, slot}. The 📚 window: *Goes with* (show it / ⤵＋ both into the assembly). AI: library_search
  `goes_with`, library_pair {part, role | item | set}. Tests: test_library TestPairs (two ways, threads equal, a
  washer's hole over the screw), e2e_library_probes (probe ↔ receptacle seat and stroke, M5 set stack, library_pair).

- **📚 Test probes and receptacles (2026-10-29)** (the owner, an ICT / FCT tester maker: "knihovny pouzder a jehel od
  INGUN, ECT a KESACON … pokud si nejsi jistý rozměry, tak je do knihovny nepřidávej"). library/probes.json: INGUN
  GKS-100 / GKS-075 / GKS-050 probes (17 items by series and head style, 45 variants by exact order code + INGUN item
  no., spring force, preload, current), INGUN KS-100 (30, 30 05, 30 25, 30 40, 30 93) and KS-050 30 E08 receptacles,
  KESACON MPI100 / MPI075 / MPI050 flat-tip probes (12 variants). Sizes from the INGUN product pages and datasheet
  drawings (length, barrel / plunger / head Ø, plunger and head lengths, head angle), each checked against INGUN's free
  STEP model read with the app's importer (a STEP that disagrees: the part left out); a receptacle's collar thickness
  and solder cup from the STEP; the probe's seat from the maker's installation-height lists (the bore: the probe's
  barrel down to it). KESACON: its 2025 catalogue (pp. 11, 14, 18). Left out: ECT (no tip sizes, no inner sizes of
  receptacles), KESACON receptacles and INGUN KS-075 (seat or collar not certain), heads with two angles (daggers 291
  / 297, 207, 238, 319, 222, 225, 289) and the GKS-050 214 / 297 (STEP ≠ datasheet). Fields: accuracy "catalogue"
  (📐 Dimensions per catalogue), name_cs / description_cs, datasheet / cad / page links (no vendor files in the repo).
  The 📚 window lists a three-level category under its maker's heading (closed until clicked), searches Czech words,
  series and item numbers; INGUN shop link. Tests: test_library_probes (each entry built by the kernel to its sizes
  within 0.01 mm, catalogue numbers, links, searches), e2e_library_probes, e2e_library_build (253 builds).

- **gui_action `mods` (2026-10-29)** (an app report: the AI could not test Ctrl+click multi-select): mods = ["ctrl" |
  "shift" | "alt" | "meta"] held during a click — at / pick / at_mm / a drawn thing (the pointer + mouse events carry
  ctrlKey …) or a control (its click event). Test: e2e_ai_gui.py — F2:end, then the front face with ctrl: both
  selected; a plain click: one; a wrong key refused.
- **gui_action `at` = a point of the AI's picture (2026-10-29)** (an app report: a fillet click meant for an edge
  landed on the face). get_screenshot is 1200 × 900 whatever the view's shape, but `at` was 0 … 1 of the view on
  screen (another aspect, and a narrow view fitted from farther): a point read off the picture missed by tens of px.
  Now view.snapshot keeps the camera that drew it (`view.shot`, `cameraState` / `setCamera`); every get_screenshot is
  noted (agent_more `noteShot`: a 3D view's camera, the window's scale for ui, the sheet's paper). gui_action `at` /
  `drag_to` are its pixels (or 0 … 1 of it): while the click is dispatched the view holds the picture's camera (not
  drawn: `view.held`), so picks and edge snapping see exactly what the picture showed; the view's own camera is put
  back after (a drag that turned it: kept, its shape the view's). `pick` answers `at` in the picture's pixels;
  gui_highlight `at` follows the 3D point there. No picture of what is on screen: 0 … 1 of the view, as before.
  Test: e2e_ai_gui.py — a block's vertical edge projected with the picture's camera, clicked in ◜ Fillet at
  1600 × 800 and in a narrow view: that very edge picked (the old fractions: none / another).
- **Two-face joints in either order; ∥ ⟂ ∠ ranked up; Esc (2026-10-30)** (the AI's report: the parent's face first,
  then the child's -> "join them the other way round"). addJoint now swaps the two when `to` (through others) hangs
  on `from`: the child moves; it refuses only when neither can move. Two flat faces list Touch, ∥, ⟂, ∠, Gap, Flush
  (Flush / 〰 first as before when they face the same way / a spring); one flat face ranks ∥ and ⟂ right after Flush
  (∠, Tangent, 〰 under ⋯ Show all). Esc in the assembly also works with a slider / check box focused (it was
  ignored as typing). Esc with the view focused already cleared a two-face pick (also through gui_action key) — not
  reproduced; covered by the test now. Test: e2e_assembly_twoface.

- **A click picks what is in sight (2026-10-29)** (the AI's report: a click on a thin plate's side face picked a hole
  hidden behind it). The assembly's `roundEdgeAt` (a click near a circle takes its round face) and the snap points
  (`snapNear`: corners, middles, centres) did not look at depth: a hole's rim inside a 4 mm plate, a few px from the
  click on its side, won. Now AsmView.sees(point) casts a ray to the point (a surface before it: hidden), roundEdgeAt
  takes the nearest circle in sight, and snapNear takes a `seen` test (measurePoint passes it). Test:
  e2e_assembly_thinside.

- **∥ on a part held by a pin keeps it on the pin (2026-10-29)** (the AI's report: a ∥ joint on a sub-assembly hanging
  on a ◎ concentric joint moved it 24.7 mm off its axis). joints.js turned a later joint's part about its own face's
  centroid — about the right direction, but off the axis line; and ∥ always wanted the faces facing the same way, so
  faces 2° off facing away turned 178°. Now an axis joint's `fixed` carries its point (`o`) and later joints turn about
  that line (`pivotOf`); a new ∥ is made the way round the faces stand (`flip`); a new ∥ / ⟂ / ∠ that the part's free
  turn cannot satisfy is taken out again with a reason (`turnOnlyRefused`: a toast, snap_faces an error). Test:
  e2e_assembly_parallel_axis (the solver alone in one pass, and the assembly).
- **⏺ Recording of moves (2026-10-30)** (the owner: "the AI should see what I do — look what I'm doing, this is the
  problem"). web/js/recorder.js: the top bar's ⏺ (#recBtn) or the AI's start_recording {reason} starts it; it runs until
  stopped (■ Stop in the pill, ⏺, stop_recording), across workspaces / parts and a reload (sessionStorage: the
  newest 2000 events, a `reload` event). Cheap (2026-10-30, the owner: "with recording on it is almost impossible to
  do anything"): the copy was the whole log + every picture JSON-stringified on each event (35–60 ms per save with a
  long recording) and a screenshot one 70 ms task — now a3d.rec is a small header, a3d.rec.c<k> chunks of 100 events
  (only the changed ones written, at most once a second, in requestIdleCallback; at once on pagehide / hidden),
  a3d.rec.s<id> one key per picture (written once); a drag's samples are numbers (the view's box read on the press),
  what is under the cursor only on press / release; the pill's text set only when it changes, placed in an animation
  frame; screenshots when idle via screenshotUI {canvas, width, slice} (the page walked as a generator in 8 ms slices,
  no PNG round trip, no noteShot) and toBlob; capture listeners passive; recorder.cost times its handlers. Headless
  Edge, robot arm demo, a full log: longest recorder run 62 → 1 ms per interaction, a screenshot 72 → 14 ms. The pill: fixed, at the top centre of the visible view under its toolbar and
  hint, red, a slow pulsing dot, the time, "(started by the AI)". Hooked centrally: document pointer events (capture) —
  a click {button, keys, at 0 … 1 of the view, px of get_screenshot {ui: true}, on: what is under it as the tools name
  it (modeler view.pick / pickEdge -> edgeRef / measurePoint snaps, a sketch point [u, v], assembly pickInst, a sheet's
  [data-dim] …)}, a held button: one `drag` event with its path sampled every 50 ms / 8 px, of view / object (the
  view's controls on or off), from / to; no plain movement —, `click` (a control's label; a suggestions row: `suggest`
  {row, table, about}), keydown (named keys and shortcuts, not typing), input / change (`value`, once per value),
  wheel (`view` zoom, merged), History.watchers (new in history.js: undo / redo, and the snapshots diffed: steps,
  parts, joints, couplings, harnesses added / changed (field: old → new) / deleted), `a3d:select` (suggest.js
  showSuggest: what is selected, its refs), a MutationObserver on #toasts (every message, level + text). Screenshots
  (agent_more screenshotUI, 800 px PNG, the clicks of the last 5 s / the drag drawn in red) at an error / warning toast
  and a step done, at most one every 5 s each, 12 kept. AI: start_recording, stop_recording, get_recording {since, last,
  paths}, get_recording_screenshot {id} (agent_tools.py, the system prompt's "Watching the user", teach-the-user
  skill); the chat (agent.js): 📎 Attach the recording (n events) on a stopped one -> its events as lines with the next
  message. Tests: test_agent_wiring (recorder.js handlers), tools/e2e_recording.py (29 checks), e2e_agent. Left out:
  saving a recording to the data folder; a sketch's shapes are diffed as "shapes: n → m items", not shape by shape.

  1600 × 800 and in a narrow view: that very edge picked (the old fractions: none / another). 2026-10-30 (an app
  report from before this: ui pixels "off the screen", a drag by fractions turned the view): checked for
  get_screenshot {ui: true} too — a harness point in ✎ Edit points dragged by ui pixels and by the fitted picture's
  pixels lands where aimed, the view does not turn; pixels outside the last picture are refused with its size.
- **The AI sees the suggestions table (2026-10-29)** (the owner: "zdá se mi, že agent nevidí suggestion table"). It
  did not: gui_state listed the table's rows as plain buttons among the rest (where: panel, no title, no order, nothing
  marking them), the rows under ⋯ Show all not at all, and get_screenshot drew the 3D only. Now suggest.js keeps each
  table's rows on its box (`suggestTables()`: title, refs, every row with its section and rank, shown or hidden;
  `runSuggestion()` opens ⋯ Show all for a hidden row, then back to the top rows) and agent_more.js gives the AI:
  gui_state `suggestions` {title, about (what is selected, as the ✨ refs name it), hint, where, rows [{n, icon, label,
  section, rank_pos}], more, all, show_all} and `where: "suggest"`; gui_action `suggest` (a row by its label — Czech or
  English, part of it, no accents needed) and `pick` (a face "F2:end" / a part "I2" / "I2 F2:end" clicked where it
  shows on screen: the middle of where a scan of the view hits it, not under a panel); every gui_action answer has the
  table now. get_screenshot {ui: true}: the window as the user sees it, drawn box by box from the page (no HTML-to-canvas
  library: backgrounds, borders, text, fields' values, the view's canvas and the sheet's SVG; z-index overlays last),
  the text giving the table's box. No separate get_suggestions tool: pick + gui_state answer "what would the table
  offer here". The prompt and the skills (ui-tester: suggestion-first, rank_pos judged; teach-the-user: lead through the
  table's rows; model-a-part, assemble-parts) teach it. Tests: test_agent (schemas), e2e_ai_suggest.

- **🔌 Cable harness in the assembly (2026-10-29)** (the owner: "simulovat kabelové svazky … zvolím tloušťku kabelu,
  minimální radius a pak jen naklikám body"). web/js/assembly/harness.js (HarnessTool; assembly.js only hooks it:
  toolbar, suggestions, panel, tree, draw, pointer, keys, history, summary, handlers, stepTree): assembly JSON
  `harnesses` [{id H…, kind cable | wires | ribbon | sleeve, d, color, wires [{d, color}], pitch, r_min (none: 5 × Ø),
  reserve %, points [{inst, at (in the part), n (its face's normal: lies on it, Ø/2 + 0.5 off; none: a hole's centre)} |
  {xyz}]}] — a point on a part follows it (the drawn mesh's matrix: mechanisms, drags, explode). The route (2026-10-30
  shaped by default, the owner: "by default se má tvarovat podle radiusu"): each corner an arc of r_min tangent to both
  legs; two corners whose shared leg is too short for both arcs (an S / Z step, two 45° turns) moved apart along their
  outer legs — the least move that fits, scanned + bisected, bounded by what the corners beyond want (route → _spread
  / spread, the same in Python and JS); only what nothing fixes (a short end leg, a U narrower than 2 r_min) gets the
  largest radius that fits (a leg shared by two corners split by what each wants) and a quiet amber note on the spot
  "R 6 mm — na 15 není místo" (no red overlay; none while the corner hangs on the point under the mouse); lines +
  arcs, its length live. 🔒 Locked length (`length_locked` mm; the panel's button by the length, the suggestions,
  edit_harness length_locked / length): shape(points, r_min, spans, total) bows every span alike — two points put in
  each span (its middle ± r_min, h off it, _bowed) out of the corners at its ends (_sag: the incoming leg's direction
  minus the outgoing one's, square to the span, + a little −z), h = λ × the span's length, λ bisected until the
  shaped length is the locked one —, the fillet routing above rounds them; shorter than the straight route: straight,
  `taut` {short} — drawn red, a note in the view and the panel, a toast once (as a collision), get_assembly `taut`.
  The step's `length` gives STEP / GLB the same.
  Points (2026-10-30, the owner + an app report on placing them exactly): a point clicked on a face keeps its `face`
  name; 🔒 locked = {inst, at, n, face} (moves with the part), 🔓 = {xyz, on: {inst, at, n, face}} (stays in space;
  lockPoint sticks it back where it is then); `adopt` takes a loaded point in space lying on a face (6 axis rays, Ø/2 +
  0.5 ± 0.75 off) as locked to it. The panel's points list (pointsList / pointsHandlers: part · face, x / y / z typed,
  ↑ ↓ ✕, ＋ between, 🗑 all, the hovered row lit — this.hl), editPts for every change of the points. candidate():
  a flat face with a cylinder of the part square on it round its centre (axisOf: a pin's top, a ring) snaps to its
  centre (frame.o) before a hole's centre snap; Alt + click takes the face behind (altDepth; again at the same spot:
  one further; its outward normal); ◎ centreItem moves a point to its face's centre / onto a hole's axis. checkThrough
  keeps the first spot inside each part and the span it is on (throughAt: ⚠ label there, get_assembly `through_at`).
  The panel's length is the cable's own (the next point's preview "· s dalším bodem …" beside it; no preview with the
  mouse off the view — it made the label jump on ✎). AI: get_assembly `point_list` [{n, part, locked, face, xyz}],
  edit_harness lock_points / unlock_points.
  ➰ Spans (`spans` [{from (0-based), length}]): shape(spans=) bows each span with a length of its own (its depth
  bisected for that length, Gauss–Seidel ×4 as a bow turns its neighbours' end corners; a span's length runs from
  corner to corner, a corner's place the middle of its arc, so they add up to the whole); they win over length_locked
  (totalIgnored, said in the panel); too short: that span straight, taut {span, short}. editPts keeps a span while its
  two points stay neighbours. UI: this.span (the chosen cable clicked again: cableNear's leg; the list's length
  between two rows), the suggestion ➰ Smyčka / volná délka -> one input (empty: its length now). The step's `spans`
  give STEP the same. AI: edit_harness spans [{from: point number, length | null}], get_assembly `spans`.
  Clear of the parts (2026-10-30, the owner: "kabel by měl … nenarážet do ostatních objektů"): leads — an end with a
  face normal gets a point out along it, lead_of = r_min · tan(half the turn to the next point, ≤ 160°) + Ø (at least
  r_min + Ø) —; avoid / avoidRoute — the shaped route sampled every rad / 2 (rad = Ø/2 + 0.5), each sample probed
  (Python: a callable, the tests' signed distances; the browser: the parts' meshes — inside by ray parity, out through
  the nearest of 14 directions; outside nearer than rad: away), the deepest hit of each leg becomes a detour point
  (push + rad / 2) or moves the leg's own detour point further out, shaped again, ≤ 6 rounds; the clicked points stay.
  The browser keeps the result per harness for the points it was worked out for (AVOID, keyed by the points, end
  normals, r_min, Ø, lengths): avoidAll runs 400 ms after a change with checkThrough, so a drag shows the leads at once
  and the detours when it stops. routeAt / docRoute -> routeOf -> routeE (shape on the expanded points, bends / spans /
  taut told back by the clicked points). The export sends those points (harnessStep) — STEP is the drawn cable.
  Markers "kabel koliduje s …" where it still goes through / grazes a part; get_assembly detour_points, still_hits,
  spans_not_kept. The detours are found on the taut route; a locked length's slack then bows on the legs but the
  leads (`still`, sent in the step too); a span with its own length gets no detours (its length wins, a hit is
  told) and, holding a lead, its slack on its longest other leg (its target corrected until the whole span is
  right). A bow sits in the straight part of its leg (between the end corners' arcs), so the length grows smoothly
  with its depth. A bend within 3 % of r_min counts as kept (no note for a lead's corner a hair tighter).
  📎 ⛓ (2026-10-30, with library/cableparts.js and assembly/chains.js): a point {inst, at, clip} sits on a clip's axis
  (clipAt: clipsFor(outerD) — the snuggest, or the one chosen in the suggestions — placeClip on the face point (the
  point minus its lift) along the neighbours' direction, then the point at axis.o in the clip's frame, locked to it);
  editPts notices a clip whose point went (this.orphans: "the clip stays" + ✕). 📎 preview and pick list (2026-10-30, assembly/clippick.js — the
  owner: "u výběru příchytek by mělo jít vidět preview příchytky … a taky výběr ze seznamu"): a clip row's hover(on)
  (the suggestions, the list; focus too) -> ClipPick.ghost: clipPose (the point's face spot, normal and the cable's
  way; a point with a clip: from that clip's mount frame) -> cableparts clipPlace (the same matrix placeClip puts it
  at) on a see-through yellow mesh + edges from clipGeometry (the kernel's body, cached per item|size; only moved),
  a CSS2D label (name · Ø range · mountText). The list (floatBox kind 'clips'): clipChoices(Ø) — every clip / tie
  mount / tie size, the fitting ones first, the rest greyed with why (small / large / tie) — grouped by type, ↑ ↓
  through it; a click clipAt (a point with a clip: swapped — the new one put in, the point moved onto it, the old one
  removed, one undo step); ☐ for all points on faces: clipAll (one undo step). It closes when the chosen point
  changes, on Esc, ✕ or a pick. auto3d/cableparts.py clip_choices (test_cableparts). ↔ Slack (2026-10-30): slackOf(h, r) = spans − tightSpans (taut: − short); labels hn-slack at each span's middle
  (unstacked with the notes), the rows' hn-sl; showKinds().slack (default off), the panel's ↔ switch the same;
  harnessFacts span_slack_mm, spans[].slack_mm. ⚠ Notes (2026-10-30): short text + title; showKinds().warnings (suggest.js, the bottom row's Show: group, shown
  when the assembly has harnesses) — off: no hn-warn / hn-clash / hn-note, the panel's hn-hidden count; unstack()
  after every frame's CSS2D labels (labels.render wrapped): bottom-up, a label over one placed before is lifted; a
  harness not chosen: one hn-sum "⚠ n" (all in its title). 🪄 Auto-fix (2026-10-30): warnings(h) = avoidOne + routeAt + throughOf (taut, bends, parts hit, short leads);
  autoFix tries per round the first kind that has tries (taut: lengthen / unlock; bends: drop / move free points;
  hits: free points to a side of the part's box, a point put in round it; short: the next free point out along the
  normal), each try lengthened when it pulls the cable taut, keeps the best that lowers the count, ≤ 8 rounds, one
  commit. AI edit_harness auto_fix. ➰ Loop editing (2026-10-30): litSpan (the row under the mouse, the span being typed, the span chosen) -> a blue
  tube over that stretch of the route (by its spans' lengths along the RouteCurve), the rest's materials at 0.35;
  tightSpans(h, r): routeE through the same E (leads, detours) with no own lengths and no lock; the slider's range
  [tightest, max(3 × chord, chord + 300)], 'input' -> spanSet + drawNow once a frame (this.sliding keeps the panel),
  'change' -> setSpan (one undo step). 🔌 Connection points (2026-10-30): a point {conn: true | false}; connOf: said, else an end on a part (not a clip);
  excuser(h, pts) excuses a connection point's part within max(lead, 5 Ø) + Ø of it — probe() skips it (no detour),
  throughOf skips its samples, shortLeads leaves that end out. Row 🔌 / suggestion toggle (setConn, one undo step);
  lockPoint keeps conn; AI edit_harness connect_points / disconnect_points, point_list `connection`. A span {from, chain: C…} (spanSet
  keeps length and chain on one entry): spanChains reads chainRoute now, from the end nearer the span's first point;
  expandE puts the path into the points before the span's last point (tag 'chain': no slack, no detours, its hits not
  told); the AVOID key holds the path's ends and the draw key the moving end, so a chain moved re-shapes the cable.
  chainSpan with no id: chainsFor(outerD, r_min)[0] (Bi ≥ Ø + 2, dmax ≥ Ø, R ≥ r_min; the smallest), placeChain at the
  span's first point, its runs along the span, addChain. The step sends the points with the path (STEP has it).
  avoidAll leaves the harness's own clips and chains out of the probed parts. AI: edit_harness clip {point, item?,
  size?}, chain {span, id | null}; point_list `clip`, spans `chain`. Drawn as TubeGeometry along a by-length curve (wires twisted round the centre, a ribbon flat — ExtrudeGeometry
  turned level at its start —, a sleeve corrugated); ⚠ through a part: the centre line's samples tested by ray parity
  against the parts' meshes. BOM (bom.js): a line per wire / cable "Vodič Ø1,5 mm hnědý — 1 350 mm" (+ reserve, up to
  10 mm), kind harness, no position. Export: a part per harness with one step {type: "harness"} (doc.py ->
  auto3d/modeler/harness.py, the same math in Python; kernel.pipe_body: circles / a ribbon's rectangle swept with
  MakePipeShell along lines + arcs, one solid per wire, faces <id>:w<k>:… painted their colours) — STEP / IGES / GLB
  and the assembly's drawing sheet (sheet.js flatten). AI: add_harness / edit_harness, get_assembly `harnesses`
  (length, bends_too_tight, through_parts); the assemble-parts skill. Demo *Řídicí box s motorem*. Tests:
  tests/test_harness.py (straight, L = straight parts + πR/2, an L sampled G1 with curvature radius ≥ R, a Z / two
  45° turns shaped to R, only a U turn flagged, 🔒 400 mm kept ± 0.5 with the ends moved closer (curvature ≥ R,
  sagging), taut with the shortfall moved apart, a locked cable's solid π(d/2)²·L + STEP, fewer than 2 points, a
  span 140 mm with its ends 100 / 130 apart (± 0.5, curvature ≥ R) and 150 (taut by 10), its solid, an end on a
  pin's top (lead straight up, the tube's least distance to the pin > 0), a span through a box's corner (a detour,
  anchors kept, curvature ≥ R, least distance > 0), bundle Ø 1 / 3 / 7, cable volume
  π(d/2)²·L + watertight + STEP round trip, 4 wire solids, ribbon / sleeve, errors), tools/e2e_harness.py.
  Left out: a sleeve is solid in STEP (not hollow); wires are laid side by side in STEP (twisted only on screen); the
  through-a-part check tests the centre line, not the Ø; a point on a part inside a moved sub-assembly is on the
  sub-assembly as a whole.
- **Floating boxes resize from every edge; the suggestions never show a scrollbar (2026-10-29)** (the owner: "never
  show a scroll bar in the suggestions table, let me resize it by any edge"). floatbox.js puts invisible zones on each
  floating box (`.fb-edge[data-dir=n|s|e|w|nw|ne|sw|se]`: 6 px along the edges, 10 px at the corners; the bottom-right
  one stays the visible `.fb-size` grip) with the matching cursor (also while dragging: body `--fb-cur`); dragging the
  left / top side moves the box so the right / bottom side stays put; min sizes, the view's edges, the remembered
  place / size and the header's double-click reset as before. The zones show only on a floating box (`.fb-box`), so a
  docked widget / docked suggestions have none; the floating table's rows are inset 6 px, clear of them.
  `scrollFade(el)` (floatbox.js): a scroll container with a hidden scrollbar (`.fb-fade`) and a soft mask fade at the
  edge where content is hidden (`fade-top` / `fade-bottom`, kept on scroll and resize) — the suggestions' `.vs-list`,
  floating and docked; the wheel / touch still scroll it. Tests: e2e_floatboxes (real drags on the w / n / e edges and
  the ne / sw corners, the cursors under the mouse at each zone, 40 rows: offsetWidth − clientWidth = 0, the fades,
  the wheel, a click 2 px inside a row 7 px from the edge runs it, docked: no scrollbar, no zones).

- **📏 Measurements table done (2026-10-29)** (the owner: measure more kinds, keep the results in a compact table).
  web/js/measure.js — one MeasureTool per workspace (3D model, assembly), hooked in by toggleMeasure / measurePick /
  clickMeasure: what a click picks decides the kind (no mode menu): a corner / reference point (a round edge's centre
  or an edge's middle only within 6 px — snapWins — else the edge itself), an edge (a line: L; a circle: Ø; an arc: R,
  by its points), a face (area; a round one Ø and its axis), a part (the assembly's Prvky | Díly chip). Two picks:
  point–point (distance, ΔX ΔY ΔZ), point–face / edge / axis (square to it), parallel flat faces (the gap), else the
  angle (acute, 180 − a in the tail), parallel edges / axes (apart; round ones also `alt`: the gap between their
  surfaces — the střed–střed | min chip), part–part: the clearance from the kernel (POST /api/assembly/clearance ->
  doc.assembly_clearance -> kernel.min_distance, BRepExtrema_DistShapeShape; a sub-assembly: its parts as one side;
  `overlap` when they go into each other). The first click adds a row, the second turns it into the pair's; empty
  space starts anew; the tool stays on, Esc ends it. Rows live in the doc (part.measures / assembly.measures: saved
  with it, kept across tab switches and reloads; not in undo) with their marks (lines, dots, a label) drawn in the
  view (view.msGroup). The table: a left-dock widget (`measure-model` / `measure-assembly`) — #, icon, what, value
  (tabular, 70 px, mm in the header), muted tail, ✕; 22 px rows; hover lights the mark, a click suggests copy value /
  row, hide its mark, delete; head 👁 📋 (tab separated) 🗑 (↶ in the toast). The old floating .m-measure box is gone.
  AI: measure also adds a row (table_row, value); list_measurements / clear_measurements. Tests: test_clearance,
  e2e_measure_table (Czech, 1280 × 800, real mouse: 28.284, L 20, Ø6, 5 apart, 90°, hover, ✕, 12 rows, Esc, tab
  switch, 🗑 + ↶, the assembly's clearance 5); e2e_measure_snap / e2e_assembly_measure / e2e_model_inspect /
  e2e_ux_model / e2e_floatboxes / e2e_i18n read the table now.
- **Tolerances, fits and roughness as lists on the drawing sheet (2026-10-29)** (the owner: "pro tolerance ve 2D
  výkresu nabídni seznam tolerancí, to samé u drsností"). The suggestions table takes a row of value chips
  (suggest.js `{chips: [{label, title, on, primary, run}]}`: inline, one click each, the current one ✓, no popup). A
  dimension clicked: ± Tolerance ±0.01 ±0.02 ±0.05 **±0.1** ±0.2 ±0.5 +0.1/0 0/−0.1 +0.2/0 0/−0.2 (again: none),
  "Obecná tolerance (ISO 2768-m)" (✓ while it has none of its own), "Vlastní…" (the typed one, as before); a Ø: Uložení —
  díra **H7** H8 H9 H11 and — hřídel **h6** h7 g6 f7 k6 m6 p6, each chip's tooltip its limit deviations at that size
  ("H7: +0.015 / 0 mm — kolík, uložení ložiska"; sheet/fits.js got H11 and h7). The title block's Drsnost: the Ra chips
  0.4 0.8 1.6 3.2 6.3 12.5 25 µm in its suggestions and under its cell's text box while it is typed in (`.sh-ralist`).
  **Surface roughness symbols** (sheet/rough.js, ISO 21920 / ISO 1302): an edge of a view clicked -> "✓ Drsnost povrchu"
  with the same Ra chips places the check-mark symbol where the edge was clicked (on the edge when it is on top of the
  view, else on a reference line with a leader and an arrowhead); "▸ Výroba" unfolds Libovolná / Obrobit (the bar) /
  Bez úběru (the circle). A symbol is chosen by a click (its own table: Ra, Výroba, Smazat), dragged along its edge or
  away (a leader), deleted with Delete, undone; sheet JSON `rough: [{id, view, edge, k, off, ra, proc}]`. The general
  roughness in the title block reads "Ra 1.6 (✓)" while symbols exist. PDF as drawn; DXF: its own layer "symbols".
  AI: sheet_edit `roughness [{view, edge, ra, process, at} | {id, ra, process} | {id, remove: true}]`, get_sheet lists
  them; a one-sided tolerance "0/-0.1" writes "0/−0.1". Tests: e2e_sheet_tolerances (real mouse, Czech), e2e_ux_sheet
  (the chips instead of the dialogs), test_exchange_formats (the symbol's layer).
- **A made hole dragged on its face (2026-10-29)** (the owner: "dovol mi u děr ji pokud nemá uzamčenou kotu chytit a
  s držením levého tlačítka myši posunout … na snapping pointy dané face"). web/js/modeler/holedrag.js: `holeUnder`
  (no tool on: a Hole step's position under the mouse — the mouse ray on the hole's face plane within its Ø (≥ 6 px),
  the face seen from the front, not behind the part), `HoleDrag` (started past 4 px with the left button down, the
  camera held: snapped by facesnap's `snapOnFace` like the Hole tool — the step's own edges skipped, its other holes as
  keys but not one measured from this hole; a green ring (and head), the snap drawn, the distances as live labels and
  at the mouse; let go: `moveHole` — the point moved, each moved distance re-referenced (a middle -> the nearest edge,
  an edge it went past -> the nearest edge, else the same reference with the new d; a snap onto the face's centre /
  a middle line / a hole / a round edge -> that, through `holeKeyRefs`, split out of clickHole), the step chosen, one
  `commit` (undo step); Esc: `cancel`, nothing changed). Locks: `f.lock[i] = {x, y}` (front-end only; the kernel
  ignores it) — set when a distance is typed (setHoleDist: tag, tool label, panel field; the x / y fields), the
  🔒 / 🔓 button in each row of the Hole panel toggles it; a locked one shows 🔒 on its tag (the tool's label: CSS
  ::before). Locked one way: the drag keeps that coordinate (a snap off that line drops to the grid); both: no drag,
  "🔒 dimension locked" at the mouse. A plain click still goes to clickFace (the hole's centre picked, ◎ Select the
  hole); empty space still turns the view. Left out: moving a hole of a ⁂ pattern / ⇋ mirror copy (only the Hole
  step's own positions), dragging while a tool is open (the tool's own fields / labels do it there). Tests:
  e2e_hole_drag.
- **A hole's properties each on its own (2026-10-29)** (the owner: "typ díry … a to, jestli má nebo nemá závit, by
  mělo být nesloučené"): a hole step is `shape` (plain | counterbore | countersink | d_flat) + `thread` (absent /
  "M5"; the AI may give true or {standard, kind: cosmetic | real} — kind sets the part's 🔩 threads, which stay one
  setting per part) + `through` / `depth` + `standard` (or a plain `d`). Threaded: the hole is the tap drill, else the
  ISO 273 clearance Ø; the head the size's — so a threaded counterbore, a threaded countersink work. Old files: the
  single `hole_type` (clearance = plain M5, tapped = plain threaded M5 …) is still read — holes.py `spec` / `resolve`
  (Python) and holes.js `holeSpec` read both, `setHole` writes the new form (no migration needed: the old one builds
  the same solid, test_old_files_build_the_same). The kernel and the drawing take resolve's output (thread "M5", head
  cbore / csk, hole_type d_flat) unchanged; the callout of a threaded counterbore is "M5 ↧ 10 ⌴ Ø10 ↧ 5.4" (ISO
  order: size, depth, head — as before for any head). UI: `holePropsHtml` / `bindHoleProps` — 4 short rows (Shape:
  4 icons, Thread: Threaded + Cosmetic / Real, Depth: Through all / To a depth + mm, Size: M2…M20 or Custom Ø) in the
  Hole panel and the chosen step's panel; the suggestions: Shape (4), Thread (With thread M5 ✓ / Add thread M5, show /
  hide, real / cosmetic), Depth (one row), Size (±2). AI: add_feature / edit_feature hole {shape, thread, standard}
  (agent_tools schema, model-a-part skill), the old hole_type still taken. Left out: a thread depth of its own (the
  thread runs the hole's depth), a fine / coarse clearance choice (none existed). Tests: test_hole_standard
  (test_properties, test_old_files_build_the_same, test_combinations), e2e_model_hole_standard (rewritten: shape
  icons, Threaded, To a depth, a threaded counterbore's volume and callout, the AI's threaded M3 countersink),
  e2e_hole_suggest, e2e_model_hole_dflat / _head, e2e_thread_default, e2e_select_from_point updated.
- **A hole's dimensions typed again (2026-10-29)** (the owner: "nemůžu nyní v 3D návrhu zadávat kóty k dírám"). Cause:
  since 0e17470 an edited hole opens without placing, and in the tool its numbers on the part were display-only
  (`.hole-dim` pointer-events none; the chosen step's clickable tags are hidden while a tool is open), so a click on
  a distance only said "click ＋ Add position first" — the panel fields were the only way; and a hole snapped to a
  face's middle ({mid}) had no number to type at all (only 🎯). Now: the hole tool's labels (each half of a {mid}
  too) and its Ø / ↓ depth labels open the size editor when not placing (`openDimEdit` with `edit.tool`: `applyDim`
  previews into `cmd.feature`, no undo step, Cancel puts the step back; while placing they stay out of the mouse's
  way — the panel takes the numbers); `setHoleDist` is the one path (panel field, tool label, chosen step's tag): a
  {mid} typed becomes {edge: its left / lower edge, d}. The panel's {mid} row has a number too; a chosen hole's
  {mid} gets its ↔ / ↕ tag. Tests: e2e_hole_dims (new).
- **A chosen hole's choices inline (2026-10-29)** (the owner: "velikosti a typy díry … v další vyskakovací tabulce …
  ukaž všechny možnosti … jen když jich bude moc, tak scroll"; "u díry mi v suggestion chybí zobrazit závit"; "nikdy
  nezobrazuj scroll bar"): `holeItems` replaces the Type ▾ / Size ▾ rows (and their `choose` popups) with sections of
  rows — Type (the six kinds, icon + short name), Size (`holeSizes`, ±2), Thread (a tapped hole: Thread: show / hide,
  Real thread ↔ Cosmetic — `setThreads`, the table shown again; else 🔩 Add thread M… — `threadFor`: its screw size,
  else the M size whose tap drill is nearest its Ø), the current one ✓; one click = `setHoleType` / `setHoleSize`, one
  undo step. suggest.js: a row with `always` shows past the top N (not counted), `on` ticks it (.vs-pin-row: 24 px
  rows); a table's rows scroll with no scrollbar (`scrollbar-width: none`), `scrollFade` puts a fade at the edge
  where rows are hidden (.fade-t / .fade-b; the table grows to the view's height first, no fixed height). Tests:
  e2e_hole_suggest (rewritten: 6 + 5 rows without a popup, one click countersink / M6 exact volumes, Add thread M5,
  Thread: hide; 1280 × 800: scrolls inside, no scrollbar, the fades), e2e_ux_model / e2e_select_from_point updated.
- **One size, every view it can go in (2026-10-29)** (the owner: the sheet's suggestions only ever offered the front
  and the top view, never the right one — the check took the first view a size was found in). sheet.py `places(geo)`
  (sent as geometry.places; a sheet built before it is built again once): per axis of the part and place along it, the
  views that show that place as a point a dimension hangs on — an edge across the axis (visible "e" / hidden "h",
  from the view's visible polylines), a full circle's centre ("c"), the view's box ("b") — in views whose right / up
  is that axis (`_axis`: never the iso view; Section A–A as the right view). Computed on the server because it has the
  projections and is unit-tested there; the browser's check (sheet.js) still decides what is missing. Each missing size
  is one item (id "z:30", "Ø6", "R3") with `cands` — web/js/sheet/dimcandidates.js `withViews`: the views
  drawn that show it, ranked (ISO 129: round 3 > box 2.5 > visible edge 2 > hidden 0, −0.4 a line its extension line
  crosses, +0.5 a dimension of the same step there, then front / top / right); the item's view is the best one.
  Suggestions: "↕ Height 30 (2 views)" rows (suggest.js rows may have `hover(on)`); hovering a row, a Check row or
  the orange ? shows dashed accent ghosts (dimSvg recoloured) in every candidate view; a click on the row adds it in
  the best view, on a ghost in that one (`candDim`: from the view's lowest place, on the outer side with room — not
  into the gap to the next view —, past the dimensions there); "⇄ Move to another view" on a linear dimension
  (`otherViews`: both ends seen in that view), one ↶ step. The AI: get_sheet check.missing [{id, what, views (best
  first), key}], sheet_edit add {missing: id, view?}. Tests: test_sheet_dim_views (a block with a hole and a step:
  height in front + right, depth in top + right, the hole's place only in the top, the step's floor hidden in the
  front / seen in the right, the section), e2e_sheet_dim_views.
- **✂ Section view fixed and capped (2026-10-29)** (the AI's report: a revolved pump body cut at y = 0 showed whole, with
  a jagged ring at z = 0). Causes: a Y cut kept the half toward the iso / front cameras (x and z kept the far half), so
  the part looked uncut; a face lying in the cut (the bottom at z = 0) z-fought with the clip plane — the jagged ring;
  the cut was hollow (no caps). Now (view.js setSection) X / Z keep below, Y behind the cut (⇄ the other side), the
  plane sits 1e-4 × the part's size into the kept side (a face in the cut goes whole), and updateCaps fills the cut:
  web/js/modeler/sectioncap.js slices each part's triangles by the plane into closed outlines (an open one is left
  unfilled), nests them (even-odd: holes) and triangulates them — brick red, an assembly's a little toward the part's
  colour; remade when the cut, a part or its placement changes, and before get_screenshot's picture. Tests:
  e2e_section_revolved.
- **Kernel bugs from the AI's reports (2026-10-29)** (RealSWReports, an apple bottle: a spline profile revolved,
  shelled, bitten from the side). **CoG of a revolved spline body off its axis** (cog_mm [8.8, 0, 59] of a Ø75 × 72
  bottle): a part with a long B-spline edge gets its volume from Gauss-Kronrod (`_volume`), and GK leaves the centre
  unintegrated unless asked (CGFlag) — what it gave was not a centre. Asking costs 1–3 s, so the centre now comes from
  the quick rule when its volume is within CENTRE_TOL 0.5 % of GK's (it integrates the moments too), else from GK with
  CGFlag. The bottle: [0, 0, 31.67]. Tests: test_mass_props (a hemisphere at 3r/8, as arcs and as a 13-point spline;
  a shelled hemisphere at 3/8·(R⁴ − r⁴)/(R³ − r³); a spline cup solid and shelled against its mesh's centroid).
  **A drafted cut of 14 small arcs removed nothing** (25°, 11 deep): BRepOffsetAPI_DraftAngle tilts each wall as it is
  and came back "done" with no valid solid (BRepCheck fails from 10° there; at 10–17° it was valid-looking but cut the
  wrong amount). `kernel.draft` now refuses a result that is not a valid solid, and an extrude's draft then builds
  one drafted prism with LocOpe_DPrism (`kernel.drafted_prism`: the profile offset along the height, rounded where
  walls part; the height passed along the slanted wall, d / cos a; refused when the walls meet before the far end).
  The plain draft stays first (sharp corners, the prismatoid tests). A loft to the offset wire was not taken: the
  offset of this profile changes its edges (the scallops vanish), which a ruled loft cannot follow. The report's
  bite at 25° × 11 mm: "at most 23.14°" (the scallops close up past that); 5 mm deep at 25° cuts / adds
  ∫ area(profile shrunk by h·tan 25°) dh. Tests: test_extrude_draft_of_round_scallops (cut and add, STEP, refused
  when too steep). **A shell after a side cut left the body mostly solid, "ok"** (182 000 mm³ where 2 mm walls are
  35 000): MakeThickSolid comes back "done" with no valid solid when a cut's floor lies near the inner wall (even a
  Ø20 bite 3 mm into a Ø60 cylinder; join type, Intersection mode and tolerance changed nothing). `kernel.shell` now
  checks the result (`_thin_wall`: BRepCheck valid and the volume at most THIN_WALL 1.5 × the outside it keeps × t);
  else `_hollowed`: the body offset t in as a whole (MakeOffsetShape with intersections) is the cavity, opened at
  each flat open face by the cavity moved 1.5 t out through it within that face's slab, and cut from the body (the
  cylinder: its wall bends round the bite). Neither: `Unsizable` "The shell could not be made all over the part — …"
  (Czech added; `_sized` passes an Unsizable on without its search for the most that fits). The report's apple cannot
  be offset as a whole even without the bite (no shell back; likely its 1 mm lip at the neck, gone at 2 mm), so it
  gets that issue — the AI's
  workaround (shell first, then the bite and a plug) stays the way. Tests: test_shell_after_a_side_bite.
  **That test failed 1 full-suite run in 3**: MakeOffsetShape is not repeatable where a face vanishes t in (the
  lip): the same body gave no shell or an invalid "inside" (155 000 mm³, where 2 mm in is 138 000), by where its
  shapes lay in memory — a copy of the body flipped it, so the suite's earlier tests did too. The invalid inside was
  cut out and passed `_thin_wall`. `_hollowed` now drops an inside BRepCheck finds invalid. Test:
  test_shell_the_other_way_not_by_chance (the lip body copied 24 × never hollowed; the bitten cylinder always, alike).
- **🎬 Demo "Pumpička" (2026-10-29)**: the AI's pump rebuilt as a stand-in (tools/make_demos.py pumpicka): a turned
  body (an inlet Ø4 with a 45° seat under a bore Ø20, see-through), a piston with a hollow rod and a 45° seat for the
  outlet ball (concentric in the bore, its turn locked, 6 mm stroke "Zmáčknutí tlačítka"), a 〰 spring Ø18/12 × 20 from
  the bore's bottom to the piston (k 0.3 N/mm), two Ø6 balls ● on their seats' axes with 2.5 mm lifts going ↕ by the
  piston's direction (the inlet lifts going up, the outlet going down) — one ⚙ "Pumpička", no collisions. Tests:
  test_demos (its spring and valve rules), e2e_demos (▶: the piston and both balls move, the spring drawn at the
  piston every frame).

- **Assembly: ↕ by the driver's direction — check valves (2026-10-29)** (report 2026-10-29-203234: the pump's balls
  could not move by the stroke's direction). A motion's limits may carry `follow: {part, key?, at: "max" | "min"}`:
  Assembly.moveFree measures the moved part's position along that motion before and after (any move: a slider, ▶,
  a drag, the AI) and followDirection puts each follower at `at` when it went forward, at the other end when it went
  back (still: stays). mechanism.js lists a follower in its driver's mechanism, not as one of its own; traceOf goes
  there and back for it (the curve drawn in order: a loop showing both stops). The row of a slide with limits:
  "↕ Podle směru pohonu" (the driver: the mechanism whose driver slides most nearly along it) and "<driver> vpřed → na
  max / na min". AI: set_travel `follow` ({part, motion?, at} | null), get_assembly `at[].follows`. Left out: a
  keyframe table (the driver's position → the part's) — not needed for valves; a crank's full turn only goes forward,
  so a valve on a crank-driven piston follows the crank, not the piston (the rule takes the driver's own motion).
  Tests: e2e_assembly_ball_spring (one click picks the piston; forward → max, back → min; the AI's rule at min; ▶ only
  at the stops, both seen; the trace has both; null takes it off).

- **Assembly: 〰 springs (2026-10-29)** (the app's AI, report 2026-10-29-203234: in a pump's mechanism the spring was a
  rigid part, the piston passed through it). assembly/springs.js: `springs: [{id, part, face (its end that reaches),
  onto, ontoFace, k?}]` — not a joint that holds (its part is held by its own joints). Free length: its modelled length
  between its end face and the flat face across it (springEnds); now: from that base to the face it reaches, along its
  axis; Assembly.draw gives its mesh the matrix scaled along the axis about its base (springMatrix) — so sliders, a
  drag, ⚙ ▶, the 🎬 animation and screenshots show it compressing; the row (part panel, overview) "volná · teď ·
  stlačení" + k (N/mm, the one input) → the force, updated while the parts move. Clashes (the panel, check_collisions,
  ⚠ the travel) between a spring and the parts it is joined to / reaches are dropped (the kernel has it at its free
  length). 〰 Spring in Joint ▾ (two flat faces); two flat faces picked: 〰 first when a part is called spring /
  pružina. AI: snap_faces type "spring" (value = k), get_assembly `springs`. Tests: e2e_assembly_ball_spring (scale =
  distance / free length at rest, 4 mm down and every frame of ▶; 16 / 4 mm / 2 N in get_assembly and the row; the
  kernel's overlap dropped from check_collisions and check_travel).

- **Assembly: 🔒 a touch's slides lockable (2026-10-29)** (the same report: after a touch the ball still slid in X / Y,
  lock_motion said "Nenašla se vazba…"). lockMotion tries as before (the joint's angle / distance, a new flush / gap /
  parallel joint), then keeps the motion on its own joint: a slide as `slides: [{d (in the other part's frame), at}]`
  — the anchor (a ball's centre, else the face's centroid) kept at that distance along d —, a turn of a ball joint as
  `rot` (all three turns: one turn alone of three is not kept). joints.js applies them after the joint's own kind and
  counts them in jointMiss / jointResidual (closed loops). The row: "🔒 2 locked" with ✕; get_assembly joints
  `locked_motions`. Tests: e2e_assembly_ball_spring (a disc on a top: 3 → 2 → 1 ways, not moved, pushed back by its
  joint, ✕ frees; a ball on an axis: its slide, then its turns), e2e_assembly_lockmotion as before.

- **Assembly: 🔗 fixed together (2026-10-29)** (the same report: "fix part A to part B as they are now"). A `rigid`
  joint keeps the part's own directions and its anchor face's place in the other part's frame (`rot`, `pos`, from
  joints.frameNow); its faces only anchor it (the clicked ones, else each part's biggest). It is applied last of the
  part's joints (it has the last word); the part has no motion of its own, its Moves are the other part's (*— with
  …*). 🔗 Fixed together in Joint ▾ (any face of each part), *🔗 Fix A to B* in the suggestions for two chosen parts
  (a 📌 fixed one is the one it goes to); its row names the two parts "as they are". AI: snap_faces type "rigid", no
  faces needed. Tests: e2e_assembly_ball_spring (a flag fixed to a pin follows its slide and turn, 0 own motions).

- **Assembly: ● ball joints (2026-10-29)** (the app's AI, report 2026-10-29-202947: a valve ball could not be joined —
  tangent refused a sphere, concentric wants a cylinder). The kernel's face info tells a sphere (`type: "sphere"`,
  radius, centre) and a cone (`type: "cone"`, `cone: {apex, d (the way it opens), half}` — not an `axis`, so the
  sketch's axis references stay the holes' and shafts'), also for faces placed again (_moved_surface). joints.js:
  **● ball** — a ball's centre on the other part's axis (a hole, a cone: it slides along it and turns any way, 4 ways)
  or on another ball's centre (3 turns); **◉ seat** — the ball in a conical seat (its centre r / sin half from the
  apex) or on the edge of a hole smaller than it (√(R² − r²) out of the hole's end, on its side). Both are pure shifts
  (either part may be the ball); a part's later joints are followed by its ball joints again (holdPart). A ball's
  turns about X / Y / Z through its centre are its motions (after the axis' slide and turn). A ball + a hole / cone /
  ball picked as two faces with no tool on: ◉ and ● first in the suggestions; one ball face: ● / ◉ … first. AI:
  snap_faces type "ball" / "seat" (anything else refused, it says why). Tests: test_modeler_features
  (test_ball_and_cone_faces: volumes, apex / half angle, moved, STEP round trip), e2e_assembly_ball_spring.

- **Icons at an extrude's height (2026-10-29)** (the owner: "u kliknutí na dimenzi vysunutí … pár ikonek … směr, k
  ploše a další ploše"): clicking the "↕ 10" label on the part opens the size editor with one line of 16 px stroke
  icons (web/js/modeler/dimicons.js, drawn like the step tree's): ⇅ flip, both sides, up to a face… (opens the Extrude
  panel to click the face), up to next (offered only once a background rebuild finds a face that way), through all
  (cuts only), add ↔ cut. The mode that is on is lit in the tree's add green / cut red, clicked again it goes back to a
  typed distance; each click is one undo step and the editor opens again by the label. The label stays in up to /
  through modes ("↕ k další ploše", placed from the kernel's `went`); typing a number goes back to a distance. A
  revolve's angle gets full turn / half turn / add ↔ cut. setExtrude() is the one code path for the Extrude panel and
  the icons. Tests: e2e_dim_icons.
- **Assembly: the drag cue (2026-10-29)** (the owner: a chosen part can be dragged, but the cursor hardly showed it).
  assembly/drag.js dragPlan decides what a drag of the chosen part moves (the press and the cursor both ask it, so they
  agree); over that part the cursor is the motion's symbol, 32 px, the accent colour on a white outline — ↻ a turn,
  ↔ a slide (along its line on screen), ⚙ with an arrow a mechanism — and it and the parts that go with it glow;
  dragging: the symbol filled and the value at the cursor ("↻ 37°", "↔ 12.5 mm"; a mechanism: its driver, as its
  slider); the first time, "Táhněte — pohne dílem / mechanismem" at the cursor (until the first drag). A fully held or
  📌 fixed part, a part not chosen, empty space: the normal cursor (the view turns). Tests: e2e_assembly_dragcue.
  The cursor redrawn (2026-10-29, the owner: "ugly, does not fit the design"): the normal arrow stays, a round 17 px
  badge at its lower right in the panel colour with an accent ring and a soft shadow holds the motion's icon drawn like
  the app's 16 px stroke icons (a turn arc with its head, a two-headed arrow along the slide, linked joints for a
  mechanism); dragging: the badge filled with the accent, the icon white. Hotspot at the arrow's tip, a 2× image via
  image-set (HiDPI), `grab` fallback; the label is a small pill beside the badge. drag.js cueSvg.

- **A snap point offers what it belongs to (2026-10-29)**: `pickSnap` puts `ownerItems` first — a round edge's centre /
  quadrant: ◎ Select the hole (a Hole step -> `suggestStep`; another round cut -> its cylinder face's table: `faceTable`,
  factored out of `clickFace`) and ◯ Select the circle / ◠ the arc (`pickEdge`); an edge's middle: ⟋ Select the edge; a
  corner: up to 3 edges that meet there. The sketch: a circle's / arc's centre picked -> ◯ Select the circle first.
  The assembly: `roundAt` — a round edge's centre / quadrant on a part (seen away from the rim; on the rim or the wall
  the click already takes the round face) -> ◎ Select the hole Øn -> that face in `facePicks` (Concentric …). A chosen
  hole's Ø label sits on its centre: click elsewhere first. Tests: e2e_select_from_point (new).
- **A chosen hole: its type and size at hand (2026-10-29)**: a Hole step chosen (its wall, its rim — `pickEdge` —,
  its row) puts `holeRows` on top of the suggestions: *Type: ⌴ Counterbore ▾* (`chooseHoleType`: all of
  `HOLE_TYPES`, the current ✓), *Size: M5 ▾* (`holeSizes`: ±2 in the M2…M20 series, a plain Ø: ±2 steps of 0.5 mm up
  to 6, then 1 mm), ✎ Edit the hole, 📏 its Ø — each switch in place, one undo step (`changedHole`). The right panel
  (no tool open) is `renderHoleStep`: Type / Size or Ø / Through / Depth changed at once, ✎ Edit the hole, ＋ Add
  position (edit + `armPlace`); `selectStep` scrolls the step's row into sight. Only `hole` steps — an extrude's round
  cut keeps its face rows. Tests: e2e_hole_suggest (new).
- **A new thread is cosmetic and seen at once (2026-10-29)**: `commit()` -> `showNewThreads`: a hole step with a
  thread that the last undo step did not have (the Hole tool's Tapped, a type switched, the AI's add / edit) turns
  the part's threads from hidden to `cosmetic` in the same undo step, with a toast; real threads stay one choice away
  (the tapped hole's panel: *🔩 Thread — Cosmetic / Real thread (slower)*, the Part panel's 🔩 Threads). Parts as
  opened keep their setting. Tests: e2e_thread_default (new), e2e_model_threads (the new holes show cosmetic first).
- **Choosing a hole never arms its placing (2026-10-29)**: an edited hole / text step (✎, double-click) opens its
  panel with `cmd.place` off (`PLACES`): no preview at the mouse, a click places nothing (a notice says how) until
  **＋ Add position** (a hole) / **⌖ Move by clicking** (a text / picture) — `armPlace`, a toggle; new ones place at
  once as before. Choosing a step (its row, its faces) opened no tool already; sketches open only by ✎ (their own tool
  bar), • reference points have nothing to place. Tests: e2e_hole_select (new).
- **Soft / hard slider ranges (2026-10-29)**: `/api/model/limits` lists in `_soft` a max that is only how far the
  search looked (it still built there: an extrude's height) or a suggestion (a pattern's count / spacing: the copies
  that reach the part — decided soft, the pattern may run off the part; `_pattern` then warns *Only N of the copies
  reach the part*); everything else is hard (a cut / blind hole capped at through, a hole as wide as the part, a full
  turn, what OpenCASCADE cannot build). Soft numbers get no max: the slider grows round a bigger typed number (to a
  round 1 / 2 / 5 × 10ⁿ), the range shows *2 – 4+*; hard ones are held saying why (`LIMIT_WHY`: *max 9.94 — a bigger
  rounding does not fit here*), in the panel and the 3D label's editor (whose pattern count is soft too). A number
  below its min is no longer forced up while typing ("1" on the way to "10" became 20): held to the min when done. The
  draft angle is ±44.5°. Assembly sliders: the joint gap already grows (±50 mm, wider round a typed value); the turn
  sliders (±180°) and travel limits are hard — unchanged. Tests: test_limits (+ `_soft`, 6 copies past the end build
  with a warning), e2e_slider_grow (new), e2e_model_pattern (along y the count is kept, with the warning).
- **Right-click = OK, with a hint at the cursor (2026-10-29)** (as in SolidWorks): a right-click in the view presses the
  primary button of the bottom-right action dock — OK of a step, ✓ Finish sketch, Done (🎨 paint) — or a panel button
  marked `data-rclick-ok` (🔩 the assembly's screw: Add); the very same click, so the same undo step and rules
  (web/js/actiondock.js). Only a click: a right press moved < 4 px and let go within 400 ms; a right drag still pans
  (FreeControls: right = pan). Only on the view's picture (canvas / svg), not on its labels, fields, buttons or
  floating boxes; the panels keep the browser's menu (copy / paste in a field) — chosen so a right-click in the panel
  never confirms by surprise. Nothing to confirm: nothing happens. The primary button's tooltip gets "Right mouse button
  = OK". While the mouse is over the view, a small muted hint below-right of the cursor (a snap label sits above-right)
  says it: a mouse icon with its right button lit + the button's word ("OK", "Dokončit skicu", "Hotovo"), and what Esc
  does where the workspace says it (Modeler.escMeaning): "Esc Zrušit" in red when Esc throws the command away (a new
  panel, a placing tool with nothing placed, Sketch on… choosing a plane), "Esc Hotovo" muted when Esc keeps what was
  placed; left out where Esc only ends a sketch tool or a hole's reference pick. Hidden while dragging and with no
  command. Joints in the assembly are made on the second pick (no OK) — nothing to confirm there. Tests: e2e_rclick_ok
  (new).
- **Esc keeps what was placed (2026-10-29)**: in a tool that places things click after click — ◎ Hole (positions),
  Fillet / Chamfer (edges), Shell (open faces) — Esc ends the placing and keeps them (`escCommand`: as OK, a toast
  *Hole: 1 position(s) kept*); with nothing placed (or nothing changed in an edited step) it cancels; the Cancel button
  always throws it away; Esc while picking a hole's reference edge ends only that pick. The sketch already kept a
  ╱ line chain's segments on Esc; the assembly's tools place one thing each (🔩 a screw, a joint: Esc before it is
  made = cancel), 🔩 Fasteners are added one click each — unchanged. Tests: e2e_esc_keeps (new).
- **UX review leftovers (2026-10-29)**: Export ▾ in the top bar works on a 📄 drawing sheet (PDF, DXF, 🖨 Print —
  only those shown: styles.css hides the 3D formats there) and in a 📐 2D drawing (DXF of the shown layers); tests:
  e2e_ux_sheet. **/api/model/limits of a fillet next to a hole** (40 × 30 × 10, Ø10 4 mm from the edge) took > 120 s
  and gave a 500: each failing trial ran _sized's own 18-step search, and OpenCASCADE builds radii just below the
  limit (8.98 of 8.985) for 10–18 s each. Now limits' trials only need a no (doc._explain), a rounding's range is
  found to 1 % (marked "_approx": the panel shows "≈ 8.94" and lets a typed value up to 2 % above it stand), every
  search stops after SIZE_BUDGET 2 s or a trial slower than 0.4 s (also _sized's "at most": that plate's r 9 now
  ~11 s, was ~60 s); the endpoint answers {_error} instead of a 500 (timeout 30 s). That plate: 0.08 s in-process,
  1.4 s over HTTP; tests: test_limits_of_a_rounding_next_to_a_hole_answer_fast, e2e_model_limits. **Picking**: the
  view's pickOutline gives a face under the mouse priority over a used sketch's faint lines (the ray met them through
  the part: the plate's own bottom sketch picked from its top face); the sketch chosen in the tree only right on its
  line (~0.4 % of the part), a sketch not extruded yet as before; tests: e2e_model_tree. **Hole panel at 1280 × 800**:
  a position's row cut its ✕ off (nowrap words); now its words wrap (minmax grid column), the number and ⇄ 🎯 stay
  whole; tests: e2e_ux_model. **AI: a dimension's tolerance / reference**: sheet_edit {dims: {<id>: {tol: "±0.1" /
  "+0.2/-0.1" / null, ref: true / false}}} (tolText checks it, a Ø is told to take a fit; stored as the panel does:
  d.dims[id] for an automatic one, on the user's own dimension), get_sheet's dims show tol / ref; tests: e2e_agent.
- **Several windows / starts done**: a second start of the exe (launcher: unchanged — Edge --app with the same
  profile opens a new window of the running server, a fresh page) or ⧉ / Ctrl+click on 📄 Nový projekt -> the start
  screen with a project of its own. windows.js answers on a BroadcastChannel "a3d-windows" which project is open
  there (openElsewhere): autosave.offerLast offers the last project NOT open in another window, 🕘 Nedávné projekty
  marks such a one "otevřen v jiném okně" (opening it is allowed: the windows of a project sync). The title is the
  project's name. tests: tools/e2e_new_project.py (a second window of the app).
- **✨ AI: a chat per window done** (the owner: "jak to funguje, pokud program spustím víckrát? … A bude fungovat
  agent?"). Decided: (a) each window its own chat — server.CHATS {client id: ChatSession}, made at the window's first
  chat request, its Claude Code process only with its first message (a window that never chats costs nothing; ended
  10 min after its window closed); (b) one shared chat aimed at the last-typed window was rejected: two projects' talk
  in one conversation, and a call could still land in the wrong window between two messages. The window's id
  (agent.js CLIENT: sessionStorage — kept by a reload and 📄 New project, new in a new window) goes with every chat
  request; ChatSession starts its MCP server with --client <id>, which sends it with each tool call; /api/agent/call
  sets agent.ROUTE (a ContextVar: server tools such as open_file relay with it too); Relay.call(to=…) is taken by that
  window's poll only. Closed: the page's pagehide beacon (/api/agent/bye) -> calls fail with GONE_TEXT after a 10 s
  grace (a reload polls again first); no beacon (a killed browser) -> not seen for 90 s (a long call says
  /api/agent/alive every 10 s). Calls without a client (an MCP client of its own, e2e_agent) go to the window in use as
  before. launcher.stop -> server.stop_chats(). tests: test_agent (routing, closed, no goodbye, server, --client),
  tools/e2e_new_project.py (two browsers, two projects).
- **📄 New project done** (the owner, 2026-10-29: "Nevím jak intuitivně založit nový projekt, pokud mám zrovna nějaký
  projekt otevřený"): web/js/newproject.js — Otevřít ▾ › 📄 Nový projekt (Ctrl+Alt+N by the key's place, e.code KeyN:
  Ctrl+N is the browser's, and Ctrl+Alt is AltGr on a Czech keyboard), the project widget's ⋯ menu (leftDock.projectMenu),
  the docked suggestions' row with nothing selected and the assembly's table (rank 20: under ⋯ Ukázat vše). The project
  on screen is kept first (autosave.saveNow, autosave.kept() — not kept: asked), then the page loads afresh with ?new
  (nothing of the old project lingers in the workspaces; no "continue" strip): the start screen, a new autosave id, a
  toast „Předchozí projekt „…“ je uložen — Otevřít ▾ › 🕘 Nedávné projekty" with ↶ Otevřít znovu (autosave.open: its
  own id). ⧉ Nový projekt v novém okně: window.open(?new). The window's title is the project's name (showProjectName).
  tests: tools/e2e_new_project.py.
- **Mouse side buttons = Undo / Redo; Back stays in the app done** (the owner, 2026-10-30: "boční tlačítka na myši
  … místo back na stránce, což v browseru zavře program"): web/js/mouseback.js — buttons 3 / 4 stopped on mousedown /
  mouseup / auxclick (document, capture); on the press a Ctrl+Z / Ctrl+Y keydown on the body, so every workspace's own
  key path runs (not over a text field). A guard entry ({a3dGuard}) pushed on load (after ?new is read), again on the
  first trusted pointer / key (Chromium skips entries pushed without a user gesture) and on every popstate. No
  beforeunload prompt: the autosave's pagehide beacon keeps the project. tests: tools/e2e_mouse_back.py.
- **Assembly: suggestion-based and compact done** (the owner: "90 % základních věcí ze suggestions"; audit of 22 basic
  tasks: 8 → 20 doable from the Suggested table alone, the crank built from its four parts in 14 clicks instead of
  ≈ 27 with four Ctrl+clicks on small faces). assembly/smart.js: pinFits (a free round face of the chosen part and one
  of another part that fit — a pin as big as the hole or ≤ 0.6 mm smaller; the fixed / joined target and the nearest
  first) -> ◎ "Do díry v Základna · Ø6" / "Na čep Klika · Ø8" (joinRound, seated when a face around it fits), restOn
  (its lowest face looking down onto the top of the fixed part, or of the other chosen one) -> ⧉ "Položit na Základna".
  Assembly.suggestAssembly: nothing chosen -> the whole assembly's table (empty: the project's parts, 3D models
  first, 📚 Z knihovny… (hooks.openLibrary), 📂 Ze souboru…; then a loose pin that fits a hole, ⚙ Ovládat mechanismus,
  ⚠ Ukázat kolize (n), 🔩 Přidat spojovací prvky (n) (findCandidates), ＋ the parts not placed yet, 💥 Rozložit / Složit
  zpět, ✂ Řez, 📏, 📋 Kusovník, 📄 Výkres sestavy …; cached by the parts' places and joints). partItems ranked: the pin /
  put-on / drive first, then join, open, ↻ Otočit o 90° / ⤵ Položit na bok (loose parts), 📌 (not on a joined part: a
  dead end), ✕, 🏷 Přejmenovat, 📄 Výkres dílu (hooks.openSheet; ⊕ one more copy stays in the list row); 🪶 left the table (a property: in the panel). Esc: a menu, the
  collisions / fasteners list, then the chosen part (back to the whole assembly's table). Toolbar in one row of
  names where it fits (data-max-rows 2 for compactbar.js: icons when more): 🔗 Vazba ▾ (the joint types and
  🔩 Šroub / kolík in a menu; the chip shows the active type), 💥 Rozložit ▾ (the slider and "Podle vazeb"); menus
  close on a click elsewhere and over the Suggested table. Right panel: nothing chosen — the joints and couplings
  folded into "🔗 Vazby (n)" (open by itself when one does not hold), the duplicate 📄 Výkres gone; a part — Open /
  📌 / ✕ under its name (Join, Make it its own part: the table), Reset its place inside "Umístit ručně", Úpravy + Vzhled
  folded into "🎨 Vzhled a úpravy" (assembly.moreOpen); a coupling's row laid out as a joint's. ⚙ Mechanism: a crank on
  a pin of the fixed part is the driver first (also when the slider, not the rod, closes the loop). tests:
  tools/e2e_ux_assembly.py; e2e tests that clicked a joint type open 🔗 Vazba ▾ first.
- **✨ Suggestion-based 3D model and sketch done** (the owner, 2026-10-29: "90 % základních věcí … z chytrých a
  relevantních suggestions"; audit of ~20 basic tasks: 55 % → 90 % through the table's top rows): nothing chosen in the
  3D model -> "Další krok" (≤ 6 rows, ranked by context: an empty model ✏ Skica na rovině…; an unused sketch ⬆ Vysunout
  skicu „…“; after a hole ⁂ Pole z poslední díry; else ✏ sketch on a face, ◎ hole, ◜ / ◸ edges, 📄 Výkres — the drawing sheet …); a click on an EDGE
  (lit on hover) -> ◜ Zaoblit / ◸ Zkosit tuto hranu first, the command opening with it chosen (Ctrl+click: several);
  a step's row (or a sketch's outline) -> ✎ edit, 🏷 rename, ⁂ pattern it, ✕ delete, ◌ off, ↑ / ↓ move, ⏮ roll back
  here (a click on a row no longer leaves the previous table up); a face also 📏 Změřit ji, 🎨, ⁂ for a hole's face;
  Esc clears the choice; OK / Cancel leave nothing chosen. The sketch: "Další krok" with nothing picked (≤ 5 rows over
  the drawing: ✓ Hotovo — pak vysunout, 🪄, ⬚ Vybrat tvar, ↔ Kóta, ◯ Kruh; none in an empty sketch); a line clicked in
  its middle gets the line's suggestions (its length …), not an empty table. Compact panels: the Part panel's "Next"
  block (a hint + buttons repeating the toolbar) gone, Tolerances / See-through under "Další…", the sketch panel without
  the second 🏷 Sizes switch and the repeated hint, its Tips folded. Fixed: a click on a sketch size label left its
  drag running (the label stopped pointerup) — the label wandered with the mouse and, after the sketch, every move threw
  a console error. tools/e2e_ux_model.py does the tasks only through the suggestions.
- **AI tool coverage checked (2026-10-29)** (the owner: "checkni, jestli AI agent má přístup ke všem toolům"):
  docs/AI-TOOLS-COVERAGE.md — 90 GUI capabilities against the tools: before ok 54 / partial 14 / gui only 21, now
  ok 64 / partial 13 / gui 12 (layout, rare, many-input tools). tests/test_agent_wiring.py: the page's handlers (read
  from the JS: the blocks that build agentHandlers) ↔ TOOLS both ways, SERVER_TOOLS, the MCP tools/list, the chat's
  TOOL_LABEL (12 were missing) and a skill / the system prompt naming each tool (3 were not); e2e_agent asks the page
  for its handlers too. Added: list_demos / open_demo and open_file of a .a3d.json (server -> load_project ->
  openLoaded, blobs and version history), export format "project" (savedProject), get_assembly parts' mass_g and
  missing_joint + add_missing_joint, drive_mechanism trace, place_part fixed, switch_variant / take_part, add_feature
  type "solid" with a path (server: import_solid into the blob store). The real chat (tools/e2e_chat.py, fixed to wait
  for the whole turn: ai-busy) ran "open the crank demo, its mass, the slider's stroke, a GIF, save the project":
  open_demo, get_assembly, drive_mechanism trace, record_animation, export project — 203.6 g, 50 mm.
  Left to gui_action: layout (widgets, windows, language, planes / ⊕ shown, explode per part, simplified look),
  sketch extend / construction / mirror / offset, step reorder, split pieces as parts, bending, print split joints.
- **The shell for a new user done** (the owner: "maximální intuitivnost… suggestion based"; an audit at 1280×800 and
  1600×1000 in Czech). **Start screen** (web/js/start.js): a project with no part, or every tab closed
  (body.start-open; start-fresh when there are no parts), shows only "Co chcete vytvořit?" and four cards — ✏ Nový díl
  (project.newModel), 📂 Otevřít soubor (#anyInput: any kind, routed by its extension — openFiles in app.js, also behind
  Open ▾ › 📂 Soubor… and Ctrl+O), 🎬 Demo (showDemos), ✨ Zeptat se AI (the chat in the drawer beside it); ← → between
  the cards; the quick part's panels hidden behind it (12 controls in sight instead of ~35); "No part open" above the
  cards when tabs were closed, the project tree beside it. No tour. **Files dropped anywhere** (initWindowDrop): a dashed
  frame over the window; a drop no view took (the quick part's view, the assembly's, the chat keep theirs) opens as
  from 📂. **Top bar**: ✨ AI in every workspace (the quick part: its left AI tab), no "No drawing loaded", Ctrl+S saves.
  **Suggestions core** (suggest.js, API unchanged): the head one line (the title ends in … with a tooltip), its setting
  "Top 8" / "Prvních 8" shows with the mouse over the table (or while open), not in the title's way; keyboard — ↓ with
  no field focused goes into the table on screen, ↓ ↑ Home End move, Enter runs (and nothing else that listens for it),
  Esc leaves; **suggestMenu(at, title, items)**: the same rows as a small menu at a place — a part tab's right-click /
  long-press: ✎ Přejmenovat, ⧉ Duplikovat, ↗ Otevřít v novém okně, ✕ Zavřít záložku. **Less bulk**: the docked project
  widget as tall as its rows (leftDock.fitContent; one part 80 px, was ~200), the quick part's view chips one line each
  (the row wraps, nothing cut off at 1280), toasts close on a click and at most 4 stay, the 3D print tab answers first
  (fits / does not fit right under the printer; the build volume settings and the joints of split pieces folded — open
  when it does not fit), the library shows its first part at once (↑ ↓ in the search walk the list; categories in Czech).
  Tests: tools/e2e_ux_shell.py (32 checks, Czech, 1280×800 + 1600×1000 screenshots); e2e_suggest's setting click hovers
  the table first. Left out: the "continue where you left off" strip stays above the start screen; the outline wizard
  unchanged (dense but each control relevant).
- **📐 Suggestions in the 2D drawing done**: web/js/drawing2d/drawsuggest.js (showSuggest). With nothing chosen:
  ✏ as a sketch of a new 3D model, ▤ as a quick part, 📏 measure, ⬇ DXF. For the shapes chosen: ≡ all like this, Ø / R
  / length: change the size… (one value, all of them change), only these as a sketch / a quick part (no question:
  DrawingEditor.useShapes), to another layer…, ✕ delete. Esc with shapes chosen: nothing chosen. No table while
  drawing or measuring. tools/e2e_ux_sheet.py (2D part, 4 checks).
  Left out: merge / simplify as a command (it happens when the drawing becomes a sketch), lasting dimensions.
- **📄 Suggestions on the drawing sheet done** (the owner: "suggestion based — 90 % of the basic things from
  suggestions"; before, the sheet had no table, and a click on a view, an edge or the title block did nothing
  visible). web/js/sheet/sheetsuggest.js builds the table from what is chosen. SheetEditor has selView, selGeo
  {view, edge | c} and selTitle, set by a click without a drag (clickSelect: a circle or an edge under the mouse,
  else the view), and marked in blue, not printed (selSvg; the title block framed).
  - View: its missing sizes, all its sizes / as the sheet, ＋ a dimension, bigger / smaller (the next ISO 5455
    scale) / as the sheet, add Section A–A, back to its place, rename, hide (also Delete).
  - Edge: dimension its length, or distance / angle to… (the ＋ Dimension tool with the edge as its first pick).
  - Circle: Ø / R, or the hole callout; when it has a dimension already, "Its dimension: …" chooses that one.
  - Dimension: tolerance… (tolText: ±0.1 or +0.2/−0.1, d.tol), fit… (H7, H8, h6, g6, k6, p6), reference
    dimension (d.ref: "(60 ±0.1)"; check() leaves it out of "given twice"), to the other side, delete. Both are kept
    like a moved place: d.dims[id] for an automatic dimension, on the user's dimension itself (setDimProps); the
    text (dimText = dimCore + tol, in brackets) also goes to the PDF, the DXF and get_sheet.
  - Title block: title / drawing no. / drawn by / note… (one field), material (opens the part), template…, frame…,
    paper A3 / A4, save as template…, company, logo and fields, export DXF.
  - Nothing chosen (kept short so it covers little of the paper): add the missing sizes, remove sizes given twice,
    remove lost dimensions, show a hidden view, ⬇ Export PDF, 🖨 Print (printPdf: the sheet's PDF printed from a
    hidden frame), add BOM page (an assembly).
  - Also fixed: a view's label under a hole callout's text (leaderEnd); the left panel's double line and gap above
    Views; Paper and Scale above the title block in the right panel; Tolerance and Reference as fields in the
    dimension's panel.
  - Tests: tools/e2e_ux_sheet.py (30 checks, Czech, real clicks).
  - **The drawing set from the table** (the owner: "zobraz všechny listy sestavy"): an assembly's sheet offers
    📑 All sheets of the assembly (n) right after the fixes (nothing chosen) and first in the title block's table,
    n = its assemblies + made parts + BOM pages (sheetsuggest setOf), and ⤓ PDF of all sheets (the hooks' setPdf =
    the assembly's drawingSetPdf); a part's sheet in an assembly: 📑 Sheets of the assembly “…”. Both open 📚 All
    pages (the set one sheet below the other, this one in sight); there the table goes ▼ Next / ▲ Previous sheet
    (from the one in sight — markSeen redraws it), ⤓ PDF, ↩ Back to this sheet. AI: get_sheet's drawing_set
    {assembly, sheets, pages, all_pages_shown}, sheet_edit all_pages. Tests: tools/e2e_drawing_set.py (12 checks,
    Czech: 6 sheets on screen, next / previous, the part's sheet goes to its page).
  - Left out: a detail view (more than 2 inputs); the top bar's Export ▾ on a sheet (shell); `sheet_edit` setting
    tol / ref (AI tools).
- **Assembly: suggestion-based and compact done** (the owner: "90 % základních věcí ze suggestions"; audit of 22 basic
  tasks: 8 → 20 doable from the Suggested table alone, the crank built from its four parts in 14 clicks instead of
  ≈ 27 with four Ctrl+clicks on small faces). assembly/smart.js: pinFits (a free round face of the chosen part and one
  of another part that fit — a pin as big as the hole or ≤ 0.6 mm smaller; the fixed / joined target and the nearest
  first) -> ◎ "Do díry v Základna · Ø6" / "Na čep Klika · Ø8" (joinRound, seated when a face around it fits), restOn
  (its lowest face looking down onto the top of the fixed part, or of the other chosen one) -> ⧉ "Položit na Základna".
  Assembly.suggestAssembly: nothing chosen -> the whole assembly's table (empty: the project's parts, 3D models
  first, 📚 Z knihovny… (hooks.openLibrary), 📂 Ze souboru…; then a loose pin that fits a hole, ⚙ Ovládat mechanismus,
  ⚠ Ukázat kolize (n), 🔩 Přidat spojovací prvky (n) (findCandidates), ＋ the parts not placed yet, 💥 Rozložit / Složit
  zpět, ✂ Řez, 📏, 📋 Kusovník, 📄 Výkres sestavy …; cached by the parts' places and joints). partItems ranked: the pin /
  put-on / drive first, then join, open, ↻ Otočit o 90° / ⤵ Položit na bok (loose parts), 📌 (not on a joined part: a
  dead end), ✕, 🏷 Přejmenovat, ⊕ Ještě jeden; 🪶 left the table (a property: in the panel). Esc: a menu, the
  collisions / fasteners list, then the chosen part (back to the whole assembly's table). Toolbar in one row of
  names where it fits (data-max-rows 2 for compactbar.js: icons when more): 🔗 Vazba ▾ (the joint types and
  🔩 Šroub / kolík in a menu; the chip shows the active type), 💥 Rozložit ▾ (the slider and "Podle vazeb"); menus
  close on a click elsewhere and over the Suggested table. Right panel: nothing chosen — the joints and couplings
  folded into "🔗 Vazby (n)" (open by itself when one does not hold), the duplicate 📄 Výkres gone; a part — Open /
  📌 / ✕ under its name (Join, Make it its own part: the table), Reset its place inside "Umístit ručně", Úpravy + Vzhled
  folded into "🎨 Vzhled a úpravy" (assembly.moreOpen); a coupling's row laid out as a joint's. ⚙ Mechanism: a crank on
  a pin of the fixed part is the driver first (also when the slider, not the rod, closes the loop). tests:
  tools/e2e_ux_assembly.py; e2e tests that clicked a joint type open 🔗 Vazba ▾ first.
- **⏮ Print and export as the rollback bar stands done** (the owner: "Chci tisknout podle aktuálního umístění
  posuvníku" — as SolidWorks): one place on the server, doc.at_bar(part) — the steps up to part.rollback (absent or a
  step that is not there: all) — used by rebuild, body_of, export (STEP / IGES / STL / OBJ / GLB / PDF) and sheet, so
  the browser's Export menu, 🖨 Prepare for 3D print (its STEP; the split cuts that copy), the AI's export /
  prepare_print / check_print and a part's drawing sheet all get the rolled-back part; 3MF is made from the body on
  screen (already rolled back). In the browser steptree.js stepsAtBar / rolledText / rollbackNote (the same rule);
  **assemblies and drawing sheets follow the bar too** (consistent with SolidWorks): Assembly.partFeatures (its
  bodies, clashes, STEP / IGES / GLB tree via stepfile.js, the BOM's volumes) and the sheet's partHash / assembly
  page send stepsAtBar. Said so it never surprises: the Part panel's 3D print and Export sections and the Export
  menu's top line "⏮ Podle posuvníku historie: bez posledních 2 kroků (Vysunutí 2, Vysunutí 3)" (sketches of the
  left-out steps not counted, ≤ 4 names), each menu item a ⏮ mark (#exportMenu.rolled), the export's toast (a
  warning) with the note; the print copy keeps it (state.model.rollback_note: a line on top of its 3D print tab,
  check_print `rolled_back`); an assembly's part panel and a drawing sheet's panel "⚠ Díl je vrácený v historii: …"
  (an assembly's sheet: "Díly vrácené v historii: <names>"). AI tool texts (rollback, export, check_print, get_model's
  note, prepare_print's answer) and the change-a-model skill say it. Tests: tests/test_model_rollback_export.py (a
  block + boss + hole: the bar under the block -> the STEP read back / STL / IGES = 8000 mm³, watertight; under the
  boss = 8500; at the end or under the last step = 8500 − the hole; rebuild and the sheet; the HTTP export);
  tools/e2e_model_rollback.py (+ 16 checks: the panel / menu / toast notes in Czech, STL and 3MF volumes, the print
  copy's note, check_print and exact pieces, an assembly and a drawing sheet of the plate with their ⚠ notes; at the end: all, no note).
  Left out: thumbnails in the project tree and the parts library still show every step.
- **🕘 Versions done** (the owner's design: versions without git, also in the frozen exe). auto3d/versions.py: a
  content-addressed store per project, `<data>/versions/<project id>/` — `objects/ab/cdef…` (each part's JSON, the
  project-level bits {name, parameters, order …} and the thumbnail, zlib, under the SHA-256 of their bytes: a part that
  did not change costs nothing), `versions/<id>.json` (a manifest {id, parent, variant, time, label, auto, parts: {part
  id: hash}, project, thumb, names, kinds, changed, volumes, note}), `state.json` (the variants {id, name, head, base}
  and the one on screen). Imported files stay in the blob store (the parts name them by hash). Written whole (temp +
  replace, autosave's PermissionError retries), a lock per project; ids, hashes and variant ids checked by pattern (no
  path traversal). An automatic version at most every AUTO_GAP = 180 s (a part added / removed: at once; nothing
  changed: none). Thinning of automatic ones (all of 24 h, the newest of each hour for a week, of each day after;
  per variant; named ones, heads and bases kept) and gc of objects no manifest uses, after each automatic save.
  diff(a, b): parts added / removed / changed, a 3D model's steps by id (added, removed, values {key, before, after,
  unit}: a sketch's locked sizes by dim id), an assembly's placed parts, the volume (the browser sends the part on
  screen's), the parameters. restore = the state now kept as "before-restore", then the old one as a new version on top.
  Variants: create from any version (it becomes the one on screen), switch, take_part (one part of another variant's
  head). bundle / unbundle: the store in the project file (`versions` key; each object checked against its hash).
  Server: /api/versions/<pid> (GET list, POST save), /v/<vid> (+ /thumb, /restore), /diff, /variants (+ /<var>/switch),
  /take-part, /bundle (GET / POST); forgetting a project (✕ in Recent projects) drops its store. web/js/versions.js: the
  🕘 Versions widget (leftdock addWidget `folded`: folded until opened — computed, not written into the saved layout),
  model and assembly: Variant ▾, 💾 Save version… (one field), the timeline (thumbnail 160 × 100 JPEG from the view,
  not fitted; time; label / "automatic"; changed parts), ⇄ compare (inline), ⑂ variant (one field), "Take a part from
  a variant…"; the preview (the project loaded, body.vr-preview, a banner ↩ / ⤺, capture listeners block clicks, keys,
  the assembly's left drag — the view still turns; autosave.paused); restore with ↶ in its toast. app.js hooks only
  (autosave `saved` -> versions.auto; Save project makes a version; Save project ▾ "with version history"; Open of a
  file with `versions` -> /bundle). AI: list_versions, save_version, restore_version, compare_versions,
  create_variant (agent_tools.py, change-a-model skill, e2e_agent). tests/test_versions.py (9: dedupe 10 versions ×
  one of 5 parts = 14 part objects, restore exact, diff names "d 10 -> 15" and a sketch dim, thinning with fake times,
  gc, variants, take-part, bad ids, bundle round trip), tools/e2e_versions.py (29 checks, Czech). Measured: 50 automatic
  versions of a 5-part project (the gear demo's parts, a real ~2 kB thumbnail each, one part changed each time): 170 kB
  in 155 files (620 kB allocated at 4 kB clusters), 219 kB bundled into the project file.
  Left out: the two bodies overlaid in two colours (compare is text), a Ctrl+Z of a restore (↶ in its toast and the
  "Before restoring" version instead), versions of the quick part / drawing / sheet workspaces' own widget (the widget
  is in the model and assembly workspaces; versions are of the whole project anyway).
- **🕘 Versions: a graph of the branches; rename / delete a variant done** (the owner: "a graph of the branches would
  help, the history is unclear now"). versions.js draws one SVG over the list's left column (14 px a lane, from the
  rows' measured positions: rows keep one height, a ResizeObserver draws it again when the widget is shown): a line per
  variant in its colour (7 colours by the variant's place; the chip by Variant ▾ and the legend have it), a dot per
  version, the fork a curve from the version a variant was made from into its lane, the variant on screen's lane bolder
  (the others at half), its newest version ringed green (● current), other heads ringed in their colour, the previewed
  one a dashed ring. Default: the variant on screen + the fork row (dashed, a hollow dot on the parent's lane); its
  versions other variants were made from carry a small stub in their colour. "All variants" (a toggle by the switcher,
  remembered; GET ?all=1 -> `all`: every manifest) interleaves every variant by time with a legend (name, number of
  versions; double-click renames, ✕ deletes); another variant's version previewed: the banner names the variant and
  offers ⑂ Go to this variant. Variant ▾ also has ✎ Rename this variant… / 🗑 Delete this variant… (double-click the chip
  / label renames too); delete asks inline ("Smazat variantu „X“ i s jejími verzemi (n)? Nejde to vrátit.", Esc keeps
  it). versions.delete_variant (not main, not one another variant was made from; the one on screen -> main's head; its
  manifests deleted after state.json, then gc), rename_variant refuses a clashing name; the list's variants carry
  `count`. Server: POST /variants/<var>/rename {name}, /variants/<var>/delete. AI: list_versions gives each version's
  parent and variant and each variant's made_from / versions; rename_variant, delete_variant (only when asked).
  Tests: test_versions (10: + rename clash, all, delete refused for main / a parent, its own objects collected, A's
  kept), e2e_versions (46 checks; + 17 at 1280 × 800: 3 lanes, the forks at the dots of B and A, the bolder lane and the
  ring, another variant's preview banner, rename by double-click, delete with the confirm and Zrušit, the default view
  main only with the stub, list_versions' graph fields, rename_variant). Left out: merging variants.
  **Plan, not built: "Also save versions to Git"** (an option for users who use git). Mirror, never replace: the
  content store stays the truth (the frozen exe has no git). When on and `git` is on PATH (or dulwich, pure Python, if
  bundled), a repository per project under `<data>/versions/<pid>/git/` (or a folder the user picks); each manifest
  saved becomes a commit — one file per part (`parts/<name>-<id>.json`, pretty-printed so diffs read), `project.json`,
  `thumb.jpg`; message = the label or "automatic" + the changed parts; author = the app user; the variant = a branch
  (`main`, `variant/<name>`), parent = the manifest's parent's commit (a map manifest id -> commit sha in
  `git-map.json`). Thinned automatic versions stay in git (git's own packing keeps it small). Written by a background
  thread after the manifest (a failure only marks the version "not in git" and retries); nothing is ever read back from
  git, so there is no merge to resolve. A push to a remote is the user's own (a button later, not automatic).

- **⚙ Mechanism tall enough at first done**: its default height 150 -> 230 px (mechanism.js addWidget h), so the
  crank demo's two motion rows and the "Chybí jedna vazba…" line with ➕ Přidat vazbu show without scrolling.
  e2e_mechanism_by_mouse checks the widget does not scroll at that step.

- **The assembly view follows an insert only when it has to done** (the mouse walkthrough: every ＋ Vložit díl reset
  the view to iso, the user's zoom lost): the first part -> iso; a new part outside the camera's view -> all fitted,
  seen from where the camera looks now (ModelView.fit); a part already in view -> the camera stays (Assembly.inView:
  the 8 corners of its box in the frustum). The same for ＋ Vložit díl, a drag from the project tree, the AI's
  insert_part and "one more of this part". Test: e2e_assembly_insert_view.

- **✕ in the project tree asks by turning red, not by a dialog done** (the mouse walkthrough: one click removed a whole
  part): the first click turns ✕ into a red "Smazat?" for 3 s, a second click (or Enter / Space) deletes, moving the
  pointer or the focus away or waiting puts the ✕ back; ↶ Zpět still restores it (parts.js armDelete). The only
  one-click delete of a whole part; an assembly's "✕ Vyjmout" stays one click — Ctrl+Z / ↶ undoes it (one history
  step) and the part stays in the project. Test: e2e_project_tree (one click keeps it, 3 s disarm, Enter twice
  deletes, ↶ back).
- **⚖ Mass properties done** (M6's "materials and mass" finished): kernel.centre(shape) — the centre of mass from the
  same integral as the volume (_volume now gives (volume, centre), kept together in `_volumes`: asking both costs one;
  several solids weighted by their volumes); tessellate's mesh has `cog` and `area` (the solids' faces: a file's loose
  faces left out). materials.py mass_g(volume, material) (the drawing's title block uses it). Part panel: Plocha
  (cm²) and Těžiště (x; y; z) mm with ⊕ (Modeler.toggleCog / showCog -> ModelView.setCog: a ⊕ CSS2D marker over the
  part, made once and moved). Assembly: massProps() — each placed part's mass (massOf: a part's own `mass_g` / its
  library item's first, else volume × material; the panel's parts list now uses massOf too, as the BOM) at its cog
  moved by its matrix; a ◇ sub-assembly's merged body carries its cog. The Assembly panel's CoG with ⊕; draw() moves
  the marker and the panel's value (▶ a mechanism, a drag: every frame, no kernel call). AI: get_model body
  area_mm2 / cog_mm, get_assembly mass_g / cog_mm (parts_without_mass). tests/test_mass_props.py (block, L by the
  area formula, an off-centre hole, two solids, STEP round trip, the packed message), tools/e2e_mass.py.
  Left out: a mass of its own typed in the UI (only the `mass_g` field is read), moments of inertia.
- **⏮ Rollback bar in the 3D model's step tree done** (SolidWorks / Solid Edge): part.rollback = the id of the step
  the bar is under (absent: at the end); saved with the part, in the undo history (History capture), one undo step a
  move. modeler.barAt / builtSteps / insertSteps / fixBar / setRollback: shown() builds the steps above the bar (a new
  command's preview inserted at it; a step under the bar opened: the part up to it), new steps (sketch, OK of a command,
  a reference point, the AI's add_feature) are spliced in at the bar and the bar moves under them; a deleted bar step
  moves it to the step before; under the last step it is at the end. sketches() / repeatable() / draftable() and the
  sketch outlines in the view only offer what is above the bar (usable()). The tree (rollbar): a 6 px separator with a
  grip after the last top-level block above the bar (role=separator, tabindex 0); dragged with the mouse between the
  top-level blocks — the 3D view follows while dragging (the tree is not redrawn then: barDrag), Esc puts it back;
  ↑ / ↓ / Home / End / Enter keys (focus kept), a double-click: to the end. Rows under it greyed (.rolled, a tooltip),
  "Potlačeno do konce: n krok(ů)" + ⤓ Na konec under the tree, the status line "⏮ Vráceno za krok „…“". A right-click
  on a row: ⏮ Vrátit se sem / ⤓ Na konec / ✎ Upravit krok / ✕ Smazat krok (stepMenu; Esc closes). Rebuilds are fast:
  doc.evaluate's prefix cache already holds the state after each step, so a rolled-back rebuild builds nothing
  (tests/test_modeler_kernel test_rollback_reuses_the_cached_prefix). Exports / assemblies / the print follow the bar
  since 2026-10-29 (the entry above). AI: get_model `rollback {after, name, rolled_back}` and each step `rolled_back`;
  a tool `rollback {to: step id | "end"}`; gui_state steps `state: "rolled_back"` and `rollback_bar {under}`.
  tools/e2e_model_rollback.py (33 checks: 4 steps -> the bar dragged above step 3 = the 2-step volume, greyed rows; a
  hole inserted at position 3; edits above / under the bar; a reload keeps it; the menu, keys, double-click, Ctrl+Z;
  dragged to the end = all; the AI tool; Czech). Left out: the bar above the first step (nothing built), dragging it
  inside a block (between a sketch and its extrude) — the right-click on the sketch does that.

- **🎬 Save animation of a mechanism done** (⚙ Mechanism ⋯): one cycle of the driver (a full turn / there and back,
  ▶'s speed) from the current view -> a looping GIF (default) or a video. The page draws the frames
  (`view.snapshot`, fit: false; the 3D only, an optional name caption; ≤ 1280 px across) one at a time (the page stays
  responsive); GIF: PNG frames posted to /api/anim/<id>/frame/<n>, made into one GIF by `auto3d/animation.py` (Pillow,
  one median-cut palette from frames across the cycle, no dither: no flicker; a progress job, cancellable) — chosen
  over a GIF encoder vendored into web/ because Pillow is already a dependency, the file must be in the data folder for
  the AI anyway, and the encoding runs off the page. Video: MediaRecorder on a canvas' captureStream (MP4 where the
  browser can — Edge / Chrome now can —, else WebM), paced at 25 fps, the file posted to the data folder. Code in
  web/js/assembly/anim.js (mechanism.js: one hook). AI: record_animation {mechanism, format}; gui_state `animation`.
  tests/test_animation.py, tools/e2e_mechanism_anim.py.
- **𝑥 Project parameters done** (the owner: named values of the project that any typed size can use): `L = 100`,
  `D = 8`, `t = L / 20` — web/js/params.js: a small parser of our own (numbers, 2,5 too; names; + − × ÷; brackets; mm /
  ° after a number skipped; no eval), evaluateAll (any order, circles and references to a bad one are errors of each
  parameter), readField (a field's text: a number, an expression or "name = expression"), resolveIn (every object with
  `expr` gets its numbers again, deep), the store (its own History; History.first / History.committed in history.js:
  Ctrl+Z / ↶ in any workspace takes a parameter change back when it was the last step). The place it is resolved: the
  **browser** — a number keeps its expression beside it (`{"d": 50, "expr": {"d": "L/2"}}`; a sketch size shown as a
  radius: `{"v": {"x": "D", "k": 0.5}}`), the number is always the value, so the kernel, exports, drawings and older code
  read numbers as before; auto3d/modeler/params.py is the same in Python (project.migrate puts the numbers as the file's
  `parameters` say: a file edited by hand); tests/param_cases.json holds the cases both must agree on. The server:
  doc._param_dims — a sketch whose locked size has an expression is solved again (planegcs) and its new points go back
  (`update`), so a part not on screen follows a changed parameter too. web/js/paramsui.js: exprField (a tool panel's
  number becomes a text field that also takes an expression: the panel's own listeners get a plain number as before —
  the expression worked out and handed to them, kept when they took it; shown "L/2 = 50" while not typed in; a bad one
  red with the reason, the number kept; ↑ / ↓ step a plain number), the 𝑥 Parameters widget (leftdock addWidget, model
  and assembly; hidden while there are none; name = expression = value ✕, "New: L = 100"), follow() (every model part
  and assembly re-resolved; the one on screen rebuilt, the others through /api/model/rebuild by name — the ⚙ jobs list
  —, an assembly on screen refreshed; a part's undo snapshot re-resolved on restore). Fields: every number of the tool
  panels (modeler.addSliders), the on-model size editor (openDimEdit / applyDim), the sketch's size labels (editLabel →
  setSizeExpr / keepExpr; labels "L/2 = 50"), the assembly joints' gap / distance / angle. Project file: `parameters`
  [{name, expr}] (Project.toJSON / loadAll). AI: get_parameters, set_parameter {name, value | delete} (lists the parts
  rebuilt with their volumes), add_feature / edit_feature numbers and sketch_dim value may be expressions (get_model
  `expressions`, get_sketch dims `expression`); model-a-part skill. tests/test_params.py (precedence, references, units,
  errors, circles, no eval, resolve, migrate; d = L / 2 and a sketch width W follow -> volumes, watertight, STEP round
  trip), tools/e2e_parameters.py, e2e_agent. Left out: renaming a parameter (its uses are not renamed), units other
  than mm / °, functions (sin, sqrt…), the sketcher's own panels (offset distance, pattern count / spacing in a
  sketch, move / rotate boxes), the mechanism / DOF sliders' numbers, a second window of the project (parameters are
  not sent to it live).
- **🎬 A 4th demo: gears and a rack done** — demos/prevodovka-s-hrebenem.a3d.json (6 kB, "Převodovka s hřebenem"):
  a base with two pins, Pastorek Ø30 and Kolo Ø60 in mesh (⚙ G1, i = 2:1), a Hřeben sliding beside the pinion (▤ G2,
  π·30 mm a turn), a hole off each wheel's middle to see it turn, colours; one ⚙ Mechanism driven by "Otáčení
  pastorku" over −120 … 120°. tools/make_demos.py builds it through the AI's tools (snap_faces type gear / rack) and
  now takes the names of the demos to build (`… - prevodovka-s-hrebenem`: the others stay as they are).
  tests/test_demos.py (its couplings: 2:1 in mesh, π·30, the pinion drives both); e2e_demos opens it: one mechanism of
  three parts, ▶ with the ratios held, the wheel dragged in the view.

- **Readable motion names by default done** (the walkthrough's "left out": the crank's motion was "Otočit kolem osy:
  stěna Extrude 2" until renamed). Assembly.motionsOf names each free motion by its part and kind: "Turn: Crank" /
  "Slide: Slider" (Czech "Otáčení: Klika" / "Posuv: Smýkadlo"); two motions of one kind add how, in brackets ("Slide:
  Lid (along X)", "(along the axis)", "(on the face)" …: each candidate's `how`); the joint's own words stay as
  `detail` (the motion row's tooltip); a part fixed on a turning one shows that part's motion ("Turn: Bearing", the
  hint says it goes along). The user's names (moveNames) still win. e2e_assembly_lockmotion / lever / loop /
  mechanism and make_demos find the motions by the new words.

- **⚙ Couplings between motions — gears, belts, a rack done** (the owner: "couplings between motions in assemblies,
  each one joint with ONE input"). web/js/assembly/couplings.js: assembly JSON `couplings` [{id G…, type gear | belt
  | rack, a, aFace, b, bFace, ratio, inner, flip, name}] — gear / belt: ratio = turns of a per turn of b (Ø b / Ø a,
  "i = 2:1"), a gear pair opposite ways (a ring gear round a pinion, `inner`, and a belt the same way); rack: a = the
  pinion's round face, b = the rack's flat side along its axis, ratio = mm per turn (π·Ø). couplingOptions(fa, fb,
  pins) infers what fits from the picked faces: two rims (isPin) on parallel axes apart — touching (Ø a + Ø b apart):
  a gear first, further: a belt first; a hole + a pin: only a ring gear round it (else it is a joint to make: the
  rod's eye on the slider's pin keeps ◎ Concentric first — e2e_mechanism_by_mouse); a rim + a flat face along its axis:
  a rack. Assembly.couplingItems ranks them first (−1) when both parts can turn about those axes (the rack: slide),
  else after the joints. Solving: Assembly.applyMates -> followCouplings(asm, before, drive) after placeAll /
  closeLoops — each coupling whose one side moved (deltaOf: the turn about its rim's axis, the slide along the rack;
  the exact amount from moveFree's drive {mo, amount}, so a turn past 180° counts) moves the other side's mover
  (moverOf: itself or the shaft it is keyed on) by the coupled amount, then placeAll / closeLoops again (a loop on a
  coupled part follows) — each part once, through a whole train, no back-and-forth. mechanisms(): coupled parts merge
  into one mechanism (`train`; a gear keyed on a turning shaft joins the shaft's); drag.js turns a train's gear by
  its own axis (a part of a closed loop still drives the loop's driver); the joint spin slider passes its turn on.
  The part panel's "Couplings" rows (ratio — one input —, ⇄, ✕, a name by double-click, hover lights both faces),
  the overview lists them; History keeps them. AI: snap_faces type gear / belt / rack (value = ratio), get_assembly
  `couplings`, edit_joint {id G…, ratio, flip, name}, remove_joint; the assemble-parts skill; e2e_agent (refused on
  flat faces). tools/e2e_assembly_gears.py (33 checks): the suggestions, 2:1 -> the wheel −45° for 90°, the belt the
  same way ×2, the rack π·Ø per turn and driven back, one ⚙ Mechanism, ▶ with the ratios held to < 0.05°, ⚠ the
  travel, a drag of the wheel, the ratio typed / ⇄ / ✕ / undo, saved and opened again, Czech. Left out: gear teeth
  (no gear feature in the modeller: a wheel is its pitch circle, the ratio from its Ø), couplings inside a
  sub-assembly's own engine, a planetary carrier (the turn is measured in the world, not against a moving carrier).

- **Big STEP files open fast done:** the 44 MB board (126 062 faces, 5237 solids) took ~50 s to open (cold server):
  profiled in the kernel process — STEP read 15–19 s (ReadFile 1.7 s, the XCAF transfer 10.5 s: C++, no parallel
  option in OCCT 8.0; the colours / turned_out walk ~3 s), import's volume 2.3 s, then tessellate 25–27 s: BRepMesh
  only 2.7 s (already parallel), the rest Python per face — triangles 5.4 s, face info 8.3 s (box centres 4.5 s),
  edges 1.8 s, adjacency 2.1 s, the volume again 2.5 s (solid_body's compound of the solids missed volume's cache).
  The board is 19 382 different faces placed 126 062 times (49 475 edges of 303 387). Now: auto3d/modeler/filecache.py
  keeps a big file (> MIN_FACES 3000) in the data folder's cache/models by its blob hash — <sha>.brep (the shape as
  read, BinTools binary B-rep: exact, the same faces in the same order; read in 0.3 s), <sha>.json (its colours and
  import_solid's answer), <sha>.<step>-<solid|ref>-<full|light>.mesh (tessellate's answer, marshal); each entry
  stamped with VERSION, the code's hash (kernel.py, doc.py, filecache.py) and the blob's size and time, else made
  again; damaged -> read again; the folder under LIMIT_MB 4096, least used first. doc._solid_shape / import_solid read
  it first; a solid step's body carries src (blob, id, ref) so doc._tessellated finds its mesh. kernel (import /
  meshing path only): tessellate's heavy path — _face_meshes (a placed face's mesh read once, moved by its place's
  matrix; the same position bytes as before), _surface_of / _moved_surface (a placed face's surface asked once),
  _box_centres (all flat faces' box centres at once), _heavy_edges (an edge placed many times divided once; its faces
  from MapShapesAndAncestors — the list's ends, not walked from Python: 0.5 ms each), read_brep / write_brep,
  loose_faces kept for its shape, solid_body passes the file's volume on. Measured (cold server, localhost; this
  machine shared with other jobs, ±15 %), before -> after: first open (import + rebuild) 51.7 s -> 35.4 s (import
  23 -> 21.8 s, rebuild 28.7 -> 13.5 s; tessellate alone 27.5 -> 13.9 s, 🪶 light 20.9 -> 11.4 s); second open in a
  new server (the cache) 51.7 -> 4.5 s (import 1.5 s, rebuild 3.0 s); time to the first picture (e2e_big_part_load:
  import + shown) 24.1 + 27.2 s -> 21.0 + 14.0 s cold, 1.5 + 3.1 s from the cache; the kernel process's peak memory
  1171 -> 1273 MB cold (the mesh written), 969 MB from the cache; the cache 92 MB for the board (19 MB B-rep, 71 MB
  mesh, 2.5 MB colours). Faces' frames from the new box centres differ from before by < 2e-5 mm (12 677 of 126 037,
  rounding), all else the same. tests/test_filecache.py (a hit reads and meshes nothing, the same answer, mesh,
  colours, an exact STEP export; a file changed in place / other code / a damaged entry read again; small files not
  kept; the size limit; a part placed three times meshed as three copies made apart). tools/e2e_cancel.py imports a
  copy of the board with one more line (the board itself comes from the cache in a second: nothing to cancel), and
  finds its server by its command line when netstat shows no owner. Left out: a coarse first mesh refined later (the
  time is in reading the STEP and in Python per face, not in BRepMesh — a coarser mesh saves ~1 s), meshing across
  the kernel pool (BRepMesh is already parallel; shapes would have to go through B-rep files), skipping tiny faces
  (every face must stay pickable by its id).
- **A mechanism built by mouse: the walkthrough, its fixes, "one joint is missing" done** (the owner: "how hard is it
  for a user to make a mechanism?"). The crank – rod – slider put together with real clicks only (headless Edge, Czech,
  1600×1000; the crank demo's parts; tools/e2e_mechanism_by_mouse.py replays it). Found and fixed, one commit each:
  a small hole / pin seen from afar was all the snap circles of its centre (0 of ~170 spots picked a face, so
  "◎ Soustředně" never showed) -> Assembly.idleSnap: on a round face or near its rim only a corner snaps; a Ctrl+click
  beside the parts dropped the first pick -> kept; the empty assembly's steps and the two-part panel line were English
  (and named the old 🧲 Snap) -> Czech, today's way; a thin side (7 px) was all corner / midpoint snaps -> a plain
  click snaps within 5 px (📏 Measure 10); after ◎ Concentric the crank sat inside the base and its underside (for
  Touch) could not be clicked from any view -> two round faces offer "◎ Soustředně + dosednout · Ø10" first
  (Concentric + Touch of the faces around them: roundEnds / seatPair / joinRound, Solid Edge's Insert; the seat while
  the moving part has no other joints and one is a pin), then "◎ Jen soustředně · Ø10"; the slider's underside onto
  the base needed the view turned (4 drags still 0 spots) -> two flat faces facing up offer "⧉ Položit Smýkadlo na
  Základna" (putOn: the moving part's face on the other side); ▭ Flush of the placed slider's side jumped it 15 mm off
  its line (the crank turned −4.85°) -> a Flush on a part held already keeps the offset as it stands (keepOffset), two
  faces facing the same way list ▭ Flush first. Now: 10 clicks for a new assembly with 4 parts, 3 per joint (a rim,
  Ctrl+click, the first suggestion) — 18 for the five joints, 3 to type 90° and ▶: 28 in all, every face on the first
  click. "One joint is missing": web/js/assembly/missing.js missingJoint(asm) — a free hole and a free pin (isPin: its
  triangles face away from the axis) of a matching Ø (the pin up to 0.6 mm smaller), parallel axes within the parts'
  size, both parts joined and still moving, not in one loop, the joint legal (no part hanging on the other) — the
  nearest pair; ⚙ Mechanism (or the part panel of one of the two when the widget is closed) shows "Chybí jedna vazba,
  aby se mechanismus uzavřel: díra Ø8 (Ojnice) ↔ čep Ø8 (Smýkadlo)" and "➕ Přidat vazbu" (joinRound: one undo step;
  hovering the line lights the hole and the pin). Quiet before the slider is placed, when complete and on all three
  demos; the four-bar without its last joint names "díra Ø6 (Spojnice) ↔ čep Ø6 (Vahadlo)". Tests:
  e2e_mechanism_by_mouse (the build, the helper, Ctrl+Z, the formula at 90°, ▶), e2e_assembly_facepick (now exits 1).
  Left out: the crank's motion is still named after its face ("Otočit kolem osy: stěna Extrude 2") until renamed; a
  slider's line needs a Flush (no rail / slot in the demo's base).

- **Widgets: two opacities, the project tree docked by default done:** a floating widget's panel opacity (background,
  border, header background: 0–100 %, 0 = only its content over the view; CSS color-mix with --pop) and its content's
  (rows, buttons, texts: 30–100 %, opacity on its children with --cop; the mouse over it: 100 %). Ctrl+wheel on the
  header: the panel's, Ctrl+Shift+wheel: the content's (the tooltip names both); the ⋯ menu's two sliders Panel /
  Content (Obsah). State ws.<ws>.pop / .cop per widget (an older single `op` becomes the content's); ↺ Default
  layout clears them; docked widgets are never see-through. A first install (and ↺ Default layout): the project
  tree docked on top of the column in every workspace, compact (34 % of the column, 150–230 px: ~6 rows at
  1280×800); ☰ folds / unfolds it (toggleTree(on) with on given: unfolds / folds), or opens the popup once
  unpinned; a saved layout stays as it was. A floating panel opens beside a floating tree (left 314 px), not on it.
  e2e_left_pins (66 checks), e2e_project_tree starts with the tree behind ☰ (its subject), e2e_project / e2e_tabs open
  ☰ only when the tree is not in sight.
- **🎬 Demo projects done** (the owner: "make demo projects, e.g. a simple crank, where all parts can be seen moving
  right; let the app load them"): demos/ klikovy-mechanismus (r 25, L 100), ctyrkloubovy-mechanismus (a crank–rocker:
  20 / 70 / 50 on a 60 mm base, the loop closed elbow-up) and roboticke-rameno (an open chain: arm on a column, forearm
  on its pin with limits ±135°, a gripper with its turn locked) — 7–8 kB each, 3D models of sketches / extrudes /
  holes, built through the app by tools/make_demos.py (the same tools as the AI: snap_faces, move_free, name_motion,
  drive_mechanism, lock_motion, set_travel), Czech part, joint and motion names, each with a "demo" record {name,
  name_cs, text, text_cs, order} and opening on its assembly. auto3d/demos.py listing / load (only a file of the
  folder, migrated), server /api/demos and /api/demos/<file> (read-only), web/js/demos.js (Open ▾ → 🎬 Demo projects…:
  the names and texts in the app's language; Open -> app.js openLoaded: a new project, a fresh autosave record).
  tools/build/auto3d.spec takes demos/, smoke.py opens one. tests/test_demos.py (each valid, its loop's joints, Czech
  names, small, bad names refused, the routes), tools/e2e_demos.py.
  The owner's own project (data/projects/db8d0297…, "Klikový mechanismus") was left as it is; a copy with J9 back is in
  the scratchpad of the job (not a demo: it has two copies of the crank, sheets and a second assembly).

- **A part dragged in the 3D view moves its whole mechanism done** (the owner: "the parts move as a whole, by their
  joints"): there was no way to move a part with the mouse — a drag always turned the view. web/js/assembly/drag.js
  startDrag(asm, id, press): the chosen part under the mouse (a capture listener on the viewport, before the view's
  controls; their `enabled` off while it drags) — a part of a closed-loop mechanism drives the loop's driver, else
  its own motion (an axis turn first, else a slide along an axis, else the first); a turn follows the angle of the
  mouse's ray on the plane across the axis through the grabbed point (unwrapped past ±180°), a slide the nearest
  point of its line to the ray; each move Assembly.moveFree by the change (limits kept), so placeAll carries the
  parts hanging on it (an open chain) and closeLoops solves the loop; one undo step when let go. The cursor: a hand
  over the chosen part that can move. Assembly.refresh renders ⚙ Mechanism and the toolbar once the loops are known
  (an opened project showed none until the next change). Checked: the crank dragged ~90° — the slider at the formula
  (e2e_assembly_mechanism), the demos' crank, four-bar crank and robot arm (e2e_demos).

- **⚙ Mechanism widget and named motions done** (the owner: "a slider should set the motions of all the parts, not
  one — for simulating whole systems"; "let the motions be named"). The owner's project "Klikový mechanismus" had lost
  its closing joint J9 (the rod's second eye on the slider's pin — the AI removed it, report 2026-10-29 01:51:11);
  added back, the crank drives the rod and the slider (r 30, L 110: x = r·cosθ + √(L² − r²sin²θ) at 90° steps).
  web/js/assembly/mechanism.js: mechanisms(asm) — each mechanismOf loop (its closing part, joined onto two of its
  parts, does not drive) and each part outside loops with a turn / slide about an axis or limits (no fasteners, no 📌);
  the default driver ranked: a full-turn limit, a turn of a part the closing part is on (the crank), any axis turn,
  limits; the travel: limits, else 0 … 360 for a turn (full: the short way round), else ± its size. driveTo
  (Assembly.moveFree, quiet for sweeps; `stopped`: the loop's dead point or a miss), traceOf (36 steps of the driver,
  the first follower's motionPos, put back), MechanismPanel (render on every Assembly.render; ▶: 90°/s a full turn or
  the travel in 2 s each way × speed, reversed when stopped; ⏸ commits; ⋯ driver / speed / ⚠ checkTravel(…, range) /
  📈 SVG). doc.mechs [{parts, name, drive {part, key}, speed}] found again by the parts they share (History captures
  it); a motion's own name in instance.moveNames {key: name} (motionsOf puts it in `label`, keeps `auto`) —
  Assembly.nameMotion; the part panel's motion name and the widget's names renamed by double-click (renameInPlace).
  leftdock.js: addWidget(w, ws, {title, h, close}) / show(w, on) — a workspace's own widget, docked (default) or
  floating like the others, its mode per workspace, its ✕. Toolbar ⚙ Mechanism (only with a mechanism), the part
  suggestion "Drive the mechanism". AI: get_assembly `mechanisms`, drive_mechanism {mechanism, to, driver, name, play},
  name_motion {part, motion, name}. tools/e2e_assembly_mechanism.py; e2e_agent (both refused without a mechanism).
  Left out: a mechanism through a sub-assembly's own moving parts (its inner motions stay in its part panel).

- **⬆ Extrude this face done:** a new sketch entity `{t: "outline", face: {name, fp}}` — a flat face's edges as
  projected edges: doc._face_outlines finds the face again each rebuild (kernel.find_faces), kernel.face_loops copies
  its wires (outer loop + holes) onto the sketch plane, counter-clockwise, with [u, v] rings for "what is inside what";
  kernel._loops takes them (edges named `<entity>:<loop>:<k>`, so the extrude's walls are `<id>:side:o1:0:3`); the
  sketch step's status carries `outline` {entity: rings} for the browser (modeler.faceOutlines: the 3D view's sketch
  lines, the sketcher draws / selects / deletes it). A flat face's suggestions: "⬆ Extrude this face" (rank 0.5, after
  ✏ Sketch on this face) -> modeler.extrudeFace: the outline sketch kept in cmd.pre (shown() builds it before the
  extrude; OK pushes both — one undo step; Cancel drops it), the Extrude panel 10 mm add, no Sketch choice; ⇅ of a face
  extrude (isFaceExtrude) toggles add / cut into the part. The Extrude panel's pull arrow (view.setPullArrow /
  pullHit / pullAlong: any extrude by a distance): its tip dragged sets the distance (0.5 mm steps), the field and
  slider follow. AI: add_feature extrude {face, d, op} (the sketch made first, as the GUI); get_model's sketch
  `outline_of`. tests/test_face_extrude.py (top up 10 = 16000, the hole kept, cut 4, follows the face, a side face,
  watertight, STEP round trip, a missing face an issue); tools/e2e_model_face_extrude.py; e2e_suggest; e2e_agent.
  Left out: an outline entity cannot be mirrored / patterned / offset in the sketcher (it is the face's; draw over it).

- **Server / kernel messages in Czech done:** every message the server sends to the page (issues of steps,
  refusals as JSON "error", warnings, notes — KernelError / ValueError / … texts, issue(…) helpers, {"message": …}
  dicts, `_sized` words) has a Czech entry in web/js/i18n.js: 161 exact texts, 110 patterns ({} = a value; a value
  that may be "" like " (hole 2)" gives both forms). i18n.t(): a mark in front ("⚠ …") is kept and the message
  after it translated; a pattern whose Czech starts with a translated value gets a capital ("Úhel 30 ° se sem
  nevejde…"). tests/test_i18n_messages.py reads the sources with ast (f-string values -> {}, both sides of a
  conditional, names given a text) and i18n.js's CS / CS_PATTERNS, and fails on a message without Czech (`py
  tests/test_i18n_messages.py` lists them); MCP-tool answers (server tool_*, mcp_server, agent_tools) are left
  out — they go to Claude. tools/e2e_i18n.py: a rib with nothing to close against and a ⟋ Draft too steep shown
  in Czech in their panels, texts with values through t(). Left out: several issues joined into one line (each
  is translated only when shown alone), texts of OCCT / library exceptions passed through as they are.
- **Mounting holes on an assembly sheet done:** sheet._mounting (in _assembly, the base part given): the base part's
  free holes (_free_holes: its round faces with the axis outside the part and no other placed part at ¼ / ½ / ¾ of
  the way along it — a pin's / screw's hole left out) matched to the assembly view's circles, then auto_dims "medium"
  on a geometry of only those circles, view by view, with box#x0 / box#y0 the base part's corners -> the same row /
  grid, PCD and ordinate rules; renamed base#x0 / base#y0 (points added to the views), rings "mnt:pcd:…";
  geometry.mount [{view, keys}]; build_assembly runs place() when there are some. The base: doc.assembly_sheet(base=)
  — sheet.js baseOf: the part fixed 📌, else the one most joints are made onto, else the first (not a fastener); in
  sourceHash only when it is not the first (old sheets keep their revision). asmCheck asks for the mounting holes
  (each linked to base#x0 / base#y0 in its view: a pitch its row, a PCD its holes; "a mounting hole (Ø5)", ＋ from
  base#x…). A view dragged or given its own scale: Sheet.replace() -> /api/sheet/place (sheet.place with lay.views
  where the user put them and lay.vscale; _Paper.sc per view) — also after a rebuild when views are moved.
  test_assembly_sheet_mounting_holes (4 holes, 2 pinned: 8 / 42, 64; base a pin: none; all filled: none),
  test_place_for_moved_and_scaled_views, TestSheetRoutes.test_place_again; tools/e2e_assembly_sheet.py (Mount).
  Left out: a mounting hole's Ø (positions only — the base part's sheet gives it), a hole of a sub-assembly's part as
  the base, a hole half split into two faces.
- **AI set up at any time while the app runs done (the owner, for customers without AI access yet):**
  auto3d/ai_access.py — state() no_claude / signed_out / invalid / ok (Claude Code found? a kept key — refused in this
  run? else `claude auth status --json`, asked at most every 5 s); an API key checked with Anthropic (/v1/models: 401 /
  403 refused, else offline) and kept with Windows DPAPI in <data>/ai/key.bin, given to the chat as ANTHROPIC_API_KEY
  (ai_access.chat_env); "Sign in with Claude" = `claude auth login` in its own console window. Routes /api/ai/access,
  /key, /login, /logout (the chat restarts with the new access). agent.py: a turn / exit refused for the access
  (auth_error) -> `auth: true` on done / exit, the key marked invalid. agent.js: the set-up screen in place of the chat
  (install command + Check again; Sign in + register link; key field + console link; polls every 2 s while signing
  in), 🔑 Access (who is connected, Sign out / change the key), the screen back on an `auth` event; Czech in i18n.js.
  tests/test_ai_access.py, tools/e2e_ai_access.py; docs/DISTRIBUTION.md "AI".

- **A Windows program for customers done (docs/DISTRIBUTION.md):** tools/build/build.py — a clean venv (versions
  pinned in tools/build/constraints.txt), PyInstaller one-folder (tools/build/auto3d.spec: web/, library/,
  agent_plugin/, the delvewheel DLL folders of OCP / planegcs / cascadio, BUILD.json with the commit), the portable zip,
  the Inno Setup installer (tools/build/installer.iss: per user, no admin; only when ISCC is installed — it is not on
  the build machine yet: the owner's call) and tools/build/smoke.py on the result. auto3d/launcher.py (the exe's start;
  `py -m auto3d.launcher` from a checkout): the data in %LOCALAPPDATA%\Auto3DModeler (A3D_DATA), port 5173 or a free one
  (--port / A3D_PORT), one copy per data folder (mutex + instance.json probed), Edge --app window with its own profile
  (closing it quits), pystray tray (Open / Logs / Quit, Czech on a Czech Windows), logs in data\logs, a message box when
  it cannot start. The kernel processes run frozen (freeze_support in tools/build/Auto3DModeler.py); the chat's MCP
  server is the exe (`--mcp-server`, auto3d/agent.py when frozen); agent.WORKDIR, meshpart.STORE and the AI's
  RealSWReports (frozen) follow A3D_DATA; version.build reads BUILD.json. tests/test_launcher.py; checked on the built
  exe: smoke (kernel + 4 workers, 8000 mm³ block, STEP), e2e_model_features, e2e_exchange_formats, a real e2e_chat.
  Left out: code signing (unsigned: SmartScreen warning; options in the doc), an update check.
- **Left-column widgets done** (the owner: pin the project tree, the suggestions; drag-and-drop docking; floating with
  opacity; remembered): web/js/leftdock.js. main.layout's first column is now `#leftCol` (flex column) holding widgets
  `.lw-widget[data-w=project|panel|suggest]`, each with an `.lw-head` (⠿ title, ▾ fold, ⋯ menu); the five workspace
  panels are wrapped (their ws class copied, so one shows). Order and the splitters (`.lw-split`, kept while dragged)
  by CSS `order`; the stretching one is the panel (else the last open one), the others `flex: 0 1 <h>px`. A docked
  header dragged (dragStart: ghost + `.lw-mark` drop line) -> the column at that place, or the view -> floating there;
  a floating one is a floatBox (kind `lw-<w>-<ws>`; floatbox.js got `dock` + setDockHook so a floating box dragged
  over the column docks, and box.fb.vp so a box can float over another workspace's view). The suggestions docked stay
  in their view (all the code finding `:scope > .view-suggest` keeps working) as `.docked` position: fixed over their
  place in the column (sync on resize / apply); suggest.js calls leftDock.placeSuggest instead of floatBox, 📌 in its
  head. The project tree: 'popup' (as before, ☰), 'dock' or 'float' (parts.js renders it without its own head then;
  its head in the popup has 📌 and is draggable; a double-click on a row renames: renameInTree). Opacity: Ctrl+wheel on
  a floating header / the ⋯ slider (30–100 %, CSS vars --op-<w> per workspace). Nothing docked: `body.lw-empty`, the
  column 0 wide (a drag shows a drop zone at the left edge). localStorage a3d.leftDock {project, suggest, order, ws:
  {<ws>: {panel, h, fold, op}}} — the project tree's and the suggestions' place and the order the same everywhere,
  the rest per workspace; ⋯ › ↺ Default layout clears it, the lw-* / suggest box places and the column width
  (splitters.resetWidth). tools/e2e_left_pins.py (55 checks). Left out: floating a widget outside the browser window;
  dragging the right panel (it stays as it is).
- **Right column a dock too done** (the owner, 2026-10-29: "like the left panel, the right one customizable — drag and
  drop widgets anywhere"): leftdock.js now runs two columns, `#leftCol` and `#rightCol` (`.lw-col`, grid columns
  `--lcol` / `--rcol` on body), the same mechanics in both (header drag with a drop line in either column or onto the
  view, splitters, ▾, ⋯, two opacities). Modes: 'dock' (left, as before), 'right', 'float', 'popup'. Each workspace's
  right panel (#modelRight, #asmRight, #dwgRight, #shRight, the quick part's) is the body of a widget `props`
  ("Properties"), so every `#modelRight …` lookup still works wherever it is. Sections that stand on their own are
  widgets of their own (SECTIONS): the workspace marks them `data-dock="<name>"` in its render and a MutationObserver
  moves them into the widget's box (`#modelExport` — Export / 3D print, `#asmBom` — the assembly's parts list and
  export, `#shTitle` — the sheet's title block); the widget shows while the panel has it, sized to its content; the
  panel element's querySelector also searches those boxes (the workspaces' `$()` find them). Kept out of the split
  (live updates, many selectors): an assembly part's joints / moves, the sketch and step panels. Persistence: the same
  key a3d.leftDock, now `v: 2` — a v1 state reads as it was (its order kept, 'props' added; ws[<ws>].props: its mode);
  ↺ Default layout resets both columns and both widths. An empty column is a 6 px strip (`lw-empty` / `rw-empty`,
  `.col-empty`; dropping a widget there docks it). gui_state's area() calls any widget control 'panel' wherever it is
  (unchanged). tools/e2e_dock_both.py (35 checks; real drags; the tests looking up moved controls now use #modelExport
  / #asmBom / #shTitle).
- **Widget autosize and rows done** (the owner: "autosize … to have all fields visible; for each widget the number of
  lines, a more button"): each widget's ⋯ menu has ↕ Automatic height (me.auto[w]: docked — flex-basis its natural
  height, never the stretching one; floating — height to its content, at most the view; a MutationObserver per widget
  + rAF re-measures, `natural()` opens inner scrollers; the splitter / a floating grip or edge turns it off) and, for
  list widgets (ROWS selectors: project .pt-row, the step tree's top rows, the assembly's parts, ⚙ mechanism,
  versions, parameters, measurements, or addWidget's `rows`), Rows N (me.rows[w], 0 = all): rows past N get .lw-cut
  and a `⋯ More (k)` / `▴ Fewer` row. The suggestions' N is the same setting (suggestLimit reads it; default 8 or the
  old a3d.suggestTop, which is still written). The floating suggestions table has the same ⋯ menu (dock, float, the
  two opacity sliders, autosize, Rows); its scrollers and every widget body use floatbox's scrollFade (no scrollbar).
  All per workspace in a3d.leftDock; ↺ Default layout resets them. tools/e2e_dock_both.py (+17 checks, 52).
- **Suggestions closable done** (the owner: "close the suggestion table any time; closed it is a button bottom left;
  an auto switch"): ✕ in the table's head (or Space outside boxes and buttons) -> leftDock.setSg({closed, auto}) per
  workspace (me.sgClosed, me.sgAuto); the box is still drawn but `.vs-closed` (so the AI sees it: suggestTables /
  suggestInfo report `closed: true`, runSuggestion opens it first), and a `.vs-pill` "💡 Suggestions (n)" with an
  Automatically checkbox sits at the table's anchor above the filter row. ✕ with auto on turns auto off and says so
  once (a3d.sgToldClose). Docked: closed = folded (fold('suggest') keeps them in step). ↺ Default layout: open, auto. e2e_dock_both +11 checks (63).

- **Nested step tree done** (SolidWorks / Solid Edge style; owner's request 2026-10-29): steptree.js — treeShape (a
  sketch under the first step made from it, a later one made from it too / a pattern's / a mirror's steps as links, the
  point steps in a "Reference" group with the Top / Front / Right planes) and a 16×16 stroke icon per kind (like
  parts.js kindIcon) coloured by group: add green, cut red, edge blue, face teal, pattern purple, sketch grey-blue,
  ref yellow; failed red, off greyed. modeler.renderTree: one-line 22 px rows, 12 px a level, ▸ / ▾ per row
  (localStorage a3d.treeOpen; folded at first), all rows stay in the DOM (folded: hidden). selectStep opens the rows
  above (openTo) and scrolls the row into sight; a click on a sketch's lines in the view chooses the sketch (was: only
  an open line); the mouse on a row lights its faces (view.setHover(-1, ids)); a link row goes to its step; a plane
  row's ✏ / double-click sketches on it. moveStep takes a list (a step dragged with its sketch). gui_state's steps:
  parent / depth / folded. tools/e2e_model_tree.py (30 checks). Left out: a rollback bar (none yet), dragging a point
  inside Reference, datum planes / axes as their own steps (none exist yet).
- **Quick edits of a part with 🔩 real threads done:** an edit waited for the threads' cut and the mesh of the grooves
  (the 29-step tools/e2e_perf.py model, 9 threads: ~17–27 s an edit). Measured where the time went (its full rebuild,
  32.6 s on a loaded machine): the cut 9.7 s, the mesh 15.6 s — of it kernel.tangent_chains 7.5 s (the fillet builder
  given every edge, ~4 ms each: 7 s on the part without threads too) and _outward 4.9 s (the classifier past the
  helical faces). Now: tangent_chains gives the builder only edges that meet another within 20° at a vertex
  (_smooth_ends; the same chains on the perf model and 13 NIST / OCCT / FreeCAD files: 8 s -> 0.1 s, Schenkel.stp
  7.5 -> 0.5 s) and skips the grooves' edges (no step can round them); cut_threads' Body carries `plain` (the part
  before the cut: flat faces' outward side classified against it — the same flat faces) and `grooves`. The mesh is
  the same (positions, faces, edges; chains but on the grooves: test_threaded_mesh_as_before). doc._cuts keeps the
  last 4 cuts per (the solid before them — IsSame —, their holes): a step that leaves the solid as it was (a sketch, a
  point, a step turned off) is not cut again. The browser's rebuild asks `later` (with more than one kernel process):
  real threads not cut yet come back as threads.real {holes, pending} on the plain part, drawn as cosmetic lines, the
  Part panel "⏳ 9 real threads being cut — shown as lines until then"; modeler.cutThreads then asks for the cut
  (POST /api/model/rebuild {cut}: worker op threads_bin, part key "threads:<part>" — a process of its own, so the
  part's next edits are not held up; ⚙ lists "Cutting real threads" with ✕ Stop -> "The threads were not cut
  (stopped)"), one at a time, swapped in when it comes unless the part changed since (resultKey). The AI's settle,
  setThreads and the tests wait for it (this.threading); exports, volumes, the print split and assemblies cut as
  before (identical STEP volume / STL). Measured (same loaded machine, before -> after): the perf model's edit of a
  later step 32.6 s -> shown 2.1 s (in the browser 2.3 s, hover while cutting 40 moves 206 ms main thread, the real
  threads in after 16.6 s), a thread edit 32.3 s -> shown 2.7 s, its full rebuild with the cut 32.6 -> 15.2 s, the
  AI's dimension edit (waits for the cut) 27.7 -> 21.5 s; an M8 through + M6 × 20 blind part: 1.47 s -> shown 0.02 s
  (the cut 0.7 s after). test_real_thread_cut_kept, test_real_threads_later, test_threaded_mesh_as_before,
  test_chains_as_the_fillet_builder_finds_them; tools/e2e_model_threads.py (a fillet / the thread M6 -> M5 / reopened:
  shown with lines first, the analytic volumes after), e2e_cancel.py 2 (the cut stopped from ⚙), e2e_perf.py (the
  part saved to perf_model.json, edits timed: shown / threads in / hover meanwhile). Left out: a coarser mesh of the
  helical faces (the browser holds 236 000 triangles), the cut itself (9.5 s for 9 threads: one OCCT boolean, not
  incremental); a threaded part meshes not watertight at some sizes (e.g. a 44 × 20 × 12 block, M6 at x 14 / 30 —
  BRepMesh on the grooves, before this change too).
- **Hole positions drawn on the sheet done:** sheet.auto_dims places each hole step's holes of one size (a counterbore's
  circles left to its holes) in the view showing them round, from box#x0 / box#y0 (ISO 129): a row / grid its first
  one + its pitch (as before), a bolt circle (sheet._ring: least-squares circle through the centres, equal angles — all
  round ≥ 3, an arc ≥ 4; geometry.views[v].rings {key "pcd:<first hole>", c, r, n, step, start, keys}, its centre a
  point "<key>#c") its centre + one `pcd` dim "PCD Ø60 · 6× 60°" (start "(15°)" when no hole is on an axis), ≤ 3
  (BASELINE_MAX) baseline, more ordinates (`ord`: one row each way, the edge's 0 once a row, values closer than their
  text moved along it, `sh`). Each carries `pos` (its step / "Ø3"). sheet.place (in build, and server._sheet_layout
  for the frame's layout): a side's positions that hit another view, the frame, the title block (180 mm), the iso view
  or other dimensions go to the view's other side when clearer; a callout in the way turned / lengthened (outside its
  view when it can); sheet.overlaps for the tests. sheet.js: the pitch circle dash-dot (.sh-pcd), ordSvg, check()
  joins a pcd's holes to its centre, dxfDims -> real ordinate dimensions (sheetdxf add_ordinate_x/y_dim) and a Ø for
  the PCD; get_sheet's dims {hole_position, ordinate}; "PCD" -> "rozteč". test_hole_positions (4 corners, a row of 5,
  6 around a bore, 6 anywhere: no overlaps), test_bolt_circles_and_crowded_ordinates; tools/e2e_sheet_hole_positions.py.
  Left out: a jogged ordinate's own DXF jog (the leader is ezdxf's), positions on an assembly sheet (only overall sizes).
- **⊿ Rib's other side and its suggestion done:** a rib's `flip` (kernel.rib keeps the closing piece of each side of
  the line: by itself the smaller, flipped the other side's; that side open: "⇅ flip it back"). The Rib panel's
  ⇅ Flip direction; a sketch of one open line (isOpenLine) chosen in the list or clicked in the view suggests
  ⊿ Rib from this line (rank 0), Edit the sketch, Delete (suggestSketch); startRib(id) takes that sketch. AI:
  add_feature rib {flip}. test_rib_flip (a chord across a bore: both segments' volumes, watertight, STEP round trip;
  the L bracket flipped refused); tools/e2e_model_draft_rib.py; e2e_agent.

- **Draft angle on extrudes done:** an extrude's `draft` (degrees, under 45; negative: out): each prism tool tapered
  by kernel.draft before it is added or cut (the neutral plane the sketch; Both sides with a draft = two halves, each
  tapering away from the sketch, as ＋ Other side; d2's piece too; up to a face too; Through all / Up to next refused);
  too much for the walls: the most that fits is told (_sized). kernel.draft now names the tilted walls by
  ModifiedShape (Modified was empty for them — the ⟋ Draft step lost its walls' names too). The Extrude panel's small
  Draft field (no slider; hidden and dropped with Through all / Up to next), the step's text "· draft 5°";
  add_feature / edit_feature extrude {draft} (0 takes it off), get_model shows it. test_extrude_draft (prismatoid
  volumes, symmetric, d2, a pocket, watertight, STEP round trip, refusals); tools/e2e_model_draft_rib.py; e2e_agent.

- **D holes done** (left out of the standard holes before): hole_type "d_flat" — a hole for a D-shaft, its Ø d and
  `flat`, the size across the flat (flat to far side, the D-shaft's own number: Ø5 D4.5); holes.D_FLATS (Ø3 / 4 / 5 /
  6 / 8 -> 2.5 / 3.5 / 4.5 / 5.5 / 7.5, else 0.9 × d: the flat 0.8 × r from the centre; holes.js the same, test-checked).
  kernel.dflat_face (an arc + the chord, its flat facing the frame's x turned `flat_angle`°; r < flat < d else an
  issue; no teardrop, no head / thread); faces `<id>:hole:k` and `<id>:flat:k`. The Hole panel: Type "D (flat)" ->
  Diameter + Across the flat (its slider r … d) + ⇄ (90° a click); no Size / Edit sizes / Teardrop; the flat follows
  the Ø while it is the default. The drawing: callout "Ø5 D4.5 THRU" (sheet.callout / sheet.js calloutRest), the
  flat's edge not dimensioned (_deco, the check), and a hole's arc of more than half a circle is a hole (Ø, ISO 129 —
  was: only ≥ 270°, a teardrop). The AI: add_feature / edit_feature hole {hole_type: "d_flat", d, flat, flat_angle};
  get_model's flat. tests/test_hole_dflat.py (circle − segment volumes, the flat's place both ways, watertight, STEP,
  callouts, errors), tools/e2e_model_hole_dflat.py (15 checks), e2e_agent (the Ø5 D4.5 through 20).
- **⛓ Fillet / chamfer tangent chains done:** OpenCASCADE's fillet and chamfer builders always round an edge's whole
  tangent chain (its contour) — one top edge of a box with rounded corners took all 8, but only that edge was shown
  picked and the 7 other new faces had no name. kernel.tangent_chains (the builder's own contours, Add without Build:
  < 1 ms on a box) -> each tessellated edge's `chain` (heavy models: none); round_edges names every face of the
  contour `<id>:round:k` / `bevel:k`; chain_size. The panel's ⛓ Whole chain (on by default; off stored as
  `chain: false`): the hover lights the chain, a click picks / drops all of it ("Added a chain of 3 edges."); off, a
  click takes one edge and the step warns "It goes on along 2 more edge(s) …" (the rounding cannot stop there). The
  AI: add_feature fillet / chamfer {chain} (default true: each given edge with its chain, as a click), find_refs
  edges `chain: n`, get_model `chain: false`. tests/test_fillet_chain.py (Pappus volumes of R1 / chamfer 1 round a
  rounded outline, all faces named, watertight, STEP, the 8 refs = the 1 ref, the warning); e2e_model_features
  (⛓ off / on clicks), e2e_agent (chamfer from one edge: 8 edges, −24.225 mm³).
- **The AI's screenshots whole and clean (RealSWReports 2026-10-29 01:55:47, 2026-10-28 04:30:30 / 04:30:48) done:**
  with the chat beside it the view was a 339 × 900 strip and the picture too — an assembly 240 mm long cut off.
  ModelView.snapshot({w, h, fit, faces, over}): the renderer and the label layer set to 1200 × 900 for one frame (the
  camera's aspect too), fitted, drawn, put back in the same task (nothing flashes); the hover, picks, the chosen step's
  tint and an assembly part's glow (a clash's red stays) left out of it; `faces` lit orange (MARK). fit() now puts the
  ball round the box inside the narrower of the two view angles (+5 %) — a narrow view backs off. get_screenshot
  {highlight: [face names or step ids]} (a 3D model; wrong names refused, the lit faces named in the text; refused in
  an assembly); the size labels drawn where the picture's camera puts them. add_feature / edit_feature: an extrude /
  revolve / loft / sweep add that adds nothing warns "It adds nothing — it lies inside the part (⇅ flip)" (a cut
  already did). tools/e2e_ai_screenshot.py; e2e_ai_sketch counts the label boxes anywhere in the picture.
  Already done before (skipped): fit / section off / sheet screenshots, went + volume_change, flush faces merged,
  find_refs of_step, measure in models, the sheet check's decal edges and keys, steps named after their sketch.
  Left out of the wishlist (more than ~2 inputs, or a new feature type): an extrude dir "into_body" / world direction,
  a D-flat hole (head cbore / csk and thread "M5" exist as hole options), a sketch on a face in world coordinates
  (exists: origin "world" / "corner"), a rib feature from an open line, check_model (check_print does min_wall /
  overhang on a 3D model).
- **The AI's GUI audit (2026-10-28) done:** checked each item first — the duplicate Cancel (a feature panel's Cancel
  plus the rebuild's) and the greyed toolbar after it, ⊂⊃ Slot in the sketch bar, the "↕ Plane at" arrow (+ = …),
  sketch names and an unused sketch in ⬆ Extrude, the last hole / cut in ⁂ Pattern, hole position / head / thread
  fields and "Measure catches" only where a click snaps had been fixed by later work. Now: the rebuild's button is
  ✕ Stop (one Cancel on screen), OK / Cancel in the view's corner get tooltips (actiondock.js, by data-a), ▣ Solid from
  a file is greyed while a step is open; ⁂ Pattern's Repeat is a checklist of steps by name (several repeated
  together, at least one kept); ⇋ Mirror has ▱ Face (then a click on a flat face: "Across the face …"); ◜ Fillet /
  ◸ Chamfer say what the last click picked ("Added the edge between … and …", "Added 4 edge(s) of …") and show the
  step's state once built; face labels ("the top of …") in Czech; gui_state lists the 3D model's step tree (id, name,
  what, off / failed / selected / editing). tools/e2e_model_gui_audit.py. Default step names were another job's.
- **The AI teaches, tests the GUI and suggests done:** the owner asked that the AI show the user what to do, test the
  UI on /uiTester and report missing features. New browser tool gui_highlight {control (n / label as gui_action) or
  at (a view spot), text, step, wait, timeout, clear} (web/js/agent_teach.js): a pulsing ring + a speech-bubble tip,
  the rest dimmed by the ring's shadow; pointer-events none, so the click goes on to the control; a capture
  pointerdown / click on it ends the tip ("clicked"), Esc (consumed) or ✕ "closed", the next tip "replaced", clear;
  wait answers then (timeout 60 s, ≤ 120). Follows the control each frame (found again by its label when the panel
  is drawn anew), z-index above floating boxes and menus. Skills teach-the-user, ui-tester (test parts, the GUI path
  of each feature, Czech, report once, a summary table), suggest-features; a "Missing a tool?" line in the six
  workflow skills. Chat slash commands (auto3d/agent.py expand_command: /uiTester, /suggest -> the skill's
  instruction; the chat shows what was typed). report_problem refuses a title like an earlier one (auto3d/reports.py:
  words without endings, Jaccard / cover; no false pair among the 26 real reports) unless again: true; list_reports
  {search, kind}. tests: test_report_problem_once, test_report_titles_alike, test_slash_commands, test_tool_schemas;
  tools/e2e_ai_teach.py (26 checks), e2e_agent (gui_highlight + list_reports through MCP), e2e_ai_gui.

- **Standard holes done:** auto3d/modeler/holes.py — per size M2 … M20 the clearance Ø (ISO 273 medium), a counterbore
  for an ISO 4762 socket head (DIN 974-1: M5 Ø10 × 5.4), a 90° countersink for an ISO 10642 head (its dk: M5 Ø11.2) and
  the tap drill (THREADS / PITCH moved here from doc.py); a hole step's `hole_type` (clearance / counterbore /
  countersink / tapped) + `standard` "M5": holes.resolve fills d / head / head_d / head_depth / thread from the table
  (the step's own sizes win, the type sets head and thread) — in the build, the callouts (_holes), _threads and
  thread_holes (cosmetic / real threads), so the callouts are the existing ones ("Ø5.5 ⌴ Ø10 ↧ 5.4", "M5 ↧ 10").
  The Hole panel: Type (Simple / Clearance hole / ⌴ / ⌵ / Tapped) and Size replace the Thread and Head choices;
  web/js/modeler/holes.js (the same table, test-checked) writes the sizes on the step (setHoleStandard), the first
  size the nearest to the hole's Ø, then the last one used; the sizes folded under Edit sizes (details.m-holesizes);
  Fit shown for a simple hole. A step made before (thread / head, no type) shows as Tapped / ⌴ / ⌵ with Size "—".
  The AI: add_feature / edit_feature hole {standard, hole_type} (a new size or type: the table's sizes again; "simple"
  keeps the Ø). tests/test_hole_standard.py (the table, resolve, M5 counterbore / countersink / tapped / M4 clearance
  volumes vs. formulas, watertight, STEP round trip, callouts, errors); tools/e2e_model_hole_standard.py,
  e2e_model_hole_head.py (the new choices), e2e_agent.py (M5 counterbore, M6 edit). Left out: the D-flat hole (a
  shaft's flat is a profile, not one more size). The callout keeps the drawing's order "Ø5.5 ⌴ Ø10 ↧ 5.4" (hole first,
  as the existing callouts and their tests), not "⌴ Ø10 ↧ 5.4 / Ø5.5".
- **Closed loops of joints solved together done (RealSWReports 2026-10-29 crank–rod–slider):** a part joined onto
  two parts that move (the rod's second eye on the slider's pin) made its first joint "not held" — a part's joints
  were applied one after another, the last one won. Now web/js/assembly/loops.js: findLoops (a part with joints onto
  ≥ 2 parts + the parts between them down to the parts all hang on; 📌 fixed parts and parts without joints stay;
  loops sharing a part merged), solveLoop (damped least squares — Levenberg–Marquardt — over a small move of each
  free part, 6 numbers each; the misses from joints.jointResidual: smooth, 0 when a joint holds, for every joint
  type, a locked turn and an axial distance too; the damping keeps the least move, so a way left free is not taken),
  loopFreedom (the rank of the misses' Jacobian -> how many ways the loop moves: 1 for a crank-slider) and
  screwBetween / stepsBetween (a driven part's move from where it was as a screw, in ≤ 10° / L/10 steps).
  Assembly.applyMates(drive) = placeAll (as before) -> closeLoops -> placeAll again when a loop moved (the parts on
  it go along). The driven part ({id, was}: moveFree — the motion sliders and move_free —, ▶ playTravel, ⚠
  checkTravel) stays where it was put and is followed step by step; past a dead point it stops at the last place
  that closes (bisected; move_free says "stopped … a dead point"); a loop that cannot close keeps the parts as
  placed and says why on its joints (whyNot: "the closed loop I2–I3–I4 cannot close here …") and in the panel.
  Open chains are not touched (a loop is solved only when its joints miss by > 1e-5 mm). get_assembly: `loops`
  [{id, parts, closed, free_motions, stopped, drive}], a part's `loop` / `moves_with_loop`; the panel's hint "In a
  closed loop with …". A placed crank-slider: 0.1 ms to place all again, 0.6 ms a 3° turn followed, 12 ms when it
  cannot close. tools/e2e_assembly_loop.py (r 25, L 100: the slider at r·cosθ + √(L² − r²sin²θ) to 0.05 mm at
  0 / 30 / 60 / 90 / 180 / 45 / −115° — 90°, 135° and −200° in one move_free —, driven by the slider, by the panel's
  slider, ▶ played, check_travel over 0 … 360, the dead point, the loop closed by itself when joined 12 mm off,
  the rod too short and back). Left: the loop solve is in the browser only (no Python tests — there is no JS
  runner); sub-assemblies' own loops solve in their engine (innerAsm) but a loop through a sub-assembly's moving
  part and this assembly's parts is not looked for.
- **A short, ranked suggestions table done:** the owner asked for a clean table, the most relevant first. Every table
  (a sketch's picks, a face of the 3D model, a placed part / a face in an assembly) goes through suggest.js
  showSuggest, which now dedupes rows (same icon and label), keeps the N most relevant (a row's `rank`, else its place)
  under their sections, and puts the rest behind a last row "⋯ Show all (n)" — it opens everything in sections in
  place (remembered for the session, sessionStorage a3d.suggestAll; "▴ Fewer" closes it). N (3…30, default 8) is set
  in the table's own header: "Suggested" opens a small number field (localStorage a3d.suggestTop). Ranks: a sketch —
  the likeliest four (a size, the relation nearest to true), Delete, then for one / two shapes the other relations,
  construction, the edits (for more shapes the edits first); the sketch's own "More…" is gone. A flat face — ✏ Sketch
  on it, ◎ Hole, ◜ Fillet, ◸ Chamfer, ✎ Edit, text, shell, ✕ Delete (mirror, split, turn off, threads under Show
  all); a round face — its edges, threads, edit. A placed part — 🔗 Join, ◆ Open its part, ✎ Edit here, 📌 Fix …; an
  assembly face — its joints (touch / gap / flush / concentric / tangent) first, the part's actions under them.
  e2e_suggest (14 checks), e2e_sketch_multiselect, e2e_model_split / threads updated. Not done: a drawing sheet has
  no suggestions table (nothing to rank); "Extrude this face" is not a command yet.
- **A placed part's panel in Czech, each action once done** (AI report 2026-10-29-015647): the panel's "◆ Open its
  part", "📌 Fix in place" were one text with their icon (not in the dictionary: English) — now t() on the words; the
  joint names' tooltip translated before data-no-i18n (a named joint's) skips it; the suggestions table left out the
  chosen part's actions the panel already has (Assembly.inPanel: chosen alone, not an inner part, no paint / bolt); the
  turn rows read ↻ X / ↻ Y / ↻ Z and gui_state names a row's inputs by it (.as-rot; an empty label: the row's name, not
  "input"); a motion is named by its joint's own name, a library / imported part's face by what it is
  (partFaceText: "the round face Ø22", "a flat face"). tools/e2e_assembly_panel_cs.py.

- **gui_action safe with changed panels; ⧉ its own part undone takes the copy done** (AI report 2026-10-29-015635):
  the AI gave a value to control n 63 — a slider in its last gui_state, a button after a part was chosen — and the
  button was clicked (a copy made). Now a value for a button (or anything but a slider / box / choice; a checkbox takes
  true / false) is refused, nothing done; every gui_action answer whose controls changed has `controls` with their new
  numbers. Undo of ⧉ Make it its own part: Assembly.tidyCopies after each undo / redo takes the copy out of the project
  (project.take) while no assembly uses it and it is unchanged; a redo puts it back (putBack). tools/e2e_ai_gui.py.

- **Assembly sheet: balloons on a bare face, checked; only overall sizes asked done** (AI reports 2026-10-28-042725,
  2026-10-29-015608): a balloon's leader ended at the middle of its part's box — a base plate's under the rod lying on
  it, next to the rod's own. sheet._shown_spots: a depth buffer of the iso view (points strewn over each part's coarse
  triangles, kernel.view_triangles; 220 cells across), each part's spot inside its largest patch no other part hides,
  apart from the spots taken before (the least seen first) -> marks[id].Iso and .seen (mm² seen); a big assembly drawn
  from its mesh keeps the middles. sheet.js: an item's one balloon on its copy that shows most (a sub-assembly: on its
  part that shows most). get_sheet: parts_list[].balloon {at_mm, leader_to_mm, points_to} and balloons {count, ok,
  problems: a pos twice, a qty not what the level places, an item with no balloon}. check() on an assembly sheet
  (asmCheck): only the overall length / width / height (a part's holes, radii and edges belong on its own sheet).
  test_balloon_spot_on_a_bare_face, test_assembly_sheet_exploded; tools/e2e_assembly_sheet.py (2 Lids: one item, qty
  2, its balloon on the visible one; an overall size removed: just that one missing).

- **A threaded part's volume integrated once done:** kernel.volume keeps the last 4 shapes' volumes — the part with
  🔩 real threads was integrated after its cut (the check that something was cut) and again when meshed (the adaptive
  rule on helical faces: ~3 s). The 29-step model with 9 real threads (tools/e2e_perf.py model): its rebuild after a
  dimension edit 22.9 -> 18.6 s on the server, switching to real 21.1 -> 16.8 s; still the cut (~9.5 s) and the
  mesh of the grooves (~10 s) each edit. test_real_thread_volume_once.
- **Quick hover and picking on big parts and assemblies done:** the owner found the app slow, at times frozen.
  tools/e2e_perf.py measured it (real CDP mouse input; per action the main-thread ms, long tasks, /api times): with no
  tool on, every mouse move cast up to 600 rays through all the part's triangles for the hover's snap dots
  (setHoverSnaps) — a 29-step model with 9 real threads (236 000 triangles) froze up to 6 s a move, the 44 MB board
  (943 000) up to 23 s. Now modeler/bvh.js: a tree over a mesh's triangles (Mesh.raycast through it, the same hits
  as three.js' own — 3000 rays checked — about 70 × quicker; built when the browser is idle after the part shows);
  the hover worked once a frame (modeler / assembly: a press runs a waiting one first); snap points and edges on the
  screen kept while the camera stays (snapPoints, snapNear, edgesOnScreen: an edge whose screen box is farther than
  the reach skipped); a hover repaints only the faces whose colour changes, sent to the GPU as ranges (repaint); a
  step's faces looked up once per body; the assembly keeps each body's triangles, normals, edges and colours across
  draws (a hover over another part, the explode slider, a choice drew everything anew); a sketch's lines and circles
  drawn as one object per colour with kept materials (the Drive Gear's 732 shapes: 700 objects and materials a
  hover). Main-thread ms before -> after: model hover (80 moves) 68 757 -> 327, a click 6 968 -> 45; board hover
  (40) 92 217 -> 599, turning 21 901 -> 218, a click 20 525 -> 60, measuring 1 217 -> 47 (opening 913 -> 1 225: the
  tree); MIT E-Vent hover 3 278 -> 313, explode slider 850 -> 77, choosing 287 -> 71; Festo hover 1 321 -> 249;
  gear sketch hover 2 749 -> 307, box select 614 -> 62. The sheet (dragging a dimension ~25 ms a move: SVG layout)
  and the idle app (6–10 ms a second with three tabs: the render loops only draw when something changed, autosave
  and the window sync wait for a change, no polling but the AI's long poll) needed nothing.
  Left: real threads are cut and meshed again on each edit (9 holes: ~23 s on the server, the view stays usable).
- **⚙ What is working now done:** the owner could not see what ran in the background or stop it. worker.Pool keeps
  its jobs waiting or running (Pool.jobs: kind in plain words — worker.KINDS —, the part's name, its process, waiting /
  running, since) -> list_jobs(); cancel("k<n>") stops one as a Cancel does (leaves the queue, else only its process
  is killed; its request's rid cancelled too, so its page says Cancelled). progress.operation(rid, kind) and
  begin_request(what, req): a before_request hook takes the part's name from the body's `what`, else the tab on
  screen (X-A3D-Tab), and the page's request id (X-A3D-Req). GET /api/jobs: the kernel's jobs plus slow requests
  outside it (a quick part's slicing, a file being read: "r<rid>"); POST /api/jobs/<id>/cancel (404 when it has
  ended); _model_call answers a stopped job 409 cancelled. web/js/jobs.js: a fetch wrapper marks the page's slow
  requests (an upload is listed before the server has a job); ⚙ N in the top bar (#jobsBtn) only while something
  runs, polled every 1 s then (4 s idle, so other windows' and the AI's jobs show); the list: kind · part · time (live,
  only the times redrawn — just after each whole second of the first job, from a start time on the page's clock that
  polls never set back: redrawn once a second at a random moment, a number could stay for almost 2 s) · ✕ Stop; it pulses when a job runs over 3 s with no progress box on screen.
  tests/test_kernel_pool.py (test_jobs_listed_and_stopped_while_waiting, test_stop_from_the_jobs_list_kills_only_that_worker,
  test_jobs_route); tools/e2e_cancel.py 1b (the board's import: ⚙ 1, the list names the file, ✕ Stop: gone in 0.13 s).
- **Cancel stops the job once, nothing restarts it done:** the owner saw Cancel not stopping the kernel and the
  busy text going Building ↔ Cancelling. Found: the app's busy box (#busy) polled the stage and wrote "Building the 3D
  model" over "Cancelling…"; it tracked one rid, so a second request at the same time (opening a sheet runs ensure
  twice: the tab's load and sheet_open) was not cancelled and came back; a cancelled sheet was made again by the next
  ensure(); the box sat in the quick part's viewport, invisible in the other workspaces; a tab shown while another one
  loaded (📄 Drawing during an assembly's load) got its data overwritten with 'live' (parts.show) — ↻ Try again then
  did nothing. The kernel side was right (Worker._run kills only that process on Cancel). Now web/js/progressbox.js
  (from app.js): several rids at once, the newest shown, ✕ Cancel cancels them all, "Cancelling…" until they end (the
  poll no longer writes over it), then gone; it moves to the viewport on screen (bottom middle outside the quick part);
  `delay` for quick ones. The 3D model: Cancel → "Cancelling…", the queued rebuild dropped, the last result kept with
  "Cancelled — ↻ Rebuild". The sheet: one job per drawing (ensure waits for the same one), a cancelled one is not made
  again until ↻ Try again or a change. The assembly's part builds go through the box (a cancelled part keeps its
  body; no clash check after it); a newer clash check cancels the older one's job (/api/assembly/clashes takes a rid,
  409), the ⚠ list has ✕ Stop; the print split (/api/print/plan rid, 409) too. tests/test_kernel_pool.py
  (test_cancel_kills_only_that_worker, TestCancelRoutes); tools/e2e_cancel.py: the board's import, 12 real threads, MIT
  E-Vent's sheet — before: Cancelling… → gone → Making the drawing… → Building again; after: Cancelling… → gone in
  0.13–0.23 s, no kernel CPU after it, nothing sent again.
- **AI: simplify_sketch done:** {id, op simplify | join | outline, tol} (agent_tools.py, agent_model.js: the whole
  sketch through /api/model/sketch/clean, committed as one change) -> the step's result + shapes / points before →
  after, area_mm2, dropped sizes; the skill use-a-drawing says when. tools/e2e_agent.py (a 72-sided polyline -> one
  circle, π 20² 5; a wavy 120-line outline -> join: one spline, the area kept; a non-sketch refused).
- **⛓ Merge in sketches done:** sketchclean.join (each connected chain -> one `fit` spline per run between corners
  > 25°, a straight run a line; _dense_chain samples it, fit_spline within tol; a closed chain starts at a corner, none:
  one closed spline) and outline (polygonize the picks within tol, even-odd -> one block {polys, w0, h0, at}), POST
  /api/model/sketch/clean {op, sketch, ids, tol}. Sketcher: splines can be picked (pickOf / splineAt, box, delete,
  copy); mergeItems -> ⛓ Join into one curve / 🧹 Simplify first in the short list for a chain of ≥ 6 pieces
  (chainOf: ends within 0.02 mm count as one — the old conversion's ends missed by a hair), ◆ Make it one outline in
  the short list for closed loops (else under More… → Edit); mergeBox: one input (Tolerance), shown at once
  (mergeTo: from the snapshot each time, one undo step), "732 → 13 shapes", Enter / Esc; a `fit` spline's points
  hidden unless it is clicked (hiddenPts: not drawn, not picked). The bar's ⛓ Merge (copy group): with picks the table
  offers only the merge rows; with none a mode (clicks and boxes add) whose table has 🧹 Simplify the whole sketch.
  Drive Gear.dxf as the old conversion made it (732 shapes, the owner's screenshot): ⛓ Join -> 13 shapes (one spline of
  770 points round the teeth) in ~1 s, area 1540.3; 🧹 Simplify -> 316 (252 at 0.02 mm). tools/e2e_sketch_merge.py.

- **Clean 2D drawing -> sketch done:** auto3d/modeler/sketchclean.py from_drawing (POST /api/drawing/sketch; editor.js
  drawingToCleanSketch, the old drawingToSketch as the offline fallback): ends within tol welded (_Nodes: union-find on
  a grid; tol = max(0.01, 1e-4 · size) ≤ 0.1 mm), pieces shorter than tol absorbed, chains through two-piece nodes
  (_chains): collinear lines -> one, arcs on one circle -> one (a full turn: a circle), a polyline -> lines / arcs
  (greedy _segment, the arc's centre on its ends' bisector so both ends are on it) and runs of ≥ 3 smooth ones -> one
  spline when that is fewer points; a `smooth` poly (read_drawing marks SPLINE / ELLIPSE) -> one line, arc or spline
  (fit_spline: a natural cubic over the chord, as splinePts, points added where it strays > tol both ways); a closed
  polyline -> a circle or starts at its sharpest corner. tan relations line–arc only in sketches of ≤ 60 shapes (in the
  gear they made each solve 7× slower). Finger.dxf: 702 shapes / 827 points -> 231 / 378, area 7186.81 -> 7186.75
  (the old conversion's ends missed by a hair: its area 185 — nothing closed). Kernel: a closed spline going clockwise
  is reversed in _mixed_wire (holes are put in reversed: a CW one gave 1335 for 1178); kernel.volume integrates a
  solid with a B-spline edge of > 8 knots span by span (VolumePropertiesGK, IsUseSpan) — a plane bounded by one
  770-span curve was 8 % off with the adaptive rule (CTC-02's reference: 47106859.125, as GK without spans at 1e-9).
  tests/test_sketch_clean.py; tools/e2e_sketch_merge.py (part 1).

- **Autosave waits longer on a busy machine done:** autosave._write / _read retry a Windows sharing violation
  (WinError 5 / 32) for up to ~8 s with a growing pause (_pause), not ~2 s / ~1 s — under the full test run with the
  kernel pool busy, test_same_project_saved_at_once once failed with "Access is denied".
- **Default title block B — ISO 7200 done:** a drawing that chose no template uses "B — ISO 7200" (title block B,
  parts list B, the ISO 5457 frame) — the owner's choice; sheet.js DEFAULT_TPL, the AI's sheet_edit without a name too.
  Tests that check the Modern block pick it explicitly (e2e_sheet, e2e_bom, e2e_sheet_views_templates).
- **The sketch panel from the AI's UI report (RealSWReports 2026-10-28 21:49:41) done:** Sketcher.stateHtml (under
  the free count): the contradicting locks named (`conflicting`, kept by takeState) — their rows `.sk-dim.bad`, their
  shapes red (badOf takes the dim ids too); locks held twice; 🪄 Lock at rounded values (autoDimension {round}:
  sketchauto.roundValue — whole mm, ½ under 5 mm, whole degrees; `rounded` lists each size as drawn -> as locked, so
  the order of rounding does not show) with ✓ Keep / ↶ Take back (back()); ∪ Unite overlapping shapes (overlapping():
  unionRegions — `crosses`: a region no other one crosses, a hole, is left alone — and innerPiece, ≤ 80 shapes).
  Rows: data-dimrow, "Width / Height / Length" by the line's H / V; bindProps (one hook line in modeler.renderProps)
  lights the row's view label (mouseenter on it: its highlight) and binds the buttons. Suggestions:
  sketchauto.standardShapes (a loop of 2 lines + 2 half arcs of one radius, 4 nearly level / upright lines at right
  angles without all their H / V, 2 arcs on one centre) -> convertShape (slot: tangent joins, eq, one group;
  rectangle: H / V, one group; circle: one circle, a rad lock -> its dia) first in the list; ∪ with 2+ picks when
  shapes overlap. tools/e2e_sketch_ui.py.
- **The AI's sketch tools (RealSWReports 2026-10-28 21:49 / 21:58 part 1) done:** web/js/modeler/agent_sketch.js
  (spread into modelHandlers): get_sketch (a detached Sketcher on the step, or the open one: points, shapes with
  coordinates and state, relations named, dims {id, kind, name, value, locked, between}, dof, free, conflicts
  {contradicting, held_twice}), sketch_auto_dims {id, round}, sketch_dim {id, dim (an id or "len:l1" / "dia:c1" /
  "rad:a1"), value | locked}, sketch_trim {sketch, shape, at} (at projected onto the shape), sketch_union {sketch} —
  withSketch opens a closed sketch in the editor, runs it, finishes it (one model undo step), and returns the
  sketcher's toasts as messages. Sketcher.unionShapes: the closed loops / circles as they are (a polygon each), then
  the middle of each piece between crossings that lies inside another region (not on its border) is trimmed
  (trimAt {quiet}), up to UNION_MAX, one sketch undo step. trimAt keeps a trimmed shape's whole-shape relations (eq,
  tang, par, perp, conc — once) and the tangents at ends that stay (re-pointed to a split-off piece), and drops an
  `on` whose point became the shape's own end (held twice). The report's rect + slot: one outline of 5 lines + 2 arcs,
  59945.008 mm³ = the exact union (shapely); the overlapping shapes extruded gave 59942.757. gui_state: a sketch
  label is a control {kind dim, label "d3: 65", state locked / free / set by the others / reference}, a 🔒 / 🔓 / ✕
  button on a label or panel row says which ("65 › ✕"). Screenshots: the labels are CSS2D page elements over the
  WebGL canvas, never in its picture — model_screenshot renders them for its camera and draws each one (box + text)
  onto the image (drawLabels). Schemas in agent_tools.py, the model-a-part skill, e2e_agent's case.
  tools/e2e_ai_sketch.py.
- **🪄 Auto-dimension that says what it did (RealSWReports 2026-10-28 21:48 / 21:49 / 21:58 part 2-3) done:**
  Sketcher.autoDimension({round}) -> {added, relations?, references?, dof, free: [shape names], error?} (for the AI
  too): a lock only held twice (constraints.solve's new `redundant`, apart from `conflicting`) becomes a reference
  first; contradicting locks are named (ruleNames) and red; then sketchauto.nearRelations (H / V within 0.5°, a line
  running into an arc within 0.5° -> tan, radii within 0.5 % -> eq, each kept only when it lowers the dof and moves no
  point over 0.05 mm), then autoDimCandidates (reordered: sides not ending at an arc, free-standing arcs' centres from
  the nearest part edges / the origin, the shape's place, then the sides that end at arcs, slanted lines) — each kept
  only when it lowers the dof, the solver's points applied after each. Still free: a toast naming the shapes
  (shapeName). Labels of sizes the others set show ＝ (driven, no 🔓). Joined curves (⛓ `fit` splines, the merge on
  main): constraints._fit_curves — each inner point keeps its distances to two anchors (its ends; closed: start + the
  first inner point; distances as drawn, so a drag moves the curve), soft (never a conflict), left out of the free
  check and FREE_CHECK_MAX: a 300-point curve is 4 free, not 600. test_a_joined_curve_moves_as_a_whole;
  tools/e2e_sketch_autodims.py (the hand-drawn rect ∪ slot: 5 free -> R + 2 centres, 9 locks, ＝ labels, the volume
  kept on Finish; the AI's shapes: 9 locks at once; tangents / equal found first; a lock held twice; one that does not
  fit named).
- **The profile sketch that froze the AI's session fixed (RealSWReports 2026-10-28 21:58) done:** the AI's
  get_screenshot waited for two animation frames, which a hidden / covered window never gets: the call never ended,
  the page's bridge loop (agent.js) stopped asking for calls and after 45 s the server said "the app is not open".
  frames.js nextFrames(n, ms) ends by the clock too (every awaited requestAnimationFrame: the screenshots, sketcher's
  label edits); the bridge gives any call at most CALL_BUDGET_S = 140 s and goes on. The profile itself opened red
  (dof -2: its arcs' centres were locked besides their locked ends) and so 🪄 was hidden — sketchFromShapes: an arc's
  centre is not locked (an exact point), a tangent `tan` where the line beside it runs in smoothly (one per arc), else
  its radius; a slot: tangent sides, `eq` ends, one radius (5 sizes, was 6 + 4 free); points worked out from others
  kept exact (r9), so opening / finishing moves nothing; the H / V clean-up no longer drops a tangent. Guards:
  constraints.solve's free-size check has a time budget (FREE_CHECK_SECONDS = 1.5: `free.partial`, `free.unknown`
  — shown uncoloured), Sketcher.solve gives up after SOLVE_WAIT_MS, 🪄 after AUTO_DIM_MS (what is locked stays, a
  toast says so) and solves without the free check per try, an error in it is a toast (was silent); a reopened sketch
  gets its colours at once (takeState / badOf: the shapes of conflicting locks red — `bad` was never set);
  edit_feature's new shapes drop the old place / rd / hidden. test_free_check_has_a_time_budget,
  test_ais_profile_with_tangent_arcs_is_fully_defined, test_ais_slot_is_fully_defined_by_five_sizes;
  tools/e2e_sketch_freeze.py.
- **M0 done:** several parts in one project (tabs), project file v3, optional packages, `/api/kernel`.
- **M1 done:** the 3D model workspace; sketch → extrude (add / cut, through all, both sides); worker process; STL / STEP.
- **M2 done:** the sketcher.
  - Rectangle, line and circle; sizes lock by typing 🔒 (planegcs).
  - Dragging moves what is free.
  - ↔ Dimension between points, circles, lines, the origin and the part's edges; ✕ deletes it.
  - The part is see-through while sketching.
- **M3 done:**
  - Faces named through OCCT history, so steps follow their faces and edges.
  - Fillet, chamfer, hole, revolve and shell.
  - Turning steps on / off; unused sketches shown as lines.
- **M4 done:** ◆ To 3D model (any classic part's outline becomes a sketch block); 🖼 Outline in a sketch (picture,
  DXF / DWG, PDF); 🖨 Prepare for 3D print (a printing copy of a model part as a Quick part). Also: dimensions can be
  locked / freed / deleted / hidden in sketches, drawing dimensions can be hidden in the Quick part, the hover
  highlight shows what a dimension attaches to, and the origin is always shown.
- **M5 done:** AI tools for model parts (list_parts, open_part, new_model, get_model, find_refs, add_feature,
  edit_feature, delete_feature, turn_off_feature, prepare_print; screenshot / export / undo follow the part on
  screen); skills in agent_plugin/ loaded with `--plugin-dir` (`--tools Skill`), also served as get_guide and MCP
  prompts. A real chat built a filleted plate with a hole using the model-a-part skill, with the exact volume.
- **M6 done:** 📏 Measure (faces, edges, Ø, distances; corner snapping; hidden edges not picked), ✂ Section (X / Y / Z,
  slider), material and mass (also for the AI: set_material, get_model).
- **M7 done:** assemblies (a project tab kind): insert model parts, 🧲 snap face to face (turned + centred), position /
  90° turns, explode, parts list with masses, STL / STEP export (`/api/assembly/export/step`, placed bodies in one
  compound), saved in the project.
- **AI for assemblies done:** new_assembly, get_assembly, insert_part, snap_faces, place_part, remove_from_assembly;
  skill assemble-parts; tools/e2e_assembly_ai.py.
- **Pattern done:** ⁂ Pattern (in a row / around; repeats extrudes, revolves, holes and patterns by their tool
  solids, names "<id>:<k>:<name>"); AI `add_feature {type: "pattern"}`; tools/e2e_model_pattern.py.
  Edge picks in a perspective view (view.edgeAt): whether an edge is hidden behind the part is judged at the edge's
  point nearest the mouse ray (Ray.distanceSqToSegment), not at the screen's t lerped in 3D — that point slid along an
  edge seen at a slant (the plate's short edge in iso: 0.65 mm farther than the surface, over the slack) and a visible
  edge was refused (⁂ Pattern's "click an edge" did nothing there). e2e_model_pattern.py now asserts (10 checks).
- **Arcs done:** ◠ Arc (3 clicks: start, end, bend), R dimension (planegcs arcs), true circular edges in the kernel,
  AI shape {slot}; tools/e2e_model_arc.py.
- **Dimensions follow the part done:** sketch dimension ends to the part store {vertex: {faces, fp}} or
  {edge: {a, b, fp}}; the rebuild finds them again (kernel find_vertex / find_edges), re-solves the sketch and
  hands the new places back (status.update). Holes are placed from the face's edges (hole.from). tools/e2e_model_refs.py.
- **Round corner done:** ◜ Round corner in sketches (roundCorner: tangent arc, constraints tan + corner — the sharp
  corner stays a point on both lines); the AI's rect {r}; typed sizes keep the other axis (solve keep=u|v).
  tools/e2e_model_round.py.
- **Custom references done:** Extrude up to a face (+ offset, extrude.upto); 🎯 hole distances from any edge of the
  face, from another step's hole (its centre) or another hole of the same step (from: {hole: j}). tools/e2e_model_custom.py.
- **Quick parts in assemblies done:** a quick part goes in as its STEP export, read back by a "solid" step
  (faces named <id>:f<k>; snap, mass, STEP export as for model parts). tools/e2e_assembly_quick.py.
- **Offset sketch planes done:** plane {datum, offset} (the sketch bar's Offset field; the AI's {datum, offset}).
- **Loft / sweep done:** loft (ThruSections through sketches in order), sweep (PipeShell, mitred corners, profiles
  with holes); open sketches are paths. tools/e2e_model_loft.py.
- **Tangent arcs done:** an arc started at a line's loose end is tangent to it (constraint tan; Shift = free).
- **Trim done:** ✂ Trim (crossings line / circle / arc; constraint on: a cut end stays on its cutter, or joins its
  end). tools/e2e_model_trim.py.
- **Offset done:** ⧈ Offset (circles, loops of lines / arcs with mitred corners and tangent joins, blocks via
  /api/model/sketch/offset with shapely). A typed radius holds every other point; a drag / hold only places the
  points, the final solve and its check run without it. tools/e2e_model_offset.py.
- **Decorating model faces done:** decal step (text traced in the browser via /api/trace, or a picture outline),
  raised / engraved on a flat face, follows it; the AI's decal. tools/e2e_model_decal.py.
- **Assembly links done:** snaps hold (doc.mates {move, face, onto, ontoFace}, re-applied after refresh and moves;
  moving the snapped part by hand unlinks; no cycles; saved, undoable). tools/e2e_assembly_links.py.
- **Autosave done:** auto3d/autosave.py (data/projects/<id>.json + .meta.json, written whole via a temp file, MAX 40),
  /api/projects routes; web/js/autosave.js (History.commit / go and the quick part's history fire `a3d:changed`; saved
  3 s later if the project file changed, a beacon on pagehide; 🕘 Recent projects; the last one offered). A3D_DATA
  points a server at another data folder (test servers). tests/test_autosave.py, tools/e2e_autosave.py.
- **Drawing sheets — step 1 (the server) done:** auto3d/modeler/sheet.py — per view the exact lines, circles and arcs
  of the B-rep edges with keys from the face names (a hole: `H1:hole:0`, its centre `H1:hole:0#c`; a line's ends
  `<faces>#0/#1`; the view box `box#x0…`), the automatic dimensions of a preset (light: overall sizes, Ø per size
  "8× Ø3 H7", the biggest R; medium: + the holes' places — a row / grid once with its pitch "3× 10" —, radii, heights;
  full: + every level and column), stable ids (the user's moves stay), the layout (A4 / A3, scale, views), the PDF
  from the editor's SVG. /api/sheet/build, /api/sheet/pdf. TestSheet.
- **Drawing sheets — step 2 (the editor) done:** part kind `sheet` (auto3d/project.py), web/js/sheet/sheet.js
  SheetEditor (one SVG for the screen and the PDF; views and dimensions dragged, Del, ＋ Dimension by two points / a
  circle, presets, paper, views on / off; the user's moves in `dims`, deleted autos in `hidden`, own ones in `user`),
  Project.newSheet (one per part), 📄 Drawing sheet in the model panel; partHash of the part's steps / material /
  tolerances: an `a3d:changed` listener gives closed sheets a new revision + date (built.stale), ensure() builds again.
  tools/e2e_sheet.py.
- **Drawing sheets — step 3 (the AI) done:** browser tools sheet_open (the part's sheet, made once), get_sheet (dims
  with their texts; `points: <view>` its point keys and circles), sheet_edit (preset, paper, views, remove, restore,
  move, add by two point keys or a circle; SheetEditor.addFor / pointsOf); export pdf on a sheet: export_data pdf ->
  the sheet's SVG -> sheet.pdf. automation-design uses sheets. tools/e2e_ai_sheet.py.
- **⟋ Draft done:** kernel.draft (BRepOffsetAPI_DraftAngle on the step's `of:side…` faces, the neutral plane its start
  face, the pull from its start to its end, names carried); a `draft` step {of, angle} (doc, LIMIT_FIELDS angle: the
  most that fits is told); the modeler's ⟋ Draft (renderDraft: the extrude, the angle; a click on a wall picks its
  extrude); add_feature draft for the AI. test_draft; tools/e2e_model_draft.py.
- **Fixes from the AI's reports done (RealSWReports 2026-10-28):** get_screenshot fits the whole part / assembly
  (view.fit: the camera's direction kept; fit: false keeps a zoomed view), on a drawing sheet it is the sheet (its SVG
  drawn on white); set_view section "off" / "none" takes the cut off; gui_state lists the 3D model's steps (kind step,
  name, what, [id]) and a choice's text with its value; the 3D Snap row hidden while a feature is made.
  tools/e2e_ai_reports.py.
- **Quick part: a click on a thin object picks it (full test pass, job 15):** viewer.pickSurface takes a corner only
  when a ray from the camera to it meets nothing more than ~1.5 px before it (was: the hit distance + 1 % of the part,
  so a corner 3 mm under a box won); clicking / dragging an object matches its heights within 0.1 % of the part (was
  0.6 %, so a band on a 3 mm box picked the box). tools/e2e_history.py.
- **"Continue where you left off" covers nothing (full test pass, job 15):** the restore bar is a strip under the top
  bar in the page's flow (was fixed bottom-left, over the Quick part's chat Send); Autosave.dropOffer takes it away on
  the first change with a part open. tools/e2e_autosave.py, e2e_chat_photos.py.
- **Steps named after their sketch done:** nextName(type, sketch): an extrude / revolve of a sketch the user named
  is "Extrude – Slot" (a "Sketch 2" keeps "Extrude 3"), in the panel and for the AI. tools/e2e_ai_reports.py.
- **The assembly's joints as buttons done:** the bar's 🔗 Joint ▾ menu is a row (.as-jbar): each joint type a
  button of its own (one click starts it, lit while its faces are picked, a click again / Esc stops), Screw / pin last;
  the hint goes under the bar however many rows it has; the suggestions table goes while faces are picked.
  e2e_assembly_joints / _concentric / _bolt / _edgepick / _fasteners / _health, e2e_assembly.
- **The assembly's UI check done (1600×1000 and 1280×800, EN / CZ):** the suggestions table stays under the command
  bar (showSuggest's place: a max height, its rows scroll), its head keeps a gap to "Suggested"; the 3D Snap / Hover
  row turns to icons when its names do not fit (.snap-filters.compact, measured, names in the tooltips); the panel's
  sliders and buttons shrink / wrap instead of running out of it; a joint row label reads as a label; a face inside a
  sub-assembly is named ("Arm I2: the top of Extrude 1"), the face names in Czech. e2e_assembly_dof finds its row by
  the instance order.
- **Ctrl+click to choose several in the 3D model done:** clickFace keeps `picks` ({face, step, point} / {point,
  snap}); Ctrl adds or takes one away (addPick) -> showPicks: their steps' faces lit, the points marked, the table:
  Between them (the distance; two parallel flat faces: the gap), the steps (turn them off / on, ✕ Delete them —
  removeSteps, one question for steps that need them), ✨ with all of them. tools/e2e_model_multipick.py.
- **• Reference points done:** a `point` step {at: {vertex: {faces, fp}} | {centre: <edge ref>} | {mid: <edge ref>} |
  {xyz}} — no geometry; doc._point finds it again each rebuild (find_vertex / find_edges + edge_centre / the edge's
  middle), status `point` [x, y, z] and `update` {at: its new fp}; gone: an issue, the last place kept (State.points,
  rebuild's `points`). The browser: pickSnap's • Reference point here (Modeler.pointRef: the faces at a corner, the
  edge a centre / middle belongs to), ModelView.setPoints (a dot + its name; the chosen one lit), measurePoint snaps to
  them (snap 'point'); Sketcher.refs lists them seen square onto the sketch (pointIds {point}), a dimension end
  {ref, point: id} follows it (doc._ref_uv); deleting what it stands on keeps it at {xyz}. AI: add_feature point
  (at {corner: [x, y, z]} / {centre} / {mid} / a ref), find_refs kind "point", get_model's xyz. test_reference_point;
  tools/e2e_model_point.py.
- **Distances from round faces' axes done:** a sketch dimension end {ref, axis: {face, fp}} and a hole's from
  {x: {axis: {face, fp}, d}} — doc._axis_of (kernel.find_faces + face_axis: cylinder / cone / torus / turned faces) /
  _axis_in (seen square onto the plane: a point, or a line — the end is the point of it nearest its ref); gone: a
  warning, the last place kept. The browser: axes.js roundAxes (the faces' axes on a plane, as far as each face
  reaches; roundings left out); Sketcher.refs().axes (dashed blue centre lines; picked on the line or over the face as
  a 'line' target) and the circles' centres named by an axis square to the plane; the hole panel's 🎯 holeAxisAt (a
  round face or its rim; the axis square to the face or straight across) and refCoord; refsTo / detach know them. AI:
  find_refs kind "axis", a sketch shape's from: {axis}, hole from {x: {axis: <name>, d}}. test_distances_from_a_round_face_axis;
  tools/e2e_model_axis_refs.py.
- **View cube done:** viewcube.js (ModelView {cube: true} in the 3D model and the assembly): CSS 3D faces turned by
  the camera's rotation each frame (the faces turned away hidden), each face 3 × 3 cells whose data-dir is where they
  look from — the middle the face, the sides its edges, the corners its corners (the same dir on neighbouring faces
  lights together on hover); a click -> setView(side | [x, y, z]) (setView: + back / left / bottom, a direction for an
  edge or a corner; same fitted distance; Z up, the top +Y up, the bottom -Y up); ⌂ the iso view. It sits under the
  command bar (a ResizeObserver on the bar), the busy box beside it, the hint narrower. The Iso / Top / Front / Right
  buttons left both bars (`action('view-…')` still works). At 1280×800 the assembly's bar 189 -> 159 px; the 3D
  model's stays 129 px (its 4 rows are all tools there; the views sat in the last row). Labels TOP … LEFT, Czech
  SHORA … ZLEVA. tools/e2e_view_cube.py.
- **Compact command bars done:** compactbar.js fitBar(bar) (one call in renderCmdBar and the assembly's renderBar):
  after each render (a MutationObserver on the bar — the translation too) and on the view's resize (a ResizeObserver)
  it counts the rows of the bar's controls; over 3 rows with names, the tools (data-a / data-joint / data-origin
  buttons, the 🔗 Joint label) show only their icon (CSS: font-size 0 + ::before attr(data-icon); "⚠ 3 collision(s)"
  -> "⚠ 3", a menu keeps ▾), the name leads the tooltip (t(): in the current language); labels without an icon (Top,
  Front) and ✓ Finish / ✕ Cancel keep their text; wider again: names and tooltips back. At 1280×800 the 3D model's bar
  129 -> 59 px, the sketch's 126 -> 64 px, the assembly's 159 -> 66 px (2 rows, English and Czech); at 1600×1000 the
  bars keep their 3 rows of names (95 / 94 / 98 px, as before — so the limit is 3 rows, not 2). tools/e2e_compact_bars.py.
  Compact, the sketch's ↕ Plane at chip shows only ↕, its field and mm (its "(+ = +Z)" goes; the tooltip and the arrow
  on pointing say which way): with ⊂⊃ Slot the Czech sketch bar had grown to 3 rows (95 px) at 1280×800, now 2 (64 px).
- **Sketches and holes from a corner or the part's origin — step 1 (kernel, AI) done:** plane.origin on a face plane
  (sketch, hole, decal): "corner" (doc._origin: kernel.face_span — the exact box of the faces of that name in the
  frame's u / v — its (u0, v0), found again each rebuild, so it follows the corner), "world" (the world origin seen
  square onto the plane, fixed), {point: <id>} (a • point step); the frame's o moved there in the plane and the answer
  tagged `origin`. web/js/modeler/origin.js (originAt, shiftSketch, worldToUV). AI: add_feature sketch plane {face,
  origin} / hole {face, origin, points} — "world" places in world X / Y / Z (a face whose v runs against its world
  axis — the bottom, the back — turned over: v, dy and arcs), get_model gives origin and the world places back.
  test_face_origin; tools/e2e_sketch_origin.py.
- **… step 2 (the UI) done:** the sketch bar's Origin .seg (originSeg; a sketch on a face): setSketchOrigin ->
  moveOrigin (the face's centre from the body, ⌜ from view.faceSpan, ⊕ the world origin, all seen square onto the
  plane), shiftSketch (points, {ref} ends, a block's `at`, fix's `at`; dx / dy / dist to the origin measured anew), one
  undo step (Sketcher.snapshot keeps a face plane). frame() / holeFrame() take a rebuild's frame only while its
  `origin` tag matches the plane's (sameOrigin), else the plane's own. The hole panel's From: ⇤ Edges (each hole's
  `from` its nearest edges) | ⌜ Corner | ⊕ Origin (plane.origin, `from` dropped, the rows "from the corner" / "from the
  part's origin"); a click on the face is measured from it. tools/e2e_sketch_origin.py.
- **No right-click menu in the 3D model done:** clickFace shows the face's tools in the suggestions table in its
  sections (On this face / Its edges / The part / Step · name, showSuggest {section}); the .m-fmenu pop-up and its
  styles are gone, a right click only pans. e2e_model_pick.
- **The assembly's suggestions in sections done:** showSuggest items {section} are headings (.vs-sec); a picked
  face's table: the part first (◆ Select the whole part — the face pick dropped, its moves in the panel —, then
  Assembly.partItems: open, join, simplified, edit here, fix, its own part, take out), then This face (its joints,
  measure); a snap pick's table: the point's section, then the part's. ◔ Quadrants off by default (near a rim they took
  the click meant for it). e2e_assembly_facepick, e2e_suggest.
- **↺ Restore in the size editor done:** openDimEdit's ↺ <the value it opened with> puts it back in the number and
  the slider and previews it (the editor stays open; greyed while unchanged). e2e_model_pick.
- **Flexible sub-assemblies done (step 1: their own motions):** a placed sub-assembly's `inner` {its instance id:
  matrix in its frame} — its parts moved in this placement only (its own document stays); innerList (the overrides
  over its document), bodyOf / bodyKey (such a placement has its own merged body, `<part>@<inner>`), innerAsm (an
  engine Object.create(this) on its parts and joints — holdPart / applyMates / motionsOf / moveFree as they are —
  whose draw / commit go to keepInner: the moved places kept, the body merged again, the parent's joints applied),
  settleInner on refresh (its joints changed in its tab), innerMotions -> the panel's "Moves inside <sub>" (sliders
  only: motionHtml `only`; limits read from its document) and ↺ As in <sub>; flatParts / STEP / the sheet's flatten
  / the tree's preview use the moved places. AI: get_assembly `inner` (part "I3/I2", free, at), move_free "I3/I2"
  (set_travel / lock_motion / check_travel refuse it: its own assembly's). tools/e2e_assembly_flexsub.py.
- **Flexible sub-assemblies, step 2 (the parent's joints) done:** flexOf (the parts that move inside a sub-assembly
  by its own joints, cached until refresh); insideMate: a parent joint whose face is on such a part ("I2/…") holds
  that part inside it, when the sub-assembly is held otherwise too (another joint, or 📌) — alone it places the whole
  as before. holdPart / motionsOf of the sub-assembly leave such joints out; applyMates places it, then settleInner;
  innerAsm(it, outer) adds them to its engine with the parts they join as fixed stand-ins ("^I1", joint "^J3", in
  its frame) — so its Moves inside lose what they hold. e2e_assembly_flexsub (a parallel joint locks the lever's turn).
- **Flexible sub-assemblies, step 3 (fully functional mechanisms) done (2026-10-29)** (the owner: "with assemblies
  inside each other I cannot move the mechanisms — a sub-assembly should be fully functional"). Assembly.flatAsm: one
  engine (Object.create, as innerAsm) whose instances are this assembly's plus each ⚙ moving sub-assembly's joined,
  not-📌 parts as "I3/I2" (placed in the world; travel / moveNames keys and its joints' ids prefixed "I3/J1"), its
  joints onto its parts that stay go onto the placement "I3" with the face "I1/…" (the merged body), this assembly's
  joints and couplings with a face "I2/…" on a moving part go onto "I3/I2" — so placeAll / closeLoops /
  followCouplings / motionsOf work through both levels (a loop through both is found and solved together; the parts
  here on an inner part go along). doc.mechs: this one's + the sub-assembly's own (`_sub`, taken over by recOf when
  renamed / redriven here). Kept while flatSig (matrices, inner, rigid, joints) is the same; keepFlat writes the
  places back (this assembly's matrices, the placement's `inner`, its body merged again), draw / commit as usual.
  mechanism.js mechanisms(): this one's + the flat engine's with an "I3/…" part (`flat`; all inside one: `inside`,
  "<name> (in <sub>)"), engOf routes posOf / driveTo / traceOf / ⚠ check / 🎬 to it; drag.js: innerPartAt (the hit
  face's "I2/…" on the chosen sub-assembly) -> that part in the flat engine. innerAsm now has the sub-assembly's
  couplings (followCouplings no longer skipped in an engine with an owner). `rigid: true` on a placement (🧱): no
  inner motions, insideMate / innerMotions / flatAsm leave it out; its panel's ⚙ Moving sub-assembly checkbox, the
  suggestions' ⚙ Moving sub-assembly / 🧱 Make it rigid. AI: get_assembly / gui_state `mechanisms` `inside`,
  drive_mechanism {mechanism: "I3" | "I3/I2", driver "I3/I2 motion 0"}, move_free "I3/I2" (the flat engine),
  place_part {rigid}. tools/e2e_subassembly_mechanism.py (crank demo as a sub-assembly: formula at 90°, a flag
  follows, drag, ▶, ⚠, a loop through both levels, rigid; the gearbox demo: 2:1, π·Ø). Left out: deeper nesting (a
  sub-assembly's sub-assembly's parts stay with it), naming an inner motion from the parent's ⚙ Mechanism.
- **Hover marks, quadrants, hover filters done:** view.js snapPoints(edges, matrix, kinds) (snapNear uses it; a round
  edge's ◔ quadrants: along the world axis lying best in its plane, and across), ModelView.edgeAt (pickEdge over
  placed edge lists, hidden ones not taken), setHoverEdges / setHoverSnaps (the snap dots the camera sees: one ray
  each) / clearHoverMarks; Modeler.hoverMarks (the edge under the mouse, the hovered step's points) and
  Assembly.hoverMarks (only the hovered part's edges, the face's points); suggest.js hoverKinds (a3d.hover3d) — the
  filter row's Hover: ⟋ Edges, • Snap points. tools/e2e_hover_marks.py.
- **⇳ Midway sketch plane done:** a face plane's `mid` (the parallel face across): doc.plane_frame puts its origin
  halfway between both faces as they are now (_plane_offset; a face gone: the place it had); the "Sketch on…" bar's
  ⇳ Midway (toggleMidPick / clickMid: the first face lit, the second parallel and across -> enterSketch); the AI's
  plane {face, mid} (planeOf refuses one not parallel). test_mid_plane; tools/e2e_sketch_midplane.py.
- **𝐓 Text in sketches done:** the sketch bar's 𝐓 Text (Modeler.insertText / textBlock: textOutline traced by
  /api/trace, scaled to the letters' own box h high, its corner at 0) -> a block entity with `text` (the kernel's
  block loops, holes kept); its panel: Text (retext: traced again, the height and corner kept) and Height (setBlock
  h), the text field focused to type over. tools/e2e_sketch_text.py.
- **Sketch Snap filters done:** the sketch's filter row has two groups — Snap: • Points, ⊹ Midpoints, ◎ Centres,
  ⊕ Origin, ⟋ On shapes, ⌜ Part edges, ┆ Guides, ▦ Grid (Sketcher.snapKinds, localStorage a3d.sksnap; Sketcher.snap
  and point drags follow them; Grid off: the point lands where the mouse is) and Select (pickable, a3d.skpick: what
  ⬚ Select / ↔ Dimension / ⟂ Relations take — kept apart, as snapping used to follow it). suggest.js fitFilterRow:
  names on one line; the group the tool does not use as icons; a group a line; icons — up to the Finish / Cancel dock,
  its height (--skf-h) lifting the suggestions / size box. tools/e2e_sketch_snaps.py.
- **Snap filters for the part under a sketch done (2026-10-29):** the owner missed the sketch's filter row on a part —
  it never showed there: Sketcher.renderFilters took the 3D view's row (.sk-filters.snap-filters, there whenever the
  part has a body) as its own and modeler.render then removed it with showSnapFilters(false); on an empty model it
  showed. Now it takes only `.sk-filters:not(.snap-filters)`. The one ⌜ Part edges toggle is a group of its own, "On
  the part:" (only with a body): ⌜ Corners, ⊹ Edge midpoints, ◎ Centres, ◔ Quadrants — the 3D view's Snap choice
  (suggest.js snapKinds / setSnapKind, a3d.snap3d: off in 3D = off on the sketch, quadrants off by default) — and ⟋
  Edges (on an edge, sketch-only: a3d.sksnap.edges; the old `part` key dropped). Sketcher.partSnaps lists the part's
  points per those (refs() has arcs too: the in-plane arcs' centres); snap() catches them with refKind, the label
  names it (roh dílu, střed hrany dílu, střed na dílu, kvadrant na dílu); the sketch's ◎ Centres is its own circles'
  only. While a drawing tool is on, the allowed part points within ~220 px of the mouse are marked (dim green dots).
  Every snap tooltip says Alt = no snapping. tools/e2e_sketch_snap_filters.py.
- **The offset arrow only on demand done:** the arrow (and its ⊙ / ⊗ / "+ +Z" tag) is drawn only while the mouse is
  over the ↕ Plane at chip or its field has focus (Modeler.showPlaneArrow; planeArrowLabel kept by renderCmdBar) —
  a sketch starts without it, so it is not in the way of drawing. tools/e2e_sketch_slot.py.
- **The offset arrow seen end-on done:** ModelView.updatePlaneArrow (each frame drawn): looking along the plane's
  normal (the Top view down +Z) the arrow's cone tip was a purple blob — then it is the CAD symbol ⊙ (toward you) /
  ⊗ (away) with its label beside the origin, from the side the arrow and "+ +Z" at its tip.
- **The sketch plane's offset direction shown done:** the ↕ Plane at chip says which way + goes (+ = +Z, on Front −Y)
  and ModelView.setPlaneArrow draws an arrow along the plane's normal labelled the same (gone off the sketch) — the
  GUI audit's offset-plane direction. tools/e2e_sketch_slot.py.
- **The sheet check leaves decoration out done:** check() skips circles and edges of a decal step's faces (engraved /
  raised text and pictures are not sized); get_sheet's missing items end with their point key / circle [...] for
  sheet_edit add. tools/e2e_ai_reports.py.
- **The AI's measure in 3D models done:** measure {a: {face}, b: {face}} on the model on screen (measureModel: centres
  apart, the angle, the gap between parallel flat faces — a wall's thickness —, round faces' axes apart and Ø), as in
  assemblies. tools/e2e_ai_reports.py.
- **🖨 Print check done:** ModelView.printCheck({minWall, overhang}) on the mesh as it lies (its lowest z the bed):
  triangles facing down past the overhang angle (not on the bed) red; a ray in from each face (both sides hit, a
  4000-face sample on big meshes) meeting the other side within minWall orange; areas, boxes, the thinnest wall. The
  toolbar's 🖨 Print check (a box under the toolbar, its min wall remembered, re-run after each rebuild); the AI's
  check_print {min_wall, overhang}. tools/e2e_model_printcheck.py.
- **Section A–A on part sheets done:** sheet.section_view (the part ∩ the box x ≤ its middle, projected as the Right
  view sees it; the cut faces' wires -> hatch outlines; the cut's two ends on the Front view) -> geometry.views.Section
  when build(…, section) (doc.sheet / worker / /api/sheet/build section); the sheet: d.section (☐ Section A–A, in the
  undo history, the Right view hidden and its place taken), drawn() (the views drawn and picked, Section included),
  hatchSvg (45° lines clipped even-odd — plain lines, so the PDF has them), the A–A cut line with arrows on the Front.
  test_section_view; tools/e2e_sheet_section.py.
- **Exploded iso on assembly sheets done:** doc._exploded (each top-level part, a sub-assembly's parts together, moved
  from the middle of all by 1.2 × k × its distance); assembly_sheet(…, explode) -> sheet.build_assembly(…, iso_placed):
  the iso drawn from the pulled-apart parts and their Iso marks (the balloons) there, the other views assembled; the
  sheet's ☐ Iso view exploded (d.exploded, k 2, in the undo history; the drawing set's pages follow their own sheet).
  test_assembly_sheet_exploded; tools/e2e_assembly_sheet_explode.py.
- **⊂⊃ Slot sketch tool done:** Sketcher.slotPoint (centre, centre, width from the mouse's distance to the middle
  line: slotHalf), addSlot (two lines and two arcs in a group, tan ×4, eq on the ends, h / v when drawn level /
  upright), a live preview "40 × 10"; the toolbar's ⊂⊃ Slot (make group). tools/e2e_sketch_slot.py.
- **⁂ Pattern in sketches done:** the sketch bar's ⁂ Pattern (copy group) repeats the picked shapes (⬚ Select, Ctrl,
  a box; a rectangle / joined outline goes whole — Sketcher.wholeShape, shared with ⇋ Mirror): at once 3 in a row
  along X (spacing: the shapes' length × 1.5; a picked construction line: along it) or 6 around a picked point;
  makePattern / unmakePattern (pure, sketcher.js) put the copies and a `pat` relation {kind row | around, n, d, e |
  c, src, pairs, circles, copies}. Full constraints (constraints._pattern): a row along X holds each first copy
  d further by `difference`, along a line by parallel + distance (the other points: a parallelogram through a helper
  midpoint), the next copies by symmetric_point (each one halfway); around: equal distance from the centre and
  set_l2l_angle i·360°/n; circles equal_radius — the copies keep the original's size and follow it, dof unchanged.
  The quick box (bottom left, editPattern: In a row / Around, Count, Spacing) re-makes them live as you type
  (repattern: unmake + make in one relock), a click on a line = along it, on a point / circle = around it; Enter =
  done; the whole edit is one undo step; the ⁂ symbol reopens it. The AI: any sketch shape + pattern {count, spacing}
  or {count, around: [u, v]} (agent_model sketchFromShapes -> makePattern). test_modeler_sketch TestSketchPattern;
  tools/e2e_sketch_pattern.py; e2e_agent (a flange: 6 around, 3 in a row).
- **⧈ Linked offset done:** ⧈ Offset's copy of a circle or a loop of lines / arcs is held by an `off` relation
  {d, pairs: [[original, copy, w]], src, copies} (w: the side of a positive d — a line's copy left of a -> b, an arc's
  bigger; the copy's ends named as its original's). constraints._offset: a copy line parallel + set_p2l_distance |d|
  (an end on a copy arc: parallel only; both: nothing — the arcs hold it), a copy arc concentric (it shares the
  centre), its radius the original's + w·d (difference of two radius parameters, signed) and its ends on the rays
  through the original's ends (not a touching line / circle crossing); a circle the same radius rule — no new free
  sizes. A distance has no side, so after the solve _offset_wrong checks each copy's side and _offset_place puts a
  copy that jumped across (a width typed 20 bigger than d) back beside its solved original, then solves again. The
  sketcher: makeOffset makes the relation (blocks stay one-off, said in the box and the hint), a ⧈ size label
  (offLabel: a short dimension a fifth along the first line / across the rims) types the distance (setOffset: the
  original's points held; negative = the other side), ⛓ Unlink the offset in a picked copy's suggestions and the
  Relations panel's ✕ (unlinkOffset: the copy stays, its lines get their original's h / v), deleting all its shapes
  drops it; an offset circle's Ø label starts at 135° (not on its original's). TestSketchOffset;
  tools/e2e_sketch_offset_linked.py.
- **Unique ids in sketches done:** Sketcher.newId also skips the ids it gave out before — several asked for before
  any is added (a point on the origin's dx / dy locks, a slot's two sides and ends, a rounded corner's relations)
  got one id (d1, d1), so ✕ / 🔒 on one acted on both; upgradeSketch gives the later of two equal ids a free one
  (old files open repaired). tools/e2e_sketch_ids.py.
- **Angle dimensions on sheets done:** kind "ang" {a, b: edge keys, r}: SheetEditor.angleOf (where the two lines cross,
  each toward its far end, the angle between), drawn as an arc with arrows and extension lines to edges short of it,
  the text clear of the arc; dragged: its radius; ＋ Dimension on two non-parallel edges makes one; sheet_edit add
  {view, edges} for the AI (parallel refused). tools/e2e_sheet_angle.py.
- **Shaft fits on sheets done:** web/js/sheet/fits.js (the ISO 286 table of fits.py: H6 … H9, f7 … p6); a selected Ø
  dimension's Fit choice (fitField / setFit: the post of a user's dimension, or an override in d.dims for an
  automatic one), its deviations in the panel; sheet_edit fits {id: class | null} for the AI. tools/e2e_sheet_fits.py.
- **Threaded holes done:** a hole's thread "M5" (doc.THREADS: ISO metric coarse M2 … M20 -> the tap drill): drilled
  at the tap drill whatever d says; doc.sheet passes {tap Ø: "M5"} to sheet.auto_dims, the hole's dimension carries
  thread and is drawn "2× M5"; the Hole panel's Thread choice (the diameter greyed), the step's text, add_feature /
  edit_feature thread. test_threaded_hole; tools/e2e_model_hole_head.py.
- **⊿ Rib done:** a `rib` step {sketch, t}: kernel.open_chain (the sketch's lines end to end) and kernel.rib — the
  line pushed far to each side as a polygon, a prism ±t/2 about the sketch plane, minus the part; the piece by the
  line that closes against the part (not out to the far side) is added (faces R:start / R:end / R:side:<line>); a
  line in the air is refused. The modeler's ⊿ Rib (renderRib: the sketch, the thickness; the newest unused sketch
  with a line), add_feature rib for the AI. test_rib; tools/e2e_model_rib.py.
- **⌴ / ⌵ hole heads done:** a hole's head "cbore" (head_d, head_depth: a second, wider prism; faces H:cbore:k,
  H:cbore_floor:k) or "csk" (head_d, head_angle 90: kernel.countersink, a cone; face H:csk:k); the Hole panel's Head
  choice sizes it from the hole (1.8 × d × d / 2 × d), the step's text shows it; add_feature / edit_feature head (null
  takes it off). test_hole_heads; tools/e2e_model_hole_head.py.
- **▲ Teardrop holes done:** a hole's `teardrop: true` (a sideways hole, its axis square to Z): kernel.teardrop_face —
  the circle with its top (+Z) a 45° point (a 270° arc and two tangent sides), prism faces H:hole:k (the round part)
  and H:tear:k (the sides); a counterbore gets the point too (H:cbore_tear:k), a countersink is refused, a hole going
  up / down is refused (an issue); a thread keeps its round tap drill. The sheet: a 270° arc of a hole face counts as
  full (Ø d, its place), the point's edges are decoration (sheet._deco, sheet.js check). The print check takes a face
  at just 45° as printable (1e-4). The Hole panel's Teardrop (print sideways) checkbox (greyed with a tooltip when the
  hole goes up / down), the step's text "▲ teardrop"; add_feature / edit_feature teardrop. test_teardrop_hole;
  tools/e2e_model_teardrop.py.
- **Tools coloured by group done:** web/js/toolgroups.js (toolGroup(action) -> g-make / g-modify / g-copy / g-detail /
  g-define / g-inspect), used by the sketch's, the 3D model's and the assembly's bars; each group's buttons side by
  side (make blue, modify amber, copy purple, details teal, define / join green, look and check grey).
  tools/e2e_tool_groups.py.
- **get_sheet lists an assembly's balloons done:** parts_list [{pos, name, part, qty, instances, balloon {at_mm,
  points_to} or null}] (sheet.balloonAt, kept while other pages are drawn); one balloon per item on its first placed
  part. tools/e2e_assembly_sheet.py.
- **Flush faces merged done:** kernel.combine ends with _unify (ShapeUpgrade_UnifySameDomain, names carried through
  its history): a wall flush with the plate it stands on gives one face per plane, with both names — no seam, no name
  on two faces (the AI's coplanar-faces report). test_flush_faces_merge.
- **find_refs by step done:** of_step (the faces a step made / all their edges — to round them at once), between_steps
  [a, b] (the edges where a face of only one meets a face of only the other: a rib's joint with its plate); faces
  merged from two steps listed with names. tools/e2e_ai_reports.py.
- **An extrude says where it went done:** its status has went {along "+z" / "-y" …, range [from, to]} (doc._went from
  the extrude's vector and its tools' box); add_feature / edit_feature also return volume_change_mm3 — the AI sees a
  wrong-way extrude at once (the wishlist's datum-direction item). test_extrude_says_where_it_went;
  tools/e2e_ai_reports.py.
- **Extrude up to next done:** extrude.upto_next (the panel's third extent, "Up to next"): kernel.prism_up_to_next
  extrudes the profile far, an add keeps the pieces of it outside the part that touch the sketch (up to the first face
  across the whole profile — a face across only part of it is filled round), a cut the pieces inside it (a sketch off
  the part: the nearest); faces named through _carry (start / side:<entity>; end = the part's faces it stops at).
  Nothing in the way -> an issue (the panel shows it once built). The AI's upto_next: true.
  test_extrude_up_to_next; tools/e2e_model_extrude_more.py.
- **Extrude ＋ Other side done:** extrude.d2 — a second blind prism on the other side of the sketch plane (its far
  face named start), any extent; symmetric wins (ticking one unticks the other); went.other_side [from, to]. The AI's
  d2. test_extrude_other_side; tools/e2e_model_extrude_more.py.
- **✂ Split body done:** a `split` step {plane, keep} — plane as a sketch's ({datum, offset}, {face, frame}, ⇳ {face,
  mid}; a face plane may have an offset too), keep "both" | "above" (the side its normal points to) | "below".
  kernel.split: the part ∩ / − a half-space prism on the plane (BRepAlgoAPI_Common / Cut), names carried, the cut
  faces `<id>:cut:0` (above) / `:1` (below); both: the pieces' solids in one compound (later fuses keep them apart
  unless a step joins them; tessellate's `solid` index, mass and STEP see two bodies); a piece of no volume -> "The
  plane does not cross the part". Status `bodies`. The modeler's ✂ Split (renderSplit: Top / Front / Right through
  the part's middle, Offset, ⇳ Midway on a face plane, Keep ✂ Both / This side / Other side; the arrow says which is
  "this side"; ModelView.setShades: one shade per body while it is open), clickFace's "✂ Split here" under The part
  (splitPlane: a face through the part cuts along itself, an outer one halfway to the farthest parallel face), ⧉ Make
  each piece its own part (hooks.newParts: two model parts, the steps up to the split, each keeping one side). AI
  add_feature {type: "split", plane, keep}; get_model's body `solids`. test_split; tools/e2e_model_split.py.
- **Exact print split (R8) done:** 🖨 Prepare for 3D print opens the model's STEP (not an STL) as the quick part, so a
  STEP quick part (no 3D objects added, no bends, the kernel installed: printexact.source) is split exactly. The
  planner is unchanged (slices -> printing.plan: cut places, bed fit, joints.apply_joints); each piece also carries
  its `cell_region` (a polygon, or hidden dovetails' z layers) and `voids` (pockets, glue channels / ports, recesses);
  printexact.request turns them into rings (a pocket open to the slices' bottom / top: through the exact face) and
  the worker's `print_pieces` (modeler/printsplit.py) cuts the STEP's solid, turned / scaled like the slices
  (importers.orient), with them as B-rep prisms (kernel.prisms, kernel.boolean common / cut with lists, unified),
  meshes each finely (kernel.print_triangles, 0.01 mm) or writes STEP (turned over when it prints back-face up, at the
  origin). /api/print/plan: `exact` + per piece `exact` {faces, triangles, volume, tol}, its size / fit from the exact
  box; /api/export: the zips' pieces (and the whole part) from the exact solid; a kernel failure -> the slab pieces
  with a warning. Connectors stay slab prisms (exact already). Ø100 × 300 on a 200 bed: 2 pieces of 3 faces (the
  slab pieces: ~4 900 faces, 18 000 triangles, vertices up to 0.25 mm off the cylinder; exact: 888 triangles, vertices
  on it, chords within 0.0045 mm), volumes = π r² L to 1e-9. The print tab: a hint that the pieces are exact, each
  piece tagged *exact*. test_print_exact; tools/e2e_print_split_model.py.
- **check_print on quick parts again done:** the 3D model's check_print (🖨 Print check) had replaced the quick part's
  (printer fit / split) — after prepare_print it answered "not a 3D model"; app.js BOTH routes it by the workspace,
  agent_tools has one check_print schema (printer, split, min_wall, overhang). e2e_agent, e2e_model_printcheck.
- **Faces picked with no tool on, joints suggested done:** the assembly's idle click also picks a face / a round edge
  (facePicks: one, or Ctrl: one of each of two parts; lit by drawMarks); suggestFaces — one face: the joints it can
  start (then the other face), two: the joint types fitting both (JOINT_TYPES by face kind), made through clickJoint.
  tools/e2e_assembly_facepick.py.
- **Delete from the tree at once, ↶ Undo done:** the tree's ✕ calls Project.remove(id, false) (no question);
  lastDeleted kept 30 s — ↶ Undo in the tree's header (undoDelete) puts it back where it was. e2e_project_tree.
- **Snap points with no tool on done:** the 3D model's and the assembly's hover show setSnapMark; a click on one
  picks it (Modeler.pickSnap / Assembly.snapPick with its part): Measure from here (measuring.a set), Copy its
  coordinates, ✨. e2e_measure_snap.
- **✨ Ask the AI about the selection, 3D snap filters done:** showSuggest(…, refs) shows ✨ (setAskAI from app.js: the
  chat opens with "[Selected …]" in its message — the step / face ids, sketch shapes, assembly parts); suggest.js
  showSnapFilters / snapKinds (localStorage a3d.snap3d) — a row bottom left in the 3D model and the assembly, the
  table above it; snapNear takes the kinds. e2e_model_pick (✨), e2e_measure_snap (Corners off).
- **📌 Fixed parts done:** an instance's `fixed` (the first one put in a new assembly; 📌 in its panel / the list /
  the suggestions; toggleFixed refuses a part its own joints move): mayMove refuses it, addJoint from it swaps the
  direction (the other part moves), both fixed: refused; get_assembly says `fixed`. The assembly's suggestions also
  offer ✎ Edit it here / 🔓 Unlock and edit it here. tools/e2e_assembly_fixed.py.
- **The face's tools as suggestions, a movable table done:** clickFace (left click) shows the face's tools with
  showSuggest (data-from face; dropped when a tool starts or nothing is clicked); suggest.js — the header drags the
  table (window listeners in the capture phase), its place kept as a part of the view (localStorage a3d.suggestAt;
  a double-click on the header: back to its corner). e2e_model_pick.
- **Quieter planes, ◫ Planes on / off done:** the Top / Front / Right planes fainter (fill 0.035, edges 0.22, small
  labels); Modeler.datums / togglePlanes (localStorage a3d.planes) — hidden unless a sketch plane is being chosen.
  tools/e2e_planes.py.
- **Box selection in sketches done:** Sketcher.down on empty space with ⬚ Select -> a box drag (.sk-box; crossing when
  dragged right to left); boxPicks (each shape's points on the screen: touched / wholly inside); Ctrl adds to the
  picks; deleteSel removes several picks. e2e_sketch_pick.
- **Reorder steps by dragging done:** the step list's rows are draggable (text/a3d-step; drop-before / after);
  Modeler.moveStep — refused when a step would come before one it uses (dependents), committed and rebuilt, taken back
  (history.go(-1)) when a step no longer builds. tools/e2e_model_reorder.py.
- **Measure snap points done:** view.snapNear — an edge's ends (corner), its middle along it (midpoint), a round
  edge's centre (centre) within 10 px; measurePoint (model and assembly) uses it; while 📏 Measure is on the snap
  under the mouse is shown (setSnapMark: a green point and its name). tools/e2e_measure_snap.py.
- **Metals look metallic done:** materials.finishOf (metalness / roughness per material: metals high, glass smooth,
  rubber rough); view.js studio(renderer) — a PMREM of a gradient sky + soft boxes as scene.environment (one per
  renderer: a WebGL texture is its context's); setLook / the assembly's meshes use the finish (envMapIntensity 1 for
  metal, 0.35 else).
- **Materials with colours done:** web/js/modeler/materials.js — 37 materials in groups (3D printing, engineering
  plastics, metals, other) with density and a default colour (lookColor: the part's own colour, else its material's
  when one was chosen); auto3d/modeler/materials.py the same densities (drawing PDF mass, set_material's enum).
  tools/e2e_materials.py.
- **Round sizes placed freely, Ø inside / R outside done:** f.place['dia:' / 'rad:' + id] = [angle, distance] (an
  old single angle still read); roundDim draws Ø across the circle or R from the centre, out to the label; roundAt sets
  f.rd by where it is dropped (inside: Ø, outside: R); movable keeps array places. e2e_sketch_pick.
- **Redo in a sketch done:** Sketcher.snapshot / step (clears redo) / back (keeps it for redo) / forward — Ctrl+Y or
  Ctrl+Shift+Z (the other workspaces had it already). e2e_sketch_pick.
- **Drawing guides done:** Sketcher.snap after the shapes: in line with a key point's x / y (points, midpoints, the
  origin) or on a line's extension (beyond its ends), both: where they cross; `guides` [[from, to]] drawn dashed green
  while a drawing tool is on. The filters moved bottom left (the suggestions / size box above them, clear of the
  Finish / Cancel corner). e2e_sketch_pick (beside a corner: level with it; above it: two guides).
- **Snapping onto shapes done:** Sketcher.snap (by the filters): points / origin, line midpoints (a `mid` rule:
  constraints symmetric_point), the part's corners / centres, a place on a sketch line / circle / arc (an `on` rule) or
  on the part's straight / round edges, then the grid; the snap named at the mouse (midpoint, on the line …).
  test_point_held_at_a_lines_middle; e2e_sketch_pick (an off-grid line: from its middle to a place on it).
- **Guides when placing on a face done:** web/js/modeler/facesnap.js — snapOnFace (faceKeys: the face's edges'
  snapPoints by snapKinds, its centre from view.faceSpan, view.refPoints, extra keys: this step's holes) as
  Sketcher.snap: onto a key, onto the face's edges, else level with a key along the face's x / y or on a straight
  edge's extension, both: the crossing; snapDrawing (the guides dashed green, the spot ringed and named, .face-snap).
  Modeler.faceSpot / showSpot (pointermove for ◎ Hole and Aa Text; Shift / Alt free) — the hole's preview: a ring of
  Ø d and its nearestEdges distances (drawHoleDims(at)); clickHole / clickDecal place on the snap. Stored meaning: a
  coordinate taken from another hole of the step -> from {hole: j, d: 0}, from an earlier hole's rim -> {edge, round};
  else the nearest edges as before (the middle line = half the width from an edge, not "the middle" — no such ref).
  suggest.js snapKinds.guides (┆ Guides in the Snap row, shown while a hole / text is placed). e2e_model_hole_guides.
- **A hole kept in the middle done:** hole.from {x: {mid: [edge a, edge b], d}} — doc._hole_from_edges finds both
  straight edges again by name, the hole's x = the middle of their lines + d (a gone / no longer straight edge: a
  warning, it stays). clickHole stores it when the snap was the face's centre or a guide through edge midpoints
  (Modeler.midEdges: the nearest edges on either side, the spot halfway); refCoord / drawHoleDims (both halves) /
  holeDimRow ("↔ in the middle of the left and right edges", 🎯 replaces it) / refsTo / detach know it; the AI's
  add_feature hole from {mid} (agent_model holeFrom checks two refs). test_hole_midway_between_two_edges (40 → 60
  wide: exact, STEP round trip, an edge gone), e2e_model_hole_guides (edit_feature 60 wide: the hole follows).
- **Tree pictures, drag into an assembly, library icon, middle-click close done:** thumbs.js (bodyOf: a light rebuild
  kept by its steps; picture: one offscreen renderer, iso; svgPicture for sheets) via hooks.thumb (sub-assemblies
  placed); Project.showPreview / hidePreview (.tr-preview beside the row); tree rows draggable (text/a3d-insert) —
  Assembly's viewport drop inserts; library parts carry library.steps (stepsHash) — fromLibrary while unchanged:
  kindIcon('library'); a tab's auxclick (middle button) closes it. tools/e2e_tree_more.py.
- **Sketch picks, filters, midpoints, R / Ø, the face menu on a right click done:** Sketcher.pickable (points, mid,
  origin, lines, round, edges; localStorage a3d.skpick) gates pickTarget, shown as .sk-filters (bottom middle,
  renderFilters from renderCmdBar); a line's middle is a pick ({mid: line} end — constraints.end adds a point held by
  symmetric_point; endUV; relPick takes the line); the origin / midpoints are ⬚ picks (kind origin / mid, distance
  suggestions); dimHits (each dimension's line / leader / arc, from movable) — a press on one drags the dimension
  (down / move / up); f.rd per circle / arc (roundAs, shownFactor, flipRound: the label, its box, the quick box and the
  suggestions show R or Ø, the lock stays dia / rad). The face menu: contextmenu without a drag (rdown); a left click
  only chooses the step. test_distance_from_a_lines_middle; tools/e2e_sketch_pick.py; e2e_model_pick (right click).
- **Reference dimensions, quieter dimension lines done:** relock returns whether it held ({quiet}); addDim of a size
  the others fix (redundant at its own value) keeps it as `free: true` (a reference: only measures, "(90°)"; a
  shape's own size: a note); dimension / extension lines dashed (DIM_ON soft violet, DIM_FREE faint), drawn for free
  sizes too. e2e_sketch_smart (90° between two sides of the rectangle: a reference, no error).
- **🧹 Clean up empty projects done:** autosave.empty_default (every part empty — a model without steps, an assembly
  without parts, a drawing without shapes; a sheet counts as something — and the project's and parts' names the app's
  own: 3D model 1, Sestava 2, Project …) / cleanup(keep, dry_run); POST /api/projects-cleanup; 🕘 Recent projects ›
  🧹 asks with their names first. test_cleanup_empty_default_projects; tools/e2e_cleanup.py.
- **One tab per new window, tabs dragged between windows done:** Project.showOnly / shown (a window opened by ⧉
  shows only its part's tab; switchTo adds, ✕ removes it from this window only — the part stays open elsewhere); a
  tab's drag carries text/a3d-from {win, project}; a drop on another window's tab row / a tab adopts it there
  (Project.adopt: the same project, the part already synced) and Windows.tell({took}) makes the first window close it.
  e2e_windows.
- **Suggestions for the selection done:** suggest.js showSuggest(viewport, title, items, hint) — a table bottom left;
  Sketcher: ⬚ Select picks (pickItem: point / line / circle / arc; Ctrl+click adds / removes) -> suggestions() by what
  is picked (own sizes, h / v / fix, relations via addRelation, dimBetween for the dimension that fits two, chains for
  3+, setConstruction); the picks drawn as selected, cleared by setTool / Esc. Assembly.renderSuggest for sel / sel2
  (open its part, join, simplified, own part, take out; join them, measure, collisions). tools/e2e_suggest.py.
- **Construction lines done:** sketch entities with `construction: true` (the kernel's _loops skip them; the revolve
  side check counts only the outline's points); Sketcher.toggleConstruction / consMode / consFlag (┄ in the bar: with
  ⬚ Select the selection, else new shapes); drawn dashed amber; Revolve offers construction lines first and takes the
  first as its axis. test_revolve (round a construction line); tools/e2e_sketch_construction.py.
- **A view with all its sizes, the same size lit up done:** per_view "all" (sheet.auto_dims: as full, its own outer
  sizes, Ø / R again, its edges' places; the check does not count it as twice); SheetEditor.sameAs(id) — the chosen
  dimension's size in the other views (the same direction of the part between the same places, or a Ø / R alike),
  drawn teal (.sh-dim.same). test_a_view_with_all_its_sizes; tools/e2e_sheet_same.py.
- **Sketch dimensions as on a drawing done:** Sketcher.movable(label, key, at, what) — a label dragged sets
  `f.place[key]` (len: offset across the line, dx / dy / dist: the dimension line's offset, dia / rad: an angle round
  the circle, ang: the arc's radius; kept by undo); locked sizes drawn with extension lines, arrows (dimLine / arrow),
  leaders for Ø / R; a rectangle shows a size on its locked side; the mouse on a label lights up what it measures in a
  layer of its own (view.setSketchHighlight: the labels are not redrawn, clicks on them stay). e2e_sketch_smart.
- **Sketch colours by state done:** constraints.solve(detail=True) (asked on every solve without a drag): a point is
  free when fixing it lowers the dof (each tried: up to FREE_CHECK_MAX = 150 points), a circle's radius likewise ->
  `free: {points, radii}`; Sketcher.stateOf -> lines / arcs / circles / splines and points blue (free), green (done),
  red (bad). test_which_points_are_free; e2e_sketch_smart.
- **Smart sketch dimensions done:** dims `ang` {e, e2, r1, r2, sg, v°} (planegcs set_l2l_angle on the lines as rays
  from their crossing toward the clicked arms; a reversed ray is an extra line b→a) and `pl` {a, e, v} (set_p2l_distance);
  dimOptions picks them for two crossing lines / a point and a slanted line; drawn as an arc / a perpendicular; the quick
  size box sits in the view's bottom-left (over no shape). tests: test_angle_between_two_lines,
  test_point_from_a_slanted_line; e2e_sketch_smart (a triangle: 36.87° -> 45, the corner from the slanted side).
- **Sketch state and the instant size done:** Modeler.sketchState (on renderProps / the bar): ✓ Finish sketch `.done`
  (green) at dof 0, 🪄 hidden unless dof > 0; Sketcher.quickSize — the first ↔ Dimension click on a line / circle /
  arc opens its len / Ø / R beside it (view.uvToScreen), Enter locks it (addDim {edit: false} + setSize), a second
  click gives a distance as before. The sheet's Light / Medium / Full as one segmented chip as high as the others;
  part tabs and the project tree drawn icons per kind (parts.js kindIcon). tools/e2e_sketch_smart.py.
- **The face menu redone done:** clickFace's menu is `.m-fmenu` (it shared `.m-ctx` with the "editing in the
  assembly" bar, now `.m-editctx`, whose styles broke it): a header (step, face), sections On this face / Its edges /
  The part / Step (delete in red), an icon column, kept inside the view; only the left button alone opens it, a right
  click closes it. tools/e2e_model_pick.py.
- **Actions in the view's corner done:** actiondock.js — a `.mp-actions` row drawn by a panel or a toolbar (OK /
  Cancel, ✓ Finish sketch, ✕ Cancel of a plane pick, Done) is moved to `.view-actions` in the bottom-right of its
  viewport (MutationObserver; a hidden placeholder keeps its place, a panel drawn again replaces it); toasts go up
  while one shows. The sketch's plane offset is a styled chip (↕ Plane at). Rule for new tools: their actions go there.
- **☰ Project tree done:** Project.renderTree — #projTree over the left panel (in main.layout): assemblies with their
  parts grouped (×n, sub-assemblies nested, no loops), sheets under their source, then the rest; the live part's
  data from its workspace (dataOf); re-drawn on a3d:changed while open; open / closed remembered (localStorage
  a3d.tree). tools/e2e_project_tree.py.
- **Part tabs in their own row done:** #partTabs is a strip under the top bar (body a flex column, .layout flex 1),
  wrapping into rows; a tab ≥ 5 letters + its buttons, up to 200 px (on screen / renaming: 420 px); tabs draggable
  (Project.move; dropped outside the window: hooks.openWindow); ✕ on the last tab too — Project.setNone: the part
  stays live underneath, body.none-open shows "No part open", switchTo / show bring it back. tools/e2e_tabs.py.
- **The assembly's list as a tree done:** renderList — a placed sub-assembly's row gets ▸ / ▾ (twist; folded: "· n
  part(s)", all levels), innerRows from bom.js instanceTree (the same walk as the BOM): its parts indented with a
  guide line (--depth), nested sub-assemblies fold open too; open paths in localStorage a3d.asmTree {assembly id:
  [paths]}. chooseInner(top, path): the placement chosen + selInner {top, path} — innerLit gives draw() the faces'
  prefix ("I2/"), setBodies paints those faces blue (no whole-part glow); renderInner: the part's name, "I2 inside
  Lever (I4)", its Moves inside (innerMotions of that part only) or "holds it in place", Open its part / Open <sub> /
  Choose the whole <sub>; choose() clears it; Ctrl+click: the placement as the second part. tools/e2e_assembly_tree.py.
- **📋 Bill of materials rolled up through the hierarchy done:** web/js/assembly/bom.js — one engine (the assembly's
  panel, the sheets, the AI): instanceTree (the placed parts instance by instance, sub-assemblies opened, loops not),
  itemNumbers (moved here from SheetEditor: the drawing set's positions), makeBuy (the one place make / buy is decided
  in the browser, materials.js printed() as the server's made_how: library / standard -> bought; printing plastics ->
  made (3D print), else made; bomFlat rows carry it as `made` for the server's bom_csv), bomOf(ctx, aid, {mode, numbering}) -> tree (per assembly a node per part: qty in its parent, total =
  qty × the parent's total), rows (one per part, the totals summed over every place, `in`: where from), lines,
  pieces / kinds / mass; bomTable / bomCsv. bomview.js: 📋 BOM window (Summary / Structured with ▾ folds, the assembly
  or any sub-assembly, ⬇ CSV, ⬇ Excel). auto3d/bomxlsx.py + GET / POST /api/bom/xlsx (openpyxl optional: 501 and CSV
  only). Assembly.bomCtx / massOf / numberingOf (hooks.setRoot = sheet.rootOf: positions as the balloons), bomFlat and
  ⬇ BOM (CSV) on the engine. Sheets: d.bomPage ('summary' | 'structured') on an assembly's sheet -> bomPages (paged,
  22 rows on A4) + bomSvg (the parts list's style, the set's template / frame) after its page in drawingSet, 📚 All
  pages and the sheet's own PDF; 📋 Add BOM page in its panel. AI: get_bom {assembly, mode}, get_assembly parts_list
  `total`. tests/test_bom_xlsx.py; tools/e2e_bom.py.
- **The BOM in Czech done:** material names go through t() like the material select (ocel, hliník …): bomTable's
  material cell (CSV / Excel), the 📋 BOM window, the BOM page, the assembly pages' parts lists, the title block and
  the assembly panel's parts list; the Save dialog's file types (app.js SAVE_TYPES) through t(); Czech for the AI's
  "reading the bill of materials". e2e_bom in Czech: the window's materials, the CSV, the toasts, every page's texts.
- **One item numbering per drawing set done:** SheetEditor.itemNumbers(root) — the top assembly's parts 1…n, then each
  sub-assembly's new ones in page order; assemblyPage numbers its rows (and balloons) by the set's root (rootOf), so a
  part has one number on every page (the cache key carries the numbering). e2e_drawing_set checks Machine 1–3, Lid unit 4, 5.
- **⧉ Windows done:** windows.js — every window holds the whole project; on a3d:changed each part whose (name, kind,
  data) changed is posted on a BroadcastChannel per project (autosave id); a window takes it in (its part on screen
  shown again with its undo kept, an assembly refreshed / a sheet ensured for changed parts, a new part closed, a
  deleted one gone), and remembers what it took so nothing goes back. ⧉ on a tab / in ☰ Parts saves the project and
  opens `?project=…&part=…`, which loads it from the server. a3d:project-loading / Autosave onId reconnect when
  another project is opened. tools/e2e_windows.py.
- **The AI tests the GUI by the mouse and keys done:** gui_state lists a sheet's dims / views / title cells (kind dim /
  view / cell, where: view); gui_action at = [x, y] (0 … 1 of the view), at_mm (a sheet's paper), drag_to, double,
  key (Delete, Enter, Escape, ctrl+z — alone, on a control or after a click): pointer + mouse events at the point
  (agent_more.js gesture: a pointer capture gets the rest, as the sheet draws its SVG anew on a press), -> what was
  under the mouse and what is selected. tools/e2e_ai_gui.py.
- **🔒 Lock a motion done:** 🔒 in each free motion's row (assembly.lockMotion): its own joint's angle (a turn about
  an axis / on a face) or dist + side (along an axis) where it is now, else a new flush / gap / touch joint of
  parallel flat faces across the move or a parallel joint of flat faces along the turn's axis (nearest / biggest
  first, onto the parts it is joined to) — kept only when the free ways drop, else undone; via: the part it is fixed
  on. AI lock_motion. tools/e2e_assembly_lockmotion.py.
- **🪶 Simplified parts in assemblies done:** rebuild `lod` light / full / auto (light when over HEAVY_FACES):
  kernel.tessellate(light) — the mesh cleared and made coarse, no edges, faces without sketch frames / refs, rounded
  (the 42 MB board: 14.6 -> 8.4 MB to the browser); _tess keeps the light and full meshes apart; doc.light {pid:
  bool} per part in the assembly, 🪶 Simplified in a placed part's Look. Collisions / drawings use the full part.
  TestLightMesh, tools/e2e_assembly_light.py.
- **Drawings of big imported parts done:** project_edges of a shape over HEAVY_FACES: HLRBRep_PolyAlgo on its mesh
  (kept, not meshed again), the pieces chained, no hidden lines (a grey wash on a board) — the 42 MB board's sheet
  296 s -> 19 s, 17 -> 8 MB; dimensions still from the exact edges.
- **Faster drawing sheets for huge parts done:** sheet._cached keeps a part's views by its features' hash (doc._key)
  in the worker — another preset / paper / the section on only makes the dimensions again (the assembly sheet's by
  its placed parts + explode); the section projects only its Right view of the half, the exploded assembly only its
  own iso; a big model (over HEAVY_FACES) drawn as the paper shows it (sheet._scale: the layout's biggest scale):
  solids, edges and holes under SMALL 0.25 paper mm left out (geometry.simple {left_out, under} -> a note in the
  sheet's left panel), the mesh outline joined end to end in any order and kept to FINE 0.05 paper mm (kernel._chain /
  _simplify), the iso at its cell's scale; its Section cut solid by solid (only those across x = middle; the cut
  pieces meshed); an exact projection's straight splines (a hole's sides seen edge-on) sent as two points
  (kernel._straight). PolyAlgo holds the GIL — views in threads gain nothing, left out. The 44 MB board (126 062
  faces, 5237 solids): sheet 78 -> 25 s, 44 -> 4.6 MB; + Section > 45 min (10 GB, never finished) -> 10 s; a
  preset / paper change 78 -> 0.01 s; two boards' exploded assembly sheet 438 -> 60 s, 77 -> 7.3 MB, again 1 s; a
  plate with 171 holes: 2.1 -> 0.9 MB, its Section on 1.0 -> 0.15 s, its assembly 4.3 -> 1.8 MB. tests/test_sheet_speed.py.
- **Big parts load faster (binary mesh transfer) done:** /api/model/rebuild {bin: true} answers one binary message
  (auto3d/modeler/packed.py: "A3DM", the header's length, a JSON header {arrays: [{at, off, n, type}], result}, then
  the arrays as they are, each at a multiple of 4) — web/js/modeler/packed.js fetchRebuild views them as Float32Array
  / Uint32Array (nothing decoded; the b64 helpers pass typed arrays through); the modeler, the assembly's bodies, the
  thumbnails and the library's preview use it; without `bin` the JSON answer (base64) is as before (the AI tools,
  tests, e2e_library_build). The worker packs it (op rebuild_bin) and doc._packed keeps a body's encoded mesh
  (packed.Mesh: its JSON made once) by body, lod, colours and ref id — an unchanged body is not encoded again.
  kernel.tessellate gathers each face's triangles as arrays and makes the positions, face ids and (big models) the
  faces' areas / middles at once (np.bincount), the flat faces' frames in plain floats — the same bytes as before.
  Measured (tools/e2e_big_part_load.py, localhost, headless Edge), before -> after: the 44 MB board (126 062 faces,
  943 717 triangles) tessellated 24.9 -> 17.7 s; shown again (unchanged, e.g. a sketch added) 2.4–2.7 s -> 0.55 s
  (server 1.7 s -> 0.12 s: no pickled dicts, base64 or JSON per rebuild; the fetch 1.9 s -> 0.19 s; read 0.29 ->
  0.14 s); 87.7 -> 79.6 MB; the plate with 171 holes 2.21 -> 1.78 MB, 25 + 8 -> 8 + 1 ms. Left out: gzip (localhost:
  1.2 s to pack 92 MB, more than the transfer), quantised positions and edges as one buffer (edges are 2 MB of the
  board's 80; the faces' JSON is 40 MB but parses in 0.14 s), indexed geometry. tests/test_model_packed.py.
- **Quick collisions with big imported parts done:** kernel.placed gives a location (shape.Moved), no copy — a 42 MB
  board (24 290 faces, 1170 solids) cost 1.3 s a placed copy, now 0.09 s (10 copies apart 8.9 -> 0.9 s); interference
  goes solid by solid (only solids whose boxes meet); quick (the background check after a change): a pair meeting in
  more than QUICK_PAIRS solids is estimated from the boxes (`approx`, ≈ in the list; 36 s -> 0.4 s), ↻ Check again
  computes it. tests: test_quick_check_estimates_big_overlaps.
- **An assembly's own sheet done:** a sheet's source may be an assembly — SheetEditor.assemblyPage (its placed parts,
  parts list, balloons; shared with drawingSet), sourceHash (the placed parts and theirs, sub-assemblies too) for the
  revisions; no presets / size check on it; 📄 Drawing in the assembly toolbar and its panel; the drawing set takes
  the assembly's own sheet (moves, dimensions, texts). Balloons spread round the iso view (turned on until clear) and
  dragged (`balloons: {pos: [x, y]}`); Pages (pagesOf: the set from this assembly down; a click: hooks.openSheet) and,
  on a part's sheet, the assemblies it is in. tools/e2e_assembly_sheet.py.
- **Sheet check done:** SheetEditor.check — per world axis (x: front / top across; y: top up / right across; z:
  front / right up) a union-find of the places the linear dimensions link (a pitch "n×" links its row; a circle of a
  known Ø / R links its centre ± r); every circle centre, straight edge (not a rounding's) and far end must reach the
  part's lowest place; every circle a Ø, every arc an R; the same distance twice = dup, a distance already linked =
  over. ⚠ per view, ＋ / ＋ all (addMissing: from box#x0 / box#y0), ? marks (screen only), ✕ the twice ones; the AI:
  get_sheet check, sheet_edit complete / drop_twice. Seams of round faces are no edges any more. tools/e2e_sheet_check.py.
- **Drawing sheets — step 4 (an assembly's drawing set) done:** sheet.build_assembly (the placed parts as one
  compound: views, overall sizes, a mark per placed part for its balloon; /api/sheet/assembly), sheet.pdf of several
  SVGs (a page each); SheetEditor.drawingSet: depth-first — the assembly's page (front, top, iso where the right view
  was; the parts list over the title block; balloons), its sub-assemblies, then its made parts, each once, by their
  own sheet (built again when stale) or made medium; bought / standard parts only listed; title blocks: kind, in, pos,
  sheet n / N; 📄 Drawings (PDF) in the assembly panel, export pdf of an assembly for the AI. Also: no hit rectangles
  in the PDF (MuPDF filled `transparent` black) and a font on every text (it does not inherit one).
  tests: TestAssemblySheet; tools/e2e_drawing_set.py.
- **Fits and tolerances on the drawing done:** auto3d/modeler/fits.py (ISO 286: holes H6–H9, shafts f7–p6, to 120 mm;
  label "Ø8 H7 (+0.015 / 0)"); a hole step's `fit` (its Fit choice; add_feature / edit_feature fit), a part's
  `tolerance` f / m / c (the part panel's Tolerances; set_material tolerance) -> drawing.pdf: "Ø8 H7" at the hole, the
  fits with deviations and ISO 2768 in the title block; materials POM, aluminium, steel, stainless steel, brass.
  tests: test_drawing_fits_and_tolerances, TestFits; tools/e2e_model_fits.py.
- **The design brief with buttons, skills per design kind done:** browser tool ask_user (ChatPanel.ask: a card of
  options, the recommended first ★, the answers sent as one message once all open ones are answered; ✎ Other… types);
  the system prompt asks the brief before a new design and asks with options when unsure; skills start-a-design,
  fits-and-tolerances (ISO 286 table, ISO 2768, ISO 273 holes, tap drills, counterbores, printed fits),
  print-functional, print-graphics; automation-design: made to be manufactured; model-a-part: simple, editable steps.
  tools/e2e_ai_ask.py. Not yet: tolerances on the PDF drawings.
- **Reports of three kinds, a steady concentric flip, a free ↻ done:** report_problem `kind` (bug / tool request /
  ui; the file named request-… / ui-…; the system prompt asks for requests when it works around a missing tool or the
  UI is not intuitive); applyJoint axis keeps the way round the part is (a stored flip turned it over at every hold),
  flipJoint turns it over once; the ↻ slider of a free turn: turnAbout (the turn stays free, usable on a locked
  joint); guiControls lists the parts of the list. e2e_assembly_lever.
- **Reports with the version, the GUI for the AI, locked joints done:** auto3d/version.py (VERSION 0.9.0 + git
  commit / date / local changes) in every report and /api/version; agent_more guiControls / gui_state / gui_action
  (one numbering of the visible controls, the chat left out; a greyed one refused); a locked joint's row greyed,
  edit_joint refuses it, `locked` in get_assembly. tests: test_report_problem, test_version_route; e2e_assembly_lever.
- **Joints named, the turn lock shown, explode along the joints, driving through a fixed part done:** a joint's
  `name` (double-click, edit_joint / snap_faces name); 🔓 free / 🔒 locked by every ↻ slider (m.angle; parallel has
  none); motionsOf: a part fully held on one part that can move gets that part's motions (`via`; moveFree, motionPos,
  limits, ▶ and the travel check act on it); explodeAlong: a joined part's pull projected onto its free move
  directions (orthonormal, cached in exDirs until a change) plus its parent's offset. tools/e2e_assembly_lever.py.
- **Collisions always told done:** scheduleClashes after every commit / refresh (700 ms; 250 with the panel open),
  the ⚠ button's text and colour from the last check (clashLabel / updateClashButton); a row's click: showClash ->
  AsmView.focusBox (the camera onto the overlap's box), the parts not in it at opacity 0.12; ⤢ Show all.
  tools/e2e_assembly_clash.py.
- **Drawings and boards for the AI done:** server open_file -> read_drawing / read_gerber_set (a folder) -> the
  page's `load_drawing` (a 📐 drawing tab); DXF / DWG open as drawings like in the app (`as: "part"`: the outline as
  before). Browser tools drawing_delete, drawing_add, drawing_units; drawing_layers color / new / active; list_parts
  says "2D drawing". tools/e2e_ai_drawing.py.
- **Motion with limits done:** motionsOf's motions carry a key (`J2:along`, `J1:u`, `X`, …) and a ref joint;
  motionPos measures where the part is along one from that joint's face / axis (spinOf for turns); an instance's
  `travel: {key: {min, max}}` bounds its slider (absolute now), setTravel puts it inside; ▶ playTravel (3 s, then back);
  checkTravel: 24 steps, the matrices of the parts that move -> /api/assembly/sweep (doc.assembly_sweep: each solid
  built once, kernel.interference(only=the moving)) -> the parts it hits and from where to where. AI: set_travel,
  check_travel, move_free `to`, get_assembly `at`. TestAssemblyClashes.test_sweep, tools/e2e_assembly_travel.py.
- **Joints that say when they do not hold done:** joints.js jointMiss (per type: angle and distance off, a locked
  turn too); Assembly.checkJoints after every applyMates (this.health), whyNot names the joint that holds the part
  elsewhere (the one that, left out, lets it hold — holdPart(…, skip)); red rows / ⚠ tags / status count, a warning
  when a new joint fights one; get_assembly `not_held`. addJoint on the same two faces changes that joint (returns
  the mate). Fasteners tagged on their instances (`fastener: {id: K1, text, bolt}`): one row, ✕ / removeInst takes
  the whole fastener and its drilled holes (doc.bolts + syncDrills); get_assembly `fasteners`; 🔩 in Joint ▾ opens the
  Fasteners panel (and the click goes on). tools/e2e_assembly_health.py.
- **The whole app for the AI done:** web/js/agent_more.js (drawing tools, edit_joint / remove_joint, measure,
  set_view, rename_part / delete_part, export_data for the server's files), auto3d/export3mf.py (an object per
  colour, base materials), server bom_csv and export 3mf / bom / dxf (POST /api/export/3mf for the menu), the skill
  use-a-drawing. tests/test_export3mf.py, tools/e2e_ai_more.py.
- **Smooth curves and more AI tools done:** sketch entity `spline` {pts: [point ids]} (kernel.spline_curve:
  GeomAPI_Interpolate; sampled for the loops, one B-spline edge in _mixed_wire; Sketcher.splineOf / splinePts draw and
  pick it); the AI's sketch shape `profile` (corners, {smooth}, {arc}); tools set_look, paint_faces, move_free,
  save_to_library (browser) and report_problem (server: RealSWReports/<date>-<title>.md); the system prompt asks for
  reports and smooth profiles. tests: TestSmoothCurves, test_report_problem, tools/e2e_ai_shapes.py.
- **CQ2 cylinders, colours, real models done:** library smc-cdq2b (SMC CQ2 catalogue, with auto switch) and smc-d-m9;
  a step's `color` -> part.paint {feature, color} (paint.js colours every face that step made); data/library/models.json
  (library.set_model, POST /api/library/model) -> buildPart uses the attached STEP (a solid step) for that choice.
  tools/e2e_library_real.py.
- **AI library-first done:** tools library_search / library_add / check_collisions (agent_tools.py + app.js
  libraryTools), get_assembly with free / fully_held per joined part and maker / pn in parts_list, the system prompt's
  "use the parts library first" rule, skills mechanical-design and automation-design (assemble-parts updated).
  tools/e2e_library_ai.py.
- **Parts library done:** library/*.json (the app's: fasteners, mechanical, panel, automation) + data/library/*.json
  (the user's; auto3d/library.py: load / check / save / delete, GET / POST /api/library, DELETE /api/library/<id>);
  web/js/library/build.js (formulas, sizes × lengths -> sketch + extrude / revolve steps, part.library facts, shop
  search links), browser.js (📚 window with a 3D preview, Save to the library), the assembly's bomFlat / ⬇ BOM CSV.
  tests/test_library.py, tools/e2e_library_build.py, tools/e2e_library.py.
- **Collisions done:** kernel.interference (box test, then BRepAlgoAPI_Common volume per pair), doc.assembly_clashes,
  worker op, POST /api/assembly/clashes; the assembly's ⚠ panel (flatParts, checkClashes after each commit while
  open, red parts + overlap boxes via AsmView.setClashBoxes). tests: TestAssemblyClashes, tools/e2e_assembly_clash.py.
- **Assembly DOF done:** assembly/dof.js (freeMotions: the part nudged 6 ways, its joints applied — the kept nudges'
  rank = how many ways it moves; candidate motions from its joints' axes / faces and X / Y / Z picked to span them);
  Assembly.holdPart / applyMates (a part goes along with its first joint's part via instance.hang; a first touch
  centres once: mate.centred), motionsOf / moveFree (the Moves sliders), shownJoints / choose (sel + Ctrl sel2),
  drawJointTags (joint symbols via view.setTags). tools/e2e_assembly_dof.py.
- **🕘 AI history done:** auto3d/ai_history.py (data/history/<id>.json + .meta.json; the same state as the newest is
  not saved again; MAX_STATES 300), /api/history routes; web/js/aihistory.js saves the project file after a chat turn
  that ran tools in this page (agent.js bridgeStats), lists and loads back (keeping the current one first).
  tests/test_ai_history.py, tools/e2e_ai_history.py.
- **🏷 Sizes done:** Modeler.sizeMode (all | locked | none, localStorage `a3d.sizes`), sizeShown(locked, sketch)
  used by Sketcher.draw and Modeler.sketchTags / showStepDims; BIG_SKETCH = 200 shapes labels only locked sizes
  (bigAll per sketch to show them anyway). tools/e2e_sizes.py.
- **PCB boards done:** auto3d/pcb.py (own readers: Gerber RS-274X / X2 with apertures, macros, arcs, regions,
  polarity, step & repeat; Excellon with formats fitted onto the board; ODB++ matrix / features / profile / own
  symbols / .Z via unlzw; layer kinds by X2 attribute, extension or name), drawing2d.to_dxf (⬇ DXF), the editor
  draws batches (Path2D per layer and look) and picks through a grid. tests/test_pcb.py, tools/e2e_pcb.py.
- **Drawing filters done:** editor.js FIELDS / OPS (dynamic filter rows, all must hold), matches outlined, likeThis,
  setSize (Ø / R / length for the whole selection). tools/e2e_drawing_filter.py.
- **Keep dependents done:** modeler.dependents (hard: needs it; soft: stands on it) + detach (plane -> its frame now,
  edge refs -> fixed points, up-to -> distance); choose.js dialog; delete_feature keep_dependents. tools/e2e_delete_keep.py.
- **2D drawings done:** drawing.py (A4 PDF: front / top / right by kernel.project_edges = OCCT HLR, iso, overall
  dimensions, hole labels and positions, title block; PyMuPDF); /api/model/export/pdf, the AI's export pdf.
  tools/e2e_model_drawing.py.
- **Pick & edit in 3D done:** hover lights the step (view.setHover with its faces), a click pops up face tools
  (m-ctx) and shows the step's sizes as labels (view.setTags) with a number + slider editor (live preview; sketch sizes
  solved with their locks). tools/e2e_model_pick.py.
- **Assembly joints done:** joints.js (touch / gap / flush / axis / parallel, applied in order per part, later ones
  restricted to the fixed direction; an axis allows an end-to-end flip); faces picked and marked in 3D (setMarks), the
  joint list with gap / flip / ✕; turning sliders with 90° catches. tools/e2e_assembly_joints.py.
- **Fasteners done:** fasteners.js (holes on one axis across parts -> screw + insert / screw / pin by the hole Ø,
  standard lengths; standard parts as project model parts, held by axis + touch / flush joints); the AI's
  suggest_fasteners / add_fasteners. tools/e2e_assembly_fasteners.py.
- **Bolts through parts done:** fasteners.js partsAlong (a ray through the placed parts' meshes -> the pieces of
  each part along it) and planBolt (the touching stack, screw + nut / insert / pin, its length, the holes); assembly.js
  addBolt drills a hole step into each part (tagged `bolt: <assembly>:B…`, kept in doc.bolts so undo / redo puts the
  part steps back — syncDrills) and adds the standard parts with joints. New joints: perp, angle (value °), tangent
  (joints.js turnToAngle). tools/e2e_assembly_bolt.py.
- **Mirror done:** doc.py `mirror` step (of body / a step, a datum or face plane, copy or move; kernel.mirrored_body);
  in sketches the ⇋ Mirror tool (sketcher.mirror) with a `mir` constraint (planegcs symmetric_line per point pair,
  equal radii; its redundant parts are not conflicts). Decorations get X / Y / Turn (doc.py turns the outline).
  tools/e2e_model_mirror.py, tests test_mirror / TestSketchMirror.
- **Imported solids done:** blobs.py (files by SHA-256 on disk, /api/blob), /api/model/import -> worker
  doc.import_solid (a STEP as it is; an STL / OBJ sewn into a solid, kernel.mesh_solid, <= 60 000 triangles); the
  `solid` step takes `blob` and `op` add / cut / ref (refs tessellated apart, drawn see-through). Big shapes
  (> 3000 faces): a quick bbox, a coarser mesh, face areas from the mesh, tiny edges skipped; an unchanged body is
  not meshed again. The project file carries the blobs. tools/e2e_model_solid.py.
- **Edit in place done:** assembly doc.editable {part: true} (locked by default), editInPlace -> app switches to the
  part, modeler.setContext (the other placed parts in its frame, view.setContext; a bar back). tools/e2e_assembly_edit.py.
- **Assembly measure done:** AsmView.measurePoint (corners of every placed part), assembly.clickMeasure (faces /
  axes apart). tools/e2e_assembly_measure.py.
- **Duplicate done:** parts.js duplicate (a new tab after it, "(copy)" names); assembly.ownPart. tools/e2e_duplicate.py.
- **STEP assemblies out (18b) done:** /api/assembly/export/step {tree: {root, parts: {id: {name, features, colour}},
  assemblies: {id: {name, instances: [{ref, matrix, colour?}]}}}} -> doc._tree_step (each part built once, its STEP
  face colours kept, instance names "<part>-<n>") -> kernel.write_step_tree (XCAF: AddShape per part, NewShape +
  AddComponent per assembly, names, colours; STEPCAFControl_Writer, AP214IS, mm). AP214 rather than AP242: OCCT's
  AP242 writer adds nothing we use (no PMI) and AP214 is what the three CAD programs read most reliably. The old
  {instances} flat compound stays. stepfile.stepTree / Assembly.stepTree (a sub-assembly placed with `inner`: a
  product of its own, "Lever (I2)"); the AI's export {format: "step"} on an assembly (get_body gives step_tree).
  tests/test_step_assembly.py (export -> import: tree, names, exact matrices, volumes), tools/e2e_step_assembly.py.
- **STEP assemblies in (18a) done:** kernel._read_xcaf / read_step_tree (XCAF: free shapes, components, locations ->
  column-major matrices, product names, part / face / instance colours; a part placed again is one label -> one part;
  several top shapes under one root; _fold: a sub-assembly of one placement (an ECAD board wraps each component so)
  goes into its parent, the matrices multiplied), step_structure (parts / placements / subs, given by import_solid as
  `structure`), write_step_tree (also to_step_coloured: a part's own STEP with its face colours); doc.import_assembly
  -> a blob per part (_keep: the read shape kept, the shape cache holds more while small), POST
  /api/model/import/assembly. web/js/assembly/stepfile.js: askHowToOpen (choose.js; one body first over 150 parts +
  subs), addTree (a 3D model per part with one solid step, background assemblies, the top one opened; a big tree all
  🪶 light). Open / drop -> openSolid asks; the assembly's ＋ Insert ▾ From a file and a file dropped on its view ->
  hooks.importFile (a sub-assembly). AI: open_file {as: "assembly"} -> load_step_assembly. The 44 MB board: 220
  parts, 270 sub-assemblies, 2269 placements, shown in 70 s (195 s before the cache / light). tests/test_step_assembly.py,
  tools/e2e_step_assembly.py.
- **IGES in and out (18c) done:** kernel.to_iges (IGESControl_Writer, B-rep mode: MSBO solids, mm; `surfaces`: trimmed
  surfaces only, as older programs write it), read_iges (IGESCAFControl through _read_xcaf / read_step_colours(kind
  "iges"): solids as they are; surfaces only -> sewn_solid (BRepBuilderAPI_Sewing 0.01 mm, no free edges -> solids);
  not closed -> the surfaces, `how` "surfaces"), write_iges_tree (the STEP tree's XCAF document, now kernel._xcaf_tree,
  through IGESCAFControl_Writer: every part placed with its name and colour; IGESControl_Controller.Init_s() first, else
  the B-rep mode setting does not exist yet and faces are written). doc.import_solid .igs / .iges -> a STEP blob
  (`iges`: solid | sewn | surfaces; surfaces: op "ref" + a warning), doc.export "iges", assembly_step fmt "iges"
  (/api/assembly/export/<step|iges>, /api/model/export/iges -> .igs). The browser: OPEN_SOLID_RE, the accept lists, the
  Export menu (model / assembly only), the panels' IGES buttons; the AI's export iges and open_file .igs (load_solid ->
  openSolid). tests/test_exchange_formats.py TestIges, tools/e2e_exchange_formats.py.
- **Drawing sheet to DXF (18d) done:** auto3d/modeler/sheetdxf.py to_dxf(svg, dims, scale) — the sheet's printed SVG
  (svg(true), the PDF's) walked with ElementTree: lines / polylines / rects / circles / simple paths / texts on a layer
  per kind (sh-view: dashed -> hidden, 0.18 mm lines -> hatch, else visible; texts -> text; the rest -> frame; the
  balloons -> dims), y flipped, the paper 1:1 in mm ($INSUNITS 4); the dimensions not from the SVG but from
  SheetEditor.dxfDims (where dimSvg puts them: linear a / b / at, dia / rad c / r / u / end, ang X / u1 / u2 / r) as
  real DXF dimensions (dimstyle A3D, DIMLFAC = 1 / scale, "<>" for the measured value with the sheet's prefix kept;
  a fit / thread keeps its own text). POST /api/sheet/dxf; ⬇ DXF in the sheet's bar; the AI's export dxf on a sheet
  (export_data dxf -> {sheet: dxfData()}). The PDF is in true scale: MuPDF makes the page the SVG's mm size, 1 mm =
  1 mm (TestSheetDxf.test_sheet_pdf_prints_in_true_scale). tests/test_exchange_formats.py TestSheetDxf,
  tools/e2e_exchange_formats.py.
- **glTF / GLB and OBJ out (18e) done:** kernel.write_gltf_tree — the parts meshed (as finely as the viewer's), the
  STEP tree's XCAF document (_xcaf_tree finish=True: each part also an XCAFDoc_VisMaterial PBR — its colour, metalness,
  roughness) through OCCT's RWGltf_CafWriter (binary; mm -> m, Z up -> glTF's Y up; node names InstanceOrProduct:
  "Plate-1", sub-assemblies nested; Compact transforms); chosen over writing GLB from our meshes because the XCAF tree,
  names, instance colours and materials come with it. materials.py COLOR / FINISH / finish_of / look_colour mirror
  materials.js (stepTree sends each part's material). doc.export "glb" (one part in its colour and finish, an imported
  file's face colours) and "obj" (kernel.to_obj: shared corners, a normal per triangle, mm); assembly_step fmt "glb"
  (/api/assembly/export/glb; the flat form refused). The Export menu: GLB now for 3D models and assemblies too (the
  quick part's stays viewer.exportGLB), OBJ for 3D models; the panels' GLB / OBJ buttons; the AI's export glb / obj.
  The part's paint (faces painted in the browser) is not in the GLB / STEP (only the part's, instances' and the file's
  colours). tests/test_exchange_formats.py TestGltfObj, tools/e2e_exchange_formats.py.
- **Parasolid (.x_t / .x_b) and JT — looked into (18f), not added:** checked 2026-10-28 on PyPI (jt, jtreader, jtopen,
  jt-reader, parasolid, pyparasolid, xt-reader, x_t … — none exist; pyjt is unrelated) and GitHub. pythonocc-core /
  cadquery-ocp (our OCP) read neither.
  - *Parasolid*: Siemens' kernel. The XT format is documented (Siemens' "Parasolid XT Format Reference"), but every
    working reader is commercial: Parasolid itself, OCCT's paid Parasolid XDE component, CAD Exchanger, HOOPS Exchange.
    Open efforts: omerbasavul/cadconvert (Rust, C ABI / .NET, MIT, created 2026-08, 4 stars: x_t / STEP -> glTF / USDZ
    *meshes* only — no B-rep for our kernel, very young); akiselev/xt-parser (Rust, WIP alpha, no licence: may not be
    used).
  - *JT* (ISO 14306): Siemens' JT Open Toolkit needs a JT Open programme licence. Open Cascade published its JT reader
    (TKJT) and JT Assistant under GPL-2.0 (Open-Cascade-SAS/JT-Assistant, 2025; fork cbsghost/oce-jt, 2019): C++ / Qt,
    reads the tessellated LODs (meshes), not the exact XT B-rep inside a JT; GPL-2.0 — linked into the app it would
    make the app GPL; run as a separate program on a file it would not, but it needs a C++ / Qt build for Windows.
    Others are partial: TobiasMusin/Voyager (Java, Apache-2.0, experimental JT 10 -> glTF mesh), svr2kos2/JTReader (C#,
    MIT, WIP), ian-wigley/JT-Reader (partial, v8.1).
  - *Recommendation*: no native or Parasolid / JT reading now; STEP stays the way in (SolidWorks, CATIA, Solid Edge, NX
    and Creo all save STEP AP214 / AP242; the app tells the user so). If a JT / XT must be seen one day: a mesh-only
    👁 reference body through an external converter run as its own program (cadconvert, MIT), never as an exact solid —
    and only once an open reader has matured. Revisit in a year.
- **Exchange tested with real files (18g):** samples/ToImportToOurApp (55 MB; README.md: for each file
  the program that made it, how to open it, what to see, its source and licence; samples.json the same for the tests;
  solidedge/ waits for the owner's own exports) — besides STL / OBJ meshes, 3MF, DXF / DWG, PDF drawings, pictures for the
  outline wizard and a KiCad Gerber + Excellon board; STEP from CATIA V5 (R14, R19, R20 and NIST's CTC / FTC), NX (8.5; UG via Theorem), Creo / Pro/ENGINEER,
  SolidWorks 2010 / 2017 / 2021, Inventor 2019, Fusion 360 / Inventor (Autodesk Translation Framework), I-DEAS,
  CoCreate, AutoCAD 2000, ACIS, EUCLID, 3D_Evolution; AP203 / AP214 / AP242 e1–e3; IGES from SolidWorks, Inventor,
  EUCLID and Open CASCADE. Public domain (NIST), CC-BY 3.0 (FreeCAD-library), LGPL (FreeCAD, OCCT, occt-import-js), BSD
  (STEPcode). tests/test_cad_samples.py (every file under 3 MB: faces, volume, bbox, structure, the assembly tree's parts /
  placements / volume, STEP / IGES round trips; ~40 s) and tools/e2e_cad_samples.py (each file through the browser:
  import, an AI edit — sketch + cut, hole, fillet —, sheet -> PDF / DXF, STEP / IGES / GLB out and the STEP read back,
  an exact print split). Worked: every B-rep part and assembly opened (parts, placements, sub-assemblies and names as in
  the file; up to 41 placements, 7.8 MB in ~38 s), edits, sheets, exports and round trips. Found (listed as expected
  failures in the unit test; for the main session): read_step_tree segfaults on a STEP whose assembly label has no name
  (kernel._label_name: TDF_Label.FindAttribute on a missing TDataStd_Name — NIST CTC-02 AP242 "Open as an assembly"); a
  part's volume counts loose faces (supplemental surfaces) in kernel.volume (CTC-02: 45.47 instead of 47.11 · 10⁶ mm³);
  non-ASCII names written double-UTF-8 in the STEP export ("Držák" -> "DrÅ¾Ã¡k", _xcaf_tree) and 8-bit names read
  wrongly ("ÖN" -> "Վ"); a model's STEP export drops the file's face colours (doc.export -> K.to_step); the "Open as an
  assembly?" count includes empty products (Pro/E AS1: 10 / 36 for 5 / 18); a tessellated AP242 opens as a body with a
  negative volume, and its sheet (like an IGES reference body's) never builds; an assembly with external references
  (CATIA S1, 12 part files) says "no solid"; flat faces stored as B-splines (I-DEAS, Inventor's IGES) are not "plane"
  faces, so no sketch / hole on them; a failed sheet build (/api/sheet/build or /api/sheet/assembly 500 — a reference
  body, a tessellated one, the MIT E-Vent assembly over the worker's 120 s) shows no message, the sheet just stays empty;
  a cut on the Reespirator's B-spline "balloon" raises its volume; autosave can answer 500 (os.replace while the same
  project's previous save holds the file: WinError 32). Other formats: STL / OBJ open as quick parts, DXF and the
  Gerber set as 2D drawings, pictures in the outline wizard; DWG needs ODA / LibreDWG (says so); 3MF is not read
  ("Unsupported file type"); NIST's GD&T PDF sheets give no part (FTC-11) or a wrong 25 × 9 mm one (CTC-01).
- **Real-file import faults fixed (18h):** kernel._label_name checks the name is there (FindAttribute on a label without
  one killed the worker: CTC-02 AP242 as an assembly), components pointing nowhere are skipped; kernel.volume counts
  the solids only (loose faces beside them: kernel.loose_faces, shown as a `<id>:surfaces` reference, out of the
  booleans) and integrates faces other than planes / cylinders adaptively, each solid on its own (the quick rule was
  ~1e-4 off on B-splines and spheres: a cut "raised" the Reespirator balloon's volume); step_structure counts only
  products with faces (Pro/E AS1: 5 / 18 as opened); kernel.turned_out turns inside-out solids the STEP reader's
  healing leaves (by the volume's sign); a tessellated STEP (faces with triangles only: kernel.faceted) becomes a solid
  of its facets per closed body (faceted_solids -> mesh_solid) with a note; B-spline faces flat within 1e-5 mm are
  planes (flat_plane: GeomLib_IsPlanarSurface, oriented like the surface) for frames, sketches, holes; a fillet on
  smooth edges (BRepLib.ContinuityOfFaces) says so (NIST FTC-07's longest edges are tangent to roundings); IGES
  surfaces are sewn per shell (sewn_solids: a solid per closed body, the rest loose faces, how "partly"; again at
  1 / 10 000 of the size); an assembly with external references (external_refs: DOCUMENT_FILE names) opens with its
  part files picked together (/api/model/import takes several files; _main_file picks the top one; merged_step makes
  one STEP of them), alone it names the files it needs. tessellate classifies flat faces with one classifier per solid
  (40 s -> 4 s on a 1 700-face part). Tests: test_cad_samples (TestCadSampleKnownBugs: a test per fault, no expected
  failures left); e2e_cad_samples (S1 picked with its folder).
- **Real files: autosave of one project at once done:** autosave.save takes a lock per project id, writes each file
  through a temp file of its own (pid + thread) and retries the replace for ~2 s on a sharing violation (WinError 32 /
  5 while a reader holds the file); reads retry too; a disk error answers 503 with the reason (the last state kept).
  tests/test_autosave.py test_same_project_saved_at_once (6 threads × 15 saves + a reader: failed before with
  PermissionError); tools/e2e_autosave.py fires six saves at once (all 200).
- **Real files: 3MF import done:** importers.read_3mf_groups (the zip's start part from _rels, else the one .model;
  objects with a mesh or components, build items' and components' transforms, the unit, basematerials / colorgroup
  colours) -> read_3mf; .3mf in MESH_FORMATS (a quick part, like STL / OBJ: Open ▾ CAD / 3D file, drop, the AI's
  open_file), in import_solid (▣ Solid from a file, an assembly's From a file / drop) and project files. Box 10 × 20 × 30
  (6 000 mm³), cube_gears (17 objects, 25 692 triangles, placed), our part_base_plate.3mf (its two colours; the same
  volume as its STL) and assembly_frame.3mf (57 698 mm³ ±1 %) read back. tests/test_import.py Test3MFImport,
  Test3MFSolid (the solid and its STEP round trip); tools/e2e_cad_samples.py opens both 3MF samples (box 0.1 s, cube_gears
  19 s).
- **Real files: drawing sheets that fail or take long done:** the sheet routes run through server._sheet_call: the
  request's rid (the app's progress bar with Cancel: 409), the exact drawing limited to EXACT_SHEET_TIMEOUT (150 s) then
  stopped and made again from the mesh (doc.sheet / assembly_sheet `simple` -> sheet.geometry(from_mesh), SHEET_TIMEOUT
  600 s), a kernel failure answered 422 with its reason (was a bare 500). An assembly over sheet.ASSEMBLY_EXACT_FACES
  (1000) is drawn from its mesh at once: MIT E-Vent (41 placements, 2 150 faces) — the exact HLR of its top view never
  ended (> 40 min; front / right 4 s), from the mesh 12 s in the kernel, 10 s in the browser. Why a part cannot be
  drawn: doc.sheet "only a reference body" (an IGES of open surfaces), sheet.geometry "no size to draw" (no box: the
  tessellated NIST FTC-08). The sheet (sheet.js) toasts it once and shows it on the paper with ↻ Try again (Czech too).
  tests/test_sheet_errors.py; tools/e2e_sheet_errors.py; tools/e2e_cad_samples.py waits for the built sheet or its
  message (MIT E-Vent, hammer.iges, FTC-08: all OK; the manifest's known sheet failure dropped).
- **Real files: a PDF of several views says it is unsure done:** what NIST's GD&T sheets do to the PDF reader
  (sketch.py): it takes the stroked lines of the widest class (≥ 0.6 × the thickest) as the outline and the largest
  closed loop of them as the part; CTC-01's views are 0.72 pt lines with arcs (67 curves, dropped) and crossing lines,
  so none of its 21 shapes closes — the only closed loop is a 71 × 25 pt box (25 × 9 mm at 1:1); its dimension values
  are letter outlines, not text (no dimension is read: every size a guess). FTC-11's part is drawn in 0.36 pt lines
  under 14 short 0.72 pt strokes; read with the next width class down it still gives only small closed boxes, so no
  simple fix — the reader now says so: `unsure_outline` (a warning, also a toast: the largest closed outline is smaller
  than shapes that do not close; their boxes drawn), `no_geometry` explains "a dimensioned drawing with several views
  … trace the view from a picture", `no_text` also when the values are outlines (extract.outlined_glyphs ≥ 20 and no
  dimension read). tests/test_pipeline.py (synthetic sheets, the two NIST PDFs); tools/e2e_cad_samples.py (pdf/).
- **STEP colours done:** kernel.read_step_colours (STEPCAFControl + XCAF: colours followed down the assembly tree to the
  faces of the shape the solid step uses), State.colours by face name -> faces' `color` in the rebuild; the view /
  assembly show them under the paint. tools/e2e_step_colours.py.
- **2D drawings done:** a part kind `drawing` (auto3d/drawing2d.py read_drawing: entities + layers + colours in mm,
  file units; outline_of -> importers.outline_polys for a quick part), web/js/drawing2d/editor.js (canvas viewer, layers,
  select / line / circle / measure, snapping, units, Use ▾ -> drawingToSketch or /api/drawing/outline). DXF / DWG open
  there. tools/e2e_drawing2d.py.
- **Sketch snapping & auto-dimension done:** sketcher.refs().circles (the part's closed round edges square to the
  plane), snap / pickTarget use them; autoDimension tries autoDimCandidates (sizes, then nearest part edges, then the
  origin) one by one, keeping a size only when the solver's free count drops. tools/e2e_sketch_auto.py.
- **Paint done:** part `paint` [{name, fp, color}] (paint.js: the same-named face nearest fp), faces' `solid` index from
  the kernel, 🎨 Paint mode (faces / bodies, Ctrl+click), the look in the modeler's undo; rename.js for 🏷. tools/e2e_paint.py.
- **Look done:** part data `color` / `opacity` (view.setLook), a placed part's `colour` / `opacity` override
  (assembly.lookOf). tools/e2e_look.py.
- **Concentric distance done:** an axis joint's `dist` / `side` (joints.js axialEnds / axialGap: the round faces'
  lengths along the axis from the mesh, assembly.cylSpan); two holes joined get it filled in; ↻🔒 sets `angle`.
  tools/e2e_assembly_concentric.py.
- **Value ranges done:** doc.limits (each ranged number of a step found by building it at trial values; patterns and
  depths from the geometry), /api/model/limits; failures explained with the most that fits (doc._sized).
- **Sketch relations done:** par / perp / eq / conc / coin / tang / fix (+ h / v) set by the user (constraints.py
  _relation; sketcher RELATIONS, symbols, list; collapsing solutions refused). tools/e2e_model_relations.py.
- **Hole callouts on sheets done:** doc._holes (each hole step's d / thread / depth / head / fit / teardrop; _head_sizes
  shared with the hole feature) -> sheet.build(holes) -> geometry.holes; auto_dims gives each step's holes one dia dim
  {hole: step} in the first view showing them round (sheet._step: "<step>:hole|cbore|csk:k", a pattern's copy too), its
  head's circle no Ø of its own; the text (sheet.callout / SheetEditor.calloutRest): "4× Ø3.4 THRU", "M5 ↧ 8",
  "Ø3.4 ⌴ Ø6 ↧ 3.2", "M3 ⌵ Ø5 × 90°", "Ø8 H7 THRU", "Ø6 THRU ▲". The check: a callout gives its step's Ø, head Ø, angle,
  depths and its head's edges; without it a countersink's angle (an ang dim on its cone), a counterbore's / blind
  depth (a linear dim on cbore_floor / bottom) are missing items {kind: hole, hole, key: the hole circle}; ＋, the AI's
  complete and add {circle} on a hole circle add the callout (calloutFor). PDF: MuPDF takes ⌴ ⌵ ↧ ▲ from its Noto
  Symbols fallback (the text extracts as typed); DXF: the dimension's own text (Unicode, the drafting program's font
  shows it). Also: suppressed hole steps no longer feed the sheet's fits / threads. test_hole_callouts (+ the 171-hole
  plate: one "171×" callout); tools/e2e_sheet_hole_callouts.py.
- **Hole heads that fit done:** a threaded hole's head defaults come from its nominal Ø (M3: ⌵ Ø6, ⌴ Ø5.4 × 3), not d
  or the tap drill — doc._head_sizes, the AI's add_feature headOf, the Hole panel's Head choice alike. doc._head_fits
  (before cutting): kernel.head_room (the head's rim just under the face inside the part all round, else the widest
  that is) and kernel.material_along (the part's depth under the hole, a blind hole's own depth) — a head wider than
  the face or as deep as the part is an issue with the most that fits ("at most Ø6.4"), never cut through.
  test_hole_head_fits; tools/e2e_sheet_hole_callouts.py (the AI's M3 ⌵ on a 2 mm plate).
- **Sheet views renamed, moved and scaled done:** d.viewNames (a double-click on a view's label on the sheet: a field
  over it; or on its name in the Views panel; in undo, the PDF, the DXF), d.scale (the sheet's own, an override of the
  fit: sheet.parse_scale "1:2522" / "3:1" / "1/5" / "0.5"; layout(geo, paper, scale, frame) — server.py _sheet_layout
  makes the layout for it; Auto chooses A3 when it does not fit A4) and d.vscale (a view's own, its label "Top
  (2:1)"; SheetEditor.vs(v) everywhere a view is drawn / picked; the DXF's dimensions of it get their own DIMLFAC).
  Scale choices: 10:1 … 1:100 and Custom… (choose.js ask(): a small text dialog). The title block's Scale is the
  sheet's; dimensions stay the part's sizes. Views past the frame: a warning (panel, status, get_sheet past_the_frame),
  never refused. Dragging a view snaps it in line (Top under / over Front, Right and Section beside it, within 4 mm, a
  dashed guide); Shift: free. sheet_edit scale / view_scales / view_names for the AI. tests/test_sheet_views.py;
  tools/e2e_sheet_views_templates.py.
- **A modern title block done:** SheetEditor.titleSvg redrawn (the same SVG on screen, in the PDF and the DXF) with
  every field kept (ISO 7200): a company / logo column on the left (Auto3DModeler · Dimensions in mm until a company is
  given), the kind line (Part · in … · Pos. n) small and muted over the part's name large and bold, the drawing no. on
  its right; then Material | Scale | Paper | Tolerances | Sheet n / N and Drawn by | Created | Changed · Rev | Note —
  labels 1.75 mm grey over 2.9 mm values; one 0.35 mm outline, 0.13 mm rules between rows and short ones between
  cells; dates as ISO 8601. 150 mm wide on A4, 180 mm on A3, inside the frame's right / bottom margins. The parts list
  of an assembly's page in the same style (one outline, muted header over a rule, light rows, the position bold).
  tools/e2e_sheet_views_templates.py (inside the frame, black / grey / white only, the name ≥ 5 mm).
- **Title-block templates for a whole drawing set done:** auto3d/title_templates.py — {name, layout block | strip,
  hide [fields], texts {company, address, drawn, note, tolstd}, logo (a data URL ≤ 400 kB), frame} kept in
  data/title_templates.json (server-side, like the parts library: every project uses them); the app's Modern (the
  default), Compact (a strip) and ISO 5457 cannot be changed. GET / POST / DELETE /api/title-templates. A sheet names
  its template (d.template); without one it takes its drawing set's (the top assembly's sheet's — new sheets of the set
  too), else Modern; d.tb {layout, hide, logo} are this sheet's own changes. The right panel: Template ▾, 💾 Save as
  template… (ask: a name; the title block as shown, the sheet's company / address / drawn / note / tolerance standard
  go into it), ⇶ Use for all drawings of this assembly (hooks.applyTemplate: every sheet of SheetEditor.pagesOf(root),
  the top assembly's made when it has none), and folded: Company, Address, Tolerance standard, Logo (scaled to ≤ 600 ×
  300 px), Layout Block | Strip (14 mm: layout(frame.title) gives the views the room), the fields shown. svgOf takes
  the set's template, so the PDF, the DXF and 📚 All pages show it. AI: sheet_edit template / template_all /
  save_template, texts company / address / tolstd; get_sheet template + templates. tests/test_title_templates.py;
  tools/e2e_sheet_views_templates.py (typed, saved, kept on the server; Machine → Lid unit → Lid / Pin, Base: all five
  pages and their PDF carry the company; a new sheet of the set takes it; the DXF; back to Modern).
- **The sheet's frame and margins done:** frame {preset simple (10 mm, 0.5 line: the default, as before) | iso (ISO
  5457: 20 mm left for filing, 10 elsewhere, 0.7 line, zones, centring marks) | narrow (5 mm) | none (no line, 10 mm
  kept) | custom {m [left, top, right, bottom] ≤ 40 mm, line ≤ 2 mm, zones, marks}} — held by the title-block template
  (so a drawing set follows it), a sheet's own d.frame overrides it (in undo). SheetEditor.frameSvg: the line; zones
  (about 50 mm each, an even count: A4 6 × 4, A3 8 × 6; numbers across, letters down, in the margins with ticks);
  centring marks from the paper's edge 5 mm into the frame. layKey / layReq pass the margins to layout(frame) — the
  views' cells and the auto-fit scale use them; the title block, parts list and the fit warning sit inside them; the
  PDF and DXF draw it from the same SVG. The right panel's Frame: Simple | Standard ISO 5457 | Narrow | None |
  Custom… (its five numbers and two ticks). AI: sheet_edit frame; get_sheet frame. tests/test_sheet_views.py
  (margins, a strip's room, the fit); tools/e2e_sheet_views_templates.py (ISO: the PDF's frame rect at 20 mm, zones A
  / 6; None: no frame; Custom… 25 mm typed, Ctrl+Z; the template's ISO frame on all five pages of a set).
- **Short sketch suggestions done:** Sketcher.suggestions — at most 4 rows + ✕ Delete, ranked: a dimension first,
  then the relations nearly true already (two lines: ∥ under 10°, ⟂ over 80°, = within 10 % of length; two circles:
  ◎ / = / ⌒ by how near; of the nearly true ones = after ∥ / ⟂ / ◎; none: the nearest one), not those held already
  (hasRule: ∥ / ⟂ by both lines' H / V); a loop (loopOfPicks -> loopFrom, split out of loopAt): ⧈ Offset, ⁂ Pattern,
  ✥ Move; mixed: ✥ Move…, ⧉ Copy, ⇋ Mirror. ⋯ More… (sgMore, reset by a new pick) lists the rest in Edit / Relations /
  Kind sections (showSuggest {section}). The title counts "N shapes, M points". The picks as a whole: pickShapes /
  pickPoints / pickCentre (a picked point is the pivot); transformPicks (move / rotate / scale: their points held
  where they go — solve(drag) — the relations kept; turnRules: a quarter turn swaps H / V and dx / dy locks, any other
  angle puts ∥ / ⟂ for them); relock {exact}: constraints.solve's new `held` {ok, conflicts} refuses a hold the locks
  do not let through, the toast naming them; xformBox (✥ dx / dy, ⟳ 90°, ⤢ 2×: shown at once, retyped from where they
  were, one undo step, Esc back); copyPicks (beside them, H / V, tangents, locked sizes along; the copy picked);
  mirrorPicks (the ⇋ box: an axis or a line and done); addRelations (chains as one undo step, a held one left out).
  test_held_says_whether_a_group_got_there; tools/e2e_sketch_multiselect.py.
- **Dragging several picked sketch shapes done:** Sketcher.down — a press on one of several picks (inPicks: a picked
  shape, a point of one, a picked side's rectangle) drags pickPoints together; the grabbed point (the nearest of the
  shape's own) snaps (snap's skip takes a Set: the moving points are not snapped to, nor guide from), its guides drawn
  (dragGuides); the others by the same offset, the solver keeps the relations; one undo step; picks kept (refreshPicks).
  An unpicked shape dragged moves alone and drops the picks. tools/e2e_sketch_multiselect.py.
- **🔩 Cosmetic threads done:** part `threads` "hidden" (default) | "cosmetic" (doc.THREAD_MODES). Every rebuild says
  where the threaded holes are: out.threads {mode, holes} — doc.thread_holes (cached per features key) finds them by
  their walls' names ("<step>:hole:k", a pattern's / mirror's copies "P1:2:<step>:hole:k") in the built body;
  kernel.round_span gives the wall's axis, its extent along it and which ends are open (the classifier a hair past
  each end: an open end is not inside the part; of two, the one the step's normal points to is the entry) -> {name,
  thread, at (entry, on the axis), axis (into the part), depth, major, minor (tap drill), pitch (doc.PITCH, ISO 261
  coarse), through}. ModelView.setThreads draws them (view.threadSegments: a right-hand helix on the wall, a hair
  inside it, 24 pieces a turn, and a 48-piece ring at the major Ø a hair above the entry face; its own thin
  material, clipped by ✂ Section); the solid is unchanged. The click's "The part" section: 🔩 Show all threads /
  Hide all threads (only with threaded holes); the Part panel's 🔩 Threads Hidden / Cosmetic; the setting is in the
  modeler's undo (the look snapshot) and the project file; an assembly's placed part shows its part's (AsmView, the
  body's threads). The AI: set_look {threads}. test_cosmetic_thread_data; tools/e2e_model_threads.py.
- **🔩 Real threads done:** part threads "real": after all the steps doc._real_threads cuts an internal ISO metric
  thread into each threaded hole (cached per features key, so a view change or an undo does not cut again; the
  steps' own refs are untouched — they were built before it). kernel.thread_tool: the basic profile of ISO 68-1 (60°
  flanks, P/8 flat at the major Ø; a trapezoid from 0.1 P inside the tap drill out to the major Ø, kernel.thread_reach)
  swept with BRepOffsetAPI_MakePipeShell along a right-hand helix (2D lines on a Geom_CylindricalSurface, a fixed
  binormal: the profile stays in the axis's plane), cached per (major, minor, pitch, length). The helix is one edge a
  turn: one long helical face made the cut with the hole's cylinder fail silently (no intersection found: the volume
  unchanged, or wrong); per turn it is right to 2e-5 of the groove's analytic volume. A groove runs a pitch past an
  open end and stops thread_reach short of a blind bottom; kernel.along places it (a location, no copy);
  kernel.cut_threads cuts them all at once (SetRunParallel: 8 holes 4.6 -> 1.5 s) carrying the names — the hole's
  wall keeps "<step>:hole:k" on its strips, the thread's faces are "<step>:thread:k" (a copy's "P1:1:<step>:thread:k").
  A cut that fails or removes nothing: the part without threads and threads.real.issue. rebuild's threads.real {holes,
  cut, seconds, warning (more than MANY_THREADS = 8), issue}. body_of(part, threads=True) gives exports (STEP / IGES /
  STL / OBJ / GLB), the print split (its STEP printing copy), assembly STEP / clashes the threaded body; the sheet, the
  PDF drawing and the assembly sheet take threads=False (no helix edges: the callout and, in sheet.js, a thin ¾ circle
  at the major Ø on each threaded hole seen round, class sh-thread). The browser: the choose dialog "Cosmetic (light) |
  Real geometry (slower)", the Part panel's Real (+ "n real threads, cut in s" and the warning), a toast with the
  time; while a tool / a sketch is open real is asked as cosmetic (threadsShown). Placed parts: flatParts / the STEP
  tree carry their part's threads. Measured (tessellation included; the cut alone in brackets): M5 × 10 one hole 0.45 s
  (0.23 s), 220 -> 6 238 triangles; 8 holes M6 × 12 3.7 s (1.8 s), 1 676 -> 48 574; 12 holes 5.1 s (2.5 s), 2 508 ->
  77 308; again (cached) 0 s. The STEP of two M6 × 12: 1.7 MB (80 spline surfaces). Left out: external threads on
  shafts (no thread feature for them yet), a print clearance on the profile, thread run-outs, left-hand / fine
  pitches. test_real_thread, test_real_threads_split; tools/e2e_model_threads.py.
- **Floating boxes moved and resized done:** web/js/floatbox.js floatBox(box, viewport, {kind, handle, remember,
  min, onDefault}) — called after a box is put in its view (again after its content is re-rendered): dragged by its
  header (or a slim ⠿ .fb-strip added on top / at a bar's left end), resized by the .fb-size grip in its bottom-right
  corner (pointer events, window listeners in the capture phase; min sizes, the content scrolls), the one in hand on
  top (.fb-front), kept inside the view and under the command bar (a ResizeObserver on the view pulls it back in),
  remembered per kind in localStorage a3d.box.<kind> ({ax, dx, ay, dy} from the nearer side of the view + {w, h}); a
  double-click on the header forgets it (back at the caller's default place). Clicks on its buttons / fields neither
  drag nor reach the 3D view. Covered: the suggestions table (suggest; was a3d.suggestAt), 🖨 Print check
  (printcheck), 📏 Measure (measure — 3D model and assembly), ✂ Section (section), and in sketches ⇋ Mirror, ⁂ Pattern,
  the quick size box (sk-mirror / sk-pattern / sk-quick); the boxes that open by the mouse — the size editor
  (dimedit), ⧈ Offset by, "Which distance?" — keep only their size (remember 'size'). Not covered yet: the 2D
  drawing editor's .dw-measure line; the drawing sheet editor (sheet.js) has no box floating over its sheet.
  tools/e2e_floatboxes.py.
- **A face's centre does not drift with its holes (fix):** a flat face's frame `o` (kernel._box_centre) is the middle of
  its box in its own u / v, not the centre of its area — that moved with every hole cut into the face, so the AI's
  second hole landed 0.32 off (40.32 for 40) and any edit_feature of a hole (it picked the face's frame again) moved
  the hole (8.25 / 6.5 -> 8.14 / 6.56). edit_feature keeps the step's stored frame while its face, mid and origin
  stay; a key beside `fields` is refused ("put the changes in fields: {…}"). Saved frames are used as stored.
  test_face_centre_ignores_holes; tools/e2e_agent.py.
- **Export names and colours right (fix, found making samples/ExportFromOurApp):** names reach XCAF as UTF-8
  (`TCollection_ExtendedString(text, True)`: "M6×16", not "M6Ã—16"); a STEP is written in ASCII, its other characters
  as STEP's own `\X2\00D7\X0\` (kernel._step_ascii — OCCT wrote raw UTF-8); the writers' Interface_Static settings
  (product name, schema, IGES B-rep mode — one set per worker process) are set for one export and put back
  (kernel._settings), so a part's STEP no longer took the last assembly's product name. A part's STEP / IGES go
  through XCAF as the assembly's do: its name, its colour (own or material's), its faces' colours — an imported file's
  and the 🎨 paint (doc.face_colours resolves part.paint as paint.js paintedFaces: the face of that name nearest fp,
  or every face of a step); the assembly tree carries each part's paint (stepfile.js) to STEP, IGES and glTF. An
  assembly's IGES is a body per placement (kernel._flat: copied there, so a part placed twice keeps each placement's
  colour), each named in ASCII by its placements' path ("Post pair-2/Post-1", "M6x16"). glTF: a part's colour lives in
  its material only, so a placement's own colour (the green post) shows. The BOM's Bought / made by the material
  (materials.printed / made_how: a printing plastic "made (3D print)", else "made"); an assembly sheet's title block
  material "—" (not "PLA"). test_export_names, test_export_samples; the samples made again.
- **One dark look for choices (fix, the owner: "the Views panel does not fit the app"):** styles.css gives every
  `<select>` (and text field) the app's style at zero specificity (`:where`): var(--bg), the --line border, a quiet
  SVG arrow, the .field height, the accent focus ring, a dimmed disabled state; panel rules set background-color only
  (the arrow stays). The sheet's Views panel: one grid row per view — ☑, its name (double-click: rename; its own
  dimensions as a small tag), ✓ / ⚠ n, ⋯ (a small menu: Dimensions in this view — As the sheet, Light, Medium, Full,
  All its sizes), the scale in a column (Sheet 1:2 / standard / Custom…; disabled while the view is off); Section A–A
  is a row of its own (its tick turns the section on, no separate check box); a one-line hint. Verified on screenshots
  (sheet left / right panels, 1600 × 1000 and 1280 × 800, EN / CS; the hole panel; the material choice; the library);
  tools/e2e_sheet.py and e2e_sheet_same.py pick the per-view dimensions through ⋯.
- **Parallel booleans done:** every boolean of the kernel (BRepAlgoAPI Cut / Fuse / Common — combine, up to next,
  rib, split, material_along, the print split's `boolean`, clashes, the sheet's section, real threads' cut_threads)
  goes through kernel.bop, which sets SetRunParallel (kernel.PARALLEL; A3D_PARALLEL_BOOL=0: serial). No Splitter /
  BOPAlgo builder is used. Verified the same: the whole unit suite passes both ways, and tests/test_parallel_bool.py
  builds holes, threaded holes, real threads, patterns, fillets / chamfer, shell, split, rib and the 171-hole plate
  both ways — volumes to 1e-9, face counts, face names; clashes, print pieces and a section alike. Nothing had to stay serial. Times (best of 3, a loaded 16-core machine,
  serial -> parallel): the 171-hole plate rebuilt 5.29 -> 4.06 s, a split step 0.68 -> 0.61 s, the exact print split
  (the plate on an 80 mm bed, 6 pieces) 0.88 -> 0.82 s, a clash check of three such plates 0.78 -> 0.59 s — the
  booleans are small (one hole each): most of the time is outside the intersection stage.
- **A pool of kernel processes done:** worker.Pool (WORKER; server.MODEL_WORKER) of N Worker processes
  "auto3d-kernel-<i>": N = A3D_WORKERS, else min(4, cores − 1), one more only with 2 GB free each (psutil, else
  GlobalMemoryStatusEx on Windows; this 16-core machine: 4); /api/kernel says `workers`. Routing (worker.part_key):
  a part's jobs by its first step (an imported file: its blob; that is what its cached prefixes, meshes and
  sheet views start with, so the modeller tab, the assembly, the sheet, limits and the AI meet the same caches);
  an assembly's clashes / sweep / sheet by its instance ids; a print split by its file; imports of a new assembly
  and assembly exports: the least busy. A key keeps its process (LRU of 512); a new one goes to the least busy (then
  fewest parts); a part whose process has been busy > 1 s with other parts' jobs (none of its own waiting) moves to
  an idle one. Each Worker: its own pipe, a Condition and a FIFO of job sequence numbers (jobs run in the order they
  came; a Cancel while waiting leaves the queue); the reply carries the job's number (an answer to a job cancelled
  after it was sent is not taken for the next one's). A crash fails that job and those waiting for that process
  ("…while building another job — try again"), restarts only it; a timeout / Cancel kills only it; a process over
  A3D_WORKER_MB (3072) resident is restarted after its job. The worker loop and its ops table are unchanged (the
  messages carry the number). Browser: assembly.buildBodies keeps a part's newest build (an older answer coming
  later is dropped), the sheet's ensure keeps its newest run, the drawing set asks for its parts' sheets at once
  (the modeller's pump and the clash check were already ordered). Times (A3D_WORKERS=1 -> 4): an assembly of four
  171-hole-like plates opened 8.82 -> 2.09 s, a drawing set of four parts 3.17 -> 0.90 s, the two-sessions test
  (one imports the 44 MB board and draws the 171-hole plate, the other edits a small part): the small part's
  rebuild 28.4 s (behind the import) -> 7–19 ms, the plate's sheet 25.0 -> 1.4 s; two heavy parts from two
  threads 3.49 -> 2.14 s. tests/test_kernel_pool.py; tools/e2e_kernel_pool.py.
- **Title-block styles A–E done (the owner's five designs):** web/js/sheet/tbstyles.js titleBlock draws them as SVG in
  mm, from the 5 px = 1 mm mockups: A "Strip" 180 × 21 (IBM Plex Sans Condensed, one row), B "ISO 7200" 180 × 40 (IBM
  Plex Sans; drawn / checked / approved, roughness, the first-angle projection symbol), C "Dark band" 180 × 34
  (Barlow), D "Minimal" 170 × 28 (Inter, no grid), E "Column" 90 × 56 (Plex Condensed). Their fields (SheetEditor
  tbFields): the name, what it is ("Part · production drawing"), drawing no., rev, material, mass (a part's volume —
  /api/sheet/build now gives it — × its material's density; an assembly's from its BOM), scale, paper, sheet n / N,
  tolerances, roughness (a new text `surface`), drawn by, the date (28. 10. 2026 in Czech, 2026-10-28 in English),
  checked / approved (new texts, — when empty), the company (its first word as the mark, or the logo) and address.
  Labels small and in capitals as in the designs, Czech through i18n. The fonts (SIL OFL, the licences beside them)
  are in web/fonts (tools/make_sheet_fonts.py: static weights cut from the variable Plex Sans / Inter, all subset to
  Latin + Czech + the drawing symbols, ~58 kB a file; fonts.css); texts are measured in the loaded font (a canvas) to
  fit and to right-align. The PDF: MuPDF's SVG reader only has its base fonts, so auto3d/modeler/sheetpdf.py takes a
  style's texts (they carry data-ff) out of the SVG and writes them on the page with the same font files (PyMuPDF
  TextWriter, baseline / anchor / letter spacing kept; a letter a font lacks in Helvetica or Droid Sans Fallback),
  then subsets the fonts. The DXF keeps its Arial text style. New sheets still start with Modern.
- **Parts-list styles A–E done:** tbstyles.js partsList, each with its title block's font: A a muted header over a
  rule, hairline rows, "6 items · 23 pcs in all … total mass"; B the rows numbered bottom-up over a light grey header
  band and "Parts list · 6 items · 23 pcs … Σ mass", thin column rules; C a black "Parts list" band with the summary,
  the positions in circles like balloons; D no vertical lines, hairline rows, a spaced heading; E 90 mm, two lines an
  item (the name over its standard / drawing no.; the material over make · mass). Columns: pos, name, qty, material,
  mass each (ctx.massOf), standard / order no. (the library's pn, else that part's drawing no.), make / buy (make /
  print 3D / buy). On an assembly sheet the list sits directly on the title block, both at the frame's right /
  bottom (other widths: aligned right), as many rows as fit 40 mm under the top (then "… n more"; the balloons kept,
  SheetEditor.balloonsSvg). A 📋 BOM page in a style: the summary / structured BOM the frame's width on the title
  block, "Bill of materials — <assembly> · Summary · n / m" in the style's title, its rows per page by the style
  (bomRowsIn).
- **Any title block with any parts list done:** a template has titleStyle (block / strip — the app's Modern — or A …
  E; an older one: its layout) and bomStyle (modern / A … E), checked by auto3d/title_templates.py; the app's
  templates "A — Strip", "B — ISO 7200" (with the ISO 5457 frame), "C — Dark band", "D — Minimal", "E — Column" pair
  each title block with its own list (Modern stays the default). The sheet's panel: Title block style ▾ and Parts
  list style ▾ under Template ▾ (d.tb.titleStyle / bomStyle — this drawing's, the hint says so, until 💾 Save as
  template… keeps both with the frame; ⇶ Use for all drawings with an unsaved mix asks for its template name first);
  the Layout Block / Strip chips are gone (Modern — strip is a style). Folded: Roughness (Ra) (kept in the template),
  Checked by, Approved by. AI: sheet_edit title_style / bom_style (template_all with an unsaved mix wants
  save_template), texts surface / checked / approved; get_sheet title_style / bom_style; the automation-design skill
  says how. tests/test_title_templates.py (styles saved / loaded, older ones, the five designs); tools/e2e_sheet_styles.py.
- **The views keep off an assembly's parts list done:** the styles' taller lists (8 mm rows) covered the views. The
  sheet sends the layout a keep-out (SheetEditor.keepOut / listKeep: the title block's and the list's rectangles as
  drawn — rows past "… n more" are on the BOM page — per paper when it is Auto) and iso_at Right; sheet.py layout
  (_keep, _room, _clear) moves a view in the union's way up or left (the front and the top view together, they line
  up; KEEP_GAP 14 mm beside, 18 mm below for the sizes and names), shrinks the iso view, then takes the auto scale a
  step smaller; an own scale stays. An iso view not moved by the user follows the new layout (isoLaid); one the user
  dragged onto the list stays and gets ⚠ past the frame (outside). tests/test_sheet_views.py TestLayoutKeepOut;
  tools/e2e_sheet_styles.py 1b (all 36 title / list pairs at A4 and A3, 5 parts: no view box over the list or title).
- **Typing straight into the title block done (the owner: "mělo by jít psát přímo do razítka"):** a click on a cell of
  any title block (A … E, Modern, Modern strip) lays a text box over it — its place, size and font (SheetEditor.editCell;
  the cell's biggest text gives the font); Enter or a click elsewhere keeps it, Esc not, Tab / Shift+Tab go along the
  cells. Cells to type into have a text cursor and a light blue outline on hover; computed ones (data-ro: material of
  a part — from its model —, mass, scale, paper, sheet n / N, revision, dates) take no text, their tooltip / the hint
  says where the value comes from. web/js/sheet/tbedit.js holds the table: TB_EDIT {field: propagate} — drawn,
  checked, approved, company, address, tolstd, surface: yes; title, number, note: never; material: only typed on an
  assembly's sheet — and TB_COMPUTED; hitRect() makes every style's cells. After a project-wide field on a sheet of an
  assembly's drawing set (the assembly's or a part's in it), a small question over the title block, not modal:
  "Přepsat i ve všech listech sestavy „X“? (n listů)" Ano / Jen tady, "neptat se znovu" (the field's answer kept for
  the session). Ano keeps it as the set's (setTexts on the top assembly's sheet — made when it has none, as for a
  template — so pages without a sheet of their own show it; every sheet's own text of it taken away); a sheet's own
  text still wins (textsOf: template, set, own). The suggestions' title-block rows open the cell's text box (a field
  the style does not show: the old dialog); the panel fields stay (their placeholder: the set's / template's text)
  and ask the same. AI: sheet_edit texts {…, material} with all_sheets true (only the project-wide ones go; the rest
  "kept on this sheet only"). tools/e2e_title_inline.py (Czech, real mouse / keys: the box over the cell in its font,
  D-100 on the sheet and in the PDF and not asked, Esc, Tab -> Kontroloval and the question, Ano -> all 3 pages of the
  set's PDF say F. Paul, D-100 on one; the mass cell computed; the suggestion row; the panel; the AI; every style).
- **A server older than its checkout says so done:** the app server runs for hours while main moves on. version.head()
  (the checkout's HEAD, `git rev-parse` at most every 30 s; A3D_FAKE_HEAD for tests; '' in the built app) and stale();
  a report's version line says both commits when they differ ("server started at main @ 92d0e37, …; checkout now at
  1e35a8d — restart the app to run it") and the page's commit when it is another one (the page sends it with its AI
  polls: ?build=, server.PAGE_BUILDS). /api/version has head / stale; web/js/stale.js shows a small ⟳ New version —
  restart the app (or — reload the page: the server restarted under an old page) in the top bar, asked every minute
  and on focus. A tool the MCP server lists but the app server does not know: "this app server is older than the tool
  list; restart the app" (the MCP server sends listed: true; it also rewrites an old server's "Unknown tool").
  tests: test_launcher test_moved_head, test_agent test_older_app_server / test_report_says_the_page_build;
  tools/e2e_stale_notice.py.
- **The later list is done.** Ideas for after it (each to be kept simple, ≤ 2 inputs): ~~hole / sketch distances from
  round faces (a shaft's axis)~~ (done); ~~dimensions of hole positions drawn on the 2D drawing (not only listed)~~ (done); joint types in
  assemblies beyond face-on-face (axis on axis for pins in holes); a sketch mirror line; draft angle on extrudes.
  round faces (a shaft's axis)~~ (done); dimensions of hole positions drawn on the 2D drawing (not only listed); joint types in
  assemblies beyond face-on-face (axis on axis for pins in holes); a sketch mirror line; ~~draft angle on extrudes~~ (done).

## 0. Summary

- **Goal.** Add a new **"3D model"** workspace. You draw 2D sketches with dimensions, then 3D tools (extrude, revolve, hole, fillet, shell, pattern) turn them into a solid, step by step, as in Solid Edge or SolidWorks. Every step is plain JSON, so the AI can build and edit models with the same tools the user has. Light assemblies come later. The current tools stay: picture → outline, the cookie-cutter and solid presets, PDF drawings, design layers, bends and 3D print (printer fit, splitting, joints).
- **Kernel decision: option (c), a hybrid.**
  - The current z-slab kernel (`auto3d/solid.py`) stays unchanged. It still runs the Part, 3D design and 3D print tabs.
  - The new workspace uses a real CAD kernel, **OpenCASCADE**, through the `cadquery-ocp-novtk` wheel.
  - Sketches are solved by **planegcs** (the FreeCAD sketch solver).
  - Both new packages are **optional**. Without them the app works exactly as it does today. The new tab then shows an "install" hint.
- **One project, many documents.** A project file becomes a small library of parts and assemblies. A "classic" part (today's kind: PDF, picture, DXF, STL) can be used inside a 3D model as a body or as a sketch. A 3D model part can be sent to the 3D print tab.
- **AI.** The MCP server gets new tools for sketches, features, assemblies and topology. Skills ship as a small Claude Code plugin loaded with `--plugin-dir`. The same texts are also served by an MCP tool (`get_guide`), so Claude Desktop and other clients get them too.
- **Roadmap.** 8 milestones (M0 to M7, plus "later"). Each one can be shipped and tested. Total is about 16–20 weeks for one developer working with AI help.

### Words used in this document

- **B-rep** (boundary representation): a solid stored as its exact faces (flat, cylinder, cone…), the edges between them and the corners. Because the edges really exist, you can pick an edge and round it, and STEP files keep true circles. Today the app stores solids as stacks of flat slices instead.
- **Constraint solver**: a program that moves the points of a sketch so that all rules are true at the same time. Examples of rules: "this line is horizontal", "this length is 40 mm", "this arc touches that line".
- **Feature**: one modelling step (sketch, extrude, fillet…). The **feature tree** is the ordered list of steps. **Rollback** means "show the model as it was after step N".
- **Topological naming**: how a feature remembers *which* face or edge it uses after earlier steps change. See risk R1.
- **Datum**: a fixed reference plane or axis (XY, XZ, YZ, Z axis…).
- **Mate**: an assembly rule between two parts, for example "these two faces touch".

---

## 1. What the current kernel can and cannot do (evidence)

**How it works today** (`auto3d/solid.py`):
- A solid is a list of `(z0, z1, section)` slabs. Each slab has a constant 2D shapely cross-section.
- `csg(ops)` only accepts `(op, region, z_from, z_to)`. In other words, it can only combine prisms that run along **Z** (solid.py lines 160–184).
- Faces are only horizontal caps and vertical walls (solid.py lines 1–12, `faces()` from line 258).
- STEP export writes only `PLANE` faces (export.py lines 1–4). The README already says that exact cylindrical faces "would need a CAD kernel" (README, bending section).
- Round holes are *guessed* by fitting circles to slab sections (`features()` / `_fit_circle`, line 378 on).
- Curved or slanted imports become stairs (`meshpart.py` lines 104–109, `importers.slice_mesh`).
- Printing and joints depend on slabs: `material_between`, `clipped`, `clipped_layers`, `carved` (printing.py lines 185 and 245, joints.py line 183).

| Modelling need | Slabs today | With option (a): slabs + sketch planes on X/Y/Z |
|---|---|---|
| Extrude along Z from the bed or a top face | exact | exact |
| Holes and pockets from the top | exact | exact |
| Round a vertical edge (2D corner rounding of the section) | possible | exact |
| Extrude or hole from the **side** (X or Y direction) | impossible | only as stairs (slices along Z) |
| Revolve (knob, bottle, wheel) | impossible | stairs only |
| Fillet or chamfer of a horizontal or top edge | impossible | stairs only |
| Shell of a non-prismatic part | impossible | impossible |
| Angled plane, draft, loft, sweep | impossible | impossible |
| STEP with true cylinders | no | no |
| Pick an edge and round it | no edges exist | no |

**Conclusion.** Option (a) covers "2.5D Solid Edge": plates, brackets, boxes made from Z-extrusions. It cannot cover "fully model single parts", which you now want. The slab kernel is still very good at what it does (exact booleans, watertight meshes, joints, splitting, design patterns), so we keep it for that.

---

## 2. Kernel options compared (checked on PyPI on 2026-10-25, Python 3.13.7 AMD64)

| Option | Windows / Py 3.13 wheel | Download size | What it brings | Risk |
|---|---|---|---|---|
| **cadquery-ocp-novtk 8.0.1.1.0** (OCCT 8 bindings, no VTK) | yes, `cp313-cp313-win_amd64` (also cp311–cp314) | **47.8 MB** wheel + tiny `cadquery-ocp-proxy`. Installed size is estimated at 150–250 MB; measure it in M0. | Full B-rep: prism, revolve, booleans, fillet, chamfer, shell, draft, loft, sweep, exact STEP read/write, tessellation, mass properties, exact distances, sections | Large install. Some OCCT calls can fail or even crash the process, so run it in a worker process (see 7.2). The API is low-level, so we write our own thin wrapper. |
| build123d 0.13.0 (pure Python, uses the above) | yes (py3-none-any) | 0.4 MB itself, **but** pulls in scipy (36.6 MB), scikit-learn (8.2 MB), sympy (6.3 MB), ipython, ocpsvg, lib3mf and **threejs-materials (89.8 MB)** | Nice API (selectors, fillet helpers) | About 200 MB of extra packages we do not need, more version pins, and it makes `requirements` fragile. **Rejected.** We can copy *ideas* from it. |
| cadquery 2.8.0 | yes | Needs `cadquery-ocp<8.0` **with VTK (80 MB)**, plus casadi, nlopt, trame, numba | Same kernel, heavier | **Rejected.** Heaviest option, and it pins the older OCCT 7.9. |
| manifold3d 3.5.4 (mesh CSG) | yes, 1.0 MB | 1 MB | Very fast, robust mesh booleans, extrude, revolve | No real edges or faces (no edge fillet, no shell), STEP only as facets, and no face topology for picking. Good for "quick STL", not for "like SolidWorks". **Not the main kernel.** Possible later helper. |

**Already installed:** `cascadio 0.1.1` (16.9 MB) contains its own copy of OCCT and is used for STEP import. In M0, test that `import cascadio` and `import OCP` work together in one process. Later, STEP import can move to OCP and `cascadio` can become optional.

### 2D constraint solver

| Candidate | Py 3.13 Windows | License | Notes |
|---|---|---|---|
| **planegcs 0.9.6** | yes, 0.6 MB (cp312–cp314) | LGPL-2.1+ | The FreeCAD Sketcher solver (proven core), with new Python bindings (released 2026-10-10). Points, lines, circles, arcs, all common constraints. |
| python-solvespace 3.0.8 | **no cp313 wheel** (stops at cp311) | GPL-3 | Rejected: will not install on our Python. |
| py-slvs 1.0.6 | yes | **GPL-3**, last release 2023 | Rejected: license risk if the app is shared, and not maintained. |
| Our own (extend `solver.py`) | — | — | Today it only solves axis-aligned "levels" in a tree. Angles, tangency, circles and loops of constraints would mean writing a Newton solver. Too much work and too risky. |

**Do we need a solver at all? Yes.** Without one, sketches are just fixed coordinates, like today's 2D shapes. Dimensions would not *drive* the geometry, and changing a number would not update the part. A driving dimension is the heart of the Solid Edge workflow.

**Recommendation.** Wrap planegcs in `auto3d/modeler/constraints.py`, so it could be replaced later. If planegcs is missing, sketches still work with fixed coordinates; dimensions are shown but do not drive anything, and a hint says so.

### Recommendation: option (c), hybrid

```
                       ┌────────────── classic parts (unchanged) ──────────────┐
PDF / picture / DXF /  │ sketch.py / outline.py / meshpart.py → Solid (slabs)   │──► Part, 3D design, bends,
STL (today)            │ design layers, bends, joints, split, export (planar)   │    3D print (as today)
                       └──────────────────────────┬─────────────────────────────┘
                                                  │ "use in 3D model"
                                                  ▼  (slabs → our own STEP → OCP shape, exact, no new code)
                       ┌────────────── 3D model parts (new) ───────────────────┐
sketches (planegcs) ──►│ feature tree → OCP B-rep (worker process, cached)     │──► mesh + face/edge ids (viewer)
                       │ extrude, revolve, hole, fillet, shell, pattern …       │──► exact STEP / STL / 3MF
                       └──────────────────────────┬─────────────────────────────┘
                                                  │ "print / split" (the STEP as a quick part)
                                                  ▼  (slices → printing.plan: where to cut, fit, joints)
                                         3D print tab: fit, split, joints — the pieces cut from the exact
                                         B-rep with the plan's cells / pockets as prisms (printexact.py)
```

Two bridges reuse code that already exists:
- **Slabs → B-rep.** `export.to_step(solid)` already writes a correct planar B-rep. Read those bytes back with OCP's `STEPControl_Reader`, in memory. The result is exact, and there is no new geometry code.
- **B-rep → slabs.** Tessellate the shape, then use `importers.slice_mesh` and `Solid.from_slabs`. This is the same path as the STL import today.

---

## 3. Tool list for quick part modelling

MVP = in the first usable version (M1–M4). Later = after M7, or only if users ask for it.

> **Owner's rule (2026-10-25): it has to be intuitive and really easy to use. If a tool is complicated for
> the user — for example it needs lots of inputs — do not add it yet.** This rule overrides the tables
> below. In practice:
> - A tool may ask for **at most two things** (one pick + one number, or two picks). Everything else gets a
>   good default and is not shown.
> - Every tool must work with its defaults right away, show a live preview, and be undoable.
> - An empty screen always says what to do next and offers the one obvious button.
>
> So, for now:
> - **Extrude**: only distance plus add / cut (cut is picked automatically when the sketch is on the part).
>   "Symmetric" is a single checkbox. (Since done, each one control: "Up to a face", "Up to next" and "＋ Other
>   side" — the second direction as one more distance.)
> - **Hole**: click a point on a face and give a diameter. It goes through by default. Counterbore,
>   countersink, size tables and teardrop are deferred. (Since done: heads, threads and teardrop, one control each.)
> - **Chamfer**: one distance only. **Fillet**: pick edges and give a radius.
> - **Shell**: pick the face to open and give the wall thickness.
> - **Patterns**: count only; the spacing follows from the part. Even simpler is "repeat N times along an
>   edge". Deferred until the basics feel easy.
> - **Sketch constraints**: mostly automatic while drawing, plus dimensions you type. No constraint
>   toolbox at first.
> - **Reference planes**: "sketch on a face" covers most needs. Offset and angled planes are deferred.
> - **Assemblies**: insert a part and snap it face to face only.
>
> Each milestone is reviewed against this rule before it ships (count the clicks; ask "would a
> first-time user know what to do here?").

### 3.1 Sketch

| Tool | Purpose | Inputs | When |
|---|---|---|---|
| Sketch on datum plane | Start a sketch on XY / XZ / YZ | plane | MVP (M1) |
| Sketch on face | Sketch on a flat face of the part | picked planar face (named reference) | MVP (M3) |
| Sketch on offset / angled plane | via reference planes (3.3) | plane feature | MVP (M3) |
| Line / polyline | Chain of lines | clicks; auto H/V/coincident | MVP (M2) |
| Rectangle | 2-corner and centre rectangle | 2 clicks | MVP (M1 as numbers, M2 drawn) |
| Circle | Centre + radius | 2 clicks | MVP (M1/M2) |
| Arc | 3-point and centre-start-end; tangent arc from a line end | clicks | MVP (M2), tangent arc in M3 |
| Polygon | Regular n-gon (hex nuts!) | centre, radius, n, inscribed/circumscribed | MVP (M2) |
| Slot | Straight slot | 2 centres + width | Done (⊂⊃ Slot: centres, then the width) |
| Point | For holes and construction | click | MVP (M2) |
| Construction toggle and centreline | Helper geometry, revolve axis, mirror line | entity | MVP (M2) |
| 2D fillet / chamfer | Round or cut a sketch corner (adds arc + tangency) | corner, r / d | MVP (M2) |
| Trim | Cut a segment back to the nearest crossings | click on segment | MVP (M2) |
| Extend | Extend a line up to the next entity | click | Done (lines; the end gets an "on" constraint) |
| Offset | Copy a loop at a distance (linked: it follows its original; ⛓ Unlink = one-off) | loop, distance, side | MVP (M2); linked offset done |
| Mirror | Mirror entities about a line, adding symmetric constraints | entities, line | MVP (M2) |
| Sketch pattern | Linear / circular copies inside the sketch | entities, count, step | Done (⁂ Pattern: a `pat` relation, the copies follow) |
| Project edges ("Include" / "Convert entities") | Bring part edges into the sketch | picked edges | MVP (M3) |
| Outline / DXF / PDF block | A traced outline, DXF region or PDF profile as one rigid block (position, angle, scale dimension) | asset + width | MVP (M4) |
| Text | Text traced into a block (reuses today's browser text tracing) | text, height | Done (𝐓 Text) |
| Spline | Free curve | points | Done (〰 Spline) |
| **Constraints** | coincident, horizontal, vertical, parallel, perpendicular, tangent, equal, fixed, concentric, midpoint, symmetric, point-on-curve | picked entities | MVP (M2), all supported by planegcs |
| **Dimensions** | distance (aligned / horizontal / vertical), radius / diameter, angle; driving or reference; value may be an expression using parameters (`w/2+3`) | picked entities, value | MVP (M2) |
| Auto-constraints while drawing | H/V/coincident/tangent guessed from snapping. This is what makes sketching *quick*. | — | MVP (M2) |
| Status (degrees of freedom) | "Fully defined" vs "2 free"; free entities shown in blue | — | MVP (M2) |

### 3.2 Features

| Feature | Purpose | Inputs | When |
|---|---|---|---|
| Extrude | Push a sketch region out | sketch, regions (default: all closed), op = new / add / cut / intersect, extent = blind / symmetric / through all / up to face / up to next, flip, 2nd direction | Done: blind, symmetric, through, up to face (+ offset), up to next, ＋ other side (d2, blind) |
| Revolve | Spin a sketch around an axis | sketch, axis (centreline or datum axis), angle, op | MVP (M3) |
| Hole | Proper holes on a face | face, sketch points, type = simple / counterbore / countersink, size from a table (M2–M12, with print clearance), depth or through, **teardrop** option for horizontal holes (printable without support) — done: `teardrop: true` | MVP (M3) |
| Fillet | Round edges | edges (named references), radius | MVP (M3) |
| Chamfer | Bevel edges | edges, distance, or distance + angle | MVP (M3) |
| Shell | Hollow a part | faces to remove, wall thickness | MVP (M3) |
| Linear pattern | Repeat features or a body | features or body, direction (edge / axis), count, spacing | MVP (M3) |
| Circular pattern | Repeat around an axis | features or body, axis, count, angle | MVP (M3) |
| Mirror | Mirror features or a body | plane / planar face | MVP (M3) |
| Combine bodies | Add / subtract / intersect body B with body A | 2 bodies, op | MVP (M3) |
| Move / rotate body | Place a body | body, translate, rotate | MVP (M3) |
| Insert part / import | A classic part, STEP or STL as a body | source reference, placement, op | MVP (M4) |
| Draft | Angle walls for moulds | faces, neutral plane, angle | Done (⟋ Draft: an extrude's walls, the angle) |
| Loft | Shape between 2+ sketches | sketches | Done (⧫ Loft) |
| Sweep | Profile along a path | sketch + path sketch | Done (〰 Sweep) |
| Decorate face | Today's design layers (patterns, logos) on any **planar face** of a model part, embossed or cut along the face normal | face, layer JSON | Later (M8). Easy, because `design.layer_regions` already makes shapely regions. |
| Thread, rib, split body | — | — | Thread (hole M2 … M20, labelled on drawings), ⊿ Rib and ✂ Split body (plane, keep both / one side) done |

### 3.3 Reference geometry

| Tool | Inputs | When |
|---|---|---|
| Datum planes XY / XZ / YZ, axes X / Y / Z, origin | built in | MVP (M1) |
| Offset plane | plane or face, distance | MVP (M3) |
| Angled plane | plane + edge / axis, angle | MVP (M3) |
| Mid plane | two parallel faces | Done (⇳ Midway, a sketch's plane {face, mid}) |
| Axis | cylinder face, or 2 points, or 2 planes | MVP (M3): cylinder and 2 points |
| Point | vertex, centre of circle | Done (• Point: a corner, a round edge's centre, an edge's middle) |

### 3.4 Feature tree

| Function | When |
|---|---|
| Ordered list: origin → sketches → features; icons; error and warning badges with the reason | MVP (M1) |
| Edit (re-opens the command with its values), rename, delete (warns about dependants) | MVP (M1–M3) |
| Suppress / unsuppress | MVP (M3) |
| Rollback bar (drag, or "Roll to here"); new features go in at the bar | MVP (M3) |
| Parameters table (name, expression, value), shared by all sketches and features | MVP (M2) |
| Reorder by drag | Done (refused when a step needs one after it; undone if it fails) |

### 3.5 Inspect

| Tool | Inputs | When |
|---|---|---|
| Measure (exact distance / angle / radius between faces, edges, vertices) | 1–2 references | MVP (M6). Today's measure tool keeps working on classic parts. |
| Mass properties: volume, area, mass, centre of mass | body + material | MVP (M6) |
| Materials: PLA 1.24, PETG 1.27, ABS 1.04, ASA 1.07, TPU 1.21, PA 1.14 g/cm³; infill % as an estimate | per part | MVP (M6) |
| Section view: clipping plane with a capped cut | plane, offset | MVP (M6) |
| Printability: faces overhanging more than 45° highlighted, thin walls | body | Done (🖨 Print check, check_print) |

### 3.6 Assemblies (keep it light)

| Tool | Inputs | When |
|---|---|---|
| Assembly document; insert a part from the project library or from a file | part id, placement | M7 |
| Ground (fix) an instance | instance | M7 |
| Mates: coincident (plane–plane, with flip), concentric (axis–axis), distance (plane–plane offset) | 2 references + value | M7 |
| Exploded view: per-instance offset steps, with a slider | instance, vector | M7 — slider done; 💥 per part (`instance.stay`: held parts stay, the others move away from their middle) |
| BOM (parts list): part, quantity, material, mass | — | M7 |
| Export: assembly STEP (several bodies), or "print all parts" (each to the print tab) | — | M7 |
| Angle / parallel / tangent mates, interference check, motion | — | Done (joints by face kind, clashes, motion with limits) |

**Cut, to stay "quick creation":**
- no 2D drawing sheets
- no surfacing
- no sheet metal (classic bends stay)
- no configurations or design tables (only global parameters)
- no in-context editing of parts inside an assembly
- no motion study
- no 3D sketches
- no full topological naming (see R1)
- no feature reordering at first
- no rendering

---

## 4. Sources and sharing parts across the app

### 4.1 How today's pieces feed the modeller

| Today | In the 3D model workspace | How |
|---|---|---|
| Picture wizard (outline.js / outline.py), with its candidates and hand edits | **Sketch block** "Outline from picture": rigid, with a width/height dimension, re-editable in the same wizard | `outline.scaled_outline` + `clean_outline` → rings (mm) → block entity. The wizard gets a third button next to *Apply to the part*: **Use as sketch in 3D model**. |
| Presets (cookie cutter, solid) | Unchanged in the Part workspace. Can be **inserted as a body** into a model (for example a cutter with an added modelled handle). | Classic part → `_solve_full` → `to_step` → OCP read |
| PDF drawing (parametric) | (1) stays a classic part; (2) **"Use profile as sketch"**: a linked block whose loops follow the PDF dimensions; (3) insert the whole PDF part as a body | the profile comes from `solver.solve` / `profile_polygon` |
| DXF / DWG | Sketch block (real size), **or** a classic part as today | `importers.read_dxf` polygons |
| STEP | **Exact B-rep body** (new, through OCP). Faces can be picked and filleted. | `STEPControl_Reader` |
| STL / OBJ | **Mesh body**: shown, measured, used in assemblies and printing. Booleans only after "convert to solid" (OCCT sewing; allowed up to about 50k triangles, with a warning). | `importers.read_mesh` |
| Design layers | Classic parts only. Later: the "Decorate face" feature on planar faces of model parts. | `design.layer_regions` |
| Bends | Classic parts only. Model parts use real geometry (revolve, angled planes). | — |
| 3D print (fit, split, joints) | Works on any part. Model parts (their STEP as a quick part): the slices plan the split with `printing.plan` and `joints` unchanged; the pieces are cut from the exact B-rep, the joints built as B-rep prisms from the same shapely polygons (done: `printexact.py`, `modeler/printsplit.py`). STL / OBJ parts, parts with 3D objects, no kernel: the slab pieces. | `slice_mesh` + `Solid.from_slabs`, `kernel.prisms` |
| Print orientation | **New, needed for model parts**: "Place on bed: pick a face". The slab pipeline assumes Z up. | rotation feature applied at print time only |

### 4.2 Project file v3 (today's files are already `version: 2`, see app.js line 1585)

The project becomes a library: `parts[]` (classic or model), `assemblies[]`, and shared `assets{}`. Big data (pictures, imported files, PDFs) lives in `assets` once and is referred to by id. That keeps undo snapshots and rebuild requests small.

```json
{
  "app": "Auto3DModeler", "version": 3, "project_name": "Shelf bracket",
  "unit": "mm",
  "active": {"doc": "P2", "workspace": "model"},
  "assets": {
    "A1": {"type": "image", "name": "pernicek.png", "data": "data:image/png;base64,..."},
    "A2": {"type": "mesh",  "name": "clip.stl", "data": "<base64>", "mesh_id": "<server hash>"},
    "A3": {"type": "pdf",   "name": "initial draft.pdf", "data": "<base64>"}
  },
  "parts": [
    {"id": "P1", "kind": "classic", "name": "Cookie cutter",
     "classic": { "...": "today's v2 payload: model, preview, values, userSet, layers, bends, snap, original, outline_editor, import_file, layer_pictures" }},
    {"id": "P2", "kind": "model", "name": "Bracket", "material": "PETG",
     "params": [{"id": "w", "name": "Width", "expr": "80"}, {"id": "t", "name": "Wall", "expr": "3"}],
     "rollback": null,
     "features": [
       {"id": "F1", "type": "sketch", "name": "Base sketch", "plane": {"datum": "XY"},
        "points":   {"v1": [0, 0], "v2": [80, 0], "v3": [80, 40], "v4": [0, 40]},
        "entities": [{"id": "e1", "t": "line", "p": ["v1", "v2"]}, {"id": "e5", "t": "circle", "c": "v9", "r": 4, "construction": false},
                     {"id": "b1", "t": "block", "source": {"asset": "A1", "outline": "<polygons>", "editor": {}}, "at": [10, 5], "rot": 0, "width": "30"}],
        "constraints": [{"id": "c1", "t": "horizontal", "e": ["e1"]}, {"id": "c2", "t": "distance", "e": ["v1", "v2"], "value": "w"}]},
       {"id": "F2", "type": "extrude", "sketch": "F1", "regions": "all", "op": "new",
        "extent": {"type": "blind", "d": "t"}, "flip": false},
       {"id": "F3", "type": "sketch", "plane": {"face": {"feature": "F2", "role": "end"}}, "...": "..."},
       {"id": "F4", "type": "hole", "sketch": "F3", "points": ["v1"], "kind": "counterbore", "size": "M4", "depth": {"type": "through"}},
       {"id": "F5", "type": "fillet", "edges": [{"feature": "F2", "role": "side", "entity": "e2", "fp": {"c": [80, 20, 1.5], "len": 40}}], "r": "2"},
       {"id": "F6", "type": "insert", "source": {"part": "P1"}, "place": {"t": [0, 0, 3], "r": [0, 0, 0]}, "op": "add"},
       {"id": "F7", "type": "insert", "source": {"asset": "A2"}, "op": "new"}
     ]},
    {"id": "P3", "kind": "model", "name": "Pin", "features": []}
  ],
  "assemblies": [
    {"id": "S1", "name": "Shelf",
     "instances": [{"id": "I1", "part": "P2", "fixed": true,  "place": {"t": [0, 0, 0], "r": [0, 0, 0]}, "explode": [0, 0, 0]},
                   {"id": "I2", "part": "P3", "fixed": false, "place": {"t": [20, 10, 0], "r": [0, 0, 0]}, "explode": [0, 0, 20]}],
     "mates": [{"id": "M1", "type": "concentric", "a": {"inst": "I2", "ref": {"feature": "F2", "role": "side", "entity": "e1"}},
                "b": {"inst": "I1", "ref": {"feature": "F4", "role": "hole", "index": 0}}},
               {"id": "M2", "type": "coincident", "a": {"inst": "I2", "ref": {"feature": "F2", "role": "start"}},
                "b": {"inst": "I1", "ref": {"feature": "F2", "role": "end"}}, "flip": true}]}
  ]
}
```

**Ids.**
- Parts use `P…`, assemblies `S…`, instances `I…`, mates `M…`, features `F…`, sketch points `v…`, sketch entities `e…` / `b…`, constraints `c…`, assets `A…`.
- Ids are unique inside their container and never reused, so references stay valid after deletes.
- Use the existing `newId` style from outlinepanel.js.

**References between features.**
- A feature refers to an earlier feature by id (`"sketch": "F1"`).
- A face or edge is a **named reference**, not an index: `{feature, role, entity?, index?, fp}`.
  - `role` comes from how the face was made. Extrude gives `start` / `end` / `side` (+ the sketch `entity` that swept it). Revolve gives `side`, `cap_start`, `cap_end`. Hole gives `hole` / `cbore`. Fillet gives `round`.
  - `fp` (fingerprint) stores the centre, normal, type, area or length, so the kernel can re-find the face if the name no longer matches.
- Parameters are referred to by id inside expressions (`"w/2"`).
- Expressions are evaluated on the server with a tiny safe evaluator: numbers, + − × ÷, parentheses, parameter ids. No `eval`.

**Migration** (`auto3d/project.py`):
- `migrate(proj) -> v3`. A file with `version` 1, 2 or none is wrapped as a single classic part `P1`, holding all of today's fields verbatim.
- `import_file` and pictures move to `assets`. The classic payload keeps a pointer, so `loadParsed` still gets exactly what it gets today.
- The client calls `POST /api/project/migrate` when opening a file. There is one implementation, and it has unit tests.
- Saving always writes v3.
- "Export classic part as v2" can be kept for sharing with older versions. That is optional.

### 4.3 API endpoints (new)

The server stays the single source of truth for geometry. The client sends the part JSON, as `/api/solve` does today. The server caches OCCT shapes by a hash of "features up to N" (inside the worker), so editing feature 7 does not rebuild features 1–6.

| Endpoint | Body → result |
|---|---|
| `GET /api/kernel` | → `{occ: "8.0.1" or null, gcs: "0.9.6" or null, install_hint}` |
| `POST /api/project/migrate` | any project → v3 project |
| `GET /api/jobs`, `POST /api/jobs/<id>/cancel` | What runs now (kernel jobs and slow requests: id, kind, what, worker, state, elapsed, stage) for the top bar's ⚙ list; ✕ Stop of one (404: ended). |
| `POST /api/model/rebuild` | `{part, assets_ids, rid, need: ["mesh","topology"], parts: {id: classic payload} for inserts}` → `{ok, bodies: [{id, mesh (base64 positions), face_of_tri (uint32), faces: [{ref, type, normal, centroid, area, radius?}], edges: [{ref, type, polyline, length, radius?}], bbox, volume}], features: [{id, ok, issues, reattached?}], params: {id: value}}`. Uses `progress.operation(rid)`, so the existing progress bar and Cancel work. |
| `POST /api/model/sketch/solve` | `{sketch, params, drag?: {point, to}}` → `{points, status: ok / over / conflict, dof, free: [...], conflicts: [...]}` |
| `POST /api/model/measure` | `{part, a: ref, b: ref}` → distance / angle / radius, closest points |
| `POST /api/model/section` | `{part, plane}` → section outlines for capping |
| `POST /api/model/mass` | `{part, material, infill?}` → volume, area, mass, centre of mass |
| `POST /api/model/export/<stl|step|3mf>` | `{part}` or `{assembly}` → file |
| `POST /api/model/to_slabs` | `{part, layer?, bed_face?}` → used internally by print endpoints for model parts |
| `POST /api/print/plan`, `/api/export/*` | **extended**: accept `{doc: {kind: "model", part}}` besides today's body; dispatch in a new `_solid_for(body)` next to `_solve_full` |
| `POST /api/assembly/solve` | `{assembly, parts}` → instance transforms + mate status |
| `POST /api/assembly/bom` | → rows |

---

## 5. User interface

### 5.1 Workspaces

A **workspace switch** sits in the top bar, left of the file name:

`[ Quick part ] [ 3D model ] [ Assembly ]`

- **Quick part** = today's UI, unchanged: left Dimensions / Checks / Drawing / AI, right Part / 3D design / 3D print. It works on the active *classic* part.
- **3D model** = the new workspace, for the active *model* part.
- **Assembly** = M7.
- A **Project panel** (a dropdown under the file name, or a narrow strip at the top of the left panel) lists all parts and assemblies, with an icon, name and kind. A click opens the part in its workspace. A right-click gives: rename, duplicate, delete, "Use in 3D model", "Send to 3D print", "Insert into assembly".
- The **open buttons stay**. *Open picture / PDF / CAD* create a new classic part (as today). The wizard, the Part tab and the Drawing tab also get **"Use as sketch"** / **"Use as body"** buttons, which add to the open model part, or to a new one.
- **3D print** and **✨ AI** are shared. They work on whichever document is active.

### 5.2 Layout of the 3D model workspace (Solid Edge / SolidWorks style)

```
┌ top bar: brand · [Quick part|3D model|Assembly] · project ▾ · Open… · Save · Export ▾ · CZ ┐
├ command bar (changes with mode) ──────────────────────────────────────────────────────────┤
│ Part mode:   Sketch ▾ | Extrude  Revolve  Hole  Fillet  Chamfer  Shell | Pattern ▾ Mirror │
│              | Plane ▾ Axis | Measure  Section  Mass | ↶ ↷ | selection filter: ◻face ╱edge •vertex ▣body │
│ Sketch mode: Line Rect▾ Circle Arc▾ Polygon Slot Point | Fillet Trim Offset Mirror Project │
│              | Constraints ▾ Dimension | Construction | ✓ Finish sketch  ✕ Cancel   │
├──────────────┬───────────────────────────────────────────────┬──────────────────────────┤
│ Feature tree │                                               │ Property panel           │
│  ⌂ Origin    │            three.js viewport                  │ (active command: inputs, │
│  ▭ Sketch 1  │   (sketch mode: looks straight at the plane,  │  references to pick,     │
│  ⬆ Extrude 1 │    grid, snapping marks, constraint glyphs,   │  live preview, OK/Cancel)│
│  ○ Hole 1  ⚠ │    editable dimension labels like today)      │ idle: selection info /   │
│ ── rollback ─│                                               │ parameters               │
│  ◜ Fillet 1  │   view cube · std views · section toggle      │ tabs: Properties |       │
│ Parameters ▸ │                                               │       3D print | ✨ AI   │
├──────────────┴───────────────────────────────────────────────┴──────────────────────────┤
│ status: "Sketch 1 — fully defined" / "2 degrees of freedom" · hint for the active command│
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

**Workflow (as in Solid Edge ordered mode):**
1. Click *Sketch*, then pick a plane or face. The camera turns to face it.
2. Draw. Auto-constraints appear as you draw. Click an entity, then *Dimension*, and type a value or an expression.
3. *Finish sketch*.
4. *Extrude*. The sketch is pre-selected; the property panel shows distance, direction and op, with a live preview. Click OK.
5. Pick faces or edges for hole, fillet or shell.
6. Double-click a tree item (or a dimension on the model) to edit it.

**Keyboard:** S sketch, E extrude, R revolve, H hole, F fillet, D dimension, L line, C circle, Esc cancel / finish, Delete, Ctrl+Z / Ctrl+Y.

### 5.3 Picking faces, edges and vertices

- The server sends each body's triangles with `face_of_tri` (one face id per triangle), plus edge polylines and vertices, each with its named `ref`.
- Face pick: raycast the mesh → triangle → face id → highlight that face's triangles.
- Edge and vertex pick: nearest edge polyline or vertex on screen within 8 px. This is the same idea as the corner snapping in `viewer.pickSurface`.
- The selection filter limits what can be picked. Commands set the filter automatically (Fillet → edges, Shell → faces).
- Hover highlight with a small label ("Edge · Extrude 1 · line e2 · 40 mm"). Ctrl+click adds to the selection. A pick on a face while Fillet is active means "all edges of this face" (Solid Edge behaviour).
- Code: a new `web/js/modeler/pick.js`. Reuse the helper patterns from `viewer.js`, but do not overload `Viewer`. Use a subclass, or a second `Viewer` instance in the model workspace container.

### 5.4 Undo / redo

- Move today's `history` object (app.js lines 38–108) into `web/js/history.js` as a small class: `new History({capture, restore, key})`.
- Quick part uses it exactly as now. Each model part and assembly gets its own instance. Its capture is `{features, params, rollback}`; assets are left out because they do not change.
- Each command OK, each sketch "Finish", each AI tool call = one step. Inside sketch mode there is a local sketch history (each drawn entity or constraint is a step), merged into one model step at *Finish*.
- Switching documents keeps each document's history. Opening a new project resets all histories (same as today).

### 5.5 Translations (CZ / EN)

- `web/js/i18n.js` translates by exact text, so **every new label, tooltip, hint and message must be added to `CS` / `CS_PATTERNS`**.
- To keep the 565-line file manageable, put modeller texts in `web/js/i18n_modeler.js` (an exported object). Spread it into `CS` and `CS_PATTERNS` in i18n.js. The mechanism does not change.
- Extend `tools/e2e_i18n.py` to walk the model workspace, sketch mode and every command panel.
- Proposed Czech terms (SolidWorks / Solid Edge CZ usage):

| EN | CZ |
|---|---|
| Sketch | Skica |
| Extrude / Cut extrude | Vysunutí / Vysunutý řez |
| Revolve | Rotace |
| Hole | Díra |
| Fillet | Zaoblení |
| Chamfer | Zkosení |
| Shell | Skořepina |
| Linear / circular pattern | Lineární / kruhové pole |
| Mirror | Zrcadlení |
| Plane / axis | Rovina / osa |
| Feature tree | Strom prvků |
| Rollback | Vrácení stromu |
| Suppress | Potlačit |
| Constraint | Vazba |
| Dimension | Kóta |
| Construction line | Konstrukční čára |
| Fully defined | Plně určená |
| Parameters | Parametry |
| Assembly | Sestava |
| Mate | Vazba sestavy |
| Exploded view | Rozložený pohled |
| BOM | Kusovník |
| Part library | Knihovna dílů |
| Body | Těleso |
| Through all | Skrz vše |
| Symmetric | Symetricky |
| Up to face | K ploše |
| Up to next | K další ploše |
| Other side | Druhá strana |

---

## 6. AI integration

### 6.1 New MCP tools (in `auto3d/agent_tools.py`)

These follow today's pattern. Editing tools run in the browser (`where: "browser"`), so every change is visible and undoable. They call the server to rebuild and return the result. A short, generic set keeps the prompt small. Detailed schemas live in the guides (6.3).

**Documents**
- `list_documents` → parts and assemblies (id, name, kind, active)
- `open_document(id)`, `new_part(name, material?)`, `new_assembly(name)`

**Read and reason**
- `get_model` → params (expr, value); features (id, type, name, ok, issues, key values); bodies (bbox, volume, mass); rollback. Replaces `get_part` for model parts. `get_part` stays for classic parts.
- `get_sketch(id)` → points, entities, constraints, dof, status, conflicts
- `find_refs(query)` → named references, with type, centroid, normal, radius, area, length. Query examples: `{kind: "face", normal: [0,0,1], extreme: "max"}` (top face), `{kind: "edge", of_face: ref}`, `{kind: "edge", circular: true, radius: 2}`, `{kind: "face", feature: "F4"}`, `{near: [x,y,z]}`. **This is how the AI picks faces without guessing indices.**
- `measure(a, b)`, `get_mass(material?)`
- `get_screenshot(view, highlight?: [refs], section?)` (extended)

**Sketch**
- `create_sketch(plane: datum | face ref | plane feature, name?)` → id
- `sketch_add(sketch, entities: [...])`, in a batch: line, polyline, rect, circle, arc, polygon, slot, point, construction flag → entity ids
- `sketch_constrain(sketch, constraints: [...])`, in a batch, incl. dimensions with expressions → dof, status
- `sketch_edit(sketch, ops)`: move / delete / trim / offset / mirror / fillet2d
- `sketch_from_outline(sketch, candidate | asset, width?)`: uses the last `trace_picture`
- `finish_sketch(sketch)` → validates closed regions; lists regions with ids and areas

**Features**
- `add_feature(type, ...)`, where type = extrude / revolve / hole / fillet / chamfer / shell / pattern_linear / pattern_circular / mirror / plane / axis / combine / move / insert → id + rebuild result
- `edit_feature(id, fields)`, `suppress_feature(id, on)`, `delete_feature(id)`, `rollback_to(id | null)`
- `set_parameters({name: expr})`

**Assembly (M7)**
- `insert_part(assembly, part, place?)`, `add_mate(type, a, b, value?, flip?)`, `explode(instance, vector)`, `get_bom`

**Bridges**
- `send_to_print(part, bed_face?)` (then today's `check_print`)
- `export(format, doc?)` (extended to model parts and assemblies, plus 3mf)

**Guides**
- `get_guide(topic)` → the text of a skill (6.3). This is the fallback for clients without skills, such as Claude Desktop.

Also extend `mcp_server.py`:
- Set `instructions` in `initialize` to a short version of the workflow (Claude Code puts MCP server instructions into the system prompt).
- Add `prompts/list` and `prompts/get` that serve the same skill texts. Users can then start them as `/mcp__auto3d__model-a-part` in Claude Code or Desktop.
- Keep it standard-library only.

### 6.2 New `SYSTEM_PROMPT`

Keep it short. Workflows go into skills, which are loaded only when needed and so cost no tokens otherwise. Proposed text:

> You are the design assistant inside Auto3DModeler, a local app for QUICK 3D-printable parts. The user sees the app next to this chat; every tool change appears at once and can be undone.
>
> The project holds parts and assemblies (list_documents).
> - **Classic parts** (Quick part workspace) come from a PDF drawing, a picture outline (cookie cutter / solid / custom objects), a DXF or an STL. Use them for presets and flat decorated parts: get_part, set_make, add_object, add_shape, add_design_layer.
> - **Model parts** (3D model workspace) are built like in SolidWorks: sketches with dimensions and constraints, then features (extrude, revolve, hole, fillet, chamfer, shell, pattern, mirror). Use them for mechanical parts, holes from the side, round parts and fillets.
> - **Assemblies** place parts with mates.
>
> Before modelling a part, load the matching skill (auto3d:model-a-part, auto3d:from-picture, auto3d:from-drawing, auto3d:print-prep, auto3d:assemble, auto3d:edit-imported) or call get_guide(topic) if skills are not available.
>
> Rules:
> - Pick faces and edges with find_refs, never by guessing.
> - Drive sizes with named parameters.
> - Get every sketch to 0 degrees of freedom.
> - Put fillets and chamfers last.
> - After changes, check get_model (all features ok) and get_screenshot before saying it is done.
> - Coordinates: x right, y up, z up from the printer bed, mm.
> - Never open files or the sample on your own; work on what is open, or ask.
> - Use printable defaults (walls ≥ 1.2 mm, hole clearance +0.2 mm, overhangs ≤ 45°) unless told otherwise.
> - Ask only when a decision is really the user's (key sizes, what to make).
> - Answer in the user's language, briefly. Only the listed tools exist — no files or shell.

### 6.3 Skills: where they live and what they say

**Location.** A plugin folder in the repo, loaded for the chat session only:

```
agent_plugin/
  .claude-plugin/plugin.json        {"name": "auto3d", "version": "1.0.0", "description": "Auto3DModeler workflows"}
  skills/model-a-part/SKILL.md
  skills/from-picture/SKILL.md
  skills/from-drawing/SKILL.md
  skills/print-prep/SKILL.md
  skills/assemble/SKILL.md
  skills/edit-imported/SKILL.md
```

Each SKILL.md must be **self-contained** (no extra files). The chat has no Read tool, so it could not open supporting files. `mcp_server.py` reads the same files for `get_guide` and `prompts/*`, so there is one source of truth.

What each skill says (frontmatter `name` + `description` that says *when* to use it, then a body of about 40–80 lines):

- **model-a-part**: "Use when the user wants a new mechanical / functional part."
  1. Clarify purpose, key sizes, printer, material; otherwise use defaults.
  2. `new_part`; `set_parameters` for the key sizes.
  3. Choose the base plane so that the largest flat face lies on the bed (XY, z = 0).
  4. Base sketch centred on the origin, fully constrained, dimensions = parameters.
  5. Base feature (extrude / revolve).
  6. Secondary features on faces found with `find_refs`; use `hole`, not circles, for holes; pattern / mirror instead of repeating.
  7. Fillets / chamfers last; chamfer bed edges rather than filleting them.
  8. Verify: `get_model`, `get_mass`, screenshots iso + side + section through holes.
  9. Report the parameters the user can tweak.

  It also includes a worked example (a wall bracket with 2 countersunk holes and a rib) as a tool-call sequence, and pitfalls: refs re-attached after edits, `regions` when a sketch has nested loops, symmetric extrude for parts centred on a plane.
- **from-picture**: "Use when the user gives a photo / picture."
  1. `trace_picture` → choose a candidate, use hints if none fits.
  2. Decide: a cookie cutter, plaque or stencil → classic `use_outline` with a preset. A part *shaped like* the picture with mechanical features → `new_part`, then `sketch_from_outline` with width, then extrude, then features.
  3. Notches narrower than 2 × wall: use clean-up `close` / `smooth`.
  4. Verify with a screenshot next to the picture.
- **from-drawing**: "Use for PDF / DXF drawings." PDF parametric → classic part (dimensions drive it); offer "use profile as sketch" when 3D features are needed. DXF → sketch block or classic. Check the Checks list for estimated dimensions and ask about them.
- **print-prep**: "Use before export / when the user wants to print."
  - Orientation: place it on the largest flat face (`send_to_print` with `bed_face`).
  - Rules: walls ≥ 2 perimeters, holes +0.2 mm (teardrop if horizontal), overhang ≤ 45°, bridges ≤ 10 mm, emboss ≥ 0.4 mm, text stroke ≥ 0.6 mm.
  - `check_print`; split with joints when too big (which joint for which case).
  - Export STL / 3MF, or STEP for CAD.
- **assemble**: "Use for multi-part designs." New assembly; insert parts; ground the first; mates in order (concentric, then coincident, then distance); check with a screenshot plus an exploded view; BOM; print all parts (each through print-prep).
- **edit-imported**: "Use on STL / STEP the user wants to modify." STEP = exact body, all features allowed. STL = mesh body: measure, insert into assemblies, print; booleans only after converting (warn about size); or rebuild the shape in a model part using measurements.

### 6.4 Do skills load under today's flags? No. Here is what to change.

Today `ChatSession.command()` (agent.py lines 197–212) uses:
`--tools ""`, `--allowedTools mcp__auto3d`, `--setting-sources local`, `--strict-mcp-config`, cwd `data/agent/`.

- Claude Code loads a skill through its built-in **Skill** tool. `--tools ""` removes *all* built-in tools, including Skill, so the model cannot load any skill.
- `--setting-sources local` skips the user and project setting sources. Skills in `~/.claude/skills` and `.claude/skills` are tied to those sources, and the cwd is the empty `data/agent/` anyway. Even with the Skill tool, no app skills would be found. (This is good: the user's personal skills should not leak into the app.)
- Claude Code 2.1.310 (`claude --help`) has `--plugin-dir <path>`: "Load a plugin from a directory or .zip for this session only". It also says "skills still resolve via /skill-name".

**Change in `ChatSession.command()`:**
```
--tools "Skill"                         # only the Skill tool; still no files, no shell
--allowedTools "mcp__auto3d,Skill"
--plugin-dir <repo>/agent_plugin        # our skills only, namespaced auto3d:<name>
(keep) --setting-sources local --strict-mcp-config --permission-mode dontAsk --no-session-persistence
```

**Verify in M5:**
1. Unit test: `command()` contains these flags.
2. The stream-json `system/init` message lists the `Skill` tool and the `auto3d:*` skills. Log it in `translate()`, and show "skills: 6" in the chat status.
3. One `tools/e2e_chat.py` run: "make a 40 mm cube with a 5 mm hole, use your modelling skill". The transcript must show a Skill call.

**Fallback** (if a Claude Code version refuses `--tools Skill`, or for Claude Desktop): the `get_guide` MCP tool, MCP `prompts`, and the richer `instructions`. These always work, because they only use the MCP channel. Do **not** depend on MCP *resources*: reading them in Claude Code also needs built-in tools that `--tools` would remove.

---

## 7. Code layout and main risks

### 7.1 New modules

```
auto3d/modeler/__init__.py     available() → OCP / planegcs present?
auto3d/modeler/kernel.py       THE ONLY file that imports OCP: prism, revolve, booleans, fillet, chamfer, shell,
                               pattern, mirror, tessellate (with face ids), step io, mass, distance, section, sewing
auto3d/modeler/naming.py       named refs: roles from feature history (Generated / Modified / First / Last shape),
                               fingerprints, re-attach with a warning
auto3d/modeler/constraints.py  planegcs adapter (sketch JSON ↔ solver), dof, conflicts
auto3d/modeler/sketch2d.py     sketch → closed regions (shapely for loops; arcs kept as true arcs for the kernel)
auto3d/modeler/doc.py          feature evaluation, expressions, cache by prefix hash, issues per feature
auto3d/modeler/worker.py       a pool of worker processes (a part's jobs on one, in order) holding the caches; timeouts; cancel; crash → restart + error
auto3d/modeler/bridges.py      classic part → shape (to_step → read), shape → slabs (slice_mesh), mesh → body
auto3d/modeler/assembly.py     mates → transforms (small numpy Gauss-Newton on 6 DOF per instance), BOM
auto3d/project.py              v3 schema, migrate()
web/js/history.js              generic undo / redo
web/js/workspace.js            workspace switch + project panel
web/js/modeler/{modeler,tree,commands,props,sketcher,pick,params}.js
web/js/assembly/{assembly,mates}.js
web/js/i18n_modeler.js
agent_plugin/…                 skills
requirements-modeler.txt       cadquery-ocp-novtk==8.0.1.1.0, planegcs==0.9.6   (optional)
```

`server.py` stays thin. It adds a `/api/model/*` blueprint-style section and a `_solid_for(body)` dispatch for print and export.

### 7.2 Risks

| # | Risk | What we do |
|---|---|---|
| R1 | **Topological naming**: fillet edges "jump" after an earlier feature changes | Name faces by role (from OCCT history) + fingerprint. When a reference is re-attached by fingerprint, show ⚠ "reference re-attached — check" on the feature, so the user or AI can confirm. No promise of full robustness (SolidWorks has the same problem). Tests change early dimensions and check that later fillets keep the same edges. |
| R2 | OCCT failure or crash brings down Flask | All kernel calls run in `worker.py` (a pool of processes; a part's jobs always on the same one). An exception becomes a feature issue. A crash means restart the worker and report "kernel crashed while building Fillet 2". Timeout 60 s, with Cancel through `progress`. This also avoids thread-safety problems (Flask runs `threaded=True`). |
| R3 | Install size and failures | Optional extra; `/api/kernel` shows status and the exact `py -m pip install -r requirements-modeler.txt`. Versions are pinned. Note: do not install `cadquery-ocp` (with VTK) next to `-novtk`, because both provide the `OCP` module. |
| R4 | OCCT inside both `cascadio` and OCP in one process | Smoke test in M0. If they clash, load OCP only in the worker process (planned anyway). |
| R5 | Sketch dragging feels slow over HTTP | Local Flask + planegcs: about 5–20 ms per solve. Throttle to one solve in flight (the same pattern as `pump()` in app.js). Later option: a vendored planegcs WASM build. |
| R6 | planegcs bindings are young (0.9.x) | Adapter layer; our own unit tests for each constraint type; pinned version. |
| R7 | app.js is already 1,879 lines | The new workspace lives in its own modules with its own state. app.js only gets: workspace switch hooks, "use in model" buttons, and the save / open of v3. |
| R8 | Splitting model parts for print is approximate at first (stairs on curved walls) | Done: the exact OCCT split (the slab plan's cells and joint pockets as B-rep prisms); the slab pieces stay the fallback (STL parts, no kernel, a kernel failure — with a warning). |

---

## 8. Roadmap (each milestone can be shipped and tested)

Sizes are for one developer with AI help. S ≈ 1 week, M ≈ 2 weeks, L ≈ 3 weeks.

| M | Content | Tests | Size |
|---|---|---|---|
| **M0 Foundations** | `project.py` v3 + migrate + endpoint; save / open v3; project panel (classic parts only, several per project); `history.js` extracted (Quick part behaviour unchanged); `/api/kernel`; `requirements-modeler.txt`; worker skeleton; cascadio + OCP smoke test; measure the install size | `test_project.py`: v2 → v3 round trip on old files, assets dedup. **All existing e2e must still pass** (history, outline_project, unified). New `tools/e2e_project.py`: two parts in one project, switch, save, reload. | S |
| **M1 First body** | `kernel.py`, `doc.py`, `worker.py`; sketch with numeric rect / circle / polyline (no solver yet); extrude blind / symmetric / through, add / cut / new; datum planes; mesh with `face_of_tri`; STL / STEP export of model parts; 3D model workspace skeleton (tree, property panel, Extrude command, rebuild with progress) | `test_modeler_kernel.py` (skip without OCP): box / cylinder / cut volumes against formulas, watertight tessellation (`mesh_stats`), STEP write → read → same volume, prefix cache hit. `tools/e2e_model_basic.py`: new part → rect → extrude → cut → export. | M |
| **M2 Sketcher** | planegcs adapter; sketch mode UI; line, rect, circle, arc, polygon, slot, point, construction; auto-constraints; constraints and dimensions with expressions; trim, offset, mirror, 2D fillet; DOF status; parameters table | `test_modeler_sketch.py` (skip without planegcs): each constraint, DOF counts, over-constrained detection, expression evaluator (and that it refuses code). `tools/e2e_model_sketch.py` with REAL mouse input: draw a slot, dimension it, change a parameter → the part updates. | L |
| **M3 Features + tree** | sketch on face, reference planes / axes, revolve, hole (+ teardrop), fillet, chamfer, shell, patterns, mirror, combine, move; picking faces / edges / vertices with filter; named references + re-attach; rollback, suppress, edit | One volume test per feature (analytic: hole in a block, revolve of a rectangle = cylinder, shell of a box); naming test (change the base width, fillet still on the same edges); failed feature reports an issue, not a crash. `tools/e2e_model_features.py`: pick an edge → fillet; rollback bar; suppress. | L |
| **M4 Bridges / sources** | "Use as sketch" from wizard / DXF / PDF profile (blocks); insert classic part as a body (live link); STEP → exact body; STL → mesh body (+ convert to solid); model part → 3D print (fit, bed face, split via slabs, joints); export from print tab | `test_modeler_bridges.py`: cookie cutter → body has the same volume as the slab solid; PDF sample → body; slabs of an extruded model part equal the original volume; STEP import volume. `tools/e2e_model_sources.py`: picture → sketch → extrude → print plan. | M |
| **M5 AI** | MCP tools (6.1), `find_refs`; new SYSTEM_PROMPT; `agent_plugin` skills; `get_guide` + MCP prompts + instructions; chat flags change (6.4) | `test_agent.py`: tool list / schemas, command flags, `get_guide` returns each skill. Extend `tools/e2e_agent.py`: drive the model tools through the real MCP process (no model needed): build the bracket from the skill example and compare the volume. One `tools/e2e_chat.py` run (uses the account, so run it sparingly). | M |
| **M6 Inspect** | exact measure, section view (capped), materials and mass, Czech texts completed | volume / mass vs analytic; `tools/e2e_i18n.py` covers the model workspace with no English left. | S |
| **M7 Assemblies (light)** | assembly document; insert; ground; coincident, concentric and distance mates; explode; BOM; assembly STEP; print all parts | `test_assembly.py`: pin in hole (concentric + coincident) gives the expected transform; over-constrained mates are reported; BOM counts. `tools/e2e_assembly.py`. | M |
| **Later (M8+)** | loft, sweep, draft; decorate face (design layers on model faces); ~~exact OCCT split with B-rep joints~~ (done); 3MF with colours; overhang map; text and spline in sketches; feature reorder; angle / parallel mates; interference check | — | — |

**Release order:** M0 → M1 → M2 → M3 is the first big demo: "a real part from sketches". M4 and M5 make it *this* app (pictures + AI). M6 and M7 round it off.

---

## 9. Updates to `.claude/agents/*.md`

### architect.md: replace the intro paragraph and the pipeline list

```markdown
You are the software architect of Auto3DModeler — a local Flask + three.js app for QUICK 3D-printable
parts. It has two geometry paths, and you must keep them separate:

1. Classic parts (Quick part workspace): 2D sources (PDF drawings, picture outlines, DXF, sliced STL)
   become 2.5D `Solid` z-slabs (shapely sections). Booleans are exact, meshes watertight, STEP
   kernel-free. Design layers, bends, splitting and joints live here. Protect that simplicity.
2. Model parts (3D model workspace): a feature tree (sketches with constraints → extrude, revolve,
   hole, fillet, chamfer, shell, pattern, mirror) evaluated by OpenCASCADE (OCP, optional dependency)
   in a worker process; sketches solved by planegcs (optional). Light assemblies (insert, 3 mate
   types, explode, BOM) sit on top.

The goal is quick creation, not every CAD feature: prefer a few robust tools with good defaults.
Bridges, not copies: classic → model through our own STEP writer (exact); model → print through
tessellation + `importers.slice_mesh` → `Solid.from_slabs`.

Know the pipeline before proposing anything (read the files, don't guess):
- Classic: `sketch.py`/`extract.py` (PDF), `solver.py`, `outline.py` (picture wizard, presets),
  `design.py`, `solid.py`, `export.py`, `printing.py`, `joints.py`, `bend.py`, `meshpart.py`/`importers.py`
- Model: `auto3d/modeler/` — `kernel.py` (ONLY place that imports OCP), `naming.py` (named face/edge
  references + fingerprints), `constraints.py` (planegcs), `doc.py` (evaluation, cache), `worker.py`,
  `bridges.py`, `assembly.py`; `auto3d/project.py` (project v3: parts[], assemblies[], assets{})
- AI: `agent_tools.py` (tools + SYSTEM_PROMPT), `mcp_server.py` (also get_guide / prompts),
  `agent.py` (chat flags), `agent_plugin/skills/*` (workflow skills — one source for skills and get_guide)
- `server.py` – thin HTTP layer; `_solve_full` (classic) and `_solid_for` / `/api/model/*` (model)
- Web: `app.js` (Quick part), `workspace.js`, `history.js`, `modeler/*.js`, `assembly/*.js`, `i18n*.js`
```

Principles: replace bullets 2, 3 and 5 with:

```markdown
- Classic sources produce a `solution` + `Solid`; model parts produce named B-rep bodies. Anything that
  prints must reach a `Solid` (via the bridge) so print / split / joints keep working.
- Features reference faces / edges only through named references (`{feature, role, entity, fp}`), never
  by index. Every new feature type defines its face roles.
- Project files are v3; `project.migrate` must open every older file. New fields get defaults.
- OCP and planegcs are optional: the app must start and the classic workspace must work without them.
  Kernel calls go through the worker (crash isolation, cancel).
- Every new MCP tool needs a matching skill / guide update, and every user-visible string an i18n entry.
```

### programmer.md: add under Conventions

```markdown
- Model parts: import OCP only in `auto3d/modeler/kernel.py`; call it through `worker.py` from the
  server. Features are pure functions of (feature JSON, earlier shapes); return issues, never raise to
  the HTTP layer. Give every face a role in `naming.py` when you add a feature type.
- Optional deps: guard with `auto3d.modeler.available()`; tests use
  `@unittest.skipUnless(available("occ"), "OCP not installed")`. Pin versions in `requirements-modeler.txt`.
- Sketch values may be expressions over parameter ids; evaluate them with `doc.eval_expr` (no eval()).
- Frontend: the model workspace has its own state and `History` instance (web/js/history.js); do not
  grow app.js beyond hooks. New UI text goes to `web/js/i18n_modeler.js` (CS + CS_PATTERNS).
- AI: a new MCP tool = schema in agent_tools.py + browser handler + a line in the relevant
  `agent_plugin/skills/*/SKILL.md` + a case in tools/e2e_agent.py.
```

Definition of done: add "volumes checked against an analytic value for model features; STEP write → read round trip".

### tester.md: add a section 4

```markdown
4. 3D model workspace (needs `py -m pip install -r requirements-modeler.txt`; report clearly when the
   kernel is missing — those tests must SKIP, not fail):
   - Unit: tests/test_modeler_kernel.py, test_modeler_sketch.py, test_modeler_bridges.py, test_project.py,
     test_assembly.py. Every feature: analytic volume within 1e-6 relative, watertight tessellation,
     STEP round trip volume, and a naming test (change an early dimension → later fillet / hole still on
     the same faces, or a visible "re-attached" warning — never a silent jump).
   - Browser (REAL mouse input): tools/e2e_project.py, e2e_model_basic.py, e2e_model_sketch.py,
     e2e_model_features.py (pick edge → fillet, rollback, suppress), e2e_model_sources.py
     (picture → sketch → extrude → print plan), e2e_assembly.py; e2e_i18n.py must walk sketch mode and
     every command panel.
   - AI: tools/e2e_agent.py builds the skill example part through the MCP process and compares the
     volume; check the chat `init` event lists the Skill tool and the auto3d:* skills.
   - Old project files (v1/v2 .a3d.json) must open unchanged in the Quick part workspace.
```

### ui-designer.md: replace the layout sentence and add rules

```markdown
You own the user experience of Auto3DModeler: a dark, dense desktop tool UI with three workspaces
switched in the top bar — Quick part (today's layout: left Dimensions / Checks / Drawing / AI, centre
viewport, right Part / 3D design / 3D print), 3D model (Solid Edge / SolidWorks style: command bar on top
that changes in sketch mode, feature tree with rollback bar on the left, property panel with OK / Cancel
on the right, selection filter, status line with sketch degrees of freedom) and Assembly. A project
panel lists all parts and assemblies. The user is a maker who wants FAST printable results — fewer
clicks beat more options; the AI chat can do everything the UI can.

Additional rules for the modeller:
- Use standard CAD words and icons users know from SolidWorks / Solid Edge (Extrude, Revolve, Fillet…),
  with Czech terms from the glossary in docs/ARCHITECTURE-modeler.md.
- Commands pre-select what makes sense (last sketch, edges of a picked face) and show a live preview.
- Picking: hover highlight + label of what will be picked; the filter follows the active command.
- Every new string goes to web/js/i18n_modeler.js; check with tools/e2e_i18n.py.
```

---

### Critical files for implementation
- C:\DEVELOPMENT\PROJECTS\Auto3DModeler\auto3d\solid.py (slab kernel; bridge via `from_slabs` / `faces`)
- C:\DEVELOPMENT\PROJECTS\Auto3DModeler\server.py (`_solve_full`, print / export dispatch, agent endpoints)
- C:\DEVELOPMENT\PROJECTS\Auto3DModeler\web\js\app.js (history lines 38–108, save / open lines 1583–1606, AI handlers)
- C:\DEVELOPMENT\PROJECTS\Auto3DModeler\auto3d\agent_tools.py and C:\DEVELOPMENT\PROJECTS\Auto3DModeler\auto3d\agent.py (tools, SYSTEM_PROMPT, chat flags lines 197–212)
- C:\DEVELOPMENT\PROJECTS\Auto3DModeler\auto3d\importers.py / meshpart.py / export.py (slice_mesh, mesh import, our STEP writer used as the classic → B-rep bridge)

### Facts checked
- PyPI on 2026-10-25: cadquery-ocp-novtk 8.0.1.1.0 has a cp313 win_amd64 wheel (47.8 MB). build123d 0.13.0 pulls in scipy, scikit-learn, sympy, ipython and threejs-materials (89.8 MB). cadquery 2.8.0 needs OCP < 8.0 plus VTK (80 MB). manifold3d 3.5.4 is 1.0 MB. planegcs 0.9.6 has a cp313 wheel (0.6 MB, LGPL). python-solvespace has no cp313 wheel. py-slvs is GPL-3 and was last released in 2023.
- Claude Code 2.1.310 `--help` shows `--plugin-dir` and `--tools`. Nothing was installed or downloaded; metadata was read from the PyPI JSON API.
- Not run yet (planned for M0 / M5):
  - the installed size of OCP;
  - whether OCP and `cascadio` can be imported in one process;
  - whether `--tools "Skill"` is accepted, checked against the chat's `init` event.
