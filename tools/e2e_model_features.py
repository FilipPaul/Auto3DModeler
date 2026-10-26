"""Fillet, chamfer, hole, revolve, shell and turning steps off, with REAL mouse input in headless Edge: a 40 x 20 x 10 box ->
◜ Fillet: click a vertical edge, radius 2 -> exact volume; the box gets taller -> the rounding follows its edge;
a click on a face picks all its edges; ◎ Hole: a click near the top face's centre snaps to it, Ø5 through all;
● / ◌ turns a step off and on; ◸ Chamfer on a top edge; volumes checked.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_model_features.py http://127.0.0.1:5199 <out dir>
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
M = "window.__app.modeler"


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


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#modelViewport canvas")


def off_uv(uv):
    return js(f"""const m = {M}, v = m.view, f = m.frame(), [u, w] = arguments[0];
      const y = [f.n[1]*f.x[2]-f.n[2]*f.x[1], f.n[2]*f.x[0]-f.n[0]*f.x[2], f.n[0]*f.x[1]-f.n[1]*f.x[0]];
      const p = new (v.camera.position.constructor)(f.o[0] + u*f.x[0] + w*y[0], f.o[1] + u*f.x[1] + w*y[1], f.o[2] + u*f.x[2] + w*y[2]);
      const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(uv))


