"""Snap points in an assembly, with REAL mouse moves (the page in Czech, a clean localStorage): the face under the mouse
shows its snap points (corners, edge middles, centres) as green dots — with no tool on and in 📏 Measure — and a click on
a dot takes that point. The owner's case (2026-10-31): in his imported STEP assembly (“Sestava ICT M1556.stp”: 254 parts
🪶 simplified — their meshes come without edges) no dots at all, not even in 📏 Measure.

  1. the 150-part demo (top-level parts and placed sub-assemblies — one merged body each): a part's face and a
     sub-assembly's face hovered -> dots; a dot clicked -> its snap picked; 📏 Measure: dots, two dots clicked -> the
     distance between them;
  2. the same demo exported as a STEP assembly and opened as an assembly, every part 🪶 simplified (the board's case: a
     big tree opens so): their edges are asked for when the mouse is on them -> dots on a top-level part and inside a
     sub-assembly's merged body, a dot clicked, 📏 two dots measured;
  3. --ict: the owner's file (C:/Users/PAULSWARE/Downloads/Sestava ICT M1556.stp, opened from a copy in <out dir>) the same.
No console errors.

  A3D_DATA=<a scratch folder> py server.py --port 5199 --no-browser
  PYTHONIOENCODING=utf-8 py tools/e2e_asm_snaps.py http://127.0.0.1:5199 <out dir> [--ict] [--window]
"""
import base64
import shutil
import sys
import time
from pathlib import Path

from selenium.webdriver.common.by import By

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_big_assembly import Builder  # noqa: E402

URL = sys.argv[1].rstrip("/")
OUT = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
args = sys.argv[3:]
ICT = Path("C:/Users/PAULSWARE/Downloads/Sestava ICT M1556.stp")
DEMO = Path(__file__).resolve().parent.parent / "demos" / "velka-sestava-150.a3d"
fails = []


def check(what, ok, info=""):
    print(("ok   " if ok else "FAIL ") + what + (f" — {info}" if info else ""))
    if not ok:
        fails.append(what)


b = Builder(URL, window="--window" in args)
d, js = b.d, b.js
A = "window.__app.assembly"


def mouse(ty, x, y):
    d.execute_cdp_cmd("Input.dispatchMouseEvent", {"type": ty, "x": x, "y": y, "button": "none" if ty == "mouseMoved" else "left", "clickCount": 1})


def move(x, y):
    """The mouse moved to x, y (from a few px away: real moves), then two frames for the hover's work."""
    for k in (6, 3, 0):
        mouse("mouseMoved", x - k, y)
        time.sleep(0.03)
    b.run("await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));")


def click(x, y):
    move(x, y)
    mouse("mousePressed", x, y)
    mouse("mouseReleased", x, y)
    time.sleep(0.3)


def dots():
    """The hover's dots on the screen: [[x, y, world xyz]] (in the canvas, not under a panel; in sight — the GPU's depth
    test hides the others, as measurePoint's sees does)."""
    return js(f"""const v = {A}.view, g = v.hoverSnapGroup?.children[0], r = v.renderer.domElement.getBoundingClientRect(), out = [];
      if (!g) return out;
      for (const w of g.userData.at) {{
        const [x, y] = v.toScreen(w);
        if (x > r.left + 4 && x < r.right - 4 && y > r.top + 4 && y < r.bottom - 4 && document.elementFromPoint(x, y) === v.renderer.domElement && v.sees(w)) out.push([x, y, w.toArray()]);
      }}
      return out;""")


def spots(sub=None):
    """Points on the shown parts (their middles on the screen, where the part itself is under the mouse) -> [[x, y,
    inst, merged]] — sub: only sub-assemblies' merged bodies (True) or only parts (False)."""
    return js(f"""const A = {A}, v = A.view, r = v.renderer.domElement.getBoundingClientRect(), out = [], want = arguments[0];
      for (const m of v.shown()) {{
        const merged = !!m.userData.body.sub;
        if (want !== null && merged !== want) continue;
        m.geometry.computeBoundingBox();
        const bb = m.geometry.boundingBox;
        for (const t of [0.5, 0.3, 0.7]) {{
          const c = bb.min.clone().lerp(bb.max, t).applyMatrix4(m.matrix).project(v.camera);
          const x = Math.round(r.left + (c.x + 1) / 2 * r.width), y = Math.round(r.top + (1 - c.y) / 2 * r.height);
          if (x < r.left + 40 || x > r.right - 40 || y < r.top + 40 || y > r.bottom - 40 || document.elementFromPoint(x, y) !== v.renderer.domElement) continue;
          if (v.pickInst(x, y)?.inst === m.userData.inst) {{ out.push([x, y, m.userData.inst, merged]); break; }}
        }}
      }}
      return out.slice(0, 40);""", sub)


