"""⚠ Collisions in an assembly, in headless Edge: a base (80 × 60 × 10) and a plate (40 × 30 × 5) put 3 mm into it ->
⚠ Collisions: 1 overlap of 40 × 30 × 3 = 3600 mm³, both parts glowing red, the overlap boxed -> hover the row -> the
plate moved up 3 mm (it only touches now): checked again on its own -> no overlaps -> 2 mm too far into it again ->
2400 mm³ -> ↗ picks the two parts.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_clash.py http://127.0.0.1:5199 <out dir>
"""
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


def place(inst, x, y, z):
    js(f"const it = {A}.inst(arguments[0]); it.matrix = [1,0,0,0, 0,1,0,0, 0,0,1,0, arguments[1], arguments[2], arguments[3], 1]; {A}.commit()", inst, x, y, z)


def listed():
    wait(f"return !{A}.clashBusy")
    time.sleep(0.3)
    return [r.text.replace("\n", " ") for r in d.find_elements(By.CSS_SELECTOR, "#asmRight .as-clash")] or d.find_element(By.CSS_SELECTOR, "#asmRight .mp-count").text


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Base")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 80, "h": 60}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("new_model", name="Plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 30}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("new_assembly", name="Clash")
    call("insert_part", part="Base")
    call("insert_part", part="Plate")
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    place("I2", 20, 15, 7)  # 3 mm into the base's top
    js(f"{A}.view.setView('iso')")
    d.find_element(By.CSS_SELECTOR, "#asmViewport [data-a=clashes]").click()
    print("⚠ Collisions:", listed())
    print("glowing red:", js(f"return {A}.view.meshes.map(m => m.material.emissive.getHex() === 0x6a0d0d)"), "| overlap boxes:", js(f"return {A}.view.clashGroup.children.length / 2"))
    d.save_screenshot(f"{OUT}/asm_clash.png")
    ActionChains(d).move_to_element(d.find_element(By.CSS_SELECTOR, "#asmRight .as-clash")).perform()
    time.sleep(0.3)
    print("hover the row: still marked", js(f"return {A}.view.clashGroup.children.length / 2"))
    place("I2", 20, 15, 10)  # on the top: touching only
    time.sleep(0.6)
    print("moved up 3 mm (touching) — checked again:", listed(), "| red:", js(f"return {A}.view.meshes.filter(m => m.material.emissive.getHex() === 0x6a0d0d).length"))
    place("I2", 20, 15, 8)
    time.sleep(0.6)
    print("2 mm in again:", listed())
    d.find_element(By.CSS_SELECTOR, "#asmRight [data-cpick]").click()
    time.sleep(0.4)
    print("↗ picks:", js(f"return [{A}.sel, {A}.sel2]"), "|", d.find_element(By.CSS_SELECTOR, "#asmRight h2").text)
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
