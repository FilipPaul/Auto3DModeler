"""Widgets in the left column, in headless Edge at 1280×800 with real mouse drags: two parts "Base", "Lid" and an
assembly -> at first (a first install) the project tree is docked on top of the column, compact (as tall as its rows, at most ~8) -> ⋯ ☰
Back behind the button: ☰ opens it as before -> its header dragged into the left column docks it on top of the 3D
model's step tree (the same rows, icons, ⧉ / ✕; a double-click renames a part) -> it stays in the sketch, the
assembly and the 3D model again -> the splitter between the two widgets dragged: their heights change -> ▾ folds the
tree to its header -> the left column's edge makes it wider (the 3D view narrower) -> a face clicked: the suggestions
float in the view; their 📌 docks them under the panel (over their place in the column), nothing selected: a quiet
line -> the tree's header dragged onto the view: it floats there; two opacities — the panel (Ctrl+wheel, its ⋯
slider; 0 %: no background, border, header) and the content (Ctrl+Shift+wheel, its slider; the mouse over it: whole)
-> a reload: the same layout (docked suggestions, floating tree, its opacities, the heights, the width) -> the
floating tree dragged back into the column -> ⋯ ☰ Back behind the ☰ button -> ↺ Default layout -> in Czech: the
headers, the menu and the tooltips; no horizontal page scroll; no console errors.

  PYTHONIOENCODING=utf-8 py tools/e2e_left_pins.py http://127.0.0.1:5199 <out dir>
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
    """Press on `el` (`at` px from its left, away from its buttons; negative: from its right) and let go at the page
    point (x, y), in steps."""
    r = el.rect
    at = at if at >= 0 else r["width"] + at
    sx, sy = r["x"] + at, r["y"] + r["height"] / 2
    a = ActionChains(d, duration=40).move_to_element_with_offset(el, at - r["width"] / 2, 0).click_and_hold()
    for k in range(1, 6):
        a.move_by_offset(round((x - sx) / 5), round((y - sy) / 5))
    a.release().perform()
    time.sleep(0.5)


def state():
    return json.loads(js("return localStorage.getItem('a3d.leftDock') || '{}'"))


def tree_rows(scope="#leftCol"):
    return js("return [...document.querySelectorAll(arguments[0] + ' #projTree .pt-row')].map(r => r.querySelector('.pt-rname').textContent)", scope)


def settled():
    time.sleep(0.4)
    wait(f"return {M}.result?.body && !{M}.inflight")
    time.sleep(0.3)


def face_click():
    js(f"{M}.view.setView('iso')")
    time.sleep(0.4)
    o = js(f"""const v = {M}.view, [sx, sy] = v.toScreen(new (v.camera.position.constructor)(20, 15, 5)), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""")
    ActionChains(d, duration=30).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, "#modelViewport canvas"), *o).click().perform()
    time.sleep(0.7)


def looks(sel):
    """A widget's [background alpha, border alpha, header background alpha, its content's opacity]."""
    return js("""const w = document.querySelector(arguments[0]), a = (c) => { const m = c.match(/[\\d.]+/g).map(Number);
        return c.includes('/') || c.startsWith('rgba') ? m[m.length - 1] : 1; };
      const h = w.querySelector(':scope > .lw-head'), body = w.querySelector(':scope > :not(.lw-head):not(.fb-size)');
      return [a(getComputedStyle(w).backgroundColor), a(getComputedStyle(w).borderTopColor), a(getComputedStyle(h).backgroundColor), +getComputedStyle(body).opacity];""", sel)


def mouse_away():
    ActionChains(d).move_to_element(d.find_element(By.CSS_SELECTOR, ".brand")).perform()
    time.sleep(0.3)


def no_hscroll():
    return js("return document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1")



def no_versions():
    """The 🕘 Versions widgets (folded at the column's foot; e2e_versions tests them) out of the way: the layout as it
    is with the project tree, the panel and the suggestions."""
    js("return import('/js/leftdock.js').then(m => { for (const w of ['versions-model', 'versions-assembly']) m.leftDock.show(w, false); })")


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.clear(); localStorage.setItem('auto3d-lang', 'en')")
    d.get(URL)
    wait("return !!window.__app")
    no_versions()
    for name in ("Base", "Lid"):
        call("new_model", name=name)
        call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 30}}])
        call("add_feature", type="extrude", sketch="F1", d=5)
    call("new_assembly", name="Pair")
    call("insert_part", part="Base")
    call("insert_part", part="Lid")
    js(f"{P}.switchTo({P}.parts.find(p => p.name === 'Base').id)")
    time.sleep(1)
    settled()

    print("at first: the project tree docked on top")
    check(state() == {} and js("return document.querySelector('#projTree').closest('#leftCol') !== null"), "a first install: the tree in the column")
    order = js("return [...document.querySelectorAll('#leftCol > .lw-widget')].filter(e => e.offsetHeight).sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top).map(e => e.dataset.w)")
    check(order == ["project", "panel"], f"on top of the step tree: {order}")
    th, rh = rect("#leftCol .lw-widget[data-w=project]")["h"], rect("#leftCol #projTree .pt-row")["h"]
    rows_fit, rows_in = (th - 26 - 12) / rh, js("return document.querySelectorAll('#leftCol #projTree .pt-row').length")
    check(rows_in - 0.1 <= rows_fit <= 8.5 and js("const t = document.querySelector('#leftCol #projTree'); return t.scrollHeight <= t.clientHeight + 1"),
          f"compact: {th:.0f} px, room for {rows_fit:.1f} rows — as tall as its {rows_in} rows, no scrolling")
    check(rect("#modelLeft")["h"] > 300, f"the step tree keeps room: {rect('#modelLeft')['h']:.0f} px")
    shot("lp0_default")
    d.find_element(By.CSS_SELECTOR, "#partTabs .pt-all").click()
    time.sleep(0.3)
    check(rect("#leftCol .lw-widget[data-w=project]")["h"] < 32, "☰ folds the docked tree")
    d.find_element(By.CSS_SELECTOR, "#partTabs .pt-all").click()
    time.sleep(0.3)
    check(abs(rect("#leftCol .lw-widget[data-w=project]")["h"] - th) < 3, "☰ again unfolds it")
    d.find_element(By.CSS_SELECTOR, "#leftCol .lw-widget[data-w=project] .lw-menu").click()
    time.sleep(0.3)
    next(b for b in d.find_elements(By.CSS_SELECTOR, ".lw-pop button") if "☰" in b.text).click()
    time.sleep(0.4)

    print("☰ the popup, as before")
    check(js("return document.querySelector('#projTree').classList.contains('open') && document.querySelector('#projTree').parentElement.matches('main.layout')"), "☰ opens the tree over the left panel")
    check(bool(d.find_elements(By.CSS_SELECTOR, "#projTree .tr-head .tr-pin")), "its header has 📌")
    shot("lp1_popup")

    print("drag its header into the left column")
    col = rect("#leftCol")
    drag_to(d.find_element(By.CSS_SELECTOR, "#projTree .tr-head"), col["x"] + 100, col["y"] + 20)
    check(state().get("project") == "dock", f"docked (state: {state().get('project')})")
    check(js("return document.querySelector('#projTree').closest('.lw-widget')?.dataset.w === 'project'"), "the tree is a widget in the column")
    order = js("return [...document.querySelectorAll('#leftCol > .lw-widget')].filter(e => e.offsetHeight).sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top).map(e => e.dataset.w)")
    check(order == ["project", "panel"], f"the project on top, the step tree under it: {order}")
    check(sorted(tree_rows()) == ["Base", "Lid", "Pair"], f"the same rows: {tree_rows()}")
    check(bool(d.find_elements(By.CSS_SELECTOR, "#leftCol #projTree .pt-row .ico")) and bool(d.find_elements(By.CSS_SELECTOR, "#leftCol #projTree .pt-win"))
          and bool(d.find_elements(By.CSS_SELECTOR, "#leftCol #projTree .pt-del")), "icons, ⧉ and ✕ on the rows")
    check(no_hscroll(), "no horizontal page scroll")
    shot("lp2_docked_model")

    print("rename by a double-click")
    row = next(r for r in d.find_elements(By.CSS_SELECTOR, "#leftCol #projTree .pt-row") if r.text.startswith("Base"))
    ActionChains(d).double_click(row.find_element(By.CSS_SELECTOR, ".pt-rname")).perform()
    time.sleep(0.4)
    inp = d.find_elements(By.CSS_SELECTOR, "#projTree .tr-rename")
    check(bool(inp), "a name field")
    if inp:
        inp[0].send_keys("a")  # Ctrl+A
        inp[0].send_keys("Base plate\n")
        time.sleep(0.4)
    check("Base plate" in tree_rows(), f"renamed: {tree_rows()}")

    print("other workspaces")
    js(f"{M}.action('sketch')")
    time.sleep(0.4)
    js(f"{M}.action('datum-XY')")
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.6)
    check(js("return document.querySelector('#leftCol #projTree')?.offsetHeight > 60"), "the tree in the sketch")
    shot("lp3_sketch")
    js(f"{M}.action('cancelSketch')")
    time.sleep(0.5)
    js(f"{P}.switchTo({P}.parts.find(p => p.name === 'Pair').id)")
    wait("return document.body.classList.contains('ws-assembly')")
    time.sleep(1)
    check(js("return document.querySelector('#leftCol #projTree')?.offsetHeight > 60 && document.querySelector('#asmLeft').offsetHeight > 60"), "the tree and the assembly's tree in the assembly")
    shot("lp4_assembly")
    js(f"{P}.switchTo({P}.parts.find(p => p.name === 'Base plate').id)")
    wait("return document.body.classList.contains('ws-model')")
    settled()

    print("the splitter between them")
    h0 = rect("#leftCol .lw-widget[data-w=project]")["h"]
    sp = d.find_element(By.CSS_SELECTOR, "#leftCol .lw-split")
    ActionChains(d, duration=40).move_to_element(sp).click_and_hold().move_by_offset(0, 40).move_by_offset(0, 40).release().perform()
    time.sleep(0.3)
    h1 = rect("#leftCol .lw-widget[data-w=project]")["h"]
    check(abs(h1 - h0 - 80) < 6, f"the tree taller: {h0:.0f} -> {h1:.0f}")
    check(state()["ws"]["model"]["h"].get("project") == round(h1), f"remembered for the 3D model: {state()['ws']['model']['h']}")
    js(f"{P}.switchTo({P}.parts.find(p => p.name === 'Pair').id)")
    wait("return document.body.classList.contains('ws-assembly')")
    time.sleep(0.6)
    ha = rect("#leftCol .lw-widget[data-w=project]")["h"]
    check(abs(ha - h0) < 6, f"the assembly keeps its own height: {ha:.0f}")
    js(f"{P}.switchTo({P}.parts.find(p => p.name === 'Base plate').id)")
    wait("return document.body.classList.contains('ws-model')")
    settled()

    print("▾ folds")
    d.find_element(By.CSS_SELECTOR, "#leftCol .lw-widget[data-w=project] .lw-fold").click()
    time.sleep(0.3)
    hf = rect("#leftCol .lw-widget[data-w=project]")["h"]
    check(hf < 32, f"folded to its header: {hf:.0f}")
    d.find_element(By.CSS_SELECTOR, "#leftCol .lw-widget[data-w=project] .lw-fold").click()
    time.sleep(0.3)
    check(abs(rect("#leftCol .lw-widget[data-w=project]")["h"] - h1) < 6, "unfolded: its height back")

    print("the column's width")
    w0, c0 = rect("#leftCol")["w"], rect("#modelViewport canvas")["w"]
    sl = d.find_element(By.CSS_SELECTOR, ".splitter.split-left")
    ActionChains(d, duration=40).move_to_element(sl).click_and_hold().move_by_offset(30, 0).move_by_offset(30, 0).release().perform()
    time.sleep(0.6)
    w1, c1 = rect("#leftCol")["w"], rect("#modelViewport canvas")["w"]
    check(abs(w1 - w0 - 60) < 4 and abs(c0 - c1 - 60) < 4, f"wider column {w0:.0f} -> {w1:.0f}, the 3D view {c0:.0f} -> {c1:.0f}")
    check(abs(rect("#leftCol .lw-widget[data-w=project]")["w"] - w1) < 3, "the tree as wide")

    print("the suggestions docked")
    face_click()
    check(js("return !!document.querySelector('#modelViewport > .view-suggest:not(.docked)')"), "a face: the suggestions float in the view")
    shot("lp5_suggest_float")
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-pin").click()
    time.sleep(0.5)
    check(state().get("suggest") == "dock", "📌: docked")
    sg, ph = rect("#modelViewport .view-suggest"), rect("#leftCol .lw-widget[data-w=suggest]")
    check(sg and ph and abs(sg["x"] - ph["x"]) < 2 and abs(sg["w"] - ph["w"]) < 2 and sg["y"] >= ph["y"] and sg["b"] <= ph["b"] + 1,
          f"the table over its place in the column: {sg} / {ph}")
    order = js("return [...document.querySelectorAll('#leftCol > .lw-widget')].filter(e => e.offsetHeight).sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top).map(e => e.dataset.w)")
    check(order == ["project", "panel", "suggest"], f"under the panel: {order}")
    js("document.querySelector('#modelViewport .view-suggest .vs-list button').scrollIntoView()")
    shot("lp6_suggest_docked")
    js(f"{M}.dropSuggest()")
    time.sleep(0.4)
    check(js("return document.querySelector('#leftCol .lw-widget[data-w=suggest] .lw-empty-sg').checkVisibility()"), "nothing selected: a quiet line")

    print("the tree floats over the view")
    vp = rect("#modelViewport")
    drag_to(d.find_element(By.CSS_SELECTOR, "#leftCol .lw-widget[data-w=project] .lw-head"), vp["x"] + 300, vp["y"] + 200)
    check(state().get("project") == "float", "floating")
    fl = rect("#modelViewport > .lw-widget[data-w=project]")
    check(fl and abs(fl["x"] - (vp["x"] + 260)) < 30 and abs(fl["y"] - (vp["y"] + 190)) < 30, f"where it was let go: {fl}")
    check(sorted(tree_rows("#modelViewport")) == ["Base plate", "Lid", "Pair"], "its rows")
    head = d.find_element(By.CSS_SELECTOR, "#modelViewport > .lw-widget[data-w=project] .lw-head")
    FW = "#modelViewport > .lw-widget[data-w=project]"
    for _ in range(4):
        js("arguments[0].dispatchEvent(new WheelEvent('wheel', {deltaY: 100, ctrlKey: true, bubbles: true, cancelable: true}))", head)
    for _ in range(2):
        js("arguments[0].dispatchEvent(new WheelEvent('wheel', {deltaY: 100, ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true}))", head)
    mouse_away()
    lk = looks(FW)
    check(abs(lk[0] - 0.8) < 0.02 and abs(lk[2] - 0.8) < 0.02, f"Ctrl+wheel: the panel 80 % (background, header): {lk}")
    check(abs(lk[3] - 0.9) < 0.01, f"Ctrl+Shift+wheel: the content 90 %: {lk[3]}")
    tip = head.get_attribute("title")
    check("Ctrl+wheel" in tip and "Ctrl+Shift+wheel" in tip, "its tooltip names both")
    d.find_element(By.CSS_SELECTOR, f"{FW} .lw-menu").click()
    time.sleep(0.3)
    labels = [e.text for e in d.find_elements(By.CSS_SELECTOR, ".lw-pop .lw-opn")]
    check(labels == ["Panel", "Content"], f"two sliders: {labels}")
    for k, v in (("pop", 0), ("cop", 60)):
        js("arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('input'))", d.find_element(By.CSS_SELECTOR, f".lw-pop input[data-k={k}]"), v)
    time.sleep(0.2)
    shot("lp7_float_menu")
    d.find_element(By.TAG_NAME, "body").send_keys("")  # Esc closes the menu
    time.sleep(0.2)
    check(not d.find_elements(By.CSS_SELECTOR, ".lw-pop"), "Esc closes the menu")
    mouse_away()
    lk = looks(FW)
    check(lk[0] == 0 and lk[1] == 0 and lk[2] == 0, f"the panel 0 %: no background, border, header background: {lk}")
    check(abs(lk[3] - 0.6) < 0.01, f"the content 60 %: {lk[3]}")
    shot("lp7b_panel_0")
    ActionChains(d).move_to_element(d.find_element(By.CSS_SELECTOR, f"{FW} .pt-row")).perform()
    time.sleep(0.4)
    check(looks(FW)[3] == 1, "the mouse over it: the content whole")
    mouse_away()
    order = js("return [...document.querySelectorAll('#leftCol > .lw-widget')].filter(e => e.offsetHeight).map(e => e.dataset.w)")
    check(sorted(order) == ["panel", "suggest"], f"the column keeps the rest: {order}")
    face_click()
    shot("lp8_floating")
    js(f"{M}.dropSuggest()")
    layout = state()
    width = rect("#leftCol")["w"]

    print("a reload")
    time.sleep(4.5)  # (the project kept on the server: autosave)
    d.refresh()
    wait("return !!window.__app")
    no_versions()
    wait("return document.querySelector('.restore-bar [data-a=open]')", 15).click()
    wait(f"return {P}.parts.length === 3", 30)
    js(f"{P}.switchTo({P}.parts.find(p => p.name === 'Base plate').id)")
    wait("return document.body.classList.contains('ws-model')")
    settled()
    check(state() == layout, "the same state")
    fl2 = rect("#modelViewport > .lw-widget[data-w=project]")
    check(fl2 and abs(fl2["x"] - fl["x"]) < 3 and abs(fl2["y"] - fl["y"]) < 3, f"the tree floats where it was: {fl2}")
    mouse_away()
    lk = looks("#modelViewport > .lw-widget[data-w=project]")
    check(lk[0] == 0 and abs(lk[3] - 0.6) < 0.01, f"its opacities: the panel 0 %, the content 60 %: {lk}")
    check(abs(rect("#leftCol")["w"] - width) < 2, "the column's width")
    check(js("return !document.querySelector('#leftCol .lw-widget[data-w=suggest]').hidden"), "the suggestions docked")
    shot("lp9_reloaded")

    print("back into the column")
    col = rect("#leftCol")
    drag_to(d.find_element(By.CSS_SELECTOR, "#modelViewport > .lw-widget[data-w=project] .lw-head"), col["x"] + 100, col["y"] + 8)
    check(state().get("project") == "dock", "docked again")
    order = js("return [...document.querySelectorAll('#leftCol > .lw-widget')].filter(e => e.offsetHeight).sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top).map(e => e.dataset.w)")
    check(order == ["project", "panel", "suggest"], f"dropped on top: {order}")
    lk = looks("#leftCol .lw-widget[data-w=project]")
    check(lk[0] == 1 and lk[3] == 1, f"docked: not see-through: {lk}")

    print("☰ back behind the button")
    d.find_element(By.CSS_SELECTOR, "#leftCol .lw-widget[data-w=project] .lw-menu").click()
    time.sleep(0.3)
    next(b for b in d.find_elements(By.CSS_SELECTOR, ".lw-pop button") if "☰" in b.text).click()
    time.sleep(0.4)
    check(state().get("project") == "popup" and not js("return document.querySelector('#leftCol .lw-widget[data-w=project]').offsetHeight"), "unpinned: the column without it")
    check(js("return document.querySelector('#projTree').classList.contains('open') && document.querySelector('#projTree').parentElement.matches('main.layout')"), "…open as the ☰ popup")
    d.find_element(By.CSS_SELECTOR, "#projTree .tr-x").click()
    time.sleep(0.3)
    d.find_element(By.CSS_SELECTOR, "#partTabs .pt-all").click()
    time.sleep(0.3)
    check(js("return document.querySelector('#projTree').classList.contains('open')"), "☰ opens it again")
    d.find_element(By.CSS_SELECTOR, "#projTree .tr-x").click()

    print("↺ Default layout")
    d.find_element(By.CSS_SELECTOR, "#leftCol .lw-widget[data-w=suggest] .lw-menu").click()
    time.sleep(0.3)
    next(b for b in d.find_elements(By.CSS_SELECTOR, ".lw-pop button") if "↺" in b.text).click()
    time.sleep(0.5)
    s = state()
    check(s.get("project") == "dock" and s.get("suggest") == "float" and not s.get("ws"), f"the usual layout: {s}")
    check(abs(rect("#leftCol")["w"] - 340) < 2, f"the usual width: {rect('#leftCol')['w']}")
    order = js("return [...document.querySelectorAll('#leftCol > .lw-widget')].filter(e => e.offsetHeight).sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top).map(e => e.dataset.w)")
    check(order == ["project", "panel"], f"the tree docked on top, then the panel: {order}")
    check(not js("return [...document.body.style].some(p => /^--[pc]op-/.test(p))"), "no opacities left")

    print("the 3D model's panel floats too")
    d.find_element(By.CSS_SELECTOR, "#leftCol .lw-widget[data-w=project] .lw-menu").click()  # (the tree floats first: nothing left docked then)
    time.sleep(0.3)
    d.find_element(By.CSS_SELECTOR, ".lw-pop button[data-a=float]").click()
    time.sleep(0.4)
    vp = rect("#modelViewport")
    c0 = rect("#modelViewport canvas")["w"]
    drag_to(d.find_element(By.CSS_SELECTOR, "#leftCol .lw-widget[data-w=panel].model-only .lw-head"), vp["x"] + 200, vp["y"] + 150)
    time.sleep(0.4)
    check(js("return !!document.querySelector('#modelViewport > .lw-widget.floating #modelLeft')"), "the step tree floats over the view")
    check(js("return document.body.classList.contains('lw-empty')") and rect("#leftCol")["w"] < 8, "nothing docked: only a thin strip to drop on")
    c1 = rect("#modelViewport canvas")["w"]
    check(c1 > c0 + 300, f"the 3D view takes its room: {c0:.0f} -> {c1:.0f}")
    js(f"{P}.switchTo({P}.parts.find(p => p.name === 'Pair').id)")
    wait("return document.body.classList.contains('ws-assembly')")
    time.sleep(0.6)
    check(rect("#leftCol")["w"] > 300 and js("return document.querySelector('#asmLeft').closest('.lw-widget').parentElement.id") == "leftCol",
          "the assembly keeps its panel docked (per workspace)")
    js(f"{P}.switchTo({P}.parts.find(p => p.name === 'Base plate').id)")
    wait("return document.body.classList.contains('ws-model')")
    settled()
    shot("lp10_panel_float")
    lr = rect("main.layout")
    drag_to(d.find_element(By.CSS_SELECTOR, "#modelViewport > .lw-widget.floating[data-w=panel] .lw-head"), lr["x"] + 15, lr["y"] + 200, at=-70)  # (its right part: the floating tree overlaps its left)
    check(js("return document.querySelector('#modelLeft').closest('.lw-widget').parentElement.id") == "leftCol" and rect("#leftCol")["w"] > 300,
          "dropped at the left edge: docked again, the column back")
    d.find_element(By.CSS_SELECTOR, "#modelViewport > .lw-widget[data-w=project] .lw-menu").click()
    time.sleep(0.3)
    next(b for b in d.find_elements(By.CSS_SELECTOR, ".lw-pop button") if "↺" in b.text).click()
    time.sleep(0.5)

    print("Czech")
    d.find_element(By.ID, "langBtn").click()
    time.sleep(0.4)
    heads = js("return [...document.querySelectorAll('#leftCol > .lw-widget')].filter(e => e.offsetHeight).sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top).map(e => e.querySelector('.lw-head b').textContent)")
    check(heads == ["☰ Projekt", "3D model"], f"the headers: {heads}")
    d.find_element(By.CSS_SELECTOR, "#leftCol .lw-widget[data-w=project] .lw-menu").click()
    time.sleep(0.3)
    items = [b.text for b in d.find_elements(By.CSS_SELECTOR, ".lw-pop button")]
    check(items[-4:] == ["📌 Ukotvit v pravém panelu", "⧉ Plovoucí nad pohledem", "☰ Zpět pod tlačítko ☰", "↺ Výchozí rozložení"], f"the menu: {items}")
    tips = js("return [document.querySelector('#leftCol .lw-split')?.title, document.querySelector('#leftCol .lw-head').title, document.querySelector('.lw-fold').title]")
    check(all(t and "the" not in t for t in tips), f"the tooltips: {tips}")
    shot("lp11_cs")
    d.find_element(By.TAG_NAME, "body").send_keys("")
    js("localStorage.setItem('auto3d-lang', 'en')")
    check(no_hscroll(), "no horizontal page scroll")
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
