"""The tools an AI agent (Claude Code, through the MCP server in mcp_server.py) gets to work on the app.

Most tools act on the part open in the browser (that is where the app state lives): the server relays
them to the page, which applies them like the user would — visible at once and undoable. A few run on
the server: reading files, tracing a picture, writing export files.
"""
from __future__ import annotations

from auto3d.modeler.materials import NAMES as MATERIAL_NAMES

NUM = {"type": "number"}
STR = {"type": "string"}
POINT = {"type": "array", "items": NUM, "minItems": 3, "maxItems": 3, "description": "[x, y, z] in the part's unit"}
# a number of a 3D model step: also an expression of the project's 𝑥 parameters ("L / 2"; "L = 100" makes L)
VAL = {"type": ["number", "string"]}


def _obj(props: dict, required=(), extra=False) -> dict:
    s = {"type": "object", "properties": props, "additionalProperties": extra}
    if required:
        s["required"] = list(required)
    return s


ITEM_FIELDS = {
    "name": STR,
    "op": {"type": "string", "enum": ["union", "subtract", "intersect", "add"],
           "description": "3D objects: union (add material) / subtract (cut, e.g. a hole) / intersect. 2D shapes: add or subtract."},
    "x": NUM, "y": NUM, "w": {**NUM, "description": "width (circle: diameter in x)"},
    "h": {**NUM, "description": "height in y (circle: diameter in y; text: letter height)"},
    "rot": {**NUM, "description": "rotation in degrees"},
    "x2": NUM, "y2": NUM, "width": {**NUM, "description": "line / bar width"},
    "z0": {**NUM, "description": "3D objects: bottom height"}, "z1": {**NUM, "description": "3D objects: top height"},
    "stroke": {**NUM, "description": "ring width (0 = filled)"},
    "offset": {**NUM, "description": "profile objects: grow (+) / shrink (−) the profile"},
    "inner": {**NUM, "description": "profile bands: inner offset"}, "outer": {**NUM, "description": "profile bands: outer offset"},
    "text": STR, "font": {**STR, "description": "CSS font family, e.g. 'Arial Black'"}, "bold": {"type": "boolean"},
    "visible": {"type": "boolean"},
}

