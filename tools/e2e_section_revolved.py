"""✂ The section view of a revolved part (the AI's report: a pump body cut at y = 0 showed whole, with a jagged ring
at z = 0), in headless Edge: a flanged tube revolved 360° (a Ø10 bore, walls 7 mm, a Ø40 × 10 flange) ->
- ✂ Section from the toolbar (Y, at the middle: 0): the half toward the camera is gone, the cut faces are capped —
  one cap, inside the part's box, of the profile's area twice (2 × 360 mm²); X too; ⇄ the other side;
- the AI's set_view {view: front, section: {axis: y, offset: 0}} + get_screenshot: the cap's brick red on both walls
  of the tube with the bore open between them (7 : 10 : 7), and on the flange (15 : 10 : 15); flipped: no cap seen;
- top view cut at z = 25: a ring; cut at z = 0 (on the bottom face): nothing left, no flickering ring;
- an assembly of two of them: set_view section y: both cut and capped (four walls on a row); its ✂ button too.

  PYTHONIOENCODING=utf-8 py tools/e2e_section_revolved.py http://127.0.0.1:5199 <out dir>
"""
import base64
import io
import json
import sys
import time

from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1400,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"
A = "window.__app.assembly"
H = "window.__app.agentHandlers"
fails = []


def check(what, ok, *more):
    print("OK  " if ok else "FAIL", what, *more)
    if not ok:
        fails.append(what)


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


def shot(name, **args):
    """get_screenshot -> the picture as RGB, saved as <name>.png."""
    r = js(f"return {H}.get_screenshot(arguments[0]).then(r => [r.text, r.image]).catch(e => ['ERROR ' + e.message, null])", args)
    if not r[1]:
        print("no picture:", r[0])
        return None
    raw = base64.b64decode(r[1])
    open(f"{OUT}/{name}.png", "wb").write(raw)
    return Image.open(io.BytesIO(raw)).convert("RGB")


def is_cap(p):
    r, g, b = p
    return r > 90 and g > 40 and b > 30 and r - g > 40 and r - b > 50  # (brick red; not the origin's red / orange x arrow)


def cap_box(img):
    """The box round the cap-coloured pixels (None: none) and their count."""
    px, w = img.load(), img.width
    xs, ys, n = [], [], 0
    for y in range(0, img.height, 2):
        for x in range(0, w, 2):
            if is_cap(px[x, y]):
                xs.append(x)
                ys.append(y)
                n += 1
    return ((min(xs), min(ys), max(xs), max(ys)) if xs else None), n


def runs(img, y):
    """The cap-coloured runs along row y -> [(x0, x1)] (gaps of a pixel or two closed)."""
    px, out, start = img.load(), [], None
    for x in range(img.width + 1):
        c = x < img.width and is_cap(px[x, y])
        if c and start is None:
            start = x
        if not c and start is not None:
            if out and start - out[-1][1] <= 3:
                out[-1] = (out[-1][0], x - 1)
            else:
                out.append((start, x - 1))
            start = None
    return [r for r in out if r[1] - r[0] > 3]


def ratios(rs):
    """Runs [(a0, a1), (b0, b1)] -> (left wall, gap, right wall) widths, as fractions of the whole."""
    (a0, a1), (b0, b1) = rs
    whole = b1 - a0
    return round((a1 - a0) / whole, 2), round((b0 - a1) / whole, 2), round((b1 - b0) / whole, 2)


def near(got, want, tol=0.04):
    return len(got) == len(want) and all(abs(g - w) <= tol for g, w in zip(got, want))


