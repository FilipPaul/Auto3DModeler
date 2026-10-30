"""👁 Hiding parts of an assembly, in headless Edge, in Czech, with real clicks, on the robot arm demo: the suggestions
for a chosen part always show "✎ Upravit díl zde" and "👁 Skrýt / zobrazit…" (also with only 3 rows) -> 👁 opens its
choices as rows (hovering Skrýt previews it) -> Skrýt: the part is not drawn, a click on its spot picks what is behind
it, its row in the tree struck through, "👁 1 skryté · Zobrazit vše" over the tree -> Zobrazit vše -> Zprůhlednit: its
material see-through (opacity < 1), a click there takes the part behind it -> Skrýt ostatní (izolovat): only it ->
Zobrazit vše over the tree -> 👁 in the tree hides / shows a part, Alt+click: see-through -> two parts (Ctrl+click):
both hidden -> H / Shift+H / Alt+H -> the mechanisms, the BOM and the collision check unchanged by it -> autosaved,
reloaded: still hidden -> the AI: set_visibility, get_assembly hidden / transparent, get_screenshot -> ✎ Upravit díl
zde opens the part in place -> no console errors.

  PYTHONIOENCODING=utf-8 py tools/e2e_hide_parts.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
A = "window.__app.assembly"
H = "window.__app.agentHandlers"
SG = "#asmViewport .view-suggest"
bad = []


def check(ok, what):
    print(("  ok   " if ok else "  FAIL ") + what)
    if not ok:
        bad.append(what)


def wait(script, t=90):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def call(t, **a):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", t, a)


def ready():
    wait(f"return window.__app.state.workspace === 'assembly' && {A}.doc.instances.length === 4 && {A}.doc.instances.every(i => {A}.bodies[i.part]?.body) && {A}.mech.list.length")
    time.sleep(0.8)


def labels():
    """The suggestion rows shown: their labels."""
    return [b.text.strip() for b in d.find_elements(By.CSS_SELECTOR, f"{SG} .vs-list button[data-sg]") if b.is_displayed()]


def sg_row(label):
    return next(b for b in d.find_elements(By.CSS_SELECTOR, f"{SG} .vs-list button[data-sg]") if label in b.text)


def shown_ids():
    return js(f"return {A}.view.meshes.filter(m => m.visible).map(m => m.userData.inst).sort()")


def display():
    return js(f"return {A}.doc.display || {{}}")


def spot(inst, behind=True):
    """A spot of the view (x, y from the canvas's middle) where `inst` is the first part under the mouse — with another
    part behind it when there is one such spot (behind)."""
    return js(f"""const a = {A}, v = a.view, cv = v.renderer.domElement, r = cv.getBoundingClientRect(), out = [];
      for (let fx = 0.04; fx < 0.96; fx += 0.02) for (let fy = 0.06; fy < 0.94; fy += 0.02) {{
        const x = r.left + fx * r.width, y = r.top + fy * r.height;
        if (document.elementFromPoint(x, y) !== cv) continue;
        const hits = v.ray(x, y).intersectObjects(v.meshes, false);
        if (hits[0]?.object.userData.inst !== arguments[0]) continue;
        const next = hits.find(h => h.object.userData.inst !== arguments[0]);
        out.push([x - r.left - r.width / 2, y - r.top - r.height / 2, next ? next.object.userData.inst : null]);
      }}
      const b = out.find(o => o[2]);
      return (arguments[1] && b) || out[Math.floor(out.length / 2)] || null""", inst, behind)


def click_view(x, y, ctrl=False):
    cv = js(f"return {A}.view.renderer.domElement")
    act = ActionChains(d).move_to_element_with_offset(cv, int(x), int(y))
    if ctrl:
        act = act.key_down(Keys.CONTROL).click().key_up(Keys.CONTROL)
    else:
        act = act.click()
    act.perform()
    time.sleep(0.5)


def tree_row(inst):
    return d.find_element(By.CSS_SELECTOR, f"#asmLeft .as-list .mt-item[data-inst='{inst}']")


def choose_in_tree(inst, ctrl=False):
    r = tree_row(inst).find_element(By.CSS_SELECTOR, ".mt-name")
    if ctrl:
        ActionChains(d).key_down(Keys.CONTROL).click(r).key_up(Keys.CONTROL).perform()
    else:
        r.click()
    time.sleep(0.4)


def open_eye_rows():
    if not any("Skrýt ostatní" in x for x in labels()):
        sg_row("Skrýt / zobrazit…").click()
        time.sleep(0.4)


def key(k, mod=None):
    body = d.find_element(By.TAG_NAME, "body")
    act = ActionChains(d)
    if mod:
        act = act.key_down(mod).send_keys(k).key_up(mod)
    else:
        act = act.send_keys(k)
    act.perform()
    time.sleep(0.4)


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('a3d.leftDock'); localStorage.setItem('auto3d-lang', 'cs')")
    d.get(URL)
    wait("return !!window.__app")
    # the robot arm demo
    d.find_element(By.ID, "openBtn").click()
    time.sleep(0.2)
    js("document.getElementById('demoBtn').click()")
    wait("return document.querySelectorAll('.demos [data-demo]').length")
    row = next(r for r in d.find_elements(By.CSS_SELECTOR, ".demos [data-demo]") if "robot" in r.get_attribute("data-demo"))
    row.find_element(By.CSS_SELECTOR, "[data-open]").click()
    ready()
    js(f"{A}.view.setView('iso')")
    time.sleep(0.5)
    mech0 = json.loads(call("get_assembly"))["mechanisms"]
    bom0 = call("get_bom")
    asm_id = js("return window.__app.project.active")

    # 1. a part clicked in the view: ✎ Upravit díl zde and 👁 Skrýt / zobrazit… among the rows shown, also with 3 rows
    p2 = spot("I2")
    print("  the arm's spot:", p2)
    click_view(p2[0], p2[1])
    check(js(f"return {A}.sel") == "I2", "a click on the arm chooses it")
    ActionChains(d).move_to_element(d.find_element(By.CSS_SELECTOR, f"{SG} .vs-head b")).perform()  # (⋯ Top n shows on hover)
    time.sleep(0.3)
    d.find_element(By.CSS_SELECTOR, f"{SG} .vs-set").click()
    inp = d.find_element(By.CSS_SELECTOR, f"{SG} .vs-top input")
    inp.send_keys("3", Keys.ENTER)
    time.sleep(0.4)
    ls = labels()
    print("  rows shown (3 at most + the pinned ones):", ls)
    check(any("Upravit díl zde" in x for x in ls) and any("Skrýt / zobrazit…" in x for x in ls) and bool(d.find_elements(By.CSS_SELECTOR, f"{SG} [data-sg-all]")),
          "with 3 rows: ✎ Upravit díl zde and 👁 Skrýt / zobrazit… shown, the rest under ⋯ Ukázat vše")
    check(not any("Odemknout" in x for x in ls), "no separate “Odemknout a upravit” row")

    # 2. 👁 opens its choices as rows in the table
    sg_row("Skrýt / zobrazit…").click()
    time.sleep(0.4)
    ls = labels()
    print("  👁 open:", ls)
    check(all(any(w in x for x in ls) for w in ("Skrýt", "Zprůhlednit", "Skrýt ostatní (izolovat)", "Zprůhlednit ostatní"))
          and not any("Zobrazit vše" in x for x in ls) and not d.find_elements(By.CSS_SELECTOR, ".sg-menu, .modal"),
          "👁: Skrýt, Zprůhlednit, Skrýt ostatní (izolovat), Zprůhlednit ostatní as rows (no popup); no Zobrazit vše yet")
    d.save_screenshot(f"{OUT}/hide_rows.png")
    hide = next(b for b in d.find_elements(By.CSS_SELECTOR, f"{SG} .vs-list button[data-sg]") if b.text.strip().endswith("Skrýt"))
    ActionChains(d).move_to_element(hide).perform()
    time.sleep(0.4)
    check("I2" not in shown_ids() and not display(), "hovering Skrýt previews it (the arm not drawn, nothing set)")
    ActionChains(d).move_to_element(tree_row("I1")).perform()
    time.sleep(0.4)
    check("I2" in shown_ids(), "the mouse off the row: the arm back")

    # 3. Skrýt: not drawn, a click there picks what is behind it, the tree strikes it through, the note over the tree
    hide = next(b for b in d.find_elements(By.CSS_SELECTOR, f"{SG} .vs-list button[data-sg]") if b.text.strip().endswith("Skrýt"))
    hide.click()
    time.sleep(0.5)
    check(display() == {"I2": "hidden"} and "I2" not in shown_ids(), f"Skrýt: the arm hidden {display()}")
    check("as-hidden" in tree_row("I2").get_attribute("class"), "the tree: its row dimmed / struck through")
    note = d.find_element(By.CSS_SELECTOR, "#asmLeft .as-vis")
    check(note.is_displayed() and "1 skryté" in note.text and "Zobrazit vše" in note.text, f"the note over the tree: {note.text!r}")
    check(any("Zobrazit vše" in x for x in labels()), "the table: Zobrazit vše now")
    js(f"{A}.choose(null)")
    time.sleep(0.3)
    click_view(p2[0], p2[1])
    print("  clicked the arm's spot again: chosen", js(f"return {A}.sel"), "(behind it:", p2[2], ")")
    check(js(f"return {A}.sel") != "I2" and js(f"return {A}.sel") == p2[2], "a click on the hidden arm's spot picks what is behind it")
    d.save_screenshot(f"{OUT}/hide_hidden.png")

    # 4. Zobrazit vše (the note over the tree)
    d.find_element(By.CSS_SELECTOR, "#asmLeft .as-vis .as-showall").click()
    time.sleep(0.4)
    check(not display() and len(shown_ids()) == 4 and not d.find_element(By.CSS_SELECTOR, "#asmLeft .as-vis").is_displayed(), "Zobrazit vše: every part back, the note gone")

    # 5. Zprůhlednit: see-through, a click there takes the part behind it
    choose_in_tree("I2")
    open_eye_rows()
    sg_row("Zprůhlednit").click()
    time.sleep(0.5)
    op = js(f"const m = {A}.view.meshes.find(m => m.userData.inst === 'I2'); return [m.material.opacity, m.material.transparent, m.visible]")
    check(display() == {"I2": "clear"} and op[0] < 1 and op[1] and op[2], f"Zprůhlednit: opacity {op}")
    check("as-clear" in tree_row("I2").get_attribute("class") and "1 průhledné" in d.find_element(By.CSS_SELECTOR, "#asmLeft .as-vis").text, "the tree: see-through row, the note says so")
    js(f"{A}.choose(null)")
    time.sleep(0.3)
    click_view(p2[0], p2[1])
    check(js(f"return {A}.sel") == (p2[2] or "I2"), f"a click on it takes the part behind it ({js(f'return {A}.sel')})")

    # 6. Skrýt ostatní (izolovat), then Zobrazit vše in the table
    choose_in_tree("I2")
    open_eye_rows()
    sg_row("Skrýt ostatní (izolovat)").click()
    time.sleep(0.5)
    check(shown_ids() == ["I2"] and display() == {"I1": "hidden", "I3": "hidden", "I4": "hidden"}, f"izolovat: only the arm {shown_ids()}")
    d.save_screenshot(f"{OUT}/hide_isolated.png")
    sg_row("Zobrazit vše").click()
    time.sleep(0.5)
    check(not display() and len(shown_ids()) == 4, "Zobrazit vše in the table: everything back")

    # 7. Zprůhlednit ostatní
    open_eye_rows()
    sg_row("Zprůhlednit ostatní").click()
    time.sleep(0.5)
    check(display() == {"I1": "clear", "I3": "clear", "I4": "clear"}, f"Zprůhlednit ostatní: {display()}")
    sg_row("Zobrazit vše").click()
    time.sleep(0.4)

    # 8. 👁 in the tree
    eye = lambda: tree_row("I3").find_element(By.CSS_SELECTOR, ".as-eye")
    ActionChains(d).move_to_element(tree_row("I3")).perform()
    time.sleep(0.2)
    eye().click()
    time.sleep(0.4)
    check(display() == {"I3": "hidden"} and "I3" not in shown_ids() and eye().is_displayed(), "👁 in the tree: hidden (the eye stays in sight)")
    eye().click()
    time.sleep(0.4)
    check(not display() and "I3" in shown_ids(), f"👁 again: shown {display()}")
    ActionChains(d).move_to_element(tree_row("I3")).perform()
    ActionChains(d).key_down(Keys.ALT).click(eye()).key_up(Keys.ALT).perform()
    time.sleep(0.4)
    check(display() == {"I3": "clear"}, f"Alt+click 👁: see-through {display()}")
    eye().click()
    time.sleep(0.4)
    check(display() == {"I3": "hidden"}, "👁 on a see-through part: hidden")
    eye().click()
    time.sleep(0.4)

    # 9. two parts (Ctrl+click): both
    choose_in_tree("I2")
    choose_in_tree("I3", ctrl=True)
    check(js(f"return [{A}.sel, {A}.sel2]") == ["I2", "I3"], "Ctrl+click: two parts chosen")
    check(any("Skrýt / zobrazit…" in x for x in labels()), "the two parts' table: 👁 Skrýt / zobrazit… too")
    open_eye_rows()
    print("  chosen:", js(f"return [{A}.sel, {A}.sel2]"), labels())
    next(b for b in d.find_elements(By.CSS_SELECTOR, f"{SG} .vs-list button[data-sg]") if b.text.strip().endswith("Skrýt")).click()
    time.sleep(0.5)
    check(display() == {"I2": "hidden", "I3": "hidden"}, f"Skrýt with two chosen: both hidden {display()}")

    # 10. H / Shift+H / Alt+H
    key("H", Keys.SHIFT)
    check(not display(), "Shift+H: everything shown")
    choose_in_tree("I4")
    key("h")
    check(display() == {"I4": "hidden"}, "H: the chosen part hidden")
    key("h")
    check(not display(), "H again: shown")
    key("h", Keys.ALT)
    check(shown_ids() == ["I4"], f"Alt+H: isolated {shown_ids()}")
    key("H", Keys.SHIFT)
    check(not display() and len(shown_ids()) == 4, "Shift+H: back")
    title = sg_row("Skrýt / zobrazit…").get_attribute("title")
    check("Shift+H" in title and "Alt+H" in title, f"the shortcuts in its tooltip: {title!r}")

    # 10b. only a face picked (no whole part): ✎ Upravit díl zde and 👁 there too, acting on the face's part
    js(f"{A}.choose(null)")
    time.sleep(0.3)
    p3 = spot("I3", behind=False)
    click_view(p3[0], p3[1])
    fp = js(f"return ({A}.facePicks || []).map(q => [q.inst, q.face.name])")
    print("  the face picked:", fp)
    ls = labels()
    check(len(fp) == 1 and fp[0][0] == "I3" and any("Upravit díl zde" in x for x in ls) and any("Skrýt / zobrazit…" in x for x in ls),
          "a face picked: ✎ Upravit díl zde and 👁 Skrýt / zobrazit… among the rows shown")
    open_eye_rows()
    next(b for b in d.find_elements(By.CSS_SELECTOR, f"{SG} .vs-list button[data-sg]") if b.text.strip().endswith("Skrýt")).click()
    time.sleep(0.5)
    check(display() == {"I3": "hidden"}, f"Skrýt from the face's table: its part hidden {display()}")
    key("H", Keys.SHIFT)

    # 11. display only: the mechanisms, the BOM and the collision check do not change
    call("set_visibility", hide=["I3"], transparent=["I2"])
    mech1 = json.loads(call("get_assembly"))["mechanisms"]
    check(json.dumps(mech0, sort_keys=True) == json.dumps(mech1, sort_keys=True), "the mechanisms unchanged with parts hidden")
    check(call("get_bom") == bom0, "the BOM unchanged")
    cl = call("check_collisions")
    print("  check_collisions:", cl[:120])
    check(not cl.startswith("ERROR"), "the collision check runs over every part")

    # 12. the AI
    g = json.loads(call("get_assembly"))
    check(g.get("hidden") == ["I3"] and g.get("transparent") == ["I2"], f"get_assembly: hidden {g.get('hidden')} transparent {g.get('transparent')}")
    shot = js(f"return {H}.get_screenshot({{}}).then(r => !!(r.image || r.images || r.text)).catch(e => 'ERROR ' + e.message)")
    check(shot is True, f"get_screenshot with a part hidden: {shot}")
    check(call("set_visibility", hide=["I9"]).startswith("ERROR"), "set_visibility: an unknown part refused")
    check(call("set_visibility").startswith("ERROR"), "set_visibility with nothing: refused")
    tx = call("set_visibility", isolate=["I4"], others="transparent")
    check(display() == {"I1": "clear", "I2": "clear", "I3": "clear"} and "see-through: I1, I2, I3" in tx, f"set_visibility isolate, others transparent: {tx[:90]}")
    call("set_visibility", show_all=True, hide=["I3"])
    check(display() == {"I3": "hidden"}, "show_all then hide: only I3 hidden")

    # 13. autosaved, reloaded: still hidden
    js("return window.__app.autosave.saveNow()")
    time.sleep(0.5)
    d.refresh()
    wait("return !!window.__app")
    wait("return document.querySelector('.restore-bar')", 15)
    d.find_element(By.CSS_SELECTOR, ".restore-bar [data-a=open]").click()
    time.sleep(1)
    call("open_part", id=asm_id)
    ready()
    check(display() == {"I3": "hidden"} and "I3" not in shown_ids() and "as-hidden" in tree_row("I3").get_attribute("class"), "reloaded: I3 still hidden")
    key("H", Keys.SHIFT)
    check(not display(), "Shift+H after the reload: shown")

    # 14. ✎ Upravit díl zde from a picked face: the part in the 3D modeler, in place, that face chosen there
    js(f"{A}.view.setView('iso'); {A}.choose(null)")
    time.sleep(0.5)
    p2 = spot("I2", behind=False)
    click_view(p2[0], p2[1])
    face = js(f"return ({A}.facePicks || [])[0]?.face.name")
    check(js(f"return ({A}.facePicks || [])[0]?.inst") == "I2" and not js(f"return {A}.editable({A}.inst('I2').part)"), f"a face of the arm picked ({face}), its part locked")
    sg_row("Upravit díl zde").click()
    wait("return window.__app.state.workspace === 'model'", 30)
    check(js("return window.__app.state.workspace") == "model" and js("return !!window.__app.modeler.context"), "✎ Upravit díl zde: its part opened in place (unlocked first)")
    got = wait("const m = window.__app.modeler; return m.picks?.length === 1 && m.picks[0].kind === 'face' ? m.picks[0].face.name : null", 30)
    tb = d.find_element(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-head b").text
    print("  in the part:", got, "| its table:", tb)
    check(got == face, f"the face picked in the assembly is chosen in the part ({got}), its suggestions shown ({tb!r})")
    d.save_screenshot(f"{OUT}/hide_edit_face.png")

    errs = [e for e in d.get_log("browser") if e["level"] == "SEVERE" and "favicon" not in e["message"]]
    check(not errs, f"no console errors {[e['message'][:160] for e in errs]}")
finally:
    d.quit()

print("FAILED:" if bad else "ALL OK", *bad, sep="\n  ")
sys.exit(1 if bad else 0)
