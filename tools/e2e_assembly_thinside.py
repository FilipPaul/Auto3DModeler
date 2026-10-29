"""A click on the flat side face of a thin plate with holes picks that face, not a hole hidden behind it — REAL mouse
input in headless Edge: a 4 mm plate (60 × 22) with a Ø8.49 and a Ø5.66 hole, in an assembly, seen from the iso view
-> clicks on its long side face right in front of each hole (their rims hidden 3–7 mm behind it, a few px away on the
screen): the side face picked (flat), its name in the table's title -> zoomed out (the side a few px tall): the same
(no snap to a hidden hole's centre either) -> a click on a hole's rim on the top (seen) still picks the hole's round
face.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_thinside.py http://127.0.0.1:5199 <out dir>
"""
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.actions.wheel_input import ScrollOrigin
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
bad = []


def check(ok, what):
    print(("  ok  " if ok else "  FAIL") + " " + what)
    if not ok:
        bad.append(what)


opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
H = "window.__app.agentHandlers"
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


def world(inst, p):
    return js(f"const m = {A}.inst(arguments[0]).matrix, [x, y, z] = arguments[1]; return [m[0]*x + m[4]*y + m[8]*z + m[12], m[1]*x + m[5]*y + m[9]*z + m[13], m[2]*x + m[6]*y + m[10]*z + m[14]]", inst, p)


def at(inst, p):
    """A point of a placed part on the screen, from the canvas' middle (px)."""
    return js(f"""const v = {A}.view, V = v.camera.position.constructor, [sx, sy] = v.toScreen(new V(...arguments[0])), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", world(inst, p))


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#asmViewport canvas")


def click(inst, p):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *at(inst, p)).perform()
    time.sleep(0.3)
    ActionChains(d).click().perform()
    time.sleep(0.5)


def picks():
    return js(f"return ({A}.facePicks || []).map(q => [q.inst, q.face.type, q.face.name])")


def title():
    b = d.find_elements(By.CSS_SELECTOR, "#asmViewport .view-suggest .vs-head b")
    return b[0].text if b else ""


try:
    d.get(URL)
    wait("return !!window.__app")
    js("window.confirm = () => true")
    call("new_model", name="Base")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 80, "h": 50}}])
    call("add_feature", type="extrude", sketch="F1", d=6)
    call("new_model", name="Plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 22}}])
    call("add_feature", type="extrude", sketch="F1", d=4)
    call("add_feature", type="hole", face="F2:end", points=[[-15, 0]], d=8.49)
    call("add_feature", type="hole", face="F2:end", points=[[15, 0]], d=5.66)
    time.sleep(1)
    call("new_assembly", name="Thin")
    call("insert_part", part="Base")
    call("insert_part", part="Plate")
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    js(f"{A}.view.setView('iso')")
    time.sleep(0.8)
    # the plate's long side facing the camera, and where the holes are along it
    side = js(f"""const a = {A}, it = a.inst('I2'), body = a.bodies[it.part].body, v = a.view, cam = v.camera.getWorldDirection(new (v.camera.position.constructor)());
      const sides = body.faces.filter((f) => f.type === 'plane' && /:side:/.test(f.name)).map((f) => ({{ name: f.name, n: a.worldFace('I2', f.name).normal, c: f.centroid }}))
        .filter((f) => Math.abs(f.n.y) > 0.9).sort((p, q) => p.n.dot(cam) - q.n.dot(cam));
      const holes = body.faces.filter((f) => f.type === 'cylinder').map((f) => [f.name, f.axis.o[0], 2 * f.radius, f.axis.o[1]]);
      return {{ name: sides[0].name, y: sides[0].c[1], holes, bbox: body.bbox }};""")
    print("the side facing the camera:", side["name"], "at y", side["y"], "| the holes (name, x, Ø, y):", side["holes"])
    zmid = (side["bbox"][2] + side["bbox"][5]) / 2
    for name, x, dia, _ in side["holes"]:
        click("I2", [x, side["y"], zmid])
        p = picks()
        check(p == [["I2", "plane", side["name"]]], f"a click on the side in front of the hole {name} (Ø{dia:.2f}): {p} | the table: {title()}")
    d.save_screenshot(f"{OUT}/thinside_near.png")

    # zoomed out: the side only a few px tall (the report's plate seen in a whole arm), the hidden rims nearer still
    for _ in range(3):
        ActionChains(d).scroll_from_origin(ScrollOrigin.from_element(canvas(), 0, 0), 0, 240).perform()
        time.sleep(0.15)
    time.sleep(0.5)
    tall = abs(at("I2", [0, side["y"], side["bbox"][5]])[1] - at("I2", [0, side["y"], side["bbox"][2]])[1])
    print("  the side's height on the screen:", tall, "px")
    for name, x, dia, _ in side["holes"]:
        click("I2", [x, side["y"], zmid])
        p = picks()
        check(p == [["I2", "plane", side["name"]]] and js(f"return !{A}.snapPick"), f"zoomed out, the side in front of {name}: {p} (snap {js(f'return {A}.snapPick?.snap || null')}) | {title()}")
    d.save_screenshot(f"{OUT}/thinside_far.png")

    # a hole's rim on the top, seen: its round face still picked (a hole seen from the front: click its circle)
    js(f"{A}.view.setView('iso')")
    time.sleep(0.6)
    name, x, dia, y = side["holes"][0]
    click("I2", [x + dia / 2, y, side["bbox"][5]])
    p = picks()
    check(len(p) == 1 and p[0][1] == "cylinder", f"a click on the hole's rim on the top (seen): its round face {p}")
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
print("FAILED:" if bad else "ALL OK", bad if bad else "")
sys.exit(1 if bad else 0)
