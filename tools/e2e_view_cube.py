"""The view cube (top right of the 3D model's and the assembly's view), with REAL clicks in headless Edge at 1280×800:
the command bar without the Iso / Top / Front / Right buttons (its height now and with them, as before) and clear of the
cube -> a click on TOP looks from above (+Y up) -> ⌂ the iso view -> FRONT -> a corner: the iso view from it -> an edge:
from between its two faces -> the hover lights a corner's three parts -> action('view-right') still works -> in a sketch:
the cube turns the view and a rectangle can still be drawn -> the assembly's cube -> the Czech labels.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_view_cube.py http://127.0.0.1:5199 <out dir>
"""
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1280,800")
opts.add_argument("--lang=en-US")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"
A = "window.__app.assembly"
H = "window.__app.agentHandlers"
ok = []


def check(name, cond):
    ok.append(bool(cond))
    print(f"  {name}: {'OK' if cond else 'FAIL'}")


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def cam(w=M):
    """Where the camera looks from (a unit vector from the target, rounded) and its up."""
    return js(f"""const v = {w}.view, c = v.camera, o = c.position.clone().sub(v.controls.target).normalize();
      return [o.toArray().map(x => +x.toFixed(2) + 0), c.up.toArray().map(x => +x.toFixed(2) + 0)]""")


def near(a, b, tol=0.03):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def cube_cell(dir_, vp="#modelViewport"):
    """The cube's cell looking from dir_ on a face turned to us (an edge or a corner has one on each face it is on)."""
    return next(e for e in d.find_elements(By.CSS_SELECTOR, f'{vp} .view-cube [data-dir="{dir_}"]') if e.is_displayed())


def cube_click(dir_, vp="#modelViewport"):
    ActionChains(d, duration=30).move_to_element(cube_cell(dir_, vp)).pause(0.15).click().perform()
    time.sleep(0.5)


def bar_height(vp="#modelViewport"):
    """The bar's height now, and with the old view buttons put back (as it was before the cube) -> [now, before]."""
    return js(f"""const bar = document.querySelector('{vp} > .m-cmdbar'), now = bar.offsetHeight;
      const extra = document.createElement('span');
      extra.innerHTML = '<span class="sep"></span>' + ['Iso', 'Top', 'Front', 'Right'].map(l => `<button class="chip">${{l}}</button>`).join('');
      bar.append(...extra.childNodes);
      const before = bar.offsetHeight;
      for (const e of [...bar.children].slice(-5)) e.remove();
      return [now, before]""")


