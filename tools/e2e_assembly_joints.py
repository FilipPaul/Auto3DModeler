"""Assembly joints and turning, with REAL mouse input in headless Edge: a 60 x 40 x 5 plate with a Ø8 hole and a
headed pin (head Ø14 x 3, shaft Ø8 x 20) -> 🔗 Joint ▾ Pin in hole: the pin's shaft, then the plate's hole (the face
under the mouse is marked) -> the pin on the hole's axis -> 🔗 Joint ▾ Touch: the underside of the head... (its top
face, as modelled) onto the plate's top -> the pin goes down into the hole, head on the plate -> the joints are listed
(hovering one marks its faces), a gap typed -> the head lifts -> ✕ removes a joint; the plate made thicker in its tab
-> the pin follows; turning with the slider (it catches at 90°) and an exact angle typed.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_joints.py http://127.0.0.1:5199 <out dir>
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


def move(inst, local):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *screen_of(inst, local)).perform()
    time.sleep(0.3)


def click(inst, local):
    move(inst, local)
    ActionChains(d).click().perform()
    time.sleep(0.6)


def joint_menu(kind):
    time.sleep(0.2)
    d.find_element(By.CSS_SELECTOR, f"#asmViewport [data-joint={kind}]").click()
    time.sleep(0.3)


def pin_box():
    return next(p["bbox"] for p in json.loads(call("get_assembly"))["parts"] if p["id"] == "I2")


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=8)
    call("new_model", name="Pin")
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 14}}])
    call("add_feature", type="extrude", sketch="F1", d=3)
    call("add_feature", type="sketch", plane={"face": "F2:end"}, shapes=[{"circle": {"x": 0, "y": 0, "d": 8}}])
    call("add_feature", type="extrude", sketch="F3", d=20)
    time.sleep(1)
    call("new_assembly", name="Pinned")
    call("insert_part", part="Plate")
    call("insert_part", part="Pin")
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    call("place_part", part="I2", z=30)  # above the plate, so its faces are not hidden in it
    js(f"{A}.view.setView('iso')")
    time.sleep(0.6)

    # Pin in hole: the pin's shaft (r 4, at height 12), then the plate's hole wall (its far side)
    joint_menu("axis")
    print("hint:", js("return document.querySelector('#asmViewport .m-hint').textContent"))
    move("I2", [-4, 0, 12])
    print("hover marks a round face:", js(f"return !!{A}.hoverFace?.ok"))
    ActionChains(d).click().perform()
    time.sleep(0.5)
    click("I1", [30, 24, 2.5])
    b = pin_box()
    print("pin in hole: pin axis at", round((b[0] + b[3]) / 2, 3), round((b[1] + b[4]) / 2, 3), "(hole at 30, 20) | z", b[2], b[5], "(still above)")

    # Touch: the head's top face (z 3 in the pin) onto the plate's top -> the pin turns over into the hole
    js(f"{A}.view.setView('iso')")
    time.sleep(0.4)
    joint_menu("touch")
    click("I2", [5.5, 0, 3])
    click("I1", [10, 10, 5])
    b = pin_box()
    print("touch: pin z", b[2], "to", b[5], "(expected 5 - 20 = -15 .. 8) | axis", round((b[0] + b[3]) / 2, 3), round((b[1] + b[4]) / 2, 3))
    d.save_screenshot(f"{OUT}/joints1.png")

    js(f"{A}.sel = 'I2'; {A}.render(); {A}.draw()")
    time.sleep(0.3)
    rows = d.find_elements(By.CSS_SELECTOR, "#asmRight .as-jrow")
    print("joints listed:", [r.text.replace("\n", " ") for r in rows])
    ActionChains(d).move_to_element(rows[0]).perform()
    time.sleep(0.3)
    print("hovering a joint marks its faces:", js(f"return {A}.view.markGroup.children.length"))
    gap = d.find_element(By.CSS_SELECTOR, "#asmRight [data-jgap]")
    gap.send_keys(Keys.CONTROL, "a")
    gap.send_keys("2", Keys.ENTER)
    time.sleep(0.6)
    print("gap 2 -> pin top z", pin_box()[5], "(expected 10)")

    # the plate gets thicker: the pin follows
    next(t for t in d.find_elements(By.CSS_SELECTOR, "#partTabs .part-tab") if t.text.startswith("Plate")).click()
    wait("return document.body.classList.contains('ws-model')")
    time.sleep(0.6)
    call("edit_feature", id="F2", fields={"d": 8})
    time.sleep(1)
    next(t for t in d.find_elements(By.CSS_SELECTOR, "#partTabs .part-tab") if t.text.startswith("Pinned")).click()
    wait("return document.body.classList.contains('ws-assembly')")
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    time.sleep(0.8)
    print("plate 8 thick -> pin top z", pin_box()[5], "(expected 13)")

    # ✕ the gap joint: the pin stays where it is
    js(f"{A}.sel = 'I2'; {A}.render()")
    time.sleep(0.3)
    d.find_elements(By.CSS_SELECTOR, "#asmRight [data-jdel]")[-1].click()
    time.sleep(0.5)
    print("after ✕:", [j["type"] for j in json.loads(call("get_assembly"))["joints"]], "| pin top z", pin_box()[5])

    # turning: the plate, by the slider (it catches at 90°) and by a typed angle
    js(f"{A}.sel = 'I1'; {A}.render()")
    time.sleep(0.3)
    sl = d.find_element(By.CSS_SELECTOR, "#asmRight input[data-rot=z]")
    js("arguments[0].value = 88; arguments[0].dispatchEvent(new Event('input')); arguments[0].dispatchEvent(new Event('change'))", sl)
    time.sleep(0.6)
    print("slider 88 -> caught at", d.find_element(By.CSS_SELECTOR, "#asmRight input[data-rotn=z]").get_attribute("value"),
          "| plate x axis now", [round(v, 3) for v in js(f"return {A}.inst('I1').matrix.slice(0, 3)")], "| pin follows (axis):",
          [round(v, 2) for v in pin_box()])
    num = d.find_element(By.CSS_SELECTOR, "#asmRight input[data-rotn=z]")
    num.send_keys(Keys.CONTROL, "a")
    num.send_keys("37.5", Keys.ENTER)
    time.sleep(0.6)
    print("typed 37.5° -> z angle", d.find_element(By.CSS_SELECTOR, "#asmRight input[data-rotn=z]").get_attribute("value"))
    d.save_screenshot(f"{OUT}/joints2.png")
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
