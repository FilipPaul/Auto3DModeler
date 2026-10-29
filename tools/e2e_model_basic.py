"""The 3D model workspace, first part, with REAL mouse input in headless Edge:
＋ New 3D model -> it is sketching on the Top plane -> two clicks draw a rectangle -> type its width on its
label -> Finish -> Extrude opens with a live preview -> OK -> Sketch on the top face (a real click on it)
-> a circle -> Finish -> Extrude defaults to Cut -> Through all -> OK -> volumes checked, Undo / Redo,
editing the first extrude moves the hole with its face, Export STL, Save project -> reopen, switching
between a model tab and a drawing tab.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_model_basic.py http://127.0.0.1:5199 <out dir>
"""
import json
import math
import sys
import time
from pathlib import Path

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
# the step tree shows a sketch under the step made from it (folded): every row opened, the row of part.features[i]
STEP_ROW = ("const m = window.__app.modeler; m.part.features.forEach(f => m.openTo(f.id)); m.renderTree(); "
            "return document.querySelector(`#modelLeft .mt-item[data-id=\"${m.part.features[arguments[0]].id}\"]`)")


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def settled():
    time.sleep(0.25)
    wait(f"return !{M}.inflight")
    time.sleep(0.2)


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#modelViewport canvas")


def offset_of(uv):
    """Sketch (u, v) -> offset from the canvas centre (the way Selenium computes it), via the view."""
    return js(f"""const m = {M}, v = m.view, [u, w] = arguments[0];
      const {{ o, x, y }} = (() => {{ const f = m.frame(); const V = (a) => ({{x: a[0], y: a[1], z: a[2]}}); return {{ o: f.o, x: f.x, y: [f.n[1]*f.x[2]-f.n[2]*f.x[1], f.n[2]*f.x[0]-f.n[0]*f.x[2], f.n[0]*f.x[1]-f.n[1]*f.x[0]] }}; }})();
      const p = new (v.camera.position.constructor)(o[0] + u*x[0] + w*y[0], o[1] + u*x[1] + w*y[1], o[2] + u*x[2] + w*y[2]);
      const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(uv))


def click_uv(uv):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *offset_of(uv)).perform()
    time.sleep(0.15)
    ActionChains(d).click().perform()
    time.sleep(0.2)


def body():
    return js(f"const b = {M}.result?.body; return b && {{volume: b.volume, bbox: b.bbox.map(v => +v.toFixed(4)), faces: b.faces.length}}")


def btn(sel):
    d.find_element(By.CSS_SELECTOR, sel).click()
    time.sleep(0.3)


try:
    d.get(URL)
    wait("return !!window.__app")
    btn("#newModelBtn")
    wait(f"return {M}.mode === 'sketch'")
    settled()
    print("new model: tabs", js("return [...document.querySelectorAll('#partTabs .part-tab')].map(t => t.textContent.trim())"),
          "| mode", js(f"return {M}.mode"), "| tool", js(f"return {M}.sk.tool"), "| plane", js(f"return {M}.sk.f.plane"),
          "| hint", js("return document.querySelector('.m-hint').textContent"))
    d.save_screenshot(f"{OUT}/m1_new.png")

    # two clicks: a 40 x 20 rectangle (grid snapping)
    click_uv((0, 0))
    ActionChains(d, duration=200).move_to_element_with_offset(canvas(), *offset_of((40, 20))).perform()
    time.sleep(0.2)
    print("while drawing:", js("return document.querySelector('.sk-label.live')?.textContent"))
    click_uv((40, 20))
    ents = js(f"return {M}.sk.f.entities")
    print("rectangle:", ents)

    # type the width on its label
    vals = d.find_elements(By.CSS_SELECTOR, ".sk-label.edit .sk-val")
    lab = next((e for e in vals if e.text == "40"), None)
    if lab:
        lab.click()
        time.sleep(0.2)
        inp = d.find_element(By.CSS_SELECTOR, ".sk-input")
        inp.send_keys(Keys.CONTROL, "a")
        inp.send_keys("50", Keys.ENTER)
        time.sleep(0.3)
    time.sleep(0.4)
    print("after typing the width:", js(f"return {M}.sk.f.points"), "| locks", js(f"return {M}.sk.f.dims.map(d => [d.t, d.v])"),
          "| locked labels", js("return [...document.querySelectorAll('.sk-label.locked')].map(l => l.textContent)"))
    d.save_screenshot(f"{OUT}/m2_sketch.png")

    # Finish -> Extrude opens by itself, with a preview
    btn("[data-a=finish]")
    wait(f"return {M}.cmd && {M}.result?.body")
    settled()
    print("extrude opened:", js(f"return [{M}.cmd.feature.op, {M}.cmd.feature.d]"), "| preview body", body())
    dist = d.find_element(By.CSS_SELECTOR, "#modelRight input[data-k=d]")
    dist.send_keys(Keys.CONTROL, "a")
    dist.send_keys("12")
    settled()
    print("preview at 12 mm:", body())
    d.save_screenshot(f"{OUT}/m3_extrude.png")
    btn("#modelViewport .view-actions [data-a=ok]")
    settled()
    print("after OK:", body(), "| tree", js("return [...document.querySelectorAll('.mt-item')].map(r => r.textContent.replace(/\\s+/g, ' ').trim())"))

    # Sketch -> click the top face (the view looks from above-front: find a point on the top face)
    btn("[data-a=sketch]")
    print("sketch mode:", js(f"return {M}.mode"))
    pt = js(f"""const v = {M}.view, r = v.renderer.domElement.getBoundingClientRect();
      for (let gy = 0.2; gy < 0.9; gy += 0.01) for (let gx = 0.2; gx < 0.8; gx += 0.01) {{
        const x = Math.round(r.left + gx * r.width), y = Math.round(r.top + gy * r.height);
        if (document.elementFromPoint(x, y) !== v.renderer.domElement) continue;
        const h = v.pick(x, y);
        if (h?.face?.normal && h.face.normal[2] > 0.99) return [x - Math.floor(r.left + r.width / 2), y - Math.floor(r.top + r.height / 2)];
      }} return null;""")
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *pt).perform()
    time.sleep(0.2)
    print("hovered face highlighted:", js(f"return {M}.view.hover >= 0"))
    ActionChains(d).click().perform()
    wait(f"return {M}.mode === 'sketch'")
    settled()
    print("sketch on the top face:", js(f"return {M}.sk.f.plane"))

    # a circle at the face centre, 6 mm across
    btn("[data-a=circle]")
    click_uv((0, 0))
    click_uv((3, 0))
    print("circle:", js(f"return {M}.sk.f.entities.map(e => [e.t, 2 * e.r, {M}.sk.P(e.c)])"), "| locks", js(f"return {M}.sk.f.dims.map(d => [d.t, d.v])"))
    dia = js(f"return 2 * {M}.sk.f.entities[0].r")
    btn("[data-a=finish]")
    wait(f"return {M}.cmd")
    settled()
    print("extrude default on a face:", js(f"return {M}.cmd.feature.op"), "| preview", body())
    d.find_element(By.CSS_SELECTOR, "#modelRight input[data-k=through]").click()
    settled()
    btn("#modelViewport .view-actions [data-a=ok]")
    settled()
    b = body()
    print("hole through:", b, "| expected", round(50 * 20 * 12 - math.pi * dia * dia / 4 * 12, 3))
    d.save_screenshot(f"{OUT}/m4_hole.png")

    # undo / redo
    d.find_element(By.CSS_SELECTOR, "#modelViewport .m-view canvas").click()
    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    settled()
    print("Ctrl+Z:", body()["volume"], "| steps", js(f"return {M}.part.features.length"))
    ActionChains(d).key_down(Keys.CONTROL).send_keys("y").key_up(Keys.CONTROL).perform()
    settled()
    print("Ctrl+Y:", body()["volume"])

    # change the first extrude: double-click it in the tree, 20 mm -> the hole stays through
    ActionChains(d).double_click(js(STEP_ROW, 1)).perform()
    wait(f"return {M}.cmd")
    dist = d.find_element(By.CSS_SELECTOR, "#modelRight input[data-k=d]")
    dist.send_keys(Keys.CONTROL, "a")
    dist.send_keys("20", Keys.ENTER)
    settled()
    print("first extrude 20 mm:", body(), "| expected", round(50 * 20 * 20 - math.pi * dia * dia / 4 * 20, 3),
          "| sketch 2 origin", js(f"return {M}.frames.F3?.o"))

    # export STL (Save dialog stubbed)
    js("""window.__saved = null; window.showSaveFilePicker = async (o) => ({ name: o.suggestedName,
      createWritable: async () => ({ write: async (b) => { window.__saved = { size: b.size, text: b.type === 'application/json' ? await b.text() : null }; }, close: async () => {} }) });""")
    d.find_element(By.ID, "exportBtn").click()
    d.find_element(By.CSS_SELECTOR, "[data-fmt=stl]").click()
    wait("return window.__saved")
    print("STL exported:", js("return window.__saved.size"), "bytes")

    # a drawing as a second tab, back to the model
    js("document.getElementById('sampleBtn').click()")
    wait("return window.__app.state.solution && document.body.classList.contains('ws-model') === false")
    time.sleep(1)
    d.find_elements(By.CSS_SELECTOR, "#partTabs .part-tab")[0].click()
    wait("return document.body.classList.contains('ws-model')")
    settled()
    print("back on the model:", body()["volume"], "| undo still there:", js(f"return {M}.history.canUndo()"))

    # save the project and reopen it
    js("window.__saved = null")
    d.find_element(By.ID, "saveBtn").click()
    wait("return window.__saved?.text")
    proj = json.loads(js("return window.__saved.text"))
    print("saved:", [(p["id"], p["kind"], p["name"], len(p.get("model", {}).get("features", []))) for p in proj["parts"]])
    path = Path(OUT) / "model_project.a3d.json"
    path.write_text(json.dumps(proj), encoding="utf-8")
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "projectInput").send_keys(str(path))
    wait(f"return document.body.classList.contains('ws-model') && {M}.result?.body")
    settled()
    print("reopened:", body()["volume"], "| tabs", js("return [...document.querySelectorAll('#partTabs .part-tab')].map(t => t.textContent.trim())"))
    d.save_screenshot(f"{OUT}/m5_reopened.png")
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
