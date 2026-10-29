"""The drag cue, in headless Edge (Czech, 1600×1000): over the chosen part that a drag moves, the cursor is the motion's
symbol (drag.js dragCue — the same check as the press: dragPlan) and the part and the parts that go with it glow;
elsewhere the normal cursor (the view turns). A pin in a base's hole (turns and slides): ↻ over it; nothing chosen, the
📌 fixed base: no cue -> 🔒 both its motions locked (fully held): no cue -> a lid on the base: ↔ along its slide -> the
crank demo: the crank chosen, over it ⚙ (a mechanism: the crank, the rod and the slider glow), the first-time hint
"Táhněte — pohne mechanismem" at the cursor -> pressed and dragged: the cursor filled, the value at the cursor ("↻ 52°")
the same as ⚙ Mechanism's, the slider at r·cosθ + √(L² − r²sin²θ) -> let go: back to the cue, the hint not shown any
more. Screenshots with the cursor drawn in (headless Edge shows no OS cursor) and the three cursors 4× enlarged.

  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_dragcue.py http://127.0.0.1:5199 <out dir>
"""
import math
import re
import sys
import time
import urllib.parse

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


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def spot(inst):
    """A screen spot on the part (as the mouse picks it, not under a joint's tag), nearest the middle of what is seen of it — px from the canvas' middle."""
    return js(f"""const a = {A}, v = a.view, r = v.renderer.domElement.getBoundingClientRect(), cx = Math.floor(r.left + r.width / 2), cy = Math.floor(r.top + r.height / 2), hits = [];
      for (let y = r.top + 10; y < r.bottom - 10; y += 8) for (let x = r.left + 10; x < r.right - 10; x += 8) if (document.elementFromPoint(x, y) === v.renderer.domElement && v.pickInst(x, y)?.inst === arguments[0]) hits.push([x, y]); // (not under a joint's tag)
      if (!hits.length) return null;
      const c = hits.reduce((s, p) => [s[0] + p[0] / hits.length, s[1] + p[1] / hits.length], [0, 0]);
      const p = hits.sort((p, q) => Math.hypot(p[0] - c[0], p[1] - c[1]) - Math.hypot(q[0] - c[0], q[1] - c[1]))[0];
      return [Math.round(p[0]) - cx, Math.round(p[1]) - cy];""", inst)


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#asmViewport canvas")


def hover(inst=None, at=None):
    """The mouse over the part (or at a spot) -> the canvas' cursor."""
    at = at or spot(inst)
    ActionChains(d, duration=50).move_to_element_with_offset(canvas(), at[0] + 3, at[1] + 2).move_to_element_with_offset(canvas(), *at).perform()
    time.sleep(0.4)
    return cursor()


def cursor():
    return js("return document.querySelector('#asmViewport canvas').style.cursor")


def svg(cur):
    m = re.search(r'url\("data:image/svg\+xml,([^"]+)"\)', cur or "")
    return urllib.parse.unquote(m.group(1)) if m else ""


def kind(cur):
    """Which cue the cursor is: 'turn' / 'slide' / 'mech' (by its drawing), '' the normal one."""
    s = svg(cur)
    m = re.search(r'data-cue="(\w+)', s)
    return "" if not s else m.group(1) if m else "?"


def hotspot(cur):
    """The cursor's hotspot (after its image / image-set) and whether a 2× image comes with it."""
    m = re.search(r'\)\s+(\d+) (\d+), grab', cur or "")
    return (int(m.group(1)), int(m.group(2))) if m else None, " 2x)" in (cur or "")


def tip():
    els = d.find_elements(By.CSS_SELECTOR, "#asmViewport .as-dragtip")
    return (els[0].text, "strong" in els[0].get_attribute("class")) if els else ("", False)


def shot(name, at):
    """A screenshot with the cursor drawn where the mouse is (headless Edge draws no cursor)."""
    js("""const cv = document.querySelector('#asmViewport canvas'), r = cv.getBoundingClientRect(), m = /url\\("([^"]+)"\\).*?\\)?\\s(\\d+) (\\d+), grab/.exec(cv.style.cursor);
      if (!m) return; const im = document.createElement('img'); im.id = 'j-cur'; im.src = m[1];
      Object.assign(im.style, { position: 'fixed', zIndex: 99999, pointerEvents: 'none', width: '32px', height: '32px', left: (r.left + r.width / 2 + arguments[0] - +m[2]) + 'px', top: (r.top + r.height / 2 + arguments[1] - +m[3]) + 'px' });
      document.body.appendChild(im);""", at[0], at[1])
    time.sleep(0.2)
    d.save_screenshot(f"{OUT}/{name}.png")
    js("document.getElementById('j-cur')?.remove()")