def hover_dots(where, sub=None, tries=14):
    """A face of a part hovered until one shows dots (a small round face may have none to show) -> (spot, dots)."""
    for s in spots(sub)[:tries]:
        move(s[0], s[1])
        got = dots()
        if not got:  # (a 🪶 simplified part's edges come from the kernel: the dots a moment later)
            time.sleep(0.8)
            got = dots()
        if got:
            return s, got
    check(f"{where}: a hovered face shows its snap points as dots", False, f"{len(spots(sub))} spots tried")
    return None, []


def alone(got, px=14):
    """The dots with no other dot within px on the screen (a click there means that one), else all of them."""
    out = [q for q in got if all(q is o or (q[0] - o[0]) ** 2 + (q[1] - o[1]) ** 2 >= px * px for o in got)]
    return out or got


def case(where, sub_too=True):
    """Hover dots on a part (and on a sub-assembly's merged body), a dot clicked, 📏 two dots measured."""
    js(f"{A}.facePicks = []; {A}.choose(null); {A}.render()")
    for sub in ([False, True] if sub_too else [None]):
        s, got = hover_dots(f"{where} ({'inside a sub-assembly' if sub else 'a part'})", sub)
        if not s:
            continue
        check(f"{where}: {'a sub-assembly' if sub else 'a part'} {s[2]} hovered: its face's snap points shown", len(got) > 0, f"{len(got)} dots")
    s, got = hover_dots(where)
    if not s:
        return
    t0 = time.time()
    d.save_screenshot(str(OUT / f"asm_snaps_{''.join(c if c.isalnum() else '_' for c in where)[:40]}_hover.png"))
    x, y, w = alone(got)[0]
    click(round(x), round(y))
    pick = js(f"const s = {A}.snapPick; return s ? [s.snap, s.inst, s.point.toArray()] : null")
    ok = bool(pick) and sum((a - b_) ** 2 for a, b_ in zip(pick[2], w)) ** 0.5 < 1e-3
    check(f"{where}: a dot clicked takes its snap point", ok, pick if ok else f"{pick}; the dot {w} at {x:.0f}, {y:.0f}; there now: "
          + str(js(f"const s = {A}.view.measurePoint(arguments[0], arguments[1], 5); return s && [s.snap, s.inst, s.point.toArray()]", round(x), round(y))))
    # 📏 Measure: the dots too, and two of them measured
    js(f"if (!{A}.measuring) {A}.toggleMeasure()")
    time.sleep(0.3)
    s, got = hover_dots(f"{where} 📏 Measure")
    if not s:
        return
    check(f"{where}: 📏 Measure — the hovered face's snap points shown", len(got) > 0, f"{len(got)} dots")
    lone = alone(got)
    one = lone[0]
    far = max(lone, key=lambda q: (q[0] - one[0]) ** 2 + (q[1] - one[1]) ** 2)
    if far is one or abs(far[0] - one[0]) + abs(far[1] - one[1]) < 25:
        print(f"  ({where}: the dots too close together on the screen to click two)")
    else:
        n0 = js(f"return ({A}.doc.measures || []).length")
        click(round(one[0]), round(one[1]))
        click(round(far[0]), round(far[1]))
        row = js(f"const l = {A}.doc.measures || []; return l.length ? l[l.length - 1] : null")
        want = sum((a - b_) ** 2 for a, b_ in zip(one[2], far[2])) ** 0.5
        check(f"{where}: 📏 two dots clicked -> the distance between them", bool(row) and row.get("kind") == "dist" and abs(row["v"] - want) < 1e-2,
              f"{row and row.get('v')} vs {want:.3f} ({js(f'return ({A}.doc.measures || []).length') - n0} rows: {row and [row.get('kind'), row.get('a'), row.get('b')]})")
    js(f"{A}.toggleMeasure()")
    d.save_screenshot(str(OUT / f"asm_snaps_{''.join(c if c.isalnum() else '_' for c in where)[:40]}.png"))
    print(f"  ({where}: {time.time() - t0:.1f} s)")


