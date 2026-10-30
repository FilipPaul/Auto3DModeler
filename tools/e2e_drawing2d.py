"""The 2D drawing workspace, with REAL mouse input in headless Edge: Open a DXF -> a 📐 drawing part (not a 3D part):
its layers listed in their colours -> File units cm (x10) and back -> a layer hidden -> a line drawn corner to corner (snapping) -> 📏 Measure: two
corners (100 mm), a circle (Ø8) -> the new line selected and deleted, Ctrl+Z brings it back -> Use ▾ as a sketch of a
new 3D model (lines, circles, arc joined) -> Use ▾ as a quick part (the closed outline, as a DXF import gave) -> the
project saved with the drawing, and opened again.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_drawing2d.py http://127.0.0.1:5199 <out dir> [<a .dxf> — else a test plate is made]
"""
import json
import os
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from auto3d import package  # noqa: E402  (the saved .a3d read back)

URL, OUT = sys.argv[1], sys.argv[2]
DXF = sys.argv[3] if len(sys.argv) > 3 else None
if not DXF:  # a plate on 3 layers: an outline with an arc, 2 holes + a block of one, a note
    import os
    import ezdxf
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    for name, col in [("OUTLINE", 1), ("HOLES", 3), ("NOTES", 5)]:
        doc.layers.add(name, color=col)
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (100, 0), (100, 60), (0, 60)], close=True, dxfattribs={"layer": "OUTLINE"})
    msp.add_circle((20, 20), 4, dxfattribs={"layer": "HOLES"})
    msp.add_circle((80, 20), 4, dxfattribs={"layer": "HOLES"})
    msp.add_arc((50, 60), 10, 180, 360, dxfattribs={"layer": "OUTLINE"})
    msp.add_line((0, 30), (10, 30), dxfattribs={"layer": "NOTES", "color": 2})
    msp.add_text("PLATE 1", dxfattribs={"layer": "NOTES", "height": 5, "insert": (30, 40)})
    doc.blocks.new("SLOT").add_circle((0, 0), 2)
    msp.add_blockref("SLOT", (50, 20), dxfattribs={"layer": "HOLES"})
    DXF = os.path.abspath(os.path.join(OUT, "plate.dxf"))
    doc.saveas(DXF)
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
D = "window.__app.drawing2d"
M = "window.__app.modeler"


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def click(p, dx=0, dy=0):
    s = js(f"return {D}.toScreen(arguments[0])", p)
    cv = d.find_element(By.CSS_SELECTOR, "#dwgViewport canvas")
    w, h = js("const r = arguments[0].getBoundingClientRect(); return [r.width, r.height]", cv)
    ActionChains(d, duration=30).move_to_element_with_offset(cv, round(s[0] - w / 2) + dx, round(s[1] - h / 2) + dy).perform()
    time.sleep(0.15)
    ActionChains(d).click().perform()
    time.sleep(0.3)


def tool(t):
    d.find_element(By.CSS_SELECTOR, f"#dwgViewport .dw-bar [data-a={t}]").click()
    time.sleep(0.2)


def ents():
    return js(f"return {D}.d.entities.length")


