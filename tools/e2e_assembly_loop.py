"""A closed loop of joints, in headless Edge (the AI's report of 2026-10-29: a crank – rod – slider): a crank turns on
a base's shaft (concentric + touch), a rod on the crank's pin (concentric + touch), a slider in a line on the base
(touch + flush) and the rod's second eye on the slider's pin (concentric) -> all joints hold, get_assembly has one loop
(I2, I3, I4) with 1 free motion -> move_free the crank by 30° steps and 90° at once: the slider's pin at
x = r·cosθ + √(L² − r²·sin²θ) from the shaft (r 25, L 100), every joint held -> move_free the slider: the crank turns
-> the crank's slider in its panel (the loop's hint) -> set_travel 0 … 360 + check_travel: a full turn -> ▶ play: the
joints hold while it plays -> the slider's line moved 130 mm off (rod too short): "cannot close", the loop not closed
-> back: closed again.

  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_loop.py http://127.0.0.1:5199 <out dir>
"""
import json
import math
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
R, L = 25, 100
bad = []


def check(ok, what):
    print(("  ok  " if ok else "  FAIL") + " " + what)
    if not ok:
        bad.append(what)


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def call(t, **a):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", t, a)


def axis(i, face):
    """A round face's axis point in the world (x, y)."""
    return js(f"const f = {A}.worldFace(arguments[0], arguments[1]); return [f.axis.o.x, f.axis.o.y]", i, face)


def state():
    """The crank's angle θ (degrees, from its pin about the shaft) and the slider's pin x from the shaft."""
    (sx, sy), (px, py), (qx, _) = js(f"return [['I1', 'F4:side:c1'], ['I2', 'F5:side:c1'], ['I4', 'F4:side:c1']].map(([i, n]) => {{ const f = {A}.worldFace(i, n); return [f.axis.o.x, f.axis.o.y]; }})")  # (at once: ▶ moves them between two calls)
    return math.degrees(math.atan2(py - sy, px - sx)), qx - sx


def expected(theta):
    t = math.radians(theta)
    return R * math.cos(t) + math.sqrt(L * L - (R * math.sin(t)) ** 2)


def unheld():
    return [j["id"] for j in json.loads(call("get_assembly"))["joints"] if j.get("not_held")]


