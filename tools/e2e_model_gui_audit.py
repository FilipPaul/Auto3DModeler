"""The AI's GUI audit (2026-10-28), with REAL mouse input in headless Edge: a 60 x 20 x 5 plate, a Ø4 hole, a boss and
an unused sketch "Žebro" -> ⬆ Extrude: the unused sketch chosen, sketches by name; one Cancel (with a tooltip; the
rebuild's button is ✕ Stop), a real click on it frees the whole toolbar (▣ Solid from a file greyed while a step is
open); ⁂ Pattern: the last hole chosen (not the newest step), the boss ticked too -> both repeated (volume);
⇋ Mirror: ▱ A face -> "click a flat face" -> a click on the plate's end: "Across the face …"; ◜ Fillet: a click on
an edge says which edge, a click on a face "Added 4 edge(s) of …"; gui_state lists the step tree (names, off);
the sketch toolbar has ⊂⊃ Slot and "↕ Plane at" says which way + goes; the same panels in Czech.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_model_gui_audit.py http://127.0.0.1:5199 <out dir>
"""
import json
import math
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.add_argument("--lang=en-US")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"
H = "window.__app.agentHandlers"
fails = []


def check(what, ok, more=""):
    print(("OK   " if ok else "FAIL ") + what + (f" — {more}" if more else ""))
    if not ok:
        fails.append(what)


def wait(script, t=30):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def settled():
    time.sleep(0.3)
    wait(f"return !{M}.inflight")
    time.sleep(0.3)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#modelViewport canvas")


