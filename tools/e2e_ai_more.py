"""More of the app for the AI, in headless Edge (tool calls through the server's /api/agent/call, as the MCP server
sends them): a DXF opened as a 2D drawing -> get_drawing, drawing_find (the Ø8 circles on HOLES), drawing_set_size
(Ø10), drawing_layers (only HOLES), export dxf, drawing_use as a sketch -> a 3D model -> set_view (section), a 3MF in its
colours (yellow body, orange top) -> an assembly: edit_joint (gap 5, flip), measure the gap, remove_joint, export bom
-> rename_part, delete_part (a used part refused) -> the Export menu's 3MF.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_ai_more.py http://127.0.0.1:5199 <out dir>
"""
import io
import json
import os
import sys
import time
import urllib.request
import zipfile

import ezdxf
from selenium import webdriver
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
doc = ezdxf.new("R2010")
doc.header["$INSUNITS"] = 4
for name in ("HOLES", "EDGE"):
    doc.layers.add(name)
msp = doc.modelspace()
for x in (10, 30, 50):
    msp.add_circle((x, 10), 4, dxfattribs={"layer": "HOLES"})
msp.add_circle((70, 10), 3, dxfattribs={"layer": "HOLES"})
for a, b in (((0, 0), (80, 0)), ((80, 0), (80, 20)), ((80, 20), (0, 20)), ((0, 20), (0, 0))):
    msp.add_line(a, b, dxfattribs={"layer": "EDGE"})
DXF = os.path.abspath(os.path.join(OUT, "plate_holes.dxf"))
doc.saveas(DXF)

opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"
A = "window.__app.assembly"


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def ai(tool, **args):
    req = urllib.request.Request(f"{URL}/api/agent/call", data=json.dumps({"tool": tool, "args": args}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        res = json.loads(r.read())
    return ("ERROR " if res.get("isError") else "") + "".join(c.get("text", "") for c in res.get("content", []))


def data(tool, **args):
    t = ai(tool, **args)
    try:
        return json.loads(t)
    except ValueError:
        return t


try:
    d.get(URL)
    wait("return !!window.__app")
    time.sleep(1.5)
    d.find_element(By.ID, "cadInput").send_keys(DXF)
    wait("return window.__app.state.workspace === 'drawing'")
    time.sleep(0.5)
    g = data("get_drawing")
    print("get_drawing:", g["shapes"], g["size_mm"], [(l["name"], l["shapes"]) for l in g["layers"]])
    f = data("drawing_find", filters=[{"field": "shape", "value": "circle"}, {"field": "layer", "value": "HOLES"}, {"field": "dia", "value": 8}])
    print("drawing_find Ø8 on HOLES:", f["found"], "selected", f["selected"], [x["d"] for x in f["first"]])
    print("drawing_set_size:", ai("drawing_set_size", kind="dia", value=10), "->", js("return window.__app.drawing2d.d.entities.filter(e => e.t === 'circle').map(e => 2 * e.r)"))
    print("drawing_layers only HOLES:", ai("drawing_layers", only=["HOLES"]))
    print("export dxf:", ai("export", format="dxf", path=OUT))
    ai("drawing_layers", show=["EDGE"])
    print("drawing_use all as sketch:", ai("drawing_use", **{"as": "sketch", "what": "all"}))
    wait("return window.__app.state.workspace === 'model'")
    ai("add_feature", type="extrude", sketch="F1", d=5)
    wait(f"return !!{M}.result?.body && !{M}.inflight")
    print("extruded with holes:", js(f"return {M}.result.body.faces.filter(f => f.type === 'cylinder').length"), "round faces")
    print("set_view section:", ai("set_view", view="iso", section={"axis": "y", "offset": 10}), "| cut:", js(f"return {M}.section"))
    ai("set_view", section=None)
    ai("set_look", color="#FFD400")
    top = js(f"return {M}.result.body.faces.find(f => f.type === 'plane' && f.normal[2] > 0.9).name")
    ai("paint_faces", faces=[top], color="#FF8800")
    r = ai("export", format="3mf", path=OUT)
    print("export 3mf:", r)
    path = r.split(" to ")[-1].strip()
    root = zipfile.ZipFile(path).read("3D/3dmodel.model").decode()
    print("  colours in the 3MF:", root.count("<base "), "|", [c for c in ("#FFD400FF", "#FF8800FF") if c in root], "| objects:", root.count("<object "))

    # an assembly: joints changed, measured, removed; the BOM
    ai("new_model", name="Lid")
    ai("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 30, "h": 20}}])
    ai("add_feature", type="extrude", sketch="F1", d=4)
    ai("new_assembly", name="Joints")
    plate = js("return window.__app.project.parts.find(p => p.kind === 'model' && p.name !== 'Lid').name")
    ai("insert_part", part=plate)
    ai("insert_part", part="Lid")
    ai("snap_faces", type="touch", move={"part": "I2", "face": "F2:start"}, onto={"part": "I1", "face": "E2:end" if False else js("return window.__app.assembly.bodies[window.__app.assembly.inst('I1').part].body.faces.find(f => f.type === 'plane' && f.normal[2] > 0.9).name")})
    j = data("get_assembly")["joints"][0]
    print("joint:", j["id"], j["type"], "gap", j.get("gap"))
    print("edit_joint gap 5:", ai("edit_joint", id=j["id"], gap=5))
    top1 = js("return window.__app.assembly.bodies[window.__app.assembly.inst('I1').part].body.faces.find(f => f.type === 'plane' && f.normal[2] > 0.9).name")
    print("measure the gap:", ai("measure", a={"part": "I1", "face": top1}, b={"part": "I2", "face": "F2:start"}))
    print("edit_joint locked:", ai("edit_joint", id=j["id"], locked=True)[:60], "| remove locked:", ai("remove_joint", id=j["id"])[:70])
    ai("edit_joint", id=j["id"], locked=False)
    print("remove_joint:", ai("remove_joint", id=j["id"]), "| joints left", len(data("get_assembly")["joints"]))
    print("set_view explode:", ai("set_view", explode=0.6)[:60], "| explode", js(f"return {A}.explode"))
    r = ai("export", format="bom", path=OUT)
    print("export bom:", r)
    print("  ", open(r.split(" to ")[-1].strip(), encoding="utf-8-sig").read().splitlines()[:3])
    print("export 3mf of the assembly:", ai("export", format="3mf", path=os.path.join(OUT, "assembly.3mf")))

    # the project's parts
    print("rename_part:", ai("rename_part", id="Lid", name="Cover"))
    print("delete a used part:", ai("delete_part", id="Cover")[:90])
    ai("new_model", name="Scrap")
    print("delete_part:", ai("delete_part", id="Scrap"), "| parts:", js("return window.__app.project.parts.map(p => p.name)"))
    # the Export menu's 3MF (the user's)
    ai("open_part", id="Joints")
    wait("return window.__app.state.workspace === 'assembly'")
    time.sleep(1)
    js("""window.__saved = []; window.showSaveFilePicker = async (o) => ({ name: o.suggestedName,
      createWritable: async () => ({ write: async (b) => { window.__saved.push([o.suggestedName, (await b.arrayBuffer()).byteLength]); }, close: async () => {} }) });""")
    js("document.querySelector('#exportMenu [data-fmt=\"3mf\"]').click()")
    wait("return window.__saved.length === 1", 30)
    print("Export menu 3MF:", js("return window.__saved[0]"))
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
