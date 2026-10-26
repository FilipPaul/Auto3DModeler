"""🕘 AI history, in headless Edge: two AI turns (tool calls sent through the server's /api/agent/call, as the MCP server
does) -> after each one the whole project is kept on the server with the message that made it -> a turn whose past is
only replayed (no tools ran here) keeps nothing -> 🕘 History lists them, newest first -> the part renamed by hand -> Load
the first one: the plate without its hole is back, and the renamed project is kept too ("before loading"). The states the test made are
deleted at the end.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_ai_history.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time
import urllib.request

from selenium import webdriver
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def http(method, path, body=None):
    req = urllib.request.Request(f"{URL}{path}", method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def ai(tool, **args):
    return http("POST", "/api/agent/call", {"tool": tool, "args": args})


def states():
    return http("GET", "/api/history")["states"]


before = {s["id"] for s in states()}
try:
    d.get(URL)
    wait("return !!window.__app")
    time.sleep(1.5)  # the bridge polls

    js("window.__chat.handle({ type: 'user', seq: 1e9, text: 'Make a 60 × 40 × 5 plate' })")
    ai("new_model", name="Plate")
    ai("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    ai("add_feature", type="extrude", sketch="F1", d=5)
    wait(f"return !!{M}.result?.body && !{M}.inflight")
    js("window.__chat.handle({ type: 'done' })")
    time.sleep(1)
    new = [s for s in states() if s["id"] not in before]
    print("after the 1st turn:", [(s["prompt"], s["tools"], [p["name"] for p in s["parts"]]) for s in new])

    js("window.__chat.handle({ type: 'user', text: 'Add a Ø6 hole in the middle' })")
    ai("add_feature", type="hole", face="F2:end", points=[[30, 20]], d=6)
    wait(f"return {M}.part.features.length === 3 && !{M}.inflight")
    js("window.__chat.handle({ type: 'done' })")
    time.sleep(1)
    js("window.__chat.handle({ type: 'done' })")  # a replayed end of a turn: no tools ran -> nothing kept
    time.sleep(1)
    new = [s for s in states() if s["id"] not in before]
    print("after the 2nd turn (+ a replayed one):", [(s["prompt"], s["tools"]) for s in new])

    js("const p = window.__app.project; p.rename(p.active, 'Plate (by hand)')")  # a change of the user's, after the AI
    js("document.querySelector('#tab-ai .ai-hist').click()")
    wait("return document.querySelectorAll('.aih-row').length >= 2")
    print("🕘 History rows:", [r.text.replace("\n", " | ")[:90] for r in d.find_elements(By.CSS_SELECTOR, ".aih-row")][:2])
    d.save_screenshot(f"{OUT}/ai_history.png")
    first = new[-1]["id"]
    d.find_element(By.CSS_SELECTOR, f".aih-row[data-id='{first}'] [data-load]").click()
    wait("return !document.querySelector('.aih')")
    wait(f"return !!{M}.result?.body && !{M}.inflight")
    print("loaded the 1st state:", js(f"return {M}.part.features.map(f => f.type)"), "|",
          js("return [...document.querySelectorAll('.toast')].map(t => t.textContent).slice(-1)[0]"))
    new = [s for s in states() if s["id"] not in before]
    print("kept before loading:", [(s["kind"], [p["name"] for p in s["parts"]]) for s in new if s["kind"] == "before-load"])
finally:
    for s in states():
        if s["id"] not in before:
            http("DELETE", f"/api/history/{s['id']}")
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
