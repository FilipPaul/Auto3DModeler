"""The desktop start of the app (the built Auto3DModeler.exe, see docs/DISTRIBUTION.md; `py -m auto3d.launcher` from a
checkout does the same): the server on a free port, the app in its own window, one copy running.

* `data_dir()` – where the user's data lives: A3D_DATA, else (the built app) %LOCALAPPDATA%\\Auto3DModeler — never the
  install folder — else the checkout's data/.
* `pick_port()` – --port / A3D_PORT as given, else 5173 when free (the page's local storage stays the same), else any.
* One copy per data folder: a named mutex (Windows) and data/instance.json {url, pid}; a second start only opens the
  window of the running one (`running_url`).
* `open_window()` – Microsoft Edge as an app window (--app, its own profile in data/window: no tabs, no address bar),
  else the default browser. Closing that window quits the app; the tray icon (pystray, when installed) has
  Open / Logs / Quit.
* Logs (the built app has no console): data/logs/auto3d.log, the one before kept as auto3d.1.log.
* `Auto3DModeler.exe --mcp-server --url …` is the AI chat's MCP server (auto3d/mcp_server.py) — there is no Python
  to run it with in the built app.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

APP = "Auto3DModeler"
DEFAULT_PORT = 5173
LOG_KEEP = 5 * 1024 * 1024  # a log bigger than this is moved to auto3d.1.log at the next start
ROOT = Path(__file__).resolve().parent.parent


def frozen() -> bool:
    """True in the built app (PyInstaller)."""
    return bool(getattr(sys, "frozen", False))


# --------------------------------------------------------------------------- where, which port
def data_dir(env=None, is_frozen=None) -> Path:
    """The user's data folder: A3D_DATA, else %LOCALAPPDATA%\\Auto3DModeler in the built app, else <checkout>/data."""
    env = os.environ if env is None else env
    if env.get("A3D_DATA"):
        return Path(env["A3D_DATA"])
    if frozen() if is_frozen is None else is_frozen:
        base = env.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / APP
    return ROOT / "data"


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def pick_port(requested=None, env=None, preferred=DEFAULT_PORT) -> int:
    """--port (requested) or A3D_PORT as given; else `preferred` when free; else one the system hands out."""
    env = os.environ if env is None else env
    for v in (requested, env.get("A3D_PORT")):
        if v not in (None, ""):
            return int(v)
    if port_free(preferred):
        return preferred
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# --------------------------------------------------------------------------- one copy running
def instance_file(data: Path) -> Path:
    return Path(data) / "instance.json"


def app_answers(url: str, timeout: float = 1.5) -> bool:
    """True when our app answers at url (its /api/version)."""
    try:
        with urllib.request.urlopen(f"{url}/api/version", timeout=timeout) as r:
            return "version" in json.loads(r.read().decode())
    except Exception:  # noqa: BLE001 — refused, timed out, another program: not ours
        return False


def running_url(data: Path) -> str | None:
    """The url of the copy already running on this data folder, or None (no file, or it does not answer)."""
    try:
        url = json.loads(instance_file(data).read_text(encoding="utf-8")).get("url")
    except (OSError, ValueError, AttributeError):
        return None
    return url if url and app_answers(url) else None


def write_instance(data: Path, url: str):
    instance_file(data).write_text(json.dumps({"url": url, "pid": os.getpid()}), encoding="utf-8")


def clear_instance(data: Path):
    """Forget instance.json when it is this process's."""
    try:
        if json.loads(instance_file(data).read_text(encoding="utf-8")).get("pid") == os.getpid():
            instance_file(data).unlink()
    except (OSError, ValueError, AttributeError):
        pass


def take_lock(data: Path):
    """A named mutex for this data folder: (handle, True) when this is the first copy, (handle, False) when another
    one holds it. Not Windows: (None, True) — instance.json alone."""
    if os.name != "nt":
        return None, True
    import ctypes
    k32 = ctypes.windll.kernel32
    k32.CreateMutexW.restype = ctypes.c_void_p
    name = f"Local\\{APP}-" + hashlib.sha1(str(Path(data).resolve()).lower().encode()).hexdigest()[:16]
    handle = k32.CreateMutexW(None, False, name)
    return handle, k32.GetLastError() != 183  # ERROR_ALREADY_EXISTS