def off_xyz(p):
    return js(f"""const v = {M}.view, [x, y, z] = arguments[0];
      const [sx, sy] = v.toScreen(new (v.camera.position.constructor)(x, y, z)), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(p))


def click_at(o):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *o).perform()
    time.sleep(0.2)
    ActionChains(d).click().perform()
    time.sleep(0.3)


def btn(sel):
    d.find_element(By.CSS_SELECTOR, sel).click()
    time.sleep(0.3)


def vol():
    return js(f"return {M}.result?.body?.volume")


def typed(sel, value, enter=True):
    el = d.find_element(By.CSS_SELECTOR, sel)
    el.send_keys(Keys.CONTROL, "a")
    el.send_keys(str(value), *([Keys.ENTER] if enter else []))
    settled()


def top_face_point():
    return js(f"""const v = {M}.view, r = v.renderer.domElement.getBoundingClientRect();
      for (let gy = 0.25; gy < 0.85; gy += 0.01) for (let gx = 0.3; gx < 0.7; gx += 0.01) {{
        const x = Math.round(r.left + gx * r.width), y = Math.round(r.top + gy * r.height);
        if (document.elementFromPoint(x, y) !== v.renderer.domElement) continue;
        const h = v.pick(x, y);
        if (h?.face?.normal && h.face.normal[2] > 0.99) return [x - Math.floor(r.left + r.width / 2), y - Math.floor(r.top + r.height / 2)];
      }} return null;""")


try:
    d.get(URL)
    wait("return !!window.__app")
    btn("#newModelBtn")
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.6)
    click_at(off_uv((0, 0)))
    click_at(off_uv((40, 20)))
    btn(".m-cmdbar [data-a=finish]")
    wait(f"return {M}.cmd")
    settled()
    btn("#modelRight [data-a=ok]")
    settled()
    print("box:", vol(), "| face names", sorted(f.get("name", "?") for f in js(f"return {M}.result.body.faces")))

    # ◜ Fillet: hover + click the vertical edge at (40, 0)
    btn(".m-cmdbar [data-a=fillet]")
    o = off_xyz([40, 0, 5])
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *o).perform()
    time.sleep(0.3)
    print("hovered edge highlighted:", js(f"return {M}.view.edgeGroup.children.length > 0"))
    ActionChains(d).click().perform()
    settled()
    print("edges picked:", js(f"return {M}.cmd.feature.edges"))
    typed("#modelRight input[data-k=r]", 2, enter=False)
    print(f"preview volume {vol():.4f} expected {8000 - (4 - math.pi) * 10:.4f}")
    d.save_screenshot(f"{OUT}/f1_fillet.png")
    btn("#modelRight [data-a=ok]")
    settled()
    print("steps:", js(f"return {M}.part.features.map(f => f.name + ' ' + {M}.whatText(f))"))

    # the box taller: double-click Extrude 1, 15 mm -> the rounding follows
    ActionChains(d).double_click(d.find_elements(By.CSS_SELECTOR, ".mt-item")[1]).perform()
    wait(f"return {M}.cmd")
    typed("#modelRight input[data-k=d]", 15)
    print(f"taller: {vol():.4f} expected {12000 - (4 - math.pi) * 15:.4f} | issues", js(f"return {M}.result.features.filter(s => !s.ok || s.warnings.length)"))

    # a click on a face takes all its edges (then cancel)
    btn(".m-cmdbar [data-a=fillet]")
    click_at(top_face_point())
    print("click on the top face -> edges picked:", js(f"return {M}.cmd.feature.edges.length"))
    btn("#modelRight [data-a=cancel]")
    settled()

    # ◎ Hole: a click near the top face's centre (snaps), Ø5 through
    btn(".m-cmdbar [data-a=hole]")
    click_at(off_xyz([20.4, 9.7, 15]))
    print("hole points (snapped to the centre):", js(f"return {M}.cmd.feature.points"), "| face", js(f"return {M}.cmd.feature.plane?.face"))
    btn("#modelRight [data-a=ok]")
    settled()
    v_hole = vol()
    print(f"with the hole: {v_hole:.4f} expected {12000 - (4 - math.pi) * 15 - math.pi * 6.25 * 15:.4f}")
    d.save_screenshot(f"{OUT}/f2_hole.png")

    # turn the hole off and on again (● / ◌ in the list)
    rows = d.find_elements(By.CSS_SELECTOR, ".mt-item")
    ActionChains(d).move_to_element(rows[-1]).perform()
    rows[-1].find_element(By.CSS_SELECTOR, "[data-a=off]").click()
    settled()
    print("hole off:", round(vol(), 4), "| row", js("return document.querySelectorAll('.mt-item')[3].textContent.replace(/\\s+/g, ' ').trim()"))
    rows = d.find_elements(By.CSS_SELECTOR, ".mt-item")
    ActionChains(d).move_to_element(rows[-1]).perform()
    rows[-1].find_element(By.CSS_SELECTOR, "[data-a=off]").click()
    settled()
    print("hole on again:", abs(vol() - v_hole) < 1e-6)

    # ◸ Chamfer the front top edge (y 0, z 15), 1 mm
    btn(".m-cmdbar [data-a=chamfer]")
    click_at(off_xyz([12, 0, 15]))
    print("chamfer edges:", js(f"return {M}.cmd.feature.edges"))
    typed("#modelRight input[data-k=d]", 1, enter=False)
    btn("#modelRight [data-a=ok]")
    settled()
    print(f"chamfered: {vol():.4f} (less than {v_hole:.4f}: {vol() < v_hole}) | issues", js(f"return {M}.result.features.filter(s => !s.ok)"))
    print("tree:", js(f"return [...document.querySelectorAll('.mt-item')].map(r => r.querySelector('.mt-name').textContent + ' · ' + r.querySelector('.mt-what').textContent)"))
    d.save_screenshot(f"{OUT}/f3_all.png")

    # undo the chamfer, redo it
    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    settled()
    print("Ctrl+Z:", abs(vol() - v_hole) < 1e-6)

    # ⟳ Revolve in a new model: the empty sketch moves to the Front plane, a 10 x 20 rectangle beside the
    # vertical axis (x 5..15), Finish (cancel the extrude), Revolve 360° -> a tube
    btn("#newModelBtn")
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.6)
    btn(".m-cmdbar [data-a=plane-XZ]")
    print("sketch plane now:", js(f"return {M}.sk.f.plane"))
    click_at(off_uv((5, 0)))
    click_at(off_uv((15, 20)))
    print("plane buttons gone after drawing:", not js("return !!document.querySelector('.m-cmdbar [data-a^=plane-]')"))
    btn(".m-cmdbar [data-a=finish]")
    wait(f"return {M}.cmd")
    btn("#modelRight [data-a=cancel]")
    settled()
    btn(".m-cmdbar [data-a=revolve]")
    settled()
    us = js(f"return Object.values({M}.part.features[0].points).map(p => p[0])")
    r0, r1 = min(us), max(us)
    print(f"revolve preview: {vol():.4f} expected {math.pi * (r1 ** 2 - r0 ** 2) * 20:.4f} | axis options",
          js("return [...document.querySelectorAll('#modelRight select[data-k=axis] option')].map(o => o.textContent)"))
    btn("#modelRight [data-a=ok]")
    settled()
    print("bbox:", js(f"return {M}.result.body.bbox.map(v => +v.toFixed(4))"))
    d.save_screenshot(f"{OUT}/f4_revolve.png")

    # ▢ Shell: click the tube's top (the flat ring at z 20), wall 1
    btn(".m-cmdbar [data-a=shell]")
    click_at(off_xyz([0, -10, 20]))
    print("open faces:", js(f"return {M}.cmd.feature.faces.map(f => f.name)"))
    typed("#modelRight input[data-k=t]", 1, enter=False)
    btn("#modelRight [data-a=ok]")
    settled()
    v = vol()
    print(f"shelled: {v:.3f} | issues", js(f"return {M}.result.features.filter(s => !s.ok)"), "| tree",
          js(f"return [...document.querySelectorAll('.mt-item')].map(r => r.querySelector('.mt-name').textContent + ' · ' + r.querySelector('.mt-what').textContent)"))
    d.save_screenshot(f"{OUT}/f5_shell.png")
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
