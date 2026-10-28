"""🔩 Threads shown on the part, with REAL mouse input in headless Edge:
1. A 40 x 20 x 12 block with two M6 holes (through). A click on its top face: the suggestions' "The part" offers
   🔩 Show all threads -> Cosmetic: helix lines drawn on both holes (the view's thread lines counted: 12 turns x 24
   pieces + a 48-piece ring each), the volume unchanged; the Part panel's Threads choice says Cosmetic.
2. A click on the part -> Hide all threads: no lines; Ctrl+Z: back to cosmetic.
3. The AI: set_look {threads: "hidden"}.
4. The sheet still says M6 (its callout).

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_model_threads.py http://127.0.0.1:5199 <out dir>
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
PLAIN = 40 * 20 * 12 - 2 * math.pi * 2.5 ** 2 * 12  # two Ø5 tap drills through 12
LINES = 2 * (12 * 24 + 48)  # each hole: 12 turns of 24 pieces and its 48-piece ring


def check(what, ok):
    print(("OK   " if ok else "FAIL ") + what)
    if not ok:
        failed.append(what)


def wait(script, t=60):
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


def suggestion(start):
    """The suggestions table's button whose text starts with `start` (None: not offered)."""
    for b in d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-list button"):
        if " ".join(b.text.split()).startswith(start):
            return b
    return None


def volume():
    return round(js(f"return {M}.result.body.volume"), 3)


def thread_lines():  # the view's cosmetic thread pieces (each two points)
    return js(f"const g = {M}.view.threadGroup; return g ? g.children.reduce((n, o) => n + o.geometry.attributes.position.count / 2, 0) : 0")


def click_top():
    js(f"{M}.view.setView('iso')")
    time.sleep(0.4)
    click(off_xyz([4, 4, 12]))  # the top face, off the holes


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Threads")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=12)
    wait(f"return !!{M}.result?.body")
    settled()
    print(call("add_feature", type="hole", face="F2:end", points=[[-8, 0], [8, 0]], through=True, thread="M6")[:120])
    settled()
    print("volume:", volume(), "| threaded holes:", [h["name"] for h in js(f"return {M}.threadHoles()")])
    check("two M6 holes, plain", abs(volume() - PLAIN) < 1e-3 and len(js(f"return {M}.threadHoles()")) == 2)
    check("no thread lines yet", thread_lines() == 0)

    # 1. a click on the part -> 🔩 Show all threads
    click_top()
    b = suggestion("🔩")
    print("offered:", b and " ".join(b.text.split()), "| under", js("return [...document.querySelectorAll('#modelViewport .view-suggest .vs-sec')].map(e => e.textContent)"))
    check("🔩 Show all threads offered", b is not None and "Show all threads" in b.text)
    b.click()
    time.sleep(0.3)
    settled()
    n = thread_lines()
    print("cosmetic: the view's thread pieces", n, "| expected", LINES, "| holes drawn", js(f"return {M}.view.threadCount"), "| part.threads", js(f"return {M}.part.threads"))
    check("helix lines drawn on both holes", n == LINES and js(f"return {M}.view.threadCount") == 2)
    check("cosmetic: the solid unchanged", abs(volume() - PLAIN) < 1e-3)
    seg = js("return [...document.querySelectorAll('#modelRight [data-thr]')].map(b => [b.dataset.thr, b.classList.contains('on')])")
    print("the Part panel's Threads:", seg)
    check("the Part panel says Cosmetic", ["cosmetic", True] in seg)
    js(f"""const v = {M}.view, C = v.camera.position.constructor; v.controls.target.set(12, 10, 10); v.camera.position.set(22, -4, 26); v.camera.lookAt(12, 10, 10); v.controls.update(); v.invalidate();""")
    time.sleep(0.6)
    d.find_element(By.CSS_SELECTOR, "#modelViewport").screenshot(f"{OUT}/threads_cosmetic.png")

    # 2. Hide all threads; Ctrl+Z brings them back
    click_top()
    b = suggestion("🔩")
    check("then 🔩 Hide all threads offered", b is not None and "Hide all threads" in b.text)
    b.click()
    settled()
    print("hidden:", thread_lines(), js(f"return {M}.part.threads"))
    check("hidden: no thread lines", thread_lines() == 0 and js(f"return {M}.part.threads") is None)
    ActionChains(d).move_to_element(canvas()).perform()
    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    settled()
    print("Ctrl+Z:", thread_lines(), js(f"return {M}.part.threads"))
    check("undo: cosmetic again", thread_lines() == LINES and js(f"return {M}.part.threads") == "cosmetic")

    # 3. the AI
    t = call("set_look", threads="hidden")
    settled()
    print("set_look hidden:", t)
    check("set_look threads hidden", "threads hidden" in t and thread_lines() == 0)
    t = call("set_look", threads="sideways")
    print("set_look sideways:", t)
    check("a wrong threads value refused", t.startswith("ERROR"))

    # 4. the sheet: still the M6 callout
    sizes = None
    if not call("sheet_open", part="Threads").startswith("ERROR"):
        wait("return !!window.__app.sheet.svgEl")
        sizes = sorted({x["text"] for x in json.loads(call("get_sheet"))["dims"] if x["kind"] in ("dia", "rad")})
        print("the sheet's hole sizes:", sizes)
        call("open_part", id="Threads")
        settled()
    check("the drawing says M6", sizes is not None and any("M6" in s for s in sizes))
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
print("FAILED:" if failed else "ALL OK", failed if failed else "")
sys.exit(1 if failed else 0)
