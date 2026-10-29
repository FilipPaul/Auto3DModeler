"""Quick parts in assemblies, in headless Edge: a PDF drawing (a quick part) and a 3D model pin -> ＋ New assembly ->
＋ Insert part lists both (▤ quick, ◆ model) -> insert the drawing's part (as its solid) and the pin -> the pin snapped
onto the part's top face -> parts list -> STEP export of both.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_quick.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time
from pathlib import Path

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


try:
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "pdfInput").send_keys(str(Path("initial draft.pdf").resolve()))
    wait("return !!window.__app.state.solution", 90)
    quick_bbox = js("const s = window.__app.state.solution; return s.bbox || s.size || null")
    call("new_model", name="Pin")
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 6}}])
    call("add_feature", type="extrude", sketch="F1", d=15)
    time.sleep(1)
    print("parts:", json.loads(call("list_parts")))

    call("new_assembly", name="Drawing + pin")
    time.sleep(0.5)
    d.find_element(By.CSS_SELECTOR, "#asmViewport [data-a=insert]").click()
    time.sleep(0.3)
    print("insert menu:", [b.text for b in d.find_elements(By.CSS_SELECTOR, "#asmViewport .as-insert [data-part]")])
    d.find_element(By.CSS_SELECTOR, "#asmViewport [data-a=insert]").click()
    r = json.loads(call("insert_part", part="initial draft"))
    print("quick part inserted:", r["parts"])
    r = json.loads(call("insert_part", part="Pin"))
    print("pin inserted:", [(p["id"], p["name"], p["bbox"]) for p in r["parts"]])

    # the quick part's largest upward flat face: snap the pin's bottom onto it
    top = js(f"""const b = {A}.bodies[{A}.inst('I1').part].body;
      return b.faces.filter(f => f.type === 'plane' && f.normal[2] > 0.99).sort((p, q) => q.area - p.area)[0].name""")
    r = json.loads(call("snap_faces", move={"part": "I2", "face": "F2:start"}, onto={"part": "I1", "face": top}))
    print("snapped onto", top, "->", [(p["id"], p["bbox"]) for p in r["parts"]])
    print("parts list:", r["parts_list"])
    js(f"{A}.view.setView('iso')")
    time.sleep(0.5)
    d.save_screenshot(f"{OUT}/asq_assembly.png")

    js("""window.__saved = []; window.showSaveFilePicker = async (o) => ({ name: o.suggestedName,
      createWritable: async () => ({ write: async (b) => { window.__saved.push([o.suggestedName, b.size, await b.text()]); }, close: async () => {} }) });""")
    js(f"{A}.sel = null; {A}.render()")
    time.sleep(0.3)
    d.find_element(By.CSS_SELECTOR, "#asmBom [data-x=step]").click()
    wait("return window.__saved.length === 1", 90)
    name, size, text = js("return window.__saved[0]")
    print("STEP export:", name, size, "bytes | solids:", text.count("MANIFOLD_SOLID_BREP"))
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
