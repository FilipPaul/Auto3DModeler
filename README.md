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
- a **CAD / 3D file**: STL / OBJ / 3MF / STEP / IGES files — a **STEP or IGES opens as a 3D model** with its exact
  solid as the first step (sketch on its faces, drill it, build a cover around it; a 40 MB STEP in under a minute);
  STL / OBJ / 3MF open as a quick part (sliced, for printing; Shift+drop a STEP for that too; a 3MF from a slicer or our
  own export: all its objects, placed as in the file). A **STEP assembly** — what
  SolidWorks, CATIA and Solid Edge export (their own SLDASM / CATProduct / ASM files are closed; save as STEP AP214 /
  AP242 there) — asks first: **Open as an assembly** makes a 3D model part per different part (a screw used 22 times
  is one part), an assembly ◇ with a placed part per placement, sub-assemblies nested, the file's names and colours;
  **Open as one body** opens it as before. A big tree (an assembled board: hundreds of parts) offers one body first
  and, as an assembly, shows its parts 🪶 simplified. An assembly STEP whose parts are files of their own (CATIA
  writes it so): pick it **with its part files** at once (or drop them all) — they open as one assembly;
- a saved project.

You can also drop a file on the view. To model a part from scratch, click **＋ New 3D model** (see
[3D model workspace](#3d-model-workspace)).

**Čeština / English**: the **CZ / EN** button at the right of the top bar switches the language live. The choice
is remembered; the first time, the app uses the browser's language. Your own text (the project name, chat
messages, the names you type) is never translated. Dimension names that come from a drawing are only shown
translated; the project file keeps the originals. Translations live in `web/js/i18n.js`. Exact texts go in
`CS`. Texts with values go in `CS_PATTERNS`, where `{}` is a value; values that are known texts are translated
too. Text with markup goes in `CS_HTML`. Messages from the server and the CAD kernel (a refused step, an import
error, a warning) are shown in Czech too: `tests/test_i18n_messages.py` collects every message text from the
Python sources (an f-string's values as `{}`) and fails when one has no Czech entry, so add it with the message.

**Long work shows progress**: importing or rebuilding a large 3D file, making a drawing sheet, building an
assembly's parts or splitting a part for printing shows a progress box with **Cancel** (in whichever workspace is on
screen). Cancel stops that job in the CAD kernel at once (only its process restarts; other parts' jobs go on), the box
says *Cancelling…* and is gone — the work is not started again on its own. A quick part goes back the way it was; a 3D
model keeps its last result with *Cancelled — ↻ Rebuild*; a sheet says *Cancelled* with ↻ Try again; the next change
builds as usual. The ⚠ Collisions list has ✕ Stop while it checks.

**What is working now (⚙ N)**: while anything runs — a part being built, a file read, a drawing made, a collision
check, also from another window or the AI — the top bar shows **⚙** with how many jobs; nothing when idle. Click it:
each job in plain words, which part, how long it has run (live), waiting or running, and **✕ Stop**. A job running
over 3 s with no progress box on screen makes the ⚙ pulse, so a busy app does not look frozen. Curved or slanted 3D imports get a slice height chosen
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
**Arrange the left panel as you like** — the project tree, the workspace's own panel (the steps, the assembly's
parts…) and the **suggestions** table are widgets: **drag a header** into the left panel to dock it there (a line shows
where it goes; the 📌 in the ☰ tree or on the suggestions does it at once), or onto the view to let it **float** over
the drawing. Docked widgets share the height (drag the line between them), **▾** folds one to its header, the panel's
right edge sets its width. The project tree starts docked on top (☰ folds it; ⋯ › ☰ puts it back behind the button).
A floating widget moves and resizes like the other boxes and has two opacities: its **panel** (background, border,
header — at 0 % only its content floats over the view; **Ctrl+wheel** on its header) and its **content** (rows,
buttons, text — 30 % at least, whole while the mouse is over it; **Ctrl+Shift+wheel**), also as two sliders in its
**⋯** menu. The layout is remembered per workspace; **⋯ › ↺ Default
layout** puts everything back. A double-click on a row of the project tree renames the part.

**Snap and Select filters** (the row at the bottom of a sketch, remembered): **Snap:** *Points, Midpoints, Centres,
Origin, On shapes, Guides, Grid* — where a point you draw (or drag) lands; *Grid* off puts it exactly
where you click, Alt held snaps to nothing. On a part, **On the part:** *Corners, Edge midpoints, Centres, Quadrants,
Edges* says which of the part's points a drawn point catches — the same choice as the 3D view's Snap row (turned off
there, off in the sketch too); while you draw, the part's points that can be caught near the mouse are marked. **Select:** *Points, Midpoints, Origin, Lines, Circles / arcs, Part edges*
— what a click may pick in ⬚ Select, ↔ Dimension and ⟂ Relations. In a narrow window the names turn to icons (they
stay in the tooltips). The origin and a line's **midpoint** can be
picked and dimensioned from (the distance is held from the middle as the line changes). A dimension can be dragged by
its label or **by its dimension line**. A circle or arc shows its size as **R or Ø** — *⇄ Show it as a radius /
diameter* (or R ⇄ Ø in its size box); a typed value is taken that way. Drag a round size's label anywhere: dropped
**inside the circle** it becomes a diameter across it, **outside** a radius from the centre. **Drawing snaps** to points, a line's
**midpoint** (the new point stays at the middle), anywhere **on a line, circle or arc** (it stays on it) and the
part's edges — off the grid too — the place named at the mouse; the Snap filters say what it snaps to. **Guides**: in line with a point (its x or y — a
corner, a line's middle, the origin) or on the extension of a line, the cursor catches there and a temporary dashed
line shows what it lines up with (two at once: where they cross).

**↕ Plane at** (a sketch on a base plane) moves the sketch plane along its normal; *(+ = +Z)* says which way.
Point at it (or type in it) and an arrow shows that direction — ⊙ / ⊗ when you look straight along it; otherwise
it stays hidden, out of the way of drawing.

**◫ Planes** in the 3D model's toolbar shows or hides the (faint) Top / Front / Right planes — remembered; they show
anyway while a sketch plane is being chosen.

The tool buttons are coloured by what they do: make (blue), modify (amber), copy (purple), details (teal),
define / join (green), look and check (grey).

**⊂⊃ Slot** (sketch): click the centres of its two round ends, move out to its width and click — two straight
sides and two half circles that stay a slot (sides tangent, ends equal) when you size it.

**𝐓 Text** (sketch): puts "Text" 10 mm high in the sketch — type your text and its height in the panel, drag it
where it goes, then ⬆ Extrude it (raised letters, or cut in on the part). The letters' holes (A, O …) stay open.

**⇳ Midway** (✏ Sketch, while choosing where to sketch): click a flat face, turn the view, click the face across
from it — the sketch goes halfway between them (a rib or a hole centred in a part) and stays in the middle when the
part changes.

**Measured from a corner or the part's origin**: a sketch on a face has *Origin: ◎ Face centre | ⌜ Corner | ⊕ Part
origin* in its bar (the face's centre is the middle of its outline's box — holes cut into the face do not move it). ⌜ Corner puts the sketch's 0, 0 on the face's lower-left corner (it follows that corner when the
part changes), ⊕ Part origin on the part's own 0, 0, 0 (so the numbers are the X / Y you see; a hole at (30, 10) stays
there when the block grows the other way). What is already drawn keeps its place — its numbers change, and sizes to
the origin now measure from the new one; Ctrl+Z takes the switch back. ◎ Hole has the same choice as *From: ⇤ Edges |
⌜ Corner | ⊕ Origin* (Edges: each hole from its nearest edges, as before). The AI gives `origin: "corner"` /
`"world"` / a • reference point.

**Hover marks** (3D model and assembly, no tool on): the edge under the mouse lights up (a line or a circle), and the
snap points of the step (in an assembly: the face) under it show as small green dots — corners, edge middles,
centres (and ◔ quadrants of circles, once switched on — off by default, so a click on a rim takes the rim). The row bottom left switches them: Snap (what Measure and a click catch) and
Hover (⟋ Edges, • Snap points); both are remembered. Hovering stays quick on big parts and assemblies: the 44 MB board
(almost a million triangles) or a model with real threads answers the mouse at once instead of freezing for seconds —
the part is searched through a tree of its triangles, built while the app is idle after it opens.

**🖨 Print check** (3D model toolbar): marks what will not print well as the part lies on the bed — overhangs over 45°
in red (they need supports, or turn the part) and walls thinner than the minimum you set (1.2 mm by default) in
orange — with their areas and the thinnest wall. It follows the part as you change it.

**Section A–A**: on a part's sheet tick *Section A–A* — the part cut through its middle and seen from the right, the
cut faces hatched, in the right view's place; the cut is marked A–A on the front view. Its edges can be dimensioned
like any view's.

**Exploded assembly drawings**: on an assembly's sheet tick *Iso view exploded* — the iso view shows the parts pulled
apart (a sub-assembly moves as one), with the balloons on them; the front and top views stay assembled.

**Angles on the drawing**: with ＋ Dimension, click two edges that meet at an angle (a slanted edge and the one it
meets): an angle dimension, an arc round their corner — drag it closer or farther.

**Fits on the drawing**: select a Ø dimension on the sheet and choose its *Fit* — H6 … H9 for a hole, f7 / g6 / h6 /
k6 / m6 / p6 for a shaft (a pin, a boss, an axle); it is drawn *Ø8 h6* and the panel tells its deviations.

**⊿ Rib**: a gusset in a corner — draw one line in a sketch across the corner (e.g. on the Right plane through the
plate and the wall, from the wall to the plate), then ⊿ Rib and its thickness: the side of the line that closes
against the part is filled, half the thickness each side of the sketch plane. When both sides close (a line across a
bore), the smaller piece is filled; *⇅ Flip direction* takes the other. A click on such a line in the view (or on its
sketch in the list) suggests *⊿ Rib from this line*.

**⬆ Extrude this face**: click a flat face of the part — *⬆ Extrude this face* (second in the suggestions) pulls the
whole face out 10 mm, its holes kept; type the distance, slide it, or drag the orange arrow's tip in the view. *⇅ Flip
direction* makes it a cut that deep into the part instead. OK leaves two ordinary steps — a sketch of the face's
outline and its extrude; the outline follows the face when earlier steps change it. Cancel leaves nothing.

