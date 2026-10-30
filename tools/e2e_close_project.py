"""✕ Close project, in headless Edge, Czech: a 3D model made and the project renamed -> Otevřít ▾ › ✕ Zavřít projekt ->
the start screen with no part open, the closed project first in its 🕘 row with its picture (and first in the 🕘
dialog); one click there opens it again (its name, its part and steps); a failed save asks „Zavřít i tak" / „Zpět"
(Zpět: nothing closes); the project widget's ⋯ menu has it; an empty project closes too; the AI's close_project. No
console errors, no native dialogs.

  PYTHONIOENCODING=utf-8 py tools/e2e_close_project.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time
import urllib.request

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
bad = []
NAME = "Držák motoru"
# every page (also the fresh one after closing): a native dialog is counted, not shown
d.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": """
  for (const k of ['alert', 'confirm', 'prompt']) window[k] = () => { localStorage.setItem('e2e.native', (+localStorage.getItem('e2e.native') || 0) + 1); return true; };
"""})


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


def ai(tool, **args):
    req = urllib.request.Request(f"{URL}/api/agent/call", data=json.dumps({"tool": tool, "args": args}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        res = json.loads(r.read())
    return ("ERROR " if res.get("isError") else "") + "".join(c.get("text", "") for c in res.get("content", []))


def fresh_page():
    """The page loaded again (?new): a new autosave id, the start screen."""
    wait("return !!window.__app && !!window.__app.autosave && document.readyState === 'complete'")
    time.sleep(1.5)


def close_by_menu():
    old = js("return window.__app.autosave.id")
    d.find_element(By.ID, "openBtn").click()
    time.sleep(0.2)
    d.find_element(By.ID, "closeProjectBtn").click()
    wait(f"return !!window.__app && window.__app.autosave && window.__app.autosave.id !== '{old}'", 60)
    fresh_page()


def recent_names():
    return js("return [...document.querySelectorAll('#startRecent .st-proj b')].map(b => b.textContent)")


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.setItem('auto3d-lang', 'cs'); localStorage.removeItem('e2e.native')")
    d.get(URL + "?new")
    fresh_page()

    # an older project first, so the closed one is not first only by being the newest
    d.find_element(By.ID, "newModelBtn").click()
    wait("return window.__app.project.parts.length > 0")
    js("window.__app.state.projectName = 'Starší projekt'")
    js("return window.__app.autosave.saveNow()")
    time.sleep(0.5)
    d.find_element(By.ID, "newProjTopBtn").click()
    time.sleep(0.2)
    d.find_element(By.CSS_SELECTOR, "#newProjPop [data-np=here]").click()
    wait("return !!window.__app && window.__app.project && window.__app.project.parts.length === 0", 60)
    fresh_page()

    # a 3D model: a block (the AI's tools: the same steps as the clicks), the project renamed by its name
    time.sleep(1.5)  # (the page polls for the AI's calls)
    ai("new_model", name="Blok")
    ai("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    r = ai("add_feature", type="extrude", sketch="F1", d=10)
    check(not r.startswith("ERROR"), f"a block 40 × 20 × 10: {r[:80]}")
    el = d.find_element(By.ID, "fileName")
    el.click()
    time.sleep(0.2)
    el.send_keys(Keys.CONTROL, "a")
    el.send_keys(NAME, Keys.ENTER)
    time.sleep(0.3)
    check(js("return window.__app.state.projectName") == NAME, f"the project renamed: {js('return window.__app.state.projectName')!r}")
    pid = js("return window.__app.autosave.id")

    # the menus: Otevřít ▾ and the project widget's ⋯ and 📄's box offer it
    d.find_element(By.ID, "openBtn").click()
    time.sleep(0.2)
    txt = d.find_element(By.ID, "closeProjectBtn").text
    check("Zavřít projekt" in txt, f"Otevřít ▾ › {txt!r}")
    d.find_element(By.ID, "openBtn").click()
    d.find_element(By.ID, "newProjTopBtn").click()
    time.sleep(0.2)
    box = [b.text for b in d.find_elements(By.CSS_SELECTOR, "#newProjPop button")]
    check(any("Zavřít projekt" in b for b in box), f"📄's box: {box}")
    d.find_element(By.ID, "newProjTopBtn").click()
    js("window.__leftDock.dock('project')")
    time.sleep(0.4)
    js("document.querySelector('.lw-widget[data-w=project] .lw-menu').click()")
    time.sleep(0.3)
    labels = js("return [...document.querySelectorAll('.lw-pop button')].map(b => b.textContent.trim())")
    check(any("Zavřít projekt" in x for x in labels), f"the project widget's ⋯: {labels[:3]}")
    js("window.__leftDock.closeMenu()")

    # a failed save: asked „Zavřít i tak" / „Zpět" — Zpět keeps it open
    js("""window.__realFetch = window.fetch;
          window.fetch = (u, o) => (String(u).startsWith('/api/projects/') && o?.method === 'POST' ? Promise.resolve(new Response('{"error": "disk full"}', { status: 500 })) : window.__realFetch(u, o));""")
    js("window.__app.state.projectName = 'Držák motoru 2'")  # (a change not kept yet)
    d.find_element(By.ID, "openBtn").click()
    time.sleep(0.2)
    d.find_element(By.ID, "closeProjectBtn").click()
    wait("return !!document.querySelector('.choose.confirm')", 10)
    btns = [b.text for b in d.find_elements(By.CSS_SELECTOR, ".choose.confirm .choose-opts button")]
    say = js("return document.querySelector('.choose.confirm p')?.innerText || ''")
    check(btns[:2] == ["Zavřít i tak", "Zpět"] and "uložit" in say, f"not saved: {say[:70]!r} {btns}")
    d.save_screenshot(f"{OUT}/close_not_saved.png")
    d.find_elements(By.CSS_SELECTOR, ".choose.confirm .choose-opts button")[1].click()
    time.sleep(0.5)
    check(js("return window.__app.project.parts.length") == 1 and js("return window.__app.autosave.id") == pid, "Zpět: the project stays open")
    js(f"window.fetch = window.__realFetch; window.__app.state.projectName = '{NAME}'")

    # ✕ Zavřít projekt -> the start screen, nothing open, it first in 🕘 with its picture
    close_by_menu()
    check(js("return document.body.classList.contains('start-open')"), "the start screen shows")
    check(js("return window.__app.project.parts.length") == 0, "no part is open")
    check(not js("return document.getElementById('fileName').textContent.trim()"), "no project name in the top bar")
    check(not js("return window.__app.history?.canUndo?.() || window.__app.modeler?.history?.canUndo?.()"), "the undo history is empty")
    toast = js("return [...document.querySelectorAll('.toast')].map(t => t.textContent).join(' | ')")
    check(NAME in toast and "zavřen" in toast, f"the toast: {toast!r}")
    wait("return document.querySelectorAll('#startRecent .st-proj').length > 0", 15)
    names = recent_names()
    check(names[:1] == [NAME], f"first in 🕘 Recent projects: {names}")
    try:  # (in this headless run the fresh page's requests can queue ~20 s behind the old page's — 📄 New project too)
        pic = wait("const i = document.querySelector('#startRecent .st-proj img'); return !!i && i.complete && i.naturalWidth > 0", 45)
    except TimeoutError:
        pic = False
    check(pic is True, "with its picture")
    kept = json.loads(urllib.request.urlopen(f"{URL}/api/projects").read())["projects"]
    me = next((p for p in kept if p["id"] == pid), {})
    check(me.get("name") == NAME and me.get("thumb"), f"kept on the server with its picture: {me.get('name')!r} thumb {me.get('thumb')}")
    js("window.__app.autosave.showRecent()")
    wait("return document.querySelectorAll('.choose .aih-row').length > 0", 15)
    first = js("return document.querySelector('.aih-row .aih-prompt')?.textContent")
    check(first == NAME, f"first in the 🕘 dialog too: {first!r}")
    js("document.querySelector('.choose.aih .choose-x').click()")
    d.save_screenshot(f"{OUT}/close_start.png")

    # one click opens it again: its name, its part and steps
    d.find_element(By.CSS_SELECTOR, "#startRecent .st-proj").click()
    wait("return window.__app.project.parts.length === 1", 30)
    time.sleep(1)
    check(js("return window.__app.state.projectName") == NAME and js("return window.__app.autosave.id") == pid, "reopened: the same project")
    steps = js("return window.__app.modeler.part?.features?.length || window.__app.project.current?.data?.part?.features?.length || 0")
    check(steps >= 2, f"its block is back ({steps} steps)")
    check(not js("return document.body.classList.contains('start-open')"), "the start screen gone")

    # the AI: close_project — unchanged since it opened (its kept time older than another project saved meanwhile)
    time.sleep(1.5)
    old = next(p for p in json.loads(urllib.request.urlopen(f"{URL}/api/projects").read())["projects"] if p["id"] != pid)
    body = json.loads(urllib.request.urlopen(f"{URL}/api/projects/{old['id']}").read())
    body["project_name"] = "Novější projekt"
    urllib.request.urlopen(urllib.request.Request(f"{URL}/api/projects/e2e-newer-{int(time.time())}", data=json.dumps({"project": body}).encode(), headers={"Content-Type": "application/json"})).read()
    r = ai("close_project")
    check(not r.startswith("ERROR") and "closed" in r, f"close_project: {r[:110]}")
    wait(f"return !!window.__app && window.__app.autosave && window.__app.autosave.id !== '{pid}'", 60)
    fresh_page()
    check(js("return document.body.classList.contains('start-open') && window.__app.project.parts.length === 0"), "the AI closed it: the start screen")
    wait("return document.querySelectorAll('#startRecent .st-proj').length > 0", 15)
    names = recent_names()
    check(names[:1] == [NAME] and "Novější projekt" in names, f"first in 🕘 again, before one saved later: {names}")

    # an empty project closes too
    close_by_menu()
    check(js("return document.body.classList.contains('start-open') && window.__app.project.parts.length === 0"), "an empty project closed: the start screen")
    toast = js("return [...document.querySelectorAll('.toast')].map(t => t.textContent).join(' | ')")
    check("Projekt je zavřen" in toast, f"the toast: {toast!r}")
    time.sleep(1.5)
    r = ai("close_project")
    check("empty" in r, f"close_project on an empty one: {r[:90]}")
    wait("return !!window.__app && document.readyState === 'complete'", 60)
    fresh_page()

    check(not js("return +localStorage.getItem('e2e.native') || 0"), "no native dialogs")
    errs = [x["message"] for x in d.get_log("browser") if x["level"] == "SEVERE" and "favicon" not in x["message"] and "/api/projects/" not in x["message"]]
    check(not errs, f"no console errors {errs[:3]}")
finally:
    d.quit()
print("ALL OK" if not bad else f"FAILED: {bad}")
sys.exit(1 if bad else 0)
