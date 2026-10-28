"""An assembly sheet's iso view exploded, in headless Edge: Box = Base + Lid (the lid on top) -> its sheet -> ☐ Iso
view exploded ticked: the iso drawing taller (the lid lifted off), the balloons on the parts where they are drawn, the
front view as before -> Ctrl+Z: assembled again -> a picture of the sheet.

  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_sheet_explode.py http://127.0.0.1:5199 <out dir>
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
A = "window.__app.assembly"
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


def iso_tall():
    return round(js(f"const ys = {S}.d.built.geometry.iso.flat().map(p => p[1]); return Math.max(...ys) - Math.min(...ys);"), 2)


def built():
    time.sleep(0.5)
    wait(f"return !{S}.busy && {S}.d?.built")
    time.sleep(0.5)


try:
    d.get(URL)
    wait("return !!window.__app")
    for name, h in (("Base", 10), ("Lid", 4)):
        call("new_model", name=name)
        call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
        call("add_feature", type="extrude", sketch="F1", d=h)
    call("new_assembly", name="Box")
    call("insert_part", part="Base")
    call("insert_part", part="Lid")
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    call("place_part", part="I2", x=0, y=0, z=10)
    print("sheet_open:", json.loads(call("sheet_open", part="Box"))["preset"])
    wait(f"return !!{S}.svgEl && {S}.d.asm")
    built()
    t0, front0 = iso_tall(), js(f"return {S}.d.built.geometry.views.Front.box")
    b0 = js(f"return {S}.balloonAt")
    box = d.find_element(By.CSS_SELECTOR, ".sh-props [data-k=exploded]")
    print("☐ Iso view exploded:", box.is_selected(), "| the iso", t0, "tall")
    box.click()
    built()
    print("ticked: the iso", iso_tall(), "tall | the front the same:", js(f"return {S}.d.built.geometry.views.Front.box") == front0,
          "| balloons moved:", js(f"return {S}.balloonAt") != b0, "| kept:", js(f"return !!{S}.d.exploded"))
    shot = js(f"""const svg = new XMLSerializer().serializeToString({S}.svgEl);
      return new Promise((ok) => {{ const img = new Image(); img.onload = () => {{ const c = document.createElement('canvas'); c.width = 1400; c.height = Math.round(1400 * img.height / img.width);
        const x = c.getContext('2d'); x.fillStyle = '#fff'; x.fillRect(0, 0, c.width, c.height); x.drawImage(img, 0, 0, c.width, c.height); ok(c.toDataURL('image/png').split(',')[1]); }};
        img.src = URL.createObjectURL(new Blob([svg], {{ type: 'image/svg+xml' }})); }});""")
    open(f"{OUT}/sheet_exploded.png", "wb").write(base64.b64decode(shot))
    js(f"{S}.history.go(-1)")
    built()
    print("Ctrl+Z: the iso", iso_tall(), "tall | exploded:", js(f"return !!{S}.d.exploded"))
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
