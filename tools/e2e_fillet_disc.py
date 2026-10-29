"""◜ Fillet on a disc with a hole (the AI's report: one click on the top outer edge, ⛓ Whole chain on, rounded the
hole's rim too — "2 edge(s)"), with REAL mouse clicks in headless Edge: a Ø70 × 10 disc, a Ø9.5 hole through at
(6, 13) -> no edge of it is in a tangent chain; ◜ Fillet, a click a little inside the top outer edge, on the top
face (where a click aimed at the edge lands) -> that edge alone, not the face's two; R2, OK -> "1 edge(s)", the
volume as Pappus says; a click on the edge itself -> that edge; a click in the middle of the top face still takes all
its edges (the outer circle and the hole's rim).

  PYTHONIOENCODING=utf-8 py tools/e2e_fillet_disc.py http://127.0.0.1:5199 <out dir>
"""
import math
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1400,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"
H = "window.__app.agentHandlers"
fails = []


def check(what, ok, *more):
    print("OK  " if ok else "FAIL", what, *more)
    if not ok:
        fails.append(what)


def wait(script, t=120):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(script)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def settled():
    time.sleep(0.3)
    wait(f"return !{M}.inflight && !!{M}.result")


def canvas():
    return js(f"return {M}.view.renderer.domElement")


def off_xyz(p):
    """A model point -> its offset from the view's middle in pixels (as ActionChains takes it)."""
    return js(f"""const v = {M}.view, [x, y, z] = arguments[0];
      const [sx, sy] = v.toScreen(new (v.camera.position.constructor)(x, y, z)), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(p))


def move_to(o):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *o).perform()
    time.sleep(0.3)


def click_at(o):
    move_to(o)
    ActionChains(d).click().perform()
    time.sleep(0.4)


def picked():
    return js(f"return [{M}.cmd.feature.edges.map(e => [e.a, e.b].sort().join(' | ')), {M}.cmd.lastPick]")


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Disc")
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 70}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    settled()
    r = call("add_feature", type="hole", face="F2:end", points=[[6, 13]], d=9.5, through=True)
    settled()
    v0 = js(f"return {M}.result.body.volume")
    check("the disc with its hole", abs(v0 - math.pi * (35 ** 2 - 4.75 ** 2) * 10) < 0.01, v0, r[:80])
    check("no edge of it in a tangent chain", not js(f"return {M}.result.body.edges.some(e => e.chain !== undefined)"))
    call("set_view", view="iso")
    time.sleep(0.4)

    d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=fillet]").click()
    wait(f"return {M}.cmd?.feature?.type === 'fillet'")
    check("⛓ Whole chain on (the default)", js("return document.querySelector('#modelRight input[data-k=chain]').checked"))

    # a click aimed at the edge that lands a little inside it, on the top face
    o = off_xyz([0, -33.5, 10])
    e = off_xyz([0, -35, 10])
    gap = math.hypot(o[0] - e[0], o[1] - e[1])
    move_to(o)
    hover = js(f"const v = {M}.view, r = v.renderer.domElement.getBoundingClientRect(); return [v.pickEdge(r.left + r.width / 2 + arguments[0], r.top + r.height / 2 + arguments[1], 16), v.pick(r.left + r.width / 2 + arguments[0], r.top + r.height / 2 + arguments[1])?.face?.name]", *o)
    check(f"the point is on the top face, {gap:.0f} px inside the edge", hover[1] == "F2:end" and 4 < gap < 16, hover, gap)
    ActionChains(d).click().perform()
    time.sleep(0.4)
    p = picked()
    check("a click just inside the edge: that edge, not the top face's two", p[0] == ["F2:end | F2:side:c1"], p)
    js(f"const i = document.querySelector('#modelRight input[data-k=r]'); i.value = 2; i.dispatchEvent(new Event('input', {{bubbles: true}})); i.dispatchEvent(new Event('change', {{bubbles: true}}));")
    time.sleep(0.3)
    settled()
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=ok]").click()
    settled()
    f = js(f"return {M}.part.features.at(-1)")
    xbar = 2 * (10 - 3 * math.pi) / (12 - 3 * math.pi)
    want = v0 - (4 - math.pi) * 2 * math.pi * (35 - xbar)
    v = js(f"return {M}.result.body.volume")
    check("R2 on 1 edge: the volume (Pappus)", f["type"] == "fillet" and f["r"] == 2 and len(f["edges"]) == 1 and abs(v - want) < 0.05, f.get("r"), len(f["edges"]), v, want)
    check("the step says 1 edge(s)", "1 edge(s)" in js(f"return {M}.whatText({M}.part.features.at(-1))"), js(f"return {M}.whatText({M}.part.features.at(-1))"))
    d.save_screenshot(f"{OUT}/fillet_disc.png")

    # on the edge itself: that edge alone; in the middle of the top face: all its edges (the circle and the hole's rim)
    call("undo")
    settled()
    d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=fillet]").click()
    wait(f"return {M}.cmd?.feature?.type === 'fillet'")
    click_at(off_xyz([0, -35, 10]))
    p = picked()
    check("a click on the top outer edge: that edge alone", p[0] == ["F2:end | F2:side:c1"] and p[1].startswith("Added the edge"), p)
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=cancel]").click()
    settled()
    d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=fillet]").click()
    wait(f"return {M}.cmd?.feature?.type === 'fillet'")
    click_at(off_xyz([-15, -10, 10]))
    p = picked()
    check("a click in the face's middle: all its edges (2)", len(p[0]) == 2 and "edge(s) of" in p[1], p)
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=cancel]").click()
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    d.quit()
print("FAILED:", fails if fails else "none")
sys.exit(1 if fails else 0)
