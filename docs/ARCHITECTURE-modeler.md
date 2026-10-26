# Auto3DModeler: plan for the 3D modeller workspace

Status: plan only. No code has been changed.
Date: 2026-10-25. Written by the architect agent.

---

## Progress (2026-10-26)

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
- **Value ranges done:** doc.limits (each ranged number of a step found by building it at trial values; patterns and
  depths from the geometry), /api/model/limits; failures explained with the most that fits (doc._sized).
- **The later list is done.** Ideas for after it (each to be kept simple, ≤ 2 inputs): hole / sketch distances from
  round faces (a shaft's axis); dimensions of hole positions drawn on the 2D drawing (not only listed); joint types in
  assemblies beyond face-on-face (axis on axis for pins in holes); a sketch mirror line; draft angle on extrudes.

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
                                                  │ "print / split"
                                                  ▼  (tessellate → importers.slice_mesh → Solid.from_slabs)
                                         3D print tab: fit, split, joints (exact for prismatic parts;
                                         curved walls become stairs; exact OCCT split comes later)
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
>   "Symmetric" is a single checkbox. The second direction, "up to face" and "up to next" are deferred.
> - **Hole**: click a point on a face and give a diameter. It goes through by default. Counterbore,
>   countersink, size tables and teardrop are deferred.
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
| Slot | Straight slot | 2 centres + width | MVP (M2) |
| Point | For holes and construction | click | MVP (M2) |
| Construction toggle and centreline | Helper geometry, revolve axis, mirror line | entity | MVP (M2) |
| 2D fillet / chamfer | Round or cut a sketch corner (adds arc + tangency) | corner, r / d | MVP (M2) |
| Trim | Cut a segment back to the nearest crossings | click on segment | MVP (M2) |
| Extend | Extend a line up to the next entity | click | Later |
| Offset | Copy a loop at a distance (one-off copy) | loop, distance, side | MVP (M2), linked offset later |
| Mirror | Mirror entities about a line, adding symmetric constraints | entities, line | MVP (M2) |
| Sketch pattern | Linear / circular copies inside the sketch | entities, count, step | Later (use the feature pattern) |
| Project edges ("Include" / "Convert entities") | Bring part edges into the sketch | picked edges | MVP (M3) |
| Outline / DXF / PDF block | A traced outline, DXF region or PDF profile as one rigid block (position, angle, scale dimension) | asset + width | MVP (M4) |
| Text | Text traced into a block (reuses today's browser text tracing) | text, font, height | Later (easy) |
| Spline | Free curve | points | Later |
| **Constraints** | coincident, horizontal, vertical, parallel, perpendicular, tangent, equal, fixed, concentric, midpoint, symmetric, point-on-curve | picked entities | MVP (M2), all supported by planegcs |
| **Dimensions** | distance (aligned / horizontal / vertical), radius / diameter, angle; driving or reference; value may be an expression using parameters (`w/2+3`) | picked entities, value | MVP (M2) |
| Auto-constraints while drawing | H/V/coincident/tangent guessed from snapping. This is what makes sketching *quick*. | — | MVP (M2) |
| Status (degrees of freedom) | "Fully defined" vs "2 free"; free entities shown in blue | — | MVP (M2) |

### 3.2 Features

| Feature | Purpose | Inputs | When |
|---|---|---|---|
| Extrude | Push a sketch region out | sketch, regions (default: all closed), op = new / add / cut / intersect, extent = blind / symmetric / through all / up to face / up to next, flip, 2nd direction | MVP: blind, symmetric, through (M1); to face / next (M3) |
| Revolve | Spin a sketch around an axis | sketch, axis (centreline or datum axis), angle, op | MVP (M3) |
| Hole | Proper holes on a face | face, sketch points, type = simple / counterbore / countersink, size from a table (M2–M12, with print clearance), depth or through, **teardrop** option for horizontal holes (printable without support) | MVP (M3) |
| Fillet | Round edges | edges (named references), radius | MVP (M3) |
| Chamfer | Bevel edges | edges, distance, or distance + angle | MVP (M3) |
| Shell | Hollow a part | faces to remove, wall thickness | MVP (M3) |
| Linear pattern | Repeat features or a body | features or body, direction (edge / axis), count, spacing | MVP (M3) |
| Circular pattern | Repeat around an axis | features or body, axis, count, angle | MVP (M3) |
| Mirror | Mirror features or a body | plane / planar face | MVP (M3) |
| Combine bodies | Add / subtract / intersect body B with body A | 2 bodies, op | MVP (M3) |
| Move / rotate body | Place a body | body, translate, rotate | MVP (M3) |
| Insert part / import | A classic part, STEP or STL as a body | source reference, placement, op | MVP (M4) |
| Draft | Angle walls for moulds | faces, neutral plane, angle | Later |
| Loft | Shape between 2+ sketches | sketches | Later (M8) |
| Sweep | Profile along a path | sketch + path sketch | Later (M8) |
| Decorate face | Today's design layers (patterns, logos) on any **planar face** of a model part, embossed or cut along the face normal | face, layer JSON | Later (M8). Easy, because `design.layer_regions` already makes shapely regions. |
| Thread, rib, split body | — | — | Later |

### 3.3 Reference geometry

| Tool | Inputs | When |
|---|---|---|
| Datum planes XY / XZ / YZ, axes X / Y / Z, origin | built in | MVP (M1) |
| Offset plane | plane or face, distance | MVP (M3) |
| Angled plane | plane + edge / axis, angle | MVP (M3) |
| Mid plane | two parallel faces | Later |
| Axis | cylinder face, or 2 points, or 2 planes | MVP (M3): cylinder and 2 points |
| Point | vertex, centre of circle | Later |

### 3.4 Feature tree

| Function | When |
|---|---|
| Ordered list: origin → sketches → features; icons; error and warning badges with the reason | MVP (M1) |
| Edit (re-opens the command with its values), rename, delete (warns about dependants) | MVP (M1–M3) |
| Suppress / unsuppress | MVP (M3) |
| Rollback bar (drag, or "Roll to here"); new features go in at the bar | MVP (M3) |
| Parameters table (name, expression, value), shared by all sketches and features | MVP (M2) |
| Reorder by drag | Later |

### 3.5 Inspect

| Tool | Inputs | When |
|---|---|---|
| Measure (exact distance / angle / radius between faces, edges, vertices) | 1–2 references | MVP (M6). Today's measure tool keeps working on classic parts. |
| Mass properties: volume, area, mass, centre of mass | body + material | MVP (M6) |
| Materials: PLA 1.24, PETG 1.27, ABS 1.04, ASA 1.07, TPU 1.21, PA 1.14 g/cm³; infill % as an estimate | per part | MVP (M6) |
| Section view: clipping plane with a capped cut | plane, offset | MVP (M6) |
| Printability: faces overhanging more than 45° highlighted, thin walls | body | Later |

### 3.6 Assemblies (keep it light)

| Tool | Inputs | When |
|---|---|---|
| Assembly document; insert a part from the project library or from a file | part id, placement | M7 |
| Ground (fix) an instance | instance | M7 |
| Mates: coincident (plane–plane, with flip), concentric (axis–axis), distance (plane–plane offset) | 2 references + value | M7 |
| Exploded view: per-instance offset steps, with a slider | instance, vector | M7 |
| BOM (parts list): part, quantity, material, mass | — | M7 |
| Export: assembly STEP (several bodies), or "print all parts" (each to the print tab) | — | M7 |
| Angle / parallel / tangent mates, interference check, motion | — | Later |

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
| 3D print (fit, split, joints) | Works on any part. Model parts: exact bounding box for the fit check; splitting converts B-rep → slabs (stairs warning for curved walls) and then reuses `printing.plan` and `joints` unchanged. Later: exact OCCT split, with joints built as B-rep prisms from the same shapely polygons. | `slice_mesh` + `Solid.from_slabs` |
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
auto3d/modeler/worker.py       one worker process holding the shape cache; timeouts; cancel; crash → restart + error
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
| R2 | OCCT failure or crash brings down Flask | All kernel calls run in `worker.py` (one process). An exception becomes a feature issue. A crash means restart the worker and report "kernel crashed while building Fillet 2". Timeout 60 s, with Cancel through `progress`. This also avoids thread-safety problems (Flask runs `threaded=True`). |
| R3 | Install size and failures | Optional extra; `/api/kernel` shows status and the exact `py -m pip install -r requirements-modeler.txt`. Versions are pinned. Note: do not install `cadquery-ocp` (with VTK) next to `-novtk`, because both provide the `OCP` module. |
| R4 | OCCT inside both `cascadio` and OCP in one process | Smoke test in M0. If they clash, load OCP only in the worker process (planned anyway). |
| R5 | Sketch dragging feels slow over HTTP | Local Flask + planegcs: about 5–20 ms per solve. Throttle to one solve in flight (the same pattern as `pump()` in app.js). Later option: a vendored planegcs WASM build. |
| R6 | planegcs bindings are young (0.9.x) | Adapter layer; our own unit tests for each constraint type; pinned version. |
| R7 | app.js is already 1,879 lines | The new workspace lives in its own modules with its own state. app.js only gets: workspace switch hooks, "use in model" buttons, and the save / open of v3. |
| R8 | Splitting model parts for print is approximate at first (stairs on curved walls) | Clear issue text; exact OCCT split in "later". Fit check is exact from the start. |

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
| **Later (M8+)** | loft, sweep, draft; decorate face (design layers on model faces); exact OCCT split with B-rep joints; 3MF with colours; overhang map; text and spline in sketches; feature reorder; angle / parallel mates; interference check | — | — |

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
