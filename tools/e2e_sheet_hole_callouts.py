"""Hole callouts on a drawing sheet, in headless Edge: the owner's plate 14.5 × 14 × 2 with one countersunk M3 hole at
8.25 / 6.5 -> its sheet: one callout "M3 ⌵ Ø5 × 90°" in the top view (not "M3" and "Ø5" apart), its place 8.25 / 6.5,
✓ fully dimensioned -> the callout deleted: the check lists the countersink's angle with its circle key (and the M3 /
the Ø5) -> the AI's sheet_edit restore: ✓ again -> deleted again, ＋ on the angle's row: the callout back (the user's),
✓ -> a counterbore and a blind thread on another plate: "Ø3.4 ⌴ Ø6 ↧ 3.2", "2× M4 ↧ 6", ✓ -> the PDF's text and the
DXF's dimension texts carry the callouts with their symbols. No console errors.

  PYTHONIOENCODING=utf-8 py tools/e2e_sheet_hole_callouts.py http://127.0.0.1:5199 <out dir>
"""
import base64
import io
import json
import os
import sys
import time
import urllib.request

import ezdxf
import fitz
from selenium import webdriver
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
S = "window.__app.sheet"
bad = []


def check(ok, what):
    print(("  ok   " if ok else "  FAIL ") + what)
    if not ok:
        bad.append(what)


