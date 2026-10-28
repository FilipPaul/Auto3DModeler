"""💥 Explode only the chosen parts, in headless Edge: a base, a lid 5 mm above it and a second lid -> Explode 0.8: all
three move (💥 shown on every row) -> 💥 off on the base: it stays, the lids move away from it (the lid on top goes
up) -> Ctrl+click 💥 on the lid: only the lid moves -> undo -> Ctrl+click on the only one again: all move -> the choice is
saved with the assembly.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_explode.py http://127.0.0.1:5199 <out dir>
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
A = "window.__app.assembly"
H = "window.__app.agentHandlers"


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def moves():
    """Each placed part: how far it moves when exploded, and the direction's z (rounded)."""
    return js("""return Object.fromEntries(Object.entries(window.__ex).map(([k, v]) => [k, v ? [Math.round(Math.hypot(...v)), Math.round(v[2])] : 0]))""")


def boom(inst, ctrl=False):
    # rows follow doc.instances; not by the row's text — a fixed part reads "I1 📌"
    row = d.find_elements(By.CSS_SELECTOR, "#asmLeft .as-list .mt-item")[js(f"return {A}.doc.instances.findIndex(i => i.id === arguments[0])", inst)]
    b = row.find_element(By.CSS_SELECTOR, "[data-a=boom]")
    if ctrl:
        ActionChains(d).key_down(Keys.CONTROL).click(b).key_up(Keys.CONTROL).perform()
    else:
        b.click()
    time.sleep(0.4)


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Base")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 80, "h": 60}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("new_model", name="Lid")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 80, "h": 60}}])
    call("add_feature", type="extrude", sketch="F1", d=4)
    call("new_assembly", name="Box")
    call("insert_part", part="Base")
    call("insert_part", part="Lid")
    call("insert_part", part="Lid")
    call("snap_faces", type="gap", gap=5, move={"part": "I2", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    js(f"""const v = {A}.view, o = v.setBodies.bind(v);
      v.setBodies = (items) => {{ window.__ex = Object.fromEntries(items.map((i) => [i.id, i.explode])); return o(items); }};
      {A}.sel = null; {A}.render(); {A}.view.setView('iso')""")
    js("const r = document.querySelector('#asmViewport .as-explode input'); r.value = 0.8; r.dispatchEvent(new Event('input'))")
    time.sleep(0.4)
    print("Explode 0.8, all move:", moves(), "| 💥 shown:", js("return [...document.querySelectorAll('#asmLeft .as-boom')].filter(b => b.offsetParent).length"))
    boom("I1")
    print("💥 off on the base:", moves(), "| base row greyed:", js("return document.querySelectorAll('#asmLeft .as-boom.off').length"))
    d.save_screenshot(f"{OUT}/explode_some.png")
    boom("I2", ctrl=True)
    print("Ctrl+click on the lid — only it moves:", moves(), "| stay:", js(f"return {A}.doc.instances.map(i => [i.id, !!i.stay])"))
    js(f"{A}.history.go(-1)")
    time.sleep(0.4)
    print("undo:", js(f"return {A}.doc.instances.map(i => [i.id, !!i.stay])"))
    boom("I2", ctrl=True)
    boom("I2", ctrl=True)
    print("Ctrl+click on the only one again — all move:", moves())
    boom("I3")
    print("saved with the assembly:", js(f"return {A}.payload().instances.map(i => [i.id, !!i.stay])"))
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
