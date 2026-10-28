"""Distances from a round face's axis (a cross hole under the top face), with REAL mouse input in headless Edge:
1. A 60 x 40 x 20 block with a Ø8 cross hole along y (its axis at x 30, z 10). A sketch on the top face: the hole's
   axis shows as a dashed centre line; ↔ Dimension from a circle to it (hovered: "axis of the round face"), typed 15,
   cut through. The cross hole moves to x 40 -> the circle follows: 15 from the axis (x 55).
2. ◎ Hole on the top face; its ↔ 🎯 picks the cross hole's rim in the front view (the round face -> its axis):
   "↔ 15 mm right of the axis"; the cross hole moves -> the hole goes along.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_model_axis_refs.py http://127.0.0.1:5199 <out dir>
"""
import json
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
failed = []


def check(what, ok):
    print(("OK   " if ok else "FAIL ") + what)
    if not ok:
        failed.append(what)


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


def off_xyz(p):
    return js(f"""const v = {M}.view, [x, y, z] = arguments[0];
      const [sx, sy] = v.toScreen(new (v.camera.position.constructor)(x, y, z)), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(p))


def off_uv(uv):
    return js(f"""const m = {M}, v = m.view, f = m.frame(), [u, w] = arguments[0];
      const y = [f.n[1]*f.x[2]-f.n[2]*f.x[1], f.n[2]*f.x[0]-f.n[0]*f.x[2], f.n[0]*f.x[1]-f.n[1]*f.x[0]];
      const p = new (v.camera.position.constructor)(f.o[0] + u*f.x[0] + w*y[0], f.o[1] + u*f.x[1] + w*y[1], f.o[2] + u*f.x[2] + w*y[2]);
      const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(uv))


def move(o):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *o).perform()
    time.sleep(0.25)


def click(o):
    move(o)
    ActionChains(d).click().perform()
    time.sleep(0.35)


def btn(sel):
    d.find_element(By.CSS_SELECTOR, sel).click()
    time.sleep(0.3)


def bores():  # the vertical round faces' centres (x, y): the cut circle, the hole
    b = js(f"return {M}.result.body")
    return sorted([round(c, 3) for c in f["centroid"][:2]] for f in b["faces"] if f["type"] == "cylinder" and abs(f["axis"]["d"][2]) > 0.99)


def block(name):
    call("new_model", name=name)
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=20)
    call("add_feature", type="sketch", plane="XZ", shapes=[{"circle": {"x": 30, "y": 10, "d": 8}}])
    call("add_feature", type="extrude", sketch="F3", op="cut", d=100, symmetric=True)
    settled()


def move_cross(x):
    call("edit_feature", id="F3", fields={"shapes": [{"circle": {"x": x, "y": 10, "d": 8}}]})
    settled()


try:
    d.get(URL)
    wait("return !!window.__app")

    # 1. a sketch circle 15 from the cross hole's axis
    block("Axis sketch")
    btn("#modelViewport [data-a=sketch]")
    click(off_xyz([45, 30, 20]))
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.6)
    fr = js(f"return {M}.frame()")
    print("sketch on the top face, origin", fr["o"])
    axes = js(f"return {SK}.refs().axes.map(q => [q.ref.face, q.a, q.b])")
    print("axes on the sketch:", axes)
    check("the cross hole's axis is a line along v at u 0", len(axes) == 1 and abs(axes[0][1][0]) < 1e-6 and abs(axes[0][2][0]) < 1e-6)
    btn(".m-cmdbar [data-a=circle]")
    click(off_uv([12, 5]))
    click(off_uv([15, 5]))
    btn(".m-cmdbar [data-a=dim]")
    click(off_uv([15, 5]))  # the circle -> its centre
    move(off_uv([0.5, -12]))  # over the cross hole, near its axis
    hover = js("return [...document.querySelectorAll('.sk-label.hover')].map(e => e.textContent)")
    print("hovered:", hover)
    check("hover names the axis", any("axis" in h or "osa" in h for h in hover))
    d.save_screenshot(f"{OUT}/axis1_hover.png")
    ActionChains(d).click().perform()
    time.sleep(0.6)
    inp = d.find_elements(By.CSS_SELECTOR, ".sk-input")
    check("the size editor opened", bool(inp))
    inp[0].send_keys(Keys.CONTROL, "a")
    inp[0].send_keys("15", Keys.ENTER)
    time.sleep(0.8)
    dim = js(f"return {SK}.f.dims.find(x => typeof x.a === 'object' && x.a.axis)")
    print("dimension:", json.dumps(dim))
    check("a dx dimension 15 from the axis", dim and dim["t"] == "dx" and abs(abs(dim["v"]) - 15) < 1e-6)
    d.save_screenshot(f"{OUT}/axis2_dim.png")
    btn("#modelViewport .view-actions [data-a=finish]")
    settled()
    js("document.querySelector('#modelRight [data-k=through]')?.click()")
    settled()
    btn("#modelViewport .view-actions [data-a=ok]")
    settled()
    print("cut:", bores())
    check("the circle is cut at x 45", bores() and bores()[0][0] == 45)
    move_cross(40)
    print("cross hole at x 40 -> the circle:", bores(), "| warnings", [s["warnings"] for s in js(f"return {M}.result.features") if s["warnings"]])
    check("the circle follows the axis to x 55", bores() and bores()[0][0] == 55)
    js(f"{M}.view.setView('iso')")
    time.sleep(0.4)
    d.save_screenshot(f"{OUT}/axis3_followed.png")

    # 2. a hole measured from the cross hole's axis (🎯 on its rim)
    block("Axis hole")
    js(f"{M}.view.setView('top')")
    time.sleep(0.4)
    btn("#modelViewport [data-a=hole]")
    click(off_xyz([44, 12, 20]))
    settled()
    js(f"{M}.view.setView('front')")
    time.sleep(0.4)
    btn("#modelRight [data-pickref='0:x']")
    move(off_xyz([30, 0, 14]))  # the cross hole's rim on the front face
    check("the cross hole's rim is pickable under the mouse", js("return document.querySelector('#modelViewport canvas').style.cursor") == "pointer")
    ActionChains(d).click().perform()
    time.sleep(0.5)
    f = js(f"return {M}.cmd.feature")
    print("from:", json.dumps(f["from"]))
    rows = [r.text for r in d.find_elements(By.CSS_SELECTOR, "#modelRight .mp-hd")]
    print("panel:", rows)
    check("↔ measured from the axis", (f["from"][0].get("x") or {}).get("axis", {}).get("face", "").startswith("F4:") and any("axis" in r or "osy" in r for r in rows))
    inp = d.find_element(By.CSS_SELECTOR, "#modelRight [data-hd='0:x']")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys("15")
    settled()
    print("typed 15:", js(f"return {M}.cmd.feature.points"))
    d.save_screenshot(f"{OUT}/axis4_hole.png")
    btn("#modelViewport .view-actions [data-a=ok]")
    settled()
    check("the hole is at x 45", bores() and bores()[0][0] == 45)
    move_cross(20)
    print("cross hole at x 20 -> the hole:", bores())
    check("the hole follows the axis to x 35", bores() and bores()[0][0] == 35)
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
print("FAILED:" if failed else "ALL OK", failed if failed else "")
sys.exit(1 if failed else 0)
