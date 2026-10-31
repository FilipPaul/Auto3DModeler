---
name: easy-assembly
description: Use when parts must be easy to put together (design for assembly, DFA, "snadná montáž", montovatelnost) — automation, ICT / FCT fixtures, functional prints with several parts. Fewer parts and fasteners, self-locating features, one assembly direction, tool access, captive nuts, assembly clearances, service access — each checked with the app's tools and reported as an assembly section in the design review.
---

# Easy to assemble

A part that is cheap to make can still cost an hour on the bench. Design so a person who has never seen it puts it
together right, first time, from one side, with one tool. Use with design-principles, standard-parts and
machined-part / print-functional; clearances in fits-and-tolerances.

**Best effort, not hard rules.** Every rule below is a preference. When one cannot be met (a part must be
asymmetric, a second assembly direction is unavoidable, a screw has to sit under another part), do what is possible
and carry on — do not stop, loop or ask about each rule. List each compromise in one line in the hand-over /
design-review ("⚠ assembled from 2 sides — the sensor bracket needs it"; in Czech "⚠ montáž ze 2 stran — nutné kvůli
…"). Ask the user (`ask_user`) only when a compromise changes what the design does.

## 1. Fewer parts
For every pair of made parts ask Boothroyd's three questions. Merge them (one model, one extrude more) unless **one**
is yes:
1. Does it **move** relative to the other in use?
2. Must it be of a **different material** (insulating, wear, transparent, spring)?
3. Must it come apart for **service, adjustment or assembly** of something else?
- A spacer, a bracket screwed to a plate, a stop block → a boss, a rib or a step of the same part (machined from one
  block if the stock allows; printed as one).
- **Fewer fasteners**: on printed parts snap-fits, hooks and press-fit pins instead of screws; a tab in a slot plus
  one screw instead of four; a part held by its neighbours (a stack clamped by one screw pair).
- `get_bom {mode: "summary"}` before and after: say how many parts and fasteners the merge saved.

## 2. Self-locating parts
A part should find its place before any screw goes in; screws clamp, they do not locate.
- **Dowel pins**: two per joint, far apart — one in a round hole, the other in a slot along the line between them
  (or a diamond pin), so the fit does not fight the hole spacing. Pins H7 in one part, press m6 in the other
  (fits-and-tolerances); one Ø per project (standard-parts). Joint: `snap_faces {type: "axis"}` pin in hole.
- **Shoulders, spigots, pockets**: a spigot Ø into a bore, a plate into a 1–2 mm pocket, a step against an edge — a
  sketch + extrude `op: "cut"` / `"add"`, joined `touch` + `axis` in the assembly.
- **Lead-ins**: a chamfer 0.5–1 mm at 30–45° on every pin end, spigot and the mouth of its bore / pocket
  (`add_feature {type: "chamfer", edges, d: 0.8}`), so parts slide in instead of catching.
- **One way only (poka-yoke)**: where a wrong orientation is possible and wrong, make it impossible — pins of
  different Ø or an asymmetric pin pattern, a notch, a D-flat (`shape: "d_flat"`). Or the opposite: make the part
  **fully symmetric** so any orientation is right.
- **Never "almost symmetric"**: a plate with holes 0.5 mm off centre or one hole missing gets fitted turned round.
  Make the difference big and visible, or remove it.

## 3. One direction, top-down
- Plan the order before modelling the joints: a base that lies on the bench, every next part dropped on from above
  (−Z), fastened from the top. Avoid turning the assembly over; avoid side insertions.
- Each part must stay where it is put while it is fastened (it sits in a pocket, on pins, or against a shoulder) —
  no part to be held with one hand while screwing with the other.
- Sub-assemblies that can be built and tested alone (a probe plate, a sensor bracket) are their own assembly
  (`new_assembly`), inserted into the main one as a whole.

## 4. Tool access, sized by the real tool
- **Hex socket (imbus) by default**: ISO 4762 / DIN 912 socket head cap screws, ISO 10642 countersunk where flush is
  needed — one set of hex keys assembles everything. From the library (`library_search {query: "ISO 4762 M4"}`).
  **All screws from one side**, as few sizes as possible (standard-parts).
- **Key per thread**: M3 → 2.5 mm, M4 → 3, M5 → 4, M6 → 5, M8 → 6 mm.
- **Check every screw**: from its head along its axis a free straight path for the key / ball-end driver —
  free Ø = the driver's Ø + 1–2 mm (a T-handle or bit: its shank Ø; a socket wrench: its outer Ø), at least the
  head Ø + 1 mm where the screw passes through. Length: the key's length (straight driver ~ 100–150 mm), or the
  short leg of an L-key (~ 20–30 mm) from the side when the axis is blocked further away.
- **Torque**: room next to the head to swing an L-key 60–90°.
- **Path blocked** by another part: first move or turn the screw, or change the assembly order. Else cut a
  **tool-access hole** in the blocking part, coaxial with the screw: Ø = tool Ø + 1–2 mm (≥ head Ø + 1 mm if the
  screw goes through it) — `add_feature {type: "hole", d, through: true}` on the screw's axis. Never cut a 🔒 locked
  part or a library part: pick another place, or list the compromise.

## 5. Fasteners that need no second hand
- No spanner behind: a **thread in the part** (machined: `thread: true`), a **heat-set insert** (printed:
  `library_pair {part, role: "insert"}`, `bolt_parts {kind: "insert"}`), a **press-in nut / PEM** in sheet metal,
  or a **captive nut in a hex pocket** (a 6-point `polyline` sketch, across flats s + 0.3, cut 0.2 mm deeper than
  the nut) open from the side the nut drops in.
- **Screw length**: clamp length + engagement (standard-parts §3); never shorter than 1 d engaged in steel, 1.5 d in
  aluminium, the full insert length in a printed part. Not so long that it bottoms out.
- **Washers only where needed**: on slots, soft material, painted surfaces. Not by habit.

## 6. Tolerances for assembly
- Locating features get a clearance that a person can push together by hand (pin in a slot: H7 / g6; a spigot:
  H7 / h6; a printed part 0.2–0.3 mm per side).
- **Do not over-constrain**: one fit per direction. Two pins locate; the screws go through **oversize** holes
  (ISO 273 medium, `thread: false`) and the second pin is a slot. Two spigots plus pins in the same direction jam.
- **Stack-up of hole patterns**: one part has the exact holes (threads or pins), the mating part clearance holes —
  never tight holes in both.

## 7. Cables and service
- Leave a channel, clip points and a connector you can reach for each cable (`add_harness`, P-clamps); cables go in
  after the mechanics without unscrewing them.
- Parts that wear (probes, guide pins, pads, belts, sensors) come out **alone**, from the same side, without
  taking the rest apart — their screws reachable with the assembly mounted.

## 8. Check in the app
1. **Order**: write the assembly steps as a numbered list (part, direction, fastener, tool) — it goes into the
   hand-over.
2. `get_assembly`: every part `fully_held` (or `free` exactly as designed), no `not_held`.
3. `check_collisions {}` at rest. **Insertion path**: for a part with a slide along its insertion axis (a pin or
   spigot joined `axis` leaves it), `move_free {part, motion, amount}` out by its insertion length, or
   `set_travel` from there to its seat and `check_travel {part, motion}` — it must be free all the way. Lock it
   again after (`lock_motion`).
4. **Tool access** (§4) for each screw: its axis from `get_assembly` (fasteners K…, their parts) / `find_refs`;
   `measure {a: {part, face: <screw head>}, b: {part, face: <the nearest wall / part above>}}` for the free Ø and
   length; a section along the axis (`set_view {section: {axis, offset}}` + `get_screenshot`) shows the line out. In
   doubt: a thin cylinder stand-in of the key (Ø, length) on the axis + `check_collisions {}`, removed after. No tool
   does this well yet — once per chat `report_problem {kind: "tool request"}` "check_tool_access {screw} → free
   length / blocking part" (after `list_reports`).
5. **Exploded view**: `set_view {view: "iso", explode: 0.6}` + `get_screenshot` to show the order; `explode: 0`
   after.

## 9. Report: the assembly section of design-review
Add to the design-review table, one row each:

| Area | Item | Result | Recommendation |
|---|---|---|---|
| Assembly | parts / fasteners | 6 made, 14 screws | spacer → boss (−1 part, −2 screws) |
| Assembly | tools | 3 mm hex key only | — |
| Assembly | directions | all from the top (−Z) | — |
| Assembly | self-locating | ⚠ cover plate free to turn 180° | pins Ø4 + Ø5 (poka-yoke) |
| Assembly | tool access | ⚠ M4 at the back: 1 mm to the wall | move it 2 mm in |
| Assembly | compromises | ⚠ from 2 sides — the sensor bracket needs it | — |

Then the steps ("1. Base plate on the bench. 2. Probe plate on its 2 pins, from the top, 4 × M4 × 16, 3 mm key. …")
and offer the fixes with `ask_user {question, options, recommended}`.
