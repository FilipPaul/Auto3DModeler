"""🎬 Save animation of a mechanism, in headless Edge: the crank demo opened -> ⚙ Mechanism ⋯ shows 🎬 Save animation,
GIF / video and the name caption -> a GIF saved: the progress line counts the frames, the page answers meanwhile, the file
(downloaded from the data folder) has ≥ 20 frames of the view's size (≤ 1280 across), looping, the frames differ one
from the next (the slider moves) -> the parts back where they were -> Cancel halfway: nothing saved, the parts back ->
a video when headless Edge can record one (else skipped, said so) -> the AI's record_animation (the path in the data
folder) and gui_state's `animation` -> Czech labels -> no console errors. One GIF is kept in <out dir>/crank.gif.

  PYTHONIOENCODING=utf-8 py tools/e2e_mechanism_anim.py http://127.0.0.1:5199 <out dir>
"""
import io
import json
import os
import sys
import time
import urllib.request

from PIL import Image, ImageChops
from selenium import webdriver
from selenium.webdriver.common.by import By

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.add_argument("--lang=en-US")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
A = "window.__app.assembly"
H = "window.__app.agentHandlers"
bad = []


def check(ok, what):
    print(("  ok  " if ok else "  FAIL") + " " + what)
    if not ok:
        bad.append(what)


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def call(t, **a):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", t, a)


def mats():
    return js(f"return {A}.doc.instances.map(i => [...i.matrix])")


def same(a, b):
    return all(abs(p - q) < 1e-6 for x, y in zip(a, b) for p, q in zip(x, y))


def fetch(url):
    return urllib.request.urlopen(f"{URL}{url}").read()


def note():
    return js(f"const a = {A}.mech.anim, n = a && Object.values(a.notes).pop(); return n ? {{ ...n, text: document.querySelector('.mc-anim + .as-dofnote')?.textContent || '' }} : null")


