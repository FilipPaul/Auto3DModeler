"""The sketch tells its state and dimensions smartly, with REAL mouse input: a new model's rectangle -> ✓ Finish sketch
not green, 🪄 Auto-dimension shown, its lines blue (free) -> ↔ Dimension, one click on the top line: its length in a box at once, 50 typed +
Enter -> the line is 50; its label dragged down (kept), what it measures lit up -> one click on a line, then a click on another: the distance chooser / a distance instead of
its length -> 🪄 -> every size fixed: ✓ Finish sketch green, 🪄 gone.

  PYTHONIOENCODING=utf-8 py tools/e2e_sketch_smart.py http://127.0.0.1:5199 <out dir>
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
    time.sleep(0.35)


def tool(t):
    d.find_element(By.CSS_SELECTOR, f".m-cmdbar [data-a={t}], #modelViewport .view-actions [data-a={t}]").click()
    time.sleep(0.25)


def state():
    fin = d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=finish]")
    auto = d.find_elements(By.CSS_SELECTOR, ".m-cmdbar [data-a=autodim]")
    return {"dof": js(f"return {SK}.dof"), "finish green": "done" in fin.get_attribute("class"),
            "🪄 shown": bool(auto) and auto[0].is_displayed()}


def mid(which):
    """A point on the rectangle's left / right line (away from its size label in the middle), as it is now."""
    return js(f"""const s = {SK}, ls = s.f.entities.filter(e => e.t === 'line').map(e => [s.P(e.a), s.P(e.b)]).filter(([a, b]) => Math.abs(a[0] - b[0]) < 1e-6);
      ls.sort((p, q) => p[0][0] - q[0][0]); const [a, b] = ls[arguments[0] === 'left' ? 0 : ls.length - 1]; return [(a[0] + b[0]) / 2, a[1] + (b[1] - a[1]) * 0.2];""", which)


def lens():
    return js(f"return {SK}.f.entities.filter(e => e.t === 'line').map(e => +{SK}.measure({{t: 'len', e: e.id}}).toFixed(3))")


