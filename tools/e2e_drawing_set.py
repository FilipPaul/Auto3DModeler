"""An assembly's drawing set (one PDF), in headless Edge: parts Base, Lid, Pin; a sub-assembly "Lid unit" (Lid + 2 Pins);
the final assembly "Machine" (Base + Lid unit + a bought screw from the library). The Base has its own drawing sheet
with a dimension of the user's. -> 📄 Drawings (PDF) in the Machine's panel -> pages in order: Machine (its views, the
parts list with Base, ◇ Lid unit, the screw as bought, balloons), Lid unit (Lid, Pin ×2), Lid, Pin, Base (with the
user's dimension); the parts numbered once for the whole set (Machine 1–3, the Lid unit's go on: 4, 5); every page names itself, what it is in and "Sheet n / N" -> the AI's export pdf: the same set.
Then in Czech, from the sheets' suggestions tables (sheet/sheetsuggest.js): the Machine's sheet with a BOM page -> nothing
chosen: "📑 Všechny listy sestavy (6)" in the top rows (also in the title block's table, with "⤓ PDF všech listů") -> a
click: all 6 sheets on screen (5 drawings + the BOM page) and the table goes from sheet to sheet (▼ Další list) and back;
get_sheet's drawing_set; the Base's sheet: "📑 Listy sestavy „Machine“" -> the set, the Base's page in sight.

  PYTHONIOENCODING=utf-8 py tools/e2e_drawing_set.py http://127.0.0.1:5199 <out dir>
"""
import json
import os
import sys
import time
import urllib.request

import fitz
from selenium import webdriver
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
A = "window.__app.assembly"
S = "window.__app.sheet"
fails = []


def check(name, ok, info=""):
    print(("OK  " if ok else "FAIL"), name, info)
    if not ok:
        fails.append(name)


def wait(script, t=90):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(script)


def rows():
    return js("return [...document.querySelectorAll('#shViewport .view-suggest .vs-list button')].map(b => b.textContent.replace(/\\s+/g, ' ').trim())") or []


def row(label):
    for b in d.find_elements(By.CSS_SELECTOR, "#shViewport .view-suggest .vs-list button"):
        if label in b.text:
            b.click()
            time.sleep(0.6)
            return
    raise AssertionError(f"no row {label!r} in {rows()}")