def clear_of_cube(vp="#modelViewport"):
    """The cube is under the bar, and the hint (when shown) beside it."""
    return js(f"""const c = document.querySelector('{vp} .view-cube').getBoundingClientRect(), b = document.querySelector('{vp} > .m-cmdbar');
      const h = document.querySelector('{vp} > .m-hint'), hr = h && !h.hidden && h.getBoundingClientRect();
      return b.getBoundingClientRect().bottom <= c.top && (!hr || hr.right < c.left)""")


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('auto3d-lang')")
    call("new_model", name="Block")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=20)
    wait(f"return !!{M}.result?.body && !{M}.inflight")
    js(f"{M}.view.setView('iso')")
    time.sleep(0.6)
    now, before = bar_height()
    print(f"3D model bar at 1280x800: {now} px now, {before} px with the view buttons (before)")
    check("the bar is no higher than before (its 4 rows at this width are all tools)", now <= before)
    check("no view buttons in the bar", not d.find_elements(By.CSS_SELECTOR, "#modelViewport .m-cmdbar [data-a^=view-]"))
    check("the cube is under the bar, the hint beside it", clear_of_cube())
    box = d.find_element(By.CSS_SELECTOR, "#modelViewport .view-cube").rect
    vp = d.find_element(By.CSS_SELECTOR, "#modelViewport").rect
    print("the cube:", box, "| the view:", vp)
    check("the cube is ~70-90 px, top right", 60 <= box["width"] <= 95 and vp["x"] + vp["width"] - (box["x"] + box["width"]) < 20
          and box["y"] - vp["y"] < vp["height"] / 3)
    d.save_screenshot(f"{OUT}/view_cube_model.png")

    cube_click("0,0,1")
    print("TOP:", cam())
    check("TOP looks from above, +Y up", near(cam()[0], [0, 0, 1]) and near(cam()[1], [0, 1, 0]))
    cube_click("iso")
    print("⌂:", cam())
    check("⌂ is the iso view", near(cam()[0], [0.43, -0.71, 0.55]))
    cube_click("0,-1,0")
    print("FRONT:", cam())
    check("FRONT looks from the front, Z up", near(cam()[0], [0, -1, 0]) and near(cam()[1], [0, 0, 1]))
    dist = js(f"const v = {M}.view; return Math.round(v.camera.position.distanceTo(v.controls.target))")
    cube_click("1,-1,1")
    print("the front-right-top corner:", cam())
    check("a corner: the iso view from it", near(cam()[0], [0.58, -0.58, 0.58]))
    check("the same distance (fitted)", abs(js(f"const v = {M}.view; return Math.round(v.camera.position.distanceTo(v.controls.target))") - dist) <= 1)
    ActionChains(d, duration=30).move_to_element(cube_cell("1,-1,1")).perform()
    time.sleep(0.3)
    lit = js("return [...document.querySelectorAll('#modelViewport .view-cube .hi')].map(e => e.dataset.dir)")
    print("hover on the corner lights:", lit)
    check("the corner's three parts light up", lit == ["1,-1,1"] * 3)
    d.save_screenshot(f"{OUT}/view_cube_corner.png")
    cube_click("0,-1,1")
    print("the front-top edge:", cam())
    check("an edge: from between its faces", near(cam()[0], [0, -0.71, 0.71]))
    js(f"{M}.action('view-right')")
    time.sleep(0.3)
    print("action('view-right'):", cam())
    check("action('view-…') still works", near(cam()[0], [1, 0, 0]))

    # a sketch: the cube turns the view, drawing still works
    d.find_element(By.CSS_SELECTOR, "#modelViewport .m-cmdbar [data-a=sketch]").click()
    time.sleep(0.5)
    d.find_element(By.CSS_SELECTOR, "#modelViewport .m-cmdbar [data-a=datum-XY]").click()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.6)
    check("the cube shows in a sketch", d.find_element(By.CSS_SELECTOR, "#modelViewport .view-cube").is_displayed())
    cube_click("iso")
    print("sketch, ⌂:", cam(), "| still sketching:", js(f"return {M}.mode"))
    n0 = js(f"return {M}.sk.f.entities.length")
    cv = d.find_element(By.CSS_SELECTOR, "#modelViewport canvas")
    for uv in ((40, 5), (55, 15)):  # a rectangle by two clicks (beside the block)
        off = js(f"""const m = {M}, v = m.view, f = m.frame(), [u, w] = arguments[0];
          const y = [f.n[1]*f.x[2]-f.n[2]*f.x[1], f.n[2]*f.x[0]-f.n[0]*f.x[2], f.n[0]*f.x[1]-f.n[1]*f.x[0]];
          const p = new (v.camera.position.constructor)(f.o[0] + u*f.x[0] + w*y[0], f.o[1] + u*f.x[1] + w*y[1], f.o[2] + u*f.x[2] + w*y[2]);
          const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
          return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(uv))
        ActionChains(d, duration=30).move_to_element_with_offset(cv, *off).pause(0.12).click().perform()
        time.sleep(0.4)
    n1 = js(f"return {M}.sk.f.entities.length")
    print("a rectangle drawn in the iso view:", n0, "->", n1, "entities")
    check("drawing works after the cube turned the view", n1 > n0 and js(f"return {M}.mode") == "sketch")
    cube_click("0,0,1")
    check("TOP in a sketch, still sketching", near(cam()[0], [0, 0, 1]) and js(f"return {M}.mode") == "sketch")
    d.save_screenshot(f"{OUT}/view_cube_sketch.png")
    js(f"{M}.action('cancelSketch')")
    time.sleep(0.4)

    # the assembly
    call("new_assembly", name="Pair")
    call("insert_part", part="Block")
    call("insert_part", part="Block")
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    js(f"{A}.view.setView('iso')")
    time.sleep(0.8)
    now, before = bar_height("#asmViewport")
    print(f"assembly bar at 1280x800: {now} px now, {before} px with the view buttons (before)")
    check("the assembly bar is lower than before", now < before)
    check("no view buttons in the assembly bar", not d.find_elements(By.CSS_SELECTOR, "#asmViewport .m-cmdbar [data-a^=view-]"))
    check("the assembly's cube is under its bar", clear_of_cube("#asmViewport"))
    cube_click("1,0,0", "#asmViewport")
    print("assembly RIGHT:", cam(A))
    check("assembly RIGHT", near(cam(A)[0], [1, 0, 0]))
    cube_click("1,-1,1", "#asmViewport")
    print("assembly corner:", cam(A))
    check("assembly corner", near(cam(A)[0], [0.58, -0.58, 0.58]))
    d.save_screenshot(f"{OUT}/view_cube_assembly.png")

    d.find_element(By.ID, "langBtn").click()
    time.sleep(0.6)
    labels = js("return [...document.querySelectorAll('#asmViewport .view-cube .vc-face b')].map(e => e.textContent)")
    print("Czech labels:", labels)
    check("Czech labels", labels[:3] == ["SHORA", "ZDOLA", "ZEPŘEDU"])
    d.save_screenshot(f"{OUT}/view_cube_assembly_cs.png")
    d.find_element(By.ID, "langBtn").click()
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    print("ALL OK" if ok and all(ok) and not errs else f"FAILED ({ok.count(False)} of {len(ok)})")
    d.quit()
