"""A suggestion whose inputs are picked already DOES its action (the owner: "Změřit mezi nimi" measures at once, not
just turns 📏 on), in the Czech UI, rows clicked with the mouse: a base and a plate held 5 mm above it ->
  two parts chosen -> 📏 Změřit mezi nimi: the clearance row (5) appears with no more clicks, 📏 stays on;
  two faces picked -> 📏 Změřit mezi nimi: their gap (5) at once;
  one face picked -> 📏 Měřit odtud: its row (the area) and the first pick waiting — one click on the plate's top: 10;
  a corner of a part -> 📏 Měřit odtud: waiting from that point;
  the 3D model: two spots picked (Ctrl+click) -> 📏 Vzdálenost: its row in 📏 Měření, the tool on;
  the 3D model: an edge picked -> 📏 Délka 80 mm (was a toast): its length row, 📏 on, the edge the first pick.

  PYTHONIOENCODING=utf-8 py tools/e2e_direct_suggest.py http://127.0.0.1:5199 <out dir>
"""
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
A = "window.__app.assembly"
M = "window.__app.modeler"
H = "window.__app.agentHandlers"
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


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def row(vp, label):
    """Click the Suggested table's row that starts with `label` (under ⋯ Ukázat vše too) -> clicked?"""
    sel = f"#{vp} .view-suggest [data-sg]"
    for _ in range(2):
        b = next((x for x in d.find_elements(By.CSS_SELECTOR, sel) if " ".join(x.text.split()).startswith(label) or label in x.text), None)
        if b:
            b.click()
            time.sleep(0.4)
            return True
        more = d.find_elements(By.CSS_SELECTOR, f"#{vp} .view-suggest [data-sg-all]")
        if not more:
            break
        more[0].click()
        time.sleep(0.3)
    print("   rows:", [" ".join(x.text.split()) for x in d.find_elements(By.CSS_SELECTOR, sel)])
    return False


def rows(ws):
    """📏 The measurements table's rows: [{kind, v, text}] (the doc's, as saved)."""
    doc = f"{A}.doc" if ws == "assembly" else f"{M}.part"
    return js(f"return ({doc}.measures || []).map(r => ({{ kind: r.kind, v: r.v, text: r.text || '' }}))")


def esc():
    ActionChains(d).send_keys(Keys.ESCAPE).perform()
    time.sleep(0.4)


