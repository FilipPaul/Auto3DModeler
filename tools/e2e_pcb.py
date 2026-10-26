"""Gerber / ODB++ boards in the 📐 Drawing workspace, in headless Edge: a Gerber set (.zip: top / bottom copper,
silkscreen, outline, an Excellon drill file) opens as a drawing — the top copper, outline, holes and silkscreen shown,
the rest hidden — traces at their width, pads filled -> a click inside a pad selects it -> 📏 snaps to a pad's
middle -> 🔍 Width = 0.25 finds the thin traces -> ⬇ DXF saves the shown layers (polylines of the traces' width,
hatched pads) and it opens again as a drawing -> the same files picked loose (several at once) make one board.
Optionally a bigger board (a .zip / .tgz) is opened and timed.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_pcb.py http://127.0.0.1:5199 <out dir> [<a board .zip / .tgz>]
"""
import os
import sys
import time
import zipfile

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
BIG = sys.argv[3] if len(sys.argv) > 3 else None
HEAD = "%FSLAX36Y36*%%MOMM*%"
FILES = {
    "board/demo.GTL": HEAD + "%ADD10C,0.25*%%ADD11C,0.6*%%ADD12R,1.6X1.6*%D10*X5000000Y5000000D02*X25000000Y5000000D01*X25000000Y15000000D01*"
                      "D11*X5000000Y15000000D02*X15000000Y15000000D01*D12*X5000000Y5000000D03*X25000000Y15000000D03*M02*",
    "board/demo.GBL": HEAD + "%ADD10C,0.4*%D10*X5000000Y10000000D02*X25000000Y10000000D01*M02*",
    "board/demo.GTO": HEAD + "%ADD10C,0.15*%D10*X3000000Y3000000D02*X8000000Y3000000D01*M02*",
    "board/demo.GKO": HEAD + "%ADD10C,0.1*%D10*X0Y0D02*X30000000Y0D01*X30000000Y20000000D01*X0Y20000000D01*X0Y0D01*M02*",
    "board/demo.DRL": "M48\nMETRIC,LZ,000.000\nT1C0.8\n%\nT1\nX005000Y005000\nX025000Y015000\nM30\n",
}
os.makedirs(OUT, exist_ok=True)
ZIP = os.path.abspath(os.path.join(OUT, "demo_board.zip"))
with zipfile.ZipFile(ZIP, "w") as z:
    for n, t in FILES.items():
        z.writestr(n, t)
LOOSE = []
for n, t in FILES.items():
    path = os.path.abspath(os.path.join(OUT, os.path.basename(n)))
    with open(path, "w", encoding="ascii") as fh:
        fh.write(t)
    LOOSE.append(path)

opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
D = "window.__app.drawing2d"


def wait(script, t=120):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def click(p):
    s = js(f"return {D}.toScreen(arguments[0])", p)
    cv = d.find_element(By.CSS_SELECTOR, "#dwgViewport canvas")
    w, h = js("const r = arguments[0].getBoundingClientRect(); return [r.width, r.height]", cv)
    ActionChains(d, duration=30).move_to_element_with_offset(cv, round(s[0] - w / 2), round(s[1] - h / 2)).perform()
    time.sleep(0.15)
    ActionChains(d).click().perform()
    time.sleep(0.3)


def open_files(paths):
    n = js("return window.__app.project.parts.length")
    d.find_element(By.ID, "cadInput").send_keys("\n".join(paths))
    wait(f"return window.__app.project.parts.length > {n} && window.__app.state.workspace === 'drawing'")
    time.sleep(0.6)


try:
    d.get(URL)
    wait("return !!window.__app")
    open_files([ZIP])
    layers = js(f"return {D}.d.layers.map(l => [l.name, l.kind, l.color, l.visible !== false])")
    print("layers:", layers)
    print("shapes:", js(f"return {D}.d.entities.map(e => e.t + (e.w ? ' w' + e.w : '') + (e.fill ? ' filled' : '')).join(', ')"))
    d.save_screenshot(f"{OUT}/pcb1.png")

    click([25.3, 15.4])  # inside the square pad (1.6 x 1.6 around 25, 15)
    print("click inside a pad:", d.find_element(By.CSS_SELECTOR, "#dwgRight h2").text, "| selected", js(f"return [...{D}.sel]"))
    d.find_element(By.CSS_SELECTOR, "#dwgViewport .dw-bar [data-a=measure]").click()
    click([5.15, 5.1])  # near the other pad's middle
    print("measure from:", d.find_element(By.CSS_SELECTOR, "#dwgViewport .dw-measure").text)
    click([25.12, 14.9])
    print("measure:", d.find_element(By.CSS_SELECTOR, "#dwgViewport .dw-measure").text)
    js(f"{D}.setTool('select'); {D}.sel.clear(); {D}.filters = [{{ field: 'w', op: '=', value: '0.25' }}]; {D}.updateMatches(); {D}.renderProps()")
    time.sleep(0.3)
    print("Width = 0.25:", d.find_element(By.CSS_SELECTOR, "#dwgRight .dw-fcount").text)

    js("""window.__saved = []; window.showSaveFilePicker = async (o) => ({ name: o.suggestedName,
      createWritable: async () => ({ write: async (b) => { window.__saved.push([o.suggestedName, await b.text()]); }, close: async () => {} }) });""")
    d.find_element(By.CSS_SELECTOR, "#dwgViewport .dw-bar [data-a=dxf]").click()
    wait("return window.__saved.length === 1", 30)
    name, text = js("return window.__saved[0]")
    print("DXF:", name, "| LWPOLYLINE", text.count("LWPOLYLINE"), "| HATCH", text.count("\nHATCH"), "| CIRCLE", text.count("\nCIRCLE"),
          "| layers named:", [n for n in ("demo.GTL", "demo.GKO", "demo.DRL", "demo.GBL") if f"\n{n}\n" in text])
    path = os.path.abspath(os.path.join(OUT, "demo_out.dxf"))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    open_files([path])
    print("the DXF opened again:", js(f"return [{D}.d.entities.length, {D}.d.layers.map(l => l.name)]"))

    open_files(LOOSE)
    print("loose files (5 at once):", js(f"return [{D}.d.entities.length, {D}.d.layers.length, {D}.d.pcb]"))

    if BIG:
        t = time.time()
        open_files([BIG])
        print("bigger board:", os.path.basename(BIG), "opened in", round(time.time() - t, 1), "s |", js(f"return {D}.d.entities.length"), "shapes on", js(f"return {D}.d.layers.length"), "layers")
        js(f"{D}.rev++; {D}.paint()")
        print("  redraw ms:", js(f"const e = {D}, t = performance.now(); e.paint(); return Math.round(performance.now() - t)"),
              "| a pick ms:", js(f"const e = {D}, t = performance.now(); for (let i = 0; i < 10; i++) e.hitAt(300 + i * 40, 420); return Math.round((performance.now() - t) / 10)"))
        d.save_screenshot(f"{OUT}/pcb2.png")
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
