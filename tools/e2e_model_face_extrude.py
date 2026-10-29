"""⬆ Extrude this face, in headless Edge: a 40 × 20 × 10 block with a Ø6 hole -> a click on its top suggests
"⬆ Extrude this face" in the top rows (after ✏ Sketch on this face) -> clicked: the Extrude panel, 10 mm out of the part
(the hole goes on up), its outline sketch not a step yet -> the pull arrow's tip dragged up: the distance grows -> 4
typed, ⇅: a cut 4 into the part, ⇅ again: out -> Cancel: no step left behind -> again, OK: two ordinary steps (a
sketch of the face's outline + the extrude) -> the block made 15 tall: the face's extrude follows it -> the sketch
opened: the outline drawn -> in Czech: "Vysunout tuto plochu". Ends ALL OK / FAILED.

  PYTHONIOENCODING=utf-8 py tools/e2e_model_face_extrude.py http://127.0.0.1:5199 <out dir>
"""
import json
import math
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1500,900")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
H = "window.__app.agentHandlers"
M = "window.__app.modeler"
fails = []
FACE = 800 - 9 * math.pi  # (the top: 40 × 20 less the Ø6 hole)


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


def check(ok, what):
    print("OK  " if ok else "FAIL", what)
    if not ok:
        fails.append(what)


def settled_volume():
    time.sleep(0.4)
    wait(f"return !{M}.inflight && !{M}.building && {M}.result?.body")
    time.sleep(0.6)
    return js(f"return {M}.result.body.volume")


def lang(cs):  # (the 🌐 button: switched live)
    if (js("return document.documentElement.lang") == "cs") != cs:
        d.find_element(By.ID, "langBtn").click()
        time.sleep(0.5)


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#modelViewport canvas")


