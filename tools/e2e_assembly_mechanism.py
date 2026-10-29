"""⚙ Mechanism, in headless Edge: a crank – rod – slider (as e2e_assembly_loop: r 25, L 100) -> the widget shows in
the left column with the crank as its driver -> its slider to 90°: the slider's pin at x = r·cosθ + √(L² − r²·sin²θ)
-> ▶ plays (the parts move, the formula holds), ⏸ stops it where it is -> the mechanism and the crank's motion named by a
double-click (get_assembly, the part panel, undo / redo, the project saved and opened again) -> the AI's
drive_mechanism / name_motion -> the crank dragged round in the 3D view: the rod and the slider follow -> ✕ closes the
widget, ⚙ Mechanism in the toolbar opens it -> Czech labels -> a plain assembly (two plates touching): no widget, no
button.

  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_mechanism.py http://127.0.0.1:5199 <out dir>
"""
import json
import math
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
opts.add_argument("--lang=en-US")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
A = "window.__app.assembly"
H = "window.__app.agentHandlers"
W = "#leftCol .lw-widget[data-w=mech], #asmViewport .lw-widget[data-w=mech]"
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


def state():
    """The crank's angle θ (degrees, its pin about the shaft) and the slider's pin x from the shaft."""
    (sx, sy), (px, py), (qx, _) = js(f"return [['I1', 'F4:side:c1'], ['I2', 'F5:side:c1'], ['I4', 'F4:side:c1']].map(([i, n]) => {{ const f = {A}.worldFace(i, n); return [f.axis.o.x, f.axis.o.y]; }})")
    return math.degrees(math.atan2(py - sy, px - sx)), qx - sx


def expected(theta):
    t = math.radians(theta)
    return R * math.cos(t) + math.sqrt(L * L - (R * math.sin(t)) ** 2)


def miss():
    return js(f"return {A}.doc.mates.filter(m => {A}.whyNot(m)).map(m => m.id)")


def at_formula(what):
    th, x = state()
    e = expected(th)
    check(abs(x - e) < 0.05 and not miss(), f"{what}: θ {th:.1f}°, slider {x:.3f} mm, the formula {e:.3f} (joints not held: {miss()})")
    return th, x


def widget():
    els = [e for e in d.find_elements(By.CSS_SELECTOR, W) if e.is_displayed()]
    return els[0] if els else None


def slide(sel, v):
    js("const s = document.querySelector(arguments[0]); s.value = arguments[1]; s.dispatchEvent(new Event('input')); s.dispatchEvent(new Event('change'))", sel, v)


def rename(el, text):
    ActionChains(d).double_click(el).perform()
    time.sleep(0.2)
    ActionChains(d).send_keys(text).send_keys(Keys.ENTER).perform()
    time.sleep(0.5)


