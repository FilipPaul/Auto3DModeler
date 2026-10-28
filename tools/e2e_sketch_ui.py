"""The sketch panel and suggestions from the AI's UI report (2026-10-28 21:49), with REAL clicks in headless Edge:
A. the AI's rect + overlapping slot: the panel offers ∪ Unite overlapping shapes -> one outline (the exact union's
   volume after Finish); its rows are named ("Width 65", "Height 65"), a row under the mouse lights its label.
B. a hand-drawn rect ∪ slot with odd values (R23.2155, a centre at y 8.94): 🪄 Lock at rounded values -> R23, y 9 …
   listed in the panel; ↶ Take back -> as it was; again and ✓ Keep -> fully defined at the round values.
C. a lock that does not fit: the panel says which ones do not fit, the row and the shapes red.
D. a slot drawn as two lines and two half arcs (no relations): a click on a side -> the suggestions offer ⊂⊃ Make it a
   slot first -> tangent joins and equal ends, one shape.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_sketch_ui.py http://127.0.0.1:5199 <out dir>
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


def hand(R, C1, C2, dims=True):
    """A 65 × 65 square from (-20, -30) ∪ a slot of radius R round C1 and C2, as single lines and arcs, its joining
    line tangent to both arcs, the arcs equal; locked: the square's width, height and corner."""
    L = math.dist(C1, C2)
    N = ((C2[1] - C1[1]) / L, -(C2[0] - C1[0]) / L)
    T1, T2 = [C1[0] + R * N[0], C1[1] + R * N[1]], [C2[0] + R * N[0], C2[1] + R * N[1]]
    return {
        "points": {"p1": [-20, -30], "p2": [45, -30], "p3": [45, C1[1] - math.sqrt(R * R - (45 - C1[0]) ** 2)], "c1": list(C1), "p4": T1, "p5": T2,
                   "c2": list(C2), "p6": [C2[0] - math.sqrt(R * R - (35 - C2[1]) ** 2), 35], "p7": [-20, 35]},
        "entities": [{"id": "l1", "t": "line", "a": "p1", "b": "p2"}, {"id": "l2", "t": "line", "a": "p2", "b": "p3"},
                     {"id": "a1", "t": "arc", "c": "c1", "a": "p3", "b": "p4"}, {"id": "l3", "t": "line", "a": "p4", "b": "p5"},
                     {"id": "a2", "t": "arc", "c": "c2", "a": "p5", "b": "p6"}, {"id": "l4", "t": "line", "a": "p6", "b": "p7"},
                     {"id": "l5", "t": "line", "a": "p7", "b": "p1"}],
        "constraints": [{"id": "k1", "t": "h", "e": "l1"}, {"id": "k2", "t": "v", "e": "l2"}, {"id": "k3", "t": "h", "e": "l4"},
                        {"id": "k4", "t": "v", "e": "l5"}, {"id": "k5", "t": "tan", "e": "l3", "arc": "a1", "p": "p4"},
                        {"id": "k6", "t": "tan", "e": "l3", "arc": "a2", "p": "p5"}, {"id": "k7", "t": "eq", "e": "a1", "e2": "a2", "user": True}],
        "dims": [{"id": "d1", "t": "len", "e": "l1", "v": 65}, {"id": "d2", "t": "len", "e": "l5", "v": 65},
                 {"id": "d3", "t": "dx", "a": "O", "b": "p1", "v": -20}, {"id": "d4", "t": "dy", "a": "O", "b": "p1", "v": -30}] if dims else [],
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
    call("new_model", name=name)
    call("add_feature", type="sketch", plane="XY", shapes=shapes or [{"rect": {"x": 0, "y": 0, "w": 10, "h": 10}}])
    if sketch:
        js(f"Object.assign({M}.part.features[0], structuredClone(arguments[0])); {M}.commit()", sketch)
    call("add_feature", type="extrude", sketch="F1", d=10)
    wait(f"return !!{M}.result?.body && !{M}.inflight")


def open_sketch():
    ActionChains(d).double_click(d.find_elements(By.CSS_SELECTOR, "#modelLeft .mt-item")[0]).perform()
    wait(f"return {M}.mode === 'sketch' && {SK}?.dof !== null && ({SK}.free || {SK}.conflicts?.length)", 10)
    time.sleep(0.5)


def panel_button(a):
    return d.find_element(By.CSS_SELECTOR, f"#modelRight [data-a={a}], .mp-body [data-a={a}]")


def finish():
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=finish]").click()
    wait(f"return {M}.mode === 'part' && !{M}.inflight && !!{M}.result?.body")
    return js(f"return {M}.result.body.volume")


