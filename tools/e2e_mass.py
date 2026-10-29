"""⚖ Mass properties, in headless Edge (Czech): an L-shaped 3D model (a 40 × 10 foot and a 10 × 20 upright, 5 thick)
-> its Part panel: volume 3 cm³, mass 3.7 g (PLA), area 19 cm², CoG (15; 10; 2.5) mm -> ⊕ shows the marker at
the centre (Těžiště), ⊕ again hides it -> brass: the mass follows -> the AI's get_model has mass_g_solid, area_mm2,
cog_mm -> the crank demo: its Assembly panel's CoG with ⊕, the marker where massProps puts it -> ▶ plays: the marker
and the panel's CoG move with the parts (each look: the marker at the parts' weighted centre) -> get_assembly's mass_g
and cog_mm, the same mass as get_bom's.

  PYTHONIOENCODING=utf-8 py tools/e2e_mass.py http://127.0.0.1:5199 <out dir>
"""
import json
import math
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"
A = "window.__app.assembly"
H = "window.__app.agentHandlers"
bad = []


def check(ok, what):
    print(("  ok  " if ok else "  FAIL") + " " + what)
    if not ok:
        bad.append(what)


def wait(script, t=90):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def call(t, **a):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", t, a)


def near(a, b, tol=1e-3):
    return a is not None and b is not None and len(a) == len(b) and all(abs(x - y) <= tol for x, y in zip(a, b))


