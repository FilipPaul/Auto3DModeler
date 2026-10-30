"""Editing a Hole step, a click on another face, in headless Edge, in Czech, with real mouse clicks: a 100 × 40 × 10
block with a 30 × 30 pad 8 mm high on its top, 2× M3 tapped holes on the block's top -> a click on a hole's rim, ✎
Upravit díru -> a click on the hole's own face: none added (editing never arms placing), the suggestions' first row
＋ Přidat díru sem (ringed), the toast with the same button -> that row: a third hole where the click was, ＋ Přidat
pozici on -> a click on the pad's top: the step stays as it was, the suggestions' first row ＋
Stejná díra na této ploše (a ring on it), the toast says why and has the same button; a click on the toast's text
points again -> the toast's button: the step is done (3 holes), a new Hole step on the pad, M3 tapped like it, its hole
where the click was -> Enter: two Hole steps, the body's volume down by the drilled Ø (tap drill 2.5) × depth -> Ctrl+Z,
again through the suggestions' row instead of the toast -> the same.

  PYTHONIOENCODING=utf-8 py tools/e2e_hole_second_face.py http://127.0.0.1:5199 <out dir>
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


def face_px(name, p):
    """A pixel on face `name` near the 3D point p -> its offset from the canvas' middle."""
    return js(f"""const v = {M}.view, V = v.camera.position.constructor, [sx, sy] = v.toScreen(new V(...arguments[1])), r = v.renderer.domElement.getBoundingClientRect();
      for (let rad = 0; rad < 60; rad += 3) for (let a = 0; a < 360; a += rad ? 20 : 360) {{
        const x = sx + rad * Math.cos(a * Math.PI / 180), y = sy + rad * Math.sin(a * Math.PI / 180), h = v.pick(x, y);
        if (h?.face?.name === arguments[0] && v.pickEdge(x, y, 9) < 0) return [Math.round(x - Math.floor(r.left + r.width / 2)), Math.round(y - Math.floor(r.top + r.height / 2))];
      }}
      return null;""", name, list(p))


def rim_of(step, centre):
    """A pixel on the rim of a hole of `step` (an edge between its wall and the face) near the 3D point `centre`."""
    return js(f"""const v = {M}.view, V = v.camera.position.constructor, [sx, sy] = v.toScreen(new V(...arguments[1])), r = v.renderer.domElement.getBoundingClientRect(), b = {M}.result.body;
      for (let rad = 0; rad < 30; rad += 1) for (let a = 0; a < 360; a += 15) {{
        const x = sx + rad * Math.cos(a * Math.PI / 180), y = sy + rad * Math.sin(a * Math.PI / 180), i = v.pickEdge(x, y, 3);
        if (i >= 0 && b.edges[i].faces.some((k) => b.faces[k]?.name?.startsWith(arguments[0] + ':'))) return [Math.round(x - Math.floor(r.left + r.width / 2)), Math.round(y - Math.floor(r.top + r.height / 2))];
      }}
      return null;""", step, list(centre))


def click_off(o):
    ActionChains(d, duration=30).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, CV), *o).perform()
    time.sleep(0.3)
    ActionChains(d).click().perform()
    time.sleep(0.8)


def ring_on(sel):
    """Is the pointing ring (pointat.js) shown around the control `sel`?"""
    return js("""const r = document.querySelector('.teach-ring.pt-ring:not(.pt-out)'), el = [...document.querySelectorAll(arguments[0])].find((e) => e.getClientRects().length);
      if (!r || r.hidden || !el) return false;
      const a = r.getBoundingClientRect(), b = el.getBoundingClientRect(), cx = b.left + b.width / 2, cy = b.top + b.height / 2;
      return cx > a.left && cx < a.right && cy > a.top && cy < a.bottom;""", sel)


def toasts():
    return [e.text for e in d.find_elements(By.CSS_SELECTOR, "#toasts .toast")]


def holes():
    """The Hole steps as they are now (the one open in the tool: its edited copy; a new one: at the end)."""
    return js(f"""const c = {M}.cmd?.feature, fs = {M}.part.features.map(f => (c && f.id === c.id ? c : f));
      if (c && !fs.includes(c)) fs.push(c);
      return fs.filter(f => f.type === 'hole').map(f => ({{id: f.id, face: f.plane?.face?.name, n: f.points.length, d: f.d, thread: f.thread, standard: f.standard, type: f.hole_type || null}}))""")


def volume():
    return js(f"return {M}.result?.body?.volume ?? {M}.result?.volume ?? null")


def open_edit():
    """A click on a hole's rim (as the report: the edge), then ✎ Upravit díru in the suggestions."""
    o = rim_of("F5", [16.25, 15, 10])
    check("a hole's rim found on the screen", o is not None)
    click_off(o)
    sg = lambda: d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-list button[data-sg]")  # noqa: E731
    pick = [b for b in sg() if "Vybrat díru" in b.text]  # (the rim's snap: ◎ Vybrat díru M3 first)
    if pick:
        pick[0].click()
        time.sleep(0.6)
    row = [b for b in sg() if "Upravit díru" in b.text]
    check(f"✎ Upravit díru in the suggestions ({[' '.join(b.text.split()) for b in sg()]})", bool(row))
    row[0].click()
    settled()
    check("the hole is open to edit", js(f"return {M}.cmd?.feature.id === 'F5' && !{M}.cmd.isNew"))


