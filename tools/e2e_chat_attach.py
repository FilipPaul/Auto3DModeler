"""📎 Příloha — files attached to an AI chat message, as a user does it, in headless Edge with the stand-in Claude Code
(tools/fake_claude.py, which keeps each message it got whole in its session file): through the real file picker a
small UTF-8 .txt, a cp1250 .txt with Czech letters, a 200 kB .log and a .step; a .csv pasted (Ctrl+V) and a .json +
a .md dropped onto the chat; an .exe refused in-app; chips with an icon, the name and the size, ✕ removes one; Send ->
the stand-in gets both texts right (no mojibake), the log's path with its first 200 lines, the STEP's path; the sent
bubble shows the chips, also after a reload (the kept conversation); in Czech the button is "📎 Příloha" and the
refusal "Tento typ souboru zatím neumím přiložit". No console errors, no native dialogs.

The server must run with the stand-in:
  A3D_DATA=<scratch>/data AUTO3D_CLAUDE=<absolute path>/tools/fake_claude.py CLAUDE_CONFIG_DIR=<scratch>/claude py server.py --port 5199 --no-browser
  PYTHONIOENCODING=utf-8 py tools/e2e_chat_attach.py http://127.0.0.1:5199 <out dir> <scratch>/claude
"""
import json
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By