def ai(tool, **args):
    req = urllib.request.Request(f"{URL}/api/agent/call", data=json.dumps({"tool": tool, "args": args}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        res = json.loads(r.read())
    return ("ERROR " if res.get("isError") else "") + "".join(c.get("text", "") for c in res.get("content", []))


def pages(path):
    return [p.get_text() for p in fitz.open(path)]


try:
    d.get(URL)
    time.sleep(2)
    for name, w, h, t in (("Base", 80, 50, 10), ("Lid", 60, 40, 4)):
        ai("new_model", name=name)
        ai("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": w, "h": h}}])
        ai("add_feature", type="extrude", sketch="F1", d=t)
    ai("add_feature", type="hole", face="F2:end", points=[[-20, 0], [20, 0]], d=6)
    ai("new_model", name="Pin")
    ai("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 6}}])
    ai("add_feature", type="extrude", sketch="F1", d=12)
    # the Base's own sheet, with a dimension of the user's
    base = next(p["id"] for p in json.loads(ai("list_parts")) if p["name"] == "Base")
    json.loads(ai("sheet_open", part=base))
    pts = json.loads(ai("get_sheet", points="Front"))["Front"]["points"]
    ends = [p for p in pts if p["key"].endswith("#0") or p["key"].endswith("#1")]
    a, b = ends[0]["key"], max(ends, key=lambda p: abs(p["at"][1] - ends[0]["at"][1]))["key"]
    print("the Base's own dimension:", json.loads(ai("sheet_edit", add=[{"view": "Front", "a": a, "b": b, "dir": "v", "pre": "MY"}]))["done"])

    ai("new_assembly", name="Lid unit")
    for p in ("Lid", "Pin", "Pin"):
        ai("insert_part", part=p)
    ai("new_assembly", name="Machine")
    ai("insert_part", part="Base")
    ai("insert_part", part="Lid unit")
    print("a bought screw:", ai("library_add", item="iso4762", size="M3", length=10, to="assembly")[:50])
    time.sleep(1)
    js(f"{A}.sel = null; {A}.render()")
    time.sleep(0.4)
    btn = d.find_element(By.CSS_SELECTOR, "#asmBom [data-a=drawingSet]")
    print("the button:", btn.text)
    # the PDF as the button makes it (the download is caught in the page)
    res = js("""return window.__app.sheet.drawingSet(window.__app.project.active, {
        kindOf: (id) => window.__app.project.parts.find(q => q.id === id)?.kind,
        sheetOf: (id) => { const p = window.__app.project.parts.find(q => q.kind === 'sheet' && typeof q.data === 'object' && q.data?.source === id); return p ? p.data : null; },
        bought: (data, name) => !!data?.standard || /screw|nut|insert/.test(name) }).then(s => s.pages)""")
    print("pages (the button's way):", res)
    nums = js("""const S = window.__app.sheet, P = window.__app.project, ctx = { kindOf: (id) => P.parts.find(q => q.id === id)?.kind, sheetOf: () => null, bought: (d, n) => /screw|ISO/.test(n) };
        const id = (n) => P.parts.find(q => q.name === n).id;
        return Promise.all(['Machine', 'Lid unit'].map(n => S.assemblyPage(id(n), ctx).then(r => r.rows.map(x => [x.pos, x.name]))))""")
    print("one numbering for the set: Machine", nums[0], "| Lid unit", nums[1])
    out = ai("export", format="pdf", path=OUT)
    print("the AI's export:", out[:160])
    path = os.path.join(OUT, "Machine — drawings.pdf")
    texts = pages(path)
    print("PDF pages:", len(texts))
    for i, t in enumerate(texts):
        first = [w for w in ("Machine", "Lid unit", "Lid", "Pin", "Base") if w in t]
        print(f"  {i + 1}:", "Sheet", f"{i + 1} / {len(texts)}" in t, "| names:", first, "| sub-assembly" if "Sub-assembly" in t else "", "| MY" if "MY" in t else "",
              "| list:" if "Part number" in t else "", [w for w in ("◇ Lid unit", "ISO 4762", "bought") if w in t])
    d.save_screenshot(f"{OUT}/drawing_set.png")
    page1 = fitz.open(path)[0]
    page1.get_pixmap(dpi=60).save(f"{OUT}/drawing_set_p1.png")

    # ---- the sheets' suggestions: 📑 all sheets of the assembly (in Czech)
    d.find_element(By.ID, "langBtn").click()
    time.sleep(0.5)
    js("localStorage.removeItem('a3d.box.suggest'); localStorage.removeItem('a3d.leftDock'); sessionStorage.removeItem('a3d.suggestAll')")
    ai("sheet_open", part="Machine")
    wait(f"return !{S}.busy && !!{S}.svgEl")
    js(f"{S}.d.bomPage = 'summary'; {S}.commit()")  # (a BOM page after the assembly's)
    wait(f"return !{S}.busy && !!{S}.svgEl")
    js(f"{S}.clearSel(); {S}.render()")
    time.sleep(0.6)
    r = rows()
    top = r[:3]
    check("assembly sheet: 📑 Všechny listy sestavy (6) in the top rows", any("Všechny listy sestavy (6)" in x for x in top), str(r))
    check("assembly sheet: ⤓ PDF všech listů offered", any("PDF všech listů" in x for x in r), str(r))
    gs = json.loads(ai("get_sheet"))["drawing_set"]
    check("get_sheet drawing_set: Machine, 6 sheets, 5 drawings", gs["assembly"] == "Machine" and gs["sheets"] == 6 and len(gs["pages"]) == 5, str(gs)[:200])
    d.save_screenshot(f"{OUT}/drawing_set_suggest.png")
    js(f"{S}.clearSel(); {S}.selTitle = true; {S}.render()")
    time.sleep(0.5)
    r = rows()
    check("title block's table: 📑 Všechny listy sestavy first", "Všechny listy sestavy (6)" in r[0], str(r))
    js(f"{S}.clearSel(); {S}.render()")
    time.sleep(0.5)
    row("Všechny listy sestavy")
    n = wait(f"const n = document.querySelectorAll('#shViewport .sh-sheetpage').length; return n > 1 && n", 120)
    check("the row opens all sheets: 6 (Machine, BOM, Lid unit, Lid, Pin, Base)", n == 6 and js(f"return {S}.setMode"), f"{n} pages")
    r = rows()
    check("in All pages: ▼ Další list: Lid unit, ↩ Zpět na tento list", any("Další list: Lid unit" in x for x in r) and any("Zpět na tento list" in x for x in r), str(r))
    d.save_screenshot(f"{OUT}/drawing_set_all.png")
    row("Další list")
    time.sleep(1.2)
    check("▼ Další list scrolls to the Lid unit's sheet", js(f"return {S}.seen") == js("return window.__app.project.parts.find(q => q.name === 'Lid unit').id"), js(f"return {S}.seen"))
    check("then the table offers ▲ Předchozí list: Machine", any("Předchozí list: Machine" in x for x in rows()), str(rows()))
    d.save_screenshot(f"{OUT}/drawing_set_next.png")
    row("Zpět na tento list")
    check("↩ back to the Machine's sheet alone", not js(f"return {S}.setMode") and wait(f"return !!{S}.svgEl", 30), "")
    # a part's sheet in the assembly: 📑 Listy sestavy „Machine“
    ai("sheet_open", part="Base")
    wait(f"return !{S}.busy && !!{S}.svgEl && window.__app.project.parts.find(q => q.id === {S}.d.source)?.name === 'Base'")
    js(f"{S}.clearSel(); {S}.render()")
    time.sleep(0.5)
    r = rows()
    check("part sheet: 📑 Listy sestavy „Machine“ in the top rows", any("Listy sestavy „Machine“" in x for x in r[:3]), str(r))
    row("Listy sestavy „Machine“")
    n = wait(f"const n = document.querySelectorAll('#shViewport .sh-sheetpage').length; return n > 1 && n", 120)
    time.sleep(1)
    base = js("return window.__app.project.parts.find(q => q.name === 'Base').id")
    st = js(f"const s = {S}.stage, p = s.querySelector('[data-pageid=\"' + arguments[0] + '\"]'); return p && p.getBoundingClientRect().top < s.getBoundingClientRect().top + s.clientHeight / 3", base)  # (the last page: as high as the scroll goes)
    check("…goes to the set (6 sheets), the Base's page in sight", n == 6 and st, f"{n} pages, in sight {st}")
    d.save_screenshot(f"{OUT}/drawing_set_part.png")
    print("AI all_pages:", ai("sheet_edit", all_pages=False)[:120])
    check("sheet_edit all_pages false: this sheet alone", not js(f"return {S}.setMode"))
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        fails.append("console errors")
    print(f"{len(fails)} failed" + (f": {fails}" if fails else " — all OK"))
    d.quit()
sys.exit(1 if fails else 0)
