"""⏮ The rollback bar of the 3D model's step tree, in headless Edge (Czech, 1280×800) with REAL mouse input: a part
with 4 top-level steps (plate, fillet, boss, cut) -> the bar (6 px) under the last one -> dragged above step 3: the
volume is the 2-step volume, the boss and the cut greyed (gui_state "rolled_back", get_model's rollback), the status
line and "⤓ Na konec" say it -> a hole added: inserted at position 3 (under the fillet), the bar right under it ->
the fillet changed (AI; a panel's OK): rebuilt, still rolled back; a step under the bar opened: shown up to it ->
the page reloaded (autosave, Open): the bar where it was -> right-click a row: "Vrátit se sem" -> ↓ key, double-click
-> dragged to the end: every step, the volume of all minus the hole -> Ctrl+Z puts the bar back -> the AI's rollback
{to} -> under the plate, exports follow the bar (as SolidWorks): the part panel's "⏮ Podle posuvníku historie: bez
posledních 4 kroků (…)", the Export menu's note and ⏮ marks, the STL and 3MF (Save dialog answered by the test) of the
plate's volume with the note in the toast, 🖨 the print copy (its print panel's note, check_print rolled_back, the exact
pieces' volume), an assembly and a drawing sheet of the plate with "⚠ Díl je vrácený v historii" -> the bar at the end:
every step in the STL, the assembly and the sheet, no note anywhere. Prints a check list and ALL OK / FAILED; screenshots in <out dir>.

  PYTHONIOENCODING=utf-8 py tools/e2e_model_rollback.py http://127.0.0.1:5199 <out dir>
"""
import base64
import io
import json
import math
import re
import struct
import sys
import time
import traceback
import zipfile

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
HOLE = math.pi * 3 ** 2 * 10  # Ø6 through the 10 mm plate


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


def vol():
    return js(f"return +{M}.result.body.volume.toFixed(1)")


def ids():
    return js(f"return {M}.part.features.map(f => f.id)")


def top_rows():
    """The top-level rows and the bar as shown: ids, '|' for the bar."""
    return js("""return [...document.querySelectorAll('#modelLeft .mt-tree > .mt-item[data-depth="0"], #modelLeft .mt-tree > .mt-rollbar')]
      .map(r => r.classList.contains('mt-rollbar') ? '|' : r.dataset.id)""")


def greyed():
    return js("return [...document.querySelectorAll('#modelLeft .mt-item.rolled')].map(r => r.dataset.id)")


def bar():
    return d.find_element(By.CSS_SELECTOR, "#modelLeft .mt-rollbar")


def row(rid):
    return d.find_element(By.CSS_SELECTOR, f'#modelLeft .mt-item[data-id="{rid}"]')


def catch_saves():
    """The Save dialog answered by the test: each saved file kept as [name, base64]."""
    js("""window.__saved = []; window.showSaveFilePicker = async (o) => ({ name: o.suggestedName,
      createWritable: async () => ({ write: async (b) => { const u = new Uint8Array(await b.arrayBuffer()); let s = '';
        for (let i = 0; i < u.length; i += 8192) s += String.fromCharCode(...u.subarray(i, i + 8192));
        window.__saved.push([o.suggestedName, btoa(s)]); }, close: async () => {} }) });""")


def saved(n):
    """The n-th saved file's bytes (waited for), also written to OUT."""
    wait(f"return window.__saved.length >= {n}", 120)
    name, b64 = js(f"return window.__saved[{n - 1}]")
    data = base64.b64decode(b64)
    with open(f"{OUT}/{name}", "wb") as fh:
        fh.write(data)
    return data


def tri_volume(tris):
    return sum(a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0]) for a, b, c in tris) / 6


def stl_volume(data):
    n = struct.unpack("<I", data[80:84])[0]
    return tri_volume([[struct.unpack("<3f", data[84 + 50 * i + 12 + 12 * k: 84 + 50 * i + 24 + 12 * k]) for k in range(3)] for i in range(n)])


def mf_volume(data):
    """The volume of every object of a 3MF (its vertices and triangles)."""
    xml = zipfile.ZipFile(io.BytesIO(data)).read("3D/3dmodel.model").decode()
    total = 0.0
    for obj in re.findall(r"<object .*?</object>", xml, re.S):
        vs = [tuple(float(v) for v in m) for m in re.findall(r'<vertex x="([^"]+)" y="([^"]+)" z="([^"]+)"', obj)]
        total += tri_volume([[vs[int(i)] for i in m] for m in re.findall(r'<triangle v1="(\d+)" v2="(\d+)" v3="(\d+)"', obj)])
    return total


