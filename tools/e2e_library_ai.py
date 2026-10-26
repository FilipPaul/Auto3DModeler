"""The AI and the parts library, in headless Edge (tool calls through the server's /api/agent/call, as the MCP server
sends them): library_search "608" / "M3 socket" / "inductive M12" -> the items with sizes and part numbers ->
new_assembly, a plate with a Ø22.1 seat (made) -> library_add the 608 bearing into the assembly: placed, its faces ->
snap_faces axis + touch: the bearing in its seat -> get_assembly: the bearing free to turn only, part numbers in the
parts list -> check_collisions: none -> a screw put in its place on purpose -> the overlap reported -> a wrong
size answered with the sizes there are.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_library_ai.py http://127.0.0.1:5199 <out dir>
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


def wait(script, t=60):
    end = time.time() + t
    while time.time() < end:
        v = js(script)
        if v:
            return v
        time.sleep(0.1)
    raise TimeoutError(script)


def ai(tool, **args):
    req = urllib.request.Request(f"{URL}/api/agent/call", data=json.dumps({"tool": tool, "args": args}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        res = json.loads(r.read())
    text = "".join(c.get("text", "") for c in res.get("content", []))
    return ("ERROR " if res.get("isError") else "") + text


def data(tool, **args):
    t = ai(tool, **args)
    try:
        return json.loads(t)
    except ValueError:
        return t


try:
    d.get(URL)
    wait("return !!window.__app")
    time.sleep(1.5)
    for q in ("608", "M3 socket", "inductive M12", "cylinder 16"):
        r = data("library_search", query=q)
        print(f"search {q!r}:", [(x["item"], x["example"]["pn"]) for x in r][:3] if isinstance(r, list) else r[:120])
    print("search nothing:", ai("library_search", query="flux capacitor")[:110])

    ai("new_model", name="Bearing block")
    ai("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": -20, "y": -20, "w": 40, "h": 40}}])
    ai("add_feature", type="extrude", sketch="F1", d=10)
    ai("add_feature", type="hole", face="F2:end", points=[[0, 0]], d=22.1, through=False, depth=7.2)
    ai("new_assembly", name="Bearing test")
    print("insert block:", ai("insert_part", part="Bearing block")[:60])
    r = data("library_add", item="bearing", size="608", to="assembly")
    print("library_add 608:", {k: r[k] for k in ("placed", "name", "pn", "maker")}, "| faces:", [(f["face"], f["type"], f.get("d")) for f in r["faces"]][:6])
    outer = next(f["face"] for f in r["faces"] if f["type"] == "round" and abs(f.get("d", 0) - 22) < 0.01)
    bottom = r["bottom_face"]  # the face it stands on (not a shield's recess above it)
    wait("return window.__app.assembly.doc.instances.length === 2")
    hole = js("const a = window.__app.assembly; return a.bodies[a.inst('I1').part].body.faces.find(f => f.type === 'cylinder').name")
    seat = js("const a = window.__app.assembly; return a.bodies[a.inst('I1').part].body.faces.filter(f => f.type === 'plane' && f.normal[2] > 0.9).sort((p, q) => p.centroid[2] - q.centroid[2])[0].name")
    print("axis:", ai("snap_faces", type="axis", move={"part": r["placed"], "face": outer}, onto={"part": "I1", "face": hole})[:50])
    print("touch:", ai("snap_faces", type="touch", move={"part": r["placed"], "face": bottom}, onto={"part": "I1", "face": seat})[:50])
    asm = data("get_assembly")
    brg = next(p for p in asm["parts"] if p["id"] == r["placed"])
    print("the bearing:", brg.get("free") or brg.get("fully_held"), "| bbox z", brg["bbox"][2], brg["bbox"][5])
    print("parts list:", [(p["name"], p["qty"], p.get("pn"), p.get("maker")) for p in asm["parts_list"]])
    print("collisions:", ai("check_collisions"))
    r2 = data("library_add", item="iso4762", size="M3", length=10, to="assembly")
    print("a screw added:", r2["placed"], r2["pn"])
    ai("place_part", part=r2["placed"], x=0, y=0, z=0)
    c = data("check_collisions")
    print("screw inside the block -> collisions:", [(x["parts"], x["overlap_mm3"]) for x in c] if isinstance(c, list) else c)
    print("a wrong size:", ai("library_add", item="bearing", size="609")[:120])
    print("a wrong length:", ai("library_add", item="iso4762", size="M3", length=11)[:120])
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
