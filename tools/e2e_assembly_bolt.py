"""A screw through parts that have no holes yet, and the new joints, with REAL mouse input in headless Edge: a plate
joined onto a base (no holes) -> 🔗 Joint ▾ 🔩 Screw / pin -> a click on the plate's top -> the panel suggests
"M3×20 screw + M3 nut" through both (a see-through preview) -> Add -> a Ø3.4 hole step in each part, the screw's
head on the plate, the nut under the base -> Ctrl+Z takes it all back (holes too), Ctrl+Y puts it back -> the AI puts
an M3 screw + insert in (bolt_parts) -> the new joints: a roller Tangent on the base, a flap at an Angle (30°) and
Perpendicular to the base.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_bolt.py http://127.0.0.1:5199 <out dir>
"""
import json
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
A = "window.__app.assembly"
H = "window.__app.agentHandlers"


def wait(script, t=90):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#asmViewport canvas")


def click_world(p):
    off = js(f"""const v = {A}.view, p = new (v.camera.position.constructor)(...arguments[0]);
      const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", p)
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *off).perform()
    time.sleep(0.2)
    ActionChains(d).click().perform()
    time.sleep(0.6)


def holes_of(name):
    return js("return window.__app.project.parts.find(p => p.name === arguments[0]).data.features.filter(f => f.type === 'hole').map(f => [f.id, f.d, f.through, f.depth || null, f.bolt])", name)


def bbox(inst):
    return next(p["bbox"] for p in json.loads(call("get_assembly"))["parts"] if p["id"] == inst)


try:
    d.get(URL)
    wait("return !!window.__app")
    js("window.confirm = () => true")
    call("new_model", name="Plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("new_model", name="Base")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 80, "h": 60}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("new_model", name="Roller")
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 12}}])
    call("add_feature", type="extrude", sketch="F1", d=30)
    call("new_model", name="Flap")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 20, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=2)
    time.sleep(1)
    call("new_assembly", name="Bolted")
    call("insert_part", part="Base")
    call("insert_part", part="Plate")
    call("snap_faces", move={"part": "I2", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    js(f"{A}.view.setView('iso')")
    time.sleep(0.5)

    # 🔗 Joint ▾ 🔩 Screw / pin, then a click on the plate's top
    time.sleep(0.2)
    print("joint menu:", [b.get_attribute("textContent") for b in d.find_elements(By.CSS_SELECTOR, "#asmViewport .as-jlist [data-joint]")])
    d.find_element(By.CSS_SELECTOR, "#asmViewport [data-a=joints]").click()  # (🔗 Joint ▾: its menu)
    d.find_element(By.CSS_SELECTOR, "#asmViewport [data-joint=fastener]").click()
    time.sleep(0.3)
    print("hint:", js("return document.querySelector('#asmViewport .m-hint').textContent"))
    top = js(f"const f = {A}.worldFace('I2', 'F2:end'); return f.centroid.toArray()")
    click_world([top[0] + 12, top[1] + 8, top[2]])
    print("panel:", d.find_element(By.CSS_SELECTOR, "#asmRight h2").text, "| at", js(f"return [{A}.bolt.x, {A}.bolt.y]"))
    print("through:", [e.text for e in d.find_elements(By.CSS_SELECTOR, "#asmRight .as-bolt-parts .as-jrow")])
    print("suggests:", d.find_element(By.CSS_SELECTOR, "#asmRight .as-bolt-msg").text, "|", d.find_element(By.CSS_SELECTOR, "#asmRight .as-bolt-holes").text)
    print("preview pieces:", js(f"return {A}.view.ghostGroup.children.length"))
    d.save_screenshot(f"{OUT}/bolt1.png")
    vol0 = js(f"return [{A}.bodies[{A}.inst('I1').part].body.volume, {A}.bodies[{A}.inst('I2').part].body.volume]")

    d.find_element(By.CSS_SELECTOR, "#asmRight [data-a=addBolt]").click()
    wait(f"return {A}.doc.instances.length === 4 && Object.values({A}.bodies).every(b => b.body)")
    time.sleep(1)
    s = json.loads(call("get_assembly"))
    print("parts:", [(p["id"], p["name"]) for p in s["parts"]])
    print("joints:", [(j["type"], j["part"], j["onto"]) for j in s["joints"]])
    print("holes: Plate", holes_of("Plate"), "| Base", holes_of("Base"))
    vol1 = js(f"return [{A}.bodies[{A}.inst('I1').part].body.volume, {A}.bodies[{A}.inst('I2').part].body.volume]")
    print("volume taken by the holes:", [round(a - b, 3) for a, b in zip(vol0, vol1)], "expected", [round(math.pi * 1.7 ** 2 * 10, 3), round(math.pi * 1.7 ** 2 * 5, 3)])
    base, plate, screw, nut = (bbox(i) for i in ("I1", "I2", "I3", "I4"))
    print("screw head top", round(screw[5], 3), "= plate top + 3:", round(plate[5] + 3, 3), "| screw tip", round(screw[2], 3))
    print("nut top", round(nut[5], 3), "= base bottom", round(base[2], 3), "| nut centre", [round((nut[0] + nut[3]) / 2, 3), round((nut[1] + nut[4]) / 2, 3)],
          "screw centre", [round((screw[0] + screw[3]) / 2, 3), round((screw[1] + screw[4]) / 2, 3)])
    print("broken joints:", [j for j in s["joints"] if j.get("broken")])
    js(f"{A}.view.setView('front')")
    time.sleep(0.4)
    d.save_screenshot(f"{OUT}/bolt2.png")

    # undo: the screw, the nut and the holes; redo: all back
    body = d.find_element(By.TAG_NAME, "body")
    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    wait(f"return {A}.doc.instances.length === 2")
    time.sleep(0.5)
    print("after Ctrl+Z: holes Plate", holes_of("Plate"), "Base", holes_of("Base"), "| parts", js(f"return {A}.doc.instances.length"))
    ActionChains(d).key_down(Keys.CONTROL).send_keys("y").key_up(Keys.CONTROL).perform()
    wait(f"return {A}.doc.instances.length === 4")
    time.sleep(0.5)
    print("after Ctrl+Y: holes Plate", len(holes_of("Plate")), "Base", len(holes_of("Base")))

    # the AI: an M3 screw into an insert in the base
    r = call("bolt_parts", part="I2", face="F2:end", x=-15, y=-8, kind="insert", size="M3")
    print("AI bolt_parts:", r[:200])
    print("holes now: Plate", holes_of("Plate"), "| Base", holes_of("Base"))
    print("an impossible one:", call("bolt_parts", part="I2", face="F2:end", x=200, y=0))

    # the new joints
    call("insert_part", part="Roller")
    call("insert_part", part="Flap")
    call("insert_part", part="Flap")
    ids = [p["id"] for p in json.loads(call("get_assembly"))["parts"]]
    roller, flap, flap2 = ids[-3], ids[-2], ids[-1]
    r = json.loads(call("snap_faces", type="tangent", move={"part": roller, "face": "F2:side:c1"}, onto={"part": "I1", "face": "F2:end"}))
    ax = js(f"const f = {A}.worldFace(arguments[0], 'F2:side:c1'); return [f.axis.o.toArray(), f.axis.d.toArray()]", roller)
    print("tangent: roller axis", [round(v, 3) for v in ax[1]], "height above the base top", round(ax[0][2] - base[5], 3), "(r = 6)")
    call("snap_faces", type="angle", value=30, move={"part": flap, "face": "F2:end"}, onto={"part": "I1", "face": "F2:end"})
    n = js(f"return {A}.worldFace(arguments[0], 'F2:end').normal.toArray()", flap)
    print("angle 30: the flap's face at", round(math.degrees(math.acos(max(-1, min(1, n[2])))), 3), "°")
    call("snap_faces", type="perp", move={"part": flap2, "face": "F2:end"}, onto={"part": "I1", "face": "F2:end"})
    n = js(f"return {A}.worldFace(arguments[0], 'F2:end').normal.toArray()", flap2)
    print("perpendicular: the face's normal z", round(n[2], 6))
    js(f"{A}.sel = arguments[0]; {A}.render()", flap)
    time.sleep(0.3)
    print("joint row:", [e.text.replace("\n", " ") for e in d.find_elements(By.CSS_SELECTOR, "#asmRight .as-jrow")][:1])
    # change the angle in its box
    box = d.find_element(By.CSS_SELECTOR, "#asmRight [data-jval]")
    box.clear()
    box.send_keys("60", Keys.ENTER)
    time.sleep(0.6)
    n = js(f"return {A}.worldFace(arguments[0], 'F2:end').normal.toArray()", flap)
    print("angle typed 60: now", round(math.degrees(math.acos(max(-1, min(1, n[2])))), 3), "°")
    js(f"{A}.view.setView('iso')")
    time.sleep(0.4)
    d.save_screenshot(f"{OUT}/bolt3.png")
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
