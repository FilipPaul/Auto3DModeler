"""A chosen Hole step: its types and sizes as rows of the suggestions, its fields in the right panel, in headless Edge
with real mouse clicks: a 60 × 40 × 10 block, an M5 ⌴ counterbore hole (◎ Hole) and a Ø8 round pocket cut by an
extrude -> a click on the hole's wall: its properties each a section of compact rows, no popup — Shape (the 4, ⌴
Counterbore ✓), Thread (🔩 Add thread M5), Depth (through all ⇄ to a depth), Size (exactly M3 M4 ✓M5 M6 M8); the right panel shows the hole step, its row in the list marked
-> one click ⌵ Countersink: its exact volume -> one click M6: the M6 countersink's volume -> Ctrl+Z: M5 again -> its
rim: the same rows above the edge's -> the pocket's wall: no Shape / Size -> 🔩 Add thread M5: a threaded countersink,
shown; Thread: hide -> hidden; the depth row both ways -> at 1280 × 800 the table scrolls inside (no scrollbar, a fade at the hidden edge), its head in sight,
all the choices shown past the top N.

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


def table():
    """The suggestions table as [[section, [[row text, current?], ...]], ...] (rows before any section: under "")."""
    return js("""const out = [];
      for (const el of document.querySelectorAll('#modelViewport .view-suggest .vs-list > *')) {
        if (el.classList.contains('vs-sec')) out.push([el.textContent.trim(), []]);
        else if (el.dataset.sg !== undefined) { if (!out.length) out.push(['', []]); out[out.length - 1][1].push([el.textContent.split(/\\s+/).join(' ').trim(), el.classList.contains('on')]); }
      }
      return out;""")


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

    # ---- a click on the hole's wall: its types and sizes as rows (no second popup)
    o = wall_of("F3", [15, 20, 7])
    print("the hole's wall at", o)
    click_off(o)
    t = table()
    print("table:", t[:4])
    check("Shape is the first section: the 4 shapes as rows, ⌴ Counterbore ✓", t and t[0][0] in ("Shape", "Tvar") and len(t[0][1]) == 4
          and [x for x, on in t[0][1] if on] and "Counterbore" in [x for x, on in t[0][1] if on][0] and sum(on for _, on in t[0][1]) == 1)
    dep = dict(t).get("Depth") or dict(t).get("Hloubka") or []
    check("Depth: one row, through all ⇄ to a depth", len(dep) == 1 and "⇄" in dep[0][0])
    sizes = dict(t).get("Size") or dict(t).get("Velikost") or []
    check("Size: exactly M3 M4 ✓M5 M6 M8 as rows", [x.split()[-1].rstrip("✓") for x, _ in sizes] == ["M3", "M4", "M5", "M6", "M8"] and [on for _, on in sizes] == [False, False, True, False, False])
    thr = dict(t).get("Thread") or dict(t).get("Závit") or []
    check("Thread: 🔩 Add thread M5 (not threaded yet)", len(thr) == 1 and "M5" in thr[0][0] and ("Add thread" in thr[0][0] or "Přidat závit" in thr[0][0]))
    check("no popup to open", not js("return !!document.querySelector('.choose-back')"))
    h = js("return [...document.querySelectorAll('#modelViewport .view-suggest .vs-pin-row')].map(b => b.getBoundingClientRect().height)")
    check(f"compact rows (~24 px: {sorted(set(round(x) for x in h))})", h and all(22 <= x <= 27 for x in h))
    check("the hole step chosen, no tool open", js(f"return {M}.selected") == "F3" and js(f"return !{M}.cmd"))
    panel = js("return [document.querySelector('#modelRight h2')?.textContent, document.querySelector('#modelRight .m-hshape [data-shape].on')?.dataset.shape, document.querySelector('#modelRight [data-k=standard]')?.value]")
    print("right panel:", panel)
    check("the right panel shows the hole step (its shape ⌴, Size M5)", panel == ["Hole 1", "counterbore", "M5"])
    check("its row in the list is marked", js("return !!document.querySelector('#modelLeft .mt-item.on[data-id=F3]')"))
    d.save_screenshot(f"{OUT}/hole_suggest.png")

    # ---- one click: ⌵ Countersink
    row(["Countersink", "Kuželové"]).click()
    settled()
    v = vol()
    f3 = js(f"return {M}.part.features.find(f => f.id === 'F3')")
    check(f"⌵ Countersink: its exact volume ({v:.2f} vs {BASE - CSK5:.2f})", f3["head"] == "csk" and abs(v - (BASE - CSK5)) < 0.5)
    check("the table again: Countersink ✓", any("Countersink" in x or "Kuželové" in x for x, on in table()[0][1] if on))

    # ---- one click: M6
    row(["M6"]).click()
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
    t = table()
    print("rim table:", [s for s, _ in t])
    check("its rim: the hole chosen, Shape / Size above Fillet", js(f"return {M}.selected") == "F3" and t and t[0][0] in ("Shape", "Tvar")
          and any("Fillet" in x or "Zaobl" in x for _, rs in t for x, _ in rs))

    # ---- the pocket's wall: not a Hole step
    js(f"{M}.selectStep(null)")
    o = wall_of("F5", [45, 20, 7])
    click_off(o)
    t = table()
    print("pocket sections:", [s for s, _ in t])
    check("the round pocket: no Shape / Size rows", t and not any(s in ("Shape", "Tvar", "Size", "Velikost") for s, _ in t))
    check("the right panel is the part's again", js("return !document.querySelector('#modelRight .m-hshape')"))

    # ---- 🔩 a thread: added, then shown / hidden
    js(f"{M}.selectStep('F3'); {M}.suggestStep('F3')")
    time.sleep(0.5)
    row(["Add thread", "Přidat závit"]).click()
    settled()
    f3 = js(f"return {M}.part.features.find(f => f.id === 'F3')")
    thr = dict(table()).get("Thread") or dict(table()).get("Závit") or []
    print("thread rows:", thr, "| threads:", js(f"return {M}.part.threads"))
    check("🔩 Add thread M5: a threaded M5 countersink (the tap drill), shown (cosmetic)", f3.get("thread") == "M5" and f3.get("shape") == "countersink" and f3.get("d") == 4.2
          and js(f"return {M}.part.threads") == "cosmetic")
    check("its rows: With thread M5 ✓ · Thread: hide · Real thread", len(thr) == 3 and thr[0][1] and "M5" in thr[0][0] and any("hide" in x or "skrýt" in x for x, _ in thr) and any("Real" in x or "Skutečný" in x for x, _ in thr))
    row(["Thread: hide", "Závit: skrýt"]).click()
    settled()
    thr = dict(table()).get("Thread") or dict(table()).get("Závit") or []
    check("Thread: hide -> hidden, the row says show", not js(f"return {M}.part.threads") and any("show" in x or "zobrazit" in x for x, _ in thr))
    row(["Through all", "Skrz vše"]).click()
    settled()
    check("the depth row: to a depth (10)", js(f"return {M}.part.features.find(f => f.id === 'F3').through") is False)
    row(["To a depth", "Do hloubky"]).click()
    settled()
    check("…and through all again", js(f"return {M}.part.features.find(f => f.id === 'F3').through") is True)

    # ---- a small window: the table scrolls inside (no scrollbar, a fade), its head stays
    d.set_window_size(1280, 800)
    time.sleep(0.8)
    js(f"{M}.selectStep(null); {M}.selectStep('F3'); {M}.suggestStep('F3')")
    time.sleep(0.8)
    sc = js("""const b = document.querySelector('#modelViewport .view-suggest'), l = b.querySelector('.vs-list'), h = b.querySelector('.vs-head'), vr = b.parentElement.getBoundingClientRect(), br = b.getBoundingClientRect();
      return { sh: l.scrollHeight, ch: l.clientHeight, bar: l.offsetWidth - l.clientWidth, fadeB: l.classList.contains('fade-b'), head: h.getBoundingClientRect().top >= vr.top && h.getBoundingClientRect().bottom <= vr.bottom,
        inside: br.top >= vr.top - 1 && br.bottom <= vr.bottom + 1, rows: l.querySelectorAll('button[data-sg]').length, pinned: l.querySelectorAll('.vs-pin-row').length };""")
    print("1280 × 800:", sc)
    check("1280 × 800: the rows scroll inside the table, the head in sight", sc["sh"] > sc["ch"] + 5 and sc["head"] and sc["inside"])
    check("no scrollbar, a fade at the bottom", sc["bar"] == 0 and sc["fadeB"])
    check(f"the choices past the top N all shown ({sc['pinned']} pinned of {sc['rows']})", sc["pinned"] >= 13)
    d.save_screenshot(f"{OUT}/hole_suggest_small.png")
    js("const l = document.querySelector('#modelViewport .view-suggest .vs-list'); l.scrollTop = l.scrollHeight")
    time.sleep(0.4)
    check("scrolled down: the fade at the top", js("return document.querySelector('#modelViewport .view-suggest .vs-list').classList.contains('fade-t')"))
    d.save_screenshot(f"{OUT}/hole_suggest_small_end.png")
finally:
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        fails.append("console errors")
    d.quit()

print("FAILED:" if fails else "ALL OK", fails if fails else "")
sys.exit(1 if fails else 0)
