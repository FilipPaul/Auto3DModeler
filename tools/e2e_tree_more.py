"""The project tree and tabs, more, in headless Edge: a Base model, an assembly with a library screw -> the screw's tab and
tree row show the library icon; a step added to the screw: its own icon again -> a hover on the Base's row in ☰: a
picture of it -> the Base's row dragged onto the assembly's view: one more Base in it -> a middle click on a tab
closes it.

  PYTHONIOENCODING=utf-8 py tools/e2e_tree_more.py http://127.0.0.1:5199 <out dir>
"""
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
H = "window.__app.agentHandlers"
P = "window.__app.project"
A = "window.__app.assembly"


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(script)


def icons(sel):
    return js("return [...document.querySelectorAll(arguments[0])].map(r => [r.querySelector('.pt-name, .pt-rname')?.textContent, r.querySelector('.ico')?.classList[1]])", sel)


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Base")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 30}}])
    call("add_feature", type="extrude", sketch="F1", d=6)
    call("new_assembly", name="Box")
    call("insert_part", part="Base")
    print("a library screw:", call("library_add", item="iso4762", size="M3", length=10, to="assembly")[:40])
    time.sleep(1)
    print("tabs:", icons("#partTabs .part-tab"))
    js(f"{P}.toggleTree(true)")
    time.sleep(0.4)
    print("tree:", icons("#projTree .pt-row"))
    screw = js(f"return {P}.parts.find(p => p.data?.library || p.name.includes('ISO')).id")
    js(f"const p = {P}.parts.find(q => q.id === arguments[0]); p.data = {{ ...p.data, features: [...p.data.features, {{ id: 'X9', type: 'sketch', plane: {{ datum: 'XY' }}, points: {{}}, entities: [] }}] }}; {P}.render()", screw)
    time.sleep(0.3)
    print("the screw changed: its icon", icons(f"#projTree .pt-row[data-part='{screw}']"))

    base = js(f"return {P}.parts.find(p => p.name === 'Base').id")
    row = d.find_element(By.CSS_SELECTOR, f"#projTree .pt-row[data-part='{base}']")
    ActionChains(d).move_to_element(row).perform()
    wait("return document.querySelector('.tr-preview img')?.src?.startsWith('data:image/png')", 30)
    print("hover on the Base: a picture", js("return [document.querySelector('.tr-preview img').naturalWidth, document.querySelector('.tr-preview b').textContent]"))
    d.save_screenshot(f"{OUT}/tree_preview.png")
    ActionChains(d).move_by_offset(400, 300).perform()
    time.sleep(0.3)
    print("  gone after:", js("return document.querySelector('.tr-preview').hidden"))

    n0 = js(f"return {A}.doc.instances.length")
    js("""const row = document.querySelector(`#projTree .pt-row[data-part="${arguments[0]}"]`), vp = document.getElementById('asmViewport'), dt = new DataTransfer();
      row.dispatchEvent(new DragEvent('dragstart', { bubbles: true, dataTransfer: dt }));
      vp.dispatchEvent(new DragEvent('dragover', { bubbles: true, cancelable: true, dataTransfer: dt }));
      vp.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: dt }));""", base)
    wait(f"return {A}.doc.instances.length > {n0}", 20)
    print("the Base dragged from the tree into the assembly:", n0, "->", js(f"return {A}.doc.instances.map(i => i.part === arguments[0] ? 'Base' : 'other')", base))

    tabs0 = len(d.find_elements(By.CSS_SELECTOR, "#partTabs .part-tab"))
    tab = d.find_element(By.CSS_SELECTOR, f"#partTabs .part-tab[data-part='{base}']")
    js("arguments[0].dispatchEvent(new MouseEvent('auxclick', { bubbles: true, cancelable: true, button: 1 }))", tab)
    time.sleep(0.6)
    print("a middle click on the Base's tab:", tabs0, "->", len(d.find_elements(By.CSS_SELECTOR, "#partTabs .part-tab")), "tabs")
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
