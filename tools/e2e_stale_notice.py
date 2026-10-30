"""⟳ New version in the top bar, in headless Edge: a server whose checkout moved on since it started (faked with
A3D_FAKE_HEAD) -> the notice shows, in Czech, with its tooltip; /api/version says stale. Start the test server with
the fake HEAD:

  A3D_FAKE_HEAD=fa4e000 A3D_DATA=<scratch>/data py server.py --port 5199 --no-browser
  PYTHONIOENCODING=utf-8 py tools/e2e_stale_notice.py http://127.0.0.1:5199 <out dir>
"""
import json, sys, time, urllib.request
from selenium import webdriver
from selenium.webdriver.common.by import By
URL, OUT = sys.argv[1], sys.argv[2]
v = json.loads(urllib.request.urlopen(f"{URL}/api/version").read())
print("/api/version:", v["text"], "| stale", v["stale"], "| head", v["head"])
assert v["stale"] and v["head"] == "fa4e000", "start the server with A3D_FAKE_HEAD=fa4e000"
assert "checkout now at fa4e000 — restart the app" in v["text"], v["text"]
o = webdriver.EdgeOptions(); o.add_argument("--headless=new"); o.add_argument("--window-size=1500,900"); o.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=o); js = d.execute_script
try:
    d.get(URL); time.sleep(1)
    js("localStorage.setItem('auto3d-lang', 'cs')"); d.refresh(); time.sleep(2.5)
    note = d.find_element(By.ID, "staleNote")
    text, title = note.text, note.get_attribute("title")
    print("notice:", note.is_displayed(), "|", text, "|", title)
    assert note.is_displayed(), "the notice is not shown"
    assert text == "⟳ Nová verze — restartujte aplikaci", text
    assert "Zavřete aplikaci a spusťte ji znovu" in title, title
    assert js("return document.querySelector('.project-bar').contains(arguments[0])", note), "not in the top bar"
    d.save_screenshot(f"{OUT}/stale_notice_cs.png")
    js("localStorage.setItem('auto3d-lang', 'en')"); d.refresh(); time.sleep(2.5)
    print("English:", d.find_element(By.ID, "staleNote").text)
    assert d.find_element(By.ID, "staleNote").text == "⟳ New version — restart the app"
    errors = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errors)
    assert not errors
    print("OK")
finally:
    js("localStorage.removeItem('auto3d-lang')")
    d.quit()
