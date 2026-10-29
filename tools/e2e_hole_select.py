"""Choosing a hole that is there already never arms the Hole tool, in headless Edge with real mouse clicks: a 40 × 40 ×
10 block with a Ø6 hole -> its row in the step list clicked: chosen, no tool open, ◎ Hole not lit; a click on the part
adds no hole -> ✎ Edit the step: the panel opens, but the mouse shows no new hole and a click adds none (a notice says
＋ Add position) -> ＋ Add position: the mouse shows the hole, a click adds one -> OK: 2 holes, the volume of two.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_hole_select.py http://127.0.0.1:5199 <out dir>
"""
import math
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
H = "window.__app.agentHandlers"
M = "window.__app.modeler"
CV = "#modelViewport canvas"
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


def check(what, ok):
    print(("  ok  " if ok else "  FAIL") + " " + what)
    if not ok:
        fails.append(what)


def settled():
    time.sleep(0.6)
    wait(f"return !{M}.inflight")
    time.sleep(0.4)


def off_3d(p):
    return js(f"""const v = {M}.view, V = v.camera.position.constructor, [sx, sy] = v.toScreen(new V(...arguments[0])), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(p))


def move_to(p):
    ActionChains(d, duration=30).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, CV), *off_3d(p)).perform()
    time.sleep(0.4)


def click_at(p):
    move_to(p)
    ActionChains(d).click().perform()
    time.sleep(0.6)


def positions():
    return sum(len(f["points"]) for f in js(f"return {M}.part.features") if f["type"] == "hole")


def toasts():
    return " | ".join(e.text for e in d.find_elements(By.CSS_SELECTOR, ".toast"))


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Select")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=6, through=True)
    settled()
    js(f"{M}.view.setView('top')")
    time.sleep(0.6)
    hole = js(f"return {M}.part.features.find(f => f.type === 'hole').id")

    # ---- its row in the list: chosen only
    row = next(r for r in d.find_elements(By.CSS_SELECTOR, "#modelLeft .mt-item") if "Hole" in r.text or "Díra" in r.text)
    row.click()
    time.sleep(0.8)
    print("row clicked: selected", js(f"return {M}.selected"), "| cmd", js(f"return {M}.cmd && {M}.cmd.feature.type"))
    check("the hole step chosen, no tool open", js(f"return {M}.selected") == hole and js(f"return !{M}.cmd"))
    check("◎ Hole is not lit", not js("return !!document.querySelector('#modelViewport [data-a=hole].on')"))
    move_to([10, 30, 10])
    check("no hole preview at the mouse", js(f"return !{M}.spot"))
    click_at([10, 30, 10])
    settled()
    check("a click on the part adds no hole", positions() == 1 and js(f"return !{M}.cmd"))

    # ---- ✎ Edit the step: the panel, but no placing until ＋ Add position
    js(f"{M}.edit(arguments[0])", hole)
    settled()
    check("editing: the hole's panel is open", js(f"return {M}.cmd?.feature.type") == "hole" and js(f"return {M}.cmd.place") is False)
    move_to([10, 30, 10])
    check("editing: no hole preview at the mouse", js(f"return !{M}.spot"))
    click_at([10, 30, 10])
    print("editing, clicked:", js(f"return {M}.cmd.feature.points"), "|", toasts())
    check("editing: a click adds no hole, a notice says how", len(js(f"return {M}.cmd.feature.points")) == 1 and ("Add position" in toasts() or "Přidat pozici" in toasts()))
    d.find_element(By.CSS_SELECTOR, "#modelRight [data-a=addpos]").click()
    time.sleep(0.4)
    move_to([10, 30, 10])
    check("＋ Add position: the hole shown at the mouse", js(f"return !!{M}.spot"))
    click_at([10, 30, 10])
    check("＋ Add position: a click adds a hole", len(js(f"return {M}.cmd.feature.points")) == 2)
    d.save_screenshot(f"{OUT}/hole_select_add.png")
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=ok]").click()
    settled()
    v = js(f"return {M}.result.body.volume")
    check(f"OK: 2 holes ({v:.2f})", positions() == 2 and abs(v - (16000 - 2 * math.pi * 9 * 10)) < 0.5)
finally:
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        fails.append("console errors")
    d.quit()

print("FAILED:" if fails else "ALL OK", fails if fails else "")
sys.exit(1 if fails else 0)
