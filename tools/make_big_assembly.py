"""Build big benchmark assemblies (.a3d) through the app, as the AI would: its parts made with the AI tools (sketches,
extrudes, holes, a ▣ Solid from a STEP file, library screws / nuts / washers / a bearing / a standoff), then placed in
bulk — the many copies of a fastener put straight into the assembly document with their joints (◎ concentric on the
hole, ▭ touch under the head), as insert_part + snap_faces would, without one rebuild per copy — and saved as the app
saves a project (/api/project/package). For the performance tests (tools/e2e_big_assembly.py) and profiling.

  PYTHONIOENCODING=utf-8 py tools/make_big_assembly.py http://127.0.0.1:5199 <out folder> [a] [b] [c]

  a  big-150.a3d   ~150 placed parts of ~20 distinct ones: a base, plates screwed on with M4 screws, washers and nuts
                   (through the base), columns carrying a "Module A" sub-assembly each (a plate with M3 screws, washers,
                   nuts), "Bearing block" sub-assemblies (a block, a 608 bearing, a shaft, M5 screws), L brackets, an
                   imported STEP part twice, standoffs — joints: concentric and touch
  b  big-500.a3d   ~520 placed parts: 40 plates on a base with 4 × (M3 screw, washer, nut) each, few joints
  c  mech-30.a3d   a gear train: 30 discs on the pins of a base, each turning on its pin, each one geared to the next —
                   one ⚙ mechanism of 30 moving parts
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

from selenium import webdriver

ROOT = Path(__file__).resolve().parent.parent
STEP = ROOT / "samples" / "ToImportToOurApp" / "nist" / "827-9999-906.stp"  # (102.5 × 69.5 × 19.5 mm, 89 faces)


def T(x, y, z):
    """A three.js matrix (column-major) moving by x, y, z."""
    return [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, z, 1]


class Builder:
    """A headless Edge on the app with the AI's tools (call) and a bulk placer (put / mate / done)."""

    def __init__(self, url, software_gl=False, window=False):
        self.url = url.rstrip("/")
        opts = webdriver.EdgeOptions()
        if not window:  # (window: a real Edge window — its frames painted as the owner sees them)
            opts.add_argument("--headless=new")
        if software_gl:  # (WebGL on the CPU — SwiftShader —, as on a machine without a usable GPU)
            opts.add_argument("--use-angle=swiftshader")
            opts.add_argument("--enable-unsafe-swiftshader")
        opts.add_argument("--window-size=1600,1000")
        opts.add_argument("--enable-precise-memory-info")
        opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
        self.d = webdriver.Edge(options=opts)
        self.d.set_script_timeout(600)
        self.js = self.d.execute_script

    def quit(self):
        self.d.quit()

    def fresh(self):
        self.d.get(self.url)
        self.wait("return !!window.__app")
        time.sleep(1)

    def wait(self, script, t=120, *a):
        end = time.time() + t
        while time.time() < end:
            v = self.js(script, *a)
            if v:
                return v
            time.sleep(0.1)
        raise TimeoutError(script)

    def run(self, script, *a):
        """An async script (its body awaits; `return` its value)."""
        r = self.d.execute_async_script("const done = arguments[arguments.length - 1]; (async () => { " + script + " })()"
                                        ".then((v) => done({ v }), (e) => done({ e: String(e && e.stack || e) }))", *a)
        if "e" in r:
            raise RuntimeError(r["e"])
        return r.get("v")

    def call(self, tool, **a):
        r = self.d.execute_async_script("const done = arguments[arguments.length - 1]; window.__app.agentHandlers[arguments[0]](arguments[1])"
                                        ".then((r) => done(r.text), (e) => done('ERROR ' + e.message))", tool, a)
        if r.startswith("ERROR"):
            raise RuntimeError(f"{tool} {a}: {r}")
        return r

    # ---- parts
    def model(self, name, steps):
        """A new 3D model from add_feature steps ([{type, …}])."""
        self.call("new_model", name=name)
        for s in steps:
            r = json.loads(self.call("add_feature", **s))
            if not r.get("ok"):
                raise RuntimeError(f"{name}: {s} -> {r}")

    def plate(self, name, w, h, t, holes=(), hole_d=3.4, more=()):
        """A plate w × h × t (its corner at 0, 0, 0), round holes through it at points from its middle."""
        steps = [{"type": "sketch", "plane": "XY", "shapes": [{"rect": {"x": 0, "y": 0, "w": w, "h": h}}]}, {"type": "extrude", "sketch": "F1", "d": t}]
        if holes:
            steps.append({"type": "hole", "face": "F2:end", "points": [list(p) for p in holes], "d": hole_d})
        for pts, d in more:  # (more hole steps of other sizes)
            steps.append({"type": "hole", "face": "F2:end", "points": [list(p) for p in pts], "d": d})
        self.model(name, steps)

    def library(self, item, size, length=None):
        """A library part as a 3D model of the project -> its part name."""
        a = {"item": item, "size": size, "to": "model"}
        if length:
            a["length"] = length
        self.call("library_add", **a)
        return self.js("const p = window.__app.project.parts; return p[p.length - 1].name")

    def step_part(self, name, path):
        sha = json.loads(urllib.request.urlopen(urllib.request.Request(f"{self.url}/api/blob", path.read_bytes(), {"Content-Type": "application/octet-stream"})).read())["sha"]
        self.call("new_model", name=name)
        self.call("add_feature", type="solid", blob=sha, file=path.name, op="add")
        self.wait("return !!window.__app.modeler.result?.body && !window.__app.modeler.building", 180)

    def faces(self, names):
        """The parts' faces (by part name): {name: {id, faces: [{name, type, centroid, normal, r}]}} — built by the
        assembly's kernel calls (an assembly must be on screen)."""
        return self.run("""const A = window.__app.assembly, names = arguments[0], out = {};
          const parts = window.__app.project.parts.filter((p) => names.includes(p.name));
          await A.buildBodies(parts.map((p) => p.id));
          for (const p of parts) {
            const b = A.bodies[p.id]?.body;
            if (!b) throw new Error(`${p.name}: ${A.bodies[p.id]?.error}`);
            out[p.name] = { id: p.id, bbox: b.bbox, faces: b.faces.map((f) => ({ name: f.name, type: f.type, centroid: f.centroid, normal: f.normal || null,
              r: f.radius ?? f.r ?? null, axis: f.axis || null })) };
          }
          return out;""", list(names))

    # ---- placing in bulk
    def assembly(self, name):
        self.call("new_assembly", name=name)
        self.js("window.__big = { inst: [], mates: [] }")

    def put(self, iid, part_id, m, **extra):
        self.js("window.__big.inst.push(Object.assign({ id: arguments[0], part: arguments[1], matrix: arguments[2] }, arguments[3]))", iid, part_id, m, extra)

    def mate(self, kind, move, face, onto, onto_face, **extra):
        self.js("const b = window.__big; b.mates.push(Object.assign({ id: 'J' + (b.mates.length + 1), type: arguments[0], move: arguments[1], face: arguments[2], onto: arguments[3], ontoFace: arguments[4], gap: 0 }, arguments[5]))",
                kind, move, face, onto, onto_face, extra)

    def done(self):
        """The placed parts and joints into the assembly on screen (one undo step), built and placed by their joints ->
        {instances, joints, unmet}."""
        return self.run("""const A = window.__app.assembly, b = window.__big;
          A.doc.instances.push(...b.inst);
          A.doc.mates = [...(A.doc.mates || []), ...b.mates];
          window.__big = { inst: [], mates: [] };
          await A.refresh();
          A.commit();
          return { instances: A.doc.instances.length, joints: A.doc.mates.length, unmet: A.unmet().length };""")

    def save(self, file, active_name, name, demo=None):
        """The project as the app saves it (an .a3d with its picture); demo: its 🎬 record (auto3d/demos.py) — its Czech
        name then the project's name."""
        proj = self.js("return window.__app.autosave.hooks.project()")
        proj["project_name"] = demo["name_cs"] if demo else name
        if demo:
            proj["demo"] = demo
        proj["active"] = {"part": next(p["id"] for p in proj["parts"] if p["name"] == active_name)}
        thumb = self.d.execute_async_script("window.__app.projectThumb().then(arguments[arguments.length - 1], () => arguments[arguments.length - 1](null))")
        req = urllib.request.Request(f"{self.url}/api/project/package", json.dumps({"project": proj, "thumbnail": thumb}).encode("utf-8"),
                                     {"Content-Type": "application/json"})
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(urllib.request.urlopen(req, timeout=300).read())
        print(f"  saved {file} ({file.stat().st_size // 1024} kB)")


