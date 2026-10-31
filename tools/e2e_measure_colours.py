"""📏 Measure's colours: a block, five rows of the Measurements table (a distance between two corners, an angle between
two faces, a face's area, an edge's length, a hole's Ø) -> the icon and the value of each kind in its own colour
(distance, size, angle, area: four different ones, as styles.css' --m-dist / --m-size / --m-angle / --m-area), the
view's label and line the same colour as its row; the distance's ΔX ΔY ΔZ each in its axis' colour (--m-dx/dy/dz:
three different ones, none the muted rest); a screenshot.

  PYTHONIOENCODING=utf-8 py tools/e2e_measure_colours.py http://127.0.0.1:5199 <out dir>
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
H = "window.__app.agentHandlers"
M = "window.__app.modeler"
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


def check(ok, what):
    print(("OK   " if ok else "FAIL ") + what)
    if not ok:
        fails.append(what)


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Block")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 20, "y": 10, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    wait(f"return {M}.result?.body && !{M}.inflight")
    js(f"{M}.view.setView('iso')")
    js(f"{M}.action('measure')")
    time.sleep(0.3)
    # the rows, as clicks would make them (measure.js: pair / single)
    js(f"""const ms = {M}.ms, pt = (p) => ({{ kind: 'point', p, snap: 'corner' }}), face = (id, n, c, area) => ({{ kind: 'face', id, at: c, face: {{ type: 'plane', normal: n, centroid: c, area }} }});
      ms.addPair(pt([0, 0, 10]), pt([40, 20, 0]));
      ms.addPair(face('F2', [0, 0, 1], [20, 10, 10], 800), face('F3', [1, 0, 0], [40, 10, 5], 200));
      ms.addPair(face('F2', [0, 0, 1], [20, 10, 10], 800));
      ms.addPair({{ kind: 'edge', id: 'E1', pts: [0, 0, 10, 40, 0, 10] }});
      const ring = []; for (let k = 0; k <= 24; k++) ring.push(20 + 3 * Math.cos(k * Math.PI / 12), 10 + 3 * Math.sin(k * Math.PI / 12), 10);
      ms.addPair({{ kind: 'edge', id: 'E9', pts: ring }});""")
    time.sleep(0.5)
    rows = js("""return [...document.querySelectorAll('[data-w=measure-model] .ms-row')].map(r => ({ cls: r.className, icon: r.querySelector('.ms-i').textContent,
      ci: getComputedStyle(r.querySelector('.ms-i')).color, cv: getComputedStyle(r.querySelector('.ms-v')).color,
      deltas: [...r.querySelectorAll('.ms-tail span')].map(s => [s.textContent, getComputedStyle(s).color]), tail: getComputedStyle(r.querySelector('.ms-tail')).color }))""")
    for r in rows:
        print(" ", r["icon"], r["cls"], r["ci"], r["deltas"])
    kinds = {r["icon"]: r for r in rows}
    want = {"↔": "dist", "∠": "angle", "▭": "area", "L": "size", "Ø": "size"}
    check(all(f"mk-{k}" in kinds.get(i, {}).get("cls", "") for i, k in want.items()), "each row has its kind's class")
    check(all(r["ci"] == r["cv"] for r in rows), "the icon and the value of a row share its colour")
    c4 = {kinds[i]["ci"] for i in ("↔", "∠", "▭", "L")}
    check(len(c4) == 4, f"distance, angle, area and size: four different colours {sorted(c4)}")
    check(kinds["L"]["ci"] == kinds["Ø"]["ci"], "a length and a Ø: the same (size) colour")
    vars_ = js("const s = getComputedStyle(document.documentElement); return ['dist', 'angle', 'area', 'size', 'dx', 'dy', 'dz'].map(k => s.getPropertyValue('--m-' + k).trim())")
    print("  the variables:", vars_)
    check(all(vars_), "the CSS variables are set")
    dl = kinds["↔"]["deltas"]
    check([x[0][:2] for x in dl] == ["ΔX", "ΔY", "ΔZ"] and len({x[1] for x in dl}) == 3 and all(x[1] != kinds["↔"]["tail"] for x in dl),
          f"ΔX ΔY ΔZ each in its own colour, not the muted rest: {dl}")
    marks = js("""return [...document.querySelectorAll('#modelViewport .ms-mark')].map(e => [e.className, getComputedStyle(e).color])""")
    check(len(marks) == 5 and all(any(f"mk-{k}" in m[0] for k in ("dist", "angle", "area", "size")) for m in marks), f"the view's labels carry their kind ({len(marks)})")
    check({m[1] for m in marks} == {r["ci"] for r in rows}, "the labels' colours are the rows'")
    lines = js(f"""return {M}.view.msGroup.children.filter(o => o.isLine).map(o => '#' + o.material.color.getHexString())""")
    print("  the lines:", lines)
    check(len(set(lines)) >= 3, "the view's lines: a colour per kind (distance, angle, length, Ø)")
    d.save_screenshot(f"{OUT}/measure_colours.png")
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        fails.append("console errors")
    d.quit()
print("FAILED:" if fails else "ALL OK", fails if fails else "")
sys.exit(1 if fails else 0)
