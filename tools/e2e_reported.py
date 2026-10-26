"""The problems the AI reported (RealSWReports, 2026-10-26), fixed — in headless Edge, tool calls through /api/agent/call:
(1) edit_feature on a sketch with only a new plane keeps its shapes; (2) edit_feature on a mirror with only a new `of`
keeps its plane; (3) a part just put into an assembly (so chosen) shows its own colour and painted faces, a blue glow
only; and the joint panel's gap slider: a flat joint's gap set by sliding (the part follows), typed in its box.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_reported.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time
import urllib.request

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


try:
    d.get(URL)
    wait("return !!window.__app")
    time.sleep(1.5)
    # (1) a sketch moved to another plane keeps its shapes
    ai("new_model", name="Duck")
    ai("add_feature", type="sketch", plane={"datum": "XZ", "offset": -4}, shapes=[{"profile": {"points": [[0, 0], [15, 0], {"smooth": [[20, 12], [8, 22]]}, [0, 25]]}}])
    ai("add_feature", type="revolve", sketch="F1", axis="y", angle=360)
    wait(f"return !!{M}.result?.body && !{M}.inflight")
    n0 = js(f"return {M}.part.features[0].entities.length")
    r = ai("edit_feature", id="F1", fields={"plane": "XZ"})
    wait(f"return !{M}.inflight")
    print("(1) new plane only:", js(f"return {M}.part.features[0].plane"), "| shapes kept:", js(f"return {M}.part.features[0].entities.length") == n0,
          "| builds:", js(f"return {M}.result?.features?.every(f => f.ok)"))
    # (2) a mirror told only another `of` keeps its plane
    ai("new_model", name="Block")
    ai("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 5, "w": 20, "h": 10}}])
    ai("add_feature", type="extrude", sketch="F1", d=5)
    ai("add_feature", type="mirror", of="F2", plane="XZ")
    wait(f"return !!{M}.result?.body && !{M}.inflight")
    ai("edit_feature", id="F3", fields={"of": "body"})
    wait(f"return !{M}.inflight")
    print("(2) mirror of the body:", js(f"return [{M}.part.features[2].of, {M}.part.features[2].plane]"), "| size",
          js(f"const b = {M}.result.body.bbox; return [b[3]-b[0], b[4]-b[1]].map(v => +v.toFixed(2))"), "(20 × 30: across XZ, not 40 long)")
    # (3) a painted part put into an assembly shows its own colours while chosen
    ai("open_part", id="Block")
    ai("set_look", color="#FFD400")
    ai("paint_faces", faces=["F2:end"], color="#FF8800")
    ai("new_model", name="Pond")
    ai("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": -30, "y": -30, "w": 60, "h": 60}}])
    ai("add_feature", type="extrude", sketch="F1", d=4)
    ai("set_look", color="#4FA8E8")
    ai("new_assembly", name="Pond and duck")
    ai("insert_part", part="Pond")
    ai("insert_part", part="Block")
    wait(f"return {A}.doc.instances.length === 2 && Object.values({A}.bodies).every(b => b.body)")
    time.sleep(0.5)
    print("(3) chosen:", js(f"return {A}.sel"), "| its look:", js(f"""const m = {A}.view.meshes.find(x => x.userData.inst === {A}.sel);
      return ['#' + m.material.color.getHexString(), !!m.geometry.attributes.color, '#' + m.material.emissive.getHexString()]"""), "(its colours + a blue glow)")
    # the gap slider
    print(ai("snap_faces", type="touch", move={"part": "I2", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})[:40])
    js(f"{A}.choose('I2')")
    time.sleep(0.4)
    z0 = js(f"return {A}.inst('I2').matrix[14]")
    sl = d.find_element(By.CSS_SELECTOR, "#asmRight [data-jgaps]")
    print("gap slider:", sl.get_attribute("min"), "…", sl.get_attribute("max"), "| at", sl.get_attribute("value"))
    js("arguments[0].value = 17; arguments[0].dispatchEvent(new Event('input')); arguments[0].dispatchEvent(new Event('change'))", sl)
    time.sleep(0.5)
    print("slid to 17:", js(f"return {A}.doc.mates[0].type + ' ' + {A}.doc.mates[0].gap"), "| the lid up by", round(js(f"return {A}.inst('I2').matrix[14]") - z0, 3))
    js("arguments[0].value = 0.4; arguments[0].dispatchEvent(new Event('input')); arguments[0].dispatchEvent(new Event('change'))", d.find_element(By.CSS_SELECTOR, "#asmRight [data-jgaps]"))
    time.sleep(0.4)
    print("slid near 0: catches at", js(f"return {A}.doc.mates[0].gap"))
    num = d.find_element(By.CSS_SELECTOR, "#asmRight [data-jgapn]")
    js("arguments[0].value = 2.5; arguments[0].dispatchEvent(new Event('change'))", num)
    time.sleep(0.4)
    print("typed 2.5:", js(f"return {A}.doc.mates[0].gap"), "| undo ->", (js(f"{A}.history.go(-1)") or True) and (time.sleep(0.4) or js(f"return {A}.doc.mates[0].gap")))
    d.save_screenshot(f"{OUT}/joint_gap.png")
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
