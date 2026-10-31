"""✨ AI settings in the chat, in Czech, in headless Edge with the stand-in Claude Code (tools/fake_claude.py — no model,
no sign-in; its session files under <claude config dir> hold the whole text it got):

1. a 3D model, the ✨ AI drawer -> ✨ Nastavení: the panel in place of the log (Czech: Nastavení AI, Profil návrhu …);
   🎨 Dekorace -> 3D tisk, the rules off; ⚙ Automatizace / ICT -> CNC, the rules on; 🔩 Snadná montáž off -> ✎ Vlastní;
   🐞 Hledač chyb raises the token estimate;
2. 🖨 Funkční tisk, a message: Claude gets "[Nastavení: profil=tisk; …]" first; a second message without a change gets
   no line;
3. "#u" typed -> the tags' list (#uc) -> Enter puts it in; "#cn" + Tab -> #cnc: sent, the bubble shows the text without
   them and the chips #uc #cnc, Claude's line has režimy=teach-me and výroba=CNC;
4. 📌 Omezit AI na aktuálně otevřený soubor: Claude's MCP server lists fewer tools (the stand-in asks it: "TOOLS?") —
   its process started again unseen (no "stopped" note), the session resumed, the line says omezení=soubor; 🌐 off:
   started again without WebSearch, the line says internet=ne; the tags' row under the box (thin, Czech tooltips): a click
   puts #cnc in at the cursor, again takes it out; the 📌 Jen tento soubor chip beside 📎 flips the same setting (the
   panel shows it, the tool list grows / shrinks); "Zobrazit tagy pod chatem" off hides the row;
5. 💾 Save (the Save dialog stubbed) -> the .a3d has ai_settings; reload, open it -> the same settings (📌 on, the
   tags' row still hidden; shown again);
6. 🎨 Dekorace + Použít jako výchozí -> a reload (a new project) starts with them; the saved project keeps its own; an
   older project without settings gets the default;
no console errors, no native dialogs (confirm / alert / prompt unused).

The server must run with the stand-in:
  A3D_DATA=<scratch>/data AUTO3D_CLAUDE=<absolute path>/tools/fake_claude.py CLAUDE_CONFIG_DIR=<scratch>/claude py server.py --port 5199 --no-browser
  PYTHONIOENCODING=utf-8 py tools/e2e_ai_settings.py http://127.0.0.1:5199 <out dir> <scratch>/claude
"""
import base64
import json
import re
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from auto3d import package  # noqa: E402

URL, OUT, CLAUDE_DIR = sys.argv[1].rstrip("/"), Path(sys.argv[2]), Path(sys.argv[3])
OUT.mkdir(parents=True, exist_ok=True)
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1500,950")
opts.add_argument("--lang=cs-CZ")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
FAILS, COUNT = [], {"ok": 0}
NO_DIALOGS = ("window.__dialogs = []; for (const k of ['confirm', 'alert', 'prompt']) "
              "window[k] = (m) => { window.__dialogs.push(k + ': ' + m); return k === 'confirm'; };")
STUB = """window.__saved = null; window.showSaveFilePicker = async (o) => ({ name: o.suggestedName,
  createWritable: async () => ({ write: async (b) => { const u = new Uint8Array(await b.arrayBuffer()); let s = ''; for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode(...u.subarray(i, i + 0x8000)); window.__saved = btoa(s); }, close: async () => {} }) });"""
PANEL = "#aiDrawer .ai-settings"


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
    return js(script)


def page(reload=False):
    if reload:
        d.refresh()
    else:
        d.get(URL)
    wait("return !!window.__app && !!window.__chat")
    time.sleep(1)
    js(NO_DIALOGS)


def chat_open():
    """The chat in sight (the ✨ AI drawer of the 3D model)."""
    if not js("return !document.getElementById('aiDrawer').hidden"):
        d.find_element(By.ID, "aiBtn").click()
    wait("return !!document.querySelector('#aiDrawer textarea')?.offsetParent")


def new_model():
    js("document.getElementById('newModelBtn').click()")
    wait("return window.__app.state.workspace === 'model'")
    time.sleep(0.8)
    chat_open()


