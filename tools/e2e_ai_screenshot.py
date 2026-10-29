"""The AI's get_screenshot in a narrow window (the chat beside the view made it a 339 × 900 strip), in headless Edge:
the report's bracket (a wall from {datum XZ, offset 20} flipped: its front flush with the plate's: one face, both
names) -> the picture is 1200 × 900 and the whole part is in it (nothing at its borders); a hover, picks and the
chosen step's tint left on screen are not in it (the same picture as without); highlight ["F4"] lights the step's
faces in orange, a wrong name is refused; an extrude inside the part warns that it adds nothing -> an assembly of
three parts in a row, exploded -> 1200 × 900, all of it in the picture; highlight refused there.

  PYTHONIOENCODING=utf-8 py tools/e2e_ai_screenshot.py http://127.0.0.1:5199 <out dir>
"""
import base64
import io
import json
import sys
import time

from PIL import Image
from selenium import webdriver

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=760,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"
A = "window.__app.assembly"
H = "window.__app.agentHandlers"
fails = []


def check(what, ok, *more):
    print("OK  " if ok else "FAIL", what, *more)
    if not ok:
        fails.append(what)


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


def shot(name, **args):
    """get_screenshot -> (its text, the picture as RGB), saved as <name>.png."""
    r = js(f"return {H}.get_screenshot(arguments[0]).then(r => [r.text, r.image]).catch(e => ['ERROR ' + e.message, null])", args)
    if not r[1]:
        return r[0], None
    raw = base64.b64decode(r[1])
    open(f"{OUT}/{name}.png", "wb").write(raw)
    return r[0], Image.open(io.BytesIO(raw)).convert("RGB")


def drawn_box(img):
    """The box round the pixels that are not the background (#161b22) -> (x0, y0, x1, y1)."""
    bg = Image.new("RGB", img.size, (0x16, 0x1b, 0x22))
    from PIL import ImageChops
    diff = ImageChops.difference(img, bg).convert("L").point(lambda v: 255 if v > 24 else 0)
    return diff.getbbox()


def inside(img, box, margin=4):
    return box and box[0] > margin and box[1] > margin and box[2] < img.width - margin and box[3] < img.height - margin


def orange(img):
    return sum(1 for r, g, b in img.getdata() if r > 170 and 60 < g < 150 and b < 110 and r - b > 100)


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Bracket")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": -30, "y": -20, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("add_feature", type="sketch", plane={"datum": "XZ", "offset": 20}, shapes=[{"rect": {"x": -30, "y": 0, "w": 60, "h": 45}}])
    call("add_feature", type="extrude", sketch="F3", d=5, flip=True)
    wait(f"return !!{M}.result?.body && !{M}.inflight")
    front = json.loads(call("find_refs", kind="face", normal=[0, -1, 0]))
    check("the report's bracket: its front one face with both names", len(front) == 1 and {"F2", "F4"} <= {n.split(":")[0] for n in front[0].get("names", [])},
          [(f["name"], f.get("names")) for f in front])
    cw, ch = js(f"const e = {M}.view.renderer.domElement; return [e.clientWidth, e.clientHeight]")
    check("the view on screen is narrow", cw < ch, f"{cw} × {ch}")

    text, img = shot("model_iso", view="iso")
    check("model: 1200 × 900", img and img.size == (1200, 900), img and img.size, text[:60])
    box = drawn_box(img)
    check("model: all of the part in the picture", inside(img, box), box)
    check("model: the view on screen is put back", js(f"const e = {M}.view.renderer.domElement; return [e.clientWidth, e.clientHeight]") == [cw, ch])

    # leftovers on screen: a step chosen (gold), a face under the mouse, a pick
    js(f"const v = {M}.view; v.setSelectedFaces(v.body.faces.filter(f => f.name.startsWith('F4:')).map(f => f.id)); v.setHover(0); v.picked.add(1); v.paint();")
    _, img2 = shot("model_tinted")
    check("model: hover / picks / chosen step not in the picture", img2 and list(img2.getdata()) == list(img.getdata()))
    check("model: the tints stay on screen", js(f"return {M}.view.hover === 0 && {M}.view.picked.has(1) && !!{M}.view.selSet"))
    js(f"const v = {M}.view; v.setSelectedFaces(null); v.setHover(-1); v.picked.clear(); v.paint();")

    text, img3 = shot("model_highlight", highlight=["F4"])
    check("highlight F4: orange faces", img3 and orange(img3) > 2000, orange(img3) if img3 else None, "| plain:", orange(img))
    check("highlight F4: named in the text", "Lit in orange: F4:" in text, text[:100])
    text, _ = shot("model_badhl", highlight=["F9:end"])
    check("highlight a wrong name: refused", text.startswith("ERROR") and "F9:end" in text, text[:90])

    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": -10, "y": -10, "w": 20, "h": 10}}])
    r = json.loads(call("add_feature", type="extrude", sketch="F5", d=3))
    check("an extrude inside the part: warns it adds nothing", any("adds nothing" in w for w in r["warnings"]), r["warnings"], r.get("volume_change_mm3"))
    r = json.loads(call("edit_feature", id="F6", fields={"flip": True}))
    check("flipped: it adds, no warning", r["volume_change_mm3"] > 0 and not any("adds nothing" in w for w in r["warnings"]), r["volume_change_mm3"])

    # an assembly 240 mm long: three parts in a row, exploded
    call("new_model", name="Bar")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 80, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    time.sleep(1)
    call("new_assembly", name="Row")
    for x in (0, 80, 160):
        r = json.loads(call("insert_part", part="Bar"))
        call("place_part", part=r["parts"][-1]["id"], x=x)
    call("set_view", view="iso", explode=0.6)
    time.sleep(1)
    text, img4 = shot("asm_exploded")
    check("assembly: 1200 × 900", img4 and img4.size == (1200, 900), img4 and img4.size, text[:60])
    box = drawn_box(img4)
    check("assembly: all of it in the picture (exploded)", inside(img4, box), box)
    js(f"{A}.sel = {A}.doc.instances[0].id; {A}.draw();")
    _, img5 = shot("asm_chosen")
    check("assembly: a chosen part's glow not in the picture", img5 and list(img5.getdata()) == list(img4.getdata()))
    check("assembly: highlight refused", call("get_screenshot", highlight=["F2:end"]).startswith("ERROR highlight"))
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    d.quit()
print("FAILED:", fails if fails else "none")
sys.exit(1 if fails else 0)
