"""⁂ Pattern with REAL mouse input in headless Edge: a 60 x 20 x 5 plate with one Ø4 hole (built through the AI tools) ->
⁂ Pattern: the hole is chosen, "How many" 5, "Apart" 12 -> exact volume; a click on the plate's short (y) edge
turns the row along y; ◌ Around on a disc with one hole: 6 around Z, then a click on a round face (the boss) for
its axis; the AI's add_feature pattern; deleting the hole deletes the pattern too.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_model_pattern.py http://127.0.0.1:5199 <out dir>
"""
import json
import math
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
    time.sleep(0.3)
    wait(f"return !{M}.inflight")
    time.sleep(0.3)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#modelViewport canvas")


def off_xyz(p):
    return js(f"""const v = {M}.view, [x, y, z] = arguments[0];
      const [sx, sy] = v.toScreen(new (v.camera.position.constructor)(x, y, z)), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(p))


def click_at(o):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *o).perform()
    time.sleep(0.2)
    ActionChains(d).click().perform()
    time.sleep(0.3)


def btn(sel):
    d.find_element(By.CSS_SELECTOR, sel).click()
    time.sleep(0.3)


def typed(k, value):
    inp = d.find_element(By.CSS_SELECTOR, f"#modelRight [data-k={k}]")
    inp.clear()
    inp.send_keys(str(value))
    settled()


def vol():
    return js(f"return {M}.result?.body?.volume")


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("add_feature", type="hole", face="F2:end", points=[[-24, 0]], d=4)
    settled()
    one = 6000 - math.pi * 4 * 5
    print("plate with one hole:", round(vol(), 3), "| expected", round(one, 3))

    btn("#modelViewport [data-a=pattern]")
    print("panel:", d.find_element(By.CSS_SELECTOR, "#modelRight .mp-body").text.replace("\n", " | "))
    typed("count", 5)
    typed("spacing", 12)
    print("5 holes, 12 apart:", round(vol(), 3), "| expected", round(6000 - 5 * math.pi * 4 * 5, 3))
    js(f"{M}.view.setView('iso')")
    time.sleep(0.4)
    d.save_screenshot(f"{OUT}/pat1_row.png")
    # a click on the short edge at x = 60 (along y) turns the row: with 12 apart along y the holes leave the plate
    click_at(off_xyz([60, 10, 5]))
    settled()
    print("direction from the edge:", js(f"return {M}.cmd.feature.dir"), "| Y button on:", js("return !!document.querySelector('#modelRight [data-ax=y].on')"))
    btn("#modelRight [data-ax=x]")
    settled()
    btn("#modelRight [data-a=ok]")
    settled()
    print("tree:", js(f"return [...document.querySelectorAll('#modelLeft .mt-item')].map(e => e.innerText.replace(/\\n/g, ' '))"))
    print("volume:", round(vol(), 3), "| ok:", js(f"return {M}.result.ok"))

    # delete the hole: the pattern needs it and goes too
    js("window.confirm = () => true")
    hole = js(f"return {M}.part.features.find(f => f.type === 'hole').id")
    js(f"{M}.remove(arguments[0])", hole)
    settled()
    print("after deleting the hole:", [f["type"] for f in js(f"return {M}.part.features")], round(vol(), 3))

    # around: a disc Ø60 with a boss Ø10 in the middle, one hole at 20 from the centre
    call("new_model", name="Flange")
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 60}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("add_feature", type="sketch", plane={"face": "F2:end"}, shapes=[{"circle": {"x": 0, "y": 0, "d": 10}}])
    call("add_feature", type="extrude", sketch="F3", d=10)
    call("add_feature", type="hole", face="F2:end", points=[[20, 0]], d=6)
    settled()
    base = math.pi * 900 * 5 + math.pi * 25 * 10
    btn("#modelViewport [data-a=pattern]")
    btn("#modelRight [data-kind=circular]")
    settled()
    print("around Z, 6:", round(vol(), 3), "| expected", round(base - 6 * math.pi * 9 * 5, 3))
    typed("count", 4)
    js(f"{M}.view.setView('iso')")
    time.sleep(0.4)
    # a click on the boss's round side: around its axis (the same Z axis here, so the volume stays)
    click_at(off_xyz([0, -5, 10]))
    settled()
    print("axis from the boss:", js(f"return {M}.cmd.feature.axis"), "| 4 around:", round(vol(), 3), "| expected", round(base - 4 * math.pi * 9 * 5, 3))
    d.save_screenshot(f"{OUT}/pat2_around.png")
    btn("#modelRight [data-a=ok]")
    settled()

    # the AI's way
    r = call("add_feature", type="pattern", of=["F5"], kind="circular", axis="z", count=3)
    print("AI pattern of the hole, 3 around:", r[:160])
    r = call("add_feature", type="pattern", of=["F5"], dir="y", count=2, spacing=50)
    print("AI pattern out of the part:", r[:200])
    print("AI bad of:", call("add_feature", type="pattern", of=["F1"], count=3))
    print("get_model pattern:", [s for s in json.loads(call("get_model"))["steps"] if s["type"] == "pattern"][:1])
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
