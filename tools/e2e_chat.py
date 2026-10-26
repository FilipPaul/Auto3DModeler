"""The real thing: a message in the app's ✨ AI tab -> Claude Code (the installed one, its own sign-in) ->
the app's MCP tools -> the part. Uses the Claude account Claude Code is signed in with.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_chat.py http://127.0.0.1:5199 <out dir> "message"
"""
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.by import By

URL, OUT, MESSAGE = sys.argv[1], sys.argv[2], sys.argv[3]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
try:
    d.get(URL)
    time.sleep(2)
    js("document.querySelector('.tab[data-tab=ai]').click()")
    time.sleep(0.5)
    print("status:", js("return document.querySelector('.ai-status').textContent"))
    ta = d.find_element(By.CSS_SELECTOR, ".ai-form textarea")
    ta.send_keys(MESSAGE)
    js("document.querySelector('.ai-form button[type=submit]').click()")
    t0 = time.time()
    last = ""
    while time.time() - t0 < 420:
        time.sleep(2)
        st = js("return document.querySelector('.ai-status').textContent")
        if st != last:
            print(f"  {time.time() - t0:5.0f}s  {st}")
            last = st
        busy = js("return document.querySelector('.ai-panel').classList.contains('busy')")
        if not busy and time.time() - t0 > 5:
            break
    print(f"finished after {time.time() - t0:.0f}s")
    for kind, text in js("return [...document.querySelectorAll('.ai-msg')].map(m => [m.className.replace('ai-msg ', ''), m.innerText])"):
        print(f"[{kind}] {text[:400]}")
    print("part:", js("const s = window.__app.state; return s.model ? [s.model.source, s.solution && +s.solution.volume.toFixed(3), (s.model.extras || []).map(o => o.name + ':' + o.op)] : null"))
    print("3D model:", js("const m = window.__app.modeler; return document.body.classList.contains('ws-model') ? [m.part.features.map(f => f.type + ' ' + m.whatText(f)), m.result?.body && [m.result.body.bbox.map(v => +v.toFixed(3)), +m.result.body.volume.toFixed(3)]] : null"))
    d.save_screenshot(f"{OUT}/chat.png")
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
