"""Part tabs, in headless Edge: 9 parts with long names -> the tabs in a row of their own, in two rows, each name at
least 5 letters readable -> the tab on screen wider -> a double-click to rename widens it -> a tab dragged before the
first one: the order changes (kept in the project) -> every tab closed, the last one too: "No part open" -> ☰ opens
a part again.

  PYTHONIOENCODING=utf-8 py tools/e2e_tabs.py http://127.0.0.1:5199 <out dir>
"""
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1500,900")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
H = "window.__app.agentHandlers"
P = "window.__app.project"


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def tabs():
    return d.find_elements(By.CSS_SELECTOR, "#partTabs .part-tab")


try:
    d.get(URL)
    time.sleep(2)
    for i in range(9):
        call("new_model", name=f"Otočné rameno dlouhé {i + 1}")
    time.sleep(0.5)
    rows = sorted({round(t.rect["y"]) for t in tabs()})
    print("tabs:", len(tabs()), "| rows:", len(rows), "| under the top bar:", tabs()[0].rect["y"] >= d.find_element(By.CSS_SELECTOR, ".topbar").rect["height"] - 1)
    shown = js("""const c = document.createElement('canvas').getContext('2d'); c.font = getComputedStyle(document.querySelector('#partTabs .pt-name')).font;
      return [...document.querySelectorAll('#partTabs .pt-name')].map(n => n.clientWidth >= c.measureText('Otočn').width - 0.5)""")
    print("5 letters readable on every tab:", all(shown))
    on = d.find_element(By.CSS_SELECTOR, "#partTabs .part-tab.on")
    other = next(t for t in tabs() if "on" not in t.get_attribute("class"))
    print("the one on screen wider:", on.rect["width"] > other.rect["width"], round(on.rect["width"]), ">", round(other.rect["width"]))
    w0 = other.rect["width"]
    js("arguments[0].dispatchEvent(new MouseEvent('dblclick', {bubbles: true}))", other.find_element(By.CSS_SELECTOR, ".pt-name"))
    time.sleep(0.3)
    print("renaming widens it:", "editing" in other.get_attribute("class"), other.rect["width"] >= w0)
    js("document.activeElement.blur()")
    time.sleep(0.3)
    order0 = js(f"return {P}.parts.map(p => p.name)")
    js("""const ts = document.querySelectorAll('#partTabs .part-tab'), src = ts[ts.length - 1], dst = ts[0], dt = new DataTransfer();
      const r = dst.getBoundingClientRect(), at = { bubbles: true, cancelable: true, dataTransfer: dt, clientX: r.left + 3, clientY: r.top + 5 };
      src.dispatchEvent(new DragEvent('dragstart', at)); dst.dispatchEvent(new DragEvent('dragover', at)); dst.dispatchEvent(new DragEvent('drop', at));
      src.dispatchEvent(new DragEvent('dragend', { ...at, clientX: 200, clientY: 60 }));""")
    order1 = js(f"return {P}.parts.map(p => p.name)")
    print("the last tab dragged before the first:", order1[0] == order0[-1], "| the tabs:", tabs()[0].text[:22], "| windows:", len(d.window_handles))
    for _ in range(12):
        x = d.find_elements(By.CSS_SELECTOR, "#partTabs .part-tab .pt-x")
        if not x:
            break
        js("arguments[0].click()", x[0])
        time.sleep(0.3)
    print("all closed:", len(tabs()), "tabs | No part open:", js("return document.body.classList.contains('none-open')"),
          d.find_element(By.CSS_SELECTOR, ".no-part").text[:20])
    d.save_screenshot(f"{OUT}/tabs_none.png")
    d.find_element(By.CSS_SELECTOR, ".pt-all").click()
    time.sleep(0.3)
    d.find_element(By.CSS_SELECTOR, ".part-all .pt-row .pt-open").click()
    time.sleep(1)
    print("☰ opens one again:", len(tabs()), "tab | none-open:", js("return document.body.classList.contains('none-open')"), "| on screen:", js(f"return {P}.current.name"))
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
