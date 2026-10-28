"""Concentric with a distance and a rotation lock, with REAL mouse input in headless Edge: two plates with a Ø8 hole
each -> 🔗 Joint ▾ Concentric: the upper plate's hole, then the lower plate's hole -> the holes on one axis and the
distance filled in (the plates touching) -> typed 30: the plates 30 mm apart -> the lower plate thicker: the upper one
follows (still 30 above) -> 🔓 free locks its turn (🔒 locked), the turn slider sets it -> the AI does the same with
snap_faces {type: "axis", gap, lock_rotation}.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_concentric.py http://127.0.0.1:5199 <out dir>
"""
import json
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


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#asmViewport canvas")


def screen_of(inst, local):
    return js(f"""const a = {A}, it = a.inst(arguments[0]), v = a.view, V = v.camera.position.constructor;
      const M = new (v.camera.matrix.constructor)().fromArray(it.matrix), p = new V(...arguments[1]).applyMatrix4(M);
      const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", inst, local)


def click(inst, local):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *screen_of(inst, local)).perform()
    time.sleep(0.3)
    ActionChains(d).click().perform()
    time.sleep(0.6)


def bbox(inst):
    return next(p["bbox"] for p in json.loads(call("get_assembly"))["parts"] if p["id"] == inst)


def hole_axis(inst):
    return js(f"const f = {A}.worldFace(arguments[0], 'F3:hole:0'); return [f.axis.o.x, f.axis.o.y].map(v => +v.toFixed(3))", inst)


def x_dir(inst):
    return js(f"const it = {A}.inst(arguments[0]); return [it.matrix[0], it.matrix[1], it.matrix[2]].map(v => +v.toFixed(3))", inst)


try:
    d.get(URL)
    wait("return !!window.__app")
    js("window.confirm = () => true")
    call("new_model", name="Lower")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=8)
    call("new_model", name="Upper")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 30, "h": 30}}])
    call("add_feature", type="extrude", sketch="F1", d=4)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=8)
    time.sleep(1)
    call("new_assembly", name="Stacked")
    call("insert_part", part="Lower")
    call("insert_part", part="Upper")
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    js(f"{A}.view.setView('iso')")
    time.sleep(0.6)

    time.sleep(0.2)
    d.find_element(By.CSS_SELECTOR, "#asmViewport [data-joint=axis]").click()
    time.sleep(0.3)
    click("I2", [15, 19, 2])  # the upper plate's hole wall (its far side)
    click("I1", [30, 24, 2.5])  # the lower plate's hole wall
    s = json.loads(call("get_assembly"))
    print("joint:", [(j["type"], j.get("distance"), j.get("rotation_locked")) for j in s["joints"]])
    print("holes on one axis:", hole_axis("I1"), hole_axis("I2"), "| upper z", bbox("I2")[2], "(touching the lower's top at 5)")

    js(f"{A}.sel = 'I2'; {A}.render(); {A}.draw()")
    time.sleep(0.3)
    print("row:", d.find_element(By.CSS_SELECTOR, "#asmRight .as-jrow").text.replace("\n", " "))
    box = d.find_element(By.CSS_SELECTOR, "#asmRight [data-jdist]")
    box.send_keys(Keys.CONTROL, "a")
    box.send_keys("30", Keys.ENTER)
    time.sleep(0.6)
    print("distance 30: upper z", bbox("I2")[2], "(expected 5 + 30 = 35) | still on the axis", hole_axis("I2"))
    d.save_screenshot(f"{OUT}/conc1.png")

    # the lower plate 8 thick: the upper one stays 30 above it
    print("  open:", call("open_part", id="Lower")[:80])
    print("  edit:", call("edit_feature", id="F2", fields={"d": 8})[:120])
    print("  back:", call("open_part", id="Stacked")[:80])
    wait(f"return window.__app.state.workspace === 'assembly' && Object.values({A}.bodies).every(b => b.body)")
    wait(f"return {A}.bodies[{A}.inst('I1').part].body.bbox[5] > 7.9", 60)
    time.sleep(0.5)
    print("lower 8 thick:", bbox("I1")[5], "| upper z", bbox("I2")[2], "(expected 38)")

    # the turn: free, then locked where it is, then set by the slider
    js(f"{A}.sel = 'I2'; {A}.render(); {A}.draw()")
    time.sleep(0.3)
    lock = d.find_element(By.CSS_SELECTOR, "#asmRight [data-jrot]")
    print("rotation button:", lock.text)
    lock.click()
    time.sleep(0.5)
    print("after the click:", d.find_element(By.CSS_SELECTOR, "#asmRight [data-jrot]").text, "| locked", json.loads(call("get_assembly"))["joints"][0]["rotation_locked"])
    num = d.find_element(By.CSS_SELECTOR, "#asmRight [data-jspinn]")
    num.send_keys(Keys.CONTROL, "a")
    num.send_keys("45", Keys.ENTER)
    time.sleep(0.6)
    print("turned 45: x direction", x_dir("I2"), "| still 30 above", bbox("I2")[2] if False else js(f"return +{A}.worldFace('I2', 'F3:hole:0').axis.o.z.toFixed(3)"), "| on the axis", hole_axis("I2"))
    js(f"{A}.view.setView('iso')")
    time.sleep(0.4)
    d.save_screenshot(f"{OUT}/conc2.png")

    # clearing the distance: it slides again (stays where it is)
    js(f"{A}.sel = 'I2'; {A}.render(); {A}.draw()")
    time.sleep(0.3)
    box = d.find_element(By.CSS_SELECTOR, "#asmRight [data-jdist]")
    box.send_keys(Keys.CONTROL, "a", Keys.DELETE, Keys.ENTER)
    time.sleep(0.5)
    print("distance cleared:", json.loads(call("get_assembly"))["joints"][0]["distance"], "| upper z", bbox("I2")[2])

    # the AI: a third plate 12 mm from the lower one (on top: they start inside each other), its turn locked
    call("insert_part", part="Upper")
    r = json.loads(call("snap_faces", type="axis", gap=12, lock_rotation=True, move={"part": "I3", "face": "F3:hole:0"}, onto={"part": "I1", "face": "F3:hole:0"}))
    j = r["joints"][-1]
    print("AI:", j["type"], "distance", j["distance"], "locked", j["rotation_locked"], "| I3 z", bbox("I3")[2], bbox("I3")[5], "| on the axis", hole_axis("I3"))
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
