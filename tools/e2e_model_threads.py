"""🔩 Threads shown on the part, with REAL mouse input in headless Edge:
1. A 40 x 20 x 12 block with two M6 holes (through). A click on its top face: the suggestions' "The part" offers
   🔩 Show all threads -> asked once: Cosmetic (light): helix lines drawn on both holes (the view's thread lines
   counted: 12 turns x 24 pieces + a 48-piece ring each), the volume unchanged; the Part panel's Threads says Cosmetic.
2. A click on the part -> Hide all threads: no lines; Ctrl+Z: back to cosmetic.
3. Hide, then 🔩 Show all threads -> Real geometry (slower): the volume drops by the grooves' analytic volume, faces
   F3:thread:0 / :1 beside F3:hole:k, the time and triangles printed, no lines; the Part panel says what it took;
   a close-up screenshot. The STEP / STL exports carry the threads. The Part panel's Hidden: the plain volume again;
   Ctrl+Z: real again.
4. The AI: set_look {threads: "hidden"}, a wrong value refused.
5. The sheet still says M6 (its callout), a thin ¾ circle at Ø6 on each hole, and the same lines with or without real
   threads (no helix clutter).
6. Cosmetic again, the part placed in a new assembly: its thread lines drawn there too.

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
T30 = math.tan(math.radians(30))
R, R0 = 3.0, 2.5  # M6: the major and the tap drill's radius (pitch 1)
GROOVE = 2 * math.pi * (1 / 8 * (R * R - R0 * R0) / 2 + 2 * T30 * (R * (R * R - R0 * R0) / 2 - (R ** 3 - R0 ** 3) / 3)) * 12  # one hole's groove
REAL = PLAIN - 2 * GROOVE


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
    js("document.querySelector('#modelViewport .view-suggest [data-sg-all]')?.click()")  # (⋯ Show all: the rarer rows)
    time.sleep(0.3)
    for b in d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-list button"):
        if " ".join(b.text.split()).startswith(start):
            return b
    return None


def volume():
    return round(js(f"return {M}.result.body.volume"), 3)


def thread_lines():  # the view's cosmetic thread pieces (each two points)
    return js(f"const g = {M}.view.threadGroup; return g ? g.children.reduce((n, o) => n + o.geometry.attributes.position.count / 2, 0) : 0")


def choose(start):
    """The choose dialog's answer whose text starts with `start`, clicked."""
    wait("return !!document.querySelector('.choose-back')")
    opts = d.find_elements(By.CSS_SELECTOR, ".choose-back .choose-opts button")
    print("asked:", d.find_element(By.CSS_SELECTOR, ".choose-back p").text, "|", [" ".join(o.text.split()) for o in opts])
    next(o for o in opts if o.text.startswith(start)).click()
    time.sleep(0.3)


