"""Compact command bars, in headless Edge: at 1280×800 the 3D model's bar, the sketch's bar and the assembly's bar
(with its 🔗 Joint row) take at most 2 rows — their tools show only their icons, the name goes first in the tooltip —
in English and in Czech; at 1600×1000 they keep their full names (as before); a narrower window compacts the bar
live (a ResizeObserver), a wider one brings the names back.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_compact_bars.py http://127.0.0.1:5199 <out dir>
"""
import sys
import time

from selenium import webdriver

URL, OUT = sys.argv[1], sys.argv[2]
M = "window.__app.modeler"
A = "window.__app.assembly"
H = "window.__app.agentHandlers"
ok = []


def check(name, cond):
    ok.append(bool(cond))
    print(f"  {name}: {'OK' if cond else 'FAIL'}")


def browser(w, h):
    opts = webdriver.EdgeOptions()
    opts.add_argument("--headless=new")
    opts.add_argument(f"--window-size={w},{h}")
    opts.add_argument("--lang=en-US")
    opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
    return webdriver.Edge(options=opts)


def wait(d, script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = d.execute_script(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def call(drv, tool_name, **args):
    return drv.execute_script(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def bar(d, vp):
    """The bar's height, its rows (the tops of its controls), whether it is compact, and its tool buttons
    ([shown text, title]) -> dict."""
    return d.execute_script("""const bar = document.querySelector(arguments[0] + ' > .m-cmdbar'), tops = [];
      for (const e of bar.querySelectorAll('button, label, .m-mode, .m-say, .as-jlabel')) {
        if (e.closest('.mp-actions, .menu-list') || !e.offsetWidth) continue;
        tops.push(e.getBoundingClientRect().top);
      }
      tops.sort((a, b) => a - b);
      let rows = 0, last = -1e9;
      for (const y of tops) if (y > last + 10) { rows++; last = y; }
      const tools = [...bar.querySelectorAll('button[data-a], button[data-joint]')].filter((b) => !b.closest('.mp-actions, .menu-list'))
        .map((b) => [b.innerText.replace(/\\s+/g, ' ').trim(), b.title || '', Math.round(b.getBoundingClientRect().width), b.dataset.a || b.dataset.joint, b.dataset.icon || '']);
      return { h: bar.offsetHeight, rows, compact: bar.classList.contains('cb-compact'), tools };""", vp)


def lang(d, cs):
    if (d.execute_script("return document.documentElement.lang") == "cs") != cs:
        d.find_element("id", "langBtn").click()
        time.sleep(0.8)


def setup_model(d):
    d.get(URL)
    wait(d, "return !!window.__app")
    d.execute_script("localStorage.removeItem('auto3d-lang')")
    call(d, "new_model", name="Block")
    call(d, "add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call(d, "add_feature", type="extrude", sketch="F1", d=20)
    wait(d, f"return !!{M}.result?.body && !{M}.inflight")
    time.sleep(0.6)


def enter_sketch(d):
    d.execute_script(f"{M}.action('sketch')")
    time.sleep(0.4)
    d.execute_script(f"{M}.action('datum-XY')")
    wait(d, f"return {M}.mode === 'sketch'")
    time.sleep(0.6)


def leave_sketch(d):
    d.execute_script(f"{M}.action('cancelSketch')")
    time.sleep(0.5)


def setup_assembly(d):
    call(d, "new_assembly", name="Pair")
    call(d, "insert_part", part="Block")
    call(d, "insert_part", part="Block")
    wait(d, f"return Object.values({A}.bodies).every(b => b.body)")
    time.sleep(0.8)


def errors(d):
    return [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]


errs = []
# ---------------------------------------------------------------- 1280×800: at most 2 rows, icons only
d = browser(1280, 800)
try:
    setup_model(d)
    for cs in (False, True):
        lang(d, cs)
        L = "cs" if cs else "en"
        b = bar(d, "#modelViewport")
        print(f"[{L}] 3D model bar at 1280x800: {b['h']} px, {b['rows']} rows, compact={b['compact']}")
        check(f"[{L}] the 3D model bar takes at most 2 rows", b["rows"] <= 2)
        ext = next(x for x in b["tools"] if x[3] == "extrude")
        print(f"[{L}]   Extrude button: {ext}")
        check(f"[{L}] Extrude shows only its icon, its name leads the tooltip", ext[4] == "⬆" and ext[2] < 40 and ext[1].split(":")[0] in ("Extrude", "Vysunutí") and (not cs or "Dát skice výšku" in ext[1]))
        d.save_screenshot(f"{OUT}/compact_model_1280_{L}.png")

        enter_sketch(d)
        b = bar(d, "#modelViewport")
        print(f"[{L}] sketch bar at 1280x800: {b['h']} px, {b['rows']} rows, compact={b['compact']}")
        check(f"[{L}] the sketch bar takes at most 2 rows", b["rows"] <= 2)
        rect = next(x for x in b["tools"] if x[3] == "rect")
        print(f"[{L}]   Rectangle button: {rect}")
        check(f"[{L}] Rectangle shows only its icon, named in the tooltip", rect[4] == "▭" and rect[2] < 40 and rect[1].split(":")[0] in ("Rectangle", "Obdélník"))
        check(f"[{L}] the plane buttons (no icon) keep their text", all(x[0] for x in b["tools"]))
        hint_ok = d.execute_script("""const b = document.querySelector('#modelViewport > .m-cmdbar'), h = document.querySelector('#modelViewport > .m-hint');
          return !h || h.hidden || h.getBoundingClientRect().top >= b.getBoundingClientRect().bottom""")
        check(f"[{L}] the hint is under the bar", hint_ok)
        d.save_screenshot(f"{OUT}/compact_sketch_1280_{L}.png")
        leave_sketch(d)
    lang(d, False)

    # a wider view (the side panel narrower) brings the names back, live
    d.set_window_size(1900, 1000)
    time.sleep(0.8)
    b = bar(d, "#modelViewport")
    print(f"wider window (1900): {b['h']} px, {b['rows']} rows, compact={b['compact']}")
    check("a wider window brings the names back", not b["compact"] and any(x[0] == "⬆ Extrude" for x in b["tools"]))
    check("... and the tooltips as they were", any(x[1].startswith("Give a sketch a height") for x in b["tools"]))
    d.set_window_size(1280, 800)
    time.sleep(0.8)
    check("narrower again: icons only", bar(d, "#modelViewport")["compact"])

    setup_assembly(d)
    for cs in (False, True):
        lang(d, cs)
        L = "cs" if cs else "en"
        b = bar(d, "#asmViewport")
        print(f"[{L}] assembly bar at 1280x800: {b['h']} px, {b['rows']} rows, compact={b['compact']}")
        check(f"[{L}] the assembly bar takes at most 2 rows", b["rows"] <= 2)
        j = next(x for x in b["tools"] if x[3] == "joints")  # (🔗 Joint ▾: the joint types in its menu)
        print(f"[{L}]   a joint button: {j}")
        d.save_screenshot(f"{OUT}/compact_assembly_1280_{L}.png")
    lang(d, False)
    errs += errors(d)
finally:
    d.quit()

# ---------------------------------------------------------------- 1600×1000: as before, full names
d = browser(1600, 1000)
try:
    setup_model(d)
    for cs in (False, True):
        lang(d, cs)
        L = "cs" if cs else "en"
        b = bar(d, "#modelViewport")
        print(f"[{L}] 3D model bar at 1600x1000: {b['h']} px, {b['rows']} rows, compact={b['compact']}")
        check(f"[{L}] 1600: the 3D model bar keeps its names", not b["compact"] and any(x[0] in ("⬆ Extrude", "⬆ Vysunutí") for x in b["tools"]))
        d.save_screenshot(f"{OUT}/compact_model_1600_{L}.png")
        enter_sketch(d)
        b = bar(d, "#modelViewport")
        print(f"[{L}] sketch bar at 1600x1000: {b['h']} px, {b['rows']} rows, compact={b['compact']}")
        d.save_screenshot(f"{OUT}/compact_sketch_1600_{L}.png")
        leave_sketch(d)
    lang(d, False)
    setup_assembly(d)
    for cs in (False, True):
        lang(d, cs)
        L = "cs" if cs else "en"
        b = bar(d, "#asmViewport")
        print(f"[{L}] assembly bar at 1600x1000: {b['h']} px, {b['rows']} rows, compact={b['compact']}")
        d.save_screenshot(f"{OUT}/compact_assembly_1600_{L}.png")
    lang(d, False)
    b = bar(d, "#asmViewport")
    check("1600: the assembly bar keeps its names", not b["compact"] and any("Measure" in x[0] for x in b["tools"]))
    errs += errors(d)
finally:
    d.quit()

print("console errors:", errs)
print("ALL OK" if ok and all(ok) and not errs else f"FAILED ({ok.count(False)} of {len(ok)})")
