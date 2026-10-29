"""⚙ Couplings between motions, in headless Edge: a base with three pins, a pinion Ø30, a wheel Ø60 in mesh with it,
a pulley Ø30 apart and a rack beside the pinion -> Ctrl+click the two gears' rims: "⚙ Gear pair · i = 2:1" first ->
the pinion turned 90°: the wheel −45° (half, the other way) -> a belt wheel ↔ pulley: the pulley the same way, twice
as fast -> rim + the rack's side: "▤ Rack and pinion · 94.248 mm per turn" first -> the rack moves π·Ø per turn ->
one ⚙ Mechanism for the whole train: its slider, ▶ (the ratios hold while it plays), ⚠ the travel checked ->
the wheel dragged in the view: the pinion turns twice as far back -> the panel's ratio typed (3) and ⇄ -> undo ->
the AI's snap_faces type gear / belt / rack and get_assembly `couplings` -> Czech.

  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_gears.py http://127.0.0.1:5199 <out dir>
"""
import json
import math
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

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


def disc(name, dia):
    """A gear / pulley as its pitch circle: a disc Ø dia, 6 mm thick, a Ø10 hole in its middle."""
    call("new_model", name=name)
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": dia}}])
    call("add_feature", type="extrude", sketch="F1", d=6)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=10)


def faces(i, test):
    """A placed part's face names whose world face passes `test` (JS on f)."""
    return js(f"""const it = {A}.inst(arguments[0]), b = {A}.bodies[it.part].body;
      return [...new Set(b.faces.map(f => f.name))].filter(n => {{ const f = {A}.worldFace(arguments[0], n); return {test}; }})""", i)


def rim(i):
    return js(f"""const it = {A}.inst(arguments[0]), b = {A}.bodies[it.part].body;
      return b.faces.filter(f => f.type === 'cylinder').sort((p, q) => q.radius - p.radius)[0].name""", i)


def ang(i):
    """A part's turn about +Z (degrees, from its matrix)."""
    m = js(f"return {A}.inst(arguments[0]).matrix", i)
    return math.degrees(math.atan2(m[1], m[0]))


def ypos(i):
    return js(f"return {A}.inst(arguments[0]).matrix[13]", i)


def wrap(a):
    return (a + 180) % 360 - 180


def snapshot():
    """The three wheels' turns and the rack's y, read at one moment (▶ moves them between two reads)."""
    m = js(f"return ['I2', 'I3', 'I4', 'I5'].map(i => {A}.inst(i).matrix)")
    return {"g1": math.degrees(math.atan2(m[0][1], m[0][0])), "g2": math.degrees(math.atan2(m[1][1], m[1][0])), "p": math.degrees(math.atan2(m[2][1], m[2][0])), "rack": m[3][13]}


def pick(*qs):
    """Faces picked with no tool on (a click, then Ctrl+click) -> the suggestion table's rows."""
    js(f"""{A}.facePicks = arguments[0].map(([i, n]) => ({{ inst: i, face: {A}.worldFace(i, n) }})); {A}.sel = arguments[0][0][0]; {A}.sel2 = null; {A}.mode = 'idle'; {A}.renderSuggest()""", [list(q) for q in qs])
    time.sleep(0.3)
    return [" ".join(b.text.split()) for b in d.find_elements(By.CSS_SELECTOR, "#asmViewport .view-suggest .vs-list button")]


def couplings():
    return json.loads(call("get_assembly")).get("couplings", [])


