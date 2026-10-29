"""Typing straight into the title block (sheet/tbedit.js, SheetEditor.editCell), in Czech, with a REAL mouse and
keyboard: parts Base and Lid in an assembly "Machine" -> the Base's drawing sheet (title block B — ISO 7200) -> a click on
the drawing-number cell: a text box right over it (inside the cell, in its font) -> D-100 + Enter: on the sheet and in
the PDF; the drawing no. does not ask about the other sheets -> Kreslil: typed then Esc: not kept; typed then Tab: kept,
the next field (Kontroloval) gets the text box, and "Přepsat i ve všech listech sestavy „Machine“? (3 listů)" shows ->
Ano: the Machine's sheet keeps it for the set, every page of the set's PDF says "F. Paul" -> the mass cell is computed:
no text box, its tooltip in the hint -> the suggestions' row "Číslo výkresu" opens the cell's text box -> the panel's
field still works -> the AI's sheet_edit texts + all_sheets -> every style (A … E, Modern, Modern strip): a click on Kreslil types into it. Screenshots to <out dir>.

  PYTHONIOENCODING=utf-8 py tools/e2e_title_inline.py http://127.0.0.1:5199 <out dir>
"""
import base64
import json
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
    wait(f"return !{S}.busy && !!{S}.svgEl && !{S}.d.built?.stale", 90)
    time.sleep(0.5)


def click_cell(key):
    """A real click in the middle of title-block cell `key`."""
    el = d.find_element(By.CSS_SELECTOR, f"#shViewport .sh-title [data-tcell={key}]")
    ActionChains(d).move_to_element(el).click().perform()
    time.sleep(0.4)


def box():
    """The open text box of a title-block cell: [its field, its value] or None."""
    return js("const i = document.querySelector('#shViewport .sh-tbedit'); return i ? [i.dataset.tbedit, i.value, document.activeElement === i] : null")


def title_text():
    return js(f"return [...{S}.svgEl.querySelectorAll('.sh-title text')].map(t => t.textContent).join(' | ')")


def pdf_text(svgs):
    b64 = js("""return fetch('/api/sheet/pdf', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({svgs: arguments[0], name: 'x'})})
      .then(r => r.arrayBuffer()).then(b => { let s = ''; const u = new Uint8Array(b); for (let i = 0; i < u.length; i += 8192) s += String.fromCharCode(...u.subarray(i, i + 8192)); return btoa(s); })""", svgs)
    return [p.get_text() for p in fitz.open("pdf", base64.b64decode(b64))]


