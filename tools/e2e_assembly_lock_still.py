"""🔒 Locking a motion moves nothing, at the value it shows, and one undo takes it back, in headless Edge (Czech; the
AI's report 2026-10-30 "lock_motion of a concentric slide moves the part and turns a sub-assembly's inner motion"):
the crank demo ("Pohon") placed in "Stroj" on a fixed plate, its crank turned 30° there; a flag of Stroj ◎ concentric
on the inner crank's pin (it slides along it and turns), slid 3 mm and turned -> lock_motion of its slide: the toast /
answer says the value get_assembly showed, the slide is gone from its free ways, no part moved (every placement, the
places inside Pohon too) -> the 🔒 of its turn in the panel: the same -> undo twice: both locks gone, every part
where it was -> redo: the locks back, still nothing moved.

  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_lock_still.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time
import urllib.request

from selenium import webdriver
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


def places():
    """Every placement's matrix and its places inside (inner), rounded."""
    out = js(f"return {A}.doc.instances.map(i => [i.id, i.matrix, i.inner || null])")
    return json.loads(json.dumps(out), parse_float=lambda v: round(float(v), 5))


def same(a, b):
    return [x[0] for x, y in zip(a, b) if x != y]


def flag():
    return next(p for p in json.loads(call("get_assembly"))["parts"] if p["id"] == "I3")


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('auto3d-lang')")
    load_demo("klikovy-mechanismus.a3d")
    wait(f"return {A}.doc.instances.length === 4 && {A}.doc.instances.every(i => {A}.bodyOf(i)?.body)")
    pin_d = js(f"return 2 * {A}.worldFace('I4', 'F4:side:c1').radius")
    call("rename_part", id="Klikový mechanismus", name="Pohon")
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
    call("drive_mechanism", mechanism="I2", to=30)
    r = call("snap_faces", type="axis", move={"part": "I3", "face": "F3:hole:0"}, onto={"part": "I2", "face": "I2/F5:side:c1"})
    check(not r.startswith("ERROR"), f"the flag ◎ on the inner crank's pin: {r[:60]}")
    f0 = flag()
    names = f0.get("free", [])
    check(len(names) == 2, f"the flag slides and turns: {names}")
    call("move_free", part="I3", motion=0, to=3)
    call("move_free", part="I3", motion=1, to=-40)
    f1 = flag()
    slide = next(a for a in f1["at"] if "mm" in a)
    print("  before the lock:", f1["at"])
    p0, m0 = places(), js(f"return JSON.stringify({A}.doc.mates)")
    steps0 = js(f"return {A}.history.undo.length")

    # the AI: lock_motion of its slide
    r = call("lock_motion", part="I3", motion=0)
    want = f"{slide['mm']:g}".replace(".", ",")
    check(not r.startswith("ERROR") and f" {want} mm" in r, f"lock_motion of the slide says where it is ({slide['mm']} mm): {r[:90]}")
    f2 = flag()
    check(len(f2.get("free", [])) == 1 and "mm" not in json.dumps(f2.get("at")), f"the slide is gone from its free ways: {f2.get('free')}")
    moved = same(p0, places())
    check(not moved, f"no part moved by the lock (the places inside Pohon too): {moved}")

    # the 🔒 of its turn in the panel
    turn = next(a for a in f2["at"] if "deg" in a)
    js(f"{A}.choose('I3')")
    time.sleep(0.6)
    rows = [x for x in d.find_elements(By.CSS_SELECTOR, "#asmRight .as-dof") if x.find_elements(By.CSS_SELECTOR, "[data-dlock]")]
    check(len(rows) == 1, f"the panel: one motion with 🔒 left ({len(rows)})")
    toasts0 = len(d.find_elements(By.CSS_SELECTOR, ".toast"))
    rows[0].find_element(By.CSS_SELECTOR, "[data-dlock]").click()
    time.sleep(0.8)
    tx = " ".join(e.text for e in d.find_elements(By.CSS_SELECTOR, ".toast"))
    want = f"{turn['deg']:g}".replace(".", ",")
    check(f"{want}°" in tx, f"🔒 of the turn: the toast says where it is ({turn['deg']}°): {tx[:120]} ({toasts0} toasts before)")
    check(not flag().get("free"), "fully held now")
    moved = same(p0, places())
    check(not moved, f"no part moved by the 🔒 either: {moved}")
    check(js(f"return {A}.history.undo.length") == steps0 + 2, "two undo steps: one for each lock")

    # undo: the locks gone, every part where it was
    js(f"return {A}.history.go(-1)")
    time.sleep(1)
    js(f"return {A}.history.go(-1)")
    time.sleep(1.5)
    check(js(f"return JSON.stringify({A}.doc.mates)") == m0, "undo twice: both locks gone, the joints as before")
    moved = same(p0, places())
    check(not moved, f"undo twice: every part where it was: {moved}")
    check(len(flag().get("free", [])) == 2, "it slides and turns again")
    js(f"return {A}.history.go(1)")
    time.sleep(1)
    js(f"return {A}.history.go(1)")
    time.sleep(1.5)
    check(not flag().get("free") and not same(p0, places()), "redo: locked again, still nothing moved")
    d.save_screenshot(f"{OUT}/lock_still.png")
finally:
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        bad.append(f"console errors: {errs[:3]}")
    d.quit()
print("FAILED:" if bad else "ALL OK", bad if bad else "")
sys.exit(1 if bad else 0)