def marker(view):
    """The ⊕ marker: [visible, its point, its label] of a view."""
    return js(f"const c = {view}.view.cog; return c ? [c.visible && c.element.isConnected, c.position.toArray(), c.element.textContent] : [false, null, '']")


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('a3d.leftDock'); localStorage.setItem('auto3d-lang', 'cs')")
    d.get(URL)
    wait("return !!window.__app")

    # 1. an L: the foot and the upright as two extrudes
    call("new_model", name="L")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 10}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 10, "w": 10, "h": 20}}])
    call("add_feature", type="extrude", sketch="F3", d=5)
    wait(f"return {M}.result?.body && Math.abs({M}.result.body.volume - 3000) < 1e-3")
    time.sleep(0.6)
    b = js(f"const b = {M}.result.body; return {{cog: b.cog, area: b.area, volume: b.volume}}")
    check(near(b["cog"], [15, 10, 2.5], 1e-4) and abs(b["area"] - 1900) < 1e-3, f"the kernel: cog {b['cog']}, area {b['area']} mm², volume {b['volume']} mm³")
    panel = d.find_element(By.CSS_SELECTOR, "#modelRight .mp-facts").text
    print("  panel:", panel.replace("\n", " | "))
    check("Plocha" in panel and "19 cm²" in panel and "Těžiště" in panel and "(15; 10; 2.5) mm" in panel and "3.7 g" in panel and "Objem" in panel,
          "the Part panel (Czech): Objem 3 cm³, Hmotnost 3.7 g, Plocha 19 cm², Těžiště (15; 10; 2.5) mm")
    check(not marker(M)[0], "no marker before ⊕")
    d.find_element(By.CSS_SELECTOR, "#modelRight [data-a=cog]").click()
    time.sleep(0.4)
    vis, at, label = marker(M)
    check(vis and near(at, [15, 10, 2.5], 1e-4) and "Těžiště" in label, f"⊕: the marker at {at}, labelled “{label}”")
    check("on" in d.find_element(By.CSS_SELECTOR, "#modelRight [data-a=cog]").get_attribute("class"), "⊕ shows it is on")
    d.save_screenshot(f"{OUT}/mass_part.png")
    Select(d.find_element(By.CSS_SELECTOR, "#modelRight select[data-k=material]")).select_by_value("brass")
    time.sleep(0.5)
    panel = d.find_element(By.CSS_SELECTOR, "#modelRight .mp-facts").text
    check("25.5 g" in panel and marker(M)[0], "brass: the mass 25.5 g (3 cm³ × 8.5), the marker still on")
    g = json.loads(call("get_model"))
    body = g.get("body") or {}
    check(near(body.get("cog_mm"), [15, 10, 2.5], 1e-3) and abs((body.get("area_mm2") or 0) - 1900) < 1e-3 and abs((body.get("mass_g_solid") or 0) - 25.5) < 1e-6,
          f"get_model: cog_mm {body.get('cog_mm')}, area_mm2 {body.get('area_mm2')}, mass_g_solid {body.get('mass_g_solid')}")
    d.find_element(By.CSS_SELECTOR, "#modelRight [data-a=cog]").click()
    time.sleep(0.3)
    check(not marker(M)[0], "⊕ again: the marker hidden")

    # 2. the crank demo: the assembly's centre of mass, live while it plays
    d.find_element(By.ID, "openBtn").click()
    time.sleep(0.2)
    js("document.getElementById('demoBtn').click()")
    wait("return document.querySelectorAll('.demos [data-demo]').length")
    rows = d.find_elements(By.CSS_SELECTOR, ".demos [data-demo]")
    rows[0].find_element(By.CSS_SELECTOR, "[data-open]").click()
    wait(f"return window.__app.state.workspace === 'assembly' && {A}.doc.instances.length > 1 && {A}.doc.instances.every(i => {A}.bodies[i.part]?.body) && {A}.mech.list.length")
    time.sleep(0.8)
    js(f"{A}.choose(null)")
    wait(f"return {A}.$('.as-cogv')")
    mp = js(f"return {A}.massProps()")
    check(mp["cog"] and mp["mass_g"] > 0 and mp["unknown"] == 0, f"the crank: mass {mp['mass_g']} g, CoG {mp['cog']}")
    txt = js(f"return {A}.$('.as-mass').textContent")
    check("Těžiště" in txt and "mm" in txt, f"the Assembly panel: “{' '.join(txt.split())}”")
    js(f"{A}.$('.as-mass [data-a=cog]').click()")
    time.sleep(0.4)
    vis, at, label = marker(A)
    check(vis and near(at, mp["cog"], 1e-3) and "Těžiště" in label, f"⊕: the marker at {at}")
    a = json.loads(call("get_assembly"))
    bom = json.loads(call("get_bom"))
    check(near(a.get("cog_mm"), mp["cog"], 1e-3) and abs(a.get("mass_g", 0) - mp["mass_g"]) < 0.01 and abs(a.get("mass_g", 0) - bom.get("mass_g", -1)) < 0.05,
          f"get_assembly: mass_g {a.get('mass_g')} (get_bom {bom.get('mass_g')}), cog_mm {a.get('cog_mm')}")
    d.find_element(By.CSS_SELECTOR, "[data-mcplay='0']").click()
    seen, off, texts = [], 0, set()
    end = time.time() + 2.5
    while time.time() < end:
        vis, at, _ = marker(A)
        now = js(f"return {A}.massProps().cog")
        off = max(off, max(abs(x - y) for x, y in zip(at, now)))
        seen.append(at)
        texts.add(js(f"return {A}.$('.as-cogv')?.textContent || ''"))
        time.sleep(0.1)
    d.find_element(By.CSS_SELECTOR, "[data-mcplay='0']").click()
    time.sleep(0.4)
    span = max(math.dist(p, q) for p in seen for q in seen)
    check(span > 0.5 and off < 0.5, f"▶: the marker moved {span:.2f} mm with the parts ({len(seen)} looks), off their centre {off:.3f} mm at most")
    check(len(texts) > 2, f"the panel's CoG followed: {len(texts)} different values")
    d.save_screenshot(f"{OUT}/mass_assembly.png")

    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    check(not errs, f"no console errors {errs[:3]}")
finally:
    d.quit()
print("FAILED:" if bad else "ALL OK", bad if bad else "")
sys.exit(1 if bad else 0)
