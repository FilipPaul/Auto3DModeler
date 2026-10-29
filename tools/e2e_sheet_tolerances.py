"""Tolerances, fits and surface roughness offered as lists on the drawing sheet (sheet/sheetsuggest.js, sheet/rough.js),
in Czech, with REAL mouse clicks: a plate 60 × 40 × 8 with a Ø10 hole -> 📄 its sheet -> the 60 dimension clicked: the
tolerance chips (±0.01 … ±0.5, +0.1/0 …, Obecná tolerance, Vlastní…) -> ±0.05: "60 ±0.05", ✓ on the chip -> the Ø10
callout clicked: the fit chips (H7 … H11, h6 … p6; H7's tooltip "+0.015 / 0") -> H7: "Ø10 H7" -> the title block's
Drsnost cell typed in: the Ra list under it -> Ra 0.8; the title block's suggestions: Ra 1.6 -> the top edge of the
front view clicked: Drsnost povrchu -> Ra 3.2: the symbol drawn on the edge, the title block "Ra 1.6 (✓)"; Výroba ▸
Obrobit (the bar); dragged along the edge -> the PDF has "±0.05", "Ø10 H7", "Ra 3.2", the DXF the symbol on layer
symbols -> Delete removes it -> the AI: sheet_edit roughness (add, change, remove), a one-sided tolerance, a fit H11.

  PYTHONIOENCODING=utf-8 py tools/e2e_sheet_tolerances.py http://127.0.0.1:5199 <out dir>
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
    return [b.text.replace("\n", " ") for b in t.find_elements(By.CSS_SELECTOR, ".vs-list > button")] if t else []


def chips():
    t = table()
    return [b.text for b in t.find_elements(By.CSS_SELECTOR, ".vs-chips .chip")] if t else []


def click_el(el):
    ActionChains(d).move_to_element(el).click().perform()
    time.sleep(0.5)


def chip(label):
    """Click the table's chip `label` (a real mouse click)."""
    for b in table().find_elements(By.CSS_SELECTOR, ".vs-chips .chip"):
        if b.text.replace("✓ ", "") == label:
            click_el(b)
            return b
    raise AssertionError(f"no chip {label!r} in {chips()}")


def row(label):
    for b in table().find_elements(By.CSS_SELECTOR, ".vs-list > button"):
        if label in b.text:
            click_el(b)
            return
    raise AssertionError(f"no row {label!r} in {rows()}")


def screen(pt):
    return js(f"""const s = {S}.svgEl, p = s.createSVGPoint(); p.x = arguments[0][0]; p.y = arguments[0][1];
      const q = p.matrixTransform(s.getScreenCTM()), r = {S}.stage.getBoundingClientRect();
      return [Math.round(q.x - (r.left + r.width / 2)), Math.round(q.y - (r.top + r.height / 2))]""", pt)


def click_paper(pt):
    x, y = screen(pt)
    ActionChains(d).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, "#shViewport .sh-stage"), x, y).click().perform()
    time.sleep(0.5)


def dim_text(i):
    return js(f"const x = {S}.allDims().find(q => q.id === arguments[0]); return x ? {S}.dimText(x, {S}.value(x)) : null", i)


def click_dim(i):
    click_el(d.find_element(By.CSS_SELECTOR, f'#shViewport [data-dim="{i}"] text'))


def download(fmt):
    js("window.__dl = null")
    js(f"{S}.export{fmt}()")
    wait("return !!window.__dl", 30)
    return base64.b64decode(js("return window.__dl.b64"))


