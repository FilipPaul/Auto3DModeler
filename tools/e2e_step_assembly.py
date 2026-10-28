"""STEP assemblies (as SolidWorks / CATIA / Solid Edge exchange them), in headless Edge: a STEP assembly ("Machine":
Plate + Post, Post placed again inside the sub-assembly "Sub") opened from Open → CAD / 3D file -> the question "Open
as an assembly" -> parts Plate and Post once each, Sub a sub-assembly, Machine on screen: its parts list and every
placed part's box as in the file -> dropped onto that assembly: a sub-assembly of it -> the AI's open_file as
"assembly" -> a plain one-body STEP opens as a 3D model, no question.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_step_assembly.py http://127.0.0.1:5199 <out dir>
"""
import hashlib
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

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
H = "window.__app.agentHandlers"
bad = []
I16 = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
TURNED = [0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1, 0, 100, 0, 0, 1]
TILTED = [1, 0, 0, 0, 0, 0.6, 0.8, 0, 0, -0.8, 0.6, 0, 5, -6, 7.25, 1]


def box(w, h, dd):
    pts = {"p1": [0, 0], "p2": [w, 0], "p3": [w, h], "p4": [0, h]}
    lines = [{"id": f"l{i + 1}", "t": "line", "a": f"p{i + 1}", "b": f"p{(i + 1) % 4 + 1}"} for i in range(4)]
    return [{"id": "S1", "type": "sketch", "plane": {"datum": "XY"}, "points": pts, "entities": lines},
            {"id": "E1", "type": "extrude", "sketch": "S1", "op": "add", "d": dd}]


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


def answer(label):
    """Click an answer of the app's question (choose.js) -> the question's text."""
    wait("return !!document.querySelector('.choose')", 60)
    q = js("return document.querySelector('.choose p').textContent")
    btn = next(b for b in d.find_elements(By.CSS_SELECTOR, ".choose .btn") if b.text.startswith(label))
    btn.click()
    return q


def boxes():
    """Every placed part of the assembly on screen (sub-assemblies' too): its part's name and its box in the world."""
    flat = js(f"""const a = {A};
      return a.flatParts().map((f) => {{
        const pid = (function find(list, ids) {{ const it = list.find((i) => i.id === ids[0]); return ids.length > 1 ? find(a.innerList(it), ids.slice(1)) : it.part; }})(a.doc.instances, f.id.split('/'));
        return [a.partName(pid), a.bodies[pid]?.body?.bbox, f.matrix];
      }})""")
    out = []
    for name, bb, m in flat:
        corners = [(x, y, z) for x in (bb[0], bb[3]) for y in (bb[1], bb[4]) for z in (bb[2], bb[5])]
        w = [[m[r] * x + m[4 + r] * y + m[8 + r] * z + m[12 + r] for r in range(3)] for x, y, z in corners]
        out.append([name, *[round(min(p[k] for p in w), 3) + 0.0 for k in range(3)], *[round(max(p[k] for p in w), 3) + 0.0 for k in range(3)]])
    return sorted(out, key=str)


def want_boxes():
    """The same, from the kernel: the parts' solids placed by the file's matrices."""
    plate, post = (doc.body_of({"features": box(*s)}).body.shape for s in ((40, 20, 10), (10, 10, 30)))
    up50 = [*I16[:12], 0, 0, 50, 1]
    mul = lambda a, b: [sum(a[k * 4 + r] * b[c * 4 + k] for k in range(4)) for c in range(4) for r in range(4)]  # noqa: E731
    out = []
    for name, shape, m in (("Plate", plate, I16), ("Post", post, TURNED), ("Post", post, mul(up50, TILTED)), ("Plate", plate, mul(up50, [*I16[:12], 0, 0, 30, 1]))):
        out.append([name, *[round(v, 3) + 0.0 for v in K.bbox(K.placed(shape, m))]])
    return sorted(out, key=str)


def machine_step(path):
    """The assembly as SolidWorks would hand it over: a structured STEP (AP214)."""
    parts = {"P1": {"name": "Plate", "shape": doc.body_of({"features": box(40, 20, 10)}).body.shape, "colour": "#ff0000"},
             "P2": {"name": "Post", "shape": doc.body_of({"features": box(10, 10, 30)}).body.shape}}
    asms = {"A1": {"name": "Machine", "instances": [{"ref": "P1", "matrix": I16}, {"ref": "P2", "matrix": TURNED, "colour": "#00ff00"},
                                                    {"ref": "A2", "matrix": [*I16[:12], 0, 0, 50, 1]}]},
            "A2": {"name": "Sub", "instances": [{"ref": "P2", "matrix": TILTED}, {"ref": "P1", "matrix": [*I16[:12], 0, 0, 30, 1]}]}}
    data = K.write_step_tree(parts, asms, "A1", "Machine")
    Path(path).write_bytes(data)
    return data


