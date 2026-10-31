"""✕ Cancel on the "Making the drawings… 45 / 250" card, in headless Edge (the page in Czech). The 150-part demo has
only 11 pages (its parts repeat): its set timed cold and warm (its drawings then forgotten again). For the cancel: a
machine of N different plates (made here through the AI's tools, saved as an .a3d in <out dir>); its drawing set
(📄 Výkresy (PDF) in the assembly's panel) started, cancelled after a few drawings -> no more started, then the app's
own question "Uložit hotové výkresy (n z m)? Příště se už nebudou dělat znovu." [Ano, uložit] [Ne, zahodit]
[Uložit a stáhnout PDF hotových] (never a native dialog):
  1. the 150-part demo: a cold and a warm full run timed (the drawings then forgotten: the sheet cache empty again);
  2. cancel -> Ne, zahodit: the next run finds none of them kept (its quick look at the server: no hits);
  3. that next run cancelled -> Ano, uložit (k drawings); the page reloaded, the demo opened again, the set run once
     more: the counter is at the kept count within seconds, only the rest is made (the server builds total − k parts)
     and the PDF has every page, numbered "n / N";
  4. reloaded again: a warm full run (all kept) timed — no part made at all.
No console errors. (The AI's drawing set has no stop: e2e_drawing_set's export pdf runs to the end.)

  A3D_DATA=<a scratch folder> py server.py --port 5199 --no-browser
  PYTHONIOENCODING=utf-8 py tools/e2e_drawing_cancel.py http://127.0.0.1:5199 <out dir>
"""
import base64
import re
import sys
import time
from pathlib import Path

import fitz
from selenium.webdriver.common.by import By

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_big_assembly import Builder  # noqa: E402

URL = sys.argv[1].rstrip("/")
OUT = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
DEMO = Path(__file__).resolve().parent.parent / "demos" / "velka-sestava-150.a3d"
MACHINE = OUT / "drawing-cancel-machine.a3d"
N = 48  # (different plates: N part pages)
A = "window.__app.assembly"
fails = []


def check(what, ok, info=""):
    print(("ok   " if ok else "FAIL ") + what + (f" — {info}" if info else ""))
    if not ok:
        fails.append(what)


b = Builder(URL)
d, js = b.d, b.js
# no native dialogs (counted if one comes); the saved PDF caught in the page; the sheet requests counted
d.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": """
  for (const k of ['alert', 'confirm', 'prompt']) window[k] = () => { localStorage.setItem('e2e.native', (+localStorage.getItem('e2e.native') || 0) + 1); return true; };
  window.__saved = []; window.showSaveFilePicker = async (o) => ({ name: o.suggestedName, createWritable: async () => ({
    write: async (bl) => { const u = new Uint8Array(await bl.arrayBuffer()); let s = ''; for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode(...u.subarray(i, i + 0x8000)); window.__saved.push([o.suggestedName, btoa(s)]); },
    close: async () => {} }) });
  window.__req = { only: 0, hits: 0, builds: 0 };
  const f0 = window.fetch;
  window.fetch = async (url, o) => {
    const r = await f0(url, o);
    if (String(url).endsWith('/api/sheet/build') && o?.body) {
      const c = JSON.parse(o.body).cache;
      if (c === 'only') { window.__req.only++; r.clone().json().then((j) => { if (j.hit) window.__req.hits++; }); }
      else if (c) window.__req.builds++;
    }
    return r;
  };
"""})


def open_demo(path=MACHINE):
    b.fresh()
    b.run("const I = await import('/js/i18n.js'); I.setLang('cs');")
    d.find_element(By.ID, "projectInput").send_keys(str(path.resolve()))
    b.wait(f"const A = {A}; return A.active && A.doc.instances.length > 0 && !window.__app.project.busy", 300)
    time.sleep(1.5)
    js(f"{A}.sel = null; {A}.render()")
    time.sleep(0.4)


def counter():
    """The card's "n / m" -> (n, m), or None."""
    t = js("const c = document.getElementById('loadCard'); return c && !c.hidden ? c.querySelector('.load-step').textContent : ''") or ""
    m = re.search(r"(\d+) / (\d+)", t)
    return (int(m[1]), int(m[2])) if m else None


