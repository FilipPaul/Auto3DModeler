"""The 3D model's step tree, nested and two-way, in headless Edge at 1280×800 with REAL mouse input: a plate (sketch ->
extrude), a sketch on its top -> a cut and a boss from the same sketch, a fillet, a pattern of the cut, a reference
point -> the tree: each extrude with its sketch under it (folded), the boss with a link to the sketch it shares, the
pattern with a link to the cut, the point in the folded Reference group with the Top / Front / Right planes; drawn icons
coloured by group; rows one line (≤ 24 px), 12 px a level. ▸ opens / ▾ folds (remembered after a reload). A click on
the fillet's face in the view -> its row chosen and in sight; a click on the cut's sketch outline -> the sketch chosen,
its step folded open; a click on a row -> its faces tinted in the view, a sketch's outline lit; the mouse on a row ->
its faces lit lightly; a link row -> its step. Rename and turn off / on from the row; gui_state's steps with parent /
depth; dragging the boss moves its sketch along. Czech texts. Prints a check list and ALL OK / FAILED.

  PYTHONIOENCODING=utf-8 py tools/e2e_model_tree.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1280,800")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"
H = "window.__app.agentHandlers"
ok = []


def check(name, cond, info=""):
    ok.append(bool(cond))
    print(f"  {name}: {'OK' if cond else 'FAIL'}{'' if cond or info == '' else f'  ({info})'}")


def wait(script, t=60):
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


def row(sel):
    return d.find_element(By.CSS_SELECTOR, f"#modelLeft .mt-tree {sel}")


def rows():
    """The tree's rows as shown: [id or link / group / plane, depth, hidden, kind, group]."""
    return js("""return [...document.querySelectorAll('#modelLeft .mt-tree .mt-row')].map(r => ({
      id: r.dataset.id || (r.dataset.link ? 'link:' + r.dataset.link : r.dataset.datum ? 'plane:' + r.dataset.datum : 'group:' + r.dataset.group),
      d: +getComputedStyle(r).getPropertyValue('--d') || 0, hidden: r.hidden, parent: r.dataset.parent || null,
      kind: r.dataset.kind || null, group: r.dataset.group || null, h: r.getBoundingClientRect().height,
      icon: r.querySelector('.mt-icon svg')?.getAttribute('class') || ''}))""")


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#modelViewport canvas")


