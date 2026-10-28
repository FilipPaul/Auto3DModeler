"""3D files as exact solids, in headless Edge: Open → CAD / 3D file with a STEP -> a 3D model part (its first step the
solid, the exact volume) in about a second (a bigger STEP too, timed, the page answering all the while) -> a cover:
a box built around a STEP shown as a 👁 Reference (see-through, the volume unchanged) -> ⬚ Cut out: the box minus
the block -> the AI sees the solid's size -> an assembly inserts a STEP From a file -> the project saved carries
the file, and opens again.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_model_solid.py http://127.0.0.1:5199 <out dir> <a .step file> [<a bigger .step>]
"""
import json
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.by import By

URL, OUT, STEP = sys.argv[1], sys.argv[2], sys.argv[3]
BIG = sys.argv[4] if len(sys.argv) > 4 else None
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"
A = "window.__app.assembly"
H = "window.__app.agentHandlers"


def wait(script, t=120):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def settled():
    time.sleep(0.3)
    wait(f"return !{M}.inflight")
    time.sleep(0.3)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def pick_file(path):
    """The next file input the app opens itself (input.click()) gets this file."""
    js("""HTMLInputElement.prototype.__click = HTMLInputElement.prototype.__click || HTMLInputElement.prototype.click;
      HTMLInputElement.prototype.click = function () { if (this.type === 'file') { this.id = 'e2eFile'; this.hidden = true; document.body.appendChild(this); } else this.__click(); };""")
    return lambda: (wait("return !!document.getElementById('e2eFile')", 10), d.find_element(By.ID, "e2eFile").send_keys(path),
                    js("document.getElementById('e2eFile').remove()"))


def one_body():
    """A STEP that holds an assembly asks how to open it: as one body, as this test expects (no question: nothing)."""
    js("""let n = 0; (function go() { const b = [...document.querySelectorAll('.choose .btn')].find((x) => x.textContent.trim().startsWith('Open as one body'));
      if (b) b.click(); else if (n++ < 300) setTimeout(go, 100); })()""")


def open_cad(path):
    t0 = time.time()
    n = js("return window.__app.project.parts.length")
    d.find_element(By.ID, "cadInput").send_keys(path)
    one_body()
    lag = 0
    while time.time() - t0 < 300:
        t1 = time.time()
        done = js(f"return window.__app.project.parts.length > arguments[0] && !!{M}.result?.body", n)
        lag = max(lag, time.time() - t1)
        if done:
            break
        time.sleep(0.25)
    return round(time.time() - t0, 1), round(lag, 2)


try:
    d.get(URL)
    wait("return !!window.__app")
    js("window.confirm = () => true")
    t, lag = open_cad(STEP)
    settled()
    f = js(f"return {M}.part.features")
    print("opened:", js("return window.__app.state.workspace"), "| steps", [(x["type"], x.get("op"), x.get("file")) for x in f], "| volume", round(js(f"return {M}.result.body.volume"), 3),
          "| in", t, "s, the page's slowest answer", lag, "s")
    if BIG:
        t, lag = open_cad(BIG)
        settled()
        b = js(f"return {M}.result.body")
        print("bigger STEP:", len(b["faces"]), "faces, volume", round(b["volume"], 1), "| in", t, "s, the page's slowest answer", lag, "s")

    # a cover around the block: a box, the block as a reference, then cut out
    call("new_model", name="Cover")
    call("add_feature", type="sketch", plane={"datum": "XY", "offset": -3}, shapes=[{"rect": {"x": -3, "y": -3, "w": 46, "h": 26}}])
    call("add_feature", type="extrude", sketch="F1", d=16)
    settled()
    box = js(f"return {M}.result.body.volume")
    go = pick_file(STEP)
    d.find_element(By.CSS_SELECTOR, "#modelViewport [data-a=solidFile]").click()
    go()
    wait(f"return {M}.cmd?.feature?.type === 'solid'", 60)
    settled()
    print("solid step panel:", d.find_element(By.CSS_SELECTOR, "#modelRight").text.split("\n")[:3], "| op", js(f"return {M}.cmd.feature.op"))
    print("as a reference: volume", round(js(f"return {M}.result.body.volume"), 3), "= box", round(box, 3), "| see-through solids", js(f"return {M}.view.refGroup?.children.length"))
    d.save_screenshot(f"{OUT}/solid1.png")
    d.find_element(By.CSS_SELECTOR, "#modelRight [data-op=cut]").click()
    settled()
    print("cut out: volume", round(js(f"return {M}.result.body.volume"), 3), "= box − block", round(box - 8000, 3))
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=ok]").click()
    settled()
    steps = json.loads(call("get_model"))["steps"]
    print("AI sees:", [(s["type"], s.get("op"), s.get("bbox")) for s in steps if s["type"] == "solid"])
    js(f"{M}.view.setView('iso')")
    time.sleep(0.4)
    d.save_screenshot(f"{OUT}/solid2.png")

    # an assembly: Insert part ▾ From a file
    call("new_assembly", name="With a file")
    d.find_element(By.CSS_SELECTOR, "#asmViewport [data-a=insert]").click()
    time.sleep(0.2)
    go = pick_file(STEP)
    d.find_element(By.CSS_SELECTOR, "#asmViewport [data-a=fromFile]").click()
    go()
    wait(f"return {A}.doc.instances.length === 1 && Object.values({A}.bodies).every(b => b.body)", 60)
    print("assembly from a file:", [(p["name"], p["bbox"]) for p in json.loads(call("get_assembly"))["parts"]])

    # the project file carries the STEP
    js("""window.__saved = []; window.showSaveFilePicker = async (o) => ({ name: o.suggestedName,
      createWritable: async () => ({ write: async (b) => { window.__saved.push(await b.text()); }, close: async () => {} }) });""")
    d.find_element(By.ID, "saveBtn").click()
    wait("return window.__saved.length === 1", 60)
    proj = json.loads(js("return window.__saved[0]"))
    print("saved project: parts", len(proj["parts"]), "| files carried", {k: len(v) for k, v in (proj.get("blobs") or {}).items()})
    path = f"{OUT}/solid_project.a3d.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(proj, fh)
    d.find_element(By.ID, "projectInput").send_keys(path)
    wait("return window.__app.project.parts.length === %d && document.querySelector('.toast')?.textContent.includes('Project loaded')" % len(proj["parts"]), 60)
    first = next(p for p in proj["parts"] if p["kind"] == "model")
    next(t for t in d.find_elements(By.CSS_SELECTOR, "#partTabs .part-tab") if t.text.startswith(first["name"])).click()
    wait(f"return window.__app.state.workspace === 'model' && !!{M}.result?.body", 60)
    print("reopened:", first["name"], "| volume", round(js(f"return {M}.result.body.volume"), 3))
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
