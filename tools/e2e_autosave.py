"""Autosave and recent projects, in headless Edge: a 3D model made -> kept on the server a few seconds later ("✓ Saved")
-> two quick saves of it at once (several POSTs together) all kept -> the page reloaded (as after a crash): the bar offers it -> Open: the same parts and steps back -> a change: kept under
the same project (not a new one) -> 🕘 Recent projects lists it -> forgotten with ✕.

Run the test server with its own data folder, so the user's recent projects stay clean:
  A3D_DATA=<a scratch folder> py server.py --port 5199 --no-browser
  PYTHONIOENCODING=utf-8 py tools/e2e_autosave.py http://127.0.0.1:5199 <out dir>
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
H = "window.__app.agentHandlers"


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def recent():
    with urllib.request.urlopen(f"{URL}/api/projects") as r:
        return json.loads(r.read())["projects"]


try:
    for p in recent():  # (a clean start)
        urllib.request.urlopen(urllib.request.Request(f"{URL}/api/projects/{p['id']}", method="DELETE"))
    d.get(URL)
    wait("return !!window.__app")
    time.sleep(1)
    print("an empty start offers nothing:", not d.find_elements(By.CSS_SELECTOR, ".restore-bar"))
    js(f"return {H}.new_model({{ name: 'Bracket' }})")
    js(f"return {H}.add_feature({{ type: 'sketch', plane: 'XY', shapes: [{{ rect: {{ x: 0, y: 0, w: 40, h: 20 }} }}] }})")
    js(f"return {H}.add_feature({{ type: 'extrude', sketch: 'F1', d: 6 }})")
    wait(f"return !!{M}.result?.body && !{M}.inflight")
    wait("return !document.getElementById('autosaveState').hidden", 20)
    print("status:", d.find_element(By.ID, "autosaveState").text)
    rec = recent()
    print("kept:", [(p["name"], [x["name"] for x in p["parts"]]) for p in rec])
    pid = js("return window.__app.autosave.id")
    # two quick autosaves (and more) of the same project at once: all answered 200 (WinError 32 used to make one 500)
    st = js("""const a = window.__app.autosave, p = a.hooks.project(), url = `/api/projects/${a.id}`;
      return Promise.all([1, 2, 3, 4, 5, 6].map(k => fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project: { ...p, project_name: 'Bracket' } }) }).then(r => r.status)));""")
    print("quick saves at once:", st, "| kept:", [p["name"] for p in recent()])

    d.refresh()  # as after a crash
    wait("return !!window.__app")
    bar = wait("return document.querySelector('.restore-bar')", 10)
    print("after a reload, the bar:", d.find_element(By.CSS_SELECTOR, ".restore-bar span").text)
    d.find_element(By.CSS_SELECTOR, ".restore-bar [data-a=open]").click()
    wait(f"return window.__app.state.workspace === 'model' && !!{M}.result?.body", 30)
    print("opened again:", js("return window.__app.project.parts.map(p => p.name)"), "| steps:", js(f"return {M}.part.features.map(f => f.type)"),
          "| the same project id:", js("return window.__app.autosave.id") == pid)
    js(f"return {H}.add_feature({{ type: 'fillet', edges: [], r: 1 }}).catch(() => null)")  # (a change; it may not build)
    js(f"{M}.part.color = '#ff8800'; {M}.history.commit()")
    time.sleep(4.5)
    rec = recent()
    print("a change: still one project:", len(rec), "| kept the change:", json.loads(urllib.request.urlopen(f"{URL}/api/projects/{pid}").read())["parts"][0]["model"].get("color"))

    # the bar is a strip under the top bar (it covers no button); ✕ closes it; making a part closes it too
    d.refresh()
    wait("return !!window.__app")
    wait("return document.querySelector('.restore-bar')", 10)
    print("the bar under the top bar:", js("return document.querySelector('.restore-bar').previousElementSibling.classList.contains('topbar')"),
          "| fixed:", js("return getComputedStyle(document.querySelector('.restore-bar')).position === 'fixed'"))
    d.find_element(By.CSS_SELECTOR, ".restore-bar [data-a=x]").click()
    print("✕ closes it:", not d.find_elements(By.CSS_SELECTOR, ".restore-bar"))
    d.refresh()
    wait("return !!window.__app")
    wait("return document.querySelector('.restore-bar')", 10)
    js("document.getElementById('sampleBtn').click()")
    wait("return !!window.__app.state.solution?.mesh", 60)
    time.sleep(0.5)
    print("gone once a part is open:", not d.find_elements(By.CSS_SELECTOR, ".restore-bar"))
    js("return window.__app.autosave.saveNow()")
    for p in recent():  # (only the Bracket kept, for the list below)
        if p["id"] != pid:
            urllib.request.urlopen(urllib.request.Request(f"{URL}/api/projects/{p['id']}", method="DELETE"))

    js("document.getElementById('recentBtn').click()")
    wait("return document.querySelectorAll('.aih-row').length >= 1")
    print("🕘 Recent projects:", [r.text.replace("\n", " | ")[:80] for r in d.find_elements(By.CSS_SELECTOR, ".aih-row")])
    d.save_screenshot(f"{OUT}/recent.png")
    js("window.confirm = () => true")
    d.find_element(By.CSS_SELECTOR, ".aih-row [data-del]").click()
    time.sleep(0.6)
    print("forgotten:", recent())
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
