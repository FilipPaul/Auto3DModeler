"""⇤⇥ A mechanism's limits, in headless Edge, in Czech, with real clicks: an arm turning on a pin of a fixed base (a post
on the base in its way) -> ⚙ Mechanism shows "bez mezí" under its slider -> ⚠ Check the travel, then ⇤⇥ Meze: limits
around where it is, clear of the post -> min / max typed in the row (limitsOf matches) -> ▶ plays within them -> the
slider to 30°, ⋯ "Nastavit max. sem ⇥": max 30 -> ✕ takes them off ("bez mezí") -> the part chosen: the Suggested
table offers "Meze pohybu…" (the part panel's min field focused, "⇤⇥ Meze" on its button) and "Min. sem" / "Max. sem"
-> autosaved, the page reloaded, the project restored: the limits kept -> no console errors.

  PYTHONIOENCODING=utf-8 py tools/e2e_mech_limits.py http://127.0.0.1:5199 <out dir>
"""
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
A = "window.__app.assembly"
H = "window.__app.agentHandlers"
W = "#leftCol .lw-widget[data-w=mech], #asmViewport .lw-widget[data-w=mech]"
bad = []


def check(ok, what):
    print(("  ok  " if ok else "  FAIL") + " " + what)
    if not ok:
        bad.append(what)


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def call(t, **a):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", t, a)


def widget():
    els = [e for e in d.find_elements(By.CSS_SELECTOR, W) if e.is_displayed()]
    return els[0] if els else None


def lim():
    """The arm's turn limits {min, max} (Assembly.limitsOf) or None."""
    return js(f"const a = {A}, m = a.mech.list[0]; const l = a.limitsOf(a.inst(m.driver.part), m.driver.mo); return l && {{min: l.min, max: l.max}}")


def pos():
    return js(f"const a = {A}, m = a.mech.list[0]; return a.motionPos(m.driver.part, m.driver.mo)")


def limtext():
    return widget().find_element(By.CSS_SELECTOR, ".mc-lim").text


def type_into(el, text):
    el.click()
    time.sleep(0.1)
    ActionChains(d).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).send_keys(text).send_keys(Keys.ENTER).perform()
    time.sleep(0.6)


