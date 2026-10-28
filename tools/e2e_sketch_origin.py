"""Sketches and holes on a face measured from its ⌜ corner or ⊕ the part's origin, in headless Edge: a block 40 × 20 × 10
-> the AI: a hole at world (30, 10) (origin "world"), a circle (10, 5) from the top's corner cut through (origin "corner"),
on the bottom face (its v runs along −Y) a hole and a rectangle in world X / Y -> the block made longer towards −x: the
world places stay, the corner's follow it; get_model gives the origin and the world places back; a wrong origin refused.

  PYTHONIOENCODING=utf-8 py tools/e2e_sketch_origin.py http://127.0.0.1:5199 <out dir>
"""
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
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    d.quit()
print("FAILED:" if fails else "ALL OK", fails or "")
sys.exit(1 if fails or errs else 0)
