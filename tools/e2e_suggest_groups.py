"""The Suggested table in categories and the icons' colours by kind, in headless Edge, in Czech, on the 🎬 150-part demo
(demos/velka-sestava-150.a3d: "Machine" with the sub-assemblies "Module A" and "Bearing block"):
- showSuggest itself (suggest.js, on a bare box): rows of one category — no header; of three — a header each, the
  category of the most relevant row first, each one's rows by rank, the top-N limit kept (⋯ Show all), Show all: every
  row, still in categories; sections go into the rows' tooltips;
- nothing chosen: the whole assembly's table in categories (Vazby / Pohyb / Vložit díly … in Czech), the first
  category holds the top-ranked row, at most N rows (+ the ones always in sight), ⋯ Ukázat vše;
- a placed part chosen: 🔗 joints blue (k-joint), ◆ Otevřít jeho díl with the trees' part icon on purple (k-part), the
  panel's button purple with the same icon; a placed sub-assembly chosen: its rows about it green (k-asm), Otevřít jeho
  díl with the trees' assembly icon; colours: the trees' (#a371f7 part, #7ee787 assembly, #58a6ff joint);
- the parts list's rows no taller than the project tree's; no console errors.

  PYTHONIOENCODING=utf-8 py tools/e2e_suggest_groups.py http://127.0.0.1:5199 <out dir>
"""
import os
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
DEMO = Path(__file__).resolve().parent.parent / "demos" / "velka-sestava-150.a3d"
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
A = "window.__app.assembly"
bad = []


def check(ok, what):
    print(("  ok   " if ok else "  FAIL ") + what)
    if not ok:
        bad.append(what)


def wait(script, t=120):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


# the table on screen: [[kind, text, icon classes, has a drawn icon (its kind)] …] — kind: 'h' a category's header, 'r' a row
TABLE = """const box = arguments[0] ? document.querySelector(arguments[0]) : document.querySelector('#asmViewport .view-suggest');
  if (!box) return null;
  return [...box.querySelectorAll('.vs-list > *')].map(e => e.classList.contains('vs-sec') ? ['h' + (e.classList.contains('vs-grp') ? 'g' : 's'), e.textContent.trim(), e.dataset.grp || '']
    : ['r', e.textContent.trim().replace(/\\s+/g, ' '), e.querySelector('.vs-i')?.className || '', (e.querySelector('.vs-i .ico')?.getAttribute('class') || '').split(' ')[1] || '', +(e.dataset.sg ?? -1)]);"""