try:
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "newModelBtn").click()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.6)
    click_uv((0, 0))
    click_uv((40, 20))
    wait(f"return {SK}.dof > 0", 10)
    time.sleep(0.6)
    print("a rectangle:", state())
    colours = lambda: js(f"return {SK}.f.entities.map(e => {SK}.stateOf(e))")  # noqa: E731
    wait(f"return !!{SK}.free", 10)
    print("  its lines:", colours(), "(blue: free)")
    tool("dim")
    click_uv((20, 20))  # the top line
    box = wait("return document.querySelector('.sk-quick input')", 5)
    print("one click on a line — its size at once:", d.find_element(By.CSS_SELECTOR, ".sk-quick").text.replace("\n", " | "))
    inp = d.find_element(By.CSS_SELECTOR, ".sk-quick input")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys("50", Keys.ENTER)
    time.sleep(1.2)
    print("  50 typed:", lens(), "| locked:", js(f"return {SK}.f.dims.map(x => [x.t, +x.v.toFixed(2)])"))
    # the locked 50: drawn as a dimension, dragged 40 px down (kept), what it measures lit up meanwhile
    lab = next(e for e in d.find_elements(By.CSS_SELECTOR, ".sk-label.movable") if e.text.startswith("50"))
    y0 = lab.rect["y"]
    ActionChains(d).move_to_element(lab).perform()
    time.sleep(0.3)
    lit = js(f"return {SK}.hoverSize?.key || null")
    lab = next(e for e in d.find_elements(By.CSS_SELECTOR, ".sk-label.movable") if e.text.startswith("50"))  # (drawn anew)
    ActionChains(d, duration=40).move_to_element_with_offset(lab, -lab.rect["width"] / 2 + 3, 0).click_and_hold().move_by_offset(0, 20).move_by_offset(0, 20).release().perform()
    time.sleep(0.6)
    lab = next(e for e in d.find_elements(By.CSS_SELECTOR, ".sk-label.movable") if e.text.startswith("50"))
    print("the 50 dragged down:", round(lab.rect["y"] - y0), "px | kept:", js(f"return {SK}.f.place"), "| lit while on it:", lit,
          "| no value box:", not js("return document.querySelector('.sk-input')"))
    d.save_screenshot(f"{OUT}/sketch_dims.png")
    click_uv(mid("left"))  # the left line …
    print("  a click on the left line: its box", bool(js("return document.querySelector('.sk-quick')")))
    click_uv(mid("right"))  # … then the right line: a distance, not a length
    time.sleep(1.0)
    print("  then the right line: box gone", not js("return document.querySelector('.sk-quick')"),
          "| dims:", js(f"return {SK}.f.dims.map(x => [x.t, +x.v.toFixed(2)])"), "| a typing box:", bool(js("return document.querySelector('.sk-input')")))
    js("document.querySelector('.sk-input')?.blur()")
    time.sleep(0.6)
    d.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    print("  before 🪄:", state())
    if state()["🪄 shown"]:
        tool("autodim")
    wait(f"return {SK}.dof === 0", 15)
    time.sleep(0.6)
    print("🪄 then:", state())
    time.sleep(0.5)
    print("  its lines:", colours(), "(green: fully defined)")
    # a dimension the others fix already (90° between two sides of the rectangle): kept as a reference, in brackets
    tool("dim")
    click_uv(mid("left"))
    click_uv((mid("right")[0] * 0.25 + mid("left")[0] * 0.75, js(f"return Math.max(...Object.values({SK}.f.points).map(p => p[1]))")))  # the top side, near the left
    time.sleep(1.0)
    ref = js(f"const x = {SK}.f.dims.find(x => x.t === 'ang'); return x ? [!!x.free, +{SK}.measure(x).toFixed(2)] : null")
    print("90° between two sides: a reference:", ref, "| its label:",
          js("return [...document.querySelectorAll('.sk-label.dist')].map(l => l.querySelector('.sk-val').textContent).find(t => t.startsWith('∠'))"),
          "| an error:", js("return [...document.querySelectorAll('.toast.error')].length"), "| still fully defined:", js(f"return {SK}.dof"))
    d.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    time.sleep(0.3)
    d.save_screenshot(f"{OUT}/sketch_smart.png")

    # a triangle: two crossing lines -> their angle; a corner and the slanted side -> its distance from it
    d.find_element(By.ID, "newModelBtn").click()
    wait(f"return {M}.mode === 'sketch' && !{SK}.f.entities.length")
    time.sleep(0.6)
    tool("line")
    for uv in ((0, 0), (40, 0), (0, 30), (0, 0)):
        click_uv(uv)
    d.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    time.sleep(0.4)
    print("the triangle:", js(f"return {SK}.f.entities.map(e => e.t + ':' + [e.a, e.b].map(p => {SK}.P(p).map(v => +v.toFixed(1))).join('>'))"))
    tool("dim")
    click_uv((30, 0))     # the bottom line, left of the right corner
    click_uv((30, 7.5))   # the slanted side, up from it
    time.sleep(0.8)
    ang = js(f"const x = {SK}.f.dims.find(x => x.t === 'ang'); return x ? [+x.v.toFixed(2), +{SK}.measure(x).toFixed(2)] : null")
    print("two crossing lines -> an angle:", ang, "(atan 30/40 = 36.87)", "| a typing box:", bool(js("return document.querySelector('.sk-input')")))
    inp = d.find_element(By.CSS_SELECTOR, ".sk-input")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys("45", Keys.ENTER)
    time.sleep(1.2)
    print("  45 typed:", js(f"const x = {SK}.f.dims.find(x => x.t === 'ang'); return +{SK}.measure(x).toFixed(3)"), "| its label:",
          js("return [...document.querySelectorAll('.sk-label.dist')].map(l => l.querySelector('.sk-val').textContent).find(t => t.startsWith('∠'))"))
    tip = js(f"const l = {SK}.f.entities.filter(e => e.t === 'line').map(e => [{SK}.P(e.a), {SK}.P(e.b)]); const sl = l.find(([a, b]) => Math.abs(a[0] - b[0]) > 1e-6 && Math.abs(a[1] - b[1]) > 1e-6); return [sl[0][0] + (sl[1][0] - sl[0][0]) * 0.75, sl[0][1] + (sl[1][1] - sl[0][1]) * 0.75]")
    click_uv((0, 0))      # the corner at the origin …
    click_uv(tip)         # … and the slanted side: the corner's distance from it
    time.sleep(0.8)
    js("document.querySelector('.sk-input')?.blur()")
    time.sleep(0.8)
    pl = js(f"const x = {SK}.f.dims.find(x => x.t === 'pl'); return x ? +{SK}.measure(x).toFixed(3) : null")
    print("a corner and a slanted line -> its distance:", pl, "| the dims:", js(f"return {SK}.f.dims.map(x => x.t)"))
    d.save_screenshot(f"{OUT}/sketch_angle.png")
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
