"""The loading card, in headless Edge: a big STEP (the biggest in samples/, 7.8 MB) dropped on the start screen says
"Loading ‹name› (7.8 MB)…" at once — in the page within 100 ms of the drop, a frame painted with it before any long
task of the import (the browser's long tasks vs the card's insertion) — then its steps (Uploading to the server… /
Reading the STEP file… / the kernel's stage) and the seconds so far; the question (an assembly) without the card over
it, then the card again while the mesh is made; gone when the part is shown. A broken STEP: the card, then an error
message in the app (Czech: "Načítám …"). ⬇ Export STEP: the card never over the Save dialog. No console errors, no
native dialogs.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_loading_indicator.py http://127.0.0.1:5199 <out dir> [<a big .step>]
"""
import os
import re
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
SAMPLES = Path(__file__).resolve().parent.parent / "samples"
BIG = sys.argv[3] if len(sys.argv) > 3 else str(max(list(SAMPLES.rglob("*.step")) + list(SAMPLES.rglob("*.stp")) + list(SAMPLES.rglob("*.STEP")), key=lambda p: p.stat().st_size))
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
d.set_script_timeout(60)
js = d.execute_script
bad = []
d.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": """
  for (const k of ['alert', 'confirm', 'prompt']) window[k] = () => { localStorage.setItem('e2e.native', (+localStorage.getItem('e2e.native') || 0) + 1); return true; };
"""})

# the card watched from the start: when it is put on the page / shown (its first frame: a requestAnimationFrame callback
# while it is shown), every text it showed, and the browser's long tasks
WATCH = """
window.__lt = [];
new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__lt.push([e.startTime, e.duration]); }).observe({ type: 'longtask' });
window.__card = { shown: [], frames: [], texts: [], hidden: [] };
let was = false;
const look = () => {
  const c = document.getElementById('loadCard'), on = !!c && !c.hidden;
  if (on && !was) { const at = performance.now(); window.__card.shown.push(at); requestAnimationFrame(() => window.__card.frames.push([at, performance.now(), !document.getElementById('loadCard').hidden])); }
  if (!on && was) window.__card.hidden.push(performance.now());
  if (on) { const t = c.innerText.replace(/\\s+/g, ' ').trim(); if (window.__card.texts[window.__card.texts.length - 1] !== t) window.__card.texts.push(t); }
  was = on;
};
new MutationObserver(look).observe(document.body, { subtree: true, childList: true, attributes: true, characterData: true });
"""


def check(ok, what):
    print(("  ok  " if ok else "  FAIL") + " " + what)
    if not ok:
        bad.append(what)


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def drop(path, on="#startScreen"):
    """The file dropped (a DataTransfer, as the browser makes it) -> the page's clock at the drop."""
    js("let i = document.getElementById('e2eFile'); if (!i) { i = document.createElement('input'); i.type = 'file'; i.id = 'e2eFile'; i.hidden = true; document.body.appendChild(i); } i.value = '';")
    d.find_element(By.ID, "e2eFile").send_keys(path)
    return js("""const f = document.getElementById('e2eFile').files[0], dt = new DataTransfer(); dt.items.add(f);
      const at = performance.now();
      document.querySelector(arguments[0]).dispatchEvent(new DragEvent('drop', { dataTransfer: dt, bubbles: true, cancelable: true }));
      return at;""", on)


