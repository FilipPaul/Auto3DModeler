"""A mechanism two levels down driven from the top, in headless Edge — the owner's gate (2026-11-01: "Sestava ICT M1556"
→ "Sestava brány" → "Sestava pant P" → the hinge's leaf; in the gate's own tab "Otevírání brány" opens it, in the top
one ⚙ Mechanism offered only the struts' turns, which did not move it, and drive_mechanism timed out).
A "Hinge" (a 📌 pin, a leaf turning on it), a "Strut" (a rod, a body sliding on it), a "Gate" (the hinge 📌, a bracket
pin 📌, the strut: its rod's eye on the bracket pin, its body's eye on the leaf's far hole — a loop through both levels,
named "Otevírání" and driven by the leaf's turn) and a "Machine" with the gate placed in it:
- ⚙ Mechanism of Machine lists "Otevírání (v Gate)", driven by the leaf two levels down (I1/I1/I2);
- its slider / drive_mechanism (a nested driver path too) turns the leaf by the step asked, the strut follows: its rod's
  eye on the bracket pin, its body's eye on the leaf, the body on the rod's axis — every joint held;
- the places kept on the placement (`inner`: "I1/I2" for the leaf inside the hinge), Gate's and Hinge's own documents
  unchanged; undo turns it back; 🧱 rigid then ⚙ moving again keeps the pose;
- the owner's project, when the server's data has it: in "Sestava ICT M1556" the gate opens 90° from the top, its struts
  joined, within a few seconds.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_deep_mechanism.py http://127.0.0.1:5199 <out dir>
"""
import json
import math
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_big_assembly import Builder, T  # noqa: E402

URL, OUT = sys.argv[1].rstrip("/"), Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
A = "window.__app.assembly"
P = "window.__app.project"
PIN, EYE, ROD = "F2:side:c1", "F3:hole:0", "F5:side:c1"  # (a pin's round side, an eye's hole, the rod's / body's round side)
fails = []


def check(what, ok):
    print(("OK  " if ok else "FAIL"), what)
    if not ok:
        fails.append(what)


b = Builder(URL)
d, js = b.d, b.js


def built():
    b.wait(f"const a = {A}; return a.active && a.doc.instances.length > 0 && a.doc.instances.every((i) => a.bodyOf(i)?.body)", 900)
    time.sleep(0.8)


def go(name):
    t = time.time()
    b.run(f"await {P}.switchTo({P}.parts.find((p) => p.name === arguments[0]).id);", name)
    built()
    return time.time() - t


def coaxial(i1, f1, i2, f2):
    """Two round faces (placed part, its face) on one axis: [sin of the angle between the axes, distance of the 2nd
    axis' origin from the 1st axis (mm)]."""
    return js(f"""const a = {A}, x = a.worldFace(arguments[0], arguments[1]).axis, y = a.worldFace(arguments[2], arguments[3]).axis;
      const s = x.d.clone().cross(y.d).length(), w = y.o.clone().sub(x.o), off = w.clone().sub(x.d.clone().multiplyScalar(w.dot(x.d))).length();
      return [+s.toFixed(6), +off.toFixed(4)];""", i1, f1, i2, f2)


def on_axis(r):
    return bool(r) and r[0] < 1e-5 and r[1] < 1e-3


def leaf():
    """The leaf's angle in Machine (degrees): its far hole about the hinge pin."""
    o, h = js(f"return [{A}.worldFace('I1', 'I1/I1/{PIN}').axis.o.toArray(), {A}.worldFace('I1', 'I1/I2/F3:hole:1').axis.o.toArray()]")
    return math.degrees(math.atan2(h[1] - o[1], h[0] - o[0]))


def strut_held(what):
    r = [coaxial("I1", f"I2/{PIN}", "I1", f"I3/I1/{EYE}"), coaxial("I1", "I1/I2/F3:hole:1", "I1", f"I3/I2/{EYE}"), coaxial("I1", f"I3/I1/{ROD}", "I1", f"I3/I2/{ROD}")]
    miss = js(f"const a = {A}, fl = a.flatAsm(); return [...a.unmet().map((m) => m.id), ...(fl ? fl.unmet().map((m) => m.id) : [])]")
    check(f"{what}: the strut's rod eye on the bracket pin {r[0]}, its body's eye on the leaf {r[1]}, the body on the rod's axis {r[2]}, not held {miss}",
          all(on_axis(x) for x in r) and not miss)


def doc(name):
    return json.dumps(next(p for p in js(f"return {P}.toJSON()")["parts"] if p.get("name") == name)["assembly"]["instances"])


def mech():
    js(f"{A}.mech.render()")
    return js(f"return {A}.mech.list.map((m) => ({{ name: m.name, driver: m.driver && m.driver.part, key: m.driver && m.driver.mo.key, min: m.min, max: m.max, parts: m.parts }}))")


