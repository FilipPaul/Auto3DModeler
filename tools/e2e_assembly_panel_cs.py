"""A placed part's panel in Czech, in headless Edge (the AI's report 2026-10-29-015647): a base with a pin, a bearing on
it (marked as a library part) and an arm on the bearing's outside -> the arm chosen: its panel's actions in Czech
(◆ Otevřít jeho díl, 📌 Ukotvit na místě, ✕ Vyjmout), each action once on screen (the suggestions table leaves out
what the panel has), its free turn named by a readable face of the library bearing ("válcová plocha Ø22"), not its
step's name -> the joint named "čep ramene": the motion takes that name -> the joint names' tooltips in Czech -> the
base chosen (not joined): gui_state names its turn sliders and boxes ↻ X / ↻ Y / ↻ Z (none "input").

  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_panel_cs.py http://127.0.0.1:5199 <out dir>
"""
import json
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
A = "window.__app.assembly"
H = "window.__app.agentHandlers"


def call(t, **a):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", t, a)


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(script)


def pick(i):
    js(f"{A}.choose(arguments[0])", i)
    time.sleep(0.6)


def texts(sel):
    return [e.replace("\n", " ").strip() for e in js(f"return [...document.querySelectorAll(arguments[0])].filter(e => e.offsetParent).map(e => e.textContent)", sel)]


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.setItem('auto3d-lang', 'cs')")
    d.get(URL)
    wait("return !!window.__app && document.documentElement.lang === 'cs'")
    call("new_model", name="Base")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 60}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="sketch", plane={"face": "F2:end"}, shapes=[{"circle": {"x": 0, "y": 0, "d": 10}}])
    call("add_feature", type="extrude", sketch="F3", d=30)
    call("new_model", name="Bearing")
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 22}}])
    call("add_feature", type="extrude", sketch="F1", d=7)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=10)
    call("new_model", name="Arm")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 30, "y": 0, "w": 80, "h": 30}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=22)
    call("new_assembly", name="Lever")
    js("window.__app.project.parts.find(p => p.name === 'Bearing').data.library = { pn: '608-2Z', maker: 'SKF' }")  # (as a library part)
    for p in ("Base", "Bearing", "Arm"):
        call("insert_part", part=p)
    wait(f"return Object.values({A}.bodies).length === 3 && Object.values({A}.bodies).every(b => b.body)")
    S = lambda **a: call("snap_faces", **a)[:40]  # noqa: E731
    S(type="axis", move={"part": "I2", "face": "F3:hole:0"}, onto={"part": "I1", "face": "F4:side:c1"})
    S(type="touch", move={"part": "I2", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})
    print("the arm on the bearing's outside:", S(type="axis", move={"part": "I3", "face": "F3:hole:0"}, onto={"part": "I2", "face": "F2:side:c1"}))
    S(type="flush", move={"part": "I3", "face": "F2:start"}, onto={"part": "I2", "face": "F2:start"})

    pick("I3")
    panel = " | ".join(texts("#asmRight button"))
    english = [w for w in ("Open its part", "Fix in place", "Take it out", "Make it its own part", "Join it to another part") if w in panel]
    print("the arm's panel buttons:", panel[:300])
    print("  English left:", english)
    assert not english
    shown = texts("#asmRight button, #asmViewport .view-suggest button")
    once = {w: sum(w in s for s in shown) for w in ("Otevřít jeho díl", "Ukotvit na místě", "Udělat z něj vlastní díl", "Vyjmout", "Spojit s jiným dílem")}
    print("  each action on screen:", once, "| the suggestions table:", texts("#asmViewport .view-suggest button"))
    assert all(n == 1 for n in once.values())
    motions = texts("#asmRight .as-dof > label")
    print("  its motions:", motions)
    assert any("Ø22" in m for m in motions) and not any("F2" in m or "Extrude" in m or "Vysunutí" in m for m in motions)
    tips = set(js("return [...document.querySelectorAll('#asmRight [data-jname]')].map(e => e.title)"))
    print("  the joint names' tooltips:", tips)

    call("edit_joint", id="J3", name="čep ramene")
    pick("I1")
    pick("I3")
    motions = texts("#asmRight .as-dof > label")
    tips = set(js("return [...document.querySelectorAll('#asmRight [data-jname]')].map(e => e.title)"))
    print("the joint named:", motions, "| tooltips:", tips)
    assert any("čep ramene" in m for m in motions) and tips == {"Dvojklik: dát jí vlastní název"}

    pick("I1")
    js("const s = document.querySelector('#asmRight details.as-free'); if (s) s.open = true")  # (the base has no joint of its own to move it: as placed)
    time.sleep(0.3)
    turns = [(c["kind"], c["label"]) for c in json.loads(call("gui_state", where="panel"))["controls"] if c["kind"] in ("slider", "box") and "↻" in c["label"] and "J" not in c["label"]]
    unnamed = [c["label"] for c in json.loads(call("gui_state", where="panel"))["controls"] if c["label"] == "input"]
    print("the base's turn controls:", turns, "| unnamed:", unnamed)
    assert {lab for _, lab in turns} >= {"↻ X", "↻ Y", "↻ Z"} and not unnamed
    d.save_screenshot(f"{OUT}/assembly_panel_cs.png")
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    js("localStorage.removeItem('auto3d-lang')")
    d.quit()
