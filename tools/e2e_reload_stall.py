"""After the page loads itself again (📄 New project, ✕ Close project, a reload), in headless Edge: the fresh page's
requests go out at once — /api/version and a project's picture answer within 2 s, no request of the page waits to be
sent (the old page, kept in the browser's back/forward cache, used to hold its AI poll and chat stream, and with the
fresh page's the browser's 6 connections per server were taken: ~20 s of waiting). Also with the ✨ AI chat open, and
the AI's tool calls still reach the page after each load. No console errors.

  PYTHONIOENCODING=utf-8 py tools/e2e_reload_stall.py http://127.0.0.1:5199 <out dir>
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
bad = []


def check(ok, what):
    print(("  ok  " if ok else "  FAIL") + " " + what)
    if not ok:
        bad.append(what)


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def ai(tool, timeout=30, **args):
    req = urllib.request.Request(f"{URL}/api/agent/call", data=json.dumps({"tool": tool, "args": args}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        res = json.loads(r.read())
    return ("ERROR " if res.get("isError") else "") + "".join(c.get("text", "") for c in res.get("content", []))


def open_chat():
    if js("return document.getElementById('aiDrawer').hidden && !document.getElementById('tab-ai').offsetParent"):
        d.find_element(By.ID, "aiBtn").click()
    wait("return !!document.getElementById('tab-ai').offsetParent", 10)


def reloaded(what, old, chat=False):
    """The fresh page after `what`: its own requests timed — none waits to be sent, the version and a picture at once."""
    wait(f"return !!window.__app && !!window.__app.autosave && window.__app.autosave.id !== '{old}' && document.readyState === 'complete'", 60)
    if chat:
        open_chat()
    thumb = js("return window.__e2eThumb")
    t = js("""const go = (u) => { const t = performance.now(); return fetch(u, { cache: 'no-store' }).then((r) => r.blob()).then(() => performance.now() - t); };
              return Promise.all([go('/api/version'), go(arguments[0] + '&n=' + Math.random())])""", thumb)
    check(t[0] < 2000 and t[1] < 2000, f"{what}: /api/version {t[0]:.0f} ms, a project's picture {t[1]:.0f} ms (under 2 s)")
    time.sleep(2.5)
    late = js("""return performance.getEntriesByType('resource').filter((e) => e.name.includes('/api/') && e.requestStart > 0
                   && e.requestStart - e.startTime > 1500).map((e) => [e.name.replace(location.origin, '').slice(0, 50), Math.round(e.requestStart - e.startTime)])""")
    check(not late, f"{what}: no request of the fresh page waited to be sent {late[:4]}")
    if chat:
        check(js("return !!document.querySelector('#tab-ai') && !!window.EventSource"), f"{what}: the chat is open")
    t0 = time.time()
    r = ai("gui_state")
    check(not r.startswith("ERROR") and time.time() - t0 < 5, f"{what}: the AI's call reaches the page ({time.time() - t0:.1f} s): {r[:60]!r}")


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.setItem('auto3d-lang', 'cs')")
    d.get(URL + "?new")
    wait("return !!window.__app && !!window.__app.autosave && document.readyState === 'complete'")
    time.sleep(1.5)  # (the page polls for the AI's calls)

    # a project with a picture: a block by the AI's tools
    ai("new_model", name="Blok")
    ai("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    r = ai("add_feature", type="extrude", sketch="F1", d=10)
    check(not r.startswith("ERROR"), f"a block 40 × 20 × 10: {r[:70]}")
    js("window.__app.state.projectName = 'Reload'")
    js("return window.__app.autosave.saveNow().then(() => window.__app.autosave.keepThumb({ force: true }))")
    pid = js("return window.__app.autosave.id")
    me = next((p for p in json.loads(urllib.request.urlopen(f"{URL}/api/projects").read())["projects"] if p["id"] == pid), {})
    check(bool(me.get("thumb")), f"the project has its picture ({me.get('thumb')})")
    thumb = f"/api/projects/{pid}/thumb?{me.get('thumb')}"
    d.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": f"window.__e2eThumb = {json.dumps(thumb)};"})
    js(f"window.__e2eThumb = {json.dumps(thumb)}")
    open_chat()
    time.sleep(1)

    # 📄 New project here, the chat open (its stream)
    old = js("return window.__app.autosave.id")
    d.find_element(By.ID, "newProjTopBtn").click()
    time.sleep(0.2)
    d.find_element(By.CSS_SELECTOR, "#newProjPop [data-np=here]").click()
    reloaded("📄 New project", old, chat=True)

    # the project again from 🕘, then ✕ Close project: the start screen shows its picture at once
    wait("return document.querySelectorAll('#startRecent .st-proj').length > 0", 15)
    d.find_element(By.CSS_SELECTOR, "#startRecent .st-proj").click()
    wait("return window.__app.project.parts.length === 1", 30)
    time.sleep(1.5)
    old = js("return window.__app.autosave.id")
    d.find_element(By.ID, "openBtn").click()
    time.sleep(0.2)
    js("document.getElementById('closeProjectBtn').click()")  # (the open chat may cover the menu)
    t0 = time.time()
    reloaded("✕ Close project", old)
    try:
        wait("const i = document.querySelector('#startRecent .st-proj img'); return !!i && i.complete && i.naturalWidth > 0", 5)
        pic = True
    except TimeoutError:
        pic = False
    check(pic, f"✕ Close project: the start screen's picture shows ({time.time() - t0:.1f} s after the click)")
    d.save_screenshot(f"{OUT}/reload_stall_closed.png")

    # a plain reload with the chat open, twice in a row
    for i in range(2):
        old = js("window.__app.autosave.__e2eOld = 1; return window.__app.autosave.id")
        js("location.reload()")
        wait("return !window.__app || !window.__app.autosave || !window.__app.autosave.__e2eOld", 30)
        reloaded(f"reload {i + 1}", "", chat=True)

    errs = [x["message"] for x in d.get_log("browser") if x["level"] == "SEVERE" and "favicon" not in x["message"]]
    check(not errs, f"no console errors {errs[:3]}")
finally:
    d.quit()
print("ALL OK" if not bad else f"FAILED: {bad}")
sys.exit(1 if bad else 0)
