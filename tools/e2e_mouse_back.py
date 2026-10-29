"""The mouse's side buttons and the browser's Back, in headless Edge, Czech: a block (sketch + extrude) -> the back side
button (3) over the 3D view undoes the extrude, the forward one (4) redoes it, once per press, the browser's own action
stopped; over a text field: nothing; history.back() (twice) -> still the same page, the project still there. No console
errors.

  PYTHONIOENCODING=utf-8 py tools/e2e_mouse_back.py http://127.0.0.1:5199 <out dir>
"""
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
bad = []


def check(ok, what):
    print(("  ok  " if ok else "  FAIL") + " " + what)
    if not ok:
        bad.append(what)


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


def steps():
    return js(f"return {M}.part.features.length")


def side(button, target="document.querySelector('#modelViewport canvas')"):
    """mousedown + mouseup + auxclick with a side button -> [default prevented on each]"""
    return js(f"""const el = {target}, r = el.getBoundingClientRect(), o = {{bubbles: true, cancelable: true, button: {button},
      buttons: {8 if button == 3 else 16}, clientX: r.x + r.width / 2, clientY: r.y + r.height / 2}};
      return ['mousedown', 'mouseup', 'auxclick'].map(t => {{ const e = new MouseEvent(t, o); el.dispatchEvent(e); return e.defaultPrevented; }});""")


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.setItem('auto3d-lang', 'cs')")
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Blok")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 30}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    wait(f"return !{M}.inflight && {M}.history.canUndo()")
    time.sleep(0.8)
    check(steps() == 2, f"the block: sketch + extrude ({steps()} steps)")
    js("window.__mbMark = 1")
    prevented = side(3)
    time.sleep(0.8)
    check(all(prevented), f"◀ (button 3): the browser's own action stopped on mousedown / mouseup / auxclick {prevented}")
    check(steps() == 1, f"◀ undoes the extrude, once ({steps()} step)")
    prevented = side(4)
    time.sleep(0.8)
    check(all(prevented), f"▶ (button 4): stopped too {prevented}")
    check(steps() == 2, f"▶ redoes it ({steps()} steps)")
    # over a text field: the browser's own text undo is the keys' — the side button does nothing
    js("const i = document.createElement('input'); i.id = 'mbField'; i.value = 'abc'; document.body.append(i); i.focus()")
    prevented = side(3, "document.getElementById('mbField')")
    time.sleep(0.6)
    check(all(prevented) and steps() == 2, f"◀ over a text field: nothing undone, no navigation ({steps()} steps)")
    js("document.getElementById('mbField').remove()")
    # the browser's Back stays in the app
    url = d.current_url
    js("history.back()")
    time.sleep(1.0)
    js("history.back()")
    time.sleep(1.0)
    check(js("return window.__mbMark === 1 && !!window.__app"), f"history.back() twice: the same page, not left ({d.current_url})")
    check(d.current_url.split("?")[0] == url.split("?")[0], f"the address is the app's: {d.current_url}")
    check(steps() == 2 and js("return window.__app.project.parts.length") == 1, f"the project is still there ({steps()} steps)")
    check(js("return !!history.state?.a3dGuard"), "the guard entry is back on top")
    d.save_screenshot(f"{OUT}/mouse_back.png")
    errs = [x["message"] for x in d.get_log("browser") if x["level"] == "SEVERE"]
    check(not errs, f"no console errors {errs}")
finally:
    d.quit()
print("ALL OK" if not bad else f"FAILED: {bad}")
sys.exit(1 if bad else 0)
