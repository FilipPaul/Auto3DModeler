"""◠ Arc in a sketch, with REAL mouse input in headless Edge: a line (0,0)-(40,0), then an arc from (40,0) to (0,0)
bent up through (20,20) -> a half disc R20 (closed with the line) -> R label, typed R25 (the centre stays) ->
↔ Dimension on the arc twice = its radius -> Finish -> Extrude: exact volume with a true round side; the arc
shows as a line in 3D; the AI's slot shape.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_model_arc.py http://127.0.0.1:5199 <out dir>
"""
import json
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
H = "window.__app.agentHandlers"


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


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


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
    time.sleep(0.3)


def tool(t):
    d.find_element(By.CSS_SELECTOR, f".m-cmdbar [data-a={t}]").click()
    time.sleep(0.2)


def labels():
    return js("return [...document.querySelectorAll('.sk-label.edit')].map(l => l.querySelector('.sk-val')?.textContent)")


def arc_info():
    return js(f"""const s = {SK}, e = s.f.entities.find(x => x.t === 'arc'); if (!e) return null;
      return {{c: s.P(e.c).map(v => +v.toFixed(3)), a: s.P(e.a).map(v => +v.toFixed(3)), b: s.P(e.b).map(v => +v.toFixed(3)), r: +s.arcR(e).toFixed(4)}}""")


try:
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "newModelBtn").click()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.8)
    tool("line")
    click_uv((0, 0))
    click_uv((40, 0))
    d.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    time.sleep(0.2)
    tool("arc")
    print("hint:", js("return document.querySelector('#modelViewport .m-hint').textContent"))
    click_uv((40, 0))
    click_uv((0, 0))
    move_uv((20, 20))
    print("preview label:", js("return document.querySelector('.sk-label.live')?.textContent"))
    d.save_screenshot(f"{OUT}/arc1_preview.png")
    ActionChains(d).click().perform()
    time.sleep(0.5)
    print("arc:", arc_info(), "| joined to the line:", js(f"return {SK}.f.entities.map(e => [e.t, e.a, e.b])"), "| labels", labels())

    # type the radius: R25 (the centre stays at (20, 0), the ends move out along the circle)
    lab = next(el for el in d.find_elements(By.CSS_SELECTOR, ".sk-label.edit") if el.find_element(By.CSS_SELECTOR, ".sk-val").text.startswith("R"))
    lab.find_element(By.CSS_SELECTOR, ".sk-val").click()
    time.sleep(0.2)
    inp = d.find_element(By.CSS_SELECTOR, ".sk-input")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys("25", Keys.ENTER)
    time.sleep(0.8)
    print("R25:", arc_info(), "| dims", js(f"return {SK}.f.dims.map(x => [x.t, x.v])"))
    js(f"{SK}.back()")  # Ctrl+Z
    time.sleep(0.5)
    print("undo:", arc_info())

    # ↔ Dimension: the arc twice = its radius
    js(f"{SK}.f.dims = []; {SK}.changed()")
    tool("dim")
    move_uv((20 + 20 * math.cos(1.0), 20 * math.sin(1.0)))
    print("hover:", js("return document.querySelector('.sk-label.hover')?.textContent"))
    ActionChains(d).click().perform()
    time.sleep(0.3)
    click_uv((20 + 20 * math.cos(2.0), 20 * math.sin(2.0)))
    time.sleep(0.6)
    inp = d.find_elements(By.CSS_SELECTOR, ".sk-input")
    if inp:
        inp[0].send_keys(Keys.ENTER)
        time.sleep(0.5)
    print("dimension tool on the arc:", js(f"return {SK}.f.dims.map(x => [x.t, x.e, x.v])"))
    d.save_screenshot(f"{OUT}/arc2_sketch.png")

    # finish and extrude
    tool("finish")
    settled()
    btn = d.find_elements(By.CSS_SELECTOR, "#modelRight [data-a=ok]")
    if btn:
        btn[0].click()
    settled()
    b = js(f"return {M}.result.body")
    h = js(f"return {M}.part.features.find(f => f.type === 'extrude').d")
    print("extruded:", round(b["volume"], 4), "| expected", round(math.pi * 400 / 2 * h, 4), "| faces", sorted((f["name"], f["type"]) for f in b["faces"]))
    js(f"{M}.view.setView('iso')")
    time.sleep(0.4)
    d.save_screenshot(f"{OUT}/arc3_solid.png")

    # a tangent arc: a line, then an arc started at its loose end continues it (two clicks)
    d.find_element(By.ID, "newModelBtn").click()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.8)
    tool("line")
    click_uv((0, 0))
    click_uv((20, 0))
    d.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    time.sleep(0.2)
    tool("arc")
    click_uv((20, 0))
    print("tangent hint:", js("return document.querySelector('#modelViewport .m-hint').textContent")[:40])
    click_uv((30, 10))
    print("tangent arc:", arc_info(), "| constraint:", js(f"return {SK}.f.constraints.filter(c => c.t === 'tan').map(c => [c.e, c.arc])"))
    # type the line 50 long: the arc moves along, still tangent (its centre stays above the line's end)
    lab = next(el for el in d.find_elements(By.CSS_SELECTOR, ".sk-label.edit") if el.find_element(By.CSS_SELECTOR, ".sk-val").text == "20")
    lab.find_element(By.CSS_SELECTOR, ".sk-val").click()
    time.sleep(0.2)
    inp = d.find_element(By.CSS_SELECTOR, ".sk-input")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys("25", Keys.ENTER)
    time.sleep(0.8)
    a = arc_info()
    print("line 25:", a, "| tangent (centre straight above the line's end):", abs(a["c"][0] - 25) < 1e-3)
    d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=cancelSketch]").click()
    time.sleep(0.5)

    # a new sketch with an arc, not extruded: shown as lines in 3D
    call("add_feature", type="sketch", plane="XZ", shapes=[{"slot": {"x1": 0, "y1": 30, "x2": 30, "y2": 30, "w": 10}}])
    settled()
    print("sketch outlines in 3D (line pieces per sketch):", js(f"return {M}.view.outlineGroup.children.map(o => o.geometry.attributes.position.count / 2)"))
    # the AI's slot: a plate with a slot cut through it
    call("new_model", name="Slotted")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": -10, "y": -10, "w": 60, "h": 20}}, {"slot": {"x1": 0, "y1": 0, "x2": 30, "y2": 0, "w": 8}}])
    r = json.loads(call("add_feature", type="extrude", sketch="F1", d=4))
    print("AI slot plate:", r["ok"], r["body"]["volume_mm3"], "| expected", round(4 * (1200 - 30 * 8 - math.pi * 16), 3))
    print("bad slot:", call("add_feature", type="sketch", plane="XY", shapes=[{"slot": {"x1": 0, "y1": 0, "x2": 0, "y2": 0, "w": 8}}]))
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
