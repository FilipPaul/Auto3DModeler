"""⏺ The recording of moves, in headless Edge, in Czech, with real mouse input: the top bar's ⏺ starts it -> the red pill
"Nahrávám pohyby · 0:00 · ■ Zastavit" at the top centre of the 3D view -> a block made through the UI (✏ Skica na
rovině from the table, a rectangle clicked, ✓ Hotovo, the extrude's distance typed 0 -> OK: the error toast, then 10 -> OK)
-> the top face clicked (a click event with its place, the button and the face under it) -> a table row run (◎ Díra) ->
Esc -> Ctrl+Z -> a drag with the button held (one drag event: its points, from / to) -> an assembly: the pill there too
-> get_recording (the page's handler and /api/agent/call): the events in order with their ids and the toast's text,
paths: false leaves the points out, a screenshot (get_recording_screenshot) -> ■ Zastavit hides the pill -> the chat's
📎 Přiložit záznam (n událostí) -> a reload: still offered, attached -> the events in the next message (caught before the
server), still offered -> ➤ Zastavit a poslat AI on the pill: stopped and sent -> ▾ the last two recordings, the older one
sent -> the AI's start_recording: "(spustila AI)" -> a reload: it goes on (a reload event)
-> stop_recording -> cheap: a long recording (2000 events, 12 pictures), a 2 s orbit, 25 clicks + 25 keys, an error:
under 2 ms per recorder handler call, no recorder run over 50 ms (the CDP profiler), the session's copy a small header
and chunks. Console errors: none.

  PYTHONIOENCODING=utf-8 py tools/e2e_recording.py http://127.0.0.1:5199 <out dir>
"""
import base64
import json
import sys
import time
import urllib.request
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

URL, OUT = sys.argv[1], Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1400,900")
opts.add_argument("--lang=cs-CZ")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"
SK = f"{M}.sk"
H = "window.__app.agentHandlers"
FAILS, COUNT = [], {"ok": 0}


def check(what, ok, got=None):
    print(("  ok   " if ok else "  FAIL ") + what + ("" if ok or got is None else f" -> {str(got)[:600]}"))
    if ok:
        COUNT["ok"] += 1
    else:
        FAILS.append(what)


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.15)
    raise TimeoutError(script)


def settle():
    time.sleep(0.4)
    wait(f"return !{M}.inflight", 150)
    time.sleep(0.4)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r).catch(e => ({{text: 'ERROR ' + e.message}}))", tool_name, args)


def recording(**args):
    return json.loads(call("get_recording", **args)["text"])


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#modelViewport canvas")


def off_uv(uv):
    return js(f"""const m = {M}, v = m.view, f = m.frame(), [u, w] = arguments[0];
      const y = [f.n[1]*f.x[2]-f.n[2]*f.x[1], f.n[2]*f.x[0]-f.n[0]*f.x[2], f.n[0]*f.x[1]-f.n[1]*f.x[0]];
      const p = new (v.camera.position.constructor)(f.o[0] + u*f.x[0] + w*y[0], f.o[1] + u*f.x[1] + w*y[1], f.o[2] + u*f.x[2] + w*y[2]);
      const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(uv))


def off_xyz(p):
    return js(f"""const v = {M}.view, [x, y, z] = arguments[0];
      const [sx, sy] = v.toScreen(new (v.camera.position.constructor)(x, y, z)), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(p))


def free_spot(o):
    return js("""const c = document.querySelector('#modelViewport canvas').getBoundingClientRect(), [dx, dy] = arguments[0];
      const el = document.elementFromPoint(Math.floor(c.left + c.width / 2) + dx, Math.floor(c.top + c.height / 2) + dy);
      return !!el && el.tagName === 'CANVAS';""", list(o))


def click(o):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *o).perform()
    time.sleep(0.2)
    ActionChains(d).click().perform()
    time.sleep(0.5)