def mech():
    return json.loads(call("get_assembly")).get("mechanisms") or []


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('a3d.leftDock'); localStorage.setItem('auto3d-lang', 'en')")
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Base")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 200, "h": 140}}])
    call("add_feature", type="extrude", sketch="F1", d=8)
    call("add_feature", type="sketch", plane={"face": "F2:end"}, shapes=[{"circle": {"x": x, "y": 0, "d": 10}} for x in (-30, 15, 85)])
    call("add_feature", type="extrude", sketch="F3", d=12)
    disc("Pinion", 30)
    disc("Wheel", 60)
    disc("Pulley", 30)
    call("new_model", name="Rack")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 12, "h": 120}}])
    call("add_feature", type="extrude", sketch="F1", d=6)
    call("new_assembly", name="Gearbox")
    for p in ("Base", "Pinion", "Wheel", "Pulley", "Rack"):
        call("insert_part", part=p)
    wait(f"return {A}.doc.instances.length === 5 && {A}.doc.instances.every(i => {A}.bodies[i.part]?.body)")
    js(f"{A}.inst('I1').fixed = true")
    pins = sorted(faces("I1", "f.type === 'cylinder'"), key=lambda n: js(f"return {A}.worldFace('I1', arguments[0]).axis.o.x", n))
    S = lambda **a: call("snap_faces", **a)[:70]  # noqa: E731
    for i, pin in zip(("I2", "I3", "I4"), pins):
        hole = next(n for n in faces(i, "f.type === 'cylinder'") if "hole" in n)
        S(type="axis", move={"part": i, "face": hole}, onto={"part": "I1", "face": pin})
        S(type="touch", move={"part": i, "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})
    S(type="touch", move={"part": "I5", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})
    back = faces("I5", "f.normal && f.normal.x < -0.99")[0]
    edge = faces("I1", "f.normal && f.normal.x < -0.99")[0]
    px = js(f"return {A}.worldFace('I2', arguments[0]).axis.o.x", rim("I2"))
    bx = js(f"return {A}.worldFace('I1', arguments[0]).centroid.x", edge)
    S(type="flush", move={"part": "I5", "face": back}, onto={"part": "I1", "face": edge}, gap=-(px - 15 - 12 - bx))  # (its front on the pinion's rim)
    front = faces("I5", "f.normal && f.normal.x > 0.99")[0]
    fx = js(f"return {A}.worldFace('I5', arguments[0]).centroid.x", front)
    check(abs(fx - (px - 15)) < 0.01 and not js(f"return {A}.unmet().length"), f"the parts placed: the rack's side (x {fx:.2f}) on the pinion's rim (x {px - 15:.2f})")

    # ⚙ two rims Ctrl+clicked: the gear pair first, with its ratio
    rows = pick(("I2", rim("I2")), ("I3", rim("I3")))
    print("  suggested:", rows)
    check(bool(rows) and rows[0] == "⚙ Gear pair · i = 2:1", f"two rims of turning parts: ⚙ Gear pair · i = 2:1 first ({rows[:3]})")
    check(any(r.startswith("⛓ Belt / chain") for r in rows), "⛓ Belt / chain offered too")
    d.save_screenshot(f"{OUT}/gears_suggest.png")
    d.find_elements(By.CSS_SELECTOR, "#asmViewport .view-suggest .vs-list button")[0].click()
    time.sleep(0.5)
    c = couplings()
    check(len(c) == 1 and c[0]["type"] == "gear" and c[0]["ratio"] == 2 and c[0]["way"] == "opposite", f"G1 made: {c}")
    m = mech()
    check(any(sorted(x["parts"]) == ["I2", "I3"] for x in m), f"one mechanism for the pair: {[x['parts'] for x in m]}")

    # the pinion turned 90°: the wheel −45°
    s0 = snapshot()
    print("  move_free:", call("move_free", part="I2", motion=0, amount=90)[:80])
    s1 = snapshot()
    d1, d2 = wrap(s1["g1"] - s0["g1"]), wrap(s1["g2"] - s0["g2"])
    check(abs(abs(d1) - 90) < 0.01 and abs(d2 + d1 / 2) < 0.01, f"ratio 2:1: the pinion {d1:.3f}°, the wheel {d2:.3f}° (half, the other way)")
    check(abs(s1["p"] - s0["p"]) < 1e-6 and abs(s1["rack"] - s0["rack"]) < 1e-6, "the pulley and the rack not coupled yet: still")

    # ⛓ a belt: wheel -> pulley (Ø60 -> Ø30), the same way, twice as fast
    rows = pick(("I3", rim("I3")), ("I4", rim("I4")))
    check(bool(rows) and rows[0] == "⛓ Belt / chain · i = 1:2", f"two rims apart: ⛓ Belt / chain · i = 1:2 first ({rows[:3]})")
    print("  snap_faces belt:", S(type="belt", move={"part": "I3", "face": rim("I3")}, onto={"part": "I4", "face": rim("I4")}))
    s0 = snapshot()
    call("move_free", part="I2", motion=0, amount=30)
    s1 = snapshot()
    d1, d2, dp = (wrap(s1[k] - s0[k]) for k in ("g1", "g2", "p"))
    check(abs(d2 + d1 / 2) < 0.01 and abs(dp - 2 * d2) < 0.01, f"belt: the wheel {d2:.3f}°, the pulley {dp:.3f}° (the same way, twice)")
    js("document.querySelector('#asmViewport .view-suggest')?.remove()")

    # ▤ the pinion's rim + the rack's side: the rack and pinion first, π·Ø per turn
    rows = pick(("I2", rim("I2")), ("I5", front))
    print("  suggested:", rows[:4])
    check(bool(rows) and rows[0] == "▤ Rack and pinion · 94.248 mm per turn", f"rim + the rack's flat side: ▤ Rack and pinion first ({rows[:2]})")
    d.find_elements(By.CSS_SELECTOR, "#asmViewport .view-suggest .vs-list button")[0].click()
    time.sleep(0.5)
    c = couplings()
    check(len(c) == 3 and c[2]["type"] == "rack" and abs(c[2]["ratio"] - math.pi * 30) < 1e-4, f"G3 rack: {c[2] if len(c) > 2 else c}")
    s0 = snapshot()
    call("move_free", part="I2", motion=0, amount=90)
    s1 = snapshot()
    d1, dy = wrap(s1["g1"] - s0["g1"]), s1["rack"] - s0["rack"]
    check(abs(abs(dy) - math.pi * 30 / 4) < 0.01 and abs(dy + math.radians(d1) * 15) < 0.01, f"the rack moved {dy:.4f} mm for {d1:.2f}° (π·30/4 = {math.pi * 30 / 4:.4f}; the rim's way)")
    s0 = snapshot()
    call("move_free", part="I2", motion=0, amount=180)
    call("move_free", part="I2", motion=0, amount=180)
    s1 = snapshot()
    check(abs(abs(s1["rack"] - s0["rack"]) - math.pi * 30) < 0.01 and abs(abs(wrap(s1["g2"] - s0["g2"])) - 180) < 0.01,
          f"a whole turn: the rack {s1['rack'] - s0['rack']:.3f} mm (π·Ø = {math.pi * 30:.3f}), the wheel half a turn")
    call("move_free", part="I5", motion=0, amount=-(s1["rack"] - s0["rack"]))  # (the rack back: the pinion turns back)
    s2 = snapshot()
    check(abs(s2["rack"] - s0["rack"]) < 0.01 and abs(wrap(s2["g1"] - s0["g1"])) < 0.05, f"the rack driven back: the pinion back too ({wrap(s2['g1'] - s0['g1']):.3f}°)")

    # one ⚙ Mechanism for the whole train: its slider, ▶, ⚠ the travel
    m = mech()
    check(len(m) == 1 and sorted(m[0]["parts"]) == ["I2", "I3", "I4", "I5"], f"one mechanism, the whole train: {[(x['name'], x['parts']) for x in m]}")
    w = [e for e in d.find_elements(By.CSS_SELECTOR, W) if e.is_displayed()]
    check(len(w) == 1 and len(w[0].find_elements(By.CSS_SELECTOR, ".mc-row")) == 1, "⚙ Mechanism shows it as one row")
    call("set_travel", part="I2", motion=0, min=-120, max=120)
    call("drive_mechanism", driver="I2 motion 0", to=0)
    s0 = snapshot()
    r = call("drive_mechanism", to=60)
    s1 = snapshot()
    d1, d2, dp, dy = wrap(s1["g1"] - s0["g1"]), wrap(s1["g2"] - s0["g2"]), wrap(s1["p"] - s0["p"]), s1["rack"] - s0["rack"]
    check(abs(abs(d1) - 60) < 0.05 and abs(d2 + d1 / 2) < 0.01 and abs(dp - 2 * d2) < 0.01 and abs(dy + math.radians(d1) * 15) < 0.01,
          f"drive_mechanism to 60: pinion {d1:.2f}°, wheel {d2:.2f}°, pulley {dp:.2f}°, rack {dy:.3f} mm")
    js("document.querySelector('[data-mcplay=\"0\"]').click()")
    worst, seen, n = 0, set(), 0
    end = time.time() + 2.5
    while time.time() < end:
        s = snapshot()
        g1 = s0["g1"] - math.degrees((s["rack"] - s0["rack"]) / 15)  # (the pinion's turn, unwrapped, from the rack)
        worst = max(worst, abs(wrap(s["g1"] - g1)), abs(wrap(s["g2"] - (s0["g2"] - (g1 - s0["g1"]) / 2))), abs(wrap(s["p"] - (s0["p"] - (g1 - s0["g1"])))))
        seen |= {k for k in s if abs(s[k] - s1[k]) > 1e-3}
        n += 1
        time.sleep(0.1)
    check(seen == {"g1", "g2", "p", "rack"} and worst < 0.05 and n > 5, f"▶ plays: all four move ({sorted(seen)}), the ratios off by {worst:.4f}° at most ({n} looks)")
    d.save_screenshot(f"{OUT}/gears_playing.png")
    js("document.querySelector('[data-mcplay=\"0\"]').click()")
    time.sleep(0.3)
    js("document.querySelector('[data-mcmore=\"0\"]').click()")
    time.sleep(0.2)
    js("document.querySelector('[data-mccheck=\"0\"]').click()")
    note = wait("const n = document.querySelector('.mc-row .as-dofnote'); return n && !/Checking/.test(n.textContent) && n.textContent", 120)
    print("  ⚠ travel:", note)
    check("Free" in note or "hits" in note, f"⚠ the travel checked: {note[:100]}")

    # the wheel dragged round in the view: the pinion turns twice as far, the other way
    call("drive_mechanism", to=0)
    js(f"{A}.choose('I3'); {A}.view.setView('top')")
    time.sleep(0.8)
    cv = js(f"return {A}.view.renderer.domElement")
    js(f"window.__THREE = {{ Vector3: {A}.view.camera.position.constructor }}")
    scr = lambda p: js(f"const r = arguments[0].getBoundingClientRect(), v = new window.__THREE.Vector3(...arguments[1]).project({A}.view.camera); return [(v.x + 1) / 2 * r.width - r.width / 2, (1 - v.y) / 2 * r.height - r.height / 2]", cv, p)  # noqa: E731
    o = js(f"return {A}.worldFace('I3', arguments[0]).axis.o.toArray()", rim("I3"))
    top = js(f"return {A}.worldFace('I3', 'F2:end').centroid.z")
    rr = 22
    s0 = snapshot()
    gx, gy = scr([o[0] + rr, o[1], top])
    act = ActionChains(d, duration=20).move_to_element_with_offset(cv, int(gx), int(gy)).click_and_hold()
    for k in range(1, 9):
        a_ = math.radians(5 * k)
        sx, sy = scr([o[0] + rr * math.cos(a_), o[1] + rr * math.sin(a_), top])
        act = act.move_to_element_with_offset(cv, int(sx), int(sy))
    act.release().perform()
    time.sleep(0.6)
    s1 = snapshot()
    d1, d2 = wrap(s1["g1"] - s0["g1"]), wrap(s1["g2"] - s0["g2"])
    check(abs(d2) > 20 and abs(d1 + 2 * d2) < 0.05, f"the wheel dragged {d2:.2f}° in the view: the pinion {d1:.2f}° (twice, the other way)")
    d.save_screenshot(f"{OUT}/gears_dragged.png")

    # the panel: the ratio typed, ⇄ the other way, ✕ -> undo
    js(f"{A}.choose('I2')")
    time.sleep(0.4)
    rows = d.find_elements(By.CSS_SELECTOR, "#asmRight [data-crow]")
    check(len(rows) == 2 and "Gear pair" in rows[0].text and "Rack and pinion" in rows[1].text, f"the pinion's panel: its couplings {[r.text.split(chr(10))[0] for r in rows]}")
    inp = d.find_element(By.CSS_SELECTOR, "#asmRight [data-cratio='G1']")
    js("arguments[0].value = '3'; arguments[0].dispatchEvent(new Event('change'))", inp)
    time.sleep(0.3)
    s0 = snapshot()
    call("move_free", part="I2", motion=0, amount=30)
    s1 = snapshot()
    d1, d2 = wrap(s1["g1"] - s0["g1"]), wrap(s1["g2"] - s0["g2"])
    check(abs(d2 + d1 / 3) < 0.01, f"the ratio typed 3: the wheel {d2:.3f}° for {d1:.3f}°")
    js("document.querySelector('#asmRight [data-cflip=\"G1\"]').click()")
    time.sleep(0.3)
    s0 = snapshot()
    call("move_free", part="I2", motion=0, amount=30)
    s1 = snapshot()
    d1, d2 = wrap(s1["g1"] - s0["g1"]), wrap(s1["g2"] - s0["g2"])
    check(abs(d2 - d1 / 3) < 0.01, f"⇄: the same way now ({d2:.3f}° for {d1:.3f}°)")
    js("document.querySelector('#asmRight [data-cdel=\"G3\"]').click()")
    time.sleep(0.3)
    check(len(couplings()) == 2, "✕ the rack's coupling removed")
    js(f"{A}.history.go(-1)")
    time.sleep(0.6)
    check(len(couplings()) == 3, "undo: it is back")
    for _ in range(4):  # (the two moves, ⇄ and the ratio)
        js(f"{A}.history.go(-1)")
        time.sleep(0.4)
    c = couplings()
    check(c and c[0]["ratio"] == 2 and c[0]["way"] == "opposite", f"undo: the ratio 2 and the way back ({c[:1]})")

    # the AI: a wrong pair refused; get_assembly; saved and opened again
    r = call("snap_faces", type="gear", move={"part": "I2", "face": rim("I2")}, onto={"part": "I5", "face": front})
    check(r.startswith("ERROR") and "round" in r, f"a gear on a flat face refused: {r[:90]}")
    r = call("snap_faces", type="rack", move={"part": "I2", "face": rim("I2")}, onto={"part": "I5", "face": "F2:end"})
    check(r.startswith("ERROR"), f"a rack on a face across the axis refused: {r[:90]}")
    proj = js("return window.__app.autosave.hooks.project()")
    js("return fetch('/api/project/migrate', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(arguments[0])}).then(r => r.json()).then(p => window.__app.project.loadAll(p))", proj)
    time.sleep(1)
    call("open_part", id="Gearbox")
    wait(f"return {A}.doc.instances.length === 5 && {A}.doc.instances.every(i => {A}.bodies[i.part]?.body) && {A}.mech.list.length")
    check(len(couplings()) == 3 and len(mech()) == 1, "saved and opened again: the couplings, one mechanism")
    s0 = snapshot()
    call("move_free", part="I3", motion=0, amount=-20)
    s1 = snapshot()
    check(abs(wrap(s1["g1"] - s0["g1"]) + 2 * wrap(s1["g2"] - s0["g2"])) < 0.01, "the wheel driven: the pinion follows (the other way round too)")

    # Czech
    d.find_element(By.ID, "langBtn").click()
    time.sleep(0.6)
    rows = pick(("I2", rim("I2")), ("I3", rim("I3")))
    check(bool(rows) and rows[0] == "⚙ Ozubení / převod · i = 2:1", f"Czech: {rows[:2]}")
    js(f"document.querySelector('#asmViewport .view-suggest')?.remove(); {A}.facePicks = []; {A}.choose('I2')")
    time.sleep(0.4)
    head = d.find_elements(By.CSS_SELECTOR, "#asmRight h3")
    txt = d.find_element(By.CSS_SELECTOR, "#asmRight").text
    check("Převody" in txt and "Převod" in txt and "Hřeben a pastorek" in txt and "mm na otáčku" in txt, f"Czech panel: {[h.text for h in head]}")
    d.save_screenshot(f"{OUT}/gears_cs.png")
    d.find_element(By.ID, "langBtn").click()
    time.sleep(0.4)
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE" and "favicon" not in e["message"] and "/api/ai/access" not in e["message"]]
    check(not errs, f"no errors in the console: {errs[:3]}")
finally:
    d.quit()
print("FAILED:" if bad else "ALL OK", len(bad), bad)
sys.exit(1 if bad else 0)
