"""📏 Measure in an assembly, with REAL mouse input in headless Edge: a base and a plate held 5 mm above it (Gap) ->
📏 Measure -> the plate's top, then the base's top: the distance and "Faces apart" 10 -> a corner of the base snaps
-> two holes in different parts: "Axes apart" -> Esc ends.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_measure.py http://127.0.0.1:5199 <out dir>
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


def click(inst, local, dx=0, dy=0):
    x, y = screen_of(inst, local)
    ActionChains(d, duration=30).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, "#asmViewport canvas"), x + dx, y + dy).perform()
    time.sleep(0.2)
    ActionChains(d).click().perform()
    time.sleep(0.5)


def box():
    """📏 The newest row of the measurements table (measure.js)."""
    return js("return [...document.querySelectorAll('[data-w=measure-assembly] .ms-row')].at(-1)?.innerText.replace(/\\s+/g, ' ') || ''")


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Base")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 80, "h": 60}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="hole", face="F2:end", points=[[-30, -20]], d=6)
    call("new_model", name="Plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 30}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=6)
    time.sleep(1)
    call("new_assembly", name="Measured")
    call("insert_part", part="Base")
    call("insert_part", part="Plate")
    call("snap_faces", type="gap", gap=5, move={"part": "I2", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    js(f"{A}.sel = null; {A}.render(); {A}.view.setView('iso')")
    time.sleep(0.6)

    d.find_element(By.CSS_SELECTOR, "#asmViewport [data-a=measure]").click()
    time.sleep(0.3)
    print("hint:", js("return document.querySelector('#asmViewport .m-hint').textContent"))
    click("I2", [28, 12, 5])  # the plate's top
    print("first:", box())
    click("I1", [70, 8, 10])  # the base's top
    print("second:", box())
    d.save_screenshot(f"{OUT}/measure1.png")
    click("I1", [80, 0, 10], 3, 2)  # near the base's corner
    print("corner:", box())
    click("I2", [20, 15, 5])
    print("to the plate's top:", box())
    # the two holes: the plate's hole wall (far side) and the base's hole wall
    js(f"{A}.view.setView('iso')")
    time.sleep(0.4)
    click("I2", [20, 18, 2.5])  # the far wall of the plate's hole
    print("plate hole:", box()[:60])
    click("I1", [10, 13, 9])  # the far wall of the base's hole (its front-left corner)
    print("base hole:", box())
    d.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    time.sleep(0.3)
    print("Esc: the table kept", js("return document.querySelectorAll('[data-w=measure-assembly] .ms-row').length"), "row(s) | button on", "on" in d.find_element(By.CSS_SELECTOR, "#asmViewport [data-a=measure]").get_attribute("class"))
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
