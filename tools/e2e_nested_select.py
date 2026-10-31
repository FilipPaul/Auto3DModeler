"""Choosing several parts inside sub-assemblies from the top assembly, in headless Edge: "Inner" (a plate with a pin)
in "Mid" (with a spacer) in "Top" (with a base) -> in the view: a click on the plate (the whole Mid chosen), Ctrl+click
on the spacer: the plate and the spacer chosen (2 parts, Mid not as a whole), lit in the view and in the list ->
Ctrl+click the pin (3), the base (a placed part: 4), the spacer again (out: 3) -> the panel lists them, the suggestions
have no ✕ Take them out (not Mid as a whole), Delete takes nothing out -> the list: a row, Ctrl+click another row two
levels deep, Shift+click a range -> a plain click on Mid in the view still chooses it whole.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_nested_select.py http://127.0.0.1:5199 <out dir>
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
P = "window.__app.project"
H = "window.__app.agentHandlers"
PLATE, PIN, SPACER, BASE = "I2/I2/I1", "I2/I2/I2", "I2/I1", "I1"
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


def spot(key):
    """A spot on the top of the part `key` that a click hits (its face, not another part's), not under a panel or
    the suggestions table — the rightmost one; offset from the canvas centre."""
    return js(f"""const a = {A}, v = a.view, V = v.camera.position.constructor, key = arguments[0];
      const f = a.flatParts().find((x) => x.id === key), W = new (v.camera.matrix.constructor)().fromArray(f.matrix);
      const it = a.placedAt(key).it, b = a.bodies[it.part].body.bbox, r = v.renderer.domElement.getBoundingClientRect();
      const top = key.split('/')[0], want = key.includes('/') ? key.slice(top.length + 1) + '/' : '';
      let best = null;
      for (let i = 1; i < 10; i++) for (let j = 1; j < 10; j++) {{
        const p = new V(b[0] + (b[3] - b[0]) * i / 10, b[1] + (b[4] - b[1]) * j / 10, b[5]).applyMatrix4(W), [sx, sy] = v.toScreen(p);
        const on = (x, y) => {{ const h = v.pickInst(x, y); return h?.inst === top && (want ? String(h.face?.name || '').startsWith(want) : true); }};
        const hit = [[0, 0], [-3, -3], [3, -3], [-3, 3], [3, 3]].every(([dx, dy]) => on(sx + dx, sy + dy)); // (a pixel off: still on it)
        if (hit && document.elementFromPoint(sx, sy) === v.renderer.domElement && (!best || sx > best[0])) best = [sx, sy];
      }}
      return best && [Math.round(best[0] - Math.floor(r.left + r.width / 2)), Math.round(best[1] - Math.floor(r.top + r.height / 2))];""", key)


def click(key, ctrl=False):
    off = spot(key)
    if not off:
        check(f"{key} in sight to click", False)
        return
    canvas = d.find_element(By.CSS_SELECTOR, "#asmViewport canvas")
    ch = ActionChains(d, duration=30).move_to_element_with_offset(canvas, *off)
    if ctrl:
        ch = ch.key_down(Keys.CONTROL).click().key_up(Keys.CONTROL)
    else:
        ch = ch.click()
    ch.perform()
    time.sleep(0.5)


def keys():
    return js(f"return {A}.selKeys()")


def lit_rows():
    return js("return [...document.querySelectorAll('#asmLeft .as-list .mt-item.on')].map(r => r.dataset.inst || r.dataset.path)")


def row(key):
    return d.find_element(By.CSS_SELECTOR, f"#asmLeft .as-list [data-path='{key}'], #asmLeft .as-list [data-inst='{key}']")


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
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    for path in ["I2", "I2/I2"]:  # (Mid and Inner folded open in the list)
        if path not in js(f"return [...{A}.openPaths()]"):
            js(f"{A}.toggleOpen(arguments[0])", path)
    js(f"{A}.view.setView('iso')")
    time.sleep(0.6)

    # the view: a click, then Ctrl+clicks on parts inside the sub-assemblies
    click(PLATE)
    check(f"a click on the plate: Mid chosen whole {keys()}", keys() == ["I2"])
    d.find_element(By.CSS_SELECTOR, "#asmViewport .view-suggest .vs-x").click()  # (the table folded away: not over the parts clicked next)
    time.sleep(0.3)
    click(SPACER, ctrl=True)
    check(f"Ctrl+click on the spacer: the plate and the spacer {keys()}", sorted(keys()) == sorted([PLATE, SPACER]))
    lit = js(f"return {A}.innerLit({A}.inst('I2'))")
    mesh = js(f"const m = {A}.view.meshes.find(x => x.userData.inst === 'I2'); return !!m.geometry.attributes.color")
    check(f"…both lit in the view ({lit}, coloured faces: {mesh}), Mid not as a whole", sorted(lit or []) == ["I1/", "I2/I1/"] and mesh)
    check(f"…and in the list {lit_rows()}", sorted(lit_rows()) == sorted([PLATE, SPACER]))
    click(PIN, ctrl=True)
    check(f"Ctrl+click on the pin: 3 {keys()}", sorted(keys()) == sorted([PLATE, SPACER, PIN]))
    click(BASE, ctrl=True)
    check(f"Ctrl+click on the base (a placed part): 4 {keys()}", sorted(keys()) == sorted([PLATE, SPACER, PIN, BASE]))
    click(SPACER, ctrl=True)
    check(f"Ctrl+click on the spacer again: out {keys()}", sorted(keys()) == sorted([PLATE, PIN, BASE]))
    head = d.find_element(By.CSS_SELECTOR, "#asmRight .mp-body h2").text
    items = [e.text for e in d.find_elements(By.CSS_SELECTOR, "#asmRight .as-many li")]
    check(f"the panel: {head!r} {items}", head.startswith("3") and len(items) == 3)
    sugg = js("return [...document.querySelectorAll('#asmViewport .view-suggest [data-sg]')].map(b => b.textContent)") or []
    check(f"the suggestions: no ✕ Take them out (not Mid as a whole) {sugg[:6]}", sugg and not any("Take them out" in x for x in sugg))
    d.save_screenshot(f"{OUT}/select1.png")
    n0 = js(f"return {A}.doc.instances.length")
    ActionChains(d).send_keys(Keys.DELETE).perform()
    time.sleep(0.4)
    check("Delete takes nothing out (a part inside Mid: not Mid)", js(f"return {A}.doc.instances.length") == n0)

    # the list: a row, Ctrl+click, Shift+click
    js(f"{A}.select([])")
    time.sleep(0.3)
    row(SPACER).find_element(By.CSS_SELECTOR, ".mt-name").click()
    time.sleep(0.3)
    ActionChains(d).key_down(Keys.CONTROL).click(row(PLATE).find_element(By.CSS_SELECTOR, ".mt-name")).key_up(Keys.CONTROL).perform()
    time.sleep(0.3)
    check(f"the list: a row, Ctrl+click another two levels deep {keys()}", sorted(keys()) == sorted([SPACER, PLATE]))
    ActionChains(d).key_down(Keys.SHIFT).click(row(PIN).find_element(By.CSS_SELECTOR, ".mt-name")).key_up(Keys.SHIFT).perform()
    time.sleep(0.3)
    check(f"Shift+click the pin: the rows from the plate (clicked last) to it {keys()}", sorted(keys()) == sorted([PLATE, PIN]))
    ActionChains(d).key_down(Keys.CONTROL).key_down(Keys.SHIFT).click(row(SPACER).find_element(By.CSS_SELECTOR, ".mt-name")).key_up(Keys.SHIFT).key_up(Keys.CONTROL).perform()
    time.sleep(0.3)
    check(f"Ctrl+Shift+click the spacer: those rows added {keys()}", sorted(keys()) == sorted([SPACER, "I2/I2", PLATE, PIN]))
    check(f"…lit in the list {lit_rows()}", sorted(lit_rows()) == sorted(keys()))
    js(f"{A}.select([])")
    time.sleep(0.3)
    click(PLATE)
    check(f"a plain click on a part of Mid still chooses Mid whole {keys()}", keys() == ["I2"])
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    d.quit()
print("FAILED:" if fails or errs else "all OK", fails or errs or "")
sys.exit(1 if fails or errs else 0)
