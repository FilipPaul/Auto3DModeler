"""Two faces picked in an assembly, in either order, with REAL mouse and keyboard input: a Base (not fixed) and a Plate on
it (⧉ Touch, turned 10°) -> a click on the Base's side, then Ctrl+click on the Plate's side (the parent first: the
"wrong" order) -> ∥ Parallel, ⟂ Perpendicular and ∠ Angle among the top rows of the table -> ∥ clicked: joined, the
Plate (the part that hangs on the other) turns, not refused ("join them the other way round") -> one face picked:
∥ in the top rows shown (not only under ⋯ Show all) -> Esc in the view clears a two-face pick (also with a table
row or a panel's slider in the keyboard's hand).

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_twoface.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

URL, OUT = sys.argv[1], sys.argv[2]
bad = []


def check(ok, what):
    print(("  ok  " if ok else "  FAIL") + " " + what)
    if not ok:
        bad.append(what)


opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
H = "window.__app.agentHandlers"
A = "window.__app.assembly"


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


def world(inst, p):
    return js(f"const m = {A}.inst(arguments[0]).matrix, [x, y, z] = arguments[1]; return [m[0]*x + m[4]*y + m[8]*z + m[12], m[1]*x + m[5]*y + m[9]*z + m[13], m[2]*x + m[6]*y + m[10]*z + m[14]]", inst, p)


def at(inst, p):
    """A point of a placed part on the screen, from the canvas' middle (px)."""
    return js(f"""const v = {A}.view, V = v.camera.position.constructor, [sx, sy] = v.toScreen(new V(...arguments[0])), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", world(inst, p))


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#asmViewport canvas")


def click(inst, p, ctrl=False):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *at(inst, p)).perform()
    time.sleep(0.3)
    ch = ActionChains(d)
    (ch.key_down(Keys.CONTROL).click().key_up(Keys.CONTROL) if ctrl else ch.click()).perform()
    time.sleep(0.6)


def picks():
    return js(f"return ({A}.facePicks || []).map(q => [q.inst, q.face.name])")


def rows():
    return [" ".join(b.text.split()) for b in d.find_elements(By.CSS_SELECTOR, "#asmViewport .view-suggest .vs-list button:not(.vs-more)")]


def toasts():
    return js("return [...document.querySelectorAll('.toast')].map(e => e.textContent).join(' | ')")


try:
    d.get(URL)
    wait("return !!window.__app")
    js("window.confirm = () => true")
    call("new_model", name="Base")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 80, "h": 50}}])
    call("add_feature", type="extrude", sketch="F1", d=6)
    call("new_model", name="Plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 30}}])
    call("add_feature", type="extrude", sketch="F1", d=4)
    time.sleep(1)
    call("new_assembly", name="Order")
    call("insert_part", part="Base")
    call("insert_part", part="Plate")
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    call("place_part", part="I1", fixed=False)  # (neither fixed: only the order tells which moves — the report's case)
    r = call("snap_faces", type="touch", move={"part": "I2", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})
    check(not r.startswith("ERROR"), f"⧉ the Plate on the Base ({r[:60]})")
    js(f"{A}.turnAbout({A}.doc.mates[0], 10)")
    js(f"{A}.facePicks = []; {A}.choose(null); {A}.view.setView('iso')")
    time.sleep(0.8)

    # the parent's face first, then Ctrl+click the child's: the "wrong" order
    click("I1", [40, 0, 3])
    click("I2", [20, 0, 2], ctrl=True)
    p = picks()
    print("picked:", p)
    check([q[0] for q in p] == ["I1", "I2"], "two faces picked: the Base's side, then the Plate's side")
    rs = rows()
    print("the table:", rs)
    top = rs[:5]
    check(all(any(x.startswith(icon) for x in top) for icon in ("∥", "⟂", "∠")), f"∥ / ⟂ / ∠ among the top 5 rows: {top}")
    js(f"{A}.hooks.toast = ((f) => (text, ...rest) => {{ (window.__toasts = window.__toasts || []).push(text); return f(text, ...rest); }})({A}.hooks.toast)")
    next(b for b in d.find_elements(By.CSS_SELECTOR, "#asmViewport .view-suggest .vs-list button") if b.text.strip().startswith("∥")).click()
    time.sleep(0.8)
    said = js("return (window.__toasts || []).join(' | ')")
    print("toasts:", said)
    j = json.loads(call("get_assembly"))["joints"]
    print("joints:", [(x["id"], x["type"], x.get("move"), x.get("onto"), x.get("not_held")) for x in j])
    par = [x for x in j if x["type"] == "parallel"]
    check(len(par) == 1 and "other way round" not in said, "∥ made in the 'wrong' order — not refused")
    check(js(f"return {A}.doc.mates.find(m => m.type === 'parallel')?.move") == "I2", "the Plate (the part that hangs on the Base) moves")
    check(all(not x.get("not_held") for x in j), "every joint holds")
    ang = js(f"const a = {A}; return +(a.worldFace('I2', 'F2:side:l1').normal.angleTo(a.worldFace('I1', 'F2:side:l1').normal) * 180 / Math.PI).toFixed(3)")
    check(ang < 0.05, f"the sides parallel now ({ang}°)")
    d.save_screenshot(f"{OUT}/twoface_parallel.png")

    # one flat face picked: ∥ in the rows shown, not only under ⋯ Show all
    js(f"{A}.facePicks = []; {A}.choose(null)")
    click("I1", [40, 0, 3])
    rs = rows()
    print("one face:", rs)
    check(any(x.startswith("∥") for x in rs), "one flat face: ∥ Parallel… among the rows shown")

    # Esc in the view clears a two-face pick
    click("I2", [20, 0, 2], ctrl=True)
    check(len(picks()) == 2, f"two faces picked again: {picks()}")
    ActionChains(d).send_keys(Keys.ESCAPE).perform()
    time.sleep(0.4)
    check(picks() == [] and js(f"return {A}.sel") is None, f"Esc: the faces and the part unpicked ({picks()}, sel {js(f'return {A}.sel')})")
    click("I1", [40, 0, 3])
    click("I2", [20, 0, 2], ctrl=True)
    js("document.querySelector('#asmViewport .view-suggest .vs-list button')?.focus()")
    ActionChains(d).send_keys(Keys.ESCAPE).perform()
    time.sleep(0.4)
    check(picks() == [], f"Esc with a table row in the keyboard's hand: unpicked too ({picks()})")
    click("I2", [20, 0, 2])
    sl = d.find_elements(By.CSS_SELECTOR, "#asmRight input[type=range]")
    if sl:
        sl[0].click()  # (a slider of its panel in the keyboard's hand — a click on it moves it a little)
        time.sleep(0.4)
        ActionChains(d).send_keys(Keys.ESCAPE).perform()
        time.sleep(0.4)
        check(picks() == [] and js(f"return {A}.sel") is None, f"Esc with a slider of the panel in the keyboard's hand: unpicked ({picks()}, sel {js(f'return {A}.sel')})")
    else:
        check(False, "the Plate's panel has a slider")
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
print("FAILED:" if bad else "ALL OK", bad if bad else "")
sys.exit(1 if bad else 0)
