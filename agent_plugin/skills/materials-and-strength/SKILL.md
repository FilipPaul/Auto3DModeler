---
name: materials-and-strength
description: Use whenever a design has parts that carry load or join other parts, or mixes materials and processes (printed PLA / PETG / ASA / PA-CF, CNC aluminium or steel, POM, FR4) — before designing a new part or joint among them. Neighbours' materials, a property table, joint rules (screws in plastic and aluminium, creep, galvanic pairs, expansion, stiffness, wear, layer direction) and quick deflection / stress checks.
---

# Materials and strength in mixed assemblies

## 1. Know what you attach to
Before designing a part that joins or carries others, read its neighbours:
- `get_assembly` — each placed part's part, material and mass; library parts carry their own material (steel
  8.8 screws, stainless pins, FR4, POM …) in the library item's description.
- `get_model` of a made part — its material and mass (set with `set_material`).
- No material set yet: decide it now (machined-part / print-functional) and `set_material {material}` — masses,
  the BOM and the drawing follow.
- The load is unknown and it matters (a bracket that carries, a press, a handle): ask once with `ask_user` —
  "What does it carry?" with options (≈ 1 kg / ≈ 5 kg / ≈ 20 kg / a force in N), your guess first.

## 2. Properties (room temperature, typical)
| Material (`set_material`) | E GPa | Yield / tensile MPa | ρ g/cm³ | Max °C | Creep | α µm/m·K |
|---|---|---|---|---|---|---|
| PLA (`PLA`) | 3.5 | – / 50 | 1.24 | 50 | high | 70 |
| PETG (`PETG`) | 2.0 | – / 45 | 1.27 | 70 | medium | 65 |
| ASA (`ASA`) | 2.0 | – / 40 | 1.07 | 90 | medium | 90 |
| PA12 (`PA`) | 1.7 | – / 45 | 1.01 | 100 | medium, takes water | 100 |
| PA-CF (`PA-CF`) | 6–8 | – / 80 | 1.2 | 120 | low | 30 |
| AlMg3 EN AW-5754 (`aluminium`) | 70 | 130 / 220 | 2.66 | 150 | none | 23 |
| EN AW-6082-T6 (`aluminium`) | 70 | 250 / 300 | 2.70 | 150 | none | 23 |
| EN AW-7075-T6 (`aluminium 7075`) | 72 | 480 / 540 | 2.81 | 120 | none | 23 |
| S235 (`steel`) | 210 | 235 / 360 | 7.85 | 400 | none | 12 |
| 1.4301 (`stainless steel`) | 200 | 210 / 520 | 7.9 | 400 | none | 16 |
| POM-C (`POM`) | 2.8 | 65 / 65 | 1.41 | 100 | low for a plastic | 110 |
| FR4 / G10 (`FR4 (PCB)`) | 20 (in plane) | – / 300 | 1.85 | 130 (Tg) | low | 14 |
**Printed parts are anisotropic**: across the layers (Z) ≈ 50–60 % of the XY strength; the printed values above are
XY, 100 % infill, 4+ walls. Plastics under permanent load: design to ≤ 1/3 of their strength (creep).

## 3. Joint rules
- **Screw into plastic**: never a cut thread below M6. Heat-set insert (ruthex, one size per thread) where it is
  opened again; thread-forming screw (core hole ≈ 0.8 d) where it is assembled once. Clamp a plastic part with a
  washer or a large head — surface pressure ≤ 10 MPa permanent (PLA / PETG) — and a limited torque: M3 ≤ 0.5 N·m,
  M4 ≤ 1 N·m into inserts.
- **Printed part clamped between metal**: it creeps and the screw loosens. Keep the clamped plastic thin, the load
  path short, use a metal spacer / sleeve through the plastic where the preload matters, or a spring / wave washer.
- **Steel screw in aluminium**: engagement ≥ 1.5 d (2 d in AlMg3 or where torque is high); opened often (> ~10×) or
  ≤ M4 in a service part → a helicoil (thread insert) — say so on the drawing. Steel into steel: 1 d.
- **Galvanic pairs**: aluminium + stainless / copper in wet or salty air corrodes the aluminium — insulating washers,
  anodised aluminium, or zinc-plated steel screws; in a dry indoor fixture accept it.
- **Thermal expansion**: Δ = Δα · L · ΔT. 500 mm of aluminium on steel, ΔT 20 K: (23 − 12) · 0.5 · 20 = 0.11 mm —
  fix one end, slotted holes at the other; plastic on metal over > 200 mm: slots always.
- **Stiffness mismatch**: the softest member deflects first. Run the load path through the stiff parts (aluminium,
  steel); a printed part locates, covers or guides, it does not carry the main load between two metal parts.
- **Wear pairs**: POM on steel or anodised aluminium is good (low friction, no grease); PTFE / PA also fine.
  Printed sliding parts wear and stick — use a POM strip or a bought bushing. Aluminium on aluminium: galls, avoid.
- **Layer direction**: load along the printed layers; a hook, a clip, a cantilever lies flat on the bed (print-functional).

## 4. Quick checks (N, mm, MPa — E in MPa = GPa × 1000)
- Mass: `get_model` (the part), `get_assembly` `mass_g` (all of it) — for handling (design-review) and the load of
  its own weight (1 kg ≈ 10 N).
- Cantilever bracket, force F at length L, section b × h (h in the bending direction):
  I = b · h³ / 12, deflection δ = F · L³ / (3 · E · I), stress σ = M · y / I = 6 · F · L / (b · h²).
- Example: PETG, b 20, h 5, L 50, F 20 N → I = 208 mm⁴, δ = 20 · 125000 / (3 · 2000 · 208) = 2.0 mm (too soft),
  σ = 12 MPa. h 8 → I = 853, δ = 0.49 mm, σ = 4.7 MPa. The same in 6082: δ 0.06 mm at h 5.
- Safety factor on yield (plastics: on strength): metal ≥ 2, printed plastic ≥ 3–4 (across layers use the Z value),
  POM / FR4 ≥ 3. Deflection: ≤ L / 500 for locating parts (probe plates, guides), ≤ L / 200 elsewhere.
- Too weak: increase h first (δ ∝ 1/h³), add a rib (model-a-part), shorten L, then change the material.
- Say the result in one line: "Bracket PETG 8 mm: 0.5 mm sag and 4.7 MPa at 20 N — safety 9."

## 5. Hand over
In your summary name each part's material and process and the one weak point you checked (or that the load was
assumed and which). design-review takes it as its function / strength item.
