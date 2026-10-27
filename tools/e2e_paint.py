"""🎨 Paint and renaming, with REAL mouse input in headless Edge: a part of two bodies (two blocks apart) -> 🎨 Paint ->
a click on a top face, the colour red -> Ctrl+click a side face: two chosen, blue -> ▣ Bodies: a click picks all faces
of one block -> Ctrl+Z takes a colour back -> 🏷 renames a step in the list -> an assembly shows the painted faces ->
🏷 in its list renames the part (and its tab).

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_paint.py http://127.0.0.1:5199 <out dir>
"""
import sys
import time

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


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def click_at(p, ctrl=False):
    off = js(f"""const v = {M}.view, p = new (v.camera.position.constructor)(...arguments[0]);
      const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", p)
    ac = ActionChains(d, duration=30).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, "#modelViewport canvas"), *off)
    if ctrl:
        ac.key_down(Keys.CONTROL).click().key_up(Keys.CONTROL)
    else:
        ac.pause(0.2).click()
    ac.perform()
    time.sleep(0.5)


def set_colour(v):
    el = d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=paint]")
    js("arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('input', {bubbles: true})); arguments[0].dispatchEvent(new Event('change', {bubbles: true}))", el, v)
    time.sleep(0.4)


def count():
    return d.find_element(By.CSS_SELECTOR, "#modelRight .mp-count").text


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Two blocks")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 30, "h": 20}}, {"rect": {"x": 50, "y": 0, "w": 30, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    wait(f"return !!{M}.result?.body && !{M}.inflight")
    js(f"{M}.view.setView('iso')")
    time.sleep(0.5)
    print("bodies in the part:", js(f"return new Set({M}.result.body.faces.map(f => f.solid)).size"))

    d.find_element(By.CSS_SELECTOR, "#modelViewport [data-a=paint]").click()
    time.sleep(0.3)
    print("hint:", js("return document.querySelector('#modelViewport .m-hint').textContent"))
    click_at([15, 10, 10])  # the first block's top
    print("chosen:", count())
    set_colour("#ff3b30")
    print("colours:", js(f"return {M}.part.paint"), "| painted faces in the view", js(f"return {M}.view.faceColor.size"))
    click_at([15, 0, 5], ctrl=True)  # its front face, Ctrl
    print("Ctrl+click:", count())
    set_colour("#0a84ff")
    print("colours:", js(f"return {M}.part.paint"))
    d.find_element(By.CSS_SELECTOR, "#modelRight [data-by=solid]").click()
    time.sleep(0.3)
    click_at([65, 10, 10])  # the second block
    print("▣ Bodies, a click on the second block:", count())
    set_colour("#34c759")
    print("painted faces:", len(js(f"return {M}.part.paint")))
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=donePaint]").click()
    time.sleep(0.3)
    d.save_screenshot(f"{OUT}/paint1.png")
    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    time.sleep(1)
    print("Ctrl+Z: painted faces", len(js(f"return {M}.part.paint || []")))
    ActionChains(d).key_down(Keys.CONTROL).send_keys("y").key_up(Keys.CONTROL).perform()
    time.sleep(1)
    print("Ctrl+Y: painted faces", len(js(f"return {M}.part.paint || []")))

    # 🏷 a step
    row = d.find_elements(By.CSS_SELECTOR, "#modelLeft .mt-item")[1]
    js("arguments[0].querySelector('[data-a=rename]').click()", row)
    time.sleep(0.2)
    name = row.find_element(By.CSS_SELECTOR, ".mt-name")
    name.send_keys(Keys.CONTROL, "a")
    name.send_keys("Blocks", Keys.ENTER)
    time.sleep(0.4)
    print("step renamed:", js(f"return {M}.part.features.map(f => f.name)"))

    # an assembly shows the painted faces; 🏷 renames the part
    call("new_assembly", name="Painted")
    call("insert_part", part="Two blocks")
    wait(f"return {A}.doc.instances.length === 1 && Object.values({A}.bodies).every(b => b.body)")
    js(f"{A}.sel = null; {A}.draw(); {A}.view.setView('iso')")
    time.sleep(0.4)
    print("assembly mesh with face colours:", js(f"return {A}.view.meshes[0].material.vertexColors && !!{A}.view.meshes[0].geometry.attributes.color"))
    d.save_screenshot(f"{OUT}/paint2.png")
    row = d.find_element(By.CSS_SELECTOR, "#asmLeft .mt-item")
    js("arguments[0].querySelector('[data-a=rename]').click()", row)
    time.sleep(0.2)
    name = row.find_element(By.CSS_SELECTOR, ".mt-name")
    name.send_keys(Keys.CONTROL, "a")
    name.send_keys("Painted blocks", Keys.ENTER)
    time.sleep(0.5)
    print("part renamed:", [p["name"] for p in __import__("json").loads(call("list_parts"))], "| list", d.find_element(By.CSS_SELECTOR, "#asmLeft .mt-name").text)
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
