"""The CAD kernel runs in its own processes: a crash or a hang in OpenCASCADE cannot take the app down, Cancel can
stop it, and its caches (doc._cache, the meshes, the sheets' views, the files read) live as long as the process.

A pool of such processes ("auto3d-kernel-1" …), so one long job (a big STEP import, a drawing set, a print split)
does not hold up the rest: N = A3D_WORKERS, else min(4, cores − 1), one more only with 2 GB of free memory each.
The server's request threads call `WORKER.run(op, arg)`:
- the jobs of one part (a model part, an assembly, a print split's file — `part_key`) go to the same process, one
  after another in the order they came, so its caches stay valid;
- other parts' jobs run on other processes at the same time; a new part / an import goes to the least busy one;
- a crash restarts only that process (the jobs waiting for it fail with a clear error), a timeout or Cancel kills
  only that one, and one whose memory grew past A3D_WORKER_MB (3 GB) is restarted between jobs.
A3D_WORKERS=1: one process for everything, as before.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import multiprocessing as mp
import os
import threading
import time
from collections import Counter, OrderedDict, deque
from contextlib import contextmanager

from .. import progress

GB = 1 << 30
MEMORY_LIMIT = float(os.environ.get("A3D_WORKER_MB") or 3072) * (1 << 20)  # a process bigger than this is restarted
_seq = itertools.count(1)  # every job's sequence number (its reply carries it back)


class KernelUnavailable(RuntimeError):
    pass


class KernelFailed(RuntimeError):
    pass


def _main(conn):
    # OpenCASCADE writes statistics to the console (STEP export): keep the server log readable
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, 1)
    except OSError:
        pass
    from . import doc, packed, printsplit
    from .kernel import KernelError
    ops = {"rebuild": doc.rebuild, "rebuild_bin": lambda a: packed.pack(doc.rebuild(a, True)),  # (the browser's: packed.py)
           "export": lambda a: doc.export(a["part"], a["fmt"], a.get("name") or "part"),
           "assembly_step": lambda a: doc.assembly_step(a.get("instances"), a.get("tree"), a.get("name") or "assembly", a.get("fmt") or "step"),
           "assembly_clashes": lambda a: doc.assembly_clashes(a["instances"], bool(a.get("quick"))),
           "assembly_sweep": lambda a: doc.assembly_sweep(a["instances"], a["steps"]),
           "sheet": lambda a: doc.sheet(a["part"], a.get("preset") or "medium", a.get("paper"), a.get("per_view"), bool(a.get("section"))),
           "assembly_sheet": lambda a: doc.assembly_sheet(a["instances"], a.get("paper"), a.get("explode") or 0),
           "limits": lambda a: doc.limits(a["features"], a["id"]), "import_solid": doc.import_solid,
           "import_assembly": doc.import_assembly, "print_pieces": printsplit.pieces}
    while True:
        try:
            op, arg, seq = conn.recv()
        except (EOFError, OSError):
            return
        try:
            conn.send(("ok", ops[op](arg), seq))
        except KernelError as e:
            conn.send(("error", str(e), seq))
        except Exception as e:  # noqa: BLE001 — anything else is a kernel bug: report, keep serving
            conn.send(("error", f"The CAD kernel failed ({type(e).__name__}: {e}).", seq))


# ------------------------------------------------------------------ memory (psutil when installed, else Windows' own)
def _free_memory():
    """Bytes of memory free for new processes, or None (not known here)."""
    try:
        import psutil
        return psutil.virtual_memory().available
    except ImportError:
        pass
    if os.name == "nt":
        import ctypes

        class Status(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        s = Status()
        s.dwLength = ctypes.sizeof(Status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s)):
            return s.ullAvailPhys
    return None


def rss(pid):
    """The resident memory of process pid in bytes, or None (not known here)."""
    try:
        import psutil
        try:
            return psutil.Process(pid).memory_info().rss
        except psutil.Error:
            return None
    except ImportError:
        pass
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage",
                                              "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
        k32 = ctypes.windll.kernel32
        k32.OpenProcess.restype = wintypes.HANDLE
        h = k32.OpenProcess(0x1000 | 0x0010, False, pid)  # (query limited information, read memory)
        if not h:
            return None
        try:
            c = Counters()
            c.cb = ctypes.sizeof(Counters)
            return c.WorkingSetSize if k32.K32GetProcessMemoryInfo(h, ctypes.byref(c), c.cb) else None
        finally:
            k32.CloseHandle(wintypes.HANDLE(h))
    return None


def pool_size():
    """How many kernel processes: A3D_WORKERS, else min(4, cores − 1) — one more only while 2 GB of memory is free
    for it (the first one always)."""
    env = (os.environ.get("A3D_WORKERS") or "").strip()
    if env:
        try:
            return max(1, int(env))
        except ValueError:
            pass
    n = max(1, min(4, (os.cpu_count() or 1) - 1))
    free = _free_memory()
    if free is not None:
        n = max(1, min(n, 1 + int(free // (2 * GB))))
    return n


# ------------------------------------------------------------------ one kernel process
class Worker:
    """One kernel process and its pipe; its jobs run one at a time, in the order they came."""

    def __init__(self, index=1):
        self.index = index
        self.proc = None
        self.conn = None
        self.cv = threading.Condition()  # guards everything below and the pipe's turn
        self.waiting = deque()  # the jobs' sequence numbers, the first one running
        self.keys = Counter()  # part key -> its jobs waiting or running here
        self.crashes = 0  # times it died mid-job (jobs that waited for it fail)
        self.restarts = 0  # times its process was started
        self.since = None  # when the running job got its turn

    def busy(self):
        with self.cv:
            return len(self.waiting)

    def held_up(self, key):
        """Busy for over Pool.MOVE_AFTER s with other parts' jobs, none of key's waiting here."""
        with self.cv:
            return bool(self.waiting) and not self.keys.get(key) and time.time() - (self.since or time.time()) > Pool.MOVE_AFTER

    def _start(self):
        from . import available
        if not available("occ"):
            raise KernelUnavailable("The 3D model workspace needs its CAD kernel: py -m pip install -r requirements-modeler.txt")
        ctx = mp.get_context("spawn")
        self.conn, child = ctx.Pipe()
        self.proc = ctx.Process(target=_main, args=(child,), daemon=True, name=f"auto3d-kernel-{self.index}")
        self.proc.start()
        self.restarts += 1

    def _kill(self):
        if self.proc and self.proc.is_alive():
            self.proc.kill()
            self.proc.join(5)
        self.proc = None

    @contextmanager
    def _turn(self, seq, key):
        """Wait for this job's turn (the jobs before it done); a Cancel while waiting leaves the queue."""
        with self.cv:
            self.waiting.append(seq)
            self.keys[key] += 1
            crashes = self.crashes
            try:
                if self.waiting[0] != seq:
                    progress.report("Waiting for the CAD kernel (another job of it is running)")
                while self.waiting[0] != seq:
                    self.cv.wait(0.05)
                    progress.check()
                if self.crashes != crashes:
                    raise KernelFailed("The CAD kernel stopped unexpectedly while building another job — try again.")
            except BaseException:
                self._leave(seq, key)
                raise
            self.since = time.time()
        try:
            yield
        finally:
            with self.cv:
                self._leave(seq, key)

    def _leave(self, seq, key):
        if self.waiting[0] == seq:
            self.since = None
        self.waiting.remove(seq)
        self.keys[key] -= 1
        if self.keys[key] <= 0:
            del self.keys[key]
        self.cv.notify_all()

    def run(self, op, arg, timeout=120, key=None, seq=None):
        """Run op in the kernel process; honours the request's Cancel (progress.Cancelled is raised)."""
        seq = next(_seq) if seq is None else seq
        with self._turn(seq, key):
            return self._run(op, arg, timeout, seq)

    def _run(self, op, arg, timeout, seq):
        progress.report("Building the 3D model")
        if not (self.proc and self.proc.is_alive()):
            self._start()
        try:
            self.conn.send((op, arg, seq))
        except OSError:  # (it died just now: a new one)
            self._kill()
            self._start()
            self.conn.send((op, arg, seq))
        t0 = time.time()
        while True:
            try:
                reply = self.conn.recv() if self.conn.poll(0.05) else None
            except (EOFError, OSError):  # (the pipe closed: the process died)
                reply = None
                self.proc.join(5)
            if reply:
                kind, val, got = reply
                if got != seq:  # (an answer to an earlier job: not this one's)
                    continue
                self._trim()
                if kind == "ok":
                    return val
                raise KernelFailed(val)
            if not self.proc.is_alive():
                self.proc = None
                with self.cv:
                    self.crashes += 1
                raise KernelFailed("The CAD kernel stopped unexpectedly while building — it restarts with the next change.")
            try:
                progress.check()
            except progress.Cancelled:
                self._kill()  # the only way to stop OpenCASCADE mid-operation; it restarts on the next call
                raise
            if time.time() - t0 > timeout:
                self._kill()
                raise KernelFailed(f"Building took longer than {timeout} s and was stopped.")

    def _trim(self):
        """A process grown past MEMORY_LIMIT (a big board's caches) is restarted: the next job starts a fresh one."""
        size = rss(self.proc.pid) if self.proc else None
        if size is not None and size > MEMORY_LIMIT:
            self._kill()

    def close(self):
        self._kill()


