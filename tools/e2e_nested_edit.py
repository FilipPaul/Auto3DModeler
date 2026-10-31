"""Editing a part two sub-assemblies deep from the top assembly, in headless Edge: "Inner" (a plate with a pin),
placed turned 90° and moved in "Mid" (with a spacer), placed moved in "Top" (with a base) -> in Top, the plate's row
(I2/I2/I1) in the list: ✎ Edit it here is off while 🔒 Locked, a double-click on the plate in the view says so and
shows its panel -> 🔓 -> ✎ Edit it here: the plate in the 3D modeler, the base, the spacer and the pin see-through
around it, each where it is in Top seen from the plate (its frame) -> a Ø6 hole added -> ◇ Back: Top shows the plate
with the hole (its merged sub-assembly body smaller by the hole), Mid (kept warm, opened before) and Inner too -> a
double-click on the plate opens it again -> ✏ Sketch on this face from one of its faces picked in Top: a sketch
open on that face of the plate.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_nested_edit.py http://127.0.0.1:5199 <out dir>
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
js = d.execute_script
M = "window.__app.modeler"
A = "window.__app.assembly"
P = "window.__app.project"
H = "window.__app.agentHandlers"
KEY = "I2/I2/I1"  # Top's Mid -> Mid's Inner -> Inner's plate
HOLE = math.pi * 9 * 5  # a Ø6 hole through the 5 mm plate
fails = []


def check(what, ok):
    print(("OK  " if ok else "FAIL"), what)
    if not ok:
        fails.append(what)


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def tab(name):
    js(f"const p = {P}.parts.find(q => q.name === arguments[0]); return {P}.switchTo(p.id)", name)
    wait(f"return window.__app.state.workspace === 'assembly' && {P}.current.name === arguments[0]".replace("arguments[0]", repr(name)), 60)
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    time.sleep(0.6)


def drawn_volume(inst):
    """The volume of the body drawn on screen for this placed part."""
    return js(f"const m = ({A}.view.meshes || []).find(x => x.userData.inst === arguments[0]); return m ? m.userData.body.volume : null", inst)


def plate_world():
    """The plate's matrix in Top, from the kernel's flat list of parts (another path than the edit's own)."""
    return js(f"return {A}.flatParts().find(f => f.id === arguments[0]).matrix", KEY)


def dblclick_plate():
    """A double-click on a spot of the plate's top in sight (not behind the pin) — its rightmost one: the suggestions
    table the first click shows floats at the view's left, the second click is not to land on it."""
    off = js(f"""const a = {A}, v = a.view, V = v.camera.position.constructor, W = new (v.camera.matrix.constructor)().fromArray(arguments[0]);
      const r = v.renderer.domElement.getBoundingClientRect();
      let best = null;
      for (let x = 4; x <= 56; x += 4) for (let y = 4; y <= 36; y += 4) {{
        const [sx, sy] = v.toScreen(new V(x, y, 5).applyMatrix4(W)), h = v.pickInst(sx, sy);
        if (h?.face?.name === 'I2/I1/F2:end' && document.elementFromPoint(sx, sy) === v.renderer.domElement && (!best || sx > best[0])) best = [sx, sy];
      }}
      return best && [Math.round(best[0] - Math.floor(r.left + r.width / 2)), Math.round(best[1] - Math.floor(r.top + r.height / 2))];""", plate_world())
    check("the plate's top in sight", bool(off))
    ActionChains(d, duration=30).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, "#asmViewport canvas"), *off).perform()
    time.sleep(0.2)
    ActionChains(d).double_click().perform()
    time.sleep(0.8)


def toast():
    return js("return [...document.querySelectorAll('.toast')].map(t => t.textContent).slice(-1)[0]")


def choose_plate():
    js(f"{A}.select([arguments[0]])", KEY)
    time.sleep(0.4)


