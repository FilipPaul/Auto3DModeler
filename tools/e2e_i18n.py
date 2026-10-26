"""Czech / English: the language switch translates the whole page live (panels, the outline wizard, checks,
toasts), lists texts that stay in English, and switching back restores the originals — in headless Edge.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_i18n.py http://127.0.0.1:5199 <out dir>
"""
import sys
from pathlib import Path
import time

from selenium import webdriver
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
PIC = str(Path(__file__).resolve().parent.parent / 'pernicek.png')
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.add_argument("--lang=en-US")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script

# visible text nodes / tooltips with English words that were not translated
LEFT = r"""const out = new Set(), words = /\b(the|and|to|of|with|click|add|from|part|outline|size|height|width|drawing|remove|edit|object|shape|layer|show|pick)\b/i;
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n; while ((n = w.nextNode())) { const p = n.parentElement, s = n.nodeValue.trim();
    if (!s || !p || p.closest('.ai-msg, [data-no-i18n], script, style, .dim-label') || !p.getClientRects().length) continue;
    if (words.test(s)) out.add(s.slice(0, 90)); }
  for (const e of document.querySelectorAll('[title], [placeholder]')) for (const a of ['title', 'placeholder']) {
    const v = e.getAttribute(a); if (v && words.test(v) && !e.closest('[data-no-i18n]')) out.add('@' + v.slice(0, 90)); }
  return [...out];"""


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def tab(sel):
    js(f"document.querySelector('{sel}').click()")
    time.sleep(0.4)


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('auto3d-lang')")
    d.get(URL)
    wait("return !!window.__app")
    print("default (en-US browser):", js("return document.documentElement.lang"), "| button:", d.find_element(By.ID, "langBtn").text)
    js("document.getElementById('sampleBtn').click()")
    wait("return window.__app.state.solution?.mesh")
    time.sleep(1)
    en_dims = js("return document.querySelector('.panel.left').innerText.slice(0, 200)")

    d.find_element(By.ID, "langBtn").click()
    time.sleep(0.5)
    print("after switch:", js("return document.documentElement.lang"), "| button:", d.find_element(By.ID, "langBtn").text)
    print("top bar:", js("return document.querySelector('.topbar .actions').innerText.replace(/\\n/g, ' | ')"))
    print("dimensions panel:", js("return document.querySelector('.panel.left').innerText.slice(0, 300).replace(/\\n/g, ' | ')"))
    left = set(js(LEFT))
    for sel in ("[data-tab=issues]", "[data-tab=drawing]", "[data-tab=ai]", "[data-rtab=outline]", "[data-rtab=design]", "[data-rtab=print]"):
        try:
            tab(sel)
        except Exception as e:  # noqa: BLE001
            print("no tab", sel, e)
            continue
        left |= set(js(LEFT))
    d.save_screenshot(f"{OUT}/i1_cz.png")
    # added later: a 3D object and a toast
    js("return window.__app.agentHandlers.add_object({kind: 'cylinder', op: 'subtract', x: 30, y: 5.5, w: 2, h: 2, z0: 0, z1: 1})")
    time.sleep(1.5)
    tab("[data-rtab=outline]")
    left |= set(js(LEFT))
    print("toasts:", js("return [...document.querySelectorAll('.toast')].map(t => t.textContent)"))
    print("part panel:", js("return document.getElementById('rtab-outline').innerText.slice(0, 400).replace(/\\n/g, ' | ')"))
    # the outline wizard (on the test picture)
    d.find_element(By.ID, "imgInput").send_keys(PIC)
    wait("return document.querySelector('.wizard .wz-cand, .wizard .wz-cands > *')", 60)
    time.sleep(1.5)
    print("wizard:", js("return document.querySelector('.wizard').innerText.slice(0, 300).replace(/\\n/g, ' | ')"))
    left |= set(js(LEFT))
    d.save_screenshot(f"{OUT}/i3_wizard.png")
    # use it: an outline part (cookie cutter) — the Part panel and the design-layer hint, also rebuilt later
    js("document.querySelector('.wizard .wz-use').click()")
    wait("return window.__app.state.model?.kind === 'outline' && window.__app.state.solution?.mesh")
    time.sleep(1)
    tab("[data-rtab=design]")
    print("design target:", js("return document.getElementById('designTarget').innerText"))
    tab("[data-rtab=outline]")
    print("part panel:", js("return document.getElementById('rtab-outline').innerText.slice(0, 500).replace(/\\n/g, ' | ')"))
    left |= set(js(LEFT))
    d.save_screenshot(f"{OUT}/i4_outline_part.png")
    print("still English (%d):" % len(left))
    for s in sorted(left):
        print("   ", s)

    # the 3D model workspace: new model, sketch mode, a rectangle, the Extrude panel, the finished part
    before_model = set(left)
    d.find_element(By.ID, "newModelBtn").click()
    wait("return window.__app.modeler.mode === 'sketch'")
    time.sleep(1)
    left |= set(js(LEFT))
    def inner(sel, n=400):
        return (js("return document.querySelector(arguments[0]).innerText", sel) or "")[:n].replace("\n", " | ")

    print("model sketch bar:", inner(".m-cmdbar"))
    js("""const s = window.__app.modeler.sk; s.addRect({uv: [0, 0], id: 'O'}, {uv: [40, 20]});
      s.addCircle({uv: [10, 10]}, {uv: [13, 10]}); s.sel = {kind: 'entity', id: 'c1'}; s.changed();""")
    time.sleep(0.4)
    left |= set(js(LEFT))
    js("window.__app.modeler.sk.setTool('line')")
    time.sleep(0.3)
    left |= set(js(LEFT))
    # a dimension, the chooser and the list of locks
    js("""const s = window.__app.modeler.sk; s.setTool('dim');
      s.f.dims.push({id: 'dz', t: 'dx', a: 'O', b: s.f.entities.find(e => e.t === 'circle').c, v: 10}); s.changed();
      s.showChooser([{spec: {t: 'dx'}, v: 3}, {spec: {t: 'dy'}, v: 4}, {spec: {t: 'dist'}, v: 5}], {clientX: 700, clientY: 400});""")
    time.sleep(0.4)
    left |= set(js(LEFT))
    js("window.__app.modeler.sk.closeChooser()")
    time.sleep(0.4)
    left |= set(js(LEFT))
    js("window.__app.modeler.finishSketch()")
    wait("return window.__app.modeler.cmd && window.__app.modeler.result?.body")
    time.sleep(0.8)
    left |= set(js(LEFT))
    print("extrude panel:", inner("#modelRight"))
    js("window.__app.modeler.okExtrude()")
    wait("return !window.__app.modeler.inflight && !window.__app.modeler.cmd")
    time.sleep(0.8)
    left |= set(js(LEFT))
    # fillet and hole panels
    js("const m = window.__app.modeler; m.toggleMeasure(); m.measureBox('<div class=\"mm-rows\"><b>Flat face</b><span>Area</span><b>1</b></div><p class=\"hint\">Click a second spot for the distance.</p>'); m.toggleSection();")
    time.sleep(0.5)
    left |= set(js(LEFT))
    js("const m = window.__app.modeler; m.toggleMeasure(); m.toggleSection();")
    time.sleep(0.3)
    for cmd in ("fillet", "hole", "chamfer", "revolve", "shell"):
        js(f"window.__app.modeler.action('{cmd}')")
        time.sleep(0.6)
        left |= set(js(LEFT))
        js("window.__app.modeler.cancelCommand()")
        time.sleep(0.4)
    print("model tree:", inner(".mt-tree"), "| part panel:", inner("#modelRight", 200))
    # an assembly with the model in it
    js("window.__app.project.newAssembly()")
    wait("return document.body.classList.contains('ws-assembly')")
    time.sleep(0.6)
    left |= set(js(LEFT))
    pid = js("return window.__app.project.parts.find(p => p.kind === 'model').id")
    js("return window.__app.assembly.insert(arguments[0])", pid)
    wait("return window.__app.assembly.doc.instances.length === 1 && Object.values(window.__app.assembly.bodies).every(b => b.body)")
    time.sleep(0.6)
    left |= set(js(LEFT))
    js("window.__app.assembly.sel = null; window.__app.assembly.render()")
    time.sleep(0.4)
    left |= set(js(LEFT))
    print("still English in the 3D model workspace:", sorted(set(js(LEFT)) - before_model))
    d.save_screenshot(f"{OUT}/i5_model_cz.png")
    d.find_elements(By.CSS_SELECTOR, "#partTabs .part-tab")[0].click()
    wait("return !document.body.classList.contains('ws-model')")
    time.sleep(1)

    # rename of a dimension is not triggered by the translated name
    names = js("return window.__app.state.model.params.map(p => p.name)")
    tab("[data-tab=params]")
    js("const n = document.querySelector('.param .name'); n && (n.focus(), n.blur());")
    time.sleep(0.3)
    print("param names unchanged:", names == js("return window.__app.state.model.params.map(p => p.name)"), names[:3])

    d.find_element(By.ID, "langBtn").click()
    time.sleep(0.5)
    czech = js("""const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT), out = [];
      let n; while ((n = w.nextNode())) if (/[ěščřžůĚŠČŘŽ]/.test(n.nodeValue) && !n.parentElement.closest('[data-no-i18n]')) out.push(n.nodeValue.trim().slice(0, 60));
      for (const e of document.querySelectorAll('[title]')) if (/[ěščřžůĚŠČŘŽ]/.test(e.title) && !e.closest('[data-no-i18n]')) out.push('@' + e.title.slice(0, 60));
      return out;""")
    print("back to English — Czech left:", czech, "| lang", js("return document.documentElement.lang"))
    d.refresh()
    wait("return !!window.__app")
    print("after reload: lang", js("return document.documentElement.lang"), "(remembered)")
    js("localStorage.setItem('auto3d-lang', 'cs')")
    d.refresh()
    wait("return !!window.__app")
    time.sleep(0.5)
    print("opened in Czech:", js("return document.documentElement.lang"), "|", js("return document.querySelector('.topbar').innerText.replace(/\\n/g, ' | ')"))
    js("localStorage.removeItem('auto3d-lang')")
    del en_dims
    d.save_screenshot(f"{OUT}/i2_en.png")
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
