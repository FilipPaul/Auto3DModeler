"""A crank – rod – slider put together by mouse only, as a new user would (headless Edge, Czech, 1600×1000): 📂 Otevřít ▾
→ 🎬 Demo projects → the crank demo (its four parts) -> ＋ → Nová sestava -> ＋ Vložit díl ×4 -> each joint by real
clicks in the view (no AI tools, no API): a hole's rim, Ctrl+click the pin -> "◎ Soustředně + dosednout · Ø10" first
(the crank on the base's pin, seated); the rod on the crank's pin the same way (Ø8); the slider's top, Ctrl+click the
base's top -> "⧉ Položit Smýkadlo na Základna"; the rod's second eye, Ctrl+click the slider's pin -> "◎ Soustředně ·
Ø8": the loop closes (one free motion); the slider's front side, Ctrl+click the base's front side -> "▭ Zarovnat"
first, its offset kept (the slider stays in line) -> ⚙ Mechanismus: 90 typed — the slider at r·cosθ + √(L² − r²sin²θ)
(r 25, L 100), as in e2e_assembly_loop; ▶ plays, the joints hold. Every face is picked on the first click; the clicks
are counted. The helper: with all but the last joint, ⚙ Mechanismus shows "Chybí jedna vazba, aby se mechanismus
uzavřel: díra Ø8 (Ojnice) ↔ čep Ø8 (Smýkadlo)" (not before the slider is placed, not when complete); ➕ Přidat vazbu
closes the loop (the slider at the formula), Ctrl+Z takes it back.

  PYTHONIOENCODING=utf-8 py tools/e2e_mechanism_by_mouse.py http://127.0.0.1:5199 <out dir>
"""
import math
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
R, L = 25, 100
bad = []
clicks = [0]


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


def press(el):
    ActionChains(d).move_to_element(el).click().perform()
    clicks[0] += 1
    time.sleep(0.4)


# Where to click a face, as a user aims: a round face (a hole, a pin's rim) — the point of its rim nearest the eye; a
# flat or round face — where the hover lights it up, nearest the middle of what is seen of it (screen px from the
# canvas' middle). What a click there picks is what the app's hover shows (idleSnap / roundEdgeAt / pickInst).
AIM = """
const a = %s, v = a.view, [inst, name, kind] = arguments, it = a.inst(inst), b = a.bodyOf(it).body, m = new (v.camera.matrix.constructor)().fromArray(it.matrix);
const r = v.renderer.domElement.getBoundingClientRect(), cx = Math.floor(r.left + r.width / 2), cy = Math.floor(r.top + r.height / 2);
const P = new (v.camera.position.constructor)();
const scr = (x, y, z) => { P.set(x, y, z).applyMatrix4(m); const [sx, sy] = v.toScreen(P.clone()); return [sx, sy, P.distanceTo(v.camera.position)]; };
const ids = new Set(b.faces.filter(f => f.name === name).map(f => f.id)), idx = b.faces.map((f, i) => ids.has(f.id) ? i : -1).filter(i => i >= 0);
const what = (sx, sy) => { const h = v.pickInst(sx, sy); if (a.idleSnap({ clientX: sx, clientY: sy }, h)?.snap) return null; const f = v.roundEdgeAt(sx, sy) || h; return f?.face ? f.inst + ':' + f.face.name : null; };
let out = [];
if (kind === 'rim') {
  for (const e of b.edges || []) { if (!(e.faces || []).some(i => idx.includes(i))) continue; const p = e.pts; for (let k = 0; k + 2 < p.length; k += 3) out.push(scr(p[k], p[k + 1], p[k + 2])); }
  out.sort((p, q) => p[2] - q[2]);
  out = out.slice(0, 1);
} else {
  const PF = b._P || (b._P = (typeof b.positions === 'string' ? new Float32Array(Uint8Array.from(atob(b.positions), c => c.charCodeAt(0)).buffer) : b.positions));
  const FF = b._F || (b._F = (typeof b.face_ids === 'string' ? new Uint32Array(Uint8Array.from(atob(b.face_ids), c => c.charCodeAt(0)).buffer) : b.face_ids));
  const tris = [];
  for (let t = 0; t < FF.length; t++) if (ids.has(FF[t])) { const k = t * 9; tris.push(scr((PF[k] + PF[k + 3] + PF[k + 6]) / 3, (PF[k + 1] + PF[k + 4] + PF[k + 7]) / 3, (PF[k + 2] + PF[k + 5] + PF[k + 8]) / 3)); }
  const xs = tris.map(p => p[0]), ys = tris.map(p => p[1]), x0 = Math.min(...xs) - 30, x1 = Math.max(...xs) + 30, y0 = Math.min(...ys) - 30, y1 = Math.max(...ys) + 30;
  const st = Math.max(2, Math.round(Math.max(x1 - x0, y1 - y0) / 60)), vis = [];
  for (let y = y0; y <= y1; y += st) for (let x = x0; x <= x1; x += st) if (what(x, y) === inst + ':' + name) vis.push([x, y]);
  const c = vis.reduce((s, p) => [s[0] + p[0] / vis.length, s[1] + p[1] / vis.length], [0, 0]);
  out = vis.sort((p, q) => Math.hypot(p[0] - c[0], p[1] - c[1]) - Math.hypot(q[0] - c[0], q[1] - c[1])).slice(0, 1);
}
return out.filter(([sx, sy]) => sx > r.left + 4 && sx < r.right - 4 && sy > r.top + 4 && sy < r.bottom - 4).map(([sx, sy]) => [Math.round(sx) - cx, Math.round(sy) - cy]);
""" % A


