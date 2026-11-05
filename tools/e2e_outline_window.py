"""The outline window docked or floating (headless Edge, REAL mouse drags): it opens docked over the app's work area (the
top bar stays usable and on top), ⧉ floats it, its title moves it and its corner / edges resize it (the picture fits
the new size, the candidate list and the side panel reflow, OK / Cancel stay in sight), the choice and the size are
remembered for the next picture, ▣ docks it again; the ✨ AI chat opens beside it (not over it), docked or floating.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_outline_window.py http://127.0.0.1:5199 <abs path to pernicek.png> <screenshot dir>
Saves win_docked.png, win_floating.png, win_floating_resized.png, win_chat.png. Exits 1 on a failed check or a
console error.
"""
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

URL, IMG, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
fails = []


def check(ok, what):
    print("OK  " if ok else "FAIL", what)
    if not ok:
        fails.append(what)


def wait(js, t=60):
    end = time.time() + t
    while time.time() < end:
        v = d.execute_script(js)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(js)


def rect(sel):
    return d.execute_script(f"const r = document.querySelector('{sel}')?.getBoundingClientRect(); return r && {{x: r.left, y: r.top, w: r.width, h: r.height, r: r.right, b: r.bottom}}")


def open_picture():
    d.find_element(By.ID, "imgInput").send_keys(IMG)
    wait("return document.querySelectorAll('.wz-cand').length > 0 && document.querySelector('.wz-busy').hidden")
    time.sleep(0.5)


def drag(x, y, dx, dy):
    a = ActionChains(d)
    a.move_by_offset(0, 0)
    a.w3c_actions.pointer_action.move_to_location(int(x), int(y))
    a.w3c_actions.pointer_action.pointer_down()
    for k in range(1, 9):
        a.w3c_actions.pointer_action.move_to_location(int(x + dx * k / 8), int(y + dy * k / 8))
    a.w3c_actions.pointer_action.pointer_up()
    a.perform()
    time.sleep(0.4)


def stage_fits():
    """The picture box fits inside the stage (zoom 100 %) and touches two of its sides."""
    s, i = rect(".wz-stage"), rect(".wz-stage img")
    inside = i["x"] >= s["x"] - 1 and i["y"] >= s["y"] - 1 and i["r"] <= s["r"] + 1 and i["b"] <= s["b"] + 1
    snug = abs(i["w"] - (s["w"] - 16)) < 2 or abs(i["h"] - (s["h"] - 16)) < 2
    return inside and snug


