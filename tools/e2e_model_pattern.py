"""⁂ Pattern with REAL mouse input in headless Edge: a 60 x 20 x 5 plate with one Ø4 hole (built through the AI tools) ->
⁂ Pattern: the hole is chosen, "How many" 5, "Apart" 12 -> exact volume; a click on the plate's short (y) edge
turns the row along y (its count and spacing kept — the range is only a suggestion —, the panel warns that copies
run off the plate); ◌ Around on a disc with one
hole: 6 around Z, then a click on a round face (the boss) for its axis; the AI's add_feature pattern; deleting the
hole deletes the pattern too. Prints a check list and ALL OK / FAILED.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_model_pattern.py http://127.0.0.1:5199 <out dir>
"""
import json
import math
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"
H = "window.__app.agentHandlers"
ok = []


def check(name, cond):
    ok.append(bool(cond))
    print(f"  {name}: {'OK' if cond else 'FAIL'}")


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


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#modelViewport canvas")


def off_xyz(p):
    return js(f"""const v = {M}.view, [x, y, z] = arguments[0];
      const [sx, sy] = v.toScreen(new (v.camera.position.constructor)(x, y, z)), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(p))


def click_at(o):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *o).perform()
    time.sleep(0.2)
    ActionChains(d).click().perform()
    time.sleep(0.3)


def btn(sel):
    d.find_element(By.CSS_SELECTOR, sel).click()
    time.sleep(0.3)


def typed(k, value):
    inp = d.find_element(By.CSS_SELECTOR, f"#modelRight [data-k={k}]")
    inp.clear()
    inp.send_keys(str(value))
    settled()


def vol():
    return js(f"return {M}.result?.body?.volume")


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("add_feature", type="hole", face="F2:end", points=[[-24, 0]], d=4)
    settled()
    one = 6000 - math.pi * 4 * 5
    print("plate with one hole:", round(vol(), 3), "| expected", round(one, 3))
    check("the plate with one hole", abs(vol() - one) < 0.01)

    btn("#modelViewport [data-a=pattern]")
    print("panel:", d.find_element(By.CSS_SELECTOR, "#modelRight .mp-body").text.replace("\n", " | "))
    typed("count", 5)
    typed("spacing", 12)
    print("5 holes, 12 apart:", round(vol(), 3), "| expected", round(6000 - 5 * math.pi * 4 * 5, 3))
    check("5 holes, 12 apart", abs(vol() - (6000 - 5 * math.pi * 4 * 5)) < 0.01)
    js(f"{M}.view.setView('iso')")
    time.sleep(0.4)
    d.save_screenshot(f"{OUT}/pat1_row.png")
    # a click on the middle of the short top edge at x = 60 (the plate: x 0..60, y 0..20; the edge runs along y) turns
    # the row; along y the plate is only 20 wide: "How many" and "Apart" stay as typed (their ranges are only a
    # suggestion), the panel says the copies past the plate change nothing. (In the iso view this edge is seen at a slant: the
    # pick once took it as hidden behind the top face and the click did nothing.)
    click_at(off_xyz([60, 10, 5]))
    settled()
    along, y_on = js(f"return {M}.cmd.feature.dir"), js("return !!document.querySelector('#modelRight [data-ax=y].on')")
    print("direction from the edge:", along, "| Y button on:", y_on)
    check("a click on the short edge turns the row along y", along and abs(abs(along[1]) - 1) < 1e-6 and y_on)
    n, sp = js(f"return [{M}.cmd.feature.count, {M}.cmd.feature.spacing]")
    print("along y:", n, "x", sp, "mm apart")
    warn = " ".join(e.text for e in d.find_elements(By.CSS_SELECTOR, "#modelRight .mp-warn"))
    print("  warning:", warn)
    check("along y the count and spacing stay, with a warning that copies run off the plate", n == 5 and sp == 12 and any(w in warn for w in ("reach the part", "changed nothing", "zasáhne", "nic nezm")))
    btn("#modelRight [data-ax=x]")
    settled()
    typed("count", 5)
    typed("spacing", 12)
    btn("#modelViewport .view-actions [data-a=ok]")
    settled()
    print("tree:", js(f"return [...document.querySelectorAll('#modelLeft .mt-item')].map(e => e.innerText.replace(/\\n/g, ' '))"))
    print("volume:", round(vol(), 3), "| ok:", js(f"return {M}.result.ok"))
    check("back along x and OK: 5 holes", abs(vol() - (6000 - 5 * math.pi * 4 * 5)) < 0.01 and js(f"return {M}.result.ok"))

    # delete the hole: the pattern needs it and goes too
    hole = js(f"return {M}.part.features.find(f => f.type === 'hole').id")
    js(f"{M}.remove(arguments[0])", hole)
    wait("return !!document.querySelector('.choose.confirm')")  # (asked in the page: Delete them)
    btn(".choose.confirm .btn.primary")
    settled()
    left = [f["type"] for f in js(f"return {M}.part.features")]
    print("after deleting the hole:", left, round(vol(), 3))
    check("deleting the hole deletes the pattern too", left == ["sketch", "extrude"] and abs(vol() - 6000) < 0.01)

    # around: a disc Ø60 with a boss Ø10 in the middle, one hole at 20 from the centre
    call("new_model", name="Flange")
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 60}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("add_feature", type="sketch", plane={"face": "F2:end"}, shapes=[{"circle": {"x": 0, "y": 0, "d": 10}}])
    call("add_feature", type="extrude", sketch="F3", d=10)
    call("add_feature", type="hole", face="F2:end", points=[[20, 0]], d=6)
    settled()
    base = math.pi * 900 * 5 + math.pi * 25 * 10
    btn("#modelViewport [data-a=pattern]")
    btn("#modelRight [data-kind=circular]")
    settled()
    print("around Z, 6:", round(vol(), 3), "| expected", round(base - 6 * math.pi * 9 * 5, 3))
    check("6 around Z", abs(vol() - (base - 6 * math.pi * 9 * 5)) < 0.01)
    typed("count", 4)
    js(f"{M}.view.setView('iso')")
    time.sleep(0.4)
    # a click on the boss's round side: around its axis (the same Z axis here, so the volume stays)
    click_at(off_xyz([0, -5, 10]))
    settled()
    axis = js(f"return {M}.cmd.feature.axis")
    print("axis from the boss:", axis, "| 4 around:", round(vol(), 3), "| expected", round(base - 4 * math.pi * 9 * 5, 3))
    check("the boss's round face gives the axis (Z), 4 around", isinstance(axis, dict) and abs(abs(axis["d"][2]) - 1) < 1e-6
          and abs(vol() - (base - 4 * math.pi * 9 * 5)) < 0.01)
    d.save_screenshot(f"{OUT}/pat2_around.png")
    btn("#modelViewport .view-actions [data-a=ok]")
    settled()

    # the AI's way
    r = call("add_feature", type="pattern", of=["F5"], kind="circular", axis="z", count=3)
    print("AI pattern of the hole, 3 around:", r[:160])
    check("the AI's pattern, 3 around", '"ok":true' in r)
    r = call("add_feature", type="pattern", of=["F5"], dir="y", count=2, spacing=50)
    print("AI pattern out of the part:", r[:200])
    r = call("add_feature", type="pattern", of=["F1"], count=3)
    print("AI bad of:", r)
    check("the AI's pattern of a sketch is refused", r.startswith("ERROR"))
    print("get_model pattern:", [s for s in json.loads(call("get_model"))["steps"] if s["type"] == "pattern"][:1])
finally:
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    d.quit()
print("ALL OK" if ok and all(ok) and not errs else f"FAILED ({ok.count(False)} of {len(ok)})")
