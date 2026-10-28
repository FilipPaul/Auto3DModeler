"""The drawing sheet's title-block and parts-list styles A–E, in headless Edge: an assembly "Stand" (a base plate, two
lids, a bracket, three pins, a bought ISO 4762 screw) -> its sheet -> Title block style ▾ / Parts list style ▾ each
of A … E picked in the panel: the title block has the design's size at the frame's bottom right, the parts list sits
on it (no gap, the right edges together), the labels in the UI's language, the texts in the style's font (on screen
and in the PDF, whose fonts are the bundled IBM Plex / Barlow / Inter) -> a mix (title D + list C): 💾 Save as
template… keeps both on the server -> 📋 Add BOM page, ⇶ Use for all drawings of this assembly: every page of the
drawing set has the D title block, the BOM page the C list; the set's PDF has the fields (drawing no., drawn by,
labels) -> the app's template "B — ISO 7200" brings its ISO frame -> the AI's sheet_edit title_style / bom_style ->
the DXF has the title block's texts. Screenshots of each pair (screen and PDF) go to <out dir>.

  PYTHONIOENCODING=utf-8 py tools/e2e_sheet_styles.py http://127.0.0.1:5199 <out dir> [cs]
"""
import base64
import io
import json
import sys
import time
import urllib.request

import ezdxf
import fitz
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select

URL, OUT = sys.argv[1], sys.argv[2]
LANG = sys.argv[3] if len(sys.argv) > 3 else "en"
CS = LANG == "cs"
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
S = "window.__app.sheet"
SIZE = {"A": (180, 21), "B": (180, 40), "C": (180, 34), "D": (170, 28), "E": (90, 56)}
BOMW = {"A": 180, "B": 180, "C": 180, "D": 170, "E": 90}
FONT = {"A": "IBM Plex Sans Condensed", "B": "IBM Plex Sans", "C": "Barlow", "D": "Inter", "E": "IBM Plex Sans Condensed"}
LABEL = {"A": "ČÍSLO VÝKRESU" if CS else "DRAWING NO.", "B": "KONTROLOVAL" if CS else "CHECKED", "C": "FORMÁT" if CS else "SHEET SIZE",
         "D": "HMOTNOST" if CS else "MASS", "E": "TOLERANCE" if CS else "TOLERANCES"}
TPL = "Mix DC"
fails = []


def check(ok, what):
    print(("  ok  " if ok else "  FAIL ") + what)
    if not ok:
        fails.append(what)


