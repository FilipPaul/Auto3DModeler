"""Merging sketch shapes, with REAL mouse input in headless Edge:
1. Finger.dxf opened as a 2D drawing -> Use ▾ as a sketch: cleaned on the way (702 -> ~231 shapes, the toast says
   so) -> ⬆ Extrude 5: the volume = the drawing's closed area × 5.
2. Drive Gear.dxf as the old browser conversion made it (hundreds of shapes, as the owner's sketches are) -> a box
   over the gear: ⛓ Join into one curve is the first row, 🧹 Simplify the second -> Join: the teeth one spline (its
   points hidden), the area kept, in well under 2 s -> Ctrl+Z: all back.
3. A hand-drawn chain (lines and a tangent arc) -> box -> ⛓ Join: one spline; the tolerance typed 0.5 -> done again
   (one undo step), within 0.5 of the chain -> Ctrl+Z.
4. A rectangle with a circle in it -> box -> ◆ Make it one outline (in the short list): one block, its hole kept.
5. ⛓ Merge (the bar) with nothing picked -> 🧹 Simplify the whole sketch -> tolerance typed -> "N → M shapes".

  PYTHONIOENCODING=utf-8 py tools/e2e_sketch_merge.py http://127.0.0.1:5199 <out dir>
"""
import math
import os
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

URL, OUT = sys.argv[1], sys.argv[2]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAWINGS = os.path.join(ROOT, "samples", "ToImportToOurApp", "drawings")
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"
SK = f"{M}.sk"
FAILS = []


def check(name, ok):
    print(("  ok   " if ok else "  FAIL ") + name)
    if not ok:
        FAILS.append(name)


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#modelViewport canvas")


