"""The suggestions table for what is selected (bottom left of the view), with REAL mouse input: a sketch's rectangle and
circle -> ⬚ a line: "A line" — its length, horizontal, vertical, construction -> Ctrl+click a crossing line: the angle
between them, parallel, perpendicular, equal -> "Equal" made -> Ctrl+click a circle + a line: tangent -> Esc: gone ->
an assembly: a part chosen: open its part, join it … -> Ctrl+click a second: join them, measure, collisions -> "Join
them": picking faces. The table is short: at most N rows (default 8, set in its header) of the most relevant, then
"⋯ Show all (n)" which opens everything in sections (remembered for the session, ▴ Fewer closes it); the top rows for
two lines (the angle, ∥ / ⟂), a face (✏ Sketch on it, ◎ Hole) and a placed part (🔗 Join, ◆ Open its part).

  PYTHONIOENCODING=utf-8 py tools/e2e_suggest.py http://127.0.0.1:5199 <out dir>
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
A = "window.__app.assembly"
H = "window.__app.agentHandlers"
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


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def canvas(sel="#modelViewport canvas"):
    return d.find_element(By.CSS_SELECTOR, sel)


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
    if ctrl:
        ch.key_down(Keys.CONTROL).click().key_up(Keys.CONTROL)
    else:
        ch.click()
    ch.perform()
    time.sleep(0.4)


def tool(t):
    d.find_element(By.CSS_SELECTOR, f".m-cmdbar [data-a={t}], #modelViewport .view-actions [data-a={t}]").click()
    time.sleep(0.25)


def table(vp="#modelViewport"):
    box = d.find_elements(By.CSS_SELECTOR, f"{vp} .view-suggest")
    if not box:
        return None
    return [box[0].find_element(By.CSS_SELECTOR, ".vs-head b").text] + [b.text.replace("\n", " ") for b in box[0].find_elements(By.CSS_SELECTOR, ".vs-list button")]


def rows(tb):
    """The action rows of a table (not ⋯ Show all / ▴ Fewer)."""
    return [r for r in (tb or [])[1:] if not r.startswith(("⋯ Show all", "▴ Fewer"))]


def more_row(vp="#modelViewport"):
    b = d.find_elements(By.CSS_SELECTOR, f"{vp} .view-suggest .vs-more")
    return " ".join(b[0].text.split()) if b else None


def sections(vp="#modelViewport"):
    return [s.text for s in d.find_elements(By.CSS_SELECTOR, f"{vp} .view-suggest .vs-sec")]


def press(label, vp="#modelViewport"):
    next(b for b in d.find_elements(By.CSS_SELECTOR, f"{vp} .view-suggest .vs-list button") if label in b.text).click()
    time.sleep(0.8)


try:
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "newModelBtn").click()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.6)
    click_uv((0, 0))
    click_uv((40, 20))
    tool("circle")
    click_uv((60, 10))
    click_uv((64, 10))
    tool("select")
    print("nothing chosen:", table())
    click_uv((10, 20))  # the top line
    print("a line:", table())
    pos = d.find_element(By.CSS_SELECTOR, "#modelViewport .view-suggest").rect
    vp = d.find_element(By.CSS_SELECTOR, "#modelViewport").rect
    sel = d.find_element(By.CSS_SELECTOR, "#modelViewport > .sk-filters").rect  # (the sketch's Select: row, under the table)
    print("  bottom left, just above the Select row:", pos["x"] - vp["x"] < 30 and 0 <= sel["y"] - (pos["y"] + pos["height"]) < 20,
          f"(left {pos['x'] - vp['x']:.0f} px, {sel['y'] - (pos['y'] + pos['height']):.0f} px above the row)")
    click_uv((40, 6), ctrl=True)  # + the right line (they cross at the corner)
    tb = table()
    print("+ a crossing line:", tb)
    check("two lines: the angle first, then the relation nearest to true (= / ∥ / ⟂), the other relations above the edits", tb and "angle" in tb[1] and any(x in tb[2] for x in ("Equal", "Perpendicular", "Parallel")) and tb.index(next(r for r in tb if "Parallel" in r or "Fix" in r)) < tb.index(next(r for r in tb if "Move" in r)))
    check("two lines: at most 8 rows, then ⋯ Show all (n)", len(rows(tb)) <= 8 and (more_row() or "").startswith("⋯ Show all ("))
    total = int((more_row() or "(0)").rsplit("(", 1)[1].rstrip(")"))
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-suggest [data-sg-all]").click()
    time.sleep(0.4)
    tb = table()
    print("  ⋯ Show all:", sections(), tb)
    d.save_screenshot(f"{OUT}/suggest_all.png")
    check(f"Show all: all {total} rows, in sections, ▴ Fewer last", len(rows(tb)) == total > 8 and len(sections()) >= 2 and more_row() == "▴ Fewer")
    check("…remembered for the session", js("return sessionStorage.getItem('a3d.suggestAll')") == "1")
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-suggest [data-sg-fewer]").click()
    time.sleep(0.4)
    check("▴ Fewer: the short table again", len(rows(table())) == 8 and (more_row() or "").startswith("⋯ Show all"))
    # N set in the header: "Suggested" -> a number field
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-set").click()
    time.sleep(0.3)
    inp = d.find_element(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-top input")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys("5", Keys.ENTER)
    time.sleep(0.4)
    tb = table()
    print("  N = 5:", tb, "| stored", js("return localStorage.getItem('a3d.suggestTop')"))
    check("N = 5: five rows + Show all, stored", len(rows(tb)) == 5 and (more_row() or "").startswith("⋯ Show all") and js("return localStorage.getItem('a3d.suggestTop')") == "5")
    check("…the field closed after Enter", not d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-top"))
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-set").click()
    time.sleep(0.3)
    d.save_screenshot(f"{OUT}/suggest_setting.png")
    inp = d.find_element(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-top input")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys("8", Keys.ENTER)
    time.sleep(0.4)
    check("N back to 8", len(rows(table())) == 8)
    press("Equal")
    print("  Equal made:", js(f"return {SK}.f.constraints.filter(k => k.user).map(k => k.t)"))
    top = js(f"const s = {SK}, l = s.f.entities.filter(e => e.t === 'line').map(e => [s.P(e.a), s.P(e.b)]).filter(([a, b]) => Math.abs(a[1] - b[1]) < 1e-6).sort((p, q) => q[0][1] - p[0][1])[0]; return [l[0][0] + (l[1][0] - l[0][0]) * 0.25, l[0][1]]")
    click_uv(top)  # the top line, where it is now
    click_uv((64, 10), ctrl=True)  # + the circle
    print("a line + a circle:", table())
    d.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    time.sleep(0.4)
    print("Esc:", table())
    tool("finish")
    wait(f"return {M}.mode === 'part'", 10)
    time.sleep(0.5)
    print("after the sketch:", table())

    # a face of a 3D model: Sketch on it, Hole here first; the rest under Show all
    call("new_model", name="Plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    wait(f"return !!{M}.result?.body && !{M}.inflight")
    js(f"{M}.view.setView('iso')")
    time.sleep(0.6)
    dx, dy = js(f"""const v = {M}.view, p = new (v.camera.position.constructor)(20, 10, 10);
      const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""")
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), dx, dy).perform()
    time.sleep(0.2)
    ActionChains(d).click().perform()
    time.sleep(0.6)
    tb = table()
    print("a flat face:", sections(), tb)
    d.save_screenshot(f"{OUT}/suggest_face.png")
    check("a face: ✏ Sketch on this face, ◎ Hole here first", tb and "Sketch on this face" in tb[1] and "Hole here" in tb[2])
    check("a face: 8 rows (Fillet, Edit among them) + Show all", len(rows(tb)) == 8 and any("Round its edges" in r for r in tb) and any("Edit the step" in r for r in tb) and (more_row() or "").startswith("⋯ Show all"))
    check("a face: Split / Mirror only under Show all", not any("Split here" in r or "Mirror across" in r for r in tb))
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-suggest [data-sg-all]").click()
    time.sleep(0.4)
    tb = table()
    check("Show all: Split here, Mirror, Turn it off there", all(any(x in r for r in tb) for x in ("Split here", "Mirror across this face", "Turn it off")))
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-suggest [data-sg-fewer]").click()
    time.sleep(0.3)

    for name in ("Base", "Lid"):
        call("new_model", name=name)
        call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 30}}])
        call("add_feature", type="extrude", sketch="F1", d=5)
    call("new_assembly", name="Box")
    call("insert_part", part="Base")
    call("insert_part", part="Lid")
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    js(f"{A}.choose('I1')")
    time.sleep(0.4)
    tb = table("#asmViewport")
    print("a part:", tb)
    check("a placed part: 🔗 Join it, ◆ Open its part first", tb and "Join it to another part" in tb[1] and "Open its part" in tb[2])
    check("…no Show all (fewer than 8)", len(rows(tb)) <= 8 and not more_row("#asmViewport"))
    js(f"{A}.choose('I2', true)")
    time.sleep(0.4)
    print("+ another part:", table("#asmViewport"))
    press("Join them", "#asmViewport")
    print("  Join them: picking faces:", js(f"return {A}.mode"), "| the table:", table("#asmViewport"))
    d.save_screenshot(f"{OUT}/suggest.png")
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    d.quit()
print("FAILED:" if FAILS else "all checks OK", FAILS if FAILS else "")
sys.exit(1 if FAILS or errs else 0)
