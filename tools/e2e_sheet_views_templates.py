"""Drawing-sheet views renamed, moved and scaled, in headless Edge with the mouse: a bracket 60 × 30 × 8 with two holes ->
its sheet -> a double-click on the Front view's name: typed "Side A" + Enter -> the label, the Views panel, the PDF
say it; Ctrl+Z brings "Front" back, Ctrl+Y "Side A" again -> the Top view dragged a little off its place: it snaps
under the front view (the same x), with Shift it does not -> the Right view's scale Custom… 1:2522: its label says
"(1:2522)" -> the sheet's scale Custom… 1:2522: the title block's Scale says 1:2522, the Right view's label no more
(it is the sheet's), the dimensions still the real sizes; 5:1 on A4 warns "past the frame" -> the DXF has a
dimension measuring 60 at 5:1.

  PYTHONIOENCODING=utf-8 py tools/e2e_sheet_views_templates.py http://127.0.0.1:5199 <out dir> [cs]
"""
import base64
import io
import json
import sys
import time

import ezdxf
import fitz
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select

URL, OUT = sys.argv[1], sys.argv[2]
LANG = sys.argv[3] if len(sys.argv) > 3 else "en"
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
S = "window.__app.sheet"
H = "window.__app.agentHandlers"
COMPANY, TPL = "ACME Automation s.r.o.", "ACME"
fails = []


def check(ok, what):
    print(("  ok  " if ok else "  FAIL ") + what)
    if not ok:
        fails.append(what)


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


def stage():
    return d.find_element(By.CSS_SELECTOR, "#shViewport .sh-stage")


def screen(pt):
    """A paper point (mm) -> the offset from the stage's middle in px (for ActionChains)."""
    return js(f"""const s = {S}.svgEl, p = s.createSVGPoint(); p.x = arguments[0][0]; p.y = arguments[0][1];
      const q = p.matrixTransform(s.getScreenCTM()), r = {S}.stage.getBoundingClientRect();
      return [Math.round(q.x - (r.left + r.width / 2)), Math.round(q.y - (r.top + r.height / 2))]""", pt)


def px_per_mm():
    return js(f"return {S}.svgEl.getScreenCTM().a")


def label_at(v):
    return js(f"const r = document.querySelector('#shViewport [data-vlabel={v}]').getBBox(); return [r.x + r.width / 2, r.y + r.height / 2]")


def labels():
    return js("return [...document.querySelectorAll('#shViewport [data-vlabel]')].map(t => t.textContent)")


def title_texts():
    return js("return [...document.querySelectorAll('#shViewport .sh-title text')].map(t => t.textContent)")


def pdf_of(body_js):
    """/api/sheet/pdf of a body made in the page (e.g. "{svg: …}") -> the PDF (fitz)."""
    b64 = js(f"""return fetch('/api/sheet/pdf', {{method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({body_js})}})
        .then(r => r.arrayBuffer()).then(b => {{ let s = ''; const u = new Uint8Array(b); for (let i = 0; i < u.length; i++) s += String.fromCharCode(u[i]); return btoa(s); }})""")
    return fitz.open(stream=base64.b64decode(b64), filetype="pdf")


def pick_custom(sel_css, value):
    """A scale <select>: Custom… -> the dialog -> typed + Enter."""
    Select(d.find_element(By.CSS_SELECTOR, sel_css)).select_by_value("custom")
    inp = wait("return document.querySelector('.choose.ask .ask-in')", 5)
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys(value, Keys.ENTER)
    time.sleep(0.6)


