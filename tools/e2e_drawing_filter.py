"""🔍 Select by filter in the 📐 Drawing workspace, in headless Edge: a drawing with Ø8 circles on two layers, Ø6 ones and
lines -> ＋ Filter three times: Shape is circle, Layer is HOLES, Ø = 8 -> 3 match (outlined) -> Select them -> Ø 10 for all
three (the others stay) -> Ctrl+Z -> a Ø6 circle: ≡ All like this -> 2 -> lines: Length 25 for all -> a filter removed.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_drawing_filter.py http://127.0.0.1:5199 <out dir>
"""
import os
import sys
import time

import ezdxf
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

URL, OUT = sys.argv[1], sys.argv[2]
doc = ezdxf.new("R2010")
doc.header["$INSUNITS"] = 4
for name, col in [("HOLES", 3), ("DRILL", 1), ("EDGE", 7)]:
    doc.layers.add(name, color=col)
msp = doc.modelspace()
for x in (10, 30, 50):
    msp.add_circle((x, 10), 4, dxfattribs={"layer": "HOLES"})  # Ø8
for x in (10, 30):
    msp.add_circle((x, 30), 3, dxfattribs={"layer": "HOLES"})  # Ø6
for x in (70, 90):
    msp.add_circle((x, 10), 4, dxfattribs={"layer": "DRILL"})  # Ø8, another layer
msp.add_line((0, 50), (20, 50), dxfattribs={"layer": "EDGE"})
msp.add_line((30, 50), (40, 60), dxfattribs={"layer": "EDGE"})
DXF = os.path.abspath(os.path.join(OUT, "holes.dxf"))
doc.saveas(DXF)

opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
D = "window.__app.drawing2d"


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def pick(sel, value):
    el = d.find_elements(By.CSS_SELECTOR, sel)[-1]
    js("arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('change', {bubbles: true}))", el, value)
    time.sleep(0.3)


def count():
    return d.find_element(By.CSS_SELECTOR, "#dwgRight .dw-fcount").text


def radii():
    return js(f"return {D}.d.entities.filter(e => e.t === 'circle').map(e => [e.layer, 2 * e.r])")


def add_filter():
    d.find_element(By.CSS_SELECTOR, "#dwgRight [data-a=addFilter]").click()
    time.sleep(0.3)


