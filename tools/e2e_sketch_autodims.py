"""🪄 Auto-dimension on the AI's reported sketches (2026-10-28 21:48 / 21:49 / 21:58), with REAL clicks in headless Edge:
A. the hand-drawn rectangle ∪ slot (single lines + two arcs, the joining line tangent to both, the arcs equal; 4 sizes
   locked, 5 free): a double-click opens it, 🪄 locks exactly the 5 it needs (R and the two arc centres from the
   origin: 9 locks in all = a rectangle's 4 + a slot's 5), dof 0, ✓ Finish green, no 🔓 left on the view's labels (the
   sizes the others set show ＝), a toast says so; Finish keeps the volume.
B. the same from the AI's shapes (rect + slot): it opens fully defined with 9 locks, nothing to add; Finish keeps the
   volume (was 59942.538 -> 59942.76: the slot's rounded sides moved).
C. a lock that contradicts the others: 🪄 says which ones do not fit (was: nothing happened, no message).

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_sketch_autodims.py http://127.0.0.1:5199 <out dir>
"""
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
d.set_script_timeout(60)
js = d.execute_script
M = "window.__app.modeler"
SK = f"{M}.sk"
H = "window.__app.agentHandlers"

# the union's outline: a 65 × 65 square from (-20, -30), a slot of R23 round (45, 9) and (15, 35)
R, C1, C2 = 23.0, (45.0, 9.0), (15.0, 35.0)
L = math.dist(C1, C2)
N = ((C2[1] - C1[1]) / L, -(C2[0] - C1[0]) / L)  # (the slot's outer side: right of c1 -> c2)
T1, T2 = [C1[0] + R * N[0], C1[1] + R * N[1]], [C2[0] + R * N[0], C2[1] + R * N[1]]
HAND = {
    "points": {"p1": [-20, -30], "p2": [45, -30], "p3": [45, C1[1] - R], "c1": list(C1), "p4": T1, "p5": T2, "c2": list(C2),
               "p6": [C2[0] - R, 35], "p7": [-20, 35]},
    "entities": [{"id": "l1", "t": "line", "a": "p1", "b": "p2"}, {"id": "l2", "t": "line", "a": "p2", "b": "p3"},
                 {"id": "a1", "t": "arc", "c": "c1", "a": "p3", "b": "p4"}, {"id": "l3", "t": "line", "a": "p4", "b": "p5"},
                 {"id": "a2", "t": "arc", "c": "c2", "a": "p5", "b": "p6"}, {"id": "l4", "t": "line", "a": "p6", "b": "p7"},
                 {"id": "l5", "t": "line", "a": "p7", "b": "p1"}],
    "constraints": [{"id": "k1", "t": "h", "e": "l1"}, {"id": "k2", "t": "v", "e": "l2"}, {"id": "k3", "t": "h", "e": "l4"},
                    {"id": "k4", "t": "v", "e": "l5"}, {"id": "k5", "t": "tan", "e": "l3", "arc": "a1", "p": "p4"},
                    {"id": "k6", "t": "tan", "e": "l3", "arc": "a2", "p": "p5"}, {"id": "k7", "t": "eq", "e": "a1", "e2": "a2", "user": True}],
    "dims": [{"id": "d1", "t": "len", "e": "l1", "v": 65}, {"id": "d2", "t": "len", "e": "l5", "v": 65},
             {"id": "d3", "t": "dx", "a": "O", "b": "p1", "v": -20}, {"id": "d4", "t": "dy", "a": "O", "b": "p1", "v": -30}],
}


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.05)
    raise TimeoutError(script)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def check(what, ok, detail=""):
    print(("OK   " if ok else "FAIL ") + what, detail)
    if not ok:
        raise SystemExit(1)


def model(name, sketch=None, shapes=None):
    """A new model: a sketch (raw JSON or the AI's shapes) extruded 10 mm -> its volume."""
    call("new_model", name=name)
    call("add_feature", type="sketch", plane="XY", shapes=shapes or [{"rect": {"x": 0, "y": 0, "w": 10, "h": 10}}])
    if sketch:
        js(f"Object.assign({M}.part.features[0], structuredClone(arguments[0])); {M}.commit()", sketch)
    call("add_feature", type="extrude", sketch="F1", d=10)
    wait(f"return !!{M}.result?.body && !{M}.inflight")
    return js(f"return {M}.result.body.volume")


def open_sketch():
    ActionChains(d).double_click(d.find_elements(By.CSS_SELECTOR, "#modelLeft .mt-item")[0]).perform()
    wait(f"return {M}.mode === 'sketch' && {SK}?.dof !== null && (!!{SK}?.free || {SK}?.conflicts?.length > 0)", 10)
    time.sleep(0.4)


def state():
    return js(f"""const s = {SK}; return {{dof: s.dof, locks: s.f.dims.filter(x => !x.free).length,
      green: !!document.querySelector('#modelViewport .view-actions [data-a=finish].done'),
      wand: !document.querySelector('.m-cmdbar [data-a=autodim]')?.hidden,
      open: [...document.querySelectorAll('#modelViewport .sk-label button.sk-lock')].filter(b => b.textContent === '🔓').length,
      driven: document.querySelectorAll('#modelViewport .sk-label .sk-driven').length,
      toast: [...document.querySelectorAll('.toast')].map(t => t.textContent).slice(-1)[0] || ''}}""")


