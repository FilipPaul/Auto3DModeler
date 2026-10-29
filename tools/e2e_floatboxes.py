"""Floating boxes over the 3D view (web/js/floatbox.js), with REAL mouse drags: the suggestions table, 🖨 Print check,
📏 Measure's result and the ✂ Section bar — each: dragged by its header (or ⠿ strip) it moves; the corner grip resizes
it; a drag far out stops at the view's edge (under the toolbar); after a reload it opens where it was left, at the size
it was given; a double-click on the header puts it back; a button inside it still works (the section's Y axis).
Every edge and corner resizes (the suggestions table): the left / top edge keeps the right / bottom one in place, each
zone shows its cursor, a click on a row near the edge still runs the row; the table's rows never show a scrollbar (also
with many rows, and docked in the left column) — a fade at the edge where rows are hidden.

  PYTHONIOENCODING=utf-8 py tools/e2e_floatboxes.py http://127.0.0.1:5199 <out dir>
"""
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.add_argument("--lang=en-US")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"
H = "window.__app.agentHandlers"
VP = "#modelViewport"
BOXES = {  # kind: (the box, its handle)
    "suggest": (".view-suggest", ".vs-head"),
    "printcheck": (".m-printcheck", ".mpc-head"),
    "measure": (".m-measure", ".fb-strip"),
    "section": (".m-section", ".fb-strip"),
}
fails = []


def check(ok, what):
    print(("  ok   " if ok else "  FAIL ") + what)
    if not ok:
        fails.append(what)


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.15)
    raise TimeoutError(script)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def settled():
    time.sleep(0.4)
    wait(f"return {M}.result?.body && !{M}.inflight")
    time.sleep(0.3)


def block():
    call("new_model", name="Floaty")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 30}}])
    call("add_feature", type="extrude", sketch="F1", d=8)
    settled()
    js(f"{M}.view.setView('iso')")
    time.sleep(0.5)


def face_click():
    """A real click on the block's top face."""
    o = js(f"""const v = {M}.view, [sx, sy] = v.toScreen(new (v.camera.position.constructor)(30, 15, 8)), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""")
    ActionChains(d, duration=30).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, f"{VP} canvas"), *o).click().perform()
    time.sleep(0.6)


def bar(a):
    d.find_element(By.CSS_SELECTOR, f"{VP} .m-cmdbar [data-a={a}]").click()
    time.sleep(0.6)


def open_box(kind):
    """Opens the box (the others closed first)."""
    js(f"if ({M}.printChk) {M}.togglePrintCheck(); if ({M}.measuring) {M}.toggleMeasure(); if ({M}.section) {M}.toggleSection();"
       f"document.querySelector('{VP} .view-suggest')?.remove()")
    time.sleep(0.3)
    if kind == "suggest":
        face_click()
    elif kind == "printcheck":
        bar("printcheck")
    elif kind == "measure":
        bar("measure")
        face_click()
    elif kind == "section":
        bar("section")
    return wait(f"return document.querySelector('{VP} > {BOXES[kind][0]}')", 10)


def rect(kind):
    """The box's place in the view and its size (px), and the view's size / where the toolbar ends."""
    return js(f"""const vp = document.querySelector('{VP}'), b = vp.querySelector(':scope > {BOXES[kind][0]}'); if (!b) return null;
      const r = b.getBoundingClientRect(), v = vp.getBoundingClientRect(), bar = vp.querySelector(':scope > .m-cmdbar');
      return {{x: Math.round(r.left - v.left), y: Math.round(r.top - v.top), w: Math.round(r.width), h: Math.round(r.height), vw: Math.round(v.width), vh: Math.round(v.height),
        barBottom: Math.round(bar.getBoundingClientRect().bottom - v.top)}};""")


def el(kind, part):
    return d.find_element(By.CSS_SELECTOR, f"{VP} > {BOXES[kind][0]} {part}" if part != "box" else f"{VP} > {BOXES[kind][0]}")


