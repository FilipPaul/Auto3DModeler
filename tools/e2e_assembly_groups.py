"""🔗 Many parts fixed together as one rigid group, in headless Edge (Czech; the AI's request 2026-10-30 "group many
placed parts into one rigid body"): "Stroj" = a plate, the crank demo as the fixed sub-assembly "Pohon" (its rows
open) and five flags around its crank -> real clicks: the first flag, Shift+click the fifth, Ctrl+click the inner
crank's row -> the suggestion "🔗 Spojit pevně (6 dílů)" -> one group: nothing moved, one row in the joints panel
("Klika (6 dílů)", no rigid rows of its own), get_assembly `groups` {base I2, the five flags}, its joints left out of
`joints` -> the inner mechanism driven 10°: every flag turned 10° about the crank's shaft -> renamed by a double-click
("Brána") -> ✕ in its row: dissolved, the flags stay, a drive leaves them -> undo: the group back, it follows again
-> the AI: fix_together {all_except, to: "I2/I2", name} and remove_joint R… ; a wrong part refused.

  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_groups.py http://127.0.0.1:5199 <out dir>
"""
import json
import math
import sys
import time
import urllib.request

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

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
FLAGS = ["I3", "I4", "I5", "I6", "I7"]
bad = []


def check(ok, what):
    print(("  ok  " if ok else "  FAIL") + " " + what)
    if not ok:
        bad.append(what)


def wait(script, t=120):
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


def click(key, *keys):
    sel = f'[data-inst="{key}"]' if "/" not in key else f'[data-path="{key}"]'
    el = d.find_element(By.CSS_SELECTOR, f"#leftCol .as-list > {sel}")
    js("arguments[0].scrollIntoView({block: 'center'})", el)
    act = ActionChains(d)
    for k in keys:
        act = act.key_down(k)
    act = act.click(el.find_element(By.CSS_SELECTOR, ".mt-name"))
    for k in reversed(keys):
        act = act.key_up(k)
    act.perform()
    time.sleep(0.4)


def corners():
    """Every flag's bounding box corners in the world."""
    return js(f"""return arguments[0].map((id) => {{ const it = {A}.inst(id), b = {A}.bodyOf(it).body.bbox, m = it.matrix, out = [];
      for (const x of [b[0], b[3]]) for (const y of [b[1], b[4]]) for (const z of [b[2], b[5]])
        out.push([0, 1, 2].map((k) => m[k] * x + m[4 + k] * y + m[8 + k] * z + m[12 + k]));
      return out; }})""", FLAGS)


def shaft():
    f = js(f"const f = {A}.worldFace('I2', 'I1/F4:side:c1').axis; return [f.o.toArray(), f.d.toArray()]")
    return f[0], f[1]


def turned(p, o, a, deg):
    t = math.radians(deg)
    v = [p[k] - o[k] for k in range(3)]
    dot = sum(v[k] * a[k] for k in range(3))
    cr = [a[1] * v[2] - a[2] * v[1], a[2] * v[0] - a[0] * v[2], a[0] * v[1] - a[1] * v[0]]
    return [o[k] + v[k] * math.cos(t) + cr[k] * math.sin(t) + a[k] * dot * (1 - math.cos(t)) for k in range(3)]


def crank_deg():
    o, a = shaft()
    pin = js(f"return {A}.worldFace('I2', 'I2/F5:side:c1').axis.o.toArray()")
    ref = js(f"return {A}.worldFace('I2', 'I1/F4:side:c1').xdir.toArray()")
    v = [pin[k] - o[k] for k in range(3)]
    dv = sum(v[k] * a[k] for k in range(3))
    v = [v[k] - a[k] * dv for k in range(3)]
    dr = sum(ref[k] * a[k] for k in range(3))
    r = [ref[k] - a[k] * dr for k in range(3)]
    cr = [r[1] * v[2] - r[2] * v[1], r[2] * v[0] - r[0] * v[2], r[0] * v[1] - r[1] * v[0]]
    return math.degrees(math.atan2(sum(cr[k] * a[k] for k in range(3)), sum(r[k] * v[k] for k in range(3))))


