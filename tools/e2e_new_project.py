"""📄 New project, in headless Edge (Czech): a project with a 3D model open -> Otevřít ▾ › 📄 Nový projekt -> the start
screen with an empty project (a new autosave id, the window's title back to the app's), the toast says where the
previous one is; the previous project is in 🕘 Recent projects and ↶ in the toast opens it again (its parts and steps)
-> Ctrl+Alt+N does the same; the project widget's ⋯ menu has it too; an empty project: nothing happens but a note ->
⧉ New project in a new window: a second window with the start screen, the first one as it was. The AI with two
browser windows (two projects): each window's chat (the MCP server with --client <the window's id>, as the chat starts
it) reads and changes its own window's project only (a reload and 📄 New project keep the window's chat, a new window has
its own); a call for no window goes to the window in use; the second window
closed: its chat's call fails at once with "… was closed", the first one's still works.

  A3D_DATA=<a scratch folder> py server.py --port 5199 --no-browser
  PYTHONIOENCODING=utf-8 py tools/e2e_new_project.py http://127.0.0.1:5199 <out dir>
"""
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

URL, OUT = sys.argv[1], sys.argv[2]
ROOT = Path(__file__).resolve().parent.parent
Path(OUT).mkdir(parents=True, exist_ok=True)
H = "window.__app.agentHandlers"
M = "window.__app.modeler"
FAILS = []


def browser():
    opts = webdriver.EdgeOptions()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1400,900")
    return webdriver.Edge(options=opts)


d = browser()
d2 = None
js = d.execute_script


def check(name, ok):
    print(("  ok   " if ok else "  FAIL ") + name)
    if not ok:
        FAILS.append(name)


def wait(script, t=40, drv=None):
    end = time.time() + t
    while time.time() < end:
        v = (drv or d).execute_script(script)
        if v:
            return v
        time.sleep(0.15)
    raise TimeoutError(script)


def recent():
    with urllib.request.urlopen(f"{URL}/api/projects") as r:
        return json.loads(r.read())["projects"]


def ready(drv=None):
    wait("return !!window.__app && !!window.__app.autosave", drv=drv)
    time.sleep(0.8)


def make_block(name, drv=None):
    x = (drv or d).execute_script
    x(f"return {H}.new_model({{ name: arguments[0] }})", name)
    x(f"return {H}.add_feature({{ type: 'sketch', plane: 'XY', shapes: [{{ rect: {{ x: 0, y: 0, w: 40, h: 20 }} }}] }})")
    x(f"return {H}.add_feature({{ type: 'extrude', sketch: 'F1', d: 6 }})")
    wait(f"return !!{M}.result?.body && !{M}.inflight", drv=drv)


def toast_text():
    return js("return [...document.querySelectorAll('#toasts .toast')].map(t => t.textContent).join(' | ')")


def open_menu_item(btn_id):
    d.find_element(By.ID, "openBtn").click()
    time.sleep(0.2)
    d.find_element(By.ID, btn_id).click()


