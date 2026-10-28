"""Construction lines in a sketch, with REAL mouse input: a 10 × 20 rectangle (x 5 … 15) -> ┄ Construction on, a line at
x 25 drawn (dashed, a helper) -> ┄ off -> ⬚ the rectangle selected, ┄: it becomes construction, ┄ again: back ->
✓ Finish sketch -> ⟳ Revolve: its axis is the construction line by itself -> OK: a ring round x 25 (π (20² − 10²) 20).

  PYTHONIOENCODING=utf-8 py tools/e2e_sketch_construction.py http://127.0.0.1:5199 <out dir>
"""
import math
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
SK = f"{M}.sk"


def wait(script, t=30):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#modelViewport canvas")


def off(uv):
    return js(f"""const m = {M}, v = m.view, f = m.frame(), [u, w] = arguments[0];
      const y = [f.n[1]*f.x[2]-f.n[2]*f.x[1], f.n[2]*f.x[0]-f.n[0]*f.x[2], f.n[0]*f.x[1]-f.n[1]*f.x[0]];
      const p = new (v.camera.position.constructor)(f.o[0] + u*f.x[0] + w*y[0], f.o[1] + u*f.x[1] + w*y[1], f.o[2] + u*f.x[2] + w*y[2]);
      const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(uv))


def click_uv(uv):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *off(uv)).perform()
    time.sleep(0.12)
    ActionChains(d).click().perform()
    time.sleep(0.35)


def tool(t):
    d.find_element(By.CSS_SELECTOR, f".m-cmdbar [data-a={t}], #modelViewport .view-actions [data-a={t}]").click()
    time.sleep(0.25)


def ents():
    return js(f"return {SK}.f.entities.map(e => [e.id, e.t, !!e.construction])")


try:
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "newModelBtn").click()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.6)
    click_uv((5, 0))
    click_uv((15, 20))
    tool("construction")
    print("┄ on:", "on" in d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=construction]").get_attribute("class"))
    tool("line")
    click_uv((25, -5))
    click_uv((25, 30))
    d.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    time.sleep(0.4)
    tool("construction")
    print("a line drawn with ┄ on:", ents()[-1], "| ┄ off:", "on" not in d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=construction]").get_attribute("class"))
    tool("select")
    click_uv((5, 14))  # the rectangle (a side of it)
    print("  ⬚ selected:", js(f"return {SK}.sel"))
    tool("construction")
    print("  ┄ on the selection:", [e for e in ents() if e[2]])
    tool("construction")
    print("  ┄ again: back:", [e for e in ents() if e[2]])
    d.save_screenshot(f"{OUT}/sketch_construction.png")
    tool("finish")
    wait(f"return {M}.mode === 'part'", 10)
    time.sleep(0.8)
    if js(f"return !!{M}.cmd"):
        d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=cancel]").click()
        time.sleep(0.6)
    tool("revolve")
    wait(f"return {M}.cmd?.feature?.type === 'revolve'", 10)
    print("⟳ Revolve: its axis", js(f"return {M}.cmd.feature.axis"), "| the choice:",
          js("return document.querySelector('#modelRight [data-k=axis]')?.selectedOptions[0]?.textContent"))
    wait(f"return {M}.result?.body && !{M}.inflight", 60)
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=ok]").click()
    wait(f"return !{M}.cmd && !{M}.inflight && {M}.result?.body", 60)
    v = js(f"return {M}.result.body.volume")
    print("revolved round it:", round(v, 1), "expected", round(math.pi * (20 ** 2 - 10 ** 2) * 20, 1))
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