def start():
    js("window.__req = { only: 0, hits: 0, builds: 0 }; window.__saved = []")
    d.find_element(By.CSS_SELECTOR, "#asmBom [data-a=drawingSet]").click()


def cancel_after(parts):
    """✕ Cancel once `parts` part drawings are made -> the counter then."""
    b.wait(f"return window.__req.builds >= {parts}", 600)
    at = counter()
    d.find_element(By.CSS_SELECTOR, "#loadCard .load-cancel").click()
    return at


def answer(word):
    """The question's text, then its button with `word` clicked."""
    b.wait("return [...document.querySelectorAll('.choose .btn')].some((x) => x.offsetParent)", 600)
    q = js("return document.querySelector('.choose p').textContent")
    btns = js("return [...document.querySelectorAll('.choose .btn')].map((x) => x.textContent.trim())")
    next(x for x in d.find_elements(By.CSS_SELECTOR, ".choose .btn") if word in x.text).click()
    time.sleep(0.5)
    return q, btns


def finished(t=900):
    """The run ended (its card gone) -> seconds."""
    t0 = time.time()
    b.wait("const c = document.getElementById('loadCard'); return !c || c.hidden", t)
    return time.time() - t0


try:
    b.fresh()
    js("localStorage.clear()")
    # 1. the 150-part demo: cold, then warm (the page's memory emptied: from the server's cache), then forgotten
    open_demo(DEMO)
    print("the button:", d.find_element(By.CSS_SELECTOR, "#asmBom [data-a=drawingSet]").text)
    RUN = """const P = window.__app.project, S = window.__app.sheet, t0 = performance.now(); S.cache = new Map();
      const ctx = { kindOf: (id) => P.parts.find((q) => q.id === id)?.kind, sheetOf: () => null, bought: (d, n) => !!d?.library };
      const s = await S.drawingSet(P.active, ctx); const ms = performance.now() - t0;
      return [s.total, s.svgs.length, s.made, s.cancelled, ms];"""
    FORGET = "await window.__app.sheet.forget(arguments[0])"
    cold = b.run(RUN)
    warm = b.run(RUN)
    b.run(FORGET, cold[2])
    gone = b.run(RUN)  # (forgotten: made anew)
    b.run(FORGET, gone[2])
    print(f"  the 150-part demo: {cold[0]} pages — cold {cold[4] / 1000:.1f} s ({len(cold[2])} drawings made), warm {warm[4] / 1000:.1f} s ({len(warm[2])} made)")
    check("150-part demo: every page, not cancelled; warm: nothing made; forgotten: made again", cold[1] == cold[0] and not cold[3] and not warm[2] and len(gone[2]) == len(cold[2]),
          [len(cold[2]), len(warm[2]), len(gone[2])])

    # the machine of N different plates (made once: <out dir>/drawing-cancel-machine.a3d)
    if not MACHINE.exists():
        b.fresh()
        t0 = time.time()
        for i in range(N):
            b.plate(f"Deska {i + 1:02}", 30 + i, 20 + (i * 7) % 30, 2 + i % 4, holes=[(-8, 0), (8, 0)])
        b.assembly("Stroj")
        ids = js("return window.__app.project.parts.filter((p) => p.kind === 'model').map((p) => p.id)")
        for i, pid in enumerate(ids):
            b.put(f"I{i + 1}", pid, [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 90 * (i % 8), 60 * (i // 8), 0, 1])
        print("  the machine:", b.done(), f"({time.time() - t0:.0f} s)")
        b.save(MACHINE, "Stroj", "Stroj")
    open_demo()

    # 2. cancel -> Ne, zahodit: nothing kept
    start()
    at = cancel_after(4)
    q, btns = answer("Ne, zahodit")
    print("  cancelled at", at, "| the question:", q, "|", btns)
    total = int(re.search(r" z (\d+)\)", q)[1])
    check("the question in Czech: Uložit hotové výkresy (n z m)? …", q.startswith("Uložit hotové výkresy (") and "Příště se už nebudou dělat znovu." in q and total == N + 1, q)
    check("three answers: Ano, uložit / Ne, zahodit / Uložit a stáhnout PDF hotových", sorted(btns) == sorted(["Ano, uložit", "Ne, zahodit", "Uložit a stáhnout PDF hotových"]), btns)
    built_then = js("return window.__req.builds")
    time.sleep(3)
    check("cancel: no more drawings started after it", js("return window.__req.builds") == built_then, f"{built_then} -> {js('return window.__req.builds')}")
    check("cancel: the card is gone, no PDF saved", finished(30) < 30 and not js("return window.__saved.length"))

    # 3. the next run: nothing kept by the discarded one; cancelled -> Ano, uložit; reload; the rest only
    start()
    b.wait("return window.__req.builds >= 1", 600)
    hits_after_no = js("return window.__req.hits")
    check("after Ne: the next run finds none of its drawings kept", hits_after_no == 0, hits_after_no)
    at = cancel_after(8)
    time.sleep(0.3)
    q, _ = answer("Ano, uložit")
    m = re.search(r"\((\d+) z (\d+)\)", q)
    kept, kept_parts = int(m[1]), js("return window.__req.builds")
    print(f"  cancelled at {at}, kept {kept} of {m[2]} pages ({kept_parts} part drawings)")
    check("Ano: kept count ≥ the counter at cancel", kept >= (at or (0, 0))[0], f"{kept} vs {at}")
    finished(30)
    open_demo()  # (reloaded: nothing in the page's memory)
    t0 = time.time()
    start()
    seen = None
    while time.time() - t0 < 20:
        c = counter()
        if c and c[0] >= kept:
            seen = (c, round(time.time() - t0, 1))
            break
        time.sleep(0.1)
    print("  after the reload: the counter at the kept count:", seen)
    check("after the reload: the counter at the kept count within seconds", bool(seen) and seen[1] < 15, seen)
    secs = finished()
    b.wait("return window.__saved.length === 1", 60)
    req = js("return window.__req")
    print(f"  the rest made in {time.time() - t0:.1f} s:", req)
    check("only the rest was made (all part pages − the kept ones)", req["builds"] == req["only"] - kept_parts and req["hits"] == kept_parts, f"{req}, {kept_parts} kept")
    name, data = js("return window.__saved[0]")
    path = OUT / "drawing_cancel.pdf"
    path.write_bytes(base64.b64decode(data))
    texts = [p.get_text() for p in fitz.open(path)]
    check(f"the PDF has every page ({total}), numbered n / N", len(texts) == total and all(f"{i + 1} / {total}" in tx for i, tx in enumerate(texts)), f"{len(texts)} pages, {name}")

    # 4. a warm full run: nothing made
    open_demo()
    t0 = time.time()
    start()
    finished()
    b.wait("return window.__saved.length === 1", 60)
    warm = time.time() - t0
    req = js("return window.__req")
    print(f"  warm full run (reloaded, all kept): {warm:.1f} s (with the PDF), cold drawings {cold[4] / 1000:.1f} s", req)
    check("warm run: no part drawn again", req["builds"] == 0, req)
    d.save_screenshot(str(OUT / "drawing_cancel.png"))

    check("no native dialogs", not js("return +localStorage.getItem('e2e.native') || 0"))
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE" and "favicon" not in e["message"]]
    check("no console errors", not errs, errs[:3])
finally:
    b.quit()
print("\nALL OK" if not fails else f"\n{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
