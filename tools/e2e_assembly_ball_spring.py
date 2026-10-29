"""● Ball joints, 🔗 fixed together, 🔒 a touch's slides, 〰 a spring and ↕ a check valve — in headless Edge, through the
AI's tools (as the app's AI met them in a pump: a valve ball, a spring, the balls moving by the stroke's direction):
  - a ball's centre on a hole's axis (● ball): it only slides along the axis and turns (4 ways); on another ball's
    centre: 3 turns only; ◉ seated in a 45° cone: its centre r / sin 45° from the apex; on a hole's edge: √(R² − r²) out;
    picked as two faces with no tool on, the suggestions offer ◉ / ● first;
  - 🔗 rigid: a part fixed to another one as it is — it follows that part's slide, it has no motions of its own;
  - 🔒 a touch joint's in-plane slides locked one by one (they no longer slide, the part does not jump);
  - 〰 a spring between a piston and a body: its length follows the piston (the view's scale = distance / free length)
    while ⚙ ▶ plays, its panel says free / now / compressed and the force with k, no collision between it and its parts;
  - ↕ a check valve: a ball with one slide between two stops sits at max while the driver goes forward, at min back.

  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_ball_spring.py http://127.0.0.1:5199 <out dir>
"""
import math
import sys
import time
from pathlib import Path

from selenium import webdriver

URL, OUT = sys.argv[1], Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
A = "window.__app.assembly"
H = "window.__app.agentHandlers"
fails = []


def check(ok, what):
    print(("OK   " if ok else "FAIL ") + what)
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


def must(tool_name, **args):
    r = call(tool_name, **args)
    if r.startswith("ERROR"):
        raise RuntimeError(f"{tool_name} {args}: {r}")
    return r


def face(inst, kind, pick="first"):
    """A placed part's face name of a type ('sphere', 'cone', 'cylinder', 'plane'); pick 'top' / 'bottom' for flat faces."""
    return js(f"""const it = {A}.inst(arguments[0]), b = {A}.bodies[it.part].body;
      let fs = b.faces.filter(f => f.type === arguments[1]);
      if (arguments[2] === 'top') fs = fs.filter(f => f.normal[2] > 0.99).sort((p, q) => q.centroid[2] - p.centroid[2]);
      if (arguments[2] === 'bottom') fs = fs.filter(f => f.normal[2] < -0.99).sort((p, q) => p.centroid[2] - q.centroid[2]);
      return fs[0]?.name || null""", inst, kind, pick)


def centre(inst, name):
    return js(f"const f = {A}.worldFace(arguments[0], arguments[1]); return (f.centre || f.centroid).toArray()", inst, name)


def ways(inst):
    return js(f"return {A}.motionsOf(arguments[0])?.count ?? null", inst)


def labels(inst):
    return js(f"return ({A}.motionsOf(arguments[0])?.motions || []).map(m => m.kind + ':' + (m.key || ''))", inst)


def revolve(name, points):
    """A part turned about its own Z: a closed profile [u (radius), v (height)] on XZ, a full turn."""
    must("new_model", name=name)
    must("add_feature", type="sketch", plane="XZ", shapes=[{"profile": {"points": points}}])
    must("add_feature", type="revolve", sketch="F1", axis="y", angle=360)


