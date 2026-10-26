"""Panels made wider / narrower with the mouse, in headless Edge (REAL mouse drags), in a 3D model: the left panel's
edge dragged 100 px right -> 440 px, the 3D view narrower; the right panel's edge 80 px left -> 390 px; the AI chat's
edge 120 px left -> 560 px; remembered after a reload; a double-click on an edge -> the usual width again.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_panels.py http://127.0.0.1:5199 <out dir>
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


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def width(sel):
    return js("return Math.round(document.querySelector(arguments[0]).getBoundingClientRect().width)", sel)


def drag(sel, dx):
    h = d.find_element(By.CSS_SELECTOR, sel)
    ActionChains(d, duration=50).move_to_element(h).click_and_hold().move_by_offset(dx // 2, 0).move_by_offset(dx - dx // 2, 0).release().perform()
    time.sleep(0.5)


def open_model():
    wait("return !!window.__app")
    js("localStorage.removeItem('a3d.sizes'); return window.__app.agentHandlers.new_model({ name: 'Plate' })")
    wait("return window.__app.state.workspace === 'model'")
    time.sleep(0.5)


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('a3d.panels')")
    d.refresh()
    open_model()
    print("at first: left", width("#modelLeft"), "| right", width("#modelRight"), "| 3D view", width("#modelViewport canvas"))
    drag(".split-left", 100)
    print("left edge +100:", width("#modelLeft"), "| 3D view", width("#modelViewport canvas"))
    drag(".split-right", -80)
    print("right edge -80:", width("#modelRight"))
    js("document.getElementById('aiBtn').click()")
    time.sleep(0.4)
    print("chat at first:", width("#aiDrawer"))
    drag(".split-chat", -120)
    print("chat edge -120:", width("#aiDrawer"), "| the layout leaves room for it:", width("main.layout"))
    d.save_screenshot(f"{OUT}/panels.png")
    d.refresh()
    open_model()
    js("document.getElementById('aiBtn').click()")
    time.sleep(0.4)
    print("after a reload: left", width("#modelLeft"), "| right", width("#modelRight"), "| chat", width("#aiDrawer"))
    ActionChains(d).double_click(d.find_element(By.CSS_SELECTOR, ".split-left")).perform()
    time.sleep(0.4)
    print("double-click the left edge:", width("#modelLeft"))
    drag(".split-left", -300)
    print("dragged far: no narrower than", width("#modelLeft"))
finally:
    js("localStorage.removeItem('a3d.panels')")
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
