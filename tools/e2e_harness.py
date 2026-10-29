"""🔌 Cable harness in the assembly, with a real mouse, in Czech (headless Edge): a box, a PCB on it and a motor beside
it -> a click on the PCB's top -> "🔌 Vést kabel odsud" in the suggestions -> Volné dráty, 4 × -> three more points
clicked (the PCB's top, the box's top, the motor's top) -> Esc keeps them: one harness, 4 wires, its length as the
kernel's math has it (auto3d/modeler/harness.py from the same points), the tree's row, BOM lines with the colours and
lengths (+5 %, rounded up to 10 mm) -> the motor moved: its point follows (and on 💥 Explode) -> a point dragged with
the mouse -> a corner with no room for the radius: a quiet ⚠ note in the view and the panel (no red over the cable) ->
a Z clicked with two sharp corners 6 mm apart: shaped to the radius, no note, the drawn tube's centre on arcs of R
-> a point deleted (Delete) -> undo -> 🔒 its length locked (the panel's button): the motor moved closer, the cable
keeps its length (the slack sags, as harness.py's shape), moved far away: taut, red, "Kabel je napnutý — krátký o …"
-> STEP export holds
the four wires -> the AI's add_harness / edit_harness / get_assembly.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_harness.py http://127.0.0.1:5199 <out dir>
"""
import json
import math
import sys
import time
import urllib.request
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from auto3d.modeler import harness as HM  # noqa: E402  (the kernel's route math, to check the page's)

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
A = "window.__app.assembly"
T = f"{A}.harnessTool"
H = "window.__app.agentHandlers"
fails = []


