"""🕘 Previous conversations of the AI chat, in headless Edge, in Czech, with the stand-in Claude Code (tools/fake_claude.py —
no model, no sign-in; it answers "Echo #n: … | resumed: <session or no> | summary: <yes / no>"): a conversation of two
messages (the first with a photo) -> ＋ Nová konverzace -> a second one -> a reload: the second one is still on screen ->
a reload after the app lost it (a window whose chat the server does not have): it comes back from the kept copy ->
🕘 Předchozí konverzace lists both (this project's, date, title = the first message, the number of messages) -> the
first one opened: its messages, tool lines and the photo's thumbnail back, a note -> a message goes on with it: Claude
Code's session resumed (--resume) -> the second one's session gone: opened, a message goes to a new session with the
conversation in short, the note says so -> ✕ deletes one (with a confirm). Console errors: none.

The server must run with the stand-in (its sessions in CLAUDE_CONFIG_DIR, given here as the third argument):
  A3D_DATA=<scratch>/data AUTO3D_CLAUDE=tools/fake_claude.py CLAUDE_CONFIG_DIR=<scratch>/claude py server.py --port 5199 --no-browser
  PYTHONIOENCODING=utf-8 py tools/e2e_chat_history.py http://127.0.0.1:5199 <out dir> <scratch>/claude
"""
import base64
import json
import sys
import time
import urllib.request
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

