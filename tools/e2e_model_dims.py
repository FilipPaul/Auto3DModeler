"""Dimensions in a sketch with REAL mouse input: a plate, a sketch on its top face (the part turns see-through,
its edges show dashed), a circle, then ↔ Dimension: circle -> the plate's top edge, type 6; circle -> the right
edge, type 8 -> the hole sits 6 / 8 mm from those edges; no automatic x / y labels; ✕ deletes a dimension;
two points -> the "which distance?" chooser; cut through -> volume.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_model_dims.py http://127.0.0.1:5199 <out dir>
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
    time.sleep(0.3)


def tool(t):
    d.find_element(By.CSS_SELECTOR, f".m-cmdbar [data-a={t}], #modelViewport .view-actions [data-a={t}]").click()
    time.sleep(0.2)


def type_open_input(value):
    inp = wait("return document.querySelector('.sk-input')")
    inp = d.find_element(By.CSS_SELECTOR, ".sk-input")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys(str(value), Keys.ENTER)
    time.sleep(0.7)


def centre():
    return js(f"const c = {SK}.f.entities.find(e => e.t === 'circle'); return {SK}.P(c.c).map(v => +v.toFixed(4))")


def labels():
    return js("return [...document.querySelectorAll('.sk-label.edit')].map(l => l.querySelector('.sk-val').textContent)")


try:
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "newModelBtn").click()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.6)
    click_uv((0, 0))
    click_uv((40, 20))
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=finish]").click()
    wait(f"return {M}.cmd && {M}.result?.body && !{M}.inflight")
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=ok]").click()
    wait(f"return !{M}.cmd && !{M}.inflight")
    time.sleep(0.5)

    # a sketch on the top face
    tool("sketch")
    pt = js(f"""const v = {M}.view, r = v.renderer.domElement.getBoundingClientRect();
      for (let gy = 0.25; gy < 0.85; gy += 0.01) for (let gx = 0.25; gx < 0.75; gx += 0.01) {{
        const x = Math.round(r.left + gx * r.width), y = Math.round(r.top + gy * r.height);
        if (document.elementFromPoint(x, y) !== v.renderer.domElement) continue;
        const h = v.pick(x, y);
        if (h?.face?.normal && h.face.normal[2] > 0.99) return [x - Math.floor(r.left + r.width / 2), y - Math.floor(r.top + r.height / 2)];
      }} return null;""")
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *pt).click().perform()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.8)
    print("part see-through:", js(f"return [{M}.view.material.transparent, {M}.view.material.opacity]"),
          "| part edges as references:", js(f"return {SK}.refs().lines.length"), "lines,", js(f"return {SK}.refs().points.length"), "corners")

    # a circle away from the origin
    tool("circle")
    click_uv((5, 2))
    click_uv((7, 2))
    print("circle centre", centre(), "| labels", labels())

    # hovering shows what a dimension would attach to (and the origin is always marked)
    tool("dim")
    for what, uv in (("top edge", (-12, 10)), ("corner", (20, 10)), ("origin", (0, 0)), ("circle", (7, 2))):
        ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *off(uv)).perform()
        time.sleep(0.3)
        print(f"hover {what}:", js("return document.querySelector('.sk-label.hover')?.textContent"))
    d.save_screenshot(f"{OUT}/d0_hover.png")

    # ↔ Dimension: circle -> top edge of the plate (v = 10 in this face's sketch), type 6
    r = js(f"return {SK}.f.entities.find(e => e.t === 'circle').r")
    click_uv((5 + r, 2))
    print("first pick:", js(f"return {SK}.dimA?.kind"), "| hint", js("return document.querySelector('.m-hint').textContent"))
    click_uv((-12, 10))
    wait("return document.querySelector('.sk-input')")
    print("input opened with the distance it has now:", js("return document.querySelector('.sk-input')?.value"))
    type_open_input(6)
    print("6 below the top edge:", centre(), "| dims", js(f"return {SK}.f.dims.map(d => [d.t, d.a, d.b, d.v])"))

    # circle -> right edge (u = 20), type 8
    click_uv((centre()[0] + r, centre()[1]))
    click_uv((20, -6))
    type_open_input(8)
    c = centre()
    print("8 from the right edge:", c, "| expected [12, 4]")
    print("labels (no automatic x / y):", labels())
    d.save_screenshot(f"{OUT}/d1_dims.png")

    # two points -> the chooser: circle centre -> a corner of the part
    click_uv((c[0] - r, c[1]))
    click_uv((-20, -10))
    print("chooser:", js("return [...document.querySelectorAll('.sk-choose button')].map(b => b.textContent)"))
    d.find_element(By.CSS_SELECTOR, ".sk-choose button").click()  # along x
    time.sleep(0.6)
    conflict = js("return [...document.querySelectorAll('.toast')].map(t => t.textContent).pop()")
    print("a third distance along x conflicts with the 8 from the right:", "conflict" in (conflict or "").lower() or "does not fit" in (conflict or ""), "|", conflict)
    js("document.querySelector('.sk-input')?.remove()")

    # ✕ deletes the dimension to the top edge -> the circle is free in y again
    n0 = js(f"return {SK}.f.dims.length")
    el = next(e for e in d.find_elements(By.CSS_SELECTOR, ".sk-label.dist") if "↕" in e.text)
    el.find_element(By.CSS_SELECTOR, ".sk-del").click()
    time.sleep(0.6)
    print("✕ on ↕ 6:", n0, "->", js(f"return {SK}.f.dims.length"), "| panel list", js("return [...document.querySelectorAll('.sk-dim span')].map(s => s.textContent)"))

    # 🔒 -> 🔓: the ↔ 8 only measures now; 🔓 -> 🔒 locks it again at the value it has
    el = next(e for e in d.find_elements(By.CSS_SELECTOR, ".sk-label.dist") if "↔" in e.text)
    el.find_element(By.CSS_SELECTOR, ".sk-lock").click()
    time.sleep(0.6)
    print("↔ 8 freed:", js(f"return {SK}.f.dims.map(d => [d.t, d.v, !!d.free])"), "| label", js("return [...document.querySelectorAll('.sk-label.dist')].map(l => l.textContent)"))
    el = next(e for e in d.find_elements(By.CSS_SELECTOR, ".sk-label.dist") if "↔" in e.text)
    el.find_element(By.CSS_SELECTOR, ".sk-lock").click()
    time.sleep(0.6)
    print("locked again:", js(f"return {SK}.f.dims.map(d => [d.t, d.v, !!d.free])"))

    # ✕ on the circle's own size (Ø) hides it; ↔ Dimension on the circle twice brings it back, locked
    el = next(e for e in d.find_elements(By.CSS_SELECTOR, ".sk-label.edit") if e.text.startswith("Ø"))
    el.find_element(By.CSS_SELECTOR, ".sk-del").click()
    time.sleep(0.6)
    print("Ø hidden:", not any(e.text.startswith("Ø") for e in d.find_elements(By.CSS_SELECTOR, ".sk-label.edit")),
          "| show button:", js("return document.querySelector('#modelRight [data-a=showSizes]')?.textContent"))
    c = centre()
    click_uv((c[0] - r, c[1]))
    click_uv((c[0], c[1] - r))
    wait("return document.querySelector('.sk-input')")
    d.find_element(By.CSS_SELECTOR, ".sk-input").send_keys(Keys.CONTROL, "a")
    d.find_element(By.CSS_SELECTOR, ".sk-input").send_keys("5", Keys.ENTER)
    time.sleep(0.6)
    print("circle twice -> Ø back and locked at 5:", js(f"return [{SK}.f.dims.find(d => d.t === 'dia'), 2 * {SK}.f.entities.find(e => e.t === 'circle').r]"))
    r = js(f"return {SK}.f.entities.find(e => e.t === 'circle').r")

    # finish and cut through: the hole is where the dimensions put it
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=finish]").click()
    wait(f"return {M}.cmd && !{M}.inflight")
    d.find_element(By.CSS_SELECTOR, "#modelRight input[data-k=through]").click()
    time.sleep(0.4)
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=ok]").click()
    wait(f"return !{M}.cmd && !{M}.inflight")
    time.sleep(0.5)
    vol = js(f"return {M}.result.body.volume")
    print(f"volume {vol:.3f} expected {40 * 20 * 10 - math.pi * r * r * 10:.3f} | part opaque again:", js(f"return {M}.view.material.opacity"))

    # Quick part: a drawing's own dimension can be hidden (✕ on its label) and shown again (Show)
    js("document.getElementById('sampleBtn').click()")
    wait("return window.__app.state.solution && !document.body.classList.contains('ws-model')")
    time.sleep(1.2)
    n_labels = js("return document.querySelectorAll('.dim-label').length")
    lab = d.find_elements(By.CSS_SELECTOR, ".dim-label.drawing")[0]
    ActionChains(d).move_to_element(lab).perform()
    time.sleep(0.2)
    lab.find_element(By.CSS_SELECTOR, ".dim-x").click()
    time.sleep(0.8)
    print("drawing dimension hidden:", n_labels, "->", js("return document.querySelectorAll('.dim-label').length"),
          "| group", js("return [...document.querySelectorAll('.param-group')].map(g => g.textContent)"))
    d.find_element(By.CSS_SELECTOR, ".show-dim").click()
    time.sleep(0.8)
    print("shown again:", js("return document.querySelectorAll('.dim-label').length") == n_labels)
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
