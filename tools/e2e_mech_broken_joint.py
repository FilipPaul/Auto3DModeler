"""⚙ Mechanism brought into view, and a broken joint said, in headless Edge, in Czech, with real clicks: a Base with a
Ø8 pin, an Arm with a Ø8 hole at one end, the Arm on the pin (◎ Concentric J1 + ⧉ Touch J2): it turns — a mechanism ->
the ⚙ Mechanismus widget folded in the left column, the Arm clicked in the part list, ⚙ Ovládat mechanismus: the widget unfolded, a ring
on its row, its slider focused -> the widget floating behind the suggestions, ⚙ Ovládat mechanismus: raised to the front, ringed -> a new hole at the Arm's other end, its first one deleted (its face F3:hole:0 is gone): J1 broken —
the mechanism row says "⚠ vazba J1 je přerušená — plocha F3:hole:0 chybí" with 🔧 Opravit vazbu, the joint list too ->
its slider moved: one warning toast (with its own 🔧 Opravit vazbu), moved again: no second one -> 🔧 Opravit vazbu,
a click on the new hole's rim in the view: J1 holds on F4:hole:0, the Arm's new hole on the pin's axis, no warning.

  PYTHONIOENCODING=utf-8 py tools/e2e_mech_broken_joint.py http://127.0.0.1:5199 <out dir>
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
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
A = "window.__app.assembly"
H = "window.__app.agentHandlers"
W = ".lw-widget[data-w=mech]"
fails = []


def check(what, ok):
    print(("  ok  " if ok else "  FAIL") + " " + what)
    if not ok:
        fails.append(what)


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(script)


def call(t, **a):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", t, a)


def world(inst, p):
    return js(f"const m = {A}.inst(arguments[0]).matrix, [x, y, z] = arguments[1]; return [m[0]*x + m[4]*y + m[8]*z + m[12], m[1]*x + m[5]*y + m[9]*z + m[13], m[2]*x + m[6]*y + m[10]*z + m[14]]", inst, p)


def at(inst, p):
    """A point of a placed part on the screen, from the canvas' middle (px)."""
    return js(f"""const v = {A}.view, V = v.camera.position.constructor, [sx, sy] = v.toScreen(new V(...arguments[0])), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", world(inst, p))


def click(o):
    cv = d.find_element(By.CSS_SELECTOR, "#asmViewport canvas")
    ActionChains(d, duration=30).move_to_element_with_offset(cv, *o).perform()
    time.sleep(0.2)
    ActionChains(d).click().perform()
    time.sleep(0.6)


def ring_on(sel):
    return js("""const r = document.querySelector('.teach-ring.pt-ring:not(.pt-out)'), el = [...document.querySelectorAll(arguments[0])].find((e) => e.getClientRects().length);
      if (!r || r.hidden || !el) return false;
      const a = r.getBoundingClientRect(), b = el.getBoundingClientRect(), cx = b.left + b.width / 2, cy = b.top + b.height / 2;
      return cx > a.left && cx < a.right && cy > a.top && cy < a.bottom;""", sel)


def drive_row():
    """The Arm clicked in the assembly's part list, then ⚙ Ovládat mechanismus in the suggestions."""
    js(f"{A}.choose(null)")
    time.sleep(0.3)
    d.find_element(By.CSS_SELECTOR, '.as-list .mt-item[data-inst="I2"] .mt-name').click()
    time.sleep(0.5)
    rows = [b for b in d.find_elements(By.CSS_SELECTOR, "#asmViewport .view-suggest .vs-list button[data-sg], .view-suggest.docked .vs-list button[data-sg]") if "Ovládat mechanismus" in b.text]
    check(f"⚙ Ovládat mechanismus in the Arm's suggestions (sel {js(f'return {A}.sel')}: {[' '.join(b.text.split()) for b in d.find_elements(By.CSS_SELECTOR, '.view-suggest .vs-list button')][:8]})", bool(rows))
    rows[0].click()
    time.sleep(0.5)


def warnings():
    return [e.text for e in d.find_elements(By.CSS_SELECTOR, "#toasts .toast.warning") if "J1" in e.text]


def slide(v):
    js("const s = document.querySelector('[data-mcv=\"0\"]'); s.value = arguments[0]; s.dispatchEvent(new Event('input')); s.dispatchEvent(new Event('change'))", v)
    time.sleep(0.4)


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.setItem('auto3d-lang', 'cs'); localStorage.removeItem('a3d.leftDock')")
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Base")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 80, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="sketch", plane={"face": "F2:end"}, shapes=[{"circle": {"x": 0, "y": 0, "d": 8}}])
    call("add_feature", type="extrude", sketch="F3", d=20)
    call("new_model", name="Arm")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 16}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("add_feature", type="hole", face="F2:end", points=[[-20, 0]], d=8)
    call("new_assembly", name="Otočné rameno")
    for p in ("Base", "Arm"):
        call("insert_part", part=p)
    wait(f"return {A}.doc.instances.length === 2 && {A}.doc.instances.every(i => {A}.bodies[i.part]?.body)")
    js(f"{A}.inst('I1').fixed = true")
    call("snap_faces", type="axis", move={"part": "I2", "face": "F3:hole:0"}, onto={"part": "I1", "face": "F4:side:c1"})
    call("snap_faces", type="touch", move={"part": "I2", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})
    time.sleep(0.6)
    mech = (json.loads(call("get_assembly")).get("mechanisms") or [None])[0]
    check(f"a mechanism: the Arm turns ({mech and mech.get('driver')})", bool(mech) and mech["parts"] == ["I2"])

    # (a) the widget folded: ⚙ Ovládat mechanismus unfolds it, rings its row, focuses its slider
    js("window.__leftDock.fold('mech', true)")
    time.sleep(0.3)
    check("⚙ Mechanismus folded in the left column", js(f"return document.querySelector('{W}').classList.contains('folded')"))
    drive_row()
    check("unfolded", not js(f"return document.querySelector('{W}').classList.contains('folded')"))
    check("a ring on its row", ring_on(f"{W} .mc-row"))
    check("its slider focused", js("return document.activeElement?.matches('[data-mcv]')"))
    d.save_screenshot(f"{OUT}/mech_brought.png")
    # floating behind another box: raised
    js("window.__leftDock.float('mech')")
    time.sleep(0.4)
    js(f"{A}.choose(null)")
    time.sleep(0.3)
    d.find_element(By.CSS_SELECTOR, '.as-list .mt-item[data-inst="I2"] .mt-name').click()
    time.sleep(0.5)
    js("document.querySelectorAll('#asmViewport > .fb-front').forEach(b => b.classList.remove('fb-front')); document.querySelector('#asmViewport > .view-suggest')?.classList.add('fb-front')")  # (the suggestions over it)
    check("floating, not in front", not js(f"return document.querySelector('{W}').classList.contains('fb-front')") and js(f"return document.querySelector('{W}').classList.contains('floating')"))
    d.find_element(By.CSS_SELECTOR, "#asmViewport .view-suggest").find_elements(By.XPATH, ".//button[contains(., 'Ovládat mechanismus')]")[0].click()
    time.sleep(0.5)
    check("floating: raised to the front, ringed", js(f"return document.querySelector('{W}').classList.contains('fb-front')") and ring_on(f"{W} .mc-row"))
    js("window.__leftDock.reset()")
    time.sleep(0.4)

    # (b) the Arm's hole replaced by one at its other end: J1 broken
    call("open_part", id="Arm")
    print("  new hole:", call("add_feature", type="hole", face="F2:end", points=[[20, 0]], d=8)[:40])
    print("  old one deleted:", call("delete_feature", id="F3")[:60])
    call("open_part", id="Otočné rameno")
    wait(f"return {A}.doc.mates.find(m => m.id === 'J1')?.broken", 30)
    time.sleep(0.6)
    j = next(x for x in json.loads(call("get_assembly"))["joints"] if x["id"] == "J1")
    check(f"J1 broken, its gone face named: {j}", j.get("broken") and j.get("gone_face") == "F3:hole:0")
    note = d.find_elements(By.CSS_SELECTOR, f"{W} .mc-broken")
    check(f"the mechanism row says so: {[n.text for n in note]}", note and "vazba J1 je přerušená" in note[0].text and "F3:hole:0 chybí" in note[0].text and "Opravit vazbu" in note[0].text)
    js(f"{A}.choose('I2')")
    time.sleep(0.4)
    jl = [e.text for e in d.find_elements(By.CSS_SELECTOR, ".as-jrow.bad") if "J1" in e.text]
    check(f"the joint list too: {jl}", jl and "F3:hole:0 chybí" in jl[0] and "Opravit vazbu" in jl[0])
    check("get_assembly's mechanism lists it", any(b["id"] == "J1" for b in (json.loads(call("get_assembly"))["mechanisms"][0].get("broken_joints") or [])))
    d.save_screenshot(f"{OUT}/mech_broken.png")

    # driving: one warning
    slide(30)
    w1 = warnings()
    check(f"driving with it broken warns: {w1}", len(w1) == 1 and "Opravit vazbu" in w1[0])
    slide(60)
    check("driving again: no second warning", len(warnings()) == 1)

    # 🔧 Opravit vazbu, a click on the new hole's rim
    d.find_element(By.CSS_SELECTOR, f"{W} [data-mcfix=J1]").click()
    time.sleep(0.4)
    hint = js("return document.querySelector('#asmViewport .m-hint')?.textContent || ''")
    check(f"fixing: the hint says what to click: {hint}", "F3:hole:0" in hint and "Arm I2" in hint)
    o = None
    for ang in range(0, 360, 20):
        p = [50 + 4 * math.cos(math.radians(ang)), 8 + 4 * math.sin(math.radians(ang)), 5]
        q = at("I2", p)
        hit = js(f"""const v = {A}.view, r = v.renderer.domElement.getBoundingClientRect(), x = Math.floor(r.left + r.width / 2) + arguments[0], y = Math.floor(r.top + r.height / 2) + arguments[1];
          const h = {A}.jointPick({{clientX: x, clientY: y}}, v.pickInst(x, y)); return h?.inst === 'I2' && h.face?.name === 'F4:hole:0'""", *q)
        if hit:
            o = q
            break
    check("the new hole's rim found on the screen", o is not None)
    click(o)
    time.sleep(0.6)
    j = next(x for x in json.loads(call("get_assembly"))["joints"] if x["id"] == "J1")
    check(f"J1 holds again on the new hole: {j}", not j.get("broken") and j["face"] == "F4:hole:0")
    ax = js(f"const a = {A}.worldFace('I2', 'F4:hole:0').axis, b = {A}.worldFace('I1', 'F4:side:c1').axis; return Math.hypot(a.o.x - b.o.x, a.o.y - b.o.y)")
    check(f"the Arm's new hole on the pin's axis ({ax:.4f} mm off)", ax < 0.01)
    check("the row no longer warns", not d.find_elements(By.CSS_SELECTOR, f"{W} .mc-broken"))
    d.save_screenshot(f"{OUT}/mech_fixed.png")
    errs = [x["message"] for x in d.get_log("browser") if x["level"] == "SEVERE"]
    check(f"no errors in the console: {errs[:3]}", not errs)
finally:
    js("localStorage.removeItem('auto3d-lang')")
    d.quit()

print("FAILED:" if fails else "ALL OK", *fails, sep="\n  ")
sys.exit(1 if fails else 0)
