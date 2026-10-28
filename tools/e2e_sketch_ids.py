"""Every id in a sketch is unique, with REAL mouse input: a new model's sketch -> ▭ a rectangle, ◯ a circle at the
origin (its centre locked there by a ↔ dx and a ↕ dy), ⊂⊃ a slot, ⁂ a pattern of the circle, ⧈ an offset of the
rectangle -> all point / entity / relation / dimension ids differ -> ↔ Dimension twice (a corner from the slot's
centre, along x and y) -> the ✕ on one of them removes only that one. Then a sketch saved with duplicate ids (as older versions made them) opens repaired.

  PYTHONIOENCODING=utf-8 py tools/e2e_sketch_ids.py http://127.0.0.1:5199 <out dir>
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
    time.sleep(0.15)
    ActionChains(d).click().perform()
    time.sleep(0.4)


def tool(t):
    d.find_element(By.CSS_SELECTOR, f".m-cmdbar [data-a={t}], #modelViewport .view-actions [data-a={t}]").click()
    time.sleep(0.25)


def settle():
    time.sleep(0.8)
    wait(f"return !{M}.building")
    time.sleep(0.3)


def ids():
    """All ids in the sketch, by kind; and the ones used more than once (across all kinds)."""
    got = js(f"""const f = {SK}.f; return {{points: Object.keys(f.points), entities: f.entities.map((e) => e.id),
      constraints: f.constraints.map((k) => k.id), dims: f.dims.map((x) => x.id)}}""")
    every = [i for v in got.values() for i in v]
    return got, sorted({i for i in every if every.count(i) > 1})


def new_sketch():
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "newModelBtn").click()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.6)
    tool("plane-XY")
    js(f"{M}.view.lookAt({M}.frame(), 160); {SK}.draw()")
    time.sleep(0.4)


try:
    new_sketch()
    # ▭ a rectangle away from the origin
    click_uv((15, 15))
    click_uv((55, 35))
    # ◯ a circle at the origin: two locks (dx, dy) made in one step
    tool("circle")
    click_uv((0, 0))
    click_uv((6, 0))
    got, dup = ids()
    print("circle at the origin: dims", js(f"return {SK}.f.dims.map((x) => [x.id, x.t])"), "| duplicates:", dup)
    # ⊂⊃ a slot
    tool("slot")
    click_uv((-50, 0))
    click_uv((-25, 0))
    click_uv((-37.5, 4))
    print("slot:", js(f"return {SK}.f.entities.filter((e) => e.g && e.t !== 'line' || e.t === 'arc').map((e) => e.id)"),
          "| slot lines:", js(f"""const s = {SK}, g = s.f.entities.find((e) => e.t === 'arc')?.g;
            return s.f.entities.filter((e) => e.g === g && e.t === 'line').map((e) => e.id)"""))
    # ⁂ a pattern of the circle
    tool("select")
    click_uv((0, -6))
    print("picked:", js(f"return ({SK}.picks || []).map((q) => q.kind + ' ' + q.id)"))
    tool("pattern")
    settle()
    el = d.find_element(By.CSS_SELECTOR, ".sk-pattern [data-pk=n]")
    el.send_keys(Keys.CONTROL, "a")
    el.send_keys("3", Keys.ENTER)
    settle()
    print("pattern:", js(f"return {SK}.f.constraints.filter((k) => k.t === 'pat').map((k) => [k.id, k.n, k.copies])"))
    # ⧈ an offset of the rectangle
    tool("offset")
    click_uv((35, 15))
    inp = wait("return document.querySelector('.sk-choose input')")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys("3", Keys.ENTER)
    settle()
    tool("select")
    time.sleep(0.6)
    got, dup = ids()
    print("counts:", {k: len(v) for k, v in got.items()}, "| duplicate ids:", dup, "| all unique:", not dup)
    d.save_screenshot(f"{OUT}/sketch_ids.png")

    # ↔ Dimension: the rectangle's bottom right corner from the slot's right centre, along x and along y (two more dims)
    tool("dim")
    for i in range(2):
        click_uv((55, 15))
        click_uv((-25, 0))
        wait("return document.querySelectorAll('.sk-choose button').length")
        d.find_elements(By.CSS_SELECTOR, ".sk-choose button")[i].click()
        inp = wait("return document.querySelector('.sk-input')")
        inp.send_keys(Keys.CONTROL, "a")
        inp.send_keys(("80", "15")[i], Keys.ENTER)
        settle()
    tool("select")
    time.sleep(0.6)
    got, dup = ids()
    print("dims:", js(f"return {SK}.f.dims.map((x) => [x.id, x.t, x.v])"), "| duplicate ids:", dup)

    # ✕ on one dimension's label: only that one goes
    dims0 = js(f"return {SK}.f.dims.map((x) => x.id)")
    labs = [e for e in d.find_elements(By.CSS_SELECTOR, "#modelViewport .sk-label.dist[data-dim]") if e.is_displayed()]
    print("dimension labels with ✕:", [e.get_attribute("data-dim") for e in labs])
    gone = labs[0].get_attribute("data-dim")
    ActionChains(d).move_to_element(labs[0]).perform()
    time.sleep(0.2)
    labs[0].find_element(By.CSS_SELECTOR, ".sk-del").click()
    settle()
    dims1 = js(f"return {SK}.f.dims.map((x) => x.id)")
    print("deleted", gone, "->", len(dims0), "->", len(dims1), "dims | removed:", sorted(set(dims0) - set(dims1)),
          "| only that one:", sorted(set(dims0) - set(dims1)) == [gone] and len(dims1) == len(dims0) - 1)

    # ---- an old sketch with duplicate ids (two d1, two l1, two k1) opens repaired
    fixed = js("""return import('/js/modeler/sketcher.js').then(({ upgradeSketch }) => {
      const f = upgradeSketch({ points: { p1: [0, 0], p2: [10, 0], p3: [10, 5] },
        entities: [{ id: 'l1', t: 'line', a: 'p1', b: 'p2' }, { id: 'l1', t: 'line', a: 'p2', b: 'p3' }],
        constraints: [{ id: 'k1', t: 'h', e: 'l1' }, { id: 'k1', t: 'v', e: 'l1' }],
        dims: [{ id: 'd1', t: 'dx', a: '0', b: 'p1', v: 0 }, { id: 'd1', t: 'dy', a: '0', b: 'p1', v: 0 }] });
      return [f.entities.map((e) => e.id), f.constraints.map((k) => k.id), f.dims.map((x) => x.id)]; })""")
    print("old sketch repaired:", fixed, "| expected [['l1', 'l2'], ['k1', 'k2'], ['d1', 'd2']]")
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
