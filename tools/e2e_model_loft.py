"""⧫ Loft and 〰 Sweep in headless Edge: a 20 x 20 square on Top and a 10 x 10 square 30 mm above it (Offset) ->
⧫ Loft picks both (From / To) -> a frustum, exact volume -> Ctrl+Z; then a Ø4 circle on Front and a path on Top
(up 30 mm, then right 30) -> 〰 Sweep picks the circle as profile and the open line as path -> a bent rod; switching
profile and path gives a clear message; the AI's loft.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_model_loft.py http://127.0.0.1:5199 <out dir>
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


def wait(script, t=30):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def settled():
    time.sleep(0.3)
    wait(f"return !{M}.inflight")
    time.sleep(0.3)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def btn(sel):
    d.find_element(By.CSS_SELECTOR, sel).click()
    time.sleep(0.3)


def panel():
    return d.find_element(By.CSS_SELECTOR, "#modelRight .mp-body").text.replace("\n", " | ")


def selected(k):
    return Select(d.find_element(By.CSS_SELECTOR, f"#modelRight select[data-k={k}]")).first_selected_option.text


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Loft")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": -10, "y": -10, "w": 20, "h": 20}}])
    call("add_feature", type="sketch", plane={"datum": "XY", "offset": 30}, shapes=[{"rect": {"x": -5, "y": -5, "w": 10, "h": 10}}])
    settled()
    print("bar: loft enabled", js("return !document.querySelector('#modelViewport [data-a=loft]').disabled"))
    btn("#modelViewport [data-a=loft]")
    settled()
    print("loft panel:", panel()[:160], "| from", selected("s0"), "to", selected("s1"))
    print("preview volume:", round(js(f"return {M}.result.body.volume"), 3), "| expected", round(30 / 3 * (400 + 100 + 200), 3))
    btn("#modelViewport .view-actions [data-a=ok]")
    settled()
    js(f"{M}.view.setView('iso')")
    time.sleep(0.4)
    d.save_screenshot(f"{OUT}/loft1.png")
    print("tree:", js("return [...document.querySelectorAll('#modelLeft .mt-item')].map(e => e.textContent.trim().split(/\\s{2,}/)[0])"))

    # sweep: a new model with a circle on Front and an open path on Top
    call("new_model", name="Sweep")
    call("add_feature", type="sketch", plane="XZ", shapes=[{"circle": {"x": 0, "y": 0, "d": 4}}])
    call("add_feature", type="sketch", plane="XY", shapes=[{"path": {"points": [[0, 0], [0, 30], [30, 30]]}}])
    settled()
    print("path sketch ok by itself:", js(f"return {M}.result.features.map(s => s.ok)"))
    btn("#modelViewport [data-a=sweep]")
    settled()
    print("sweep panel:", "profile", selected("profile"), "| path", selected("path"))
    v = js(f"return {M}.result.body?.volume")
    print("preview volume:", round(v, 3), "| expected (two straight 30 mm runs, a sharp corner)", "≈", round(math.pi * 4 * 60, 1))
    Select(d.find_element(By.CSS_SELECTOR, "#modelRight select[data-k=profile]")).select_by_visible_text("Sketch 2")
    Select(d.find_element(By.CSS_SELECTOR, "#modelRight select[data-k=path]")).select_by_visible_text("Sketch 1")
    settled()
    print("swapped:", [l for l in panel().split(" | ") if l.startswith("⚠")])
    Select(d.find_element(By.CSS_SELECTOR, "#modelRight select[data-k=profile]")).select_by_visible_text("Sketch 1")
    Select(d.find_element(By.CSS_SELECTOR, "#modelRight select[data-k=path]")).select_by_visible_text("Sketch 2")
    settled()
    btn("#modelViewport .view-actions [data-a=ok]")
    settled()
    js(f"{M}.view.setView('iso')")
    time.sleep(0.4)
    d.save_screenshot(f"{OUT}/loft2_sweep.png")
    print("swept:", js(f"return {M}.result.ok"), round(js(f"return {M}.result.body.volume"), 3))

    # the AI's loft: a square to a circle
    call("new_model", name="AI loft")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": -10, "y": -10, "w": 20, "h": 20}}])
    call("add_feature", type="sketch", plane={"datum": "XY", "offset": 25}, shapes=[{"circle": {"x": 0, "y": 0, "d": 12}}])
    r = json.loads(call("add_feature", type="loft", sketches=["F1", "F2"]))
    print("AI loft:", r["ok"], r["body"]["size_mm"], r["body"]["volume_mm3"])
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
