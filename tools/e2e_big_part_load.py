"""Big parts load quickly, in headless Edge: a plate with 171 holes and a 44 MB imported board (126 062 faces) — each
built by the app (the first time: the kernel too; again: kept), then its rebuild fetched both ways: JSON with base64
arrays (the AI tools' and tests' answer) and the binary message the app uses (modeler/packed.js) — the bytes and the
times of each, the same arrays and faces both ways, and a face picked on the part after it is shown.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_big_part_load.py http://127.0.0.1:5199 <out dir> [<a big .step>]
"""
import os
import sys
import time

import requests
from selenium import webdriver

URL, OUT = sys.argv[1], sys.argv[2]
STEP = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(__file__), "..", "data", "imports", "45c51541a12d03a8.step")
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
d.set_script_timeout(900)
js = d.execute_script
M = "window.__app.modeler"


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
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
            {"id": "P2", "type": "pattern", "features": ["H1", "P1"], "kind": "linear", "dir": [0, 1, 0], "count": 9, "spacing": 10}]


MEASURE = """
const [feats, done] = arguments, M = window.__app.modeler;
const b64 = (s, T) => { const bin = atob(s), u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return new T(u.buffer); };
const frame = () => new Promise((ok) => requestAnimationFrame(() => requestAnimationFrame(ok)));
(async () => {
  const out = {}, { unpack } = await import('/js/modeler/packed.js');
  const shown = async () => { const T = performance.now(); M.part.features = feats; await M.rebuild(); await frame(); return Math.round(performance.now() - T); };
  out.app_first = await shown();
  out.app_again = await shown();
  const get = async (bin) => {
    const T = performance.now(), res = await fetch('/api/model/rebuild', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ part: { features: feats }, bin }) });
    const buf = await res.arrayBuffer(), t1 = performance.now();
    let r;
    if (bin) r = unpack(buf);
    else { r = JSON.parse(new TextDecoder().decode(buf)); for (const b of [r.body, ...(r.refs || [])]) { b.positions = b64(b.positions, Float32Array); b.face_ids = b64(b.face_ids, Uint32Array); } }
    return { r, bytes: buf.byteLength, fetch: Math.round(t1 - T), read: Math.round(performance.now() - t1) };
  };
  const j = await get(false), b = await get(true);
  const same = (x, y) => x.length === y.length && x.every((v, i) => v === y[i]);
  const sorted = (k, v) => (ArrayBuffer.isView(v) ? v.length : v && typeof v === 'object' && !Array.isArray(v) ? Object.fromEntries(Object.entries(v).sort()) : v);
  const rest = (r) => JSON.stringify(r, sorted); // (the same fields, whatever their order)
  out.json = { bytes: j.bytes, fetch: j.fetch, read: j.read };
  out.bin = { bytes: b.bytes, fetch: b.fetch, read: b.read };
  out.same = same(j.r.body.positions, b.r.body.positions) && same(j.r.body.face_ids, b.r.body.face_ids) && rest(j.r) === rest(b.r);
  out.triangles = b.r.body.face_ids.length;
  out.faces = b.r.body.faces.length;
  // a face picked near the middle of the part (from the top; between the plate's holes), as the mouse would
  M.view.setView('top');
  await frame();
  const bb = M.result.body.bbox, P = M.view.camera.position.constructor;
  const [x, y] = M.view.toScreen(new P(bb[0] + (bb[3] - bb[0]) * 0.525, bb[1] + (bb[4] - bb[1]) * 0.525, bb[5])), hit = M.view.pick(x, y);
  out.picked = hit?.face ? (hit.face.name || hit.face.id) + ' (' + hit.face.type + ')' : null;
  done(out);
})().catch((e) => done({ error: String(e.stack || e) }));
"""

try:
    parts = [("plate, 171 holes", plate())]
    if os.path.exists(STEP):
        t0 = time.time()
        with open(STEP, "rb") as fh:
            blob = requests.post(URL + "/api/model/import", files={"file": (os.path.basename(STEP), fh)}, timeout=900).json()["blob"]
        print(f"imported {os.path.basename(STEP)} ({os.path.getsize(STEP) / 1e6:.1f} MB) in {time.time() - t0:.1f} s")
        parts.append(("board (44 MB STEP)", [{"id": "B1", "type": "solid", "blob": blob}]))
    else:
        print("no big STEP at", STEP, "- the plate only")
    d.get(URL)
    wait("return !!window.__app")
    js("return window.__app.agentHandlers.new_model({name: 'Big'})")
    wait(f"return !!{M}.part")
    rows = []
    for name, feats in parts:
        r = d.execute_async_script(MEASURE, feats)
        if r.get("error"):
            raise RuntimeError(r["error"])
        rows.append((name, r))
        print(f"{name}: {r['faces']} faces, {r['triangles']} triangles; shown by the app {r['app_first']} ms the first time, "
              f"{r['app_again']} ms again | the same arrays and faces both ways: {r['same']} | picked: {r['picked']}")
    print()
    print(f"{'part':22} {'JSON + base64':>26} {'binary':>26}")
    for name, r in rows:
        j, b = r["json"], r["bin"]
        print(f"{name:22} {j['bytes'] / 1e6:8.2f} MB {j['fetch']:6} + {j['read']:4} ms {b['bytes'] / 1e6:8.2f} MB {b['fetch']:6} + {b['read']:4} ms")
    print("(fetch: the request until the last byte; read: JSON.parse + base64 / the binary header and views)")
    d.save_screenshot(os.path.join(OUT, "big_part_load.png"))
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
finally:
    d.quit()
