"""Duplicating parts, in headless Edge: a 3D model -> ⧉ Duplicate as a new part -> a new tab "Plate (copy)" on screen
-> the copy made thicker, the original stays -> an assembly with two of the original -> ⧉ Make it its own part on
I2 -> I2 uses a new copy; that copy made thicker changes I2 only -> the AI's duplicate_part.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_duplicate.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"
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


def parts():
    return [(p["id"], p["name"]) for p in json.loads(call("list_parts"))]


def height(name):
    call("open_part", id=name)
    wait(f"return !!{M}.result?.body && !{M}.inflight")
    return js(f"return {M}.result.body.bbox[5]")


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 30}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    wait(f"return !!{M}.result?.body")
    js(f"{M}.selected = null; {M}.renderProps()")
    time.sleep(0.3)
    d.find_element(By.CSS_SELECTOR, "#modelRight [data-a=duplicatePart]").click()
    wait("return window.__app.project.current?.name === 'Plate (copy)'")
    wait(f"return !!{M}.result?.body && !{M}.inflight")
    print("after ⧉:", parts(), "| on screen", js("return window.__app.project.current.name"), "| steps", len(js(f"return {M}.part.features")))
    call("edit_feature", id="F2", fields={"d": 12})
    print("copy 12 thick:", height("Plate (copy)"), "| original:", height("Plate"))

    call("new_assembly", name="Two plates")
    call("insert_part", part="Plate")
    call("insert_part", part="Plate")
    wait(f"return {A}.doc.instances.length === 2 && Object.values({A}.bodies).every(b => b.body)")
    js(f"{A}.sel = 'I2'; {A}.render(); {A}.draw()")
    time.sleep(0.3)
    js("document.querySelector('#asmViewport .view-suggest [data-sg-all]')?.click()")  # (⧉ Make it its own part: a suggestion, under ⋯ Show all)
    time.sleep(0.3)
    next(b for b in d.find_elements(By.CSS_SELECTOR, "#asmViewport .view-suggest .vs-list button") if "Make it its own part" in b.text).click()
    js("sessionStorage.removeItem('a3d.suggestAll')")
    wait(f"return {A}.inst('I2').part !== {A}.inst('I1').part")
    own = js(f"return [{A}.inst('I1').part, {A}.inst('I2').part]")
    print("I2 its own part:", own, "| names", [n for i, n in parts() if i in own], "| toast", js("return [...document.querySelectorAll('.toast')].map(t => t.textContent).slice(-1)[0]"))
    name = next(n for i, n in parts() if i == own[1])
    call("open_part", id=name)
    wait(f"return !!{M}.result?.body")
    call("edit_feature", id="F2", fields={"d": 9})
    call("open_part", id="Two plates")
    wait(f"return window.__app.state.workspace === 'assembly' && {A}.bodies[{A}.inst('I2').part]?.body?.bbox[5] > 8.9", 60)
    s = json.loads(call("get_assembly"))
    print("I1 / I2 heights:", [p["bbox"][5] - p["bbox"][2] for p in s["parts"]], "(5 and 9)")

    r = call("duplicate_part", id="Plate", name="Plate B")
    print("AI:", r, "| parts", [n for _, n in parts()])
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
