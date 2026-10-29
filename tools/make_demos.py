"""Build the 🎬 demo projects (demos/*.a3d.json) through the app, as a user (or the AI) would: 3D models from sketches
and extrudes, an assembly with joints, the motions named in Czech, the mechanism's driver and name set — then the
project as the app saves it, with its "demo" record (auto3d/demos.py).

  PYTHONIOENCODING=utf-8 py tools/make_demos.py http://127.0.0.1:5199 [<out folder, default demos/>]

  klikovy-mechanismus      a crank – rod – slider (r 25, L 100)
  ctyrkloubovy-mechanismus a four-bar crank–rocker (crank 20, coupler 70, rocker 50 on a 60 mm base)
  roboticke-rameno         an open chain: an arm on a column, a forearm on its pin, a gripper fixed on the forearm
"""
import json
import math
import sys
import time
from pathlib import Path

from selenium import webdriver

URL = sys.argv[1]
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parent.parent / "demos"
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


def snap(**a):
    return call("snap_faces", **a)


def motion(part, word):
    """The number of a part's free motion whose name has `word` (get_assembly `free`)."""
    free = next(p for p in json.loads(call("get_assembly"))["parts"] if p["id"] == part).get("free", [])
    return next(i for i, m in enumerate(free) if word in m)


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
    along = motion("I4", "X")
    call("move_free", part="I4", motion=along, amount=axis("I3", rounds("I3", "hole")[1])[0] - axis("I4", rounds("I4", "side")[0])[0])
    snap(type="axis", move={"part": "I3", "face": rounds("I3", "hole")[1]}, onto={"part": "I4", "face": rounds("I4", "side")[0]})
    call("name_motion", part="I2", motion=motion("I2", "Turn"), name="Otáčení kliky")
    call("name_motion", part="I4", motion=motion("I4", "X"), name="Posuv smýkadla")
    for j, n in (("J1", "klika na čepu základny"), ("J3", "ojnice na čepu kliky"), ("J7", "ojnice na čepu smýkadla")):
        js(f"{A}.doc.mates.find(m => m.id === arguments[0]).name = arguments[1]", j, n)
    print(call("drive_mechanism", driver={"part": "I2", "motion": 0}, name="Klikový mechanismus", to=40)[:140])
    save("klikovy-mechanismus.a3d.json", "Klikový mechanismus", {
        "order": 1, "name": "Crank – rod – slider", "name_cs": "Klikový mechanismus",
        "text": "A crank turns, the rod pushes the slider to and fro — one slider (⚙ Mechanism) moves all three parts; ▶ plays it. Drag the crank in the view: the rest follows.",
        "text_cs": "Klika se otáčí, ojnice posouvá smýkadlo tam a zpět — jeden posuvník (⚙ Mechanismus) hýbe všemi třemi díly; ▶ ho přehraje. Táhněte kliku v pohledu: ostatní ji následují."})

    # ---------------------------------------------------------------- a four-bar linkage (crank–rocker)
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
finally:
    d.quit()
