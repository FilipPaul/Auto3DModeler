"""The AI teaching the user with gui_highlight, in headless Edge: a 3D model -> a pulsing ring around ✏ Sketch with
the tip below it (the rest dimmed) -> a click elsewhere: it stays -> the user's real click on ✏ Sketch: the sketch
starts (nothing blocked) and the ring goes; the next call says "the user clicked it" -> Escape closes a tip (the
sketch stays open) -> wait: true through the real bridge (/api/agent/call): answers "clicked" after the user's click ->
wait with a short timeout: still shown, then clear -> a spot of the view (at), clicked there -> in an assembly, over a
floating box -> Czech: the ✕'s tooltip -> no control / unknown control / no text: refused.

  PYTHONIOENCODING=utf-8 py tools/e2e_ai_teach.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import threading
import time
import urllib.request
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

URL, OUT = sys.argv[1], Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
H = "window.__app.agentHandlers"
fails = []


def check(what, ok):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails.append(what)


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


def bridge(tool_name, **args):
    """A tool call as Claude Code's MCP server makes it: through the app server to this page and back."""
    req = urllib.request.Request(f"{URL}/api/agent/call", json.dumps({"tool": tool_name, "args": args}).encode(), {"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=180).read())
    return ("ERROR " if r.get("isError") else "") + r["content"][0]["text"]


def ring():
    """The ring and tip on screen: {ring: rect, tip: rect, text, step, spot} or None."""
    return js("""const r = document.querySelector('.teach-ring'), t = document.querySelector('.teach-tip');
      if (!r) return null; const a = r.getBoundingClientRect(), b = t.getBoundingClientRect();
      return {ring: [a.left, a.top, a.right, a.bottom], tip: [b.left, b.top, b.right, b.bottom], hidden: r.hidden, spot: r.classList.contains('spot'),
        text: t.querySelector('.teach-text').textContent, step: t.querySelector('.teach-step')?.textContent || '', n: document.querySelectorAll('.teach-ring').length,
        shade: getComputedStyle(r).boxShadow, pe: getComputedStyle(r).pointerEvents};""")


def control(label):
    """A control on screen by its label (part of it): its element."""
    return js("""const want = arguments[0].toLowerCase();
      return [...document.querySelectorAll('button')].find((b) => b.offsetParent && b.textContent.toLowerCase().includes(want) && !b.closest('#aiDrawer, .teach-tip')) || null;""", label)


def around(rg, el):
    r = js("const r = arguments[0].getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom];", el)
    return rg and rg["ring"][0] <= r[0] and rg["ring"][1] <= r[1] and rg["ring"][2] >= r[2] and rg["ring"][3] >= r[3]


try:
    d.get(URL)
    wait("return !!window.__app")
    time.sleep(1.5)  # (the page starts long-polling for the AI's calls)
    call("new_model", name="Teach")
    wait("return window.__app.state.workspace === 'model'")
    time.sleep(0.5)

    # 1. a ring around ✏ Sketch with the tip below it, the rest dimmed; nothing takes the clicks
    r = call("gui_highlight", control="Sketch", text="Click ✏ Sketch to start drawing on a plane.", step="1/3")
    print("gui_highlight:", r)
    sk = control("Sketch")
    rg = ring()
    check("a ring around ✏ Sketch", around(rg, sk))
    check("the tip with the text and the step", rg and rg["text"].startswith("Click ✏ Sketch") and rg["step"] == "1/3")
    check("the tip next to the control", rg and rg["tip"][1] >= rg["ring"][3] - 1)
    check("the rest dimmed, nothing blocked", rg and "9999px" in rg["shade"] and rg["pe"] == "none")
    time.sleep(0.4)  # (the tip slides in)
    d.save_screenshot(str(OUT / "teach_1_sketch.png"))
    # a click somewhere else: the tip stays
    ActionChains(d).move_by_offset(800, 600).click().perform()
    ActionChains(d).move_by_offset(-800, -600).perform()
    time.sleep(0.3)
    check("a click elsewhere: the tip stays", ring() is not None)
    # the user's real click on ✏ Sketch: it works (the sketch starts) and the ring goes
    sk.click()
    time.sleep(0.6)
    check("clicked: the ring is gone", ring() is None)
    mode = js("return window.__app.modeler.mode")
    print("  the modeller after the click:", mode)
    check("clicked: the control did its job (not blocked)", mode in ("plane", "sketch"))

    # 2. the next tip says what happened to the one before; Escape closes it (and is not passed on)
    plane = js("return [...document.querySelectorAll('button')].find((b) => b.offsetParent && /^(Top|XY)/.test(b.textContent.trim()))?.textContent.trim() || null")
    print("  a plane button:", plane)
    r = call("gui_highlight", control=plane or "Cancel", text="Now pick the Top plane.", step="2/3")
    print("gui_highlight:", r)
    check("the next call says the user clicked the one before", "the user clicked it" in r)
    time.sleep(0.4)  # (the tip slides in)
    d.save_screenshot(str(OUT / "teach_2_plane.png"))
    mode0 = js("return window.__app.modeler.mode")
    ActionChains(d).send_keys(Keys.ESCAPE).perform()
    time.sleep(0.3)
    check("Escape: the tip is gone", ring() is None)
    check("Escape went to the tip only (the sketch's own step stays)", js("return window.__app.modeler.mode") == mode0)
    r = call("gui_highlight", control=plane or "Cancel", text="Pick the Top plane.")
    check("the next call says the user closed it", "closed the tip" in r)
    r = call("gui_highlight", control="Cancel", text="Or cancel.")
    check("a new tip replaces the old one (one ring)", ring()["n"] == 1 and "replaced by the next tip" in r)
    call("gui_highlight", clear=True)
    check("clear: true removes it", ring() is None)

    # 3. wait: true through the real bridge: it answers when the user has clicked
    out = {}
    th = threading.Thread(target=lambda: out.update(r=bridge("gui_highlight", control=plane or "Cancel", text="Click here.", wait=True, timeout=30)))
    t0 = time.time()
    th.start()
    wait("return !!document.querySelector('.teach-ring')", 20)
    time.sleep(1.0)
    check("wait: no answer before the click", th.is_alive())
    control(plane or "Cancel").click()
    th.join(20)
    print(f"wait: true -> {out.get('r')} ({time.time() - t0:.1f} s)")
    check("wait: true answers after the user's click", "the user clicked" in out.get("r", ""))
    # a short timeout: still shown, then cleared
    r = bridge("gui_highlight", control="Finish sketch" if control("Finish sketch") else "Cancel", text="Finish the sketch.", wait=True, timeout=1)
    print("wait 1 s:", r)
    check("timeout: says so, the tip stays", "has not clicked" in r and ring() is not None)
    bridge("gui_highlight", clear=True)

    # 4. a spot of the view (at): a round ring there; a real click at it counts
    r = call("gui_highlight", at=[0.5, 0.5], text="Click the middle of the view.")
    print("gui_highlight at:", r)
    rg = ring()
    v = js("const r = document.querySelector('#modelViewport').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2];")
    cx, cy = (rg["ring"][0] + rg["ring"][2]) / 2, (rg["ring"][1] + rg["ring"][3]) / 2
    check("at: a round ring at the view's middle", rg["spot"] and abs(cx - v[0]) < 2 and abs(cy - v[1]) < 2)
    time.sleep(0.4)  # (the tip slides in)
    d.save_screenshot(str(OUT / "teach_3_spot.png"))
    vp = d.find_element(By.CSS_SELECTOR, "#modelViewport")
    ActionChains(d).move_to_element(vp).click().perform()
    time.sleep(0.3)
    check("at: a click there closes it", ring() is None)

    # 5. refused: nothing to point at, an unknown control, no text
    for args in ({"text": "x"}, {"control": "No such button at all", "text": "x"}, {"control": "Cancel"}):
        r = call("gui_highlight", **args)
        print("refused:", r[:110])
        check(f"refused {list(args)}", r.startswith("ERROR"))

    # 6. an assembly (another workspace) with a floating box open; Czech
    call("gui_action", key="Escape")
    call("new_model", name="Pin")
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 5}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("new_assembly", name="Teach box")
    wait("return window.__app.state.workspace === 'assembly'")
    time.sleep(0.5)
    js("document.getElementById('langBtn').click()")
    time.sleep(0.5)
    ins = js("return [...document.querySelectorAll('#assemblyWs button, button')].find((b) => b.offsetParent && /Insert part|Vložit díl/.test(b.textContent))?.textContent.trim() || null")
    print("  the insert button:", ins)
    r = call("gui_highlight", control=ins or "Vložit", text="Klikněte sem a vložte díl.", step="1/2")
    print("gui_highlight (assembly, Czech):", r)
    rg = ring()
    check("assembly: a ring around ＋ Insert part", rg and around(rg, control(ins or "Vložit")))
    check("Czech: the ✕ says Zavřít tip (Esc)", js("return document.querySelector('.teach-x').title") == "Zavřít tip (Esc)")
    check("the tip's own text is not translated", ring()["text"] == "Klikněte sem a vložte díl.")
    z = js("return [...document.querySelectorAll('.fb-box, .ai-drawer, .menu-list')].map((e) => +getComputedStyle(e).zIndex || 0)")
    check("above floating boxes and menus", all(int(js("return +getComputedStyle(document.querySelector('.teach-ring')).zIndex")) > x for x in z))
    time.sleep(0.4)  # (the tip slides in)
    d.save_screenshot(str(OUT / "teach_4_assembly_cs.png"))
    control(ins or "Vložit").click()
    time.sleep(0.4)
    check("assembly: clicked, gone", ring() is None)
    js("document.getElementById('langBtn').click()")
finally:
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    d.quit()
print(f"\n{len(fails)} failed" + (": " + "; ".join(fails) if fails else ""))
sys.exit(1 if fails else 0)
