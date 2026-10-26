"""Undo / redo (Ctrl+Z / Ctrl+Y), selecting any object by clicking it in 3D, Delete, and deleting
dimensions from their 3D label — in headless Edge with real keyboard and mouse input.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_history.py http://127.0.0.1:5199 <out dir>
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


def wait(script, t=30):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(script)


def settle():
    time.sleep(0.4)
    wait("return document.getElementById('busy').hidden")
    time.sleep(0.9)  # the history records a step 600 ms after a rebuild


def vol():
    return round(js("return window.__app.state.solution.volume"), 3)


def key(k, shift=False):
    a = ActionChains(d).key_down(Keys.CONTROL)
    if shift:
        a = a.key_down(Keys.SHIFT)
    a = a.send_keys(k)
    if shift:
        a = a.key_up(Keys.SHIFT)
    a.key_up(Keys.CONTROL).perform()
    settle()


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#viewport canvas")


def click_canvas(dx, dy):
    ActionChains(d, duration=40).move_to_element_with_offset(canvas(), int(dx), int(dy)).click().perform()


FIND = """const [z] = arguments, v = window.__app.viewer, r = v.renderer.domElement.getBoundingClientRect();
for (let gy = 0.15; gy < 0.9; gy += 0.01) for (let gx = 0.1; gx < 0.9; gx += 0.01) {
  const cx = Math.round(r.left + gx * r.width), cy = Math.round(r.top + gy * r.height);
  if (document.elementFromPoint(cx, cy) !== v.renderer.domElement) continue; // a label or panel is on top there
  const h = v.pickSurface(cx, cy);
  if (h && (h.snap === 'top face' || (h.snap === 'corner' && h.normal[2] > 0.9)) && Math.abs(h.z - z) < 1e-6) return [cx - r.left - r.width / 2, cy - r.top - r.height / 2, h];
}
return null;"""


def place(kind_btn, z):
    js("[...document.querySelectorAll('#rtab-outline .row-actions button')].find(b => b.dataset.a === arguments[0] && b.closest('div').textContent.includes('Bar')).click()", kind_btn)
    time.sleep(0.4)
    s = js(FIND, z)
    click_canvas(s[0], s[1])
    settle()
    return s[2]


try:
    d.get(URL)
    wait("return !!window.__app")
    js("document.getElementById('sampleBtn').click()")
    wait("return window.__app.state.solution && window.__app.state.solution.mesh")
    settle()
    v0 = vol()
    print("start:", v0, "| undo enabled:", js("return !document.getElementById('undoBtn').disabled"))

    # 1. a dimension edit, Ctrl+Z, Ctrl+Y
    js("""const i = document.querySelector('.param[data-param="p1"] input'); i.value = '90'; i.dispatchEvent(new Event('change'));""")
    settle()
    v1 = vol()
    d.find_element(By.TAG_NAME, "body").click()
    key("z")
    print(f"length 90: {v0} -> {v1}; Ctrl+Z -> {vol()} (length {js('return window.__app.state.values.p1')})")
    key("y")
    print(f"Ctrl+Y -> {vol()} (length {js('return window.__app.state.values.p1')})")
    key("z")

    # 2. a box placed on the top face (z = 1 cm), then select it by clicking it and Delete
    js("document.querySelector('.rtab[data-rtab=outline]').click()")
    hit = place("rect", 1)
    v2 = vol()
    box = js("return window.__app.state.model.extras.at(-1)")
    print(f"box placed at ({box['x']:.2f}, {box['y']:.2f}) z {box['z0']}..{box['z1']}: volume {v0} -> {v2}")
    js("window.__app.outlinePanel.selected = null; window.__app.outlinePanel.render()")
    # click on the box's top (z1), found on screen
    top = js(FIND, box["z1"])
    click_canvas(top[0], top[1])
    time.sleep(0.4)
    print("clicked the box -> selected:", js("return window.__app.outlinePanel.selected") == box["id"],
          "| highlight rings:", js("return window.__app.viewer.selectionRings?.length || 0"))
    d.save_screenshot(f"{OUT}/h1_selected.png")
    ActionChains(d).send_keys(Keys.DELETE).perform()
    settle()
    print(f"Delete -> extras {len(js('return window.__app.state.model.extras'))}, volume {vol()}")
    key("z")
    print(f"Ctrl+Z -> extras {len(js('return window.__app.state.model.extras'))}, volume {vol()}")

    # 2b. a profile band (not a primitive: selected through its footprint from the server)
    js("[...document.querySelectorAll('#rtab-outline .row-actions button')].find(b => b.dataset.a === 'band' && b.closest('div').textContent.includes('Bar')).click()")
    settle()
    band = js("return window.__app.state.model.extras.at(-1)")
    js("window.__app.outlinePanel.selected = null; window.__app.outlinePanel.render()")
    top = js(FIND, band["z1"])
    click_canvas(top[0], top[1])
    time.sleep(0.4)
    print(f"profile band z {band['z0']}..{band['z1']}: clicked it -> selected:", js("return window.__app.outlinePanel.selected") == band["id"],
          "| highlight rings:", js("return window.__app.viewer.selectionRings?.length || 0"))
    ActionChains(d).send_keys(Keys.DELETE).perform()
    settle()
    print("Delete -> band gone:", not js("return window.__app.state.model.extras.some(o => o.id === arguments[0])", band["id"]))

    # 3. a point dimension (reference on PDF parts) deleted with its label ✕, then undone
    js("""window.__app.state.model.point_dims = window.__app.state.model.point_dims || [];""")
    js("document.getElementById('measureBtn').click()")
    for z in (1, 1):
        pass
    a = js(FIND, 1)
    click_canvas(a[0], a[1]); time.sleep(0.3)
    b = js(FIND.replace("gx = 0.1", "gx = 0.5"), 1)
    click_canvas(b[0], b[1]); time.sleep(0.4)
    js("document.querySelector('#measureBox [data-axis=d]').click()")
    settle()
    pid = js("return window.__app.state.model.params.find(p => p.kind === 'point')?.id")
    lab = js("return [...document.querySelectorAll('.dim-label')].find(e => e.querySelector('.dim-x') && e.title.includes('Dimension'))")
    ActionChains(d).move_to_element(lab).perform(); time.sleep(0.2)
    x = lab.find_element(By.CSS_SELECTOR, ".dim-x")
    print("label ✕ visible on hover:", x.is_displayed())
    ActionChains(d).move_to_element(x).click().perform()
    settle()
    print("✕ -> point dimension gone:", not js("return window.__app.state.model.params.some(p => p.id === arguments[0])", pid))
    key("z")
    print("Ctrl+Z -> back:", js("return window.__app.state.model.params.some(p => p.id === arguments[0])", pid))

    # 4. redo all the way, then the toolbar buttons
    key("z", shift=True)
    print("Ctrl+Shift+Z (redo) -> gone again:", not js("return window.__app.state.model.params.some(p => p.id === arguments[0])", pid))
    js("document.getElementById('undoBtn').click()"); settle()
    print("↶ button -> back:", js("return window.__app.state.model.params.some(p => p.id === arguments[0])", pid),
          "| redo enabled:", js("return !document.getElementById('redoBtn').disabled"))
    d.save_screenshot(f"{OUT}/h2_end.png")
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