def state():
    """The crank's angle θ and the slider's pin x from the base's pin."""
    (sx, sy), (px, py), (qx, _) = js(f"return [['I1', 'F4:side:c1'], ['I2', 'F5:side:c1'], ['I4', 'F4:side:c1']].map(([i, n]) => {{ const f = {A}.worldFace(i, n); return [f.axis.o.x, f.axis.o.y]; }})")
    return math.degrees(math.atan2(py - sy, px - sx)), qx - sx


def expected(theta):
    t = math.radians(theta)
    return R * math.cos(t) + math.sqrt(L * L - (R * math.sin(t)) ** 2)


def plain():
    """A pin in a base's hole (↻), the base (none), the pin locked (none), a lid on the base (↔)."""
    call("new_model", name="Base")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 80, "h": 60}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="hole", face="F2:end", points=[[-25, -15]], d=6)
    call("new_model", name="Pin")
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 6}}])
    call("add_feature", type="extrude", sketch="F1", d=20)
    call("new_model", name="Lid")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 30}}])
    call("add_feature", type="extrude", sketch="F1", d=4)
    call("new_assembly", name="Cue")
    for p in ("Base", "Pin", "Lid"):
        call("insert_part", part=p)
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    js(f"{A}.inst('I1').fixed = true; {A}.commit()")
    hole = js(f"return {A}.bodies[{A}.inst('I1').part].body.faces.find(f => f.type === 'cylinder').name")
    call("snap_faces", type="axis", move={"part": "I2", "face": "F2:side:c1"}, onto={"part": "I1", "face": hole})
    js(f"const m = {A}.doc.mates.find(x => x.move === 'I2'); delete m.dist; delete m.angle; {A}.applyMates(); {A}.commit()")
    call("snap_faces", type="touch", move={"part": "I3", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})
    call("move_free", part="I3", motion="X", amount=20)
    js(f"{A}.choose(null)")
    time.sleep(0.5)
    check(kind(hover("I2")) == "", f"nothing chosen: the normal cursor over the pin ({cursor()!r})")
    js(f"{A}.choose('I2')")
    time.sleep(0.5)
    at = spot("I2")
    c = hover(at=at)
    check(kind(c) == "turn" and c.endswith("grab"), f"the pin chosen (it turns and slides): ↻ over it — {kind(c)!r}, the fallback {c[-5:]!r}")
    hs, two = hotspot(c)
    check(hs == (1, 1) and "M1.5 1.5V17.6" in svg(c), f"the normal arrow with the badge, the hotspot at its tip: {hs}, a 2× image: {two}")
    check(js(f"return {A}.cueParts?.join()") == "I2", f"the pin glows as the part that moves: {js(f'return {A}.cueParts')}")
    shot("cue_turn", at)
    check(kind(hover("I1")) == "", f"over the base (not chosen, 📌 fixed): the normal cursor ({cursor()[:20]!r})")
    js(f"{A}.choose('I1')")
    time.sleep(0.5)
    check(kind(hover("I1")) == "", f"the 📌 fixed base chosen: no cue ({cursor()[:20]!r})")
    js(f"{A}.choose('I3')")
    time.sleep(0.5)
    at = spot("I3")
    c = hover(at=at)
    check(kind(c) == "slide", f"the lid on the base (it slides): ↔ over it — {kind(c)!r}")
    shot("cue_slide", at)
    print("  lock:", call("lock_motion", part="I2", motion=0)[:60], "|", call("lock_motion", part="I2", motion=0)[:60])
    js(f"{A}.choose('I2')")
    time.sleep(0.5)
    n = js(f"return {A}.motionsOf('I2')?.count")
    c = hover("I2")
    check(n == 0 and kind(c) == "", f"the pin fully held ({n} ways): no cue — {c[:20]!r}")
    check(not tip()[0], f"no hint at the cursor over a held part: {tip()}")


