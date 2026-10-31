"""A big imported STEP assembly switched top -> sub-assembly -> top in a real Edge window, and its parts chosen: the
owner's case (2026-10-31: "Sestava ICT M1556.stp", 25 MB — 254 parts, 44 sub-assemblies — opened as an assembly; the
top assembly, then "Sestava základní desky", then the top again: half a minute of a frozen window, no sign of work).

Each step — a row of the project tree clicked as a mouse does, the page in Czech — is timed from the click to the
switch done and its frame painted, with the loading card watched: a step over 300 ms shows it within 100 ms of the
click (painted before the work, never a silent freeze), and the steps are held to budgets (the first visit of the
sub-assembly a few seconds at most, every return warm under 0.5 s). No console errors.

  A3D_DATA=<a scratch folder> py server.py --port 5199 --no-browser
  PYTHONIOENCODING=utf-8 py tools/e2e_ict_switch.py http://127.0.0.1:5199 <out dir> [--file <a STEP assembly>] [--headless] [--profile]

Without --file: the owner's file at C:/Users/PAULSWARE/Downloads/Sestava ICT M1556.stp (opened from a copy in <out dir>)
when it is there, else (CI) a smaller one made here — the 150-part demo (demos/velka-sestava-150.a3d) exported as a
STEP assembly (its sub-assemblies nested in it) and opened as an assembly the same way. --headless: no window
(software GL).
"""
import json
import shutil
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

from selenium.webdriver.common.by import By

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_big_assembly import Builder  # noqa: E402

URL = sys.argv[1].rstrip("/")
OUT = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
args = sys.argv[3:]
OWNER = Path(args[args.index("--file") + 1]) if "--file" in args else Path("C:/Users/PAULSWARE/Downloads/Sestava ICT M1556.stp")
WINDOW = "--headless" not in args
PROFILE = "--profile" in args  # (a CDP CPU profile of each switch: <out>/ict-step<k>.cpuprofile, its top functions printed)
DEMO = Path(__file__).resolve().parent.parent / "demos" / "velka-sestava-150.a3d"
# budgets (ms) — measured on the owner's file in a real window (before the fix: the first return to the top 34 668 ms,
# the second 29 528 ms, one long task each and no card; the first visit of the sub-assembly 575 ms, its card at 378 ms)
BUDGET = {"first_visit_ms": 1500, "warm_ms": 500, "card_ms": 100, "card_over_ms": 300}
fails = []


def check(what, ok, info=""):
    print(("ok   " if ok else "FAIL ") + what + (f" — {info}" if info else ""))
    if not ok:
        fails.append(what)


def plain(s):
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()


b = Builder(URL, software_gl=not WINDOW, window=WINDOW)
d, js = b.d, b.js
d.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": """
  for (const k of ['alert', 'confirm', 'prompt']) window[k] = () => { localStorage.setItem('e2e.native', (+localStorage.getItem('e2e.native') || 0) + 1); return true; };
"""})


def synthetic():
    """The 150-part demo as a STEP assembly (a product per part, its sub-assemblies nested) -> its path."""
    out = OUT / "big-150-assembly.step"
    b.fresh()
    d.find_element(By.ID, "projectInput").send_keys(str(DEMO.resolve()))
    b.wait("const A = window.__app.assembly; return A.active && A.doc.instances.length > 0 && A.doc.instances.every((i) => A.bodyOf(i)?.body)", 300)
    data = b.run("""const A = window.__app.assembly, r = await fetch('/api/assembly/export/step', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tree: A.stepTree(), name: 'Velka sestava 150' }) });
      if (!r.ok) throw new Error(await r.text()); const u = new Uint8Array(await r.arrayBuffer()); let s = '';
      for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode(...u.subarray(i, i + 0x8000)); return btoa(s);""")
    import base64
    out.write_bytes(base64.b64decode(data))
    return out


def open_assembly(path):
    """Open path (a STEP assembly) as an assembly, the page in Czech -> seconds."""
    b.fresh()
    b.run("const I = await import('/js/i18n.js'); I.setLang('cs');")
    time.sleep(0.5)
    t0 = time.time()
    d.find_element(By.ID, "cadInput").send_keys(str(path.resolve()))
    end = time.time() + 900
    while time.time() < end:
        btns = [x for x in d.find_elements(By.CSS_SELECTOR, ".choose .btn") if x.is_displayed()]
        if btns:
            next(x for x in btns if "sestav" in x.text.lower()).click()  # (Otevřít jako sestavu)
            break
        time.sleep(0.2)
    b.wait("""const A = window.__app.assembly; return window.__app.state.workspace === 'assembly' && A.doc.instances.length > 0
      && A.doc.instances.every((i) => A.bodyOf(i)?.body) && !window.__app.project.busy""", 1800)
    s = time.time() - t0
    time.sleep(4)  # (what follows the first frame: the collision check, the panels)
    return s


def top_functions(profile, n=12):
    """A CPU profile's functions by self time -> [(ms, name, where)]."""
    nodes, by = {x["id"]: x for x in profile["nodes"]}, {}
    for s_, dt in zip(profile.get("samples", []), profile.get("timeDeltas", [])):
        cf = nodes[s_]["callFrame"]
        key = (cf["functionName"] or "(anon)", f"{cf['url'].rsplit('/', 1)[-1]}:{cf['lineNumber'] + 1}")
        by[key] = by.get(key, 0) + dt
    return [(round(us / 1000, 1), k[0], k[1]) for k, us in sorted(by.items(), key=lambda kv: -kv[1])[:n]]


