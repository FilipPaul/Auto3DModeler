"""The AI's sketch tools (RealSWReports 2026-10-28 21:49 / 21:58) through window.__app.agentHandlers, in headless Edge:
get_sketch (shapes with coordinates, relations, dims with names / values / locked, dof, what is free and what does not
fit), sketch_union (the report's rect + slot -> one outline, tangents / equal radius kept, the volume the exact union's),
sketch_auto_dims (fully defined after it), sketch_dim (R 20 by value; a wrong id refused; a lock freed), sketch_trim
(a circle cut by a line -> an arc), and in the open sketch gui_state's dimension labels with their values and a
get_screenshot that carries the labels (they are page elements over the 3D view, drawn onto the picture now).

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_ai_sketch.py http://127.0.0.1:5199 <out dir>
"""
import base64
import json
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
d.set_script_timeout(120)
js = d.execute_script
M = "window.__app.modeler"
H = "window.__app.agentHandlers"


def call(tool_name, **args):
    r = js(f"return {H}[arguments[0]](arguments[1]).then(r => ({{text: r.text, image: r.image || null}})).catch(e => ({{text: 'ERROR ' + e.message}}))", tool_name, args)
    print(f"· {tool_name} {json.dumps(args)[:80]}\n    {r['text'][:260]}")
    return r


def jcall(tool_name, **args):
    t = call(tool_name, **args)["text"]
    if t.startswith("ERROR"):
        raise SystemExit(f"FAIL {tool_name}: {t}")
    return json.loads(t)


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.05)
    raise TimeoutError(script)


