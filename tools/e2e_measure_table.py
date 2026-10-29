"""📏 The measurements table, with REAL mouse input in headless Edge (1280 × 800, Czech): a 40 × 20 × 10 block with a
Ø6 hole and a 15 mm high boss on its left half -> 📏 Měřit -> two corners: the distance (and ΔX ΔY ΔZ), an edge: its
length, the hole's rim: Ø6, the block's top and the boss' top: 5 apart (parallel faces), the boss' top and the front
face: 90° -> each a row that stays (the tool stays on); hovering a row lights its mark in the view; ✕ removes one;
12 rows look tidy (screenshot); Esc ends the tool and keeps the table; another part and back: still there; 🗑 clears
(↶ brings them back). The assembly: the same table; Díly (parts) -> the plate and the base: their clearance 5 (the
kernel's least distance).

  PYTHONIOENCODING=utf-8 py tools/e2e_measure_table.py http://127.0.0.1:5199 <out dir>
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
opts.add_argument("--window-size=1280,800")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
H = "window.__app.agentHandlers"
M = "window.__app.modeler"
A = "window.__app.assembly"
fails = []


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name, "" if ok else info)
    if not ok:
        fails.append(name)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(script)


def at(view, p, matrix_of=None):
    """A 3D point (of placed part matrix_of in an assembly) -> its offset from the canvas' middle (pixels)."""
    return js(f"""const v = {view}.view, V = v.camera.position.constructor, p = new V(...arguments[0]);
      if (arguments[1]) p.applyMatrix4(new (v.camera.matrix.constructor)().fromArray({view}.inst(arguments[1]).matrix));
      const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(p), matrix_of)


def click(view, sel, p, nudge=(0, 0), inst=None):
    o = at(view, p, inst)
    ActionChains(d, duration=30).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, sel), o[0] + nudge[0], o[1] + nudge[1]).perform()
    time.sleep(0.35)
    tip = js("return [...document.querySelectorAll('.ms-tip')].filter(e => !e.hidden).map(e => e.textContent)[0] || ''")
    ActionChains(d).click().perform()
    time.sleep(0.45)
    return tip


def click_empty(sel, view=M):
    """A click on empty space (beside the part, nothing over the canvas there): the next click starts anew."""
    el = d.find_element(By.CSS_SELECTOR, sel)
    o = js(f"""const v = {view}.view, c = v.renderer.domElement, r = c.getBoundingClientRect();
      for (let y = r.top + 60; y < r.bottom - 20; y += 23) for (let x = r.left + 20; x < r.right - 20; x += 31)
        if (document.elementFromPoint(x, y) === c && !v.pick(x, y) && !{view}.measurePick({{ clientX: x, clientY: y }}))
          return [Math.round(x - Math.floor(r.left + r.width / 2)), Math.round(y - Math.floor(r.top + r.height / 2))];
      return null;""")
    ActionChains(d, duration=30).move_to_element_with_offset(el, o[0], o[1]).perform()
    ActionChains(d).click().perform()
    time.sleep(0.3)


def rows(ws):
    return js(f"""return [...document.querySelectorAll('.lw-widget[data-w="measure-{ws}"] .ms-row')].map(r => ({{
      n: r.querySelector('.ms-n').textContent, i: r.querySelector('.ms-i').textContent, what: r.querySelector('.ms-what').textContent,
      v: r.querySelector('.ms-v').textContent, tail: r.querySelector('.ms-tail').textContent, id: +r.dataset.ms }}))""")


def num(s):
    s = s.replace("Ø", "").replace("R", "").replace("°", "").replace("mm²", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.setItem('auto3d-lang', 'cs')")
    d.refresh()
    wait("return !!window.__app")
    call("new_model", name="Block")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="hole", face="F2:end", points=[[10, 0]], d=6, through=True)
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 20, "h": 20}}])
    call("add_feature", type="extrude", sketch="F4", d=15)
    wait(f"return {M}.result?.body && !{M}.inflight && {M}.part.features.length === 5")
    js(f"{M}.view.setView('iso')")
    time.sleep(0.8)
    bb = js(f"return {M}.result.body.bbox")
    cyl = js(f"return {M}.result.body.faces.filter(f => f.type === 'cylinder').map(f => ({{o: f.axis.o, r: f.radius}}))")
    print("the block:", bb, "| hole:", cyl)
    hx, hy = cyl[0]["o"][0], cyl[0]["o"][1]
    cv = "#modelViewport canvas"

    print("1. 📏 Měřit: the empty table says what to do")
    d.find_element(By.CSS_SELECTOR, "#modelViewport .m-cmdbar [data-a=measure]").click()
    time.sleep(0.4)
    w = "#leftCol .lw-widget[data-w='measure-model']"
    check("the 📏 Měření widget shows", js(f"return !document.querySelector(\"{w}\")?.hidden"))
    empty = js(f"return document.querySelector(\"{w} .ms-empty\")?.textContent || ''")
    head = js(f"return document.querySelector(\"{w} .lw-head b\")?.textContent || ''")
    check("its empty state and header in Czech", "Zatím nic" in empty and "Měření" in head, (empty, head))
    print("   hint:", js("return document.querySelector('#modelViewport .m-hint').textContent"))

    print("2. point – point")
    t1 = click(M, cv, [20, 0, 10], (3, -2))
    t2 = click(M, cv, [40, 20, 10], (3, -2))
    r = rows("model")
    print("   hover labels:", t1, "|", t2, "| rows:", r)
    check("two corners: one row, the distance √(40² + 20²)", len(r) == 1 and abs(num(r[0]["v"]) - math.hypot(20, 20)) < 0.01, r)
    check("… with ΔX ΔY ΔZ in its muted tail", "ΔX 20" in r[0]["tail"] and "ΔY 20" in r[0]["tail"], r[0]["tail"] if r else None)

    print("3. an edge's length")
    t = click(M, cv, [26, 0, 10], (0, 1))
    r = rows("model")
    print("   hover:", t, "| row:", r[-1])
    check("the top front edge of the block's right half: L 20", len(r) == 2 and r[-1]["i"] == "L" and abs(num(r[-1]["v"]) - 20) < 0.01, r)
    check("… named in Czech (Hrana E…)", r[-1]["what"].startswith("Hrana E"), r[-1]["what"])
    click_empty(cv)

    print("4. the hole's Ø")
    t = click(M, cv, [hx, hy - 3, 10], (0, 1))
    r = rows("model")
    print("   hover:", t, "| row:", r[-1])
    check("the hole's rim: Ø6", len(r) == 3 and r[-1]["v"] == "Ø6", r)
    check("… named a hole (Díra E…)", r[-1]["what"].startswith("Díra"), r[-1]["what"])
    click_empty(cv)

    print("5. two parallel faces")
    click(M, cv, [36, 16, 10])
    click(M, cv, [6, 6, 15])
    r = rows("model")
    print("   row:", r[-1])
    check("the block's top and the boss' top: 5 apart", len(r) == 4 and abs(num(r[-1]["v"]) - 5) < 0.01 and "↔" in r[-1]["what"], r)

    print("6. the angle between two faces")
    click(M, cv, [5, 12, 15])
    click(M, cv, [30, 0, 5])
    r = rows("model")
    print("   row:", r[-1])
    check("the boss' top and the front face: 90°", len(r) == 5 and r[-1]["i"] == "∠" and r[-1]["v"] == "90°", r)

    print("7. hover a row: its mark lit; ✕ removes one")
    marks = js("return document.querySelectorAll('#modelViewport .ms-mark').length")
    check("every row has its mark in the view", marks == 5, marks)
    row = d.find_elements(By.CSS_SELECTOR, f"{w} .ms-row")[1]
    ActionChains(d).move_to_element(row).perform()
    time.sleep(0.3)
    lit = js("return [...document.querySelectorAll('#modelViewport .ms-mark.on')].map(e => e.textContent)")
    check("hovering row 2 lights its mark", len(lit) == 1 and lit[0].startswith("2"), lit)
    d.find_element(By.CSS_SELECTOR, "#modelViewport").screenshot(f"{OUT}/measure_hover.png")
    row.find_element(By.CSS_SELECTOR, ".ms-x").click()
    time.sleep(0.3)
    r = rows("model")
    check("✕: the edge's row gone, 4 left", len(r) == 4 and not any(x["i"] == "L" for x in r), r)
    row = d.find_elements(By.CSS_SELECTOR, f"{w} .ms-row")[0]
    row.click()
    time.sleep(0.3)
    sg = [" ".join(b.text.split()) for b in d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-list button")]
    check("a row clicked: copy / hide / delete suggested", any("Kopírovat hodnotu" in s for s in sg) and any("Smazat" in s for s in sg), sg)
    next(b for b in d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-list button") if "Kopírovat hodnotu" in b.text).click()
    time.sleep(0.2)
    check("📋 copies the value", abs(float(js(f"return {M}.ms.copied")) - math.hypot(20, 20)) < 0.01, js(f"return {M}.ms.copied"))

    print("8. twelve rows at 1280 × 800")
    pairs = [([40, 0, 10], [40, 20, 10]), ([0, 0, 15], [20, 0, 15]), ([20, 0, 15], [40, 0, 10]), ([0, 20, 15], [0, 0, 15]),
             ([20, 20, 10], [40, 20, 10]), ([0, 0, 15], [40, 20, 10]), ([20, 20, 15], [40, 0, 10]), ([20, 0, 10], [20, 20, 15])]
    for a, b in pairs:
        click(M, cv, a, (3, -2))
        click(M, cv, b, (3, -2))
    r = rows("model")
    print("   rows:", len(r), [x["what"] + " " + x["v"] for x in r])
    check("12 rows kept", len(r) == 12, len(r))
    fit = js(f"""const w = document.querySelector("{w}"), l = w.querySelector('.ms-list'), rs = [...w.querySelectorAll('.ms-row')];
      return {{ h: Math.round(rs[0].getBoundingClientRect().height), wide: rs.every(x => x.scrollWidth <= x.clientWidth + 1), scroll: l.scrollHeight > l.clientHeight }}""")
    check("rows ~22 px high, nothing sticks out", 20 <= fit["h"] <= 24 and fit["wide"], fit)
    d.save_screenshot(f"{OUT}/measure_table_12.png")
    d.find_element(By.CSS_SELECTOR, w).screenshot(f"{OUT}/measure_table_widget.png")

    print("9. Esc ends the tool, the table stays; another part and back: still there")
    d.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    time.sleep(0.3)
    check("Esc: the tool off", not js(f"return !!{M}.measuring"))
    check("… the table kept (12 rows, shown)", len(rows("model")) == 12 and js(f"return !document.querySelector(\"{w}\").hidden"))
    call("new_model", name="Other")
    time.sleep(1)
    check("another part: its own (no) table", js(f"return document.querySelector(\"{w}\").hidden"), rows("model"))
    call("open_part", id="Block")
    wait(f"return {M}.result?.body && !{M}.inflight")
    time.sleep(0.5)
    check("back on the block: its 12 rows again", len(rows("model")) == 12, len(rows("model")))

    print("10. 🗑 clears, ↶ brings them back")
    d.find_element(By.CSS_SELECTOR, f"{w} [data-msa=clear]").click()
    time.sleep(0.3)
    check("🗑: no rows", len(rows("model")) == 0)
    undo = [b for b in d.find_elements(By.CSS_SELECTOR, "#toasts .toast button") if "Zpět" in b.text]
    check("… a toast with ↶ Zpět", bool(undo))
    if undo:
        undo[-1].click()
        time.sleep(0.3)
        check("↶: the 12 rows back", len(rows("model")) == 12)

    print("11. the assembly: the clearance between two parts")
    call("new_model", name="Plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 30, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    time.sleep(1)
    call("new_assembly", name="Measured")
    call("insert_part", part="Block")
    call("insert_part", part="Plate")
    call("snap_faces", type="gap", gap=5, move={"part": "I2", "face": "F2:start"}, onto={"part": "I1", "face": "F5:end"})
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    js(f"{A}.sel = null; {A}.render(); {A}.view.setView('iso')")
    time.sleep(0.8)
    d.find_element(By.CSS_SELECTOR, "#asmViewport [data-a=measure]").click()
    time.sleep(0.4)
    wa = "#leftCol .lw-widget[data-w='measure-assembly']"
    check("the assembly's own table (empty)", js(f"return !document.querySelector(\"{wa}\").hidden") and not rows("assembly"))
    seg = [b.text for b in d.find_elements(By.CSS_SELECTOR, f"{wa} [data-msm]")]
    check("its chip: Prvky | Díly", seg == ["Prvky", "Díly"], seg)
    d.find_element(By.CSS_SELECTOR, f"{wa} [data-msm=parts]").click()
    time.sleep(0.2)
    cva = "#asmViewport canvas"
    click(A, cva, [5, 5, 5], (0, 0), "I2")  # the plate's top
    click(A, cva, [35, 15, 10], (0, 0), "I1")  # the block's right top
    wait(f"return {A}.ms.rows().some(r => r.kind === 'clear' && r.v != null) || {A}.ms.rows().some(r => (r.tail || '').startsWith('⚠'))", 60)
    time.sleep(0.3)
    r = rows("assembly")
    print("   rows:", r)
    check("Díly: the plate and the block: clearance 5", len(r) == 1 and r[0]["i"] == "⇹" and abs(num(r[0]["v"]) - 5) < 0.01, r)
    d.find_element(By.CSS_SELECTOR, f"{wa} [data-msm=items]").click()
    time.sleep(0.2)
    click(A, cva, [5, 5, 5], (0, 0), "I2")
    click(A, cva, [35, 15, 10], (0, 0), "I1")
    r = rows("assembly")
    top = js(f"const a = {A}, V = a.view.camera.position.constructor; return new V(5, 5, 5).applyMatrix4(new (a.view.camera.matrix.constructor)().fromArray(a.inst('I2').matrix)).z")
    check("Prvky: the plate's top and the block's top: parallel, apart as they are", len(r) == 2 and r[-1]["i"] == "⫽" and abs(num(r[-1]["v"]) - (top - 10)) < 0.01, (r, top))
    d.save_screenshot(f"{OUT}/measure_assembly.png")
    d.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    time.sleep(0.3)
    check("Esc in the assembly: the table kept", len(rows("assembly")) == 2 and not js(f"return !!{A}.measuring"))

    print("12. kept with the project: reloaded (autosave) and opened again")
    time.sleep(4.5)  # (autosave: a few seconds after the change)
    d.refresh()
    wait("return !!window.__app")
    wait("return document.querySelector('.restore-bar')", 15)
    d.find_element(By.CSS_SELECTOR, ".restore-bar [data-a=open]").click()
    wait("return window.__app.project.parts.length >= 4", 30)
    call("open_part", id="Measured")
    wait(f"return window.__app.state.workspace === 'assembly' && Object.values({A}.bodies).every(b => b.body)", 60)
    time.sleep(0.5)
    check("after a reload: the assembly's 2 rows", len(rows("assembly")) == 2, rows("assembly"))
    call("open_part", id="Block")
    wait(f"return window.__app.state.workspace === 'model' && {M}.result?.body && !{M}.inflight", 60)
    time.sleep(0.5)
    check("… and the block's 12 rows", len(rows("model")) == 12, len(rows("model")))
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        fails.append("console errors")
    d.quit()
print("FAILED:" if fails else "ALL PASSED", fails)
sys.exit(1 if fails else 0)
