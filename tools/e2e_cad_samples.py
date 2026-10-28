"""Real CAD files from other programs (samples/ToImportToOurApp: CATIA V5, NX, Creo, SolidWorks, Inventor / Fusion, I-DEAS, CoCreate,
AutoCAD, ACIS, EUCLID …), in headless Edge, each through the app as a user would:
- import: a part opens from Open → CAD / 3D file as a 3D model ("Open as one body" when asked), an assembly with
  "Open as an assembly", an IGES opens as it is — the time, faces / volume / bbox, coloured faces, the parts,
  placements and sub-assemblies, their names, and the warnings shown;
- edit (a part, or an assembly's biggest part): a sketch on its biggest flat face with a Ø3 circle cut 1 mm deep, a
  Ø2 hole through on the next flat face, a 0.3 mm fillet on an edge of that face — each by the AI's tools (ok and
  the volume going down);
- drawing: sheet_open -> get_sheet (views, dimensions), the AI's export pdf and dxf (the DXF read back with ezdxf);
- export back: the AI's export step / iges / glb; the STEP read again by the kernel (a part: its volume; an assembly:
  its parts, placements, sub-assemblies and total volume against the file's), and an assembly's STEP opened again by
  the AI's open_file as "assembly" (the same counts);
- 3D print: one mid-size part bigger than the bed (manifest "print": true) -> prepare_print -> Split to fit the
  Bambu Lab P1S: exact pieces that fit;
- console errors after each file.
Prints a table, writes <out dir>/cad_samples.json. Exit 1 when a check the manifest does not list as a known app bug
fails. Each file's expected values come from samples/ToImportToOurApp/samples.json (recorded by tests/test_cad_samples.py's numbers).

usage (server running with its own data folder, e.g. `A3D_DATA=<scratch> py server.py --port 5197 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_cad_samples.py http://127.0.0.1:5197 <out dir> [<name filters, comma separated>]
"""
import io
import json
import os
import sys
import time
import traceback
import urllib.request
from pathlib import Path

import ezdxf
from selenium import webdriver
from selenium.webdriver.common.by import By

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from auto3d.modeler import kernel as K  # noqa: E402

URL, OUT = sys.argv[1], sys.argv[2]
ONLY = [w.lower() for w in sys.argv[3].split(",")] if len(sys.argv) > 3 else []  # (parts of file paths, comma separated)
SAMPLES = ROOT / "samples" / "ToImportToOurApp"
os.makedirs(OUT, exist_ok=True)
MANIFEST = json.loads((SAMPLES / "samples.json").read_text(encoding="utf-8"))
M = "window.__app.modeler"
A = "window.__app.assembly"
H = "window.__app.agentHandlers"
P = "window.__app.printPanel"


def new_driver():
    opts = webdriver.EdgeOptions()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1600,1000")
    opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
    drv = webdriver.Edge(options=opts)
    drv.set_script_timeout(900)  # (a big assembly's drawing sheet takes longer than the default 30 s)
    cfg = getattr(drv.command_executor, "_client_config", None)
    if cfg is not None:  # (and longer than selenium's own 120 s for one command)
        cfg.timeout = 1000
    return drv


d = None


def js(*a):
    return d.execute_script(*a)


def wait(script, t=120, *args):
    end = time.time() + t
    while time.time() < end:
        v = js(script, *args)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script[:120])


def settled():
    time.sleep(0.3)
    wait(f"return !{M}.inflight", 300)
    time.sleep(0.2)


def call(tool, **a):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool, a)