def drag_bar_to(rid, below=False):
    """The bar pressed and moved (real mouse) to the top edge of a row (below: its bottom edge), let go."""
    b, r = bar(), row(rid)
    by = b.rect["y"] + b.rect["height"] / 2
    ty = r.rect["y"] + (r.rect["height"] + 2 if below else -1)
    ActionChains(d, duration=40).move_to_element(b).click_and_hold().move_by_offset(0, (ty - by) / 2).move_by_offset(0, (ty - by) / 2).release().perform()
    settled()


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.setItem('auto3d-lang', 'cs')")
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Rollback")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])  # F1
    call("add_feature", type="extrude", sketch="F1", d=10)  # F2: the plate
    settled()
    call("add_feature", type="fillet", edges=[{"a": "F2:end", "b": "F2:side:l1", "fp": [30, 0, 10]}], r=2)  # F3
    settled()
    v2 = vol()
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 10, "y": 10, "d": 8}}])  # F4
    call("add_feature", type="extrude", sketch="F4", d=15)  # F5: a boss
    call("add_feature", type="sketch", plane={"datum": "XY", "offset": 10}, shapes=[{"circle": {"x": 50, "y": 30, "d": 5}}])  # F6
    call("add_feature", type="extrude", sketch="F6", op="cut", through=True)  # F7: a hole cut through
    settled()
    v4 = vol()
    print("steps:", ids(), "| volume after 2 steps", v2, "| after 4", v4)
    check("4 top-level steps, the bar under the last", top_rows() == ["F2", "F3", "F5", "F7", "|"], top_rows())
    h = bar().rect["height"]
    check("the bar is 6 px high", abs(h - 6) < 0.6, h)
    check("the bar: Czech tooltip, keyboard focusable", bar().get_attribute("title").startswith("Pruh vrácení stromu") and bar().get_attribute("tabindex") == "0",
          bar().get_attribute("title"))
    check("no end button at the end", not d.find_elements(By.CSS_SELECTOR, "#modelLeft .mt-rb-end"))
    d.save_screenshot(f"{OUT}/rb1_end.png")

    # ---- dragged above step 3: the part as after 2 steps
    drag_bar_to("F5")
    print("rows:", top_rows(), "| rollback:", js(f"return {M}.part.rollback"))
    check("the bar above step 3", top_rows() == ["F2", "F3", "|", "F5", "F7"], top_rows())
    check("volume = the 2-step volume", abs(vol() - v2) < 0.5, (vol(), v2))
    check("later rows greyed (with their sketches)", set(greyed()) == {"F4", "F5", "F6", "F7"}, greyed())
    gs = json.loads(call("gui_state"))
    rb = [s["id"] for s in gs["steps"] if s.get("state") == "rolled_back"]
    check("gui_state: steps rolled_back, the bar under F3", set(rb) == {"F4", "F5", "F6", "F7"} and gs.get("rollback_bar", {}).get("under") == "F3", (rb, gs.get("rollback_bar")))
    gm = json.loads(call("get_model"))
    check("get_model: rollback after F3", gm.get("rollback", {}).get("after") == "F3" and [s["id"] for s in gm["steps"] if s.get("rolled_back")] == ["F4", "F5", "F6", "F7"],
          gm.get("rollback"))
    end_txt = d.find_element(By.CSS_SELECTOR, "#modelLeft .mt-rb-end").text
    status = d.find_element(By.CSS_SELECTOR, "#modelViewport .m-status").text
    print("end box:", end_txt.replace("\n", " | "), "| status:", status)
    check("Czech: 'Potlačeno do konce: 4' + '⤓ Na konec'", "Potlačeno do konce: 4" in end_txt and "⤓ Na konec" in end_txt, end_txt)
    check("status line says it", "Vráceno za krok „Zaoblení 1“" in status, status)
    check("a greyed row's tooltip (Czech)", row("F5").get_attribute("title").startswith("Potlačeno do konce"), row("F5").get_attribute("title"))
    d.save_screenshot(f"{OUT}/rb2_rolled.png")

    # ---- a hole added: in at the bar (position 3), the bar under it
    r = call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=6)
    settled()
    order = ids()
    print("hole:", r[:80], "| order:", order)
    check("the hole inserted at position 3", order[3] == "F8" and order[:3] == ["F1", "F2", "F3"], order)
    check("the bar right under the hole", top_rows() == ["F2", "F3", "F8", "|", "F5", "F7"] and js(f"return {M}.part.rollback") == "F8", top_rows())
    check("volume = 2 steps − the hole", abs(vol() - (v2 - HOLE)) < 1, (vol(), v2 - HOLE))

    # ---- edits while rolled back: an earlier step (AI, then its panel's OK), a step under the bar (its preview)
    v_before = vol()
    call("edit_feature", id="F3", fields={"r": 3})
    settled()
    dF = vol() - v_before  # (the bigger round takes this much)
    check("an earlier step changed: rebuilt, still rolled back", js(f"return {M}.part.rollback") == "F8" and abs(vol() - v_before) > 1, (vol(), v_before))
    js(f"{M}.edit('F2')")
    settled()
    check("its panel open: the part up to the bar", js(f"return {M}.cmd?.feature.id") == "F2" and js(f"return {M}.shown().length") == 4)
    js(f"{M}.okCommand()")
    settled()
    v3 = vol()
    js(f"{M}.edit('F5')")
    settled()
    check("a step under the bar opened: shown up to it (the boss)", js(f"return {M}.shown().map(f => f.id).join()") == "F1,F2,F3,F8,F4,F5" and vol() > v3 + 100, vol())
    d.save_screenshot(f"{OUT}/rb2b_edit_under.png")
    js(f"{M}.cancelCommand()")
    settled()
    check("cancelled: back to the bar", js(f"return {M}.part.rollback") == "F8" and abs(vol() - v3) < 0.5, vol())

    # ---- reloaded: the bar where it was
    js("return window.__app.autosave.saveNow()")
    time.sleep(0.5)
    d.refresh()
    wait("return !!window.__app")
    wait("return document.querySelector('.restore-bar')", 10)
    d.find_element(By.CSS_SELECTOR, ".restore-bar [data-a=open]").click()
    wait(f"return window.__app.state.workspace === 'model' && !!{M}.result?.body", 30)
    settled()
    check("reload keeps the bar", js(f"return {M}.part.rollback") == "F8" and top_rows() == ["F2", "F3", "F8", "|", "F5", "F7"] and abs(vol() - v3) < 0.5,
          (js(f"return {M}.part.rollback"), top_rows(), vol()))

    # ---- right-click a row: Vrátit se sem
    ActionChains(d).context_click(row("F2")).perform()
    time.sleep(0.3)
    items = js("return [...document.querySelectorAll('.mt-ctx button')].map(b => b.textContent.trim())")
    print("menu:", items)
    check("context menu in Czech", "⏮ Vrátit se sem" in items and "⤓ Na konec" in items, items)
    d.save_screenshot(f"{OUT}/rb3_menu.png")
    ActionChains(d).send_keys(Keys.ESCAPE).perform()
    time.sleep(0.2)
    check("Esc closes it", not d.find_elements(By.CSS_SELECTOR, ".mt-ctx"))
    ActionChains(d).context_click(row("F2")).perform()
    time.sleep(0.3)
    d.find_element(By.CSS_SELECTOR, ".mt-ctx [data-a=rollHere]").click()
    settled()
    check("Vrátit se sem: the bar under the plate", top_rows() == ["F2", "|", "F3", "F8", "F5", "F7"] and js(f"return {M}.part.rollback") == "F2", top_rows())

    # ---- the keyboard: ↓ one step down
    bar().click()  # (focus; a click without moving leaves it where it is)
    settled()
    ActionChains(d).send_keys(Keys.ARROW_DOWN).perform()
    settled()
    check("↓ moves it one step down (focus kept)", top_rows() == ["F2", "F3", "|", "F8", "F5", "F7"] and js("return document.activeElement?.classList.contains('mt-rollbar')"),
          top_rows())
    ActionChains(d).double_click(bar()).perform()
    settled()
    check("double-click: to the end", top_rows()[-1] == "|" and not js(f"return {M}.part.rollback"), top_rows())
    js(f"return {M}.history.go(-1)")
    settled()
    check("Ctrl+Z: the bar back", js(f"return {M}.part.rollback") == "F3", js(f"return {M}.part.rollback"))

    # ---- dragged to the end: everything
    drag_bar_to("F7", below=True)
    print("rows:", top_rows(), "| volume", vol())
    check("dragged to the end: every step", top_rows() == ["F2", "F3", "F8", "F5", "F7", "|"] and not js(f"return {M}.part.rollback") and not greyed(), top_rows())
    check("volume = all 4 steps − the hole", abs(vol() - (v4 - HOLE + dF)) < 1, (vol(), v4 - HOLE + dF))
    check("no end box, no status note", not d.find_elements(By.CSS_SELECTOR, "#modelLeft .mt-rb-end") and not d.find_elements(By.CSS_SELECTOR, ".m-rb-note"))
    d.save_screenshot(f"{OUT}/rb4_end_again.png")

    # ---- the AI: rollback {to}
    r = json.loads(call("rollback", to="F2"))
    check("AI rollback to F2", r.get("rolled_back_after") == "F2" and top_rows()[:2] == ["F2", "|"], r)
    v_plate = vol()

    # ---- ⏮ exports follow the bar (as SolidWorks): the plate alone, said in Czech
    catch_saves()
    note = js("return document.querySelector('#modelRight .mp-rb-note')?.textContent || ''")
    print("panel note:", note)
    check("the part panel says it (Czech, the steps left out)",
          note.startswith("⏮ Podle posuvníku historie: bez posledních 4 kroků (") and "Zaoblení 1" in note and "Vysunutí 3" in note, note)
    d.find_element(By.ID, "exportBtn").click()
    time.sleep(0.3)
    menu = js("const m = document.getElementById('exportMenu'); return {rolled: m.classList.contains('rolled'), note: m.querySelector('.menu-note')?.textContent,"
              " mark: getComputedStyle(m.querySelector('[data-fmt=stl]'), '::after').content}")
    print("export menu:", menu)
    check("the Export menu: the note on top, each item marked ⏮", menu["rolled"] and (menu["note"] or "").startswith("⏮ Podle posuvníku historie") and "⏮" in menu["mark"], menu)
    d.save_screenshot(f"{OUT}/rb6_export_menu.png")
    d.find_element(By.CSS_SELECTOR, "#exportMenu [data-fmt=stl]").click()
    v_stl = stl_volume(saved(1))
    toast = wait("return [...document.querySelectorAll('.toast')].map(t => t.textContent).find(t => t.includes('Podle posuvníku')) || ''", 20)
    print("STL volume", round(v_stl, 1), "| plate", v_plate, "| toast:", toast)
    check("STL export = the rolled-back volume", abs(v_stl - v_plate) < 0.5, (v_stl, v_plate))
    check("the export's toast says it (Czech)", toast.startswith("Exportováno") and "⏮ Podle posuvníku historie: bez posledních 4 kroků" in toast, toast)
    d.find_element(By.ID, "exportBtn").click()
    time.sleep(0.2)
    d.find_element(By.CSS_SELECTOR, "#exportMenu [data-fmt='3mf']").click()
    v_3mf = mf_volume(saved(2))
    check("3MF export = the rolled-back volume", abs(v_3mf - v_plate) < 0.5, (v_3mf, v_plate))

    # ---- the print copy: the plate alone, its print panel says so; check_print too
    model_id = js("return window.__app.project.current.id")
    d.find_element(By.CSS_SELECTOR, "#modelRight [data-a=toPrint]").click()
    wait("return window.__app.state.workspace === 'quick' && window.__app.state.solution && document.querySelector('#rtab-print [data-a=split]')", 90)
    time.sleep(0.5)
    pnote = js("return document.querySelector('#rtab-print .print-rb-note')?.textContent || ''")
    print("print panel:", pnote)
    check("the print panel says the copy is rolled back (Czech)", pnote.startswith("⏮ Podle posuvníku historie: bez posledních 4 kroků"), pnote)
    cp = json.loads(call("check_print"))
    check("check_print: rolled_back, 10 mm high (no boss)", cp.get("rolled_back", "").startswith("⏮") and abs(cp["part_mm"][2] - 10) < 0.01, cp)
    d.save_screenshot(f"{OUT}/rb7_print_copy.png")
    d.find_element(By.CSS_SELECTOR, "#rtab-print [data-a=split]").click()
    wait("return window.__app.printPanel.pieces && !window.__app.printPanel.busy", 120)
    v_print = js("return window.__app.printPanel.pieces.reduce((s, p) => s + (p.exact?.volume || 0), 0)")
    check("the print copy's exact pieces = the rolled-back volume", abs(v_print - v_plate) < 0.5, (v_print, v_plate))

    # ---- an assembly shows the part as its bar stands (as SolidWorks), its panel says so
    call("new_assembly", name="RB asm")
    call("insert_part", part=model_id)
    wait("return window.__app.assembly.doc.instances.length && window.__app.assembly.bodyOf(window.__app.assembly.doc.instances[0])?.body", 60)
    v_asm = js("return window.__app.assembly.bodyOf(window.__app.assembly.doc.instances[0]).body.volume")
    check("the assembly places the rolled-back part", abs(v_asm - v_plate) < 0.5, (v_asm, v_plate))
    js("const a = window.__app.assembly; a.sel = a.doc.instances[0].id; a.renderProps()")
    anote = js("return document.querySelector('.as-rb-note')?.textContent || ''")
    print("assembly panel:", anote)
    check("the assembly part's panel: ⚠ Díl je vrácený v historii", anote.startswith("⚠ Díl je vrácený v historii: bez posledních 4 kroků"), anote)
    js("return window.__app.project.switchTo(arguments[0])", model_id)
    wait(f"return window.__app.state.workspace === 'model' && !!{M}.result?.body", 30)
    settled()
    # ---- a drawing sheet of it: drawn as the bar stands, its panel says so
    d.find_element(By.CSS_SELECTOR, "#modelRight [data-a=newSheet]").click()
    wait("return window.__app.state.workspace === 'sheet' && window.__app.sheet.d?.built", 90)
    time.sleep(0.5)
    snote = js("return document.querySelector('.sh-rb-note')?.textContent || ''")
    v_sheet = js("return window.__app.sheet.d.built.volume")
    print("sheet:", v_sheet, "|", snote)
    check("the drawing sheet: the plate, ⚠ Díl je vrácený v historii", abs(v_sheet - v_plate) < 0.5 and snote.startswith("⚠ Díl je vrácený v historii: bez posledních 4 kroků"), (v_sheet, snote))
    d.save_screenshot(f"{OUT}/rb8_sheet.png")
    js("return window.__app.project.switchTo(arguments[0])", model_id)
    wait(f"return window.__app.state.workspace === 'model' && !!{M}.result?.body", 30)
    settled()

    # ---- the bar at the end: every step, no note
    r = json.loads(call("rollback", to="end"))
    check("AI rollback to the end", "rollback" in r and abs(vol() - (v4 - HOLE + dF)) < 1, r)
    v_all = vol()
    d.find_element(By.ID, "exportBtn").click()
    time.sleep(0.3)
    menu = js("const m = document.getElementById('exportMenu'); return {rolled: m.classList.contains('rolled'), note: !!m.querySelector('.menu-note')}")
    check("at the end: no note, no marks in the Export menu", not menu["rolled"] and not menu["note"], menu)
    js("document.querySelectorAll('.toast').forEach(t => t.remove())")
    d.find_element(By.CSS_SELECTOR, "#exportMenu [data-fmt=stl]").click()
    v_stl = stl_volume(saved(3))
    time.sleep(0.3)
    toasts = js("return [...document.querySelectorAll('.toast')].map(t => t.textContent)")
    check("STL export at the end = every step", abs(v_stl - v_all) < 2, (v_stl, v_all))  # (a mesh: the hole facetted)
    check("no note in its toast, none in the part panel", toasts and not any("posuvníku" in t for t in toasts) and not d.find_elements(By.CSS_SELECTOR, ".mp-rb-note"), toasts)
    js("return window.__app.assembly && window.__app.project.switchTo(window.__app.project.parts.find(p => p.kind === 'assembly').id)")
    wait("return window.__app.state.workspace === 'assembly'", 30)
    wait(f"return Math.abs(window.__app.assembly.bodyOf(window.__app.assembly.doc.instances[0])?.body?.volume - {v_all}) < 0.5", 60)
    js("const a = window.__app.assembly; a.sel = a.doc.instances[0].id; a.renderProps()")
    check("the assembly follows: every step, no ⚠ note", not d.find_elements(By.CSS_SELECTOR, ".as-rb-note"))
    js("return window.__app.project.switchTo(window.__app.project.parts.find(p => p.kind === 'sheet').id)")
    wait(f"return window.__app.state.workspace === 'sheet' && Math.abs(window.__app.sheet.d.built?.volume - {v_all}) < 0.5", 90)
    time.sleep(0.3)
    check("the drawing sheet follows: every step, no ⚠ note", not d.find_elements(By.CSS_SELECTOR, ".sh-rb-note"))
    js("return window.__app.project.switchTo(arguments[0])", model_id)
    wait(f"return window.__app.state.workspace === 'model' && !!{M}.result?.body", 30)
    settled()
    check("AI: a wrong id refused", call("rollback", to="F99").startswith("ERROR"))
    time.sleep(0.3)
    d.save_screenshot(f"{OUT}/rb5_final.png")

    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    check("no console errors", not errs, errs[:3])
except Exception:  # noqa: BLE001 — shown, and counted as a failure
    traceback.print_exc()
    ok.append(False)
finally:
    print("ALL OK" if ok and all(ok) else f"FAILED ({ok.count(False)} of {len(ok)})")
    d.quit()
    sys.exit(0 if ok and all(ok) else 1)