URL, OUT, CFG = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
OUT.mkdir(parents=True, exist_ok=True)
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1400,900")
opts.add_argument("--lang=cs-CZ")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
FAILS, COUNT = [], {"ok": 0}
PNG = "data:image/png;base64," + base64.b64encode(bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000""1f15c4890000000d49444154789c6300010000050001")).decode()


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
        time.sleep(0.15)
    raise TimeoutError(script)


def http(method, path):
    with urllib.request.urlopen(urllib.request.Request(f"{URL}{path}", method=method), timeout=30) as r:
        return json.loads(r.read())


def start(reload=False):
    if reload:
        d.refresh()  # (a reload keeps this window's chat; a new d.get would be a new window)
    else:
        d.get(URL)
    wait("return !!window.__app && !!window.__chat")
    time.sleep(1.2)
    if not js("return !document.getElementById('aiDrawer').hidden || !!document.querySelector('#tab-ai').offsetParent"):
        d.find_element(By.ID, "aiBtn").click()
    wait("return !!document.querySelector('#tab-ai textarea').offsetParent")


def say(text, photo=False):
    n = js("return document.querySelectorAll('#tab-ai .ai-msg.assistant').length")
    if photo:
        js("window.__chat.photos.push({name: 'star.png', data: arguments[0]}); window.__chat.renderPhotos()", PNG)
    ta = d.find_element(By.CSS_SELECTOR, "#tab-ai textarea")
    ta.send_keys(text)
    ta.send_keys(Keys.ENTER)
    wait(f"return document.querySelectorAll('#tab-ai .ai-msg.assistant').length > {n} && !window.__chat.busy")
    return js("const a = document.querySelectorAll('#tab-ai .ai-msg.assistant'); return a[a.length - 1].textContent")


def log():
    return js("""return [...document.querySelectorAll('#tab-ai .ai-log .ai-msg')].map(m => [m.className.replace('ai-msg ', ''), m.textContent.trim().slice(0, 90),
                 m.querySelectorAll('img.ai-msg-photo').length])""")


def rows():
    js("document.querySelector('#tab-ai .ai-convs-btn').click()")
    wait("return document.querySelector('#tab-ai .ai-convs .ai-conv, #tab-ai .ai-convs .ai-conv-none')")
    return js("""return [...document.querySelectorAll('#tab-ai .ai-conv')].map(r => ({id: r.dataset.id, title: r.querySelector('b').textContent,
                 when: r.querySelector('.ai-conv-when').textContent, on: r.classList.contains('on')}))""")


try:
    for c in http("GET", "/api/chat/conversations")["conversations"]:
        http("DELETE", f"/api/chat/conversations/{c['id']}")
    print("1. Czech: the bar's buttons")
    start()
    labels = js("return [...document.querySelectorAll('#tab-ai .ai-convbar button')].map(b => b.textContent)")
    check("🕘 Předchozí konverzace, ＋ Nová konverzace", labels == ["🕘 Předchozí konverzace", "＋ Nová konverzace"], labels)
    check("no conversations yet: the list says so", rows() == [] and "Zatím žádné" in js("return document.querySelector('#tab-ai .ai-convs').textContent"))
    js("document.querySelector('#tab-ai .ai-convs-btn').click()")

    print("2. the first conversation: two messages, the first with a photo")
    r1 = say("Udělej desku 60 × 40", photo=True)
    check("the stand-in answers (a new session)", r1.startswith("Echo #1: Udělej desku 60 × 40") and "resumed: no" in r1, r1)
    r2 = say("Přidej díru Ø6")
    check("the second message in the same session", r2.startswith("Echo #2: Přidej díru"), r2)
    first = http("GET", "/api/chat/conversations")["conversations"][0]
    check("kept: title, 4 messages, the project, its session", first["title"] == "Udělej desku 60 × 40" and first["messages"] == 4
          and first["project"] == js("return window.__app.autosave.id") and first["session"], first)
    check("the bar shows the conversation's title", js("return document.querySelector('#tab-ai .ai-convtitle').textContent") == "Udělej desku 60 × 40")

    print("3. ＋ Nová konverzace -> a second one")
    js("document.querySelector('#tab-ai .ai-new').click()")
    wait("return !document.querySelector('#tab-ai .ai-log .ai-msg')")
    r3 = say("Druhá konverzace: kolečko")
    check("a new session", r3.startswith("Echo #1: Druhá konverzace") and "resumed: no" in r3, r3)
    second = [c for c in http("GET", "/api/chat/conversations")["conversations"] if c["id"] != first["id"]][0]

    print("4. a reload: the conversation on screen stays")
    start(reload=True)
    wait("return document.querySelectorAll('#tab-ai .ai-msg.assistant').length >= 1")
    check("after a reload: the second conversation", [m[1] for m in log() if m[0] == "user"] == ["Druhá konverzace: kolečko"], log())
    print("   a reload after the app lost it (this window's chat not on the server): back from the kept copy")
    js("""const c = 'j' + Date.now(); sessionStorage.setItem('a3d.chatClient', c); sessionStorage.setItem('a3d.chatKeep', '1');
          sessionStorage.setItem('a3d.chatConv', c + '|' + arguments[0]);""", second["id"])
    start(reload=True)
    wait("return document.querySelectorAll('#tab-ai .ai-msg.assistant').length >= 1", 15)
    check("restored: its message and answer", [m[0] for m in log() if m[0] in ("user", "assistant")] == ["user", "assistant"]
          and js("return window.__chat.conv?.id") == second["id"], log())

    print("5. 🕘 Předchozí konverzace: both listed")
    rs = rows()
    d.save_screenshot(str(OUT / "chat_history_list.png"))
    check("two rows, the newest first, this one marked", [r["id"] for r in rs] == [second["id"], first["id"]] and rs[0]["on"], rs)
    check("a row: the first message as its title, a date, the number of messages (Czech)", rs[1]["title"] == "Udělej desku 60 × 40"
          and "zpráv: 4" in rs[1]["when"] and any(ch.isdigit() for ch in rs[1]["when"].split("·")[0]), rs[1])
    head = "Tento projekt" if js("return window.__app.autosave.id") == first["project"] else "Dřívější konverzace"  # (a reload: a new project)
    check(f"headed {head}", head in js("return document.querySelector('#tab-ai .ai-convs').textContent"))

    print("6. open the first: its messages are back")
    js(f"document.querySelector(\"#tab-ai .ai-conv[data-id='{first['id']}']\").click()")
    wait("return document.querySelectorAll('#tab-ai .ai-msg.user').length === 2")
    time.sleep(0.5)
    lg = log()
    d.save_screenshot(str(OUT / "chat_history_open.png"))
    kinds = [m[0] for m in lg]
    check("user, tool line, AI — twice", [k for k in kinds if k in ("user", "tool", "assistant")] == ["user", "tool", "assistant"] * 2, lg)
    check("the photo as a thumbnail", lg[[m[0] for m in lg].index("user")][2] == 1, lg)
    check("a note: an earlier conversation, write to go on", any(m[0].strip() == "note" and "Dřívější konverzace z" in m[1] for m in lg), lg)
    check("not busy (nothing runs)", not js("return window.__chat.busy"))
    check("the bar shows its title", js("return document.querySelector('#tab-ai .ai-convtitle').textContent") == "Udělej desku 60 × 40")

    print("7. continue it: Claude Code's session resumed")
    r4 = say("Pokračuj: zaobli hrany")
    check("--resume of its session (the AI has its context: message #3)", r4 == f"Echo #3: Pokračuj: zaobli hrany | resumed: {first['session']} | summary: no", r4)
    check("kept: 6 messages now", [c for c in http("GET", "/api/chat/conversations")["conversations"] if c["id"] == first["id"]][0]["messages"] == 6)

    print("8. the second one's session gone: a new session told it in short")
    (CFG / "projects" / "fake" / f"{second['session']}.jsonl").unlink()
    rows()
    js(f"document.querySelector(\"#tab-ai .ai-conv[data-id='{second['id']}']\").click()")
    wait("return document.querySelectorAll('#tab-ai .ai-msg.user').length === 1")
    r5 = say("A teď modře")
    check("a new session with the summary", r5 == "Echo #1: A teď modře | resumed: no | summary: yes", r5)
    check("the note says so (Czech)", any(m[0].strip() == "note" and "nešlo obnovit" in m[1] for m in log()), log())

    print("9. ✕ deletes one (with a confirm)")
    rs = rows()
    js(f"document.querySelector(\"#tab-ai .ai-conv[data-id='{first['id']}'] .ai-conv-x\").click()")
    asked = wait("return document.querySelector('.choose.confirm p')?.textContent", 5)  # (the app's own dialog, not the browser's)
    check("asked first (Czech)", "Smazat tuto konverzaci" in (asked or ""), asked)
    js("document.querySelector('.choose.confirm .btn.primary').click()")
    wait(f"return !document.querySelector(\"#tab-ai .ai-conv[data-id='{first['id']}']\")")
    check("one left, in the list and on the server", [r["id"] for r in rows()] == [second["id"]]
          and [c["id"] for c in http("GET", "/api/chat/conversations")["conversations"]] == [second["id"]])
    js(f"document.querySelector(\"#tab-ai .ai-conv[data-id='{second['id']}'] .ai-conv-x\").click()")
    wait("return document.querySelector('.choose.confirm')", 5)
    js("[...document.querySelectorAll('.choose.confirm .btn')].pop().click()")  # (Zrušit)
    time.sleep(0.5)
    check("a confirm said no: kept", len(http("GET", "/api/chat/conversations")["conversations"]) == 1)
finally:
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    check("no console errors", not errs, errs)
    print(f"\n{COUNT['ok']} ok, {len(FAILS)} failed" + (f": {FAILS}" if FAILS else ""))
    d.quit()
sys.exit(1 if FAILS else 0)