def pad_click():
    o = face_px("F4:end", [80, 20, 18])
    check("the pad's top found on the screen", o is not None)
    click_off(o)
    return o


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.setItem('auto3d-lang', 'cs'); localStorage.removeItem('a3d.leftDock')")
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Rameno")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 100, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="sketch", plane={"face": "F2:end"}, shapes=[{"rect": {"x": 15, "y": -15, "w": 30, "h": 30}}])
    call("add_feature", type="extrude", sketch="F3", d=8)
    r = call("add_feature", type="hole", face="F2:end", points=[[-35, -5], [-25, 5]], thread=True, standard="M3", through=True)
    print("  hole:", r[:120])
    settled()
    h0 = holes()
    check(f"2× M3 tapped on the block's top: {h0}", len(h0) == 1 and h0[0]["n"] == 2 and h0[0]["face"] == "F2:end" and h0[0]["thread"])
    v0 = volume()

    # ✎ Upravit díru, a click on its own face: ＋ Přidat díru sem offered
    open_edit()
    click_off(face_px("F2:end", [10, 32, 10]))
    settled()
    check(f"a click on its own face alone adds none (opening a step never arms it): {holes()[0]['n']} holes", holes()[0]["n"] == 2)
    rows = [" ".join(b.text.split()) for b in d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-list button[data-sg]")]
    check(f"the suggestions' first row: ＋ Přidat díru sem ({rows})", rows and "Přidat díru sem" in rows[0])
    check("a ring on that row", ring_on("[data-sgid=holeHere]"))
    check(f"the toast says how, with the same button: {toasts()}", any("Přidat díru sem" in x and "Přidat pozici" in x for x in toasts()))
    d.save_screenshot(f"{OUT}/second_face_here.png")
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-suggest [data-sgid=holeHere]").click()
    settled()
    check(f"＋ Přidat díru sem: a third hole there: {holes()[0]['n']} holes", holes()[0]["n"] == 3)
    check("＋ Přidat pozici is on now (more clicks add more)", js("return !!document.querySelector('[data-a=addpos].on')"))

    # a click on the pad's top: offered, not refused
    spot = pad_click()
    check(f"the step stays on its face, 3 holes: {holes()}", len(holes()) == 1 and holes()[0]["n"] == 3 and js(f"return !!{M}.cmd"))
    rows = [" ".join(b.text.split()) for b in d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-list button[data-sg]")]
    check(f"the suggestions' first row: ＋ Stejná díra na této ploše ({rows})", rows and "Stejná díra na této ploše" in rows[0])
    check("a ring on that row", ring_on("[data-sgid=sameHole]"))
    t = [e for e in d.find_elements(By.CSS_SELECTOR, "#toasts .toast") if "jedné ploše" in e.text]
    check(f"the toast says why, with the same button: {[x.text for x in t]}", bool(t) and "Stejná díra na této ploše" in t[-1].text)
    d.save_screenshot(f"{OUT}/second_face_offer.png")
    js("document.querySelectorAll('.teach-ring.pt-ring').forEach(r => r.remove())")
    ActionChains(d).move_to_element_with_offset(t[-1], -t[-1].size["width"] // 2 + 12, 0).click().perform()  # its text, not its button
    time.sleep(0.3)
    check("a click on the toast's text points again (the toast stays)", ring_on("[data-sgid=sameHole]") and t[-1].is_displayed())
    t[-1].find_element(By.CSS_SELECTOR, "button.pt-act").click()
    settled()
    hs = holes()
    check(f"the edited step done, a new one on the pad with the same type, size, thread: {hs}", len(hs) == 2 and hs[0]["n"] == 3 and hs[1]["face"] == "F4:end" and hs[1]["n"] == 1
          and all(hs[1][k] == hs[0][k] for k in ("d", "thread", "standard", "type")) and js(f"return {M}.cmd?.isNew === true"))
    ActionChains(d).send_keys(Keys.ENTER).perform()
    settled()
    v1 = volume()
    # a third Ø2.5 through the block (10 mm) and one through the pad and block (18 mm): the volume down by both
    dv = math.pi * (hs[0]["d"] / 2) ** 2 * (10 + 18)
    check(f"OK: two Hole steps, the volume {v0} -> {v1} (down by {dv:.3f} mm³)", js(f"return !{M}.cmd") and len(holes()) == 2 and v0 and v1 and abs((v0 - v1) - dv) < 0.05 * dv)
    check("no step failed", js(f"return ({M}.result?.features || []).every(s => s.ok !== false && !s.error)"))

    # again, through the suggestions' row
    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    settled()
    check(f"Ctrl+Z: one Hole step again: {holes()}", len(holes()) == 1)
    open_edit()
    pad_click()
    row = d.find_element(By.CSS_SELECTOR, "#modelViewport .view-suggest [data-sgid=sameHole]")
    row.click()
    settled()
    hs = holes()
    check(f"the suggestions' row does the same: {hs}", len(hs) == 2 and hs[1]["face"] == "F4:end" and hs[1]["n"] == 1 and js(f"return {M}.cmd?.isNew === true"))
    d.save_screenshot(f"{OUT}/second_face_row.png")
    errs = [x["message"] for x in d.get_log("browser") if x["level"] == "SEVERE"]
    check(f"no errors in the console: {errs[:3]}", not errs)
finally:
    js("localStorage.removeItem('auto3d-lang')")
    d.quit()

print("FAILED:" if fails else "ALL OK", *fails, sep="\n  ")
sys.exit(1 if fails else 0)
