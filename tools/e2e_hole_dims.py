"""A hole's dimensions typed — placing a new one and editing one, in headless Edge with real mouse and keys: a 40 × 40
× 10 block, ◎ Hole, a click at about (10, 12) (its labels on the part not in the way while placing) -> its ↔ and ↕
distances typed into the panel (8, 6) -> OK: the hole's centre at (8, 6) -> ✎ Edit the hole (no placing): its ↔ label
on the part clicked, 20 typed -> moved; its ↕ field typed 15 -> moved; its Ø label clicked, 7 typed -> Ø7 -> OK: the
centre at (20, 15), the volume of a Ø7 hole -> chosen (no tool): its Ø tag typed 4 -> Ø4 -> a hole clicked in the face's
middle (kept in the middle, no number before): its ↔ field in the panel shows 20, typed 12 -> measured from the left
edge, x = 12.

  PYTHONIOENCODING=utf-8 py tools/e2e_hole_dims.py http://127.0.0.1:5199 <out dir>
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
H = "window.__app.agentHandlers"
M = "window.__app.modeler"
CV = "#modelViewport canvas"
fails = []


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(script)


def check(what, ok):
    print(("  ok  " if ok else "  FAIL") + " " + what)
    if not ok:
        fails.append(what)


def settled():
    time.sleep(0.6)
    wait(f"return !{M}.inflight")
    time.sleep(0.4)


def click_at(p, nudge=(0, 0)):
    o = js(f"""const v = {M}.view, V = v.camera.position.constructor, [sx, sy] = v.toScreen(new V(...arguments[0])), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(p))
    ActionChains(d, duration=30).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, CV), o[0] + nudge[0], o[1] + nudge[1]).perform()
    time.sleep(0.4)
    ActionChains(d).click().perform()
    time.sleep(0.6)


def label(css, start):
    """A label on the part (css) whose text starts with `start`."""
    return next((e for e in d.find_elements(By.CSS_SELECTOR, css) if e.is_displayed() and e.text.strip().startswith(start)), None)


def hover_click(el):
    """The mouse onto a label, a moment (the labels are drawn again when the mouse leaves the part), then a click there."""
    ActionChains(d, duration=30).move_to_element(el).perform()
    time.sleep(0.4)
    ActionChains(d).click().perform()
    time.sleep(0.4)


def type_in_editor(value):
    """The size editor (opened by a label): its number replaced by `value`, Enter."""
    wait(f"return !!{M}.dimEdit")
    inp = d.find_element(By.CSS_SELECTOR, "#modelViewport .m-dimedit .m-dimedit-row input")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys(value, Keys.ENTER)
    settled()


def type_field(css, value):
    el = d.find_element(By.CSS_SELECTOR, css)
    el.click()
    el.send_keys(Keys.CONTROL, "a")
    el.send_keys(value)
    time.sleep(0.2)
    settled()


def centres():
    """The hole walls' centres (x, y), from the built part."""
    return sorted([round(c, 3) for c in f["centroid"][:2]] for f in js(f"return {M}.result.body.faces") if f["type"] == "cylinder")


def ok_tool():
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=ok]").click()
    settled()


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('a3d.snap3d')")
    call("new_model", name="Dims")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    settled()
    js(f"{M}.view.setView('top')")
    time.sleep(0.6)

    # ---- a new hole: placed, then its distances typed (a label on the part, a field in the panel)
    js(f"{M}.action('hole')")
    time.sleep(0.4)
    click_at([10, 12, 10], (0, 0))
    settled()
    fr = js(f"return {M}.cmd.feature.from[0]")
    print("placed, from:", {k: v.get("d") for k, v in fr.items()})
    check("placing: its labels on the part stay out of the mouse's way", not d.find_elements(By.CSS_SELECTOR, "#modelViewport .sk-label.hole-dim.edit"))
    type_field("#modelRight [data-hd='0:x']", "8")
    check("↔ typed in the panel: 8 from the left edge", js(f"return {M}.cmd.feature.from[0].x.d") == 8)
    type_field("#modelRight [data-hd='0:y']", "6")
    d.save_screenshot(f"{OUT}/hole_dims_new.png")
    ok_tool()
    c = centres()
    print("the hole at", c)
    check("OK: the hole's centre at (8, 6)", c == [[8, 6]])

    # ---- editing it (no placing): a label on the part, a field, its Ø label
    hole = js(f"return {M}.part.features.find(f => f.type === 'hole').id")
    js(f"{M}.edit(arguments[0])", hole)
    settled()
    check("editing: not placing", js(f"return {M}.cmd.place") is False)
    el = label("#modelViewport .sk-label.hole-dim.edit", "8")
    check("editing: its ↔ label can be clicked", el is not None)
    hover_click(el)
    type_in_editor("20")
    check("editing: ↔ typed 20 -> it moved", js(f"return {M}.cmd.feature.points[0][0]") == 0 and js(f"return {M}.cmd.feature.from[0].x.d") == 20)
    type_field("#modelRight [data-hd='0:y']", "15")
    check("editing: ↕ field typed 15", js(f"return {M}.cmd.feature.from[0].y.d") == 15)
    el = label("#modelViewport .sk-label.hole-dim.hole-size", "Ø")
    check("editing: its Ø label on the part", el is not None and el.text.strip() == "Ø5")
    hover_click(el)
    type_in_editor("7")
    check("editing: Ø typed 7", js(f"return {M}.cmd.feature.d") == 7)
    d.save_screenshot(f"{OUT}/hole_dims_edit.png")
    ok_tool()
    c, v = centres(), js(f"return {M}.result.body.volume")
    print("after editing:", c, round(v, 2))
    check("OK: at (20, 15), Ø7", c == [[20, 15]] and abs(v - (16000 - math.pi * 3.5 ** 2 * 10)) < 0.1)

    # ---- chosen (no tool): its Ø tag typed
    js(f"{M}.selectStep(arguments[0])", hole)
    time.sleep(0.6)
    el = label("#modelViewport .m-dimtag", "Ø")
    check("chosen: its Ø tag on the part", el is not None)
    hover_click(el)
    type_in_editor("4")
    v = js(f"return {M}.result.body.volume")
    check(f"chosen: Ø typed 4 -> Ø4 ({v:.2f})", js(f"return {M}.part.features.find(f => f.id === arguments[0]).d", hole) == 4 and abs(v - (16000 - math.pi * 4 * 10)) < 0.1)
    js(f"{M}.selectStep(null)")

    # ---- a hole in the face's middle: typed, it is measured from the left edge
    js(f"{M}.action('hole')")
    time.sleep(0.4)
    click_at([20, 20, 10], (1, 1))
    settled()
    fr = js(f"return {M}.cmd.feature.from[0]")
    print("in the middle:", fr)
    check("clicked in the middle: kept in the middle", bool((fr.get("x") or {}).get("mid")))
    el = d.find_element(By.CSS_SELECTOR, "#modelRight [data-hd='0:x']")
    check("its ↔ field shows 20", el.get_attribute("value") == "20")
    type_field("#modelRight [data-hd='0:x']", "12")
    fr = js(f"return {M}.cmd.feature.from[0]")
    check("typed 12: measured from the left edge", (fr.get("x") or {}).get("d") == 12 and "edge" in fr["x"] and "mid" not in fr["x"])
    ok_tool()
    c = centres()
    print("the holes at", c)
    check("the second hole at (12, 20)", [12, 20] in c)
finally:
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        fails.append("console errors")
    d.quit()

print("FAILED:" if fails else "ALL OK", fails if fails else "")
sys.exit(1 if fails else 0)
