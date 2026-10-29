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
    print(f"    get_model: {step.get('hole_type')} {step.get('standard')} Ø{step.get('d')} ⌴ Ø{step.get('head_d')} ↧ {step.get('head_depth')}")
    tool("edit_feature", id=r["id"], fields={"standard": "M6"})
    step = next(s for s in json.loads(tool("get_model")[0])["steps"] if s["id"] == r["id"])
    print(f"    edited to M6: Ø{step.get('d')} ⌴ Ø{step.get('head_d')} ↧ {step.get('head_depth')} | match: {[step.get('d'), step.get('head_d'), step.get('head_depth')] == [6.6, 11, 6.4]}")
    t, _ = tool("add_feature", type="hole", face="F2:end", points=[[0, 0]], standard="M7", hole_type="tapped")
    print(f"    an unknown size refused: {'standard' in t}")
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
    tool("open_part", id="Flange")
    tool("prepare_print")
    tool("check_print")
    # teaching: a ring and a tip at a control (gone on clear), and the reports written so far
    tool("gui_highlight", control="Save project", text="Save your work here.", step="1/1")
    print("    highlighted:", d.execute_script("return document.querySelector('.teach-tip')?.textContent.replace(/\\s+/g, ' ').trim()"))
    tool("gui_highlight", clear=True)
    print("    cleared:", d.execute_script("return !document.querySelector('.teach-ring')"))
    tool("list_reports", search="sketch")
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    mcp.stdin.close()
    mcp.wait(5)
    d.quit()
