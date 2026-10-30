import sys, olefile, re, struct, math, collections, json
sys.stdout.reconfigure(encoding="utf-8")
o = olefile.OleFileIO(sys.argv[1])
d = o.openstream("Preview/Structure/IDS").read()
names = [(m.start(), m.group().decode("utf-16-le")) for m in re.finditer(rb"(?:[\x20-\x7e\xa0-\xff][\x00\x01]){3,120}?\.\x00p\x00a\x00r\x00:\x00(?:[0-9]\x00)+", d)]
rows = []
i = 0
while i + 128 <= len(d):
    v = struct.unpack_from("<16d", d, i)
    if all(math.isfinite(x) and abs(x) < 10 for x in v) and abs(v[15] - 1) < 1e-12 and v[3] == v[7] == v[11] == 0 and \
       all(abs(sum(v[a*4+k]*v[b*4+k] for k in range(3)) - (a == b)) < 1e-9 for a in range(3) for b in range(3)):
        prev = [n for n in names if n[0] > i][:1]
        nm = prev[0][1] if prev else "?"
        rot = [[round(v[c*4+r], 6) for c in range(3)] for r in range(3)]
        rows.append({"occurrence": nm.split("\\")[-1], "offset": i, "t_mm": [round(x*1000, 4) for x in v[12:15]], "R": rot})
        i += 128
    else:
        i += 1
json.dump(rows, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(rows), "placements; first per part:")
seen = set()
for r in rows:
    k = r["occurrence"].split(":")[0]
    if k in seen: continue
    seen.add(k)
    print(f"   {r['occurrence']:50} t={r['t_mm']} R={r['R']}")
zs = collections.Counter((r["occurrence"].split(':')[0], r["t_mm"][2]) for r in rows)
print("z levels per part:", dict(zs))
xs = [r["t_mm"][0] for r in rows]; ys = [r["t_mm"][1] for r in rows]
print("x range", min(xs), max(xs), "y range", min(ys), max(ys))
