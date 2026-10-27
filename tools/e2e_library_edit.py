"""Changing library parts, in headless Edge: an own part "Holder" saved to the library (5 thick) and put into the project
(a copy) -> ✎ Edit in the library: a 3D model tab marked "📚 Library part" -> made 12 thick, 📚 Save back to the library:
the library's Holder is 12 thick, the copy in the project still 5, a new use takes 12 -> a catalogue part (ISO 4762 M3)
-> ✎ Make my own copy: a new own part in "My parts", opened to change; the catalogue unchanged -> the AI's
save_to_library on a library part being changed saves it back.

  PYTHONIOENCODING=utf-8 py tools/e2e_library_edit.py http://127.0.0.1:5199 <out dir>
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
M = "window.__app.modeler"
L = "window.__app.library"


def ai(tool, **args):
    req = urllib.request.Request(f"{URL}/api/agent/call", data=json.dumps({"tool": tool, "args": args}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        res = json.loads(r.read())
    return ("ERROR " if res.get("isError") else "") + "".join(c.get("text", "") for c in res.get("content", []))


def library():
    with urllib.request.urlopen(f"{URL}/api/library") as r:
        return json.loads(r.read())["items"]


def thick(features):
    return next(f["d"] for f in features if f["type"] == "extrude")


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.15)
    raise TimeoutError(script)


try:
    for it in library():  # (a clean start: no Holder of an earlier run)
        if it.get("source") == "user" and (it["name"].startswith("Holder") or it["name"].startswith("ISO 4762")):
            urllib.request.urlopen(urllib.request.Request(f"{URL}/api/library/{it['id']}", method="DELETE"))
    d.get(URL)
    time.sleep(2)
    ai("new_model", name="Holder")
    ai("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 30, "h": 20}}])
    ai("add_feature", type="extrude", sketch="F1", d=5)
    print("saved:", ai("save_to_library", name="Holder")[:60])
    hid = next(it["id"] for it in library() if it["name"] == "Holder")
    print("a copy in the project:", ai("library_add", item=hid, to="model")[:40])
    copy = json.loads(ai("list_parts"))[-1]["id"]

    js(f"{L}.open('Holder')")
    time.sleep(1)
    js(f"{L}.select('{hid}')")
    time.sleep(1.5)
    btn = d.find_element(By.CSS_SELECTOR, ".lib-acts [data-a=libEdit]")
    print("the button:", btn.text)
    btn.click()
    wait(f"return !!{M}.part.libEdit && !!{M}.result?.body && !{M}.inflight", 60)
    js(f"{M}.renderProps()")
    time.sleep(0.3)
    print("opened:", js("return window.__app.project.current.name"), "| marked:", d.find_element(By.CSS_SELECTOR, "#modelRight .mp-libedit b").text)
    ai("edit_feature", id="F2", fields={"d": 12})
    wait(f"return !{M}.inflight", 60)
    js(f"{M}.renderProps()")
    time.sleep(0.3)
    d.find_element(By.CSS_SELECTOR, "#modelRight [data-a=saveBack]").click()
    time.sleep(1)
    print("saved back: the library's Holder", thick(next(it for it in library() if it["id"] == hid)["features"]),
          "| items named Holder:", sum(1 for it in library() if it["name"] == "Holder"))
    print("  the copy in the project still:", js("return window.__app.project.parts.find(p => p.id === arguments[0]).data.features.find(f => f.type === 'extrude').d", copy))
    ai("library_add", item=hid, to="model")
    wait(f"return !{M}.inflight && !{M}.part.libEdit", 30)
    print("  a new use takes it:", thick(js(f"return {M}.payload().features")), "| not a library edit:", not js(f"return !!{M}.part.libEdit"))

    # a catalogue part: its own copy
    n_user = sum(1 for it in library() if it.get("source") == "user")
    js(f"{L}.open('ISO 4762')")
    time.sleep(1)
    js(f"{L}.select('iso4762', 'M3', 10)")
    time.sleep(1.5)
    btn = d.find_element(By.CSS_SELECTOR, ".lib-acts [data-a=libEdit]")
    print("a catalogue part:", btn.text)
    btn.click()
    wait(f"return !!{M}.part.libEdit && !{M}.inflight", 60)
    own = [it for it in library() if it.get("source") == "user"]
    print("  own parts", n_user, "->", len(own), "| the new one:", [(it["name"], it["category"]) for it in own if it["name"].startswith("ISO 4762")],
          "| opened:", js("return window.__app.project.current.name"))
    print("  the catalogue still there:", any(it["id"] == "iso4762" and it.get("source") != "user" for it in library()))
    print("the AI saves it back:", ai("save_to_library")[:90])
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
