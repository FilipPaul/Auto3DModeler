"""𝑥 Project parameters, in headless Edge: the browser's parser agrees with Python's on tests/param_cases.json -> a
plate (40 × 20) whose Extrude distance is typed "L = 40" (L made, the field keeps "L", 𝑥 Parameters appears) -> a bar
(30 × 10 × 5) whose sketch width is typed "L/2" on its size label (shown "L/2 = 20") -> L = 60 in the widget: the bar
on screen and the plate (not on screen, rebuilt through the ⚙ jobs list's path) both follow -> Ctrl+Z: L 40 again,
both back -> a bad expression ("L/") and a circle (t = L / 20, then L = t * 20) refused with the old values kept; a
field with an unknown name marked, its number kept -> the project saved and opened again (reload): the parameters
and expressions kept -> Czech: "𝑥 Parametry" and the messages. Ends ALL OK / FAILED.

  PYTHONIOENCODING=utf-8 py tools/e2e_parameters.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

URL, OUT = sys.argv[1], sys.argv[2]
ROOT = Path(__file__).resolve().parent.parent
CASES = json.loads((ROOT / "tests" / "param_cases.json").read_text(encoding="utf-8"))
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1500,900")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
H = "window.__app.agentHandlers"
M = "window.__app.modeler"
P = "window.__app.project"
W = ".lw-widget[data-w=params-model]"
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


def check(ok, what):
    print("OK  " if ok else "FAIL", what)
    if not ok:
        fails.append(what)


def settled_volume():
    time.sleep(0.5)
    wait(f"return !{M}.inflight && {M}.result?.body")
    time.sleep(0.4)
    return js(f"return {M}.result.body.volume")


def lang(cs):
    if (js("return document.documentElement.lang") == "cs") != cs:
        d.find_element(By.ID, "langBtn").click()
        time.sleep(0.5)


def part_data(name):
    return js(f"const p = {P}.parts.find(q => q.name === arguments[0]); return {P}.dataOf(p)", name)


def toasts():
    return js("return [...document.querySelectorAll('#toasts .toast')].map(e => e.textContent).join(' | ')")


def val(name):
    return js(f"return document.querySelector(`{W} .px-row[data-px='{name}'] .px-expr`)?.value")


def widget_set(name, value):
    inp = d.find_element(By.CSS_SELECTOR, f"{W} .px-row[data-px='{name}'] .px-expr")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys(value, Keys.ENTER)
    time.sleep(0.4)


try:
    d.get(URL)
    time.sleep(2)
    lang(False)

    # ---- the browser's parser: the same answers as Python's
    got = js("""return import('/js/params.js').then(P => {
      const out = {values: [], errors: [], lists: []};
      for (const [text, vals] of arguments[0].values) { try { out.values.push(P.evalText(text, vals)); } catch (e) { out.values.push('ERR ' + e.code); } }
      for (const [text, vals] of arguments[0].errors) { try { P.evalText(text, vals); out.errors.push('none'); } catch (e) { out.errors.push(e.code); } }
      for (const [pairs] of arguments[0].lists) { const r = P.evaluateAll(pairs.map(([name, expr]) => ({name, expr}))); out.lists.push([r.values, Object.keys(r.errors).sort()]); }
      return out; })""", CASES)
    bad = [c[0] for c, v in zip(CASES["values"], got["values"]) if not isinstance(v, (int, float)) or abs(v - c[2]) > 1e-9]
    check(not bad, f"parser values agree with Python ({len(CASES['values'])} cases){' — wrong: ' + str(bad) if bad else ''}")
    bad = [c[0] for c, v in zip(CASES["errors"], got["errors"]) if v != c[2]]
    check(not bad, f"parser errors agree ({len(CASES['errors'])} cases){' — wrong: ' + str(bad) if bad else ''}")
    bad = [c[0] for c, (vals, errs) in zip(CASES["lists"], got["lists"]) if errs != sorted(c[2]) or any(abs(vals[k] - v) > 1e-9 for k, v in c[1].items())]
    check(not bad, f"parameter lists agree ({len(CASES['lists'])} cases)")

    # ---- part A: the Extrude distance typed "L = 40"
    call("new_model", name="Plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    check(not js("return document.querySelector('.lw-widget[data-w=params-model]')?.offsetParent"), "no parameters: the 𝑥 widget is not shown")
    js(f"{M}.startExtrude()")
    num = wait("return document.querySelector('#modelRight input[data-k=d]')")
    time.sleep(0.3)
    num = d.find_element(By.CSS_SELECTOR, "#modelRight input[data-k=d]")
    num.send_keys(Keys.CONTROL, "a")
    num.send_keys("L = 40")
    time.sleep(0.5)
    check(js(f"return {M}.cmd?.feature.d") == 40, "typing “L = 40”: the preview takes 40")
    num.send_keys(Keys.ENTER)
    time.sleep(0.6)
    if js(f"return !!{M}.cmd"):
        js(f"{M}.okCommand()")
    va = settled_volume()
    fa = js(f"return {M}.part.features.find(f => f.type === 'extrude')")
    check(abs(va - 40 * 20 * 40) < 1e-3 and fa.get("expr") == {"d": "L"}, f"the extrude keeps d = L (40): volume {va}, expr {fa.get('expr')}")
    check(js(f"return document.querySelector('{W}')?.offsetParent !== null"), "the 𝑥 Parameters widget appeared with L")
    check(val("L") == "40", "the widget lists L = 40")

    # ---- part B: a sketch's width typed "L/2" on its size label
    call("new_model", name="Bar")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 30, "h": 10}}])
    call("add_feature", type="extrude", d=5)
    vb0 = settled_volume()
    check(abs(vb0 - 1500) < 1e-3, f"the bar 30 × 10 × 5: {vb0}")
    sid = js(f"return {M}.part.features.find(f => f.type === 'sketch').id")
    js(f"{M}.edit(arguments[0])", sid)
    wait("return document.querySelectorAll('.sk-label.edit').length")
    time.sleep(0.6)
    lab = js("return [...document.querySelectorAll('.sk-label.edit .sk-val')].findIndex(e => /(^|\\s)30$/.test(e.textContent.trim()))")
    check(lab >= 0, "the sketch shows its width 30")
    d.find_elements(By.CSS_SELECTOR, ".sk-label.edit .sk-val")[lab].click()
    inp = wait("return document.querySelector('.sk-input')")
    inp = d.find_element(By.CSS_SELECTOR, ".sk-input")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys("L/2", Keys.ENTER)
    time.sleep(1.2)
    shown = js("return [...document.querySelectorAll('.sk-label.edit .sk-val')].map(e => e.textContent)")
    check(any("L/2 = 20" in s for s in shown), f"the size label shows “L/2 = 20”: {shown}")
    js(f"{M}.finishSketch()")
    vb = settled_volume()
    dim = js(f"return {M}.part.features.find(f => f.type === 'sketch').dims.find(x => x.expr)")
    check(abs(vb - 1000) < 1e-3 and dim and dim["expr"] == {"v": "L/2"}, f"the bar is 20 wide: volume {vb}, dim {dim}")

    # ---- L = 60 in the widget: both parts follow
    js("""window.__rb = []; const f0 = window.fetch; window.fetch = (u, o) => { // (the rebuilds asked for, by the part they name)
      if (String(u).includes('/api/model/rebuild')) window.__rb.push(JSON.parse(o.body).what || '(on screen)');
      return f0(u, o); };""")
    widget_set("L", "60")
    vb = settled_volume()
    check(abs(vb - 30 * 10 * 5) < 1e-3, f"L = 60: the bar on screen is 30 wide again: {vb}")
    wait(f"return {P}.parts.find(q => q.name === 'Plate').data.features.find(f => f.type === 'extrude').d === 60", 20)
    check(True, "L = 60: the plate (not on screen) has d = 60")
    rb = js("return window.__rb")
    check("Plate" in rb and "(on screen)" in rb, f"both rebuilt through /api/model/rebuild, the plate by its name (the ⚙ jobs list's): {rb}")
    js(f"{P}.switchTo({P}.parts.find(q => q.name === 'Plate').id)")
    va = settled_volume()
    check(abs(va - 40 * 20 * 60) < 1e-3, f"the plate opened: 40 × 20 × 60 = {va}")
    js(f"{P}.switchTo({P}.parts.find(q => q.name === 'Bar').id)")
    settled_volume()

    # ---- Ctrl+Z: L back to 40, both follow
    d.find_element(By.TAG_NAME, "body").send_keys(Keys.CONTROL, "z")
    time.sleep(0.5)
    vb = settled_volume()
    check(val("L") == "40" and abs(vb - 1000) < 1e-3,
          f"Ctrl+Z: L = 40 again, the bar 20 wide: {vb}")
    wait(f"return {P}.parts.find(q => q.name === 'Plate').data.features.find(f => f.type === 'extrude').d === 40", 20)
    check(True, "Ctrl+Z: the plate back to d = 40")

    # ---- bad expressions: refused, old values kept
    widget_set("L", "L/")
    time.sleep(0.5)
    check(val("L") == "40" and "not finished" in toasts(), f"“L/” refused, L stays 40: {toasts()[:160]}")
    nw = d.find_element(By.CSS_SELECTOR, f"{W} .px-new")
    nw.send_keys("t = L / 20", Keys.ENTER)
    time.sleep(0.6)
    check(js(f"return document.querySelector('{W} .px-row[data-px=t] .px-res')?.textContent") == "= 2", "t = L / 20 added: = 2")
    widget_set("L", "t * 20")
    time.sleep(0.5)
    check(val("L") == "40" and "circle" in toasts(), f"L = t * 20 (a circle) refused: {toasts()[-160:]}")
    js(f"{M}.edit({M}.part.features.find(f => f.type === 'extrude').id)")
    num = wait("return document.querySelector('#modelRight input[data-k=d]')")
    time.sleep(0.3)
    num = d.find_element(By.CSS_SELECTOR, "#modelRight input[data-k=d]")
    num.send_keys(Keys.CONTROL, "a")
    num.send_keys("Q + 1")
    time.sleep(0.4)
    check("px-bad" in num.get_attribute("class") and js(f"return {M}.cmd.feature.d") == 5, f"an unknown name in a field: marked, d stays 5 ({num.get_attribute('title')[:80]})")
    num.send_keys(Keys.CONTROL, "a")
    num.send_keys("t + 3")
    time.sleep(0.5)
    fd = js(f"return [{M}.cmd.feature.d, {M}.cmd.feature.expr]")
    check(fd[0] == 5 and fd[1] == {"d": "t + 3"}, f"“t + 3” in the field: d = 5 kept as t + 3 ({fd})")
    num.send_keys(Keys.ENTER)
    time.sleep(0.4)
    if js(f"return !!{M}.cmd"):
        js(f"{M}.okCommand()")
    settled_volume()
    widget_set("t", "L / 10")
    vb = settled_volume()
    check(abs(vb - 20 * 10 * 7) < 1e-3, f"t = L / 10: the bar is 20 × 10 × (4 + 3): {vb}")

    # ---- saved and opened again
    pid = js("return window.__app.autosave.saveNow().then(() => window.__app.autosave.id)")
    saved = js("return window.__app.project.toJSON().parameters")
    check(saved == [{"name": "L", "expr": "40"}, {"name": "t", "expr": "L / 10"}], f"the project file has its parameters: {saved}")
    d.refresh()
    time.sleep(2)
    js("return window.__app.autosave.open(arguments[0])", pid)
    wait(f"return {P}.parts.length >= 2", 30)
    time.sleep(1)
    got = js("return import('/js/params.js').then(P => P.params.list)")
    check(got == [{"name": "L", "expr": "40"}, {"name": "t", "expr": "L / 10"}], f"reloaded: the parameters are back: {got}")
    plate = part_data("Plate")
    check(plate and plate["features"][-1].get("expr") == {"d": "L"} and plate["features"][-1]["d"] == 40, "reloaded: the plate's d = L (40)")

    # ---- Czech
    lang(True)
    js(f"{P}.switchTo({P}.parts.find(q => q.name === 'Bar').id)")
    time.sleep(1)
    title = js(f"return document.querySelector('{W} .lw-head b')?.textContent")
    check(title == "𝑥 Parametry", f"Czech widget title: {title}")
    widget_set("L", "(1 + 2")
    time.sleep(0.4)
    check("není uzavřená závorka" in toasts(), f"Czech message: {toasts()[-120:]}")
    d.save_screenshot(str(Path(OUT) / "parameters_cs.png"))
    errs = [x["message"] for x in d.get_log("browser") if x["level"] == "SEVERE" and "favicon" not in x["message"]]
    check(not errs, f"no errors in the console {errs[:3]}")
finally:
    d.quit()
print("ALL OK" if not fails else f"FAILED: {fails}")
sys.exit(1 if fails else 0)
