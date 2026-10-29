"""📄 New project, in headless Edge (Czech): a project with a 3D model open -> Otevřít ▾ › 📄 Nový projekt -> the start
screen with an empty project (a new autosave id, the window's title back to the app's), the toast says where the
previous one is; the previous project is in 🕘 Recent projects and ↶ in the toast opens it again (its parts and steps)
-> Ctrl+Alt+N does the same; the project widget's ⋯ menu has it too; an empty project: nothing happens but a note ->
⧉ New project in a new window: a second window with the start screen, the first one as it was.

  A3D_DATA=<a scratch folder> py server.py --port 5199 --no-browser
  PYTHONIOENCODING=utf-8 py tools/e2e_new_project.py http://127.0.0.1:5199 <out dir>
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
Path(OUT).mkdir(parents=True, exist_ok=True)
H = "window.__app.agentHandlers"
M = "window.__app.modeler"
FAILS = []


def browser():
    opts = webdriver.EdgeOptions()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1400,900")
    return webdriver.Edge(options=opts)


d = browser()
js = d.execute_script


def check(name, ok):
    print(("  ok   " if ok else "  FAIL ") + name)
    if not ok:
        FAILS.append(name)


def wait(script, t=40, drv=None):
    end = time.time() + t
    while time.time() < end:
        v = (drv or d).execute_script(script)
        if v:
            return v
        time.sleep(0.15)
    raise TimeoutError(script)


def recent():
    with urllib.request.urlopen(f"{URL}/api/projects") as r:
        return json.loads(r.read())["projects"]


def ready(drv=None):
    wait("return !!window.__app && !!window.__app.autosave", drv=drv)
    time.sleep(0.8)


def make_block(name, drv=None):
    x = (drv or d).execute_script
    x(f"return {H}.new_model({{ name: arguments[0] }})", name)
    x(f"return {H}.add_feature({{ type: 'sketch', plane: 'XY', shapes: [{{ rect: {{ x: 0, y: 0, w: 40, h: 20 }} }}] }})")
    x(f"return {H}.add_feature({{ type: 'extrude', sketch: 'F1', d: 6 }})")
    wait(f"return !!{M}.result?.body && !{M}.inflight", drv=drv)


def toast_text():
    return js("return [...document.querySelectorAll('#toasts .toast')].map(t => t.textContent).join(' | ')")


def open_menu_item(btn_id):
    d.find_element(By.ID, "openBtn").click()
    time.sleep(0.2)
    d.find_element(By.ID, btn_id).click()


try:
    for p in recent():  # (a clean start)
        urllib.request.urlopen(urllib.request.Request(f"{URL}/api/projects/{p['id']}", method="DELETE"))
    d.get(URL)
    js("localStorage.setItem('auto3d-lang', 'cs')")
    d.get(URL)
    ready()
    make_block("Konzola")
    old_id = js("return window.__app.autosave.id")
    check(f"the window's title names the project: {d.title!r}", "Konzola" in d.title)
    d.find_element(By.ID, "openBtn").click()
    time.sleep(0.2)
    item = d.find_element(By.ID, "newProjectBtn")
    check(f"Otevřít ▾ has 📄 Nový projekt: {item.text!r}", "Nový projekt" in item.text and "Ctrl+Alt+N" in item.text)
    check("… and ⧉ Nový projekt v novém okně", "Nový projekt v novém okně" in d.find_element(By.ID, "newProjectWinBtn").text)
    d.save_screenshot(str(Path(OUT) / "np_menu.png"))
    item.click()
    wait("return !!window.__app && !!window.__app.autosave && document.readyState === 'complete'")
    ready()
    check("the start screen with an empty project", js("return document.body.classList.contains('start-open') && window.__app.project.parts.length === 0"))
    new_id = js("return window.__app.autosave.id")
    check("a new autosave id", new_id != old_id)
    check(f"the window's title is the app's again: {d.title!r}", "Konzola" not in d.title)
    check("no ?new left in the address", "new" not in js("return location.search"))
    check("no 'continue where you left off' bar (a new project was asked for)", not d.find_elements(By.CSS_SELECTOR, ".restore-bar"))
    tt = toast_text()
    check(f"the toast says where the previous one is: {tt!r}", "Předchozí projekt „Konzola“ je uložen" in tt and "Nedávné projekty" in tt)
    rec = recent()
    check(f"the previous project is in Recent: {[p['name'] for p in rec]}", any(p["id"] == old_id and p["name"] == "Konzola" for p in rec))
    d.save_screenshot(str(Path(OUT) / "np_after.png"))
    # ↶ in the toast: the previous project again
    d.find_element(By.CSS_SELECTOR, "#toasts .toast button").click()
    wait(f"return window.__app.project.parts.length === 1 && !!{M}.result?.body", 30)
    check("↶ Otevřít znovu: the previous project, its part and steps", js(f"return window.__app.project.parts[0].name === 'Konzola' && {M}.part.features.length === 2"))
    check("… under its own id (not a copy)", js("return window.__app.autosave.id") == old_id)

    # Ctrl+Alt+N
    ActionChains(d).key_down(Keys.CONTROL).key_down(Keys.ALT).send_keys("n").key_up(Keys.ALT).key_up(Keys.CONTROL).perform()
    wait("return document.readyState === 'complete' && !!window.__app && window.__app.project.parts.length === 0 && document.body.classList.contains('start-open')", 30)
    ready()
    check("Ctrl+Alt+N: an empty project again", js("return window.__app.autosave.id") not in (old_id, new_id))
    # an empty project: a note, nothing else
    before = js("return window.__app.autosave.id")
    open_menu_item("newProjectBtn")
    time.sleep(0.8)
    check(f"an empty project: only a note ({toast_text()!r})", js("return window.__app.autosave.id") == before and "už je prázdný" in toast_text())

    # the project widget's ⋯ menu
    make_block("Deska")
    js("window.__leftDock.dock('project')")
    time.sleep(0.4)
    js("document.querySelector('.lw-widget[data-w=project] .lw-menu').click()")
    time.sleep(0.3)
    labels = js("return [...document.querySelectorAll('.lw-pop button')].map(b => b.textContent.trim())")
    check(f"the project widget's ⋯ menu: {labels[:3]}", any("Nový projekt" == x.replace("📄", "").strip() for x in labels) and any("v novém okně" in x for x in labels))
    d.save_screenshot(str(Path(OUT) / "np_widget_menu.png"))
    js("window.__leftDock.closeMenu()")
    # the suggestions widget docked, nothing selected: its row
    js("window.__leftDock.dock('suggest')")
    time.sleep(0.4)
    row = js("const b = document.querySelector('.lw-widget[data-w=suggest] .lw-sg-new'); return b && b.getClientRects().length ? b.textContent.trim() : ''")
    check(f"the docked suggestions with nothing selected: a 📄 row ({row!r})", "Nový projekt" in row)

    # ⧉ in a new window: this one stays, the other starts empty
    here = js("return window.__app.autosave.id")
    handles = d.window_handles
    open_menu_item("newProjectWinBtn")
    end = time.time() + 15
    while len(d.window_handles) == len(handles) and time.time() < end:
        time.sleep(0.2)
    new = [h for h in d.window_handles if h not in handles]
    check("⧉ a second window opened", len(new) == 1)
    if new:
        d.switch_to.window(new[0])
        ready()
        check("… with the start screen and an empty project", js("return document.body.classList.contains('start-open') && !window.__app.project.parts.length"))
        check("… a project of its own", js("return window.__app.autosave.id") != here)
        d.close()
        d.switch_to.window(handles[0])
    check("the first window kept its project", js("return window.__app.autosave.id") == here and js("return window.__app.project.parts.length") == 1)
finally:
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE" and "favicon" not in e["message"]]
    if errs:
        print("browser errors:", errs[:5])
    d.quit()

print("FAILS:", FAILS if FAILS else "none")
sys.exit(1 if FAILS else 0)
