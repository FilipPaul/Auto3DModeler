"""Colour and see-through, in headless Edge: a 3D model's Part panel -> Colour red, See-through 40 % -> the body red and
see-through -> an assembly shows it so -> one placed copy gets its own colour (green, 60 %), the other stays as the part
-> ↺ As its part -> Ctrl+Z.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_look.py http://127.0.0.1:5199 <out dir>
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
M = "window.__app.modeler"
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


def set_input(sel, value):
    el = d.find_element(By.CSS_SELECTOR, sel)
    js("arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('input', {bubbles: true})); arguments[0].dispatchEvent(new Event('change', {bubbles: true}))", el, value)
    time.sleep(0.4)


def mats():
    return js(f"return {A}.view.meshes.map(m => [m.userData.inst, '#' + m.material.color.getHexString(), +m.material.opacity.toFixed(2)])")


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Shell")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 30}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    wait(f"return !!{M}.result?.body")
    js(f"{M}.selected = null; {M}.renderProps()")
    time.sleep(0.3)
    set_input("#modelRight [data-k=color]", "#ff3b30")
    set_input("#modelRight [data-k=clear]", "40")
    print("model view: colour", js(f"return '#' + {M}.view.bodyColor?.getHexString()"), "| opacity", js(f"return {M}.view.material.opacity"),
          "| part data", js(f"return [{M}.part.color, {M}.part.opacity]"))
    js(f"{M}.view.setView('iso')")
    time.sleep(0.3)
    d.save_screenshot(f"{OUT}/look1.png")

    call("new_assembly", name="Looks")
    call("insert_part", part="Shell")
    call("insert_part", part="Shell")
    wait(f"return {A}.doc.instances.length === 2 && Object.values({A}.bodies).every(b => b.body)")
    time.sleep(0.5)
    print("assembly, as the part:", mats())
    js(f"{A}.sel = 'I2'; {A}.moreOpen = true; {A}.render(); {A}.draw()")  # (🎨 Look and editing: open)
    time.sleep(0.3)
    print("panel says:", d.find_element(By.CSS_SELECTOR, "#asmRight .mp-look + p.hint").text)
    set_input("#asmRight [data-look=colour]", "#34c759")
    set_input("#asmRight [data-look=clear]", "60")
    js(f"{A}.sel = null; {A}.draw()")
    time.sleep(0.3)
    print("I2 its own look:", mats())
    js(f"{A}.view.setView('iso')")
    time.sleep(0.3)
    d.save_screenshot(f"{OUT}/look2.png")
    js(f"{A}.sel = 'I2'; {A}.render(); {A}.draw()")
    time.sleep(0.3)
    d.find_element(By.CSS_SELECTOR, "#asmRight [data-look=reset]").click()
    time.sleep(0.4)
    js(f"{A}.sel = null; {A}.draw()")
    print("↺ As its part:", mats())
    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    time.sleep(0.8)
    js(f"{A}.sel = null; {A}.draw()")
    print("Ctrl+Z:", mats())
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
