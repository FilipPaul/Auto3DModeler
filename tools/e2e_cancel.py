"""✕ Cancel of heavy work, with real clicks in headless Edge — each time: the busy box says Cancelling… once and is gone
within ~2 s, its text never goes back to Building, the kernel process doing the job is stopped (no process of the
server keeps working), and the page does not send the job again:
1. the 44 MB board imported (Open → CAD / 3D file) → Cancel in the busy box;
2. a heavy rebuild (a 120 × 40 × 20 block, 12 M6 holes as real threads): the part shows at once with thread lines
   while the threads are cut in the background (⚙: Cutting real threads) → ✕ Stop there: the part keeps its plain
   body, the Part panel says the threads were not cut; then a normal edit builds as usual (the analytic volume);
3. the MIT E-Vent assembly's drawing sheet (📄 Drawing in the assembly's bar) → Cancel: the sheet says Cancelled, not
   made again on its own; ↻ Try again starts it again.
Also (1b) the top bar's ⚙ N: idle nothing; the board imported again → "⚙ 1", its list shows the import with the file's
name and a running time, its ✕ Stop ends it (the indicator and the busy box gone, the kernel idle).

  PYTHONIOENCODING=utf-8 py tools/e2e_cancel.py http://127.0.0.1:5199 <out dir> <the 44 MB board .step> [<MIT E-Vent .step>]
"""
import json
import math
import os
import re
import subprocess
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.by import By

URL, OUT, BOARD = sys.argv[1], sys.argv[2], sys.argv[3]
EVENT = sys.argv[4] if len(sys.argv) > 4 else os.path.join(os.path.dirname(__file__), "..", "samples", "ToImportToOurApp", "freecad-library", "MIT E Vent Pre Production Model.step")
PORT = int(re.search(r":(\d+)", URL.split("//")[1]).group(1))
M = "window.__app.modeler"
H = "window.__app.agentHandlers"
failed = []


def check(what, ok):
    print(("OK   " if ok else "FAIL ") + what)
    if not ok:
        failed.append(what)


# ------------------------------------------------------------------ the server's kernel processes (Windows)
def server_pid():
    """The server's process id, or None: its socket not seen (a sandbox hides other processes' sockets and ids) —
    the kernel's CPU is then not checked (said so)."""
    out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        p = line.split()
        if len(p) >= 5 and p[1].endswith(f":{PORT}") and p[3] == "LISTENING" and p[4] != "0":
            return int(p[4])
    print(f"NOTE no server process seen on port {PORT} (a sandbox?) — the kernel's CPU is not checked")
    return None


PS = ("Get-CimInstance Win32_Process -Filter 'ParentProcessId=%d' | ForEach-Object { [pscustomobject]@{pid=$_.ProcessId; "
      "cpu=($_.UserModeTime+$_.KernelModeTime)/1e7} } | ConvertTo-Json -Compress")


def kernel_cpu():
    """{pid: CPU seconds} of the server's child processes (the kernel's)."""
    out = subprocess.run(["powershell", "-NoProfile", "-c", PS % SPID], capture_output=True, text=True).stdout.strip()
    v = json.loads(out) if out else []
    return {p["pid"]: p["cpu"] for p in (v if isinstance(v, list) else [v])}


def idle_kernel(what, secs=2.0):
    """No kernel process works for `secs` (each gains < 0.3 s of CPU)."""
    if SPID is None:
        print(f"SKIP {what}: the kernel's CPU (no server process seen)")
        return
    a = kernel_cpu()
    time.sleep(secs)
    b = kernel_cpu()
    busy = {p: round(b[p] - a.get(p, 0), 2) for p in b if b[p] - a.get(p, 0) > 0.3}
    check(f"{what}: no kernel process keeps working {busy or ''}", not busy)


# ------------------------------------------------------------------ the browser
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
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


def call(tool, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool, args)


# every change of the busy boxes (the app's and the 3D model's), with its time
LOG = """window.__blog = []; const T = performance.now(); let last = '';
const look = () => { const b = document.getElementById('busy'), m = document.querySelector('#modelViewport .m-busy');
  const s = [b.hidden ? '' : b.querySelector('.busy-text').textContent, !m || m.hidden ? '' : m.querySelector('span').textContent];
  const k = s.join('|'); if (k !== last) { last = k; window.__blog.push([Math.round(performance.now() - T), ...s]); } };
new MutationObserver(look).observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['hidden'] });
window.__blogT = setInterval(look, 50);
window.__sent = []; if (!window.__fetch0) { window.__fetch0 = window.fetch; window.fetch = (u, o) => { if (!/progress|agent|projects|chat/.test(String(u))) window.__sent.push([Math.round(performance.now() - T), String(u)]); return window.__fetch0(u, o); }; }
window.__blogAt = () => performance.now() - T;"""


def log():
    return js("return window.__blog")


def after_cancel(entries, t_click, col=0):
    """The texts one box showed from Cancelling… on (col 0: the app's box, 1: the 3D model's), repeats dropped."""
    texts = [e[1 + col] for e in entries if e[0] >= t_click - 100]
    texts = texts[texts.index("Cancelling…"):] if "Cancelling…" in texts else texts
    return [x for k, x in enumerate(texts) if not k or x != texts[k - 1]]


