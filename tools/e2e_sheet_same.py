"""A drawing sheet's views and the same sizes, in headless Edge: a block with holes -> its sheet: the Right view has no
dimension of its own (its sizes are given in the Front and Top) -> the Right view's choice "All its sizes": it gets
its width and height -> a click on the Front's height: the Right's height lights up as the same size -> a click on
the Top's depth: the Right's width lights up.

  PYTHONIOENCODING=utf-8 py tools/e2e_sheet_same.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
H = "window.__app.agentHandlers"
S = "window.__app.sheet"


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def wait(script, t=120):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(script)


def dims(view):
    return js(f"return {S}.allDims().filter(x => x.view === arguments[0]).map(x => [x.id, x.kind, x.dir || '', +({S}.value(x) || 0).toFixed(2)])", view)


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Block")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 30}}])
    call("add_feature", type="extrude", sketch="F1", d=12)
    call("add_feature", type="hole", face="F2:end", points=[[-20, 0], [20, 0]], d=5)
    call("sheet_open", part="Block")
    wait(f"return !!{S}.svgEl && !{S}.busy")
    print("the Right view by itself:", dims("Right"))
    sel = d.find_element(By.CSS_SELECTOR, "#shLeft select[data-vp=Right]")
    print("  its choices:", [o.text for o in Select(sel).options])
    Select(sel).select_by_value("all")
    wait(f"return {S}.d.built?.vp === JSON.stringify({{Right: 'all'}}) && !{S}.busy", 60)
    time.sleep(0.6)
    right = dims("Right")
    print("All its sizes:", right, "| not flagged as twice:", js(f"return {S}.check().dup.size + {S}.check().over.size") == 0)
    front_h = next(x for x in dims("Front") if x[2] == "v" and abs(x[3] - 12) < 0.01)
    js(f"{S}.sel = arguments[0]; {S}.render()", front_h[0])
    time.sleep(0.3)
    lit = js("return [...document.querySelectorAll('#shViewport .sh-dim.same')].map(g => g.dataset.dim)")
    print("the Front's height chosen: the same size lit up in", [x for x in right if x[0] in lit], "| others lit:", [i for i in lit if i not in [x[0] for x in right]])
    top_d = next(x for x in dims("Top") if x[2] == "v" and abs(x[3] - 30) < 0.01)
    js(f"{S}.sel = arguments[0]; {S}.render()", top_d[0])
    time.sleep(0.3)
    lit = js("return [...document.querySelectorAll('#shViewport .sh-dim.same')].map(g => g.dataset.dim)")
    print("the Top's depth chosen:", [x for x in right if x[0] in lit])
    d.save_screenshot(f"{OUT}/sheet_same.png")
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
