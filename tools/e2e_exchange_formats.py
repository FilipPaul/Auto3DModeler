"""Exchange formats beside STEP (SolidWorks, CATIA, Solid Edge …), in headless Edge:
IGES — a plate with a hole exported from the model's Export menu as .igs (the exact volume read back), opened again from
Open → CAD / 3D file as a 3D model (one solid step, the same volume); an assembly (Plate + Post) exported as one IGES
from its panel and by the AI (export iges: every part placed); the AI's open_file on an IGES of open surfaces: a
reference body with the warning.
Sheet DXF — the plate's drawing sheet: ⬇ DXF next to ⬇ PDF -> read back with ezdxf: mm, the layers (visible, hidden,
dims, text, frame), as many real dimensions as the sheet shows, the 40 mm width measured as 40 (the paper × DIMLFAC),
the title block's text; the AI's export dxf on the sheet the same.
GLB / OBJ — the plate (aluminium) from the Export menu as GLB (one node "Plate", metallic, 40 mm = 0.04 m) and OBJ (the
volume from its triangles); the assembly as GLB from the Export menu (a node per placed part, "Plate-1", "Post-1",
placed as on screen) and by the AI; the AI's export obj of the plate. No console errors.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_exchange_formats.py http://127.0.0.1:5199 <out dir>
"""
import base64
import io
import json
import math
import os
import struct
import sys
import time
import urllib.request
from pathlib import Path

import ezdxf
from selenium import webdriver
from selenium.webdriver.common.by import By

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from auto3d.modeler import doc, kernel as K  # noqa: E402

URL, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
A = "window.__app.assembly"
M = "window.__app.modeler"
H = "window.__app.agentHandlers"
bad = []
PLATE_HOLE = 8000 - math.pi * 16 * 10  # 40 × 20 × 10, a Ø8 hole through


def wait(script, t=120):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def check(ok, what):
    print(("  ok   " if ok else "  FAIL ") + what)
    if not ok:
        bad.append(what)


def call(t, **a):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", t, a)


