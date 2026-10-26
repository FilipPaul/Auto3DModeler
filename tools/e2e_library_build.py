"""📚 Every part of the library builds, in headless Edge: each item, each size, its shortest and longest length, made into
3D model steps (web/js/library/build.js) and built by the kernel -> a solid, its volume and size, every cut taking
material away (no "removes nothing" warning); a few checked against
their catalogue sizes (an M3×10 socket head screw 13 mm tall, a 608 bearing Ø22 × 7, SMC CDJ2B16-50 75 + 50 long, a SICK
IME12 46 long, a NEMA 17 42.3 wide, SMC CDQ2B25 52 square and 37.5 + stroke long).

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_library_build.py http://127.0.0.1:5199 <out dir>
"""
import sys
import time

from selenium import webdriver

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1400,900")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
d.set_script_timeout(900)
js = d.execute_script


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


try:
    d.get(URL)
    wait("return !!window.__app")
    res = d.execute_async_script("""const done = arguments[arguments.length - 1];
      (async () => {
        const B = await import('./js/library/build.js');
        const items = (await (await fetch('/api/library')).json()).items, out = [];
        for (const it of items) for (const s of B.sizesOf(it)) {
          const ls = B.lengthsOf(it, s.key), lens = ls ? [...new Set([ls.values[0], ls.values[ls.values.length - 1]])] : [undefined];
          for (const L of lens) {
            const row = { id: it.id, size: s.key, L };
            try {
              const p = B.buildPart(it, s.key, L);
              row.name = p.name; row.pn = p.data.library.pn;
              const r = await (await fetch('/api/model/rebuild', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ part: { features: p.data.features } }) })).json();
              if (!r.body) row.error = (r.features || []).flatMap((f) => f.issues || []).join(' ') || r.error || 'no solid';
              else { row.volume = +r.body.volume.toFixed(2); const b = r.body.bbox; row.size3 = [b[3] - b[0], b[4] - b[1], b[5] - b[2]].map((v) => +v.toFixed(2)); }
              const bad = (r.features || []).filter((f) => f.issues?.length);
              if (bad.length) row.issues = bad.map((f) => `${f.id}: ${f.issues.join(' ')}`).join(' | ');
              const warn = (r.features || []).filter((f) => f.warnings?.length);
              if (warn.length) row.warnings = warn.map((f) => `${f.id}: ${f.warnings.join(' ')}`).join(' | ');
            } catch (e) { row.error = e.message; }
            out.push(row);
          }
        }
        done(out);
      })().catch((e) => done([{ error: e.message }]));""")
    ok = [r for r in res if not r.get("error") and r.get("volume", 0) > 0]
    bad = [r for r in res if r.get("error") or not r.get("volume") or "removes nothing" in (r.get("warnings") or "")]
    print("built:", len(ok), "of", len(res))
    for r in bad:
        print("  FAILED:", r)
    print("every cut takes material away:", not any("removes nothing" in (r.get("warnings") or "") for r in res))
    for r in res:
        if r.get("issues"):
            print("  issues:", r["id"], r["size"], r["L"], r["issues"][:200])
    def find(i, s, L=None):
        return next((r for r in res if r["id"] == i and r["size"] == s and (L is None or r["L"] == L)), None)
    print("M3×4 socket head:", find("iso4762", "M3", 4).get("size3"), "(Ø5.5 × 4+3)")
    print("608 bearing:", find("bearing", "608").get("size3"), "(Ø22 × 7)")
    print("CDJ2B16 stroke 15:", find("smc-cdj2b", "Ø16", 15).get("size3"), "| pn", find("smc-cdj2b", "Ø16", 15).get("pn"), "(Ø20 × 75 + 15)")
    print("SICK IME12:", find("sick-ime", "M12, 4 mm").get("size3"), "| pn", find("sick-ime", "M12, 4 mm").get("pn"), "(46 long)")
    print("NEMA 17 48:", find("nema17", "48 mm (17HS19-2004S1)").get("size3"), "(42.3 × 42.3 × 48 + 26)")
    print("ruthex M3:", find("ruthex", "M3").get("size3"), find("ruthex", "M3").get("pn"))
    print("Würth 10 mm:", find("wurth-sstii-m3", "10").get("pn"), "(970100321)", find("wurth-sstii-m3", "10").get("size3"))
    print("CDQ2B25 stroke 5:", find("smc-cdq2b", "Ø25", 5).get("size3"), "(52 × 52 × 37.5 + 5) | pn", find("smc-cdq2b", "Ø25", 5).get("pn"))
    print("CDQ2B12 stroke 5:", find("smc-cdq2b", "Ø12", 5).get("size3"), "(32 × 32 × 31.5 + 5) | pn", find("smc-cdq2b", "Ø12", 5).get("pn"))
    print("CDQ2B50 stroke 100:", find("smc-cdq2b", "Ø50", 100).get("size3"), "(64 × 64 × 48.5 + 100)")
    print("D-M9BW:", find("smc-d-m9", "2-wire, 2-colour").get("pn"), find("smc-d-m9", "2-wire, 2-colour").get("size3"))
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
