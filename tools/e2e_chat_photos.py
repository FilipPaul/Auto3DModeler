"""Photos in the AI chat: 📎 attach, drop onto the chat, thumbnails with ✕, Send carries the photos, the
server saves them and the user bubble shows them — in headless Edge. Claude is not started: the send
request is captured in the page (the server side — saving, checking, the message to Claude — is covered by
tests/test_agent.py).

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_chat_photos.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
PIC = str(Path(__file__).resolve().parent.parent / "pernicek.png")
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script


def wait(script, t=30):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def thumbs():
    return js("return document.querySelectorAll('#tab-ai .ai-thumb').length")


try:
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "aiBtn").click()  # (✨ AI in the top bar: the start screen covers the tabs of an empty app)
    time.sleep(0.3)

    # 📎: the real file input
    d.find_element(By.CSS_SELECTOR, "#tab-ai .ai-attach input").send_keys(PIC)
    wait("return document.querySelectorAll('#tab-ai .ai-thumb').length === 1")
    print("after 📎:", thumbs(), "thumbnail(s)")

    # drop a picture onto the chat (a DataTransfer with a file made in the page)
    js("""const c = document.createElement('canvas'); c.width = 40; c.height = 30; const g = c.getContext('2d');
      g.fillStyle = '#c33'; g.fillRect(5, 5, 30, 20);
      c.toBlob((b) => { const dt = new DataTransfer(); dt.items.add(new File([b], 'dropped.png', { type: 'image/png' }));
        const t = document.querySelector('#tab-ai .ai-log');
        for (const type of ['dragover', 'drop']) t.dispatchEvent(new DragEvent(type, { dataTransfer: dt, bubbles: true, cancelable: true })); });""")
    wait("return document.querySelectorAll('#tab-ai .ai-thumb').length === 2")
    print("after drop:", thumbs(), "| names", js("return [...document.querySelectorAll('#tab-ai .ai-thumb')].map(t => t.title)"))

    # a text file is refused
    js("""const dt = new DataTransfer(); dt.items.add(new File(['x'], 'notes.txt', { type: 'text/plain' }));
      document.querySelector('#tab-ai').dispatchEvent(new DragEvent('drop', { dataTransfer: dt, bubbles: true, cancelable: true }));""")
    time.sleep(0.3)
    print("text file ignored:", thumbs() == 2)

    # ✕ removes one
    d.find_elements(By.CSS_SELECTOR, "#tab-ai .ai-thumb-x")[1].click()
    time.sleep(0.2)
    print("after ✕:", thumbs())
    d.save_screenshot(f"{OUT}/c1_photo_attached.png")

    # Send: the request carries the photo; answer like the server, then show the user bubble from the event
    js("""window.__sent = null; const orig = window.fetch;
      window.fetch = async (u, o) => { if (String(u).includes('/api/chat/send')) {
          window.__sent = JSON.parse(o.body);  // what the server gets (its half is tested in tests/test_agent.py)
          return new Response(JSON.stringify({ ok: true }), { headers: { 'Content-Type': 'application/json' } }); }
        return orig(u, o); };""")
    ta = d.find_element(By.CSS_SELECTOR, "#tab-ai textarea")
    ta.send_keys("Make a 90 mm cookie cutter from this")
    d.find_element(By.CSS_SELECTOR, "#tab-ai .ai-form button[type=submit]").click()
    wait("return window.__sent")
    sent = js("return window.__sent")
    print("sent:", json.dumps({"text": sent["text"], "photos": [(p["name"], p["data"][:22], len(p["data"])) for p in sent["photos"]]}))
    print("thumbnails cleared after send:", thumbs() == 0)
    js("window.__chat.handle({type: 'user', text: arguments[0], photos: [{name: 'pernicek.png', url: '/api/chat/photo/none.png'}]})", sent["text"])
    time.sleep(0.3)
    print("user bubble:", js("const m = [...document.querySelectorAll('#tab-ai .ai-msg.user')].pop(); return [m.querySelectorAll('img.ai-msg-photo').length, m.textContent]"))
    d.save_screenshot(f"{OUT}/c2_photo_sent.png")
finally:
    print("console errors:", [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE" and "none.png" not in e["message"]])
    d.quit()