def wait_for_running(data: Path, seconds: float = 30.0) -> str | None:
    """The other copy may still be starting: its url once it answers, else None."""
    end = time.time() + seconds
    while time.time() < end:
        url = running_url(data)
        if url:
            return url
        time.sleep(0.3)
    return None


# --------------------------------------------------------------------------- the window
def find_edge(env=None) -> str | None:
    """msedge.exe (on every Windows 10 / 11), or None."""
    env = os.environ if env is None else env
    for base in (env.get("ProgramFiles(x86)"), env.get("ProgramFiles"), env.get("LOCALAPPDATA")):
        if base:
            p = Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
            if p.exists():
                return str(p)
    return None


def window_command(edge: str, url: str, data: Path) -> list[str]:
    """Edge as an app window with its own profile (data/window): the app's page alone, no tabs or address bar."""
    return [edge, f"--app={url}", f"--user-data-dir={Path(data) / 'window'}", "--no-first-run",
            "--no-default-browser-check", "--disable-features=msEdgeSidebarV2,msHubApps"]


def open_window(url: str, data: Path, browser: bool = False):
    """Show the app: Edge's app window (returns its process) or, with browser=True / no Edge, the default browser
    (returns None)."""
    edge = None if browser else find_edge()
    if edge:
        try:
            return subprocess.Popen(window_command(edge, url, data), close_fds=True)
        except OSError:
            pass
    webbrowser.open(url)
    return None


# --------------------------------------------------------------------------- logs
def log_path(data: Path) -> Path:
    return Path(data) / "logs" / "auto3d.log"


def open_log(data: Path):
    """data/logs/auto3d.log for appending (the one before moved to auto3d.1.log when it grew past LOG_KEEP)."""
    path = log_path(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if path.stat().st_size > LOG_KEEP:
            os.replace(path, path.with_name("auto3d.1.log"))
    except OSError:
        pass
    return open(path, "a", encoding="utf-8", buffering=1, errors="replace")


# the tray's and the message box's words: Czech on a Czech Windows (the page has its own CZ / EN switch)
CS = {"Open": "Otevřít", "Open in the browser": "Otevřít v prohlížeči", "Logs": "Záznamy (logy)", "Quit": "Ukončit",
      "{app} could not start.\n\nThe details are in {log}.": "{app} se nepodařilo spustit.\n\nPodrobnosti jsou v {log}."}


def czech() -> bool:
    if os.name != "nt":
        return False
    import ctypes
    return ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x05  # (LANG_CZECH)


def say(text: str) -> str:
    return CS.get(text, text) if czech() else text


def message(text: str):
    """A Windows message box (the built app has no console to say it in)."""
    if os.name == "nt":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, APP, 0x10)
    else:
        print(text, file=sys.stderr)


