import sys; sys.stdout.reconfigure(encoding="utf-8")
import olefile, sys, os
for p in sys.argv[1:]:
    o = olefile.OleFileIO(p)
    print("=====", os.path.basename(p))
    for e in o.listdir(streams=True, storages=True):
        name = "/".join(e)
        t = o.get_type(e)
        if t == olefile.STGTY_STREAM:
            sz = o.get_size(e)
            d = o.openstream(e).read(24)
            print(f"S {name!r:60} {sz:9d} {d.hex(' ')}  {d!r}"[:200])
        else:
            print(f"D {name!r}")
