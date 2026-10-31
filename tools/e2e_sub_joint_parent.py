"""A sub-assembly's own joints hold in the assembly it is placed in, in headless Edge — the owner's gas strut (2026-11-01:
"Plynová vzpěra 175N_oa_6" in "Sestava brány": its rod on the body's axis in its own tab, beside it in the parent, no
joint ⚠ not held, rigid or moving alike). A "Strut" (a rod with an eye, a body with an eye, the body put 4 mm off the
rod's axis as an imported STEP may have it) placed in "Gate" on two pins, its rod's eye on the first one:
- ◎ Concentric body ↔ rod made from Gate (snap_faces with nested keys): Strut's own joint, the body on the rod's axis
  in Gate and in Strut's tab;
- Gate's joint of the body's eye onto the second pin (a part that moves inside Strut): the loop through both levels
  closed — the strut turns about the first pin and pulls out, the body still on the rod's axis, every joint held;
- 🧱 rigid, ⚙ moving again: the body on the axis;
- Strut's joint changed in its own tab (its slide locked: too short to reach the pin): back in Gate the body stays on
  the rod's axis and Gate's joint on the pin is ⚠ not held (before: the body pulled off the axis onto the pin, nothing
  said);
- the owner's project, when the server's data has it ("Sestava ICT M1556"): in "Sestava brány" the strut's rod on its
  body's axis.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_sub_joint_parent.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_big_assembly import Builder  # noqa: E402

URL, OUT = sys.argv[1].rstrip("/"), Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
A = "window.__app.assembly"
P = "window.__app.project"
ROD, EYE = "F5:side:c1", "F3:hole:0"  # (the rod's / body's round face along the strut, the eye's hole)
fails = []


def check(what, ok):
    print(("OK  " if ok else "FAIL"), what)
    if not ok:
        fails.append(what)


b = Builder(URL)
d, js = b.d, b.js


def coaxial(i1, f1, i2, f2):
    """Two round faces (placed part, its face) on one axis: [sin of the angle between the axes, distance of the 2nd
    axis' origin from the 1st axis (mm)]."""
    return js(f"""const a = {A}, x = a.worldFace(arguments[0], arguments[1]).axis, y = a.worldFace(arguments[2], arguments[3]).axis;
      const s = x.d.clone().cross(y.d).length(), w = y.o.clone().sub(x.o), off = w.clone().sub(x.d.clone().multiplyScalar(w.dot(x.d))).length();
      return [+s.toFixed(6), +off.toFixed(4)];""", i1, f1, i2, f2)


def on_axis(r):
    return bool(r) and r[0] < 1e-5 and r[1] < 1e-3


def built():
    b.wait(f"const a = {A}; return a.active && a.doc.instances.length > 0 && a.doc.instances.every((i) => a.bodyOf(i)?.body)", 600)
    time.sleep(0.8)


def model(name, steps):
    """A 3D model from add_feature steps, its last one built (a sketch's own answer may come before its build)."""
    b.call("new_model", name=name)
    for s in steps:
        b.call("add_feature", **s)
    b.wait("return !!window.__app.modeler.result?.body && !window.__app.modeler.inflight", 120)


def go(name):
    b.run(f"await {P}.switchTo({P}.parts.find((p) => p.name === arguments[0]).id);", name)
    built()


def unmet():
    return js(f"return {A}.unmet().map((m) => m.id)")


def strut_mates():
    return js(f"return ({P}.parts.find((p) => p.name === 'Strut').data.mates || []).map((m) => [m.type, m.move, m.face, m.onto, m.ontoFace])")


try:
    b.fresh()
    eye = [{"type": "sketch", "plane": "XY", "shapes": [{"rect": {"x": -10, "y": -10, "w": 20, "h": 20}}]},
           {"type": "extrude", "sketch": "F1", "d": 10},
           {"type": "hole", "face": "F2:end", "points": [[0, 0]], "d": 8}]
    model("Rod", eye + [{"type": "sketch", "plane": "XZ", "shapes": [{"circle": {"x": 0, "y": 5, "d": 6}}]}, {"type": "extrude", "sketch": "F4", "d": 120}])
    model("Body", eye + [{"type": "sketch", "plane": "XZ", "shapes": [{"circle": {"x": 0, "y": 5, "d": 15}}]}, {"type": "extrude", "sketch": "F4", "d": 80}])
    model("Pin", [{"type": "sketch", "plane": "XY", "shapes": [{"circle": {"x": 0, "y": 0, "d": 8}}]}, {"type": "extrude", "sketch": "F1", "d": 30}])
    ids = js(f"return Object.fromEntries({P}.parts.map((p) => [p.name, p.id]))")
    # Strut: the rod (📌) along -Y from its eye at the origin; the body turned about Z, its eye 170 mm down and 4 mm off
    # the rod's axis (where an imported STEP may put it)
    b.assembly("Strut")
    b.put("I1", ids["Rod"], [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1], fixed=True)
    b.put("I2", ids["Body"], [-1, 0, 0, 0, 0, -1, 0, 0, 0, 0, 1, 0, 4, -170, 0, 1])
    b.done()
    # Gate: two pins (📌), the strut's rod eye on the first one
    b.assembly("Gate")
    b.put("I1", ids["Pin"], [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, -10, 1], fixed=True)
    b.put("I2", ids["Pin"], [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 60, -150, -10, 1], fixed=True)
    b.put("I3", js(f"return {P}.parts.find((p) => p.name === 'Strut').id"), [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1])
    b.mate("axis", "I3", f"I1/{EYE}", "I1", "F2:side:c1")
    b.done()
    built()
    check(f"the demo: the body off the rod's axis {coaxial('I3', f'I1/{ROD}', 'I3', f'I2/{ROD}')}", not on_axis(coaxial("I3", f"I1/{ROD}", "I3", f"I2/{ROD}")))

    # ◎ Concentric body ↔ rod, made from Gate: Strut's own joint
    r = b.call("snap_faces", type="axis", move={"part": "I3/I2", "face": ROD}, onto={"part": "I3/I1", "face": ROD})
    time.sleep(1)
    check(f"snap_faces I3/I2 ↔ I3/I1 from Gate: {r[:90]!r} -> Strut's joint {strut_mates()}", "saved in the sub-assembly Strut" in r and len(strut_mates()) == 1)
    check(f"…in Gate the body on the rod's axis {coaxial('I3', f'I1/{ROD}', 'I3', f'I2/{ROD}')}", on_axis(coaxial("I3", f"I1/{ROD}", "I3", f"I2/{ROD}")))
    go("Strut")
    check(f"…and in Strut's tab {coaxial('I1', ROD, 'I2', ROD)}", on_axis(coaxial("I1", ROD, "I2", ROD)))
    go("Gate")

    # Gate's joint of the body's eye onto the second pin: the loop through both levels closes
    r = b.call("snap_faces", type="axis", move={"part": "I3/I2", "face": EYE}, onto={"part": "I2", "face": "F2:side:c1"})
    time.sleep(1)
    gm = js(f"return {A}.doc.mates.map((m) => [m.id, m.move, m.face, m.onto])")
    check(f"the body's eye onto the 2nd pin: Gate's joint {gm}", len(gm) == 2 and gm[1][1] == "I3" and gm[1][2] == f"I2/{EYE}")
    rb, e1, e2 = coaxial("I3", f"I1/{ROD}", "I3", f"I2/{ROD}"), coaxial("I1", "F2:side:c1", "I3", f"I1/{EYE}"), coaxial("I2", "F2:side:c1", "I3", f"I2/{EYE}")
    check(f"…the strut turned and pulled out: body on the rod's axis {rb}, rod's eye on pin 1 {e1}, body's eye on pin 2 {e2}, not held {unmet()}",
          on_axis(rb) and on_axis(e1) and on_axis(e2) and unmet() == [])
    d.save_screenshot(str(OUT / "subjoint-closed.png"))

    # 🧱 rigid, ⚙ moving again
    b.call("place_part", part="I3", rigid=True)
    time.sleep(0.5)
    check(f"🧱 rigid: the body on the rod's axis {coaxial('I3', f'I1/{ROD}', 'I3', f'I2/{ROD}')}", js(f"return {A}.inst('I3').rigid === true") and on_axis(coaxial("I3", f"I1/{ROD}", "I3", f"I2/{ROD}")))
    b.call("place_part", part="I3", rigid=False)
    time.sleep(0.5)
    check(f"⚙ moving again: the body on the rod's axis {coaxial('I3', f'I1/{ROD}', 'I3', f'I2/{ROD}')}, not held {unmet()}",
          on_axis(coaxial("I3", f"I1/{ROD}", "I3", f"I2/{ROD}")) and unmet() == [])

    # Strut's joint changed in its own tab: its slide locked 40 mm in — too short for the 2nd pin
    go("Strut")
    b.run(f"const a = {A}, m = a.doc.mates[0]; m.dist = 40; m.side = m.side || 1; a.applyMates(); a.commit();")
    time.sleep(0.5)
    check(f"Strut's tab: its joint with a distance, the body on the axis {coaxial('I1', ROD, 'I2', ROD)}", on_axis(coaxial("I1", ROD, "I2", ROD)) and unmet() == [])
    go("Gate")
    rb = coaxial("I3", f"I1/{ROD}", "I3", f"I2/{ROD}")
    check(f"back in Gate: the body stays on the rod's axis {rb}, Gate's joint on the pin ⚠ not held {unmet()}", on_axis(rb) and unmet() == ["J2"])
    check(f"…the status says so: {js(f'return {A}.$(\".m-status\").textContent')!r}", "not held" in js(f"return {A}.$('.m-status').textContent"))
    b.call("place_part", part="I3", rigid=True)
    time.sleep(0.5)
    check(f"…🧱 rigid: still on the axis {coaxial('I3', f'I1/{ROD}', 'I3', f'I2/{ROD}')}", on_axis(coaxial("I3", f"I1/{ROD}", "I3", f"I2/{ROD}")))
    d.save_screenshot(str(OUT / "subjoint-short.png"))

    # the owner's project, when this server's data has it
    owner = [p for p in json.loads(urllib.request.urlopen(f"{URL}/api/projects").read()).get("projects", []) if p.get("name") == "Sestava ICT M1556"]
    if owner:
        pid = max(owner, key=lambda p: p.get("time", 0))["id"]
        d.get(f"{URL}/?project={pid}")
        b.wait(f"return !!window.__app && {P}.parts.some((p) => p.name === 'Sestava brány')", 900)
        go("Sestava brány")
        rows = js(f"""const a = {A}, sub = {P}.parts.find((p) => p.name === 'Plynová vzpěra 175N_oa_6'), it = a.doc.instances.find((i) => i.part === sub?.id);
          const own = sub?.data.instances || [], by = (s) => own.find((i) => a.partName(i.part).includes(s))?.id;
          return it ? [it.id, by('PÍSTNICE'), by('TĚLO')] : null;""")
        if rows:
            r = coaxial(rows[0], f"{rows[1]}/F1:f0", rows[0], f"{rows[2]}/F1:f3")
            check(f"the owner's Sestava brány: the strut's rod on its body's axis {r}", on_axis(r))
        else:
            check("the owner's project: the strut placed in Sestava brány", False)
    else:
        print("(the owner's project is not in this server's data: skipped)")
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    b.quit()
print("FAILED:" if fails or errs else "all OK", fails or errs or "")
sys.exit(1 if fails or errs else 0)
