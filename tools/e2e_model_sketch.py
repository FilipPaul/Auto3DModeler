"""Sketch locks with REAL mouse input in headless Edge: a plate and a hole; lock the hole's position (🔓 -> 🔒),
type a new plate width -> the hole stays 10 mm from the edge; drag a corner -> the locked width holds and only
the free height follows; lock everything -> "Fully locked"; unlock the width -> dragging changes it; a
triangle with the line tool (closed by clicking its first point); Ctrl+Z in the sketch; extrude volume.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_model_sketch.py http://127.0.0.1:5199 <out dir>
"""
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
SK = f"{M}.sk"


def wait(script, t=30):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#modelViewport canvas")


def off(uv):
    return js(f"""const m = {M}, v = m.view, f = m.frame(), [u, w] = arguments[0];
      const y = [f.n[1]*f.x[2]-f.n[2]*f.x[1], f.n[2]*f.x[0]-f.n[0]*f.x[2], f.n[0]*f.x[1]-f.n[1]*f.x[0]];
      const p = new (v.camera.position.constructor)(f.o[0] + u*f.x[0] + w*y[0], f.o[1] + u*f.x[1] + w*y[1], f.o[2] + u*f.x[2] + w*y[2]);
      const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(uv))


def click_uv(uv):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *off(uv)).perform()
    time.sleep(0.12)
    ActionChains(d).click().perform()
    time.sleep(0.25)


def drag_uv(a, b):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *off(a)).perform()
    time.sleep(0.15)
    ac = ActionChains(d, duration=60).click_and_hold()
    ox, oy = off(a)
    tx, ty = off(b)
    for k in range(1, 6):
        ac = ac.move_by_offset(round((tx - ox) / 5), round((ty - oy) / 5))
    ac.release().perform()
    time.sleep(0.6)


def label(text):
    """The size label showing `text` (its value part)."""
    for el in d.find_elements(By.CSS_SELECTOR, ".sk-label.edit"):
        if el.find_element(By.CSS_SELECTOR, ".sk-val").text == text:
            return el
    raise LookupError(f"no label {text!r}: {[e.text for e in d.find_elements(By.CSS_SELECTOR, '.sk-label.edit')]}")


def type_label(text, value):
    label(text).find_element(By.CSS_SELECTOR, ".sk-val").click()
    time.sleep(0.2)
    inp = d.find_element(By.CSS_SELECTOR, ".sk-input")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys(str(value), Keys.ENTER)
    time.sleep(0.6)


def lock(text):
    label(text).find_element(By.CSS_SELECTOR, ".sk-lock").click()
    time.sleep(0.6)


def pts():
    return js(f"return Object.fromEntries(Object.entries({SK}.f.points).map(([k, p]) => [k, p.map(v => +v.toFixed(4))]))")


def labels():
    return js("return [...document.querySelectorAll('.sk-label.edit')].map(l => l.textContent)")


def tool(t):
    d.find_element(By.CSS_SELECTOR, f".m-cmdbar [data-a={t}]").click()
    time.sleep(0.2)


try:
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "newModelBtn").click()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.8)

    # plate 40 x 20 from the origin, a circle at (10, 10) with r 3
    click_uv((0, 0))
    click_uv((40, 20))
    tool("circle")
    click_uv((10, 10))
    click_uv((13, 10))
    print("drawn:", pts(), "| labels", labels())

    # select the circle, lock its position (x 10, y 10) with the 🔓 buttons
    tool("select")
    click_uv((10, 12.5))  # inside the circle
    print("selected:", js(f"return {SK}.sel"), "| labels", labels())
    # its position from the origin with ↔ Dimension: origin -> circle, choose along x (then along y), keep the value
    for which in (0, 1):
        tool("dim")
        click_uv((0, 0))
        click_uv((10 - 5, 10))  # the circle's left edge (r 5)
        d.find_elements(By.CSS_SELECTOR, ".sk-choose button")[which].click()
        time.sleep(0.5)
        wait("return document.querySelector('.sk-input')")
        d.find_element(By.CSS_SELECTOR, ".sk-input").send_keys(Keys.ENTER)
        time.sleep(0.5)
    tool("select")
    print("position locked:", js(f"return {SK}.f.dims.map(d => [d.t, d.a, d.b, d.v])"))

    # a wider plate: type 80 on the width label -> the hole stays at x 10
    type_label("40", 80)
    p = pts()
    print("width 80:", p, "| hole centre", js(f"return {SK}.P({SK}.f.entities.find(e => e.t === 'circle').c)"))
    d.save_screenshot(f"{OUT}/s1_locked.png")

    # drag the top-right corner to (95, 35): width locked -> x stays 80, the height follows
    drag_uv((80, 20), (95, 35))
    p = pts()
    print("corner dragged:", p["p3"], "| plate", p)

    # lock the height and the diameter -> fully locked
    h = js(f"return {SK}.f.points.p3[1]")
    lock(f"{round(h, 3):g}")
    lock(js("return [...document.querySelectorAll('.sk-label.edit .sk-val')].map(v => v.textContent).find(t => t.startsWith('Ø'))"))
    print("dof:", js(f"return {SK}.dof"), "|", js("return document.querySelector('.sk-dof')?.textContent"))

    # a contradicting size is refused, with the reason
    js(f"{SK}.setSize({{t: 'dx', a: 'O', b: 'p1'}}, 5)")
    time.sleep(0.6)
    print("typing a new value for a locked position changes it:", pts()["p1"], pts()["p2"])
    js(f"{SK}.back()")
    time.sleep(0.4)

    # unlock the width -> dragging the corner changes it now
    lock("80")
    drag_uv((80, h), (60, h))
    print("width free, corner dragged to 60:", pts()["p3"])

    # the line tool: a triangle away from the plate, closed by clicking its first point
    tool("line")
    for uv in ((-35, 5), (-10, 5), (-35, 30), (-35, 5)):
        click_uv(uv)
    lines = js(f"return {SK}.f.entities.filter(e => e.t === 'line' && !e.g).map(e => [e.a, e.b])")
    print("triangle lines:", lines, "| H/V rules:", js(f"return {SK}.f.constraints.filter(c => !{SK}.ent(c.e)?.g).map(c => c.t)"))
    d.save_screenshot(f"{OUT}/s2_triangle.png")

    # Ctrl+Z removes the last line, Ctrl+Y is not needed: draw it again
    n0 = js(f"return {SK}.f.entities.length")
    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    time.sleep(0.3)
    print("Ctrl+Z in the sketch:", n0, "->", js(f"return {SK}.f.entities.length"))
    tool("line")
    click_uv((-35, 30))
    click_uv((-35, 5))

    # finish -> extrude 5 mm: plate (60 x h) minus the hole, plus the triangle
    d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=finish]").click()
    wait(f"return {M}.cmd && {M}.result?.body && !{M}.inflight")
    time.sleep(0.6)
    dist = d.find_element(By.CSS_SELECTOR, "#modelRight input[data-k=d]")
    dist.send_keys(Keys.CONTROL, "a")
    dist.send_keys("5", Keys.ENTER)
    wait(f"return !{M}.cmd && !{M}.inflight")
    time.sleep(0.6)
    vol = js(f"return {M}.result.body.volume")
    r = js(f"return {M}.part.features[0].entities.find(e => e.t === 'circle').r")
    exp = (60 * h - math.pi * r * r + 25 * 25 / 2) * 5
    print(f"volume {vol:.3f} expected {exp:.3f} | steps", js(f"return {M}.part.features.map(f => f.name)"),
          "| issues", js(f"return {M}.result.features.filter(s => !s.ok)"))
    d.save_screenshot(f"{OUT}/s3_extruded.png")

    # reopen the sketch: locks are still there
    d.find_elements(By.CSS_SELECTOR, ".mt-item")[0].click()
    ActionChains(d).double_click(d.find_elements(By.CSS_SELECTOR, ".mt-item")[0]).perform()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.8)
    print("reopened sketch: locks", js(f"return {SK}.f.dims.length"), "| dof", js(f"return {SK}.dof"))

    # sketches are lines in the 3D view: a used one faint, one not extruded yet bright; double-click opens it
    d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=cancelSketch]").click()
    wait(f"return {M}.mode === 'part' && !{M}.inflight")
    time.sleep(0.4)
    outl = f"return {M}.view.outlineGroup.children.map(c => [c.userData.sketch, +c.material.opacity.toFixed(2)])"
    print("outlines (used sketch):", js(outl))
    d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=sketch]").click()
    time.sleep(0.3)
    d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=datum-XY]").click()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.5)
    tool("circle")
    click_uv((-60, 20))
    click_uv((-50, 20))
    d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=finish]").click()
    wait(f"return {M}.cmd && !{M}.inflight")
    d.find_element(By.CSS_SELECTOR, "#modelRight [data-a=cancel]").click()
    wait(f"return !{M}.cmd && !{M}.inflight")
    time.sleep(0.5)
    print("outlines (+ a sketch not extruded):", js(outl), "| steps", js(f"return {M}.part.features.map(f => f.name)"))
    d.save_screenshot(f"{OUT}/s4_outlines.png")
    # double-click on its circle (screen point of the circle's edge)
    pt = js(f"""const v = {M}.view, f = {M}.part.features.at(-1), c = f.points[f.entities[0].c], r = f.entities[0].r;
      const p = new (v.camera.position.constructor)(c[0] + r, c[1], 0), [sx, sy] = v.toScreen(p), R = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(R.left + R.width / 2)), Math.round(sy - Math.floor(R.top + R.height / 2))];""")
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *pt).perform()
    time.sleep(0.2)
    print("hover over its lines:", js("return document.querySelector('#modelViewport canvas').title"))
    ActionChains(d).double_click().perform()
    time.sleep(0.6)
    print("double-click opens it:", js(f"return [{M}.mode, {SK}?.f.name]"))
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
