"""The tools an AI agent (Claude Code, through the MCP server in mcp_server.py) gets to work on the app.

Most tools act on the part open in the browser (that is where the app state lives): the server relays
them to the page, which applies them like the user would — visible at once and undoable. A few run on
the server: reading files, tracing a picture, writing export files.
"""
from __future__ import annotations

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
     "description": "A picture of the 3D view, to check your work. view: iso (default), front (top-down onto the "
                    "front face), back, side.",
     "inputSchema": _obj({"view": {"type": "string", "enum": ["iso", "front", "back", "side"]}})},
    {"name": "open_file", "where": "server",
     "description": "Open a file from disk as the new part: PDF drawing, DXF / DWG drawing, or STL / OBJ / STEP 3D "
                    "file. For a photo or picture use trace_picture instead. It opens as a new part (its own tab); "
                    "the parts already open stay in the project.",
     "inputSchema": _obj({"path": STR, "page": {"type": "integer", "description": "PDF page (0-based)"}}, ["path"])},
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
     "description": "Export the part as STL or STEP (mm) to a file — or, for a 3D model part, pdf: a 2D drawing (front / "
                    "top / right views, sizes, holes, title block). path: file or folder (default: the user's Downloads "
                    "folder). Returns the written path.",
     "inputSchema": _obj({"format": {"type": "string", "enum": ["stl", "step", "pdf"]}, "path": STR}, ["format"])},
    {"name": "undo", "where": "browser", "description": "Undo the last change made through these tools.",
     "inputSchema": _obj({})},

    # ---- parts of the project (tabs) and 3D model parts (sketches -> extrude / revolve / fillet / hole …)
    {"name": "list_parts", "where": "browser",
     "description": "The parts of the project (tabs): id, name, kind (quick part = drawing / picture / import; 3D model) and "
                    "which one is on screen.",
     "inputSchema": _obj({})},
    {"name": "open_part", "where": "browser", "description": "Put a part (id or name from list_parts) on screen.",
     "inputSchema": _obj({"id": STR}, ["id"])},
    {"name": "new_model", "where": "browser",
     "description": "Start a new, empty 3D model part (its own tab) — for mechanical parts built from sketches and "
                    "features. Then add_feature.",
     "inputSchema": _obj({"name": STR})},
    {"name": "get_model", "where": "browser",
     "description": "The 3D model on screen: its steps in order (id, type, values, ok / issues / warnings), the body's "
                    "size and volume. Call it first and after changes.",
     "inputSchema": _obj({})},
    {"name": "find_refs", "where": "browser",
     "description": "Find faces or edges of the 3D model by description (never guess names). Faces: normal [x, y, z] "
                    "(e.g. [0, 0, 1] = facing up), extreme max / min along that normal (the top-most face), name "
                    "(part of a face name), near [x, y, z]. Edges: of_face (a face name), circular true / false, near. "
                    "Edges come with a ready ref {a, b, fp} for fillet / chamfer.",
     "inputSchema": _obj({"kind": {"type": "string", "enum": ["face", "edge"]}, "normal": POINT,
                          "extreme": {"type": "string", "enum": ["max", "min"]}, "name": STR, "near": POINT,
                          "of_face": STR, "circular": {"type": "boolean"}, "limit": {"type": "integer"}})},
    {"name": "add_feature", "where": "browser",
     "description": "Add a step to the 3D model (it rebuilds; the result says ok / issues). type:\n"
                    "- sketch: plane \"XY\" (top, the bed) / \"XZ\" (front) / \"YZ\" (right) / {datum: \"XY\", offset: 30} (moved along its "
                    "normal) / {face: <name>} (origin = the face's "
                    "centre); shapes: [{rect: {x, y, w, h, r}} (lower-left corner; r = rounded corners) | {circle: {x, y, d}} | {slot: {x1, y1, x2, y2, w}} (round ends "
                    "centred at x1,y1 and x2,y2) | {polyline: {points: [[u, v], …]}} "
                    "(closed)] — a shape inside another is a hole; sizes are locked.\n"
                    "- extrude: sketch (id), d, op add / cut, through (cut through all), symmetric, flip; or up_to: a flat face's "
                    "name (as far as that face — it follows the face), offset (mm past it, negative = short of it).\n"
                    "- revolve: sketch, axis \"y\" (the sketch's vertical axis) / \"x\" / a line id, angle (360), op.\n"
                    "- hole: face (name), points [[u, v]] from the face's centre, d, through (default) or depth; "
                    "from: [{x: {edge: <ref from find_refs>, d}, y: {edge, d}}] per hole = its distance from a straight edge "
                    "of that face (d signed along the face's x / y; the hole keeps it when the part changes).\n"
                    "- fillet: edges [refs from find_refs], r. chamfer: edges, d.\n"
                    "- shell: faces [names of the faces left open], t (wall).\n"
                    "- pattern: repeat steps — of [ids of extrude / revolve / hole / pattern steps], count (with the original). "
                    "kind \"linear\": dir \"x\" / \"y\" / \"z\" / [dx, dy, dz], spacing (mm). kind \"circular\": evenly around "
                    "axis \"x\" / \"y\" / \"z\" (through the origin) / {o, d} / a round face's name (its axis), angle (360).\n"
                    "- loft: sketches [ids, in order] — a solid from one closed outline to the next (put them on offset planes, "
                    "e.g. {datum: \"XY\", offset: 30}), op.\n"
                    "- sweep: profile (a sketch id: a closed outline across the path's start), path (a sketch id: an open "
                    "line — shapes [{path: {points: [[u, v], …]}}]), op.\n"
                    "- decal: text on a flat face — face (name), text, h (letter height mm), op add (raised) / cut (engraved), "
                    "depth (mm), at [u, v] from the face's centre, angle (degrees it is turned on the face).",
     "inputSchema": _obj({"type": {"type": "string", "enum": ["sketch", "extrude", "revolve", "hole", "fillet", "chamfer", "shell", "pattern", "loft", "sweep", "decal"]},
                          "name": STR, "plane": {}, "shapes": {"type": "array"}, "lock": {"type": "boolean"},
                          "sketch": STR, "d": NUM, "op": {"type": "string", "enum": ["add", "cut"]}, "through": {"type": "boolean"},
                          "symmetric": {"type": "boolean"}, "flip": {"type": "boolean"}, "axis": {}, "angle": NUM,
                          "face": STR, "points": {"type": "array"}, "depth": NUM, "edges": {"type": "array"}, "r": NUM,
                          "faces": {"type": "array"}, "t": NUM, "of": {}, "kind": {"type": "string", "enum": ["linear", "circular"]},
                          "count": NUM, "spacing": NUM, "dir": {}, "up_to": STR, "offset": NUM,
                          "sketches": {"type": "array"}, "profile": STR, "path": STR,
                          "text": STR, "h": NUM, "at": {"type": "array"}}, ["type"])},
    {"name": "edit_feature", "where": "browser",
     "description": "Change a step of the 3D model: id and fields (as in add_feature, e.g. {d: 15}, {r: 3}, {points: …}, a "
                    "sketch's {shapes: […]}). Later steps follow their faces.",
     "inputSchema": _obj({"id": STR, "fields": _obj({}, extra=True)}, ["id", "fields"])},
    {"name": "delete_feature", "where": "browser",
     "description": "Delete a step of the 3D model (the steps that need it are deleted too).",
     "inputSchema": _obj({"id": STR}, ["id"])},
    {"name": "turn_off_feature", "where": "browser", "description": "Turn a step off (off true) or on again (off false); it is kept.",
     "inputSchema": _obj({"id": STR, "off": {"type": "boolean"}}, ["id"])},
    {"name": "set_material", "where": "browser",
     "description": "The 3D model's material (for its mass in get_model): PLA, PETG, ABS, ASA, TPU or PA.",
     "inputSchema": _obj({"material": {"type": "string", "enum": ["PLA", "PETG", "ABS", "ASA", "TPU", "PA"]}}, ["material"])},
    {"name": "prepare_print", "where": "browser",
     "description": "A printing copy of the 3D model on screen, opened as a quick part on the 3D print tab — then check_print "
                    "and export work on it.",
     "inputSchema": _obj({})},
    {"name": "new_assembly", "where": "browser",
     "description": "Start a new, empty assembly (its own tab) to place 3D model parts of the project together. Then insert_part.",
     "inputSchema": _obj({"name": STR})},
    {"name": "get_assembly", "where": "browser",
     "description": "The assembly on screen: its placed parts (id I1…, part, position, bounding box in mm) and the parts list (qty, material, mass).",
     "inputSchema": _obj({})},
    {"name": "insert_part", "where": "browser",
     "description": "Add a part (id or name from list_parts: a 3D model, or a quick part — a drawing, picture or import — as its solid) to the assembly on screen; it is put beside the others. Returns the parts.",
     "inputSchema": _obj({"part": STR}, ["part"])},
    {"name": "snap_faces", "where": "browser",
     "description": "Join a placed part to another one with a joint that holds: move = {part: <placed id I…>, face: <face name>}, "
                    "onto = {part, face}. type: \"touch\" (flat faces meet, centred — the default), \"gap\" (flat faces facing, gap mm "
                    "apart), \"flush\" (flat faces in one plane, gap = offset), \"axis\" (concentric: two round faces on one axis, a pin in a hole), "
                    "\"parallel\", \"perp\" (perpendicular), \"angle\" (value = degrees between the faces' directions), \"tangent\" "
                    "(a round face touching a flat one). A part's joints apply in order: e.g. axis (pin shaft → hole) then touch (head → plate top) seats a "
                    "pin. Face names come from find_refs in the part's own model (\"F2:end\" = the top of the first extrude).",
     "inputSchema": _obj({"move": _obj({"part": STR, "face": STR}, ["part", "face"]), "onto": _obj({"part": STR, "face": STR}, ["part", "face"]),
                          "type": {"type": "string", "enum": ["touch", "gap", "flush", "axis", "parallel", "perp", "angle", "tangent"]}, "gap": NUM,
                          "value": NUM}, ["move", "onto"])},
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
    {"name": "remove_from_assembly", "where": "browser", "description": "Take a placed part (id I…) out of the assembly.",
     "inputSchema": _obj({"part": STR}, ["part"])},
    {"name": "get_guide", "where": "local",
     "description": "A step-by-step guide: model-a-part, from-picture, print-prep, change-a-model, assemble-parts. Read it before such a task "
                    "when your skills are not available.",
     "inputSchema": _obj({"topic": {"type": "string", "enum": ["model-a-part", "from-picture", "print-prep", "change-a-model", "assemble-parts"]}}, ["topic"])},
]

