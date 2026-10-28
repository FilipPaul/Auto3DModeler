"""⧈ Offset's copy stays linked to its original, with REAL mouse input: a 40 x 20 rectangle -> ⧈ Offset 3 (outside):
a 46 x 26 copy held by a ⧈ relation (no new free sizes) -> the rectangle's width label typed 60: the copy follows
(-3 … 63) -> the ⧈ 3 label typed 5: the copy moves (-5 … 65), its original stays -> Ctrl+Z: 3 again, Ctrl+Y: 5 ->
⬚ Select the copy: ⛓ Unlink the offset in the suggestions -> unlinked (a one-off copy, its lines horizontal / vertical)
-> Ctrl+Z: linked again -> ✓ Finish, ⬆ Extrude 5: the frame (70·30 − 60·20)·5. Then a circle offset −2 (a ring)
whose Ø is typed bigger: the inner circle follows.

  PYTHONIOENCODING=utf-8 py tools/e2e_sketch_offset_linked.py http://127.0.0.1:5199 <out dir>
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
M = "window.__app.modeler"
SK = f"{M}.sk"


def wait(script, t=30):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#modelViewport canvas")


def off(uv):
    return js(f"""const m = {M}, v = m.view, f = m.frame(), [u, w] = arguments[0];
      const y = [f.n[1]*f.x[2]-f.n[2]*f.x[1], f.n[2]*f.x[0]-f.n[0]*f.x[2], f.n[0]*f.x[1]-f.n[1]*f.x[0]];
      const p = new (v.camera.position.constructor)(f.o[0] + u*f.x[0] + w*y[0], f.o[1] + u*f.x[1] + w*y[1], f.o[2] + u*f.x[2] + w*y[2]);
      const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(uv))


def move_uv(uv):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *off(uv)).perform()
    time.sleep(0.15)


def click_uv(uv):
    move_uv(uv)
    ActionChains(d).click().perform()
    time.sleep(0.4)


def tool(t):
    d.find_element(By.CSS_SELECTOR, f".m-cmdbar [data-a={t}], #modelViewport .view-actions [data-a={t}]").click()
    time.sleep(0.25)


def settle():
    time.sleep(0.8)
    wait(f"return !{M}.building")
    time.sleep(0.3)


def key(ch):
    ActionChains(d).key_down(Keys.CONTROL).send_keys(ch).key_up(Keys.CONTROL).perform()
    time.sleep(0.8)


def type_into(el, v):
    """A real click on a size label, then the number and Enter."""
    ActionChains(d).move_to_element(el).click().perform()
    inp = wait("return document.querySelector('#modelViewport .sk-input')")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys(str(v), Keys.ENTER)
    settle()


def label(text):
    """The size label showing exactly this text."""
    els = [e for e in d.find_elements(By.CSS_SELECTOR, "#modelViewport .sk-label .sk-val") if e.text.strip() == text]
    return els[0] if els else None


def span(ids):
    ps = js(f"const s = {SK}; return arguments[0].map((id) => s.P(id))", ids)
    return [round(min(p[0] for p in ps), 4), round(max(p[0] for p in ps), 4), round(min(p[1] for p in ps), 4), round(max(p[1] for p in ps), 4)]


def copy_pts():
    return js(f"""const s = {SK}, k = s.f.constraints.find((c) => c.t === 'off');
      return k ? [...new Set(k.copies.flatMap((id) => {{ const e = s.ent(id); return e ? [e.a, e.b] : []; }}))] : []""")


def new_sketch():
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "newModelBtn").click()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.6)
    tool("plane-XY")
    js(f"{M}.view.lookAt({M}.frame(), 120); {SK}.draw()")
    time.sleep(0.4)


def extrude(h):
    tool("finish")
    wait(f"return {M}.mode === 'part'")
    tool("extrude")
    time.sleep(0.4)
    el = d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=d]")
    el.clear()
    el.send_keys(f"{h}\n")
    time.sleep(0.5)
    for b in d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=ok]"):  # (Enter may have done it)
        b.click()
    wait(f"return {M}.result?.body && !{M}.building")
    time.sleep(0.8)
    return js(f"return {M}.result.body.volume")


