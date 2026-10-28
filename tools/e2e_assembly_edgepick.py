"""A concentric joint picked by its circles, with REAL mouse clicks in headless Edge: an SMC SY3120 valve from the library
(its ports are holes seen from the top as circles) and a Ø3.5 pin -> ◎ Concentric: a click on the pin's top circle,
then a click on the circle of a port (not into the hole, its wall is hard to hit from above) -> the joint is made on the
port's round face: the pin on that port's axis.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_edgepick.py http://127.0.0.1:5199 <out dir>
"""
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
A = "window.__app.assembly"
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


def circle_point(inst, near=None, top=True):
    """A point (canvas offset from its centre) on a circular edge of a placed part that bounds a round face: the edge
    nearest to `near` (world [x, y]) at the part's top (or bottom)."""
    return js(f"""const a = {A}, v = a.view, mesh = v.meshes.find(m => m.userData.inst === arguments[0]), b = mesh.userData.body, M = mesh.matrix;
      const V = v.camera.position.constructor, near = arguments[1], top = arguments[2];
      const round = b.edges.filter(e => (e.faces || []).some(i => b.faces[i]?.type === 'cylinder')).map(e => {{
        const p = new V(e.pts[0], e.pts[1], e.pts[2]).applyMatrix4(M);
        const n = e.pts.length / 3, c = new V(); for (let k = 0; k < n; k++) c.add(new V(e.pts[3*k], e.pts[3*k+1], e.pts[3*k+2]).applyMatrix4(M)); c.multiplyScalar(1 / n);
        return {{ p, c }}; }});
      round.sort((x, y) => (top ? y.c.z - x.c.z : x.c.z - y.c.z) || (near ? Math.hypot(x.c.x - near[0], x.c.y - near[1]) - Math.hypot(y.c.x - near[0], y.c.y - near[1]) : 0));
      const q = round[0].p, [sx, sy] = v.toScreen(q), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2)), round[0].c.toArray().map(x => +x.toFixed(2))];""", inst, near, top)


def click_at(xy):
    cv = d.find_element(By.CSS_SELECTOR, "#asmViewport canvas")
    ActionChains(d, duration=30).move_to_element_with_offset(cv, xy[0], xy[1]).perform()
    time.sleep(0.25)
    ActionChains(d).click().perform()
    time.sleep(0.5)


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Pin")
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 3.5}}])
    call("add_feature", type="extrude", sketch="F1", d=12)
    call("new_assembly", name="Valve")
    print("valve:", call("library_add", item="smc-sy3120", to="assembly")[:60])
    call("insert_part", part="Pin")
    wait(f"return {A}.doc.instances.length === 2 && Object.values({A}.bodies).every(b => b.body)")
    js(f"{A}.sel = null; {A}.render(); {A}.view.setView('bottom' in {{}} ? 'iso' : 'iso')")
    # the ports are cut from the valve's underside: look from below so they are circles on its face
    js(f"const v = {A}.view, b = v.fitBox(), c = b.getCenter(new (v.camera.position.constructor)()); v.camera.up.set(0, 1, 0); v.camera.position.set(c.x + 20, c.y - 30, c.z - 160); v.controls.target.copy(c); v.controls.update(); v.invalidate()")
    time.sleep(0.6)
    time.sleep(0.2)
    d.find_element(By.CSS_SELECTOR, "#asmViewport [data-joint=axis]").click()
    time.sleep(0.3)
    pin = circle_point("I2", top=False)
    print("pin's circle at", pin[2])
    click_at(pin)
    print("joint from:", js(f"return {A}.jointFrom && [{A}.jointFrom.inst, {A}.jointFrom.face.name, {A}.jointFrom.face.type]"))
    port = circle_point("I1", near=[0, 26], top=False)
    print("the port's circle at", port[2])
    cv = d.find_element(By.CSS_SELECTOR, "#asmViewport canvas")
    ActionChains(d, duration=30).move_to_element_with_offset(cv, port[0], port[1]).perform()
    time.sleep(0.3)
    print("hover on the circle lights its round face:", js(f"return {A}.hoverFace && [{A}.hoverFace.face.type, {A}.hoverFace.ok]"))
    d.save_screenshot(f"{OUT}/edgepick.png")
    ActionChains(d).click().perform()
    time.sleep(0.6)
    print("joint:", js(f"return {A}.doc.mates.map(m => [m.type, m.move, m.face, m.onto, m.ontoFace])"))
    axis = js(f"""const a = {A}, f = a.worldFace('I1', a.doc.mates[0].ontoFace), p = a.worldFace('I2', a.doc.mates[0].face);
      const d = f.axis.d.clone().normalize(), off = p.axis.o.clone().sub(f.axis.o); return +off.sub(d.multiplyScalar(off.dot(d))).length().toFixed(4)""")
    print("the pin on the port's axis (distance between the axes):", axis)
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
