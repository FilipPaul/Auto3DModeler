---
name: ict-fixture
description: Use for an ICT / FCT test fixture (bed of nails, test adapter, Prüfadapter, testovací přípravek) — probe plate with INGUN / KESACON receptacles and probes on the PCB's test points, PCB carrier with guide pins and cut-outs, top plate with pressure pins, vacuum or mechanical press, interface to the tester. Load with design-principles, standard-parts and machined-part.
---

# ICT / FCT test fixture

## 1. Ask only what the app cannot know
With `ask_user` (one question each, your recommendation first), only when not given:
- **The PCB data**: Gerber / ODB++ (or a DXF) with the outline, the test points and the tooling holes — it is
  opened with `open_file {path}`; the board thickness (1.6 mm default) and the highest components top / bottom.
- **The press**: manual lever / pneumatic (recommend for < ~500 probes) or vacuum; ICT or FCT; the tester or the
  interface connector it plugs into.
Everything else (plates, materials, grid, keep-outs) you choose and say.

## 2. Read the board
- `open_file {path}` → `get_drawing {}` (layers, units; fix with `drawing_units`), then `drawing_find {filters}`:
  test points (pads / drill hits on the test or copper layer), tooling holes (`[{field: "dia", op: "≥", value: 3}]`
  on the holes layer), the outline.
- **Origin = the primary tooling hole** of the PCB (or its lower-left corner when the board has none): the same
  origin in every plate, so the test-point coordinates go straight into hole steps (`origin: "world"`).
- Check DFT before modelling, report what fails: pad Ø ≥ 0.9 mm (100 mil), ≥ 0.6 mm (50 mil); pad centre ≥ 1 mm
  from component bodies, ≥ 2 mm from components > 3 mm high, ≥ 3 mm from the board edge (vacuum: ≥ 5 mm seal border).

## 3. Probe series = the closest spacing
| Grid | Series (library) | When |
|---|---|---|
| 2.54 mm (100 mil) | INGUN GKS-100 in KS-100 | the default — most robust, cheapest |
| 1.91 mm (75 mil) | INGUN GKS-075 | pads closer than 2.54 |
| 1.27 mm (50 mil) | INGUN GKS-050 in KS-050, KESACON MPI | only where needed |
Use **one series per fixture** where possible (standard-parts); a second series only for the dense area. Head style
by target: crown (`"GKS-100 crown"`) on solder / leads, spear / cone on pads and vias, flat on gold.
`library_search {query: "probe 2.54"}`: the receptacle's description gives the **mounting hole Ø in FR4** and the
**installation height H** (tip above the plate); the probe gives its **stroke** and spring force. Take them from
there — never guess a press-fit hole.

## 4. The stack (bottom → top) and its heights
1. **Probe plate**: FR4 / G10 8–10 mm (`set_material {material: "FR4 (PCB)", tolerance: "m"}`), receptacle holes
   `add_feature {type: "hole", face, origin: "world", points: [[x, y], …], d: <the item's hole Ø>}` (a plain hole,
   no standard); ≥ 30 mm free below for the wiring.
2. **PCB carrier (stripper) plate**: POM-C or FR4 6–10 mm, spring-loaded on guide bushings above the probe plate;
   probe clearance holes Ø probe + 0.5; pockets for the underside components = outline + 1 mm per side, depth =
   height + 1 mm (or through); chamfer 0.5 on the PCB seat edges.
3. **Guide pins** for the PCB in the carrier: tooling holes Ø3 / Ø4 +0.08/0 → pins Ø3 / Ø4 g6, one round and one
   **diamond (relieved)** pin diagonally (no jamming from the PCB's hole-pitch tolerance), sticking out PCB t + 3 mm
   with a conical lead-in; press-fit in H7.
4. **Top (push-down) plate**: Al 10–12 mm with **pressure pins** (POM, Ø4–6, ends rounded) on free board areas,
   opposite the probe clusters, ≤ 25 mm apart, ≥ 1 mm from components, near edges and connectors.
- **Heights**: at rest the probe tips are ≥ 1 mm below the PCB (protected). In test position each probe is pressed
  by its **working stroke ≈ 2/3 of the max stroke** (GKS-100: the item's stroke × 2/3). Carrier travel = rest gap +
  working stroke. Keep it as parameters: `set_parameter` `pcb_t`, `grid`, `stroke_w`, `t_probe`, `t_carrier`.

## 5. Forces → press
- Probe force total = n × spring force at the working stroke (e.g. 300 × 1.5 N = 450 N); pressure pins and the press
  carry it with 1.5× reserve; the top plate and the carrier sag < 0.1 mm (materials-and-strength).
- **Mechanical / pneumatic press** (default): simple, double-sided probing possible; a pneumatic cylinder from the
  library sized by automation-design (Ø40 at 6 bar ≈ 750 N). **Vacuum**: big boards, many probes, one side only;
  needs a sealed carrier (gasket, ≥ 5 mm border, no open vias) — more parts and set-up.
- Safety: pinch point between the top plate and the carrier → two-hand start or a guard (design-review).

## 6. Build it in the app
1. Plates as 3D models (machined-part rules), all on the PCB origin; holes from the drawing coordinates.
2. `new_assembly {name: "ICT fixture <board>"}`, `insert_part` the plates, join with `snap_faces` (touch / gap /
   axis on the guide bushings).
3. Receptacle: `library_add {item, size, to: "assembly"}`, `snap_faces {move: {part, face: <its outer cylinder>},
   onto: {part: <probe plate>, face: <its hole>}, type: "axis"}` + `touch` collar on the plate top; then
   `library_pair {part: <receptacle I…>, role: "probe"}` — the probe seated, its stroke as its slide's limits.
   More of them: `library_add` the same item again (one BOM row, n pieces).
4. Probes that must keep a pitch to each other (a dense pair, a Kelvin pair): `snap_faces {type: "axis_distance",
   distance: 2.54}` between their round faces; `measure {a, b}` checks any spacing ≥ the grid.
5. Motion: the carrier's slide `set_travel {part, motion, min, max}` (rest → test), `check_travel {part, motion}`,
   `check_collisions {}` at both ends; at test position `measure` tip to pad = working stroke.
6. `get_bom {mode: "summary"}`: probes and receptacles per series, screws (standard-parts); drawings of the plates
   (production-drawing); then design-review.
