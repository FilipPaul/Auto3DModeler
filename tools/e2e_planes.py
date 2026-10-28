"""The Top / Front / Right planes, in headless Edge: an empty model shows them faint -> ◫ Planes off: hidden, remembered
-> with a body, choosing a sketch plane: shown anyway -> cancelled: hidden again -> ◫ Planes on.

  PYTHONIOENCODING=utf-8 py tools/e2e_planes.py http://127.0.0.1:5199 <out dir>
"""
import sys, time
from selenium import webdriver
from selenium.webdriver.common.by import By
URL, OUT = sys.argv[1], sys.argv[2]
o = webdriver.EdgeOptions(); o.add_argument("--headless=new"); o.add_argument("--window-size=1500,900"); o.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=o); js = d.execute_script
M = "window.__app.modeler"
d.get(URL); time.sleep(2)
js("localStorage.removeItem('a3d.planes')")
d.find_element(By.ID, "newModelBtn").click(); time.sleep(1)
js(f"{M}.leaveSketchMode ? {M}.action('cancelSketch') : null"); time.sleep(0.8)
vis = lambda: js(f"return {M}.view.datumGroup.visible")
print("an empty model: planes", vis(), "| faint:", js(f"return {M}.view.datumGroup.children.filter(m => m.userData.datum).map(m => m.material.opacity)"))
d.save_screenshot(f"{OUT}/planes_on.png")
d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=planes]").click(); time.sleep(0.4)
print("◫ Planes off:", vis(), "| remembered:", js("return localStorage.getItem('a3d.planes')"))
H = "window.__app.agentHandlers"
call = lambda n, **a: js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", n, a)
call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 30, "h": 20}}]); call("add_feature", type="extrude", sketch="F1", d=5); time.sleep(1.5)
js(f"{M}.action('sketch')"); time.sleep(0.6)
print("choosing a sketch plane: shown anyway", vis())
js(f"{M}.action('cancelPlane')"); time.sleep(0.5)
print("back: hidden again", vis())
d.find_element(By.CSS_SELECTOR, ".m-cmdbar [data-a=planes]").click(); time.sleep(0.4)
print("◫ Planes on:", vis())
print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
d.quit()
