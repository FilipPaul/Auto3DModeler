"""Joints you can see and parts that move only the ways their joints leave free (sliders), in headless Edge: a base with a
Ø6 hole, a Ø6 pin and a lid -> the pin concentric in the hole: 2 ways (along the axis, about it) -> slide 5 mm along
the axis: still in the hole -> its distance locked: 1 way -> its turn locked too: fully held -> the lid on the base's top:
3 ways (2 moves on the face, a turn) -> moved 10 mm along X: it stays on the face -> the base moved 20 mm: the lid
goes along, 10 mm off centre still -> a part chosen: its joints listed and their symbols in the view -> Ctrl+click
a second one: the joints between the two.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_dof.py http://127.0.0.1:5199 <out dir>
"""
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


def pick(inst):
    js(f"{A}.choose(arguments[0])", inst)
    time.sleep(0.4)


def moves():
    return [e.text for e in d.find_elements(By.CSS_SELECTOR, "#asmRight .as-dof label")]


def held():
    return d.find_element(By.CSS_SELECTOR, "#asmRight").text.count("Fully held")


def slide(i, by):
    """A slider moved `by` from where it is (the sliders show where the part is along each way)."""
    js("""const s = document.querySelectorAll('#asmRight [data-dof]')[arguments[0]]; s.value = +s.value + arguments[1];
      s.dispatchEvent(new Event('input')); s.dispatchEvent(new Event('change'))""", i, by)
    time.sleep(0.5)


def pos(inst, local=(0, 0, 0)):
    return js(f"""const it = {A}.inst(arguments[0]), V = {A}.view.camera.position.constructor, M = new ({A}.view.camera.matrix.constructor)().fromArray(it.matrix);
      return new V(...arguments[1]).applyMatrix4(M).toArray().map(v => +v.toFixed(3))""", inst, list(local))


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Base")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 80, "h": 60}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="hole", face="F2:end", points=[[-25, -15]], d=6)
    call("new_model", name="Pin")
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 6}}])
    call("add_feature", type="extrude", sketch="F1", d=20)
    call("new_model", name="Lid")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 30, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=4)
    call("new_assembly", name="Moving")
    for p in ("Base", "Pin", "Lid"):
        call("insert_part", part=p)
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    hole = js(f"return {A}.bodies[{A}.inst('I1').part].body.faces.find(f => f.type === 'cylinder').name")
    print("snap pin:", call("snap_faces", type="axis", move={"part": "I2", "face": "F2:side:c1"}, onto={"part": "I1", "face": hole})[:80])
    print("snap lid:", call("snap_faces", type="touch", move={"part": "I3", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})[:80])
    js(f"{A}.view.setView('iso')")
    time.sleep(0.5)

    pick("I2")
    print("pin, concentric:", moves())
    js(f"const m = {A}.doc.mates.find(x => x.move === 'I2'); delete m.dist; delete m.angle; {A}.applyMates(); {A}.commit()")
    pick("I2")
    print("pin, distance free, turn free:", moves())
    z0 = pos("I2")[2]
    i_axis = [k for k, t in enumerate(moves()) if t.startswith("↔")]  # (the pin's one slide: "↔ Slide: Pin" — motions are named by their part)[0]
    slide(i_axis, 5)
    p = pos("I2")
    print("slid 5 along the axis: z", z0, "->", p[2], "| still on the hole's axis (x, y):", p[:2])
    js(f"const m = {A}.doc.mates.find(x => x.move === 'I2'); m.dist = 0; m.side = 1; {A}.applyMates(); {A}.commit()")
    pick("I2")
    print("distance locked:", moves())
    js(f"const m = {A}.doc.mates.find(x => x.move === 'I2'); m.angle = 0; {A}.applyMates(); {A}.commit()")
    pick("I2")
    print("turn locked too — fully held:", held(), "| sliders", moves())

    pick("I3")
    print("lid on the base's top:", moves())
    c0 = pos("I3", (15, 10, 0))
    i_x = [k for k, t in enumerate(moves()) if "X" in t and t.startswith("↔")][0]
    slide(i_x, 10)
    c1 = pos("I3", (15, 10, 0))
    print("10 along X:", c0, "->", c1, "| on the face still (z):", c1[2])
    js(f"const it = {A}.inst('I1'); it.matrix[12] += 20; {A}.movedByHand('I1'); {A}.commit()")
    time.sleep(0.4)
    c2 = pos("I3", (15, 10, 0))
    print("base moved 20 in x -> the lid goes along:", c2, "| 10 off the base's middle still:", round(c2[0] - (40 + 20), 3))

    pick("I1")
    print("base chosen — joints listed:", len(d.find_elements(By.CSS_SELECTOR, "#asmRight [data-jrow]")),
          "| symbols in the view:", js("return document.querySelectorAll('#asmViewport .as-jtag').length"))
    # rows follow doc.instances; not by the row's text — a fixed part reads "I3 📌"
    row = d.find_elements(By.CSS_SELECTOR, "#asmLeft .as-list .mt-item")[js(f"return {A}.doc.instances.findIndex(i => i.id === 'I3')")]
    ActionChains(d).key_down(Keys.CONTROL).click(row.find_element(By.CSS_SELECTOR, ".mt-name")).key_up(Keys.CONTROL).perform()
    time.sleep(0.4)
    print("Ctrl+click the lid:", d.find_element(By.CSS_SELECTOR, "#asmRight h2").text, "| joints between:",
          len(d.find_elements(By.CSS_SELECTOR, "#asmRight [data-jrow]")), "| symbols:", js("return document.querySelectorAll('#asmViewport .as-jtag').length"))
    d.save_screenshot(f"{OUT}/asm_dof.png")
    js("document.querySelector('#asmViewport .as-jtag').click()")
    time.sleep(0.3)
    print("a symbol clicked: its parts", js(f"return [{A}.sel, {A}.sel2]"))
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
