"""The AI asks with options (ask_user), in headless Edge through /api/agent/call: two questions -> the chat opens with
two cards of buttons, the AI's recommended option first and marked ★ -> one clicked: nothing sent yet (one more open)
-> the second clicked: one message with both answers ("<question> → <option>") -> "✎ Other…": the answers so far and
the question go into the box to type -> a call without options is refused.
The message is caught in the page (no Claude needed).

  PYTHONIOENCODING=utf-8 py tools/e2e_ai_ask.py http://127.0.0.1:5199 <out dir>
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


def ai(tool, **args):
    req = urllib.request.Request(f"{URL}/api/agent/call", data=json.dumps({"tool": tool, "args": args}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        res = json.loads(r.read())
    return ("ERROR " if res.get("isError") else "") + "".join(c.get("text", "") for c in res.get("content", []))


def cards():
    return [[o.text.replace("\n", " | ") for o in c.find_elements(By.CSS_SELECTOR, ".ai-opt")] for c in d.find_elements(By.CSS_SELECTOR, ".ai-msg.ask")]


try:
    d.get(URL)
    time.sleep(2)
    js("window.__sent = []; window.__chat.send = function () { window.__sent.push(this.$('textarea').value); this.$('textarea').value = ''; }")
    print("ask 1:", ai("ask_user", question="What is the part for?", recommended=1, options=[
        {"label": "Automation / machine", "description": "made to be manufactured, standard parts"},
        {"label": "Functional 3D print", "description": "a sensor bracket that carries a little load — fits what you asked"},
        {"label": "Graphic / decorative"}])[:80])
    ai("ask_user", question="Easy to edit by a person?", options=["Yes — simple sketches", "Any way that reaches the goal"])
    time.sleep(0.5)
    print("chat in sight:", js("return document.getElementById('tab-ai').offsetParent !== null"))
    print("cards:", cards())
    print("recommended first and marked:", d.find_elements(By.CSS_SELECTOR, ".ai-msg.ask .ai-opt")[0].get_attribute("class"))
    d.save_screenshot(f"{OUT}/ask.png")
    d.find_elements(By.CSS_SELECTOR, ".ai-msg.ask")[0].find_elements(By.CSS_SELECTOR, ".ai-opt")[0].click()
    time.sleep(0.4)
    print("one answered: sent", js("return window.__sent"))
    d.find_elements(By.CSS_SELECTOR, ".ai-msg.ask")[1].find_elements(By.CSS_SELECTOR, ".ai-opt")[0].click()
    time.sleep(0.6)
    print("both answered: sent", js("return window.__sent"))
    print("the others greyed:", len(d.find_elements(By.CSS_SELECTOR, ".ai-msg.ask.done .ai-opt:not(.on)")))

    ai("ask_user", question="Which material?", options=[{"label": "PETG"}, {"label": "PLA"}])
    time.sleep(0.4)
    d.find_elements(By.CSS_SELECTOR, ".ai-msg.ask")[2].find_element(By.CSS_SELECTOR, ".ai-opt.other").click()
    time.sleep(0.3)
    print("✎ Other…: the box", repr(js("return document.querySelector('#tab-ai textarea').value")), "| sent", len(js("return window.__sent")))
    print("no options:", ai("ask_user", question="Size?", options=[])[:70])
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
