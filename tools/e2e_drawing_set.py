"""An assembly's drawing set (one PDF), in headless Edge: parts Base, Lid, Pin; a sub-assembly "Lid unit" (Lid + 2 Pins);
the final assembly "Machine" (Base + Lid unit + a bought screw from the library). The Base has its own drawing sheet
with a dimension of the user's. -> 📄 Drawings (PDF) in the Machine's panel -> pages in order: Machine (its views, the
parts list with Base, ◇ Lid unit, the screw as bought, balloons), Lid unit (Lid, Pin ×2), Lid, Pin, Base (with the
user's dimension); every page names itself, what it is in and "Sheet n / N" -> the AI's export pdf: the same set.

  PYTHONIOENCODING=utf-8 py tools/e2e_drawing_set.py http://127.0.0.1:5199 <out dir>
"""
import json
import os
import sys
import time
import urllib.request

import fitz
from selenium import webdriver
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
A = "window.__app.assembly"


def ai(tool, **args):
    req = urllib.request.Request(f"{URL}/api/agent/call", data=json.dumps({"tool": tool, "args": args}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        res = json.loads(r.read())
    return ("ERROR " if res.get("isError") else "") + "".join(c.get("text", "") for c in res.get("content", []))


def pages(path):
    return [p.get_text() for p in fitz.open(path)]


try:
    d.get(URL)
    time.sleep(2)
    for name, w, h, t in (("Base", 80, 50, 10), ("Lid", 60, 40, 4)):
        ai("new_model", name=name)
        ai("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": w, "h": h}}])
        ai("add_feature", type="extrude", sketch="F1", d=t)
    ai("add_feature", type="hole", face="F2:end", points=[[-20, 0], [20, 0]], d=6)
    ai("new_model", name="Pin")
    ai("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 6}}])
    ai("add_feature", type="extrude", sketch="F1", d=12)
    # the Base's own sheet, with a dimension of the user's
    base = next(p["id"] for p in json.loads(ai("list_parts")) if p["name"] == "Base")
    json.loads(ai("sheet_open", part=base))
    pts = json.loads(ai("get_sheet", points="Front"))["Front"]["points"]
    ends = [p for p in pts if p["key"].endswith("#0") or p["key"].endswith("#1")]
    a, b = ends[0]["key"], max(ends, key=lambda p: abs(p["at"][1] - ends[0]["at"][1]))["key"]
    print("the Base's own dimension:", json.loads(ai("sheet_edit", add=[{"view": "Front", "a": a, "b": b, "dir": "v", "pre": "MY"}]))["done"])

    ai("new_assembly", name="Lid unit")
    for p in ("Lid", "Pin", "Pin"):
        ai("insert_part", part=p)
    ai("new_assembly", name="Machine")
    ai("insert_part", part="Base")
    ai("insert_part", part="Lid unit")
    print("a bought screw:", ai("library_add", item="iso4762", size="M3", length=10, to="assembly")[:50])
    time.sleep(1)
    js(f"{A}.sel = null; {A}.render()")
    time.sleep(0.4)
    btn = d.find_element(By.CSS_SELECTOR, "#asmRight [data-a=drawingSet]")
    print("the button:", btn.text)
    # the PDF as the button makes it (the download is caught in the page)
    res = js("""return window.__app.sheet.drawingSet(window.__app.project.active, {
        kindOf: (id) => window.__app.project.parts.find(q => q.id === id)?.kind,
        sheetOf: (id) => { const p = window.__app.project.parts.find(q => q.kind === 'sheet' && typeof q.data === 'object' && q.data?.source === id); return p ? p.data : null; },
        bought: (data, name) => !!data?.standard || /screw|nut|insert/.test(name) }).then(s => s.pages)""")
    print("pages (the button's way):", res)
    out = ai("export", format="pdf", path=OUT)
    print("the AI's export:", out[:160])
    path = os.path.join(OUT, "Machine — drawings.pdf")
    texts = pages(path)
    print("PDF pages:", len(texts))
    for i, t in enumerate(texts):
        first = [w for w in ("Machine", "Lid unit", "Lid", "Pin", "Base") if w in t]
        print(f"  {i + 1}:", "Sheet", f"{i + 1} / {len(texts)}" in t, "| names:", first, "| sub-assembly" if "Sub-assembly" in t else "", "| MY" if "MY" in t else "",
              "| list:" if "Part number" in t else "", [w for w in ("◇ Lid unit", "ISO 4762", "bought") if w in t])
    d.save_screenshot(f"{OUT}/drawing_set.png")
    page1 = fitz.open(path)[0]
    page1.get_pixmap(dpi=60).save(f"{OUT}/drawing_set_p1.png")
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