def check(what, ok, got=""):
    print(f"{'OK ' if ok else 'BAD'} {what}{f' — {got}' if got != '' else ''}")
    if not ok:
        fails.append(what)


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def offset(p):
    """A world point on the screen, from the canvas' middle (px)."""
    return js(f"""const v = {A}.view, V = v.camera.position.constructor, [sx, sy] = v.toScreen(new V(...arguments[0])), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", p)


def click_at(p, key=None):
    cv = d.find_element(By.CSS_SELECTOR, "#asmViewport canvas")
    ActionChains(d, duration=30).move_to_element_with_offset(cv, *offset(p)).perform()
    time.sleep(0.25)
    ActionChains(d).click().perform()
    time.sleep(0.5)


def typein(sel, text):
    """Type into a field of the panel as a user does: click, select all, type, Enter."""
    el = d.find_element(By.CSS_SELECTOR, sel)
    el.click()
    ActionChains(d).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).send_keys(text or Keys.DELETE).send_keys(Keys.ENTER).perform()
    time.sleep(0.5)


def table():
    box = d.find_elements(By.CSS_SELECTOR, "#asmViewport .view-suggest")
    return [" ".join(b.text.split()) for b in box[0].find_elements(By.CSS_SELECTOR, ".vs-list button")] if box else []


def world_points(hid="H1"):
    return js(f"""const t = {T}, h = t.get(arguments[0]);
      return h.points.map((p) => window.__hnPoint(h, p).toArray());""", hid)


def page_length(hid="H1"):
    return js(f"return {T}.list().find(h => h.id === arguments[0]) && window.__hnLength(arguments[0])", hid)


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.setItem('auto3d-lang', 'cs'); localStorage.removeItem('a3d.harness')")
    d.get(URL)
    wait("return !!window.__app")
    js("""import('/js/assembly/harness.js').then((m) => {
      window.__hnPoint = (h, p) => m.pointAt(window.__app.assembly, h, p);
      window.__hnLength = (id) => { const h = window.__app.assembly.harnessTool.get(id); return m.routeOf(h, h.points.map((p) => m.pointAt(window.__app.assembly, h, p)).filter(Boolean)).length; };
      window.__hn = m; })""")
    wait("return !!window.__hn")
    call("new_model", name="Krabice")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 160, "h": 100}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("new_model", name="DPS")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=2)
    call("new_model", name="Motor")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 30, "h": 30}}])
    call("add_feature", type="extrude", sketch="F1", d=30)
    call("new_assembly", name="Pohon")
    for p in ("Krabice", "DPS", "Motor"):
        call("insert_part", part=p)
    call("place_part", part="I2", x=10, y=50, z=10)
    call("place_part", part="I3", x=115, y=10, z=10)
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    js(f"{A}.choose(null); {A}.view.setView('iso')")
    time.sleep(1)
    d.save_screenshot(f"{OUT}/harness_0_parts.png")

    # 1. a click on the PCB's top: 🔌 Vést kabel odsud
    click_at([20, 80, 12])
    rows = table()
    check("the PCB's face offers 🔌 Vést kabel odsud", any("Vést kabel odsud" in r for r in rows), rows[:8])
    btn = next(b for b in d.find_elements(By.CSS_SELECTOR, "#asmViewport .view-suggest .vs-list button") if "Vést kabel odsud" in b.text)
    btn.click()
    time.sleep(0.5)
    check("routing: the tool is on, one point", js(f"return {T}.edit === 'H1' && {T}.get('H1').points.length") == 1, js(f"return {T}.edit"))
    check("the toolbar names it 🔌 Kabelový svazek", "Kabelový svazek" in d.find_element(By.CSS_SELECTOR, "#asmViewport [data-a=harness]").get_attribute("textContent"))
    # Volné dráty, 4 wires
    next(b for b in d.find_elements(By.CSS_SELECTOR, "#asmRight .hn-kinds button") if "Volné dráty" in b.text).click()
    time.sleep(0.3)
    typein("#asmRight input[data-hn=n]", "4")
    check("Volné dráty, 4 wires", js(f"const h = {T}.get('H1'); return [h.kind, h.wires.length]") == ["wires", 4])
    # three more points: the PCB's other end, the box's top, the motor's top (a hover first: the preview)
    cv = d.find_element(By.CSS_SELECTOR, "#asmViewport canvas")
    ActionChains(d, duration=30).move_to_element_with_offset(cv, *offset([60, 80, 12])).perform()
    time.sleep(0.5)
    check("a live preview while clicking (the next point, the length)", js(f"return !!{T}.hover") and "Délka" in d.find_element(By.CSS_SELECTOR, "#asmRight .hn-len").text,
          d.find_element(By.CSS_SELECTOR, "#asmRight .hn-len").text)
    d.save_screenshot(f"{OUT}/harness_1_preview.png")
    for p in ([60, 80, 12], [60, 15, 10], [130, 25, 40]):
        click_at(p)
    check("4 points clicked", js(f"return {T}.get('H1').points.length") == 4, js(f"return {T}.get('H1').points"))
    check("points stuck to their parts (PCB, PCB, box, motor)", js(f"return {T}.get('H1').points.map(p => p.inst)") == ["I2", "I2", "I1", "I3"],
          js(f"return {T}.get('H1').points.map(p => p.inst)"))
    ActionChains(d).send_keys(Keys.ESCAPE).perform()
    time.sleep(0.5)
    check("Esc keeps the points", js(f"return !{T}.edit && {T}.get('H1').points.length") == 4)
    js(f"{T}.sel = 'H1'; {A}.render(); {A}.draw()")
    time.sleep(0.4)
    d.save_screenshot(f"{OUT}/harness_2_routed.png")

    # 2. its length: as the kernel's math has it from the same points
    pts = world_points()
    L = page_length()
    r_min = js(f"return window.__hn.rMinOf({T}.get('H1'))")
    py = HM.route(pts, r_min)["length"]
    check("length = the kernel's route (harness.py)", abs(L - py) < 1e-6, f"{L:.3f} vs {py:.3f}")
    check("the points lie on their faces, Ø/2 + 0.5 off (the PCB's top z 12 + 1.81 + 0.5)", abs(pts[0][2] - (12 + HM.bundle_d(4, 1.5) / 2 + 0.5)) < 1e-3, pts[0])
    lt = f"{round(L):,}".replace(",", " ")
    tree = d.find_element(By.CSS_SELECTOR, "#asmLeft .hn-row").text
    check("the tree: 🔌 Svazek 1 · 4 × Ø1,5 · its length", "Svazek 1" in tree and f"4 × Ø1,5 · {lt} mm" in tree, tree)
    panel_len = d.find_element(By.CSS_SELECTOR, "#asmRight .hn-len").text
    check("the panel's length", panel_len == f"Délka {lt} mm", panel_len)

    # 3. the BOM: a line per wire with its colour and length (+5 %, up to 10 mm)
    bom = json.loads(call("get_bom"))
    want = math.ceil(L * 1.05 / 10) * 10
    wires = [r for r in bom["rows"] if r["name"].startswith("Vodič")]
    check("BOM: 4 wires with their colours and lengths", sorted(r["name"] for r in wires) == sorted(f"Vodič Ø1,5 mm {c} — {want} mm" for c in ("červený", "černý", "modrý", "hnědý")),
          [r["name"] for r in wires])
    js(f"{A}.openBom()")
    time.sleep(0.8)
    win = " ".join(e.text for e in d.find_elements(By.CSS_SELECTOR, ".bom-win, .bw-table, table"))
    check("the 📋 BOM window lists them", f"Vodič Ø1,5 mm červený — {want} mm" in win, win[-300:])
    d.save_screenshot(f"{OUT}/harness_3_bom.png")
    ActionChains(d).send_keys(Keys.ESCAPE).perform()
    js("for (const b of document.querySelectorAll('.bom-win .fb-close, .bw-close, [data-a=closeBom]')) b.click()")
    time.sleep(0.3)

    # 4. the motor moved: its point follows; explode too
    before = world_points()[3]
    call("place_part", part="I3", x=135, y=10, z=10)
    time.sleep(0.6)
    after = world_points()[3]
    check("the motor moved 20 mm: its point follows", abs(after[0] - before[0] - 20) < 1e-6 and abs(after[1] - before[1]) < 1e-6, (before, after))
    check("…and the PCB's do not", world_points()[0] == pts[0])
    js(f"{A}.setExplode(0.6)")
    time.sleep(0.5)
    ex = world_points()
    check("💥 explode: the points go with their parts", ex[0] != pts[0] and ex[3] != after, (ex[0], ex[3]))
    d.save_screenshot(f"{OUT}/harness_4_explode.png")
    js(f"{A}.setExplode(0)")
    time.sleep(0.3)

    # 5. a point dragged with the mouse (onto the box's top elsewhere)
    js(f"{T}.editPoints('H1')")
    time.sleep(0.4)
    p2 = world_points()[2]
    cv = d.find_element(By.CSS_SELECTOR, "#asmViewport canvas")
    ActionChains(d, duration=60).move_to_element_with_offset(cv, *offset(p2)).click_and_hold().move_by_offset(10, 0).move_to_element_with_offset(cv, *offset([90, 20, 10])).release().perform()
    time.sleep(0.6)
    p2b = world_points()[2]
    check("a point dragged onto the box's top", js(f"return {T}.get('H1').points[2].inst") == "I1" and math.dist(p2b, [90, 20, 10 + HM.bundle_d(4, 1.5) / 2 + 0.5]) < 1.5, (p2, p2b))

    # 6. a corner with no room for the radius (its leg ends at the cable's start): a quiet ⚠ note, no red over it
    typein("#asmRight input[data-hn=r]", "80")
    warn = [e.text for e in d.find_elements(By.CSS_SELECTOR, "#asmViewport .hn-warn")]
    bad = [e.text for e in d.find_elements(By.CSS_SELECTOR, "#asmRight .hn-bad")]
    check("R 80: the corner with no room noted ⚠ in the view", any("na 80 není místo" in w for w in warn), warn)
    check("…and in the panel", any("na R 80 mm není místo" in b for b in bad), bad)
    check("…quietly: no red over the cable", not js(f"return {T}.group.children.some(o => o.material?.color?.getHex() === 0xff4d4d)"))
    d.save_screenshot(f"{OUT}/harness_5_tight.png")
    typein("#asmRight input[data-hn=r]", "")  # (empty: the rule of thumb again)
    check("R empty: the rule of thumb 5 × Ø, no ⚠", js(f"return window.__hn.rMinOf({T}.get('H1'))") == math.ceil(5 * HM.bundle_d(4, 1.5)) and not d.find_elements(By.CSS_SELECTOR, "#asmViewport .hn-warn"))

    # 6b. a Z clicked in space with two sharp corners 6 mm apart, R 15: shaped — the corners moved apart along the
    # outer legs until both arcs are R 15 —, no note; the tube's rings centred on lines and on arcs of R 15
    js(f"{T}.finish(false)")
    r = call("add_harness", type="cable", d=4, r_min=15, points=[{"xyz": [0, 140, 60]}, {"xyz": [60, 140, 60]}, {"xyz": [60, 146, 60]}, {"xyz": [120, 146, 60]}])
    check("a Z with sharp corners: H2 cable", r.startswith("H2 cable"), r[:120])
    js(f"{T}.sel = 'H2'; {A}.render(); {A}.draw()")
    time.sleep(0.5)
    check("…shaped: no ⚠ note, no red", not d.find_elements(By.CSS_SELECTOR, "#asmViewport .hn-warn") and not d.find_elements(By.CSS_SELECTOR, "#asmRight .hn-bad")
          and not js(f"return {T}.group.children.some(o => o.material?.color?.getHex() === 0xff4d4d)"))
    rings = js(f"""const m = {T}.group.children.find(o => o.userData.harness === 'H2' && o.geometry?.type === 'TubeGeometry'), g = m.geometry, p = g.attributes.position, k = g.parameters.radialSegments, out = [];
      for (let i = 0; i <= g.parameters.tubularSegments; i++) {{ let x = 0, y = 0, z = 0; for (let j = 0; j < k; j++) {{ const q = i * (k + 1) + j; x += p.getX(q); y += p.getY(q); z += p.getZ(q); }} out.push([x / k, y / k, z / k]); }}
      return out;""")
    zr = HM.route([[0, 140, 60], [60, 140, 60], [60, 146, 60], [120, 146, 60]], 15)
    arcs = [s for s in zr["segments"] if s[0] == "arc"]
    on = lambda q: min([abs(math.dist(q, s[4]) - s[5]) for s in arcs] + [abs(q[1] - 140), abs(q[1] - 146)])  # noqa: E731  (on an arc or on a leg)
    on_arc = [q for q in rings if 140 + 1e-3 < q[1] < 146 - 1e-3]
    check("…the drawn tube bends on arcs of R 15 (its rings' centres)", len(arcs) == 2 and all(abs(s[5] - 15) < 1e-6 for s in arcs) and len(on_arc) >= 4
          and max(on(q) for q in rings) < 0.05, (len(on_arc), max(on(q) for q in rings)))
    check("…its length as the kernel's", abs(page_length("H2") - zr["length"]) < 1e-6, (page_length("H2"), zr["length"]))
    d.save_screenshot(f"{OUT}/harness_5b_shaped.png")
    call("edit_harness", id="H2", remove=True)
    js(f"{T}.sel = 'H1'; {T}.editPoints('H1')")
    time.sleep(0.4)

    # 7. a point chosen (clicked) and deleted with Delete; undo brings it back
    click_at(world_points()[1])
    check("a click on a point chooses it", js(f"return {T}.pt") == 1)
    ActionChains(d).send_keys(Keys.DELETE).perform()
    time.sleep(0.4)
    check("Delete removes it", js(f"return {T}.get('H1').points.length") == 3)
    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    time.sleep(0.6)
    check("Ctrl+Z brings it back", js(f"return {T}.get('H1').points.length") == 4)
    ActionChains(d).send_keys(Keys.ENTER).perform()
    time.sleep(0.4)
    check("Enter: done", not js(f"return {T}.edit"))

    # 7b. 🔒 its length locked with the panel's button; the motor moved closer: the cable keeps its length (the slack
    # sags), as the kernel's math has it; moved far away: taut — red, a note in the view and the panel
    js(f"{T}.sel = 'H1'; {A}.render(); {A}.draw()")
    time.sleep(0.3)
    L0 = page_length()
    d.find_element(By.CSS_SELECTOR, "#asmRight [data-hx=lock]").click()
    time.sleep(0.5)
    locked = js(f"return {T}.get('H1').length_locked")
    check("🔒 the panel's button locks its length as it is", locked and abs(locked - L0) < 0.06 and "🔒" in d.find_element(By.CSS_SELECTOR, "#asmRight [data-hx=lock]").text, (locked, L0))
    call("place_part", part="I3", x=105, y=20, z=10)
    time.sleep(0.6)
    pts_c = world_points()
    Lc, py_c = page_length(), HM.shape(world_points(), r_min, total=locked)
    check("the motor moved closer: the cable keeps its length (± 0.5 mm)", abs(Lc - locked) <= 0.5 and HM.route(pts_c, r_min)["length"] < locked - 20, (Lc, locked))
    check("…as harness.py's shape (slack sagging), no bend under R", abs(Lc - py_c["length"]) < 1e-3 and all(b["ok"] for b in py_c["bends"]), (Lc, py_c["length"], [round(b["r"], 2) for b in py_c["bends"]]))
    check("…not taut", not d.find_elements(By.CSS_SELECTOR, "#asmRight .hn-taut"))
    d.save_screenshot(f"{OUT}/harness_6b_slack.png")
    call("place_part", part="I3", x=400, y=10, z=10)
    time.sleep(0.6)
    short = HM.route(world_points(), r_min)["length"] - locked
    taut_v = [e.text for e in d.find_elements(By.CSS_SELECTOR, "#asmViewport .hn-taut")]
    taut_p = [e.text for e in d.find_elements(By.CSS_SELECTOR, "#asmRight .hn-taut")]
    check("pulled too far: taut, noted in the view", any("Kabel je napnutý" in w for w in taut_v), taut_v)
    check("…and in the panel with how much it is short", any(f"krátký o {round(short):,}".replace(",", " ") in w or "krátký o" in w for w in taut_p) and short > 0, (taut_p, short))
    check("…drawn red", js(f"return {T}.group.children.some(o => o.userData.harness === 'H1' && o.material?.color?.getHex() === 0xd0312d)"))
    check("…get_assembly says taut", json.loads(call("get_assembly"))["harnesses"][0].get("taut", {}).get("short_mm", 0) > 0)
    d.save_screenshot(f"{OUT}/harness_6c_taut.png")
    call("place_part", part="I3", x=135, y=10, z=10)
    time.sleep(0.4)
    js(f"{T}.sel = 'H1'; {A}.render(); {A}.draw()")
    time.sleep(0.3)
    d.find_element(By.CSS_SELECTOR, "#asmRight [data-hx=lock]").click()
    time.sleep(0.4)
    check("🔓 unlocked again", not js(f"return {T}.get('H1').length_locked"))

    # 8. STEP export: the four wires in it (as solids of their own part "Svazek 1")
    tree = js(f"return {A}.stepTree()")
    req = urllib.request.Request(f"{URL}/api/assembly/export/step", data=json.dumps({"tree": tree, "name": "Pohon"}).encode(), headers={"Content-Type": "application/json"})
    step = urllib.request.urlopen(req, timeout=300).read().decode("latin-1")
    (Path(OUT) / "harness_pohon.step").write_text(step, encoding="latin-1")
    check("STEP: the harness is in it (its part, 3 parts + 4 wires as solids)", "Svazek 1" in step and step.count("MANIFOLD_SOLID_BREP") >= 7, step.count("MANIFOLD_SOLID_BREP"))

    # 9. the AI: add_harness, edit_harness, get_assembly
    r = call("add_harness", type="cable", d=6, color="black", points=[{"part": "I1", "face": "F2:end"}, {"xyz": [80, 120, 40]}, {"part": "I3", "face": "F2:end"}])
    check("add_harness: a cable H2", r.startswith("H2 cable"), r[:120])
    r = call("edit_harness", id="H2", r_min=500)
    check("edit_harness r_min 500: its corner reported", "bends_too_tight" in r, r[:200])
    a = json.loads(call("get_assembly"))
    check("get_assembly lists the harnesses with their lengths", [h["id"] for h in a.get("harnesses", [])] == ["H1", "H2"] and all(h["length_mm"] > 0 for h in a["harnesses"]), a.get("harnesses"))
    r = call("edit_harness", id="H2", remove=True)
    check("edit_harness remove", r.startswith("H2 removed") and len(json.loads(call("get_assembly"))["harnesses"]) == 1, r)
    d.save_screenshot(f"{OUT}/harness_6_done.png")
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        fails.append("console errors")
    d.quit()
print(f"{'FAILED: ' + ', '.join(fails) if fails else 'ALL OK'}")
sys.exit(1 if fails else 0)