def record(fmt, cancel_at=None):
    """🎬 clicked with format fmt -> (the stages seen, the slowest answer of the page meanwhile in s, the last note)."""
    js(f"const s = document.querySelector('[data-mcafmt=\"0\"]'); s.value = arguments[0]; s.dispatchEvent(new Event('change'))", fmt)
    js(f"{A}.mech.anim.notes = {{}}")
    d.find_element(By.CSS_SELECTOR, "[data-mcanim='0']").click()
    stages, slow = set(), 0.0
    end = time.time() + 180
    while time.time() < end:
        t0 = time.time()
        st = js("const e = document.querySelector('.mc-astage'); return e ? e.textContent : null")
        slow = max(slow, time.time() - t0)
        if st:
            stages.add(st.split(" ")[1] if " " in st else st)
            if cancel_at and "/" in st and int(st.split("/")[0].split()[-1]) >= cancel_at:
                d.find_element(By.CSS_SELECTOR, "[data-mcacancel]").click()
                cancel_at = None
        elif note() and not js(f"return !!{A}.mech.anim.job"):
            break
        time.sleep(0.15)
    return stages, slow, note()


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('a3d.leftDock'); localStorage.setItem('auto3d-lang', 'en')")
    d.get(URL)
    wait("return !!window.__app")
    d.find_element(By.ID, "openBtn").click()
    time.sleep(0.2)
    js("document.getElementById('demoBtn').click()")
    wait("return document.querySelectorAll('.demos [data-demo]').length")
    row = next(r for r in d.find_elements(By.CSS_SELECTOR, ".demos [data-demo]") if "klikovy" in r.get_attribute("data-demo"))
    row.find_element(By.CSS_SELECTOR, "[data-open]").click()
    wait(f"return window.__app.state.workspace === 'assembly' && {A}.doc.instances.length > 1 && {A}.doc.instances.every(i => {A}.bodies[i.part]?.body) && {A}.mech.list.length")
    time.sleep(0.8)
    d.find_element(By.CSS_SELECTOR, "[data-mcmore='0']").click()
    time.sleep(0.3)
    btn = d.find_elements(By.CSS_SELECTOR, "[data-mcanim='0']")
    fmts = js("return [...document.querySelectorAll('[data-mcafmt=\"0\"] option')].map(o => [o.value, o.textContent])")
    cap = js("return document.querySelector('[data-mcacap=\"0\"]')?.checked")
    check(btn and btn[0].text == "🎬 Save animation" and fmts[0] == ["gif", "GIF"] and cap, f"⋯ shows 🎬 Save animation, {fmts}, the name caption on")
    d.save_screenshot(f"{OUT}/anim_menu.png")
    size = js(f"const el = {A}.view.container, w = Math.min(1280, el.clientWidth) & ~1; return [w, Math.round(w * el.clientHeight / el.clientWidth) & ~1]")
    m0 = mats()

    # a GIF
    t0 = time.time()
    stages, slow, n = record("gif")
    print(f"  GIF in {time.time() - t0:.1f} s; stages {sorted(stages)}; the page's slowest answer {slow:.2f} s; note {n and n['text']}")
    check("Recording" in stages and slow < 1.0, f"the progress line counted the frames ({sorted(stages)}), the page answered within {slow:.2f} s")
    f = (n or {}).get("file") or {}
    check(n and n["text"].startswith("🎬 Saved: ") and f.get("format") == "gif", f"saved: {n and n['text']}")
    gif = Image.open(io.BytesIO(fetch(f["url"])))
    frames = []
    for k in range(gif.n_frames):
        gif.seek(k)
        frames.append(gif.convert("RGB"))
    diffs = [ImageChops.difference(a, b).getbbox() is not None for a, b in zip(frames, frames[1:])]
    print(f"  the GIF: {gif.n_frames} frames, {gif.size}, {gif.info.get('duration')} ms each, loop {gif.info.get('loop')}, {f['bytes']} bytes; frames that differ from the one before {sum(diffs)} / {len(diffs)}")
    check(gif.n_frames >= 20 and list(gif.size) == size and gif.info.get("loop") == 0, f"≥ 20 frames ({gif.n_frames}) of the view's size {size} ({gif.size}), looping")
    check(sum(diffs) >= 0.95 * len(diffs), "the frames differ one from the next: the mechanism moves")
    mid = frames[len(frames) // 2]
    check(ImageChops.difference(frames[0], mid).getbbox() is not None, "half a turn on, the picture is another")
    check(os.path.isfile(f["path"]) and os.path.getsize(f["path"]) == f["bytes"], f"the file is in the data folder: {f['path']}")
    with open(f"{OUT}/crank.gif", "wb") as fh:
        fh.write(fetch(f["url"]))
    check(same(mats(), m0), "the parts are back where they were")
    gs = json.loads(call("gui_state"))
    check(gs.get("animation", {}).get("saved") == f["file"], f"gui_state animation: {gs.get('animation')}")

    # Cancel halfway
    stages, slow, n = record("gif", cancel_at=8)
    check(n and n["text"] == "🎬 Cancelled." and same(mats(), m0), f"Cancel: {n and n['text']}, the parts back")

    # a video, where headless Edge records one
    if any(v == "video" for v, _ in fmts):
        stages, slow, n = record("video")
        f = (n or {}).get("file") or {}
        print(f"  video: {n and n['text']}")
        raw = fetch(f["url"]) if f.get("url") else b""
        kind = "webm" if raw[:4] == b"\x1a\x45\xdf\xa3" else "mp4" if raw[4:8] == b"ftyp" else None
        check(kind == f.get("format") and len(raw) > 2000 and same(mats(), m0), f"a video: {f.get('file')}, {len(raw)} bytes, {kind}")
    else:
        print("  (skipped: this browser cannot record a video from a canvas — only GIF is offered)")

    # the AI
    r = call("record_animation", format="gif")
    print("  record_animation:", r[:220])
    path = r.split(" — ")[1].split(" (")[0] if " — " in r else ""
    check("saved as GIF" in r and os.path.isfile(path), f"record_animation: the file in the data folder ({path})")
    r = call("record_animation", mechanism="nothing like it")
    check(r.startswith("ERROR No mechanism"), f"record_animation of no such mechanism: {r[:90]}")

    # Czech
    d.find_element(By.ID, "langBtn").click()
    time.sleep(0.6)
    b = d.find_element(By.CSS_SELECTOR, "[data-mcanim='0']")
    cap = d.find_element(By.CSS_SELECTOR, ".mc-cap").get_attribute("title")
    saved = d.find_element(By.CSS_SELECTOR, ".mc-anim + .as-dofnote").text
    check(b.text == "🎬 Uložit animaci" and cap.startswith("Název mechanismu") and saved.startswith("🎬 Uloženo: ") and "snímků" in saved,
          f"Czech: {b.text} | {cap} | {saved}")
    d.save_screenshot(f"{OUT}/anim_cs.png")
    d.find_element(By.ID, "langBtn").click()
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE" and "favicon" not in e["message"] and "/api/ai/access" not in e["message"]]
    check(not errs, f"no errors in the console: {errs[:3]}")
finally:
    d.quit()

print("\nmechanism animation:", "ALL OK" if not bad else f"{len(bad)} FAILED: {bad}")
sys.exit(1 if bad else 0)
