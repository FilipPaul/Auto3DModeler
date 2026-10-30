"""How long the server's requests and kernel calls take: per endpoint (its route) and per kernel op — count, total,
longest (ms), and the bytes answered. Kept in memory since the start (or the last reset); GET /api/timings shows them
(?reset=1 clears them) — for profiling big projects (tools/e2e_big_assembly.py)."""
from __future__ import annotations

import threading
import time
from contextlib import contextmanager

_LOCK = threading.Lock()
_STATS: dict[str, dict] = {}


def note(key: str, ms: float, size: int = 0) -> None:
    """One more call of `key` that took ms (and answered size bytes)."""
    with _LOCK:
        s = _STATS.setdefault(key, {"n": 0, "ms": 0.0, "max_ms": 0.0, "bytes": 0})
        s["n"] += 1
        s["ms"] += ms
        s["max_ms"] = max(s["max_ms"], ms)
        s["bytes"] += size


@contextmanager
def timed(key: str):
    t0 = time.perf_counter()
    try:
        yield
    finally:
        note(key, (time.perf_counter() - t0) * 1000)


def report(reset: bool = False) -> dict:
    """{key: {n, ms, max_ms, avg_ms, bytes}}, the slowest in all first."""
    with _LOCK:
        out = {k: {**v, "ms": round(v["ms"], 1), "max_ms": round(v["max_ms"], 1), "avg_ms": round(v["ms"] / v["n"], 1)}
               for k, v in sorted(_STATS.items(), key=lambda kv: -kv[1]["ms"])}
        if reset:
            _STATS.clear()
    return out
