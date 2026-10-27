"""Sketch relations, with REAL mouse input in headless Edge: two loose lines -> ⟂ Relations ▾ Parallel: click both ->
the second turns parallel -> Equal: both -> the same length -> their symbols show by the lines and in the panel ->
Perpendicular on top of Parallel is refused (it says which relation is in the way) -> a click on a symbol removes the
relation; two circles -> Concentric; a line -> Tangent to a circle.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_model_relations.py http://127.0.0.1:5199 <out dir>
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


def click(uv):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *off(uv)).perform()
    time.sleep(0.15)
    ActionChains(d).click().perform()
    time.sleep(0.45)


def tool(t):
    d.find_element(By.CSS_SELECTOR, f".m-cmdbar [data-a={t}], #modelViewport .view-actions [data-a={t}]").click()
    time.sleep(0.2)


def relation(kind):
    d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=relate]").click()
    time.sleep(0.2)
    d.find_element(By.CSS_SELECTOR, f".m-cmdbar [data-rel={kind}]").click()
    time.sleep(0.3)


def esc():
    d.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    time.sleep(0.2)


def P(k):
    return js(f"return {SK}.P(arguments[0])", k)


def toast():
    return js("return [...document.querySelectorAll('.toast')].map(t => t.textContent).slice(-1)[0]")


try:
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "newModelBtn").click()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.8)
    js(f"{M}.view.lookAt({M}.frame(), 90); {SK}.draw()")
    time.sleep(0.3)
    tool("line")
    click((0, 0))
    click((30, 0))
    esc()
    click((0, 10))
    click((20, 17))
    esc()
    lines = js(f"return {SK}.f.entities.filter(e => e.t === 'line').map(e => [e.id, e.a, e.b])")
    print("lines:", lines)

    relation("par")
    print("hint:", js("return document.querySelector('#modelViewport .m-hint').textContent"))
    click((15, 0))
    click((10, 13.5))
    time.sleep(0.6)
    (_, a1, b1), (_, a2, b2) = lines
    u = [P(b1)[0] - P(a1)[0], P(b1)[1] - P(a1)[1]]
    v = [P(b2)[0] - P(a2)[0], P(b2)[1] - P(a2)[1]]
    print("parallel:", abs(u[0] * v[1] - u[1] * v[0]) < 1e-6, "| second line now", P(a2), P(b2))

    relation("eq")
    click((15, 0))
    m2 = [(P(a2)[0] + P(b2)[0]) / 2, (P(a2)[1] + P(b2)[1]) / 2]
    click(m2)
    time.sleep(0.6)
    L1 = math.dist(P(a1), P(b1))
    L2 = math.dist(P(a2), P(b2))
    print("equal:", round(L1, 4), round(L2, 4))
    print("symbols:", [e.text for e in d.find_elements(By.CSS_SELECTOR, ".sk-rel")], "| panel:", [e.text for e in d.find_elements(By.CSS_SELECTOR, "#modelRight .sk-dim span:first-child") if any(c in e.text for c in "∥=⟂◎⌒")])

    relation("perp")
    click((15, 0))
    m2 = [(P(a2)[0] + P(b2)[0]) / 2, (P(a2)[1] + P(b2)[1]) / 2]
    click(m2)
    time.sleep(0.6)
    print("perpendicular on top of parallel:", toast(), "| relations", js(f"return {SK}.f.constraints.filter(k => k.user).map(k => k.t)"), "| picks", js(f"return {SK}.relPicks"))
    d.save_screenshot(f"{OUT}/rel1.png")

    # a click on the ∥ symbol removes it
    esc()
    tool("select")
    sym = next(e for e in d.find_elements(By.CSS_SELECTOR, ".sk-rel") if e.text == "∥")
    sym.click()
    time.sleep(0.6)
    print("after clicking ∥:", [e.text for e in d.find_elements(By.CSS_SELECTOR, ".sk-rel")])

    # circles: concentric; a line tangent to a circle
    tool("circle")
    click((-25, 20))
    click((-20, 20))
    click((-12, 25))
    click((-10, 25))
    relation("conc")
    click((-20, 20))
    click((-10, 25))
    time.sleep(0.6)
    cs = js(f"return {SK}.f.entities.filter(e => e.t === 'circle').map(e => {SK}.P(e.c).map(v => +v.toFixed(4)))")
    print("concentric centres:", cs)
    relation("tang")
    click((15, 0))  # the first line
    click((cs[0][0] + 5, cs[0][1]))  # the bigger circle's edge
    time.sleep(0.6)
    c = js(f"return (() => {{ const c = {SK}.f.entities.find(e => e.t === 'circle'); return [{SK}.P(c.c), c.r]; }})()")
    pa, pb = P(a1), P(b1)
    dist = abs((pb[0] - pa[0]) * (pa[1] - c[0][1]) - (pa[0] - c[0][0]) * (pb[1] - pa[1])) / math.dist(pa, pb)
    print("tangent: distance from the centre to the line", round(dist, 4), "= r", round(c[1], 4))
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