def ai(tool, **args):
    req = urllib.request.Request(f"{URL}/api/agent/call", data=json.dumps({"tool": tool, "args": args}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        res = json.loads(r.read())
    return ("ERROR " if res.get("isError") else "") + "".join(c.get("text", "") for c in res.get("content", []))


def catch_saves():
    """The Save dialog answered by the test: each saved file kept as [name, base64]."""
    js("""window.__saved = []; window.showSaveFilePicker = async (o) => ({ name: o.suggestedName,
      createWritable: async () => ({ write: async (b) => { const u = new Uint8Array(await b.arrayBuffer()); let s = '';
        for (let i = 0; i < u.length; i += 8192) s += String.fromCharCode(...u.subarray(i, i + 8192));
        window.__saved.push([o.suggestedName, btoa(s)]); }, close: async () => {} }) });""")


def saved(n, name_end):
    """The n-th saved file (waited for) -> its bytes, written to OUT."""
    wait(f"return window.__saved.length >= {n}", 120)
    name, b64 = js(f"return window.__saved[{n - 1}]")
    check(name.endswith(name_end), f"saved as {name}")
    data = base64.b64decode(b64)
    Path(OUT, name).write_bytes(data)
    return Path(OUT, name), data


def world_box():
    """The box around every placed part of the assembly on screen, in the world (from its parts' boxes, as placed)."""
    flat = js(f"const a = {A}; return a.doc.instances.map((i) => [a.bodyOf(i).body.bbox, i.matrix])")
    pts = [[m[r] * x + m[4 + r] * y + m[8 + r] * z + m[12 + r] for r in range(3)]
           for bb, m in flat for x in (bb[0], bb[3]) for y in (bb[1], bb[4]) for z in (bb[2], bb[5])]
    return [min(p[k] for p in pts) for k in range(3)] + [max(p[k] for p in pts) for k in range(3)]


def glb_json(data):
    """A binary glTF's JSON (its header checked: glTF 2, the whole length)."""
    magic, version, length = struct.unpack("<4sII", data[:12])
    check(magic == b"glTF" and version == 2 and length == len(data), f"a GLB file: {magic} v{version}, {length} of {len(data)} bytes")
    n = struct.unpack("<I", data[12:16])[0]
    return json.loads(data[20:20 + n])


def obj_volume(data):
    v, vol = [], 0.0
    for line in data.decode("utf-8").splitlines():
        if line.startswith("v "):
            v.append([float(x) for x in line.split()[1:4]])
        elif line.startswith("f "):
            a, b, c = (v[int(q.split("/")[0]) - 1] for q in line.split()[1:4])
            vol += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6
    return vol


def menu(fmt):
    try:
        d.find_element(By.ID, "exportBtn").click()
        d.find_element(By.CSS_SELECTOR, f"#exportMenu [data-fmt={fmt}]").click()
    except Exception:
        d.save_screenshot(os.path.join(OUT, f"menu_{fmt}.png"))
        print("   menu:", js("const b = document.getElementById('exportBtn'); return [b.disabled, getComputedStyle(b).display, b.parentElement.className, document.body.className, getComputedStyle(document.querySelector('#exportMenu [data-fmt=" + fmt + "]')).display]"))
        raise


try:
    d.get(URL)
    wait("return !!window.__app")
    js("window.confirm = () => true")
    catch_saves()

    # ------------------------------------------------------------------ IGES
    # a plate with a hole (the AI's tools), exported from the Export menu as IGES
    call("new_model", name="Plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 20, "y": 10, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=8, through=True)
    wait(f"return Math.abs(({M}.result?.body?.volume || 0) - {PLATE_HOLE}) < 1e-3", 60)
    check(js("return getComputedStyle(document.querySelector('#exportMenu [data-fmt=iges]')).display") != "none", "IGES in the Export menu of a 3D model")
    menu("iges")
    igs, data = saved(1, "Plate.igs")
    shape, _, how = K.read_iges(data)
    check(how == "solid" and abs(K.volume(shape) - PLATE_HOLE) < 1e-3, f"the IGES holds the exact solid ({how}, {K.volume(shape):.3f} mm³)")

    # opened again from Open → CAD / 3D file: a 3D model with one solid step
    n_parts = js("return window.__app.project.parts.length")
    d.find_element(By.ID, "cadInput").send_keys(str(igs))
    wait(f"return window.__app.project.parts.length === {n_parts + 1} && window.__app.state.workspace === 'model' && !!{M}.result?.body", 60)
    f1 = js(f"return {M}.part.features")
    check(len(f1) == 1 and f1[0]["type"] == "solid" and f1[0]["op"] == "add" and f1[0]["file"] == "Plate.igs", f"one solid step {f1}")
    check(abs(js(f"return {M}.result.body.volume") - PLATE_HOLE) < 1e-3, "the IGES opened with the same volume")

    # an assembly: Plate + Post turned, exported as one IGES from its panel, then by the AI
    call("new_model", name="Post")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 5, "y": 5, "w": 10, "h": 10}}])
    call("add_feature", type="extrude", sketch="F1", d=30)
    call("new_assembly", name="Pair")
    call("insert_part", part="Plate")
    call("insert_part", part="Post")
    wait(f"return {A}.doc.instances.length === 2 && {A}.doc.instances.every(i => {A}.bodyOf(i)?.body)", 60)
    call("place_part", part="I2", x=100, y=0, z=0)
    check(js("return getComputedStyle(document.querySelector('#exportMenu [data-fmt=iges]')).display") != "none", "IGES in the Export menu of an assembly")
    js(f"{A}.sel = null; {A}.render()")  # (nothing chosen: the assembly's panel with its Export buttons)
    d.find_element(By.CSS_SELECTOR, "#asmBom [data-x=iges]").click()
    _, data = saved(2, "Pair.igs")
    shape, _, _ = K.read_iges(data)
    check(K.solids(shape) == 2 and abs(K.volume(shape) - (PLATE_HOLE + 3000)) < 1e-2 and all(abs(a - b) < 1e-3 for a, b in zip(K.bbox(shape), world_box())),
          f"the assembly's IGES: both parts, placed ({K.solids(shape)} solids, {K.volume(shape):.2f} mm³)")
    r = ai("export", format="iges", path=OUT)
    print("   AI:", r[:160])
    check(r.startswith("Exported the assembly as one IGES file") and Path(OUT, "Pair.igs").exists(), "the AI exports the assembly as IGES")

    # the AI opens an IGES of open surfaces: a reference body, with the warning
    st = doc.body_of({"features": [{"id": "S1", "type": "sketch", "plane": {"datum": "XY"}, "points": {"p1": [0, 0], "p2": [30, 0], "p3": [30, 30], "p4": [0, 30]},
                                    "entities": [{"id": f"l{i + 1}", "t": "line", "a": f"p{i + 1}", "b": f"p{(i + 1) % 4 + 1}"} for i in range(4)]},
                                   {"id": "E1", "type": "extrude", "sketch": "S1", "op": "add", "d": 5}]})
    fm = K._face_map(st.body.shape)
    open_igs = Path(OUT, "open_tray.iges")
    open_igs.write_bytes(K.to_iges(K.compound([fm.FindKey(k) for k in range(1, fm.Extent())]), surfaces=True))
    r = ai("open_file", path=str(open_igs))
    print("   AI:", r[:220])
    check(r.startswith("Opened open_tray.iges as the 3D model") and "op ref" in r and "reference body" in r, "open_file: an open IGES is a reference body, said so")
    wait(f"return window.__app.state.workspace === 'model' && ({M}.result?.refs || []).length === 1", 60)
    check(js(f"return !{M}.result.body && {M}.part.features[0].op === 'ref'"), "shown as a reference, no solid")
    check(js("return [...document.querySelectorAll('.toast')].some(t => t.textContent.includes('reference body'))"), "the warning shown")

    # ------------------------------------------------------------------ the drawing sheet as a DXF
    r = json.loads(call("sheet_open", part="Plate"))
    wait("return window.__app.state.workspace === 'sheet' && !!window.__app.sheet.d?.built", 60)
    n_dims = js("return window.__app.sheet.dxfDims().length")
    texts = [x["text"] for x in r["dims"]]
    print("   sheet:", r["paper"], r.get("scale"), texts)
    n_saved = js("return window.__saved.length")
    d.find_element(By.CSS_SELECTOR, ".sh-bar [data-a=dxf]").click()
    _, data = saved(n_saved + 1, ".dxf")

    def dxf_facts(data):
        dx = ezdxf.read(io.StringIO(data.decode("utf-8")))
        msp = dx.modelspace()
        dims = list(msp.query("DIMENSION"))
        vals = [round(dm.get_measurement() * dx.dimstyles.get(dm.dxf.dimstyle).dxf.dimlfac, 4) for dm in dims if dm.dxf.dimtype & 7 == 0]
        used = {e.dxf.layer for e in msp}
        return dx, dims, vals, used, [t.dxf.text for t in msp.query("TEXT")]

    dx, dims, vals, used, words = dxf_facts(data)
    check(dx.header["$INSUNITS"] == 4 and {"visible", "hidden", "dims", "text", "frame"} <= used, f"DXF in mm, layers {sorted(used)}")
    check(len(dims) == n_dims and n_dims == len(texts), f"every dimension of the sheet a DXF dimension ({len(dims)} of {n_dims})")
    check(40 in vals and 20 in vals, f"the 40 × 20 plate measured in true size {vals}")
    check(any("Plate" in w for w in words) and "Front" in words, "the title block and the view names")
    r = ai("export", format="dxf", path=OUT)
    print("   AI:", r[:120])
    path = r.rsplit(" to ", 1)[-1].strip()
    check(r.startswith("Exported") and path.endswith(".dxf") and Path(path).exists(), "the AI exports the sheet as DXF")
    if Path(path).exists():
        _, dims2, vals2, _, _ = dxf_facts(Path(path).read_bytes())
        check(len(dims2) == n_dims and 40 in vals2, "the AI's DXF: the same dimensions")

    # ------------------------------------------------------------------ GLB / OBJ
    call("open_part", id="Plate")
    wait(f"return window.__app.state.workspace === 'model' && window.__app.project.current?.name === 'Plate' && !!{M}.result?.body", 60)
    call("set_material", material="aluminium")
    n_saved = js("return window.__saved.length")
    menu("glb")
    _, data = saved(n_saved + 1, "Plate.glb")
    g = glb_json(data)
    pbr = g["materials"][0]["pbrMetallicRoughness"]
    pos = [g["accessors"][p["attributes"]["POSITION"]] for p in g["meshes"][0]["primitives"]]
    span = [round(max(a["max"][k] for a in pos) - min(a["min"][k] for a in pos), 6) for k in range(3)]
    check([n.get("name") for n in g["nodes"]] == ["Plate"] and abs(pbr["metallicFactor"] - 0.9) < 1e-4 and span == [0.04, 0.01, 0.02],
          f"the plate's GLB: one node, aluminium (metallic {pbr['metallicFactor']:.2f}), metres Y up {span}")
    menu("obj")
    _, data = saved(n_saved + 2, "Plate.obj")
    check(abs(obj_volume(data) - PLATE_HOLE) < PLATE_HOLE * 2e-3, f"the plate's OBJ: its volume {obj_volume(data):.1f} mm³")
    r = ai("export", format="obj", path=OUT)
    check(r.startswith("Exported") and r.strip().endswith("Plate.obj"), f"the AI exports OBJ: {r[:80]}")

    call("open_part", id="Pair")
    wait(f"return window.__app.state.workspace === 'assembly' && {A}.doc.instances.every(i => {A}.bodyOf(i)?.body)", 60)
    check(js("return getComputedStyle(document.querySelector('#exportMenu [data-fmt=glb]')).display") != "none", "GLB in the Export menu of an assembly")
    menu("glb")
    _, data = saved(n_saved + 3, "Pair.glb")
    g = glb_json(data)
    root = g["nodes"][g["scenes"][g.get("scene", 0)]["nodes"][0]]
    kids = [g["nodes"][k] for k in root.get("children", [])]
    want = js(f"return {A}.doc.instances.map(i => i.matrix.slice(12, 15))")  # where each part is placed (mm, Z up)
    got = [[round(v * 1000, 3) for v in (k.get("translation") or [0, 0, 0])] for k in kids]
    check(root.get("name") == "Pair" and [k.get("name") for k in kids] == ["Plate-1", "Post-1"], f"the assembly's GLB: {root.get('name')} -> {[k.get('name') for k in kids]}")
    check(all(abs(a - b) < 1e-3 for w, gt in zip(want, got) for a, b in zip([w[0], w[2], -w[1]], gt)), f"placed as on screen (glTF Y up) {got} ~ {want}")
    r = ai("export", format="glb", path=OUT)
    print("   AI:", r[:120])
    check(r.startswith("Exported the assembly as a binary glTF") and Path(OUT, "Pair.glb").exists(), "the AI exports the assembly as GLB")

    errs = [m["message"] for m in d.get_log("browser") if m["level"] == "SEVERE" and "favicon" not in m["message"]]
    check(not errs, f"no console errors {errs[:3]}")
    d.save_screenshot(os.path.join(OUT, "exchange_formats.png"))
finally:
    d.quit()
print("FAILED:" if bad else "ALL OK", *bad, sep="\n  ")
sys.exit(1 if bad else 0)
