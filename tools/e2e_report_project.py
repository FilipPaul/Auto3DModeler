"""The AI's problem report carries the project, in headless Edge (tool calls through the server's /api/agent/call, as
the MCP server sends them): a small part (sketch + extrude), a second one and an assembly of both -> ⏺ a recording of a
few clicks, stopped -> get_screenshot {ui: true} (its id) -> report_problem with screenshots ["last", {shot: "view",
caption}]: the .md, <base>.a3d (the project), <base>.recording.json and <base>.shot-1/2.png (valid pictures of a
sensible size) next to it, the .md's Project / Recording / Screenshots lines and its image links; list_reports says
so -> a new empty project -> the .a3d opened through 📂 Open ›
File… (the page's file input): the same parts and the same steps -> no console errors. Exits 1 on a failed check.

Run it against a server whose reports go to a folder of its own (not the repository's RealSWReports):
  A3D_DATA=<scratch>/data A3D_REPORTS=<scratch>/reports py server.py --port 5199 --no-browser
  PYTHONIOENCODING=utf-8 py tools/e2e_report_project.py http://127.0.0.1:5199 <out dir>
"""
import json
import os
import re
import sys
import time
import urllib.request

import cv2
import numpy as np
from selenium import webdriver
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
P = "window.__app.project"
failed = []


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        try:
            v = js(script)
        except Exception:  # (the page reloading: 📄 New project)
            v = None
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def ai(tool, **args):
    req = urllib.request.Request(f"{URL}/api/agent/call", data=json.dumps({"tool": tool, "args": args}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        res = json.loads(r.read())
    return ("ERROR " if res.get("isError") else "") + "".join(c.get("text", "") for c in res.get("content", []))


def check(name, ok, got=""):
    print(f"  {'ok ' if ok else 'FAIL'} {name}{f': {got}' if got != '' else ''}")
    if not ok:
        failed.append(name)


def parts():
    """The project's parts: [(kind, name, the steps' types / the placed parts)]."""
    proj = js(f"return {P}.toJSON()")
    return [(p["kind"], p["name"], [f["type"] for f in p["model"]["features"]] if p["kind"] == "model"
             else sorted(i.get("part", "") for i in p["assembly"].get("instances", [])) if p["kind"] == "assembly" else []) for p in proj["parts"]]


try:
    d.get(URL)
    wait("return !!window.__app")
    time.sleep(1.5)
    ai("new_model", name="Plate")
    ai("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    ai("add_feature", type="extrude", sketch="F1", d=8)
    ai("new_model", name="Lid")
    ai("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 30, "h": 20}}])
    ai("add_feature", type="extrude", sketch="F1", d=4)
    ai("new_assembly", name="Box")
    ai("insert_part", part="Plate")
    ai("insert_part", part="Lid")
    before = parts()
    print("the project:", before)

    # ⏺ a few moves recorded, then stopped (the report takes a recording of the last 30 min)
    print("start_recording:", ai("start_recording", reason="e2e")[:40])
    for _ in range(3):
        d.find_element(By.ID, "openBtn").click()
        time.sleep(0.3)
    d.find_element(By.TAG_NAME, "body").click()
    print("stop_recording:", ai("stop_recording")[:40])

    # the AI looks at the window first, then attaches what it saw and the view as it is now
    shot = ai("get_screenshot", ui=True)
    sid = re.search(r"\(Screenshot (s\d+): report_problem", shot)
    check("get_screenshot gives an id", bool(sid), shot[-80:])
    r = ai("report_problem", title="Test report with the project", what="Nothing is wrong — the test checks the attachments.", steps="report_problem {…}",
           screenshots=["last", {"shot": "view", "caption": "the assembly Box, fitted"}])
    print("report_problem:", r)
    check("written with all", "with the project, the recording of moves and 2 screenshots" in r and "Not attached" not in r, r[-120:])
    md = r.split("Reported: ")[1].split(" — ")[0]
    md = md if os.path.isabs(md) else os.path.join(ROOT, md)
    check("reports outside the repository (A3D_REPORTS)", not os.path.abspath(md).startswith(os.path.join(ROOT, "RealSWReports")), md)
    gz, rec = md[:-3] + ".a3d", md[:-3] + ".recording.json"
    check(".md / .a3d / .recording.json exist", all(os.path.exists(p) for p in (md, gz, rec)))
    text = open(md, encoding="utf-8").read()
    proj_line = next((ln for ln in text.splitlines() if ln.startswith("- **Project:**")), "")
    rec_line = next((ln for ln in text.splitlines() if ln.startswith("- **Recording:**")), "")
    print("  ", proj_line, "\n  ", rec_line)
    check("the Project line", f"`{os.path.basename(gz)}` (open it in the app: 📂 Open ▾ › File…) — 3 part(s): Plate, Lid, Box" in proj_line)
    check("the Recording line", f"`{os.path.basename(rec)}`" in rec_line and "stopped" in rec_line)
    sys.path.insert(0, ROOT)
    from auto3d import package
    got = package.load(open(gz, "rb").read())
    saved = got["project"]
    check("the .a3d is a project with its picture", saved.get("app") == "Auto3DModeler" and saved.get("version") == 3 and got["versions"] is None
          and (got["thumbnail"] or b"")[1:4] == b"PNG", f"{os.path.getsize(gz)} B, {[p['name'] for p in saved['parts']]}")
    events = json.load(open(rec, encoding="utf-8"))["events"]
    check("the recording's events", events[0]["kind"] == "start" and events[-1]["kind"] == "stop" and any(e["kind"] == "click" for e in events),
          [e["kind"] for e in events])
    # the screenshots: the window as the AI saw it, the 3D view — real pictures, linked from the .md
    shots = sorted(f for f in os.listdir(os.path.dirname(md)) if f.startswith(os.path.basename(md)[:-3] + ".shot-"))
    print("  screenshots:", [(f, os.path.getsize(os.path.join(os.path.dirname(md), f))) for f in shots])
    check("two screenshots next to it", len(shots) == 2, shots)
    for i, f in enumerate(shots, 1):
        raw = open(os.path.join(os.path.dirname(md), f), "rb").read()
        img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        kind = "png" if raw[:8] == b"\x89PNG\r\n\x1a\n" else "webp" if raw[8:12] == b"WEBP" else "?"
        check(f"shot {i} is a picture of a sensible size", img is not None and kind != "?" and 400 <= max(img.shape[:2]) <= 1600
              and 5000 < len(raw) <= 1 << 20, (kind, None if img is None else img.shape[:2], len(raw)))
        check(f"shot {i} has some contents", img is not None and float(img.std()) > 5, None if img is None else round(float(img.std()), 1))
    check("the .md links them", f"![the AI's screenshot {sid.group(1) if sid else '?'}]({shots[0] if shots else '?'})" in text
          and f"![the assembly Box, fitted]({shots[-1] if shots else '?'})" in text and "- **Screenshots:** 2 (below)" in text,
          [ln for ln in text.splitlines() if ".shot-" in ln])
    row = json.loads(ai("list_reports", search="report with the project"))[0]
    check("list_reports says what is attached", row.get("project") == os.path.basename(gz) and row.get("recording") == os.path.basename(rec)
          and row.get("screenshots") == shots, row)

    # a new, empty project (the page starts again); then the attached project opened as the user would: 📂 Open › File…
    js("document.getElementById('newProjectBtn').click()")
    wait(f"return !!window.__app && !{P}.toJSON().parts.some(p => p.name === 'Lid')", 30)
    time.sleep(1.5)
    print("a new project:", parts())
    d.find_element(By.ID, "anyInput").send_keys(os.path.abspath(gz))
    wait(f"return {P}.toJSON().parts.some(p => p.name === 'Lid')", 60)
    time.sleep(1.5)
    after = parts()
    print("opened again:", after)
    check("the same parts and steps", after == before)
    d.save_screenshot(f"{OUT}/report_project_opened.png")
finally:
    errors = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errors)
    if errors:
        failed.append("console errors")
    d.quit()
print("FAILED:" if failed else "ALL OK", failed if failed else "")
sys.exit(1 if failed else 0)
