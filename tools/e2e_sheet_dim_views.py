"""One size, every view it can go in — the sheet's missing sizes in headless Edge, in Czech, with a real mouse: a block
60 × 40 × 30 with a hole and a step along its back (its floor at z 20), the sheet's front, top and right views -> the
front view's height deleted: the suggestions list it once, "↕ Výška 30 (2 pohledy)" -> hovering the row: 2 ghosts, in
the front and the right view -> a click on the right view's ghost: the height there, the row and the ghosts gone ->
↶ Undo: back to missing (one step) -> ↷ -> the dimension chosen: "⇄ Přesunout do jiného pohledu: Zepředu" (hover: its
ghost) moves it -> the step's floor (hidden in the front view, an edge in the right view): its best view the right one
-> the AI: get_sheet missing [{id, what, views}], sheet_edit add {missing, view: "Right"}.

  PYTHONIOENCODING=utf-8 py tools/e2e_sheet_dim_views.py http://127.0.0.1:5199 <out dir>
"""
import json
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
S = "window.__app.sheet"
H = "window.__app.agentHandlers"
fails = []


def check(name, ok, info=""):
    print(("OK  " if ok else "FAIL"), name, info)
    if not ok:
        fails.append(name)


def call(t, **a):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", t, a)


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.15)
    raise TimeoutError(script)


def rows():
    return [b.text.replace("\n", " ") for b in d.find_elements(By.CSS_SELECTOR, "#shViewport .view-suggest .vs-list button")]


def row_el(label):
    for b in d.find_elements(By.CSS_SELECTOR, "#shViewport .view-suggest .vs-list button"):
        if label in b.text:
            return b
    raise AssertionError(f"no row {label!r} in {rows()}")


def ghosts():
    return js("return [...document.querySelectorAll('#shViewport .sh-ghost')].map(g => g.dataset.gview)")


def missing():
    return js(f"return {S}.check().missing.map(m => ({{id: m.id, view: m.view, views: m.cands.map(c => c.view), size: m.size, key: m.key}}))")


def heights():
    return [m for m in missing() if m["id"] == "z:30"]


