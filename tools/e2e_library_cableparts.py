"""📎 ⛓ Cable clips and energy chains from the parts library, in headless Edge: 📚 the library window lists Cable clips /
Cable ties / Energy chains (HellermannTyton, igus) -> an igus E2.15 chain (Bi 20, R 38) ⤵ into an assembly: its first
link placed, the rest drawn on as a U (one instanced mesh), the ⛓ rows in its panel; chainPath 2 × run + πR long, its
moving end where its travel says, for two travels; the travel slider moves it (the U redrawn); "Moves with" a part:
that part moved -> the chain rolls along; the parts list counts its links. clipsFor(6) -> H3P first; placeClip on a
point (the cable's axis where it belongs); ＋ Screw M4 on the clip: its head on the clip's seat. No console errors.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_library_cableparts.py http://127.0.0.1:5199 <out dir>
"""
import math
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
d.set_script_timeout(120)
js = d.execute_script
A = "window.__app.assembly"
H = "window.__app.agentHandlers"
fails = []


def check(what, ok, got=""):
    print(("OK  " if ok else "FAIL"), what, got)
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


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def run(script, *args):
    """An async snippet (await allowed; `C` = library/cableparts.js, `K` = assembly/chains.js) -> its value."""
    return d.execute_async_script("""const done = arguments[arguments.length - 1], args = [...arguments].slice(0, -1);
      (async () => { const C = await import('./js/library/cableparts.js'), K = await import('./js/assembly/chains.js');
        const f = new Function('C', 'K', 'args', 'return (async () => {' + args.shift() + '})()'); return f(C, K, args); })()
        .then(done).catch((e) => done({ error: e.message }));""", script, *args)


