"""⚠ Collisions while a mechanism moves, in headless Edge, in Czech: an arm (Rameno) turning on a pin of a fixed base with a
post (Sloupek) in its way -> ⚙ Mechanism: ⚠ is off (no bands, the slider into the post: nothing red, no note) -> ⚠ on:
the travel scanned, red bands under the slider where the exact collision check finds the post (just inside a band: a
collision, a few degrees outside: none) -> the slider into a band: both parts glow red, the overlap boxed, the note
"⚠ Kolize: Rameno × Sloupek (−… mm)" -> ▶ with the note (a screenshot mid-animation) -> ⋯ Zastavit při kolizi: ▶ from
outside stops inside a band -> the AI: drive_mechanism {collisions} / get_assembly / check_travel tell the bands ->
autosaved and reloaded: still on -> ⚠ off: nothing red, no note, no bands -> a demo opens with it off -> no console
errors.

  PYTHONIOENCODING=utf-8 py tools/e2e_mech_collisions.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
A = "window.__app.assembly"
H = "window.__app.agentHandlers"
RED = 0x6A0D0D
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


def pos():
    return js(f"const a = {A}, m = a.mech.list[0]; return ((a.motionPos(m.driver.part, m.driver.mo) % 360) + 360) % 360")


def slide(v):
    js("const s = document.querySelector(arguments[0]); s.value = arguments[1]; s.dispatchEvent(new Event('input')); s.dispatchEvent(new Event('change'))", "[data-mcv='0']", v)
    time.sleep(0.5)


def red():
    """The placed parts glowing red (their ids)."""
    return js(f"const a = {A}; return a.view.meshes.map((m, k) => m.material.emissive.getHex() === {RED} ? a.doc.instances[k]?.id : null).filter(Boolean)")


def note():
    els = [e for e in d.find_elements(By.CSS_SELECTOR, "#asmViewport > .mc-clashnote") if e.is_displayed()]
    return els[0].text if els else ""


def bands():
    return js(f"const a = {A}, m = a.mech.list[0], s = a.mech.scans[m.key]; return s && s.steps ? a.mech.clashSummary(m).collision_bands : null")


def exact(v):
    """The kernel's own check with the arm at v (it goes back): does it hit the post?"""
    return d.execute_async_script(f"""const done = arguments[arguments.length - 1], a = {A}, m = a.mech.list[0], snap = a.doc.instances.map(x => [x.id, [...x.matrix]]);
      window.__drive(a, m, arguments[0], false, true);
      const inst = a.flatParts();
      for (const [id, mat] of snap) a.inst(id).matrix = mat;
      a.checkJoints();
      fetch('/api/assembly/clashes', {{method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{instances: inst}})}})
        .then(r => r.json()).then(r => done(r.clashes.some(c => [c.a, c.b].includes('I2') && [c.a, c.b].includes('I3')))).catch(e => done('ERR ' + e));""", v)


def inside(v, bs, pad=0.0):
    return any(b["from"] - pad <= v <= b["to"] + pad for b in bs)