try:
    # ---- a rectangle offset 3 outside, linked
    new_sketch()
    click_uv((0, 0))
    click_uv((40, 20))
    tool("select")
    time.sleep(0.5)
    dof0 = js(f"return {SK}.dof")
    tool("offset")
    print("hint:", js("return document.querySelector('#modelViewport .m-hint')?.textContent")[-60:])
    click_uv((20, 0))
    inp = wait("return document.querySelector('.sk-choose input')")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys("3", Keys.ENTER)
    settle()
    tool("select")
    time.sleep(0.6)
    q = copy_pts()
    print("offset 3:", js(f"return {SK}.f.constraints.filter((k) => k.t === 'off').map((k) => [k.d, k.pairs.length])"),
          "| copy spans", span(q), "| dof", dof0, "->", js(f"return {SK}.dof"))
    lab = label("⧈ 3")
    print("the ⧈ 3 label shown:", bool(lab))
    d.save_screenshot(f"{OUT}/offset_linked1.png")
    # the rectangle's width typed 60: the copy follows
    type_into(label("40"), 60)
    print("width 60 -> copy spans", span(q), "| expected [-3, 63, -3, 23]")
    # the distance typed 5: the copy moves, the rectangle stays
    orig = js(f"return {SK}.f.entities.filter((e) => e.g).flatMap((e) => [e.a, e.b])")
    type_into(label("⧈ 3"), 5)
    print("distance 5 -> copy spans", span(q), "| expected [-5, 65, -5, 25] | rectangle", span(orig))
    key("z")
    print("Ctrl+Z -> copy spans", span(q), "| label", bool(label("⧈ 3")))
    key("y")
    print("Ctrl+Y -> copy spans", span(q), "| label", bool(label("⧈ 5")))
    # pick the copy: Unlink in the suggestions
    click_uv((20, -5))
    items = [e.text for e in d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest button, #modelViewport .view-suggest .vs-item")]
    print("picked:", js(f"return ({SK}.picks || []).map((p) => p.kind + ' ' + p.id)"), "| suggestions:", [i for i in items if i][:8])
    unl = [e for e in d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest *") if e.text.strip().endswith("Unlink the offset")]
    unl[-1].click()
    settle()
    print("unlinked:", not js(f"return {SK}.f.constraints.some((k) => k.t === 'off')"),
          "| copy lines h / v:", js(f"""const s = {SK}; return s.f.constraints.filter((k) => (k.t === 'h' || k.t === 'v') && !s.ent(k.e)?.g).length"""),
          "| spans", span(q))
    key("z")
    print("Ctrl+Z -> linked again:", js(f"return {SK}.f.constraints.some((k) => k.t === 'off')"))
    v = extrude(5)
    print("frame extruded 5:", round(v, 4), "| expected", round((70 * 30 - 60 * 20) * 5, 4))

    # ---- a circle offset inside (a ring), its Ø typed bigger: the inner circle follows
    new_sketch()
    tool("circle")
    click_uv((0, 0))
    click_uv((10, 0))
    tool("offset")
    click_uv((10, 0))
    inp = wait("return document.querySelector('.sk-choose input')")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys("-2", Keys.ENTER)
    settle()
    tool("select")
    time.sleep(0.6)
    rs = lambda: sorted(js(f"return {SK}.f.entities.filter((e) => e.t === 'circle').map((e) => +e.r.toFixed(4))"))  # noqa: E731
    print("ring:", rs())
    type_into(label("Ø20"), 30)
    print("Ø30 -> radii", rs(), "| expected [13, 15]")
    v = extrude(5)
    print("ring extruded 5:", round(v, 4), "| expected", round(math.pi * (225 - 169) * 5, 4))
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
