---
name: design-review
description: Use before you tell the user a design (a part, an assembly, a fixture, a machine) is done, or when they ask for a review / "check it" / "zkontroluj to". A compact engineering checklist — function, strength, ergonomics, economy, safety — each item checked with the app's tools where possible, reported as one table with fixes offered.
---

# Design review before hand-over

Go through the list with the tools, not from memory. Skip items that do not apply (a single printed clip has no
pinch points). Keep it quick: one pass, then the table.

## 1. Function
| Check | How |
|---|---|
| Every part held as in reality; moving parts keep exactly their motion | `get_assembly`: `fully_held` / `free`, no `not_held`, no `broken` joints, `groups` as intended |
| No collisions at rest | `check_collisions {}` — overlap = a missing hole / pocket or a wrong joint |
| No collisions over the motion | `check_travel {part, motion}` for each limited motion; `drive_mechanism {mechanism, collisions: true}` for mechanisms |
| Strokes and positions right | `measure {a, b}` (a probe's working stroke, a gap, a sensor's distance) |
| Every step builds | `get_model` of each made part: all `ok`, no warnings left unexplained |
| Assembly access | every screw head reachable with its key from outside (`set_view {section}` + `get_screenshot`); screws not hidden under other parts; an assembly order exists |
| Easy assembly | easy-assembly §8 checklist (order, insertion paths, tool clearance, exploded view) → its Assembly rows in the table |
| Service | wearing parts (probes, guide pins, pads, belts) replaceable without taking the whole apart |
| Cables | routed, bend radius kept, no taut cable over the travel: get_assembly `harnesses` at both limits (cable-routing) |
| Strength | the weak point checked (materials-and-strength): load path through stiff parts, deflection, safety factor |

## 2. Ergonomics
| Check | How |
|---|---|
| No sharp edges where hands go | chamfer / fillet steps in `get_model` on outer edges, or the ISO 13715 note on the drawing |
| Handling weight | `get_assembly` `mass_g`: > 15 kg needs handles / two people, > 25 kg a lift; a swappable insert ≤ 10 kg with grips |
| Operator reach and height | controls and the PCB load area ≤ 400 mm from the front edge, working height 900–1100 mm |
| Loading is obvious | guide pins / stops make a wrong position impossible (poka-yoke), the PCB goes in one way only |
| Labels | name / number engraved (`decal`) or a label place; connectors and adjustments marked |

## 3. Economy
| Check | How |
|---|---|
| Number of made parts | `get_bom {mode: "summary"}` make rows — can two be one? can a made part be bought (a spacer → a standoff)? |
| Kinds of bought parts | standard-parts count — can kinds merge? |
| Material and stock | plate thicknesses from the stock series, cheapest material that works (machined-part) |
| Machining set-ups | per made part: sides with features (machined-part §5) |
| Tolerances only where functional | `get_sheet` dims with `tol` / fits — each one has a reason |
| Bought vs made | bought where a standard part exists; made where it saves several bought ones |

## 4. Safety
| Check | How |
|---|---|
| Pinch / crush points | moving plates or arms closing to < 25 mm (fingers) → a guard, two-hand start or a gap ≥ 25 mm / ≤ 4 mm |
| Press / cylinder force > 150 N reachable by hands | two-hand control or a guard / light curtain, an E-stop (automation-design) |
| Stored energy | springs and pneumatics release safely (exhaust valve, captive springs) |
| Electrical | live parts covered, insulating plates where probes / wires are |

## 5. Report
One short table to the user (their language), a row per item that applies:

| Area | Item | Result | Recommendation |
|---|---|---|---|
| Function | collisions | OK | — |
| Function | screw access | ⚠ 2 × M4 under the top plate | counterbore from the top |
| Economy | bought kinds | ⚠ 9 kinds | M4 × 14 → M4 × 16 (−1 kind) |
| Safety | pinch point | ⚠ top plate 12 mm gap | two-hand start |

Then the one-line verdict ("Ready, 2 recommendations" / "Not ready: a collision"). Offer the fixes with
`ask_user {question, options, recommended}` (e.g. *Fix all ★* / *Only the function items* / *Leave it*) and end the
turn; do the chosen ones, then re-run only the checks they touch. A problem caused by the app (a wrong collision, a
check tool that fails) → `report_problem {kind: "bug", …}` after `list_reports`.
