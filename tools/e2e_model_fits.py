"""Fits and tolerances for the 2D drawing, in headless Edge: the AI makes a plate with an Ø8 H7 hole and sets aluminium +
ISO 2768-m -> the step list says "Ø8 H7", the part panel's Tolerances shows ISO 2768-m -> the hole step opened: its
Fit is H7; set to H8 by hand -> the drawing (PDF) says Ø8 H8 with its deviations and ISO 2768-m -> edit_feature fit
null takes it off; a wrong fit is refused.

  PYTHONIOENCODING=utf-8 py tools/e2e_model_fits.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time
import urllib.request

import fitz
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"
H = "window.__app.agentHandlers"


def call(t, **a):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", t, a)


def pdf_text():
    part = js(f"return {M}.payload()")
    req = urllib.request.Request(f"{URL}/api/model/export/pdf", data=json.dumps({"part": part, "name": "Plate"}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return fitz.open(stream=r.read(), filetype="pdf")[0].get_text()


try:
    d.get(URL)
    time.sleep(2)
    call("new_model", name="Plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=8)
    print("hole:", call("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=8, fit="h7")[:60])
    print("material + tolerance:", json.loads(call("set_material", material="aluminium", tolerance="m")).get("material"))
    time.sleep(1)
    print("the step list:", [e.text for e in d.find_elements(By.CSS_SELECTOR, ".mt-item") if "Ø8" in e.text][:1])
    js(f"{M}.renderProps()")
    time.sleep(0.3)
    tol = d.find_elements(By.CSS_SELECTOR, "[data-k=tolerance]")
    print("the part's Tolerances:", Select(tol[0]).first_selected_option.text if tol else None)
    js(f"{M}.edit('F3')")
    time.sleep(0.6)
    fit = d.find_element(By.CSS_SELECTOR, "[data-k=fit]")
    print("the hole's Fit:", Select(fit).first_selected_option.text)
    Select(fit).select_by_value("H8")
    d.find_element(By.CSS_SELECTOR, "[data-a=ok]").click()
    time.sleep(1)
    print("after OK:", js(f"return {M}.part.features.find(f => f.id === 'F3').fit"))
    text = pdf_text()
    print("the drawing:", [w for w in ("Ø8 H8", "Fits: Ø8 H8 (+0.022 / 0)", "General tolerances ISO 2768-m (medium)", "aluminium") if w in text])
    print("fit off:", call("edit_feature", id="F3", fields={"fit": None})[:40], "->", js(f"return {M}.part.features.find(f => f.id === 'F3').fit ?? null"))
    print("a wrong fit:", call("edit_feature", id="F3", fields={"fit": "Q7"})[:80])
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