def nearest(faces, kind, x, y):
    """The name of a part's round face (`kind` in its name, e.g. ':hole:') whose axis is nearest to x, y (part frame)."""
    c = [f for f in faces if f["type"] == "cylinder" and kind in f["name"]]
    return min(c, key=lambda f: (f["centroid"][0] - x) ** 2 + (f["centroid"][1] - y) ** 2)["name"]


def screw_faces(f, d):
    """A library screw's shank (round, Ø d) and the underside of its head (flat, facing -z, highest)."""
    shank = min((x for x in f["faces"] if x["type"] == "cylinder"), key=lambda x: abs((x["r"] or 0) * 2 - d) if x["r"] else abs(x["centroid"][2]))
    under = max((x for x in f["faces"] if x["type"] == "plane" and x["normal"] and x["normal"][2] < -0.99), key=lambda x: x["centroid"][2])
    return shank["name"], under["name"]


def bore(f):
    """A nut's / washer's / bearing's inner round face (the smallest)."""
    return min((x for x in f["faces"] if x["type"] == "cylinder"), key=lambda x: x["r"] if x["r"] else 1e9)["name"]


def height(f):
    return f["bbox"][5] - f["bbox"][2]


class Fasten:
    """Screws through holes: the screw from the top (its head on the top face), a washer and a nut under the bottom."""

    def __init__(self, b, faces, screw, washer, nut, d, length):
        self.b, self.d, self.length = b, d, length
        self.s, self.w, self.n = faces[screw], faces[washer], faces[nut]
        self.shank, self.under = screw_faces(self.s, d)
        self.wb, self.nb = bore(self.w), bore(self.n)
        self.wt, self.nt = height(self.w), height(self.n)

    def at(self, ids, x, y, top, bottom, host, hole, top_face, joints=True):
        """A screw at x, y (world) with its head on z = top, washer + nut under z = bottom; joined to host's hole."""
        s, w, n = next(ids), next(ids), next(ids)
        self.b.put(s, self.s["id"], T(x, y, top - self.length))
        self.b.put(w, self.w["id"], T(x, y, bottom - self.wt))
        self.b.put(n, self.n["id"], T(x, y, bottom - self.wt - self.nt))
        if joints:
            self.b.mate("axis", s, self.shank, host, hole, centred=True)
            self.b.mate("touch", s, self.under, host, top_face)
            self.b.mate("axis", w, self.wb, s, self.shank, centred=True)
            self.b.mate("axis", n, self.nb, s, self.shank, centred=True)
        return s


