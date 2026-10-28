"""⟋ Draft, in headless Edge: a 40 × 20 × 10 block -> ⟋ Draft (its extrude chosen, 3°) -> 5° typed: the walls lean in
(the volume of the frustum) -> OK: a step "Draft 1 · 5° · Extrude 1" -> 60° typed: refused with the most that fits;
the AI's add_feature draft.

  PYTHONIOENCODING=utf-8 py tools/e2e_model_draft.py http://127.0.0.1:5199 <out dir>
"""
import math
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1500,900")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
H = "window.__app.agentHandlers"
M = "window.__app.modeler"


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(script)


def angle(v):
    inp = d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=angle]")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys(str(v), Keys.ENTER)
    time.sleep(0.5)
    wait(f"return !{M}.inflight")


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Mould")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    wait(f"return {M}.result?.body && !{M}.inflight")
    d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=draft]").click()
    wait(f"return {M}.cmd?.feature?.type === 'draft'")
    print("⟋ Draft:", js(f"return [{M}.cmd.feature.of, {M}.cmd.feature.angle]"), "| its panel:", d.find_element(By.CSS_SELECTOR, "#modelRight h2").text)
    angle(5)
    k = 10 * math.tan(math.radians(5))
    a0, a1 = 800, (40 - 2 * k) * (20 - 2 * k)
    print("5°: volume", round(js(f"return {M}.result.body.volume"), 1), "| a frustum:", round(10 / 3 * (a0 + a1 + math.sqrt(a0 * a1)), 1))
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=ok]").click()
    wait(f"return !{M}.cmd && !{M}.inflight")
    print("the step:", js("return [...document.querySelectorAll('#modelLeft .mt-item')].map(r => r.textContent.replace(/\s+/g, ' ').trim()).slice(-1)[0]"))
    js(f"{M}.edit('F3')")
    wait(f"return {M}.cmd?.feature?.type === 'draft'")
    angle(60)
    wait("return document.querySelector('#modelRight .mp-bad')", 15)
    print("60°:", d.find_element(By.CSS_SELECTOR, "#modelRight .mp-bad").text[:70])
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=cancel]").click()
    time.sleep(0.5)
    print("the AI's draft:", call("add_feature", type="draft", of="F2", angle=2)[:60])
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