try:
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "cadInput").send_keys(DXF)
    wait("return window.__app.state.workspace === 'drawing'")
    time.sleep(0.8)
    print("opened as:", js("return window.__app.project.current.kind"), "| shapes", ents(),
          "| layers", [r.text.replace("\n", " ") for r in d.find_elements(By.CSS_SELECTOR, "#dwgLeft .dw-layer")])
    print("panel:", d.find_element(By.CSS_SELECTOR, "#dwgRight .mp-facts").text.replace("\n", " "))
    d.save_screenshot(f"{OUT}/dw1.png")
    sel = d.find_element(By.CSS_SELECTOR, "#dwgRight [data-k=units]")
    js("arguments[0].value = 'cm'; arguments[0].dispatchEvent(new Event('change', {bubbles: true}))", sel)
    time.sleep(0.3)
    print("file units cm:", d.find_element(By.CSS_SELECTOR, "#dwgRight .mp-facts").text.split("\n")[1])
    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    time.sleep(0.3)
    print("Ctrl+Z:", d.find_element(By.CSS_SELECTOR, "#dwgRight .mp-facts").text.split("\n")[1], "| units", js(f"return {D}.d.file_units"))

    row = next(r for r in d.find_elements(By.CSS_SELECTOR, "#dwgLeft .dw-layer") if "NOTES" in r.text)
    row.find_element(By.CSS_SELECTOR, "[data-a=eye]").click()
    time.sleep(0.3)
    print("NOTES hidden:", d.find_element(By.CSS_SELECTOR, "#dwgRight .mp-facts").text.replace("\n", " "))

    n0 = ents()
    tool("line")
    click([0.4, 0.3])
    click([99.6, 59.7])
    d.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    time.sleep(0.2)
    new = js(f"return {D}.d.entities.slice(-1)[0]")
    print("line drawn:", ents() - n0, new["t"], new["a"], new["b"], "on", new["layer"], "(snapped to the corners)")

    tool("measure")
    click([0.3, 0.2])
    click([100.3, 0.4])
    print("measure corners:", d.find_element(By.CSS_SELECTOR, "#dwgViewport .dw-measure").text)
    click([24, 20])  # on the hole's rim (r 4 around 20, 20)
    print("measure circle:", d.find_element(By.CSS_SELECTOR, "#dwgViewport .dw-measure").text)
    d.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    time.sleep(0.1)
    tool("select")
    click([50, 30])  # on the new diagonal line
    print("selected:", d.find_element(By.CSS_SELECTOR, "#dwgRight h2").text, "|", d.find_element(By.CSS_SELECTOR, "#dwgRight p.hint").text)
    d.find_element(By.TAG_NAME, "body").send_keys(Keys.DELETE)
    time.sleep(0.3)
    print("deleted:", ents(), "| Ctrl+Z:", end=" ")
    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    time.sleep(0.3)
    print(ents())
    d.save_screenshot(f"{OUT}/dw2.png")

    d.find_element(By.CSS_SELECTOR, "#dwgRight [data-use=sketch]").click()
    wait(f"return window.__app.state.workspace === 'model' && !{M}.inflight")
    time.sleep(0.5)
    sk = js(f"return {M}.part.features[0]")
    from collections import Counter
    print("as a sketch:", sk["type"], dict(Counter(e["t"] for e in sk["entities"])), "| points", len(sk["points"]), "| ok", js(f"return {M}.result?.ok"))

    next(t for t in d.find_elements(By.CSS_SELECTOR, "#partTabs .part-tab") if t.text.startswith("plate") and "3D" not in t.text).click()
    wait("return window.__app.state.workspace === 'drawing'")
    time.sleep(0.4)
    d.find_element(By.CSS_SELECTOR, "#dwgRight [data-use=quick]").click()
    wait("return window.__app.state.workspace === 'quick' && !!window.__app.state.solution", 60)
    sol = js("return window.__app.state.solution")
    print("as a quick part:", js("return window.__app.state.model.kind || window.__app.state.model.source"), "| size", [round(v, 2) for v in sol["bbox"]], "| volume", round(sol["volume"], 1))

    js("""window.__saved = []; window.showSaveFilePicker = async (o) => ({ name: o.suggestedName,
      createWritable: async () => ({ write: async (b) => { const u = new Uint8Array(await b.arrayBuffer()); let s = ''; for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode(...u.subarray(i, i + 0x8000)); window.__saved.push(btoa(s)); }, close: async () => {} }) });""")
    d.find_element(By.ID, "saveBtn").click()
    wait("return window.__saved.length === 1", 30)
    raw = __import__("base64").b64decode(js("return window.__saved[0]"))
    proj = package.load(raw)["project"]
    print("saved:", [(p["kind"], p["name"]) for p in proj["parts"]])
    path = f"{OUT}/dw_project.a3d"
    with open(path, "wb") as fh:
        fh.write(raw)
    d.find_element(By.ID, "projectInput").send_keys(path)
    wait("return [...document.querySelectorAll('.toast')].some(t => t.textContent.includes('Project loaded'))", 30)
    next(t for t in d.find_elements(By.CSS_SELECTOR, "#partTabs .part-tab") if t.text.startswith("plate") and "3D" not in t.text).click()
    wait("return window.__app.state.workspace === 'drawing'")
    print("reopened drawing:", ents(), "shapes | layers", js(f"return {D}.d.layers.map(l => l.name + (l.visible === false ? ' (hidden)' : ''))"))
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
