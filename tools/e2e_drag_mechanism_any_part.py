"""Any part of a ⚙ mechanism dragged with the real mouse, in headless Edge (Czech, 1600×1000), nothing chosen first:
the crank – rod – slider demo — over the rod the ⚙ cue (the three parts glow); the rod (a coupler: no motion of its
own) pressed and dragged to where its spot is with the crank 60° on: the crank turns there, the grabbed spot under the
mouse, the slider at r·cosθ + √(L² − r²·sin²θ); one Ctrl+Z puts all back -> the slider pressed and dragged along its line:
it follows the mouse, the crank turns, the formula holds -> the crank pressed: it turns after the mouse as before ->
a click without moving only chooses (nothing moves) -> the crank's limits 30° … 150° (⇤⇥): the rod and the slider
dragged far past them — the crank stays within, the formula holds -> the four-bar demo: its coupler dragged — the
crank turns, the rocker's pin where the closed form puts it. No console errors.

  PYTHONIOENCODING=utf-8 py tools/e2e_drag_mechanism_any_part.py http://127.0.0.1:5199 <out dir>
"""
import json
import math
import re
import sys
import time

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


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#asmViewport canvas")


def mid():
    """The canvas' middle on screen (Selenium's offsets are from it)."""
    return js("const r = arguments[0].getBoundingClientRect(); return [Math.floor(r.left + r.width / 2), Math.floor(r.top + r.height / 2)]", canvas())


def spot(inst):
    """A screen spot on the part (as the mouse picks it, 3 px round it too, not under a joint's tag), nearest the middle of
    what is seen of it — px from the canvas' middle."""
    return js(f"""const a = {A}, v = a.view, cv = v.renderer.domElement, r = cv.getBoundingClientRect(), cx = Math.floor(r.left + r.width / 2), cy = Math.floor(r.top + r.height / 2), hits = [];
      const on = (x, y) => document.elementFromPoint(x, y) === cv && v.pickInst(x, y)?.inst === arguments[0];
      for (let y = r.top + 10; y < r.bottom - 10; y += 6) for (let x = r.left + 10; x < r.right - 10; x += 6) if (on(x, y) && on(x + 3, y) && on(x - 3, y) && on(x, y + 3) && on(x, y - 3)) hits.push([x, y]);
      if (!hits.length) return null;
      const c = hits.reduce((s, p) => [s[0] + p[0] / hits.length, s[1] + p[1] / hits.length], [0, 0]);
      const p = hits.sort((p, q) => Math.hypot(p[0] - c[0], p[1] - c[1]) - Math.hypot(q[0] - c[0], q[1] - c[1]))[0];
      return [Math.round(p[0]) - cx, Math.round(p[1]) - cy];""", inst)


def cursor_kind():
    m = re.search(r'data-cue%3D%22(\w+)', js("return document.querySelector('#asmViewport canvas').style.cursor") or "")
    return m.group(1) if m else ""


def hover(at):
    ActionChains(d, duration=50).move_to_element_with_offset(canvas(), at[0] + 3, at[1] + 2).move_to_element_with_offset(canvas(), *at).perform()
    time.sleep(0.4)
    return cursor_kind()


def drag(at, to, steps=12):
    """A real drag: pressed at `at`, the mouse in steps to `to` (px from the canvas' middle), let go."""
    act = ActionChains(d, duration=20).move_to_element_with_offset(canvas(), *at).click_and_hold()
    for k in range(1, steps + 1):
        act = act.move_to_element_with_offset(canvas(), int(at[0] + (to[0] - at[0]) * k / steps), int(at[1] + (to[1] - at[1]) * k / steps))
    act.release().perform()
    time.sleep(0.5)


def mats():
    return {i["id"]: i["matrix"] for i in js(f"return {A}.doc.instances.map(i => ({{id: i.id, matrix: [...i.matrix]}}))")}


def same(a, b):
    return all(all(abs(p - q) < 1e-6 for p, q in zip(a[i], b[i])) for i in a)


def at_mech():
    """Where ⚙ Mechanism says the driver is (its number)."""
    return json.loads(call("get_assembly"))["mechanisms"][0]["at"]


