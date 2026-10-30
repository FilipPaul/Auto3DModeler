"""Several parts in one project (tabs in the top bar): every opened file becomes a part, switching keeps
each part's edits and undo history, rename by double-click, Save project (version 3) -> reload -> Open
project, an old version-2 file still opens, closing a part — in headless Edge with real clicks.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_project.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from auto3d import package  # noqa: E402  (the saved .a3d read back)

URL, OUT = sys.argv[1], sys.argv[2]
PIC = str(Path(__file__).resolve().parent.parent / "pernicek.png")
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def tabs():
    return js("return [...document.querySelectorAll('#partTabs .part-tab')].map(t => (t.classList.contains('on') ? '*' : '') + t.querySelector('.pt-name').textContent)")


def settled():
    wait("return document.getElementById('busy').hidden && window.__app.state.solution")
    time.sleep(0.8)


def tab(i):
    return d.find_elements(By.CSS_SELECTOR, "#partTabs .part-tab")[i]


STUB = """window.__saved = null; window.showSaveFilePicker = async (o) => ({ name: o.suggestedName,
  createWritable: async () => ({ write: async (b) => { const u = new Uint8Array(await b.arrayBuffer()); let s = ''; for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode(...u.subarray(i, i + 0x8000)); window.__saved = btoa(s); }, close: async () => {} }) });
  window.confirm = () => true;"""

try:
    d.get(URL)
    wait("return !!window.__app")
    print("empty app — tabs hidden:", js("return document.getElementById('partTabs').hidden"))

    # part 1: the sample drawing, with an added hole and a changed value
    js("document.getElementById('sampleBtn').click()")
    wait("return window.__app.state.model?.source === 'initial draft.pdf'")
    settled()
    js("return window.__app.agentHandlers.add_object({kind: 'cylinder', op: 'subtract', x: 30, y: 5.5, w: 2, h: 2, z0: 0, z1: 1})")
    settled()
    vol1 = js("return window.__app.state.solution.volume")
    print("tabs after the sample:", tabs(), "| volume with hole", vol1)

    # part 2: a picture -> cookie cutter, in its own tab
    d.find_element(By.ID, "imgInput").send_keys(PIC)
    wait("return document.querySelector('.wizard .wz-cand')")
    time.sleep(1)
    d.find_element(By.CSS_SELECTOR, ".wizard .wz-use").click()
    wait("return window.__app.state.model?.kind === 'outline'")
    settled()
    print("tabs after the picture:", tabs())

    # back to part 1 with a real click: its hole, volume and undo history are back
    tab(0).click()
    wait("return window.__app.state.model?.source === 'initial draft.pdf'")
    settled()
    print("part 1 again: volume", js("return window.__app.state.solution.volume"), "(was", vol1, ") | extras",
          js("return (window.__app.state.model.extras || []).length"), "| undo enabled", js("return !document.getElementById('undoBtn').disabled"))
    d.find_element(By.ID, "undoBtn").click()
    settled()
    print("undo in part 1 removes the hole:", js("return (window.__app.state.model.extras || []).length"), "| tabs", tabs())
    d.find_element(By.ID, "redoBtn").click()
    settled()

    # rename part 2 by double-click
    tab(1).click()
    wait("return window.__app.state.model?.kind === 'outline'")
    settled()
    ActionChains(d).double_click(tab(1).find_element(By.CSS_SELECTOR, ".pt-name")).perform()
    time.sleep(0.2)
    ActionChains(d).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).send_keys("Cookie cutter").send_keys(Keys.ENTER).perform()
    time.sleep(0.3)
    print("after rename:", tabs())
    d.save_screenshot(f"{OUT}/p1_two_parts.png")

    # the ＋ menu offers the ways to add a part
    d.find_element(By.CSS_SELECTOR, "#partTabs .pt-add").click()
    time.sleep(0.2)
    print("＋ menu:", js("return [...document.querySelectorAll('#partTabs .part-add.open .menu-list button')].map(b => b.textContent)"))
    d.find_element(By.CSS_SELECTOR, ".viewport").click()

    # save (Save dialog stubbed) -> version 3 with both parts
    js(STUB)
    d.find_element(By.ID, "saveBtn").click()
    wait("return window.__saved")
    raw = __import__("base64").b64decode(js("return window.__saved"))
    proj = package.load(raw)["project"]
    print("saved: version", proj["version"], "| parts", [(p["id"], p["name"], p["classic"]["model"].get("kind") or "pdf") for p in proj["parts"]],
          "| active", proj["active"], "| project", proj["project_name"])
    path = Path(OUT) / "two_parts.a3d"
    path.write_bytes(raw)

    # reload and open it again
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "projectInput").send_keys(str(path))
    wait("return document.querySelectorAll('#partTabs .part-tab').length === 2 && window.__app.state.model?.kind === 'outline'")
    settled()
    print("reopened:", tabs(), "| top bar name", d.find_element(By.ID, "fileName").text,
          "| toast", js("return [...document.querySelectorAll('.toast')].map(t => t.textContent).pop()"))
    tab(0).click()
    wait("return window.__app.state.model?.source === 'initial draft.pdf'")
    settled()
    print("reopened part 1: volume", js("return window.__app.state.solution.volume"), "(was", vol1, ")")

    # an old version-2 project (one part) in a package still opens (migrated)
    v2 = {"app": "Auto3DModeler", "version": 2, "project_name": "Old file", **proj["parts"][0]["classic"]}
    old = Path(OUT) / "old_v2.a3d"
    old.write_bytes(package.write(v2, None)[0])
    d.find_element(By.ID, "projectInput").send_keys(str(old))
    wait("return document.querySelectorAll('#partTabs .part-tab').length === 1")
    settled()
    print("old v2 file:", tabs(), "| name", d.find_element(By.ID, "fileName").text, "| volume", js("return window.__app.state.solution.volume"))

    # a second file -> 2 tabs; close the first with ✕
    js("window.confirm = () => true")
    js("document.getElementById('sampleBtn').click()")
    wait("return document.querySelectorAll('#partTabs .part-tab').length === 2")
    settled()
    tab(0).find_element(By.CSS_SELECTOR, ".pt-x").click()
    wait("return document.querySelectorAll('#partTabs .part-tab').length === 1")
    print("after closing the tab:", tabs(), "| ✕ on the last tab too (closes it: nothing on screen):", bool(tab(0).find_elements(By.CSS_SELECTOR, ".pt-x")),
          "| still in the project:", js("return window.__app.project.parts.map(p => p.name + (p.closed ? ' (closed)' : ''))"))
    d.save_screenshot(f"{OUT}/p2_after_close.png")
    # ☰ Parts: every part — the closed one opens again (a tab), the state is saved with the project
    js("if (!document.querySelector('#projTree .pt-row')?.offsetParent) document.querySelector('#partTabs .pt-all').click()")  # (☰: the tree in sight — docked at first, or its popup)
    time.sleep(0.7)  # (past the tree's redraw 400 ms after the tab was closed: a row clicked before it is gone)
    # (read in one go: the tree is drawn again 400 ms after the tab was closed — row by row could catch it half way)
    print("☰ Parts:", js("return [...document.querySelectorAll('#projTree .pt-row')].map(r => r.innerText)"),
          "| closed ones:", len(d.find_elements(By.CSS_SELECTOR, "#projTree .pt-row.closed")))
    d.find_element(By.CSS_SELECTOR, "#projTree .pt-row.closed .pt-open").click()
    wait("return document.querySelectorAll('#partTabs .part-tab').length === 2")
    settled()
    print("opened again:", tabs())
    tab(1).find_element(By.CSS_SELECTOR, ".pt-x").click()
    wait("return document.querySelectorAll('#partTabs .part-tab').length === 1")
    print("saved with a closed part:", js("return window.__app.project.toJSON().parts.map(p => [p.name, !!p.closed])"))
    # ✕ in the ☰ tree deletes (after asking) — the tree is still open
    print("  the tree stays open:", "open" in d.find_element(By.CSS_SELECTOR, "#projTree").get_attribute("class"))
    time.sleep(0.2)
    d.find_element(By.CSS_SELECTOR, "#projTree .pt-row.closed .pt-del").click()
    time.sleep(0.4)
    print("deleted from ☰ Parts:", js("return window.__app.project.parts.map(p => p.name)"), "|", tabs())
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
