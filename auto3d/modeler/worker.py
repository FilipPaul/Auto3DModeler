"""The CAD kernel runs in its own process: a crash or a hang in OpenCASCADE cannot take the app down,
Cancel can stop it, and its shape cache (doc._cache) lives as long as the process.

The server calls `run("rebuild", part)` from a request thread; calls are handled one at a time.
"""
from __future__ import annotations

import multiprocessing as mp
import os
import threading
import time

from .. import progress


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
    from . import doc, packed
    from .kernel import KernelError
    ops = {"rebuild": doc.rebuild, "rebuild_bin": lambda a: packed.pack(doc.rebuild(a, True)),  # (the browser's: packed.py)
           "export": lambda a: doc.export(a["part"], a["fmt"], a.get("name") or "part"),
           "assembly_step": lambda a: doc.assembly_step(a.get("instances"), a.get("tree"), a.get("name") or "assembly"),
           "assembly_clashes": lambda a: doc.assembly_clashes(a["instances"], bool(a.get("quick"))),
           "assembly_sweep": lambda a: doc.assembly_sweep(a["instances"], a["steps"]),
           "sheet": lambda a: doc.sheet(a["part"], a.get("preset") or "medium", a.get("paper"), a.get("per_view"), bool(a.get("section"))),
           "assembly_sheet": lambda a: doc.assembly_sheet(a["instances"], a.get("paper"), a.get("explode") or 0),
           "limits": lambda a: doc.limits(a["features"], a["id"]), "import_solid": doc.import_solid,
           "import_assembly": doc.import_assembly}
    while True:
        try:
            op, arg = conn.recv()
        except (EOFError, OSError):
            return
        try:
            conn.send(("ok", ops[op](arg)))
        except KernelError as e:
            conn.send(("error", str(e)))
        except Exception as e:  # noqa: BLE001 — anything else is a kernel bug: report, keep serving
            conn.send(("error", f"The CAD kernel failed ({type(e).__name__}: {e})."))


class Worker:
    def __init__(self):
        self.proc = None
        self.conn = None
        self.lock = threading.Lock()

    def _start(self):
        from . import available
        if not available("occ"):
            raise KernelUnavailable("The 3D model workspace needs its CAD kernel: py -m pip install -r requirements-modeler.txt")
        ctx = mp.get_context("spawn")
        self.conn, child = ctx.Pipe()
        self.proc = ctx.Process(target=_main, args=(child,), daemon=True, name="auto3d-kernel")
        self.proc.start()

    def _kill(self):
        if self.proc and self.proc.is_alive():
            self.proc.kill()
        self.proc = None

    def run(self, op, arg, timeout=120):
        """Run op in the kernel process; honours the request's Cancel (progress.Cancelled is raised)."""
        with self.lock:
            if not (self.proc and self.proc.is_alive()):
                self._start()
            self.conn.send((op, arg))
            t0 = time.time()
            progress.report("Building the 3D model")
            while True:
                if self.conn.poll(0.05):
                    kind, val = self.conn.recv()
                    if kind == "ok":
                        return val
                    raise KernelFailed(val)
                if not self.proc.is_alive():
                    self.proc = None
                    raise KernelFailed("The CAD kernel stopped unexpectedly while building — it restarts with the next change.")
                try:
                    progress.check()
                except progress.Cancelled:
                    self._kill()  # the only way to stop OpenCASCADE mid-operation; it restarts on the next call
                    raise
                if time.time() - t0 > timeout:
                    self._kill()
                    raise KernelFailed(f"Building took longer than {timeout} s and was stopped.")

    def close(self):
        self._kill()


WORKER = Worker()