try:
    d.get(URL)
    time.sleep(2)
    if LANG != "en":
        js("localStorage.setItem('auto3d-lang', arguments[0])", LANG)
        d.get(URL)
        time.sleep(2)
    call("new_model", name="Bracket")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 30}}])
    call("add_feature", type="extrude", sketch="F1", d=8)
    call("add_feature", type="hole", face="F2:end", points=[[-20, 0], [20, 0]], d=5)
    call("set_material", material="aluminium", tolerance="m")
    call("sheet_open")
    wait(f"return !!{S}.svgEl && !{S}.busy", 60)
    call("sheet_edit", template="Modern")  # (this test checks the Modern title block; the default is B — ISO 7200)
    wait(f"return !{S}.busy", 60)
    time.sleep(0.5)
    front = "Zepředu" if LANG == "cs" else "Front"

    print("0. the modern title block: inside the frame, black on white, the part's name large")
    box = js("""const b = document.querySelector('#shViewport .sh-title').getBBox(), L = window.__app.sheet.lay, m = L.margins || [L.margin, L.margin, L.margin, L.margin];
      return {b: [b.x, b.y, b.x + b.width, b.y + b.height], in: [m[0], m[1], L.size[0] - m[2], L.size[1] - m[3]]}""")
    b, inner = box["b"], box["in"]
    check(b[0] >= inner[0] - 0.01 and b[1] >= inner[1] - 0.01 and b[2] <= inner[2] + 0.01 and b[3] <= inner[3] + 0.01, f"the title block {[round(v, 1) for v in b]} inside the frame {inner}")
    cols = js("return [...new Set([...document.querySelectorAll('#shViewport .sh-title [stroke], #shViewport .sh-title text')].map(e => e.getAttribute('stroke') || e.getAttribute('fill')).filter(c => c && c !== 'none'))]")
    check(set(cols) <= {"#000", "#555", "#fff"}, f"black, grey and white only: {cols}")
    big = js("const t = [...document.querySelectorAll('#shViewport .sh-title text[font-weight=bold]')].find(t => t.textContent === 'Bracket'); return t ? +t.getAttribute('font-size') : 0")
    check(big >= 5, f"the part's name in bold, {big} mm high")

    print("1. rename the Front view by a double-click on its name")
    x, y = screen(label_at("Front"))
    ActionChains(d).move_to_element_with_offset(stage(), x, y).click().pause(0.1).click().perform()
    inp = wait("return document.querySelector('input.sh-rename')", 5)
    check(inp.get_attribute("value") == front, f"the field starts with its name ({inp.get_attribute('value')})")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys("Side A", Keys.ENTER)
    time.sleep(0.5)
    check("Side A" in labels(), f"the label says Side A: {labels()}")
    check(js("return [...document.querySelectorAll('#shLeft .sh-vname')].map(e => e.textContent).includes('Side A')"), "the Views panel says Side A")
    ActionChains(d).move_to_element_with_offset(stage(), 0, -300).click().perform()  # (the stage has the keys)
    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    time.sleep(0.4)
    check(front in labels() and "Side A" not in labels(), f"Ctrl+Z: {front} again")
    ActionChains(d).key_down(Keys.CONTROL).send_keys("y").key_up(Keys.CONTROL).perform()
    time.sleep(0.4)
    check("Side A" in labels(), "Ctrl+Y: Side A again")
    d.save_screenshot(f"{OUT}/views_renamed.png")

    print("2. drag the Top view: it snaps under the front view")
    fx = js(f"return {S}.centre('Front')[0]")
    top = js(f"return {S}.centre('Top')")
    k = px_per_mm()
    sx, sy = screen([top[0] - 12, top[1]])  # (on the view's box, left of the holes)
    pb = js(f"return {S}.paperBox('Top')")
    sx, sy = screen([pb[0] + 2, (pb[1] + pb[3]) / 2])
    ActionChains(d).move_to_element_with_offset(stage(), sx, sy).click_and_hold().move_by_offset(int(10 * k), int(6 * k)).pause(0.2).move_by_offset(-int(7.5 * k), 0).pause(0.3).perform()
    guides = js("return document.querySelectorAll('#shViewport .sh-guide').length")
    ActionChains(d).release().perform()
    time.sleep(0.4)
    now = js(f"return {S}.centre('Top')")
    check(abs(now[0] - fx) < 1e-6, f"Top snapped under Front: x {now[0]:.2f} = {fx:.2f}; moved down {now[1] - top[1]:.1f} mm; a guide while dragging: {guides}")
    pb = js(f"return {S}.paperBox('Top')")
    sx, sy = screen([pb[0] + 2, (pb[1] + pb[3]) / 2])
    ActionChains(d).move_to_element_with_offset(stage(), sx, sy).key_down(Keys.SHIFT).click_and_hold().move_by_offset(int(2.5 * k), 0).pause(0.2).release().key_up(Keys.SHIFT).perform()
    time.sleep(0.4)
    free = js(f"return {S}.centre('Top')")
    check(abs(free[0] - fx) > 1, f"with Shift it moves freely: x {free[0]:.2f}")
    d.save_screenshot(f"{OUT}/views_snapped.png")

    print("3. scales: the Right view 1:2522, then the sheet 1:2522")
    pick_custom("#shLeft select[data-vs=Right]", "1:2522")
    right = "Zprava" if LANG == "cs" else "Right"
    check(f"{right} (1:2522)" in labels(), f"the Right view's label: {labels()}")
    pick_custom("#shRight select[data-k=scale]", "1:2522")
    wait(f"return !{S}.busy && {S}.lay.scale[1] === 2522", 30)
    time.sleep(0.4)
    tt = title_texts()
    check("1:2522" in tt, f"the title block's scale: {[x for x in tt if ':' in x][:3]}")
    check(right in labels() and f"{right} (1:2522)" not in labels(), f"the Right view at the sheet's scale says no scale: {labels()}")
    dims = js(f"return {S}.allDims().map(x => {S}.dimText(x, {S}.value(x)))")
    check("60" in dims and "30" in dims, f"the dimensions are the real sizes: {dims}")
    d.save_screenshot(f"{OUT}/views_scale_2522.png")
    Select(d.find_element(By.CSS_SELECTOR, "#shRight select[data-k=scale]")).select_by_value("5:1")
    wait(f"return !{S}.busy && {S}.lay.scale[0] === 5", 30)
    time.sleep(0.4)
    warn = js("return document.querySelector('#shLeft .sh-outside')?.textContent || ''")
    check("1:2522" not in title_texts() and "5:1" in title_texts(), "5:1 in the title block")
    check(bool(warn), f"5:1 on A4 warns: {warn}")
    d.save_screenshot(f"{OUT}/views_scale_5.png")
    res = json.loads(call("get_sheet"))
    check(res.get("scale") == "5:1" and res.get("view_names", {}).get("Front") == "Side A" and res.get("past_the_frame"), f"get_sheet: scale {res.get('scale')}, names {res.get('view_names')}, past {res.get('past_the_frame')}")
    dxf = js(f"""return fetch('/api/sheet/dxf', {{method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({S}.dxfData())}}).then(r => r.text())""")
    check("Side A" in dxf, "the DXF has the view's name")
    doc = ezdxf.read(io.StringIO(dxf))
    meas = sorted(round(dm.get_measurement() / 5, 2) for dm in doc.modelspace().query("DIMENSION") if dm.dxf.dimtype & 7 == 0)  # (linear: paper mm / 5 = the part's)
    check(60.0 in meas, f"the DXF's linear dimensions measure the part at 5:1: {meas}")
    pdf = pdf_of(f"{{svg: {S}.svg(true)}}")
    txt = pdf[0].get_text()
    check("Side A" in txt and "5:1" in txt, "the PDF has Side A and 5:1")
    pdf[0].get_pixmap(dpi=70).save(f"{OUT}/views_pdf.png")
    Select(d.find_element(By.CSS_SELECTOR, "#shRight select[data-k=scale]")).select_by_value("")  # (Auto again)
    wait(f"return !{S}.busy && !{S}.d.scale", 30)

    print("3b. the frame: Standard ISO 5457, None, Custom…")
    js(f"{S}.sel = null; {S}.render()")
    Select(d.find_element(By.CSS_SELECTOR, "#shRight select[data-k=frame]")).select_by_value("iso")
    wait(f"return !{S}.busy && {S}.lay.margins[0] === 20", 30)
    time.sleep(0.4)
    pdf = pdf_of(f"{{svg: {S}.svg(true)}}")
    mm = 72 / 25.4
    rects = [it["rect"] for it in pdf[0].get_drawings() if it["rect"].width > 200 * mm and it["rect"].height > 150 * mm]
    frame = [r for r in rects if abs(r.x0 - 20 * mm) < 0.2 and abs(r.x1 - 287 * mm) < 0.2 and abs(r.y0 - 10 * mm) < 0.2]
    check(bool(frame), f"ISO 5457: the PDF's frame starts 20 mm from the left: {[(round(r.x0 / mm, 2), round(r.y0 / mm, 2), round(r.x1 / mm, 2), round(r.y1 / mm, 2)) for r in rects]}")
    txt = pdf[0].get_text("words")
    check(any(w[4] == "A" and w[0] < 20 * mm for w in txt) and any(w[4] == "6" and w[1] < 10 * mm for w in txt), "zones: A in the left margin, 6 along the top")
    fx = js(f"return {S}.centre('Front')[0]")
    check(js(f"return {S}.paperBox('Front')[0]") > 20 and fx > 79.25, f"the views laid out inside it: Front at x {fx:.2f} (was 79.25)")
    d.save_screenshot(f"{OUT}/frame_iso.png")
    pdf[0].get_pixmap(dpi=70).save(f"{OUT}/frame_iso_pdf.png")
    Select(d.find_element(By.CSS_SELECTOR, "#shRight select[data-k=frame]")).select_by_value("none")
    wait(f"return !{S}.busy && {S}.lay.margins[0] === 10", 30)
    pdf = pdf_of(f"{{svg: {S}.svg(true)}}")
    rects = [it["rect"] for it in pdf[0].get_drawings() if it["rect"].width > 200 * mm and it["rect"].height > 150 * mm and it.get("color") is not None]
    check(not rects and "data-frame" not in js(f"return {S}.svg(true)"), f"None: no frame line ({len(rects)})")
    Select(d.find_element(By.CSS_SELECTOR, "#shRight select[data-k=frame]")).select_by_value("custom")
    left = wait("return document.querySelector('#shRight [data-fr=l]')", 5)
    left.send_keys(Keys.CONTROL, "a")
    left.send_keys("25", Keys.ENTER)
    wait(f"return !{S}.busy && {S}.lay.margins[0] === 25", 30)
    check(js(f"return {S}.frameOf().preset") == "custom" and js(f"return {S}.svg(true)").count('data-frame') == 1, "Custom…: a 25 mm left margin typed, the frame drawn there")
    ActionChains(d).move_to_element_with_offset(stage(), 0, -300).click().perform()
    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    wait(f"return !{S}.busy && {S}.lay.margins[0] !== 25", 30)
    check(js(f"return {S}.frameOf().m[0]") == 10, "Ctrl+Z: back to before")
    Select(d.find_element(By.CSS_SELECTOR, "#shRight select[data-k=frame]")).select_by_value("iso")
    wait(f"return !{S}.busy && {S}.lay.margins[0] === 20", 30)

    print("4. a title-block template: typed, saved, used for an assembly's whole drawing set")
    js(f"{S}.sel = null; {S}.render()")
    d.find_element(By.CSS_SELECTOR, "#shRight .sh-tbmore summary").click()
    time.sleep(0.2)
    for k, v in (("company", COMPANY), ("address", "Main St 1; 602 00 Brno"), ("drawn", "F. Paul")):
        el = d.find_element(By.CSS_SELECTOR, f"#shRight [data-text={k}]")
        el.clear()
        el.send_keys(v, Keys.ENTER)
        time.sleep(0.3)
    d.find_element(By.CSS_SELECTOR, "#shRight [data-a=saveTpl]").click()
    inp = wait("return document.querySelector('.choose.ask .ask-in')", 5)
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys(TPL, Keys.ENTER)
    wait(f"return {S}.d.template === '{TPL}'", 10)
    time.sleep(0.4)
    check(COMPANY in title_texts(), f"the title block shows the company: {[x for x in title_texts() if 'ACME' in x]}")
    kept = js("return fetch('/api/title-templates').then(r => r.json()).then(j => j.templates.find(x => x.name === arguments[0]) || null)", TPL)
    check(bool(kept) and kept["texts"].get("company") == COMPANY and kept["texts"].get("drawn") == "F. Paul", f"kept on the server: {kept and kept['texts']}")
    check(js(f"return !({S}.d.texts || {{}}).company"), "the sheet's own company went into the template")
    d.save_screenshot(f"{OUT}/template_saved.png")

    # a small assembly by the AI tools: Base, Lid, Pin; "Lid unit" (Lid + Pin); "Machine" (Base + Lid unit)
    for nm, w, h, th in (("Base", 80, 50, 10), ("Lid", 60, 40, 4)):
        call("new_model", name=nm)
        call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": w, "h": h}}])
        call("add_feature", type="extrude", sketch="F1", d=th)
    call("new_model", name="Pin")
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 6}}])
    call("add_feature", type="extrude", sketch="F1", d=12)
    call("sheet_open", part="Base")  # (a sheet made before: it gets the template too)
    call("new_assembly", name="Lid unit")
    call("insert_part", part="Lid")
    call("insert_part", part="Pin")
    call("new_assembly", name="Machine")
    call("insert_part", part="Base")
    call("insert_part", part="Lid unit")
    call("sheet_open", part="Machine")
    wait(f"return !!{S}.svgEl && !{S}.busy && !!{S}.d.asm", 90)
    time.sleep(0.5)
    js(f"{S}.sel = null; {S}.render()")
    check(js(f"return {S}.tplName()") == "B — ISO 7200", "the assembly's sheet starts with the default B — ISO 7200")
    Select(d.find_element(By.CSS_SELECTOR, "#shRight select[data-k=tpl]")).select_by_value(TPL)
    time.sleep(0.4)
    d.find_element(By.CSS_SELECTOR, "#shRight [data-a=tplSet]").click()
    time.sleep(1.5)
    sheets = js("return window.__app.project.parts.filter(p => p.kind === 'sheet').map(p => [p.name, p.data === 'live' ? window.__app.sheet.d.template : p.data.template])")
    print("   sheets:", sheets)
    check(all(tp == TPL for nm, tp in sheets if "Bracket" not in nm), "every sheet of the set has the template (the Bracket's is not in it)")
    res = json.loads(call("get_sheet"))
    check(res.get("template") == TPL, f"get_sheet: template {res.get('template')}")
    d.save_screenshot(f"{OUT}/template_on_set.png")
    # a new sheet of the set takes it: the Lid's (made now, no template of its own)
    call("sheet_open", part="Lid")
    wait(f"return !!{S}.svgEl && !{S}.busy && !{S}.d.asm", 60)
    check(not js(f"return {S}.d.template") and js(f"return {S}.tplName()") == TPL and COMPANY in title_texts(), f"the Lid's new sheet takes it from the set: {json.loads(call('get_sheet')).get('template')}")
    call("sheet_open", part="Machine")
    wait(f"return !!{S}.svgEl && !{S}.busy && !!{S}.d.asm", 60)
    js(f"return {S}.drawingSet({S}.d.source, {S}.hooks.drawingCtx()).then(s => {{ window.__set = s; }})")
    names = js("return window.__set.pages")
    svgs = js("return window.__set.svgs.map(s => s.includes(arguments[0]))", COMPANY)
    check(len(svgs) == 5 and all(svgs), f"every page of the set has the company: {names} {svgs}")
    pdf = pdf_of("{svgs: window.__set.svgs}")
    pages = [p.get_text() for p in pdf]
    check(len(pages) == 5 and all(COMPANY in p for p in pages), f"every page of the set's PDF ({len(pages)}) has the company")
    framed = [any(abs(it["rect"].x0 - 20 * mm) < 0.2 and it["rect"].height > 150 * mm for it in p.get_drawings()) for p in pdf]
    check(all(framed), f"the template's ISO frame (20 mm left) on every page: {framed}")
    pdf[0].get_pixmap(dpi=80).save(f"{OUT}/template_set_p1.png")
    pdf[len(pages) - 1].get_pixmap(dpi=80).save(f"{OUT}/template_set_last.png")
    dxf = js(f"""return fetch('/api/sheet/dxf', {{method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({S}.dxfData())}}).then(r => r.text())""")
    check(COMPANY in dxf, "the DXF has the company")
    print("   the AI back to Modern:", json.loads(call("sheet_edit", template="Modern"))["done"])
    check(COMPANY not in title_texts(), "Modern: no company")
    call("sheet_edit", template=TPL)
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    d.quit()
print("FAILED:" if fails else "ALL OK", fails)
sys.exit(1 if fails else 0)
