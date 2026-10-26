"""One Part tab for every source, dimensions between points, measuring, CAD / 3D imports — in headless Edge
with real mouse input.

PDF sample: 2D shape + added post in the Part tab, measure -> keep as (reference) dimension;
DXF: real size, cookie cutter; STL: sliced part, a hole added, a dimension that scales the part,
project round trip with the 3D file; picture: outline-editor and enlarged-drawing 2D measuring.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_unified.py http://127.0.0.1:5199 <abs path to pernicek.png> <out dir>
"""
import io
import json
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

URL, IMG, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script


def wait(script, t=40):
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


def loaded():
    wait("return window.__app.state.solution && window.__app.state.solution.mesh")
    settle()


FIND = """const [z, up] = arguments, v = window.__app.viewer, r = v.renderer.domElement.getBoundingClientRect();
for (let gy = 0.12; gy < 0.92; gy += 0.01) for (let gx = 0.08; gx < 0.92; gx += 0.01) {
  const cx = Math.round(r.left + gx * r.width), cy = Math.round(r.top + gy * r.height), h = v.pickSurface(cx, cy);
  if (h && (z === null || Math.abs(h.z - z) < 1e-6) && h.snap === (up ? 'top face' : 'bottom face'))
    return [cx - r.left - r.width / 2, cy - r.top - r.height / 2, h];
}
return null;"""
CORNER = """const v = window.__app.viewer, p = v.mesh.geometry.attributes.position, r = v.renderer.domElement.getBoundingClientRect();
const skip = arguments[0] || [];
for (let i = 0; i < p.count; i++) {
  const s = v.toScreen(p.getX(i), p.getY(i), p.getZ(i)), x = Math.round(s.x + 2), y = Math.round(s.y + 1);
  if (x < r.left + 20 || x > r.right - 20 || y < r.top + 60 || y > r.bottom - 40) continue;
  const h = v.pickSurface(x, y);
  if (h && h.snap === 'corner' && !skip.some((q) => Math.hypot(q[0] - h.x, q[1] - h.y, q[2] - h.z) < 1)) return [x - r.left - r.width / 2, y - r.top - r.height / 2, h];
}
return null;"""


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#viewport canvas")


def click_canvas(dx, dy):
    ActionChains(d, duration=40).move_to_element_with_offset(canvas(), int(dx), int(dy)).click().perform()


def part_btn(text):
    js("[...document.querySelectorAll('#rtab-outline button')].find(b => b.textContent.includes(arguments[0])).click()", text)


def measure_two_corners():
    a = js(CORNER, [])
    click_canvas(a[0], a[1]); time.sleep(0.3)
    b = js(CORNER, [[a[2]["x"], a[2]["y"], a[2]["z"]]])
    click_canvas(b[0], b[1]); time.sleep(0.4)
    return a[2], b[2]


def upload(input_id, path):
    d.find_element(By.ID, input_id).send_keys(str(path))


