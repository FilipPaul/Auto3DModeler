"""Build the 🎬 demo projects (demos/*.a3d.json) through the app, as a user (or the AI) would: 3D models from sketches
and extrudes, an assembly with joints, the motions named in Czech, the mechanism's driver and name set — then the
project as the app saves it, with its "demo" record (auto3d/demos.py).

  PYTHONIOENCODING=utf-8 py tools/make_demos.py http://127.0.0.1:5199 [<out folder, default demos/ (or -)>] [<name> …]

  klikovy-mechanismus      a crank – rod – slider (r 25, L 100)
  ctyrkloubovy-mechanismus a four-bar crank–rocker (crank 20, coupler 70, rocker 50 on a 60 mm base)
  roboticke-rameno         an open chain: an arm on a column, a forearm on its pin, a gripper fixed on the forearm
  prevodovka-s-hrebenem    gears and a rack: a pinion Ø30 turns a wheel Ø60 (i = 2:1) and moves a rack π·30 mm a turn
  pumpicka                 a pump: a piston on a 〰 spring, two ↕ check-valve balls (an inlet in the body, an outlet in the piston)
  ridici-box-s-motorem     a box with a PCB and a motor joined by a 🔌 4-wire harness; the motor turns a pulley
  portalovy-pojezd         a carriage on a beam with a stepper: its 🔒 cable in 📎 P-clips through an igus ⛓ energy chain
  otocne-rameno-s-kabelem  an arm on a hinge with a sensor: 4 loose wires, a ➰ loop across the hinge, 📎 tie mounts
"""
import json
import math
import sys
import time
from pathlib import Path

from selenium import webdriver

URL = sys.argv[1]
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] != "-" else Path(__file__).resolve().parent.parent / "demos"
ONLY = set(sys.argv[3:])  # (only these demos, by file name without .a3d.json — none: all)
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
d = webdriver.Edge(options=opts)
js = d.execute_script
A = "window.__app.assembly"
H = "window.__app.agentHandlers"


def call(t, **a):
    r = js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", t, a)
    if r.startswith("ERROR"):
        raise RuntimeError(f"{t} {a}: {r}")
    return r


def wait(script, t=90):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def fresh():
    """An empty project (a page loaded anew)."""
    d.get(URL)
    wait("return !!window.__app")
    time.sleep(1)


def bar(name, w, h, t, holes=(), pins=(), hole_d=8, pin_d=8, pin_h=10):
    """A plate w × h × t: round holes at x (from its middle, along w) and pins standing on its top."""
    call("new_model", name=name)
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": w, "h": h}}])
    call("add_feature", type="extrude", sketch="F1", d=t)
    if holes:
        call("add_feature", type="hole", face="F2:end", points=[[x, 0] for x in holes], d=hole_d)
    if pins:
        call("add_feature", type="sketch", plane={"face": "F2:end"}, shapes=[{"circle": {"x": x, "y": 0, "d": pin_d}} for x in pins])
        call("add_feature", type="extrude", sketch="F4" if holes else "F3", d=pin_h)  # (the sketch just made)


def block(sketches):
    """A new model's steps: extrudes one after another, [(x, y, w, h, z0, dz)] — a rectangle at x, y (its corner) on the
    plane z = z0, dz up (sketch F1, extrude F2, the next F3, F4 …)."""
    for k, (x, y, w, h, z0, dz) in enumerate(sketches):
        call("add_feature", type="sketch", plane="XY" if not z0 else {"datum": "XY", "offset": z0}, shapes=[{"rect": {"x": x, "y": y, "w": w, "h": h}}])
        call("add_feature", type="extrude", sketch=f"F{2 * k + 1}", d=dz)


def assembly(name, parts):
    call("new_assembly", name=name)
    for p in parts:
        call("insert_part", part=p)
    wait(f"return {A}.doc.instances.length === {len(parts)} && {A}.doc.instances.every(i => {A}.bodies[i.part]?.body)")
    js(f"{A}.inst('I1').fixed = true")


def rounds(i, kind):
    """A placed part's round faces of one kind ('hole' or 'side' — a pin's), sorted by their axis' world x."""
    return js(f"""const it = {A}.inst(arguments[0]), b = {A}.bodies[it.part].body;
      const names = [...new Set(b.faces.filter(f => f.type === 'cylinder' && f.name.includes(arguments[1])).map(f => f.name))];
      return names.map(n => [n, {A}.worldFace(arguments[0], n).axis.o.x]).sort((p, q) => p[1] - q[1]).map(p => p[0])""", i, ":" + kind)


def axis(i, face):
    return js(f"return {A}.worldFace(arguments[0], arguments[1]).axis.o.toArray()", i, face)


def facing(i, n, step="F2"):
    """A placed part's flat face of extrude `step` looking along n (world, e.g. [1, 0, 0])."""
    return js(f"""const it = {A}.inst(arguments[0]), b = {A}.bodies[it.part].body;
      return [...new Set(b.faces.map(f => f.name))].filter(x => x.startsWith(arguments[2] + ':')).find(x => {{ const f = {A}.worldFace(arguments[0], x);
        return f.normal && f.normal.x * arguments[1][0] + f.normal.y * arguments[1][1] + f.normal.z * arguments[1][2] > 0.99; }})""", i, n, step)


def snap(**a):
    return call("snap_faces", **a)