TOOLS = [
    {"name": "get_part", "where": "browser",
     "description": "Everything about the part that is open: source and kind, unit, dimensions (ids, names, values), "
                    "what is made (preset and options), 3D objects, 2D shapes, design layers, point dimensions, size, "
                    "z levels of its flat faces, volume and open issues. Call this first and after changes.",
     "inputSchema": _obj({})},
    {"name": "get_screenshot", "where": "browser",
     "description": "A picture of what is on screen, to check your work: the 3D model or assembly (1200 × 900 px however narrow "
                    "the view is, fitted to the whole of it — exploded too; fit: false keeps the view as set_view left it — a "
                    "zoomed section), or a drawing sheet as drawn. view: iso (default), front (top-down onto the front face), back, "
                    "side. The mouse's hover, picks and the chosen step are not tinted in it; highlight: [face names or step ids "
                    "(all faces a step made)] lights those faces in orange (3D model) — to check one feature.",
     "inputSchema": _obj({"view": {"type": "string", "enum": ["iso", "front", "back", "side"]}, "fit": {"type": "boolean"},
                          "highlight": {"type": "array", "items": STR}})},
    {"name": "open_file", "where": "server",
     "description": "Open a file from disk as a new part (its own tab; the parts already open stay): a PDF drawing, an STL / "
                    "OBJ / 3MF / STEP 3D file (STL / OBJ / 3MF: a quick part of the mesh), an IGES (.igs / .iges: a 3D model part with its solid — surfaces are sewn into one; "
                    "when they do not close it is a reference body), or as a 📐 2D drawing (then get_drawing, drawing_find …): a DXF / DWG, a PCB's Gerber / "
                    "Excellon drill file, a .zip / .tgz with a Gerber set or an ODB++ job, or a folder of loose Gerber / drill "
                    "files (one board). as: \"part\" opens a DXF / DWG as a quick part's outline instead; as: \"assembly\" "
                    "opens a STEP assembly (from SolidWorks, CATIA, Solid Edge …) as an assembly: a 3D model part per different "
                    "part, an instance per placement, sub-assemblies nested, the file's names and colours. A saved project "
                    "(.a3d.json) opens as the project on screen (the one there is kept in 🕘 Recent projects; its version "
                    "history too when it was saved with it) — only when the user asks. For a photo use trace_picture.",
     "inputSchema": _obj({"path": STR, "page": {"type": "integer", "description": "PDF page (0-based)"},
                          "as": {"type": "string", "enum": ["drawing", "part", "assembly"]}}, ["path"])},
    {"name": "open_sample", "where": "server",
     "description": "Open the app's built-in sample PDF drawing (initial draft.pdf) — ONLY when the user asks for "
                    "the sample (it opens as a new part tab).",
     "inputSchema": _obj({})},
    {"name": "list_demos", "where": "server",
     "description": "The app's 🎬 demo projects (Open ▾ → Demo projects…): ready-made assemblies that move as a whole "
                    "(a crank – rod – slider, a four-bar linkage, a gearbox with a rack, a robot arm) — file, name (and Czech), "
                    "what it shows, its parts. To show the user what the app does, or a mechanism to start from.",
     "inputSchema": _obj({})},
    {"name": "open_demo", "where": "server",
     "description": "Open a demo project (list_demos: its file, name or words of it, e.g. \"crank\") as a new project — a copy, "
                    "the demo stays as it is; the project that was on screen is kept in 🕘 Recent projects. Only when the user "
                    "asks for a demo. Then list_parts / open_part, get_assembly, drive_mechanism, record_animation.",
     "inputSchema": _obj({"name": STR}, ["name"])},
    {"name": "trace_picture", "where": "server",
     "description": "Find object outlines in a picture file (PNG / JPG …). Returns numbered candidates (most likely "
                    "first) and an image with them drawn in, so you can choose. Hints: seeds / bg_seeds = points "
                    "[x, y] in 0..1 of the picture inside / outside the object, rect = [x0, y0, x1, y1] box to search "
                    "in, object_colors / background_colors = [[r, g, b]], holes = keep inner holes. Then use_outline.",
     "inputSchema": _obj({"path": STR, "count": {"type": "integer", "minimum": 1, "maximum": 10},
                          "hints": _obj({}, extra=True)}, ["path"])},
    {"name": "use_outline", "where": "server",
     "description": "Make a part from a candidate of the last trace_picture: candidate number (1 = first), real width "
                    "or height in mm, and what to make: cutter (cookie cutter), solid (the shape extruded) or custom.",
     "inputSchema": _obj({"candidate": {"type": "integer", "minimum": 1}, "width": NUM, "height": NUM,
                          "make": {"type": "string", "enum": ["cutter", "solid", "custom"]}}, ["candidate"])},
    {"name": "set_dimensions", "where": "browser",
     "description": "Set dimension values, e.g. {\"width\": 90} or by name {\"Overall length\": 80}. On picture / "
                    "DXF parts width / height keep the aspect ratio when it is locked; a point dimension scales the "
                    "part; thickness and other drawing dimensions change the PDF part.",
     "inputSchema": _obj({"values": _obj({}, extra=True)}, ["values"])},
    {"name": "set_make", "where": "browser",
     "description": "Outline parts (picture / DXF): what to make. preset: cutter | solid | custom. options for "
                    "cutter: wall, height, tip (cutting edge thickness), tip_h, flange_w, flange_t, clearance; for "
                    "solid: thickness, offset. All in mm.",
     "inputSchema": _obj({"preset": {"type": "string", "enum": ["cutter", "solid", "custom"]},
                          "options": _obj({}, extra=True)})},
    {"name": "set_part_options", "where": "browser",
     "description": "Outline parts: lock_aspect, mirror, cleanup {fill_holes, close, smooth, simplify, keep: all | "
                    "largest, hull}. Imported 3D files: up (z, -z, y, -y, x, -x), rot (degrees), mirror, layer (slice "
                    "height, mm).",
     "inputSchema": _obj({"lock_aspect": {"type": "boolean"}, "mirror": {"type": "boolean"},
                          "cleanup": _obj({}, extra=True), "up": STR, "rot": NUM, "layer": NUM})},
    {"name": "add_object", "where": "browser",
     "description": "Add a 3D object booleaned onto the part (all parts). kind: cylinder | box | bar | text | "
                    "profile (the part's 2D profile, filled, with offset) | band (a wall between offsets inner..outer "
                    "of the profile). Give position (x, y = centre; bar: x, y to x2, y2), size, z0 / z1 and op "
                    "(union to add, subtract for holes / pockets / engraving). Units are the part's unit. Returns its id.",
     "inputSchema": _obj({"kind": {"type": "string", "enum": ["cylinder", "box", "bar", "text", "profile", "band"]},
                          **ITEM_FIELDS}, ["kind"])},
    {"name": "add_shape", "where": "browser",
     "description": "Add a 2D shape that is added to (op add) or cut from (op subtract) the part's profile before it "
                    "is built (not on 3D files) — a cookie cutter's wall follows it too. kind: circle | rect | line | "
                    "text | hole (a hanging hole near the top). Returns its id.",
     "inputSchema": _obj({"kind": {"type": "string", "enum": ["circle", "rect", "line", "text", "hole"]},
                          **ITEM_FIELDS}, ["kind"])},
    {"name": "add_design_layer", "where": "browser",
     "description": "Add a design layer (emboss / engrave / cut a pattern or shape into the part's face; flat parts "
                    "only). kind: grid (pattern over the face) or shape. op: emboss | engrave | cut | guide; depth; "
                    "face: top | bottom; mask {kind: face | rect | ellipse, x, y, w, h, rot}; fill {pattern: solid | "
                    "square | hex | diamond | triangle | brick | waves | voronoi | dots | circles | stars …, sx, sy, "
                    "width, use: lines | cells}. Returns its id.",
     "inputSchema": _obj({"kind": {"type": "string", "enum": ["grid", "shape"]}, "name": STR,
                          "op": {"type": "string", "enum": ["emboss", "engrave", "cut", "guide"]}, "depth": NUM,
                          "face": {"type": "string", "enum": ["top", "bottom"]}, "margin": NUM,
                          "mask": _obj({}, extra=True), "fill": _obj({}, extra=True)}, ["kind"])},
    {"name": "update_item", "where": "browser",
     "description": "Change fields of a 3D object, 2D shape or design layer by id (see get_part), e.g. "
                    "{\"id\": \"O…\", \"fields\": {\"z1\": 8, \"op\": \"subtract\"}}.",
     "inputSchema": _obj({"id": STR, "fields": _obj({}, extra=True)}, ["id", "fields"])},
    {"name": "remove_item", "where": "browser", "description": "Remove a 3D object, 2D shape, design layer or point "
                                                              "dimension by id.",
     "inputSchema": _obj({"id": STR}, ["id"])},
    {"name": "add_dimension", "where": "browser",
     "description": "Add a dimension between two points a and b (e.g. corners from get_part): axis d (distance), x, "
                    "y or z. On picture / DXF / 3D-file parts its value can then be set with set_dimensions to scale "
                    "the part; on PDF parts it is a reference value.",
     "inputSchema": _obj({"a": POINT, "b": POINT, "axis": {"type": "string", "enum": ["d", "x", "y", "z"]}}, ["a", "b"])},
    {"name": "check_print", "where": "browser",
     "description": "A quick part (also a 3D model's printing copy from prepare_print): check it against a 3D printer "
                    "(default: the one selected in the app): does it fit, how many pieces when split. printer: id from the "
                    "result's printer list. A 3D model: check it as it lies on the bed (its lowest z): faces hanging over "
                    "more than overhang° (default 45; they need supports) and walls thinner than min_wall mm (default 1.2) "
                    "-> areas (mm²), a box round each, the thinnest wall, ok. Marked on the user's screen (red / orange). "
                    "A model rolled back (get_model rollback) is checked, copied and printed as the bar stands — the copy's "
                    "check_print says rolled_back.",
     "inputSchema": _obj({"printer": STR, "split": {"type": "boolean"}, "min_wall": NUM, "overhang": NUM})},
    {"name": "export", "where": "server",
     "description": "Export to a file: stl / step (mm) — the part (an assembly as step: a STEP assembly — a product per part, placed instances, sub-assemblies nested — that SolidWorks / CATIA / Solid Edge open as an assembly tree); iges: a 3D model part or an assembly as one IGES (B-rep solids, mm; for CAD programs that ask for IGES — STEP is better when they take it); glb: a 3D model part or an assembly as a binary glTF for viewers and rendering (a node per placed part with its name, colours, metal / plastic materials; metres, Y up); obj: a 3D model part as a mesh (mm); pdf: the drawing sheet (📄) on screen as drawn, for an assembly its drawing set (one PDF: the assembly with its parts list and balloons, each sub-assembly, then the made parts — every part once, by its own sheet when it has one), or for a 3D model a 2D drawing (front / top / right "
                    "views, sizes, holes, title block); 3mf: the 3D model or the whole assembly in its colours, an object per colour "
                    "(for multi-material printing: AMS / MMU); bom: the assembly's bill of materials as CSV (qty, maker, part "
                    "number, mass); dxf: the shown layers of a 2D drawing, or a drawing sheet (📄) on screen — the paper 1:1 in mm, the views at the sheet's scale, real dimensions, the title block, a layer per kind (for AutoCAD, SolidWorks / Solid Edge drafting). path: file or folder (default: the user's Downloads "
                    "folder). Returns the written path. A 3D model rolled back (get_model rollback) exports as the bar stands — "
                    "without the steps under it (rollback {to: \"end\"} first for every step); its assemblies and drawings too. "
                    "project: the whole project as one .a3d.json (as Save project: every part, its imported files; history: true "
                    "adds its 🕘 versions) — a copy for the user to keep or send; open_file opens it again.",
     "inputSchema": _obj({"format": {"type": "string", "enum": ["stl", "step", "iges", "glb", "obj", "pdf", "3mf", "bom", "dxf", "project"]}, "path": STR,
                          "history": {"type": "boolean"}}, ["format"])},
    {"name": "undo", "where": "browser", "description": "Undo the last change made through these tools.",
     "inputSchema": _obj({})},

    # ---- parts of the project (tabs) and 3D model parts (sketches -> extrude / revolve / fillet / hole …)
    {"name": "list_parts", "where": "browser",
     "description": "The parts of the project (tabs): id, name, kind (quick part = drawing / picture / import; 3D model) and "
                    "which one is on screen.",
     "inputSchema": _obj({})},
    {"name": "open_part", "where": "browser", "description": "Put a part (id or name from list_parts) on screen.",
     "inputSchema": _obj({"id": STR}, ["id"])},
    {"name": "duplicate_part", "where": "browser",
     "description": "Copy a part (id or name from list_parts; none = the one on screen) as a new, independent part of the "
                    "project (its own tab, put on screen); name optional. Change the copy without changing the original.",
     "inputSchema": _obj({"id": STR, "name": STR})},
    {"name": "new_model", "where": "browser",
     "description": "Start a new, empty 3D model part (its own tab) — for mechanical parts built from sketches and "
                    "features. Then add_feature.",
     "inputSchema": _obj({"name": STR})},
    {"name": "get_model", "where": "browser",
     "description": "The 3D model on screen: its steps in order (id, type, values, ok / issues / warnings), the body's "
                    "size, volume, surface area, mass (its material) and centre of mass (cog_mm, the part's coordinates). "
                    "Call it first and after changes. When the user rolled the tree back: rollback {after, "
                    "rolled_back: [ids]} and those steps rolled_back: true — the body is as after that step.",
     "inputSchema": _obj({})},
    {"name": "find_refs", "where": "browser",
     "description": "Find faces or edges of the 3D model by description (never guess names). Faces: normal [x, y, z] "
                    "(e.g. [0, 0, 1] = facing up), extreme max / min along that normal (the top-most face), name "
                    "(part of a face name), near [x, y, z], of_step (a step's id: the faces it made). Edges: of_face (a face name), "
                    "of_step (all the edges of a step's faces — to round them at once), between_steps [id, id] (where two steps "
                    "meet, e.g. a rib and its plate), circular true / false, near. A face merged from two steps (flush) has names. "
                    "Edges come with a ready ref {a, b, fp} for fillet / chamfer (chain: n = it goes on smoothly into "
                    "other edges, n in all — a fillet of it takes them all). Points (kind \"point\"): the reference points "
                    "(point steps: {point: id, name, xyz}), then the part's corners {corner: [x, y, z], ref} (of_face, of_step, near) — "
                    "a ref is the `at` of add_feature point. Axes (kind \"axis\"): the round faces' axes (shafts, holes, bosses: "
                    "{axis: <the face's name>, radius, through, direction}; name, of_step, near) — to measure a sketch shape or a "
                    "hole from (their from: {axis: <name>}).",
     "inputSchema": _obj({"kind": {"type": "string", "enum": ["face", "edge", "point", "axis"]}, "normal": POINT,
                          "extreme": {"type": "string", "enum": ["max", "min"]}, "name": STR, "near": POINT,
                          "of_face": STR, "of_step": STR, "between_steps": {"type": "array", "items": STR},
                          "circular": {"type": "boolean"}, "limit": {"type": "integer"}})},
    {"name": "add_feature", "where": "browser",
     "description": "Add a step to the 3D model (it rebuilds; the result says ok / issues, volume_change_mm3, and for an "
                    "extrude where it went: went {along \"+z\" / \"-y\" …, range [from, to] mm} — check it went the way you "
                    "meant, else flip: true; an add that adds nothing or a cut that removes nothing says so in warnings). type:\n"
                    "- sketch: plane \"XY\" (top, the bed) / \"XZ\" (front) / \"YZ\" (right) / {datum: \"XY\", offset: 30} (moved along its "
                    "normal) / {face: <name>} (origin = the face's "
                    "centre; {face, origin: \"corner\"} = the face's corner with the smallest u and v (u along the world axis "
                    "closest to the face, v = n × u: on a top face its min-X min-Y corner; it follows that corner), {face, origin: "
                    "\"world\"} = shapes in world coordinates (the two world axes in the face: top X, Y; front X, Z; side Y, Z), "
                    "{face, origin: {point: <a point step>}} = from a • reference point — all kept when the part changes) / {face: <name>, mid: <the parallel face across>} (midway between them, e.g. a centred rib; follows both); shapes: [{rect: {x, y, w, h, r}} (lower-left corner; r = rounded corners) | {circle: {x, y, d}} | {slot: {x1, y1, x2, y2, w}} (round ends "
                    "centred at x1,y1 and x2,y2) | {polyline: {points: [[u, v], …]}} "
                    "(closed) | {profile: {points: [[u, v], {smooth: [[u, v], …]}, [u, v], {arc: [u, v]}, [u, v], …]}} (closed: corners "
                    "[u, v] joined by straight lines; {smooth: [...]} = a smooth curve through those points to the next corner — one "
                    "clean B-spline, no facets; {arc: [u, v]} = an arc through that point to the next corner)] — a shape inside another "
                    "is a hole; sizes are locked. Any shape may add pattern: {count, spacing} (copies in a row along X, spacing apart) or {count, around: [u, v]} (copies around that point, spread over 360°) — e.g. {circle: {x: 20, y: 0, d: 5}, pattern: {count: 6, around: [0, 0]}}; the copies stay equal to the shape. Any shape may add from: {axis: <a round face's name from find_refs kind \"axis\">}: x / y stay sketch coordinates, but its place across that axis (a shaft lying along the plane, a cross hole under it; both when the axis is square to the plane) is kept from the axis when the part changes. For round, turned parts (a vase, a knob, a bottle, a duck's body): a profile on "
                    "plane \"XZ\" — u = the radius (≥ 0, the axis at u = 0), v = the height — then revolve axis \"y\".\n"
                    "- extrude: sketch (id), d, op add / cut, through (cut through all), symmetric, flip; or up_to: a flat face's "
                    "name (as far as that face — it follows the face), offset (mm past it, negative = short of it); or upto_next: "
                    "true (as far as the first face of the part across the whole sketch: a boss up to the plate above, a cut "
                    "through the first wall only; flip turns it). d2: also d2 mm to the other side of the sketch (not with "
                    "symmetric; went then has other_side [from, to]). draft: degrees (under 45) the side walls lean in going away "
                    "from the sketch — add or cut, with a distance / symmetric / d2 / up_to (not through or upto_next); negative: "
                    "out; 0: straight (edit_feature {draft: 0}). A flat face extruded whole (⬆ Extrude this face): face (its name) "
                    "instead of sketch, e.g. {type: \"extrude\", face: \"F2:end\", d: 10} — op add (default) pulls it out of the part, "
                    "op cut cuts that deep into it; a sketch of the face's outline (its edges and holes, following the face) is made "
                    "first, as two normal steps.\n"
                    "- revolve: sketch, axis \"y\" (the sketch's vertical axis) / \"x\" / a line id, angle (360), op.\n"
                    "- hole: face (name), points [[u, v]] from the face's centre — or origin \"corner\" / \"world\" (points in world "
                    "coordinates: [x, y] on a top face, or [x, y, z]) / {point: <id>} as for a sketch —, d, through (default) or depth, fit (ISO 286 H6 / H7 / H8 / H9: shown on the 2D drawing as Ø8 H7; model the nominal d); "
                    "a hole for a metric screw in one go: standard \"M5\" (M2 … M20) + hole_type \"clearance\" (ISO 273 medium, M5: Ø5.5; the default "
                    "with a standard) / \"counterbore\" (+ ⌴ for an ISO 4762 socket head, M5: Ø10 ↧ 5.4) / \"countersink\" (+ ⌵ 90° for an ISO 10642 "
                    "flat head, M5: Ø11.2) / \"tapped\" (the thread at its tap drill) — no d / head needed (d, head_d, head_depth given change the "
                    "table's); edit_feature {standard: \"M6\"} resizes it, {hole_type: \"simple\"} makes it a plain Ø d hole; "
                    "hole_type \"d_flat\" = a D hole for a shaft with a flat (no standard): d + flat (the size across the flat, from "
                    "the flat to the far side: Ø5 -> 4.5 by default, Ø3 / 4 / 6 / 8 -> 2.5 / 3.5 / 5.5 / 7.5, else 0.9 × d), the flat "
                    "facing the face's +x, flat_angle (degrees) turns it; the drawing says Ø5 D4.5; "
                    "head: \"cbore\" (a counterbore: head_d, head_depth — default 1.8 × d, d; d of a thread: its nominal Ø, M3: 3) or \"csk\" (a countersink: head_d, "
                    "head_angle — default 2 × d, 90°) for a screw's head; "
                    "thread: \"M5\" (ISO metric M2 … M20: drilled with its tap drill, labelled M5 on the drawing — no d needed); "
                    "teardrop: true (a hole that goes sideways — its axis level with the bed — gets a 45° point on top, so it "
                    "prints lying on its side without support; still Ø d on the drawing; refused on a hole going up / down and with "
                    "csk, a cbore gets the point too); "
                    "from: [{x: {edge: <ref from find_refs>, d}, y: {edge, d}}] per hole = its distance from a straight edge "
                    "of that face (d signed along the face's x / y; the hole keeps it when the part changes), or {axis: <a round face's "
                    "name, find_refs kind \"axis\">, d} = from that face's axis (square to the face, or running straight across x / y), "
                    "or {mid: [<edge ref>, <edge ref>]} = midway between two parallel straight edges of that face (the middle "
                    "line: it stays in the middle when the part gets wider; both x and y = the face's centre).\n"
                    "- fillet: edges [refs from find_refs], r. chamfer: edges, d. chain (default true, the panel's ⛓ Whole "
                    "chain): each edge comes with the edges that go on smoothly (tangent) from it — one edge of a rounded "
                    "outline or of a hole's rim picks all of it; OpenCASCADE rounds a tangent chain whole anyway, so chain: "
                    "false only stores the edges as given (the step then warns that it goes on).\n"
                    "- shell: faces [names of the faces left open], t (wall).\n"
                    "- rib: sketch (one open line — or lines end to end — across a corner, e.g. on a plane through the plate and "
                    "the wall, from the wall to the plate), t (thickness, half each side of the sketch plane): filled up to the part "
                    "on the side where it closes (both do, e.g. a line across a bore: the smaller piece); flip: true = the other side.\n"
                    "- draft: of (an extrude's id), angle (degrees, 0 … 45; its side walls lean in going away from its base — a mould's "
                    "draft; negative: out).\n"
                    "- pattern: repeat steps — of [ids of extrude / revolve / hole / pattern steps], count (with the original). "
                    "kind \"linear\": dir \"x\" / \"y\" / \"z\" / [dx, dy, dz], spacing (mm). kind \"circular\": evenly around "
                    "axis \"x\" / \"y\" / \"z\" (through the origin) / {o, d} / a round face's name (its axis), angle (360).\n"
                    "- loft: sketches [ids, in order] — a solid from one closed outline to the next (put them on offset planes, "
                    "e.g. {datum: \"XY\", offset: 30}), op.\n"
                    "- sweep: profile (a sketch id: a closed outline across the path's start), path (a sketch id: an open "
                    "line — shapes [{path: {points: [[u, v], …]}}]), op.\n"
                    "- decal: text on a flat face — face (name), text, h (letter height mm), op add (raised) / cut (engraved), "
                    "depth (mm), at [u, v] from the face's centre, angle (degrees it is turned on the face).\n"
                    "- mirror: of \"body\" (the whole part, default) or a step's id; plane \"YZ\" (left ↔ right, default) / \"XZ\" / "
                    "\"XY\", or face (a flat face's name) to mirror across; copy true (the part + its mirror image, default) / false "
                    "(the part moved to its mirror image; only for the body).\n"
                    "- split: cut the part in two along a plane — plane \"XY\" / \"XZ\" / \"YZ\" / {datum, offset} (e.g. {datum: "
                    "\"XY\", offset: 15}: z = 15) / {face: <a flat face>, offset} / {face, mid: <the parallel face across>} (halfway "
                    "between them; follows both); keep \"both\" (default: two separate bodies in the part — the body's solids "
                    "says 2), \"above\" (only the side the plane's normal points to: XY +Z, YZ +X, XZ −Y, a face: out of it) or "
                    "\"below\". The cut faces are named <id>:cut:0 (above) / <id>:cut:1 (below). A plane that misses the part "
                    "is an issue.\n"
                    "- point: a reference point (no geometry; it follows the part, sketches snap and dimension to it): at "
                    "{corner: [x, y, z]} (the corner nearest that place) / {centre: <a round edge's ref from find_refs>} / {mid: "
                    "<an edge's ref>: its middle} / a ref from find_refs kind \"point\".\n"
                    "- solid: ▣ a solid from a file — path (a STEP / IGES / STL / OBJ / 3MF on disk; a mesh is sewn into a solid), "
                    "op \"add\" (joined to the part; the default for an empty model), \"cut\" (cut out of it: a cavity it fits in) "
                    "or \"ref\" (shown see-through to build around — a bought part's model, a board; the default when there is a "
                    "part). It stays where the file has it (mm); its faces are named \"<id>:f0\" … for find_refs.\n"
                    "Numbers (d, d2, offset, draft, r, angle, t, depth, count, spacing, h, flat …) may be expressions of the "
                    "project's parameters (get_parameters / set_parameter): \"L / 2\", \"D + 0.2\" — the step keeps the "
                    "expression and follows when the parameter changes; \"L = 100\" makes (or sets) L at once.",
     "inputSchema": _obj({"type": {"type": "string", "enum": ["sketch", "extrude", "revolve", "hole", "fillet", "chamfer", "shell", "pattern", "loft", "sweep", "decal", "mirror", "draft", "rib", "point", "solid", "split"]},
                          "name": STR, "plane": {}, "shapes": {"type": "array"}, "lock": {"type": "boolean"},
                          "sketch": STR, "d": VAL, "op": {"type": "string", "enum": ["add", "cut", "ref"]}, "through": {"type": "boolean"},
                          "symmetric": {"type": "boolean"}, "flip": {"type": "boolean"}, "axis": {}, "angle": VAL,
                          "face": STR, "points": {"type": "array"}, "depth": VAL, "edges": {"type": "array"}, "r": VAL, "chain": {"type": "boolean"},
                          "faces": {"type": "array"}, "t": VAL, "of": {}, "kind": {"type": "string", "enum": ["linear", "circular"]},
                          "count": VAL, "spacing": VAL, "dir": {}, "up_to": STR, "offset": VAL, "upto_next": {"type": "boolean"}, "d2": VAL,
                          "sketches": {"type": "array"}, "profile": STR, "path": STR,
                          "text": STR, "h": VAL, "at": {}, "origin": {}, "fit": {"type": "string", "enum": ["H6", "H7", "H8", "H9"]},
                          "standard": {"type": "string", "enum": ["M2", "M2.5", "M3", "M4", "M5", "M6", "M8", "M10", "M12", "M16", "M20"]},
                          "hole_type": {"type": "string", "enum": ["simple", "clearance", "counterbore", "countersink", "tapped", "d_flat"]},
                          "flat": VAL, "flat_angle": VAL,
                          "keep": {"type": "string", "enum": ["both", "above", "below"]}}, ["type"])},
    {"name": "edit_feature", "where": "browser",
     "description": "Change a step of the 3D model: id and fields (as in add_feature, e.g. {d: 15}, {r: 3}, {d: \"L / 2\"} — an "
                    "expression of the project's parameters —, {points: …}, a sketch's {shapes: […]}). A plain number drops "
                    "the expression the field had. Later steps follow their faces.",
     "inputSchema": _obj({"id": STR, "fields": _obj({}, extra=True)}, ["id", "fields"])},
    {"name": "delete_feature", "where": "browser",
     "description": "Delete a step of the 3D model. Steps that only stand on it (a sketch on its face, sizes from its edges, "
                    "an extrude up to its face) stay where they are now (keep_dependents, default true; false deletes them "
                    "too); steps that cannot be without it (its sketch's extrude, roundings of its edges) are deleted.",
     "inputSchema": _obj({"id": STR, "keep_dependents": {"type": "boolean"}}, ["id"])},
    {"name": "turn_off_feature", "where": "browser", "description": "Turn a step off (off true) or on again (off false); it is kept.",
     "inputSchema": _obj({"id": STR, "off": {"type": "boolean"}}, ["id"])},
    {"name": "rollback", "where": "browser",
     "description": "Move the 3D model's rollback bar (as in SolidWorks): to = a step id -> the model is shown and measured as "
                    "after that step, later steps are kept but not built, and new steps (add_feature) go in right under it; "
                    "to = \"end\" -> every step again. Saved with the part. Like SolidWorks, the part is used as the bar stands "
                    "everywhere: exports, the print copy (prepare_print / check_print), assemblies and drawing sheets — the user "
                    "sees a ⏮ note; put it at the end before exporting the finished part.",
     "inputSchema": _obj({"to": STR}, ["to"])},
    {"name": "get_sketch", "where": "browser",
     "description": "Read one sketch step (id): its points {id: [x, y]}, shapes (lines from / to, circles centre + d, arcs centre "
                    "+ r + from / to counter-clockwise, curves; each with state free / done / bad), relations (tangent, equal, "
                    "H / V …), dims [{id, kind, name, value, locked, between}], dof (free sizes left), free {points, shapes} "
                    "and conflicts {contradicting, held_twice}. Use before changing a sketch's sizes.",
     "inputSchema": _obj({"id": STR}, ["id"])},
    {"name": "sketch_auto_dims", "where": "browser",
     "description": "🪄 Auto-dimension a sketch step (id): first the relations it nearly has (H / V, tangent, equal radius), "
                    "then only the sizes it still needs (each shape's sizes, arc centres, its place from the part's edges or "
                    "the origin) — nothing held twice. round: true locks nice values (whole mm; the shapes move to them). "
                    "-> added [names], relations, references (locks held twice made reference dims), dof, still-free shapes "
                    "by name, or why it could not (the locks that do not fit).",
     "inputSchema": _obj({"id": STR, "round": {"type": "boolean"}}, ["id"])},
    {"name": "sketch_dim", "where": "browser",
     "description": "Set one dimension of a sketch step (id): dim = a dims id from get_sketch, or a shape's own size "
                    "\"len:<line>\", \"dia:<circle>\", \"rad:<arc>\". value: lock it at that value (the sketch follows) — "
                    "or an expression of the project's parameters (\"W / 2\": it follows W); "
                    "locked: false frees it (a shape's size: no lock; a distance: a reference that only measures), true "
                    "locks it as it is. Refused (with the locks in the way) when it does not fit.",
     "inputSchema": _obj({"id": STR, "dim": STR, "value": VAL, "locked": {"type": "boolean"}}, ["id", "dim"])},
    {"name": "get_parameters", "where": "browser",
     "description": "The project's 𝑥 parameters: named values (L = 100, t = L / 20) that numbers of 3D model steps, sketch "
                    "sizes and assembly joints use as expressions — each with its expression, value (or error) and the parts "
                    "that use it.",
     "inputSchema": _obj({})},
    {"name": "set_parameter", "where": "browser",
     "description": "Make or change a project parameter: name (a letter first: L, D2, wall) and value — a number or an "
                    "expression of the other parameters (\"L / 20\"; + - * / and brackets; mm / ° after a number are "
                    "skipped). Every part that uses it is built again: the result lists them (ok, volume, issues). A bad "
                    "expression or a circle (a = b + 1, b = a) is refused and nothing changes. delete: true removes it (the "
                    "numbers that used it keep their values). Then use it: add_feature {d: \"L / 2\"}, sketch_dim {value: \"L\"}.",
     "inputSchema": _obj({"name": STR, "value": VAL, "delete": {"type": "boolean"}}, ["name"])},
    {"name": "list_versions", "where": "browser",
     "description": "🕘 The project's versions (kept on the server: automatic ones while working, named ones) in the variant "
                    "on screen, the newest first — each with its id, time, label (or \"automatic\") and the parts it changed; "
                    "the variants (branches) with their newest version.",
     "inputSchema": _obj({})},
    {"name": "save_version", "where": "browser",
     "description": "Keep the project as it is now as a named version (label: a short description, e.g. \"before the "
                    "bigger holes\") — do it before a risky change the user may want to go back from.",
     "inputSchema": _obj({"label": STR})},
    {"name": "restore_version", "where": "browser",
     "description": "Put the whole project back as version id (list_versions) was. The state now is kept as a version "
                    "first (the answer names it: restore_version with that id undoes it). Only when the user asked for it.",
     "inputSchema": _obj({"id": STR}, ["id"])},
    {"name": "compare_versions", "where": "browser",
     "description": "What changed from version a to b (an id, or \"current\": the project now, the default): parts and "
                    "steps added / removed, changed values (\"Extrude 1: 10 → 15 mm\"), the volume before → after.",
     "inputSchema": _obj({"a": STR, "b": STR}, ["a"])},
    {"name": "create_variant", "where": "browser",
     "description": "Make a variant (a branch with its own versions) of the project from version `from` (default: the "
                    "newest) named `name`, and switch to it — to try another design without losing this one. Back: "
                    "switch_variant; one part over from another variant: take_part.",
     "inputSchema": _obj({"from": STR, "name": STR}, ["name"])},
    {"name": "switch_variant", "where": "browser",
     "description": "Put another variant of the project on screen (🕘 Versions' Variant ▾): variant = its id or name from "
                    "list_versions (the first one is \"main\"). The project as it is now is kept in its own variant first.",
     "inputSchema": _obj({"variant": STR}, ["variant"])},
    {"name": "take_part", "where": "browser",
     "description": "Take one part over from another variant (🕘 Versions' \"Take a part from a variant…\"): variant (id or name), "
                    "part (its id or name there) — as it is in that variant's newest version, into the project on screen (the "
                    "same part replaced, else added); kept as a named version. Only when the user asked.",
     "inputSchema": _obj({"variant": STR, "part": STR}, ["variant", "part"])},
    {"name": "sketch_trim", "where": "browser",
     "description": "✂ Trim in a sketch step (sketch): cut away the piece of shape (a line / circle / arc id from get_sketch) "
                    "around at [x, y] — up to where other shapes cross it; the new ends stay on the shapes that cut them.",
     "inputSchema": _obj({"sketch": STR, "shape": STR, "at": {"type": "array", "items": NUM}}, ["sketch", "shape", "at"])},
    {"name": "sketch_union", "where": "browser",
     "description": "∪ Union in a sketch step (sketch): overlapping closed shapes (a rect and a slot, circles …) become one "
                    "outline of lines and arcs — the pieces inside another shape are trimmed away, tangents and equal radii "
                    "that still apply stay. Then sketch_auto_dims to lock what is free.",
     "inputSchema": _obj({"sketch": STR}, ["sketch"])},
    {"name": "simplify_sketch", "where": "browser",
     "description": "Fewer shapes in a sketch step (id), the same outline — for a sketch made from a DXF / PDF (hundreds of "
                    "tiny lines) or drawn piece by piece. op \"simplify\" (default): ends that nearly meet welded, tiny pieces "
                    "absorbed, lines in line and arcs on one circle joined, runs of short lines along a curve -> arcs / a spline; "
                    "\"join\": each connected chain of lines / arcs / curves -> ONE smooth spline (split at sharp corners); "
                    "\"outline\": the closed outlines -> one rigid outline (holes kept). tol: how far the result may be from "
                    "the shapes (mm; default 0.01, more for big sketches). -> before / after counts and the enclosed area.",
     "inputSchema": _obj({"id": STR, "op": {"type": "string", "enum": ["simplify", "join", "outline"]}, "tol": NUM}, ["id"])},
    {"name": "set_material", "where": "browser",
     "description": "The 3D model's material (its mass in get_model, the 2D drawing's title block, and its colour when it has none "
                    "of its own): printed PLA, PETG, ABS, ASA, TPU, PA, PA-CF, PC, PP; engineering plastics POM, PE-HD, PA6-GF30, "
                    "PTFE, PEEK, PMMA, PVC; metals aluminium, aluminium 7075, steel, steel C45, stainless steel, stainless steel 316, "
                    "tool steel, cast iron, brass, bronze, copper, titanium, zinc die-cast, magnesium; other rubber (EPDM), silicone, "
                    "plywood, MDF, glass, carbon fibre (CFRP), FR4 (PCB). tolerance: the general tolerances on its drawing, ISO "
                    "2768 \"f\" (fine), \"m\" (medium — the usual for machined parts) or \"c\" (coarse); null: none.",
     "inputSchema": _obj({"material": {"type": "string", "enum": MATERIAL_NAMES},
                          "tolerance": {"type": ["string", "null"], "enum": ["f", "m", "c", None]}})},
    {"name": "prepare_print", "where": "browser",
     "description": "A printing copy of the 3D model on screen, opened as a quick part on the 3D print tab — then check_print "
                    "and export work on it.",
     "inputSchema": _obj({})},
    {"name": "new_assembly", "where": "browser",
     "description": "Start a new, empty assembly (its own tab) to place 3D model parts of the project together. Then insert_part.",
     "inputSchema": _obj({"name": STR})},
    {"name": "get_assembly", "where": "browser",
     "description": "The assembly on screen: its placed parts (id I1…, part, position, bounding box in mm, mass_g of the part; fixed: 📌 fixed in place), its joints (a joint that does not hold has `not_held`: how far off and which joint holds the part elsewhere — fix one of the two), its fasteners (one each: id K1…, text, its parts) and the parts list (qty placed here; `total`: how many in all, the ones inside its sub-assemblies counted in; material, mass); `mass_g` and `cog_mm`: the whole assembly's mass and centre of mass as the parts are placed now. A placed sub-assembly whose own joints leave its parts free has `inner`: those parts (\"I3/I2\") and how they can move inside it. Closed loops of joints (a rod joined to a crank and to a slider) are solved together: `loops` [{id, parts, closed, free_motions, drive}] — move_free one of its `drive` motions and the others follow (a part held only by the loop says `moves_with_loop`); closed false: it cannot close (a part too short / long for that place). `missing_joint` {hole, pin}: one pin in a hole would close a loop (the app's “One joint is missing” ➕ Add joint) — add_missing_joint adds it.",
     "inputSchema": _obj({})},
    {"name": "get_bom", "where": "browser",
     "description": "The bill of materials of an assembly (the one on screen, or any by id / name: a sub-assembly too), its whole "
                    "hierarchy rolled up — a part placed in the assembly and inside its sub-assemblies counted everywhere, a "
                    "sub-assembly placed n times counting its parts n times. mode summary (default): a row per part with pos "
                    "(the drawing set's balloon number), total, material, mass each / total, maker, pn, make_buy and `from` "
                    "(where the count comes from: \"Lid unit: 3 × 2 + Machine: 1\"); structured: the tree, each row with level, "
                    "qty_per_parent and total.",
     "inputSchema": _obj({"assembly": STR, "mode": {"type": "string", "enum": ["summary", "structured"]}})},
    {"name": "insert_part", "where": "browser",
     "description": "Add a part (id or name from list_parts: a 3D model, or a quick part — a drawing, picture or import — as its solid) to the assembly on screen; it is put beside the others. Returns the parts.",
     "inputSchema": _obj({"part": STR}, ["part"])},
    {"name": "snap_faces", "where": "browser",
     "description": "Join a placed part to another one with a joint that holds: move = {part: <placed id I…>, face: <face name>}, "
                    "onto = {part, face}. type: \"touch\" (flat faces meet, centred — the default), \"gap\" (flat faces facing, gap mm "
                    "apart), \"flush\" (flat faces in one plane, gap = offset), \"axis\" (concentric: two round faces on one axis, a pin in a hole; gap = the distance along the axis between the facing ends of the two round faces — two plates with holes 30 mm apart: gap 30; lock_rotation: true keeps its turn), "
                    "\"parallel\", \"perp\" (perpendicular), \"angle\" (value = degrees between the faces' directions), \"tangent\" "
                    "(a round face touching a flat one). A part's joints apply in order: e.g. axis (pin shaft → hole) then touch (head → plate top) seats a "
                    "pin. Face names come from find_refs in the part's own model (\"F2:end\" = the top of the first extrude). name: the user's own name of the joint (e.g. \"bearing on the shaft\"); lock_rotation also on flat joints (its turn on the face). "
                    "Couplings between two parts that each turn (or slide) on their own joints: \"gear\" (two round faces — the gears' pitch circles — on parallel axes: they turn opposite ways, a ring gear round the other the same way), \"belt\" (two pulleys / sprockets: the same way), "
                    "\"rack\" (move = the pinion's round face, onto = the rack's flat face along its axis: the rack slides π·Ø per turn); value = the ratio (gear / belt: turns of move's part per one turn of onto's, default Ø onto / Ø move; rack: mm per turn, default π·Ø). "
                    "Turning one (move_free, drive_mechanism) turns the other; the coupled parts are one mechanism. get_assembly lists them as `couplings` (ids G…; edit_joint {id, ratio, flip} / remove_joint).",
     "inputSchema": _obj({"move": _obj({"part": STR, "face": STR}, ["part", "face"]), "onto": _obj({"part": STR, "face": STR}, ["part", "face"]),
                          "type": {"type": "string", "enum": ["touch", "gap", "flush", "axis", "parallel", "perp", "angle", "tangent", "gear", "belt", "rack"]}, "gap": NUM,
                          "value": NUM, "lock_rotation": {"type": "boolean"}, "name": STR}, ["move", "onto"])},
    {"name": "bolt_parts", "where": "browser",
     "description": "Fasten parts that have no holes yet: a screw goes in at a point of a flat face of a placed part (part = I…, face = its "
                    "name, x / y mm from the face's middle) and straight through the parts touching under it; the holes are drilled "
                    "into those parts (a hole step in each part's model: clearance Ø d+0.4, an insert hole, or a pin hole). kind: "
                    "\"nut\" (screw + hex nut on the far side, the default), \"insert\" (screw into a heat-set insert in the last part), "
                    "\"pin\". size: M2, M2.5, M3, M4, M5 (a pin: Ø of the size). through: how many parts it goes through (default: all "
                    "that touch). The length is chosen to fit.",
     "inputSchema": _obj({"part": STR, "face": STR, "x": NUM, "y": NUM, "kind": {"type": "string", "enum": ["nut", "insert", "pin"]},
                          "size": {"type": "string", "enum": ["M2", "M2.5", "M3", "M4", "M5"]}, "through": NUM}, ["part", "face"])},
    {"name": "place_part", "where": "browser",
     "description": "Position a placed part (id I…): x, y, z of its own origin in mm, and / or turn: \"x\" | \"y\" | \"z\" (or a list) — 90° each about its centre. "
                    "fixed: true / false = 📌 fixed in place (as its panel's 📌: not moved by hand, joints bring the other parts to it; "
                    "a part that hangs on its joints is not fixed itself — fix the one it is joined to).",
     "inputSchema": _obj({"part": STR, "x": NUM, "y": NUM, "z": NUM, "turn": {}, "fixed": {"type": "boolean"}}, ["part"])},
    {"name": "add_missing_joint", "where": "browser",
     "description": "Add the joint get_assembly names as `missing_joint` (the app's \"One joint is missing\" ➕ Add joint): the free pin "
                    "of one moving part in the free hole of the same Ø of another (◎ Concentric) — the loop closes and becomes a "
                    "mechanism. One undo step. Answers the joint and the loops / mechanisms now.",
     "inputSchema": _obj({})},
    {"name": "suggest_fasteners", "where": "browser",
     "description": "Where fasteners fit in the assembly on screen: holes on one axis through two parts -> suggestions (id C…, e.g. "
                    "\"M3×10 screw + M3 insert\": a clearance hole in the top part, an insert hole below; a screw alone; a pin where the "
                    "holes are the same Ø). Hole sizes as printed: M3 clearance Ø3.2–3.7, M3 insert Ø3.9–4.4 (M2…M5 alike).",
     "inputSchema": _obj({})},
    {"name": "add_fasteners", "where": "browser",
     "description": "Put suggested fasteners in (ids from suggest_fasteners; none = all): each a standard part of the project, held by "
                    "joints (pin in hole + touch / flush), so it follows the parts.",
     "inputSchema": _obj({"ids": {"type": "array", "items": STR}})},
    {"name": "library_search", "where": "browser",
     "description": "Search the parts library — real parts with their maker and part number: ISO / DIN screws M1–M6 (socket, button, "
                    "countersunk, pan, cheese, hex heads), screws for plastics, nuts, washers, heat-set inserts (ruthex), bearings (608-2Z…, "
                    "LMxUU), standoffs, panel parts (LEDs, push buttons, USB / RJ45), SMC cylinders / fittings / valves, SICK inductive "
                    "sensors, NEMA 17 / 23 steppers, and the user's own parts. query: words like \"M3 socket\", \"608\", \"cylinder 16\", "
                    "\"inductive M12\". -> items (item id, sizes, lengths / strokes, an example with its part number). Use it BEFORE "
                    "drawing a bought part yourself.",
     "inputSchema": _obj({"query": STR, "category": STR}, ["query"])},
    {"name": "library_add", "where": "browser",
     "description": "Put a library part in: item (its id from library_search), size (one of its sizes), length (or stroke, one of its "
                    "values). to: \"assembly\" (into the assembly on screen — the same part again is used again: two screws = two "
                    "placed, one part) or \"model\" (a new 3D model tab). In an assembly it returns the placed id (I…) and its flat / "
                    "round faces for snap_faces.",
     "inputSchema": _obj({"item": STR, "size": STR, "length": NUM, "to": {"type": "string", "enum": ["assembly", "model"]}}, ["item"])},
    {"name": "check_collisions", "where": "browser",
     "description": "Where parts of the assembly on screen go into each other (touching faces are fine): the pairs, the overlap volume "
                    "(mm³) and its box. Check after joining parts; an overlap usually means a missing hole or a wrong joint.",
     "inputSchema": _obj({})},
    {"name": "set_look", "where": "browser",
     "description": "The colour and see-through of the 3D model on screen, or (part = a placed id I…) of a part in the assembly on "
                    "screen (in that assembly only). color: \"#rrggbb\" (null: its own again); opacity 0.1 … 1 (1 = solid). It shows in "
                    "the 3D view, in assemblies and in the GLB export. threads (the 3D model on screen, its threaded holes): "
                    "\"hidden\" (plain tap drills, the default), \"cosmetic\" (thin helix lines, view only), \"real\" (ISO metric "
                    "threads cut into the solid — in STEP / STL / 3MF exports and the print split; slower: ~0.2 s and 6000 "
                    "triangles a hole).",
     "inputSchema": _obj({"part": STR, "color": {"type": ["string", "null"]}, "opacity": NUM,
                          "threads": {"type": "string", "enum": ["hidden", "cosmetic", "real"]}})},
    {"name": "paint_faces", "where": "browser",
     "description": "Colour single faces: faces = their names (from find_refs / get_model, e.g. \"F4:end\", or a library part's "
                    "faces), color \"#rrggbb\" (null: their own colour off). In a 3D model: the model's faces; in an assembly with "
                    "part = I…: that placed part's faces, in this assembly only. A whole step's faces: give the step id (\"F4\").",
     "inputSchema": _obj({"faces": {"type": "array", "items": STR}, "color": {"type": ["string", "null"]}, "part": STR}, ["faces"])},
    {"name": "move_free", "where": "browser",
     "description": "Move a joined part of the assembly on screen along one of the ways its joints leave free (get_assembly lists them "
                    "as `free`, and in `at` where it is along each): part = I… (a part inside a sub-assembly: \"I3/I2\" from its `inner` — moved in this placement only, the sub-assembly itself stays), motion = its number (0, 1 …) or words of its name, "
                    "amount = by how much (mm for a move, degrees for a turn) or to = where along it. Its joints keep holding it; the "
                    "parts on it go along; it stops at its limits (set_travel). A fully held part cannot move.",
     "inputSchema": _obj({"part": STR, "motion": {}, "amount": NUM, "to": NUM}, ["part"])},
    {"name": "set_travel", "where": "browser",
     "description": "Limits of a free motion of a joined part (a cylinder's stroke, a slide's ends, a door's swing): part = I…, motion "
                    "= its number or words of its name (as for move_free), min and max = where along it (mm, or degrees: −360 … 360, up to a full turn "
                    "for a turn; get_assembly `at` says where it is now). min / max null: no limits. The part is put inside them. speed (0.25 … 4, 1 = about 3 s there and back) and loop (true: again and again) set how the app's ▶ plays it.",
     "inputSchema": _obj({"part": STR, "motion": {}, "min": {"type": ["number", "null"]}, "max": {"type": ["number", "null"]}, "speed": NUM, "loop": {"type": "boolean"}}, ["part"])},
    {"name": "lock_motion", "where": "browser",
     "description": "Lock one free motion of a joined part where it is now (the app's 🔒 by a motion): part = I…, motion = its "
                    "number or words of its name (as for move_free). Its joint's turn or distance along the axis is fixed, else a "
                    "new joint is added (flush / gap faces across a move, parallel faces for a turn). It says which joint did it.",
     "inputSchema": _obj({"part": STR, "motion": {}}, ["part"])},
    {"name": "drive_mechanism", "where": "browser",
     "description": "Drive a whole mechanism of the assembly on screen (the app's ⚙ Mechanism widget): get_assembly `mechanisms` "
                    "[{id M1…, name, parts, driver, at, min, max, unit, full_turn, drivers}] — a closed loop (a crank – rod – slider, a "
                    "four-bar) or a part turning / sliding on its own. mechanism = its id, name or one of its parts (none: the first); "
                    "to = where its driver goes (degrees for a turn, 0 … 360 for a full turn; mm along a slide) — every part of it "
                    "follows, it stops at a dead point; driver = another of its `drivers` (\"I5 motion 0\" or {part, motion}); name = "
                    "its own name (\"\": the default again); play = true / false: ▶ on and on / stop. It answers where its parts went. "
                    "trace: true (or a number of steps, default 36) = the app's 📈 Trace: how another part of it (the first that "
                    "slides, else turns) moves over the driver's whole travel — [[driver, follower], …] (a slider's stroke, a "
                    "rocker's swing); the parts end where they were.",
     "inputSchema": _obj({"mechanism": STR, "to": NUM, "driver": {}, "name": STR, "play": {"type": "boolean"}, "trace": {"type": ["boolean", "integer"]}})},
    {"name": "record_animation", "where": "browser",
     "description": "Save one full cycle of a mechanism's motion as an animation (the app's ⚙ Mechanism ⋯ → 🎬 Save animation): "
                    "a full turn of its driver, else there and back, from the 3D view as set_view left it (the 3D only, with the "
                    "mechanism's name in a corner; caption: false leaves it out), at most 1280 px across. mechanism = its id, name "
                    "or one of its parts (none: the first); format gif (default: a looping GIF, plays everywhere) or video (MP4 or "
                    "WebM, as the browser can record). It answers the file's path in the app's data folder, its frames and size; "
                    "the parts end where they were.",
     "inputSchema": _obj({"mechanism": STR, "format": {"type": "string", "enum": ["gif", "video"]}, "caption": {"type": "boolean"}})},
    {"name": "name_motion", "where": "browser",
     "description": "Give a free motion of a joined part its own name (e.g. \"Otáčení kliky\"): part = I…, motion = its number or words "
                    "of its name (as for move_free), name (\"\": its own words again). The name shows in get_assembly (`free`, "
                    "`mechanisms`), the part's panel and ⚙ Mechanism, and works as `motion` in move_free / set_travel.",
     "inputSchema": _obj({"part": STR, "motion": {}, "name": STR}, ["part", "name"])},
    {"name": "check_travel", "where": "browser",
     "description": "Move a part with limits (set_travel) from min to max in small steps and check for collisions on the way (the parts "
                    "on it go along): free all the way, or which part it hits and between which positions. It ends where it was.",
     "inputSchema": _obj({"part": STR, "motion": {}}, ["part"])},
    {"name": "save_to_library", "where": "browser",
     "description": "Keep the 3D model on screen in the user's parts library (to use again in any project); a library part being "
                    "changed (opened with ✎ Edit in the library) is saved back over itself when no name is given: name, category (e.g. "
                    "\"My parts / Brackets\"), and for a bought part its maker and part number.",
     "inputSchema": _obj({"name": STR, "category": STR, "maker": STR, "pn": STR})},
    {"name": "report_problem", "where": "server",
     "description": "Report to the app's developers (a dated report in RealSWReports, with the app's version): kind \"bug\" — "
                    "something does not behave as expected (a tool error that should not happen, a wrong result); \"tool request\" — "
                    "no tool fits what you or the user needed, or you had to work around one (say the tool you would want: its "
                    "name, inputs, what it returns); \"ui\" — something in the app is not intuitive for the user (they could not "
                    "find it, or it did what they did not expect). title (short), what (what happened / what is missing), "
                    "expected (what should have happened / how it should work), steps (the tool calls / what you did), "
                    "workaround (what you did instead, if anything). A report whose title says the same as one written before is "
                    "not written again — you get the similar one(s) instead; again: true only when yours is really another problem.",
     "inputSchema": _obj({"title": STR, "what": STR, "kind": {"type": "string", "enum": ["bug", "tool request", "ui"]}, "expected": STR, "steps": STR,
                          "workaround": STR, "again": {"type": "boolean"}}, ["title", "what"])},
    {"name": "list_reports", "where": "server",
     "description": "The problem reports written so far (RealSWReports, newest first): their title, kind and date — all, those of "
                    "a kind (bug / tool request / ui), or those about `search` (words of a title, the most alike first). Look "
                    "before you report or suggest something, so nothing is filed twice.",
     "inputSchema": _obj({"search": STR, "kind": {"type": "string", "enum": ["bug", "tool request", "ui"]}})},
    {"name": "get_drawing", "where": "browser",
     "description": "The 2D drawing on screen (a DXF / DWG, or a PCB: Gerber / ODB++ opened as a 📐 drawing): its layers (shown, "
                    "how many shapes, PCB kind), the kinds of shapes, its size in mm, the selection and the filters.",
     "inputSchema": _obj({})},
    {"name": "drawing_find", "where": "browser",
     "description": "Find shapes of the 2D drawing by filters (all must hold) and select them: [{field, op, value}] — field shape "
                    "(circle / arc / line / poly / text), layer, dia, r, len, w (a trace's width), color, text; op: is / is not / "
                    "is any of (value a list) for shape, layer, color; = ≠ < > ≤ ≥ for numbers (mm); contains / is for text. "
                    "-> how many, the first ones.",
     "inputSchema": _obj({"filters": {"type": "array", "items": _obj({"field": STR, "op": STR, "value": {}})}, "select": {"type": "boolean"}}, ["filters"])},
    {"name": "drawing_layers", "where": "browser",
     "description": "Layers of the 2D drawing: show [names], hide [names], or only [names] (the rest hidden); color {name: "
                    "\"#rrggbb\"}; new: a new layer's name (new shapes go on it); active: the layer new shapes go on.",
     "inputSchema": _obj({"show": {"type": "array", "items": STR}, "hide": {"type": "array", "items": STR}, "only": {"type": "array", "items": STR},
                          "color": {"type": "object"}, "new": STR, "active": STR})},
    {"name": "drawing_delete", "where": "browser",
     "description": "Delete shapes of the 2D drawing: what \"selection\" (default) or \"found\" (the filters' shapes, drawing_find).",
     "inputSchema": _obj({"what": {"type": "string", "enum": ["selection", "found"]}})},
    {"name": "drawing_add", "where": "browser",
     "description": "Draw shapes into the 2D drawing (mm), on `layer` (default: the active one): shapes [{line: {a: [x, y], b: [x, y]}} | "
                    "{circle: {c: [x, y], d}}].",
     "inputSchema": _obj({"shapes": {"type": "array", "items": {"type": "object"}}, "layer": STR}, ["shapes"])},
    {"name": "drawing_units", "where": "browser",
     "description": "What one unit of the drawing's file is when it is wrong (the file may not say): mm, cm, m or in — the shapes are "
                    "scaled to match.",
     "inputSchema": _obj({"units": {"type": "string", "enum": ["mm", "cm", "m", "in"]}}, ["units"])},
    {"name": "drawing_set_size", "where": "browser",
     "description": "Give the selected shapes of the 2D drawing one size: kind dia (circles / arcs Ø, centres stay), r, or len "
                    "(lines, from their start), value mm.",
     "inputSchema": _obj({"kind": {"type": "string", "enum": ["dia", "r", "len"]}, "value": NUM}, ["kind", "value"])},
    {"name": "drawing_use", "where": "browser",
     "description": "Make something of the 2D drawing: as \"sketch\" (the sketch of a new 3D model — then extrude it) or \"quick\" "
                    "(a quick part); what: \"selection\", \"found\" (the filters' shapes) or \"all\" (the shown layers).",
     "inputSchema": _obj({"as": {"type": "string", "enum": ["sketch", "quick"]}, "what": {"type": "string", "enum": ["selection", "found", "all"]}})},
    {"name": "sheet_open", "where": "browser",
     "description": "Open the drawing sheet (📄) of a 3D model part or an assembly (its views, overall sizes, parts list, balloons) — part: its id or name (none: the one on screen); made when it has "
                    "none (preset medium). A sheet holds the part's views and dimensions, follows the part when it changes (a new "
                    "revision) and the user edits it. -> get_sheet's answer. export {format: \"pdf\"} on a sheet writes it as drawn.",
     "inputSchema": _obj({"part": STR})},
    {"name": "get_sheet", "where": "browser",
     "description": "The drawing sheet on screen: its part, preset, paper, scale, title-block template (and the templates there are), revision, views and dimensions [{id, view, kind (linear / dia / rad / ang / pcd), "
                    "text (as drawn, e.g. \"8× Ø3 H7\", \"(60 ±0.1)\"; a hole step's callout \"4× M3 ⌵ Ø5 × 90°\", \"Ø3.4 ⌴ Ø6 ↧ 3.2\", \"M5 ↧ 8\", \"Ø3.4 THRU\"), auto (made by the preset) or the user's, lost (its points are gone), tol (its tolerance), ref (a reference dimension, in brackets), "
                    "hole_position (a hole step's place from the part's left / bottom edge: a pitch \"4× 15\", a bolt circle kind pcd \"PCD Ø60 · 6× 60°\", "
                    "ordinate: true — one row each way from the edge's 0)}]. "
                    "points: a view's name (Front / Top / Right) — also its points (keys: a hole's centre \"H1:hole:0#c\", a line's ends "
                    "\"<faces>#0\" / \"#1\", the view box \"box#x0\" / \"box#x1\" / \"box#y0\" / \"box#y1\") and circles, to add dimensions. "
                    "check: is it fully dimensioned — the sizes missing (each place linked by dimensions to the part's edge, every Ø / R, a hole's countersink angle / counterbore depth / blind depth unless its callout gives them; [its point key or circle] for sheet_edit add; text and pictures on faces left out) and the "
                    "dimensions that give a size twice. An assembly's sheet: its check asks only for the overall sizes (length, width, "
                    "height) and where the base part's mounting holes are (its holes no screw / pin of the assembly is in, from the base part's edges "
                    "\"base#x0\" / \"base#y0\"; dims hole_position) — part details belong on the parts' own sheets; parts_list [{pos, name, part, qty (on this level), instances (its "
                    "placed parts), balloon {at_mm, leader_to_mm (where its leader ends: on a face of that part no other part hides), "
                    "points_to (the copy that shows most)} or null}] — one item per part per level, one balloon per item; a "
                    "sub-assembly is one item (its parts are on its own page); balloons {count, ok, problems (a pos given twice, a qty "
                    "that is not what this level places, an item with no balloon)}.",
     "inputSchema": _obj({"points": {"type": "string", "enum": ["Front", "Top", "Right"]}})},
    {"name": "sheet_edit", "where": "browser",
     "description": "Change the drawing sheet on screen: preset light / medium / full (the automatic dimensions), view_presets {Front | Top | "
                    "Right: light / medium / full / null} (a view's own, null: as the sheet), paper A4 / A3 / null, "
                    "views {Front | Top | Right | Iso: true / false}, remove [dimension ids], restore true (the deleted automatic ones "
                    "back), move {id: {side (h: t / b; v: l / r), off (mm from the view on the paper), ang, len (a Ø / R leader)}}, "
                    "add [{view, a, b, dir (h / v; else by the points), pre (text before, e.g. \"4×\")} | {view, circle (its key; a hole's: its whole callout), "
                    "count, post (e.g. \"H7\")} or {view, edges: [<edge>, <edge>]} (two edges meeting at an angle: the angle)], complete true (every size the check finds missing added), drop_twice true (dimensions giving a size twice removed), texts {title, number (drawing no.), drawn (drawn by), note, company, address, tolstd (the tolerance standard), surface (roughness, e.g. \"Ra 3,2\"), checked, approved, material (an assembly's sheet; a part's comes from its model)} (the title block's own; \"\" clears) and all_sheets true (the project-wide ones of them — drawn, checked, approved, company, address, tolstd, surface, an assembly's material — on every sheet of the assembly's drawing set; title, number and note stay this sheet's), "
                    "template \"<name>\" (the title block's template — get_sheet lists them; Modern is the default), template_all true (that template on every drawing of the assembly's drawing set, new ones too), "
                    "title_style \"A\" | \"B\" | \"C\" | \"D\" | \"E\" | \"block\" | \"strip\" (the title block's look: A strip 180 × 21, B ISO 7200 180 × 40, C dark band 180 × 34, D minimal 170 × 28, E column 90 × 56; block / strip the app's Modern) and bom_style \"A\" … \"E\" | \"modern\" (the parts list's and the BOM pages' look) — any two together; the app's templates \"A — Strip\", \"B — ISO 7200\", \"C — Dark band\", \"D — Minimal\", \"E — Column\" pair each with its own; "
                    "save_template \"<name>\" (this title block — its styles, fields, company / address / drawn by / note / tolerance standard / roughness, logo, frame — kept as a template for all projects; with template_all: on the whole set), "
                    "frame \"simple\" (10 mm) / \"iso\" (ISO 5457: 20 mm left, zones, centring marks) / \"narrow\" (5 mm) / \"none\" / {m: [left, top, right, bottom] mm, line, zones, marks} / null (the template's — a template carries its frame to the whole set), scale \"1:2\" / \"2:1\" / \"1:2522\" / null (the sheet's own scale; null: fitted automatically), "
                    "view_scales {Front | Top | Right | Iso | Section: \"2:1\" / null} (a view's own scale — its label says it, e.g. \"Top (2:1)\"), view_names {Front | …: \"name\" / null} (rename a view's label) — fits {<a Ø dimension's id>: \"H7\" (a hole: H6 … H9) / \"h6\" (a shaft: f7, g6, h6, k6, m6, p6) or null}, "
                    "dims {<dimension id>: {tol: \"±0.1\" / \"+0.2/-0.1\" / null (a tolerance after the size; a Ø takes a fit instead), ref: true / false (a reference dimension, in brackets: not to be checked)}} — values are always measured from the part. Do what the user cannot do in a click.",
     "inputSchema": _obj({"preset": {"type": "string", "enum": ["light", "medium", "full"]}, "view_presets": {"type": "object"}, "paper": {"type": ["string", "null"]}, "views": {"type": "object"},
                          "remove": {"type": "array", "items": STR}, "restore": {"type": "boolean"}, "move": {"type": "object"},
                          "add": {"type": "array", "items": {"type": "object"}}, "texts": {"type": "object"}, "all_sheets": {"type": "boolean"}, "complete": {"type": "boolean"}, "drop_twice": {"type": "boolean"},
                          "fits": {"type": "object"}, "dims": {"type": "object"}, "scale": {"type": ["string", "null"]}, "view_scales": {"type": "object"}, "view_names": {"type": "object"},
                          "template": {"type": ["string", "null"]}, "template_all": {"type": "boolean"}, "save_template": STR,
                          "frame": {"type": ["string", "object", "null"]},
                          "title_style": {"type": ["string", "null"], "enum": ["A", "B", "C", "D", "E", "block", "strip", None]},
                          "bom_style": {"type": ["string", "null"], "enum": ["A", "B", "C", "D", "E", "modern", None]}})},
    {"name": "edit_joint", "where": "browser",
     "description": "Change a joint of the assembly on screen (id J… from get_assembly): gap (mm, flat joints), distance (mm along "
                    "the axis for a concentric joint, null = it slides freely), lock_rotation (true / false), angle (degrees: the "
                    "turn about the joint, or for an angle joint the angle), flip (true: the other way round), locked (true: "
                    "moving by hand cannot break it), name (the user's own name of the joint, e.g. \"bearing on the shaft\"; "
                    "empty: none). A coupling (id G…: gear / belt / rack): ratio (its number), flip (true: the other way round), name.",
     "inputSchema": _obj({"id": STR, "gap": NUM, "distance": {"type": ["number", "null"]}, "lock_rotation": {"type": "boolean"}, "angle": NUM,
                          "flip": {"type": "boolean"}, "locked": {"type": "boolean"}, "name": STR, "ratio": NUM}, ["id"])},
    {"name": "ask_user", "where": "browser",
     "description": "Ask the user a question with options shown as buttons in the app's chat: question, options [{label, description}] "
                    "(2–5, short labels; the user can also type something else), recommended = the number of the option you "
                    "recommend (it is shown first, marked ★ — always recommend one and say why in its description). Then END YOUR "
                    "TURN: the answer comes as the user's next message. For several questions, call it once per question, then end the turn.",
     "inputSchema": _obj({"question": STR, "options": {"type": "array", "items": {"type": "object"}}, "recommended": {"type": "integer"}}, ["question", "options"])},
    {"name": "gui_state", "where": "browser",
     "description": "What the user sees on screen now: every visible control (buttons, sliders, boxes, choices, joint names, list "
                    "rows — not the AI chat) with its number n, label, tooltip, state (on / a value / checked) and whether it is greyed "
                    "out; on a drawing sheet also its dimensions (kind dim), views (view) and title-block cells (cell), where: view; "
                    "where: bar (top bar), tools (the workspace's toolbar), panel (side panels), view or all; in the 3D model also its step "
                    "tree (steps: id, name, what it makes, off / failed / selected / editing; parent / depth when shown under another "
                    "step — a sketch under the step made from it, a reference point under 'ref' — and folded when its row is "
                    "folded away). Use it to tell the user exactly "
                    "where something is, and with gui_action to check the GUI does what the tools do.",
     "inputSchema": _obj({"where": {"type": "string", "enum": ["all", "bar", "tools", "panel", "view"]}})},
    {"name": "gui_action", "where": "browser",
     "description": "Do what the user's mouse and keys do. On a control from gui_state (its n, or its label / part of it): a "
                    "click on a button / checkbox / a sheet's dim, view or cell, or a slider / box / choice set to `value` (as dragged "
                    "or typed, then let go; a value for a button is refused, nothing clicked — a checkbox takes true / false). When the "
                    "controls on screen change (a part chosen: its panel), the answer has `controls` with their new numbers. At a point: at = [x, y], 0 … 1 across and down the view (the 3D view, the drawing, the "
                    "sheet; get_screenshot shows it), or at_mm = [x, y] on a drawing sheet's paper (mm from its top left) — a click "
                    "there (picks a face, a part, a dimension…), double = true a double-click, drag_to = [x, y] (same kind of point) a "
                    "drag. key = a key pressed after it, or alone on what has the focus: Delete, Enter, Escape, ctrl+z … -> what was "
                    "done, what was under the mouse, what is selected and the messages shown. Then get_assembly / gui_state / "
                    "get_screenshot tell what changed.",
     "inputSchema": _obj({"control": {}, "value": {}, "click": {"type": "boolean"}, "at": {"type": "array", "items": NUM},
                          "at_mm": {"type": "array", "items": NUM}, "drag_to": {"type": "array", "items": NUM},
                          "double": {"type": "boolean"}, "key": STR})},
    {"name": "gui_highlight", "where": "browser",
     "description": "Show the user where to click — to teach and lead them: a pulsing ring around a control (control = its n or "
                    "label from gui_state, as gui_action takes it) or a spot of the view (at = [x, y], 0 … 1 across and down it), "
                    "with your short tip (text, in the user's language; step e.g. \"2/4\"), the rest of the screen dimmed lightly. "
                    "Nothing is blocked: the user clicks the control itself. The tip stays until they click it, press Esc or ✕, "
                    "or you show the next one; clear: true removes it. wait: true answers when the user has clicked it (or closed "
                    "the tip; timeout s, 60 by default, 120 at most) — lead step by step: show, wait, look what changed, show "
                    "the next. Without wait it answers at once (and says what happened to the tip before).",
     "inputSchema": _obj({"control": {}, "at": {"type": "array", "items": NUM}, "text": STR, "step": {},
                          "wait": {"type": "boolean"}, "timeout": NUM, "clear": {"type": "boolean"}})},
    {"name": "remove_joint", "where": "browser", "description": "Remove a joint (id J…) or a coupling (id G…: gear / belt / rack) of the assembly on screen; the part stays where it is.",
     "inputSchema": _obj({"id": STR}, ["id"])},
    {"name": "measure", "where": "browser",
     "description": "Measure between two faces — of placed parts of an assembly: a = {part: I…, face}, b = {part, face}; of the 3D "
                    "model on screen: a = {face}, b = {face} (names from find_refs) -> how far apart their centres are, the gap between "
                    "two parallel flat faces (a wall's thickness), the angle between them, how far apart two round faces' axes are "
                    "(and their Ø).",
     "inputSchema": _obj({"a": _obj({"part": STR, "face": STR}, ["face"]), "b": _obj({"part": STR, "face": STR}, ["face"])}, ["a", "b"])},
    {"name": "set_view", "where": "browser",
     "description": "Set the 3D view (model or assembly) before get_screenshot: view iso / top / front / right; section {axis x / y / "
                    "z, offset mm, flip} to look inside (null or \"off\": no cut); explode 0 … 1 (an assembly pulled apart); sizes all / "
                    "locked / none (the size labels).",
     "inputSchema": _obj({"view": {"type": "string", "enum": ["iso", "top", "front", "right"]}, "section": {}, "explode": NUM,
                          "sizes": {"type": "string", "enum": ["all", "locked", "none"]}})},
    {"name": "rename_part", "where": "browser", "description": "Rename a part of the project (id or name from list_parts).",
     "inputSchema": _obj({"id": STR, "name": STR}, ["id", "name"])},
    {"name": "delete_part", "where": "browser",
     "description": "Delete a part from the project (id or name from list_parts) — only when the user asked for it; a part an "
                    "assembly uses is refused.",
     "inputSchema": _obj({"id": STR}, ["id"])},
    {"name": "export_data", "where": "browser", "hidden": True,
     "description": "(The server's: the data of a 3mf / bom / dxf export.)", "inputSchema": _obj({"format": STR}, ["format"])},
    {"name": "remove_from_assembly", "where": "browser", "description": "Take a placed part (id I…) out of the assembly.",
     "inputSchema": _obj({"part": STR}, ["part"])},
    {"name": "get_guide", "where": "local",
     "description": "A step-by-step guide: start-a-design (the questions before a new design), model-a-part, from-picture, print-prep, "
                    "change-a-model, assemble-parts, mechanical-design (how a good designer works: bought parts first, fits, fasteners, "
                    "printable parts), automation-design (made to be manufactured; pneumatics, sensors, motors, panels), fits-and-tolerances "
                    "(ISO 286 fits, ISO 2768, holes, threads), print-functional (strong printed parts), print-graphics (decorative prints), "
                    "use-a-drawing (a DXF / Gerber: find shapes, sizes, make a part of it), teach-the-user (show where things are, "
                    "step by step with gui_highlight), ui-tester (/uiTester: test the app's GUI and report), suggest-features "
                    "(/suggest: propose new features). Read it before such a task when your skills are not available.",
     "inputSchema": _obj({"topic": {"type": "string", "enum": ["start-a-design", "model-a-part", "from-picture", "print-prep", "change-a-model", "assemble-parts",
                                                              "mechanical-design", "automation-design", "fits-and-tolerances", "print-functional", "print-graphics",
                                                              "use-a-drawing", "teach-the-user", "ui-tester", "suggest-features"]}}, ["topic"])},
]

