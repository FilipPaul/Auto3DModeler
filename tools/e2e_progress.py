"""Progress bar + Cancel (import, slow rebuild), the automatic slice height, the feature-aware measure tool,
and renaming / saving the project with the Save dialog — in headless Edge.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_progress.py http://127.0.0.1:5199 <curved .stl> <out dir>
"""
import json
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

URL, STL, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def toasts():
    return js("return [...document.querySelectorAll('.toast')].map(t => t.textContent)")


try:
    d.get(URL)
    wait("return !!window.__app")

    # ---- import a curved STL: progress shown, slice height chosen automatically
    d.find_element(By.ID, "cadInput").send_keys(STL)
    seen = set()
    end = time.time() + 60
    while time.time() < end and not js("return !!(window.__app.state.solution && window.__app.state.model?.kind === 'mesh')"):
        if not js("return document.getElementById('busy').hidden"):
            seen.add(js("return document.querySelector('.busy-text').textContent"))
        time.sleep(0.05)
    time.sleep(1)
    m = js("return window.__app.state.model")
    print("import progress seen:", sorted(seen)[:6])
    print("slice height chosen:", m["mesh_opts"]["layer"], "| info:", [i["message"] for i in m["issues"]])

    # ---- a slow rebuild (very fine slices): progress bar, then Cancel -> back to the last state
    js("""const f = [...document.querySelectorAll('#rtab-outline .field')].find(r => r.textContent.includes('Slice height'));
      const i = f.querySelector('input'); i.value = '0.01'; i.dispatchEvent(new Event('input'));""")
    wait("return !document.getElementById('busy').hidden && /Slicing/.test(document.querySelector('.busy-text').textContent)", 30)
    time.sleep(1.0)
    st = js("return [document.querySelector('.busy-text').textContent, document.querySelector('.busy-bar i').style.width]")
    print("slow rebuild shows:", st)
    d.save_screenshot(f"{OUT}/g1_progress.png")
    d.find_element(By.ID, "busyCancel").click()
    wait("return document.getElementById('busy').hidden", 30)
    time.sleep(0.8)
    print("after Cancel: slice height", js("return window.__app.state.model.mesh_opts.layer"), "| toasts:", [t for t in toasts() if "Cancel" in t])

    # ---- measure: a hole is recognised (Ø, centre, depth), centre-to-centre between two holes
    js("document.getElementById('sampleBtn').click()")
    wait("return window.__app.state.model?.source === 'initial draft.pdf' && window.__app.state.solution?.mesh")
    time.sleep(0.8)
    h = window = None
    for x in (30, 50):
        js(f"return window.__app.agentHandlers.add_object({{kind: 'cylinder', op: 'subtract', x: {x}, y: 5.5, w: 2, h: 2, z0: 0, z1: 1}})")
        time.sleep(1.2)
    wait("return document.getElementById('busy').hidden")
    time.sleep(0.6)
    print("features:", js("return window.__app.state.solution.features.circles.map(c => [c.hole ? 'hole' : 'boss', 2 * c.r, c.x, c.y, c.z0, c.z1])"))
    FIND = """const [cx0] = arguments, v = window.__app.viewer, r = v.renderer.domElement.getBoundingClientRect();
      for (let gy = 0.15; gy < 0.9; gy += 0.004) for (let gx = 0.05; gx < 0.95; gx += 0.004) {
        const x = Math.round(r.left + gx * r.width), y = Math.round(r.top + gy * r.height);
        if (document.elementFromPoint(x, y) !== v.renderer.domElement) continue;
        const h = v.pickSurface(x, y), f = h && window.__app.featureAt(h);
        // offsets from the element centre the way Selenium computes it (rounded down)
        if (f && f.kind === 'circle' && Math.abs(f.x - cx0) < 0.01) return [x - Math.floor(r.left + r.width / 2), y - Math.floor(r.top + r.height / 2)];
      }
      return null;"""
    js("document.getElementById('measureBtn').click()")
    canvas = d.find_element(By.CSS_SELECTOR, "#viewport canvas")
    p1 = js(FIND, 30)
    print("p1:", p1)
    ActionChains(d, duration=40).move_to_element_with_offset(canvas, *p1[:2]).perform(); time.sleep(0.3)
    print("hover label:", js("return document.querySelector('.pick-label')?.textContent"))
    ActionChains(d).click().perform(); time.sleep(0.4)
    print("after 1st click:", js("return document.querySelector('#measureBox .mb-rows').innerText.replace(/\\n/g, ' ')"))
    p2 = js(FIND, 50)
    js("""window.__ups = []; document.querySelector('#viewport canvas').addEventListener('pointerup', (e) => {
      const h = window.__app.viewer.pickSurface(e.clientX, e.clientY); window.__ups.push([e.clientX, e.clientY, h, h && window.__app.featureAt(h)]); }, true)""")
    ActionChains(d, duration=40).move_to_element_with_offset(canvas, *p2[:2]).perform(); time.sleep(0.3)
    print("hover label 2:", js("return document.querySelector('.pick-label')?.textContent"), "| target", p2)
    ActionChains(d).click().perform(); time.sleep(0.4)
    print("2nd click seen at:", js("return window.__ups"))
    print("after 2nd click:", js("return document.querySelector('#measureBox .mb-rows').innerText.replace(/\\n/g, ' ')"))
    d.save_screenshot(f"{OUT}/g2_measure.png")
    js("document.querySelector('#measureBox [data-dia]').click()"); time.sleep(0.4)
    print("kept Ø as dimension:", js("return window.__app.state.model.params.filter(p => p.kind === 'point').map(p => [p.name, +p.value.toFixed(3)])"))

    # ---- rename the project in the top bar, save with the Save dialog (stubbed: headless has no dialog)
    js("""window.__picked = null; window.showSaveFilePicker = async (o) => { window.__picked = {name: o.suggestedName, id: o.id};
      return { name: 'Renamed in dialog.a3d.json', createWritable: async () => ({ write: async (b) => { window.__picked.size = b.size; }, close: async () => {} }) }; };""")
    name = d.find_element(By.ID, "fileName")
    name.click(); time.sleep(0.2)
    ActionChains(d).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).send_keys("Plate with holes").send_keys(Keys.ENTER).perform()
    time.sleep(0.3)
    print("renamed:", js("return window.__app.state.projectName"), "| top bar:", name.text)
    d.find_element(By.ID, "saveBtn").click(); time.sleep(0.8)
    print("Save dialog:", js("return window.__picked"), "| name now:", js("return window.__app.state.projectName"),
          "| toast:", [t for t in toasts() if "saved" in t])
    js("""window.__picked = null; document.getElementById('exportBtn').click(); document.querySelector('[data-fmt=stl]').click();""")
    time.sleep(1.5)
    print("export dialog:", js("return window.__picked"))
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