def go(pid, tag=""):
    """A row of the project tree clicked as a mouse does -> {ms: to the switch done and its frame painted, card: ms to
    the loading card on screen (None: not shown), long: the long tasks after the click}."""
    xy = js("""const r = document.querySelector(`#projTree .pt-row[data-part="${arguments[0]}"] .pt-open`); r.scrollIntoView({ block: 'nearest' });
      const b = r.getBoundingClientRect(); return [b.left + 20, b.top + b.height / 2];""", pid)
    d.execute_cdp_cmd("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": xy[0], "y": xy[1], "button": "none"})
    time.sleep(0.4)
    # (the card watched on every frame and by a MutationObserver: when it was put on screen)
    js("""const pid = arguments[0], P = window.__app.project; window.__sw = { t0: 0, done: null, card: null, long: [] };
      const w = window.__sw, seen = () => { const c = document.getElementById('loadCard'); return c && !c.hidden; };
      window.addEventListener('pointerdown', () => { w.t0 = performance.now(); }, { capture: true, once: true });
      try { new PerformanceObserver((l) => { for (const e of l.getEntries()) w.long.push([e.startTime, e.duration]); }).observe({ type: 'longtask' }); } catch (e) {}
      const look = () => { const A = window.__app.assembly, M = window.__app.modeler, v = P.current?.kind === 'assembly' ? A.view : M.view;
        if (w.t0 && w.card === null && seen()) w.card = performance.now() - w.t0;
        if (w.t0 && P.active === pid && !P.busy && !M.inflight && !v.dirty) { w.done = performance.now() - w.t0; return; } requestAnimationFrame(look); };
      requestAnimationFrame(look);""", pid)
    if PROFILE:
        d.execute_cdp_cmd("Profiler.enable", {})
        d.execute_cdp_cmd("Profiler.setSamplingInterval", {"interval": 500})
        d.execute_cdp_cmd("Profiler.start", {})
    for ty in ("mousePressed", "mouseReleased"):
        d.execute_cdp_cmd("Input.dispatchMouseEvent", {"type": ty, "x": xy[0], "y": xy[1], "button": "left", "clickCount": 1})
    b.wait("return window.__sw.done !== null", 600)
    if PROFILE:
        prof = d.execute_cdp_cmd("Profiler.stop", {})["profile"]
        (OUT / f"ict-step{tag}.cpuprofile").write_text(json.dumps(prof))
        for row in top_functions(prof):
            print(f"      {row[0]:8} ms  {row[1]}  {row[2]}")
    r = js("const w = window.__sw; return { ms: Math.round(w.done), card: w.card === null ? null : Math.round(w.card), long: w.long.filter(([s]) => s >= w.t0).map(([, x]) => Math.round(x)) };")
    time.sleep(2)  # (what may follow: a clash check, the panels)
    return r


try:
    if OWNER.exists():
        src = OUT / OWNER.name
        if not src.exists() or src.stat().st_size != OWNER.stat().st_size:
            shutil.copyfile(OWNER, src)  # (the owner's file read-only: a copy opened)
        sub_name = "sestava zakladni desky"
        print(f"the owner's file: {OWNER.name} ({OWNER.stat().st_size / 1e6:.1f} MB)")
    else:
        print(f"SKIP the owner's file ({OWNER} is not here) — the CI version: the 150-part demo exported as a STEP assembly")
        src, sub_name = synthetic(), None
    urllib.request.urlopen(f"{URL}/api/timings?reset=1").read()
    s = open_assembly(src)
    info = js("""const P = window.__app.project, data = (p) => (p.data === 'live' ? window.__app.assembly.doc : p.data);
      return { top: P.active, name: P.current?.name, parts: P.parts.filter((p) => p.kind === 'model').length,
        subs: P.parts.filter((p) => p.kind === 'assembly' && p.id !== P.active).map((p) => [p.id, p.name, (data(p)?.instances || []).length]) };""")
    print(f"opened {src.name} as an assembly in {s:.1f} s: “{info['name']}”, {info['parts']} parts, {len(info['subs'])} sub-assemblies")
    top = info["top"]
    subs = sorted(info["subs"], key=lambda x: -x[2])
    sub = next((x for x in subs if sub_name and plain(x[1]).startswith(sub_name)), subs[0] if subs else None)
    check("the file opened as an assembly with sub-assemblies", bool(sub), info["subs"][:5])
    if not sub:
        raise SystemExit(1)
    print(f"  the sub-assembly: “{sub[1]}” ({sub[2]} placed in it)")
    res = {}
    for k, (tag, pid) in enumerate([("top", top), ("sub", sub[0]), ("top", top), ("sub", sub[0]), ("top", top)]):
        r = go(pid, k)
        res[f"{k}:{tag}"] = r
        print(f"  {k}: {tag:4} {r['ms']:6} ms   card at {r['card']} ms   long tasks {r['long'][:8]}")
    steps = list(res.values())
    for k, r in enumerate(steps):
        if r["ms"] > BUDGET["card_over_ms"]:
            check(f"step {k} took {r['ms']} ms: the loading card on screen within {BUDGET['card_ms']} ms of the click",
                  r["card"] is not None and r["card"] <= BUDGET["card_ms"], f"card at {r['card']} ms")
    check(f"the first visit of the sub-assembly under {BUDGET['first_visit_ms']} ms", steps[1]["ms"] < BUDGET["first_visit_ms"], steps[1]["ms"])
    for k in (2, 3, 4):
        check(f"step {k} (back, warm) under {BUDGET['warm_ms']} ms", steps[k]["ms"] < BUDGET["warm_ms"], steps[k]["ms"])
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE" and "favicon" not in e["message"]]
    check("no console errors", not errs, errs[:3])
    check("no native dialogs", not js("return +localStorage.getItem('e2e.native') || 0"))
    (OUT / "ict_switch.json").write_text(json.dumps({"open_s": s, "steps": res}, indent=1))
finally:
    b.quit()
print("\nALL OK" if not fails else f"\n{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
