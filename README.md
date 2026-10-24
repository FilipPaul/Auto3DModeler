# Auto3DModeler

Turns a dimensioned 2D PDF drawing into a parametric 3D model you can edit, add dimensions to,
decorate with real 3D design (embossed / engraved / cut-through grids, shapes and logos), check against
your 3D printer and split into printable pieces — exported as STL or STEP.

```
pip install -r requirements.txt
python server.py            # opens http://127.0.0.1:5173
```

Click **Sample drawing** to load `initial draft.pdf`, or open/drop your own PDF.

## How it works

1. **Extraction** ([auto3d/extract.py](auto3d/extract.py)) – reads the vector content of the PDF with PyMuPDF:
   thick strokes = part outline, filled/open triangles = dimension arrowheads, text = dimension values.
2. **Interpretation** ([auto3d/sketch.py](auto3d/sketch.py)) – the drawing is treated as *topology only*:
   - corners are merged and traced into closed loops (outer profile + cutouts);
   - corners on the same vertical/horizontal edge share an x/y **level**;
   - each pair of opposing arrows is a dimension, matched to the edges its tips point at and to its label;
   - every dimension becomes a constraint `level_hi − level_lo = value`.

   **Dimensions are the source of truth.** Drawing proportions are used only when something is not
   dimensioned (the estimate is flagged and should be confirmed). This matters for the sample, which is
   not drawn to scale (3.1–27.4 pt per cm across its dimensions).
3. **Solving** ([auto3d/solver.py](auto3d/solver.py)) – positions are propagated through the constraint tree,
   then the profile is validated (no self-intersection, cutouts inside the outline, no overlaps). Invalid
   edits are rejected with a reason and the last valid model is kept.
4. **3D solid** ([auto3d/design.py](auto3d/design.py), [auto3d/solid.py](auto3d/solid.py)) – design layers become 2D
   regions, the part is built as a stack of z-slabs and meshed without T-junctions (watertight).
5. **Export** ([auto3d/export.py](auto3d/export.py)) – binary STL and AP214 STEP (one solid per connected body), in **mm**.
6. **Printing** ([auto3d/printing.py](auto3d/printing.py), [auto3d/joints.py](auto3d/joints.py)) – printer profiles,
   fit check, split planning and joints between pieces.
7. **Bending** ([auto3d/bend.py](auto3d/bend.py)) – folds and rolls applied to the final mesh (split across the
   bend zones, then mapped onto the bent shape).

## What gets reported (Checks tab)

| Severity | Situation |
| --- | --- |
| error | label is not a number / zero / missing; dimensions contradict each other; no outline found; no readable text |
| warning | a feature is not dimensioned (value estimated); no thickness given (default used); dimension not attached to geometry; orphan dimension text; open outline; curves/angled dimensions (unsupported) |
| info | redundant dimension (shown as reference); arrow snapped to a nearby edge; edges assumed aligned; drawing not to scale |

A thickness can be given in the drawing as a note like `t=18mm`; otherwise set it in the Dimensions panel.

## Editing

- Type in the parameter list, or click a value in the 3D view to edit it in place.
- Drag a 3D value left/right to scrub it, or scroll over it. `Shift` = ×10, `Alt` = ×0.1.
- Inputs accept arithmetic (`78.7/2`). Parameter names can be renamed by clicking them.
- Dimensions are chained the way they are drawn: e.g. a cutout dimensioned from the right edge follows it
  when the overall length changes.

### Adding dimensions

Click **＋ Dimension** (or press `D`), pick two edges or corners on the part, type the value. The click
position sets where the dimension is drawn. Dimensions form a tree, so a new one must replace a
constraint between the two picks: an estimated/assumed value is replaced automatically, otherwise you
choose which existing dimension becomes a driven *reference*. Reference / conflicting dimensions can be
made driving the same way (**Make driving** / **Use this value**); added dimensions can be removed.

## 3D design (right panel)

Each layer = **mask × fill → operation**:

| | options |
| --- | --- |
| Mask | whole face (with edge margin), rectangle, ellipse, image/logo (PNG/JPG/SVG traced to a silhouette); position, size, rotation, invert |
| Fill | solid, or one of 20 patterns. **Line patterns** — square, rectangular, diagonal, triangular, hexagonal, brick, columns, waves, zigzag, chevron, fish scales, Voronoi (seeded, adjustable randomness), contour (follows the mask outline), spiral, radial — use the *lines* (ribs) or the *cells* between them. **Shape patterns** — dots, circles, checkerboard, stars, crosses — use the *filled shapes* or their *outlines*. Spacing, line width, shape size, amplitude, angle, origin, offset |
| Operation | **emboss** (raise by height), **engrave** (cut in by depth), **cut through** (lattice / perforation), **guide** (outline only) |

Layers are real geometry and are included in STL/STEP. Masks can be dragged on the part (with snapping).
Checks warn about depths ≥ thickness, layers outside the face, and features thinner than 0.4 mm.

