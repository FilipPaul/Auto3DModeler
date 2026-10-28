"""Picking on the part + outline masks in 3D design, in headless Edge with real mouse input.

Cookie cutter -> custom objects -> ＋ Cylinder placed by clicking the flange top -> its top height picked
on the cutting edge -> corner snapping -> Esc; then 3D design ＋ Outline (picture traced in the outline
editor) as an engraved layer on the flange, reopened for editing, saved and reloaded with the project.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_pick_layers.py http://127.0.0.1:5199 <abs path to pernicek.png> <out dir>
"""
import json
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

URL, IMG, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script


def wait(script, t=30):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(script)


def settle():
    time.sleep(0.5)
    wait("return document.getElementById('busy').hidden")
    time.sleep(0.6)


# find a screen point whose pick hits a face at height z with the given normal direction
FIND = """const [z, up] = arguments, v = window.__app.viewer, r = v.renderer.domElement.getBoundingClientRect();
for (let gy = 0.15; gy < 0.9; gy += 0.01) for (let gx = 0.1; gx < 0.9; gx += 0.01) {
  const cx = r.left + gx * r.width, cy = r.top + gy * r.height, h = v.pickSurface(cx, cy);
  if (h && h.snap === (up ? 'top face' : 'bottom face') && Math.abs(h.z - z) < 1e-6) return [cx - r.left - r.width / 2, cy - r.top - r.height / 2, h];
}
return null;"""


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#viewport canvas")


def click_canvas(dx, dy):
    ActionChains(d, duration=40).move_to_element_with_offset(canvas(), int(dx), int(dy)).click().perform()


