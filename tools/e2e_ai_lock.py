"""🔒 Locked for the AI, in headless Edge (Czech; the AI's calls through the server's /api/agent/call, as the MCP server
sends them): parts Deska (its height = the parameter T), Ložisko, Kolík, Víko, Rám, a sub-assembly "Pohon" (Ložisko +
Kolík) and "Stroj" (Deska, Pohon, Víko, Rám, a library screw) -> the project tree: Ložisko's 🔒 clicked (shown, the
others' only on hover), Ctrl+click two rows -> "🔒 Zamknout pro AI (2)" -> Stroj's list: Shift+click 3 rows -> the
suggestion "🔒 Zamknout pro AI (3)" (one undo step: Ctrl+Z takes all three back, Ctrl+Y again); the icons show -> the AI:
get_model / list_parts / get_assembly say ai_locked; edit_feature, add_feature, set_material, delete_part, rename_part
on a locked part refused with "je zamčený pro AI … vazby přidat lze"; the library screw refused without a flag;
set_parameter T (it drives Deska) refused and names it; set_look / move inside the locked Pohon refused; snap_faces to
a locked part and into the locked Pohon's Kolík -> joined -> the user changes Ložisko's material by hand (done, the note
"Díl je zamčený pro AI") -> the panel's reason chip (koupený) -> save, reload: the locks kept -> unlocked via the
suggestion "🔓 Odemknout pro AI (3)" -> the AI may change them again -> no console errors, no native dialogs.

  PYTHONIOENCODING=utf-8 py tools/e2e_ai_lock.py http://127.0.0.1:5199 <out dir>
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
APP = "window.__app"
A = f"{APP}.assembly"
bad = []
LOCKED = "je zamčený pro AI"


def check(ok, what, got=None):
    print(("  ok  " if ok else "  FAIL") + " " + what + ("" if ok or got is None else f" — got {str(got)[:300]}"))
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


def ai(tool, **args):
    req = urllib.request.Request(f"{URL}/api/agent/call", data=json.dumps({"tool": tool, "args": args}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        res = json.loads(r.read())
    text = "".join(c.get("text", "") for c in res.get("content", []))
    return ("ERROR " if res.get("isError") else "") + text


def data(tool, **args):
    t = ai(tool, **args)
    try:
        return json.loads(t)
    except ValueError:
        return t


def pid(name):
    return next(p["id"] for p in data("list_parts") if p["name"] == name)


def locked_ids():
    return sorted(js(f"return {APP}.project.parts.filter(p => p.ai_lock).map(p => p.name)"))


def block(name, w, h, t):
    ai("new_model", name=name)
    ai("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": w, "h": h}}])
    ai("add_feature", type="extrude", sketch="F1", d=t)


def pin(name, dia, h):
    ai("new_model", name=name)
    ai("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": dia}}])
    ai("add_feature", type="extrude", sketch="F1", d=h)


def tree_row(name):
    return next(r for r in d.find_elements(By.CSS_SELECTOR, "#projTree .pt-row") if r.find_element(By.CSS_SELECTOR, ".pt-rname").text == name)


def asm_row(key):
    sel = f'[data-inst="{key}"]' if "/" not in key else f'[data-path="{key}"]'
    return d.find_element(By.CSS_SELECTOR, f"#leftCol .as-list > {sel}")


def click(el, *keys):
    js("arguments[0].scrollIntoView({block: 'center'})", el)
    act = ActionChains(d)
    for k in keys:
        act = act.key_down(k)
    act = act.click(el)
    for k in reversed(keys):
        act = act.key_up(k)
    act.perform()
    time.sleep(0.4)


def suggest(label):
    for e in d.find_elements(By.CSS_SELECTOR, ".view-suggest .vs-list [data-sg]"):
        if e.is_displayed() and label in e.text:
            return e
    return None


try:
    d.get(URL)
    wait(f"return !!{APP}")
    js("localStorage.removeItem('auto3d-lang'); localStorage.removeItem('a3d.asmTree'); localStorage.removeItem('a3d.leftDock')")
    d.get(URL)
    wait(f"return !!{APP}")
    time.sleep(1)
    js("window.__asked = 0; for (const k of ['alert', 'confirm', 'prompt']) window[k] = () => { window.__asked++; return null; }")

    # ------------------------------------------------------------------ the project
    block("Deska", 120, 80, 8)
    ai("set_parameter", name="T", value="8")
    print("Deska's height by T:", ai("edit_feature", id="F2", fields={"d": "T"})[:60])
    pin("Ložisko", 22, 7)
    pin("Kolík", 5, 20)
    block("Víko", 40, 40, 3)
    block("Rám", 30, 10, 10)
    ai("new_assembly", name="Pohon")
    ai("insert_part", part="Ložisko")
    ai("insert_part", part="Kolík")
    ai("new_assembly", name="Stroj")
    for p in ("Deska", "Pohon", "Víko", "Rám"):
        ai("insert_part", part=p)
    lib = data("library_add", item="iso4762", size="M3", length=10, to="assembly")
    print("the library screw:", lib.get("name") if isinstance(lib, dict) else lib)
    wait(f"return {A}.doc.instances.length === 5 && {A}.doc.instances.every(i => {A}.bodyOf(i)?.body)")
    time.sleep(1)

    # ------------------------------------------------------------------ the project tree: one 🔒, then Ctrl+click two rows
    wait("return document.querySelectorAll('#projTree .pt-row').length >= 7")
    row = tree_row("Ložisko")
    btn = row.find_element(By.CSS_SELECTOR, ".ai-lock")
    check(not btn.is_displayed() or btn.value_of_css_property("visibility") == "hidden", "an unlocked row's 🔒 is hidden (until hover)")
    ActionChains(d).move_to_element(row).perform()
    time.sleep(0.2)
    check(row.find_element(By.CSS_SELECTOR, ".ai-lock").value_of_css_property("visibility") == "visible", "…and shows on hover")
    row.find_element(By.CSS_SELECTOR, ".ai-lock").click()
    time.sleep(0.4)
    check(locked_ids() == ["Ložisko"], "🔒 in the tree locks Ložisko", locked_ids())
    on = tree_row("Ložisko").find_element(By.CSS_SELECTOR, ".ai-lock")
    ActionChains(d).move_to_element(tree_row("Stroj")).perform()
    time.sleep(0.2)
    check("on" in on.get_attribute("class") and on.value_of_css_property("visibility") == "visible", "its 🔒 stays shown")
    check(js(f"return {APP}.project.current.name") == "Stroj", "the 🔒 click did not open the part")
    # Ctrl+click Víko and Rám: chosen, the bar offers the lock for both
    click(tree_row("Víko").find_element(By.CSS_SELECTOR, ".pt-rname"), Keys.CONTROL)
    click(tree_row("Rám").find_element(By.CSS_SELECTOR, ".pt-rname"), Keys.CONTROL)
    picked = js(f"return [...{APP}.project.picked].map(id => {APP}.project.parts.find(p => p.id === id).name).sort()")
    print("chosen in the tree:", picked)
    bar = d.find_element(By.CSS_SELECTOR, "#projTree .tr-picked")
    check("Zamknout pro AI" in bar.text, "the tree's suggestion row: Zamknout pro AI", bar.text)
    lock_btn = next(b for b in bar.find_elements(By.CSS_SELECTOR, "button") if "Zamknout" in b.text)
    want = sorted(set(picked) - {"Ložisko"})
    check(f"({len(want)})" in lock_btn.text, f"…for the {len(want)} not locked yet", lock_btn.text)
    lock_btn.click()
    time.sleep(0.4)
    check(set(want) <= set(locked_ids()), "Ctrl+click + the suggestion locked them", locked_ids())
    # the ⋯ menu of a row unlocks them again (all chosen)
    more = tree_row("Víko").find_element(By.CSS_SELECTOR, ".pt-more")
    ActionChains(d).move_to_element(more).perform()
    more.click()
    time.sleep(0.3)
    items = [e.text for e in d.find_elements(By.CSS_SELECTOR, ".sg-menu [data-sg]")]
    check(any("Odemknout pro AI" in x for x in items), "the row's ⋯ menu: Odemknout pro AI", items)
    next(e for e in d.find_elements(By.CSS_SELECTOR, ".sg-menu [data-sg]") if "Odemknout" in e.text).click()
    time.sleep(0.4)
    check(locked_ids() == ["Ložisko"], "the ⋯ menu unlocked Víko and Rám (both chosen)", locked_ids())
    tree_row("Stroj").find_element(By.CSS_SELECTOR, ".pt-rname").click()  # (a plain click: none chosen)
    time.sleep(0.5)

    # ------------------------------------------------------------------ Stroj's list: Shift+click 3 rows -> the suggestion
    ids = js(f"return {A}.doc.instances.map(i => [i.id, {A}.partName(i.part)])")
    by = {n: i for i, n in ids}
    print("Stroj:", ids)
    click(asm_row(by["Pohon"]).find_element(By.CSS_SELECTOR, ".mt-name"))
    click(asm_row(by["Rám"]).find_element(By.CSS_SELECTOR, ".mt-name"), Keys.SHIFT)
    print("chosen:", js(f"return {A}.selKeys()"))
    s = suggest("Zamknout pro AI (3)")
    check(s is not None, "the suggestion 🔒 Zamknout pro AI (3)", [e.text for e in d.find_elements(By.CSS_SELECTOR, ".view-suggest [data-sg]")][:14])
    if s:
        s.click()
        time.sleep(0.5)
    check(sorted(locked_ids()) == sorted(["Ložisko", "Pohon", "Víko", "Rám"]), "Pohon, Víko, Rám locked (Ložisko still)", locked_ids())
    icons = [r.get_attribute("data-inst") for r in d.find_elements(By.CSS_SELECTOR, "#leftCol .as-list > [data-inst]") if r.find_elements(By.CSS_SELECTOR, ".ai-lock.on")]
    check(sorted(icons) == sorted([by["Pohon"], by["Víko"], by["Rám"], next(i for i, n in ids if n.startswith("ISO"))]), "🔒 shown on their rows (the library screw's always)", icons)
    js(f"{A}.history.go(-1)")
    time.sleep(0.5)
    check(locked_ids() == ["Ložisko"], "one Ctrl+Z takes the three back", locked_ids())
    js(f"{A}.history.go(1)")
    time.sleep(0.5)
    check(sorted(locked_ids()) == sorted(["Ložisko", "Pohon", "Víko", "Rám"]), "…and redo locks them again", locked_ids())
    d.save_screenshot(f"{OUT}/ai_lock_assembly.png")

    # ------------------------------------------------------------------ the AI: what it reads
    lp = {p["name"]: p for p in data("list_parts")}
    check(lp["Ložisko"].get("ai_locked") and not lp["Deska"].get("ai_locked"), "list_parts: ai_locked", lp["Ložisko"])
    ga = data("get_assembly")
    rows = {p["name"]: p for p in ga["parts"]}
    check(rows["Pohon"].get("ai_locked") and rows["Víko"].get("ai_locked") and not rows["Deska"].get("ai_locked"), "get_assembly: ai_locked per part", {k: v.get("ai_locked") for k, v in rows.items()})
    screw = next(n for n in rows if n.startswith("ISO"))
    check(rows[screw].get("ai_lock_reason") == "library", "…the library screw locked as a library part", rows[screw].get("ai_lock_reason"))
    hs = js("return [...document.querySelectorAll('#projTree .pt-row, #leftCol .as-list > .mt-item')].filter(r => r.querySelector('.ai-lib')).map(r => Math.round(r.getBoundingClientRect().height))")
    check(len(hs) == 2 and all(h < 50 for h in hs), "the library screw's rows: one line each, its 🔒 in them", hs)

    # snap_faces to a locked part, and into the locked Pohon (its Kolík) — joints may be added
    r = ai("snap_faces", move={"part": by["Deska"], "face": "F2:end"}, onto={"part": by["Víko"], "face": "F2:start"}, type="touch")
    check(not r.startswith("ERROR"), "snap_faces Deska onto the locked Víko: allowed", r[:200])
    r = ai("snap_faces", move={"part": by["Rám"], "face": "F2:start"}, onto={"part": by["Pohon"], "face": "I2/F2:end"}, type="touch")
    check(not r.startswith("ERROR") and LOCKED not in r, "snap_faces into the locked Pohon's Kolík: allowed", r[:200])
    # what changes a locked part or the locked sub-assembly: refused
    for tool, args in [("set_look", {"part": by["Víko"], "color": "#ff0000"}), ("paint_faces", {"part": by["Pohon"], "faces": ["F2:end"], "color": "#ff0000"}),
                       ("move_free", {"part": f"{by['Pohon']}/I2", "amount": 5}), ("remove_from_assembly", {"part": f"{by['Pohon']}/I1"})]:
        r = ai(tool, **args)
        check(r.startswith("ERROR") and "zamčen" in r and "vazby přidat lze" in r, f"{tool} on a locked one: refused", r[:160])
    r = ai("set_look", part=by["Deska"], color="#3366ff")
    check(not r.startswith("ERROR"), "set_look on the unlocked Deska: done", r[:120])

    # a locked 3D model: its steps, material, name, the part itself
    ai("open_part", id="Ložisko")
    gm = data("get_model")
    check(gm.get("ai_locked") is True, "get_model: ai_locked", {k: gm.get(k) for k in ("name", "ai_locked")})
    vol = js(f"return {APP}.modeler.result?.body?.volume")
    for tool, args in [("edit_feature", {"id": "F2", "fields": {"d": 12}}),
                       ("add_feature", {"type": "fillet", "edges": ["F2:end"], "r": 1}),
                       ("set_material", {"material": "steel"}),
                       ("delete_part", {"id": "Ložisko"}),
                       ("rename_part", {"id": "Ložisko", "name": "Ložisko 2"})]:
        r = ai(tool, **args)
        check(r.startswith("ERROR") and "🔒 Ložisko " + LOCKED in r and "vazby přidat lze" in r, f"{tool} on the locked Ložisko: refused", r[:160])
    check(js(f"return {APP}.modeler.result?.body?.volume") == vol and js(f"return {APP}.modeler.part.material || 'PLA'") == "PLA", "Ložisko unchanged")
    # a library part: refused without the flag
    sid = js(f"return {APP}.project.parts.find(p => p.name.startsWith('ISO')).id")
    check(js(f"return !{APP}.project.parts.find(p => p.id === arguments[0]).ai_lock", sid), "the library screw carries no flag")
    ai("open_part", id=sid)
    r = ai("edit_feature", id="F2", fields={"d": 3})
    check(r.startswith("ERROR") and LOCKED in r and "díl z knihovny" in r, "edit_feature on the library screw: refused", r[:160])
    r = ai("set_material", material="steel")
    check(r.startswith("ERROR") and LOCKED in r, "set_material on the library screw: refused", r[:120])
    # a parameter driving a locked part
    ai("open_part", id="Deska")
    print("lock Deska (the user, in its panel):")
    box = d.find_element(By.CSS_SELECTOR, "#modelRight .ai-lock-panel")
    check("Zamčeno pro AI" in box.text, "the panel's row: Zamčeno pro AI", box.text)
    box.find_element(By.CSS_SELECTOR, "input[data-ailock-toggle]").click()
    time.sleep(0.4)
    check("Deska" in locked_ids(), "the panel's toggle locks Deska", locked_ids())
    r = ai("set_parameter", name="T", value="12")
    check(r.startswith("ERROR") and "Deska" in r and LOCKED in r, "set_parameter T (drives Deska): refused, names Deska", r[:200])
    r = ai("set_parameter", name="W", value="5")
    check(not r.startswith("ERROR"), "set_parameter W (drives nothing locked): done", r[:120])

    # ------------------------------------------------------------------ the user still edits a locked part (a note)
    ai("open_part", id="Ložisko")
    wait(f"return !!{APP}.modeler.result?.body")
    time.sleep(0.5)
    js("document.querySelectorAll('#toasts .toast').forEach(t => t.remove())")
    sel = d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=material]")
    js("arguments[0].value = 'PETG'; arguments[0].dispatchEvent(new Event('change'))", sel)
    time.sleep(0.6)
    col = d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=color]")
    js("arguments[0].value = '#aa3300'; arguments[0].dispatchEvent(new Event('input')); arguments[0].dispatchEvent(new Event('change'))", col)
    time.sleep(0.6)
    toasts = [e.text for e in d.find_elements(By.CSS_SELECTOR, "#toasts .toast")]
    check(js(f"return {APP}.modeler.part.material") == "PETG" and js(f"return {APP}.modeler.part.color") == "#aa3300", "the user changed the locked Ložisko's material and colour")
    check(any("Díl je zamčený pro AI" in x for x in toasts), "…with the note Díl je zamčený pro AI", toasts)
    chip = next(b for b in d.find_elements(By.CSS_SELECTOR, "#modelRight .ai-reasons .chip") if b.text == "koupený")
    chip.click()
    time.sleep(0.4)
    check(js(f"return {APP}.project.parts.find(p => p.name === 'Ložisko').ai_lock.reason") == "bought", "the reason chip: koupený")
    r = ai("edit_feature", id="F2", fields={"d": 9})
    check("(koupený díl)" in r, "the refusal names the reason", r[:120])
    d.save_screenshot(f"{OUT}/ai_lock_panel.png")

    # ------------------------------------------------------------------ save, reload: the locks kept
    proj = js(f"return {APP}.savedProject({{history: false, savePoint: false}})")
    before = locked_ids()
    d.get(URL)
    wait(f"return !!{APP}")
    time.sleep(1)
    js("window.__asked = 0; for (const k of ['alert', 'confirm', 'prompt']) window[k] = () => { window.__asked++; return null; }")
    js("return fetch('/api/project/migrate', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(arguments[0])}).then(r => r.json()).then(p => window.__app.project.loadAll(p))", proj)
    time.sleep(2)
    check(locked_ids() == before, "save + reload keeps the locks", (before, locked_ids()))
    check(js(f"return {APP}.project.parts.find(p => p.name === 'Ložisko').ai_lock.reason") == "bought", "…and the reason")
    ai("open_part", id="Ložisko")
    r = ai("set_material", material="steel")
    check(r.startswith("ERROR") and LOCKED in r, "after the reload: still refused", r[:100])

    # ------------------------------------------------------------------ unlock via the suggestion
    ai("open_part", id="Stroj")
    wait(f"return {A}.doc.instances.length === 5 && {A}.doc.instances.every(i => {A}.bodyOf(i)?.body)")
    time.sleep(1)
    ids = js(f"return {A}.doc.instances.map(i => [i.id, {A}.partName(i.part)])")
    by = {n: i for i, n in ids}
    click(asm_row(by["Pohon"]).find_element(By.CSS_SELECTOR, ".mt-name"))
    click(asm_row(by["Rám"]).find_element(By.CSS_SELECTOR, ".mt-name"), Keys.SHIFT)
    s = suggest("Odemknout pro AI (3)")
    check(s is not None, "the suggestion 🔓 Odemknout pro AI (3)", [e.text for e in d.find_elements(By.CSS_SELECTOR, ".view-suggest [data-sg]")][:14])
    if s:
        s.click()
        time.sleep(0.5)
    check(sorted(locked_ids()) == ["Deska", "Ložisko"], "Pohon, Víko, Rám unlocked", locked_ids())
    r = ai("set_look", part=by["Víko"], color="#00aa00")
    check(not r.startswith("ERROR"), "the AI may colour Víko again", r[:100])
    check(not js(f"return [...document.querySelectorAll('#leftCol .as-list > [data-inst=\"{by['Víko']}\"] .ai-lock.on')].length"), "Víko's 🔒 gone")
    d.save_screenshot(f"{OUT}/ai_lock_unlocked.png")
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    check(not errs, "no console errors", errs)
    try:
        check(js("return window.__asked || 0") == 0, "no native dialogs")
    except Exception as e:  # noqa: BLE001
        check(False, "no native dialogs", e)
    d.quit()
print("FAILED:" if bad else "ALL OK", bad if bad else "")
sys.exit(1 if bad else 0)
