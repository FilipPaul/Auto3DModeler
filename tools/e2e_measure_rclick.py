"""📏 Measure's right-click, with REAL mouse input (Czech): a 40 × 20 × 10 block -> 📏 Measure, a corner clicked (the
first pick waits) -> a right-click: the measurement ends (no pick waiting, its row stays, the tool still on; the hint
says "Pravé tlačítko: …") -> a right-drag turns / pans the view and leaves the tool on -> a right-click with nothing
picked: the tool closes. No browser menu (the contextmenu event cancelled) and no app menu opens. The same in an
assembly with the block, and in a 📐 2D drawing's Measure (a DXF plate).

  PYTHONIOENCODING=utf-8 py tools/e2e_measure_rclick.py http://127.0.0.1:5199 <out dir>
"""
import os
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from selenium.webdriver.common.actions.mouse_button import MouseButton
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
D = "window.__app.drawing2d"
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


def check(ok, what):
    print(("OK   " if ok else "FAIL ") + what)
    if not ok:
        fails.append(what)


def at(view, p):
    """A 3D point -> its offset from the canvas' middle (pixels)."""
    return js(f"""const v = {view}.view, V = v.camera.position.constructor, [sx, sy] = v.toScreen(new V(...arguments[0])), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(p))


def click(view, sel, p, nudge=(4, -3)):
    o = at(view, p)
    ActionChains(d, duration=30).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, sel), o[0] + nudge[0], o[1] + nudge[1]).perform()
    time.sleep(0.3)
    ActionChains(d).click().perform()
    time.sleep(0.5)


def rclick(sel, dx=-250, dy=-200):
    """A right-click on empty space of the view (its default menu: was it cancelled?)."""
    js("window.__ctx = []; if (!window.__ctxOn) { window.__ctxOn = true; window.addEventListener('contextmenu', (e) => window.__ctx.push(e.defaultPrevented)); }")
    ActionChains(d, duration=30).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, sel), dx, dy).context_click().perform()
    time.sleep(0.5)
    return js("return window.__ctx")


def rdrag(sel, dx=-250, dy=-200):
    """A right-drag of 120 px (the view turns / pans)."""
    ActionChains(d, duration=30).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, sel), dx, dy).perform()
    ab = ActionBuilder(d, duration=30)
    ab.pointer_action.pointer_down(MouseButton.RIGHT)
    for k in range(1, 7):
        ab.pointer_action.move_by(20, 0)
    ab.pointer_action.pointer_up(MouseButton.RIGHT)
    ab.perform()
    time.sleep(0.5)


def menus():
    """App menus open (a context menu, a menu list)."""
    return js("return [...document.querySelectorAll('.ctx-menu, .m-ctx, .menu-list, .context-menu')].filter(e => e.offsetParent).length")


def rows(ws):
    return js(f"return document.querySelectorAll('[data-w=measure-{ws}] .ms-row').length")


def cam(view):
    return js(f"const c = {view}.view.camera.position, t = {view}.view.controls.target; return [c.x, c.y, c.z, t.x, t.y, t.z].map(v => +v.toFixed(3))")


def flow(view, ws, sel, corner):
    """Measure on, a corner picked, right-click: ended; right-drag: the view moves; right-click: the tool closes."""
    on = lambda: js(f"return !!{view}.measuring")  # noqa: E731
    pend = lambda: js(f"return !!{view}.ms.pend")  # noqa: E731
    js(f"{view}.measuring || {view}.toggleMeasure()") if ws == "assembly" else js(f"{view}.measuring || {view}.action('measure')")
    time.sleep(0.3)
    n0 = rows(ws)
    click(view, sel, corner)
    check(pend() and rows(ws) == n0 + 1, f"{ws}: a corner picked — waiting for the second (rows {n0} -> {rows(ws)})")
    hint = js("return [...document.querySelectorAll('.m-hint')].filter(e => e.offsetParent).map(e => e.textContent).join(' | ')")
    check("Pravé tlačítko: ukončit měření" in hint, f"{ws}: the hint says the right-click: {hint!r}")
    ctx = rclick(sel)
    check(on() and not pend() and rows(ws) == n0 + 1, f"{ws}: right-click — the measurement ended, its row stays ({rows(ws)}), the tool on")
    check(ctx and all(ctx) and not menus(), f"{ws}: no browser menu (contextmenu cancelled: {ctx}), no app menu ({menus()})")
    c0 = cam(view)
    rdrag(sel)
    c1 = cam(view)
    check(c0 != c1 and on(), f"{ws}: a right-drag moves the view ({c0} -> {c1}) and keeps the tool on")
    hint = js("return [...document.querySelectorAll('.m-hint')].filter(e => e.offsetParent).map(e => e.textContent).join(' | ')")
    check("Pravé tlačítko: zavřít nástroj" in hint, f"{ws}: nothing picked — the hint: {hint!r}")
    ctx = rclick(sel)
    check(not on() and rows(ws) == n0 + 1, f"{ws}: right-click with nothing picked — the tool closed, the rows stay")
    check(ctx and all(ctx) and not menus(), f"{ws}: still no menu ({ctx}, {menus()})")
    ctx = rclick(sel)
    check(not on(), f"{ws}: another right-click with the tool off does nothing to it")


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.setItem('auto3d-lang', 'cs')")
    d.refresh()
    wait("return !!window.__app")
    call("new_model", name="Block")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 20, "y": 10, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    wait(f"return {M}.result?.body && !{M}.inflight")
    js(f"{M}.view.setView('iso')")
    time.sleep(0.8)
    x0, y0, z0, x1, y1, z1 = js(f"return {M}.result.body.bbox")
    flow(M, "model", "#modelViewport canvas", [x0, y0, z1])
    d.save_screenshot(f"{OUT}/measure_rclick_model.png")

    call("new_assembly", name="Box")
    call("insert_part", part="Block")
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    js(f"{A}.view.setView('iso')")
    time.sleep(0.8)
    flow(A, "assembly", "#asmViewport canvas", [x1, y0, z1])

    # 📐 a 2D drawing: its own Measure (two spots)
    import ezdxf
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    doc.modelspace().add_lwpolyline([(0, 0), (100, 0), (100, 60), (0, 60)], close=True)
    dxf = os.path.abspath(os.path.join(OUT, "measure_rclick_plate.dxf"))
    doc.saveas(dxf)
    d.find_element(By.ID, "cadInput").send_keys(dxf)
    wait("return window.__app.state.workspace === 'drawing'")
    time.sleep(0.8)
    d.find_element(By.CSS_SELECTOR, "#dwgViewport .dw-bar [data-a=measure]").click()
    time.sleep(0.2)
    s = js(f"return {D}.toScreen([0, 0])")
    cv = d.find_element(By.CSS_SELECTOR, "#dwgViewport canvas")
    w, h = js("const r = arguments[0].getBoundingClientRect(); return [r.width, r.height]", cv)
    ActionChains(d, duration=30).move_to_element_with_offset(cv, round(s[0] - w / 2) + 1, round(s[1] - h / 2) - 1).perform()
    time.sleep(0.15)
    ActionChains(d).click().perform()
    time.sleep(0.3)
    check(js(f"return !!{D}.measure?.a && !{D}.measure.b"), "drawing: a first spot picked")
    ctx = rclick("#dwgViewport canvas", 200, 150)
    check(js(f"return {D}.tool") == "measure" and not js(f"return !!{D}.measure"), f"drawing: right-click — the measurement ended, Measure still on ({ctx})")
    v0 = js(f"return [{D}.view.cx, {D}.view.cy]")
    rdrag("#dwgViewport canvas", 200, 150)
    check(js(f"return [{D}.view.cx, {D}.view.cy]") != v0 and js(f"return {D}.tool") == "measure", "drawing: a right-drag pans, Measure stays on")
    ctx = rclick("#dwgViewport canvas", 200, 150)
    check(js(f"return {D}.tool") == "select" and ctx and all(ctx), f"drawing: right-click with nothing picked — back to Select ({ctx})")
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        fails.append("console errors")
    d.quit()
print("FAILED:" if fails else "ALL OK", fails if fails else "")
sys.exit(1 if fails else 0)
