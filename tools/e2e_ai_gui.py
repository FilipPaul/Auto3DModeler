"""The AI testing the GUI as the user, in headless Edge: an assembly (Base + Lid) -> gui_action at a point of the 3D
view where the lid is: the lid picked -> at an empty corner: nothing picked -> Delete on the lid: taken out -> ctrl+z:
back -> the Lid chosen in the parts list: the answer has the panel's new controls -> a value given to its "⧉ Make it
its own part" button: refused, nothing made -> clicked: a copy -> ctrl+z: the copy out of the project too -> redo: back
-> a drawing sheet of the Base: gui_state lists its dimensions, views, title cells -> gui_action on a dimension:
selected -> Delete: gone -> ctrl+z: back -> at_mm on the view, drag_to 20 mm right: the view moved -> a double-click on
the title's cell: its field has the focus -> no control / point / key: refused -> a block in ◜ Fillet at 1600 × 800
and in a narrow view: get_screenshot, an edge's pixel in it (projected with the picture's camera), gui_action at it:
that edge picked -> pick answers `at` in the picture's pixels; gui_highlight at them rings the same face -> mods:
the top face, then the front face with ctrl: both selected (a plain click: the front only); a wrong key refused.

  PYTHONIOENCODING=utf-8 py tools/e2e_ai_gui.py http://127.0.0.1:5199 <out dir>
"""
import json
import math
import sys
import time

from selenium import webdriver

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
A = "window.__app.assembly"
S = "window.__app.sheet"
H = "window.__app.agentHandlers"


def wait(script, t=120):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(script)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def act(**args):
    r = call("gui_action", **args)
    return r if r.startswith("ERROR") else json.loads(r)


