"""Soft and hard slider ranges in the 3D tools, in headless Edge: a 40 × 40 × 10 block with a Ø3 hole at x = 3 ->
⁂ Pattern: its count range is only what still reaches the part ("+": soft) — typing 10 keeps 10 (no max on the
number), the slider grows to take it, the panel warns that only some copies reach the part; spacing 3.5 typed: all 10
fit -> OK: the volume of 10 holes -> the pattern's "10×" label on the part: typing 12 is taken too -> Fillet on a top
edge (a hard limit: what OpenCASCADE can build): typing 15 is pulled back to the max, saying why ("a bigger rounding does
not fit here"); in the label's editor 15 is refused with the same reason -> ⟳ Draft: 50° is held at 44.5°.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_slider_grow.py http://127.0.0.1:5199 <out dir>
"""
import math
import sys
import time

from selenium import webdriver
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
H = "window.__app.agentHandlers"
fails = []


def wait(script, t=30):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def check(what, ok):
    print(("  ok  " if ok else "  FAIL") + " " + what)
    if not ok:
        fails.append(what)


def settled():
    time.sleep(0.6)
    wait(f"return !{M}.inflight")
    time.sleep(0.6)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def field(k):
    """The number k of the open tool's panel: [value, min, max, slider max, the range under the slider]."""
    return js(f"""const n = document.querySelector('#modelRight [data-k="{k}"]:not([type=checkbox])'), s = n.closest('.field, label, .mp-hd').nextElementSibling;
      return [n.value, n.getAttribute('min'), n.getAttribute('max'), s.max, s.nextElementSibling?.classList.contains('mp-range') ? s.nextElementSibling.textContent : null]""")


def type_in(k, text):
    inp = d.find_element(By.CSS_SELECTOR, f"#modelRight [data-k={k}]")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys(text)
    time.sleep(0.4)
    return inp


def last_toast():
    return js("return [...document.querySelectorAll('.toast')].map(t => t.textContent).slice(-1)[0] || ''")


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Sliders")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="hole", face="F2:end", points=[[-17, 0]], d=3, through=True)
    settled()
    v1 = js(f"return {M}.result.body.volume")
    check(f"the block with one Ø3 hole ({v1:.2f})", abs(v1 - (16000 - math.pi * 2.25 * 10)) < 0.5)

    # ---- ⁂ Pattern: the count's range is soft
    js(f"{M}.startPattern()")
    settled()
    f0 = field("count")
    print("count at first (value, min, max, slider max, range):", f0)
    check("the count's range says it is a suggestion (“+”)", (f0[4] or "").endswith("+") and f0[2] is None)
    reach = int(f0[3])
    type_in("count", "10")
    settled()
    f1 = field("count")
    print("count 10 typed:", f1, "| feature", js(f"return {M}.cmd.feature.count"))
    check("10 typed is kept (not pulled back to %d)" % reach, f1[0] == "10" and js(f"return {M}.cmd.feature.count") == 10)
    check("the slider grew to take it", float(f1[3]) >= 10)
    warn = " ".join(e.text for e in d.find_elements(By.CSS_SELECTOR, "#modelRight .mp-warn"))
    print("warning:", warn)
    check("the panel says copies run off the part", "reach the part" in warn or "zasáhne" in warn)
    type_in("spacing", "3.5")
    settled()
    print("spacing:", field("spacing"))
    d.save_screenshot(f"{OUT}/slider_grow_pattern.png")
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=ok]").click()
    settled()
    pat = next(f for f in js(f"return {M}.part.features") if f["type"] == "pattern")
    v = js(f"return {M}.result.body.volume")
    print("pattern:", pat["count"], pat["spacing"], "| volume", v)
    check(f"10 holes cut ({v:.2f})", pat["count"] == 10 and abs(v - (16000 - 10 * math.pi * 2.25 * 10)) < 1)

    # the pattern's label on the part (3D size editor): soft too
    js(f"{M}.selectStep(arguments[0])", pat["id"])
    time.sleep(0.8)
    tag = next(e for e in d.find_elements(By.CSS_SELECTOR, ".m-dimtag") if e.text.endswith("×"))
    tag.click()
    time.sleep(1.2)
    num = d.find_element(By.CSS_SELECTOR, ".m-dimedit .px-in")
    num.send_keys(Keys.CONTROL, "a")
    num.send_keys("24")
    time.sleep(0.4)
    smax = js("return +document.querySelector('.m-dimedit input[type=range]').max")
    num.send_keys(Keys.ENTER)
    settled()
    pat = next(f for f in js(f"return {M}.part.features") if f["type"] == "pattern")
    print("label editor: 24 typed -> slider max", smax, "| count", pat["count"])
    check("the label's editor takes 24 (more than its first max 20), its slider grown", pat["count"] == 24 and smax >= 24)
    js(f"{M}.history.go(-1)")
    settled()

    # ---- Fillet: a hard limit — pulled back, saying why
    call("add_feature", type="fillet", edges=[{"a": "F2:end", "b": "F2:side:l1", "fp": [20, 0, 10]}], r=2)
    settled()
    fil = [f for f in js(f"return {M}.part.features") if f["type"] == "fillet"][-1]["id"]
    js(f"{M}.edit(arguments[0])", fil)
    settled()
    wait(f"return document.querySelector('#modelRight [data-k=r]')?.getAttribute('max')")
    print("fillet r:", field("r"))
    type_in("r", "15")
    r = field("r")
    msg = last_toast()
    print("typed 15 ->", r[0], "|", msg)
    check("15 pulled back to the max (≈ 9.9)", 9.5 < float(r[0]) < 10.2 and r[2] is not None)
    check("…saying why", "bigger rounding" in msg or "větší zaoblení" in msg)
    d.save_screenshot(f"{OUT}/slider_grow_fillet.png")
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=cancel]").click()
    settled()
    js(f"{M}.selectStep(arguments[0])", fil)
    time.sleep(0.8)
    next(e for e in d.find_elements(By.CSS_SELECTOR, ".m-dimtag") if e.text.startswith("R")).click()
    wait("return document.querySelector('.m-dimedit .mp-range')")
    num = d.find_element(By.CSS_SELECTOR, ".m-dimedit .px-in")
    num.send_keys(Keys.CONTROL, "a")
    num.send_keys("15")
    time.sleep(0.4)
    why = js("const w = document.querySelector('.m-dimedit-why'); return w && !w.hidden ? w.textContent : ''")
    print("label editor, 15 typed:", why)
    check("the label's editor says why 15 does not go", "bigger rounding" in why or "větší zaoblení" in why)
    num.send_keys(Keys.ESCAPE)
    settled()

    # ---- ⟳ Draft: under 45°
    js(f"{M}.action('draft')")
    settled()
    if js(f"return {M}.cmd?.feature.type") == "draft":
        type_in("angle", "50")
        a = field("angle")
        print("draft 50 typed ->", a, "|", last_toast())
        check("draft: 50° held at 44.5°", a[0] == "44.5" and float(a[3]) <= 45)
        d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=cancel]").click()
        settled()
    else:
        check("draft tool opens", False)
finally:
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        fails.append("console errors")
    d.quit()

print("FAILED:" if fails else "ALL OK", fails if fails else "")
sys.exit(1 if fails else 0)
