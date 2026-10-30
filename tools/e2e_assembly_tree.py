"""The assembly's parts as a tree in its left panel, in headless Edge, with real clicks: "Lever" (a base with a pin, an
arm turning on it) and "Lid unit" (a lid and 2 pins) inside "Machine" (Lid unit placed twice, Lever, a frame) -> each
placed sub-assembly a folded node "▸ … · n part(s)" -> ▸ opens it (its parts indented, their ids) -> a click on an inner
part: it is lit in the view, the panel names it ("I2 inside Lever"), shows its Moves inside (the arm) -> a slider
turns it here -> ◇ Choose the whole Lever -> an inner part of Lid unit: no moves, "holds it in place" -> Ctrl+click
an inner row picks its placement as the second part -> ▾ folds it -> opened nodes remembered after a reload -> the
top rows still choose, 💥 and 📌 as before.

  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_tree.py http://127.0.0.1:5199 <out dir>
"""
import json
import os
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
opts.add_argument("--lang=en-US")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
A = "window.__app.assembly"
H = "window.__app.agentHandlers"
bad = []


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


def check(ok, what):
    print(("  ok   " if ok else "  FAIL ") + what)
    if not ok:
        bad.append(what)


def rows():
    """The list's rows: [indent depth, text]."""
    return js("""return [...document.querySelectorAll('#asmLeft .as-list .mt-item')].map(r => [+(r.style.getPropertyValue('--depth') || 0),
        r.querySelector('.mt-name').textContent + ' ' + r.querySelector('.mt-what').textContent, r.classList.contains('on')])""")


