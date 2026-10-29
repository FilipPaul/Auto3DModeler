"""🎬 Demo projects, in headless Edge: Open ▾ → Demo projects… lists the demos (names and texts, in Czech too) -> each
one opened from the menu (as a new project; the demo file on the server unchanged) -> its assembly on screen with
⚙ Mechanism and Czech motion names -> ▶ plays: every moving part moves and every joint holds (the loop's worst miss
< 0.05 mm) -> the crank – rod – slider: the slider at r·cosθ + √(L² − r²·sin²θ); the four-bar: the rocker's pin where
the closed form puts it (one branch all the way); the robot arm: the forearm and the gripper go along with the arm ->
the crank (the arm) dragged in the 3D view: the others follow.

  PYTHONIOENCODING=utf-8 py tools/e2e_demos.py http://127.0.0.1:5199 <out dir>
"""
import hashlib
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
opts.add_argument("--lang=en-US")
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


def demo_bytes(f):
    with urllib.request.urlopen(f"{URL}/api/demos/{f}") as r:
        return hashlib.sha1(r.read()).hexdigest()


def worst():
    """The largest miss of all the assembly's joints (mm)."""
    return js(f"""return import('./js/assembly/loops.js').then(L => {{
      const a = {A}, P = new Map(a.doc.instances.map(i => [i.id, new window.__V.M4().fromArray(i.matrix)]));
      return L.worstMiss(a.doc.mates.filter(m => !a.insideMate(m)), P, (i, n, M) => a.worldFace(i, n, M)); }})""")


def ax(i, face):
    return js(f"const o = {A}.worldFace(arguments[0], arguments[1]).axis.o; return [o.x, o.y]", i, face)


def axes(*pairs):
    """Several round faces' axis points (x, y) at once (▶ moves the parts between two calls)."""
    return js(f"return arguments[0].map(([i, n]) => {{ const o = {A}.worldFace(i, n).axis.o; return [o.x, o.y]; }})", [list(p) for p in pairs])


def rounds(i, kind):
    return js(f"""const it = {A}.inst(arguments[0]), b = {A}.bodies[it.part].body;
      const names = [...new Set(b.faces.filter(f => f.type === 'cylinder' && f.name.includes(arguments[1])).map(f => f.name))];
      return names.map(n => [n, {A}.worldFace(arguments[0], n).axis.o.x]).sort((p, q) => p[1] - q[1]).map(p => p[0])""", i, ":" + kind)


def mats():
    return {i["id"]: i["matrix"] for i in js(f"return {A}.doc.instances.map(i => ({{id: i.id, matrix: [...i.matrix]}}))")}


def open_demo(k):
    d.find_element(By.ID, "openBtn").click()
    time.sleep(0.2)
    js("document.getElementById('demoBtn').click()")  # (the menu's item: under a toast or a splitter at times)
    wait("return document.querySelectorAll('.demos [data-demo]').length")
    rows = d.find_elements(By.CSS_SELECTOR, ".demos [data-demo]")
    f = rows[k].get_attribute("data-demo")
    rows[k].find_element(By.CSS_SELECTOR, "[data-open]").click()
    wait(f"return window.__app.state.workspace === 'assembly' && {A}.doc.instances.length > 1 && {A}.doc.instances.every(i => {A}.bodies[i.part]?.body) && {A}.mech.list.length")
    time.sleep(0.8)
    return f


def play(k=0, secs=2.5, look=None):
    """▶ on row k for a while: which parts moved, the joints' worst miss, look() each time."""
    m0 = mats()
    d.find_element(By.CSS_SELECTOR, f"[data-mcplay='{k}']").click()
    moved, w, n = set(), 0, 0
    end = time.time() + secs
    while time.time() < end:
        w = max(w, worst())
        if look:
            look()
        n += 1
        for i, m in mats().items():
            if any(abs(p - q) > 1e-3 for p, q in zip(m, m0[i])):
                moved.add(i)
        time.sleep(0.1)
    d.find_element(By.CSS_SELECTOR, f"[data-mcplay='{k}']").click()
    time.sleep(0.4)
    return moved, w, n


