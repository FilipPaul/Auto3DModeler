"""🎬 The two cable demos, in headless Edge: Open ▾ → Demo projects… lists "Portálový pojezd" and "Otočné rameno s
kabelem" (names and texts in Czech too) -> each opened from the menu -> its mechanism driven to its two limits and its
middle: at each, every harness has no ⚠ (not taut, nothing it goes through or still hits, no bend too tight, no span
not kept), a 🔒 length stays what it was locked at, a ➰ span keeps its own length, no parts overlap (the server's
check) -> the gantry: the ⛓ chain's moving end goes with the carriage (always within its reach), the cable's points on
the carriage go along -> the arm: its tie mounts and its sensor's end swing with it -> ▶ plays: the driver moves and
the cable with it -> no errors in the console.

  PYTHONIOENCODING=utf-8 py tools/e2e_cable_demos.py http://127.0.0.1:5199 <out dir>
"""
import json
import math
import sys
import time
import urllib.request

from selenium import webdriver
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.add_argument("--lang=en-US")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
A = "window.__app.assembly"
H = "window.__app.agentHandlers"
bad = []
FLAGS = ("taut", "through_parts", "still_hits", "bends_too_tight", "spans_not_kept")


def check(ok, what):
    print(("  ok  " if ok else "  FAIL") + " " + what)
    if not ok:
        bad.append(what)


def wait(script, t=90):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def call(t, **a):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", t, a)


def open_demo(file):
    d.find_element(By.ID, "openBtn").click()
    time.sleep(0.2)
    js("document.getElementById('demoBtn').click()")  # (the menu's item: under a toast at times)
    wait("return document.querySelectorAll('.demos [data-demo]').length")
    row = next(r for r in d.find_elements(By.CSS_SELECTOR, ".demos [data-demo]") if r.get_attribute("data-demo") == file)
    row.find_element(By.CSS_SELECTOR, "[data-open]").click()
    wait(f"return window.__app.state.workspace === 'assembly' && {A}.doc.instances.length > 1 && {A}.doc.instances.every(i => {A}.bodies[i.part]?.body) && {A}.mech.list.length")
    time.sleep(1.0)


def at(pos):
    """The mechanism driven to pos -> get_assembly then (the harnesses worked out again: their facts read now)."""
    r = call("drive_mechanism", to=pos)
    check(not r.startswith("ERROR"), f"drive_mechanism to {pos}: {r[:90]}")
    time.sleep(0.6)
    return json.loads(call("get_assembly"))


def clean(a, pos):
    """Every harness at pos: no ⚠ flag, its 🔒 length and its ➰ spans' lengths kept."""
    for h in a.get("harnesses", []):
        flags = {k: h[k] for k in FLAGS if h.get(k)}
        check(not flags, f"at {pos}: {h['id']} “{h.get('name')}” {h['length_mm']} mm — no ⚠ {flags or ''}")
        if h.get("length_locked_mm"):
            check(abs(h["length_mm"] - h["length_locked_mm"]) < 0.5, f"at {pos}: 🔒 {h['length_mm']} mm = locked {h['length_locked_mm']} mm")
        for s in h.get("spans", []):
            if s.get("length_mm"):
                check(abs(s["now_mm"] - s["length_mm"]) < 0.5, f"at {pos}: ➰ span {s['from']}–{s['to']} {s['now_mm']} mm = its {s['length_mm']} mm")


def no_clash(pos):
    r = call("check_collisions")
    check(r.startswith("No parts overlap"), f"at {pos}: no parts overlap ({r[:120]})")


def part(a, i):
    return next(p for p in a["parts"] if p["id"] == i)


