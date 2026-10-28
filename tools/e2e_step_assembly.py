"""STEP assemblies (as SolidWorks / CATIA / Solid Edge exchange them), in headless Edge: "Machine" built with the AI's
tools (Plate, Post turned on its side, the sub-assembly "Sub" with Post again and Plate) -> the AI's export as step: a STEP
assembly (a product per part, the sub-assembly nested, instance names) -> that file opened from Open → CAD / 3D file
-> the question "Open as an assembly" -> parts Plate and Post once each, Sub a sub-assembly, Machine on screen: its
parts list and every placed part's box as they were, Plate's colour kept -> dropped onto that assembly: a
sub-assembly of it -> the AI's open_file as "assembly" -> a plain one-body STEP opens as a 3D model, no question.

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
from auto3d.modeler import doc  # noqa: E402

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


try:
    d.get(URL)
    wait("return !!window.__app")
    js("window.confirm = () => true")

    # 0. Machine, built with the AI's tools, exported by the AI as a STEP assembly
    for name, w, h, dd in (("Plate", 40, 20, 10), ("Post", 10, 10, 30)):
        call("new_model", name=name)
        call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": w / 2, "y": h / 2, "w": w, "h": h}}])
        call("add_feature", type="extrude", sketch="F1", d=dd)
    js("const p = window.__app.project.parts.find(q => q.name === 'Plate'); p.data.color = '#ff0000'")
    call("new_assembly", name="Sub")
    call("insert_part", part="Post")
    call("insert_part", part="Plate")
    call("place_part", part="I2", x=0, y=0, z=30)
    call("new_assembly", name="Machine")
    call("insert_part", part="Plate")
    call("insert_part", part="Post")
    call("insert_part", part="Sub")
    wait(f"return {A}.doc.instances.length === 3 && {A}.doc.instances.every(i => {A}.bodyOf(i)?.body)", 60)
    call("place_part", part="I2", x=100, y=0, z=0, turn="x")
    call("place_part", part="I3", x=0, y=0, z=50)
    time.sleep(0.5)
    want = boxes()
    print("   built:", want)
    list0 = sorted((p["name"], p["qty"]) for p in json.loads(call("get_assembly"))["parts_list"])
    r = ai("export", format="step", path=OUT)
    print("   export:", r[:160])
    step = os.path.join(OUT, "Machine.step")
    check(r.startswith("Exported the assembly as a STEP assembly") and os.path.exists(step), "the AI exports the assembly as a STEP assembly")
    data = Path(step).read_bytes()
    text = data.decode("latin-1")
    check(text.count("NEXT_ASSEMBLY_USAGE_OCCURRENCE") == 5 and text.count("PRODUCT('Post'") == 1 and "PRODUCT('Sub'" in text and "'Post-1'" in text,
          "the file: a product per part, 5 placements, Sub nested, instance names")

    # 1. Open → CAD / 3D file: asked, opened as an assembly
    d.find_element(By.ID, "cadInput").send_keys(step)
    q = answer("Open as an assembly")
    check("2 different parts placed 4 times, 1 sub-assemblies" in q, f"the question: {q}")
    wait("return window.__app.state.workspace === 'assembly' && window.__app.project.current?.name === 'Machine' && window.__app.project.parts.length === 8", 60)
    wait(f"return {A}.doc.instances.length === 3 && {A}.doc.instances.every(i => {A}.bodyOf(i)?.body)", 60)
    kinds = js("return window.__app.project.parts.slice(4).map(p => [p.name, p.kind])")
    check(sorted(kinds) == [["Machine", "assembly"], ["Plate", "model"], ["Post", "model"], ["Sub", "assembly"]], f"project parts {kinds}")
    got = boxes()
    print("   boxes:", got)
    check(len(got) == len(want) and all(g[0] == w[0] and all(abs(a - b) < 1e-3 for a, b in zip(g[1:], w[1:])) for g, w in zip(got, want)),
          "every placed part's box as it was built")
    list1 = sorted((p["name"], p["qty"]) for p in json.loads(call("get_assembly"))["parts_list"])
    check(list1 == list0, f"the parts list as it was {list1}")
    look = js("return window.__app.project.parts.slice(4).find(p => p.name === 'Plate').data.features[0]")
    check(look["type"] == "solid" and look.get("blob"), "a part is a 3D model with one solid step on its own STEP")
    plate = js(f"return {A}.bodies[window.__app.project.parts.slice(4).find(p => p.name === 'Plate').id].body")
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
    check(r.startswith(f"Opened {os.path.basename(step)} as the assembly") and "2 different parts" in r, "open_file as assembly")
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
