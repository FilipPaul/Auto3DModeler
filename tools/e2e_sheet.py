"""Drawing sheets (📄), in headless Edge: a plate 40 × 20 × 10 with 8 holes Ø3 H7 in a grid and a rounding -> 📄 Drawing
sheet: its views and the medium dimensions ("8× Ø3 H7" once, the pitch "3× 10") -> Light: fewer; Full: more; light with the top view medium -> a
dimension chosen and deleted (Del); ↺ brings it back -> dragged lower: its offset changes -> ＋ Dimension: two points
clicked -> a new one with the measured value; a circle clicked -> its Ø -> the part made 15 thick -> the sheet again:
Rev 2, "changed" now, the height reads 15 -> ⬇ PDF: the same texts in the PDF.

  PYTHONIOENCODING=utf-8 py tools/e2e_sheet.py http://127.0.0.1:5199 <out dir>
"""
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
M = "window.__app.modeler"
S = "window.__app.sheet"
H = "window.__app.agentHandlers"


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


def texts():
    return [r.find_element(By.CSS_SELECTOR, "span").text.lstrip("↔↕ ") for r in d.find_elements(By.CSS_SELECTOR, "#shLeft .sh-drow")]


def screen(pt):
    """A paper point (mm) -> the offset from the stage's middle in px (for ActionChains)."""
    return js(f"""const s = {S}.svgEl, p = s.createSVGPoint(); p.x = arguments[0][0]; p.y = arguments[0][1];
      const q = p.matrixTransform(s.getScreenCTM()), r = {S}.stage.getBoundingClientRect();
      return [Math.round(q.x - (r.left + r.width / 2)), Math.round(q.y - (r.top + r.height / 2))]""", pt)


def click_paper(pt):
    x, y = screen(pt)
    ActionChains(d).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, "#shViewport .sh-stage"), x, y).click().perform()
    time.sleep(0.4)


