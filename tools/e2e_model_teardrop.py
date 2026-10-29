"""▲ Teardrop holes (printed sideways without support), with REAL mouse input in headless Edge:
1. A 40 x 20 x 20 block, 🖨 Print check on. ◎ Hole clicked on its front face (a sideways hole), Ø6: the print check
   shows the round hole's top as an overhang. Teardrop (print sideways) ticked: the exact volume (the circle and the
   point beyond it: (¾π + 1) r² × 20 less), no overhang left. OK -> the step says ▲ teardrop.
2. ◎ Hole on the top face: Teardrop greyed, its tooltip says why. Cancel.
3. The drawing still says Ø6 (the point is not a size of its own). Ctrl+Z takes the hole away.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_model_teardrop.py http://127.0.0.1:5199 <out dir>
"""
import json
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
failed = []
BLOCK = 40 * 20 * 20
TEAR = BLOCK - (0.75 * math.pi + 1) * 9 * 20  # Ø6 through 20: the circle and the point beyond it


def check(what, ok):
    print(("OK   " if ok else "FAIL ") + what)
    if not ok:
        failed.append(what)


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
    time.sleep(0.4)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#modelViewport canvas")


def off_xyz(p):
    return js(f"""const v = {M}.view, [x, y, z] = arguments[0];
      const [sx, sy] = v.toScreen(new (v.camera.position.constructor)(x, y, z)), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(p))


def click(o):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *o).perform()
    time.sleep(0.25)
    ActionChains(d).click().perform()
    time.sleep(0.4)


def btn(sel):
    d.find_element(By.CSS_SELECTOR, sel).click()
    time.sleep(0.3)


def volume():
    return round(js(f"return {M}.result.body.volume"), 3)


def overhang():  # the 🖨 panel's overhang row, and ModelView.printCheck's own number
    row = d.find_elements(By.CSS_SELECTOR, "#modelViewport .m-printcheck .mpc-row")
    return (row[0].text if row else None), js(f"return {M}.view.printCheck({{ minWall: 1.2 }}).overhang.area")


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Teardrop")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": -20, "y": -10, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=20)
    wait(f"return !!{M}.result?.body")
    settled()
    btn(".m-cmdbar [data-a=printcheck]")
    print("🖨 on the block:", overhang())
    check("the block alone has no overhang", overhang()[1] == 0)

    # 1. a hole into the front face, Ø6
    js(f"{M}.view.setView('front')")
    time.sleep(0.5)
    btn("#modelViewport [data-a=hole]")
    click(off_xyz([0, -10, 10]))  # the front face's centre
    settled()
    f = js(f"return {M}.cmd.feature")
    print("hole on", f["plane"]["face"]["name"], "frame n", f["plane"]["frame"]["n"], "points", f["points"])
    check("the hole is on the front face", abs(f["plane"]["frame"]["n"][1] + 1) < 1e-6)
    dia = d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=d]")
    dia.send_keys(Keys.CONTROL, "a")
    dia.send_keys("6")
    settled()
    v_round = volume()
    print("round Ø6:", v_round, "| expected", round(BLOCK - math.pi * 9 * 20, 3))
    check("the round hole's volume", abs(v_round - (BLOCK - math.pi * 9 * 20)) < 1e-3)
    oh = overhang()
    print("🖨 the round hole:", oh)
    check("the round hole's top hangs over", oh[1] > 50)
    tear = d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=teardrop]")
    check("Teardrop is offered on a sideways hole", tear.is_enabled() and not tear.is_selected())
    d.find_element(By.XPATH, "//*[@id='modelRight']//label[input[@data-k='teardrop']]").click()  # the label, as a user does
    settled()
    v = volume()
    print("▲ teardrop:", v, "| expected", round(TEAR, 3), "| feature", js(f"return {M}.cmd.feature.teardrop"))
    check("the teardrop's exact volume", abs(v - TEAR) < 1e-3)
    oh = overhang()
    print("🖨 the teardrop:", oh)
    check("no overhang at the hole's top", oh[1] == 0 and "—" in (oh[0] or ""))
    names = js(f"return {M}.result.body.faces.flatMap(f => f.names || [f.name]).filter(n => n && n.startsWith('F3:'))")
    print("its faces:", sorted(set(names)))
    check("faces named hole / tear", {"F3:hole:0", "F3:tear:0"} <= set(names))
    js(f"{M}.view.setView('iso')")
    time.sleep(0.4)
    d.find_element(By.CSS_SELECTOR, "#modelViewport").screenshot(f"{OUT}/teardrop1.png")
    btn("#modelViewport .view-actions [data-a=ok]")
    settled()
    step = js(r"return [...document.querySelectorAll('#modelLeft .mt-item:not([data-parent])')].map(r => r.textContent.replace(/\s+/g, ' ').trim()).slice(-1)[0]")
    print("the step:", step)
    check("the step says teardrop", "teardrop" in step)

    # 2. a hole on the top face: Teardrop greyed, the tooltip says why
    js(f"{M}.view.setView('iso')")
    time.sleep(0.5)
    btn("#modelViewport [data-a=hole]")
    click(off_xyz([10, 0, 20]))
    settled()
    tear = d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=teardrop]")
    tip = d.find_element(By.XPATH, "//*[@id='modelRight']//label[input[@data-k='teardrop']]").get_attribute("title")
    print("on the top:", "enabled" if tear.is_enabled() else "greyed", "|", tip)
    check("Teardrop greyed on a hole going down", not tear.is_enabled() and "sideways" in tip)
    btn("#modelViewport .view-actions [data-a=cancel]")
    settled()

    # 3. the drawing: still Ø6; Ctrl+Z takes the hole away
    sizes = None
    if not call("sheet_open", part="Teardrop").startswith("ERROR"):
        wait("return !!window.__app.sheet.svgEl")
        sizes = sorted({x["text"] for x in json.loads(call("get_sheet"))["dims"] if x["kind"] in ("dia", "rad")})
        print("the sheet's hole sizes:", sizes)
        call("open_part", id="Teardrop")
        settled()
    check("the drawing says Ø6 (no R for the teardrop)", sizes is not None and any("Ø6" in s for s in sizes) and not any(s.startswith("R") for s in sizes))
    ActionChains(d).move_to_element(canvas()).perform()
    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    settled()
    print("Ctrl+Z:", volume())
    check("undo takes the teardrop hole away", abs(volume() - BLOCK) < 1e-3)
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
print("FAILED:" if failed else "ALL OK", failed if failed else "")
sys.exit(1 if failed else 0)
