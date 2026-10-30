"""A snap point shown under the mouse is what a click takes (WYSIWYG), with REAL mouse input, Quadrants switched on:
1. Assembly: a 60 × 40 × 10 block with a Ø16 boss on it, placed. The mouse on the boss' top rim at a quadrant: the
   "quadrant" mark shows -> a click 2–3 px beside it picks that point (the table: "… · A quadrant Ø16", 📏 Measure from
   here, ⧉ Copy its coordinates), not the round face; the same for its centre and for a top corner of the block; a click
   on the block's top away from the points picks that face.
2. An imported STEP part (samples/…/nist_ctc_01, holes in it) placed: a hole's rim quadrant clicked -> that point.
3. The 3D model workspace: the same part — a quadrant, the centre, a corner clicked -> that point; the face away -> the face.
4. Hidden (👁) parts: their points are neither shown nor taken. No console errors.

  PYTHONIOENCODING=utf-8 py tools/e2e_snap_click.py http://127.0.0.1:5199 <out dir>
"""
import os
import sys
import time
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
ACV, MCV = "#asmViewport canvas", "#modelViewport canvas"
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


def at(view, p):
    """A 3D point (world) -> its offset from the canvas' middle (pixels)."""
    return js(f"""const v = {view}.view, V = v.camera.position.constructor, [sx, sy] = v.toScreen(new V(...arguments[0])), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(p))


def on_canvas(view, p, nudge=(2, -2)):
    """The spot on the canvas itself (not under a panel over it)."""
    o = at(view, p)
    return js(f"""const r = {view}.view.renderer.domElement.getBoundingClientRect(), x = Math.floor(r.left + r.width / 2) + arguments[0], y = Math.floor(r.top + r.height / 2) + arguments[1];
      return document.elementFromPoint(x, y) === {view}.view.renderer.domElement""", o[0] + nudge[0], o[1] + nudge[1])


def back_off(view, k=1.7):
    """The camera k times farther from what it looks at: the part away from the panels over the view's sides."""
    js(f"const v = {view}.view; v.camera.position.sub(v.controls.target).multiplyScalar(arguments[0]).add(v.controls.target); v.controls.update(); v.invalidate()", k)
    time.sleep(0.5)


def hover(view, sel, p, nudge=(2, -2)):
    o = at(view, p)
    if not on_canvas(view, p, nudge):
        raise RuntimeError(f"the spot {o} is under a panel, not on the canvas")
    ActionChains(d, duration=30).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, sel), o[0] + nudge[0], o[1] + nudge[1]).perform()
    time.sleep(0.5)
    return js("return [...document.querySelectorAll('.m-snap')].filter(e => e.offsetParent).map(e => e.textContent)")


def click(view, sel, p, nudge=(2, -2)):
    shown = hover(view, sel, p, nudge)
    ActionChains(d).click().perform()
    time.sleep(0.8)
    return shown


def head(vp):
    return js(f"return document.querySelector('{vp} .view-suggest .vs-head b')?.textContent || ''")


def rows(vp):
    return [" ".join(b.text.split()) for b in d.find_elements(By.CSS_SELECTOR, f"{vp} .view-suggest .vs-list button[data-sg]")]


def world(inst, p):
    m = js(f"return {A}.inst(arguments[0]).matrix", inst)
    return [m[0] * p[0] + m[4] * p[1] + m[8] * p[2] + m[12], m[1] * p[0] + m[5] * p[1] + m[9] * p[2] + m[13], m[2] * p[0] + m[6] * p[1] + m[10] * p[2] + m[14]]


def seen(view, p):
    return js(f"const v = {view}.view; return v.sees ? v.sees(new (v.camera.position.constructor)(...arguments[0])) : true", list(p))


def asm_pick():
    return js(f"const s = {A}.snapPick; return {{ snap: s?.snap || null, faces: ({A}.facePicks || []).map(q => q.face.type) }}")


