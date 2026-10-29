"""Several sketch shapes at once, with REAL mouse input: a rectangle and a circle box-selected -> the short table
(◆ Make it one outline, ✥ Move…, ⧉ Copy, ⇋ Mirror, ✕ Delete all first, ⋯ Show all — the rest in sections) -> the rectangle's edge dragged: both go by
the same vector (one undo step) -> ✥ Move with dx 10 typed: all exactly 10 -> the rectangle alone: ⧈ Offset,
◆ One outline, ⁂ Pattern first; ⟳ Rotate 90: its corners turned about its centre (H / V swapped) -> ⤢ Scale 2: its sizes doubled; with
a locked width: refused, the toast names the lock -> ┄ construction toggles all -> ✕ Delete all, Ctrl+Z restores.
Then the short lists: two lines nearly parallel (the angle, ∥ first), two at an angle, a line and a circle (the
distance, ⌒ Tangent), two circles (the distance, ◎ / =), each at most 8 rows (the table's limit).

  PYTHONIOENCODING=utf-8 py tools/e2e_sketch_multiselect.py http://127.0.0.1:5199 <out dir>
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


def wait(script, t=30):
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
    ch, k = ActionChains(d), Keys.CONTROL if ctrl else Keys.ALT if alt else None
    (ch.key_down(k).click().key_up(k) if k else ch.click()).perform()
    time.sleep(0.4)


def tool(t):
    d.find_element(By.CSS_SELECTOR, f".m-cmdbar [data-a={t}], #modelViewport .view-actions [data-a={t}]").click()
    time.sleep(0.25)


def table():
    box = d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest")
    if not box:
        return None
    return [box[0].find_element(By.CSS_SELECTOR, ".vs-head b").text] + [b.text.replace("\n", " ") for b in box[0].find_elements(By.CSS_SELECTOR, ".vs-list button")]


def sections():
    return [s.text for s in d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-sec")]


def press(label):
    next(b for b in d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-list button") if label in b.text).click()
    time.sleep(0.9)


def keys(*k, ctrl=False):
    ch = ActionChains(d)
    if ctrl:
        ch.key_down(Keys.CONTROL)
    ch.send_keys(*k)
    if ctrl:
        ch.key_up(Keys.CONTROL)
    ch.perform()
    time.sleep(0.8)


def stop():
    """A line drawn: its length box (it comes a moment later) closed, the chain stopped."""
    time.sleep(0.8)
    for _ in range(2):
        if not js(f"return !!document.querySelector('.sk-input') || !!{SK}.chain"):
            break
        keys(Keys.ESCAPE)


def box(p, q):
    a, b = off(p), off(q)
    ActionChains(d, duration=40).move_to_element_with_offset(canvas(), *a).click_and_hold().move_by_offset((b[0] - a[0]) // 2, (b[1] - a[1]) // 2) \
        .move_to_element_with_offset(canvas(), *b).release().perform()
    time.sleep(0.7)
    return sorted(js(f"return ({SK}.picks || []).map(q => q.kind)"))


def pts():
    return js(f"return structuredClone({SK}.f.points)")


def rect():
    """The rectangle's corners (its group's points) in order, and its box [u0, v0, u1, v1]."""
    ps = js(f"const s = {SK}, g = s.f.entities.find(e => e.g)?.g; return s.f.entities.filter(e => e.g === g).map(e => s.P(e.a))")
    xs, ys = [p[0] for p in ps], [p[1] for p in ps]
    return ps, [min(xs), min(ys), max(xs), max(ys)]


def circle():
    return js(f"const s = {SK}, e = s.f.entities.find(e => e.t === 'circle'); return [s.P(e.c), e.r]")


def everything():
    """The box round all shapes (circles whole)."""
    b = js(f"""const s = {SK}, ps = [];
      for (const e of s.f.entities) {{ if (e.t === 'circle') {{ const c = s.P(e.c); ps.push([c[0] - e.r, c[1] - e.r], [c[0] + e.r, c[1] + e.r]); }} else ps.push(s.P(e.a), s.P(e.b)); }}
      return [Math.min(...ps.map(p => p[0])), Math.min(...ps.map(p => p[1])), Math.max(...ps.map(p => p[0])), Math.max(...ps.map(p => p[1]))]""")
    return box((b[0] - 5, b[1] - 5), (b[2] + 5, b[3] + 5))


def on_line(i, k=0.3):
    """A place k along the i-th line (not its middle: that picks the midpoint)."""
    return js(f"const s = {SK}, e = s.f.entities.filter(e => e.t === 'line')[arguments[0]], a = s.P(e.a), b = s.P(e.b); return [a[0] + (b[0] - a[0]) * arguments[1], a[1] + (b[1] - a[1]) * arguments[1]]", i, k)


def box_around(b, m=4):
    return box((b[0] - m, b[1] - m), (b[2] + m, b[3] + m))


def type_in(text):
    inp = d.find_element(By.CSS_SELECTOR, "#modelViewport .sk-xform input")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys(text)
    time.sleep(0.6)
    return inp


def toasts():
    return [t.text for t in d.find_elements(By.CSS_SELECTOR, "#toasts .toast")]


def short(tb, most=8):
    rows = [r for r in tb[1:] if not r.startswith(("⋯ Show all", "▴ Fewer"))]
    return len(rows) <= most


def show_all():
    """⋯ Show all (once opened it stays open for the session)."""
    b = d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest [data-sg-all]")
    if b:
        b[0].click()
        time.sleep(0.5)


try:
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "newModelBtn").click()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.6)
    click_uv((10, 10))
    click_uv((50, 30))
    tool("circle")
    click_uv((70, 20))
    click_uv((75, 20))
    tool("select")
    _, rb = rect()
    print("drawn: the rectangle", rb, "| the circle", circle())

    # --- a box round both: the short table, ⋯ Show all opens the rest in sections
    got = box((rb[0] - 6, rb[1] - 6), (82, rb[3] + 6))
    tb = table()
    print("both box-selected:", got, "->", tb)
    check("box picks 4 lines and the circle", got == ["circle", "line", "line", "line", "line"])
    check("title says 5 shapes", tb and tb[0] == "5 shapes")
    check("closed outlines (a rectangle round a circle): One outline, Move, Copy, Mirror, Delete all first, ⋯ Show all last",
          tb and [r.split(" ", 1)[1] for r in tb[1:6]] == ["Make it one outline", "Move…", "Copy", "Mirror", "Delete all"] and tb[-1].startswith("⋯ Show all") and short(tb))
    show_all()
    print("  ⋯ Show all:", sections(), table()[1:])
    check("Show all shows the Edit / Kind / Relations sections", [s.lower() for s in sections()] == ["edit", "kind", "relations"])
    check("…with Rotate, Scale, Pattern, Equal, Fix, construction", all(any(x in r for r in table()) for x in ["Rotate…", "Scale…", "Pattern", "Fix — all their points", "Make it construction"]))

    # --- the rectangle's edge dragged: everything picked goes by the same vector, one undo step
    p0, n0 = pts(), js(f"return {SK}.undo.length")
    grab = (rb[0] + (rb[2] - rb[0]) * 0.3, rb[1])
    ActionChains(d, duration=40).move_to_element_with_offset(canvas(), *off(grab)).click_and_hold().move_by_offset(20, -10).move_by_offset(20, -10).move_by_offset(10, -5).release().perform()
    time.sleep(1.0)
    p1 = pts()
    vecs = {k: (round(p1[k][0] - p0[k][0], 6), round(p1[k][1] - p0[k][1], 6)) for k in p0}
    print("dragged by its edge: the moves", vecs)
    check("all points moved by one vector (not zero)", len(set(vecs.values())) == 1 and list(vecs.values())[0] != (0, 0))
    check("one undo step", js(f"return {SK}.undo.length") == n0 + 1)
    check("still both picked", len(js(f"return {SK}.picks")) == 5)
    tb = table()
    check("the table stays", tb and tb[0] == "5 shapes")

    # --- ✥ Move: dx 10 typed
    p0 = pts()
    press("Move")
    type_in("10")
    keys(Keys.ENTER)
    p1 = pts()
    mv = {k: (round(p1[k][0] - p0[k][0], 6), round(p1[k][1] - p0[k][1], 6)) for k in p0}
    print("✥ Move dx 10:", set(mv.values()))
    check("✥ Move dx 10: all moved exactly 10", set(mv.values()) == {(10, 0)})
    check("its box closed, the table back", not d.find_elements(By.CSS_SELECTOR, ".sk-xform") and table())

    # --- the rectangle alone: a loop -> Offset, Pattern first; ⟳ Rotate 90
    ps0, rb = rect()
    got = box_around(rb)
    tb = table()
    print("the rectangle box-selected:", got, "->", tb)
    check("a loop: Offset, One outline, Pattern, Move, Delete all first",
          tb and [r.split(" ", 1)[1] for r in tb[1:6]] == ["Offset", "Make it one outline", "Pattern", "Move…", "Delete all"])
    # an unpicked shape (the circle) dragged: only it moves, the picks go
    (cc, cr), p0 = circle(), pts()
    ActionChains(d, duration=40).move_to_element_with_offset(canvas(), *off((cc[0] - cr, cc[1]))).click_and_hold().move_by_offset(-15, 0).move_by_offset(-15, 0).release().perform()
    time.sleep(1.0)
    p1 = pts()
    moved = [k for k in p0 if p0[k] != p1[k]]
    print("the unpicked circle dragged: moved", moved, "| picks", js(f"return {SK}.picks.length"))
    check("an unpicked shape dragged: only it moves, the picks go", moved == [js(f"return {SK}.f.entities.find(e => e.t === 'circle').c")] and js(f"return {SK}.picks.length") == 0)
    if moved:
        keys("z", ctrl=True)
    box_around(rb)
    n0 = js(f"return {SK}.undo.length")
    show_all()
    press("Rotate")
    print("  ⟳ box:", d.find_element(By.CSS_SELECTOR, ".sk-xform").text.replace("\n", " | "))
    time.sleep(0.6)
    keys(Keys.ENTER)
    ps1, rb1 = rect()
    cu, cv = (rb[0] + rb[2]) / 2, (rb[1] + rb[3]) / 2
    turned = [[round(cu - (p[1] - cv), 6), round(cv + (p[0] - cu), 6)] for p in ps0]
    print("⟳ Rotate 90: the box", rb, "->", rb1)
    check("⟳ Rotate 90: each corner turned about the centre", all(math.hypot(a[0] - b[0], a[1] - b[1]) < 1e-5 for a, b in zip(turned, ps1)))
    check("…H / V swapped (the sides stay square)", js(f"return {SK}.f.constraints.filter(k => k.t === 'h' || k.t === 'v').length") == 4)
    check("…one undo step", js(f"return {SK}.undo.length") == n0 + 1)
    keys("z", ctrl=True)
    check("Ctrl+Z: the corners back", all(math.hypot(a[0] - b[0], a[1] - b[1]) < 1e-6 for a, b in zip(rect()[0], ps0)))

    # --- ⤢ Scale 2 (nothing locked): sizes doubled
    _, rb = rect()
    box_around(rb)
    show_all()
    press("Scale")
    time.sleep(0.6)
    keys(Keys.ENTER)
    _, rb2 = rect()
    print("⤢ Scale 2:", rb, "->", rb2)
    check("⤢ Scale 2: width and height doubled", abs((rb2[2] - rb2[0]) - 2 * (rb[2] - rb[0])) < 1e-5 and abs((rb2[3] - rb2[1]) - 2 * (rb[3] - rb[1])) < 1e-5)
    keys("z", ctrl=True)

    # --- a locked width: ⤢ refused with a clear toast, nothing moved
    _, rb = rect()
    click_uv(((rb[0] + rb[2]) / 2 - 3, rb[1]))
    press("Its length")
    keys(Keys.ENTER)
    check("the width is locked", js(f"return {SK}.f.dims.some(x => x.t === 'len')"))
    ps0, rb = rect()
    box_around(rb)
    show_all()
    press("Scale")
    time.sleep(0.6)
    keys(Keys.ENTER)
    ts = toasts()
    print("⤢ Scale 2 with a locked width: toasts", ts)
    check("refused: the toast names the lock", any("Locked sizes hold the selection" in x for x in ts))
    check("…nothing moved", all(math.hypot(a[0] - b[0], a[1] - b[1]) < 1e-6 for a, b in zip(rect()[0], ps0)))
    keys(Keys.ESCAPE)
    check("Esc: the box gone", not d.find_elements(By.CSS_SELECTOR, ".sk-xform"))

    # --- ┄ construction for all, back; ✕ Delete all, Ctrl+Z
    everything()
    show_all()
    press("Make it construction")
    check("┄ all construction", js(f"return {SK}.f.entities.every(e => e.construction)"))
    keys("z", ctrl=True)
    check("Ctrl+Z: none construction", js(f"return {SK}.f.entities.every(e => !e.construction)"))
    everything()
    n = js(f"return {SK}.f.entities.length")
    press("Delete all")
    check("✕ Delete all", js(f"return {SK}.f.entities.length") == 0)
    keys("z", ctrl=True)
    check("Ctrl+Z: all back", js(f"return {SK}.f.entities.length") == n)
    everything()
    d.find_element(By.TAG_NAME, "body").send_keys(Keys.DELETE)
    time.sleep(0.6)

    # --- the short lists (⋯ Show all closed again)
    js("sessionStorage.removeItem('a3d.suggestAll')")
    tool("line")
    click_uv((0, 0 + 5))
    click_uv((40, 5))
    stop()
    tool("line")
    click_uv((0, 14), alt=True)  # (Alt: not snapped — 4° off level stays so)
    click_uv((40, 17), alt=True)
    stop()
    tool("select")
    click_uv(on_line(0))
    click_uv(on_line(1), ctrl=True)
    tb = table()
    print("two lines nearly parallel:", tb)
    check("nearly parallel: the angle first, ∥ next, Delete, short", tb and "angle" in tb[1] and "Parallel" in tb[2] and any("Delete" in r for r in tb) and short(tb))
    tool("line")
    click_uv((50, 5))
    click_uv((80, 5))
    stop()
    tool("line")
    click_uv((50, 12))
    click_uv((70, 32))
    stop()
    tool("select")
    click_uv(on_line(2))
    click_uv(on_line(3, 0.85), ctrl=True)  # (its length label sits nearer the middle)
    tb = table()
    print("two lines at 45°:", tb)
    d.save_screenshot(f"{OUT}/sketch_multiselect_45.png")
    check("at an angle: the angle first, one relation, short", tb and "angle" in tb[1] and short(tb))
    tool("circle")
    click_uv((20, 35))
    click_uv((25, 35))
    tool("circle")
    click_uv((40, 36))
    click_uv((45, 36))
    tool("select")
    click_uv(on_line(0))
    click_uv((25, 35), ctrl=True)
    tb = table()
    print("a line and a circle:", tb)
    check("line + circle: the distance, Tangent, short", tb and "centre to the line" in tb[1] and "Tangent" in tb[2] and short(tb))
    click_uv((25, 35))
    click_uv((45, 36), ctrl=True)
    tb = table()
    print("two circles:", tb)
    check("two circles: the distance, Equal / Concentric next, short", tb and "centres" in tb[1] and "Equal" in tb[2] and short(tb))
    d.save_screenshot(f"{OUT}/sketch_multiselect.png")
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    d.quit()
print("FAILED:" if FAILS else "all checks OK", FAILS if FAILS else "")
sys.exit(1 if FAILS or errs else 0)
