"""📚 Test probes in the parts library, in headless Edge and in Czech: 📚 Knihovna -> Testovací jehly (pogo pins) ->
INGUN (a heading that opens) -> a GKS-100 variant (GKS-100 214 130 A 2000): its Czech description, "Rozměry podle
katalogu", the datasheet / STEP links, a 3D preview 33.4 long -> ⤵ into an assembly -> a search for "1.27" finds the
50-mil ones only.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_library_probes.py http://127.0.0.1:5199 <out dir>
"""
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


def search(q):
    box = d.find_element(By.CSS_SELECTOR, ".lib .lib-q")
    box.clear()
    box.send_keys(q)
    time.sleep(0.4)
    return [b.get_attribute("data-item") for b in d.find_elements(By.CSS_SELECTOR, ".lib .lib-item")]


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.setItem('auto3d-lang', 'cs')")
    d.get(URL)
    wait("return !!window.__app")
    call("new_assembly", name="Fixture")
    wait("return window.__app.state.workspace === 'assembly'")
    d.find_element(By.ID, "libBtn").click()
    wait("return window.__app.library.items?.length > 10 && !!document.querySelector('.lib .lib-item')")
    js("document.querySelector('.lib .lib-q').value = ''; window.__app.library.state.q = ''; window.__app.library.renderList()")
    groups = [g.text for g in d.find_elements(By.CSS_SELECTOR, ".lib .lib-gname")]
    check("the group Testovací jehly (pogo pins)", any(g.startswith("TESTOVACÍ JEHLY (POGO PINS)") or g.startswith("Testovací jehly (pogo pins)") for g in groups), groups)
    check("the group Pouzdra (receptacles)", any("pouzdra (receptacles)" in g.lower() for g in groups), "")
    subs = js("return [...document.querySelectorAll('.lib [data-sub]')].map(b => b.dataset.sub)")
    check("makers as headings (INGUN, KESACON)", "Test probes|INGUN" in subs and "Test probes|KESACON" in subs, subs)
    check("closed: no probe listed yet", not d.find_elements(By.CSS_SELECTOR, ".lib [data-item^='ingun-gks']"))
    d.find_element(By.CSS_SELECTOR, ".lib [data-sub='Test probes|INGUN']").click()
    time.sleep(0.3)
    listed = [b.get_attribute("data-item") for b in d.find_elements(By.CSS_SELECTOR, ".lib .lib-subitems [data-item]")]
    check("INGUN opened: its GKS probes", "ingun-gks100-214" in listed and all(x.startswith("ingun-gks") for x in listed), listed)
    d.find_element(By.CSS_SELECTOR, ".lib [data-item='ingun-gks100-214']").click()
    time.sleep(0.3)
    js("const s = document.querySelector('.lib [data-k=size]'); s.value = arguments[0]; s.dispatchEvent(new Event('change'))", "Ø1.3 · 2 N")
    wait("return !!window.__app.library.lastBody && document.querySelector('.lib h2')?.textContent.includes('214 130')", 30)
    time.sleep(0.5)
    det = d.find_element(By.CSS_SELECTOR, ".lib .lib-detail")
    h2 = det.find_element(By.CSS_SELECTOR, "h2").text
    check("the variant GKS-100 214 130 A 2000", h2 == "INGUN GKS-100 214 130 A 2000", h2)
    desc = det.find_element(By.CSS_SELECTOR, ".lib-desc").text
    check("its description in Czech", "testovací jehla" in desc and "GKS-100-0008" in desc and "rastr 2.54 mm" in desc, desc[:120])
    check("Rozměry podle katalogu", det.find_element(By.CSS_SELECTOR, ".lib-acc").text.endswith("Rozměry podle katalogu"))
    links = {a.get_attribute("data-link"): a.get_attribute("href") for a in det.find_elements(By.CSS_SELECTOR, ".lib-links a")}
    check("datasheet + STEP links (ingun.com)", links.get("datasheet", "").endswith("GKS-100-0008_EN_Datasheet.pdf") and links.get("cad", "").endswith(".STEP"), links)
    facts = det.find_element(By.CSS_SELECTOR, ".lib-facts").text.replace("\n", " ")
    check("maker, part number, INGUN item no.", "INGUN" in facts and "GKS-100 214 130 A 2000" in facts and "GKS-100-0008" in facts, facts)
    bb = js("const b = window.__app.library.lastBody.bbox; return [b[3]-b[0], b[4]-b[1], b[5]-b[2]].map(v => +v.toFixed(2))")
    check("the preview: Ø1.37 barrel, 33.4 long", bb == [1.37, 1.37, 33.4], bb)
    d.save_screenshot(f"{OUT}/probes-library.png")
    d.find_element(By.CSS_SELECTOR, ".lib [data-a=insert]").click()
    wait(f"return {A}.doc.instances.length === 1 && !!{A}.bodies[{A}.doc.instances[0].part]?.body", 60)
    pn = js(f"const p = {A}.doc.instances[0].part; return window.__app.project.parts.find(x => x.id === p).data.library.pn")
    check("in the assembly, with its part number", pn == "GKS-100 214 130 A 2000", pn)
    d.find_element(By.ID, "libBtn").click()
    wait("return !!document.querySelector('.lib .lib-item')")
    found = search("1.27")
    check("search 1.27: the 50-mil ones only", found and all(x.startswith(("ingun-gks050", "ingun-ks050", "kesacon-mpi050")) for x in found), found)
    check("  … probes and their receptacle", "ingun-gks050-201" in found and "ingun-ks050" in found and "kesacon-mpi050-f" in found)
    found = search("korunka 2.54")
    check("search korunka 2.54 (Czech head style)", "ingun-gks100-214" in found, found)
    found = search("GKS-100-0008")
    check("search by INGUN item no.", found[:1] == ["ingun-gks100-214"], found)
    d.save_screenshot(f"{OUT}/probes-search.png")
    js("document.querySelector('.lib .choose-x').click()")
finally:
    errs = [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    js("localStorage.removeItem('auto3d-lang')")
    d.quit()
    print("FAILED:" if fails else "ALL OK", fails)
