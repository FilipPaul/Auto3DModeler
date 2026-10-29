"""The assembly's basic tasks done only from the Suggested table, in Czech, with real mouse clicks, at 1280×800: the
crank demo's parts in a new empty assembly — it offers them (＋ Základna: one click, fixed) -> ＋ Klika from the whole
assembly's table, chosen: ◎ Onto the pin of Základna · Ø10 first (one click: concentric and seated) -> ＋ Ojnice: ◎ onto
the crank's pin -> ＋ Smýkadlo: ⧉ Put it on Základna, ◎ Into the hole of Ojnice: a closed loop, every joint holds ->
🏷 Rename it (typed) -> Esc: the whole assembly's table: ⚙ Drive the mechanism, 💥 Explode / Put it back together,
✂ Section on / off, ⚠ collisions (the list), 📏 Measure distances, 📋 Bill of materials (its window), ✕ Take it out
(Ctrl+Z back), 📄 Drawing of the assembly (its sheet) — each task's clicks counted. Also: the toolbar in at most 2
rows at 1280, 🔗 Joint ▾ menu (Esc closes it), the part panel's look folded, the overview's joints folded.

  PYTHONIOENCODING=utf-8 py tools/e2e_ux_assembly.py http://127.0.0.1:5199 <out dir>
"""
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1280,800")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
A = "window.__app.assembly"
H = "window.__app.agentHandlers"
bad, clicks = [], {}


def check(ok, what):
    print(("  ok  " if ok else "  FAIL") + " " + what)
    if not ok:
        bad.append(what)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(script)


def table():
    """The Suggested table: [title, rows …] (None: no table)."""
    box = d.find_elements(By.CSS_SELECTOR, "#asmViewport .view-suggest")
    if not box:
        return None
    return [box[0].find_element(By.CSS_SELECTOR, ".vs-head b").text] + [" ".join(b.text.split()) for b in box[0].find_elements(By.CSS_SELECTOR, ".vs-list button")]


def suggest(task, label, first=False):
    """Click the table's row that holds `label` (a real click) — `first`: it must be the top row. Counted for `task`."""
    tb = table() or []
    rows = tb[1:]
    hit = next((i for i, r in enumerate(rows) if label in r), None)
    check(hit is not None and (not first or hit == 0), f"{task}: “{label}” {'first ' if first else ''}in the table {tb}")
    if hit is None:
        return False
    d.find_elements(By.CSS_SELECTOR, "#asmViewport .view-suggest .vs-list button")[hit].click()
    clicks[task] = clicks.get(task, 0) + 1
    time.sleep(0.8)
    return True