def off(c0, c1):
    return max(math.dist(p, q) for a, b in zip(c0, c1) for p, q in zip(a, b))


def follows(what, c0, th0):
    dth = ((crank_deg() - th0 + 180) % 360) - 180
    o, a = shaft()
    want = [[turned(p, o, a, dth) for p in f] for f in c0]
    e = off(want, corners())
    check(abs(dth) > 5 and e < 0.01, f"{what}: the crank turned {dth:.2f}°, every flag with it about the shaft (corners off by {e:.4f} mm)")


def group_rows():
    return [e.text for e in d.find_elements(By.CSS_SELECTOR, "#asmRight [data-grow]")]


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('auto3d-lang'); localStorage.removeItem('a3d.asmTree')")
    load_demo("klikovy-mechanismus.a3d")
    wait(f"return {A}.doc.instances.length === 4 && {A}.doc.instances.every(i => {A}.bodyOf(i)?.body)")
    call("rename_part", id="Klikový mechanismus", name="Pohon")
    crank = js(f"return {A}.doc.instances.find(i => i.id === 'I2').part")
    call("new_model", name="Deska")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 400, "h": 300}}])
    call("add_feature", type="extrude", sketch="F1", d=8)
    call("new_model", name="Prapor")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 30, "h": 10}}])
    call("add_feature", type="extrude", sketch="F1", d=3)
    call("new_assembly", name="Stroj")
    for p in ("Deska", "Pohon", *["Prapor"] * 5):
        call("insert_part", part=p)
    wait(f"return {A}.doc.instances.length === 7 && {A}.doc.instances.every(i => {A}.bodyOf(i)?.body)")
    call("place_part", part="I1", fixed=True)
    call("place_part", part="I2", x=40, y=-30, z=8, turn="z")
    call("place_part", part="I2", fixed=True)
    call("drive_mechanism", mechanism="I2", to=30)
    top = js(f"return {A}.worldFace('I2', 'I2/F2:end').centroid.toArray()")
    for k, f in enumerate(FLAGS):
        call("place_part", part=f, x=top[0] - 20 + 12 * k, y=top[1] + 20 + 9 * k, z=top[2] + 2 + 4 * k)
    js(f"{A}.toggleOpen('I2')")
    time.sleep(0.5)
    c0, th0 = corners(), crank_deg()
    cname = js(f"return window.__app.project.toJSON().parts.find(p => p.name === 'Pohon').assembly.instances.find(i => i.id === 'I2').part")
    crank_name = js(f"return {A}.partName(arguments[0])", cname)

    # the GUI: the five flags (a click, Shift+click) and the inner crank (Ctrl+click) -> 🔗 Spojit pevně (6 dílů)
    click("I3")
    click("I7", Keys.SHIFT)
    click("I2/I2", Keys.CONTROL)
    check(js(f"return {A}.selKeys()") == [*FLAGS, "I2/I2"], f"chosen: {js(f'return {A}.selKeys()')}")
    sg = [e for e in d.find_elements(By.CSS_SELECTOR, ".vs-list [data-sg]") if e.is_displayed()]
    item = next((e for e in sg if "Spojit pevně" in e.text), None)
    check(item is not None and "Spojit pevně (6 dílů)" in item.text, f"the suggestion: {item.text if item else [e.text for e in sg]}")
    steps0 = js(f"return {A}.history.undo.length")
    item.click()
    time.sleep(1)
    check(off(c0, corners()) < 1e-6, f"made: nothing moved ({off(c0, corners()):.6f} mm)")
    check(js(f"return {A}.history.undo.length") == steps0 + 1, "one undo step")
    ga = json.loads(call("get_assembly"))
    g = (ga.get("groups") or [{}])[0]
    check(g.get("base") == "I2" and sorted(g.get("parts", [])) == FLAGS and g.get("name") == crank_name, f"get_assembly groups: {ga.get('groups')} (name: the crank's, {crank_name})")
    check(not any(j["part"] in FLAGS for j in ga["joints"]), f"its joints are not in `joints`: {[j['id'] for j in ga['joints']]}")
    js(f"{A}.select([])")
    time.sleep(0.4)
    d.execute_script("const f = document.querySelector('#asmRight details.as-jfold'); if (f) f.open = true;")
    rows = group_rows()
    check(len(rows) == 1 and f"{crank_name} (6 dílů)" in rows[0], f"one row in the joints panel: {rows}")
    check(not d.find_elements(By.CSS_SELECTOR, "#asmRight [data-jrow]") or all(
        "Prapor" not in e.text for e in d.find_elements(By.CSS_SELECTOR, "#asmRight [data-jrow]")), "no rigid rows of the flags' own")
    d.save_screenshot(f"{OUT}/groups_made.png")

    # the inner mechanism driven: the group goes along
    call("drive_mechanism", mechanism="I2", to=40)
    follows("driven 10°", c0, th0)
    call("drive_mechanism", mechanism="I2", to=75)
    follows("driven 45°", c0, th0)
    call("drive_mechanism", mechanism="I2", to=30)
    check(off(c0, corners()) < 0.01, "back at 30°: the flags where they were")

    # renamed by a double-click
    el = d.find_element(By.CSS_SELECTOR, "#asmRight [data-gname]")
    ActionChains(d).double_click(el).perform()
    time.sleep(0.3)
    ed = d.switch_to.active_element
    ed.send_keys(Keys.CONTROL, "a")
    ed.send_keys("Brána", Keys.ENTER)
    time.sleep(0.5)
    rows = group_rows()
    check(js(f"return {A}.doc.groups[0].name") == "Brána" and rows and "Brána (6 dílů)" in rows[0], f"renamed: {rows}")

    # ✕ dissolves it: the flags stay, a drive leaves them; undo: back
    d.find_element(By.CSS_SELECTOR, "#asmRight [data-gdel]").click()
    time.sleep(0.8)
    check(not js(f"return {A}.doc.groups") and not js(f"return {A}.doc.mates.some(m => arguments[0].includes(m.move))", FLAGS), "✕: the group and its joints gone")
    check(off(c0, corners()) < 1e-6, "the flags stay where they are")
    call("drive_mechanism", mechanism="I2", to=50)
    check(off(c0, corners()) < 1e-6, "driven: the flags stay (not fixed any more)")
    call("drive_mechanism", mechanism="I2", to=30)
    js(f"return {A}.history.go(-1)")
    time.sleep(1.5)
    js(f"return {A}.history.go(-1)")
    time.sleep(1.5)
    js(f"return {A}.history.go(-1)")
    time.sleep(1.5)
    check(js(f"return {A}.doc.groups?.[0]?.name") == "Brána", f"undo: the group back ({js(f'return {A}.doc.groups')})")
    call("drive_mechanism", mechanism="I2", to=40)
    follows("undone, driven 10°", c0, th0)
    call("drive_mechanism", mechanism="I2", to=30)

    # the AI: fix_together
    call("remove_joint", id="R1")
    r = call("fix_together", parts=["I3", "I99"])
    check(r.startswith("ERROR") and "I99" in r, f"a wrong part refused: {r[:80]}")
    r = call("fix_together", all_except=["I1"], to="I2/I2", name="Brána AI")
    g = (json.loads(call("get_assembly")).get("groups") or [{}])[0]
    check(not r.startswith("ERROR") and g.get("name") == "Brána AI" and g.get("base") == "I2" and sorted(g.get("parts", [])) == FLAGS,
          f"fix_together {{all_except: [I1], to: I2/I2}}: {r[:90]} | {g}")
    call("drive_mechanism", mechanism="I2", to=45)
    follows("the AI's group, driven 15°", c0, th0)
    r = call("remove_joint", id=g.get("id", "R1"))
    check("dissolved" in r and "groups" not in json.loads(call("get_assembly")), f"remove_joint {g.get('id')}: {r[:70]}")
finally:
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        bad.append(f"console errors: {errs[:3]}")
    d.quit()
print("FAILED:" if bad else "ALL OK", bad if bad else "")
sys.exit(1 if bad else 0)