def rows():
    return {e.text.strip(): e for e in d.find_elements(By.CSS_SELECTOR, ".vs-list [data-sg]") if e.is_displayed()}


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('a3d.leftDock'); localStorage.setItem('auto3d-lang', 'cs')")
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Base")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 200, "h": 200}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="sketch", plane={"face": "F2:end"}, shapes=[{"circle": {"x": 0, "y": 0, "d": 8}}])
    call("add_feature", type="extrude", sketch="F3", d=20)
    call("add_feature", type="sketch", plane={"face": "F2:end"}, shapes=[{"rect": {"x": 0, "y": 45, "w": 10, "h": 10}}])
    call("add_feature", type="extrude", sketch="F5", d=20)
    call("new_model", name="Arm")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 70, "h": 12}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("add_feature", type="hole", face="F2:end", points=[[-28, 0]], d=8)
    call("new_assembly", name="Arm on a pin")
    for p in ("Base", "Arm"):
        call("insert_part", part=p)
    wait(f"return {A}.doc.instances.length === 2 && {A}.doc.instances.every(i => {A}.bodies[i.part]?.body)")
    js(f"{A}.inst('I1').fixed = true")
    hole = js(f"return {A}.bodies[{A}.inst('I2').part].body.faces.find(f => f.type === 'cylinder' && /hole/.test(f.name)).name")
    print(" ", call("snap_faces", type="axis", move={"part": "I2", "face": hole}, onto={"part": "I1", "face": "F4:side:c1"})[:70])
    print(" ", call("snap_faces", type="touch", move={"part": "I2", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})[:70])
    time.sleep(0.6)

    # the widget: the arm's turn, no limits
    w = widget()
    check(w is not None, "⚙ Mechanism shows by itself")
    check(js(f"return {A}.mech.list.length === 1 && {A}.mech.list[0].driver.part === 'I2' && !{A}.mech.list[0].lim"), "one mechanism: the arm's turn, no limits")
    check("bez mezí" in limtext(), f"the row shows “bez mezí”: {limtext()!r}")
    add = d.find_element(By.CSS_SELECTOR, "[data-mclimadd='0']")
    check(add.text == "⇤⇥ Meze" and add.get_attribute("title").startswith("Meze:"), f"⇤⇥ Meze in Czech: {add.text!r}")
    d.save_screenshot(f"{OUT}/mech_limits_none.png")

    # ⚠ Check the travel (in ⋯), then ⇤⇥ Meze: limits around where it is, clear of the post
    d.find_element(By.CSS_SELECTOR, "[data-mcmore='0']").click()
    time.sleep(0.3)
    d.find_element(By.CSS_SELECTOR, "[data-mccheck='0']").click()
    wait(f"return {A}.mech.checked[{A}.mech.list[0].key]", 60)
    chk = js(f"return {A}.mech.checked[{A}.mech.list[0].key]")
    print("  checked:", chk)
    check(len(chk["hits"]) >= 1, f"⚠ the post is in the arm's way: {[(h['from'], h['to']) for h in chk['hits']]}")
    p0 = pos() % 360
    inside = any(h["from"] <= p0 <= h["to"] for h in chk["hits"])
    d.find_element(By.CSS_SELECTOR, "[data-mclimadd='0']").click()
    time.sleep(0.6)
    l0 = lim()
    print("  first limits:", l0, "at", p0)
    hit_in = lambda lo, hi: any(h["from"] <= (lo + k * (hi - lo) / 100) % 360 <= h["to"] for h in chk["hits"] for k in range(101))  # noqa: E731
    check(l0 is not None and (inside or not hit_in(l0["min"], l0["max"])),f"⇤⇥ Meze: limits set {l0}, clear of the post (it was {'in' if inside else 'out of'} the way)")
    check(js("return document.activeElement?.dataset?.mclim") == "0:min", "the min value is focused to type next")

    # min / max typed in the row
    type_into(d.find_element(By.CSS_SELECTOR, "[data-mclim='0:min']"), "-45")
    type_into(d.find_element(By.CSS_SELECTOR, "[data-mclim='0:max']"), "90")
    l1 = lim()
    check(l1 == {"min": -45, "max": 90}, f"typed in the row: limitsOf {l1}")
    vals = [e.get_attribute("value") for e in d.find_elements(By.CSS_SELECTOR, "[data-mclim]")]
    check(vals == ["-45", "90"] and "°" in limtext(), f"the row shows ⇤ {vals} ° ⇥: {limtext()!r}")
    sl = d.find_element(By.CSS_SELECTOR, "[data-mcv='0']")
    check(sl.get_attribute("min") == "-45" and sl.get_attribute("max") == "90", "the slider keeps to them")
    d.save_screenshot(f"{OUT}/mech_limits_typed.png")

    # ▶ for a moment: within them
    d.find_element(By.CSS_SELECTOR, "[data-mcplay='0']").click()
    seen, end = [], time.time() + 2.5
    while time.time() < end:
        seen.append(pos())
        time.sleep(0.05)
    d.find_element(By.CSS_SELECTOR, "[data-mcplay='0']").click()
    time.sleep(0.3)
    check(len(seen) > 10 and min(seen) >= -45.5 and max(seen) <= 90.5 and max(seen) - min(seen) > 30, f"▶ stays within −45 … 90: {min(seen):.1f} … {max(seen):.1f} ({len(seen)} looks)")

    # the slider to 30°, ⋯ Nastavit max. sem ⇥
    js("const s = document.querySelector(arguments[0]); s.value = 30; s.dispatchEvent(new Event('input')); s.dispatchEvent(new Event('change'))", "[data-mcv='0']")
    time.sleep(0.4)
    if not d.find_elements(By.CSS_SELECTOR, "[data-mchere='0:max']"):
        d.find_element(By.CSS_SELECTOR, "[data-mcmore='0']").click()
        time.sleep(0.3)
    b = d.find_element(By.CSS_SELECTOR, "[data-mchere='0:max']")
    check(b.text == "Nastavit max. sem ⇥" and d.find_element(By.CSS_SELECTOR, "[data-mchere='0:min']").text == "⇤ Nastavit min. sem", f"⋯ offers {b.text!r}")
    b.click()
    time.sleep(0.5)
    l2 = lim()
    check(l2 and l2["min"] == -45 and abs(l2["max"] - 30) < 0.01, f"Nastavit max. sem: {l2}")
    d.save_screenshot(f"{OUT}/mech_limits_here.png")

    # ✕ takes them off
    d.find_element(By.CSS_SELECTOR, "[data-mclimoff='0']").click()
    time.sleep(0.5)
    check(lim() is None and "bez mezí" in limtext(), f"✕: no limits again ({limtext()!r})")
    d.find_element(By.CSS_SELECTOR, "[data-mclimadd='0']").click()  # (on again, for the rest)
    time.sleep(0.5)

    # the part chosen: the Suggested table
    js(f"{A}.choose('I2')")
    time.sleep(0.5)
    r = rows()
    print("  suggestions:", list(r))
    check(any("Meze pohybu…" in k for k in r) and any("Min. sem" in k for k in r) and any("Max. sem" in k for k in r), "the table offers ⇤⇥ Meze pohybu…, ⇤ Min. sem, ⇥ Max. sem")
    btn = d.find_element(By.CSS_SELECTOR, "#asmRight [data-dlim='0']")
    check(btn.text == "⇤⇥ Meze" and btn.get_attribute("title").startswith("Jeho meze"), f"the part panel's button: {btn.text!r} — {btn.get_attribute('title')[:30]}")
    check(len(d.find_elements(By.CSS_SELECTOR, "#asmRight [data-dhere='0:min'], #asmRight [data-dhere='0:max']")) == 2, "the part panel: ⇤ sem / sem ⇥")
    next(e for k, e in r.items() if "Meze pohybu…" in k).click()
    time.sleep(0.5)
    check(js("return document.activeElement?.dataset?.dmin") == "0", "Meze pohybu…: the part panel's min field focused")
    js("const s = document.querySelector(arguments[0]); s.value = 10; s.dispatchEvent(new Event('input')); s.dispatchEvent(new Event('change'))", "#asmRight [data-dof='0']")
    time.sleep(0.4)
    p = pos()
    next(e for k, e in rows().items() if "Min. sem" in k).click()
    time.sleep(0.5)
    l3 = lim()
    check(l3 and abs(l3["min"] - p) < 0.01, f"Min. sem (at {p:.2f}): {l3}")
    d.save_screenshot(f"{OUT}/mech_limits_suggest.png")

    # a reload keeps them
    js("return window.__app.autosave.saveNow()")
    time.sleep(0.5)
    d.refresh()
    wait("return !!window.__app")
    wait("return document.querySelector('.restore-bar')", 15)
    d.find_element(By.CSS_SELECTOR, ".restore-bar [data-a=open]").click()
    time.sleep(1)
    call("open_part", id="Arm on a pin")
    wait(f"return {A}.doc.instances.length === 2 && {A}.doc.instances.every(i => {A}.bodies[i.part]?.body) && {A}.mech?.list.length", 30)
    time.sleep(0.5)
    l4 = lim()
    check(l4 == l3, f"after a reload: {l4}")
    check(widget() is not None and [e.get_attribute("value") for e in d.find_elements(By.CSS_SELECTOR, "[data-mclim]")] == [f"{+round(l3['min'], 2):g}", f"{l3['max']:g}"], "the widget shows them again")

    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE" and "favicon" not in e["message"] and "/api/ai/access" not in e["message"]]
    check(not errs, f"no console errors {errs[:3]}")
finally:
    d.quit()

print("FAILED:" if bad else "ALL OK", *bad, sep="\n  ")
sys.exit(1 if bad else 0)
