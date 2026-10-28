"""Guides while placing on a face (modeler/facesnap.js), with REAL mouse input: a 40 × 40 × 10 block, ◎ Hole -> the
mouse near the top face's middle line: a dashed guide, the spot snapped to x = 20; near the centre (not on it): two
guides, (20, 20); on it: "centre of the face" -> a click: the hole exactly at (20, 20) -> a second hole in line with
the first one's centre: placed from it (from.x = {hole: 0}) -> Shift: not snapped -> the Corners filter off: no corner
caught; the Guides filter off: no guide -> OK: the volume -> Aa Text: level with the holes, a guide too -> the block
60 wide (edit_feature): hole 1 still in the middle ({mid} on x and y, "in the middle of …"), hole 2 in line with it.

  PYTHONIOENCODING=utf-8 py tools/e2e_model_hole_guides.py http://127.0.0.1:5199 <out dir>
"""
import math
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
H = "window.__app.agentHandlers"
M = "window.__app.modeler"
CV = "#modelViewport canvas"
fails = []


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


def check(what, ok):
    print(("  ok  " if ok else "  FAIL") + " " + what)
    if not ok:
        fails.append(what)


def at(p):
    """A 3D point -> its offset from the canvas' middle (pixels)."""
    return js(f"""const v = {M}.view, V = v.camera.position.constructor, [sx, sy] = v.toScreen(new V(...arguments[0])), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(p))


def hover(p, nudge=(0, 0), shift=False):
    """The mouse at a 3D point (+ pixels) -> the spot: {xyz (world), kind, name, guides, label}."""
    o = at(p)
    a = ActionChains(d, duration=30)
    if shift:
        a.key_down(Keys.SHIFT)
    a.move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, CV), o[0] + nudge[0], o[1] + nudge[1])
    if shift:
        a.key_up(Keys.SHIFT)
    a.perform()
    time.sleep(0.35)
    return js(f"""const s = {M}.spot;
      if (!s) return null;
      const {{ o, x, n }} = s.fr, y = [n[1] * x[2] - n[2] * x[1], n[2] * x[0] - n[0] * x[2], n[0] * x[1] - n[1] * x[0]], [u, v] = s.s.uv;
      return {{ xyz: [0, 1, 2].map((k) => +(o[k] + u * x[k] + v * y[k]).toFixed(6)), kind: s.s.kind, guides: s.s.guides.length,
        label: [...document.querySelectorAll('.face-snap')].map((e) => e.textContent).join(' '),
        dims: [...document.querySelectorAll('.hole-dim.live')].map((e) => e.textContent) }};""")


def world(i):
    """The i-th hole of the step being placed, in world coordinates."""
    return js(f"""const f = {M}.cmd.feature, {{ o, x, n }} = {M}.holeFrame(f), y = [n[1] * x[2] - n[2] * x[1], n[2] * x[0] - n[0] * x[2], n[0] * x[1] - n[1] * x[0]], [u, v] = f.points[arguments[0]];
      return [0, 1, 2].map((k) => +(o[k] + u * x[k] + v * y[k]).toFixed(6));""", i)


def snapbar(key):
    d.find_element(By.CSS_SELECTOR, f"#modelViewport .snap-filters [data-snap={key}]").click()
    time.sleep(0.3)


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('a3d.snap3d')")
    call("new_model", name="Block")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    wait(f"return {M}.result?.body && !{M}.inflight")
    js(f"{M}.view.setView('top')")
    time.sleep(0.6)
    print("the block:", js(f"return {M}.result.body.bbox"), "| mm per pixel:", round(js(f"return {M}.view.mmPerPixel({{ o: [20, 20, 10], x: [1, 0, 0], n: [0, 0, 1] }})"), 4))
    js(f"{M}.action('hole')")
    time.sleep(0.4)
    print("the filters:", " | ".join(d.find_element(By.CSS_SELECTOR, "#modelViewport .snap-filters").text.splitlines()))

    s = hover([20, 30, 10], (5, 0))
    print("near the middle line (5 px off):", s)
    check("a guide, snapped to x = 20", s and s["guides"] == 1 and abs(s["xyz"][0] - 20) < 1e-6 and s["kind"] == "line")
    check("the hole's distances shown", s and len(s["dims"]) == 2)
    d.save_screenshot(f"{OUT}/hole_guide_line.png")
    s = hover([20, 20, 10], (7, -7))
    print("near the centre (7, 7 px off):", s)
    check("two guides, snapped to (20, 20)", s and s["guides"] == 2 and s["xyz"][:2] == [20, 20] and s["kind"] == "cross")
    d.save_screenshot(f"{OUT}/hole_guide_cross.png")
    s = hover([20, 20, 10], (2, 1))
    print("on the centre:", s)
    check("the face's centre", s and s["kind"] == "face" and s["xyz"][:2] == [20, 20])
    s = hover([20, 20, 10], (7, -7))
    ActionChains(d).click().perform()
    time.sleep(1.2)
    print("clicked: hole 1 at", world(0), "| from", js(f"return {M}.cmd.feature.from[0]"))
    check("hole 1 exactly at (20, 20)", world(0)[:2] == [20, 20])
    fr = js(f"return {M}.cmd.feature.from[0]")
    check("hole 1 kept in the middle: from {mid} on x and y", all(len((fr.get(k) or {}).get("mid") or []) == 2 for k in ("x", "y")))
    rows = [" ".join(e.text.split()) for e in d.find_elements(By.CSS_SELECTOR, "#modelRight .mp-hole .mp-hd")]
    print("  its rows:", rows)
    check("its rows say in the middle", len(rows) == 2 and all("in the middle of" in r for r in rows))

    s = hover([20, 8, 10], (5, 0))
    print("in line with hole 1, below it:", s)
    check("in line with hole 1 (x = 20)", s and s["kind"] == "line" and abs(s["xyz"][0] - 20) < 1e-6)
    ActionChains(d).click().perform()
    time.sleep(1.2)
    fr = js(f"return {M}.cmd.feature.from[1]")
    print("clicked: hole 2 at", world(1), "| from", fr)
    check("hole 2 at x = 20, placed from hole 1", world(1)[0] == 20 and (fr.get("x") or {}).get("hole") == 0)

    s = hover([20, 30, 10], (5, 0), shift=True)
    print("Shift, near the middle line:", s)
    check("Shift: not snapped", s and s["kind"] is None and abs(s["xyz"][0] - 20) > 0.05)
    s = hover([0, 0, 10], (3, -3))
    print("near a corner:", s)
    check("a corner caught", s and s["kind"] == "corner" and s["xyz"][:2] == [0, 0])
    snapbar("corner")
    s = hover([0, 0, 10], (3, -3))
    print("Corners off, near a corner:", s)
    check("Corners off: no corner", s and s["kind"] != "corner")
    snapbar("corner")
    snapbar("guides")
    s = hover([20, 30, 10], (5, 0))
    print("Guides off, near the middle line:", s)
    check("Guides off: no guide", s and s["guides"] == 0)
    snapbar("guides")

    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=ok]").click()
    time.sleep(0.5)
    wait(f"return !{M}.cmd && !{M}.inflight && {M}.result?.body")
    time.sleep(1)
    v, exp = js(f"return {M}.result.body.volume"), 40 * 40 * 10 - 2 * math.pi * 2.5 ** 2 * 10
    print("the volume:", round(v, 3), "| expected", round(exp, 3))
    check("the volume", abs(v - exp) < 0.05)

    d.find_element(By.CSS_SELECTOR, "#modelViewport [data-a=decal]").click()
    time.sleep(0.5)
    s = hover([12, 30, 10]); s = hover([32, 20, 10], (0, 6))
    print("Aa Text, level with the holes (y = 20):", s)
    check("Text: a guide too", s and s["guides"] >= 1 and s["kind"] in ("line", "cross"))
    d.save_screenshot(f"{OUT}/decal_guide.png")
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=cancel]").click()
    time.sleep(0.8)

    # the block 60 wide (the AI's edit_feature): hole 1 stays in the middle, hole 2 in line with it
    print("widened:", call("edit_feature", id="F1", fields={"shapes": [{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}]})[:80])
    time.sleep(0.5)
    wait(f"return !{M}.inflight && {M}.result?.body?.bbox?.[3] > 59")
    time.sleep(1)
    cs = sorted([round(c, 6) for c in f["centroid"][:2]] for f in js(f"return {M}.result.body.faces") if f["type"] == "cylinder")
    print("  bbox", js(f"return {M}.result.body.bbox"), "| the holes at", cs, "| warnings", js(f"return {M}.result.features.map((x) => x.warnings || [])"))
    check("60 wide: hole 1 at (30, 20), hole 2 at (30, 8)", cs == [[30, 8], [30, 20]])
    d.save_screenshot(f"{OUT}/hole_guide_wider.png")
    # the AI: a hole's from {mid: [edge, edge]} — put on the middle line whatever x it was given
    left, right = {"a": "F2:side:l4", "b": "F2:end", "fp": [0, 20, 10]}, {"a": "F2:side:l2", "b": "F2:end", "fp": [60, 20, 10]}
    r = call("add_feature", type="hole", face="F2:end", points=[[7, 12]], d=3, **{"from": [{"x": {"mid": [left, right]}}]})
    wait(f"return !{M}.inflight")
    time.sleep(1)
    cs = sorted([round(c, 6) for c in f["centroid"][:2]] for f in js(f"return {M}.result.body.faces") if f["type"] == "cylinder")
    print("AI hole midway:", r[:60], "| the holes at", cs)
    check("the AI's hole on the middle line (x = 30; y from the face's centroid)", len(cs) == 3 and all(c[0] == 30 for c in cs))
    r = call("add_feature", type="hole", face="F2:end", points=[[7, 12]], d=3, **{"from": [{"x": {"mid": [left]}}]})
    print("  one edge only:", r[:110])
    check("a mid with one edge refused", r.startswith("ERROR") and "two edge refs" in r)
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    print("FAILED:" if fails or errs or sys.exc_info()[0] else "ALL OK", fails)
    d.quit()
