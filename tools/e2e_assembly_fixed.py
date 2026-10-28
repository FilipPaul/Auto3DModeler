"""📌 Fixed parts in an assembly, in headless Edge: Base and Lid put in -> the first (Base) is fixed in place, 📌 in the
parts list -> moving it by hand (the AI's place_part) refused -> a joint made from the Base onto the Lid moves the
Lid, not the Base -> the Lid's suggestions: unlock and edit it here, fix in place … -> the Base freed: it moves.

  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_fixed.py http://127.0.0.1:5199 <out dir>
"""
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1500,900")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
H = "window.__app.agentHandlers"
A = "window.__app.assembly"


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(script)


def at(inst):
    return js(f"return {A}.inst(arguments[0]).matrix.slice(12, 15).map(v => +v.toFixed(2))", inst)


try:
    d.get(URL)
    wait("return !!window.__app")
    for name, h in (("Base", 10), ("Lid", 4)):
        call("new_model", name=name)
        call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
        call("add_feature", type="extrude", sketch="F1", d=h)
    call("new_assembly", name="Box")
    call("insert_part", part="Base")
    call("insert_part", part="Lid")
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    print("fixed:", js(f"return {A}.doc.instances.map(i => [i.id, !!i.fixed])"), "| the list:", [e.text for e in d.find_elements(By.CSS_SELECTOR, "#asmLeft .mt-what")])
    print("the Base moved by hand:", call("place_part", part="I1", x=50)[:70], "| at", at("I1"))
    base0, lid0 = at("I1"), at("I2")
    call("snap_faces", type="touch", move={"part": "I1", "face": "F2:end"}, onto={"part": "I2", "face": "F2:start"})
    time.sleep(0.5)
    print("a joint from the Base onto the Lid: Base", base0, "->", at("I1"), "| Lid", lid0, "->", at("I2"),
          "| the joint moves:", js(f"return {A}.doc.mates.map(m => m.move)"))
    js(f"{A}.choose('I2')")
    time.sleep(0.4)
    print("the Lid's suggestions:", [b.text.replace(chr(10), " ") for b in d.find_elements(By.CSS_SELECTOR, "#asmViewport .view-suggest .vs-list button")])
    js(f"{A}.choose('I1')")
    time.sleep(0.4)
    d.find_element(By.CSS_SELECTOR, "#asmRight [data-a=fix]").click()
    time.sleep(0.4)
    print("the Base freed:", js(f"return !!{A}.inst('I1').fixed"), "| moved by hand:", call("place_part", part="I1", x=50)[:30], at("I1"))
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
