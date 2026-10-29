"""The AI chat's access to Claude, set up at any time while the app runs (the ✨ AI panel's set-up screen).

The chat is Claude Code (auto3d/agent.py); it can reach Claude two ways:
* the user's Claude account — Claude Code's own sign-in (`claude auth login`, a browser page; its credentials stay in
  Claude Code's folder, the app never sees them);
* an Anthropic API key (console.anthropic.com) — kept for this user in <data>/ai/key.bin, encrypted with Windows DPAPI
  (only this Windows user can read it back; elsewhere a file only the user may read), given to the chat's Claude Code
  as ANTHROPIC_API_KEY. It is never logged and only ever sent to Anthropic (the check, the chat).

`state()` -> {"state": "no_claude" | "signed_out" | "invalid" | "ok", "method": "key" | "claude" | None, …}.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API_URL = os.environ.get("A3D_ANTHROPIC_URL") or "https://api.anthropic.com"  # (a test's fake server)
REGISTER_URL = "https://claude.ai"                       # a Claude account (Pro / Max: the chat on the subscription)
CONSOLE_URL = "https://console.anthropic.com/settings/keys"  # API keys
INSTALL_URL = "https://claude.com/claude-code"
INSTALL_CMD = "irm https://claude.ai/install.ps1 | iex"  # Claude Code's own installer (PowerShell, no admin, no Node)
_STATUS_TTL = 5.0  # s: `claude auth status` is asked at most this often

_lock = threading.Lock()
_invalid: set[str] = set()   # keys refused by Anthropic in this run (a hash of each)
_status_cache: dict = {}     # {"t", "claude", "env_key", "out"}
_login: subprocess.Popen | None = None


def data_dir() -> Path:
    return Path(os.environ.get("A3D_DATA") or ROOT / "data")


def key_file(data: Path | None = None) -> Path:
    return (data or data_dir()) / "ai" / "key.bin"


# --------------------------------------------------------------------------- DPAPI (Windows), else user-only file
def _blob(data: bytes):
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]
    buf = ctypes.create_string_buffer(data, len(data))
    return Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf, Blob


def _dpapi(data: bytes, protect: bool) -> bytes:
    import ctypes
    src, _keep, Blob = _blob(data)
    out = Blob()
    fn = ctypes.windll.crypt32.CryptProtectData if protect else ctypes.windll.crypt32.CryptUnprotectData
    ok = fn(ctypes.byref(src), None if not protect else "Auto3DModeler AI key", None, None, None, 0x1, ctypes.byref(out))
    if not ok:
        raise OSError("DPAPI failed")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


def save_key(key: str, data: Path | None = None):
    key = key.strip()
    path = key_file(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = _dpapi(key.encode(), True) if os.name == "nt" else key.encode()
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(raw)
    if os.name != "nt":
        os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def load_key(data: Path | None = None) -> str | None:
    """The stored API key, or None (none stored, or it cannot be read — another Windows user's file)."""
    path = key_file(data)
    try:
        raw = path.read_bytes()
        return (_dpapi(raw, False) if os.name == "nt" else raw).decode()
    except (OSError, UnicodeDecodeError):
        return None


def forget_key(data: Path | None = None):
    key_file(data).unlink(missing_ok=True)


def _h(key: str) -> str:
    import hashlib
    return hashlib.sha256(key.encode()).hexdigest()


def mark_invalid(key: str | None):
    if key:
        _invalid.add(_h(key))


def looks_like_key(key: str) -> bool:
    return bool(re.fullmatch(r"sk-ant-[A-Za-z0-9_\-]{8,}", (key or "").strip()))


def check_key(key: str, timeout: float = 15.0) -> str:
    """Ask Anthropic whether the key works: "ok", "invalid" (refused) or "offline" (could not ask)."""
    if not looks_like_key(key):
        return "invalid"
    req = urllib.request.Request(f"{API_URL}/v1/models?limit=1", headers={"x-api-key": key.strip(), "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=timeout):
            return "ok"
    except urllib.error.HTTPError as exc:
        return "invalid" if exc.code in (401, 403) else "offline"
    except (urllib.error.URLError, OSError):
        return "offline"


AUTH_WORDS = re.compile(r"invalid api key|invalid x-api-key|authentication_error|not logged in|please run /login|"
                        r"oauth token (has )?expired|\b401\b|credit balance is too low", re.I)


def auth_error(text: str | None) -> bool:
    """Whether a chat error is about the access (a bad / expired key, signed out) — then the set-up screen comes back."""
    return bool(text and AUTH_WORDS.search(text))


# --------------------------------------------------------------------------- Claude Code's own sign-in
def _no_window() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def claude_status(exe: str, env: dict | None = None) -> dict:
    """`claude auth status --json` -> its dict ({"loggedIn", "authMethod", "email" …}); {} when it cannot tell."""
    try:
        r = subprocess.run([exe, "auth", "status", "--json"], capture_output=True, text=True, timeout=20,
                           creationflags=_no_window(), env=env)
        return json.loads(r.stdout or "{}")
    except (OSError, subprocess.SubprocessError, ValueError):
        return {}


def start_login(exe: str, console: bool = False) -> None:
    """Claude Code's sign-in (a browser page) in a window of its own; state() follows it. console: the Anthropic
    Console (API billing) instead of a Claude subscription."""
    global _login
    from .agent import clean_env
    flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    _login = subprocess.Popen([exe, "auth", "login", *(["--console"] if console else [])], creationflags=flags, env=clean_env())
    _status_cache.clear()


def logout_claude(exe: str):
    from .agent import clean_env
    subprocess.run([exe, "auth", "logout"], capture_output=True, timeout=30, creationflags=_no_window(), env=clean_env())
    _status_cache.clear()


# --------------------------------------------------------------------------- the state the panel shows
def state(find=None, data: Path | None = None, status=None) -> dict:
    """{"state", "method", "email", "claude", "logging_in", "links"} — what the ✨ AI panel shows:
    no_claude: Claude Code is not installed (install it, then "Check again");
    invalid: the stored key was refused (enter another, or sign in);
    ok: a stored key, or Claude Code signed in (its account or an ANTHROPIC_API_KEY of the user's own);
    signed_out: neither."""
    from .agent import clean_env, find_claude
    exe = (find or find_claude)()
    out = {"claude": exe, "method": None, "email": None, "logging_in": bool(_login and _login.poll() is None),
           "links": {"register": REGISTER_URL, "console": CONSOLE_URL, "install": INSTALL_URL}, "install_cmd": INSTALL_CMD}
    if not exe:
        return {**out, "state": "no_claude"}
    key = load_key(data)
    if key:
        return {**out, "state": "invalid" if _h(key) in _invalid else "ok", "method": "key", "key_end": key[-4:]}
    with _lock:
        c = _status_cache
        if not (c.get("claude") == exe and time.time() - c.get("t", 0) < _STATUS_TTL):
            c.update(t=time.time(), claude=exe, out=(status or claude_status)(exe, clean_env()))
        st = c["out"]
    if st.get("loggedIn"):
        return {**out, "state": "ok", "method": "claude", "email": st.get("email"), "auth": st.get("authMethod")}
    return {**out, "state": "signed_out"}


def chat_env(env: dict, data: Path | None = None) -> dict:
    """The chat's Claude Code environment with the stored key (when there is one)."""
    key = load_key(data)
    return {**env, "ANTHROPIC_API_KEY": key} if key else env


if __name__ == "__main__":  # py -m auto3d.ai_access : what the panel would show
    json.dump(state(), sys.stdout, indent=1)
