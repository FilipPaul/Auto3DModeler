"""☰ The project's tree, in headless Edge: Base, Lid, Pin, a sub-assembly "Lid unit" (Lid + 2 Pins), "Machine" (Base +
Lid unit), a drawing sheet of the Base, a loose part "Spare" -> ☰: the tree over the left panel — Machine, in it the
Base (its sheet under it) and the Lid unit (Lid, Pin ×2), then Spare -> a click on the Pin opens it (marked, the tree
stays) -> a part put in the Machine shows in the tree at once -> its ✕ arms a red "Delete?" (3 s; a second click or
Enter deletes, ↶ Undo brings it back) -> ▸ / ▾ fold a row with rows under it (remembered), 🔍 "zakladni" finds
"Základní deska" inside the folded Lid unit (opened for it, its rows lit; a click opens it; Esc: all again, the fold
back) -> ✕ closes the tree, ☰ again opens it (remembered after a reload).

  PYTHONIOENCODING=utf-8 py tools/e2e_project_tree.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

URL, OUT = sys.argv[1], sys.argv[2]
bad = []


def check(ok, what):
    print(("  ok   " if ok else "  FAIL ") + what)
    if not ok:
        bad.append(what)

opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1500,900")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
H = "window.__app.agentHandlers"
P = "window.__app.project"


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def tree():
    return js("""return [...document.querySelectorAll('#projTree .pt-row')].map(r =>
      `${'  '.repeat((parseFloat(r.style.paddingLeft) - 4) / 14)}${({model: '◆', assembly: '◇', sheet: '📄', drawing: '📐', classic: '▤'})[r.querySelector('.ico').classList[1].slice(4)]} ${r.querySelector('.pt-rname').textContent}${r.querySelector('.tr-qty')?.textContent ? ' ' + r.querySelector('.tr-qty').textContent : ''}${r.classList.contains('on') ? ' ←' : ''}`)""")


try:
    d.get(URL)
    time.sleep(2)
    js("localStorage.setItem('a3d.leftDock', JSON.stringify({project: 'popup'}))")  # (this test: the tree behind ☰ — docked is the default: e2e_left_pins)
    d.get(URL)
    time.sleep(2)
    for name in ("Base", "Lid", "Pin", "Spare", "Základní deska"):
        call("new_model", name=name)
        call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 30}}])
        call("add_feature", type="extrude", sketch="F1", d=5)
    call("new_assembly", name="Lid unit")
    for p in ("Lid", "Pin", "Pin", "Základní deska"):
        call("insert_part", part=p)
    call("new_assembly", name="Machine")
    call("insert_part", part="Base")
    call("insert_part", part="Lid unit")
    call("sheet_open", part="Base")
    time.sleep(1)
    js(f"{P}.switchTo({P}.parts.find(p => p.name === 'Machine').id)")
    time.sleep(1)
    d.find_element(By.CSS_SELECTOR, "#partTabs .pt-all").click()
    time.sleep(0.5)
    box = d.find_element(By.CSS_SELECTOR, "#projTree")
    left = d.find_element(By.CSS_SELECTOR, "#asmLeft").rect
    print("the tree over the left panel:", "open" in box.get_attribute("class"), abs(box.rect["x"] - left["x"]) < 2)
    print("\n".join(tree()))
    d.save_screenshot(f"{OUT}/project_tree.png")
    pin = next(r for r in d.find_elements(By.CSS_SELECTOR, "#projTree .pt-row") if r.find_element(By.CSS_SELECTOR, ".pt-rname").text == "Pin")
    pin.find_element(By.CSS_SELECTOR, ".pt-open").click()
    time.sleep(1)
    print("the Pin opened:", js(f"return {P}.current.name"), "| marked:", [r for r in tree() if r.endswith("←")], "| still open:", "open" in box.get_attribute("class"))
    js(f"{P}.switchTo({P}.parts.find(p => p.name === 'Machine').id)")
    time.sleep(1)
    call("insert_part", part="Spare")
    time.sleep(1)
    print("Spare put in the Machine:", [r for r in tree() if "Spare" in r])
    js("window.__asked = 0; window.confirm = () => { window.__asked++; return true; }")
    n = js(f"return {P}.parts.length")
    spare = next(r for r in d.find_elements(By.CSS_SELECTOR, "#projTree .pt-row") if r.find_element(By.CSS_SELECTOR, ".pt-rname").text == "Spare")
    x = spare.find_element(By.CSS_SELECTOR, ".pt-del")
    js("arguments[0].click()", x)
    time.sleep(0.3)
    print("✕ on Spare, 1st click: armed:", x.text, "armed" in x.get_attribute("class"), "| kept:", js(f"return {P}.parts.length") == n)
    ActionChains(d).move_to_element(spare.find_element(By.CSS_SELECTOR, ".pt-open")).perform()
    d.save_screenshot(f"{OUT}/project_tree_armed.png")
    time.sleep(3.3)
    print("  after 3 s: back to", x.text, "| kept:", js(f"return {P}.parts.length") == n)
    js("arguments[0].focus()", x)
    x.send_keys(Keys.ENTER)
    time.sleep(0.2)
    print("  Enter: armed:", x.text, "| kept:", js(f"return {P}.parts.length") == n)
    x.send_keys(Keys.ENTER)
    time.sleep(0.5)
    print("  Enter again: deleted:", n, "->", js(f"return {P}.parts.length"), "| asked:", js("return window.__asked"),
          "| ↶:", d.find_element(By.CSS_SELECTOR, "#projTree .tr-undo").text)
    d.find_element(By.CSS_SELECTOR, "#projTree .tr-undo").click()
    time.sleep(0.5)
    print("  ↶ Undo: back", js(f"return {P}.parts.length"), "| in the Machine again:", [r for r in tree() if "Spare" in r])
    # ▸ / ▾: a row with rows under it folds, remembered
    def row(name):
        return next(r for r in d.find_elements(By.CSS_SELECTOR, "#projTree .pt-row") if r.find_element(By.CSS_SELECTOR, ".pt-rname").text == name)
    n_all = len(tree())
    row("Lid unit").find_element(By.CSS_SELECTOR, "button.tr-tw").click()
    time.sleep(0.3)
    folded = tree()
    print("Lid unit folded:", folded)
    check(len(folded) == n_all - 3 and not any("Pin" in r for r in folded) and row("Lid unit").find_element(By.CSS_SELECTOR, ".tr-tw").text == "▸",
          f"▸ folds the Lid unit: its 3 rows hidden ({n_all} -> {len(folded)})")
    check(len(json.loads(js("return localStorage.getItem('a3d.projFold')") or "{}")) == 1, "the fold remembered (a3d.projFold, per project)")
    row("Machine").find_element(By.CSS_SELECTOR, "button.tr-tw").click()
    time.sleep(0.3)
    check([r.replace(" ←", "").strip() for r in tree()] == ["◇ Machine"], f"▸ Machine: only its row ({tree()})")
    row("Machine").find_element(By.CSS_SELECTOR, "button.tr-tw").click()
    time.sleep(0.3)
    # 🔍 the same find as the assembly's list: no accents, no case; the rows they are in opened for it
    find = d.find_element(By.CSS_SELECTOR, "#projTree .tr-find")
    check(find.get_attribute("placeholder") == "Find a part…", "🔍 in the tree's header")
    find.send_keys("zakladni")
    time.sleep(0.6)
    found = tree()
    print("🔍 zakladni:", found)
    hits = js("return [...document.querySelectorAll('#projTree .pt-row.tr-hit .pt-rname')].map(e => e.textContent)")
    check([r.replace(" ←", "").strip() for r in found] == ["◇ Machine", "◇ Lid unit", "◆ Základní deska"] and hits == ["Základní deska"],
          "🔍 'zakladni': Základní deska and the assemblies it is in (Lid unit opened though folded), lit")
    row("Základní deska").find_element(By.CSS_SELECTOR, ".pt-open").click()
    time.sleep(1)
    check(js(f"return {P}.current.name") == "Základní deska", "a click on the row found opens it")
    find = d.find_element(By.CSS_SELECTOR, "#projTree .tr-find")
    js("arguments[0].focus()", find)
    find.send_keys(Keys.ESCAPE)
    time.sleep(0.4)
    check(len(tree()) == n_all - 3 and not find.get_attribute("value"), f"Esc: every row again, the Lid unit folded as it was ({len(tree())})")
    row("Lid unit").find_element(By.CSS_SELECTOR, "button.tr-tw").click()
    time.sleep(0.3)
    check(len(tree()) == n_all, "▾ again: its rows back")
    d.save_screenshot(f"{OUT}/project_tree_find.png")
    d.find_element(By.CSS_SELECTOR, "#projTree .tr-x").click()
    time.sleep(0.3)
    print("✕ closes it:", "open" not in box.get_attribute("class"))
    d.find_element(By.CSS_SELECTOR, "#partTabs .pt-all").click()
    time.sleep(0.3)
    print("☰ opens it again:", "open" in d.find_element(By.CSS_SELECTOR, "#projTree").get_attribute("class"),
          "| remembered:", js("return localStorage.getItem('a3d.tree')"))
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        bad.append("console errors")
    d.quit()
print("FAILED:", bad if bad else "none")
sys.exit(1 if bad else 0)