### Bending

Bends are applied last, to the finished part, so cutouts, design layers and joints bend with it
(length is kept on the mid-thickness, like real sheet bending).

- **＋ Fold line** — click on the part where the fold goes (`R` rotates the line). Set the bend angle
  (0° = flat, 90° = right angle), the inner radius, and the shape: *front outside* (roof ∧, tube) or
  *front inside* (gutter ∨). Several folds in the same direction give U, Z or multi-facet roof shapes.
- **＋ Roll** — bends the whole length into one arc of the given angle (180° = half tube, up to almost a
  full ring); the inner radius follows from length and angle.
- **Flat view** switches the bends off temporarily to edit masks and dimensions; the dimension tool and
  fold placement switch to it automatically.

Checks refuse overlapping bends, bends in two crossing directions (a flat sheet can't do that), bend
zones running off the part, and inner radii smaller than embossed design on the inner face.

Bent STL files are smooth (one facet per ≤ 3°). Bent STEP files are faceted solids (flat facets),
because exact cylindrical faces would need a CAD kernel. When splitting a bent part, cuts are kept out
of the bend zones and each piece is exported bent (curved parts usually need supports; alternatively
print flat with the bends hidden and heat-bend).

## 3D print (right panel)

Built-in printers: **Creality Ender-3 Pro** (220 × 220 × 250 mm) and **Bambu Lab P1S** (256 × 256 × 256 mm);
add your own with **＋ New printer** (stored in `data/printers.json`). The build volume is shown in 3D and
the part is checked against it (with a configurable bed margin, 90° rotation allowed). **Split to fit**
cuts the part into the fewest pieces that fit, preferring even pieces and cuts through solid material
(more glue area); pieces are exported as a ZIP of STL or STEP files with an `ASSEMBLY.txt` sheet.

### Joining split pieces

All joints are vertical extrusions, so pieces and connectors print flat without supports. Connectors are
placed only where the cut runs through solid material, keeping ≥ 1.2 mm of wall to edges, cutouts and
design features; every option has a print *clearance* (default 0.15–0.2 mm).

| Joint | How it works | Extra parts |
| --- | --- | --- |
| Butt joint | straight cut, glued (glue channel + ports by default) | – |
| Dovetail — through | trapezoid tabs through the full thickness (outline visible on the front) | – |
| Dovetail — hidden, flat front | tabs only behind a straight front skin (default 3 mm), so the assembled front is flat with a hairline seam. Pieces alternate male (print front-up, tabs on the bed) / female (print front-down, sockets open upwards); male pieces drop into the sockets from the back | – |
| Jigsaw puzzle | round knobs printed into the cut (alternating or one direction) | – |
| Butterfly keys | bow-tie pockets across the seam (front or back), keys printed separately | bow-tie keys |
| Dowel pins | rectangular pockets inside the cut faces (short bridge, no supports) | rectangular pins |
| Splice plate | plate recessed across the seam (back by default), optional M-screw pilot holes | plates |

**Glue features** (butt joint, both dovetails, puzzle, dowels): a small *glue channel* runs along each seam
inside the thickness (below the skin for hidden dovetails) so glue spreads along the joint and excess
collects there instead of squeezing out onto the front; optional *injection ports* — half-holes in both
pieces that form round holes on the back once assembled — let you dry-fit the parts and then inject thin
CA or slow epoxy until it appears at the next port. Channel size and port diameter are adjustable.

The split planner gives every piece its own length allowance (e.g. in a male / female row only the male
pieces get longer), so joints cost as few extra pieces as possible.

Connector parts are grouped into identical parts (`…_butterfly1_x4.stl` = print 4). When the pockets
open on the back, pieces are exported back-face up so the pockets face upwards; if the front has
embossed design this is reported instead. Integral joints make pieces longer, which the split planner
accounts for.

Projects (model, edited/added dimensions, design layers) can be saved/loaded as `.a3d.json`.

## Tests

```
python -m unittest discover -s tests -v
```

The suite covers the sample drawing (all 12 dimensions, geometry, propagation, exports), synthetic
drawings for each failure mode (invalid/missing/zero labels, missing dimensions, conflicts, redundancy,
open outline, no dimensions, thickness note), every design operation and pattern (watertight mesh,
volumes, STEP bodies), image tracing, printer profiles, splitting and every joint type (fit, watertight
pieces and connectors, material conservation, wall checks, joints through engraved patterns).

## Current limitations

- Single view, straight-line profiles extruded to a constant thickness; arcs/holes (Ø, R), angled
  dimensions and multi-view drawings are reported but not modelled yet.
- Design features and joints are vertical extrusions (no chamfers/rounded profiles, no round dowels).
- Very dense curved patterns over a large face (hundreds of circles/scales) can take several seconds to rebuild.
- Scanned (raster) PDFs and PDFs with text converted to outlines can't be read (no OCR).
