"""The freeze from the AI's report (2026-10-28 21:58): a sketch set by edit_feature to one closed profile (lines + 2 arcs
given as {arc: [u, v]}), then opened by a REAL double-click on it in the steps list, in headless Edge:
- it opens in under 2 s and the page keeps answering (a script round trip under 0.5 s, for 3 s);
- the profile is fully defined (dof 0, no conflicts, no red shapes; each arc tangent to the line it runs into, its
  centre not locked twice) and ✓ Finish sketch is green;
- with no animation frames (a hidden / covered window) get_screenshot still answers (it waited for ever: the app
  stopped asking the server for the AI's calls and looked closed);
- Finish keeps the volume.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_sketch_freeze.py http://127.0.0.1:5199 <out dir>
"""
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
d.set_script_timeout(30)
js = d.execute_script
M = "window.__app.modeler"
SK = f"{M}.sk"
H = "window.__app.agentHandlers"
PROFILE = {"points": [[-20, -30], [45, -30], [45, -14], {"arc": [66.5497, 0.9621]}, [60.06341, 26.38085], [30.06341, 52.38085],
                      {"arc": [5.4461, 55.9218]}, [-8, 35], [-20, 35]]}


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.05)
    raise TimeoutError(script)


def call(tool_name, timeout=20, **args):
    return js(f"""return Promise.race([{H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message),
      new Promise(r => setTimeout(() => r('HUNG'), {timeout * 1000}))])""", tool_name, args)


def check(what, ok, detail=""):
    print(("OK   " if ok else "FAIL ") + what, detail)
    if not ok:
        raise SystemExit(1)


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Freeze")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": -20, "y": -30, "w": 65, "h": 65}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    print(call("edit_feature", id="F1", fields={"shapes": [{"profile": PROFILE}]})[:160])
    wait(f"return !!{M}.result?.body && !{M}.inflight")
    vol0 = js(f"return {M}.result.body.volume")
    print("volume", vol0)
    row = d.find_elements(By.CSS_SELECTOR, "#modelLeft .mt-item")[0]
    t0 = time.time()
    ActionChains(d).double_click(row).perform()
    wait(f"return {M}.mode === 'sketch' && {SK}?.dof !== null && !!{SK}?.free", 10)
    opened = time.time() - t0
    check("the sketch opens in under 2 s", opened < 2, f"({opened:.2f} s)")
    slow = 0
    for _ in range(15):
        t1 = time.time()
        js("return 1")
        slow = max(slow, time.time() - t1)
        time.sleep(0.2)
    check("the page keeps answering", slow < 0.5, f"(slowest {slow:.3f} s)")
    st = js(f"""const s = {SK}; return {{dof: s.dof, bad: s.f.entities.filter(e => s.stateOf(e) === 'bad').length,
      done: s.f.entities.filter(e => s.stateOf(e) === 'done').length, n: s.f.entities.length,
      tans: s.f.constraints.filter(k => k.t === 'tan').length,
      green: document.querySelector('#modelViewport .view-actions [data-a=finish]')?.classList.contains('done')}}""")
    print("state", st)
    check("dof 0, nothing red, every shape green", st["dof"] == 0 and st["bad"] == 0 and st["done"] == st["n"])
    check("each arc tangent to the line it runs into", st["tans"] == 2)
    check("✓ Finish sketch is green", st["green"])
    d.save_screenshot(f"{OUT}/freeze1.png")

    # a hidden / covered window gets no animation frames: the AI's screenshot must still answer
    js("window.__raf = window.requestAnimationFrame; window.requestAnimationFrame = () => 0")
    t1 = time.time()
    shot = call("get_screenshot")
    check("get_screenshot answers without animation frames", shot != "HUNG" and not shot.startswith("ERROR"), f"({time.time() - t1:.2f} s)")
    js("window.requestAnimationFrame = window.__raf")

    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=finish]").click()
    wait(f"return {M}.mode !== 'sketch' && !{M}.inflight")
    if js(f"return {M}.mode") != "part":  # (Finish goes on to Extrude for a new sketch: cancel it)
        js(f"{M}.cancel?.()")
    wait(f"return {M}.mode === 'part' && !{M}.inflight && !!{M}.result?.body")
    vol1 = js(f"return {M}.result.body.volume")
    check("Finish keeps the volume", abs(vol1 - vol0) < 0.01, f"({vol0} -> {vol1})")
    print("ALL OK")
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    d.quit()
