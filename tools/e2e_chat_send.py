"""The AI chat's basic path, as a user does it, in headless Edge with the stand-in Claude Code (tools/fake_claude.py — no
model, no sign-in): ✨ AI -> a message typed in the box and sent with Enter -> its bubble at once, then the AI's answer
(its tool line, "Echo #1: …"), Send enabled again -> a second one with the Send button -> a slow answer (a message with
"SLOW": the stand-in streams text for a minute) -> Stop stops it within seconds (Stop hidden, Send enabled, the chat's
process ended) -> the next message is answered again. Console errors: none.

The regression it guards: the server's request timings read the chat's endless event stream to measure it, so nothing
reached the page — the sent message did not show, no answer came and Stop did nothing.

The server must run with the stand-in:
  A3D_DATA=<scratch>/data AUTO3D_CLAUDE=tools/fake_claude.py CLAUDE_CONFIG_DIR=<scratch>/claude py server.py --port 5199 --no-browser
  PYTHONIOENCODING=utf-8 py tools/e2e_chat_send.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

URL, OUT = sys.argv[1], Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1400,900")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
FAILS, COUNT = [], {"ok": 0}


def check(what, ok, got=None):
    print(("  ok   " if ok else "  FAIL ") + what + ("" if ok or got is None else f" -> {str(got)[:600]}"))
    if ok:
        COUNT["ok"] += 1
    else:
        FAILS.append(what)


def wait(script, t=30):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    return js(script)


def msgs(kind):
    return js(f"return [...document.querySelectorAll('.ai-msg.{kind}')].map(m => m.innerText)")


def status():
    client = d.execute_async_script("import('/js/agent.js').then((m) => arguments[0](m.CLIENT))")  # (this window's chat)
    with urllib.request.urlopen(f"{URL}/api/chat/status?client={client}", timeout=10) as r:
        return json.loads(r.read())


BUSY = "return document.querySelector('.ai-panel').classList.contains('ai-busy')"
try:
    d.get(URL)
    wait("return !!window.__app && !!window.__chat")
    time.sleep(1)
    d.find_element(By.ID, "aiBtn").click()  # (the ✨ AI button: the chat in sight)
    time.sleep(0.5)
    ta = d.find_element(By.CSS_SELECTOR, ".ai-form textarea")
    check("the chat's box in sight", ta.is_displayed())

    # 1. typed + Enter: the bubble at once, then the answer
    ta.send_keys("Make a box 40 x 30 x 10 mm")
    t0 = time.time()
    ta.send_keys(Keys.ENTER)
    shown = wait("return [...document.querySelectorAll('.ai-msg.user')].some(m => m.innerText.includes('Make a box 40'))", 5)
    check(f"Enter: the user's bubble shows at once ({time.time() - t0:.1f} s)", shown and time.time() - t0 < 5, msgs("user"))
    check("the box is empty again", ta.get_attribute("value") == "")
    got = wait("return [...document.querySelectorAll('.ai-msg.assistant')].some(m => m.innerText.includes('Echo #1'))", 30)
    check("the AI's answer comes", got, msgs("assistant"))
    check("its answer is about the message", any("Make a box 40" in m for m in msgs("assistant")), msgs("assistant"))
    check("a tool line for its call", js("return document.querySelectorAll('.ai-msg.tool').length") >= 1)
    check("not busy after the answer: Send enabled, Stop hidden",
          wait(f"{BUSY.replace('return ', 'return !')}", 10)
          and js("return !document.querySelector('.ai-form button[type=submit]').disabled && document.querySelector('.ai-stop').hidden"))

    # 2. the Send button
    ta.send_keys("Second message")
    d.find_element(By.CSS_SELECTOR, ".ai-form button[type=submit]").click()
    check("Send button: the bubble shows", wait("return [...document.querySelectorAll('.ai-msg.user')].some(m => m.innerText.includes('Second message'))", 5))
    check("its answer comes (the same session)", wait("return [...document.querySelectorAll('.ai-msg.assistant')].some(m => m.innerText.includes('Echo #2'))", 30),
          msgs("assistant"))
    wait(f"{BUSY.replace('return ', 'return !')}", 10)

    # 3. Stop during an answer
    ta.send_keys("A SLOW one please")
    ta.send_keys(Keys.ENTER)
    check("slow: the bubble shows", wait("return [...document.querySelectorAll('.ai-msg.user')].some(m => m.innerText.includes('SLOW'))", 5))
    check("the answer streams in", wait("return [...document.querySelectorAll('.ai-msg.assistant')].some(m => /\\b3 /.test(m.innerText))", 20),
          msgs("assistant"))
    stop = d.find_element(By.CSS_SELECTOR, ".ai-stop")
    check("busy while it answers: Stop in sight", js(BUSY) and stop.is_displayed())
    d.save_screenshot(str(OUT / "chat-send-answering.png"))
    js("arguments[0].click()", stop)  # (as the button does; hidden — the check above failed already)
    t0 = time.time()
    done = wait(f"{BUSY.replace('return ', 'return !')}", 10)
    check(f"Stop: the answer stops ({time.time() - t0:.1f} s)", done and time.time() - t0 < 8)
    check("Stop hidden, Send enabled", js("return document.querySelector('.ai-stop').hidden && !document.querySelector('.ai-form button[type=submit]').disabled"))
    time.sleep(1.5)
    text = js("return [...document.querySelectorAll('.ai-msg.assistant')].pop().innerText")
    time.sleep(1.5)
    check("no more text after Stop", js("return [...document.querySelectorAll('.ai-msg.assistant')].pop().innerText") == text)
    check("the chat's process ended", not status()["running"], status())

    # 4. the next message is answered again (a new process, the session resumed)
    ta.send_keys("After the stop")
    ta.send_keys(Keys.ENTER)
    check("after Stop: the bubble shows", wait("return [...document.querySelectorAll('.ai-msg.user')].some(m => m.innerText.includes('After the stop'))", 5))
    check("after Stop: answered", wait("return [...document.querySelectorAll('.ai-msg.assistant')].some(m => m.innerText.includes('After the stop'))", 30),
          msgs("assistant"))
    d.save_screenshot(str(OUT / "chat-send.png"))
finally:
    if FAILS:
        print("chat:", js("return [...document.querySelectorAll('.ai-msg')].map(m => m.className + ': ' + m.innerText.slice(0, 200))"))
    errors = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    check("no console errors", not errors, errors)
    d.quit()

print(f"\n{COUNT['ok']} ok, {len(FAILS)} failed" + (": " + "; ".join(FAILS) if FAILS else ""))
sys.exit(1 if FAILS else 0)
