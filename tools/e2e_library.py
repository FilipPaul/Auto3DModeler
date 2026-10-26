"""📚 The parts library window, in headless Edge: 📚 Library -> search "608" -> the bearing: 608-2Z, Ø8 × Ø22 × 7, a 3D
preview, shop links -> ◆ Open as a new 3D model: a part with its library facts in its panel -> a new assembly: an M3×10
socket head screw put in twice (one part, two placed) and a SICK sensor -> the parts list with part numbers -> ⬇ BOM
(CSV): quantities, makers, part numbers -> 📚 Save to the library (a 3D model of the user's): found in the library
(★), then deleted.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_library.py http://127.0.0.1:5199 <out dir>
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


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def search(q):
    box = d.find_element(By.CSS_SELECTOR, ".lib .lib-q")
    box.clear()
    box.send_keys(q)
    time.sleep(0.3)
    return [b.text.split("\n")[0] for b in d.find_elements(By.CSS_SELECTOR, ".lib .lib-item")]


def pick(item_id, size=None, length=None):
    d.find_element(By.CSS_SELECTOR, f".lib [data-item='{item_id}']").click()
    time.sleep(0.3)
    if size is not None:
        js("const s = document.querySelector('.lib [data-k=size]'); s.value = arguments[0]; s.dispatchEvent(new Event('change'))", size)
        time.sleep(0.3)
    if length is not None:
        js("const s = document.querySelector('.lib [data-k=length]'); s.value = arguments[0]; s.dispatchEvent(new Event('change'))", str(length))
        time.sleep(0.3)


try:
    d.get(URL)
    wait("return !!window.__app")
    js("""window.__saved = []; window.showSaveFilePicker = async (o) => ({ name: o.suggestedName,
      createWritable: async () => ({ write: async (b) => { const u = new Uint8Array(await b.arrayBuffer()); window.__saved.push([o.suggestedName, await b.text(), [...u.slice(0, 3)]]); }, close: async () => {} }) });""")
    d.find_element(By.ID, "libBtn").click()
    wait("return window.__app.library.items?.length > 10 && !!document.querySelector('.lib .lib-item')")
    print("categories:", [g.text for g in d.find_elements(By.CSS_SELECTOR, ".lib .lib-gname")])
    print("search 608:", search("608"))
    pick("bearing", "608")
    wait("return !!window.__app.library.lastBody", 30)
    det = d.find_element(By.CSS_SELECTOR, ".lib .lib-detail")
    print("608:", det.find_element(By.CSS_SELECTOR, "h2").text, "|", det.find_element(By.CSS_SELECTOR, ".lib-desc").text[:80])
    print("  facts:", det.find_element(By.CSS_SELECTOR, ".lib-facts").text.replace("\n", " "), "| shops:", [a.text for a in det.find_elements(By.CSS_SELECTOR, ".lib-shops a")])
    print("  preview:", js("const b = window.__app.library.lastBody.bbox; return [b[3]-b[0], b[4]-b[1], b[5]-b[2]].map(v => +v.toFixed(2))"))
    print("  'Put into the assembly' (no assembly on screen) disabled:", not d.find_element(By.CSS_SELECTOR, ".lib [data-a=insert]").is_enabled())
    d.save_screenshot(f"{OUT}/library.png")
    d.find_element(By.CSS_SELECTOR, ".lib [data-a=model]").click()
    wait(f"return window.__app.state.workspace === 'model' && !!{M}.result?.body")
    time.sleep(0.4)
    print("as a 3D model:", js("return window.__app.project.current.name"), "| its panel:", d.find_element(By.CSS_SELECTOR, "#modelRight .lib-part").text.replace("\n", " ")[:120])

    call("new_assembly", name="Box")
    for item, size, length in (("iso4762", "M3", 10), ("iso4762", "M3", 10), ("sick-ime", "M12, 4 mm", None)):
        d.find_element(By.ID, "libBtn").click()
        wait("return window.__app.library.items?.length > 10 && !!document.querySelector('.lib .lib-item')")
        search("screw" if item == "iso4762" else "SICK")
        pick(item, size, length)
        d.find_element(By.CSS_SELECTOR, ".lib [data-a=insert]").click()
        wait(f"return !document.querySelector('.lib') && Object.values({A}.bodies).every(b => b.body)")
        time.sleep(0.4)
    print("in the assembly:", js(f"return {A}.doc.instances.map(i => [i.id, i.part])"), "| model parts in the project:",
          js("return window.__app.project.parts.filter(p => p.kind === 'model').map(p => p.name)"))
    js(f"{A}.sel = null; {A}.render()")
    time.sleep(0.3)
    print("parts list part numbers:", d.find_element(By.CSS_SELECTOR, "#asmRight .as-pns").text.replace("\n", " | "))
    d.find_element(By.CSS_SELECTOR, "#asmRight [data-a=bomCsv]").click()
    wait("return window.__saved.length === 1", 20)
    name, text, head = js("return window.__saved[0]")
    print("BOM:", name, "| starts with the UTF-8 mark (Excel):", head == [0xEF, 0xBB, 0xBF])
    for line in text.lstrip(chr(0xFEFF)).split(chr(13) + chr(10)):
        print("  ", line[:70], "…", line[-45:])

    # 📚 Save to the library: a 3D model of the user's
    call("new_model", name="My bracket")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 30, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=3)
    wait(f"return !!{M}.result?.body && !{M}.inflight")
    js(f"{M}.renderProps()")
    time.sleep(0.3)
    d.find_element(By.CSS_SELECTOR, "#modelRight [data-a=saveToLibrary]").click()
    wait("return !!document.querySelector('.lib-save')")
    js("document.querySelector('.lib-save [data-k=category]').value = 'My parts / Brackets'")
    d.find_element(By.CSS_SELECTOR, ".lib-save [data-a=save]").click()
    wait("return !document.querySelector('.lib-save')")
    mine = js("return fetch('/api/library').then(r => r.json()).then(r => r.items.filter(i => i.source === 'user').map(i => [i.id, i.name, i.category]))")
    print("saved to the library:", mine)
    d.find_element(By.ID, "libBtn").click()
    wait("return window.__app.library.items?.length > 10 && !!document.querySelector('.lib .lib-item')")
    print("found with a search:", search("bracket"))
    for mid, _, _ in mine:
        if mid.startswith("my-my-bracket"):
            js("return fetch('/api/library/' + arguments[0], { method: 'DELETE' })", mid)
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