try:
    d.get(URL)
    wait("return !!window.__app")
    for name, w, h in (("Base", 80, 10), ("Lid", 30, 4)):
        call("new_model", name=name)
        call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": w, "h": 50}}])
        call("add_feature", type="extrude", sketch="F1", d=h)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=6)
    call("new_assembly", name="Box")
    call("insert_part", part="Base")
    call("insert_part", part="Lid")
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    call("place_part", part="I2", z=30)
    call("set_view", view="top")
    time.sleep(0.8)
    # a point of the view where the lid is (as the user would aim at it)
    at = js(f"""const v = document.querySelector('#asmViewport').getBoundingClientRect();
      for (let y = 0.1; y < 0.9; y += 0.02) for (let x = 0.1; x < 0.9; x += 0.02)
        if ({A}.view.pickInst(v.left + x * v.width, v.top + y * v.height)?.inst === 'I2') return [x + 0.04, y + 0.04];
      return null;""")
    print("the lid on screen at", [round(v, 2) for v in at])
    r = act(at=at)
    print("click on the lid:", r["done"], "| selected", r["selected"])
    r = act(at=[0.02, 0.98])
    print("click on an empty corner:", r["done"], "| selected", r["selected"])
    act(at=at)
    r = act(key="Delete")
    print("Delete:", r["done"], "| parts", js(f"return {A}.doc.instances.length"))
    r = act(key="ctrl+z")
    print("ctrl+z:", r["done"], "| parts", js(f"return {A}.doc.instances.length"))

    # a part chosen in the list: the panel changes -> the answer has the controls' new numbers
    act(at=[0.02, 0.98])
    row = next(c for c in json.loads(call("gui_state", where="panel"))["controls"] if c["kind"] == "part" and "I2" in c["label"])
    r = act(control=row["n"])
    if any("Make it its own part" in x for x in r["suggestions"].get("all", [])):  # (a row the user reaches by ⋯ Show all)
        print("  ⧉ Make it its own part is under ⋯ Show all (of", r["suggestions"]["more"], "): opened, n", r["suggestions"]["show_all"])
        sel = r["selected"]
        r = act(control=r["suggestions"]["show_all"])
        r["selected"] = r["selected"] or sel
    own = next((c for c in r.get("controls", []) if "Make it its own part" in c["label"]), None)
    print("the Lid chosen in the list:", r["selected"], "| fresh controls:", len(r.get("controls", [])), "| its own part button: n", own and own["n"])
    assert r["selected"] == "I2" and own
    count = lambda: len(json.loads(call("list_parts")))  # noqa: E731
    n0 = count()
    r = act(control=own["n"], value=90)
    print("a value given to that button:", r[:110], "| parts", n0, "->", count())
    assert r.startswith("ERROR") and "button" in r and count() == n0
    r = act(control=own["n"])
    time.sleep(0.5)
    print("clicked:", r["done"], "| parts", n0, "->", count(), "| I2's part:", js(f"return {A}.inst('I2').part"))
    assert count() == n0 + 1
    r = act(key="ctrl+z")
    time.sleep(0.5)
    print("ctrl+z: the copy gone too — parts", count(), "| I2's part:", js(f"return {A}.inst('I2').part"), "| toasts", r["toasts"][-1:])
    assert count() == n0
    js(f"return {A}.history.go(1)")
    time.sleep(0.8)
    print("redo: the copy back — parts", count(), "| I2's part:", js(f"return {A}.inst('I2').part"), "| it is in the project:", js(f"return window.__app.project.parts.some(p => p.id === {A}.inst('I2').part)"))
    assert count() == n0 + 1
    js(f"return {A}.history.go(-1)")
    time.sleep(0.8)

    print("sheet_open:", json.loads(call("sheet_open", part="Base"))["preset"])
    wait(f"return !!{S}.svgEl")
    view = json.loads(call("gui_state", where="view"))["controls"]
    kinds = {}
    for c in view:
        kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
    print("gui_state view:", kinds, "| e.g.", [c["label"] for c in view][:4])
    dim = next(c for c in view if c["kind"] == "dim")
    r = act(control=dim["n"])
    print("a dimension clicked:", r["done"], "| selected", r["selected"])
    n0 = js(f"return {S}.allDims().length")
    r = act(key="Delete")
    print("Delete:", r["done"], "| dims", n0, "->", js(f"return {S}.allDims().length"))
    act(key="ctrl+z")
    print("ctrl+z: dims", js(f"return {S}.allDims().length"))
    top = js(f"return {S}.centre('Top')")
    r = act(at_mm=top, drag_to=[top[0] + 20, top[1]])
    print("drag the Top view 20 mm right:", r["done"], "| centre", [round(v, 1) for v in top], "->", [round(v, 1) for v in js(f"return {S}.centre('Top')")])
    cell = next(c for c in json.loads(call("gui_state", where="view"))["controls"] if c["label"] == "title title")
    r = act(control=cell["n"], double=True)
    print("double-click the title:", r["done"], "| focus on", js("return document.activeElement?.dataset?.text || document.activeElement?.tagName"))
    print("nothing given:", act()[:70])
    print("a wrong point:", act(at=[0.5])[:60])

    # at = pixels of get_screenshot's 1200 × 900 picture, in a view of another shape: a block's edge aimed at from the
    # picture (the edge's middle projected with the picture's own camera) -> ◜ Fillet picks that very edge
    call("new_model", name="Block")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=20)
    wait("return !!window.__app.modeler.result?.body && !window.__app.modeler.inflight")
    M = "window.__app.modeler"

    def to_picture(p):
        """A 3D point -> its pixel in the last picture, through the camera that drew it (view.shot)."""
        s = js(f"const s = {M}.view.shot; return {{w: s.w, h: s.h, fov: s.fov, aspect: s.aspect, zoom: s.zoom, "
               "pos: s.position.toArray(), q: s.quaternion.toArray()}")
        x, y, z, w = s["q"]
        R = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
             [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
             [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
        d = [p[k] - s["pos"][k] for k in range(3)]
        c = [sum(R[k][j] * d[k] for k in range(3)) for j in range(3)]  # (Rᵀ · d: in the camera's frame, -z ahead)
        t = math.tan(math.radians(s["fov"]) / 2) / s["zoom"]
        nx, ny = c[0] / -c[2] / (t * s["aspect"]), c[1] / -c[2] / t
        return [(nx + 1) / 2 * s["w"], (1 - ny) / 2 * s["h"]], (s["w"], s["h"])

    def fillet_edges():
        return js(f"return ({M}.cmd?.feature.edges || []).map(r => r.fp)")

    for size, edge, mid in (((1600, 800), "the front right edge", [60, 0, 10]), ((1000, 1000), "the front left edge", [0, 0, 10])):
        d.set_window_size(*size)
        time.sleep(0.8)
        cw, ch = js(f"const e = {M}.view.renderer.domElement; return [e.clientWidth, e.clientHeight]")
        if not js(f"return !!{M}.cmd"):
            act(control="◜ Fillet")
        text = call("get_screenshot", view="iso")
        px, (w, h) = to_picture(mid)
        print(f"view {cw} × {ch} (aspect {cw / ch:.2f}), picture {w} × {h}: {edge} at px", [round(v) for v in px], "|", text[:70])
        assert "1200 × 900 px" in text and "gui_action" in text
        # the old way (the same numbers as fractions of the view on screen) lands elsewhere
        old = js(f"""const v = {M}.view, r = v.renderer.domElement.getBoundingClientRect(), i = v.pickEdge(r.left + {px[0] / w} * r.width, r.top + {px[1] / h} * r.height);
          return i >= 0 ? v.body.edges[i].mid : null""")
        n0 = len(fillet_edges())
        r = act(at=[round(px[0]), round(px[1])])
        got = fillet_edges()
        print("  gui_action at:", r["done"], "| fillet edges", got, "| as fractions of the view it would hit", old)
        assert len(got) == n0 + 1 and all(abs(a - b) < 1e-3 for a, b in zip(got[-1], mid)), (got, mid)
        assert old is None or any(abs(a - b) > 1e-3 for a, b in zip(old, mid)), old
        back = js(f"const v = {M}.view, e = v.renderer.domElement; return [v.camera.aspect, e.clientWidth / e.clientHeight, v.held]")
        print("  the view's own camera back:", [round(v, 3) if isinstance(v, float) else v for v in back])
        assert abs(back[0] - back[1]) < 1e-6 and not back[2]
    # pick answers where the face is in the picture (its pixels), the click through it hits that face again
    act(key="Escape")
    time.sleep(1)
    call("get_screenshot", view="iso")
    r = act(pick="F2:end")
    print("pick F2:end -> at", r.get("at"), "|", r.get("at_is"))
    assert r["at"] and r["at"][0] > 1 and "pixels" in r["at_is"]
    act(key="Escape")
    face = js(f"""const v = {M}.view, r = v.renderer.domElement.getBoundingClientRect(), s = v.shot, own = v.cameraState();
      v.setCamera(s); const f = v.pick(r.left + {r['at'][0]} / s.w * r.width, r.top + {r['at'][1]} / s.h * r.height)?.face?.name; v.setCamera(own); return f""")
    print("  that pixel through the picture's camera:", face)
    assert face and face.startswith("F2:end")
    # gui_highlight at the same pixels: the ring sits on that face in the view as it is drawn
    call("gui_highlight", at=r["at"], text="Here.")
    time.sleep(0.3)
    ring = js("const b = document.querySelector('.teach-ring').getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2]")
    face = js(f"return {M}.view.pick(arguments[0], arguments[1])?.face?.name", *ring)
    call("gui_highlight", clear=True)
    print("gui_highlight at those pixels: the ring on", face)
    assert face and face.startswith("F2:end")
    # mods: the user's Ctrl+click — the top face, then the front face with ctrl: both selected; without: the front only
    d.set_window_size(1600, 800)  # (the narrow view's floating table covers the front face)
    time.sleep(0.8)
    front = json.loads(call("find_refs", kind="face", normal=[0, -1, 0]))[0]["name"]
    picks = lambda: js(f"return ({M}.picks || []).map(p => p.face?.name || p.kind)")  # noqa: E731
    act(pick="F2:end")
    r = act(pick=front, mods=["ctrl"])
    assert not isinstance(r, str), r
    print("Ctrl+click", front, "after F2:end:", r["done"], "| selection", picks())
    assert "with ctrl" in r["done"] and len(picks()) == 2 and front in picks()
    act(pick=front)
    print("  a plain click on it then:", picks())
    assert picks() == [front]
    print("bad mods:", act(pick=front, mods=["hyper"])[:60])
    act(key="Escape")
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
