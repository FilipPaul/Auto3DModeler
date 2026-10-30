"""The AI's smooth shapes, colours and reports, in headless Edge (tool calls through the server's /api/agent/call, as the
MCP server sends them): a duck-like body drawn as one sketch `profile` with a smooth part, revolved -> ONE smooth side
face -> set_look yellow, paint_faces the top orange -> the sketch shows the curve -> an assembly: set_look a placed part,
paint its face, move_free a joined lid along its free way -> save_to_library (then deleted) -> report_problem writes a
dated report into RealSWReports (then deleted).

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_ai_shapes.py http://127.0.0.1:5199 <out dir>
"""
import json
import os
import sys
import time
import urllib.request

from selenium import webdriver

URL, OUT = sys.argv[1], sys.argv[2]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"
A = "window.__app.assembly"


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def ai(tool, **args):
    req = urllib.request.Request(f"{URL}/api/agent/call", data=json.dumps({"tool": tool, "args": args}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        res = json.loads(r.read())
    return ("ERROR " if res.get("isError") else "") + "".join(c.get("text", "") for c in res.get("content", []))


try:
    d.get(URL)
    wait("return !!window.__app")
    time.sleep(1.5)
    ai("new_model", name="Duck body")
    print("sketch:", ai("add_feature", type="sketch", plane="XZ", shapes=[{"profile": {"points": [
        [0, 0], [18, 0], {"smooth": [[26, 10], [24, 24], [14, 32], [16, 42], [10, 50]]}, [0, 52]]}}])[:70])
    print("revolve:", ai("add_feature", type="revolve", sketch="F1", axis="y", angle=360)[:70])
    wait(f"return !!{M}.result?.body && !{M}.inflight")
    faces = js(f"return {M}.result.body.faces.map(f => [f.name, f.type])")
    print("faces:", faces, "| one smooth side:", sum(1 for n, _ in faces if ":side:s" in n) == 1)
    print("set_look:", ai("set_look", color="#FFD400"))
    top = js(f"return {M}.result.body.faces.filter(f => f.type === 'plane').sort((a, b) => b.centroid[2] - a.centroid[2])[0].name")
    print("paint_faces:", ai("paint_faces", faces=[top], color="#FF8800"), "| model:", js(f"return [{M}.part.color, ({M}.part.paint || []).map(p => p.color)]"))
    print("a wrong colour:", ai("set_look", color="yellow")[:60])
    d.save_screenshot(f"{OUT}/ai_duck.png")
    js(f"{M}.edit('F1')")
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.5)
    print("the sketch's curve:", js(f"return {M}.sk.f.entities.map(e => e.t)"), "| drawn as", js(f"return {M}.sk.splineOf({M}.sk.f.entities.find(e => e.t === 'spline')).length"), "points")
    js(f"{M}.cancelSketch ? {M}.cancelSketch() : {M}.action('cancel')")
    time.sleep(0.5)

    # the assembly: look, paint, a free move
    ai("new_model", name="Base")
    ai("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 80, "h": 60}}])
    ai("add_feature", type="extrude", sketch="F1", d=10)
    ai("new_model", name="Lid")
    ai("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 30, "h": 20}}])
    ai("add_feature", type="extrude", sketch="F1", d=4)
    ai("new_assembly", name="Look")
    ai("insert_part", part="Base")
    ai("insert_part", part="Lid")
    ai("snap_faces", type="touch", move={"part": "I2", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})
    print("set_look I2:", ai("set_look", part="I2", color="#2E7D32", opacity=0.6))
    print("paint_faces I1:", ai("paint_faces", part="I1", faces=["F2:end"], color="#FF0000"))
    x0 = js(f"return {A}.inst('I2').matrix[12]")
    print("move_free:", ai("move_free", part="I2", motion="X", amount=12)[:70], "| x", x0, "->", js(f"return {A}.inst('I2').matrix[12]"))
    print("move_free, wrong motion:", ai("move_free", part="I2", motion="sideways up", amount=1)[:120])

    # the library: the model kept
    print("open_part:", ai("open_part", id="Duck body")[:120])
    wait(f"return window.__app.state.workspace === 'model' && !!{M}.result?.body")
    r = ai("save_to_library", name="Duck body", category="My parts / Toys")
    print("save_to_library:", r[:90])
    mine = js("return fetch('/api/library').then(r => r.json()).then(r => r.items.filter(i => i.source === 'user' && i.name === 'Duck body').map(i => i.id))")
    for mid in mine:
        js("return fetch('/api/library/' + arguments[0], { method: 'DELETE' })", mid)

    # report_problem
    r = ai("report_problem", title="Test report from e2e", what="Nothing is wrong — the test checks the report.", expected="a file", steps="report_problem {…}")
    print("report_problem:", r)
    path = os.path.join(ROOT, r.split("Reported: ")[1].split(" — ")[0]) if "Reported: " in r else None
    if path and os.path.exists(path):
        text = open(path, encoding="utf-8").read()
        print("  the report:", text.splitlines()[0], "|", [ln for ln in text.splitlines() if ln.startswith("- **Date")][0][:40])
        for ext in ("", ".a3d", ".recording.json"):  # (with the project / the recording attached to it)
            if os.path.exists(path[:-3] + ext if ext else path):
                os.remove(path[:-3] + ext if ext else path)
        try:
            os.rmdir(os.path.dirname(path))  # (the folder, when the test made it)
        except OSError:
            pass
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