def drag_turn(inst, centre, deg=80):
    """The part dragged round `centre` (x, y) by `deg` in the top view, grabbed on its top half-way out."""
    js(f"{A}.choose(arguments[0]); {A}.view.setView('top')", inst)
    time.sleep(0.8)
    cv = js(f"return {A}.view.renderer.domElement")
    bb = js(f"const it = {A}.inst(arguments[0]), b = {A}.bodies[it.part].body, M = new window.__V.M4().fromArray(it.matrix), box = new window.__V.B3(new window.__V.V3(...b.bbox.slice(0, 3)), new window.__V.V3(...b.bbox.slice(3))).applyMatrix4(M); return [box.min.toArray(), box.max.toArray()]", inst)
    top = bb[1][2] - 0.2
    far = max(((x, y) for x in (bb[0][0], bb[1][0]) for y in (bb[0][1], bb[1][1])), key=lambda p: math.hypot(p[0] - centre[0], p[1] - centre[1]))
    a0 = math.atan2(far[1] - centre[1], far[0] - centre[0])
    big = math.hypot(far[0] - centre[0], far[1] - centre[1])
    tries = [(f, t) for f in (0.55, 0.7, 0.4, 0.85, 0.25) for t in range(0, 360, 15)]  # (a spot of it the view shows: not under another part or a table)

    def scr(a, rr):
        p = [centre[0] + rr * math.cos(a), centre[1] + rr * math.sin(a), top]
        return js(f"const r = arguments[0].getBoundingClientRect(), v = new window.__V.V3(...arguments[1]).project({A}.view.camera); return [(v.x + 1) / 2 * r.width - r.width / 2, (1 - v.y) / 2 * r.height - r.height / 2]", cv, p)
    ok = js(f"const r = arguments[0].getBoundingClientRect(); return arguments[1].map(([x, y]) => {{ const cx = r.left + r.width / 2 + x, cy = r.top + r.height / 2 + y; return document.elementFromPoint(cx, cy) === arguments[0] && {A}.view.pickInst(cx, cy)?.inst === arguments[2]; }})",
            cv, [scr(a0 + math.radians(t), f * big) for f, t in tries], inst)
    f, t = tries[ok.index(True)] if True in ok else tries[0]
    a0, rr = a0 + math.radians(t), f * big
    gx, gy = scr(a0, rr)
    act = ActionChains(d, duration=20).move_to_element_with_offset(cv, int(gx), int(gy)).click_and_hold()
    for k in range(1, 11):
        sx, sy = scr(a0 + math.radians(deg * k / 10), rr)
        act = act.move_to_element_with_offset(cv, int(sx), int(sy))
    m0 = mats()
    act.release().perform()
    time.sleep(0.6)
    return {i for i, m in mats().items() if any(abs(p - q) > 1e-3 for p, q in zip(m, m0[i]))}


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('a3d.leftDock'); localStorage.setItem('auto3d-lang', 'en')")
    d.get(URL)
    wait("return !!window.__app")
    js(f"window.__V = {{ V3: {A}.view.camera.position.constructor, M4: {A}.view.camera.matrix.constructor, B3: null }}")
    js("window.__V.B3 = class { constructor(a, b) { this.min = a; this.max = b; } applyMatrix4(M) { const ps = []; for (const x of [this.min.x, this.max.x]) for (const y of [this.min.y, this.max.y]) for (const z of [this.min.z, this.max.z]) ps.push(new window.__V.V3(x, y, z).applyMatrix4(M)); this.min = new window.__V.V3(Math.min(...ps.map(p => p.x)), Math.min(...ps.map(p => p.y)), Math.min(...ps.map(p => p.z))); this.max = new window.__V.V3(Math.max(...ps.map(p => p.x)), Math.max(...ps.map(p => p.y)), Math.max(...ps.map(p => p.z))); return this; } }")
    listing = json.loads(urllib.request.urlopen(f"{URL}/api/demos").read())["demos"]
    print("  demos:", [(x["file"], x["name"], x["name_cs"]) for x in listing])
    check(len(listing) >= 3 and all(x["text"] and x["text_cs"] and x["name_cs"] for x in listing), "three demos or more, each with its names and texts (Czech too)")
    before = {x["file"]: demo_bytes(x["file"]) for x in listing}

    # the menu lists them
    d.find_element(By.ID, "openBtn").click()
    time.sleep(0.2)
    d.find_element(By.ID, "demoBtn").click()
    wait("return document.querySelectorAll('.demos [data-demo]').length")
    names = [e.text for e in d.find_elements(By.CSS_SELECTOR, ".demos [data-demo] .aih-prompt")]
    check(names == [x["name"] for x in listing], f"Open ▾ → Demo projects… lists them: {names}")
    d.save_screenshot(f"{OUT}/demos_menu.png")
    d.find_element(By.CSS_SELECTOR, ".demos .choose-x").click()

    # 1. the crank – rod – slider
    f = open_demo(0)
    pid0 = js("return window.__app.autosave.id")
    a = json.loads(call("get_assembly"))
    m = a["mechanisms"][0]
    print("  mechanism:", m["name"], "·", m["driver"]["label"])
    check(f == "klikovy-mechanismus.a3d.json" and m["name"] == "Klikový mechanismus" and m["driver"]["label"] == "Otáčení kliky", f"{f}: ⚙ {m['name']}, driven by “{m['driver']['label']}”")
    shaft, pin, spin = rounds("I1", "side")[0], rounds("I2", "side")[0], rounds("I4", "side")[0]
    R, L = 25, 100
    off = [0]

    def formula():
        (sx, sy), (px, py), (qx, _) = axes(("I1", shaft), ("I2", pin), ("I4", spin))
        th = math.atan2(py - sy, px - sx)
        off[0] = max(off[0], abs(qx - sx - (R * math.cos(th) + math.sqrt(L * L - (R * math.sin(th)) ** 2))))
    moved, w, n = play(0, look=formula)
    check(moved == {"I2", "I3", "I4"} and w < 0.05 and off[0] < 0.05 and n > 5, f"▶: {sorted(moved)} moved, joints off {w:.4f} mm at most, the slider off the formula {off[0]:.4f} mm ({n} looks)")
    d.save_screenshot(f"{OUT}/demo_crank.png")
    moved = drag_turn("I2", ax("I1", shaft))
    off[0] = 0
    formula()
    check({"I3", "I4"} <= moved and off[0] < 0.05 and worst() < 0.05, f"the crank dragged in the view: {sorted(moved)} moved, the formula held ({off[0]:.4f})")

    # 2. the four-bar linkage
    f = open_demo(1)
    check(js("return window.__app.autosave.id") != pid0, "each demo opens as a new project")
    a = json.loads(call("get_assembly"))
    m = a["mechanisms"][0]
    names = {p["id"]: p.get("free") for p in a["parts"]}
    check(m["name"] == "Čtyřkloubový mechanismus" and m["driver"]["label"] == "Otáčení kliky" and "Kývání vahadla" in (names.get("I4") or []) and m.get("full_turn"),
          f"{f}: ⚙ {m['name']}, “{m['driver']['label']}”, the rocker “{names.get('I4')}”")
    s1, s2 = rounds("I1", "side")
    cpin, rpin = rounds("I2", "side")[0], rounds("I4", "side")[0]
    b_, c_ = 70, 50
    fb = {"off": 0, "branch": set(), "swing": [], "turn": []}

    def closed_form():
        (ox, oy), (qx, qy), (px, py), (bx, by) = axes(("I1", s1), ("I1", s2), ("I2", cpin), ("I4", rpin))
        dx, dy = qx - px, qy - py
        dd = math.hypot(dx, dy)
        k = (b_ * b_ - c_ * c_ + dd * dd) / (2 * dd)
        h = math.sqrt(max(0.0, b_ * b_ - k * k))
        sols = [(px + k * dx / dd - s * h * dy / dd, py + k * dy / dd + s * h * dx / dd) for s in (1, -1)]
        e = [math.hypot(bx - x, by - y) for x, y in sols]
        fb["off"] = max(fb["off"], min(e))
        fb["branch"].add(e.index(min(e)))
        fb["swing"].append(math.degrees(math.atan2(by - qy, bx - qx)))
        fb["turn"].append(math.degrees(math.atan2(py - oy, px - ox)))
    moved, w, n = play(0, secs=4.5, look=closed_form)
    sw = max(fb["swing"]) - min(fb["swing"])
    turned = len({round(t / 30) for t in fb["turn"]})
    check(moved == {"I2", "I3", "I4"} and w < 0.05 and fb["off"] < 0.05 and len(fb["branch"]) == 1, f"▶: {sorted(moved)} moved, joints off {w:.4f} mm, the rocker's pin off the closed form {fb['off']:.4f} mm, one branch {fb['branch']}")
    check(turned >= 10 and 20 < sw < 120, f"the crank went all the way round ({turned} of 12 30°-sectors), the rocker swung {sw:.1f}°")
    d.save_screenshot(f"{OUT}/demo_fourbar.png")
    moved = drag_turn("I2", ax("I1", s1), deg=70)
    fb["off"] = 0
    closed_form()
    check({"I3", "I4"} <= moved and fb["off"] < 0.05 and worst() < 0.05, f"the crank dragged in the view: {sorted(moved)} moved, the rocker where the closed form puts it ({fb['off']:.4f})")

    # 3. the robot arm: an open chain
    f = open_demo(2)
    a = json.loads(call("get_assembly"))
    ms = {x["name"]: x for x in a["mechanisms"]}
    print("  mechanisms:", {k: v["driver"]["label"] for k, v in ms.items()})
    check(set(ms) == {"Rameno", "Loket"} and ms["Rameno"]["driver"]["label"] == "Otáčení ramene" and ms["Loket"]["driver"]["label"] == "Ohyb lokte",
          f"{f}: two rows — the arm and the elbow, named in Czech")
    k_arm = [x["name"] for x in a["mechanisms"]].index("Rameno")
    moved, w, n = play(k_arm)
    check(moved == {"I2", "I3", "I4"} and w < 0.05, f"▶ the arm: {sorted(moved)} moved — the forearm and the gripper go along; joints off {w:.4f} mm")
    k_el = [x["name"] for x in a["mechanisms"]].index("Loket")
    moved, w, n = play(k_el)
    check(moved == {"I3", "I4"} and w < 0.05, f"▶ the elbow: {sorted(moved)} moved — the gripper follows, the arm stays; joints off {w:.4f} mm")
    d.save_screenshot(f"{OUT}/demo_robot.png")
    moved = drag_turn("I2", ax("I1", rounds("I1", "side")[0]))
    check({"I2", "I3", "I4"} <= moved and worst() < 0.05, f"the arm dragged in the view: {sorted(moved)} moved")

    # 4. gears and a rack: couplings — the pinion turns the wheel (i = 2:1, the other way) and moves the rack (π·30 a turn)
    f = open_demo(3)
    a = json.loads(call("get_assembly"))
    m = a["mechanisms"][0]
    cs = {c["type"]: c for c in a.get("couplings", [])}
    print("  mechanism:", m["name"], "·", m["driver"]["label"], "| couplings:", [(c["id"], c["type"], c["ratio"]) for c in cs.values()])
    check(f == "prevodovka-s-hrebenem.a3d.json" and len(a["mechanisms"]) == 1 and m["name"] == "Převodovka s hřebenem" and m["driver"]["label"] == "Otáčení pastorku"
          and sorted(m["parts"]) == ["I2", "I3", "I4"], f"{f}: one ⚙ {m['name']} of {m['parts']}, driven by “{m['driver']['label']}”")
    check(cs.get("gear", {}).get("ratio") == 2 and cs["gear"].get("way") == "opposite" and abs(cs.get("rack", {}).get("ratio", 0) - math.pi * 30) < 1e-3, "its couplings: a gear pair 2:1 and a rack π·30 mm per turn")

    def gears():
        g = js(f"return ['I2', 'I3', 'I4'].map(i => {A}.inst(i).matrix)")
        return math.degrees(math.atan2(g[0][1], g[0][0])), math.degrees(math.atan2(g[1][1], g[1][0])), g[2][13]
    g0, gr = gears(), {"off": 0}

    def ratios():
        p, w, y = gears()
        turned = math.degrees(-(y - g0[2]) / 15)  # (the pinion's turn, unwrapped, from where the rack is: 15 mm a radian)
        gr["off"] = max(gr["off"], abs((p - g0[0] - turned + 180) % 360 - 180), abs((w - g0[1] + turned / 2 + 180) % 360 - 180))
    moved, w, n = play(0, look=ratios)
    check(moved == {"I2", "I3", "I4"} and w < 0.05 and gr["off"] < 0.05 and n > 5, f"▶: {sorted(moved)} moved, joints off {w:.4f} mm, the ratios off {gr['off']:.4f}° ({n} looks)")
    d.save_screenshot(f"{OUT}/demo_gears.png")
    g0 = gears()
    moved = drag_turn("I3", ax("I1", rounds("I1", "side")[1]), deg=40)
    gr["off"] = 0
    ratios()
    check({"I2", "I3", "I4"} <= moved and gr["off"] < 0.05, f"the wheel dragged in the view: {sorted(moved)} moved, the ratios held ({gr['off']:.4f}°)")

    # the demo files did not change; Czech
    after = {x["file"]: demo_bytes(x["file"]) for x in listing}
    check(after == before, "the demo files on the server are as they were")
    d.find_element(By.ID, "langBtn").click()
    time.sleep(0.5)
    d.find_element(By.ID, "openBtn").click()
    time.sleep(0.2)
    btn = d.find_element(By.ID, "demoBtn").text
    d.find_element(By.ID, "demoBtn").click()
    wait("return document.querySelectorAll('.demos [data-demo]').length")
    head = d.find_element(By.CSS_SELECTOR, ".demos h3").text
    names = [e.text for e in d.find_elements(By.CSS_SELECTOR, ".demos [data-demo] .aih-prompt")]
    check(btn == "🎬 Demo projekty…" and head == "🎬 Demo projekty" and names == [x["name_cs"] for x in listing], f"Czech: {btn} | {head} | {names}")
    d.save_screenshot(f"{OUT}/demos_menu_cs.png")
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE" and "favicon" not in e["message"]]
    check(not errs, f"no errors in the console: {errs[:3]}")
finally:
    d.quit()

print("\ndemos:", "ALL OK" if not bad else f"{len(bad)} FAILED: {bad}")
sys.exit(1 if bad else 0)
