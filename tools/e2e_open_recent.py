"""A big project opened from the start screen's 🕘 Recent projects (the owner, 2026-10-31: "when loading a project from
the intro screen from recent projects, the screen freezes without informing the user").

The 500-part demo (demos/velka-sestava-500.a3d) is kept on the server as an autosaved project, the page reloaded to
the start screen (in Czech), its picture in Recent projects clicked as a mouse does. Checked: the loading card
"Otevírám ‹name›…" on the page within 150 ms of the click and a frame painted with it before any long task of the
opening; the steps it went through (n of m parts built); the card gone once the project's first frame is painted
(the assembly drawn, the start screen away); the time from the click to that frame. No console errors, no native
dialogs. Then, the page reloaded again (the first opening's collision check maybe still running: stopped with its
page), 🕘 Recent projects… (the box) › Open: the card at once too, and no wait for the last page's kernel job; a 🎬
demo opened from the start screen: its card from the click too (before its file is fetched).

  A3D_DATA=<a scratch folder> py server.py --port 5199 --no-browser
  PYTHONIOENCODING=utf-8 py tools/e2e_open_recent.py http://127.0.0.1:5199 <out dir> [--file <an .a3d>] [--step <a STEP assembly>] [--id <a kept project>] [--window]

--file: another project file instead of the demo; --step: a STEP assembly (e.g. the owner's 254-part
"Sestava ICT M1556.stp", opened from a copy in <out dir>) opened as an assembly first and kept by autosave, then opened
again from Recent projects; --id: a project kept already (e.g. by an earlier --step run: a cold server opens it);
--window: a real Edge window (else headless).
"""
import json
import shutil
import sys
import time
import urllib.request
import uuid
from pathlib import Path

from selenium.webdriver.common.by import By

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_big_assembly import Builder  # noqa: E402

URL = sys.argv[1].rstrip("/")
OUT = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
args = sys.argv[3:]
FILE = Path(args[args.index("--file") + 1]) if "--file" in args else Path(__file__).resolve().parent.parent / "demos" / "velka-sestava-500.a3d"
STEP = Path(args[args.index("--step") + 1]) if "--step" in args else None
KEPT = args[args.index("--id") + 1] if "--id" in args else None
WINDOW = "--window" in args
BUDGET = {"card_ms": 150}
fails = []


def check(what, ok, info=""):
    print(("ok   " if ok else "FAIL ") + what + (f" — {info}" if info else ""))
    if not ok:
        fails.append(what)


def post(path, body, ctype="application/json"):
    req = urllib.request.Request(URL + path, data=body, headers={"Content-Type": ctype}, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=300).read())


b = Builder(URL, window=WINDOW)
d, js = b.d, b.js
d.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": """
  for (const k of ['alert', 'confirm', 'prompt']) window[k] = () => { localStorage.setItem('e2e.native', (+localStorage.getItem('e2e.native') || 0) + 1); return true; };
