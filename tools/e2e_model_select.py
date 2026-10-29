"""Choosing a step in the list, in headless Edge: a 60 x 40 x 5 plate with a Ø6 hole -> a click on "Sketch 1" in the
list marks it in 3D (its lines in gold, the faces made from it) and shows its sizes on the finished part -> its 60
changed to 80 there with the slider / number -> the part is 80 wide (the sketch itself was changed, one undo step) ->
a click on "Hole 1" marks the hole and shows Ø6 -> a click on empty space clears it.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_model_select.py http://127.0.0.1:5199 <out dir>
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
    time.sleep(0.5)
    wait(f"return !{M}.inflight")
    time.sleep(0.3)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def row(name):
    js(f"{M}.part.features.forEach(f => {M}.openTo(f.id)); {M}.renderTree()")  # (a sketch is shown under its step, folded)
    return next(r for r in d.find_elements(By.CSS_SELECTOR, "#modelLeft .mt-item") if r.find_element(By.CSS_SELECTOR, ".mt-name").text == name)


def tags():
    return [e.text for e in d.find_elements(By.CSS_SELECTOR, ".m-dimtag") if e.text]


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}], lock=False)
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("add_feature", type="hole", face="F2:end", points=[[10, 5]], d=6)
    settled()
    js(f"{M}.view.setView('iso')")
    time.sleep(0.4)

    row("Sketch 1").click()
    time.sleep(0.6)
    print("Sketch 1 chosen: faces marked", js(f"return {M}.view.selSet?.size"), "| its lines gold:",
          js(f"return {M}.view.outlineGroup.children.some(o => o.material?.color?.getHex?.() === 0xf2cc60)"), "| sizes on the part:", tags())
    d.save_screenshot(f"{OUT}/select1.png")
    tag = next(e for e in d.find_elements(By.CSS_SELECTOR, ".m-dimtag") if e.text.endswith("60"))
    tag.click()
    time.sleep(0.3)
    box = d.find_element(By.CSS_SELECTOR, ".m-dimedit")
    js("const s = arguments[0]; s.value = 70; s.dispatchEvent(new Event('input'))", box.find_element(By.CSS_SELECTOR, "input[type=range]"))
    time.sleep(1.2)
    settled()
    print("slider 70 -> the part", js(f"return {M}.result.body.bbox"))
    inp = box.find_element(By.CSS_SELECTOR, "input[type=number]")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys("80", Keys.ENTER)
    time.sleep(1)
    settled()
    print("80 -> the part", js(f"return {M}.result.body.bbox"), "| the sketch's line", js(f"return {M}.part.features[0].dims.find(d => d.t === 'len')?.v"),
          "| still chosen:", js(f"return {M}.selected"), "| sizes:", tags())

    row("Hole 1").click()
    time.sleep(0.6)
    print("Hole 1 chosen: faces marked", js(f"return {M}.view.selSet?.size"), "| sizes:", tags())

    # empty space: nothing chosen
    spot = js(f"""const v = {M}.view, r = v.renderer.domElement.getBoundingClientRect();
      for (let y = r.height / 2 - 40; y > -r.height / 2 + 60; y -= 30) for (let x = -r.width / 2 + 40; x < r.width / 2 - 40; x += 30)
        if (!v.pick(r.left + r.width / 2 + x, r.top + r.height / 2 + y)) return [Math.round(x), Math.round(y)];
      return null;""")
    ActionChains(d).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, "#modelViewport canvas"), *spot).click().perform()
    time.sleep(0.5)
    print("empty click: chosen", js(f"return {M}.selected"), "| sizes", tags(), "| marked", js(f"return {M}.view.selSet?.size ?? 0"))
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
