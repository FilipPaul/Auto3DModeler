"""💾 Save project as an .a3d package, in headless Edge: a project with an imported STEP (▣ Solid from a file), a
sketched part and an assembly of both -> Save project -> the download is <name>.a3d, a ZIP with project.json,
blobs/<the STEP's own name> byte for byte as the source and an iso thumbnail.png -> opened on a fresh page: the same
parts, steps and assembly; the STEP back in the store -> 🕘 Recent projects and the start screen show each project's
picture (img elements, loaded, not blank) -> the 🎬 demo cards show theirs -> no console errors.

Run the test server with its own data folder:
  A3D_DATA=<a scratch folder> py server.py --port 5199 --no-browser
  PYTHONIOENCODING=utf-8 py tools/e2e_project_package.py http://127.0.0.1:5199 <out dir>
"""
import base64
import io
import json
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from auto3d import package  # noqa: E402

URL, OUT = sys.argv[1].rstrip("/"), sys.argv[2]
Path(OUT).mkdir(parents=True, exist_ok=True)
STEP = ROOT / "samples" / "ExportFromOurApp" / "part_base_plate.step"
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
d.set_script_timeout(120)
js = d.execute_script
H = "window.__app.agentHandlers"
fails = []


def check(what, ok, info=""):
    print(("ok   " if ok else "FAIL ") + what + (f" — {info}" if info else ""))
    if not ok:
        fails.append(what)


def wait(script, t=60, *a):
    end = time.time() + t
    while time.time() < end:
        v = js(script, *a)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def call(t, **a):
    r = d.execute_async_script(f"const done = arguments[arguments.length - 1]; {H}[arguments[0]](arguments[1]).then(r => done(r.text), e => done('ERROR ' + e.message))", t, a)
    if r.startswith("ERROR"):
        raise RuntimeError(f"{t} {a}: {r}")
    return r


def fresh():
    d.get(URL)
    wait("return !!window.__app")
    time.sleep(1)


# an <img>'s picture: loaded, and not one colour (drawn into a canvas, its pixels counted)
SEEN = """const im = arguments[0]; if (!im.complete || !im.naturalWidth) return null;
  const c = document.createElement('canvas'); c.width = im.naturalWidth; c.height = im.naturalHeight;
  const g = c.getContext('2d'); g.drawImage(im, 0, 0); const px = g.getImageData(0, 0, c.width, c.height).data, seen = new Set();
  for (let i = 0; i < px.length; i += 4 * 97) seen.add(`${px[i]},${px[i + 1]},${px[i + 2]},${px[i + 3]}`);
  return { w: c.width, h: c.height, colours: seen.size };"""


def pictures(sel):
    out = []
    for im in d.find_elements(By.CSS_SELECTOR, sel):
        end = time.time() + 15
        while time.time() < end and not js("return arguments[0].complete && arguments[0].naturalWidth > 0", im):
            time.sleep(0.1)
        out.append(js(SEEN, im))
    return out