# --------------------------------------------------------------------------- start
class App:
    """The running server (werkzeug in a thread) and how it ends."""

    def __init__(self, data: Path, port: int):
        self.data, self.port = data, port
        self.url = f"http://127.0.0.1:{port}"
        self.done = threading.Event()
        self.httpd = None
        self.window = None  # Edge's app window process
        self.tray = None

    def start(self):
        import server  # (heavy: OpenCV, Flask … — after the second-copy check)
        from werkzeug.serving import make_server
        server.APP_URL = self.url  # the MCP server started by the chat calls back here
        if frozen():  # the log: errors, not a line per request (the page polls all the time)
            import logging
            logging.getLogger("werkzeug").setLevel(logging.WARNING)
        self.httpd = make_server("127.0.0.1", self.port, server.app, threaded=True)
        threading.Thread(target=self.httpd.serve_forever, name="http", daemon=True).start()
        write_instance(self.data, self.url)
        print(f"{APP} running at {self.url} (data: {self.data})", flush=True)

    def show(self, browser=False):
        proc = open_window(self.url, self.data, browser)
        if proc is not None and self.window is None:
            self.window = proc
            threading.Thread(target=self._watch_window, args=(proc,), daemon=True).start()

    def _watch_window(self, proc):
        """Closing the app window quits the app — unless Edge handed the window to a copy of it already open (from
        before: it exits at once) and we cannot tell when that one closes."""
        t0 = time.time()
        proc.wait()
        if time.time() - t0 < 5:
            self.window = None
            return
        print("The app window was closed: quitting.", flush=True)
        self.quit()

    def quit(self):
        self.done.set()
        if self.tray is not None:
            self.tray.stop()

    def run_tray(self) -> bool:
        """The tray icon (Open / Open in the browser / Logs / Quit) until Quit; False when pystray is not there."""
        try:
            import pystray
            from PIL import Image, ImageDraw
        except Exception:  # noqa: BLE001 — optional: then the window's close (or the process's end) quits
            return False
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        g = ImageDraw.Draw(img)
        g.polygon([(32, 4), (60, 18), (32, 32), (4, 18)], fill=(96, 165, 250))
        g.polygon([(4, 18), (32, 32), (32, 60), (4, 46)], fill=(37, 99, 235))
        g.polygon([(60, 18), (32, 32), (32, 60), (60, 46)], fill=(29, 78, 216))
        menu = pystray.Menu(
            pystray.MenuItem(say("Open"), lambda: self.show(), default=True),
            pystray.MenuItem(say("Open in the browser"), lambda: self.show(browser=True)),
            pystray.MenuItem(say("Logs"), lambda: os.startfile(log_path(self.data).parent) if os.name == "nt" else None),
            pystray.MenuItem(say("Quit"), lambda: self.quit()))
        self.tray = pystray.Icon(APP, img, f"{APP} — {self.url}", menu)
        if self.done.is_set():
            return True
        self.tray.run()
        return True

    def stop(self):
        if self.httpd is not None:
            self.httpd.shutdown()
        clear_instance(self.data)
        try:
            import server
            server.stop_chats()  # the chats' Claude Code (one per window that chatted)
            from auto3d.modeler.worker import WORKER
            WORKER.close()
        except Exception:  # noqa: BLE001 — quitting anyway
            pass


def parse(argv):
    ap = argparse.ArgumentParser(prog=APP, description="Start Auto3DModeler and open its window.")
    ap.add_argument("--port", type=int, help="the server's port (default: A3D_PORT, else 5173 when free, else any)")
    ap.add_argument("--no-browser", action="store_true", help="do not open a window (a test server)")
    ap.add_argument("--browser", action="store_true", help="open the default browser instead of an app window")
    ap.add_argument("--no-tray", action="store_true", help="no tray icon")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv[:1] == ["--mcp-server"]:  # the AI chat's MCP server (stdio)
        sys.argv = [sys.argv[0], *argv[1:]]
        from auto3d import mcp_server
        mcp_server.main()
        return 0
    args = parse(argv)
    data = data_dir()
    data.mkdir(parents=True, exist_ok=True)
    os.environ["A3D_DATA"] = str(data)  # server.py and the modules keep the user's data here
    if frozen() or sys.stdout is None:  # no console: the log is where print and errors go
        sys.stdout = sys.stderr = open_log(data)
    _lock, first = take_lock(data)
    # (holding the mutex: no other copy runs on this folder — an old instance.json whose port another program now
    # answers on is not ours; without a mutex (not Windows) instance.json is all there is)
    url = (None if _lock else running_url(data)) if first else wait_for_running(data)
    if url:  # already running: only its window
        print(f"Already running at {url}: opening its window.", flush=True)
        if not args.no_browser:
            open_window(url, data, args.browser)
        return 0
    app = App(data, pick_port(args.port))
    t0 = time.time()
    try:
        app.start()
    except Exception:  # noqa: BLE001 — told in the log and (with a window) a message box, not a hanging error dialog
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        if not args.no_browser:
            message(say("{app} could not start.\n\nThe details are in {log}.").format(app=APP, log=log_path(data)))
        return 1
    print(f"Started in {time.time() - t0:.1f} s.", flush=True)
    if not args.no_browser:
        app.show(args.browser)
    try:
        if args.no_tray or not app.run_tray():
            while not app.done.wait(0.5):
                pass
    except KeyboardInterrupt:
        pass
    finally:
        app.stop()
    print("Stopped.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
