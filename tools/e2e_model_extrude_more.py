"""⬆ Extrude "Up to next" and "＋ Other side", with REAL mouse / keyboard input in headless Edge:
1. Two plates 40 × 40 × 10 with a 10 mm gap (a wall joins them); a circle Ø10 on the lower plate's top: ⬆ Extrude,
   Up to next -> the boss fills the gap up to the upper plate (+ π · 25 · 10), the tree says "up to next"; ⇅ flip
   -> nothing that way: the panel says so; Ctrl+Z after OK takes the boss away, Ctrl+Y brings it back.
2. A block 40 × 20: ⬆ Extrude 10, tick ＋ Other side, type 5, Enter -> 40 × 20 × 15 (z -5 … 10); ticking Both
   sides unticks it; Ctrl+Z.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_model_extrude_more.py http://127.0.0.1:5199 <out dir>
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
fails = []


def wait(script, t=30):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def settled():
    time.sleep(0.3)
    wait(f"return !{M}.inflight")
    time.sleep(0.3)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def btn(sel):
    d.find_element(By.CSS_SELECTOR, sel).click()
    time.sleep(0.3)


def vol():
    return js(f"return {M}.result?.body?.volume ?? 0")


def check(what, ok, got=""):
    print(f"{'OK ' if ok else 'FAIL'} {what} {got}")
    if not ok:
        fails.append(what)


def keys(*k):
    a = ActionChains(d).key_down(Keys.CONTROL)
    for x in k:
        a = a.send_keys(x)
    a.key_up(Keys.CONTROL).perform()


try:
    d.get(URL)
    wait("return !!window.__app")

    # 1. up to next: a boss from the lower plate's top up to the upper plate
    call("new_model", name="Shelf")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="sketch", plane={"datum": "XY", "offset": 10}, shapes=[{"rect": {"x": 0, "y": 0, "w": 5, "h": 40}}])
    call("add_feature", type="extrude", sketch="F3", d=10)
    call("add_feature", type="sketch", plane={"datum": "XY", "offset": 20}, shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 40}}])
    call("add_feature", type="extrude", sketch="F5", d=10)
    call("add_feature", type="sketch", plane={"datum": "XY", "offset": 10}, shapes=[{"circle": {"x": 20, "y": 20, "d": 10}}])
    settled()
    v0 = vol()
    check("two plates and a wall", abs(v0 - 34000) < 1e-6, v0)
    btn("#modelViewport [data-a=extrude]")
    settled()
    seg = [b.text for b in d.find_elements(By.CSS_SELECTOR, "#modelRight [data-upto]")]
    check("extent choices", seg == ["Distance", "Up to a face", "Up to next"], seg)
    btn("#modelRight [data-upto='next']")
    settled()
    exp = 34000 + math.pi * 25 * 10
    check("up to next: the preview fills the gap", abs(vol() - exp) < 1e-3, f"{vol():.4f} expected {exp:.4f}")
    print("panel:", d.find_element(By.CSS_SELECTOR, "#modelRight .mp-count").text)
    d.save_screenshot(f"{OUT}/x1_upto_next.png")
    btn("#modelRight [data-k=flip]")
    settled()
    bad = d.find_elements(By.CSS_SELECTOR, "#modelRight .mp-bad")
    check("flipped: nothing that way, said", bool(bad) and "Up to next" in bad[0].text, bad[0].text if bad else None)
    btn("#modelRight [data-k=flip]")
    settled()
    btn("#modelViewport .view-actions [data-a=ok]")
    settled()
    check("OK: the boss stays", abs(vol() - exp) < 1e-3, f"{vol():.4f}")
    what = js(f"return {M}.whatText({M}.part.features.at(-1))")
    check("the tree says up to next", what == "up to next", what)
    went = js(f"return {M}.status({M}.part.features.at(-1).id)?.went")
    check("went +z 10 … 20", went == {"along": "+z", "range": [10, 20]}, went)
    # the upper plate 5 higher (its sketch 25, the wall 15): the boss follows
    call("edit_feature", id="F5", fields={"plane": {"datum": "XY", "offset": 25}})
    call("edit_feature", id="F4", fields={"d": 15})
    settled()
    exp2 = 34000 + 1000 + math.pi * 25 * 15
    check("the gap 15: the boss 15 tall", abs(vol() - exp2) < 1e-3, f"{vol():.4f} expected {exp2:.4f}")
    keys("z")
    settled()
    keys("z")
    settled()
    keys("z")
    settled()
    check("Ctrl+Z ×3: no boss", abs(vol() - 34000) < 1e-6, f"{vol():.4f}")
    keys("y")
    settled()
    check("Ctrl+Y: the boss again", abs(vol() - exp) < 1e-3, f"{vol():.4f}")

    # 2. the other side: a block 10 up + 5 down
    call("new_model", name="Block")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    settled()
    btn("#modelViewport [data-a=extrude]")
    settled()
    btn("#modelRight [data-k=other]")
    settled()
    inp = d.find_element(By.CSS_SELECTOR, "#modelRight input[data-k=d2]")
    check("Other side: its distance shown and focused", inp == d.switch_to.active_element, inp.get_attribute("value"))
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys("5")
    settled()
    check("preview 40 × 20 × 15", abs(vol() - 12000) < 1e-6, vol())
    sliders = len(d.find_elements(By.CSS_SELECTOR, "#modelRight .mp-slider"))
    check("a slider under each distance", sliders >= 2, sliders)
    btn("#modelRight [data-k=symmetric]")
    settled()
    check("Both sides unticks Other side", not d.find_elements(By.CSS_SELECTOR, "#modelRight input[data-k=d2]") and abs(vol() - 8000) < 1e-6, vol())
    btn("#modelRight [data-k=other]")
    settled()
    check("Other side unticks Both sides", not d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=symmetric]").is_selected())
    inp = d.find_element(By.CSS_SELECTOR, "#modelRight input[data-k=d2]")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys("5")
    settled()
    d.save_screenshot(f"{OUT}/x2_other_side.png")
    inp.send_keys(Keys.ENTER)
    settled()
    bb = js(f"return {M}.result.body.bbox")
    check("Enter = OK: 12000, z -5 … 10", abs(vol() - 12000) < 1e-6 and bb[2] == -5 and bb[5] == 10, (vol(), bb))
    what = js(f"return {M}.whatText({M}.part.features.at(-1))")
    check("the tree says the other side", what == "10 mm · other side 5 mm", what)
    went = js(f"return {M}.status({M}.part.features.at(-1).id)?.went")
    check("went has both ranges", went == {"along": "+z", "range": [0, 10], "other_side": [-5, 0]}, went)
    keys("z")
    settled()
    check("Ctrl+Z: no block", vol() == 0, vol())
finally:
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    print("FAILED:" if fails or errs else "ALL OK", fails)
    d.quit()
