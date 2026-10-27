"""A lever on a bearing on a shaft, in headless Edge (the AI's reports of 2026-10-27): the bearing turns on the shaft
(concentric + touch), the arm is fixed on the bearing (concentric, turn locked + flush) -> the arm is not "fully
held": it moves with the bearing ("Turn about … — with Bearing"), its slider / move_free turn the bearing and the arm
goes along -> 🔓 free / 🔒 locked on a flat joint: locked, the bearing is fully held; free again -> a joint named by
a double-click ("ložisko na tyč"), shown in get_assembly; edit_joint name -> Explode with Respect joints: the bearing
and the arm go along with the base; without the touch the bearing comes off the shaft only along its axis.

  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_lever.py http://127.0.0.1:5199 <out dir>
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


def call(t, **a):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", t, a)


def part(i):
    return next(p for p in json.loads(call("get_assembly"))["parts"] if p["id"] == i)


def turned(i):
    """How far a part is turned about Z (degrees, from its matrix)."""
    return js(f"const m = {A}.inst(arguments[0]).matrix; return +(Math.atan2(m[1], m[0]) * 180 / Math.PI).toFixed(1)", i)


def pick(i):
    js(f"{A}.choose(arguments[0])", i)
    time.sleep(0.5)


def row(jid):
    return d.find_element(By.CSS_SELECTOR, f"#asmRight [data-jrow={jid}]")


try:
    d.get(URL)
    time.sleep(2)
    call("new_model", name="Base")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 60}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="sketch", plane={"face": "F2:end"}, shapes=[{"circle": {"x": 0, "y": 0, "d": 10}}])
    call("add_feature", type="extrude", sketch="F3", d=30)
    call("new_model", name="Bearing")
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 22}}])
    call("add_feature", type="extrude", sketch="F1", d=7)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=10)
    call("new_model", name="Arm")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 30, "y": 0, "w": 80, "h": 30}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=22)
    call("new_assembly", name="Lever")
    for p in ("Base", "Bearing", "Arm"):
        call("insert_part", part=p)
    time.sleep(1.5)
    S = lambda **a: call("snap_faces", **a)[:30]  # noqa: E731
    S(type="axis", move={"part": "I2", "face": "F3:hole:0"}, onto={"part": "I1", "face": "F4:side:c1"})
    S(type="touch", move={"part": "I2", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})
    S(type="axis", move={"part": "I3", "face": "F3:hole:0"}, onto={"part": "I2", "face": "F2:side:c1"}, lock_rotation=True)
    S(type="flush", move={"part": "I3", "face": "F2:start"}, onto={"part": "I2", "face": "F2:start"})
    arm = part("I3")
    print("the arm:", arm.get("free"), "| fully held:", arm.get("fully_held", False))
    b0, a0 = turned("I2"), turned("I3")
    print("move_free the arm 30°:", call("move_free", part="I3", motion=0, amount=30)[:70])
    print("  bearing turned", b0, "->", turned("I2"), "| arm", a0, "->", turned("I3"))

    pick("I3")
    print("the arm's panel:", d.find_element(By.CSS_SELECTOR, "#asmRight .as-dof label").text, "|", d.find_elements(By.CSS_SELECTOR, "#asmRight h3 + .hint")[0].text[:70])
    js("""const s = document.querySelector('#asmRight [data-dof]'); s.value = +s.value + 45; s.dispatchEvent(new Event('input')); s.dispatchEvent(new Event('change'))""")
    time.sleep(0.6)
    print("its slider +45°: bearing", turned("I2"), "| arm", turned("I3"))

    pick("I2")
    b = row("J2").find_element(By.CSS_SELECTOR, "[data-jrot]")
    print("J2 (touch) turn:", b.text, "| bearing:", part("I2").get("free"))
    pick("I2")
    row("J2").find_element(By.CSS_SELECTOR, "[data-jrot]").click()
    time.sleep(0.5)
    txt = row("J2").find_element(By.CSS_SELECTOR, "[data-jrot]").text
    print("clicked:", txt, "| bearing fully held:", part("I2").get("fully_held", False))
    pick("I2")
    row("J2").find_element(By.CSS_SELECTOR, "[data-jrot]").click()
    time.sleep(0.5)
    txt = row("J2").find_element(By.CSS_SELECTOR, "[data-jrot]").text
    print("again:", txt, "| bearing:", part("I2").get("free"))

    pick("I2")
    nm = row("J1").find_element(By.CSS_SELECTOR, "[data-jname]")
    ActionChains(d).double_click(nm).perform()
    time.sleep(0.2)
    ActionChains(d).send_keys("ložisko na tyč").send_keys(Keys.ENTER).perform()
    time.sleep(0.5)
    txt = row("J1").find_element(By.CSS_SELECTOR, "[data-jname]").text
    print("named:", txt, "|", [(j["id"], j.get("name")) for j in json.loads(call("get_assembly"))["joints"]][:2])
    print("edit_joint name:", json.loads(call("edit_joint", id="J3", name="páka na ložisko")).get("name"))
    d.save_screenshot(f"{OUT}/lever.png")

    js(f"{A}.sel = null; {A}.explode = 1; {A}.explodeRespect = true; {A}.exDirs = null; {A}.render(); {A}.draw()")
    off = lambda: js(f"return {A}.view.meshes.map(m => [m.userData.inst, ...new ({A}.view.camera.position.constructor)().setFromMatrixPosition(m.matrix).toArray().map(v => +v.toFixed(2))])")  # noqa: E731
    pos0 = {i: js(f"return {A}.inst(arguments[0]).matrix.slice(12, 15).map(v => +v.toFixed(2))", i) for i in ("I1", "I2", "I3")}
    o = {r[0]: [round(r[k + 1] - pos0[r[0]][k], 2) for k in range(3)] for r in off()}
    print("explode, respect joints: offsets", o, "| all the same (they go along):", o["I1"] == o["I2"] == o["I3"])
    print("  the checkbox:", d.find_element(By.CSS_SELECTOR, "#asmViewport [data-a=exRespect]").is_selected())
    call("remove_joint", id="J2")  # the bearing can slide along the shaft now
    js(f"{A}.exDirs = null; {A}.draw()")
    o = {r[0]: [round(r[k + 1] - pos0[r[0]][k], 2) for k in range(3)] for r in off()}
    rel = [round(o["I2"][k] - o["I1"][k], 2) for k in range(3)]
    print("  without the touch: the bearing off the base's offset by", rel, "(only along the shaft's axis, z)")
    d.save_screenshot(f"{OUT}/lever_explode.png")
    js(f"{A}.explodeRespect = false; {A}.exDirs = null; {A}.draw()")
    o = {r[0]: [round(r[k + 1] - pos0[r[0]][k], 2) for k in range(3)] for r in off()}
    print("  not respecting: the bearing's own pull", [round(o["I2"][k] - o["I1"][k], 2) for k in range(3)])
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
