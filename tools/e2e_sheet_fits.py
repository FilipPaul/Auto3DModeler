"""Fits on the drawing sheet, in headless Edge: a plate with a Ø8 pin standing on it -> its sheet: the pin's Ø dimension
selected -> Fit h6: drawn "Ø8 h6", its deviations told (0 / −0.009) -> Fit — : plain again -> the AI's sheet_edit fits
k6 -> a wrong class refused -> Ctrl+Z.

  PYTHONIOENCODING=utf-8 py tools/e2e_sheet_fits.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time

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
S = "window.__app.sheet"
H = "window.__app.agentHandlers"


def wait(script, t=120):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(script)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def pin_text():
    return js(f"const d = {S}.allDims().find((x) => x.id === arguments[0]); return {S}.dimText(d, {S}.value(d));", pin)


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Pin plate")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=5)
    call("add_feature", type="sketch", plane={"face": "F2:end"}, shapes=[{"circle": {"x": 0, "y": 0, "d": 8}}])
    call("add_feature", type="extrude", sketch="F3", d=15)
    print("sheet_open:", json.loads(call("sheet_open", part="Pin plate"))["preset"])
    wait(f"return !!{S}.svgEl")
    dims = json.loads(call("get_sheet"))["dims"]
    pin = next(x["id"] for x in dims if x["kind"] == "dia")
    print("the pin's size:", pin_text())
    js(f"{S}.sel = arguments[0]; {S}.render(); {S}.renderProps();", pin)
    time.sleep(0.4)
    fit = Select(d.find_element(By.CSS_SELECTOR, ".sh-props [data-k=fit]"))
    print("the Fit choices:", [o.get_attribute("value") for o in fit.options])
    fit.select_by_value("h6")
    time.sleep(0.4)
    print("h6:", pin_text(), "|", d.find_element(By.CSS_SELECTOR, ".sh-props .hint[data-no-i18n]").text)
    Select(d.find_element(By.CSS_SELECTOR, ".sh-props [data-k=fit]")).select_by_value("")
    time.sleep(0.4)
    print("—:", pin_text())
    print("the AI's k6:", json.loads(call("sheet_edit", fits={pin: "k6"}))["done"], "|", pin_text())
    print("a wrong class:", call("sheet_edit", fits={pin: "z9"})[:50])
    js("document.querySelector('.sh-stage')?.focus()")
    js(f"{S}.history.go(-1)")
    time.sleep(0.4)
    print("undo:", pin_text())
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
