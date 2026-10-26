"""🎨 Paint and ✂ Section in an assembly, with REAL mouse clicks in headless Edge: a base and a plate 5 mm above it ->
🎨 Paint: a click on the plate's top face, Ctrl+click the base's top -> 2 faces -> a colour: both painted in this
assembly (the parts' own data unchanged) -> undo -> ◆ Whole parts: the base -> its colour -> ✂ Section: every part cut
(clipping planes on their materials), the slider moves the cut, ✕ ends it.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_paint.py http://127.0.0.1:5199 <out dir>
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


def screen_of(inst, local):
    return js(f"""const a = {A}, it = a.inst(arguments[0]), v = a.view, V = v.camera.position.constructor;
      const M = new (v.camera.matrix.constructor)().fromArray(it.matrix), p = new V(...arguments[1]).applyMatrix4(M);
      const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", inst, local)


def click(inst, local, ctrl=False):
    x, y = screen_of(inst, local)
    ActionChains(d, duration=30).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, "#asmViewport canvas"), x, y).perform()
    time.sleep(0.2)
    if ctrl:
        ActionChains(d).key_down(Keys.CONTROL).click().key_up(Keys.CONTROL).perform()
    else:
        ActionChains(d).click().perform()
    time.sleep(0.5)


def colour(value):
    js("const c = document.querySelector('#asmRight [data-k=paint]'); c.value = arguments[0]; c.dispatchEvent(new Event('input')); c.dispatchEvent(new Event('change'))", value)
    time.sleep(0.4)


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Base")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 80, "h": 60}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("new_model", name="Plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 30}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("new_assembly", name="Painted")
    call("insert_part", part="Base")
    call("insert_part", part="Plate")
    call("snap_faces", type="gap", gap=5, move={"part": "I2", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    js(f"{A}.sel = null; {A}.render(); {A}.view.setView('iso')")
    time.sleep(0.6)

    d.find_element(By.CSS_SELECTOR, "#asmViewport [data-a=paint]").click()
    time.sleep(0.3)
    print("paint hint:", d.find_element(By.CSS_SELECTOR, "#asmViewport .m-hint").text)
    click("I2", [20, 15, 5])         # the plate's top (its local origin: the sketch's corner)
    click("I1", [75, 55, 10], ctrl=True)  # the base's top, near its far corner
    print("chosen:", d.find_element(By.CSS_SELECTOR, "#asmRight .mp-count").text, "| marked:", js(f"return {A}.view.markGroup.children.length"))
    colour("#ff0000")
    print("painted in the assembly:", js(f"return {A}.doc.instances.map(i => [i.id, (i.paint || []).map(p => p.name + ' ' + p.color)])"),
          "| the parts' own paint:", js("return window.__app.project.parts.filter(p => p.kind === 'model').map(p => (typeof p.data === 'object' ? p.data.paint : null) || null)"))
    print("drawn red:", js(f"return {A}.view.meshes.map(m => !!m.geometry.attributes.color)"))
    d.save_screenshot(f"{OUT}/asm_paint.png")
    js(f"{A}.history.go(-1)")
    time.sleep(0.4)
    print("undo:", js(f"return {A}.doc.instances.map(i => (i.paint || []).length)"))
    d.find_element(By.CSS_SELECTOR, "#asmRight [data-by=part]").click()
    time.sleep(0.2)
    click("I1", [30, 20, 10])
    print("whole parts:", d.find_element(By.CSS_SELECTOR, "#asmRight .mp-count").text)
    colour("#00aa00")
    print("the base's colour here:", js(f"return {A}.doc.instances.map(i => [i.id, i.colour || null])"))
    d.find_element(By.CSS_SELECTOR, "#asmRight [data-a=donePaint]").click()
    time.sleep(0.3)

    d.find_element(By.CSS_SELECTOR, "#asmViewport [data-a=section]").click()
    time.sleep(0.4)
    planes = lambda: js(f"return {A}.view.meshes.map(m => (m.material.clippingPlanes || []).map(p => [p.normal.toArray().map(Math.round), +p.constant.toFixed(2)]))")
    print("✂ section on:", js(f"return {A}.section"), "| every part cut:", planes())
    js("const r = document.querySelector('#asmViewport .m-section input'); r.value = 10; r.dispatchEvent(new Event('input'))")
    time.sleep(0.3)
    print("slider to 10:", planes()[0], "|", d.find_element(By.CSS_SELECTOR, "#asmViewport .m-section b").text)
    d.find_element(By.CSS_SELECTOR, "#asmViewport .m-section [data-ax=z]").click()
    time.sleep(0.3)
    print("Z:", planes()[0])
    d.save_screenshot(f"{OUT}/asm_section.png")
    d.find_element(By.CSS_SELECTOR, "#asmViewport .m-section [data-x]").click()
    time.sleep(0.3)
    print("✕: section", js(f"return {A}.section"), "| planes", planes())
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