def toasts():
    return js("return [...document.querySelectorAll('.toast')].map(t => t.textContent).join(' | ')")


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('auto3d-lang'); localStorage.removeItem('e2e.native')")
    d.get(URL + "?new")
    wait("return !!window.__app && !!window.__app.autosave && document.readyState === 'complete'")
    time.sleep(1.5)
    check(js("return document.body.classList.contains('start-open')"), "the start screen is open")
    js(WATCH)

    # ---- the big STEP dropped on the start screen
    size = os.path.getsize(BIG)
    print(f"  {Path(BIG).name}: {size / 1e6:.1f} MB")
    t0 = drop(BIG)
    shot = False
    end = time.time() + 600
    asked = False
    while time.time() < end:
        st = js("""const c = document.getElementById('loadCard'), q = [...document.querySelectorAll('.choose-back button')].find(b => /one body/.test(b.textContent));
          return { on: !!c && !c.hidden, q: !!q, open: /is open as a 3D model/.test([...document.querySelectorAll('.toast')].map(t => t.textContent).join(' ')) };""")
        if st["on"] and not shot and js("return /Reading|Building|Uploading/.test(document.getElementById('loadCard').innerText)"):
            d.save_screenshot(os.path.join(OUT, "loading_card.png"))
            shot = True
        if st["q"] and not asked:
            asked = True
            check(not st["on"], "the question (an assembly) is asked without the loading card over it")
            d.save_screenshot(os.path.join(OUT, "loading_question.png"))
            js("[...document.querySelectorAll('.choose-back button')].find(b => /one body/.test(b.textContent)).click()")
        if st["open"]:
            break
        time.sleep(0.25)
    wait("const c = document.getElementById('loadCard'); return !c || c.hidden", 60)
    card = js("return window.__card")
    lts = js("return window.__lt")
    first = card["shown"][0] if card["shown"] else None
    check(first is not None and first - t0 < 100, f"the card is on the page {first - t0 if first else '—':.1f} ms after the drop" if first else "the card was never shown")
    frame = card["frames"][0] if card["frames"] else None
    check(bool(frame) and frame[2] and frame[1] - t0 < 250, f"a frame with the card ran {frame[1] - t0:.0f} ms after the drop" if frame else "no frame with the card")
    early = [x for x in lts if x[0] >= t0 - 1 and frame and x[0] < frame[1]]
    print(f"  long tasks after the drop: {[(round(s - t0), round(dur)) for s, dur in lts if s >= t0 - 1][:8]}")
    check(not early, f"no long task of the import before the card's first frame: {early}")
    texts = card["texts"]
    print("  the card said:", *texts[:12], sep="\n    ")
    name = Path(BIG).name
    check(any(name in s and f"({size / 1e6:.1f} MB)" in s for s in texts), f"'Loading {name} ({size / 1e6:.1f} MB)…'")
    check(any("Uploading to the server" in s for s in texts), "the step 'Uploading to the server…'")
    check(any("Reading the STEP file" in s or "CAD kernel makes it a solid" in s for s in texts), "the step: reading the STEP")
    check(any("Making the mesh" in s or "Drawing" in s for s in texts), "the step: the mesh / drawing")
    check(any(re.search(r"\b\d+ s\b",s.split("…")[-1]) for s in texts), "the seconds so far shown")
    check(asked, "the 7.8 MB file is an assembly: asked how to open it")
    check(len(card["shown"]) == len(card["hidden"]) and len(card["shown"]) >= 2, f"shown {len(card['shown'])} × and gone each time (before the question, after the part)")
    check(js("return window.__app.project.parts.some(p => p.kind === 'model')") and "is open as a 3D model" in toasts(), "the part is open")
    d.save_screenshot(os.path.join(OUT, "loading_done.png"))

    # ---- ⬇ Export STEP: the card (when it takes a while) never over the Save dialog
    js("""window.__saveSeen = null; window.showSaveFilePicker = async (o) => { const c = document.getElementById('loadCard'); window.__saveSeen = !!c && !c.hidden;
      return { name: o.suggestedName, createWritable: async () => ({ write: async () => {}, close: async () => {} }) }; };""")
    n0 = len(js("return window.__card.shown"))
    js("document.querySelector('#exportMenu [data-fmt=step]').click()")
    wait("return window.__saveSeen !== null", 120)
    check(js("return window.__saveSeen") is False, "Export STEP: no card over the Save dialog")
    wait("const c = document.getElementById('loadCard'); return !c || c.hidden", 30)
    print(f"  export: the card shown {len(js('return window.__card.shown')) - n0} × (a slow export only)")

    # ---- a broken STEP, in Czech: the card, then the error in the app
    js("localStorage.setItem('auto3d-lang', 'cs')")
    d.get(URL + "?new")
    wait("return !!window.__app && !!window.__app.autosave && document.readyState === 'complete'")
    time.sleep(1.5)
    js(WATCH)
    broken = os.path.join(OUT, "broken part.step")
    with open(broken, "w", encoding="ascii") as f:
        f.write("ISO-10303-21;\nHEADER;\nthis is not a STEP file\n" + "x" * 300_000 + "\nEND-ISO-10303-21;\n")
    t0 = drop(broken)
    wait("return window.__card.hidden.length > 0", 120)
    card = js("return window.__card")
    check(bool(card["shown"]) and card["shown"][0] - t0 < 100, "broken file: the card at once")
    print("  the card said:", *card["texts"][:6], sep="\n    ")
    check(any(s.startswith("Načítám broken part.step (300 kB)…") for s in card["texts"]), f"in Czech: {card['texts'][:1]}")
    check(any("Nahrávám na server…" in s or "Čtu soubor" in s for s in card["texts"]), "its steps in Czech")
    err = wait("return [...document.querySelectorAll('.toast.error')].map(t => t.textContent).join(' | ')", 30)
    check(bool(err), f"an error in the app: {err[:120]!r}")
    check(js("return document.getElementById('loadCard').hidden"), "the card is gone")
    d.save_screenshot(os.path.join(OUT, "loading_error.png"))
    js("localStorage.removeItem('auto3d-lang')")

    check(not js("return +localStorage.getItem('e2e.native') || 0"), "no native dialogs")
    errs = [x["message"] for x in d.get_log("browser") if x["level"] == "SEVERE" and "favicon" not in x["message"]
            and "/api/model/import" not in x["message"]]  # (the broken file's 4xx answer)
    check(not errs, f"no console errors {errs[:3]}")
finally:
    d.quit()
print("ALL OK" if not bad else f"FAILED: {bad}")
sys.exit(1 if bad else 0)
