"""Locked joints, asking before breaking, and turning about a joint, in headless Edge: a plate with a hole and a pin
with a flat on its head, two copies of the plate (the joint list tells them apart: I1 / I3) -> the pin in the hole +
on the plate -> 🔒 the axis joint: moving the pin by hand is refused (a notice), the pin stays -> unlocked: moving
asks first — "no" keeps the joints, "yes" breaks them -> undo -> ↻ turning the pin about the axis joint to 90°
(the slider catches there) and to 30° typed.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_lock.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time

from selenium import webdriver
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


def joints():
    return json.loads(call("get_assembly"))["joints"]


def pin_pos():
    return [round(v, 3) for v in js(f"return {A}.inst('I2').matrix.slice(12, 15)")]


def pin_x_dir():
    return [round(v, 3) for v in js(f"return {A}.inst('I2').matrix.slice(0, 3)")]


def select(inst):
    js(f"{A}.sel = arguments[0]; {A}.render(); {A}.draw()", inst)
    time.sleep(0.3)


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=8)
    call("new_model", name="Pin")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": -7, "y": -4, "w": 14, "h": 8}}])  # a flat head
    call("add_feature", type="extrude", sketch="F1", d=3)
    call("add_feature", type="sketch", plane={"face": "F2:end"}, shapes=[{"circle": {"x": 0, "y": 0, "d": 8}}])
    call("add_feature", type="extrude", sketch="F3", d=20)
    time.sleep(1)
    call("new_assembly", name="Locked")
    call("insert_part", part="Plate")
    call("insert_part", part="Pin")
    call("insert_part", part="Plate")
    call("place_part", part="I2", z=30)
    call("snap_faces", type="axis", move={"part": "I2", "face": "F4:side:c1"}, onto={"part": "I1", "face": "H1:hole:0".replace("H1", "F3")})
    call("snap_faces", type="touch", move={"part": "I2", "face": "F2:end"}, onto={"part": "I1", "face": "F2:end"})
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    print("joints:", [(j["type"], j["part"], j["onto"]) for j in joints()], "| pin at", pin_pos())
    select("I2")
    print("labels:", [r.text.split("\n")[0:2] for r in d.find_elements(By.CSS_SELECTOR, "#asmRight .as-jrow")][:1])

    # 🔒 the axis joint: moving by hand is refused
    d.find_elements(By.CSS_SELECTOR, "#asmRight [data-jlock]")[0].click()
    time.sleep(0.4)
    print("locked:", [j.get("locked", False) for j in json.loads(json.dumps(js(f"return {A}.doc.mates")))])
    before = pin_pos()
    select("I2")
    inp = d.find_element(By.CSS_SELECTOR, "#asmRight input[data-k=x]")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys("99", Keys.ENTER)
    time.sleep(0.5)
    print("move refused:", pin_pos() == before, "|", js("return [...document.querySelectorAll('.toast')].map(t => t.textContent).slice(-1)[0]"))
    print("✕ of a locked joint disabled:", js("return document.querySelectorAll('#asmRight [data-jdel][disabled]').length"))

    # unlocked: moving asks — no keeps everything, yes breaks the joints
    select("I2")
    d.find_elements(By.CSS_SELECTOR, "#asmRight [data-jlock]")[0].click()
    time.sleep(0.4)
    js("window.__asked = []; window.confirm = (q) => { window.__asked.push(q); return false; }")
    select("I2")
    inp = d.find_element(By.CSS_SELECTOR, "#asmRight input[data-k=x]")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys("99", Keys.ENTER)
    time.sleep(0.5)
    print("asked:", js("return window.__asked"), "| 'no' -> still", pin_pos() == before, len(joints()), "joints")
    js("window.confirm = () => true")
    select("I2")
    inp = d.find_element(By.CSS_SELECTOR, "#asmRight input[data-k=x]")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys("99", Keys.ENTER)
    time.sleep(0.5)
    print("'yes' -> moved", pin_pos()[0] == 99, "| joints", len(joints()))
    call("undo")
    time.sleep(0.8)
    print("undo -> joints", len(joints()), "| at", pin_pos())

    # ↻ turning about the axis joint
    select("I2")
    sl = d.find_elements(By.CSS_SELECTOR, "#asmRight input[data-jspin]")[0]
    print("spin now:", sl.get_attribute("value"), "| head's x direction", pin_x_dir())
    js("arguments[0].value = 87; arguments[0].dispatchEvent(new Event('input')); arguments[0].dispatchEvent(new Event('change'))", sl)
    time.sleep(0.6)
    print("slider 87 -> caught at 90: x direction", pin_x_dir(), "| still on the axis", pin_pos()[:2], "| joints", len(joints()))
    select("I2")
    num = d.find_elements(By.CSS_SELECTOR, "#asmRight input[data-jspinn]")[0]
    num.send_keys(Keys.CONTROL, "a")
    num.send_keys("30", Keys.ENTER)
    time.sleep(0.6)
    print("30 typed -> x direction", pin_x_dir(), "(expected cos 30 = 0.866, sin 30 = 0.5)")
    d.save_screenshot(f"{OUT}/lock1.png")
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
