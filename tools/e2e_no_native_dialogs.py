"""No pop-up windows from the browser (the owner's rule): every question is asked inside the app, in Czech, in
headless Edge. The page's confirm / alert / prompt are replaced by recorders (a native one would also stop every
script here: UnexpectedAlertPresentException) and must stay unused throughout:
- moving a joined part by hand (typed X): the bar in the view's bottom-right corner "Posunutí rukou zruší jeho vazby"
  — Zpět keeps it, Esc keeps it, "Zrušit vazby a posunout" breaks them and moves it;
- deleting a step others need (the sketch under an extrude): the in-page yes / no — Zrušit keeps it, "Smazat je" deletes both;
- 🕘 Recent projects ✕ (forget a project): Zrušit keeps it, Zapomenout forgets it;
- 📚 Library ✕ on an own part: Smazat deletes it;
- 🖨 a custom printer's Delete: Smazat deletes it.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_no_native_dialogs.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time
import urllib.request

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

URL, OUT = sys.argv[1].rstrip("/"), sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
A = "window.__app.assembly"
M = "window.__app.modeler"
H = "window.__app.agentHandlers"
BAR = "#asmViewport .view-actions .as-break"
CONF = ".choose.confirm"
fails = []

# the browser's own dialogs, recorded (and answered "no") instead of shown
SPY = """window.__native = window.__native || [];
for (const f of ['confirm', 'alert', 'prompt']) window[f] = (m) => { window.__native.push(f + ': ' + m); return f === 'prompt' ? null : false; };"""


def check(what, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + what, extra)
    if not ok:
        fails.append(what)


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


def http(path, body=None, method=None):
    req = urllib.request.Request(f"{URL}{path}", data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"}, method=method)
    return json.loads(urllib.request.urlopen(req, timeout=30).read() or b"null")


def native():
    return js("return window.__native")


def confirm_text():
    return wait(f"return document.querySelector('{CONF} p')?.textContent", 10)


def answer(primary):
    """Click the in-page question's yes (primary) or Zrušit; it goes away."""
    btns = d.find_elements(By.CSS_SELECTOR, f"{CONF} .choose-opts .btn")
    b = next(x for x in btns if ("primary" in x.get_attribute("class")) == primary)
    word = b.text
    b.click()
    time.sleep(0.4)
    check(f"  '{word}' closes the question", not js(f"return !!document.querySelector('{CONF}')"))
    return word


def pin_x():
    return round(js(f"return {A}.inst('I2').matrix[12]"), 3)


def joints():
    return len(json.loads(call("get_assembly"))["joints"])


def type_x(v):
    js(f"{A}.sel = 'I2'; {A}.render(); {A}.draw()")
    time.sleep(0.3)
    js("const f = document.querySelector('#asmRight .as-free'); if (f) f.open = true")
    inp = d.find_element(By.CSS_SELECTOR, "#asmRight input[data-k=x]")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys(str(v), Keys.ENTER)
    time.sleep(0.5)


