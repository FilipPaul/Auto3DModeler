"""A snap point clicked offers what it belongs to, in headless Edge with real mouse clicks:
1. 3D model: a 60 × 40 × 10 block, an M5 ⌴ counterbore hole (◎ Hole) and a Ø8 pocket cut by an extrude. The hole's
   centre clicked: "◎ Select the hole M5" in the top 3 rows, "◯ Select the circle Ø…" too, the point's own rows below
   -> Select the hole: the hole's table (Type ▾ / Size ▾), the step chosen -> the centre again, Select the circle: the
   edge's table (Fillet this edge) -> the pocket's centre: "Select the round face Ø8" (not a Hole step: no "hole") ->
   its table -> an edge's middle: "⟋ Select the edge" -> the edge's table.
2. Sketch: a circle drawn, its centre clicked with ⬚ Select: "◯ Select the circle Ø…" first -> the circle picked.
3. Assembly: a plate with a Ø20 hole placed, seen from the top; the hole's centre clicked: "◎ Select the hole Ø20" -> its round face
   chosen, the table shows its joints (Concentric).

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_select_from_point.py http://127.0.0.1:5199 <out dir>
"""
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
js = d.execute_script
H = "window.__app.agentHandlers"
M = "window.__app.modeler"
A = "window.__app.assembly"
fails = []


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


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


def settled():
    time.sleep(0.6)
    wait(f"return !{M}.inflight")
    time.sleep(0.4)


