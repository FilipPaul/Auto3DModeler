"""↔ Vzdálenost os (axis_distance): two round faces kept with their axes parallel, a distance apart — the report's two
INGUN GKS-100 probes 20 mm apart, in headless Edge in Czech, with REAL mouse and keyboard input:
- the solver alone (joints.js imported in the page): two round faces askew -> one pass: parallel, 20.000 apart; its
  swing kept at 30°; an axis along a flat face (either part's) 7.5 from it; the loop solve's numbers all 0;
- two GKS-100 probes from the library, the second 20 mm beside the first and tilted 3° -> a click on its barrel,
  Ctrl+click on the first one's -> "↔ Vzdálenost os 20 mm" in the top rows, next to ◎ Soustředně -> clicked: the axes
  parallel and 20.000 apart, a word on ▭ Zarovnat for the same height;
- free: a turn about its own axis and a slide along it (its swing round the other one kept); ▭ Zarovnat on the bottoms:
  the same height, only the turn left;
- the panel: the field 25 -> 25.000, the slider (→ key) 25.5, the field 25 again;
- the ↔ Mezera tool clicked on a round face becomes ↔ Vzdálenost os (the report: "Klikněte na rovnou plochu");
- saved, reloaded: the joint and its 25 mm kept;
- the AI: snap_faces type axis_distance distance 20, get_assembly reports it, edit_joint distance 30, flat faces refused;
- a loop: a third probe on the first one (↔ 20) and on a plate (▭) the first one sits in — the plate slid 10 mm, the
  first probe turned 40° in its hole: every joint holds, still 20 apart;
- no console errors.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_axis_distance.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

URL, OUT = sys.argv[1], sys.argv[2]
bad = []


def check(ok, what):
    print(("  ok  " if ok else "  FAIL") + " " + what)
    if not ok:
        bad.append(what)


opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.add_argument("--lang=cs-CZ")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
H = "window.__app.agentHandlers"
A = "window.__app.assembly"
BARREL = "F2:side:l2"  # (a GKS-100's barrel, Ø1.37)
BOTTOM = "F2:side:l1"  # (its flat bottom, facing down)


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


def apart(b, a, fb=BARREL, fa=BARREL):
    """The two round faces' axes: [the distance between them (mm), the angle between them (degrees)]."""
    return js(f"""const s = {A}, f = s.worldFace(arguments[0], arguments[2]), g = s.worldFace(arguments[1], arguments[3]);
      const dA = g.axis.d.clone().normalize(), v = f.axis.o.clone().sub(g.axis.o), ang = f.axis.d.angleTo(dA) * 180 / Math.PI;
      return [+v.sub(dA.clone().multiplyScalar(v.dot(dA))).length().toFixed(4), +Math.min(ang, 180 - ang).toFixed(4)];""", b, a, fb, fa)


def at(inst, face, t=None):
    """A point on a round face's surface facing the camera, on the screen from the canvas' middle (px): along it at t
    (0 … 1), else the first of a few places along it where the canvas itself is under the mouse and shows that face."""
    return js(f"""const s = {A}, v = s.view, f = s.worldFace(arguments[0], arguments[1]), d = f.axis.d.clone().normalize(), cv = v.renderer.domElement;
      const sp = f.span || [0, 0], r = cv.getBoundingClientRect(), mx = Math.floor(r.left + r.width / 2), my = Math.floor(r.top + r.height / 2);
      const px = (t) => {{
        const c = f.axis.o.clone().addScaledVector(d, sp[0] + (sp[1] - sp[0]) * t), out = v.camera.position.clone().sub(c).projectOnPlane(d).normalize();
        const [sx, sy] = v.toScreen(c.addScaledVector(out, f.radius * 0.9));
        return [Math.round(sx - mx), Math.round(sy - my)];
      }};
      if (arguments[2] !== null) return px(arguments[2]);
      for (const t of [0.5, 0.3, 0.7, 0.2, 0.8, 0.4, 0.6]) {{
        const [x, y] = px(t), h = v.pickInst(mx + x, my + y);
        if (document.elementFromPoint(mx + x, my + y) === cv && h?.inst === arguments[0] && h.face?.name === arguments[1]) return [x, y];
      }}
      return px(0.5);""", inst, face, t)


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#asmViewport canvas")


