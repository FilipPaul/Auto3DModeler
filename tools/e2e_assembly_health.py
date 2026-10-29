"""Assembly joints that say when they do not hold, in headless Edge: a Lid touching a Base -> the same two faces joined
again as a Gap: that joint changes (no second one) -> a Flush joint that fights it: the joint that does not hold is red,
says how far off and which joint holds the part elsewhere, the status bar counts it, get_assembly reports it -> ✕ one:
all hold again -> a screw + nut through both (bolt_parts): one 🔩 row in the joints list, not its four joints -> ✕ it:
the screw, the nut and the holes drilled for it go -> 🔩 in the Joint menu opens the Fasteners panel.

  PYTHONIOENCODING=utf-8 py tools/e2e_assembly_health.py http://127.0.0.1:5199 <out dir>
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
    with urllib.request.urlopen(req, timeout=180) as r:
        res = json.loads(r.read())
    return ("ERROR " if res.get("isError") else "") + "".join(c.get("text", "") for c in res.get("content", []))


def summary():
    return json.loads(ai("get_assembly"))


def panel():
    return d.find_element(By.CSS_SELECTOR, "#asmRight").text.replace("\n", " | ")


def toasts():
    return [t.text for t in d.find_elements(By.CSS_SELECTOR, ".toast")]


try:
    d.get(URL)
    time.sleep(2)
    for name, h in (("Base", 8), ("Lid", 4)):
        ai("new_model", name=name)
        ai("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
        ai("add_feature", type="extrude", sketch="F1", d=h)
    ai("new_assembly", name="Box")
    ai("insert_part", part="Base")
    ai("insert_part", part="Lid")
    lid_on = dict(move={"part": "I2", "face": "F2:start"}, onto={"part": "I1", "face": "F2:end"})
    ai("snap_faces", type="touch", **lid_on)
    s = summary()
    print("touch:", [(j["id"], j["type"], j.get("not_held")) for j in s["joints"]])

    # the same faces again, as a 5 mm gap: the joint changes, no second one
    ai("snap_faces", type="gap", gap=5, **lid_on)
    s = summary()
    lid = next(p for p in s["parts"] if p["id"] == "I2")
    print("the same faces again:", [(j["id"], j["type"], j["gap"]) for j in s["joints"]], "| lid bottom z:", lid["bbox"][2])

    # a flush joint (the lid's top level with the base's top) fights the gap
    ai("snap_faces", type="flush", move={"part": "I2", "face": "F2:end"}, onto={"part": "I1", "face": "F2:end"})
    time.sleep(0.5)
    s = summary()
    print("fighting joints:", [(j["id"], j["type"], j.get("not_held")) for j in s["joints"]])
    js(f"{A}.sel = null; {A}.render(); {A}.draw()")
    time.sleep(0.4)
    print("status:", d.find_element(By.CSS_SELECTOR, "#asmViewport .m-status").text)
    print("red rows:", [r.text.replace("\n", " | ") for r in d.find_elements(By.CSS_SELECTOR, "#asmRight .as-jrow.bad")])
    print("warning:", [e.text for e in d.find_elements(By.CSS_SELECTOR, "#asmRight .as-jbad")])
    print("red tags:", len(d.find_elements(By.CSS_SELECTOR, ".as-jtag.bad")))
    d.save_screenshot(f"{OUT}/health_bad.png")

    bad = [j for j in s["joints"] if j.get("not_held")]
    keep = next(j["id"] for j in s["joints"] if not j.get("not_held"))
    ai("remove_joint", id=keep)
    s = summary()
    print("one removed:", [(j["id"], j["type"], j.get("not_held")) for j in s["joints"]], "| status:", d.find_element(By.CSS_SELECTOR, "#asmViewport .m-status").text)

    # a screw + nut through both: one row
    for j in s["joints"]:
        ai("remove_joint", id=j["id"])
    ai("snap_faces", type="touch", **lid_on)
    print("bolt:", ai("bolt_parts", part="I2", face="F2:end", x=20, y=10, kind="nut", size="M3")[:60])
    s = summary()
    print("fasteners:", s["fasteners"], "| joints:", len(s["joints"]), "| not held:", [j["id"] for j in s["joints"] if j.get("not_held")])
    js(f"{A}.sel = null; {A}.jointsOpen = true; {A}.render(); {A}.draw()")  # (🔗 Joints (n) unfolded)
    time.sleep(0.4)
    print("rows:", [r.text.replace("\n", " | ") for r in d.find_elements(By.CSS_SELECTOR, "#asmRight .as-joints > .as-jrow")])
    d.save_screenshot(f"{OUT}/health_bolt.png")
    holes = lambda: js(f"return {A}.doc.instances.filter(i => i.id === 'I1' || i.id === 'I2').map(i => {A}.hooks.partData(i.part).features.filter(f => f.type === 'hole').length)")
    print("holes drilled (Base, Lid):", holes())
    d.find_element(By.CSS_SELECTOR, "#asmRight [data-fdel]").click()
    time.sleep(2)
    s = summary()
    print("after ✕:", [p["name"] for p in s["parts"]], "| fasteners:", s["fasteners"], "| joints:", len(s["joints"]), "| toast:", toasts()[-1:] if toasts() else None)
    print("holes left (Base, Lid):", holes())

    # 🔩 in the Joint menu: the Fasteners panel
    time.sleep(0.3)
    d.find_element(By.CSS_SELECTOR, "#asmViewport [data-a=joints]").click()  # (🔗 Joint ▾: its menu)
    d.find_element(By.CSS_SELECTOR, "#asmViewport [data-joint=fastener]").click()
    time.sleep(0.4)
    print("Joint ▾ 🔩:", d.find_element(By.CSS_SELECTOR, "#asmRight h2").text, "| mode:", js(f"return {A}.mode"))
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
