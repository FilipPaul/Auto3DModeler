"""The tools coloured by group, in headless Edge: the 3D model's, the sketch's and the assembly's toolbars — each tool
button has its group's class and colour (make blue, modify amber, copy purple, details teal, define / join green, look
and check grey), the groups side by side; screenshots of the bars.

  PYTHONIOENCODING=utf-8 py tools/e2e_tool_groups.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time

from selenium import webdriver

URL, OUT = sys.argv[1], sys.argv[2]
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
        time.sleep(0.2)
    raise TimeoutError(script)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def bar(sel):
    """The bar's tool buttons in order: [action, group, border colour]."""
    return js("""return [...document.querySelectorAll(arguments[0] + ' .chip[data-a]')].filter((b) => b.offsetParent && !b.disabled)
      .map((b) => [b.dataset.a, ([...b.classList].find((c) => c.startsWith('g-')) || '').slice(2), getComputedStyle(b).borderTopColor])""", sel)




def report(name, items):
    runs = []
    for a, g, _ in items:
        if g and (not runs or runs[-1][0] != g):
            runs.append([g, []])
        if g:
            runs[-1][1].append(a)
    print(f"{name}:", " | ".join(f"{g}: {' '.join(a)}" for g, a in runs))
    groups = [g for g, _ in runs]
    print("  each group in one run:", len(groups) == len(set(groups)))
    colours = {}
    for _, g, c in items:
        if g:
            colours.setdefault(g, set()).add(c)
    print("  one colour per group, different groups differ:", all(len(v) == 1 for v in colours.values()) and len({next(iter(v)) for v in colours.values()}) == len(colours))


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Block")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 30}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    wait(f"return !!{M}.result?.body")
    report("3D model", bar(".m-cmdbar"))
    d.find_element("css selector", ".m-cmdbar").screenshot(f"{OUT}/groups_model.png")
    js(f"{M}.edit('F1')")
    time.sleep(0.6)
    if js(f"return {M}.mode") == "sketch":
        report("sketch", bar(".m-cmdbar"))
        d.find_element("css selector", ".m-cmdbar").screenshot(f"{OUT}/groups_sketch.png")
    else:
        print("sketch: not opened (mode", js(f"return {M}.mode"), ")")
    call("new_assembly", name="Box")
    call("insert_part", part="Block")
    time.sleep(1)
    report("assembly", bar("#asmViewport .m-cmdbar"))
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
