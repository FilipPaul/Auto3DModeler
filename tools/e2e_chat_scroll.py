"""The AI chat scrolls while Claude works, in headless Edge (in a 3D model, the chat in its
drawer): a long conversation (events as the server sends them) ->
Claude busy: the panel keeps its place and size, the log scrolls -> scrolled up, new text arriving leaves it there ->
back at the bottom, new text keeps it at the bottom.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_chat_scroll.py http://127.0.0.1:5199 <out dir>
"""
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.actions.wheel_input import ScrollOrigin
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
C = "window.__chat"


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def panel():
    return js(f"""const r = {C}.root, b = r.getBoundingClientRect(), s = getComputedStyle(r);
      return [s.position, Math.round(b.width), Math.round(b.height)]""")


def log():
    return js(f"const l = {C}.log; return [Math.round(l.scrollTop), l.scrollHeight - l.clientHeight]")


try:
    d.get(URL)
    wait("return !!window.__app")
    js("return window.__app.agentHandlers.new_model({ name: 'Plate' })")
    wait("return window.__app.state.workspace === 'model'")
    js("document.getElementById('aiBtn').click()")  # the chat in its drawer at the right
    time.sleep(0.4)
    print("panel at rest:", panel())
    for i in range(12):
        js(f"{C}.handle({{ type: 'user', text: 'Question {i}' }}); {C}.handle({{ type: 'text', text: 'Answer {i}\\n\\n' + 'A long line of the answer. '.repeat(30) }}); {C}.handle({{ type: 'done' }})")
    js(f"{C}.handle({{ type: 'user', text: 'Make a plate' }})")  # Claude is working now
    time.sleep(0.3)
    print("busy:", js(f"return {C}.busy"), "| panel while busy:", panel(), "| log [top, max]:", log())
    lg = d.find_element(By.CSS_SELECTOR, "#tab-ai .ai-log")
    ActionChains(d).scroll_from_origin(ScrollOrigin.from_element(lg), 0, -1500).perform()  # the mouse wheel, up
    time.sleep(0.4)
    up = log()
    print("wheel up while busy:", up)
    for _ in range(20):
        js(f"{C}.handle({{ type: 'delta', text: 'more words of the reply ' }})")
    js(f"{C}.handle({{ type: 'tool', name: 'add_feature', input: {{ type: 'extrude' }} }})")
    time.sleep(0.3)
    print("new text arrives — it stays where it was read:", log()[0] == up[0], log())
    ActionChains(d).scroll_from_origin(ScrollOrigin.from_element(lg), 0, 100000).perform()
    time.sleep(0.4)
    for _ in range(20):
        js(f"{C}.handle({{ type: 'delta', text: 'and more words ' }})")
    t, m = log()
    print("at the bottom — it follows:", abs(t - m) <= 2, [t, m])
    d.save_screenshot(f"{OUT}/chat_scroll.png")
    js(f"{C}.handle({{ type: 'done' }})")
    print("done — panel:", panel())
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
