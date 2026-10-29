"""The AI seeing and using the suggestions table, in headless Edge (the app is worked through it: select -> it offers
what fits): a plate (sketch + extrude) in Czech -> gui_action {pick: "F2:end"} clicks the top face where it shows ->
gui_state.suggestions: its title, what it is about (the face of the step), the rows with their n and rank, more = the
rows under ⋯ Ukázat vše and their labels; where: "suggest" only the table -> gui_action {suggest: "Díra"}: the hole
command opens, the answer has the table / controls now -> Esc; a hidden row ("Turn it off", English) reached through
⋯ Ukázat vše: the step turned off, the table back to its top rows -> ctrl+z -> an unknown label: refused, the offered
rows named -> get_screenshot {ui: true}: the window with the table drawn where it is (its pixels are the table's, not
the 3D view's background), plain get_screenshot unchanged -> an assembly: pick "I1" -> the part's table, a row run ->
a drawing sheet: a dimension clicked -> its table -> no table: suggest refused.

  PYTHONIOENCODING=utf-8 py tools/e2e_ai_suggest.py http://127.0.0.1:5199 <out dir>
"""
import base64
import json
import sys
import time
from pathlib import Path

from selenium import webdriver

URL, OUT = sys.argv[1], Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
M = "window.__app.modeler"
A = "window.__app.assembly"
S = "window.__app.sheet"
H = "window.__app.agentHandlers"


def wait(script, t=120):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(script)


def call(tool_name, **args):
    return js(f"return {H}[arguments[0]](arguments[1]).then(r => r.text).catch(e => 'ERROR ' + e.message)", tool_name, args)


def act(**args):
    r = call("gui_action", **args)
    return r if r.startswith("ERROR") else json.loads(r)


def table():
    return json.loads(call("gui_state", where="suggest"))["suggestions"]


