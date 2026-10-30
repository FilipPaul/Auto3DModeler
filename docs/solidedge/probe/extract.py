import sys; sys.stdout.reconfigure(encoding="utf-8")
import olefile, sys, os, glob, struct, zlib
src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
for p in sorted(glob.glob(os.path.join(src, "*.par")) + glob.glob(os.path.join(src, "*.asm"))):
    o = olefile.OleFileIO(p)
    base = os.path.splitext(os.path.basename(p))[0]
    for e in o.listdir():
        if e[0] == "PARASOLID":
            d = o.openstream(e).read()
            hdr = d[:600].decode("latin1")
            g = [l for l in hdr.split("\n") if l.startswith(("GUISE","FORMAT","SCH=","APPL","DATE"))]
            fn = os.path.join(out, f"j-separse-{base}__{e[1]}")
            open(fn, "wb").write(d)
            i = d.find(b"PS\x00")
            print(f"{base[:40]:40} {e[1]:18} {len(d):8} {';'.join(g)} | {d[i:i+70]!r}"[:330])
