"""The AI in the open outline window, without the model (headless Edge + the real MCP server process, as Claude Code
starts it): the user opens a picture, the window's ✨ AI opens the chat beside it, then each wish is a JSON-RPC tool
call like Claude Code makes — outline_window (the candidates + the picture with them drawn in), outline_window_edit:
Object = Thin wall, a 'not this' point, smoothing, a quarter turn, select + combine (＋ / −), the size, Solid shape,
✓ accept -> the part, then outline_window answers that no window is open.

usage (server running, e.g. `py server.py --port 5199 --no-browser`):
  PYTHONIOENCODING=utf-8 py tools/e2e_outline_ai.py http://127.0.0.1:5199 <abs path to pernicek.png> <screenshot dir>
Saves ai_window_chat.png (the chat beside the window), ai_acting.png (the window after the AI's changes),
ai_picture_<n>.png (the pictures the AI got) and ai_part.png. Exits 1 on a failed check or a console error.
"""
import base64
import json
import subprocess
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By

URL, IMG, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
ROOT = Path(__file__).resolve().parent.parent
opts = webdriver.EdgeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.set_capability("ms:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=opts)
mcp = None
fails = []
ids = iter(range(1, 10_000))
shots = iter(range(1, 100))


def check(ok, what):
    print("OK  " if ok else "FAIL", what)
    if not ok:
        fails.append(what)


def wait(js, t=60):
    end = time.time() + t
    while time.time() < end:
        v = d.execute_script(js)
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(js)


def rpc(method, params=None):
    mid = next(ids)
    mcp.stdin.write((json.dumps({"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}}) + "\n").encode())
    mcp.stdin.flush()
    return json.loads(mcp.stdout.readline().decode())["result"]


def tool(name, **args):
    """An MCP tool call -> (text, the picture's PNG bytes or None, is error)."""
    r = rpc("tools/call", {"name": name, "arguments": args})
    text = r["content"][0]["text"]
    img = next((base64.b64decode(c["data"]) for c in r["content"] if c["type"] == "image"), None)
    if img:
        (Path(OUT) / f"ai_picture_{next(shots)}.png").write_bytes(img)
    print(f"· {name} {json.dumps(args)[:100]}\n    {'ERROR ' if r.get('isError') else ''}{text[:220]}{' [+image]' if img else ''}")
    return text, img, bool(r.get("isError"))


def state(text):
    return json.loads(text[text.index("{"):])


W = "window.__app.wizard"

try:
    d.get(URL)
    wait("return !!window.__app")
    d.execute_script("localStorage.removeItem('a3d.outlineWindow')")
    mcp = subprocess.Popen([sys.executable, str(ROOT / "auto3d" / "mcp_server.py"), "--url", URL],
                           stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "e2e", "version": "1"}})
    names = {t["name"] for t in rpc("tools/list")["tools"]}
    check({"outline_window", "outline_window_edit"} <= names, "the MCP server lists outline_window / outline_window_edit")
    time.sleep(1.5)  # (the page polls for calls)

    t, img, err = tool("outline_window")
    check(err and "No outline window is open" in t, "no window open: a clear error")

    # the user opens a picture; ✨ AI in the window opens the chat beside it (docked: not over it)
    d.find_element(By.ID, "imgInput").send_keys(IMG)
    wait("return document.querySelectorAll('.wz-cand').length > 0 && document.querySelector('.wz-busy').hidden")
    d.find_element(By.CSS_SELECTOR, ".wz-ai").click()
    time.sleep(0.6)
    chat = d.execute_script("const r = document.getElementById('aiDrawer').getBoundingClientRect(); return document.getElementById('aiDrawer').hidden ? null : {x: r.left, w: r.width}")
    win = d.execute_script("const r = document.querySelector('.wz-box').getBoundingClientRect(); return {r: r.right}")
    check(chat is not None and win["r"] <= chat["x"] + 1, f"✨ AI in the window: the chat beside it ({win['r']:.0f} <= {chat and chat['x']:.0f})")
    check(d.execute_script("return !!document.querySelector('#aiDrawer textarea')"), "…with its message box")
    ctx = d.execute_script("return window.__chat.context()")
    check("Outline from picture" in ctx and "outline_window" in ctx, f"the chat's message carries what is on screen: {ctx[:70]}…")
    d.save_screenshot(f"{OUT}/ai_window_chat.png")

    # look: the candidates and the picture with them drawn in
    t, img, err = tool("outline_window")
    s = state(t)
    n0 = len(s["candidates"])
    check(not err and img and img[:4] == b"\x89PNG", "outline_window: a PNG picture of the window's outlines")
    pw, ph = int.from_bytes(img[16:20], "big"), int.from_bytes(img[20:24], "big")
    check(max(pw, ph) == 1000, f"…1000 px on its longer side (the small picture enlarged): {pw}x{ph}")
    check(s["selected"] == "#1" and s["candidates"][0]["n"] == "#1" and len(s["candidates"][0]["box"]) == 4,
          f"…{n0} candidates named as listed, #1 selected")
    check(s["object"] == "auto" and s["picture"]["width_px"] > 0, "…the Object mode and the picture's size")

    # "take the thin-wall one": Object = Thin wall (the window's switch shows it)
    t, img, err = tool("outline_window_edit", mode="thin")
    check(not err and state(t)["object"] == "thin", "mode thin")
    check(d.execute_script("return document.querySelector('.wz-kind [data-k=thin]').classList.contains('on')"), "…the Object switch shows Thin wall")
    t, img, err = tool("outline_window_edit", mode="auto")

    # "remove the shadow on the left": a not-this point; smoothing; the window's controls follow
    t, img, err = tool("outline_window_edit", not_this=[[0.03, 0.5]], smoothing=3)
    s = state(t)
    check(s["hints"]["not_this"] == [[0.03, 0.5]] and s["settings"]["smoothing"] == 3, "not_this point + smoothing 3")
    check(d.execute_script("return document.querySelector('[data-h=smoothing]').value") == "3", "…the Smoothing slider shows 3")
    check(d.execute_script("return [...document.querySelectorAll('.wz-chip')].some(c => c.textContent.includes('not this 1'))"), "…the hint chip is listed")

    # "turn it 90°": width <-> height
    w0, h0 = s["picture"]["width_px"], s["picture"]["height_px"]
    t, img, err = tool("outline_window_edit", rotate=90)
    s = state(t)
    check((s["picture"]["width_px"], s["picture"]["height_px"]) == (h0, w0), f"rotate 90: {w0}x{h0} -> {s['picture']['width_px']}x{s['picture']['height_px']}")
    check(s["hints"]["not_this"] == [[0.5, 0.03]], f"…the hint turned with it {s['hints']['not_this']}")
    t, img, err = tool("outline_window_edit", rotate=270)

    # select + combine: #1 ＋ #3 -> the edit, selected
    t, img, err = tool("outline_window_edit", select=1, add=["#3"])
    s = state(t)
    check(s["selected"] == "edit" and s["candidates"][0]["n"] == "edit", "select 1 + add #3 -> the edit, selected")
    check(d.execute_script(f"return !!{W}.edit && {W}.sel === 0"), "…the window shows ✎ Your edit")
    t, img, err = tool("outline_window_edit", cut=[2])
    check(not err, "cut #2 from the edit")
    t, img, err = tool("outline_window_edit", select="#9")
    check(err and "#1" in t, "an unknown candidate: an error naming the ones there are")
    t, img, err = tool("outline_window_edit", inside=[[1.5, 0.2]])
    check(err and "0..1" in t, "a point outside 0..1: refused")
    t, img, err = tool("outline_window_edit", drop_edit=True, select=1)
    check(not err and state(t)["selected"] == "#1" and state(t)["candidates"][0]["n"] == "#1", "drop_edit: back to #1")

    # the size + what to make
    t, img, err = tool("outline_window_edit", width=65, make="solid")
    s = state(t)
    check(s["size_mm"]["width"] == 65 and s["size_mm"]["height"] > 0 and s["make"] == "solid", f"width 65 -> {s['size_mm']}, make solid")
    check(d.execute_script("return document.querySelector('.wz-w').value") == "65", "…the window's width field shows 65")
    d.save_screenshot(f"{OUT}/ai_acting.png")

    # ✓ accept: the window closes, the part is made (its size in the answer)
    t, img, err = tool("outline_window_edit", accept=True)
    check(not err and "Used the outline #1" in t and "Size 65" in t, "accept: the part made, its size in the answer")
    check(d.execute_script("return !document.querySelector('.wizard')"), "…the window is closed")
    sol = d.execute_script("const s = window.__app.state.solution; return {bbox: s.bbox, preset: window.__app.state.model.make?.preset ?? null}")
    check(abs((sol["bbox"][2] - sol["bbox"][0]) - 65) < 0.5, f"…a part 65 mm wide ({sol})")
    t, img, err = tool("outline_window")
    check(err, "after accept: no outline window open")
    time.sleep(0.5)
    d.save_screenshot(f"{OUT}/ai_part.png")
    check(d.execute_script("return !document.body.classList.contains('wz-open')"), "the app back as it was")
finally:
    if mcp:
        mcp.kill()
    errs = [e["message"] for e in d.get_log("browser") if e["level"] == "SEVERE"]
    print("console errors:", errs)
    d.quit()
if fails or errs:
    print("FAILED:", fails)
    sys.exit(1)
print("all OK")
