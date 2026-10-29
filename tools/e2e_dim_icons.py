"""The icons at an extrude's height on the part (the size editor), with REAL mouse / keyboard input in headless Edge,
in Czech:
1. A block 40 × 30 × 10: click its "↕ 10" label -> the editor with ⇅ / both sides / add ↔ cut icons (no up to a face /
   next — nothing before it; no through all — it adds), Czech tooltips; ⇅ -> the box goes below the sketch (z -10 … 0);
   both sides -> centred (z -5 … 5), lit; Esc closes the editor and its icons; Ctrl+Z -> flipped again; a click away
   closes it too.
2. Two plates with a 10 mm gap, a Ø10 circle on the lower one extruded 3: the icons offer up to a face and up to next;
   up to next -> the boss fills the gap (z 10 … 20, + π · 25 · 10), its label says so; add ↔ cut -> through all is
   offered now (a cut); through all -> the cut goes through the lower plate; Up to a face… opens the Extrude panel to
   click the face (Esc cancels it).
3. A revolve's angle: full turn / half turn icons; half -> 180°.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_dim_icons.py http://127.0.0.1:5199 <out dir>
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


def settled():
    time.sleep(0.3)
    wait(f"return !{M}.inflight")
    time.sleep(0.3)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def check(what, ok, got=""):
    print(f"{'OK ' if ok else 'FAIL'} {what} {got}")
    if not ok:
        fails.append(what)


def zr():
    b = js(f"return {M}.result?.body?.bbox")
    return [round(b[2], 3), round(b[5], 3)] if b else None


def vol():
    return js(f"return {M}.result?.body?.volume ?? 0")


def height_tag():
    """The extrude's height label on the part (it starts with ↕ and is the last one added)."""
    for el in reversed(d.find_elements(By.CSS_SELECTOR, ".m-dimtag")):
        if el.text.startswith("↕") and el.is_displayed():
            return el
    return None


def open_height():
    js(f"{M}.view.setView('iso')")  # (the whole part in sight: its label too)
    time.sleep(0.4)
    tag = height_tag()
    ActionChains(d, duration=40).move_to_element(tag).click().perform()
    wait("return !!document.querySelector('.m-dimedit .m-dimicons')")
    time.sleep(0.3)


def icons():
    return js("return [...document.querySelectorAll('.m-dimedit .m-dimicons [data-ic]')].map(b => b.dataset.ic + (b.classList.contains('on') ? '*' : ''))")


