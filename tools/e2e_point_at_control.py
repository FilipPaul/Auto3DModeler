"""A message that names a control points at it (web/js/pointat.js), in headless Edge, in Czech, with real clicks: a new
3D model, E (⬆ Vysunout) with no sketch -> the toast "Nejprve nakreslete skicu (✏ Skica)" and a pulsing ring on ✏ Skica in
the toolbar (no dimming of the screen) -> gone after ~2.6 s -> the same message again at once: no ring (in moderation)
-> a click on the toast's text: the ring again, the toast stays -> a press elsewhere: the ring goes -> a control in a
folded widget (the step tree folded in the left column): unfolded, scrolled to, ringed -> one ring at a time.

  PYTHONIOENCODING=utf-8 py tools/e2e_point_at_control.py http://127.0.0.1:5199 <out dir>
"""
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


def rings():
    return js("return document.querySelectorAll('.teach-ring.pt-ring:not(.pt-out)').length")


def ring_on(sel):
    """Is the pointing ring shown around the control `sel` (its middle inside the ring)?"""
    return js("""const r = document.querySelector('.teach-ring.pt-ring:not(.pt-out)'), el = [...document.querySelectorAll(arguments[0])].find((e) => e.getClientRects().length);
      if (!r || r.hidden || !el) return false;
      const a = r.getBoundingClientRect(), b = el.getBoundingClientRect(), cx = b.left + b.width / 2, cy = b.top + b.height / 2;
      return cx > a.left && cx < a.right && cy > a.top && cy < a.bottom;""", sel)


def extrude():
    """E (⬆ Vysunout — its button is greyed out with no sketch: the key still asks)."""
    d.find_element(By.CSS_SELECTOR, "body").send_keys("e")
    time.sleep(0.4)


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.setItem('auto3d-lang', 'cs'); localStorage.removeItem('a3d.leftDock')")
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Ukázka")
    time.sleep(0.8)

    extrude()
    t = [e for e in d.find_elements(By.CSS_SELECTOR, "#toasts .toast") if "skic" in e.text.lower()]
    check(f"E (⬆ Vysunout) with no sketch: the toast says so ({[x.text for x in t]})", bool(t))
    check("a ring on ✏ Skica in the toolbar", ring_on("#modelViewport .m-cmdbar [data-a=sketch]"))
    check("no dimming: the ring has no screen-wide shadow", "9999px" not in js("return getComputedStyle(document.querySelector('.teach-ring.pt-ring')).boxShadow"))
    d.save_screenshot(f"{OUT}/point_sketch.png")
    time.sleep(3.0)
    check("gone after a few seconds", rings() == 0)
    extrude()
    check("the same message again at once: no ring (in moderation)", rings() == 0)
    t = [e for e in d.find_elements(By.CSS_SELECTOR, "#toasts .toast") if "skic" in e.text.lower()]
    t[-1].click()
    time.sleep(0.3)
    check("a click on the toast's text: the ring again, the toast stays", ring_on("#modelViewport .m-cmdbar [data-a=sketch]") and t[-1].is_displayed())
    check("its tooltip says so", "ukážu" in (t[-1].get_attribute("title") or ""))
    ActionChains(d).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, "#modelViewport canvas"), 0, 0).click().perform()
    time.sleep(0.4)
    check("a press elsewhere: the ring goes", rings() == 0)

    # a control in a folded widget: unfolded, scrolled to, ringed — one ring at a time
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 20, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    time.sleep(1)
    js("window.__leftDock.fold('panel', true)")
    time.sleep(0.4)
    check("the step tree's widget folded", js("return document.querySelector('.lw-widget[data-w=panel][data-ws=model]')?.classList.contains('folded')"))
    js("return import('/js/pointat.js').then(m => { m.pointAt('#modelViewport .m-cmdbar [data-a=sketch]'); m.pointAt('.mt-tree .mt-row'); })")
    time.sleep(0.5)
    check("pointed at a step row: its widget unfolded", not js("return document.querySelector('.lw-widget[data-w=panel][data-ws=model]').classList.contains('folded')"))
    check("the row ringed, one ring at a time", ring_on(".mt-tree .mt-row") and rings() == 1)
    d.save_screenshot(f"{OUT}/point_unfolded.png")
    errs = [x["message"] for x in d.get_log("browser") if x["level"] == "SEVERE"]
    check(f"no errors in the console: {errs[:3]}", not errs)
finally:
    js("localStorage.removeItem('auto3d-lang')")
    d.quit()

print("FAILED:" if fails else "ALL OK", *fails, sep="\n  ")
sys.exit(1 if fails else 0)