try:
    b.fresh()
    js("localStorage.setItem('auto3d-lang', 'cs')")
    b.fresh()
    eye = [{"type": "sketch", "plane": "XY", "shapes": [{"rect": {"x": -10, "y": -10, "w": 20, "h": 20}}]},
           {"type": "extrude", "sketch": "F1", "d": 10},
           {"type": "hole", "face": "F2:end", "points": [[0, 0]], "d": 8}]
    b.model("Rod", eye + [{"type": "sketch", "plane": "XZ", "shapes": [{"circle": {"x": 0, "y": 5, "d": 6}}]}, {"type": "extrude", "sketch": "F4", "d": 120}])
    b.model("Body", eye + [{"type": "sketch", "plane": "XZ", "shapes": [{"circle": {"x": 0, "y": 5, "d": 15}}]}, {"type": "extrude", "sketch": "F4", "d": 80}])
    b.model("Pin", [{"type": "sketch", "plane": "XY", "shapes": [{"circle": {"x": 0, "y": 0, "d": 8}}]}, {"type": "extrude", "sketch": "F1", "d": 30}])
    # the leaf: 160 × 20, its holes at x = 0 (on the hinge pin) and x = 130 (the strut's body) — points from its middle
    b.model("Leaf", [{"type": "sketch", "plane": "XY", "shapes": [{"rect": {"x": -10, "y": -10, "w": 160, "h": 20}}]},
                     {"type": "extrude", "sketch": "F1", "d": 10},
                     {"type": "hole", "face": "F2:end", "points": [[-70, 0], [60, 0]], "d": 8}])
    ids = js(f"return Object.fromEntries({P}.parts.map((p) => [p.name, p.id]))")
    b.assembly("Hinge")  # the pin 📌 (down to z = -10), the leaf turning on it
    b.put("I1", ids["Pin"], T(0, 0, -10), fixed=True)
    b.put("I2", ids["Leaf"], T(0, 0, 0))
    b.mate("axis", "I2", EYE, "I1", PIN)
    b.done()
    b.assembly("Strut")  # the rod 📌 along -Y from its eye, the body sliding on it, its eye 170 mm down
    b.put("I1", ids["Rod"], T(0, 0, 0), fixed=True)
    b.put("I2", ids["Body"], [-1, 0, 0, 0, 0, -1, 0, 0, 0, 0, 1, 0, 0, -170, 0, 1])
    b.mate("axis", "I2", ROD, "I1", ROD)
    b.done()
    ids = js(f"return Object.fromEntries({P}.parts.map((p) => [p.name, p.id]))")
    b.assembly("Gate")  # the hinge 📌, the bracket pin 📌, the strut between the pin and the leaf's far hole
    b.put("I1", ids["Hinge"], T(0, 0, 0), fixed=True)
    b.put("I2", ids["Pin"], T(60, -160, -10), fixed=True)
    b.put("I3", ids["Strut"], T(60, -160, 0))
    b.mate("axis", "I3", f"I1/{EYE}", "I2", PIN)
    b.mate("axis", "I3", f"I2/{EYE}", "I1", "I2/F3:hole:1")
    b.done()
    built()
    b.run(f"const a = {A}; a.doc.mechs = [{{ parts: ['I1/I2', 'I3', 'I3/I2'], name: 'Otevírání', drive: {{ part: 'I1/I2', key: 'I1/J1:turn' }} }}]; a.commit();")
    gm = mech()
    check(f"Gate's own mechanism, driven by the hinge's leaf: {gm}", any(m["name"] == "Otevírání" and m["driver"] == "I1/I2" for m in gm))
    gate0, hinge0 = doc("Gate"), doc("Hinge")
    ids = js(f"return Object.fromEntries({P}.parts.map((p) => [p.name, p.id]))")

    b.assembly("Machine")
    b.put("I1", ids["Gate"], T(100, 50, 0), fixed=True)
    b.done()
    built()
    ms = mech()
    m = next((x for x in ms if x["name"].startswith("Otevírání")), None)
    check(f"Machine's ⚙ Mechanism: the gate's own one, one driver two levels down: {ms}", m is not None and m["driver"] == "I1/I1/I2" and m["key"] == "I1/I1/J1:turn" and "(v Gate)" in m["name"])
    check("…and nothing else (the strut's own turn is part of it)", len(ms) == 1)

    # driven from the top: the leaf turns by the step asked, the strut follows
    r = b.call("drive_mechanism", mechanism="I1", to=0)
    a1 = leaf()
    turn = js(f"return {A}.flatAsm().motionsOf('I1/I1/I2').motions.findIndex((m) => /:turn$/.test(m.key))")  # (its turn, not its slide along the pin)
    t = time.time()
    r = b.call("drive_mechanism", mechanism="I1", driver={"part": "I1/I1/I2", "motion": turn}, to=30)
    dt = time.time() - t
    a2 = leaf()
    check(f"drive_mechanism (nested driver) to 30°: the leaf {a1:.2f}° -> {a2:.2f}° in {dt:.1f} s ({r[:100]!r})", abs(abs(a2 - a1) - 30) < 0.5 and dt < 10)
    strut_held("at 30°")
    inner = js(f"return {A}.inst('I1').inner || null")
    check(f"kept on the placement: inner {sorted(inner or {})}", bool(inner) and "I1/I2" in inner and "I3" in inner and "I3/I2" in inner)
    check("Gate's and Hinge's own documents unchanged", doc("Gate") == gate0 and doc("Hinge") == hinge0)
    k = next(i for i, x in enumerate(mech()) if x["name"].startswith("Otevírání"))
    js(f"""const s = document.querySelectorAll('[data-mcv="{k}"]')[0]; s.value = 55; s.dispatchEvent(new Event('input')); s.dispatchEvent(new Event('change'))""")
    time.sleep(1)
    a3 = leaf()
    check(f"⚙ Mechanism's slider to 55°: the leaf {a3:.2f}° ({a3 - a1:.2f}° from 0)", abs(abs(a3 - a1) - 55) < 0.5)
    strut_held("at 55°")
    d.save_screenshot(str(OUT / "deepmech-55.png"))

    js(f"{A}.history.go(-1)")
    time.sleep(1.5)
    check(f"undo: back at 30° ({leaf():.2f}°)", abs(leaf() - a2) < 0.5)
    js(f"{A}.history.go(1)")
    time.sleep(1.5)
    b.call("place_part", part="I1", rigid=True)
    time.sleep(0.5)
    check(f"🧱 rigid: the pose kept ({leaf():.2f}°), no mechanism inside {mech()}", abs(leaf() - a3) < 0.5 and not mech())
    b.call("place_part", part="I1", rigid=False)
    time.sleep(0.5)
    check(f"⚙ moving again: the pose kept ({leaf():.2f}°)", abs(leaf() - a3) < 0.5)
    strut_held("moving again")

    # the owner's project, when this server's data has it
    owner = [p for p in json.loads(urllib.request.urlopen(f"{URL}/api/projects").read()).get("projects", []) if p.get("name") == "Sestava ICT M1556"]
    if owner:
        pid = max(owner, key=lambda p: p.get("time", 0))["id"]
        d.get(f"{URL}/?project={pid}")
        b.wait(f"return !!window.__app && {P}.parts.some((p) => p.name === 'Sestava ICT M1556')", 900)
        go("Sestava ICT M1556")
        gate = js(f"const s = {P}.parts.find((p) => p.name === 'Sestava brány'); return !!(s && (s.data?.mechs || []).length)")
    if owner and not gate:
        print("(a \"Sestava ICT M1556\" without the owner's gate mechanism — a plain STEP import: skipped)")
    elif owner:
        it = js(f"const a = {A}, sub = {P}.parts.find((p) => p.name === 'Sestava brány'); return a.doc.instances.find((i) => i.part === sub.id).id")
        ms = mech()
        m = next((x for x in ms if x["name"].startswith("Otevírání brány")), None)
        check(f"the owner's ICT: ⚙ Mechanism offers “Otevírání brány” driven by the hinge two levels down: {m and (m['name'], m['driver'], m['min'], m['max'])}",
              m is not None and m["driver"].startswith(f"{it}/") and m["driver"].count("/") == 2)
        if m:
            frame = js(f"const fl = {A}.flatAsm(); return fl.doc.mechs.length && fl.doc.instances.find((x) => x.id.startsWith('{it}/') && {P}.parts.find((p) => p.id === x.part)?.name === 'Sestava rámu')?.id")
            b.call("drive_mechanism", mechanism=it, to=m["min"])
            x0 = js(f"return {A}.flatAsm().inst(arguments[0]).matrix.slice(0, 3)", frame)
            t = time.time()
            r = b.call("drive_mechanism", mechanism=it, driver={"part": m["driver"], "motion": 0}, to=m["max"])
            dt = time.time() - t
            x1 = js(f"return {A}.flatAsm().inst(arguments[0]).matrix.slice(0, 3)", frame)
            turn = math.degrees(math.acos(max(-1, min(1, sum(p * q for p, q in zip(x0, x1))))))
            miss = js(f"const a = {A}; return [...a.unmet().map((m) => m.id), ...a.flatAsm().unmet().map((m) => m.id)]")
            check(f"…driven from the top ({m['min']} -> {m['max']}°): the gate's frame {frame} turned {turn:.1f}° in {dt:.1f} s, not held {miss}", abs(turn - 90) < 1 and dt < 10 and not miss)
            d.save_screenshot(str(OUT / "deepmech-ict.png"))
    else:
        print("(the owner's project is not in this server's data: skipped)")
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    b.quit()
print("FAILED:" if fails or errs else "all OK", fails or errs or "")
sys.exit(1 if fails or errs else 0)
