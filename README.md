# Auto3DModeler

*Created by [Rafiontech s.r.o.](https://www.rafiontech.cz/).*

Turns a dimensioned 2D PDF drawing into a parametric 3D model you can edit, add dimensions to,
decorate with real 3D design (embossed / engraved / cut-through grids, shapes and logos), check against
your 3D printer and split into printable pieces — exported as STL or STEP.

```
pip install -r requirements.txt
python server.py            # opens http://127.0.0.1:5173
```

Use **📂 Open ▾** to open a file. It offers:
- a PDF drawing (try **Sample drawing**, which loads `initial draft.pdf`);
- a **picture**, to trace the outline of an object in a photo (e.g. `pernicek.png`) and make a cookie cutter
  or a solid shape from it — see [Outline from a picture](#outline-from-a-picture);
- **PCB data** — a Gerber set or an ODB++ job (a .zip / .tgz, or several Gerber / drill files picked together) —
  opens as a **📐 Drawing** too, a layer per Gerber file / ODB++ layer (see [PCB boards](#pcb-boards-gerber-odb));
- a **DXF / DWG drawing** opens as a **📐 Drawing** — see [DXF / DWG drawings](#dxf--dwg-drawings); nothing is made of it until you
  choose (Shift+drop: straight to a quick part, as before);
- a **CAD / 3D file**: STL / OBJ / STEP files — a **STEP opens as a 3D model** with its exact
  solid as the first step (sketch on its faces, drill it, build a cover around it; a 40 MB STEP in under a minute);
  STL / OBJ open as a quick part (sliced, for printing; Shift+drop a STEP for that too);
- a saved project.

You can also drop a file on the view. To model a part from scratch, click **＋ New 3D model** (see
[3D model workspace](#3d-model-workspace)).

**Čeština / English**: the **CZ / EN** button at the right of the top bar switches the language live. The choice
is remembered; the first time, the app uses the browser's language. Your own text (the project name, chat
messages, the names you type) is never translated. Dimension names that come from a drawing are only shown
translated; the project file keeps the originals. Translations live in `web/js/i18n.js`. Exact texts go in
`CS`. Texts with values go in `CS_PATTERNS`, where `{}` is a value; values that are known texts are translated
too. Text with markup goes in `CS_HTML`.

**Long work shows progress**: importing or rebuilding a large 3D file shows a progress bar with **Cancel**.
Cancelling puts the part back the way it was. Curved or slanted 3D imports get a slice height chosen
automatically so they build in a few seconds; the Part tab lets you set a finer one.

**Project name and saving**: click the project name in the top bar to rename it. *Save project* and the exports
open the browser's Save dialog (Edge / Chrome), so you can pick the folder and the name. Other browsers download
the file instead.

**Several parts in one project**: every file you open becomes its own **part tab**, in a row of its own under the
top bar — more rows when they do not fit, so every name stays readable (the tab on screen, or one being renamed, shows
its whole name). Click a tab to switch parts; each keeps its edits and its own undo history. Double-click a
tab to rename it, **drag** it to move it (dropped outside the window: it opens in a ⧉ new window), and use **✕** to
close the tab — the part stays in the project; closing the last one leaves *No part open* until ☰ opens one. **☰** (before the tabs) opens the **project tree**
in the left panel: every part of the project, open or not, as they go together — each assembly with what is in it
(sub-assemblies inside, *Pin ×2*), each part's 📄 drawing sheets under it, then the parts in no assembly. The mouse on a
row shows a **picture** of what is in it; a row **dragged onto an assembly's view** puts that part in. A part from the
library shows the **library icon** (📚) until it is changed. A **middle click** on a tab closes it. Click one to
open it (the tree stays), ⧉ opens it in a new window, ✕ deletes it from the project at once — **↶ Undo** in the
tree's header brings it back (for half a minute). Parts made for an assembly (fasteners) are added without a tab. The **＋**
next to the tabs offers the usual ways to open a file.

**What a sketch click takes**: the row of filters at the bottom of the sketch — *Points, Midpoints, Origin, Lines,
Circles / arcs, Part edges* — says what a click may pick (remembered). The origin and a line's **midpoint** can be
picked and dimensioned from (the distance is held from the middle as the line changes). A dimension can be dragged by
its label or **by its dimension line**. A circle or arc shows its size as **R or Ø** — *⇄ Show it as a radius /
diameter* (or R ⇄ Ø in its size box); a typed value is taken that way. Drag a round size's label anywhere: dropped
**inside the circle** it becomes a diameter across it, **outside** a radius from the centre. **Drawing snaps** to points, a line's
**midpoint** (the new point stays at the middle), anywhere **on a line, circle or arc** (it stays on it) and the
part's edges — off the grid too — the place named at the mouse; the same filters say what it snaps to. **Guides**: in line with a point (its x or y — a
corner, a line's middle, the origin) or on the extension of a line, the cursor catches there and a temporary dashed
line shows what it lines up with (two at once: where they cross).

**◫ Planes** in the 3D model's toolbar shows or hides the (faint) Top / Front / Right planes — remembered; they show
anyway while a sketch plane is being chosen.

**⟋ Draft**: tilts an extrude's side walls by a few degrees (they lean in going up from its base; negative: out) so a
moulded or cast part comes out of its mould — choose the extrude (or click one of its walls) and the angle.

**Reorder steps**: drag a step up or down the step list. A move that would put a step before one it uses is refused
(it says which), and one after which the model no longer builds is taken back; Ctrl+Z undoes a move.

**A click on a face of a 3D model** chooses its step and shows its tools in the Suggested table (bottom left) — the
table can be **dragged by its header** anywhere in the view, and stays there (a double-click on the header: back).
Its **✨** puts what is selected into the AI chat — as the AI's tools name it (a step and a face, sketch shapes,
assembly parts) — so you can ask about it. The **Snap** row under it (3D model, assembly) says what 📏 Measure catches:
corners, edge midpoints, centres. With **no tool on**, the snap point under the mouse shows too and a click picks it
(in an assembly: with its part) — *📏 Measure from here*, *Copy its coordinates*, ✨.
The same tools open with a **right click** on it (a left click chooses its step and shows its
sizes; the right button dragged still pans).

**Box selection** in a sketch (⬚ Select, drag on empty space): **right to left** takes every shape the box touches
(green, dashed), **left to right** only the shapes wholly inside it (blue); hold **Ctrl** to add to what is picked —
by click or by box. Delete removes them all.

**Suggestions for what is selected**: choose a shape in a sketch (⬚ Select) or a part in an assembly, and a small
table in the bottom-left corner of the view says what can be done with it — a line: its length, horizontal,
vertical, construction; a part: open it, join it, simplified, its own part, take it out. **Ctrl+click** more and it
offers what fits them together: two crossing lines — their angle, parallel, perpendicular, equal; a line and a circle —
tangent, the distance from its centre; two circles — concentric, equal, tangent; two parts — join them, measure,
check for collisions. Esc (or another tool) closes it.

**Construction lines**: **┄ Construction** in the sketch toolbar draws helper lines, circles and arcs (dashed
amber) while it is on; with ⬚ Select it turns the selected shape into one (or back). They guide — a ⟳ Revolve takes
a construction line as its axis by itself, ⇋ Mirror can mirror across one, dimensions and relations use them — but
are not part of the outline that is extruded.

**The sketch tells its state**: its shapes are **blue** while they can still move, **green** when fully defined and
**red** in a lock that does not fit; **✓ Finish sketch** turns green when every size is fixed, and **🪄 Auto-dimension**
shows only while sizes are still free. **↔ Dimension** on a line, circle or arc gives its size at once (a box beside
it: type and Enter); a click on a second shape instead gives what fits the two: two points — the distance (along x,
along y or straight), two crossing lines — the **angle** between the arms you clicked, a point and a slanted line —
its distance from the line, two parallel lines — the distance between them. Sizes are drawn **as on a
drawing** (dashed extension lines, a dimension line with arrows, a leader for Ø / R — soft violet when locked, faint
when free). A dimension the other sizes fix already (90° between two sides of a rectangle) is added as a **reference
dimension**: it only measures, shown in brackets *(90°)*; 🔓 / 🔒 on a dimension switches it between reference and
driving; **drag** any size label to move it
(kept with the sketch), and the mouse on a label lights up what it measures.

**Actions in the corner**: the buttons that finish or leave a step — **✓ Finish sketch**, **OK** / **Cancel** of a
feature, **Done** — float in the bottom-right corner of the view in every workspace; the toolbars hold only the tools.

**⧉ Windows (several monitors)**: the **⧉** on a tab (or in ☰ Parts) opens that part — a 3D model, an assembly, a
drawing sheet, a 2D drawing — in a new browser window, with only that tab (the other parts are in its ☰ tree).
**Drag a tab** from one window onto another window's tab row: it opens there and goes from the first. The windows stay linked: a change in one is in the others at
once (an assembly using a changed part is built again, a drawing sheet of it gets a new revision, the same part on
screen in two windows shows the change in both), and the project is saved the same from any of them.

**Autosave**: the project is kept on the server (`data/projects/`) a few seconds after each change — "✓ Saved 22:31" by
the project's name says so — so a closed tab or a browser crash loses nothing. **Open ▾ → 🕘 Recent projects…** lists
the kept projects to open again (✕ forgets one; **🧹 Clean up empty projects** deletes, after asking, every one with
nothing in it that still has the name the app gave it — the one on screen stays); when the app starts empty, the last one is offered at the bottom left.
*Save project* still writes a file to keep or send.

**Panels**: drag the edge between a side panel and the view (or the AI chat's left edge) to make it wider or narrower;
the widths are remembered, a double-click on an edge gives the usual width again.

**Turning the view**: a left drag turns the 3D view freely, as far as you like (over the top too): across the screen
about its upright, up and down about its level. A right drag pans, the wheel zooms; Iso / Top / Front / Right set the
view again.
*Save project* stores all the parts in one file (project version 3). Older project files still open, as a
project with one part. The plan for the coming 3D model workspace (sketches → extrude / revolve / fillet …,
light assemblies) is in [docs/ARCHITECTURE-modeler.md](docs/ARCHITECTURE-modeler.md). Its optional packages
are listed in `requirements-modeler.txt`; the app works without them.

## 3D model workspace

**＋ New 3D model** opens a new part tab (marked ◆) where you build a part step by step, as in Solid Edge or
SolidWorks. It has only the tools that need almost no input.

1. It starts sketching on the **Top** plane. Draw with **▭ Rectangle** (two clicks: the corners),
   **⟋ Line** (click point after point; click the first point again to close the shape) or **◯ Circle**
   (the centre, then the edge), or **◠ Arc** (click where it starts and ends, bend it with the mouse, click; its
   radius shows as R and can be typed and locked like any size). Started at the loose end of a line, the arc
   **continues the line smoothly** (tangent) — two clicks: the line's end, then where the arc ends; Shift-click
   for a free arc. **◜ Round corner** (F): click a corner where two
   lines meet and type the radius — an arc tangent to both lines replaces the corner. The sharp corner stays as a
   point (dashed), so the rectangle keeps its width and you can still dimension from the corner; changing the
   width or the radius keeps the rounding tangent. **✂ Trim** (T): click the piece of a line, circle or arc to cut
   away — up to where other shapes cross it (shown in red first). A circle becomes the arc that is left, a line or
   an arc keeps its other part(s), and the new ends stay on the shape that cut them. **⟷ Extend** (E): click a line near an end — it
   lengthens up to the next shape it meets (shown in green first) and that end stays on it. **⟂ Relations ▾** makes shapes
   keep a relation: *Horizontal*, *Vertical*, *Parallel*, *Perpendicular*, *Equal* (two lines the same length, two
   circles / arcs the same size), *Concentric*, *Coincident* (a point on a point, a line or a circle), *Tangent* and
   *Fix* — choose it, click the shapes. Each shows a small symbol by its shape (click it to remove it) and is listed in
   the panel; relations that contradict each other or the locked sizes are refused, naming the one in the way.
   **The part under the sketch**: its round edges (hole rims, bosses — on any level) show dashed with a ✛ centre; a
   click snaps to a centre and to the circle itself (draw a circle on a hole: the same place and Ø), and ↔ Dimension
   measures from them. **🪄 Auto-dimension** locks what the sketch still needs to be fully defined: each shape's
   sizes, then its place from the nearest edges of the part (a hole from the outer edges closest to it), else the origin.
   **⇋ Mirror**: choose the Y or X axis in its little box (or click a line of the sketch), then click shapes — a
   rectangle or a joined outline goes whole. The mirror image is a copy that stays mirrored (⇋ *Mirrored*: change the
   original and the copy follows; click the ⇋ symbol to let it go free); points on the mirror line are shared, so half
   a profile becomes a closed one. *Move* turns the shapes over instead of copying them. **⧈ Offset** (O): click a
   closed shape and type the distance (negative = inside) — a parallel copy: a circle gets a concentric one, an
   outline of lines and arcs keeps its sharp corners sharp and its roundings concentric, a picture outline grows
   or shrinks (e.g. the wall of a cookie cutter).
   - Points snap to the grid (it follows the zoom), to the origin, and to existing points. Snapping onto a point
     joins the shapes there. Hold Alt to draw without snapping. A line drawn almost horizontal or vertical
     becomes exactly that.
   - **Every size has a label. Type a number on it to lock it 🔒.** A locked size stays when you drag or change
     other sizes. For example, lock a hole at x 10 and it stays 10 mm from the edge when the plate gets wider.
     Click 🔒 to free a size again, or 🔓 to lock it as it is.
   - **↔ Dimension** (D) adds a distance. Click two things: points, a circle (its centre), lines, the origin, or
     the **edges of the part**. When you sketch on a face, its edges show dashed and can be dimensioned from.
     Choose along x, along y or straight if more than one fits, then type the value; it is locked. For example:
     circle → the plate's top edge, type 6; circle → the right edge, type 8; the hole now sits 6 / 8 mm from those
     edges. ✕ on a dimension (or in the panel's list) deletes it. 🔒 / 🔓 on a dimension you added locks it (it holds) or
     frees it (it only measures and shows the live value). A shape's own sizes (lengths, Ø) can be hidden with ✕ too:
     ↔ Dimension on the same line or circle twice adds it back, and *Show hidden sizes* brings back all of them.
     There are no automatic position labels: a shape shows only its own sizes and the dimensions you added.
   - **🏷 Sizes** (at the top of the step list and in the sketch panel; remembered): **All**, **🔒 Locked** (only
     the sizes you locked — and on the part a step's own numbers, like an extrude's height) or **None** (a clean
     view). It works both in a sketch and on the 3D part. A big sketch (over 200 shapes, e.g. made from a PCB)
     labels only its locked sizes even under All — *Show them all anyway* gives it every label. A long Dimensions
     list in the panel is folded.
   - Whatever the mouse is on that a dimension or a new point would attach to lights up green and is named
     (point, corner of the part, edge of the part, line, circle, origin). The origin is always shown (orange, with
     its x / y arrows).
   - **🖼 Outline** inserts an outline from a picture (traced in the outline editor), a DXF / DWG or a PDF
     drawing as one shape. On a face it is centred on the face. Drag it to move it; type its width (on its label
     or in the panel) to size it.
   - Drag a shape (⬚ Select) to move it: only what is free follows the mouse. A point drawn on the origin is
     locked there.
   - While you sketch, the part is see-through, so the sketch, the grid and the dimensions show even behind it.
   - The panel says how many sizes are still free, or "✓ Fully locked". A size that contradicts other locks is
     refused, and the message says which locks are in the way.
   - Delete removes the selection; Ctrl+Z undoes the last change in the sketch. A shape inside another one
     becomes a hole.
2. **✓ Finish sketch** opens **Extrude** straight away, with a live preview.
   - Choose **⬆ Add material** or **⬇ Cut**, and type the distance.
   - Optionally tick *Both sides* or *Through all* (for a cut), or click *⇅ Flip direction*.
   - Or **Up to a face**: click a flat face of the part — the extrude goes as far as that face (with an *Offset*:
     more = past it, negative = short of it) and follows the face when the part changes.
   - OK, or Enter, adds the step.
3. **✏ Sketch** again and **click a flat face** of the part to sketch on it. On a face, Extrude starts as
   **Cut**, ready for holes and pockets.
   - A sketch on the top or bottom face of an extrude follows that face when the extrude changes.

4. **◜ Fillet** (F) rounds edges and **◸ Chamfer** bevels them. Click the edges (a click on a face takes all of its
   edges; a picked edge is dropped by clicking it again), then type the radius or size. **◎ Hole** (H): click on a
   flat face where a hole goes (near the centre it snaps to it; click again for more holes on the same face), and
   type the diameter. It goes through all by default, or untick *Through all* and give a depth. Each hole is
   placed from the face's nearest edges — *↔ 10 mm from the right edge*, *↕ 5 mm from the lower edge*, drawn on
   the face. Type a distance to move it, ⇄ measures from the edge on the other side, and 🎯 lets you click *any*
   edge of the face — or another hole (then it is measured from that hole's centre and follows it). Every tool shows a live
   preview.

   **Dimensions follow the part.** A hole's distances and a sketch's dimensions to the part's edges or corners
   (↔ Dimension on a dashed edge) remember *which* edge or corner it is (by the faces that meet there). Make the
   part wider in an earlier step and the hole or the sketch moves with its edge, keeping its distance.
5. **⟳ Revolve** spins a sketch around an axis: the sketch's vertical axis (the default), its horizontal axis or one
   of its lines, a full turn or any angle. Draw half the shape beside the axis, e.g. half a vase on the **Front**
   plane. A new, empty sketch can be moved to Front / Right with the buttons in the bar, and a sketch on a base plane
   can be moved along it with **Offset** (e.g. 30 mm above the bed). **▢ Shell** hollows the
   part out: click the face(s) to leave open (the top of a cup) and type the wall thickness.
6. **⧫ Loft** makes a shape from one outline to another — e.g. a square base to a round top: two sketches one above
   the other (give the second sketch an *Offset*), choose *From* and *To*. **〰 Sweep** moves an outline along a
   path — pipes, handles, rails: a closed profile across the path's start, and a path of lines and arcs (an open
   line); sharp corners of the path are mitred. Both can add or cut material.
7. **Aa Text / picture** decorates a flat face: click where it goes (near the face's centre it snaps to it), type
   the text (or choose a picture — it is traced to an outline), its height, *Raised* or *Engraved* and the depth.
   It stays on its face when the part changes.
8. **⁂ Pattern** repeats a step (a hole, a boss, a cut — or another pattern): **▦ In a row** — how many and how far
   apart, along X / Y / Z or a straight edge you click; **◌ Around** — how many, evenly around Z (or X / Y), or around
   the axis of a round face you click (a hole, a shaft). The copies follow when the original changes.
   **⇋ Mirror** mirrors the whole part, or one step (a hole, a boss, a cut), across YZ (left ↔ right), XZ (front ↔
   back) or XY (top ↔ bottom) — or a flat face you click (also *⇋ Mirror across this face* on a clicked face): **⇋
   Mirror and copy** (the part and its mirror image) or **↦ Mirror only** (the part turned into its mirror image).

**Pointing at and clicking the part.** The step under the mouse lights up (all its faces) and its name shows at
the mouse. A click on a face pops up the tools for it — sketch on it, a hole or text there, round / bevel its edges,
hollow it out with it open, edit / turn off / delete its step — and shows that step's **sizes on the part** (the
sketch's sizes on its plane, the height, Ø, R, the wall…). Click a size: a number and a **slider** — the part
follows while you slide; Enter / OK keeps it (one undo step), Esc goes back. Every number in a tool's panel
(Extrude, Revolve, Fillet, Chamfer, Hole, Shell, Pattern, Text) has a **slider** under it too — slide and watch.
The sliders run only over the values that **work**: the kernel tries the step with the part as it is and finds the
range (the biggest rounding the edges allow, a wall up to what the part can take, a blind hole up to the part's
thickness, a pattern only as far as its copies still reach the part); the range shows under the slider, a typed
value beyond it is held at the limit. When a step fails anyway, it says how much does fit (*at most 9.99 mm*) — or
that no size works there and what to change.
A click on a step in the **list** does the same as a click on the part: it is marked in 3D (a sketch's lines in
gold, with the faces made from it) and its sizes show on the finished part — change a sketch's sizes there,
looking at the result.

Every face of the model has a name ("the top of Extrude 1", "the wall made by line 3"). Roundings, holes and
sketches keep pointing at the same faces and edges when earlier sizes change. For example, make the box taller and
the rounded edge is still the same edge. If an edge can only be found again by its position, the step shows a
yellow ⚠.

**Looking at it:**
- **📏 Measure** (M): click a face for its type and area (and Ø when it is round), or an edge for its length (or
  Ø). Then click a second spot for the distance with Δx / Δy / Δz. It snaps to the part's **corners, edge midpoints and the centres of round edges** (holes, pins) — the point it will
  take shows green with its name while the mouse is near (in assemblies too) — and edges hidden
  behind the part are not picked.
- **✂ Section** cuts the view along X, Y or Z with a slider, to look inside (⇄ shows the other side).
- The Part panel shows the size, volume and **mass** for the chosen **material** (PLA, PETG, ABS, ASA, TPU, PA;
  solid, no infill).

**From the other parts of the app:**
- **◆ To 3D model** (in the Quick part's 3D toolbar) makes a new model tab from the part's outline: a picture
  traced into a cookie cutter, a DXF, a PDF drawing (its profile with the cutouts, in mm) or a 3D file's
  footprint. The outline becomes the first sketch, and Extrude is ready.
- **🖨 Prepare for 3D print** (in a model's Part panel) makes a printing copy of the model as a Quick part, on the
  3D print tab: printer fit, splitting into pieces with joints. Make it again after changing the model.

Sketches show as lines in the 3D view: bright while not extruded yet, faint once used. Double-click a sketch's lines to
change it. The steps are listed on the left. Double-click a step (or ✎) to change it; ● / ◌ turns a step off and on (it is kept); ✕ deletes it, together with the
steps that need it. A step that cannot be built shows ⚠ with the reason, and the others still build. Ctrl+Z /
Ctrl+Y undo and redo whole steps, and each model tab keeps its own history.

**Export ▾** (or the buttons in the panel) gives STL for printing and STEP with exact circles and faces for
other CAD programs.

The model is built by a real CAD kernel, OpenCASCADE. It runs in its own process, so a failure cannot stop the
app, and Cancel works on long rebuilds. It needs the optional packages in `requirements-modeler.txt`
(`py -m pip install -r requirements-modeler.txt`, about 175 MB installed). Without them the rest of the app
works, and the workspace says what to install.

Coming next ([plan](docs/ARCHITECTURE-modeler.md)):
- arcs, sizes between any two points, and equal / parallel / perpendicular rules;
- AI tools for models;

## DXF / DWG drawings

A DXF / DWG opens as it is in the **📐 Drawing** workspace: every line, circle, arc, polyline and text on its
layers, in their colours, in real mm.
- **Layers** (left): 👁 show / hide (All / None), the colour, a click makes it the layer new lines go on, ＋ Layer.
  **Ctrl+click** picks more layers, **Shift+click** all between: 👁 or a colour on one of them changes them all, and
  their bar can show / hide them, select their shapes or make them a filter (*Layer is any of …*).
- **⬚ Select** (Ctrl+click: more; Delete removes; a shape's panel moves it to another layer), **／ Line** (L) and
  **◯ Circle** (C) — ends, middles and centres snap — **📏 Measure** (M: two spots, or a circle's Ø), ↶ ↷, ⤢ Fit (F).
  Drag the paper to move it, the wheel zooms.
- **🔍 Select by filter**: ＋ Filter adds a condition — Shape, Layer, Ø, Radius, Length, Colour or Text with is / is not,
  = ≠ < > ≤ ≥ or contains — as many as you like, all must hold; the matching shapes are outlined and counted, *Select
  them* or *Add to the selection*. **💧 From a shape** (the eyedropper): click a shape in the drawing and the filters become what it is — remove one
  to find more (without *Layer*: on any layer). **≡ All like this** fills the filters from a selected shape (its shape, layer and
  size). Selected circles get one **Ø** box (centres stay), circles and arcs an **R**, lines a **Length** — type it and
  all of them change.
- **File units**: a file may not say its units (PCB tools often draw in inches) or say them wrong — choose mm / cm /
  m / inch and the drawing is rescaled; a tiny drawing with no units says so when it opens.
- **Use ▾** asks, when shapes are selected or a filter finds some, whether it takes the selection, the filter's
  shapes or all the shown layers — then makes something of them: **✏ As a sketch of a new 3D model** (lines, circles and arcs, their
  ends joined — then ⬆ Extrude), or **▤ As a quick part** (its closed outlines: a cutter, a solid shape …).

## PCB boards (Gerber, ODB++)

*Open → CAD / PCB / 3D file* takes a **Gerber set** (RS-274X / X2 and Excellon drill files: a .zip, or the files
picked together) or an **ODB++ job** (.tgz / .zip, also packed inside a zip; compressed .Z files too). The board opens
as a 📐 Drawing — everything in the DXF / DWG section above works on it (layers, measuring, 🔍 filters with a
**Width** filter for traces, ≡ / 💧, Use ▾):
- a **layer per file** (Gerber X2 names its own; else the extension or the name — KiCad, Altium, Eagle, OrCAD, gEDA,
  fab short names like `tl` / `bs`), in PCB colours; the top copper, outline, holes and top silkscreen are shown,
  the rest is a click on 👁 away. Several boards in one zip (folders) are told apart by their folder.
- traces are drawn **at their width**, pads and copper areas **filled**, clear (negative) parts cut out; pads snap at
  their middle. Aperture macros, arcs, regions and step & repeat are read; ODB++ standard symbols and the job's own.
- **drill files** often do not say their number format: their holes are scaled onto the board drawn by the Gerber
  files of their folder (it says so when it does).
- **⬇ DXF** saves the shown layers (of any drawing): in mm, its layers and colours; a trace -> a polyline of its
  width, pads and areas -> closed outlines + a solid hatch, clear parts on `<layer>_CLEAR`.
- A board of half a million shapes opens in a few seconds and stays quick to pan, zoom and pick.

## 2D drawings

**📄 Drawing sheet** (a 3D model's panel) opens the part's drawing as a tab of its own, to edit: the front, top,
right and iso views on an A4 / A3 page with a title block (part, material, scale, paper, tolerances, created,
**changed + revision**). Its dimensions are made by a preset (for the whole sheet, and each view may have its own in the Views list) — **Light** (the overall sizes, a Ø for each hole size,
the biggest R), **Medium** (+ where the holes are, the radii, the heights) or **Full** (+ every level) — and holes
alike are dimensioned **once**: *8× Ø3 H7*, the first hole's place and the row's pitch *3× 10* (200 holes in a grid
are one Ø and two pitches, not 400 dimensions). Each size is given once on the sheet — a view whose sizes are all in
the others (often the Right) has none; its choice **All its sizes** gives it its own anyway. **Clicking a dimension
lights up the same size in the other views** (teal). **Drag** a dimension or a view to move it, **Del** removes a
dimension (↺ brings deleted ones back), **＋ Dimension**: click an **edge** (it lights up under the mouse) — click it
again (or Enter) for its **length**, another edge for the **distance between them**, or a point for the distance from
the edge —, two points (a corner, a hole's centre), or a circle (its Ø / R). A value is always measured from the part — it cannot be typed. The sheet **follows its part**: change
the part and the views and dimensions are made again, the revision goes up and *Changed* says when (your moved and
own dimensions stay on their edges and holes). **Check** (the left panel) tells whether the part is fully dimensioned: each view shows ✓ or ⚠ with how many sizes it
misses — a hole's place, an edge, a Ø or R — listed with **＋** (add that one, from the part's edge) and **＋ Add all
missing**, and marked with an orange **?** on the drawing (not in the PDF); dimensions that give a size twice are
marked ⧉ (*✕ Remove them*). A known circle gives its own edges (a tangent side, a boss), a pitch *4× 10* its row.
The title block takes your own texts — *Title*, *Drawing no.*, *Drawn by*, *Note* — in the panel (a double-click on a cell goes to its field). **⬇ PDF** gives the sheet as you see it. The AI works on sheets too
(`sheet_open`, `get_sheet`, `sheet_edit`: a preset, the paper, views, dimensions added between points or on a
circle, removed or moved; `export {format: "pdf"}` on a sheet) — for what the editor does not offer in a click.

**📄 Drawing** in an assembly's toolbar (or *📄 Drawing sheet* in its panel) opens the **assembly's own drawing sheet**
to edit: its front, top and iso views, overall sizes, parts list and balloons — move them, add your dimensions and
texts, **drag the balloons** where you want them (they start spread round the view); it follows the assembly (a moved
part: a new revision). Its **Pages** list — on every page of the set, the part's sheets too — shows the whole set
(the assembly, its sub-assemblies, their parts) with this page marked; a click opens that page's drawing sheet (made
when it has none). **📚 All pages** shows the set one page below the other to scroll through, like a PDF: Pages marks
the page in sight, a click in Pages goes to it, a double-click on a page opens it to edit. The drawing set below uses these sheets.

**📄 Drawings (PDF)** in an assembly's panel makes its whole drawing set as one PDF, in the order of the assembly:
the **assembly** (its views, overall sizes, the **parts list** — position, name, quantity, material, part number —
and a **balloon** with the position on each part in the iso view), then each **sub-assembly** the same way followed by
its parts, then the assembly's own **made parts**. The positions are numbered **once for the whole set** (the top
assembly's parts 1, 2 …, a sub-assembly's new ones go on from there; a part used twice keeps its number). Every part is drawn once — by its own 📄 drawing sheet when it has
one (with your dimensions), otherwise made with the medium preset; bought and standard parts (library, screws, nuts)
are only in the parts lists. Each page's title block names the part or assembly, what it is in (*in Machine · Pos.
1*) and its page (*Sheet 2 / 5*). The AI's `export {format: "pdf"}` in an assembly writes the same set.

**📐 Drawing (PDF)** in a 3D model's panel (or *PDF — 2D drawing* in the Export menu) makes an A4 drawing sheet:
the **Front**, **Top** and **Right** views with visible edges (solid) and hidden ones (dashed), an iso view, the
overall sizes dimensioned, every hole labelled (Ø) and listed with its position from the part's lower-left corner,
and a title block (name, size, material, mass, scale). The AI's `export {format: "pdf"}` writes the same file.
A big imported model (more than ~3000 faces — an assembled PCB, a maker's STEP) is drawn from its mesh, without hidden
lines: seconds instead of minutes; its dimensions are still measured from the exact edges.

**Fits and tolerances**: a Hole step has a **Fit** (H6 / H7 / H8 / H9, ISO 286) — the drawing labels it *Ø8 H7* and
lists it with its deviations (*Ø8 H7 (+0.015 / 0)*); the part's **Tolerances** (ISO 2768-f / m / c) go into the
title block. The model keeps the nominal size. **Materials** (37, in groups): 3D printing (PLA, PETG, ABS, ASA, TPU, PA, PA-CF, PC, PP), engineering plastics (POM, PE-HD,
PA6-GF30, PTFE, PEEK, PMMA, PVC), metals (aluminium, 7075, steel, C45, stainless 304 / 316, tool steel, cast iron, brass,
bronze, copper, titanium, zinc die-cast, magnesium) and other (EPDM rubber, silicone, plywood, MDF, glass, CFRP, FR4) —
each with its density (the mass) and a colour the part takes when it has none of its own; **metals look metallic**
(polished stainless, brushed aluminium, brass …) — the views reflect a soft studio.

## 📚 Parts library

**A part from the library is always a copy in your project** — change it there and the library stays as it is. To
change the library itself: **✎ Edit in the library** (your own parts) opens the part as a 3D model marked *📚 Library
part*; **📚 Save back to the library** keeps the change in that library part (parts already in projects stay as they
were, new uses take it). The library's own catalogue parts stay as they are: **✎ Make my own copy** makes the chosen
size a part of your own library, opened to change. The AI's `save_to_library` without a name saves a library part being
changed back.

**📚 Library** (top bar) holds real parts to build with, each with its maker, part number and order numbers:
- **Fasteners**: screws M1–M6 with several heads (socket ISO 4762, button ISO 7380, countersunk ISO 10642, pan head
  ISO 7045, slotted cheese DIN 84 from M1, hex ISO 4017), screws for plastics, nuts (ISO 4032, lock DIN 985, square
  DIN 562), washers ISO 7089;
- **ruthex heat-set inserts** (with the hole size to print), **bearings** (608-2Z and others; LMxUU), **standoffs**
  (Würth WA-SSTII M3, brass M/F);
- **panel parts** (APEM Q8 LEDs, Eaton M22 push buttons and E-stop, Neutrik D-size USB / RJ45 feed-throughs);
- **automation**: SMC CJ2 cylinders and CQ2 compact cylinders (CDQ2B ø12–ø50, bore and stroke), D-M9 auto switches for
  them, KQ2 fittings, an SY3000 valve; SICK IME12 / IME18 inductive sensors; NEMA 17 / 23 stepper motors.

Search (e.g. *M3*, *608*, *SMC*, *SICK*), choose the size (and length or stroke), and see it in 3D. Then **⤵ Put into
the assembly** on screen (the same part is used again when you put it in twice) or **◆ Open as a new 3D model**.
Parts marked **≈ outline** are drawn from their catalogue sizes as an envelope, so check the maker's drawing for
the details. The parts are drawn by the app, coloured part by part (a cylinder's rod lighter than its body). **📎 Use
the maker's model (STEP)…** attaches the real model you downloaded from the maker (SMC, SICK… — after a log-in there,
and theirs to use, not to share) to the chosen size: from then on the library puts in that exact model, in its own
colours, still with its part number in the BOM; ✕ goes back to the drawn one. *Find it at* searches the part number at the maker's own shop (SMC, SICK, SKF) and at shops that fit the part: MISUMI,
RS Components, Conrad and TME for mechanical parts; Mouser, Farnell, TME, GM Electronic, RS and Conrad for electronic ones. A library part's panel
shows its facts. **📚 Save to the library** (a 3D model's panel) keeps your own part, with its maker and part number
if bought, in `data/library/` on the server. The format for writing parts by hand is in
[library/README.md](library/README.md). An assembly's **⬇ BOM (CSV)** lists every part (inside sub-assemblies too)
with quantity, maker, part number, order numbers and mass, as a CSV that Excel opens.

## Assemblies

**＋ New assembly** (in the ＋ menu next to the part tabs) opens an assembly tab (◇), where the parts of the project
are placed together — 3D models ◆, quick parts ▤ (drawings, pictures, imports: they go in as their solid) and other
**assemblies ◇ as one unit** (a sub-assembly: its parts as placed there, joined and fastened like a part; its mass is
its parts'; STEP lists every part; an assembly cannot go into itself):
- **＋ Insert part ▾** adds a model part, as often as you like (⧉ in the list adds one more). A new one is put
  beside the others.
- **🔗 Joint ▾**: choose how the part is held — **Touch** (S: a flat face onto a flat face, centred), **Gap** (facing,
  a distance apart), **Flush** (in one plane), **Concentric** (two round faces on one axis: a pin in a hole; its
  **↕ distance** is the gap along the axis between the facing ends of the two round faces — two plates with holes
  joined this way get it filled in (touching) and you type e.g. 30; empty = it slides),
  **Parallel**, **Perpendicular**, **Angle** (two flat faces at the angle you type), **Tangent** (a round face on a
  flat one), or **🔩 Screw / pin** — then
  click a face of the part to move and the face it goes to (the face under the mouse is marked). For round faces a
  click on (or near) a **circle** — a hole's or a pin's edge — is enough: its round face is taken (a hole seen from the
  front, whose wall is hard to hit). A part can have
  several joints, applied in order: *Concentric* + *Touch* seats a pin in its hole, head on the face. Joints
  **hold**: when the other part moves or a part changes size in its own tab, the joined part follows. The panel
  lists the joints (hovering one marks its two faces, the copies are told apart: I1, I2…), with the gap / offset to
  type, ⇅ to turn it round, **↕ a slider for the gap** (a flat joint's gap; a concentric joint's distance once it is set; it catches at 0), **↻ a slider to turn the part about the joint** (a pin about its hole's axis, a part on
  its face; it catches at 90°) with **🔓 free / 🔒 locked** next to it — whether the part may still turn about the
  joint (free: ↻ turns the part and it stays free, also on a locked 🔒 joint; locked: ↻ sets the angle it is locked
  at). **⇅** on a concentric joint turns the part over end to end once, **🔒 lock** and ✕. A locked joint cannot be
  broken: the part cannot be moved by hand while it holds; moving a part held by unlocked joints asks first.
  **Double-click a joint's name** to give it your own (e.g. *ložisko na tyč*); it is shown in the list, over its
  symbol in the view and to the AI.
- **A part fixed on a moving part moves with it**: a lever fixed on a bearing (its turn locked) that turns on a
  shaft is not "fully held" — its Moves are the bearing's (*Turn about … — with Bearing*): drive the lever, the
  bearing turns and the lever goes along.
- **Joints that do not hold say so**: after every change each joint is checked where its part ended up. One that
  another joint overrides (e.g. a *Gap* of 5 mm and a *Flush* on the same lid) turns **red** with the reason —
  *"Not held — 9 mm off: J2 (Flush) holds Lid elsewhere. Change one of them, or ✕ one."* — its symbol in the view
  shows ⚠, the status bar counts them (*⚠ 1 not held*), and making a joint that fights another one warns at once.
  Joining the **same two faces again** changes that joint (e.g. Touch → Gap 5 mm) instead of adding a second one.
- **Seeing the joints**: choose a part — its joints are listed and their symbols (⧉ ◎ ∥ …) shown in the view between
  the two faces; **Ctrl+click** a second part — the joints between those two. Hover a symbol: its faces light up;
  click it: its two parts. With nothing chosen, every joint is shown.
- **Moving a joined part — only the ways its joints leave free**: its panel shows **Moves**, a slider for each way it
  can still move (e.g. a pin in a hole: *along the axis* and *turn about the axis*; a part on a face: *along X*,
  *along Y*, *turn on the face*). Slide and let go — it stays there, held by its joints, and the parts on it follow.
  A part with nothing left free says **🔒 Fully held**. *Place it by hand (breaks its joints)* is still there, folded.
  Each slider shows **where the part is** along that way (from the face or axis it is joined to — e.g. how far a pin
  sticks out of its hole), so a typed number puts it there.
- **Motion with limits**: **⇤⇥** next to a way gives it a **min** and **max** — a cylinder's stroke, a slide's ends,
  a door's swing (a turn: −360 … 360°, up to a full turn — e.g. 0 … 270°). Then the slider goes only between them (it is the drive: slide it and the parts
  on it go along), **▶** plays it from min to max and back — its **speed** (¼× … 4×) and **↻ repeat** next to it —, and **⚠ Check the travel** moves it from min to max in
  small steps and checks for collisions on the way: *"✓ Free all the way"* or *"⚠ It hits Stop (I3) from 1.25 to 20
  mm"*. It ends where it was. The AI does the same with `set_travel`, `check_travel` and `move_free {to}`.
  A part on a face is centred on it once, when the joint is made; after that it keeps where it slid, and goes along
  with the part it hangs on.
- **🔒 Lock a motion**: the 🔒 next to a free way fixes it where the part is — its joint's turn or distance along the
  axis is set, or else a new joint is added onto the part it is joined to (flat faces across a move: *Flush* / *Gap*
  at the distance they are; flat faces along a turn: *Parallel*). A toast says which joint did it; a flat-face joint
  may hold its turn too. The AI: `lock_motion`.
- **🪶 Simplified** (a placed part's *Look*): the part is shown with a coarser mesh and less data — quicker to load
  and to show; its joints still work, its edges cannot be picked; collisions and drawings use the full part. A big
  imported part (thousands of faces: an assembled PCB, a maker's STEP) is simplified by itself; untick it for its
  full data. It counts for every copy of the part in the assembly.
- **✎ Edit it here** (a placed part's panel, or double-click it): its part opens in the full 3D modeler with the rest
  of the assembly see-through around it, in place; *◇ Back to the assembly* returns. It is **🔒 Locked** per part
  until you unlock it (🔓 Editable from here), so nothing is changed by accident.
- **Joints with no tool on**: click a face (or a hole's / pin's rim) — it lights up and the Suggested table offers the
  joints it can start; **Ctrl+click a face of another part** and it offers the joints that fit the two (two round
  faces: ◎ Concentric; two flat: Touch, Flush, Gap, Parallel …; round and flat: Tangent) — one click makes it.
- **📌 Fixed in place**: the first part put in an assembly is fixed (📌 in the list): it is not moved by hand, and a
  joint made from it moves the other part. 📌 in a part's panel (or the Suggested table) fixes or frees any part.
- **📏 Measure** (assembly): click a spot, then another — the distance and Δx / Δy / Δz (corners snap); two parallel
  flat faces also give the gap between them, two round faces how far apart their axes are.
- **⧉ Duplicate as a new part** (a 3D model's *Part* panel) copies it into a new, independent part (its own tab);
  in an assembly **⧉ Make it its own part** gives a placed part a copy of its own, to change it alone. The AI:
  `duplicate_part`.
- **A STEP file's colours** (of its components, bodies and faces) come with it — in the modeler and in assemblies;
  your own 🎨 paint goes over them, and *Keep the file's colours* (in its solid step) turns them off.
- **Deleting a step others stand on** (e.g. an imported model you sketched on): *Keep them where they are* leaves a
  sketch on a fixed plane with its sizes (sizes from the deleted step's edges become fixed), an extrude up to its face
  keeps its distance; only steps that cannot be without it (roundings of its edges …) go. *Delete them too* removes all.
- **🎨 Paint** (3D model): click faces — or, with ▣ Bodies, whole bodies of an imported file — Ctrl+click for more,
  then pick a colour; ↺ takes a face's own colour off. A painted face keeps its colour when the part changes (its name
  and place) and shows in assemblies; Ctrl+Z undoes it. **🏷** in a row renames a step (3D model list) or a part
  (assembly list, its tab too).
- **Colour and see-through**: a 3D model's *Part* panel sets its colour and how see-through it is (also in every
  assembly); in an assembly a placed part can have its own (*Look*, ↺ back to its part's).
- The panel of a selected part has its x / y / z position, **Turn** sliders for X / Y / Z (any angle; they catch at
  0, ±90 and ±180°, or type an exact angle), its joints, *Join it to another part*, **◆ Open its part** (its part's
  own tab, to change it), *Reset its place* and *Take it out*. Moving or turning a joined part by hand asks before it breaks its joints (locked ones never break).
- **🔩 Screw / pin through parts** (🔩 Fasteners → *Screw / pin through parts…*; 🔩 in 🔗 Joint ▾ opens the same
  panel, ready for the click): click a point on
  a flat face where it goes in — the parts touching one after another under it are found, and the panel suggests
  what fits, with a see-through preview: **screw + nut** (a hex nut on the far side), **screw + heat-set insert**
  (in the last part, when it is thick enough) or a **pin**, M2–M5, its length chosen from the thickness. X / Y move
  the point (from the face's middle); the checkboxes end it earlier. **Add drills the holes into the parts** (a
  *Hole* step in each part's own model — clearance Ø d+0.4, the insert's hole, or the pin's) and puts the standard
  parts in, held by joints. Ctrl+Z takes back the parts and the holes. The AI does the same with `bolt_parts`.
- **🔩 Fasteners** finds where holes line up through two parts and suggests what fits, from the hole sizes (as
  printed): an **M2–M5 screw with a heat-set insert** (a clearance hole in the top part, an insert hole below), a
  screw alone, or a **dowel pin** (equal holes) — with a standard length that fits. Hover a suggestion to see its
  holes; *Add* or *Add all* puts them in as standard parts of the project (a socket-head screw, an insert, a pin),
  held by joints: the screw on the hole's axis, its head on the part; the insert flush with the face. They follow
  when the parts change. In the joints list a fastener is **one row** — *🔩 M3×16 screw + M3 nut · through Lid, Base*
  — not its four joints; its **✕** (or *Take it out* on the screw or the nut) takes out the screw, the nut / insert
  and the holes that were drilled for it.
- **⚠ Collisions** finds where parts go into each other (touching faces are fine). It is checked a moment after
  every change, so the button itself says it: **⚠ 2 collision(s)** in red, or **✓ No collisions** in green. Click it
  for the list — each pair and how much (mm³), the parts glowing red and the overlap boxed in red; hover a row for
  just that pair, **click a row: the view goes to that collision**, the other parts see-through (click again or
  *⤢ Show all* to go back); ↗ chooses the two parts (their joints and moves). Slide a part and see it clear. Big imported parts (a whole assembled PCB) are checked quickly: two of them overlapping in many places show an estimate (**≈**) after a change — *↻ Check again* computes it exactly.
- **🎨 Paint** colours faces of the placed parts (▢ Faces) or whole parts (◆ Whole parts) in this assembly: click
  them, Ctrl+click for more, pick a colour. The parts keep their own colours in their tabs and other assemblies.
- **✂ Section** cuts every part along X, Y or Z (a slider moves the cut, ⇄ shows the other side).
- **Explode** pulls the parts apart to look at them; their placement does not change. **💥** on a part in the list
  (shown while exploded) chooses whether it moves: off, it stays in place and the others move away from the parts
  that stay (a lid lifts off its box); **Ctrl+click** — only this one moves (again: all of them). Saved with the
  assembly, undoable. **Respect joints** (next to the slider): a joined part moves only the ways its joints leave
  free — a pin comes out of its hole along the axis, a bearing slides off its shaft — and goes along with the part it
  is on; a part held fast stays on it.
- The **parts list** shows each part, how many, its material and mass, and the total. **Export** gives STL (all
  parts as placed, in one file) or STEP (each part as its own body).
- Changing a part in its own tab updates the assembly. The assembly is saved in the project. Undo / redo work as
  everywhere.
- The AI chat can build assemblies too: *“put the pin into the plate”* — it inserts the parts and snaps their
  faces together (tools new_assembly, insert_part, snap_faces, place_part, get_assembly; skill assemble-parts).

## AI assistant (✨ AI tab)

Tell Claude what you want — *"make a 90 mm cookie cutter from C:\pics\star.png with a hanging hole"*, *"cut a
5 mm hole 8 mm from the top"*, *"engrave my name on the flange and export an STL"* — and it works on the part in
the app: every change appears in the 3D view at once and **↶ Undo AI change** takes it back.
On a quick part the chat is the **✨ AI** tab of the left panel; in a 3D model or an assembly the **✨ AI** button in
the top bar opens the same chat (the same conversation) at the right side — ✕ closes it.

**🕘 History** (in the chat's top bar): after each AI turn that changed something, the server keeps the whole project
(every part — 3D models, assemblies, drawings) in `data/history/` next to `server.py`, with the message that made
it. The list shows them newest first; **Load** opens the project as it was then — the project on screen is kept in
the history first ("before loading"), so nothing is lost. ✕ deletes a state; the oldest go after 300.

**Photos**: attach photos to a message with **📎 Photo**, by pasting (Ctrl+V) or by dropping them on the chat.
Thumbnails show before you send, and ✕ removes one. You can attach up to 5 photos of up to 10 MB each; very
large ones are scaled down to 2400 px. Claude sees the photos and can trace one into a part (for example
*"make a cookie cutter from this, 90 mm wide"*). Photos are saved in `data/agent/photos/` so the tracing tools
can open them.

- It runs on **your own Claude Code** installation and sign-in (a Claude Pro / Max subscription or an API key):
  the app starts `claude -p` in the background — found on the PATH, in `~/.local/bin`, or the newest copy
  bundled with the VS Code / Cursor extension; set `AUTO3D_CLAUDE` to point elsewhere and
  `AUTO3D_CLAUDE_MODEL` to choose a model. The app never sees your credentials (Claude Code signs in through
  Anthropic's own flow); usage counts against your own plan. If you give the app to others, each of them signs in
  with their own account.
- Claude gets **only the app's tools** ([auto3d/agent_tools.py](auto3d/agent_tools.py)), through the app's own MCP
  server ([auto3d/mcp_server.py](auto3d/mcp_server.py)): read the part, look at the 3D view, open files / the
  sample, trace a picture and use an outline, set dimensions, choose what to make, add / change / remove 3D
  objects, 2D shapes, design layers and point dimensions, check the printer, export, undo.
- **3D models too**: it can list and open the parts of the project and start a new 3D model. It builds a model
  step by step: sketches from rectangles, circles and polylines (sizes locked), extrude, revolve, hole, fillet,
  chamfer and shell. It finds faces and edges by description (`find_refs`: "the top face", "the edges of that
  face", "the round edges"), changes, deletes or turns off steps, and prepares a printing copy. Example: *"make a
  50 × 30 × 4 mm plate with a 5 mm hole in the middle and 2 mm rounded corners"*.
- **Smooth shapes**: a sketch can hold **smooth curves** (splines through points) besides lines and arcs — draw one
  with **〰 Spline** (S) in the sketch toolbar: click the points it goes through, Enter / double-click ends it, its first
  point closes it, a line's end joins it. The AI draws
  a whole outline as one `profile` — straight parts, arcs through a point and smooth parts through points — and
  revolves or extrudes it. The curve becomes one true B-spline in the solid, so a vase, a knob or a duck's body is one
  clean smooth surface, not many little faces. The sketch shows the curve and its points can be dragged.
- **Everything the app does, the AI can do**: besides modelling, assemblies, the library and collisions, it colours
  parts (`set_look`: colour, see-through) and single faces (`paint_faces`), in a model or per placed part in an
  assembly; moves a joined part along its free ways (`move_free`); keeps a model in the library (`save_to_library`).
- **The rest of the app** is there too: 2D drawings — `open_file` opens a DXF / DWG, a Gerber / drill file, a
  Gerber set or ODB++ job (.zip / .tgz) or a folder of loose Gerber files as a 📐 drawing — (`get_drawing`,
  `drawing_find` by filters, `drawing_delete`, `drawing_add` lines and circles, `drawing_units`, `drawing_layers`:
  show / hide, colour, a new layer; `drawing_set_size`, `drawing_use` as a sketch or a quick part), joints changed or removed (`edit_joint`,
  `remove_joint`), `measure` between faces, the view for its screenshots (`set_view`: a section, explode, size labels),
  parts renamed or deleted, and files: `export` stl / step / pdf / **3mf** / **bom** / **dxf**.
- **Problem reports**: when something in the app does not behave as expected, the AI writes a dated report
  (`report_problem`) into **RealSWReports/** next to `server.py`: what happened, what was expected, the steps, the
  workaround — a **bug**, a **tool request** (no tool fitted, so it worked around it: the tool it would want) or a
  **ui** note (you could not find something, or a control surprised you). It cannot write files itself (no file
  tools), so the server writes them — with the **app version** it
  came from (`auto3d/version.py`: VERSION and the git commit, e.g. *0.9.0 (main @ 2900fde, 2026-10-27)*; also
  `/api/version`).
- **The AI asks with buttons**: before a new design it asks (unless you said it) what it is for — *automation / a
  machine*, a *functional 3D print* or a *graphic / decorative* model —, whether it is 3D printed, and whether it must
  be *easy for a person to edit* (simple sketches with few sizes each) or may be built any way. The question shows in
  the chat as buttons, its **★ recommended** option first; a click answers (*✎ Other…* to type). It asks the same way
  whenever a choice is really yours. Then it works by the skill for that kind of design: **automation** (made to be
  manufactured — standard stock and cutters, standard holes and fasteners, fits, library parts, a working assembly
  with travel checks, a PDF drawing per part), **functional print** (orientation for strength, walls, overhangs,
  inserts, material) or **graphic print** (details that print, few supports, colours / 3MF); **fits-and-tolerances**
  holds ISO 286 fits (H7/g6, k6, p6 …), ISO 2768 general tolerances, clearance / tap-drill holes and counterbores.
- **The GUI for the AI**: `gui_state` lists what you see (every button, slider, box, joint name, its state, greyed
  out or not) so the AI can tell you exactly where something is; `gui_action` clicks or slides one the way the mouse
  does — so it can check the app behaves like its tools. It also clicks, double-clicks or drags **at a point** of the
  view (picking a part or a face in 3D, a dimension, view or title cell on a drawing sheet — `at_mm` on the paper) and
  presses **keys** (Delete, Enter, Escape, ctrl+z); a sheet's dimensions, views and title cells are listed too. A **locked 🔒 joint** is greyed out in the panel (only 🔒
  unlocks it) and the AI cannot change it either.
- **Library first**: Claude designs like a mechanical engineer. Every bought part (screws, nuts, inserts, bearings,
  standoffs, panel parts, SMC pneumatics, SICK sensors, motors) comes from the 📚 parts library (`library_search`,
  `library_add`), with its real part number in the BOM. Only the parts to be printed are drawn, around the bought ones.
  It joins the parts so they move as in reality (`get_assembly` says what can still move, or `fully_held`) and checks
  `check_collisions`.
- **Skills**: the workflow guides in [agent_plugin/skills/](agent_plugin/skills/). The workflows are model-a-part,
  change-a-model, from-picture, print-prep and assemble-parts. Design know-how sits in **mechanical-design** (bought
  parts first, fits for bearings / inserts / screws, printable walls, joints and collisions, the BOM) and
  **automation-design** (cylinder force and stroke, sensor mounting and range, motor mounts, panel holes). They are loaded as a Claude Code plugin for the chat
  (`--plugin-dir`), and Claude reads the matching one before a task. The MCP server serves the same texts
  as the `get_guide` tool and as MCP prompts, for other clients like Claude Desktop.
- Built-in file and shell tools are switched off (`--tools Skill` keeps only the skill loader), only this MCP
  server is loaded (`--strict-mcp-config`), your global hooks and settings are not (`--setting-sources local`),
  and the session runs in the empty folder `data/agent/`.
- How it fits together: the chat panel → `POST /api/chat/send` → one Claude Code process per chat (stream-json in
  and out, streamed to the page as Server-Sent Events) → the MCP server → `POST /api/agent/call` → tools that change
  the part are relayed to the open page (long-poll), applied there like a user edit and answered; reading files,
  tracing pictures and writing exports run on the server.

The same MCP server works from **Claude Desktop or Claude Code** directly (the app must be running and open in a
browser) — e.g. in a Claude Code / Desktop MCP configuration:

```json
{ "mcpServers": { "auto3d": { "command": "py", "args": ["C:/path/to/Auto3DModeler/auto3d/mcp_server.py", "--url", "http://127.0.0.1:5173"] } } }
```

## Every part works the same way

Whatever it comes from, a part has the same tabs and tools; only the top of the **Part** tab (its source)
differs:

| Source | Part tab source section | Scales with |
| --- | --- | --- |
| PDF drawing | the drawing (its dimensions drive the part) | the drawing's dimensions |
| Picture | the traced outline, clean-up, *Make*: cookie cutter / solid shape / custom | width / height |
| DXF / DWG | the drawing's closed regions in real size (mm), clean-up, *Make* … | width / height |
| STL / OBJ / STEP | up axis, 90° turns, mirror, slice height | scale % |

Below it, for every part: **3D objects added to the part** (booleaned on: profile / profile band offsets,
cylinders, boxes, bars, text — placed and sized by clicking on the part, see *Pick on the part*) and **2D shapes on
the profile** (added to / cut from the profile before it is built; not for 3D files).

**Dimensions** — **＋ Dimension** (`D`): on PDF drawings the parametric dimension tool (edges / corners); on every
other part a dimension between **two picked points** (corners and faces snap), as many as you like, as the
distance or along X / Y / Z. Typing a value **scales the part** so the dimension fits — pictures / DXF in X and Y
(heights stay), 3D files uniformly; together with everything placed on it (shapes, objects, other dimensions).
On PDF drawings added point dimensions are reference values.

**Measure** — **📏 Measure** (`M`): two clicks on the part give the distance, Δx, Δy and Δz; *Keep as dimension*
turns it into one. In 2D: 📏 in the outline editor (picture pixels and mm) and in the enlarged Drawing view
(mm, for pictures and DXF drawings).

### Imports

- **DXF**: lines, arcs, circles, polylines, splines and ellipses (also in blocks) are joined into closed regions
  (even-odd: holes, islands in holes), in real size from `$INSUNITS` (unitless = mm). Open lines are reported and
  ignored. Needs `ezdxf`.
- **DWG** is a closed format: it is converted to DXF with the free **ODA File Converter** or LibreDWG's `dwg2dxf`
  when one is installed; otherwise the import says so (or save the drawing as DXF).
- **▣ Solid from a file** (3D model) adds a STEP / STL / OBJ as a step: **▣ Joined** to the part, **⬚ Cut out** of it
  (a cavity it fits in exactly) or **👁 Reference** (drawn see-through, not part of the part — build a cover or a holder
  around it, then cut a copy of it out). An STL / OBJ is made an exact solid (up to 60 000 triangles). Assemblies
  insert one with *＋ Insert part ▾ → From a file*. The files are kept by the server and carried in the project file.
- **STL / OBJ / STEP as a quick part** (STEP is tessellated with `cascadio` / OpenCASCADE): the part is cut into flat slices at every
  flat face — exact for parts whose walls are vertical between flat faces (plates, brackets, cutters), slanted /
  curved walls become steps of the *slice height*. The file is kept on the server (`data/imports/`) and inside the
  project file, so projects reopen anywhere. Design layers need a flat part; on 3D files use 3D objects (e.g.
  subtract a text object to engrave it).

## Outline from a picture

**Open picture** (or drop a picture with no part loaded / with `Shift`) opens the outline wizard
([auto3d/outline.py](auto3d/outline.py), [web/js/outline.js](web/js/outline.js)):

1. **Candidates** — several independent segmentations run on the picture: a background colour model learned
   from the picture border (lightness weighted less, so shading and shadows matter less), GrabCut, colour
   clustering, brightness / saturation thresholds and edges. Thin uniform frames around photos are removed
   first. Each connected region is a candidate; the strongest outer regions are refined with GrabCut seeded
   from them (separates drop shadows from the object edge). Candidates are ranked by edge contrast along the
   boundary, how many method families agree, size and solidity; regions inside a bigger candidate (inner
   decoration) and regions touching the picture edge rank lower. 3–10 candidates are shown with a confidence.
2. **Help the detection** — *✚ inside object* (only outlines containing the point are kept), *✖ not this*
   (click a shadow, the background or a neighbour: outlines containing it are dropped and GrabCut treats it as
   background), *▭ box around object* (only that area is searched — handy for one object among several, or one part
   of an object), *object / background colours* with the eyedropper (nearest-colour classification, refined by
   GrabCut); colour tolerance, smoothing, inner holes. Clicking an outline on the picture selects it.
3. **✎ Edit outline** — take the selected candidate (or **Empty** to draw from scratch) and change it by hand.
   Pick a **tool** — **polygon** (click corners; double-click, `Enter` or a click on the first point closes it,
   right-click / `Backspace` removes the last point, `Esc` cancels), freehand **lasso** (drag a loop) or **brush**
   (adjustable size) — and a **mode**: **＋ Add**, **− Remove** or **✂ Cut out** (keep only what is inside the
   polygon / loop — draw around the part you want). Keys: `P` `L` `B` for the tools, `1` `2` `3` for the modes,
   `Ctrl+Z` undo. Every candidate has **＋ / −** to add it to or cut it from your edit (e.g. body ＋ wheels − shadow).
   The edit is traced into the same smooth outline (server-side, [`outline_from_mask`](auto3d/outline.py)) and
   listed as **✎ Your edit**.
   **Zoom** with the mouse wheel (around the cursor, up to 20×) or − / + / Fit (keys `+` `−` `0`); **pan** by dragging
   with no tool active, with the middle mouse button or with `Space` + drag.
4. **Real size** — width or height in mm (aspect kept; editable later in Dimensions like any dimension, with an
   optional aspect lock).

**Back to the outline** — **✎ Edit outline** (3D view toolbar, Outline → 3D panel, Drawing tab or the enlarged
drawing) reopens the editor on the outline the part is made from: it is listed first as **● In use** (or
**✎ In use — your edit**, with the painted mask restored so you can keep editing), selected, with your detection
hints; fresh detections appear below it. **Apply to the part** keeps the part's scale (mm per picture pixel), so
what you did not change keeps its real size — type a size to rescale; dimensions, shapes and objects stay. The
editor state is saved in the project file (`outline_editor`: mask + hints, next to the picture), so it survives
**Save project** / **Open project**.

**Drawing tab** — **⤢ Enlarge** (or a click on the drawing) shows the PDF page or the picture with its outline
full-window, with wheel zoom (around the cursor), drag to pan, double-click / `0` to fit.

**Outline → 3D** (right panel) — what is built from the outline:

| Make | Result |
| --- | --- |
| Cookie cutter | wall (thickness, total height) with a thinner cutting edge on top, and a flange on the bed. The inside of the wall is exactly on the outline (+ clearance), so cookies come out at the size you set. *Mirror outline* if the cookie must match the picture after turning the cutter over |
| Solid shape | the whole shape extruded (the cookie itself, a plaque, a base), grown/shrunk by an offset; design layers (emboss / engrave patterns, logos) apply to its top |
| Custom | a list of **3D objects** built top-down with booleans: each adds (∪ union), removes (− subtract) or keeps only the overlap (∩ intersect) with everything above it |

3D objects are extruded regions between a bottom and a top height: the outline filled (with an offset), a
**band** between two offsets of the outline (walls, rims, flanges), a circle / cylinder, rectangle / box or
line / bar (filled or as a ring). **Edit as 3D objects →** turns a preset into its objects to modify it
(e.g. cut a hanging hole through the flange, add a handle bar across the cutter).

**Outline clean-up** (Outline → 3D, in mm, applied to the traced outline only): *fill holes*, *close gaps*
(bridges slots and notches narrower than 2 × the value — a cookie cutter cannot cut those anyway), *round
corners* (also removes spikes / necks thinner than 2 × the value), *simplify*, keep *all pieces* or the *largest
only*, *convex hull*. Changing the outline afterwards (**Change outline…**) keeps size, shapes and objects.

**Pick on the part instead of typing** — every 3D object and 2D shape has **⌖** buttons next to its heights
(*bottom / top z* = extrude from / to), its centre and line ends: click ⌖, then click the part. A flat face gives
its exact height, a click near a corner snaps to it (10 px, also across edges between faces), on walls the
height snaps to the nearest face edge; a label shows what is under the cursor (`corner · x … y … z …`). Orbiting
still works while picking (only a click picks); `Esc` cancels. New cylinders / boxes / bars / text (and 2D
shapes) are **placed by clicking** where they go: a 3D object then stands on the clicked top face (3 mm high,
text 1 mm) or hangs from a bottom face; `Esc` keeps the default place.

**2D shapes on the outline** (circles, rectangles, lines, **text**, **＋ Hole** for hanging) are added to or cut
from the outline itself before anything is built, so a cookie-cutter wall follows them too. **Text** is rendered
in the browser in the chosen font (any installed font; bold, several lines) and traced, so it can also be a
**3D object** — e.g. a name raised on the cutter's flange or cut into a plaque. Shapes and primitive objects can be
dragged on the part; `Delete` removes the selected one. Export, printer fit / splitting and projects work as
for drawings.

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
- **Undo / redo**: `Ctrl+Z` / `Ctrl+Y` (or `Ctrl+Shift+Z`), or ↶ / ↷ in the 3D toolbar — for every change:
  dimensions, objects, shapes, design layers, bends, outline edits and the AI's changes (each AI change is its own
  step). A drag or a scrub is one step (a step is recorded when the rebuild has settled). Opening another part
  starts a new history.
- **Select and delete**: click any object in the 3D view — a hole, post, bar, text, profile offset or band, a
  design layer's mask — to select it (it is highlighted and opened in the Part tab); `Delete` removes it, `Esc`
  deselects. Objects of a cookie-cutter / solid preset belong to the preset (use *Edit as 3D objects →* to change
  them). Dimensions you added and point dimensions show a **✕** on their 3D label (or press `Delete` while pointing
  at the label); the drawing's own dimensions drive the part and cannot be deleted.

### Adding dimensions

A drawing's own dimensions drive the part, so they cannot be deleted, but they can be **hidden**: ✕ on the
label (or *Hide* in Dimensions) removes it from the view. The size still applies, and *Show* in the Dimensions
tab (group *Hidden*) brings it back. Dimensions you added are deleted with ✕.


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

Layers are real geometry and are included in STL/STEP. Masks can be dragged on the part (with snapping); new
shape / image / outline layers are placed by clicking where they go.

**＋ Outline** traces an object in a picture with the outline editor (detection, hints, hand edits — see
[Outline from a picture](#outline-from-a-picture)) and uses that outline as the mask, e.g. to engrave a cookie's
silhouette into a plaque or a PDF part. **✎ Edit outline…** in the layer reopens the editor on it (edit and hints
kept, scale kept); the picture and editor state are saved in the project (`layer_pictures`).

On parts made from a picture, layers go on the **first object** of Outline → 3D (for a cookie cutter: the
flange — *front* = its top, *back* = its bottom); the 3D design tab says which one. Reorder the custom objects to
decorate another one.
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
of the bend zones where possible and each piece is exported bent, levelled at its middle (curved parts
usually need supports; alternatively print flat with the bends hidden and heat-bend).

**Joints in a bend** (unavoidable for rolls): joints are built on the flat part and bent with it, so
both sides match exactly on the curve. Because curved pieces are pushed together along the bend rather
than straight through the thickness, integral joints (dovetails, puzzle knobs) on curved seams get extra
clearance = thickness × joint depth ÷ bend radius. Separate connectors on curved seams (butterfly keys,
dowels, splice plates) are printed curved to fit their curved pockets and are grouped by curvature.
The split preview shows pieces and connectors in their assembled, bent position.

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
pieces and connectors, material conservation, wall checks, joints through engraved patterns), and outlines from
pictures (detection on synthetic photos with frames, shading and icing-like texture, colour hints and seed
points, the `pernicek.png` sample; cookie-cutter / solid / boolean object volumes, watertight meshes, mirroring,
2D shapes, invalid input, the HTTP endpoints).

## Current limitations

- Single view, straight-line profiles extruded to a constant thickness; arcs/holes (Ø, R), angled
  dimensions and multi-view drawings are reported but not modelled yet.
- Design features and joints are vertical extrusions (no chamfers/rounded profiles, no round dowels).
- Very dense curved patterns over a large face (hundreds of circles/scales) can take several seconds to rebuild.
- Scanned (raster) PDFs and PDFs with text converted to outlines can't be read (no OCR).
