"""Assemblies in assemblies, in headless Edge: "Pinned" (a plate with a pin in its hole, joined) -> a new assembly
"Stack" with a base block -> ＋ Insert part lists ◇ Pinned -> inserted as one unit (one body of both parts, its faces
named after its parts) -> its plate's bottom joined onto the base's top -> parts list (Pinned's mass = plate + pin)
-> STEP with all 3 solids -> back in "Pinned", "Stack" is not offered (no assembly in itself).

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_sub.py http://127.0.0.1:5199 <out dir>
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


def wait(script, t=90):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def menu():
    d.find_element(By.CSS_SELECTOR, "#asmViewport [data-a=insert]").click()
    time.sleep(0.2)
    items = [b.text for b in d.find_elements(By.CSS_SELECTOR, "#asmViewport .as-insert [data-part]")]
    d.find_element(By.CSS_SELECTOR, "#asmViewport [data-a=insert]").click()
    return items


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=8)
    call("new_model", name="Pin")
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 14}}])
    call("add_feature", type="extrude", sketch="F1", d=3)
    call("add_feature", type="sketch", plane={"face": "F2:end"}, shapes=[{"circle": {"x": 0, "y": 0, "d": 8}}])
    call("add_feature", type="extrude", sketch="F3", d=20)
    call("new_model", name="Base")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 80, "h": 60}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    time.sleep(1)
    call("new_assembly", name="Pinned")
    call("insert_part", part="Plate")
    call("insert_part", part="Pin")
    call("place_part", part="I2", z=30)
    call("snap_faces", type="axis", move={"part": "I2", "face": "F4:side:c1"}, onto={"part": "I1", "face": "F3:hole:0"})
    call("snap_faces", type="touch", move={"part": "I2", "face": "F2:end"}, onto={"part": "I1", "face": "F2:end"})
    time.sleep(0.5)

    call("new_assembly", name="Stack")
    print("insert menu:", menu())
    call("insert_part", part="Base")
    r = json.loads(call("insert_part", part="Pinned"))
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    sub = js(f"return {A}.bodies[{A}.inst('I2').part].body")
    print("Pinned as one body:", len(sub["faces"]), "faces | e.g.", sorted({f["name"] for f in sub["faces"]})[:3], "| bbox", [round(v, 2) for v in sub["bbox"]])
    print("list:", [e.text.replace("\n", " ") for e in d.find_elements(By.CSS_SELECTOR, "#asmLeft .mt-item")])
    r = json.loads(call("snap_faces", type="touch", move={"part": "I2", "face": "I1/F2:start"}, onto={"part": "I1", "face": "F2:end"}))
    print("Pinned on the base:", [(p["id"], p["bbox"]) for p in r["parts"]])
    print("parts list:", r["parts_list"])
    js(f"{A}.sel = 'I2'; {A}.render()")
    time.sleep(0.3)
    print("joint row:", [e.text.replace("\n", " ") for e in d.find_elements(By.CSS_SELECTOR, "#asmRight .as-jrow")][:1])
    js(f"{A}.view.setView('iso')")
    time.sleep(0.4)
    d.save_screenshot(f"{OUT}/sub1.png")

    js("""window.__saved = []; window.showSaveFilePicker = async (o) => ({ name: o.suggestedName,
      createWritable: async () => ({ write: async (b) => { window.__saved.push([o.suggestedName, await b.text()]); }, close: async () => {} }) });""")
    js(f"{A}.sel = null; {A}.render()")
    time.sleep(0.3)
    d.find_element(By.CSS_SELECTOR, "#asmBom [data-x=step]").click()
    wait("return window.__saved.length === 1", 90)
    name, text = js("return window.__saved[0]")
    print("STEP:", name, "| solids:", text.count("MANIFOLD_SOLID_BREP"))

    # no assembly in itself
    next(t for t in d.find_elements(By.CSS_SELECTOR, "#partTabs .part-tab") if t.text.startswith("Pinned")).click()
    wait("return document.body.classList.contains('ws-assembly')")
    time.sleep(0.8)
    print("in Pinned, the menu:", menu(), "(no Stack, no Pinned)")
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
