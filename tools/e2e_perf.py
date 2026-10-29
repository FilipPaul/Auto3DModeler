"""How quick the app feels, in headless Edge with real input (Chrome DevTools Protocol mouse events): for each scenario
the main-thread time of each action (CDP Performance.getMetrics: TaskDuration / ScriptDuration), its long tasks
(PerformanceObserver 'longtask', over 50 ms: count, total, worst) and the server requests it made (Resource Timing,
/api/… only). With --profile also the JavaScript functions that took the time (CDP Profiler: self and total ms per
function, the app's own files first).

Scenarios (pick with a comma separated list as the 3rd argument; default all):
  model     a 3D model of 29 steps (sketches, holes, patterns, a fillet, a chamfer, text; 9 threaded holes cut for real:
            236 000 triangles): built, opened, a dimension edited, the mouse over faces / edges (hover marks, snap points), the view turned, a face picked,
            Ctrl-picked, the suggestions opened;
  big       the 44 MB imported board (data/imports/45c51541a12d03a8.step, or pass --big=<path>): opened, turned, hovered, measured;
  asm       MIT E Vent (13 parts / 41 placements) opened as an assembly: hovered, parts chosen, explode slider moved,
            collisions checked, the BOM opened; then the Festo valve the same (hover and choose);
  sketch    Drive Gear.dxf as a sketch (732 shapes): hovered, box-selected, a line dragged;
  sheet     the Festo valve assembly's drawing sheet (title block, parts list): hovered, zoomed, panned, a dimension dragged;
  idle      the app idle with 3 tabs open (a model, an assembly, a sketch) for 10 s: the main-thread time it spends.

usage (server running with its own data folder, e.g. `A3D_DATA=<scratch> py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_perf.py http://127.0.0.1:5199 <out dir> [model,big,asm,sketch,sheet,idle] [--profile[=<word>]] [--big=<a .step>]
Writes <out dir>/perf.json (the numbers of each action) and prints a table.
"""
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests
from selenium import webdriver
from selenium.webdriver.common.by import By

ROOT = Path(__file__).resolve().parent.parent
args = [a for a in sys.argv[1:] if not a.startswith("--")]
flags = {a.split("=")[0]: (a.split("=", 1)[1] if "=" in a else True) for a in sys.argv[1:] if a.startswith("--")}
URL, OUT = args[0], args[1]
ONLY = args[2].split(",") if len(args) > 2 else ["model", "big", "asm", "sketch", "sheet", "idle"]
PROFILE = flags.get("--profile")  # True: every action; a word: the actions whose name has it
BIG = flags.get("--big") or str(ROOT / "data" / "imports" / "45c51541a12d03a8.step")
if not os.path.exists(BIG):  # (a worktree has no data folder: the main checkout's)
    BIG = str(ROOT.parent.parent.parent / "data" / "imports" / "45c51541a12d03a8.step") if ".claude" in str(ROOT) else BIG
SAMPLES = ROOT / "samples" / "ToImportToOurApp"
EVENT = SAMPLES / "freecad-library" / "MIT E Vent Pre Production Model.step"
FESTO = SAMPLES / "freecad-library" / "VALVULA 5-2 VIAS PNEUMATICA SIMPLES SOLENOIDE.STEP"
GEAR = SAMPLES / "drawings" / "Drive Gear.dxf"
os.makedirs(OUT, exist_ok=True)
M = "window.__app.modeler"
A = "window.__app.assembly"
H = "window.__app.agentHandlers"

# every long task (> 50 ms) since the page opened, kept in window.__lt
LONGTASKS = """
window.__lt = [];
try { new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__lt.push([e.startTime, e.duration]); }).observe({ type: 'longtask', buffered: true }); } catch (e) {}
"""

opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
d.set_script_timeout(900)
cfg = getattr(d.command_executor, "_client_config", None)
if cfg is not None:
    cfg.timeout = 1000
