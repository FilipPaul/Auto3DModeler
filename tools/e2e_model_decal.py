"""Aa Text / picture on a 3D model's face, with REAL mouse input in headless Edge: a 60 x 30 x 5 plate -> Aa Text /
picture -> click near the top face's centre (snaps to it) -> the text "Text" 8 mm high, raised 1 mm -> typed "Text3D"
(the outline follows) -> Engraved -> OK; the plate gets thicker -> the text stays on its top; the AI writes text
on a face; a picture outline through the picker.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_model_decal.py http://127.0.0.1:5199 <out dir>
"""
import json
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
H = "window.__app.agentHandlers"


def wait(script, t=30):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def settled():
    time.sleep(0.5)
    wait(f"return !{M}.inflight")
    time.sleep(0.3)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#modelViewport canvas")


def off_xyz(p):
    return js(f"""const v = {M}.view, [x, y, z] = arguments[0];
      const [sx, sy] = v.toScreen(new (v.camera.position.constructor)(x, y, z)), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(p))


def click(o):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *o).perform()
    time.sleep(0.2)
    ActionChains(d).click().perform()
    time.sleep(0.4)


def btn(sel):
    d.find_element(By.CSS_SELECTOR, sel).click()
    time.sleep(0.3)


def body():
    return js(f"return {M}.result.body")


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Sign")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 30}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    settled()
    plate = body()["volume"]
    js(f"{M}.view.setView('iso')")
    time.sleep(0.4)
    btn("#modelViewport [data-a=decal]")
    settled()
    click(off_xyz([30.5, 15.3, 5]))  # near the top's centre: snaps to it
    settled()
    f = js(f"return {M}.cmd.feature")
    print("placed at", f["at"], "on", f["plane"]["face"]["name"], "| outline polygons", len(f["polys"] or []), "| aspect", f["aspect"])
    b = body()
    print("raised: volume +", round(b["volume"] - plate, 2), "mm³ | top z", b["bbox"][5])
    inp = d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=text]")
    inp.send_keys(Keys.END, "3D")
    time.sleep(1.2)
    settled()
    f2 = js(f"return {M}.cmd.feature")
    print("typed:", f2["text"], "| wider:", f2["aspect"] > f["aspect"], "| volume +", round(body()["volume"] - plate, 2))
    btn("#modelRight [data-op=cut]")
    settled()
    print("engraved: volume -", round(plate - body()["volume"], 2), "| top z", body()["bbox"][5])
    # its place by sliders: X, Y across the face, and the turn
    fields = {e.get_attribute("data-at") or e.get_attribute("data-k"): (e.get_attribute("data-lo"), e.get_attribute("data-hi"))
              for e in d.find_elements(By.CSS_SELECTOR, "#modelRight [data-at], #modelRight [data-k=angle]")}
    print("place fields (slider ranges):", fields, "| sliders", len(d.find_elements(By.CSS_SELECTOR, "#modelRight .mp-slider")))

    def slide(sel, v):
        sl = js("return document.querySelector('#modelRight ' + arguments[0]).closest('.field').nextElementSibling", sel)
        js("arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('input', {bubbles: true})); arguments[0].dispatchEvent(new Event('change', {bubbles: true}))", sl, v)
        time.sleep(0.3)
        settled()

    def mid():  # the middle of the letters' faces (x, y)
        return js(f"""const id = {M}.cmd.feature.id, fs = {M}.result.body.faces.filter(f => f.name.startsWith(id + ':'));
          return [fs.reduce((s, f) => s + f.centroid[0], 0) / fs.length, fs.reduce((s, f) => s + f.centroid[1], 0) / fs.length].map(v => +v.toFixed(2))""")
    m0 = mid()
    slide("[data-at='0']", 12)
    m1 = mid()
    print("X slider 12: at", js(f"return {M}.cmd.feature.at"), "| letters moved in x by", round(m1[0] - m0[0], 2), "y by", round(m1[1] - m0[1], 2))
    slide("[data-k=angle]", 90)
    bb = js(f"""const id = {M}.cmd.feature.id, fs = {M}.result.body.faces.filter(f => f.name.startsWith(id + ':')).map(f => f.centroid);
      return [Math.max(...fs.map(c => c[0])) - Math.min(...fs.map(c => c[0])), Math.max(...fs.map(c => c[1])) - Math.min(...fs.map(c => c[1]))].map(v => +v.toFixed(2))""")
    print("turned 90°: angle", js(f"return {M}.cmd.feature.angle"), "| letters' spread x, y", bb, "(taller than wide now) | ok", js(f"return {M}.result.features.at(-1).ok"))
    d.save_screenshot(f"{OUT}/decal1.png")
    slide("[data-k=angle]", 0)
    slide("[data-at='0']", 0)
    btn("#modelViewport .view-actions [data-a=ok]")
    settled()
    print("tree:", js("return [...document.querySelectorAll('#modelLeft .mt-item')].map(e => e.textContent.trim().split(/\\s{2,}/)[0])")[-1])
    call("edit_feature", id="F2", fields={"d": 8})
    settled()
    print("plate 8 thick -> still engraved on top:", body()["bbox"][5] == 8, "| ok", js(f"return {M}.result.ok"))

    # the AI writes on the front face
    r = json.loads(call("add_feature", type="decal", face="F2:side:l1", text="Hi", h=4, depth=0.6))
    print("AI decal on the front:", r["ok"], r["body"]["bbox"])

    # a picture outline (through the picker the user would use)
    js(f"""{M}.hooks.pickOutline = async () => ({{ name: 'star', width: 20, height: 10, polygons: [[[[0, 0], [20, 0], [20, 10], [0, 10]]]] }});""")
    btn("#modelViewport [data-a=decal]")
    settled()
    btn("#modelRight [data-src=picture]")
    btn("#modelRight [data-a=pickPicture]")
    time.sleep(0.4)
    js(f"{M}.view.setView('iso')")
    time.sleep(0.3)
    click(off_xyz([12, 8, 8]))
    settled()
    v0 = body()["volume"]
    f3 = js(f"return {M}.cmd.feature")
    print("picture:", f3["name"], "| aspect", f3["aspect"], "| at", f3["at"], "| ok", js(f"return {M}.result.features.at(-1).ok"))
    btn("#modelViewport .view-actions [data-a=ok]")
    settled()
    print("steps:", [s["type"] for s in json.loads(call("get_model"))["steps"]])
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