def click(inst, face, ctrl=False, t=None):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *at(inst, face, t)).perform()
    time.sleep(0.3)
    ch = ActionChains(d)
    (ch.key_down(Keys.CONTROL).click().key_up(Keys.CONTROL) if ctrl else ch.click()).perform()
    time.sleep(0.6)


def picks():
    return js(f"return ({A}.facePicks || []).map(q => [q.inst, q.face.name])")


def rows():
    return [" ".join(b.text.split()) for b in d.find_elements(By.CSS_SELECTOR, "#asmViewport .view-suggest .vs-list button:not(.vs-more)")]


def joint(jid):
    return next((j for j in json.loads(call("get_assembly"))["joints"] if j["id"] == jid), None)


def type_into(el, text):
    el.click()
    el.send_keys(Keys.CONTROL, "a")
    el.send_keys(text, Keys.ENTER)
    time.sleep(0.6)


try:
    d.get(URL)
    wait("return !!window.__app")
    js("window.confirm = () => true")

    # 0. the solver alone (joints.js): one pass from askew; the swing kept; an axis along a flat face; the loop's numbers
    unit = d.execute_async_script("""const done = arguments[arguments.length - 1];
      Promise.all([import('three'), import('/js/assembly/joints.js')]).then(([THREE, J]) => {
        const V = (...a) => new THREE.Vector3(...a);
        const faceAt = (f) => (M) => {
          const nm = new THREE.Matrix3().getNormalMatrix(M), P = (p) => p.clone().applyMatrix4(M), D = (v) => v.clone().applyMatrix3(nm).normalize();
          return { ...f, centroid: P(f.centroid), xdir: D(f.xdir), ydir: D(f.ydir), ...(f.normal ? { normal: D(f.normal) } : {}), ...(f.axis ? { axis: { o: P(f.axis.o), d: D(f.axis.d) } } : {}) };
        };
        const pin = { type: 'cylinder', radius: 0.7, span: [0, 30], axis: { o: V(0, 0, 0), d: V(0, 0, 1) }, centroid: V(0, 0, 15), xdir: V(1, 0, 0), ydir: V(0, 1, 0) };
        const flat = { type: 'plane', normal: V(0, 1, 0), centroid: V(0, 0, 0), xdir: V(1, 0, 0), ydir: V(0, 1, 0) };
        const A = faceAt(pin)(new THREE.Matrix4()), Aflat = faceAt(flat)(new THREE.Matrix4().makeTranslation(0, 3, 0));
        const askew = () => new THREE.Matrix4().makeTranslation(13, 4, 2).multiply(new THREE.Matrix4().makeRotationX(0.09)).multiply(new THREE.Matrix4().makeRotationY(-0.05));
        const r3 = (v) => +(+v).toFixed(4), out = {};
        const run = (k, j, fB, fA) => {
          const M = J.applyJoint(askew(), j, faceAt(fB), fA, true, null).M, b = faceAt(fB)(M), m = J.jointMiss(j, b, fA);
          out[k] = { ok: m.ok, mm: r3(m.mm), deg: r3(m.deg), now: r3(J.axisDistanceNow(b, fA)), res: r3(Math.max(...J.jointResidual(j, b, fA).map(Math.abs))) };
          return b;
        };
        run('two axes 20', { type: 'axis_distance', dist: 20 }, pin, A);
        const b = run('swing kept 30°', { type: 'axis_distance', dist: 20, angle: 30 }, pin, A);
        out['swing kept 30°'].orbit = r3(J.orbitOf(b, A));
        run('axis along a flat face 7.5', { type: 'axis_distance', dist: 7.5, side: 1 }, pin, Aflat);
        run('a flat face along an axis 7.5', { type: 'axis_distance', dist: 7.5, side: -1 }, flat, A);
        const far = faceAt(pin)(askew()), j = { type: 'axis_distance', dist: 20 }; // (not placed: the loop's numbers are not 0)
        out['askew, not placed'] = { ok: J.jointMiss(j, far, A).ok, res: r3(Math.max(...J.jointResidual(j, far, A).map(Math.abs))) };
        done(out);
      }).catch((e) => done('ERROR ' + e.message));""")
    print("solver:", unit)
    placed = {k: v for k, v in unit.items() if k != "askew, not placed"} if isinstance(unit, dict) else {}
    check(bool(placed) and all(v["ok"] and v["res"] < 1e-6 for v in placed.values()), "solver: each holds after one pass, the loop solve's numbers all 0")
    check(placed.get("two axes 20", {}).get("now") == 20 and placed["two axes 20"]["deg"] < 1e-4, "solver: two axes askew -> parallel, 20.000 apart")
    check(placed.get("swing kept 30°", {}).get("orbit") == 30, "solver: its swing kept at 30° round the other axis")
    check(placed.get("axis along a flat face 7.5", {}).get("now") == 7.5 and placed.get("a flat face along an axis 7.5", {}).get("now") == -7.5, "solver: an axis 7.5 from a flat face (either part's)")
    check(isinstance(unit, dict) and not unit["askew, not placed"]["ok"] and unit["askew, not placed"]["res"] > 0.1, "solver: askew and not placed — it does not hold")

    # 1. two GKS-100 probes from the library: the second 20 mm beside the first, tilted 3°
    call("new_assembly", name="Jehly")
    for _ in range(2):
        call("library_add", item="ingun-gks100-214", to="assembly")
    wait(f"return {A}.doc.instances.length === 2 && Object.values({A}.bodies).every(b => b.body)")
    call("place_part", part="I1", fixed=True)
    call("place_part", part="I2", x=20, y=0, z=0)
    js(f"""const s = {A}, it = s.inst('I2'), o = s.worldFace('I2', '{BARREL}').axis.o, M = s.view.camera.matrix.constructor;
      const T = (p, k = 1) => new M().makeTranslation(k * p.x, k * p.y, k * p.z);
      it.matrix = T(o).multiply(new M().makeRotationY(3 * Math.PI / 180)).multiply(T(o, -1)).multiply(new M().fromArray(it.matrix)).toArray();
      s.applyMates(); s.draw()""")
    js(f"{A}.facePicks = []; {A}.choose(null); {A}.view.setView('front')")
    time.sleep(0.8)
    a0 = apart("I2", "I1")
    print("before:", a0)

    # 2. a click on its barrel, Ctrl+click on the first one's -> ↔ Vzdálenost os 20 mm, next to ◎ Soustředně
    click("I2", BARREL)
    click("I1", BARREL, ctrl=True)
    p = picks()
    print("picked:", p)
    check(p == [["I2", BARREL], ["I1", BARREL]], "both barrels picked (a click, then Ctrl+click)")
    rs = rows()
    print("the table:", rs)
    ax = [i for i, x in enumerate(rs) if x.startswith("↔") and "Vzdálenost os" in x]
    check(bool(ax) and ax[0] < 3 and any(x.startswith("◎") and "Soustředně" in x for x in rs[:3]), f"↔ Vzdálenost os in the top 3 rows, next to ◎ Soustředně: {rs[:3]}")
    check(bool(ax) and "20 mm" in rs[ax[0]], f"…with the distance they have now: {rs[ax[0]] if ax else None}")
    js(f"{A}.hooks.toast = ((f) => (text, ...rest) => {{ (window.__toasts = window.__toasts || []).push(text); return f(text, ...rest); }})({A}.hooks.toast)")
    next(b for b in d.find_elements(By.CSS_SELECTOR, "#asmViewport .view-suggest .vs-list button") if "Vzdálenost os" in b.text).click()
    time.sleep(0.8)
    said = js("return (window.__toasts || []).join(' | ')")
    print("toasts:", said)
    a1 = apart("I2", "I1")
    jid = js(f"return {A}.doc.mates.find(m => m.type === 'axis_distance')?.id")
    j1 = joint(jid) if jid else None
    print("joint:", j1, "axes:", a1)
    check(j1 is not None and j1["part"] == "I2" and j1["distance"] == 20 and not j1.get("not_held"), "↔ joint made: I2 onto I1, 20 mm, it holds")
    check(a1[0] == 20 and a1[1] < 0.001, f"the axes parallel and 20.000 apart: {a0} -> {a1}")
    check("Zarovnat" in said, "the toast tells how to get the same height (▭ Zarovnat on their ends)")
    d.save_screenshot(f"{OUT}/axis_distance_made.png")

    # 3. free: a turn about its own axis and a slide along it; ▭ Zarovnat on the bottoms -> the same height
    free = next(p for p in json.loads(call("get_assembly"))["parts"] if p["id"] == "I2").get("free", [])
    ways = js(f"return {A}.motionsOf('I2').motions.map(m => [m.kind, m.detail])")
    print("free:", free, ways)
    check(len(ways) == 2 and any(k == "turn" and "vlastní osy" in w for k, w in ways) and any(k == "move" and "osy" in w for k, w in ways),
          f"free: a turn about its own axis and a slide along it (its swing round I1 kept): {ways}")
    r = call("snap_faces", type="flush", move={"part": "I2", "face": BOTTOM}, onto={"part": "I1", "face": BOTTOM})
    check(not r.startswith("ERROR"), f"▭ Zarovnat the bottoms ({r[:60]})")
    hz = js(f"const s = {A}; return [s.worldFace('I1', '{BOTTOM}').centroid.z, s.worldFace('I2', '{BOTTOM}').centroid.z].map(v => +v.toFixed(4))")
    free = next(p for p in json.loads(call("get_assembly"))["parts"] if p["id"] == "I2").get("free", [])
    check(hz[0] == hz[1] and apart("I2", "I1")[0] == 20, f"the same height ({hz}), still 20 apart")
    check(len(free) == 1, f"…only its turn about its own axis left: {free}")

    # 4. the panel: the field 25, the slider (→), the field again
    js(f"{A}.choose('I2')")
    time.sleep(0.6)
    fld = d.find_element(By.CSS_SELECTOR, f"#asmRight [data-jdist='{jid}']")
    type_into(fld, "25")
    a2 = apart("I2", "I1")
    check(a2[0] == 25 and a2[1] < 0.001, f"the field 25 -> {a2}")
    sl = d.find_element(By.CSS_SELECTOR, f"#asmRight [data-jgaps='{jid}']")
    sl.send_keys(Keys.ARROW_RIGHT)
    time.sleep(0.6)
    a3 = apart("I2", "I1")
    check(a3[0] == 25.5, f"the slider → -> {a3}")
    fld = d.find_element(By.CSS_SELECTOR, f"#asmRight [data-jdist='{jid}']")
    type_into(fld, "25")
    check(apart("I2", "I1")[0] == 25 and joint(jid)["distance"] == 25, f"the field 25 again: {apart('I2', 'I1')}")
    d.save_screenshot(f"{OUT}/axis_distance_25.png")

    # 5. the ↔ Mezera tool on a round face: it becomes ↔ Vzdálenost os
    call("library_add", item="ingun-gks100-214", to="assembly")
    wait(f"return {A}.doc.instances.length === 3 && Object.values({A}.bodies).every(b => b.body)")
    call("place_part", part="I3", x=-15, y=0, z=0)
    js(f"{A}.facePicks = []; {A}.choose(null); {A}.view.setView('front')")
    time.sleep(0.8)
    js(f"{A}.startJoint('gap')")
    click("I3", BARREL)
    check(js(f"return {A}.jointType") == "axis_distance" and js(f"return {A}.mode") == "joint-to", "↔ Mezera, a round face clicked: ↔ Vzdálenost os, now the other face")
    click("I1", BARREL)
    m3 = js(f"return {A}.doc.mates.filter(m => m.move === 'I3' && m.type === 'axis_distance').map(m => m.dist)")
    check(m3 == [15], f"…the other barrel clicked: ↔ 15 mm, as they stood ({m3})")
    call("remove_joint", id=js(f"return {A}.doc.mates.find(m => m.move === 'I3').id"))

    # 6. saved, reloaded: the joint and its 25 mm kept
    js("return window.__app.autosave.saveNow()")
    time.sleep(1)
    d.refresh()
    wait("return !!window.__app")
    wait("return document.querySelector('.restore-bar')", 15)
    d.find_element(By.CSS_SELECTOR, ".restore-bar [data-a=open]").click()
    time.sleep(2)
    call("open_part", id="Jehly")
    wait(f"return {A}.active && Object.values({A}.bodies).every(b => b.body)", 60)
    time.sleep(1)
    j2 = joint(jid)
    check(j2 is not None and j2["type"] == "axis_distance" and j2["distance"] == 25 and not j2.get("not_held") and apart("I2", "I1")[0] == 25, f"reloaded: {j2}, {apart('I2', 'I1')}")

    # 7. the AI: snap_faces axis_distance 20, get_assembly, edit_joint 30, flat faces refused
    r = call("snap_faces", type="axis_distance", distance=20, move={"part": "I3", "face": BARREL}, onto={"part": "I1", "face": BARREL})
    check(not r.startswith("ERROR"), f"snap_faces axis_distance 20 ({r[:80]})")
    jj = [j for j in json.loads(call("get_assembly"))["joints"] if j["part"] == "I3" and j["type"] == "axis_distance"]
    print("AI joint:", jj)
    check(len(jj) == 1 and jj[0]["distance"] == 20 and jj[0].get("rotation_locked") is True and apart("I3", "I1") == [20, 0], f"get_assembly reports it: {jj}, {apart('I3', 'I1')}")
    r = call("edit_joint", id=jj[0]["id"], distance=30)
    check('"distance":30' in r and apart("I3", "I1")[0] == 30, f"edit_joint distance 30 -> {apart('I3', 'I1')}")
    call("edit_joint", id=jj[0]["id"], distance=20)
    r = call("snap_faces", type="axis_distance", move={"part": "I3", "face": BOTTOM}, onto={"part": "I1", "face": BOTTOM})
    check(r.startswith("ERROR") and "round" in r, f"two flat faces refused, with why: {r[:120]}")

    # 8. a loop: the first probe in a plate's hole (the plate slides on a base), the third on the first (↔ 20) and on the plate (▭)
    call("new_model", name="Zakladna")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 120, "h": 60}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("new_model", name="Deska")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=3)
    call("add_feature", type="hole", face="F2:end", points=[[-10, 0]], d=2)
    time.sleep(1)
    call("open_part", id="Jehly")
    wait(f"return {A}.active", 30)
    call("place_part", part="I1", fixed=False)
    call("insert_part", part="Zakladna")
    call("insert_part", part="Deska")
    wait(f"return {A}.doc.instances.length === 5 && Object.values({A}.bodies).every(b => b.body)")
    call("place_part", part="I4", fixed=True)
    for args in [dict(type="touch", move={"part": "I5", "face": "F2:start"}, onto={"part": "I4", "face": "F2:end"}),
                 dict(type="axis", move={"part": "I1", "face": BARREL}, onto={"part": "I5", "face": "F3:hole:0"}),
                 dict(type="flush", move={"part": "I1", "face": BOTTOM}, onto={"part": "I5", "face": "F2:start"}),
                 dict(type="flush", move={"part": "I3", "face": BOTTOM}, onto={"part": "I5", "face": "F2:start"})]:
        r = call("snap_faces", **args)
        check(not r.startswith("ERROR"), f"{args['type']} {args['move']['part']} -> {args['onto']['part']} ({r[:60]})")
    s = json.loads(call("get_assembly"))
    print("loops:", s.get("loops"), [(j["id"], j["type"], j["part"], j["onto"], j.get("not_held")) for j in s["joints"]])
    check(all(not j.get("not_held") for j in s["joints"]), "every joint holds")
    plate = next(p for p in s["parts"] if p["id"] == "I5")
    mo = next((k for k, f in enumerate(plate.get("free", [])) if "X" in f), None)
    print("plate free:", plate.get("free"))
    x0 = js(f"return {A}.worldFace('I1', '{BARREL}').axis.o.x")
    r = call("move_free", part="I5", motion=mo if mo is not None else 0, amount=10)
    s = json.loads(call("get_assembly"))
    x1 = js(f"return {A}.worldFace('I1', '{BARREL}').axis.o.x")
    print("moved:", r[:80], x0, "->", x1, [(j["id"], j.get("not_held")) for j in s["joints"]])
    check(abs(x1 - x0) > 5, f"the plate slid: the first probe went along ({x0:.2f} -> {x1:.2f})")
    check(all(not j.get("not_held") for j in s["joints"]) and apart("I3", "I1") == [20, 0] and apart("I1", "I5", BARREL, "F3:hole:0")[0] < 0.001,
          f"the loop holds: the third probe still 20 from the first ({apart('I3', 'I1')}), the first in its hole")
    r = call("move_free", part="I1", motion=0, amount=40)  # (the first probe turned in its hole: the third one, kept round it, swings along)
    s = json.loads(call("get_assembly"))
    print("turned:", r[:80], [(j["id"], j.get("not_held")) for j in s["joints"]])
    check(all(not j.get("not_held") for j in s["joints"]) and apart("I3", "I1") == [20, 0], f"the first probe turned 40°: the loop still holds, 20 apart ({apart('I3', 'I1')})")
    d.save_screenshot(f"{OUT}/axis_distance_loop.png")
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        bad.append("console errors")
    d.quit()
print("FAILED:" if bad else "ALL OK", bad if bad else "")
sys.exit(1 if bad else 0)
