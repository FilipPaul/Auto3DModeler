"""One joint = one constraint, in headless Edge (the owner, 2026-11-01): a collar on a shaft — ↔ Gap onto the base and
◎ Concentric on the shaft. ◎ has no distance and no turn of its own: its row offers +↕ (a distance along the axis) and
+↻ (a rotation) as joints of their own; the gap's row has its ↕ row only and offers +↻ (+◎ greyed: there is one).
+↕ on the gap-held collar is greyed (its other joint holds that slide already). A second collar held by ◎ only: +↕ -> a
joint of its own at the distance it has (nothing moves), its ↕ row moves the collar, +↕ greyed then ("kept by J…");
+↻ -> a rotation joint, its ↻ slider turns the collar; every ↕ / ↻ row ends with its 🔒 in one column; ✕ on ◎ takes
its ↕ / ↻ with it. The AI: snap_faces axis gap + lock_rotation
-> three joints, get_assembly distance / rotation_locked; edit_joint distance null -> the ↕ joint gone. Czech texts.

  PYTHONIOENCODING=utf-8 py tools/e2e_joint_rows.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time

from selenium import webdriver
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
fails = []


def call(t, **a):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", t, a)


def check(ok, what):
    print(("OK   " if ok else "FAIL ") + what)
    if not ok:
        fails.append(what)


def wait(cond, timeout=40):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if js(cond):
                return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


def pick(i):
    js(f"{A}.choose(arguments[0])", i)
    time.sleep(0.5)


def row(jid):
    return d.find_element(By.CSS_SELECTOR, f"#asmRight [data-jrow={jid}]")


def has(r, sel):
    return len(r.find_elements(By.CSS_SELECTOR, sel)) > 0


def add_btn(jid, kind):
    return row(jid).find_element(By.CSS_SELECTOR, f"[data-jadd][data-kind={kind}]")


def mates():
    return js(f"return JSON.parse(JSON.stringify({A}.doc.mates))")


def mate(jid):
    return next((m for m in mates() if m["id"] == jid), None)


def mats():
    return js(f"return Object.fromEntries({A}.doc.instances.map(i => [i.id, i.matrix]))")


def same(a, b, tol=1e-4):
    return all(max(abs(x - y) for x, y in zip(a[k], b[k])) < tol for k in a)


def z(i):
    return round(js(f"return {A}.inst(arguments[0]).matrix[14]", i), 3)


def turned(i):
    return round(js(f"const m = {A}.inst(arguments[0]).matrix; return Math.atan2(m[1], m[0]) * 180 / Math.PI", i), 2)


def lock_rights(r):
    return js("return [...arguments[0].querySelectorAll('.as-jspin .as-jdof')].map(b => Math.round(b.getBoundingClientRect().right))", r)


try:
    d.get(URL)
    js("localStorage.removeItem('auto3d-lang')")
    d.refresh()
    time.sleep(2)
    call("new_model", name="Base")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 60}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="sketch", plane={"face": "F2:end"}, shapes=[{"circle": {"x": 0, "y": 0, "d": 10}}])
    call("add_feature", type="extrude", sketch="F3", d=30)
    call("new_model", name="Collar")
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 22}}])
    call("add_feature", type="extrude", sketch="F1", d=7)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=10)
    call("new_assembly", name="Rows")
    for p in ("Base", "Collar", "Collar"):
        call("insert_part", part=p)
    time.sleep(1.5)
    S = lambda **a: call("snap_faces", **a)[:40]  # noqa: E731
    S(type="gap", gap=3, move={"part": "I2", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})
    S(type="axis", move={"part": "I2", "face": "F3:hole:0"}, onto={"part": "I1", "face": "F4:side:c1"})
    S(type="axis", move={"part": "I3", "face": "F3:hole:0"}, onto={"part": "I1", "face": "F4:side:c1"})
    ms = mates()
    print("joints:", [(m["id"], m["type"], m["move"]) for m in ms])
    check([m["type"] for m in ms] == ["gap", "axis", "axis"] and not any("dist" in m or "angle" in m for m in ms), "◎ made: no distance, no turn of its own")

    # 1. the first collar: ↔ Gap J1 + ◎ J2
    pick("I2")
    d.save_screenshot(f"{OUT}/rows_collar.png")
    r1, r2 = row("J1"), row("J2")
    print("J1:", r1.text.replace("\n", " | "), "\nJ2:", r2.text.replace("\n", " | "))
    check(has(r1, "[data-jgaps]") and not has(r1, "[data-jspin]"), "↔ Gap: its ↕ row, no ↻ row")
    check(not has(r2, "[data-jgaps]") and not has(r2, "[data-jspin]"), "◎ Concentric: no ↕ / ↻ row of its own")
    b = add_btn("J1", "spin")
    check(b.is_enabled(), f"↔ Gap offers +↻ ({b.get_attribute('title')})")
    b = add_btn("J1", "axis")
    check(not b.is_enabled() and "J2" in b.get_attribute("title"), f"…+◎ greyed: {b.get_attribute('title')}")
    b = add_btn("J2", "axial")
    check(not b.is_enabled(), f"◎ +↕ greyed — the gap holds that slide: {b.get_attribute('title')}")
    check(add_btn("J2", "spin").is_enabled(), "◎ +↻ offered")
    hdr = js("const r = arguments[0]; const y = (s) => r.querySelector(s).getBoundingClientRect().top; return Math.abs(y('.as-jt') - y('[data-jadd]')) < 12 && Math.abs(y('.as-jt') - y('[data-jlock]')) < 12", r2)
    check(hdr, "+↕ +↻ 🛡 ✕ on the joint's top line")

    # 2. the second collar: ◎ J3 only — +↕ at the distance it has, nothing moves
    pick("I3")
    m0 = mats()
    add_btn("J3", "axial").click()
    time.sleep(0.7)
    ms = mates()
    ax = next((m for m in ms if m["type"] == "axial"), None)
    check(ax is not None and ax["move"] == "I3" and same(m0, mats()), f"+↕ -> {ax and ax['id']} at {ax and ax.get('dist')} mm, nothing moved")
    check(not add_btn("J3", "axial").is_enabled() and ax["id"] in add_btn("J3", "axial").get_attribute("title"), f"…+↕ greyed then: {add_btn('J3', 'axial').get_attribute('title')}")
    check("as-jnew" in row(ax["id"]).get_attribute("class"), "…its new row lit")
    sl = row(ax["id"]).find_element(By.CSS_SELECTOR, "[data-jgaps]")
    z0 = z("I3")
    js("arguments[0].value = +arguments[0].value + 5; arguments[0].dispatchEvent(new Event('input')); arguments[0].dispatchEvent(new Event('change'))", sl)
    time.sleep(0.6)
    check(abs(z("I3") - z0) > 1, f"its ↕ slider moves the collar: z {z0} -> {z('I3')} (dist {mate(ax['id'])['dist']})")
    num = row(ax["id"]).find_element(By.CSS_SELECTOR, "[data-jgapn]")
    num.send_keys(Keys.CONTROL, "a")
    num.send_keys("12", Keys.ENTER)
    time.sleep(0.6)
    check(mate(ax["id"])["dist"] == 12, f"typed 12: dist {mate(ax['id'])['dist']}, z {z('I3')}")
    # +↻: a rotation joint, its slider turns the collar
    add_btn("J3", "spin").click()
    time.sleep(0.7)
    sp = next((m for m in mates() if m["type"] == "spin"), None)
    check(sp is not None and not add_btn("J3", "spin").is_enabled(), f"+↻ -> {sp and sp['id']} at {sp and sp.get('angle')}°, +↻ greyed then")
    a0 = turned("I3")
    num = row(sp["id"]).find_element(By.CSS_SELECTOR, "[data-jspinn]")
    num.send_keys(Keys.CONTROL, "a")
    num.send_keys("45", Keys.ENTER)
    time.sleep(0.6)
    check(abs(abs(turned("I3") - a0) - 45) < 1 or abs(mate(sp["id"])["angle"] - 45) < 1e-6 and abs(turned("I3") - a0) > 1, f"↻ 45: turned {a0} -> {turned('I3')}")
    pick("I3")
    xs = lock_rights(row(ax["id"])) + lock_rights(row(sp["id"]))
    check(len(xs) == 2 and max(xs) - min(xs) <= 1, f"the ↕ / ↻ locks in one column: {xs}")
    held = json.loads(call("get_assembly"))
    j3 = next(j for j in held["joints"] if j["id"] == "J3")
    check(j3.get("distance") == 12 and j3.get("rotation_locked") and j3.get("distance_joint") == ax["id"], f"get_assembly J3: {j3}")
    i3 = next(p for p in held["parts"] if p["id"] == "I3")
    check(i3.get("fully_held") or not i3.get("free"), f"I3 fully held: {i3.get('free')}")
    d.save_screenshot(f"{OUT}/rows_added.png")

    # 3. no duplicate: the AI asks for a second distance on J3 -> the same joint changed
    call("edit_joint", id="J3", distance=8)
    check(len([m for m in mates() if m["type"] == "axial"]) == 1 and mate(ax["id"])["dist"] == 8, "edit_joint distance 8: the same ↕ joint, no second")
    call("edit_joint", id="J3", distance=None)
    check(mate(ax["id"]) is None, "edit_joint distance null: the ↕ joint gone")

    # 4. ✕ on ◎: its ↻ goes with it
    pick("I3")
    row("J3").find_element(By.CSS_SELECTOR, "[data-jdel]").click()
    time.sleep(0.5)
    check(not any(m["move"] == "I3" for m in mates()), f"✕ ◎: its ↻ with it ({[m['id'] for m in mates()]})")

    # 5. the AI: ◎ with a distance and its turn kept -> three joints
    r = S(type="axis", gap=6, lock_rotation=True, move={"part": "I3", "face": "F3:hole:0"}, onto={"part": "I1", "face": "F4:side:c1"})
    mine = [(m["type"], m.get("dist"), m.get("angle")) for m in mates() if m["move"] == "I3"]
    check([x[0] for x in mine] == ["axis", "axial", "spin"] and mine[1][1] == 6, f"snap_faces axis gap 6 + lock_rotation: {mine}")

    # 5b. Czech: the rows' add buttons
    pick("I2")
    d.find_element(By.ID, "langBtn").click()
    time.sleep(0.6)
    pick("I2")
    tips = [b.get_attribute("title") for b in d.find_elements(By.CSS_SELECTOR, "#asmRight [data-jadd]")]
    print("cs:", row("J2").text.replace("\n", " | "), tips)
    check(tips and all(any(w in x for w in ("Přidat", "nejde", "drží")) for x in tips), "Czech: the +↕ +↻ +◎ tooltips")
    d.save_screenshot(f"{OUT}/rows_cs.png")
    d.find_element(By.ID, "langBtn").click()
    time.sleep(0.4)

finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
print("FAILED:" if fails else "all OK", fails)
sys.exit(1 if fails else 0)
