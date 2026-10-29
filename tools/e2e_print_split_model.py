"""Exact print pieces of a 3D model part, in headless Edge: a round bar Ø80 × 400 lying along x ->
🖨 Prepare for 3D print (a STEP printing copy on the 3D print tab, its hint says the pieces are exact) -> Bambu Lab
P1S, a plain cut -> Split to fit this printer: 2 pieces cut from the exact solid (a handful of faces each, smooth walls — triangle
counts from the response, against the sliced part's), both fit the bed; dowel pins -> the pockets cut too; the STL /
STEP zips of the pieces.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_print_split_model.py http://127.0.0.1:5199 <out dir>
"""
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"
H = "window.__app.agentHandlers"
P = "window.__app.printPanel"
failed = []


def check(name, ok, *info):
    print(("OK  " if ok else "FAIL") + f" {name}", *info)
    if not ok:
        failed.append(name)


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def settled():
    time.sleep(0.3)
    wait(f"return !{M}.inflight")
    time.sleep(0.3)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def pieces():
    return js(f"return ({P}.pieces || []).map(p => ({{index: p.index, size: p.size_mm, orientation: p.orientation, exact: p.exact, count: p.mesh.count}}))")


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.setItem('a3d.printer', 'bambulab-p1s'); localStorage.setItem('a3d.joint', JSON.stringify({type: 'none', glue: 'none'}))")
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Bar")
    call("add_feature", type="sketch", plane="YZ", shapes=[{"circle": {"x": 0, "y": 40, "d": 80}}])
    call("add_feature", type="extrude", sketch="F1", d=400)
    settled()
    b = js(f"return {M}.result.body")
    vol = b["volume"]
    check("the bar", abs(vol - 3.14159265359 * 40 * 40 * 400) < 1e-3, round(vol, 3), b["bbox"])

    # 🖨 Prepare for 3D print -> a STEP printing copy on the 3D print tab
    hint = js("return document.querySelector('#modelExport [data-a=toPrint]')?.closest('div').previousElementSibling?.textContent")
    check("the model's hint says exact", "exact" in (hint or ""), hint)
    d.find_element(By.CSS_SELECTOR, "#modelExport [data-a=toPrint]").click()
    wait("return !document.body.classList.contains('ws-model') && window.__app.state.model?.kind === 'mesh' && window.__app.state.solution", 90)
    time.sleep(1)
    m = js("return {source: window.__app.state.model.source, mesh_id: window.__app.state.model.mesh_id, tab: document.querySelector('.rtab.active')?.dataset.rtab, sliced: window.__app.state.solution.mesh?.count}")
    check("a STEP printing copy on the 3D print tab", m["mesh_id"].endswith(".step") and m["tab"] == "print", m)
    wait("return document.querySelector('#rtab-print [data-a=split]')")
    exact_hint = js("return document.querySelector('#rtab-print .exact-hint')?.textContent")
    check("the print tab says the pieces are exact", bool(exact_hint), exact_hint)
    d.save_screenshot(f"{OUT}/ps1_copy.png")

    # Split to fit this printer: exact pieces
    d.find_element(By.CSS_SELECTOR, "#rtab-print [data-a=split]").click()
    wait(f"return {P}.pieces && !{P}.busy", 120)
    time.sleep(0.5)
    ps = pieces()
    usable = 256 - 2 * 5
    print("pieces:", ps)
    check("2 pieces", len(ps) == 2)
    check("cut from the exact solid (few faces)", all(p["exact"] and p["exact"]["faces"] <= 8 for p in ps), [p["exact"] and p["exact"]["faces"] for p in ps])
    check("they fit the bed", all(p["orientation"] != "too big" and max(p["size"][:2]) <= usable + 1e-6 for p in ps), [p["size"] for p in ps])
    check("smooth: fine triangles from the exact solid", all(p["count"] == p["exact"]["triangles"] for p in ps),
          "triangles", [p["count"] for p in ps], "vs the sliced whole part", m["sliced"])
    check("volumes add up", abs(sum(p["exact"]["volume"] for p in ps) - vol) < 1e-3, sum(p["exact"]["volume"] for p in ps), vol)
    notes = js("return [...document.querySelectorAll('#rtab-print .fit-note')].map(e => e.textContent)")
    check("the issues say exact split", any("Exact split" in n for n in notes), notes[:2])
    tags = js("return [...document.querySelectorAll('#rtab-print .piece span')].map(e => e.textContent)")
    check("each piece marked exact", sum("exact" in t for t in tags) == 2, tags)
    d.save_screenshot(f"{OUT}/ps2_pieces.png")

    # dowel pins: pockets cut in the exact pieces
    js(f"{P}.setJoint({{type: 'dowel'}})")
    time.sleep(0.5)
    wait(f"return {P}.pieces && !{P}.busy && ({P}.connectors || []).length", 120)
    time.sleep(0.5)
    ps2 = pieces()
    pins = js(f"return {P}.connectors.reduce((n, g) => n + g.qty, 0)")
    pocket = 15.2 * 8.4 * 4.4
    check("dowel pockets cut exactly", pins > 0 and all(abs(p["exact"]["volume"] - (vol / 2 - pins * pocket)) < 1e-3 for p in ps2),
          pins, "pins", [round(p["exact"]["volume"], 3) for p in ps2])
    d.save_screenshot(f"{OUT}/ps3_dowels.png")

    # the zips of the pieces
    for fmt in ("stl", "step"):
        r = js(f"""const {{ solution, ...body }} = {P}.getBody();
          return fetch('/api/export/{fmt}', {{method: 'POST', headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{...body, printer: {P}.selected, margin: {P}.margin, split: true, joint: {P}.jointRequest()}})}})
            .then(async (res) => [res.status, res.headers.get('Content-Type'), (await res.arrayBuffer()).byteLength]);""")
        check(f"{fmt.upper()} zip of the pieces", r[0] == 200 and r[1] == "application/zip" and r[2] > 1000, r)
    errors = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    check("no console errors", not errors, errors)
finally:
    d.quit()
print("ALL OK" if not failed else f"FAILED: {failed}")
sys.exit(1 if failed else 0)
