"""Both side columns are docks, in headless Edge at 1280×800 with real mouse drags: a 3D model "Base" and an assembly
"Pair" -> an old left-only layout (a3d.leftDock v1) is read as it was (its order, its heights, the floating tree) and
the right panels come in the right column -> at first the right column holds the 3D model's ⚙ Properties (the part:
size, material …) and its own Export / 3D print widget -> the Properties header dragged into the left column: it is
there and works (the material changed -> applied) -> the project tree dragged into the right column -> the Export
widget dragged onto the view: it floats -> a reload: the same layout -> the tree dragged back left: the right column is
empty -> a thin strip, the 3D view wider -> the floating Export dropped on that strip: docked again -> the right
column's edge makes it wider (the view narrower) -> ↺ Default layout puts both columns back -> the assembly: its Parts
list and export widget on the right, dragged left it still exports -> 📄 Drawing sheet: the sheet's Title block widget
-> in Czech: the headers and the menu -> 1600×1000 too; no horizontal page scroll; no console errors.

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


def reload():
    time.sleep(4.5)  # (the project kept on the server: autosave)
    d.refresh()
    wait("return !!window.__app")
    no_versions()
    wait("return document.querySelector('.restore-bar [data-a=open]')", 15).click()
    wait(f"return {P}.parts.length === 2", 30)
    js(f"{P}.switchTo({P}.parts.find(p => p.name === 'Base').id)")
    time.sleep(1)
    settled()
    no_versions()


def menu(scope, w, label):
    head(scope, w).find_element(By.CSS_SELECTOR, ".lw-menu").click()
    time.sleep(0.3)
    next(b for b in d.find_elements(By.CSS_SELECTOR, ".lw-pop button") if label in b.text).click()
    time.sleep(0.6)


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
    reload()
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

    print("Czech")
    d.find_element(By.ID, "langBtn").click()
    time.sleep(0.5)
    heads = js("return [...document.querySelectorAll('#rightCol > .lw-widget')].filter(e => e.offsetHeight).sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top).map(e => e.querySelector('.lw-head b').textContent)")
    check(heads == ["Vlastnosti", "Export / 3D tisk"], f"the headers: {heads}")
    head("#rightCol", "props").find_element(By.CSS_SELECTOR, ".lw-menu").click()
    time.sleep(0.3)
    items = [b.text for b in d.find_elements(By.CSS_SELECTOR, ".lw-pop button")]
    check(items == ["📌 Ukotvit v levém panelu", "⧉ Plovoucí nad pohledem", "↺ Výchozí rozložení"], f"the menu: {items}")
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
