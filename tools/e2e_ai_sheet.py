"""The AI's drawing-sheet tools, through /api/agent/call with the page open in headless Edge: a plate with 6 holes ->
sheet_open: the sheet made (medium) -> get_sheet: its dimensions -> get_sheet {points: "Top"}: the holes' centres ->
sheet_edit add: a distance between two hole centres and a circle's Ø with "H7" -> remove one, move one, light, the
iso view hidden -> a wrong id refused -> export pdf: the sheet as drawn (its texts in the PDF) -> sheet_open again: the
same sheet, not a second one.

  PYTHONIOENCODING=utf-8 py tools/e2e_ai_sheet.py http://127.0.0.1:5199 <out dir>
"""
import json
import os
import sys
import time
import urllib.request

import fitz
from selenium import webdriver

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script


def ai(tool, **args):
    req = urllib.request.Request(f"{URL}/api/agent/call", data=json.dumps({"tool": tool, "args": args}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        res = json.loads(r.read())
    return ("ERROR " if res.get("isError") else "") + "".join(c.get("text", "") for c in res.get("content", []))


try:
    d.get(URL)
    time.sleep(2)
    ai("new_model", name="Bracket")
    ai("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 30}}])
    ai("add_feature", type="extrude", sketch="F1", d=6)
    ai("add_feature", type="hole", face="F2:end", points=[[x, y] for x in (-20, 0, 20) for y in (-7, 7)], d=4.5)
    print("export pdf of the model (no sheet on screen):", ai("export", format="pdf", path=OUT)[:60])
    s = json.loads(ai("sheet_open"))
    print("sheet_open:", s["part"], s["preset"], s["paper"], "| dims:", [x["text"] for x in s["dims"]])
    pts = json.loads(ai("get_sheet", points="Top"))["Top"]
    holes = [p for p in pts["points"] if p["key"].endswith("#c")]
    print("Top points:", len(pts["points"]), "| hole centres:", len(holes), "| circles:", [(c["key"], c["d"]) for c in pts["circles"]][:2])
    a, b = holes[0]["key"], max(holes, key=lambda p: abs(p["at"][0] - holes[0]["at"][0]))["key"]
    r = json.loads(ai("sheet_edit", add=[{"view": "Top", "a": a, "b": b}, {"view": "Top", "circle": pts["circles"][0]["key"], "post": "H7"}]))
    print("added:", r["done"], "| theirs:", [x["text"] for x in r["dims"] if not x["auto"]])
    auto = [x for x in r["dims"] if x["auto"]]
    r = json.loads(ai("sheet_edit", remove=[auto[-1]["id"]], move={auto[0]["id"]: {"off": 20}}, views={"Iso": False}))
    print("removed + moved:", r["done"], "| deleted autos", r["deleted_auto"])
    r = json.loads(ai("sheet_edit", preset="light"))
    print("edited:", r["done"], "| preset", r["preset"], "| views", r["views"], "| dims", len(r["dims"]), "| deleted autos", r["deleted_auto"])
    print("moved:", js("const s = window.__app.sheet; return Object.values(s.d.dims).map(o => o.off)"))
    print("a wrong id:", ai("sheet_edit", remove=["nope"])[:60])
    out = ai("export", format="pdf", path=OUT)
    print("export:", out[:80])
    pdf = os.path.join(OUT, "Bracket — drawing.pdf")
    text = fitz.open(pdf)[0].get_text() if os.path.exists(pdf) else ""
    print("the PDF:", [w for w in ("Ø4.5", "H7", "Front", "Top", "Bracket") if w in text], "| no Iso view:", js("return !!window.__app.sheet.d.off.Iso"))
    n = len(json.loads(ai("list_parts")))
    ai("open_part", id=json.loads(ai("list_parts"))[0]["id"])
    s2 = json.loads(ai("sheet_open", part="Bracket"))
    print("sheet_open again: parts", n, "->", len(json.loads(ai("list_parts"))), "| its own dims kept:", [x["text"] for x in s2["dims"] if not x["auto"]])
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
