"""🔗 A part fixed onto a part inside a sub-assembly turns with it, in headless Edge (Czech; the AI's report 2026-10-30
"rigid joint onto a part inside a sub-assembly follows only its translation"): the crank demo ("Pohon") placed turned
and shifted in "Stroj" on a fixed plate, a flag of Stroj 🔗 fixed onto the inner crank's end face -> the inner
mechanism driven 10° (and 25° more): the crank turns that much about its shaft and the flag with it — every point of the
flag turned by the same angle about the shaft's axis, the joint held -> back to the start: the flag where it was ->
an older file's joint (rot / pos measured against the sub-assembly's directions, no `fr`) opens with the flag where it
was, measured again against the crank (fr: 2), and follows the crank too.

  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_rigid_inner.py http://127.0.0.1:5199 <out dir>
"""
import json
import math
import sys
import time
import urllib.request

from selenium import webdriver

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
    js("return window.__app.project.loadAll(arguments[0])", p)
    time.sleep(2)


def corners(i):
    """The flag's bounding box corners in the world (its matrix)."""
    return js(f"""const it = {A}.inst(arguments[0]), b = {A}.bodyOf(it).body.bbox, m = it.matrix, out = [];
      for (const x of [b[0], b[3]]) for (const y of [b[1], b[4]]) for (const z of [b[2], b[5]])
        out.push([0, 1, 2].map((k) => m[k] * x + m[4 + k] * y + m[8 + k] * z + m[12 + k]));
      return out;""", i)


def turned(p, o, a, deg):
    """Point p turned deg° about the line (o, a) (a: a unit direction)."""
    t = math.radians(deg)
    v = [p[k] - o[k] for k in range(3)]
    dot = sum(v[k] * a[k] for k in range(3))
    cr = [a[1] * v[2] - a[2] * v[1], a[2] * v[0] - a[0] * v[2], a[0] * v[1] - a[1] * v[0]]
    return [o[k] + v[k] * math.cos(t) + cr[k] * math.sin(t) + a[k] * dot * (1 - math.cos(t)) for k in range(3)]


def crank_deg():
    """The inner crank's turn about its shaft (degrees, about the shaft's axis direction) — its pin seen from the shaft."""
    o, a = shaft()
    pin = js(f"return {A}.worldFace('I2', 'I2/F5:side:c1').axis.o.toArray()")
    ref = js(f"const f = {A}.worldFace('I2', 'I1/F4:side:c1'); return f.xdir.toArray()")
    v = [pin[k] - o[k] for k in range(3)]
    dv = sum(v[k] * a[k] for k in range(3))
    v = [v[k] - a[k] * dv for k in range(3)]
    dr = sum(ref[k] * a[k] for k in range(3))
    r = [ref[k] - a[k] * dr for k in range(3)]
    cr = [r[1] * v[2] - r[2] * v[1], r[2] * v[0] - r[0] * v[2], r[0] * v[1] - r[1] * v[0]]
    return math.degrees(math.atan2(sum(cr[k] * a[k] for k in range(3)), sum(r[k] * v[k] for k in range(3))))


def shaft():
    f = js(f"const f = {A}.worldFace('I2', 'I1/F4:side:c1').axis; return [f.o.toArray(), f.d.toArray()]")
    return f[0], f[1]


