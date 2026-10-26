"""🔩 Fasteners in an assembly, in headless Edge: a 40 x 40 x 4 lid with four Ø3.4 holes and a 40 x 40 x 10 base with
four Ø4.0 holes 6 deep at the same places -> the lid joined onto the base (touch) -> 🔩 Fasteners suggests "M3×8 screw
+ M3 insert" at each of the four holes (hovering marks the holes) -> Add all: four screws and four inserts, standard
parts of the project, held by joints: each screw on its hole's axis with its head on the lid, each insert flush with the
base's top -> the lid gets thicker in its tab -> the screws follow; a pin where the holes are the same Ø; the AI's
suggest_fasteners / add_fasteners.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_fasteners.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
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
CORNERS = [[-14, -14], [14, -14], [14, 14], [-14, 14]]


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


def parts():
    return json.loads(call("get_assembly"))["parts"]


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Lid")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=4)
    call("add_feature", type="hole", face="F2:end", points=CORNERS, d=3.4)
    call("new_model", name="Base")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="hole", face="F2:end", points=CORNERS, d=4.0, through=False, depth=6)
    time.sleep(1)
    call("new_assembly", name="Box")
    call("insert_part", part="Base")
    call("insert_part", part="Lid")
    call("snap_faces", move={"part": "I2", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    js(f"{A}.view.setView('iso')")
    time.sleep(0.5)

    d.find_element(By.CSS_SELECTOR, "#asmViewport [data-a=fasteners]").click()
    time.sleep(0.6)
    rows = d.find_elements(By.CSS_SELECTOR, "#asmRight [data-cand]")
    print("suggestions:", [r.text.replace("\n", " ") for r in rows])
    ActionChains(d).move_to_element(rows[0]).perform()
    time.sleep(0.3)
    print("hovering marks its holes:", js(f"return {A}.view.markGroup.children.length"))
    d.save_screenshot(f"{OUT}/fast1.png")
    d.find_element(By.CSS_SELECTOR, "#asmRight [data-a=addAll]").click()
    wait(f"return {A}.doc.instances.length === 10 && Object.values({A}.bodies).every(b => b.body)")
    time.sleep(0.8)
    ps = parts()
    screws = [p for p in ps if "screw" in p["name"]]
    inserts = [p for p in ps if "insert" in p["name"]]
    print("added:", len(screws), "screws,", len(inserts), "inserts | names", sorted({p["name"] for p in screws + inserts}))
    for s in screws[:2]:
        b = s["bbox"]
        print("  screw at", round((b[0] + b[3]) / 2, 2), round((b[1] + b[4]) / 2, 2), "| z", b[2], "to", b[5], "(head on the lid: top 14 + 3 = 17, tip 14 - 8 = 6)")
    for i in inserts[:1]:
        b = i["bbox"]
        print("  insert z", b[2], "to", b[5], "(flush with the base's top: 5 to 10)")
    print("project parts:", json.loads(call("list_parts")))
    print("joints:", len(json.loads(call("get_assembly"))["joints"]))
    print("panel after:", d.find_element(By.CSS_SELECTOR, "#asmRight .mp-count").text, "| suggestions now", call("suggest_fasteners"))
    js(f"{A}.view.setView('iso')")
    time.sleep(0.5)
    d.save_screenshot(f"{OUT}/fast2.png")

    # the lid gets thicker: the screws follow it
    next(t for t in d.find_elements(By.CSS_SELECTOR, "#partTabs .part-tab") if t.text.startswith("Lid")).click()
    wait("return document.body.classList.contains('ws-model')")
    time.sleep(0.6)
    call("edit_feature", id="F2", fields={"d": 6})
    time.sleep(1)
    next(t for t in d.find_elements(By.CSS_SELECTOR, "#partTabs .part-tab") if t.text.startswith("Box")).click()
    wait(f"return document.body.classList.contains('ws-assembly') && Object.values({A}.bodies).every(b => b.body)")
    time.sleep(0.8)
    print("lid 6 thick -> screw head top z", [p["bbox"][5] for p in parts() if "screw" in p["name"]][:2], "(expected 19)")

    # a pin where the holes are the same Ø, through the AI
    call("new_model", name="Block A")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 20, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=6)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=4)
    call("new_model", name="Block B")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 20, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=6)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=4)
    call("new_assembly", name="Pinned")
    call("insert_part", part="Block A")
    call("insert_part", part="Block B")
    call("snap_faces", move={"part": "I2", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})
    print("AI suggest:", call("suggest_fasteners"))
    r = call("add_fasteners")
    print("AI add:", r[:60], "| pin:", [(p["name"], p["bbox"]) for p in parts() if "pin" in p["name"]])
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
