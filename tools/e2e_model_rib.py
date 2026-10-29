"""⊿ Rib, in headless Edge: an L bracket (a plate 40 × 20 × 5, a wall 5 thick at its back, 30 tall) and a sketch on the
Right plane through its middle with one line from the wall to the plate -> ⊿ Rib in the toolbar: that sketch, 3 thick
-> 4: the triangle under the line filled (+ ½ · 15 · 20 · 4) -> OK: the step's text -> the AI's add_feature rib on a
line in the air: refused with the reason.

  PYTHONIOENCODING=utf-8 py tools/e2e_model_rib.py http://127.0.0.1:5199 <out dir>
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


def settled_volume():
    time.sleep(0.4)
    wait(f"return !{M}.building && {M}.result?.body")
    time.sleep(0.6)
    return round(js(f"return {M}.result.body.volume"), 2)


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Bracket")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 15, "w": 40, "h": 5}}])
    call("add_feature", type="extrude", sketch="F3", d=30)
    call("add_feature", type="sketch", plane={"datum": "YZ", "offset": 20}, shapes=[{"path": {"points": [[15, 25], [0, 5]]}}])
    v0 = settled_volume()
    print("the bracket:", v0)
    d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=rib]").click()
    time.sleep(0.5)
    f = js(f"return {M}.cmd?.feature")
    print("⊿ Rib:", f and [f["name"], f["sketch"], f["t"]], "| its sketch chosen:", d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=sketch]").get_attribute("value"))
    print("  3 thick:", round(settled_volume() - v0, 2), "| expected", 0.5 * 15 * 20 * 3)
    el = d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=t]")
    el.clear()
    el.send_keys("4\n")
    print("  4 thick:", round(settled_volume() - v0, 2), "| expected", 0.5 * 15 * 20 * 4)
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=ok]").click()
    time.sleep(1)
    print("the step:", js(r"return [...document.querySelectorAll('#modelLeft .mt-item:not([data-parent])')].map(r => r.textContent.replace(/\s+/g, ' ').trim()).slice(-1)[0]"))
    call("add_feature", type="sketch", plane={"datum": "YZ", "offset": 10}, shapes=[{"path": {"points": [[15, 60], [0, 45]]}}])
    r = json.loads(call("add_feature", type="rib", t=3))
    print("the AI's rib in the air:", r["ok"], "|", (r["issues"] or [""])[0][:70])
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
