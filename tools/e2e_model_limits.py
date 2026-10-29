"""Value ranges in the 3D tools, in headless Edge: a 40 x 20 x 10 box -> Fillet on a top edge: its slider runs 0.01 –
9.99 (what OpenCASCADE can build there; the range shows under it), typing 15 is held at 9.99 (a notice) and the step
builds (no "does not fit" warning) -> Shell next to that rounding: no wall works, and the panel says why -> Hole (blind): depth up to the box's 10 -> Pattern:
count up to what still reaches the part -> the R label on the part (3D size editor): the same range.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_model_limits.py http://127.0.0.1:5199 <out dir>
"""
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"
H = "window.__app.agentHandlers"


def wait(script, t=30):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def settled():
    time.sleep(0.6)
    wait(f"return !{M}.inflight")
    time.sleep(0.6)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def ranges():
    return [e.text for e in d.find_elements(By.CSS_SELECTOR, "#modelRight .mp-range")]


def slider_range(k):
    return js(f"""const n = document.querySelector('#modelRight input[data-k="{k}"]:not([type=checkbox])'), s = n.closest('.field, label, .mp-hd').nextElementSibling;
      return [n.min, n.max, s.min, s.max]""")


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Limits")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="fillet", edges=[{"a": "F2:end", "b": "F2:side:l1", "fp": [20, 0, 10]}], r=2)
    settled()

    js(f"{M}.edit('F3')")
    settled()
    print("fillet R range:", ranges(), "| number / slider", slider_range("r"))
    inp = d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=r]")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys("15")
    time.sleep(0.3)
    print("typed 15 ->", inp.get_attribute("value"), "|", js("return [...document.querySelectorAll('.toast')].map(t => t.textContent).slice(-1)[0]"))
    settled()
    st = js(f"return {M}.result.features.find(s => s.id === 'F3')")
    print("builds at the most:", st["ok"], st["issues"], "| R", js(f"return {M}.cmd.feature.r"))
    d.save_screenshot(f"{OUT}/limits1.png")
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=cancel]").click()
    settled()

    js(f"{M}.startShell()")
    settled()
    print("shell, no open face yet:", ranges())
    js(f"{M}.cmd.feature.faces.push({{name: 'F2:end', fp: [20, 10, 10]}}); {M}.renderProps(); {M}.rebuild()")  # the top: open
    settled()
    print("shell wall range:", ranges(), "| why:", [e.text for e in d.find_elements(By.CSS_SELECTOR, "#modelRight .mp-bad")])
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=cancel]").click()
    settled()

    call("add_feature", type="hole", face="F2:end", points=[[-10, 0]], d=4, through=False, depth=3)
    settled()
    holes = [s["id"] for s in js(f"return {M}.part.features") if s["type"] == "hole"]
    js(f"{M}.edit(arguments[0])", holes[-1])
    settled()
    print("hole ranges (Ø, depth):", ranges())
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=cancel]").click()
    settled()

    js(f"{M}.startPattern()")
    settled()
    print("pattern ranges (count, spacing):", ranges())
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=cancel]").click()
    settled()

    # the size on the part: the fillet's R label
    js(f"{M}.selectStep('F3')")
    time.sleep(0.6)
    tag = next(e for e in d.find_elements(By.CSS_SELECTOR, ".m-dimtag") if e.text.startswith("R"))
    tag.click()
    time.sleep(1.2)
    print("3D editor range:", [e.text for e in d.find_elements(By.CSS_SELECTOR, ".m-dimedit .mp-range")],
          "| slider max", js("return document.querySelector('.m-dimedit input[type=range]').max"))
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