def pick(inst, face, kind, ctrl=False):
    """One click (Ctrl+click) on a face, aimed as a user would -> was it picked on that first click?"""
    spot = js(AIM, inst, face, kind)
    if not spot:
        check(False, f"{inst} {face}: nowhere to click it")
        return False
    cv = d.find_element(By.CSS_SELECTOR, "#asmViewport canvas")
    ActionChains(d, duration=30).move_to_element_with_offset(cv, *spot[0]).perform()
    time.sleep(0.25)
    ch = ActionChains(d)
    (ch.key_down(Keys.CONTROL).click().key_up(Keys.CONTROL) if ctrl else ch.click()).perform()
    clicks[0] += 1
    time.sleep(0.5)
    return [inst, face] in js(f"return ({A}.facePicks || []).map(q => [q.inst, q.face.name])")


def table():
    box = d.find_elements(By.CSS_SELECTOR, "#asmViewport .view-suggest")
    return [" ".join(b.text.split()) for b in box[0].find_elements(By.CSS_SELECTOR, ".vs-list button")] if box else []


def choose(first):
    """The table's first suggestion is `first` (its start) -> clicked."""
    rows = table()
    check(bool(rows) and rows[0].startswith(first), f"the first suggestion: {first!r} — the table {rows}")
    btn = d.find_elements(By.CSS_SELECTOR, "#asmViewport .view-suggest .vs-list button")
    if btn:
        press(btn[0])
        time.sleep(0.6)


def rounds(i, kind):
    """A placed part's round faces of a kind ('hole' / 'side' — a pin's), by their axis' x."""
    return js(f"""const it = {A}.inst(arguments[0]), b = {A}.bodies[it.part].body;
      return [...new Set(b.faces.filter(f => f.type === 'cylinder' && f.name.includes(arguments[1])).map(f => f.name))].map(n => [n, {A}.worldFace(arguments[0], n).axis.o.x]).sort((p, q) => p[1] - q[1]).map(p => p[0])""", i, ":" + kind)


def front(i):
    """A placed part's flat face toward −y (its front side)."""
    return js(f"""const it = {A}.inst(arguments[0]), b = {A}.bodies[it.part].body;
      return [...new Set(b.faces.filter(f => f.type === 'plane').map(f => f.name))].find(n => {A}.worldFace(arguments[0], n).normal.y < -0.99)""", i)


def geo():
    """The crank's angle θ (deg), the slider's pin x and y from the base's pin (mm) — at once."""
    (sx, sy), (px, py), (qx, qy) = js(f"return arguments[0].map(([i, n]) => {{ const f = {A}.worldFace(i, n); return [f.axis.o.x, f.axis.o.y]; }})",
                                      [["I1", rounds("I1", "side")[0]], ["I2", rounds("I2", "side")[0]], ["I4", rounds("I4", "side")[0]]])
    return math.degrees(math.atan2(py - sy, px - sx)), qx - sx, qy - sy


def expected(theta):
    t = math.radians(theta)
    return R * math.cos(t) + math.sqrt(L * L - (R * math.sin(t)) ** 2)


def unheld():
    return js(f"return ({A}.doc.mates || []).filter(m => {A}.health?.get(m.id)?.ok === false).map(m => m.id)")


def mates():
    return js(f"return {A}.doc.mates.map(m => [m.type, m.move, m.onto])")


def worst():
    """The largest miss of all the joints (mm)."""
    return js(f"""return import('./js/assembly/loops.js').then(L => {{
      const a = {A}, M = a.view.camera.matrix.constructor, P = new Map(a.doc.instances.map(i => [i.id, new M().fromArray(i.matrix)]));
      return L.worstMiss(a.doc.mates.filter(m => !a.insideMate(m)), P, (i, n, MM) => a.worldFace(i, n, MM)); }})""")


