"""⇄ The position sliders of a part placed by hand (Umístit ručně), in Czech, in headless Edge: a plate and a block in
a new assembly, the block chosen (not joined: its panel is the placing by hand) -> Poloha X / Y / Z sliders above
the Natočení ones, each with its number field -> X slid +20: live while sliding, the matrix 20 mm further on X after
letting go -> Shift + → on the slider: 0.1 mm, → alone: 1 mm -> Y = 15.5 typed: exact -> one Ctrl+Z (undo) takes it
back -> X slid to its slider's end: the slider centred again round the new place on letting go -> the part moved
another way (the matrix, then a draw): the sliders follow -> no console errors.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_manual_position.py http://127.0.0.1:5199 <out dir>
"""
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
A = "window.__app.assembly"
H = "window.__app.agentHandlers"
bad, errs = [], []


def check(ok, what):
    print(("  ok  " if ok else "  FAIL") + " " + what)
    if not ok:
        bad.append(what)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def pos():
    return [round(v, 4) for v in js(f"return {A}.inst('I2').matrix.slice(12, 15)")]


def slider(k):
    return d.find_element(By.CSS_SELECTOR, f"#asmRight input[data-pos={k}]")


def rng(k):
    return [float(slider(k).get_attribute(a)) for a in ("min", "max")]


def slide(k, v, let_go=True):
    """The slider moved to v (input events while sliding; change: let go)."""
    js("arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('input', {bubbles: true}))", slider(k), v)
    if let_go:
        js("arguments[0].dispatchEvent(new Event('change', {bubbles: true}))", slider(k))
        time.sleep(0.4)


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.setItem('auto3d-lang', 'cs')")
    d.get(URL)
    wait("return !!window.__app && document.documentElement.lang === 'cs'")
    call("new_model", name="Plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("new_model", name="Block")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 10, "h": 10}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    time.sleep(1)
    call("new_assembly", name="Hand")
    call("insert_part", part="Plate")
    call("insert_part", part="Block")
    wait(f"return {A}.doc.instances.length === 2 && Object.values({A}.bodies).every(b => b.body)")
    js(f"{A}.sel = 'I2'; {A}.render(); {A}.draw()")
    time.sleep(0.5)

    # 1 the sliders: position above the turns, a number field each, in Czech
    order = js("const b = document.querySelector('#asmRight'); return [...b.querySelectorAll('input[data-pos], input[data-rot]')].map(e => e.dataset.pos ? 'p' + e.dataset.pos : 'r' + e.dataset.rot)")
    check(order == ["px", "py", "pz", "rx", "ry", "rz"], f"Poloha X/Y/Z, then Natočení X/Y/Z: {order}")
    check(all(js(f"return !!document.querySelector('#asmRight input[data-k={k}][type=number]')") for k in "xyz"), "a number field next to each position slider")
    heads = js("return [...document.querySelectorAll('#asmRight h3')].map(h => h.textContent)")
    check("Poloha" in heads and heads.index("Poloha") < heads.index("Natočení"), f"the headings in Czech: {heads}")
    tip = slider("x").find_element(By.XPATH, "..").get_attribute("title")
    check("osy" in tip and "Shift" in tip, f"the tooltip (Czech, the same axes as the turns): {tip[:90]}…")
    p0, (lo, hi) = pos(), rng("x")
    half = (hi - lo) / 2
    check(abs((lo + hi) / 2 - p0[0]) <= 1 and half >= 60, f"the X range centred on {p0[0]}, ± at least the assembly's 60 mm: {lo} – {hi}")
    d.save_screenshot(f"{OUT}/pos_sliders.png")

    # 2 X slid +20: live, then one step on letting go
    slide("x", p0[0] + 20, let_go=False)
    time.sleep(0.2)
    check(pos()[0] == p0[0] + 20, f"live while sliding: X {pos()[0]}")
    js("arguments[0].dispatchEvent(new Event('change', {bubbles: true}))", slider("x"))
    time.sleep(0.4)
    m = js(f"return {A}.inst('I2').matrix")
    check(m[12] == p0[0] + 20 and m[13:15] == p0[1:3] and m[:12] == [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0], f"the matrix 20 mm further on X, not turned: {m}")
    check(js("return document.querySelector('#asmRight input[data-k=x]').value") == str(int(p0[0] + 20)), "the number field shows it")

    # 3 Shift + → : 0.1 mm, → : 1 mm
    x1 = pos()[0]
    js("arguments[0].focus()", slider("x"))  # (a click would move the thumb to where it lands)
    ActionChains(d).key_down(Keys.SHIFT).send_keys(Keys.ARROW_RIGHT).key_up(Keys.SHIFT).perform()
    time.sleep(0.4)
    check(abs(pos()[0] - (x1 + 0.1)) < 1e-6, f"Shift + →: 0.1 mm ({x1} -> {pos()[0]})")
    call("undo")
    time.sleep(0.5)
    js("arguments[0].focus()", slider("x"))
    ActionChains(d).send_keys(Keys.ARROW_RIGHT).perform()
    time.sleep(0.4)
    check(pos()[0] == x1 + 1, f"→ alone: 1 mm ({x1} -> {pos()[0]})")
    call("undo")
    time.sleep(0.5)

    # 4 Y = 15.5 typed: exact; one undo back
    y0 = pos()[1]
    num = d.find_element(By.CSS_SELECTOR, "#asmRight input[data-k=y]")
    num.send_keys(Keys.CONTROL, "a")
    num.send_keys("15.5", Keys.ENTER)
    time.sleep(0.5)
    check(pos()[1] == 15.5, f"Y typed 15.5: {pos()[1]}")
    check(abs(float(slider("y").get_attribute("value")) - 15.5) < 0.51, f"the Y slider there too: {slider('y').get_attribute('value')}")
    call("undo")
    time.sleep(0.5)
    check(pos()[1] == y0, f"one undo: Y back to {pos()[1]}")
    check(pos()[0] == p0[0] + 20, f"…the X move still there: {pos()[0]}")
    call("undo")
    time.sleep(0.5)
    check(pos() == p0, f"one more undo: the +20 on X gone too: {pos()}")

    # 5 slid to the end: centred again on letting go
    lo, hi = rng("x")
    slide("x", hi)
    lo2, hi2 = rng("x")
    check(pos()[0] == hi and hi2 > hi and abs((lo2 + hi2) / 2 - hi) <= 1, f"at the end ({hi}): the range centred again: {lo} – {hi} -> {lo2} – {hi2}")
    slide("x", hi + 5)
    check(rng("x") == [lo2, hi2], f"inside it: the range stays {rng('x')}")

    # 6 moved another way: the sliders follow
    js(f"const it = {A}.inst('I2'); it.matrix = it.matrix.slice(0, 12).concat([7, -3, 2, 1]); {A}.draw()")
    time.sleep(0.2)
    shown = [js(f"return [document.querySelector('#asmRight input[data-pos={k}]').value, document.querySelector('#asmRight input[data-k={k}]').value]") for k in "xyz"]
    check([s[1] for s in shown] == ["7", "-3", "2"] and float(shown[0][0]) == 7, f"the sliders follow a move made elsewhere: {shown}")
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    js("localStorage.removeItem('auto3d-lang')")
    d.quit()
if errs:
    bad.append("console errors")
print("FAILED:" if bad else "ALL OK", bad if bad else "")
sys.exit(1 if bad else 0)
