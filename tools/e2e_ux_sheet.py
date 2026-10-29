"""The drawing sheet's suggestions table (sheet/sheetsuggest.js), in Czech, with REAL mouse clicks on the sheet and on
the table's rows: a plate 60 × 40 × 8 with 4 holes Ø4 -> 📄 Drawing sheet (light) -> nothing chosen: the next steps
(Doplnit chybějící kóty -> fully dimensioned) -> a view: Větší (2:1), Ctrl+Z; Přidat řez A–A; the section: Skrýt pohled
-> the top view hidden (Delete), 👁 Ukázat pohled brings it back -> an edge: Okótovat její délku (60 mm) -> the new
dimension: Tolerance… ±0.1, Referenční kóta "(60 ±0.1)", Na druhou stranu, Smazat -> a hole: its callout chosen
(Jeho kóta), Uložení… H7 -> the title block: Číslo výkresu… D-001, Šablona (Modern), Rámeček… Úzký -> Esc: Export PDF
(the PDF has D-001), Tisk (a print frame with the PDF). Screenshots at 1600 × 1000 and the view's table at 1280 × 800.

  PYTHONIOENCODING=utf-8 py tools/e2e_ux_sheet.py http://127.0.0.1:5199 <out dir>
"""
import base64
import sys
import time

import fitz
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


def built():
    wait(f"return !{S}.busy && !!{S}.svgEl", 90)
    time.sleep(0.4)


def table():
    el = d.find_elements(By.CSS_SELECTOR, "#shViewport .view-suggest")
    return el[0] if el else None


def title():
    t = table()
    return t.find_element(By.CSS_SELECTOR, ".vs-head b").text if t else None


def rows():
    t = table()
    return [b.text.replace("\n", " ") for b in t.find_elements(By.CSS_SELECTOR, ".vs-list button")] if t else []


def row(label):
    """Click the table's row whose text has `label` (a real mouse click)."""
    t = table()
    for b in t.find_elements(By.CSS_SELECTOR, ".vs-list button"):
        if label in b.text:
            ActionChains(d).move_to_element(b).click().perform()
            time.sleep(0.5)
            return True
    raise AssertionError(f"no row {label!r} in {rows()}")


def screen(pt):
    return js(f"""const s = {S}.svgEl, p = s.createSVGPoint(); p.x = arguments[0][0]; p.y = arguments[0][1];
      const q = p.matrixTransform(s.getScreenCTM()), r = {S}.stage.getBoundingClientRect();
      return [Math.round(q.x - (r.left + r.width / 2)), Math.round(q.y - (r.top + r.height / 2))]""", pt)


def click_paper(pt):
    x, y = screen(pt)
    ActionChains(d).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, "#shViewport .sh-stage"), x, y).click().perform()
    time.sleep(0.5)


def answer(text):
    """Type into the open ask() dialog and press OK."""
    inp = wait("return document.querySelector('.choose.ask .ask-in')", 5)
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys(text)
    d.find_element(By.CSS_SELECTOR, ".choose.ask [data-a=ok]").click()
    time.sleep(0.5)


def pick(label):
    """Click the choose() dialog's option `label`."""
    wait("return document.querySelector('.choose .choose-opts')", 5)
    for b in d.find_elements(By.CSS_SELECTOR, ".choose .choose-opts button"):
        if b.text.split("\n")[0].strip() == label:
            b.click()
            time.sleep(0.5)
            return
    raise AssertionError(f"no option {label!r}")


def view_mid(v):
    pb = js(f"return {S}.paperBox(arguments[0])", v)
    return [(pb[0] + pb[2]) / 2 + (pb[2] - pb[0]) * 0.17, (pb[1] + pb[3]) / 2 + (pb[3] - pb[1]) * 0.12]


