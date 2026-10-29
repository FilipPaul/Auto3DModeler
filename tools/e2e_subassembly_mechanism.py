"""A sub-assembly's own mechanisms at work in the assembly it is placed in, in headless Edge (Czech; the owner: "with
assemblies inside each other I cannot move the mechanisms — a sub-assembly should be fully functional"):
the crank demo's assembly (renamed "Pohon") placed turned and shifted in "Stroj" on a fixed plate -> ⚙ Mechanism lists
"Klikový mechanismus (v Pohon)" -> its slider to 90°: the inner slider's pin at x = r·cosθ + √(L² − r²·sin²θ) in the
sub-assembly's frame, every joint held -> a flag of Stroj on the inner slider's pin follows it -> the inner crank
dragged round in the view (Pohon chosen, the crank grabbed) -> ▶ plays it -> ⚠ the travel checked -> the moves kept on
the placement (`inner`), Pohon's own document unchanged -> the AI: get_assembly / gui_state list it (`inside`),
drive_mechanism {mechanism: "I2"} and move_free "I2/I2" -> a loop through both levels: a second rod of Stroj on the
inner crank's pin and a slider of Stroj on its plate — driving the inner crank moves them, by the formula -> 🧱 rigid
(⚙ Pohyblivá podsestava off in its panel): no inner mechanism, move_free "I2/I2" refused, the drag does not move it;
on again: it works -> the gearbox demo with a rack as a sub-assembly: its train (couplings) driven in the parent, the
wheel at −½ the pinion's turn, the rack π·Ø per turn.

  PYTHONIOENCODING=utf-8 py tools/e2e_subassembly_mechanism.py http://127.0.0.1:5199 <out dir>
"""
import json
import math
import sys
import time
import urllib.request

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.add_argument("--lang=cs-CZ")
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


def load_demo(f):
    with urllib.request.urlopen(f"{URL}/api/demos/{f}") as r:
        p = json.loads(r.read())
    js("return fetch('/api/project/migrate', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(arguments[0])}).then(r => r.json()).then(p => window.__app.project.loadAll(p))", p)
    time.sleep(2)


def local(sub, p):
    """A world point in the frame of placement `sub` (its matrix: column-major, a turn and a shift)."""
    m = js(f"return {A}.inst(arguments[0]).matrix", sub)
    q = [p[0] - m[12], p[1] - m[13], p[2] - m[14]]
    return [m[0] * q[0] + m[1] * q[1] + m[2] * q[2], m[4] * q[0] + m[5] * q[1] + m[6] * q[2], m[8] * q[0] + m[9] * q[1] + m[10] * q[2]]


def axis(i, face):
    return js(f"return {A}.worldFace(arguments[0], arguments[1]).axis.o.toArray()", i, face)


def state(sub="I2", slider=None):
    """The inner crank's angle θ (degrees, its pin about the shaft) and the inner slider's pin x from the shaft — in the
    sub-assembly's frame; slider: another slider's pin (part id, face) measured the same way."""
    faces = [[sub, "I1/F4:side:c1"], [sub, "I2/F5:side:c1"], list(slider) if slider else [sub, "I4/F4:side:c1"]]
    pts = js(f"return arguments[0].map(([i, n]) => {A}.worldFace(i, n).axis.o.toArray())", faces)  # (at once: ▶ moves them between two calls)
    (sx, sy, _), (px, py, _), (qx, _, _) = [local(sub, p) for p in pts]
    return math.degrees(math.atan2(py - sy, px - sx)), qx - sx


def expected(theta):
    t = math.radians(theta)
    return R * math.cos(t) + math.sqrt(L * L - (R * math.sin(t)) ** 2)


def miss():
    return js(f"{A}.checkJoints(); return {A}.doc.mates.filter(m => {A}.whyNot(m)).map(m => m.id)")


def at_formula(what, slider=None):
    th, x = state(slider=slider)
    e = expected(th)
    check(abs(x - e) < 0.05 and not miss(), f"{what}: θ {th:.1f}°, slider {x:.3f} mm, the formula {e:.3f} (joints not held: {miss()})")
    return th, x


