"""A right-click in a sketch ends the drawing tool, not the sketch (as in CAD apps) — with REAL mouse input, in the
Czech UI: a new model -> ◯ two circles -> a right-click in the view: the circle tool ends (⬚ Select), a 3rd click draws
nothing, the sketch is still open with 2 circles -> ⟋ lines: 3 points, a right-click ends the chain (the tool stays),
a second right-click leaves the tool -> no tool: a right-click keeps the sketch open -> the hint by the cursor:
"🖱 Konec kružnice" / "Konec lomené čáry" / "Konec čáry" while a tool is on, no 🖱 without one -> ✓ Finish sketch ->
the Extrude panel: a right-click is still its OK (the step is added). Console errors: none.

  PYTHONIOENCODING=utf-8 py tools/e2e_sketch_rclick.py http://127.0.0.1:5199 <out dir>
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
    """The offset from the canvas' middle of a point [u, v] of the sketch."""
    return js(f"""const m = {M}, v = m.view, f = m.frame(), [u, w] = arguments[0];
      const y = [f.n[1]*f.x[2]-f.n[2]*f.x[1], f.n[2]*f.x[0]-f.n[0]*f.x[2], f.n[0]*f.x[1]-f.n[1]*f.x[0]];
      const p = new (v.camera.position.constructor)(f.o[0] + u*f.x[0] + w*y[0], f.o[1] + u*f.x[1] + w*y[1], f.o[2] + u*f.x[2] + w*y[2]);
      const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(uv))


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


def right_click(o):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *o).perform()
    time.sleep(0.2)
    ActionChains(d).context_click().perform()
    time.sleep(0.6)


def hover(o):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *o).perform()
    ActionChains(d, duration=30).move_by_offset(3, 2).perform()
    time.sleep(0.3)


def hint():
    """The cursor hint: (shown, its text, has the mouse icon)."""
    return js("""const h = document.querySelector('#modelViewport .rc-hint');
      if (!h || h.hidden) return [false, '', false];
      return [true, h.textContent.replace(/\\s+/g, ' ').trim(), !!h.querySelector('.rc-mouse')];""")


def ents(kind):
    return js(f"return {SK}.f.entities.filter(e => e.t === arguments[0]).length", kind)


def tool(a):
    d.find_element(By.CSS_SELECTOR, f".m-cmdbar [data-a={a}], #modelViewport [data-a={a}]").click()
    time.sleep(0.3)


try:
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "newModelBtn").click()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.8)

    # ---- ◯ two circles, a right-click ends the tool; a 3rd click draws nothing
    tool("circle")
    hover(free_spot())
    h = hint()
    print("hint with ◯ on:", h)
    check("hint with ◯ on: 🖱 Konec kružnice", h[0] and h[2] and "Konec kružnice" in h[1], h)
    click_at(off_uv((-30, 0)))
    click_at(off_uv((-22, 0)))
    click_at(off_uv((30, 0)))
    click_at(off_uv((38, 0)))
    check("◯: 2 circles drawn", ents("circle") == 2, ents("circle"))
    d.save_screenshot(f"{OUT}/sk_rclick_circles.png")
    right_click(free_spot())
    check("◯: a right-click ended the circle tool (⬚ Select)", js(f"return {SK}.tool") == "select", js(f"return {SK}.tool"))
    check("◯: the sketch is still open", js(f"return {M}.mode") == "sketch" and not js(f"return !!{M}.cmd"))
    click_at(off_uv((0, 30)))
    click_at(off_uv((8, 30)))
    check("◯: the next clicks draw nothing (2 circles)", ents("circle") == 2, ents("circle"))
    hover(free_spot())
    h = hint()
    print("hint with no tool:", h)
    check("no tool: the hint has no 🖱 part", not h[2] and "Konec" not in h[1] and "Dokončit" not in h[1], h)

    # ---- ⟋ lines: the 1st right-click ends the chain, the 2nd the tool
    tool("line")
    click_at(off_uv((-30, -30)))
    click_at(off_uv((0, -40)))
    click_at(off_uv((30, -30)))
    n_lines = ents("line")
    check("⟋: 2 lines drawn in a chain", n_lines == 2 and js(f"return !!{SK}.chain"), [n_lines, js(f"return !!{SK}.chain")])
    hover(free_spot())
    h = hint()
    print("hint in a chain:", h)
    check("hint in a chain: 🖱 Konec lomené čáry", h[0] and h[2] and "Konec lomené čáry" in h[1], h)
    d.save_screenshot(f"{OUT}/sk_rclick_chain.png")
    right_click(free_spot())
    check("⟋: the 1st right-click ended the chain, the line tool stays",
          not js(f"return !!{SK}.chain") and js(f"return {SK}.tool") == "line" and ents("line") == n_lines,
          [js(f"return !!{SK}.chain"), js(f"return {SK}.tool"), ents("line")])
    hover(free_spot())
    h = hint()
    check("hint after the chain: 🖱 Konec čáry", h[0] and h[2] and "Konec čáry" in h[1] and "lomené" not in h[1], h)
    right_click(free_spot())
    check("⟋: the 2nd right-click left the tool (⬚ Select)", js(f"return {SK}.tool") == "select", js(f"return {SK}.tool"))

    # ---- no tool: a right-click keeps the sketch open
    right_click(free_spot())
    check("no tool: a right-click keeps the sketch open", js(f"return {M}.mode") == "sketch" and js(f"return {SK}.tool") == "select"
          and ents("circle") == 2 and ents("line") == n_lines)

    # ---- Esc still ends a tool
    tool("circle")
    d.find_element(By.TAG_NAME, "body").send_keys("")
    time.sleep(0.3)
    check("Esc still ends the tool", js(f"return {SK}.tool") == "select" and js(f"return {M}.mode") == "sketch")

    # ---- ✓ Finish sketch, then in Extrude a right-click is OK
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=finish]").click()
    wait(f"return {M}.mode === 'part' && !!{M}.cmd", 20)
    settled()
    check("✓ Finish sketch opened the Extrude panel", js(f"return {M}.cmd?.feature.type") == "extrude")
    hover(free_spot())
    h = hint()
    print("hint with Extrude:", h)
    check("hint with Extrude: 🖱 OK", h[0] and h[2] and h[1].startswith("OK"), h)
    right_click(free_spot())
    settled()
    n_ex = len([f for f in js(f"return {M}.part.features") if f["type"] == "extrude"])
    check("Extrude: a right-click is its OK (the step is added)", n_ex == 1 and js(f"return !{M}.cmd"), [n_ex, js(f"return !!{M}.cmd")])
    d.save_screenshot(f"{OUT}/sk_rclick_extruded.png")
finally:
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        fails.append("console errors")
    d.quit()

print(f"{n_ok[0]} checks ok;", "FAILED:" if fails else "ALL OK", fails if fails else "")
sys.exit(1 if fails else 0)
