"""A chosen Hole step: its type and size in the suggestions, its fields in the right panel, in headless Edge with real
mouse clicks: a 60 × 40 × 10 block, an M5 ⌴ counterbore hole (◎ Hole) and a Ø8 round pocket cut by an extrude ->
a click on the hole's wall: "Type: ⌴ Counterbore ▾" and "Size: M5 ▾" in the top rows, the right panel shows the
hole step (its Type / Size, no tool open), its row in the list marked -> Type ▾ offers all 6 kinds (the current ✓) ->
⌵ Countersink: the countersink's exact volume -> Size ▾ offers exactly M3 M4 ✓M5 M6 M8 -> M6: the M6 countersink's
volume -> Ctrl+Z: M5 again -> a click on the pocket's wall: no Type / Size rows (not a Hole step).

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_hole_suggest.py http://127.0.0.1:5199 <out dir>
"""
import math
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


def settled():
    time.sleep(0.6)
    wait(f"return !{M}.inflight")
    time.sleep(0.4)


def wall_of(step, centre):
    """A pixel on a round wall of `step` near the 3D point `centre` -> its offset from the canvas' middle."""
    return js(f"""const v = {M}.view, V = v.camera.position.constructor, [sx, sy] = v.toScreen(new V(...arguments[1])), r = v.renderer.domElement.getBoundingClientRect();
      for (let rad = 2; rad < 60; rad += 2) for (let a = 0; a < 360; a += 15) {{
        const x = sx + rad * Math.cos(a * Math.PI / 180), y = sy + rad * Math.sin(a * Math.PI / 180), h = v.pick(x, y);
        if (h?.face?.name?.startsWith(arguments[0] + ':') && h.face.type !== 'plane' && v.pickEdge(x, y, 9) < 0) return [Math.round(x - Math.floor(r.left + r.width / 2)), Math.round(y - Math.floor(r.top + r.height / 2))];
      }}
      return null;""", step, list(centre))


def click_off(o):
    ActionChains(d, duration=30).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, CV), *o).perform()
    time.sleep(0.3)
    ActionChains(d).click().perform()
    time.sleep(0.8)


