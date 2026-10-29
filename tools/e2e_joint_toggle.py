"""🔗 Show: Joints in the assembly's bottom row (Snap / Hover / Show), in headless Edge, Czech: the crank demo opened, the
crank chosen -> its joints' symbols in the view -> 🔗 Vazby switched off: none -> a reload: still off (remembered) ->
switched on: back. No console errors.

  PYTHONIOENCODING=utf-8 py tools/e2e_joint_toggle.py http://127.0.0.1:5199 <out dir>
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
A = "window.__app.assembly"
bad = []


def check(ok, what):
    print(("  ok  " if ok else "  FAIL") + " " + what)
    if not ok:
        bad.append(what)


def wait(script, t=90):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def open_crank():
    d.find_element(By.ID, "openBtn").click()
    time.sleep(0.3)
    js("document.getElementById('demoBtn').click()")
    wait("return document.querySelectorAll('.demos [data-demo]').length")
    d.find_elements(By.CSS_SELECTOR, ".demos [data-demo]")[0].find_element(By.CSS_SELECTOR, "[data-open]").click()
    wait(f"return window.__app.state.workspace === 'assembly' && {A}.doc.instances.length > 1 && {A}.doc.instances.every(i => {A}.bodies[i.part]?.body)", 150)
    time.sleep(1)


def tags():
    return js("return [...document.querySelectorAll('#asmViewport .as-jtag')].filter(e => e.getClientRects().length).length")


def choose_crank():
    js(f"const it = {A}.doc.instances.find(i => {A}.mates?.length !== 0 && (({A}.doc.mates || []).some(m => m.move === i.id))); {A}.choose(it.id)")
    time.sleep(0.6)


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('a3d.show3d'); localStorage.setItem('auto3d-lang', 'cs')")
    d.get(URL)
    wait("return !!window.__app")
    time.sleep(1)
    open_crank()
    choose_crank()
    n = tags()
    check(n > 0, f"the chosen part's joints show their symbols: {n}")
    btn = d.find_element(By.CSS_SELECTOR, "#asmViewport .snap-filters [data-show=joints]")
    name = btn.text + " " + (btn.get_attribute("title") or "")  # (a narrow view: icons only, the name in its tooltip)
    check("Vazby" in name and "on" in btn.get_attribute("class"), f"the bottom row has 🔗 Vazby, on: {name!r}")
    head = js("return [...document.querySelectorAll('#asmViewport .snap-filters .skf-t')].map(e => e.textContent)")
    check("Zobrazit:" in head, f"its group is “Zobrazit:” next to Přichytit / Najetí: {head}")
    btn.click()
    time.sleep(0.5)
    check(tags() == 0, f"switched off: no joint symbols ({tags()})")
    d.save_screenshot(f"{OUT}/joints_hidden.png")
    d.get(URL)
    wait("return !!window.__app")
    time.sleep(1)
    open_crank()
    choose_crank()
    check(tags() == 0 and "on" not in d.find_element(By.CSS_SELECTOR, "#asmViewport .snap-filters [data-show=joints]").get_attribute("class"),
          "after a reload: still off (remembered)")
    d.find_element(By.CSS_SELECTOR, "#asmViewport .snap-filters [data-show=joints]").click()
    time.sleep(0.5)
    check(tags() > 0, f"switched on again: the symbols are back ({tags()})")
    d.save_screenshot(f"{OUT}/joints_shown.png")
    errs = [x["message"] for x in d.get_log("browser") if x["level"] == "SEVERE"]
    check(not errs, f"no console errors {errs}")
finally:
    d.quit()
print("ALL OK" if not bad else f"FAILED: {bad}")
sys.exit(1 if bad else 0)
