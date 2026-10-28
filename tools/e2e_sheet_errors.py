"""A drawing sheet that cannot be made says why, in headless Edge: an IGES reference body (surfaces that do not close)
opened -> 📄 its sheet -> a toast and, in the paper area, "The drawing could not be made: <reason>" with ↻ Try again
(asks again: the same message) -> in Czech; then our own 3MF exports (a part in two colours, the Frame) open as quick
parts.

usage (server running with its own data folder, e.g. `A3D_DATA=<scratch> py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_sheet_errors.py http://127.0.0.1:5199 <out dir>
"""
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
ROOT = Path(__file__).resolve().parent.parent
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"
H = "window.__app.agentHandlers"


def wait(script, t=120):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script[:120])


def toasts():
    return js("return [...document.querySelectorAll('.toast')].map(t => t.textContent.trim()).filter(Boolean)")


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.setItem('a3d.lang', 'en')")
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "cadInput").send_keys(str(ROOT / "samples" / "ToImportToOurApp" / "occt" / "hammer.iges"))
    wait(f"return window.__app.state.workspace === 'model' && ({M}.result?.refs || []).length > 0", 180)
    print("opened as a reference body:", js(f"return {M}.part.features[0].op"))
    sent = js("window.__sheetPosts = 0; const f = window.fetch; window.fetch = (u, o) => { if (String(u).includes('/api/sheet/build')) window.__sheetPosts++; return f(u, o); }; return true")
    t0 = time.time()
    js(f"return {H}.sheet_open({{}}).then(r => r.text)")
    wait("return window.__app.state.workspace === 'sheet' && !!document.querySelector('.sh-failed')", 120)
    print(f"the message on the sheet ({time.time() - t0:.1f} s):", d.find_element(By.CSS_SELECTOR, ".sh-failed p").text[:160])
    print("toast:", [x[:90] for x in toasts() if "could not be made" in x])
    d.save_screenshot(f"{OUT}/sheet_failed.png")
    n = js("return window.__sheetPosts")
    d.find_element(By.CSS_SELECTOR, ".sh-failed [data-a=retry]").click()
    wait(f"return window.__sheetPosts > {n} && !!document.querySelector('.sh-failed') && !window.__app.sheet.busy", 120)
    print("↻ Try again: asked again:", js("return window.__sheetPosts") > n, "| the message again:", bool(d.find_elements(By.CSS_SELECTOR, ".sh-failed")))
    d.find_element(By.ID, "langBtn").click()  # (Czech)
    time.sleep(0.5)
    print("in Czech:", d.find_element(By.CSS_SELECTOR, ".sh-failed").text.replace("\n", " | ")[:160])
    d.save_screenshot(f"{OUT}/sheet_failed_cs.png")
    d.find_element(By.ID, "langBtn").click()

    # our own 3MF exports: quick parts of their meshes
    for name in ("part_base_plate.3mf", "assembly_frame.3mf"):
        n0 = js("return window.__app.project.parts.length")
        d.find_element(By.ID, "cadInput").send_keys(str(ROOT / "samples" / "ExportFromOurApp" / name))
        wait(f"return window.__app.project.parts.length > {n0} && window.__app.state.workspace === 'quick' && !!window.__app.state.solution?.mesh", 180)
        s = js("const s = window.__app.state.solution; return {ok: s.ok, size: ['size_x', 'size_y', 'size_z'].map(k => +s.values[k].toFixed(1)), volume: Math.round(s.volume)}")
        print(f"{name}:", s)
    d.save_screenshot(f"{OUT}/frame_3mf.png")
finally:
    print("console errors:", [e["message"][:160] for e in d.get_log("browser") if e["level"] == "SEVERE" and "422" not in e["message"]])
    d.quit()
