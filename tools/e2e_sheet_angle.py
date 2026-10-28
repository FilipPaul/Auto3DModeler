"""Angle dimensions on the drawing sheet, in headless Edge: a plate whose outline has a slanted edge -> its sheet ->
＋ Dimension, a click on the slanted edge and one on the upright edge it meets: an angle "123.7°" (an arc round their
corner) -> the AI's sheet_edit add {view, edges}: the same angle; two parallel edges refused -> get_sheet lists them
(kind ang) -> a screenshot of the Top view.

  PYTHONIOENCODING=utf-8 py tools/e2e_sheet_angle.py http://127.0.0.1:5199 <out dir>
"""
import base64
import json
import math
import sys
import time

from selenium import webdriver

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


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Slant plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"polyline": {"points": [[0, 0], [40, 0], [40, 10], [10, 30], [0, 30]]}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    print("sheet_open:", json.loads(call("sheet_open", part="Slant plate"))["preset"])
    wait(f"return !!{S}.svgEl")
    lines = js(f"return {S}.geo.views.Top.lines.map(l => [l.key, l.a, l.b])")
    slant = next(k for k, a, b in lines if abs(a[0] - b[0]) > 1e-3 and abs(a[1] - b[1]) > 1e-3)
    upright = next(k for k, a, b in lines if abs(a[0] - b[0]) < 1e-3 and abs(a[0] - max(p[0] for _, p, q in lines for p in (p, q))) < 1e-3)
    flat = [k for k, a, b in lines if abs(a[1] - b[1]) < 1e-3]
    print("edges: slanted", slant, "| upright", upright, "| expected", round(90 + math.degrees(math.atan2(20, 30)), 1))
    # ＋ Dimension: a click on each edge's middle
    js(f"{S}.action('dim')")
    for k in (slant, upright):
        js(f"const l = {S}.geo.views.Top.lines.find(x => x.key === arguments[0]); {S}.clickDim({S}.P('Top', [(l.a[0] + l.b[0]) / 2, (l.a[1] + l.b[1]) / 2]));", k)
        time.sleep(0.2)
    made = js(f"const d = {S}.allDims().find(x => x.id === {S}.sel); return d && [d.kind, {S}.dimText(d, {S}.value(d))];")
    print("two edges clicked:", made, "| drawn:", js(f"return !!document.querySelector('#shViewport [data-dim=\"' + {S}.sel + '\"] path')"))
    js(f"{S}.action('dim')")
    r = json.loads(call("sheet_edit", add=[{"view": "Top", "edges": [f"{slant}#0", upright]}]))
    print("the AI's:", r["done"][:40], "|", [x["text"] for x in r["dims"] if x["kind"] == "ang"])
    print("parallel edges:", call("sheet_edit", add=[{"view": "Top", "edges": flat[:2]}])[:60])
    shot = js(f"""const svg = new XMLSerializer().serializeToString({S}.svgEl);
      return new Promise((ok) => {{ const img = new Image(); img.onload = () => {{ const c = document.createElement('canvas'); c.width = 1400; c.height = Math.round(1400 * img.height / img.width);
        const x = c.getContext('2d'); x.fillStyle = '#fff'; x.fillRect(0, 0, c.width, c.height); x.drawImage(img, 0, 0, c.width, c.height); ok(c.toDataURL('image/png').split(',')[1]); }};
        img.src = URL.createObjectURL(new Blob([svg], {{ type: 'image/svg+xml' }})); }});""")
    open(f"{OUT}/sheet_angle.png", "wb").write(base64.b64decode(shot))
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
