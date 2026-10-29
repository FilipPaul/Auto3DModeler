"""The AI tools end to end: the real MCP server process (as Claude Code starts it) -> the app -> the page in
headless Edge, without the model: each step is a JSON-RPC tool call like Claude Code makes.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_agent.py http://127.0.0.1:5199 <abs path to pernicek.png> <out dir>
"""
import base64
import json
import math
import subprocess
import sys
import time
from pathlib import Path

from selenium import webdriver

URL, IMG, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
ROOT = Path(__file__).resolve().parent.parent
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
mcp = subprocess.Popen([sys.executable, str(ROOT / "auto3d" / "mcp_server.py"), "--url", URL],
                       stdin=subprocess.PIPE, stdout=subprocess.PIPE)
ids = iter(range(1, 10_000))


def rpc(method, params=None):
    mid = next(ids)
    mcp.stdin.write((json.dumps({"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}}) + "\n").encode())
    mcp.stdin.flush()
    return json.loads(mcp.stdout.readline().decode())["result"]


def tool(tool_name, **args):
    name = tool_name
    r = rpc("tools/call", {"name": name, "arguments": args})
    text = r["content"][0]["text"]
    img = next((c for c in r["content"] if c["type"] == "image"), None)
    if img:
        (Path(OUT) / f"a_{name}_{next(ids)}.png").write_bytes(base64.b64decode(img["data"]))
    flag = "ERROR " if r.get("isError") else ""
    print(f"· {name} {json.dumps(args)[:90]}\n    {flag}{text[:300]}{' [+image]' if img else ''}")
    return text, r


try:
    d.get(URL)
    time.sleep(2.5)  # the page starts long-polling
    print("initialize:", rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "e2e", "version": "1"}})["serverInfo"])
    print("tools:", len(rpc("tools/list")["tools"]))

    tool("get_part")
    tool("open_sample")
    t, _ = tool("get_part")
    part = json.loads(t)
    print("    dims:", [(p["id"], p["name"], p["value"]) for p in part["dimensions"]][:4], "bbox:", part["bbox"])
    v0 = part["volume"]
    tool("add_object", kind="cylinder", op="subtract", x=40, y=5.5, w=2, h=2, z0=0, z1=1, name="Hole")
    tool("set_dimensions", values={"Overall length": 90})
    tool("set_dimensions", values={"nonsense": 3})
    tool("get_screenshot", view="iso")
    t, _ = tool("undo")
    t, _ = tool("undo")
    print("    volume back to the start:", json.loads(tool("get_part")[0])["volume"] == v0)

    t, _ = tool("trace_picture", path=IMG, count=4)
    tool("use_outline", candidate=1, width=100, make="cutter")
    tool("set_make", options={"height": 12, "wall": 1.2})
    tool("add_shape", kind="hole", w=6, h=6)
    t, _ = tool("add_object", kind="text", text="PERNÍK", h=6, x=50, y=-2.5, z0=2, z1=3, op="union")
    tool("add_design_layer", kind="shape", op="engrave", depth=0.5, mask={"kind": "rect", "x": 20, "y": -2.5, "w": 6, "h": 2})
    part = json.loads(tool("get_part")[0])
    print("    preset:", part["make"]["preset"], part["make"]["options"].get("height"), "| added:", [o["name"] for o in part["added_objects"]],
          "| shapes:", [s["name"] for s in part["shapes"]], "| layers:", [L["name"] for L in part["design_layers"]], "| issues:", part["issues"])
    tool("check_print")
    tool("export", format="stl", path=str(Path(OUT) / "agent_cutter.stl"))
    tool("get_screenshot", view="iso")
    tool("remove_item", id="nope")
    print("exported file:", (Path(OUT) / "agent_cutter.stl").stat().st_size, "bytes")
    d.save_screenshot(f"{OUT}/a_page.png")

    # ---- a 3D model through the model tools: the plate from the model-a-part guide's worked example
    print("guide:", tool("get_guide", topic="model-a-part")[0][:60].replace("\n", " "))
    tool("new_model", name="Plate")
    tool("set_dimensions", values={"width": 3})  # a quick-part tool on a model: a clear error
    tool("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    tool("add_feature", type="extrude", sketch="F1", d=5)
    top = json.loads(tool("find_refs", kind="face", normal=[0, 0, 1], extreme="max")[0])[0]["name"]
    tool("add_feature", type="hole", face=top, d=4, points=[[-24, -14], [24, -14], [24, 14], [-24, 14]])
    corners = []
    for c in ([0, 0, 2.5], [60, 0, 2.5], [60, 40, 2.5], [0, 40, 2.5]):
        corners.append(json.loads(tool("find_refs", kind="edge", near=c, circular=False, limit=1)[0])[0]["ref"])
    t, _ = tool("add_feature", type="fillet", edges=corners, r=3)
    import math
    v = json.loads(t)["body"]["volume_mm3"]
    exp = 60 * 40 * 5 - 4 * math.pi * 4 * 5 - 4 * (9 - math.pi * 9 / 4) * 5
    print(f"    model volume {v} expected {exp:.3f} | match: {abs(v - exp) < 0.01}")
    holes = json.loads(tool("find_refs", kind="edge", of_face=top, circular=True)[0])
    print("    round edges on the top:", len(holes), "| radius", holes[0]["circle"]["radius"] if holes else None)
    # ⛓ one edge of the rounded top outline: the chamfer takes its whole chain (8 edges), ½ d² swept round it
    e = json.loads(tool("find_refs", kind="edge", near=[30, 0, 5], limit=1)[0])[0]
    t, _ = tool("add_feature", type="chamfer", edges=[e["ref"]], d=0.5)
    st = next(s for s in json.loads(tool("get_model")[0])["steps"] if s["type"] == "chamfer")
    want = 0.125 * (2 * 54 + 2 * 34 + 2 * math.pi * (3 - 0.5 / 3))
    print(f"    chain: find_refs says {e.get('chain')} | the chamfer has {st['edges']} edges | -{-json.loads(t).get('volume_change_mm3', 0):.3f} "
          f"expected {want:.3f} | match: {e.get('chain') == 8 and st['edges'] == 8 and abs(json.loads(t).get('volume_change_mm3', 0) + want) < 0.01}")
    tool("delete_feature", id=st["id"])
    tool("edit_feature", id="F2", fields={"d": 8})
    m = json.loads(tool("get_model")[0])
    print("    after the plate got 8 thick:", m["body"]["size_mm"], "| all ok:", all(s["ok"] for s in m["steps"]))
    tool("turn_off_feature", id="F4", off=True)
    tool("delete_feature", id="F3")
    tool("undo")
    tool("get_screenshot", view="iso")
    tool("export", format="step", path=str(Path(OUT) / "agent_plate.step"))
    print("    STEP file:", (Path(OUT) / "agent_plate.step").stat().st_size, "bytes")
    # ---- ⬆ up to next and the other side: two plates 10 apart (a wall joins them), a boss from the lower one up to
    # the upper one; a block 10 up + d2 4 down
    tool("new_model", name="Shelf")
    tool("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 40}}])
    tool("add_feature", type="extrude", sketch="F1", d=10)
    tool("add_feature", type="sketch", plane={"datum": "XY", "offset": 10}, shapes=[{"rect": {"x": 0, "y": 0, "w": 5, "h": 40}}])
    tool("add_feature", type="extrude", sketch="F3", d=10)
    tool("add_feature", type="sketch", plane={"datum": "XY", "offset": 20}, shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 40}}])
    tool("add_feature", type="extrude", sketch="F5", d=10)
    tool("add_feature", type="sketch", plane={"datum": "XY", "offset": 10}, shapes=[{"circle": {"x": 20, "y": 20, "d": 10}}])
    t, _ = tool("add_feature", type="extrude", sketch="F7", upto_next=True)
    r = json.loads(t)
    print(f"    up to next: went {r.get('went')} | +{r.get('volume_change_mm3')} expected {math.pi * 25 * 10:.3f}")
    t, _ = tool("edit_feature", id="F2", fields={"d2": 4})
    r = json.loads(t)
    print(f"    d2 4: went {r.get('went')} | +{r.get('volume_change_mm3')} expected 6400")
    # ---- an extrude's draft: a 40 × 20 block 10 tall, its walls 5° in (a prismatoid); draft 0: the block again
    tool("new_model", name="Mould")
    tool("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    t, _ = tool("add_feature", type="extrude", sketch="F1", d=10, draft=5)
    k = 10 * math.tan(math.radians(5))
    exp = 10 / 6 * (800 + 4 * (40 - k) * (20 - k) + (40 - 2 * k) * (20 - 2 * k))
    v = json.loads(t)["body"]["volume_mm3"]
    print(f"    draft 5°: volume {v} expected {exp:.3f} | match: {abs(v - exp) < 0.01} | step: {json.loads(tool('get_model')[0])['steps'][-1].get('draft')}")
    t, _ = tool("edit_feature", id="F2", fields={"draft": 0})
    print(f"    draft 0: volume {json.loads(t)['body']['volume_mm3']} expected 8000")
    # ---- 𝑥 project parameters: L = 40; a block 30 × 20 with d = "L / 4" and its width "L / 2" (a sketch size);
    # L = 60 -> 30 × 20 × 15 (rebuilt, listed); a circle refused, L kept; get_parameters says where it is used
    tool("set_parameter", name="L", value=40)
    tool("new_model", name="Param block")
    tool("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 30, "h": 20}}])
    t, _ = tool("add_feature", type="extrude", sketch="F1", d="L / 4")
    print(f"    d = L / 4: volume {json.loads(t)['body']['volume_mm3']} expected 6000")
    w = next(x for x in json.loads(tool("get_sketch", id="F1")[0])["dims"] if x["kind"] == "len" and abs(x["value"] - 30) < 1e-6)
    tool("sketch_dim", id="F1", dim=w["id"], value="L / 2")
    t, _ = tool("set_parameter", name="L", value=60)
    r = json.loads(t)
    print(f"    L = 60: rebuilt {[(x['part'], round(x.get('volume') or 0, 3)) for x in r['rebuilt']]} expected Param block 30 × 20 × 15 = 9000")
    print("    a circle:", tool("set_parameter", name="L", value="L + 1")[0][:110])
    print("    get_parameters:", tool("get_parameters")[0][:200])
    print("    edit_feature d = \"Q\":", tool("edit_feature", id="F2", fields={"d": "Q"})[0][:110])
    tool("set_parameter", name="L", delete=True)
    # ---- ⊿ a rib across a bore: a 40 cube, a bore Ø20 along X, a line across it at z 25 — the small segment, flipped
    # the large one (4 thick)
    tool("new_model", name="Bore rib")
    tool("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 40}}])
    tool("add_feature", type="extrude", sketch="F1", d=40)
    tool("add_feature", type="sketch", plane="YZ", shapes=[{"circle": {"x": 20, "y": 20, "d": 20}}])
    tool("add_feature", type="extrude", sketch="F3", op="cut", d=100, symmetric=True)
    tool("add_feature", type="sketch", plane={"datum": "YZ", "offset": 20}, shapes=[{"path": {"points": [[5, 25], [35, 25]]}}])
    seg = 100 * math.acos(0.5) - 5 * math.sqrt(75)
    t, _ = tool("add_feature", type="rib", sketch="F5", t=4)
    print(f"    rib: +{json.loads(t).get('volume_change_mm3')} expected {4 * seg:.3f}")
    t, _ = tool("edit_feature", id="F6", fields={"flip": True})
    v = json.loads(t)["body"]["volume_mm3"]
    exp = 64000 - math.pi * 100 * 40 + 4 * (math.pi * 100 - seg)
    print(f"    rib flipped: volume {v} expected {exp:.3f} | match: {abs(v - exp) < 0.01}")
    # ---- ⬆ a face extruded: a 40 × 20 × 10 block with a Ø6 hole, its top pulled up 10 (the hole goes on up), then
    # its top cut 4 back in
    tool("new_model", name="Face up")
    tool("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    tool("add_feature", type="extrude", sketch="F1", d=10)
    tool("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=6)
    r = json.loads(tool("add_feature", type="extrude", face="F2:end", d=10)[0])
    want = 8000 - 9 * math.pi * 10
    steps = json.loads(tool("get_model")[0])["steps"]
    print(f"    face extruded: ok {r.get('ok')} | +{r.get('volume_change_mm3')} expected {want:.3f} | match: "
          f"{abs(r.get('volume_change_mm3', 0) - want) < 0.01 and steps[-2].get('outline_of') == ['F2:end'] and steps[-1]['sketch'] == steps[-2]['id']}")
    r = json.loads(tool("add_feature", type="extrude", face=f"{r['id']}:end", d=4, op="cut")[0])
    print(f"    face cut in: {r.get('volume_change_mm3')} expected {-(800 - 9 * math.pi) * 4:.3f} | match: {abs(r.get('volume_change_mm3', 0) + (800 - 9 * math.pi) * 4) < 0.01}")
    t, _ = tool("add_feature", type="extrude", face="F9:end", d=4)
    print(f"    an unknown face refused: {'No face' in t and not any(s.get('outline_of') == ['F9:end'] for s in json.loads(tool('get_model')[0])['steps'])}")
    # ---- distances from a round face's axis: a block with a cross hole, a sketch circle and a hole measured from it;
    # the cross hole moves 10 -> both go along
    tool("new_model", name="Cross")
    tool("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    tool("add_feature", type="extrude", sketch="F1", d=20)
    tool("add_feature", type="sketch", plane="XZ", shapes=[{"circle": {"x": 30, "y": 10, "d": 8}}])
    tool("add_feature", type="extrude", sketch="F3", op="cut", d=100, symmetric=True)
    ax = json.loads(tool("find_refs", kind="axis")[0])[0]["axis"]
    tool("add_feature", type="sketch", plane={"face": "F2:end"}, shapes=[{"circle": {"x": 15, "y": 5, "d": 6}, "from": {"axis": ax}}])
    tool("add_feature", type="extrude", sketch="F5", op="cut", through=True)
    tool("add_feature", type="hole", face="F2:end", points=[[-15, -10]], d=4, **{"from": [{"x": {"axis": ax, "d": -15}}]})
    tool("edit_feature", id="F3", fields={"shapes": [{"circle": {"x": 40, "y": 10, "d": 8}}]})
    xs = sorted(round(x, 3) for x in d.execute_script(
        "return window.__app.modeler.result.body.faces.filter((f) => f.type === 'cylinder' && Math.abs(f.axis.d[2]) > 0.99).map((f) => f.centroid[0])"))
    print(f"    axis refs: {ax} | the cross hole moved 10 -> x {xs} expected [25, 55] | match: {xs == [25, 55]}")
    # ---- a teardrop hole into the front (sideways: prints without support); refused on the top (it goes down)
    front = json.loads(tool("find_refs", kind="face", normal=[0, -1, 0])[0])[0]["name"]
    r = json.loads(tool("add_feature", type="hole", face=front, points=[[-20, 0]], d=4, teardrop=True)[0])
    print(f"    teardrop: ok {r.get('ok')} | {r.get('volume_change_mm3')} expected {-(3 * math.pi + 4) * 40:.3f}")
    t, _ = tool("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=4, teardrop=True)
    print(f"    teardrop on the top refused: {'sideways' in t}")
    tool("undo")
    # ---- a standard hole in one go: M5 counterbore (ISO 273 Ø5.5 through the 20 block, ⌴ Ø10 ↧ 5.4); edited to M6
    r = json.loads(tool("add_feature", type="hole", face="F2:end", points=[[0, 12]], standard="M5", hole_type="counterbore")[0])
    want = -math.pi * (2.75 ** 2 * 20 + (25 - 2.75 ** 2) * 5.4)
    print(f"    M5 counterbore: ok {r.get('ok')} | {r.get('volume_change_mm3')} expected {want:.3f} | match: {abs(r.get('volume_change_mm3', 0) - want) < 0.05}")
    step = next(s for s in json.loads(tool("get_model")[0])["steps"] if s["id"] == r["id"])
    print(f"    get_model: {step.get('shape')} {step.get('standard')} Ø{step.get('d')} ⌴ Ø{step.get('head_d')} ↧ {step.get('head_depth')}")
    tool("edit_feature", id=r["id"], fields={"standard": "M6"})
    step = next(s for s in json.loads(tool("get_model")[0])["steps"] if s["id"] == r["id"])
    print(f"    edited to M6: Ø{step.get('d')} ⌴ Ø{step.get('head_d')} ↧ {step.get('head_depth')} | match: {[step.get('d'), step.get('head_d'), step.get('head_depth')] == [6.6, 11, 6.4]}")
    t, _ = tool("add_feature", type="hole", face="F2:end", points=[[0, 0]], standard="M7", hole_type="tapped")
    print(f"    an unknown size refused: {'standard' in t}")
    tool("delete_feature", id=r["id"])
    # ---- a D hole for a Ø5 D-shaft: Ø5, 4.5 across the flat, through the 20 block: the circle less its segment
    r = json.loads(tool("add_feature", type="hole", face="F2:end", points=[[0, 12]], hole_type="d_flat", d=5, flat=4.5)[0])
    want = -20 * (math.pi * 6.25 - (6.25 * math.acos(2 / 2.5) - 2 * math.sqrt(6.25 - 4)))
    step = next(s for s in json.loads(tool("get_model")[0])["steps"] if s["id"] == r["id"])
    print(f"    D hole: {step.get('what')} | {r.get('volume_change_mm3')} expected {want:.3f} | match: {abs(r.get('volume_change_mm3', 0) - want) < 0.05 and step.get('flat') == 4.5}")
    tool("delete_feature", id=r["id"])
    # ---- a second hole on a face with a hole in it lands where asked (the face's centre: the middle of its box, not of
    # its area); a slice cut off the side (the face's box moves), then an edit of only d: the hole stays; a field next to
    # fields instead of in it: refused
    tool("new_model", name="Two holes")
    tool("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    tool("add_feature", type="extrude", sketch="F1", d=10)
    tool("add_feature", type="hole", face="F2:end", points=[[-15, 0]], d=8)
    tool("add_feature", type="hole", face="F2:end", points=[[10, 12]], d=4)
    holes = lambda: sorted([round(c, 4) for c in f["axis"]["o"][:2]] for f in d.execute_script(  # noqa: E731
        "return window.__app.modeler.result.body.faces.filter((f) => f.type === 'cylinder')"))
    print(f"    second hole: axes {holes()} expected [[15, 20], [40, 32]] | match: {holes() == [[15, 20], [40, 32]]}")
    tool("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 50, "y": 0, "w": 10, "h": 40}}])
    tool("add_feature", type="extrude", sketch="F5", op="cut", through=True)
    t, r = tool("edit_feature", id="F4", head_d=6)
    print(f"    stray field refused: {bool(r.get('isError')) and 'fields' in t}")
    tool("edit_feature", id="F4", fields={"d": 5})
    print(f"    after the side cut and d 5: axes {holes()} expected [[15, 20], [40, 32]] | match: {holes() == [[15, 20], [40, 32]]}")
    # ---- ✂ split: a 60 × 40 × 20 box cut at z 15 — both pieces (two bodies), then only the lid; a plane past it: an issue
    tool("new_model", name="Box and lid")
    tool("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    tool("add_feature", type="extrude", sketch="F1", d=20)
    t, _ = tool("add_feature", type="split", plane={"datum": "XY", "offset": 15}, keep="both")
    r = json.loads(t)
    print(f"    split both: ok {r['ok']} | solids {r['body'].get('solids')} expected 2 | volume {r['body']['volume_mm3']} expected 48000")
    t, _ = tool("edit_feature", id=r["id"], fields={"keep": "above"})
    r = json.loads(t)
    print(f"    split above: volume {r['body']['volume_mm3']} expected 12000 | change {r.get('volume_change_mm3')}")
    t, _ = tool("edit_feature", id=r["id"], fields={"offset": 40})
    print("    split past the part:", json.loads(t)["issues"])
    # ---- a sketch shape's ⁂ pattern: a flange, six holes around the middle and three in a row
    tool("new_model", name="Flange")
    tool("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 60}},
                                                           {"circle": {"x": 20, "y": 0, "d": 5}, "pattern": {"count": 6, "around": [0, 0]}},
                                                           {"circle": {"x": -6, "y": -15, "d": 3}, "pattern": {"count": 3, "spacing": 6}}])
    t, _ = tool("add_feature", type="extrude", sketch="F1", d=5)
    v = json.loads(t)["body"]["volume_mm3"]
    exp = math.pi * (30 ** 2 - 6 * 2.5 ** 2 - 3 * 1.5 ** 2) * 5
    print(f"    pattern: volume {v} expected {exp:.3f} | match: {abs(v - exp) < 0.01} | relations:",
          d.execute_script("return window.__app.modeler.part.features[0].constraints.filter((k) => k.t === 'pat').map((k) => [k.kind, k.n])"))
    tool("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 4}, "pattern": {"count": 3, "around": [0, 0]}}])  # (on its centre: refused)
    # ---- simplify_sketch: a circle as a 72-sided polyline (as a DXF gives it) -> one circle; a wavy outline of 120
    # lines -> join: one spline, the same area
    tool("new_model", name="Simplified")
    ring = [[round(20 * math.cos(math.radians(i * 5)), 6), round(20 * math.sin(math.radians(i * 5)), 6)] for i in range(72)]
    tool("add_feature", type="sketch", plane="XY", lock=False, shapes=[{"polyline": {"points": ring}}])
    r = json.loads(tool("simplify_sketch", id="F1", tol=0.05)[0])  # (the 72 sides are 0.019 off the circle)
    t, _ = tool("add_feature", type="extrude", sketch="F1", d=5)
    v = json.loads(t)["body"]["volume_mm3"]
    print(f"    simplify: shapes {r['shapes']} | a circle: {r['shapes']['after'] == 1} | volume {v} ~ π 20² 5 = {math.pi * 2000:.1f}")
    wave = [[round((20 + 2 * math.cos(6 * t)) * math.cos(t), 6), round((20 + 2 * math.cos(6 * t)) * math.sin(t), 6)] for t in (i * 2 * math.pi / 120 for i in range(120))]
    tool("add_feature", type="sketch", plane={"datum": "XY", "offset": 20}, lock=False, shapes=[{"polyline": {"points": wave}}])
    r = json.loads(tool("simplify_sketch", id="F3", op="join")[0])
    print(f"    join: shapes {r['shapes']} | one curve: {r['shapes']['after'] == 1} | area {r['area_mm2']} kept: {abs(r['area_mm2']['after'] - r['area_mm2']['before']) < r['area_mm2']['before'] * 0.005}")
    tool("simplify_sketch", id="F2")  # (not a sketch: refused)
    # ---- the sketch tools: a rect and an overlapping slot -> get_sketch, sketch_union (one outline), sketch_auto_dims,
    # sketch_dim (R 20), sketch_trim (a circle cut by a line)
    tool("new_model", name="Sketch tools")
    tool("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": -20, "y": -30, "w": 65, "h": 65}}, {"slot": {"x1": 45, "y1": 9, "x2": 15, "y2": 35, "w": 46}}])
    v0 = json.loads(tool("add_feature", type="extrude", sketch="F1", d=10)[0])["body"]["volume_mm3"]
    s = json.loads(tool("get_sketch", id="F1")[0])
    print(f"    get_sketch: {len(s['shapes'])} shapes, {sum(x['locked'] for x in s['dims'])} locks, dof {s['dof']}, names {[x['name'] for x in s['dims']][:3]}")
    u = json.loads(tool("sketch_union", sketch="F1")[0])
    a = json.loads(tool("sketch_auto_dims", id="F1")[0])
    v1 = json.loads(tool("get_model")[0])["body"]["volume_mm3"]
    print(f"    union: {u['shapes']} | auto-dims: fully defined {a['fully_defined']} | volume {v0} (overlapping) -> {v1} | the exact union's"
          f" 59945.008: {abs(v1 - 59945.0078) < 0.01}")
    arc = next(x["id"] for x in json.loads(tool("get_sketch", id="F1")[0])["shapes"] if x["t"] == "arc")
    tool("sketch_dim", id="F1", dim=f"rad:{arc}", value=20)
    tool("sketch_dim", id="F1", dim="nothing", value=3)  # (no such dimension: refused)
    tool("list_parts")
    # the BOM of an assembly with a sub-assembly placed twice (get_bom: every level rolled up)
    tool("new_assembly", name="Pair")
    tool("insert_part", part="Flange")
    tool("insert_part", part="Two holes")
    tool("new_assembly", name="Rack")
    for p in ("Pair", "Pair", "Flange"):
        tool("insert_part", part=p)
    b = json.loads(tool("get_bom", mode="summary")[0])
    print("    get_bom totals:", {r["name"]: r["total"] for r in b["rows"]}, "| Flange 3 (1 × 2 + 1):",
          next(r["total"] for r in b["rows"] if r["name"] == "Flange") == 3)
    tool("get_bom", assembly="Pair", mode="structured")
    # ⚙ a mechanism: none in a rack of loose parts (refused, it says why); a loose part's motion cannot be named
    print("    drive_mechanism, no mechanism:", tool("drive_mechanism", to=90)[0][:100])
    print("    record_animation, no mechanism:", tool("record_animation", format="gif")[0][:100])
    print("    name_motion, not joined:", tool("name_motion", part="I1", motion=0, name="Turn")[0][:100])
    # ⚙ a coupling (snap_faces type gear / belt / rack): flat faces refused, it says why
    print("    snap_faces gear, flat faces:", tool("snap_faces", type="gear", move={"part": "I3", "face": "F2:end"}, onto={"part": "I1", "face": "I1/F2:start"})[0][:100])
    # ● a ball joint wants a ball: flat faces refused (it says why); 🔗 rigid needs no faces; 〰 a spring's row in get_assembly
    print("    snap_faces ball, flat faces:", tool("snap_faces", type="ball", move={"part": "I3", "face": "F2:end"}, onto={"part": "I2", "face": "I1/F2:start"})[0][:100])
    print("    snap_faces rigid, no faces:", tool("snap_faces", type="rigid", move={"part": "I3"}, onto={"part": "I2"})[0][:60])
    print("    lock_motion, fixed together:", tool("lock_motion", part="I3", motion=0)[0][:80])
    print("    set_travel follow, no limits:", tool("set_travel", part="I3", motion=0, follow={"at": "max"})[0][:100])
    # 🔌 a cable harness: 3 loose wires from the flange's top up to a point in space (its length), changed to 2, a
    # wrong id refused, listed by get_assembly
    t, _ = tool("add_harness", type="wires", count=3, points=[{"part": "I3", "face": "F2:end"}, {"xyz": [0, 0, 120]}])
    print("    add_harness:", t[:100])
    print("    edit_harness, no such id:", tool("edit_harness", id="H9", count=2)[0][:80])
    tool("edit_harness", id="H1", count=2, color="red")
    hs = json.loads(tool("get_assembly")[0]).get("harnesses", [])
    print(f"    harnesses: {[(h['id'], len(h['wires']), h['length_mm']) for h in hs]} | 2 wires: {len(hs) == 1 and len(hs[0]['wires']) == 2}")
    tool("open_part", id="Flange")
    tool("prepare_print")
    tool("check_print")
    # 🕘 versions: a named one, the extrude 10 -> 12, compared (the value and the volume named), a variant from it,
    # the first version restored (the answer names the one that undoes it)
    tool("new_model", name="Versioned")
    tool("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 10, "h": 10}}])
    tool("add_feature", type="extrude", d=10)
    first = json.loads(tool("save_version", label="before the change")[0])["saved"]["id"]
    tool("edit_feature", id="F2", fields={"d": 12})
    c = json.loads(tool("compare_versions", a=first)[0])
    print("    compare:", c["summary"], "| names 10 → 12 mm:", any("10 → 12 mm" in s for s in c["summary"]))
    tool("create_variant", name="taller")
    v = json.loads(tool("list_versions")[0])
    print("    variants:", [x["name"] for x in v["variants"]], "on:", v["variant"]["name"])
    r = json.loads(tool("restore_version", id=first)[0])
    print(f"    restored: volume {json.loads(tool('get_model')[0])['body']['volume_mm3']} expected 1000 | undo: {r['undo']}")
    print("    a bad id:", tool("restore_version", id="../x")[0][:80])
    # 🕘 back to main (switch_variant) and the taller one's part taken over (take_part): Versioned 10 × 10 × 30 there
    tool("edit_feature", id="F2", fields={"d": 30})
    tool("save_version", label="taller 30")
    r = json.loads(tool("switch_variant", variant="main")[0])
    tool("open_part", id="Versioned")
    v_main = json.loads(tool("get_model")[0])["body"]["volume_mm3"]
    print(f"    switch_variant: on {r['variant']['name']} | Versioned there {v_main} (not 3000: {abs(v_main - 3000) > 1})")
    print("    take_part, no such part:", tool("take_part", variant="taller", part="Nothing")[0][:90])
    tool("take_part", variant="taller", part="Versioned")
    tool("open_part", id="Versioned")
    v = json.loads(tool("get_model")[0])["body"]["volume_mm3"]
    print(f"    take_part: Versioned {v} expected 3000 | match: {abs(v - 3000) < 0.01} | variant still main: "
          f"{json.loads(tool('list_versions')[0])['variant']['name'] == 'main'}")
    print("    switch_variant, no such one:", tool("switch_variant", variant="nope")[0][:90])
    # ---- ▣ a solid from a file (add_feature type solid, path): a 20 cube written as STEP, joined into a new model
    # (8000), a Ø10 hole through it, then the same file as a see-through reference (the volume stays) and cut out
    tool("new_model", name="Cube file")
    tool("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 20, "h": 20}}])
    tool("add_feature", type="extrude", sketch="F1", d=20)
    cube = str(Path(OUT) / "agent_cube.step")
    tool("export", format="step", path=cube)
    tool("new_model", name="From a file")
    r = json.loads(tool("add_feature", type="solid", path=cube)[0])
    top = json.loads(tool("find_refs", kind="face", normal=[0, 0, 1], extreme="max")[0])[0]["name"]
    print(f"    solid add: ok {r.get('ok')} | volume {r['body']['volume_mm3']} expected 8000 | its top face {top} (F1:f…: {top.startswith('F1:f')})")
    r = json.loads(tool("add_feature", type="hole", face=top, points=[[0, 0]], d=10)[0])
    want = 8000 - math.pi * 25 * 20
    print(f"    hole in it: {r['body']['volume_mm3']} expected {want:.3f} | match: {abs(r['body']['volume_mm3'] - want) < 0.01}")
    r = json.loads(tool("add_feature", type="solid", path=cube)[0])
    print(f"    the file again (a part there: op ref by default): {r.get('volume_change_mm3', 0)} expected 0 | op "
          f"{next(s for s in json.loads(tool('get_model')[0])['steps'] if s['id'] == r['id']).get('op')}")
    tool("export", format="step", path=str(Path(OUT) / "agent_from_file.step"))
    print("    STEP of it:", (Path(OUT) / "agent_from_file.step").stat().st_size, "bytes")
    print("    no such file:", tool("add_feature", type="solid", path=str(Path(OUT) / "nope.step"))[0][:80])
    # ---- 🎬 demos (list_demos, open_demo) and a project file (open_file .a3d.json): the crank – rod – slider
    rows = json.loads(tool("list_demos")[0])
    print("    demos:", [x["file"] for x in rows])
    tool("open_demo", name="crank")
    parts = json.loads(tool("list_parts")[0])
    asm = next(p for p in parts if p["kind"] == "assembly")
    tool("open_part", id=asm["id"])
    a = json.loads(tool("get_assembly")[0])
    masses = [p.get("mass_g") for p in a["parts"]]
    print(f"    crank demo: {len(parts)} parts | mechanisms {[m['name'] for m in a.get('mechanisms', [])]} | each part's mass {masses} | "
          f"their sum is the assembly's {a.get('mass_g')}: {abs(sum(x or 0 for x in masses) - (a.get('mass_g') or -1)) < 0.05}")
    # 📈 the slider's stroke over a full turn of the crank: about twice the crank's throw (its hole to its pin)
    t, _ = tool("drive_mechanism", trace=True)
    import re
    pts = json.loads(re.search(r"\): (\[\[.*\]\])\.", t).group(1))
    throw = json.loads(tool("measure", a={"part": "I2", "face": "F3:hole:0"}, b={"part": "I2", "face": "F5:side:c1"})[0])["axes_apart"]
    stroke = max(y for _, y in pts) - min(y for _, y in pts)
    print(f"    trace: {len(pts)} points, stroke {stroke:.3f} | 2 × throw {2 * throw:.3f} | match: {2 * throw * 0.98 < stroke < 2 * throw * 1.1}")
    # ➕ the missing joint: the rod's pin joint to the slider taken away -> named, added back -> the mechanism again
    rod_pin = next(j["id"] for j in a["joints"] if j["part"] == "I3" and j["onto"] == "I4")
    tool("remove_joint", id=rod_pin)
    a = json.loads(tool("get_assembly")[0])
    print(f"    missing_joint: {a.get('missing_joint')} | mechanisms {len(a.get('mechanisms', []))}")
    r = tool("add_missing_joint")[0]
    a = json.loads(tool("get_assembly")[0])
    print(f"    added: {r[:120]} | missing now {a.get('missing_joint')} | closed loop: {any(lp['closed'] for lp in a.get('loops', []))}")
    print("    add_missing_joint, none missing:", tool("add_missing_joint")[0][:80])
    # 📌 fixed in place: the base freed and fixed again; the crank hangs on its joints (refused)
    tool("place_part", part="I1", fixed=False)
    print("    I1 freed:", not next(p for p in json.loads(tool("get_assembly")[0])["parts"] if p["id"] == "I1").get("fixed"))
    tool("place_part", part="I1", fixed=True)
    print("    I1 fixed again:", next(p for p in json.loads(tool("get_assembly")[0])["parts"] if p["id"] == "I1").get("fixed"))
    print("    I2 fixed (it hangs on its joints):", tool("place_part", part="I2", fixed=True)[0][:80])
    # a saved project file opens the same way (the demo's own file)
    t, _ = tool("open_file", path=str(ROOT / "demos" / "ctyrkloubovy-mechanismus.a3d.json"))
    print(f"    project file: {t[:120]}")
    # ... and the project on screen saved as one (export format project), then opened again: the same parts
    proj = Path(OUT) / "agent_project.a3d.json"
    tool("export", format="project", path=str(proj))
    saved = json.loads(proj.read_text(encoding="utf-8"))
    tool("open_file", path=str(proj))
    again = [p["name"] for p in json.loads(tool("list_parts")[0])]
    print(f"    export project: {saved['app']} v{saved['version']} {[p['name'] for p in saved['parts']]} | opened again the same: {again == [p['name'] for p in saved['parts']]}")
    # every browser tool has its handler in the page (tests/test_agent_wiring.py reads the sources; this asks the page)
    sys.path.insert(0, str(ROOT))
    from auto3d.agent_tools import BROWSER_TOOLS
    have = set(d.execute_script("return Object.keys(window.__app.agentHandlers)"))
    print(f"    the page's handlers: {len(have)} | browser tools without one: {sorted(BROWSER_TOOLS - have)}")
    # 📄 a dimension's own tolerance and a reference dimension on a part's sheet (sheet_edit dims), shown by get_sheet
    tool("new_model", name="Toleranced")
    tool("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    tool("add_feature", type="extrude", sketch="F1", d=8)
    tool("sheet_open")
    sh = json.loads(tool("get_sheet")[0])
    lin = [x["id"] for x in sh["dims"] if x["kind"] == "linear"][:2]
    t, _ = tool("sheet_edit", dims={lin[0]: {"tol": "+0.2/-0.1"}, lin[1]: {"tol": "±0.05", "ref": True}})
    got = {x["id"]: x for x in json.loads(t)["dims"]}
    print(f"    tol / ref: {got[lin[0]].get('tol')} {got[lin[0]]['text']} | {got[lin[1]].get('tol')} ref {got[lin[1]].get('ref')} {got[lin[1]]['text']}"
          f" | ok: {got[lin[0]].get('tol') == '+0.2/−0.1' and got[lin[1]].get('ref') is True and got[lin[1]]['text'].startswith('(')}")
    t, _ = tool("sheet_edit", dims={lin[1]: {"tol": None, "ref": False}})
    got = {x["id"]: x for x in json.loads(t)["dims"]}
    print(f"    cleared: {'tol' not in got[lin[1]] and 'ref' not in got[lin[1]]} | a bad tolerance refused:", tool("sheet_edit", dims={lin[0]: {"tol": "abc"}})[0][:90])
    # teaching: a ring and a tip at a control (gone on clear), and the reports written so far
    tool("gui_highlight", control="Save project", text="Save your work here.", step="1/1")
    print("    highlighted:", d.execute_script("return document.querySelector('.teach-tip')?.textContent.replace(/\\s+/g, ' ').trim()"))
    tool("gui_highlight", clear=True)
    print("    cleared:", d.execute_script("return !document.querySelector('.teach-ring')"))
    # ⏺ the recording of moves: the AI starts it (the pill says so), reads it, stops it
    tool("start_recording", reason="the user asked: watch me")
    print("    the pill:", d.execute_script("const p = document.querySelector('.rec-pill'); return p && !p.hidden && p.textContent"))
    t, _ = tool("get_recording", last=5, paths=False)
    print(f"    running: {json.loads(t)['running']} | first event: {json.loads(t)['events'][0]['kind']}")
    tool("stop_recording")
    print("    stopped, the pill gone:", d.execute_script("return document.querySelector('.rec-pill').hidden"))
    print("    an unknown shot:", tool("get_recording_screenshot", id="S9")[1].get("isError"))
    tool("list_reports", search="sketch")
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    mcp.stdin.close()
    mcp.wait(5)
    d.quit()
