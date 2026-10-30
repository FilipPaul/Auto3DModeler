"""A size's editor on the part (a label clicked): ☑ 🔒 Zamčeno and ☑ Zobrazit under its number, in headless Edge,
Czech, with real clicks: a 40 × 16 block, its extrude chosen -> the "🔒 16" label clicked -> Zamčeno unticked -> OK:
the label has no 🔒, the sketch's 16 is no longer locked -> Ctrl+Z: locked again -> Zobrazit unticked -> OK: the label
is gone (saved in the part's hidden_dims) -> the left panel's Rozměry: Vše brings it back -> a hole's ↔ distance
locked (typed): Zamčeno unticked -> OK: f.lock gone, no 🔒 -> ticked again, right-click in the view = OK: locked
again. No console errors.

  PYTHONIOENCODING=utf-8 py tools/e2e_dim_popup.py http://127.0.0.1:5199 <out dir>
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
H = "window.__app.agentHandlers"
M = "window.__app.modeler"
CV = "#modelViewport canvas"
POP = "#modelViewport .m-dimedit"
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
    time.sleep(0.5)
    wait(f"return !{M}.inflight")
    time.sleep(0.3)


def labels():
    return [e.text.strip() for e in d.find_elements(By.CSS_SELECTOR, "#modelViewport .m-dimtag") if e.is_displayed()]


def label(test):
    """A size label on the part whose text passes test."""
    return next((e for e in d.find_elements(By.CSS_SELECTOR, "#modelViewport .m-dimtag") if e.is_displayed() and test(e.text.strip())), None)


def hover_click(el):
    ActionChains(d, duration=30).move_to_element(el).perform()
    time.sleep(0.4)
    ActionChains(d).click().perform()
    time.sleep(0.4)


def pop(css):
    return d.find_element(By.CSS_SELECTOR, f"{POP} {css}")


def choose(step):
    js(f"{M}.selectStep(arguments[0])", step)
    time.sleep(0.6)


def len16():
    """The sketch's dimension on its 16 long side (a lock), or None."""
    return js(f"""const sk = {M}.part.features.find(f => f.id === 'F1'), P = (id) => sk.points[id];
      return sk.dims.find(x => x.t === 'len' && !x.free && (e => e && Math.abs(Math.hypot(P(e.a)[0] - P(e.b)[0], P(e.a)[1] - P(e.b)[1]) - 16) < 1e-6)(sk.entities.find(g => g.id === x.e))) || null""")


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.setItem('auto3d-lang', 'cs'); localStorage.removeItem('a3d.sizes'); localStorage.removeItem('a3d.snap3d')")
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Rameno")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 16}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    settled()
    js(f"{M}.view.setView('iso')")
    choose("F2")
    print("labels:", labels())
    el = label(lambda s: s.startswith("🔒") and s.endswith(" 16"))
    check("the extrude's 🔒 16 label on the part", el is not None and len16() is not None)

    # ---- ☐ Zamčeno -> OK: free, no 🔒
    hover_click(el)
    wait(f"return !!{M}.dimEdit")
    box = d.find_element(By.CSS_SELECTOR, POP).text
    check(f"the editor has 🔒 Zamčeno and Zobrazit: {box!r}", "Zamčeno" in box and "Zobrazit" in box)
    lock = pop("[data-c=lock]")
    check("Zamčeno is ticked (the size is locked)", lock.is_selected())
    d.save_screenshot(f"{OUT}/dim_popup_open.png")
    lock.click()
    pop("[data-a=ok]").click()
    settled()
    print("labels:", labels())
    check("OK: the 16 label without 🔒", label(lambda s: s == "16") is not None and label(lambda s: s.startswith("🔒") and s.endswith(" 16")) is None)
    check("the model data: the 16 not locked", len16() is None)

    # ---- Ctrl+Z
    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    settled()
    choose("F2")
    check("Ctrl+Z: locked again, 🔒 16 back", len16() is not None and label(lambda s: s.startswith("🔒") and s.endswith(" 16")) is not None)

    # ---- ☐ Zobrazit -> gone; Rozměry: Vše -> back
    n0 = len(labels())
    hover_click(label(lambda s: s.startswith("🔒") and s.endswith(" 16")))
    wait(f"return !!{M}.dimEdit")
    pop("[data-c=show]").click()
    pop("[data-a=ok]").click()
    settled()
    print("labels:", labels(), js(f"return {M}.part.hidden_dims"))
    check("Zobrazit unticked: the 16 label is gone, the others stay", label(lambda s: s.endswith(" 16")) is None and len(labels()) == n0 - 1)
    check("still locked (only hidden)", len16() is not None)
    check("hidden_dims saved in the part", len(js(f"return {M}.part.hidden_dims || []")) == 1)
    d.save_screenshot(f"{OUT}/dim_popup_hidden.png")
    d.find_element(By.CSS_SELECTOR, "#modelLeft .m-sizes [data-sz=all]").click()
    settled()
    check("Rozměry: Vše -> the 16 label back", label(lambda s: s.startswith("🔒") and s.endswith(" 16")) is not None and not js(f"return {M}.part.hidden_dims"))

    # ---- a hole's distance: its lock (f.lock)
    js(f"{M}.view.setView('top')")
    time.sleep(0.5)
    js(f"{M}.action('hole')")
    time.sleep(0.4)
    o = js(f"""const v = {M}.view, V = v.camera.position.constructor, [sx, sy] = v.toScreen(new V(10, 8, 10)), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""")
    ActionChains(d, duration=30).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, CV), o[0], o[1]).perform()
    time.sleep(0.4)
    ActionChains(d).click().perform()
    settled()
    f = d.find_element(By.CSS_SELECTOR, "#modelRight [data-hd='0:x']")
    f.click()
    f.send_keys(Keys.CONTROL, "a")
    f.send_keys("8")
    time.sleep(0.3)
    settled()
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=ok]").click()
    settled()
    hole = js(f"return {M}.part.features.find(f => f.type === 'hole')")
    print("hole:", hole.get("from"), hole.get("lock"))
    check("the hole's ↔ typed: locked", bool((hole.get("lock") or [{}])[0] and hole["lock"][0].get("x")))
    choose(hole["id"])
    print("labels:", labels())
    el = label(lambda s: s.startswith("🔒 ↔"))
    check("its 🔒 ↔ label on the part", el is not None)
    hover_click(el)
    wait(f"return !!{M}.dimEdit")
    lock = pop("[data-c=lock]")
    check("the hole distance's editor: Zamčeno ticked", lock.is_selected())
    lock.click()
    pop("[data-a=ok]").click()
    settled()
    lk = js(f"return {M}.part.features.find(f => f.type === 'hole').lock || null")
    check(f"OK: the ↔ distance free ({lk})", not (lk and lk[0] and lk[0].get("x")))
    el = label(lambda s: s.startswith("↔"))
    check("its label without 🔒", el is not None)
    hover_click(el)
    wait(f"return !!{M}.dimEdit")
    lock = pop("[data-c=lock]")
    check("free: Zamčeno unticked", not lock.is_selected())
    lock.click()
    o = js(f"""const v = {M}.view, V = v.camera.position.constructor, [sx, sy] = v.toScreen(new V(30, 12, 10)), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""")
    ActionChains(d, duration=30).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, CV), o[0], o[1]).perform()
    time.sleep(0.3)
    ActionChains(d).context_click().perform()
    settled()
    lk = js(f"return {M}.part.features.find(f => f.type === 'hole').lock || null")
    check(f"ticked, right-click in the view = OK: locked again ({lk})", bool(lk and lk[0] and lk[0].get("x")) and not js(f"return !!{M}.dimEdit"))
    check("its 🔒 ↔ label back", label(lambda s: s.startswith("🔒 ↔")) is not None)
    d.save_screenshot(f"{OUT}/dim_popup_hole.png")

    errs = [x["message"] for x in d.get_log("browser") if x["level"] == "SEVERE"]
    check(f"no console errors {errs}", not errs)
finally:
    d.quit()
print("ALL OK" if not fails else f"FAILED: {fails}")
sys.exit(1 if fails else 0)
