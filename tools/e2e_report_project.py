"""The AI's problem report carries the project, in headless Edge (tool calls through the server's /api/agent/call, as
the MCP server sends them): a small part (sketch + extrude), a second one and an assembly of both -> ⏺ a recording of a
few clicks, stopped -> report_problem: the .md, <base>.a3d.json.gz (the project) and <base>.recording.json next to
it, the .md's Project / Recording lines; list_reports says so -> a new empty project -> the .gz opened through 📂 Open ›
File… (the page's file input): the same parts and the same steps -> no console errors. Exits 1 on a failed check.

Run it against a server whose reports go to a folder of its own (not the repository's RealSWReports):
  A3D_DATA=<scratch>/data A3D_REPORTS=<scratch>/reports py server.py --port 5199 --no-browser
  PYTHONIOENCODING=utf-8 py tools/e2e_report_project.py http://127.0.0.1:5199 <out dir>
"""
import gzip
import json
import os
import sys
import time
import urllib.request

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

    r = ai("report_problem", title="Test report with the project", what="Nothing is wrong — the test checks the attachments.", steps="report_problem {…}")
    print("report_problem:", r)
    check("written with both", "with the project and the recording of moves" in r, r[-80:])
    md = r.split("Reported: ")[1].split(" — ")[0]
    md = md if os.path.isabs(md) else os.path.join(ROOT, md)
    check("reports outside the repository (A3D_REPORTS)", not os.path.abspath(md).startswith(os.path.join(ROOT, "RealSWReports")), md)
    gz, rec = md[:-3] + ".a3d.json.gz", md[:-3] + ".recording.json"
    check(".md / .a3d.json.gz / .recording.json exist", all(os.path.exists(p) for p in (md, gz, rec)))
    text = open(md, encoding="utf-8").read()
    proj_line = next((ln for ln in text.splitlines() if ln.startswith("- **Project:**")), "")
    rec_line = next((ln for ln in text.splitlines() if ln.startswith("- **Recording:**")), "")
    print("  ", proj_line, "\n  ", rec_line)
    check("the Project line", f"`{os.path.basename(gz)}` (open it in the app: 📂 Open ▾ › File…) — 3 part(s): Plate, Lid, Box" in proj_line)
    check("the Recording line", f"`{os.path.basename(rec)}`" in rec_line and "stopped" in rec_line)
    saved = json.loads(gzip.decompress(open(gz, "rb").read()))
    check("the .gz is a project", saved.get("app") == "Auto3DModeler" and saved.get("version") == 3 and "versions" not in saved,
          f"{os.path.getsize(gz)} B, {[p['name'] for p in saved['parts']]}")
    events = json.load(open(rec, encoding="utf-8"))["events"]
    check("the recording's events", events[0]["kind"] == "start" and events[-1]["kind"] == "stop" and any(e["kind"] == "click" for e in events),
          [e["kind"] for e in events])
    row = json.loads(ai("list_reports", search="report with the project"))[0]
    check("list_reports says what is attached", row.get("project") == os.path.basename(gz) and row.get("recording") == os.path.basename(rec), row)

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