def at_angle(what):
    th, x = state()
    e = expected(th)
    check(abs(x - e) < 0.05 and not unheld(), f"{what}: θ {th:.1f}°, slider {x:.3f} mm, the formula {e:.3f} (joints not held: {unheld()})")


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Base")  # 240 × 60 × 10, a Ø10 shaft 6 high at x 20, y 30
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 240, "h": 60}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="sketch", plane={"face": "F2:end"}, shapes=[{"circle": {"x": -100, "y": 0, "d": 10}}])
    call("add_feature", type="extrude", sketch="F3", d=6)
    call("new_model", name="Crank")  # 45 × 16 × 6, its Ø10 hole and a Ø8 pin 25 apart
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 45, "h": 16}}])
    call("add_feature", type="extrude", sketch="F1", d=6)
    call("add_feature", type="hole", face="F2:end", points=[[-12.5, 0]], d=10)
    call("add_feature", type="sketch", plane={"face": "F2:end"}, shapes=[{"circle": {"x": 12.5, "y": 0, "d": 8}}])
    call("add_feature", type="extrude", sketch="F4", d=20)
    call("new_model", name="Rod")  # 120 × 16 × 5, two Ø8 eyes 100 apart
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 120, "h": 16}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("add_feature", type="hole", face="F2:end", points=[[-50, 0], [50, 0]], d=8)
    call("new_model", name="Slider")  # 30 × 30 × 5 with a Ø8 pin 25 high
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 30, "h": 30}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("add_feature", type="sketch", plane={"face": "F2:end"}, shapes=[{"circle": {"x": 0, "y": 0, "d": 8}}])
    call("add_feature", type="extrude", sketch="F3", d=25)
    call("new_assembly", name="Crank slider")
    for p in ("Base", "Crank", "Rod", "Slider"):
        call("insert_part", part=p)
    wait(f"return {A}.doc.instances.length === 4 && {A}.doc.instances.every(i => {A}.bodies[i.part]?.body)")
    js(f"{A}.inst('I1').fixed = true")
    S = lambda **a: call("snap_faces", **a)[:60]  # noqa: E731
    hole = lambda i, k: js(f"return {A}.bodies[{A}.inst(arguments[0]).part].body.faces.filter(f => f.type === 'cylinder' && /hole/.test(f.name)).map(f => f.name).sort()[arguments[1]]", i, k)  # noqa: E731
    print("J1", S(type="axis", move={"part": "I2", "face": hole("I2", 0)}, onto={"part": "I1", "face": "F4:side:c1"}))
    print("J2", S(type="touch", move={"part": "I2", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"}))
    print("J3", S(type="axis", move={"part": "I3", "face": hole("I3", 0)}, onto={"part": "I2", "face": "F5:side:c1"}))
    print("J4", S(type="touch", move={"part": "I3", "face": "F2:start"}, onto={"part": "I2", "face": "F2:end"}))
    print("J5", S(type="touch", move={"part": "I4", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"}))
    print("J6", S(type="flush", move={"part": "I4", "face": "F2:side:l1"}, onto={"part": "I1", "face": "F2:side:l1"}, gap=-15))
    th, _ = state()
    print("the crank at", round(th, 2), "° | the rod's eyes", hole("I3", 0), hole("I3", 1))
    # the slider under the rod's second eye (as the report: placed first, both joints agree at 0°)
    sl = json.loads(call("get_assembly"))
    along = next(i for i, m in enumerate(next(p for p in sl["parts"] if p["id"] == "I4")["free"]) if m.startswith("Slide"))
    qx = axis("I4", "F4:side:c1")[0]
    ex = axis("I3", hole("I3", 1))[0]
    print("move_free the slider:", call("move_free", part="I4", motion=along, amount=ex - qx)[:60])
    print("J7", S(type="axis", move={"part": "I3", "face": hole("I3", 1)}, onto={"part": "I4", "face": "F4:side:c1"}))
    a = json.loads(call("get_assembly"))
    print("loops:", a.get("loops"))
    lp = (a.get("loops") or [{}])[0]
    check(sorted(lp.get("parts", [])) == ["I2", "I3", "I4"] and lp.get("closed") and lp.get("free_motions") == 1,
          f"one closed loop I2–I3–I4 with 1 free motion: {lp}")
    check(not unheld(), f"all joints hold: not held {unheld()}")
    rod = next(p for p in a["parts"] if p["id"] == "I3")
    check(rod.get("loop") == "L1" or rod.get("moves_with_loop") == "L1", f"the rod is in the loop: {rod.get('loop') or rod.get('moves_with_loop')}")
    at_angle("0°")

    turn = next(i for i, m in enumerate(next(p for p in a["parts"] if p["id"] == "I2")["free"]) if m.startswith("Turn"))
    for k in range(1, 4):
        call("move_free", part="I2", motion=turn, amount=30)
        at_angle(f"+30° × {k}")
    call("move_free", part="I2", motion=turn, amount=90)
    at_angle("+90° at once")
    call("move_free", part="I2", motion=turn, amount=135)
    at_angle("+135° at once")
    call("move_free", part="I2", motion=turn, amount=-200)
    at_angle("−200° at once")

    # the slider drives: the crank turns
    th0, x0 = state()
    print("move_free the slider −10:", call("move_free", part="I4", motion=along, amount=-10)[:80])
    th1, x1 = state()
    check(abs((x1 - x0) + 10) < 0.05 and abs(th1 - th0) > 1, f"the slider −10 mm: {x0:.2f} -> {x1:.2f}, the crank turned {th0:.1f}° -> {th1:.1f}°")
    at_angle("driven by the slider")

    # the crank's panel: its slider turns it, the loop follows; the hint tells the loop
    js(f"{A}.choose('I2')")
    time.sleep(0.5)
    hint = d.find_element(By.CSS_SELECTOR, "#asmRight .as-loop").text
    check("I3" in hint and "I4" in hint, f"the crank's panel: {hint}")
    js("""const s = document.querySelector('#asmRight [data-dof]'); s.value = +s.value + 40; s.dispatchEvent(new Event('input')); s.dispatchEvent(new Event('change'))""")
    time.sleep(0.6)
    at_angle("its slider +40°")
    js(f"{A}.choose('I3')")
    time.sleep(0.5)
    check(not d.find_elements(By.CSS_SELECTOR, "#asmRight .mp-count") or "Fully held" not in d.find_element(By.CSS_SELECTOR, "#asmRight .mp-count").text,
          "the rod's panel: not 'fully held' (it moves with the loop)")
    d.save_screenshot(f"{OUT}/loop.png")

    # a full turn: limits, the travel checked, ▶ played
    print("set_travel:", call("set_travel", part="I2", motion=turn, min=0, max=360)[:90])
    t0 = time.time()
    r = call("check_travel", part="I2", motion=turn)
    print("check_travel:", r[:200], f"({time.time() - t0:.1f} s)")
    check(not r.startswith("ERROR"), "check_travel over a full turn")
    at_angle("after check_travel (where it was)")
    js(f"{A}.playTravel('I2', {A}.motionFor('I2', {turn}).mo)")
    worst, n, open_ = 0, 0, 0
    end = time.time() + 2.5
    while time.time() < end:
        th, x = state()
        worst = max(worst, abs(x - expected(th)))
        open_ += js(f"return ({A}.loops || []).some(l => !l.closed)")
        n += 1
        time.sleep(0.1)
    print("  not closed in", open_, "of", n, "looks")
    js(f"if ({A}.playing) {A}.playing.stop = true")
    time.sleep(0.5)
    check(worst < 0.05 and n > 5, f"▶ play: {n} looks, the slider off the formula by {worst:.4f} mm at most")
    at_angle("after ▶ (where it was)")
    check(open_ == 0, "the loop closed all through ▶")
    print("  placing all again (closed):", js(f"const t = performance.now(); for (let k = 0; k < 5; k++) {A}.applyMates(); return +((performance.now() - t) / 5).toFixed(1)"), "ms | a 3° turn followed:", js(f"const t = performance.now(), d = {A}.motionFor('I2', {turn}).mo; for (let k = 0; k < 5; k++) {A}.moveFree('I2', d, 3, null, false); return +((performance.now() - t) / 5).toFixed(1)"), "ms")

    # the slider pushed past its dead point (x = r + L): it stops there, the joints hold
    r = call("move_free", part="I4", motion=along, amount=80)
    th, x = state()
    print("move_free the slider +80:", r[:130])
    check("dead point" in r and abs(x - (R + L)) < 0.05 and abs(th) < 3 and not unheld(), f"stopped at the dead point: slider {x:.3f} (r + L = {R + L}), θ {th:.2f}°")
    call("move_free", part="I2", motion=turn, amount=60)
    at_angle("the crank on from there")

    # the second eye joined again with the slider out of place: the loop closes by itself (the least moves)
    j7 = next(j for j in json.loads(call("get_assembly"))["joints"] if j["onto"] == "I4" and j["type"] == "axis")
    call("remove_joint", id=j7["id"])
    call("move_free", part="I4", motion=along, amount=12)
    print("J8", S(type="axis", move={"part": "I3", "face": hole("I3", 1)}, onto={"part": "I4", "face": "F4:side:c1"}))
    at_angle("joined again 12 mm off: closed")

    # the rod too short: the slider's line 130 mm off the shaft
    print("J6 gap −145:", call("edit_joint", id="J6", gap=-145)[:60])
    a = json.loads(call("get_assembly"))
    lp = a.get("loops", [{}])[0]
    why = [j.get("not_held") for j in a["joints"] if j.get("not_held")]
    check(lp.get("closed") is False and why and "cannot close" in why[0], f"cannot close: closed {lp.get('closed')}, {why[:1]}")
    js(f"{A}.choose('I2')")
    time.sleep(0.5)
    print("  the panel:", d.find_element(By.CSS_SELECTOR, "#asmRight .as-loop").text, "| placing all again:", js(f"const t = performance.now(); for (let k = 0; k < 5; k++) {A}.applyMates(); return +((performance.now() - t) / 5).toFixed(1)"), "ms")
    call("edit_joint", id="J6", gap=-15)
    a = json.loads(call("get_assembly"))
    check(a.get("loops", [{}])[0].get("closed") and not unheld(), f"back: closed again {a.get('loops')}")
    at_angle("back")
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
print("FAILED:" if bad else "ALL OK", bad if bad else "")
sys.exit(1 if bad else 0)
