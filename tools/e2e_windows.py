"""⧉ A part in a window of its own, in headless Edge: a Base model and an assembly using it -> ⧉ on the Base's tab: a
new window with the Base on screen -> a hole added there: the assembly in the first window is built again with it ->
a second Base put in the assembly (first window): the other window has it too -> the Base on screen in both: a step
added in one is shown in the other -> no changes going back and forth when nothing is done, the same in both -> a
drawing sheet of the Base in the other window: a hole added in the first -> the sheet made again (a new revision) -> the new
window showed only its tab -> a tab dragged from the first window into the second's tab row: it opens there and goes from the first.

  PYTHONIOENCODING=utf-8 py tools/e2e_windows.py http://127.0.0.1:5199 <out dir>
"""
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
A = "window.__app.assembly"
H = "window.__app.agentHandlers"
P = "window.__app.project"


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(script)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def faces_in_asm():
    return js(f"return {A}.bodies[{A}.inst('I1').part]?.body?.faces.length")


errors = []
try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Base")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    base = js(f"return {P}.active")
    call("new_assembly", name="Box")
    call("insert_part", part="Base")
    wait(f"return !!{A}.bodies[{A}.inst('I1').part]?.body")
    f0 = faces_in_asm()
    first = d.current_window_handle
    tab = d.find_element(By.CSS_SELECTOR, f"#partTabs .part-tab[data-part='{base}']")
    js("arguments[0].click()", tab.find_element(By.CSS_SELECTOR, ".pt-win"))
    end = time.time() + 20
    while len(d.window_handles) < 2 and time.time() < end:
        time.sleep(0.2)
    second = next(h for h in d.window_handles if h != first)
    d.switch_to.window(second)
    wait(f"return !!window.__app && {P}.parts.length === 2 && {P}.active === '{base}' && !!window.__app.modeler.result?.body")
    print("⧉ the new window:", js(f"return [{P}.current.name, document.title, window.__app.state.workspace, {P}.parts.map(p => p.name)]"))
    print("  only its tab there:", js("return [...document.querySelectorAll('#partTabs .part-tab')].map(t => t.textContent.trim())"),
          "| the project has both:", js(f"return {P}.parts.length"))
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=8)
    print("  a hole added there:", js("return window.__app.modeler.part.features.length"), "steps")
    d.switch_to.window(first)
    wait(f"return {A}.bodies[{A}.inst('I1').part]?.body?.faces.length !== {f0}", 60)
    print("the first window's assembly built again:", f0, "->", faces_in_asm(), "faces")
    call("insert_part", part="Base")
    time.sleep(1)
    d.switch_to.window(second)
    wait(f"return ({P}.parts.find(p => p.kind === 'assembly').data.instances || []).length === 2", 20)
    print("the other window has the second Base:", js(f"return {P}.parts.find(p => p.kind === 'assembly').data.instances.length"))
    d.switch_to.window(first)
    js(f"{P}.switchTo('{base}')")
    wait(f"return {P}.active === '{base}' && !!window.__app.modeler.result?.body")
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 20, "y": 10, "d": 4}}])
    d.switch_to.window(second)
    wait("return window.__app.modeler.part.features.length === 4", 20)
    print("both on the Base: a step in the first shown in the other:", js("return window.__app.modeler.part.features.map(f => f.type)"))
    # quiet: nothing goes back and forth
    sent = []
    for h in (first, second):
        d.switch_to.window(h)
        js("window.__msgs = 0; const ch = new BroadcastChannel(`a3d-project-${window.__app.autosave.id}`); ch.onmessage = () => window.__msgs++; window.__ch = ch;")
    time.sleep(3)
    for h in (first, second):
        d.switch_to.window(h)
        sent.append(js("return window.__msgs"))
    print("messages in 3 quiet seconds:", sent)
    keys = []
    for h in (first, second):
        d.switch_to.window(h)
        keys.append(js(f"return JSON.stringify({P}.parts.map(p => [p.id, p.name, p.kind, p.id === {P}.active ? 'live' : p.data]).filter(x => x[3] === 'live' || true).map(x => x[0] + x[1]))"))
        keys.append(js("return JSON.stringify(window.__app.modeler.payload().features)"))
    print("the same in both:", keys[0] == keys[2], keys[1] == keys[3])
    d.switch_to.window(second)
    call("sheet_open", part="Base")
    wait("return !!window.__app.sheet.svgEl && !!window.__app.sheet.d.built", 120)
    h0, c0 = js("return [window.__app.sheet.d.hash, window.__app.sheet.allDims().length]")
    d.switch_to.window(first)
    call("add_feature", type="hole", face="F2:end", points=[[-20, -10]], d=5)
    d.switch_to.window(second)
    wait(f"return window.__app.sheet.d.hash !== '{h0}' && !window.__app.sheet.busy", 120)
    time.sleep(1)
    print("a sheet in the other window made again:", js("return [window.__app.sheet.d.rev, window.__app.sheet.allDims().length]"), "dims before", c0)
    # a tab dragged from the first window into the second one's tab row: it opens there, it goes from here
    d.switch_to.window(first)
    box_id = js(f"return {P}.parts.find(p => p.name === 'Box').id")
    js(f"{P}.switchTo(arguments[0])", box_id)
    time.sleep(1)
    src = js(f"return [window.__app.windows.wid, window.__app.autosave.id]")
    js("""const tab = document.querySelector(`#partTabs .part-tab[data-part="${arguments[0]}"]`), dt = new DataTransfer();
      window.__dt = dt; tab.dispatchEvent(new DragEvent('dragstart', { bubbles: true, dataTransfer: dt }));""", box_id)
    d.switch_to.window(second)
    js("""const dt = new DataTransfer(); dt.setData('text/a3d-part', arguments[0]); dt.setData('text/a3d-from', JSON.stringify({ win: arguments[1], project: arguments[2] }));
      const el = document.getElementById('partTabs'); el.dispatchEvent(new DragEvent('dragover', { bubbles: true, cancelable: true, dataTransfer: dt }));
      el.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: dt }));""", box_id, *src)
    time.sleep(1.5)
    print("dropped into the second window:", js("return [...document.querySelectorAll('#partTabs .part-tab')].map(t => t.textContent.trim())"), "| on screen:", js(f"return {P}.current.name"))
    d.switch_to.window(first)
    time.sleep(1.2)  # (the second window told it that it took the tab)
    print("  gone from the first window:", js("return [...document.querySelectorAll('#partTabs .part-tab')].map(t => t.textContent.trim())"), "| windows:", len(d.window_handles))
    for h in (first, second):
        d.switch_to.window(h)
        errors += [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
finally:
    print("console errors:", errors)
    d.quit()