def cancel_click(selector):
    t = js("return window.__blogAt()")
    d.find_element(By.CSS_SELECTOR, selector).click()
    return t


try:
    SPID = server_pid()
    d.get(URL)
    wait("return !!window.__app")

    # ---- 1. the board's import -> Cancel
    print("1. the 44 MB board imported, Cancel after 3 s")
    js(LOG)
    d.find_element(By.ID, "cadInput").send_keys(os.path.abspath(BOARD))
    wait("return !document.getElementById('busy').hidden", 30)
    time.sleep(3)
    t = cancel_click("#busyCancel")
    gone = wait("return document.getElementById('busy').hidden && window.__blogAt()", 10) - t
    texts = after_cancel(log(), t)
    print("   busy texts after the click:", texts, f"| gone after {gone / 1000:.2f} s")
    check("the import's busy box is gone within 2 s", gone < 2000)
    check("its text: Cancelling…, then nothing — never Building / Reading again", texts == ["Cancelling…", ""])
    idle_kernel("after the import's Cancel")
    check("no 3D model was opened", js("return window.__app.state.workspace") != "model")
    check("nothing was sent again", not [u for _, u in js("return window.__sent") if "import" in u][1:])

    # ---- 1b. ⚙ in the top bar: the import listed with its file, ✕ Stop there ends it
    print("1b. the board imported again, stopped from the ⚙ jobs list")
    check("idle: no ⚙", js("return document.getElementById('jobsBtn').hidden"))
    js(LOG)
    d.find_element(By.ID, "cadInput").send_keys(os.path.abspath(BOARD))
    wait("return !document.getElementById('jobsBtn').hidden", 15)
    time.sleep(2.5)
    btn = d.find_element(By.ID, "jobsBtn")
    print("   the indicator:", btn.text)
    check("the indicator says ⚙ 1", btn.text.replace(" ", "") == "⚙1")
    btn.click()
    wait("return !document.getElementById('jobsList').hidden && document.querySelectorAll('#jobsList .jobs-row').length", 5)
    row = d.find_element(By.CSS_SELECTOR, "#jobsList .jobs-row")
    print("   the list:", " | ".join(r.text.replace("\n", " · ") for r in d.find_elements(By.CSS_SELECTOR, "#jobsList .jobs-row")))
    check("the list shows the import with its file's name", "Importing a file" in row.text and os.path.basename(BOARD) in row.text)
    t1 = row.find_element(By.CSS_SELECTOR, ".jobs-time").text
    time.sleep(1.2)
    t2 = row.find_element(By.CSS_SELECTOR, ".jobs-time").text
    check(f"its time runs ({t1} -> {t2})", t2 != t1)
    d.save_screenshot(os.path.join(OUT, "cancel_jobs_list.png"))
    t0 = time.time()
    row.find_element(By.CSS_SELECTOR, "[data-stop]").click()
    wait("return document.getElementById('jobsBtn').hidden && document.getElementById('busy').hidden", 10)
    print(f"   ⚙ gone after {time.time() - t0:.2f} s")
    check("✕ Stop ends it: the indicator and the busy box are gone within 3 s", time.time() - t0 < 3)
    texts = after_cancel(log(), 0)
    check(f"the busy box: Cancelling…, then nothing {texts}", texts == ["Cancelling…", ""])
    idle_kernel("after ✕ Stop")
    check("no 3D model was opened", js("return window.__app.state.workspace") != "model")

    # ---- 2. a heavy rebuild (12 real threads): shown at once, the cut stopped from ⚙; then a normal edit
    print("2. a part with 12 real threads: shown at once, its cut stopped from the ⚙ jobs list")
    call("new_model", name="Threads")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 120, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=20)
    pts = [[-50 + 20 * i, -10 + 20 * j] for i in range(6) for j in range(2)]
    call("add_feature", type="hole", face="F2:end", points=pts, through=True, thread="M6")
    wait(f"return !{M}.inflight && {M}.result?.body", 60)
    plain = 120 * 40 * 20 - 12 * math.pi * 2.5 ** 2 * 20
    v0 = js(f"return {M}.result.body.volume")
    check(f"12 M6 holes, plain ({v0:.1f} mm³)", abs(v0 - plain) < 1e-3)
    js(LOG)
    t0 = time.time()
    js(f"{M}.part.threads = 'real'; {M}.rebuild()")
    wait(f"return !{M}.inflight && !!{M}.result?.threads?.real?.pending", 30)
    print(f"   shown in {time.time() - t0:.2f} s, the threads being cut:", js("return document.querySelector('#modelRight .mp-thr-pending')?.textContent"))
    check("the part shows at once with thread lines, as it was", abs(js(f"return {M}.result.body.volume") - v0) < 1e-6 and js(f"return {M}.view.threadCount") == 12)
    wait("return !document.getElementById('jobsBtn').hidden", 15)
    time.sleep(1.5)
    check("the real threads are still being cut", js(f"return !!{M}.threading"))
    d.find_element(By.ID, "jobsBtn").click()
    wait("return !document.getElementById('jobsList').hidden && document.querySelectorAll('#jobsList .jobs-row').length", 5)
    row = next(r for r in d.find_elements(By.CSS_SELECTOR, "#jobsList .jobs-row") if "Cutting real threads" in r.text)
    print("   the list:", row.text.replace("\n", " · "))
    check("⚙ lists the cut with its part", "Threads" in row.text)
    t = time.time()
    row.find_element(By.CSS_SELECTOR, "[data-stop]").click()
    wait(f"return !{M}.threading", 10)
    print(f"   the cut ended {time.time() - t:.2f} s after ✕ Stop")
    check("✕ Stop ends the cut within 2 s", time.time() - t < 2)
    stopped = js("return document.querySelector('#modelRight .mp-bad')?.textContent")
    print("   the Part panel:", stopped)
    check("the Part panel says the threads were not cut", stopped is not None and "not cut" in stopped)
    check("the part keeps its plain body (and the lines)", abs(js(f"return {M}.result.body.volume") - v0) < 1e-6 and js(f"return {M}.view.threadCount") == 12)
    check("the 3D model's box stayed hidden", js("return document.querySelector('#modelViewport .m-busy').hidden"))
    idle_kernel("after ✕ Stop of the cut")
    sent = [u for _, u in js("return window.__sent") if "rebuild" in u]
    check(f"nothing was sent again (the part and its cut: {len(sent)} sent)", len(sent) == 2)
    d.save_screenshot(os.path.join(OUT, "cancel_rebuild.png"))
    # a normal edit: a fresh build as usual (threads hidden, the block 25 high)
    js(f"{M}.part.threads = null; {M}.part.features[1].d = 25; {M}.commit()")
    wait(f"return !{M}.inflight && Math.abs({M}.result.body.volume - {120 * 40 * 25 - 12 * math.pi * 2.5 ** 2 * 25}) < 1e-3", 60)
    check("a new edit builds normally (the analytic volume)", True)
    check("the Cancelled note is gone", js("return document.querySelector('#modelViewport .m-busy').hidden"))

    # ---- 3. the MIT E-Vent assembly's sheet -> Cancel
    print("3. MIT E-Vent's drawing sheet, Cancel")
    d.find_element(By.ID, "cadInput").send_keys(os.path.abspath(EVENT))
    wait("return !!document.querySelector('.choose-back')", 120)
    next(o for o in d.find_elements(By.CSS_SELECTOR, ".choose-back .choose-opts button") if o.text.startswith("Open as an assembly")).click()
    wait("return window.__app.state.workspace === 'assembly' && document.getElementById('busy').hidden", 180)
    time.sleep(1)
    js(LOG)
    d.find_element(By.CSS_SELECTOR, "#asmViewport [data-a=sheet]").click()
    wait("return window.__app.state.workspace === 'sheet' && !document.getElementById('busy').hidden", 30)
    time.sleep(3)
    check("the busy box shows in the sheet (it was in the hidden quick-part view)", js("return document.getElementById('busy').getClientRects().length > 0"))
    d.save_screenshot(os.path.join(OUT, "cancel_sheet_busy.png"))
    t = cancel_click("#busyCancel")
    gone = wait("return document.getElementById('busy').hidden && window.__blogAt()", 10) - t
    texts = after_cancel(log(), t)
    print("   busy texts after the click:", texts, f"| gone after {gone / 1000:.2f} s")
    check("the sheet's busy box is gone within 2 s", gone < 2000)
    check("its text: Cancelling…, then nothing — never Making / Building again", texts == ["Cancelling…", ""])
    time.sleep(3)
    check("not made again on its own", js("return document.getElementById('busy').hidden") and len([u for _, u in js("return window.__sent") if "/api/sheet" in u]) == 1)
    check("the sheet says Cancelled, with ↻ Try again", "Cancelled" in d.find_element(By.CSS_SELECTOR, "#shViewport .sh-stage").text
          and bool(d.find_elements(By.CSS_SELECTOR, "#shViewport [data-a=retry]")))
    idle_kernel("after the sheet's Cancel")
    n = len([u for _, u in js("return window.__sent") if "/api/sheet" in u])
    d.find_element(By.CSS_SELECTOR, "#shViewport [data-a=retry]").click()
    time.sleep(1)
    check("↻ Try again makes it again", len([u for _, u in js("return window.__sent") if "/api/sheet" in u]) == n + 1
          and not js("return document.getElementById('busy').hidden"))
    js("document.getElementById('busyCancel').click()")
    wait("return document.getElementById('busy').hidden", 10)

    errs = [m["message"] for m in d.get_log("browser") if m["level"] == "SEVERE" and "favicon" not in m["message"] and "409" not in m["message"]]
    check(f"no console errors {errs[:3]}", not errs)
finally:
    d.quit()
print("FAILED:" if failed else "ALL OK", *failed, sep="\n  ")
sys.exit(1 if failed else 0)
