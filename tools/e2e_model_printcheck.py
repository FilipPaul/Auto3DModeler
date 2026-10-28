"""🖨 Print check, in headless Edge: a block -> 🖨 Print check: nothing found -> a 1 mm cap 40 × 40 on a 10 × 10 stem
(a mushroom) -> it follows the part: the cap's underside an overhang (40² − 10² = 1500 mm², red), the cap thinner than
1.2 mm (orange, thinnest 1) -> min wall 0.5: no thin walls -> off: the marks gone -> the AI's check_print.

  PYTHONIOENCODING=utf-8 py tools/e2e_model_printcheck.py http://127.0.0.1:5199 <out dir>
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


def panel():
    els = d.find_elements(By.CSS_SELECTOR, "#modelViewport .m-printcheck")
    return " | ".join(r.text.replace("\n", " ") for r in els[0].find_elements(By.CSS_SELECTOR, ".mpc-row")) if els else None


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Mushroom")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": -5, "y": -5, "w": 10, "h": 10}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    wait(f"return !!{M}.result?.body")
    time.sleep(0.5)
    d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=printcheck]").click()
    time.sleep(0.5)
    print("🖨 on a block:", panel(), "|", d.find_element(By.CSS_SELECTOR, "#modelViewport .m-printcheck .hint").text)
    call("add_feature", type="sketch", plane={"face": "F2:end"}, shapes=[{"rect": {"x": -20, "y": -20, "w": 40, "h": 40}}])
    call("add_feature", type="extrude", sketch="F3", d=1)
    time.sleep(1.5)
    print("the cap on:", panel(), "| marks drawn:", js(f"return !!{M}.view.printMarks"))
    js(f"{M}.view.setView('front')")
    time.sleep(0.6)
    d.find_element(By.CSS_SELECTOR, "#modelViewport").screenshot(f"{OUT}/printcheck.png")
    js("const w = document.querySelector('#modelViewport .m-printcheck [data-k=minWall]'); w.value = '0.5'; w.dispatchEvent(new Event('change'));")
    time.sleep(0.8)
    print("min wall 0.5:", panel())
    d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=printcheck]").click()
    time.sleep(0.4)
    print("off:", panel(), "| marks:", js(f"return !!{M}.view.printMarks"))
    r = json.loads(call("check_print"))
    print("the AI's check_print:", {k: r[k] for k in ("overhang_mm2", "thin_mm2", "thinnest_mm", "ok")}, "| overhang box", r["overhang_box"])
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
