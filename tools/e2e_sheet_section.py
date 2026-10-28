"""Section A–A on a part's drawing sheet, in headless Edge: a 40 × 20 × 10 block with a Ø6 hole through its middle ->
its sheet -> ☐ Section A–A ticked: a "Section A–A" view in the right view's place (the right view hidden), its cut faces
hatched (lines), the cut marked A–A on the front view; its edges can be dimensioned (＋ Dimension on its height) ->
Ctrl+Z: gone -> a picture of the sheet.

  PYTHONIOENCODING=utf-8 py tools/e2e_sheet_section.py http://127.0.0.1:5199 <out dir>
"""
import base64
import json
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
S = "window.__app.sheet"
H = "window.__app.agentHandlers"


def wait(script, t=120):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(script)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def built():
    time.sleep(0.5)
    wait(f"return !{S}.busy && {S}.d?.built")
    time.sleep(0.5)


def picture(name):
    shot = js(f"""const svg = new XMLSerializer().serializeToString({S}.svgEl);
      return new Promise((ok) => {{ const img = new Image(); img.onload = () => {{ const c = document.createElement('canvas'); c.width = 1400; c.height = Math.round(1400 * img.height / img.width);
        const x = c.getContext('2d'); x.fillStyle = '#fff'; x.fillRect(0, 0, c.width, c.height); x.drawImage(img, 0, 0, c.width, c.height); ok(c.toDataURL('image/png').split(',')[1]); }};
        img.src = URL.createObjectURL(new Blob([svg], {{ type: 'image/svg+xml' }})); }});""")
    open(f"{OUT}/{name}", "wb").write(base64.b64decode(shot))


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Holed block")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=6)
    print("sheet_open:", json.loads(call("sheet_open", part="Holed block"))["preset"])
    wait(f"return !!{S}.svgEl")
    built()
    box = d.find_element(By.CSS_SELECTOR, "[data-sec]")
    print("☐ Section A–A:", box.is_selected(), "| views", js(f"return {S}.drawn()"))
    box.click()
    built()
    print("ticked: views", js(f"return {S}.drawn()"), "| hatch lines:", js("return document.querySelectorAll('#shViewport [data-view=Section] line').length"),
          "| its name:", js("return [...document.querySelectorAll('#shViewport [data-view=Section] text')].map(e => e.textContent)"),
          "| A marks:", js("return [...document.querySelectorAll('#shViewport text')].filter(e => e.textContent === 'A').length"))
    # its height dimensioned: an upright edge of the section, clicked twice
    up = js(f"const g = {S}.geo.views.Section; const l = g.lines.find(l => Math.abs(l.a[0] - l.b[0]) < 1e-6 && Math.abs(l.a[1] - l.b[1]) > 5); return l && [l.key, l.a, l.b];")
    js(f"{S}.action('dim')")
    for _ in range(2):
        js(f"const l = {S}.geo.views.Section.lines.find(x => x.key === arguments[0]); {S}.clickDim({S}.P('Section', [(l.a[0] + l.b[0]) / 2, (l.a[1] + l.b[1]) / 2]));", up[0])
        time.sleep(0.2)
    js(f"{S}.action('dim')")
    print("a dimension on the section:", js(f"const d = {S}.allDims().find(x => x.id === {S}.sel); return d && [d.view, {S}.dimText(d, {S}.value(d))];"))
    picture("sheet_section.png")
    js(f"{S}.history.go(-1)")
    js(f"{S}.history.go(-1)")
    built()
    print("Ctrl+Z ×2: views", js(f"return {S}.drawn()"), "| section on:", js(f"return !!{S}.d.section"))
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
