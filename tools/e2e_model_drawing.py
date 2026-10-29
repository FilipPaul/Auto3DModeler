"""📐 2D drawing (PDF) of a 3D model part, in headless Edge: a 60 x 40 x 10 plate with two Ø6 holes (built through the AI
tools) -> 📐 Drawing (PDF) in the part's panel -> a PDF with the Front / Top / Right views, the sizes, the holes and the
title block; the same from the top Export menu; the AI's export {format: "pdf"}.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_model_drawing.py http://127.0.0.1:5199 <out dir>
"""
import base64
import json
import sys
import time
import urllib.request
from pathlib import Path

import fitz
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
H = "window.__app.agentHandlers"


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


def saved_pdf(i):
    name, b64 = js(f"return window.__saved[{i}]")
    return name, base64.b64decode(b64)


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_model", name="Bracket")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("add_feature", type="hole", face="F2:end", points=[[-20, -10], [20, 10]], d=6)
    call("set_material", material="PETG")
    wait(f"return !{M}.inflight && {M}.result?.body")
    time.sleep(0.5)
    js("""window.__saved = []; window.showSaveFilePicker = async (o) => ({ name: o.suggestedName,
      createWritable: async () => ({ write: async (b) => { const r = new FileReader(); await new Promise(res => { r.onload = res; r.readAsDataURL(b); });
        window.__saved.push([o.suggestedName, r.result.split(',')[1]]); }, close: async () => {} }) });""")
    btn = d.find_element(By.CSS_SELECTOR, "#modelExport [data-x=pdf]")
    print("button:", btn.text)
    btn.click()
    wait("return window.__saved.length === 1")
    name, data = saved_pdf(0)
    page = fitz.open(stream=data, filetype="pdf")[0]
    text = page.get_text().replace("\n", " | ")
    print("saved:", name, len(data), "bytes | PDF:", data[:4] == b"%PDF")
    print("text:", text[:260])
    page.get_pixmap(dpi=90).save(str(Path(OUT) / "drawing_e2e.png"))
    print("toast:", js("return [...document.querySelectorAll('.toast')].map(t => t.textContent).slice(-1)[0]"))

    # the top Export menu
    d.find_element(By.ID, "exportBtn").click()
    time.sleep(0.2)
    item = d.find_element(By.CSS_SELECTOR, "#exportMenu [data-fmt=pdf]")
    print("menu item visible:", item.is_displayed(), item.text)
    item.click()
    wait("return window.__saved.length === 2")
    print("menu export:", saved_pdf(1)[0])

    # the AI's export to a file
    # (export runs on the server, like the MCP server calls it; the page answers its get_body)
    out = Path(OUT) / "ai_drawing.pdf"
    if out.exists():
        out.unlink()
    req = urllib.request.Request(f"{URL}/api/agent/call", data=json.dumps({"tool": "export", "args": {"format": "pdf", "path": str(out)}}).encode(),
                                 headers={"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=120).read())
    print("AI export:", r["content"][0]["text"], "| exists", out.exists(), "| PDF", out.read_bytes()[:4] == b"%PDF" if out.exists() else None)
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