def ai(tool, **args):
    req = urllib.request.Request(f"{URL}/api/agent/call", data=json.dumps({"tool": tool, "args": args}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        res = json.loads(r.read())
    return ("ERROR " if res.get("isError") else "") + "".join(c.get("text", "") for c in res.get("content", []))


def wait(script, t=90):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(script)


def pdf_of(body_js):
    b64 = js(f"""return fetch('/api/sheet/pdf', {{method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({body_js})}})
        .then(r => r.arrayBuffer()).then(b => {{ let s = ''; const u = new Uint8Array(b); for (let i = 0; i < u.length; i++) s += String.fromCharCode(u[i]); return btoa(s); }})""")
    return fitz.open(stream=base64.b64decode(b64), filetype="pdf")


def boxes():
    """The title block's and the parts list's boxes (mm) on the sheet on screen, and the frame's inner corner."""
    return js("""const g = (s) => { const e = document.querySelector('#shViewport ' + s); if (!e) return null; const r = e.querySelector('rect').getBBox(); return [r.x, r.y, r.x + r.width, r.y + r.height]; };
      const L = window.__app.sheet.lay, m = L.margins; return {title: g('.sh-title'), bom: g('.sh-bom [data-style], .sh-bom'), corner: [L.size[0] - m[2], L.size[1] - m[3]]}""")


def pick(sel, value):
    Select(d.find_element(By.CSS_SELECTOR, f"#shRight select[data-k={sel}]")).select_by_value(value)
    time.sleep(0.3)
    wait(f"return !{S}.busy")
    time.sleep(0.5)


def corner_png(pdf, name):
    pg, mm = pdf[0], 72 / 25.4
    W, H = pg.rect.width, pg.rect.height
    pg.get_pixmap(dpi=170, clip=fitz.Rect(W - 200 * mm, H - 130 * mm, W, H)).save(f"{OUT}/{name}")


try:
    d.get(URL)
    time.sleep(1.5)
    js("localStorage.setItem('auto3d-lang', arguments[0])", LANG)
    d.get(URL)
    time.sleep(2)
    plate, lid, bracket, pin = ("Základová deska", "Víko", "Držák", "Kolík Ø4×12") if CS else ("Base plate", "Lid", "Bracket", "Pin Ø4×12")
    for nm, w, h, th, mat in ((plate, 120, 80, 10, "aluminium"), (lid, 60, 40, 4, "PLA"), (bracket, 30, 20, 8, "aluminium")):
        ai("new_model", name=nm)
        ai("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": w, "h": h}}])
        ai("add_feature", type="extrude", sketch="F1", d=th)
        ai("set_material", material=mat, tolerance="m")
    ai("new_model", name=pin)
    ai("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 4}}])
    ai("add_feature", type="extrude", sketch="F1", d=12)
    ai("new_assembly", name="Stand")
    for p, n in ((plate, 1), (lid, 2), (bracket, 1), (pin, 3)):
        for _ in range(n):
            ai("insert_part", part=p)
    ai("library_add", item="iso4762", size="M3", length=10, to="assembly")
    ai("sheet_open")
    wait(f"return !!{S}.svgEl && !{S}.busy && !!{S}.d.asm")
    ai("sheet_edit", texts={"company": "Rafiontech s.r.o.", "address": "Brno, CZ", "drawn": "F. Paul", "number": "A3D-0042", "surface": "Ra 3,2"})
    wait(f"return !{S}.busy")
    js("return document.fonts.ready.then(() => true)")
    js(f"{S}.sel = null; {S}.render()")
    time.sleep(0.4)
    check(js(f"return {S}.tplName()") == "Modern" and js(f"return {S}.tb().style") == "block", "a new sheet keeps the Modern title block (the default)")
    names = js("return [...document.querySelectorAll('#shRight select[data-k=tbstyle] option')].map(o => o.textContent)")
    check(("A — Pruh" if CS else "A — Strip") in names and ("E — Sloupec" if CS else "E — Column") in names, f"Title block style ▾: {names}")

    print("1. each style pair, picked in the panel")
    for k in "ABCDE":
        pick("tbstyle", k)
        pick("bomstyle", k)
        b = boxes()
        t, l, c = b["title"], b["bom"], b["corner"]
        w, h = SIZE[k]
        check(abs(t[2] - c[0]) < 0.3 and abs(t[3] - c[1]) < 0.3 and abs(t[2] - t[0] - w) < 0.3 and abs(t[3] - t[1] - h) < 0.3, f"{k}: the title block {w} × {h} mm at the frame's corner {c}: {[round(v, 1) for v in t]}")
        check(abs(l[3] - t[1]) < 0.01 and abs(l[2] - t[2]) < 0.3 and abs(l[2] - l[0] - BOMW[k]) < 0.3, f"{k}: the parts list ({BOMW[k]} mm) right on the title block: {[round(v, 1) for v in l]}")
        texts = js("return [...document.querySelectorAll('#shViewport .sh-title text, #shViewport .sh-bom text')].map(t => t.textContent)")
        fam = js("return getComputedStyle(document.querySelector('#shViewport .sh-title text[data-ff]')).fontFamily")
        check(LABEL[k] in texts and "A3D-0042" in texts and FONT[k] in fam, f"{k}: {LABEL[k]}, A3D-0042, in {fam.split(',')[0]}")
        mats = [x for x in texts if x in ("hliník", "aluminium", "ocel", "steel")]
        check(("Kolík Ø4×12" if CS else "Pin Ø4×12") in texts and "ISO 4762 M3×10" in texts and set(mats) == ({"hliník", "ocel"} if CS else {"aluminium", "steel"}),
              f"{k}: the parts list has the pin and the screw, materials in the UI's language: {sorted(set(mats))}")
        d.save_screenshot(f"{OUT}/styles_{LANG}_{k}{k}.png")
        pdf = pdf_of(f"{{svg: {S}.svg(true)}}")
        fonts = {f[3] for f in pdf[0].get_fonts()}
        txt = pdf[0].get_text()
        check(any(FONT[k].split()[0] in f for f in fonts) and "A3D-0042" in txt and LABEL[k] in txt.replace("\n", " "), f"{k}: the PDF has {LABEL[k]}, A3D-0042 in {sorted(fonts)}")
        corner_png(pdf, f"styles_{LANG}_{k}{k}_pdf.png")

    print("2. a mix: title block D with parts list C, saved as a template")
    pick("tbstyle", "D")
    pick("bomstyle", "C")
    b = boxes()
    check(abs(b["bom"][2] - b["title"][2]) < 0.3 and b["bom"][0] < b["title"][0] - 9, f"the 180 mm list and the 170 mm block aligned right: {[round(v, 1) for v in b['bom']]} on {[round(v, 1) for v in b['title']]}")
    hint = js("return [...document.querySelectorAll('#shRight .hint')].map(e => e.textContent).join(' | ')")
    check(("tohoto výkresu" if CS else "this drawing's") in hint, "the panel says the mix is this drawing's until saved")
    d.save_screenshot(f"{OUT}/styles_{LANG}_DC.png")
    corner_png(pdf_of(f"{{svg: {S}.svg(true)}}"), f"styles_{LANG}_DC_pdf.png")
    d.find_element(By.CSS_SELECTOR, "#shRight [data-a=saveTpl]").click()
    inp = wait("return document.querySelector('.choose.ask .ask-in')", 5)
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys(TPL, Keys.ENTER)
    wait(f"return {S}.d.template === '{TPL}'", 10)
    kept = js("return fetch('/api/title-templates').then(r => r.json()).then(j => j.templates.find(x => x.name === arguments[0]) || null)", TPL)
    check(bool(kept) and kept["titleStyle"] == "D" and kept["bomStyle"] == "C" and kept["texts"].get("surface") == "Ra 3,2", f"kept on the server: {kept and (kept['titleStyle'], kept['bomStyle'], kept['texts'])}")
    check(js(f"return !{S}.d.tb && {S}.tb().style === 'D' && {S}.tb().bomStyle === 'C'"), "the sheet now takes both from the template")

    print("3. the BOM page and the whole drawing set")
    js(f"{S}.sel = null; {S}.render()")
    d.find_element(By.CSS_SELECTOR, "#shRight [data-a=bomAdd]").click()
    time.sleep(0.6)
    js(f"{S}.setMode = false; {S}.render()")
    wait(f"return !{S}.busy")
    d.find_element(By.CSS_SELECTOR, "#shRight [data-a=tplSet]").click()
    time.sleep(1.5)
    sheets = js("return window.__app.project.parts.filter(p => p.kind === 'sheet').map(p => p.data === 'live' ? window.__app.sheet.d.template : p.data.template)")
    check(sheets and all(s == TPL for s in sheets), f"every drawing of the set uses {TPL}: {sheets}")
    js(f"return {S}.drawingSet({S}.d.source, {S}.hooks.drawingCtx()).then(s => {{ window.__set = s; }})")
    wait("return !!window.__set", 120)
    info = js("""return window.__set.svgs.map((s, i) => ({bom: window.__set.bom[i], title: /class="sh-title" data-style="D"/.test(s), list: /class="sh-bompage" data-style="C"/.test(s) && /class="sh-bom" data-style="C"/.test(s)}))""")
    print("   pages:", js("return window.__set.pages"))
    check(len(info) >= 5 and all(p["title"] for p in info), f"every page has the D title block ({len(info)} pages)")
    check(any(p["bom"] and p["list"] for p in info), "the BOM page uses the C parts list")
    pdf = pdf_of("{svgs: window.__set.svgs}")
    allt = [p.get_text().replace("\n", " ") for p in pdf]
    check(len(allt) == len(info) and all("F. Paul" in t and (("KRESLIL" if CS else "DRAWN BY") in t) for t in allt), "every page of the set's PDF has drawn by: F. Paul")
    check("A3D-0042" in allt[0] and (("KUSOVNÍK" if CS else "PARTS LIST") in allt[0] or "Kusovník" in allt[0] or "Parts list" in allt[0]), "the assembly's page: its drawing no. and its parts list")
    bp = next(i for i, p in enumerate(info) if p["bom"])
    check(("Kusovník" if CS else "Bill of materials") in allt[bp] and "ISO 4762 M3×10" in allt[bp], f"the BOM page (page {bp + 1}) lists the screw")
    fonts = {f[3] for p in pdf for f in p.get_fonts()}
    check(any("Inter" in f for f in fonts) and any("Barlow" in f for f in fonts), f"the set's PDF embeds Inter and Barlow: {sorted(fonts)}")
    pdf[bp].get_pixmap(dpi=70).save(f"{OUT}/styles_{LANG}_bompage.png")
    pdf[len(allt) - 1].get_pixmap(dpi=70).save(f"{OUT}/styles_{LANG}_lastpage.png")

    print("4. the app's template B — ISO 7200 (its frame too), the AI's styles, the DXF")
    Select(d.find_element(By.CSS_SELECTOR, "#shRight select[data-k=tpl]")).select_by_value("B — ISO 7200")
    wait(f"return !{S}.busy && {S}.lay.margins[0] === 20", 60)
    check(js(f"return {S}.tb().style === 'B' && {S}.tb().bomStyle === 'B' && {S}.frameOf().preset === 'iso'"), "B — ISO 7200: its title block, its list, the ISO frame")
    res = json.loads(ai("sheet_edit", title_style="E", bom_style="A"))
    wait(f"return !{S}.busy")
    res = json.loads(ai("get_sheet"))
    check(res.get("title_style") == "E" and res.get("bom_style") == "A", f"the AI: title_style {res.get('title_style')}, bom_style {res.get('bom_style')}")
    bad = ai("sheet_edit", title_style="Z")
    check(bad.startswith("ERROR"), f"a wrong style refused: {bad[:80]}")
    dxf = js(f"""return fetch('/api/sheet/dxf', {{method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({S}.dxfData())}}).then(r => r.text())""")
    doc = ezdxf.read(io.StringIO(dxf))
    words = [e.dxf.text for e in doc.modelspace().query("TEXT")]
    check("A3D-0042" in words and "Stand" in words and ("KRESLIL" if CS else "DRAWN BY") in words, f"the DXF has the E title block's texts: {words[-25:]}")
    d.save_screenshot(f"{OUT}/styles_{LANG}_EA.png")
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        fails.append("console errors")
    d.quit()
print("FAILED:" if fails else "ALL OK", fails)
sys.exit(1 if fails else 0)