"""})

# the card and the opening watched from the click: the card put on screen (and its first frame), every text it
# showed, the long tasks, and the first frame of the opened project (the start screen away, the toast said, the view
# drawn with nothing left to draw)
WATCH = """
const w = window.__or = { t0: 0, card: null, cardFrame: null, texts: [], gone: null, first: null, told: null, long: [], cardAtFirst: null };
try { new PerformanceObserver((l) => { for (const e of l.getEntries()) w.long.push([e.startTime, e.duration]); }).observe({ type: 'longtask' }); } catch (e) {}
const on = () => { const c = document.getElementById('loadCard'); return !!c && !c.hidden; };
const seen = () => {
  if (!w.t0) return;
  if (on()) {
    if (w.card === null) { w.card = performance.now() - w.t0; requestAnimationFrame(() => { if (w.cardFrame === null && on()) w.cardFrame = performance.now() - w.t0; }); }
    const t = document.getElementById('loadCard').innerText.replace(/\\s+/g, ' ').trim();
    if (w.texts[w.texts.length - 1] !== t) w.texts.push(t);
  } else if (w.card !== null && w.gone === null) w.gone = performance.now() - w.t0;
};
new MutationObserver(seen).observe(document.body, { subtree: true, childList: true, attributes: true, characterData: true });
window.addEventListener('pointerdown', () => { w.t0 = performance.now(); seen(); }, { capture: true, once: true });
const look = () => {
  const A = window.__app.assembly, M = window.__app.modeler, P = window.__app.project, asm = P.current?.kind === 'assembly', v = asm ? A.view : M.view;
  // (its first frame: every placed part's body drawn — a part: its body — nothing left to draw; then the toast: opened)
  const drawn = asm ? A.doc.instances.length > 0 && A.doc.instances.every((i) => A.bodyOf(i)?.body) && !!A.drawn : !!M.result?.body;
  if (w.t0 && w.first === null && P.parts.length && drawn && !document.body.classList.contains('start-open') && !M.inflight && !v.dirty) {
    w.first = performance.now() - w.t0; w.cardAtFirst = on();
  }
  if (w.t0 && w.first !== null && [...document.querySelectorAll('.toast')].some((t) => /znovu otevřen|is open again|otevřeno jako nový projekt/.test(t.textContent))) { w.told = performance.now() - w.t0; return; }
  requestAnimationFrame(look);
};
requestAnimationFrame(look);
"""


def keep_project():
    """The project kept on the server as autosave keeps it -> (id, name, placed parts)."""
    if KEPT:
        meta = next(p for p in json.loads(urllib.request.urlopen(f"{URL}/api/projects").read())["projects"] if p["id"] == KEPT)
        return KEPT, meta["name"], None
    if STEP:
        src = OUT / STEP.name
        if not src.exists() or src.stat().st_size != STEP.stat().st_size:
            shutil.copyfile(STEP, src)  # (the owner's file read-only: a copy opened)
        b.fresh()
        d.find_element(By.ID, "cadInput").send_keys(str(src.resolve()))
        end = time.time() + 900
        while time.time() < end:
            btns = [x for x in d.find_elements(By.CSS_SELECTOR, ".choose .btn") if x.is_displayed()]
            if btns:
                next(x for x in btns if "assembl" in x.text.lower() or "sestav" in x.text.lower()).click()
                break
            time.sleep(0.2)
        b.wait("""const A = window.__app.assembly; return window.__app.state.workspace === 'assembly' && A.doc.instances.length > 0
          && A.doc.instances.every((i) => A.bodyOf(i)?.body) && !window.__app.project.busy""", 1800)
        time.sleep(3)
        r = b.run("const S = window.__app.autosave; await S.saveNow(); await S.keepThumb({ force: true }); return [S.id, window.__app.state.projectName || window.__app.project.current.name];")
        return r[0], r[1], None
    proj = post("/api/project/open", FILE.read_bytes(), "application/octet-stream")["project"]
    pid = f"e2e-{uuid.uuid4().hex[:12]}"
    post(f"/api/projects/{pid}", json.dumps({"project": proj}).encode())
    return pid, proj.get("project_name") or FILE.stem, sum(len(p.get("assembly", {}).get("instances", [])) for p in proj["parts"] if p["kind"] == "assembly")


def start_screen(pid):
    """The page reloaded empty, in Czech, on the start screen with pid in its recent projects -> its button."""
    d.get(URL + "?new")
    b.wait("return !!window.__app && !!window.__app.autosave && document.readyState === 'complete'")
    b.run("const I = await import('/js/i18n.js'); I.setLang('cs');")
    b.wait("return document.body.classList.contains('start-open') && !document.getElementById('startRecent').hidden", 15)
    time.sleep(1)
    js("window.__app.autosave.first = arguments[0]; window.__app.autosave.fillStart(document.getElementById('startRecent'))", pid)  # (first, as ✕ Close project puts it: newer ones kept meanwhile do not push it out)
    b.wait(f"return !!document.querySelector('#startRecent .st-proj[data-id=\"{pid}\"]')", 15)
    time.sleep(0.5)


def click(sel):
    """sel clicked as a mouse does (CDP) after the watch is on."""
    xy = js("const e = document.querySelector(arguments[0]); e.scrollIntoView({ block: 'nearest' }); const r = e.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2];", sel)
    d.execute_cdp_cmd("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": xy[0], "y": xy[1], "button": "none"})
    time.sleep(0.3)
    js(WATCH)
    for ty in ("mousePressed", "mouseReleased"):
        d.execute_cdp_cmd("Input.dispatchMouseEvent", {"type": ty, "x": xy[0], "y": xy[1], "button": "left", "clickCount": 1})


def result(tag):
    b.wait("return window.__or.told !== null", 600)
    time.sleep(0.3)
    r = js("const w = window.__or; return { ...w, long: w.long.filter(([s]) => s >= w.t0 - 1).map(([s, x]) => [Math.round(s - w.t0), Math.round(x)]) };")
    print(f"  {tag}: card at {r['card'] and round(r['card'])} ms (its frame {r['cardFrame'] and round(r['cardFrame'])} ms), "
          f"first frame of the project {round(r['first'])} ms, card gone at {r['gone'] and round(r['gone'])} ms")
    print(f"    long tasks: {r['long'][:10]}")
    print("    the card said:", *r["texts"][:12], sep="\n      ")
    return r


try:
    urllib.request.urlopen(f"{URL}/api/timings?reset=1").read()
    pid, name, placed = keep_project()
    print(f"kept: “{name}” ({pid})" + (f", {placed} placed parts" if placed else ""))
    start_screen(pid)
    d.save_screenshot(str(OUT / "open_recent_start.png"))
    click(f'#startRecent .st-proj[data-id="{pid}"]')
    time.sleep(0.4)
    d.save_screenshot(str(OUT / "open_recent_card.png"))
    r = result("start screen › Recent projects")
    check(f"the loading card on screen within {BUDGET['card_ms']} ms of the click", r["card"] is not None and r["card"] <= BUDGET["card_ms"], f"{r['card']} ms")
    check("a frame painted with the card before any long task of the opening",
          r["cardFrame"] is not None and not [x for x in r["long"] if x[0] < r["cardFrame"] and x[0] + x[1] > r["card"] + 5], f"frame {r['cardFrame']}, long {r['long'][:3]}")
    check(f"it says “Otevírám {name}…”", any(f"Otevírám {name}" in s for s in r["texts"]), r["texts"][:2])
    check("it tells the parts being built (n of m)", any("dílů" in s and " z " in s for s in r["texts"]), r["texts"][-3:])
    check("the card is up until the project's first frame", r["gone"] is not None and r["cardAtFirst"] and r["gone"] >= r["first"], f"gone {r['gone']}, first {r['first']}")
    check("the card is gone after the project shows", js("const c = document.getElementById('loadCard'); return !c || c.hidden"))
    check("the project is open", js("return window.__app.project.parts.length > 0 && !document.body.classList.contains('start-open')"))
    d.save_screenshot(str(OUT / "open_recent_done.png"))
    timing = {"recent": r}

    # 🕘 Recent projects… (the box) › Open: the same card
    start_screen(pid)
    js("window.__app.autosave.showRecent()")
    b.wait(f"return !!document.querySelector('.aih-row[data-id=\"{pid}\"] [data-open]')", 15)
    click(f'.aih-row[data-id="{pid}"] [data-open]')
    r = result("Recent projects… › Open")
    check(f"Recent projects… › Open: the card within {BUDGET['card_ms']} ms", r["card"] is not None and r["card"] <= BUDGET["card_ms"], f"{r['card']} ms")
    # (the page before was reloaded with its collision check running: that kernel job stopped with it — the opening
    # does not wait for it; before: 120 s on the owner's ICT assembly, "waiting for the CAD kernel")
    check("opened again after a reload: no waiting for the last page's kernel job", r["first"] < timing["recent"]["first"] + 5000,
          f"{round(r['first'])} ms vs {round(timing['recent']['first'])} ms the first time")
    timing["box"] = r

    # 🎬 a demo (its file fetched after the click): the card from the click too
    start_screen(pid)
    js("document.querySelector('[data-start=demo]').click()")
    b.wait("return !!document.querySelector(`.demos [data-demo='velka-sestava-150.a3d'] [data-open]`)", 15)
    click(".demos [data-demo='velka-sestava-150.a3d'] [data-open]")
    r = result("🎬 Demo › Open")
    check(f"a demo: the card “Otevírám Velká sestava — 150 dílů…” within {BUDGET['card_ms']} ms",
          r["card"] is not None and r["card"] <= BUDGET["card_ms"] and any("Otevírám Velká sestava — 150 dílů" in s for s in r["texts"]), f"{r['card']} ms, {r['texts'][:1]}")
    timing["demo"] = r

    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE" and "favicon" not in e["message"]]
    check("no console errors", not errs, errs[:3])
    check("no native dialogs", not js("return +localStorage.getItem('e2e.native') || 0"))
    (OUT / "open_recent.json").write_text(json.dumps(timing, indent=1))
    if not (STEP or KEPT):  # (the demo's copy: forgotten again)
        urllib.request.urlopen(urllib.request.Request(f"{URL}/api/projects/{pid}", method="DELETE")).read()
finally:
    b.quit()
print("\nALL OK" if not fails else f"\n{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
