"""🔒 Lock a motion by one click, in headless Edge: a Ø6 pin concentric in a base's hole (it slides and turns) -> 🔒 by
its turn: the joint's turn is set (1 way left) -> 🔒 by its slide: the joint's distance (fully held, not moved) -> a lid
touching the base (it slides two ways and turns) -> 🔒 by "Along X": a new flush joint of side faces at the distance
they are, the lid not moved -> the AI: lock_motion the rest -> fully held.

  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_lockmotion.py http://127.0.0.1:5199 <out dir>
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


def ways(inst):
    return js(f"return {A}.motionsOf(arguments[0])?.count", inst)


def lock(text):
    """🔒 in the row of the motion whose name has `text`."""
    rows = d.find_elements(By.CSS_SELECTOR, "#asmRight .as-dof")
    row = next(r for r in rows if text in r.find_element(By.CSS_SELECTOR, "label").text)
    row.find_element(By.CSS_SELECTOR, "[data-dlock]").click()
    time.sleep(0.6)


def matrix(inst):
    return js(f"return {A}.inst(arguments[0]).matrix", inst)


def moved(inst, m0):
    """How far its matrix is from m0 (the biggest difference)."""
    return round(max(abs(a - b) for a, b in zip(matrix(inst), m0)), 5)


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
    call("new_model", name="Lid")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 30}}])
    call("add_feature", type="extrude", sketch="F1", d=4)
    call("new_assembly", name="Locks")
    for p in ("Base", "Pin", "Lid"):
        call("insert_part", part=p)
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    hole = js(f"return {A}.bodies[{A}.inst('I1').part].body.faces.find(f => f.type === 'cylinder').name")
    call("snap_faces", type="axis", move={"part": "I2", "face": "F2:side:c1"}, onto={"part": "I1", "face": hole})
    js(f"const m = {A}.doc.mates.find(x => x.move === 'I2'); delete m.dist; delete m.angle; {A}.applyMates(); {A}.commit()")
    pick("I2")
    print("the pin: ways", ways("I2"))
    before = matrix("I2")
    lock("Turn: Pin")
    m = js(f"return {A}.doc.mates.find(x => x.move === 'I2')")
    print("🔒 its turn: angle", m.get("angle"), "| ways", ways("I2"))
    pick("I2")
    lock("Slide: Pin")
    m = js(f"return {A}.doc.mates.find(x => x.move === 'I2')")
    print("🔒 its slide: dist", m.get("dist"), "side", m.get("side"), "| ways", ways("I2"), "| moved by", moved("I2", before))
    print("  the panel:", d.find_element(By.CSS_SELECTOR, "#asmRight").text.count("Fully held") == 1)

    call("snap_faces", type="touch", move={"part": "I3", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})
    call("move_free", part="I3", motion="X", amount=7.5)
    pick("I3")
    n0, before = ways("I3"), matrix("I3")
    print("the lid: ways", n0, [r.find_element(By.CSS_SELECTOR, "label").text for r in d.find_elements(By.CSS_SELECTOR, "#asmRight .as-dof")])
    lock("along X")
    new = js(f"return {A}.doc.mates.filter(x => x.move === 'I3').slice(1)")
    print("🔒 along X:", [(j["type"], j["face"], j["ontoFace"], j["gap"]) for j in new], "| ways", ways("I3"), "| moved by", moved("I3", before))
    print("AI lock_motion:", call("lock_motion", part="I3", motion=0)[:70], "| ways", ways("I3"), "| moved by", moved("I3", before))
    print("AI on a held part:", call("lock_motion", part="I3", motion=0)[:60])
    print("the joints hold:", js(f"return {A}.doc.mates.every(m => !m.broken) && {A}.unmet().length === 0"))
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
