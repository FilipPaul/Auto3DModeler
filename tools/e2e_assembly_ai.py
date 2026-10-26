"""The AI's assembly tools, in headless Edge (the same handlers the MCP server relays to): two 3D model parts ->
new_assembly -> insert_part x2 -> get_assembly -> snap_faces (the pin's top onto the plate's top) -> place_part
(move + turn) -> get_screenshot -> undo -> wrong face / wrong tool errors -> remove_from_assembly.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_ai.py http://127.0.0.1:5199 <out dir>
"""
import base64
import json
import sys
import time

from selenium import webdriver

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
A = "window.__app.assembly"
H = "window.__app.agentHandlers"


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def matrix(inst):
    return js(f"return {A}.inst(arguments[0]).matrix.map(v => +v.toFixed(4))", inst)


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("new_model", name="Pin")
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 8}}])
    call("add_feature", type="extrude", sketch="F1", d=20)
    time.sleep(1)

    print("new_assembly:", call("new_assembly", name="Pinned plate"))
    print("workspace:", js("return document.body.classList.contains('ws-assembly')"))
    for part in ("Plate", "Pin"):
        r = json.loads(call("insert_part", part=part))
        print(f"insert_part {part}:", [(p["id"], p["name"], p["position"]) for p in r["parts"]])
    print("insert unknown:", call("insert_part", part="Nope"))
    r = json.loads(call("get_assembly"))
    print("get_assembly:", r)

    r = json.loads(call("snap_faces", move={"part": "I2", "face": "F2:end"}, onto={"part": "I1", "face": "F2:end"}))
    m = matrix("I2")
    print("snapped:", m[12:15], "| upside down:", m[10] == -1, "| pin bbox:", r["parts"][1]["bbox"])
    print("bad face:", call("snap_faces", move={"part": "I2", "face": "F9:end"}, onto={"part": "I1", "face": "F2:end"}))
    side = js(f"return {A}.bodies.P2.body.faces.find(f => f.type !== 'plane').name")
    print("round face:", call("snap_faces", move={"part": "I2", "face": side}, onto={"part": "I1", "face": "F2:end"}))
    print("same part:", call("snap_faces", move={"part": "I1", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"}))

    r = json.loads(call("place_part", part="I2", x=10, turn="x"))
    print("place_part x=10 + turn x:", matrix("I2")[12], matrix("I2")[4:7])
    shot = js(f"return {H}.get_screenshot({{view: 'iso'}}).then(r => r.image)")
    open(f"{OUT}/asai_shot.png", "wb").write(base64.b64decode(shot))
    print("screenshot bytes:", len(shot))
    print("undo:", call("undo"), matrix("I2")[4:7])
    print("model tool in an assembly:", call("add_feature", type="extrude", sketch="F1", d=2)[:120])
    print("quick tool in an assembly:", call("get_part")[:120])
    print("remove:", [p["id"] for p in json.loads(call("remove_from_assembly", part="I2"))["parts"]])
    print("list_parts:", call("list_parts"))
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