try:
    d.get(URL)
    wait("return !!window.__app")

    # ---- PDF sample: the Part tab exists, 2D shape + added post, measure -> keep (reference) dimension
    js("document.getElementById('sampleBtn').click()"); loaded()
    print("PDF: Part tab visible:", js("return !document.querySelector('.rtab[data-rtab=outline]').hidden"),
          "| Part tab title:", js("return document.querySelector('.rtab[data-rtab=outline]').textContent"))
    js("document.querySelector('.rtab[data-rtab=outline]').click()")
    vol0 = js("return window.__app.state.solution.volume")
    part_btn("Hole"); time.sleep(0.4)
    spot = js(FIND, 1, True); click_canvas(spot[0], spot[1]); settle()
    vol1 = js("return window.__app.state.solution.volume")
    js("[...document.querySelectorAll('#rtab-outline .row-actions button')].find(b => b.dataset.a === 'rect' && b.closest('div').textContent.includes('Bar')).click()"); time.sleep(0.4)
    spot = js(FIND, 1, True); click_canvas(spot[0], spot[1]); settle()
    vol2 = js("return window.__app.state.solution.volume")
    print(f"PDF: hole cut {vol0:.2f} -> {vol1:.2f}, box added on top -> {vol2:.2f} cm³; z_range {js('return window.__app.state.solution.z_range')}")
    js("document.getElementById('measureBtn').click()")
    a, b = measure_two_corners()
    print("PDF measure:", js("return document.querySelector('#measureBox .mb-rows').innerText.replace(/\\n/g, ' ')"))
    js("document.querySelector('#measureBox [data-axis=d]').click()"); time.sleep(0.5)
    pd = js("return window.__app.state.model.params.filter(p => p.kind === 'point').map(p => [p.name, p.role, +p.value.toFixed(3)])")
    print("PDF kept dimension:", pd, "| label in 3D:", js("return [...document.querySelectorAll('.dim-label')].some(e => e.textContent.includes('('))"))
    d.save_screenshot(f"{OUT}/u1_pdf.png")

    # ---- DXF: real size, cookie cutter
    import ezdxf
    doc = ezdxf.new(); doc.header["$INSUNITS"] = 4; msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (80, 0), (80, 50), (40, 70), (0, 50)], close=True)
    msp.add_circle((40, 25), 8)
    dxf = Path(OUT) / "house.dxf"; doc.saveas(dxf)
    upload("cadInput", dxf.resolve()); loaded()
    m = js("const s = window.__app.state; return [s.model.kind, s.model.outline.space, s.values.width, s.values.height, s.solution.z_range]")
    print("DXF:", m)
    js("document.querySelector('.ol-preset [data-p=cutter]').click()"); settle()
    print("DXF cutter:", js("return [window.__app.state.solution.ok, window.__app.state.solution.z_range, window.__app.state.solution.objects.map(o => o.name)]"),
          "| Edit outline hidden (no picture):", js("return document.getElementById('editOutlineBtn').hidden"))
    d.save_screenshot(f"{OUT}/u2_dxf.png")
    # lightbox measure across the DXF (80 mm wide drawing, padded)
    js("document.querySelector('.tab[data-tab=drawing]').click()"); time.sleep(0.3)
    js("document.getElementById('drawingEnlarge').click()"); time.sleep(0.5)
    print("DXF lightbox measure button:", js("return !!document.querySelector('.lb-mbtn')"))
    ActionChains(d).send_keys("").perform(); time.sleep(0.2)

    # ---- STL: sliced part, hole added on top face, dimension scales it, project round trip
    from auto3d.export import build_solid, to_stl
    from auto3d.sketch import build_model
    from auto3d.solver import solve
    model, _, _ = build_model((ROOT / "initial draft.pdf").read_bytes(), 0)
    stl = Path(OUT) / "sample.stl"; stl.write_bytes(to_stl(build_solid(solve(model), model["unit"]), model["unit"], "sample"))
    upload("cadInput", stl.resolve()); loaded()
    s0 = js("const s = window.__app.state; return [s.model.kind, s.solution.values.size_x, s.solution.values.size_y, s.solution.values.size_z, s.solution.volume]")
    print("STL:", s0)
    js("[...document.querySelectorAll('#rtab-outline .row-actions button')].find(b => b.dataset.a === 'circle').click()"); time.sleep(0.4)
    spot = js(FIND, 10, True); click_canvas(spot[0], spot[1]); settle()
    # make it a through hole: subtract from 0..10
    js("""const o = window.__app.state.model.extras.at(-1); Object.assign(o, {op: 'subtract', z0: 0, z1: 10, w: 8, h: 8});
      window.__app.outlinePanel.changed(true);"""); settle()
    print("STL hole:", js("return [window.__app.state.solution.volume, window.__app.state.model.extras.map(o => o.name + ':' + o.op)]"))
    # ＋ Dimension (point to point) along X between two corners, then type 2x its value -> part scales 200 %
    js("document.getElementById('dimToolBtn').click()")
    a, b = measure_two_corners()
    js("document.querySelector('#measureBox [data-axis=x]').click()"); time.sleep(0.4)
    ActionChains(d).send_keys("").perform(); time.sleep(0.2)  # stop adding more
    pid, val = js("const p = window.__app.state.model.params.find(p => p.kind === 'point'); return [p.id, p.value]")
    js(f"""const i = document.querySelector('.param[data-param="{pid}"] input'); i.value = '{val * 2}'; i.dispatchEvent(new Event('change'));""")
    settle()
    s1 = js("const s = window.__app.state; return [s.values.scale, s.solution.values.size_x, s.solution.volume, s.values[arguments[0]]]", pid)
    print(f"STL dimension {val:.2f} -> {val * 2:.2f}: scale {s1[0]} %, size_x {s1[1]:.1f}, volume {s1[2]:.0f} (x{s1[2] / js('return 1') / 1:.0f}), dim now {s1[3]:.2f}")
    d.save_screenshot(f"{OUT}/u3_stl.png")
    js("""window.__saved = null; window.showSaveFilePicker = async (o) => ({ name: o.suggestedName,
      createWritable: async () => ({ write: async (b) => { window.__saved = await b.text(); }, close: async () => {} }) });""")
    js("document.getElementById('saveBtn').click()")
    saved = wait("return window.__saved")
    proj = (lambda p: next(q for q in p["parts"] if q["id"] == p["active"]["part"])["classic"])(json.loads(saved))  # project v3: the part on screen
    path = Path(OUT) / "stl_project.a3d.json"; path.write_text(saved, encoding="utf-8")
    print(f"STL project: {len(saved) // 1024} kB, import_file {bool(proj.get('import_file'))}, point dims {len(proj['model']['point_dims'])}")
    d.get(URL); wait("return !!window.__app")
    upload("projectInput", path.resolve()); loaded()
    print("STL project reopened:", js("const s = window.__app.state; return [s.model.kind, +s.solution.volume.toFixed(0), s.values.scale, s.model.point_dims.length]"))

    # ---- picture: outline editor 2D measure, enlarged drawing measure in mm
    upload("imgInput", IMG)
    wait("return document.querySelectorAll('.wz-cand').length > 0"); time.sleep(1)
    js("const w = document.querySelector('.wz-w'); w.value = '120'; w.dispatchEvent(new Event('input'))")
    js("document.querySelector('[data-tool=measure]').click()")
    st = d.find_element(By.CSS_SELECTOR, ".wz-stage")
    pos = lambda fx, fy: js("""const st = document.querySelector('.wz-stage').getBoundingClientRect(), r = document.querySelector('.wz-stage svg').getBoundingClientRect();
      return [Math.round(r.left + arguments[0] * r.width - st.left - st.width / 2), Math.round(r.top + arguments[1] * r.height - st.top - st.height / 2)]""", fx, fy)
    for fx in (0.1, 0.9):
        ActionChains(d, duration=30).move_to_element_with_offset(st, *pos(fx, 0.5)).click().perform(); time.sleep(0.2)
    print("editor measure:", js("return document.querySelector('.wz-stage svg text')?.textContent"))
    d.save_screenshot(f"{OUT}/u4_wizard_measure.png")
    d.find_element(By.CSS_SELECTOR, ".wz-use").click(); loaded()
    js("document.querySelector('.tab[data-tab=drawing]').click()"); time.sleep(0.3)
    js("document.getElementById('drawingEnlarge').click()"); time.sleep(0.5)
    js("document.querySelector('.lb-mbtn').click()")
    lst = d.find_element(By.CSS_SELECTOR, ".lb-stage")
    lpos = lambda fx: js("""const st = document.querySelector('.lb-stage').getBoundingClientRect(), r = document.querySelector('.lb-content').getBoundingClientRect();
      return [Math.round(r.left + arguments[0] * r.width - st.left - st.width / 2), 0]""", fx)
    for fx in (0.0, 1.0):
        ActionChains(d, duration=30).move_to_element_with_offset(lst, *lpos(fx)).click().perform(); time.sleep(0.2)
    print("lightbox measure (full picture width):", js("return document.querySelector('.lb-measure').textContent"),
          "| picture width in mm:", js("const s = window.__app.state, o = s.model.outline, xs = o.polygons.flatMap(p => p[0].map(q => q[0])); return +(o.img_w * s.values.width / (Math.max(...xs) - Math.min(...xs))).toFixed(2)"))
    d.save_screenshot(f"{OUT}/u5_lightbox_measure.png")
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