js = d.execute_script
cdp = d.execute_cdp_cmd
cdp("Page.addScriptToEvaluateOnNewDocument", {"source": LONGTASKS})
cdp("Performance.enable", {"timeDomain": "timeTicks"})
results = []  # [{scenario, action, wall, task, script, lt_n, lt_ms, lt_max, api: [[path, ms]], top}]


def wait(script, t=120, *a):
    end = time.time() + t
    while time.time() < end:
        v = js(script, *a)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def call(tool_name, **kw):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, kw)


def metrics():
    m = {x["name"]: x["value"] for x in cdp("Performance.getMetrics", {})["metrics"]}
    return m.get("TaskDuration", 0), m.get("ScriptDuration", 0)


def frames(n=2):
    """n frames drawn (or 30 s gone: a page that draws no more is reported, not waited for) -> ms."""
    return d.execute_async_script("""const [k0, done] = arguments, t = performance.now(); let k = k0;
      const tm = setTimeout(() => done(-1), 30000), f = () => (--k > 0 ? requestAnimationFrame(f) : (clearTimeout(tm), done(performance.now() - t)));
      requestAnimationFrame(f);""", n)


def top_functions(profile, n=8):
    """The app's functions that took the time: self ms and total ms (the time with what they called)."""
    nodes = {x["id"]: x for x in profile["nodes"]}
    parent = {}
    for x in profile["nodes"]:
        for c in x.get("children", []):
            parent[c] = x["id"]
    selfms, total = defaultdict(float), defaultdict(float)
    key = lambda nd: (nd["callFrame"]["functionName"] or "(anon)", nd["callFrame"]["url"].split("/js/")[-1] if "/js/" in nd["callFrame"]["url"] else nd["callFrame"]["url"].split("/")[-1], nd["callFrame"]["lineNumber"] + 1)
    for sid, dt in zip(profile.get("samples", []), profile.get("timeDeltas", [])):
        ms = dt / 1000
        nd = nodes[sid]
        if nd["callFrame"]["functionName"] in ("(idle)", "(program)", "(root)"):
            continue
        selfms[key(nd)] += ms
        seen, k = set(), sid
        while k is not None:
            kk = key(nodes[k])
            if kk not in seen and "/js/" in nodes[k]["callFrame"]["url"]:
                seen.add(kk)
                total[kk] += ms
            k = parent.get(k)
    own = lambda k: "vendor" not in k[1]
    app = sorted(((v, k) for k, v in total.items() if own(k)), reverse=True)[:n]
    hot = sorted(((v, k) for k, v in selfms.items()), reverse=True)[:n]
    return {"total": [[f"{k[0]} {k[1]}:{k[2]}", round(v)] for v, k in app], "self": [[f"{k[0]} {k[1]}:{k[2]}", round(v)] for v, k in hot]}


class measure:
    """with measure(scenario, action): … -> one row of results (main-thread time, long tasks, server requests)."""

    def __init__(self, scenario, action):
        self.s, self.a = scenario, action
        self.prof = PROFILE is True or (isinstance(PROFILE, str) and PROFILE in action)

    def __enter__(self):
        js("performance.clearResourceTimings(); performance.setResourceTimingBufferSize(5000)")
        self.lt0 = js("return window.__lt.length")
        if self.prof:
            cdp("Profiler.enable", {})
            cdp("Profiler.setSamplingInterval", {"interval": 1000})
            cdp("Profiler.start", {})
        self.m0 = metrics()
        self.t0 = time.time()
        return self

    def __exit__(self, *exc):
        if exc[0]:
            if self.prof:
                cdp("Profiler.stop", {})
            return False
        frames(3)  # (the frame the action asked for drawn)
        wall = (time.time() - self.t0) * 1000
        m1 = metrics()
        lt = js("return window.__lt.slice(arguments[0])", self.lt0)
        api = js("return performance.getEntriesByType('resource').filter(e => e.name.includes('/api/')).map(e => [new URL(e.name).pathname, Math.round(e.duration)])")
        row = {"scenario": self.s, "action": self.a, "wall": round(wall), "task": round((m1[0] - self.m0[0]) * 1000),
               "script": round((m1[1] - self.m0[1]) * 1000), "lt_n": len(lt), "lt_ms": round(sum(x[1] for x in lt)),
               "lt_max": round(max([x[1] for x in lt] or [0])), "api": api}
        if self.prof:
            row["top"] = top_functions(cdp("Profiler.stop", {})["profile"])
        results.append(row)
        apis = ", ".join(f"{p.replace('/api/', '')} {ms}" for p, ms in api[:6]) + (f" … +{len(api) - 6}" if len(api) > 6 else "")
        print(f"  {self.a:34} wall {row['wall']:6} | main thread {row['task']:6} ms (js {row['script']:6}) | long tasks {row['lt_n']:3} = {row['lt_ms']:6} ms, worst {row['lt_max']:5}"
              + (f" | api: {apis}" if api else ""), flush=True)
        if self.prof:
            print("      total:", "; ".join(f"{f} {ms}" for f, ms in row["top"]["total"][:6]))
            print("      self: ", "; ".join(f"{f} {ms}" for f, ms in row["top"]["self"][:6]))
        return False


