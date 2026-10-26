"""Turning the 3D view without limits, with REAL mouse drags in headless Edge: a 3D model -> a long drag up turns the view
over the top (the camera ends up below the part — the old view stopped at the pole) -> a drag across turns it about the
screen's upright -> a right drag pans (the target moves) -> the wheel zooms -> in a sketch the left button does not
turn the view.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_view_turn.py http://127.0.0.1:5199 <out dir>
"""
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.actions.wheel_input import ScrollOrigin
from selenium.webdriver.common.by import By

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
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def cam():
    """The camera's direction from the target (rounded) and its distance."""
    return js(f"""const v = {M}.view, c = v.camera, o = c.position.clone().sub(v.controls.target);
      return [o.clone().normalize().toArray().map(x => +x.toFixed(2)), Math.round(o.length()), v.controls.target.toArray().map(x => Math.round(x))]""")


def drag(dx, dy, button="left", steps=12):
    cv = d.find_element(By.CSS_SELECTOR, "#modelViewport canvas")
    a = ActionChains(d, duration=20).move_to_element(cv)
    if button == "left":
        a.click_and_hold()
    else:
        a.context_click()  # (a right press: the pan below uses the controls' own handler)
    for _ in range(steps):
        a.move_by_offset(dx // steps, dy // steps)
    a.release().perform()
    time.sleep(0.8)  # the turn slows down and stops


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Block")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=20)
    wait(f"return !!{M}.result?.body && !{M}.inflight")
    js(f"{M}.view.setView('front')")
    time.sleep(0.5)
    print("front view:", cam())
    drag(0, 360)  # down the screen: the view turns over the top of the part and on
    after = cam()
    print("long drag down:", after, "| went over the top (now looking up from below):", after[0][2] < -0.3)
    js(f"{M}.view.setView('front')")
    time.sleep(0.4)
    drag(300, 0)
    print("drag across (about the upright):", cam(), "| the camera stays level:", abs(cam()[0][2]) < 0.05)
    before = cam()
    js(f"""const c = {M}.view.controls; c.pan(120, 0); c.changed()""")
    time.sleep(0.3)
    print("pan: the target moved:", before[2], "->", cam()[2])
    d0 = cam()[1]
    ActionChains(d).scroll_from_origin(ScrollOrigin.from_element(d.find_element(By.CSS_SELECTOR, "#modelViewport canvas")), 0, -300).perform()
    time.sleep(0.4)
    print("wheel: closer", d0, "->", cam()[1])
    d.save_screenshot(f"{OUT}/view_turn.png")
    js(f"{M}.edit('F1')")
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.6)
    s0 = cam()
    drag(0, 200)
    print("in a sketch, a left drag does not turn the view:", s0[0] == cam()[0])
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