try:
    d.get(URL)
    wait("return !!window.__app")
    js("localStorage.removeItem('a3d.suggestTop'); sessionStorage.removeItem('a3d.suggestAll')")  # (the default: top 8)
    act(control="CZ")
    call("new_model", name="Deska")
    call("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 60, "h": 40}}])
    call("add_feature", type="extrude", sketch="F1", d=8)
    wait(f"return !!{M}.result?.body")
    call("set_view", view="iso")
    time.sleep(0.8)

    # the top face picked by its name -> the table about it
    r = act(pick="F2:end")
    print("pick F2:end:", r["done"], "| at", r["at"])
    sg = r["suggestions"]
    print("the table:", sg["title"], "| about:", sg["about"], "| where:", sg["where"])
    print("  rows:", [(x["n"], x["icon"], x["label"], x["rank_pos"]) for x in sg["rows"]])
    print("  more:", sg["more"], "| hidden:", sg["all"], "| ⋯ show all n", sg["show_all"])
    assert sg["title"] and "F2" in sg["about"] and "F2:end" in sg["about"], sg
    assert len(sg["rows"]) == 8 and all(x["n"] for x in sg["rows"]), sg["rows"]
    hidden = js("return document.querySelector('.view-suggest .vs-more')?.textContent")
    assert sg["more"] == len(sg["all"]) and sg["more"] > 0 and str(sg["more"] + 8) in hidden, (sg["more"], hidden)
    assert sorted(x["rank_pos"] for x in sg["rows"]) == list(range(1, 9))
    full = json.loads(call("gui_state"))
    rows_n = {x["n"] for x in sg["rows"]}
    assert full["suggestions"]["rows"] == sg["rows"]
    assert all(c["where"] == "suggest" for c in full["controls"] if c["n"] in rows_n)
    only = json.loads(call("gui_state", where="suggest"))["controls"]
    print("where: suggest ->", len(only), "controls, all the table's:", all(c["where"] == "suggest" for c in only))
    assert only and all(c["where"] == "suggest" for c in only)

    # a row run by its Czech label -> the hole command
    r = act(suggest="Díra")
    print("suggest Díra:", r["done"], "| hole command:", js(f"return {M}.cmd?.feature?.type"), "| controls now:", len(r.get("controls", [])))
    assert js(f"return {M}.cmd?.feature?.type") == "hole"
    act(key="Escape")
    wait(f"return !{M}.cmd")
    print("  Esc: the hole kept where the face was clicked -> steps", js(f"return {M}.part.features.map(f => f.type)"), "; ctrl+z")
    act(key="ctrl+z")
    wait(f"return {M}.part.features.length === 2")

    # a hidden row (under ⋯ Ukázat vše), named in English
    r = act(pick="F2:end")
    print("pick again:", r["done"], "| table:", r.get("suggestions", {}).get("title"), r.get("suggestions", {}).get("more"))
    off = next(x for x in table()["all"] if "Vypnout" in x)
    r = act(suggest="turn it off")
    print("suggest 'turn it off' (hidden:", off, "):", r["done"], "| F2 off:", js(f"return {M}.part.features.find(f => f.id === 'F2').suppressed"))
    assert "Show all" in r["done"] and js(f"return !!{M}.part.features.find(f => f.id === 'F2').suppressed")
    assert js("return sessionStorage.getItem('a3d.suggestAll')") is None  # (back to the top rows, as the user had it)
    act(key="ctrl+z")
    wait(f"return !{M}.part.features.find(f => f.id === 'F2').suppressed")

    act(pick="F2:end")
    r = act(suggest="teleport")
    print("an unknown row:", r[:140])
    assert r.startswith("ERROR") and "offers" in r

    # the window as the user sees it: the table drawn where it is
    plain = json.loads(js(f"return {H}.get_screenshot({{}}).then(r => JSON.stringify({{text: r.text, n: r.image.length}}))"))
    shot = js(f"return {H}.get_screenshot({{ui: true}}).then(r => r)")
    (OUT / "suggest-ui.png").write_bytes(base64.b64decode(shot["image"]))
    box = json.loads(shot["text"][shot["text"].rindex("{"):])["suggestions_box"]
    print("get_screenshot ui:", shot["text"][:150], "| plain:", plain["text"][:40])
    # the same picture with the table hidden: in the table's box the two differ (the table, not the 3D view under it)
    bare = js(f"""const b = document.querySelector('.view-suggest'); b.style.visibility = 'hidden';
        return {H}.get_screenshot({{ui: true}}).then(r => {{ b.style.visibility = ''; return r.image; }})""")
    stats = js("""const [a64, b64, b] = arguments; const load = (s) => new Promise((ok) => { const im = new Image(); im.onload = () => {
        const c = document.createElement('canvas'); c.width = im.width; c.height = im.height; const x = c.getContext('2d'); x.drawImage(im, 0, 0);
        ok({ w: im.width, h: im.height, d: x.getImageData(b[0], b[1], b[2] - b[0], b[3] - b[1]).data }); }; im.src = 'data:image/png;base64,' + s; });
        return Promise.all([load(a64), load(b64)]).then(([p, q]) => { let diff = 0, bright = 0, n = 0;
          for (let i = 0; i < p.d.length; i += 4) { n++; if (Math.abs(p.d[i] - q.d[i]) + Math.abs(p.d[i + 1] - q.d[i + 1]) + Math.abs(p.d[i + 2] - q.d[i + 2]) > 30) diff++; if (p.d[i] + p.d[i + 1] + p.d[i + 2] > 450) bright++; }
          return { w: p.w, h: p.h, differs: diff / n, text: bright / n }; });""", shot["image"], bare, box)
    print("  the picture", stats["w"], "×", stats["h"], "| in the table's box: differs from the view under it", round(stats["differs"], 3), "| light text", round(stats["text"], 3))
    assert stats["differs"] > 0.15 and stats["text"] > 0.01
    assert "The window" not in plain["text"] and "3D view" in plain["text"]
    act(key="Escape")

    # an assembly: a part picked by its id -> its table, a row run
    call("new_assembly", name="Sestava")
    call("insert_part", part="Deska")
    wait(f"return Object.values({A}.bodies).every(b => b.body)")
    call("set_view", view="iso")
    time.sleep(0.8)
    r = act(pick="I1")
    sg = r["suggestions"]
    print("assembly pick I1:", r["done"], "| selected", r["selected"], "| table:", sg["title"], "| about:", sg["about"], "| rows", [x["label"] for x in sg["rows"]][:5], "| more", sg["more"])
    assert r["selected"] == "I1" and "I1" in sg["about"] and sg["rows"]
    row = sg["rows"][0]["label"]
    r = act(suggest=row)
    print("  its first row run:", r["done"])
    assert r["done"].startswith("suggestion")
    act(key="Escape")

    # a drawing sheet: a dimension clicked -> its table
    call("sheet_open", part="Deska")
    wait(f"return !!{S}.svgEl")
    dim = next(c for c in json.loads(call("gui_state", where="view"))["controls"] if c["kind"] == "dim")
    r = act(control=dim["n"])
    sg = r.get("suggestions")
    print("sheet: dimension", dim["label"], "clicked -> table:", sg and sg["title"], "| about:", sg and sg["about"], "| rows", sg and [x["label"] for x in sg["rows"]][:5])
    assert sg and sg["rows"]
    shot = js(f"return {H}.get_screenshot({{ui: true}}).then(r => r.text)")
    print("  get_screenshot ui on the sheet:", shot[:120])
    assert "suggestions table" in shot
    act(key="Escape")
    act(at_mm=[5, 5])
    time.sleep(0.4)
    r = act(suggest="Díra") if not js("return document.querySelector('.view-suggest')?.getClientRects().length") else "ERROR (a table still shown)"
    print("no table:", r[:110])
    assert r.startswith("ERROR")
    print("OK")
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
