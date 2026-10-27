"""Bridges between the Quick part and the 3D model workspace, in headless Edge:
a picture traced into a cookie-cutter part -> ◆ To 3D model -> a new model tab whose first sketch is the outline,
Extrude open -> OK; in that model a sketch on the top face -> 🖼 Outline (the picture again, traced) -> a block,
moved and sized; extrude it as a boss; 🖨 Prepare for 3D print -> a printing copy as a Quick part on the
3D print tab; the sample PDF -> ◆ To 3D model (its profile with the cutouts, in mm).

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_model_sources.py http://127.0.0.1:5199 <out dir>
"""
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

URL, OUT = sys.argv[1], sys.argv[2]
PIC = str(Path(__file__).resolve().parent.parent / "pernicek.png")
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"


def wait(script, t=60):
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


def btn(sel):
    d.find_element(By.CSS_SELECTOR, sel).click()
    time.sleep(0.4)


def tabs():
    return js("return [...document.querySelectorAll('#partTabs .part-tab')].map(t => (t.classList.contains('on') ? '*' : '') + t.querySelector('.pt-name').textContent)")


def body():
    return js(f"const b = {M}.result?.body; return b && {{volume: +b.volume.toFixed(3), bbox: b.bbox.map(v => +v.toFixed(3))}}")


try:
    d.get(URL)
    wait("return !!window.__app")

    # a picture -> a cookie cutter (Quick part)
    d.find_element(By.ID, "imgInput").send_keys(PIC)
    wait("return document.querySelector('.wizard .wz-cand')")
    time.sleep(1)
    btn(".wizard .wz-use")
    wait("return window.__app.state.model?.kind === 'outline' && window.__app.state.solution")
    time.sleep(1)
    print("◆ To 3D model button shown:", js("return !document.getElementById('toModelBtn').hidden"))

    # ◆ To 3D model -> a new model tab, the outline as its first sketch, Extrude open
    btn("#toModelBtn")
    wait(f"return document.body.classList.contains('ws-model') && {M}.cmd && !{M}.inflight", 60)
    settled()
    print("tabs:", tabs(), "| steps", js(f"return {M}.part.features.map(f => f.name)"), "| command", js(f"return {M}.cmd.feature.type"))
    btn("#modelViewport .view-actions [data-a=ok]")
    settled()
    b = body()
    print("extruded outline:", b, "| width 100 mm as traced:", abs(b["bbox"][3] - b["bbox"][0] - 100) < 0.5)
    d.save_screenshot(f"{OUT}/b1_to_model.png")

    # a sketch on the top face -> 🖼 Outline -> the picture traced again -> a block in the sketch
    btn(".m-cmdbar [data-a=sketch]")
    pt = js(f"""const v = {M}.view, r = v.renderer.domElement.getBoundingClientRect();
      for (let gy = 0.3; gy < 0.8; gy += 0.01) for (let gx = 0.3; gx < 0.7; gx += 0.01) {{
        const x = Math.round(r.left + gx * r.width), y = Math.round(r.top + gy * r.height);
        if (document.elementFromPoint(x, y) !== v.renderer.domElement) continue;
        const h = v.pick(x, y);
        if (h?.face?.normal && h.face.normal[2] > 0.99) return [x - Math.floor(r.left + r.width / 2), y - Math.floor(r.top + r.height / 2)];
      }} return null;""")
    ActionChains(d, duration=30).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, "#modelViewport canvas"), *pt).click().perform()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.6)
    # headless Edge closes file dialogs at once: keep the picker open for the test to hand it the file
    js("const c = HTMLInputElement.prototype.click; HTMLInputElement.prototype.click = function () { if (this.type !== 'file') c.call(this); }")
    btn(".m-cmdbar [data-a=outline]")
    d.find_element(By.ID, "outlinePickInput").send_keys(PIC)
    wait("return document.querySelector('.wizard .wz-cand')")
    time.sleep(1)
    # make it small: 30 mm wide
    w = d.find_element(By.CSS_SELECTOR, ".wizard .wz-w")
    w.send_keys(Keys.CONTROL, "a")
    w.send_keys("30")
    time.sleep(0.3)
    btn(".wizard .wz-use")
    wait(f"return {M}.sk?.f.entities.some(e => e.t === 'block')", 60)
    time.sleep(0.6)
    blk = js(f"const e = {M}.sk.f.entities.find(e => e.t === 'block'); return [e.name, +e.w0.toFixed(2), +e.h0.toFixed(2), e.at, e.polys.length]")
    print("block:", blk, "| selected:", js(f"return {M}.sk.sel"), "| panel", js("return document.querySelector('#modelRight h3')?.textContent"))
    # size it to 20 mm wide in the panel
    inp = d.find_element(By.CSS_SELECTOR, "#modelRight input[data-bk=w]")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys("20", Keys.ENTER)
    time.sleep(0.5)
    print("resized:", js(f"const e = {M}.sk.f.entities.find(e => e.t === 'block'); return [+(e.w0 * e.scale).toFixed(3), +(e.h0 * e.scale).toFixed(3)]"))
    d.save_screenshot(f"{OUT}/b2_block.png")
    btn("#modelViewport .view-actions [data-a=finish]")
    wait(f"return {M}.cmd && !{M}.inflight")
    js(f"{M}.cmd.feature.op = 'add'; {M}.cmd.feature.d = 2; {M}.renderProps(); {M}.rebuild()")
    settled()
    btn("#modelViewport .view-actions [data-a=ok]")
    settled()
    b2 = body()
    print("with the boss on top:", b2, "| taller by 2:", abs((b2["bbox"][5] - b2["bbox"][2]) - (b["bbox"][5] - b["bbox"][2]) - 2) < 1e-6,
          "| issues", js(f"return {M}.result.features.filter(s => !s.ok)"))
    d.save_screenshot(f"{OUT}/b3_boss.png")

    # 🖨 Prepare for 3D print -> a printing copy (a Quick part from the STL), on the 3D print tab
    btn("#modelRight [data-a=toPrint]")
    wait("return !document.body.classList.contains('ws-model') && window.__app.state.model?.kind === 'mesh' && window.__app.state.solution", 90)
    time.sleep(1)
    print("print copy:", tabs(), "| 3D print tab active:", js("return document.querySelector('.rtab.active')?.dataset.rtab"),
          "| volume", round(js("return window.__app.state.solution.volume"), 1), "vs model", b2["volume"])
    d.save_screenshot(f"{OUT}/b4_print.png")

    # the sample PDF -> ◆ To 3D model: its profile with the cutouts, in mm
    js("document.getElementById('sampleBtn').click()")
    wait("return window.__app.state.model?.source === 'initial draft.pdf' && window.__app.state.solution")
    time.sleep(1)
    btn("#toModelBtn")
    wait(f"return document.body.classList.contains('ws-model') && {M}.cmd && !{M}.inflight", 60)
    settled()
    btn("#modelViewport .view-actions [data-a=ok]")
    settled()
    print("PDF -> model:", body(), "| tabs", tabs())
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
