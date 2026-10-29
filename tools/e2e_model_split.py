"""✂ Split body, with REAL mouse input in headless Edge: a 40 × 20 × 10 block -> a click on its top face -> "✂ Split here"
from the face's suggestions (an outer face: midway to the bottom, z 5) -> Keep Both (default: two bodies, 4000 + 4000,
two shades) -> OK -> edit, "This side" (the top half, 4000) -> OK -> ↶ undo: both again -> a Front plane through the
middle -> ⧉ each piece its own part (two new parts of 4000 each) -> the AI's add_feature split.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_model_split.py http://127.0.0.1:5199 <out dir>
"""
import json
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
M = "window.__app.modeler"
H = "window.__app.agentHandlers"


def wait(script, t=30):
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


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#modelViewport canvas")


def click_at(xyz):
    """A real click on the 3D point xyz (as the canvas shows it now)."""
    dx, dy = js(f"""const v = {M}.view, p = new (v.camera.position.constructor)(...arguments[0]);
      const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(xyz))
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), dx, dy).perform()
    time.sleep(0.15)
    ActionChains(d).click().perform()
    time.sleep(0.5)


def body():
    return js(f"return {{volume: {M}.result.body.volume, solids: {M}.result.body.solids, bbox: {M}.result.body.bbox}}")


def press(css):
    d.find_element(By.CSS_SELECTOR, css).click()
    settled()


def tree_last():
    return js("return [...document.querySelectorAll('#modelLeft .mt-item')].map(e => e.textContent.trim().replace(/\\s+/g, ' '))")[-1]


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Block")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    settled()
    js(f"{M}.view.setView('iso')")
    time.sleep(0.4)
    click_at([20, 10, 10])  # the top face, no tool on: its suggestions
    js("document.querySelector('#modelViewport .view-suggest [data-sg-all]')?.click()")  # (⋯ Show all: the rarer rows)
    time.sleep(0.3)
    items = [' '.join(b.text.split()) for b in d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-list button")]
    print("suggestions:", [x for x in items if x.startswith("✂")], "under", js("return [...document.querySelectorAll('#modelViewport .view-suggest .vs-sec')].map(e => e.textContent)"))
    next(b for b in d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-list button") if b.text.startswith("✂")).click()
    settled()
    f = js(f"return {M}.cmd?.feature")
    print("panel:", d.find_element(By.CSS_SELECTOR, "#modelRight h2").text, "| plane: face", f["plane"]["face"]["name"], "mid", (f["plane"].get("mid") or {}).get("name"), "| keep", f["keep"])
    b = body()
    print(f"Keep Both: volume {b['volume']:.3f} expected 8000 | bodies {b['solids']} expected 2 | shades on: {js(f'return !!{M}.view.shades')}")
    halves = js(f"""const b = {M}.result.body, ids = {M}.view.faceIds, tri = {M}.view.mesh.geometry.attributes.position.array, v = [0, 0];
      for (let t = 0; t < ids.length; t++) {{ const k = b.faces[ids[t]].solid || 0, a = tri.slice(t * 9, t * 9 + 9);
        v[k] += (a[0] * (a[4] * a[8] - a[5] * a[7]) - a[1] * (a[3] * a[8] - a[5] * a[6]) + a[2] * (a[3] * a[7] - a[4] * a[6])) / 6; }}
      return v.map((x) => +x.toFixed(2));""")
    print("each body:", halves, "expected [4000, 4000]")
    print("hint:", d.find_element(By.CSS_SELECTOR, "#modelRight .hint:nth-of-type(2)").text if d.find_elements(By.CSS_SELECTOR, "#modelRight .hint:nth-of-type(2)") else None)
    d.save_screenshot(f"{OUT}/split_both.png")
    press("#modelViewport .view-actions [data-a=ok]")
    print("step:", tree_last(), "| shades after OK:", js(f"return !!{M}.view.shades"))
    sid = f["id"]

    # This side: the half the arrow points to (up: the top half, z 5..10)
    js(f"{M}.edit(arguments[0])", sid)
    wait(f"return {M}.cmd?.feature?.type === 'split'")
    settled()
    press("#modelRight [data-keep=above]")
    b = body()
    print(f"This side: volume {b['volume']:.3f} expected 4000 | z {b['bbox'][2]:.3f}..{b['bbox'][5]:.3f} expected 5..10 | bodies {b['solids']}")
    press("#modelViewport .view-actions [data-a=ok]")
    print("step:", tree_last())
    press(".m-cmdbar [data-a=undo]")
    b = body()
    print(f"↶ undo: volume {b['volume']:.3f} expected 8000 | bodies {b['solids']} | keep {js(f'return {M}.part.features.find((g) => g.id === arguments[0]).keep', sid)}")

    # a base plane: Front through the middle (y 10), then each piece its own part
    js(f"{M}.edit(arguments[0])", sid)
    wait(f"return {M}.cmd?.feature?.type === 'split'")
    settled()
    press("#modelRight [data-pl=XZ]")
    print("Front plane:", js(f"return {M}.cmd.feature.plane"), "| volume", round(body()["volume"], 3), "| bodies", body()["solids"])
    off = d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=offset]")
    off.clear()
    off.send_keys("-15\n")
    settled()
    print("offset -15 (y 15):", js(f"return {M}.status(arguments[0]).issues", sid), "| bodies", body()["solids"])
    off = d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=offset]")
    off.clear()
    off.send_keys("-30\n")
    settled()
    print("offset -30 (y 30, past the part):", js(f"return {M}.status(arguments[0]).issues", sid))
    off = d.find_element(By.CSS_SELECTOR, "#modelRight [data-k=offset]")
    off.clear()
    off.send_keys("-10\n")
    settled()
    n0 = js("return window.__app.project.parts.length")
    press("#modelRight [data-a=pieces]")
    wait(f"return window.__app.project.parts.length === {n0 + 2} && {M}.result?.body && !{M}.inflight", 30)
    settled()
    parts = js("return window.__app.project.parts.slice(-2).map((p) => p.name)")
    print("pieces as parts:", parts, "| the one on screen: volume", round(body()["volume"], 3), "expected 4000 | keep",
          js(f"return {M}.part.features.find((g) => g.type === 'split').keep"))

    # the AI
    call("new_model", name="AI split")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    r = json.loads(call("add_feature", type="split", plane={"datum": "YZ", "offset": 30}, keep="below"))
    print(f"AI split below x 30: ok {r['ok']} | volume {r['body']['volume_mm3']} expected 6000")
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
