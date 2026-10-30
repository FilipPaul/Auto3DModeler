"""⊕ The origin lit like a snap point, in Czech, with REAL mouse input: a 20 × 10 × 10 block away from the origin ->
the sketch (✏ Line): the mouse near 0, 0 -> the marker and "Počátek"; a line drawn from there starts at exactly [0, 0] ->
the 3D model (no tool on): the mouse at the origin -> "Počátek", on its X arrow -> "Osa X"; Přichytit: Rohy off -> not
caught -> 📏 Měření: the origin picked, then a corner: their distance -> a hole spot on a face over the origin snaps
to it -> an assembly: the origin named there too. No console errors.

  PYTHONIOENCODING=utf-8 py tools/e2e_origin_hover.py http://127.0.0.1:5199 <out dir>
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
d.set_script_timeout(60)
js = d.execute_script
H = "window.__app.agentHandlers"
M = "window.__app.modeler"
A = "window.__app.assembly"
SK = f"{M}.sk"
STEP_ROW = ("const m = window.__app.modeler; m.part.features.forEach(f => m.openTo(f.id)); m.renderTree(); "
            "return document.querySelector(`#modelLeft .mt-item[data-id=\"${m.part.features[arguments[0]].id}\"]`)")


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def check(what, ok, detail=""):
    print(("OK   " if ok else "FAIL ") + what, detail)
    if not ok:
        raise SystemExit(1)


def at(view, p):
    """A 3D point -> its offset from the canvas' middle (pixels)."""
    return js(f"""const v = {view}.view, V = v.camera.position.constructor, [sx, sy] = v.toScreen(new V(...arguments[0])), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(p))


def move(view, sel, p, nudge=(4, -3)):
    o = at(view, p)
    ActionChains(d, duration=30).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, sel), o[0] + nudge[0], o[1] + nudge[1]).perform()
    time.sleep(0.4)


def iso(view):
    """Seen from the side, the origin in the view too (aimed between it and the part, from a little farther)."""
    js(f"""const v = {view}.view; v.setView('iso'); const c = v.controls.target.clone().multiplyScalar(0.5), dir = v.camera.position.clone().sub(v.controls.target);
      v.controls.target.copy(c); v.camera.position.copy(c).addScaledVector(dir, 1.8); v.controls.update(); v.invalidate();""")
    time.sleep(0.8)


def snaps():
    return js("return [...document.querySelectorAll('.m-snap')].map(e => e.textContent).filter(Boolean)")


def click(view, sel, p, nudge=(4, -3)):
    move(view, sel, p, nudge)
    ActionChains(d).click().perform()
    time.sleep(0.5)


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.setItem('auto3d-lang', 'cs'); localStorage.removeItem('a3d.snap'); localStorage.removeItem('a3d.sksnap')")
    d.get(URL)
    wait("return !!window.__app")
    check("Czech", js("return document.documentElement.lang") == "cs")
    cv = "#modelViewport canvas"

    print("1. the sketch: the origin lit and named, a line from it")
    call("new_model", name="Blok")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 8, "y": 6, "w": 20, "h": 10}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    wait(f"return !!{M}.result?.body && !{M}.inflight")
    ActionChains(d).double_click(js(STEP_ROW, 0)).perform()
    wait(f"return {M}.mode === 'sketch' && {SK}?.dof !== null", 10)
    js(f"{M}.view.lookAt({M}.frame(), 120); {SK}.setTool('line'); {SK}.draw()")
    time.sleep(0.6)
    move(M, cv, [0, 0, 0])
    lab = js("return [...document.querySelectorAll('.sk-label.hover')].map(e => e.textContent)")
    hv = js(f"return {SK}.hover")
    check("near 0, 0: the marker on the origin and 'Počátek'", hv and hv.get("end") == "O" and hv.get("uv") == [0, 0] and "Počátek" in lab, (hv, lab))
    ActionChains(d).click().perform()
    time.sleep(0.4)
    move(M, cv, [12, 7, 0], (0, 0))
    ActionChains(d).click().perform()
    time.sleep(0.6)
    ActionChains(d).send_keys("").perform()  # Esc: the line tool ends
    time.sleep(0.6)
    line = js(f"const s = {SK}, e = s.f.entities.filter(x => x.t === 'line').at(-1); return e && [s.P(e.a), s.P(e.b)]")
    check("the line starts at exactly [0, 0]", line and line[0] == [0, 0], line)
    d.save_screenshot(f"{OUT}/origin_sketch.png")
    js(f"{M}.cancelSketch()")  # (✕ Cancel: the part as it was)
    wait(f"return {M}.mode === 'part' && !{M}.inflight && !!{M}.result?.body")

    print("2. the 3D model: the origin and its arrows named")
    iso(M)
    move(M, cv, [0, 0, 0])
    check("no tool on, at the origin: 'Počátek'", "Počátek" in snaps(), snaps())
    k = js(f"return {M}.view.origin.scale.x")
    move(M, cv, [k * 0.6, 0, 0], (0, 0))
    tip = js("return document.querySelector('#modelViewport .m-tip:not([hidden])')?.textContent || ''")
    check("on its X arrow: 'Osa X'", tip == "Osa X", tip)
    bar = d.find_element(By.CSS_SELECTOR, "#modelViewport .snap-filters")
    print("  the snap filters:", " | ".join(bar.text.splitlines()))
    bar.find_element(By.CSS_SELECTOR, "[data-snap=corner]").click()
    time.sleep(0.3)
    move(M, cv, [0, 0, 0])
    check("Přichytit: Rohy off -> the origin not caught", "Počátek" not in snaps(), snaps())
    d.find_element(By.CSS_SELECTOR, "#modelViewport .snap-filters [data-snap=corner]").click()
    time.sleep(0.3)

    print("3. 📏 Měření: from the origin")
    js(f"{M}.action('measure')")
    time.sleep(0.4)
    move(M, cv, [0, 0, 0])
    check("📏 at the origin: 'Počátek'", "Počátek" in snaps(), snaps())
    x0, y0, z0, x1, y1, z1 = js(f"return {M}.result.body.bbox")
    click(M, cv, [0, 0, 0])
    click(M, cv, [x1, y0, z1], (-3, 3))
    row = js("return [...document.querySelectorAll('[data-w=measure-model] .ms-row')].at(-1)?.innerText.replace(/\\s+/g, ' ') || ''")
    want = math.sqrt(x1 * x1 + y0 * y0 + z1 * z1)
    print("  row:", row, "| expected", round(want, 3))
    check("the origin picked and measured to the corner", "Počátek" in row and f"{want:.3f}" in row, row)
    d.save_screenshot(f"{OUT}/origin_measure.png")
    js(f"{M}.action('measure')")
    time.sleep(0.3)

    print("4. a hole on a face over the origin snaps to it")
    call("new_model", name="Deska")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": -10, "y": -5, "w": 40, "h": 30}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    wait(f"return !!{M}.result?.body && !{M}.inflight")
    near = d.execute_async_script(f"""const done = arguments[arguments.length - 1];
      import('/js/modeler/facesnap.js').then(({{ snapOnFace }}) => {{
        const v = {M}.view, f = v.body.faces.find(x => x.type === 'plane' && x.normal[2] > 0.9);
        const fr = {{ o: [5, 3, 5], x: [1, 0, 0], n: [0, 0, 1] }}, s = snapOnFace(v, {{ face: f, fr, uv: [-4.7, -3.2], mpp: 0.1 }});
        done([s.kind, s.uv, s.name]);
      }}).catch(e => done(String(e)));""")
    check("a spot near the origin's place on the top face snaps to it", near and near[0] == "origin" and near[1] == [-5, -3], near)

    print("5. an assembly: the origin named")
    call("new_assembly", name="Sestava")
    call("insert_part", part="Blok")
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    iso(A)
    move(A, "#asmViewport canvas", [0, 0, 0], (2, -2))  # (no tool on: within 5 px)
    asm = snaps()
    check("assembly, no tool on, at the origin: 'Počátek'", "Počátek" in asm, asm)
    k = js(f"return {A}.view.origin.scale.x")
    move(A, "#asmViewport canvas", [0, 0, k * 0.6], (0, 0))
    tip = js("return document.querySelector('#asmViewport .as-dragtip')?.textContent || ''")
    check("on its Z arrow: 'Osa Z'", tip == "Osa Z", tip)
    d.save_screenshot(f"{OUT}/origin_assembly.png")
    print("ALL OK")
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    d.quit()
    if errs:
        raise SystemExit(1)
