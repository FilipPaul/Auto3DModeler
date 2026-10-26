"""Sliders in the 3D tools' panels, in headless Edge: every number of Extrude, Hole, Fillet, Chamfer, Shell, Revolve,
Pattern and Text / picture has a slider under it; moving it previews the part live (the volume changes), typing a
number moves the slider, OK keeps it.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_model_sliders.py http://127.0.0.1:5199 <out dir>
"""
import math
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
M = "window.__app.modeler"
H = "window.__app.agentHandlers"


def wait(script, t=30):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def settled():
    time.sleep(0.5)
    wait(f"return !{M}.inflight")
    time.sleep(0.3)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def sliders():
    return d.find_elements(By.CSS_SELECTOR, "#modelRight .mp-slider")


def slide(el, v):
    js("arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('input'))", el, v)
    settled()


def vol():
    return js(f"return {M}.result.body?.volume")


def open_edit(step_id):
    js(f"{M}.edit(arguments[0])", step_id)
    settled()


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Sliders")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=5)
    call("add_feature", type="fillet", edges=[{"a": "F2:side:l1", "b": "F2:side:l2", "fp": [40, 0, 5]}], r=2)
    settled()

    # Extrude: the distance's slider
    open_edit("F2")
    print("extrude sliders:", len(sliders()), "| panel numbers:", len(d.find_elements(By.CSS_SELECTOR, "#modelRight input[type=number]")))
    v0 = vol()
    slide(sliders()[0], 15)
    print("extrude slider 15 -> height", js(f"return {M}.result.body.bbox[5]"), "| number box", d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=d]").get_attribute("value"))
    inp = d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=d]")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys("12")
    time.sleep(0.2)
    print("typed 12 -> slider", sliders()[0].get_attribute("value"))
    settled()
    d.find_element(By.CSS_SELECTOR, "#modelRight [data-a=ok]").click()
    settled()
    print("kept: height", js(f"return {M}.result.body.bbox[5]"))

    # Hole: Ø and its distances
    open_edit("F3")
    print("hole sliders:", len(sliders()))
    v1 = vol()
    slide(sliders()[0], 8)
    print("hole Ø slider 8 -> volume", round(vol(), 2), "| expected", round(v1 - math.pi * (16 - 6.25) * 12, 2))
    d.find_element(By.CSS_SELECTOR, "#modelRight [data-a=ok]").click()
    settled()

    # Fillet: R
    open_edit("F4")
    print("fillet sliders:", len(sliders()))
    a = vol()
    slide(sliders()[0], 4)
    print("fillet R slider 4 -> volume smaller:", vol() < a)
    d.find_element(By.CSS_SELECTOR, "#modelRight [data-a=cancel]").click()
    settled()

    # Pattern (count, spacing) and Shell (wall), new
    js(f"{M}.startPattern()")
    settled()
    print("pattern sliders:", len(sliders()), [s.get_attribute("step") for s in sliders()])
    b = vol()
    slide(sliders()[0], 2)  # 3 -> 2 copies (a 4th would land outside the 40 mm part)
    print("count slider 2 -> count", js(f"return {M}.cmd.feature.count"), "| volume bigger (one hole less):", vol() > b)
    d.find_element(By.CSS_SELECTOR, "#modelRight [data-a=cancel]").click()
    settled()
    js(f"{M}.startShell()")
    settled()
    print("shell sliders:", len(sliders()))
    d.find_element(By.CSS_SELECTOR, "#modelRight [data-a=cancel]").click()
    settled()
    js(f"{M}.startDecal()")
    settled()
    print("text sliders:", len(sliders()))
    d.save_screenshot(f"{OUT}/sliders.png")
    d.find_element(By.CSS_SELECTOR, "#modelRight [data-a=cancel]").click()
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
