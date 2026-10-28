"""⁂ Pattern in a sketch, with REAL mouse input: a new model's sketch -> ◯ a circle -> ⬚ Select it -> ⁂ Pattern: the
quick box (bottom left), Count 4, Spacing 15, Enter: four circles 15 apart along X, kept equal (a ⁂ relation) ->
the ⁂ symbol clicked: Count 5 -> re-made (five) -> Ctrl+Z: four again (one step), Ctrl+Z: one, Ctrl+Y: four ->
✓ Finish sketch, ⬆ Extrude 5: the volume 4 · π r² · 5. Then around: a disc R 30, a hole R 5 at x 20 -> ⁂ Pattern,
a click on the disc (its centre), Count 6: six holes on a circle, 60° apart -> extruded: π (30² − 6 · 5²) · 5.

  PYTHONIOENCODING=utf-8 py tools/e2e_sketch_pattern.py http://127.0.0.1:5199 <out dir>
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


def typed(k, v, enter=False):
    el = d.find_element(By.CSS_SELECTOR, f".sk-pattern [data-pk={k}]")
    el.send_keys(Keys.CONTROL, "a")
    el.send_keys(v, *([Keys.ENTER] if enter else []))
    time.sleep(0.2)


def settle():
    time.sleep(0.6)
    wait(f"return !{M}.building")
    time.sleep(0.3)


def circles():
    return js(f"""const s = {SK}; return s.f.entities.filter((e) => e.t === 'circle')
      .map((e) => [+s.P(e.c)[0].toFixed(3), +s.P(e.c)[1].toFixed(3), +e.r.toFixed(3)])""")


def key(ch):
    ActionChains(d).key_down(Keys.CONTROL).send_keys(ch).key_up(Keys.CONTROL).perform()
    time.sleep(0.6)


def extrude(h):
    tool("finish")
    wait(f"return {M}.mode === 'part'")
    tool("extrude")
    time.sleep(0.4)
    el = d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=d]")
    el.clear()
    el.send_keys(f"{h}\n")
    time.sleep(0.5)
    for b in d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=ok]"):  # (Enter may have done it)
        b.click()
    wait(f"return {M}.result?.body && !{M}.building")
    time.sleep(0.8)
    return js(f"return {M}.result.body.volume")


def new_sketch():
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "newModelBtn").click()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.6)
    tool("plane-XY")


try:
    # ---- in a row: a circle -> 4, 15 apart
    new_sketch()
    tool("circle")
    click_uv((0, 0))
    click_uv((5, 0))
    r = circles()[0][2]
    tool("select")
    click_uv((r, 0))
    print("picked:", js(f"return ({SK}.picks || []).map((q) => q.kind)"))
    b = d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=pattern]")
    print("⁂ Pattern in the sketch bar:", b.is_displayed(), "| group:", "g-copy" in b.get_attribute("class"))
    b.click()
    settle()
    print("at once (live):", len(circles()), "circles | the box:", js("return !!document.querySelector('.sk-pattern.sk-quick')"),
          "| first spacing:", js("return document.querySelector('.sk-pattern [data-pk=d]')?.value"))
    typed("n", "4")
    typed("d", "15", enter=True)
    settle()
    cs = circles()
    print("4 in a row, 15 apart:", cs, "| box closed:", not js("return !!document.querySelector('.sk-pattern')"))
    print("  held by:", js(f"return {SK}.f.constraints.filter((k) => k.t === 'pat').map((k) => [k.kind, k.n, k.d])"),
          "| dof:", js(f"return {SK}.dof"))
    # the ⁂ symbol: the count changed -> re-made
    sym = [e for e in d.find_elements(By.CSS_SELECTOR, ".sk-rel") if e.text.strip() == "⁂"]
    print("the ⁂ symbol shown:", len(sym))
    sym[0].click()
    time.sleep(0.4)
    typed("n", "5", enter=True)
    settle()
    print("count 5 -> re-made:", [c[0] for c in circles()])
    key("z")
    print("Ctrl+Z:", [c[0] for c in circles()])
    key("z")
    print("Ctrl+Z:", [c[0] for c in circles()])
    key("y")
    print("Ctrl+Y:", [c[0] for c in circles()])
    v = extrude(5)
    print("extruded 5:", round(v, 2), "| expected", round(4 * math.pi * r * r * 5, 2))

    # ---- around: a disc R 30 and a hole R 5 at x 20 -> 6 around the disc's centre
    new_sketch()
    tool("circle")
    click_uv((0, 0))
    click_uv((30, 0))
    click_uv((20, 0))
    click_uv((25, 0))
    R, h = sorted(c[2] for c in circles())[::-1]
    tool("select")
    hc = [c for c in circles() if c[2] == h][0]
    click_uv((hc[0] + h * 0.7071, hc[1] + h * 0.7071))
    print("picked:", js(f"return ({SK}.picks || []).map((q) => q.kind)"))
    tool("pattern")
    settle()
    click_uv((0, R))  # the disc: around its centre
    settle()
    print("around:", js(f"return {SK}.f.constraints.filter((k) => k.t === 'pat').map((k) => [k.kind, k.n, k.c])"),
          "| box says:", js("return document.querySelector('.sk-pattern .hint')?.textContent.trim().slice(0, 40)"))
    typed("n", "6", enter=True)
    settle()
    small = sorted([c for c in circles() if abs(c[2] - h) < 1e-6], key=lambda c: math.atan2(c[1], c[0]) % (2 * math.pi))
    print("6 on a circle:", len(small), "| radii from the centre:", sorted({round(math.hypot(c[0], c[1]), 3) for c in small}),
          "| angles:", [round(math.degrees(math.atan2(c[1], c[0])) % 360, 2) for c in small])
    v = extrude(5)
    print("extruded 5:", round(v, 2), "| expected", round(math.pi * (R * R - 6 * h * h) * 5, 2))
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