def ids(start=1, prefix="I"):
    k = start
    while True:
        yield f"{prefix}{k}"
        k += 1


def big150(b, out, file="big-150.a3d", demo=None):
    b.fresh()
    # ---- the parts (20 distinct with the two sub-assemblies)
    pb = [(x0, y0) for y0 in (20, 120) for x0 in (20, 160, 300)]  # Plate B corners on the base
    pb_holes = [(-45, -30), (45, -30), (45, 30), (-45, 30)]
    m4 = [(x0 + 60 + hx - 300, y0 + 40 + hy - 200) for x0, y0 in pb for hx, hy in pb_holes]
    b.plate("Base", 600, 400, 10, m4, 4.5)
    b.plate("Plate B", 120, 80, 8, pb_holes, 4.5)
    b.plate("Plate A", 80, 60, 6, [(-30, -20), (30, -20), (30, 20), (-30, 20)], 3.4)
    b.plate("Column", 40, 40, 150)
    b.plate("Block", 60, 40, 20, [(0, 0)], 22, more=[([(-22, 0), (22, 0)], 5.5)])
    b.model("Shaft", [{"type": "sketch", "plane": "XY", "shapes": [{"circle": {"x": 0, "y": 0, "d": 8}}]}, {"type": "extrude", "sketch": "F1", "d": 60}])
    b.model("L bracket", [{"type": "sketch", "plane": "XY", "shapes": [{"rect": {"x": 0, "y": 0, "w": 40, "h": 30}}]}, {"type": "extrude", "sketch": "F1", "d": 5},
                          {"type": "sketch", "plane": "XY", "shapes": [{"rect": {"x": 0, "y": 0, "w": 40, "h": 5}}]}, {"type": "extrude", "sketch": "F3", "d": 40}])
    b.step_part("Housing (STEP)", STEP)
    lib = {k: b.library(*v) for k, v in {
        "M4x25": ("iso4762", "M4", 25), "W4": ("iso7089", "M4"), "N4": ("iso4032", "M4"),
        "M3x12": ("iso4762", "M3", 12), "W3": ("iso7089", "M3"), "N3": ("iso4032", "M3"),
        "M5x20": ("iso4762", "M5", 20), "W5": ("iso7089", "M5"), "608": ("bearing", "608"), "SO": ("standoff-mf", "M3", 10)}.items()}
    print("  parts:", lib)
    # ---- Module A: a plate with 4 M3 screws, washers and nuts under it
    b.assembly("Module A")
    f = b.faces(["Plate A", lib["M3x12"], lib["W3"], lib["N3"]])
    fa = Fasten(b, f, lib["M3x12"], lib["W3"], lib["N3"], 3, 12)
    g = ids()
    b.put(next(g), f["Plate A"]["id"], T(0, 0, 0), fixed=True)
    for hx, hy in [(10, 10), (70, 10), (70, 50), (10, 50)]:
        fa.at(g, hx, hy, 6, 0, "I1", nearest(f["Plate A"]["faces"], ":hole:", hx, hy), "F2:end")
    print("  Module A:", b.done())
    # ---- Bearing block: a block, a 608 bearing in it, a shaft in the bearing, 2 M5 screws with washers on top
    b.assembly("Bearing block")
    f = b.faces(["Block", "Shaft", lib["608"], lib["M5x20"], lib["W5"]])
    g = ids()
    blk = next(g)
    b.put(blk, f["Block"]["id"], T(0, 0, 0), fixed=True)
    brg, sh = next(g), next(g)
    bh = height(f[lib["608"]])
    b.put(brg, f[lib["608"]]["id"], T(30, 20, 20 - bh))
    outer = max((x for x in f[lib["608"]]["faces"] if x["type"] == "cylinder"), key=lambda x: x["r"] or 0)["name"]
    b.mate("axis", brg, outer, blk, nearest(f["Block"]["faces"], ":hole:", 30, 20), centred=True)
    b.put(sh, f["Shaft"]["id"], T(30, 20, 2))
    b.mate("axis", sh, "F2:side:c1", brg, bore(f[lib["608"]]), centred=True)
    shank, under = screw_faces(f[lib["M5x20"]], 5)
    wt = height(f[lib["W5"]])
    for hx in (8, 52):
        s, w = next(g), next(g)
        b.put(w, f[lib["W5"]]["id"], T(hx, 20, 20))
        b.put(s, f[lib["M5x20"]]["id"], T(hx, 20, 20 + wt - 20))
        b.mate("axis", s, shank, blk, nearest(f["Block"]["faces"], ":hole:", hx, 20), centred=True)
        b.mate("axis", w, bore(f[lib["W5"]]), s, shank, centred=True)
    print("  Bearing block:", b.done())
    # ---- the machine
    b.assembly("Machine")
    f = b.faces(["Base", "Plate B", "Column", "L bracket", "Housing (STEP)", lib["SO"], lib["M4x25"], lib["W4"], lib["N4"]])
    fb = Fasten(b, f, lib["M4x25"], lib["W4"], lib["N4"], 4, 25)
    g = ids()
    base = next(g)
    b.put(base, f["Base"]["id"], T(0, 0, 0), fixed=True)
    for k, (x0, y0) in enumerate(pb):
        p = next(g)
        b.put(p, f["Plate B"]["id"], T(x0, y0, 10), **({} if k < 2 else {"fixed": True}))
        if k < 2:  # (two plates held by a touch on the base: they slide on it, their screws go along)
            b.mate("touch", p, "F2:start", base, "F2:end", centred=True)
        for hx, hy in pb_holes:
            fb.at(g, x0 + 60 + hx, y0 + 40 + hy, 18, 0, p, nearest(f["Plate B"]["faces"], ":hole:", 60 + hx, 40 + hy), "F2:end")
    cols = []
    for y in (60, 180, 300):
        c = next(g)
        cols.append(c)
        b.put(c, f["Column"]["id"], T(480, y - 20, 10))
        b.mate("touch", c, "F2:start", base, "F2:end", centred=True)
    for x in (40, 120, 200, 280):
        c = next(g)
        b.put(c, f["L bracket"]["id"], T(x, 345, 10))
        b.mate("touch", c, "F2:start", base, "F2:end", centred=True)
    hb = f["Housing (STEP)"]["bbox"]
    for x in (320, 440):
        b.put(next(g), f["Housing (STEP)"]["id"], T(x - hb[0], 205 - hb[1], 10 - hb[2]), fixed=True)
    so = f[lib["SO"]]["bbox"]
    for x, y in ((8, 8), (592, 8), (8, 392), (592, 392)):
        b.put(next(g), f[lib["SO"]]["id"], T(x, y, 10 - so[2]), fixed=True)
    print("  Machine parts:", b.done())
    for k, (y, c) in enumerate(zip((60, 180, 300), cols)):
        b.call("insert_part", part="Module A")
        b.js("const A = window.__app.assembly, it = A.doc.instances[A.doc.instances.length - 1]; it.matrix = arguments[0]; it.fixed = true", T(460, y - 30, 160))
    for x in (70, 220):
        b.call("insert_part", part="Bearing block")
        b.js("const A = window.__app.assembly, it = A.doc.instances[A.doc.instances.length - 1]; it.matrix = arguments[0]; it.fixed = true", T(x, 280, 10))
    r = b.run("const A = window.__app.assembly; A.commit(); await A.refresh(); return { top: A.doc.instances.length, all: A.flatParts().length, joints: A.doc.mates.length, unmet: A.unmet().length }")
    print("  Machine:", r)
    b.save(out / file, "Machine", "Big assembly 150", demo)