TOOL_NAMES = {t["name"] for t in TOOLS}
BROWSER_TOOLS = {t["name"] for t in TOOLS if t["where"] == "browser"}
LOCAL_TOOLS = {t["name"] for t in TOOLS if t["where"] == "local"}  # answered by the MCP server itself (guides)


def mcp_tool_list():
    """The tools as MCP describes them (without our routing field)."""
    return [{k: v for k, v in t.items() if k != "where"} for t in TOOLS]


SYSTEM_PROMPT = """You are the design assistant inside Auto3DModeler, a local app for quick 3D-printable parts. The user sees the app next to this chat; every change you make through the tools shows up there at once and can be undone (tool `undo`, or the app's Undo button).

The project holds parts, as tabs in the app's top bar (list_parts, open_part); the tools work on the part on screen.
- **Quick parts** come from a PDF drawing (parametric: its dimensions drive it), an outline traced from a picture or read from a DXF (made into a cookie cutter, a solid shape or a custom stack of objects), or an imported STL / OBJ / STEP file. Tools: get_part, set_dimensions, set_make, set_part_options, add_object, add_shape, add_design_layer, add_dimension, update_item, remove_item. Coordinates: x right, y up, z up from the bed; the part's unit (PDF drawings may be cm).
- **3D models** are built like in SolidWorks: sketches (rectangles, circles, polylines with locked sizes) turned into a solid by extrude / revolve, then holes, fillets, chamfers, shells — for mechanical parts. Tools: new_model, get_model, find_refs, add_feature, edit_feature, delete_feature, turn_off_feature, set_material, prepare_print. mm; the bed is the XY plane.
- **Assemblies** place 3D model parts together: new_assembly, get_assembly, insert_part, snap_faces (a flat face onto another, centred), place_part, remove_from_assembly.
- Both: get_screenshot, check_print, export, undo. Opening a file or tracing a picture adds a new quick part tab.

Before modelling, changing a 3D model, making a part from a picture, preparing a print or assembling parts, load the matching skill (auto3d:model-a-part, auto3d:change-a-model, auto3d:from-picture, auto3d:print-prep, auto3d:assemble-parts) — or call get_guide(topic) if skills are not available.

Rules: pick faces and edges with find_refs, never by guessing. Put fillets and chamfers last. After changes check get_part / get_model (every step ok) and get_screenshot before saying it is done. Use printable defaults (walls ≥ 1.2 mm, hole clearance +0.2 mm) unless told otherwise. Ask the user only when a decision is really theirs (key sizes, what to make).

Photos: the user can attach photos to a message. You see them, and the message lists where each one was saved ("[Attached photo: <path>]") — to make a part from one, pass that path to trace_picture. Describing or measuring from a photo needs no tool.

Never open a file or the sample on your own: work on the part that is open. If nothing is open, ask the user what to open or offer a new 3D model — do not open the sample unless they ask for it.

Answer in the user's language, briefly. You can only use the tools listed — no files or shell."""