def mech():
    return (json.loads(call("get_assembly")).get("mechanisms") or [None])[0]


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('a3d.leftDock'); localStorage.setItem('auto3d-lang', 'en')")
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Base")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 240, "h": 60}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="sketch", plane={"face": "F2:end"}, shapes=[{"circle": {"x": -100, "y": 0, "d": 10}}])
    call("add_feature", type="extrude", sketch="F3", d=6)
    call("new_model", name="Crank")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 45, "h": 16}}])
    call("add_feature", type="extrude", sketch="F1", d=6)
    call("add_feature", type="hole", face="F2:end", points=[[-12.5, 0]], d=10)
    call("add_feature", type="sketch", plane={"face": "F2:end"}, shapes=[{"circle": {"x": 12.5, "y": 0, "d": 8}}])
    call("add_feature", type="extrude", sketch="F4", d=20)
    call("new_model", name="Rod")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 120, "h": 16}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("add_feature", type="hole", face="F2:end", points=[[-50, 0], [50, 0]], d=8)
    call("new_model", name="Slider")
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
    S(type="axis", move={"part": "I2", "face": hole("I2", 0)}, onto={"part": "I1", "face": "F4:side:c1"})
    S(type="touch", move={"part": "I2", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})
    S(type="axis", move={"part": "I3", "face": hole("I3", 0)}, onto={"part": "I2", "face": "F5:side:c1"})
    S(type="touch", move={"part": "I3", "face": "F2:start"}, onto={"part": "I2", "face": "F2:end"})
    S(type="touch", move={"part": "I4", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})
    S(type="flush", move={"part": "I4", "face": "F2:side:l1"}, onto={"part": "I1", "face": "F2:side:l1"}, gap=-15)
    a = json.loads(call("get_assembly"))
    along = next(i for i, m in enumerate(next(p for p in a["parts"] if p["id"] == "I4")["free"]) if "X" in m)
    qx = js(f"return {A}.worldFace('I4', 'F4:side:c1').axis.o.x")
    ex = js(f"return {A}.worldFace('I3', arguments[0]).axis.o.x", hole("I3", 1))
    call("move_free", part="I4", motion=along, amount=ex - qx)
    S(type="axis", move={"part": "I3", "face": hole("I3", 1)}, onto={"part": "I4", "face": "F4:side:c1"})
    time.sleep(0.5)

    # the widget: there by itself, the crank drives
    w = widget()
    check(w is not None and "Mechanism" in w.find_element(By.CSS_SELECTOR, ".lw-head b").text, "⚙ Mechanism shows in the left column by itself")
    m = mech()
    print("  mechanism:", m)
    check(m and m["driver"]["part"] == "I2" and m.get("full_turn") and m["min"] == 0 and m["max"] == 360 and sorted(m["parts"]) == ["I2", "I3", "I4"],
          f"one mechanism I2–I3–I4, the crank I2 drives it over a full turn: {m and m['driver']}")
    check(len(d.find_elements(By.CSS_SELECTOR, "#asmViewport .m-cmdbar [data-a=mech]")) == 1, "⚙ Mechanism in the toolbar")
    rows = w.find_elements(By.CSS_SELECTOR, ".mc-row")
    check(len(rows) == 1 and len(rows[0].find_elements(By.CSS_SELECTOR, "input[type=range]")) == 1, "one row, one slider")

    # its slider to 90°: the whole mechanism follows
    th0, _ = state()
    slide("[data-mcv='0']", 90)
    time.sleep(0.4)
    th, x = at_formula("the widget's slider to 90°")
    check(abs(abs(th - th0) - 90) < 1 or abs(abs(th - th0) - 270) < 1, f"the crank turned 90°: {th0:.1f}° -> {th:.1f}°")
    check(abs(float(d.find_element(By.CSS_SELECTOR, "[data-mcn='0']").get_attribute("value")) - 90) < 0.5, "its number shows 90")
    d.save_screenshot(f"{OUT}/mechanism_90.png")

    # ▶ plays: every part of it moves, the joints hold; ⏸ stops it where it is
    undo0 = js(f"return {A}.history.canUndo() && {A}.history.undoStack?.length")
    d.find_element(By.CSS_SELECTOR, "[data-mcplay='0']").click()
    seen, worst, n = set(), 0, 0
    start = {i: js(f"return [...{A}.inst(arguments[0]).matrix]", i) for i in ("I2", "I3", "I4")}
    end = time.time() + 2.5
    while time.time() < end:
        th, x = state()
        worst = max(worst, abs(x - expected(th)))
        n += 1
        for i in ("I2", "I3", "I4"):
            if any(abs(p - q) > 1e-3 for p, q in zip(js(f"return {A}.inst(arguments[0]).matrix", i), start[i])):
                seen.add(i)
        time.sleep(0.1)
    check(js(f"return !!{A}.mech.playing") and d.find_element(By.CSS_SELECTOR, "[data-mcplay='0']").text == "⏸", "▶ plays: the button shows ⏸")
    check(seen == {"I2", "I3", "I4"} and worst < 0.05 and n > 5, f"▶: all parts move ({sorted(seen)}), the slider off the formula by {worst:.4f} mm at most ({n} looks)")
    d.save_screenshot(f"{OUT}/mechanism_playing.png")
    d.find_element(By.CSS_SELECTOR, "[data-mcplay='0']").click()
    time.sleep(0.3)
    th1, x1 = state()
    time.sleep(0.5)
    th2, x2 = state()
    check(not js(f"return !!{A}.mech.playing") and abs(th1 - th2) < 1e-6, f"⏸ stops it where it is: θ {th1:.2f}° (stays {th2:.2f}°)")
    at_formula("after ⏸")

    # names: the mechanism and the crank's motion, by a double-click
    rename(d.find_element(By.CSS_SELECTOR, "[data-mcname='0']"), "Crank drive")
    check(mech()["name"] == "Crank drive" and "Crank drive" in widget().text, f"the mechanism renamed: {mech()['name']}")
    rename(d.find_element(By.CSS_SELECTOR, "[data-mcmo='0']"), "Crank turn")
    a = json.loads(call("get_assembly"))
    crank = next(p for p in a["parts"] if p["id"] == "I2")
    check("Crank turn" in crank.get("free", []) and a["mechanisms"][0]["driver"]["label"] == "Crank turn", f"the motion renamed: free {crank.get('free')}")
    js(f"{A}.choose('I2')")
    time.sleep(0.4)
    lab = d.find_element(By.CSS_SELECTOR, "#asmRight [data-mname='0']")
    check(lab.text == "Crank turn" and "own name" in (lab.get_attribute("title") or ""), f"the part panel's motion row: {lab.text}")
    rename(lab, "Turn of the crank")
    check(next(p for p in json.loads(call("get_assembly"))["parts"] if p["id"] == "I2")["free"][0] == "Turn of the crank", "renamed in the part panel too")
    gs = json.loads(call("gui_state"))
    check(any("Turn of the crank" in (c.get("label") or "") for c in gs["controls"]) and any("Crank drive" in (c.get("label") or "") for c in gs["controls"]),
          "gui_state shows both names")
    js(f"{A}.history.go(-1)")
    time.sleep(0.6)
    check(next(p for p in json.loads(call("get_assembly"))["parts"] if p["id"] == "I2")["free"][0] == "Crank turn", "undo: the name before")
    js(f"{A}.history.go(1)")
    time.sleep(0.6)
    check(next(p for p in json.loads(call("get_assembly"))["parts"] if p["id"] == "I2")["free"][0] == "Turn of the crank", "redo: the new name again")
    # saved and opened again
    proj = js("return window.__app.autosave.hooks.project()")
    js("return fetch('/api/project/migrate', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(arguments[0])}).then(r => r.json()).then(p => window.__app.project.loadAll(p))", proj)
    time.sleep(1)
    print(call("open_part", id="Crank slider")[:80])
    wait(f"return {A}.doc.instances.length === 4 && {A}.doc.instances.every(i => {A}.bodies[i.part]?.body) && {A}.mech.list.length")
    m = mech()
    check(m["name"] == "Crank drive" and m["driver"]["label"] == "Turn of the crank", f"opened again: {m['name']} · {m['driver']['label']}")

    # the AI: drive_mechanism, name_motion
    r = call("drive_mechanism", to=180)
    print("  drive_mechanism:", r[:160])
    at_formula("drive_mechanism to 180")
    check(abs(mech()["at"] - 180) < 0.5, f"at {mech()['at']}")
    r = call("name_motion", part="I4", motion=0, name="Slide")
    print("  name_motion:", r[:120])
    check(next(p for p in json.loads(call("get_assembly"))["parts"] if p["id"] == "I4")["free"][0] == "Slide", "name_motion: the slider's motion named")
    call("drive_mechanism", driver="I4 motion 0")
    _, x0 = state()
    r = call("drive_mechanism", to=mech()["at"] + 110 - x0)  # (its place along its motion: from its face, not the shaft)
    print("  drive_mechanism by the slider:", r[:160])
    th, x = at_formula("driven by the slider")
    check(abs(x - 110) < 0.05 and mech()["driver"]["part"] == "I4", f"the slider at 110 mm: {x:.3f}")
    r = call("drive_mechanism", driver="I2 motion 0", name="Klikový mechanismus")
    check(mech()["name"] == "Klikový mechanismus" and mech()["driver"]["part"] == "I2", "drive_mechanism: renamed, the crank drives again")

    # the crank dragged round in the view: the rod and the slider follow
    call("drive_mechanism", to=0)
    js(f"{A}.choose('I2'); {A}.view.setView('top')")
    time.sleep(0.8)
    cv = js(f"return {A}.view.renderer.domElement")
    scr = lambda p: js(f"const r = arguments[0].getBoundingClientRect(), v = new window.__THREE.Vector3(...arguments[1]).project({A}.view.camera); return [(v.x + 1) / 2 * r.width - r.width / 2, (1 - v.y) / 2 * r.height - r.height / 2]", cv, p)  # noqa: E731
    js(f"window.__THREE = {{ Vector3: {A}.view.camera.position.constructor }}")  # (three.js' Vector3: the screen place of a point)
    o = js(f"return {A}.worldFace('I2', arguments[0]).axis.o.toArray()", hole("I2", 0))
    pin = js(f"return {A}.worldFace('I2', 'F5:side:c1').axis.o.toArray()")
    bb = js(f"return {A}.bodies[{A}.inst('I2').part].body.bbox")
    top = bb[5] - 0.1 + js(f"return {A}.inst('I2').matrix[14]")
    grab = [(o[0] + pin[0]) / 2 + (pin[0] - o[0]) * 0.1, (o[1] + pin[1]) / 2, top]  # on the crank's top, toward the pin
    rr = math.hypot(grab[0] - o[0], grab[1] - o[1])
    th0, x0 = state()
    gx, gy = scr(grab)
    act = ActionChains(d, duration=20).move_to_element_with_offset(cv, int(gx), int(gy)).click_and_hold()
    path = []
    for k in range(1, 13):
        a_ = math.radians(7.5 * k)
        p = [o[0] + rr * math.cos(a_), o[1] + rr * math.sin(a_), top]
        sx, sy = scr(p)
        path.append((sx, sy))
        act = act.move_to_element_with_offset(cv, int(sx), int(sy))
    act.release().perform()
    time.sleep(0.6)
    th1, x1 = state()
    print(f"  dragged: θ {th0:.1f}° -> {th1:.1f}°, slider {x0:.2f} -> {x1:.2f}")
    check(abs(th1 - th0) > 45 and abs(x1 - x0) > 1, f"the crank dragged ~90° in the view: θ {th0:.1f}° -> {th1:.1f}°, the slider {x0:.2f} -> {x1:.2f} mm")
    at_formula("after the drag")
    d.save_screenshot(f"{OUT}/mechanism_dragged.png")

    # ✕ closes it, ⚙ Mechanism opens it again
    widget().find_element(By.CSS_SELECTOR, ".lw-close").click()
    time.sleep(0.3)
    check(widget() is None, "✕ closes the widget")
    d.find_element(By.CSS_SELECTOR, "#asmViewport .m-cmdbar [data-a=mech]").click()
    time.sleep(0.3)
    check(widget() is not None, "⚙ Mechanism in the toolbar opens it again")
    # ⋯: the drivers, ⚠ the travel, 📈 the trace
    d.find_element(By.CSS_SELECTOR, "[data-mcmore='0']").click()
    time.sleep(0.2)
    opts_ = [o.text for o in d.find_elements(By.CSS_SELECTOR, "[data-mcdrv='0'] option")]
    check(len(opts_) >= 2, f"⋯: a choice of driver {opts_}")
    d.find_element(By.CSS_SELECTOR, "[data-mctrace='0']").click()
    time.sleep(1)
    pts = js("return document.querySelector('.mc-trace polyline')?.getAttribute('points').split(' ').length || 0")
    lab = js("return document.querySelector('.mc-tlabel')?.textContent || ''")
    check(pts > 20 and "Slide" in lab, f"📈 trace: {pts} points, {lab}")
    at_formula("after the trace (where it was)")
    d.find_element(By.CSS_SELECTOR, "[data-mccheck='0']").click()
    note = wait("const n = document.querySelector('.mc-row .as-dofnote'); return n && !/Checking/.test(n.textContent) && n.textContent", 120)
    print("  ⚠ travel:", note)
    check("Klikový mechanismus" in note and ("Free" in note or "hits" in note), f"⚠ the travel checked: {note[:90]}")
    d.save_screenshot(f"{OUT}/mechanism_more.png")

    # Czech
    d.find_element(By.ID, "langBtn").click()
    time.sleep(0.6)
    w = widget()
    head = w.find_element(By.CSS_SELECTOR, ".lw-head b").text
    tip = d.find_element(By.CSS_SELECTOR, "[data-mcmo='0']").get_attribute("title")
    play = d.find_element(By.CSS_SELECTOR, "[data-mcplay='0']").get_attribute("title")
    check(head == "⚙ Mechanismus" and tip == "Dvojklik: dát mu vlastní název" and play.startswith("Přehrát"), f"Czech: {head} | {tip} | {play}")
    d.save_screenshot(f"{OUT}/mechanism_cs.png")
    d.find_element(By.ID, "langBtn").click()
    time.sleep(0.4)

    # a plain assembly: no mechanism, no widget, no button
    call("new_assembly", name="Plates")
    call("insert_part", part="Base")
    call("insert_part", part="Rod")
    wait(f"return {A}.doc.instances.length === 2 && {A}.doc.instances.every(i => {A}.bodies[i.part]?.body)")
    js(f"{A}.inst('I1').fixed = true")
    S(type="touch", move={"part": "I2", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})
    time.sleep(0.5)
    check(widget() is None and not d.find_elements(By.CSS_SELECTOR, "#asmViewport .m-cmdbar [data-a=mech]") and "mechanisms" not in json.loads(call("get_assembly")),
          "a plain assembly (a plate lying on another): no widget, no button, no mechanisms")
    d.save_screenshot(f"{OUT}/mechanism_none.png")
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE" and "favicon" not in e["message"] and "/api/ai/access" not in e["message"]]
    check(not errs, f"no errors in the console: {errs[:3]}")
finally:
    d.quit()

print("\nmechanism:", "ALL OK" if not bad else f"{len(bad)} FAILED: {bad}")
sys.exit(1 if bad else 0)
