"""⌴ / ⌵ hole heads, in headless Edge: a 40 × 20 × 10 block, ◎ Hole Ø6 on its top -> Head ⌴ Counterbore: Ø10.8 × 6 by
default, the volume less the counterbore; Head Ø 10, depth 4: exact -> ⌵ Countersink: Ø12 (2 × d) at 90° -> OK; the AI's
add_feature hole with head "cbore" and edit_feature head null (taken off) -> Thread M5:
the diameter its tap drill 4.2 (greyed), the step says M5, the sheet's hole size M5; a wrong thread refused.

  PYTHONIOENCODING=utf-8 py tools/e2e_model_hole_head.py http://127.0.0.1:5199 <out dir>
"""
import json
import math
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"
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


def volume():
    js(f"window.__v = null; {M}.rebuild().then(() => window.__v = {M}.result?.body?.volume)")
    time.sleep(0.3)
    wait(f"return !{M}.building && {M}.result?.body")
    time.sleep(0.5)
    return round(js(f"return {M}.result.body.volume"), 2)


def typed(k, v):
    el = d.find_element(By.CSS_SELECTOR, f"#modelRight [data-k={k}]")
    el.clear()
    el.send_keys(str(v))
    time.sleep(1.2)


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Block")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": -20, "y": -10, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    wait(f"return !!{M}.result?.body")
    js(f"{M}.action('hole')")
    time.sleep(0.4)
    js(f"{M}.cmd.feature.plane = {{ face: {{ name: 'F2:end' }}, frame: {{ o: [0, 0, 10], x: [1, 0, 0], n: [0, 0, 1] }} }}; {M}.cmd.feature.points = [[0, 0]]; {M}.cmd.feature.d = 6; {M}.renderProps(); {M}.rebuild();")
    time.sleep(1.5)
    base = 8000 - math.pi * 9 * 10
    print("the hole:", volume(), "| expected", round(base, 2))
    Select(d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=head]")).select_by_value("cbore")
    time.sleep(1.5)
    f = js(f"return {M}.cmd.feature")
    print("⌴ Counterbore: Ø", f.get("head_d"), "×", f.get("head_depth"), "| volume", volume(), "| expected", round(base - math.pi * (10.8 ** 2 / 4 - 9) * 6, 2))
    typed("head_d", 10)
    typed("head_depth", 4)
    print("Ø10 × 4:", volume(), "| expected", round(base - math.pi * 16 * 4, 2))
    Select(d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=head]")).select_by_value("csk")
    time.sleep(1.5)
    f = js(f"return {M}.cmd.feature")
    print("⌵ Countersink: Ø", f.get("head_d"), "| depth field:", bool(d.find_elements(By.CSS_SELECTOR, "#modelRight [data-k=head_depth]")),
          "| volume", volume(), "| expected", round(base - (math.pi * 3 / 3 * (36 + 9 + 18) - math.pi * 9 * 3), 2))
    print("the panel's head choices:", [o.text for o in Select(d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=head]")).options])
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=ok]").click()
    time.sleep(1)
    print("the step:", js(r"return [...document.querySelectorAll('#modelLeft .mt-item')].map(r => r.textContent.replace(/\s+/g, ' ').trim()).slice(-1)[0]"))
    r = json.loads(call("add_feature", type="hole", face="F2:end", points=[[12, 0]], d=4, head="cbore"))
    print("the AI's counterbore:", r["ok"], r["volume_change_mm3"], "| expected", round(-(math.pi * 4 * 10 + math.pi * (7.2 ** 2 / 4 - 4) * 4), 3))
    g = json.loads(call("get_model"))
    print("  get_model shows it:", [{k: s[k] for k in ("head", "head_d", "head_depth") if k in s} for s in g["steps"] if s["id"] == r["id"]])
    r = json.loads(call("edit_feature", id=r["id"], fields={"head": None}))
    print("  head taken off:", r["ok"], r["volume_change_mm3"])
    print("a wrong head:", call("add_feature", type="hole", face="F2:end", points=[[-12, 0]], d=4, head="spot")[:50])
    # a threaded hole: the panel's Thread sets the tap drill; the drawing says M5
    js(f"{M}.action('hole')")
    time.sleep(0.4)
    js(f"{M}.cmd.feature.plane = {{ face: {{ name: 'F2:end' }}, frame: {{ o: [0, 0, 10], x: [1, 0, 0], n: [0, 0, 1] }} }}; {M}.cmd.feature.points = [[-14, 5]]; {M}.renderProps(); {M}.rebuild();")
    time.sleep(1)
    Select(d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=thread]")).select_by_value("M5")
    time.sleep(1.2)
    dia = d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=d]")
    print("Thread M5: Ø", dia.get_attribute("value"), "| disabled", not dia.is_enabled())
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=ok]").click()
    time.sleep(1)
    print("  the step:", js(r"return [...document.querySelectorAll('#modelLeft .mt-item')].map(r => r.textContent.replace(/\s+/g, ' ').trim()).slice(-1)[0]"))
    print("a wrong thread:", call("add_feature", type="hole", face="F2:end", points=[[0, 5]], thread="M7")[:60])
    print("  sheet_open:", json.loads(call("sheet_open", part="Block"))["preset"])
    wait("return !!window.__app.sheet.svgEl")
    print("  the sheet's hole sizes:", sorted({x["text"] for x in json.loads(call("get_sheet"))["dims"] if x["kind"] == "dia"}))
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
