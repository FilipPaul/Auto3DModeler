"""The app's shell for a new user, in Czech, with the real mouse and keyboard (headless Edge, 1280×800): an empty start
shows the start screen — ✏ New part, 📂 Open a file, 🎬 Demo, ✨ Ask the AI — and little else; each start works: a new
part opens the 3D model, ✨ opens the chat, a STEP picked through 📂 opens, a file dropped anywhere opens (also over a
3D model's view, which has no drop of its own), a demo opens. Every tab closed: the start screen again, with "No part
open". Save (also Ctrl+S) and Export ▾ are reachable; ✨ AI is in the top bar in every workspace. A tab right-clicked:
its menu (rename, duplicate, a window, close) in the suggestions' look, ↑ ↓ Enter Esc. The suggestions table of a face:
↓ goes into it, ↓ / ↑ between its rows, Enter runs one. The project widget is as tall as its rows. Screenshots at
1280×800 and 1600×1000.

  PYTHONIOENCODING=utf-8 py tools/e2e_ux_shell.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

URL, OUT = sys.argv[1], sys.argv[2]
ROOT = Path(__file__).resolve().parent.parent
STEP = str(ROOT / "samples" / "ExportFromOurApp" / "part_base_plate.step")
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1280,800")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"
P = "window.__app.project"
FAILS = []


def check(name, ok):
    print(("  ok   " if ok else "  FAIL ") + name)
    if not ok:
        FAILS.append(name)


def wait(script, t=30):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.15)
    raise TimeoutError(script)


def shown(sel):
    return js("const e = document.querySelector(arguments[0]); return !!e && !!e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden'", sel)


def start_open():
    return js("return document.body.classList.contains('start-open')")


def key(k, *mods):
    a = ActionChains(d)
    for m in mods:
        a.key_down(m)
    a.send_keys(k)
    for m in mods:
        a.key_up(m)
    a.perform()
    time.sleep(0.25)


# a 10 mm cube as an ASCII STL, dropped (as from the file manager) on the element under the point x, y
DROP = """const [x, y, name] = arguments, v = [[0,0,0],[10,0,0],[10,10,0],[0,10,0],[0,0,10],[10,0,10],[10,10,10],[0,10,10]];
  const f = [[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],[1,2,6],[1,6,5],[2,3,7],[2,7,6],[3,0,4],[3,4,7]];
  let s = 'solid cube\\n';
  for (const t of f) s += `facet normal 0 0 0\\nouter loop\\n${t.map(i => `vertex ${v[i].join(' ')}`).join('\\n')}\\nendloop\\nendfacet\\n`;
  const dt = new DataTransfer();
  dt.items.add(new File([s + 'endsolid cube\\n'], name, { type: 'model/stl' }));
  const el = document.elementFromPoint(x, y);
  for (const type of ['dragenter', 'dragover']) el.dispatchEvent(new DragEvent(type, { dataTransfer: dt, bubbles: true, cancelable: true, clientX: x, clientY: y }));
  const over = document.body.classList.contains('file-over');
  el.dispatchEvent(new DragEvent('drop', { dataTransfer: dt, bubbles: true, cancelable: true, clientX: x, clientY: y }));
  return over;"""

try:
    for p in json.loads(urllib.request.urlopen(f"{URL}/api/projects").read())["projects"]:  # (a clean start: no "continue")
        urllib.request.urlopen(urllib.request.Request(f"{URL}/api/projects/{p['id']}", method="DELETE"))
    d.get(URL)
    js("localStorage.clear(); localStorage.setItem('auto3d-lang', 'cs')")
    d.get(URL)
    wait("return !!window.__app")
    time.sleep(1.2)

    # ---------------------------------------------------------------- the first impression
    cards = [c.find_element(By.CSS_SELECTOR, "b").text for c in d.find_elements(By.CSS_SELECTOR, ".st-card")]
    print("the start screen:", cards)
    check("an empty start: the start screen with ✏ / 📂 / 🎬 / ✨", start_open() and len(cards) == 4 and shown(".start-screen"))
    check("…in Czech", cards == ["Nový díl", "Otevřít soubor", "Demo", "Zeptat se AI"])
    check("…title: Co chcete vytvořit?", d.find_element(By.CSS_SELECTOR, ".st-title").text == "Co chcete vytvořit?")
    calm = js("""return [...document.querySelectorAll('button, .btn, input:not([type=file]), select')].filter(e => e.getClientRects().length
      && getComputedStyle(e).visibility !== 'hidden' && !e.closest('[hidden]')).length""")
    print("controls in sight:", calm)
    check("calm: at most 14 controls in sight (top bar + 4 cards)", calm <= 14)
    check("no quick part panels behind it (Dimensions / 3D design hidden)", not shown("#tab-params") and not shown("#rtab-design"))
    check("the file name is empty, not 'no drawing'", d.find_element(By.ID, "fileName").text.strip() == "")
    check("✨ AI in the top bar", shown("#aiBtn"))
    d.save_screenshot(f"{OUT}/ux_start_1280.png")
    d.set_window_size(1600, 1000)
    time.sleep(0.4)
    d.save_screenshot(f"{OUT}/ux_start_1600.png")
    d.set_window_size(1280, 800)
    time.sleep(0.4)
    # ←→ between the cards
    d.find_element(By.CSS_SELECTOR, ".st-card[data-start=new]").send_keys(Keys.ARROW_RIGHT)
    check("→ moves to 📂 Open a file", js("return document.activeElement?.dataset.start") == "open")

    # ---------------------------------------------------------------- ✨ Ask the AI: the chat, in the drawer
    d.find_element(By.CSS_SELECTOR, ".st-card[data-start=ai]").click()
    time.sleep(0.4)
    check("✨ Ask the AI: the chat opens beside the start screen", shown("#aiDrawer") and shown("#aiDrawer textarea") and start_open())
    d.save_screenshot(f"{OUT}/ux_start_ai.png")
    d.find_element(By.ID, "aiClose").click()
    time.sleep(0.2)

    # ---------------------------------------------------------------- ✏ New part
    d.find_element(By.CSS_SELECTOR, ".st-card[data-start=new]").click()
    wait("return window.__app.state.workspace === 'model'")
    time.sleep(0.6)
    check("✏ New part: a 3D model, its tab, the start screen gone", not start_open() and js(f"return {P}.parts.length") == 1)
    ph = js("return document.querySelector('#leftCol .lw-widget[data-w=project]').getBoundingClientRect().height")
    print("the project widget with one part:", round(ph), "px")
    check("the project widget as tall as its rows (one part: ≤ 90 px)", 0 < ph <= 90)
    if js(f"return !!{M}.sk"):
        js(f"{M}.cancelSketch()")  # (a new part starts in a sketch)
    time.sleep(0.3)

    # ---------------------------------------------------------------- the tab's menu: right-click
    tab = d.find_element(By.CSS_SELECTOR, "#partTabs .part-tab")
    ActionChains(d).context_click(tab).perform()
    time.sleep(0.3)
    items = [" ".join(b.text.split()) for b in d.find_elements(By.CSS_SELECTOR, ".sg-menu .vs-list button")]
    print("the tab's menu:", items)
    check("a tab right-clicked: Rename, Duplicate, a new window, Close", len(items) == 4 and items[0].endswith("Přejmenovat") and "Duplikovat" in items[1] and "Zavřít záložku" in items[3])
    d.save_screenshot(f"{OUT}/ux_tab_menu.png")
    check("…the first row in the keyboard's hand", js("return document.activeElement?.matches('.sg-menu .vs-list button')") and "Přejmenovat" in js("return document.activeElement.textContent"))
    key(Keys.ARROW_DOWN)
    check("↓: Duplicate", "Duplikovat" in js("return document.activeElement.textContent"))
    key(Keys.ARROW_UP)
    key(Keys.ENTER)
    time.sleep(0.3)
    check("Enter on Rename: the name is being typed", js("return !!document.querySelector('#partTabs [contenteditable=true], #partTabs input, #partTabs .editing')") and not shown(".sg-menu"))
    a = ActionChains(d)
    a.key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).send_keys("Držák").send_keys(Keys.ENTER).perform()
    time.sleep(0.3)
    check("…renamed to Držák", js(f"return {P}.current.name") == "Držák")
    ActionChains(d).context_click(d.find_element(By.CSS_SELECTOR, "#partTabs .part-tab")).perform()
    time.sleep(0.2)
    key(Keys.ESCAPE)
    check("Esc closes the menu", not shown(".sg-menu"))

    # ---------------------------------------------------------------- save / export reachable
    check("Save project enabled", js("return !document.getElementById('saveBtn').disabled"))
    js("""window.__saveClicks = 0; window.addEventListener('click', (e) => { if (e.target.closest?.('#saveBtn')) { window.__saveClicks++; e.stopPropagation(); e.preventDefault(); } }, true);""")
    js("document.activeElement?.blur()")
    key("s", Keys.CONTROL)
    check("Ctrl+S: Save project", js("return window.__saveClicks") == 1)

    # ---------------------------------------------------------------- a face's suggestions with the keyboard
    H = "window.__app.agentHandlers"
    js(f"return {H}.add_feature({{ type: 'sketch', plane: 'XY', shapes: [{{ rect: {{ x: 0, y: 0, w: 40, h: 20 }} }}] }})")
    js(f"return {H}.add_feature({{ type: 'extrude', sketch: 'F1', d: 10 }})")
    wait(f"return !!{M}.result?.body && !{M}.inflight")
    check("Export ▾ enabled with a solid", js("return !document.getElementById('exportBtn').disabled"))
    d.find_element(By.ID, "exportBtn").click()
    time.sleep(0.3)
    fm = [b.text for b in d.find_elements(By.CSS_SELECTOR, "#exportMenu [data-fmt]:not(.off) .fm-t b") if b.is_displayed()]
    check("Export ▾: STL and STEP in sight", any(x.startswith("STL") for x in fm) and any(x.startswith("STEP") for x in fm))
    key(Keys.ESCAPE)
    time.sleep(0.2)
    check("Esc closes Export ▾", not js("return document.getElementById('exportMenuWrap').classList.contains('open')"))
    js(f"{M}.view.setView('iso')")
    time.sleep(0.6)
    cv = d.find_element(By.CSS_SELECTOR, "#modelViewport canvas")
    dx, dy = js(f"""const v = {M}.view, p = new (v.camera.position.constructor)(20, 10, 10);
      const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""")
    ActionChains(d, duration=30).move_to_element_with_offset(cv, dx, dy).perform()
    time.sleep(0.2)
    ActionChains(d).click().perform()
    time.sleep(0.6)
    rows = [" ".join(b.text.split()) for b in d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-list button")]
    print("a face's table:", rows[:4], "| head:", js("return document.querySelector('#modelViewport .view-suggest .vs-set')?.textContent"))
    check("the table's head: 'Prvních 8' (its setting), one line", js("return document.querySelector('#modelViewport .view-suggest .vs-set').textContent") == "Prvních 8"
          and js("const h = document.querySelector('#modelViewport .view-suggest .vs-head'); return h.offsetHeight < 34"))
    js("document.activeElement?.blur()")
    key(Keys.ARROW_DOWN)
    first = js("return document.activeElement?.matches('#modelViewport .view-suggest .vs-list button') && document.activeElement.textContent")
    check("↓: into the table, its first row", bool(first) and "Skica na této ploše" in first)
    key(Keys.ARROW_DOWN)
    key(Keys.ARROW_UP)
    check("↓ ↑: back on the first row", js("return document.activeElement.textContent") == first)
    d.save_screenshot(f"{OUT}/ux_suggest_keys.png")
    key(Keys.ENTER)
    time.sleep(0.6)
    check("Enter runs it: a sketch on the face", js(f"return !!{M}.sk"))
    key(Keys.ESCAPE)
    time.sleep(0.3)
    if js(f"return !!{M}.sk"):
        js(f"{M}.cancelSketch()")
    time.sleep(0.3)

    # ---------------------------------------------------------------- a file dropped on a 3D model's view
    vp = d.find_element(By.ID, "modelViewport").rect
    over = js(DROP, vp["x"] + vp["width"] / 2, vp["y"] + vp["height"] / 2, "kostka.stl")
    check("a file over the window: the dashed frame", over)
    wait(f"return {P}.parts.some(p => p.name === 'kostka') && !!window.__app.state.solution?.mesh", 60)
    check("an STL dropped on a 3D model's view: it opens as a part of its own", js(f"return {P}.current.name") == "kostka" and not js("return document.body.classList.contains('file-over')"))
    check("✨ AI also in the quick part's top bar", shown("#aiBtn"))
    d.find_element(By.ID, "aiBtn").click()
    time.sleep(0.3)
    check("…there it shows the panel's ✨ AI tab", js("return document.querySelector('.tab[data-tab=ai]').classList.contains('active')"))
    js("document.querySelector('.tab[data-tab=params]').click()")
    d.save_screenshot(f"{OUT}/ux_quick_1280.png")

    # ---------------------------------------------------------------- every tab closed: the start screen again
    for _ in range(4):
        x = d.find_elements(By.CSS_SELECTOR, "#partTabs .part-tab .pt-x")
        if not x:
            break
        x[0].click()
        time.sleep(0.5)
    check("every tab closed: the start screen with 'No part open'", start_open() and "Žádný díl" in d.find_element(By.CSS_SELECTOR, ".start-screen .no-part").text)
    check("…the project tree beside it", shown("#leftCol .lw-widget[data-w=project]"))
    d.save_screenshot(f"{OUT}/ux_none_open.png")

    # ---------------------------------------------------------------- 📂 Open a file: a STEP
    d.find_element(By.ID, "anyInput").send_keys(STEP)
    wait("return window.__app.state.workspace === 'model' && !!window.__app.modeler.result?.body && !document.body.classList.contains('start-open')", 90)
    check("📂 Open a file (a STEP): it opens as a 3D model", js(f"return {P}.current.name").startswith("part_base_plate"))

    # ---------------------------------------------------------------- 🎬 Demo from the start screen (a new project)
    for _ in range(6):
        x = d.find_elements(By.CSS_SELECTOR, "#partTabs .part-tab .pt-x")
        if not x:
            break
        x[0].click()
        time.sleep(0.4)
    d.find_element(By.CSS_SELECTOR, ".st-card[data-start=demo]").click()
    wait("return document.querySelectorAll('.demos [data-open]').length > 0")
    d.find_element(By.CSS_SELECTOR, ".demos [data-open]").click()
    wait("return window.__app.state.workspace === 'assembly' && window.__app.project.parts.length >= 4", 150)  # (the first open after a server start also starts its kernel processes)
    check("🎬 Demo: the mechanism opens (an assembly and its parts)", not start_open())
    time.sleep(1)
    d.set_window_size(1600, 1000)
    time.sleep(0.6)
    d.save_screenshot(f"{OUT}/ux_demo_1600.png")

    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    check("no console errors", not errs)
finally:
    d.quit()
print("all checks OK" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}")
sys.exit(1 if FAILS else 0)