try:
    d.get(URL)
    wait("return !!window.__app")
    d.execute_script("localStorage.removeItem('a3d.outlineWindow'); localStorage.removeItem('a3d.box.outline-window')")

    # docked: fills the work area under the top bar, the top bar on top (its menus usable)
    open_picture()
    lay, root, top = rect(".layout"), rect(".wizard"), rect(".topbar")
    check(d.execute_script("return document.querySelector('.wizard').classList.contains('docked')"), "opens docked")
    check(abs(root["y"] - lay["y"]) < 2 and abs(root["h"] - lay["h"]) < 2 and abs(root["w"] - lay["w"]) < 2,
          f"docked fills the work area {lay} ~ {root}")
    check(root["y"] >= top["b"] - 1, "the top bar is not covered")
    el = d.execute_script("const r = document.getElementById('aiBtn').getBoundingClientRect(); return document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2)?.closest('#aiBtn') ? 1 : 0")
    check(el == 1, "the top bar's ✨ AI button can be clicked")
    check(stage_fits(), "the picture fits the stage (docked)")
    d.save_screenshot(f"{OUT}/win_docked.png")

    # ✨ AI from the top bar: the chat beside the docked window, the window narrower, not covered
    d.find_element(By.ID, "aiBtn").click()
    time.sleep(0.6)
    chat = rect("#aiDrawer")
    root = rect(".wizard")
    check(chat and chat["w"] > 200 and root["r"] <= chat["x"] + 1, f"the chat opens beside the window ({root['r']:.0f} <= {chat['x']:.0f})")
    check(d.execute_script("return !!document.querySelector('#aiDrawer #tab-ai')"), "the chat is in the drawer while the window is open")
    time.sleep(0.4)
    check(stage_fits(), "the picture fits the narrower stage")
    d.save_screenshot(f"{OUT}/win_chat.png")
    d.find_element(By.ID, "aiBtn").click()
    time.sleep(0.5)
    check(d.execute_script("return document.getElementById('aiDrawer').hidden"), "✨ AI again closes the chat")

    # ⧉ floating: a window inside the work area, the app behind it reachable
    d.find_element(By.CSS_SELECTOR, ".wz-dock").click()
    time.sleep(0.5)
    check(d.execute_script("return document.querySelector('.wizard').classList.contains('floating')"), "⧉ floats it")
    box = rect(".wz-box")
    lay = rect(".layout")
    check(box["w"] < lay["w"] - 10 and box["x"] >= lay["x"] - 1 and box["b"] <= lay["b"] + 1, f"a window inside the work area {box}")
    check(stage_fits(), "the picture fits the stage (floating)")
    d.save_screenshot(f"{OUT}/win_floating.png")

    # resized by the bottom-right corner, moved by its title, then resized by the left edge
    drag(box["r"] - 3, box["b"] - 3, -420, -260)
    b2 = rect(".wz-box")
    check(abs(b2["w"] - (box["w"] - 420)) < 4 and abs(b2["h"] - (box["h"] - 260)) < 4, f"corner resize {box['w']:.0f}x{box['h']:.0f} -> {b2['w']:.0f}x{b2['h']:.0f}")
    head = rect(".wz-head")
    drag(head["x"] + 140, head["y"] + head["h"] / 2, 120, 60)
    b3 = rect(".wz-box")
    check(abs(b3["x"] - b2["x"] - 120) < 4 and abs(b3["y"] - b2["y"] - 60) < 4, f"dragged by the title (+120, +60): {b2['x']:.0f},{b2['y']:.0f} -> {b3['x']:.0f},{b3['y']:.0f}")
    drag(b3["x"] + 2, b3["y"] + b3["h"] / 2, 60, 0)
    b4 = rect(".wz-box")
    check(abs(b4["x"] - b3["x"] - 60) < 4 and abs(b4["r"] - b3["r"]) < 3, "left edge resize: the right side stays")
    time.sleep(0.4)
    check(stage_fits(), "the picture fits the smaller stage")
    side, use = rect(".wz-side"), rect(".wz-use")
    check(side["b"] <= b4["b"] + 1 and side["r"] <= b4["r"] + 1, "the side panel stays inside the window")
    check(use["b"] <= side["b"] + 1 and use["y"] >= side["y"], "Use this outline stays in sight (the side panel scrolls)")
    check(d.execute_script("const s = document.querySelector('.wz-side'); return s.scrollHeight > s.clientHeight"), "the side panel scrolls")
    d.save_screenshot(f"{OUT}/win_floating_resized.png")

    # ✨ AI while floating: the window stays inside the area left of the chat
    d.find_element(By.ID, "aiBtn").click()
    time.sleep(0.6)
    chat, b5 = rect("#aiDrawer"), rect(".wz-box")
    check(b5["r"] <= chat["x"] + 1, "floating: the window is pulled left of the chat")
    d.find_element(By.ID, "aiBtn").click()
    time.sleep(0.4)

    # remembered: the next picture opens floating, the same size
    d.find_element(By.CSS_SELECTOR, ".wz-cancel").click()
    wait("return !document.querySelector('.wizard')")
    check(not d.execute_script("return document.body.classList.contains('wz-open')"), "closed: no wz-open left")
    open_picture()
    b6 = rect(".wz-box")
    check(d.execute_script("return document.querySelector('.wizard').classList.contains('floating')"), "the next picture opens floating")
    check(abs(b6["w"] - b4["w"]) < 4 and abs(b6["h"] - b4["h"]) < 4, f"…the same size ({b4['w']:.0f}x{b4['h']:.0f} -> {b6['w']:.0f}x{b6['h']:.0f})")

    # keys typed in a field are the field's (the window's Space / + / − / Backspace keys stay out of the chat)
    d.find_element(By.ID, "aiBtn").click()
    time.sleep(0.4)
    ta = d.find_element(By.CSS_SELECTOR, "#aiDrawer textarea")
    ta.click()
    ta.send_keys("a + b - 0")
    check(ta.get_attribute("value") == "a + b - 0", f"typing in the chat beside the window ({ta.get_attribute('value')!r})")
    check(d.execute_script("return window.__app.wizard.zoom") == 1, "…does not zoom the picture")
    ta.clear()
    d.find_element(By.ID, "aiBtn").click()
    time.sleep(0.3)

    # ▣ docks it again (remembered)
    d.find_element(By.CSS_SELECTOR, ".wz-dock").click()
    time.sleep(0.4)
    lay, root = rect(".layout"), rect(".wz-box")
    check(abs(root["w"] - lay["w"]) < 2 and abs(root["h"] - lay["h"]) < 2, "▣ docks it again")
    check(d.execute_script("return localStorage.getItem('a3d.outlineWindow')") == "dock", "the choice is remembered")
    check(stage_fits(), "the picture fits the stage (docked again)")

    # a part from it still works
    d.execute_script("""const i = document.querySelector('.wz-w'); i.value = '80'; i.dispatchEvent(new Event('input'));""")
    d.find_element(By.CSS_SELECTOR, ".wz-use").click()
    wait("return window.__app.state.solution && window.__app.state.solution.mesh")
    check(d.execute_script("return !!document.querySelector('#tab-ai') && !document.querySelector('#aiDrawer #tab-ai')"),
          "after the window closes the chat is back in the quick part's panel")
finally:
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    d.quit()
if fails or errs:
    print("FAILED:", fails)
    sys.exit(1)
print("all OK")
