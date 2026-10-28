"""Steps reordered by dragging in the step list, in headless Edge: a plate (sketch + extrude), a second sketch on the Top
plane and a boss extruded from it, a fillet on the plate -> the second sketch dragged to the top of the list: moved (it
uses nothing) -> the boss dragged above its own sketch: refused, "it uses it" -> the fillet dragged above the plate:
refused -> the body the same as before the moves.

  PYTHONIOENCODING=utf-8 py tools/e2e_model_reorder.py http://127.0.0.1:5199 <out dir>
"""
import sys
import time

from selenium import webdriver

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1500,900")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
H = "window.__app.agentHandlers"
M = "window.__app.modeler"


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(script)


def order():
    return js(f"return {M}.part.features.map(f => f.name)")


def drag(src, dst, after=False):
    """A step's row dropped on another one's (its lower half: after it)."""
    js("""const rows = [...document.querySelectorAll('#modelLeft .mt-item')], s = rows.find(r => r.querySelector('.mt-name').textContent === arguments[0]),
      t = rows.find(r => r.querySelector('.mt-name').textContent === arguments[1]), dt = new DataTransfer(), b = t.getBoundingClientRect();
      const y = arguments[2] ? b.bottom - 2 : b.top + 2;
      s.dispatchEvent(new DragEvent('dragstart', { bubbles: true, dataTransfer: dt }));
      t.dispatchEvent(new DragEvent('dragover', { bubbles: true, cancelable: true, dataTransfer: dt, clientY: y }));
      t.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: dt, clientY: y }));""", src, dst, after)
    time.sleep(1.5)
    wait(f"return !{M}.inflight")


def toasts():
    return js("return [...document.querySelectorAll('.toast')].map(t => t.textContent).slice(-1)")


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 10, "y": 10, "d": 8}}])
    call("add_feature", type="extrude", sketch="F3", d=15)
    print("fillet:", call("add_feature", type="fillet", edges=[{"a": "F2:end", "b": "F2:side:l1", "fp": [30, 0, 5]}], r=1)[:50])
    wait(f"return {M}.result?.body && !{M}.inflight")
    vol0 = js(f"return +{M}.result.body.volume.toFixed(2)")
    names = order()
    print("the steps:", names, "| volume", vol0)
    drag(names[2], names[0])
    print("the second sketch dragged to the top:", order())
    drag(names[3], names[2])
    print("the boss above its own sketch:", order(), "|", toasts())
    drag(names[4], names[0])
    print("the fillet above the plate:", order(), "|", toasts())
    print("the body the same:", js(f"return +{M}.result.body.volume.toFixed(2)") == vol0, "| all built:", js(f"return {M}.result.features.every(s => s.ok)"))
    js(f"{M}.history.go(-1)")
    time.sleep(1)
    print("undo the move:", order())
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
