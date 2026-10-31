---
name: cable-routing
description: Use when the user names cables, wires, a harness, tubes or "from where to where" the cabling goes, or the design has motors, sensors, connectors, a PCB, valves or a moving axis with powered parts. Plans the cabling at concept time — the cable list, bend radii, channels, holes, clips, glands, energy chains, service loops — then routes it with add_harness and checks it over the motion.
---

# Cable routing — plan it with the mechanics

Plan the cables EARLY, when the concept is laid out — not after the parts are done. A hole, a channel or a clip spot
is one step in a made part now and a redesign later. Load assemble-parts (item 8 has the harness tools in full).

## 1. The cable list first
Write it as a short table before the first made part, one row per cable:

| From → to | Kind | Ø | r_min | Connector at each end |
|---|---|---|---|---|
| sensor B1 → box | signal, M12 4-pin | 5 mm | 30 static / 60 moving | M12 straight plug Ø15, 45 mm long |

- **Kind**: power (motor, heater, mains), signal (sensors, switches), bus (CAN, EtherCAT, USB, encoder), pneumatic
  tube (Ø4 / Ø6). Group them later by kind.
- **Ø**: the maker's datasheet; unknown → ask the user once (`ask_user {…}` with typical sizes as options) or take a
  typical one: M8 / M12 sensor cables Ø4–6 mm, stepper / servo motor cables Ø6–9 mm, a ribbon 1.27 × wires, PU tube
  Ø4 / Ø6. A library part with a cable (a SICK sensor, a motor) shows where it plugs in.
- **Min bend radius**: static ≈ 5–7 × Ø, moving or in a chain ≈ 10–12 × Ø, a tube ≈ 4–5 × Ø (Ø4: ≥ 15 mm) — or what
  the maker says. Pass it as `r_min` (the app's default is 5 × Ø: static only).
- **Connector size at each end**: holes, slots and chains must pass the CONNECTOR, not just the cable (an M12 plug
  Ø15–20, a D-sub 9 ≈ 31 × 13, a motor's Molex ≈ 12 × 10). Leave its length + the cable's straight exit (≈ 3 × Ø)
  free behind every socket — a sensor's M12 plug needs ≥ 35–45 mm.

## 2. Reserve space in the made parts
- **Channels and grooves**: a groove ≥ bundle Ø + 2 mm wide and deep, along a frame edge or under a cover; a
  slot cut through a plate where the connector must pass (connector + 1–2 mm each side).
- **Pass-through holes**: connector + 1–2 mm, edges chamfered or rounded (r ≥ 1 mm) — a fillet / chamfer step on the
  hole's edges — or a rubber grommet (a stand-in of its outside sizes when not in the library). Never a sharp
  laser-cut or sheet edge on a cable.
- **Clip / tie-mount spots** every 100–150 mm on a static run, and within 50 mm of each bend and connector:
  HellermannTyton P-clamps (H1P–H8P, screw M4) or MB tie mounts — `library_search {query: "P-clamp"}`. Put an M4
  tapped or clearance hole (fits-and-tolerances) at each spot in the made part, on a flat face ≥ the clip's foot.
- **Strain relief** at every connector and gland: a clip 30–80 mm before it, so a pull never reaches the contacts.
- **Cable glands** in housings and boxes: M12 (cable Ø3–6.5), M16 (Ø4.5–10), M20 (Ø6–13) — a thread or clearance
  hole Ø12.2 / 16.2 / 20.2, ≥ the gland's nut across corners (M16 ≈ 22 mm) from a wall and from the next gland.
- **Separate power from signal**: ≥ 20–30 mm apart, cross at 90°, or a divider / a separate channel. Bus and encoder
  cables beside a motor cable are the classic fault.
- Keep cables away from hot parts, sharp edges, pinch points and the moving parts' way.

## 3. Moving axes
- **Energy chain** for a linear axis (igus from the library: `library_search {query: "e-chain"}` — E2.10, E2.15,
  14, 10):
  - inner width / height ≥ the bundle + 10–20 % (cables side by side, not stacked; a divider between power and
    signal);
  - the chain's bend radius ≥ the largest moving r_min (10–12 × Ø);
  - the travel from the mechanism's limits (`set_travel {…}` / the stroke); the fixed end at the middle of the
    travel keeps the chain shortest;
  - room for the chain's U (≈ 2 × bend radius + link height) above or beside the axis in the frame.
- **Service loop** across a hinge or a short stroke: a slack span long enough for the whole motion (arc length at
  the cable's radius + 10–20 %), its bend ≥ the moving r_min, clipped on both sides of the hinge, close to its axis.
- **Check both limits**: the cable is never taut and hits nothing at min and at max, and in between.

## 4. Build it in the app
1. Place the bought parts with their connectors (sensors, motors, valves, a box with glands) and the made parts with
   their holes, channels and clip spots.
2. `add_harness {type: "cable", d, r_min, reserve: 10, name: "B1 → box", points: [...]}` — from a connector face to
   a connector face (`find_refs` for the faces; the ends on a part are connection points), through the holes and
   along the channels (`{part, face}` / `{part, point}`), `{xyz}` only to lead it round. One harness per cable, or
   type `"wires"` for a bundle of loose wires.
3. Clips: `edit_harness {id, clip: {point: 3}}` on each clip spot (it picks the snuggest P-clamp, fixed to that
   part). A moving span: `edit_harness {id, chain: {span: 2}}` (a chain sized for the bundle is put in) or a loop
   `edit_harness {id, spans: [{from: 3, length: 180}]}`; the chain follows the carriage:
   `edit_chain {id: "C1", moves_with: "I5"}`.
4. Lock the length (`edit_harness {id, length_locked: true}`), then `drive_mechanism {mechanism, to}` or
   `check_travel {part, motion}` to both limits and `get_assembly {}` at each: `harnesses` with `taut`,
   `bends_too_tight`, `through_parts`, `still_hits`, `too_close`; `chains` with `reach_ok`.
5. Warnings → `edit_harness {id, auto_fix: true}` first. What is left: fix the MADE PART (a bigger hole, a channel, a
   clip spot moved, a chamfer) or the route — do not force the cable with a lower r_min.

## 5. Assembly and service
- Cables go in after the mechanics: every connector reachable with a hand (≥ 30 mm around a plug), every clip's
  screw reachable with its key.
- A part that wears or is swapped (a sensor, a motor, a probe plate) comes out by unplugging, not by cutting ties:
  a connector at the part, clips that open (P-clamps) rather than ties around it. With auto3d:easy-assembly (if
  loaded): cables count in its assembly order.
- Label both ends of each cable (the cable list's name).

## 6. Hand-over
- The cable list with lengths: the harness lengths from `get_assembly {}` / `get_bom {mode: "summary"}` + 10 %
  reserve (set `reserve: 10`), Ø, kind and connectors.
- Clips, tie mounts, glands and chains in the BOM (from the library, with part numbers).
- design-review's Function table gets a row: "cables routed, bend radius kept, no taut cable over the travel".

## Best effort
A rule that cannot be met (no room for 10 × Ø, a channel would weaken a part, no gland size fits): take the closest
compromise (a smaller r_min for a static cable, a clip instead of a channel, a flatter cable), carry on, and list it
in the hand-over with the reason.
