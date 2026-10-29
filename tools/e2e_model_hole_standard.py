"""Standard holes in the Hole panel, in headless Edge: a 40 × 20 × 10 block, ◎ Hole Ø5 on its top -> Type ⌴ Counterbore:
Size M5 picked (the nearest to Ø5), Ø5.5 with ⌴ Ø10 ↧ 5.4 from the ISO table, the exact volume, "Edit sizes" folded ->
Size M6: Ø6.6 ⌴ Ø11 ↧ 6.4 -> back to M5, Edit sizes: head depth 4 (the volume follows), 5.4 again -> ⌵ Countersink (M5
kept: Ø11.2, no depth field) -> ⌴ again, OK: the step says "M5 Ø5.5 ⌴Ø10×5.4" -> a second hole: Tapped, M5, 10 deep (the
tap drill Ø4.2 greyed in the fold), Czech labels -> the sheet: "Ø5.5 ⌴ Ø10 ↧ 5.4" and "M5 ↧ 10" -> the AI's edit_feature
hole_type simple: Ø5.5 kept, no head. No console errors.

  PYTHONIOENCODING=utf-8 py tools/e2e_model_hole_standard.py http://127.0.0.1:5199 <out dir>
"""
import json
import math
import os
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

URL, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"
H = "window.__app.agentHandlers"
bad = []


def check(ok, what):
    print(("  ok   " if ok else "  FAIL ") + what)
    if not ok:
        bad.append(what)


def wait(script, t=120):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(script)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def volume():
    time.sleep(0.8)
    wait(f"return !{M}.building && {M}.result?.body")
    time.sleep(0.4)
    return round(js(f"return {M}.result.body.volume"), 2)


def pick(k, v):
    Select(d.find_element(By.CSS_SELECTOR, f"#modelRight [data-k={k}]")).select_by_value(v)
    time.sleep(0.6)


def typed(k, v):
    el = d.find_element(By.CSS_SELECTOR, f"#modelRight [data-k={k}]")
    el.clear()
    el.send_keys(str(v))
    time.sleep(0.6)


def feature():
    return js(f"return {M}.cmd.feature")


