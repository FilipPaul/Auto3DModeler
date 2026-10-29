"""A made hole dragged on its face — in Czech, headless Edge, a real mouse (ActionChains): a 60 × 40 × 10 plate, one
◎ Hole step with two holes (15, 12) and (45, 28) -> hovered: the move cursor and its hint -> the first one dragged
onto the face's centre: a ring where it goes, the snap marked, its distances live; let go: exactly (30, 20), kept in
the middle, the other hole where it was, the volume the same -> Ctrl+Z: back at (15, 12) -> Esc mid-drag: it stays,
no undo step -> dragged in line with the face's centre: (22, 20) -> its ↔ locked 🔒 in its panel: dragged
diagonally, only ↕ moves (22, 8) -> both locked: "🔒 kóta zamčená" at the mouse, a drag does not move it -> a plain
click chooses it -> a drag on empty space still turns the view. No console errors.

  PYTHONIOENCODING=utf-8 py tools/e2e_hole_drag.py http://127.0.0.1:5199 <out dir>
"""
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
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
H = "window.__app.agentHandlers"
M = "window.__app.modeler"
CV = "#modelViewport canvas"
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


def offset(p):
    """A 3D point -> the mouse's offset from the canvas's middle (as ActionChains wants it)."""
    return js(f"""const v = {M}.view, V = v.camera.position.constructor, [sx, sy] = v.toScreen(new V(...arguments[0])), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(p))


def canvas():
    return d.find_element(By.CSS_SELECTOR, CV)


def hover(p):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *offset(p)).perform()
    time.sleep(0.5)


def click_at(p):
    hover(p)
    ActionChains(d).click().perform()
    time.sleep(0.6)


def press_and_go(a, b, steps=10):
    """The left button pressed at a, the mouse moved to b (held there)."""
    pa, pb = offset(a), offset(b)
    ac = ActionChains(d, duration=20).move_to_element_with_offset(canvas(), *pa).pause(0.4).click_and_hold()
    for k in range(1, steps + 1):
        ac.move_to_element_with_offset(canvas(), pa[0] + round((pb[0] - pa[0]) * k / steps), pa[1] + round((pb[1] - pa[1]) * k / steps))
    ac.pause(0.5).perform()


def release():
    ActionChains(d).release().perform()
    settled()


def drag(a, b):
    press_and_go(a, b)
    release()


def hole():
    return js(f"return {M}.part.features.find(f => f.type === 'hole')")


def centres():
    """The hole walls' centres (x, y), from the built part."""
    return sorted([round(c, 3) for c in f["centroid"][:2]] for f in js(f"return {M}.result.body.faces") if f["type"] == "cylinder")


def tip():
    return js("const e = document.querySelector('#modelViewport .m-tip'); return e && !e.hidden ? e.textContent : ''")


def undo_steps():
    return js(f"return {M}.history.undo.length")


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.setItem('auto3d-lang', 'cs'); localStorage.removeItem('a3d.snap3d')")
    d.get(URL)
    wait("return !!window.__app && document.documentElement.lang === 'cs'")
    call("new_model", name="Drag")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    settled()
    js(f"{M}.view.setView('top')")
    time.sleep(0.6)

    # ---- one Hole step, two holes placed by clicks
    js(f"{M}.action('hole')")
    time.sleep(0.4)
    click_at([15, 12, 10])
    settled()
    click_at([45, 28, 10])
    settled()
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=ok]").click()
    settled()
    js(f"{M}.selectStep(null)")
    hid = hole()["id"]
    v0 = js(f"return {M}.result.body.volume")
    print("placed:", centres(), round(v0, 2))
    check("two holes at (15, 12) and (45, 28)", centres() == [[15, 12], [45, 28]])

    # ---- hovered: the move cursor and the hint
    hover([15, 12, 10])
    cur = js(f"return document.querySelector('{CV}').style.cursor")
    print("hover:", cur, "|", tip())
    check("hovered: the move cursor", cur == "move")
    check("hovered: 'tažením posunete díru' at the mouse", "tažením posunete díru" in tip())

    # ---- dragged onto the face's centre
    n0, p1 = undo_steps(), hole()["points"][1]
    press_and_go([15, 12, 10], [30.3, 20.2, 10])
    mid = js("""return { ring: window.__app.modeler.view.sketchGroup.children.length, snap: [...document.querySelectorAll('#modelViewport .face-snap')].map(e => e.textContent),
      live: [...document.querySelectorAll('#modelViewport .hole-dim.live')].map(e => e.textContent), drag: !!window.__app.modeler.holeDrag }""")
    print("mid-drag:", mid, "|", tip())
    d.save_screenshot(f"{OUT}/hole_drag_mid.png")
    check("mid-drag: the ring where it goes, drawn", mid["drag"] and mid["ring"] > 0)
    check("mid-drag: the snap named (the face's centre)", any("plochy" in s for s in mid["snap"]))
    check("mid-drag: its distances live (30 and 20)", set(mid["live"]) == {"20", "30"} and tip() == "↔ 30  ↕ 20")
    check("mid-drag: the part not changed yet", centres() == [[15, 12], [45, 28]])
    release()
    f = hole()
    print("dropped:", centres(), f["from"][0])
    check("let go: exactly on the face's centre (30, 20)", centres() == [[30, 20], [45, 28]])
    check("let go: kept in the middle both ways", bool(f["from"][0]["x"].get("mid")) and bool(f["from"][0]["y"].get("mid")))
    check("let go: the other hole where it was", f["points"][1] == p1 and [45, 28] in centres())
    check("let go: the volume the same", abs(js(f"return {M}.result.body.volume") - v0) < 1e-3)
    check("let go: one undo step", undo_steps() == n0 + 1)
    check("let go: the hole step chosen", js(f"return {M}.selected") == hid)

    # ---- Ctrl+Z: back
    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    settled()
    print("undone:", centres())
    check("Ctrl+Z: the hole back at (15, 12)", centres() == [[15, 12], [45, 28]])

    # ---- Esc mid-drag: it stays
    js(f"{M}.selectStep(null)")
    n0 = undo_steps()
    press_and_go([15, 12, 10], [40, 33, 10])
    ActionChains(d).send_keys(Keys.ESCAPE).perform()
    time.sleep(0.3)
    check("Esc: the preview gone", js(f"return !{M}.holeDrag && {M}.view.sketchGroup.children.length === 0"))
    release()
    print("after Esc:", centres())
    check("Esc mid-drag: the hole stays at (15, 12)", centres() == [[15, 12], [45, 28]])
    check("Esc mid-drag: no undo step", undo_steps() == n0)

    # ---- in line with the face's centre: (22, 20)
    drag([15, 12, 10], [22, 20.3, 10])
    print("in line:", centres(), hole()["from"][0])
    check("dragged in line with the centre: exactly (22, 20)", centres() == [[22, 20], [45, 28]])
    check("its ↔ from the left edge: 22", hole()["from"][0]["x"].get("d") == 22)

    # ---- ↔ locked: only ↕ moves
    js(f"{M}.edit(arguments[0])", hid)
    settled()
    d.find_element(By.CSS_SELECTOR, "#modelRight [data-lockhd='0:x']").click()
    time.sleep(0.3)
    check("🔒 in the panel: ↔ locked", (hole_cmd := js(f"return {M}.cmd.feature.lock")) and hole_cmd[0].get("x") is True)
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=ok]").click()
    settled()
    js(f"{M}.selectStep(null)")
    hover([22, 20, 10])
    print("hover, ↔ locked:", tip())
    check("hovered: says ↔ is locked", "↔ zamčená" in tip())
    press_and_go([22, 20, 10], [35, 8.2, 10])
    print("mid-drag, ↔ locked:", tip())
    check("mid-drag: x stays 22", "↔ 22" in tip())
    release()
    print("↔ locked:", centres(), hole()["from"][0])
    check("↔ locked: only ↕ moved -> (22, 8)", centres() == [[22, 8], [45, 28]])
    check("↔ locked: still 22 from the left edge", hole()["from"][0]["x"].get("d") == 22)

    # ---- both locked: it does not move
    js(f"{M}.edit(arguments[0])", hid)
    settled()
    d.find_element(By.CSS_SELECTOR, "#modelRight [data-lockhd='0:y']").click()
    time.sleep(0.3)
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=ok]").click()
    settled()
    js(f"{M}.selectStep(null)")
    hover([22, 8, 10])
    print("hover, both locked:", tip(), js(f"return document.querySelector('{CV}').style.cursor"))
    check("both locked: '🔒 kóta zamčená' at the mouse", "🔒 kóta zamčená" in tip())
    check("both locked: no move cursor", js(f"return document.querySelector('{CV}').style.cursor") != "move")
    n0 = undo_steps()
    drag([22, 8, 10], [40, 30, 10])
    check("both locked: a drag does not move it", centres() == [[22, 8], [45, 28]] and undo_steps() == n0)
    js(f"{M}.view.setView('top')")
    time.sleep(0.6)

    # ---- a plain click: as before — its centre picked, ◎ Vybrat díru in the table chooses the step
    js(f"{M}.selectStep(null); {M}.view.setView('iso')")
    time.sleep(0.8)
    wall = js(f"""const c = {M}.view.camera.position, dx = 45 - c.x, dy = 28 - c.y, L = Math.hypot(dx, dy);
      return [45 + 2.5 * dx / L, 28 + 2.5 * dy / L, 7.5];""")
    hover(wall)
    print("hover on its wall:", tip())
    check("its wall hovered: the hint", "tažením posunete díru" in tip())
    n0 = undo_steps()
    ActionChains(d).click().perform()
    settled()
    picks = js(f"return ({M}.picks || []).map(p => [p.kind, p.snap || ''])")
    rows = [b.text for b in d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-list button")]
    print("clicked:", picks, rows[:4])
    check("a click picks the hole's centre (not a drag)", picks == [["point", "centre"]] and not js(f"return !!{M}.holeDrag"))
    sel = next((b for b in d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-list button") if "Vybrat díru" in b.text), None)
    check("the table offers ◎ Vybrat díru", sel is not None)
    if sel:
        sel.click()
        time.sleep(0.5)
    check("…which chooses the hole step", js(f"return {M}.selected") == hid)
    check("the click moved nothing", centres() == [[22, 8], [45, 28]] and undo_steps() == n0)

    # ---- a drag on empty space turns the view
    js(f"{M}.selectStep(null)")
    js(f"{M}.dropSuggest(); {M}.view.setView('top')")
    time.sleep(0.8)
    pa = js(f"""const cv = {M}.view.renderer.domElement, r = cv.getBoundingClientRect();
      for (const fy of [0.5, 0.35, 0.65]) for (const fx of [0.08, 0.92, 0.15, 0.85]) {{
        const x = Math.round(r.left + r.width * fx), y = Math.round(r.top + r.height * fy);
        if (document.elementFromPoint(x, y) === cv && !{M}.view.pick(x, y)) return [x - Math.floor(r.left + r.width / 2), y - Math.floor(r.top + r.height / 2)];
      }}
      return null;""")
    cam = js(f"return {M}.view.camera.position.toArray()")
    check("an empty spot on the canvas", pa is not None)
    ActionChains(d, duration=20).move_to_element_with_offset(canvas(), *(pa or [0, 0])).click_and_hold().move_by_offset(-60 if pa and pa[0] > 0 else 60, 30).move_by_offset(-40 if pa and pa[0] > 0 else 40, 20).release().perform()
    time.sleep(0.6)
    cam2 = js(f"return {M}.view.camera.position.toArray()")
    check("a drag on empty space turns the view", math.dist(cam, cam2) > 1)
    check("…and moves no hole", centres() == [[22, 8], [45, 28]])
    d.save_screenshot(f"{OUT}/hole_drag_end.png")
finally:
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        fails.append("console errors")
    d.quit()

print("FAILED:" if fails else "ALL OK", fails if fails else "")
sys.exit(1 if fails else 0)