def open_demo(name, n=4):
    js("document.getElementById('openBtn').click()")
    time.sleep(0.4)
    js("document.getElementById('demoBtn').click()")
    wait("return document.querySelectorAll('.demos [data-demo]').length")
    row = next(r for r in d.find_elements(By.CSS_SELECTOR, ".demos [data-demo]") if name in r.get_attribute("data-demo"))
    row.find_element(By.CSS_SELECTOR, "[data-open]").click()
    wait(f"return window.__app.state.workspace === 'assembly' && {A}.doc.instances.length === {n} && {A}.doc.instances.every(i => {A}.bodies[i.part]?.body) && {A}.mech?.list.length")
    time.sleep(1)
    js(f"{A}.choose(null); {A}.view.setView('top')")
    time.sleep(0.8)


def target(inst, at, by):
    """Where the spot `at` (px from the middle) of part `inst` is on screen once the mechanism's driver is `by` further
    on (driven quietly, the parts back after) -> [px from the middle] or null (not on the part)."""
    return js(f"""return import('./js/assembly/mechanism.js').then(M => {{
      const a = {A}, v = a.view, r = v.renderer.domElement.getBoundingClientRect(), cx = Math.floor(r.left + r.width / 2), cy = Math.floor(r.top + r.height / 2);
      const h = v.pickInst(cx + arguments[1][0], cy + arguments[1][1]);
      if (h?.inst !== arguments[0]) return null;
      const T = v.camera.matrix.constructor, it = a.inst(arguments[0]), loc = h.point.clone().applyMatrix4(new T().fromArray(it.matrix).invert());
      const m = a.mech.list[0], snap = a.doc.instances.map(x => [x.id, [...x.matrix]]);
      M.driveTo(a, m, M.posOf(a, m) + arguments[2], false, true);
      const [x, y] = v.toScreen(loc.applyMatrix4(new T().fromArray(it.matrix)));
      for (const [i, mm] of snap) a.inst(i).matrix = mm;
      a.checkJoints(); a.draw();
      return [Math.round(x - cx), Math.round(y - cy)]; }})""", inst, at, by)


def grabbed_at(inst, at):
    """The part's point first under `at`, where it is on screen now (px from the middle)."""
    return js(f"""const a = {A}, v = a.view, r = v.renderer.domElement.getBoundingClientRect(), cx = Math.floor(r.left + r.width / 2), cy = Math.floor(r.top + r.height / 2);
      window.__grab = {{ inst: arguments[0] }};
      const h = v.pickInst(cx + arguments[1][0], cy + arguments[1][1]), T = v.camera.matrix.constructor;
      window.__grab.loc = h.point.clone().applyMatrix4(new T().fromArray(a.inst(arguments[0]).matrix).invert()); return true;""", inst, at)


def grabbed_now():
    return js(f"""const a = {A}, v = a.view, r = v.renderer.domElement.getBoundingClientRect(), cx = Math.floor(r.left + r.width / 2), cy = Math.floor(r.top + r.height / 2), T = v.camera.matrix.constructor;
      const [x, y] = v.toScreen(window.__grab.loc.clone().applyMatrix4(new T().fromArray(a.inst(window.__grab.inst).matrix))); return [x - cx, y - cy];""")


def crank_state():
    """The crank's angle θ (from its shaft to its pin) and the slider's pin x from the shaft."""
    (sx, sy), (px, py), (qx, _) = js(f"return [['I1', 'F4:side:c1'], ['I2', 'F5:side:c1'], ['I4', 'F4:side:c1']].map(([i, n]) => {{ const f = {A}.worldFace(i, n); return [f.axis.o.x, f.axis.o.y]; }})")
    return math.degrees(math.atan2(py - sy, px - sx)), qx - sx


def formula_off():
    th, x = crank_state()
    t = math.radians(th)
    return abs(x - (R * math.cos(t) + math.sqrt(L * L - (R * math.sin(t)) ** 2)))


def dang(a, b):
    return abs((a - b + 180) % 360 - 180)