def motion(part, word):
    """The number of a part's free motion whose name has `word` (get_assembly `free`)."""
    free = next(p for p in json.loads(call("get_assembly"))["parts"] if p["id"] == part).get("free", [])
    return next(i for i, m in enumerate(free) if word in m)


def want(name):
    return not ONLY or name in ONLY


def save(file, active_name, meta):
    proj = js("return window.__app.autosave.hooks.project()")
    proj["project_name"] = meta["name_cs"]
    pid = next(p["id"] for p in proj["parts"] if p["name"] == active_name)
    proj["active"] = {"part": pid}
    proj["demo"] = meta
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / file).write_text(json.dumps(proj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"  saved {OUT / file} ({(OUT / file).stat().st_size // 1024} kB)")


try:
    # ---------------------------------------------------------------- a crank – rod – slider
    if want("klikovy-mechanismus"):
        fresh()
        bar("Základna", 240, 60, 10, pins=[-100], pin_d=10, pin_h=6)
        bar("Klika", 45, 16, 6, holes=[-12.5], hole_d=10, pins=[12.5], pin_d=8, pin_h=20)
        bar("Ojnice", 120, 16, 5, holes=[-50, 50], hole_d=8)
        bar("Smýkadlo", 30, 30, 5, pins=[0], pin_d=8, pin_h=25)
        assembly("Klikový mechanismus", ["Základna", "Klika", "Ojnice", "Smýkadlo"])
        snap(type="axis", move={"part": "I2", "face": rounds("I2", "hole")[0]}, onto={"part": "I1", "face": rounds("I1", "side")[0]})
        snap(type="touch", move={"part": "I2", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})
        snap(type="axis", move={"part": "I3", "face": rounds("I3", "hole")[0]}, onto={"part": "I2", "face": rounds("I2", "side")[0]})
        snap(type="touch", move={"part": "I3", "face": "F2:start"}, onto={"part": "I2", "face": "F2:end"})
        snap(type="touch", move={"part": "I4", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})
        snap(type="flush", move={"part": "I4", "face": "F2:side:l1"}, onto={"part": "I1", "face": "F2:side:l1"}, gap=-15)
        along = motion("I4", "Slide")
        call("move_free", part="I4", motion=along, amount=axis("I3", rounds("I3", "hole")[1])[0] - axis("I4", rounds("I4", "side")[0])[0])
        snap(type="axis", move={"part": "I3", "face": rounds("I3", "hole")[1]}, onto={"part": "I4", "face": rounds("I4", "side")[0]})
        call("name_motion", part="I2", motion=motion("I2", "Turn"), name="Otáčení kliky")
        call("name_motion", part="I4", motion=motion("I4", "Slide"), name="Posuv smýkadla")
        for j, n in (("J1", "klika na čepu základny"), ("J3", "ojnice na čepu kliky"), ("J7", "ojnice na čepu smýkadla")):
            js(f"{A}.doc.mates.find(m => m.id === arguments[0]).name = arguments[1]", j, n)
        print(call("drive_mechanism", driver={"part": "I2", "motion": 0}, name="Klikový mechanismus", to=40)[:140])
        save("klikovy-mechanismus.a3d.json", "Klikový mechanismus", {
            "order": 1, "name": "Crank – rod – slider", "name_cs": "Klikový mechanismus",
            "text": "A crank turns, the rod pushes the slider to and fro — one slider (⚙ Mechanism) moves all three parts; ▶ plays it. Drag the crank in the view: the rest follows.",
            "text_cs": "Klika se otáčí, ojnice posouvá smýkadlo tam a zpět — jeden posuvník (⚙ Mechanismus) hýbe všemi třemi díly; ▶ ho přehraje. Táhněte kliku v pohledu: ostatní ji následují."})

    # ---------------------------------------------------------------- a four-bar linkage (crank–rocker)
    if want("ctyrkloubovy-mechanismus"):
        fresh()
        bar("Základna", 160, 80, 8, pins=[-30, 30], pin_d=8, pin_h=5)
        bar("Klika", 36, 12, 5, holes=[-10], hole_d=8, pins=[10], pin_d=6, pin_h=10)
        bar("Spojnice", 86, 12, 4, holes=[-35, 35], hole_d=6)
        bar("Vahadlo", 66, 12, 5, holes=[-25], hole_d=8, pins=[25], pin_d=6, pin_h=10)
        assembly("Čtyřkloubový mechanismus", ["Základna", "Klika", "Spojnice", "Vahadlo"])
        s1, s2 = rounds("I1", "side")
        snap(type="axis", move={"part": "I2", "face": rounds("I2", "hole")[0]}, onto={"part": "I1", "face": s1})
        snap(type="touch", move={"part": "I2", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})
        snap(type="axis", move={"part": "I4", "face": rounds("I4", "hole")[0]}, onto={"part": "I1", "face": s2})
        snap(type="touch", move={"part": "I4", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})
        snap(type="axis", move={"part": "I3", "face": rounds("I3", "hole")[0]}, onto={"part": "I2", "face": rounds("I2", "side")[0]})
        snap(type="touch", move={"part": "I3", "face": "F2:start"}, onto={"part": "I2", "face": "F2:end"})
        # the rocker and the coupler turned to meet (the crank at 90°: its pin up), then the loop closed
        call("move_free", part="I2", motion=motion("I2", "Turn"), to=90)
        o2, o4, pa = axis("I1", s1), axis("I1", s2), axis("I2", rounds("I2", "side")[0])
        a, b, c = 20, 70, 50
        dx, dy = o4[0] - pa[0], o4[1] - pa[1]
        dd = math.hypot(dx, dy)
        k = (b * b - c * c + dd * dd) / (2 * dd)
        hgt = math.sqrt(max(0, b * b - k * k))
        bx, by = pa[0] + k * dx / dd - hgt * dy / dd, pa[1] + k * dy / dd + hgt * dx / dd  # (the upper one: elbow up)
        rp = axis("I4", rounds("I4", "side")[0])
        turn = math.degrees(math.atan2(by - o4[1], bx - o4[0]) - math.atan2(rp[1] - o4[1], rp[0] - o4[0]))
        call("move_free", part="I4", motion=motion("I4", "Turn"), amount=turn)
        cur = rounds("I3", "hole")
        far = max(cur, key=lambda n: math.hypot(axis("I3", n)[0] - pa[0], axis("I3", n)[1] - pa[1]))
        fp = axis("I3", far)
        turn = math.degrees(math.atan2(by - pa[1], bx - pa[0]) - math.atan2(fp[1] - pa[1], fp[0] - pa[0]))
        call("move_free", part="I3", motion=motion("I3", "Turn"), amount=turn)
        snap(type="axis", move={"part": "I3", "face": far}, onto={"part": "I4", "face": rounds("I4", "side")[0]})
        call("name_motion", part="I2", motion=motion("I2", "Turn"), name="Otáčení kliky")
        call("name_motion", part="I4", motion=motion("I4", "Turn"), name="Kývání vahadla")
        print(call("drive_mechanism", driver={"part": "I2", "motion": 0}, name="Čtyřkloubový mechanismus", to=60)[:140])
        save("ctyrkloubovy-mechanismus.a3d.json", "Čtyřkloubový mechanismus", {
            "order": 2, "name": "Four-bar linkage", "name_cs": "Čtyřkloubový mechanismus",
            "text": "The crank turns all the way round, the coupler swings the rocker to and fro (a crank–rocker: crank 20, coupler 70, rocker 50 mm on a 60 mm base).",
            "text_cs": "Klika se otáčí dokola, spojnice kýve vahadlem tam a zpět (klika–vahadlo: klika 20, spojnice 70, vahadlo 50 mm na základně 60 mm)."})

    # ---------------------------------------------------------------- a robot arm: an open chain
    if want("roboticke-rameno"):
        fresh()
        bar("Základna", 120, 120, 8, pins=[0], pin_d=12, pin_h=16)
        bar("Rameno", 100, 20, 8, holes=[-40], hole_d=12, pins=[40], pin_d=10, pin_h=14)
        bar("Předloktí", 80, 16, 6, holes=[-30], hole_d=10, pins=[30], pin_d=8, pin_h=10)
        call("new_model", name="Chapadlo")
        call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 24, "h": 24}}])
        call("add_feature", type="extrude", sketch="F1", d=10)
        call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=8)
        call("add_feature", type="sketch", plane={"face": "F2:end"}, shapes=[{"circle": {"x": x, "y": 0, "d": 6}} for x in (-8.5, 8.5)])  # (two fingers)
        call("add_feature", type="extrude", sketch="F4", d=14)
        assembly("Robotické rameno", ["Základna", "Rameno", "Předloktí", "Chapadlo"])
        snap(type="axis", move={"part": "I2", "face": rounds("I2", "hole")[0]}, onto={"part": "I1", "face": rounds("I1", "side")[0]})
        snap(type="touch", move={"part": "I2", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})
        snap(type="axis", move={"part": "I3", "face": rounds("I3", "hole")[0]}, onto={"part": "I2", "face": rounds("I2", "side")[0]})
        snap(type="touch", move={"part": "I3", "face": "F2:start"}, onto={"part": "I2", "face": "F2:end"})
        snap(type="axis", move={"part": "I4", "face": rounds("I4", "hole")[0]}, onto={"part": "I3", "face": rounds("I3", "side")[0]})
        snap(type="touch", move={"part": "I4", "face": "F2:start"}, onto={"part": "I3", "face": "F2:end"})
        print(" ", call("lock_motion", part="I4", motion=motion("I4", "Turn"))[:80])
        call("name_motion", part="I2", motion=motion("I2", "Turn"), name="Otáčení ramene")
        call("name_motion", part="I3", motion=motion("I3", "Turn"), name="Ohyb lokte")
        call("set_travel", part="I3", motion="Ohyb lokte", min=-135, max=135)
        call("drive_mechanism", mechanism="I2", name="Rameno")
        call("drive_mechanism", mechanism="I3", name="Loket", to=60)
        print(call("drive_mechanism", mechanism="I2", to=30)[:140])
        save("roboticke-rameno.a3d.json", "Robotické rameno", {
            "order": 3, "name": "Robot arm", "name_cs": "Robotické rameno",
            "text": "An open chain: turn the arm and the forearm with the gripper goes along; bend the elbow and the gripper follows it. Each joint has its own slider and ▶.",
            "text_cs": "Otevřený řetězec: otočte ramenem a předloktí s chapadlem jdou s ním; ohněte loket a chapadlo ho následuje. Každý kloub má svůj posuvník a ▶."})

    # ---------------------------------------------------------------- gears and a rack: couplings between motions
    if want("prevodovka-s-hrebenem"):
        fresh()
        call("new_model", name="Základna")
        call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 200, "h": 140}}])
        call("add_feature", type="extrude", sketch="F1", d=8)
        call("add_feature", type="sketch", plane={"face": "F2:end"}, shapes=[{"circle": {"x": x, "y": 0, "d": 10}} for x in (-30, 15)])
        call("add_feature", type="extrude", sketch="F3", d=12)
        for name, dia, mark in (("Pastorek", 30, 9), ("Kolo", 60, 21)):  # (a wheel as its pitch circle, a hole off its middle to see it turn)
            call("new_model", name=name)
            call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": dia}}])
            call("add_feature", type="extrude", sketch="F1", d=6)
            call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=10)
            call("add_feature", type="hole", face="F2:end", points=[[mark, 0]], d=4 if dia < 40 else 6)
        call("new_model", name="Hřeben")
        call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 12, "h": 120}}])
        call("add_feature", type="extrude", sketch="F1", d=6)
        assembly("Převodovka s hřebenem", ["Základna", "Pastorek", "Kolo", "Hřeben"])
        pins = rounds("I1", "side")
        for i, pin in zip(("I2", "I3"), pins):
            hole = min(rounds(i, "hole"), key=lambda n: abs(axis(i, n)[0] - axis(i, rounds(i, "side")[0])[0]) + abs(axis(i, n)[1] - axis(i, rounds(i, "side")[0])[1]))  # (the one in its middle)
            snap(type="axis", move={"part": i, "face": hole}, onto={"part": "I1", "face": pin})
            snap(type="touch", move={"part": i, "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})
        snap(type="touch", move={"part": "I4", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})
        side = lambda i, sx: js(f"return [...new Set({A}.bodies[{A}.inst(arguments[0]).part].body.faces.map(f => f.name))].find(n => {{ const f = {A}.worldFace(arguments[0], n); return f.normal && f.normal.x * arguments[1] > 0.99; }})", i, sx)  # noqa: E731
        rim = rounds("I2", "side")[0]
        px, bx = axis("I2", rim)[0], js(f"return {A}.worldFace('I1', arguments[0]).centroid.x", side("I1", -1))
        snap(type="flush", move={"part": "I4", "face": side("I4", -1)}, onto={"part": "I1", "face": side("I1", -1)}, gap=-(px - 15 - 12 - bx))  # (the rack's side on the pinion's rim)
        snap(type="gear", move={"part": "I2", "face": rim}, onto={"part": "I3", "face": rounds("I3", "side")[0]}, name="pastorek a kolo")
        snap(type="rack", move={"part": "I2", "face": rim}, onto={"part": "I4", "face": side("I4", 1)}, name="pastorek a hřeben")
        for i, color in (("I1", "#c9ced6"), ("I2", "#e8a33d"), ("I3", "#4a90d9"), ("I4", "#a070d0")):
            call("set_look", part=i, color=color)
        call("name_motion", part="I2", motion=motion("I2", "Turn"), name="Otáčení pastorku")
        call("name_motion", part="I3", motion=motion("I3", "Turn"), name="Otáčení kola")
        call("name_motion", part="I4", motion=0, name="Posuv hřebene")
        call("set_travel", part="I2", motion="Otáčení pastorku", min=-120, max=120)
        print(call("drive_mechanism", driver={"part": "I2", "motion": 0}, name="Převodovka s hřebenem", to=0)[:140])
        save("prevodovka-s-hrebenem.a3d.json", "Převodovka s hřebenem", {
            "order": 4, "name": "Gears and a rack", "name_cs": "Převodovka s hřebenem",
            "text": "A pinion Ø30 turns a wheel Ø60 (⚙ i = 2:1 — half as fast, the other way) and moves a rack π·30 mm a turn — one slider (⚙ Mechanism) moves all three; ▶ plays it. Drag the wheel or push the rack in the view: the others follow.",
            "text_cs": "Pastorek Ø30 otáčí kolem Ø60 (⚙ i = 2:1 — polovičními otáčkami, opačně) a posouvá hřeben o π·30 mm na otáčku — jeden posuvník (⚙ Mechanismus) hýbe všemi třemi; ▶ ho přehraje. Táhněte kolo nebo hřeben v pohledu: ostatní je následují."})
    # ---------------------------------------------------------------- a pump: a spring and two check-valve balls
    if want("pumpicka"):
        fresh()

        def turned(name, pts):
            """A part turned about its own Z: a closed profile [radius, height] on XZ, a full turn."""
            call("new_model", name=name)
            call("add_feature", type="sketch", plane="XZ", shapes=[{"profile": {"points": pts}}])
            call("add_feature", type="revolve", sketch="F1", axis="y", angle=360)
        # the body: an inlet Ø4 with a 45° seat (its apex 5 up) under a bore Ø20 from 10 to 50 mm
        turned("Těleso", [[2, 0], [15, 0], [15, 50], [10, 50], [10, 10], [5, 10], [2, 7]])
        # the piston Ø19.6 × 8 with a hollow rod: a channel Ø3 up to a 45° seat (its apex 10.5 up) for the outlet ball
        turned("Píst", [[1.5, 0], [9.8, 0], [9.8, 8], [4, 8], [4, 40], [3.5, 40], [3.5, 14], [1.5, 12]])
        call("new_model", name="Pružina")
        call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 18}}, {"circle": {"x": 0, "y": 0, "d": 12}}])
        call("add_feature", type="extrude", sketch="F1", d=20)
        for name in ("Kulička sací", "Kulička výtlačná"):
            turned(name, [[0, -3], {"arc": [3, 0]}, [0, 3]])
        assembly("Pumpička", ["Těleso", "Píst", "Pružina", "Kulička sací", "Kulička výtlačná"])

        def find(i, kind, **w):
            """A placed part's face: its type, radius / the z of a flat face looking up (+1) or down (-1)."""
            return js(f"""const it = {A}.inst(arguments[0]), b = {A}.bodies[it.part].body, w = arguments[2];
              return b.faces.find(f => f.type === arguments[1] && (w.r === undefined || Math.abs(f.radius - w.r) < 1e-6)
                && (w.up === undefined || (f.normal[2] * w.up > 0.99 && Math.abs(f.centroid[2] - w.z) < 1e-6)))?.name""", i, kind, w)
        seat = 3 / math.sin(math.pi / 4)  # (a Ø6 ball in a 45° seat: its centre r / sin 45° from the apex)
        call("place_part", part="I2", x=0, y=0, z=30)
        call("place_part", part="I3", x=0, y=0, z=10)
        call("place_part", part="I4", x=0, y=0, z=5 + seat)
        call("place_part", part="I5", x=0, y=0, z=40.5 + seat)
        bore = find("I1", "cylinder", r=10)
        snap(type="axis", move={"part": "I3", "face": find("I3", "cylinder", r=9)}, onto={"part": "I1", "face": bore}, lock_rotation=True)
        snap(type="touch", move={"part": "I3", "face": "F2:start"}, onto={"part": "I1", "face": find("I1", "plane", up=1, z=10)})
        snap(type="axis", move={"part": "I2", "face": find("I2", "cylinder", r=9.8)}, onto={"part": "I1", "face": bore}, lock_rotation=True)
        snap(type="spring", move={"part": "I3", "face": "F2:end"}, onto={"part": "I2", "face": find("I2", "plane", up=-1, z=0)}, value=0.3, name="pružina pístu")
        snap(type="ball", move={"part": "I4", "face": find("I4", "sphere")}, onto={"part": "I1", "face": find("I1", "cone")}, name="sací ventil")
        snap(type="ball", move={"part": "I5", "face": find("I5", "sphere")}, onto={"part": "I2", "face": find("I2", "cone")}, name="výtlačný ventil")
        press = motion("I2", "Slide")
        call("name_motion", part="I2", motion=press, name="Zmáčknutí tlačítka")
        up = js(f"return {A}.motionsOf('I2').motions[arguments[0]].dir.z > 0", press)  # (its value grows going up)
        at = float(js(f"const a = {A}, mo = a.motionsOf('I2').motions[arguments[0]]; return a.motionPos('I2', mo)", press))
        call("set_travel", part="I2", motion=press, min=min(at, at + (-6 if up else 6)), max=max(at, at + (-6 if up else 6)))
        for i, name, lift_when_up in (("I4", "Zdvih sacího ventilu", True), ("I5", "Zdvih výtlačného ventilu", False)):
            k = motion(i, "Slide")
            bu = js(f"return {A}.motionsOf(arguments[0]).motions[arguments[1]].dir.z > 0", i, k)
            p = float(js(f"const a = {A}, mo = a.motionsOf(arguments[0]).motions[arguments[1]]; return a.motionPos(arguments[0], mo)", i, k))
            lift = 2.5 if bu else -2.5
            call("set_travel", part=i, motion=k, min=min(p, p + lift), max=max(p, p + lift))
            lifted, seated = ("max", "min") if bu else ("min", "max")
            # the inlet opens while the piston goes up (it sucks), the outlet while it goes down (it presses)
            call("set_travel", part=i, motion=k, follow={"part": "I2", "motion": press, "at": lifted if lift_when_up == up else seated})
            call("name_motion", part=i, motion=k, name=name)
        call("set_look", part="I1", color="#9fb3c8", opacity=0.35)
        for i, color in (("I2", "#e8a33d"), ("I3", "#4a90d9"), ("I4", "#d94a4a"), ("I5", "#3fb950")):
            call("set_look", part=i, color=color)
        print(call("drive_mechanism", mechanism="I2", name="Pumpička", to=at + (-3 if up else 3))[:160])
        save("pumpicka.a3d.json", "Pumpička", {
            "order": 5, "name": "Pump", "name_cs": "Pumpička",
            "text": "Press the button: the piston compresses the spring (〰 drawn as long as it is: free 20 mm, now, the force), the outlet ball lifts and the inlet ball sits on its seat; let go: the other way round — check valves (↕ by the piston's direction). ▶ plays it, 📈 Trace shows a ball's two stops.",
            "text_cs": "Zmáčkněte tlačítko: píst stlačí pružinu (〰 kreslená tak dlouhá, jaká je: volná 20 mm, teď, síla), výtlačná kulička se zvedne a sací dosedne do sedla; pusťte: naopak — zpětné ventily (↕ podle směru pístu). ▶ to přehraje, 📈 Průběh ukáže oba dorazy kuličky."})
    # ---------------------------------------------------------------- a box with a PCB and a motor: a 🔌 4-wire harness
    if want("ridici-box-s-motorem"):
        fresh()
        call("new_model", name="Krabice")
        call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 160, "h": 100}}])
        call("add_feature", type="extrude", sketch="F1", d=8)
        call("new_model", name="DPS")
        call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
        call("add_feature", type="extrude", sketch="F1", d=1.6)
        call("new_model", name="Motor")
        call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 30, "h": 30}}])
        call("add_feature", type="extrude", sketch="F1", d=30)
        call("add_feature", type="sketch", plane={"face": "F2:end"}, shapes=[{"circle": {"x": 0, "y": 0, "d": 6}}])
        call("add_feature", type="extrude", sketch="F3", d=10)  # (its shaft)
        call("new_model", name="Řemenice")
        call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 30}}])
        call("add_feature", type="extrude", sketch="F1", d=6)
        call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=6)
        call("add_feature", type="hole", face="F2:end", points=[[9, 0]], d=4)  # (a mark: it is seen to turn)
        assembly("Řídicí box s motorem", ["Krabice", "DPS", "Motor", "Řemenice"])
        call("place_part", part="I2", x=15, y=30, z=8)
        call("place_part", part="I2", fixed=True)
        call("place_part", part="I3", x=110, y=35, z=8)
        call("place_part", part="I3", fixed=True)
        snap(type="axis", move={"part": "I4", "face": rounds("I4", "hole")[0] if axis("I4", rounds("I4", "hole")[0])[0] < axis("I4", rounds("I4", "hole")[-1])[0] else rounds("I4", "hole")[-1]},
             onto={"part": "I3", "face": rounds("I3", "side")[0]}, name="řemenice na hřídeli")
        snap(type="touch", move={"part": "I4", "face": "F2:start"}, onto={"part": "I3", "face": "F2:end"})
        for i, color in (("I1", "#c9ced6"), ("I2", "#2f8f4e"), ("I3", "#5b6470"), ("I4", "#e8a33d")):
            call("set_look", part=i, color=color)
        call("name_motion", part="I4", motion=motion("I4", "Turn"), name="Otáčení řemenice")
        print(call("add_harness", type="wires", count=4, name="Napájení motoru",
                   points=[{"part": "I2", "face": "F2:end"}, {"xyz": [62, 50, 34]}, {"xyz": [95, 18, 34]}, {"part": "I3", "face": "F2:side:l1"}])[:160])
        print(call("drive_mechanism", driver={"part": "I4", "motion": 0}, name="Motor", to=0)[:140])
        js(f"{A}.harnessTool.sel = null; {A}.render(); {A}.draw()")
        save("ridici-box-s-motorem.a3d.json", "Řídicí box s motorem", {
            "order": 5, "name": "Control box with a motor", "name_cs": "Řídicí box s motorem",
            "text": "A PCB and a motor in a box, joined by a 🔌 cable harness of 4 loose wires (red, black, blue, brown) routed over the box — its length, the bends at the minimum radius, a BOM line per wire. Click the harness: edit its points, change it to a cable; ▶ turns the motor's pulley.",
            "text_cs": "Deska plošných spojů a motor v krabici, spojené 🔌 kabelovým svazkem ze 4 volných drátů (červený, černý, modrý, hnědý) vedeným nad krabicí — jeho délka, ohyby na minimální poloměr, řádek kusovníku na každý drát. Klikněte na svazek: upravte body, změňte ho na kabel; ▶ otáčí řemenicí motoru."})
    # ---------------------------------------------------------------- a gantry carriage: a cable through a ⛓ energy chain
    if want("portalovy-pojezd"):
        fresh()
        # the base 640 × 220 with two 3 mm pads for the cable's clips (a P-clip holds the cable 10 mm off its screw: on
        # y 50, the chain's lane)
        call("new_model", name="Základna")
        block([(0, 0, 640, 220, 0, 10), (210, 30, 20, 20, 10, 3), (340, 30, 20, 20, 10, 3)])
        call("new_model", name="Nosník")  # (the linear guide: a beam 60 high — the carriage rides above the chain's upper run)
        block([(0, 0, 500, 30, 0, 60)])
        # the carriage 200 × 170 × 12 (x from its middle) over the beam and the chain's lane (y 25 here): a 4 mm block
        # under the chain's moving end (x 60 … 80) and a pad for the cable's clip, its axis on the chain's level
        call("new_model", name="Vozík")
        block([(-100, 0, 200, 170, 0, 12), (55, 10, 30, 30, 12, 4), (10, 5, 20, 20, 12, 11.8)])
        call("new_model", name="Rozvodnice")  # (a box with a cable gland low on its +x side)
        block([(0, 0, 70, 60, 0, 60), (70, 22, 10, 16, 8, 14)])
        assembly("Portálový pojezd", ["Základna", "Nosník", "Vozík", "Rozvodnice"])
        call("place_part", part="I2", x=80, y=160, z=10)
        call("place_part", part="I2", fixed=True)
        call("place_part", part="I4", x=15, y=20, z=10)
        call("place_part", part="I4", fixed=True)
        snap(type="touch", move={"part": "I3", "face": "F2:start"}, onto={"part": "I2", "face": "F2:end"}, name="vozík na nosníku")
        call("lock_motion", part="I3", motion=motion("I3", "Turn"))  # (the touch leaves two slides and a turn: the turn locked,
        pos = lambda i: next(p for p in json.loads(call("get_assembly"))["parts"] if p["id"] == i)["position"]  # noqa: E731
        k = motion("I3", "along Y")  # the carriage moved across to the chain's lane, there locked)
        y0 = pos("I3")[1]
        call("move_free", part="I3", motion=k, amount=25 - y0)
        if abs(pos("I3")[1] - 25) > 1e-6:
            call("move_free", part="I3", motion=k, amount=2 * (y0 - 25))
        call("lock_motion", part="I3", motion=motion("I3", "along Y"))
        along = motion("I3", "Slide")
        call("name_motion", part="I3", motion=along, name="Pojezd vozíku")
        call("set_travel", part="I3", motion="Pojezd vozíku", min=-150, max=150)
        call("move_free", part="I3", motion=along, to=0)
        xc, yc, zc = pos("I3")
        # a NEMA 17 stepper on the carriage, in the chain's lane: its +x side (the cable's end) toward the chain
        call("library_add", item="nema17", size="34 mm", to="assembly")
        call("place_part", part="I5", x=xc - 75, y=yc + 25, z=zc + 12)
        snap(type="rigid", move={"part": "I5"}, onto={"part": "I3"}, name="motor na vozíku")
        # ⛓ an igus E2.15 chain (Bi 16, R 38): its fixed end on the base below the moving end's middle, its lower run on
        # the base; its moving end on the carriage's block (x + 60), moving with the carriage
        call("library_add", item="igus-e2-15", size="Bi 16", length=38, to="assembly")
        ha, links = 19.3, 16  # (its outer height; 16 links reach ±200 mm)
        call("place_part", part="I6", x=xc + 60, y=yc + 25, z=10 + ha / 2)
        call("place_part", part="I6", fixed=True)
        js(f"""const a = {A}, rec = a.doc.chains.find(c => c.part === 'I6'); rec.links = arguments[0]; rec.name = 'Energetický řetěz';
          return import('./js/assembly/chains.js').then(C => {{ C.followPart(a, rec, 'I3'); a.commit(); C.drawChains(a); }})""", links)
        print(" ", json.dumps(json.loads(call("get_assembly")).get("chains")))
        # 🔌 the motor's cable: from the box's gland along the base (two P-clips), through the chain, a clip on the
        # carriage, to the motor — every point locked to its part
        print(" ", call("add_harness", type="cable", d=7, color="orange", name="Kabel motoru", points=[
            {"part": "I4", "face": facing("I4", [1, 0, 0], "F4")}, {"part": "I1", "face": "F4:end"}, {"part": "I1", "face": "F6:end"},
            {"part": "I3", "face": "F6:end"}, {"part": "I5", "face": facing("I5", [1, 0, 0])}])[:600])
        call("edit_harness", id="H1", chain={"span": 3, "id": "C1"})
        for k in (2, 3):
            call("edit_harness", id="H1", clip={"point": k, "item": "ht-hp-pclamp"})
        call("move_free", part="I3", motion=along, to=150)  # (the carriage's clip along +x: from the base's clip to the motor)
        call("edit_harness", id="H1", clip={"point": 4, "item": "ht-hp-pclamp"})
        call("move_free", part="I3", motion=along, to=0)
        print(" ", call("edit_harness", id="H1", length_locked=True)[:1200])
        for i, color in (("I1", "#c9ced6"), ("I2", "#8f99a6"), ("I3", "#4a90d9"), ("I4", "#5b6470")):
            call("set_look", part=i, color=color)
        print(call("drive_mechanism", driver={"part": "I3", "motion": 0}, name="Portálový pojezd", to=-60)[:140])
        js(f"{A}.harnessTool.sel = null; {A}.render(); {A}.draw()")
        save("portalovy-pojezd.a3d.json", "Portálový pojezd", {
            "order": 6, "name": "Gantry carriage", "name_cs": "Portálový pojezd",
            "text": "A carriage on a rail (⚙ travel ±150 mm) with a NEMA 17 stepper; its cable runs from the box along the base in two 📎 P-clips (HellermannTyton H4P), through an igus E2.15 ⛓ energy chain and a clip on the carriage to the motor. ▶: the chain rolls with the carriage and the cable follows it — its 🔒 length stays the same.",
            "text_cs": "Vozík na kolejnici (⚙ pojezd ±150 mm) s krokovým motorem NEMA 17; jeho kabel vede z rozvodnice po základně ve dvou 📎 P-příchytkách (HellermannTyton H4P), energetickým řetězem igus E2.15 ⛓ a příchytkou na vozíku k motoru. ▶: řetěz se odvaluje s vozíkem a kabel ho následuje — jeho 🔒 délka zůstává stejná."})
    # ---------------------------------------------------------------- a swinging arm: a ➰ service loop across its hinge
    if want("otocne-rameno-s-kabelem"):
        fresh()
        # the base 480 × 440 with a column Ø40, 80 high, and a pin Ø16 on it (the hinge at x 260, y 220)
        call("new_model", name="Základna")
        block([(0, 0, 480, 440, 0, 10)])
        for k, (dia, z0, dz) in enumerate(((40, 10, 80), (16, 90, 10))):
            call("add_feature", type="sketch", plane={"datum": "XY", "offset": z0}, shapes=[{"circle": {"x": 260, "y": 220, "d": dia}}])
            call("add_feature", type="extrude", sketch=f"F{3 + 2 * k}", d=dz)
        # the arm 270 × 40 × 10 (x from its hinge): a hole Ø16 on the pin, a hole Ø12 for the sensor 200 out, two pads for
        # tie mounts (one behind the hinge: the cable comes onto the arm near its axis)
        call("new_model", name="Rameno")
        block([(-45, -20, 270, 40, 0, 10), (-36, -8, 16, 16, 10, 1), (92, -8, 16, 16, 10, 1)])
        call("add_feature", type="hole", face="F2:end", points=[[110, 0]], d=12)  # (from the top's middle, x 90)
        call("add_feature", type="hole", face="F2:end", points=[[-90, 0]], d=16)
        call("new_model", name="Řídicí jednotka")  # (a controller box 120 × 90 × 80, a cable gland on its top by the hinge)
        block([(0, 0, 120, 90, 0, 80), (98, 37, 16, 16, 80, 10)])
        assembly("Otočné rameno s kabelem", ["Základna", "Rameno", "Řídicí jednotka"])
        call("place_part", part="I3", x=30, y=175, z=10)
        call("place_part", part="I3", fixed=True)
        radius = lambda i, n: js(f"return {A}.worldFace(arguments[0], arguments[1]).radius", i, n)  # noqa: E731
        pin = min(rounds("I1", "side"), key=lambda n: radius("I1", n))
        snap(type="axis", move={"part": "I2", "face": max(rounds("I2", "hole"), key=lambda n: radius("I2", n))}, onto={"part": "I1", "face": pin}, name="rameno na čepu")
        snap(type="touch", move={"part": "I2", "face": "F2:start"}, onto={"part": "I1", "face": facing("I1", [0, 0, 1], "F4")})
        turn = motion("I2", "Turn")
        call("name_motion", part="I2", motion=turn, name="Otáčení ramene")
        call("move_free", part="I2", motion=turn, to=0)
        call("set_travel", part="I2", motion="Otáčení ramene", min=-90, max=90)
        # a SICK IME12 sensor in the arm's tip (its thread in the hole), its sensing face down, 15 mm below the arm
        call("library_add", item="sick-ime", size="M12, 4 mm", to="assembly")
        snap(type="axis", move={"part": "I4", "face": "F2:side:l2"}, onto={"part": "I2", "face": min(rounds("I2", "hole"), key=lambda n: radius("I2", n))}, lock_rotation=True, name="snímač v rameni")
        box = lambda i: next(p for p in json.loads(call("get_assembly"))["parts"] if p["id"] == i)["bbox"]  # noqa: E731
        k, z0 = motion("I4", "Slide"), box("I4")[2]
        call("move_free", part="I4", motion=k, amount=75 - z0)
        if abs(box("I4")[2] - 75) > 1e-6:
            call("move_free", part="I4", motion=k, amount=2 * (z0 - 75))
        call("lock_motion", part="I4", motion=k)
        top = js(f"""const it = {A}.inst('I4'), b = {A}.bodies[it.part].body;
          return b.faces.filter(f => f.type === 'plane' && f.normal[2] > 0.99).sort((p, q) => q.centroid[2] - p.centroid[2])[0].name""")
        # 🔌 four loose wires (a PNP sensor's: brown +, blue −, black signal, white) from the controller's gland to the
        # sensor: ➰ a loop of slack arching over to the arm (up out of the gland: it comes onto the arm from above), two
        # tie mounts on the arm
        print(" ", call("add_harness", type="wires", wires=[{"color": c, "d": 1.5} for c in ("brown", "blue", "black", "white")], name="Kabel snímače", points=[
            {"part": "I3", "face": "F4:end"}, {"part": "I2", "face": "F4:end"}, {"part": "I2", "face": "F6:end"},
            {"part": "I4", "face": top}])[:600])
        for k in (2, 3):  # (a tie mount on the arm: fixed to it, it goes with the arm)
            call("edit_harness", id="H1", clip={"point": k, "item": "ht-mb-mount"})
        print(" ", call("edit_harness", id="H1", spans=[{"from": 1, "length": 150}])[:1200])
        for i, color in (("I1", "#c9ced6"), ("I2", "#e8a33d"), ("I3", "#5b6470")):
            call("set_look", part=i, color=color)
        print(call("drive_mechanism", driver={"part": "I2", "motion": 0}, name="Otočné rameno", to=40)[:140])
        js(f"{A}.harnessTool.sel = null; {A}.render(); {A}.draw()")
        save("otocne-rameno-s-kabelem.a3d.json", "Otočné rameno s kabelem", {
            "order": 7, "name": "Swinging arm with a cable", "name_cs": "Otočné rameno s kabelem",
            "text": "An arm on a hinge (⚙ −90 … +90°) with a SICK sensor at its tip, wired with 4 loose wires (brown, blue, black, white) from the controller: a ➰ loop of slack arching across the hinge onto the arm, two adhesive 📎 tie mounts (HellermannTyton MB3A) on the arm. ▶ swings the arm — the loop takes up the motion and never goes taut; the wires keep clear of the box and the arm.",
            "text_cs": "Rameno na čepu (⚙ −90 … +90°) se snímačem SICK na konci, zapojeným 4 volnými vodiči (hnědý, modrý, černý, bílý) z řídicí jednotky: ➰ smyčka rezervy obloukem přes kloub na rameno, na rameni dvě samolepicí 📎 příchytky (HellermannTyton MB3A). ▶ rameno kývá — smyčka pohyb vyrovná a nikdy se nenapne; vodiče se vyhnou krabici i rameni."})
finally:
    d.quit()
