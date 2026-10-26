"""Drive the app in headless Edge: picture -> wizard -> cookie cutter -> solid -> custom objects -> export.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_outline.py http://127.0.0.1:5199 <abs path to pernicek.png> <screenshot dir>
Prints each step's result and any browser console errors; saves screenshots 1_wizard.png ... 6_drawing.png.
"""
import json
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.by import By

URL, IMG, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
log = []


def errors():
    for e in d.get_log("browser"):
        if e["level"] in ("SEVERE",):
            log.append(e["message"])
    return log


def wait(js, t=30):
    end = time.time() + t
    while time.time() < end:
        v = d.execute_script(js)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(js)


def shot(name):
    d.save_screenshot(f"{OUT}/{name}.png")


try:
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "imgInput").send_keys(IMG)
    wait("return document.querySelectorAll('.wz-cand').length > 0")
    time.sleep(0.5)
    shot("1_wizard")
    print("candidates:", d.execute_script("return [...document.querySelectorAll('.wz-conf')].map(e => e.textContent)"))
    w = d.find_element(By.CSS_SELECTOR, ".wz-w")
    w.clear(); w.send_keys("120")
    d.execute_script("document.querySelector('.wz-w').dispatchEvent(new Event('input'))")
    print("size:", d.execute_script("return [document.querySelector('.wz-w').value, document.querySelector('.wz-h').value]"))
    # an eyedropper hint round-trip: pick the background colour (green, left of the cookie)
    d.execute_script("document.querySelector('[data-tool=background]').click()")
    st = d.find_element(By.CSS_SELECTOR, ".wz-stage img")
    d.execute_script("""const r = arguments[0].getBoundingClientRect(), stage = document.querySelector('.wz-stage');
      for (const type of ['pointerdown', 'pointerup']) stage.dispatchEvent(new PointerEvent(type,
        {clientX: r.left + 0.02 * r.width, clientY: r.top + 0.5 * r.height, bubbles: true, button: 0, pointerId: 1}));""", st)
    d.execute_script("document.querySelector('[data-tool=background]').click()")  # tool off again
    time.sleep(0.3)
    wait("return document.querySelector('.wz-busy').hidden && document.querySelectorAll('.wz-cand').length > 0")
    print("after bg hint:", d.execute_script("return [...document.querySelectorAll('.wz-conf')].map(e => e.textContent)"),
          d.execute_script("return document.querySelectorAll('.wz-chip').length"), "chip(s)")
    shot("2_wizard_hint")
    d.find_element(By.CSS_SELECTOR, ".wz-use").click()
    wait("return window.__app.state.solution && window.__app.state.solution.mesh")
    time.sleep(0.8)
    shot("3_cutter")
    s = d.execute_script("const s = window.__app.state.solution; return {bbox: s.bbox, z: s.z_range, tris: s.mesh.count, ok: s.ok}")
    print("cutter:", json.dumps(s))
    print("status:", d.find_element(By.ID, "statusBar").text)

    # change width in Dimensions -> height follows (aspect lock)
    d.execute_script("""const i = document.querySelector('.param[data-param="width"] input');
      i.value = '150'; i.dispatchEvent(new Event('change'));""")
    wait("return Math.abs(window.__app.state.values.width - 150) < 1e-6")
    time.sleep(1.0)
    print("height row shows:", d.execute_script("""return document.querySelector('.param[data-param="height"] input').value"""))
    print("after width=150:", d.execute_script("return window.__app.state.values"))

    # solid preset
    d.execute_script("document.querySelector('.ol-preset [data-p=solid]').click()")
    time.sleep(1.5)
    wait("return window.__app.state.solution.z_range[1] === 6")
    shot("4_solid")
    print("solid z:", d.execute_script("return window.__app.state.solution.z_range"))

    # back to cutter, then convert to custom and add a cylinder subtract + a bar union
    d.execute_script("document.querySelector('.ol-preset [data-p=cutter]').click()")
    time.sleep(1.5)
    d.execute_script("[...document.querySelectorAll('#rtab-outline button')].find(b => b.textContent.startsWith('Edit as 3D')).click()")
    time.sleep(1.5)
    print("custom objects:", d.execute_script("return window.__app.state.model.objects.map(o => o.name + ':' + o.op)"))
    d.execute_script("[...document.querySelectorAll('#rtab-outline button')].find(b => b.textContent.includes('Bar')).click()")
    time.sleep(1.5)
    d.execute_script("[...document.querySelectorAll('#rtab-outline button')].find(b => b.textContent.includes('Cylinder')).click()")
    time.sleep(0.5)
    d.execute_script("""const sel = [...document.querySelectorAll('#rtab-outline .layer.open select')][0];
      sel.value = 'subtract'; sel.dispatchEvent(new Event('change'));""")
    time.sleep(1.5)
    # 2D shape on the outline
    d.execute_script("[...document.querySelectorAll('#rtab-outline button')].find(b => b.textContent.includes('Circle')).click()")
    time.sleep(2)
    shot("5_custom")
    print("custom:", d.execute_script("const s = window.__app.state.solution; return {ok: s.ok, tris: s.mesh.count, objs: s.objects.length, issues: s.issues.map(i => i.message)}"))
    print("status:", d.find_element(By.ID, "statusBar").text)
    # export STL through the app's API
    n = d.execute_script("""const st = window.__app.state;
      return fetch('/api/export/stl', {method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({model: st.model, values: st.values, layers: [], bends: []})}).then(r => r.arrayBuffer()).then(b => b.byteLength)""")
    print("stl bytes:", n)
    # drawing tab
    d.execute_script("document.querySelector('.tab[data-tab=drawing]').click()")
    time.sleep(0.5)
    shot("6_drawing")
finally:
    print("console errors:", errors())
    d.quit()
