"""∥ Parallel on a part a ◎ concentric joint already holds (free turn), in headless Edge: a plate with a Ø8 hole on a
base plate's Ø8 hole, turned 2° about it -> ∥ its side face to the base's side face (facing away, as in the report:
178°; then facing the same way) -> the plate turns about the hole's axis only: both joints hold, the hole stays on the
axis -> ∥ its top face to the base's side face (no turn about the axis makes them parallel) is refused with a reason
and nothing moves; the same through the clicked-faces path (a warning toast).

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_parallel_axis.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time

from selenium import webdriver

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
A = "window.__app.assembly"
H = "window.__app.agentHandlers"
fails = []


def check(ok, what):
    print(("OK  " if ok else "FAIL") + " " + what)
    if not ok:
        fails.append(what)


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


def joints():
    return json.loads(call("get_assembly"))["joints"]


def axis_off():
    """How far the plate's hole axis is from the base's (mm) and the angle between them (degrees)."""
    return js(f"""const a = {A}, f = a.worldFace('I2', 'F3:hole:0'), g = a.worldFace('I1', 'F3:hole:0');
      const v = f.axis.o.clone().sub(g.axis.o), dA = g.axis.d.clone().normalize();
      return [+v.clone().sub(dA.clone().multiplyScalar(v.dot(dA))).length().toFixed(4), +(Math.min(f.axis.d.angleTo(dA), Math.PI - f.axis.d.angleTo(dA)) * 180 / Math.PI).toFixed(4)];""")


def angle(f2, f1):
    return js(f"const a = {A}; return +(a.worldFace('I2', arguments[0]).normal.angleTo(a.worldFace('I1', arguments[1]).normal) * 180 / Math.PI).toFixed(3)", f2, f1)


def sides(inst):
    """The plate's flat side faces by the way they face in the world: {'+x': name, '-x': …, '+y': …, '-y': …}."""
    return js(f"""const a = {A}, it = a.inst(arguments[0]), out = {{}};
      for (const f of a.bodies[it.part].body.faces.filter((f) => f.type === 'plane' && /:side:/.test(f.name))) {{
        const n = a.worldFace(arguments[0], f.name).normal;
        for (const [k, v] of [['+x', n.x], ['-x', -n.x], ['+y', n.y], ['-y', -n.y]]) if (v > 0.9) out[k] = f.name;
      }}
      return out;""", inst)


