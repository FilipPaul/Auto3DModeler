"""◜ Round corner in a sketch, with REAL mouse input in headless Edge: a 40 x 20 rectangle -> ◜ Round corner ->
hover a corner ("corner") -> click it: an arc (R4, a fifth of the short side), the radius editor opens -> type 5 ->
the width still shows (to the sharp corner) and can be typed (60: the rounding moves along, still R5) -> round a
second corner -> Ctrl+Z -> Finish -> Extrude: exact volume; the AI's rect with r.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_model_round.py http://127.0.0.1:5199 <out dir>
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


def move(uv):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *off(uv)).perform()
    time.sleep(0.2)


def click(uv):
    move(uv)
    ActionChains(d).click().perform()
    time.sleep(0.35)


def tool(t):
    d.find_element(By.CSS_SELECTOR, f".m-cmdbar [data-a={t}], #modelViewport .view-actions [data-a={t}]").click()
    time.sleep(0.2)


def type_in_editor(value):
    inp = wait("return document.querySelector('.sk-input')")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys(str(value), Keys.ENTER)
    time.sleep(0.9)


def arcs():
    return js(f"""const s = {SK}; return s.f.entities.filter(e => e.t === 'arc').map(e => ({{
      c: s.P(e.c).map(v => +v.toFixed(3)), a: s.P(e.a).map(v => +v.toFixed(3)), b: s.P(e.b).map(v => +v.toFixed(3)), r: +s.arcR(e).toFixed(4)}}))""")


def labels():
    return js("return [...document.querySelectorAll('.sk-label.edit .sk-val')].map(l => l.textContent)")


try:
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "newModelBtn").click()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.8)
    click((0, 0))
    click((40, 20))
    print("rectangle labels:", labels())
    tool("round")
    print("hint:", js("return document.querySelector('#modelViewport .m-hint').textContent"))
    move((40.3, 19.8))
    print("hover:", js("return document.querySelector('.sk-label.hover')?.textContent"))
    ActionChains(d).click().perform()
    time.sleep(0.9)
    print("rounded (default):", arcs(), "| editor open:", bool(js("return document.querySelector('.sk-input')")))
    type_in_editor(5)
    print("R5:", arcs(), "| labels", labels())
    d.save_screenshot(f"{OUT}/round1.png")

    # the width (to the sharp corner, measuring) -> type 60: the rounded corner moves along, still R5
    lab = next(el for el in d.find_elements(By.CSS_SELECTOR, ".sk-label.edit") if el.find_element(By.CSS_SELECTOR, ".sk-val").text == "40")
    lab.find_element(By.CSS_SELECTOR, ".sk-val").click()
    type_in_editor(60)
    print("width 60:", arcs(), "| corner p3:", js(f"return {SK}.P('p3')"), "| dof", js(f"return {SK}.dof"))

    # a second corner (the origin corner), then undo it
    click((0, 0))
    type_in_editor(3)
    print("two corners:", len(arcs()), [a["r"] for a in arcs()])
    js(f"{SK}.back(); {SK}.back()")
    time.sleep(0.5)
    print("Ctrl+Z x2 -> one corner:", len(arcs()))

    tool("finish")
    settled()
    btns = d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=ok]")
    if btns:
        btns[0].click()
    settled()
    b = js(f"return {M}.result.body")
    h = js(f"return {M}.part.features.find(f => f.type === 'extrude').d")
    print("extruded:", round(b["volume"], 4), "| expected", round((60 * 20 - (4 - math.pi) / 4 * 25) * h, 4))
    js(f"{M}.view.setView('iso')")
    time.sleep(0.4)
    d.save_screenshot(f"{OUT}/round2_solid.png")

    # the AI: a plate with rounded corners
    call("new_model", name="Rounded plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40, "r": 6}}])
    r = json.loads(call("add_feature", type="extrude", sketch="F1", d=5))
    print("AI rounded plate:", r["ok"], r["body"]["volume_mm3"], "| expected", round(5 * (2400 - (4 - math.pi) * 36), 3))
    print("AI bad r:", call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 10, "h": 10, "r": 6}}]))
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
