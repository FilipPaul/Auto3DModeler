"""Flexible sub-assemblies, in headless Edge: "Lever" (a base with a pin, a lever on the pin: one free turn) placed twice
in "Machine" (on a frame) -> get_assembly lists the turn as `inner` of each placement ("I2/I2") -> choosing the
placement shows "Moves inside Lever" with a slider -> the slider turns the lever in this view (the frame and the base
stay) -> saved on that placement (`inner`), the other placement and Lever's own document unchanged -> move_free
"I2/I2" to 90° -> undo / redo -> the collisions and the STEP see the turned lever (flatParts) -> ↺ As in Lever -> the
project file keeps `inner` -> a parallel joint of Machine on the arm turns it inside Lever and locks its turn (the
placement stays), taken away: it turns again -> Lever's own tab still has the lever where it was.

  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_flexsub.py http://127.0.0.1:5199 <out dir>
"""
import json
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
bad = []


def wait(script, t=90):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def call(t, **a):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", t, a)


def check(ok, what):
    print(("  ok   " if ok else "  FAIL ") + what)
    if not ok:
        bad.append(what)


def part(i):
    return next(p for p in json.loads(call("get_assembly"))["parts"] if p["id"] == i)


def inner_turn(i):
    """How far the lever inside placement i is turned about Z (degrees, from its matrix in the placement; 0: as in Lever)."""
    return js(f"""const it = {A}.inst(arguments[0]), m = it.inner?.I2 || {A}.hooks.partData(it.part).instances.find(x => x.id === 'I2').matrix;
      return +(Math.atan2(m[1], m[0]) * 180 / Math.PI).toFixed(1)""", i)


def flat_turn(fid):
    """The same, of the flat parts the kernel gets (collisions, sweep, STEP)."""
    return js(f"const m = {A}.flatParts().find(f => f.id === arguments[0]).matrix; return +(Math.atan2(m[1], m[0]) * 180 / Math.PI).toFixed(1)", fid)