def off(view, p):
    return js(f"""const v = {view}.view, V = v.camera.position.constructor, [sx, sy] = v.toScreen(new V(...arguments[0])), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(p))


def click(cv, o):
    ActionChains(d, duration=30).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, cv), *o).perform()
    time.sleep(0.3)
    ActionChains(d).click().perform()
    time.sleep(0.8)


def rows(vp="#modelViewport"):
    return [" ".join(b.text.split()) for b in d.find_elements(By.CSS_SELECTOR, f"{vp} .view-suggest .vs-list button[data-sg]")]


def press(text, vp="#modelViewport"):
    next(b for b in d.find_elements(By.CSS_SELECTOR, f"{vp} .view-suggest .vs-list button[data-sg]") if any(x in b.text for x in text)).click()
    time.sleep(0.8)


def head(vp="#modelViewport"):
    return js(f"return document.querySelector('{vp} .view-suggest .vs-head b')?.textContent || ''")


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('a3d.snap3d')")

    # ---- 1. the 3D model
    call("new_model", name="Points")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="hole", face="F2:end", points=[[-15, 0]], hole_type="counterbore", standard="M5", through=True)
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 45, "y": 20, "d": 8}}])
    call("add_feature", type="extrude", sketch="F4", op="cut", d=100, symmetric=True)
    settled()
    js(f"{M}.view.setView('iso')")
    time.sleep(0.8)
    CV = "#modelViewport canvas"

    click(CV, off(M, [15, 20, 10]))
    r = rows()
    print("the hole's centre:", head(), "|", r[:5])
    check("“Select the hole M5” in the top 3 rows", any("Select the hole M5" in x or "Vybrat díru M5" in x for x in r[:3]))
    check("“Select the circle Ø…” offered too, the point's own rows below", any("Select the circle" in x or "Vybrat kružnici" in x for x in r) and any("Measure from here" in x or "Měřit odsud" in x for x in r[2:]))
    press(["Select the hole", "Vybrat díru"])
    r = rows()
    print("  -> the hole's table:", head(), "|", r[:4])
    check("Select the hole: the hole's table (Type / Size), the step chosen", js(f"return {M}.selected") == "F3" and any(x.split(" ", 1)[-1].startswith(("Type:", "Typ:")) for x in r[:3]))

    js(f"{M}.selectStep(null); {M}.dropSuggest()")  # (chosen, the hole's Ø label sits on its centre)
    click(CV, off(M, [15, 20, 10]))
    press(["Select the circle", "Vybrat kružnici"])
    r = rows()
    print("  -> the circle's table:", head(), "|", r[:5])
    check("Select the circle: the edge's table (Fillet this edge)", any("Fillet this edge" in x or "Zaoblit tuto hranu" in x for x in r))

    js(f"{M}.selectStep(null); {M}.dropSuggest()")
    click(CV, off(M, [45, 20, 10]))
    r = rows()
    print("the pocket's centre:", head(), "|", r[:4])
    check("the pocket: “Select the round face Ø8”, no “Select the hole”", any("Select the round face Ø8" in x or "Vybrat válcovou plochu Ø8" in x for x in r[:3]) and not any("Select the hole" in x or "Vybrat díru" in x for x in r))
    press(["Select the round face", "Vybrat válcovou plochu"])
    r = rows()
    print("  -> its table:", head(), "|", r[:4])
    check("its round face's table (the extrude's step)", js(f"return {M}.selected") == "F5" and any("Round its edges" in x or "Zaoblit její hrany" in x for x in r))

    js(f"{M}.selectStep(null); {M}.dropSuggest()")
    click(CV, off(M, [30, 0, 10]))
    r = rows()
    print("an edge's middle:", head(), "|", r[:4])
    check("an edge's middle: “Select the edge” first", r and ("Select the edge" in r[0] or "Vybrat hranu" in r[0]))
    press(["Select the edge", "Vybrat hranu"])
    check("its table: the edge's", any("Fillet this edge" in x or "Zaoblit tuto hranu" in x for x in rows()) and head() in ("An edge", "Hrana"))
    d.save_screenshot(f"{OUT}/select_from_point_model.png")

    # ---- 2. the sketch: a circle's centre
    d.find_element(By.ID, "newModelBtn").click()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.8)
    js(f"{M}.sk.setTool('circle')")
    SK = f"{M}.sk"

    def off_uv(uv):
        return js(f"""const m = {M}, v = m.view, f = m.frame(), [u, w] = arguments[0];
          const y = [f.n[1]*f.x[2]-f.n[2]*f.x[1], f.n[2]*f.x[0]-f.n[0]*f.x[2], f.n[0]*f.x[1]-f.n[1]*f.x[0]];
          const p = new (v.camera.position.constructor)(f.o[0] + u*f.x[0] + w*y[0], f.o[1] + u*f.x[1] + w*y[1], f.o[2] + u*f.x[2] + w*y[2]);
          const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
          return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(uv))
    click(CV, off_uv((10, 10)))
    click(CV, off_uv((15, 10)))
    js(f"{SK}.setTool('select')")
    time.sleep(0.3)
    click(CV, off_uv((10, 10)))
    r = rows()
    print("the circle's centre:", js(f"return {SK}.picks.map(q => q.kind)"), "|", r[:4])
    check("sketch: “Select the circle Ø…” first", r and ("Select the circle Ø" in r[0] or "Vybrat kružnici Ø" in r[0]))
    press(["Select the circle", "Vybrat kružnici"])
    check("sketch: the circle picked", js(f"return {SK}.picks.map(q => q.kind)") == ["circle"])
    js(f"{M}.finishSketch && {M}.cancelSketch ? {M}.cancelSketch() : null")

    # ---- 3. the assembly: a hole's centre on a placed part
    call("new_model", name="Plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=20, through=True)
    call("new_assembly", name="Picks")
    call("insert_part", part="Plate")
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    js(f"{A}.view.setView('top')")  # (looking down through the hole: its centre, away from its rim)
    time.sleep(0.8)
    bb = js(f"return {A}.bodies[{A}.inst('I1').part].body.bbox")
    m = js(f"return {A}.inst('I1').matrix")
    cx, cy, cz = (bb[0] + bb[3]) / 2, (bb[1] + bb[4]) / 2, bb[5]
    w = [m[0] * cx + m[4] * cy + m[8] * cz + m[12], m[1] * cx + m[5] * cy + m[9] * cz + m[13], m[2] * cx + m[6] * cy + m[10] * cz + m[14]]
    click("#asmViewport canvas", off(A, w))
    r = rows("#asmViewport")
    print("the assembly hole's centre:", head("#asmViewport"), "|", r[:4])
    check("assembly: “Select the hole Ø20” offered first", r and ("Select the hole Ø20" in r[0] or "Vybrat díru Ø20" in r[0]))
    press(["Select the hole", "Vybrat díru"], "#asmViewport")
    r = rows("#asmViewport")
    picks = js(f"return ({A}.facePicks || []).map(q => [q.inst, q.face.type])")
    print("  -> ", picks, "|", r[:5])
    check("assembly: its round face chosen, its joints offered (Concentric)", picks == [["I1", "cylinder"]] and any("Concentric" in x or "Soustředn" in x for x in r))
    d.save_screenshot(f"{OUT}/select_from_point_asm.png")
finally:
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        fails.append("console errors")
    d.quit()

print("FAILED:" if fails else "ALL OK", fails if fails else "")
sys.exit(1 if fails else 0)
