"""Big assemblies stay quick, in headless Edge: the ~150-part benchmark assembly — the 🎬 demo
demos/velka-sestava-150.a3d (tools/make_big_assembly.py a, through tools/make_demos.py; --build: built anew through the
app) — opened on a fresh page and measured — open to the first frame and to interactive (no
long task for 0.5 s), orbit frame rate, hover / pick / select latency, a drag of a part with joints, the joint solve,
collisions, the BOM, an autosave, a version save, JS heap and GPU buffers (estimated), the server's time per endpoint
and kernel call — printed, kept as JSON, and held to budgets.

  A3D_DATA=<a scratch folder> py server.py --port 5199 --no-browser
  PYTHONIOENCODING=utf-8 py tools/e2e_big_assembly.py http://127.0.0.1:5199 <out dir> [--files a.a3d b.a3d …] [--profile] [--gpu] [--build]

--build: the assembly built now through the app (tools/make_big_assembly.py) and saved in <out dir>, not the demo;
--files: measure these .a3d files instead (made before by make_big_assembly.py; no budgets checked, a mechanism file is
driven too); --profile: a CDP CPU profile of opening each (<out>/<name>.cpuprofile, its top functions printed); --gpu:
the machine's GPU (default: WebGL in software, SwiftShader — what the budgets are set for).
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_big_assembly import Builder, big150  # noqa: E402

# budgets for the 150-part assembly in headless Edge. Software GL (SwiftShader, the default): a frame of its 93 000
# triangles with the studio's reflections takes ~150 ms on the CPU (6 fps measured; merging every part into one draw
# call gave only +30 %) — so the frame rate's budget there is low; with a GPU (--gpu) it is 60 fps
BUDGET = {"interactive_s": 8.0, "orbit_fps": 4, "pick_ms": 50, "select_ms": 100, "hover_ms": 50, "drag_move_ms": 50}

URL = sys.argv[1].rstrip("/")
OUT = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
args = sys.argv[3:]
FILES = [Path(a) for a in args[args.index("--files") + 1:] if not a.startswith("--")] if "--files" in args else []
PROFILE = "--profile" in args
GPU = "--gpu" in args  # (the machine's GPU; default: software GL, as the budgets assume)
BUILD = "--build" in args
if GPU:
    BUDGET["orbit_fps"] = 30
DEMO = Path(__file__).resolve().parent.parent / "demos" / "velka-sestava-150.a3d"
fails = []


def check(what, ok, info=""):
    print(("ok   " if ok else "FAIL ") + what + (f" — {info}" if info else ""))
    if not ok:
        fails.append(what)


# in the page: frame times (the view's own render loop), long tasks, rAF callbacks' times
PROBE = """
window.__perf = { long: [], frames: [], rafs: [] };
try { new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__perf.long.push([e.startTime, e.duration]); }).observe({ type: 'longtask', buffered: true }); } catch (e) {}
const raf = window.requestAnimationFrame.bind(window);
window.requestAnimationFrame = (cb) => raf((t) => { const s = performance.now(); cb(t); const d = performance.now() - s;
  if (cb.name !== 'loop') window.__perf.rafs.push([s, d]); });
"""

# the view's frames: when each was drawn and how long renderer.render took
FRAMES = """const v = window.__app.assembly.view, r = v.renderer;
if (!r.__timed) { const render = r.render.bind(r); r.render = (s, c) => { const t = performance.now(); render(s, c); window.__perf.frames.push([t, performance.now() - t]); }; r.__timed = true; }"""


def stats(xs):
    xs = sorted(xs)
    if not xs:
        return {"n": 0}
    return {"n": len(xs), "avg": round(sum(xs) / len(xs), 2), "p50": round(xs[len(xs) // 2], 2), "max": round(xs[-1], 2)}


def top_functions(profile, n=15):
    """A CPU profile's functions by self time -> [(ms, name, where)]."""
    nodes = {x["id"]: x for x in profile["nodes"]}
    dt = {}
    samples, deltas = profile.get("samples", []), profile.get("timeDeltas", [])
    for s, d in zip(samples, deltas):
        dt[s] = dt.get(s, 0) + d
    by = {}
    for nid, us in dt.items():
        cf = nodes[nid]["callFrame"]
        key = (cf["functionName"] or "(anon)", f"{cf['url'].rsplit('/', 1)[-1]}:{cf['lineNumber'] + 1}")
        by[key] = by.get(key, 0) + us
    return [(round(us / 1000, 1), k[0], k[1]) for k, us in sorted(by.items(), key=lambda kv: -kv[1])[:n]]


