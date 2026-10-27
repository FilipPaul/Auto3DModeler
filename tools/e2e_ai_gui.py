"""The AI testing the GUI as the user, in headless Edge: an assembly (Base + Lid) -> gui_action at a point of the 3D
view where the lid is: the lid picked -> at an empty corner: nothing picked -> Delete on the lid: taken out -> ctrl+z:
back -> a drawing sheet of the Base: gui_state lists its dimensions, views, title cells -> gui_action on a dimension:
selected -> Delete: gone -> ctrl+z: back -> at_mm on the view, drag_to 20 mm right: the view moved -> a double-click on
the title's cell: its field has the focus -> no control / point / key: refused.

  PYTHONIOENCODING=utf-8 py tools/e2e_ai_gui.py http://127.0.0.1:5199 <out dir>
"""
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
S = "window.__app.sheet"
H = "window.__app.agentHandlers"


def wait(script, t=120):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(script)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def act(**args):
    r = call("gui_action", **args)
    return r if r.startswith("ERROR") else json.loads(r)


try:
    d.get(URL)
    wait("return !!window.__app")
    for name, w, h in (("Base", 80, 10), ("Lid", 30, 4)):
        call("new_model", name=name)
        call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": w, "h": 50}}])
        call("add_feature", type="extrude", sketch="F1", d=h)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=6)
    call("new_assembly", name="Box")
    call("insert_part", part="Base")
    call("insert_part", part="Lid")
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    call("place_part", part="I2", z=30)
    call("set_view", view="top")
    time.sleep(0.8)
    # a point of the view where the lid is (as the user would aim at it)
    at = js(f"""const v = document.querySelector('#asmViewport').getBoundingClientRect();
      for (let y = 0.1; y < 0.9; y += 0.02) for (let x = 0.1; x < 0.9; x += 0.02)
        if ({A}.view.pickInst(v.left + x * v.width, v.top + y * v.height)?.inst === 'I2') return [x + 0.04, y + 0.04];
      return null;""")
    print("the lid on screen at", [round(v, 2) for v in at])
    r = act(at=at)
    print("click on the lid:", r["done"], "| selected", r["selected"])
    r = act(at=[0.02, 0.98])
    print("click on an empty corner:", r["done"], "| selected", r["selected"])
    act(at=at)
    r = act(key="Delete")
    print("Delete:", r["done"], "| parts", js(f"return {A}.doc.instances.length"))
    r = act(key="ctrl+z")
    print("ctrl+z:", r["done"], "| parts", js(f"return {A}.doc.instances.length"))

    print("sheet_open:", json.loads(call("sheet_open", part="Base"))["preset"])
    wait(f"return !!{S}.svgEl")
    view = json.loads(call("gui_state", where="view"))["controls"]
    kinds = {}
    for c in view:
        kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
    print("gui_state view:", kinds, "| e.g.", [c["label"] for c in view][:4])
    dim = next(c for c in view if c["kind"] == "dim")
    r = act(control=dim["n"])
    print("a dimension clicked:", r["done"], "| selected", r["selected"])
    n0 = js(f"return {S}.allDims().length")
    r = act(key="Delete")
    print("Delete:", r["done"], "| dims", n0, "->", js(f"return {S}.allDims().length"))
    act(key="ctrl+z")
    print("ctrl+z: dims", js(f"return {S}.allDims().length"))
    top = js(f"return {S}.centre('Top')")
    r = act(at_mm=top, drag_to=[top[0] + 20, top[1]])
    print("drag the Top view 20 mm right:", r["done"], "| centre", [round(v, 1) for v in top], "->", [round(v, 1) for v in js(f"return {S}.centre('Top')")])
    cell = next(c for c in json.loads(call("gui_state", where="view"))["controls"] if c["label"] == "title title")
    r = act(control=cell["n"], double=True)
    print("double-click the title:", r["done"], "| focus on", js("return document.activeElement?.dataset?.text || document.activeElement?.tagName"))
    print("nothing given:", act()[:70])
    print("a wrong point:", act(at=[0.5])[:60])
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
