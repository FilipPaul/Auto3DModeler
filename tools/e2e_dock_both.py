"""Both side columns are docks, in headless Edge at 1280×800 with real mouse drags: a 3D model "Base" and an assembly
"Pair" -> an old left-only layout (a3d.leftDock v1) is read as it was (its order, its heights, the floating tree) and
the right panels come in the right column -> at first the right column holds the 3D model's ⚙ Properties (the part:
size, material …) and its own Export / 3D print widget -> the Properties header dragged into the left column: it is
there and works (the material changed -> applied) -> the project tree dragged into the right column -> the Export
widget dragged onto the view: it floats -> a reload: the same layout -> the tree dragged back left: the right column is
empty -> a thin strip, the 3D view wider -> the floating Export dropped on that strip: docked again -> the right
column's edge makes it wider (the view narrower) -> ↺ Default layout puts both columns back -> the assembly: its Parts
list and export widget on the right, dragged left it still exports -> 📄 Drawing sheet: the sheet's Title block widget
-> ⋯ ↕ Automatic height on the project tree: 3 parts -> 12, it grows with them, no inner scrolling; the splitter dragged
turns it off -> ⋯ Rows 5: 5 rows + ⋯ More (7) -> all 12 + ▴ Fewer -> back to 5 -> the floating suggestions table's ⋯:
its Rows shared with its old "Top N" (8 -> 5: five rows, Top 5, a3d.suggestTop), its two opacities (panel 0 %,
content 60 %: computed styles) -> a reload keeps all of it -> ↺ Default layout puts it back -> in Czech: the headers and the menu -> 1600×1000 too; no horizontal page scroll; no console errors.

  PYTHONIOENCODING=utf-8 py tools/e2e_dock_both.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time
import traceback

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1280,800")
opts.add_argument("--lang=en-US")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
H = "window.__app.agentHandlers"
P = "window.__app.project"
M = "window.__app.modeler"
bad = []


def check(ok, what):
    print(("  ok   " if ok else "  FAIL ") + what)
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


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def shot(name):
    d.save_screenshot(f"{OUT}/{name}.png")


def rect(sel):
    return js("const e = document.querySelector(arguments[0]); if (!e) return null; const r = e.getBoundingClientRect(); return {x: r.left, y: r.top, w: r.width, h: r.height, b: r.bottom, r: r.right}", sel)


def drag_to(el, x, y, at=40):
    """Press on `el` (`at` px from its left, away from its buttons) and let go at the page point (x, y), in steps."""
    r = el.rect
    sx, sy = r["x"] + at, r["y"] + r["height"] / 2
    a = ActionChains(d, duration=40).move_to_element_with_offset(el, at - r["width"] / 2, 0).click_and_hold()
    for k in range(1, 6):
        a.move_by_offset(round((x - sx) / 5), round((y - sy) / 5))
    a.release().perform()
    time.sleep(0.6)


def head(scope, w):
    return js("return [...document.querySelectorAll(arguments[0] + ' .lw-widget[data-w=' + arguments[1] + '] > .lw-head')].find(e => e.offsetHeight)", scope, w)


def col(c):
    """The widgets shown in column `c` (leftCol / rightCol), top to bottom."""
    return js("""return [...document.querySelectorAll('#' + arguments[0] + ' > .lw-widget')].filter(e => e.offsetHeight)
      .sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top).map(e => e.dataset.w)""", c)


def no_versions():
    js("return import('/js/leftdock.js').then(m => { for (const w of ['versions-model', 'versions-assembly']) m.leftDock.show(w, false); })")


def settled():
    time.sleep(0.4)
    wait(f"return {M}.result?.body && !{M}.inflight")
    time.sleep(0.3)


def reload(n=2):
    time.sleep(4.5)  # (the project kept on the server: autosave)
    d.refresh()
    wait("return !!window.__app")
    no_versions()
    wait("return document.querySelector('.restore-bar [data-a=open]')", 15).click()
    wait(f"return {P}.parts.length === {n}", 30)
    js(f"{P}.switchTo({P}.parts.find(p => p.name === 'Base').id)")
    time.sleep(1)
    settled()
    no_versions()


def menu(scope, w, label):
    head(scope, w).find_element(By.CSS_SELECTOR, ".lw-menu").click()
    time.sleep(0.3)
    next(b for b in d.find_elements(By.CSS_SELECTOR, ".lw-pop button") if label in b.text).click()
    time.sleep(0.6)


def face_click():
    js(f"{M}.view.setView('iso')")
    time.sleep(0.4)
    o = js(f"""const v = {M}.view, [sx, sy] = v.toScreen(new (v.camera.position.constructor)(20, 15, 5)), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""")
    ActionChains(d, duration=30).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, "#modelViewport canvas"), *o).click().perform()
    time.sleep(0.8)


def looks(sel):
    """A box's [background alpha, header background alpha, its content's opacity]."""
    return js("""const w = document.querySelector(arguments[0]), a = (c) => { const m = c.match(/[\\d.]+/g).map(Number);
        return c.includes('/') || c.startsWith('rgba') ? m[m.length - 1] : 1; };
      const h = w.firstElementChild, body = w.querySelector('.vs-list');
      return [a(getComputedStyle(w).backgroundColor), a(getComputedStyle(h).backgroundColor), +getComputedStyle(body).opacity];""", sel)


def mouse_away():
    ActionChains(d).move_to_element(d.find_element(By.CSS_SELECTOR, ".brand")).perform()
    time.sleep(0.3)


def tree_shown():
    return js("return [...document.querySelectorAll('#leftCol #projTree .pt-row')].filter(r => r.offsetHeight).length")


def more_text():
    return js("return document.querySelector('#leftCol #projTree .lw-more')?.textContent || ''")


def no_hscroll():
    return js("return document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1")


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.clear(); localStorage.setItem('auto3d-lang', 'en')")
    d.get(URL)
    wait("return !!window.__app")
    no_versions()
    call("new_model", name="Base")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 30}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("new_assembly", name="Pair")
    call("insert_part", part="Base")
    js(f"{P}.switchTo({P}.parts.find(p => p.name === 'Base').id)")
    time.sleep(1)
    settled()

    print("an old left-only layout")
    js("localStorage.setItem('a3d.leftDock', JSON.stringify({project: 'dock', suggest: 'float', order: ['panel', 'project', 'suggest'], ws: {model: {h: {project: 150}}}}))")
    reload()
    check(col("leftCol") == ["panel", "project"], f"its order kept: {col('leftCol')}")
    check(abs(rect("#leftCol .lw-widget[data-w=project]")["h"] - 150) < 3, "its heights kept")
    check(col("rightCol") == ["props", "mexport"], f"the right panels in the right column: {col('rightCol')}")
    js("localStorage.removeItem('a3d.leftDock')")
    reload()

    print("at first")
    check(col("leftCol") == ["project", "panel"], f"left: {col('leftCol')}")
    check(col("rightCol") == ["props", "mexport"], f"right: Properties, Export / 3D print: {col('rightCol')}")
    check(js("return !!document.querySelector('#rightCol #modelRight select[data-k=material]') && !!document.querySelector('#rightCol #modelExport [data-a=toPrint]') && !document.querySelector('#modelRight [data-a=toPrint]')"),
          "the material in Properties, 🖨 / STL … in Export / 3D print")
    check(js(f"return {M}.$('[data-x=stl]') === document.querySelector('#modelExport [data-x=stl]')"), "the model still finds its export buttons (its $)")
    shot("db1_default")
    vp0 = rect("#modelViewport")

    print("Properties dragged into the left column")
    lc = rect("#leftCol")
    drag_to(head("#rightCol", "props"), lc["x"] + 100, lc["b"] - 20)
    check(col("leftCol") == ["project", "panel", "props"], f"under the step tree: {col('leftCol')}")
    check(col("rightCol") == ["mexport"], f"the right keeps Export: {col('rightCol')}")
    sel = d.find_element(By.CSS_SELECTOR, "#leftCol #modelRight select[data-k=material]")
    js("arguments[0].value = 'PETG'; arguments[0].dispatchEvent(new Event('change', {bubbles: true}))", sel)
    time.sleep(0.6)
    check(js(f"return {M}.part.material") == "PETG", "the material changed there: applied")
    shot("db2_props_left")

    print("the project tree dragged into the right column")
    rc = rect("#rightCol")
    drag_to(head("#leftCol", "project"), rc["x"] + 100, rc["y"] + 8)
    check(col("rightCol") == ["project", "mexport"], f"on top of the right column: {col('rightCol')}")
    check(js("return !!document.querySelector('#rightCol #projTree .pt-row')"), "its rows there")

    print("Export floated over the view")
    vp = rect("#modelViewport")
    drag_to(head("#rightCol", "mexport"), vp["x"] + vp["w"] / 2, vp["y"] + 160)
    check(js("return !!document.querySelector('#modelViewport > .lw-widget.floating[data-w=mexport] [data-a=toPrint]')"), "it floats in the view, its buttons in it")
    shot("db3_moved")

    print("a reload")
    reload(2)
    check(col("leftCol") == ["panel", "props"], f"left: {col('leftCol')}")
    check(col("rightCol") == ["project"], f"right: {col('rightCol')}")
    check(js("return !!document.querySelector('#modelViewport > .lw-widget.floating[data-w=mexport]:not([hidden])')"), "Export still floats")
    st = json.loads(js("return localStorage.getItem('a3d.leftDock')"))
    check(st.get("v") == 2 and st["ws"]["model"].get("props") == "dock" and st.get("project") == "right", f"remembered: {st.get('project')}, {st['ws']['model'].get('props')}")

    print("the right column emptied")
    lc = rect("#leftCol")
    drag_to(head("#rightCol", "project"), lc["x"] + 100, lc["y"] + 8)
    check(col("rightCol") == [] and js("return document.body.classList.contains('rw-empty')"), "nothing docked on the right")
    rc, vp1 = rect("#rightCol"), rect("#modelViewport")
    check(rc["w"] <= 8, f"a thin strip: {rc['w']} px")
    check(vp1["w"] > vp0["w"] + 250, f"the view wider: {vp0['w']} -> {vp1['w']}")
    shot("db4_right_empty")
    drag_to(d.find_element(By.CSS_SELECTOR, "#modelViewport > .lw-widget[data-w=mexport] > .lw-head"), rc["x"] - 10, rc["y"] + 200)
    check(col("rightCol") == ["mexport"] and not js("return document.body.classList.contains('rw-empty')"), f"dropped on the strip: docked there: {col('rightCol')}")

    print("the right column's edge")
    w0 = rect("#rightCol")["w"]
    sp = d.find_element(By.CSS_SELECTOR, ".splitter.split-right")
    ActionChains(d, duration=40).click_and_hold(sp).move_by_offset(-60, 0).release().perform()
    time.sleep(0.4)
    check(abs(rect("#rightCol")["w"] - (w0 + 60)) < 4 and rect("#modelViewport")["r"] <= rect("#rightCol")["x"] + 1, f"wider: {w0} -> {rect('#rightCol')['w']}, the view follows")

    print("↺ Default layout")
    menu("#rightCol", "mexport", "↺")
    check(col("leftCol") == ["project", "panel"] and col("rightCol") == ["props", "mexport"], f"both columns back: {col('leftCol')} | {col('rightCol')}")
    check(abs(rect("#rightCol")["w"] - 310) < 3, f"the usual width: {rect('#rightCol')['w']}")

    print("the assembly")
    js(f"{P}.switchTo({P}.parts.find(p => p.name === 'Pair').id)")
    wait("return document.body.classList.contains('ws-assembly')")
    time.sleep(1.2)
    no_versions()
    check(col("rightCol") == ["props", "abom"] and js("return !!document.querySelector('#rightCol #asmBom .as-bom') && !!document.querySelector('#rightCol #asmRight h2')"),
          f"Properties and Parts list and export: {col('rightCol')}")
    lc = rect("#leftCol")
    drag_to(head("#rightCol", "abom"), lc["x"] + 100, lc["b"] - 20)
    check("abom" in col("leftCol") and js("return !!document.querySelector('#leftCol #asmBom [data-x=step]')"), f"dragged left: {col('leftCol')}")
    check(js("return window.__app.assembly.$('.as-cogv') !== null || !window.__app.assembly.massProps().cog"), "the assembly still finds its CoG line (its $)")
    shot("db5_assembly")
    menu("#leftCol", "abom", "↺")
    check(col("rightCol") == ["props", "abom"], f"reset: {col('rightCol')}")

    print("a drawing sheet: its Title block widget")
    js(f"{P}.switchTo({P}.parts.find(p => p.name === 'Base').id)")
    time.sleep(1)
    settled()
    d.find_element(By.CSS_SELECTOR, "#modelExport [data-a=newSheet]").click()
    wait("return document.body.classList.contains('ws-sheet') && document.querySelector('#shTitle [data-text=title]')", 30)
    time.sleep(1)
    check(col("rightCol") == ["props", "stitle"], f"Properties and Title block: {col('rightCol')}")
    check(js("return !!document.querySelector('#shRight select[data-k=paper]') && !document.querySelector('#shRight [data-text=title]')"), "the paper in Properties, the texts in Title block")
    shot("db6_sheet")
    js(f"{P}.switchTo({P}.parts.find(p => p.name === 'Base').id)")
    time.sleep(1)
    settled()

    print("↕ Automatic height")
    menu("#leftCol", "project", "↕")
    time.sleep(0.8)
    st = json.loads(js("return localStorage.getItem('a3d.leftDock')"))
    h3 = rect("#leftCol .lw-widget[data-w=project]")["h"]
    check(st["ws"]["model"]["auto"].get("project") is True and tree_shown() == 3, f"on, 3 parts: {h3} px")
    for i in range(9):
        call("new_model", name=f"P{i + 1}")
    js(f"{P}.switchTo({P}.parts.find(p => p.name === 'Base').id)")
    time.sleep(1.5)
    settled()
    time.sleep(0.8)
    h12 = rect("#leftCol .lw-widget[data-w=project]")["h"]
    inner = js("return [...document.querySelectorAll('#leftCol .lw-widget[data-w=project], #leftCol .lw-widget[data-w=project] *')].filter(e => e.scrollHeight > e.clientHeight + 1 && /auto|scroll/.test(getComputedStyle(e).overflowY)).length")
    check(tree_shown() == 12 and h12 > h3 + 150 and inner == 0, f"12 parts: it grew {h3} -> {h12} px, no inner scrolling ({inner})")
    shot("db9_autosize")
    head("#leftCol", "project")  # (the splitter under it, dragged: a height of the user's own)
    sp = js("return [...document.querySelectorAll('#leftCol > .lw-split')].find(e => !e.hidden && e.dataset.a === 'project')")
    ActionChains(d, duration=40).click_and_hold(sp).move_by_offset(0, -60).release().perform()
    time.sleep(0.5)
    st = json.loads(js("return localStorage.getItem('a3d.leftDock')"))
    check(not st["ws"]["model"]["auto"].get("project"), "the splitter dragged: automatic height off")
    head("#leftCol", "project").find_element(By.CSS_SELECTOR, ".lw-menu").click()
    time.sleep(0.3)
    check("✓" not in next(b.text for b in d.find_elements(By.CSS_SELECTOR, ".lw-pop button") if "↕" in b.text), "the menu shows it off")

    print("Rows")
    inp = d.find_element(By.CSS_SELECTOR, ".lw-pop .lw-rows input")
    check(inp.get_attribute("value") == "", "the project tree: all rows at first")
    inp.send_keys("5\n")
    time.sleep(0.6)
    check(tree_shown() == 5 and more_text() == "⋯ More (7)", f"5 rows + {more_text()}")
    d.find_element(By.CSS_SELECTOR, "#leftCol #projTree .lw-more").click()
    time.sleep(0.5)
    check(tree_shown() == 12 and more_text() == "▴ Fewer", f"opened: {tree_shown()} rows + {more_text()}")
    d.find_element(By.CSS_SELECTOR, "#leftCol #projTree .lw-more").click()
    time.sleep(0.5)
    check(tree_shown() == 5, f"▴ Fewer: {tree_shown()} rows")

    print("the suggestions table's ⋯")
    face_click()
    wait("return document.querySelector('#modelViewport > .view-suggest:not(.docked) .vs-menu')", 10)
    n0 = js("return document.querySelectorAll('#modelViewport > .view-suggest [data-sg]').length")
    d.find_element(By.CSS_SELECTOR, "#modelViewport > .view-suggest .vs-menu").click()
    time.sleep(0.3)
    inp = d.find_element(By.CSS_SELECTOR, ".lw-pop .lw-rows input")
    check(inp.get_attribute("value") == "8" and n0 == 8, f"its Rows: the old Top 8 ({inp.get_attribute('value')}, {n0} rows)")
    js("for (const [k, v] of [['pop', 0], ['cop', 60]]) { const r = document.querySelector(`.lw-pop input[data-k=${k}]`); r.value = v; r.dispatchEvent(new Event('input', {bubbles: true})); }")
    inp.clear()
    inp.send_keys("5\n")
    time.sleep(0.6)
    rows5 = js("return document.querySelectorAll('#modelViewport > .view-suggest [data-sg]').length")
    top = js("return document.querySelector('#modelViewport > .view-suggest .vs-set').textContent")
    check(rows5 == 5 and top == "Top 5" and js("return localStorage.getItem('a3d.suggestTop')") == "5", f"Rows 5: {rows5} rows, {top}, the old setting too")
    mouse_away()
    lk = looks("#modelViewport > .view-suggest")
    check(lk[0] == 0 and lk[1] == 0 and abs(lk[2] - 0.6) < 0.01, f"its opacities: the panel 0 %, the content 60 %: {lk}")
    shot("db10_suggest")

    print("a reload keeps them")
    reload(12)
    check(tree_shown() == 5 and more_text() == "⋯ More (7)", f"the tree: 5 rows + {more_text()}")
    face_click()
    wait("return document.querySelector('#modelViewport > .view-suggest:not(.docked)')", 10)
    mouse_away()
    lk = looks("#modelViewport > .view-suggest")
    check(js("return document.querySelectorAll('#modelViewport > .view-suggest [data-sg]').length") == 5 and lk[0] == 0 and abs(lk[2] - 0.6) < 0.01, f"the table: 5 rows, its opacities {lk}")

    print("↺ Default layout puts them back")
    menu("#leftCol", "project", "↺")
    time.sleep(0.6)
    face_click()
    mouse_away()
    lk = looks("#modelViewport > .view-suggest")
    check(tree_shown() == 12 and not more_text(), f"the tree: all {tree_shown()} rows")
    check(js("return document.querySelectorAll('#modelViewport > .view-suggest [data-sg]').length") == 8 and lk[0] == 1 and lk[2] == 1, f"the table: 8 rows, opaque {lk}")

    print("✕ closes the suggestions table")
    sg_vis = lambda: js("return !!document.querySelector('#modelViewport > .view-suggest:not(.vs-closed)')?.offsetHeight")
    pill = lambda: js("return document.querySelector('#modelViewport > .vs-pill .vs-open')?.textContent.trim() || ''")
    d.find_element(By.CSS_SELECTOR, "#modelViewport > .view-suggest .vs-x").click()
    time.sleep(0.5)
    toasts = js("return [...document.querySelectorAll('.toast')].map(x => x.textContent).join(' | ')")
    p0 = pill()
    check(not sg_vis() and p0.startswith("💡 Suggestions (") and "no longer open by themselves" in toasts, f"closed: {p0!r}, told once")
    pr, fr, vr = rect("#modelViewport > .vs-pill"), rect("#modelViewport > .snap-filters"), rect("#modelViewport")
    check(pr["x"] - vr["x"] < 30 and pr["b"] <= fr["y"] + 1 and vr["b"] - pr["b"] < 90, f"the button bottom left, above the filter row: {pr}")
    shot("db11_closed")
    js(f"{M}.view.setView('front')")
    ActionChains(d, duration=30).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, "#modelViewport canvas"), -300, 180).click().perform()  # (nothing selected)
    time.sleep(0.7)
    p1 = pill()
    face_click()
    p2 = pill()
    check(not sg_vis() and p1 != p2, f"a selection does not open it, the count follows: {p1} -> {p2}")
    st = json.loads(call("gui_state", where="suggest"))
    check(st["suggestions"].get("closed") is True, f"gui_state: the table there, closed: {st['suggestions'].get('closed')}")
    d.find_element(By.CSS_SELECTOR, "#modelViewport > .vs-pill .vs-open").click()
    time.sleep(0.5)
    check(sg_vis() and not pill(), "the button opens it")
    d.find_element(By.CSS_SELECTOR, "#modelViewport > .view-suggest .vs-x").click()
    time.sleep(0.4)
    d.find_element(By.CSS_SELECTOR, "#modelViewport > .vs-pill .vs-auto input").click()
    time.sleep(0.5)
    check(sg_vis(), "Automatically on: open again")
    face_click()
    check(sg_vis(), "and it opens on a selection")
    d.find_element(By.CSS_SELECTOR, "#modelViewport > .view-suggest .vs-x").click()
    time.sleep(0.4)
    reload(12)
    face_click()
    check(not sg_vis() and pill().startswith("💡"), f"a reload keeps it closed: {pill()}")
    ActionChains(d).move_to_element(d.find_element(By.CSS_SELECTOR, ".brand")).click().perform()
    js("document.activeElement?.blur()")
    ActionChains(d).send_keys(" ").perform()
    time.sleep(0.5)
    check(sg_vis(), "Space opens it")
    ActionChains(d).send_keys(" ").perform()
    time.sleep(0.5)
    check(not sg_vis(), "Space closes it")

    print("Czech")
    d.find_element(By.ID, "langBtn").click()
    time.sleep(0.5)
    heads = js("return [...document.querySelectorAll('#rightCol > .lw-widget')].filter(e => e.offsetHeight).sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top).map(e => e.querySelector('.lw-head b').textContent)")
    check(heads == ["Vlastnosti", "Export / 3D tisk"], f"the headers: {heads}")
    head("#rightCol", "props").find_element(By.CSS_SELECTOR, ".lw-menu").click()
    time.sleep(0.3)
    items = [b.text for b in d.find_elements(By.CSS_SELECTOR, ".lw-pop button")]
    check(items == ["📌 Ukotvit v levém panelu", "⧉ Plovoucí nad pohledem", "↕ Automatická výška", "↺ Výchozí rozložení"], f"the menu: {items}")
    check(not d.find_elements(By.CSS_SELECTOR, ".lw-pop .lw-rows"), "a form: no Rows")
    d.find_element(By.TAG_NAME, "body").click()
    head("#leftCol", "project").find_element(By.CSS_SELECTOR, ".lw-menu").click()
    time.sleep(0.3)
    rl = js("return [document.querySelector('.lw-pop .lw-rows .lw-rown').textContent, document.querySelector('.lw-pop .lw-rows input').placeholder]")
    check(rl == ["Počet řádků", "vše"], f"Rows in Czech: {rl}")
    pl = js("return [document.querySelector('#modelViewport > .vs-pill .vs-open').textContent.trim(), document.querySelector('#modelViewport > .vs-pill .vs-auto').textContent.trim()]")
    check(pl[0].startswith("💡 Návrhy (") and pl[1] == "Automaticky", f"the closed suggestions' button in Czech: {pl}")
    d.find_element(By.TAG_NAME, "body").click()
    head("#rightCol", "props").find_element(By.CSS_SELECTOR, ".lw-menu").click()
    time.sleep(0.3)
    tips = js("return [[...document.querySelectorAll('#rightCol .lw-head')].find(e => e.offsetHeight).title, ...[...document.querySelectorAll('.lw-pop button')].map(b => b.title)]")
    check(all(t and " the " not in t for t in tips), f"the tooltips: {tips}")
    shot("db7_cs")
    d.find_element(By.TAG_NAME, "body").click()
    check(no_hscroll(), "no horizontal page scroll")

    print("1600×1000")
    d.set_window_size(1600, 1000)
    time.sleep(0.8)
    shot("db8_1600")
    check(no_hscroll(), "no horizontal page scroll")
    js("localStorage.setItem('auto3d-lang', 'en')")
except Exception:
    traceback.print_exc()
    bad.append("an exception")
finally:
    errs = [e["message"][:300] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs or "none")
    if errs:
        bad.append("console errors")
    d.quit()
    print("FAILED:" if bad else "ALL OK", *bad, sep="\n  ")
    sys.exit(1 if bad else 0)