try:
    d.set_script_timeout(60)
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('a3d.leftDock'); localStorage.setItem('auto3d-lang', 'cs')")
    d.get(URL)
    wait("return !!window.__app")
    js("import('/js/assembly/mechanism.js').then(m => { window.__drive = m.driveTo; })")
    call("new_model", name="Základna")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 200, "h": 200}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="sketch", plane={"face": "F2:end"}, shapes=[{"circle": {"x": 0, "y": 0, "d": 8}}])
    call("add_feature", type="extrude", sketch="F3", d=20)
    call("new_model", name="Rameno")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 70, "h": 12}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("add_feature", type="hole", face="F2:end", points=[[-28, 0]], d=8)
    call("new_model", name="Sloupek")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 10, "h": 10}}])
    call("add_feature", type="extrude", sketch="F1", d=20)
    call("new_assembly", name="Rameno a sloupek")
    for p in ("Základna", "Rameno", "Sloupek"):
        call("insert_part", part=p)
    wait(f"return {A}.doc.instances.length === 3 && {A}.doc.instances.every(i => {A}.bodies[i.part]?.body)")
    js(f"{A}.inst('I1').fixed = true")
    hole = js(f"return {A}.bodies[{A}.inst('I2').part].body.faces.find(f => f.type === 'cylinder' && /hole/.test(f.name)).name")
    print(" ", call("snap_faces", type="axis", move={"part": "I2", "face": hole}, onto={"part": "I1", "face": "F4:side:c1"})[:70])
    print(" ", call("snap_faces", type="touch", move={"part": "I2", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})[:70])
    # the post (10 × 10): on the base's top, 40 … 50 mm from the pin (at 100, 100), fixed
    js(f"""const a = {A}, b = a.inst('I1'), p = a.inst('I3'), M = new (a.view.camera.matrix.constructor)().fromArray(b.matrix);
      p.matrix = M.multiply(new (a.view.camera.matrix.constructor)().makeTranslation(95, 140, 10)).toArray(); p.fixed = true; a.commit();""")
    time.sleep(0.8)
    check(js(f"return {A}.mech.list.length === 1 && {A}.mech.list[0].driver.part === 'I2'"), "one mechanism: the arm's turn")

    # ⚠ off by default: no bands, nothing red into the post
    check(not js(f"return {A}.mech.list[0].rec?.clash") and js(f"return {A}.mech.clashSummary({A}.mech.list[0]).collisions") is None, "⚠ is off by default")
    btn = d.find_element(By.CSS_SELECTOR, "[data-mcclash='0']")
    check(btn.text == "⚠" and "on" not in btn.get_attribute("class") and btn.get_attribute("title").startswith("Kolize:"), f"the row's ⚠ in Czech: {btn.get_attribute('title')[:40]!r}")
    check(not d.find_elements(By.CSS_SELECTOR, ".mc-clashbar"), "no bands under the slider")
    js(f"{A}.mech.check({A}.mech.list[0]).catch(() => {{}})")
    chk = wait(f"return {A}.mech.checked[{A}.mech.list[0].key]", 60)
    hits = chk["hits"]
    check(len(hits) == 1 and hits[0]["with"] == "I3", f"⚠ Check the travel: the arm hits the post {[(h['from'], h['to'], h['with']) for h in hits]}")
    mid = (hits[0]["from"] + hits[0]["to"]) / 2
    slide(mid)
    check(not red() and not note() and not js(f"return {A}.mech.scans[{A}.mech.list[0].key]"), f"off: the slider into the post ({mid:.0f}°) — nothing red, no note, no scan")

    # ⚠ on: the travel scanned, red bands where the kernel finds the post
    t0 = time.time()
    d.find_element(By.CSS_SELECTOR, "[data-mcclash='0']").click()
    wait("return document.querySelector('.mc-clashbar:not(.busy)')", 60)
    print(f"  scanned in {time.time() - t0:.1f} s ({js(f'return {A}.mech.scans[{A}.mech.list[0].key].n')} steps)")
    bs = bands()
    print("  bands:", bs)
    check(js(f"return {A}.mech.list[0].rec.clash === true") and "on" in d.find_element(By.CSS_SELECTOR, "[data-mcclash='0']").get_attribute("class"), "⚠ on: kept in the mechanism's record")
    check(len(bs) == 1 and bs[0]["with"] == ["I3"] and 10 < bs[0]["to"] - bs[0]["from"] < 90, f"one band, with the post: {bs}")
    check(len(d.find_elements(By.CSS_SELECTOR, ".mc-clashbar i")) == 1, "one red band drawn under the slider")
    b0 = bs[0]
    e_in = [exact(b0["from"] + 2.5), exact(b0["to"] - 2.5)]
    e_out = [exact(b0["from"] - 4), exact(b0["to"] + 4)]
    check(e_in == [True, True] and e_out == [False, False], f"the band is at the right angles: the kernel finds the post just inside it {e_in}, not 4° outside {e_out}")
    check(b0["from"] - 1 <= hits[0]["from"] and hits[0]["to"] <= b0["to"] + 1, f"⚠ Check the travel's stretch {hits[0]['from']} … {hits[0]['to']} lies in the band")

    # the slider into the band: both red, the overlap boxed, the note
    slide((b0["from"] + b0["to"]) / 2)
    rr, nt = red(), note()
    print("  red:", rr, "| note:", nt)
    check(sorted(rr) == ["I2", "I3"], f"in the band: the arm and the post glow red {rr}")
    check(js(f"return {A}.view.clashGroup.children.length") >= 1, "the overlap boxed")
    check(nt.startswith("⚠ Kolize: Rameno × Sloupek (−") and nt.endswith(" mm)"), f"the note: {nt!r}")
    d.save_screenshot(f"{OUT}/mech_clash_slider.png")
    slide(b0["from"] - 20)
    check(not red() and not note(), "out of it: nothing red, no note")

    # ▶ with ⚠ on: the note comes and goes; a screenshot mid-collision
    d.find_element(By.CSS_SELECTOR, "[data-mcplay='0']").click()
    seen, shot, frames0 = set(), False, js("return performance.now()")
    end = time.time() + 6
    while time.time() < end:
        n = note()
        seen.add(bool(n))
        if n and not shot:
            d.save_screenshot(f"{OUT}/mech_clash_play.png")
            shot = True
        time.sleep(0.05)
    d.find_element(By.CSS_SELECTOR, "[data-mcplay='0']").click()
    time.sleep(0.4)
    check(seen == {True, False} and shot, f"▶: the note shows in the band and goes out of it ({seen}); screenshot {OUT}/mech_clash_play.png")

    # ⋯ Zastavit při kolizi: ▶ stops inside the band
    slide(b0["from"] - 30)
    if not d.find_elements(By.CSS_SELECTOR, "[data-mcstop='0']"):
        d.find_element(By.CSS_SELECTOR, "[data-mcmore='0']").click()
    time.sleep(0.3)
    stop = d.find_element(By.CSS_SELECTOR, "[data-mcstop='0']")
    check("Zastavit při kolizi" in stop.find_element(By.XPATH, "..").text and not stop.is_selected(), "⋯ offers “Zastavit při kolizi”, off")
    stop.click()
    time.sleep(0.4)
    check(js(f"return {A}.mech.list[0].rec.clashStop === true"), "Zastavit při kolizi: on")
    d.find_element(By.CSS_SELECTOR, "[data-mcplay='0']").click()
    wait(f"return !{A}.mech.playing", 12)
    p = pos()
    check(inside(p, bs, 0.5) and p < b0["from"] + 6, f"▶ stopped where the collision starts: {p:.1f}° (band {b0['from']} … {b0['to']})")
    check(sorted(red()) == ["I2", "I3"] and note(), "stopped: both red, the note")
    d.find_element(By.CSS_SELECTOR, "[data-mcplay='0']").click()  # (▶ again from inside: it goes on through)
    time.sleep(1.0)
    check(js(f"return !!{A}.mech.playing"), "▶ again inside the band: it goes on")
    d.find_element(By.CSS_SELECTOR, "[data-mcplay='0']").click()
    time.sleep(0.4)

    # the AI
    tx = call("drive_mechanism", to=(b0["from"] + b0["to"]) / 2)
    print("  drive_mechanism:", tx[-260:])
    check("collision bands over its travel" in tx and "Colliding where it is now" in tx, "drive_mechanism tells the bands and the collision now")
    g = json.loads(call("get_assembly"))
    m0 = g["mechanisms"][0]
    check(m0.get("collisions") is True and m0.get("stop_at_collision") is True and len(m0.get("collision_bands", [])) == 1, f"get_assembly: {dict((k, m0.get(k)) for k in ('collisions', 'stop_at_collision', 'collision_bands'))}")
    call("set_travel", part="I2", motion=0, min=b0["from"] - 40, max=b0["to"] + 40)
    ct = call("check_travel", part="I2", motion=0)
    print("  check_travel:", ct[-160:])
    check("Collision bands" in ct, "check_travel tells the collision bands")
    js(f"const a = {A}, m = a.mech.list[0]; a.setTravel(m.driver.part, m.driver.mo, null)")
    time.sleep(0.5)
    print("  limits off:", js(f"const a = {A}, m = a.mech.list[0]; return [m.min, m.max, m.full, a.inst('I2').travel || null]"))
    tx = call("drive_mechanism", collisions=False)
    check(not js(f"return {A}.mech.list[0].rec?.clash") and "Collisions shown" not in tx, "drive_mechanism {collisions: false}: off")
    tx = call("drive_mechanism", collisions=True)
    check(js(f"return {A}.mech.list[0].rec?.clash === true") and json.dumps(bs, separators=(",", ":")) in tx, f"drive_mechanism {{collisions: true}}: on, bands {tx[tx.find('collision bands'):][:90]!r}")

    # autosaved, reloaded: still on
    js("return window.__app.autosave.saveNow()")
    time.sleep(0.5)
    d.refresh()
    wait("return !!window.__app")
    wait("return document.querySelector('.restore-bar')", 15)
    d.find_element(By.CSS_SELECTOR, ".restore-bar [data-a=open]").click()
    time.sleep(1)
    call("open_part", id="Rameno a sloupek")
    wait(f"return {A}.doc.instances.length === 3 && {A}.doc.instances.every(i => {A}.bodies[i.part]?.body) && {A}.mech.list.length", 60)
    wait("return document.querySelector('.mc-clashbar:not(.busy) i')", 60)
    check(js(f"return {A}.mech.list[0].rec?.clash === true"), "reloaded: ⚠ still on, the bands back")

    # ⚠ off: nothing red, no note, no bands
    js("import('/js/assembly/mechanism.js').then(m => { window.__drive = m.driveTo; })")
    slide((b0["from"] + b0["to"]) / 2)
    check(sorted(red()) == ["I2", "I3"], "on, in the band: red")
    d.find_element(By.CSS_SELECTOR, "[data-mcclash='0']").click()
    time.sleep(0.5)
    slide((b0["from"] + b0["to"]) / 2 + 1)
    check(not red() and not note() and not d.find_elements(By.CSS_SELECTOR, ".mc-clashbar"), "⚠ off: nothing red, no note, no bands")
    d.save_screenshot(f"{OUT}/mech_clash_off.png")

    # a demo opens with it off
    d.find_element(By.ID, "openBtn").click()
    time.sleep(0.2)
    js("document.getElementById('demoBtn').click()")
    wait("return document.querySelectorAll('.demos [data-demo]').length")
    d.find_elements(By.CSS_SELECTOR, ".demos [data-demo]")[0].find_element(By.CSS_SELECTOR, "[data-open]").click()
    wait(f"return window.__app.state.workspace === 'assembly' && {A}.doc.instances.length > 1 && {A}.doc.instances.every(i => {A}.bodies[i.part]?.body) && {A}.mech.list.length", 90)
    time.sleep(0.8)
    check(not js(f"return {A}.mech.list.some(m => m.rec?.clash || m.rec?.clashStop)") and not d.find_elements(By.CSS_SELECTOR, ".mc-clashbar") and not js(f"return Object.keys({A}.mech.scans).length"),
          "a demo: ⚠ off, nothing scanned")

    errs = [e for e in d.get_log("browser") if e["level"] == "SEVERE" and "favicon" not in e["message"]]
    check(not errs, f"no console errors {[e['message'][:160] for e in errs]}")
finally:
    d.quit()

print("FAILED:" if bad else "ALL OK", *bad, sep="\n  ")
sys.exit(1 if bad else 0)
