"""✂ Trim in a sketch, with REAL mouse input in headless Edge: a 40 x 30 rectangle and a Ø10 circle on its right edge
-> ✂ Trim: hover shows the piece in red -> click the circle's inner half (it becomes an arc: Ø10 -> R5) -> click the
edge between the crossings (the edge splits in two) -> Finish -> Extrude: a rectangle with a round tab, exact
volume; the circle's size typed later: the trimmed ends stay on it; a line with no crossings is removed whole.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_model_trim.py http://127.0.0.1:5199 <out dir>
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


def ents():
    return js(f"return {SK}.f.entities.map(e => e.t + ':' + e.id)")


try:
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "newModelBtn").click()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.8)
    js(f"{M}.view.lookAt({M}.frame(), 110); {SK}.draw()")  # room for the circle beside the rectangle
    time.sleep(0.4)
    click((0, 0))
    click((40, 30))
    tool("circle")
    click((40, 8))
    click((45, 8))
    print("drawn:", ents())

    tool("trim")
    move((40 + 5 * math.cos(math.radians(200)), 8 + 5 * math.sin(math.radians(200))))  # the circle's inner half
    print("hover:", js("return document.querySelector('.sk-label.hover')?.textContent"), "| piece points:", len(js(f"return {SK}.hover?.pts || []")))
    ActionChains(d).click().perform()
    time.sleep(0.8)
    print("circle trimmed ->", ents(), "| dims", js(f"return {SK}.f.dims.map(x => x.t + ' ' + x.v)"))
    click((40, 8))  # the edge inside the circle
    print("edge trimmed ->", ents(), "| on-constraints", js(f"return {SK}.f.constraints.filter(k => k.t === 'on').length"))
    d.save_screenshot(f"{OUT}/trim1.png")

    # the circle's radius typed: the trimmed ends follow it
    lab = next(el for el in d.find_elements(By.CSS_SELECTOR, ".sk-label.edit") if el.find_element(By.CSS_SELECTOR, ".sk-val").text.startswith("R"))
    lab.find_element(By.CSS_SELECTOR, ".sk-val").click()
    time.sleep(0.2)
    inp = d.find_element(By.CSS_SELECTOR, ".sk-input")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys("6", Keys.ENTER)
    time.sleep(0.8)
    ends = js(f"""const s = {SK}, a = s.f.entities.find(e => e.t === 'arc'); return [s.P(a.a), s.P(a.b), s.P(a.c)].map(p => p.map(v => +v.toFixed(4)))""")
    print("R6: arc ends", ends[:2], "centre", ends[2], "| on the edge x = 40:", all(abs(p[0] - 40) < 1e-4 for p in ends[:2]))

    tool("finish")
    settled()
    btns = d.find_elements(By.CSS_SELECTOR, "#modelRight [data-a=ok]")
    if btns:
        btns[0].click()
    settled()
    b = js(f"return {M}.result.body")
    h = js(f"return {M}.part.features.find(f => f.type === 'extrude').d")
    print("extruded:", round(b["volume"], 4), "| expected", round((1200 + math.pi * 36 / 2) * h, 4), "| ok", js(f"return {M}.result.ok"))

    # a lone line: trimmed away whole
    d.find_element(By.ID, "newModelBtn").click()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.8)
    tool("line")
    click((0, 0))
    click((20, 0))
    d.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    tool("trim")
    click((10, 0))
    print("lone line trimmed:", ents())
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
