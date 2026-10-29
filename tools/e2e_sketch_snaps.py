"""The sketch's Snap filters, with REAL mouse input: the row at the bottom of a sketch — "Snap: Points / ends,
Midpoints, Centres, Origin, On lines / curves, Guides, Grid (on a part also "On the part: …") | Select: …" -> a line drawn ->
Midpoints off: a click near its middle does not snap there (on: it does, a `mid` rule) -> Grid off: a click lands
off the grid (on: on it) -> Guides off: beside a corner no dashed guide (on: one) -> reloaded: the choices kept.
The row clear of the suggestions table, the quick size box and Finish / Cancel at 1600×1000 and 1280×800, in
English and Czech (screenshots).

  PYTHONIOENCODING=utf-8 py tools/e2e_sketch_snaps.py http://127.0.0.1:5199 <out dir>
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
opts.add_argument("--lang=en-US")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"
SK = f"{M}.sk"
FAILS = []


def check(name, ok):
    print(("  ok   " if ok else "  FAIL ") + name)
    if not ok:
        FAILS.append(name)


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
    time.sleep(0.25)


def click_uv(uv):
    move_uv(uv)
    ActionChains(d).click().perform()
    time.sleep(0.4)


def tool(t):
    d.find_element(By.CSS_SELECTOR, f".m-cmdbar [data-a={t}], #modelViewport .view-actions [data-a={t}]").click()
    time.sleep(0.25)


def esc():
    d.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    time.sleep(0.6)


def snap(k):
    """Click the Snap toggle `k`; -> is it on now."""
    d.find_element(By.CSS_SELECTOR, f"#modelViewport .sk-filters [data-sksnap={k}]").click()
    time.sleep(0.3)
    return "on" in d.find_element(By.CSS_SELECTOR, f"#modelViewport .sk-filters [data-sksnap={k}]").get_attribute("class")


def last_line():
    return js(f"""const e = {SK}.f.entities.filter(x => x.t === 'line').slice(-1)[0];
      return [{SK}.P(e.a), {SK}.P(e.b), {SK}.f.constraints.filter(k => k.p === e.a || k.p === e.b).map(k => k.t)]""")


def new_sketch():
    d.find_element(By.ID, "newModelBtn").click()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.6)


def overlaps(tag):
    """The filter row against the table / quick box / the action dock: [name, overlapping] each present."""
    out = []
    row = d.find_element(By.CSS_SELECTOR, "#modelViewport .sk-filters").rect
    for sel in ["#modelViewport .view-suggest", "#modelViewport .sk-quick", "#modelViewport .view-actions"]:
        for e in d.find_elements(By.CSS_SELECTOR, sel):
            r = e.rect
            hit = not (r["x"] >= row["x"] + row["width"] or r["x"] + r["width"] <= row["x"] or r["y"] >= row["y"] + row["height"] or r["y"] + r["height"] <= row["y"])
            out.append(sel.split()[-1])
            check(f"{tag}: the row clear of {sel.split()[-1]}", not hit)
    sc = js("const b = document.querySelector('#modelViewport .sk-filters'); return b.scrollWidth <= b.clientWidth + 1")
    check(f"{tag}: the row fits (no scrollbar)", sc)
    return out


def views(tag):
    """The row with a shape picked (the table) and with the quick size box, screenshots."""
    tool("select")
    click_uv((20, 10))  # the line: its suggestions table
    print(f"[{tag}] the row:", d.find_element(By.CSS_SELECTOR, "#modelViewport .sk-filters").text.replace("\n", " "),
          "| compact:", js("return [...document.querySelectorAll('#modelViewport .sk-filters, #modelViewport .sk-filters .skf-g')].map(e => e.className)"))
    if tag.endswith("cs"):
        eng = js(r"""return [...document.querySelectorAll('#modelViewport .sk-filters [title], #modelViewport .sk-filters button')]
          .flatMap(e => [e.title, e.textContent]).filter(s => /\b(the|to|click|snap|select|points|lines|grid|guides|origin)\b/i.test(s))""")
        print("  English left in the row:", eng)
        check(f"{tag}: the row and its tooltips in Czech", not eng)
    print("  present:", overlaps(f"{tag} + table"))
    d.save_screenshot(f"{OUT}/sketch_snaps_{tag}_table.png")
    esc()
    tool("dim")
    click_uv((20, 10))  # a click on the line: its quick size box
    print("  present:", overlaps(f"{tag} + quick box"))
    d.save_screenshot(f"{OUT}/sketch_snaps_{tag}_quick.png")
    esc()
    tool("line")
    move_uv((-20, -25))
    d.save_screenshot(f"{OUT}/sketch_snaps_{tag}_line.png")
    esc()


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('a3d.sksnap'); localStorage.removeItem('a3d.skpick'); localStorage.setItem('auto3d-lang', 'en')")
    d.refresh()
    wait("return !!window.__app")
    new_sketch()
    bar = d.find_element(By.CSS_SELECTOR, "#modelViewport .sk-filters")
    print("the row:", bar.text.replace("\n", " "))
    check("Snap group with 7 toggles, all on (the part's own: e2e_sketch_snap_filters)", js("return [...document.querySelectorAll('#modelViewport .sk-filters [data-sksnap]')].filter(b => b.classList.contains('on')).length") == 7)
    check("Select group kept (6 toggles)", len(bar.find_elements(By.CSS_SELECTOR, "[data-f]")) == 6)
    check("drawing: the Snap group is the active one", "active" in bar.find_element(By.CSS_SELECTOR, ".skf-snap").get_attribute("class"))
    # a line from (10, 10) to (50, 10)
    tool("line")
    click_uv((10, 10))
    click_uv((50, 10))
    esc()
    # Midpoints on: a click near its middle snaps there
    tool("line")
    click_uv((30.4, 10.5))
    click_uv((30.4, 30))
    esc()
    a, b, ks = last_line()
    print("Midpoints on: the click near the middle ->", a, ks)
    check("Midpoints on: it lands on the middle, held by a mid rule", abs(a[0] - 30) < 1e-6 and abs(a[1] - 10) < 1e-6 and "mid" in ks)
    tool("line")  # (a second line: the first one's middle has a point of its own now)
    click_uv((10, -10))
    click_uv((50, -10))
    esc()
    check("Midpoints off", not snap("mid"))
    n = js(f"return {SK}.f.entities.length")
    tool("line")
    click_uv((30.4, -9.5))
    click_uv((30.4, -25))
    esc()
    a, b, ks = last_line()
    print("Midpoints off: the click near the middle ->", a, ks)
    check("Midpoints off: a line drawn from where the mouse was, on the line (not its middle), no mid rule",
          js(f"return {SK}.f.entities.length") == n + 1 and abs(a[0] - 30.4) < 0.3 and abs(a[1] + 10) < 1e-6 and "mid" not in ks and "on" in ks)
    # Grid: on -> on the grid; off -> where the mouse is
    g = js(f"return {SK}.gridStep()")
    tool("line")
    click_uv((-23.37, -41.71))
    click_uv((-41.13, -47.29))
    esc()
    a, b, _ = last_line()
    on_grid = lambda p: all(abs(v / g - round(v / g)) < 1e-6 for v in p)
    print("Grid on (step", g, "):", a, b)
    check("Grid on: the points on the grid", on_grid(a) and on_grid(b))
    check("Grid off", not snap("grid"))
    tool("line")
    click_uv((-63.37, -21.71))
    click_uv((-77.13, -33.29))
    esc()
    a, b, _ = last_line()
    print("Grid off:", a, b)
    check("Grid off: the points off the grid (free)", not on_grid(a) and not on_grid(b))
    # Guides: beside the line's right end, level with it
    tool("line")
    move_uv((50 + 14.3, 10.35))
    gd = js(f"return ({SK}.cursor?.guides || []).length")
    print("Guides on: beside (50, 10):", js(f"return {SK}.cursor?.uv"), "guides", gd)
    check("Guides on: a dashed guide", gd > 0)
    check("Guides off", not snap("guides"))
    move_uv((50 + 14.2, 10.3))
    move_uv((50 + 14.3, 10.35))
    gd = js(f"return ({SK}.cursor?.guides || []).length")
    print("Guides off:", js(f"return {SK}.cursor?.uv"), "guides", gd)
    check("Guides off: no dashed guide", gd == 0)
    d.save_screenshot(f"{OUT}/sketch_snaps_off.png")
    esc()
    # reloaded: kept
    d.refresh()
    wait("return !!window.__app")
    new_sketch()
    st = js("return Object.fromEntries([...document.querySelectorAll('#modelViewport .sk-filters [data-sksnap]')].map(b => [b.dataset.sksnap, b.classList.contains('on')]))")
    print("after a reload:", st)
    check("after a reload: Midpoints, Grid, Guides still off, the rest on", st == {"ends": True, "mid": False, "centre": True, "origin": True, "on": True, "guides": False, "grid": False})
    for k in ("mid", "grid", "guides"):
        snap(k)
    # the row's place at both sizes, English and Czech
    tool("line")
    click_uv((10, 10))
    click_uv((50, 10))
    esc()
    views("1600_en")
    d.find_element(By.ID, "langBtn").click()
    time.sleep(0.8)
    views("1600_cs")
    d.set_window_size(1280, 800)
    time.sleep(1)
    views("1280_cs")
    d.find_element(By.ID, "langBtn").click()
    time.sleep(0.8)
    views("1280_en")
finally:
    js("localStorage.removeItem('a3d.sksnap')")
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    d.quit()
print("FAILED:" if FAILS else "all checks OK", FAILS if FAILS else "")
sys.exit(1 if FAILS or errs else 0)