def cbore(d_, hd, hdep, t=10):
    return round(8000 - math.pi * ((d_ / 2) ** 2 * t + ((hd / 2) ** 2 - (d_ / 2) ** 2) * hdep), 2)


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Block")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": -20, "y": -10, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    wait(f"return !!{M}.result?.body")
    js(f"{M}.action('hole')")
    time.sleep(0.4)
    js(f"{M}.cmd.feature.plane = {{ face: {{ name: 'F2:end' }}, frame: {{ o: [0, 0, 10], x: [1, 0, 0], n: [0, 0, 1] }} }}; {M}.cmd.feature.points = [[-8, 0]]; {M}.renderProps(); {M}.rebuild();")
    check(abs(volume() - round(8000 - math.pi * 6.25 * 10, 2)) < 0.05, "a simple Ø5 hole")
    types = [o.get_attribute("value") for o in Select(d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=hole_type]")).options]
    check(types == ["", "clearance", "counterbore", "countersink", "tapped", "d_flat"], f"Type: {types}")
    pick("hole_type", "counterbore")
    f = feature()
    check([f.get("standard"), f.get("d"), f.get("head"), f.get("head_d"), f.get("head_depth")] == ["M5", 5.5, "cbore", 10, 5.4], f"⌴ Counterbore: M5 from Ø5 -> {f.get('d')} ⌴ {f.get('head_d')} ↧ {f.get('head_depth')}")
    v = volume()
    check(abs(v - cbore(5.5, 10, 5.4)) < 0.05, f"its volume {v} = {cbore(5.5, 10, 5.4)}")
    check(not d.find_elements(By.CSS_SELECTOR, "#modelRight > * > .field [data-k=d], #modelRight .m-holesizes[open]")
          and not d.find_element(By.CSS_SELECTOR, "#modelRight .m-holesizes [data-k=head_d]").is_displayed(), "the sizes folded under Edit sizes, no Diameter field")
    pick("standard", "M6")
    f = feature()
    check([f.get("d"), f.get("head_d"), f.get("head_depth")] == [6.6, 11, 6.4], f"M6: Ø{f.get('d')} ⌴ Ø{f.get('head_d')} ↧ {f.get('head_depth')}")
    check(abs(volume() - cbore(6.6, 11, 6.4)) < 0.05, "M6's volume")
    pick("standard", "M5")
    d.find_element(By.CSS_SELECTOR, "#modelRight .m-holesizes summary").click()
    time.sleep(0.3)
    typed("head_depth", 4)
    check(abs(volume() - cbore(5.5, 10, 4)) < 0.05 and feature().get("standard") == "M5", "Edit sizes: head depth 4, still M5")
    typed("head_depth", 5.4)
    check(bool(d.find_elements(By.CSS_SELECTOR, "#modelRight .m-holesizes[open]")), "the fold stays open after a change")
    pick("hole_type", "countersink")
    f = feature()
    check([f.get("standard"), f.get("d"), f.get("head"), f.get("head_d")] == ["M5", 5.5, "csk", 11.2] and not d.find_elements(By.CSS_SELECTOR, "#modelRight [data-k=head_depth]"),
          f"⌵ Countersink keeps M5: Ø{f.get('d')} ⌵ Ø{f.get('head_d')}, no depth field")
    h, R, r = 2.85, 5.6, 2.75
    v = volume()
    want = round(8000 - math.pi * r * r * 10 - (math.pi * h / 3 * (R * R + R * r + r * r) - math.pi * r * r * h), 2)
    check(abs(v - want) < 0.1, f"its volume {v} = {want}")
    pick("hole_type", "counterbore")
    check(abs(volume() - cbore(5.5, 10, 5.4)) < 0.05, "⌴ again: M5 counterbore")
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=ok]").click()
    time.sleep(1)
    step = js(r"return [...document.querySelectorAll('#modelLeft .mt-item:not([data-parent])')].map(r => r.textContent.replace(/\s+/g, ' ').trim()).slice(-1)[0]")
    check("M5 Ø5.5 ⌴Ø10×5.4" in step, f"the step: {step}")
    # a tapped hole, 10 deep
    js(f"{M}.action('hole')")
    time.sleep(0.4)
    js(f"{M}.cmd.feature.plane = {{ face: {{ name: 'F2:end' }}, frame: {{ o: [0, 0, 10], x: [1, 0, 0], n: [0, 0, 1] }} }}; {M}.cmd.feature.points = [[10, 0]]; {M}.renderProps(); {M}.rebuild();")
    time.sleep(1)
    pick("hole_type", "tapped")
    check(feature().get("standard") == "M5", "Tapped: the last size (M5)")
    d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=through]").click()
    time.sleep(0.6)
    d.find_element(By.CSS_SELECTOR, "#modelRight .m-holesizes summary").click() if not d.find_elements(By.CSS_SELECTOR, "#modelRight .m-holesizes[open]") else None
    dia = d.find_element(By.CSS_SELECTOR, "#modelRight .m-holesizes [data-k=d]")
    check(dia.get_attribute("value") == "4.2" and not dia.is_enabled(), f"the tap drill Ø{dia.get_attribute('value')} greyed")
    f = feature()
    check([f.get("thread"), f.get("through"), f.get("depth")] == ["M5", False, 10], f"M5 tapped, 10 deep: {f.get('thread')} {f.get('depth')}")
    v = volume()
    check(abs(v - round(cbore(5.5, 10, 5.4) - math.pi * 2.1 ** 2 * 10, 2)) < 0.05, f"the volume {v}")
    d.find_element(By.ID, "langBtn").click()
    time.sleep(0.6)
    panel = d.find_element(By.CSS_SELECTOR, "#modelRight").text
    check(all(w in panel for w in ("Typ", "Velikost", "Upravit rozměry", "Ø vrtáku pro závit"))
          and "Závitová" in js("return document.querySelector('#modelRight [data-k=hole_type]').textContent"), "Czech: Typ, Velikost, Upravit rozměry, Závitová")
    d.find_element(By.ID, "langBtn").click()
    time.sleep(0.6)
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=ok]").click()
    time.sleep(1)
    print("  sheet_open:", json.loads(call("sheet_open", part="Block"))["preset"])
    wait("return !!window.__app.sheet.svgEl")
    texts = [x["text"] for x in json.loads(call("get_sheet"))["dims"] if x["kind"] == "dia"]
    check({"Ø5.5 ⌴ Ø10 ↧ 5.4", "M5 ↧ 10"} <= set(texts), f"the sheet's callouts: {texts}")
    check("Ø5.5 ⌴ Ø10 ↧ 5.4" in js("return document.querySelector('#shViewport svg').textContent"), "the callout drawn on the sheet")
    d.save_screenshot(os.path.join(OUT, "hole-standard-sheet.png"))
    # the AI makes the counterbore simple again: its Ø kept, no head
    call("open_part", id="Block")
    sid = next(x["id"] for x in json.loads(call("get_model"))["steps"] if x.get("hole_type") == "counterbore")
    r = json.loads(call("edit_feature", id=sid, fields={"hole_type": "simple"}))
    s = next(x for x in json.loads(call("get_model"))["steps"] if x["id"] == sid)
    check(r["ok"] and s.get("d") == 5.5 and "head" not in s and "hole_type" not in s, f"the AI's simple again: Ø{s.get('d')} {s.get('head')}")
finally:
    errs = [m["message"][:200] for m in d.get_log("browser") if m["level"] == "SEVERE" and "favicon" not in m["message"]]
    check(not errs, f"no console errors {errs[:3]}")
    d.quit()
print("FAILED:" if bad else "ALL OK", *bad, sep="\n  ")
sys.exit(1 if bad else 0)
