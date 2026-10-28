"""Ctrl+click to choose several things in the 3D model, with real mouse clicks in headless Edge: a plate 40 × 20 × 10, a
boss 10 × 10 × 10 on it, a Ø8 hole -> a click on the plate's top, Ctrl+click on the boss's top: 2 chosen, both steps
lit, "Gap between the faces 10 mm" and the distance; Ctrl+click a corner: 3; Ctrl+click the boss again: taken away
-> ◌ Turn them off (the plate and the boss at once), ↶ back -> the boss and the hole chosen: ✕ Delete them (one step).

  PYTHONIOENCODING=utf-8 py tools/e2e_model_multipick.py http://127.0.0.1:5199 <out dir>
"""
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"
H = "window.__app.agentHandlers"


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(script)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def settle():
    time.sleep(0.4)
    wait(f"return !{M}.building && {M}.result?.body")
    time.sleep(0.5)


def click(p, ctrl=False):
    off = js(f"""const v = {M}.view, p = arguments[0];
      const [sx, sy] = v.toScreen(new (v.camera.position.constructor)(p[0], p[1], p[2])), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", p)
    cv = d.find_element(By.CSS_SELECTOR, "#modelViewport canvas")
    ActionChains(d, duration=30).move_to_element_with_offset(cv, *off).perform()
    time.sleep(0.2)
    ch = ActionChains(d)
    (ch.key_down(Keys.CONTROL).click().key_up(Keys.CONTROL) if ctrl else ch.click()).perform()
    time.sleep(0.5)


def table():
    box = d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest")
    if not box:
        return None
    return {"title": box[0].find_element(By.CSS_SELECTOR, ".vs-head b").text,
            "sections": [e.text for e in box[0].find_elements(By.CSS_SELECTOR, ".vs-sec")],
            "items": [" ".join(b.text.split()) for b in box[0].find_elements(By.CSS_SELECTOR, ".vs-list button")]}


def press(label):
    next(b for b in d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-list button") if label in b.text).click()
    time.sleep(0.6)


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Plate with a boss")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="sketch", plane={"face": "F2:end"}, shapes=[{"rect": {"x": -5, "y": -5, "w": 10, "h": 10}}])
    call("add_feature", type="extrude", sketch="F3", d=10)
    call("add_feature", type="hole", face="F2:end", points=[[12, 0]], d=8)
    settle()
    js(f"{M}.view.setView('iso')")
    time.sleep(0.5)
    click([6, 6, 10])
    print("a click on the plate's top:", table()["title"])
    click([18, 12, 20], ctrl=True)
    tb = table()
    print("+ Ctrl the boss's top:", tb, "| lit faces:", js(f"return {M}.view.selSet?.size || 0"))
    d.save_screenshot(f"{OUT}/multipick.png")
    click([40, 0, 10], ctrl=True)
    print("+ Ctrl a corner:", table()["title"], "| points marked:", js(f"return {M}.picks.filter(q => q.kind === 'point').length"))
    click([18, 12, 20], ctrl=True)
    print("Ctrl the boss again (taken away):", table()["title"], "|", table()["sections"])
    click([40, 0, 10], ctrl=True)  # (the corner away too: only the plate)
    click([18, 12, 20], ctrl=True)
    press("Turn them off")
    time.sleep(0.4)
    wait(f"return !{M}.building")  # (both off: no body at all)
    print("◌ Turn them off:", js(f"return {M}.part.features.filter(f => f.suppressed).map(f => f.name)"))
    js(f"{M}.history.go(-1)")
    settle()
    print("  ↶ back:", js(f"return {M}.part.features.filter(f => f.suppressed).length"), "off")
    n0 = js(f"return {M}.part.features.length")
    click([18, 12, 20])
    click([29.9, 13.43, 5], ctrl=True)  # the hole's far wall (Ø8 at (32, 10): the side the iso camera looks at, between its rims)
    tb = table()
    print("the boss + the hole:", tb["sections"] if tb else None)
    press("Delete them")
    settle()
    print("✕ Delete them:", n0, "->", js(f"return {M}.part.features.length"), "steps |", js(f"return {M}.part.features.map(f => f.name)"))
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