def measure(b, path, mechanism=False):
    """Open path on a fresh page and measure it -> {metric: value}."""
    d, js = b.d, b.js
    res = {"file": path.name}
    urllib.request.urlopen(f"{URL}/api/timings?reset=1").read()
    b.fresh()
    js(PROBE)
    if PROFILE:
        d.execute_cdp_cmd("Profiler.enable", {})
        d.execute_cdp_cmd("Profiler.setSamplingInterval", {"interval": 200})
        d.execute_cdp_cmd("Profiler.start", {})
    t0 = js("return performance.now()")
    b.d.find_element("id", "projectInput").send_keys(str(path.resolve()))
    # the first frame: every placed part drawn (its body built) and the view rendered once after that
    js("""const t0 = arguments[0]; window.__first = null;
      const look = () => { const A = window.__app.assembly, v = A?.view;
        if (A?.active && A.doc.instances.length && v?.meshes?.length === A.doc.instances.length && !v.dirty) { window.__first = performance.now() - t0; return; }
        requestAnimationFrame(look); };
      look();""", t0)
    end = time.time() + 300
    while time.time() < end and js("return window.__first") is None:
        time.sleep(0.05)
    res["first_frame_s"] = round(js("return window.__first") / 1000, 2)
    time.sleep(4)  # (what runs after: the clash check, panels, thumbnails)
    lt = js("return window.__perf.long.filter(([s]) => s >= arguments[0])", t0)
    tti = t0 + res["first_frame_s"] * 1000
    for s, dur in sorted(lt):
        if s - tti >= 500:
            break
        tti = max(tti, s + dur)
    res["interactive_s"] = round((tti - t0) / 1000, 2)
    res["open_long_tasks"] = {"n": len(lt), "total_ms": round(sum(x[1] for x in lt)), "max_ms": round(max([x[1] for x in lt] or [0]))}
    if PROFILE:
        prof = d.execute_cdp_cmd("Profiler.stop", {})["profile"]
        (OUT / f"{path.stem}.cpuprofile").write_text(json.dumps(prof))
        res["open_top_functions"] = top_functions(prof)
    info = js("""const A = window.__app.assembly, r = A.view.renderer;
      return { top: A.doc.instances.length, all: A.flatParts().length, joints: (A.doc.mates || []).length, calls: r.info.render.calls, triangles: r.info.render.triangles,
        geometries: r.info.memory.geometries, programs: r.info.programs?.length,
        gl: (() => { const g = r.getContext(), x = g.getExtension('WEBGL_debug_renderer_info'); return x ? g.getParameter(x.UNMASKED_RENDERER_WEBGL) : g.getParameter(g.RENDERER); })() };""")
    res.update(info)
    js(FRAMES)

    # ---- orbit: the camera turned a little every frame for 3 s
    js("window.__perf.frames = []")
    js("""const v = window.__app.assembly.view, t = performance.now(); window.__orbit = true;
      const step = () => { if (performance.now() - t > 3000) { window.__orbit = false; return; } v.controls.rotate(0.01, 0.002); v.controls.changed(); requestAnimationFrame(step); };
      requestAnimationFrame(step);""")
    while js("return window.__orbit"):
        time.sleep(0.1)
    fr = js("return window.__perf.frames")
    res["orbit_fps"] = round(len(fr) / 3, 1)
    res["orbit_render_ms"] = stats([x[1] for x in fr])

    # ---- pick: what is under the mouse at the middle of each of 30 placed parts
    pts = js("""const A = window.__app.assembly, v = A.view, r = v.renderer.domElement.getBoundingClientRect(), out = [];
      for (const m of v.shown()) {
        m.geometry.computeBoundingSphere();
        const c = m.geometry.boundingSphere.center.clone().applyMatrix4(m.matrix).project(v.camera);
        const x = r.left + (c.x + 1) / 2 * r.width, y = r.top + (1 - c.y) / 2 * r.height;
        if (x > r.left + 5 && x < r.right - 5 && y > r.top + 5 && y < r.bottom - 5 && v.pickInst(x, y)?.inst === m.userData.inst) out.push([x, y, m.userData.inst]);
      }
      return out;""")
    pts = pts[:: max(1, len(pts) // 30)][:30]
    res["pick_points"] = len(pts)
    res["pick_ms"] = stats(js("""const v = window.__app.assembly.view, out = [];
      for (const [x, y] of arguments[0]) { const t = performance.now(); v.pickInst(x, y); out.push(performance.now() - t); } return out;""", pts))

    # ---- hover: the mouse over one part, then another (the work runs once a frame: its rAF callback timed)
    cv = "window.__app.assembly.view.renderer.domElement"
    js("window.__perf.rafs = []")
    for x, y, _ in pts[:12]:
        js(f"{cv}.dispatchEvent(new PointerEvent('pointermove', {{ clientX: arguments[0], clientY: arguments[1], bubbles: true }}))", x, y)
        time.sleep(0.12)
    res["hover_ms"] = stats([x[1] for x in js("return window.__perf.rafs")])

    # ---- select: a click on a part (press + release, the handlers' time) and its next frame
    sel = []
    for x, y, _ in pts[:8]:
        sel.append(js(f"""const cv = {cv}, o = {{ clientX: arguments[0], clientY: arguments[1], bubbles: true, button: 0, pointerId: 1 }};
          const t = performance.now(); cv.dispatchEvent(new PointerEvent('pointerdown', o)); cv.dispatchEvent(new PointerEvent('pointerup', o)); return performance.now() - t;""", x, y))
        time.sleep(0.15)
    res["select_ms"] = stats(sel)
    js("window.__app.assembly.choose(null)")

    # ---- the joint solve: every joint applied again
    res["solve_ms"] = stats(js("const A = window.__app.assembly, out = []; for (let i = 0; i < 5; i++) { const t = performance.now(); A.applyMates(); out.push(performance.now() - t); } return out;"))
    res["draw_ms"] = stats(js("const A = window.__app.assembly, out = []; for (let i = 0; i < 5; i++) { const t = performance.now(); A.draw(); out.push(performance.now() - t); } return out;"))

    # ---- a drag: a part held by a touch joint (its screws go along) moved 20 steps
    drag = js("""const A = window.__app.assembly, m = (A.doc.mates || []).find((j) => j.type === 'touch' && !A.inst(j.move)?.fixed && (A.doc.mates || []).some((k) => k.onto === j.move));
      return m ? m.move : null""")
    if drag:
        res["drag_part"] = drag
        mv = js("""const A = window.__app.assembly, v = A.view, id = arguments[0], r = v.renderer.domElement.getBoundingClientRect();
          A.choose(id);
          const m = v.meshes.find((x) => x.userData.inst === id); m.geometry.computeBoundingBox();
          const top = m.geometry.boundingBox.max.clone(), lo = m.geometry.boundingBox.min;
          const p = new (top.constructor)((top.x + lo.x) / 2 + (top.x - lo.x) * 0.3, (top.y + lo.y) / 2, top.z).applyMatrix4(m.matrix).project(v.camera);
          return [r.left + (p.x + 1) / 2 * r.width, r.top + (1 - p.y) / 2 * r.height];""", drag)
        times = js(f"""const cv = {cv}, [x, y] = arguments[0], o = (dx) => ({{ clientX: x + dx, clientY: y + dx * 0.3, bubbles: true, button: 0, buttons: 1, pointerId: 1 }}), out = [];
          cv.dispatchEvent(new PointerEvent('pointerdown', o(0)));
          for (let i = 1; i <= 20; i++) {{ const t = performance.now(); window.dispatchEvent(new PointerEvent('pointermove', o(i * 2))); out.push(performance.now() - t); }}
          window.dispatchEvent(new PointerEvent('pointerup', o(40)));
          return out;""", mv)
        res["drag_move_ms"] = stats(times)
        b.run("await window.__app.assembly.history.go(-1);")

    # ---- ▶ a mechanism: driven to 12 places, then played for 3 s
    if mechanism:
        t = []
        for k in range(12):
            t0 = time.time()
            b.call("drive_mechanism", to=k * 30)
            t.append((time.time() - t0) * 1000)
        res["drive_step_ms"] = stats(t)  # (the AI's drive_mechanism: the parts moved, the panels, its answer)
        res["drive_solve_ms"] = stats(js("""const A = window.__app.assembly, m = A.mech.list[0], out = [];
          for (let k = 0; k < 40; k++) { const t = performance.now(); A.moveFree(m.driver.part, m.driver.mo, 3, null, false, true); out.push(performance.now() - t); }
          return out;"""))  # (one step of the driver: the joints, loops and couplings solved, not drawn)
        js("window.__perf.frames = []; window.__perf.rafs = []")
        b.call("drive_mechanism", play=True)
        time.sleep(3)
        b.call("drive_mechanism", play=False)
        res["play_fps"] = round(len(js("return window.__perf.frames")) / 3, 1)
        res["play_step_ms"] = stats([x[1] for x in js("return window.__perf.rafs")])  # (each frame's work: the parts moved, drawn)

    # ---- collisions, the BOM, an autosave, a version
    for key, fn in (("collisions_s", lambda: b.call("check_collisions")), ("bom_s", lambda: b.call("get_bom")),
                    ("autosave_s", lambda: b.run("await window.__app.autosave.saveNow();")),
                    ("version_s", lambda: b.call("save_version", note="bench"))):
        t0 = time.time()
        try:
            fn()
            res[key] = round(time.time() - t0, 2)
        except Exception as e:  # (said, not stopped on)
            res[key] = f"error: {str(e)[:120]}"
    res["project_json_kB"] = js("return Math.round(JSON.stringify(window.__app.autosave.hooks.project()).length / 1024)")

    # ---- memory: the JS heap; the GPU's buffers estimated from the geometries drawn (each once)
    res["js_heap_MB"] = js("return performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1048576) : null")
    res["gpu_buffers_MB"] = js("""const seen = new Set(); let n = 0;
      window.__app.assembly.view.scene.traverse((o) => { const g = o.geometry; if (!g) return;
        for (const a of [...Object.values(g.attributes), g.index].filter(Boolean)) { const arr = a.array || a.data?.array; if (arr && !seen.has(arr)) { seen.add(arr); n += arr.byteLength; } }
        if (o.isInstancedMesh && !seen.has(o.instanceMatrix.array)) { seen.add(o.instanceMatrix.array); n += o.instanceMatrix.array.byteLength; } });
      return Math.round(n / 1048576 * 10) / 10;""")
    res["server"] = {k: v for k, v in json.loads(urllib.request.urlopen(f"{URL}/api/timings").read()).items()
                     if not any(w in k for w in ("/agent/", "/chat/", "/ai/", "/timings")) and v["ms"] >= 5}  # (the long polls left out)
    return res


def show(res):
    print(f"\n== {res['file']}: {res.get('top')} placed ({res.get('all')} with the sub-assemblies' parts), {res.get('joints')} joints, "
          f"{res.get('calls')} draw calls, {res.get('triangles')} triangles")
    for k, v in res.items():
        if k in ("file", "server", "open_top_functions"):
            continue
        print(f"  {k:22} {v}")
    print("  server (slowest first):")
    for k, v in res["server"].items():
        print(f"    {k:40} n {v['n']:4}  total {v['ms']:9} ms  max {v['max_ms']:8} ms  {v['bytes'] // 1024} kB")
    for row in res.get("open_top_functions", []):
        print(f"    {row[0]:8} ms  {row[1]}  {row[2]}")


b = Builder(URL, software_gl=not GPU)
b.d.execute_cdp_cmd("Performance.enable", {})
try:
    results = []
    if FILES:
        for f in FILES:
            r = measure(b, f, mechanism=f.stem.startswith("mech"))
            show(r)
            results.append(r)
    else:
        f = DEMO
        if BUILD or not DEMO.exists():
            t0 = time.time()
            big150(b, OUT)
            print(f"built the 150-part assembly in {time.time() - t0:.0f} s")
            f = OUT / "big-150.a3d"
        r = measure(b, f)
        show(r)
        results.append(r)
        check(f"interactive in under {BUDGET['interactive_s']} s", r["interactive_s"] < BUDGET["interactive_s"], r["interactive_s"])
        check(f"orbit at {BUDGET['orbit_fps']} fps or more", r["orbit_fps"] >= BUDGET["orbit_fps"], r["orbit_fps"])
        check(f"pick under {BUDGET['pick_ms']} ms", r["pick_ms"].get("max", 1e9) < BUDGET["pick_ms"], r["pick_ms"])
        check(f"hover under {BUDGET['hover_ms']} ms", r["hover_ms"].get("p50", 1e9) < BUDGET["hover_ms"], r["hover_ms"])
        check(f"select under {BUDGET['select_ms']} ms", r["select_ms"].get("p50", 1e9) < BUDGET["select_ms"], r["select_ms"])
        check(f"a drag step under {BUDGET['drag_move_ms']} ms", r.get("drag_move_ms", {}).get("p50", 1e9) < BUDGET["drag_move_ms"], r.get("drag_move_ms"))
        unmet = b.js("return window.__app.assembly.unmet().length")
        check("every part drawn, every joint holds", r["top"] > 90 and unmet == 0, f"{r['top']} placed, {unmet} not held")
        check("collisions, BOM, autosave and a version: no error", all(isinstance(r[k], float) for k in ("collisions_s", "bom_s", "autosave_s", "version_s")),
              {k: r[k] for k in ("collisions_s", "bom_s", "autosave_s", "version_s")})
    (OUT / "big_assembly_results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
finally:
    errs = [e["message"] for e in b.d.get_log("browser") if e["level"] == "SEVERE" and "favicon" not in e["message"]] if hasattr(b.d, "get_log") else []
    if not FILES:
        check("no console errors", not errs, errs[:3])
    b.quit()
print("FAILED:" if fails else "ALL OK", fails if fails else "")
sys.exit(1 if fails else 0)
