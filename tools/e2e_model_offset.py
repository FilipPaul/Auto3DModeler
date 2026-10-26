"""⧈ Offset in a sketch, with REAL mouse input in headless Edge: a 40 x 20 rectangle -> ⧈ Offset: hover shows the whole
outline -> click it -> type 3 -> a 46 x 26 copy around it (sharp corners) -> Finish -> Extrude: a frame, exact
volume; a circle offset inwards (-2) -> a ring; a rounded rectangle offset 2 -> its arcs stay concentric (tangent
joins); a picture outline (block) offset through the server.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_model_offset.py http://127.0.0.1:5199 <out dir>
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


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#modelViewport canvas")


def off(uv):
    return js(f"""const m = {M}, v = m.view, f = m.frame(), [u, w] = arguments[0];
      const y = [f.n[1]*f.x[2]-f.n[2]*f.x[1], f.n[2]*f.x[0]-f.n[0]*f.x[2], f.n[0]*f.x[1]-f.n[1]*f.x[0]];
      const p = new (v.camera.position.constructor)(f.o[0] + u*f.x[0] + w*y[0], f.o[1] + u*f.x[1] + w*y[1], f.o[2] + u*f.x[2] + w*y[2]);
      const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(uv))


def move(uv):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *off(uv)).perform()
    time.sleep(0.2)


def click(uv):
    move(uv)
    ActionChains(d).click().perform()
    time.sleep(0.5)


def tool(t):
    d.find_element(By.CSS_SELECTOR, f".m-cmdbar [data-a={t}]").click()
    time.sleep(0.2)


def offset_by(uv, dist):
    click(uv)
    inp = wait("return document.querySelector('.sk-choose input')")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys(str(dist), Keys.ENTER)
    time.sleep(0.9)


def new_sketch():
    d.find_element(By.ID, "newModelBtn").click()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.8)
    js(f"{M}.view.lookAt({M}.frame(), 110); {SK}.draw()")
    time.sleep(0.4)


def extrude_volume():
    tool("finish")
    settled()
    b = d.find_elements(By.CSS_SELECTOR, "#modelRight [data-a=ok]")
    if b:
        b[0].click()
    settled()
    return js(f"return {M}.result.body?.volume"), js(f"return {M}.part.features.find(f => f.type === 'extrude')?.d"), js(f"return {M}.result.ok")


try:
    d.get(URL)
    wait("return !!window.__app")
    new_sketch()
    click((0, 0))
    click((40, 20))
    tool("offset")
    move((20, 0))
    print("hover: loop of", len(js(f"return {SK}.hover?.loop || []")), "| hint", js("return document.querySelector('#modelViewport .m-hint').textContent")[:30])
    offset_by((20, 0), 3)
    pts = js(f"return Object.values({SK}.f.points)")
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    print("offset 3:", len(js(f"return {SK}.f.entities")), "lines | spans x", min(xs), max(xs), "y", min(ys), max(ys))
    d.save_screenshot(f"{OUT}/offset1.png")
    v, h, ok = extrude_volume()
    print("frame extruded:", round(v, 4), "| expected", round((46 * 26 - 40 * 20) * h, 4), ok)

    # a circle offset inwards: a ring
    new_sketch()
    tool("circle")
    click((0, 0))
    click((10, 0))
    tool("offset")
    offset_by((10, 0), -2)
    print("circles:", js(f"return {SK}.f.entities.map(e => e.t + ' r' + e.r)"))
    v, h, ok = extrude_volume()
    print("ring:", round(v, 4), "| expected", round(math.pi * (100 - 64) * h, 4), ok)

    # a rounded rectangle (◜ Round corner on all four) offset 2: tangent joins, concentric arcs
    new_sketch()
    click((0, 0))
    click((40, 20))
    tool("round")
    for c in ((0, 0), (40, 0), (40, 20), (0, 20)):
        click(c)
        inp = wait("return document.querySelector('.sk-input')")
        inp.send_keys(Keys.CONTROL, "a")
        inp.send_keys("5", Keys.ENTER)
        time.sleep(0.8)
    tool("offset")
    offset_by((20, 0), 2)
    arcs = js(f"return {SK}.f.entities.filter(e => e.t === 'arc').map(e => +{SK}.arcR(e).toFixed(4))")
    print("rounded rectangle offset: arcs", sorted(arcs))
    v, h, ok = extrude_volume()
    inner = 40 * 20 - (4 - math.pi) * 25
    outer = 44 * 24 - (4 - math.pi) * 49
    print("rounded frame:", round(v, 4), "| expected", round((outer - inner) * h, 4), ok)

    # a picture outline (block) offset by the server
    new_sketch()
    js(f"""{SK}.addBlock({{ name: 'square', polygons: [[[[0, 0], [10, 0], [10, 10], [0, 10]]]], width: 10, height: 10 }})""")
    time.sleep(0.5)
    tool("offset")
    offset_by((5, 5), 2)
    print("blocks:", js(f"return {SK}.f.entities.filter(e => e.t === 'block').map(e => [e.name, +e.w0.toFixed(3)])"))
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
