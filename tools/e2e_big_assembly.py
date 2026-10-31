"""Big assemblies stay quick, in headless Edge: the ~150-part benchmark assembly — the 🎬 demo
demos/velka-sestava-150.a3d (tools/make_big_assembly.py a, through tools/make_demos.py; --build: built anew through the
app) — opened on a fresh page and measured — open to the first frame and to interactive (no
long task for 0.5 s), orbit frame rate, hover / pick / select latency, a drag of a part with joints, the joint solve,
collisions, the BOM, an autosave, a version save, JS heap and GPU buffers (estimated), the server's time per endpoint
and kernel call — printed, kept as JSON, and held to budgets.

  A3D_DATA=<a scratch folder> py server.py --port 5199 --no-browser
  PYTHONIOENCODING=utf-8 py tools/e2e_big_assembly.py http://127.0.0.1:5199 <out dir> [--files a.a3d b.a3d …] [--profile] [--gpu] [--window] [--build]

The full UI is timed too, with the page in Czech (the owner's): a click on a part, on another, on empty space, Esc,
a click on a row of the parts tree — from the press to the handlers' end, to the next painted frame, the long tasks.

--build: the assembly built now through the app (tools/make_big_assembly.py) and saved in <out dir>, not the demo;
--files: measure these .a3d files instead (made before by make_big_assembly.py; no budgets checked, a mechanism file is
driven too); --profile: a CDP CPU profile of opening each (<out>/<name>.cpuprofile, its top functions printed); --gpu:
the machine's GPU (default: WebGL in software, SwiftShader — what the budgets are set for); --window: a real Edge
window (with the GPU), as the owner sees it.

Tabs (the owner: back to the big assembly from one of its parts took long): a row of the project tree clicked — the
assembly -> a plate in it -> the assembly, twice; a sub-assembly and back; the plate 1 mm thicker in its tab, then back —
timed to the switch done and its frame drawn, with checks: back unchanged nothing built, drawn or checked again (the
same meshes, the camera kept); after the change its copies drawn 1 mm thicker, the joints hold, no stale meshes.
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
BUDGET = {"interactive_s": 8.0, "orbit_fps": 4, "pick_ms": 50, "select_ms": 100, "hover_ms": 50, "drag_move_ms": 50,
          "ui_ms": 100,  # (the whole UI's answer to a click / Esc, in Czech: the handlers, the panels, their translation)
          "tab_back_ms": 300, "tab_back_changed_ms": 1500}  # (a project tree row clicked: back to the assembly, to its frame painted)

URL = sys.argv[1].rstrip("/")
OUT = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
args = sys.argv[3:]
FILES = [Path(a) for a in args[args.index("--files") + 1:] if not a.startswith("--")] if "--files" in args else []
PROFILE = "--profile" in args
GPU = "--gpu" in args or "--window" in args  # (the machine's GPU; default: software GL, as the budgets assume)
WINDOW = "--window" in args  # (a real Edge window, not headless: its frames painted as the owner sees them; implies --gpu)
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

    # ---- the whole UI in Czech, as the owner uses it (the default docks, the suggestions, the parts tree): a click on a
    # part, on another, on empty space, Esc, a click on a row of the tree, Esc -> from the press to the handlers' end
    # (Event Timing: the input's delay + every handler, the translation of what they changed too), to the next painted
    # frame, and the long tasks. (A text the tables do not hold was matched against every pattern each time: 2.5 s a
    # click on big-500, 11 s on big-150.)
    res.update(ui_timings(b, pts))

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

    # ---- tabs: the assembly -> one of its parts -> the assembly (with and without a dimension changed there)
    res.update(tab_switch(b))

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


UI_PROBE = """
if (!window.__ui) {
  window.__ui = { ev: [], long: [], t0: 0 };
  new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__ui.ev.push([e.startTime, e.processingEnd, e.duration, e.processingEnd - e.processingStart]); }).observe({ type: 'event', durationThreshold: 16 });
  new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__ui.long.push([e.startTime, e.duration]); }).observe({ type: 'longtask' });
  for (const ty of ['pointerdown', 'keydown']) window.addEventListener(ty, () => { if (!window.__ui.t0) window.__ui.t0 = performance.now(); }, true);
}
window.__ui.ev = []; window.__ui.long = []; window.__ui.t0 = 0;
"""


def ui_timings(b, pts):
    """The full UI's select / deselect / Esc / tree click with the page in Czech -> {ui_<what>_<work | paint | long>: stats}."""
    d, js = b.d, b.js
    b.run("const I = await import('/js/i18n.js'); I.setLang('cs');")
    time.sleep(1.5)
    empty = js("""const v = window.__app.assembly.view, r = v.renderer.domElement.getBoundingClientRect();
      for (let y = r.top + 60; y < r.bottom - 20; y += 23) for (let x = r.left + 40; x < r.right - 40; x += 37)
        if (document.elementFromPoint(x, y) === v.renderer.domElement && !v.pickInst(x, y)) return [x, y];
      return null;""")
    seen = [p for p in pts if js("return document.elementFromPoint(arguments[0], arguments[1]) === window.__app.assembly.view.renderer.domElement", p[0], p[1])]

    def click(x, y):  # (as a mouse: the browser's own input, its hit test and pointer capture)
        for ty in ("mouseMoved", "mousePressed", "mouseReleased"):
            d.execute_cdp_cmd("Input.dispatchMouseEvent", {"type": ty, "x": x, "y": y, "button": "none" if ty == "mouseMoved" else "left", "clickCount": 1})

    def esc():
        for ty in ("keyDown", "keyUp"):
            d.execute_cdp_cmd("Input.dispatchKeyEvent", {"type": ty, "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})

    def row(k):
        xy = js("""const rows = [...document.querySelectorAll('.as-list > .mt-item')].filter((r) => r.offsetParent), r = rows[arguments[0]];
          r.scrollIntoView({ block: 'nearest' }); const b = r.querySelector('.mt-name').getBoundingClientRect(); return [b.left + 5, b.top + b.height / 2, r.dataset.inst];""", k)
        click(xy[0], xy[1])
        return xy[2]

    out, right = {}, {}
    for i in range(3):
        p, q = seen[(i * 5) % len(seen)], seen[(i * 5 + 2) % len(seen)]
        for what, fn, want in (("select", lambda: click(p[0], p[1]), p[2]), ("select2", lambda: click(q[0], q[1]), q[2]),
                               ("deselect", lambda: click(*empty), None), ("select", lambda: click(p[0], p[1]), p[2]),
                               ("esc", esc, None), ("tree", lambda: row(1 + i), "row"), ("esc", esc, None)):
            js(UI_PROBE)
            got = fn()
            time.sleep(0.6)
            r = js("""const u = window.__ui, t0 = u.t0, ev = u.ev.filter((e) => e[0] >= t0 - 1);
              return { work: ev.reduce((s, e) => s + e[3], 0), paint: ev.length ? Math.max(...ev.map((e) => e[0] + e[2])) - t0 : 0,
                long: Math.max(0, ...u.long.filter((l) => l[0] >= t0 - 5).map((l) => l[1])), sel: window.__app.assembly.sel };""")
            # (a click on a part: a part chosen — a small one in front of the point's part may take the click; the tree's
            # row: its part; empty space, Esc: none)
            ok = r["sel"] == got if want == "row" else bool(r["sel"]) if want else r["sel"] is None
            if not ok:
                print(f"  (full UI, {what}: {r['sel']} chosen, not {got if want == 'row' else want})")
            right[what] = right.get(what, True) and ok
            for k in ("work", "paint", "long"):
                out.setdefault(f"ui_{what}_{k}", []).append(r[k])
    # a row of the tree clicked: its part's lines blue (seen through); the mouse over rows: their lines lit, nothing drawn anew
    row(4)
    time.sleep(0.4)
    right["tree_lines"] = js("const A = window.__app.assembly; return A.view.placed.get(A.sel)?.lines.material === A.view.chosenEdge")
    lit = js("""const A = window.__app.assembly, v = A.view, rows = [...document.querySelectorAll('.as-list > .mt-item')].filter((r) => r.offsetParent).slice(5, 25), out = [];
      let drawn = 0; const dr = A.draw; A.draw = (...a) => { drawn++; return dr.apply(A, a); };
      let ok = true;
      for (const r of rows) { const t = performance.now(); r.querySelector('.mt-name').dispatchEvent(new PointerEvent('pointerover', { bubbles: true })); out.push(performance.now() - t);
        ok = ok && v.placed.get(r.dataset.inst)?.lines.material === v.litEdge; }
      document.querySelector('.as-list').dispatchEvent(new PointerEvent('pointerleave'));
      A.draw = dr;
      return { ms: out, ok: ok && ![...v.placed.values()].some((p) => p.lines.material === v.litEdge), drawn };""")
    right["tree_hover_lines"] = lit["ok"] and lit["drawn"] == 0
    b.run("const I = await import('/js/i18n.js'); I.setLang('en');")
    res = {k: stats(v) for k, v in out.items()}
    res["ui_tree_hover_ms"] = stats(lit["ms"])
    res["ui_chosen_right"] = right
    return res


# in the page: what a switch of tabs did — fetched, drawn anew, the meshes and camera before it (to compare)
TAB_PROBE = """const A = window.__app.assembly;
if (!window.__tab) { window.__tab = {}; const f = window.fetch; window.fetch = (u, o) => { window.__tab.fetches?.push(String(u).split('?')[0]); return f(u, o); };
  const s = A.view.setBodies.bind(A.view); A.view.setBodies = (l) => { window.__tab.drawn++; return s(l); }; }
Object.assign(window.__tab, { fetches: [], drawn: 0, meshes: new Set(A.view.meshes || []), cam: A.view.camera.position.toArray().join() });"""


def tab_switch(b):
    """The owner's way back and forth (the page in Czech): a row of the project tree clicked — the assembly -> a plate
    placed in it -> the assembly, twice; a sub-assembly and back (when there is one); the plate 1 mm thicker, then back -> timings from
    the click to the frame painted (the switch done, the view drawn) and what was right: {tab_<what>_ms, tab_right}."""
    d, js = b.d, b.js
    asm = js("return window.__app.project.active")
    plate = js("""const P = window.__app.project, used = window.__app.assembly.doc.instances.map((i) => i.part);  // (a plate placed right in it: Plate B / Plate A)
      return (P.parts.filter((p) => /^Plate/.test(p.name) && used.includes(p.id)).sort((x, y) => used.filter((u) => u === y.id).length - used.filter((u) => u === x.id).length)[0] || {}).id || null;""")
    if not plate:  # (a file of other parts: --files)
        return {}
    b.run("const I = await import('/js/i18n.js'); I.setLang('cs');")
    time.sleep(1)
    sub = js("return (window.__app.project.parts.find((p) => p.kind === 'assembly' && p.name === 'Module A') || {}).id || null")

    def go(pid):  # (the tree's row clicked as a mouse does; -> ms to the switch done and its view drawn)
        xy = js("""const r = document.querySelector(`#projTree .pt-row[data-part="${arguments[0]}"] .pt-open`); r.scrollIntoView({ block: 'nearest' });
          const b = r.getBoundingClientRect(); return [b.left + 20, b.top + b.height / 2];""", pid)
        d.execute_cdp_cmd("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": xy[0], "y": xy[1], "button": "none"})
        time.sleep(0.4)
        js("""const pid = arguments[0], P = window.__app.project, t0 = performance.now(); window.__done = null;
          const look = () => { const A = window.__app.assembly, M = window.__app.modeler, v = P.current?.kind === 'assembly' ? A.view : M.view;
            if (P.active === pid && !P.busy && !M.inflight && !v.dirty) { window.__done = performance.now() - t0; return; } requestAnimationFrame(look); };
          requestAnimationFrame(look);""", pid)
        for ty in ("mousePressed", "mouseReleased"):
            d.execute_cdp_cmd("Input.dispatchMouseEvent", {"type": ty, "x": xy[0], "y": xy[1], "button": "left", "clickCount": 1})
        b.wait("return window.__done !== null", 60)
        return round(js("return window.__done"))

    res, right = {}, {}
    js("const v = window.__app.assembly.view; v.controls.rotate(0.4, 0.1); v.controls.changed();")  # (the owner's own view: kept)
    time.sleep(1.5)
    for k in (1, 2):
        res[f"tab_to_part_{k}_ms"] = go(plate)
        time.sleep(1)
        js(TAB_PROBE)
        res[f"tab_back_{k}_ms"] = go(asm)
        time.sleep(1.5)  # (what may follow: a clash check, the panels)
        same = js("""const A = window.__app.assembly, w = window.__tab;
          return { fetched: w.fetches.filter((u) => /rebuild|clashes/.test(u)), drawn: w.drawn, kept: A.view.meshes.every((m) => w.meshes.has(m)) && A.view.meshes.length === w.meshes.size,
            camera: A.view.camera.position.toArray().join() === w.cam };""")
        right[f"back {k}: nothing built, drawn or checked again, the same meshes, the camera kept"] = not same["fetched"] and not same["drawn"] and same["kept"] and same["camera"]
        if not right[f"back {k}: nothing built, drawn or checked again, the same meshes, the camera kept"]:
            print(f"  (tab back {k}: {same})")
    if sub:  # (another assembly on screen between: this one put aside warm, its meshes back)
        js(TAB_PROBE)  # (the assembly's meshes and camera now: the same ones back)
        res["tab_to_sub_ms"] = go(sub)
        time.sleep(1)
        res["tab_back_from_sub_ms"] = go(asm)
        time.sleep(1.5)
        k = js("const A = window.__app.assembly, w = window.__tab; return [A.view.meshes.every((m) => w.meshes.has(m)) && A.view.meshes.length === w.meshes.size, A.view.camera.position.toArray().join() === w.cam, A.view.bodyGroup.children.filter((o) => o.isMesh).length === A.doc.instances.length];")
        right["back from a sub-assembly: its meshes kept, the camera kept, no other assembly's meshes left"] = all(k)
    # the plate 1 mm thicker in its tab -> back: its copies drawn with the new body (their box 1 mm taller), the joints hold
    box = """const A = window.__app.assembly, m = A.view.meshes.find((x) => A.inst(x.userData.inst)?.part === arguments[0]);
      m.geometry.computeBoundingBox(); const s = m.geometry.boundingBox.getSize(new (m.geometry.boundingBox.min.constructor)()); return [s.x, s.y, s.z].map((v) => Math.round(v * 1000) / 1000);"""
    size0 = js(box, plate)
    res["tab_to_part_3_ms"] = go(plate)
    m = json.loads(b.call("get_model"))
    ext = next(x for x in m.get("features", m.get("steps", [])) if x.get("type") == "extrude")
    b.call("edit_feature", id=ext["id"], fields={"d": (ext.get("d") or 3) + 1})
    b.run("const M = window.__app.modeler; while (M.inflight) await M.inflight;")
    time.sleep(1)
    js(TAB_PROBE)
    res["tab_back_changed_ms"] = go(asm)
    time.sleep(2)
    size1 = js(box, plate)
    st = js("""const A = window.__app.assembly, w = window.__tab, v = A.view;
      return { unmet: A.unmet().length, stale: v.meshes.filter((m) => m.userData.body !== A.bodyOf(A.inst(m.userData.inst))?.body).length,
        extra: v.bodyGroup.children.filter((o) => o.isMesh && !v.meshes.includes(o)).length, n: v.meshes.length, all: A.doc.instances.length,
        reused: v.meshes.filter((m) => w.meshes.has(m)).length, camera: v.camera.position.toArray().join() === w.cam };""")
    res["tab_changed"] = {"box_before": size0, "box_after": size1, **st}
    right["back after the plate 1 mm thicker: its copies drawn 1 mm thicker, the joints hold"] = (
        st["unmet"] == 0 and sorted(round(b1 - b0, 3) for b0, b1 in zip(size0, size1)) == [0, 0, 1])
    right["back after the change: no stale meshes (each drawn with its part's body now), every mesh reused, the camera kept"] = (
        st["stale"] == 0 and st["extra"] == 0 and st["n"] == st["all"] and st["reused"] == st["all"] and st["camera"])
    b.run(f"await window.__app.project.switchTo('{plate}'); const M = window.__app.modeler; await M.history.go(-1); while (M.inflight) await M.inflight;"
          f" await window.__app.project.switchTo('{asm}');")  # (the plate as it was: the measurements after this on the demo as made)
    b.run("const I = await import('/js/i18n.js'); I.setLang('en');")
    res["tab_right"] = right
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


b = Builder(URL, software_gl=not GPU, window=WINDOW)
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
        for what in ("select", "select2", "deselect", "esc", "tree"):
            w, lt = r[f"ui_{what}_work"], r[f"ui_{what}_long"]
            check(f"full UI in Czech, {what}: its handlers under {BUDGET['ui_ms']} ms", w.get("p50", 1e9) < BUDGET["ui_ms"], f"work {w}, paint {r[f'ui_{what}_paint']}, long {lt}")
        if GPU:  # (SwiftShader draws a frame in ~150 ms on the page's thread: the paint and long tasks held only on a GPU)
            check(f"full UI, a click to its painted frame under {BUDGET['ui_ms']} ms, no long task over it",
                  all(r[f"ui_{w}_paint"].get("p50", 1e9) < BUDGET["ui_ms"] and r[f"ui_{w}_long"].get("max", 1e9) < BUDGET["ui_ms"] for w in ("select", "select2", "deselect", "esc", "tree")),
                  {w: (r[f"ui_{w}_paint"].get("p50"), r[f"ui_{w}_long"].get("max")) for w in ("select", "select2", "deselect", "esc", "tree")})
        check("full UI: each click / Esc chose what it should; a tree row clicked: its lines blue, hovered: lit, nothing drawn anew",
              all(r["ui_chosen_right"].values()), r["ui_chosen_right"])
        check(f"the mouse over a tree row under {BUDGET['hover_ms']} ms", r["ui_tree_hover_ms"].get("max", 1e9) < BUDGET["hover_ms"], r["ui_tree_hover_ms"])
        for k in ("tab_back_1_ms", "tab_back_2_ms") + (("tab_back_from_sub_ms",) if "tab_back_from_sub_ms" in r else ()):
            check(f"tabs: {k[4:-3].replace('_', ' ')} to the assembly under {BUDGET['tab_back_ms']} ms", r[k] < BUDGET["tab_back_ms"], r[k])
        check(f"tabs: back after a dimension changed in the part under {BUDGET['tab_back_changed_ms']} ms", r["tab_back_changed_ms"] < BUDGET["tab_back_changed_ms"], r["tab_back_changed_ms"])
        check("tabs: the assembly kept warm — nothing again when nothing changed, only the changed part after a change", all(r["tab_right"].values()), {**r["tab_right"], **r["tab_changed"]})
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