def panel(open_=True):
    shown = js(f"return !document.querySelector('{PANEL}').hidden")
    if shown != open_:
        d.find_element(By.CSS_SELECTOR, "#aiDrawer .ai-set").click()
    wait(f"return document.querySelector('{PANEL}').hidden === {'false' if open_ else 'true'}", 3)


def seg(k):
    """The buttons of a row: [(text, on)]."""
    return js(f"return [...document.querySelectorAll('{PANEL} .ais-seg[data-k={k}] button')].map(b => [b.textContent, b.classList.contains('on')])")


def on_of(k):
    return [t for t, on in seg(k) if on]


def click_seg(k, v):
    d.find_element(By.CSS_SELECTOR, f"{PANEL} .ais-seg[data-k={k}] button[data-v={v}]").click()
    time.sleep(0.15)


def toggles():
    return js(f"return Object.fromEntries([...document.querySelectorAll('{PANEL} .ais-tog input[data-k]')].map(c => [c.dataset.k, c.checked]))")


def toggle(k):
    d.find_element(By.CSS_SELECTOR, f"{PANEL} .ais-tog input[data-k={k}]").click()
    time.sleep(0.15)


def sent():
    """The text the stand-in Claude got last (its newest session file's last line)."""
    files = sorted((CLAUDE_DIR / "projects" / "fake").glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    return json.loads(files[-1].read_text(encoding="utf-8").splitlines()[-1])["text"] if files else ""


def say(text, enter=True):
    n = js("return document.querySelectorAll('#aiDrawer .ai-msg.assistant').length")
    ta = d.find_element(By.CSS_SELECTOR, "#aiDrawer textarea")
    if text:
        ta.send_keys(text)
    if enter:
        ta.send_keys(Keys.ENTER)
    wait(f"return document.querySelectorAll('#aiDrawer .ai-msg.assistant').length > {n} && !window.__chat.busy", 45)
    return js("const a = document.querySelectorAll('#aiDrawer .ai-msg.assistant'); return a[a.length - 1]?.textContent || ''")


try:
    for f in (CLAUDE_DIR / "projects" / "fake").glob("*.jsonl"):
        f.unlink()
    page()
    js("localStorage.removeItem('a3d.aiSettings')")
    page(reload=True)
    print("1. the ✨ Nastavení panel: profiles set the toggles, a change -> Vlastní")
    new_model()
    btn = d.find_element(By.CSS_SELECTOR, "#aiDrawer .ai-set")
    check("the chat's head: ✨ Nastavení", btn.text == "✨ Nastavení", btn.text)
    panel(True)
    check("the panel in place of the log", js(f"return !!document.querySelector('{PANEL}').offsetParent && document.querySelector('#aiDrawer .ai-log').hidden"))
    head = js(f"return document.querySelector('{PANEL} .ais-head b').textContent")
    titles = js(f"return [...document.querySelectorAll('{PANEL} .ais-h')].map(h => h.textContent)")
    check("Czech: Nastavení AI, Profil návrhu, Výroba, Ptát se před návrhem, Odpovědi, Chování",
          head == "✨ Nastavení AI" and titles == ["Profil návrhu", "Výroba", "Ptát se před návrhem", "Odpovědi", "Chování"], (head, titles))
    check("the profiles", [t for t, _ in seg("profile")] == ["⚙ Automatizace / ICT", "🖨 Funkční tisk", "🎨 Dekorace", "✎ Vlastní"], seg("profile"))
    check("the default: Automatizace, CNC, Jen klíčové rozměry, Stručně",
          (on_of("profile"), on_of("make"), on_of("ask"), on_of("answers")) == (["⚙ Automatizace / ICT"], ["CNC obrábění"], ["Jen klíčové rozměry"], ["Stručně"]),
          (on_of("profile"), on_of("make"), on_of("ask"), on_of("answers")))
    tg = toggles()
    check("the default toggles: rules on, 🌐 internet on, teach / bugs / lean off",
          tg == {"standard": True, "dfm": True, "dfa": True, "review": True, "teach": False, "bugs": False, "internet": True, "lean": False}, tg)
    labels = js(f"return [...document.querySelectorAll('{PANEL} .ais-tog')].map(l => l.textContent.trim())")
    check("the toggles in Czech with their cost", labels[:4] == ["📦 Standardizace dílů+0", "🏭 Jednoduchá výroba+0", "🔩 Snadná montáž+0", "🔍 Kontrola návrhu+3–6 tis."]
          and "📌 Omezit AI na aktuálně otevřený soubor−12–18 tis." in labels and "🌐 Hledat díly na internetu" in labels, labels)
    check("the old name is gone", "Úsporný" not in js(f"return document.querySelector('{PANEL}').textContent"))
    click_seg("profile", "deco")
    tg = toggles()
    check("🎨 Dekorace: 3D tisk, the rules off", on_of("make") == ["3D tisk"] and not any(tg[k] for k in ("standard", "dfm", "dfa", "review")), (on_of("make"), tg))
    click_seg("profile", "automation")
    tg = toggles()
    check("⚙ Automatizace: CNC, the rules on", on_of("make") == ["CNC obrábění"] and all(tg[k] for k in ("standard", "dfm", "dfa", "review")), (on_of("make"), tg))
    est0 = js(f"return document.querySelector('{PANEL} .ais-est').textContent")
    toggle("dfa")
    check("🔩 off -> ✎ Vlastní", on_of("profile") == ["✎ Vlastní"], on_of("profile"))
    toggle("bugs")
    est1 = js(f"return document.querySelector('{PANEL} .ais-est').textContent")
    nums = lambda s: [int(x) for x in re.findall(r"\d+", s)]  # noqa: E731
    check(f"🐞 raises the estimate ({est0} -> {est1})", "tis. tokenů na úkol" in est1 and nums(est1)[0] > nums(est0)[0], (est0, est1))
    toggle("bugs")
    click_seg("make", "laser")
    check("výroba: several at once", on_of("make") == ["CNC obrábění", "Laser / plech"], on_of("make"))
    d.save_screenshot(str(OUT / "ai-settings-panel.png"))

    print("2. 🖨 Funkční tisk; the line goes with the first message, not with an unchanged second one")
    click_seg("profile", "print")
    check("🖨 Funkční tisk: 3D tisk, rules on", on_of("make") == ["3D tisk"] and toggles()["dfa"], (on_of("make"), toggles()))
    d.find_element(By.CSS_SELECTOR, f"{PANEL} .ais-done").click()
    check("Hotovo: the log back", wait("return !document.querySelector('#aiDrawer .ai-log').hidden", 3))
    r1 = say("Udělej držák telefonu")
    got = sent()
    check("Claude gets the settings line first", got.startswith("[Nastavení: profil=tisk; výroba=3D-tisk; ptát=klíčové; odpovědi=stručně; "
                                                                 "zásady=standard-parts,print-functional,easy-assembly,design-review; režimy=-; internet=ano]\n\nUdělej držák"), got)
    check("the answer is about the message (the line not in it)", r1.startswith("Echo #1: Udělej držák telefonu"), r1)
    check("the bubble shows the message only", js("return [...document.querySelectorAll('#aiDrawer .ai-msg.user')].pop().textContent") == "Udělej držák telefonu")
    say("Přidej díru Ø5")
    check("a second message, nothing changed: no line", sent() == "Přidej díru Ø5", sent())

    print("3. # tags: the list, Enter / Tab, chips, the line for that message")
    ta = d.find_element(By.CSS_SELECTOR, "#aiDrawer textarea")
    ta.send_keys("#u")
    menu = wait("return !document.querySelector('#aiDrawer .ai-tagmenu').hidden && document.querySelector('#aiDrawer .ai-tagmenu').textContent", 3)
    check("'#u': the list offers #uc (Uč mě)", menu and "#uc" in menu and "Uč mě" in menu, menu)
    ta.send_keys(Keys.ENTER)
    check("Enter puts it in (not sent)", ta.get_attribute("value") == "#uc " and js("return document.querySelector('#aiDrawer .ai-tagmenu').hidden"), ta.get_attribute("value"))
    ta.send_keys("zaobli hrany #cn")
    wait("return document.querySelector('#aiDrawer .ai-tagmenu').textContent.includes('#cnc')", 3)
    ta.send_keys(Keys.TAB)
    check("Tab puts #cnc in", ta.get_attribute("value") == "#uc zaobli hrany #cnc ", ta.get_attribute("value"))
    r3 = say("", enter=True)
    got = sent()
    user = js("const u = [...document.querySelectorAll('#aiDrawer .ai-msg.user')].pop(); return [u.firstChild.textContent, [...u.querySelectorAll('.ai-chip')].map(c => c.textContent)]")
    check("the bubble: the text without the tags, chips #uc #cnc", user == ["zaobli hrany", ["#uc", "#cnc"]], user)
    check("the tags out of what Claude reads", got.endswith("\n\nzaobli hrany") and "#uc" not in got, got)
    check("the line for that message: výroba=CNC, režimy=teach-me", "výroba=CNC;" in got and "zásady=standard-parts,machined-part," in got and "režimy=teach-me;" in got, got)
    say("A teď normálně")
    check("the next message: the project's settings again", sent().startswith("[Nastavení: profil=tisk; výroba=3D-tisk;") and "režimy=-" in sent(), sent())
    say("hrany #kontrola")  # (a tag typed whole, the list open: one Enter sends)
    check("a tag typed whole + Enter: sent at once (#kontrola changes nothing here: no line)", sent() == "hrany" and js(
        "return [...[...document.querySelectorAll('#aiDrawer .ai-msg.user')].pop().querySelectorAll('.ai-chip')].map(c => c.textContent)") == ["#kontrola"], sent())

    print("4. 📌 Omezit AI na aktuálně otevřený soubor: fewer tools")
    r = say("TOOLS? kolik")
    full = int(re.search(r"tools: (\d+)", r).group(1)) if "tools:" in r else 0
    check(f"all the tools without it ({full})", full > 100, r)
    panel(True)
    toggle("lean")
    check("📌 on: the estimate drops", "−12–18" in js(f"return document.querySelector('{PANEL}').textContent"))
    panel(False)
    notes = js("return document.querySelectorAll('#aiDrawer .ai-msg.note').length")
    r = say("TOOLS? a teď")
    lean = int(re.search(r"tools: (\d+)", r).group(1)) if "tools:" in r else 0
    check(f"📌 the 3D model's tools only: {full} -> {lean}", 0 < lean < full * 0.6, r)
    check("the session went on (resumed: its message #7)", r.startswith("Echo #7:") and "resumed: " in r and "resumed: no" not in r, r)
    check("unseen: no 'stopped' note", js("return document.querySelectorAll('#aiDrawer .ai-msg.note').length") == notes)
    check("the line says omezení=soubor (not režimy=lean)", "omezení=soubor]" in sent() and "režimy=-" in sent(), sent())
    check("📌 Jen tento soubor under the box: on", js("return document.querySelector('#aiDrawer .ai-pin').classList.contains('on')"))
    check("🌐 on: Claude may search the web", r.endswith("web: yes"), r)
    panel(True)
    toggle("internet")
    panel(False)
    r = say("TOOLS? bez internetu")
    check("🌐 off: started again without web search, the session resumed", r.endswith("web: no") and "resumed: no" not in r, r)
    check("the line says internet=ne", "internet=ne;" in sent(), sent())
    panel(True)
    toggle("internet")
    panel(False)
    d.save_screenshot(str(OUT / "ai-settings-chat.png"))

    print("4b. the tags' row under the box; the 📌 quick toggle; hiding the row")
    geo = js("const q = (s) => document.querySelector('#aiDrawer ' + s).getBoundingClientRect(); const a = q('textarea'), b = q('.ai-tagbar'), c = q('.ai-send');"
             "return [a.bottom, b.top, b.bottom, b.height, c.top]")
    check(f"the row under the box, thin ({geo[3]:.0f} px), above the buttons", geo[1] >= geo[0] - 1 and geo[3] <= 20 and geo[2] <= geo[4] + 1, geo)
    chips = js("return [...document.querySelectorAll('#aiDrawer .ai-tagchip')].map(b => [b.textContent, b.title])")
    check("the chips #uc #chyby #kontrola #rychle #cnc #tisk #bez-otazek", [c[0] for c in chips] == ["#uc", "#chyby", "#kontrola", "#rychle", "#cnc", "#tisk", "#bez-otazek"], chips)
    check("their tooltips in Czech", all(c[1].startswith("Pro tuto zprávu: ") for c in chips) and "navrhnout pro CNC obrábění" in chips[4][1], chips)
    ta = d.find_element(By.CSS_SELECTOR, "#aiDrawer textarea")
    ta.send_keys("díra Ø5")
    ta.send_keys(Keys.HOME)
    cnc = d.find_element(By.CSS_SELECTOR, "#aiDrawer .ai-tagchip[data-tag=cnc]")
    cnc.click()
    v = ta.get_attribute("value")
    check("a click puts #cnc in at the cursor", v == "#cnc díra Ø5", v)
    check("its chip lit, the box keeps the focus", "on" in cnc.get_attribute("class") and js("return document.activeElement.tagName") == "TEXTAREA")
    cnc.click()
    v = ta.get_attribute("value")
    check("a second click takes it out", v == "díra Ø5" and "on" not in cnc.get_attribute("class"), v)
    ta.send_keys(Keys.END)
    cnc.click()
    check("at the end: '… #cnc '", ta.get_attribute("value") == "díra Ø5 #cnc ", ta.get_attribute("value"))
    js("const t = document.querySelector('#aiDrawer textarea'); t.value = ''; t.dispatchEvent(new Event('input'))")
    check("cleared: no chip lit", not js("return document.querySelectorAll('#aiDrawer .ai-tagchip.on').length"))
    pin = d.find_element(By.CSS_SELECTOR, "#aiDrawer .ai-pin")
    check("📌 Jen tento soubor (Czech tooltip: Zapnuto)", pin.text == "📌 Jen tento soubor" and pin.get_attribute("title").startswith("Zapnuto: "), (pin.text, pin.get_attribute("title")))
    pin.click()
    time.sleep(0.2)
    check("📌 off: unlit, the tooltip Vypnuto", "on" not in pin.get_attribute("class") and pin.get_attribute("title").startswith("Vypnuto: "), pin.get_attribute("title"))
    panel(True)
    check("the panel shows it off", toggles()["lean"] is False, toggles())
    panel(False)
    r = say("TOOLS? zase vše")
    n = int(re.search(r"tools: (\d+)", r).group(1)) if "tools:" in r else 0
    check(f"📌 off: all the tools again ({n})", n == full and "resumed: no" not in r, r)
    check("the line without omezení", "omezení" not in sent() and sent().startswith("[Nastavení:"), sent())
    pin.click()
    time.sleep(0.2)
    panel(True)
    check("📌 on again: the panel shows it", toggles()["lean"] is True, toggles())
    panel(False)
    r = say("TOOLS? zase jen soubor")
    n = int(re.search(r"tools: (\d+)", r).group(1)) if "tools:" in r else 0
    check(f"📌 on: the file's tools only ({n})", n == lean and "resumed: no" not in r, r)
    panel(True)
    tb = d.find_element(By.CSS_SELECTOR, f"{PANEL} .ais-tagbar")
    lab = js(f"return document.querySelector('{PANEL} .ais-ui').textContent.trim()")
    check("the panel: 'Zobrazit tagy pod chatem' on", lab == "Zobrazit tagy pod chatem" and tb.is_selected(), lab)
    tb.click()
    time.sleep(0.15)
    panel(False)
    check("off: the row hidden, the box and 📌 stay", js("return document.querySelector('#aiDrawer .ai-tagbar').hidden && !!document.querySelector('#aiDrawer .ai-pin').offsetParent"))
    ta.send_keys("#ko")
    check("the # list still works", wait("return document.querySelector('#aiDrawer .ai-tagmenu').textContent.includes('#kontrola')", 3))
    js("const t = document.querySelector('#aiDrawer textarea'); t.value = ''; t.dispatchEvent(new Event('input'))")
    d.save_screenshot(str(OUT / "ai-settings-tagbar.png"))

    print("5. 💾 Save -> the .a3d keeps them; reload + open -> the same")
    js(STUB)
    d.find_element(By.ID, "saveBtn").click()
    check("saved", wait("return !!window.__saved", 20))
    raw = base64.b64decode(js("return window.__saved"))
    proj = package.load(raw)["project"]
    ai = proj.get("ai_settings") or {}
    check("the project file has ai_settings (print, lean)", ai.get("profile") == "print" and ai.get("lean") is True, ai)
    saved = OUT / "ai-settings.a3d"
    saved.write_bytes(raw)
    page()
    get = "return import('/js/aisettings.js').then(m => arguments[0](m.aiSettings.get()))"
    s0 = d.execute_async_script(get)
    check("fresh page: Automatizace (the app's default)", s0["profile"] == "automation" and not s0["lean"], s0)
    d.find_element(By.ID, "projectInput").send_keys(str(saved))
    wait("return document.querySelectorAll('#partTabs .part-tab').length === 1 && window.__app.state.workspace === 'model'", 30)
    time.sleep(0.8)
    s1 = d.execute_async_script(get)
    check("opened: its settings (Funkční tisk, 📌)", s1["profile"] == "print" and s1["lean"] and s1["make"] == ["print"], s1)
    chat_open()
    panel(True)
    check("the panel shows them", on_of("profile") == ["🖨 Funkční tisk"] and toggles()["lean"], (on_of("profile"), toggles()))
    check("after the reload: 📌 on, the tags' row still hidden", js("return document.querySelector('#aiDrawer .ai-pin').classList.contains('on') && document.querySelector('#aiDrawer .ai-tagbar').hidden"))
    d.find_element(By.CSS_SELECTOR, f"{PANEL} .ais-tagbar").click()
    check("shown again from the panel", js("return !document.querySelector('#aiDrawer .ai-tagbar').hidden"))

    print("6. Použít jako výchozí -> a new project starts with them")
    click_seg("profile", "deco")
    click_seg("answers", "normal")
    check("not the default yet: 'Použít jako výchozí' offered", js(f"return !document.querySelector('{PANEL} .ais-default').hidden"))
    d.find_element(By.CSS_SELECTOR, f"{PANEL} .ais-default").click()
    check("kept: 'Výchozí nastavení aplikace'", wait(f"return !document.querySelector('{PANEL} .ais-isdef').hidden && document.querySelector('{PANEL} .ais-isdef').textContent", 3)
          == "Výchozí nastavení aplikace")
    page()
    s2 = d.execute_async_script(get)
    check("a new project: Dekorace, Normálně", s2["profile"] == "deco" and s2["answers"] == "normal" and s2["make"] == ["print"], s2)
    d.find_element(By.ID, "projectInput").send_keys(str(saved))
    wait("return document.querySelectorAll('#partTabs .part-tab').length === 1 && window.__app.state.workspace === 'model'", 30)
    time.sleep(0.8)
    s3 = d.execute_async_script(get)
    check("the saved project keeps its own (Funkční tisk)", s3["profile"] == "print", s3)
    old = {k: v for k, v in proj.items() if k != "ai_settings"}
    older = OUT / "ai-settings-older.a3d"
    older.write_bytes(package.write(old, None)[0])
    d.find_element(By.ID, "projectInput").send_keys(str(older))
    time.sleep(2.5)
    s4 = d.execute_async_script(get)
    check("an older project without them: the default (Dekorace)", s4["profile"] == "deco", s4)
    js("localStorage.removeItem('a3d.aiSettings'); localStorage.removeItem('a3d.chatTags')")

    errors = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    check("no console errors", not errors, errors)
    check("no native dialogs", js("return window.__dialogs") == [], js("return window.__dialogs"))
except Exception as exc:  # noqa: BLE001
    import traceback
    traceback.print_exc()
    FAILS.append(f"crashed: {exc}")
    d.save_screenshot(str(OUT / "ai-settings-crash.png"))
finally:
    d.quit()

print(f"\n{COUNT['ok']} ok, {len(FAILS)} failed" + (": " + "; ".join(FAILS) if FAILS else ""))
sys.exit(1 if FAILS else 0)
