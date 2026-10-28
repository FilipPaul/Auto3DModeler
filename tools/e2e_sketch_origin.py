"""Sketches and holes on a face measured from its ⌜ corner or ⊕ the part's origin, in headless Edge: a block 40 × 20 × 10
-> the AI: a hole at world (30, 10) (origin "world"), a circle (10, 5) from the top's corner cut through (origin "corner"),
on the bottom face (its v runs along −Y) a hole and a rectangle in world X / Y -> the block made longer towards −x: the
world places stay, the corner's follow it; get_model gives the origin and the world places back; a wrong origin refused.
Then with real clicks: a sketch on a new block's top, a circle drawn -> the sketch bar's ⌜ Corner: its 0, 0 at the
corner, the circle keeps its place (its coordinates shift), Ctrl+Z / Ctrl+Y -> a circle (10, 10) from the corner, cut
through -> ◎ Hole on the top, From ⊕ Origin (the part's): the hole's numbers are world X / Y -> the block made longer towards −x:
the corner's hole follows, the part origin's stays.

  PYTHONIOENCODING=utf-8 py tools/e2e_sketch_origin.py http://127.0.0.1:5199 <out dir>
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


def face_named(n):
    return js(f"return {M}.result.body.faces.find(f => f.type === 'plane' && Math.abs(f.frame.n[0] - arguments[0][0]) + Math.abs(f.frame.n[1] - arguments[0][1]) + Math.abs(f.frame.n[2] - arguments[0][2]) < 1e-6)?.name", n)


def holes(prefix):
    """The x, y of the round faces of the steps whose id starts so (a hole's wall: its axis)."""
    b = js(f"return {M}.result.body")
    return sorted([round(c, 3) for c in f["centroid"][:2]] for f in b["faces"] if f["type"] == "cylinder" and f["name"].startswith(prefix))


def centroid(name):
    return js(f"return {M}.result.body.faces.find(f => f.name === arguments[0])?.centroid", name)


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


def circles():
    return js(f"""const s = {SK}; return s.f.entities.filter((e) => e.t === 'circle')
      .map((e) => [+s.P(e.c)[0].toFixed(3), +s.P(e.c)[1].toFixed(3), +e.r.toFixed(3)])""")


def key(ch):
    ActionChains(d).key_down(Keys.CONTROL).send_keys(ch).key_up(Keys.CONTROL).perform()
    time.sleep(0.6)


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Origins")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    settle()
    top, bottom = face_named([0, 0, 1]), face_named([0, 0, -1])

    # 1. the AI: a hole at world (30, 10); a circle (10, 5) from the top's corner, cut through
    r = json.loads(call("add_feature", type="hole", face=top, origin="world", points=[[30, 10]], d=4))
    hw = r["id"]
    check("hole origin world: ok", r.get("ok") is True, r)
    check("… at world (30, 10)", holes(hw) == [[30, 10]], holes(hw))
    r = json.loads(call("add_feature", type="sketch", plane={"face": top, "origin": "corner"}, shapes=[{"circle": {"x": 10, "y": 5, "d": 6}}]))
    sc = r["id"]
    check("sketch origin corner: ok", r.get("ok") is True, r)
    check("its plane stores origin corner", js(f"return {M}.part.features.find(f => f.id === arguments[0]).plane.origin", sc) == "corner")
    check("its frame's 0, 0 is the corner (0, 0, 10)", js(f"return {M}.frames[arguments[0]].o", sc) == [0, 0, 10], js(f"return {M}.frames[arguments[0]].o", sc))
    r = json.loads(call("add_feature", type="extrude", sketch=sc, op="cut", through=True))
    cc = r["id"]
    check("… cut: the hole at (10, 5)", holes(cc) == [[10, 5]], holes(cc))
    # on the bottom face (its v runs along −Y): world X / Y still
    r = json.loads(call("add_feature", type="hole", face=bottom, origin="world", points=[[20, 15]], d=3, through=False, depth=3))
    hb = r["id"]
    check("a hole on the bottom at world (20, 15)", holes(hb) == [[20, 15]], holes(hb))
    r = json.loads(call("add_feature", type="sketch", plane={"face": bottom, "origin": "world"}, shapes=[{"rect": {"x": 30, "y": 12, "w": 6, "h": 4}}]))
    sb = r["id"]
    r = json.loads(call("add_feature", type="extrude", sketch=sb, op="cut", d=2))
    check("a pocket on the bottom from world X / Y: 6 × 4 × 2", r.get("ok") is True and abs(r.get("volume_change_mm3", 0) + 48) < 1e-3, r.get("volume_change_mm3"))
    c = centroid(f"{r['id']}:end")
    check("… its floor centred at (33, 14, 2)", c and [round(v, 3) for v in c] == [33, 14, 2], c)
    gm = json.loads(call("get_model"))
    step = next(s for s in gm["steps"] if s["id"] == hb)
    check("get_model: the hole's origin and its world places", step.get("origin") == "world" and step.get("points") == [[20, 15]], step)
    err = call("add_feature", type="hole", face=top, origin="middle", points=[[0, 0]])
    check("a wrong origin refused", err.startswith("ERROR") and "origin" in err, err)
    d.save_screenshot(f"{OUT}/origin1_ai.png")

    # 2. the block made longer towards −x: the world places stay, the corner's follow it
    call("edit_feature", id="F1", fields={"shapes": [{"rect": {"x": -20, "y": 0, "w": 60, "h": 20}}]})
    settle()
    check("longer: all steps ok", all(js(f"return {M}.status(arguments[0]).ok", i) for i in (hw, sc, cc, hb, sb)))
    check("the world hole stays at (30, 10)", holes(hw) == [[30, 10]], holes(hw))
    check("the bottom hole stays at (20, 15)", holes(hb) == [[20, 15]], holes(hb))
    check("the corner's circle follows the corner to (−10, 5)", holes(cc) == [[-10, 5]], holes(cc))

    # 3. the user: a sketch on a new block's top -> ⌜ Corner
    call("new_model", name="Origins by hand")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    settle()
    js(f"{M}.view.setView('iso')")
    time.sleep(0.5)
    btn(".m-cmdbar [data-a=sketch]")
    click(off_xyz([12, 12, 10]))
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.6)
    seg = js("return [...document.querySelectorAll('.m-cmdbar .m-origin button')].map(b => b.textContent + (b.classList.contains('on') ? ' *' : ''))")
    check("the sketch bar: Origin ◎ Face centre (on) | ⌜ Corner | ⊕ Part origin", seg == ["◎ Face centre *", "⌜ Corner", "⊕ Part origin"], seg)
    o0 = js(f"return {M}.frame().o")
    check("its 0, 0 at the face's centre (20, 10, 10)", o0 == [20, 10, 10], o0)
    btn(".m-cmdbar [data-a=circle]")
    click(off_uv([-10, -5]))
    click(off_uv([-8, -5]))
    c0 = circles()
    print("a circle drawn at", c0)
    btn(".m-cmdbar [data-origin=corner]")
    fr = js(f"return {M}.frame()")
    check("⌜ Corner: the sketch's 0, 0 at the corner (0, 0, 10)", fr["o"] == [0, 0, 10], fr["o"])
    c1 = circles()
    check("… the circle keeps its place: its coordinates + (20, 10)", len(c1) == 1 and abs(c1[0][0] - c0[0][0] - 20) < 1e-6 and abs(c1[0][1] - c0[0][1] - 10) < 1e-6, c1)
    check("… ⌜ Corner lit", js("return document.querySelector('.m-cmdbar [data-origin=corner]').classList.contains('on')"))
    d.save_screenshot(f"{OUT}/origin2_corner.png")
    key("z")
    check("Ctrl+Z: back to the face's centre", js(f"return {M}.frame().o") == [20, 10, 10] and circles() == c0 and js("return document.querySelector('.m-cmdbar [data-origin=centre]').classList.contains('on')"), (js(f"return {M}.frame().o"), circles()))
    key("y")
    check("Ctrl+Y: the corner again", js(f"return {M}.frame().o") == [0, 0, 10] and circles() == c1, (js(f"return {M}.frame().o"), circles()))
    btn(".m-cmdbar [data-a=select]")
    js(f"{SK}.f.entities = []; {SK}.f.points = {{}}; {SK}.f.dims = []; {SK}.f.constraints = []; {SK}.changed()")  # (start over: one circle)
    btn(".m-cmdbar [data-a=circle]")
    click(off_uv([10, 10]))
    click(off_uv([12, 10]))
    c2 = circles()
    check("a circle about (10, 10) from the corner", len(c2) == 1 and abs(c2[0][0] - 10) < 0.6 and abs(c2[0][1] - 10) < 0.6, c2)
    btn("#modelViewport .view-actions [data-a=finish]")
    settle()
    js("document.querySelector('#modelRight [data-k=through]')?.click()")
    settle()
    btn("#modelViewport .view-actions [data-a=ok]")
    settle()
    cut = js(f"return {M}.part.features.at(-1).id")
    hc = holes(cut)
    check("cut: the hole at the corner + the circle's place", hc == [[round(c2[0][0], 3), round(c2[0][1], 3)]], (hc, c2))
    check("the sketch stores origin corner", js(f"return {M}.part.features.find(f => f.type === 'sketch' && f.id !== 'F1').plane.origin") == "corner")

    # 4. ◎ Hole on the top, From ⊕ Origin (the part's)
    btn(".m-cmdbar [data-a=hole]")
    click(off_xyz([30, 15, 10]))
    settle()
    seg = js("return [...document.querySelectorAll('#modelRight .m-origin button')].map(b => b.textContent + (b.classList.contains('on') ? ' *' : ''))")
    check("the hole panel: From ⇤ Edges (on) | ⌜ Corner | ⊕ Origin", seg == ["⇤ Edges *", "⌜ Corner", "⊕ Origin"], seg)
    hf = js(f"return {M}.cmd.feature.id")
    h0 = holes(hf)
    btn("#modelRight [data-origin=world]")
    settle()
    pts = js(f"return {M}.cmd.feature.points")
    check("⊕ Origin: the hole's numbers are its world X / Y", len(h0) == 1 and abs(pts[0][0] - h0[0][0]) < 1e-3 and abs(pts[0][1] - h0[0][1]) < 1e-3, (pts, h0))
    check("… it stays where it was", holes(hf) == h0, holes(hf))
    rows = js("return [...document.querySelectorAll('#modelRight .mp-hd .hint')].map(e => e.textContent)")
    check("… its rows say from the part's origin", rows == ["from the part's origin"] * 2, rows)
    d.save_screenshot(f"{OUT}/origin3_hole.png")
    btn("#modelViewport .view-actions [data-a=ok]")
    settle()

    # 5. the block made longer towards −x: the corner's hole follows, the part origin's stays
    call("edit_feature", id="F1", fields={"shapes": [{"rect": {"x": -20, "y": 0, "w": 60, "h": 20}}]})
    settle()
    check("longer: the corner's hole moved 20 to −x", holes(cut) == [[round(hc[0][0] - 20, 3), hc[0][1]]], holes(cut))
    check("… the part origin's hole stays", holes(hf) == h0, holes(hf))
    js(f"{M}.view.setView('iso')")
    time.sleep(0.4)
    d.save_screenshot(f"{OUT}/origin4_longer.png")
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    d.quit()
print("FAILED:" if fails else "ALL OK", fails or "")
sys.exit(1 if fails or errs else 0)