def off(p):
    """A 3D point -> the mouse offset from the canvas' centre."""
    return js(f"""const v = {M}.view, p = new (v.camera.position.constructor)(...arguments[0]);
      const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(p))


def click_top():
    js(f"{M}.view.setView('iso')")
    time.sleep(0.6)
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *off((8, 5, top_z()))).perform()
    time.sleep(0.2)
    ActionChains(d).click().perform()
    time.sleep(0.6)
    return [b.text.replace("\n", " ") for b in d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-list button")]


def top_z():
    return js(f"return {M}.result.body.bbox[5]")


def press(label):
    next(b for b in d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-list button") if label in b.text).click()
    wait(f"return {M}.cmd?.feature?.type === 'extrude'")


def ok_cancel(a):
    d.find_element(By.CSS_SELECTOR, f"#modelViewport .view-actions [data-a={a}]").click()
    wait(f"return !{M}.cmd && !{M}.inflight")


def type_d(v):
    inp = d.find_element(By.CSS_SELECTOR, "#modelRight .mp-body input[data-k=d]")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys(str(v))


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('auto3d-lang')")
    d.refresh()
    wait("return !!window.__app")
    call("new_model", name="Face up")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=6)
    v0 = settled_volume()
    check(abs(v0 - FACE * 10) < 0.01, f"the block with its hole: {v0:.3f}")

    # ---- the suggestion, near the top
    rows = click_top()
    check(len(rows) > 2 and "Sketch on this face" in rows[0] and "Extrude this face" in rows[1], f"a click on the top: {rows[:4]}")
    press("Extrude this face")
    f = js(f"return {M}.cmd.feature")
    check(f["op"] == "add" and f["d"] == 10 and not f["flip"] and js(f"return {M}.cmd.pre?.length") == 1, f"the Extrude panel: {f['op']} {f['d']} mm, its sketch waiting")
    check(len(js(f"return {M}.part.features")) == 3, "the outline sketch is not a step yet")
    v = settled_volume()
    check(abs(v - FACE * 20) < 0.01, f"the preview: 10 out, the hole goes on up — {v:.3f} = {FACE * 20:.3f}")
    check(not d.find_elements(By.CSS_SELECTOR, "#modelRight [data-k=sketch]"), "no Sketch choice (it is this face's)")
    # the pull arrow: its tip dragged up 60 px — longer
    tip = js(f"const p = {M}.view.pull; return p && p.o.clone().addScaledVector(p.n, p.len + p.head * 0.5).toArray()")
    check(bool(tip) and abs(tip[2] - 10 - 10 - js(f"return {M}.view.pull.head") * 0.5) < 1e-6, f"the pull arrow from the face up, its tip at z {tip and round(tip[2], 2)}")
    x, y = off(tip)
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), x, y).perform()
    time.sleep(0.2)
    ActionChains(d, duration=200).click_and_hold().move_by_offset(0, -30).move_by_offset(0, -30).release().perform()
    d2 = js(f"return {M}.cmd.feature.d")
    val = js("return document.querySelector('#modelRight .mp-body input[data-k=d]').value")
    v = settled_volume()
    check(d2 > 10 and float(val) == d2 and abs(v - FACE * (10 + d2)) < 0.01, f"dragged: {d2} mm (the field {val}), {v:.3f}")
    check(js(f"return {M}.view.controls.enabled") is True, "the view turns again after the drag")
    type_d(4)
    v = settled_volume()
    check(abs(v - FACE * 14) < 0.01, f"4 typed: {v:.3f}")
    d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=flip]").click()
    v = settled_volume()
    f = js(f"return {M}.cmd.feature")
    check(f["op"] == "cut" and not f["flip"] and abs(v - FACE * 6) < 0.01, f"⇅: a cut 4 into the part — {v:.3f} = {FACE * 6:.3f}")
    d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=flip]").click()
    v = settled_volume()
    check(js(f"return {M}.cmd.feature.op") == "add" and abs(v - FACE * 14) < 0.01, "⇅ again: out of it")
    d.save_screenshot(f"{OUT}/face_extrude_preview.png")
    ok_cancel("cancel")
    v = settled_volume()
    check(len(js(f"return {M}.part.features")) == 3 and abs(v - v0) < 0.01, "Cancel: no step left, the block as it was")

    # ---- again, OK: two ordinary steps
    click_top()
    press("Extrude this face")
    settled_volume()
    ok_cancel("ok")
    v = settled_volume()
    fs = js(f"return {M}.part.features")
    sk, ex = fs[-2], fs[-1]
    check(len(fs) == 5 and sk["type"] == "sketch" and sk["entities"][0]["t"] == "outline" and sk["entities"][0]["face"]["name"] == "F2:end"
          and ex["type"] == "extrude" and ex["sketch"] == sk["id"], f"OK: {sk['name']} (the outline of F2:end) + {ex['name']}")
    check(abs(v - FACE * 20) < 0.01, f"the part: {v:.3f}")
    # the block made 15 tall: the face (and its extrude) follow
    call("edit_feature", id="F2", fields={"d": 15})
    v = settled_volume()
    check(abs(v - FACE * 25) < 0.01, f"the block 15 tall: the face's extrude follows — {v:.3f} = {FACE * 25:.3f}")
    # undo: both steps go at once
    js(f"{M}.history.go(-1)")
    v = settled_volume()
    js(f"{M}.history.go(-1)")
    v = settled_volume()
    check(len(js(f"return {M}.part.features")) == 3 and abs(v - v0) < 0.01, "undo: the sketch and the extrude go together")
    js(f"{M}.history.go(1)")
    v = settled_volume()
    check(len(js(f"return {M}.part.features")) == 5, "redo: both back")
    # the sketch opened: its outline (the face's two loops) drawn
    js(f"{M}.edit(arguments[0])", sk["id"])
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.8)
    check(js(f"return {M}.sk.outlineRings({M}.sk.f.entities[0]).length") == 2, "the sketch opened: the face's outline and its hole drawn")
    d.save_screenshot(f"{OUT}/face_extrude_sketch.png")
    js(f"{M}.cancelSketch()")
    wait(f"return {M}.mode === 'part'")
    # the AI: the same in one call
    r = json.loads(call("add_feature", type="extrude", face=f"{ex['id']}:end", d=2))
    check(r.get("ok") and abs(r.get("volume_change_mm3", 0) - FACE * 2) < 0.01, f"the AI's add_feature extrude {{face}}: +{r.get('volume_change_mm3')}")

    # ---- in Czech
    lang(True)
    rows = click_top()
    check(any("Vysunout tuto plochu" in r for r in rows[:3]), f"in Czech: {rows[:3]}")
    lang(False)
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    d.quit()
print("ALL OK" if not fails and not errs else f"FAILED: {fails}")
