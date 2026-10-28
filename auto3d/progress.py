"""Progress and cancelling for long operations (importing / slicing a 3D file, rebuilding a part).

The page sends an id with a slow request (`rid`), polls GET /api/progress/<rid> while it waits and may
cancel it (POST /api/progress/<rid>/cancel). Deep inside the work, `report()` updates what the page shows
and `check()` raises `Cancelled` once the user cancelled — both are no-ops outside such a request.
"""
from __future__ import annotations

import threading
import time
from contextlib import contextmanager


class Cancelled(Exception):
    pass


_ops: dict[str, dict] = {}
_lock = threading.Lock()
_local = threading.local()


def begin_request(what: str | None = None, req: str | None = None):
    """A request thread starts: what it works on (a part's name, for the jobs list) and the page's id of the request."""
    _local.what, _local.req = what, req


def name(what: str | None):
    """What this request works on, once known (an uploaded file's name)."""
    _local.what = what


def what() -> str | None:
    return getattr(_local, "what", None)


def req() -> str | None:
    return getattr(_local, "req", None)


def rid() -> str | None:
    return getattr(_local, "rid", None)


@contextmanager
def operation(rid: str | None, kind: str = "Working"):
    """Run the body as the operation `rid` (in this thread); kind: what it is, in plain words (the jobs list)."""
    if not rid:
        yield
        return
    with _lock:
        _ops[rid] = {"stage": "Starting…", "done": 0, "total": 0, "cancel": _ops.get(rid, {}).get("cancel", False),
                     "started": time.time(), "finished": False, "live": True, "kind": kind, "what": what(), "req": req()}
        for k in [k for k, v in _ops.items() if v.get("finished") and time.time() - v["started"] > 300]:
            del _ops[k]
    _local.rid = rid
    try:
        yield
    finally:
        _local.rid = None
        with _lock:
            if rid in _ops:
                _ops[rid]["finished"] = True


def report(stage: str, done: int = 0, total: int = 0):
    rid = getattr(_local, "rid", None)
    if rid:
        with _lock:
            op = _ops.get(rid)
            if op:
                op.update(stage=stage, done=done, total=total)
    check()


def check():
    rid = getattr(_local, "rid", None)
    if rid and _ops.get(rid, {}).get("cancel"):
        raise Cancelled()


def status(rid: str) -> dict:
    with _lock:
        op = dict(_ops.get(rid) or {"stage": "", "done": 0, "total": 0, "finished": False})
    for k in ("started", "live", "kind", "what", "req"):
        op.pop(k, None)
    return op


def cancel(rid: str):
    with _lock:
        # a cancel can arrive before the work registered itself: remember it
        _ops.setdefault(rid, {"stage": "", "done": 0, "total": 0, "started": time.time(), "finished": False})["cancel"] = True


def running() -> list[tuple[str, dict]]:
    """The operations under way: [(rid, {stage, done, total, started, kind, what, req, cancel})]."""
    with _lock:
        return [(r, dict(op)) for r, op in _ops.items() if op.get("live") and not op.get("finished")]
