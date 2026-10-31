"""A sketch on a face of an imported STEP (the page in Czech, REAL mouse clicks in headless Edge):
1. samples/…/nist_ctc_01 imported as a ▣ solid step, 👁 reference (op "ref" — "build around a bought part"): a click on
   its big flat face with holes -> the suggestions "✏ Skica na této ploše" and "⇱ Převzít obrys plochy do skici"; ✏ opens
   a sketch on that face (plane = the face, origin = its centre, the face named F1:f<n>).
2. ⇱ Převzít obrys plochy do skici -> a sketch whose shapes are the face's loops (lines, arcs, circles, one ⇱ relation
   holding them; the solver: nothing free) — its length = the face's edges' length; extruded 5 mm -> a solid of the face's
   area × 5, its box the face's box (the outline matches); watertight is the kernel's (unit tests).
3. The same file joined (op "add"): its flat face offers ✏ and ⇱ too; ✏ opens a sketch on it.
4. In an assembly: the imported part's flat face -> "✏ Skica na této ploše → upravit díl zde" and "＋ Nový díl se skicou
   na této ploše"; ＋ makes a new part placed where it is (the file in it see-through) and opens it with a sketch on
   that face.
5. The AI path through /api/agent/call: add_feature solid (path, op ref), find_refs (ref: true faces), add_feature sketch
   {plane: {face}, shapes: [{from_face}]}, extrude 5 -> the volume = area × 5.
6. No console errors.

  PYTHONIOENCODING=utf-8 py tools/e2e_step_sketch.py http://127.0.0.1:5199 <out dir>
"""
import json
import math
import os
import sys
import time
import urllib.request
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
STEP = Path(__file__).resolve().parent.parent / "samples" / "ToImportToOurApp" / "nist" / "nist_ctc_01_asme1_rd.stp"
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
H = "window.__app.agentHandlers"
M = "window.__app.modeler"
A = "window.__app.assembly"
MCV, ACV = "#modelViewport canvas", "#asmViewport canvas"
fails = []


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def ai(tool, **args):
    req = urllib.request.Request(f"{URL}/api/agent/call", data=json.dumps({"tool": tool, "args": args}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        res = json.loads(r.read())
    return ("ERROR " if res.get("isError") else "") + "".join(c.get("text", "") for c in res.get("content", []))


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(script)


def check(what, ok):
    print(("  ok  " if ok else "  FAIL") + " " + what)
    if not ok:
        fails.append(what)


def built():
    wait(f"return {M}.result && !{M}.inflight && !{M}.queued", 180)
    time.sleep(0.3)


def spot(view, name, refs=True):
    """A pixel (client x, y) on face `name` that a click there picks: the middle of one of its triangles, in sight."""
    return js(f"""const v = {view}.view, name = arguments[0], refs = arguments[1], V = v.camera.position.constructor, r = v.renderer.domElement.getBoundingClientRect();
      const meshes = refs ? (v.refGroup?.children || []).map(m => [m, m.userData.ref.faceIds, m.userData.ref.faces]) : [[v.mesh, v.faceIds, v.body.faces]];
      for (const [m, ids, faces] of meshes) {{
        const pos = m.geometry.attributes.position.array;
        for (let t = 0; t < ids.length; t++) {{
          const f = faces.find(x => x.id === ids[t]);
          if (!f || f.name !== name) continue;
          const c = new V((pos[t*9] + pos[t*9+3] + pos[t*9+6]) / 3, (pos[t*9+1] + pos[t*9+4] + pos[t*9+7]) / 3, (pos[t*9+2] + pos[t*9+5] + pos[t*9+8]) / 3);
          const [x, y] = v.toScreen(c);
          if (x < r.left + 260 || x > r.right - 340 || y < r.top + 90 || y > r.bottom - 120) continue;
          if (document.elementFromPoint(x, y) !== v.renderer.domElement) continue;
          const h = v.pick(x, y, {{ refs }});
          if (h?.face?.name === name && !v.measurePoint(x, y)?.snap && !(v.body && v.pickEdge(x, y, 9) >= 0)) return [Math.round(x), Math.round(y)];
        }}
      }}
      return null;""", name, refs)


def real_click(sel, xy):
    el = d.find_element(By.CSS_SELECTOR, sel)
    o = js("const r = arguments[0].getBoundingClientRect(); return [Math.floor(r.left + r.width / 2), Math.floor(r.top + r.height / 2)]", el)
    ActionChains(d, duration=30).move_to_element_with_offset(el, xy[0] - o[0], xy[1] - o[1]).pause(0.3).click().perform()
    time.sleep(0.8)


def rows(vp):
    return [" ".join(b.text.split()) for b in d.find_elements(By.CSS_SELECTOR, f"{vp} .view-suggest .vs-list button[data-sg]")]


def press(vp, text):
    """Click the suggestion row that says `text` (under ⋯ Show all when not among the top ones)."""
    for _ in range(2):
        for b in d.find_elements(By.CSS_SELECTOR, f"{vp} .view-suggest .vs-list button[data-sg]"):
            if text in " ".join(b.text.split()):
                b.click()
                time.sleep(0.8)
                return True
        more = d.find_elements(By.CSS_SELECTOR, f"{vp} .view-suggest [data-sg-all]")
        if not more:
            break
        more[0].click()
        time.sleep(0.4)
    return False


def import_step():
    js("let i = document.getElementById('e2eFile'); if (!i) { i = document.createElement('input'); i.type = 'file'; i.id = 'e2eFile'; i.hidden = true; document.body.appendChild(i); } i.value = '';")
    d.find_element(By.ID, "e2eFile").send_keys(str(STEP))
    return d.execute_async_script("""const done = arguments[arguments.length - 1], f = document.getElementById('e2eFile').files[0], fd = new FormData();
      fd.append('file', f);
      fetch('/api/model/import', { method: 'POST', body: fd }).then(r => r.json()).then(done, (e) => done({ error: String(e) }));""")


def ref_faces():
    return js(f"return ({M}.result.refs || []).flatMap(r => r.faces.map(f => ({{ ...f, solid: r.id, edges: r.edges.filter(e => e.faces.includes(r.faces.indexOf(f))).map(e => e.pts) }})))")


def poly_len(pts):
    return sum(math.dist(pts[i:i + 3], pts[i + 3:i + 6]) for i in range(0, len(pts) - 3, 3))


def sketch_len(f):
    P = lambda k: f["points"][k]  # noqa: E731
    total = 0.0
    for e in f["entities"]:
        if e["t"] == "line":
            total += math.dist(P(e["a"]), P(e["b"]))
        elif e["t"] == "circle":
            total += 2 * math.pi * e["r"]
        elif e["t"] == "arc":
            c, a, b = P(e["c"]), P(e["a"]), P(e["b"])
            r = math.dist(c, a)
            sw = (math.atan2(b[1] - c[1], b[0] - c[0]) - math.atan2(a[1] - c[1], a[0] - c[0])) % (2 * math.pi) or 2 * math.pi
            total += r * sw
        elif e["t"] == "spline":
            q = [P(k) for k in e["pts"]]
            total += sum(math.dist(q[i], q[i + 1]) for i in range(len(q) - 1))
    return total


try:
    if not STEP.exists():
        print("(no STEP sample: skipped)")
        sys.exit(0)
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.setItem('auto3d-lang', 'cs'); localStorage.removeItem('a3d.leftDock')")
    d.get(URL)
    wait("return !!window.__app")
    print("lang:", js("return document.documentElement.lang"))

    r = import_step()
    print("STEP import:", {k: r.get(k) for k in ("name", "faces", "op", "error")})
    check("the STEP is read", bool(r.get("blob")))

    # ---- 1. 👁 reference: a sketch on its flat face with holes
    js("""const r = arguments[0]; return window.__app.project.newModel({ features: [{ id: 'F1', type: 'solid', name: 'Koupený díl', blob: r.blob, file: r.name, op: 'ref' }] }, 'Kryt kolem dílu')""", r)
    built()
    faces = ref_faces()
    flat = sorted([f for f in faces if f["type"] == "plane"], key=lambda f: -f["area"])
    face = flat[0]
    loops = len([1 for e in face["edges"]])
    print("the reference's biggest flat face:", face["name"], round(face["area"], 2), "edges:", loops)
    check("a reference solid's faces come with names and frames", face["name"].startswith("F1:f") and bool(face.get("frame")))
    js(f"{M}.view.setView('iso')")
    time.sleep(0.8)
    xy = spot(M, face["name"])
    check("a spot of that face in sight", bool(xy))
    real_click(MCV, xy)
    rs = rows("#modelViewport")
    print("rows:", rs)
    check("✏ Skica na této ploše offered on the reference's face", any("Skica na této ploše" in x for x in rs))
    check("⇱ Převzít obrys plochy do skici offered", any("Převzít obrys plochy do skici" in x for x in rs))
    d.save_screenshot(os.path.join(OUT, "step_sketch_ref_face.png"))
    press("#modelViewport", "Skica na této ploše")
    wait(f"return {M}.mode === 'sketch'", 20)
    pl = js(f"return {M}.sk.f.plane")
    print("sketch plane:", pl)
    check("the sketch is on that face (named F1:f<n>), origin = its centre", pl.get("face", {}).get("name") == face["name"]
          and all(abs(a - b) < 1e-6 for a, b in zip(pl["frame"]["o"], face["frame"]["o"])))
    js(f"{M}.cancelSketch()")
    time.sleep(0.8)

    # ---- 2. ⇱ its outline taken into a sketch, extruded 5 mm
    js(f"{M}.view.setView('iso')")
    time.sleep(0.8)
    real_click(MCV, spot(M, face["name"]))
    check("⇱ pressed", press("#modelViewport", "Převzít obrys plochy do skici"))
    wait(f"return {M}.mode === 'sketch' && {M}.sk.f.constraints.some(k => k.t === 'proj')", 60)
    time.sleep(1)
    sk = js(f"return {M}.sk.f")
    kinds = {}
    for e in sk["entities"]:
        kinds[e["t"]] = kinds.get(e["t"], 0) + 1
    k = next(c for c in sk["constraints"] if c["t"] == "proj")
    edge_len = sum(poly_len(p) for p in face["edges"])
    print("taken:", kinds, "relation:", {x: k.get(x) for x in ("t", "face")}, "length", round(sketch_len(sk), 3), "the face's edges", round(edge_len, 3))
    check("the face's loops became lines, arcs and circles", kinds.get("line", 0) > 0 and kinds.get("circle", 0) + kinds.get("arc", 0) > 0)
    check("held by one ⇱ relation to that face", k.get("face", {}).get("name") == face["name"] and len(k.get("ents") or []) == len(sk["entities"]))
    check("the outline's length matches the face's edges (0.5 %)", abs(sketch_len(sk) - edge_len) < 0.005 * edge_len)
    dof = d.execute_async_script(f"""const done = arguments[arguments.length - 1], f = {M}.sk.f;
      fetch('/api/model/sketch/solve', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ sketch: f }}) }}).then(r => r.json()).then(done, e => done({{ error: String(e) }}));""")
    print("solve:", {x: dof.get(x) for x in ("ok", "dof", "conflicts")})
    check("the taken shapes are held (solved, nothing free)", dof.get("ok") and dof.get("dof") == 0)
    rel = js("return [...document.querySelectorAll('.sk-rel')].map(e => e.textContent)")
    check("its ⇱ symbol shows in the sketch", "⇱" in rel)
    d.save_screenshot(os.path.join(OUT, "step_sketch_taken.png"))
    js(f"{M}.finishSketch()")
    time.sleep(1.5)
    built()
    js(f"{M}.cmd && {M}.cancelCommand()")  # (Finish may open an extrude: the AI handler makes it, 5 mm)
    time.sleep(0.5)
    sid = js(f"return {M}.part.features.filter(f => f.type === 'sketch').at(-1).id")
    print(call("add_feature", type="extrude", sketch=sid, d=5, op="add"))
    built()
    b = js(f"return {M}.result.body && {{ volume: {M}.result.body.volume, bbox: {M}.result.body.bbox }}")
    want = face["area"] * 5
    print("extruded:", b, "want", round(want, 3))
    check("extruded 5 mm: the volume = the face's area × 5", b and abs(b["volume"] - want) < 1e-4 * want)
    fb = [min(face["edges"][i][j] for i in range(len(face["edges"])) for j in range(axis, len(face["edges"][i]), 3)) for axis in range(3)]
    fB = [max(face["edges"][i][j] for i in range(len(face["edges"])) for j in range(axis, len(face["edges"][i]), 3)) for axis in range(3)]
    check("its box is the face's box (in the face's plane)", b and all(abs(b["bbox"][a] - fb[a]) < 0.05 and abs(b["bbox"][a + 3] - fB[a]) < 0.05 for a in (0, 1)))
    d.save_screenshot(os.path.join(OUT, "step_sketch_extruded.png"))

    # ---- 3. joined (op add): ✏ and ⇱ on its flat face too
    js("""const r = arguments[0]; return window.__app.project.newModel({ features: [{ id: 'F1', type: 'solid', name: 'Díl', blob: r.blob, file: r.name, op: 'add' }] }, 'Koupený díl')""", r)
    built()
    js(f"{M}.view.setView('iso')")
    time.sleep(0.8)
    xy = spot(M, face["name"], refs=False)
    check("joined: a spot of the face in sight", bool(xy))
    real_click(MCV, xy)
    rs = rows("#modelViewport")
    print("joined rows:", rs)
    check("joined: ✏ Skica na této ploše offered", any("Skica na této ploše" in x for x in rs))
    check("joined: ⇱ Převzít obrys plochy do skici among them", press("#modelViewport", "Převzít obrys plochy do skici"))
    wait(f"return {M}.mode === 'sketch' && {M}.sk.f.constraints.some(k => k.t === 'proj')", 60)
    n = js(f"return {M}.sk.f.entities.length")
    check(f"joined: the outline taken ({n} shapes, as on the reference)", n == len(sk["entities"]))
    js(f"{M}.cancelSketch()")
    time.sleep(0.5)
    # a straight edge of that face: ⇱ Převzít hrany do skici among its suggestions -> a sketch on the face with that line
    ref = js(f"""const b = {M}.result.body, i = b.edges.findIndex(e => e.faces.length === 2 && e.pts.length === 6 && e.faces.some(k => b.faces[k].name === arguments[0]));
      return {M}.edgeRef(i)""", face["name"])
    labels = js(f"return {M}.edgeItems([arguments[0]]).map(x => x.label)", ref)
    check("an edge offers ⇱ Převzít hrany do skici", "Převzít hrany do skici" in labels)
    js(f"{M}.sketchFromEdges([arguments[0]])", ref)
    wait(f"return {M}.mode === 'sketch' && {M}.sk.f.constraints.some(k => k.t === 'proj')", 60)
    es = js(f"return {M}.sk.f.entities.map(e => e.t)")
    check(f"the edge taken into a sketch on its face: {es}", es == ["line"] and js(f"return {M}.sk.f.plane.face.name") == face["name"])
    js(f"{M}.cancelSketch()")
    time.sleep(0.5)

    # ---- 4. in an assembly: the imported part's face
    print(call("new_assembly", name="Sestava"))
    print(call("insert_part", part="Koupený díl"))
    wait(f"return Object.values({A}.bodies).every(b => b.body)", 180)
    js(f"{A}.view.setView('iso')")
    time.sleep(1)
    xy = js(f"""const v = {A}.view, name = arguments[0], r = v.renderer.domElement.getBoundingClientRect(), V = v.camera.position.constructor;
      const mesh = v.meshes.find(m => m.userData.inst === 'I1'), b = mesh.userData.body, f = b.faces.find(x => x.name === name);
      const pos = mesh.geometry.attributes.position.array, ids = mesh.userData.faceIds;
      for (let t = 0; ids && t < ids.length; t++) {{
        if (ids[t] !== f.id) continue;
        const c = new V((pos[t*9] + pos[t*9+3] + pos[t*9+6]) / 3, (pos[t*9+1] + pos[t*9+4] + pos[t*9+7]) / 3, (pos[t*9+2] + pos[t*9+5] + pos[t*9+8]) / 3).applyMatrix4(mesh.matrix);
        const [x, y] = v.toScreen(c);
        if (x < r.left + 260 || x > r.right - 340 || y < r.top + 90 || y > r.bottom - 120 || document.elementFromPoint(x, y) !== v.renderer.domElement) continue;
        if (v.pickInst(x, y)?.face?.name === name && !v.measurePoint?.(x, y, 9)?.snap) return [Math.round(x), Math.round(y)];
      }}
      return null;""", face["name"])
    print("assembly spot:", xy)
    check("assembly: a spot of the face in sight", bool(xy))
    if xy:
        real_click(ACV, xy)
        rs = rows("#asmViewport")
        print("assembly rows:", rs)
        check("assembly: ✏ Skica na této ploše → upravit díl zde offered", press("#asmViewport", "Skica na této ploše → upravit díl zde") or any("upravit díl zde" in x for x in rs))
        if js(f"return {M}.mode === 'sketch' || !!{M}.context"):
            wait(f"return {M}.mode === 'sketch'", 60)
            check("assembly ✏: the part opens in place with a sketch on that face", js(f"return {M}.sk?.f.plane?.face?.name") == face["name"] and bool(js(f"return !!{M}.context")))
            js(f"{M}.cancelSketch()")
            time.sleep(0.5)
            js(f"{M}.hooks.backTo?.({M}.context?.back)")
            wait(f"return {A}.active", 30)
            time.sleep(1)
        real_click(ACV, xy)
        check("assembly: ＋ Nový díl se skicou na této ploše pressed", press("#asmViewport", "Nový díl se skicou na této ploše"))
        wait(f"return {M}.mode === 'sketch'", 120)
        pl = js(f"return {M}.sk.f.plane")
        part = js(f"return {M}.part.features.map(f => [f.type, f.op])")
        print("new part:", part, "plane:", pl.get("face"))
        check("＋: a new part with the file as a 👁 reference, the sketch on that face", part == [["solid", "ref"]] and pl.get("face", {}).get("name") == face["name"] and bool(js(f"return !!{M}.context")))
        d.save_screenshot(os.path.join(OUT, "step_sketch_new_part.png"))
        js(f"{M}.cancelSketch()")
        time.sleep(0.5)

    # ---- 5. the AI path
    print(ai("new_model", name="AI kryt"))
    out = ai("add_feature", type="solid", path=str(STEP), op="ref")
    print("solid:", out[:160])
    built()
    refs = ai("find_refs", kind="face", normal=[0, 0, 1], limit=40)
    fl = [f for f in json.loads(refs[refs.index("["):]) if f.get("name") == face["name"]]
    check("AI: find_refs lists the reference's faces (ref: true)", bool(fl) and fl[0].get("ref") is True)
    out = ai("add_feature", type="sketch", plane={"face": face["name"]}, shapes=[{"from_face": face["name"]}])
    print("sketch:", out[:200])
    built()
    gm = ai("get_model")
    print("get_model:", gm[:300])
    out = ai("add_feature", type="extrude", d=5)
    print("extrude:", out[:200])
    built()
    v = js(f"return {M}.result.body?.volume")
    check("AI: the face's outline taken and extruded 5 mm -> area × 5", v and abs(v - want) < 1e-4 * want)
    check("AI: get_model says where the sketch took its shapes from", "taken_from" in gm)
finally:
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        fails.append("console errors")
    d.quit()

print("FAILED:" if fails else "ALL OK", fails if fails else "")
sys.exit(1 if fails else 0)