def ai(tool, timeout=900, **args):
    req = urllib.request.Request(f"{URL}/api/agent/call", data=json.dumps({"tool": tool, "args": args}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        res = json.loads(r.read())
    return ("ERROR " if res.get("isError") else "") + "".join(c.get("text", "") for c in res.get("content", []))


def toasts():
    return js("return [...document.querySelectorAll('.toast')].map(t => t.textContent.trim()).filter(Boolean)")


def console_errors():
    return [m["message"][:200] for m in d.get_log("browser") if m["level"] == "SEVERE" and "favicon" not in m["message"]]


def fresh():
    """A clean page for each file (an empty project; nothing left from the file before)."""
    if not d.current_url.startswith(URL):
        d.get(URL)
        js("localStorage.setItem('a3d.printer', 'bambulab-p1s'); localStorage.setItem('a3d.joint', JSON.stringify({type: 'none', glue: 'none'}))")
    d.get(URL)
    wait("return !!window.__app")
    js("window.confirm = () => true")
    d.get_log("browser")  # (the log so far dropped)


def relay_ready():
    """The server's AI calls reach this page (not the one before the reload, whose long poll may still be open)."""
    name = js("return window.__app.project.current?.name")
    end = time.time() + 60
    while time.time() < end:
        if name in ai("list_parts", timeout=60):
            return
        time.sleep(0.5)
    raise TimeoutError("the AI's calls do not reach the page")


def answer(label, t=300):
    """Click the app's question's button starting with label (choose.js) -> the question's text, or None (not asked)."""
    end = time.time() + t
    while time.time() < end:
        q = js("return document.querySelector('.choose p')?.textContent || null")
        if q:
            next(b for b in d.find_elements(By.CSS_SELECTOR, ".choose .btn") if b.text.strip().startswith(label)).click()
            return q
        if js(f"return !!(window.__app.state.workspace === 'model' && {M}.result && ({M}.result.body || ({M}.result.refs || []).length))"):
            return None
        if any(("could not" in x or "error" in x.lower() or "no solid" in x.lower()) for x in toasts()):
            return None
        time.sleep(0.1)
    return None


def import_part(path, kind, with_files=False):
    """Open → CAD / 3D file -> a 3D model (or an assembly) -> facts. with_files: the other files of its folder picked
    with it (an assembly STEP whose parts are files of their own)."""
    t0 = time.time()
    n0 = js("return window.__app.project.parts.length")
    more = [str(f) for f in sorted(Path(path).parent.iterdir()) if f != Path(path)] if with_files else []
    d.find_element(By.ID, "cadInput").send_keys("\n".join([str(path), *more]))
    q = answer("Open as an assembly" if kind == "assembly" else "Open as one body")
    out = {"asked": q}
    if kind == "assembly":
        wait(f"""return window.__app.state.workspace === 'assembly' && {A}.doc.instances.length > 0
                 && {A}.doc.instances.every(i => {A}.bodyOf(i)?.body) || [...document.querySelectorAll('.toast')].some(t => /error|could not|no solid/i.test(t.textContent))""", 900)
        out["s"] = round(time.time() - t0, 1)
        if js("return window.__app.state.workspace") != "assembly":
            raise RuntimeError("not opened as an assembly: " + " | ".join(toasts())[:300])
        time.sleep(0.5)
        asm = json.loads(call("get_assembly"))
        flat = js(f"return {A}.flatParts().length")
        kinds = js("return window.__app.project.parts.slice(arguments[0]).map(p => [p.name, p.kind])", n0)
        vols = js(f"""const a = {A}; return a.flatParts().map((f) => {{
            const pid = (function find(list, ids) {{ const it = list.find((i) => i.id === ids[0]); return ids.length > 1 ? find(a.innerList(it), ids.slice(1)) : it.part; }})(a.doc.instances, f.id.split('/'));
            const b = a.bodies[pid]?.body; return [b?.volume || 0, (b?.faces || []).filter(x => x.color).length]; }})""")
        out.update(parts=sum(1 for _, k in kinds if k == "model"), subs=sum(1 for _, k in kinds if k == "assembly") - 1, placements=flat,
                   names=sorted({p["name"] for p in asm["parts"]})[:8], volume=round(sum(v for v, _ in vols), 3),
                   coloured_placements=sum(1 for _, c in vols if c), top=js("return window.__app.project.current?.name"))
    else:
        wait(f"""return (window.__app.state.workspace === 'model' && window.__app.project.parts.length > arguments[0] && {M}.result && ({M}.result.body || ({M}.result.refs || []).length))
                 || [...document.querySelectorAll('.toast')].some(t => /error|could not|no solid|no faces/i.test(t.textContent))""", 900, n0)
        out["s"] = round(time.time() - t0, 1)
        settled()
        body = js(f"return {M}.result?.body ? (({{volume, bbox, faces}}) => ({{volume, bbox, faces: faces.length, coloured: faces.filter(f => f.color).length}}))({M}.result.body) : null")
        refs = js(f"return ({M}.result?.refs || []).length")
        if not body and not refs:
            raise RuntimeError("not opened: " + " | ".join(toasts())[:300])
        if body:
            out.update(volume=round(body["volume"], 3), bbox=[round(v, 3) for v in body["bbox"]] if body["bbox"] else None, faces=body["faces"], coloured=body["coloured"])
        out["op"] = js(f"return {M}.part.features[0].op")
        out["refs"] = refs
    out["warnings"] = [x for x in toasts() if "IGES" in x or "surfaces" in x or "reference" in x][:2]
    return out


def flat_faces():
    """The model's flat faces whose normal is along an axis, biggest first: (name, normal, centroid)."""
    fs = []
    for n in ([0, 0, 1], [0, 0, -1], [0, 1, 0], [0, -1, 0], [1, 0, 0], [-1, 0, 0]):
        r = call("find_refs", kind="face", normal=n, limit=6)
        if r.startswith("ERROR"):
            raise RuntimeError(r)
        fs += [(f["name"], n, inside(f["name"]) or f["centroid"], f["area"]) for f in json.loads(r) if f.get("type") == "plane"]
    return sorted(fs, key=lambda f: -f[3])


def inside(name):
    """A point on the face itself (its centroid may be in a hole: a flange's): the middle of its roundest big triangle."""
    return js(f"""const v = {M}.view, b = v.body, pos = v.mesh?.geometry.attributes.position.array;
      if (!pos) return null;
      const ids = new Set(b.faces.filter((f) => f.name === arguments[0]).map((f) => f.id));
      let best = null, score = 0;
      for (let t = 0; t < v.faceIds.length; t++) {{
        if (!ids.has(v.faceIds[t])) continue;
        const p = [0, 1, 2].map((k) => [pos[t * 9 + 3 * k], pos[t * 9 + 3 * k + 1], pos[t * 9 + 3 * k + 2]]);
        const e = (a, c) => Math.hypot(a[0] - c[0], a[1] - c[1], a[2] - c[2]);
        const la = e(p[0], p[1]), lb = e(p[1], p[2]), lc = e(p[2], p[0]), s = (la + lb + lc) / 2;
        const area = Math.sqrt(Math.max(0, s * (s - la) * (s - lb) * (s - lc))), r = area / s;  // (the inscribed circle's radius)
        if (r > score) {{ score = r; best = [0, 1, 2].map((k) => (p[0][k] + p[1][k] + p[2][k]) / 3); }}
      }}
      return best;""", name)


def uv(n, c):
    """A world point on a face square to an axis -> the face sketch's world-origin coordinates (top X, Y; front X, Z; side Y, Z)."""
    return [c[0], c[1]] if n[2] else [c[0], c[2]] if n[1] else [c[1], c[2]]


def edit_model():
    """Sketch + cut, hole, fillet by the AI's tools on the model on screen -> {cut, hole, fillet}: 'ok -Δ' or the error."""
    out = {}
    settled()
    v0 = js(f"return {M}.result.body.volume")
    faces = flat_faces()
    if not faces:
        return {"cut": "no flat face along an axis"}
    for name, n, c, _ in faces[:4]:  # the biggest flat face whose middle is material
        n_steps = js(f"return {M}.part.features.length")
        r = call("add_feature", type="sketch", plane={"face": name, "origin": "world"}, shapes=[{"circle": {"x": uv(n, c)[0], "y": uv(n, c)[1], "d": 3}}])
        sk = js(f"return {M}.part.features.at(-1).id")
        r2 = call("add_feature", type="extrude", sketch=sk, d=1, op="cut")
        settled()
        v1 = js(f"return {M}.result.body?.volume || 0")
        if not r.startswith("ERROR") and not r2.startswith("ERROR") and v1 < v0 - 1:
            out["cut"] = f"ok {v1 - v0:.2f}"
            break
        while js(f"return {M}.part.features.length") > n_steps:  # (missed the material: take both steps back)
            call("undo")
            settled()
        out["cut"] = (r2 if r2.startswith("ERROR") else r)[:120] if (r.startswith("ERROR") or r2.startswith("ERROR")) else f"no change {v1 - v0:.2f}: {r2[:120]}"
    v0 = js(f"return {M}.result.body.volume")
    for name, n, c, _ in faces[1:5]:
        r = call("add_feature", type="hole", face=name, origin="world", points=[c], d=2, through=True)
        settled()
        v1 = js(f"return {M}.result.body?.volume || 0")
        if not r.startswith("ERROR") and v1 < v0 - 0.1:
            out["hole"] = f"ok {v1 - v0:.2f}"
            break
        if not r.startswith("ERROR"):
            call("undo")
            settled()
        out["hole"] = r[:120] if r.startswith("ERROR") else f"no change {v1 - v0:.2f}"
    v0 = js(f"return {M}.result.body.volume")
    bb = js(f"return {M}.result.body.bbox")
    fr = round(min(0.3, 0.05 * min(bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2])), 3)  # (0.3 mm; less on a tiny part)
    tries = []
    for name, *_ in faces[:4]:  # the longest straight edges of the biggest faces, 8 tries at most
        es = json.loads(call("find_refs", kind="edge", of_face=name, limit=20) or "[]")
        tries += sorted(es, key=lambda e: ("circle" in e, -e["length"]))[:2]  # (straight ones first; a round part: its circles)
    out["fillet"] = "no edge"
    for e in tries[:8]:
        r = call("add_feature", type="fillet", edges=[e["ref"]], r=fr)
        settled()
        ok = js(f"const f = {M}.part.features.at(-1); return f.type === 'fillet' && !({M}.result.issues || {{}})[f.id]")
        v1 = js(f"return {M}.result.body?.volume || 0")
        if not r.startswith("ERROR") and ok and abs(v1 - v0) > 1e-6:
            out["fillet"] = f"ok {v1 - v0:+.3f}"
            break
        if not r.startswith("ERROR"):
            call("undo")
            settled()
        out["fillet"] = r[:160] if r.startswith("ERROR") else f"no change {v1 - v0:+.3f}: " + r[:160]
    out["volume"] = round(js(f"return {M}.result.body.volume"), 3)
    return out


def dxf_facts(path):
    dx = ezdxf.readfile(path)
    msp = dx.modelspace()
    dims = list(msp.query("DIMENSION"))
    return {"dims": len(dims), "entities": len(msp), "layers": sorted({e.dxf.layer for e in msp})}


def drawing(stem, model_name):
    """The drawing sheet of the part / assembly on screen -> its views and dimensions, PDF and DXF written (the time
    it took); one that cannot be made: the message on the sheet (with ↻ Try again) and the toast."""
    t0 = time.time()
    r = call("sheet_open")
    if r.startswith("ERROR"):
        return {"sheet": r[:160]}
    try:
        wait("return window.__app.state.workspace === 'sheet' && (!!window.__app.sheet.d?.built || !!document.querySelector('.sh-failed'))", 900)
    except TimeoutError:
        out = {"sheet": "the sheet was not built in 900 s: " + " | ".join(toasts())[:160]}
        call("open_part", id=model_name)
        return out
    if not js("return !!window.__app.sheet.d?.built"):
        out = {"sheet": "not made: " + js("return document.querySelector('.sh-failed p').textContent")[:200],
               "retry": js("return !!document.querySelector('.sh-failed [data-a=retry]')"),
               "toast": any(x.startswith("The drawing could not be made") for x in toasts())}
        call("open_part", id=model_name)
        return out
    s = json.loads(call("get_sheet"))
    out = {"views": len(s.get("views") or []), "dims": len(s.get("dims") or []), "rev": s.get("revision"), "s": round(time.time() - t0, 1),
           "from_mesh": js("return !!window.__app.sheet.geo?.simple")}
    relay_ready()
    pdf = ai("export", format="pdf", path=str(Path(OUT, stem + ".pdf")))
    out["pdf"] = "ok" if pdf.startswith("Exported") and Path(OUT, stem + ".pdf").stat().st_size > 1000 else pdf[:120]
    dxf = ai("export", format="dxf", path=str(Path(OUT, stem + ".dxf")))
    if dxf.startswith("Exported"):
        f = dxf_facts(str(Path(OUT, stem + ".dxf")))
        out["dxf"] = f"ok {f['dims']} dims, {f['entities']} entities"
        out["dxf_dims_match"] = f["dims"] == out["dims"]
    else:
        out["dxf"] = dxf[:120]
    call("open_part", id=model_name)
    wait("return window.__app.state.workspace !== 'sheet'", 120)
    return out


def exports(stem, kind, original):
    """STEP / IGES / GLB by the AI's export; the STEP read back by the kernel and compared."""
    out = {}
    for fmt in ("step", "iges", "glb"):
        p = Path(OUT, f"{stem}.out.{fmt}")
        t0 = time.time()
        r = ai("export", format=fmt, path=str(p))
        out[fmt] = f"ok {p.stat().st_size // 1024} KB {time.time() - t0:.1f}s" if r.startswith("Exported") and p.exists() else r[:140]
    p = Path(OUT, f"{stem}.out.step")
    if p.exists():
        shape, cols, built = K.read_step_colours(p.read_bytes(), summary=True)
        out["rt_volume"] = round(K.volume(shape), 3)
        out["rt_structure"] = built
        out["rt_coloured"] = len(cols)
        if kind == "assembly":
            r = ai("open_file", path=str(p), **{"as": "assembly"})
            out["reopen"] = r[:200]
    return out


def print_split():
    """prepare_print -> the 3D print tab -> Split to fit this printer (exact pieces)."""
    r = call("prepare_print")
    wait("return !document.body.classList.contains('ws-model') && window.__app.state.model?.kind === 'mesh' && window.__app.state.solution", 300)
    wait("return document.querySelector('#rtab-print [data-a=split]')", 60)
    d.find_element(By.CSS_SELECTOR, "#rtab-print [data-a=split]").click()
    wait(f"return {P}.pieces && !{P}.busy", 600)
    time.sleep(0.5)
    ps = js(f"return ({P}.pieces || []).map(p => ({{size: p.size_mm.map(v => +v.toFixed(1)), orientation: p.orientation, exact: !!p.exact, faces: p.exact?.faces, volume: p.exact?.volume}}))")
    fits = all(p["orientation"] != "too big" for p in ps)
    return {"prepare": r[:80], "pieces": len(ps), "exact": sum(p["exact"] for p in ps), "fit": fits,
            "volume": round(sum(p["volume"] or 0 for p in ps), 1), "sizes": [p["size"] for p in ps][:4]}


def near(a, b, rel=1e-4):
    return a is not None and b is not None and abs(a - b) <= rel * max(1.0, abs(b))


def open_other(item):
    """A mesh / drawing / PDF / picture / board opened as the app's menus open it -> what came of it (ok: something opened)."""
    t0 = time.time()
    paths = [str(SAMPLES / p) for p in item.get("paths") or [item["path"]]]
    n0 = js("return window.__app.project.parts.length")
    kind = item["kind"]
    if kind == "pdf":
        d.find_element(By.ID, "pdfInput").send_keys(paths[0])
    elif kind == "picture":
        d.find_element(By.ID, "imgInput").send_keys(paths[0])
    else:
        d.find_element(By.ID, "cadInput").send_keys("\n".join(paths))
    err = "return [...document.querySelectorAll('.toast')].some(t => /error|could not|cannot|not supported|unsupported|closed format|install|please drop/i.test(t.textContent))"
    if kind == "picture":
        wait(f"return document.querySelectorAll('.wz-cand').length > 0 || ({err[7:]})", 180)
        n = js("return document.querySelectorAll('.wz-cand').length")
        out = {"candidates": n, "confidence": js("return [...document.querySelectorAll('.wz-conf')].map(e => e.textContent).slice(0, 3)")}
        if n:
            d.find_element(By.CSS_SELECTOR, ".wz-use").click()
            wait("return !!window.__app.state.solution?.mesh", 180)
            s = js("const s = window.__app.state.solution; return {bbox: s.bbox, tris: s.mesh.count, ok: s.ok}")
            out.update(part=s, ok=bool(s["tris"]))
    elif kind in ("drawing", "pcb"):
        wait(f"return (window.__app.project.parts.length > {n0} && window.__app.state.workspace === 'drawing') || ({err[7:]})", 300)
        ok = js("return window.__app.state.workspace === 'drawing'")
        out = {"ok": ok}
        if ok:
            out.update(js("const e = window.__app.drawing2d; return {entities: e.d.entities.length, layers: e.d.layers.length, units: e.d.units || null}"))
    elif kind == "pdf":
        wait(f"return !!window.__app.state.solution || !!window.__app.state.model?.issues?.length || ({err[7:]})", 300)
        s = js("const s = window.__app.state.solution; return s ? {ok: s.ok, bbox: s.bbox || null, source: window.__app.state.model?.source} : null")
        out = {"ok": bool(s), "part": s, "checks": js("return document.querySelectorAll('#checks li, .check-item').length")}
    else:  # a mesh (STL / OBJ: a 3D model's solid when small, else a sliced quick part; 3MF: not read)
        wait(f"""return (window.__app.project.parts.length > {n0} && ((window.__app.state.workspace === 'model' && !!{M}.result?.body)
                 || (window.__app.state.workspace === 'quick' && !!window.__app.state.solution))) || ({err[7:]})""", 300)
        ws = js("return window.__app.state.workspace")
        body = js(f"return {M}.result?.body ? {{volume: {M}.result.body.volume, faces: {M}.result.body.faces.length}} : null") if ws == "model" else None
        out = {"ok": js(f"return window.__app.project.parts.length > {n0}"), "workspace": ws, "solid": body}
    out["s"] = round(time.time() - t0, 1)
    out["toasts"] = [x[:120] for x in toasts()][:3]
    return out


rows, bad, others = [], [], []
try:
    d = new_driver()
    for item in MANIFEST["files"]:
        if ONLY and not any(w in item["path"].lower() for w in ONLY):
            continue
        path = SAMPLES / item["path"]
        stem = Path(item["path"]).stem.replace(" ", "_")
        kind, exp, known = item["kind"], item.get("expect") or {}, item.get("known") or {}
        row = {"file": item["path"], "program": item["program"], "format": item["format"], "kind": kind}
        print(f"\n=== {item['path']} ({item['program']}, {item['format']}, {kind})", flush=True)
        try:
            fresh()
            imp = import_part(path, "assembly" if kind == "assembly" else "part", item.get("with_files"))
            row["import"] = imp
            print("   import:", json.dumps(imp, ensure_ascii=False)[:400], flush=True)
            fails = []
            if kind == "assembly":
                if (imp["parts"], imp["placements"]) != (exp.get("parts"), exp.get("placements")):
                    fails.append(f"parts / placements {imp['parts']} / {imp['placements']} != {exp.get('parts')} / {exp.get('placements')}")
                if not near(imp["volume"], exp.get("asm_volume"), 1e-3):
                    fails.append(f"volume {imp['volume']} != {exp.get('asm_volume')}")
            elif imp.get("volume") is not None and exp.get("volume") is not None and not near(imp["volume"], exp["volume"]):
                fails.append(f"volume {imp['volume']} != {exp['volume']}")
            # edit: a part, or the assembly's biggest part
            if kind == "assembly":
                name = js(f"""const a = {A}, models = new Set(window.__app.project.parts.filter(p => p.kind === 'model').map(p => p.id));
                    return Object.entries(a.bodies).filter(([k, b]) => models.has(k) && b?.body).sort((x, y) => y[1].body.volume - x[1].body.volume)[0]?.[0] || null""")
                asm_name = js("return window.__app.project.current.name")
                if name:
                    call("open_part", id=name)
                    wait(f"return window.__app.state.workspace === 'model' && !!{M}.result?.body", 300)
            if js(f"return window.__app.state.workspace === 'model' && !!{M}.result?.body"):
                row["edit"] = edit_model()
            else:
                row["edit"] = {"cut": "no solid to edit (" + str(imp.get("op")) + ")"}
            print("   edit:", row["edit"], flush=True)
            model_name = js("return window.__app.project.current.name")
            if kind == "assembly":  # the drawing and the exports of the assembly itself
                call("open_part", id=asm_name)
                wait(f"return window.__app.state.workspace === 'assembly' && {A}.doc.instances.every(i => {A}.bodyOf(i)?.body)", 300)
                model_name = asm_name
            row["drawing"] = drawing(stem, model_name)
            print("   drawing:", row["drawing"], flush=True)
            if kind == "assembly":
                wait(f"return window.__app.state.workspace === 'assembly' && {A}.doc.instances.every(i => {A}.bodyOf(i)?.body)", 300)
            row["export"] = exports(stem, kind, imp)
            print("   export:", row["export"], flush=True)
            ex = row["export"]
            if kind == "assembly":
                want = {"parts": exp.get("parts"), "placements": exp.get("placements"), "subs": exp.get("subs")}
                if ex.get("rt_structure") != want:
                    fails.append(f"STEP round trip structure {ex.get('rt_structure')} != {want}")
                if ex.get("reopen", "").startswith("ERROR"):
                    fails.append("re-open of the exported STEP: " + ex["reopen"][:100])
            elif "volume" not in known and row["edit"].get("volume") and ex.get("rt_volume") is not None and not near(ex["rt_volume"], row["edit"]["volume"], 1e-5):
                fails.append(f"STEP round trip volume {ex['rt_volume']} != {row['edit']['volume']}")
            if item.get("print"):
                call("open_part", id=model_name)
                wait(f"return window.__app.state.workspace === 'model' && !!{M}.result?.body", 300)
                row["print"] = print_split()
                print("   print:", row["print"], flush=True)
                if not (row["print"]["pieces"] >= 2 and row["print"]["fit"] and row["print"]["exact"] == row["print"]["pieces"]):
                    fails.append(f"print split {row['print']}")
            for k in ("cut", "hole", "fillet"):
                v = str(row["edit"].get(k, "skipped"))
                if not v.startswith("ok") and k not in known.get("edit", []):
                    fails.append(f"edit {k}: {v}")
            for k, v in [("pdf", row["drawing"].get("pdf", row["drawing"].get("sheet"))), ("dxf", row["drawing"].get("dxf", row["drawing"].get("sheet")))] + \
                    [(k, ex.get(k)) for k in ("step", "iges", "glb")]:
                if not str(v).startswith("ok") and k not in known.get("export", []):
                    fails.append(f"{k}: {v}")
            row["console"] = console_errors()
            if row["console"] and "console" not in known:
                fails.append(f"console errors {row['console'][:2]}")
            row["fails"] = fails
        except Exception as e:  # noqa: BLE001 — a file that breaks the flow is a result, not the end of the run
            row["error"] = f"{type(e).__name__}: {e}"[:300]
            row["fails"] = [row["error"]]
            traceback.print_exc()
            try:
                row["console"] = console_errors()
                d.save_screenshot(os.path.join(OUT, stem + "_error.png"))
            except Exception:  # noqa: BLE001 — the browser itself is stuck: a new one for the next file
                d.quit()
                d = new_driver()
            if "unsupported" in known and "import" not in row:  # (a file the app cannot open: listed in the manifest)
                row["fails"] = []
                row["known"] = known["unsupported"]
        try:
            d.save_screenshot(os.path.join(OUT, stem + ".png"))
        except Exception:  # noqa: BLE001
            d.quit()
            d = new_driver()
        for f in row["fails"]:
            print("   FAIL", f, flush=True)
            bad.append(f"{item['path']}: {f}")
        rows.append(row)
        Path(OUT, "cad_samples.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    for item in MANIFEST.get("others", []):  # the other formats the app opens: meshes, drawings, PDF, pictures, a board
        if ONLY and not any(w in item["path"].lower() for w in ONLY):
            continue
        print(f"\n=== {item['path']} ({item['program']}, {item['kind']})", flush=True)
        row = {"file": item["path"], "kind": item["kind"], "program": item["program"]}
        try:
            fresh()
            row["result"] = open_other(item)
            row["console"] = console_errors()
            fails = [] if row["result"].get("ok") or item.get("known") else [f"not opened: {row['result']}"]
            fails += [f"console errors {row['console'][:2]}"] if row["console"] and not item.get("known") else []
        except Exception as e:  # noqa: BLE001
            fails = [] if item.get("known") else [f"{type(e).__name__}: {e}"[:200]]
            row["result"] = {"error": f"{type(e).__name__}: {e}"[:200], "toasts": toasts()}
        print("   ", json.dumps(row["result"], ensure_ascii=False)[:400], flush=True)
        d.save_screenshot(os.path.join(OUT, Path(item["path"]).stem.replace(" ", "_") + ".png"))
        for f in fails:
            print("   FAIL", f, flush=True)
            bad.append(f"{item['path']}: {f}")
        others.append(row)
        Path(OUT, "cad_samples_others.json").write_text(json.dumps(others, indent=1, ensure_ascii=False), encoding="utf-8")
finally:
    if d:
        d.quit()

for r in others:
    print("%-60s %-10s %s" % (r["file"][-60:], r["kind"], json.dumps(r["result"], ensure_ascii=False)[:150]))

print("\n%-48s %-26s %-7s %-6s %-30s %-24s %-16s %-28s %s" % ("file", "program", "format", "kind", "import", "edit", "drawing", "export / round trip", "print"))
for r in rows:
    imp = r.get("import") or {}
    if r.get("error"):
        imp_s = "ERROR " + r["error"][:60]
    elif r["kind"] == "assembly":
        imp_s = f"{imp.get('s')}s {imp.get('parts')}p/{imp.get('placements')}x/{imp.get('subs')}sub"
    else:
        imp_s = f"{imp.get('s')}s {imp.get('faces')}f {imp.get('op')}" + (" col" if imp.get("coloured") else "")
    ed = r.get("edit") or {}
    ed_s = " ".join(f"{k[0]}:{'ok' if str(ed.get(k, '-')).startswith('ok') else 'X'}" for k in ("cut", "hole", "fillet"))
    dr = r.get("drawing") or {}
    dr_s = f"{dr.get('views')}v {dr.get('dims')}d pdf:{'ok' if dr.get('pdf') == 'ok' else 'X'} dxf:{'ok' if str(dr.get('dxf', '')).startswith('ok') else 'X'}"
    ex = r.get("export") or {}
    ex_s = " ".join(f"{k}:{'ok' if str(ex.get(k, '')).startswith('ok') else 'X'}" for k in ("step", "iges", "glb")) + (f" rt:{ex.get('rt_structure', {}).get('placements', '-')}x" if ex else "")
    pr = r.get("print")
    pr_s = f"{pr['pieces']} pieces fit={pr['fit']}" if pr else ""
    print("%-48s %-26s %-7s %-6s %-30s %-24s %-16s %-28s %s" % (r["file"][-48:], r["program"][:26], r["format"][:7], r["kind"][:6], imp_s[:30], ed_s, dr_s, ex_s, pr_s))
print("\nFAILED:" if bad else "\nALL OK", *bad, sep="\n  ")
sys.exit(1 if bad else 0)
