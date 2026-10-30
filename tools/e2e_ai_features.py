"""The AI reaches the features of 2026-10-29 / 30 (the audit in docs/ARCHITECTURE-modeler.md, "AI tools for the new
features"), each tool through /api/agent/call as the MCP server calls it, with the page open in headless Edge:
- holes: a threaded M5 counterbore by shape / thread / standard, 🔒 lock true -> get_model lock + from; edit_feature
  {lock: [{x: true}]}, {lock: false}; a wrong lock refused;
- the crank demo: set_travel {min: "here"} / {max: "here"} where move_free left it; both "here" refused;
  set_view {joints: false / true} (the bottom row's 🔗 Joints follows);
- a cable harness: edit_harness insert_points / set_points / order / remove_points (a span's own length kept with its
  two points), a wrong number refused; an igus chain from library_add, edit_chain {links, travel, moves_with, name},
  travel while moving with a part refused; library_search finds P-clamps and e-chains;
- a drawing sheet: sheet_edit move {id: {view}} (the same size in another view, a new id), a view it cannot go in
  refused with the ones it can;
- set_layout: the widgets listed, the suggestions docked right / floated, folded, rows, auto height, the table closed /
  automatic; reset;
- new_project: the project kept, an empty one in this window.

  PYTHONIOENCODING=utf-8 py tools/e2e_ai_features.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time
import urllib.request

from selenium import webdriver

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
A = "window.__app.assembly"
fails = []


def check(what, ok, got=""):
    print(f"{'OK ' if ok else 'BAD'} {what}{f' — {got}' if got != '' else ''}")
    if not ok:
        fails.append(what)


def ai(tool, **args):
    req = urllib.request.Request(f"{URL}/api/agent/call", data=json.dumps({"tool": tool, "args": args}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        res = json.loads(r.read())
    return ("ERROR " if res.get("isError") else "") + "".join(c.get("text", "") for c in res.get("content", []))


def tail_json(text):
    """The JSON at the end of an answer ("… text. {json}")."""
    return json.loads(text[text.index("{"):]) if "{" in text else {}


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        if js(script):
            return True
        time.sleep(0.25)
    raise TimeoutError(script)


try:
    d.get(URL)
    wait("return !!window.__app")
    time.sleep(2)  # (the page polls for the AI's calls)

    # ---------------------------------------------------------------- holes: shape / thread / size, 🔒 locks, distances
    ai("new_model", name="Lock plate")
    ai("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": -30, "y": -20, "w": 60, "h": 40}}])
    ai("add_feature", type="extrude", sketch="F1", d=10)
    r = ai("add_feature", type="hole", face="F2:end", points=[[-15, 0], [15, 0]], standard="M5", shape="counterbore", thread=True, lock=True)
    check("add_feature hole: threaded M5 counterbore with lock", not r.startswith("ERROR"), r[:160])
    steps = json.loads(ai("get_model"))["steps"]
    h = next(s for s in steps if s["type"] == "hole")
    check("get_model: the hole's shape, standard, thread and lock", h.get("shape") == "counterbore" and h.get("standard") == "M5" and h.get("thread") and h.get("lock") == [{"x": True, "y": True}] * 2, {k: h.get(k) for k in ("shape", "standard", "thread", "lock")})
    ai("edit_feature", id=h["id"], fields={"lock": [{"x": True}, None]})
    h = next(s for s in json.loads(ai("get_model"))["steps"] if s["type"] == "hole")
    check("edit_feature lock per position", h.get("lock") == [{"x": True}, None], h.get("lock"))
    check("the GUI's drag reads the same lock", js("const f = window.__app.modeler.part.features.find(x => x.type === 'hole'); return JSON.stringify(f.lock)") == '[{"x":true},null]')
    ai("edit_feature", id=h["id"], fields={"lock": False})
    h = next(s for s in json.loads(ai("get_model"))["steps"] if s["type"] == "hole")
    check("edit_feature lock false: none", "lock" not in h, h.get("lock"))
    r = ai("edit_feature", id=h["id"], fields={"lock": "yes"})
    check("a wrong lock refused", r.startswith("ERROR") and "lock" in r, r[:120])
    edge = json.loads(ai("find_refs", kind="edge", of_face="F2:end", limit=8))
    e = next((x for x in (edge if isinstance(edge, list) else edge.get("edges", [])) if x.get("ref")), None)
    if e:
        ai("edit_feature", id=h["id"], fields={"from": [{"x": {"edge": e["ref"], "d": 12}}, None]})
        h = next(s for s in json.loads(ai("get_model"))["steps"] if s["type"] == "hole")
        check("get_model: a hole's distance (from)", (h.get("from") or [{}])[0].get("x", {}).get("from") == "edge", h.get("from"))

    # ---------------------------------------------------------------- a sheet: a size moved to another view
    s = json.loads(ai("sheet_open"))
    moved = None
    for dm in s["dims"]:
        if dm["kind"] != "linear":
            continue
        for v in ("Front", "Top", "Right"):
            if v == dm["view"]:
                continue
            r = ai("sheet_edit", move={dm["id"]: {"view": v}})
            if not r.startswith("ERROR"):
                moved = (dm, v, json.loads(r))
                break
        if moved:
            break
    check("sheet_edit move {view}: a linear size in another view", moved is not None, [(x["id"], x["view"], x["text"]) for x in s["dims"]][:8])
    if moved:
        dm, v, r = moved
        check("…in that view, the same text, the old id gone", any(x["view"] == v and x["text"] == dm["text"] for x in r["dims"]) and not any(x["id"] == dm["id"] for x in r["dims"]), r["done"])
    lin = next(x for x in json.loads(ai("get_sheet"))["dims"] if x["kind"] == "linear")
    r = ai("sheet_edit", move={lin["id"]: {"view": "Nowhere"}})
    check("a view it cannot go in refused", r.startswith("ERROR") and "cannot go in" in r, r[:160])

    # ---------------------------------------------------------------- the crank: ⇤ min / max ⇥ here, 🔗 joints shown
    r = ai("open_demo", name="crank")
    wait(f"return window.__app.state.workspace === 'assembly' && {A}.doc.instances.length > 2", 90)
    time.sleep(1.5)
    ga = json.loads(ai("get_assembly"))
    mech = ga["mechanisms"][0]
    drv = mech["driver"]
    part, motion = (drv["part"], drv.get("motion", 0)) if isinstance(drv, dict) else (str(drv).split()[0], 0)
    ai("move_free", part=part, motion=motion, to=30)
    r = ai("set_travel", part=part, motion=motion, min="here")
    check("set_travel min \"here\": the min where it is (30)", "limits 30" in r, r[:160])
    ai("move_free", part=part, motion=motion, to=100)
    r = ai("set_travel", part=part, motion=motion, max="here")
    check("set_travel max \"here\": 30 … 100", "limits 30 … 100" in r, r[:160])
    r = ai("set_travel", part=part, motion=motion, min="here", max="here")
    check("both \"here\" refused", r.startswith("ERROR"), r[:100])
    r = ai("set_travel", part=part, motion=motion, min="soon")
    check("a word that is not \"here\" refused", r.startswith("ERROR"), r[:100])
    r = ai("set_view", joints=False)
    off = js("return JSON.parse(localStorage.getItem('a3d.show3d') || '{}').joints === false && !document.querySelector('.snap-filters [data-show=joints]')?.classList.contains('on')")
    check("set_view joints false: the bottom row's 🔗 off", off and "hidden" in r, r[:120])
    r = ai("set_view", joints=True)
    check("set_view joints true: on again", "shown" in r and js("return !!document.querySelector('.snap-filters [data-show=joints]')?.classList.contains('on')"), r[:120])

    # ---------------------------------------------------------------- set_layout
    r = tail_json(ai("set_layout"))
    names = [w["widget"] for w in r.get("widgets", [])]
    check("set_layout {}: the widgets of the assembly", {"project", "panel", "suggest", "props"} <= set(names), names)
    r = tail_json(ai("set_layout", widget="suggestions", place="right", at=1))
    sg = next(w for w in r["widgets"] if w["widget"] == "suggest")
    check("the suggestions docked right", sg["where"] == "right", sg)
    r = tail_json(ai("set_layout", widget="panel", fold=True, auto_height=True))
    p = next(w for w in r["widgets"] if w["widget"] == "panel")
    check("the panel folded, automatic height", p.get("folded") and p.get("auto_height"), p)
    r = tail_json(ai("set_layout", widget="panel", fold=False, rows=3))
    p = next(w for w in r["widgets"] if w["widget"] == "panel")
    check("the parts list: 3 rows", p.get("rows") == 3 and not p.get("folded"), p)
    r = tail_json(ai("set_layout", suggestions={"closed": True, "auto": False}))
    check("the suggestions closed, not by themselves", r["suggestions"] == {"closed": True, "auto": False}, r["suggestions"])
    r = tail_json(ai("set_layout", suggestions={"auto": True}))
    check("automatic again opens them", r["suggestions"] == {"closed": False, "auto": True}, r["suggestions"])
    r = ai("set_layout", widget="nonsense", fold=True)
    check("a widget that is not there refused, listing them", r.startswith("ERROR") and "suggest" in r, r[:140])
    r = tail_json(ai("set_layout", reset=True))
    sg = next(w for w in r["widgets"] if w["widget"] == "suggest")
    check("reset: the suggestions float again, rows all", sg["where"] == "float" and next(w for w in r["widgets"] if w["widget"] == "panel").get("rows") in (None, "all"), sg)

    # ---------------------------------------------------------------- a harness: points put in / moved / reordered / taken out
    ids = [p["id"] for p in ga["parts"]]
    pts = [{"part": ids[0], "point": [0, 0, 0]}, {"xyz": [0, 0, 80]}, {"xyz": [60, 0, 80]}, {"part": ids[1], "point": [0, 0, 0]}]
    r = ai("add_harness", type="cable", d=4, points=pts)
    hid = tail_json(r).get("id", "H1")
    ai("edit_harness", id=hid, spans=[{"from": 2, "length": 120}])
    r = tail_json(ai("edit_harness", id=hid, insert_points={"after": 1, "points": [{"xyz": [0, 30, 60]}]}))
    pl = r.get("point_list", [])
    check("insert_points after 1: 5 points, the new one second", len(pl) == 5 and [round(v) for v in pl[1]["xyz"]] == [0, 30, 60], [p.get("xyz") for p in pl])
    check("the span's own length moved with its points (from 3)", any(s.get("from") == 3 for s in r.get("spans", [])), r.get("spans"))
    r = tail_json(ai("edit_harness", id=hid, set_points=[{"n": 2, "xyz": [0, 40, 60]}]))
    check("set_points n 2: moved", [round(v) for v in r["point_list"][1]["xyz"]] == [0, 40, 60], r["point_list"][1])
    r = tail_json(ai("edit_harness", id=hid, order=[1, 3, 2, 4, 5]))
    check("order: 2 and 3 swapped", [round(v) for v in r["point_list"][2]["xyz"]] == [0, 40, 60] and [round(v) for v in r["point_list"][1]["xyz"]] == [0, 0, 80], [p["xyz"] for p in r["point_list"]])
    check("…the span whose points are no longer neighbours: gone", not any(s.get("from") == 3 for s in r.get("spans", [])), r.get("spans"))
    r = tail_json(ai("edit_harness", id=hid, remove_points=[3]))
    check("remove_points 3: 4 points", len(r["point_list"]) == 4, len(r["point_list"]))
    r = ai("edit_harness", id=hid, remove_points=[9])
    check("a wrong point number refused, nothing changed", r.startswith("ERROR") and js(f"return {A}.doc.harnesses[0].points.length") == 4, r[:120])
    r = ai("edit_harness", id=hid, order=[1, 1, 2, 3])
    check("an order with a point twice refused", r.startswith("ERROR"), r[:120])

    # ---------------------------------------------------------------- the library: clips, chains; edit_chain
    r = ai("library_search", query="P-clamp")
    check("library_search P-clamp: HellermannTyton clips", "H3P" in r or "P-clamp" in r or "hp-" in r.lower(), r[:160])
    r = ai("library_search", query="e-chain")
    check("library_search e-chain: igus chains", "igus" in r.lower(), r[:160])
    r = ai("library_add", item="igus-14", size="Bi 25", length=48, to="assembly")
    wait(f"return !!{A}.doc.chains?.length", 60)
    cid = js(f"return {A}.doc.chains[0].id")
    r = ai("edit_chain", id=cid, links=60, travel=100, name="Osa X")
    s = tail_json(r)
    check("edit_chain links 60, travel 100, name", s.get("links") == 60 and abs(s.get("travel_mm", 0) - 100) < 0.01 and s.get("name") == "Osa X", r[:200])
    r = ai("edit_chain", id=cid, travel=99999)
    reach = js(f"const c = {A}.doc.chains[0]; return c.links * c.dims.pitch - Math.PI * c.dims.R")
    check("a travel past its reach held at its end", not r.startswith("ERROR") and abs(tail_json(r)["travel_mm"] - reach) < 0.01 and tail_json(r).get("reach_ok") is not False, r[:200])
    r = ai("edit_chain", id=cid, moves_with=ids[1])
    check("edit_chain moves_with a part", tail_json(r).get("moves_with") == ids[1], r[:200])
    r = ai("edit_chain", id=cid, travel=10)
    check("travel while moving with a part refused", r.startswith("ERROR") and "moves with" in r, r[:140])
    r = ai("edit_chain", id=cid, moves_with=None)
    check("moves_with null: its own travel again", "moves_with" not in tail_json(r), r[:160])
    r = ai("edit_chain", id="C99")
    check("a chain that is not there refused", r.startswith("ERROR"), r[:100])
    r = ai("edit_chain", id=cid, remove=True)
    check("edit_chain remove: a plain part", not js(f"return !!{A}.doc.chains?.length"), r[:120])

    # ---------------------------------------------------------------- new_project
    r = ai("new_project")
    check("new_project answers before the page starts again", "kept" in r, r[:160])
    time.sleep(1.0)
    wait("return !!window.__app && !window.__app.project?.parts?.length", 60)
    time.sleep(2.5)  # (the fresh page polls again)
    lp = ai("list_parts")
    check("the new page: an empty project, the tools still reach it", not lp.startswith("ERROR") and "Lock plate" not in lp and "Crank" not in lp and "Klika" not in lp, lp[:120])
    r = ai("new_project")
    check("new_project on an empty project: nothing to do", "empty already" in r, r[:120])

    logs = [x for x in d.get_log("browser") if x["level"] == "SEVERE" and "favicon" not in x["message"]]
    check("no console errors", not logs, [x["message"][:160] for x in logs][:3])
except Exception as e:  # (a step that never came: a failure too)
    fails.append(f"stopped: {type(e).__name__} {str(e)[:200]}")
    raise
finally:
    d.save_screenshot(f"{OUT}/ai_features.png")
    d.quit()
    print("\nALL OK" if not fails else f"\nFAILED ({len(fails)}): {fails}")
    sys.exit(1 if fails else 0)
