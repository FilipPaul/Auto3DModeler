"""An assembly's drawing sheet (📄 Drawing in the assembly's toolbar), in headless Edge: Machine = Base + Lid -> the button
-> a sheet tab: the assembly's views (front, top, iso), its parts list (Base, Lid) and balloons, no presets / size check
-> the balloons apart, one dragged (kept) -> Pages: Machine, Base, Lid; the Lid's page opens its sheet and shows the
same Pages (Lid marked) -> 📚 All pages: 3 pages one below the other, scrolling marks the page in sight, a click in
Pages goes to it, a double-click opens a page to edit -> a dimension of the user's and a note typed -> back in the assembly the Lid moved -> the sheet again: Rev 2 -> the
drawing set (📄 Drawings (PDF)): its first page is this sheet, with the note -> the AI's sheet_open of an assembly.

  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_sheet.py http://127.0.0.1:5199 <out dir>
"""
import json
import os
import sys
import time
import urllib.request

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


def ai(tool, **args):
    req = urllib.request.Request(f"{URL}/api/agent/call", data=json.dumps({"tool": tool, "args": args}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        res = json.loads(r.read())
    return ("ERROR " if res.get("isError") else "") + "".join(c.get("text", "") for c in res.get("content", []))


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.15)
    raise TimeoutError(script)


try:
    d.get(URL)
    time.sleep(2)
    for name, w, h, th in (("Base", 80, 50, 10), ("Lid", 60, 40, 4)):
        ai("new_model", name=name)
        ai("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": w, "h": h}}])
        ai("add_feature", type="extrude", sketch="F1", d=th)
    ai("new_assembly", name="Machine")
    print("empty: the button greyed", not d.find_element(By.CSS_SELECTOR, "#asmViewport [data-a=sheet]").is_enabled())
    ai("insert_part", part="Base")
    ai("insert_part", part="Lid")
    time.sleep(1)
    asm = js("return window.__app.project.active")
    d.find_element(By.CSS_SELECTOR, "#asmViewport [data-a=sheet]").click()
    wait(f"return !!{S}.svgEl && !{S}.busy && !!{S}.d.asm", 60)
    time.sleep(0.5)
    print("the sheet:", js("return [window.__app.state.workspace, window.__app.project.current.name]"))
    print("  parts list:", js(f"return {S}.d.asm.rows.map(r => [r.pos, r.name, r.qty])"), "| balloons:", len(d.find_elements(By.CSS_SELECTOR, "#shViewport .sh-bom circle[r='3.4']")))
    print("  views:", js(f"return ['Front', 'Top', 'Right', 'Iso'].filter(v => !{S}.d.off[v])"), "| presets shown:", len(d.find_elements(By.CSS_SELECTOR, "#shViewport [data-preset]")),
          "| check shown:", len(d.find_elements(By.CSS_SELECTOR, "#shLeft [data-a=allMissing], #shLeft .sh-ok")))
    # the balloons apart; one dragged
    cs = js("return [...document.querySelectorAll('#shViewport [data-balloon] circle')].map(c => [+c.getAttribute('cx'), +c.getAttribute('cy')])")
    print("  balloons apart:", all(((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5 > 8 for i, (x1, y1) in enumerate(cs) for (x2, y2) in cs[i + 1:]))
    b0 = cs[0]
    def scr(pt):
        return js(f"""const s = {S}.svgEl, p = s.createSVGPoint(); p.x = arguments[0][0]; p.y = arguments[0][1];
          const q = p.matrixTransform(s.getScreenCTM()), r = {S}.stage.getBoundingClientRect(); return [Math.round(q.x - (r.left + r.width / 2)), Math.round(q.y - (r.top + r.height / 2))]""", pt)
    x0, y0 = scr(b0)
    x1, y1 = scr([b0[0] - 20, b0[1] + 10])
    stage = d.find_element(By.CSS_SELECTOR, "#shViewport .sh-stage")
    ActionChains(d).move_to_element_with_offset(stage, x0, y0).click_and_hold().move_by_offset((x1 - x0) // 2, (y1 - y0) // 2).move_by_offset((x1 - x0) - (x1 - x0) // 2, (y1 - y0) - (y1 - y0) // 2).release().perform()
    time.sleep(0.4)
    print("  balloon 1 dragged:", js(f"return {S}.d.balloons?.['1']"), "(was", [round(v, 1) for v in b0], ")")

    # Pages: the set from here; a part's page opens its sheet, and shows the same set
    print("  pages:", [b.text.replace("\n", " ") for b in d.find_elements(By.CSS_SELECTOR, "#shLeft .sh-page")])
    next(b for b in d.find_elements(By.CSS_SELECTOR, "#shLeft .sh-page") if "Lid" in b.text).click()
    wait(f"return !!{S}.svgEl && !{S}.busy && !{S}.d.asm", 60)
    print("  Lid's page:", js("return window.__app.project.current.name"), "| its Pages:", [b.text.replace("\n", " ") for b in d.find_elements(By.CSS_SELECTOR, "#shLeft .sh-page")],
          "| marked:", [b.text.replace("\n", " ") for b in d.find_elements(By.CSS_SELECTOR, "#shLeft .sh-page.on")])
    d.find_element(By.CSS_SELECTOR, "#shLeft .sh-page").click()
    wait(f"return !!{S}.svgEl && !{S}.busy && !!{S}.d.asm", 60)
    print("  back:", js("return window.__app.project.current.name"), "| the balloon kept:", js(f"return {S}.d.balloons?.['1']"))

    # 📚 All pages: the set one below the other; scrolling marks the page in sight; a click in Pages goes there
    d.find_element(By.CSS_SELECTOR, "#shViewport [data-a=setview]").click()
    wait("return document.querySelectorAll('#shViewport .sh-sheetpage').length === 3", 60)
    time.sleep(0.4)
    print("📚 All pages:", len(d.find_elements(By.CSS_SELECTOR, "#shViewport .sh-sheetpage")), "pages | the status:", d.find_element(By.CSS_SELECTOR, "#shViewport .sh-status").text)
    print("  the balloon on page 1 too:", js("return !!document.querySelector('#shViewport .sh-sheetpage [data-balloon=\"1\"]')"))
    js(f"{S}.stage.scrollTop = {S}.stage.scrollHeight")
    time.sleep(0.5)
    print("  scrolled to the end: marked", [b.text.replace("\n", " ") for b in d.find_elements(By.CSS_SELECTOR, "#shLeft .sh-page.on")])
    next(b for b in d.find_elements(By.CSS_SELECTOR, "#shLeft .sh-page") if "Machine" in b.text).click()
    time.sleep(1.2)
    print("  Pages → Machine: at the top", js(f"return {S}.stage.scrollTop") < 50)
    from selenium.webdriver.common.action_chains import ActionChains as AC
    AC(d).double_click(d.find_elements(By.CSS_SELECTOR, "#shViewport .sh-sheetpage")[2]).perform()
    wait(f"return !!{S}.svgEl && !{S}.busy && !{S}.setMode", 60)
    print("  double-click page 3:", js("return window.__app.project.current.name"), "| editing:", js(f"return !{S}.setMode && !!{S}.svgEl"))
    next(b for b in d.find_elements(By.CSS_SELECTOR, "#shLeft .sh-page") if "Machine" in b.text).click()
    wait(f"return !!{S}.svgEl && !{S}.busy && !!{S}.d.asm", 60)
    js(f"{S}.addFor({{view: 'Front', a: 'box#y0', b: 'box#y1', dir: 'v'}})")
    js(f"{S}.sel = null; {S}.render()")
    el = d.find_element(By.CSS_SELECTOR, "#shRight [data-text=note]")
    el.send_keys("Assemble dry")
    el.send_keys(Keys.ENTER)
    time.sleep(0.4)
    d.save_screenshot(f"{OUT}/assembly_sheet.png")
    rev = js(f"return {S}.d.rev")

    ai("open_part", id=asm)
    time.sleep(1)
    ai("place_part", part="I2", z=30)
    time.sleep(1.5)
    sheet_id = next(p["id"] for p in json.loads(ai("list_parts")) if p["kind"] == "drawing sheet")
    ai("open_part", id=sheet_id)
    wait(f"return !!{S}.svgEl && !{S}.busy && !{S}.d.built.stale", 60)
    time.sleep(0.4)
    print("the Lid moved: rev", rev, "->", js(f"return {S}.d.rev"), "| the user's height:", js(f"return {S}.value({S}.d.user[0])"), "| note kept:", js(f"return {S}.d.texts?.note"))

    ai("open_part", id=asm)
    time.sleep(1)
    out = ai("export", format="pdf", path=OUT)
    print("the set:", out[:110])
    pdf = os.path.join(OUT, "Machine — drawings.pdf")
    p1 = fitz.open(pdf)[0].get_text()
    print("  page 1 has the note:", "Assemble dry" in p1, "| parts list:", "Part number" in p1)
    s = json.loads(ai("sheet_open", part=asm))
    print("the AI's sheet_open of the assembly:", s["part"], "| dims:", [x["text"] for x in s["dims"]])
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