def off_xyz(p):
    return js(f"""const v = {M}.view, [x, y, z] = arguments[0];
      const [sx, sy] = v.toScreen(new (v.camera.position.constructor)(x, y, z)), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(p))


def click_at(o):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *o).perform()
    time.sleep(0.2)
    ActionChains(d).click().perform()
    time.sleep(0.3)


def btn(sel):
    d.find_element(By.CSS_SELECTOR, sel).click()
    time.sleep(0.3)


def panel():
    return d.find_element(By.CSS_SELECTOR, "#modelRight .mp-body").text.replace("\n", " | ")


def vol():
    return js(f"return {M}.result?.body?.volume")


def visible_cancels():
    return js("return [...document.querySelectorAll('button')].filter(b => b.offsetParent && /Cancel|Zrušit/.test(b.textContent))"
              ".map(b => [b.textContent.trim(), b.title])")


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.setItem('auto3d-lang', 'en')")
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Audit")
    call("add_feature", type="sketch", plane="XY", name="Deska", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("add_feature", type="hole", face="F2:end", points=[[-24, 0]], d=4)
    call("add_feature", type="sketch", plane={"face": "F2:end"}, name="Boss", shapes=[{"circle": {"x": -12, "y": 0, "d": 6}}])
    call("add_feature", type="extrude", sketch="F4", d=3)
    call("add_feature", type="sketch", plane="XY", name="Žebro", shapes=[{"rect": {"x": 20, "y": 0, "w": 4, "h": 4}}])
    settled()
    base = vol()
    bb = js(f"const g = {M}.view.mesh.geometry; g.computeBoundingBox(); const b = g.boundingBox; return [b.min.x, b.min.y, b.max.x, b.max.y]")
    x0, y0, x1, y1 = bb
    xm, ym = (x0 + x1) / 2, (y0 + y1) / 2
    print("plate from", bb)
    hole, boss = math.pi * 4 * 5, math.pi * 9 * 3
    print("plate + hole + boss:", round(base, 3), "| expected", round(6000 - hole + boss, 3))

    # 4) Extrude: the unused sketch, sketches by name
    btn("#modelViewport [data-a=extrude]")
    settled()
    opts_ = js("return [...document.querySelectorAll('#modelRight [data-k=sketch] option')].map(o => [o.textContent, o.selected])")
    check("Extrude lists sketches by name", [o[0] for o in opts_] == ["Deska", "Boss", "Žebro"], str(opts_))
    check("Extrude picks the unused sketch Žebro", [o[0] for o in opts_ if o[1]] == ["Žebro"])
    # 1) one Cancel, with a tooltip; the rebuild's button is Stop; Solid from a file greyed
    cs = visible_cancels()
    check("one Cancel on screen, with a tooltip", len(cs) == 1 and bool(cs[0][1]), str(cs))
    check("the rebuild's button is ✕ Stop", js("return document.querySelector('#modelViewport .m-busy [data-a=stop]').textContent") == "✕ Stop")
    check("▣ Solid from a file greyed while a step is open", js("return document.querySelector('#modelViewport [data-a=solidFile]').disabled"))
    d.save_screenshot(f"{OUT}/audit1_extrude.png")
    btn("#modelViewport .view-actions [data-a=cancel]")
    settled()
    greyed = js("return [...document.querySelectorAll('#modelViewport .m-cmdbar [data-a]')].filter(b => b.disabled).map(b => b.dataset.a)")
    check("after Cancel the toolbar is free", not [a for a in greyed if a not in ("redo",)], str(greyed))
    check("after Cancel no panel actions", not js("return [...document.querySelectorAll('#modelViewport .view-actions')].some(x => !x.hidden)"))

    # 4) Pattern: the last hole (not the newest step), the boss ticked too
    btn("#modelViewport [data-a=pattern]")
    settled()
    print("pattern panel:", panel())
    check("Pattern repeats the hole by default", js(f"return {M}.cmd.feature.features") == ["F3"])
    names = js("return [...document.querySelectorAll('#modelRight .mp-checks label')].map(l => l.textContent.trim())")
    check("Pattern lists steps by name", "Hole 1" in names and not any(n.startswith("F") and n[1:].isdigit() for n in names), str(names))
    count = js("return document.querySelector('#modelRight [data-k=count]').value")
    print("3 holes:", round(vol(), 3), "| expected", round(base - (int(count) - 1) * hole, 3))
    box = [b for b in d.find_elements(By.CSS_SELECTOR, "#modelRight .mp-checks label") if "Boss" in b.text or "Extrude" in b.text and "Deska" not in b.text]
    box[0].click()
    settled()
    check("Pattern repeats two steps", js(f"return {M}.cmd.feature.features") == ["F3", "F5"], str(js(f"return {M}.cmd.feature.features")))
    want = base + (int(count) - 1) * (boss - hole)
    check("hole and boss repeated (volume)", abs(vol() - want) < 0.05, f"{round(vol(), 3)} vs {round(want, 3)}")
    js(f"{M}.view.setView('iso')")
    time.sleep(0.4)
    d.save_screenshot(f"{OUT}/audit2_pattern.png")
    # unticking both: one stays
    for _ in range(2):
        d.find_element(By.CSS_SELECTOR, "#modelRight .mp-checks input:checked").click()
        settled()
    check("at least one step stays ticked", len(js(f"return {M}.cmd.feature.features")) == 1)
    btn("#modelViewport .view-actions [data-a=cancel]")
    settled()

    # 6) Mirror: a visible "A face" choice
    btn("#modelViewport [data-a=mirror]")
    settled()
    btn("#modelRight [data-pl=face]")
    check("▱ A face asks for the face", "Click a flat face of the part in the view." in panel(), panel())
    js(f"{M}.view.setView('iso')")
    time.sleep(0.4)
    click_at(off_xyz([x1, ym, 2.5]))  # the plate's right end
    settled()
    print("mirror panel:", panel())
    check("Mirror across the clicked face", bool(js(f"return {M}.cmd.feature.plane.face")) and "Across the face" in panel(), panel())
    check("▱ A face is on", js("return document.querySelector('#modelRight [data-pl=face]').classList.contains('on')"))
    d.save_screenshot(f"{OUT}/audit3_mirror.png")
    btn("#modelViewport .view-actions [data-a=cancel]")
    settled()

    # 7) Fillet: what a click picked
    btn("#modelViewport [data-a=fillet]")
    settled()
    js(f"{M}.view.setView('iso')")
    time.sleep(0.4)
    click_at(off_xyz([x1, ym, 5]))  # the top edge of the right end
    settled()
    print("fillet after an edge:", panel())
    check("an edge click says which edge", "Added the edge between" in panel() and "1 edge(s) picked" in panel(), panel())
    click_at(off_xyz([xm + 10, y0, 2.5]))  # the front wall
    settled()
    print("fillet after a face:", panel())
    check("a face click says how many of its edges", "edge(s) of" in panel(), panel())
    d.save_screenshot(f"{OUT}/audit4_fillet.png")

    # the same panel in Czech
    btn("#langBtn")
    time.sleep(0.6)
    cz = panel()
    print("fillet in Czech:", cz)
    check("Czech: the last click", "Přidáno hran:" in cz or "Přidána hrana mezi" in cz, cz)
    d.save_screenshot(f"{OUT}/audit5_fillet_cs.png")
    btn("#modelViewport .view-actions [data-a=cancel]")
    settled()
    btn("#modelViewport [data-a=pattern]")
    settled()
    cz = panel()
    print("pattern in Czech:", cz)
    check("Czech: pattern's list", "Opakovat" in cz and "kroků: 1" in cz and "Zaškrtněte" in cz, cz)
    btn("#modelViewport .view-actions [data-a=cancel]")
    settled()
    btn("#modelViewport [data-a=mirror]")
    settled()
    btn("#modelRight [data-pl=face]")
    cz = panel()
    print("mirror in Czech:", cz)
    check("Czech: mirror's face choice", "Plocha" in cz and "Klikněte na rovnou plochu dílu v pohledu." in cz, cz)
    check("Czech: Cancel's tooltip", js("return document.querySelector('#modelViewport .view-actions [data-a=cancel]').title") == "Zavřít beze změny (Esc)")
    btn("#modelViewport .view-actions [data-a=cancel]")
    settled()
    btn("#langBtn")
    time.sleep(0.4)

    # 9) gui_state: the step tree
    js(f"{M}.toggleOff('F5')")
    settled()
    st = json.loads(call("gui_state", where="panel"))
    steps = st.get("steps") or []
    print("gui_state steps:", steps)
    check("gui_state lists the steps by name", [s["name"] for s in steps][:2] == ["Extrude – Deska", "Deska"] and steps[1].get("parent") == steps[0]["id"] and len(steps) == 6, str([s["name"] for s in steps]))
    check("gui_state shows a step turned off", any(s["id"] == "F5" and s.get("off") for s in steps))
    js(f"{M}.toggleOff('F5')")
    settled()

    # 2) / 3) the sketch toolbar: ⊂⊃ Slot, ↕ Plane at with its + direction
    btn("#modelViewport [data-a=sketch]")
    btn("#modelViewport [data-a=datum-XZ]")
    time.sleep(0.5)
    check("⊂⊃ Slot in the sketch toolbar", js("return !!document.querySelector('#modelViewport .m-cmdbar [data-a=slot]')?.offsetParent"))
    plus = js("return document.querySelector('#modelViewport .m-plus')?.textContent")
    check("↕ Plane at says which way + goes", bool(plus) and "+ = " in plus, str(plus))
    ActionChains(d).move_to_element(d.find_element(By.CSS_SELECTOR, "#modelViewport .m-offset")).perform()
    time.sleep(0.4)
    d.save_screenshot(f"{OUT}/audit6_plane_arrow.png")
    btn("#modelViewport [data-a=cancelSketch]")
finally:
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    d.quit()
print("FAILED:" if fails else "ALL OK", fails if fails else "")
sys.exit(1 if fails or errs else 0)