def worst():
    return js(f"""return import('./js/assembly/loops.js').then(Lp => {{
      const a = {A}, T = a.view.camera.matrix.constructor, P = new Map(a.doc.instances.map(i => [i.id, new T().fromArray(i.matrix)]));
      return Lp.worstMiss(a.doc.mates.filter(m => !a.insideMate(m)), P, (i, n, M) => a.worldFace(i, n, M)); }})""")


def crank():
    open_demo("klikovy")
    js("localStorage.setItem('a3d.dragTip', '1')")
    rod = spot("I3")
    k = hover(rod)
    parts = js(f"return ({A}.cueParts || []).slice().sort().join()")
    check(k == "mech" and parts == "I2,I3,I4" and not js(f"return {A}.sel"), f"nothing chosen, over the rod: the ⚙ cue ({k!r}), {parts} glow")
    check(hover(spot("I1")) == "", "over the 📌 fixed base: the normal cursor")

    # the rod dragged to where its spot is with the crank 60° on
    th0, _ = crank_state()
    p0 = at_mech()
    m0 = mats()
    to = target("I3", rod, 60)
    grabbed_at("I3", rod)
    t0 = time.time()
    drag(rod, to)
    th, x = crank_state()
    g = grabbed_now()
    miss = math.hypot(g[0] - to[0], g[1] - to[1])
    print(f"  (the rod's drag took {time.time() - t0:.2f} s with the mouse's steps)")
    check(dang(th, th0) > 40 and dang(at_mech(), p0 + 60) < 8, f"the rod dragged: the crank {th0:.1f}° -> {th:.1f}° (⚙ {p0:.1f} -> {at_mech():.1f}, wanted {p0 + 60:.1f})")
    check(miss < 10, f"the rod's grabbed spot under the mouse: {miss:.1f} px off")
    check(formula_off() < 0.05 and worst() < 0.05, f"the slider at the formula ({formula_off():.4f} mm), the joints hold ({worst():.4f} mm)")
    check(js(f"return {A}.sel") is None, f"a drag does not choose: {js(f'return {A}.sel')}")
    d.save_screenshot(f"{OUT}/drag_rod.png")
    ActionChains(d).move_to_element_with_offset(canvas(), 300, 300).click().perform()  # (the focus in the view, nothing chosen)
    time.sleep(0.3)
    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    time.sleep(0.8)
    check(same(mats(), m0), "one Ctrl+Z: all back where it was before the drag")

    # the slider along its line (x on screen in the top view)
    sl = spot("I4")
    th0, x0 = crank_state()
    drag(sl, (sl[0] - 40, sl[1]))
    th, x = crank_state()
    check(abs((x0 - x) - 40 * js(f"return (() => {{ const v = {A}.view, T = v.camera.position.constructor, a = v.toScreen(new T(0, 0, 0)), b = v.toScreen(new T(1, 0, 0)); return 1 / Math.hypot(b[0] - a[0], b[1] - a[1]); }})()")) < 1.5,
          f"the slider dragged 40 px left: it moved {x0 - x:.2f} mm (it follows the mouse)")
    check(dang(th, th0) > 5 and formula_off() < 0.05, f"the crank turned {th0:.1f}° -> {th:.1f}°, the formula holds ({formula_off():.4f} mm)")

    # the crank as before
    cr = spot("I2")
    th0, _ = crank_state()
    drag(cr, (cr[0] + 30, cr[1] - 40))
    th, _ = crank_state()
    check(dang(th, th0) > 5 and formula_off() < 0.05, f"the crank dragged: {th0:.1f}° -> {th:.1f}°, the formula holds ({formula_off():.4f} mm)")

    # a click: chooses only
    m0 = mats()
    rod = spot("I3")
    ActionChains(d, duration=50).move_to_element_with_offset(canvas(), *rod).click().perform()
    time.sleep(0.6)
    check(js(f"return {A}.sel") == "I3" and same(mats(), m0), f"a click on the rod: it is chosen ({js(f'return {A}.sel')}), nothing moved")
    js(f"{A}.choose(null)")

    # limits on the crank: 30° … 150°
    idx = js(f"return {A}.motionsOf('I2').motions.findIndex(q => q.key === {A}.mech.list[0].driver.mo.key)")
    print("  limits:", call("set_travel", part="I2", motion=idx, min=30, max=150)[:80])
    call("drive_mechanism", mechanism="I2", to=90)
    time.sleep(0.6)
    m = json.loads(call("get_assembly"))["mechanisms"][0]
    check(m["min"] == 30 and m["max"] == 150 and abs(m["at"] - 90) < 0.5, f"the crank's limits 30° … 150°, it is at {m['at']}")
    lows, highs = [], []
    for who in ("I3", "I4"):
        for dx, dy in ((-260, -200), (260, 200), (-260, 200), (260, -200)):
            s = spot(who)
            if not s:
                continue
            drag(s, (s[0] + dx, s[1] + dy), steps=16)
            a = at_mech()
            (lows if a < 90 else highs).append(a)
            check(29.5 <= a <= 150.5 and formula_off() < 0.05 and worst() < 0.05, f"{who} dragged ({dx:+d}, {dy:+d}) px: the crank at {a:.1f}° — within 30 … 150, the formula holds ({formula_off():.4f})")
    check(lows and highs and min(lows) < 40 and max(highs) > 140, f"the drags reached both stops: {min(lows or [0]):.1f}° and {max(highs or [0]):.1f}°")
    d.save_screenshot(f"{OUT}/drag_limits.png")