def off_xyz(p):
    return js(f"""const v = {M}.view, [x, y, z] = arguments[0];
      const [sx, sy] = v.toScreen(new (v.camera.position.constructor)(x, y, z)), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(p))


def click_at(o):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *o).perform()
    time.sleep(0.3)
    ActionChains(d).click().perform()
    time.sleep(0.4)


def in_sight(rid):
    return js("""const r = document.querySelector(`#modelLeft .mt-item[data-id="${arguments[0]}"]`); if (!r || r.hidden) return false;
      const a = r.getBoundingClientRect(), p = document.querySelector('#modelLeft').getBoundingClientRect();
      return a.height > 0 && a.top >= p.top - 1 && a.bottom <= p.bottom + 1;""", rid)


def selected_faces():
    return js(f"const v = {M}.view; return v.selSet ? [...v.selSet].map(i => v.face(i)?.name || '') : []")


def build():
    """The part: a plate, a sketch on its top -> a cut and a boss, a fillet, a pattern of the cut, a point."""
    call("new_model", name="Tree")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 20}}])  # F1
    call("add_feature", type="extrude", sketch="F1", d=10)  # F2
    call("add_feature", type="sketch", plane={"datum": "XY", "offset": 10}, shapes=[{"circle": {"x": 10, "y": 10, "d": 6}}])  # F3
    call("add_feature", type="extrude", sketch="F3", op="cut", d=4)  # F4
    call("add_feature", type="fillet", edges=[{"a": "F2:end", "b": "F2:side:l1", "fp": [30, 0, 10]}], r=2)  # F5
    print("pattern:", call("add_feature", type="pattern", of=["F4"], count=3, spacing=15)[:60])  # F6
    print("point:", call("add_feature", type="point", at={"corner": [60, 20, 10]})[:60])  # F7
    print("boss:", call("add_feature", type="extrude", sketch="F3", d=3)[:60])  # F8: the same sketch again
    settled()
    js(f"{M}.view.setView('iso')")
    time.sleep(0.5)


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('a3d.treeOpen'); localStorage.setItem('auto3d-lang', 'en')")
    d.get(URL)
    wait("return !!window.__app")
    build()
    print("built:", js(f"return {M}.result.features.map(s => s.id + (s.ok ? '' : ' FAILED'))"))

    # ---- the tree's shape
    R = rows()
    by = {r["id"]: r for r in R}
    print("rows:", [(r["id"], r["d"], "h" if r["hidden"] else "v") for r in R])
    check("Reference group first, folded", R[0]["id"] == "group:ref" and all(by[f"plane:{k}"]["hidden"] for k in ("XY", "XZ", "YZ")))
    check("the point in Reference (depth 1, folded)", by["F7"]["parent"] == "ref" and by["F7"]["d"] == 1 and by["F7"]["hidden"])
    top = [r["id"] for r in R if r["d"] == 0 and not r["id"].startswith("group")]
    check("top level: the steps in order, sketches inside", top == ["F2", "F4", "F5", "F6", "F8"], top)
    check("sketch 1 under the plate, folded", by["F1"]["parent"] == "F2" and by["F1"]["d"] == 1 and by["F1"]["hidden"])
    check("sketch 2 under the cut (its first user)", by["F3"]["parent"] == "F4" and by["F3"]["hidden"])
    check("the boss links to the shared sketch", "link:F3" in by and [r["id"] for r in R].index("link:F3") > [r["id"] for r in R].index("F8"))
    check("the pattern links to the cut", any(r["id"] == "link:F4" for r in R))
    exp = {"F1": ("sketch", "sketch"), "F2": ("extrude", "add"), "F4": ("cut", "cut"), "F5": ("fillet", "edge"), "F6": ("pattern", "pattern"),
           "F7": ("point", "ref"), "F8": ("extrude", "add")}
    check("icons: kind and colour group", all(by[k]["kind"] == v[0] and by[k]["group"] == v[1] and f"g-{v[1]}" in by[k]["icon"] for k, v in exp.items()),
          {k: (by[k]["kind"], by[k]["group"], by[k]["icon"]) for k in exp})
    colours = js("""return [...new Set([...document.querySelectorAll('#modelLeft .mt-tree .mt-item:not([hidden]) .ico-step')].map(s => getComputedStyle(s).color))]""")
    check("different colours per group", len(colours) >= 4, colours)
    hs = [r["h"] for r in R if not r["hidden"]]
    check("rows one line, ≤ 24 px", hs and max(hs) <= 24, hs)
    d.save_screenshot(f"{OUT}/tree1_folded.png")

    # ---- ▸ opens, ▾ folds, remembered
    row('.mt-item[data-id="F2"] .mt-tw').click()
    time.sleep(0.3)
    R = rows()
    by = {r["id"]: r for r in R}
    x1 = js("return document.querySelector('#modelLeft .mt-item[data-id=\"F1\"] .mt-icon').getBoundingClientRect().left - document.querySelector('#modelLeft .mt-item[data-id=\"F2\"] .mt-icon').getBoundingClientRect().left")
    check("▸ opens: sketch 1 shown, 12 px in", not by["F1"]["hidden"] and abs(x1 - 12) < 1.5, x1)
    row('.mt-group').click()
    time.sleep(0.3)
    check("Reference opens: planes and the point", not rows()[1]["hidden"] and in_sight("F7"))
    row('.mt-item[data-id="F6"] .mt-tw').click()
    time.sleep(0.3)
    d.save_screenshot(f"{OUT}/tree2_open.png")
    d.refresh()
    wait("return !!window.__app")
    settled()
    opened = js("return JSON.parse(localStorage.getItem('a3d.treeOpen') || '[]')")
    check("folds remembered", {"F2", "ref", "F6"} <= set(opened), opened)
    build()
    check("shown open after a reload", not js("return document.querySelector('#modelLeft .mt-item[data-id=\"F1\"]').hidden"))
    row('.mt-item[data-id="F2"] .mt-tw').click()
    time.sleep(0.3)
    check("▾ folds again", js("return document.querySelector('#modelLeft .mt-item[data-id=\"F1\"]').hidden"))
    js(f"{M}.view.setView('iso')")
    time.sleep(0.5)

    # ---- the view -> the tree: a click on the fillet's round face
    js(f"{M}.selectStep(null)")
    click_at(off_xyz([30, 0.586, 9.414]))
    settled()
    check("a click on the fillet face: its row chosen and in sight", js(f"return {M}.selected") == "F5" and in_sight("F5")
          and js("return document.querySelector('#modelLeft .mt-item[data-id=\"F5\"]').classList.contains('on')"), js(f"return {M}.selected"))
    # a click on the cut's sketch outline (the circle's rim at x 10 + 3): the sketch chosen, its step folded open
    js("const s = new Set(JSON.parse(localStorage.getItem('a3d.treeOpen') || '[]')); s.delete('F4');" + f" {M}._treeOpen = s; {M}.renderTree();")
    check("(the cut folded first)", js("return document.querySelector('#modelLeft .mt-item[data-id=\"F3\"]').hidden"))
    click_at(off_xyz([10, 13, 10]))
    settled()
    check("a click on a sketch's outline: the sketch chosen, its row shown", js(f"return {M}.selected") == "F3" and in_sight("F3"), js(f"return {M}.selected"))
    lit = js(f"return {M}.view.outlineGroup.children.filter(c => c.userData.sketch === 'F3').map(c => c.material.color.getHex())")
    check("its outline lit", 0xF2CC60 in lit, lit)
    d.save_screenshot(f"{OUT}/tree3_from_view.png")

    # ---- the tree -> the view
    row('.mt-item[data-id="F4"]').click()
    time.sleep(0.4)
    names = selected_faces()
    check("a click on the cut's row: its faces tinted", names and all(n.split(":")[0] == "F4" for n in names), names[:5])
    ActionChains(d).move_to_element(row('.mt-item[data-id="F5"]')).perform()
    time.sleep(0.3)
    hov = js(f"const v = {M}.view; return (v.hoverAlso || []).map(i => v.face(i)?.name || '')")
    check("the mouse on the fillet's row: its faces lit lightly", hov and all(n.split(":")[0] == "F5" for n in hov), hov[:4])
    ActionChains(d).move_to_element(row(".mt-group")).perform()
    row('.mt-item[data-id="F8"] .mt-tw').click()
    time.sleep(0.3)
    row('.mt-link[data-link="F3"]').click()
    time.sleep(0.4)
    check("a link row goes to its step", js(f"return {M}.selected") == "F3" and in_sight("F3"))
    d.save_screenshot(f"{OUT}/tree4_from_tree.png")

    # ---- rename / off / on from the row
    r5 = row('.mt-item[data-id="F5"]')
    ActionChains(d).move_to_element(r5).perform()
    time.sleep(0.2)
    r5.find_element(By.CSS_SELECTOR, "[data-a=rename]").click()
    time.sleep(0.2)
    ActionChains(d).send_keys("Edge round").send_keys(Keys.ENTER).perform()
    time.sleep(0.4)
    check("renamed from the row", js(f"return {M}.part.features.find(f => f.id === 'F5').name") == "Edge round")
    r5 = row('.mt-item[data-id="F5"]')
    ActionChains(d).move_to_element(r5).perform()
    time.sleep(0.2)
    r5.find_element(By.CSS_SELECTOR, "[data-a=off]").click()
    settled()
    check("turned off: greyed row", js(f"return {M}.part.features.find(f => f.id === 'F5').suppressed") is True
          and js("return document.querySelector('#modelLeft .mt-item[data-id=\"F5\"]').classList.contains('off')"))
    d.save_screenshot(f"{OUT}/tree5_off.png")
    r5 = row('.mt-item[data-id="F5"]')
    ActionChains(d).move_to_element(r5).perform()
    time.sleep(0.2)
    r5.find_element(By.CSS_SELECTOR, "[data-a=off]").click()
    settled()
    check("on again", not js(f"return {M}.part.features.find(f => f.id === 'F5').suppressed"))

    # ---- gui_state: parent / depth
    st = json.loads(call("gui_state"))
    steps = {s["id"]: s for s in st.get("steps", [])}
    check("gui_state: the sketch under its step, the point under ref", steps.get("F1", {}).get("parent") == "F2" and steps.get("F1", {}).get("depth") == 1
          and steps.get("F7", {}).get("parent") == "ref" and "parent" not in steps.get("F2", {}), {k: steps[k] for k in list(steps)[:3]})

    # ---- dragging the boss (with its sketch? no: it shares the cut's sketch) and the cut with its sketch
    before = js(f"return {M}.part.features.map(f => f.id)")
    js("""const rows = [...document.querySelectorAll('#modelLeft .mt-item')], s = rows.find(r => r.dataset.id === 'F4'),
      t = rows.find(r => r.dataset.id === 'F5'), dt = new DataTransfer(), b = t.getBoundingClientRect();
      s.dispatchEvent(new DragEvent('dragstart', { bubbles: true, dataTransfer: dt }));
      t.dispatchEvent(new DragEvent('dragover', { bubbles: true, cancelable: true, dataTransfer: dt, clientY: b.bottom - 2 }));
      t.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: dt, clientY: b.bottom - 2 }));""")
    time.sleep(1.2)
    settled()
    after = js(f"return {M}.part.features.map(f => f.id)")
    print("order:", before, "->", after)
    check("the cut dragged below the fillet: its sketch moves along", after.index("F3") + 1 == after.index("F4") and after.index("F4") > after.index("F5"))
    js(f"{M}.history.go(-1)")
    settled()
    check("undone", js(f"return {M}.part.features.map(f => f.id)") == before)

    # ---- Czech
    js("localStorage.setItem('auto3d-lang', 'cs')")
    d.refresh()
    wait("return !!window.__app")
    settled()
    build()
    texts = js("""const q = (s) => document.querySelector(s); return {group: q('#modelLeft .mt-group .mt-name')?.textContent,
      gtitle: q('#modelLeft .mt-group')?.title, plane: q('#modelLeft .mt-plane .mt-name')?.textContent, ptitle: q('#modelLeft .mt-plane')?.title,
      tw: q('#modelLeft .mt-item .mt-tw[data-a]')?.title, link: q('#modelLeft .mt-link')?.title}""")
    print("Czech:", texts)
    check("Czech texts", texts["group"] == "Referenční prvky" and texts["plane"] == "Horní" and "Dvojklik" in (texts["ptitle"] or "")
          and (texts["tw"] or "").startswith(("Ukázat", "Skrýt")) and (texts["link"] or "").find("přejdete") > 0, texts)
    d.save_screenshot(f"{OUT}/tree6_cs.png")
    js("localStorage.setItem('auto3d-lang', 'en')")

    errors = [e for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errors)
    check("no console errors", not errors)
finally:
    d.quit()

print("ALL OK" if all(ok) else "FAILED", f"({sum(ok)}/{len(ok)})")