def back():
    d.find_element(By.CSS_SELECTOR, "#modelViewport [data-a=ctxBack]").click()
    wait(f"return window.__app.state.workspace === 'assembly' && {P}.current.name === 'Top'", 30)
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    time.sleep(0.6)


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=8)
    for name, shape, h in [("Pin", {"circle": {"x": 0, "y": 0, "d": 8}}, 20), ("Spacer", {"rect": {"x": 0, "y": 0, "w": 20, "h": 10}}, 15),
                           ("Base", {"rect": {"x": 0, "y": 0, "w": 200, "h": 120}}, 10)]:
        call("new_model", name=name)
        call("add_feature", type="sketch", plane="XY", shapes=[shape])
        call("add_feature", type="extrude", sketch="F1", d=h)
    time.sleep(1)
    call("new_assembly", name="Inner")
    call("insert_part", part="Plate")
    call("insert_part", part="Pin")
    call("snap_faces", type="axis", move={"part": "I2", "face": "F2:side:c1"}, onto={"part": "I1", "face": "F3:hole:0"})
    call("new_assembly", name="Mid")
    call("insert_part", part="Spacer")
    call("insert_part", part="Inner")
    call("place_part", part="I2", x=40, y=-20, z=15, turn="z")
    call("new_assembly", name="Top")
    call("insert_part", part="Base")
    call("insert_part", part="Mid")
    call("place_part", part="I2", x=-30, y=10, z=10)
    tab("Mid")  # (opened once: kept warm while Top is on screen)
    tab("Top")
    js(f"{A}.view.setView('iso')")
    time.sleep(0.4)
    sub0 = js(f"return {A}.bodyOf({A}.inst('I2')).body.volume")
    plate0 = js(f"return {A}.bodies[{P}.parts.find(p => p.name === 'Plate').id].body.volume")

    # the nested plate's panel: locked; a double-click on it says so and shows that panel
    choose_plate()
    btn = d.find_element(By.CSS_SELECTOR, "#asmRight [data-a=editHere]")
    check(f"nested plate's panel: ✎ Edit it here off while locked ({d.find_element(By.CSS_SELECTOR, '#asmRight [data-a=editLock]').text})", not btn.is_enabled())
    check("its panel has the 🔒 for the AI", bool(d.find_elements(By.CSS_SELECTOR, "#asmRight .ai-lock-panel")))
    js(f"{A}.select([])")
    time.sleep(0.3)
    dblclick_plate()
    check(f"double-click while locked: {toast()!r}", "locked" in (toast() or "") and js("return window.__app.state.workspace") == "assembly")
    check(f"…and the plate's panel shown ({js(f'return {A}.selKeys()')})", js(f"return {A}.selKeys().join()") == KEY)
    d.find_element(By.CSS_SELECTOR, "#asmRight [data-a=editLock]").click()
    time.sleep(0.3)
    check("unlocked: ✎ Edit it here on", d.find_element(By.CSS_SELECTOR, "#asmRight [data-a=editHere]").is_enabled())
    js(f"{A}.facePicks = []; {A}.renderSuggest()")
    time.sleep(0.3)
    sugg = js("return [...document.querySelectorAll('#asmViewport .sg-table button, #asmViewport [data-sg]')].map(b => b.textContent)") or []
    check(f"the suggestions for the chosen nested plate: {sugg[:3]}", any("Edit the part here" in x for x in sugg))

    # the plate opened in place: the rest of Top around it, in the plate's frame
    want = js(f"""const a = {A}, W = new (a.view.camera.matrix.constructor)(), V = a.view.camera.position.constructor;
      const Mi = W.clone().fromArray(arguments[0]).invert();
      return a.flatParts().filter(f => f.id !== arguments[1]).map(f => {{
        const b = a.bodies[a.flatParts && a.hooks.parts().find(p => p.name === a.partName(a.placedAt(f.id).it.part)).id].body.bbox;
        const c = new V((b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2).applyMatrix4(Mi.clone().multiply(W.clone().fromArray(f.matrix)));
        return c.toArray().map(v => Math.round(v * 100) / 100); }}).sort();""", plate_world(), KEY)
    d.find_element(By.CSS_SELECTOR, "#asmRight [data-a=editHere]").click()
    wait(f"return window.__app.state.workspace === 'model' && !!{M}.result?.body && !{M}.inflight")
    time.sleep(0.4)
    got = js(f"""const g = {M}.view.ctxGroup; return g.children.map(m => {{ m.geometry.computeBoundingBox();
      const c = m.geometry.boundingBox.getCenter(m.position.clone()).applyMatrix4(m.matrix); return c.toArray().map(v => Math.round(v * 100) / 100); }}).sort();""")
    check(f"editing {js(f'return {P}.current.name')} in {d.find_element(By.CSS_SELECTOR, '#modelViewport .m-editctx').text.splitlines()[0]!r}", js(f"return {P}.current.name") == "Plate")
    print("  context centres (plate frame):", got, "\n  expected:", want)
    check("the base, spacer and pin see-through, each where it is in Top (the plate's frame)",
          len(got) == 3 and len(want) == 3 and all(abs(x - y) < 0.05 for g, w in zip(got, want) for x, y in zip(g, w)))
    js(f"{M}.view.setView('iso')")
    time.sleep(0.4)
    d.save_screenshot(f"{OUT}/nested1.png")
    call("add_feature", type="hole", face="F2:end", points=[[20, 10]], d=6)
    wait(f"return !{M}.inflight")
    back()

    # Top, Mid and Inner show the hole
    sub1 = js(f"return {A}.bodyOf({A}.inst('I2')).body.volume")
    check(f"Top: Mid's body {sub0:.2f} -> {sub1:.2f} mm³ (the hole {HOLE:.2f}); drawn {drawn_volume('I2'):.2f}",
          abs(sub0 - sub1 - HOLE) < 1 and abs(drawn_volume("I2") - sub1) < 1e-6)
    js(f"{A}.view.setView('iso')")
    time.sleep(0.4)
    d.save_screenshot(f"{OUT}/nested2.png")
    tab("Mid")
    check(f"Mid (kept warm): Inner drawn {drawn_volume('I2'):.2f} mm³", abs(drawn_volume("I2") - (plate0 - HOLE + js(f"return {A}.bodies[{P}.parts.find(p => p.name === 'Pin').id].body.volume"))) < 1)
    tab("Inner")
    check(f"Inner: the plate drawn {drawn_volume('I1'):.2f} mm³", abs(drawn_volume("I1") - (plate0 - HOLE)) < 1)
    tab("Top")

    # a double-click on the plate (unlocked) opens it; ✏ a sketch on its face picked in Top
    js(f"{A}.view.setView('iso')")
    time.sleep(0.4)
    js(f"{A}.facePicks = []; {A}.select([])")  # (no suggestions table over the plate)
    time.sleep(0.3)
    dblclick_plate()
    wait("return window.__app.state.workspace === 'model'", 30)
    check(f"double-click (unlocked) opens {js(f'return {P}.current.name')}", js(f"return {P}.current.name") == "Plate")
    back()
    rows = js(f"return {A}.faceSketchItems({{ inst: 'I2', face: {{ type: 'plane', name: 'I2/I1/F2:end' }} }}, {A}.inst('I2')).map(x => x.label)")
    check(f"a face of the nested plate picked in Top: {rows}", len(rows) == 1)
    js(f"{A}.faceSketchItems({{ inst: 'I2', face: {{ type: 'plane', name: 'I2/I1/F2:end' }} }}, {A}.inst('I2'))[0].run()")
    wait(f"return window.__app.state.workspace === 'model' && {M}.mode === 'sketch'", 30)
    check(f"✏ Sketch on this face: a sketch open in {js(f'return {P}.current.name')}", js(f"return {P}.current.name") == "Plate")
    d.save_screenshot(f"{OUT}/nested3.png")
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    d.quit()
print("FAILED:" if fails or errs else "all OK", fails or errs or "")
sys.exit(1 if fails or errs else 0)
