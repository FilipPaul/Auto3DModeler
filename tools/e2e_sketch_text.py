"""𝐓 Text in a sketch: a new model's sketch -> 𝐓 Text ("Text", 10 mm high, its text field focused) -> typed "AO",
the height 12 -> ✓ Finish sketch, ⬆ Extrude 3: a body 12 high (the letters' holes kept: its volume well under its
box's), ↶ Undo takes the extrude back.

  PYTHONIOENCODING=utf-8 py tools/e2e_sketch_text.py http://127.0.0.1:5199 <out dir>
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
M = "window.__app.modeler"
SK = f"{M}.sk"


def wait(script, t=30):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def tool(t):
    d.find_element(By.CSS_SELECTOR, f".m-cmdbar [data-a={t}], #modelViewport .view-actions [data-a={t}]").click()
    time.sleep(0.25)


def block():
    return js(f"const e = {SK}.f.entities.find((x) => x.t === 'block'); return e && {{text: e.text, w: e.w0 * e.scale, h: e.h0 * e.scale, rings: e.polys.flat().length}}")


try:
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "newModelBtn").click()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.5)
    b = d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=text]")
    print("𝐓 Text in the make group:", "g-make" in b.get_attribute("class"))
    b.click()
    wait(f"return {SK}.f.entities.some((x) => x.t === 'block')")
    time.sleep(0.4)
    print("inserted:", block(), "| text field focused:", js("return document.activeElement?.dataset?.bt === 'text'"))
    inp = d.find_element(By.CSS_SELECTOR, "#modelRight input[data-bt=text]")
    inp.clear()
    inp.send_keys("AO\n")
    wait(f"return {SK}.f.entities.find((x) => x.t === 'block')?.text === 'AO'")
    time.sleep(0.3)
    print("typed AO:", block())
    h = d.find_element(By.CSS_SELECTOR, "#modelRight input[data-bk=h]")
    h.clear()
    h.send_keys("12\n")
    time.sleep(0.4)
    bl = block()
    print("height 12:", bl, "| hint:", js("return [...document.querySelectorAll('#modelRight .hint')].map(e => e.textContent).find(s => /mm/.test(s))"))
    d.save_screenshot(f"{OUT}/sketch_text.png")
    tool("finish")
    wait(f"return {M}.mode === 'part'")
    tool("extrude")
    time.sleep(0.4)
    el = d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=d]")
    el.clear()
    el.send_keys("3\n")
    time.sleep(0.5)
    for x in d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=ok]"):  # (Enter may have done it)
        x.click()
    wait(f"const b = {M}.result?.body; return b && !{M}.building && Math.abs(b.bbox[5] - b.bbox[2] - 3) < 1e-6")  # (not the preview at 10)
    time.sleep(0.5)
    bb = js(f"const b = {M}.result.body.bbox; return [b[3] - b[0], b[4] - b[1], b[5] - b[2]]")
    vol = js(f"return {M}.result.body.volume")
    print("extruded 3: size", [round(v, 2) for v in bb], "| volume", round(vol, 1), "| fill of its box", round(vol / (bb[0] * bb[1] * bb[2]), 2))
    d.save_screenshot(f"{OUT}/sketch_text_3d.png")
    n = js(f"return {M}.part.features.length")
    tool("undo")
    time.sleep(0.6)
    print("undo:", n, "->", js(f"return {M}.part.features.length"))
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