def widget():
    els = [e for e in d.find_elements(By.CSS_SELECTOR, W) if e.is_displayed()]
    return els[0] if els else None


def mech_names():
    return js(f"return {A}.mech.list.map(m => m.name)")


def sub_doc(name):
    return next(p for p in js("return window.__app.project.toJSON()")["parts"] if p.get("name") == name)["assembly"]


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('auto3d-lang')")
    load_demo("klikovy-mechanismus.a3d.json")
    wait(f"return {A}.doc.instances.length === 4 && {A}.doc.instances.every(i => {A}.bodyOf(i)?.body)")
    pin_d = js(f"return 2 * {A}.worldFace('I4', 'F4:side:c1').radius")
    call("rename_part", id="Klikový mechanismus", name="Pohon")
    own0 = json.dumps(sub_doc("Pohon")["instances"])

    call("new_model", name="Deska")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 400, "h": 300}}])
    call("add_feature", type="extrude", sketch="F1", d=8)
    call("new_model", name="Prapor")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 20, "y": 0, "w": 60, "h": 16}}])
    call("add_feature", type="extrude", sketch="F1", d=4)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=pin_d)

    call("new_assembly", name="Stroj")
    call("insert_part", part="Deska")
    call("insert_part", part="Pohon")
    call("insert_part", part="Prapor")
    wait(f"return {A}.doc.instances.length === 3 && {A}.doc.instances.every(i => {A}.bodyOf(i)?.body)")
    call("place_part", part="I1", fixed=True)
    call("place_part", part="I2", x=40, y=-30, z=8, turn="z")
    call("place_part", part="I2", fixed=True)
    m2 = js(f"return {A}.inst('I2').matrix")
    check(abs(m2[0]) < 1e-6 and abs(abs(m2[1]) - 1) < 1e-6, f"Pohon placed turned 90° about Z and shifted ({[round(v, 2) for v in m2[12:15]]})")
    r = call("snap_faces", type="axis", move={"part": "I3", "face": "F3:hole:0"}, onto={"part": "I2", "face": "I4/F4:side:c1"})
    check(not r.startswith("ERROR"), f"the flag of Stroj on the inner slider's pin: {r[:80]}")
    time.sleep(1)

    # ⚙ Mechanism lists the sub-assembly's own one
    js(f"{A}.mech.open()")
    time.sleep(0.5)
    names = mech_names()
    check("Klikový mechanismus (v Pohon)" in names, f"⚙ Mechanism lists the inner mechanism by its name, in Pohon: {names}")
    w = widget()
    check(w is not None and "Klikový mechanismus (v Pohon)" in w.text, "the widget shows it")
    k = names.index("Klikový mechanismus (v Pohon)")
    ga = json.loads(call("get_assembly"))
    gm = next((m for m in ga.get("mechanisms", []) if m.get("inside") == "I2"), None)
    check(gm and gm["driver"]["part"] == "I2/I2" and sorted(gm["parts"]) == ["I2/I2", "I2/I3", "I2/I4"], f"get_assembly mechanisms: {gm}")
    gs = json.loads(js(f"return {H}.gui_state({{}}).then(r => r.text)"))
    check(any(m.get("inside") == "I2" for m in gs.get("mechanisms", [])), f"gui_state mechanisms: {gs.get('mechanisms')}")

    # its slider to 90°: the inner slider at the formula, in Pohon's frame
    js(f"""const s = document.querySelectorAll('[data-mcv="{k}"]')[0]; s.value = 90; s.dispatchEvent(new Event('input')); s.dispatchEvent(new Event('change'))""")
    time.sleep(1)
    th, x = at_formula("the widget's slider at 90°")
    check(abs(abs(th) - 90) < 1.0, f"the inner crank at 90° ({th:.1f}; the sign: which way its pin's axis points)")
    flag_off = math.dist(axis("I3", "F3:hole:0")[:2], axis("I2", "I4/F4:side:c1")[:2])
    check(flag_off < 0.01, f"the flag (Stroj's) on the inner slider's pin followed it (off by {flag_off:.4f} mm)")
    check(js(f"return !!{A}.inst('I2').inner?.I4") and json.dumps(sub_doc("Pohon")["instances"]) == own0, "kept on the placement (inner), Pohon's own document unchanged")
    saved = next(p for p in js("return window.__app.project.toJSON()")["parts"] if p.get("name") == "Stroj")["assembly"]["instances"]
    check(any(i.get("inner") for i in saved), "the project file keeps the inner places")
    d.save_screenshot(f"{OUT}/submech_90.png")

    # undo: back where it was
    js(f"{A}.history.go(-1)")
    time.sleep(1.5)
    th_u, _ = at_formula("undo")
    check(abs(th_u - 90) > 5, f"undo: the crank went back ({th_u:.1f}°)")
    js(f"{A}.history.go(1)")
    time.sleep(1.5)

    # the inner crank dragged in the view (Pohon chosen, its crank grabbed)
    call("drive_mechanism", mechanism="I2", to=0)
    js(f"{A}.choose('I2'); {A}.view.setView('top')")
    time.sleep(0.8)
    cv = js(f"return {A}.view.renderer.domElement")
    js(f"window.__THREE = {{ Vector3: {A}.view.camera.position.constructor }}")
    scr = lambda p: js(f"const r = arguments[0].getBoundingClientRect(), v = new window.__THREE.Vector3(...arguments[1]).project({A}.view.camera); return [(v.x + 1) / 2 * r.width - r.width / 2, (1 - v.y) / 2 * r.height - r.height / 2]", cv, p)  # noqa: E731
    o, pin = axis("I2", "I1/F4:side:c1"), axis("I2", "I2/F5:side:c1")
    top = js(f"const f = {A}.worldFace('I2', 'I2/F2:end'); return f.centroid.z") - 0.05
    grab = [(o[0] + pin[0]) / 2, (o[1] + pin[1]) / 2, top]
    rr = math.hypot(grab[0] - o[0], grab[1] - o[1])
    a0 = math.atan2(grab[1] - o[1], grab[0] - o[0])
    th0, x0 = state()
    gx, gy = scr(grab)
    hit = js(f"const r = arguments[0].getBoundingClientRect(), h = {A}.view.ray(r.left + r.width / 2 + arguments[1], r.top + r.height / 2 + arguments[2]).intersectObjects({A}.view.meshes, false)[0]; const q = h && {A}.innerPartAt(h.object.userData.inst, h); return q ? q.id : (h ? 'hit ' + h.object.userData.inst : null)", cv, gx, gy)
    check(hit == "I2/I2", f"the mouse is on the inner crank ({hit})")
    act = ActionChains(d, duration=20).move_to_element_with_offset(cv, int(gx), int(gy)).click_and_hold()
    for s in range(1, 13):
        a_ = a0 + math.radians(7.5 * s)
        sx, sy = scr([o[0] + rr * math.cos(a_), o[1] + rr * math.sin(a_), top])
        act = act.move_to_element_with_offset(cv, int(sx), int(sy))
    act.release().perform()
    time.sleep(0.8)
    th1, x1 = state()
    print(f"  dragged: θ {th0:.1f}° -> {th1:.1f}°, slider {x0:.2f} -> {x1:.2f}")
    check(abs(th1 - th0) > 45 and abs(x1 - x0) > 1, f"the inner crank dragged ~90° in the view: θ {th0:.1f}° -> {th1:.1f}°, the slider {x0:.2f} -> {x1:.2f} mm")
    at_formula("after the drag")
    check(math.dist(axis("I3", "F3:hole:0")[:2], axis("I2", "I4/F4:side:c1")[:2]) < 0.01, "the flag followed the drag")
    d.save_screenshot(f"{OUT}/submech_dragged.png")

    # ▶ plays it
    names = mech_names()
    k = names.index("Klikový mechanismus (v Pohon)")
    js(f"{A}.mech.open('I2')")
    time.sleep(0.3)
    p0 = state()[0]
    js(f"document.querySelector('[data-mcplay=\"{k}\"]').click()")
    time.sleep(1.2)
    p1 = state()[0]
    check(js(f"return {A}.mech.playing?.key") is not None and abs(((p1 - p0 + 180) % 360) - 180) > 20, f"▶ plays: θ {p0:.1f}° -> {p1:.1f}°")
    js(f"{A}.mech.stop()")
    time.sleep(0.5)
    at_formula("stopped after ▶")

    # ⚠ the travel checked (a full turn, the kernel's sweep)
    r = js(f"const m = {A}.mech.list.find(x => x.inside === 'I2'); return {A}.mech.check(m).then(r => JSON.stringify(r)).catch(e => 'ERROR ' + e.message)")
    note = js(f"return {A}.mech.notes[{A}.mech.list.find(x => x.inside === 'I2').key]?.text")
    check(r and not r.startswith("ERROR") and note, f"⚠ the travel checked: {r[:120]} — {note}")
    at_formula("after the travel check (back where it was)")

    # the AI: drive_mechanism by the sub-assembly's id, move_free a part inside it
    r = call("drive_mechanism", mechanism="I2", to=150)
    th, _ = at_formula(f"drive_mechanism {{mechanism: I2, to: 150}} ({r[:50]})")
    check(abs(abs(th) - 150) < 1.0, f"at 150° ({th:.1f})")
    r = call("move_free", part="I2/I2", motion=0, to=45)
    th, _ = at_formula(f"move_free I2/I2 to 45 ({r[:40]})")
    check(not r.startswith("ERROR") and abs(abs(th) - 45) < 1.0, f"move_free: the crank at 45° ({th:.1f})")
    check(json.dumps(sub_doc("Pohon")["instances"]) == own0, "Pohon's own document still unchanged")

    def inner_mech():
        return next(m for m in json.loads(call("get_assembly"))["mechanisms"] if m.get("inside") == "I2")

    call("drive_mechanism", mechanism="I2", driver="I2/I4 motion 0")
    gm = inner_mech()
    check(gm["driver"]["part"] == "I2/I4" and gm["name"] == "Klikový mechanismus (v Pohon)", f"driven by the inner slider now, its name kept: {gm['name']} — {gm['driver']}")
    call("drive_mechanism", mechanism="I2", driver="I2/I2 motion 0", name="Klika Pohonu")
    gm = inner_mech()
    check(gm["driver"]["part"] == "I2/I2" and gm["name"] == "Klika Pohonu", f"the crank drives again, named here: {gm['name']}")
    check(sub_doc("Pohon")["mechs"][0]["name"] == "Klikový mechanismus" and any(r.get("name") == "Klika Pohonu" for r in sub_doc("Stroj").get("mechs", [])),
          "the name is Stroj's (its mechs), Pohon's own stays")

    # a loop through both levels: a rod of Stroj on the inner crank's pin, a slider of Stroj on its plate
    call("insert_part", part="Ojnice")
    call("insert_part", part="Smýkadlo")
    wait(f"return {A}.doc.instances.length === 5 && {A}.doc.instances.every(i => {A}.bodyOf(i)?.body)")
    hole = lambda i, k: js(f"return {A}.bodyOf({A}.inst(arguments[0])).body.faces.filter(f => /:hole:/.test(f.name)).map(f => f.name).sort()[arguments[1]]", i, k)  # noqa: E731
    S = lambda **a: call("snap_faces", **a)  # noqa: E731
    # Stroj's slider where the inner one is (on Pohon's base, in its line), then its joints as the demo's
    sm = js(f"return {A}.inst('I2').inner?.I4 || {A}.hooks.partData({A}.inst('I2').part).instances.find(x => x.id === 'I4').matrix")
    js(f"window.__THREE.Matrix4 = {A}.view.camera.matrix.constructor")
    js(f"""const M4 = window.__THREE.Matrix4, it = {A}.inst('I5'); it.matrix = new M4().fromArray({A}.inst('I2').matrix).multiply(new M4().fromArray(arguments[0])).toArray(); {A}.applyMates(); {A}.commit()""", sm)
    time.sleep(0.5)
    S(type="touch", move={"part": "I5", "face": "F2:start"}, onto={"part": "I2", "face": "I1/F2:end"})
    S(type="flush", move={"part": "I5", "face": "F2:side:l1"}, onto={"part": "I2", "face": "I1/F2:side:l1"}, gap=-15)
    S(type="axis", move={"part": "I4", "face": hole("I4", 0)}, onto={"part": "I2", "face": "I2/F5:side:c1"})
    S(type="touch", move={"part": "I4", "face": "F2:start"}, onto={"part": "I2", "face": "I2/F2:end"})
    r = S(type="axis", move={"part": "I4", "face": hole("I4", 1)}, onto={"part": "I5", "face": "F4:side:c1"})
    time.sleep(1)
    print("  joints not held after closing the loop:", miss())
    lm = next((m for m in js(f"return {A}.mech.list.map(m => ({{name: m.name, parts: m.parts, inside: m.inside || null}}))") if "I2/I2" in m["parts"]), None)
    check(lm and "I4" in lm["parts"] and "I5" in lm["parts"], f"one mechanism through both levels: {lm}")
    r = call("drive_mechanism", mechanism="I2/I2", to=90)
    at_formula(f"the loop through both levels driven to 90° — the inner slider ({r[:40]})")
    at_formula("— and the slider of Stroj on its rod", slider=("I5", "F4:side:c1"))
    r = call("drive_mechanism", mechanism="I2/I2", to=210)
    at_formula("at 210° — the slider of Stroj", slider=("I5", "F4:side:c1"))
    d.save_screenshot(f"{OUT}/submech_twolevels.png")

    # 🧱 rigid: no inner motion; ⚙ Moving sub-assembly in its panel
    js(f"{A}.choose('I2')")
    time.sleep(0.5)
    box = d.find_element(By.CSS_SELECTOR, "#asmRight [data-a=flexsub]")
    check(box.is_selected() and "Pohyblivá podsestava" in d.find_element(By.CSS_SELECTOR, "#asmRight .as-flexsub").text, "its panel: ⚙ Pohyblivá podsestava, on")
    th_r, x_r = state()
    box.click()
    time.sleep(1)
    check(js(f"return {A}.inst('I2').rigid === true"), "off: Pohon is rigid")
    check(not any("I2/" in str(p) for m in js(f"return {A}.mech.list.map(m => m.parts)") for p in m), f"rigid: no inner mechanism ({mech_names()})")
    r = call("move_free", part="I2/I2", motion=0, to=0)
    check(r.startswith("ERROR") and "rigid" in r, f"move_free inside a rigid one refused: {r[:80]}")
    gx, gy = scr(js(f"return {A}.worldFace('I2', 'I2/F2:end').centroid.toArray()"))
    ActionChains(d, duration=20).move_to_element_with_offset(cv, int(gx), int(gy)).click_and_hold().move_by_offset(40, 30).move_by_offset(30, 40).release().perform()
    time.sleep(0.5)
    th_d, _ = state()
    check(abs(th_d - th_r) < 0.01, f"rigid: a drag on its crank does not turn it ({th_r:.2f}° -> {th_d:.2f}°)")
    js(f"{A}.choose('I2')")
    time.sleep(0.8)
    sg = [e for e in d.find_elements(By.CSS_SELECTOR, ".vs-list [data-sg]") if e.is_displayed() and "Pohyblivá podsestava" in e.text]
    check(len(sg) == 1, f"the suggestions offer ⚙ Pohyblivá podsestava ({[e.text for e in d.find_elements(By.CSS_SELECTOR, '.vs-list [data-sg]')][:8]})")
    if sg:
        sg[0].click()
    else:
        d.find_element(By.CSS_SELECTOR, "#asmRight [data-a=flexsub]").click()
    time.sleep(1)
    check(not js(f"return !!{A}.inst('I2').rigid") and js(f"return {A}.mech.list.some(m => m.parts.includes('I2/I2'))"), f"on again: its mechanism is back ({mech_names()})")
    r = call("drive_mechanism", mechanism="I2/I2", to=300)
    at_formula("moving again, driven to 300°")
    r = call("place_part", part="I2", rigid=True)
    check(js(f"return {A}.inst('I2').rigid === true"), "place_part {rigid: true}")
    call("place_part", part="I2", rigid=False)

    # the gearbox with a rack as a sub-assembly: its couplings work in the parent
    load_demo("prevodovka-s-hrebenem.a3d.json")
    wait(f"return {A}.doc.instances.length === 4 && {A}.doc.instances.every(i => {A}.bodyOf(i)?.body)")
    call("new_model", name="Deska")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 400, "h": 300}}])
    call("add_feature", type="extrude", sketch="F1", d=8)
    call("new_assembly", name="Linka")
    call("insert_part", part="Deska")
    call("insert_part", part="Převodovka s hřebenem")
    wait(f"return {A}.doc.instances.length === 2 && {A}.doc.instances.every(i => {A}.bodyOf(i)?.body)")
    call("place_part", part="I1", fixed=True)
    call("place_part", part="I2", x=-50, y=20, z=8, turn="z")
    call("place_part", part="I2", fixed=True)
    time.sleep(0.5)
    js(f"{A}.mech.render()")
    gm = next((m for m in json.loads(call("get_assembly")).get("mechanisms", []) if m.get("inside") == "I2"), None)
    check(gm and sorted(gm["parts"]) == ["I2/I2", "I2/I3", "I2/I4"] and "Převodovka s hřebenem (v Převodovka s hřebenem)" == gm["name"], f"the gearbox's train in the parent: {gm}")

    def spin(f):
        """A part's turn about Z inside the sub-assembly (its matrix there; degrees)."""
        m = js(f"const it = {A}.inst('I2'); return it.inner?.[arguments[0]] || {A}.hooks.partData(it.part).instances.find(x => x.id === arguments[0]).matrix", f)
        return math.degrees(math.atan2(m[1], m[0])), m[12], m[13]

    w0, (_, rx0, ry0) = spin("I3")[0], spin("I4")
    call("drive_mechanism", mechanism="I2", to=0)
    w0, (_, rx0, ry0) = spin("I3")[0], spin("I4")
    r = call("drive_mechanism", mechanism="I2", to=60)
    p1, w1, (_, rx1, ry1) = spin("I2")[0], spin("I3")[0], spin("I4")
    dw = ((w1 - w0 + 180) % 360) - 180
    dr = math.hypot(rx1 - rx0, ry1 - ry0)
    check(abs(abs(p1) - 60) < 0.6 and abs(dw + p1 / 2) < 0.1, f"the pinion 60° ({p1:.2f}): the wheel turned {dw:.2f}° (−½ of it)")
    check(abs(dr - 94.24778 * 60 / 360) < 0.05, f"the rack moved {dr:.3f} mm (π·Ø per turn: {94.24778 * 60 / 360:.3f})")
    sub_gb = json.dumps(sub_doc("Převodovka s hřebenem")["instances"])
    check(js(f"return !!{A}.inst('I2').inner") and json.loads(sub_gb)[1]["matrix"] != js(f"return {A}.inst('I2').inner.I2"), "the gearbox's moves kept on the placement only")
    d.save_screenshot(f"{OUT}/submech_gearbox.png")
finally:
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        bad.append(f"console errors: {errs[:3]}")
    d.quit()
print("FAILED:" if bad else "ALL OK", bad if bad else "")
sys.exit(1 if bad else 0)
