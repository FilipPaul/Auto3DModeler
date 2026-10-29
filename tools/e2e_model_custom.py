"""Custom references in the 3D tools, with REAL mouse input in headless Edge:
1. ◎ Hole: the 🎯 button, then a click on the box's left edge -> "↔ 30 mm from the left edge"; a second hole
   measured from the first hole (🎯 + a click on its rim) -> "mm right of the hole"; the first hole moves -> the
   second follows.
2. ⬆ Extrude "Up to a face": a pin sketched beside the box on the bed, up to the box's top + 5 mm offset; the box
   gets taller -> the pin follows.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_model_custom.py http://127.0.0.1:5199 <out dir>
"""
import json
import math
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


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#modelViewport canvas")


def off_xyz(p):
    return js(f"""const v = {M}.view, [x, y, z] = arguments[0];
      const [sx, sy] = v.toScreen(new (v.camera.position.constructor)(x, y, z)), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(p))


def click(o):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *o).perform()
    time.sleep(0.2)
    ActionChains(d).click().perform()
    time.sleep(0.4)


def btn(sel):
    d.find_element(By.CSS_SELECTOR, sel).click()
    time.sleep(0.3)


def holes():
    b = js(f"return {M}.result.body")
    return sorted([round(c, 3) for c in f["centroid"][:2]] for f in b["faces"] if f["type"] == "cylinder")


def rows():
    return [r.text.replace("\n", " ") for r in d.find_elements(By.CSS_SELECTOR, "#modelRight .mp-hd")]


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Custom")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    settled()
    js(f"{M}.view.setView('top')")
    time.sleep(0.4)

    # 1. a hole measured from the left edge (picked), a second one from the first hole
    btn("#modelViewport [data-a=hole]")
    click(off_xyz([30, 5, 10]))
    settled()
    print("default:", rows())
    btn("#modelRight [data-pickref='0:x']")
    print("hint:", js("return document.querySelector('#modelViewport .m-hint').textContent"))
    click(off_xyz([0, 12, 10]))  # the box's left edge
    settled()
    print("from the left edge:", rows(), json.dumps(js(f"return {M}.cmd.feature.from[0].x")))
    click(off_xyz([18, 14, 10]))  # a second hole
    settled()
    btn("#modelRight [data-pickref='1:x']")
    click(off_xyz([30 - 2.5, 5, 10]))  # the first hole's rim (Ø5)
    settled()
    print("second hole from the first:", rows())
    d.save_screenshot(f"{OUT}/custom1_holes.png")
    btn("#modelViewport .view-actions [data-a=ok]")
    settled()
    print("holes:", holes())
    # the first hole 25 from the left (not 30): the second follows (12 left of it)
    f = js(f"return {M}.part.features.find(f => f.type === 'hole')")
    call("edit_feature", id=f["id"], fields={"from": [{**f["from"][0], "x": {**f["from"][0]["x"], "d": 25}}, f["from"][1]]})
    settled()
    print("first hole moved to 25:", holes(), "| ok", js(f"return {M}.result.ok"))

    # 2. a pin beside the box, up to the box's top + 5
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 60, "y": 10, "d": 6}}])
    settled()
    sk = js(f"return {M}.part.features.at(-1).id")
    btn("#modelViewport [data-a=extrude]")
    settled()
    print("extrude panel:", d.find_element(By.CSS_SELECTOR, "#modelRight .mp-body").text.split("\n")[:4])
    btn("#modelRight [data-upto='1']")
    js(f"{M}.view.setView('iso')")
    time.sleep(0.5)
    click(off_xyz([20, 10, 10]))  # the box's top face
    settled()
    inp = d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=offset]")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys("5")
    settled()
    print("up to:", d.find_element(By.CSS_SELECTOR, "#modelRight .mp-count").text, "| bbox", js(f"return {M}.result.body.bbox"))
    d.save_screenshot(f"{OUT}/custom2_upto.png")
    btn("#modelViewport .view-actions [data-a=ok]")
    settled()
    print("tree:", js("return [...document.querySelectorAll('#modelLeft .mt-item:not([data-parent])')].map(e => e.innerText.replace(/\\n/g, ' '))")[-1])
    v0 = js(f"return {M}.result.body.volume")
    print("volume:", round(v0, 3))
    call("edit_feature", id="F2", fields={"d": 20})
    settled()
    print("box 20 tall -> pin top:", js(f"return {M}.result.body.bbox")[5], "(expected 25)")
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