def click_empty():
    """A click on empty paper (bottom left, off the views): nothing chosen — the sheet's next steps in the table."""
    st = d.find_element(By.CSS_SELECTOR, "#shViewport .sh-stage")
    ActionChains(d).move_to_element_with_offset(st, -st.size["width"] // 2 + 30, st.size["height"] // 2 - 30).click().perform()
    time.sleep(0.5)


try:
    d.get(URL)
    js("localStorage.setItem('auto3d-lang', 'cs'); localStorage.removeItem('a3d.box.suggest'); localStorage.removeItem('a3d.leftDock'); sessionStorage.removeItem('a3d.suggestAll')")
    d.get(URL)
    wait("return !!window.__app")
    time.sleep(1)
    call("new_model", name="Kvádr")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=30)
    call("add_feature", type="hole", face="F2:end", points=[[-15, -8]], d=6)
    call("add_feature", type="sketch", plane="YZ", shapes=[{"rect": {"x": 30, "y": 20, "w": 11, "h": 11}}])
    print("the step:", call("add_feature", type="extrude", sketch="F4", op="cut", d=200, symmetric=True)[:90])
    wait(f"return !!{M}.result?.body && !{M}.inflight")
    js(f"{M}.renderProps()")
    time.sleep(0.4)
    d.find_element(By.CSS_SELECTOR, "#modelExport [data-a=newSheet]").click()
    wait(f"return !{S}.busy && !!{S}.svgEl", 90)
    time.sleep(0.5)
    check("front, top and right views on the sheet", {"Front", "Top", "Right"} <= set(js(f"return {S}.drawn()")), str(js(f"return {S}.drawn()")))
    check("the server lists where each place can be dimensioned", js(f"return !!{S}.geo.places?.z?.length"))

    # the front view's height deleted: missing, once, with its two views
    hid = js(f"return {S}.allDims().find(x => x.view === 'Front' && x.kind === 'linear' && x.a === 'box#y0' && x.b === 'box#y1')?.id")
    check("medium dimensions the height in the front view", bool(hid))
    js(f"{S}.remove(arguments[0])", hid)
    time.sleep(0.4)
    click_empty()
    hs = heights()
    print("missing:", missing())
    check("the height missing once, its views the front and the right", len(hs) == 1 and set(hs[0]["views"]) == {"Front", "Right"}, str(hs))
    rs = [r for r in rows() if "Výška 30" in r]
    print("rows:", rows())
    check("the table: “↕ Výška 30 (2 pohledy)” once", len(rs) == 1 and "(2 pohledy)" in rs[0] and rs[0].startswith("↕"), str(rs))
    check("the right view is offered (the left panel lists it)", any("Zprava" in el.text for el in d.find_elements(By.CSS_SELECTOR, "#shLeft .sh-mrow")),
          str([el.text for el in d.find_elements(By.CSS_SELECTOR, "#shLeft .sh-mrow")][:6]))

    # hovering the row: a ghost in each view
    ActionChains(d).move_to_element(row_el("Výška 30")).perform()
    time.sleep(0.3)
    g = ghosts()
    check("hovering the row: 2 ghosts, in the front and the right view", sorted(g) == ["Front", "Right"], str(g))
    check("a ghost is dashed, in the accent colour", js("const l = document.querySelector('#shViewport .sh-ghost line'); return !!l && l.getAttribute('stroke-dasharray') && l.getAttribute('stroke') === '#e8590c'"))
    d.save_screenshot(f"{OUT}/sheet_dim_views_hover.png")

    # a click on the right view's ghost: the height there
    grab = d.find_element(By.CSS_SELECTOR, "#shViewport .sh-ghost[data-gview=Right] .sh-grab")
    ActionChains(d).move_to_element(grab).click().perform()
    time.sleep(0.6)
    new = js(f"return {S}.d.user.map(x => ({{view: x.view, a: x.a, b: x.b, dir: x.dir}}))")
    print("added:", new)
    check("the ghost clicked: the height in the right view", any(x["view"] == "Right" and x["dir"] == "v" and x["b"] == "box#y1" for x in new), str(new))
    check("the row is gone", not [r for r in rows() if "Výška 30" in r] and not heights(), str(rows()))
    check("the ghosts are gone", ghosts() == [], str(ghosts()))
    d.save_screenshot(f"{OUT}/sheet_dim_views_added.png")

    # ↶ one step: missing again; ↷: there again
    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    time.sleep(0.5)
    check("↶ Undo: the height missing again (one step)", len(heights()) == 1 and not js(f"return {S}.d.user.length"), str(heights()))
    ActionChains(d).key_down(Keys.CONTROL).send_keys("y").key_up(Keys.CONTROL).perform()
    time.sleep(0.5)
    uid = js(f"return {S}.d.user.find(x => x.view === 'Right')?.id")
    check("↷ Redo: in the right view again", bool(uid))

    # the dimension chosen: ⇄ to another view
    grab = d.find_element(By.CSS_SELECTOR, f"#shViewport [data-dim='{uid}'] .sh-grab")
    ActionChains(d).move_to_element(grab).click().perform()
    time.sleep(0.5)
    print("its rows:", rows())
    mv = row_el("Přesunout do jiného pohledu")
    check("“⇄ Přesunout do jiného pohledu: Zepředu”", "Zepředu" in mv.text and mv.text.startswith("⇄"), mv.text)
    ActionChains(d).move_to_element(mv).perform()
    time.sleep(0.3)
    check("hovering it: its ghost in the front view", ghosts() == ["Front"], str(ghosts()))
    d.save_screenshot(f"{OUT}/sheet_dim_views_move.png")
    ActionChains(d).click(mv).perform()
    time.sleep(0.6)
    us = js(f"return {S}.d.user.map(x => x.view)")
    check("moved: the height in the front view, not in the right", us == ["Front"] and not heights(), str(us))
    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    time.sleep(0.5)
    check("↶ the move in one step", js(f"return {S}.d.user.map(x => x.view)") == ["Right"], str(js(f"return {S}.d.user.map(x => x.view)")))

    # the step's floor: hidden in the front view, an edge in the right view — offered best in the right one
    floor = js(f"return {S}.geo.places.z.find(p => Math.abs(p[0] - 20) < 0.01)?.[1]")
    print("z 20 is seen in:", floor)
    check("the step's floor: a hidden edge in the front view, a visible one in the right", {(v[0], v[3]) for v in floor or []} >= {("Front", "h"), ("Right", "e")}, str(floor))
    lv = js(f"return {S}.allDims().find(x => x.view === 'Front' && x.kind === 'linear' && x.dir === 'v' && x.b !== 'box#y1' && Math.abs({S}.value(x) - 20) < 0.01)?.id")
    if lv:
        js(f"{S}.remove(arguments[0])", lv)
        time.sleep(0.4)
    fl = [m for m in missing() if m["id"] == "z:20"]
    check("its size missing: the right view first", len(fl) == 1 and fl[0]["views"][0] == "Right" and "Front" in fl[0]["views"], str(fl))

    # the AI: its views, and one of them asked for
    g = json.loads(call("get_sheet"))
    mz = [m for m in g["check"]["missing"] if m["id"] == "z:20"]
    check("get_sheet: missing [{id, what, views (the best first)}]", len(mz) == 1 and mz[0]["views"][0] == "Right", str(g["check"]["missing"][:3]))
    r = json.loads(call("sheet_edit", add=[{"missing": "z:20", "view": "Front"}]))
    check("sheet_edit add {missing, view: Front}: added there", any(x["view"] == "Front" and abs(float(x["text"] or 0) - 20) < 0.01 for x in r["dims"] if not x["auto"]) and not [m for m in r["check"]["missing"] if m["id"] == "z:20"],
          str([x for x in r["dims"] if not x["auto"]]))
    js(f"{S}.remove(arguments[0])", js(f"return {S}.allDims().find(x => x.view === 'Top' && x.kind === 'linear' && x.dir === 'v' && x.a === 'box#y0' && x.b === 'box#y1')?.id"))
    time.sleep(0.4)
    bad = call("sheet_edit", add=[{"missing": "y:40", "view": "Front"}])
    check("sheet_edit add {missing, view} in a view that cannot show it: refused, its views said", bad.startswith("ERROR") and "Top" in bad and "Right" in bad, bad[:160])
    d.save_screenshot(f"{OUT}/sheet_dim_views_end.png")
    errs = [x["message"] for x in d.get_log("browser") if x["level"] == "SEVERE" and "favicon" not in x["message"]]
    check("no errors in the console", not errs, str(errs[:3]))
finally:
    d.quit()
print("FAILED:" if fails else "ALL OK", fails)
sys.exit(1 if fails else 0)