def fetch(path, body, kind="text"):
    return js(f"return fetch(arguments[0], {{method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify(arguments[1])}})"
              f".then(r => r.{'arrayBuffer().then(b => b.byteLength)' if kind == 'size' else kind + '()'})", path, body)


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
    choose("Cosmetic")
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

    # 3. real geometry: hidden, then Show all threads -> Real
    tris0 = js(f"return {M}.result.body.face_ids.length")
    click_top()
    suggestion("🔩").click()
    settled()
    click_top()
    b = suggestion("🔩")
    check("Show all threads offered again", b is not None and "Show all threads" in b.text)
    b.click()
    t0 = time.time()
    choose("Real geometry")
    settled()
    wait(f"return {M}.result.threads.mode === 'real'")
    took = time.time() - t0
    real = js(f"return {M}.result.threads.real")
    v, tris = volume(), js(f"return {M}.result.body.face_ids.length")
    names = sorted({n for f in js(f"return {M}.result.body.faces") for n in (f.get("names") or [f.get("name")]) if n and n.startswith("F3:")})
    print(f"real: volume {v} | expected {REAL:.3f} (plain {PLAIN:.3f}) | the cut {real} | clicked to shown {took:.2f} s | triangles {tris0} -> {tris}")
    print("its faces:", names)
    check("real: the volume drops by the grooves", abs(v - REAL) < 0.01 and v < PLAIN - 1)
    check("real: thread faces beside the holes' own", {"F3:hole:0", "F3:hole:1", "F3:thread:0", "F3:thread:1"} <= set(names))
    check("real: no cosmetic lines", thread_lines() == 0)
    note = js("return document.querySelector('#modelRight .mp-thr-real')?.textContent")
    print("the Part panel:", note)
    check("the Part panel says what the cut took", note is not None and "2 real threads" in note)
    js(f"""const v = {M}.view; v.controls.target.set(12, 10, 10); v.camera.position.set(22, -4, 26); v.camera.lookAt(12, 10, 10); v.controls.update(); v.invalidate();""")
    time.sleep(0.6)
    d.find_element(By.CSS_SELECTOR, "#modelViewport").screenshot(f"{OUT}/threads_real.png")
    js(f"""const v = {M}.view; v.setView('front'); v.controls.target.set(12, 10, 6); v.camera.position.set(12, -22, 6); v.camera.lookAt(12, 10, 6); v.controls.update(); v.setSection({{axis: 'y', offset: 10, flip: true}}); v.invalidate();""")  # (the back half kept: seen from the front, cut through the hole)
    time.sleep(0.6)
    d.find_element(By.CSS_SELECTOR, "#modelViewport").screenshot(f"{OUT}/threads_real_section.png")
    js(f"{M}.view.setSection(null)")
    # the exports carry them
    part = js(f"return {M}.payload()")
    step = fetch("/api/model/export/step", {"part": part, "name": "Threads"})
    stl = fetch("/api/model/export/stl", {"part": part, "name": "Threads"}, "size")
    step0 = fetch("/api/model/export/step", {"part": {**part, "threads": "hidden"}, "name": "Threads"})
    stl0 = fetch("/api/model/export/stl", {"part": {**part, "threads": "hidden"}, "name": "Threads"}, "size")
    print("STEP:", step.count("B_SPLINE_SURFACE"), "spline surfaces (hidden:", step0.count("B_SPLINE_SURFACE"), ") | STL triangles", (stl - 84) // 50, "(hidden:", (stl0 - 84) // 50, ")")
    check("the STEP / STL exports carry the threads", step.count("B_SPLINE_SURFACE") > 20 and step0.count("B_SPLINE_SURFACE") == 0 and stl > 10 * stl0)
    # the Part panel's Hidden: the plain part; Ctrl+Z: real again
    d.find_element(By.CSS_SELECTOR, "#modelRight [data-thr=hidden]").click()
    settled()
    print("the Part panel's Hidden:", volume())
    check("Hidden: back to the plain part", abs(volume() - PLAIN) < 1e-3 and js(f"return {M}.part.threads") is None)
    ActionChains(d).move_to_element(canvas()).perform()
    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    settled()
    print("Ctrl+Z:", volume(), js(f"return {M}.part.threads"), js(f"return {M}.result.threads.real"))
    check("undo: real again (cut once, kept)", abs(volume() - REAL) < 0.01 and js(f"return {M}.part.threads") == "real")

    # 3. the AI
    t = call("set_look", threads="real")
    print("set_look real:", t)
    check("set_look threads real", "threads real" in t and "cut in" in t)
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
        arcs = js("return window.__app.sheet.svg().split('sh-thread').length - 1")
        print("the sheet's hole sizes:", sizes, "| ¾ thread circles:", arcs)
        check("the sheet: a thin ¾ circle on each threaded hole", arcs == 2)
        d.find_element(By.CSS_SELECTOR, "#shViewport").screenshot(f"{OUT}/threads_sheet.png")
        call("open_part", id="Threads")
        settled()
    check("the drawing says M6", sizes is not None and any("M6" in s for s in sizes))
    part = js(f"return {M}.payload()")
    geo = lambda mode: fetch("/api/sheet/build", {"part": {**part, "threads": mode}, "preset": "medium"}, "json")["geometry"]["views"]  # noqa: E731
    a, b = geo("hidden"), geo("real")
    print("the sheet's lines, hidden / real:", {k: len(a[k]["visible"]) for k in a}, {k: len(b[k]["visible"]) for k in b})
    check("the sheet: no helix clutter with real threads", all(a[k]["visible"] == b[k]["visible"] for k in a))

    # 6. an assembly: a placed part shows its part's threads (cosmetic)
    call("set_look", threads="cosmetic")
    settled()
    call("new_assembly", name="Threads asm")
    print("insert:", call("insert_part", part="Threads")[:60])
    A = "window.__app.assembly"
    wait(f"return {A}.bodies && Object.values({A}.bodies).some(b => b.body)")
    time.sleep(1)
    n = js(f"return {A}.view.bodyGroup.children.filter(o => o.material === {A}.view.threadMaterial).reduce((n, o) => n + o.geometry.attributes.position.count / 2, 0)")
    print("the assembly's thread pieces:", n)
    check("a placed part shows its part's cosmetic threads", n == LINES)
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
print("FAILED:" if failed else "ALL OK", failed if failed else "")
sys.exit(1 if failed else 0)
