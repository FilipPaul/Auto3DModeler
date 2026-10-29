"""The sketch's snap filters on a part, with REAL mouse input, in Czech: a block 40 × 20 × 10 with a Ø8 hole off the
middle -> a sketch on its top face (✏ Sketch, a click on the face) -> the filter row at the bottom of the view shows
(Přichytit | Na dílu | Výběr; it was missing on a part: the 3D view's row took its place and was removed with it) ->
✏ Line near a corner of the part: caught (label "roh dílu"), the part's snap points near the mouse marked -> "Na dílu:
⌜ Rohy" off: the corner is not caught any more (and not marked), the hole's centre still is -> ◔ Kvadranty on: a
quadrant of the hole caught -> Alt held: nothing caught -> a line drawn from near the corner to near the centre: it
starts off the corner, ends on the centre -> the sketch left: the 3D view's Snap row has Corners off too (one choice)
-> reloaded and the sketch opened again: still off. Screenshots at 1600×1000 and 1280×800; no console errors.

  PYTHONIOENCODING=utf-8 py tools/e2e_sketch_snap_filters.py http://127.0.0.1:5199 <out dir>
"""
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

URL, OUT = sys.argv[1], sys.argv[2]
FAILS = []
M = "window.__app.modeler"
SK = f"{M}.sk"
H = "window.__app.agentHandlers"
ROW = "#modelViewport > .sk-filters:not(.snap-filters)"


def check(name, ok, extra=""):
    print(("  ok   " if ok else "  FAIL ") + name + (f"  [{extra}]" if extra and not ok else ""))
    if not ok:
        FAILS.append(name)


def browser(w, h):
    opts = webdriver.EdgeOptions()
    opts.add_argument("--headless=new")
    opts.add_argument(f"--window-size={w},{h}")
    opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
    return webdriver.Edge(options=opts)


d = None


def js(*a):
    return d.execute_script(*a)


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(script)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#modelViewport canvas")


def off3(p):
    return js(f"""const v = {M}.view, p = arguments[0];
      const [sx, sy] = v.toScreen(new (v.camera.position.constructor)(p[0], p[1], p[2])), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", p)


def off(uv):
    return js(f"""const m = {M}, v = m.view, f = m.frame(), [u, w] = arguments[0];
      const y = [f.n[1]*f.x[2]-f.n[2]*f.x[1], f.n[2]*f.x[0]-f.n[0]*f.x[2], f.n[0]*f.x[1]-f.n[1]*f.x[0]];
      const p = new (v.camera.position.constructor)(f.o[0] + u*f.x[0] + w*y[0], f.o[1] + u*f.x[1] + w*y[1], f.o[2] + u*f.x[2] + w*y[2]);
      const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(uv))


def move_uv(uv, alt=False):
    o = off(uv)
    a = ActionChains(d, duration=30)
    if alt:
        a.key_down(Keys.ALT)
    a.move_to_element_with_offset(canvas(), o[0] + 1, o[1] + 1).move_to_element_with_offset(canvas(), *o)
    if alt:
        a.key_up(Keys.ALT)
    a.perform()
    time.sleep(0.3)


def caught():
    """What the mouse catches now: [refKind or id or None, uv, the hover label]."""
    return js(f"""const c = {SK}.cursor || {{}}, l = document.querySelector('#modelViewport .sk-label.hover');
      return [c.refKind || c.id || (c.on || c.edge || c.onCircle ? 'on' : null), c.uv, l ? l.textContent : '']""")


def marks():
    """The part's snap points marked near the mouse (dim green dots)."""
    return js(f"return {SK}.partMarks")


def part_toggle(k):
    d.find_element(By.CSS_SELECTOR, f"{ROW} [data-skpart={k}]").click()
    time.sleep(0.3)
    return "on" in d.find_element(By.CSS_SELECTOR, f"{ROW} [data-skpart={k}]").get_attribute("class")


def open_sketch_on_top():
    js(f"{M}.view.setView('iso')")
    time.sleep(0.4)
    d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=sketch]").click()
    time.sleep(0.4)
    o = off3([8, 4, 10])
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *o).click().perform()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(1)


def tool(t):
    d.find_element(By.CSS_SELECTOR, f".m-cmdbar [data-a={t}]").click()
    time.sleep(0.25)


def build():
    call("new_model", name="Blok s dírou")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="hole", face="F2:end", points=[[10, 3]], d=8)
    wait(f"return !{M}.building && {M}.result?.body && {M}.part.features.length === 3")
    time.sleep(0.5)


