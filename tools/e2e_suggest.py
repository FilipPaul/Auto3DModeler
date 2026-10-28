"""The suggestions table for what is selected (bottom left of the view), with REAL mouse input: a sketch's rectangle and
circle -> ⬚ a line: "A line" — its length, horizontal, vertical, construction -> Ctrl+click a crossing line: the angle
between them, parallel, perpendicular, equal -> "Equal" made -> Ctrl+click a circle + a line: tangent -> Esc: gone ->
an assembly: a part chosen: open its part, join it … -> Ctrl+click a second: join them, measure, collisions -> "Join
them": picking faces.

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
    print("+ a crossing line:", table())
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
    print("a part:", table("#asmViewport"))
    js(f"{A}.choose('I2', true)")
    time.sleep(0.4)
    print("+ another part:", table("#asmViewport"))
    press("Join them", "#asmViewport")
    print("  Join them: picking faces:", js(f"return {A}.mode"), "| the table:", table("#asmViewport"))
    d.save_screenshot(f"{OUT}/suggest.png")
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