try:
    d.get(URL)
    js("localStorage.setItem('auto3d-lang', 'cs'); localStorage.removeItem('a3d.box.suggest'); sessionStorage.removeItem('a3d.suggestAll')")
    d.get(URL)
    wait("return !!window.__app")
    time.sleep(1)
    for name, w, h, t in (("Base", 80, 50, 10), ("Lid", 60, 40, 4)):
        call("new_model", name=name)
        call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": w, "h": h}}])
        call("add_feature", type="extrude", sketch="F1", d=t)
    call("new_assembly", name="Machine")
    call("insert_part", part="Base")
    call("insert_part", part="Lid")
    time.sleep(0.8)
    base = next(p["id"] for p in json.loads(call("list_parts")) if p["name"] == "Base")
    call("sheet_open", part=base)
    built()
    check("the Base's sheet: title block B", js(f"return {S}.tb().style") == "B", js(f"return {S}.tb().style"))
    print("   cells to type into:", js(f"return {S}.cellKeys()"))
    print("   computed cells:", js(f"return [...{S}.svgEl.querySelectorAll('.sh-title [data-ro]')].map(e => e.dataset.tcell)"))

    # 1. a click on the drawing number: a text box over the cell, D-100 + Enter
    click_cell("number")
    b = box()
    check("a click on Číslo výkresu: a text box in its place, focused", b is not None and b[0] == "number" and b[2], str(b))
    r = js("""const c = document.querySelector('#shViewport .sh-title [data-tcell=number]').getBoundingClientRect(), i = document.querySelector('#shViewport .sh-tbedit').getBoundingClientRect();
      return [Math.round(c.left), Math.round(c.top), Math.round(c.right), Math.round(c.bottom), Math.round(i.left), Math.round(i.top), Math.round(i.right), Math.round(i.bottom)]""")
    check("the text box lies on the cell", abs(r[0] - r[4]) <= 2 and r[5] >= r[1] - 2 and r[7] <= r[3] + 2, str(r))
    fs = js("return getComputedStyle(document.querySelector('#shViewport .sh-tbedit')).fontFamily")
    check("in the title block's font", "Plex" in fs, fs)
    d.save_screenshot(f"{OUT}/title_inline_1_box.png")
    ActionChains(d).send_keys("D-100").send_keys(Keys.ENTER).perform()
    time.sleep(0.5)
    check("Enter: the text box closed, D-100 on the sheet", box() is None and "D-100" in title_text() and js(f"return {S}.d.texts?.number") == "D-100", title_text()[:120])
    check("the drawing no. does not ask about the other sheets", not js("return !!document.querySelector('#shViewport .sh-tbask')"))
    pages = pdf_text([js(f"return {S}.svg(true)")])
    check("the PDF has D-100", "D-100" in pages[0])

    # 2. Esc: as it was
    click_cell("drawn")
    ActionChains(d).send_keys("Nikdo").send_keys(Keys.ESCAPE).perform()
    time.sleep(0.4)
    check("Esc: the text box closed, nothing typed kept", box() is None and "Nikdo" not in title_text() and not js(f"return {S}.d.texts?.drawn"))
    check("Esc did not leave the title block chosen state broken", js(f"return {S}.selTitle") is not None)

    # 3. Kreslil + Tab: kept, the next field's box, the question about the set
    click_cell("drawn")
    ActionChains(d).send_keys("F. Paul").send_keys(Keys.TAB).perform()
    time.sleep(0.6)
    b = box()
    check("Tab: Kreslil kept, the next field (Kontroloval) has the text box", js(f"return {S}.d.texts?.drawn") == "F. Paul" and b and b[0] == "checked" and b[2], str(b))
    q = js("const q = document.querySelector('#shViewport .sh-tbask'); return q ? q.innerText : null")
    check("the question: Přepsat i ve všech listech sestavy „Machine“? (3 listů)", q is not None and "Přepsat i ve všech listech sestavy „Machine“?" in q and "(3 listů)" in q and "Jen tady" in q and "neptat se znovu" in q, repr(q))
    d.save_screenshot(f"{OUT}/title_inline_2_ask.png")
    ActionChains(d).send_keys(Keys.ESCAPE).perform()  # (Kontroloval left as it was)
    time.sleep(0.3)
    check("Esc in Kontroloval: its box closed, the question still there", box() is None and js("return !!document.querySelector('#shViewport .sh-tbask')"))
    yes = d.find_element(By.CSS_SELECTOR, "#shViewport .sh-tbask [data-a=all]")
    check("its buttons in Czech", yes.text == "Ano", yes.text)
    ActionChains(d).move_to_element(yes).click().perform()
    time.sleep(0.8)
    check("Ano: the question gone", not js("return !!document.querySelector('#shViewport .sh-tbask')"))
    mach = next(p["id"] for p in json.loads(call("list_parts")) if p["name"] == "Machine")
    st = js("""const P = window.__app.project; const p = P.parts.find(q => q.kind === 'sheet' && typeof q.data === 'object' && q.data.source === arguments[0]); return p ? p.data.setTexts : null""", mach)
    check("the Machine's sheet keeps Kreslil for the set", (st or {}).get("drawn") == "F. Paul", str(st))
    check("still on the Base's sheet", "F. Paul" in title_text())
    svgs = js("""const S = window.__app.sheet, P = window.__app.project;
      return S.drawingSet(arguments[0], { kindOf: (id) => P.parts.find(q => q.id === id)?.kind,
        sheetOf: (id) => { const p = P.parts.find(q => q.kind === 'sheet' && (q.data === 'live' ? S.d?.source === id : q.data?.source === id)); return !p ? null : p.data === 'live' ? S.payload() : p.data; },
        bought: () => false, massOf: () => null }).then(s => s.svgs)""", mach)
    pages = pdf_text(svgs)
    check("every page of the set's PDF says F. Paul", len(pages) == 3 and all("F. Paul" in p for p in pages), f"{len(pages)} pages: {['F. Paul' in p for p in pages]}")
    check("the drawing no. stayed the Base's only", sum("D-100" in p for p in pages) == 1, str(["D-100" in p for p in pages]))

    # 4. a computed cell: no text box, its tooltip in the hint
    click_cell("mass")
    hint = js("const h = document.querySelector('#shViewport .sh-hint'); return h.hidden ? '' : h.textContent")
    check("Hmotnost is computed: no text box, the hint says why", box() is None and "Hmotnost" in hint, hint)
    tip = js("return document.querySelector('#shViewport .sh-title [data-tcell=mass] title')?.textContent")
    check("its tooltip in Czech", tip and "spočítaná" in tip, tip)
    mat = js("return document.querySelector('#shViewport .sh-title [data-tcell=material]')?.dataset.ro")
    check("a part's material is computed too (from its model)", mat == "1")
    d.save_screenshot(f"{OUT}/title_inline_3_computed.png")

    # 5. the suggestions' row opens the cell's text box
    js("document.querySelector('#shViewport .sh-tbedit')?.blur()")
    rowbtn = next((b for b in d.find_elements(By.CSS_SELECTOR, "#shViewport .view-suggest .vs-list button") if "Číslo výkresu" in b.text), None)
    check("the title block's suggestions have Číslo výkresu", rowbtn is not None)
    if rowbtn:
        ActionChains(d).move_to_element(rowbtn).click().perform()
        time.sleep(0.5)
        b = box()
        check("the row opens the cell's text box (no dialog)", b and b[0] == "number" and b[1] == "D-100" and b[2] and not js("return !!document.querySelector('.choose.ask')"), str(b))
        ActionChains(d).send_keys(Keys.ESCAPE).perform()
        time.sleep(0.3)

    # 6. the panel's field still works
    el = d.find_element(By.CSS_SELECTOR, "#shRight [data-text=note]")
    el.clear()
    el.send_keys("Hrany srazit 0,5")
    el.send_keys(Keys.ENTER)
    time.sleep(0.5)
    check("the panel's Poznámka still works", js(f"return {S}.d.texts?.note") == "Hrany srazit 0,5")

    # 7. the AI: sheet_edit texts with all_sheets — the project-wide ones to the set, the drawing no. stays here
    out = json.loads(call("sheet_edit", texts={"company": "RAFIONTECH s.r.o.", "number": "D-101"}, all_sheets=True))
    print("   the AI:", out.get("done"))
    st = js("""const P = window.__app.project; const p = P.parts.find(q => q.kind === 'sheet' && typeof q.data === 'object' && q.data.source === arguments[0]); return p ? p.data.setTexts : null""", mach)
    check("the AI's all_sheets: the company for the set, the drawing no. only here", (st or {}).get("company") == "RAFIONTECH s.r.o." and "number" not in (st or {}) and js(f"return {S}.d.texts?.number") == "D-101", str(st))

    # 8. every style: a click on Kreslil types into it
    for style in ("A", "C", "D", "E", "block", "strip", "B"):
        js(f"{S}.d.tb = {{ ...({S}.d.tb || {{}}), titleStyle: arguments[0] }}; {S}.commit()", style)
        built()
        keys = js(f"return {S}.cellKeys()")
        if "drawn" in keys:
            click_cell("drawn")
            ActionChains(d).send_keys(f"Kreslil {style}").send_keys(Keys.ENTER).perform()  # (the text box opens with its text chosen)
            time.sleep(0.5)
            js("document.querySelector('#shViewport .sh-tbask [data-a=here]')?.click()")
            ok = js(f"return {S}.d.texts?.drawn") == f"Kreslil {style}"
        else:
            ok = True
        click_cell("number")
        nb = box()
        ActionChains(d).send_keys(Keys.ESCAPE).perform()
        time.sleep(0.2)
        check(f"style {style}: Kreslil typed in place, the number's cell opens", ok and nb and nb[0] == "number", f"{keys} {nb}")
        if style in ("A", "block"):
            click_cell("number")
            d.save_screenshot(f"{OUT}/title_inline_style_{style}.png")
            ActionChains(d).send_keys(Keys.ESCAPE).perform()
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        fails.append("console errors")
    d.quit()
print("FAILED:" if fails else "ALL OK", fails if fails else "")
sys.exit(1 if fails else 0)
