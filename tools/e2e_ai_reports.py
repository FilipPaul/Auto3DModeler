"""Fixes from the AI's own reports, in headless Edge: a 3D model zoomed far out -> get_screenshot: fitted again (the
camera close to the part); fit: false keeps the view -> set_view section on, then "off": no cut -> gui_state lists the
model's steps (kind step, with their ids) and a choice with its text -> the Snap row hidden while a feature is
made -> a wall flush on the plate (add_feature says where it went, the volume change; flipped: -z): its back one face with both names; find_refs of_step / between_steps -> measure in the model (the plate 8, the wall 5) -> an extrude of
a sketch named Slot: "Extrude – Slot" ->
engraved text AB -> a drawing sheet: get_screenshot is a picture of the sheet; the check's missing sizes leave the
text out and give each its key.

  PYTHONIOENCODING=utf-8 py tools/e2e_ai_reports.py http://127.0.0.1:5199 <out dir>
"""
import base64
import json
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
M = "window.__app.modeler"
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
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text + (r.image ? ' |IMG ' + r.image.length : '')).catch(e => 'ERROR ' + e.message)", tool_name, args)


def far():
    return round(js(f"return {M}.view.camera.position.distanceTo({M}.view.controls.target)"), 1)


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=8)
    wait(f"return !!{M}.result?.body")
    fitted = far()
    js(f"const v = {M}.view; v.camera.position.sub(v.controls.target).multiplyScalar(8).add(v.controls.target); v.controls.update();")
    print("zoomed out:", fitted, "->", far())
    print("fit: false:", call("get_screenshot", fit=False)[-14:], "| distance", far())
    print("default:", call("get_screenshot")[-14:], "| distance", far(), "(fitted", fitted, ")")

    call("set_view", section={"axis": "x"})
    print("section on:", js(f"return !!{M}.section && {M}.view.renderer.localClippingEnabled"))
    call("set_view", section="off")
    print("section 'off':", js(f"return !{M}.section && !{M}.view.renderer.localClippingEnabled"))

    st = json.loads(call("gui_state"))["controls"]
    print("steps in gui_state:", [c["label"] for c in st if c["kind"] == "step"])
    print("a choice:", next((c["label"], c.get("state")) for c in st if c["kind"] == "choice"))
    print("Snap row, no tool:", js("return !!document.querySelector('#modelViewport > .snap-filters, .viewport > .snap-filters')"))
    js(f"{M}.action('shell')")
    print("Snap row, shell on:", js("return !!document.querySelector('.viewport > .snap-filters')"))
    js(f"{M}.cancelCommand()")

    # find_refs by step: a wall flush on the plate's back edge
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 35, "w": 60, "h": 5}}])
    r = json.loads(call("add_feature", type="extrude", sketch="F3", d=30))
    print("the wall's extrude: went", r.get("went"), "| volume change", r.get("volume_change_mm3"))
    r = json.loads(call("edit_feature", id="F4", fields={"flip": True}))
    print("flipped: went", r.get("went"), "| volume change", r.get("volume_change_mm3"))
    call("edit_feature", id="F4", fields={"flip": False})
    back = json.loads(call("find_refs", kind="face", normal=[0, 1, 0]))
    print("the back (flush):", [(f["name"], f.get("names")) for f in back])
    print("faces of_step F4:", sorted(f["name"] for f in json.loads(call("find_refs", kind="face", of_step="F4", limit=50))))
    print("edges of_step F4:", len(json.loads(call("find_refs", kind="edge", of_step="F4", limit=50))))
    meet = json.loads(call("find_refs", kind="edge", between_steps=["F2", "F4"], limit=50))
    print("edges between F2 and F4:", [(e["between"], e["mid"]) for e in meet])
    print("a wrong step:", call("find_refs", kind="edge", of_step="F99")[:40])
    print("measure the plate (top to bottom):", json.loads(call("measure", a={"face": "F2:end"}, b={"face": "F2:start"})).get("gap_between_faces"),
          "| the wall's thickness:", json.loads(call("measure", a={"face": "F4:side:l1"}, b={"face": "F4:side:l3"})).get("gap_between_faces"),
          "| a wrong face:", call("measure", a={"face": "F2:end"}, b={"face": "nope"})[:30])
    call("add_feature", type="sketch", plane="XY", name="Slot", shapes=[{"rect": {"x": 20, "y": 10, "w": 20, "h": 6}}])
    js(f"{M}.action('extrude')")
    time.sleep(0.5)
    print("⬆ Extrude of the sketch named Slot, in the panel:", js(f"return {M}.cmd?.feature?.name || null"))
    js(f"{M}.cmd && {M}.cancelCommand()")
    print("  the AI's:", json.loads(call("add_feature", type="extrude", op="cut", through=True))["name"])
    dec = json.loads(call("add_feature", type="decal", face="F2:end", text="AB", h=8, op="cut", depth=0.5))
    print("engraved AB:", dec["ok"], dec["id"])
    print("sheet_open:", json.loads(call("sheet_open", part="Plate"))["preset"])
    wait("return !!window.__app.sheet.svgEl")
    ck = json.loads(call("get_sheet"))["check"]
    print("the check's missing:", len(ck["missing"]), "| none of the text:", not any(f"{dec['id']}:" in m for m in ck["missing"]),
          "| each with its key:", all(m.endswith("]") and "[" in m for m in ck["missing"]), "| e.g.", ck["missing"][:1])
    r = js(f"return {H}.get_screenshot({{}}).then(r => [r.text, r.image]).catch(e => ['ERROR ' + e.message, null])")
    print("sheet screenshot:", r[0], "| png", bool(r[1]) and base64.b64decode(r[1])[:4] == b"\x89PNG")
    if r[1]:
        open(f"{OUT}/sheet_shot.png", "wb").write(base64.b64decode(r[1]))
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