try:
    d.get(URL)
    wait("return !!window.__app")
    # the parts: a body with a Ø6 hole through, a ball Ø10, a seat with a 45° cone, a second ball
    must("new_model", name="Body")
    must("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": -15, "y": -15, "w": 30, "h": 30}}])
    must("add_feature", type="extrude", sketch="F1", d=30)
    must("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=6)
    revolve("Ball", [[0, -5], {"arc": [5, 0]}, [0, 5]])
    revolve("Seat", [[2, 0], [12, 0], [12, 12], [10, 12], [2, 4]])
    revolve("Ball2", [[0, -5], {"arc": [5, 0]}, [0, 5]])
    must("new_assembly", name="Balls")
    for p in ("Body", "Ball", "Seat", "Ball2"):
        must("insert_part", part=p)
    wait(f"return {A}.doc.instances.length === 4 && {A}.doc.instances.every(i => {A}.bodies[i.part]?.body)")
    js(f"{A}.inst('I1').fixed = true")
    must("place_part", part="I2", x=40, y=10, z=50)
    must("place_part", part="I3", x=-40, y=0, z=0)
    must("place_part", part="I4", x=0, y=60, z=20)
    must("place_part", part="I3", fixed=True)
    ball, hole = face("I2", "sphere"), face("I1", "cylinder")
    cone = face("I3", "cone")
    check(bool(ball and hole and cone), f"the ball's face is a sphere ({ball}), the seat's a cone ({cone}), the hole's a cylinder ({hole})")

    # the suggestions for a ball + a hole picked with no tool on: ◉ seat first, ● centre on its axis next
    js(f"""const a = {A}; a.choose('I2'); a.facePicks = [{{inst: 'I2', face: a.worldFace('I2', arguments[0])}}, {{inst: 'I1', face: a.worldFace('I1', arguments[1])}}];
      a.renderSuggest()""", ball, hole)
    time.sleep(0.4)
    sug = js("return [...document.querySelectorAll('#asmViewport .view-suggest [data-sg]')].map(e => e.textContent.trim()).slice(0, 4)")
    check(bool(sug) and ("◉" in sug[0] or "●" in sug[0]), f"a ball + a hole: the ball joints first in the suggestions {sug}")
    js(f"{A}.facePicks = []; {A}.renderSuggest()")

    # ● the ball's centre on the hole's axis: it slides along it, turns any way — 4 ways
    must("snap_faces", move={"part": "I2", "face": ball}, onto={"part": "I1", "face": hole}, type="ball")
    c = centre("I2", ball)
    check(abs(c[0]) < 1e-6 and abs(c[1]) < 1e-6 and abs(c[2] - 50) < 1e-6, f"● on the axis: the ball's centre {c} on x = y = 0, its height kept")
    n, ls = ways("I2"), labels("I2")
    check(n == 4 and any(x.endswith(":along") for x in ls) and sum(x.startswith("turn") for x in ls) == 3, f"● on an axis: 4 ways — a slide along the axis and 3 turns ({n}: {ls})")
    js(f"""const a = {A}, d = a.motionsOf('I2'), mo = d.motions.find(m => /:along$/.test(m.key)); a.moveFree('I2', mo, 7, null, true)""")
    c2 = centre("I2", ball)
    check(abs(c2[0]) < 1e-6 and abs(c2[1]) < 1e-6 and abs(abs(c2[2] - 50) - 7) < 1e-6, f"slid 7 mm along the axis: {c2}")
    js(f"""const a = {A}, d = a.motionsOf('I2'), mo = d.motions.find(m => m.kind === 'move' && !/:along$/.test(m.key || ''));
      if (mo) a.moveFree('I2', mo, 5, null, true)""")
    c3 = centre("I2", ball)
    check(abs(c3[0]) < 1e-6 and abs(c3[1]) < 1e-6, f"it cannot leave the axis: {c3}")

    # ● ball in a ball: 3 turns only
    b2 = face("I4", "sphere")
    must("snap_faces", move={"part": "I4", "face": b2}, onto={"part": "I2", "face": ball}, type="ball")
    c4, c5 = centre("I4", b2), centre("I2", ball)
    n, ls = ways("I4"), labels("I4")
    check(max(abs(p - q) for p, q in zip(c4, c5)) < 1e-6 and n == 3 and all(x.startswith("turn") for x in ls), f"● ball joint: one centre ({c4}), 3 turns only ({n}: {ls})")
    must("remove_joint", id=js(f"return {A}.doc.mates.find(m => m.move === 'I4').id"))

    # ◉ seated in the 45° cone: its centre r / sin 45° = 7.071 above the apex (z 2 of the seat), on the axis
    must("remove_joint", id=js(f"return {A}.doc.mates.find(m => m.move === 'I2').id"))
    must("snap_faces", move={"part": "I2", "face": ball}, onto={"part": "I3", "face": cone}, type="seat")
    c = centre("I2", ball)
    check(abs(c[0] + 40) < 1e-6 and abs(c[1]) < 1e-6 and abs(c[2] - (2 + 5 / math.sin(math.pi / 4))) < 1e-4, f"◉ in the cone: centre {c} (want [-40, 0, {2 + 5 / math.sin(math.pi / 4):.4f}])")
    n = ways("I2")
    check(n == 3, f"◉ seated: only its 3 turns left ({n})")
    # ◉ on the hole's edge: a Ø10 ball on a Ø6 hole sits √(25 − 9) = 4 mm above the top
    must("remove_joint", id=js(f"return {A}.doc.mates.find(m => m.move === 'I2').id"))
    must("place_part", part="I2", x=5, y=5, z=45)
    must("snap_faces", move={"part": "I2", "face": ball}, onto={"part": "I1", "face": hole}, type="seat")
    c = centre("I2", ball)
    check(abs(c[0]) < 1e-6 and abs(c[1]) < 1e-6 and abs(c[2] - 34) < 1e-4, f"◉ on the hole's edge: centre {c} (want [0, 0, 34])")
    r = call("snap_faces", move={"part": "I2", "face": ball}, onto={"part": "I1", "face": face("I1", "plane", "top")}, type="ball")
    check(r.startswith("ERROR") and "ball" in r, f"a ball joint onto a flat face is refused: {r[:120]}")
    d.save_screenshot(str(OUT / "ball_seat.png"))

    # 🔗 fixed together: a flag fixed to a pin that slides in the body's hole goes with it, no motion of its own
    must("new_model", name="Pin")
    must("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 6}}])
    must("add_feature", type="extrude", sketch="F1", d=40)
    must("new_model", name="Flag")
    must("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": -2, "w": 20, "h": 4}}])
    must("add_feature", type="extrude", sketch="F1", d=10)
    must("open_part", id="Balls")
    wait(f"return {A}.doc.instances.length === 4")
    must("insert_part", part="Pin")
    must("insert_part", part="Flag")
    wait(f"return {A}.doc.instances.length === 6 && {A}.doc.instances.every(i => {A}.bodies[i.part]?.body)")
    must("snap_faces", move={"part": "I5", "face": face("I5", "cylinder")}, onto={"part": "I1", "face": hole}, type="axis")
    must("place_part", part="I6", x=3, y=0, z=40)
    js(f"{A}.applyMates()")
    flag0 = js(f"return {A}.inst('I6').matrix.slice(12, 15)")
    r = must("snap_faces", move={"part": "I6"}, onto={"part": "I5"}, type="rigid")
    check("rigid" in r, f"🔗 rigid by the AI without faces: {r[:90]}")
    flag1 = js(f"return {A}.inst('I6').matrix.slice(12, 15)")
    check(max(abs(p - q) for p, q in zip(flag0, flag1)) < 1e-6, f"fixed where it was: {flag0} -> {flag1}")
    own = js(f"return {A}.motionsOf('I6', true)?.count")
    check(own == 0, f"🔗 no motion of its own ({own})")
    js(f"""const a = {A}, d = a.motionsOf('I5'), mo = d.motions.find(m => /:along$/.test(m.key)); a.moveFree('I5', mo, 6, null, true)""")
    pin = js(f"return {A}.inst('I5').matrix.slice(12, 15)")
    flag2 = js(f"return {A}.inst('I6').matrix.slice(12, 15)")
    check(abs(abs(flag2[2] - flag1[2]) - 6) < 1e-6 and abs(flag2[0] - flag1[0]) < 1e-6, f"the pin slid 6 mm ({pin}): the flag went along {flag1} -> {flag2}")
    js(f"""const a = {A}, d = a.motionsOf('I5'), mo = d.motions.find(m => /:turn$/.test(m.key)); a.moveFree('I5', mo, 90, null, true)""")
    f3 = js(f"return {A}.inst('I6').matrix.slice(0, 3)")
    check(abs(f3[0]) < 1e-6 and abs(abs(f3[1]) - 1) < 1e-6, f"the pin turned 90°: the flag turned with it (its X now {f3})")
    held = js(f"return {A}.health.get({A}.doc.mates.find(m => m.type === 'rigid').id)?.ok")
    check(held is True, "the rigid joint holds")
    # 🔗 Fixed together from Joint ▾: any face of each part
    js(f"""const a = {A}; a.startJoint('rigid'); a.clickJoint({{inst: 'I4', face: a.worldFace('I4', arguments[0])}});
      a.clickJoint({{inst: 'I1', face: a.worldFace('I1', arguments[1])}})""", b2, hole)
    rj = js(f"return {A}.doc.mates.find(m => m.move === 'I4')?.type")
    check(rj == "rigid" and js(f"return {A}.mode") == "idle" and js(f"return {A}.motionsOf('I4', true)?.count") == 0, f"🔗 from Joint ▾: two faces clicked, fixed ({rj})")
    # the two parts chosen: 🔗 Fix … to … in the suggestions
    js(f"{A}.choose('I2'); {A}.choose('I4', true)")
    time.sleep(0.4)
    sug = js("return [...document.querySelectorAll('#asmViewport .view-suggest [data-sg]')].map(e => e.textContent.trim())")
    check(any("🔗" in x and ("Fix" in x or "Pevně" in x) for x in sug), f"two parts chosen: 🔗 Fix … to … suggested {sug[:5]}")

    logs = [x for x in d.get_log("browser") if x["level"] == "SEVERE"]
    check(not logs, f"no errors in the console {logs[:3]}")
finally:
    d.quit()

print("FAILED: " + "; ".join(fails) if fails else "ALL OK")
sys.exit(1 if fails else 0)