def icon(key):
    b = d.find_element(By.CSS_SELECTOR, f".m-dimedit .m-dimicons [data-ic={key}]")
    ActionChains(d, duration=40).move_to_element(b).click().perform()
    settled()
    wait("return !!document.querySelector('.m-dimedit .m-dimicons')")  # (it opens again on the new label)
    time.sleep(0.2)


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.setItem('auto3d-lang', 'cs'); localStorage.removeItem('a3d.sizes')")
    d.get(URL)
    wait("return !!window.__app")

    # 1. a block: flip, both sides, undo
    call("new_model", name="Block")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 30}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    settled()
    js(f"{M}.selectStep('F2')")
    time.sleep(0.4)
    check("block z 0 … 10", zr() == [0, 10], zr())
    open_height()
    ic = icons()
    check("the icons: flip, both sides, add ↔ cut (no up to / through all on a lone add)", ic == ["flip", "symmetric", "op"], ic)
    tips = js("return [...document.querySelectorAll('.m-dimedit .m-dimicons [data-ic]')].map(b => b.title)")
    print("tooltips:", tips)
    check("tooltips in Czech", "Obrátit směr" in tips[0] and "Na obě strany" in tips[1] and "řez" in tips[2], tips)
    check("one line", js("const r = document.querySelector('.m-dimedit .m-dimicons'); return r.getBoundingClientRect().height < 30"))
    d.save_screenshot(f"{OUT}/di1_icons.png")
    icon("flip")
    check("⇅ flip: below the sketch", zr() == [-10, 0], zr())
    check("flip lit", "flip*" in icons(), icons())
    icon("symmetric")
    check("both sides: centred", zr() == [-5, 5], zr())
    check("both sides lit", "symmetric*" in icons(), icons())
    d.save_screenshot(f"{OUT}/di2_symmetric.png")
    ActionChains(d).send_keys(Keys.ESCAPE).perform()
    settled()
    check("Esc: the editor and its icons gone", not js("return !!document.querySelector('.m-dimedit, .m-dimicons')"))
    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    settled()
    check("Ctrl+Z: one step back — flipped, not centred", zr() == [-10, 0], zr())
    js(f"{M}.selectStep('F2')")
    time.sleep(0.4)
    open_height()
    vp = d.find_element(By.ID, "modelViewport")
    ActionChains(d, duration=40).move_to_element_with_offset(vp, -vp.size["width"] // 2 + 30, vp.size["height"] // 2 - 60).click().perform()
    time.sleep(0.5)
    check("a click away closes it", not js("return !!document.querySelector('.m-dimedit')"))

    # 2. up to next, add ↔ cut, through all, up to a face
    call("new_model", name="Shelf")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="sketch", plane={"datum": "XY", "offset": 10}, shapes=[{"rect": {"x": 0, "y": 0, "w": 5, "h": 40}}])
    call("add_feature", type="extrude", sketch="F3", d=10)
    call("add_feature", type="sketch", plane={"datum": "XY", "offset": 20}, shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 40}}])
    call("add_feature", type="extrude", sketch="F5", d=10)
    call("add_feature", type="sketch", plane={"datum": "XY", "offset": 10}, shapes=[{"circle": {"x": 20, "y": 20, "d": 10}}])
    call("add_feature", type="extrude", sketch="F7", d=3)
    settled()
    v0 = 34000
    js(f"{M}.selectStep('F8')")
    time.sleep(0.4)
    open_height()
    wait("return !!document.querySelector('.m-dimedit [data-ic=next]')", 20)  # (asked the kernel in the background)
    ic = icons()
    check("a part before it: up to a face and up to next offered", ic == ["flip", "symmetric", "upto", "next", "op"], ic)
    icon("next")
    exp = v0 + math.pi * 25 * 10
    check("up to next: fills the gap", abs(vol() - exp) < 1e-3, f"{vol():.3f} expected {exp:.3f}")
    went = js(f"return {M}.status('F8')?.went")
    check("went z 10 … 20", went == {"along": "+z", "range": [10, 20]}, went)
    check("next lit, both sides gone", icons() == ["flip", "upto", "next*", "op"], icons())
    tag = height_tag().text
    check("its label says up to next", "k další ploše" in tag, tag)
    d.save_screenshot(f"{OUT}/di3_upto_next.png")
    icon("next")  # (lit: clicked again -> a typed distance)
    check("next again: back to the 3 mm distance", abs(vol() - (v0 + math.pi * 25 * 3)) < 1e-3 and not js(f"return !!{M}.part.features.at(-1).upto_next"), f"{vol():.3f}")
    icon("op")
    f = js(f"return {M}.part.features.at(-1)")
    check("add ↔ cut: a cut now", f["op"] == "cut", f["op"])
    ic = icons()
    check("a cut: through all offered", "through" in ic, ic)
    icon("through")
    exp = v0 - math.pi * 25 * 10
    check("through all: through the lower plate", abs(vol() - exp) < 1e-3, f"{vol():.3f} expected {exp:.3f}")
    check("through lit", "through*" in icons(), icons())
    d.save_screenshot(f"{OUT}/di4_cut_through.png")
    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    settled()  # (focus in the editor's field: Ctrl+Z goes to the field — Esc first)
    ActionChains(d).send_keys(Keys.ESCAPE).perform()
    settled()
    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    settled()
    check("Ctrl+Z: the cut 3 deep again", abs(vol() - (v0 - math.pi * 25 * 3)) < 1e-3, f"{vol():.3f}")
    js(f"{M}.selectStep('F8')")
    time.sleep(0.4)
    open_height()
    b = d.find_element(By.CSS_SELECTOR, ".m-dimedit .m-dimicons [data-ic=upto]")
    ActionChains(d, duration=40).move_to_element(b).click().perform()
    settled()
    check("Up to a face…: the Extrude panel, waiting for a face", js(f"return !!{M}.cmd?.feature.upto && !{M}.cmd.feature.upto.name") is True)
    d.save_screenshot(f"{OUT}/di5_upto_panel.png")
    ActionChains(d).send_keys(Keys.ESCAPE).perform()
    settled()
    check("Esc: the panel cancelled", js(f"return !{M}.cmd && !{M}.part.features.at(-1).upto") is True)

    # 3. a revolve's angle
    call("new_model", name="Knob")
    call("add_feature", type="sketch", plane="XZ", shapes=[{"rect": {"x": 5, "y": 0, "w": 10, "h": 8}}])
    call("add_feature", type="revolve", sketch="F1", axis="y", angle=360)
    settled()
    v360 = vol()
    js(f"{M}.selectStep('F2')")
    time.sleep(0.4)
    tag = [e for e in d.find_elements(By.CSS_SELECTOR, ".m-dimtag") if e.text.endswith("°")][0]
    ActionChains(d, duration=40).move_to_element(tag).click().perform()
    wait("return !!document.querySelector('.m-dimedit .m-dimicons')")
    ic = icons()
    check("revolve: full / half turn, add ↔ cut", ic == ["full*", "half", "op"], ic)
    icon("half")
    check("half a turn: 180°, half the volume", js(f"return {M}.part.features[1].angle") == 180 and abs(vol() - v360 / 2) < 1e-3 * v360, f"{vol():.2f} / {v360:.2f}")
    d.save_screenshot(f"{OUT}/di6_revolve.png")
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    js("localStorage.removeItem('auto3d-lang')")
    d.quit()
print("FAILED:" if fails else "all OK", fails)
sys.exit(1 if fails or errs else 0)
