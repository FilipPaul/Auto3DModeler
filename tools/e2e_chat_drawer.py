"""The AI chat in every workspace, in headless Edge: a quick part has it as the ✨ AI tab; in a 3D model and in an
assembly the ✨ AI button in the top bar opens the same chat (same conversation) in a drawer; ✕ closes it; back on
a quick part it is a tab again. Model shortcuts do not fire while typing in it.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_chat_drawer.py http://127.0.0.1:5199 <out dir>
"""
import sys
from pathlib import Path
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


def wait(script, t=30):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def where():
    return js("""const el = document.getElementById('tab-ai'), ta = el.querySelector('textarea');
      return {in: el.parentElement.id || el.parentElement.className, chat_visible: !!(ta && ta.offsetParent),
              button_visible: !!document.getElementById('aiBtn').offsetParent, drawer_hidden: document.getElementById('aiDrawer').hidden}""")


try:
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "pdfInput").send_keys(str(Path("initial draft.pdf").resolve()))
    wait("return !!window.__app.state.solution", 90)
    print("quick part:", where())
    d.find_element(By.CSS_SELECTOR, "[data-tab=ai]").click()
    time.sleep(0.3)
    print("quick part, AI tab:", where())
    js("document.querySelector('#tab-ai textarea').value = 'kept draft'")

    d.find_element(By.ID, "newModelBtn").click()
    wait("return document.body.classList.contains('ws-model')")
    time.sleep(0.5)
    print("3D model:", where())
    d.find_element(By.ID, "aiBtn").click()
    time.sleep(0.3)
    print("3D model, ✨ AI:", where(), "| draft kept:", js("return document.querySelector('#tab-ai textarea').value"))
    tools = js("return window.__app.modeler.mode")
    ta = d.find_element(By.CSS_SELECTOR, "#tab-ai textarea")
    ta.send_keys(" rect")  # "r" is the rectangle shortcut in a sketch: must not switch tools
    time.sleep(0.2)
    print("typing does not trigger shortcuts:", js("return window.__app.modeler.sk?.tool"), "| mode", tools)
    d.save_screenshot(f"{OUT}/chat_drawer_model.png")
    d.find_element(By.ID, "aiClose").click()
    time.sleep(0.2)
    print("closed:", where())

    js("document.querySelector('#partTabs .pt-add').click(); document.querySelector('#partTabs [data-new=assembly]').click()")
    wait("return document.body.classList.contains('ws-assembly')")
    time.sleep(0.4)
    d.find_element(By.ID, "aiBtn").click()
    time.sleep(0.3)
    print("assembly, ✨ AI:", where())

    # back to the first (quick) part tab
    d.find_elements(By.CSS_SELECTOR, "#partTabs .part-tab")[0].click()
    time.sleep(0.8)
    print("back on the quick part:", where(), "| ws", js("return window.__app.state.workspace"))
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
