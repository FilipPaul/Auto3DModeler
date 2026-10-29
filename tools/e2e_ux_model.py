"""The 3D model's and the sketch's basic tasks done ONLY through the suggestions table (select something — or nothing —
then click a row), with REAL mouse input, in the Czech UI: each action must be among the top N rows (N: the table's
limit, default 8; not under ⋯ Ukázat vše) and must work.

  empty model: "Nový díl" -> ✏ Skica na rovině… -> the empty sketch (no table over it; ▭ is on): a 40 × 30 rectangle ->
  "Další krok": ✓ Hotovo first; ◯ Kruh -> two circles inside -> ⬚ Vybrat tvar -> a circle: Ø Její průměr (typed 10) ->
  a line clicked in its middle: ↔ Jeho délka (typed 40) -> two circles: = Stejně -> two lines: the distance first ->
  ✓ Hotovo — pak vysunout (the Extrude panel, OK) -> "Další krok" (nothing chosen, ≤ 6 rows, 📄 Výkres among them) -> an edge: ◜ Zaoblit
  tuto hranu first (the fillet opens with it chosen; OK, volume down) -> an edge: ◸ Zkosit tuto hranu -> the top face:
  ✏ Skica na této ploše -> ◯ (the bar: an empty sketch has no table) -> ✓ Hotovo -> a cut (OK) -> the top face:
  ◎ Díra sem (OK) -> "Další krok": ⁂ Pole z poslední díry first (OK, the hole repeated) -> the face: 📏 Změřit ji ->
  a step in the list: ✎ Upravit krok first, 🏷 Přejmenovat (typed), ↓ Posunout dolů, ✕ Smazat krok -> "Další krok"
  again. Console errors (and server errors): none.

  PYTHONIOENCODING=utf-8 py tools/e2e_ux_model.py http://127.0.0.1:5199 <out dir> [1280x800]
"""
import sys
import time
import traceback

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

URL, OUT = sys.argv[1], sys.argv[2]
W, H_ = (int(x) for x in (sys.argv[3] if len(sys.argv) > 3 else "1280x800").split("x"))
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument(f"--window-size={W},{H_}")
opts.add_argument("--lang=cs-CZ")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"
SK = f"{M}.sk"
FAILS = []
COUNT = {"ok": 0}


def check(what, ok, got=None):
    print(("  ok   " if ok else "  FAIL ") + what + ("" if ok or got is None else f" -> {got}"))
    if ok:
        COUNT["ok"] += 1
    else:
        FAILS.append(what)


def wait(script, t=40):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def settle():
    time.sleep(0.4)
    wait(f"return !{M}.inflight", 150)
    time.sleep(0.4)


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#modelViewport canvas")


def off_xyz(p):
    return js(f"""const v = {M}.view, [x, y, z] = arguments[0];
      const [sx, sy] = v.toScreen(new (v.camera.position.constructor)(x, y, z)), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(p))


def off_uv(uv):
    return js(f"""const m = {M}, v = m.view, f = m.frame(), [u, w] = arguments[0];
      const y = [f.n[1]*f.x[2]-f.n[2]*f.x[1], f.n[2]*f.x[0]-f.n[0]*f.x[2], f.n[0]*f.x[1]-f.n[1]*f.x[0]];
      const p = new (v.camera.position.constructor)(f.o[0] + u*f.x[0] + w*y[0], f.o[1] + u*f.x[1] + w*y[1], f.o[2] + u*f.x[2] + w*y[2]);
      const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(uv))


def free_spot(o):
    """Is the canvas spot (offset from its centre) clear of the floating boxes (the suggestions table, the filters)?"""
    return js("""const c = document.querySelector('#modelViewport canvas').getBoundingClientRect(), [dx, dy] = arguments[0];
      const x = Math.floor(c.left + c.width / 2) + dx, y = Math.floor(c.top + c.height / 2) + dy, el = document.elementFromPoint(x, y);
      return !!el && el.tagName === 'CANVAS';""", list(o))


def click(o, ctrl=False):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *o).perform()
    time.sleep(0.2)
    ch = ActionChains(d)
    if ctrl:
        ch.key_down(Keys.CONTROL).click().key_up(Keys.CONTROL)
    else:
        ch.click()
    ch.perform()
    time.sleep(0.5)


def click_uv(uv, ctrl=False):
    click(off_uv(uv), ctrl)


def click_xyz(ps, ctrl=False):
    """Click the first of the 3D spots that is clear of the floating boxes."""
    for p in ps:
        o = off_xyz(p)
        if free_spot(o):
            click(o, ctrl)
            return True
    print("   (no free spot among", ps, ")")
    return False