def ai(tool, **args):
    req = urllib.request.Request(f"{URL}/api/agent/call", data=json.dumps({"tool": tool, "args": args}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        res = json.loads(r.read())
    return ("ERROR " if res.get("isError") else "") + "".join(c.get("text", "") for c in res.get("content", []))


def texts(g):
    return [x["text"] for x in g["dims"]]


def pdf_text():
    pdf = js("""return fetch('/api/sheet/pdf', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({svg: arguments[0], name: 'x'})})
      .then(r => r.arrayBuffer()).then(b => { let s = ''; for (const c of new Uint8Array(b)) s += String.fromCharCode(c); return btoa(s); })""", js(f"return {S}.svg(true)"))
    return fitz.open("pdf", base64.b64decode(pdf))[0].get_text()


def dxf_texts():
    data = js(f"""return fetch('/api/sheet/dxf', {{method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{...{S}.dxfData(), name: 'x'}})}})
      .then(r => r.text())""")
    return [dm.dxf.text for dm in ezdxf.read(io.StringIO(data)).modelspace().query("DIMENSION")]


try:
    d.get(URL)
    time.sleep(2)
    ai("new_model", name="Plate")
    ai("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 14.5, "h": 14}}])
    ai("add_feature", type="extrude", sketch="F1", d=2)
    hole = json.loads(ai("add_feature", type="hole", face="F2:end", points=[[1, -0.5]], thread="M3", head="csk", head_d=5))
    hid = hole["id"]
    g = json.loads(ai("sheet_open"))
    time.sleep(0.6)
    print("the owner's plate:", texts(g))
    co = [x for x in g["dims"] if x["text"] == "M3 ⌵ Ø5 × 90°"]
    check(len(co) == 1 and co[0]["view"] == "Top", "one callout M3 ⌵ Ø5 × 90° in the top view")
    check(not [t for t in texts(g) if t in ("M3", "Ø5", "Ø2.5")], "no separate M3 / Ø5")
    check({"14.5", "14", "2", "8.25", "6.5"} <= set(texts(g)), "the overall sizes and the hole's place stay")
    check(g["check"]["fully_dimensioned"], f"✓ fully dimensioned {g['check']['missing']}")
    check(bool(d.find_elements(By.CSS_SELECTOR, "#shLeft .sh-ok")), "the panel says ✓ Fully dimensioned")
    check("M3 ⌵ Ø5 × 90°" in js("return document.querySelector('#shViewport svg').textContent"), "the callout is drawn on the sheet")
    d.save_screenshot(f"{OUT}/sheet_hole_callout.png")

    r = json.loads(ai("sheet_edit", remove=[co[0]["id"]]))
    miss = r["check"]["missing"]
    print("the callout deleted:", miss)
    angle = [m for m in miss if f"the countersink's angle ({hid})" in m]
    check(not r["check"]["fully_dimensioned"] and len(angle) == 1 and f"[{hid}:hole:0]" in angle[0], "the check lists the countersink's angle with its key")
    check(any(f"the countersink's Ø5 ({hid})" in m for m in miss) and any(f"M3 ({hid})" in m for m in miss), "and its M3 / Ø5 in plain words")
    check(js(f"return {S}.svg(true).includes('sh-miss')") is False and js("return document.querySelectorAll('#shViewport .sh-miss').length") >= 1, "orange ? marks on the screen, not in the PDF")
    d.save_screenshot(f"{OUT}/sheet_hole_callout_missing.png")

    r = json.loads(ai("sheet_edit", restore=True))
    check(r["check"]["fully_dimensioned"] and "M3 ⌵ Ø5 × 90°" in texts(r), "the AI's restore: fully dimensioned again")

    ai("sheet_edit", remove=[co[0]["id"]])
    time.sleep(0.4)
    rows = [b for b in d.find_elements(By.CSS_SELECTOR, "#shLeft .sh-mrow") if "countersink's angle" in b.text]
    check(len(rows) == 1, "the angle's row in the panel")
    if rows:
        rows[0].find_element(By.CSS_SELECTOR, "[data-miss]").click()
        time.sleep(0.4)
    g = json.loads(ai("get_sheet"))
    mine = [x for x in g["dims"] if not x["auto"]]
    check(g["check"]["fully_dimensioned"] and [x["text"] for x in mine] == ["M3 ⌵ Ø5 × 90°"], f"＋ on it: the callout back (the user's) {[x['text'] for x in mine]}")

    words = pdf_text()
    check("M3 ⌵ Ø5 × 90°" in words, "the PDF's text has the callout")
    check("M3 ⌵ Ø5 × 90°" in dxf_texts(), "the DXF's dimension has the callout")

    ai("new_model", name="Block")
    ai("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    ai("add_feature", type="extrude", sketch="F1", d=10)
    ai("add_feature", type="hole", face="F2:end", points=[[-10, 0]], d=3.4, head="cbore", head_d=6, head_depth=3.2)
    ai("add_feature", type="hole", face="F2:end", points=[[5, -4], [12, -4]], thread="M4", through=False, depth=6)
    ai("add_feature", type="hole", face="F2:end", points=[[8, 5]], d=2)
    g = json.loads(ai("sheet_open"))
    time.sleep(0.6)
    print("the block:", texts(g))
    check({"Ø3.4 ⌴ Ø6 ↧ 3.2", "2× M4 ↧ 6", "Ø2 THRU"} <= set(texts(g)), "a counterbore, a blind thread, a plain hole: their callouts")
    check(g["check"]["fully_dimensioned"], f"✓ fully dimensioned {g['check']['missing']}")
    r = json.loads(ai("sheet_edit", remove=[x["id"] for x in g["dims"] if "⌴" in x["text"] or "↧ 6" in x["text"]]))
    miss = r["check"]["missing"]
    print("the two deleted:", miss)
    check(any("the counterbore's depth" in m for m in miss) and any("the thread's depth" in m for m in miss), "the check lists the counterbore's and the thread's depth")
    r = json.loads(ai("sheet_edit", complete=True))
    check(r["check"]["fully_dimensioned"] and {"Ø3.4 ⌴ Ø6 ↧ 3.2", "2× M4 ↧ 6"} <= set(texts(r)), f"the AI's complete: the callouts back {texts(r)}")
    words = pdf_text()
    check(all(w in words for w in ("Ø3.4 ⌴ Ø6 ↧ 3.2", "2× M4 ↧ 6", "Ø2 THRU")), "the PDF's text has them")
    d.save_screenshot(f"{OUT}/sheet_hole_callout_block.png")

    errs = [m["message"] for m in d.get_log("browser") if m["level"] == "SEVERE" and "favicon" not in m["message"]]
    check(not errs, f"no console errors {errs[:3]}")
finally:
    d.quit()
print("FAILED:" if bad else "ALL OK", *bad, sep="\n  ")
sys.exit(1 if bad else 0)