def follows(what, c0, deg):
    o, a = shaft()
    want = [turned(p, o, a, deg) for p in c0]
    off = max(math.dist(p, q) for p, q in zip(want, corners("I3")))
    held = js(f"{A}.checkJoints(); return {A}.doc.mates.filter(m => {A}.whyNot(m)).map(m => m.id)")
    check(off < 0.01 and not held, f"{what}: the flag turned {deg:.2f}° about the shaft with the crank (its corners off by {off:.4f} mm; joints not held: {held})")


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('auto3d-lang')")
    load_demo("klikovy-mechanismus.a3d")
    wait(f"return {A}.doc.instances.length === 4 && {A}.doc.instances.every(i => {A}.bodyOf(i)?.body)")
    call("rename_part", id="Klikový mechanismus", name="Pohon")
    call("new_model", name="Deska")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 400, "h": 300}}])
    call("add_feature", type="extrude", sketch="F1", d=8)
    call("new_model", name="Prapor")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 80, "h": 16}}])
    call("add_feature", type="extrude", sketch="F1", d=4)
    call("new_assembly", name="Stroj")
    call("insert_part", part="Deska")
    call("insert_part", part="Pohon")
    call("insert_part", part="Prapor")
    wait(f"return {A}.doc.instances.length === 3 && {A}.doc.instances.every(i => {A}.bodyOf(i)?.body)")
    call("place_part", part="I1", fixed=True)
    call("place_part", part="I2", x=40, y=-30, z=8, turn="z")
    call("place_part", part="I2", fixed=True)
    call("drive_mechanism", mechanism="I2", to=30)  # (the crank turned in it: its own place is not the sub-assembly's)
    top = js(f"return {A}.worldFace('I2', 'I2/F2:end').centroid.toArray()")
    call("place_part", part="I3", x=top[0] + 10, y=top[1] + 15, z=top[2] + 2)
    r = call("snap_faces", type="rigid", move={"part": "I3"}, onto={"part": "I2", "face": "I2/F2:end"})
    check(r.startswith("J"), f"the flag 🔗 fixed onto the inner crank's end face: {r[:70]}")
    time.sleep(0.5)

    th0, c0 = crank_deg(), corners("I3")
    r = call("drive_mechanism", mechanism="I2", to=40)
    th1 = crank_deg()
    dth = ((th1 - th0 + 180) % 360) - 180
    check(abs(abs(dth) - 10) < 0.5, f"the inner mechanism driven 10°: the crank turned {dth:.2f}° about its shaft ({r[:50]})")
    follows("driven 10°", c0, dth)
    call("drive_mechanism", mechanism="I2", to=65)
    th2 = crank_deg()
    follows("25° more", c0, ((th2 - th0 + 180) % 360) - 180)
    d.save_screenshot(f"{OUT}/rigid_inner_65.png")
    call("drive_mechanism", mechanism="I2", to=30)
    off = max(math.dist(p, q) for p, q in zip(c0, corners("I3")))
    check(off < 0.01, f"back to the start: the flag where it was ({off:.4f} mm)")

    # an older file's joint: its rot / pos against the sub-assembly's directions, no fr -> measured again, nothing moves
    js(f"""return Promise.all([import('/js/assembly/joints.js')]).then(([J]) => {{
      const a = {A}, m = a.doc.mates.find((x) => x.type === 'rigid');
      Object.assign(m, J.frameNow(a.worldFace(m.move, m.face, null, true), a.worldFace(m.onto, m.ontoFace, null, true)));
      delete m.fr; window.__old = JSON.stringify(m); }})""")
    m_old = json.loads(js("return window.__old"))
    js(f"{A}.applyMates()")
    m_new = js(f"return {A}.doc.mates.find((x) => x.type === 'rigid')")
    off = max(math.dist(p, q) for p, q in zip(c0, corners("I3")))
    check(off < 0.01 and m_new.get("fr") == 2 and m_new["rot"] != m_old["rot"], f"an older file's joint: the flag stays ({off:.4f} mm), measured against the crank now (fr {m_new.get('fr')}, rot {m_old['rot']} -> {m_new['rot']})")
    call("drive_mechanism", mechanism="I2", to=40)
    follows("the older file's joint, driven 10°", c0, ((crank_deg() - th0 + 180) % 360) - 180)
finally:
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        bad.append(f"console errors: {errs[:3]}")
    d.quit()
print("FAILED:" if bad else "ALL OK", bad if bad else "")
sys.exit(1 if bad else 0)
