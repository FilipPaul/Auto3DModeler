"""Drive the outline tools in headless Edge: box / 'not this' hints, combining candidates, brush and
polygon / lasso editing (add, remove, cut out), zoom and pan, outline clean-up, text and hole shapes.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_outline_tools.py http://127.0.0.1:5199 <abs path to pernicek.png> <screenshot dir>
"""
import math
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.actions.wheel_input import ScrollOrigin
from selenium.webdriver.common.by import By

URL, IMG, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)


def wait(js, t=30):
    end = time.time() + t
    while time.time() < end:
        v = d.execute_script(js)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(js)


def idle():
    """Wait for detection / mask tracing to finish."""
    time.sleep(0.4)
    wait("return document.querySelector('.wz-busy').hidden")
    time.sleep(0.5)


# REAL mouse input (trusted events, like a user): native image drag, pointerup.detail = 0 etc.
# behave as in the browser. Positions are picture fractions (fx, fy).
def at(fx, fy):
    """Offset from the stage centre (CSS px) of a picture point, for ActionChains."""
    return d.execute_script("""const [fx, fy] = arguments, st = document.querySelector('.wz-stage').getBoundingClientRect(),
        r = document.querySelector('.wz-stage svg').getBoundingClientRect();
      return [Math.round(r.left + fx * r.width - st.left - st.width / 2), Math.round(r.top + fy * r.height - st.top - st.height / 2)];""", fx, fy)


def stage():
    return d.find_element(By.CSS_SELECTOR, ".wz-stage")


def drag(points):
    a = ActionChains(d, duration=30).move_to_element_with_offset(stage(), *at(*points[0])).click_and_hold()
    for p in points[1:]:
        a = a.move_to_element_with_offset(stage(), *at(*p))
    a.release().perform()


def click(fx, fy):
    ActionChains(d, duration=30).move_to_element_with_offset(stage(), *at(fx, fy)).click().perform()


def dblclick(fx, fy):
    ActionChains(d, duration=30).move_to_element_with_offset(stage(), *at(fx, fy)).double_click().perform()


def wheel(fx, fy, dy):
    x, y = at(fx, fy)
    ActionChains(d).scroll_from_origin(ScrollOrigin.from_element(stage(), x, y), 0, dy).perform()


def mode(name):
    d.execute_script(f"document.querySelector('[data-mode=\"{name}\"]').click()")


IMG_PT = """const st = document.querySelector('.wz-stage').getBoundingClientRect(), w = window.__app.wizard;
  return w.imgPoint({clientX: st.left + st.width / 2 + arguments[0], clientY: st.top + st.height / 2 + arguments[1]})"""


def tool(name):
    d.execute_script(f"document.querySelector('[data-tool=\"{name}\"]').click()")


def cands():
    return d.execute_script("return [...document.querySelectorAll('.wz-cand')].map(r => r.querySelector('.wz-cbody b').textContent + ' ' + (r.querySelector('.wz-conf')?.textContent || ''))")


def area():
    return d.execute_script("const w = window.__app.wizard; return w.list()[w.sel].area")


