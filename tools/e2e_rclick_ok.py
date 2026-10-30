"""A right-click in the view confirms the current command (as its OK / ✓ Finish sketch / Done button), as in
SolidWorks — with REAL mouse input, in the Czech UI: a new model -> ▭ a 40 × 30 rectangle -> a right-click in the
view ends the ▭ tool, not the sketch (that is e2e_sketch_rclick's subject) -> ✓ Finish sketch (the Extrude panel
opens); the OK button's tooltip says "Pravé tlačítko myši = OK" -> a
right-click: the extrude step is added -> ◎ Hole: 1 position clicked -> a right-click in a text field of its panel:
nothing confirmed -> a right-DRAG in the view: the view pans, the hole is not confirmed -> a right-click: the hole is
kept with its 1 position -> no command: a right-click changes nothing (no step, no error).
The hint by the cursor over the view: "🖱 Konec obdélníku" in the sketch (no Esc: there it only ends a tool); "🖱 OK ·
Esc Zrušit" (red) with the Extrude panel and with ◎ Hole before a position; "🖱 OK · Esc Hotovo" (muted) once one is
placed (Esc keeps it); hidden while right-dragging and with no command. Console errors: none.

  PYTHONIOENCODING=utf-8 py tools/e2e_rclick_ok.py http://127.0.0.1:5199 <out dir>
"""
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.actions.mouse_button import MouseButton
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.add_argument("--lang=cs-CZ")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"
SK = f"{M}.sk"
fails = []
n_ok = [0]


def check(what, ok, got=None):
    print(("  ok   " if ok else "  FAIL ") + what + ("" if ok or got is None else f" -> {got}"))
    if ok:
        n_ok[0] += 1
    else:
        fails.append(what)


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.15)
    raise TimeoutError(script)


def settled():
    time.sleep(0.5)
    wait(f"return !{M}.inflight", 120)
    time.sleep(0.4)


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#modelViewport canvas")


def off_uv(uv):
    return js(f"""const m = {M}, v = m.view, f = m.frame(), [u, w] = arguments[0];
      const y = [f.n[1]*f.x[2]-f.n[2]*f.x[1], f.n[2]*f.x[0]-f.n[0]*f.x[2], f.n[0]*f.x[1]-f.n[1]*f.x[0]];
      const p = new (v.camera.position.constructor)(f.o[0] + u*f.x[0] + w*y[0], f.o[1] + u*f.x[1] + w*y[1], f.o[2] + u*f.x[2] + w*y[2]);
      const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(uv))


def off_3d(p):
    return js(f"""const v = {M}.view, V = v.camera.position.constructor, [sx, sy] = v.toScreen(new V(...arguments[0])), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(p))


def free_spot():
    """An offset from the canvas' middle where the bare canvas is (not a label, box or button over it)."""
    return js("""const c = document.querySelector('#modelViewport canvas').getBoundingClientRect();
      for (const [fx, fy] of [[0.25, 0.3], [0.3, 0.7], [0.7, 0.3], [0.2, 0.5], [0.6, 0.6], [0.4, 0.2]]) {
        const x = Math.floor(c.left + c.width * fx), y = Math.floor(c.top + c.height * fy), el = document.elementFromPoint(x, y);
        if (el && el.tagName === 'CANVAS') return [x - Math.floor(c.left + c.width / 2), y - Math.floor(c.top + c.height / 2)];
      }
      return null;""")


def click_at(o):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *o).perform()
    time.sleep(0.25)
    ActionChains(d).click().perform()
    time.sleep(0.4)


def right_click(el=None, o=None):
    ch = ActionChains(d, duration=30)
    if o is not None:
        ch.move_to_element_with_offset(el or canvas(), *o)
    else:
        ch.move_to_element(el)
    ch.perform()
    time.sleep(0.2)
    ActionChains(d).context_click().perform()
    time.sleep(0.6)