def drag(element, dx, dy, x=0, y=0):
    """A real drag from the element's middle by (dx, dy) — as far as the window goes (2 px inside it)."""
    r, (ww, wh) = element.rect, js("return [innerWidth, innerHeight]")
    cx, cy = r["x"] + r["width"] // 2 + x, r["y"] + r["height"] // 2 + y
    dx, dy = max(2 - cx, min(dx, ww - 3 - cx)), max(2 - cy, min(dy, wh - 3 - cy))
    ActionChains(d, duration=60).move_to_element_with_offset(element, x, y).click_and_hold().move_by_offset(dx // 2, dy // 2).move_by_offset(dx - dx // 2, dy - dy // 2).release().perform()
    time.sleep(0.4)


def handle(kind):
    return el(kind, BOXES[kind][1])


MOVE = {"suggest": (300, -150), "printcheck": (260, 120), "measure": (-280, -160), "section": (-200, -260)}
GROW = {"suggest": (70, 40), "printcheck": (60, 50), "measure": (80, 50), "section": (90, 10)}
kept = {}
try:
    d.get(URL)
    wait("return !!window.__app")
    js("for (const k of Object.keys(localStorage)) if (k.startsWith('a3d.box.')) localStorage.removeItem(k)")
    block()
    for kind in BOXES:
        print(f"{kind}:")
        open_box(kind)
        r0 = rect(kind)
        print("  at first:", r0)
        dx, dy = MOVE[kind]
        drag(handle(kind), dx, dy)
        r1 = rect(kind)
        check(abs(r1["x"] - r0["x"] - dx) <= 3 and abs(r1["y"] - r0["y"] - dy) <= 3, f"dragged by its header ({dx}, {dy}): moved {r1['x'] - r0['x']}, {r1['y'] - r0['y']}")
        check(abs(r1["w"] - r0["w"]) <= 1, f"same width after the move ({r0['w']} -> {r1['w']})")
        gx, gy = GROW[kind]
        drag(el(kind, "> .fb-size"), gx, gy)
        r2 = rect(kind)
        check(abs(r2["w"] - r1["w"] - gx) <= 3 and abs(r2["h"] - r1["h"] - gy) <= 3, f"the grip resized it by ({gx}, {gy}): {r2['w'] - r1['w']}, {r2['h'] - r1['h']}")
        check(abs(r2["x"] - r1["x"]) <= 1 and abs(r2["y"] - r1["y"]) <= 1, "its top left stays while resizing")
        check(bool(js(f"return localStorage.getItem('a3d.box.{kind}')")), f"remembered: {js(f'return localStorage.getItem(\"a3d.box.{kind}\")')}")
        kept[kind] = r2
        tip = js(f"return [document.querySelector('{VP} > {BOXES[kind][0]} .fb-handle')?.title, document.querySelector('{VP} > {BOXES[kind][0]} > .fb-size')?.title]")
        check(all(tip), f"tooltips: {tip}")
        d.find_element(By.CSS_SELECTOR, VP).screenshot(f"{OUT}/floatbox-{kind}-moved.png")
        if kind == "section":
            el(kind, "[data-ax=y]").click()
            time.sleep(0.5)
            check(js(f"return {M}.section?.axis") == "y" and bool(js(f"return document.querySelector('{VP} .m-section [data-ax=y].on')")), "a click on its Y button still works (the cut along Y)")
            r3 = rect(kind)
            check(abs(r3["x"] - r2["x"]) <= 1 and abs(r3["y"] - r2["y"]) <= 1 and abs(r3["w"] - r2["w"]) <= 1, f"re-rendered, it stays where it was: {r3['x']}, {r3['y']} {r3['w']}×{r3['h']}")
        if kind == "suggest":
            n0 = js(f"return {M}.view.camera.position.toArray().join()")
            drag(handle(kind), 0, 0)  # (a press on the header goes nowhere near the 3D view)
            check(js(f"return {M}.view.camera.position.toArray().join()") == n0, "a press on the header does not turn the view")

    print("reload:")
    d.refresh()
    wait("return !!window.__app")
    block()
    for kind in BOXES:
        open_box(kind)
        r = rect(kind)
        k = kept[kind]
        check(abs(r["x"] - k["x"]) <= 3 and abs(r["y"] - k["y"]) <= 3 and abs(r["w"] - k["w"]) <= 2 and abs(r["h"] - k["h"]) <= 2,
              f"{kind}: back where it was left after a reload ({r['x']}, {r['y']} {r['w']}×{r['h']} — was {k['x']}, {k['y']} {k['w']}×{k['h']})")
        if kind == "printcheck":
            d.find_element(By.CSS_SELECTOR, VP).screenshot(f"{OUT}/floatbox-after-reload.png")
        # out of the view: it stops at the edge, under the toolbar
        drag(handle(kind), -2500, -2500)
        r = rect(kind)
        check(r["x"] >= 0 and r["y"] >= r["barBottom"], f"{kind}: dragged far up-left it stays in the view, under the toolbar ({r['x']}, {r['y']}; the bar ends at {r['barBottom']})")
        drag(handle(kind), 2500, 2500)
        r = rect(kind)
        check(r["x"] + r["w"] <= r["vw"] and r["y"] + r["h"] <= r["vh"], f"{kind}: dragged far down-right it stays in the view ({r['x'] + r['w']} ≤ {r['vw']}, {r['y'] + r['h']} ≤ {r['vh']})")
        ActionChains(d).double_click(handle(kind)).perform()
        time.sleep(0.4)
        r = rect(kind)
        check(not js(f"return localStorage.getItem('a3d.box.{kind}')"), f"{kind}: a double-click on the header forgets it — back at {r['x']}, {r['y']} {r['w']}×{r['h']}")

    # the defaults again: the print check under the toolbar, the suggestions bottom left
    open_box("printcheck")
    r = rect("printcheck")
    check(r["y"] >= r["barBottom"] and r["x"] < 40, f"printcheck: at its default place under the toolbar ({r['x']}, {r['y']})")
    open_box("suggest")
    r = rect("suggest")
    check(r["x"] < 40 and r["y"] + r["h"] > r["vh"] - 120, f"suggest: at its default place bottom left ({r['x']}, {r['y'] + r['h']} of {r['vh']})")
    # a smaller window: a box at the right is pulled back in
    open_box("measure")
    drag(handle("measure"), 2500, 0)
    d.set_window_size(1250, 900)
    time.sleep(0.8)
    r = rect("measure")
    check(r["x"] + r["w"] <= r["vw"], f"measure: the window smaller — still in the view ({r['x'] + r['w']} ≤ {r['vw']})")
    d.find_element(By.CSS_SELECTOR, VP).screenshot(f"{OUT}/floatbox-small-window.png")
    # Czech tooltips (the language switch)
    d.find_element(By.ID, "langBtn").click()
    time.sleep(0.5)
    tip = js(f"return [document.querySelector('{VP} > .m-measure .fb-handle')?.title, document.querySelector('{VP} > .m-measure > .fb-size')?.title]")
    check(tip[0].startswith("Tažením přesunete") and tip[1].startswith("Tažením změníte velikost"), f"in Czech: {tip}")
    d.find_element(By.CSS_SELECTOR, VP).screenshot(f"{OUT}/floatbox-cs.png")
    d.find_element(By.ID, "langBtn").click()
    js("localStorage.removeItem('auto3d-lang')")

    print("edges (the suggestions table):")
    d.set_window_size(1600, 1000)
    time.sleep(0.6)
    js("localStorage.removeItem('a3d.box.suggest')")
    open_box("suggest")
    drag(handle("suggest"), 420, -120)  # (into the middle: room on every side)
    r0 = rect("suggest")
    print("  at:", r0)
    cur = js(f"""const b = document.querySelector('{VP} > .view-suggest'), r = b.getBoundingClientRect(), o = {{}};
      const at = {{n: [r.left + r.width / 2, r.top + 2], s: [r.left + r.width / 2, r.bottom - 2], w: [r.left + 2, r.top + r.height / 2], e: [r.right - 2, r.top + r.height / 2],
        nw: [r.left + 4, r.top + 4], ne: [r.right - 4, r.top + 4], sw: [r.left + 4, r.bottom - 4], se: [r.right - 4, r.bottom - 4]}};
      for (const [k, [x, y]] of Object.entries(at)) {{ const e = document.elementFromPoint(x, y); o[k] = [e?.dataset?.dir || e?.className, getComputedStyle(e).cursor]; }}
      return o;""")
    want = {"n": "ns-resize", "s": "ns-resize", "w": "ew-resize", "e": "ew-resize", "nw": "nwse-resize", "se": "nwse-resize", "ne": "nesw-resize", "sw": "nesw-resize"}
    for k, c in want.items():
        check(cur[k][0] == k and cur[k][1] == c, f"the {k} edge / corner: a zone there with the {c} cursor ({cur[k]})")
    inner = js(f"""const b = document.querySelector('{VP} > .view-suggest'), r = b.getBoundingClientRect(), h = b.querySelector('.vs-head').getBoundingClientRect();
      return [document.elementFromPoint(r.left + r.width / 2, h.top + h.height / 2)?.closest('.fb-handle, .fb-edge')?.className,
        document.elementFromPoint(r.left + 10, b.querySelector('.vs-list button').getBoundingClientRect().top + 8)?.closest('button, .fb-edge')?.className];""")
    check("fb-handle" in (inner[0] or "") and "fb-edge" not in (inner[1] or "") and inner[1] is not None, f"the header's middle still moves it, a row 10 px from the edge is the row ({inner})")
    drag(el("suggest", "> .fb-edge[data-dir=w]"), -60, 0)
    r1 = rect("suggest")
    check(abs(r1["w"] - r0["w"] - 60) <= 3 and abs((r1["x"] + r1["w"]) - (r0["x"] + r0["w"])) <= 1 and abs(r1["h"] - r0["h"]) <= 1,
          f"the left edge dragged 60 px left: {r0['w']} -> {r1['w']} wide, the right edge stays ({r0['x'] + r0['w']} -> {r1['x'] + r1['w']})")
    drag(el("suggest", "> .fb-edge[data-dir=n]"), 0, -50)
    r2 = rect("suggest")
    check(abs(r2["h"] - r1["h"] - 50) <= 3 and abs((r2["y"] + r2["h"]) - (r1["y"] + r1["h"])) <= 1 and abs(r2["w"] - r1["w"]) <= 1,
          f"the top edge dragged 50 px up: {r1['h']} -> {r2['h']} high, the bottom stays ({r1['y'] + r1['h']} -> {r2['y'] + r2['h']})")
    drag(el("suggest", "> .fb-edge[data-dir=e]"), 40, 0)
    r3 = rect("suggest")
    check(abs(r3["w"] - r2["w"] - 40) <= 3 and abs(r3["x"] - r2["x"]) <= 1, f"the right edge dragged 40 px: {r2['w']} -> {r3['w']}, the left stays")
    drag(el("suggest", "> .fb-edge[data-dir=ne]"), 30, -30)
    r4 = rect("suggest")
    check(abs(r4["w"] - r3["w"] - 30) <= 3 and abs(r4["h"] - r3["h"] - 30) <= 3 and abs(r4["x"] - r3["x"]) <= 1 and abs((r4["y"] + r4["h"]) - (r3["y"] + r3["h"])) <= 1,
          f"the top-right corner dragged (30, -30): {r3['w']}x{r3['h']} -> {r4['w']}x{r4['h']}, the bottom-left corner stays")
    drag(el("suggest", "> .fb-edge[data-dir=sw]"), 2000, 0)  # (smaller than its minimum: it stops there, the right edge stays)
    r5 = rect("suggest")
    check(r5["w"] == 170 and abs((r5["x"] + r5["w"]) - (r4["x"] + r4["w"])) <= 1, f"the bottom-left corner dragged far right: it stops at the minimum width ({r5['w']}), the right edge stays")
    drag(el("suggest", "> .fb-edge[data-dir=w]"), -3000, 0)
    r6 = rect("suggest")
    check(r6["x"] >= 0 and abs((r6["x"] + r6["w"]) - (r5["x"] + r5["w"])) <= 1, f"the left edge dragged far out: it stops at the view's edge ({r6['x']}), the right edge stays")
    sv = js("return JSON.parse(localStorage.getItem('a3d.box.suggest'))")
    check(abs(sv["w"] - r6["w"]) <= 1 and abs(sv["h"] - r6["h"]) <= 1, f"the new size remembered: {sv}")
    d.find_element(By.CSS_SELECTOR, VP).screenshot(f"{OUT}/floatbox-edges.png")
    # many rows: no scrollbar, a fade where rows are hidden, the wheel scrolls, a row near the edge runs
    js("localStorage.setItem('a3d.suggestTop', '30'); sessionStorage.setItem('a3d.suggestAll', '1')")
    d.execute_async_script(f"""const done = arguments[0];
      import('/js/suggest.js').then((m) => {{ window.__sgRan = null;
        m.showSuggest(document.querySelector('{VP}'), 'Many rows', Array.from({{length: 40}}, (_, i) => ({{icon: '•', label: 'Row ' + i, run: () => {{ window.__sgRan = i; }}}})));
        done(); }});""")
    time.sleep(0.4)
    L = f"document.querySelector('{VP} > .view-suggest .vs-list')"
    sc = js(f"const l = {L}; return [l.offsetWidth - l.clientWidth, l.scrollHeight > l.clientHeight + 20, l.className, l.scrollTop]")
    check(sc[0] == 0 and sc[1], f"40 rows in a low box: they overflow, no scrollbar (offsetWidth - clientWidth = {sc[0]})")
    check("fade-bottom" in sc[2] and "fade-top" not in sc[2], f"a fade at the bottom only (rows hidden below): {sc[2]}")
    d.find_element(By.CSS_SELECTOR, VP).screenshot(f"{OUT}/floatbox-fade-bottom.png")
    from selenium.webdriver.common.actions.wheel_input import ScrollOrigin
    ActionChains(d).scroll_from_origin(ScrollOrigin.from_element(d.find_element(By.CSS_SELECTOR, f"{VP} > .view-suggest .vs-list")), 0, 120).perform()
    time.sleep(0.5)
    sc = js(f"const l = {L}; return [l.scrollTop, l.className]")
    check(sc[0] > 0 and "fade-top" in sc[1] and "fade-bottom" in sc[1], f"the wheel scrolls the rows ({sc[0]} px), fades at both ends: {sc[1]}")
    d.find_element(By.CSS_SELECTOR, VP).screenshot(f"{OUT}/floatbox-fade-both.png")
    js(f"const l = {L}; l.scrollTop = l.scrollHeight")
    time.sleep(0.4)
    sc = js(f"return {L}.className")
    check("fade-top" in sc and "fade-bottom" not in sc, f"scrolled to the end: a fade at the top only: {sc}")
    row = js(f"""const l = {L}, b = l.getBoundingClientRect(); for (const x of l.querySelectorAll('button')) {{ const r = x.getBoundingClientRect(); if (r.top >= b.top + 25 && r.bottom <= b.bottom - 25) return [x.dataset.sg, r.left - document.querySelector('{VP} > .view-suggest').getBoundingClientRect().left]; }}""")
    target = d.find_element(By.CSS_SELECTOR, f"{VP} > .view-suggest .vs-list button[data-sg='{row[0]}']")
    ActionChains(d).move_to_element_with_offset(target, -target.rect["width"] // 2 + 2, 0).click().perform()
    time.sleep(0.3)
    check(js("return window.__sgRan") == int(row[0]), f"a click 2 px inside row {row[0]} (it starts {row[1]:.0f} px from the box's edge) runs it: {js('return window.__sgRan')}")
    # docked in the left column: no zones, no scrollbar
    d.find_element(By.CSS_SELECTOR, f"{VP} > .view-suggest .vs-pin").click()
    time.sleep(0.6)
    dk = js("""const b = document.querySelector('.view-suggest.docked'), l = b?.querySelector('.vs-list');
      return b && [l.offsetWidth - l.clientWidth, l.scrollHeight > l.clientHeight, [...b.querySelectorAll('.fb-edge')].filter((e) => e.offsetWidth).length, l.className];""")
    check(bool(dk) and dk[0] == 0 and dk[2] == 0, f"docked in the left column: no scrollbar ({dk and dk[0]}), no resize zones ({dk and dk[2]}), overflowing: {dk and dk[1]}, {dk and dk[3]}")
    d.save_screenshot(f"{OUT}/floatbox-docked.png")
    d.execute_async_script("const done = arguments[0]; import('/js/leftdock.js').then((m) => { m.leftDock.float('suggest', 300, 200); done(); })")
    time.sleep(0.6)
    fl = js(f"const b = document.querySelector('{VP} > .view-suggest'); return b && [b.classList.contains('docked'), [...b.querySelectorAll('.fb-edge')].filter((e) => e.offsetWidth).length]")
    check(bool(fl) and not fl[0] and fl[1] == 8, f"floating again: its 8 resize zones back ({fl})")
    js("localStorage.removeItem('a3d.suggestTop'); sessionStorage.removeItem('a3d.suggestAll')")
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    d.quit()
print("FAILED:" if fails or errs else "ALL OK", fails)
sys.exit(1 if fails or errs else 0)
