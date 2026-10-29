"""🏷 Sizes — which size labels are shown, in headless Edge: a plate (a free rectangle, three free circles) extruded ->
its sizes on the part: All = the shapes' sizes + the height, 🔒 Locked = only the height, None = nothing (remembered
after a reload) -> a big sketch (250 circles, one placed and sized: 3 sizes locked): under All only the 3 locked sizes are labelled, with a
note -> Show them all anyway -> every size -> 🔒 Locked -> 3 -> None -> 0; a long Dimensions list is folded.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_sizes.py http://127.0.0.1:5199 <out dir>
"""
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"
SK = f"{M}.sk"
H = "window.__app.agentHandlers"


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def mode(m, where="left"):
    box = f"{M}.els.left" if where == "left" else "document.querySelector('#modelRight, .mp-body')"
    js(f"{box}.querySelector('.m-sizes [data-sz={m}]').click()")
    time.sleep(0.3)


def tags():
    return js("return document.querySelectorAll('.m-dimtag').length")


def labels():
    return js("return document.querySelectorAll('.sk-label.edit').length")


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('a3d.sizes')")
    call("new_model", name="Plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}]
         + [{"circle": {"x": 15 + 15 * i, "y": 20, "d": 6}} for i in range(3)])
    call("add_feature", type="extrude", sketch="F1", d=5)
    wait(f"return !!{M}.result?.body && !{M}.inflight")
    js(f"const f = {M}.part.features[0]; f.dims = []; {M}.history.commit(); {M}.rebuild?.()")
    wait(f"return !!{M}.result?.body && !{M}.inflight")
    js(f"{M}.showStepDims({M}.part.features[1])")
    time.sleep(0.3)
    print("the extrude's sizes, All:", tags())
    mode("locked")
    print("🔒 Locked:", tags(), js("return [...document.querySelectorAll('.m-dimtag')].map(e => e.textContent)"))
    mode("none")
    print("None:", tags(), "| remembered:", js("return localStorage.getItem('a3d.sizes')"))
    d.refresh()
    wait("return !!window.__app")
    print("after a reload, the left panel says:", js(f"return {M}.els.left.querySelector('.m-sizes .on').dataset.sz"))
    mode("all")

    # a big sketch: 250 circles, three of them locked
    call("new_model", name="Board")
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 5 * (i % 25), "y": 5 * (i // 25), "d": 2}} for i in range(250)])
    wait(f"return !{M}.inflight")
    js(f"{M}.edit('F1')")
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.6)
    print("250 sizes locked — the list folded:", js("return !!document.querySelector('.mp-body details.sk-fold')"),
          "|", js("return document.querySelector('.mp-body details.sk-fold summary')?.textContent"))
    js(f"{SK}.f.dims = {SK}.f.dims.slice(3, 6); {SK}.changed()")
    time.sleep(0.6)
    print("big sketch, All:", labels(), "| note:", js("return document.querySelector('.mp-body .sk-big')?.textContent.trim()"))
    d.find_element(By.CSS_SELECTOR, ".mp-body [data-a=bigAll]").click()
    time.sleep(0.6)
    print("Show them all anyway:", labels(), "| note:", js("return document.querySelector('.mp-body .sk-big')?.textContent.trim()"))
    d.save_screenshot(f"{OUT}/sizes_all.png")
    js(f"{M}.els.left.querySelector('.m-sizes [data-sz=locked]').click()")
    time.sleep(0.4)
    print("🔒 Locked (one 🏷 switch, in the step list — not again in the sketch panel):", labels(), "| sketch panel without it:",
          not js("return !!document.querySelector('.mp-body .m-sizes')"))
    mode("none")
    print("None:", labels())
    d.save_screenshot(f"{OUT}/sizes_none.png")
    mode("all")
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
