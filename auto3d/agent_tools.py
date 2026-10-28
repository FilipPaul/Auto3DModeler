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
     "description": "A picture of what is on screen, to check your work: the 3D model or assembly (fitted to the whole of it; "
                    "fit: false keeps the view as set_view left it — a zoomed section), or a drawing sheet as drawn. view: iso "
                    "(default), front (top-down onto the front face), back, side.",
     "inputSchema": _obj({"view": {"type": "string", "enum": ["iso", "front", "back", "side"]}, "fit": {"type": "boolean"}})},
    {"name": "open_file", "where": "server",
     "description": "Open a file from disk as a new part (its own tab; the parts already open stay): a PDF drawing, an STL / "
                    "OBJ / STEP 3D file, or as a 📐 2D drawing (then get_drawing, drawing_find …): a DXF / DWG, a PCB's Gerber / "
                    "Excellon drill file, a .zip / .tgz with a Gerber set or an ODB++ job, or a folder of loose Gerber / drill "
                    "files (one board). as: \"part\" opens a DXF / DWG as a quick part's outline instead. For a photo use "
                    "trace_picture.",
     "inputSchema": _obj({"path": STR, "page": {"type": "integer", "description": "PDF page (0-based)"},
                          "as": {"type": "string", "enum": ["drawing", "part"]}}, ["path"])},
    {"name": "open_sample", "where": "server",
     "description": "Open the app's built-in sample PDF drawing (initial draft.pdf) — ONLY when the user asks for "
                    "the sample (it opens as a new part tab).",
     "inputSchema": _obj({})},
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
     "description": "Check the part against a 3D printer (default: the one selected in the app): does it fit, how "
                    "many pieces when split. printer: id from the result's printer list.",
     "inputSchema": _obj({"printer": STR, "split": {"type": "boolean"}})},
    {"name": "export", "where": "server",
     "description": "Export to a file: stl / step (mm) — the part; pdf: the drawing sheet (📄) on screen as drawn, for an assembly its drawing set (one PDF: the assembly with its parts list and balloons, each sub-assembly, then the made parts — every part once, by its own sheet when it has one), or for a 3D model a 2D drawing (front / top / right "
                    "views, sizes, holes, title block); 3mf: the 3D model or the whole assembly in its colours, an object per colour "
                    "(for multi-material printing: AMS / MMU); bom: the assembly's bill of materials as CSV (qty, maker, part "
                    "number, mass); dxf: the shown layers of a 2D drawing. path: file or folder (default: the user's Downloads "
                    "folder). Returns the written path.",
     "inputSchema": _obj({"format": {"type": "string", "enum": ["stl", "step", "pdf", "3mf", "bom", "dxf"]}, "path": STR}, ["format"])},
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
                    "size and volume. Call it first and after changes.",
     "inputSchema": _obj({})},
    {"name": "check_print", "where": "browser",
     "description": "Check the 3D model for 3D printing as it lies on the bed (its lowest z): faces hanging over more than overhang° "
                    "(default 45; they need supports) and walls thinner than min_wall mm (default 1.2) -> areas (mm²), a box round each, "
                    "the thinnest wall, ok. Marked on the user's screen (red / orange).",
     "inputSchema": _obj({"min_wall": NUM, "overhang": NUM})},
    {"name": "find_refs", "where": "browser",
     "description": "Find faces or edges of the 3D model by description (never guess names). Faces: normal [x, y, z] "
                    "(e.g. [0, 0, 1] = facing up), extreme max / min along that normal (the top-most face), name "
                    "(part of a face name), near [x, y, z], of_step (a step's id: the faces it made). Edges: of_face (a face name), "
                    "of_step (all the edges of a step's faces — to round them at once), between_steps [id, id] (where two steps "
                    "meet, e.g. a rib and its plate), circular true / false, near. A face merged from two steps (flush) has names. "
                    "Edges come with a ready ref {a, b, fp} for fillet / chamfer.",
     "inputSchema": _obj({"kind": {"type": "string", "enum": ["face", "edge"]}, "normal": POINT,
                          "extreme": {"type": "string", "enum": ["max", "min"]}, "name": STR, "near": POINT,
                          "of_face": STR, "of_step": STR, "between_steps": {"type": "array", "items": STR},
                          "circular": {"type": "boolean"}, "limit": {"type": "integer"}})},
    {"name": "add_feature", "where": "browser",
     "description": "Add a step to the 3D model (it rebuilds; the result says ok / issues, volume_change_mm3, and for an "
                    "extrude where it went: went {along \"+z\" / \"-y\" …, range [from, to] mm} — check it went the way you "
                    "meant, else flip: true). type:\n"
                    "- sketch: plane \"XY\" (top, the bed) / \"XZ\" (front) / \"YZ\" (right) / {datum: \"XY\", offset: 30} (moved along its "
                    "normal) / {face: <name>} (origin = the face's "
                    "centre); shapes: [{rect: {x, y, w, h, r}} (lower-left corner; r = rounded corners) | {circle: {x, y, d}} | {slot: {x1, y1, x2, y2, w}} (round ends "
                    "centred at x1,y1 and x2,y2) | {polyline: {points: [[u, v], …]}} "
                    "(closed) | {profile: {points: [[u, v], {smooth: [[u, v], …]}, [u, v], {arc: [u, v]}, [u, v], …]}} (closed: corners "
                    "[u, v] joined by straight lines; {smooth: [...]} = a smooth curve through those points to the next corner — one "
                    "clean B-spline, no facets; {arc: [u, v]} = an arc through that point to the next corner)] — a shape inside another "
                    "is a hole; sizes are locked. For round, turned parts (a vase, a knob, a bottle, a duck's body): a profile on "
                    "plane \"XZ\" — u = the radius (≥ 0, the axis at u = 0), v = the height — then revolve axis \"y\".\n"
                    "- extrude: sketch (id), d, op add / cut, through (cut through all), symmetric, flip; or up_to: a flat face's "
                    "name (as far as that face — it follows the face), offset (mm past it, negative = short of it).\n"
                    "- revolve: sketch, axis \"y\" (the sketch's vertical axis) / \"x\" / a line id, angle (360), op.\n"
                    "- hole: face (name), points [[u, v]] from the face's centre, d, through (default) or depth, fit (ISO 286 H6 / H7 / H8 / H9: shown on the 2D drawing as Ø8 H7; model the nominal d); "
                    "head: \"cbore\" (a counterbore: head_d, head_depth — default 1.8 × d, d) or \"csk\" (a countersink: head_d, "
                    "head_angle — default 2 × d, 90°) for a screw's head; "
                    "thread: \"M5\" (ISO metric M2 … M20: drilled with its tap drill, labelled M5 on the drawing — no d needed); "
                    "from: [{x: {edge: <ref from find_refs>, d}, y: {edge, d}}] per hole = its distance from a straight edge "
                    "of that face (d signed along the face's x / y; the hole keeps it when the part changes).\n"
                    "- fillet: edges [refs from find_refs], r. chamfer: edges, d.\n"
                    "- shell: faces [names of the faces left open], t (wall).\n"
                    "- rib: sketch (one open line — or lines end to end — across a corner, e.g. on a plane through the plate and "
                    "the wall, from the wall to the plate), t (thickness, half each side of the sketch plane): filled up to the part.\n"
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
                    "(the part moved to its mirror image; only for the body).",
     "inputSchema": _obj({"type": {"type": "string", "enum": ["sketch", "extrude", "revolve", "hole", "fillet", "chamfer", "shell", "pattern", "loft", "sweep", "decal", "mirror", "draft", "rib"]},
                          "name": STR, "plane": {}, "shapes": {"type": "array"}, "lock": {"type": "boolean"},
                          "sketch": STR, "d": NUM, "op": {"type": "string", "enum": ["add", "cut"]}, "through": {"type": "boolean"},
                          "symmetric": {"type": "boolean"}, "flip": {"type": "boolean"}, "axis": {}, "angle": NUM,
                          "face": STR, "points": {"type": "array"}, "depth": NUM, "edges": {"type": "array"}, "r": NUM,
                          "faces": {"type": "array"}, "t": NUM, "of": {}, "kind": {"type": "string", "enum": ["linear", "circular"]},
                          "count": NUM, "spacing": NUM, "dir": {}, "up_to": STR, "offset": NUM,
                          "sketches": {"type": "array"}, "profile": STR, "path": STR,
                          "text": STR, "h": NUM, "at": {"type": "array"}, "fit": {"type": "string", "enum": ["H6", "H7", "H8", "H9"]}}, ["type"])},
    {"name": "edit_feature", "where": "browser",
     "description": "Change a step of the 3D model: id and fields (as in add_feature, e.g. {d: 15}, {r: 3}, {points: …}, a "
                    "sketch's {shapes: […]}). Later steps follow their faces.",
     "inputSchema": _obj({"id": STR, "fields": _obj({}, extra=True)}, ["id", "fields"])},
    {"name": "delete_feature", "where": "browser",
     "description": "Delete a step of the 3D model. Steps that only stand on it (a sketch on its face, sizes from its edges, "
                    "an extrude up to its face) stay where they are now (keep_dependents, default true; false deletes them "
                    "too); steps that cannot be without it (its sketch's extrude, roundings of its edges) are deleted.",
     "inputSchema": _obj({"id": STR, "keep_dependents": {"type": "boolean"}}, ["id"])},
    {"name": "turn_off_feature", "where": "browser", "description": "Turn a step off (off true) or on again (off false); it is kept.",
     "inputSchema": _obj({"id": STR, "off": {"type": "boolean"}}, ["id"])},
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
     "description": "The assembly on screen: its placed parts (id I1…, part, position, bounding box in mm), its joints (a joint that does not hold has `not_held`: how far off and which joint holds the part elsewhere — fix one of the two), its fasteners (one each: id K1…, text, its parts) and the parts list (qty, material, mass).",
     "inputSchema": _obj({})},
    {"name": "insert_part", "where": "browser",
     "description": "Add a part (id or name from list_parts: a 3D model, or a quick part — a drawing, picture or import — as its solid) to the assembly on screen; it is put beside the others. Returns the parts.",
     "inputSchema": _obj({"part": STR}, ["part"])},
    {"name": "snap_faces", "where": "browser",
     "description": "Join a placed part to another one with a joint that holds: move = {part: <placed id I…>, face: <face name>}, "
                    "onto = {part, face}. type: \"touch\" (flat faces meet, centred — the default), \"gap\" (flat faces facing, gap mm "
                    "apart), \"flush\" (flat faces in one plane, gap = offset), \"axis\" (concentric: two round faces on one axis, a pin in a hole; gap = the distance along the axis between the facing ends of the two round faces — two plates with holes 30 mm apart: gap 30; lock_rotation: true keeps its turn), "
                    "\"parallel\", \"perp\" (perpendicular), \"angle\" (value = degrees between the faces' directions), \"tangent\" "
                    "(a round face touching a flat one). A part's joints apply in order: e.g. axis (pin shaft → hole) then touch (head → plate top) seats a "
                    "pin. Face names come from find_refs in the part's own model (\"F2:end\" = the top of the first extrude). name: the user's own name of the joint (e.g. \"bearing on the shaft\"); lock_rotation also on flat joints (its turn on the face).",
     "inputSchema": _obj({"move": _obj({"part": STR, "face": STR}, ["part", "face"]), "onto": _obj({"part": STR, "face": STR}, ["part", "face"]),
                          "type": {"type": "string", "enum": ["touch", "gap", "flush", "axis", "parallel", "perp", "angle", "tangent"]}, "gap": NUM,
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
     "description": "Position a placed part (id I…): x, y, z of its own origin in mm, and / or turn: \"x\" | \"y\" | \"z\" (or a list) — 90° each about its centre.",
     "inputSchema": _obj({"part": STR, "x": NUM, "y": NUM, "z": NUM, "turn": {}}, ["part"])},
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
                    "the 3D view, in assemblies and in the GLB export.",
     "inputSchema": _obj({"part": STR, "color": {"type": ["string", "null"]}, "opacity": NUM})},
    {"name": "paint_faces", "where": "browser",
     "description": "Colour single faces: faces = their names (from find_refs / get_model, e.g. \"F4:end\", or a library part's "
                    "faces), color \"#rrggbb\" (null: their own colour off). In a 3D model: the model's faces; in an assembly with "
                    "part = I…: that placed part's faces, in this assembly only. A whole step's faces: give the step id (\"F4\").",
     "inputSchema": _obj({"faces": {"type": "array", "items": STR}, "color": {"type": ["string", "null"]}, "part": STR}, ["faces"])},
    {"name": "move_free", "where": "browser",
     "description": "Move a joined part of the assembly on screen along one of the ways its joints leave free (get_assembly lists them "
                    "as `free`, and in `at` where it is along each): part = I…, motion = its number (0, 1 …) or words of its name, "
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
                    "workaround (what you did instead, if anything).",
     "inputSchema": _obj({"title": STR, "what": STR, "kind": {"type": "string", "enum": ["bug", "tool request", "ui"]}, "expected": STR, "steps": STR,
                          "workaround": STR}, ["title", "what"])},
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
     "description": "The drawing sheet on screen: its part, preset, paper, revision, views and dimensions [{id, view, kind (linear / dia / rad), "
                    "text (as drawn, e.g. \"8× Ø3 H7\"), auto (made by the preset) or the user's, lost (its points are gone)}]. "
                    "points: a view's name (Front / Top / Right) — also its points (keys: a hole's centre \"H1:hole:0#c\", a line's ends "
                    "\"<faces>#0\" / \"#1\", the view box \"box#x0\" / \"box#x1\" / \"box#y0\" / \"box#y1\") and circles, to add dimensions. "
                    "check: is it fully dimensioned — the sizes missing (each place linked by dimensions to the part's edge, every Ø / R) and the "
                    "dimensions that give a size twice. An assembly's sheet also has parts_list [{pos, name, part, qty, instances (its "
                    "placed parts), balloon {at_mm, points_to (the placed part it points at)} or null}] — one balloon per item; a "
                    "sub-assembly is one item (its parts are on its own page).",
     "inputSchema": _obj({"points": {"type": "string", "enum": ["Front", "Top", "Right"]}})},
    {"name": "sheet_edit", "where": "browser",
     "description": "Change the drawing sheet on screen: preset light / medium / full (the automatic dimensions), view_presets {Front | Top | "
                    "Right: light / medium / full / null} (a view's own, null: as the sheet), paper A4 / A3 / null, "
                    "views {Front | Top | Right | Iso: true / false}, remove [dimension ids], restore true (the deleted automatic ones "
                    "back), move {id: {side (h: t / b; v: l / r), off (mm from the view on the paper), ang, len (a Ø / R leader)}}, "
                    "add [{view, a, b, dir (h / v; else by the points), pre (text before, e.g. \"4×\")} | {view, circle (its key), "
                    "count, post (e.g. \"H7\")} or {view, edges: [<edge>, <edge>]} (two edges meeting at an angle: the angle)], complete true (every size the check finds missing added), drop_twice true (dimensions giving a size twice removed), texts {title, number (drawing no.), drawn (drawn by), note} (the title block's own; \"\" clears) — fits {<a Ø dimension's id>: \"H7\" (a hole: H6 … H9) / \"h6\" (a shaft: f7, g6, h6, k6, m6, p6) or null} — values are always measured from the part. Do what the user cannot do in a click.",
     "inputSchema": _obj({"preset": {"type": "string", "enum": ["light", "medium", "full"]}, "view_presets": {"type": "object"}, "paper": {"type": ["string", "null"]}, "views": {"type": "object"},
                          "remove": {"type": "array", "items": STR}, "restore": {"type": "boolean"}, "move": {"type": "object"},
                          "add": {"type": "array", "items": {"type": "object"}}, "texts": {"type": "object"}, "complete": {"type": "boolean"}, "drop_twice": {"type": "boolean"},
                          "fits": {"type": "object"}})},
    {"name": "edit_joint", "where": "browser",
     "description": "Change a joint of the assembly on screen (id J… from get_assembly): gap (mm, flat joints), distance (mm along "
                    "the axis for a concentric joint, null = it slides freely), lock_rotation (true / false), angle (degrees: the "
                    "turn about the joint, or for an angle joint the angle), flip (true: the other way round), locked (true: "
                    "moving by hand cannot break it), name (the user's own name of the joint, e.g. \"bearing on the shaft\"; "
                    "empty: none).",
     "inputSchema": _obj({"id": STR, "gap": NUM, "distance": {"type": ["number", "null"]}, "lock_rotation": {"type": "boolean"}, "angle": NUM,
                          "flip": {"type": "boolean"}, "locked": {"type": "boolean"}, "name": STR}, ["id"])},
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
                    "where: bar (top bar), tools (the workspace's toolbar), panel (side panels), view or all. Use it to tell the user exactly "
                    "where something is, and with gui_action to check the GUI does what the tools do.",
     "inputSchema": _obj({"where": {"type": "string", "enum": ["all", "bar", "tools", "panel", "view"]}})},
    {"name": "gui_action", "where": "browser",
     "description": "Do what the user's mouse and keys do. On a control from gui_state (its n, or its label / part of it): a "
                    "click on a button / checkbox / a sheet's dim, view or cell, or a slider / box / choice set to `value` (as dragged "
                    "or typed, then let go). At a point: at = [x, y], 0 … 1 across and down the view (the 3D view, the drawing, the "
                    "sheet; get_screenshot shows it), or at_mm = [x, y] on a drawing sheet's paper (mm from its top left) — a click "
                    "there (picks a face, a part, a dimension…), double = true a double-click, drag_to = [x, y] (same kind of point) a "
                    "drag. key = a key pressed after it, or alone on what has the focus: Delete, Enter, Escape, ctrl+z … -> what was "
                    "done, what was under the mouse, what is selected and the messages shown. Then get_assembly / gui_state / "
                    "get_screenshot tell what changed.",
     "inputSchema": _obj({"control": {}, "value": {}, "click": {"type": "boolean"}, "at": {"type": "array", "items": NUM},
                          "at_mm": {"type": "array", "items": NUM}, "drag_to": {"type": "array", "items": NUM},
                          "double": {"type": "boolean"}, "key": STR})},
    {"name": "remove_joint", "where": "browser", "description": "Remove a joint (id J…) of the assembly on screen; the part stays where it is.",
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
                    "use-a-drawing (a DXF / Gerber: find shapes, sizes, make a part of it). Read it before such a task when your skills are not available.",
     "inputSchema": _obj({"topic": {"type": "string", "enum": ["start-a-design", "model-a-part", "from-picture", "print-prep", "change-a-model", "assemble-parts",
                                                              "mechanical-design", "automation-design", "fits-and-tolerances", "print-functional", "print-graphics",
                                                              "use-a-drawing"]}}, ["topic"])},
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
- **3D models** are built like in SolidWorks: sketches (rectangles, circles, polylines with locked sizes) turned into a solid by extrude / revolve, then holes, fillets, chamfers, shells — for mechanical parts. Tools: new_model, get_model, find_refs, add_feature, edit_feature, delete_feature, turn_off_feature, set_material, prepare_print. mm; the bed is the XY plane.
- **Assemblies** place 3D model parts together: new_assembly, get_assembly, insert_part, snap_faces (joints: touch, gap, axis = concentric…), place_part, remove_from_assembly, check_collisions. get_assembly says for each joined part how it can still move (free) or that it is fully held.
- **Drawing sheets** (📄, of a 3D model part — its views and dimensions, made by a preset, edited by the user, following the part): sheet_open, get_sheet, sheet_edit; export {format: "pdf"} on a sheet writes it as drawn. Prefer a sheet over export pdf of the model when the user wants a drawing.
- **2D drawings** (a DXF / DWG, or a PCB's Gerber / ODB++ opened as a 📐 drawing — open_file opens them, also a folder of loose Gerber files): get_drawing, drawing_find (shapes by filters), drawing_delete, drawing_add (lines, circles), drawing_units, drawing_layers (show / hide, colour, a new layer), drawing_set_size, drawing_use (as the sketch of a 3D model, or a quick part).
- The GUI: gui_state lists what the user sees (buttons, sliders, their state; a sheet's dimensions / views / cells); gui_action clicks / slides one as the user would, clicks / drags at a point of the view (at, at_mm on a sheet) and presses keys (Delete, Enter, Escape, ctrl+z) — use them to tell the user where something is and to check the GUI behaves like the tools.
- Assemblies also: edit_joint / remove_joint, measure (between faces), move_free, lock_motion (fix one free motion where it is); set_travel (a free motion's limits: a cylinder's stroke) and check_travel (collisions along it); the view for screenshots: set_view (iso / top / front / right, a section, explode, size labels). The project: rename_part, delete_part (only when asked). Files: export stl / step / pdf / 3mf (in colours, for multi-material printing) / bom (CSV) / dxf.
- **The parts library** holds real, bought parts with their maker and part number (screws, nuts, washers, inserts, bearings, standoffs, panel parts, SMC pneumatics, SICK sensors, stepper motors, the user's own): library_search, library_add.
- Both: get_screenshot, check_print, export, undo. Opening a file or tracing a picture adds a new quick part tab.

**Before a new design** (a new part, device or assembly) load auto3d:start-a-design and, for what the user has not said yet, ask with ask_user (buttons in the chat, your recommendation first): what it is for — automation / a machine (made to be manufactured, standard, library parts), a functional 3D-printed part, or a graphic / decorative 3D model; whether it is 3D printed; and whether it must be easy for a person to edit (simple sketches, few sizes each) or may be built any way that reaches the goal. Then load the skills that brief asks for.

Before modelling, changing a 3D model, making a part from a picture, preparing a print or assembling parts, load the matching skill (auto3d:model-a-part, auto3d:change-a-model, auto3d:from-picture, auto3d:print-prep, auto3d:assemble-parts, auto3d:use-a-drawing) — or call get_guide(topic) if skills are not available. For any design of a device, a mechanism, a bracket for bought parts or a machine, load auto3d:mechanical-design first; for automation also auto3d:automation-design and auto3d:fits-and-tolerances; for a functional printed part auto3d:print-functional; for a graphic / decorative print auto3d:print-graphics.

**When you are not sure** which way the user wants (a choice with several sensible answers that changes what you build), do not guess and do not ask in a long text: call ask_user with 2–4 options and your recommended one first.

Work like a good mechanical designer: **use the parts library first.** Anything that is bought — screws, nuts, washers, inserts, bearings, standoffs, connectors, LEDs, buttons, cylinders, valves, fittings, sensors, motors — comes from library_search / library_add, with its real part number (it lands in the BOM); draw only the parts that are made (printed). If a bought part is not in the library, say so and draw a simple stand-in of its real outside sizes. Design the made parts around the bought ones (their holes, fits and clearances).

Rules: pick faces and edges with find_refs, never by guessing. Put fillets and chamfers last. **Model from simple shapes**: one idea per sketch (a rectangle, a circle, a slot), as few sizes in it as possible, the rest made by features (extrude, hole, pattern, mirror, fillet) — a part a person can read and change step by step; only when the user said it may be built any way, a complex sketch is fine. After changes check get_part / get_model (every step ok) and get_screenshot before saying it is done. Use printable defaults (walls ≥ 1.2 mm, hole clearance +0.2 mm) unless told otherwise. Ask the user only when a decision is really theirs (key sizes, what to make) — then with ask_user.

Photos: the user can attach photos to a message. You see them, and the message lists where each one was saved ("[Attached photo: <path>]") — to make a part from one, pass that path to trace_picture. Describing or measuring from a photo needs no tool.

Never open a file or the sample on your own: work on the part that is open. If nothing is open, ask the user what to open or offer a new 3D model — do not open the sample unless they ask for it.

Smooth, round shapes (vases, knobs, handles, toys, bottles): draw the outline as a sketch `profile` with `{smooth: [...]}` parts and revolve it (or extrude it) — one clean smooth surface instead of many small faces. Colours: set_look (the whole part) and paint_faces (single faces) — the model keeps them, also in assemblies.

If something does not behave as expected — a tool fails although your call was right, a result is wrong (sizes, positions, a joint, a colour that does not show) — call report_problem {kind: "bug"} at once with what happened, what you expected and the steps, then tell the user and carry on (or work around it). When no tool fits your work and you have to find a workaround (several calls for one thing, guessing, asking the user to click for you), write report_problem {kind: "tool request"}: the tool you would want — its name, inputs and what it returns — and the workaround you used. When the user cannot find something in the app, or a control did what they did not expect, write report_problem {kind: "ui"}: what they tried and how it should work. Do not report your own mistakes that you could fix yourself.

Answer in the user's language, briefly. You can only use the tools listed — no files or shell."""
