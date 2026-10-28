"""Make samples/ExportFromOurApp/: files the app exported, to open in other programs (Solid Edge, FreeCAD, a STEP / glTF
viewer, a slicer, a DXF viewer) and check our exports. In headless Edge, through the AI's tools (the app's real export
paths, as the Export menu): a base plate with 4× M6 threaded countersunk holes (aluminium, its top face painted), a post
(steel, a blind M5 thread 12 deep in its top), a sub-assembly "Post pair" (the post twice) placed twice in the assembly "Frame" with
two library screws -> STEP / IGES / STL / OBJ / GLB / 3MF of the plate, STEP / IGES / GLB / 3MF / BOM CSV of the
assembly, the plate's drawing sheet as PDF and DXF, the assembly's drawing set as PDF, and the project file. Each file is
checked as it comes; tests/test_export_samples.py reads them all back. No console errors.

usage (server running, e.g. `py server.py --port 5193 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/make_export_samples.py http://127.0.0.1:5193 [out dir, default samples/ExportFromOurApp]
"""
import base64
import json
import sys
import time
import urllib.request
from pathlib import Path

from selenium import webdriver

ROOT = Path(__file__).resolve().parent.parent
URL = sys.argv[1]
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else ROOT / "samples" / "ExportFromOurApp").resolve()
OUT.mkdir(parents=True, exist_ok=True)
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
    r = js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", t, a)
    if str(r).startswith("ERROR"):
        check(False, f"{t}: {r[:200]}")
    return r