try:
    d.get(URL)
    js("localStorage.setItem('auto3d-lang', 'cs'); localStorage.removeItem('a3d.box.suggest'); localStorage.removeItem('a3d.leftDock'); sessionStorage.removeItem('a3d.suggestAll')")
    d.get(URL)
    wait("return !!window.__app")
    time.sleep(1)
    call("new_model", name="Deska")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=8)
    call("add_feature", type="hole", face="F2:end", points=[[-20, -10], [20, -10], [-20, 10], [20, 10]], d=4)
    wait(f"return !!{M}.result?.body && !{M}.inflight")
    js(f"{M}.renderProps()")
    time.sleep(0.4)
    d.find_element(By.CSS_SELECTOR, "#modelRight [data-a=newSheet]").click()
    built()
    js(f"{S}.hooks.download = async (blob, name) => {{ window.__dl = {{ name, size: blob.size, b64: btoa(String.fromCharCode(...new Uint8Array(await blob.arrayBuffer()))) }}; return true; }}")
    d.find_element(By.CSS_SELECTOR, "#shViewport [data-preset=light]").click()
    wait(f"return !{S}.busy && {S}.d.built?.preset === 'light'", 60)
    time.sleep(0.5)

    # nothing chosen: the next steps
    check("a table with nothing chosen", title() == "📄 Deska", title())
    r0 = rows()
    print("   rows:", r0)
    d.save_screenshot(f"{OUT}/ux_sheet_1_nothing.png")
    if any("Doplnit chybějící kóty" in r for r in r0):
        row("Doplnit chybějící kóty")
        check("missing sizes added from the table", js(f"return {S}.check().missing.length") == 0, str(js(f"return {S}.check().missing.length")))
    check("Export PDF and Tisk offered", any("Export PDF" in r for r in rows()) and any("Tisk" in r for r in rows()), str(rows()))

    # a view: bigger, Ctrl+Z, a section, the section hidden
    click_paper(view_mid("Front"))
    check("a click on the front view chooses it", js(f"return {S}.selView") == "Front" and title() == "▣ Zepředu", f"{js(f'return {S}.selView')} {title()}")
    print("   rows:", rows())
    d.save_screenshot(f"{OUT}/ux_sheet_2_view.png")
    row("Větší (2:1)")
    check("Větší (2:1): the view at 2:1, its label says it", js(f"return JSON.stringify({S}.d.vscale?.Front)") == "[2,1]" and "Zepředu (2:1)" in (title() or ""), f"{js(f'return JSON.stringify({S}.d.vscale)')} {title()}")
    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    time.sleep(0.5)
    check("Ctrl+Z: back at the sheet's scale", not js(f"return {S}.d.vscale?.Front"))
    click_paper(view_mid("Front"))
    row("Přidat řez A–A")
    built()
    check("Přidat řez A–A: the section on the sheet", js(f"return {S}.drawn().includes('Section')"))
    d.save_screenshot(f"{OUT}/ux_sheet_3_section.png")
    click_paper(view_mid("Section"))
    check("the section chosen", js(f"return {S}.selView") == "Section", title())
    row("Skrýt pohled")
    built()
    check("Skrýt pohled: the section off, the right view back", not js(f"return {S}.drawn().includes('Section')") and js(f"return {S}.drawn().includes('Right')"))

    # the top view: Delete hides it, the table brings it back
    click_paper(view_mid("Top"))
    ActionChains(d).send_keys(Keys.DELETE).perform()
    time.sleep(0.5)
    check("Delete on a chosen view hides it", js(f"return !!{S}.d.off.Top"))
    row("Ukázat pohled: Horní")
    check("👁 Ukázat pohled: Horní brings it back", not js(f"return !!{S}.d.off.Top"))

    # an edge: its length -> the dimension's rows
    pb = js(f"return {S}.paperBox('Front')")
    click_paper([(pb[0] + pb[2]) / 2 + 3, pb[1]])
    check("a click on an edge chooses it", js(f"return !!{S}.selGeo?.edge") and (title() or "").startswith("⟋ Hrana 60"), title())
    d.save_screenshot(f"{OUT}/ux_sheet_4_edge.png")
    n0 = js(f"return {S}.d.user.length")
    row("Okótovat její délku (60 mm)")
    new = js(f"return {S}.d.user.slice(-1)[0]")
    check("Okótovat její délku: a new 60 dimension, chosen", js(f"return {S}.d.user.length") == n0 + 1 and js(f"return {S}.value({S}.d.user.slice(-1)[0])") == 60 and js(f"return {S}.sel") == new["id"])
    check("the dimension's table", (title() or "").startswith("⟷ 60"), str(rows()))
    row("Tolerance…")
    answer("0.1")
    row("Referenční kóta")
    txt = js(f"const x = {S}.allDims().find(q => q.id === '{new['id']}'); return {S}.dimText(x, {S}.value(x))")
    check("tolerance and reference: (60 ±0.1) on the sheet", txt == "(60 ±0.1)" and "(60 ±0.1)" in js(f"return {S}.svgEl.querySelector('[data-dim=\"{new['id']}\"]').textContent"), txt)
    d.save_screenshot(f"{OUT}/ux_sheet_5_dim.png")
    side0 = js(f"return {S}.d.user.find(q => q.id === '{new['id']}').side")
    row("Na druhou stranu")
    check("Na druhou stranu: the other side", js(f"return {S}.d.user.find(q => q.id === '{new['id']}').side") != side0)
    row("Smazat")
    check("Smazat: gone", not js(f"return {S}.d.user.some(q => q.id === '{new['id']}')"))
    # an edge -> the distance to another one: one more click, then back to choosing
    pb = js(f"return {S}.paperBox('Front')")
    click_paper([(pb[0] + pb[2]) / 2 + 3, pb[1]])
    row("Vzdálenost nebo úhel k…")
    click_paper([(pb[0] + pb[2]) / 2 + 3, pb[3]])
    check("Vzdálenost k…: the thickness 8 from two edges, back to choosing", js(f"return {S}.value({S}.d.user.slice(-1)[0])") == 8 and js(f"return {S}.tool") == "select" and (title() or "").startswith("⟷ 8"), f"{js(f'return {S}.value({S}.d.user.slice(-1)[0])')} {js(f'return {S}.tool')} {title()}")
    row("Smazat")

    # a hole: its callout (already there) chosen, a fit on it
    c = js(f"const c = {S}.geo.views.Top.circles.find(c => c.full), C = {S}.P('Top', c.c); return [C[0] - c.r * {S}.vs('Top'), C[1]]")
    click_paper(c)
    check("a click on a hole chooses its circle", js(f"return !!{S}.selGeo?.c") and "Ø4" in (title() or ""), f"{title()} {rows()}")
    d.save_screenshot(f"{OUT}/ux_sheet_6_hole.png")
    if any("Jeho kóta" in r for r in rows()):
        row("Jeho kóta")
    else:
        row("Popis díry")
    check("the hole's callout chosen", js(f"const x = {S}.allDims().find(q => q.id === {S}.sel); return !!x && x.kind === 'dia'"))
    row("Uložení…")
    pick("H7")
    txt = js(f"const x = {S}.allDims().find(q => q.id === {S}.sel); return {S}.dimText(x, {S}.value(x))")
    check("Uložení H7 on the callout", "H7" in txt, txt)

    # the title block
    tb = js(f"const b = {S}.svgEl.querySelector('.sh-title').getBBox(); return [b.x + b.width - 8, b.y + 4]")
    click_paper(tb)
    check("a click on the title block chooses it", js(f"return {S}.selTitle") and title() == "▤ Rohové razítko", title())
    d.save_screenshot(f"{OUT}/ux_sheet_7_title.png")
    row("Číslo výkresu…")
    answer("D-001")
    check("Číslo výkresu D-001 in the title block", js(f"return {S}.d.texts?.number") == "D-001" and "D-001" in js(f"return {S}.svgEl.querySelector('.sh-title').textContent"))
    row("Šablona:")
    pick("Moderní")
    wait(f"return !{S}.busy", 60)
    check("Šablona: Modern", js(f"return {S}.tplName()") == "Modern", js(f"return {S}.tplName()"))
    click_paper(js(f"const b = {S}.svgEl.querySelector('.sh-title').getBBox(); return [b.x + b.width - 8, b.y + 4]"))
    row("Rámeček…")
    pick("Úzký")
    built()
    check("Rámeček: Úzký", js(f"return {S}.frameOf().preset") == "narrow")

    # nothing chosen again: the PDF and print
    click_paper([3, 3])
    check("a click on empty paper: the sheet's table again", title() == "📄 Deska", title())
    row("Export PDF")
    wait("return !!window.__dl", 30)
    pdf = js("return window.__dl")
    text = fitz.open("pdf", base64.b64decode(pdf["b64"]))[0].get_text()
    check("Export PDF: a PDF with D-001 and the H7", pdf["name"].endswith(".pdf") and "D-001" in text and "H7" in text, pdf["name"])
    row("Tisk")
    wait("return !!document.querySelector('iframe.sh-print')?.src", 30)
    check("Tisk: a print frame with the PDF", js("return document.querySelector('iframe.sh-print').src.startsWith('blob:')"))
    d.save_screenshot(f"{OUT}/ux_sheet_8_done.png")

    # the view's table at 1280 × 800
    d.set_window_size(1280, 800)
    time.sleep(0.8)
    js(f"{S}.zoom = {{k: 1, x: 0, y: 0}}; {S}.applyZoom()")
    click_paper(view_mid("Front"))
    check("1280 × 800: the view's table fits the view", js("const b = document.querySelector('#shViewport .view-suggest').getBoundingClientRect(), v = document.getElementById('shViewport').getBoundingClientRect(); return b.top >= v.top && b.bottom <= v.bottom + 1"))
    d.save_screenshot(f"{OUT}/ux_sheet_9_1280.png")
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        fails.append("console errors")
    print(f"{len(fails)} failed" + (f": {fails}" if fails else " — all OK"))
    d.quit()
sys.exit(1 if fails else 0)
