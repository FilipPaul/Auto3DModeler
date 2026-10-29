"""A new thread is cosmetic and seen at once, in headless Edge: a 40 × 40 × 10 block (threads hidden, as a new part
has them) -> ◎ Hole, Type Tapped, Size M5, a real click, OK -> the part's threads are cosmetic (a toast says so), the
volume is the plain Ø4.2 tap drill's (no grooves cut), the thread lines are drawn -> the hole's panel offers 🔩 Real
thread (slower) -> Ctrl+Z takes the hole and the setting back -> threads hidden by hand, then the AI adds a tapped M4
hole: shown again (cosmetic).

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_thread_default.py http://127.0.0.1:5199 <out dir>
"""
import math
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

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
    time.sleep(0.6)
    wait(f"return !{M}.inflight")
    time.sleep(0.4)


def off_3d(p):
    return js(f"""const v = {M}.view, V = v.camera.position.constructor, [sx, sy] = v.toScreen(new V(...arguments[0])), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(p))


def toasts():
    return " | ".join(e.text for e in d.find_elements(By.CSS_SELECTOR, ".toast"))


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Thread")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    settled()
    check("a new part: threads not set (hidden)", js(f"return {M}.part.threads ?? null") is None)
    js(f"{M}.view.setView('top')")
    time.sleep(0.6)

    js(f"{M}.action('hole')")
    time.sleep(0.4)
    Select(d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=hole_type]")).select_by_value("tapped")
    time.sleep(0.3)
    Select(d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=standard]")).select_by_value("M5")
    time.sleep(0.3)
    check("the panel offers 🔩 Real thread (slower), cosmetic chosen",
          js("return !!document.querySelector('#modelRight .mp-thr-hole [data-thr=real]') && document.querySelector('#modelRight .mp-thr-hole [data-thr=cosmetic]').classList.contains('on')"))
    ActionChains(d, duration=30).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, CV), *off_3d([20, 20, 10])).perform()
    time.sleep(0.4)
    ActionChains(d).click().perform()
    time.sleep(0.6)
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=ok]").click()
    settled()
    hole = next(f for f in js(f"return {M}.part.features") if f["type"] == "hole")
    v = js(f"return {M}.result.body.volume")
    print("hole:", hole.get("thread"), hole["d"], "| threads", js(f"return {M}.part.threads"), "| volume", v, "| lines", js(f"return {M}.view.threadCount"), "|", toasts())
    check("an M5 tapped hole at the tap drill Ø4.2", hole.get("thread") == "M5" and abs(hole["d"] - 4.2) < 1e-9)
    check("the part's threads are now cosmetic", js(f"return {M}.part.threads") == "cosmetic")
    check(f"no grooves: the plain Ø4.2 hole's volume ({v:.2f})", abs(v - (16000 - math.pi * 2.1 ** 2 * 10)) < 0.5)
    check("the thread lines are drawn", js(f"return {M}.view.threadCount") == 1)
    check("a toast says the thread is cosmetic", "cosmetic" in toasts() or "kosmetick" in toasts())
    d.save_screenshot(f"{OUT}/thread_cosmetic.png")

    js(f"{M}.history.go(-1)")
    settled()
    check("Ctrl+Z: the hole and the setting go back", not any(f["type"] == "hole" for f in js(f"return {M}.part.features")) and js(f"return {M}.part.threads ?? null") is None)

    js(f"{M}.setThreads('hidden')")
    call("add_feature", type="hole", face="F2:end", points=[[-10, 0]], hole_type="tapped", standard="M4", through=True)
    settled()
    print("AI tapped M4:", js(f"return {M}.part.threads"), "| lines", js(f"return {M}.view.threadCount"))
    check("the AI's tapped hole is seen too (cosmetic)", js(f"return {M}.part.threads") == "cosmetic" and js(f"return {M}.view.threadCount") == 1)
finally:
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        fails.append("console errors")
    d.quit()

print("FAILED:" if fails else "ALL OK", fails if fails else "")
sys.exit(1 if fails else 0)
