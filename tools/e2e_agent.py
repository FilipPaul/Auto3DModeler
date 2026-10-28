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
    tool("list_parts")
    tool("prepare_print")
    tool("check_print")
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    mcp.stdin.close()
    mcp.wait(5)
    d.quit()
