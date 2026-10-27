"""Is the drawing fully dimensioned? — the sheet's check, in headless Edge: a plate 40 × 20 × 10 with 8 holes Ø3 in a grid
-> medium: ✓ fully dimensioned, every view ✓ -> the row's pitch deleted: sizes missing (the holes' places), the views
say ⚠ n, orange ? marks on the drawing (not in the PDF) -> ＋ on one missing: one fewer -> ＋ Add all missing: ✓ again
-> a dimension of the user's that the sheet has already (the width again): ⧉ twice -> ✕ Remove them: ✓ -> light: the
holes' places missing -> the AI: get_sheet check, sheet_edit complete -> ✓; the user's arm part (a boss Ø32 with a
hole, a pin): what medium leaves missing.

  PYTHONIOENCODING=utf-8 py tools/e2e_sheet_check.py http://127.0.0.1:5199 <out dir> [<a project .json with "Otočné rameno">]
"""
import json
import sys
import time
import urllib.request

from selenium import webdriver
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
USER = sys.argv[3] if len(sys.argv) > 3 else None
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
S = "window.__app.sheet"


def ai(tool, **args):
    req = urllib.request.Request(f"{URL}/api/agent/call", data=json.dumps({"tool": tool, "args": args}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        res = json.loads(r.read())
    return ("ERROR " if res.get("isError") else "") + "".join(c.get("text", "") for c in res.get("content", []))


def state():
    return js(f"""const c = {S}.check(); return {{ok: c.ok && !c.over.size, missing: c.missing.map(m => m.view + ': ' + m.what + (m.ax ? ' ' + m.ax : '')), twice: c.dup.size + c.over.size,
      views: [...document.querySelectorAll('#shLeft .sh-vrow label')].map(l => l.textContent.trim()), marks: document.querySelectorAll('#shViewport .sh-miss').length}}""")


try:
    d.get(URL)
    time.sleep(2)
    ai("new_model", name="Plate")
    ai("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    ai("add_feature", type="extrude", sketch="F1", d=10)
    ai("add_feature", type="hole", face="F2:end", points=[[x, y] for x in (-15, -5, 5, 15) for y in (-5, 5)], d=3)
    ai("sheet_open")
    time.sleep(0.6)
    st = state()
    print("medium:", st["ok"], st["missing"], "| views:", st["views"][:3])
    print("the panel says:", d.find_element(By.CSS_SELECTOR, "#shLeft .sh-ok").text if d.find_elements(By.CSS_SELECTOR, "#shLeft .sh-ok") else None)

    pitch = js(f"return {S}.allDims().find(x => x.pre === '3× ').id")
    js(f"{S}.remove('{pitch}')")
    time.sleep(0.4)
    st = state()
    print("the pitch deleted: missing", st["missing"], "| views", st["views"][:3], "| ? marks", st["marks"])
    print("  no ? in the PDF:", js(f"return {S}.svg(true).includes('sh-miss')") is False)
    d.save_screenshot(f"{OUT}/sheet_check.png")
    n = len(st["missing"])
    d.find_element(By.CSS_SELECTOR, "#shLeft [data-miss='0']").click()
    time.sleep(0.4)
    print("＋ one:", n, "->", len(state()["missing"]))
    d.find_element(By.CSS_SELECTOR, "#shLeft [data-a=allMissing]").click()
    time.sleep(0.6)
    st = state()
    print("＋ all missing:", st["ok"], st["missing"], "| views", st["views"][:3])

    js(f"{S}.addFor({{view: 'Top', a: 'box#x0', b: 'box#x1', dir: 'h'}})")
    time.sleep(0.4)
    st = state()
    print("the width again: twice", st["twice"], "| ⧉ rows:", len([r for r in d.find_elements(By.CSS_SELECTOR, "#shLeft .sh-drow") if r.text.startswith("⧉")]))
    d.find_element(By.CSS_SELECTOR, "#shLeft [data-a=dropTwice]").click()
    time.sleep(0.4)
    print("✕ Remove them:", state()["ok"], state()["twice"])

    print("light:", json.loads(ai("sheet_edit", preset="light"))["check"]["missing"][:6])
    r = json.loads(ai("sheet_edit", complete=True))
    print("the AI: complete:", r["done"], "| fully:", r["check"]["fully_dimensioned"], r["check"]["missing"])

    if USER:
        proj = json.load(open(USER, encoding="utf-8"))
        js("return window.__app.autosave.hooks.restore(arguments[0])", proj)
        time.sleep(2)
        arm = next(p for p in json.loads(ai("list_parts")) if p["name"] == "Otočné rameno")
        g = json.loads(ai("sheet_open", part=arm["id"]))
        print("the user's arm, medium:", g["check"]["fully_dimensioned"], g["check"]["missing"], "| twice:", g["check"]["twice"])
        print("  its dims:", [x["text"] for x in g["dims"]])
        d.save_screenshot(f"{OUT}/sheet_check_arm.png")
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
