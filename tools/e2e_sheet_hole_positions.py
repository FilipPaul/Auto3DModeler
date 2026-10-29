"""Hole positions drawn on a part's drawing sheet, in headless Edge (ISO 129, from the part's left / bottom edge):
a plate with 4 corner holes -> 8 / 8 from the edges and the pitches 64 / 34, ✓ fully dimensioned; a row of 5 (⁂ Pattern)
-> its first one and "4× 15"; 6 holes round a Ø20 bore (⁂ Pattern around) -> "PCD Ø60 · 6× 60°" with its dash-dot
pitch circle, ✓ — the PCD deleted: its holes' places missing, ↺ restore: ✓ again; 6 holes anywhere -> ordinates (one row
a direction, the edge's 0 once), ✓, a value moved by the AI's sheet_edit move. On every sheet: get_sheet marks them
(hole_position), no two dimension texts cover each other or another view. The PDF has the PCD's text, the DXF real
ordinate dimensions. No console errors.

  PYTHONIOENCODING=utf-8 py tools/e2e_sheet_hole_positions.py http://127.0.0.1:5199 <out dir>
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


def plate(name, w, h, t, *holes):
    """A w × h × t plate (F1 sketch, F2 extrude) and its holes / patterns (add_feature args each)."""
    ai("new_model", name=name)
    ai("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": w, "h": h}}])
    ai("add_feature", type="extrude", sketch="F1", d=t)
    for a in holes:
        r = json.loads(ai("add_feature", **a))
        check(r.get("ok", True), f"{name}: {a['type']} {r.get('issues') or ''}")
    g = json.loads(ai("sheet_open"))
    time.sleep(0.6)
    return g


# the drawn dimension texts (screen boxes) that cover each other or another view's box
COVERS = """
const svg = document.querySelector('#shViewport svg'), out = [], area = (a, b) => Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left)) * Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
const dims = window.__app.sheet.allDims(), view = Object.fromEntries(dims.map((x) => [x.id, x.view]));
const ts = [...svg.querySelectorAll('g[data-dim] text')].map((el) => ({ id: el.closest('g[data-dim]').dataset.dim, txt: el.textContent, r: el.getBoundingClientRect() }));
const vs = [...svg.querySelectorAll('g.sh-view[data-view]')].map((g) => ({ v: g.dataset.view, r: g.querySelector('.sh-vhit')?.getBoundingClientRect() })).filter((x) => x.r);
for (let i = 0; i < ts.length; i++) {
  for (let j = i + 1; j < ts.length; j++) if (area(ts[i].r, ts[j].r) > 1) out.push(`${ts[i].txt} / ${ts[j].txt}`);
  for (const v of vs) if (v.v !== view[ts[i].id] && area(ts[i].r, v.r) > 1) out.push(`${ts[i].txt} over ${v.v}`);
}
return out;"""


def clear(name):
    covers = js(COVERS)
    check(not covers, f"{name}: no dimension text covers another or another view {covers[:4]}")


try:
    d.get(URL)
    time.sleep(2)

    # a plate with 4 corner holes: the grid's first one from the edges and its pitches
    g = plate("Corners", 80, 50, 5, {"type": "hole", "face": "F2:end", "points": [[x, y] for x in (-32, 32) for y in (-17, 17)], "d": 5})
    print("corners:", texts(g))
    pos = [x for x in g["dims"] if x.get("hole_position")]
    check(sorted(x["text"] for x in pos) == ["34", "64", "8", "8"], f"4 positions: 8 / 8 from the edges, pitches 64 / 34 {[x['text'] for x in pos]}")
    check(g["check"]["fully_dimensioned"], f"✓ fully dimensioned {g['check']['missing']}")
    clear("corners")
    d.save_screenshot(f"{OUT}/hole_positions_corners.png")

    # a row of 5 made by ⁂ Pattern: its first one and "4× 15"
    g = plate("Row", 80, 50, 5, {"type": "hole", "face": "F2:end", "points": [[-30, 0]], "d": 4},
              {"type": "pattern", "of": ["F3"], "dir": "x", "count": 5, "spacing": 15})
    print("row:", texts(g))
    check({"4× 15", "10", "25"} <= {x["text"] for x in g["dims"] if x.get("hole_position")}, "the row: 10 / 25 to its first hole, 4× 15")
    check(g["check"]["fully_dimensioned"], f"✓ fully dimensioned {g['check']['missing']}")
    clear("row")

    # 6 holes round a Ø20 bore: the bolt circle "PCD Ø60 · 6× 60°", its centre the bore's
    g = plate("Flange", 100, 100, 8, {"type": "hole", "face": "F2:end", "points": [[30, 0]], "d": 6},
              {"type": "pattern", "of": ["F3"], "kind": "circular", "axis": {"o": [50, 50, 0], "d": [0, 0, 1]}, "count": 6},
              {"type": "hole", "face": "F2:end", "points": [[0, 0]], "d": 20})
    print("flange:", texts(g))
    pcd = [x for x in g["dims"] if x["kind"] == "pcd"]
    check(len(pcd) == 1 and pcd[0]["text"] == "PCD Ø60 · 6× 60°" and pcd[0]["hole_position"] == "F3", f"one PCD Ø60 · 6× 60° of F3 {[x['text'] for x in pcd]}")
    check(not [t for t in texts(g) if t in ("80", "65", "35", "20")], "not each hole's place apart")
    check(g["check"]["fully_dimensioned"], f"✓ fully dimensioned {g['check']['missing']}")
    check(js("return document.querySelectorAll('#shViewport .sh-pcd').length") == 1, "the pitch circle drawn (dash-dot)")
    clear("flange")
    d.save_screenshot(f"{OUT}/hole_positions_flange.png")
    r = json.loads(ai("sheet_edit", remove=[pcd[0]["id"]]))
    miss = r["check"]["missing"]
    print("the PCD deleted:", miss[:4])
    check(not r["check"]["fully_dimensioned"] and any("Ø6" in m and ":hole:" in m for m in miss), "the PCD deleted: its holes' places missing")
    r = json.loads(ai("sheet_edit", restore=True))
    check(r["check"]["fully_dimensioned"] and "PCD Ø60 · 6× 60°" in texts(r), "restored: ✓ again")
    words = fitz.open("pdf", base64.b64decode(js("""return fetch('/api/sheet/pdf', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({svg: arguments[0], name: 'x'})})
      .then(r => r.arrayBuffer()).then(b => { let s = ''; for (const c of new Uint8Array(b)) s += String.fromCharCode(c); return btoa(s); })""", js(f"return {S}.svg(true)"))))[0].get_text()
    check("PCD Ø60 · 6× 60°" in words, "the PDF has the PCD's text")

    # 6 holes anywhere: ordinates from the edges' 0, one row a direction
    pts = [[-40, -20], [-25, 10], [-5, -12], [12, 18], [30, -5], [41, 22]]
    g = plate("Scatter", 100, 60, 5, {"type": "hole", "face": "F2:end", "points": pts, "d": 4})
    print("scatter:", texts(g))
    ords = [x for x in g["dims"] if x.get("ordinate")]
    check(len(ords) == 12 and all(x.get("hole_position") == "F3" for x in ords), f"12 ordinates (6 holes × x, y) {len(ords)}")
    check(sorted({x["text"] for x in ords}, key=float) == ["10", "18", "25", "40", "45", "48", "52", "62", "80", "91"], "their values from the edges")
    zeros = js("return [...document.querySelectorAll('#shViewport g[data-dim] text')].filter((t) => t.textContent === '0').length")
    check(zeros == 2, f"the edges' 0 once a row: {zeros}")
    check(g["check"]["fully_dimensioned"], f"✓ fully dimensioned {g['check']['missing']}")
    clear("scatter")
    d.save_screenshot(f"{OUT}/hole_positions_ordinate.png")
    dxf = js(f"""return fetch('/api/sheet/dxf', {{method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{...{S}.dxfData(), name: 'x'}})}}).then(r => r.text())""")
    od = [x for x in ezdxf.read(io.StringIO(dxf)).modelspace().query("DIMENSION") if x.dimtype & 7 == 6]
    check(len(od) == 14, f"the DXF: 14 ordinate dimensions (12 + two 0) {len(od)}")
    r = json.loads(ai("sheet_edit", move={ords[0]["id"]: {"off": 20}}))
    check("1 moved" in json.dumps(r) or r["check"]["fully_dimensioned"], "an ordinate moved like any dimension")
    check(js(f"return {S}.allDims().find((x) => x.id === '{ords[0]['id']}').off") == 20, "its row 20 mm off the view")

    errs = [m["message"] for m in d.get_log("browser") if m["level"] == "SEVERE" and "favicon" not in m["message"]]
    check(not errs, f"no console errors {errs[:3]}")
finally:
    d.quit()
print("FAILED:" if bad else "ALL OK", *bad, sep="\n  ")
sys.exit(1 if bad else 0)
