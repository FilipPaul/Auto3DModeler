"""Joining two parts inside a sub-assembly from the top assembly, in headless Edge: "Inner" (a plate with a pin) in
"Mid" (with a bushing) placed twice in "Top" (with a base) -> in the view: a click on the bushing's hole rim, Ctrl+click
on the pin's rim (two parts of Mid, one of them two levels deep): both faces picked, both parts chosen, ◎ Concentric
offered -> clicked: the joint is Mid's own (its document, not Top's), the pin's axis on the hole's in both copies of
Mid, the toast says where it went -> Ctrl+Z: Mid as it was -> 🔒 Mid locked for changes from here: the same picks join nothing, said -> two
bushings in the two copies of Mid: the joint is Top's (one whole copy moves), the axes on one line -> Mid's panel: its
🔓 / 🔒 and how many joints it keeps.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_nested_join.py http://127.0.0.1:5199 <out dir>
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
HOLE, PIN = "I1/F3:hole:0", "I2/I2/F2:side:c1"  # (the bushing's hole and the pin's round face, as Mid's merged body names them)
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


def rim(top, name):
    """A spot on a circular edge of the round face `name` of the placed part `top` that a plain click picks as that
    face (no snap point there, not under a panel) — offset from the canvas centre."""
    return js(f"""const a = {A}, v = a.view, V = v.camera.position.constructor, [top, name] = arguments;
      const mesh = v.meshes.find((m) => m.userData.inst === top), body = mesh.userData.body, cv = v.renderer.domElement, r = cv.getBoundingClientRect();
      const idx = new Set(body.faces.map((f, i) => (f.name === name || (f.names || []).includes(name) ? i : -1)).filter((i) => i >= 0)), ok = [];
      for (const e of body.edges) {{
        if (!(e.faces || []).some((i) => idx.has(i))) continue;
        for (let k = 0; k + 2 < e.pts.length; k += 3) {{
          const [sx, sy] = v.toScreen(new V(e.pts[k], e.pts[k + 1], e.pts[k + 2]).applyMatrix4(mesh.matrix)), x = Math.round(sx), y = Math.round(sy);
          if (document.elementFromPoint(x, y) !== cv || a.idleSnap({{ clientX: x, clientY: y }}, null)?.snap) continue;
          const f = v.roundEdgeAt(x, y) || v.pickInst(x, y);
          if (f?.inst === top && f.face?.name === name) ok.push([x, y]);
        }}
      }}
      const c = ok[Math.floor(ok.length / 2)];
      return c && [c[0] - Math.floor(r.left + r.width / 2), c[1] - Math.floor(r.top + r.height / 2)];""", top, name)


def click(top, name, ctrl=False):
    off = rim(top, name)
    if not off:
        check(f"{top} {name}: a rim in sight to click", False)
        return
    canvas = d.find_element(By.CSS_SELECTOR, "#asmViewport canvas")
    ch = ActionChains(d, duration=30).move_to_element_with_offset(canvas, *off)
    ch = ch.key_down(Keys.CONTROL).click().key_up(Keys.CONTROL) if ctrl else ch.click()
    ch.perform()
    time.sleep(0.5)


def rows():
    return [x.strip() for x in js("return [...document.querySelectorAll('#asmViewport .view-suggest [data-sg]')].map(b => b.textContent)") or []]


def run_row(start):
    """The first suggestion row starting with `start` (not "+ seat"), clicked by the script -> its text."""
    return js("""const b = [...document.querySelectorAll('#asmViewport .view-suggest [data-sg]')].find(x => x.textContent.trim().startsWith(arguments[0]) && !x.textContent.includes('+'));
      if (!b) return null; b.dispatchEvent(new MouseEvent('click', { bubbles: true, detail: 1 })); return b.textContent.trim();""", start)


def coaxial(i1, f1, i2, f2):
    """Two round faces (placed part, its face) on one axis: [angle between the axes (sin), distance of the 2nd axis'
    origin from the 1st axis (mm)]."""
    return js(f"""const a = {A}, x = a.worldFace(arguments[0], arguments[1]).axis, y = a.worldFace(arguments[2], arguments[3]).axis;
      const s = x.d.clone().cross(y.d).length(), w = y.o.clone().sub(x.o), off = w.clone().sub(x.d.clone().multiplyScalar(w.dot(x.d))).length();
      return [+s.toFixed(6), +off.toFixed(4)];""", i1, f1, i2, f2)


def on_axis(r):
    return r and r[0] < 1e-5 and r[1] < 1e-3


def mid_mates():
    return js(f"return ({P}.parts.find(p => p.name === 'Mid').data.mates || []).map(m => [m.type, m.move, m.face, m.onto, m.ontoFace])")


def toasts():
    return js("return [...document.querySelectorAll('#toasts .toast')].map(t => t.textContent)") or []


def fresh_picks():
    js(f"{A}.facePicks = []; {A}.select([])")
    js("for (const t of document.querySelectorAll('#toasts .toast')) t.remove()")
    time.sleep(0.3)


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=8)
    call("new_model", name="Bushing")
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 24}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=8)
    for name, shape, h in [("Pin", {"circle": {"x": 0, "y": 0, "d": 8}}, 20), ("Base", {"rect": {"x": 0, "y": 0, "w": 260, "h": 120}}, 10)]:
        call("new_model", name=name)
        call("add_feature", type="sketch", plane="XY", shapes=[shape])
        call("add_feature", type="extrude", sketch="F1", d=h)
    time.sleep(1)
    call("new_assembly", name="Inner")
    call("insert_part", part="Plate")
    call("insert_part", part="Pin")
    call("snap_faces", type="axis", move={"part": "I2", "face": "F2:side:c1"}, onto={"part": "I1", "face": "F3:hole:0"})
    call("new_assembly", name="Mid")
    call("insert_part", part="Bushing")
    call("insert_part", part="Inner")
    call("place_part", part="I2", x=50, y=-10, z=0)
    call("new_assembly", name="Top")
    call("insert_part", part="Base")
    call("insert_part", part="Mid")
    call("place_part", part="I2", x=-70, y=10, z=10)
    call("insert_part", part="Mid")
    call("place_part", part="I3", x=40, y=10, z=10)
    wait(f"return Object.values({A}.bodies).every(b => b.body) && {A}.view.meshes.length === 3")
    js(f"{A}.view.setView('iso')")
    time.sleep(0.6)
    check(f"the demo: the pin and the hole apart {coaxial('I2', HOLE, 'I2', PIN)}", not on_axis(coaxial("I2", HOLE, "I2", PIN)))

    # two circles on two parts of one sub-assembly: Ctrl+click -> ◎ Concentric -> Mid's joint
    fresh_picks()
    t0 = time.time()
    click("I2", HOLE)
    click("I2", PIN, ctrl=True)
    picks = js(f"return {A}.facePicks.map(q => [q.inst, q.face.name])")
    keys = js(f"return {A}.selKeys()")
    check(f"Ctrl+click two circles inside Mid: both faces picked {picks}, both parts chosen {keys}", picks == [["I2", HOLE], ["I2", PIN]] and sorted(keys) == ["I2/I1", "I2/I2/I2"])
    sugg = rows()
    check(f"…the suggestions offer ◎ Concentric {sugg[:4]}", any(x.startswith("◎ Concentric") for x in sugg))
    d.save_screenshot(f"{OUT}/join1.png")
    ran = run_row("◎ Concentric")
    wait(f"return ({P}.parts.find(p => p.name === 'Mid').data.mates || []).length === 1 && !document.querySelector('#asmViewport .view-suggest')?.textContent.includes('↔ Pin')", 20)
    time.sleep(0.8)
    check(f"'{ran}': the joint is Mid's {mid_mates()}, Top keeps none ({js(f'return {A}.doc.mates.length')})",
          mid_mates() == [["axis", "I1", "F3:hole:0", "I2", "I2/F2:side:c1"]] or mid_mates() == [["axis", "I2", "I2/F2:side:c1", "I1", "F3:hole:0"]])
    check(f"…Top's own joints: none {js(f'return {A}.doc.mates.length')}", js(f"return {A}.doc.mates.length") == 0)
    check(f"…the pin on the hole's axis in this copy {coaxial('I2', HOLE, 'I2', PIN)}", on_axis(coaxial("I2", HOLE, "I2", PIN)))
    check(f"…and in the other copy of Mid {coaxial('I3', HOLE, 'I3', PIN)}", on_axis(coaxial("I3", HOLE, "I3", PIN)))
    ts = toasts()
    check(f"…the toast says where it went {ts}", any("sub-assembly Mid" in x for x in ts))
    d.save_screenshot(f"{OUT}/join2.png")
    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    wait(f"return ({P}.parts.find(p => p.name === 'Mid').data.mates || []).length === 0", 20)
    time.sleep(0.8)
    check(f"Ctrl+Z: Mid as it was {mid_mates()}, the pin off the axis again in both copies", not on_axis(coaxial("I2", HOLE, "I2", PIN)) and not on_axis(coaxial("I3", HOLE, "I3", PIN)))

    # 🔒 Mid locked for changes from here: nothing joined, said
    mid = js(f"return {P}.parts.find(p => p.name === 'Mid').id")
    js(f"{A}.toggleSubLock(arguments[0])", mid)
    fresh_picks()
    click("I2", HOLE)
    click("I2", PIN, ctrl=True)
    run_row("◎ Concentric")
    time.sleep(1)
    ts = toasts()
    check(f"Mid locked: nothing joined {mid_mates()}, said {ts[-1:]}", mid_mates() == [] and any("locked for changes from this assembly" in x for x in ts))
    js(f"{A}.toggleSubLock(arguments[0])", mid)

    # parts of two copies of Mid: Top's joint, one whole copy moves
    fresh_picks()
    click("I2", HOLE)
    click("I3", HOLE, ctrl=True)
    picks = js(f"return {A}.facePicks.map(q => [q.inst, q.face.name])")
    check(f"two bushings in the two copies: picked {picks}", picks == [["I2", HOLE], ["I3", HOLE]])
    run_row("◎ Concentric")
    wait(f"return {A}.doc.mates.length === 1", 20)
    time.sleep(0.6)
    tm = js(f"return {A}.doc.mates.map(m => [m.type, m.move, m.face, m.onto, m.ontoFace])")
    check(f"…the joint is Top's {tm}, Mid keeps none {mid_mates()}", len(tm) == 1 and tm[0][0] == "axis" and {tm[0][1], tm[0][3]} == {"I2", "I3"} and tm[0][2] == HOLE and mid_mates() == [])
    check(f"…the two holes on one axis {coaxial('I2', HOLE, 'I3', HOLE)}", on_axis(coaxial("I2", HOLE, "I3", HOLE)))

    # Mid's panel: 🔓 joints inside from here, how many it keeps
    fresh_picks()
    click("I2", HOLE)
    click("I2", PIN, ctrl=True)
    run_row("◎ Concentric")
    wait(f"return ({P}.parts.find(p => p.name === 'Mid').data.mates || []).length === 1", 20)
    fresh_picks()
    js(f"{A}.select(['I2'])")
    time.sleep(0.4)
    lock = js("return document.querySelector('#asmRight [data-a=subLock]')?.textContent || ''")
    hint = js("return document.querySelector('#asmRight .as-subj')?.textContent || ''")
    check(f"Mid's panel: {lock!r} · {hint!r}", "Joints inside it" in lock and "1 joint(s) inside Mid" in hint)
    check(f"(the run took {time.time() - t0:.1f} s)", True)
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    d.quit()
print("FAILED:" if fails or errs else "all OK", fails or errs or "")
sys.exit(1 if fails or errs else 0)
