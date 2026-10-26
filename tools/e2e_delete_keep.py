"""Deleting a step that others stand on, in headless Edge: a STEP opened as a model -> a sketch on its top face, extruded;
a rounding of one of its edges -> ✕ the STEP: the dialog offers "Keep them where they are" -> the sketch stays (on a
fixed plane, its sizes as they were), its extrude builds, the rounding (it needs the STEP's edges) goes -> Ctrl+Z ->
"Delete them too" removes all -> the AI's delete_feature keeps them by default.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_delete_keep.py http://127.0.0.1:5199 <out dir> <a .step>
"""
import json
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

URL, OUT, STEP = sys.argv[1], sys.argv[2], sys.argv[3]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"
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


def settled():
    time.sleep(0.4)
    wait(f"return !{M}.inflight")
    time.sleep(0.3)


def steps():
    return js(f"return {M}.part.features.map(f => [f.id, f.type, f.plane?.face ? 'on a face' : f.plane?.frame ? 'fixed plane' : f.plane?.datum || ''])")


def build(top):
    call("add_feature", type="sketch", plane={"face": top}, shapes=[{"rect": {"x": -5, "y": -4, "w": 10, "h": 8}}])
    call("add_feature", type="extrude", sketch="F2", d=5)
    edge = js(f"""const b = {M}.result.body, f = b.faces.find(x => x.name === arguments[0]);
      const e = b.edges.find(x => x.faces.includes(f.id) && x.faces.length === 2 && b.faces[x.faces.find(i => i !== f.id)].name.startsWith('F1:'));
      return e ? {{ a: b.faces[e.faces[0]].name, b: b.faces[e.faces[1]].name, fp: e.mid }} : null""", top)
    js(f"{M}.part.features.push({{ id: 'F4', type: 'fillet', name: 'Fillet 1', edges: [arguments[0]], r: 1 }}); {M}.commit()", edge)
    settled()


try:
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "cadInput").send_keys(STEP)
    wait(f"return window.__app.state.workspace === 'model' && !!{M}.result?.body && !{M}.inflight")
    top = js(f"return {M}.result.body.faces.filter(f => f.type === 'plane' && f.normal[2] > 0.99).sort((a, b) => b.centroid[2] - a.centroid[2])[0].name")
    build(top)
    print("steps:", steps(), "| ok", js(f"return {M}.result.ok"))
    sk = js(f"return {M}.part.features[1]")
    pts0 = sk["points"]

    row = d.find_elements(By.CSS_SELECTOR, "#modelLeft .mt-item")[0]
    js("arguments[0].querySelector('[data-a=del]').click()", row)
    wait("return !!document.querySelector('.choose')", 10)
    print("dialog:", d.find_element(By.CSS_SELECTOR, ".choose p").text)
    print("  answers:", [b.text.replace("\n", " — ") for b in d.find_elements(By.CSS_SELECTOR, ".choose-opts .btn")])
    d.save_screenshot(f"{OUT}/del1.png")
    d.find_element(By.CSS_SELECTOR, ".choose-opts .btn.primary").click()
    settled()
    sk = js(f"return {M}.part.features[0]")
    print("kept:", steps(), "| ok", js(f"return {M}.result.ok"), "| volume", round(js(f"return {M}.result.body?.volume || 0"), 3), "(10 × 8 × 5 = 400)")
    print("sketch points unchanged:", sk["points"] == pts0, "| plane", list(sk["plane"].keys()))

    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    settled()
    print("Ctrl+Z:", steps())
    row = d.find_elements(By.CSS_SELECTOR, "#modelLeft .mt-item")[0]
    js("arguments[0].querySelector('[data-a=del]').click()", row)
    wait("return !!document.querySelector('.choose')", 10)
    d.find_element(By.CSS_SELECTOR, ".choose-opts .btn.danger").click()
    settled()
    print("Delete them too:", steps())

    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    settled()
    r = call("delete_feature", id="F1")
    print("AI delete_feature:", r[:60], "| steps", steps())
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