try:
    for p in recent():  # (a clean start)
        urllib.request.urlopen(urllib.request.Request(f"{URL}/api/projects/{p['id']}", method="DELETE"))
    d.get(URL)
    js("localStorage.setItem('auto3d-lang', 'cs')")
    d.get(URL)
    ready()
    make_block("Konzola")
    old_id = js("return window.__app.autosave.id")
    chat_id = js("return window.__app.client")
    check(f"the window's title names the project: {d.title!r}", "Konzola" in d.title)
    d.find_element(By.ID, "openBtn").click()
    time.sleep(0.2)
    item = d.find_element(By.ID, "newProjectBtn")
    check(f"Otevřít ▾ has 📄 Nový projekt: {item.text!r}", "Nový projekt" in item.text and "Ctrl+Alt+N" in item.text)
    check("… and ⧉ Nový projekt v novém okně", "Nový projekt v novém okně" in d.find_element(By.ID, "newProjectWinBtn").text)
    d.save_screenshot(str(Path(OUT) / "np_menu.png"))
    item.click()
    wait("return !!window.__app && !!window.__app.autosave && document.readyState === 'complete'")
    ready()
    check("the start screen with an empty project", js("return document.body.classList.contains('start-open') && window.__app.project.parts.length === 0"))
    new_id = js("return window.__app.autosave.id")
    check("a new autosave id", new_id != old_id)
    check("this window's AI chat goes on (the same chat id)", js("return window.__app.client") == chat_id)
    check(f"the window's title is the app's again: {d.title!r}", "Konzola" not in d.title)
    check("no ?new left in the address", "new" not in js("return location.search"))
    check("no 'continue where you left off' bar (a new project was asked for)", not d.find_elements(By.CSS_SELECTOR, ".restore-bar"))
    tt = toast_text()
    check(f"the toast says where the previous one is: {tt!r}", "Předchozí projekt „Konzola“ je uložen" in tt and "Nedávné projekty" in tt)
    rec = recent()
    check(f"the previous project is in Recent: {[p['name'] for p in rec]}", any(p["id"] == old_id and p["name"] == "Konzola" for p in rec))
    d.save_screenshot(str(Path(OUT) / "np_after.png"))
    # ↶ in the toast: the previous project again
    d.find_element(By.CSS_SELECTOR, "#toasts .toast button").click()
    wait(f"return window.__app.project.parts.length === 1 && !!{M}.result?.body", 30)
    check("↶ Otevřít znovu: the previous project, its part and steps", js(f"return window.__app.project.parts[0].name === 'Konzola' && {M}.part.features.length === 2"))
    check("… under its own id (not a copy)", js("return window.__app.autosave.id") == old_id)

    # Ctrl+Alt+N
    ActionChains(d).key_down(Keys.CONTROL).key_down(Keys.ALT).send_keys("n").key_up(Keys.ALT).key_up(Keys.CONTROL).perform()
    wait("return document.readyState === 'complete' && !!window.__app && window.__app.project.parts.length === 0 && document.body.classList.contains('start-open')", 30)
    ready()
    check("Ctrl+Alt+N: an empty project again", js("return window.__app.autosave.id") not in (old_id, new_id))
    # an empty project: a note, nothing else
    before = js("return window.__app.autosave.id")
    open_menu_item("newProjectBtn")
    time.sleep(0.8)
    check(f"an empty project: only a note ({toast_text()!r})", js("return window.__app.autosave.id") == before and "už je prázdný" in toast_text())

    # the project widget's ⋯ menu
    make_block("Deska")
    js("window.__leftDock.dock('project')")
    time.sleep(0.4)
    js("document.querySelector('.lw-widget[data-w=project] .lw-menu').click()")
    time.sleep(0.3)
    labels = js("return [...document.querySelectorAll('.lw-pop button')].map(b => b.textContent.trim())")
    check(f"the project widget's ⋯ menu: {labels[:3]}", any("Nový projekt" == x.replace("📄", "").strip() for x in labels) and any("v novém okně" in x for x in labels))
    d.save_screenshot(str(Path(OUT) / "np_widget_menu.png"))
    js("window.__leftDock.closeMenu()")
    # the suggestions widget docked, nothing selected: its row
    js("window.__leftDock.dock('suggest')")
    time.sleep(0.4)
    row = js("const b = document.querySelector('.lw-widget[data-w=suggest] .lw-sg-new'); return b && b.getClientRects().length ? b.textContent.trim() : ''")
    check(f"the docked suggestions with nothing selected: a 📄 row ({row!r})", "Nový projekt" in row)

    # ⧉ in a new window: this one stays, the other starts empty
    here = js("return window.__app.autosave.id")
    handles = d.window_handles
    open_menu_item("newProjectWinBtn")
    end = time.time() + 15
    while len(d.window_handles) == len(handles) and time.time() < end:
        time.sleep(0.2)
    new = [h for h in d.window_handles if h not in handles]
    check("⧉ a second window opened", len(new) == 1)
    if new:
        d.switch_to.window(new[0])
        ready()
        check("… with the start screen and an empty project", js("return document.body.classList.contains('start-open') && !window.__app.project.parts.length"))
        check("… a project of its own", js("return window.__app.autosave.id") != here)
        check("… and a chat of its own", js("return window.__app.client") != chat_id)
        d.close()
        d.switch_to.window(handles[0])
    check("the first window kept its project", js("return window.__app.autosave.id") == here and js("return window.__app.project.parts.length") == 1)

    # the AI with two windows: each window's chat acts in its own window (the MCP server as its chat starts it:
    # --client <the window's id>), never in the other; a window closed -> its chat's calls fail, saying so
    d2 = browser()
    d2.get(URL)
    ready(d2)
    make_block("Beta", drv=d2)
    ca, cb = js("return window.__app.client"), d2.execute_script("return window.__app.client")
    check(f"each window has its own chat id ({ca[:8]}…, {cb[:8]}…)", bool(ca and cb and ca != cb))
    mcps = {}
    for name, cid in (("A", ca), ("B", cb)):
        mcps[name] = subprocess.Popen([sys.executable, str(ROOT / "auto3d" / "mcp_server.py"), "--url", URL, "--client", cid],
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    ids = iter(range(1, 1000))

    def tool(who, tname, **args):
        p = mcps[who]
        p.stdin.write((json.dumps({"jsonrpc": "2.0", "id": next(ids), "method": "tools/call", "params": {"name": tname, "arguments": args}}) + "\n").encode())
        p.stdin.flush()
        r = json.loads(p.stdout.readline().decode())["result"]
        return r["content"][0]["text"], bool(r.get("isError"))

    ta, _ = tool("A", "list_parts")
    tb, _ = tool("B", "list_parts")
    check(f"A's chat sees A's project: {ta[:80]!r}", "Deska" in ta and "Beta" not in ta)
    check(f"B's chat sees B's project: {tb[:80]!r}", "Beta" in tb and "Deska" not in tb)
    tool("B", "new_model", name="Gama")
    wait("return window.__app.project.parts.some(p => p.name === 'Gama')", drv=d2)
    time.sleep(0.5)
    check("B's chat made a part in B", d2.execute_script("return window.__app.project.parts.map(p => p.name)") == ["Beta", "Gama"])
    check("… and nothing in A", js("return window.__app.project.parts.map(p => p.name)") == ["Deska"])
    # without a window (an MCP client of its own, as e2e_agent): the window in use, as before
    with urllib.request.urlopen(urllib.request.Request(f"{URL}/api/agent/call", data=json.dumps({"tool": "list_parts", "args": {}}).encode(),
                                                       headers={"Content-Type": "application/json"})) as r:
        anyw = json.loads(r.read())["content"][0]["text"]
    check(f"a call for no window goes to a window in use: {anyw[:60]!r}", "Deska" in anyw or "Beta" in anyw)
    d2.get("about:blank")  # (the page goes as when its window is closed: its goodbye)
    d2.quit()
    d2 = None
    time.sleep(12)  # (past the grace a reload has to come back in)
    t0 = time.time()
    tb, err = tool("B", "list_parts")
    check(f"B closed: its chat's call fails, saying so ({tb[:90]!r}, {time.time() - t0:.1f} s)", err and "was closed" in tb)
    ta, err = tool("A", "list_parts")
    check("A's chat still works in A", not err and "Deska" in ta)
    d.refresh()
    ready()
    check("a reload keeps the window's chat", js("return window.__app.client") == chat_id)
    for p in mcps.values():
        p.stdin.close()
        p.wait(10)
finally:
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE" and "favicon" not in e["message"]]
    if errs:
        print("browser errors:", errs[:5])
    d.quit()
    if d2:
        d2.quit()

print("FAILS:", FAILS if FAILS else "none")
sys.exit(1 if FAILS else 0)
