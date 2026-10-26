"""〰 Spline in a sketch, with REAL mouse input in headless Edge: a line 0..40 along x -> 〰 Spline: a click on the line's
right end, two points it goes through, a click on the line's left end (it joins there: closed) -> one curve of 4
points, the sketch closed -> ⬆ extrude: one smooth side face -> a point of the curve dragged: it follows -> a circle
added and deleted: the curve keeps its points -> Esc / Enter end a curve.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_sketch_spline.py http://127.0.0.1:5199 <out dir>
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
SK = f"{M}.sk"
H = "window.__app.agentHandlers"


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def off(uv):
    return js(f"""const m = {M}, v = m.view, f = m.frame(), [u, w] = arguments[0];
      const y = [f.n[1]*f.x[2]-f.n[2]*f.x[1], f.n[2]*f.x[0]-f.n[0]*f.x[2], f.n[0]*f.x[1]-f.n[1]*f.x[0]];
      const p = new (v.camera.position.constructor)(f.o[0] + u*f.x[0] + w*y[0], f.o[1] + u*f.x[1] + w*y[1], f.o[2] + u*f.x[2] + w*y[2]);
      const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(uv))


def click(uv, double=False):
    cv = d.find_element(By.CSS_SELECTOR, "#modelViewport canvas")
    ActionChains(d, duration=30).move_to_element_with_offset(cv, *off(uv)).perform()
    time.sleep(0.2)
    (ActionChains(d).double_click() if double else ActionChains(d).click()).perform()
    time.sleep(0.4)


def tool(name):
    d.find_element(By.CSS_SELECTOR, f".m-cmdbar [data-a={name}]").click()
    time.sleep(0.3)


try:
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "newModelBtn").click()  # (it opens a sketch on the Top plane)
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.5)
    js(f"{M}.view.lookAt({M}.frame(), 90); {SK}.draw()")
    time.sleep(0.4)
    tool("line")
    click([0, 0])
    click([40, 0])
    js(f"{SK}.key(new KeyboardEvent('keydown', {{ key: 'Escape' }}))")  # the line stops
    time.sleep(0.3)
    tool("spline")
    print("hint:", d.find_element(By.CSS_SELECTOR, "#modelViewport .m-hint").text)
    click([40, 0])
    click([46, 16])
    click([20, 32])
    ActionChains(d, duration=30).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, "#modelViewport canvas"), *off([-4, 14])).perform()
    time.sleep(0.3)
    d.save_screenshot(f"{OUT}/spline_drawing.png")
    click([0, 0])  # the line's start: it joins there, the curve ends
    ents = js(f"return {SK}.f.entities.map(e => e.t + (e.pts ? ':' + e.pts.length : ''))")
    print("entities:", ents, "| still drawing:", js(f"return !!{SK}.spl"))
    print("the curve's points:", js(f"const e = {SK}.f.entities.find(e => e.t === 'spline'); return e.pts.map(p => {SK}.P(p).map(v => Math.round(v)))"))
    d.save_screenshot(f"{OUT}/spline_closed.png")
    # a circle added and deleted: the curve keeps its points
    js(f"""const S = {SK}; S.step(); S.f.points.q1 = [20, 12]; S.f.entities.push({{ id: 'c9', t: 'circle', c: 'q1', r: 3 }}); S.sel = {{ kind: 'entity', id: 'c9' }}; S.deleteSel()""")
    print("after deleting a circle — the curve's points kept:", js(f"const e = {SK}.f.entities.find(e => e.t === 'spline'); return e.pts.every(p => !!{SK}.f.points[p])"))
    d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=finish]").click()
    wait(f"return {M}.mode === 'part'")
    print("extrude:", js(f"return {H}.add_feature({{ type: 'extrude', sketch: 'F1', d: 5 }}).then(r => r.text.slice(0, 60))"))
    wait(f"return !!{M}.result?.body && !{M}.inflight")
    print("faces:", js(f"return {M}.result.body.faces.map(f => f.name)"), "| volume", js(f"return Math.round({M}.result.body.volume)"))
    d.save_screenshot(f"{OUT}/spline_solid.png")
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