def finish_volume():
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=finish]").click()
    wait(f"return {M}.mode === 'part' && !{M}.inflight && !!{M}.result?.body")
    return js(f"return {M}.result.body.volume")


try:
    d.get(URL)
    wait("return !!window.__app")

    print("A. the hand-drawn rectangle ∪ slot")
    v0 = model("Hand", sketch=HAND)
    open_sketch()
    st = state()
    print("  opened:", st)
    check("5 sizes free, 🪄 shown", st["dof"] == 5 and st["wand"])
    d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=autodim]").click()
    wait(f"return {SK}.dof === 0 && [...document.querySelectorAll('.toast')].some(t => /fully defined/.test(t.textContent))", 30)
    time.sleep(0.5)
    st = state()
    added = js(f"return {SK}.f.dims.slice(4).map(x => [x.t, x.e || (x.a + '>' + x.b), +x.v.toFixed(4)])")
    print("  after 🪄:", st, "| added", added)
    check("dof 0, ✓ Finish green, 🪄 hidden", st["dof"] == 0 and st["green"] and not st["wand"])
    check("9 locks (a rectangle's 4 + a slot's 5): R and the two centres", st["locks"] == 9
          and sorted(a[0] for a in added) == ["dx", "dx", "dy", "dy", "rad"], st["locks"])
    check("no 🔓 left on the labels (the others show ＝)", st["open"] == 0 and st["driven"] > 0, f"(＝ {st['driven']})")
    d.save_screenshot(f"{OUT}/autodims_hand.png")
    v1 = finish_volume()
    check("Finish keeps the volume", abs(v1 - v0) < 1e-3, f"({v0:.4f} -> {v1:.4f})")

    print("B. the AI's rect + slot shapes")
    v0 = model("Shapes", shapes=[{"rect": {"x": -20, "y": -30, "w": 65, "h": 65}}, {"slot": {"x1": 45, "y1": 9, "x2": 15, "y2": 35, "w": 46}}])
    open_sketch()
    st = state()
    print("  opened:", st)
    check("fully defined at once with 9 locks, nothing free", st["dof"] == 0 and st["locks"] == 9 and st["green"] and st["open"] == 0)
    v1 = finish_volume()
    check("Finish keeps the volume", abs(v1 - v0) < 1e-3, f"({v0:.4f} -> {v1:.4f})")

    print("D. the same outline without its tangents and equal radii: 🪄 adds them first")
    bare = {**HAND, "constraints": [k for k in HAND["constraints"] if k["t"] in ("h", "v")]}
    model("Bare", sketch=bare)
    open_sketch()
    print("  opened:", state())
    res = js(f"return {SK}.autoDimension()")
    print("  🪄:", res)
    rules = js(f"return {SK}.f.constraints.map(k => k.t)")
    check("2 tangents and the equal radii found, then the 5 sizes: dof 0 with 9 locks",
          rules.count("tan") == 2 and rules.count("eq") == 1 and len(res.get("relations", [])) == 3 and res["dof"] == 0 and state()["locks"] == 9, rules)

    print("C. a lock held twice, then one that does not fit")
    twice = {**HAND, "dims": HAND["dims"] + [{"id": "d9", "t": "dx", "a": "O", "b": "p2", "v": 45}]}  # (p2 is held by p1 + 65 already)
    model("Twice", sketch=twice)
    open_sketch()
    print("  opened:", state())
    d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=autodim]").click()
    wait(f"return {SK}.dof === 0 && [...document.querySelectorAll('.toast')].some(t => /fully defined/.test(t.textContent))", 30)
    toasts = js("return [...document.querySelectorAll('.toast')].map(t => t.textContent)")
    print("  toasts:", toasts[-2:])
    check("the lock held twice became a reference, the rest locked", js(f"return {SK}.f.dims.find(x => x.id === 'd9').free === true")
          and any("x 45: held twice" in t for t in toasts) and state()["locks"] == 9)
    bad = {**HAND, "dims": HAND["dims"] + [{"id": "d9", "t": "dx", "a": "O", "b": "p2", "v": 50}]}  # (65 from -20 is 45, not 50)
    model("Bad", sketch=bad)
    open_sketch()
    st = state()
    print("  opened:", st)
    check("the shapes of the locks that do not fit are red", js(f"return {SK}.f.entities.filter(e => {SK}.stateOf(e) === 'bad').length") > 0)
    res = js(f"return {SK}.autoDimension()")  # (as the AI's sketch_auto_dims does; the button shows only while sizes are free)
    print("  🪄:", res)
    toast = res.get("error") or ""
    check("the toast says it too", toast in js("return [...document.querySelectorAll('.toast')].map(t => t.textContent)"))
    check("🪄 names the lock that does not fit", "x 50" in toast, f"({toast})")
    print("ALL OK")
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