def row_czech(tag):
    eng = js(rf"""return [...document.querySelectorAll('{ROW} [title], {ROW} button, {ROW} .skf-t')]
      .flatMap(e => [e.title, e.textContent]).filter(s => /\b(the|to|click|snap|select|points|lines|grid|guides|origin|part|corners|edges|centres|hold)\b/i.test(s))""")
    check(f"{tag}: the row and its tooltips in Czech", not eng, eng)


def overlaps(tag):
    row = d.find_element(By.CSS_SELECTOR, ROW).rect
    for sel in ["#modelViewport .view-actions"]:
        for e in d.find_elements(By.CSS_SELECTOR, sel):
            r = e.rect
            hit = not (r["x"] >= row["x"] + row["width"] or r["x"] + r["width"] <= row["x"] or r["y"] >= row["y"] + row["height"] or r["y"] + r["height"] <= row["y"])
            check(f"{tag}: the row clear of Finish / Cancel", not hit)
    check(f"{tag}: the row fits (no scrollbar)", js(f"const b = document.querySelector('{ROW}'); return b.scrollWidth <= b.clientWidth + 1"))


errors = []
try:
    # ---------------------------------------------------------------- 1600 × 1000: the whole story
    d = browser(1600, 1000)
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('a3d.sksnap'); localStorage.removeItem('a3d.snap3d'); localStorage.removeItem('a3d.skpick'); localStorage.setItem('auto3d-lang', 'cs')")
    d.refresh()
    wait("return !!window.__app")
    build()
    check("the part: the 3D view's Snap row shows", bool(d.find_elements(By.CSS_SELECTOR, "#modelViewport > .snap-filters")))
    open_sketch_on_top()
    rows = d.find_elements(By.CSS_SELECTOR, ROW)
    check("a sketch on the part's face: its filter row shows", len(rows) == 1 and rows[0].is_displayed())
    check("… and the 3D view's row is gone", not d.find_elements(By.CSS_SELECTOR, "#modelViewport > .snap-filters"))
    print("the row:", rows[0].text.replace("\n", " ") if rows else None)
    check("Na dílu group: 5 toggles (corners, edge midpoints, centres, quadrants, edges)",
          js(f"return [...document.querySelectorAll('{ROW} [data-skpart]')].map(b => b.dataset.skpart).join()") == "corner,midpoint,centre,quadrant,edges")
    check("defaults as in 3D: all on but quadrants", js(f"return [...document.querySelectorAll('{ROW} [data-skpart]')].filter(b => b.classList.contains('on')).length") == 4)
    check("the sketch's own kinds kept (7)", js(f"return document.querySelectorAll('{ROW} [data-sksnap]').length") == 7)
    check("tooltips say Alt = no snapping", js(f"return [...document.querySelectorAll('{ROW} [data-skpart], {ROW} [data-sksnap]')].every(b => /Alt/.test(b.title))"))
    row_czech("1600")
    R = js(f"const r = {SK}.refs(); return {{pts: r.points, circles: r.circles}}")
    corner = min(R["pts"], key=lambda p: p[0] + p[1])
    hole = [c for c in R["circles"] if abs(c["r"] - 4) < 1e-3][0]["c"]
    print("corner", corner, "| hole centre", hole)

    tool("line")
    move_uv([corner[0] + 0.25, corner[1] + 0.2])
    c = caught()
    print("near the corner:", c, "| marks", marks())
    check("Rohy on: the part's corner caught", c[0] == "corner" and abs(c[1][0] - corner[0]) < 1e-6 and abs(c[1][1] - corner[1]) < 1e-6, c)
    check("… labelled in Czech (roh dílu)", c[2] == "roh dílu", c[2])
    n_on = marks()
    check("the part's snap points near the mouse marked", n_on >= 2, n_on)
    d.save_screenshot(f"{OUT}/sketch_snap_filters_corner.png")

    check("Rohy switched off", not part_toggle("corner"))
    check("… the 3D view's choice too (one storage)", js("return JSON.parse(localStorage.getItem('a3d.snap3d')).corner") is False)
    move_uv([corner[0] + 0.25, corner[1] + 0.2])
    c = caught()
    print("Rohy off, near the corner:", c, "| marks", marks())
    check("Rohy off: the corner is not caught", not (c[0] == "corner" or (abs(c[1][0] - corner[0]) < 1e-6 and abs(c[1][1] - corner[1]) < 1e-6)), c)
    check("… and not marked any more", marks() < n_on, marks())
    move_uv([hole[0] + 0.25, hole[1] + 0.2])
    c = caught()
    print("near the hole's centre:", c)
    check("Středy (part) on: the hole's centre still caught", c[0] == "centre" and abs(c[1][0] - hole[0]) < 1e-6, c)
    check("… labelled střed na dílu", c[2] == "střed na dílu", c[2])
    move_uv([hole[0] + 0.25, hole[1] + 0.2], alt=True)
    c = caught()
    check("Alt held: nothing caught", c[0] is None and abs(c[1][0] - hole[0]) > 1e-3, c)

    check("Kvadranty switched on", part_toggle("quadrant"))
    move_uv([hole[0] + 4.2, hole[1] + 0.2])
    c = caught()
    print("near the hole's right quadrant:", c)
    check("Kvadranty on: the hole's quadrant caught", c[0] == "quadrant" and abs(c[1][0] - (hole[0] + 4)) < 1e-6, c)
    d.save_screenshot(f"{OUT}/sketch_snap_filters_quadrant.png")
    check("Kvadranty off again", not part_toggle("quadrant"))
    move_uv([hole[0] + 4.2, hole[1] + 0.2])
    check("Kvadranty off: not caught", caught()[0] != "quadrant", caught())

    # a line from near the corner to near the centre: off the corner, on the centre
    move_uv([corner[0] + 0.25, corner[1] + 0.2])
    ActionChains(d).click().perform()
    time.sleep(0.4)
    move_uv([hole[0] + 0.25, hole[1] + 0.2])
    ActionChains(d).click().perform()
    time.sleep(0.6)
    ln = js(f"const e = {SK}.f.entities.filter(x => x.t === 'line').slice(-1)[0]; return e && [{SK}.P(e.a), {SK}.P(e.b)]")
    print("the line:", ln)
    check("the line starts off the part's corner (Rohy off)", ln and (abs(ln[0][0] - corner[0]) > 1e-3 or abs(ln[0][1] - corner[1]) > 1e-3), ln)
    check("… and ends on the hole's centre", ln and abs(ln[1][0] - hole[0]) < 1e-6 and abs(ln[1][1] - hole[1]) < 1e-6, ln)
    d.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    time.sleep(0.3)
    overlaps("1600")
    d.save_screenshot(f"{OUT}/sketch_snap_filters_1600.png")
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=cancelSketch], .m-cmdbar [data-a=cancelSketch]").click()
    wait(f"return {M}.mode === 'part'")
    time.sleep(0.4)
    on3d = js("return [...document.querySelectorAll('#modelViewport > .snap-filters [data-snap]')].filter(b => b.classList.contains('on')).map(b => b.dataset.snap).join()")
    check("the 3D view's Snap row: Corners off too", "corner" not in on3d.split(","), on3d)

    d.refresh()
    wait("return !!window.__app")
    wait(f"return {M}.result?.body || false", 60) if js(f"return !!{M}.part?.features?.length") else build()
    open_sketch_on_top()
    st = js(f"return Object.fromEntries([...document.querySelectorAll('{ROW} [data-skpart]')].map(b => [b.dataset.skpart, b.classList.contains('on')]))")
    print("after a reload:", st)
    check("reloaded: Rohy still off, the rest as left", st == {"corner": False, "midpoint": True, "centre": True, "quadrant": False, "edges": True}, st)
    part_toggle("corner")
    errors += [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    d.quit()

    # ---------------------------------------------------------------- 1280 × 800: the row there too
    d = browser(1280, 800)
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('a3d.sksnap'); localStorage.removeItem('a3d.snap3d'); localStorage.setItem('auto3d-lang', 'cs')")
    d.refresh()
    wait("return !!window.__app")
    build()
    open_sketch_on_top()
    rows = d.find_elements(By.CSS_SELECTOR, ROW)
    check("1280: the row shows on the part's face", len(rows) == 1 and rows[0].is_displayed())
    tool("line")
    R = js(f"const r = {SK}.refs(); return r.points")
    corner = min(R, key=lambda p: p[0] + p[1])
    move_uv([corner[0] + 0.3, corner[1] + 0.3])
    row_czech("1280")
    overlaps("1280")
    d.save_screenshot(f"{OUT}/sketch_snap_filters_1280.png")
    errors += [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
finally:
    if d:
        try:
            errors += [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
        except Exception:
            pass
        d.quit()
    print("console errors:", errors)
    if errors:
        FAILS.append("console errors")
    print("FAILS:", FAILS if FAILS else "none")
    sys.exit(1 if FAILS else 0)