def screen_of(inst, local):
    return js(f"""const a = {A}, it = a.inst(arguments[0]), v = a.view, V = v.camera.position.constructor;
      const M = new (v.camera.matrix.constructor)().fromArray(it.matrix), p = new V(...arguments[1]).applyMatrix4(M);
      const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", inst, local)


def click(inst, local):
    x, y = screen_of(inst, local)
    ActionChains(d, duration=30).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, "#asmViewport canvas"), x, y).perform()
    time.sleep(0.2)
    ActionChains(d).click().perform()
    time.sleep(0.5)


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.setItem('auto3d-lang', 'cs')")
    d.get(URL)
    wait("return !!window.__app && document.documentElement.lang === 'cs'")
    call("new_model", name="Base")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 80, "h": 60}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("new_model", name="Plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 30}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    time.sleep(1)
    call("new_assembly", name="Direct")
    call("insert_part", part="Base")
    call("insert_part", part="Plate")
    call("snap_faces", type="gap", gap=5, move={"part": "I2", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    js(f"{A}.view.setView('iso')")
    time.sleep(0.6)

    # 1 two parts chosen -> 📏 Změřit mezi nimi: the clearance at once, the tool stays on
    js(f"{A}.select(['I1', 'I2'])")
    time.sleep(0.5)
    check("two parts: 📏 Změřit mezi nimi in the table", row("asmViewport", "📏 Změřit mezi nimi"))
    t0 = time.time()
    try:
        wait(f"return ({A}.doc.measures || []).some(r => r.kind === 'clear' && r.v != null)", 15)
    except TimeoutError:
        pass
    got = rows("assembly")
    print("   after the row:", got, f"({time.time() - t0:.1f} s)")
    check("the clearance row with its value, no more clicks", len(got) == 1 and got[0]["kind"] == "clear" and abs((got[0]["v"] or -1) - 5) < 1e-3, got)
    check("📏 stays on", js(f"return !!{A}.measuring && {A}.ms.on"))
    check("its row in the 📏 table (the view shows it)", js("return document.querySelectorAll('[data-w=measure-assembly] .ms-row').length") == 1)
    d.save_screenshot(f"{OUT}/direct_1_parts.png")
    esc()
    check("Esc: 📏 off", not js(f"return !!{A}.measuring"))

    # 2 two faces picked (the plate's underside, the base's top) -> 📏 Změřit mezi nimi: their gap at once
    js(f"""const a = {A}; a.select(['I2', 'I1']); a.facePicks = [{{ inst: 'I2', face: a.worldFace('I2', 'F2:start') }}, {{ inst: 'I1', face: a.worldFace('I1', 'F2:end') }}];
      a.renderSuggest(); a.drawMarks();""")
    time.sleep(0.4)
    check("two faces: 📏 Změřit mezi nimi in the table", row("asmViewport", "📏 Změřit mezi nimi"))
    got = rows("assembly")
    check("two faces: the gap row (5) at once", len(got) == 2 and got[-1]["kind"] == "dist" and abs((got[-1]["v"] or -1) - 5) < 1e-3, got)
    check("📏 on after it", js(f"return !!{A}.measuring"))
    esc()

    # 3 one face picked -> 📏 Měřit odtud: its row and the first pick waiting; one click on the plate's top: 10
    js(f"""const a = {A}; a.select(['I1']); a.facePicks = [{{ inst: 'I1', face: a.worldFace('I1', 'F2:end') }}]; a.renderSuggest(); a.drawMarks();""")
    time.sleep(0.4)
    check("one face: 📏 Měřit odtud in the table", row("asmViewport", "📏 Měřit odtud"))
    got = rows("assembly")
    check("its row (the area 4800 mm²) and a pick waiting", got[-1]["kind"] == "area" and abs((got[-1]["v"] or -1) - 4800) < 1e-3 and js(f"return !!{A}.ms.pend"), got)
    click("I2", [10, 8, 5])  # the plate's top
    got = rows("assembly")
    check("one click more: the face to the plate's top, 10", got[-1]["kind"] == "dist" and abs((got[-1]["v"] or -1) - 10) < 1e-3, got)
    esc()

    # 4 a corner of a part -> 📏 Měřit odtud: that point waiting
    js(f"""const a = {A}, it = a.inst('I1'), V = a.view.camera.position.constructor, p = new V(80, 60, 10).applyMatrix4(new (a.view.camera.matrix.constructor)().fromArray(it.matrix));
      a.facePicks = []; a.snapPick = {{ inst: 'I1', point: p, snap: 'corner' }}; a.choose('I1'); a.renderSuggest();""")
    time.sleep(0.4)
    n0 = len(rows("assembly"))
    check("a corner: 📏 Měřit odtud in the table", row("asmViewport", "📏 Měřit odtud"))
    check("the corner waits as the first pick", js(f"return !!{A}.measuring && {A}.ms.pend?.ent.kind === 'point'") and len(rows("assembly")) == n0 + 1)
    esc()

    # 5 the 3D model: two spots picked -> 📏 Vzdálenost: its row in 📏 Měření, the tool on
    call("open_part", id="Base")
    wait(f"return window.__app.state.workspace === 'model' && {M}.result?.body")
    time.sleep(0.5)
    js(f"""const m = {M}, V = m.view.camera.position.constructor;
      m.picks = [{{ kind: 'point', point: new V(0, 0, 10), snap: 'corner' }}, {{ kind: 'point', point: new V(80, 0, 10), snap: 'corner' }}]; m.showPicks();""")
    time.sleep(0.4)
    check("model: two spots -> 📏 Vzdálenost 80 in the table", row("modelViewport", "📏 Vzdálenost"))
    got = rows("model")
    check("model: the distance row (80) at once", got and got[-1]["kind"] == "dist" and abs((got[-1]["v"] or -1) - 80) < 1e-3, got)
    check("model: 📏 on", js(f"return !!{M}.measuring"))
    d.save_screenshot(f"{OUT}/direct_5_model.png")
    esc()

    # 6 the 3D model: an edge picked -> 📏 Délka 80 mm: its row (L 80) in 📏 Měření at once, the tool on
    ei = js(f"""const m = {M}, b = m.result.body; return b.edges.findIndex((e, i) => {{ const s = m.edgeSize(i); return s && !s.round && Math.abs(s.L - 80) < 1e-6 && m.edgeRef(i); }})""")
    js(f"const m = {M}; m.picks = []; m.pickEdge(arguments[0], m.edgeRef(arguments[0]))", ei)
    time.sleep(0.4)
    n0 = len(rows("model"))
    check("model: an edge -> 📏 Délka 80 mm in the table", ei >= 0 and row("modelViewport", "📏 Délka 80"))
    got = rows("model")
    check("model: its length row (80) at once", len(got) == n0 + 1 and got[-1]["kind"] == "len" and abs((got[-1]["v"] or -1) - 80) < 1e-3, got)
    check("model: 📏 on, the edge waiting as the first pick", js(f"return !!{M}.measuring && {M}.ms.pend?.ent.kind === 'edge'"))
    esc()
except Exception as e:  # noqa: BLE001
    import traceback
    traceback.print_exc()
    FAILS.append(f"crashed: {e}")
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        FAILS.append("console errors")
    d.quit()
print(f"\n{COUNT['ok']} ok, {len(FAILS)} failed" + (f": {FAILS}" if FAILS else ""))
sys.exit(1 if FAILS else 0)
