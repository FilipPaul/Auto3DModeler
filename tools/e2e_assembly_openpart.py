"""◆ Open its part from an assembly, in headless Edge: a part chosen in the assembly -> its panel has "◆ Open its part"
-> clicked: that part's tab is on screen (the 3D model workspace) -> back in the assembly the button opens the other one.

  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_openpart.py http://127.0.0.1:5199 <out dir>
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
H = "window.__app.agentHandlers"


def call(t, **a):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", t, a)


try:
    d.get(URL)
    time.sleep(2)
    for name in ("Base", "Lid"):
        call("new_model", name=name)
        call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 30}}])
        call("add_feature", type="extrude", sketch="F1", d=5)
    call("new_assembly", name="Box")
    call("insert_part", part="Base")
    call("insert_part", part="Lid")
    time.sleep(1)
    asm = js("return window.__app.project.active")
    js(f"{A}.choose('I2')")
    time.sleep(0.4)
    b = d.find_element(By.CSS_SELECTOR, "#asmRight [data-a=openPart]")
    print("the button:", b.text)
    b.click()
    time.sleep(1)
    print("opened:", js("return [window.__app.state.workspace, window.__app.project.current.name]"))
    call("open_part", id=asm)
    time.sleep(1)
    js(f"{A}.choose('I1')")
    time.sleep(0.4)
    d.find_element(By.CSS_SELECTOR, "#asmRight [data-a=openPart]").click()
    time.sleep(1)
    print("the other one:", js("return [window.__app.state.workspace, window.__app.project.current.name]"))
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
