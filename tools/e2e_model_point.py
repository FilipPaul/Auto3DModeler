"""• Reference points in the 3D model, with REAL mouse clicks in headless Edge: a block 40 × 20 × 10 -> a click on its
front-right top corner, "• Reference point here": the step "Point 1" (icon •) in the list, a marker with its name at
(40, 0, 10) -> the extrude made 25 tall: the point follows its corner to (40, 0, 25) -> a second point on the middle of
the top front edge -> 📏 Measure snaps to it -> a sketch on the top: a circle dimensioned 6 from that point (↔ Dimension,
the end {point}), cut through; the block's front edge moves 6 out: the point and the hole follow -> turned off: no
marker -> the AI: add_feature {type: "point", at: {corner}}, find_refs kind "point".

  PYTHONIOENCODING=utf-8 py tools/e2e_model_point.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"
SK = f"{M}.sk"
H = "window.__app.agentHandlers"
fails = []


def check(what, ok, got=None):
    print(("OK  " if ok else "FAIL"), what, "" if got is None else f"-> {got}")
    if not ok:
        fails.append(what)


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(script)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def settle():
    time.sleep(0.4)
    wait(f"return !{M}.inflight && {M}.result?.body")
    time.sleep(0.4)


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#modelViewport canvas")


def off_xyz(p):
    return js(f"""const v = {M}.view, [x, y, z] = arguments[0];
      const [sx, sy] = v.toScreen(new (v.camera.position.constructor)(x, y, z)), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(p))