def build():
    """The demo's parts, a new assembly with the four of them — by mouse."""
    d.get(URL)
    wait("return !!window.__app")
    time.sleep(1)
    press(d.find_element(By.ID, "openBtn"))
    press(d.find_element(By.ID, "demoBtn"))
    wait("return document.querySelectorAll('.demos [data-demo]').length")
    row = next(r for r in d.find_elements(By.CSS_SELECTOR, ".demos [data-demo]") if "klikov" in r.get_attribute("data-demo"))
    press(row.find_element(By.CSS_SELECTOR, "[data-open]"))
    wait(f"return window.__app.state.workspace === 'assembly' && {A}.doc.instances.length === 4 && {A}.doc.instances.every(i => {A}.bodies[i.part]?.body)")
    time.sleep(1)
    clicks[0] = 0
    press(d.find_element(By.CSS_SELECTOR, ".pt-add"))
    press(d.find_element(By.CSS_SELECTOR, ".part-add [data-new=assembly]"))
    wait(f"return {A}.doc.instances.length === 0 && !document.querySelector('.as-start').hidden")
    time.sleep(0.5)
    start = d.find_element(By.CSS_SELECTOR, ".as-start").text
    check("Vložit díl" in start and "Ctrl+klik" in start and "Mechanismus" in start, f"the empty assembly says what to do, in Czech: {' '.join(start.split())[:160]}")
    for k, name in enumerate(["Základna", "Klika", "Ojnice", "Smýkadlo"]):
        press(d.find_element(By.CSS_SELECTOR, ".as-insert > button"))
        press(next(b for b in d.find_elements(By.CSS_SELECTOR, ".as-insert .menu-list [data-part]") if b.text.strip().endswith(name)))
        wait(f"return {A}.doc.instances.length === {k + 1} && {A}.doc.instances.every(i => {A}.bodies[i.part]?.body)")
        time.sleep(0.4)
    print(f"  a new assembly with the four parts: {clicks[0]} clicks")


def pivots():
    """The crank on the base's pin, the rod on the crank's pin, the slider on the base — each in 3 clicks."""
    n = clicks[0]
    check(pick("I2", rounds("I2", "hole")[0], "rim") and pick("I1", rounds("I1", "side")[0], "face", ctrl=True), "the crank's hole, Ctrl+click the base's pin: both picked on the first click")
    d.save_screenshot(f"{OUT}/mouse_pivot_table.png")
    choose("◎ Soustředně + dosednout · Ø10")
    check(mates() == [["axis", "I2", "I1"], ["touch", "I2", "I1"]] and not unheld(), f"the crank on the base's pin, seated: {mates()}")
    check(pick("I3", rounds("I3", "hole")[0], "rim") and pick("I2", rounds("I2", "side")[0], "face", ctrl=True), "the rod's first eye, Ctrl+click the crank's pin: picked on the first click")
    choose("◎ Soustředně + dosednout · Ø8")
    check(mates()[2:] == [["axis", "I3", "I2"], ["touch", "I3", "I2"]] and not unheld(), f"the rod on the crank's pin, seated: {mates()[2:]}")
    check(not hint(), f"nothing near-closed yet (the slider not placed): no 'missing joint' line {hint()}")
    check(pick("I4", "F2:end", "face") and pick("I1", "F2:end", "face", ctrl=True), "the slider's top, Ctrl+click the base's top: picked on the first click")
    choose("⧉ Položit Smýkadlo na Základna")
    check(mates()[4:] == [["touch", "I4", "I1"]] and not unheld(), f"the slider down on the base (its underside): {mates()[4:]}")
    print(f"  the two pivots and the slider: {clicks[0] - n} clicks")


def hint():
    return [" ".join(e.text.split()) for e in d.find_elements(By.CSS_SELECTOR, ".mc-miss") if e.is_displayed()]


def helper():
    """Built but for the last joint: ⚙ Mechanismus says which one is missing; ➕ Přidat vazbu closes the loop; Ctrl+Z: back."""
    h = hint()
    check(h == ["Chybí jedna vazba, aby se mechanismus uzavřel: díra Ø8 (Ojnice) ↔ čep Ø8 (Smýkadlo) ➕ Přidat vazbu"], f"the missing joint named in ⚙ Mechanismus: {h}")
    d.save_screenshot(f"{OUT}/mouse_missing_hint.png")
    # ⚙ Mechanismus closed (its ✕): the line is in the panel of the slider
    press(d.find_element(By.CSS_SELECTOR, ".lw-widget[data-w=mech] .lw-close"))
    check(pick("I4", "F2:end", "face"), "the slider's top clicked")
    ph = [" ".join(e.text.split()) for e in d.find_elements(By.CSS_SELECTOR, "#asmRight .mc-miss")]
    check(not hint() or ph, f"⚙ Mechanismus closed: the line in the slider's panel {ph}")
    d.save_screenshot(f"{OUT}/mouse_missing_panel.png")
    press(d.find_element(By.CSS_SELECTOR, "#asmViewport .m-cmdbar [data-a=mech]"))
    check(len(hint()) == 1, f"⚙ Mechanismus open again (toolbar): the line there {hint()}")
    n = len(mates())
    press(d.find_element(By.CSS_SELECTOR, ".mc-miss [data-mcadd]"))
    time.sleep(0.8)
    lp = js(f"return ({A}.loops || []).map(l => [l.parts.join(','), l.closed])")
    check(mates()[n:] == [["axis", "I3", "I4"]] and lp == [["I2,I3,I4", True]] and not unheld() and not hint(),
          f"➕ Přidat vazbu: {mates()[n:]}, the loop {lp}, the line gone {hint()}")
    th, x, y = geo()
    check(abs(x - expected(th)) < 0.05, f"  the slider under the rod's eye: θ {th:.2f}°, {x:.3f} mm (the formula {expected(th):.3f}), {y:.3f} across")
    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    time.sleep(0.8)
    check(len(mates()) == n and hint(), f"Ctrl+Z: the joint gone ({len(mates())} joints), the line back")