def row(label):
    """Click the suggestions table's row with `label` (real mouse)."""
    for b in d.find_elements(By.CSS_SELECTOR, "#modelViewport .view-suggest .vs-list button:not(.vs-more)"):
        if label in " ".join(b.text.split()):
            ActionChains(d).move_to_element(b).click().perform()
            time.sleep(0.6)
            return True
    raise RuntimeError(f"no row {label}")


def pill():
    return js("""const p = document.querySelector('.rec-pill'); if (!p || p.hidden) return null; const r = p.getBoundingClientRect(),
      v = [...document.querySelectorAll('section.viewport')].find((x) => x.offsetParent && x.getBoundingClientRect().width > 0)?.getBoundingClientRect();
      return {text: p.textContent.replace(/\\s+/g, ' ').trim(), cx: r.left + r.width / 2, top: r.top, vcx: v ? v.left + v.width / 2 : null, vtop: v ? v.top : null, vid: [...document.querySelectorAll('section.viewport')].find((x) => x.offsetParent && x.getBoundingClientRect().width > 0)?.id};""")


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.setItem('auto3d-lang', 'cs'); localStorage.removeItem('a3d.suggestTop'); localStorage.removeItem('a3d.box.suggest'); sessionStorage.removeItem('a3d.suggestAll'); sessionStorage.removeItem('a3d.rec'); sessionStorage.removeItem('a3d.recShots')")
    d.get(URL)
    wait("return !!window.__app && document.documentElement.lang === 'cs'")
    d.find_element(By.ID, "newModelBtn").click()
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.5)
    d.find_element(By.CSS_SELECTOR, "#modelViewport [data-a=cancelSketch]").click()
    settle()

    print("1. ⏺ in the top bar starts it: the pill at the top centre of the 3D view")
    btn = d.find_element(By.ID, "recBtn")
    check("the ⏺ switch has a Czech tooltip", "Záznam pohybů" in (btn.get_attribute("title") or ""), btn.get_attribute("title"))
    ActionChains(d).move_to_element(btn).click().perform()
    time.sleep(1.2)
    p = pill()
    check("the pill shows: Nahrávám pohyby · 0:0x · ■ Zastavit", p and "Nahrávám pohyby" in p["text"] and "Zastavit" in p["text"] and "0:0" in p["text"], p)
    check("…at the top centre of the 3D view", p and p["vid"] == "modelViewport" and abs(p["cx"] - p["vcx"]) < 3 and 0 <= p["top"] - p["vtop"] < 120, p)
    check("the ⏺ switch is on", "on" in btn.get_attribute("class"))
    d.save_screenshot(str(OUT / "rec_01_pill.png"))

    print("2. a block made through the UI")
    row("Skica na rovině")
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.4)
    click(off_uv((-20, -15)))
    click(off_uv((20, 15)))
    check("a rectangle drawn", js(f"return {SK}.f.entities.filter(e => e.t === 'line').length") == 4)
    row("Vybrat tvar")
    click(off_uv((0, -15)))  # the bottom line's middle
    row("Jeho délka")
    inp = wait("return document.activeElement && document.activeElement.tagName === 'INPUT' && document.activeElement")
    inp.send_keys(Keys.CONTROL, "a")
    inp.send_keys("0", Keys.ENTER)
    time.sleep(0.8)
    toast = js("return [...document.querySelectorAll('#toasts .toast.error')].map(t => t.textContent).join(' | ')")
    check("the line's length typed 0: an error toast", "větší než nula" in toast, toast)
    d.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    time.sleep(0.3)
    row("Hotovo")
    wait(f"return {M}.cmd && {M}.cmd.feature.type === 'extrude'")
    time.sleep(0.5)
    dist = d.find_element(By.CSS_SELECTOR, "#modelRight input[data-k=d]")
    dist.send_keys(Keys.CONTROL, "a")
    dist.send_keys("10", Keys.TAB)
    time.sleep(0.4)
    d.find_element(By.CSS_SELECTOR, "#modelViewport .view-actions [data-a=ok], #modelRight [data-a=ok]").click()
    settle()
    check("a solid", js(f"return {M}.result?.body?.volume || 0") > 1000)
    time.sleep(5.2)  # (a screenshot at most every 5 s: the next key moment gets one)

    print("3. the top face clicked (real mouse), a table row run, Esc, Ctrl+Z")
    spot = next((o for o in (off_xyz(q) for q in ((5, 5, 10), (-8, 6, 10), (10, -5, 10), (0, 0, 10))) if free_spot(o)), None)
    click(spot)
    wait("return !!document.querySelector('#modelViewport .view-suggest')")
    n_steps = js(f"return {M}.part.features.length")
    row("Díra")
    wait(f"return {M}.cmd?.feature?.type === 'hole'")
    d.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    wait(f"return !{M}.cmd")
    settle()
    ActionChains(d).key_down(Keys.CONTROL).send_keys("z").key_up(Keys.CONTROL).perform()
    wait(f"return {M}.part.features.length === {n_steps}")
    settle()

    print("4. a drag with the left button held (the view turned)")
    c = canvas()
    ActionChains(d, duration=40).move_to_element_with_offset(c, 250, -150).perform()
    ch = ActionChains(d, duration=40).click_and_hold()
    for k in range(1, 9):
        ch.move_by_offset(-18, 9).pause(0.07)
    ch.release().perform()
    time.sleep(0.6)

    print("5. an assembly: the pill goes along")
    call("new_assembly", name="Sestava")
    time.sleep(1.5)
    p = pill()
    check("the pill in the assembly's view, at its top centre", p and p["vid"] == "asmViewport" and abs(p["cx"] - p["vcx"]) < 3, p)
    d.save_screenshot(str(OUT / "rec_02_assembly.png"))

    print("6. get_recording: the events in order")
    r = recording()
    ev = r["events"]
    kinds = [e["kind"] for e in ev]
    print("   ", " · ".join(kinds))
    (OUT / "rec_events.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1), encoding="utf-8")
    def first(pred, after=-1):
        return next((e["i"] for e in ev if e["i"] > after and pred(e)), None)
    i_start = first(lambda e: e["kind"] == "start" and e["by"] == "user")
    i_sketch_row = first(lambda e: e["kind"] == "suggest" and "Skica na rovině" in e.get("row", ""), i_start)
    i_len = first(lambda e: e["kind"] == "suggest" and "Jeho délka" in e.get("row", ""), i_sketch_row)
    i_val0 = first(lambda e: e["kind"] == "value" and e.get("value") == "0", i_len)
    i_toast = first(lambda e: e["kind"] == "toast" and e["level"] == "error", i_val0)
    i_sketch = first(lambda e: e["kind"] == "step added" and e.get("type") == "sketch", i_toast)
    i_val10 = first(lambda e: e["kind"] == "value" and e.get("value") == "10", i_sketch)
    i_extr = first(lambda e: e["kind"] == "step added" and e.get("type") == "extrude", i_val10)
    i_click = first(lambda e: e["kind"] == "click" and "face F2:end" in e.get("on", ""), i_extr)
    i_sel = first(lambda e: e["kind"] == "select" and "F2" in str(e.get("what")), i_click)
    i_hole = first(lambda e: e["kind"] == "suggest" and "Díra" in e.get("row", ""), i_sel)
    i_esc = first(lambda e: e["kind"] == "key" and e["key"] == "Escape", i_hole)
    i_undo = first(lambda e: e["kind"] == "undo", i_esc)
    i_drag = first(lambda e: e["kind"] == "drag", i_undo)
    i_switch = first(lambda e: e["kind"] == "switch" and "assembly" in e["to"], i_drag)
    order = [i_start, i_sketch_row, i_len, i_val0, i_toast, i_sketch, i_val10, i_extr, i_click, i_sel, i_hole, i_esc, i_undo, i_drag, i_switch]
    check("start → ✏ row → ↔ length row → 0 typed → error toast → sketch added → 10 typed → extrude added → face clicked → selected → ◎ row → Esc → undo → drag → switch",
          all(x is not None for x in order) and order == sorted(order), order)
    by = {e["i"]: e for e in ev}
    te = by.get(i_toast, {})
    check("the toast's text and a screenshot of it", "nula" in te.get("text", "") and te.get("shot"), te)
    ce = by.get(i_click, {})
    check("the click: left button, its place (view 0 … 1 and screenshot px), the face under it", ce.get("button") == "left" and len(ce.get("at", [])) == 2
          and all(0 < v < 1 for v in ce["at"]) and len(ce.get("px", [])) == 2, ce)
    he = by.get(i_hole, {})
    check("the row run: its label, the table and what was selected", "Díra" in he.get("row", "") and he.get("table") and "F2" in he.get("about", ""), he)
    de = by.get(i_drag, {})
    check("the drag: one event, left button, of the view, several points (start … end), from / to", de.get("button") == "left" and de.get("of") == "view"
          and len(de.get("path", [])) >= 4 and len(de["path_px"]) == len(de["path"]) and "from" in de and "to" in de and de["path"][0] != de["path"][-1], de)
    check("the extrude's step: its id", by.get(i_extr, {}).get("id") == "F2", by.get(i_extr))
    check("no plain mouse movement (no move events)", not any(k in ("move", "hover") for k in kinds))
    lean = recording(paths=False)["events"]
    dl = next(e for e in lean if e["kind"] == "drag")
    check("paths: false — the drag without its points (points, from_px, to_px)", "path" not in dl and dl["points"] == len(de["path"]) and dl["from_px"] == de["path_px"][0], dl)
    check("last: 3 — the last three", [e["i"] for e in recording(last=3)["events"]] == [e["i"] for e in ev[-3:]])
    check("since — from that index on", recording(since=i_undo)["events"][0]["i"] == i_undo)
    req = urllib.request.Request(f"{URL}/api/agent/call", data=json.dumps({"tool": "get_recording", "args": {"last": 2}}).encode(), headers={"Content-Type": "application/json"})
    out = json.loads(urllib.request.urlopen(req, timeout=60).read())
    via = json.loads(out["content"][0]["text"])
    check("/api/agent/call get_recording: running, the last 2 events", via["running"] and len(via["events"]) == 2, out)
    shot = call("get_recording_screenshot", id=te.get("shot") or "S1")
    if shot.get("image"):
        (OUT / "rec_shot.png").write_bytes(base64.b64decode(shot["image"]))
    check("get_recording_screenshot: a PNG", (shot.get("image") or "").startswith("iVBOR"), shot.get("text"))
    check("an unknown screenshot refused", call("get_recording_screenshot", id="S99")["text"].startswith("ERROR"))

    print("7. ■ Zastavit (real click): the pill goes")
    ActionChains(d).move_to_element(d.find_element(By.CSS_SELECTOR, ".rec-pill .rec-stop")).click().perform()
    time.sleep(0.5)
    check("stopped: no pill, the ⏺ switch off", pill() is None and "on" not in d.find_element(By.ID, "recBtn").get_attribute("class"))
    r = recording()
    check("get_recording: not running, the stop at the end", not r["running"] and r["events"][-1]["kind"] == "stop", r["events"][-1])

    print("8. the chat: 📎 Přiložit záznam (n událostí)")
    d.find_element(By.ID, "aiBtn").click()
    time.sleep(0.6)
    chip = js("const b = document.querySelector('#aiDrawer .ai-rec button'); return b && b.offsetParent ? b.textContent : null")
    check("the chip offers the stopped recording", chip and "Přiložit záznam" in chip and f"({r['count']} událostí)" in chip, chip)
    d.find_element(By.CSS_SELECTOR, "#aiDrawer .ai-rec button").click()
    time.sleep(0.3)
    chip = js("return document.querySelector('#aiDrawer .ai-rec button')?.textContent")
    check("one click: it goes with the message", chip and "Záznam se pošle" in chip, chip)
    d.find_element(By.ID, "aiBtn").click()
    time.sleep(0.3)

    print("8b. after a reload the chat still offers it; attaching puts the events in the next message (sent: still offered)")
    d.refresh()
    wait("return !!window.__app && !!window.__chat")
    time.sleep(1.5)
    js("window.__chat.onShow()")
    time.sleep(0.4)
    chip = js("const b = document.querySelector('#tab-ai .ai-rec .ai-rec-btn'); return b && b.offsetParent ? b.textContent : null")
    check("after a reload: 📎 Přiložit záznam (n událostí)", chip and f"({r['count']} událostí)" in chip, chip)
    # (the message is caught before the server: no AI needed)
    js("""window.__sent = []; window.__chat.access = {state: 'ok'}; window.__fetch0 = window.__fetch0 || window.fetch;
      window.fetch = (u, o) => { if (String(u).startsWith('/api/chat/send')) { window.__sent.push(JSON.parse(o.body).text); return Promise.resolve(new Response('{"ok":true}')); }
        return window.__fetch0(u, o); };""")
    d.find_element(By.CSS_SELECTOR, "#tab-ai .ai-rec .ai-rec-btn").click()
    ta = d.find_element(By.CSS_SELECTOR, "#tab-ai textarea")
    ta.send_keys("Co jsem dělal?")
    ta.send_keys(Keys.ENTER)
    sent = wait("return window.__sent[0]", 10)
    js("window.__chat.setBusy(false)")
    check("the message: the text, then the recording's events", sent.startswith("Co jsem dělal?") and f"[⏺ Recording of my moves: {r['count']} events" in sent
          and " stop — by: user" in sent, sent[:300])
    chip = js("return document.querySelector('#tab-ai .ai-rec .ai-rec-btn')?.textContent")
    check("sent once: still offered (always there while a stopped recording exists)", chip and "Přiložit záznam" in chip, chip)

    print("8c. ➤ Zastavit a poslat AI on the pill; ▾ the last recordings")
    first_count = r["count"]
    js("document.getElementById('recBtn').click()")
    time.sleep(0.4)
    for k in range(3):
        js("document.body.dispatchEvent(new KeyboardEvent('keydown', {key: 'F9', bubbles: true}))")
        time.sleep(0.1)
    p = pill()
    check("the pill: ■ Zastavit and ➤ Zastavit a poslat AI", p and "Zastavit a poslat AI" in p["text"], p)
    js("window.__chat.$('textarea').value = ''")
    ActionChains(d).move_to_element(d.find_element(By.CSS_SELECTOR, ".rec-pill .rec-send")).click().perform()
    sent = wait("return window.__sent[1]", 10)
    js("window.__chat.setBusy(false)")
    second = recording()
    check("stopped and sent at once: the new recording, the chat in sight", pill() is None and sent.startswith("Podívej se, co jsem dělal(a).")
          and f"[⏺ Recording of my moves: {second['count']} events" in sent and js("return !!document.querySelector('#tab-ai textarea').offsetParent"), sent[:200])
    more = d.find_elements(By.CSS_SELECTOR, "#tab-ai .ai-rec .ai-rec-more")
    check("▾ there (two recordings kept)", bool(more))
    if more:
        more[0].click()
        time.sleep(0.2)
        items = js("return [...document.querySelectorAll('#tab-ai .ai-rec-menu button')].map(b => b.textContent)")
        check("the menu: the last recordings with time, length, events", len(items) == 2 and f"{second['count']} událostí" in items[0]
              and f"{first_count} událostí" in items[1] and all(":" in x for x in items), items)
        d.find_elements(By.CSS_SELECTOR, "#tab-ai .ai-rec-menu button")[1].click()
        chip = js("return document.querySelector('#tab-ai .ai-rec .ai-rec-btn')?.textContent")
        check("the older one chosen: it goes with the message", chip and "Záznam se pošle" in chip, chip)
        ta = d.find_element(By.CSS_SELECTOR, "#tab-ai textarea")
        ta.send_keys("A tohle předtím")
        ta.send_keys(Keys.ENTER)
        sent = wait("return window.__sent[2]", 10)
        js("window.__chat.setBusy(false)")
        check("the older recording's events in the message", f"[⏺ Recording of my moves: {first_count} events" in sent, sent[:200])
    js("window.fetch = window.__fetch0")
    d.find_element(By.ID, "aiBtn").click() if js("return !document.getElementById('aiDrawer').hidden") else None
    time.sleep(0.3)

    print("9. the AI starts it: (spustila AI); a reload goes on")
    t = call("start_recording", reason="the user asked: look at the hole")["text"]
    time.sleep(1.2)
    p = pill()
    check("start_recording: the pill says (spustila AI)", p and "spustila AI" in p["text"], (t, p))
    d.refresh()
    wait("return !!window.__app")
    time.sleep(1.5)
    p = pill()
    r = recording()
    check("after a reload: still running, the pill there, a reload event", r["running"] and p and r["events"][-1]["kind"] in ("reload", "switch", "select")
          and any(e["kind"] == "reload" for e in r["events"]) and r["started_by"] == "ai", (p, r["events"][-3:]))
    t = call("stop_recording")["text"]
    check("stop_recording: stopped", pill() is None and "Stopped" in t, t)

    print("10. cheap while the user works: a long recording (2000 events, 12 pictures), a 2 s orbit, 50 clicks / keys, an error")
    call("start_recording", reason="perf")
    js("import('/js/recorder.js').then(m => { window.__rec = m.recorder; })")
    wait("return !!window.__rec")
    js("""const r = window.__rec, path = Array.from({length: 40}, (_, k) => [k / 40, 0.5]);
      for (let k = 0; k < 2000; k++) r.push(k % 5 ? 'click' : 'drag', k % 5 ? {button: 'left', at: [0.3, 0.4], px: [300, 400], on: 'face F2:end'}
        : {button: 'left', of: 'view', path, path_px: path.map(([x, y]) => [x * 1000, y * 800])});
      const big = 'iVBOR' + 'A'.repeat(150000); for (let k = 0; k < 12; k++) r.shots.push({id: 'P' + k, i: r.n - 1, t: 0, data: big});
      r.save(true); r.lastShot = {}; r.cost = {ms: 0, max: 0, n: 0}; window.__lt = [];
      new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__lt.push(Math.round(e.duration)); }).observe({type: 'longtask'});""")
    time.sleep(1.5)
    js("window.__rec.cost = {ms: 0, max: 0, n: 0}; window.__lt = [];")
    n0 = js("return window.__rec.n")
    d.execute_cdp_cmd("Profiler.enable", {})
    d.execute_cdp_cmd("Profiler.setSamplingInterval", {"interval": 100})
    d.execute_cdp_cmd("Profiler.start", {})
    vc = js("return [...document.querySelectorAll('section.viewport canvas')].find((c) => c.offsetParent && c.getBoundingClientRect().width > 100)")
    ActionChains(d, duration=0).move_to_element_with_offset(vc, 200, -120).perform()
    ch = ActionChains(d, duration=16).click_and_hold()
    for k in range(120):  # (2 s of orbiting)
        ch.move_by_offset(-4 if k < 60 else 4, 2 if k < 60 else -2).pause(0.016)
    ch.release().perform()
    for k in range(25):  # (on the view itself, not on a table / a panel over it)
        o = js("""const c = arguments[0].getBoundingClientRect(), cx = Math.floor(c.left + c.width / 2), cy = Math.floor(c.top + c.height / 2);
          for (let j = 0; j < 40; j++) { const dx = -300 + ((arguments[1] * 20 + j * 37) % 600), dy = 150 - (j * 23) % 300;
            const el = document.elementFromPoint(cx + dx, cy + dy); if (el === arguments[0]) return [dx, dy]; } return [0, 0];""", vc, k)
        ActionChains(d, duration=0).move_to_element_with_offset(vc, *o).click().perform()
        ActionChains(d).send_keys(Keys.ESCAPE).perform()
        time.sleep(0.05)
    js("const t = document.createElement('div'); t.className = 'toast error'; t.textContent = 'Test: an error'; document.getElementById('toasts').appendChild(t); setTimeout(() => t.remove(), 1500)")
    time.sleep(3)  # (the copy written, the picture taken)
    prof = d.execute_cdp_cmd("Profiler.stop", {})["profile"]
    parent = {c: n["id"] for n in prof["nodes"] for c in n.get("children", [])}
    nodes = {n["id"]: n for n in prof["nodes"]}
    mine = {}
    for nid in sorted(nodes):  # (a node is the recorder's when it or a caller is in recorder.js / its screenshot)
        k, chain = nid, []
        while k is not None and k not in mine:
            chain.append(k)
            cf = nodes[k]["callFrame"]
            if "recorder.js" in cf["url"] or cf["functionName"] == "screenshotUI":
                mine[k] = True
                break
            k = parent.get(k)
        hit = k is not None and mine.get(k, False)
        for c in chain:
            mine.setdefault(c, hit)
    total = run = longest = 0.0
    for s, dt in zip(prof["samples"], prof["timeDeltas"]):
        if mine.get(s):
            total += dt / 1000
            run += dt / 1000
            longest = max(longest, run)
        else:
            run = 0
    cost = js("return window.__rec.cost")
    got = js("""const r = window.__rec, h = JSON.parse(sessionStorage.getItem('a3d.rec'));
      return {n: r.n, keys: r.events.filter((e) => e.kind === 'key').length, clicks: r.events.slice(-80).filter((e) => e.kind === 'click').length,
        drag: r.events.slice(-80).filter((e) => e.kind === 'drag').length, shot: r.events.slice(-5).some((e) => e.kind === 'toast' && e.shot),
        header: sessionStorage.getItem('a3d.rec').length, chunks: h.chunks.length, stored: h.chunks.every((c) => sessionStorage.getItem('a3d.rec.c' + c)), lt: window.__lt};""")
    print(f"    recorder: {cost['n']} handler calls, {cost['ms']:.1f} ms, max {cost['max']:.1f} ms; CPU in it {total:.1f} ms, longest burst {longest:.1f} ms; long tasks {got['lt']}")
    check("all recorded: the orbit (a drag), 25 clicks, 25 keys, the error with its picture",
          got["n"] - n0 >= 51 and got["drag"] >= 1 and got["clicks"] >= 25 and got["shot"], got)
    check("under 2 ms per event in the recorder's handlers (max under 16 ms)", cost["n"] and cost["ms"] / cost["n"] < 2 and cost["max"] < 16, cost)
    check("no long task from the recorder (its longest run under 50 ms), its total CPU under 150 ms", longest < 50 and total < 150, (longest, total))
    check("the session's copy: a small header and chunks of events (not the whole log rewritten)", got["header"] < 5000 and got["chunks"] in (20, 21) and got["stored"], got)
    call("stop_recording")
finally:
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    check("no console errors", not errs, errs)
    print(f"\n{COUNT['ok']} ok, {len(FAILS)} failed" + (f": {FAILS}" if FAILS else ""))
    d.quit()
sys.exit(1 if FAILS else 0)
