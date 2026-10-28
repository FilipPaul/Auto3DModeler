"""The colours of a STEP file, in headless Edge: Open a coloured STEP -> its faces in their file colours (the modeler
and an assembly) -> a face painted over one -> "Keep the file's colours" off: the part's own colour.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_step_colours.py http://127.0.0.1:5199 <out dir> <a coloured .step>
"""
import json
import sys
import time
from collections import Counter

from selenium import webdriver
from selenium.webdriver.common.by import By

URL, OUT, STEP = sys.argv[1], sys.argv[2], sys.argv[3]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"
A = "window.__app.assembly"
H = "window.__app.agentHandlers"


def wait(script, t=120):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def shown():
    """The colours the modeler paints its faces now (a count per colour)."""
    return Counter(js(f"""const v = {M}.view, c = v.mesh.geometry.attributes.color.array, out = [];
      for (let i = 0; i < c.length; i += 9) out.push('#' + new (v.bodyColor?.constructor || Object)().constructor.name);
      return [...new Set(Array.from({{length: c.length / 9}}, (_, t) => v.faceIds[t]))].map(id => {{
        const t = v.faceIds.indexOf(id); return [c[t * 9], c[t * 9 + 1], c[t * 9 + 2]].map(x => Math.round(x * 255).toString(16).padStart(2, '0')).join('');
      }})""")).most_common(4)


def one_body():
    """A STEP that holds an assembly asks how to open it: as one body, as this test expects (no question: nothing)."""
    js("""let n = 0; (function go() { const b = [...document.querySelectorAll('.choose .btn')].find((x) => x.textContent.trim().startsWith('Open as one body'));
      if (b) b.click(); else if (n++ < 300) setTimeout(go, 100); })()""")


try:
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "cadInput").send_keys(STEP)
    one_body()
    wait(f"return window.__app.state.workspace === 'model' && !!{M}.result?.body && !{M}.inflight")
    time.sleep(0.5)
    faces = js(f"return {M}.result.body.faces")
    print("file colours on faces:", len([f for f in faces if f.get("color")]), "of", len(faces), Counter(f.get("color") for f in faces).most_common(3))
    print("shown in the view:", shown())
    js(f"{M}.view.setView('iso')")
    time.sleep(0.4)
    d.save_screenshot(f"{OUT}/stepcol1.png")

    name = js("return window.__app.project.current.name")
    call("new_assembly", name="With colours")
    call("insert_part", part=name)
    wait(f"return {A}.doc.instances.length === 1 && Object.values({A}.bodies).every(b => b.body)")
    js(f"{A}.sel = null; {A}.draw(); {A}.view.setView('iso')")
    time.sleep(0.4)
    print("assembly mesh coloured per face:", js(f"return !!{A}.view.meshes[0].geometry.attributes.color && {A}.view.meshes[0].material.vertexColors"))
    d.save_screenshot(f"{OUT}/stepcol2.png")

    call("open_part", id=name)
    wait(f"return !!{M}.result?.body && !{M}.inflight")
    js(f"{M}.edit('F1')")
    time.sleep(0.5)
    box = d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=colours]")
    print("keep the file's colours:", box.is_selected())
    box.click()
    wait(f"return !{M}.inflight")
    time.sleep(0.5)
    print("off -> faces with a file colour:", len([f for f in js(f"return {M}.result.body.faces") if f.get("color")]), "| shown", shown())
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