def off_uv(uv):
    return js(f"""const m = {M}, v = m.view, f = m.frame(), [u, w] = arguments[0];
      const y = [f.n[1]*f.x[2]-f.n[2]*f.x[1], f.n[2]*f.x[0]-f.n[0]*f.x[2], f.n[0]*f.x[1]-f.n[1]*f.x[0]];
      const p = new (v.camera.position.constructor)(f.o[0] + u*f.x[0] + w*y[0], f.o[1] + u*f.x[1] + w*y[1], f.o[2] + u*f.x[2] + w*y[2]);
      const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(uv))


def click(o):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *o).perform()
    time.sleep(0.2)
    ActionChains(d).click().perform()
    time.sleep(0.5)


def btn(sel):
    d.find_element(By.CSS_SELECTOR, sel).click()
    time.sleep(0.3)


def table():
    box = d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest")
    if not box:
        return None
    return {"title": box[0].find_element(By.CSS_SELECTOR, ".vs-head b").text,
            "items": [" ".join(b.text.split()) for b in box[0].find_elements(By.CSS_SELECTOR, ".vs-list button")]}


def press(label):
    next(b for b in d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-list button") if label in b.text).click()
    time.sleep(0.6)


def points():
    return js(f"return {M}.result.points")


def markers():
    return js("return [...document.querySelectorAll('#modelViewport .m-pt')].map(e => e.textContent)")


def holes():
    b = js(f"return {M}.result.body")
    return sorted([round(c, 3) for c in f["centroid"][:2]] for f in b["faces"] if f["type"] == "cylinder")


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Reference points")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    settle()
    js(f"{M}.view.setView('iso')")
    time.sleep(0.5)

    # 1. a click on a corner -> • Reference point here
    click(off_xyz([40, 0, 10]))
    tb = table()
    check("a corner's table offers • Reference point here", tb and any("Reference point here" in x for x in tb["items"]), tb)
    press("Reference point here")
    settle()
    f = js(f"return {M}.part.features.at(-1)")
    check("the step: type point, named Point 1", f["type"] == "point" and f["name"] == "Point 1", (f["type"], f["name"], json.dumps(f["at"])))
    row = js(f"return [...document.querySelectorAll('#modelLeft .mt-item, .mt-tree .mt-item')].map(r => (r.dataset.kind === 'point' && r.dataset.parent === 'ref' ? '•' : r.dataset.kind) + ' ' + r.querySelector('.mt-name').textContent + ' · ' + r.querySelector('.mt-what').textContent)")
    check("in the step list: a point under Reference", any(r.startswith("• Point 1") for r in row), row)
    check("at the corner (40, 0, 10)", points().get(f["id"]) == [40, 0, 10], points())
    check("drawn: a marker with its name", "• Point 1" in markers(), markers())
    d.save_screenshot(f"{OUT}/point1_corner.png")

    # 2. the extrude gets taller: the point follows its corner
    call("edit_feature", id="F2", fields={"d": 25})
    settle()
    check("extrude 25 tall -> the point at (40, 0, 25)", points().get("F3") == [40, 0, 25], points())
    check("its stored place follows", js(f"return {M}.part.features.find(f => f.id === 'F3').at.vertex.fp") == [40, 0, 25])
    check("the step is ok", js(f"return {M}.status('F3').ok"))

    # 3. a second point on the middle of the top front edge
    js(f"{M}.view.setView('iso')")
    time.sleep(0.5)
    click(off_xyz([20, 0, 25]))
    tb = table()
    check("the edge middle's table", tb and "midpoint" in tb["title"].lower() or "middle" in (tb or {}).get("title", "").lower(), tb and tb["title"])
    press("Reference point here")
    settle()
    f = js(f"return {M}.part.features.at(-1)")
    check("Point 2 on the edge's middle", f["name"] == "Point 2" and "mid" in f["at"] and points().get(f["id"]) == [20, 0, 25], (f["name"], json.dumps(f["at"]), points()))
    p2 = f["id"]

    # 4. 📏 Measure snaps to it
    btn("#modelViewport [data-a=measure]")
    o = off_xyz([20, 0, 25])
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), o[0] + 3, o[1] + 2).perform()
    time.sleep(0.4)
    snap = js("return document.querySelector('#modelViewport .m-snap')?.textContent")
    check("📏 Measure: the snap mark names the point", snap == "Point 2", snap)
    ActionChains(d).click().perform()
    time.sleep(0.4)
    a = js(f"const p = {M}.measuring?.a; return p && [p.x, p.y, p.z]")
    check("📏 Measure from the point", a and [round(v, 6) for v in a] == [20, 0, 25], a)
    btn("#modelViewport [data-a=measure]")

    # 5. a sketch on the top: a circle 6 from Point 2 (↔ Dimension to it)
    btn("#modelViewport [data-a=sketch]")
    click(off_xyz([12, 12, 25]))
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.6)
    fr = js(f"return {M}.frame()")
    print("sketch on the top face, origin", fr["o"])
    pu = [20 - fr["o"][0], 0 - fr["o"][1]]  # (the face's x is the world's x)
    btn(".m-cmdbar [data-a=circle]")
    click(off_uv([pu[0], pu[1] + 5]))
    click(off_uv([pu[0] + 2, pu[1] + 5]))
    btn(".m-cmdbar [data-a=dim]")
    click(off_uv([pu[0] + 2, pu[1] + 5]))  # the circle -> its centre
    click(off_uv(pu))                      # the reference point
    time.sleep(0.6)
    inp = d.find_elements(By.CSS_SELECTOR, ".sk-input")
    check("the size editor opened", bool(inp))
    inp[0].send_keys(Keys.CONTROL, "a")
    inp[0].send_keys("6", Keys.ENTER)
    time.sleep(0.8)
    dim = js(f"return {SK}.f.dims.find(x => [x.a, x.b].some(e => e && e.point))")
    check("a dimension to the point ({point: id})", bool(dim) and any(isinstance(e, dict) and e.get("point") == p2 for e in (dim["a"], dim["b"])), json.dumps(dim))
    d.save_screenshot(f"{OUT}/point2_sketch.png")
    btn("#modelViewport .view-actions [data-a=finish]")
    settle()
    js("document.querySelector('#modelRight [data-k=through]')?.click()")
    settle()
    btn("#modelViewport .view-actions [data-a=ok]")
    settle()
    h0 = holes()
    check("cut: the hole 6 from the front edge", h0 == [[20, 6]], h0)
    # the block's front edge moves 6 out (y -6): the point and the hole go along
    call("edit_feature", id="F1", fields={"shapes": [{"rect": {"x": 0, "y": -6, "w": 40, "h": 26}}]})
    settle()
    check("Point 2 followed the edge", points().get(p2) == [20, -6, 25], points())
    check("the hole followed the point", holes() == [[20, 0]], holes())
    js(f"{M}.view.setView('iso')")
    time.sleep(0.4)
    d.save_screenshot(f"{OUT}/point3_followed.png")

    # 6. turned off: no marker; on again
    js(f"{M}.toggleOff('F3')")
    settle()
    check("Point 1 off: its marker gone", "• Point 1" not in markers() and "• Point 2" in markers(), markers())
    js(f"{M}.toggleOff('F3')")
    settle()

    # 7. the AI
    r = json.loads(call("add_feature", type="point", at={"corner": [40, 20, 25]}))
    check("AI add_feature point: ok", r.get("ok") is True, r)
    pid = r["id"]
    check("at the corner (40, 20, 25)", points().get(pid) == [40, 20, 25], points())
    refs = json.loads(call("find_refs", kind="point", limit=5))
    check("find_refs kind point lists the points first", [x.get("point") for x in refs[:3]] == ["F3", p2, pid], refs[:4])
    check("… then corners with a ready ref", any("corner" in x and "vertex" in x["ref"] for x in refs), refs[3:])
    err = call("add_feature", type="point", at={})
    check("AI add_feature point without a place: refused", err.startswith("ERROR"), err)
    gm = json.loads(call("get_model"))
    check("get_model shows the point", any(s["type"] == "point" and s.get("xyz") == [40, 20, 25] for s in gm["steps"]), [s for s in gm["steps"] if s["type"] == "point"])
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    d.quit()
print("FAILED:" if fails else "ALL OK", fails or "")
sys.exit(1 if fails or errs else 0)