try:
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "cadInput").send_keys(DXF)
    wait("return window.__app.state.workspace === 'drawing'")
    time.sleep(0.6)

    add_filter()
    pick("#dwgRight [data-fv='0']", "circle")
    print("Shape is circle:", count())
    add_filter()
    print("2nd filter:", [s.get_attribute("value") for s in d.find_elements(By.CSS_SELECTOR, "#dwgRight [data-ff]")])
    pick("#dwgRight [data-fv='1']", "HOLES")
    print("+ Layer is HOLES:", count())
    add_filter()
    print("3rd filter:", [s.get_attribute("value") for s in d.find_elements(By.CSS_SELECTOR, "#dwgRight [data-ff]")])
    box = d.find_elements(By.CSS_SELECTOR, "#dwgRight [data-fv='2']")[0]
    box.send_keys("8")
    time.sleep(0.3)
    print("+ Ø = 8 (typing):", count(), "| outlined", js(f"return {D}.matchSet.size"))
    box.send_keys(Keys.ENTER)
    time.sleep(0.3)
    d.save_screenshot(f"{OUT}/filter1.png")
    d.find_element(By.CSS_SELECTOR, "#dwgRight [data-a=selMatches]").click()
    time.sleep(0.3)
    print("selected:", js(f"return {D}.sel.size"), "|", d.find_element(By.CSS_SELECTOR, "#dwgRight h2").text)
    size = d.find_element(By.CSS_SELECTOR, "#dwgRight [data-k=size]")
    print("their Ø shown:", size.get_attribute("value"), "|", d.find_element(By.CSS_SELECTOR, "#dwgRight .mp-body p.hint").text)
    size.send_keys(Keys.CONTROL, "a")
    size.send_keys("10", Keys.ENTER)
    time.sleep(0.4)
    print("Ø 10 for them:", radii())
    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    time.sleep(0.4)
    print("Ctrl+Z:", radii())

    # ≡ All like this, on a Ø6
    js(f"{D}.sel = new Set([{D}.d.entities.find(e => e.t === 'circle' && e.r === 3).id]); {D}.renderProps(); {D}.draw()")
    time.sleep(0.2)
    d.find_element(By.CSS_SELECTOR, "#dwgRight [data-a=like]").click()
    time.sleep(0.4)
    print("All like this (a Ø6):", js(f"return {D}.sel.size"), "| filters", js(f"return {D}.filters.map(f => f.field + ' ' + f.op + ' ' + f.value)"))

    # lines: their length at once
    js(f"{D}.sel = new Set({D}.d.entities.filter(e => e.t === 'line').map(e => e.id)); {D}.renderProps(); {D}.draw()")
    time.sleep(0.2)
    size = d.find_element(By.CSS_SELECTOR, "#dwgRight [data-k=size]")
    print("two lines, lengths differ -> box:", repr(size.get_attribute("value")), "placeholder", size.get_attribute("placeholder"))
    size.send_keys("25", Keys.ENTER)
    time.sleep(0.4)
    print("length 25:", js(f"return {D}.d.entities.filter(e => e.t === 'line').map(e => [e.a, e.b, +Math.hypot(e.b[0] - e.a[0], e.b[1] - e.a[1]).toFixed(6)])"))
    d.find_elements(By.CSS_SELECTOR, "#dwgRight [data-fx]")[-1].click()
    time.sleep(0.3)
    print("a filter removed:", js(f"return {D}.filters.length"), "|", count())

    # 💧 the eyedropper: a click on a DRILL circle (Ø8) -> the filters are what it is
    js(f"{D}.sel.clear(); {D}.filters = []; {D}.renderProps(); {D}.fit()")
    time.sleep(0.3)
    d.find_element(By.CSS_SELECTOR, "#dwgRight [data-a=dropper]").click()
    time.sleep(0.2)
    print("eyedropper hint:", d.find_element(By.CSS_SELECTOR, "#dwgViewport .m-hint").text)
    s = js(f"return {D}.toScreen([74, 10])")  # on the rim of the circle at (70, 10), r 4
    cv = d.find_element(By.CSS_SELECTOR, "#dwgViewport canvas")
    w, h = js("const r = arguments[0].getBoundingClientRect(); return [r.width, r.height]", cv)
    ActionChains(d, duration=30).move_to_element_with_offset(cv, round(s[0] - w / 2), round(s[1] - h / 2)).perform()
    time.sleep(0.15)
    ActionChains(d).click().perform()
    time.sleep(0.4)
    print("eyedropper filters:", js(f"return {D}.filters.map(f => f.field + ' ' + f.op + ' ' + f.value)"), "|", count())
    d.find_elements(By.CSS_SELECTOR, "#dwgRight [data-fx]")[1].click()  # without the layer: every Ø8 circle
    time.sleep(0.3)
    print("without the layer filter:", count())

    # layers: Ctrl+click, Shift+click
    names = d.find_elements(By.CSS_SELECTOR, "#dwgLeft .dw-lname")
    names[0].click()
    time.sleep(0.2)
    names = d.find_elements(By.CSS_SELECTOR, "#dwgLeft .dw-lname")  # (the list is drawn again after each click)
    ActionChains(d).key_down(Keys.SHIFT).click(names[2]).key_up(Keys.SHIFT).perform()
    time.sleep(0.3)
    print("Shift+click 1st..3rd:", js(f"return [...{D}.layerSel]"), "| bar", d.find_element(By.CSS_SELECTOR, "#dwgLeft .dw-lsel b").text)
    names = d.find_elements(By.CSS_SELECTOR, "#dwgLeft .dw-lname")
    ActionChains(d).key_down(Keys.CONTROL).click(names[1]).key_up(Keys.CONTROL).perform()
    time.sleep(0.3)
    print("Ctrl+click the 2nd off:", js(f"return [...{D}.layerSel]"))
    d.find_element(By.CSS_SELECTOR, "#dwgLeft [data-a=selOff]").click()
    time.sleep(0.3)
    print("Hide them:", js(f"return {D}.d.layers.map(l => l.name + (l.visible === false ? ' (hidden)' : ''))"))
    d.find_element(By.CSS_SELECTOR, "#dwgLeft [data-a=selOn]").click()
    time.sleep(0.3)
    d.find_element(By.CSS_SELECTOR, "#dwgLeft [data-a=selFilter]").click()
    time.sleep(0.3)
    print("As a filter:", js(f"return {D}.filters.map(f => f.field + ' ' + f.op + ' ' + JSON.stringify(f.value))"), "|", count())
    d.find_element(By.CSS_SELECTOR, "#dwgLeft [data-a=selShapes]").click()
    time.sleep(0.3)
    print("their shapes selected:", js(f"return {D}.sel.size"))
    d.save_screenshot(f"{OUT}/filter2.png")
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
