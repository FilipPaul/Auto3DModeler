"""⟷ Extend in a sketch, with REAL mouse input in headless Edge: a locked wall (a vertical line at x 50), a free
horizontal line ending at x 30 (its end locked there), a short vertical line under a Ø10 circle -> Extend: hovering near
the line's right end shows the green extension, a click takes the end to the wall (it stays on it: the wall moved to
x 70 takes it along) -> the short line's top end reaches the circle (y 26) -> the line's left end, with nothing
beyond it, says so -> Ctrl+Z goes back.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_sketch_extend.py http://127.0.0.1:5199 <out dir>
"""
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

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


def off(uv):
    return js(f"""const m = {M}, v = m.view, f = m.frame(), [u, w] = arguments[0];
      const y = [f.n[1]*f.x[2]-f.n[2]*f.x[1], f.n[2]*f.x[0]-f.n[0]*f.x[2], f.n[0]*f.x[1]-f.n[1]*f.x[0]];
      const p = new (v.camera.position.constructor)(f.o[0] + u*f.x[0] + w*y[0], f.o[1] + u*f.x[1] + w*y[1], f.o[2] + u*f.x[2] + w*y[2]);
      const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(uv))


def move(uv):
    ActionChains(d, duration=30).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, "#modelViewport canvas"), *off(uv)).perform()
    time.sleep(0.2)


def click(uv):
    move(uv)
    ActionChains(d).click().perform()
    time.sleep(0.6)


def pt(pid):
    return js(f"return {SK}.P(arguments[0]).map(v => +v.toFixed(4))", pid)


def ends(eid):
    return js(f"return (e => [{SK}.P(e.a), {SK}.P(e.b)].map(p => p.map(v => +v.toFixed(3))))({SK}.ent(arguments[0]))", eid)


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Extend")
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 60, "y": 30, "d": 10}}])
    wait(f"return !{M}.inflight")
    js(f"{M}.edit('F1')")
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.5)
    js(f"""const f = {SK}.f;
      Object.assign(f.points, {{ q1: [50, 0], q2: [50, 40], q3: [0, 20], q4: [30, 20], q5: [57, 10], q6: [57, 15] }});
      f.entities.push({{ id: 'w1', t: 'line', a: 'q1', b: 'q2' }}, {{ id: 'l91', t: 'line', a: 'q3', b: 'q4' }}, {{ id: 'l92', t: 'line', a: 'q5', b: 'q6' }});
      f.constraints.push({{ id: 'k91', t: 'v', e: 'w1' }}, {{ id: 'k92', t: 'h', e: 'l91' }}, {{ id: 'k93', t: 'v', e: 'l92' }});
      f.dims.push({{ id: 'd91', t: 'dx', a: 'O', b: 'q1', v: 50 }}, {{ id: 'd92', t: 'dy', a: 'O', b: 'q1', v: 0 }}, {{ id: 'd93', t: 'dy', a: 'O', b: 'q2', v: 40 }},
        {{ id: 'd94', t: 'dx', a: 'O', b: 'q4', v: 30 }}, {{ id: 'd95', t: 'dy', a: 'O', b: 'q3', v: 20 }}, {{ id: 'd96', t: 'dx', a: 'O', b: 'q3', v: 0 }});
      {SK}.changed();""")
    js(f"{M}.view.lookAt({M}.frame(), 110); {SK}.draw()")
    time.sleep(0.6)
    d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=extend]").click()
    time.sleep(0.2)
    print("hint:", d.find_element(By.CSS_SELECTOR, "#modelViewport .m-hint").text)
    move([27, 20])
    print("hover near the right end:", js(f"return {SK}.hover && [{SK}.hover.grow, {SK}.hover.pts.map(p => p.map(v => +v.toFixed(3)))]"))
    d.save_screenshot(f"{OUT}/extend_hover.png")
    click([27, 20])
    print("the line now:", ends("l91"), "| its end stays on the wall:", js(f"return {SK}.f.constraints.some(k => k.t === 'on' && k.p === 'q4' && k.e === 'w1')"),
          "| the lock at x 30 gone:", not js(f"return {SK}.f.dims.some(x => x.id === 'd94')"))
    click([57, 14.6])
    print("the short line reaches the circle:", ends("l92"))
    click([1, 20])
    print("left end, nothing beyond:", js("return [...document.querySelectorAll('.toast')].map(t => t.textContent).slice(-1)[0]"), "|", ends("l91"))
    # the wall moves to x 70: the extended end goes along
    js(f"{SK}.f.dims.find(x => x.id === 'd91').v = 70")
    js(f"return {SK}.relock(() => {{}})")
    time.sleep(0.6)
    print("wall at x 70 -> the line:", ends("l91"), "| wall", ends("w1"))
    d.find_element(By.CSS_SELECTOR, "#modelViewport canvas").click()
    for _ in range(2):
        ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
        time.sleep(0.4)
    print("Ctrl+Z ×2:", ends("l91"), ends("l92"))
    d.save_screenshot(f"{OUT}/extend.png")
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
