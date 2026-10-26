"""📚 A library part with the maker's real model and its colours, in headless Edge: a drawn SMC CDQ2B25 has two
colours (the rod lighter than the body) -> a STEP file (here one the app exports) attached to "Ø25, stroke 15" with 📎 Use
the maker's model -> the detail says so, the preview shows it -> put into an assembly: the part is that solid (its
library facts and part number kept) -> stroke 20 is still drawn -> ✕ takes the model away: drawn again.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_library_real.py http://127.0.0.1:5199 <out dir>
"""
import json
import os
import sys
import time
import urllib.request

from selenium import webdriver
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
# a STEP file to stand for the maker's model: a 52 × 52 × 47.5 block, exported by the app itself
pts = {"p1": [-26, -26], "p2": [26, -26], "p3": [26, 26], "p4": [-26, 26]}
box = [{"id": "F1", "type": "sketch", "plane": {"datum": "XY"}, "points": pts,
        "entities": [{"id": f"l{i + 1}", "t": "line", "a": f"p{i + 1}", "b": f"p{i % 4 + 2 if i < 3 else 1}"} for i in range(4)]},
       {"id": "F2", "type": "extrude", "sketch": "F1", "op": "add", "d": 47.5}]
req = urllib.request.Request(f"{URL}/api/model/export/step", data=json.dumps({"part": {"features": box}, "name": "CDQ2B25-15DZ"}).encode(), headers={"Content-Type": "application/json"})
STEP = os.path.abspath(os.path.join(OUT, "CDQ2B25-15DZ.step"))
with urllib.request.urlopen(req, timeout=120) as r, open(STEP, "wb") as fh:
    fh.write(r.read())

opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
A = "window.__app.assembly"
H = "window.__app.agentHandlers"


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def choose(size, stroke):
    js("window.__app.library.open('CDQ2B')")
    wait("return !!document.querySelector('.lib [data-item=smc-cdq2b]')")
    js("document.querySelector('.lib [data-item=smc-cdq2b]').click()")
    time.sleep(0.3)
    js("const s = document.querySelector('.lib [data-k=size]'); s.value = arguments[0]; s.dispatchEvent(new Event('change'))", size)
    time.sleep(0.3)
    js("const s = document.querySelector('.lib [data-k=length]'); s.value = arguments[0]; s.dispatchEvent(new Event('change'))", str(stroke))
    time.sleep(0.5)


try:
    d.get(URL)
    wait("return !!window.__app")
    js(f"return {H}.new_assembly({{ name: 'Cylinders' }})")
    wait("return window.__app.state.workspace === 'assembly'")
    choose("Ø25", 15)
    print("drawn:", d.find_element(By.CSS_SELECTOR, ".lib h2").text, "| paint (rod colour):", js("return window.__app.library.current().built.data.paint"))
    d.find_element(By.CSS_SELECTOR, ".lib [data-a=real]").send_keys(STEP)
    wait("return !!document.querySelector('.lib .lib-realon')", 60)
    print("attached:", d.find_element(By.CSS_SELECTOR, ".lib .lib-real").text.replace("\n", " "))
    wait("return !!window.__app.library.lastBody", 30)
    time.sleep(1.0)
    print("preview of the maker's model:", js("const b = window.__app.library.lastBody.bbox; return [b[3]-b[0], b[4]-b[1], b[5]-b[2]].map(v => +v.toFixed(2))"), "(52 × 52 × 47.5)")
    d.save_screenshot(f"{OUT}/library_real.png")
    d.find_element(By.CSS_SELECTOR, ".lib [data-a=insert]").click()
    wait(f"return {A}.doc.instances.length === 1 && Object.values({A}.bodies).every(b => b.body)", 60)
    part = js(f"const it = {A}.doc.instances[0]; const p = window.__app.project.parts.find(q => q.id === it.part); return [p.name, p.data.features.map(f => f.type), p.data.library.pn, p.data.library.real]")
    print("in the assembly:", part)
    choose("Ø25", 20)
    print("stroke 20 (no model attached):", js("return window.__app.library.current().built.data.features.map(f => f.type).join(' ').slice(0, 40)"), "| real:", js("return window.__app.library.current().built.data.library.real || null"))
    choose("Ø25", 15)
    d.find_element(By.CSS_SELECTOR, ".lib [data-a=unreal]").click()
    wait("return !document.querySelector('.lib .lib-realon')", 20)
    print("✕ -> drawn again:", js("return window.__app.library.current().built.data.features[0].type"), "| stored:", js("return fetch('/api/library').then(r => r.json()).then(r => r.items.find(i => i.id === 'smc-cdq2b').models || null)"))
    js("window.__app.library.close()")
    # the drawn cylinder in the assembly: two colours (the rod lighter)
    choose("Ø25", 20)
    d.find_element(By.CSS_SELECTOR, ".lib [data-a=insert]").click()
    wait(f"return {A}.doc.instances.length === 2 && Object.values({A}.bodies).every(b => b.body)", 60)
    js(f"{A}.sel = null; {A}.render(); {A}.draw()")  # (a part just put in is chosen: drawn blue)
    time.sleep(0.5)
    print("drawn one in the assembly coloured by its steps:", js(f"return {A}.view.meshes.map(m => !!m.geometry.attributes.color)"))
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