def esc():
    ActionChains(d).send_keys(Keys.ESCAPE).perform()
    time.sleep(0.5)


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.setItem('auto3d-lang', 'cs'); sessionStorage.removeItem('a3d.suggestAll')")
    d.get(URL)
    wait("return !!window.__app && document.documentElement.lang === 'cs'")
    # the crank demo's four parts (Open ▾ → Demo projects…), then a new empty assembly of the project
    d.find_element(By.ID, "openBtn").click()
    time.sleep(0.2)
    js("document.getElementById('demoBtn').click()")
    wait("return document.querySelectorAll('.demos [data-demo]').length")
    row = next(r for r in d.find_elements(By.CSS_SELECTOR, ".demos [data-demo]") if "klikov" in r.get_attribute("data-demo"))
    row.find_element(By.CSS_SELECTOR, "[data-open]").click()
    wait(f"return window.__app.state.workspace === 'assembly' && {A}.doc.instances.length === 4 && {A}.doc.instances.every(i => {A}.bodies[i.part]?.body)")
    time.sleep(1)
    d.find_element(By.CSS_SELECTOR, ".pt-add").click()
    time.sleep(0.3)
    d.find_element(By.CSS_SELECTOR, ".part-add [data-new=assembly]").click()
    wait(f"return {A}.doc.instances.length === 0")
    time.sleep(0.8)

    # 1 an empty assembly: the project's parts, one click each
    tb = table()
    print("empty:", tb)
    check(tb and tb[1:5] == ["＋ Základna", "＋ Klika", "＋ Ojnice", "＋ Smýkadlo"], f"an empty assembly suggests its parts (3D models first): {tb}")
    d.save_screenshot(f"{OUT}/ux_asm_1_empty.png")
    suggest("insert a part", "＋ Základna", first=True)
    wait(f"return {A}.doc.instances.length === 1 && Object.values({A}.bodies).every(b => b.body)")
    check(js(f"return !!{A}.inst('I1').fixed"), "the first part is fixed")

    def insert(name):
        esc()
        suggest("insert a part", "＋ " + name)
        wait(f"return {A}.doc.instances.at(-1) && Object.values({A}.bodies).every(b => b.body) && {A}.sel === {A}.doc.instances.at(-1).id")
        time.sleep(0.8)
        print(f"{name}:", table())

    def mates():
        return js(f"return {A}.doc.mates.map(m => [m.type, m.move, m.onto])")

    # 2 the crank onto the base's pin, the rod onto the crank's pin: each the first suggestion when inserted
    insert("Klika")
    d.save_screenshot(f"{OUT}/ux_asm_2_crank.png")
    suggest("pin into a hole", "◎ Na čep Základna · Ø10", first=True)
    check(mates() == [["axis", "I2", "I1"], ["touch", "I2", "I1"]], f"◎ the crank on the base's pin, seated: {mates()}")
    insert("Ojnice")
    suggest("pin into a hole", "◎ Na čep Klika · Ø8", first=True)
    check(mates()[2:] == [["axis", "I3", "I2"], ["touch", "I3", "I2"]], f"◎ the rod on the crank's pin, seated: {mates()[2:]}")

    # 3 the slider put on the base, its pin into the rod's other hole: the loop closes
    insert("Smýkadlo")
    suggest("put a part on a face", "⧉ Položit na Základna")
    check(mates()[4:] == [["touch", "I4", "I1"]], f"⧉ the slider on the base: {mates()[4:]}")
    js(f"{A}.choose('I4')")
    time.sleep(0.5)
    suggest("pin into a hole", "◎ Do díry v Ojnice · Ø8", first=True)
    loops = js(f"return ({A}.loops || []).map(l => [l.parts, l.closed])")
    held = js(f"return [...({A}.health || new Map()).values()].every(h => h.ok)")
    check(mates()[5:] == [["axis", "I4", "I3"]] and loops and loops[0][1] and held, f"◎ the slider's pin in the rod: a closed loop {loops}, every joint holds: {held}")
    d.save_screenshot(f"{OUT}/ux_asm_3_loop.png")

    # 4 rename (still chosen)
    js(f"{A}.choose('I4')")
    time.sleep(0.4)
    if suggest("rename", "Přejmenovat"):
        ed = d.switch_to.active_element
        ed.send_keys(Keys.CONTROL, "a")
        ed.send_keys("Jezdec", Keys.ENTER)
        clicks["rename"] += 1  # (typing it, Enter)
        time.sleep(0.6)
    check(js(f"return {A}.partName({A}.inst('I4').part)") == "Jezdec", f"🏷 renamed: {js(f'return {A}.partName({A}.inst(arguments[0]).part)', 'I4')}")

    # 5 the whole assembly: Esc -> its table
    esc()
    tb = table()
    name0 = js("return window.__app.project.current.name")
    print("the whole assembly:", tb)
    check(tb and tb[0] == name0 and js(f"return !{A}.sel"), f"Esc: nothing chosen, the assembly's table: {tb and tb[0]}")
    d.save_screenshot(f"{OUT}/ux_asm_3_overview.png")
    check(js("return document.querySelector('#asmRight .as-jfold') && !document.querySelector('#asmRight .as-jfold').open"), "the overview's joints folded (🔗 Vazby (n))")
    if any("Ovládat mechanismus" in r for r in tb[1:]):
        suggest("drive the mechanism", "Ovládat mechanismus")
        check(bool(d.find_elements(By.CSS_SELECTOR, "#leftCol .lw-widget[data-w=mech], #asmViewport .lw-widget[data-w=mech]")), "⚙ the mechanism widget is there")
    else:
        check(False, f"⚙ Drive the mechanism offered (the crank turns): {tb}")

    suggest("explode", "Rozložit")
    check(js(f"return {A}.explode") > 0, f"💥 exploded: {js(f'return {A}.explode')}")
    d.save_screenshot(f"{OUT}/ux_asm_4_exploded.png")
    suggest("explode", "Složit zpět")
    check(js(f"return {A}.explode") == 0, "💥 back together")

    suggest("section", "Řez")
    check(js(f"return !!{A}.section"), "✂ section on")
    suggest("section", "Vypnout řez")
    check(js(f"return !{A}.section"), "✂ section off")

    suggest("check collisions", "kolize")
    wait(f"return {A}.clashes !== undefined && {A}.clashes !== null", 30)
    check(js(f"return !!{A}.clashPanel"), f"⚠ the collisions' list open ({js(f'return {A}.clashes.length')} found)")
    esc()
    check(js(f"return !{A}.clashPanel") and table(), "Esc closes the list, the table is back")

    suggest("measure", "Změřit vzdálenost")
    check(js(f"return !!{A}.measuring") and not table(), "📏 measuring (the table out of the way)")
    esc()
    check(js(f"return !{A}.measuring") and table(), "Esc: measuring ends, the table is back")

    suggest("BOM", "Kusovník")
    check(bool(d.find_elements(By.CSS_SELECTOR, ".bom-back")), "📋 the BOM window")
    d.save_screenshot(f"{OUT}/ux_asm_5_bom.png")
    esc()

    # 6 a part taken out and back
    js(f"{A}.choose('I4')")
    time.sleep(0.4)
    suggest("remove", "Vyjmout")
    check(js(f"return {A}.doc.instances.length") == 3, "✕ taken out")
    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    time.sleep(0.8)
    check(js(f"return {A}.doc.instances.length") == 4, "Ctrl+Z: it is back")

    # 7 the toolbar: at most 2 rows at 1280; its menus
    rows = js("""const bar = document.querySelector('#asmViewport > .m-cmdbar'), tops = [];
      for (const e of bar.children) if (e.offsetWidth > 2) tops.push(Math.round(e.getBoundingClientRect().top)); return tops""")
    check(len({round(y / 12) for y in rows}) <= 2, f"the toolbar: at most 2 rows at 1280 (its tops {rows})")
    d.find_element(By.CSS_SELECTOR, "#asmViewport [data-a=joints]").click()
    time.sleep(0.3)
    jl = [b.text for b in d.find_elements(By.CSS_SELECTOR, "#asmViewport .as-jlist [data-joint]")]
    check(len(jl) >= 8 and "◎ Soustředně" in jl, f"🔗 Vazba ▾: the joint types {jl}")
    d.save_screenshot(f"{OUT}/ux_asm_6_jointmenu.png")
    esc()
    check(not d.find_elements(By.CSS_SELECTOR, "#asmViewport .m-cmdbar .menu.open"), "Esc closes the menu")

    # 8 a part's panel: its look folded
    js(f"{A}.choose('I2')")
    time.sleep(0.4)
    check(js("const m = document.querySelector('#asmRight .as-more'); return !!m && !m.open"), "the part's look and editing folded")
    d.save_screenshot(f"{OUT}/ux_asm_7_part.png")
    esc()

    # 9 the drawing of the assembly (last: it opens its sheet)
    suggest("drawing", "Výkres sestavy")
    wait("return window.__app.state.workspace !== 'assembly'", 20)
    check(True, f"📄 the assembly's drawing sheet: {js('return window.__app.state.workspace')}")
    print("clicks per task:", clicks)
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    js("localStorage.removeItem('auto3d-lang'); sessionStorage.removeItem('a3d.suggestAll')")
    d.quit()
if errs:
    bad.append("console errors")
print("FAILED:" if bad else "ALL OK", bad if bad else "")
sys.exit(1 if bad else 0)