try:
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "imgInput").send_keys(IMG)
    wait("return document.querySelectorAll('.wz-cand').length > 0")
    idle()
    print("auto:", cands()[:4])

    # 0. the selection survives re-detection with other settings (smoothing, candidate count)
    d.execute_script("document.querySelectorAll('.wz-cand')[1].click()")
    before = d.execute_script("const w = window.__app.wizard; return [w.sel, w.list()[w.sel].area]")
    for key, val in (("smoothing", "3"), ("count", "8")):
        d.execute_script(f"""const i = document.querySelector('[data-h={key}]'); i.value = '{val}';
          i.dispatchEvent(new Event('change'));""")
        idle()
        after = d.execute_script("const w = window.__app.wizard; return [w.sel, w.list()[w.sel].area]")
        print(f"selected #2, then {key}={val}: before {before} after {after}",
              "OK" if after[0] == before[0] and abs(after[1] - before[1]) < 0.02 else "LOST SELECTION")
    d.execute_script("""for (const [k, v] of [['smoothing', '1'], ['count', '6']]) {
      const i = document.querySelector(`[data-h=${k}]`); i.value = v; i.dispatchEvent(new Event('change')); }""")
    idle()
    d.execute_script("document.querySelectorAll('.wz-cand')[0].click()")

    # 1. 'not this' on the cookie body -> whole-cookie candidates disappear
    tool("notthis"); click(0.5, 0.55); idle()
    print("not this on the body:", cands()[:4])
    d.execute_script("document.querySelector('.wz-clear').click()"); idle()

    # 2. box around the chimney only
    tool("box"); drag([(0.1, 0.08), (0.2, 0.3), (0.3, 0.45)]); idle()
    d.save_screenshot(f"{OUT}/t1_box.png")
    print("box around chimney:", cands()[:3], "area", area())
    d.execute_script("document.querySelector('.wz-clear').click()"); idle()
    tool("box")  # toggle off

    # 3. combine: start from #1, cut away candidate #3 (if any), then undo
    a0 = area()
    d.execute_script("document.querySelectorAll('.wz-cand')[2].querySelector('[data-a=sub]').click()"); idle()
    a1 = area()
    print("edit = #1 − #3:", cands()[0], f"area {a0} -> {a1}")
    d.execute_script("document.querySelector('.wz-undo').click()"); idle()
    print("after undo area:", area())

    # count native drags (the bug: dragging moved the picture instead of painting)
    d.execute_script("window.__drags = 0; document.addEventListener('dragstart', () => window.__drags++, true)")

    # 4. brush: paint a blob outside the cookie (top-left corner), then remove part of it
    tool("brush"); mode("add"); drag([(0.03, 0.03), (0.08, 0.05), (0.12, 0.08)]); idle()
    a2 = area()
    mode("remove"); drag([(0.1, 0.03), (0.12, 0.08)]); idle()
    print(f"brush add: area {a2}, after remove {area()}, pieces:",
          d.execute_script("const w = window.__app.wizard; return w.list()[0].polygons.length"),
          "| native drags:", d.execute_script("return window.__drags"))
    d.save_screenshot(f"{OUT}/t2_brush.png")
    d.execute_script("document.querySelector('.wz-undo').click()")
    d.execute_script("document.querySelector('.wz-undo').click()"); idle()

    # 5. cut out: polygon around the chimney, closed by clicking the first point -> only the chimney is left
    a_before = area()
    tool("poly"); mode("keep")
    corners = [(0.11, 0.07), (0.29, 0.07), (0.29, 0.40), (0.11, 0.40)]
    for p in corners:
        click(*p)
    d.save_screenshot(f"{OUT}/t3a_poly_open.png")
    click(*corners[0]); idle()
    print(f"cut out chimney (polygon, first-point close): area {a_before} -> {area()}")
    d.save_screenshot(f"{OUT}/t3b_cutout.png")
    d.execute_script("document.querySelector('.wz-undo').click()"); idle()

    # 6. remove with a polygon closed by DOUBLE-CLICK: the right half goes
    mode("remove")
    for p in [(0.5, 0.0), (1.0, 0.0), (1.0, 1.0)]:
        click(*p)
    dblclick(0.5, 1.0); idle()
    print(f"remove right half (polygon, double-click close): area {a_before} -> {area()}")
    d.execute_script("document.querySelector('.wz-undo').click()"); idle()

    # 7. lasso cut out: a freehand loop around the left wheel area
    tool("lasso"); mode("keep")
    loop = [(0.25 + 0.2 * math.cos(t / 12 * 2 * math.pi), 0.75 + 0.22 * math.sin(t / 12 * 2 * math.pi)) for t in range(13)]
    drag(loop); idle()
    print(f"lasso cut out: area {a_before} -> {area()} | native drags:", d.execute_script("return window.__drags"))
    d.execute_script("document.querySelector('.wz-undo').click()"); idle()

    # 8. zoom with the wheel around a point (it stays under the cursor), pan with a plain drag (no tool)
    off = at(0.2, 0.25)
    before_pt = d.execute_script(IMG_PT, *off)
    wheel(0.2, 0.25, -400); time.sleep(0.4)
    after_pt = d.execute_script(IMG_PT, *off)
    print(f"wheel zoom -> {d.execute_script('return window.__app.wizard.zoom'):.2f}; picture point under the cursor "
          f"{[round(v, 1) for v in before_pt]} -> {[round(v, 1) for v in after_pt]}")
    d.save_screenshot(f"{OUT}/t3c_zoom.png")
    # a precise polygon while zoomed: cut out the chimney top only
    tool("poly"); mode("keep")
    zc = [(0.12, 0.13), (0.28, 0.13), (0.28, 0.22), (0.12, 0.22)]  # inside the zoomed, visible part
    for p in zc:
        click(*p)
    click(*zc[0]); idle()
    print(f"zoomed cut out (chimney top): area -> {area()}")
    d.save_screenshot(f"{OUT}/t3d_zoom_cut.png")
    d.execute_script("document.querySelector('.wz-undo').click()"); idle()
    d.execute_script("document.querySelector('.wz-done').click()")  # no tool -> a drag pans
    sel0 = d.execute_script("return window.__app.wizard.sel")
    p0 = d.execute_script("return [...window.__app.wizard.pan]")
    ActionChains(d, duration=50).move_to_element_with_offset(stage(), 0, 0).click_and_hold().move_by_offset(120, 60).release().perform()
    time.sleep(0.3)
    print("pan by drag:", [round(v) for v in p0], "->", [round(v) for v in d.execute_script("return window.__app.wizard.pan")],
          "| selection kept:", d.execute_script("return window.__app.wizard.sel") == sel0)
    d.execute_script("document.querySelector('.wz-zoom-fit').click()")
    print("fit -> zoom", d.execute_script("return window.__app.wizard.zoom"))

    # 9. polygon from an empty outline: a triangle (double-click closes)
    d.execute_script("document.querySelector('.wz-edit-btn').click()")
    d.execute_script("document.querySelector('.wz-empty').click()"); time.sleep(0.6)  # switches to Polygon + Add
    for p in [(0.3, 0.3), (0.7, 0.3)]:
        click(*p)
    dblclick(0.5, 0.8)
    idle()
    tri = d.execute_script("const w = window.__app.wizard; const c = w.list()[0]; return [c.polygons.length, c.polygons[0][0].length, c.area]")
    print("polygon triangle: pieces, vertices, area =", tri)
    d.save_screenshot(f"{OUT}/t3_poly.png")

    # discard the edit, use candidate #1 as a solid shape
    d.execute_script("document.querySelector('.wz-cand.edited [data-a=drop]').click()"); idle()
    d.execute_script("document.querySelector('.wz-preset [data-p=solid]').click()")
    w = d.find_element(By.CSS_SELECTOR, ".wz-w"); w.clear(); w.send_keys("120")
    d.execute_script("document.querySelector('.wz-w').dispatchEvent(new Event('input'))")
    d.find_element(By.CSS_SELECTOR, ".wz-use").click()
    wait("return window.__app.state.solution && window.__app.state.solution.mesh")
    time.sleep(1)
    vol0 = d.execute_script("return window.__app.state.solution.volume")

    # 10. clean-up: round corners 3 mm, then keep largest
    d.execute_script("document.querySelector('details.ol-clean').open = true")
    d.execute_script("""const f = [...document.querySelectorAll('details.ol-clean .field')].find(r => r.textContent.includes('Round corners'));
      const i = f.querySelector('input'); i.value = '3'; i.dispatchEvent(new Event('input'));""")
    time.sleep(2)
    vol1 = d.execute_script("return window.__app.state.solution.volume")
    print(f"round corners 3 mm: volume {vol0:.0f} -> {vol1:.0f}")
    d.save_screenshot(f"{OUT}/t4_cleanup.png")

    # 11. hole + text (2D shape cut from the outline)
    d.execute_script("[...document.querySelectorAll('#rtab-outline button')].find(b => b.textContent.includes('Hole')).click()")
    time.sleep(1.5)
    vol2 = d.execute_script("return window.__app.state.solution.volume")
    d.execute_script("[...document.querySelectorAll('#rtab-outline button')].filter(b => b.textContent.includes('Text')).pop().click()")
    wait("return (window.__app.state.model.shapes || []).some(s => s.kind === 'poly')")
    d.execute_script("""const t = window.__app.state.model.shapes.find(s => s.kind === 'poly');
      t.op = 'subtract'; window.__app.outlinePanel.changed(true);""")
    d.execute_script("""const ta = document.querySelector('#rtab-outline .layer.open textarea'); ta.value = 'PERNÍK'; ta.dispatchEvent(new Event('change'));""")
    wait("return window.__app.state.model.shapes.find(s => s.kind === 'poly').w > 30")
    time.sleep(2)
    t = d.execute_script("const t = window.__app.state.model.shapes.find(s => s.kind === 'poly'); return [t.text, +t.w.toFixed(1), +t.h.toFixed(1), t.polygons.length]")
    vol3 = d.execute_script("return window.__app.state.solution.volume")
    print(f"hole: volume {vol1:.0f} -> {vol2:.0f}; text {t}: volume -> {vol3:.0f}")
    d.execute_script("document.querySelector('[data-view=front]').click()")
    time.sleep(1)
    d.save_screenshot(f"{OUT}/t5_text.png")

    # 12. 3D text object on a custom cookie cutter
    d.execute_script("document.querySelector('.ol-preset [data-p=cutter]').click()"); time.sleep(1.5)
    d.execute_script("[...document.querySelectorAll('#rtab-outline button')].find(b => b.textContent.startsWith('Edit as 3D')).click()"); time.sleep(1.5)
    d.execute_script("[...document.querySelectorAll('#rtab-outline .row-actions button')].find(b => b.dataset.a === 'text' && b.closest('div').textContent.includes('Bar')).click()")
    wait("return (window.__app.state.model.objects || []).some(o => o.source === 'poly')")
    time.sleep(2)
    s = d.execute_script("const s = window.__app.state.solution; return {ok: s.ok, objs: s.objects.map(o => o.name), z: s.z_range}")
    print("cutter + 3D text:", s)
    d.execute_script("document.querySelector('[data-view=iso]').click()")
    time.sleep(1)
    d.save_screenshot(f"{OUT}/t6_cutter_text.png")
finally:
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    d.quit()
