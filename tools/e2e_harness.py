"""🔌 Cable harness in the assembly, with a real mouse, in Czech (headless Edge): a box, a PCB on it and a motor beside
it -> a click on the PCB's top -> "🔌 Vést kabel odsud" in the suggestions -> Volné dráty, 4 × -> three more points
clicked (the PCB's top, the box's top, the motor's top) -> Esc keeps them: one harness, 4 wires, its length as the
kernel's math has it (auto3d/modeler/harness.py from the same points), the tree's row, BOM lines with the colours and
lengths (+5 %, rounded up to 10 mm) -> the motor moved: its point follows (and on 💥 Explode) -> a point dragged with
the mouse -> a corner with no room for the radius: a quiet ⚠ note in the view and the panel (no red over the cable) ->
a Z clicked with two sharp corners 6 mm apart: shaped to the radius, no note, the drawn tube's centre on arcs of R
-> a point deleted (Delete) -> undo -> 🔒 its length locked (the panel's button): the motor moved closer, the cable
keeps its length (the slack sags, as harness.py's shape), moved far away: taut, red, "Kabel je napnutý — krátký o …"
-> STEP export -> the AI -> the points list (part · face, x / y / z typed, ＋ between, ↑ ↓ ✕, a row lit in the view,
🗑 all + undo), a pin's top clicked off its axis: on the axis; that point 🔒 on the pin follows it, 🔓 stays in space;
a point dragged onto the pin: on its axis; Alt + click: the box's bottom (hidden); ◎ to the face's centre; the length
label not changed by ✎; where it goes through a part (span, spot, ⚠ in the view); a point in space on a face taken as
locked; ➰ a span's own length (the suggestion, one input): a loop that long, kept as the pin moves, taut too far,
edit_harness spans; the owner's case — ends on two pins' tops leave them straight up, the span round a tall block
between them (Python checks the bundle clear of every body); 📎 a clip on a point (the suggestion): the point on its
axis, deleted -> "the clip stays" ✕, undo; ⛓ a span through a chain put in from the library: the cable on its path, the
moving end moved -> it follows, undo, edit_harness chain; a clip on a moving part 🔗 fixed to it (one undo step, it
goes along, deleted with its joint, undo); a span keeps the chain end it enters over the full travel (an older file:
decided on load); a point too close to a face end for its straight lead-out: a quiet note; saved + reloaded: the locks, spans, clips and chains kept holds
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
    # (read in the page at once: the table is drawn again while the mouse moves)
    return js("return [...document.querySelectorAll('#asmViewport .view-suggest .vs-list button')].map(b => b.textContent.split(/\\s+/).join(' ').trim())") if box else []


def world_points(hid="H1"):
    return js(f"""const t = {T}, h = t.get(arguments[0]);
      return h.points.map((p) => window.__hnPoint(h, p).toArray());""", hid)


def kernel_route(hid="H1", locked=True):
    """The harness as the export sends it to the kernel (its points with the leads and detours, its spans, its locked
    length) shaped by auto3d/modeler/harness.py — the page's own math checked against it."""
    st = js(f"return window.__hn.harnessStep(window.__app.assembly.doc, {T}.get(arguments[0]))", hid)
    return HM.shape(st["points"], st["r_min"], spans={x["from"]: x["length"] for x in st.get("spans", [])} if locked else None, total=st.get("length") if locked else None, still=st.get("still") or ())


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
      window.__hnLength = (id) => m.routeAt(window.__app.assembly, window.__app.assembly.harnessTool.get(id)).length;
      window.__hn = m; })""")
    js("""import('/js/assembly/chains.js').then((k) => { window.__hnChain = (id) => { const r = k.chainRoute(window.__app.assembly, id); return r && { points: r.points, moving: r.moving.o }; }; })""")
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
    py = kernel_route()["length"]
    check("length = the kernel's route (harness.py)", abs(L - py) < 1e-3, f"{L:.3f} vs {py:.3f}")
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
    call("place_part", part="I3", x=115, y=10, z=10)
    time.sleep(0.6)
    pts_c = world_points()
    Lc, py_c = page_length(), kernel_route()
    check("the motor moved closer: the cable keeps its length (± 0.5 mm)", abs(Lc - locked) <= 0.5 and kernel_route(locked=False)["length"] < locked - 10, (Lc, locked, kernel_route(locked=False)["length"]))
    tight = lambda r: min([b["r"] for b in r["bends"]] or [r_min])  # noqa: E731
    check("…as harness.py's shape (slack sagging), its bends no tighter than without the slack", abs(Lc - py_c["length"]) < 1e-3 and tight(py_c) >= tight(kernel_route(locked=False)) - 1,
          (Lc, py_c["length"], [round(b["r"], 2) for b in py_c["bends"]]))
    check("…not taut", not d.find_elements(By.CSS_SELECTOR, "#asmRight .hn-taut"))
    d.save_screenshot(f"{OUT}/harness_6b_slack.png")
    call("place_part", part="I3", x=400, y=10, z=10)
    time.sleep(0.6)
    short = kernel_route(locked=False)["length"] - locked
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

    # 10. the points list in the panel
    def rows_text():
        return [" ".join(e.text.split()) for e in d.find_elements(By.CSS_SELECTOR, "#asmRight .hn-pt .hn-pw")]

    def pts_n():
        return js(f"return {T}.get('H1').points.length")

    js(f"{T}.sel = 'H1'; {A}.sel = null; {A}.render(); {A}.draw()")
    time.sleep(0.4)
    rows = rows_text()
    check("10. the points list: every point with its part and face", len(rows) == 4 and "DPS I2 · F" in rows[0] and "Krabice I1 · F" in rows[2] and "Motor I3" in rows[3], rows)
    ActionChains(d).move_to_element(d.find_elements(By.CSS_SELECTOR, "#asmRight .hn-pt")[2]).perform()
    time.sleep(0.3)
    check("…a row under the mouse lights its point in the view", js(f"return {T}.hl") == 2)
    d.find_elements(By.CSS_SELECTOR, "#asmRight [data-pins]")[0].click()
    time.sleep(0.4)
    P = world_points()
    check("＋ between 1 and 2: a point in the middle, on the PCB too", pts_n() == 5 and math.dist(P[1], [(P[0][i] + P[2][i]) / 2 for i in range(3)]) < 0.01 and js(f"return {T}.get('H1').points[1].inst") == "I2", P[:3])
    el = d.find_element(By.CSS_SELECTOR, "#asmRight input[data-pxyz='1:0']")
    el.click()
    ActionChains(d).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).send_keys("33").send_keys(Keys.ENTER).perform()
    time.sleep(0.5)
    check("x typed: the point moves there (still on its part)", abs(world_points()[1][0] - 33) < 0.01 and js(f"return {T}.get('H1').points[1].inst") == "I2", world_points()[1])
    before = js(f"return JSON.stringify({T}.get('H1').points)")
    d.find_element(By.CSS_SELECTOR, "#asmRight [data-pmove='1:1']").click()
    time.sleep(0.4)
    swapped = json.loads(js(f"return JSON.stringify({T}.get('H1').points)"))
    check("↓ moves it later", swapped[2] == json.loads(before)[1] and swapped[1] == json.loads(before)[2])
    d.find_element(By.CSS_SELECTOR, "#asmRight [data-pmove='2:-1']").click()
    time.sleep(0.4)
    check("↑ back", js(f"return JSON.stringify({T}.get('H1').points)") == before)
    d.find_element(By.CSS_SELECTOR, "#asmRight [data-pdel='1']").click()
    time.sleep(0.4)
    check("✕ deletes it", pts_n() == 4)
    d.find_element(By.CSS_SELECTOR, "#asmRight [data-hx=clearPts]").click()
    time.sleep(0.4)
    check("🗑 all points: none left, clicking new ones", pts_n() == 0 and js(f"return {T}.edit") == "H1")
    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    time.sleep(0.6)
    check("…Ctrl+Z brings them back", pts_n() == 4, pts_n())
    js(f"{T}.finish()")  # (✓ Done)
    time.sleep(0.3)

    # 10b. the length label stays as it is on ✎ Upravit body (no next point until the mouse is over the view)
    js(f"{T}.sel = 'H1'; {A}.render(); {A}.draw()")
    time.sleep(0.3)
    was_len = d.find_element(By.CSS_SELECTOR, "#asmRight .hn-len").text
    d.find_element(By.CSS_SELECTOR, "[data-hx=edit]").click()  # (✎ in the view's corner)
    time.sleep(0.4)
    check("✎ Upravit body: the length label as it was", d.find_element(By.CSS_SELECTOR, "#asmRight .hn-len").text == was_len, (was_len, d.find_element(By.CSS_SELECTOR, "#asmRight .hn-len").text))

    # 11. a pin on the box: its top clicked 3 mm off the axis -> the point on its axis
    call("new_model", name="Cep")
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 12}}])
    call("add_feature", type="extrude", sketch="F1", d=20)
    call("open_part", id="Pohon")
    call("insert_part", part="Cep")
    call("place_part", part="I4", x=40, y=20, z=10)
    wait(f"return Object.values({A}.bodies).every(b => b.body) && {A}.view.meshes.length === 4")
    js(f"{A}.choose(null); {T}.editPoints('H1'); {A}.view.setView('iso')")
    time.sleep(0.8)
    lz = 30 + HM.bundle_d(4, 1.5) / 2 + 0.5
    click_at([43, 20, 30])
    pin = js(f"return {T}.get('H1').points.at(-1)")
    check("11. a pin's top clicked off its axis: the point on the axis", pts_n() == 5 and pin.get("inst") == "I4" and math.hypot(pin["at"][0], pin["at"][1]) < 1e-3 and pin.get("face"), pin)
    check("…in the world: over the axis, Ø/2 + 0.5 above the top", math.dist(world_points()[4], [40, 20, lz]) < 1e-3, world_points()[4])
    js(f"{A}.renderProps ? {A}.renderProps() : {A}.render()")
    time.sleep(0.3)
    d.find_element(By.CSS_SELECTOR, "#asmRight [data-pmove='4:-1']").click()  # (a middle point now: before the motor's)
    time.sleep(0.4)
    js(f"{T}.finish()")  # (✓ Done)
    time.sleep(0.3)
    check("…moved before the motor's point (a middle point)", js(f"return {T}.get('H1').points[3].inst") == "I4")
    call("place_part", part="I4", x=60, y=20, z=10)
    time.sleep(0.6)
    check("🔒 locked on the pin: the pin moved, the point with it (its matrix × its spot)", math.dist(world_points()[3], [60, 20, lz]) < 1e-3, world_points()[3])
    check("…the cable shaped through it again (length = harness.py's route)", abs(page_length() - kernel_route()["length"]) < 1e-3)
    js(f"{T}.sel = 'H1'; {A}.render(); {A}.draw()")
    time.sleep(0.3)
    d.find_element(By.CSS_SELECTOR, "#asmRight [data-plock='3']").click()
    time.sleep(0.4)
    check("🔓 unlocked: a point in space (remembering its part)", js(f"const p = {T}.get('H1').points[3]; return !p.inst && !!p.xyz && p.on?.inst === 'I4'"))
    call("place_part", part="I4", x=80, y=20, z=10)
    time.sleep(0.6)
    check("…the pin moved: the unlocked point stays put", math.dist(world_points()[3], [60, 20, lz]) < 1e-3, world_points()[3])
    js(f"{T}.sel = 'H1'; {A}.render(); {A}.draw()")
    time.sleep(0.3)
    d.find_element(By.CSS_SELECTOR, "#asmRight [data-plock='3']").click()
    time.sleep(0.4)
    call("place_part", part="I4", x=90, y=20, z=10)
    time.sleep(0.6)
    check("🔒 again: stuck to the pin where it was, it follows from there (+10 mm)", math.dist(world_points()[3], [70, 20, lz]) < 1e-3, world_points()[3])
    call("place_part", part="I4", x=40, y=20, z=10)
    time.sleep(0.5)

    # 12. a point dragged onto the pin's top (off its axis): on the axis
    js(f"{T}.editPoints('H1')")
    time.sleep(0.4)
    p2 = world_points()[2]
    cv = d.find_element(By.CSS_SELECTOR, "#asmViewport canvas")
    ActionChains(d, duration=60).move_to_element_with_offset(cv, *offset(p2)).click_and_hold().move_by_offset(10, 0).move_to_element_with_offset(cv, *offset([38, 21, 30])).release().perform()
    time.sleep(0.6)
    q = js(f"return {T}.get('H1').points[2]")
    check("12. a point dragged onto the pin's top: on its axis", q.get("inst") == "I4" and math.hypot(q["at"][0], q["at"][1]) < 1e-3, q)
    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    time.sleep(0.5)

    # 13. Alt + click on the box's top: the face behind it — its bottom (hidden), the cable outside, below it
    n0 = pts_n()
    spot = next(s for s in ([120, 80, 10], [100, 90, 10], [150, 90, 10], [20, 10, 10], [80, 5, 10], [150, 60, 10]) if js(f"""
      const v = {A}.view, V = v.camera.position.constructor, [sx, sy] = v.toScreen(new V(...arguments[0])), h = v.ray(sx, sy).intersectObjects(v.meshes, false);
      return document.elementFromPoint(sx, sy) === v.renderer.domElement && h.length >= 2 && h[0].object.userData.inst === 'I1' && Math.abs(h[0].point.z - 10) < 1e-3 && h[1].object.userData.inst === 'I1' && Math.abs(h[1].point.z) < 1e-3;""", s))
    cv = d.find_element(By.CSS_SELECTOR, "#asmViewport canvas")
    ActionChains(d, duration=30).move_to_element_with_offset(cv, *offset(spot)).perform()
    time.sleep(0.3)
    ActionChains(d).key_down(Keys.ALT).click().key_up(Keys.ALT).perform()
    time.sleep(0.5)
    b = world_points()[-1]
    check("13. Alt + click: the box's bottom, the cable under it", pts_n() == n0 + 1 and js(f"return {T}.get('H1').points.at(-1).inst") == "I1" and abs(b[2] - (0 - HM.bundle_d(4, 1.5) / 2 - 0.5)) < 1e-3, b)
    d.find_element(By.CSS_SELECTOR, "[data-hx=undoPt]").click()
    time.sleep(0.4)

    # 14. ◎ the point to its face's centre (the box's top)
    click_at(spot)
    rows = table()
    check("14. ◎ Bod do středu této plochy / díry offered", any("Bod do středu této plochy" in r for r in rows), rows)
    js("for (const b of document.querySelectorAll('#asmViewport .view-suggest .vs-list button')) if (b.textContent.includes('Bod do středu')) { b.click(); break; }")
    time.sleep(0.5)
    check("…the point at the top's centre", js(f"return {T}.get('H1').points.at(-1).at") == [80, 50, 10], js(f"return {T}.get('H1').points.at(-1)"))
    d.find_element(By.CSS_SELECTOR, "[data-hx=undoPt]").click()
    time.sleep(0.3)
    js(f"{T}.finish()")  # (✓ Done)
    time.sleep(0.6)

    # 15. where it goes through a part: the part, the span and the spot, a ⚠ there in the view
    hs = json.loads(call("get_assembly"))["harnesses"][0]
    check("15. point_list: each point with its part, lock and face", [p.get("locked") for p in hs["point_list"]] == [True] * 5 and hs["point_list"][3]["part"] == "I4" and all(p.get("face") for p in hs["point_list"]), hs["point_list"])
    call("add_harness", type="cable", d=4, points=[{"xyz": [-20, 50, 5]}, {"xyz": [80, 50, 5]}])  # (its end inside the box: it cannot get clear)
    js(f"{T}.checkThrough()")
    time.sleep(0.6)
    h2 = json.loads(call("get_assembly"))["harnesses"][1]
    check("…through_at: the box, span 1–2, a spot inside it", [(c["part"], c["span"]) for c in h2.get("through_at") or []] == [("I1", "1–2")] and 0 <= h2["through_at"][0]["xyz"][0] <= 80, h2.get("through_at"))
    check("…a ⚠ at the spot in the view: kabel koliduje s Krabice I1", any("kabel koliduje s Krabice I1" in e.text for e in d.find_elements(By.CSS_SELECTOR, "#asmViewport .hn-clash")), [e.text for e in d.find_elements(By.CSS_SELECTOR, "#asmViewport .hn-clash")])
    check("…the panel names the span", "úsek 1–2" in d.find_element(By.CSS_SELECTOR, "#asmRight .hn-thr").text, d.find_element(By.CSS_SELECTOR, "#asmRight .hn-thr").text)
    d.save_screenshot(f"{OUT}/harness_7_points.png")
    call("edit_harness", id="H2", remove=True)

    # 16. a point in space lying on a face (as an older file's): taken as locked on that part
    r = call("add_harness", type="cable", d=6, points=[{"xyz": [150, 90, 10 + 3.5]}, {"xyz": [150, 90, 60]}])
    js(f"{A}.draw()")
    time.sleep(0.4)
    check("16. a point in space on the box's top: locked on it, the other stays free", js(f"return {T}.get('H2').points.map(p => p.inst || 'free')") == ["I1", "free"], js(f"return {T}.get('H2').points"))
    r = call("edit_harness", id="H2", unlock_points=[1])
    check("edit_harness unlock_points: in space", js(f"return !{T}.get('H2').points[0].inst"), r[:100])
    r = call("edit_harness", id="H2", lock_points=[1])
    check("edit_harness lock_points: on its part again", js(f"return {T}.get('H2').points[0].inst") == "I1", r[:100])
    call("edit_harness", id="H2", unlock_points=[1])

    # 18. ➰ a span's own length: a cable from the pin's top to the box's top and up; its first span chosen,
    # "Smyčka / volná délka" in the suggestions, its length typed (40 mm more): a loop of slack that long; the pin
    # moved: the span keeps it; moved too far: that span taut
    def span_len(hid, k):
        return js(f"const h = {T}.get(arguments[0]); return window.__hn.routeAt(window.__app.assembly, h).spans[arguments[1]]", hid, k)

    js(f"{T}.finish(false)")
    r = call("add_harness", type="cable", d=4, r_min=10, points=[{"part": "I4", "face": "F2:end"}, {"part": "I1", "face": "F2:end"}, {"xyz": [80, 50, 60]}])
    hid = r.split(" ")[0]
    js(f"{T}.sel = arguments[0]; {T}.span = 0; {A}.sel = null; {A}.render(); {A}.draw()", hid)
    time.sleep(0.4)
    rows = table()
    check("18. a span chosen: ➰ Smyčka / volná délka offered", any("Smyčka / volná délka" in r for r in rows), rows)
    js("for (const b of document.querySelectorAll('#asmViewport .view-suggest .vs-list button')) if (b.textContent.includes('Smyčka')) { b.click(); break; }")
    time.sleep(0.4)
    inp = d.find_element(By.CSS_SELECTOR, "#asmRight input[data-slen='0']")
    L0 = span_len(hid, 0)
    check("…one input: the span's length, as it is now", abs(float(inp.get_attribute("value")) - L0) < 0.06, (inp.get_attribute("value"), L0))
    want_span = round(L0 + 40, 1)
    ActionChains(d).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).send_keys(str(want_span)).send_keys(Keys.ENTER).perform()
    time.sleep(0.6)
    check("…typed 40 mm more: the span that long (± 0.5), a loop of slack", js(f"return {T}.get(arguments[0]).spans", hid) == [{"from": 0, "length": want_span}] and abs(span_len(hid, 0) - want_span) <= 0.5,
          (js(f"return {T}.get(arguments[0]).spans", hid), span_len(hid, 0)))
    py_sp = kernel_route(hid)
    check("…as harness.py's shape, every bend ≥ R", abs(py_sp["length"] - page_length(hid)) < 1e-3 and all(b["ok"] for b in py_sp["bends"]), [round(b["r"], 2) for b in py_sp["bends"]])
    d.save_screenshot(f"{OUT}/harness_8_loop.png")
    call("place_part", part="I4", x=55, y=20, z=10)
    time.sleep(0.6)
    check("the pin moved: the span keeps its length", abs(span_len(hid, 0) - want_span) <= 0.5, span_len(hid, 0))
    call("place_part", part="I4", x=-250, y=20, z=10)
    time.sleep(0.6)
    js(f"{T}.sel = arguments[0]; {A}.render(); {A}.draw()", hid)
    time.sleep(0.4)
    tt = [e.text for e in d.find_elements(By.CSS_SELECTOR, "#asmRight .hn-taut")]
    check("…moved too far: that span taut, with how much it is short", any("Úsek 1–2 je napnutý — krátký o" in x for x in tt), tt)
    call("place_part", part="I4", x=40, y=20, z=10)
    time.sleep(0.4)
    r = call("edit_harness", id=hid, spans=[{"from": 1, "length": None}])
    check("edit_harness spans length null: no length of its own", not js(f"return {T}.get(arguments[0]).spans", hid), r[:120])
    r = call("edit_harness", id=hid, spans=[{"from": 2, "length": 120}])
    check("edit_harness spans: set, listed", '"spans":[{"from":2,"to":3' in r, r[-260:])

    # 19. the owner's case: a cable from one pin's top to another's, a tall block between them — its ends leave the
    # tops straight up (the bundle never in the pins), the span goes round the block (a detour), nothing hit
    call("new_model", name="Blok")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 20, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=150)
    call("open_part", id="Pohon")
    call("insert_part", part="Cep")
    call("insert_part", part="Blok")
    ids = [x["id"] for x in json.loads(call("get_assembly"))["parts"]][-2:]
    call("place_part", part=ids[0], x=100, y=85, z=10)
    call("place_part", part=ids[1], x=55, y=35, z=10)
    call("place_part", part="I4", x=40, y=20, z=10)
    wait(f"return Object.values({A}.bodies).every(b => b.body) && {A}.view.meshes.length === 6")
    r = call("add_harness", type="cable", d=6, points=[{"part": "I4", "face": "F2:end"}, {"part": ids[0], "face": "F2:end"}])
    hid = r.split(" ")[0]
    time.sleep(1.5)
    js(f"{T}.sel = arguments[0]; {A}.render(); {A}.draw()", hid)
    time.sleep(1.0)
    st = js(f"return window.__hn.harnessStep(window.__app.assembly.doc, {T}.get(arguments[0]))", hid)
    P = st["points"]
    lift6 = 30 + 3 + 0.5
    check("19. the ends leave the pins' tops straight up (a lead)", math.dist(P[0], [40, 20, lift6]) < 1e-3 and abs(P[1][0] - 40) < 1e-3 and abs(P[1][1] - 20) < 1e-3 and P[1][2] > lift6 + 30
          and abs(P[-2][0] - 100) < 1e-3 and abs(P[-2][1] - 85) < 1e-3 and P[-2][2] > lift6 + 30, P)

    def sd_box(q, lo, hi):
        c, e = [(x + y) / 2 for x, y in zip(lo, hi)], [(y - x) / 2 for x, y in zip(lo, hi)]
        u = [abs(q[i] - c[i]) - e[i] for i in range(3)]
        return min(max(u), 0.0) + math.sqrt(sum(max(x, 0.0) ** 2 for x in u))

    def sd_pin(q, cx, cy):
        u = (math.hypot(q[0] - cx, q[1] - cy) - 6, abs(q[2] - 20) - 10)
        return min(max(u), 0.0) + math.hypot(max(u[0], 0.0), max(u[1], 0.0))

    def worst(route):
        sm = HM.samples(route, 0.5)
        return min(min(sd_box(q, [55, 35, 10], [75, 55, 160]), sd_pin(q, 40, 20), sd_pin(q, 100, 85), sd_box(q, [0, 0, 0], [160, 100, 10])) for q in sm)

    plain = HM.shape([P[0], P[1], P[-2], P[-1]], st["r_min"])
    check("…straight, it would go through the block", worst(plain) < 0, round(worst(plain), 2))
    kr = kernel_route(hid)
    check("…it goes round the block: a detour, the whole bundle clear of every body (≥ Ø/2)", len(P) > 4 and worst(kr) >= 3 - 1e-3 and all(b["ok"] for b in kr["bends"]), (len(P), round(worst(kr), 2)))
    f = json.loads(call("get_assembly"))["harnesses"][-1]
    check("…get_assembly: nothing hit, the detour told", not f.get("still_hits") and not f.get("through_parts") and f.get("detour_points", 0) >= 1, {k: f.get(k) for k in ("still_hits", "through_parts", "detour_points")})
    check("…no ⚠ marker on it in the view", js(f"return {T}.built.get(arguments[0]).objs.filter(o => o.isCSS2DObject && o.element.textContent.includes('koliduje')).length", hid) == 0)
    d.save_screenshot(f"{OUT}/harness_9_avoid.png")
    call("edit_harness", id=hid, remove=True)

    # 20. 📎 a clip on a point on the PCB's top (the suggestion, snuggest first): placed, the point on its axis; the
    # point taken away -> "the clip stays" with ✕ Remove it too; ⛓ a span through an energy chain put in from the
    # library: the cable runs its path, its length with it; the chain's moving end moved: the cable follows, undo back
    wait("return window.__hn && import('/js/library/cableparts.js').then(m => (window.__cp = m, m.clipsFor(6).length > 0 && m.chainsFor(6, 30).length > 0))", 60)
    r = call("add_harness", type="cable", d=6, points=[{"xyz": [-40, 70, 40]}, {"part": "I2", "face": "F2:end"}, {"xyz": [40, 140, 45]}])
    hid = r.split(" ")[0]
    js(f"{T}.sel = arguments[0]; {T}.pt = 1; {T}.span = null; {A}.sel = null; {A}.render(); {A}.draw()", hid)
    time.sleep(0.5)
    rows = table()
    clips = [x for x in rows if "Příchytka sem" in x]
    check("20. a point on a face chosen: 📎 Příchytka sem, the snuggest first (2–3 in the table)", 1 <= len(clips) <= 3 and js("return window.__cp.clipsFor(6)[0].label") in clips[0], rows)
    # 📎 the preview: the mouse on a clip's row -> its ghost where it would go (the point on its axis, along the cable),
    # a label (name, Ø, mounting); off the row -> gone
    def ghost():
        return js(f"""const g = {A}.view.scene.getObjectByName('clipGhost'), s = {T}.clips.shown;
          return {{ n: g ? g.children.filter(o => !o.isCSS2DObject).length : 0, s, label: g ? (g.children.find(o => o.isCSS2DObject)?.element.textContent || '') : '' }};""")

    def cable_dir():
        """The cable's way at point 2 laid onto its face (as a clip takes it), and the point (world)."""
        return js(f"""const h = {T}.get('{hid}'), P = h.points.map(p => window.__hnPoint(h, p)), n = {T}.clipPose(h, 1).n;
          const d = P[2].clone().sub(P[0]); d.sub(n.clone().multiplyScalar(d.dot(n))).normalize(); return [d.toArray(), P[1].toArray(), n.toArray()];""")
    row = next(b for b in d.find_elements(By.CSS_SELECTOR, "#asmViewport .view-suggest .vs-list button") if "Příchytka sem" in b.text)
    ActionChains(d, duration=50).move_to_element(row).perform()
    g = None
    end = time.time() + 30
    while time.time() < end and not (g := ghost())["s"]:
        time.sleep(0.1)
    cd, p1, nrm = cable_dir()
    along = abs(sum(a * b for a, b in zip(g["s"]["axis"]["d"], cd))) if g and g["s"] else 0
    on_face = abs(sum((a - b) * c for a, b, c in zip(g["s"]["matrix"][12:15], p1, nrm))) if g and g["s"] else 99  # (its mount point: the point's spot on the face)
    near = math.dist(g["s"]["axis"]["o"], p1) if g and g["s"] else 99
    ghost_m = g["s"]["matrix"] if g and g["s"] else None
    check("20a. the mouse on 📎 Příchytka sem: a ghost of that clip at the point, along the cable", g and g["n"] >= 1 and along > 0.999 and near < 15 and abs(on_face - 3.5) < 1e-3 and g["s"]["key"] == "ht-hp-pclamp|H3P", [g, along, near, on_face])
    check("…its label: the name, the cable Ø and the mounting", g and "H3P" in g["label"] and "Ø" in g["label"] and "šroub M4" in g["label"], g and g["label"])
    d.save_screenshot(f"{OUT}/harness_12_clip_ghost.png")
    ActionChains(d, duration=50).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, "#asmViewport canvas"), 300, -300).perform()
    time.sleep(0.4)
    g = ghost()
    check("…the mouse off the row: the ghost gone", g["n"] == 0 and not g["s"], g)
    # ⋯ Vybrat ze seznamu…: grouped, the fitting ones first, the too small ones greyed with why; a row previews, a click puts it
    js("for (const b of document.querySelectorAll('#asmViewport .view-suggest .vs-list button')) if (b.textContent.includes('Vybrat ze seznamu')) { b.click(); break; }")
    box = wait("return document.querySelector('#asmViewport .hn-clips')", 10)
    lst = js("""return [...document.querySelectorAll('#asmViewport .hn-clips .hnc-list > *')].map(e => e.classList.contains('hnc-sec') ? ['sec', e.textContent]
      : ['row', e.querySelector('.hnc-n').textContent.trim(), e.classList.contains('off'), e.querySelector('.hnc-m').textContent])""")
    secs = [x[1] for x in lst if x[0] == "sec"]
    groups, cur = {}, None
    for x in lst:
        if x[0] == "sec":
            cur = x[1]
            groups[cur] = []
        else:
            groups[cur].append(x)
    first_ok = all(not any(not a[2] for a in g_[k + 1:] if b[2]) for g_ in groups.values() for k, b in enumerate(g_))
    h1p = next((x for x in lst if x[0] == "row" and x[1].startswith("H1P")), None)
    check("20b. ⋯ Vybrat ze seznamu: grouped (P-příchytky, podložky, pásky), the fitting ones first", secs == ["P-příchytky", "Podložky pro pásky", "Stahovací pásky"] and first_ok
          and groups["P-příchytky"][0][1].startswith("H3P") and not groups["P-příchytky"][0][2], lst)
    check("…the too small ones greyed: “Ø 3,2 max — malá”", h1p and h1p[2] and "Ø 3,2 max — malá" in h1p[3], h1p)
    mb = d.find_element(By.XPATH, "//div[contains(@class,'hn-clips')]//button[contains(@class,'hnc-row')][.//span[@class='hnc-n' and starts-with(normalize-space(.),'MB3A')]]")
    ActionChains(d, duration=50).move_to_element(mb).perform()
    wait(f"return {T}.clips.shown?.key === 'ht-mb-mount|MB3A'", 30)
    check("…a list row pointed at: its ghost", ghost()["n"] >= 1)
    d.save_screenshot(f"{OUT}/harness_13_clip_list.png")
    off = d.find_element(By.XPATH, "//div[contains(@class,'hn-clips')]//button[contains(@class,'off')][.//span[@class='hnc-n' and starts-with(normalize-space(.),'H1P')]]")
    ActionChains(d, duration=50).move_to_element(off).click().perform()
    time.sleep(0.4)
    check("…a greyed row: no ghost, a click puts nothing in", not js(f"return {T}.get('{hid}').points[1].clip") and not js(f"return {T}.clips.shown") and js("return !!document.querySelector('#asmViewport .hn-clips')"))
    h3p = d.find_element(By.XPATH, "//div[contains(@class,'hn-clips')]//button[contains(@class,'hnc-row')][.//span[@class='hnc-n' and starts-with(normalize-space(.),'H3P')]]")
    ActionChains(d, duration=50).move_to_element(h3p).click().perform()
    cid = wait(f"return {T}.get('{hid}').points[1].clip", 30)
    time.sleep(0.5)
    placed = js(f"return {A}.inst('{cid}').matrix")
    check("…put exactly where its ghost was", ghost_m and max(abs(a - b) for a, b in zip(placed, ghost_m)) < 1e-6, [placed, ghost_m])
    check("…a list row clicked: that clip put in, the list and the ghost gone", js(f"return window.__app.project.parts.find(q => q.id === {A}.inst('{cid}').part).data.library.size") == "H3P"
          and not js("return document.querySelector('#asmViewport .hn-clips')") and ghost()["n"] == 0)
    on_axis = js(f"""const a = {A}, h = {T}.get('{hid}'), p = h.points[1], it = a.inst(p.clip), lib = window.__app.project.parts.find(q => q.id === it.part).data.library;
      const item = window.__cp.clipsFor(6).find(c => c.item.id === lib.id).item, f = window.__cp.clipFrames(item, lib.size, window.__hn.outerD(h));
      const V = a.view.camera.position.constructor, M = new (a.view.camera.matrix.constructor)().fromArray(it.matrix), o = new V(...f.axis.o).applyMatrix4(M);
      return [window.__hnPoint(h, p).distanceTo(o), lib.id, lib.size];""")
    check("…the clip placed, the point on its axis (locked to it)", cid and on_axis[0] < 1e-3, [cid, on_axis])
    check("…🔗 fixed to the PCB it was put on", js(f"return {A}.doc.mates.some(m => m.type === 'rigid' && m.move === '{cid}' && m.onto === 'I2')"), js(f"return {A}.doc.mates"))
    lst = [e.text for e in d.find_elements(By.CSS_SELECTOR, "#asmRight .hn-pt .hn-pw")]
    check("…the list shows 📎 and the clip's part", lst and "📎" in lst[1] and cid in lst[1], lst)
    f = json.loads(call("get_assembly"))["harnesses"][-1]
    check("…get_assembly: point 2 clip", f["point_list"][1].get("clip") == cid, f["point_list"][1])
    # 🔁 swapped from the point's 📎 in the panel: the same list, the clip there ✓; another clicked -> the point kept, the
    # clip replaced (the old one out), one undo step; undo -> the old one back
    n_pts, n_undo = js(f"return {T}.get('{hid}').points.length"), js(f"return {A}.history.undo.length")
    d.find_element(By.CSS_SELECTOR, "#asmRight [data-pclip='1']").click()
    wait("return document.querySelector('#asmViewport .hn-clips')", 10)
    head = js("return document.querySelector('#asmViewport .hn-clips .hnc-head b').textContent + ' | ' + (document.querySelector('#asmViewport .hn-clips .hnc-row.on')?.textContent || '')")
    check("20c. the point's 📎 in the panel: “Vyměnit příchytku”, the clip there ✓", "Vyměnit příchytku" in head and "H3P" in head.split("|")[1], head)
    mb = d.find_element(By.XPATH, "//div[contains(@class,'hn-clips')]//button[contains(@class,'hnc-row')][.//span[@class='hnc-n' and starts-with(normalize-space(.),'MB3A')]]")
    ActionChains(d, duration=50).move_to_element(mb).click().perform()
    wait(f"return {T}.get('{hid}').points[1].clip !== '{cid}'", 30)
    time.sleep(0.5)
    nid = js(f"return {T}.get('{hid}').points[1].clip")
    gap = js(f"""const a = {A}, h = {T}.get('{hid}'), p = h.points[1], it = a.inst(p.clip), lib = window.__app.project.parts.find(q => q.id === it.part).data.library;
      const f = window.__cp.clipFrames(window.__cp.clipChoices(6).find(c => c.item.id === lib.id).item, lib.size, 6);
      const V = a.view.camera.position.constructor, M = new (a.view.camera.matrix.constructor)().fromArray(it.matrix);
      return [window.__hnPoint(h, p).distanceTo(new V(...f.axis.o).applyMatrix4(M)), lib.size];""")
    check("…swapped: the point kept (on the MB3A's axis), the H3P out, one undo step", nid and js(f"return {T}.get('{hid}').points.length") == n_pts and gap[1] == "MB3A" and gap[0] < 1e-3
          and not js(f"return !!{A}.inst('{cid}')") and js(f"return {A}.history.undo.length") == n_undo + 1, [nid, gap, js(f"return {A}.history.undo.length"), n_undo])
    js(f"{A}.history.go(-1)")
    time.sleep(0.6)
    check("…undo: the H3P back on the point, the MB3A gone", js(f"const h = {T}.get('{hid}'); return h.points[1].clip === '{cid}' && !!{A}.inst('{cid}') && !{A}.inst('{nid}')"))
    d.find_element(By.CSS_SELECTOR, "#asmRight [data-pdel='1']").click()
    time.sleep(0.5)
    orphan = d.find_elements(By.CSS_SELECTOR, "#asmRight .hn-orphan")
    check("the point deleted: “the clip stays” with ✕ Remove it too", orphan and "zůstala" in orphan[0].text and js(f"return !!{A}.inst('{cid}')"), [e.text for e in orphan])
    orphan[0].find_element(By.CSS_SELECTOR, "[data-rmclip]").click()
    time.sleep(0.5)
    check("…removed: the clip is out of the assembly", not js(f"return !!{A}.inst('{cid}')"))
    for _ in range(2):
        js(f"{A}.history.go(-1)")
        time.sleep(0.5)
    check("undo ×2: the clip and the point on it back", js(f"const h = {T}.get('{hid}'); return h.points.length === 3 && h.points[1].clip === '{cid}' && !!{A}.inst('{cid}')"))
    # ⛓ span 1–2 chosen: Vést energetickým řetězem (one from the library, sized for Ø6 at R ≥ r_min)
    js(f"{T}.sel = '{hid}'; {T}.pt = null; {T}.span = 0; {A}.sel = null; {A}.render(); {A}.draw()")
    time.sleep(0.5)
    rows = table()
    check("a span chosen: ⛓ Vést energetickým řetězem offered", any("Vést energetickým řetězem" in x for x in rows), rows)
    L_before = page_length(hid)
    js("for (const b of document.querySelectorAll('#asmViewport .view-suggest .vs-list button')) if (b.textContent.includes('energetickým řetězem')) { b.click(); break; }")
    ch = wait(f"return {T}.get('{hid}').spans?.find(s => s.chain)?.chain", 60)
    wait(f"return Object.values({A}.bodies).every(b => b.body)", 60)
    time.sleep(1.0)
    path = js(f"return window.__hnChain('{ch}')")
    rt = js(f"const r = window.__hn.routeAt({A}, {T}.get('{hid}')); return {{ L: r.length, pts: r.points.map(p => p.toArray()) }}")
    on_path = all(min(math.dist(q, x) for x in rt["pts"]) < 1e-6 for q in path["points"])
    check("…a chain put in (C…), the cable runs along its path, its length with it", ch and on_path and rt["L"] > L_before + 50 and abs(page_length(hid) - kernel_route(hid)["length"]) < 1e-3,
          [ch, on_path, L_before, rt["L"]])
    sp = js(f"return window.__hn.routeAt({A}, {T}.get('{hid}')).spans")
    check("…its spans told right (each > 0, together its length)", len(sp) == 2 and min(sp) > 1 and abs(sum(sp) - rt["L"]) < 1e-3, sp)
    dims = js(f"return {A}.doc.chains.find(c => c.id === '{ch}').dims")
    check("…sized for the bundle: opening ≥ Ø + 2, bend ≥ r_min, cables up to ≥ Ø", dims["Bi"] >= 8 and dims["R"] >= 30 and dims["dmax"] >= 6, dims)
    f = json.loads(call("get_assembly"))["harnesses"][-1]
    check("…get_assembly: the span's chain", any(x.get("chain") == ch for x in f.get("spans", [])), f.get("spans"))
    d.save_screenshot(f"{OUT}/harness_10_chain.png")
    L1, o1 = page_length(hid), path["moving"]
    js(f"const a = {A}, c = a.doc.chains.find(c => c.id === '{ch}'); c.travel = 80; a.commit();")
    time.sleep(1.0)
    path2 = js(f"return window.__hnChain('{ch}')")
    rt2 = js(f"const r = window.__hn.routeAt({A}, {T}.get('{hid}')); return {{ L: r.length, pts: r.points.map(p => p.toArray()) }}")
    follows = all(min(math.dist(q, x) for x in rt2["pts"]) < 1e-6 for q in path2["points"])
    check("the chain's moving end moved 80: the cable follows it, its length updated", math.dist(path2["moving"], o1) > 70 and follows and abs(rt2["L"] - L1) > 1 and abs(page_length(hid) - kernel_route(hid)["length"]) < 1e-3,
          [o1, path2["moving"], L1, rt2["L"]])
    d.save_screenshot(f"{OUT}/harness_11_chain_moved.png")
    js(f"{A}.history.go(-1)")
    time.sleep(0.8)
    check("undo: the chain's end back, the cable's length with it", abs(page_length(hid) - L1) < 1e-3, [page_length(hid), L1])
    r = call("edit_harness", id=hid, chain={"span": 1, "id": None})
    check("edit_harness chain id null: not through it any more", not js(f"return {T}.get('{hid}').spans?.some(s => s.chain)"), r[:100])
    r = call("edit_harness", id=hid, chain={"span": 1, "id": ch})
    check("edit_harness chain {span, id}: through it again", js(f"return {T}.get('{hid}').spans?.[0]?.chain") == ch, r[:100])

    # 21. 📎 a clip on a moving part (edit_harness clip on the motor's top): 🔗 fixed to it, one undo step; the motor
    # moved: the clip goes with it, the point stays on its axis; the clip deleted: its joint goes too, undo: both back
    r = call("add_harness", type="cable", d=6, points=[{"xyz": [100, -60, 60]}, {"part": "I3", "face": "F2:end"}, {"xyz": [220, 60, 70]}])
    hm = r.split(" ")[0]
    n_undo = js(f"return {A}.history.undo.length")
    call("edit_harness", id=hm, clip={"point": 2})
    mc = js(f"return {T}.get('{hm}').points[1].clip")
    rig = js(f"return ({A}.doc.mates || []).filter(m => m.move === '{mc}').map(m => [m.type, m.onto])")
    check("21. edit_harness clip on the motor: the clip 🔗 fixed to the motor (I3)", mc and rig == [["rigid", "I3"]], [mc, rig])
    check("…one undo step (the clip put in, joined, the point on it)", js(f"return {A}.history.undo.length") == n_undo + 1, [n_undo, js(f"return {A}.history.undo.length")])

    def axis_gap():
        """How far the clip's harness point is off the clip's axis (world)."""
        return js(f"""const a = {A}, h = {T}.get('{hm}'), p = h.points[1], it = a.inst(p.clip), lib = window.__app.project.parts.find(q => q.id === it.part).data.library;
          const item = window.__cp.clipsFor(6).find(c => c.item.id === lib.id).item, f = window.__cp.clipFrames(item, lib.size, 6);
          const M = new (a.view.camera.matrix.constructor)().fromArray(it.matrix), V = a.view.camera.position.constructor;
          const o = new V(...f.axis.o).applyMatrix4(M), dd = new V(...f.axis.d).transformDirection(M), w = window.__hnPoint(h, p).sub(o);
          return w.sub(dd.multiplyScalar(w.dot(dd))).length();""")

    c0, m0 = js(f"return {A}.inst('{mc}').matrix.slice(12, 15)"), js(f"return {A}.inst('I3').matrix.slice(12, 15)")
    call("place_part", part="I3", x=m0[0] + 25)
    time.sleep(0.6)
    c1 = js(f"return {A}.inst('{mc}').matrix.slice(12, 15)")
    check("…the motor moved 25 mm: the clip goes with it, the point stays on its axis", abs(c1[0] - c0[0] - 25) < 1e-6 and abs(c1[1] - c0[1]) < 1e-6 and axis_gap() < 1e-3, [c0, c1, axis_gap()])
    js(f"{A}.removeInst('{mc}')")
    time.sleep(0.5)
    check("the clip deleted: its joint goes too", not js(f"return !!{A}.inst('{mc}') || ({A}.doc.mates || []).some(m => m.move === '{mc}' || m.onto === '{mc}')"))
    js(f"{A}.history.go(-1)")
    time.sleep(0.6)
    check("…undo: the clip and its joint back", js(f"return !!{A}.inst('{mc}') && {A}.doc.mates.some(m => m.type === 'rigid' && m.move === '{mc}' && m.onto === 'I3')"))
    for _ in range(2):
        js(f"{A}.history.go(-1)")
        time.sleep(0.6)
    check("…undo again (the move, then the clip): the clip, its joint and the point's clip gone at once",
          js(f"return !{A}.inst('{mc}') && !({A}.doc.mates || []).some(m => m.move === '{mc}') && !{T}.get('{hm}').points[1].clip"))
    js(f"{A}.history.go(1)")
    time.sleep(0.6)
    check("…redo: all three back", js(f"return !!{A}.inst('{mc}') && {A}.doc.mates.some(m => m.move === '{mc}') && {T}.get('{hm}').points[1].clip === '{mc}'"))

    # 22. ⛓ a span keeps the end of the chain it enters: its first point above the lower run, 100 mm along — the
    # moving end is nearer it for some travels, the fixed end for others; it entered at the fixed end, it stays there
    # over the full travel (no flip); an older file (no `enter`): decided on load, kept
    rec = js(f"""const a = {A}, c = a.doc.chains.find(c => c.id === '{ch}'), r = window.__cp.travelRange({{ ...c.dims, links: c.links }});
      return {{ min: r.min, max: r.max, R: c.dims.R }};""")
    lo, hi = math.ceil(rec["min"]), math.floor(rec["max"])
    js(f"const c = {A}.doc.chains.find(c => c.id === '{ch}'); c.travel = arguments[0]; {A}.commit()", lo)
    time.sleep(0.5)
    fr = js(f"""const a = {A}, it = a.inst(a.doc.chains.find(c => c.id === '{ch}').part), M = new (a.view.camera.matrix.constructor)().fromArray(it.matrix), V = a.view.camera.position.constructor;
      return [new V(0, 0, 0).applyMatrix4(M).toArray(), new V(1, 0, 0).transformDirection(M).toArray(), new V(0, 0, 1).transformDirection(M).toArray()];""")
    Ap = [fr[0][i] + 100 * fr[1][i] + rec["R"] * fr[2][i] for i in range(3)]
    Bp = [fr[0][i] + 320 * fr[1][i] + (2 * rec["R"] + 60) * fr[2][i] for i in range(3)]
    hc = call("add_harness", type="cable", d=6, points=[{"xyz": Ap}, {"xyz": Bp}]).split(" ")[0]
    call("edit_harness", id=hc, chain={"span": 1, "id": ch})
    check("22. routed through the chain at its fixed end (the nearer one then): enter = fixed", js(f"return {T}.get('{hc}').spans[0].enter") == "fixed", js(f"return {T}.get('{hc}').spans"))

    def entry(end=0):
        """How far the route's first point after the span's first point is from the chain's end (0: fixed, -1: moving),
        and whether the moving end is nearer the span's first point now."""
        return js(f"""const a = {A}, h = {T}.get('{hc}'), r = window.__hn.routeAt(a, h), c = window.__hnChain('{ch}'), V = a.view.camera.position.constructor;
          const q = r.points[r.where[0] + 1], E = new V(...c.points.at(arguments[0])), F = new V(...c.points[0]), M = new V(...c.points.at(-1)), A = window.__hnPoint(h, h.points[0]);
          return [q.distanceTo(E), A.distanceTo(M) < A.distanceTo(F)];""", end)

    flips, nearer_moving = [], 0
    for k in range(9):
        tr = lo + (hi - lo) * k / 8
        js(f"const c = {A}.doc.chains.find(c => c.id === '{ch}'); c.travel = arguments[0]; {A}.draw()", tr)
        e = entry()
        nearer_moving += e[1]
        if e[0] > 1e-6:
            flips.append((tr, e[0]))
    check("…over the full travel (9 places) it enters at the fixed end, no flip — though the moving end came nearer its first point",
          not flips and nearer_moving > 0 and js(f"return {T}.get('{hc}').spans[0].enter") == "fixed", [flips, nearer_moving, lo, hi])
    js(f"const c = {A}.doc.chains.find(c => c.id === '{ch}'); c.travel = 100; {A}.commit()")
    old = js(f"const p = {A}.payload(); for (const h of p.harnesses) for (const s of h.spans || []) delete s.enter; return p;")
    js(f"return {A}.load(arguments[0])", old)
    wait(f"return Object.values({A}.bodies).every(b => b.body)", 60)
    time.sleep(0.8)
    check("…an older file (no enter): decided once on load (the moving end, nearer now), not an undo step",
          js(f"return {T}.get('{hc}').spans[0].enter") == "moving" and entry(-1)[0] < 1e-6 and not js(f"return {A}.history.canUndo()"), js(f"return {T}.get('{hc}').spans"))
    js(f"const c = {A}.doc.chains.find(c => c.id === '{ch}'); c.travel = arguments[0]; {A}.draw()", lo)
    e = entry(-1)
    check("…the chain moved far back (its fixed end nearer now): still in at the moving end", js(f"return {T}.get('{hc}').spans[0].enter") == "moving" and e[0] < 1e-6 and not e[1], e)

    # 23. a cable leaving a face with its next point too close for its straight lead-out: a quiet note there
    hl = call("add_harness", type="cable", d=6, points=[{"part": "I1", "face": "F2:end"}, {"xyz": [0, 0, 0]}]).split(" ")[0]
    p0 = js(f"const h = {T}.get('{hl}'); return window.__hnPoint(h, h.points[0]).toArray()")
    need = js(f"return window.__hn.leadOf({T}.get('{hl}'))")
    call("edit_harness", id=hl, points=[{"part": "I1", "face": "F2:end"}, {"xyz": [p0[0] + 8, p0[1], p0[2] + 6]}])
    js(f"{T}.sel = '{hl}'; {A}.render(); {A}.draw()")
    time.sleep(0.6)
    notes = [e.text for e in d.find_elements(By.CSS_SELECTOR, "#asmViewport .hn-note")]
    f = next(x for x in json.loads(call("get_assembly"))["harnesses"] if x["id"] == hl)
    check("23. the next point 10 mm from a face end: a quiet note “příliš blízko — kabel potřebuje rovný výstup X mm”",
          any(f"příliš blízko — kabel potřebuje rovný výstup {round(need)} mm" in n for n in notes) and f.get("too_close", [{}])[0].get("lead_mm") == round(need, 1), [notes, f.get("too_close"), need])
    d.save_screenshot(f"{OUT}/harness_12_lead_note.png")
    call("edit_harness", id=hl, points=[{"part": "I1", "face": "F2:end"}, {"xyz": [p0[0] + 8, p0[1], p0[2] + need + 30]}])
    time.sleep(0.6)
    f = next(x for x in json.loads(call("get_assembly"))["harnesses"] if x["id"] == hl)
    check("…far enough: no note", not [e for e in d.find_elements(By.CSS_SELECTOR, "#asmViewport .hn-note") if "příliš blízko" in e.text] and "too_close" not in f, f.get("too_close"))
    call("edit_harness", id=hl, remove=True)

    # 17. saved and reloaded: the locks kept
    keep = js(f"return JSON.stringify({T}.list().map(h => [h.points.map(p => [p.inst || null, !!p.on, p.face || null, p.clip || null]), h.spans || null]))")
    js("return window.__app.autosave.saveNow()")
    time.sleep(1)
    d.refresh()
    wait("return !!window.__app")
    wait("return document.querySelector('.restore-bar')", 15)
    d.find_element(By.CSS_SELECTOR, ".restore-bar [data-a=open]").click()
    time.sleep(2)
    call("open_part", id="Pohon")
    wait(f"return {A}.active && Object.values({A}.bodies).every(b => b.body)", 60)
    time.sleep(1)
    got = js(f"return JSON.stringify({T}.list().map(h => [h.points.map(p => [p.inst || null, !!p.on, p.face || null, p.clip || null]), h.spans || null]))")
    check("17. reloaded: every point's part, lock, face and clip, the spans' lengths and chains kept", json.loads(got) == json.loads(keep), (keep, got))
    js("""import('/js/assembly/harness.js').then((m) => { window.__hn = m; }); import('/js/assembly/chains.js').then((k) => { window.__hnChain = (id) => { const r = k.chainRoute(window.__app.assembly, id); return r && { points: r.points, moving: r.moving.o }; }; })""")
    wait("return !!window.__hnChain && !!window.__hn")
    again = js(f"""const a = {A}, h = a.harnessTool.list().find(x => x.spans?.some(s => s.chain)); if (!h) return null;
      const c = window.__hnChain(h.spans.find(s => s.chain).chain), r = window.__hn.routeAt(a, h).points.map(p => p.toArray());
      return c.points.every(q => r.some(x => Math.hypot(q[0] - x[0], q[1] - x[1], q[2] - x[2]) < 1e-6));""")
    check("…and the reloaded cable runs along its chain again", again is True, again)
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        fails.append("console errors")
    d.quit()
print(f"{'FAILED: ' + ', '.join(fails) if fails else 'ALL OK'}")
sys.exit(1 if fails else 0)