try:
    d.get(URL)
    wait("return !!window.__app")
    js("window.confirm = () => true")

    # the solver alone (joints.js), one pass: a pin's hole on an axis (free turn) + ∥ side faces 2° off — both hold
    unit = d.execute_async_script("""const done = arguments[arguments.length - 1];
      Promise.all([import('three'), import('/js/assembly/joints.js')]).then(([THREE, J]) => {
        const V = (...a) => new THREE.Vector3(...a);
        // the plate (local): its hole on z through (0, 0), Ø8, 4 thick; a side face facing -y, 8 from the hole's line
        const hole = { type: 'cylinder', radius: 4, span: [0, 4], axis: { o: V(0, 0, 0), d: V(0, 0, 1) }, centroid: V(0, 0, 2), xdir: V(1, 0, 0), ydir: V(0, 1, 0) };
        const side = { type: 'plane', normal: V(0, -1, 0), centroid: V(17, -8, 2), xdir: V(1, 0, 0), ydir: V(0, 0, 1) };
        const faceAt = (f) => (M) => {
          const nm = new THREE.Matrix3().getNormalMatrix(M), P = (p) => p.clone().applyMatrix4(M), D = (v) => v.clone().applyMatrix3(nm).normalize();
          return { ...f, centroid: P(f.centroid), xdir: D(f.xdir), ydir: D(f.ydir), ...(f.normal ? { normal: D(f.normal) } : {}), ...(f.axis ? { axis: { o: P(f.axis.o), d: D(f.axis.d) } } : {}) };
        };
        const baseHole = faceAt({ ...hole, span: [0, 5] })(new THREE.Matrix4()), baseSide = faceAt({ ...side, normal: V(0, 1, 0), centroid: V(0, 20, 2.5) })(new THREE.Matrix4());
        const out = {};
        for (const [k, deg, flip] of [['away 178°', 2, true], ['away 178°, no flip (a 178° turn)', 2, false], ['same way 3°', 183, false]]) {
          let M = new THREE.Matrix4().makeTranslation(3, 1, 0).multiply(new THREE.Matrix4().makeRotationZ(deg * Math.PI / 180));
          const j1 = { type: 'axis' }, j2 = { type: 'parallel', ...(flip ? { flip: true } : {}) };
          const r1 = J.applyJoint(M, j1, faceAt(hole), baseHole, true, null);
          M = J.applyJoint(r1.M, j2, faceAt(side), baseSide, false, r1.fixed).M;
          const m1 = J.jointMiss(j1, faceAt(hole)(M), baseHole), m2 = J.jointMiss(j2, faceAt(side)(M), baseSide);
          out[k] = [m1.ok, +m1.mm.toFixed(4), m2.ok, +m2.deg.toFixed(4)];
        }
        done(out);
      }).catch((e) => done('ERROR ' + e.message));""")
    print("solver, one pass [axis ok, mm, parallel ok, deg]:", unit)
    check(isinstance(unit, dict) and all(v[0] and v[2] for v in unit.values()), "solver: the axis and ∥ both hold after one pass, every way round")

    call("new_model", name="Base")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=8)
    call("new_model", name="Arm")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 50, "h": 16}}])
    call("add_feature", type="extrude", sketch="F1", d=4)
    call("add_feature", type="hole", face="F2:end", points=[[-17, 0]], d=8)
    time.sleep(1)
    call("new_assembly", name="Pivot")
    call("insert_part", part="Base")
    call("insert_part", part="Arm")
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    r = call("snap_faces", type="axis", move={"part": "I2", "face": "F3:hole:0"}, onto={"part": "I1", "face": "F3:hole:0"})
    check(not r.startswith("ERROR"), f"◎ the plate's hole on the base's hole ({r[:80]})")
    js(f"{A}.view.setView('iso')")
    j1 = joints()[0]
    print("axis joint:", j1["id"], j1["type"], "rotation locked:", j1.get("rotation_locked"))
    js(f"{A}.turnAbout({A}.doc.mates[0], 2)")  # (2° off the base's sides, about the hole)
    time.sleep(0.3)
    s1, s2 = sides("I1"), sides("I2")
    print("sides:", s1, s2)
    check(axis_off()[0] < 0.01, f"turned 2° about the axis: still on it {axis_off()}")

    # facing away (178°): ∥ turns it 2° about the axis — the joint way round as they stand
    a0 = angle(s2["-y"], s1["+y"])
    r = call("snap_faces", type="parallel", move={"part": "I2", "face": s2["-y"]}, onto={"part": "I1", "face": s1["+y"]})
    check(not r.startswith("ERROR"), f"∥ added ({r[:80]})")
    js_ = joints()
    print("joints:", [(j["id"], j["type"], j.get("not_held")) for j in js_])
    check(all(not j.get("not_held") for j in js_), "both joints hold (∥ facing away)")
    off = axis_off()
    check(off[0] < 0.01 and off[1] < 0.01, f"the hole stays on the axis: {off} (was 24.7 mm off in the report)")
    a1 = angle(s2["-y"], s1["+y"])
    check(abs(a1 - 180) < 0.05, f"the faces parallel, facing away: {a0}° -> {a1}°")
    check(js(f"return !!{A}.doc.mates[1].flip") is True, "∥ made the way round they stood (flip)")
    d.save_screenshot(f"{OUT}/parallel_axis1.png")

    # facing the same way: ✕ it, turn 3° back, ∥ again on the faces facing the same way
    js(f"{A}.doc.mates.pop(); {A}.applyMates()")
    js(f"{A}.turnAbout({A}.doc.mates[0], -3)")
    time.sleep(0.2)
    b0 = angle(s2["+y"], s1["+y"])
    r = call("snap_faces", type="parallel", move={"part": "I2", "face": s2["+y"]}, onto={"part": "I1", "face": s1["+y"]})
    js_ = joints()
    print("joints:", [(j["id"], j["type"], j.get("not_held")) for j in js_])
    check(len(js_) == 2 and all(not j.get("not_held") for j in js_), "both joints hold (∥ facing the same way)")
    check(angle(s2["+y"], s1["+y"]) < 0.05 and axis_off()[0] < 0.01, f"parallel, the same way: {b0}° -> {angle(s2['+y'], s1['+y'])}°, on the axis {axis_off()}")
    js(f"{A}.doc.mates.pop(); {A}.applyMates()")

    # cannot be parallel by a turn about the axis: refused, nothing moves
    m0 = js(f"return [...{A}.inst('I2').matrix]")
    r = call("snap_faces", type="parallel", move={"part": "I2", "face": "F2:end"}, onto={"part": "I1", "face": s1["+y"]})
    print("refused:", r[:220])
    check(r.startswith("ERROR") and "J1" in r, "∥ that no turn about the axis can make: refused, naming the axis joint")
    js_ = joints()
    check(len(js_) == 1 and not js_[0].get("not_held"), f"only the axis joint, still held: {[(j['id'], j.get('not_held')) for j in js_]}")
    m1 = js(f"return [...{A}.inst('I2').matrix]")
    check(max(abs(p - q) for p, q in zip(m0, m1)) < 1e-6, "the plate did not move")

    # the same through the clicked-faces path: a warning toast, no joint
    js(f"""const a = {A}; a.jointType = 'parallel'; a.mode = 'joint-to';
      a.jointFrom = {{inst: 'I2', face: a.worldFace('I2', 'F2:end')}};
      a.clickJoint({{inst: 'I1', face: a.worldFace('I1', arguments[0])}});""", s1["+y"])
    time.sleep(0.3)
    toast = js("return [...document.querySelectorAll('.toast')].map(e => e.textContent).join(' | ')")
    print("toast:", toast[:200])
    check("J1" in toast and len(joints()) == 1, "clicked faces: refused with a toast naming J1, no joint added")
    d.save_screenshot(f"{OUT}/parallel_axis2.png")
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    d.quit()
print("FAILED:" if fails else "ALL OK", fails if fails else "")
sys.exit(1 if fails else 0)