def big500(b, out, file="big-500.a3d", demo=None):
    b.fresh()
    cells = [(x0, y0) for y0 in range(20, 800 - 79, 160) for x0 in range(20, 1200 - 99, 140)][:40]
    holes = [(-30, -20), (30, -20), (30, 20), (-30, 20)]
    pts = [(x0 + 40 + hx - 600, y0 + 30 + hy - 400) for x0, y0 in cells for hx, hy in holes]
    b.plate("Base", 1200, 800, 10, pts, 3.4)
    b.plate("Plate A", 80, 60, 6, holes, 3.4)
    lib = {k: b.library(*v) for k, v in {"M3x20": ("iso4762", "M3", 20), "W3": ("iso7089", "M3"), "N3": ("iso4032", "M3")}.items()}
    b.assembly("Rack")
    f = b.faces(["Base", "Plate A", lib["M3x20"], lib["W3"], lib["N3"]])
    fa = Fasten(b, f, lib["M3x20"], lib["W3"], lib["N3"], 3, 20)
    g = ids()
    base = next(g)
    b.put(base, f["Base"]["id"], T(0, 0, 0), fixed=True)
    for k, (x0, y0) in enumerate(cells):
        p = next(g)
        b.put(p, f["Plate A"]["id"], T(x0, y0, 10), fixed=True)
        for hx, hy in holes:  # (the first two plates' fasteners joined; the rest only placed)
            fa.at(g, x0 + 40 + hx, y0 + 30 + hy, 16, 0, p, nearest(f["Plate A"]["faces"], ":hole:", 40 + hx, 30 + hy), "F2:end", joints=k < 2)
    print("  Rack:", b.done())
    b.save(out / file, "Rack", "Big assembly 500", demo)