try:
    d.get(URL)
    js("localStorage.setItem('auto3d-lang', 'cs')")
    d.get(URL)
    wait("return !!window.__app")
    js(SPY)

    # ------------------------------------------------------------ 1. a joined part moved by hand
    call("new_model", name="Plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=8)
    call("new_model", name="Pin")
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 8}}])
    call("add_feature", type="extrude", sketch="F1", d=20)
    time.sleep(1)
    call("new_assembly", name="Joined")
    call("insert_part", part="Plate")
    call("insert_part", part="Pin")
    call("place_part", part="I2", z=30)
    call("snap_faces", type="axis", move={"part": "I2", "face": "F2:side:c1"}, onto={"part": "I1", "face": "F3:hole:0"})
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    n0, x0 = joints(), pin_x()
    print("joints:", n0, "| pin x", x0)
    type_x(25)
    hint = wait(f"return document.querySelector('{BAR} .as-break-hint')?.textContent", 10)
    words = [b.text for b in d.find_elements(By.CSS_SELECTOR, f"{BAR} .btn")]
    d.save_screenshot(f"{OUT}/nodlg_joint_bar.png")
    check("joint break: asked in the view's corner, in Czech", "Posunutí rukou zruší" in hint and words == ["Zrušit vazby a posunout", "Zpět (vazby zůstanou)"], f"{hint!r} {words}")
    check("  not moved while it asks", pin_x() == x0 and joints() == n0)
    d.find_element(By.CSS_SELECTOR, f"{BAR} [data-a=keep]").click()
    time.sleep(0.4)
    check("  Zpět: the bar goes, nothing changes", not js(f"return !!document.querySelector('{BAR}')") and pin_x() == x0 and joints() == n0)
    type_x(25)
    wait(f"return !!document.querySelector('{BAR}')", 10)
    d.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    time.sleep(0.4)
    check("  Esc: the bar goes, nothing changes", not js(f"return !!document.querySelector('{BAR}')") and pin_x() == x0 and joints() == n0)
    type_x(25)
    wait(f"return !!document.querySelector('{BAR}')", 10)
    d.find_element(By.CSS_SELECTOR, f"{BAR} [data-a=break]").click()
    time.sleep(0.6)
    check("  Zrušit vazby a posunout: joints gone, moved to 25", joints() == 0 and pin_x() == 25, f"{joints()} {pin_x()}")
    check("joint break: no native dialog", native() == [], native())

    # ------------------------------------------------------------ 2. a step others need deleted
    call("new_model", name="Block")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 20, "h": 10}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    wait(f"return !{M}.inflight && {M}.result?.body", 60)
    js(f"{M}.remove('F1')")
    q = confirm_text()
    d.save_screenshot(f"{OUT}/nodlg_step_delete.png")
    check("step delete: asked in the page, in Czech", "potřebují" in q, repr(q))
    answer(False)
    check("  Zrušit: both steps stay", len(js(f"return {M}.part.features")) == 2)
    js(f"{M}.remove('F1')")
    confirm_text()
    word = answer(True)
    time.sleep(0.5)
    check("  'Smazat je': both deleted", word == "Smazat je" and len(js(f"return {M}.part.features")) == 0, word)
    check("step delete: no native dialog", native() == [], native())

    # ------------------------------------------------------------ 3. 🕘 Recent projects ✕ (forget)
    tag = str(int(time.time()))[-6:]
    pid = f"nodlg-{tag}"
    http(f"/api/projects/{pid}", {"project": {"project_name": "Zapomeň mě", "parts": [{"id": "P1", "kind": "model", "name": "Zapomeň mě", "model": {"features": []}}]}})
    js("document.getElementById('recentBtn').click()")
    wait("return document.querySelectorAll('.aih-row').length >= 1")
    row = f".aih-row[data-id='{pid}']"
    js(f"document.querySelector(\"{row} [data-del]\").click()")
    q = confirm_text()
    check("forget: asked in the page, in Czech", "Zapomenout „Zapomeň mě“" in q, repr(q))
    answer(False)
    check("  Zrušit: still kept", any(p["id"] == pid for p in http("/api/projects")["projects"]))
    js(f"document.querySelector(\"{row} [data-del]\").click()")
    confirm_text()
    word = answer(True)
    time.sleep(0.6)
    check("  'Zapomenout': forgotten", word == "Zapomenout" and not any(p["id"] == pid for p in http("/api/projects")["projects"]), word)
    js("document.querySelector('.choose-back .choose-x')?.click()")
    time.sleep(0.3)
    check("forget: no native dialog", native() == [], native())

    # ------------------------------------------------------------ 4. 📚 Library ✕ on an own part
    call("new_model", name=f"Smazat {tag}")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 10, "h": 10}}])
    call("add_feature", type="extrude", sketch="F1", d=2)
    call("save_to_library", name=f"Smazat {tag}")
    lib = lambda: http("/api/library")["items"]
    iid = next(it["id"] for it in lib() if it["name"] == f"Smazat {tag}")
    js(f"window.__app.library.open('Smazat {tag}')")
    time.sleep(1)
    js(f"window.__app.library.select('{iid}')")
    time.sleep(1.5)
    d.find_element(By.CSS_SELECTOR, ".lib [data-a=del]").click()
    q = confirm_text()
    check("library delete: asked in the page, in Czech", "z vaší knihovny" in q, repr(q))
    word = answer(True)
    time.sleep(0.6)
    check("  'Smazat': gone from the library", word == "Smazat" and not any(it["id"] == iid for it in lib()), word)
    js("window.__app.library.close()")
    check("library delete: no native dialog", native() == [], native())

    # ------------------------------------------------------------ 5. 🖨 a custom printer deleted
    pr = http("/api/printers", {"name": f"Tiskárna {tag}", "x": 200, "y": 200, "z": 200})
    js("return window.__app.printPanel.load()")
    time.sleep(0.5)
    js("const p = window.__app.printPanel; p.selected = arguments[0]; p.render()", pr["id"])
    time.sleep(0.3)
    js("document.querySelector('#rtab-print [data-a=del]').click()")
    q = confirm_text()
    check("printer delete: asked in the page, in Czech", f"Smazat tiskárnu „Tiskárna {tag}“" in q, repr(q))
    answer(False)
    check("  Zrušit: the printer stays", any(p["id"] == pr["id"] for p in http("/api/printers")))
    js("document.querySelector('#rtab-print [data-a=del]').click()")
    confirm_text()
    word = answer(True)
    time.sleep(0.6)
    check("  'Smazat': the printer gone", word == "Smazat" and not any(p["id"] == pr["id"] for p in http("/api/printers")), word)
    check("printer delete: no native dialog", native() == [], native())
finally:
    try:
        print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
        js("localStorage.removeItem('auto3d-lang')")
    finally:
        d.quit()
print("FAILED:" if fails else "ALL PASSED", fails)
sys.exit(1 if fails else 0)