def mdl_pick():
    return js(f"return ({M}.picks || []).map(q => q.kind === 'point' ? 'point:' + q.snap : q.kind)")


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.setItem('a3d.snap3d', JSON.stringify({ corner: true, midpoint: true, centre: true, quadrant: true, guides: true })); localStorage.removeItem('a3d.hover3d')")

    # ---- the part: a block with a round boss
    call("new_model", name="Boss block")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    wait(f"return {M}.result?.body && !{M}.inflight")
    x0, y0, z0, x1, y1, z1 = js(f"return {M}.result.body.bbox")  # (the block's)
    bx, by = x0 + 14, (y0 + y1) / 2
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": bx, "y": by, "d": 16}}])
    call("add_feature", type="extrude", sketch="F3", d=25)
    wait(f"return {M}.result?.body && !{M}.inflight && {M}.result.body.bbox[5] > 20")
    print("the block:", [x0, y0, z0, x1, y1, z1], "the boss' top centre:", js(f"return {M}.result.body.edges.filter(e => e.pts.length > 12 && Math.abs(e.pts[2] - 25) < 1e-6).map(e => e.pts.length)"))
    QUAD = (bx + 8, by, 25)  # (Quadrants: along x and y — the boss' axis is z)
    CEN = (bx, by, 25)
    CORNERS = [(x, y, 10) for x in (x0, x1) for y in (y0, y1)]
    FACE = (x1 - 15, (y0 + y1) / 2, 10)  # (the block's top, away from every point)

    # ---- 1. the assembly
    call("new_assembly", name="Snaps")
    call("insert_part", part="Boss block")
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    js(f"{A}.view.setView('iso')")
    time.sleep(0.8)
    back_off(A)
    W = lambda p: world("I1", p)  # noqa: E731
    corner = next(c for c in CORNERS if seen(A, W(c)) and on_canvas(A, W(c)))
    for name, p, want in [("quadrant", QUAD, "quadrant"), ("centre", CEN, "centre"), ("corner", corner, "corner")]:
        shown = click(A, ACV, W(p))
        pk, hd, r = asm_pick(), head("#asmViewport"), rows("#asmViewport")
        print(f"assembly {name}: shown {shown} -> {pk} | {hd} | {r[:4]}")
        check(f"assembly {name}: its mark shown under the mouse", any(want in s.lower() or {"quadrant": "kvadrant", "centre": "střed", "corner": "roh"}[want] in s.lower() for s in shown))
        check(f"assembly {name}: the click picks that point, not a face", pk["snap"] == want and not pk["faces"])
        check(f"assembly {name}: the table names it, with what fits a point", (want != "quadrant" or "Ø16" in hd) and any("Measure from here" in x or "Měřit odsud" in x for x in r) and any("Copy its coordinates" in x or "Kopírovat" in x for x in r))
    hover(A, ACV, QUAD and W(QUAD), (0, 0))
    dots = js(f"return {A}.view.hoverSnapGroup?.children[0]?.geometry.getAttribute('position').count || 0")
    check(f"assembly: the hovered round face's points shown as dots ({dots})", dots >= 5)
    click(A, ACV, W(FACE), (0, 0))
    pk = asm_pick()
    print("assembly face:", pk)
    check("assembly: a click away from the points picks the face", pk["snap"] is None and pk["faces"] == ["plane"])
    d.save_screenshot(os.path.join(OUT, "snap_click_asm.png"))

    # hidden: a hidden part's points are not taken (its face neither)
    js(f"{A}.choose(null)")
    call("insert_part", part="Boss block")
    wait(f"return Object.values({A}.bodies).every(b => b.body) && {A}.inst('I2')")
    js(f"const a = {A}, it = a.inst('I2'); it.matrix = [...it.matrix]; it.matrix[13] += 80; a.draw()")  # (beside the first one)
    js(f"{A}.view.setView('iso')")  # (both in sight)
    time.sleep(0.8)
    back_off(A)
    print(call("set_visibility", hide=["I2"]))
    time.sleep(0.6)
    shown = hover(A, ACV, world("I2", CEN))
    sp = js(f"const r = {A}.view.measurePoint(...arguments[0], 5); return r && r.inst", [x + y for x, y in zip(js("const r = window.__app.assembly.view.renderer.domElement.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]"), at(A, world("I2", CEN)))])
    print("hidden part's centre:", shown, sp)
    check("assembly: a hidden part's point is not taken", sp != "I2")
    call("remove_from_assembly", part="I2")
    time.sleep(0.5)

    # ---- 2. an imported STEP part with holes
    if STEP.exists():
        js("let i = document.getElementById('e2eFile'); if (!i) { i = document.createElement('input'); i.type = 'file'; i.id = 'e2eFile'; i.hidden = true; document.body.appendChild(i); } i.value = '';")
        d.find_element(By.ID, "e2eFile").send_keys(str(STEP))
        r = d.execute_async_script("""const done = arguments[arguments.length - 1], f = document.getElementById('e2eFile').files[0], fd = new FormData();
          fd.append('file', f);
          fetch('/api/model/import', { method: 'POST', body: fd }).then(r => r.json()).then(done, (e) => done({ error: String(e) }));""")
        print("STEP import:", {k: r.get(k) for k in ("name", "faces", "error")})
        js("""const r = arguments[0]; return window.__app.project.newModel({ features: [{ id: 'F1', type: 'solid', name: 'Housing', blob: r.blob, file: r.name, op: 'add' }] }, 'Housing (STEP)')""", r)
        wait(f"return {M}.result?.body && !{M}.inflight", 180)
        call("open_part", id="Snaps")
        wait(f"return {A}.active", 30)
        print(call("insert_part", part="Housing (STEP)"))
        wait(f"return Object.values({A}.bodies).every(b => b.body)", 180)
        inst = js(f"return {A}.doc.instances.at(-1).id")
        js(f"{A}.view.setView('iso')")
        time.sleep(1)
        js(f"{A}.choose(null)")
        # a round edge of a hole, big enough on the screen, its quadrant in sight and nearest the mouse
        cand = d.execute_async_script(f"""const done = arguments[arguments.length - 1];
          import('./js/modeler/view.js').then(({{ snapPoints, ringPx }}) => {{
            const a = {A}, v = a.view, mesh = v.meshes.find(m => m.userData.inst === arguments[0]), b = mesh.userData.body, r = v.renderer.domElement.getBoundingClientRect();
            for (const e of b.edges) {{
              if (!e.faces.some(i => b.faces[i]?.type === 'cylinder')) continue;
              for (const q of snapPoints([e], mesh.matrix, {{ quadrant: true }})) {{
                if (ringPx(q, v.camera, r) < 14 || !v.sees(q.point)) continue;
                const [sx, sy] = v.toScreen(q.point), sp = v.measurePoint(sx + 2, sy - 2, 5);
                if (sp?.snap === 'quadrant' && sp.point.distanceTo(q.point) < 1e-6) {{ done({{ p: q.point.toArray(), d: 2 * q.r }}); return; }}
              }}
            }}
            done(null);
          }}, (e) => done({{ error: String(e) }}));""", inst)
        print("STEP hole quadrant:", cand)
        check("STEP part: a hole's quadrant found in sight", bool(cand and cand.get("p")))
        if cand and cand.get("p"):
            shown = click(A, ACV, cand["p"])
            pk, hd = asm_pick(), head("#asmViewport")
            print("  ->", shown, pk, hd)
            check("STEP part: the quadrant shown is what the click picks", pk["snap"] == "quadrant" and not pk["faces"] and "Ø" in hd)
            d.save_screenshot(os.path.join(OUT, "snap_click_step.png"))
    else:
        print("(no STEP sample: skipped)")

    # ---- 3. the 3D model workspace
    call("open_part", id="Boss block")
    time.sleep(1)
    wait(f"return {M}.result?.body && !{M}.inflight && {M}.result.body.bbox[5] > 20 && {M}.result.body.bbox[5] < 30", 60)
    js(f"{M}.view.setView('iso')")
    time.sleep(0.8)
    back_off(M)
    mcorner = next(c for c in CORNERS if js(f"const v = {M}.view, V = v.camera.position.constructor, p = new V(...arguments[0]), h = v.pick(...v.toScreen(p)); return !h || h.point.distanceTo(p) < 0.5", list(c)) and on_canvas(M, c))
    for name, p, want in [("quadrant", QUAD, "quadrant"), ("centre", CEN, "centre"), ("corner", mcorner, "corner")]:
        shown = click(M, MCV, p)
        pk, hd = mdl_pick(), head("#modelViewport")
        print(f"model {name}: shown {shown} -> {pk} | {hd}")
        check(f"model {name}: its mark shown", len(shown) > 0)
        check(f"model {name}: the click picks that point", pk == [f"point:{want}"])
    click(M, MCV, FACE, (0, 0))
    pk = mdl_pick()
    print("model face:", pk)
    check("model: a click away from the points picks the face", pk == ["face"])
    d.save_screenshot(os.path.join(OUT, "snap_click_model.png"))
finally:
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        fails.append("console errors")
    d.quit()

print("FAILED:" if fails else "ALL OK", fails if fails else "")
sys.exit(1 if fails else 0)
