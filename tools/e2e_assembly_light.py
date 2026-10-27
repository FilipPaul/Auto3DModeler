"""🪶 Simplified parts in an assembly, in headless Edge: a Base and a Lid -> the Lid's panel: 🪶 Simplified ticked -> its
body light (no edges, fewer triangles), kept in the assembly, a joint onto it still made -> unticked: full again.
(A big imported part is simplified by itself: TestLightMesh, and measured on a 42 MB board.)

  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_light.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time
import urllib.request

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


def ai(tool, **args):
    req = urllib.request.Request(f"{URL}/api/agent/call", data=json.dumps({"tool": tool, "args": args}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        res = json.loads(r.read())
    return ("ERROR " if res.get("isError") else "") + "".join(c.get("text", "") for c in res.get("content", []))


def wait(script, t=120):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(script)


def body(inst):
    return js(f"const b = {A}.bodies[{A}.inst(arguments[0]).part]?.body; return b ? [!!b.light, b.edges.length, b.face_ids.length] : null", inst)


try:
    d.get(URL)
    time.sleep(2)
    for name, h in (("Base", 10), ("Lid", 4)):
        ai("new_model", name=name)
        ai("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
        ai("add_feature", type="extrude", sketch="F1", d=h)
        ai("add_feature", type="hole", face="F2:end", points=[[10, 0]], d=6)
    ai("new_assembly", name="Box")
    ai("insert_part", part="Base")
    ai("insert_part", part="Lid")
    time.sleep(1)
    full = body("I2")
    print("the Lid, full:", full)
    js(f"{A}.choose('I2')")
    time.sleep(0.4)
    box = d.find_element(By.CSS_SELECTOR, "#asmRight [data-look=light]")
    print("its 🪶 box:", box.is_selected())
    box.click()
    wait(f"return !!{A}.bodies[{A}.inst('I2').part]?.body?.light")
    print("ticked: light", body("I2"), "| saved:", js(f"return {A}.doc.light"))
    print("a joint onto it still:", ai("snap_faces", type="touch", move={"part": "I2", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})[:20])
    js(f"{A}.choose('I2')")
    time.sleep(0.4)
    d.find_element(By.CSS_SELECTOR, "#asmRight [data-look=light]").click()
    wait(f"return !{A}.bodies[{A}.inst('I2').part]?.body?.light")
    print("unticked: full again", body("I2"), "== before", body("I2") == full)
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
