"""The measure tool's snap points, with REAL mouse input: a 40 × 20 × 10 block with a Ø6 hole in the middle of its top ->
📏 Measure: the mouse near the middle of the top front edge: "midpoint" shown there; near a top corner: "corner"; near
the hole's centre: "centre" -> the snap filters: Corners off, a corner not caught -> a click on the corner, then on the hole's centre: their distance (the corner to the
middle of the top: √(20² + 10²)) -> the same in an assembly with the block.

  PYTHONIOENCODING=utf-8 py tools/e2e_measure_snap.py http://127.0.0.1:5199 <out dir>
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
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
H = "window.__app.agentHandlers"
M = "window.__app.modeler"
A = "window.__app.assembly"


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


def at(view, p):
    """A 3D point -> its offset from the canvas' middle (pixels)."""
    return js(f"""const v = {view}.view, V = v.camera.position.constructor, [sx, sy] = v.toScreen(new V(...arguments[0])), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(p))


def hover(view, sel, p, nudge=(4, -3)):
    o = at(view, p)
    ActionChains(d, duration=30).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, sel), o[0] + nudge[0], o[1] + nudge[1]).perform()
    time.sleep(0.4)
    return js("return [...document.querySelectorAll('.m-snap')].map(e => e.textContent).filter(Boolean)")


def click(view, sel, p, nudge=(4, -3)):
    hover(view, sel, p, nudge)
    ActionChains(d).click().perform()
    time.sleep(0.5)


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Block")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 20, "y": 10, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=6, through=True)
    wait(f"return {M}.result?.body && !{M}.inflight")
    js(f"{M}.view.setView('iso')")
    time.sleep(0.8)
    x0, y0, z0, x1, y1, z1 = js(f"return {M}.result.body.bbox")
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    print("the block:", [x0, y0, z0, x1, y1, z1])
    js(f"{M}.action('measure')")
    time.sleep(0.3)
    cv = "#modelViewport canvas"
    print("near the top front edge's middle:", hover(M, cv, [mx, y0, z1]))
    print("near a top corner:", hover(M, cv, [x0, y0, z1]))
    print("near the hole's centre:", hover(M, cv, [mx, my, z1], (3, 2)))
    bar = d.find_element(By.CSS_SELECTOR, "#modelViewport .snap-filters")
    print("the snap filters:", " | ".join(bar.text.splitlines()))
    bar.find_element(By.CSS_SELECTOR, "[data-snap=corner]").click()
    time.sleep(0.3)
    print("  Corners off — near a top corner:", hover(M, cv, [x0, y0, z1]))
    d.find_element(By.CSS_SELECTOR, "#modelViewport .snap-filters [data-snap=corner]").click()
    time.sleep(0.3)
    click(M, cv, [x0, y0, z1])
    click(M, cv, [mx, my, z1], (3, 2))
    box = d.find_element(By.CSS_SELECTOR, "#modelViewport .m-measure").text.replace("\n", " ")
    print("corner -> centre:", box[:80], "| expected", round(math.hypot(20, 10), 3))
    d.save_screenshot(f"{OUT}/measure_snap.png")
    js(f"{M}.action('measure')")

    call("new_assembly", name="Box")
    call("insert_part", part="Block")
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    js(f"{A}.view.setView('iso')")
    time.sleep(0.8)
    js(f"{A}.toggleMeasure()")
    time.sleep(0.3)
    cv = "#asmViewport canvas"
    print("assembly — near the edge's middle:", hover(A, cv, [mx, y0, z1]), "| the hole's centre:", hover(A, cv, [mx, my, z1], (3, 2)))
    click(A, cv, [x1, y0, z1])
    click(A, cv, [mx, my, z1], (3, 2))
    print("  corner -> centre:", d.find_element(By.CSS_SELECTOR, "#asmViewport .m-measure").text.replace("\n", " ")[:80])
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