def open_step(path):
    b.fresh()
    b.run("const I = await import('/js/i18n.js'); I.setLang('cs');")
    d.find_element(By.ID, "cadInput").send_keys(str(path.resolve()))
    end = time.time() + 900
    while time.time() < end:
        btns = [x for x in d.find_elements(By.CSS_SELECTOR, ".choose .btn") if x.is_displayed()]
        if btns:
            next(x for x in btns if "sestav" in x.text.lower()).click()  # (Otevřít jako sestavu)
            break
        time.sleep(0.2)
    b.wait(f"""const A = {A}; return window.__app.state.workspace === 'assembly' && A.doc.instances.length > 0
      && A.doc.instances.every((i) => A.bodyOf(i)?.body) && !window.__app.project.busy""", 1800)
    time.sleep(2)


try:
    # a clean start: nothing remembered (the hover filters on by default), the page in Czech
    b.fresh()
    js("localStorage.clear()")
    b.fresh()
    b.run("const I = await import('/js/i18n.js'); I.setLang('cs');")
    d.find_element(By.ID, "projectInput").send_keys(str(DEMO.resolve()))
    b.wait(f"const A = {A}; return A.active && A.doc.instances.length > 0 && A.doc.instances.every((i) => A.bodyOf(i)?.body) && !window.__app.project.busy", 300)
    time.sleep(2)
    check("the hover filters' buttons are in the view (Najetí: Hrany, Body přichycení)", js("return [...document.querySelectorAll('#asmViewport .snap-filters [data-hover]')].filter((x) => x.classList.contains('on')).length") == 2)
    case("the 150-part demo")

    # its STEP export opened as an assembly, every part 🪶 simplified (as a big board opens)
    data = b.run(f"""const A = {A}, r = await fetch('/api/assembly/export/step', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ tree: A.stepTree(), name: 'Velka sestava 150' }}) }});
      if (!r.ok) throw new Error(await r.text()); const u = new Uint8Array(await r.arrayBuffer()); let s = '';
      for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode(...u.subarray(i, i + 0x8000)); return btoa(s);""")
    step = OUT / "asm-snaps-150.step"
    step.write_bytes(base64.b64decode(data))
    open_step(step)
    b.run(f"""const A = {A}, P = window.__app.project;
      A.doc.light = Object.fromEntries(P.parts.filter((p) => p.kind === 'model').map((p) => [p.id, true]));
      await A.refresh();""")
    b.wait(f"const A = {A}; return A.doc.instances.every((i) => A.bodyOf(i)?.body) && !window.__app.project.busy", 600)
    time.sleep(1)
    info = js(f"""const A = {A}, bs = A.doc.instances.map((i) => A.bodyOf(i)?.body).filter(Boolean);
      return {{ light: bs.filter((b) => b.light && !b.edges.length).length, merged: bs.filter((b) => b.sub).length, bare: bs.filter((b) => b.bare?.length).length, edges: bs.reduce((n, b) => n + b.edges.length, 0) }};""")
    print("  the STEP assembly:", info)
    check("the STEP assembly: its parts 🪶 simplified, without edges (the owner's case)", info["light"] > 0 and info["bare"] > 0 and info["edges"] == 0, info)
    case("the STEP assembly (simplified)")

    if "--ict" in args and ICT.exists():
        src = OUT / ICT.name
        if not src.exists() or src.stat().st_size != ICT.stat().st_size:
            shutil.copyfile(ICT, src)
        t0 = time.time()
        open_step(src)
        print(f"  the owner's file opened in {time.time() - t0:.0f} s")
        case("the owner's ICT", sub_too=False)
        # inside its biggest sub-assembly ("Sestava základní desky"), opened from the project tree
        pid = js("""const P = window.__app.project, data = (p) => (p.data === 'live' ? window.__app.assembly.doc : p.data);
          return P.parts.filter((p) => p.kind === 'assembly' && p.id !== P.active).sort((a, b) => (data(b)?.instances || []).length - (data(a)?.instances || []).length)[0]?.id;""")
        xy = js("""const r = document.querySelector(`#projTree .pt-row[data-part="${arguments[0]}"] .pt-open`); r.scrollIntoView({ block: 'nearest' });
          const b = r.getBoundingClientRect(); return [b.left + 20, b.top + b.height / 2];""", pid)
        click(*xy)
        b.wait(f"const P = window.__app.project, A = {A}; return P.active === arguments[0] && !P.busy && A.doc.instances.every((i) => A.bodyOf(i)?.body)", 600, pid)
        time.sleep(2)
        case("the owner's ICT sub-assembly", sub_too=False)
    elif "--ict" in args:
        print(f"SKIP the owner's file ({ICT} is not here)")
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE" and "favicon" not in e["message"]]
    check("no console errors", not errs, errs[:3])
finally:
    b.quit()
print("\nALL OK" if not fails else f"\n{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
