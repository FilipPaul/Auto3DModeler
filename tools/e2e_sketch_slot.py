"""⊂⊃ Slot in a sketch, with REAL mouse input: a new model's sketch -> ⊂⊃ Slot: a click at (0, 0), one at (30, 0) (the
centres of its ends), the mouse out to 5 from the middle line: the preview "40 × 10" -> a click: a slot of two lines
and two arcs, kept a slot (tangent sides, equal ends, level) -> ✓ Finish sketch, ⬆ Extrude 5: its volume
(30 · 10 + π 5²) · 5, its size 40 × 10.

  PYTHONIOENCODING=utf-8 py tools/e2e_sketch_slot.py http://127.0.0.1:5199 <out dir>
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


def move_uv(uv):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *off(uv)).perform()
    time.sleep(0.15)


def click_uv(uv):
    move_uv(uv)
    ActionChains(d).click().perform()
    time.sleep(0.35)


def tool(t):
    d.find_element(By.CSS_SELECTOR, f".m-cmdbar [data-a={t}], #modelViewport .view-actions [data-a={t}]").click()
    time.sleep(0.25)


try:
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "newModelBtn").click()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.6)
    tool("slot")
    print("⊂⊃ Slot on:", "on" in d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=slot]").get_attribute("class"), "| group:", "g-make" in d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=slot]").get_attribute("class"))
    click_uv((0, 0))
    click_uv((30, 0))
    move_uv((15, 5.3))
    print("the preview:", js("return [...document.querySelectorAll('#modelViewport *')].map(e => e.childElementCount ? '' : e.textContent).find(s => /\\d+ × \\d+/.test(s)) || null"))
    click_uv((15, 5))
    es = js(f"return {SK}.f.entities.map(e => e.t)")
    ks = js(f"return {SK}.f.constraints.map(k => k.t)")
    print("drawn:", sorted(es), "| kept a slot by:", sorted(ks))
    tool("finish")
    wait(f"return {M}.mode === 'part'")
    tool("extrude")
    time.sleep(0.4)
    el = d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=d]")
    el.clear()
    el.send_keys("5\n")
    time.sleep(0.5)
    for b in d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=ok]"):  # (Enter may have done it)
        b.click()
    wait(f"return {M}.result?.body && !{M}.building")
    time.sleep(0.8)
    w = js(f"const b = {M}.result.body.bbox; return [b[3] - b[0], b[4] - b[1]]")
    r = w[1] / 2
    print("extruded 5:", round(js(f"return {M}.result.body.volume"), 1), "| expected", round((30 * 2 * r + math.pi * r * r) * 5, 1), "| size", [round(v, 2) for v in w])
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
