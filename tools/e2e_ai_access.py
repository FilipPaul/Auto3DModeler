"""The AI's set-up screen (auto3d/ai_access.py), at any time while the app runs, in headless Edge: with no Claude sign-in
and no key the ✨ AI tab shows "Set up the AI assistant" (Sign in with Claude, an API key field, the register / console
links) instead of the chat; a text that is no key -> "not an Anthropic API key"; a fake key -> Anthropic refuses it
(a real request to api.anthropic.com) -> "refused", nothing kept; the screen in Czech; the rest of the app works the
same: a 3D model (rectangle -> extrude) builds. No console errors.

The server must see no Claude sign-in: start it with an empty Claude Code config folder (and no ANTHROPIC_API_KEY):
  CLAUDE_CONFIG_DIR=<empty dir> A3D_DATA=<dir> py server.py --port 5199 --no-browser
  PYTHONIOENCODING=utf-8 py tools/e2e_ai_access.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time
import urllib.request

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.add_argument("--lang=en-US")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"
fails = []


def check(ok, what, extra=""):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}{f' {extra}' if extra else ''}")
    if not ok:
        fails.append(what)


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def access():
    with urllib.request.urlopen(f"{URL}/api/ai/access", timeout=30) as r:
        return json.loads(r.read())


def shown(sel):
    return js(f"const e = document.querySelector('{sel}'); return !!e && !e.hidden && e.offsetParent !== null")


def use_key(key):
    js("document.querySelector('.ai-access .ai-acc-msg.err')?.remove()")  # (the answer's message is drawn anew)
    box = d.find_element(By.CSS_SELECTOR, ".ai-keyin")
    box.clear()
    box.send_keys(key)
    js("document.querySelector('.ai-usekey').click()")
    return wait("const m = document.querySelector('.ai-access .ai-acc-msg.err'); return m && m.textContent", 40)


def canvas():
    return d.find_element(By.CSS_SELECTOR, "#modelViewport canvas")


def offset_of(uv):
    return js(f"""const m = {M}, v = m.view, [u, w] = arguments[0], f = m.frame();
      const y = [f.n[1]*f.x[2]-f.n[2]*f.x[1], f.n[2]*f.x[0]-f.n[0]*f.x[2], f.n[0]*f.x[1]-f.n[1]*f.x[0]];
      const p = new (v.camera.position.constructor)(f.o[0] + u*f.x[0] + w*y[0], f.o[1] + u*f.x[1] + w*y[1], f.o[2] + u*f.x[2] + w*y[2]);
      const [sx, sy] = v.toScreen(p), r = v.renderer.domElement.getBoundingClientRect();
      return [Math.round(sx - Math.floor(r.left + r.width / 2)), Math.round(sy - Math.floor(r.top + r.height / 2))];""", list(uv))


def click_uv(uv):
    ActionChains(d, duration=30).move_to_element_with_offset(canvas(), *offset_of(uv)).perform()
    time.sleep(0.15)
    ActionChains(d).click().perform()
    time.sleep(0.2)


try:
    st = access()
    print("server's access state:", st["state"])
    check(st["state"] in ("signed_out", "invalid"), "the test server sees no sign-in and no key", st["state"])
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('auto3d-lang')")
    js("document.querySelector('.tab[data-tab=ai]').click()")
    wait("const e = document.querySelector('.ai-access'); return e && !e.hidden && e.textContent.includes('Set up')", 40)
    check(shown(".ai-access"), "the set-up screen is shown in the ✨ AI tab")
    check(not shown(".ai-form textarea"), "the chat's message box is hidden meanwhile")
    check(shown(".ai-signin"), "Sign in with Claude")
    check(shown(".ai-keyin") and shown(".ai-usekey"), "the API key field and Use this key")
    links = js("return [...document.querySelectorAll('.ai-access a')].map(a => a.href)")
    check(any("claude.ai" in h for h in links) and any("console.anthropic.com" in h for h in links), "register / console links", str(links))
    print("  status:", js("return document.querySelector('.ai-status').textContent"))
    d.save_screenshot(f"{OUT}/access_1_screen.png")

    msg = use_key("hello")
    check("not an Anthropic API key" in msg, "a text that is no key", msg)
    t0 = time.time()
    msg = use_key("sk-ant-api03-" + "fake0" * 16)
    check("refused" in msg, "a fake key: Anthropic refuses it", f"{msg} ({time.time() - t0:.1f} s)")
    st = access()
    check(st["state"] != "ok" and st.get("method") is None, "the refused key is not kept", st["state"])
    check(shown(".ai-access") and shown(".ai-signin"), "the set-up screen stays, ready for another try")
    d.save_screenshot(f"{OUT}/access_2_refused.png")

    # in Czech
    js("document.getElementById('langBtn').click()")
    time.sleep(0.5)
    h3 = js("return document.querySelector('.ai-access h3').textContent")
    check(h3 == "Nastavení AI asistenta", "the screen in Czech", h3)
    left = js("""const w = document.querySelector('.ai-access'); const out = [];
      const walk = document.createTreeWalker(w, NodeFilter.SHOW_TEXT);
      for (let n = walk.nextNode(); n; n = walk.nextNode()) { const t = n.nodeValue.trim();
        if (t.length > 3 && /\\b(the|and|key|with|your|Sign|Check)\\b/.test(t) && !n.parentElement.closest('code,[data-no-i18n]')) out.push(t); }
      return out;""")
    check(not left, "no English left on it", str(left))
    d.save_screenshot(f"{OUT}/access_3_cs.png")
    js("document.getElementById('langBtn').click()")
    js("localStorage.removeItem('auto3d-lang')")

    # the rest of the app: a 3D model builds
    js("document.querySelector('#newModelBtn').click()")
    wait(f"return {M}.mode === 'sketch'")
    time.sleep(0.5)
    click_uv((0, 0))
    click_uv((40, 20))
    js("document.querySelector('[data-a=finish]').click()")
    wait(f"return {M}.cmd && {M}.result?.body")
    time.sleep(0.5)
    wait(f"return !{M}.inflight")
    js("document.querySelector('#modelViewport .view-actions [data-a=ok]').click()")
    time.sleep(0.5)
    wait(f"return !{M}.inflight && {M}.result?.body")
    vol = js(f"return {M}.result.body.volume")
    check(vol and vol > 0, "the 3D model builds as before", f"volume {vol}")
    d.save_screenshot(f"{OUT}/access_4_model.png")
finally:
    errors = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE" and "/api/ai/key" not in e["message"]]
    check(not errors, "no console errors", str(errors))
    d.quit()
print("ALL OK" if not fails else f"FAILED: {fails}")
sys.exit(1 if fails else 0)