def off(uv):
    return js(f"""const m = {M}, v = m.view, f = m.frame(), [u, w] = arguments[0];
      const y = [f.n[1]*f.x[2]-f.n[2]*f.x[1], f.n[2]*f.x[0]-f.n[0]*f.x[2], f.n[0]*f.x[1]-f.n[1]*f.x[0]];
      const p = new (v.camera.position.constructor)(f.o[0] + u*f.x[0] + w*y[0], f.o[1] + u*f.x[1] + w*y[1], f.o[2] + u*f.x[2] + w*y[2]);
      const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(uv))


def click_uv(uv, ctrl=False, alt=False):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *off(uv)).perform()
    time.sleep(0.12)
    ch, k = ActionChains(d), Keys.CONTROL if ctrl else Keys.ALT if alt else None  # (Alt: no snapping)
    (ch.key_down(k).click().key_up(k) if k else ch.click()).perform()
    time.sleep(0.4)


def tool(t):
    d.find_element(By.CSS_SELECTOR, f".m-cmdbar [data-a={t}], #modelViewport .view-actions [data-a={t}]").click()
    time.sleep(0.3)


def table():
    box = d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest")
    if not box:
        return None
    return [box[0].find_element(By.CSS_SELECTOR, ".vs-head b").text] + [b.text.replace("\n", " ") for b in box[0].find_elements(By.CSS_SELECTOR, ".vs-list button")]


def press(label):
    next(b for b in d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-list button") if label in b.text).click()
    time.sleep(0.3)


def keys(*k, ctrl=False):
    ch = ActionChains(d)
    if ctrl:
        ch.key_down(Keys.CONTROL)
    ch.send_keys(*k)
    if ctrl:
        ch.key_up(Keys.CONTROL)
    ch.perform()
    time.sleep(0.8)


def box(p, q):
    a, b = off(p), off(q)
    ActionChains(d, duration=40).move_to_element_with_offset(canvas(), *a).click_and_hold().move_by_offset((b[0] - a[0]) // 2, (b[1] - a[1]) // 2) \
        .move_to_element_with_offset(canvas(), *b).release().perform()
    time.sleep(0.7)
    return js(f"return ({SK}.picks || []).length")


def kinds():
    return js(f"const c = {{}}; for (const e of {SK}.f.entities) c[e.t] = (c[e.t] || 0) + 1; return c")


def merged():
    """The ⛓ box's result line once the server answered."""
    return wait("const r = document.querySelector('#modelViewport .sk-merge [data-mk=res]'); return r && r.textContent !== '…' && r.textContent", 30)


def tol_in(text):
    inp = d.find_element(By.CSS_SELECTOR, "#modelViewport .sk-merge input")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys(text)
    time.sleep(0.2)
    return inp


def toasts():
    return [t.text for t in d.find_elements(By.CSS_SELECTOR, "#toasts .toast")]


def open_drawing(name):
    d.find_element(By.ID, "cadInput").send_keys(os.path.join(DRAWINGS, name))
    wait("return window.__app.state.workspace === 'drawing'")
    time.sleep(0.8)


def sketch_area():
    """The closed area of the sketch, as the server's clean-up measures it (a 'simplify' of nothing)."""
    return js(f"""const f = {SK} ? {SK}.f : {M}.part.features[0];
      return fetch('/api/model/sketch/clean', {{method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{op: 'simplify', ids: ['-none-'], sketch: {{points: f.points, entities: f.entities, constraints: f.constraints, dims: f.dims}}}})}})
        .then(r => r.json()).then(j => j.report.area[0])""")


try:
    d.get(URL)
    wait("return !!window.__app")

    # 1. Finger.dxf -> a clean sketch -> extruded
    open_drawing("Finger.dxf")
    n_dwg = js("return window.__app.drawing2d.d.entities.length")
    d.find_element(By.CSS_SELECTOR, "#dwgRight [data-use=sketch]").click()
    wait(f"return window.__app.state.workspace === 'model' && !{M}.inflight && {M}.part?.features?.length")
    time.sleep(0.6)
    said = " | ".join(toasts())
    f1 = js(f"return {M}.part.features[0]")
    n_sk, n_pts = len(f1["entities"]), len(f1["points"])
    print(f"Finger.dxf: {n_dwg} drawing shapes -> sketch {n_sk} shapes, {n_pts} points | toast: {said}")
    check("Finger: the sketch is far smaller than before (702 shapes)", n_sk < 260 and n_pts < 420)
    check("Finger: the toast says how much was cleaned up", "702 → " in said)
    js(f"{M}.action('extrude')")
    wait(f"return !!{M}.cmd")
    js(f"{M}.cmd.feature.d = 5")
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=ok]").click()
    wait(f"return !{M}.cmd && !{M}.inflight && {M}.result?.body", 90)
    vol = js(f"return {M}.result.body.volume")
    print("Finger extruded 5 mm:", round(vol, 2), "| expected", round(7186.806 * 5, 2))
    check("Finger: the profile closes and extrudes (volume = area × 5 within 0.5 %)", abs(vol - 7186.806 * 5) < 7186.806 * 5 * 0.005)
    d.save_screenshot(f"{OUT}/merge_finger.png")

    # 2. the gear as the old conversion made it: hundreds of shapes -> ⛓ Join
    open_drawing("Drive Gear.dxf")
    js("""return import('/js/drawing2d/editor.js').then(m => window.__app.project.newModel({features: [m.drawingToSketch(window.__app.drawing2d.d)]}, 'Gear (old)', 'none'))""")
    wait(f"return window.__app.state.workspace === 'model' && {M}.part?.features?.length")
    time.sleep(0.6)
    js(f"{M}.edit({M}.part.features[0].id)")  # (as a double-click on its step)
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.8)
    before = js(f"return {SK}.f.entities.length")
    a0 = sketch_area()
    tool("select")
    n = box((-30, -30), (30, 30))
    tb = table()
    print(f"gear (old conversion): {before} shapes, area {a0:.1f} | boxed {n} | table: {tb}")
    check("gear: ⛓ Join into one curve first, 🧹 Simplify second", tb and "Join into one curve" in tb[1] and "Simplify" in tb[2])
    d.save_screenshot(f"{OUT}/merge_gear_picked.png")
    t0 = time.time()
    press("Join into one curve")
    res = merged()
    took = time.time() - t0
    k = kinds()
    spl = js(f"return {SK}.f.entities.filter(e => e.t === 'spline').map(e => e.pts.length)")
    shown = js(f"return {SK}.hiddenPts().size")
    a1 = sketch_area()
    print(f"joined: {res} in {took:.2f} s | {k} | spline fit points {spl} (hidden {shown}) | area {a1:.1f}")
    check("gear: few shapes left (one spline round the teeth)", k.get("spline", 0) >= 1 and sum(k.values()) <= 20)
    check("gear: joined in under 2 s (the server's answer shown)", took < 2.5)
    check("gear: the joined curve's points are not shown", shown >= sum(spl) - 2 * len(spl))
    check("gear: the area kept (0.5 %)", abs(a1 - 1540.31) < 1540.31 * 0.005)
    keys(Keys.ENTER)
    time.sleep(0.5)
    d.save_screenshot(f"{OUT}/merge_gear_joined.png")
    keys("z", ctrl=True)
    check("gear: Ctrl+Z brings all the shapes back", js(f"return {SK}.f.entities.length") == before)

    # 5. ⛓ Merge (the bar), nothing picked -> 🧹 Simplify the whole sketch, a tolerance typed
    keys(Keys.ESCAPE)
    tool("merge")
    tb = table()
    print("⛓ Merge, nothing picked:", tb, "| hint", d.find_element(By.CSS_SELECTOR, ".m-hint").text[:60])
    check("⛓ Merge mode: the table offers 🧹 Simplify the whole sketch", tb and "Simplify the whole sketch" in tb[1])
    press("Simplify the whole sketch")
    res = merged()
    tol_in("0.02")
    time.sleep(1.2)
    res2 = merged()
    tol = js(f"return {SK}.mg?.tol")
    keys(Keys.ENTER)
    time.sleep(0.6)
    after = js(f"return {SK}.f.entities.length")
    print(f"simplified: {res} -> at 0.02 mm: {res2} (tol {tol}) | shapes now {after} | toast {toasts()[-1:]}")
    check("🧹 Simplify: the box says 'N → M shapes' and M is far smaller", "→" in res2 and after < before / 2)
    check("🧹 Simplify: the typed tolerance was used", tol == 0.02)
    check("🧹 Simplify: one undo step", (keys("z", ctrl=True) or True) and js(f"return {SK}.f.entities.length") == before)
    js(f"{M}.action('cancelSketch')")
    time.sleep(0.5)

    # 3. a hand-drawn chain: five lines and a tangent arc -> ⛓ Join (tolerance 0.5)
    d.find_element(By.ID, "newModelBtn").click()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.6)
    tool("line")
    chain = [(0, 0), (10, 1), (20, 4), (30, 9), (40, 16), (50, 25)]  # (turning 7 … 11° at each end: no corner)
    for i, p in enumerate(chain):
        click_uv(p, alt=i > 0)
    keys(Keys.ESCAPE)
    keys(Keys.ESCAPE)
    tool("arc")
    click_uv(chain[-1])
    click_uv((62, 33), alt=True)
    keys(Keys.ESCAPE)
    k0 = kinds()
    d.save_screenshot(f"{OUT}/merge_hand_drawn.png")
    print("drawn:", js(f"return {SK}.f.entities.map(e => [e.t, ...(e.t === 'arc' ? [e.a, e.b, e.c] : [e.a, e.b]).map(q => {SK}.P(q).map(v => +v.toFixed(2)))])"))
    drawn = js(f"const s = {SK}; return s.f.entities.map(e => e.t === 'arc' ? s.arcOf(e) : [s.P(e.a), s.P(e.b)])")
    tool("select")
    n = box((-25, -25), (85, 55))
    tb = table()
    print("hand-drawn chain:", k0, "| boxed", n, "| table", tb)
    check("hand-drawn: ⛓ Join first", tb and "Join into one curve" in tb[1])
    press("Join into one curve")
    merged()
    tol_in("0.5")
    keys(Keys.ENTER)
    time.sleep(0.8)
    k1 = kinds()
    dev = js(f"""const s = {SK}, e = s.f.entities.find(x => x.t === 'spline'); if (!e) return null;
      const ps = s.splineOf(e), seg = (p, a, b) => {{ const dx = b[0]-a[0], dy = b[1]-a[1], L = dx*dx+dy*dy || 1, t = Math.max(0, Math.min(1, ((p[0]-a[0])*dx+(p[1]-a[1])*dy)/L)); return Math.hypot(a[0]+t*dx-p[0], a[1]+t*dy-p[1]); }};
      return Math.max(...ps.map(p => Math.min(...arguments[0].flatMap(pl => pl.slice(1).map((q, i) => seg(p, pl[i], q))))))""", drawn)
    print("joined:", k1, "| farthest from the lines", dev, "| undo steps", js(f"return {SK}.undo.length"),
          js(f"const s = {SK}; return s.f.entities.map(e => [e.t, (e.pts || [e.a, e.b]).length, ...(e.pts ? [e.pts[0], e.pts[e.pts.length - 1]] : [e.a, e.b]).map(q => s.P(q).map(v => +v.toFixed(2)))])"),
          js(f"return JSON.stringify({SK}.f.dims) + JSON.stringify({SK}.f.constraints)"))
    check("hand-drawn: one spline (the lines and the arc joined)", k1 == {"spline": 1})
    check("hand-drawn: within the 0.5 mm typed", dev is not None and dev <= 0.5 + 0.02)
    d.save_screenshot(f"{OUT}/merge_hand.png")
    keys("z", ctrl=True)
    check("hand-drawn: Ctrl+Z gives the lines and the arc back", kinds() == k0)

    # 4. a rectangle with a hole -> ◆ Make it one outline
    keys(Keys.ESCAPE)
    tool("rect")
    click_uv((0, -40), alt=True)
    click_uv((40, -20), alt=True)
    tool("circle")
    click_uv((20, -30), alt=True)
    click_uv((24, -30), alt=True)
    tool("select")
    box((-15, -55), (55, -5))
    tb = table()
    print("rectangle + circle:", tb)
    check("closed outline picked: ◆ Make it one outline in the short list", tb and any("one outline" in r for r in tb[1:5]))
    press("Make it one outline")
    wait(f"return {SK}.f.entities.some(e => e.t === 'block')", 20)
    time.sleep(0.5)
    blk = js(f"return {SK}.f.entities.find(e => e.t === 'block')")
    print("outline:", kinds(), "| rings", [len(p) for p in blk["polys"]], "| at", blk["at"], "| size", blk["w0"], blk["h0"])
    check("◆ one block with its hole", [len(p) for p in blk["polys"]] == [2] and abs(blk["w0"] - 40) < 0.5 and abs(blk["h0"] - 20) < 0.5)
    d.save_screenshot(f"{OUT}/merge_outline.png")
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    d.quit()
print("FAILED:" if FAILS else "all checks OK", FAILS if FAILS else "")
sys.exit(1 if FAILS or errs else 0)