def crank():
    """The crank demo: ⚙ over the chosen crank, the hint the first time, dragged: the value at the cursor."""
    js("document.getElementById('openBtn').click()")
    time.sleep(0.4)
    js("document.getElementById('demoBtn').click()")
    wait("return document.querySelectorAll('.demos [data-demo]').length")
    row = next(r for r in d.find_elements(By.CSS_SELECTOR, ".demos [data-demo]") if "klikov" in r.get_attribute("data-demo"))
    row.find_element(By.CSS_SELECTOR, "[data-open]").click()
    wait(f"return window.__app.state.workspace === 'assembly' && {A}.doc.instances.length === 4 && {A}.doc.instances.every(i => {A}.bodies[i.part]?.body) && {A}.mech?.list.length")
    time.sleep(1)
    js("localStorage.removeItem('a3d.dragTip')")
    check(kind(hover("I2")) == "", f"nothing chosen: the normal cursor over the crank ({cursor()!r})")
    js(f"{A}.choose('I2')")
    time.sleep(0.6)
    at = spot("I2")
    c = hover(at=at)
    check(kind(c) == "mech", f"the crank chosen: ⚙ over it (a mechanism) — {kind(c)!r}")
    parts = js(f"return ({A}.cueParts || []).slice().sort().join()")
    check(parts == "I2,I3,I4", f"the crank, the rod and the slider glow (they move together): {parts}")
    check(tip() == ("Táhněte — pohne mechanismem", False), f"the first-time hint at the cursor: {tip()}")
    shot("cue_mech", at)
    rod = spot("I3")
    check(kind(hover(at=rod)) == "", f"over the rod (not chosen: a drag there turns the view): the normal cursor ({cursor()[:20]!r})")
    hover(at=at)
    th0, _ = state()
    ch = ActionChains(d, duration=60)
    ch.move_to_element_with_offset(canvas(), *at).click_and_hold().perform()
    for k in range(1, 7):
        ActionChains(d, duration=40).move_to_element_with_offset(canvas(), at[0] + 8 * k, at[1] + 10 * k).perform()
        time.sleep(0.1)
    time.sleep(0.3)
    c = cursor()
    text, strong = tip()
    th, x = state()
    mc = js(f"return +document.querySelector('[data-mcn]')?.value")
    m = re.match(r"↻ (-?\d+)°", text)
    check('data-cue="mech on"' in svg(c) and c.endswith("grabbing"), f"while dragging: the cursor filled ({kind(c)!r}, {c[-8:]!r})")
    check(bool(m) and strong and mc is not None and abs(int(m.group(1)) - round(mc)) <= 1, f"the value at the cursor: {text!r} — ⚙ Mechanism says {mc}")
    check(abs(th - th0) > 3 and abs(x - expected(th)) < 0.05, f"dragged: θ {th0:.1f}° -> {th:.1f}°, the slider {x:.3f} mm, the formula {expected(th):.3f}")
    shot("cue_dragging", (at[0] + 48, at[1] + 60))
    ActionChains(d).release().perform()
    time.sleep(0.5)
    end = (at[0] + 48, at[1] + 60)
    c = hover(at=spot("I2"))
    check(kind(c) == "mech" and not tip()[0], f"let go: the cue again ({kind(c)!r}), the first-time hint not any more: {tip()}")
    js(f"{A}.choose(null)")
    time.sleep(0.4)
    check(kind(hover(at=end)) == "", f"Esc / nothing chosen: the normal cursor ({cursor()[:20]!r})")
    # the three cursors 4× (to judge them)
    js("""const box = document.createElement('div'); box.id = 'j-big';
      Object.assign(box.style, { position: 'fixed', left: '20px', top: '20px', zIndex: 99999, display: 'flex', gap: '16px', padding: '16px', background: '#0f1216' });
      for (const [k, on] of [['turn', 0], ['slide', 0], ['mech', 0], ['mech', 1]]) for (const bg of ['#0f1216', '#c8ccd2']) {
        const c = window.__cue(k, on); const m = /url\\("([^"]+)"\\)/.exec(c); const w = document.createElement('div');
        Object.assign(w.style, { background: bg, padding: '8px' }); const im = document.createElement('img'); im.src = m[1]; im.style.width = im.style.height = '128px'; w.appendChild(im); box.appendChild(w); }
      document.body.appendChild(box);""")
    time.sleep(0.3)
    d.save_screenshot(f"{OUT}/cue_icons.png")
    js("document.getElementById('j-big')?.remove()")


try:
    d.get(URL)
    wait("return !!window.__app")
    js("return import('./js/assembly/drag.js').then(m => { window.__cue = (k, on) => m.moveCursor(k, 0, !!on); })")
    plain()
    crank()
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        bad.append("console errors")
    d.quit()
print("FAILED:" if bad else "ALL OK", bad if bad else "")
sys.exit(1 if bad else 0)
