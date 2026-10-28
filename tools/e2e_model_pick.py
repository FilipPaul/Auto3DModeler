"""Pointing at and clicking the part, with REAL mouse input in headless Edge: a 60 x 40 x 5 plate with a Ø6 hole ->
the mouse over the plate lights up its whole step and names it -> a click on the top face: the tools for that face
pop up, and the step's sizes show on the part (60, 40, ↕ 5) -> click "60": a number and a slider; sliding previews,
typing 80 + Enter keeps it (exact volume) -> the hole's Ø edited the same way -> "◎ Hole here" from the pop-up starts
a hole where it was clicked.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_model_pick.py http://127.0.0.1:5199 <out dir>
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
    time.sleep(0.4)
    wait(f"return !{M}.inflight")
    time.sleep(0.3)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#modelViewport canvas")


def off_xyz(p):
    return js(f"""const v = {M}.view, [x, y, z] = arguments[0];
      const [sx, sy] = v.toScreen(new (v.camera.position.constructor)(x, y, z)), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(p))


def move(p):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *off_xyz(p)).perform()
    time.sleep(0.3)


def click(p):
    move(p)
    ActionChains(d).click().perform()
    time.sleep(0.5)


def rclick(p):
    """A right click there (the face menu)."""
    move(p)
    ActionChains(d).context_click().perform()
    time.sleep(0.5)


def tags():
    return [e.text for e in d.find_elements(By.CSS_SELECTOR, ".m-dimtag")]


def tag(text):
    return next(e for e in d.find_elements(By.CSS_SELECTOR, ".m-dimtag") if e.text.replace("🔒 ", "") == text)


def vol():
    return js(f"return {M}.result.body.volume")


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}], lock=False)
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("add_feature", type="hole", face="F2:end", points=[[10, 5]], d=6)
    settled()
    js(f"{M}.view.setView('iso')")
    time.sleep(0.5)

    move([20, 20, 5])
    print("hover: faces lit", js(f"return {M}.view.hoverSet?.size"), "| tip:", js("return document.querySelector('.m-tip')?.textContent"))
    click([20, 20, 5])
    print("a left click: its step chosen, no menu:", js(f"return {M}.selected"), not d.find_elements(By.CSS_SELECTOR, ".m-fmenu"))
    sg = d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest")
    print("  the suggestions table:", [sg[0].find_element(By.CSS_SELECTOR, ".vs-head b").text] + [' '.join(b.text.split()) for b in sg[0].find_elements(By.CSS_SELECTOR, ".vs-list button")][:4] if sg else None)
    head = d.find_element(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-head")
    x0 = head.rect["x"]
    ActionChains(d, duration=40).move_to_element(head).click_and_hold().move_by_offset(160, -120).release().perform()
    time.sleep(0.3)
    print("  dragged by its header:", round(d.find_element(By.CSS_SELECTOR, "#modelViewport .view-suggest").rect["x"] - x0), "px | remembered:", bool(js("return localStorage.getItem('a3d.suggestAt')")))
    js("localStorage.removeItem('a3d.suggestAt'); document.querySelector('#modelViewport .view-suggest')?.remove()")
    rclick([20, 20, 5])
    print("pop-up (right click):", [b.text for b in d.find_elements(By.CSS_SELECTOR, ".m-fmenu button")])
    print("sizes on the part:", tags())
    d.save_screenshot(f"{OUT}/pick1.png")

    tag("60").click()
    time.sleep(0.4)
    box = d.find_element(By.CSS_SELECTOR, ".m-dimedit")
    slider = box.find_element(By.CSS_SELECTOR, "input[type=range]")
    js("arguments[0].value = 70; arguments[0].dispatchEvent(new Event('input'))", slider)
    time.sleep(1.5)
    settled()
    print("slider at 70 -> preview size:", js(f"return {M}.result.body.bbox"))
    inp = box.find_element(By.CSS_SELECTOR, "input[type=number]")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys("80", Keys.ENTER)
    time.sleep(1.2)
    settled()
    print("80 typed:", js(f"return {M}.result.body.bbox"), "| volume", round(vol(), 3), "| expected", round(80 * 40 * 5 - math.pi * 9 * 5, 3),
          "| undo steps", js(f"return {M}.history.canUndo()"))
    print("sizes now:", tags())

    # the hole's diameter
    js(f"{M}.closeCtx()")
    click([40, 25 + 3, 2.5])  # the hole's back wall (Ø6 at (40, 25): 10 right of where the face's centre was)
    print("hole sizes:", tags())
    tag("Ø6").click()
    time.sleep(0.3)
    inp = d.find_element(By.CSS_SELECTOR, ".m-dimedit input[type=number]")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys("8", Keys.ENTER)
    time.sleep(1)
    settled()
    print("Ø8:", round(vol(), 3), "| expected", round(80 * 40 * 5 - math.pi * 16 * 5, 3))

    # "◎ Hole here" from the pop-up
    js(f"{M}.closeCtx()")
    rclick([15, 10, 5])
    next(b for b in d.find_elements(By.CSS_SELECTOR, ".m-fmenu button") if b.text.startswith("◎")).click()
    time.sleep(0.6)
    settled()
    f = js(f"return {M}.cmd?.feature")
    print("hole here:", f and f["type"], f and f["points"], "| sizes hidden during the command:", tags() == [])
    d.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
