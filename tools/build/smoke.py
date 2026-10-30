"""Smoke test of the built app (or any Auto3DModeler.exe): start it on its own port and data folder, wait for the
server, check the CAD kernel and its processes, build a 40 × 20 × 10 block (its volume), export it as STEP, then stop
it (the whole process tree: the kernel processes too).

usage:  py tools/build/smoke.py dist/Auto3DModeler/Auto3DModeler.exe <data dir> [port] [--keep]
  --keep: leave it running (for the e2e tests against it); stop it later with  taskkill /T /F /PID <pid>
"""
import base64
import json
import os
import struct
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def get(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def post(url, body, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def block():
    sketch = {"id": "S1", "type": "sketch", "plane": {"datum": "XY"},
              "entities": [{"id": "e1", "t": "rect", "cx": 0, "cy": 0, "w": 40, "h": 20}]}
    return {"features": [sketch, {"id": "E1", "type": "extrude", "sketch": "S1", "op": "add", "d": 10}]}


def volume(positions):
    """The volume of a closed mesh of float32 triangles (x y z × 3 each)."""
    f = struct.unpack(f"<{len(positions) // 4}f", positions)
    v = 0.0
    for i in range(0, len(f), 9):
        ax, ay, az, bx, by, bz, cx, cy, cz = f[i:i + 9]
        v += ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx)
    return abs(v) / 6


def stop(proc):
    subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)


def main():
    exe, data = str(Path(sys.argv[1]).resolve()), sys.argv[2]
    port = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else 5194
    keep = "--keep" in sys.argv
    url = f"http://127.0.0.1:{port}"
    try:  # (someone else on that port — another server, an agent's — would answer for us: a wrong pass)
        other = json.loads(get(f"{url}/api/version", 1))
        raise SystemExit(f"FAIL: port {port} is taken ({other.get('text')}) — pick a free one")
    except OSError:
        pass
    stamp = Path(exe).parent / "_internal" / "BUILD.json"
    want = json.loads(stamp.read_text(encoding="utf-8")).get("commit") if stamp.exists() else None
    env = {**os.environ, "A3D_DATA": data}
    t0 = time.time()
    proc = subprocess.Popen([exe, "--port", str(port), "--no-browser", "--no-tray"], env=env)
    ok = False
    try:
        while time.time() - t0 < 120:
            try:
                ver = json.loads(get(f"{url}/api/version", 2))
                break
            except OSError:
                if proc.poll() is not None:
                    raise SystemExit(f"FAIL: it exited with {proc.returncode} (see {data}\\logs\\auto3d.log)")
                time.sleep(0.2)
        else:
            raise SystemExit("FAIL: no answer within 120 s")
        started = time.time() - t0
        print(f"up in {started:.1f} s: version {ver.get('text')}")
        assert not want or ver.get("commit") == want, f"another server answered: {ver.get('text')}, not {want}"
        kernel = json.loads(get(f"{url}/api/kernel"))
        print(f"kernel: occ {kernel['occ']}, planegcs {kernel['planegcs']}, workers {kernel['workers']}")
        assert kernel["ready"], "the CAD kernel or the sketch solver is missing"
        t1 = time.time()
        res = json.loads(post(f"{url}/api/model/rebuild", {"part": block()}))
        assert res.get("ok") and res.get("body"), res
        vol = volume(base64.b64decode(res["body"]["positions"]))
        print(f"rebuild (the first one starts a kernel process): {time.time() - t1:.1f} s, volume {vol:.1f} mm3")
        assert abs(vol - 8000) < 1, vol
        step = post(f"{url}/api/model/export/step", {"part": block(), "name": "block"})
        assert step[:20].startswith(b"ISO-10303-21"), step[:80]
        print(f"STEP export: {len(step)} bytes")
        dm = json.loads(get(f"{url}/api/demos"))["demos"]  # 🎬 demos/ (.a3d packages) went into the build and opens
        assert dm and json.loads(get(f"{url}/api/demos/{dm[0]['file']}")).get("parts"), dm
        assert dm[0]["thumb"] and get(f"{url}/api/demos/{dm[0]['file']}/thumb")[1:4] == b"PNG", dm[0]  # (its card's picture)
        print(f"demo projects: {', '.join(d['name'] for d in dm)}")
        ok = True
    finally:
        if keep and ok:
            print(f"left running: pid {proc.pid} at {url}")
        else:
            stop(proc)
    print("SMOKE OK" if ok else "SMOKE FAILED")


if __name__ == "__main__":
    main()