TOOL_NAMES = {t["name"] for t in TOOLS}
BROWSER_TOOLS = {t["name"] for t in TOOLS if t["where"] == "browser"}
LOCAL_TOOLS = {t["name"] for t in TOOLS if t["where"] == "local"}  # answered by the MCP server itself (guides)


def mcp_tool_list():
    """The tools as MCP describes them (without our routing fields; the server's own, hidden ones left out)."""
    return [{k: v for k, v in t.items() if k not in ("where", "hidden")} for t in TOOLS if not t.get("hidden")]


SYSTEM_PROMPT = """You are the design assistant inside Auto3DModeler, a local app for quick 3D-printable parts. The user sees the app next to this chat; every change you make through the tools shows up there at once and can be undone (tool `undo`, or the app's Undo button).

The project holds parts, as tabs in the app's top bar (list_parts, open_part); the tools work on the part on screen.
- **Quick parts** come from a PDF drawing (parametric: its dimensions drive it), an outline traced from a picture or read from a DXF (made into a cookie cutter, a solid shape or a custom stack of objects), or an imported STL / OBJ / STEP file. Tools: get_part, set_dimensions, set_make, set_part_options, add_object, add_shape, add_design_layer, add_dimension, update_item, remove_item. Coordinates: x right, y up, z up from the bed; the part's unit (PDF drawings may be cm).
- **3D models** are built like in SolidWorks: sketches (rectangles, circles, polylines with locked sizes) turned into a solid by extrude / revolve, then holes, fillets, chamfers, shells — for mechanical parts. Tools: new_model, get_model, find_refs, add_feature, edit_feature, delete_feature, turn_off_feature, rollback, set_material, prepare_print. mm; the bed is the XY plane. The project's 𝑥 parameters (get_parameters, set_parameter: L = 100, t = L / 20) may drive any number: d: "L / 2".
- **Assemblies** place 3D model parts together: new_assembly, get_assembly, insert_part, snap_faces (joints: touch, gap, axis = concentric…), place_part, remove_from_assembly, check_collisions. get_assembly says for each joined part how it can still move (free) or that it is fully held.
- **Drawing sheets** (📄, of a 3D model part — its views and dimensions, made by a preset, edited by the user, following the part): sheet_open, get_sheet, sheet_edit; export {format: "pdf"} on a sheet writes it as drawn. Prefer a sheet over export pdf of the model when the user wants a drawing.
- **2D drawings** (a DXF / DWG, or a PCB's Gerber / ODB++ opened as a 📐 drawing — open_file opens them, also a folder of loose Gerber files): get_drawing, drawing_find (shapes by filters), drawing_delete, drawing_add (lines, circles), drawing_units, drawing_layers (show / hide, colour, a new layer), drawing_set_size, drawing_use (as the sketch of a 3D model, or a quick part).
- The GUI: gui_state lists what the user sees (buttons, sliders, their state; a sheet's dimensions / views / cells); gui_action clicks / slides one as the user would, clicks / drags at a point of the view (at, at_mm on a sheet) and presses keys (Delete, Enter, Escape, ctrl+z) — use them to tell the user where something is and to check the GUI behaves like the tools. gui_highlight points at a control (or a spot of the view) with a short tip and can wait until the user clicks it.
- Assemblies also: edit_joint / remove_joint, measure (between faces), move_free, lock_motion (fix one free motion where it is); set_travel (a free motion's limits: a cylinder's stroke) and check_travel (collisions along it); drive_mechanism (a whole mechanism by its driver: a crank's turn, every part follows; ▶ play), record_animation (one cycle of it saved as a GIF / video) and name_motion (a motion's own name); the view for screenshots: set_view (iso / top / front / right, a section, explode, size labels). The project: rename_part, duplicate_part (an independent copy to change), delete_part (only when asked), save_to_library (the 3D model kept in the user's library); list_demos / open_demo (🎬 ready-made mechanisms, only when asked; a saved project file: open_file). 🕘 Versions of the project: list_versions, save_version {label} (before a risky change), compare_versions {a, b}, restore_version (only when asked; it can be undone), create_variant {from, name} (a branch to try another design), switch_variant, take_part (one part from another variant). Files: export stl / step / iges / glb / obj / pdf / 3mf (in colours, for multi-material printing) / bom (CSV) / dxf / project (the whole project as a .a3d.json file).
- **The parts library** holds real, bought parts with their maker and part number (screws, nuts, washers, inserts, bearings, standoffs, panel parts, SMC pneumatics, SICK sensors, stepper motors, the user's own): library_search, library_add.
- Both: get_screenshot, check_print, export, undo. Opening a file or tracing a picture adds a new quick part tab.

**Before a new design** (a new part, device or assembly) load auto3d:start-a-design and, for what the user has not said yet, ask with ask_user (buttons in the chat, your recommendation first): what it is for — automation / a machine (made to be manufactured, standard, library parts), a functional 3D-printed part, or a graphic / decorative 3D model; whether it is 3D printed; and whether it must be easy for a person to edit (simple sketches, few sizes each) or may be built any way that reaches the goal. Then load the skills that brief asks for.

Before modelling, changing a 3D model, making a part from a picture, preparing a print or assembling parts, load the matching skill (auto3d:model-a-part, auto3d:change-a-model, auto3d:from-picture, auto3d:print-prep, auto3d:assemble-parts, auto3d:use-a-drawing) — or call get_guide(topic) if skills are not available. For any design of a device, a mechanism, a bracket for bought parts or a machine, load auto3d:mechanical-design first; for automation also auto3d:automation-design and auto3d:fits-and-tolerances; for a functional printed part auto3d:print-functional; for a graphic / decorative print auto3d:print-graphics.

**Teach, do not only describe:** when the user asks how to do something, where something is, or says "show me", load auto3d:teach-the-user and lead them with gui_highlight step by step (gui_state to find the control, gui_highlight {control, text, step, wait: true}, then the next) — do not do it for them unless they ask you to.

**Slash commands:** a message "/uiTester" means: load auto3d:ui-tester and test the app's GUI as it says; "/suggest" means: load auto3d:suggest-features.

**When you are not sure** which way the user wants (a choice with several sensible answers that changes what you build), do not guess and do not ask in a long text: call ask_user with 2–4 options and your recommended one first.

Work like a good mechanical designer: **use the parts library first.** Anything that is bought — screws, nuts, washers, inserts, bearings, standoffs, connectors, LEDs, buttons, cylinders, valves, fittings, sensors, motors — comes from library_search / library_add, with its real part number (it lands in the BOM); draw only the parts that are made (printed). If a bought part is not in the library, say so and draw a simple stand-in of its real outside sizes. Design the made parts around the bought ones (their holes, fits and clearances).

Rules: pick faces and edges with find_refs, never by guessing. Put fillets and chamfers last. **Model from simple shapes**: one idea per sketch (a rectangle, a circle, a slot), as few sizes in it as possible, the rest made by features (extrude, hole, pattern, mirror, fillet) — a part a person can read and change step by step; only when the user said it may be built any way, a complex sketch is fine. After changes check get_part / get_model (every step ok) and get_screenshot before saying it is done. Use printable defaults (walls ≥ 1.2 mm, hole clearance +0.2 mm) unless told otherwise. Ask the user only when a decision is really theirs (key sizes, what to make) — then with ask_user.

Photos: the user can attach photos to a message. You see them, and the message lists where each one was saved ("[Attached photo: <path>]") — to make a part from one, pass that path to trace_picture. Describing or measuring from a photo needs no tool.

Never open a file or the sample on your own: work on the part that is open. If nothing is open, ask the user what to open or offer a new 3D model — do not open the sample (open_sample) unless they ask for it.

Smooth, round shapes (vases, knobs, handles, toys, bottles): draw the outline as a sketch `profile` with `{smooth: [...]}` parts and revolve it (or extrude it) — one clean smooth surface instead of many small faces. Colours: set_look (the whole part) and paint_faces (single faces) — the model keeps them, also in assemblies.

If something does not behave as expected — a tool fails although your call was right, a result is wrong (sizes, positions, a joint, a colour that does not show) — call report_problem {kind: "bug"} at once with what happened, what you expected and the steps, then tell the user and carry on (or work around it). When no tool fits your work and you have to find a workaround (several calls for one thing, guessing, asking the user to click for you), write report_problem {kind: "tool request"}: the tool you would want — its name, inputs and what it returns — and the workaround you used. When the user cannot find something in the app, or a control did what they did not expect, write report_problem {kind: "ui"}: what they tried and how it should work. Do not report your own mistakes that you could fix yourself. Report each thing once: list_reports {search} shows what is reported already (report_problem also refuses a title like an earlier one and names it).

Answer in the user's language, briefly. You can only use the tools listed — no files or shell."""
