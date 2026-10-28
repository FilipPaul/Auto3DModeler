"""Hover marks with no tool on, in headless Edge with real mouse moves: a block 40 × 20 × 10 with a Ø8 hole -> the mouse
on the hole's rim: that circle lit; on the top face: the step's snap points shown (corners, edge middles, the hole's
centre); ◔ Quadrants switched on: the hole's 4 quadrants too, off again; the hover filters (bottom left) switch each
off. Then the same block in an assembly: its rim lit, the hovered face's snap points; the mouse out: gone.

  PYTHONIOENCODING=utf-8 py tools/e2e_hover_marks.py http://127.0.0.1:5199 <out dir>
"""
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
M = "window.__app.modeler"
A = "window.__app.assembly"
H = "window.__app.agentHandlers"


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


def move_to(view, viewport, p):
    off = js(f"""const v = {view}, p = arguments[0];
      const [sx, sy] = v.toScreen(new (v.camera.position.constructor)(p[0], p[1], p[2])), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", p)
    cv = d.find_element(By.CSS_SELECTOR, f"#{viewport} canvas")
    ActionChains(d, duration=30).move_to_element_with_offset(cv, off[0] + 1, off[1] + 1).perform()
    time.sleep(0.15)
    ActionChains(d, duration=30).move_to_element_with_offset(cv, *off).perform()
    time.sleep(0.4)


def marks(view):
    return js(f"""const v = {view}, n = (g) => g ? g.children.length : 0;
      const pts = v.hoverSnapGroup?.children[0]?.geometry.attributes.position.count || 0;
      return {{edge: n(v.hoverEdgeGroup) > 0, edge_pts: v.hoverEdgeGroup?.children[0]?.geometry.attributes.position.count || 0, snaps: pts}}""")


def filt(attr, key):
    d.find_element(By.CSS_SELECTOR, f".snap-filters [{attr}={key}]").click()
    time.sleep(0.3)


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('a3d.snap3d'); localStorage.removeItem('a3d.hover3d')")
    call("new_model", name="Holed block")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    print("hole:", call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=8)[:40])
    time.sleep(0.5)
    wait(f"return !{M}.building && {M}.result?.body")
    js(f"{M}.view.setView('iso')")
    time.sleep(0.5)
    print("filters:", js("return [...document.querySelectorAll('.snap-filters button')].map(b => (b.classList.contains('on') ? '+' : '-') + b.textContent.trim())"))
    move_to(f"{M}.view", "modelViewport", [24, 10, 10])  # on the hole's rim (centre 20, 10; r 4)
    m = marks(f"{M}.view")
    print("on the rim: circle lit", m["edge"], "| its segments", m["edge_pts"] // 2)
    move_to(f"{M}.view", "modelViewport", [8, 4, 10])  # on the top face, away from edges
    m = marks(f"{M}.view")
    print("on the top face: edge lit", m["edge"], "| snap points", m["snaps"])
    filt("data-snap", "quadrant")  # (off unless asked for)
    move_to(f"{M}.view", "modelViewport", [9, 4, 10])
    print("  ◔ Quadrants on: snap points", marks(f"{M}.view")["snaps"])
    d.save_screenshot(f"{OUT}/hover_marks.png")
    filt("data-snap", "quadrant")
    move_to(f"{M}.view", "modelViewport", [9, 4, 10])
    print("  ◔ Quadrants off: snap points", marks(f"{M}.view")["snaps"])
    filt("data-hover", "points")
    move_to(f"{M}.view", "modelViewport", [8, 4, 10])
    print("  Hover • Snap points off:", marks(f"{M}.view")["snaps"], "| remembered", js("return localStorage.getItem('a3d.hover3d')"))
    filt("data-hover", "points")
    filt("data-hover", "edges")
    move_to(f"{M}.view", "modelViewport", [24, 10, 10])
    print("  Hover ⟋ Edges off: rim lit", marks(f"{M}.view")["edge"])
    filt("data-hover", "edges")
    call("new_assembly", name="Hovered")
    call("insert_part", part="Holed block")
    wait(f"return {A}.view.meshes?.length === 1")
    time.sleep(0.8)
    mat = js(f"return {A}.view.meshes[0].matrix.elements")
    w = lambda p: [mat[0] * p[0] + mat[4] * p[1] + mat[8] * p[2] + mat[12], mat[1] * p[0] + mat[5] * p[1] + mat[9] * p[2] + mat[13], mat[2] * p[0] + mat[6] * p[1] + mat[10] * p[2] + mat[14]]
    move_to(f"{A}.view", "asmViewport", w([24, 10, 10]))
    m = marks(f"{A}.view")
    print("assembly, on the rim: lit", m["edge"], "| the face's snap points", m["snaps"])
    d.save_screenshot(f"{OUT}/hover_marks_asm.png")
    ActionChains(d).move_to_element(d.find_element(By.CSS_SELECTOR, "#asmRight, .asm-right, #assemblyRight")).perform() if d.find_elements(By.CSS_SELECTOR, "#asmRight, .asm-right, #assemblyRight") else None
    time.sleep(0.4)
    print("mouse out:", marks(f"{A}.view"))
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