try:
    d.get(URL)
    time.sleep(2)
    js("window.__app.sheet = window.__app.sheet || null")
    call("new_model", name="Plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="hole", face="F2:end", points=[[x, y] for x in (-15, -5, 5, 15) for y in (-5, 5)], d=3, fit="H7")
    call("set_material", material="aluminium", tolerance="m")
    wait(f"return !!{M}.result?.body && !{M}.inflight")
    js(f"{M}.renderProps()")
    d.find_element(By.CSS_SELECTOR, "#modelRight [data-a=newSheet]").click()
    wait(f"return !!{S}.svgEl", 60)
    time.sleep(0.5)
    print("tabs:", [t.text for t in d.find_elements(By.CSS_SELECTOR, "#partTabs .part-tab")])
    med = texts()
    print("medium:", med)
    d.save_screenshot(f"{OUT}/sheet_medium.png")
    for p in ("light", "full"):
        d.find_element(By.CSS_SELECTOR, f"#shViewport [data-preset={p}]").click()
        wait(f"return !{S}.busy && {S}.d.built?.preset === '{p}'", 60)
        time.sleep(0.3)
        print(f"{p}:", len(texts()))
    # light for the sheet, medium for the top view only
    d.find_element(By.CSS_SELECTOR, "#shViewport [data-preset=light]").click()
    wait(f"return !{S}.busy && {S}.d.built?.preset === 'light'", 60)
    n_top = js(f"return {S}.allDims().filter(x => x.view === 'Top').length")
    from selenium.webdriver.support.ui import Select
    Select(d.find_element(By.CSS_SELECTOR, "#shLeft [data-vp=Top]")).select_by_value("medium")
    wait(f"return !{S}.busy && {S}.d.built?.vp === JSON.stringify({{Top: 'medium'}})", 60)
    time.sleep(0.3)
    print("light, the top medium: top dims", n_top, "->", js(f"return {S}.allDims().filter(x => x.view === 'Top').length"),
          "| front stays:", js(f"return {S}.allDims().filter(x => x.view === 'Front').length"))
    Select(d.find_element(By.CSS_SELECTOR, "#shLeft [data-vp=Top]")).select_by_value("")
    wait(f"return !{S}.busy && {S}.d.built?.vp === '{{}}'", 60)
    d.find_element(By.CSS_SELECTOR, "#shViewport [data-preset=medium]").click()
    wait(f"return !{S}.busy && {S}.d.built?.preset === 'medium'", 60)
    time.sleep(0.3)

    n0 = len(texts())
    d.find_elements(By.CSS_SELECTOR, "#shLeft .sh-drow")[0].click()
    time.sleep(0.2)
    ActionChains(d).send_keys(Keys.DELETE).perform()
    time.sleep(0.3)
    print("deleted one:", n0, "->", len(texts()), "| hidden:", js(f"return {S}.d.hidden.length"))
    d.find_element(By.CSS_SELECTOR, "#shLeft [data-a=unhide]").click()
    time.sleep(0.3)
    print("↺ back:", len(texts()))

    # drag the overall width down by 10 mm on the paper
    dim = js(f"const d = {S}.allDims().find(x => x.view === 'Front' && x.a === 'box#x0' && x.b === 'box#x1'); return [d.id, d.off ?? 8]")
    grab = js(f"const r = document.querySelector('[data-dim=\"{dim[0]}\"] .sh-grab').getBBox(); return [r.x + r.width / 2, r.y + r.height / 2]")
    x0, y0 = screen(grab)
    x1, y1 = screen([grab[0], grab[1] + 10])
    stage = d.find_element(By.CSS_SELECTOR, "#shViewport .sh-stage")
    ActionChains(d).move_to_element_with_offset(stage, x0, y0).click_and_hold().move_by_offset(0, (y1 - y0) // 2).move_by_offset(0, (y1 - y0) - (y1 - y0) // 2).release().perform()
    time.sleep(0.4)
    print("dragged the width: off", dim[1], "->", js(f"return {S}.d.dims['{dim[0]}']?.off"))

    # ＋ Dimension: two hole centres in the top view, then a circle
    d.find_element(By.CSS_SELECTOR, "#shViewport [data-a=dim]").click()
    a = js(f"return {S}.P('Top', {S}.geo.views.Top.points['H1:hole:0#c'])") if js(f"return !!{S}.geo.views.Top.points['H1:hole:0#c']") else None
    keys = js(f"return Object.keys({S}.geo.views.Top.points).filter(k => k.endsWith('#c'))")
    pa = js(f"return {S}.P('Top', {S}.geo.views.Top.points[arguments[0]])", keys[0])
    far = max(keys, key=lambda k: js(f"const p = {S}.geo.views.Top.points[arguments[0]], q = {S}.geo.views.Top.points[arguments[1]]; return Math.abs(p[0] - q[0])", keys[0], k))
    pb = js(f"return {S}.P('Top', {S}.geo.views.Top.points[arguments[0]])", far)
    click_paper(pa)
    click_paper(pb)
    u = js(f"return {S}.d.user.map(x => [x.kind, x.dir, {S}.value(x)])")
    print("＋ two points:", u)
    c = js(f"const c = {S}.geo.views.Top.circles[0], C = {S}.P('Top', c.c); return [C[0] + c.r * {S}.scale(), C[1]]")
    click_paper(c)
    print("＋ a circle:", js(f"return {S}.d.user.map(x => [x.kind, {S}.value(x)])"))
    ActionChains(d).send_keys(Keys.ESCAPE).perform()
    d.save_screenshot(f"{OUT}/sheet_edit.png")

    # the part changes: the sheet follows
    rev0, ch0 = js(f"return [{S}.d.rev, {S}.d.changed]")
    sheet_id = js("return window.__app.project.active")
    plate = js("return window.__app.project.parts.find(p => p.kind === 'model').id")
    call("open_part", id=plate)
    time.sleep(1)
    call("edit_feature", id="F2", fields={"d": 15})
    wait(f"return !!{M}.result?.body && !{M}.inflight")
    time.sleep(1.2)
    call("open_part", id=sheet_id)
    wait(f"return !{S}.busy && !!{S}.svgEl && !{S}.d.built.stale", 60)
    time.sleep(0.4)
    h = js(f"const d = {S}.allDims().find(x => x.view === 'Front' && x.a === 'box#y0' && x.b === 'box#y1'); return {S}.value(d)")
    print("the part 15 thick: rev", rev0, "->", js(f"return {S}.d.rev"), "| changed moved on:", js(f"return {S}.d.changed") != ch0, "| the height:", h,
          "| the dragged one kept:", js(f"return {S}.d.dims['{dim[0]}']?.off"), "| user dims:", js(f"return {S}.d.user.map(x => {S}.value(x))"))
    title = js("return [...document.querySelectorAll('#shViewport .sh-title text')].map(t => t.textContent)")
    print("title block:", [t for t in title if "Rev" in t or "ISO" in t or "aluminium" in t or "Plate" in t])

    svg = js(f"return {S}.svg(true)")
    pdf = js("""return fetch('/api/sheet/pdf', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({svg: arguments[0], name: 'x'})})
      .then(r => r.arrayBuffer()).then(b => btoa(String.fromCharCode(...new Uint8Array(b))))""", svg)
    import base64
    text = fitz.open("pdf", base64.b64decode(pdf))[0].get_text()
    print("PDF:", [w for w in ("8× Ø3 H7", "3× 10", "Front", "Top", "ISO 2768-m", "aluminium") if w in text])
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