def ai(tool, **args):
    req = urllib.request.Request(f"{URL}/api/agent/call", data=json.dumps({"tool": tool, "args": args}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        res = json.loads(r.read())
    return ("ERROR " if res.get("isError") else "") + "".join(c.get("text", "") for c in res.get("content", []))


def export(fmt, name):
    """The AI's export (the server writes the file, as the Export menu gives it) -> OUT/name."""
    target = OUT / name
    target.unlink(missing_ok=True)
    r = ai("export", format=fmt, path=str(target))
    check(r.startswith("Exported") and target.exists() and target.stat().st_size > 0, f"{name}: {r[:110]}")
    return target


try:
    d.get(URL)
    wait("return !!window.__app")
    js("window.confirm = () => true")
    js("""window.__saved = []; window.showSaveFilePicker = async (o) => ({ name: o.suggestedName,
      createWritable: async () => ({ write: async (b) => { const u = new Uint8Array(await b.arrayBuffer()); let s = '';
        for (let i = 0; i < u.length; i += 8192) s += String.fromCharCode(...u.subarray(i, i + 8192));
        window.__saved.push([o.suggestedName, btoa(s)]); }, close: async () => {} }) });""")

    # ------------------------------------------------------------------ the parts
    call("new_model", name="Base plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": -40, "y": -25, "w": 80, "h": 50}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=10, through=True)
    call("add_feature", type="hole", face="F2:end", points=[[-30, -17], [30, -17], [-30, 17], [30, 17]], thread="M6", head="csk", through=True)
    call("set_material", material="aluminium", tolerance="m")
    call("paint_faces", faces=["F2:end"], color="#d9822b")
    wait(f"return !{M}.building && !!{M}.result?.body", 60)
    g = json.loads(call("get_model"))
    print("   plate:", g.get("size_mm") or g.get("bbox"), g.get("volume_mm3") or g.get("volume"), [s.get("ok") for s in g["steps"]])
    check(all(s.get("ok", True) for s in g["steps"]), "every step of the plate ok")

    call("new_model", name="Post")
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 12}}])
    call("add_feature", type="extrude", sketch="F1", d=40)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], thread="M5", through=False, depth=12)
    call("set_material", material="steel")
    wait(f"return !{M}.building && !!{M}.result?.body", 60)

    # ------------------------------------------------------------------ the assemblies
    call("new_assembly", name="Post pair")  # (the first part placed is fixed 📌 at the origin)
    call("insert_part", part="Post")
    call("insert_part", part="Post")
    wait(f"return {A}.doc.instances.length === 2 && {A}.doc.instances.every(i => {A}.bodyOf(i)?.body)", 60)
    call("place_part", part="I2", x=40, y=0, z=0)
    call("set_look", part="I2", color="#2e9e4f")

    call("new_assembly", name="Frame")
    call("insert_part", part="Base plate")
    call("insert_part", part="Post pair")
    call("insert_part", part="Post pair")
    wait(f"return {A}.doc.instances.length === 3 && {A}.doc.instances.every(i => {A}.bodyOf(i)?.body)", 60)
    call("place_part", part="I2", x=-20, y=-8, z=10)  # on the plate's top: posts at x ±20, y ±8
    call("place_part", part="I3", x=-20, y=8, z=10)
    for x, y in ((-30, -17), (30, -17), (-30, 17), (30, 17)):  # an ISO 10642 M6×16 in each countersink, its head flush
        r = json.loads(call("library_add", item="iso10642", size="M6", length=16, to="assembly"))
        call("place_part", part=r["placed"], x=x, y=y, z=-6)
    wait(f"return {A}.doc.instances.length === 7 && {A}.doc.instances.every(i => {A}.bodyOf(i)?.body)", 60)
    a = json.loads(call("get_assembly"))
    print("   parts list:", [(p["name"], p["qty"], p.get("pn")) for p in a["parts_list"]])
    check([p["qty"] for p in a["parts_list"]] == [1, 2, 4], "Frame: the plate, the Post pair twice, 4 screws")
    js("window.__app.state.projectName = 'Frame'")

    # ------------------------------------------------------------------ exports
    call("open_part", id="Base plate")
    wait(f"return window.__app.state.workspace === 'model' && window.__app.project.current?.name === 'Base plate' && !{M}.building && !!{M}.result?.body", 60)
    for fmt, ext in (("step", "step"), ("iges", "igs"), ("stl", "stl"), ("obj", "obj"), ("glb", "glb"), ("3mf", "3mf")):
        export(fmt, f"part_base_plate.{ext}")
    call("open_part", id="Frame")
    wait(f"return window.__app.state.workspace === 'assembly' && {A}.doc.instances.every(i => {A}.bodyOf(i)?.body)", 60)
    for fmt, ext in (("step", "step"), ("iges", "igs"), ("glb", "glb"), ("3mf", "3mf"), ("bom", "csv")):
        export(fmt, f"assembly_frame.{ext}" if fmt != "bom" else "assembly_frame_BOM.csv")

    r = json.loads(call("sheet_open", part="Base plate"))
    wait("return window.__app.state.workspace === 'sheet' && !!window.__app.sheet.d?.built", 60)
    print("   sheet:", r.get("paper"), r.get("scale"), [x["text"] for x in r["dims"]])
    export("pdf", "sheet_base_plate.pdf")
    export("dxf", "sheet_base_plate.dxf")
    r = json.loads(call("sheet_open", part="Frame"))
    wait("return window.__app.state.workspace === 'sheet' && !!window.__app.sheet.d?.built", 60)
    print("   assembly sheet:", r.get("paper"), r.get("scale"), [x.get("name") for x in r.get("parts_list") or []])
    export("pdf", "sheet_frame.pdf")
    export("dxf", "sheet_frame.dxf")

    # ------------------------------------------------------------------ the project file (💾 Save project)
    js("document.getElementById('saveBtn').click()")
    wait("return window.__saved.length >= 1", 60)
    name, b64 = js("return window.__saved[window.__saved.length - 1]")
    (OUT / "project_frame.a3d.json").write_bytes(base64.b64decode(b64))
    check(name.endswith(".a3d.json"), f"the project saved ({name})")

    errs = [m["message"] for m in d.get_log("browser") if m["level"] == "SEVERE" and "favicon" not in m["message"]]
    check(not errs, f"no console errors {errs[:3]}")
finally:
    d.quit()
for f in sorted(OUT.iterdir()):
    print(f"   {f.name:32} {f.stat().st_size:>9,} B")
print("FAILED:" if bad else "ALL OK", *bad, sep="\n  ")
sys.exit(1 if bad else 0)