def caps(host):
    """The caps drawn: [[x0, y0, z0, x1, y1, z1], area]."""
    return js(f"""{host}.view.updateCaps(); const g = {host}.view.capGroup; if (!g) return [];
      return g.children.map(c => {{ const p = c.geometry.attributes.position.array, lo = [1e9, 1e9, 1e9], hi = [-1e9, -1e9, -1e9];
        let s = 0;
        for (let i = 0; i < p.length; i += 9) {{
          const u = [0, 1, 2].map(k => p[i + 3 + k] - p[i + k]), v = [0, 1, 2].map(k => p[i + 6 + k] - p[i + k]);
          s += Math.hypot(u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]) / 2;
        }}
        for (let i = 0; i < p.length; i++) {{ lo[i % 3] = Math.min(lo[i % 3], p[i]); hi[i % 3] = Math.max(hi[i % 3], p[i]); }}
        return [[...lo, ...hi].map(v => +v.toFixed(2)), +s.toFixed(1)]; }});""")


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Pump body")
    call("add_feature", type="sketch", plane="XZ", shapes=[{"polyline": {"points": [[5, 0], [20, 0], [20, 10], [12, 10], [12, 40], [5, 40]]}}])
    r = call("add_feature", type="revolve", sketch="F1", axis="y", angle=360)
    wait(f"return !!{M}.result?.body && !{M}.inflight")
    check("the revolved tube", js(f"return {M}.result.body.bbox") == [-20, -20, 0, 20, 20, 40], js(f"return {M}.result.body.bbox"))

    # ✂ from the toolbar: Y at the middle (0)
    d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=section]").click()
    time.sleep(0.6)
    check("✂ Section: y at 0", js(f"return {M}.section") == {"axis": "y", "offset": 0, "flip": False}, js(f"return {M}.section"))
    c = caps(M)
    check("one cap, the profile's area twice (720 mm²)", len(c) == 1 and abs(c[0][1] - 720) < 720 * 0.01, c)
    check("the cap inside the part, in the plane y = 0", c and all(abs(v) < 0.1 for v in (c[0][0][1], c[0][0][4]))
          and c[0][0][0] >= -20.01 and c[0][0][3] <= 20.01 and c[0][0][2] >= -0.01 and c[0][0][5] <= 40.01, c and c[0][0])
    d.save_screenshot(f"{OUT}/gui_section_y.png")
    img = shot("gui_front_y", view="front")
    box, n = cap_box(img)
    h = box[3] - box[1] if box else 0
    row = lambda z: int(box[3] - h * z / 40)
    check("on screen: the cap seen from the front", n > 2000, n, box)
    check("tube (z = 25): two walls, the bore open between them (7 : 10 : 7)", near(ratios(runs(img, row(25))), (7 / 24, 10 / 24, 7 / 24)), runs(img, row(25)))
    check("flange (z = 5): 15 : 10 : 15", near(ratios(runs(img, row(5))), (15 / 40, 10 / 40, 15 / 40)), runs(img, row(5)))

    js("const b = document.querySelector('.m-section [data-ax=x]'); b.click()")
    time.sleep(0.4)
    c = caps(M)
    check("✂ X: the cap in the plane x = 0, 720 mm²", js(f"return {M}.section.axis") == "x" and len(c) == 1 and abs(c[0][0][0]) < 0.1 and abs(c[0][1] - 720) < 7.2, c)
    img = shot("gui_right_x", view="right")
    box, n = cap_box(img)
    check("X from the right: the cap seen", n > 2000, n)
    js("document.querySelector('.m-section [data-x]').click()")
    time.sleep(0.3)
    check("✕: no section, no caps", js(f"return {M}.section") is None and caps(M) == [], caps(M))

    # the AI's way, as in the report
    t = call("set_view", view="front", section={"axis": "y", "offset": 0})
    check("set_view section y 0", "cut along y at 0" in t, t)
    img = shot("ai_front_y", view="front")
    box, n = cap_box(img)
    h = box[3] - box[1] if box else 0
    check("AI picture: the cap seen", n > 2000, n, box)
    check("AI picture: no oversized cap (40 × 40 mm, square)", box and 0.9 < (box[2] - box[0]) / max(h, 1) < 1.1, box)
    check("AI picture: the bore open (7 : 10 : 7)", box and near(ratios(runs(img, row(25))), (7 / 24, 10 / 24, 7 / 24)), box and runs(img, row(25)))
    call("set_view", section={"axis": "y", "offset": 0, "flip": True})
    img = shot("ai_front_y_flip", view="front")
    check("flipped: the near half kept, its cap faces away", cap_box(img)[1] < 300, cap_box(img)[1])
    call("set_view", view="top", section={"axis": "z", "offset": 25})
    c = caps(M)
    check("z at 25: a ring (π (12² − 5²) = 373.8 mm²)", len(c) == 1 and abs(c[0][1] - 373.85) < 373.85 * 0.01 and abs(c[0][0][2] - 25) < 0.1, c)
    img = shot("ai_top_z25", view="top")
    box, n = cap_box(img)
    rs = runs(img, (box[1] + box[3]) // 2 + 4) if box else []
    check("top: the ring, the bore open in it (7 : 10 : 7)", len(rs) == 2 and near(ratios(rs), (7 / 24, 10 / 24, 7 / 24)), rs)
    call("set_view", view="iso", section={"axis": "z", "offset": 0})
    img = shot("ai_iso_z0", view="iso")
    check("z at 0 (on the bottom face): nothing left, no ring", caps(M) == [] and cap_box(img)[1] == 0, caps(M), cap_box(img)[1])
    call("set_view", section=None)
    check("set_view section off", js(f"return {M}.section") is None and caps(M) == [])

    # an assembly of two
    time.sleep(1)
    call("new_assembly", name="Two pumps")
    for x in (0, 60):
        r = call("insert_part", part="Pump body")
        call("place_part", part=json.loads(r)["parts"][-1]["id"], x=x)
    time.sleep(1)
    t = call("set_view", view="front", section={"axis": "y", "offset": 0})
    check("assembly: set_view section y 0", "cut along y at 0" in t, t)
    c = caps(A)
    check("assembly: both parts capped, 720 mm² each", len(c) == 2 and all(abs(a - 720) < 7.2 for _, a in c), c)
    img = shot("asm_front_y", view="front")
    box, n = cap_box(img)
    h = box[3] - box[1] if box else 0
    rs = runs(img, int(box[3] - h * 25 / 40)) if box else []
    check("assembly picture: four walls on a row", len(rs) == 4, rs)
    call("set_view", section=None)
    check("assembly: section off, no caps", caps(A) == [])
    d.find_element(By.CSS_SELECTOR, "#asmViewport [data-a=section]").click()
    time.sleep(0.6)
    check("assembly ✂ button: y at the middle, both capped", js(f"return {A}.section?.axis") == "y" and len(caps(A)) == 2, js(f"return {A}.section"), caps(A))
    d.save_screenshot(f"{OUT}/asm_gui_section.png")
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    d.quit()
print("FAILED:", fails if fails else "none")
sys.exit(1 if fails else 0)
