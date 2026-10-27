"""＋ Dimension by edges on a drawing sheet, in headless Edge with real clicks: a plate 40 × 20 × 10 with a Ø6 hole ->
＋ Dimension -> the mouse over the front's top edge: it lights up -> clicked twice: its length (40) -> the front's left and
right edges: the distance between them (40, across) -> the top's lower edge and the hole's centre: the distance (up) ->
an edge and Enter: its length -> an edge and a crossing edge: refused (not parallel).

  PYTHONIOENCODING=utf-8 py tools/e2e_sheet_edges.py http://127.0.0.1:5199 <out dir>
"""
import json
import sys
import time
import urllib.request

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

URL, OUT = sys.argv[1], sys.argv[2]
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
js = d.execute_script
S = "window.__app.sheet"


def ai(tool, **args):
    req = urllib.request.Request(f"{URL}/api/agent/call", data=json.dumps({"tool": tool, "args": args}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        res = json.loads(r.read())
    return ("ERROR " if res.get("isError") else "") + "".join(c.get("text", "") for c in res.get("content", []))


def edge(view, test):
    """The paper point 30 % along an edge of a view that passes `test` (a JS expression of ln)."""
    return js(f"""const g = {S}.geo.views['{view}'], ln = g.lines.find(ln => {test});
      const a = {S}.P('{view}', ln.a), b = {S}.P('{view}', ln.b); return [a[0] + (b[0] - a[0]) * 0.3, a[1] + (b[1] - a[1]) * 0.3]""")


def at(pt):
    x, y = js(f"""const s = {S}.svgEl, p = s.createSVGPoint(); p.x = arguments[0][0]; p.y = arguments[0][1];
      const q = p.matrixTransform(s.getScreenCTM()), r = {S}.stage.getBoundingClientRect();
      return [Math.round(q.x - (r.left + r.width / 2)), Math.round(q.y - (r.top + r.height / 2))]""", pt)
    return ActionChains(d).move_to_element_with_offset(d.find_element(By.CSS_SELECTOR, "#shViewport .sh-stage"), x, y)


def click(pt):
    at(pt).click().perform()
    time.sleep(0.4)


def last():
    return js(f"const u = {S}.d.user[{S}.d.user.length - 1]; return u ? [u.kind, u.dir, {S}.value(u)] : null")


try:
    d.get(URL)
    time.sleep(2)
    ai("new_model", name="Plate")
    ai("add_feature", type="sketch", plane="XY", shapes=[{"rect": {"x": 0, "y": 0, "w": 40, "h": 20}}])
    ai("add_feature", type="extrude", sketch="F1", d=10)
    ai("add_feature", type="hole", face="F2:end", points=[[5, 0]], d=6)
    ai("sheet_open")
    time.sleep(0.8)
    d.find_element(By.CSS_SELECTOR, "#shViewport [data-a=dim]").click()
    time.sleep(0.3)
    top_edge = edge("Front", "Math.abs(ln.a[1] - 10) < 1e-6 && Math.abs(ln.b[1] - 10) < 1e-6")
    at(top_edge).perform()
    time.sleep(0.4)
    print("over the front's top edge: lit", js(f"return !!{S}.hoverEdge"))
    click(top_edge)
    print("  clicked: picked an edge", js(f"return !!{S}.pick?.edge"), "| hint:", d.find_element(By.CSS_SELECTOR, "#shViewport .sh-hint").text[:40])
    click(top_edge)
    print("  again: its length", last())
    click(edge("Front", "Math.abs(ln.a[0]) < 1e-6 && Math.abs(ln.b[0]) < 1e-6"))
    click(edge("Front", "Math.abs(ln.a[0] - 40) < 1e-6 && Math.abs(ln.b[0] - 40) < 1e-6"))
    print("left and right edges: the distance", last())
    click(edge("Top", "Math.abs(ln.a[1]) < 1e-6 && Math.abs(ln.b[1]) < 1e-6"))
    hole = js(f"return {S}.P('Top', {S}.geo.views.Top.circles.find(c => c.full).c)")
    click(hole)
    print("the top's lower edge and the hole's centre: the distance", last())
    click(edge("Right", "Math.abs(ln.a[1] - 10) < 1e-6 && Math.abs(ln.b[1] - 10) < 1e-6"))
    ActionChains(d).send_keys(Keys.ENTER).perform()
    time.sleep(0.4)
    print("an edge and Enter: its length", last())
    n = len(js(f"return {S}.d.user"))
    click(edge("Front", "Math.abs(ln.a[1] - 10) < 1e-6 && Math.abs(ln.b[1] - 10) < 1e-6"))
    click(edge("Front", "Math.abs(ln.a[0]) < 1e-6 && Math.abs(ln.b[0]) < 1e-6"))
    print("crossing edges: refused", len(js(f"return {S}.d.user")) == n, "|", [t.text for t in d.find_elements(By.CSS_SELECTOR, ".toast")][-1:])
    d.save_screenshot(f"{OUT}/sheet_edges.png")
finally:
    print("console errors:", [e["message"][:200] for e in d.get_log("browser") if e["level"] == "SEVERE"])
    d.quit()
