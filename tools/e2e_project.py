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
  createWritable: async () => ({ write: async (b) => { window.__saved = await b.text(); }, close: async () => {} }) });
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
    proj = json.loads(js("return window.__saved"))
    print("saved: version", proj["version"], "| parts", [(p["id"], p["name"], p["classic"]["model"].get("kind") or "pdf") for p in proj["parts"]],
          "| active", proj["active"], "| project", proj["project_name"])
    path = Path(OUT) / "two_parts.a3d.json"
    path.write_text(json.dumps(proj), encoding="utf-8")

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

    # an old version-2 file (one part) still opens
    v2 = {"app": "Auto3DModeler", "version": 2, "project_name": "Old file", **proj["parts"][0]["classic"]}
    old = Path(OUT) / "old_v2.a3d.json"
    old.write_text(json.dumps(v2), encoding="utf-8")
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
    print("after closing:", tabs(), "| ✕ hidden on the last part:", not tab(0).find_elements(By.CSS_SELECTOR, ".pt-x"))
    d.save_screenshot(f"{OUT}/p2_after_close.png")
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