def sub_doc():
    return next(p for p in js("return window.__app.project.toJSON()")["parts"] if p.get("name") == "Lever")["assembly"]


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Base")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 60}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="sketch", plane={"face": "F2:end"}, shapes=[{"circle": {"x": 0, "y": 0, "d": 10}}])
    call("add_feature", type="extrude", sketch="F3", d=30)
    call("new_model", name="Arm")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 30, "y": 0, "w": 80, "h": 16}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=10)
    call("new_model", name="Frame")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 300, "h": 120}}])
    call("add_feature", type="extrude", sketch="F1", d=8)

    call("new_assembly", name="Lever")
    call("insert_part", part="Base")
    call("insert_part", part="Arm")
    time.sleep(1)
    call("snap_faces", type="axis", move={"part": "I2", "face": "F3:hole:0"}, onto={"part": "I1", "face": "F4:side:c1"})
    call("snap_faces", type="touch", move={"part": "I2", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})
    arm = part("I2")
    check(len(arm.get("free", [])) == 1 and "Turn" in arm["free"][0], f"in Lever the arm turns one way: {arm.get('free')}")
    own0 = json.dumps(sub_doc()["instances"])

    call("new_assembly", name="Machine")
    call("insert_part", part="Frame")
    call("insert_part", part="Lever")
    call("insert_part", part="Lever")
    wait(f"return {A}.doc.instances.length === 3 && {A}.doc.instances.every(i => {A}.bodyOf(i)?.body)")
    call("snap_faces", type="touch", move={"part": "I2", "face": "I1/F2:start"}, onto={"part": "I1", "face": "F2:end"})
    call("snap_faces", type="touch", move={"part": "I3", "face": "I1/F2:start"}, onto={"part": "I1", "face": "F2:end"})
    call("place_part", part="I3", x=0, y=-200)
    p2 = part("I2")
    inner = p2.get("inner") or []
    check(len(inner) == 1 and inner[0]["part"] == "I2/I2" and "Turn" in inner[0]["free"][0], f"get_assembly: the placement's inner motions {inner}")

    # the panel: Moves inside Lever, a slider that turns the arm here
    js(f"{A}.choose('I2')")
    time.sleep(0.5)
    heads = [e.text for e in d.find_elements(By.CSS_SELECTOR, "#asmRight h3")]
    check(any(h.startswith("Moves inside Lever") for h in heads), f"panel headings {heads[:4]}")
    rows = d.find_elements(By.CSS_SELECTOR, "#asmRight [data-inner] [data-dof]")
    check(len(rows) == 1, f"one inner slider ({len(rows)})")
    frame0 = js(f"return [...{A}.inst('I1').matrix]")
    base0 = flat_turn("I2/I1")
    js("""const s = document.querySelector('#asmRight [data-inner] [data-dof]'); s.value = +s.value + 40; s.dispatchEvent(new Event('input')); s.dispatchEvent(new Event('change'))""")
    time.sleep(0.8)
    t1 = inner_turn("I2")
    check(abs(abs(t1) - 40) < 0.6, f"the slider turned the arm inside I2 by 40° ({t1})")
    check(js(f"return !!{A}.inst('I2').inner?.I2") and not js(f"return !!{A}.inst('I3').inner"), "kept on placement I2 only (I3 has no inner)")
    check(json.dumps(sub_doc()["instances"]) == own0, "Lever's own document unchanged")
    check(js(f"return {A}.inst('I1').matrix.every((v, k) => v === arguments[0][k])", frame0) and flat_turn("I2/I1") == base0, "the frame and the base stayed")
    check(abs(flat_turn("I2/I2") - t1) < 0.2, f"flatParts (collisions, STEP, drawings) see the turned arm ({flat_turn('I2/I2')})")
    face = js(f"return {A}.worldFace('I2', 'I2/F2:end').centroid.toArray().map(v => +v.toFixed(2))")
    print("  the arm's top face in the parent:", face)

    r = call("move_free", part="I2/I2", motion=0, to=90)
    check(not r.startswith("ERROR") and abs(abs(inner_turn("I2")) - 90) < 0.6, f"move_free I2/I2 to 90: {r[:60]} -> {inner_turn('I2')}")
    print("  move_free on a limit tool:", call("set_travel", part="I2/I2", motion=0, min=0, max=90)[:90])
    js(f"{A}.history.go(-1)")
    time.sleep(1.5)
    check(abs(abs(inner_turn("I2")) - abs(t1)) < 0.6, f"undo: back to {inner_turn('I2')}°")
    js(f"{A}.history.go(1)")
    time.sleep(1)
    check(abs(abs(inner_turn("I2")) - 90) < 0.6, f"redo: {inner_turn('I2')}°")
    d.save_screenshot(f"{OUT}/flexsub.png")

    clash = call("check_collisions")
    print("  collisions:", clash[:120])
    saved = next(p for p in js("return window.__app.project.toJSON()")["parts"] if p.get("name") == "Machine")["assembly"]["instances"]
    check(any(i.get("inner") for i in saved), "the project file keeps the placement's inner places")

    js(f"{A}.choose('I2')")
    time.sleep(0.5)
    d.find_element(By.CSS_SELECTOR, "#asmRight [data-a=innerReset]").click()
    time.sleep(0.8)
    check(not js(f"return !!{A}.inst('I2').inner") and inner_turn("I2") == 0, "↺ As in Lever: back where Lever has it")

    # this assembly's joints on the arm hold it inside Lever: a parallel joint to the frame's side locks the turn
    call("move_free", part="I2/I2", motion=0, to=40)
    place0 = js(f"return [...{A}.inst('I2').matrix]")
    r = json.loads(call("snap_faces", type="parallel", move={"part": "I2", "face": "I2/F2:side:l1"}, onto={"part": "I1", "face": "F2:side:l1"}))
    jid = r["joints"][-1]["id"]
    t2 = inner_turn("I2")
    check(abs(t2 % 180) < 0.6 or abs(t2 % 180 - 180) < 0.6, f"parallel joint {jid} on the arm (I2/F2:side:l1): the arm turned inside to {t2}°")
    check(js(f"return {A}.inst('I2').matrix.every((v, k) => Math.abs(v - arguments[0][k]) < 1e-6)", place0), "the placement itself did not move (its touch holds it)")
    p2 = part("I2")
    check(not p2.get("inner") and not any(j.get("not_held") for j in r["joints"]), f"the arm's turn is held now (inner: {p2.get('inner')}; joints hold)")
    js(f"{A}.choose('I2')")
    time.sleep(0.5)
    heads = [e.text for e in d.find_elements(By.CSS_SELECTOR, "#asmRight h3")]
    check(not any(h.startswith("Moves inside") for h in heads), f"no inner sliders while held ({heads[:3]})")
    check(json.dumps(sub_doc()["instances"]) == own0, "Lever's own document still unchanged")
    call("remove_joint", id=jid)
    time.sleep(0.5)
    check(len(part("I2").get("inner") or []) == 1, "the joint taken away: the arm turns again")

    call("open_part", id="Lever")
    time.sleep(1.5)
    check(json.dumps(sub_doc()["instances"]) == own0, "Lever's own tab: its parts where they were")
    lv = part("I2")
    check(lv.get("at", [{}])[0].get("deg") == 0 and not lv.get("inner"), f"in Lever the arm still at {lv.get('at')}")
finally:
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    d.quit()
print("FAILED:" if bad else "ALL OK", bad if bad else "")