**𝑥 Parameters — sizes by name**: any number you type for a size — an extrude's distance, a hole's Ø, a fillet's R, a
pattern's count and spacing, a size label of a sketch (or on the part), an assembly joint's gap or angle — may also be
an expression of the project's parameters: `L`, `L/2 + 5`, `=D`, `(L - 2*t) / 3` (+ − × ÷, brackets; `mm` / `°` after
a number are skipped). Typing `L = 100` in such a field makes the parameter L (and uses it there). The field keeps the
expression and shows it with its value (*L/2 = 50*); a sketch's size label shows *L/2 = 50* too. The **𝑥 Parameters**
widget in the left column (3D model and assembly; there once the project has a parameter — dock, float or fold it like
the others) lists them: `L = 100`, `t = L / 20 = 5`; change one there (Enter) and every part that uses it is built
again — the one on screen at once, the others in the background (⚙ lists them by name), an open assembly places its
parts again. Ctrl+Z takes the change back. A bad expression (*L/*), an unknown name or parameters that refer to each
other in a circle (*L = t × 20* while *t = L / 20*) are refused with a message and the old value stays. ✕ deletes a
parameter (the numbers that used it keep their values). The parameters are saved in the project file.

**⟋ Draft**: tilts an extrude's side walls by a few degrees (they lean in going up from its base; negative: out) so a
moulded or cast part comes out of its mould — choose the extrude (or click one of its walls) and the angle. (Or give
the extrude its *Draft* right away in its panel.)

**✂ Split**: cuts the part in two along a plane — by default across its longest side, in the middle. Choose Top /
Front / Right (through the part's middle; Offset moves it) or click a flat face: a face inside the part (a step's
floor) cuts along itself, an outer face cuts halfway to the face across (⇳ Midway picks that face yourself; it
follows both faces). **Keep**: ✂ Both (two bodies in one part, shown in two shades while you choose — paint by body,
mass and STEP see both), This side (where the arrow points) or Other side. On a clicked flat face with no tool on,
*✂ Split here* is under The part. With Both, *⧉ Make each piece its own part* adds two model parts, each with this
part's steps up to the split and one piece kept. The cut faces are named `<step>:cut:0` / `:1`, so later steps
(a sketch on the cut, a lid's lip) follow them.

**The step tree** (left, like SolidWorks / Solid Edge): one line a step, a small icon coloured by what it does — green
adds material (Extrude, Revolve, Loft, Rib…), red cuts (cut, Hole), blue rounds edges (Fillet, Chamfer), teal changes
faces (Shell, Draft, Split), purple repeats (Pattern, Mirror), grey-blue a sketch, yellow a reference. A step shows the
sketch it is made from under itself (**▸** opens it, **▾** folds it; remembered); a second step made from the same
sketch, and what a Pattern / Mirror repeats, show as lighter **links** (🔗 — a click goes to the step). **Reference** at
the top holds the Top / Front / Right planes (✏ or a double-click: a sketch on it) and the reference points. A click on
the part (or on a sketch's lines) chooses its step in the tree — folded rows open, the row scrolls into sight; a click
on a row tints its faces (a sketch: its outline lit), the mouse on a row lights them lightly.

**Reorder steps**: drag a step up or down the step list (a step with its sketch: both move). A move that would put a
step before one it uses is refused (it says which), and one after which the model no longer builds is taken back;
Ctrl+Z undoes a move.

**⏮ Rollback bar** (as in SolidWorks / Solid Edge): the thin line with a grip under the last step. Drag it up between
two steps and the part shows its state after that step — the steps under it are greyed (*potlačené do konce*: kept,
not built), and a new step (a sketch, a hole …) goes in right at the bar. Drag it back down, double-click it, or
**⤓ To the end** (under the tree) and every step is built again. A right-click on a step: **⏮ Roll back to here**. The
keys ↑ / ↓ / Home / End move a focused bar. Its place is saved with the part and is one undo step; the status line says
"Rolled back after …". Steps above (and under) the bar can still be changed. As in SolidWorks, the part is used **as
the bar stands** everywhere: the Export menu (STL, STEP, IGES, GLB, OBJ, 3MF, PDF), 🖨 Prepare for 3D print (and its
split), assemblies and drawing sheets leave out the steps under it. So it never surprises you, it is said: the Part
panel and the Export menu show "⏮ As the history bar stands: without the last 2 steps (Extrude 2, Extrude 3)" (the menu's
items get a ⏮ mark), the export's message repeats it, the printing copy's 3D print tab keeps the note, and an assembly's
part panel and a drawing sheet say "⚠ The part is rolled back in its history". Put the bar at the end (⤓ To the end) to
export the whole part. The AI sees it in get_model (rollback) and moves it with `rollback {to: step id | "end"}`.

**Suggestion-based**: most basic tasks of the 3D model are a click on something and a row of the Suggested table.
With **nothing chosen** it says the **next step** (a few rows, ranked by what you just did: an empty model — ✏ Sketch
on a plane…; a sketch not used yet — ⬆ Extrude it; after a hole — ⁂ Pattern the last hole; else a sketch on a face, 📄 Drawing,
◎ Hole, ◜ / ◸ edges …). A click on an **edge** offers ◜ Fillet / ◸ Chamfer this edge first (the command opens with it
chosen; Ctrl+click more edges), a click on a **step in the list** ✎ Edit, 🏷 Rename, ⁂ Pattern it, ✕ Delete, ↑ / ↓ Move,
⏮ Roll back here. In a sketch, with nothing picked: ✓ Finish — then extrude, 🪄 Auto-dimension, ⬚ Pick a shape,
↔ Dimension, ◯ Circle. Esc clears the choice.

**A click on a face of a 3D model** chooses its step and shows its tools in the Suggested table (bottom left) — the
table can be **dragged by its header** anywhere in the view, and stays there (a double-click on the header: back).
The same goes for every box floating over a view — 🖨 Print check, 📏 Measure, the ✂ Section bar, the size editor and
the sketch's small boxes: drag the header (or the **⠿** strip), **resize** with the grip in the bottom-right corner;
the place and size are remembered, and a double-click on the header puts the box back where it started.
Its **✨** puts what is selected into the AI chat — as the AI's tools name it (a step and a face, sketch shapes,
assembly parts) — so you can ask about it. The **Snap** row under it (3D model, assembly) says what 📏 Measure catches:
corners, edge midpoints, centres. With **no tool on**, the snap point under the mouse shows too and a click picks it
(in an assembly: with its part) — *📏 Measure from here*, *Copy its coordinates*, ✨. In the 3D model it also offers
**• Reference point here**: a step "Point 1" (a small marker with its name) that stays on that corner, edge middle or
round edge's centre when earlier steps change. Sketches snap to it and ↔ Dimension measures from it (seen square onto
the sketch), 📏 Measure snaps to it; it can be turned off, renamed and deleted like any step. When its corner is gone
the step says so and keeps its last place.
Everything for the clicked face is in that table, in sections — *On this face*, *Its edges*, *The part*, *Step* — so
there is no right-click menu: the right button only pans.

**Ctrl+click** in the 3D model (no tool on) chooses several things — faces (their steps) and snap points; Ctrl+click
one again takes it away. The table then offers what fits them: the distance between two (and the gap between two
parallel flat faces), turning all their steps off, deleting them together.

**Box selection** in a sketch (⬚ Select, drag on empty space): **right to left** takes every shape the box touches
(green, dashed), **left to right** only the shapes wholly inside it (blue); hold **Ctrl** to add to what is picked —
by click or by box. Delete removes them all. **Drag one of the picked shapes and they all move together** (the
grabbed point snaps as the Snap row allows, the others follow by the same offset; one undo step); dragging a shape
that is not picked moves just that one.

**⛓ Merge — many small shapes into few** (a sketch made from a DXF, or drawn by hand): box-select the shapes (or
Ctrl+click them), and when they are a connected chain of many pieces the table offers **⛓ Join into one curve** first and
**🧹 Simplify** second. **⛓ Join** makes each connected chain of lines, arcs and curves ONE smooth curve (a spline fitted
through it), split only where it turns sharply (a real corner); a straight run stays a line. **🧹 Simplify** keeps lines
and arcs but fewer of them: ends that nearly meet welded, tiny pieces absorbed, lines in line joined, arcs on one circle
joined (a full turn: a circle), a run of short lines along a curve -> arcs or a spline; shapes with sizes or relations of
their own are left as they are. Both show the result at once in a small box with one input, the **Tolerance** (how far the
result may be from what it replaces; 0.01 mm for most sketches) — retype it and it is done again — and the count,
*732 → 13 shapes*; Enter = done, Esc = back, one undo step. A joined curve's points are hidden (click the curve to see and
drag them). **◆ Make it one outline** (closed outlines picked, with their holes) makes them one rigid shape, like an
imported outline: it moves, turns and scales as a whole. **⛓ Merge** in the sketch bar does the same for any shapes: with
nothing picked it is a mode — click shapes or drag boxes over them (each adds), then choose in the table; its table also
has **🧹 Simplify the whole sketch**.

**Suggestions for what is selected**: choose a shape in a sketch (⬚ Select) or a part in an assembly, and a small
table in the bottom-left corner of the view says what can be done with it — a part: open it, join it, simplified, its
own part, take it out. In a sketch the list is short, the likeliest first, and **⋯ More…** opens the rest (in Edit /
Relations / Kind sections): a line — its length, horizontal or vertical (whichever it nearly is), delete; two lines —
the angle (or distance) between them, then ∥ / ⟂ / = whichever is nearly true already; a line and a circle — the
distance from its centre, tangent; two circles — the distance between centres, concentric / equal; a closed outline
(a box round a rectangle) — ⧈ offset, ⁂ pattern, ✥ move; several mixed shapes — ✥ Move…, ⧉ Copy, ⇋ Mirror,
✕ Delete all. **✥ Move…** (dx, dy), **⟳ Rotate…** (an angle about their centre, or about a picked point) and **⤢ Scale…**
(a factor) open a small box that shows the result at once and as you type (Enter = done, Esc = back, one undo step);
the shapes keep their relations, and a locked size that would have to change refuses it with a message naming the
lock. **⧉ Copy** puts a copy beside them, picked, ready to drag. Two parts — join them, measure, check for collisions.
Esc (or another tool) closes it.

**Suggestions on a drawing sheet (📄)**: click what you want to change and its table lists what can be done. On a
**view**: all its sizes, ＋ a dimension, bigger / smaller (2:1, 1:2 …), add Section A–A, back to its place, rename,
hide (also Delete). On an **edge**: dimension its length, or the distance / angle to another one. On a **circle**: its
Ø or the hole callout ("4× Ø4 THRU"); if it has one already, that one is chosen. On a **dimension**: a tolerance
(±0.1 or +0.2/−0.1), a fit (H7, h6 …), a reference dimension "(60)", the other side, delete. On the **title
block**: name, drawing no., drawn by, note, the material (in the part), template, frame, paper, DXF. With **nothing
chosen** you get the next steps: add the missing sizes, show a hidden view, ⬇ Export PDF, 🖨 Print. The
**2D drawing** has a table too: with nothing chosen, as a sketch / as a quick part / measure / DXF; for the shapes
chosen: all like it, change the size, only these as a sketch or a quick part, another layer, delete.

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

**The sketch panel says what is going on**: each dimension row has its name and value (*Width 65*, *Height 65*,
*R23*) and the mouse on a row lights that dimension in the view; locks that do not fit are listed (*These do not fit
together: 65, x -20, x 50*) with their rows and shapes red. While sizes are free, **🪄 Lock at rounded values** locks
them at whole millimetres — the shapes move to them, the panel lists what changed (*R23.215 → R23*) with **✓ Keep**
and **↶ Take back**. Closed shapes that overlap (a rectangle and a slot) get **∪ Unite overlapping shapes**: the
pieces inside each other are trimmed — one outline of lines and arcs, tangents and equal radii kept (a hole inside a
plate stays a hole). A slot, rectangle or circle drawn piece by piece is offered first in the suggestions as **⊂⊃
Make it a slot** / **▭ Make it a rectangle** / **◯ Make it a circle**.

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
nothing in it that still has the name the app gave it — the one on screen stays); when the app starts empty, the last one is offered in a strip under the top bar (it goes once a part is opened or made).
*Save project* still writes a file to keep or send.

**📄 New project** (**Open ▾ → 📄 New project**, **Ctrl+Alt+N** — Ctrl+N is the browser's own new window — or the
project widget's **⋯** menu; also a row of the suggestions with nothing selected): the project on screen is kept (it is
in 🕘 Recent projects) and the window starts again with an empty one — the start screen. A message says where the
previous one is, and its **↶ Open it again** brings it back. **⧉ New project in a new window** starts the empty one in
a window of its own, side by side with this one (so does **Ctrl+click** on 📄 New project). The window's title is the
project's name, so windows are told apart.

**Several windows, several starts**: the app runs once per data folder — starting it again (the built app) only opens
another window of it. Each window holds its own project: a new window starts on the start screen, and its *Continue
where you left off* offers the last project that is **not** open in another window; 🕘 Recent projects marks such a
project *open in another window* (opening it there too is allowed: the windows of one project keep each other up to
date, see ⧉ Windows). Each window has its own ✨ AI chat, working in that window only (see *AI assistant*).

**🕘 Versions** (a widget in the left column of the 3D model and the assembly, folded until you open it): the project's
earlier states, kept on the server without git (`data/versions/<project>/`). Versions come by themselves as you work
(with the autosave, at most one every 3 minutes; a part added or removed at once) and with *Save project*;
**💾 Save version…** keeps one with a short description. The timeline, newest first, shows a small picture of the view,
the time, the description (or *automatic*) and the parts that changed. **Click** a version to look at it — read only, a
banner says so, with **↩ Back to current** and **⤺ Restore this version** (the state before is kept as a version first,
so a restore can be undone — also by ↶ in its message). **⇄** compares a version with the project now: parts and steps
added or removed, changed values (*Extrude 1: 10 → 15 mm*), the volume before → after. **⑂** makes a **variant** (a
branch with its own timeline) from a version; **Variant: main ▾** on top switches between them, and **Take a part from
a variant…** copies one part as it is in another variant into this one (there is no merge). Unchanged parts are stored
once (each part's JSON under its SHA-256, zlib), so a version costs a few kB; old automatic versions are thinned (all of
the last day, one an hour for a week, one a day after that; named ones and variants are kept). *Save project ▾ → with
version history* puts the versions into the file, and opening it brings them back. The AI has list_versions,
save_version, compare_versions, restore_version and create_variant.

**🎬 Demo projects** (Open ▾ → *Demo projects…*): ready-made projects that show whole mechanisms moving — a crank –
rod – slider (*Klikový mechanismus*), a four-bar linkage (*Čtyřkloubový mechanismus*: the crank turns round, the
rocker swings), a robot arm (*Robotické rameno*: an open chain — turn the arm and the forearm and gripper go
along) and gears with a rack (*Převodovka s hřebenem*: a pinion Ø30 turns a wheel Ø60 at i = 2:1 and moves a rack
π·30 mm a turn — ⚙ couplings) and a pump (*Pumpička*: press the button — the piston compresses the 〰 spring, the
outlet ball lifts and the inlet ball sits on its seat; let go: the other way round — ↕ check valves). Each is listed with what it shows (in Czech or English) and opens as a new project — a copy, the demo stays
π·30 mm a turn — ⚙ couplings) and a control box with a motor (*Řídicí box s motorem*: a PCB and a motor joined by
a 🔌 harness of 4 loose wires; the motor turns a pulley). Each is listed with what it shows (in Czech or English) and opens as a new project — a copy, the demo stays
as it is — on its assembly with ⚙ Mechanism ready (Czech motion names, ▶). The files are in `demos/` (built through
the app by `tools/make_demos.py`) and go into the Windows build.

**Panels**: drag the edge between a side panel and the view (or the AI chat's left edge) to make it wider or narrower;
the widths are remembered, a double-click on an edge gives the usual width again.

**Turning the view**: a left drag turns the 3D view freely, as far as you like (over the top too): across the screen
about its upright, up and down about its level. A right drag pans, the wheel zooms. The **view cube** in the top-right
corner of the 3D model's and the assembly's view (under the command bar) turns with the view: click a face (TOP, FRONT,
RIGHT, BACK, LEFT, BOTTOM) to look from that side, an edge or a corner to look from between them (a corner: the iso view
from it), ⌂ for the usual iso view — the part stays fitted. The face, edge or corner under the mouse lights up; it
works in a sketch too.
On a narrow view (a small window, wide side panels) the command bars show only their tools' icons — the name is in
the tooltip — so they keep to two rows; a wider view brings the names back.
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
   measures from them. **🪄 Auto-dimension** locks what the sketch still needs to be fully defined: first the
   relations it nearly has already (a line a hair off horizontal / vertical, a line running smoothly into an arc, arcs
   of the same radius), then each shape's sizes, an arc's centre (rather than the end of a side running into it), then
   its place from the nearest edges of the part (a hole from the outer edges closest to it), else the origin. It adds
   only what fixes something, so nothing is held twice (a rectangle ∪ slot drawn by hand: its 4 sizes + R and the two
   centres). A lock the others fix already becomes a reference dimension; locks that contradict each other are named
   (and drawn red); what it cannot fix is named too ("still free: arc R23 at (45, 9)"). Sizes the others set show
   **＝** instead of 🔓 on their labels. A joined curve (⛓) moves as a whole with its ends — its many points are not
   free sizes.
   **⇋ Mirror**: choose the Y or X axis in its little box (or click a line of the sketch), then click shapes — a
   rectangle or a joined outline goes whole. The mirror image is a copy that stays mirrored (⇋ *Mirrored*: change the
   original and the copy follows; click the ⇋ symbol to let it go free); points on the mirror line are shared, so half
   a profile becomes a closed one. *Move* turns the shapes over instead of copying them. **⁂ Pattern**: select shapes
   (⬚ Select: click, Ctrl+click or a box), then ⁂ Pattern — 3 copies in a row along X appear at once; in the box
   (bottom left) type the Count and the Spacing (Enter = done), click a line to go along it, or switch to *Around*
   and click a point or a circle for the centre (default: the origin; the copies spread over 360°). The copies keep
   the original's size and follow it; click the ⁂ symbol to change the count later; Ctrl+Z takes the whole pattern
   back. **⧈ Offset** (O): click a
   closed shape and type the distance (negative = inside) — a parallel copy: a circle gets a concentric one, an
   outline of lines and arcs keeps its sharp corners sharp and its roundings concentric. The copy stays linked:
   type a bigger width or drag the original and the copy follows at the same distance; click its ⧈ label to type
   a new distance; pick the copy and choose ⛓ *Unlink the offset* for a one-off copy. A picture outline grows or
   shrinks as a one-off copy (e.g. the wall of a cookie cutter).
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
   - Or **Up to next**: the extrude goes as far as the first face of the part across the whole sketch — a boss
     from a plate up to the plate above it, a cut through the first wall only. It follows the part; when nothing is
     in the way, the panel says so (*⇅ Flip direction* turns it).
   - Tick **＋ Other side** to extrude also a distance to the other side of the sketch (5 mm to start with; type
     another). It is the other way of going both ways to *Both sides*: ticking one unticks the other.
   - **Draft** (0° to start with) tapers the side walls: they lean in going away from the sketch (negative: out), for
     a boss or a pocket that comes out of a mould. With *Both sides* / *＋ Other side* each side tapers away from the
     sketch; not with *Through all* or *Up to next*. A profile of small round bumps drafts too (its corners come out
     rounded); an angle so steep that the walls would meet before the far end is refused with the most that fits.
   - OK, or Enter, adds the step.
3. **✏ Sketch** again and **click a flat face** of the part to sketch on it. On a face, Extrude starts as
   **Cut**, ready for holes and pockets.
   - A sketch on the top or bottom face of an extrude follows that face when the extrude changes.

4. **◜ Fillet** (F) rounds edges and **◸ Chamfer** bevels them. Click the edges (a click on a face takes all of its
   edges; a picked edge is dropped by clicking it again), then type the radius or size. A click on an edge that goes
   on smoothly into others — the outline of a box with rounded corners, a hole's rim — picks the **whole chain**
   (*Added a chain of 8 edges*; the hover shows it before you click), as a rounding cannot stop where edges meet
   without a corner anyway; untick *⛓ Whole chain* to pick one edge at a time. **◎ Hole** (H): click on a
   flat face where a hole goes (click again for more holes on the same face), and type the diameter. **Esc ends the
   placing and keeps the holes placed so far** (as OK — *Hole: 1 position(s) kept*; Ctrl+Z takes them back); with
   none placed yet Esc cancels, and the **Cancel** button always throws them away. Fillet / Chamfer (edges) and Shell
   (open faces) work the same; in a sketch Esc ends a ╱ line's chain and keeps the segments drawn. Choosing a hole
   that is there (its row in the list, its wall, its rim) only chooses it: the suggestions start with **Type: ⌴
   Counterbore ▾** (all six kinds, the current one ✓) and **Size: M5 ▾** (the two sizes below and above: M3 M4 ✓M5 M6 M8;
   a plain hole: the next Ø steps, 0.5 mm up to 6 then 1 mm) — one click switches it in place, one undo step — then
   ✎ Edit the hole, 📏 its Ø, ⁂ Pattern, ✕ Delete; the right panel shows that hole step's Type / Size / Through (changed
   at once) with ✎ Edit the hole and ＋ Add position, and its row in the list is marked. (A round cut made by an
   extrude is not a Hole step: its faces keep their usual suggestions.) **✎ Editing** it opens its panel without placing —
   the mouse shows no new hole and a click adds none until **＋ Add position** (an edited text / picture: **⌖ Move by
   clicking**). While you move
   the mouse the hole is shown where it would go, with its distances to the nearest edges, and it **snaps** like a
   sketch: onto the face's corners, edge midpoints, centre, round edges' centres, other holes and • reference points
   (the snap is named at the mouse), onto its edges, and **in line** with any of those — a dashed green guide; where
   two guides cross it snaps to the crossing (the middle line of a square block: in line with both edge midpoints).
   Shift (or Alt) places it freely. The Snap row bottom left switches corners / midpoints / centres / ┆ Guides on or
   off. A hole placed in line with another hole of the step is measured from that hole, so it stays in line. A hole
   put on the face's centre, or on a middle line (in line with two edge midpoints), stays **in the middle** when the
   part changes size — its row says *↔ in the middle of the left and right edges*; 🎯 measures it from an edge instead.
   *Aa Text / picture* snaps the same way. It goes through all by default, or untick *Through all* and give a depth.
   *Type* makes it a hole for a metric screw, sized from the ISO tables by one *Size* choice (M2 … M20; the size
   nearest the hole's Ø is picked first, then the one you used last): *Clearance hole* (ISO 273 medium, M5: Ø5.5),
   *⌴ Counterbore* (that hole + room for an ISO 4762 socket head, M5: Ø10, 5.4 deep), *⌵ Countersink* (+ a 90° cone
   for an ISO 10642 flat head, M5: Ø11.2) or *Tapped* (a threaded hole: drilled with its tap drill, M5: Ø4.2, and
   labelled M5 on the drawing). The sizes are folded under *Edit sizes* — change the hole's or the head's Ø / depth
   there; *Simple* is a plain hole of the Ø you type. *D (flat)* is a hole for a D-shaft (a knob on a motor's shaft):
   its Ø and the size *Across the flat* (from the flat to the far side; a common D-shaft's by default — Ø5: 4.5, Ø3 / 4
   / 6 / 8: 2.5 / 3.5 / 5.5 / 7.5, else 0.9 × Ø — and it follows the Ø while you have not changed it); the flat faces
   the face's x direction, ⇄ turns it 90°. The drawing says *Ø5 D4.5 THRU*. A head that would not
   fit — wider than the face around the hole, or as deep as the part there (it would cut through) — is refused,
   with the most that fits. The drawing's callout says it: *Ø5.5 ⌴ Ø10 ↧ 5.4*, *M5 ↧ 10*. **A new thread shows at
   once as cosmetic lines** (a tapped hole made by the tool, its type switched, or the AI: the part's threads were
   hidden -> cosmetic, a toast says so; the hole's panel has *🔩 Thread: Cosmetic / Real thread (slower)*); parts
   opened keep their setting. To hide them or choose again: click the
   part (no tool on) and choose **🔩 Show all threads** under *The part*, then how: *Cosmetic (light)* draws a thin
   helix at the thread's pitch on each threaded hole's wall and a thin ring at its major Ø on the face (view only: the
   solid, its volume and exports stay as they are; quick, it may stay on). *Real geometry (slower)* cuts a true ISO
   metric thread (60°, the basic profile) along each threaded hole — through, or down to just short of a blind hole's
   bottom — so it is in the volume and mass, the STEP / IGES / STL / 3MF exports and 🖨 the print split. It costs
   time and triangles (an M5 × 10: about 0.45 s and 6 000 triangles; eight M6 × 12: about 3.7 s and 49 000); the
   Part panel says how long the cut took and warns when there are many. While a tool or a sketch is open the real
   threads show as cosmetic lines, so editing stays quick. After a change the part shows at once with thread lines
   (the Part panel: *⏳ 9 real threads being cut*; ⚙ lists *Cutting real threads*, with ✕ Stop) and you can go on
   working; the real threads swap in by themselves when they are cut (a change that leaves the solid as it was, or
   an undo, finds the cut it made before). Exports always carry them. Drawings keep showing the thread the standard way: the
   hole's callout (*2× M6*) and a thin ¾ circle at the major Ø. *Hide all threads* takes them away; the Part panel's
   *🔩 Threads* row (Hidden / Cosmetic / Real, shown when the part has threaded holes) switches it too, and placed
   parts in an assembly show their part's choice. *Teardrop (print sideways)*, offered on a hole that goes
   sideways (into a side face, across Z), gives the hole a 45° point on top so it prints lying on its side without
   support (the 🖨 Print check shows no overhang there); the drawing still says Ø d. A counterbore gets the point too; a
   countersink cannot. On a hole that goes up / down it is greyed. Each hole is
   placed from the face's nearest edges — *↔ 10 mm from the right edge*, *↕ 5 mm from the lower edge*, drawn on
   the face. Type a distance to move it, ⇄ measures from the edge on the other side, and 🎯 lets you click *any*
   edge of the face — or another hole (then it is measured from that hole's centre and follows it). Every tool shows a live
   preview.

   **Dimensions follow the part.** A hole's distances and a sketch's dimensions to the part's edges or corners
   (↔ Dimension on a dashed edge) remember *which* edge or corner it is (by the faces that meet there). Make the
   part wider in an earlier step and the hole or the sketch moves with its edge, keeping its distance.
   **From a shaft's or a hole's axis**: in a sketch, the axes of the part's round faces show as dashed blue centre
   lines (a cross hole under the face, a shaft lying along it; seen end on: the ✛ at a round edge's centre) — ↔ Dimension
   on one (on the line or anywhere over the round face) measures from the axis. In the hole panel, 🎯 then a click on a
   round face (or its rim) measures the hole from its axis (*↔ 15 mm right of the axis*). Move the shaft or the cross
   hole and the sketch or the hole goes along.
5. **⟳ Revolve** spins a sketch around an axis: the sketch's vertical axis (the default), its horizontal axis or one
   of its lines, a full turn or any angle. Draw half the shape beside the axis, e.g. half a vase on the **Front**
   plane. A new, empty sketch can be moved to Front / Right with the buttons in the bar, and a sketch on a base plane
   can be moved along it with **Offset** (e.g. 30 mm above the bed). **▢ Shell** hollows the
   part out: click the face(s) to leave open (the top of a cup) and type the wall thickness. A cut into the side
   before it gets a wall bent round it inside; when the walls cannot be made all over the part, the step says so
   (hollow it out before that cut) rather than leave most of it solid.
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
the mouse. A click on a **snap point** first offers what it belongs to: a round edge's centre or quadrant —
**◎ Select the hole M5** (a ◎ Hole step: its Type / Size table; another round cut: *Select the round face Ø8*) and
**◯ Select the circle Ø10** (its edge: fillet / chamfer it); an edge's middle — **⟋ Select the edge**; a corner — the
edges that meet there; the point's own rows (reference point, measure from here) stay below. The same in a sketch (a
circle's centre: *◯ Select the circle*) and in an assembly (a hole's centre on a part: *◎ Select the hole* — its
round face chosen, Concentric and the other joints offered). A click on a face pops up the tools for it — sketch on it, a hole or text there, round / bevel its edges,
hollow it out with it open, edit / turn off / delete its step — and shows that step's **sizes on the part** (the
sketch's sizes on its plane, the height, Ø, R, the wall…). Click a size: a number and a **slider** — the part
follows while you slide; Enter / OK keeps it (one undo step), Esc goes back. Every number in a tool's panel
(Extrude, Revolve, Fillet, Chamfer, Hole, Shell, Pattern, Text) has a **slider** under it too — slide and watch.
The sliders run only over the values that **work**: the kernel tries the step with the part as it is and finds the
range (the biggest rounding the edges allow, a wall up to what the part can take, a blind hole up to the part's
thickness, a pattern only as far as its copies still reach the part; a rounding's found to 1 %, shown *≈ 8.94*, as near a
hole OpenCASCADE builds slowly right below its limit); the range shows under the slider. Where the limit is **real**
(a rounding / chamfer / wall that cannot be built bigger, a hole as wide as the part, a blind hole or a cut deeper
than through, a full turn, a draft under 45°) a typed value beyond it is held at the limit, saying why (*max 9.94 — a
bigger rounding does not fit here*). Where the range is only a **suggestion** — shown with a *+* (*2 – 4+*): a
pattern's count and spacing (the copies that still reach the part), an extrude's height — a bigger number typed is
kept and the slider grows to take it (a pattern then warns *Only 4 of the copies reach the part*). When a step fails
anyway, it says how much does fit (*at most 9.99 mm*) — or that no size works there and what to change.
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
- **✂ Section** cuts the view along X, Y or Z with a slider, to look inside (⇄ shows the other side): the half toward
  you is taken away and the cut faces are filled in brick red, so bores, seats and channels show (also in the AI's
  screenshots).
- The Part panel shows the size, volume and **mass** for the chosen **material** (PLA, PETG, ABS, ASA, TPU, PA;
  solid, no infill), its **surface area** and its **centre of mass** (CoG, in the part's coordinates); **⊕** next to
  it marks the centre of mass in the view.

**From the other parts of the app:**
- **◆ To 3D model** (in the Quick part's 3D toolbar) makes a new model tab from the part's outline: a picture
  traced into a cookie cutter, a DXF, a PDF drawing (its profile with the cutouts, in mm) or a 3D file's
  footprint. The outline becomes the first sketch, and Extrude is ready.
- **🖨 Prepare for 3D print** (in a model's Part panel) makes a printing copy of the model as a Quick part, on the
  3D print tab: printer fit, splitting into pieces with joints. The copy is the model's STEP, so **Split to fit**
  cuts the pieces from the exact solid — curved walls stay smooth (no steps), each piece has a handful of faces and
  its STL is meshed within 0.01 mm; the joints' pockets and tabs are cut exactly too. Make it again after changing
  the model.

Sketches show as lines in the 3D view: bright while not extruded yet, faint once used. Double-click a sketch's lines to
change it. Over the part, a click goes to the face, not to a used sketch's faint lines on it or under it — choose that
sketch in the list first, then a click right on its lit line keeps it. The steps are listed on the left. Double-click a step (or ✎) to change it; ● / ◌ turns a step off and on (it is kept); ✕ deletes it, together with the
steps that need it. A step that cannot be built shows ⚠ with the reason, and the others still build. Ctrl+Z /
Ctrl+Y undo and redo whole steps, and each model tab keeps its own history.

**Export ▾** (or the buttons in the panel) gives STL for printing and STEP with exact circles and faces for
other CAD programs.

The model is built by a real CAD kernel, OpenCASCADE. It runs in its own process, so a failure cannot stop the
app, and Cancel works on long rebuilds. It needs the optional packages in `requirements-modeler.txt`
(`py -m pip install -r requirements-modeler.txt`, about 175 MB installed). Without them the rest of the app
works, and the workspace says what to install. Its booleans (cuts, joins, splits, clash checks) use all the
processor's cores; `A3D_PARALLEL_BOOL=0` (an environment setting) makes them use one — the results are the same.

The kernel runs as a small pool of processes, so one long job — a big STEP import, a drawing set, a print
split — does not hold up the rest: another part, another window or another assembly part is built meanwhile, and
an assembly's parts are built side by side when it opens. Each part's jobs stay with one process, in order, so its
kept results are reused. How many: `A3D_WORKERS` (an environment setting); by default one per core less one, at
most 4, and one more only while 2 GB of memory are free for it (the size is in `/api/kernel` as `workers`).
`A3D_WORKERS=1` is one process for everything, as before. A process that crashes, runs out of time or is
cancelled is restarted alone; one that grows past 3 GB (`A3D_WORKER_MB`) is restarted between jobs.

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
  The sketch comes **cleaned up**: ends that nearly meet become one point (so the outlines close and extrude), an
  exporter's tiny crumbs are absorbed, lines in line become one line, arcs on one circle one arc (or a circle), and a
  smooth curve of the file (a SPLINE, flattened into many points) one arc or one spline again — the toast says how
  much (Finger.dxf: 702 → 231 shapes, the same area). More in a sketch: ⛓ Merge (below).

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
are one Ø and two pitches, not 400 dimensions). **Where the holes are** is drawn in the view that shows them round,
measured from the part's left and bottom edge (ISO 129): a row / grid as its first hole and its pitch, holes evenly
round a centre (⁂ Pattern around, a bolt circle) as their centre and one dash-dot pitch circle *PCD Ø60 · 6× 60°*, up
to 3 holes each from the edges, more as **ordinates** (one row each way, the edge's *0*, the values moved apart where
they would touch). They are placed clear of the other views, the frame, the title block and the other dimensions —
placed again when you drag a view or give it its own scale; drag / Del them like any dimension. Each hole step gets **one callout** in the view that shows its holes
round, with everything needed to make them (ISO 129 symbols): *4× Ø3.4 THRU*, *M5 ↧ 8* (a blind thread, its depth),
*Ø3.4 ⌴ Ø6 ↧ 3.2* (a counterbore), *M3 ⌵ Ø5 × 90°* (a countersink), *Ø8 H7 THRU* (a fit), *Ø6 THRU ▲* (a teardrop) —
the head's circle is not given again. Each size is given once on the sheet — a view whose sizes are all in
the others (often the Right) has none; its choice **All its sizes** gives it its own anyway. **Clicking a dimension
lights up the same size in the other views** (teal). **Drag** a dimension or a view to move it, **Del** removes a
dimension (↺ brings deleted ones back), **＋ Dimension**: click an **edge** (it lights up under the mouse) — click it
again (or Enter) for its **length**, another edge for the **distance between them**, or a point for the distance from
the edge —, two points (a corner, a hole's centre), or a circle (its Ø / R). A value is always measured from the part — it cannot be typed. The sheet **follows its part**: change
the part and the views and dimensions are made again, the revision goes up and *Changed* says when (your moved and
own dimensions stay on their edges and holes). **Check** (the left panel) tells whether the part is fully dimensioned: each view shows ✓ or ⚠ with how many sizes it
misses — a hole's place, an edge, a Ø or R, and without a hole's callout its countersink angle, counterbore depth or
blind depth (*the countersink's angle (H1)*) — listed with **＋** (add that one, from the part's edge) and **＋ Add all
missing**, and marked with an orange **?** on the drawing (not in the PDF); dimensions that give a size twice are
marked ⧉ (*✕ Remove them*). A known circle gives its own edges (a tangent side, a boss), a pitch *4× 10* its row,
a pitch circle its holes.
**Views**: double-click a view's name (on the sheet or in the Views list) to **rename** it (*Side A*); drag a view to
move it — it **snaps in line** with the front view (Top under it, Right beside it; a dashed guide shows it), Shift
moves it freely. **Scale**: the sheet's *Scale* is *Auto* (fitted to the paper) or one you choose — 10:1 … 1:100 or
*Custom…* (any, e.g. *1:2522* or *3:1*); each view may have its own in the Views list, and then says it under its name
(*Detail B (2:1)*). The title block shows the sheet's scale; dimensions always show the part's real sizes; a view that
no longer fits inside the frame is flagged (⚠), not refused. The **title block** is clean and light (ISO 7200
fields): the part's name large, small grey labels over the values, thin rules, a company / logo column on the left —
it prints well in black and white; an assembly's parts list matches it. **Title-block templates**: in the sheet's
panel choose *Template* (Modern, Compact, ISO 5457, the five designs *A — Strip*, *B — ISO 7200*, *C — Dark band*,
*D — Minimal*, *E — Column*, or your own; a drawing that chose none uses *B — ISO 7200*). **Title block style** and **Parts list style** are chosen apart, so any
title block goes with any parts list: A (180 × 21 mm, one row), B (180 × 40 mm, the full ISO 7200 grid with checked /
approved, roughness and the projection symbol), C (180 × 34 mm, a black name band; the list's positions in circles),
D (170 × 28 mm, no grid), E (a 90 × 56 mm column; its list two lines an item). The parts list sits right on the title
block at the frame's corner, also on the BOM pages; on an assembly's drawing the views keep clear of both (moved up or
left, else the automatic scale a step smaller — a view you drag over the list is kept there and flagged ⚠); the PDF uses the styles' own fonts (IBM Plex Sans, Barlow, Inter
— open-licence, in web/fonts). Type your *Company*, *Address*, *Drawn by*, a default *Note*, the *Tolerance
standard*, the *Roughness*, *Checked by* / *Approved by*, pick a *Logo* and the fields shown (under *Company, logo
and fields*), then **💾 Save as template…** — kept on the server for all your projects. On a
drawing of an assembly, **⇶ Use for all drawings of this assembly** puts it on the assembly's, its sub-assemblies'
and its parts' drawings, and new drawings of that set take it too; the PDF and DXF use it. **Frame**: *Simple*
(10 mm all round, the default), *Standard ISO 5457* (20 mm on the left for filing, 10 mm elsewhere, a 0.7 mm line,
zones A… / 1… and centring marks), *Narrow* (5 mm), *None*, or *Custom…* (each margin, the line, zones, centring
marks). The views and the automatic scale fit inside the margins; the frame is kept in the title-block template, so a
whole drawing set follows it (a drawing may choose its own).
The title block takes your own texts — *Title*, *Drawing no.*, *Drawn by*, *Note* — in the panel (a double-click on a cell goes to its field). **⬇ PDF** gives the sheet as you see it — the page is the paper (A4 / A3) and
1 mm on the sheet is 1 mm on the page, so printed at 100 % ("actual size", not "fit to page") the sheet's scale holds.
**⬇ DXF** gives it for drafting programs (AutoCAD, SolidWorks / Solid Edge drafting): the paper 1:1 in mm, the views
where they are at the sheet's scale, real dimensions that show the part's sizes (they measure the paper, DIMLFAC = 1 /
scale), the title block and parts list as text; layers *visible*, *hidden*, *dims*, *hatch*, *text*, *frame*. The AI
works on sheets too (`sheet_open`, `get_sheet`, `sheet_edit`: a preset, the paper, views, dimensions added between
points or on a circle, removed or moved; `export {format: "pdf" | "dxf"}` on a sheet) — for what the editor does not
offer in a click.

**📄 Drawing** in an assembly's toolbar (or *📄 Drawing sheet* in its panel) opens the **assembly's own drawing sheet**
to edit: its front, top and iso views, overall sizes, parts list and balloons — move them, add your dimensions and
texts, **drag the balloons** where you want them (they start spread round the view); it follows the assembly (a moved
part: a new revision). Each part is one item of its level's parts list (two of the same screw: one item, qty 2; a
sub-assembly: one item, its parts on its own page) with **one balloon**, on the copy that shows most — its leader ends
on a face of that part no other part hides, apart from the other leaders. Its size check asks only for the assembly's
overall sizes and where it is **mounted**: the base part's free holes (the base: the part fixed in place 📌, else the
one most joints are made onto, else the first placed; free: no screw or pin of the assembly in it) are dimensioned
from the base part's edges in the view that shows them round — a row with its pitch, a bolt circle as PCD, more as
ordinates, as on a part's sheet. Holes filled by the assembly's screws and pins are left out; the parts' details
belong on their own sheets. Its **Pages** list — on every page of the set, the part's sheets too — shows the whole set
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
lines: seconds instead of minutes; its dimensions are still measured from the exact edges. On its drawing sheet what
is too small to see at the sheet's scale is left out — solids, edges and holes under 0.25 mm on the paper (a 0402
resistor on a board drawn 1:5), the left panel says how many — and its Section A–A cuts only the solids across the
cut: a 44 MB board's sheet in 25 s instead of 78 s, 4.6 MB to the browser instead of 44 MB. A sheet keeps its part's
views: another preset, paper or the section turned on does not project the part again (a hundredth of a second).
An assembly of more than ~1000 faces is drawn from its mesh the same way (MIT E-Vent's 41 placed parts: 10 s; the
exact hidden-line pass of its top view never ended), and an exact drawing that takes over 2½ minutes is stopped and
drawn from the mesh. While a sheet is made the progress bar shows it, with Cancel. A sheet that cannot be made says
why on the paper — *The drawing could not be made: …* (a reference body has no solid; a tessellated STEP has no size)
— with **↻ Try again**, and in a message.
Big parts also load faster: the model comes to the browser as raw arrays, not text, and an unchanged body is not sent
through the kernel again — the 44 MB board is shown again in about half a second instead of two and a half, first
built in 18 s of meshing instead of 25.
Big STEP files open fast the second time: a file of more than ~3000 faces, once read and meshed, is kept in the data
folder (`cache/models`, by the file's hash; under 4 GB, the least used dropped first) — opened again, even after a
restart, the 44 MB board (126 000 faces) is on screen in about 4½ s instead of 50. What is kept is the exact solid
(OpenCASCADE's own B-rep), so measurements and STEP exports are as from the file; a changed file or a newer app
version reads the file again. The first open is quicker too (about 35 s instead of 50): a part placed many times —
a board's thousands of resistors — is meshed once and moved into each place.

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

### 📋 Bill of materials (BOM)
**📋 BOM** in an assembly's panel (nothing chosen) opens its whole bill of materials, every level of the assembly
rolled up: a part's total is the sum over every place it is in — the assembly itself, its sub-assemblies at any
depth, a sub-assembly placed twice counting its parts twice. A screw placed both in the machine and inside a
sub-assembly is counted in both, nothing twice. Two views:
- **Summary** — one row per part: position, name, total quantity, material, mass each and in all, maker and part
  number (library parts), and **make / buy** (library and standard parts are bought; your own parts are made —
  *made (3D print)* of a printing plastic, *made* of a metal or another material). Hover a row to see where its count comes from
  (*Lid unit: 3 × 2 + Hinge: 1*).
- **Structured** — the assembly tree: each sub-assembly with its parts, the quantity in its parent and the running
  total; ▾ / ▸ folds a sub-assembly.

The choice at the top shows the BOM of any sub-assembly in it (or open that sub-assembly: its own 📋 BOM). The
positions are the drawing set's numbers — the same as the balloons on the drawings. **⬇ CSV** saves the view shown
(; separated for Excel); **⬇ Excel (.xlsx)** saves both views as two sheets of one workbook — it needs the optional
`openpyxl` package on the server (`requirements-modeler.txt`); without it the button is greyed and CSV is offered.
The headers and material names follow the app's language (in Czech: *Poz., Název, Ks, Materiál … Výroba / nákup*;
*ocel, hliník, PLA*) — in the window, the CSV / Excel, the BOM page and the parts lists on the drawings.

On an assembly's **📄 drawing sheet**, **📋 Add BOM page** puts the BOM on its own page right after the assembly's
page — in the drawing set, 📚 All pages and the PDFs — with the set's title-block template and frame, in the parts
list's style (Summary or Structured, chosen in the sheet's panel); a long BOM goes on over more pages (*… continued
on the next page*). The AI reads the same BOM with `get_bom {assembly, mode}`; `get_assembly`'s parts list has each
part's rolled-up `total`.

## Assemblies
- The **parts list on the left is a tree**: a placed sub-assembly has **▸** — it opens to its own parts (indented,
  with their ids; a sub-assembly in it opens too, at any depth); folded, it says how many parts are in it
  (*Lid unit I2 · 3 parts*). Which ones are open is remembered per assembly. A click on a part inside a sub-assembly
  lights it in the view and shows it in the panel: its **Moves inside** the sub-assembly when that one's own joints
  leave it free (moved in this placement only), *Open its part*, *Open* the sub-assembly or *Choose the whole* one;
  Ctrl+click takes its sub-assembly as the second part. The top rows work as before.

**＋ New assembly** (in the ＋ menu next to the part tabs) opens an assembly tab (◇), where the parts of the project
are placed together — 3D models ◆, quick parts ▤ (drawings, pictures, imports: they go in as their solid) and other
**assemblies ◇ as one unit** (a sub-assembly: its parts as placed there, joined and fastened like a part; its mass is
its parts'; the STEP keeps it as a sub-assembly; an assembly cannot go into itself):
- **＋ Insert part ▾** adds a model part, as often as you like (⧉ in the list adds one more). A new one is put
  beside the others.
- **🔗 Joint** (a button per kind in the bar — one click starts it, lit while you pick the faces; click it again or Esc to stop): choose how the part is held — **Touch** (S: a flat face onto a flat face, centred), **Gap** (facing,
  a distance apart), **Flush** (in one plane), **Concentric** (two round faces on one axis: a pin in a hole; its
  **↕ distance** is the gap along the axis between the facing ends of the two round faces — two plates with holes
  joined this way get it filled in (touching) and you type e.g. 30; empty = it slides),
  **Parallel**, **Perpendicular**, **Angle** (two flat faces at the angle you type), **Tangent** (a round face on a
  flat one), **● Ball joint** (a ball — a revolved half circle — with its centre on the axis of a hole or a cone: it
  slides along the axis and turns any way; onto another ball: one centre, it only turns), **◉ Ball in seat** (a valve
  ball seated in a conical seat, or on the edge of a hole smaller than it: on the axis, touching it), **🔗 Fixed
  together** (a part fixed to another one as they are now: it goes with it and has no motion of its own — also
  *🔗 Fix A to B* in the suggestions when two parts are chosen), or **🔩 Screw / pin** — then
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
- **〰 Spring**: pick the spring's end face and the face it pushes on (Ctrl+click; a part called *spring* / *pružina*
  puts 〰 first in the suggestions, or 〰 Spring in Joint ▾). The spring part is drawn as long as it reaches — scaled
  along its axis, its other end where it sits — while the parts move (sliders, dragging, ⚙ ▶, the 🎬 animation,
  screenshots); its model stays as it is, its free length is its modelled length. Its row: *free 20 mm · now 16 mm ·
  compressed 4 mm*, and with its stiffness **k** (N/mm, the one input) the force (*2 N*). Collisions between the spring
  and the parts it is joined to are not counted.
- **↕ By the driver's direction** (a check valve's ball, a pawl): a part with one slide between two limits (⇤⇥ — its
  stops, e.g. seated / lifted) gets **↕ By the driver's direction** in its motion's row: one click and it goes by the
  piston (the mechanism's driver sliding along it) — while the piston goes forward it sits at one stop, going back at
  the other (*Piston forward → at max / at min* chooses which). It moves with the piston's ⚙ mechanism (its slider, ▶,
  a drag), and 📈 Trace goes there and back, so both stops show. Not for a crank turning round and round (it always
  goes forward).
- **🔒 Lock a motion where it is**: 🔒 by a motion in the part's Moves keeps it — a joint's turn or distance, a new
  flush / gap / parallel joint where faces line up, else **its own joint keeps it** (a touch's slides on the face one
  by one, a ball's slide along its axis; a ball's turn locks all three of its turns). The joint's row says
  *🔒 2 locked* and ✕ there frees them again.
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
- **Closed loops — a mechanism**: a part joined to two parts that move closes a loop (a crank–rod–slider: the rod's
  eyes on the crank's pin and on the slider's pin). Its parts are solved together: turn the crank (its slider, ▶ or
  ⚠ Check the travel through a full turn) and the rod and the slider follow, the slider at r·cosθ + √(L² − r²sin²θ);
  push the slider and the crank turns. Each part's panel says *In a closed loop with I3, I4: … 1 way(s) for all of
  them*. A move past a dead point stops there. A loop that cannot close (the rod too short for that place) says so
  on its joints and in the panel (*⚠ The closed loop … cannot close here*). The AI sees `loops` in get_assembly
  (parts, closed, free_motions, the motions that drive it).
- **⚙ Mechanism — the whole mechanism by one slider**: an assembly with a mechanism (a closed loop that moves, or a
  part turning / sliding on an axis or with limits) gets a **⚙ Mechanism** widget in the left column (dock it, float it
  over the view or close it with ✕; ⚙ Mechanism in the toolbar and *Drive the mechanism* in a part's suggestions open
  it again). One row per mechanism: its name, **one slider** over its driver's travel — a crank's full turn 0 … 360°,
  a slide's limits — and **▶** (round and round for a full turn, to and fro otherwise, back at a dead point; ⏸ stops it
  where it is). Every part of the mechanism follows live. The driver is the crank by default (a full turn, else the
  part the closing rod is on); **⋯** picks another driver, the speed (½× 1× 2×), **⚠ Check the travel** (collisions over
  the whole turn) and **📈 Trace** (a curve: how the slider moves over the crank's turn). Nothing shows in an
  assembly without one.
- **🎬 Save animation** (⚙ Mechanism ⋯, *"Uložit animaci"*): one click records one full cycle of the mechanism — a
  full turn of its driver, else there and back, at the speed ▶ plays it — from the view as it is, and downloads it.
  **GIF** by default (loops, plays everywhere — phones, chats, e-mail; 20 frames a second) or **Video** (MP4 or WebM,
  whichever the browser can record; 25 frames a second, smaller and smoother). The 3D only — no labels, sizes or
  marks — at the view's shape, at most 1280 px across; **Name** puts the mechanism's name in a corner. A line in the
  row counts the frames (Cancel stops it); the parts end where they were. The files are also kept in the app's data
  folder (`data/animations/`); the GIF is made there by the server (Pillow, one palette for all frames: no flicker),
  a ⚙ job you can stop. The AI: `record_animation {mechanism, format: gif | video}` (it answers the file's path);
  gui_state shows a recording under way or the last one saved.
- **⚙ Gears, ⛓ belts, ▤ a rack — couplings**: two parts that each turn on their own pin can be tied by one number,
  the ratio (*převod*). Click the rim of one wheel, Ctrl+click the rim of the other: when both can turn about
  parallel axes the first suggestion is **⚙ Gear pair · i = 2:1** (the rims touching — the pitch circles; the ratio
  from their Ø: the bigger one turns half as fast, the other way round; a ring gear round a pinion the same way) or
  **⛓ Belt / chain · i = 1:2** (the rims apart: the same way). A wheel's rim and the flat side of a part that slides
  gives **▤ Rack and pinion · 94.248 mm per turn** (π·Ø). Then turn either part — its slider, ⚙ Mechanism, ▶, a drag
  in the view, the AI — and the other follows, through a whole train (a pinion → a wheel → a pulley → a rack); the
  coupled parts are one mechanism with one slider. The part's panel lists its **Couplings**: the ratio to type, **⇄**
  the other way round, ✕. A hole and a pin of the same Ø still offer ◎ Concentric first (a joint, not wheels). The
  AI: `snap_faces {type: "gear" | "belt" | "rack", value: ratio}`, get_assembly `couplings`, `edit_joint {id: "G1",
  ratio, flip}`, `remove_joint`. Gear teeth are not modelled: a wheel is its pitch circle (a disc).
- **Drag a part in the view**: choose a joined part, then drag it in the 3D view (the cursor shows a hand): it moves
  the way its joints leave free — a crank turns round its shaft after the mouse, a slider slides along its line — and
  every part joined to it follows live (the rod and the slider of a crank; a forearm and its gripper on a turning
  arm). Grabbing any part of a closed loop (the rod) turns the loop's driver. Elsewhere a drag turns the view as
  always.
- **Name the motions**: a free motion is named by its part — *Turn: Crank*, *Slide: Slider* (*Otáčení: Klika*,
  *Posuv: Smýkadlo*; two of a kind say how: *Slide: Lid (along X)*; the joint it comes from is in its tooltip).
  Double-click a motion's name in the part's panel or in ⚙ Mechanism (*"Dvojklik: dát mu vlastní název"*) for your
  own — "Otáčení kliky"; double-click a mechanism's name for its own. The names are kept in the assembly (undo, save
  and open again) and show everywhere: the panel, the widget, the AI's get_assembly / gui_state. The AI: get_assembly
  `mechanisms`, `drive_mechanism {mechanism, to, driver, name, play}` and `name_motion {part, motion, name}`.
- **A sub-assembly keeps its own motions**: choose a placed sub-assembly — **Moves inside <it>** shows a slider for
  each way its own joints leave its parts free (a lever on its pin). Slide: the lever turns here, in this placement
  only — the sub-assembly's own tab stays as it is, and a second placement of it can stand differently. Parts joined
  to the lever follow; collisions, STEP and drawings see it where it is. **↺ As in <it>** puts its parts back. The AI:
  get_assembly lists them as `inner` ("I3/I2"), `move_free {part: "I3/I2"}` moves one.
  A joint of this assembly on such a moving part (e.g. the lever's side parallel to the frame) holds that part inside
  the sub-assembly — the turn it locks is gone from the sliders — as long as the sub-assembly is held otherwise too
  (another joint, or 📌); a sub-assembly held only by that one joint moves as one piece, as before.
- **A sub-assembly's mechanisms work in the assembly it is in**: its own mechanisms (a crank loop, gears with a rack,
  a part turning on its own) are in **⚙ Mechanism** too, named *Klikový mechanismus (v Pohon)* — drive them by the
  slider, ▶ play them, ⚠ check their travel; choose the sub-assembly and **drag one of its parts** in the view (its
  crank turns, the rest follows). The parts move inside its placement; parts of this assembly joined to them follow,
  and a loop through both levels (a rod of this assembly on its crank's pin) is solved together. The moves are kept
  on this placement only — the sub-assembly's own tab stays as it is. **⚙ Moving sub-assembly** in its panel (on by
  default) switches it: off, it is 🧱 rigid — one body, no inner motion (offered back in its suggestions). The AI:
  get_assembly / gui_state `mechanisms` with `inside: "I3"`, `drive_mechanism {mechanism: "I3"}`, `move_free
  {part: "I3/I2"}`, `place_part {part: "I3", rigid: true}`.
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
  joints it can start; **Ctrl+click a face of another part** and it offers the joints that fit the two — one click
  makes it. Ranked, the likely one first:
  - **a hole and a pin**: *◎ Concentric + seat · Ø10* (on one axis and down on the face around the pin — Concentric +
    Touch in one step, so each pivot of a mechanism is three clicks: the hole's rim, Ctrl+click the pin, this), then
    *◎ Concentric only · Ø10* (the seat is offered while the moving part has no other joints);
  - **two flat faces facing up** (a part's top, Ctrl+click the base's top): *⧉ Put Slider on Base* — its underside
    goes onto the base, no turning the view to click a face you cannot see; then Touch, Flush …;
  - **two side faces facing the same way**: ▭ Flush first; on a part that is joined already it keeps the offset as the
    parts stand (a slider stays in line with the crank; type 0 in the panel to line the faces up).
  A plain click on a small hole or pin, or on a thin side, picks the face — corners, edge middles and centres catch a
  click only within 5 px there (📏 Measure: 10 px); a Ctrl+click beside the parts keeps the face picked first.
- **"One joint is missing"**: when the parts almost make a closed loop — the crank and the rod on their pins, the
  slider on the base, only the rod's second eye not on the slider's pin — ⚙ Mechanism (or the part's panel when the
  widget is closed) shows one quiet line: *Chybí jedna vazba, aby se mechanismus uzavřel: díra Ø8 (Ojnice) ↔ čep Ø8
  (Smýkadlo)* and **➕ Add joint**, which puts that pin in its hole (◎ Concentric; Ctrl+Z takes it back). The hole and
  the pin are found by geometry: free (no concentric joint), the same Ø (the pin up to 0.6 mm smaller), parallel axes
  near each other, both parts joined and still free to move. Nothing shows when nothing is near-closed.
- **📌 Fixed in place**: the first part put in an assembly is fixed (📌 in the list): it is not moved by hand, and a
  joint made from it moves the other part. 📌 in a part's panel (or the Suggested table) fixes or frees any part.
  A chosen part's actions are in its panel only (the Suggested table leaves them out — each action once on screen);
  its free motions are named by the joint's own name when you gave it one, a library or imported part's face by what
  it is ("the round face Ø22"), not by its steps' names; the turn sliders under X / Y / Z are ↻ X / ↻ Y / ↻ Z.
- **📏 Measure** (assembly): click a spot, then another — the distance and Δx / Δy / Δz (corners snap); two parallel
  flat faces also give the gap between them, two round faces how far apart their axes are.
- **⧉ Duplicate as a new part** (a 3D model's *Part* panel) copies it into a new, independent part (its own tab);
  in an assembly **⧉ Make it its own part** gives a placed part a copy of its own, to change it alone (↶ undo
  takes the copy out of the project again while nothing else uses it and it was not changed). The AI: `duplicate_part`.
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
- **🔩 Screw / pin through parts** (🔩 Fasteners → *Screw / pin through parts…*; 🔩 Screw / pin in the 🔗 Joint row opens the same
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
- **🔌 Cable harness** (*Kabelový svazek* in the toolbar; *🔌 Route a cable from here* on a clicked face or snap
  point, *🔌 Route a cable between them* with two parts chosen): choose what runs — **Cable** (its Ø and colour),
  **Loose wires** (how many, each one's Ø, default 1.5 mm, and IEC colour; the bundle's Ø from how round wires pack:
  1, 3, 7 wires = 1, 2.155, 3 × Ø), **Ribbon cable** (wires × pitch 1.27) or **Sleeve** (a corrugated hose, its Ø) —
  and the **minimum bend radius** (empty: the rule of thumb, 5 × Ø; a sleeve 3 × Ø), then **click the points it
  passes**: on a part's face it lies on that face (Ø/2 + 0.5 mm off), a hole's centre takes it through, a click in
  space puts a point there (in the plane facing you, through the last point). A live preview follows the mouse with
  the length (*Délka 1 284 mm*). **Esc / Enter / ✓ Done** keeps the points. Points on a part **stick to it**: they
  follow when it moves (a mechanism, a drag, 💥 Explode). Afterwards *✎ Edit points*: drag a point (onto another face
  or in space), click the cable to put a point there, click a point and press Delete. The route is straight lines
  with every corner rounded to the minimum radius; a corner whose legs are too short for it gets the largest radius
  that fits and is **marked red with ⚠ *ohyb R 6 mm < min 15 mm*** in the view and the panel — never bent tighter
  silently. *⚠ Goes through Motor I3* when its centre line passes through a part. It is drawn as tubes (loose wires
  twisted round the centre line in their colours, a ribbon flat, a sleeve corrugated), listed in the assembly tree
  (*🔌 Svazek 1 · 4 × Ø1,5 · 1 284 mm*), in the **BOM** a line per wire or cable with its length + a reserve (5 %, under
  *More*) rounded up to 10 mm — *Vodič Ø1,5 mm hnědý — 1 350 mm* — and in the **STEP / GLB / IGES** exports (a part
  per harness, each wire a solid in its colour: a circle swept along the route) and the assembly's drawing sheet.
  The AI routes them with `add_harness` / `edit_harness`; get_assembly lists them with their lengths. The demo *Řídicí
  box s motorem* has one.
- **⚠ Collisions** finds where parts go into each other (touching faces are fine). It is checked a moment after
  every change, so the button itself says it: **⚠ 2 collision(s)** in red, or **✓ No collisions** in green. Click it
  for the list — each pair and how much (mm³), the parts glowing red and the overlap boxed in red; hover a row for
  just that pair, **click a row: the view goes to that collision**, the other parts see-through (click again or
  *⤢ Show all* to go back); ↗ chooses the two parts (their joints and moves). Slide a part and see it clear. Big imported parts (a whole assembled PCB) are checked quickly: two of them overlapping in many places show an estimate (**≈**) after a change — *↻ Check again* computes it exactly.
- **🎨 Paint** colours faces of the placed parts (▢ Faces) or whole parts (◆ Whole parts) in this assembly: click
  them, Ctrl+click for more, pick a colour. The parts keep their own colours in their tabs and other assemblies.
- **✂ Section** cuts every part along X, Y or Z (a slider moves the cut, ⇄ shows the other side); each part's cut
  faces are filled.
- **Explode** pulls the parts apart to look at them; their placement does not change. **💥** on a part in the list
  (shown while exploded) chooses whether it moves: off, it stays in place and the others move away from the parts
  that stay (a lid lifts off its box); **Ctrl+click** — only this one moves (again: all of them). Saved with the
  assembly, undoable. **Respect joints** (next to the slider): a joined part moves only the ways its joints leave
  free — a pin comes out of its hole along the axis, a bearing slides off its shaft — and goes along with the part it
  is on; a part held fast stays on it.
- The **parts list** shows each part, how many, its material and mass, and the total; under it the assembly's
  **centre of mass** (CoG) from its placed parts — **⊕** marks it in the view, and it moves with the parts while a
  mechanism plays or a part is dragged. A bought part with a mass of its own (`mass_g`) counts with that mass. **Export** gives STL (all
  parts as placed, in one file) or STEP — a **STEP assembly** (AP214) that SolidWorks, CATIA and Solid Edge open as an
  assembly tree: a product per part (named as the part, in its colour; a part placed twice is one product placed twice,
  "Pin-1", "Pin-2"), each placement where it is, sub-assemblies nested as sub-assemblies (a sub-assembly whose parts
  were moved in this placement is a product of its own, "Lever (I2)"). A single 3D model still exports as one body.
- Changing a part in its own tab updates the assembly. The assembly is saved in the project. Undo / redo work as
  everywhere.
- The AI chat can build assemblies too: *“put the pin into the plate”* — it inserts the parts and snaps their
  faces together (tools new_assembly, insert_part, snap_faces, place_part, get_assembly; skill assemble-parts).

## Exchange with other CAD programs

SolidWorks (SLDPRT / SLDASM), CATIA (CATPart / CATProduct) and Solid Edge (PAR / ASM) keep their own files closed;
the app exchanges with them — and with Inventor, Fusion, Creo, NX, FreeCAD, Onshape — through **neutral formats**:

| Format | In | Out | Notes |
|---|---|---|---|
| **STEP** (.step / .stp, AP214) | a part (exact solid, colours); an assembly (parts, placements, sub-assemblies, names, colours) | a part (named, in its colour, 🎨 painted faces in theirs); an assembly as an assembly tree (the same for each part) | The best choice: all three read and write it (*Save As → STEP AP214 / AP242*). Names with ×, č … are written as STEP's own `\X2\` codes (an ASCII file every reader decodes). |
| **IGES** (.igs / .iges, 5.3) | a part: its solids, or its surfaces sewn into a solid (a warning says so); surfaces that do not close come in as a 👁 reference body | a part (exact B-rep solid, mm, its name and colours); an assembly as one file (a body per placed part, named by its place, e.g. "Post pair-2/Post-1", with its colours — IGES has no assembly tree) | For programs and suppliers that still ask for IGES. Prefer STEP. IGES holds ASCII only: "M6×16" becomes "M6x16", accents are dropped. |
| **DXF** (drawing sheet) | — (a DXF / DWG opens as a 📐 2D drawing) | a part's or an assembly's 📄 drawing sheet: the paper 1:1 in mm, views, real dimensions, title block, a layer per kind | ⬇ DXF on the sheet. Opens in AutoCAD, DraftSight, SolidWorks (*Open → DXF*, as a drawing) and Solid Edge Draft. |
| **glTF** (.glb) | — | a 3D model part (its colour, 🎨 painted faces, the material's metal / plastic look) or an assembly (a node per placed part with its name, sub-assemblies nested, colours, PBR materials); metres, Y up | For viewers, rendering (Blender, KeyShot), web pages, SolidWorks Visualize / CATIA Composer-like tools. A quick part's GLB is its preview mesh. |
| **OBJ** (.obj) | a mesh made a solid (up to 60 000 triangles), or a sliced quick part | a 3D model part as a mesh (mm, shared corners, normals) | For renderers and 3D programs that take OBJ. |
| **Parasolid** (.x_t / .x_b), **JT**, native SLDPRT / CATPart / PAR | not read | not written | Closed or licensed formats with no free reader that gives an exact solid — save as **STEP** in the program that made them (see *Parasolid and JT* in docs/ARCHITECTURE-modeler.md Progress). |

- **In**: *📂 Open ▾ → CAD / PCB / 3D file*, a file dropped on the view, *▣ Solid from a file* in a 3D model, or
  *＋ Insert part ▾ → From a file* in an assembly. The AI's `open_file` opens them too.
- **Out**: the *Export ▾* menu (or the Export buttons in the 3D model's / assembly's panel; on a drawing sheet it offers
  PDF, DXF and 🖨 Print, in a 📐 2D drawing the DXF of the shown layers); the AI's `export
  {format: "step" | "iges" | "glb" | "obj"}`; on a drawing sheet `export {format: "dxf" | "pdf"}`.
- In SolidWorks: *File → Open*, file type STEP / IGES (an assembly STEP opens as an assembly with its parts). CATIA:
  *File → Open* (STEP AP214 / IGES). Solid Edge: *Open*, file type STEP / IGES (the import wizard keeps the assembly).
- **Try them yourself**: `samples/ExportFromOurApp/` holds files the app exported (a part with threaded countersunk
  holes, an assembly with a sub-assembly and repeated parts, drawing sheets: STEP, IGES, STL, OBJ, GLB, 3MF, BOM CSV,
  PDF, DXF, the project file); its README.md says what to check in each program. `tools/make_export_samples.py`
  makes them again.
- **Tested with real files** (`samples/ToImportToOurApp` — its README says for each file which program made it, how to open
  it and what you should see, with its source and licence; `solidedge/` is for your own Solid Edge exports): exchange tested with files
  from CATIA V5, NX / Unigraphics, Creo / Pro/ENGINEER, SolidWorks, Inventor, Fusion 360, I-DEAS, CoCreate, AutoCAD and
  others (STEP AP203 / AP214 / AP242, IGES) — parts and assemblies open with their parts, placements, sub-assemblies,
  names and colours; they can be edited, drawn (sheet -> PDF / DXF) and exported back (STEP / IGES / GLB) and read again
  the same. An assembly whose parts are separate files (CATIA's external references) opens when you pick the assembly
  file **together with its part files** (alone it names the files it needs); a tessellated (mesh-only) AP242 STEP opens
  as a solid of its triangles, with a note; an IGES of loose surfaces is sewn into a solid per closed body (the faces
  that do not close are shown see-through), and comes in as a 👁 reference body only when nothing closes. Loose
  surfaces beside a STEP's solid (supplemental geometry) are shown see-through and take no part in the volume, mass
  or cuts; flat faces stored as B-splines count as flat (sketch, hole); a fillet on a smooth edge (rounded already)
  says so.

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
- **Set it up at any time, no restart**: when Claude Code is missing, not signed in, or its key was refused, the ✨ AI
  panel shows **Set up the AI assistant** instead of the chat — the install command (no Node, no admin), **Sign in
  with Claude** (runs Claude Code's own sign-in in a window; the screen follows it and the chat comes back by itself),
  or an **API key** field (checked with Anthropic first; kept encrypted with Windows DPAPI in `data/ai/key.bin` — in
  the installed app `%LOCALAPPDATA%\Auto3DModeler\ai` — and only ever sent to Anthropic). **🔑 Access** in the chat's
  top bar shows who is connected and **Sign out / change the key**. A key that stops working (a chat turn refused)
  brings the screen back with a clear message. The rest of the app never depends on it.
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
  `simplify_sketch` tidies a sketch with too many shapes (one from a DXF): fewer lines and arcs, each chain one
  smooth curve (`op: "join"`) or the outlines one rigid outline (`op: "outline"`), and says the counts before → after.
  The AI's shapes open **fully defined** (green): a profile's corners are locked and each arc is tangent to the line it runs
  into (else its radius is locked), a slot is its two centres and one radius with tangent sides and equal ends.
- **The AI reads and fixes sketches**: `get_sketch` gives a sketch's shapes with coordinates, its relations, every
  dimension with its name, value and lock, what is still free and which locks do not fit; `sketch_auto_dims` runs 🪄
  (and says what it added or why not), `sketch_dim` sets / locks / frees one dimension, `sketch_trim` cuts a piece
  away and `sketch_union` turns overlapping closed shapes (a rectangle and a slot) into one outline of lines and arcs,
  keeping tangents and equal radii. Its screenshots show the sketch's size labels, and `gui_state` lists them with
  their values.
- **Everything the app does, the AI can do**: besides modelling, assemblies, the library and collisions, it colours
  parts (`set_look`: colour, see-through) and single faces (`paint_faces`), in a model or per placed part in an
  assembly; moves a joined part along its free ways (`move_free`); keeps a model in the library (`save_to_library`).
- **The rest of the app** is there too: 2D drawings — `open_file` opens a DXF / DWG, a Gerber / drill file, a
  Gerber set or ODB++ job (.zip / .tgz) or a folder of loose Gerber files as a 📐 drawing — (`get_drawing`,
  `drawing_find` by filters, `drawing_delete`, `drawing_add` lines and circles, `drawing_units`, `drawing_layers`:
  show / hide, colour, a new layer; `drawing_set_size`, `drawing_use` as a sketch or a quick part), joints changed or removed (`edit_joint`,
  `remove_joint`), `measure` between faces, the view for its screenshots (`set_view`: a section, explode, size labels;
  `get_screenshot` is a 1200 × 900 picture of the whole part or assembly however narrow the view is beside the chat,
  without your hover or picks, and `highlight` lights the faces of a step in orange),
  parts renamed or deleted, and files: `export` stl / step / pdf / **3mf** / **bom** / **dxf** / **project** (the
  whole project as a .a3d.json, as *Save project*).
- **Demos, project files, variants, mechanisms**: ask "open the crank demo, tell me its mass and save a GIF of it" —
  the AI opens a 🎬 demo (`list_demos`, `open_demo`) or a saved project (`open_file` of a .a3d.json), reads each placed
  part's mass, traces how the slider moves over a turn of the crank (`drive_mechanism {trace: true}`, the 📈 Trace),
  adds the joint the *One joint is missing* line offers (`add_missing_joint`), fixes a part in place
  (`place_part {fixed}`), switches 🕘 variants and takes a part from another one (`switch_variant`, `take_part`), and
  puts a STEP / STL file into a 3D model as a step (`add_feature {type: "solid", path}`: ▣ Solid from a file).
  [docs/AI-TOOLS-COVERAGE.md](docs/AI-TOOLS-COVERAGE.md) lists what the AI reaches in each workspace and what is left
  to `gui_action` on purpose (layout, tools with many inputs).
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
  presses **keys** (Delete, Enter, Escape, ctrl+z). A value given to a button is refused (nothing clicked), and when
  the controls on screen change (a part chosen: its panel) the answer lists them with their new numbers; a sheet's dimensions, views and title cells are listed too.
  The AI sees the **suggestions table** as you do: its title, what it is about, its rows in order and how many are
  under ⋯ Show all; it can select a face or a part by name (`pick`) and run a row by its label (`suggest`), and
  `get_screenshot {ui: true}` gives it a picture of the whole window with the table and panels — so it can point you at
  the row to click and test the app the way you use it. A **locked 🔒 joint** is greyed out in the panel (only 🔒
  unlocks it) and the AI cannot change it either.
- **The AI shows you where**: ask "how do I add a hole?", "where is the pattern?" or "show me" and Claude leads you
  through the app's own buttons step by step (`gui_highlight`): a pulsing ring around the control (or a spot of the 3D
  view) with a short tip, the rest of the screen dimmed a little. Nothing is blocked — you click the control itself;
  the tip goes when you click it, press **Esc** or ✕, and Claude waits for your click before it shows the next step.
- **/uiTester and /suggest** in the AI chat: **/uiTester** makes Claude the app's tester — it designs a few test parts
  (sketch, extrude, hole, pattern, fillet; an assembly with joints; a drawing sheet), checks for every feature that
  its button exists, is reachable, does what the tool does and is in Czech, writes a report for each problem and ends
  with a summary table (words after it narrow it: "/uiTester only the sheet"). **/suggest** — it proposes new
  features and files the ones you pick as tool requests. Reports are filed **once**: `list_reports` shows those
  written, and `report_problem` does not write a report whose title says the same as an earlier one (it names that
  one instead; `again: true` when it is really another problem).
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
- **Several windows**: each app window has **its own chat** (its own conversation and Claude Code process, started
  with its first message), and what the AI does goes to **that window only** — the chat's MCP server is started with
  `--client <the window's id>`, every tool call carries it, and the relay hands it to that window, never to another
  one (also when another window is the one in front). A reload and 📄 New project keep the window's chat; a new
  window starts a new one. When the window is closed, its chat's calls fail at once with *"The app window this chat
  belongs to was closed — nothing was changed"*; its Claude Code ends 10 minutes later. An MCP client of its own
  (below, no `--client`) works in the window in use, as before.

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
| STL / OBJ / 3MF / STEP | up axis, 90° turns, mirror, slice height | scale % |

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
- **▣ Solid from a file** (3D model) adds a STEP / IGES / STL / OBJ / 3MF as a step: **▣ Joined** to the part, **⬚ Cut out** of it
  (a cavity it fits in exactly) or **👁 Reference** (drawn see-through, not part of the part — build a cover or a holder
  around it, then cut a copy of it out). An STL / OBJ / 3MF is made an exact solid (up to 60 000 triangles). Assemblies
  insert one with *＋ Insert part ▾ → From a file* or by dropping the file on the assembly's view — a STEP assembly
  goes in as a sub-assembly (when you choose *Open as an assembly*). The files are kept by the server and carried in
  the project file.
- **STL / OBJ / 3MF / STEP as a quick part** (STEP is tessellated with `cascadio` / OpenCASCADE): the part is cut into flat slices at every
  flat face — exact for parts whose walls are vertical between flat faces (plates, brackets, cutters), slanted /
  curved walls become steps of the *slice height*. The file is kept on the server (`data/imports/`) and inside the
  project file, so projects reopen anywhere. Design layers need a flat part; on 3D files use 3D objects (e.g.
  subtract a text object to engrave it). A STEP quick part (also a model's printing copy) is split for printing
  exactly: the cuts and joints are planned on the slices, the pieces cut from the STEP's solid (needs the CAD
  kernel; with 3D objects added, or without the kernel, the pieces are made of slices).

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
   fit check, split planning and joints between pieces; exact pieces of a STEP part
   ([auto3d/printexact.py](auto3d/printexact.py), cut in the kernel worker by
   [auto3d/modeler/printsplit.py](auto3d/modeler/printsplit.py)).
7. **Bending** ([auto3d/bend.py](auto3d/bend.py)) – folds and rolls applied to the final mesh (split across the
   bend zones, then mapped onto the bent shape).

## What gets reported (Checks tab)

| Severity | Situation |
| --- | --- |
| error | label is not a number / zero / missing; dimensions contradict each other; no outline found (a drawing of several views: what to do instead); no readable text (also dimension values drawn as outlines) |
| warning | a feature is not dimensioned (value estimated); no thickness given (default used); dimension not attached to geometry; orphan dimension text; open outline; curves/angled dimensions (unsupported); unsure which outline is the part (a sheet of several views whose shapes do not close: the largest closed one is used, also said in a message) |
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
(more glue area); pieces are exported as a ZIP of STL or STEP files with an `ASSEMBLY.txt` sheet. A part with an
exact model (a 3D model's printing copy, a STEP file) is split exactly: the pieces (marked *exact*) are cut from
its solid with the same cells and joint shapes as B-rep prisms, so curved walls stay smooth; their STL is meshed
within 0.01 mm, their STEP is the exact solid.

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

## Windows program for customers (no Python)

`py tools/build/build.py` builds `dist/Auto3DModeler/Auto3DModeler.exe` (PyInstaller, one folder, ≈ 445 MB with the CAD
kernel), a portable zip (≈ 160 MB) and — with Inno Setup 6 installed — a per-user installer, then smoke-tests the
result. The exe starts the server on a free port and opens the app in its own window (Edge app mode); a second start
only opens the window, closing it quits, a tray icon has Open / Logs / Quit. The customer's data lives in
`%LOCALAPPDATA%\Auto3DModeler` (logs in `logs\`), never in the install folder. The AI chat is optional and needs the
customer's own Claude Code. Building, installing, updating, code signing and a short Czech guide for the customer
("Instalace"): [docs/DISTRIBUTION.md](docs/DISTRIBUTION.md).

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
