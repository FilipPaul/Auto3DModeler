"""🕘 Versions, in headless Edge, in Czech: a block 20 × 10 × 10 -> 🕘 Verze folded at first, unfolded -> 💾 Uložit verzi
"A" -> the extrude 10 -> 15 -> "B" -> the timeline shows both with thumbnails; ⇄ compare A with now: "Vysunutí 1: 10 →
15 mm" and the volume 2000 -> 3000 -> a click on A: the banner, the part at 10, read only (＋ New 3D model, Delete,
Ctrl+Z do nothing) -> ↩ back: 15 -> ⤺ restore A: 10, B still listed, "Před obnovením" kept, ↶ in the toast -> ⑂ variant
"delší" from B: 15, changed to 40 -> switch to hlavní: 10 again -> take the part from "delší": 40 -> reload: the versions,
the variant and the part are there -> Save project with the history and open the file: its versions come with it.
Screenshots of each step. Ends ALL OK / FAILED.

  PYTHONIOENCODING=utf-8 py tools/e2e_versions.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1500,900")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
H = "window.__app.agentHandlers"
M = "window.__app.modeler"
P = "window.__app.project"
V = "window.__app.versions"
W = ".lw-widget[data-w=versions-model]"
fails = []


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(script)


def check(ok, what):
    print("OK  " if ok else "FAIL", what)
    if not ok:
        fails.append(what)


def shot(name):
    d.save_screenshot(str(Path(OUT) / f"versions_{name}.png"))


def volume():
    time.sleep(0.5)
    wait(f"return !{M}.inflight && {M}.result?.body")
    time.sleep(0.4)
    return round(js(f"return {M}.result.body.volume"), 3)


def rows():
    """The timeline: [{id, label, when, thumb (loaded), on}]."""
    return js(f"""return [...document.querySelectorAll('{W} .vr-row:not(.base)')].map(r => ({{id: r.dataset.v,
      label: r.querySelector('.vr-label').textContent, thumb: !!r.querySelector('img.vr-thumb') && r.querySelector('img.vr-thumb').complete
      && r.querySelector('img.vr-thumb').naturalWidth > 0, on: r.classList.contains('on')}}))""")


def row_of(label):
    return next((r for r in rows() if r["label"] == label), None)


def click_row(label):
    d.find_element(By.CSS_SELECTOR, f"{W} .vr-row[data-v='{row_of(label)['id']}'] .vr-text").click()


def save_version(label):
    d.find_element(By.CSS_SELECTOR, f"{W} .vr-save").click()
    inp = wait(f"return document.querySelector('{W} .vr-ask[data-ask=save]')")
    inp = d.find_element(By.CSS_SELECTOR, f"{W} .vr-ask[data-ask=save]")
    inp.send_keys(label, Keys.ENTER)
    wait(f"return [...document.querySelectorAll('{W} .vr-label')].some(e => e.textContent === arguments[0])".replace("arguments[0]", json.dumps(label)), 20)


def toasts():
    return js("return [...document.querySelectorAll('#toasts .toast')].map(e => e.textContent).join(' | ')")


try:
    d.get(URL)
    time.sleep(2)
    if js("return document.documentElement.lang") != "cs":
        d.find_element(By.ID, "langBtn").click()
        time.sleep(0.5)

    # ---- a block 20 × 10 × 10
    call("new_model", name="Kvádr")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 20, "h": 10}}])
    call("add_feature", type="extrude", d=10)
    v = volume()
    ext = js(f"return {M}.part.features.find(f => f.type === 'extrude')")
    check(abs(v - 2000) < 1e-3 and ext["name"] == "Vysunutí 1", f"the block 20 × 10 × 10: {v}, step “{ext['name']}”")
    js("return window.__app.autosave.saveNow()")
    wait(f"return document.querySelector('{W}')?.offsetParent", 10)
    head = js(f"return document.querySelector('{W} .lw-head b')?.textContent")
    folded = js(f"return document.querySelector('{W}').classList.contains('folded')")
    check(head == "🕘 Verze" and folded, f"the widget “{head}” is there, folded at first: {folded}")
    d.find_element(By.CSS_SELECTOR, f"{W} .lw-fold").click()
    time.sleep(0.4)
    check(not js(f"return document.querySelector('{W}').classList.contains('folded')"), "▾ unfolds it")

    # ---- version A, then 10 -> 15, version B
    save_version("A")
    call("edit_feature", id=ext["id"], fields={"d": 15})
    v = volume()
    check(abs(v - 3000) < 1e-3, f"the extrude 10 -> 15: {v}")
    save_version("B")
    time.sleep(1)
    r = rows()
    labels = [x["label"] for x in r]
    check(labels[:2] == ["B", "A"], f"the timeline, the newest first: {labels}")
    check(row_of("A")["thumb"] and row_of("B")["thumb"], "both have a thumbnail of the view")
    parts = js(f"return document.querySelector('{W} .vr-row[data-v=\"{row_of('B')['id']}\"] .vr-parts')?.textContent")
    check(parts == "Změněno: Kvádr", f"B says which part changed: {parts}")
    check("automaticky" in labels or len(labels) == 2, f"automatic versions are labelled “automaticky”: {labels}")
    shot("timeline")

    # ---- ⇄ compare A with now
    d.find_element(By.CSS_SELECTOR, f"{W} .vr-row[data-v='{row_of('A')['id']}'] [data-cmp]").click()
    diff = wait(f"return document.querySelector('{W} .vr-diff')?.innerText", 10)
    check("Vysunutí 1: 10 → 15 mm" in diff, f"compare names the value: {diff!r}")
    check("Objem: 2000 → 3000 mm³" in diff, "compare shows the volume 2000 → 3000 mm³")
    shot("compare")

    # ---- preview A: banner, 10, read only; back
    n_parts = js(f"return {P}.parts.length")
    click_row("A")
    wait("return document.querySelector('.vr-banner')", 15)
    v = volume()
    banner = js("return document.querySelector('.vr-banner').innerText")
    check(abs(v - 2000) < 1e-3, f"previewing A: the part is at 10 ({v})")
    check("Prohlížíte verzi z" in banner and "Zpět na aktuální" in banner and "Obnovit tuto verzi" in banner, f"the banner: {banner!r}")
    check(row_of("A")["on"], "A is marked in the timeline")
    shot("preview")
    d.find_element(By.ID, "newModelBtn").click()
    body = d.find_element(By.TAG_NAME, "body")
    body.send_keys(Keys.CONTROL, "z")
    body.send_keys(Keys.DELETE)
    time.sleep(0.8)
    check(js(f"return {P}.parts.length") == n_parts and abs(volume() - 2000) < 1e-3 and js(f"return !!{V}.preview"),
          "read only: ＋ New 3D model, Ctrl+Z and Delete change nothing")
    check(js("return window.__app.autosave.paused") is True, "the preview is not autosaved")
    d.find_element(By.CSS_SELECTOR, ".vr-banner [data-vb=back]").click()
    wait("return !document.querySelector('.vr-banner')", 15)
    v = volume()
    check(abs(v - 3000) < 1e-3 and not js("return window.__app.autosave.paused"), f"↩ back: the part at 15 again ({v})")

    # ---- restore A
    click_row("A")
    wait("return document.querySelector('.vr-banner')", 15)
    d.find_element(By.CSS_SELECTOR, ".vr-banner [data-vb=restore]").click()
    wait("return !document.querySelector('.vr-banner')", 15)
    time.sleep(1)
    v = volume()
    labels = [x["label"] for x in rows()]
    check(abs(v - 2000) < 1e-3, f"⤺ restored A: the part at 10 ({v})")
    check("B" in labels and "Před obnovením" in labels and labels[0].startswith("Obnoveno: A"), f"B is still listed, the state before kept: {labels}")
    check("↶ Zpět" in toasts(), f"the toast offers ↶: {toasts()[:160]}")
    shot("restored")

    # ---- ⑂ variant "delší" from B, changed to 40
    d.find_element(By.CSS_SELECTOR, f"{W} .vr-row[data-v='{row_of('B')['id']}'] [data-var]").click()
    inp = wait(f"return document.querySelector('{W} .vr-ask[data-ask=variant]')")
    d.find_element(By.CSS_SELECTOR, f"{W} .vr-ask[data-ask=variant]").send_keys("delší", Keys.ENTER)
    wait(f"return document.querySelector('{W} .vr-var')?.selectedOptions[0]?.textContent === 'delší'", 20)
    v = volume()
    check(abs(v - 3000) < 1e-3, f"variant “delší” from B: the part at 15 ({v})")
    check(js(f"return document.querySelectorAll('{W} .vr-row:not(.base)').length") == 0 and js(f"return !!document.querySelector('{W} .vr-row.base')"),
          "the variant's own timeline: empty, “made from B” under it")
    call("edit_feature", id=ext["id"], fields={"d": 40})
    v = volume()
    check(abs(v - 8000) < 1e-3, f"in “delší” the extrude is 40: {v}")
    save_version("C")
    shot("variant")

    # ---- back to hlavní: unchanged
    Select(d.find_element(By.CSS_SELECTOR, f"{W} .vr-var")).select_by_visible_text("hlavní")
    wait(f"return document.querySelector('{W} .vr-var')?.selectedOptions[0]?.textContent === 'hlavní'", 20)
    time.sleep(1)
    v = volume()
    labels = [x["label"] for x in rows()]
    check(abs(v - 2000) < 1e-3 and "C" not in labels and "B" in labels, f"switched to hlavní: the part at 10 ({v}), its own timeline {labels}")

    # ---- take the part from "delší"
    take = d.find_element(By.CSS_SELECTOR, f"{W} .vr-take")
    take.click()
    wait(f"return document.querySelector('{W} .vr-take')?.options.length > 1", 10)
    Select(d.find_element(By.CSS_SELECTOR, f"{W} .vr-take")).select_by_visible_text("delší · Kvádr")
    wait(f"return [...document.querySelectorAll('{W} .vr-label')].some(e => e.textContent.includes('převzat z varianty'))", 20)
    v = volume()
    labels = [x["label"] for x in rows()]
    check(abs(v - 8000) < 1e-3 and js(f"return {V}.data.current") == "main", f"the part taken from “delší”: 40 ({v}) in hlavní: {labels[0]}")
    shot("taken")

    # ---- reload: everything kept
    pid = js("return window.__app.autosave.saveNow().then(() => window.__app.autosave.id)")
    d.refresh()
    time.sleep(2)
    js("return window.__app.autosave.open(arguments[0])", pid)
    wait(f"return {P}.parts.length >= 1", 30)
    wait(f"return {V}.data?.versions?.length", 20)
    time.sleep(0.6)
    v = volume()
    labels = [x["label"] for x in rows()]
    variants = js(f"return [...document.querySelectorAll('{W} .vr-var option')].map(o => o.textContent)")
    check(abs(v - 8000) < 1e-3 and {"A", "B"} <= set(labels) and variants == ["hlavní", "delší"],
          f"reloaded: the part at 40 ({v}), versions {labels[:5]}, variants {variants}")

    # ---- Save project with the version history -> opened as a file: the versions come with it
    proj = js("return window.__app.savedProject({ history: true })")
    nv = len((proj.get("versions") or {}).get("versions") or [])
    check(nv >= 5 and proj["versions"]["objects"], f"the project file holds {nv} versions and their objects ({len(json.dumps(proj)) // 1024} kB)")
    js("""const f = new File([JSON.stringify(arguments[0])], 'kvadr.a3d.json', {type: 'application/json'}), dt = new DataTransfer();
      dt.items.add(f); const i = document.getElementById('projectInput'); i.files = dt.files; i.dispatchEvent(new Event('change'));""", proj)
    wait(f"return window.__app.autosave.id !== arguments[0]".replace("arguments[0]", json.dumps(pid)), 20)
    wait(f"return {V}.pid === window.__app.autosave.id && {V}.data?.versions?.some(m => m.label === 'B')", 20)
    labels = [x["label"] for x in rows()]
    check({"A", "B"} <= set(labels), f"opened from the file: its versions are back {labels[:5]}")
    plain = js("return window.__app.savedProject({ history: false })")
    check("versions" not in plain, "without the option the file has no history")

    # ---- the language: back to English and Czech again
    errs = [x["message"] for x in d.get_log("browser") if x["level"] == "SEVERE" and "favicon" not in x["message"]]
    check(not errs, f"no errors in the console {errs[:3]}")
    shot("end")
finally:
    d.quit()
print("ALL OK" if not fails else f"FAILED: {fails}")
sys.exit(1 if fails else 0)