def table():
    box = d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest")
    if not box:
        return None
    return {"title": box[0].find_element(By.CSS_SELECTOR, ".vs-head b").text,
            "rows": [" ".join(b.text.split()) for b in box[0].find_elements(By.CSS_SELECTOR, ".vs-list button:not(.vs-more)")]}


def limit():
    return js("return parseInt(localStorage.getItem('a3d.suggestTop'), 10) || 8")


def suggest(task, label, clicks=None):
    """The row `label` is in the table's top rows: click it (a task done through the suggestions)."""
    tb = table()
    rows = (tb or {}).get("rows", [])
    k = next((i for i, r in enumerate(rows) if label in r), -1)
    check(f"{task}: “{label}” in the top {limit()} rows (row {k + 1})", 0 <= k < limit(), tb)
    if k < 0:
        raise RuntimeError(f"no row {label}")
    d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-list button:not(.vs-more)")[k].click()
    time.sleep(0.6)
    return k


def type_value(v):
    """A size label opened for typing: the value + Enter."""
    inp = wait("return document.activeElement && document.activeElement.tagName === 'INPUT' && document.activeElement")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys(str(v), Keys.ENTER)
    time.sleep(0.6)


def ok():
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=ok], #modelRight [data-a=ok]").click()
    settle()


def shot(name):
    d.save_screenshot(f"{OUT}/ux_{W}_{name}.png")


