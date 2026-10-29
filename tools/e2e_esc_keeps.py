"""Esc in a tool that places things click after click KEEPS what was placed (as OK); with nothing placed it cancels;
the Cancel button throws it all away. In headless Edge, with real mouse clicks and keys: a new model -> the sketch's
╱ Line: 3 clicks (2 segments), Esc -> the 2 lines stay, the chain ends; the outline closed -> a 40 × 40 × 10 block ->
◎ Hole: 1 click, Esc -> a hole step with 1 position (volume: one Ø5 through hole) and a toast; ◎ Hole, Esc at once ->
no step; ◎ Hole: 1 click, Cancel -> no step -> Fillet: 1 edge, Esc -> a fillet step with 1 edge; Fillet, Esc at once ->
no step.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_esc_keeps.py http://127.0.0.1:5199 <out dir>
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
H = "window.__app.agentHandlers"
M = "window.__app.modeler"
SK = f"{M}.sk"
CV = "#modelViewport canvas"
fails = []


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(script)


def check(what, ok):
    print(("  ok  " if ok else "  FAIL") + " " + what)
    if not ok:
        fails.append(what)


def settled():
    time.sleep(0.6)
    wait(f"return !{M}.inflight")
    time.sleep(0.4)


def canvas():
    return d.find_element(By.CSS_SELECTOR, CV)


def off_uv(uv):
    """A point of the open sketch (u, v) -> its offset from the canvas' middle (pixels)."""
    return js(f"""const m = {M}, v = m.view, f = m.frame(), [u, w] = arguments[0];
      const y = [f.n[1]*f.x[2]-f.n[2]*f.x[1], f.n[2]*f.x[0]-f.n[0]*f.x[2], f.n[0]*f.x[1]-f.n[1]*f.x[0]];
      const p = new (v.camera.position.constructor)(f.o[0] + u*f.x[0] + w*y[0], f.o[1] + u*f.x[1] + w*y[1], f.o[2] + u*f.x[2] + w*y[2]);
      const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(uv))


def off_3d(p):
    """A 3D point -> its offset from the canvas' middle (pixels)."""
    return js(f"""const v = {M}.view, V = v.camera.position.constructor, [sx, sy] = v.toScreen(new V(...arguments[0])), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(p))


def click_at(o):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *o).perform()
    time.sleep(0.3)
    ActionChains(d).click().perform()
    time.sleep(0.5)


def esc():
    ActionChains(d).send_keys(Keys.ESCAPE).perform()
    time.sleep(0.4)


def steps(kind):
    return [f for f in js(f"return {M}.part.features") if f["type"] == kind]


def toasts():
    return " | ".join(e.text for e in d.find_elements(By.CSS_SELECTOR, ".toast"))


try:
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "newModelBtn").click()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.8)

    # ---- the sketch: ╱ Line, 3 clicks (2 segments), Esc: they stay, the chain ends
    d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=line], #modelViewport .view-actions [data-a=line]").click()
    time.sleep(0.2)
    for uv in ((0, 0), (40, 0), (40, 40)):
        click_at(off_uv(uv))
    esc()
    n = js(f"return {SK}.f.entities.filter(e => e.t === 'line').length")
    print("lines after Esc:", n, "| chain", js(f"return {SK}.chain"), "| tool", js(f"return {SK}.tool"))
    check("sketch: Esc ends the line, the 2 segments stay", n == 2 and js(f"return !{SK}.chain") and js(f"return {SK}.tool") == "line")
    for uv in ((40, 40), (0, 40), (0, 0)):  # (on: from where it ended, round to the start — it closes)
        click_at(off_uv(uv))
    check("sketch: the outline closed (4 lines)", js(f"return {SK}.f.entities.filter(e => e.t === 'line').length") == 4)
    esc()
    check("sketch: a second Esc leaves the tool", js(f"return {SK}.tool") == "select")
    sk = js(f"return {SK}.f.id")
    ActionChains(d).send_keys(Keys.ENTER).perform()
    wait(f"return {M}.mode === 'part'")
    call("add_feature", type="extrude", sketch=sk, d=10)
    settled()
    v0 = js(f"return {M}.result.body.volume")
    print("the block:", js(f"return {M}.result.body.bbox"), "volume", v0)
    check("a 40 × 40 × 10 block", abs(v0 - 16000) < 1)
    js(f"{M}.view.setView('top')")
    time.sleep(0.6)

    # ---- ◎ Hole: one click, Esc -> kept
    js(f"{M}.action('hole')")
    time.sleep(0.4)
    click_at(off_3d([12, 20, 10]))
    print("placed:", js(f"return {M}.cmd?.feature.points"))
    esc()
    settled()
    hs = steps("hole")
    print("after Esc:", "cmd" if js(f"return !!{M}.cmd") else "no cmd", "| holes", [(h["id"], h["points"]) for h in hs], "|", toasts())
    check("hole: Esc ended the tool", js(f"return !{M}.cmd"))
    check("hole: the step kept with its 1 position", len(hs) == 1 and len(hs[0]["points"]) == 1)
    v = js(f"return {M}.result.body.volume")
    check(f"hole: the volume is the block minus one Ø5 hole ({v:.2f})", abs(v - (16000 - math.pi * 2.5 ** 2 * 10)) < 0.5)
    check("hole: a toast says it was kept", "kept" in toasts() or "uloženo" in toasts())
    d.save_screenshot(f"{OUT}/esc_hole.png")

    # ---- ◎ Hole, Esc with nothing placed -> cancelled
    js(f"{M}.action('hole')")
    time.sleep(0.4)
    esc()
    settled()
    check("hole: Esc with nothing placed adds no step", len(steps("hole")) == 1 and js(f"return !{M}.cmd"))

    # ---- ◎ Hole, a click, then the Cancel button -> thrown away
    js(f"{M}.action('hole')")
    time.sleep(0.4)
    click_at(off_3d([28, 20, 10]))
    placed = js(f"return {M}.cmd?.feature.points.length")
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=cancel]").click()
    settled()
    check(f"hole: Cancel throws the placed position away ({placed} placed)", placed == 1 and len(steps("hole")) == 1)

    # ---- Fillet: one edge, Esc -> kept; nothing, Esc -> no step
    js(f"{M}.view.setView('iso')")
    time.sleep(0.6)
    js(f"{M}.action('fillet')")
    time.sleep(0.4)
    click_at(off_3d([40, 20, 10]))  # the top edge on the right
    print("edges picked:", js(f"return {M}.cmd?.feature.edges.length"))
    esc()
    settled()
    fs = steps("fillet")
    print("fillets:", [(f["id"], len(f["edges"]), f["r"]) for f in fs], "|", toasts())
    check("fillet: Esc kept the step with its 1 edge", len(fs) == 1 and len(fs[0]["edges"]) == 1 and js(f"return !{M}.cmd"))
    st = js(f"return {M}.result.features.find(s => s.id === arguments[0])", fs[0]["id"] if fs else "")
    check("fillet: it builds (the volume went down)", bool(st and st["ok"]) and js(f"return {M}.result.body.volume") < v - 0.05)
    js(f"{M}.action('fillet')")
    time.sleep(0.4)
    esc()
    settled()
    check("fillet: Esc with nothing picked adds no step", len(steps("fillet")) == 1 and js(f"return !{M}.cmd"))
    d.save_screenshot(f"{OUT}/esc_fillet.png")
finally:
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        fails.append("console errors")
    d.quit()

print("FAILED:" if fails else "ALL OK", fails if fails else "")
sys.exit(1 if fails else 0)