def right_drag(o, dx, dy):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *o).perform()
    time.sleep(0.2)
    ac = ActionChains(d, duration=40)
    pa = ac.w3c_actions.pointer_action
    pa.pointer_down(button=MouseButton.RIGHT)
    for k in range(1, 9):
        pa.move_by(dx // 8, dy // 8)
    pa.pointer_up(button=MouseButton.RIGHT)
    ac.perform()
    time.sleep(0.6)


def hover(o):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *o).perform()
    ActionChains(d, duration=30).move_by_offset(3, 2).perform()
    time.sleep(0.3)


def hint():
    """The cursor hint: (shown, its text, what Esc does: 'cancel' / 'keep' / None)."""
    return js("""const h = document.querySelector('#modelViewport .rc-hint');
      if (!h || h.hidden) return [false, '', null];
      const e = h.querySelector('.rc-esc');
      return [true, h.textContent.replace(/\\s+/g, ' ').trim(), e ? (e.classList.contains('cancel') ? 'cancel' : 'keep') : null];""")


def steps(kind):
    return [f for f in js(f"return {M}.part.features") if f["type"] == kind]


def toasts():
    return " | ".join(e.text for e in d.find_elements(By.CSS_SELECTOR, ".toast"))


try:
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "newModelBtn").click()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.8)

    # ---- the sketch: ▭ a rectangle, then a right-click finishes it
    d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=rect], #modelViewport [data-a=rect]").click()
    time.sleep(0.2)
    click_at(off_uv((0, 0)))
    click_at(off_uv((40, 30)))
    check("sketch: the rectangle is drawn", js(f"return {SK}.f.entities.filter(e => e.t === 'line').length") == 4)
    fin = d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=finish]")
    tip = fin.get_attribute("title")
    print("✓ Finish sketch tooltip:", repr(tip))
    check("the finish button's tooltip does not say a right-click finishes the sketch", "Pravé tlačítko myši" not in tip, tip)
    hover(free_spot())
    h = hint()
    print("hint in the sketch:", h)
    check("hint in the sketch: 🖱 Konec obdélníku, no Esc", h[0] and "Konec obdélníku" in h[1] and h[2] is None and "Esc" not in h[1], h)
    d.save_screenshot(f"{OUT}/rclick_hint_sketch.png")
    right_click(o=free_spot())
    check("sketch: a right-click ended the ▭ tool, the sketch stays open",
          js(f"return {M}.mode") == "sketch" and js(f"return {SK}.tool") == "select", [js(f"return {M}.mode"), js(f"return {SK}.tool")])
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=finish]").click()
    wait(f"return {M}.mode === 'part' && !!{M}.cmd", 20)
    d.save_screenshot(f"{OUT}/rclick_finished_sketch.png")
    check("sketch: ✓ Finish sketch opened the Extrude panel", js(f"return {M}.mode") == "part" and js(f"return {M}.cmd?.feature.type") == "extrude")

    # ---- the Extrude panel: a right-click is its OK
    settled()
    ok = d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=ok]")
    check("OK's tooltip: Enter and the right button", "Pravé tlačítko myši = OK" in (ok.get_attribute("title") or ""), ok.get_attribute("title"))
    hover(free_spot())
    h = hint()
    print("hint with Extrude:", h)
    check("hint with the Extrude panel: 🖱 OK · Esc Zrušit (red)", h[0] and h[1].startswith("OK") and "Esc Zrušit" in h[1] and h[2] == "cancel", h)
    d.save_screenshot(f"{OUT}/rclick_hint_extrude.png")
    right_click(o=free_spot())
    settled()
    ex = steps("extrude")
    check("extrude: a right-click added the step (as OK)", len(ex) == 1 and js(f"return !{M}.cmd"), [len(ex), js(f"return !!{M}.cmd")])
    v0 = js(f"return {M}.result.body.volume")
    check(f"extrude: the 40 × 30 × 10 block is built ({v0})", abs(v0 - 12000) < 1)
    d.save_screenshot(f"{OUT}/rclick_extruded.png")

    # ---- ◎ Hole: one position, a right-click in its panel's field (no), a right-drag (pans, no), a right-click (kept)
    js(f"{M}.view.setView('top')")
    time.sleep(0.6)
    js(f"{M}.action('hole')")
    time.sleep(0.5)
    hover(free_spot())
    h = hint()
    check("hint with ◎ Hole, nothing placed: Esc Zrušit (red)", h[0] and "Esc Zrušit" in h[1] and h[2] == "cancel", h)
    click_at(off_3d([12, 15, 10]))
    hover(free_spot())
    h = hint()
    print("hint with 1 hole placed:", h)
    check("hint with 1 hole placed: 🖱 OK · Esc Hotovo (Esc keeps it)", h[0] and h[1].startswith("OK") and "Esc Hotovo" in h[1] and h[2] == "keep", h)
    d.save_screenshot(f"{OUT}/rclick_hint_hole.png")
    check("hole: 1 position placed", js(f"return {M}.cmd?.feature.points?.length") == 1, js(f"return {M}.cmd?.feature.points"))
    fields = [e for e in d.find_elements(By.CSS_SELECTOR, "#modelRight input[type=number], #modelRight input[type=text], #modelRight input:not([type])") if e.is_displayed()]
    if fields:
        right_click(el=fields[0])
        check("a right-click in a text field of the panel does not confirm", js(f"return {M}.cmd?.feature.type") == "hole" and len(steps("hole")) == 0)
    else:
        check("the hole panel has a text field", False)
    t0 = js(f"return {M}.view.controls.target.toArray()")
    o = free_spot()
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *o).perform()
    time.sleep(0.2)
    ac = ActionChains(d, duration=40)
    ac.w3c_actions.pointer_action.pointer_down(button=MouseButton.RIGHT)
    for k in range(4):
        ac.w3c_actions.pointer_action.move_by(15, 8)
    ac.perform()
    time.sleep(0.2)
    check("the hint hides while dragging", not hint()[0], hint())
    ac = ActionChains(d, duration=40)
    for k in range(4):
        ac.w3c_actions.pointer_action.move_by(15, 7)
    ac.w3c_actions.pointer_action.pointer_up(button=MouseButton.RIGHT)
    ac.perform()
    time.sleep(0.6)
    t1 = js(f"return {M}.view.controls.target.toArray()")
    moved = sum((a - b) ** 2 for a, b in zip(t0, t1)) ** 0.5
    print("pan: target moved by", round(moved, 2), "mm")
    check("a right-drag pans the view", moved > 1, moved)
    check("a right-drag does not confirm the hole", js(f"return {M}.cmd?.feature.type") == "hole" and len(steps("hole")) == 0)
    d.save_screenshot(f"{OUT}/rclick_hole_before.png")
    right_click(o=free_spot())
    settled()
    hs = steps("hole")
    check("hole: a right-click kept it with its 1 position", len(hs) == 1 and len(hs[0]["points"]) == 1 and js(f"return !{M}.cmd"),
          [(h["id"], h["points"]) for h in hs])
    v1 = js(f"return {M}.result.body.volume")
    check(f"hole: the volume went down ({v1:.1f})", v1 < v0 - 10)
    d.save_screenshot(f"{OUT}/rclick_hole_kept.png")

    # ---- no command: a right-click changes nothing
    hover(free_spot())
    check("no command: no hint", not hint()[0], hint())
    n0, mode0 = len(js(f"return {M}.part.features")), js(f"return {M}.mode")
    right_click(o=free_spot())
    settled()
    check("no command: a right-click adds or ends nothing", len(js(f"return {M}.part.features")) == n0 and js(f"return {M}.mode") == mode0 and js(f"return !{M}.cmd"))
    d.save_screenshot(f"{OUT}/rclick_idle.png")
finally:
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        fails.append("console errors")
    d.quit()

print(f"{n_ok[0]} checks ok;", "FAILED:" if fails else "ALL OK", fails if fails else "")
sys.exit(1 if fails else 0)