def mech30(b, out, n=30, file="mech-30.a3d", demo=None):
    b.fresh()
    xs = [-(n - 1) * 15 + 30 * k for k in range(n)]
    b.model("Gear base", [{"type": "sketch", "plane": "XY", "shapes": [{"rect": {"x": 0, "y": 0, "w": n * 30 + 30, "h": 60}}]}, {"type": "extrude", "sketch": "F1", "d": 10},
                          {"type": "sketch", "plane": {"face": "F2:end"}, "shapes": [{"circle": {"x": x, "y": 0, "d": 8}} for x in xs]},
                          {"type": "extrude", "sketch": "F3", "d": 10}])
    b.model("Disc", [{"type": "sketch", "plane": "XY", "shapes": [{"circle": {"x": 0, "y": 0, "d": 29}}]}, {"type": "extrude", "sketch": "F1", "d": 5},
                     {"type": "hole", "face": "F2:end", "points": [[0, 0]], "d": 8}, {"type": "hole", "face": "F2:end", "points": [[9, 0]], "d": 3}])
    b.assembly("Gear train")
    f = b.faces(["Gear base", "Disc"])
    base = f["Gear base"]
    pins = [nearest(base["faces"], "F4:side", base["bbox"][0] + (base["bbox"][3] - base["bbox"][0]) / 2 + x, 30) for x in xs]
    hole = nearest(f["Disc"]["faces"], ":hole:", 0, 0)
    rim = max((x for x in f["Disc"]["faces"] if x["type"] == "cylinder" and x["name"].startswith("F2:side")), key=lambda x: x["r"] or 0)["name"]
    g = ids()
    b.put(next(g), base["id"], T(0, 0, 0), fixed=True)
    discs = []
    for k, x in enumerate(xs):
        dsc = next(g)
        discs.append(dsc)
        b.put(dsc, f["Disc"]["id"], T(n * 15 + 15 + x, 30, 10))
        b.mate("axis", dsc, hole, "I1", pins[k], centred=True)
        b.mate("touch", dsc, "F2:start", "I1", "F2:end")
    print("  Gear train:", b.done())
    for a, c in zip(discs, discs[1:]):
        b.call("snap_faces", type="gear", move={"part": c, "face": rim}, onto={"part": a, "face": rim})
    if demo:  # (a 🎬 demo: its motion and mechanism named in Czech)
        b.call("name_motion", part=discs[0], motion=0, name="Otáčení prvního kola")
    print(" ", b.call("drive_mechanism", driver={"part": discs[0], "motion": 0}, name=demo["name_cs"] if demo else "Gear train", to=30)[:160])
    b.save(out / file, "Gear train", "Mechanism 30", demo)


if __name__ == "__main__":
    url, out = sys.argv[1], Path(sys.argv[2])
    which = set(sys.argv[3:]) or {"a", "b", "c"}
    b = Builder(url)
    try:
        for k, fn in (("a", big150), ("b", big500), ("c", mech30)):
            if k in which:
                t0 = time.time()
                print(f"{k}: {fn.__name__}")
                fn(b, out)
                print(f"  {time.time() - t0:.0f} s")
    finally:
        b.quit()