try:
    d.get(URL)
    js("localStorage.setItem('auto3d-lang', 'cs'); localStorage.removeItem('a3d.box.suggest'); localStorage.removeItem('a3d.leftDock'); sessionStorage.removeItem('a3d.suggestAll')")
    d.get(URL)
    wait("return !!window.__app")
    time.sleep(1)
    call("new_model", name="Deska")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=8)
    call("add_feature", type="hole", face="F2:end", points=[[10, 0]], d=10)
    wait(f"return !!{M}.result?.body && !{M}.inflight")
    js(f"{M}.renderProps()")
    time.sleep(0.4)
    d.find_element(By.CSS_SELECTOR, "#modelExport [data-a=newSheet]").click()
    built()
    js(f"{S}.hooks.download = async (blob, name) => {{ window.__dl = {{ name, size: blob.size, b64: btoa(String.fromCharCode(...new Uint8Array(await blob.arrayBuffer()))) }}; return true; }}")

    # a size: the tolerance list
    dims = json.loads(call("get_sheet"))["dims"]
    w60 = next(x["id"] for x in dims if x["kind"] == "linear" and x["text"] == "60")
    dia = next(x["id"] for x in dims if x["kind"] == "dia")
    click_dim(w60)
    check("the 60 dimension chosen", js(f"return {S}.sel") == w60 and (title() or "").startswith("⟷ 60"), title())
    c = chips()
    print("   tolerance chips:", c, "| rows:", rows())
    check("the tolerance chips", c == ["±0.01", "±0.02", "±0.05", "±0.1", "±0.2", "±0.5", "+0.1/0", "0/−0.1", "+0.2/0", "0/−0.2"], str(c))
    check("Obecná tolerance (ISO 2768-m) ✓ and Vlastní… offered", any("✓ Obecná tolerance (ISO 2768-m)" in r for r in rows()) and any("Vlastní…" in r for r in rows()), str(rows()))
    check("the list fits: no scrollbar in the table", js("const l = document.querySelector('#shViewport .view-suggest .vs-list'); return l.scrollHeight <= l.clientHeight + 1"))
    d.save_screenshot(f"{OUT}/tol_1_chips.png")
    chip("±0.05")
    check("±0.05: the label reads 60 ±0.05", dim_text(w60) == "60 ±0.05" and "60 ±0.05" in js(f"return {S}.svgEl.querySelector('[data-dim=\"{w60}\"]').textContent"), dim_text(w60))
    check("±0.05 marked ✓", "✓ ±0.05" in chips() and not any("✓ Obecná" in r for r in rows()), str(chips()))
    d.save_screenshot(f"{OUT}/tol_2_set.png")

    # a Ø: the fits
    click_dim(dia)
    c = chips()
    print("   fit chips:", c, "| rows:", rows())
    check("the fit chips: holes, then shafts", c == ["H7", "H8", "H9", "H11", "h6", "h7", "g6", "f7", "k6", "m6", "p6"], str(c))
    tip = js("return [...document.querySelectorAll('#shViewport .vs-chips .chip')].find(b => b.textContent === 'H7').title")
    check("H7's tooltip: its deviations at Ø10", tip.startswith("H7: +0.015 / 0 mm"), tip)
    d.save_screenshot(f"{OUT}/tol_3_fits.png")
    chip("H7")
    check("H7: Ø10 H7", "Ø10 H7" in (dim_text(dia) or ""), dim_text(dia))
    check("H7 marked ✓", "✓ H7" in chips(), str(chips()))

    # the title block: the roughness cell's Ra list, then its suggestions
    cell = js(f"const b = {S}.svgEl.querySelector('.sh-title [data-tcell=surface]').getBBox(); return [b.x + b.width / 2, b.y + b.height / 2]")
    click_paper(cell)
    wait("return document.querySelector('#shViewport .sh-tbedit[data-tbedit=surface]')", 5)
    ra = d.find_elements(By.CSS_SELECTOR, "#shViewport .sh-ralist .chip")
    print("   the cell's Ra list:", [b.text for b in ra])
    check("the Drsnost cell: an Ra list under it", [b.text for b in ra] == ["Ra 0.4", "Ra 0.8", "Ra 1.6", "Ra 3.2", "Ra 6.3", "Ra 12.5", "Ra 25"])
    d.save_screenshot(f"{OUT}/tol_4_cell.png")
    click_el(next(b for b in ra if b.text == "Ra 0.8"))
    check("Ra 0.8 from the cell's list", js(f"return {S}.d.texts?.surface") == "Ra 0.8" and not d.find_elements(By.CSS_SELECTOR, "#shViewport .sh-ralist"), js(f"return {S}.d.texts?.surface"))
    click_paper(cell)
    js("document.activeElement?.blur()")
    time.sleep(0.3)
    check("the title block's suggestions: the Ra chips (Ra 0.8 ✓)", "✓ Ra 0.8" in chips(), str(chips()))
    chip("Ra 1.6")
    check("Ra 1.6 from the suggestions: set", js(f"return {S}.d.texts?.surface") == "Ra 1.6" and "Ra 1.6" in js(f"return {S}.svgEl.querySelector('.sh-title').textContent"))

    # an edge: Drsnost povrchu -> Ra 3.2
    pb = js(f"return {S}.paperBox('Front')")
    click_paper([pb[0] + (pb[2] - pb[0]) * 0.3, pb[1]])
    check("the top edge of the front view chosen", js(f"return !!{S}.selGeo?.edge"), title())
    print("   edge rows:", rows(), "| chips:", chips())
    check("Drsnost povrchu offered with the Ra list", "Drsnost povrchu" in table().text and "Ra 3.2" in chips(), table().text)
    d.save_screenshot(f"{OUT}/tol_5_edge.png")
    chip("Ra 3.2")
    rs = js(f"return {S}.d.rough || []")
    check("Ra 3.2: a symbol on that edge, chosen", len(rs) == 1 and rs[0]["ra"] == 3.2 and js(f"return {S}.selRough") == rs[0]["id"] and abs(rs[0]["k"] - 0.3) < 0.1, str(rs))
    rid = rs[0]["id"]
    g = js(f"return {S}.svgEl.querySelector('[data-rough=\"{rid}\"]')?.textContent")
    check("the symbol is drawn with its Ra", g == "Ra 3.2", g)
    check("the title block: Ra 1.6 (✓)", "Ra 1.6 (✓)" in js(f"return {S}.svgEl.querySelector('.sh-title').textContent"))
    check("the symbol's own table", (title() or "").startswith("✓ Ra 3.2") and "✓ Ra 3.2" in chips(), f"{title()} {chips()}")
    row("Výroba: Libovolná")
    chip("Obrobit")
    check("Výroba: Obrobit (the bar)", js(f"return {S}.roughOf('{rid}').proc") == "remove" and js(f"return {S}.svgEl.querySelectorAll('[data-rough=\"{rid}\"] line').length") >= 1)
    at = js(f"return {S}.roughAt({S}.roughOf('{rid}')).T")
    d.save_screenshot(f"{OUT}/tol_6_symbol.png")
    k0 = js(f"return {S}.roughOf('{rid}').k")
    a, b = screen([at[0] + 1, at[1] - 3]), screen([at[0] + 9, at[1] - 3])
    stage = d.find_element(By.CSS_SELECTOR, "#shViewport .sh-stage")
    ActionChains(d).move_to_element_with_offset(stage, *a).click_and_hold().move_by_offset(10, 0).move_by_offset(b[0] - a[0] - 10, 0).release().perform()
    time.sleep(0.5)
    r1 = js(f"return {S}.roughOf('{rid}')")
    check("dragged along its edge: on it still, further right", r1["k"] > k0 + 0.03 and not any(r1.get("off") or []), f"{k0} -> {r1}")
    d.save_screenshot(f"{OUT}/tol_7_sheet.png")

    # the PDF and the DXF
    pdf = download("Pdf")
    open(f"{OUT}/tol_sheet.pdf", "wb").write(pdf)
    text = fitz.open("pdf", pdf)[0].get_text()
    check("the PDF: 60 ±0.05, Ø10 H7, Ra 3.2, Ra 1.6 (✓)", all(s in text for s in ("±0.05", "Ø10 H7", "Ra 3.2", "Ra 1.6")), text[:300].replace("\n", " | "))
    print("   (✓) in the PDF:", "(✓)" in text)
    doc = ezdxf.read(io.StringIO(download("Dxf").decode("utf-8")))
    sym = [e.dxf.text for e in doc.modelspace().query("TEXT[layer=='symbols']")]
    check("the DXF: the symbol on layer symbols", sym == ["Ra 3.2"] and len(doc.modelspace().query("*[layer=='symbols']")) >= 3, str(sym))

    # Delete
    js("document.activeElement?.blur()")
    ActionChains(d).send_keys(Keys.DELETE).perform()
    time.sleep(0.4)
    check("Delete: the symbol gone, (✓) too", not js(f"return ({S}.d.rough || []).length") and "(✓)" not in js(f"return {S}.svgEl.querySelector('.sh-title').textContent"))
    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    time.sleep(0.4)
    check("Ctrl+Z: back", js(f"return ({S}.d.rough || []).length") == 1)

    # the AI
    edge = js(f"return {S}.geo.views.Front.lines.find(l => Math.abs(l.a[0] - l.b[0]) < 1e-6).key")
    r = json.loads(call("sheet_edit", roughness=[{"view": "Front", "edge": edge, "ra": 6.3, "process": "keep"}], dims={w60: {"tol": "0/-0.1"}}, fits={dia: "H11"}))
    print("   AI:", r["done"])
    added = [x for x in r.get("roughness", []) if x["ra"] == 6.3]
    check("the AI adds a symbol Ra 6.3 (no removal) on a side edge", len(added) == 1 and added[0]["process"] == "keep" and added[0]["edge"] == edge, str(r.get("roughness")))
    check("the AI: 60 0/−0.1, Ø10 H11", dim_text(w60) == "60 0/−0.1" and "Ø10 H11" in dim_text(dia), f"{dim_text(w60)} {dim_text(dia)}")
    d.save_screenshot(f"{OUT}/tol_8_ai.png")
    r = json.loads(call("sheet_edit", roughness=[{"id": added[0]["id"], "ra": "Ra 12,5"}]))
    check("the AI changes its Ra (Ra 12,5)", any(x["ra"] == 12.5 for x in r["roughness"]), str(r["roughness"]))
    r = json.loads(call("sheet_edit", roughness=[{"id": added[0]["id"], "remove": True}]))
    check("the AI removes it", len(r["roughness"]) == 1, str(r.get("roughness")))
    print("   a wrong Ra:", call("sheet_edit", roughness=[{"view": "Front", "edge": edge, "ra": "smooth"}])[:70])
    print("   a wrong edge:", call("sheet_edit", roughness=[{"view": "Front", "edge": "nope", "ra": 3.2}])[:70])
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        fails.append("console errors")
    print(f"{len(fails)} failed" + (f": {fails}" if fails else " — all OK"))
    d.quit()
sys.exit(1 if fails else 0)
