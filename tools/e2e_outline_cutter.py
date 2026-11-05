"""Cookie-cutter photos in the outline wizard (headless Edge): a thin metal strip on paper is found as
one closed outline first ('thin wall'), the Object switch (Auto / Solid object / Thin wall) and ⟳ 90° turn
the picture, then the outline makes a part.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_outline_cutter.py http://127.0.0.1:5199 <abs path to tests/fixtures> <screenshot dir>
Opens cutter-1.jpg … cutter-4.jpg; saves cutter_1.png … cutter_4.png (the detected outline) and
cutter_4_turned.png, cutter_part.png. Exits 1 on a failed check or a console error.
"""
import json
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By

URL, FIX, OUT = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
fails = []


def check(ok, what):
    print("OK  " if ok else "FAIL", what)
    if not ok:
        fails.append(what)


def wait(js, t=60):
    end = time.time() + t
    while time.time() < end:
        v = d.execute_script(js)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(js)


def idle():
    time.sleep(0.4)
    wait("return document.querySelector('.wz-busy').hidden && document.querySelectorAll('.wz-cand').length > 0")
    time.sleep(0.4)


CANDS = """const w = window.__app.wizard; return w.cands.map(c => {
  const pts = c.polygons.flatMap(p => p[0]), xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
  return {thin: c.thin, methods: c.methods, pieces: c.polygons.length,
          w: Math.max(...xs) - Math.min(...xs), h: Math.max(...ys) - Math.min(...ys)}; })"""
IMG = "const w = window.__app.wizard; return [w.img.width, w.img.height]"

try:
    d.get(URL)
    wait("return !!window.__app")
    for i in range(1, 5):
        d.find_element(By.ID, "imgInput").send_keys(str(FIX / f"cutter-{i}.jpg"))
        wait("return document.querySelectorAll('.wz-cand').length > 0")
        idle()
        c = d.execute_script(CANDS)
        check(c[0]["thin"] and "thin wall" in c[0]["methods"] and c[0]["pieces"] == 1,
              f"cutter-{i}: the first candidate is one thin-wall outline ({c[0]['methods']})")
        check(d.execute_script("return document.querySelector('.wz-kind [data-k=auto]').classList.contains('on')"),
              f"cutter-{i}: Object = Auto")
        d.save_screenshot(f"{OUT}/cutter_{i}.png")
        if i < 4:
            d.find_element(By.CSS_SELECTOR, ".wz-cancel").click()
            wait("return !document.querySelector('.wizard')")

    # the bell: Solid object -> no thin-wall candidates; Thin wall -> only those
    d.execute_script("document.querySelector('.wz-kind [data-k=solid]').click()")
    idle()
    c = d.execute_script(CANDS)
    check(not any(x["thin"] or "thin wall" in x["methods"] for x in c), "Solid object: no thin-wall candidates")
    d.execute_script("document.querySelector('.wz-kind [data-k=thin]').click()")
    idle()
    c = d.execute_script(CANDS)
    check(all("thin wall" in x["methods"] for x in c), f"Thin wall: only thin-wall candidates ({len(c)})")
    w0, h0 = d.execute_script(IMG)
    bw, bh = c[0]["w"], c[0]["h"]

    # ⟳ 90°: the picture turns, the outline found again turned (width <-> height)
    d.execute_script("document.querySelector('.wz-rotate').click()")
    idle()
    w1, h1 = d.execute_script(IMG)
    check((w1, h1) == (h0, w0), f"turned picture {w0}x{h0} -> {w1}x{h1}")
    c = d.execute_script(CANDS)
    check(abs(c[0]["w"] - bh) < 6 and abs(c[0]["h"] - bw) < 6,
          f"turned outline {bw:.0f}x{bh:.0f} -> {c[0]['w']:.0f}x{c[0]['h']:.0f}")
    check(d.execute_script("return document.querySelector('.wz-kind [data-k=thin]').classList.contains('on')"),
          "the Object choice is kept")
    d.save_screenshot(f"{OUT}/cutter_4_turned.png")

    # one size typed -> the part
    d.execute_script("""const i = document.querySelector('.wz-w'); i.value = '65'; i.dispatchEvent(new Event('input'));""")
    d.find_element(By.CSS_SELECTOR, ".wz-use").click()
    wait("return window.__app.state.solution && window.__app.state.solution.mesh")
    time.sleep(1.0)
    s = d.execute_script("const s = window.__app.state.solution; return {bbox: s.bbox, ok: s.ok}")
    print("part:", json.dumps(s))
    check(s["ok"] and abs((s["bbox"][2] - s["bbox"][0]) - 65) < 12, "a cookie cutter ~65 mm wide (+ flange)")
    check(d.execute_script("return window.__app.state.model.outline.img_w") == w1, "the part keeps the turned picture")
    d.save_screenshot(f"{OUT}/cutter_part.png")
finally:
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    d.quit()
if fails or errs:
    print("FAILED:", fails)
    sys.exit(1)
print("all OK")
