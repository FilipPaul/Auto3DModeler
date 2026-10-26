"""Snaps that hold (links) in an assembly, in headless Edge: a plate and a pin -> the pin snapped onto the plate's top ->
the panel says it follows the plate -> the plate made 8 mm thick in its own tab -> back in the assembly the pin sits
on the new top -> the plate moved -> the pin goes along -> the pin moved by hand -> unlinked (a notice) -> undo ->
linked again; the link is saved with the project.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_links.py http://127.0.0.1:5199 <out dir>
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


def pin_bbox():
    return next(p["bbox"] for p in json.loads(call("get_assembly"))["parts"] if p["id"] == "I2")


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
    call("new_assembly", name="Linked")
    call("insert_part", part="Plate")
    call("insert_part", part="Pin")
    r = json.loads(call("snap_faces", move={"part": "I2", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"}))
    print("snapped: pin z", r["parts"][1]["bbox"][2], "| links", r["joints"])
    js(f"{A}.sel = 'I2'; {A}.render()")
    time.sleep(0.3)
    print("panel:", d.find_element(By.CSS_SELECTOR, "#asmRight .as-jrow").text.replace("\n", " "))

    # the plate gets thicker in its own tab; back in the assembly the pin follows the new top
    tabs = d.find_elements(By.CSS_SELECTOR, "#partTabs .part-tab")
    next(t for t in tabs if t.text.startswith("Plate")).click()
    wait("return document.body.classList.contains('ws-model')")
    time.sleep(0.8)
    call("edit_feature", id="F2", fields={"d": 8})
    time.sleep(1)
    next(t for t in d.find_elements(By.CSS_SELECTOR, "#partTabs .part-tab") if t.text.startswith("Linked")).click()
    wait("return document.body.classList.contains('ws-assembly')")
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    time.sleep(0.8)
    print("plate 8 thick -> pin bottom z:", pin_bbox()[2], "(expected 8)")

    # the plate moves: the pin goes along
    call("place_part", part="I1", x=100)
    b = pin_bbox()
    print("plate moved to x 100 -> pin centre x:", round((b[0] + b[3]) / 2, 3), "(expected 130)")

    # the pin moved by hand: unlinked, with a notice; undo links it again
    js(f"window.confirm = () => true; {A}.sel = 'I2'; {A}.setPos('y', 50)")  # yes, break its joints
    time.sleep(0.4)
    toast = js("return [...document.querySelectorAll('.toast')].map(t => t.textContent).slice(-1)[0]")
    print("moved by hand:", toast, "| links", json.loads(call("get_assembly"))["joints"])
    call("undo")
    time.sleep(0.8)
    print("undo -> joints", len(json.loads(call("get_assembly"))["joints"]))
    d.save_screenshot(f"{OUT}/links1.png")

    # saved with the project
    js("""window.__saved = []; window.showSaveFilePicker = async (o) => ({ name: o.suggestedName,
      createWritable: async () => ({ write: async (b) => { window.__saved.push(await b.text()); }, close: async () => {} }) });""")
    d.find_element(By.ID, "saveBtn").click()
    wait("return window.__saved.length === 1")
    proj = json.loads(js("return window.__saved[0]"))
    asm = next(p for p in proj["parts"] if p["kind"] == "assembly")
    print("saved links:", asm["assembly"].get("mates"))
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
