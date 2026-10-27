"""Dimensions from the part's edges that FOLLOW the part, with REAL mouse input in headless Edge:
1. ◎ Hole on a 40 x 20 x 10 box: a click on the top face places it from the nearest edges ("↔ 10 mm from the
   right edge", "↕ 5 mm from the lower edge"), drawn on the face; typing 8 moves it; ⇄ measures from the left;
   the box gets 60 wide (an earlier step) -> the hole keeps its distance from its edge.
2. A sketch on the top face: a circle dimensioned from the part's right edge with ↔ Dimension (typed 7), cut
   through; the box gets wider -> the circle stays 7 from the right edge (not at a fixed point).

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_model_refs.py http://127.0.0.1:5199 <out dir>
"""
import json
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
SK = f"{M}.sk"
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


def off_uv(uv):
    return js(f"""const m = {M}, v = m.view, f = m.frame(), [u, w] = arguments[0];
      const y = [f.n[1]*f.x[2]-f.n[2]*f.x[1], f.n[2]*f.x[0]-f.n[0]*f.x[2], f.n[0]*f.x[1]-f.n[1]*f.x[0]];
      const p = new (v.camera.position.constructor)(f.o[0] + u*f.x[0] + w*y[0], f.o[1] + u*f.x[1] + w*y[1], f.o[2] + u*f.x[2] + w*y[2]);
      const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(uv))


def click(o):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *o).perform()
    time.sleep(0.15)
    ActionChains(d).click().perform()
    time.sleep(0.35)


def btn(sel):
    d.find_element(By.CSS_SELECTOR, sel).click()
    time.sleep(0.3)


def holes():
    b = js(f"return {M}.result.body")
    return sorted([round(c, 3) for c in f["centroid"][:2]] for f in b["faces"] if f["type"] == "cylinder")


def box(name, w):
    call("new_model", name=name)
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": w, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    settled()


try:
    d.get(URL)
    wait("return !!window.__app")

    # 1. a hole placed from the face's edges
    box("Holes", 40)
    js(f"{M}.view.setView('top')")
    time.sleep(0.4)
    btn("#modelViewport [data-a=hole]")
    click(off_xyz([30, 5, 10]))
    settled()
    f = js(f"return {M}.cmd.feature")
    print("placed:", f["points"], "| from:", json.dumps(f["from"]))
    print("panel:", [r.text for r in d.find_elements(By.CSS_SELECTOR, "#modelRight .mp-hd")])
    print("drawn on the face:", js("return [...document.querySelectorAll('.sk-label.hole-dim')].map(e => e.textContent)"))
    inp = d.find_element(By.CSS_SELECTOR, "#modelRight [data-hd='0:x']")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys("8")
    settled()
    print("typed 8:", js(f"return {M}.cmd.feature.points"), "| holes", holes())
    d.save_screenshot(f"{OUT}/refs1_hole.png")
    btn("#modelRight [data-flip='0:x']")
    print("⇄:", [r.text for r in d.find_elements(By.CSS_SELECTOR, "#modelRight .mp-hd")][0], js(f"return {M}.cmd.feature.from[0].x.d"))
    btn("#modelRight [data-flip='0:x']")  # back to the right edge (8 from it)
    btn("#modelViewport .view-actions [data-a=ok]")
    settled()
    call("edit_feature", id="F1", fields={"shapes": [{"rect": {"x": 0, "y": 0, "w": 60, "h": 20}}]})
    settled()
    print("box 60 wide -> hole (8 from the right edge, 5 from the front):", holes(), "| stored", js(f"return {M}.part.features[2].points"))
    call("undo")
    settled()
    print("undo -> box 40:", holes())

    # 2. a sketch circle dimensioned from the part's right edge
    box("Sketched", 40)
    btn("#modelViewport [data-a=sketch]")
    click(off_xyz([12, 6, 10]))
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.6)
    fr = js(f"return {M}.frame()")
    print("sketch on the top face, origin", fr["o"])
    btn(".m-cmdbar [data-a=circle]")
    click(off_uv([10, -5]))
    click(off_uv([13, -5]))
    btn(".m-cmdbar [data-a=dim]")
    click(off_uv([13, -5]))   # the circle -> its centre
    click(off_uv([20, 2]))    # the part's right edge (dashed), at u = 20
    time.sleep(0.6)
    inp = d.find_elements(By.CSS_SELECTOR, ".sk-input")
    print("editor opened:", bool(inp))
    inp[0].send_keys(Keys.CONTROL, "a")
    inp[0].send_keys("7", Keys.ENTER)
    time.sleep(0.8)
    dim = js(f"return {SK}.f.dims.find(x => x.t === 'dx' && typeof x.a === 'object')")
    print("dimension:", json.dumps(dim))
    d.save_screenshot(f"{OUT}/refs2_sketch.png")
    btn("#modelViewport .view-actions [data-a=finish]")
    settled()
    js("document.querySelector('#modelRight [data-k=through]')?.click()")
    settled()
    btn("#modelViewport .view-actions [data-a=ok]")
    settled()
    print("cut:", holes())
    call("edit_feature", id="F1", fields={"shapes": [{"rect": {"x": 0, "y": 0, "w": 60, "h": 20}}]})
    settled()
    print("box 60 wide -> circle (7 from the right edge):", holes(), "| sketch point", js(f"return {M}.part.features[2].points"),
          "| warnings", [s["warnings"] for s in js(f"return {M}.result.features") if s["warnings"]])
    js(f"{M}.view.setView('iso')")
    time.sleep(0.4)
    d.save_screenshot(f"{OUT}/refs3_followed.png")
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
