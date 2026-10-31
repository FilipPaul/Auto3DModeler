---
name: start-a-design
description: Use at the start of every new design — a new part, a device, a bracket, a mechanism, an assembly, a decorative model. Asks the user (as buttons in the chat) what the design is for, whether it is 3D printed and whether it must be easy for a person to edit, then picks the skills that fit.
---

# Start a design: the brief

Before the first sketch, know these three things. Take from the user's words what they already said; ask the rest
with `ask_user {question, options, recommended}` — one call per question, in this turn, then **end the turn** and
wait for the answers (they come as the next message). Always recommend one option (shown first, ★) and say in its
description why it fits what the user asked.

1. **What it is for**
   - *Automation / a machine* — it is made to be manufactured (machined, laser-cut, bent or printed as a real
     machine part): standards, library parts, a working assembly, a 2D drawing.
   - *A functional 3D-printed part* — it holds, carries, clips or moves something, printed (PLA / PETG / ASA …).
   - *A graphic / decorative 3D model* — it is about the look: a figure, a sign, a gift, a vase, a visual model.
   Recommend the one the request sounds like (a sensor bracket → automation; a phone stand → functional print; a
   duck → graphic).
2. **Is it 3D printed?** — *Yes, FDM* / *Yes, resin* / *No — machined or bought* / *Not decided*. Skip it when the
   answer to 1 says it (a decorative model is printed; ask only if unsure).
3. **How it is built** — *Easy for a person to edit* (simple sketches with few sizes each, one feature per idea:
   change a size and the rest follows) / *Any way that reaches the goal* (fewer steps, complex profiles allowed — the
   shape matters, not the history). Recommend *easy to edit* for automation and functional parts; for a graphic
   model *any way* is often fine.

Ask a 4th question only when a key size or the material is the user's choice and is not clear (e.g. "Which rod Ø
does it hold?" with the usual sizes as options).

## Then load the skills that fit

| Brief | Skills |
|---|---|
| Automation / machine | design-principles, standard-parts, machined-part, mechanical-design, automation-design, fits-and-tolerances (+ print-functional for printed parts) |
| ICT / FCT test fixture | the automation row + ict-fixture |
| Cables / wiring named, or powered moving parts | + cable-routing (plan the cables with the concept) |
| Functional print | design-principles, standard-parts, mechanical-design, print-functional (+ fits-and-tolerances for bearings, pins, shafts) |
| Graphic / decorative | print-graphics (if printed); model-a-part for the modelling |
| Load-carrying or joining parts, mixed materials | + materials-and-strength |
| Automation, ICT / FCT, functional prints of several parts | + easy-assembly (with machined-part / print-functional): fewer parts, self-locating, one direction, tool access |
| Always | model-a-part to build it, assemble-parts for several parts, print-prep before printing, production-drawing for made parts; **design-review before you say it is done** |

A test fixture (ICT / FCT, bed of nails, probes on a PCB) counts as automation — do not ask question 1 then.

Say the brief back in one line ("A printed functional bracket, easy to edit — I'll …") and keep to it for the whole
chat. When something later is again a real choice (two sensible ways, a size, a standard part), ask with
`ask_user {…}` again — your recommendation first — instead of guessing.
