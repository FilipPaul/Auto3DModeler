"""Mirror, with REAL mouse input in headless Edge. In a sketch: a rectangle and a circle -> ⇋ Mirror, Y axis -> a
click on the rectangle: its mirror image, joined on the axis? (no: it is 5 mm off) -> the circle too -> two ⇋ symbols
-> the original grows (a locked length) and the copy follows -> Move: the circle turned over the X axis (no copy) ->
mirror across a line of the sketch. Then in 3D: ⇋ Mirror across XZ (a copy, twice the volume) -> the same step
"Mirror only" (the volume stays, on the other side) -> the AI mirrors one hole across a face's plane.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_model_mirror.py http://127.0.0.1:5199 <out dir>
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


def click(uv):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *off(uv)).perform()
    time.sleep(0.15)
    ActionChains(d).click().perform()
    time.sleep(0.5)


def tool(t):
    d.find_element(By.CSS_SELECTOR, f".m-cmdbar [data-a={t}]").click()
    time.sleep(0.3)


def esc():
    d.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    time.sleep(0.3)


def P(k):
    return [round(v, 4) for v in js(f"return {SK}.P(arguments[0])", k)]


def ents(t):
    return js(f"return {SK}.f.entities.filter(e => e.t === arguments[0]).map(e => e.id)", t)


try:
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "newModelBtn").click()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.8)
    js(f"{M}.view.lookAt({M}.frame(), 120); {SK}.draw()")
    time.sleep(0.3)
    tool("rect")
    click((5, 0))
    click((25, 15))
    tool("circle")
    click((15, 30))
    click((19, 30))
    esc()
    print("drawn: lines", len(ents("line")), "circles", len(ents("circle")))

    tool("mirror")
    print("hint:", js("return document.querySelector('#modelViewport .m-hint').textContent"))
    print("box:", d.find_element(By.CSS_SELECTOR, ".sk-mirror").text.replace("\n", " | "))
    d.find_element(By.CSS_SELECTOR, ".sk-mirror [data-ax=y]").click()
    time.sleep(0.3)
    click((15, 0))  # the rectangle's bottom
    time.sleep(0.6)
    xs = sorted({round(p[0], 4) for p in js(f"return Object.values({SK}.f.points)")})
    print("after the rectangle: lines", len(ents("line")), "| point x:", xs)
    click((19, 30))  # the circle's edge
    time.sleep(0.6)
    cs = js(f"return {SK}.f.entities.filter(e => e.t === 'circle').map(e => [{SK}.P(e.c).map(v => +v.toFixed(4)), e.r])")
    print("circles:", cs)
    print("symbols:", [e.text for e in d.find_elements(By.CSS_SELECTOR, ".sk-rel")])
    d.save_screenshot(f"{OUT}/mirror1.png")
    with open(f"{OUT}/mirror_sketch.json", "w") as fh:
        json.dump(js(f"return {SK}.f"), fh)

    # the original grows: its bottom line locked at 30 long -> the copy follows
    bottom = js(f"""return {SK}.f.entities.find(e => e.t === 'line' && {SK}.P(e.a)[1] === 0 && {SK}.P(e.b)[1] === 0 && {SK}.P(e.a)[0] > 0).id""")
    js(f"return {SK}.relock(() => {SK}.f.dims.push({{ id: 'dz', t: 'len', e: arguments[0], v: 30 }}))", bottom)
    time.sleep(1)
    # (no position is locked, so the solver may grow it either way — the copy has to stay its mirror image)
    L = js(f"const e = {SK}.ent(arguments[0]), a = {SK}.P(e.a), b = {SK}.P(e.b); return Math.hypot(b[0] - a[0], b[1] - a[1])", bottom)
    asym = js(f"""return Math.max(...{SK}.f.constraints.filter(k => k.t === 'mir').flatMap(k => k.pairs).map(([p, q]) =>
      Math.hypot({SK}.P(p)[0] + {SK}.P(q)[0], {SK}.P(p)[1] - {SK}.P(q)[1])))""")
    print("original locked 30 long -> now", round(L, 4), "| the copy off its mirror place by at most", round(asym, 6), "mm")

    # Move: the circle turned over the X axis, no copy
    d.find_element(By.CSS_SELECTOR, ".sk-mirror [data-move]").click()
    d.find_element(By.CSS_SELECTOR, ".sk-mirror [data-ax=x]").click()
    time.sleep(0.3)
    c0 = js(f"return {SK}.f.entities.filter(e => e.t === 'circle').length")
    p = js(f"return {SK}.P({SK}.f.entities.find(e => e.t === 'circle').c)")
    click((p[0] + 4, p[1]))
    time.sleep(0.6)
    print("moved over the X axis: circles", c0, "->", js(f"return {SK}.f.entities.filter(e => e.t === 'circle').length"),
          "| centres", js(f"return {SK}.f.entities.filter(e => e.t === 'circle').map(e => {SK}.P(e.c).map(v => +v.toFixed(4)))"))
    esc()

    # across a line of the sketch
    tool("line")
    click((45, -40))
    click((45, 40))
    esc()
    esc()
    tool("mirror")
    click((45, 10))  # the line to mirror across
    print("box now:", d.find_element(By.CSS_SELECTOR, ".sk-mirror .hint").text)
    n0 = len(ents("line"))
    click((15, 15))  # the top of the first rectangle (now 30 wide: 5..35)
    time.sleep(0.6)
    xs = sorted({round(p[0], 4) for p in js(f"return Object.values({SK}.f.points)")})
    print("across x = 45: lines", n0, "->", len(ents("line")), "| point x:", xs)
    esc()
    d.save_screenshot(f"{OUT}/mirror2.png")

    # 3D: a plain plate, mirrored across XZ
    call("new_model", name="Bracket")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 5, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=6)
    call("add_feature", type="hole", face="F2:end", points=[[10, 0]], d=5)
    settled()
    v0 = js(f"return {M}.result.body.volume")
    tool("mirror")
    settled()
    print("3D panel:", d.find_element(By.CSS_SELECTOR, "#modelRight h2").text, "| planes", [b.text for b in d.find_elements(By.CSS_SELECTOR, "#modelRight [data-pl]")])
    print("YZ (default) -> volume", round(js(f"return {M}.result.body.volume"), 3), "of", round(v0, 3), "| bbox x", js(f"return {M}.result.body.bbox"))
    d.find_element(By.CSS_SELECTOR, "#modelRight [data-pl=XZ]").click()
    settled()
    b = js(f"return {M}.result.body")
    print("XZ copy: volume", round(b["volume"], 3), "= 2 ×", round(v0, 3), "| bbox y", b["bbox"][1], b["bbox"][4])
    d.find_element(By.CSS_SELECTOR, "#modelRight [data-copy='0']").click()
    settled()
    b = js(f"return {M}.result.body")
    print("XZ mirror only: volume", round(b["volume"], 3), "| bbox y", b["bbox"][1], b["bbox"][4])
    d.find_element(By.CSS_SELECTOR, "#modelRight [data-copy='1']").click()
    settled()
    d.find_element(By.CSS_SELECTOR, "#modelRight [data-a=ok]").click()
    settled()
    print("tree:", js("return [...document.querySelectorAll('#modelLeft .mt-item')].map(e => e.textContent.trim().replace(/\\s+/g, ' '))")[-1])
    js(f"{M}.view.setView('iso')")
    time.sleep(0.4)
    d.save_screenshot(f"{OUT}/mirror3.png")

    # the AI: only the hole, across the plate's right wall plane (x = 40 -> the hole at x 30 + 20 = 70: outside, so the
    # warning) and then across YZ shifted by the plate's middle
    r = json.loads(call("add_feature", type="mirror", of="F3", face="F2:side:l2"))
    print("AI mirror of the hole across the right wall:", r["ok"], "| warnings", [s.get("warnings") for s in r.get("steps", [])][-1:] if "steps" in r else r.get("warnings"))
    call("undo")
    settled()
    print("steps:", [s["type"] for s in json.loads(call("get_model"))["steps"]])
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
