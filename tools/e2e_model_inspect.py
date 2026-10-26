"""Measure, section view and mass in the 3D model workspace, in headless Edge with real clicks: a 40 x 20 x 10 block
with a Ø6 hole (built through the AI tools) -> 📏 Measure: the top face (area), the hole's edge (Ø), two corners
(distance, Δx Δy Δz); ✂ Section along X / Y / Z with the slider; the material -> mass.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_model_inspect.py http://127.0.0.1:5199 <out dir>
"""
import json
import math
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"
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
    """An AI tool, called in the page the way the MCP bridge calls it."""
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#modelViewport canvas")


def off_xyz(p):
    return js(f"""const v = {M}.view, [x, y, z] = arguments[0];
      const [sx, sy] = v.toScreen(new (v.camera.position.constructor)(x, y, z)), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(p))


def click_xyz(p):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *off_xyz(p)).perform()
    time.sleep(0.2)
    ActionChains(d).click().perform()
    time.sleep(0.4)


def box():
    return js("return document.querySelector('.m-measure')?.innerText.replace(/\\n/g, ' ')")


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Block")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="hole", face="F2:end", d=6, points=[[0, 0]])
    wait(f"return {M}.result?.body && !{M}.inflight")
    time.sleep(0.5)
    js(f"{M}.view.setView('iso')")
    time.sleep(0.5)

    # 📏 Measure: the top face, the hole's edge, two corners
    d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=measure]").click()
    time.sleep(0.3)
    click_xyz([8, 10, 10])
    print("top face:", box(), "| expected area", round(800 - math.pi * 9, 3))
    click_xyz([8, 10, 10])  # the second spot (same face): a distance of ~0; start again
    click_xyz([20, 10 + 3, 10])  # on the hole's rim
    print("hole edge:", box())
    click_xyz([20, 10, 10.0001])  # second click to reset
    click_xyz([0, 0, 10])
    click_xyz([40, 20, 10])
    print("corner -> corner:", box(), "| expected", round(math.hypot(40, 20), 3))
    d.save_screenshot(f"{OUT}/x1_measure.png")
    d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=measure]").click()
    time.sleep(0.3)

    # ✂ Section
    d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=section]").click()
    time.sleep(0.4)
    print("section:", js(f"return [{M}.section, {M}.view.material.clippingPlanes.length]"))
    d.find_element(By.CSS_SELECTOR, ".m-section [data-ax=x]").click()
    time.sleep(0.3)
    js("const r = document.querySelector('.m-section input'); r.value = 20; r.dispatchEvent(new Event('input'))")
    time.sleep(0.3)
    print("section along x at 20:", js(f"return [{M}.section, {M}.view.material.clippingPlanes[0].constant]"))
    d.save_screenshot(f"{OUT}/x2_section.png")
    d.find_element(By.CSS_SELECTOR, ".m-section [data-x]").click()
    time.sleep(0.3)
    print("section off:", js(f"return [{M}.section, {M}.view.material.clippingPlanes.length]"))

    # material -> mass
    vol = js(f"return {M}.result.body.volume")
    print("mass PLA:", js("return [...document.querySelectorAll('#modelRight .mp-facts b')].map(b => b.textContent)"), "| expected", round(vol / 1000 * 1.24, 1))
    Select(d.find_element(By.CSS_SELECTOR, "#modelRight select[data-k=material]")).select_by_visible_text("PETG")
    time.sleep(0.4)
    print("mass PETG:", js("return [...document.querySelectorAll('#modelRight .mp-facts b')].map(b => b.textContent).pop()"), "| expected", round(vol / 1000 * 1.27, 1),
          "| AI sees:", json.loads(call("get_model"))["body"]["mass_g_solid"])
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