try:
    for p in json.loads(urllib.request.urlopen(f"{URL}/api/projects").read())["projects"]:  # (a clean start)
        urllib.request.urlopen(urllib.request.Request(f"{URL}/api/projects/{p['id']}", method="DELETE"))
    fresh()
    # ---- a project: an imported STEP, a sketched pin, an assembly of both
    src = STEP.read_bytes()
    sha = json.loads(urllib.request.urlopen(urllib.request.Request(f"{URL}/api/blob", src, {"Content-Type": "application/octet-stream"})).read())["sha"]
    call("new_model", name="Plate")
    call("add_feature", type="solid", blob=sha, file=STEP.name, op="add")
    wait("return !!window.__app.modeler.result?.body && !window.__app.modeler.building", 120)
    call("new_model", name="Pin")
    call("add_feature", type="sketch", plane="XY", shapes=[{"circle": {"x": 0, "y": 0, "d": 8}}])
    call("add_feature", type="extrude", sketch="F1", d=20)
    wait("return !!window.__app.modeler.result?.body && !window.__app.modeler.building", 60)
    call("new_assembly", name="Frame")
    call("insert_part", part="Plate")
    call("insert_part", part="Pin")
    wait("return window.__app.assembly.doc?.instances.length === 2 && Object.values(window.__app.assembly.bodies).every(b => b.body)", 60)
    js("window.__app.state.projectName = 'Package test'")
    parts = js("return window.__app.project.parts.map(p => [p.name, p.kind])")
    print("project:", parts)

    # ---- 💾 Save project: the Save dialog stubbed, the bytes kept
    js("""window.__saved = null; window.showSaveFilePicker = async (o) => ({ name: o.suggestedName, createWritable: async () => ({
      write: async (b) => { const u = new Uint8Array(await b.arrayBuffer()); let s = ''; for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode(...u.subarray(i, i + 0x8000));
        window.__saved = [o.suggestedName, b.type, btoa(s)]; }, close: async () => {} }) });""")
    t0 = time.time()
    d.find_element(By.ID, "saveBtn").click()
    name, mime, b64 = wait("return window.__saved", 60)
    raw = base64.b64decode(b64)
    print(f"saved {name} ({mime}, {len(raw) // 1024} kB) in {time.time() - t0:.1f} s")
    check("the download is <name>.a3d", name == "Package test.a3d", name)
    z = zipfile.ZipFile(io.BytesIO(raw))
    check("a valid ZIP", z.testzip() is None, z.namelist())
    man = json.loads(z.read("project.json"))
    check("project.json: an a3d-package of the project", (man["format"], man["package"], man["version"], man["app"]) == ("a3d-package", 1, 3, "Auto3DModeler"))
    check("the STEP under its own name, byte for byte", z.read(f"blobs/{STEP.name}") == src, f"blobs/{STEP.name}")
    check("the STEP is listed by its hash", man["blob_files"].get(sha) == f"blobs/{STEP.name}")
    pic = z.read("thumbnail.png")
    import cv2
    import numpy as np
    im = cv2.imdecode(np.frombuffer(pic, np.uint8), cv2.IMREAD_UNCHANGED)
    check("thumbnail.png: about 512 px, not blank", im is not None and im.shape[1] == 512 and len(np.unique(im.reshape(-1, im.shape[2]), axis=0)) > 20,
          f"{im.shape if im is not None else None}")
    path = Path(OUT) / name
    path.write_bytes(raw)
    old_id = js("return window.__app.autosave.id")
    js("return window.__app.autosave.saveNow().then(() => window.__app.autosave.keepThumb())")  # (its picture kept: a few seconds after a save)
    wait("return fetch('/api/projects').then(r => r.json()).then(j => j.projects.some(p => p.id === arguments[0] && p.thumb))", 30, old_id)

    # ---- opened on a fresh page: the same parts, steps and assembly
    fresh()
    t0 = time.time()
    d.find_element(By.ID, "projectInput").send_keys(str(path.resolve()))
    wait("return window.__app.project.parts.length === 3 && [...document.querySelectorAll('.toast')].some(t => t.textContent.includes('Project loaded'))", 60)
    print(f"opened in {time.time() - t0:.1f} s")
    got = js("return window.__app.project.parts.map(p => [p.name, p.kind])")
    check("the same parts", got == parts, got)
    plate = js("const p = window.__app.project.parts.find(p => p.name === 'Plate'); return window.__app.project.dataOf(p).features")
    check("Plate: its ▣ Solid step on the same file", [f["type"] for f in plate] == ["solid"] and plate[0]["blob"] == sha and plate[0]["file"] == STEP.name, plate)
    pin = js("const p = window.__app.project.parts.find(p => p.name === 'Pin'); return window.__app.project.dataOf(p).features.map(f => f.type)")
    check("Pin: sketch + extrude", pin == ["sketch", "extrude"], pin)
    asm = js("const p = window.__app.project.parts.find(p => p.kind === 'assembly'); return window.__app.project.dataOf(p).instances.length")
    check("the assembly: two placed parts", asm == 2, asm)
    check("the STEP back in the store", urllib.request.urlopen(f"{URL}/api/blob/{sha}").read() == src)
    check("a new project of its own (its own autosave id)", js("return window.__app.autosave.id") != old_id)

    # ---- 🕘 Recent projects: each with its picture (kept a few seconds after a save, at most every few minutes)
    js("return window.__app.autosave.saveNow().then(() => window.__app.autosave.keepThumb())")
    wait("return fetch('/api/projects').then(r => r.json()).then(j => j.projects.filter(p => p.thumb).length >= 2)", 30)
    js("window.__app.autosave.showRecent()")
    wait("return document.querySelectorAll('.choose .aih-row').length >= 2", 15)
    pics = pictures(".choose .aih-row img.aih-thumb")
    print("Recent projects' pictures:", pics)
    check("🕘 Recent projects: img thumbnails, loaded, not blank", len(pics) >= 2 and all(p and p["w"] > 100 and p["colours"] > 3 for p in pics), pics)
    d.save_screenshot(f"{OUT}/pk1_recent.png")
    js("document.querySelector('.choose .choose-x').click()")

    # ---- the start screen (nothing open): the last projects as pictures to click
    fresh()
    wait("return document.body.classList.contains('start-open') && !document.getElementById('startRecent').hidden", 15)
    pics = pictures("#startRecent .st-proj img")
    print("start screen pictures:", pics)
    check("the start screen: recent projects with their pictures", len(pics) >= 2 and all(p and p["colours"] > 3 for p in pics), pics)
    d.save_screenshot(f"{OUT}/pk2_start.png")
    d.find_element(By.CSS_SELECTOR, "#startRecent .st-proj").click()
    wait("return window.__app.project.parts.length === 3", 30)
    check("a click on one opens it", js("return window.__app.state.projectName") == "Package test")

    # ---- 🎬 the demo cards show their pictures
    fresh()
    d.find_element(By.CSS_SELECTOR, "[data-start=demo]").click()
    wait("return document.querySelectorAll('.demos [data-demo]').length >= 3", 15)
    pics = pictures(".demos [data-demo] img.aih-thumb")
    check("🎬 demo cards: their pictures", len(pics) >= 3 and all(p and p["colours"] > 3 for p in pics), f"{len(pics)} pictures")
    d.save_screenshot(f"{OUT}/pk3_demos.png")

    # ---- a file that is not a project says so
    bad = Path(OUT) / "not-a-project.a3d"
    bad.write_bytes(b"{\"app\": \"Auto3DModeler\"}")
    d.find_element(By.CSS_SELECTOR, ".choose .choose-x").click()
    d.find_element(By.ID, "projectInput").send_keys(str(bad.resolve()))
    toast = wait("return [...document.querySelectorAll('.toast')].map(t => t.textContent).find(t => /project file/i.test(t))", 15)
    check("not a project: said in a toast", bool(toast), toast)
finally:
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE" and "favicon" not in e["message"]
            and "/api/project/open" not in e["message"]]  # (the bad file's 400 is expected)
    check("no console errors", not errs, errs[:3])
    d.quit()
print("FAILED:" if fails else "ALL OK", fails if fails else "")
sys.exit(1 if fails else 0)
