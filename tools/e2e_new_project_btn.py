"""📄 New project in the top bar (next to ＋ New 3D model), in headless Edge, Czech: with a part open, a click shows a
small box saying what happens to the project on screen (saved, in 🕘 Recent projects, its name) and offers here / a new
window -> "Nový projekt tady" -> the start screen, an empty project; the old one in Recent. No console errors.

  PYTHONIOENCODING=utf-8 py tools/e2e_new_project_btn.py http://127.0.0.1:5199 <out dir>
"""
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
bad = []


def check(ok, what):
    print(("  ok  " if ok else "  FAIL") + " " + what)
    if not ok:
        bad.append(what)


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.setItem('auto3d-lang', 'cs')")
    d.get(URL + "?new")
    wait("return !!window.__app")
    time.sleep(1)
    order = js("return [...document.querySelectorAll('.topbar .actions > *')].map(e => e.id || e.querySelector('button')?.id).slice(0, 3)")
    check(order[:2] == ["newProjWrap", "newModelBtn"], f"📄 Nový projekt sits next to ＋ Nový 3D model: {order}")
    d.find_element(By.ID, "newModelBtn").click()
    wait("return window.__app.project.parts.length > 0")
    js("window.__app.state.projectName = 'Držák motoru'")
    time.sleep(3)  # (autosave)
    d.find_element(By.ID, "newProjTopBtn").click()
    time.sleep(0.3)
    say = js("return document.querySelector('#newProjPop .np-say')?.innerText || ''")
    check("Držák motoru" in say and "nic se neztratí" in say and "Nedávné" in say, f"the box says what happens to the open project: {say!r}")
    btns = [b.text for b in d.find_elements(By.CSS_SELECTOR, "#newProjPop button")]
    check(any("Nový projekt tady" in b for b in btns) and any("V novém okně" in b for b in btns), f"here / a new window: {btns}")
    d.save_screenshot(f"{OUT}/new_project_box.png")
    d.find_element(By.CSS_SELECTOR, "#newProjPop [data-np=here]").click()
    wait("return !!window.__app && window.__app.project && window.__app.project.parts.length === 0", 60)
    time.sleep(1)
    check(js("return !!document.querySelector('.start-screen, #startScreen, .st-card')"), "the new project opens on the start screen")
    errs = [x["message"] for x in d.get_log("browser") if x["level"] == "SEVERE"]
    check(not errs, f"no console errors {errs}")
finally:
    d.quit()
print("ALL OK" if not bad else f"FAILED: {bad}")
sys.exit(1 if bad else 0)
