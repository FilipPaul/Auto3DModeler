"""Editing a part from its assembly, in headless Edge: a plate with a pin joined into its hole -> the plate's panel:
✎ Edit it here is off while 🔒 Locked (a double-click says so) -> 🔓 -> ✎ Edit it here: the plate in the 3D modeler,
the pin see-through around it, a bar to go back -> a hole added to the plate there -> ◇ Back to the assembly: the
plate has the new hole, the pin still in its hole -> a double-click on the plate opens it again -> locked again.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_edit.py http://127.0.0.1:5199 <out dir>
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


def select(inst):
    js(f"{A}.sel = arguments[0]; {A}.render(); {A}.draw()", inst)
    time.sleep(0.3)


def edit_buttons():
    b = d.find_element(By.CSS_SELECTOR, "#asmRight [data-a=editHere]")
    return b.is_enabled(), d.find_element(By.CSS_SELECTOR, "#asmRight [data-a=editLock]").text


def dblclick(inst, local):
    off = js(f"""const a = {A}, it = a.inst(arguments[0]), v = a.view, V = v.camera.position.constructor;
      const M = new (v.camera.matrix.constructor)().fromArray(it.matrix), p = new V(...arguments[1]).applyMatrix4(M);
      const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", inst, local)
    ActionChains(d, duration=30).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, "#asmViewport canvas"), *off).perform()
    time.sleep(0.2)
    ActionChains(d).double_click().perform()
    time.sleep(0.8)


def toast():
    return js("return [...document.querySelectorAll('.toast')].map(t => t.textContent).slice(-1)[0]")


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=8)
    call("new_model", name="Pin")
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 8}}])
    call("add_feature", type="extrude", sketch="F1", d=20)
    time.sleep(1)
    call("new_assembly", name="Pinned")
    call("insert_part", part="Plate")
    call("insert_part", part="Pin")
    call("snap_faces", type="axis", move={"part": "I2", "face": "F2:side:c1"}, onto={"part": "I1", "face": "F3:hole:0"})
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    vol0 = js(f"return {A}.bodies[{A}.inst('I1').part].body.volume")
    js(f"{A}.view.setView('iso')")
    time.sleep(0.4)

    select("I1")
    print("locked:", edit_buttons())
    dblclick("I1", [50, 30, 5])
    print("double-click while locked:", toast(), "| workspace", js("return window.__app.state.workspace"))
    select("I1")
    d.find_element(By.CSS_SELECTOR, "#asmRight [data-a=editLock]").click()
    time.sleep(0.3)
    select("I1")
    print("unlocked:", edit_buttons())
    d.find_element(By.CSS_SELECTOR, "#asmRight [data-a=editHere]").click()
    wait(f"return window.__app.state.workspace === 'model' && !!{M}.result?.body && !{M}.inflight")
    time.sleep(0.4)
    print("editing:", js("return window.__app.project.current.name"), "| the rest see-through:", js(f"return {M}.view.ctxGroup?.children.length"),
          "| bar:", d.find_element(By.CSS_SELECTOR, "#modelViewport .m-ctx").text.replace("\n", " "))
    js(f"{M}.view.setView('iso')")
    time.sleep(0.4)
    d.save_screenshot(f"{OUT}/edit1.png")
    call("add_feature", type="hole", face="F2:end", points=[[20, 10]], d=6)
    wait(f"return !{M}.inflight")
    print("a hole added there:", js(f"return {M}.part.features.length"), "steps")
    d.find_element(By.CSS_SELECTOR, "#modelViewport [data-a=ctxBack]").click()
    wait(f"return window.__app.state.workspace === 'assembly' && {A}.bodies[{A}.inst('I1').part]?.body?.volume < " + str(vol0 - 1), 60)
    time.sleep(0.5)
    vol1 = js(f"return {A}.bodies[{A}.inst('I1').part].body.volume")
    pin = js(f"const f = {A}.worldFace('I2', 'F2:side:c1'); return [f.axis.o.x, f.axis.o.y].map(v => +v.toFixed(3))")
    print("back in the assembly: plate volume", round(vol0, 2), "->", round(vol1, 2), "(a Ø6 × 5 hole:", round(3.14159265 * 9 * 5, 2), ") | the pin's axis", pin)
    js(f"{A}.view.setView('iso')")
    time.sleep(0.4)
    dblclick("I1", [55, 35, 5])
    wait("return window.__app.state.workspace === 'model'", 30)
    print("double-click (unlocked):", js("return window.__app.project.current.name"))
    d.find_element(By.CSS_SELECTOR, "#modelViewport [data-a=ctxBack]").click()
    wait("return window.__app.state.workspace === 'assembly'", 30)
    time.sleep(0.5)
    select("I1")
    d.find_element(By.CSS_SELECTOR, "#asmRight [data-a=editLock]").click()
    time.sleep(0.3)
    select("I1")
    print("locked again:", edit_buttons(), "| saved in the assembly:", js(f"return {A}.payload().editable"))
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