def table(sel=None):
    return js(TABLE, sel) or []


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.setItem('auto3d-lang', 'cs'); sessionStorage.removeItem('a3d.suggestAll')")
    d.get(URL)
    wait("return !!window.__app && document.documentElement.lang === 'cs'")

    # 1. showSuggest on a bare box: the rules
    res = d.execute_async_script("""const done = arguments[arguments.length - 1];
      import('/js/suggest.js').then((m) => {
        const vp = document.createElement('div'); vp.className = 'viewport'; vp.id = 'sgTest';
        Object.assign(vp.style, { position: 'fixed', left: '0', top: '0', width: '600px', height: '700px' });
        document.body.appendChild(vp);
        const rows = () => [...vp.querySelectorAll('.vs-list > *')].map(e => e.classList.contains('vs-grp') ? '#' + e.dataset.grp : e.classList.contains('vs-sec') ? '§' + e.textContent : e.dataset.sg ? e.lastElementChild.textContent.trim() : e.dataset.sgAll !== undefined ? '⋯' : '');
        const out = {};
        const R = (label, group, rank, extra = {}) => ({ icon: '•', label, group, rank, run: () => {}, ...extra });
        m.showSuggest(vp, 'one', [R('a', 'joint', 1), R('b', 'joint', 0)]);
        out.one = rows();
        m.showSuggest(vp, 'three', [{ section: 'Sec X' }, R('p1', 'part', 2), R('j1', 'joint', 0.5), R('p2', 'part', 1), { section: 'Sec Y' }, R('o1', 'other', 0), R('j2', 'joint', 3),
          ...Array.from({ length: 10 }, (_, k) => R('o' + (k + 2), 'other', 10 + k))]);
        out.three = rows();
        out.tip = vp.querySelector('[data-sg="1"]')?.title;
        out.icons = [...vp.querySelectorAll('[data-sg] .vs-i')].map(i => i.className);
        vp.querySelector('[data-sg-all]')?.click();
        out.all = rows();
        vp.querySelector('[data-sg-fewer]')?.click();
        vp.remove();
        done(out);
      }).catch((e) => done({ error: String(e) }));""")
    print("  bare box:", res)
    check(res.get("one") == ["a", "b"], f"one category: no header, the rows as listed ({res.get('one')})")
    three = [x for x in res.get("three", []) if x]
    check(three == ["#other", "o1", "o2", "o3", "o4", "#joint", "j1", "j2", "#part", "p2", "p1", "⋯"],
          f"three categories: Other first (o1 rank 0), then Vazby (j1 0.5), Díl (p2 rank 1 before p1 rank 2); the 8 most relevant + ⋯ ({three})")
    check(sum(1 for x in three if x and not x.startswith(("#", "⋯", "§"))) == 8, "the top-N limit (8) kept with categories")
    check(not any(x.startswith("§") for x in three), "the sections go when the rows are in categories")
    check(res.get("tip") == "Sec X", f"a section's name in its rows' tooltip ({res.get('tip')})")
    check(any("k-joint" in c for c in res.get("icons", [])) and any("k-part" in c for c in res.get("icons", [])), "the icons of joints / parts coloured by their kind")
    allr = [x for x in res.get("all", []) if x]
    check(len([x for x in allr if not x.startswith(("#", "⋯", "▴"))]) == 15 and allr.count("#other") == 1, f"Ukázat vše: all 15 rows, still in categories ({allr})")

    # 2. the demo: the whole assembly's table
    d.find_element(By.ID, "projectInput").send_keys(str(DEMO))
    wait(f"const a = {A}; return a?.active && a.doc.instances.length && a.view?.meshes?.length === a.doc.instances.length")
    wait(f"return {A}._smart || document.querySelector('#asmViewport .view-suggest .vs-grp')", 60)
    time.sleep(2)
    js(f"{A}.select([])")
    time.sleep(0.6)
    tb = table()
    heads = [x[1] for x in tb if x[0] == "hg"]
    rows = [x for x in tb if x[0] == "r" and x[4] >= 0]
    print("  nothing chosen:", heads, [r[1] for r in rows])
    d.save_screenshot(os.path.join(OUT, "groups-assembly.png"))
    sg = js("const b = document.querySelector('#asmViewport .view-suggest'); return { top: b.sg.items[b.sg.ranked.find(i => !b.sg.items[i].always)].group, first: b.querySelector('.vs-grp')?.dataset.grp }")
    check(len(heads) >= 2 and all(h in ("Vazby", "Díl", "Sestava", "Kabeláž", "Spojovací materiál", "Pohyb", "Vložit díly", "Ostatní") for h in heads),
          f"nothing chosen: categories in Czech ({heads})")
    check(sg["top"] == sg["first"], f"the category of the most relevant row first ({sg})")
    always = js("const b = document.querySelector('#asmViewport .view-suggest'); return b.sg.items.filter(i => i.always).length")
    check(len(rows) <= 8 + always and any(x[0] == "r" and x[1].startswith("⋯") for x in tb), f"top 8 kept + ⋯ Ukázat vše ({len(rows)} rows)")

    # 3. a placed part: joints blue, open its part purple with the trees' icon
    pid = js(f"return {A}.doc.instances.find(i => {A}.kindOf(i.part) === 'model' && !i.fastener && (window.__app.project.parts.find(p => p.id === i.part)?.name === 'Base')).id")
    js(f"{A}.choose(arguments[0])", pid)
    time.sleep(0.8)
    tb = table()
    js("const b = document.querySelector('#asmViewport [data-sg-all]'); b && b.click()")
    time.sleep(0.4)
    tb = table()
    d.save_screenshot(os.path.join(OUT, "groups-part.png"))
    print("  a part:", [x[1:4] for x in tb])
    op = next((x for x in tb if x[0] == "r" and "Otevřít jeho díl" in x[1]), None)
    jn = next((x for x in tb if x[0] == "r" and "Spojit s jiným dílem" in x[1]), None)
    check(op and "k-part" in op[2] and op[3] == "ico-model", f"◆ Otevřít jeho díl: purple, the trees' 3D model icon ({op})")
    check(jn and "k-joint" in jn[2], f"🔗 Spojit s jiným dílem: blue ({jn})")
    cols = js("""const c = (s) => { const e = document.querySelector('#asmViewport .view-suggest .vs-i.' + s); return e ? getComputedStyle(e).color : null; };
      return [c('k-part'), c('k-joint')]""")
    check(cols == ["rgb(163, 113, 247)", "rgb(88, 166, 255)"], f"the colours: part purple, joint blue ({cols})")
    btn = js("const b = document.querySelector('#asmRight [data-a=openPart]'); return b ? [b.className, b.querySelector('.ico')?.getAttribute('class')] : null")
    check(btn and "k-part" in btn[0] and "ico-model" in (btn[1] or ""), f"the panel's Otevřít jeho díl: purple, the same icon ({btn})")
    tree_ico = js("const r = [...document.querySelectorAll('#projTree .pt-row')].find(r => r.querySelector('.pt-rname').textContent === 'Base'); return r?.querySelector('.ico')?.getAttribute('class')")
    check(tree_ico and "ico-model" in tree_ico, f"the project tree shows the same icon for it ({tree_ico})")

    # 4. a placed sub-assembly: its rows green, the assembly icon
    sid = js(f"return {A}.doc.instances.find(i => {A}.kindOf(i.part) === 'assembly').id")
    js(f"{A}.choose(arguments[0])", sid)
    time.sleep(0.8)
    tb = table()
    d.save_screenshot(os.path.join(OUT, "groups-sub.png"))
    print("  a sub-assembly:", [x[1:4] for x in tb])
    op = next((x for x in tb if x[0] == "r" and "Otevřít jeho díl" in x[1]), None)
    check(op and "k-asm" in op[2] and op[3] == "ico-assembly", f"◇ Otevřít jeho díl of a sub-assembly: green, the trees' assembly icon ({op})")
    check("Sestava" in [x[1] for x in tb if x[0] == "hg"], "its rows under Sestava")
    col = js("const e = document.querySelector('#asmViewport .view-suggest .vs-i.k-asm'); return e && getComputedStyle(e).color")
    check(col == "rgb(126, 231, 135)", f"the assembly colour green ({col})")
    btn = js("const b = document.querySelector('#asmRight [data-a=openPart]'); return b ? [b.className, b.querySelector('.ico')?.getAttribute('class')] : null")
    check(btn and "k-asm" in btn[0] and "ico-assembly" in (btn[1] or ""), f"the panel's Otevřít jeho díl: green, the assembly icon ({btn})")
    js("sessionStorage.removeItem('a3d.suggestAll')")

    # 5. the parts list as compact as the project tree
    hs = js("""const h = (s) => [...document.querySelectorAll(s)].filter(r => r.getClientRects().length).slice(0, 5).map(r => r.getBoundingClientRect().height);
      return [h('#asmLeft .as-list > .mt-item'), h('#projTree .pt-row')]""")
    check(hs[0] and hs[1] and max(hs[0]) <= max(hs[1]) and min(hs[0]) >= 22, f"the list's rows ≤ the project tree's, ≥ 22 px ({hs})")

    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    check(not errs, f"no console errors {errs}")
finally:
    d.quit()

print("FAILED:", bad if bad else "none")
sys.exit(1 if bad else 0)