try:
    d.get(URL)
    wait("return !!window.__app")
    call("new_assembly", name="Cable carrier")
    wait("return window.__app.state.workspace === 'assembly'")
    # 📚 the library window: the new groups
    d.find_element(By.ID, "libBtn").click()
    wait("return window.__app.library.items?.length > 10 && !!document.querySelector('.lib .lib-item')")
    js("document.querySelector('.lib .lib-q').value = ''; window.__app.library.state.q = ''; window.__app.library.renderList()")
    groups = [g.text.lower() for g in d.find_elements(By.CSS_SELECTOR, ".lib .lib-gname")]
    check("groups Cable clips, Cable ties, Energy chains", all(any(g.startswith(x) for g in groups) for x in ("cable clips", "cable ties", "energy chains")), groups)
    subs = js("return [...document.querySelectorAll('.lib [data-sub]')].map(b => b.dataset.sub)")
    check("makers as headings (HellermannTyton, igus)", "Cable clips|HellermannTyton" in subs and "Energy chains|igus" in subs, subs)
    d.find_element(By.CSS_SELECTOR, ".lib [data-sub='Energy chains|igus']").click()
    time.sleep(0.3)
    d.find_element(By.CSS_SELECTOR, ".lib [data-item='igus-e2-15']").click()
    time.sleep(0.3)
    js("const s = document.querySelector('.lib [data-k=size]'); s.value = 'Bi 20'; s.dispatchEvent(new Event('change'))")
    time.sleep(0.3)
    js("const s = document.querySelector('.lib [data-k=length]'); s.value = '38'; s.dispatchEvent(new Event('change'))")
    wait("return !!window.__app.library.lastBody && document.querySelector('.lib h2')?.textContent.includes('R 38')", 30)
    det = d.find_element(By.CSS_SELECTOR, ".lib .lib-detail")
    facts = det.find_element(By.CSS_SELECTOR, ".lib-facts").text.replace("\n", " ")
    check("its part number E2.15.20.038.0", "E2.15.20.038.0" in facts, facts)
    check("Dimensions per catalogue", det.find_element(By.CSS_SELECTOR, ".lib-acc").text.endswith("Dimensions per catalogue"))
    bb = js("const b = window.__app.library.lastBody.bbox; return [b[3]-b[0], b[4]-b[1], b[5]-b[2]].map(v => +v.toFixed(2))")
    check("the preview: one link 20 × 27.8 × 19.3", bb == [20, 27.8, 19.3], bb)
    d.find_element(By.CSS_SELECTOR, ".lib [data-a=insert]").click()
    wait(f"return {A}.doc.instances.length === 1 && !!{A}.bodies[{A}.doc.instances[0].part]?.body && !!{A}.doc.chains?.length", 60)
    rec = js(f"return {A}.doc.chains[0]")
    check("a chain: its first link I1, its links from a 500 mm travel", rec["part"] == "I1" and rec["links"] == math.ceil((250 + math.pi * 38 + 40) / 20) and rec["dims"]["pn"] == "E2.15.20.038.0", rec)
    js(f"{A}.choose('I1')")
    time.sleep(0.5)
    mesh = js(f"const m = {A}.chainGroup?.children[0]; return m ? {{ count: m.count, inst: m.isInstancedMesh }} : null")
    check("the other links drawn: one instanced mesh", mesh and mesh["inst"] and mesh["count"] == rec["links"] - 1, mesh)
    check("its panel: ⛓ Energy chain rows", bool(d.find_elements(By.CSS_SELECTOR, "[data-chain] [data-chtravel]")))
    # the U: 2 × run + πR, the ends for two travels (the chain's own frame = its first link's: placed at the origin)
    links = rec["links"]
    for travel in (0, 120):
        p = run("""const c = { ...args[0].dims, links: args[0].links }, p = C.chainPath(c, args[1]);
          return { length: p.length, lower: p.lower, upper: p.upper, moving: p.moving.o, fixed: p.fixed.o, ok: p.ok, n: p.links.length,
            last: p.links[p.links.length - 1].b, poly: p.points.slice(1).reduce((s, q, i) => s + Math.hypot(q[0] - p.points[i][0], q[1] - p.points[i][1], q[2] - p.points[i][2]), 0) };""", rec, travel)
        L, run_ = links * 20, (links * 20 - math.pi * 38) / 2
        ok = abs(p["length"] - L) < 1e-9 and abs(p["lower"] - (run_ + travel / 2)) < 1e-9 and abs(p["upper"] - (run_ - travel / 2)) < 1e-9 \
            and abs(p["moving"][0] - travel) < 1e-9 and abs(p["moving"][2] - 76) < 1e-9 and p["fixed"] == [0, 0, 0] and p["n"] == links \
            and all(abs(a - b) < 1e-6 for a, b in zip(p["last"], p["moving"]))
        check(f"travel {travel}: {L} mm = lower + πR + upper; moving end at x {travel}, 2R up", ok, p)
        if travel == 0:
            check("  … 2 × run + πR", abs(p["length"] - (2 * p["lower"] + math.pi * 38)) < 1e-9)
    # the travel slider: the moving end goes, the U redrawn
    before = js(f"const m = {A}.chainGroup.children[0], M = new (m.matrix.constructor)(); m.getMatrixAt(m.count - 1, M); return M.elements.slice(12, 15)")
    js("const s = document.querySelector('[data-chain] [data-chtravel]'); s.value = '150'; s.dispatchEvent(new Event('input')); s.dispatchEvent(new Event('change'))")
    time.sleep(0.5)
    now = run("const rec = window.__app.assembly.doc.chains[0]; return K.travelOf(window.__app.assembly, rec);")
    last = js(f"const m = {A}.chainGroup.children[0], M = new (m.matrix.constructor)(); m.getMatrixAt(m.count - 1, M); return M.elements.slice(12, 15)")
    check("the slider: travel 150, the last link moved along x", now == 150 and abs(last[0] - before[0]) > 50, [now, before, last])
    d.save_screenshot(f"{OUT}/cableparts-chain.png")
    # 📎 the clips for a Ø6 bundle; one put on a point
    got = run("return C.clipsFor(6).map(c => [c.item.id, c.size, c.dmin, c.dmax]);")
    check("clipsFor(6): H3P P-clamp first, then MB3A", got[:2] == [["ht-hp-pclamp", "H3P", 5, 6.5], ["ht-mb-mount", "MB3A", 1.5, 35]], got)
    placed = run("""const a = window.__app.assembly, c = C.clipsFor(6)[0];
      const r = await C.placeClip(a, c, [300, 40, 0], [0, 0, 1], [0, 1, 0], { d: 6 });
      return { ...r, m: a.inst(r.inst).matrix };""")
    # H3P: the loop's centre F = 10 from the hole, WT + D/2 = 1 + 3.25 above the face
    check("placeClip: the clip's hole on the point, the cable's axis 10 from it at 4.25 up, along y", placed.get("axis") and all(abs(a - b) < 1e-9 for a, b in zip(placed["axis"]["o"], [290, 40, 4.25]))
          and all(abs(a - b) < 1e-9 for a, b in zip(placed["axis"]["d"], [0, 1, 0])), placed)
    turned = run("""const a = window.__app.assembly, c = C.clipsFor(6)[0];
      const M = C.clipMatrix(C.clipFrames(c.item, c.size, 6), [0, 0, 50], [1, 0, 0], [0, 0, 1]);
      const T = await import('three');
      return new T.Vector3(-10, 0, 4.25).applyMatrix4(M).toArray();""")
    check("on a wall (normal +x), the cable up: the axis 4.25 out of the wall, the hole beside it", turned and all(abs(a - b) < 1e-9 for a, b in zip(turned, [4.25, -10, 50])), turned)
    # ＋ Screw M4 on the clip: its head on the clip's seat (2 × WT = 2 above the face)
    r = call("library_pair", part=placed["inst"], role="screw")
    sc = js(f"""const a = {A}, it = a.doc.instances[a.doc.instances.length - 1], lib = window.__app.project.parts.find(p => p.id === it.part).data.library;
      return {{ pn: lib.pn, L: lib.length, z: it.matrix[14], x: it.matrix[12], y: it.matrix[13] }}""")
    check("＋ Screw M4: ISO 7045 M4 × 8 through the hole, its head on the seat (z 2)", sc["pn"].startswith("ISO 7045 M4") and sc["L"] == 8 and abs(sc["z"] + sc["L"] - 2) < 1e-6 and abs(sc["x"] - 300) < 1e-6 and abs(sc["y"] - 40) < 1e-6, [r[:160], sc])
    # the other way round: an M4 × 10 pan head screw -> ＋ Clip: H1P with its seat under the head
    call("library_add", item="iso7045", size="M4", length=10, to="assembly")
    sid = js(f"return {A}.doc.instances[{A}.doc.instances.length - 1].id")
    r = call("library_pair", part=sid, role="clip")
    cl = js(f"""const a = {A}, S = a.inst(arguments[0]), it = a.doc.instances[a.doc.instances.length - 1];
      return {{ pn: window.__app.project.parts.find(p => p.id === it.part).data.library.pn, dz: +(it.matrix[14] - S.matrix[14]).toFixed(4),
        off: +Math.hypot(it.matrix[12] - S.matrix[12], it.matrix[13] - S.matrix[13]).toFixed(4) }}""", sid)
    check("a screw M4 ×10: ＋ Clip H1P on its axis, its seat (1.6) under the head (10)", cl["pn"] == "H1P-PA66-NA" and cl["dz"] == 8.4 and cl["off"] == 0, [r[:120], cl])
    # moves with a part: the clip moved 100 along the chain's runs -> the chain's travel +100
    run("const a = window.__app.assembly, rec = a.doc.chains[0]; K.followPart(a, rec, args[0]); a.commit(); return 1;", placed["inst"])
    t0 = run("return K.travelOf(window.__app.assembly, window.__app.assembly.doc.chains[0]);")
    js(f"const a = {A}, it = a.inst(arguments[0]); it.matrix[12] += 100; a.render(); a.draw();", placed["inst"])
    t1 = run("return K.travelOf(window.__app.assembly, window.__app.assembly.doc.chains[0]);")
    route = run("const r = K.chainRoute(window.__app.assembly, 'C1'); return { o: r.moving.o, n: r.points.length, L: r.length };")
    check("moves with the clip: moved 100 -> travel 150 -> 250, its route's moving end there", abs(t0 - 150) < 1e-6 and abs(t1 - 250) < 1e-6 and abs(route["o"][0] - 250) < 1e-6, [t0, t1, route])
    # the parts list counts the links; get_assembly lists the chain
    q = js(f"const a = {A}, p = a.doc.instances[0].part; return a.bom().find(r => r.part === p).qty")
    check("the parts list: the chain's links", q == links, q)
    ga = call("get_assembly")
    check("get_assembly: chains (pn, links, travel, moves_with)", '"chains"' in ga and "E2.15.20.038.0" in ga and '"moves_with"' in ga, ga[ga.find('"chains"'):][:240])
    # undo takes the follow back, the chain stays
    js(f"return {A}.history.go(-1)")
    time.sleep(0.4)
    check("undo: not following any more, still a chain", js(f"const c = {A}.doc.chains?.[0]; return !!c && !c.follow"))
    d.save_screenshot(f"{OUT}/cableparts-clip.png")
    # in Czech: library_add (the AI) puts a chain in the same way; its panel's rows translated
    js("localStorage.setItem('auto3d-lang', 'cs')")
    d.get(URL)
    wait("return !!window.__app")
    call("new_assembly", name="Vlek")
    wait("return window.__app.state.workspace === 'assembly'")
    r = call("library_add", item="igus-14", size="Bi 25", length=48, to="assembly")
    wait(f"return !!{A}.doc.chains?.length && !!{A}.bodies[{A}.doc.instances[0].part]?.body", 60)
    js(f"{A}.choose('I1')")
    time.sleep(0.6)
    panel = js("return document.querySelector('[data-chain]')?.closest('div').parentElement.innerText || ''")
    c = js(f"return {A}.doc.chains[0]")
    check("library_add: an igus 14 chain (14.2.048.0), its rows in Czech", c["dims"]["pn"] == "14.2.048.0" and all(w in panel for w in ("Energetický řetěz", "Články", "Zdvih", "Jede s")), [c["dims"]["pn"], panel[:200]])
except Exception as e:  # (a step that never came: a failure too)
    fails.append(f"stopped: {type(e).__name__} {str(e)[:200]}")
    raise
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    if errs:
        fails.append("console errors")
    js("localStorage.removeItem('auto3d-lang')")
    d.quit()
    print("FAILED:" if fails else "ALL OK", fails)
