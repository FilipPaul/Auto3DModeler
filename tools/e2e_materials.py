"""Materials, in headless Edge: a model's Material choice in four groups (3D printing, engineering plastics, metals,
other) -> brass: its colour and mass -> the AI's set_material titanium: its colour -> in an assembly: the same colour.

  PYTHONIOENCODING=utf-8 py tools/e2e_materials.py http://127.0.0.1:5199 <out dir>
"""
import sys, time, json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
URL, OUT = sys.argv[1], sys.argv[2]
o = webdriver.EdgeOptions(); o.add_argument("--headless=new"); o.add_argument("--window-size=1500,900")
d = webdriver.Edge(options=o); js = d.execute_script
H = "window.__app.agentHandlers"
call = lambda n, **a: js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", n, a)
d.get(URL); time.sleep(2)
call("new_model", name="Bracket")
call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
call("add_feature", type="extrude", sketch="F1", d=10)
time.sleep(1)
sel = d.find_element(By.CSS_SELECTOR, "#modelRight select[data-k=material]")
print("groups:", [g.get_attribute("label") for g in sel.find_elements(By.TAG_NAME, "optgroup")], "| options:", len(sel.find_elements(By.TAG_NAME, "option")))
print("colour before:", js("return window.__app.modeler.view.bodyColor?.getHexString() || null"))
Select(sel).select_by_value("brass")
time.sleep(0.8)
print("brass: colour", js("return window.__app.modeler.view.bodyColor?.getHexString()"), "| mass:", d.find_element(By.CSS_SELECTOR, "#modelRight").text.split("Mass")[1].split("\n")[1] if "Mass" in d.find_element(By.CSS_SELECTOR, "#modelRight").text else "?")
print("AI set_material titanium:", call("set_material", material="titanium")[:60], "| colour", js("return window.__app.modeler.view.bodyColor?.getHexString()"))
call("new_assembly", name="A"); call("insert_part", part="Bracket"); time.sleep(2)
print("in the assembly:", js("const a = window.__app.assembly; return a.lookOf(a.doc.instances[0]).colour?.toString(16)"))
logs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
print("console errors:", logs)
d.quit()
