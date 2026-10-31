"""📂 Open ▾ and Export ▾ in sections, in headless Edge (1600×1000, then a narrow window): Open has its sections
(Projekt, Ukázky, Import · CAD a 3D, · 2D výkresy, · DPS) with an icon and a hint per item, all in Czech; each import
item opens a file input filtered to its types; a STEP through 🧊 STEP / IGES opens a 3D model, a DXF through 📐 DXF / DWG
and a Gerber .zip through 🟩 Gerber open 2D drawings; 🕘 the last project shows inline with its picture. Export has
3D, 2D / výkresy, Data, Projekt: in a 3D model the assembly's and the sheet's items are greyed with their reason (and a
click on one does nothing), in a 2D drawing only DXF (and the project) is lit; an assembly, a sheet, a quick part: their own. The keys: ↓ on the button opens, ↑↓
←→ Home End move, greyed items are skipped, Enter runs one, Esc closes; a click outside closes. A narrow window: one
column, inside the window. In a demo assembly: BOM CSV / Excel and the drawing set saved. No console errors, no native dialogs.

  PYTHONIOENCODING=utf-8 py tools/e2e_open_menu.py http://127.0.0.1:5199 <out dir>
"""
import os
import sys
import time
import zipfile
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

URL, OUT = sys.argv[1], sys.argv[2]
ROOT = Path(__file__).resolve().parent.parent
STEP = str(ROOT / "samples" / "ExportFromOurApp" / "part_base_plate.step")
DXF = str(ROOT / "samples" / "ToImportToOurApp" / "drawings" / "Finger.dxf")
os.makedirs(OUT, exist_ok=True)
HEAD = "%FSLAX36Y36*%%MOMM*%"
GERBER = os.path.abspath(os.path.join(OUT, "open_menu_board.zip"))
with zipfile.ZipFile(GERBER, "w") as z:  # (no board in samples/: a small Gerber set, as e2e_pcb makes it)
    z.writestr("board/b.GTL", HEAD + "%ADD10C,0.25*%D10*X5000000Y5000000D02*X25000000Y5000000D01*M02*")
    z.writestr("board/b.GKO", HEAD + "%ADD10C,0.1*%D10*X0Y0D02*X30000000Y0D01*X30000000Y20000000D01*X0Y20000000D01*X0Y0D01*M02*")
    z.writestr("board/b.DRL", "M48\nMETRIC,LZ,000.000\nT1C0.8\n%\nT1\nX005000Y005000\nM30\n")

opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
FAILS = []
# a native dialog is counted, not shown; a file input's click is noted (the file is then given to that input)
d.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": """
  window.__native = 0; for (const k of ['alert', 'confirm', 'prompt']) window[k] = () => { window.__native++; return true; };
  const click = HTMLInputElement.prototype.click;
  HTMLInputElement.prototype.click = function () { if (this.type === 'file') { window.__picked = this.id; return; } return click.call(this); };