def fourbar():
    open_demo("ctyrkloub")
    s1, s2 = js(f"""const b = {A}.bodies[{A}.inst('I1').part].body; const ns = [...new Set(b.faces.filter(f => f.type === 'cylinder' && f.name.includes(':side')).map(f => f.name))];
      return ns.map(n => [n, {A}.worldFace('I1', n).axis.o.x]).sort((p, q) => p[1] - q[1]).map(p => p[0])""")
    cpin = js(f"return {A}.bodies[{A}.inst('I2').part].body.faces.filter(f => f.type === 'cylinder' && f.name.includes(':side')).map(f => f.name).sort((p, q) => {A}.worldFace('I2', p).axis.o.x - {A}.worldFace('I2', q).axis.o.x)[0]")
    rpin = js(f"return {A}.bodies[{A}.inst('I4').part].body.faces.filter(f => f.type === 'cylinder' && f.name.includes(':side')).map(f => f.name).sort((p, q) => {A}.worldFace('I4', p).axis.o.x - {A}.worldFace('I4', q).axis.o.x)[0]")
    b_, c_ = 70, 50

    def state():
        (ox, oy), (qx, qy), (px, py), (bx, by) = js(f"return arguments[0].map(([i, n]) => {{ const o = {A}.worldFace(i, n).axis.o; return [o.x, o.y]; }})", [["I1", s1], ["I1", s2], ["I2", cpin], ["I4", rpin]])
        dx, dy = qx - px, qy - py
        dd = math.hypot(dx, dy)
        k = (b_ * b_ - c_ * c_ + dd * dd) / (2 * dd)
        h = math.sqrt(max(0.0, b_ * b_ - k * k))
        off = min(math.hypot(bx - (px + k * dx / dd - s * h * dy / dd), by - (py + k * dy / dd + s * h * dx / dd)) for s in (1, -1))
        return math.degrees(math.atan2(py - oy, px - ox)), off
    cp = spot("I3")
    check(hover(cp) == "mech", "the four-bar: over the coupler (nothing chosen) the ⚙ cue")
    th0, _ = state()
    to = target("I3", cp, 50)
    grabbed_at("I3", cp)
    drag(cp, to)
    th, off = state()
    g = grabbed_now()
    check(dang(th, th0) > 30 and off < 0.05 and worst() < 0.05, f"the coupler dragged: the crank {th0:.1f}° -> {th:.1f}°, the rocker's pin off the closed form {off:.4f} mm")
    check(math.hypot(g[0] - to[0], g[1] - to[1]) < 10, f"the coupler's grabbed spot under the mouse: {math.hypot(g[0] - to[0], g[1] - to[1]):.1f} px off")
    d.save_screenshot(f"{OUT}/drag_coupler.png")


try:
    d.get(URL)
    wait("return !!window.__app")
    crank()
    fourbar()
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        bad.append("console errors")
    d.quit()
print("FAILED:" if bad else "ALL OK", bad if bad else "")
sys.exit(1 if bad else 0)
