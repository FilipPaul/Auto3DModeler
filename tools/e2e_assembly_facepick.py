"""Faces picked with no tool on in an assembly, with REAL mouse input: a Base with a Ø6 hole and a Ø6 Pin -> a click on
the hole's rim: its face picked (lit), the Suggested table offers the joints it can start -> Ctrl+click on the pin's
round face: the joints that fit two round faces (Concentric) -> a click on it: the pin is concentric in the hole ->
a click on the Base's top and Ctrl+click on the pin's end: two flat faces — Touch, Flush, Gap …

  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_facepick.py http://127.0.0.1:5199 <out dir>
"""
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
H = "window.__app.agentHandlers"
A = "window.__app.assembly"


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(script)


def world(inst, p):
    return js(f"const m = {A}.inst(arguments[0]).matrix, [x, y, z] = arguments[1]; return [m[0]*x + m[4]*y + m[8]*z + m[12], m[1]*x + m[5]*y + m[9]*z + m[13], m[2]*x + m[6]*y + m[10]*z + m[14]]", inst, p)


def click(inst, p, ctrl=False):
    o = js(f"""const v = {A}.view, V = v.camera.position.constructor, [sx, sy] = v.toScreen(new V(...arguments[0])), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", world(inst, p))
    cv = d.find_element(By.CSS_SELECTOR, "#asmViewport canvas")
    ActionChains(d, duration=30).move_to_element_with_offset(cv, *o).perform()
    time.sleep(0.2)
    ch = ActionChains(d)
    (ch.key_down(Keys.CONTROL).click().key_up(Keys.CONTROL) if ctrl else ch.click()).perform()
    time.sleep(0.6)


def table():
    box = d.find_elements(By.CSS_SELECTOR, "#asmViewport .view-suggest")
    return [box[0].find_element(By.CSS_SELECTOR, ".vs-head b").text] + [" ".join(b.text.split()) for b in box[0].find_elements(By.CSS_SELECTOR, ".vs-list button")] if box else None


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Base")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=6, through=True)
    call("new_model", name="Pin")
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 6}}])
    call("add_feature", type="extrude", sketch="F1", d=20)
    call("new_assembly", name="Pinned")
    call("insert_part", part="Base")
    call("insert_part", part="Pin")
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    js(f"{A}.view.setView('iso')")
    time.sleep(0.8)
    bb = js(f"return {A}.bodies[{A}.inst('I1').part].body.bbox")
    hx, hy = (bb[0] + bb[3]) / 2, (bb[1] + bb[4]) / 2
    click("I1", [hx + 3, hy, bb[5]])           # the hole's rim on the top
    print("the hole's rim:", js(f"return ({A}.facePicks || []).map(q => [q.inst, q.face.name, q.face.type])"), "| the table:", table())
    print("  its sections:", js("return [...document.querySelectorAll('#asmViewport .view-suggest .vs-sec')].map(e => e.textContent)"))
    next(b for b in d.find_elements(By.CSS_SELECTOR, "#asmViewport .view-suggest .vs-list button") if "Select the whole part" in b.text).click()
    time.sleep(0.6)
    print("  ◆ Select the whole part: face picks", js(f"return ({A}.facePicks || []).length"), "| chosen", js(f"return {A}.sel"),
          "| the panel's moves:", bool(d.find_elements(By.CSS_SELECTOR, "#asmRight .mv-row, #asmRight [data-move], #asmRight input[type=range]")), "| the table:", (table() or [None])[:3])
    click("I1", [hx + 3, hy, bb[5]])           # the rim again
    click("I2", [3, 0, 10], ctrl=True)         # + the pin's round face
    print("+ the pin's round face:", js(f"return ({A}.facePicks || []).map(q => [q.inst, q.face.type])"), "| the table:", table())
    next(b for b in d.find_elements(By.CSS_SELECTOR, "#asmViewport .view-suggest .vs-list button") if "Concentric" in b.text).click()
    time.sleep(1)
    print("Concentric: the joints", js(f"return {A}.doc.mates.map(m => [m.type, m.move, m.onto])"), "| the pin on the hole's axis:",
          [round(v, 2) for v in world("I2", [0, 0, 0])[:2]], "vs", [hx, hy])
    click("I1", [bb[0] + 5, bb[1] + 5, bb[5]])  # the Base's top …
    # … and the pin's end (a small face: set as the click would)
    js(f"const a = {A}; a.facePicks = [a.facePicks[0], {{ inst: 'I2', face: a.worldFace('I2', 'F2:end') }}]; a.sel2 = 'I2'; a.render()")
    time.sleep(0.4)
    print("two flat faces:", table())
    d.save_screenshot(f"{OUT}/assembly_facepick.png")
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