def off(uv):
    return js(f"""const m = {M}, v = m.view, f = m.frame(), [u, w] = arguments[0];
      const y = [f.n[1]*f.x[2]-f.n[2]*f.x[1], f.n[2]*f.x[0]-f.n[0]*f.x[2], f.n[0]*f.x[1]-f.n[1]*f.x[0]];
      const p = new (v.camera.position.constructor)(f.o[0] + u*f.x[0] + w*y[0], f.o[1] + u*f.x[1] + w*y[1], f.o[2] + u*f.x[2] + w*y[2]);
      const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(uv))


try:
    d.get(URL)
    wait("return !!window.__app")

    print("A. ∪ Unite from the panel; named rows")
    model("Unite", shapes=[{"rect": {"x": -20, "y": -30, "w": 65, "h": 65}}, {"slot": {"x1": 45, "y1": 9, "x2": 15, "y2": 35, "w": 46}}])
    open_sketch()
    rows = [r.text for r in d.find_elements(By.CSS_SELECTOR, ".sk-dim[data-dimrow]")]
    print("  rows:", rows)
    check("rows are named: Width 65, Height 65, R23", any("Width 65" in r for r in rows) and any("Height 65" in r for r in rows) and any("R23" in r for r in rows))
    row = next(r for r in d.find_elements(By.CSS_SELECTOR, ".sk-dim[data-dimrow]") if "Width 65" in r.text)
    ActionChains(d).move_to_element(row).perform()
    time.sleep(0.3)
    lit = js(f"return [document.querySelector('.sk-label.lit')?.dataset.dim || null, {SK}.hoverSize?.key || null]")
    check("the mouse on a row lights its dimension in the view", lit[0] == row.get_attribute("data-dimrow") and lit[1], lit)
    ActionChains(d).move_by_offset(0, 300).perform()
    panel_button("unite").click()
    wait("return [...document.querySelectorAll('.toast')].some(t => /One outline/.test(t.textContent))", 30)
    n = js(f"return {SK}.f.entities.length")
    check("∪ makes one outline (5 lines + 2 arcs), the button goes", n == 7 and not d.find_elements(By.CSS_SELECTOR, "[data-a=unite]"), n)
    v = finish()
    check("the exact union's volume", abs(v - 59945.0078) < 0.01, v)

    print("B. 🪄 Lock at rounded values: listed, taken back, kept")
    model("Rounded", sketch=hand(23.2155, (45, 8.94), (15, 35)))
    open_sketch()
    pts0 = js(f"return JSON.stringify({SK}.f.points)")
    panel_button("autodimRound").click()
    wait(f"return !!document.querySelector('.sk-rounded')", 30)
    items = [li.text for li in d.find_elements(By.CSS_SELECTOR, ".sk-rounded li")]
    print("  rounded:", items)
    check("the rounded values are listed as drawn (R23.215 → R23, y 8.94 → y 9)", any(i.startswith("R23.2") and "→ R23" in i for i in items) and "y 8.94 → y 9" in items)
    check("fully defined at them", js(f"return {SK}.dof") == 0 and any(abs(x - 23) < 1e-9 for x in js(f"return {SK}.f.dims.filter(x => x.t === 'rad').map(x => x.v)")))
    panel_button("roundBack").click()
    time.sleep(0.6)
    check("↶ Take back: the sketch as it was", js(f"return {SK}.f.dims.length") == 4 and js(f"return JSON.stringify({SK}.f.points)") == pts0
          and not d.find_elements(By.CSS_SELECTOR, ".sk-rounded"))
    wait(f"return !!document.querySelector('[data-a=autodimRound]')", 10)
    panel_button("autodimRound").click()
    wait(f"return !!document.querySelector('.sk-rounded')", 30)
    panel_button("roundKeep").click()
    time.sleep(0.4)
    check("✓ Keep: the list goes, the round values stay", not d.find_elements(By.CSS_SELECTOR, ".sk-rounded") and js(f"return {SK}.dof") == 0)
    d.save_screenshot(f"{OUT}/sketch_ui_rounded.png")
    finish()

    print("C. a lock that does not fit: said in the panel, red")
    bad = hand(23, (45, 9), (15, 35))
    bad["dims"].append({"id": "d9", "t": "dx", "a": "O", "b": "p2", "v": 50})
    model("Bad", sketch=bad)
    open_sketch()
    why = d.find_element(By.CSS_SELECTOR, ".sk-why.bad").text
    check("the panel names the locks that do not fit", "x 50" in why and "do not fit" in why, why)
    check("their rows and shapes are red", d.find_elements(By.CSS_SELECTOR, ".sk-dim.bad[data-dimrow=d9]")
          and js(f"return {SK}.f.entities.filter(e => {SK}.stateOf(e) === 'bad').length") > 0)
    d.save_screenshot(f"{OUT}/sketch_ui_bad.png")

    print("D. ⊂⊃ Make it a slot from the suggestions")
    slot = {"points": {"c1": [0, 0], "c2": [30, 0], "A": [0, -8], "B": [30, -8], "C": [30, 8], "D": [0, 8]},
            "entities": [{"id": "l1", "t": "line", "a": "A", "b": "B"}, {"id": "a1", "t": "arc", "c": "c2", "a": "B", "b": "C"},
                         {"id": "l2", "t": "line", "a": "C", "b": "D"}, {"id": "a2", "t": "arc", "c": "c1", "a": "D", "b": "A"}],
            "constraints": [], "dims": []}
    model("Slot", sketch=slot)
    open_sketch()
    dof0 = js(f"return {SK}.dof")
    js(f"{M}.view.lookAt({M}.frame(), 60); {SK}.draw()")
    time.sleep(0.4)
    ActionChains(d, duration=30).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, "#modelViewport canvas"), *off((8, -8))).perform()  # (not its middle: that picks the midpoint)
    time.sleep(0.15)
    ActionChains(d).click().perform()
    time.sleep(0.5)
    sug = [b.text for b in d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-list button")]
    print("  suggestions:", sug)
    check("⊂⊃ Make it a slot is offered first", sug and "Make it a slot" in sug[0])
    d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-list button")[0].click()
    time.sleep(0.8)
    rules = js(f"return {SK}.f.constraints.map(k => k.t)")
    groups = js(f"return new Set({SK}.f.entities.map(e => e.g)).size")
    check("a slot: 4 tangent joins, equal ends, one shape", rules.count("tan") == 4 and rules.count("eq") == 1 and groups == 1, (rules, groups))
    check("fewer free sizes (5: two centres and a radius)", js(f"return {SK}.dof") == 5 and dof0 > 5, (dof0, js(f"return {SK}.dof")))
    print("ALL OK")
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