def close_loop():
    n = clicks[0]
    check(pick("I3", rounds("I3", "hole")[1], "rim") and pick("I4", rounds("I4", "side")[0], "face", ctrl=True), "the rod's second eye, Ctrl+click the slider's pin: picked on the first click")
    choose("◎ Soustředně · Ø8")
    lp = js(f"return ({A}.loops || []).map(l => [l.parts.join(','), l.closed, l.free])")
    check(lp and lp[0][0] == "I2,I3,I4" and lp[0][1] and not unheld(), f"the loop closed: {lp}, joints not held {unheld()}")
    print(f"  the loop closed: {clicks[0] - n} clicks")


def line():
    n = clicks[0]
    _, x0, y0 = geo()
    check(pick("I4", front("I4"), "face") and pick("I1", front("I1"), "face", ctrl=True), "the slider's front side, Ctrl+click the base's front side: picked on the first click")
    choose("▭ Zarovnat")
    th, x, y = geo()
    check(abs(y - y0) < 0.01 and abs(y) < 0.01 and abs(th) < 0.01 and not unheld(), f"Flush on the placed slider: its offset kept — the slider in line ({y0:.3f} -> {y:.3f} mm across), the crank at {th:.2f}°")
    print(f"  the slider's line: {clicks[0] - n} clicks")


def drive():
    rows = d.find_elements(By.CSS_SELECTOR, ".mc-row")
    k = next((i for i, r in enumerate(rows) if "další 2" in r.text), None)
    check(k is not None, f"⚙ Mechanismus shows the loop: {[' '.join(r.text.split())[:80] for r in rows]}")
    if k is None:
        return
    num = rows[k].find_element(By.CSS_SELECTOR, "[data-mcn]")
    ActionChains(d).double_click(num).perform()
    clicks[0] += 1
    num.send_keys(Keys.CONTROL, "a")
    num.send_keys("90", Keys.ENTER)
    time.sleep(1)
    th, x, _ = geo()
    check(abs(abs(th) - 90) < 0.1 and abs(x - expected(th)) < 0.05 and not unheld(), f"90 typed: θ {th:.2f}°, the slider {x:.3f} mm, the formula {expected(th):.3f}")
    d.save_screenshot(f"{OUT}/mouse_mechanism_90.png")
    press(d.find_elements(By.CSS_SELECTOR, ".mc-row")[k].find_element(By.CSS_SELECTOR, "[data-mcplay]"))
    xs, off, w = [], 0, 0
    for _ in range(14):
        th, x, _ = geo()
        xs.append(x)
        off = max(off, abs(x - expected(th)))
        w = max(w, worst())
        time.sleep(0.12)
    press(d.find_elements(By.CSS_SELECTOR, ".mc-row")[k].find_element(By.CSS_SELECTOR, "[data-mcplay]"))
    check(max(xs) - min(xs) > 10 and off < 0.05 and w < 0.05, f"▶ plays: the slider {min(xs):.1f} … {max(xs):.1f} mm, off the formula {off:.4f} mm at most, the joints' worst miss {w:.4f} mm")


try:
    build()
    pivots()
    k0 = clicks[0]
    helper()
    clicks[0] = k0  # (the helper tried and undone: the build by hand goes on)
    close_loop()
    line()
    check(not hint(), f"the mechanism complete: no 'missing joint' line {hint()}")
    d.save_screenshot(f"{OUT}/mouse_mechanism.png")
    drive()
    print(f"  clicks from the new assembly to a playing mechanism: {clicks[0]}")
    check(clicks[0] <= 32, f"{clicks[0]} clicks (≤ 32)")
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        bad.append("console errors")
    d.quit()
print("FAILED:" if bad else "ALL OK", bad if bad else "")
sys.exit(1 if bad else 0)
