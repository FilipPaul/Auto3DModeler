"""Outline round trip in headless Edge: edit an outline -> part; enlarge the Drawing tab; reopen the
editor from the part (the edit and hints come back); save the project, reload, open it, reopen again.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_outline_project.py http://127.0.0.1:5199 <abs path to pernicek.png> <out dir>
"""
import json
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.actions.wheel_input import ScrollOrigin
from selenium.webdriver.common.by import By

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from auto3d import package  # noqa: E402  (the saved .a3d read back)

URL, IMG, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
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


def idle():
    time.sleep(0.4)
    wait("return !document.querySelector('.wz-busy') || document.querySelector('.wz-busy').hidden")
    time.sleep(0.6)


def at(fx, fy):
    return js("""const [fx, fy] = arguments, st = document.querySelector('.wz-stage').getBoundingClientRect(),
        r = document.querySelector('.wz-stage svg').getBoundingClientRect();
      return [Math.round(r.left + fx * r.width - st.left - st.width / 2), Math.round(r.top + fy * r.height - st.top - st.height / 2)];""", fx, fy)


def click(fx, fy):
    ActionChains(d, duration=30).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, ".wz-stage"), *at(fx, fy)).click().perform()


def dblclick(fx, fy):
    ActionChains(d, duration=30).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, ".wz-stage"), *at(fx, fy)).double_click().perform()


def first():
    return js("""const w = window.__app.wizard, c = w.list()[w.sel], rows = [...document.querySelectorAll('.wz-cand')];
      return {selected: w.sel, label: rows[w.sel]?.querySelector('.wz-cbody b').textContent, area: c.area,
              mask: !!w.mask, smoothing: w.hints.smoothing, seeds: w.hints.seeds.length}""")


def solution_area():
    return js("return window.__app.state.solution.volume / 6")  # solid shape, 6 mm thick


try:
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "imgInput").send_keys(IMG)
    wait("return document.querySelectorAll('.wz-cand').length > 0"); idle()

    # hints the editor must remember: smoothing 2 and an 'inside' point
    js("const i = document.querySelector('[data-h=smoothing]'); i.value = '2'; i.dispatchEvent(new Event('change'))"); idle()
    js("document.querySelector('[data-tool=seed]').click()"); click(0.5, 0.55); idle()
    js("document.querySelector('[data-tool=seed]').click()")

    # edit #1: remove the right half with a polygon (double-click closes), then use it as a solid shape
    js("document.querySelector('.wz-edit-btn').click()"); idle()
    js("document.querySelector('[data-tool=poly]').click()"); js("document.querySelector('[data-mode=remove]').click()")
    for p in [(0.5, 0.0), (1.0, 0.0), (1.0, 1.0)]:
        click(*p)
    dblclick(0.5, 1.0); idle()
    edited = first()
    print("edited in the wizard:", edited)
    js("document.querySelector('.wz-preset [data-p=solid]').click()")
    js("const w = document.querySelector('.wz-w'); w.value = '60'; w.dispatchEvent(new Event('input'))")
    d.find_element(By.CSS_SELECTOR, ".wz-use").click()
    wait("return window.__app.state.solution && window.__app.state.solution.mesh"); time.sleep(1)
    a1 = solution_area()
    print(f"part: {js('return window.__app.state.values')}, area {a1:.0f} mm², editor saved: "
          f"{js('const e = window.__app.state.outlineEditor; return {mask: !!(e && e.mask), smoothing: e && e.hints.smoothing}')}")

    # Drawing tab: enlarge, zoom with the wheel, close
    js("document.querySelector('.tab[data-tab=drawing]').click()"); time.sleep(0.4)
    d.save_screenshot(f"{OUT}/p1_drawing_tab.png")
    js("document.getElementById('drawingEnlarge').click()"); time.sleep(0.5)
    st = d.find_element(By.CSS_SELECTOR, ".lb-stage")
    ActionChains(d).scroll_from_origin(ScrollOrigin.from_element(st, -100, -60), 0, -500).perform(); time.sleep(0.4)
    print("lightbox zoom:", js("return document.querySelector('.lb-val').textContent"),
          "| has the outline:", js("return !!document.querySelector('.lb-content svg path')"))
    d.save_screenshot(f"{OUT}/p2_lightbox.png")
    ActionChains(d).send_keys("").perform(); time.sleep(0.3)  # Esc
    print("lightbox closed:", js("return !document.querySelector('.lightbox')"))

    # reopen the editor from the part (3D toolbar)
    js("document.getElementById('editOutlineBtn').click()")
    wait("return document.querySelectorAll('.wz-cand').length > 1"); idle()
    re1 = first()
    print("reopened from the part:", re1, "| same area:", abs(re1["area"] - edited["area"]) < 0.005)
    d.save_screenshot(f"{OUT}/p3_reopened.png")
    # change it: add back a box on the right with a polygon -> apply to the part
    js("document.querySelector('.wz-edit-btn').click()")
    js("document.querySelector('[data-tool=poly]').click()"); js("document.querySelector('[data-mode=add]').click()")
    for p in [(0.6, 0.3), (0.8, 0.3), (0.8, 0.6)]:
        click(*p)
    dblclick(0.6, 0.6); idle()
    d.find_element(By.CSS_SELECTOR, ".wz-use").click(); time.sleep(2)
    a2 = solution_area()
    print(f"applied to the part: area {a1:.0f} -> {a2:.0f} mm²")

    # save the project (capture the download), reload, open it
    js("""window.__saved = null; window.showSaveFilePicker = async (o) => ({ name: o.suggestedName,
      createWritable: async () => ({ write: async (b) => { const u = new Uint8Array(await b.arrayBuffer()); let s = ''; for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode(...u.subarray(i, i + 0x8000)); window.__saved = btoa(s); }, close: async () => {} }) });""")
    js("document.getElementById('saveBtn').click()")
    saved = __import__("base64").b64decode(wait("return window.__saved"))
    proj = (lambda p: next(q for q in p["parts"] if q["id"] == p["active"]["part"])["classic"])(package.load(saved)["project"])  # project v3: the part on screen
    path = Path(OUT) / "roundtrip.a3d"
    path.write_bytes(saved)
    print(f"project saved: {len(saved) // 1024} kB, outline_editor: mask {bool(proj.get('outline_editor', {}).get('mask'))}, "
          f"hints.seeds {len(proj['outline_editor']['hints']['seeds'])}, picture {bool(proj['preview'].get('image'))}")
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "projectInput").send_keys(str(path.resolve()))
    wait("return window.__app.state.solution && window.__app.state.solution.mesh"); time.sleep(1)
    print(f"project opened: area {solution_area():.0f} mm² (was {a2:.0f}), editor: "
          f"{js('const e = window.__app.state.outlineEditor; return {mask: !!(e && e.mask), smoothing: e && e.hints.smoothing}')}")
    js("[...document.querySelectorAll('#rtab-outline button')].find(b => b.textContent.includes('Edit outline')).click()")
    wait("return document.querySelectorAll('.wz-cand').length > 1"); idle()
    re2 = first()
    print("reopened after project load:", re2)
    d.save_screenshot(f"{OUT}/p4_after_load.png")
    # discard the edit: the outline in use stays listed
    js("document.querySelector('.wz-cand.edited [data-a=drop]').click()"); time.sleep(0.4)
    print("after discarding the edit:", first())
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