# ---------------------------------------------------------------- real input (CDP: the browser's own mouse events)
def mouse(kind, x, y, button="none", buttons=0, mods=0, count=0):
    cdp("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": y, "button": button, "buttons": buttons, "modifiers": mods, "clickCount": count})


def sweep(rect, n=80, rows=4):
    """The mouse across a canvas in rows, n moves (as a user looking around the part)."""
    x0, y0, w, h = rect
    for i in range(n):
        r, k = divmod(i, n // rows)
        mouse("mouseMoved", x0 + w * (0.2 + 0.6 * k / (n // rows)), y0 + h * (0.3 + 0.4 * r / max(rows - 1, 1)))


def orbit(rect, steps=40, button="left"):
    """A drag across the view (left: turn; right: pan)."""
    x0, y0, w, h = rect
    cx, cy = x0 + w / 2, y0 + h / 2
    bt = {"left": 1, "right": 2, "middle": 4}[button]
    mouse("mouseMoved", cx, cy)
    mouse("mousePressed", cx, cy, button, bt, count=1)
    for i in range(steps):
        mouse("mouseMoved", cx + 6 * (i + 1), cy + 2 * (i + 1), button, bt)
    mouse("mouseReleased", cx + 6 * steps, cy + 2 * steps, button, 0, count=1)


def click(x, y, mods=0):
    mouse("mouseMoved", x, y)
    mouse("mousePressed", x, y, "left", 1, mods, 1)
    mouse("mouseReleased", x, y, "left", 0, mods, 1)


def wheel(x, y, dy, n=10):
    for _ in range(n):
        cdp("Input.dispatchMouseEvent", {"type": "mouseWheel", "x": x, "y": y, "deltaX": 0, "deltaY": dy})


def rect_of(sel):
    return js("const r = document.querySelector(arguments[0]).getBoundingClientRect(); return [r.left, r.top, r.width, r.height]", sel)


def part_point(view, frac):
    """A point on the part (from the screen: the middle of the part's box, frac across) -> client x, y."""
    return js(f"""const v = {view}, P = v.camera.position.constructor, b = new (v.fitBox().constructor)(); b.copy(v.fitBox());
      const c = b.getCenter(new P()), s = b.getSize(new P()), [fx, fy, fz] = arguments[0];
      return v.toScreen(new P(b.min.x + s.x * fx, b.min.y + s.y * fy, b.min.z + s.z * fz));""", frac)


def settled_model():
    time.sleep(0.2)
    wait(f"return !{M}.inflight && !{M}.building")


def fresh():
    d.get(URL)
    wait("return !!window.__app")
    js("window.confirm = () => true")


def open_cad(path, label):
    """Open → CAD file as the app does; answer 'Open as an assembly' / 'Open as one body'."""
    d.find_element(By.ID, "cadInput").send_keys(str(path))
    end = time.time() + 600
    while time.time() < end:
        q = js("return document.querySelector('.choose p')?.textContent || null")
        if q:
            next(b for b in d.find_elements(By.CSS_SELECTOR, ".choose .btn") if b.text.strip().startswith(label)).click()
            return
        if js("return window.__app.state.workspace === 'assembly' || window.__app.state.workspace === 'drawing'"):
            return
        time.sleep(0.1)


# ---------------------------------------------------------------- scenario 1: a 3D model of ~30 steps
def ref(kind, **kw):
    r = call("find_refs", kind=kind, **kw)
    return json.loads(r)[0]["name" if kind == "face" else "ref"]


def build_model():
    call("new_model", name="Perf block")

    def add(**kw):
        r = call("add_feature", **kw)
        if r.startswith("ERROR") or '"ok":false' in r.replace(" ", ""):
            print("   ", kw["type"], r[:140].replace("\n", " "))
    add(type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 120, "h": 80}}])  # F1
    add(type="extrude", sketch="F1", d=20)  # F2
    top = ref("face", normal=[0, 0, 1], extreme="max")
    add(type="hole", face=top, points=[[-50, -30], [50, -30], [50, 30], [-50, 30]], thread="M5")  # F3
    add(type="sketch", plane={"face": top}, shapes=[{"circle": {"x": 0, "y": 0, "d": 36}}])  # F4
    add(type="extrude", sketch="F4", d=15)  # F5
    boss = ref("face", normal=[0, 0, 1], extreme="max")
    add(type="hole", face=boss, points=[[0, 0]], d=12)  # F6
    add(type="hole", face=boss, points=[[13, 0]], d=3, depth=8)  # F7
    add(type="pattern", of=["F7"], kind="circular", axis={"o": [60, 40, 0], "d": [0, 0, 1]}, count=6)  # F8
    add(type="hole", face=top, points=[[-40, -15]], d=4, depth=8)  # F9
    add(type="pattern", of=["F9"], kind="linear", dir="y", count=4, spacing=10)  # F10
    add(type="pattern", of=["F9", "F10"], kind="linear", dir="x", count=2, spacing=80)  # F11
    add(type="sketch", plane={"face": top}, shapes=[{"slot": {"x1": -20, "y1": -32, "x2": 20, "y2": -32, "w": 6}}])  # F12
    add(type="extrude", sketch="F12", d=4, op="cut")  # F13
    front = ref("face", normal=[0, -1, 0], extreme="max")
    add(type="sketch", plane={"face": front}, shapes=[{"circle": {"x": -30, "y": 0, "d": 8}}])  # F14
    add(type="extrude", sketch="F14", d=30, op="cut")  # F15
    add(type="pattern", of=["F15"], kind="linear", dir="x", count=3, spacing=30)  # F16
    right = ref("face", normal=[1, 0, 0], extreme="max")
    add(type="sketch", plane={"face": right}, shapes=[{"rect": {"x": -20, "y": -5, "w": 40, "h": 8}}])  # F17
    add(type="extrude", sketch="F17", d=6, op="cut")  # F18
    corners = [ref("edge", near=c, circular=False, limit=1) for c in ([0, 0, 10], [120, 0, 10], [120, 80, 10], [0, 80, 10])]
    add(type="fillet", edges=corners, r=6)  # F19
    rim = ref("edge", near=[78, 40, 35], circular=True, limit=1)
    add(type="chamfer", edges=[rim], d=1.5)  # F20
    add(type="hole", face=top, points=[[-20, 25], [20, 25]], thread="M6")  # F21
    left = ref("face", normal=[-1, 0, 0], extreme="max")
    add(type="hole", face=left, points=[[15, 0], [-15, 0]], thread="M4", depth=12)  # F22
    add(type="sketch", plane={"datum": "XY", "offset": 20}, shapes=[{"rect": {"x": 85, "y": 55, "w": 20, "h": 15}}])  # F23
    add(type="extrude", sketch="F23", d=8)  # F24
    add(type="hole", face=ref("face", normal=[0, 0, 1], near=[95, 62, 28], limit=1), points=[[0, 0]], thread="M5")  # F25
    add(type="sketch", plane="XY", shapes=[{"circle": {"x": 25, "y": 60, "d": 10}}])  # F26
    add(type="extrude", sketch="F26", d=6, op="cut")  # F27
    add(type="point", at={"corner": [0, 0, 20]})  # F28
    add(type="decal", face=top, text="A3D", h=6, op="cut", depth=0.5, at=[30, -10])  # F29
    settled_model()
    return js(f"return {M}.part.features.length"), js(f"return {M}.result.ok"), js(f"return ({M}.result.issues || []).length")


def scenario_model():
    print("== model: a 3D model of ~30 steps", flush=True)
    fresh()
    with measure("model", "build 29 steps (AI tools)"):
        n, ok, issues = build_model()
    with measure("model", "threads real (9 holes)"):
        print("   ", call("set_look", threads="real")[:160])
        settled_model()
    print(f"   steps {n}, ok {ok}, issues {issues}, faces", js(f"return {M}.result.body.faces.length"), "triangles", js(f"return {M}.result.body.face_ids.length"))
    feats = js(f"return structuredClone({M}.part)")
    with open(os.path.join(OUT, "perf_model.json"), "w", encoding="utf-8") as fh:  # (the part, to time it on the server alone)
        json.dump(feats, fh)
    fresh()
    call("new_model", name="Perf block again")
    with measure("model", "open (rebuild, kernel kept)"):
        d.execute_async_script(f"const [p, done] = arguments; {M}.part.features = p.features; {M}.part.threads = p.threads; {M}.rebuild().then(() => done())", feats)
        settled_model()
    js(f"{M}.view.setView('iso')")
    frames()
    with measure("model", "edit a dimension (F2 d 20 -> 22)"):  # (the AI's edit: it waits for the threads' cut too)
        call("edit_feature", id="F2", fields={"d": 22})
        settled_model()
        wait(f"return !{M}.threading", 300)
    vp = rect_of("#modelViewport canvas")
    # 🔩 an edit in the panel: the part shows at once with thread lines, the real threads come when cut (cutThreads)
    for label, fid, k, v in (("edit a later step (F29 text depth)", "F29", "depth", 0.6), ("edit a thread (F21 M6 -> M8)", "F21", "thread", "M8")):
        with measure("model", label + ": shown"):
            js(f"const f = {M}.part.features.find(g => g.id === arguments[0]); f[arguments[1]] = arguments[2]; {M}.commit()", fid, k, v)
            settled_model()
        print("    threads pending:", js(f"return !!{M}.result.threads?.real?.pending"), "| the Part panel:", js("return document.querySelector('#modelRight .mp-thr-pending')?.textContent"), "| jobs:",
              js("return fetch('/api/jobs').then(r => r.json()).then(j => (j.jobs || j).map(x => x.kind))") if js(f"return !!{M}.threading") else "-")
        if js(f"return !!{M}.threading"):
            with measure("model", "  hover 40 moves while the threads cut"):
                sweep(vp, 40)
        with measure("model", "  … the real threads in"):
            wait(f"return !{M}.threading", 300)
        print("    real:", js(f"return {M}.result.threads.real"), "| triangles", js(f"return {M}.result.body.face_ids.length"))
    with measure("model", "hover 80 moves"):
        sweep(vp, 80)
    with measure("model", "orbit (40 moves)"):
        orbit(vp, 40)
        time.sleep(0.6)  # (the turn slows down)
    js(f"{M}.view.setView('iso')")
    frames()
    x, y = part_point(f"{M}.view", [0.3, 0.35, 1])
    with measure("model", "click a face (select + suggestions)"):
        click(x, y)
    x2, y2 = part_point(f"{M}.view", [0.75, 0.3, 1])
    with measure("model", "Ctrl-click a second face"):
        click(x2, y2, mods=2)
    print("   suggestions shown:", js("return document.querySelectorAll('#modelViewport .view-suggest .vs-list button').length"))


# ---------------------------------------------------------------- scenario 2: the big imported board
def scenario_big():
    print("== big: the 44 MB board", flush=True)
    if not os.path.exists(BIG):
        print("   no", BIG)
        return
    fresh()
    t0 = time.time()
    with open(BIG, "rb") as fh:
        blob = requests.post(URL + "/api/model/import", files={"file": (os.path.basename(BIG), fh)}, timeout=900).json()["blob"]
    print(f"   import (server, kept after the first time) {time.time() - t0:.1f} s")
    call("new_model", name="Board")
    with measure("big", "open (build + show)"):
        d.execute_async_script(f"const [f, done] = arguments; {M}.part.features = f; {M}.rebuild().then(() => done())", [{"id": "B1", "type": "solid", "blob": blob}])
        settled_model()
    print("   faces", js(f"return {M}.result.body.faces.length"), "triangles", js(f"return {M}.result.body.face_ids.length"), "edges", js(f"return {M}.result.body.edges.length"))
    js(f"{M}.view.setView('iso')")
    frames()
    vp = rect_of("#modelViewport canvas")
    with measure("big", "orbit (40 moves)"):
        orbit(vp, 40)
        time.sleep(0.6)
    js(f"{M}.view.setView('top')")
    frames()
    with measure("big", "hover 40 moves"):
        sweep(vp, 40)
    x, y = part_point(f"{M}.view", [0.4, 0.45, 1])
    with measure("big", "click a face"):
        click(x, y)
    js(f"{M}.dropSuggest?.()")
    with measure("big", "measure: on, 20 moves, 2 clicks"):
        js(f"{M}.toggleMeasure()")
        sweep(vp, 20, rows=2)
        click(*part_point(f"{M}.view", [0.3, 0.3, 1]))
        click(*part_point(f"{M}.view", [0.7, 0.6, 1]))
    js(f"{M}.toggleMeasure()")


# ---------------------------------------------------------------- scenario 3: assemblies
def asm_open(path, scen):
    with measure(scen, f"open {path.name[:24]} as an assembly"):
        open_cad(path, "Open as an assembly")
        wait(f"return window.__app.state.workspace === 'assembly' && {A}.doc.instances.length > 0 && {A}.doc.instances.every(i => {A}.bodyOf(i)?.body)", 900)
    print("   parts", js("return window.__app.project.parts.filter(p => p.kind === 'model').length"), "placements", js(f"return {A}.flatParts().length"),
          "triangles", js(f"return ({A}.view.meshes || []).reduce((n, m) => n + m.userData.faceIds.length, 0)"))


def scenario_asm():
    print("== asm: MIT E Vent and the Festo valve as assemblies", flush=True)
    fresh()
    asm_open(EVENT, "asm")
    js(f"{A}.view.setView('iso')")
    frames()
    time.sleep(1.5)  # (the first quick clash check)
    vp = rect_of("#asmViewport canvas")
    with measure("asm", "hover 80 moves"):
        sweep(vp, 80)
    with measure("asm", "orbit (40 moves)"):
        orbit(vp, 40)
        time.sleep(0.6)
    js(f"{A}.view.setView('iso')")
    frames()
    with measure("asm", "choose 3 parts (clicks)"):
        for f in ([0.4, 0.4, 0.6], [0.6, 0.5, 0.5], [0.5, 0.3, 0.7]):
            click(*part_point(f"{A}.view", f))
    print("   chosen:", js(f"return {A}.sel"))
    with measure("asm", "explode slider (20 steps)"):
        for k in range(1, 21):
            js("const r = document.querySelector('.as-explode input'); r.value = arguments[0]; r.dispatchEvent(new Event('input', {bubbles: true}))", k / 20)
            frames(1)
    with measure("asm", "explode back to 0"):
        js("const r = document.querySelector('.as-explode input'); r.value = 0; r.dispatchEvent(new Event('input', {bubbles: true}))")
    with measure("asm", "check collisions"):
        d.execute_async_script(f"const done = arguments[0]; {A}.checkClashes(false).then(() => done(), () => done())")
    print("   clashes:", js(f"return ({A}.clashes || []).length"))
    with measure("asm", "open the BOM"):
        js(f"{A}.openBom()")
        wait("return document.querySelectorAll('.bom-win tbody tr').length > 0", 30)
    print("   BOM rows:", js("return document.querySelectorAll('.bom-win tbody tr').length"))
    js("document.querySelector('.bom-win [data-a=close], .bom-win .close')?.click()")
    if FESTO.exists():
        fresh()
        asm_open(FESTO, "festo")
        js(f"{A}.view.setView('iso')")
        frames()
        time.sleep(1.5)
        vp = rect_of("#asmViewport canvas")
        with measure("festo", "hover 80 moves"):
            sweep(vp, 80)
        with measure("festo", "choose 3 parts (clicks)"):
            for f in ([0.4, 0.4, 0.6], [0.6, 0.5, 0.5], [0.5, 0.3, 0.7]):
                click(*part_point(f"{A}.view", f))


# ---------------------------------------------------------------- scenario 4: a sketch of ~500 shapes
def scenario_sketch():
    print("== sketch: Drive Gear.dxf as a sketch", flush=True)
    fresh()
    d.find_element(By.ID, "cadInput").send_keys(str(GEAR))
    wait("return window.__app.state.workspace === 'drawing'", 120)
    time.sleep(0.5)
    with measure("sketch", "use as a sketch (DXF -> sketch)"):
        d.find_element(By.CSS_SELECTOR, "#dwgRight [data-use=sketch]").click()
        wait(f"return window.__app.state.workspace === 'model' && !{M}.inflight", 300)
    sid = js(f"return {M}.part.features[0].id")
    print("   shapes:", js(f"return {M}.part.features[0].entities.length"))
    with measure("sketch", "edit the sketch (open)"):
        js(f"{M}.edit(arguments[0])", sid)
        wait(f"return {M}.mode === 'sketch' && !!{M}.sk", 60)
        time.sleep(0.3)
    vp = rect_of("#modelViewport canvas")
    with measure("sketch", "hover 80 moves"):
        sweep(vp, 80)
    bb = js(f"""const s = {M}.sk, ps = []; for (const e of s.f.entities) {{ if (e.a) ps.push(s.P(e.a)); if (e.c) ps.push(s.P(e.c)); }}
      return [Math.min(...ps.map(p => p[0])), Math.min(...ps.map(p => p[1])), Math.max(...ps.map(p => p[0])), Math.max(...ps.map(p => p[1]))]""")
    scr = lambda u, v: js(f"return {M}.view.uvToScreen({M}.frame(), arguments[0])", [u, v])
    a, b = [vp[0] + vp[2] - 20, vp[1] + 20], scr((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2)  # (from the corner, right to left: what it touches)
    with measure("sketch", "box-select a quarter (20 moves)"):
        mouse("mouseMoved", *a)
        mouse("mousePressed", *a, "left", 1, count=1)
        for i in range(1, 21):
            mouse("mouseMoved", a[0] + (b[0] - a[0]) * i / 20, a[1] + (b[1] - a[1]) * i / 20, "left", 1)
        mouse("mouseReleased", *b, "left", 0, count=1)
        time.sleep(0.3)
    print("   picked:", js(f"return ({M}.sk.picks || []).length"))
    js("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape'}))")
    p = js(f"const s = {M}.sk, e = s.f.entities.find(e => e.t === 'line'); if (!e) return null; const a = s.P(e.a), b = s.P(e.b); return [a[0] * 0.7 + b[0] * 0.3, a[1] * 0.7 + b[1] * 0.3]")
    if p:
        q = scr(*p)
        with measure("sketch", "drag a line (20 moves)"):
            mouse("mouseMoved", *q)
            mouse("mousePressed", *q, "left", 1, count=1)
            for i in range(1, 21):
                mouse("mouseMoved", q[0] + i, q[1] + i / 2, "left", 1)
            mouse("mouseReleased", q[0] + 20, q[1] + 10, "left", 0, count=1)
            time.sleep(0.5)


# ---------------------------------------------------------------- scenario 5: an assembly's drawing sheet
def scenario_sheet():
    print("== sheet: an assembly's drawing sheet", flush=True)
    fresh()
    open_cad(FESTO, "Open as an assembly")
    wait(f"return window.__app.state.workspace === 'assembly' && {A}.doc.instances.length > 0 && {A}.doc.instances.every(i => {A}.bodyOf(i)?.body)", 900)
    name = js("return window.__app.project.current.name")
    with measure("sheet", "open the assembly's sheet"):
        r = call("sheet_open", part=name)
        wait("return window.__app.state.workspace === 'sheet'", 300)
        time.sleep(0.5)
    print("   ", r[:100].replace("\n", " "))
    vp = rect_of("#shViewport")
    cx, cy = vp[0] + vp[2] / 2, vp[1] + vp[3] / 2
    with measure("sheet", "hover 60 moves"):
        sweep(vp, 60)
    with measure("sheet", "zoom (10 wheel steps in, 10 out)"):
        wheel(cx, cy, -120)
        wheel(cx, cy, 120)
    with measure("sheet", "pan (right drag, 30 moves)"):
        mouse("mouseMoved", cx, cy)
        mouse("mousePressed", cx, cy, "middle", 4, count=1)
        for i in range(30):
            mouse("mouseMoved", cx + 3 * i, cy + i, "middle", 4)
        mouse("mouseReleased", cx + 90, cy + 30, "middle", 0, count=1)
    dim = js("const t = document.querySelector('#shViewport .sh-dim text, #shViewport [data-dim] text'); if (!t) return null; const r = t.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]")
    if dim:
        with measure("sheet", "drag a dimension (20 moves)"):
            mouse("mouseMoved", *dim)
            mouse("mousePressed", *dim, "left", 1, count=1)
            for i in range(1, 21):
                mouse("mouseMoved", dim[0], dim[1] + i, "left", 1)
            mouse("mouseReleased", dim[0], dim[1] + 20, "left", 0, count=1)
    else:
        print("   (no dimension on the sheet to drag)")


# ---------------------------------------------------------------- scenario 6: the idle app
def scenario_idle():
    print("== idle: 3 tabs open, nothing done for 10 s", flush=True)
    fresh()
    call("new_model", name="Idle model")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("new_assembly", name="Idle assembly")
    js(f"return {A}.insert(window.__app.project.parts.find(p => p.name === 'Idle model').id)")
    time.sleep(0.5)
    call("new_model", name="Idle sketch")
    settled_model()
    time.sleep(2)
    for where in ("model", "assembly"):
        if where == "assembly":
            call("open_part", name="Idle assembly")
            time.sleep(2)
        with measure("idle", f"10 s idle ({where} open)"):
            time.sleep(10)
        with measure("idle", f"10 s idle, mouse resting on the view ({where})"):
            vp = rect_of("#modelViewport canvas" if where == "model" else "#asmViewport canvas")
            mouse("mouseMoved", vp[0] + vp[2] / 2, vp[1] + vp[3] / 2)
            time.sleep(10)


try:
    for name in ONLY:
        t0 = time.time()
        try:
            globals()[f"scenario_{name}"]()
        except Exception as e:  # (a scenario that broke: the others still run)
            import traceback
            traceback.print_exc()
            print(f"   {name} FAILED: {e}")
        print(f"   ({time.time() - t0:.0f} s)")
    errs = [m["message"][:160] for m in d.get_log("browser") if m["level"] == "SEVERE" and "favicon" not in m["message"]]
    print("console errors:", errs[:5])
finally:
    d.quit()
    with open(os.path.join(OUT, "perf.json"), "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=1)
    print()
    print(f"{'scenario':8} {'action':36} {'main ms':>8} {'long tasks':>11} {'ms':>7} {'worst':>6}")
    for r in results:
        print(f"{r['scenario']:8} {r['action'][:36]:36} {r['task']:8} {r['lt_n']:11} {r['lt_ms']:7} {r['lt_max']:6}")
