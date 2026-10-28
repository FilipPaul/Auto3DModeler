"""Two people at once (the kernel's pool of processes), in two headless Edge sessions: one starts heavy jobs — the
44 MB board imported (data/imports, when it is there) and the plate with 171 holes built and drawn on a sheet — while
the other keeps editing a small part: each of its rebuilds must stay under a second while the heavy jobs run.
With A3D_WORKERS=1 (one kernel process, as before) the small part waits for them (pass --report to only print).

  PYTHONIOENCODING=utf-8 py tools/e2e_kernel_pool.py http://127.0.0.1:5199 <out dir> [<a big .step>] [--report]
"""
import os
import sys
import threading
import time

import requests
from selenium import webdriver

URL, OUT = sys.argv[1], sys.argv[2]
REPORT = "--report" in sys.argv
ARGS = [a for a in sys.argv[3:] if not a.startswith("--")]
STEP = ARGS[0] if ARGS else os.path.join(os.path.dirname(__file__), "..", "data", "imports", "45c51541a12d03a8.step")
M = "window.__app.modeler"
H = "window.__app.agentHandlers"


def edge():
    opts = webdriver.EdgeOptions()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1400,900")
    opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
    d = webdriver.Edge(options=opts)
    d.set_script_timeout(900)
    return d


def wait(d, script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = d.execute_script(script)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(script)


def plate():
    """200 × 100 × 5, a Ø3 hole repeated 19 × 9 (171 holes)."""
    pts = {"p1": [0, 0], "p2": [200, 0], "p3": [200, 100], "p4": [0, 100]}
    lines = [{"id": f"l{i + 1}", "t": "line", "a": f"p{i + 1}", "b": f"p{(i + 1) % 4 + 1}"} for i in range(4)]
    top = {"face": {"name": "E1:end"}, "frame": {"o": [100, 50, 5], "x": [1, 0, 0], "n": [0, 0, 1]}}
    return [{"id": "S1", "type": "sketch", "plane": {"datum": "XY"}, "points": pts, "entities": lines},
            {"id": "E1", "type": "extrude", "sketch": "S1", "op": "add", "d": 5},
            {"id": "H1", "type": "hole", "plane": top, "points": [[-90, -40]], "d": 3, "through": True},
            {"id": "P1", "type": "pattern", "features": ["H1"], "kind": "linear", "dir": [1, 0, 0], "count": 19, "spacing": 10},
            {"id": "P2", "type": "pattern", "features": ["H1", "P1"], "kind": "linear", "dir": [0, 1, 0], "count": 9, "spacing": 10},
            {"id": "R1", "type": "fillet", "edges": [{"a": "E1:end", "b": "E1:side:l1", "fp": [100, 0, 5]}], "r": 2}]


HEAVY = """
const [feats, done] = arguments, M = window.__app.modeler, out = {};
(async () => {
  let T = performance.now();
  M.part.features = feats;
  await M.rebuild();
  out.plate = Math.round(performance.now() - T);
  T = performance.now();
  const res = await fetch('/api/sheet/build', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ part: { features: feats }, preset: 'full', section: true }) });
  const r = await res.json();
  out.sheet = Math.round(performance.now() - T);
  out.dims = (r.dims || []).length;
  done(out);
})().catch((e) => done({ error: String(e.stack || e) }));
"""

EDIT = """
const [d, done] = arguments, M = window.__app.modeler;
const T = performance.now();
M.part.features[1].d = d;
M.rebuild().then(() => done({ ms: Math.round(performance.now() - T), volume: M.result.body.volume }));
"""

a, b = edge(), edge()
ok = True
try:
    for d in (a, b):
        d.get(URL)
        wait(d, "return !!window.__app")
    b.execute_script(f"return {H}.new_model({{name: 'Small'}})")
    b.execute_script(f"return {H}.add_feature({{type: 'sketch', plane: 'XY', shapes: [{{rect: {{x: 0, y: 0, w: 30, h: 20}}}}]}})")
    b.execute_script(f"return {H}.add_feature({{type: 'extrude', sketch: 'F1', d: 10}})")
    wait(b, f"return !!{M}.result?.body")
    calm = [b.execute_async_script(EDIT, 10 + k)["ms"] for k in range(3)]
    print("the small part alone: rebuilds", calm, "ms")
    a.execute_script(f"return {H}.new_model({{name: 'Heavy'}})")
    wait(a, f"return !!{M}.part")

    heavy = {}

    def imported():
        if not os.path.exists(STEP):
            return
        t0 = time.time()
        with open(STEP, "rb") as fh:
            r = requests.post(URL + "/api/model/import", files={"file": (os.path.basename(STEP), fh)}, timeout=900)
        heavy["import"] = (round(time.time() - t0, 1), r.status_code)

    def drawn():
        t0 = time.time()
        heavy["plate"] = a.execute_async_script(HEAVY, plate())
        heavy["plate_total"] = round(time.time() - t0, 1)

    jobs = [threading.Thread(target=imported), threading.Thread(target=drawn)]
    t0 = time.time()
    for j in jobs:
        j.start()
    time.sleep(0.5)  # (they have started)
    busy = []
    k = 0
    while any(j.is_alive() for j in jobs) and k < 40:
        r = b.execute_async_script(EDIT, 12 + (k % 7))
        busy.append(r["ms"])
        k += 1
        time.sleep(0.2)
    for j in jobs:
        j.join(900)
    print(f"heavy jobs (the other session) took {time.time() - t0:.1f} s:", heavy,
          "" if os.path.exists(STEP) else f"(no {STEP}: the plate only)")
    print(f"the small part meanwhile: {len(busy)} rebuilds, ms:", busy)
    slow = [ms for ms in busy if ms > 1000]
    if not busy or slow:
        ok = False
        print("SLOW: rebuilds over a second while the heavy jobs ran:", slow or "none measured")
    if heavy.get("plate", {}).get("error") or heavy.get("import", (0, 200))[1] != 200:
        ok = False
        print("FAILED heavy job:", heavy)
    b.save_screenshot(os.path.join(OUT, "kernel_pool_small.png"))
    a.save_screenshot(os.path.join(OUT, "kernel_pool_heavy.png"))
    errs = [e["message"] for d in (a, b) for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
finally:
    a.quit()
    b.quit()
print("OK" if ok else ("REPORTED" if REPORT else "FAILED"))
sys.exit(0 if ok or REPORT else 1)
