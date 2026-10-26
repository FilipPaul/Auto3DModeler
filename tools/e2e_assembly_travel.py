"""Motion with limits, in headless Edge: a Ø6 pin concentric in a base's hole (free to slide and turn) -> its slider shows
where it is along the axis -> ⇤⇥ limits: min / max typed -> the slider stops at max -> ⚠ Check the travel: free -> a
block put in its way -> checked again: it hits the block, from where to where -> ▶ plays min -> max -> min and ends
where it was -> the AI: get_assembly `at`, move_free `to` past the limit (stopped there), check_travel, set_travel off.

  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_travel.py http://127.0.0.1:5199 <out dir>
"""
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.by import By

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


def pick(inst):
    js(f"{A}.choose(arguments[0])", inst)
    time.sleep(0.4)


def along():
    """The row of the pin's move along the hole's axis."""
    rows = d.find_elements(By.CSS_SELECTOR, "#asmRight .as-dof")
    return next(r for r in rows if r.find_element(By.CSS_SELECTOR, "label").text.startswith("↔") and "axis" in r.text)


def z_of(inst):
    return js(f"return +{A}.inst(arguments[0]).matrix[14].toFixed(3)", inst)


def typed(el, value):
    el.clear()
    el.send_keys(str(value))
    js("arguments[0].dispatchEvent(new Event('change'))", el)
    time.sleep(0.5)


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Base")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 80, "h": 60}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="hole", face="F2:end", points=[[-25, -15]], d=6)
    call("new_model", name="Pin")
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 6}}])
    call("add_feature", type="extrude", sketch="F1", d=20)
    call("new_model", name="Stop")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 20, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=6)
    call("new_assembly", name="Travel")
    for p in ("Base", "Pin"):
        call("insert_part", part=p)
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    hole = js(f"return {A}.bodies[{A}.inst('I1').part].body.faces.find(f => f.type === 'cylinder').name")
    print("pin in the hole:", call("snap_faces", type="axis", move={"part": "I2", "face": "F2:side:c1"}, onto={"part": "I1", "face": hole})[:40])
    js(f"const m = {A}.doc.mates.find(x => x.move === 'I2'); delete m.dist; delete m.angle; {A}.applyMates(); {A}.commit()")
    js(f"{A}.view.setView('front')")
    pick("I2")
    row = along()
    p0 = float(row.find_element(By.CSS_SELECTOR, "[data-dofn]").get_attribute("value"))
    print("where it is along the axis:", p0, "| its z:", z_of("I2"))

    row.find_element(By.CSS_SELECTOR, "[data-dlim]").click()
    time.sleep(0.5)
    row = along()
    print("⇤⇥ limits shown:", [e.get_attribute("value") for e in row.find_elements(By.CSS_SELECTOR, "[data-dmin], [data-dmax]")])
    typed(along().find_element(By.CSS_SELECTOR, "[data-dmin]"), p0)
    typed(along().find_element(By.CSS_SELECTOR, "[data-dmax]"), p0 + 30)
    row = along()
    sl = row.find_element(By.CSS_SELECTOR, "[data-dof]")
    print("limits:", js(f"return {A}.inst('I2').travel"), "| the slider from", sl.get_attribute("min"), "to", sl.get_attribute("max"))
    typed(row.find_element(By.CSS_SELECTOR, "[data-dofn]"), p0 + 100)
    print("typed 100 past it: stops at max — at", along().find_element(By.CSS_SELECTOR, "[data-dofn]").get_attribute("value"), "| z", z_of("I2"))
    typed(along().find_element(By.CSS_SELECTOR, "[data-dofn]"), p0)

    along().find_element(By.CSS_SELECTOR, "[data-dcheck]").click()
    wait("return !!document.querySelector('#asmRight .as-dofnote') && !/Checking/.test(document.querySelector('#asmRight .as-dofnote').textContent)", 90)
    print("check, nothing in the way:", d.find_element(By.CSS_SELECTOR, "#asmRight .as-dofnote").text, "| z back:", z_of("I2"))

    # a block above the hole, in the pin's way
    call("insert_part", part="Stop")
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    pin = js(f"""const b = {A}.bodies[{A}.inst('I2').part].body, V = {A}.view.camera.position.constructor, M = new ({A}.view.camera.matrix.constructor)().fromArray({A}.inst('I2').matrix);
      const lo = new V(b.bbox[0], b.bbox[1], b.bbox[2]).applyMatrix4(M), hi = new V(b.bbox[3], b.bbox[4], b.bbox[5]).applyMatrix4(M);
      return [(lo.x + hi.x) / 2, (lo.y + hi.y) / 2, Math.max(lo.z, hi.z)]""")
    call("place_part", part="I3", x=pin[0], y=pin[1], z=pin[2] + 10)
    pick("I2")
    along().find_element(By.CSS_SELECTOR, "[data-dcheck]").click()
    wait("return !!document.querySelector('#asmRight .as-dofnote') && !/Checking/.test(document.querySelector('#asmRight .as-dofnote').textContent)", 90)
    note = d.find_element(By.CSS_SELECTOR, "#asmRight .as-dofnote")
    print("check, a block 10 mm above:", note.text, "| red:", "bad" in note.get_attribute("class"), "| z back:", z_of("I2"))
    d.save_screenshot(f"{OUT}/travel.png")

    z0 = z_of("I2")
    along().find_element(By.CSS_SELECTOR, "[data-dplay]").click()
    time.sleep(1.4)
    z_mid = z_of("I2")
    wait(f"return !{A}.playing", 10)
    time.sleep(0.2)
    print("▶ plays: z", z0, "-> on the way", z_mid, "-> back", z_of("I2"))

    s = call("get_assembly")
    import json
    pin_s = next(p for p in json.loads(s)["parts"] if p["id"] == "I2")
    print("AI get_assembly at:", pin_s.get("at"))
    print("AI move_free to 1000:", call("move_free", part="I2", motion="axis", to=1000)[:110])
    print("AI check_travel:", call("check_travel", part="I2", motion="axis"))
    print("AI set_travel 5..8:", call("set_travel", part="I2", motion="axis", min=p0 + 5, max=p0 + 8))
    print("AI set_travel off:", call("set_travel", part="I2", motion="axis", min=None, max=None), "| travel:", js(f"return {A}.inst('I2').travel || null"))
    print("undo keeps working:", js(f"return {A}.history.canUndo?.() ?? true"))
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
