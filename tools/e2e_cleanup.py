"""🧹 Clean up empty projects, in headless Edge: three empty projects with the app's names ("3D model 1", "Sestava 2",
"Project 3"), one empty but named by the user ("Bracket"), one with a step -> Open ▾ › 🕘 Recent projects ›
🧹 Clean up empty projects: it asks, naming them -> yes: the three are gone, the named one and the one with a step
stay -> again: nothing to clean up.

  PYTHONIOENCODING=utf-8 py tools/e2e_cleanup.py http://127.0.0.1:5199 <out dir>
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
opts.add_argument("--window-size=1500,900")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script


def keep(pid, project):
    req = urllib.request.Request(f"{URL}/api/projects/{pid}", data=json.dumps({"project": project}).encode(), headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=30).read()


def model(name, features=()):
    return {"project_name": name, "parts": [{"id": "P1", "kind": "model", "name": name, "model": {"features": list(features)}}]}


def names():
    return [r.find_element(By.CSS_SELECTOR, ".aih-prompt").text for r in d.find_elements(By.CSS_SELECTOR, ".aih-row")]


try:
    tag = str(int(time.time()))[-6:]
    keep(f"cleanup-a{tag}", model("3D model 1"))
    keep(f"cleanup-b{tag}", {"parts": [{"id": "P1", "kind": "assembly", "name": "Sestava 2", "assembly": {"instances": []}}]})
    keep(f"cleanup-c{tag}", model("Project 3"))
    keep(f"cleanup-d{tag}", model("Bracket"))
    keep(f"cleanup-e{tag}", model("3D model 4", [{"id": "F1", "type": "sketch", "plane": {"datum": "XY"}, "points": {}, "entities": []}]))
    d.get(URL)
    time.sleep(2)
    js("document.getElementById('recentBtn').click()")
    time.sleep(1)
    before = names()
    print("kept:", [n for n in before if n in ("3D model 1", "Sestava 2", "Project 3", "Bracket", "3D model 4")])
    js("window.__asked = []; window.confirm = (m) => { window.__asked.push(m); return true; }")
    d.find_element(By.CSS_SELECTOR, ".choose [data-clean]").click()
    time.sleep(1.5)
    asked = js("return window.__asked")
    print("it asks:", asked[0].split("\n")[0] if asked else None, "| naming:", [n for n in ("3D model 1", "Sestava 2", "Project 3", "Bracket") if asked and n in asked[0]])
    after = names()
    print("after:", [n for n in after if n in ("3D model 1", "Sestava 2", "Project 3", "Bracket", "3D model 4")])
    d.find_element(By.CSS_SELECTOR, ".choose [data-clean]").click()
    time.sleep(1)
    print("again:", js("return [...document.querySelectorAll('.toast')].map(t => t.textContent).slice(-1)"), "| asked again:", len(js("return window.__asked")) > 1)
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
