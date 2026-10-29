"""D holes (a shaft's flat on one side) in the Hole panel, in headless Edge: a 40 × 20 × 10 block, ◎ Hole Ø5 on its top
-> Type "D (flat)": Across the flat 4.5 (the Ø5 D-shaft's), no Size / Teardrop, the volume = the circle less its segment,
the flat facing +x -> ⇄ turns it 90° (facing y, the same volume) -> Ø8: the flat follows (7.5) -> Czech labels -> OK: the
step says "Ø8 D7.5" -> the sheet's callout "Ø8 D7.5 THRU" -> the AI's add_feature hole {hole_type: "d_flat", d: 5,
flat: 4.5}: its volume, get_model's flat; edit_feature {d: 6}: the flat 5.5. No console errors.

  PYTHONIOENCODING=utf-8 py tools/e2e_model_hole_dflat.py http://127.0.0.1:5199 <out dir>
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


def typed(k, v):
    el = d.find_element(By.CSS_SELECTOR, f"#modelRight [data-k={k}]")
    el.clear()
    el.send_keys(str(v))
    time.sleep(0.6)


def d_area(dia, flat):
    r = dia / 2
    a = flat - r
    return math.pi * r * r - (r * r * math.acos(a / r) - a * math.sqrt(r * r - a * a))


def flat_normal():
    return js(f"return {M}.result.body.faces.find(f => f.name === 'H1:flat:0' || (f.names || []).some(n => /:flat:0$/.test(n)))?.normal")


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Knob")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": -20, "y": -10, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    wait(f"return !!{M}.result?.body")
    js(f"{M}.action('hole')")
    time.sleep(0.4)
    js(f"{M}.cmd.feature.plane = {{ face: {{ name: 'F2:end' }}, frame: {{ o: [0, 0, 10], x: [1, 0, 0], n: [0, 0, 1] }} }}; {M}.cmd.feature.points = [[-8, 0]]; {M}.renderProps(); {M}.rebuild();")
    check(abs(volume() - round(8000 - math.pi * 6.25 * 10, 2)) < 0.05, "a simple Ø5 hole")
    Select(d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=hole_type]")).select_by_value("d_flat")
    time.sleep(0.6)
    f = js(f"return {M}.cmd.feature")
    fl = d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=flat]")
    check([f.get("hole_type"), f.get("d"), f.get("flat"), fl.get_attribute("value")] == ["d_flat", 5, 4.5, "4.5"], f"D: Ø{f.get('d')} across the flat {f.get('flat')}")
    check(not d.find_elements(By.CSS_SELECTOR, "#modelRight [data-k=standard], #modelRight [data-k=teardrop], #modelRight .m-holesizes"), "no Size, Teardrop or Edit sizes")
    v, want = volume(), round(8000 - 10 * d_area(5, 4.5), 2)
    check(abs(v - want) < 0.05, f"its volume {v} = {want}")
    n = flat_normal() or [0, 0, 0]
    check(abs(abs(n[0]) - 1) < 1e-6, f"the flat faces x: {n}")
    d.find_element(By.CSS_SELECTOR, "#modelRight [data-a=turnflat]").click()
    v = volume()
    n = flat_normal() or [0, 0, 0]
    check(js(f"return {M}.cmd.feature.flat_angle") == 90 and abs(abs(n[1]) - 1) < 1e-6 and abs(v - want) < 0.05, f"⇄ turned 90°: the flat faces y {n}, volume {v}")
    typed("d", 8)
    f = js(f"return {M}.cmd.feature")
    v, want = volume(), round(8000 - 10 * d_area(8, 7.5), 2)
    check(f.get("flat") == 7.5 and d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=flat]").get_attribute("value") == "7.5" and abs(v - want) < 0.05,
          f"Ø8: the flat follows ({f.get('flat')}), volume {v} = {want}")
    d.find_element(By.ID, "langBtn").click()
    time.sleep(0.6)
    panel = d.find_element(By.CSS_SELECTOR, "#modelRight").text
    check("Přes plochu" in panel and "D (s plochou)" in js("return document.querySelector('#modelRight [data-k=hole_type]').textContent")
          and js("return document.querySelector('#modelRight [data-a=turnflat]').title") == "Otočit plochu o 90°", "Czech: D (s plochou), Přes plochu, ⇄'s tip")
    d.save_screenshot(os.path.join(OUT, "hole-dflat-panel.png"))
    d.find_element(By.ID, "langBtn").click()
    time.sleep(0.6)
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=ok]").click()
    time.sleep(1)
    step = js(r"return [...document.querySelectorAll('#modelLeft .mt-item')].map(r => r.textContent.replace(/\s+/g, ' ').trim()).slice(-1)[0]")
    check("Ø8 D7.5" in step, f"the step: {step}")
    print("  sheet_open:", json.loads(call("sheet_open", part="Knob"))["preset"])
    wait("return !!window.__app.sheet.svgEl")
    texts = [x["text"] for x in json.loads(call("get_sheet"))["dims"] if x["kind"] == "dia"]
    check("Ø8 D7.5 THRU" in texts, f"the sheet's callout: {texts}")
    check("Ø8 D7.5 THRU" in js("return document.querySelector('#shViewport svg').textContent"), "the callout drawn on the sheet")
    d.save_screenshot(os.path.join(OUT, "hole-dflat-sheet.png"))
    # the AI: a Ø5 D4.5 hole, then Ø6 (the flat follows: 5.5)
    call("open_part", id="Knob")
    before = json.loads(call("get_model"))["body"]["volume_mm3"]
    r = json.loads(call("add_feature", type="hole", face="F2:end", points=[[10, 0]], hole_type="d_flat", d=5, flat=4.5))
    s = json.loads(call("get_model"))["steps"][-1]
    check(r["ok"] and s.get("hole_type") == "d_flat" and s.get("flat") == 4.5 and abs(r["body"]["volume_mm3"] - (before - 10 * d_area(5, 4.5))) < 0.05,
          f"the AI's D hole: {s.get('what')} | {r['body']['volume_mm3']}")
    r = json.loads(call("edit_feature", id=s["id"], fields={"d": 6}))
    s = json.loads(call("get_model"))["steps"][-1]
    check(r["ok"] and s.get("d") == 6 and s.get("flat") == 5.5, f"the AI's Ø6: flat {s.get('flat')}")
finally:
    errs = [m["message"][:200] for m in d.get_log("browser") if m["level"] == "SEVERE" and "favicon" not in m["message"]]
    check(not errs, f"no console errors {errs[:3]}")
    d.quit()
print("FAILED:" if bad else "ALL OK", *bad, sep="\n  ")
sys.exit(1 if bad else 0)
