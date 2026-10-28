"""⇳ Midway sketch plane, in headless Edge with real mouse clicks: a block 40 × 20 × 10 -> ✏ Sketch -> ⇳ Midway -> a
click on its front face (Front view), the camera turned round, a click on its back face -> a sketch midway (y 10), its
plane {face, mid}. Then the AI's add_feature sketch plane {face, mid} (a circle): y 10; the block made 30 deep
(edit_feature): the AI's sketch follows to y 15; a face not parallel refused.

  PYTHONIOENCODING=utf-8 py tools/e2e_sketch_midplane.py http://127.0.0.1:5199 <out dir>
"""
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
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
        time.sleep(0.2)
    raise TimeoutError(script)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def settle():
    time.sleep(0.4)
    wait(f"return !{M}.building && {M}.result?.body")
    time.sleep(0.5)


def face_named(n):
    return js(f"return {M}.result.body.faces.find(f => f.type === 'plane' && Math.abs(f.frame.n[0] - arguments[0][0]) + Math.abs(f.frame.n[1] - arguments[0][1]) + Math.abs(f.frame.n[2] - arguments[0][2]) < 1e-6)?.name", n)


def click_at(p):
    off = js(f"""const v = {M}.view, p = arguments[0];
      const [sx, sy] = v.toScreen(new (v.camera.position.constructor)(p[0], p[1], p[2])), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", p)
    cv = d.find_element(By.CSS_SELECTOR, "#modelViewport canvas")
    ActionChains(d, duration=30).move_to_element_with_offset(cv, *off).perform()
    time.sleep(0.2)
    ActionChains(d).click().perform()
    time.sleep(0.5)


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Block")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    settle()
    front, back, top = face_named([0, -1, 0]), face_named([0, 1, 0]), face_named([0, 0, 1])
    print("the block's faces: front", front, "| back", back)
    d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=sketch]").click()
    wait(f"return {M}.mode === 'plane'")
    b = d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=midPlane]")
    b.click()
    time.sleep(0.3)
    b = d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=midPlane]")
    print("⇳ Midway on:", "on" in b.get_attribute("class"), "| group define:", "g-define" in b.get_attribute("class"))
    js(f"{M}.view.setView('front')")
    time.sleep(0.4)
    click_at([20, 0, 5])
    print("first face lit:", js(f"return {M}.view.selSet?.size || 0"), "| still choosing:", js(f"return {M}.mode"))
    js(f"""const v = {M}.view, c = v.controls.target; v.camera.position.set(c.x, c.y + 120, c.z + 0.01); v.camera.up.set(0, 0, 1);
      v.controls.update(); v.invalidate();""")
    time.sleep(0.4)
    click_at([20, 20, 5])
    wait(f"return {M}.mode === 'sketch'")
    pl = js(f"return {M}.sk.f.plane")
    print("sketching midway: o", [round(v, 3) for v in pl["frame"]["o"]], "| face", pl.get("face", {}).get("name"), "| mid", pl.get("mid", {}).get("name"))
    d.save_screenshot(f"{OUT}/sketch_midplane.png")
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=cancelSketch], .m-cmdbar [data-a=cancelSketch]").click()
    wait(f"return {M}.mode === 'part'")
    print("AI sketch midway:", call("add_feature", type="sketch", plane={"face": front, "mid": back}, shapes=[{"circle": {"x": 0, "y": 0, "d": 4}}])[:80])
    settle()
    sid = js(f"return {M}.part.features.at(-1).id")
    print("  its frame y:", round(js(f"return {M}.frames[arguments[0]].o[1]", sid), 3))
    print("deeper block:", call("edit_feature", id="F1", fields={"shapes": [{"rect": {"x": 0, "y": 0, "w": 40, "h": 30}}]})[:60])
    settle()
    print("  the sketch followed to y:", round(js(f"return {M}.frames[arguments[0]].o[1]", sid), 3))
    print("not parallel:", call("add_feature", type="sketch", plane={"face": front, "mid": top}, shapes=[{"circle": {"x": 0, "y": 0, "d": 4}}])[:110])
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
