"""What a sketch click can take, with REAL mouse input: a rectangle and a circle -> the selection filters at the bottom of
the view -> "Lines" off: a click on a line takes nothing, on again -> the origin picked: its suggestions -> a line's
midpoint and the circle (Ctrl+click): the distance between them, kept by the solver at the middle -> a locked
dimension dragged by its line (not its label) -> the circle's size shown as R (⇄), 5 typed: Ø 10.

  PYTHONIOENCODING=utf-8 py tools/e2e_sketch_pick.py http://127.0.0.1:5199 <out dir>
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


def click_uv(uv, ctrl=False):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *off(uv)).perform()
    time.sleep(0.12)
    ch = ActionChains(d)
    (ch.key_down(Keys.CONTROL).click().key_up(Keys.CONTROL) if ctrl else ch.click()).perform()
    time.sleep(0.4)


def tool(t):
    d.find_element(By.CSS_SELECTOR, f".m-cmdbar [data-a={t}], #modelViewport .view-actions [data-a={t}]").click()
    time.sleep(0.25)


def table():
    box = d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest")
    return [box[0].find_element(By.CSS_SELECTOR, ".vs-head b").text] + [b.text.replace("\n", " ") for b in box[0].find_elements(By.CSS_SELECTOR, ".vs-list button")] if box else None


def press(label):
    next(b for b in d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-list button") if label in b.text).click()
    time.sleep(0.9)


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('a3d.skpick')")
    d.find_element(By.ID, "newModelBtn").click()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.6)
    click_uv((10, 10))
    click_uv((50, 30))
    tool("circle")
    click_uv((70, 20))
    click_uv((74, 20))
    tool("select")
    bar = d.find_element(By.CSS_SELECTOR, "#modelViewport .sk-filters")
    vp = d.find_element(By.CSS_SELECTOR, "#modelViewport").rect
    print("the filters:", bar.text.replace("\n", " | "), "| at the bottom middle:", abs(bar.rect["x"] + bar.rect["width"] / 2 - (vp["x"] + vp["width"] / 2)) < 20)
    bar.find_element(By.CSS_SELECTOR, "[data-f=lines]").click()
    time.sleep(0.3)
    click_uv((20, 30))  # the top line, not its middle
    print("Lines off — a click on a line:", table())
    d.find_element(By.CSS_SELECTOR, "#modelViewport .sk-filters [data-f=lines]").click()
    time.sleep(0.3)
    click_uv((0, 0))
    print("the origin:", table())
    click_uv((30, 30))   # the top line's middle …
    click_uv((74, 20), ctrl=True)  # … and the circle
    print("a midpoint + the circle:", table())
    press("distance")
    js("document.querySelector('.sk-choose button')?.click()")  # (along x / y / straight: the first)
    time.sleep(1.2)
    inp = d.find_elements(By.CSS_SELECTOR, ".sk-input")
    if inp:
        inp[0].send_keys(Keys.CONTROL, "a")
        inp[0].send_keys("40", Keys.ENTER)
        time.sleep(1.2)
    dm = js(f"const x = {SK}.f.dims.find(x => x.a?.mid || x.b?.mid); return x ? [x.t, JSON.stringify(x.a), JSON.stringify(x.b), +{SK}.measure(x).toFixed(3), +x.v.toFixed(3)] : null")
    print("  the dimension from the middle:", dm)
    # a locked dimension dragged by its line (a point on it away from its label)
    key = js(f"const x = {SK}.f.dims.find(x => x.a?.mid || x.b?.mid); return x && x.id")
    hit = js(f"const h = ({SK}.dimHits || []).find(h => h.key === arguments[0]); return h ? [h.a[0] + (h.b[0] - h.a[0]) * 0.15, h.a[1] + (h.b[1] - h.a[1]) * 0.15] : null", key)
    if hit:
        before = js(f"return {SK}.f.place?.[arguments[0]] ?? 0", key)
        ActionChains(d, duration=40).move_to_element_with_offset(canvas(), *off(hit)).click_and_hold().move_by_offset(0, 15).move_by_offset(0, 15).release().perform()
        time.sleep(0.8)
        print("dragged by its line:", round(before, 2), "->", round(js(f"return {SK}.f.place?.[arguments[0]] ?? 0", key), 2), "| the shapes did not move:",
              js(f"return {SK}.f.points[{SK}.f.entities[0].a].map(v => +v.toFixed(2))"))
    else:
        print("no line to grab for", key)
    # the circle shown as R, its radius typed
    click_uv((74, 20))
    print("the circle:", table())
    press("radius")
    print("  shown as R:", js("return [...document.querySelectorAll('.sk-label.edit .sk-val')].map(v => v.textContent).filter(t => /^[RØ]/.test(t))"))
    lab = next(e for e in d.find_elements(By.CSS_SELECTOR, ".sk-label.edit .sk-val") if e.text.startswith("R"))
    lab.click()
    time.sleep(0.3)
    inp = d.find_element(By.CSS_SELECTOR, ".sk-input")
    print("  its box shows the radius:", inp.get_attribute("value"))
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys("5", Keys.ENTER)
    time.sleep(1.2)
    print("  5 typed: its Ø", js(f"return 2 * {SK}.f.entities.find(e => e.t === 'circle').r"), "| locked as", js(f"return {SK}.f.dims.filter(x => x.t === 'dia').map(x => x.v)"))
    d.save_screenshot(f"{OUT}/sketch_pick.png")
    # drawing onto a line that is off the grid: its middle, then a place along it (the points stay there)
    d.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    js(f"const s = {SK}; s.f.points.q1 = [52.13, -20.37]; s.f.points.q2 = [75.5, -2.72]; s.f.entities.push({{ id: 'lq', t: 'line', a: 'q1', b: 'q2' }}); s.changed()")
    time.sleep(0.6)
    tool("line")
    sl = js(f"const e = {SK}.ent('lq'); return [e.id, {SK}.P(e.a), {SK}.P(e.b)]")
    lid, a0, b0 = sl
    mid = [(a0[0] + b0[0]) / 2, (a0[1] + b0[1]) / 2]
    along = [a0[0] + (b0[0] - a0[0]) * 0.8, a0[1] + (b0[1] - a0[1]) * 0.8]
    print("an off-grid line:", [round(v, 2) for v in a0 + b0])
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *off([mid[0] + 0.3, mid[1] - 0.4])).perform()
    time.sleep(0.4)
    print("  the mouse near its middle:", js(f"return [{SK}.hover?.mid || null, JSON.stringify({SK}.cursor?.uv)]"), "| shown:",
          js("return [...document.querySelectorAll('.sk-label')].map(l => l.textContent).find(t => t.includes('midpoint') || t.includes('střed'))"))
    click_uv([mid[0] + 0.3, mid[1] - 0.4])
    click_uv([along[0] - 0.3, along[1] + 0.4])
    d.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    time.sleep(1)
    new = js(f"const e = {SK}.f.entities.filter(x => x.t === 'line').slice(-1)[0]; return [{SK}.P(e.a), {SK}.P(e.b), {SK}.f.constraints.filter(k => k.p === e.a || k.p === e.b).map(k => k.t + ':' + k.e)]")
    pa, pb, ks = new
    cross = lambda p: abs((b0[0] - a0[0]) * (p[1] - a0[1]) - (b0[1] - a0[1]) * (p[0] - a0[0])) / math.dist(a0, b0)
    print("  a line from its middle to a place on it: rules", ks, "| at the middle:", round(math.dist(pa, mid), 4), "| on the line:", round(cross(pb), 4))
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