def play(secs=2.0):
    """▶ for a while: the driver's part and the cable's points moved."""
    m0 = js(f"return {A}.doc.instances.map(i => [...i.matrix])")
    h0 = json.loads(call("get_assembly"))["harnesses"][0]["point_list"]
    d.find_element(By.CSS_SELECTOR, "[data-mcplay='0']").click()
    time.sleep(secs)
    d.find_element(By.CSS_SELECTOR, "[data-mcplay='0']").click()
    time.sleep(0.5)
    m1 = js(f"return {A}.doc.instances.map(i => [...i.matrix])")
    h1 = json.loads(call("get_assembly"))["harnesses"][0]["point_list"]
    moved = any(any(abs(p - q) > 1e-3 for p, q in zip(x, y)) for x, y in zip(m0, m1))
    went = any(p["xyz"] != q["xyz"] for p, q in zip(h0, h1))
    return moved, went


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('a3d.leftDock'); localStorage.setItem('auto3d-lang', 'en')")
    d.get(URL)
    wait("return !!window.__app")
    listing = {x["file"]: x for x in json.loads(urllib.request.urlopen(f"{URL}/api/demos").read())["demos"]}
    for f, cs in (("portalovy-pojezd.a3d", "Portálový pojezd"), ("otocne-rameno-s-kabelem.a3d", "Otočné rameno s kabelem")):
        x = listing.get(f) or {}
        check(x.get("name_cs") == cs and x.get("text") and x.get("text_cs") and x.get("name") != cs, f"🎬 lists {f}: “{x.get('name')}” / “{x.get('name_cs')}”, its texts")

    # 1. the gantry: a carriage, a ⛓ chain whose moving end goes with it, a 🔒 cable through the chain
    open_demo("portalovy-pojezd.a3d")
    a = json.loads(call("get_assembly"))
    m = a["mechanisms"][0]
    check(m["name"] == "Portálový pojezd" and m["driver"]["label"] == "Pojezd vozíku" and (m["min"], m["max"]) == (-150, 150),
          f"⚙ {m['name']}, driven by “{m['driver']['label']}”, {m['min']} … {m['max']} mm")
    (ch,) = a["chains"]
    (h,) = a["harnesses"]
    check(ch.get("moves_with") == "I3" and "E2.15" in ch["pn"] and h.get("length_locked_mm") and any(s.get("chain") == ch["id"] for s in h.get("spans", [])),
          f"⛓ {ch['pn']} moves with the carriage; the cable {h['id']} 🔒 {h.get('length_locked_mm')} mm runs through it")
    check(sum(1 for p in h["point_list"] if p.get("clip")) == 3 and all(p.get("locked") for p in h["point_list"]), "three 📎 P-clips, every point locked to a part")
    off = set()
    for pos in (-150, 0, 150):
        a = at(pos)
        clean(a, pos)
        no_clash(pos)
        c, car = a["chains"][0], part(a, "I3")["position"]
        off.add(round(c["moving_end"][0] - car[0], 3))
        check(c["reach_ok"] and abs(c["travel_mm"] - pos) < 1e-6, f"at {pos}: the chain's moving end x {c['moving_end'][0]} (travel {c['travel_mm']} mm, within its reach)")
    check(len(off) == 1, f"the moving end goes with the carriage (always {off} mm from it)")
    d.save_screenshot(f"{OUT}/cable_demo_gantry.png")
    moved, went = play()
    check(moved and went, f"▶ moves the carriage ({moved}) and the cable's points with it ({went})")

    # 2. the arm: four loose wires, a ➰ loop across the hinge, tie mounts on the arm
    open_demo("otocne-rameno-s-kabelem.a3d")
    a = json.loads(call("get_assembly"))
    m = a["mechanisms"][0]
    check(m["name"] == "Otočné rameno" and m["driver"]["label"] == "Otáčení ramene" and (m["min"], m["max"]) == (-90, 90),
          f"⚙ {m['name']}, driven by “{m['driver']['label']}”, {m['min']} … {m['max']}°")
    (h,) = a["harnesses"]
    check(h["type"] == "wires" and [w["color"] for w in h["wires"]] == ["brown", "blue", "black", "white"] and any(s.get("length_mm") for s in h.get("spans", [])),
          f"{h['id']}: 4 loose wires {[w['color'] for w in h['wires']]}, a ➰ span of its own length")
    tips = []
    for pos in (-90, 0, 90):
        a = at(pos)
        clean(a, pos)
        no_clash(pos)
        tips.append(a["harnesses"][0]["point_list"][-1]["xyz"])
    swing = math.degrees(math.atan2(tips[2][1] - 220, tips[2][0] - 260) - math.atan2(tips[0][1] - 220, tips[0][0] - 260)) % 360
    check(abs(swing - 180) < 1, f"the sensor's end swings with the arm: {tips[0]} -> {tips[2]} ({swing:.1f}°)")
    d.save_screenshot(f"{OUT}/cable_demo_arm.png")
    moved, went = play()
    check(moved and went, f"▶ swings the arm ({moved}) and the wires with it ({went})")

    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE" and "favicon" not in e["message"]]
    check(not errs, f"no errors in the console: {errs[:3]}")
finally:
    d.quit()

print("\ncable demos:", "ALL OK" if not bad else f"{len(bad)} FAILED: {bad}")
sys.exit(1 if bad else 0)