try:
    step = os.path.join(OUT, "machine.step")
    data = machine_step(step)
    d.get(URL)
    wait("return !!window.__app")
    js("window.confirm = () => true")

    # 1. Open → CAD / 3D file: asked, opened as an assembly
    d.find_element(By.ID, "cadInput").send_keys(step)
    q = answer("Open as an assembly")
    check("2 different parts placed 4 times, 1 sub-assemblies" in q, f"the question: {q}")
    wait("return window.__app.state.workspace === 'assembly' && window.__app.project.current?.name === 'Machine'", 60)
    wait(f"return {A}.doc.instances.length === 3 && {A}.doc.instances.every(i => {A}.bodyOf(i)?.body)", 60)
    kinds = js("return window.__app.project.parts.map(p => [p.name, p.kind])")
    check(sorted(kinds) == [["Machine", "assembly"], ["Plate", "model"], ["Post", "model"], ["Sub", "assembly"]], f"project parts {kinds}")
    got, want = boxes(), want_boxes()
    print("   boxes:", got)
    check(len(got) == len(want) and all(g[0] == w[0] and all(abs(a - b) < 1e-3 for a, b in zip(g[1:], w[1:])) for g, w in zip(got, want)),
          f"every placed part's box as in the file {want}")
    colours = js(f"return {A}.doc.instances.map(i => i.colour || null)")
    check(colours == [None, "#00ff00", None], f"the placement's own colour from the file {colours}")
    look = js("return window.__app.project.parts.find(p => p.name === 'Plate').data.features[0]")
    check(look["type"] == "solid" and look.get("blob"), "a part is a 3D model with one solid step on its own STEP")
    plate = js(f"return {A}.bodies[window.__app.project.parts.find(p => p.name === 'Plate').id].body")
    check(abs(plate["volume"] - 8000) < 1e-3 and {f.get("color") for f in plate["faces"]} == {"#ff0000"}, f"Plate: 8000 mm³, red ({plate['volume']})")
    asm = json.loads(call("get_assembly"))
    check(sorted(p["name"] for p in asm["parts"]) == ["Plate", "Post", "Sub"], f"get_assembly parts {[p['name'] for p in asm['parts']]}")

    # 2. dropped onto the assembly: asked again, goes in as a sub-assembly
    sha = hashlib.sha256(data).hexdigest()
    n_parts = js("return window.__app.project.parts.length")
    js(f"""fetch('/api/blob/{sha}').then(r => r.blob()).then(b => {A}.insertFile(new File([b], 'machine.step')))""")
    answer("Open as an assembly")
    wait(f"return {A}.doc.instances.length === 4 && {A}.doc.instances.every(i => {A}.bodyOf(i)?.body)", 60)
    added = js(f"const it = {A}.doc.instances[3]; return [{A}.kindOf(it.part), {A}.partName(it.part)]")
    check(added == ["assembly", "Machine"], f"the dropped STEP is a sub-assembly {added}")
    check(js("return window.__app.project.parts.length") == n_parts + 4, "its own parts (2), sub-assembly (1) and itself (1)")

    # 3. the AI: open_file as an assembly
    r = ai("open_file", path=step, **{"as": "assembly"})
    print("   AI:", r[:200])
    check(r.startswith("Opened machine.step as the assembly") and "2 different parts" in r, "open_file as assembly")
    wait(f"return window.__app.state.workspace === 'assembly' && {A}.doc.instances.length === 3", 60)
    stl = Path(OUT) / "x.stl"
    stl.write_bytes(b"solid x\nendsolid x\n")
    check("is for a STEP file" in ai("open_file", path=str(stl), **{"as": "assembly"}), "as assembly: STEP only")

    # 4. a plain one-body STEP: no question, a 3D model as before
    plain = os.path.join(OUT, "plain.step")
    Path(plain).write_bytes(doc.export({"features": box(40, 20, 10)}, "step"))
    d.find_element(By.ID, "cadInput").send_keys(plain)
    wait("return window.__app.state.workspace === 'model' && !!window.__app.modeler.result?.body", 60)
    check(not js("return !!document.querySelector('.choose')"), "no question for a plain STEP")
    check(abs(js("return window.__app.modeler.result.body.volume") - 8000) < 1e-3, "opened as a 3D model, 8000 mm³")

    errs = [m["message"] for m in d.get_log("browser") if m["level"] == "SEVERE" and "favicon" not in m["message"]]
    check(not errs, f"no console errors {errs[:3]}")
    d.save_screenshot(os.path.join(OUT, "step_assembly.png"))
finally:
    d.quit()
print("FAILED:" if bad else "ALL OK", *bad, sep="\n  ")
sys.exit(1 if bad else 0)