# ------------------------------------------------------------------ the pool
def _digest(x):
    return hashlib.sha1(json.dumps(x, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _of_part(part):
    """A part's key: its first step (the base sketch; an imported file: the file) — what all its kept steps start
    with, so its jobs meet its caches wherever they come from (its tab, an assembly, its sheet, the AI), and a part
    being edited stays on its process; a change of the first step builds everything anew anyway. Parts whose first
    step is the same share a process."""
    fs = (part or {}).get("features") or []
    f = fs[0] if fs else {}
    return f"blob:{f['blob']}" if f.get("type") == "solid" and f.get("blob") else f"part:{_digest(f)}"


def part_key(op, arg):
    """Which part a job is about (its jobs go to one process), or None: any process (a new file, an export of many)."""
    arg = arg or {}
    if op in ("rebuild", "rebuild_bin"):
        return _of_part(arg)
    if op in ("export", "sheet"):
        return _of_part(arg.get("part"))
    if op == "limits":
        return _of_part({"features": arg.get("features")})
    if op in ("assembly_clashes", "assembly_sweep", "assembly_sheet"):
        return "asm:" + _digest(sorted(str(i.get("id")) for i in arg.get("instances") or []))
    if op == "import_solid":
        return f"blob:{arg.get('blob')}"  # (its part's steps read the file this one keeps)
    if op == "print_pieces":
        return f"print:{arg.get('file')}"
    return None


class Pool:
    """The kernel processes and which part goes to which."""

    MOVE_AFTER = 1.0  # s: a part whose process has been busy this long with other parts' jobs moves to an idle one

    def __init__(self, n=None):
        self.n = n or pool_size()
        self.workers = [Worker(i + 1) for i in range(self.n)]
        self.lock = threading.Lock()  # the routing table
        self.route = OrderedDict()  # part key -> its worker (the last 512 parts)

    def worker_for(self, op, arg, key=...):
        """The process the job goes to (and its part's from now on)."""
        if key is ...:
            key = part_key(op, arg)
        with self.lock:
            if self.n == 1:
                return self.workers[0]
            w = self.route.get(key) if key is not None else None
            if w is not None:
                self.route.move_to_end(key)
                # its process is held up by other parts' long jobs and another is idle: the part moves (once its
                # own jobs there are done, so they stay in order) — its caches are built again there
                if w.held_up(key):
                    idle = [x for x in self.workers if not x.busy()]
                    if idle:
                        w = idle[0]
                        self.route[key] = w
                return w
            mine = Counter(id(x) for x in self.route.values())
            w = min(self.workers, key=lambda x: (x.busy(), mine[id(x)], x.index))
            if key is not None:
                self.route[key] = w
                while len(self.route) > 512:
                    self.route.popitem(last=False)
            return w

    def run(self, op, arg, timeout=120, key=...):
        """Run op in the part's kernel process (see the module's docstring); the same errors as Worker.run."""
        key = part_key(op, arg) if key is ... else key
        return self.worker_for(op, arg, key).run(op, arg, timeout, key)

    def close(self):
        for w in self.workers:
            w.close()


WORKER = Pool()