def row(text, depth=None):
    """The list's row whose name and id read `text` (at that depth: 0 the top rows, 1 inside a sub-assembly …)."""
    el = js("""return [...document.querySelectorAll('#asmLeft .as-list .mt-item')].find(r => (r.querySelector('.mt-name').textContent + ' '
        + r.querySelector('.mt-what').textContent).includes(arguments[0]) && (arguments[1] === null || +(r.style.getPropertyValue('--depth') || 0) === arguments[1]))""", text, depth)
    if not el:
        raise LookupError(text)
    return el


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('a3d.asmTree')")
    call("new_model", name="Base")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 60}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="sketch", plane={"face": "F2:end"}, shapes=[{"circle": {"x": 0, "y": 0, "d": 10}}])
    call("add_feature", type="extrude", sketch="F3", d=30)
    call("new_model", name="Arm")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 30, "y": 0, "w": 80, "h": 16}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=10)
    call("new_model", name="Lid")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 50, "h": 30}}])
    call("add_feature", type="extrude", sketch="F1", d=3)
    call("new_model", name="Pin")
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 4}}])
    call("add_feature", type="extrude", sketch="F1", d=8)
    call("new_model", name="Frame")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 300, "h": 120}}])
    call("add_feature", type="extrude", sketch="F1", d=6)
    # Lever: the arm on the base's pin, free to turn
    call("new_assembly", name="Lever")
    call("insert_part", part="Base")
    call("insert_part", part="Arm")
    time.sleep(1)
    call("snap_faces", type="axis", move={"part": "I2", "face": "F3:hole:0"}, onto={"part": "I1", "face": "F4:side:c1"})
    call("snap_faces", type="touch", move={"part": "I2", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})
    call("new_assembly", name="Lid unit")
    for p in ("Lid", "Pin", "Pin"):
        call("insert_part", part=p)
    call("new_assembly", name="Machine")
    for p in ("Frame", "Lid unit", "Lid unit", "Lever"):
        call("insert_part", part=p)
    wait(f"return {A}.doc.instances.length === 4 && Object.values({A}.bodies).every(b => b.body || b.error)")
    js(f"{A}.choose(null)")
    time.sleep(0.4)
    r0 = rows()
    print("folded:", [x[1] for x in r0])
    check(len(r0) == 4 and "Lid unit I2 · 3 part(s)" in [x[1] for x in r0] and "Lever I4 · 2 part(s)" in [x[1] for x in r0], "four top rows, the sub-assemblies folded with their counts")
    check(len(d.find_elements(By.CSS_SELECTOR, "#asmLeft .as-twist")) == 3, "▸ on each placed sub-assembly")

    # ▸ open Lever, click its arm
    row("Lever").find_element(By.CSS_SELECTOR, ".as-twist").click()
    time.sleep(0.3)
    r1 = rows()
    print("Lever open:", [(x[0], x[1]) for x in r1])
    check([(x[0], x[1]) for x in r1[4:]] == [(1, "Base I1"), (1, "Arm I2")], "its parts under it, indented, with their ids")
    row("Arm", 1).click()
    time.sleep(0.5)
    sel = js(f"return [{A}.sel, {A}.selInner]")
    print("chosen:", sel)
    check(sel == ["I4", {"top": "I4", "path": "I2"}], "the arm chosen inside Lever (I4/I2)")
    lit = js("""const m = window.__app.assembly.view.meshes.find(x => x.userData.inst === 'I4');
        const col = m.geometry.getAttribute('color'); if (!col) return null;
        const ids = m.userData.faceIds, faces = m.userData.body.faces, name = (id) => faces.find(f => f.id === id).name;
        let arm = 0, base = 0; for (let tr = 0; tr < ids.length; tr++) { const blue = col.getZ(tr * 3) > 0.9 && col.getX(tr * 3) < 0.3; if (name(ids[tr]).startsWith('I2/')) arm += blue; else base += blue; }
        return [arm, base, m.material.emissive.getHex()]""")
    print("lit triangles (arm, base, emissive):", lit)
    check(lit and lit[0] > 0 and lit[1] == 0 and lit[2] == 0, "only the arm is lit in the view (the placement not glowing as a whole)")
    panel = d.find_element(By.CSS_SELECTOR, "#asmRight .mp-body").text
    print("panel:", panel[:160].replace("\n", " | "))
    check("I2 inside Lever (I4)" in panel and "Moves inside Lever" in panel, "the panel names it and shows its moves inside Lever")
    check(row("Arm", 1).get_attribute("class").count(" on") == 1, "its row marked")
    d.save_screenshot(f"{OUT}/tree_inner.png")
    sl = d.find_element(By.CSS_SELECTOR, "#asmRight .as-inner input[type=range]")
    js("arguments[0].value = 60; arguments[0].dispatchEvent(new Event('input')); arguments[0].dispatchEvent(new Event('change'))", sl)
    time.sleep(0.5)
    turned = js(f"return !!{A}.inst('I4').inner?.I2")
    check(turned, "its slider turns the arm in this placement (inner)")
    d.find_element(By.CSS_SELECTOR, "#asmRight [data-a=wholeSub]").click()
    time.sleep(0.3)
    check(js(f"return [{A}.sel, {A}.selInner]") == ["I4", None], "◇ Choose the whole Lever: the placement")

    # Lid unit: an inner pin cannot move on its own
    row("Lid unit I2").find_element(By.CSS_SELECTOR, ".as-twist").click()
    time.sleep(0.3)
    print("Lid unit open:", [(x[0], x[1]) for x in rows()])
    row("Pin I3", 1).click()
    time.sleep(0.4)
    panel = d.find_element(By.CSS_SELECTOR, "#asmRight .mp-body").text
    check(js(f"return {A}.selInner") == {"top": "I2", "path": "I3"} and "holds it in place" in panel, "a pin in Lid unit: chosen, 'Lid unit holds it in place'")
    # Ctrl+click an inner row: its placement as the second part
    js(f"{A}.choose('I1')")
    time.sleep(0.2)
    ActionChains(d).key_down(Keys.CONTROL).click(row("Lid I1", 1)).key_up(Keys.CONTROL).perform()
    time.sleep(0.3)
    check(js(f"return [{A}.sel, {A}.sel2]") == ["I1", "I2"], "Ctrl+click on an inner row: its placement as the second part")
    # the top rows as before
    row("Frame").click()
    time.sleep(0.2)
    check(js(f"return [{A}.sel, {A}.sel2, {A}.selInner]") == ["I1", None, None], "a top row still chooses its part")
    # ▾ folds Lid unit; reload: Lever stays open
    row("Lid unit I2").find_element(By.CSS_SELECTOR, ".as-twist").click()
    time.sleep(0.3)
    kept = json.loads(js("return localStorage.getItem('a3d.asmTree')"))
    print("remembered:", kept)
    check(list(kept.values()) == [["I4"]], "▾ folds it again; the open ones kept per assembly")
    path = os.path.abspath(os.path.join(OUT, "tree.a3d"))
    with open(path, "wb") as f:
        js("""window.__saved = null; window.showSaveFilePicker = async (o) => ({ name: o.suggestedName,
          createWritable: async () => ({ write: async (b) => { const u = new Uint8Array(await b.arrayBuffer()); let s = ''; for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode(...u.subarray(i, i + 0x8000)); window.__saved = btoa(s); }, close: async () => {} }) });""")
        d.find_element(By.ID, "saveBtn").click()
        f.write(__import__("base64").b64decode(wait("return window.__saved", 30)))
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "projectInput").send_keys(path)
    wait("return window.__app.project.parts.some(p => p.name === 'Machine')", 30)
    mid = js("return window.__app.project.parts.find(p => p.name === 'Machine').id")
    call("open_part", id=mid)
    wait(f"return {A}.active && {A}.doc.instances.length === 4")
    time.sleep(0.6)
    after = rows()
    print("after a reload:", [(x[0], x[1]) for x in after])
    check([(x[0], x[1]) for x in after if x[0]] == [(1, "Base I1"), (1, "Arm I2")], "after a reload: Lever still open, Lid unit folded")
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
print("FAILED:" if bad else "ALL OK", bad)
