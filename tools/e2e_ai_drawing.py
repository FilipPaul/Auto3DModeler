"""The AI and 2D drawings / boards, through /api/agent/call with the page open in headless Edge: open_file a Gerber set
(.zip) -> a 📐 drawing (get_drawing: its PCB layers) -> drawing_find the drill holes -> drawing_delete them ->
drawing_layers: a new layer, a colour -> drawing_add a line and a circle on it -> drawing_units in (25.4 × bigger) ->
open_file a folder of loose Gerber files: one board -> open_file a DXF: a drawing; with as "part": a quick part.

  PYTHONIOENCODING=utf-8 py tools/e2e_ai_drawing.py http://127.0.0.1:5199 <out dir>
"""
import json
import os
import sys
import time
import urllib.request
import zipfile

from selenium import webdriver

URL, OUT = sys.argv[1], sys.argv[2]
HEAD = "%FSLAX36Y36*%%MOMM*%"
FILES = {
    "demo.GTL": HEAD + "%ADD10C,0.25*%%ADD12R,1.6X1.6*%D10*X5000000Y5000000D02*X25000000Y5000000D01*D12*X5000000Y5000000D03*M02*",
    "demo.GBL": HEAD + "%ADD10C,0.4*%D10*X5000000Y10000000D02*X25000000Y10000000D01*M02*",
    "demo.GKO": HEAD + "%ADD10C,0.1*%D10*X0Y0D02*X30000000Y0D01*X30000000Y20000000D01*X0Y20000000D01*X0Y0D01*M02*",
    "demo.DRL": "M48\nMETRIC,LZ,000.000\nT1C0.8\n%\nT1\nX005000Y005000\nX025000Y015000\nM30\n",
}
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)


def ai(tool, **args):
    req = urllib.request.Request(f"{URL}/api/agent/call", data=json.dumps({"tool": tool, "args": args}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        res = json.loads(r.read())
    return ("ERROR " if res.get("isError") else "") + "".join(c.get("text", "") for c in res.get("content", []))


try:
    zpath, loose = os.path.join(OUT, "board.zip"), os.path.join(OUT, "loose_board")
    os.makedirs(loose, exist_ok=True)
    with zipfile.ZipFile(zpath, "w") as z:
        for n, s in FILES.items():
            z.writestr(n, s)
            with open(os.path.join(loose, n), "w", newline="") as f:
                f.write(s)
    dxf = os.path.join(OUT, "plate.dxf")
    import ezdxf
    doc = ezdxf.new(units=4)  # mm
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (60, 0), (60, 40), (0, 40)], close=True)
    msp.add_circle((15, 20), 4)
    doc.saveas(dxf)

    d.get(URL)
    time.sleep(2)
    print("open the .zip:", ai("open_file", path=zpath))
    g = json.loads(ai("get_drawing"))
    print("its layers:", [(l["name"], l.get("kind"), l["shown"]) for l in g["layers"]], "| size", g["size_mm"])
    holes = json.loads(ai("drawing_find", filters=[{"field": "shape", "value": "circle"}, {"field": "dia", "op": "<", "value": 1}]))
    print("drill holes found:", holes["found"])
    print("deleted:", ai("drawing_delete"))
    print("a new layer:", ai("drawing_layers", new="Notes", color={"Notes": "#ff8800"}))
    print("drawn:", ai("drawing_add", shapes=[{"line": {"a": [0, -5], "b": [30, -5]}}, {"circle": {"c": [15, -10], "d": 3}}]))
    g = json.loads(ai("get_drawing"))
    print("Notes:", next(l for l in g["layers"] if l["name"] == "Notes"), "| circles left:", g["shapes"].get("circle"))
    print("a wrong layer:", ai("drawing_add", shapes=[{"line": {"a": [0, 0], "b": [1, 1]}}], layer="Nope")[:60])
    print("units:", ai("drawing_units", units="in"))

    print("open a folder of loose files:", ai("open_file", path=loose))
    print("  its layers:", len(json.loads(ai("get_drawing"))["layers"]))
    print("open a DXF:", ai("open_file", path=dxf))
    print("  shapes:", json.loads(ai("get_drawing"))["shapes"])
    print("a DXF as a part:", ai("open_file", path=dxf, **{"as": "part"})[:80])
    print("parts:", [(p["name"], p["kind"]) for p in json.loads(ai("list_parts"))])
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
