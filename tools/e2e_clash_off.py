"""⚠ The collision check switched off for a placed part and for a whole assembly (a big STEP: parts that touch by
design). Two blocks placed on each other collide; ⚠ No collision check for it on one of them: no collision; on again:
the collision is back; ⚠ Turn the collision check off for the assembly: the bar says "Kolize vypnuté" and a change
starts no check; a STEP assembly import starts with it off.

  PYTHONIOENCODING=utf-8 py tools/e2e_clash_off.py http://127.0.0.1:5199 <out dir>
"""
import sys
import time

from selenium import webdriver

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
H = "window.__app.agentHandlers"
A = "window.__app.assembly"
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
    print(("OK   " if ok else "FAIL ") + what)
    if not ok:
        fails.append(what)


def clashes():
    """The check run now (as ⚠ Check does), its count."""
    js(f"{A}.checkClashes()")
    time.sleep(0.3)
    wait(f"return !{A}.clashBusy", 90)
    return js(f"return ({A}.clashes || []).length")


def rows():
    """The part's whole table (⋯ Ukázat vše opened: a rare choice sits there)."""
    js("const b = [...document.querySelectorAll('#asmViewport .view-suggest button')].find(x => /Ukázat vše|Show all/.test(x.textContent)); b && b.click()")
    time.sleep(0.3)
    return js("return [...document.querySelectorAll('#asmViewport .view-suggest button')].map(b => b.textContent.trim())")


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.setItem('auto3d-lang', 'cs')")
    d.refresh()
    wait("return !!window.__app")
    call("new_model", name="Block")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    call("add_feature", type="extrude", sketch="F1", d=10)
    call("new_assembly", name="Stack")
    call("insert_part", part="Block")
    call("insert_part", part="Block")
    wait(f"return {A}.doc.instances.length === 2 && Object.values({A}.bodies).every(b => b.body)")
    js(f"const a = {A}; a.doc.instances[1].matrix = [...a.doc.instances[0].matrix]; a.commit()")  # (on each other: they collide)
    n0 = clashes()
    check(n0 >= 1, f"two blocks on each other: {n0} collision(s)")

    js(f"{A}.select(['I2'])")
    time.sleep(0.5)
    r = rows()
    check(any("Nekontrolovat jeho kolize" in x for x in r), f"the part's table offers ⚠ Nekontrolovat jeho kolize: {r}")
    js(f"{A}.toggleNoClash(['I2'])")
    n1 = clashes()
    check(n1 == 0 and js(f"return !!{A}.inst('I2').noClash"), f"left out of the check: {n1} collisions")
    js(f"{A}.select(['I2'])")
    time.sleep(0.5)
    check(any("Znovu kontrolovat jeho kolize" in x for x in rows()), "…its row now says Znovu kontrolovat")
    js(f"{A}.toggleNoClash(['I2'])")
    check(clashes() == n0, "checked again: the collision is back")

    js(f"{A}.select([])")
    time.sleep(0.5)
    js(f"{A}.toggleClashOff()")
    time.sleep(0.3)
    bar = js(f"return {A}.$('.m-cmdbar [data-a=clashes]')?.textContent || ''")
    check(js(f"return !!{A}.doc.clashOff") and "Kolize vypnuté" in bar, f"the assembly's check off: the bar says {bar!r}")
    js(f"const a = {A}; a.clashes = null; a.doc.instances[1].matrix[12] += 1; a.commit()")
    time.sleep(1.5)
    check(js(f"return {A}.clashes === null && !{A}.clashBusy"), "a change starts no automatic check")
    check(clashes() >= 1, "⚠ Check still asks once")
    js(f"{A}.toggleClashOff()")
    check(not js(f"return !!{A}.doc.clashOff"), "on again")

    # a STEP assembly starts with it off (stepfile.js's docs)
    src = js("return fetch('/js/assembly/stepfile.js').then(r => r.text())")
    check("clashOff: true" in src, "a STEP import's assemblies start with the check off")

    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    check(not errs, f"no console errors: {errs[:3]}")
finally:
    d.quit()
print("ALL OK" if not fails else f"{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
