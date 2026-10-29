"""An extrude's draft angle, in headless Edge: a 40 × 20 × 10 block -> its Extrude panel's Draft 5° typed: the walls
lean in (a prismatoid's volume), the step's text "10 mm · draft 5°" -> a pocket cut 4 deep with the AI's
add_feature extrude {draft: 5} -> Through all hides the field and drops the draft -> in Czech: "Úkos", "úkos 5°".

  PYTHONIOENCODING=utf-8 py tools/e2e_model_draft_rib.py http://127.0.0.1:5199 <out dir>
"""
import json
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
fails = []


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


def check(ok, what):
    print("OK  " if ok else "FAIL", what)
    if not ok:
        fails.append(what)


def settled_volume():
    time.sleep(0.4)
    wait(f"return !{M}.inflight && !{M}.building && {M}.result?.body")
    time.sleep(0.6)
    return js(f"return {M}.result.body.volume")


def prismatoid(h, w, dd, a):  # h · (A0 + 4 Am + A1) / 6, each wall k = h · tan a in
    k = h * math.tan(math.radians(a))
    return h / 6 * (w * dd + 4 * (w - k) * (dd - k) + (w - 2 * k) * (dd - 2 * k))


def lang(cs):  # (the 🌐 button: switched live)
    if (js("return document.documentElement.lang") == "cs") != cs:
        d.find_element(By.ID, "langBtn").click()
        time.sleep(0.5)


def last_step():
    return js(r"return [...document.querySelectorAll('#modelLeft .mt-item')].map(r => r.textContent.replace(/\s+/g, ' ').trim()).slice(-1)[0]")


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('auto3d-lang')")
    d.refresh()
    wait("return !!window.__app")
    # ---- 1. the draft angle in the Extrude panel
    call("new_model", name="Mould")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    check(abs(settled_volume() - 8000) < 0.01, "the block: 8000 mm³")
    js(f"{M}.edit('F2')")
    wait(f"return {M}.cmd?.feature?.type === 'extrude'")
    inp = d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=draft]")
    check(inp.get_attribute("value") == "0", "the Extrude panel's Draft field, 0 by default")
    check(not d.find_elements(By.CSS_SELECTOR, "#modelRight [data-k=draft] ~ .mp-slider, #modelRight .field:has([data-k=draft]) + .mp-slider"), "no slider under it (kept small)")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys("5")
    v = settled_volume()
    check(abs(v - prismatoid(10, 40, 20, 5)) < 0.05, f"5° typed: the walls lean in — {v:.2f} = {prismatoid(10, 40, 20, 5):.2f}")
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=ok]").click()
    wait(f"return !{M}.cmd && !{M}.inflight")
    check("draft 5°" in last_step(), f"the step's text: {last_step()}")
    d.save_screenshot(f"{OUT}/draft_block.png")
    # the AI: a pocket 20 × 10 cut 4 deep from the top with 5°
    call("add_feature", type="sketch", plane={"datum": "XY", "offset": 10}, shapes=[{"rect": {"x": 10, "y": 5, "w": 20, "h": 10}}])
    r = json.loads(call("add_feature", type="extrude", sketch="F3", op="cut", d=4, draft=5))
    exp = prismatoid(10, 40, 20, 5) - prismatoid(4, 20, 10, 5)
    check(r.get("ok") and abs(r["body"]["volume_mm3"] - exp) < 0.05, f"the AI's pocket with draft 5: {r.get('body', {}).get('volume_mm3')} = {exp:.2f}")
    # Through all: no draft field, the draft dropped
    js(f"{M}.edit('F4')")
    wait(f"return {M}.cmd?.feature?.type === 'extrude'")
    d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=through]").click()
    time.sleep(0.3)
    check(not d.find_elements(By.CSS_SELECTOR, "#modelRight [data-k=draft]") and js(f"return {M}.cmd.feature.draft") is None, "Through all: the draft field gone, no draft")
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=cancel]").click()
    time.sleep(0.5)
    # in Czech
    lang(True)
    js(f"{M}.edit('F2')")
    wait(f"return {M}.cmd?.feature?.type === 'extrude'")
    time.sleep(0.5)
    lab = js("return document.querySelector('#modelRight [data-k=draft]').closest('.field').querySelector('label').textContent")
    check(lab == "Úkos", f"in Czech the field is “{lab}”")
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=cancel]").click()
    time.sleep(0.5)
    step = js(r"return [...document.querySelectorAll('#modelLeft .mt-item')].map(r => r.textContent.replace(/\s+/g, ' ').trim()).find(t => t.includes('°'))")
    check("úkos 5°" in (step or ""), f"the step in Czech: {step}")
    lang(False)
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    d.quit()
print("ALL OK" if not fails and not errs else f"FAILED: {fails}")