URL, OUT, CLAUDE = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
OUT.mkdir(parents=True, exist_ok=True)
CZ = "Příliš žluťoučký kůň úpěl ďábelské ódy"
UTF = "Poznámka v UTF-8: šroub M4 × 12, ø 8 mm"
files = {"poznamka.txt": UTF.encode("utf-8"), "cesky-1250.txt": (CZ + "\r\nDruhý řádek: čep průměr 6\r\n").encode("cp1250"),
         "run.log": "".join(f"line {i:05d} of the machine log ...........\n" for i in range(5000)).encode(),  # ≈ 200 kB
         "drzak.step": b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n", "setup.exe": b"MZ\x90\x00"}
for name, raw in files.items():
    (OUT / name).write_bytes(raw)

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


def no_dialogs():  # (native alert / confirm / prompt counted, never shown)
    js("window.__dialogs = []; for (const k of ['alert', 'confirm', 'prompt']) window[k] = (m) => { window.__dialogs.push(k + ': ' + m); return null; };")


def chips():
    return js("return [...document.querySelectorAll('.ai-form .ai-file')].map(c => c.innerText.replace(/\\s+/g, ' ').trim())")


def toasts():
    return js("return [...document.querySelectorAll('#toasts .toast')].map(t => t.textContent)")


def give(kind, items):
    """Paste (Ctrl+V into the box) or drop (onto the chat) files made in the page: [(name, text, type)]."""
    js("""const [kind, items] = arguments; const dt = new DataTransfer();
      for (const [n, text, type] of items) dt.items.add(new File([text], n, { type }));
      if (kind === 'paste') document.querySelector('.ai-form textarea').dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true }));
      else { const t = document.querySelector('.ai-log'); for (const ty of ['dragover', 'drop']) t.dispatchEvent(new DragEvent(ty, { dataTransfer: dt, bubbles: true, cancelable: true })); }""",
       kind, items)


try:
    d.get(URL)
    wait("return !!window.__app && !!window.__chat")
    no_dialogs()
    time.sleep(1)
    d.find_element(By.ID, "aiBtn").click()
    time.sleep(0.5)
    btn = d.find_element(By.CSS_SELECTOR, ".ai-attach")
    check("the button reads 📎 Attachment", btn.text.strip() == "📎 Attachment", btn.text)

    # 1. the real file picker: four files at once
    pick = d.find_element(By.CSS_SELECTOR, ".ai-attach input")
    pick.send_keys("\n".join(str(OUT / n) for n in ("poznamka.txt", "cesky-1250.txt", "run.log", "drzak.step")))
    wait("return document.querySelectorAll('.ai-form .ai-file').length === 4", 10)
    got = chips()
    check("📎: four chips", len(got) == 4, got)
    check("chips: icon, name, size", got[:1] == [f"📄 poznamka.txt {len(files['poznamka.txt'])} B ✕"] and got[2].startswith("📄 run.log 2") and "kB" in got[2]
          and got[3].startswith("🧊 drzak.step"), got)
    check("a long text's chip says its head goes", "first 200 lines" in js("return document.querySelectorAll('.ai-form .ai-file')[2].title"))

    # 2. an unknown type: refused in-app, no chip
    pick.send_keys(str(OUT / "setup.exe"))
    check("an .exe refused in-app", wait("return [...document.querySelectorAll('#toasts .toast')].some(t => t.textContent.includes('cannot be attached yet'))", 5), toasts())
    check("no chip for it", len(chips()) == 4, chips())

    # 3. paste a text file, drop two, ✕ one
    give("paste", [("mereni.csv", "bod;x;y\nA;1,5;2\n", "text/csv")])
    check("paste: a chip for the .csv", wait("return document.querySelectorAll('.ai-form .ai-file').length === 5", 5), chips())
    check("paste: no text pasted into the box", js("return document.querySelector('.ai-form textarea').value") == "")
    give("drop", [("nastaveni.json", '{"vrtak": "Ø 4"}', "application/json"), ("navic.md", "# extra", "text/markdown")])
    check("drop: two chips more", wait("return document.querySelectorAll('.ai-form .ai-file').length === 7", 5), chips())
    js("[...document.querySelectorAll('.ai-form .ai-file')].find(c => c.innerText.includes('navic.md')).querySelector('.ai-file-x').click()")
    got = chips()
    check("✕ removes that one", len(got) == 6 and not any("navic.md" in c for c in got), got)
    d.save_screenshot(str(OUT / "attach-chips.png"))

    # 4. Send: the stand-in gets it all
    d.find_element(By.CSS_SELECTOR, ".ai-form textarea").send_keys("Read these files")
    d.find_element(By.CSS_SELECTOR, ".ai-form button[type=submit]").click()
    check("the chips leave the box", wait("return !document.querySelectorAll('.ai-form .ai-file').length", 5))
    check("answered", wait("return [...document.querySelectorAll('.ai-msg.assistant')].some(m => m.innerText.includes('Echo #1'))", 30),
          js("return [...document.querySelectorAll('.ai-msg')].map(m => m.innerText)"))
    logs = sorted((CLAUDE / "projects" / "fake").glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    msg = json.loads(logs[-1].read_text(encoding="utf-8").splitlines()[-1])["text"] if logs else ""
    msg = msg.split("]\n\n", 1)[1] if msg.startswith("[Nastavení:") else msg  # (the ✨ settings line goes first)
    check("the message has the typed text", msg.startswith("Read these files"), msg[:200])
    check("the UTF-8 text in a fence with its name", f"poznamka.txt:\n```txt\n{UTF}\n```" in msg, msg[:800])
    check("the cp1250 text right (no mojibake)", CZ in msg and "Druhý řádek: čep průměr 6" in msg and "cp1250" in msg, msg[:1500])
    head = [ln for ln in msg.splitlines() if ln.startswith("[Attached file:") and "run.log" in ln]
    check("the 200 kB log: its path, size and 'first 200 lines included'", head and "first 200 lines included" in head[0], head)
    log_path = Path(head[0][len("[Attached file: "):].split(",")[0]) if head else None
    check("the log saved whole at that path", log_path and log_path.exists() and log_path.read_bytes() == files["run.log"], log_path)
    check("its first 200 lines in the message, not more", "line 00199 of" in msg and "line 00200 of" not in msg)
    step = [ln for ln in msg.splitlines() if ln.startswith("[Attached file:") and ln.endswith("drzak.step]")]
    check("the STEP: its path given", step and Path(step[0][16:-1]).exists(), step)
    check("the pasted .csv's text", "bod;x;y\nA;1,5;2" in msg)
    check("the dropped .json's text", '{"vrtak": "Ø 4"}' in msg)
    check("the removed .md not sent", "navic.md" not in msg)

    # 5. the sent bubble: the chips; after a reload too (the kept conversation)
    bub = js("return [...[...document.querySelectorAll('.ai-msg.user')].pop().querySelectorAll('.ai-file')].map(c => c.innerText.replace(/\\s+/g, ' ').trim())")
    check("the sent bubble shows six chips", len(bub) == 6 and bub[0].startswith("📄 poznamka.txt"), bub)
    check("a chip's title is its saved path", js("return [...document.querySelectorAll('.ai-msg.user .ai-file')].some(c => c.title.endsWith('drzak.step') && c.title.includes('attachments'))"))
    d.save_screenshot(str(OUT / "attach-sent.png"))
    d.refresh()
    wait("return !!window.__app && !!window.__chat")
    no_dialogs()
    d.find_element(By.ID, "aiBtn").click()
    check("after a reload: the chips kept", wait("return document.querySelectorAll('.ai-msg.user .ai-file').length === 6", 10),
          js("return document.querySelectorAll('.ai-msg.user .ai-file').length"))

    # 6. in Czech: 📎 Příloha, the refusal in Czech
    js("localStorage.setItem('auto3d-lang', 'cs')")
    d.refresh()
    wait("return !!window.__app && !!window.__chat")
    no_dialogs()
    d.find_element(By.ID, "aiBtn").click()
    time.sleep(0.5)
    check("Czech: 📎 Příloha", d.find_element(By.CSS_SELECTOR, ".ai-attach").text.strip() == "📎 Příloha", d.find_element(By.CSS_SELECTOR, ".ai-attach").text)
    d.find_element(By.CSS_SELECTOR, ".ai-attach input").send_keys(str(OUT / "setup.exe"))
    check("Czech: Tento typ souboru zatím neumím přiložit",
          wait("return [...document.querySelectorAll('#toasts .toast')].some(t => t.textContent.includes('Tento typ souboru zatím neumím přiložit'))", 5), toasts())
    d.find_element(By.CSS_SELECTOR, ".ai-attach input").send_keys(str(OUT / "run.log"))
    wait("return document.querySelectorAll('.ai-form .ai-file').length === 1", 5)
    check("Czech: the chip's tip", "prvních 200 řádků" in js("return document.querySelector('.ai-form .ai-file').title"),
          js("return document.querySelector('.ai-form .ai-file')?.title"))
    d.save_screenshot(str(OUT / "attach-cs.png"))
    js("localStorage.removeItem('auto3d-lang')")
finally:
    try:
        check("no native dialogs", not js("return window.__dialogs || []"), js("return window.__dialogs"))
    except Exception as exc:  # (a dialog open: the page cannot even answer)
        check("no native dialogs", False, exc)
    errors = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    check("no console errors", not errors, errors)
    d.quit()

print(f"\n{COUNT['ok']} ok, {len(FAILS)} failed" + (": " + "; ".join(FAILS) if FAILS else ""))
sys.exit(1 if FAILS else 0)