def check(what, ok, detail=""):
    print(("OK   " if ok else "FAIL ") + what, detail)
    if not ok:
        raise SystemExit(1)


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Sketch tools")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": -20, "y": -30, "w": 65, "h": 65}}, {"slot": {"x1": 45, "y1": 9, "x2": 15, "y2": 35, "w": 46}}])
    v0 = jcall("add_feature", type="extrude", sketch="F1", d=10)["body"]["volume_mm3"]

    s = jcall("get_sketch", id="F1")
    arcs = [x for x in s["shapes"] if x["t"] == "arc"]
    check("get_sketch: 8 shapes with coordinates, 9 locks named with values, dof 0",
          len(s["shapes"]) == 8 and sum(x["locked"] for x in s["dims"]) == 9 and s["dof"] == 0 and s["fully_defined"]
          and all("centre" in a and "r" in a for a in arcs) and any(x["name"] == "R23" for x in s["dims"]) and any(x["name"] == "length 65" for x in s["dims"]), [x["name"] for x in s["dims"]])
    check("get_sketch: the relations (4 tangents, equal radii) and no conflicts",
          sum(k["t"] == "tan" for k in s["relations"]) == 4 and any(k["t"] == "eq" for k in s["relations"]) and not s["conflicts"]["contradicting"])

    u = jcall("sketch_union", sketch="F1")
    s = jcall("get_sketch", id="F1")
    v1 = jcall("get_model")["body"]["volume_mm3"]
    # the exact union: the square and the slot (shapely, 4096 segments a quarter) 5994.5008 mm² × 10
    check("sketch_union: one outline, the volume the exact union's", u["trimmed_pieces"] > 0 and abs(v1 - 59945.0078) < 0.01,
          f"({u['shapes']}, overlapping {v0} -> one outline {v1})")
    check("sketch_union: the tangents and equal radii that still apply stay", sum(k["t"] == "tan" for k in s["relations"]) >= 2 and any(k["t"] == "eq" for k in s["relations"]),
          [k["name"] for k in s["relations"]])
    check("one undo step for the union", js(f"return {M}.mode") == "part")

    a = jcall("sketch_auto_dims", id="F1")
    v2 = jcall("get_model")["body"]["volume_mm3"]
    check("sketch_auto_dims: fully defined, nothing moved", a["fully_defined"] and abs(v2 - v1) < 1e-3, f"(added {a['added']}, {a['locked']} locks)")
    again = jcall("sketch_auto_dims", id="F1")
    check("sketch_auto_dims again: it says why it adds nothing", "fully defined already" in again.get("error", ""), again.get("error"))

    arc = next(x["id"] for x in jcall("get_sketch", id="F1")["shapes"] if x["t"] == "arc")
    r = jcall("sketch_dim", id="F1", dim=f"rad:{arc}", value=20)
    check("sketch_dim: R 20 by value", any(x["kind"] == "rad" and x["value"] == 20 and x["locked"] for x in r["dims"]))
    bad = call("sketch_dim", id="F1", dim="nothing", value=3)["text"]
    check("sketch_dim: a wrong dimension is refused, saying what it takes", bad.startswith("ERROR") and "dims" in bad)
    dx = next(x for x in r["dims"] if x["kind"] == "dx" and x["locked"])
    r = jcall("sketch_dim", id="F1", dim=dx["id"], locked=False)
    check("sketch_dim locked false: a distance becomes a reference", any(x["id"] == dx["id"] and not x["locked"] for x in r["dims"]) and r["dof"] > 0)

    call("add_feature", type="sketch", plane={"datum": "XY", "offset": 10}, lock=False,
         shapes=[{"circle": {"x": 0, "y": 0, "d": 20}}, {"polyline": {"points": [[-15, 3], [15, 3], [15, 30], [-15, 30]]}}])
    sid = jcall("get_model")["steps"][-1]["id"]
    circ = next(x["id"] for x in jcall("get_sketch", id=sid)["shapes"] if x["t"] == "circle")
    t = jcall("sketch_trim", sketch=sid, shape=circ, at=[0, 10])
    s = jcall("get_sketch", id=sid)
    check("sketch_trim: the circle's top cut away -> an arc", not any(x["t"] == "circle" for x in s["shapes"]) and any(x["t"] == "arc" for x in s["shapes"]), t["shapes"])

    # the sketch open in the editor: gui_state lists its dimensions with values; the screenshot shows them
    ActionChains(d).double_click(d.find_elements(By.CSS_SELECTOR, "#modelLeft .mt-item")[0]).perform()
    wait(f"return {M}.mode === 'sketch' && {M}.sk?.dof !== null", 10)
    time.sleep(0.6)
    g = json.loads(call("gui_state")["text"])
    dims = [c for c in g["controls"] if c["kind"] == "dim"]
    lockbtn = [c for c in g["controls"] if c["kind"] == "button" and "›" in c["label"]]
    print("    dims:", [(c["label"], c.get("state")) for c in dims][:6], "| buttons:", [c["label"] for c in lockbtn][:4])
    check("gui_state: each dimension label with its value and state", len(dims) >= 8 and any("R20" in c["label"] for c in dims) and all(c.get("state") for c in dims))
    check("gui_state: a lock / delete button says which dimension it is on", lockbtn and all(c["label"].split(" › ")[0] for c in lockbtn))
    shot = call("get_screenshot")
    png = base64.b64decode(shot["image"])
    open(f"{OUT}/ai_sketch_labels.png", "wb").write(png)
    labels_drawn = js("""return new Promise((done) => { const img = new Image(); img.onload = () => {
        const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; const x = c.getContext('2d'); x.drawImage(img, 0, 0);
        const r = [...document.querySelectorAll('#modelViewport .sk-label.locked')][0].getBoundingClientRect(), v = document.querySelector('#modelViewport canvas').getBoundingClientRect();
        const k = img.width / v.width, px = x.getImageData(Math.round((r.left - v.left + 2) * k), Math.round((r.top - v.top + r.height / 2) * k), 1, 1).data;
        done([px[0], px[1], px[2]]); }; img.src = 'data:image/png;base64,' + arguments[0]; })""", shot["image"])
    check("get_screenshot: the locked labels are in the picture (their violet box)", abs(labels_drawn[0] - 0x2a) < 20 and abs(labels_drawn[2] - 0x45) < 25, labels_drawn)
    print("ALL OK")
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
