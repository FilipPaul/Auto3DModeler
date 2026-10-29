"""Light assemblies, in headless Edge with real clicks: two 3D model parts (a 60 x 40 x 5 plate and a Ø8 x 20 pin,
built through the AI tools) -> ＋ New assembly -> insert both -> 🧲 snap the pin's top face onto the plate's top
(it turns over and the faces meet, centred) -> nudge / turn -> explode -> parts list (mass) -> STL / STEP export ->
Save project -> reopen: the assembly is back.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_assembly.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time
from pathlib import Path

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
A = "window.__app.assembly"
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


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#asmViewport canvas")


def screen_of(inst, local):
    """The canvas offset of a point given in a part's own coordinates, as placed in the assembly."""
    return js(f"""const a = {A}, it = a.inst(arguments[0]), v = a.view, V = v.camera.position.constructor;
      const M = new (v.camera.matrix.constructor)().fromArray(it.matrix), p = new V(...arguments[1]).applyMatrix4(M);
      const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", inst, local)


def click_at(o):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *o).perform()
    time.sleep(0.2)
    ActionChains(d).click().perform()
    time.sleep(0.5)


def matrix(inst):
    return js(f"return {A}.inst(arguments[0]).matrix.map(v => +v.toFixed(4))", inst)


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("new_model", name="Pin")
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 8}}])
    call("add_feature", type="extrude", sketch="F1", d=20)
    time.sleep(1)
    print("parts:", json.loads(call("list_parts")))

    # ＋ New assembly (in the ＋ menu next to the tabs), insert both parts
    js("document.querySelector('#partTabs .pt-add').click(); document.querySelector('#partTabs [data-new=assembly]').click()")
    wait("return document.body.classList.contains('ws-assembly')")
    time.sleep(0.5)
    print("empty assembly:", js("return document.querySelector('#asmLeft .as-start').hidden === false"), "| tabs",
          js("return [...document.querySelectorAll('#partTabs .part-tab')].map(t => t.textContent.trim())"))
    for name in ("Plate", "Pin"):
        d.find_element(By.CSS_SELECTOR, "#asmViewport [data-a=insert]").click()
        time.sleep(0.2)
        next(b for b in d.find_elements(By.CSS_SELECTOR, "#asmViewport .as-insert [data-part]") if b.text.split(" ", 1)[-1] == name).click()
        wait(f"return {A}.doc.instances.length >= {1 if name == 'Plate' else 2} && Object.values({A}.bodies).every(b => b.body)")
        time.sleep(0.6)
    print("inserted:", js(f"return {A}.doc.instances.map(i => [i.id, i.part])"), "| pin placed beside:", matrix("I2")[12:15])
    js(f"{A}.view.setView('iso')")
    time.sleep(0.5)
    d.save_screenshot(f"{OUT}/as1_inserted.png")

    # 🔗 Joint ▾ Touch: the pin's top face (its own z 20) onto the plate's top (z 5)
    time.sleep(0.2)
    d.find_element(By.CSS_SELECTOR, "#asmViewport [data-a=joints]").click()  # (🔗 Joint ▾: its menu)
    d.find_element(By.CSS_SELECTOR, "#asmViewport [data-joint=touch]").click()
    time.sleep(0.3)
    click_at(screen_of("I2", [1.5, 1.5, 20]))
    print("joint from:", js(f"return {A}.jointFrom && [{A}.jointFrom.inst, {A}.jointFrom.face.name]"), "| hint", js("return document.querySelector('#asmViewport .m-hint').textContent"))
    click_at(screen_of("I1", [20, 15, 5]))
    m = matrix("I2")
    print("snapped pin matrix:", m, "| upside down (z axis -1):", m[10] == -1, "| top face now at the plate's top centre:", m[12:15])
    d.save_screenshot(f"{OUT}/as2_snapped.png")

    # the panel: nudge x, turn 90° about X, then back (the pin is joined: moving it asks — yes, break the joint)
    js("window.confirm = () => true")
    print("joined: it moves the ways its joints leave:", [e.text for e in d.find_elements(By.CSS_SELECTOR, "#asmRight .as-dof label")])
    d.find_element(By.CSS_SELECTOR, "#asmRight .as-free summary").click()  # placing it by hand (breaks the joint)
    inp = d.find_element(By.CSS_SELECTOR, "#asmRight input[data-k=x]")
    inp.clear()
    inp.send_keys("25\n")
    time.sleep(0.4)
    print("x set to 25:", matrix("I2")[12])
    sl = d.find_element(By.CSS_SELECTOR, "#asmRight input[data-rot=x]")
    js("arguments[0].value = 91; arguments[0].dispatchEvent(new Event('input')); arguments[0].dispatchEvent(new Event('change'))", sl)
    time.sleep(0.4)
    print("turned to 90° about X (slider, caught):", matrix("I2")[4:7])
    js("document.querySelector('#asmViewport [data-a=undo]').click()")
    time.sleep(0.5)
    print("undo the turn:", matrix("I2")[4:7])

    # explode, parts list, export
    js("const r = document.querySelector('#asmViewport .as-explode input'); r.value = 0.8; r.dispatchEvent(new Event('input'))")
    time.sleep(0.3)
    d.save_screenshot(f"{OUT}/as3_exploded.png")
    canvas().click()
    time.sleep(0.4)
    js(f"{A}.sel = null; {A}.render()")
    print("parts list:", js("return [...document.querySelectorAll('#asmRight .as-bom tr')].map(r => r.innerText.replace(/\\t/g, ' | '))"))
    js("""window.__saved = []; window.showSaveFilePicker = async (o) => ({ name: o.suggestedName,
      createWritable: async () => ({ write: async (b) => { window.__saved.push([o.suggestedName, b.size, b.type === 'application/json' ? await b.text() : null]); }, close: async () => {} }) });""")
    d.find_element(By.CSS_SELECTOR, "#asmRight [data-x=stl]").click()
    wait("return window.__saved.length === 1")
    d.find_element(By.CSS_SELECTOR, "#asmRight [data-x=step]").click()
    wait("return window.__saved.length === 2", 60)
    sv = js("return window.__saved.map(s => [s[0], s[1]])")
    print("exports:", sv, "| STL triangles:", (sv[0][1] - 84) // 50)

    # save the project and reopen it
    d.find_element(By.ID, "saveBtn").click()
    wait("return window.__saved.length === 3")
    proj = json.loads(js("return window.__saved[2][2]"))
    print("saved:", [(p["id"], p["kind"], p["name"]) for p in proj["parts"]])
    path = Path(OUT) / "assembly_project.a3d.json"
    path.write_text(json.dumps(proj), encoding="utf-8")
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "projectInput").send_keys(str(path))
    wait(f"return document.body.classList.contains('ws-assembly') && {A}.doc.instances.length === 2 && Object.values({A}.bodies).every(b => b.body)", 60)
    time.sleep(0.5)
    print("reopened:", js(f"return {A}.doc.instances.map(i => [i.id, i.part, i.matrix.slice(12, 15)])"))
    d.save_screenshot(f"{OUT}/as4_reopened.png")
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
