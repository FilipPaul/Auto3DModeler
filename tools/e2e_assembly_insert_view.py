"""＋ A part put into an assembly is in the view afterwards, in headless Edge: a 3D model "Block" (40 × 30 × 5) -> a new
assembly, the Block in (the first: iso, all of it seen) -> zoomed in on it, two more Blocks in (the AI's insert_part,
then dragged from the project tree): each lands beside the others, out of the zoomed view -> the view fits, the new
part is inside the camera's view -> zoomed out far, one more in: it can be seen already -> the camera stays where
it was (the user's view is not reset on every insert).

  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_insert_view.py http://127.0.0.1:5199 <out dir>
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
A = "window.__app.assembly"


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def last_seen():
    """Is the part put in last inside the camera's view (all 8 corners of its box)?"""
    return js(f"""const a = {A}, it = a.doc.instances.at(-1);
      const m = a.view.meshes.find(q => q.userData.inst === it.id);
      return !!m && a.inView(new (a.view.fitBox().constructor)().setFromObject(m));""")


def cam():
    return js(f"return {A}.view.camera.position.toArray().map(v => Math.round(v * 10) / 10)")


def zoom(k):
    """The camera k times as far from what it looks at (k < 1: zoomed in), as the mouse wheel does."""
    js(f"""const v = {A}.view, t = v.controls.target, p = v.camera.position;
      p.sub(t).multiplyScalar({k}).add(t); v.controls.update(); v.invalidate();""")


try:
    d.get(URL)
    time.sleep(2)
    call("new_model", name="Block")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 30}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("new_assembly", name="Asm")
    time.sleep(1)
    call("insert_part", part="Block")
    time.sleep(1)
    print("the first Block in (empty assembly): seen:", last_seen())
    js(f"""const v = {A}.view, t = v.controls.target; t.set(20, 15, 2.5); v.controls.update();""")
    zoom(0.25)
    time.sleep(0.3)
    print("zoomed in on it:", cam(), "| the spot beside it (x 50…90) out of the view:",
          js(f"const a = {A}, B = a.view.fitBox().constructor, V = a.view.camera.position.constructor; return !a.inView(new B(new V(50, 0, 0), new V(90, 30, 5)))"))
    call("insert_part", part="Block")
    time.sleep(1)
    print("2nd Block (AI) lands at x =", js(f"return {A}.doc.instances.at(-1).matrix[12]"), "| seen after:", last_seen(), "| camera:", cam())
    zoom(0.3)
    time.sleep(0.3)
    pid = js("return window.__app.project.parts.find(p => p.name === 'Block').id")
    js(f"""const dt = new DataTransfer(); dt.setData('text/a3d-insert', arguments[0]);
      {A}.els.viewport.dispatchEvent(new DragEvent('drop', {{dataTransfer: dt, bubbles: true, cancelable: true}}));""", pid)
    time.sleep(1.5)
    print("3rd Block (dragged from the tree) at x =", js(f"return {A}.doc.instances.at(-1).matrix[12]"), "| seen after:", last_seen(), "| parts:", js(f"return {A}.doc.instances.length"))
    d.save_screenshot(f"{OUT}/insert_view_fitted.png")
    zoom(3)
    time.sleep(0.3)
    before = cam()
    call("insert_part", part="Block")
    time.sleep(1)
    print("zoomed out, 4th Block: seen:", last_seen(), "| camera kept:", cam() == before)
    d.save_screenshot(f"{OUT}/insert_view_kept.png")
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