try:
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "imgInput").send_keys(IMG)
    wait("return document.querySelectorAll('.wz-cand').length > 0"); time.sleep(1)
    js("const w = document.querySelector('.wz-w'); w.value = '120'; w.dispatchEvent(new Event('input'))")
    d.find_element(By.CSS_SELECTOR, ".wz-use").click()
    wait("return window.__app.state.solution && window.__app.state.solution.mesh"); settle()
    js("document.querySelector('[data-view=iso]').click()"); time.sleep(0.5)
    js("[...document.querySelectorAll('#rtab-outline button')].find(b => b.textContent.startsWith('Edit as 3D')).click()"); settle()
    # what the app picks at each click (snapping included), to compare with the result
    js("""window.__picks = []; document.querySelector('#viewport canvas').addEventListener('pointerup',
      (e) => window.__picks.push(window.__app.viewer.pickSurface(e.clientX, e.clientY)), true)""")

    # ＋ Cylinder -> click on the flange top (z = 2): placed there, standing on it (z 2..5)
    js("[...document.querySelectorAll('#rtab-outline .row-actions button')].find(b => b.dataset.a === 'circle').click()"); settle()
    print("pick hint:", js("return document.getElementById('toolHint').textContent"))
    spot = js(FIND, 2, True)
    click_canvas(spot[0], spot[1]); settle()
    cyl = js("return window.__app.state.model.objects.find(o => o.source === 'circle')")
    pk = js("return window.__picks.at(-1)")
    print(f"cylinder placed: x {cyl['x']:.2f} y {cyl['y']:.2f} z {cyl['z0']}..{cyl['z1']} | clicked: {pk['snap']} "
          f"x {pk['x']:.2f} y {pk['y']:.2f} z {pk['z']} ->", "OK" if abs(cyl['x'] - pk['x']) < 1e-6 and cyl['z0'] == pk['z'] else "MISMATCH")

    # ⌖ top z -> click the top of the cutting edge (z = 15)
    js("""const card = document.querySelector('#rtab-outline .layer.open');
      [...card.querySelectorAll('.mini.pick')].find(b => b.title.startsWith('Pick the top height')).click()""")
    spot = js(FIND, 15, True)
    click_canvas(spot[0], spot[1]); settle()
    cyl = js("return window.__app.state.model.objects.find(o => o.source === 'circle')")
    print(f"top height picked on the cutting edge: z {cyl['z0']}..{cyl['z1']}, z_range {js('return window.__app.state.solution.z_range')}")
    d.save_screenshot(f"{OUT}/k1_cylinder.png")

    # hovering near a corner snaps to it; Esc cancels picking
    js("""const card = document.querySelector('#rtab-outline .layer.open');
      [...card.querySelectorAll('.mini.pick')].find(b => b.title.startsWith('Pick the centre')).click()""")
    # a corner of the flange top (z = 2) facing the camera, probed 3 px beside it at whole pixels (like a mouse)
    corner = js("""const v = window.__app.viewer, p = v.mesh.geometry.attributes.position, r = v.renderer.domElement.getBoundingClientRect();
      for (let i = 0; i < p.count; i++) { if (Math.abs(p.getZ(i) - 2) > 1e-6) continue;
        const s = v.toScreen(p.getX(i), p.getY(i), p.getZ(i)), x = Math.round(s.x + 3), y = Math.round(s.y + 1);
        const h = v.pickSurface(x, y);
        if (h && h.snap === 'corner' && Math.abs(h.z - 2) < 1e-6) return [x - r.left - r.width / 2, y - r.top - r.height / 2, h]; }
      return null;""")
    print("corner probe:", corner and corner[2])
    ActionChains(d, duration=40).move_to_element_with_offset(canvas(), int(corner[0]), int(corner[1])).perform(); time.sleep(0.3)
    print("hover near a corner:", js("return document.querySelector('.pick-label')?.textContent"))
    d.save_screenshot(f"{OUT}/k2_corner.png")
    ActionChains(d).send_keys("").perform(); time.sleep(0.2)
    print("Esc cancels:", js("return document.getElementById('toolHint').hidden && !document.querySelector('.pick-label')"))

    # 3D design: ＋ Outline from a picture -> engraved into the flange
    js("document.querySelector('.rtab[data-rtab=design]').click()")
    print("design target hint:", js("return document.getElementById('designTarget').textContent.trim().replace(/\\s+/g, ' ')"))
    vol0 = js("return window.__app.state.solution.volume")
    d.find_element(By.ID, "outlineLayerInput").send_keys(IMG)
    wait("return document.querySelectorAll('.wz-cand').length > 0"); time.sleep(1)
    print("wizard for a layer:", js("return [document.querySelector('.wz-use').textContent, document.querySelector('.wz-make').hidden]"))
    js("const w = document.querySelector('.wz-w'); w.value = '4'; w.dispatchEvent(new Event('input'))")
    d.find_element(By.CSS_SELECTOR, ".wz-use").click(); settle()
    L = js("return window.__app.layers.layers[0]")
    print(f"layer: {L['name']}, mask {L['mask']['kind']} {L['mask']['w']:.1f} x {L['mask']['h']:.2f} mm, picture {L['mask'].get('picture')}")
    # put it on the flange at the picked spot and engrave it 0.5 mm
    flange = js(FIND, 2, True)[2]
    js(f"""const L = window.__app.layers.layers[0]; Object.assign(L, {{op: 'engrave', depth: 0.5}});
      Object.assign(L.mask, {{x: {flange['x']}, y: {flange['y']}}}); window.__app.layers.render(); window.__app.layers.onChange();""")
    settle()
    vol1 = js("return window.__app.state.solution.volume")
    print(f"engraved outline on the flange: volume {vol0:.1f} -> {vol1:.1f} mm³, issues:",
          [i["message"] for i in js("return window.__app.state.solution.design_issues")])
    d.save_screenshot(f"{OUT}/k3_layer.png")

    # reopen the layer's outline in the editor, then cancel
    js("window.__app.layers.selected = null; window.__app.layers.select(window.__app.layers.layers[0].id)")
    btn = js("return [...document.querySelectorAll('#layerList button')].some(b => b.textContent.includes('Edit outline'))")
    js("[...document.querySelectorAll('#layerList button')].find(b => b.textContent.includes('Edit outline')).click()")
    wait("return document.querySelectorAll('.wz-cand').length > 1"); time.sleep(1)
    print("layer card has Edit outline:", btn, "| reopened:",
          js("const w = window.__app.wizard; return [document.querySelector('.wz-cand.on .wz-cbody b').textContent, document.querySelector('.wz-use').textContent]"))
    js("document.querySelector('.wz-cancel').click()")

    # save -> reload -> open: the layer picture comes back (Edit outline still available)
    js("""window.__saved = null; const orig = URL.createObjectURL;
      URL.createObjectURL = (b) => { b.text().then((t) => { window.__saved = t; }); return orig(b); };""")
    js("document.getElementById('saveBtn').click()")
    saved = wait("return window.__saved")
    proj = json.loads(saved)
    path = Path(OUT) / "picklayers.a3d.json"
    path.write_text(saved, encoding="utf-8")
    part = proj["parts"][0]["classic"] if "parts" in proj else proj  # a v3 file keeps the quick part under parts[].classic
    print("saved: layer_pictures", list(part.get("layer_pictures", {}).keys()), "| objects", [o["name"] for o in part["model"]["objects"]])
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "projectInput").send_keys(str(path.resolve()))
    wait("return window.__app.state.solution && window.__app.state.solution.mesh"); settle()
    print(f"reloaded: volume {js('return window.__app.state.solution.volume'):.1f} (was {vol1:.1f}), can edit layer outline:",
          js("return window.__app.layers.canEditOutline(window.__app.layers.layers[0])"))
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
