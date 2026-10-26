# Auto3DModeler

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
- a **CAD / 3D file**: DXF / DWG drawings and STL / OBJ / STEP files;
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

**Several parts in one project**: every file you open becomes its own **part tab** in the top bar, next to the
project name (📁). Click a tab to switch parts; each keeps its edits and its own undo history. Double-click a
tab to rename it, and use **✕** to close it. The **＋** next to the tabs offers the usual ways to open a file.
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
   an arc keeps its other part(s), and the new ends stay on the shape that cut them. **⧈ Offset** (O): click a
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

**Pointing at and clicking the part.** The step under the mouse lights up (all its faces) and its name shows at
the mouse. A click on a face pops up the tools for it — sketch on it, a hole or text there, round / bevel its edges,
hollow it out with it open, edit / turn off / delete its step — and shows that step's **sizes on the part** (the
sketch's sizes on its plane, the height, Ø, R, the wall…). Click a size: a number and a **slider** — the part
follows while you slide; Enter / OK keeps it (one undo step), Esc goes back.

Every face of the model has a name ("the top of Extrude 1", "the wall made by line 3"). Roundings, holes and
sketches keep pointing at the same faces and edges when earlier sizes change. For example, make the box taller and
the rounded edge is still the same edge. If an edge can only be found again by its position, the step shows a
yellow ⚠.

**Looking at it:**
- **📏 Measure** (M): click a face for its type and area (and Ø when it is round), or an edge for its length (or
  Ø). Then click a second spot for the distance with Δx / Δy / Δz. It snaps to the part's corners, and edges hidden
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

## 2D drawings

**📐 Drawing (PDF)** in a 3D model's panel (or *PDF — 2D drawing* in the Export menu) makes an A4 drawing sheet:
the **Front**, **Top** and **Right** views with visible edges (solid) and hidden ones (dashed), an iso view, the
overall sizes dimensioned, every hole labelled (Ø) and listed with its position from the part's lower-left corner,
and a title block (name, size, material, mass, scale). The AI's `export {format: "pdf"}` writes the same file.

## Assemblies

**＋ New assembly** (in the ＋ menu next to the part tabs) opens an assembly tab (◇), where the parts of the project
are placed together — 3D models ◆ and quick parts ▤ (drawings, pictures, imports: they go in as their solid):
- **＋ Insert part ▾** adds a model part, as often as you like (⧉ in the list adds one more). A new one is put
  beside the others.
- **🧲 Snap face to face** (S): click a flat face of the part to move, then the flat face it goes onto. The part
  turns and moves so that the two faces meet, centred on each other. The snap **holds**: when the other part moves,
  or either part changes size in its own tab, the snapped part follows (🔗 in its panel; *Unlink* or moving it by
  hand ends that).
- The panel of a selected part has its x / y / z position, **⟲ 90°** turns about X / Y / Z, *Snap it onto
  another face*, *Reset its place* and *Take it out*.
- **Explode** pulls the parts apart to look at them; their placement does not change.
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
- **Skills**: the workflow guides in [agent_plugin/skills/](agent_plugin/skills/) — model-a-part,
  change-a-model, from-picture, print-prep, assemble-parts. They are loaded as a Claude Code plugin for the chat
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
- **STL / OBJ / STEP** (STEP is tessellated with `cascadio` / OpenCASCADE): the part is cut into flat slices at every
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
