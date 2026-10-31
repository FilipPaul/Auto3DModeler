"""Several parts chosen in an assembly's parts list, in headless Edge (Czech; the owner: "selecting parts must be very
easy"): "Stroj" = a plate, the crank demo as the sub-assembly "Pohon" (its rows folded open) and three flags -> real
clicks with keys held: a click chooses one, Ctrl+click adds / takes out, Shift+click the rows between the last clicked
one and this one (across Pohon's own rows), Ctrl+Shift+click adds a range; the rows lit = the chosen set = the parts
lit in the view; Shift+click selects no page text; the panel and the suggestions for several (Vybráno dílů: n,
👁 Skrýt / zobrazit… on them all, Vyjmout je (n) — one undo step); a Ctrl+click in the view adds to the same set; Esc
and a click beside the rows clear it -> the 500-part demo: Ctrl / Shift+click on its rows timed (handlers < 100 ms).

  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_multiselect.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time
import urllib.request

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.add_argument("--lang=cs-CZ")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
A = "window.__app.assembly"
H = "window.__app.agentHandlers"
bad = []


def check(ok, what):
    print(("  ok  " if ok else "  FAIL") + " " + what)
    if not ok:
        bad.append(what)


def wait(script, t=120):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def call(t, **a):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", t, a)


def load_demo(f):
    with urllib.request.urlopen(f"{URL}/api/demos/{f}") as r:
        p = json.loads(r.read())
    js("return window.__app.project.loadAll(arguments[0])", p)
    time.sleep(2)


def row(key):
    sel = f'[data-inst="{key}"]' if "/" not in key else f'[data-path="{key}"]'
    return d.find_element(By.CSS_SELECTOR, f"#leftCol .as-list > {sel}")


def click(key, *keys):
    el = row(key)
    d.execute_script("arguments[0].scrollIntoView({block: 'center'})", el)
    act = ActionChains(d)
    for k in keys:
        act = act.key_down(k)
    act = act.click(el.find_element(By.CSS_SELECTOR, ".mt-name"))
    for k in reversed(keys):
        act = act.key_up(k)
    act.perform()
    time.sleep(0.4)


def chosen():
    return js(f"return {A}.selKeys()")


def lit_rows():
    return js("return [...document.querySelectorAll('#leftCol .as-list > .mt-item.on')].map(r => r.dataset.inst || r.dataset.path)")


def lit_view():
    return sorted(js(f"return {A}.view.meshes.filter(m => m.material.emissive && [0x1e4f86, 0x2f6fc4].includes(m.material.emissive.getHex())).map(m => m.userData.inst)"))


def all_rows():
    return js("return [...document.querySelectorAll('#leftCol .as-list > [data-inst], #leftCol .as-list > [data-path]')].map(r => r.dataset.inst || r.dataset.path)")


def same_set(what, want):
    keys, rows = chosen(), lit_rows()
    tops = sorted({k.split("/")[0] for k in want})
    check(sorted(keys) == sorted(want) and sorted(rows) == sorted(want) and lit_view() == tops,
          f"{what}: chosen {keys}, rows lit {rows}, view lit {lit_view()} (want {want})")


def suggest_rows():
    return [e.text for e in d.find_elements(By.CSS_SELECTOR, ".vs-list [data-sg]") if e.is_displayed()]


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('auto3d-lang'); localStorage.removeItem('a3d.asmTree')")
    load_demo("klikovy-mechanismus.a3d")
    wait(f"return {A}.doc.instances.length === 4 && {A}.doc.instances.every(i => {A}.bodyOf(i)?.body)")
    call("rename_part", id="Klikový mechanismus", name="Pohon")
    call("new_model", name="Deska")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 400, "h": 300}}])
    call("add_feature", type="extrude", sketch="F1", d=8)
    call("new_model", name="Prapor")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 16}}])
    call("add_feature", type="extrude", sketch="F1", d=4)
    call("new_assembly", name="Stroj")
    for p in ("Deska", "Pohon", "Prapor", "Prapor", "Prapor"):
        call("insert_part", part=p)
    wait(f"return {A}.doc.instances.length === 5 && {A}.doc.instances.every(i => {A}.bodyOf(i)?.body)")
    js(f"{A}.toggleOpen('I2')")
    time.sleep(0.5)
    rows = all_rows()
    print("  rows:", rows)
    check(rows[:2] == ["I1", "I2"] and rows[2].startswith("I2/") and rows[-3:] == ["I3", "I4", "I5"], "Pohon's own rows under its row")

    click("I1")
    same_set("a click chooses one", ["I1"])
    click("I3", Keys.CONTROL)
    same_set("Ctrl+click adds the second", ["I1", "I3"])
    click("I4", Keys.CONTROL)
    same_set("Ctrl+click adds the third", ["I1", "I3", "I4"])
    check(js("return document.querySelector('#asmRight .mp-body h2')?.textContent") == "Vybráno dílů: 3", f"the panel: {js('return document.querySelector(\"#asmRight .mp-body h2\")?.textContent')}")
    click("I3", Keys.CONTROL)
    same_set("Ctrl+click on a chosen one takes it out", ["I1", "I4"])

    click("I1")
    click("I4", Keys.SHIFT)
    want = rows[: rows.index("I4") + 1]
    same_set("Shift+click: every row between, Pohon's own rows too", want)
    check(js("return String(window.getSelection())") == "", f"Shift+click selected no page text ({js('return String(window.getSelection())')!r})")
    click(rows[3], Keys.SHIFT)
    same_set("Shift+click again from the same first row: fewer rows", rows[:4])

    click("I5")
    click(rows[2], Keys.CONTROL)
    click("I3", Keys.CONTROL, Keys.SHIFT)
    same_set("Ctrl+Shift+click adds the range to what is chosen", ["I5", rows[2], *rows[3:rows.index("I3") + 1]])

    # the suggestions on them all
    click("I3")
    click("I5", Keys.SHIFT)
    sg = suggest_rows()
    check(any("Vyjmout je (3)" in x for x in sg) and any("Skrýt / zobrazit" in x for x in sg), f"the suggestions for three: {sg}")
    js(f"{A}.view.setView('top')")
    time.sleep(0.4)  # (drawn once: the camera's matrices the projection below reads are updated by a render)
    # a Ctrl+click in the view adds to the same set
    pt = js(f"""const it = {A}.inst('I1'), b = {A}.bodyOf(it).body.bbox, m = it.matrix;
      const p = [(b[0] + b[3]) / 2 + 150, (b[1] + b[4]) / 2 + 120, b[5]];
      return [0, 1, 2].map((k) => m[k] * p[0] + m[4 + k] * p[1] + m[8 + k] * p[2] + m[12 + k]);""")
    js(f"window.__V3 = {A}.view.camera.position.constructor")
    cv = js(f"return {A}.view.renderer.domElement")
    xy = js(f"const r = arguments[0].getBoundingClientRect(), v = new window.__V3(...arguments[1]).project({A}.view.camera); return [(v.x + 1) / 2 * r.width - r.width / 2, (1 - v.y) / 2 * r.height - r.height / 2]", cv, pt)
    hit = js(f"const r = arguments[0].getBoundingClientRect(); return {A}.view.pickInst(r.left + r.width / 2 + arguments[1], r.top + r.height / 2 + arguments[2])?.inst", cv, *xy)
    ActionChains(d).key_down(Keys.CONTROL).move_to_element_with_offset(cv, int(xy[0]), int(xy[1])).click().key_up(Keys.CONTROL).perform()
    time.sleep(0.5)
    same_set(f"Ctrl+click in the view on the plate ({hit}) adds it", ["I3", "I4", "I5", "I1"])
    d.save_screenshot(f"{OUT}/multiselect_four.png")

    # 👁 hide them all, then show; take them out: one undo step
    js(f"{A}.select(['I3', 'I4', 'I5'])")
    d.find_element(By.TAG_NAME, "body").send_keys("h")
    time.sleep(0.4)
    check(js(f"return ['I3', 'I4', 'I5'].every(id => {A}.doc.display?.[id] === 'hidden')"), "H hides all three")
    d.find_element(By.TAG_NAME, "body").send_keys("h")
    time.sleep(0.4)
    check(js(f"return ['I3', 'I4', 'I5'].every(id => !{A}.doc.display?.[id])"), "H again shows them")
    item = next(e for e in d.find_elements(By.CSS_SELECTOR, ".vs-list [data-sg]") if e.is_displayed() and "Vyjmout je (3)" in e.text)
    item.click()
    time.sleep(0.8)
    check(js(f"return {A}.doc.instances.map(i => i.id)") == ["I1", "I2"] and chosen() == [], "Vyjmout je (3): out, none chosen")
    js(f"return {A}.history.go(-1)")
    time.sleep(1.2)
    check(js(f"return {A}.doc.instances.map(i => i.id)") == ["I1", "I2", "I3", "I4", "I5"], "one undo brings all three back")

    # Esc and a click beside the rows clear it
    js(f"{A}.select(['I3', 'I4', 'I5'])")
    d.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    time.sleep(0.4)
    same_set("Esc clears it", [])
    js(f"{A}.select(['I3', 'I4', 'I5'])")
    lst = d.find_element(By.CSS_SELECTOR, "#leftCol .as-list")
    h = lst.size["height"]
    under = js("const r = arguments[0].getBoundingClientRect(); const e = document.elementFromPoint(r.left + 40, r.bottom + 12); return e ? e.className + ' ' + e.tagName : null", lst)
    print("  beside the rows:", under)
    ActionChains(d).move_to_element_with_offset(lst, -int(lst.size["width"] / 2) + 40, int(h / 2) + 12).click().perform()
    time.sleep(0.4)
    same_set("a click beside the rows clears it", [])

    # the 500-part demo: Ctrl / Shift+click timed
    load_demo("velka-sestava-500.a3d")
    wait(f"return {A}.doc.instances.length > 400 && {A}.doc.instances.every(i => {A}.bodyOf(i)?.body)", 300)
    time.sleep(2)
    ids = js(f"return {A}.doc.instances.map(i => i.id)")
    js(f"{A}.renderList()")
    times = js(f"""const out = {{}}, row = (k) => document.querySelector(`#leftCol .as-list > [data-inst="${{k}}"]`);
      const t = (name, k, o) => {{ const r = row(k).querySelector('.mt-name'), s = performance.now();
        r.dispatchEvent(new MouseEvent('click', {{ bubbles: true, ...o }})); out[name] = Math.round(performance.now() - s); }};
      t('click', arguments[0], {{}}); t('ctrl', arguments[1], {{ ctrlKey: true }}); t('ctrl2', arguments[2], {{ ctrlKey: true }});
      t('shift', arguments[3], {{ shiftKey: true }}); t('ctrlshift', arguments[4], {{ ctrlKey: true, shiftKey: true }});
      out.n = {A}.selKeys().length; return out;""", ids[10], ids[20], ids[30], ids[200], ids[300])
    print("  500 parts, ms:", times)
    check(max(v for k, v in times.items() if k != "n") < 100 and times["n"] == 271, f"on {len(ids)} parts each click's handlers < 100 ms, Ctrl+Shift added rows 30–300 to 30–200 ({times})")
    click(ids[5])
    click(ids[60], Keys.SHIFT)
    check(len(chosen()) == 56 and len(lit_rows()) == 56, f"500 parts, real Shift+click: 56 rows ({len(chosen())}, lit {len(lit_rows())})")
finally:
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        bad.append(f"console errors: {errs[:3]}")
    d.quit()
print("FAILED:" if bad else "ALL OK", bad if bad else "")
sys.exit(1 if bad else 0)