def rows():
    return [" ".join(b.text.split()) for b in d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-list button[data-sg]")]


def row(start):
    return next(b for b in d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-list button[data-sg]") if any(" ".join(b.text.split()).split(" ", 1)[-1].startswith(s) for s in start))


def options():
    wait("return !!document.querySelector('.choose-back')")
    return [" ".join(b.text.split()) for b in d.find_elements(By.CSS_SELECTOR, ".choose-back .choose-opts button")]


def pick_option(text):
    next(b for b in d.find_elements(By.CSS_SELECTOR, ".choose-back .choose-opts button") if text in b.text).click()
    time.sleep(0.4)


def frustum(R, r, h):
    return math.pi * h / 3 * (R * R + R * r + r * r)


def vol():
    return js(f"return {M}.result.body.volume")


BASE = 60 * 40 * 10 - math.pi * 4 ** 2 * 10  # the block with its Ø8 pocket through
CBORE5 = math.pi * 2.75 ** 2 * 10 + math.pi * (5 ** 2 - 2.75 ** 2) * 5.4
CSK5 = math.pi * 2.75 ** 2 * 10 + frustum(5.6, 2.75, 2.85) - math.pi * 2.75 ** 2 * 2.85
CSK6 = math.pi * 3.3 ** 2 * 10 + frustum(6.7, 3.3, 3.4) - math.pi * 3.3 ** 2 * 3.4

try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Holes")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    print(call("add_feature", type="hole", face="F2:end", points=[[-15, 0]], hole_type="counterbore", standard="M5", through=True)[:80])
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 45, "y": 20, "d": 8}}])
    call("add_feature", type="extrude", sketch="F4", op="cut", d=100, symmetric=True)
    settled()
    v = vol()
    check(f"the block, its M5 counterbore and the pocket ({v:.2f})", abs(v - (BASE - CBORE5)) < 0.5)
    js(f"{M}.view.setView('iso')")
    time.sleep(0.8)

    # ---- a click on the hole's wall
    o = wall_of("F3", [15, 20, 7])
    print("the hole's wall at", o)
    click_off(o)
    r = rows()
    print("rows:", r[:6])
    check("“Type: ⌴ Counterbore ▾” and “Size: M5 ▾” in the top 3 rows",
          any(("Type:" in x or "Typ:" in x) and "Counterbore" in x or "Válcové" in x for x in r[:3]) and any(("Size:" in x or "Velikost:" in x) and "M5" in x for x in r[:3]))
    check("the hole step chosen, no tool open", js(f"return {M}.selected") == "F3" and js(f"return !{M}.cmd"))
    panel = js("return [document.querySelector('#modelRight h2')?.textContent, !!document.querySelector('#modelRight [data-k=hole_type]'), document.querySelector('#modelRight [data-k=standard]')?.value]")
    print("right panel:", panel)
    check("the right panel shows the hole step (its Type, Size M5)", panel[0] == "Hole 1" and panel[1] and panel[2] == "M5")
    check("its row in the list is marked", js("return !!document.querySelector('#modelLeft .mt-item.on[data-id=F3]')"))
    d.save_screenshot(f"{OUT}/hole_suggest.png")

    # ---- Type ▾: all six kinds; ⌵ Countersink
    row(["Type:", "Typ:"]).click()
    ts = options()
    print("types offered:", ts)
    check("all 6 types offered, the current one ✓", len(ts) == 6 and sum(x.startswith("✓") for x in ts) == 1 and "Counterbore" in next(x for x in ts if x.startswith("✓")))
    pick_option("Countersink")
    settled()
    v = vol()
    f3 = js(f"return {M}.part.features.find(f => f.id === 'F3')")
    check(f"⌵ Countersink: its exact volume ({v:.2f} vs {BASE - CSK5:.2f})", f3["head"] == "csk" and abs(v - (BASE - CSK5)) < 0.5)

    # ---- Size ▾: two below and two above
    row(["Size:", "Velikost:"]).click()
    ss = options()
    print("sizes offered:", ss)
    check("the sizes: exactly M3 M4 ✓M5 M6 M8", ss == ["M3", "M4", "✓ M5", "M6", "M8"])
    pick_option("M6")
    settled()
    v = vol()
    check(f"M6: the M6 countersink's volume ({v:.2f} vs {BASE - CSK6:.2f})", abs(v - (BASE - CSK6)) < 0.5)
    js(f"{M}.history.go(-1)")
    settled()
    v = vol()
    check(f"Ctrl+Z: M5 again ({v:.2f})", abs(v - (BASE - CSK5)) < 0.5)
    check("still no tool open", js(f"return !{M}.cmd"))

    # ---- its rim (a round edge of the hole): the hole chosen too, its rows above the edge's
    js(f"{M}.selectStep(null)")
    o = js(f"""const v = {M}.view, b = v.body, V = v.camera.position.constructor, r = v.renderer.domElement.getBoundingClientRect();
      const i = b.edges.findIndex((e) => e.faces.some((k) => b.faces[k]?.name?.startsWith('F3:')) && e.faces.some((k) => b.faces[k]?.name === 'F2:end'));
      const e = b.edges[i], [sx, sy] = v.toScreen(new V(e.pts[0], e.pts[1], e.pts[2]));
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""")
    click_off(o)
    r = rows()
    print("rim rows:", r[:5])
    check("its rim: the hole chosen, Type / Size above Fillet", js(f"return {M}.selected") == "F3" and len(r) > 2 and any(s in r[0] for s in ("Type:", "Typ:")) and any("Fillet" in x or "Zaobl" in x for x in r))

    # ---- the pocket's wall: not a Hole step
    js(f"{M}.selectStep(null)")
    o = wall_of("F5", [45, 20, 7])
    click_off(o)
    r = rows()
    print("pocket rows:", r[:6])
    check("the round pocket: no Type / Size rows", r and not any(x.split(" ", 1)[-1].startswith(("Type:", "Typ:", "Size:", "Velikost:")) for x in r))
    check("the right panel is the part's again", js("return !document.querySelector('#modelRight [data-k=hole_type]')"))
finally:
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        fails.append("console errors")
    d.quit()

print("FAILED:" if fails else "ALL OK", fails if fails else "")
sys.exit(1 if fails else 0)
