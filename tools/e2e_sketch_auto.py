"""Snapping to the part and 🪄 Auto-dimension, with REAL mouse input in headless Edge: a plate with a Ø8 hole -> a sketch
on its top with a free rectangle -> the hole shows dashed with its centre -> the circle tool: a click near the hole's
centre snaps onto it, a click near its rim snaps to it (the same Ø8) -> 🪄 Auto-dimension: the sketch fully defined, the
circle placed from the plate's nearest edges, the rectangle from the edges nearest it.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_sketch_auto.py http://127.0.0.1:5199 <out dir>
"""
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
H = "window.__app.agentHandlers"


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


def off(uv):
    return js(f"""const m = {M}, v = m.view, f = m.frame(), [u, w] = arguments[0];
      const y = [f.n[1]*f.x[2]-f.n[2]*f.x[1], f.n[2]*f.x[0]-f.n[0]*f.x[2], f.n[0]*f.x[1]-f.n[1]*f.x[0]];
      const p = new (v.camera.position.constructor)(f.o[0] + u*f.x[0] + w*y[0], f.o[1] + u*f.x[1] + w*y[1], f.o[2] + u*f.x[2] + w*y[2]);
      const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(uv))


def click(uv):
    ActionChains(d, duration=30).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, "#modelViewport canvas"), *off(uv)).perform()
    time.sleep(0.15)
    ActionChains(d).click().perform()
    time.sleep(0.5)


def tool(t):
    d.find_element(By.CSS_SELECTOR, f".m-cmdbar [data-a={t}], #modelViewport .view-actions [data-a={t}]").click()
    time.sleep(0.3)


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("add_feature", type="hole", face="F2:end", points=[[-15, -10]], d=8)
    call("add_feature", type="sketch", plane={"face": "F2:end"}, shapes=[{"rect": {"x": 5, "y": 2, "w": 12, "h": 8}}])
    wait(f"return !!{M}.result?.body && !{M}.inflight")
    js(f"{M}.edit('F4')")
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.6)
    js(f"{SK}.f.dims = []; {SK}.changed()")  # a free rectangle (no sizes locked)
    js(f"{M}.view.lookAt({M}.frame(), 80); {SK}.draw()")
    time.sleep(0.5)
    print("the part's round edges on the sketch:", js(f"return {SK}.refs().circles"))

    hc = js(f"return {SK}.refs().circles[0].c")
    tool("circle")
    click((hc[0] + 0.25, hc[1] - 0.2))  # near the hole's centre
    click((hc[0] + 3.85, hc[1] + 0.9))  # near its rim
    time.sleep(0.4)
    c = js(f"return (() => {{ const e = {SK}.f.entities.filter(x => x.t === 'circle').pop(); return [{SK}.P(e.c), e.r]; }})()")
    print("circle drawn on the hole: centre", [round(v, 4) for v in c[0]], "r", round(c[1], 4), "(the hole:", hc, "r 4)")
    d.save_screenshot(f"{OUT}/auto1.png")
    js(f"{SK}.setTool('select')")
    time.sleep(0.2)
    print("free before:", js(f"return {SK}.solve().then(r => r.dof)"))
    tool("autodim")
    wait("return [...document.querySelectorAll('.toast')].some(t => /size\\(s\\) locked|fully defined/.test(t.textContent))", 60)
    time.sleep(0.5)
    print("toast:", js("return [...document.querySelectorAll('.toast')].map(t => t.textContent).slice(-1)[0]"))
    print("free after:", js(f"return {SK}.solve().then(r => r.dof)"))
    dims = js(f"return {SK}.f.dims.map(x => [x.t, typeof x.a === 'object' ? (x.a.edge ? 'part edge' : 'ref') : x.a, x.b || x.e, +(+x.v).toFixed(3)])")
    print("locked:", dims)
    d.save_screenshot(f"{OUT}/auto2.png")
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=finish]").click()
    wait(f"return {M}.mode === 'part' && !{M}.inflight")
    print("the model builds:", js(f"return {M}.result.ok"), "| sketch steps", js(f"return {M}.part.features.length"))
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