"""})


def check(name, ok, info=""):
    print(("  ok   " if ok else "  FAIL ") + name + (f"  [{info}]" if info and not ok else ""))
    if not ok:
        FAILS.append(name)


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def open_menu(btn="openBtn"):
    if not js(f"return document.getElementById('{btn}').parentElement.classList.contains('open')"):
        d.find_element(By.ID, btn).click()
    time.sleep(0.3)


def is_open(btn="openBtn"):
    return js(f"return document.getElementById('{btn}').parentElement.classList.contains('open')")


TEXTS = """return [...document.querySelectorAll(arguments[0] + ' h4, ' + arguments[0] + ' .fm-t b, ' + arguments[0] + ' .fm-t small')]
  .map((e) => e.textContent.trim())"""
SAME = {"STEP / IGES", "STL / OBJ / 3MF", "DXF / DWG", "Gerber", "ODB++", "3D", "Data", "STEP", "IGES", "STL", "GLB", "OBJ", "DXF"}


def pick(label):
    """The Open item whose name is `label`: clicked -> the id of the file input it opened."""
    open_menu()
    js("window.__picked = null")
    b = next(x for x in d.find_elements(By.CSS_SELECTOR, "#openMenu .fm-item") if x.find_element(By.CSS_SELECTOR, ".fm-t b").text == label)
    b.click()
    got = wait("return window.__picked", 5)
    time.sleep(0.1)  # (the menu closes right after the click)
    return got


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.setItem('auto3d-lang', 'en')")
    d.get(URL)
    wait("return !!window.__app && !!window.__app.autosave")
    time.sleep(1)
    en = {"open": js(TEXTS, "#openMenu"), "export": js(TEXTS, "#exportMenu")}
    d.find_element(By.ID, "langBtn").click()
    time.sleep(0.6)
    cs = {"open": js(TEXTS, "#openMenu"), "export": js(TEXTS, "#exportMenu")}
    left = [a for k in en for a, b in zip(en[k], cs[k]) if a == b and a not in SAME]
    check("every name, hint and header of both menus in Czech", not left and len(en["open"]) == len(cs["open"]) > 30, (left, len(en["open"])))

    # ---------------------------------------------------------------- 📂 Open ▾: sections, icons, hints
    open_menu()
    heads = [h.text for h in d.find_elements(By.CSS_SELECTOR, "#openMenu h4")]
    check("Open ▾: Projekt, Ukázky, Import · CAD a 3D, · 2D výkresy, · DPS",
          [h.upper() for h in heads] == ["PROJEKT", "UKÁZKY", "IMPORT · CAD A 3D", "IMPORT · 2D VÝKRESY", "IMPORT · DPS"], heads)
    items = js("""return [...document.querySelectorAll('#openMenu .fm-item')].map((b) => ({ id: b.id, icon: b.querySelector('.fm-i')?.textContent.trim(),
      name: b.querySelector('.fm-t b')?.textContent, hint: b.querySelector('.fm-hint')?.textContent, pick: b.dataset.pick || '' }))""")
    check("each item: an icon, a name and a hint", all(i["icon"] and i["name"] and i["hint"] for i in items), [i for i in items if not (i["icon"] and i["hint"])])
    names = [i["name"] for i in items]
    for want in ["Otevřít libovolný soubor…", "Nový projekt", "Otevřít projekt (.a3d)…", "Nedávné projekty…", "Zavřít projekt", "Ukázkové projekty…",
                 "STEP / IGES", "STL / OBJ / 3MF", "DXF / DWG", "PDF výkres (parametrický)", "Obrázek → obrys", "Gerber", "Složka Gerber…", "ODB++"]:
        check(f"Open ▾ has „{want}“", want in names, names)
    check("the kept ids: #openAnyBtn, #newProjectBtn, #recentBtn, #demoBtn, #closeProjectBtn, #sampleBtn",
          all(js(f"return !!document.querySelector('#openMenu #{i}')") for i in ["openAnyBtn", "newProjectBtn", "recentBtn", "demoBtn", "closeProjectBtn", "sampleBtn"]))
    d.save_screenshot(f"{OUT}/open_menu_1_cs.png")

    # each import item: its own file input, filtered to its types
    ACCEPT = {"STEP / IGES": ("stepInput", {".step", ".stp", ".igs", ".iges"}), "STL / OBJ / 3MF": ("meshInput", {".stl", ".obj", ".3mf"}),
              "DXF / DWG": ("dxfInput", {".dxf", ".dwg"}), "PDF výkres (parametrický)": ("pdfInput", {".pdf"}), "Obrázek → obrys": ("imgInput", {"image/*"}),
              "Gerber": ("gerberInput", {".zip", ".gbr", ".gtl", ".drl"}), "ODB++": ("odbInput", {".tgz", ".zip"}), "Otevřít projekt (.a3d)…": ("projectInput", {".a3d"})}
    for label, (iid, want) in ACCEPT.items():
        got = pick(label)
        acc = set(js(f"return document.getElementById('{got}').accept").split(","))
        only = iid in ("stepInput", "meshInput", "dxfInput", "projectInput")  # (only its own types)
        check(f"{label} -> #{iid}, accept has {sorted(want)}", got == iid and want <= acc and (not only or acc == want), (got, acc))
        check(f"{label}: a choice closes the menu", wait("return !document.getElementById('openMenuWrap').classList.contains('open')", 3))
    got = pick("Složka Gerber…")
    check("Složka Gerber… -> a folder input", got == "gerberDirInput" and js("return document.getElementById('gerberDirInput').webkitdirectory"), got)

    # a STEP through 🧊, a DXF through 📐, a Gerber .zip through 🟩
    n = js("return window.__app.project.parts.length")
    d.find_element(By.ID, pick("STEP / IGES")).send_keys(STEP)
    wait(f"return window.__app.project.parts.length > {n} && window.__app.state.workspace === 'model' && window.__app.modeler.hasBody()", 90)
    check("🧊 STEP / IGES: the STEP opens as a 3D model", js("return window.__app.modeler.result.body.volume") > 0)
    time.sleep(0.5)

    # ---------------------------------------------------------------- Export ▾ in a 3D model
    open_menu("exportBtn")
    xheads = [h.text.upper() for h in d.find_elements(By.CSS_SELECTOR, "#exportMenu h4")]
    check("Export ▾: 3D, 2D / výkresy, Data, Projekt", xheads == ["3D", "2D / VÝKRESY", "DATA", "PROJEKT"], xheads)
    st = js("""return Object.fromEntries([...document.querySelectorAll('#exportMenu [data-fmt]')].map((b) => [b.dataset.fmt,
      { off: b.classList.contains('off'), aria: b.getAttribute('aria-disabled'), why: getComputedStyle(b.querySelector('.fm-why')).display !== 'none' ? b.querySelector('.fm-why').textContent : '' }]))""")
    on = sorted(k for k, v in st.items() if not v["off"])
    check("a 3D model: STEP, IGES, STL, 3MF, GLB, OBJ, PDF, the project lit", on == sorted(["step", "iges", "stl", "3mf", "glb", "obj", "pdf", "a3d"]), on)
    check("… the drawing set, DXF, print and BOM greyed, with their reason in Czech",
          all(st[k]["off"] and st[k]["aria"] == "true" and st[k]["why"].startswith("Pro ") for k in ["pdfset", "dxf", "print", "bomcsv", "bomxlsx"]), st)
    d.save_screenshot(f"{OUT}/open_menu_2_export_model.png")
    # the other workspaces (their own tests open them): what markExport lights there
    d.set_script_timeout(10)
    asm = d.execute_async_script("""const done = arguments[arguments.length - 1];
      import('/js/filemenus.js').then((m) => { const on = (ws) => { m.markExport(ws); return [...document.querySelectorAll('#exportMenu [data-fmt]:not(.off)')].map((b) => b.dataset.fmt).sort(); };
        const r = { assembly: on('assembly'), sheet: on('sheet'), quick: on('quick') }; m.markExport('model'); done(r); });""")
    check("an assembly: 3D but OBJ, the drawing set, the BOM, the project", asm["assembly"] == sorted(["step", "iges", "stl", "3mf", "glb", "pdfset", "bomcsv", "bomxlsx", "a3d"]), asm["assembly"])
    check("a drawing sheet: PDF, DXF, print, the project", asm["sheet"] == sorted(["pdf", "dxf", "print", "a3d"]), asm["sheet"])
    check("a quick part: STEP, STL, GLB, the project", asm["quick"] == sorted(["step", "stl", "glb", "a3d"]), asm["quick"])
    d.find_element(By.CSS_SELECTOR, "#exportMenu [data-fmt=bomcsv]").click()
    time.sleep(0.3)
    check("a click on a greyed item: nothing, the menu stays", is_open("exportBtn") and not js("return !!document.querySelector('.busy-card, .busy.on')"))
    # keys: ↓ skips the greyed items
    js("document.querySelector('#exportMenu [data-fmt=obj]').focus()")
    d.switch_to.active_element.send_keys(Keys.ARROW_DOWN)
    check("Export ▾ ↓ from OBJ: PDF (next lit)", js("return document.activeElement.dataset.fmt") == "pdf", js("return document.activeElement.dataset.fmt"))
    d.switch_to.active_element.send_keys(Keys.ARROW_DOWN)
    check("… ↓ again: skips the greyed ones to the project", js("return document.activeElement.dataset.fmt") == "a3d", js("return document.activeElement.dataset.fmt"))
    d.switch_to.active_element.send_keys(Keys.ESCAPE)
    check("Esc closes Export ▾, the focus back on its button", not is_open("exportBtn") and js("return document.activeElement.id") == "exportBtn")

    n = js("return window.__app.project.parts.length")
    d.find_element(By.ID, pick("DXF / DWG")).send_keys(DXF)
    wait(f"return window.__app.project.parts.length > {n} && window.__app.state.workspace === 'drawing'", 60)
    check("📐 DXF / DWG: the DXF opens as a 2D drawing", js("return window.__app.drawing2d.d.entities.length") > 0)
    open_menu("exportBtn")
    on = sorted(js("return [...document.querySelectorAll('#exportMenu [data-fmt]:not(.off)')].map((b) => b.dataset.fmt)"))
    check("a 2D drawing: only DXF and the project lit", on == ["a3d", "dxf"], on)
    d.find_element(By.TAG_NAME, "body").click()
    time.sleep(0.2)
    check("a click outside closes Export ▾", not is_open("exportBtn"))

    n = js("return window.__app.project.parts.length")
    d.find_element(By.ID, pick("Gerber")).send_keys(GERBER)
    wait(f"return window.__app.project.parts.length > {n} && window.__app.state.workspace === 'drawing' && window.__app.drawing2d.d.pcb", 60)
    check("🟩 Gerber: the .zip opens as a board", js("return window.__app.drawing2d.d.layers.length") >= 2)
    time.sleep(3)  # (autosaved: the project is kept on the server)

    # ---------------------------------------------------------------- the keys in 📂 Open ▾
    own = js("const a = window.__app.autosave, id = a.id; a.id = 'other-window'; return id")  # (the project on screen as another one: in 🕘)
    d.find_element(By.ID, "openBtn").click()
    wait("return document.querySelectorAll('#openRecent .fm-proj').length", 10)
    check("🕘 the last project inline, with its picture", js("return !!document.querySelector('#openRecent .fm-proj img, #openRecent .fm-proj .fm-thumb')"))
    d.save_screenshot(f"{OUT}/open_menu_3_recent.png")
    js("window.__app.autosave.id = arguments[0]", own)
    time.sleep(0.2)
    check("opened: the first item has the focus", js("return document.activeElement.id") == "openAnyBtn", js("return document.activeElement.id"))
    a = d.switch_to.active_element
    a.send_keys(Keys.ARROW_DOWN)
    check("↓: 📄 Nový projekt", js("return document.activeElement.id") == "newProjectBtn")
    d.switch_to.active_element.send_keys(Keys.ARROW_RIGHT)
    right = js("return document.activeElement.querySelector('.fm-t b')?.textContent")
    check("→: the other column (Import · CAD a 3D)", right in ("STEP / IGES", "STL / OBJ / 3MF"), right)
    d.switch_to.active_element.send_keys(Keys.ARROW_LEFT)
    check("←: back to the Projekt column", js("return document.activeElement.closest('.fm-sec')?.querySelector('h4').textContent") == "Projekt")
    d.switch_to.active_element.send_keys(Keys.END)
    check("End: ODB++", js("return document.activeElement.querySelector('.fm-t b').textContent") == "ODB++")
    d.switch_to.active_element.send_keys(Keys.HOME)
    check("Home: the first item", js("return document.activeElement.id") == "openAnyBtn")
    d.switch_to.active_element.send_keys(Keys.ARROW_UP)
    check("↑ from the first: round to the last", js("return document.activeElement.querySelector('.fm-t b').textContent") == "ODB++")
    d.switch_to.active_element.send_keys(Keys.ESCAPE)
    check("Esc closes, the focus back on 📂", not is_open() and js("return document.activeElement.id") == "openBtn")
    d.switch_to.active_element.send_keys(Keys.ARROW_DOWN)
    time.sleep(0.2)
    check("↓ on 📂 opens it", is_open())
    js("document.getElementById('demoBtn').focus()")
    d.switch_to.active_element.send_keys(Keys.ENTER)
    wait("return document.querySelectorAll('.demos [data-demo]').length", 20)
    check("Enter on 🎬 Ukázkové projekty: the gallery, the menu closed", not is_open())

    # ---------------------------------------------------------------- Export ▾ in an assembly (a demo): BOM, drawing set
    d.find_element(By.CSS_SELECTOR, ".demos [data-open]").click()
    wait("return window.__app.state.workspace === 'assembly' && window.__app.assembly.hasBody() && !document.getElementById('exportBtn').disabled", 150)
    check("a demo assembly opened: Export ▾ enabled once its bodies are built", True)
    js("""window.__saved = []; window.showSaveFilePicker = async (o) => ({ name: o.suggestedName,
      createWritable: async () => ({ write: async (b) => { window.__saved.push([o.suggestedName, b.size]); }, close: async () => {} }) });""")
    xlsx = js("return fetch('/api/bom/xlsx').then((r) => r.json()).then((j) => !!j.available)")
    for fmt, ext in [("bomcsv", ".csv"), ("bomxlsx", ".xlsx"), ("pdfset", ".pdf")]:
        if fmt == "bomxlsx" and not xlsx:
            print("  (no openpyxl on the server: BOM — Excel not tried)")
            continue
        n = js("return window.__saved.length")
        open_menu("exportBtn")
        d.find_element(By.CSS_SELECTOR, f"#exportMenu [data-fmt={fmt}]").click()
        got = wait(f"return window.__saved.length > {n} && window.__saved[window.__saved.length - 1]", 90)
        check(f"Export ▾ › {fmt}: {got[0]}", got[0].endswith(ext) and got[1] > 100, got)

    # ---------------------------------------------------------------- a narrow window: one column, in the window
    d.set_window_size(700, 900)
    time.sleep(0.6)
    open_menu()
    r = js("""const m = document.getElementById('openMenu').getBoundingClientRect(), c = [...document.querySelectorAll('#openMenu .fm-col')].map((e) => e.getBoundingClientRect().left);
      return { l: m.left, r: m.right, w: innerWidth, cols: c }""")
    check("narrow: inside the window", r["l"] >= 0 and r["r"] <= r["w"], r)
    check("narrow: one column", len(r["cols"]) == 2 and abs(r["cols"][0] - r["cols"][1]) < 2, r)
    d.save_screenshot(f"{OUT}/open_menu_4_narrow.png")

    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE" and "favicon" not in e["message"]]
    check("no errors in the console", not errs, errs[:3])
    check("no native dialogs", js("return window.__native") == 0)
finally:
    d.quit()
print("FAILED:" if FAILS else "ALL OK", FAILS)
sys.exit(1 if FAILS else 0)