def volume():
    return js(f"return {M}.result?.body?.volume || 0")


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.setItem('auto3d-lang', 'cs'); localStorage.removeItem('a3d.suggestTop'); localStorage.removeItem('a3d.box.suggest'); sessionStorage.removeItem('a3d.suggestAll')")
    d.get(URL)
    wait("return !!window.__app && document.documentElement.lang === 'cs'")
    # (a server error: what it said, and what was open — for the report)
    js("window.__bad = []; const f0 = window.fetch; window.fetch = async (...a) => { const t0 = Date.now(), m = window.__app.modeler, was = JSON.stringify(m.cmd?.feature || null).slice(0, 300); const r = await f0(...a); if (r.status >= 500) r.clone().text().then((x) => window.__bad.push(String(a[0]) + ' ' + x.slice(0, 200) + ' | asked ' + ((Date.now() - t0) / 1000).toFixed(0) + ' s ago, while ' + was)); return r; }")
    d.find_element(By.ID, "newModelBtn").click()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.5)
    d.find_element(By.CSS_SELECTOR, "#modelViewport [data-a=cancelSketch]").click()
    settle()

    print("1. an empty model: the one obvious next step")
    tb = table()
    shot("01_empty")
    check("nothing chosen, an empty model: the table says “Nový díl”, ✏ Skica na rovině… first", tb and tb["title"] == "Nový díl" and "Skica na rovině" in tb["rows"][0], tb)
    suggest("start a sketch on a plane", "Skica na rovině")
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.4)

    print("2. the sketch: draw from the suggestions")
    check("an empty sketch: no table over the drawing (▭ Obdélník is on, the hint says where to click)", table() is None and js(f"return {SK}.tool") == "rect", table())
    click_uv((-20, -15))
    click_uv((20, 15))
    check("a rectangle drawn", js(f"return {SK}.f.entities.filter(e => e.t === 'line').length") == 4)
    shot("02_rect")
    tb = table()
    check("after drawing: ✓ Hotovo — pak vysunout first", tb and "Hotovo" in tb["rows"][0], tb)
    suggest("draw a circle", "Kruh")
    click_uv((-8, 0))
    click_uv((-5, 0))
    if any("Kruh" in r for r in (table() or {}).get("rows", [])):
        suggest("draw a second circle", "Kruh")
    click_uv((10, 6))
    click_uv((13, 6))
    check("two circles drawn", js(f"return {SK}.f.entities.filter(e => e.t === 'circle').length") == 2)

    print("3. dimension and relate through the suggestions")
    suggest("pick a shape", "Vybrat tvar")
    click_uv((-5, 0))  # the first circle's rim
    suggest("dimension a circle", "průměr")
    type_value(10)
    check("Ø10 locked", js(f"return {SK}.f.dims.some(x => x.t === 'dia' && Math.abs(x.v - 10) < 1e-6)"), js(f"return {SK}.f.dims"))
    click_uv((0, -15))  # the bottom line's middle
    suggest("dimension a line", "Jeho délka")
    type_value(40)
    check("the line's length 40 locked", js(f"return {SK}.f.dims.some(x => x.t === 'len' && Math.abs(x.v - 40) < 1e-6)"), js(f"return {SK}.f.dims"))
    click_uv((-5, 0))
    click_uv((13, 6), ctrl=True)
    shot("03_two_circles")
    suggest("make two circles equal", "Stejně")
    check("= equal made", js(f"return {SK}.f.constraints.some(k => k.t === 'eq')"))
    d.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    time.sleep(0.3)
    click_uv((-20, 11))  # the left line (its upper part: the table is bottom left)
    click_uv((20, -6), ctrl=True)  # the right line
    tb = table()
    check("two lines: the distance between them first", tb and "Vzdálenost" in tb["rows"][0], tb)
    d.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    time.sleep(0.4)

    print("4. finish -> extrude")
    suggest("finish the sketch", "Hotovo")
    wait(f"return {M}.cmd && {M}.cmd.feature.type === 'extrude'")
    shot("04_extrude")
    ok()
    v0 = volume()
    check("a solid", v0 > 1000, v0)

    print("5. nothing chosen: the next step")
    tb = table()
    shot("05_next")
    check("“Další krok”: ✏ a sketch on a face first, ◎ Díra, ◜ Zaoblit, 📄 Výkres among ≤ 6 rows",
          tb and tb["title"] == "Další krok" and "Skica" in tb["rows"][0] and any("Díra" in r for r in tb["rows"]) and any("Výkres" in r for r in tb["rows"]) and len(tb["rows"]) <= 6, tb)

    print("6. an edge: fillet / chamfer first")
    js(f"{M}.view.setView('iso')")
    time.sleep(0.4)
    v3 = volume()
    click_xyz([(-10, -15, 10), (-14, -15, 10), (10, -15, 10)])  # the top front edge, not its middle
    tb = table()
    shot("09_edge")
    check("an edge: ◜ Zaoblit tuto hranu, ◸ Zkosit tuto hranu in the first two rows",
          tb and "Zaoblit tuto hranu" in tb["rows"][0] and "Zkosit tuto hranu" in tb["rows"][1], tb)
    suggest("fillet an edge", "Zaoblit tuto hranu")
    wait(f"return {M}.cmd && {M}.cmd.feature.type === 'fillet'")
    check("the fillet opens with the edge chosen", js(f"return {M}.cmd.feature.edges.length") >= 1, js(f"return {M}.cmd.feature.edges"))
    ok()
    v4 = volume()
    check("the edge rounded (volume down)", v4 < v3, (v3, v4))
    click_xyz([(-20, -5, 10), (-20, 5, 10), (20, 5, 10)])  # the top left edge
    suggest("chamfer an edge", "Zkosit tuto hranu")
    wait(f"return {M}.cmd && {M}.cmd.feature.type === 'chamfer' && {M}.cmd.feature.edges.length")
    ok()
    check("chamfered (volume down)", volume() < v4, (v4, volume()))

    print("7. a sketch on the top face -> a cut")
    js(f"{M}.view.setView('iso')")
    time.sleep(0.4)
    click_xyz([(0, 10, 10), (-2, 11, 10), (3, 12, 10)])
    tb = table()
    check("a click on the top face: its table", tb and "Skica na této ploše" in " ".join(tb["rows"]), tb)
    suggest("sketch on a face", "Skica na této ploše")
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.4)
    d.find_element(By.CSS_SELECTOR, "#modelViewport .m-cmdbar [data-a=circle]").click()  # (an empty sketch: no table — the bar's ◯)
    time.sleep(0.3)
    click(off_xyz((-10, 5, 10)))
    click(off_xyz((-6, 5, 10)))
    suggest("finish the face sketch", "Hotovo")
    wait(f"return {M}.cmd && {M}.cmd.feature.type === 'extrude'")
    check("a sketch on the part: the extrude is a cut", js(f"return {M}.cmd.feature.op") == "cut")
    ok()
    v1 = volume()
    check("the cut took material away", v1 < v0 - 1, (v0, v1))

    print("8. a hole from the face's table")
    js(f"{M}.view.setView('iso')")
    time.sleep(0.4)
    click_xyz([(14, -9, 10), (15, -10, 10), (12, -11, 10)])
    suggest("a hole", "Díra sem")
    wait(f"return {M}.cmd && {M}.cmd.feature.type === 'hole' && {M}.cmd.feature.points.length")
    shot("07_hole")
    # each hole position's row fits the right panel: its ✕ in sight, not cut off (the panel's own width, 1280 × 800)
    fit = js("""const p = document.getElementById('modelRight').getBoundingClientRect();
      return [...document.querySelectorAll('#modelRight .mp-hole')].map((r) => { const x = r.querySelector('[data-del]').getBoundingClientRect(), b = r.getBoundingClientRect();
        return { x: [Math.round(x.left), Math.round(x.right)], row: Math.round(b.right), panel: [Math.round(p.left), Math.round(p.right)], wide: r.scrollWidth <= r.clientWidth + 1,
          hit: document.elementFromPoint(x.left + x.width / 2, x.top + x.height / 2) === r.querySelector('[data-del]') }; });""")
    check("the hole panel's rows fit: each position's ✕ in sight", bool(fit) and all(f["x"][1] <= f["panel"][1] - 4 and f["wide"] and f["hit"] for f in fit), fit)
    ok()
    v2 = volume()
    check("the hole made", v2 < v1 - 1 and js(f"return {M}.part.features.some(f => f.type === 'hole')"), (v1, v2))

    print("9. after a hole: ⁂ Pole first")
    tb = table()
    check("“Další krok” after a hole: ⁂ Pole z poslední díry first", tb and "Pole z poslední díry" in tb["rows"][0], tb)
    suggest("pattern the hole", "Pole z poslední díry")
    wait(f"return {M}.cmd && {M}.cmd.feature.type === 'pattern'")
    hole = js(f"return {M}.part.features.find(f => f.type === 'hole').id")
    check("the pattern repeats the hole", js(f"return {M}.cmd.feature.features") == [hole])
    ok()

    print("10. measure a face")
    click_xyz([(0, 10, 10), (-2, 11, 10), (3, 12, 10)])
    suggest("measure", "Změřit ji")
    check("the measure box says the face's area", "Plocha" in (js("return document.querySelector('#modelViewport .m-measure')?.textContent") or ""),
          js("return document.querySelector('#modelViewport .m-measure')?.textContent"))
    d.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    time.sleep(0.4)

    print("11. a step of the list: edit, rename, move, delete")
    row = lambda fid: d.find_element(By.CSS_SELECTOR, f'#modelLeft .mt-item[data-id="{fid}"] .mt-name')
    pat = js(f"return {M}.part.features.find(f => f.type === 'pattern').id")
    row(pat).click()
    time.sleep(0.5)
    tb = table()
    shot("11_step")
    check("a step chosen: its table — ✎ Upravit krok first, ✕ Smazat krok among the rows",
          tb and "Upravit krok" in tb["rows"][0] and any("Smazat krok" in r for r in tb["rows"]), tb)
    suggest("rename a step", "Přejmenovat")
    el = wait("return document.activeElement && document.activeElement.isContentEditable ? document.activeElement : document.querySelector('#modelLeft .mt-name input, #modelLeft input.rename')")
    el.send_keys(Keys.CONTROL, "a")
    el.send_keys("Řada děr", Keys.ENTER)
    time.sleep(0.6)
    check("renamed", js(f"return {M}.part.features.find(f => f.id === '{pat}').name") == "Řada děr", js(f"return {M}.part.features.find(f => f.id === '{pat}').name"))
    order0 = js(f"return {M}.part.features.map(f => f.id)")
    row(hole).click()
    time.sleep(0.5)
    suggest("move a step down", "Posunout dolů")
    settle()
    order1 = js(f"return {M}.part.features.map(f => f.id)")
    check("moved one place down (or refused with a reason)", order1 != order0 or bool(d.find_elements(By.CSS_SELECTOR, ".toast")), (order0, order1))
    row(pat).click()
    time.sleep(0.5)
    suggest("edit a step", "Upravit krok")
    check("✎ opens the step", js(f"return {M}.cmd && {M}.cmd.feature.id") == pat)
    d.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    settle()
    row(pat).click()
    time.sleep(0.5)
    n0 = js(f"return {M}.part.features.length")
    suggest("delete a step", "Smazat krok")
    settle()
    check("deleted", js(f"return {M}.part.features.length") == n0 - 1 and not js(f"return {M}.part.features.some(f => f.id === '{pat}')"))

    print("12. Esc: nothing chosen again")
    tb = table()
    check("after a delete: “Další krok”", tb and tb["title"] == "Další krok", tb)
    shot("12_end")
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    check("no console errors", not errs, (errs, js("return window.__bad")))
except Exception:  # (said, and counted as a failure — not swallowed by the exit below)
    traceback.print_exc()
    shot("error")
    print("state:", js(f"return [{M}.mode, {M}.cmd && {M}.cmd.feature.type, {M}.part.features.map(f => f.type)]"))
    print("console:", [e["message"][:300] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    FAILS.append("an exception")
finally:
    print(f"\n{COUNT['ok']} ok, {len(FAILS)} failed" + (": " + "; ".join(FAILS) if FAILS else ""))
    d.quit()
    sys.exit(1 if FAILS else 0)
