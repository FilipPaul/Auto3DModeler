"""📏 Show: Dimensions in the 3D model's bottom row (Snap / Hover / Show), in headless Edge, Czech: a block's extrude chosen
-> its sizes on the part -> 📏 switched off: none, the left panel's Rozměry on Žádné -> on: back (the mode before) ->
the left panel's Žádné: the bottom button follows -> a reload keeps it. No console errors.

  PYTHONIOENCODING=utf-8 py tools/e2e_dims_toggle.py http://127.0.0.1:5199 <out dir>
"""
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
bad = []


def check(ok, what):
    print(("  ok  " if ok else "  FAIL") + " " + what)
    if not ok:
        bad.append(what)


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


def tags():
    return js("return [...document.querySelectorAll('.m-dimtag')].filter(e => e.getClientRects().length).length")


def btn():
    return d.find_element(By.CSS_SELECTOR, "#modelViewport .snap-filters [data-show=dims]")


def mode():
    return js(f"return {M}.sizeMode")


def show_step():
    wait(f"return !{M}.inflight")
    js(f"{M}.selectStep('F2')")
    time.sleep(0.6)


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.setItem('auto3d-lang', 'cs'); localStorage.removeItem('a3d.sizes')")
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Blok")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 30}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    show_step()
    n = tags()
    check(n > 0 and mode() == "all", f"the extrude's sizes show on the part: {n} ({mode()})")
    b = btn()
    name = b.text + " " + (b.get_attribute("title") or "")
    check("Rozměry" in name and "on" in b.get_attribute("class"), f"the bottom row has 📏 Rozměry, on: {name!r}")
    b.click()
    time.sleep(0.5)
    check(tags() == 0 and mode() == "none", f"switched off: no sizes, the mode Žádné ({tags()}, {mode()})")
    left = js("return document.querySelector('.m-sizes [data-sz].on')?.dataset.sz")
    check(left == "none", f"the left panel's Rozměry follow: {left}")
    d.save_screenshot(f"{OUT}/dims_hidden.png")
    btn().click()
    time.sleep(0.5)
    show_step()
    check(tags() > 0 and mode() == "all", f"on again: back to the mode before ({tags()}, {mode()})")
    js("document.querySelector('.m-sizes [data-sz=none]')?.click()")
    time.sleep(0.5)
    check("on" not in btn().get_attribute("class"), "the left panel's Žádné: the bottom button goes off too")
    d.refresh()
    wait("return !!window.__app")
    time.sleep(1.5)
    check(mode() == "none", f"after a reload: still hidden ({mode()})")
    errs = [x["message"] for x in d.get_log("browser") if x["level"] == "SEVERE"]
    check(not errs, f"no console errors {errs}")
finally:
    d.quit()
print("ALL OK" if not bad else f"FAILED: {bad}")
sys.exit(1 if bad else 0)
