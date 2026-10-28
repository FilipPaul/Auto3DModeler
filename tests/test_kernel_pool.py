"""The pool of kernel processes (auto3d/modeler/worker.py): its size (A3D_WORKERS), a part's jobs on one process in
the order they came, other parts' on others at the same time, a crash / a timeout / too much memory restarting only
that process, and two heavy parts built at once giving what one process gives. The kernel's tests skip without OCP.

Run:  py -m unittest tests.test_kernel_pool -v
"""
import os
import threading
import time
import unittest
from unittest import mock

from auto3d import progress
from auto3d.modeler import available, worker as W

OCC = available("occ")


def sketch(fid, entities):
    return {"id": fid, "type": "sketch", "plane": {"datum": "XY"}, "entities": entities}


def extrude(fid, sk, d, op="add"):
    return {"id": fid, "type": "extrude", "sketch": sk, "op": op, "d": d}


def block(w, name="S1"):
    return {"features": [sketch(name, [{"id": "e1", "t": "rect", "cx": 0, "cy": 0, "w": w, "h": 20}]), extrude("E1", name, 10)]}


def holes(n, d=1.0, name="S1"):
    """A plate with n × n holes in one sketch: seconds of booleans."""
    hs = [{"id": f"h{i}", "t": "circle", "cx": 1 + (i % n) * 2, "cy": 1 + (i // n) * 2, "d": d} for i in range(n * n)]
    return {"features": [sketch(name, [{"id": "e1", "t": "rect", "cx": n, "cy": n, "w": 2 * n + 2, "h": 2 * n + 2}, *hs]), extrude("E1", name, 5)]}


class TestPoolSize(unittest.TestCase):
    def test_size(self):
        """A3D_WORKERS wins (1: one process, as before); else min(4, cores − 1), at least 1, one more per 2 GB free."""
        with mock.patch.dict(os.environ, {"A3D_WORKERS": "1"}):
            self.assertEqual(W.pool_size(), 1)
        with mock.patch.dict(os.environ, {"A3D_WORKERS": "3"}):
            self.assertEqual(W.pool_size(), 3)
        with mock.patch.dict(os.environ, {"A3D_WORKERS": ""}):
            with mock.patch.object(W, "_free_memory", return_value=None), mock.patch.object(os, "cpu_count", return_value=16):
                self.assertEqual(W.pool_size(), 4)
            with mock.patch.object(W, "_free_memory", return_value=None), mock.patch.object(os, "cpu_count", return_value=2):
                self.assertEqual(W.pool_size(), 1)
            with mock.patch.object(W, "_free_memory", return_value=5 * W.GB), mock.patch.object(os, "cpu_count", return_value=16):
                self.assertEqual(W.pool_size(), 3)  # (2 GB free for each of the 2 extra)
            with mock.patch.object(W, "_free_memory", return_value=W.GB):
                self.assertEqual(W.pool_size(), 1)

    def test_part_keys(self):
        """A part's jobs share its key (its first step; an imported file: the file), whatever comes after it."""
        a, b = block(40), block(40)
        b["features"].append(extrude("E2", "S1", 3, "cut"))
        k = W.part_key("rebuild", a)
        self.assertEqual(W.part_key("rebuild_bin", b), k)
        self.assertEqual(W.part_key("sheet", {"part": a}), k)
        self.assertEqual(W.part_key("export", {"part": a, "fmt": "step"}), k)
        self.assertEqual(W.part_key("limits", {"features": a["features"], "id": "E1"}), k)
        self.assertNotEqual(W.part_key("rebuild", block(41)), k)
        deeper = block(40)
        deeper["features"][1]["d"] = 25  # (its extrude dragged: the part stays on its process)
        self.assertEqual(W.part_key("rebuild", deeper), k)
        solid = {"features": [{"id": "I1", "type": "solid", "blob": "abc"}]}
        self.assertEqual(W.part_key("rebuild", solid), W.part_key("import_solid", {"blob": "abc", "name": "x.step"}))
        inst = [{"id": "I1", "part": a, "matrix": [1] * 16}, {"id": "I2", "part": b}]
        self.assertEqual(W.part_key("assembly_clashes", {"instances": inst}), W.part_key("assembly_sweep", {"instances": inst[::-1], "steps": []}))
        self.assertIsNone(W.part_key("import_assembly", {"blob": "abc"}))
        self.assertIsNone(W.part_key("assembly_step", {"tree": {}}))


class Fake(W.Worker):
    """A worker whose jobs only note when they ran (no process)."""

    def __init__(self, index, log):
        super().__init__(index)
        self.log = log

    def _run(self, op, arg, timeout, seq):
        self.log.append(("start", self.index, arg))
        time.sleep(arg.get("t", 0.05))
        self.log.append(("end", self.index, arg))
        return arg


class TestRouting(unittest.TestCase):
    def pool(self, n):
        log = []
        p = W.Pool(n)
        p.workers = [Fake(i + 1, log) for i in range(n)]
        return p, log

    def test_same_part_same_worker_in_order(self):
        """Ten jobs of one part from ten threads: one process, one at a time, in the order they came; another part's
        jobs meanwhile on the other process."""
        p, log = self.pool(2)
        ths = []
        for i in range(10):
            ths.append(threading.Thread(target=p.run, args=("rebuild", {"n": i, "t": 0.03}), kwargs={"key": "A"}))
            ths[-1].start()
            time.sleep(0.005)  # (they come in this order)
        other = threading.Thread(target=p.run, args=("rebuild", {"n": "b", "t": 0.1}), kwargs={"key": "B"})
        other.start()
        for t in ths + [other]:
            t.join(10)
        a = [(e, w, x["n"]) for e, w, x in log if x["n"] != "b"]
        self.assertEqual({w for _, w, _ in a}, {1})
        self.assertEqual([n for e, _, n in a if e == "start"], list(range(10)))
        self.assertTrue(all(a[2 * i][0] == "start" and a[2 * i + 1][0] == "end" for i in range(10)))  # (one at a time)
        b = [w for e, w, x in log if x["n"] == "b"]
        self.assertEqual(b, [2, 2])
        self.assertLess(log.index(("start", 2, {"n": "b", "t": 0.1})), log.index(("end", 1, {"n": 9, "t": 0.03})))  # (at the same time)

    def test_new_parts_spread_and_stateless_jobs_to_the_least_busy(self):
        p, _ = self.pool(3)
        ws = [p.worker_for("rebuild", None, k) for k in "ABC"]
        self.assertEqual(sorted(w.index for w in ws), [1, 2, 3])
        self.assertIs(p.worker_for("rebuild", None, "B"), ws[1])
        ws[0].waiting.extend([101, 102])  # (busy)
        ws[1].waiting.append(103)
        self.assertIs(p.worker_for("import_assembly", None, None), ws[2])
        self.assertIs(p.worker_for("rebuild", None, "A"), ws[0])  # (its jobs only just started: stays)

    def test_a_part_held_up_by_others_moves(self):
        """A part whose process has been busy with another part's long job for over a second (none of its own
        waiting) moves to an idle process."""
        p, _ = self.pool(2)
        a = p.worker_for("rebuild", None, "A")
        a.waiting.append(1)
        a.keys["big"] = 1
        a.since = time.time() - 5
        b = p.worker_for("rebuild", None, "A")
        self.assertIsNot(b, a)
        self.assertIs(p.worker_for("rebuild", None, "A"), b)
        a.keys["A"] = 1  # (one of its own still there: stays, for the order)
        p.route["A"] = a
        self.assertIs(p.worker_for("rebuild", None, "A"), a)

    def test_one_worker_takes_everything(self):
        p, log = self.pool(1)
        for k in ("A", "B", None):
            self.assertIs(p.worker_for("rebuild", None, k), p.workers[0])
        p.run("rebuild", {"n": 1, "t": 0}, key="A")
        self.assertEqual(log[0][1], 1)

    def test_cancel_while_waiting(self):
        """A job cancelled while it waits for its turn leaves the queue (the next one runs), the running one is not
        touched."""
        p, log = self.pool(1)
        out = {}

        def slow():
            out["slow"] = p.run("rebuild", {"n": "slow", "t": 0.5}, key="A")

        def waiting():
            try:
                with progress.operation("pool-wait"):
                    p.run("rebuild", {"n": "w", "t": 0}, key="A")
            except progress.Cancelled:
                out["cancelled"] = True

        t1, t2 = threading.Thread(target=slow), threading.Thread(target=waiting)
        t1.start()
        time.sleep(0.05)
        t2.start()
        time.sleep(0.1)
        progress.cancel("pool-wait")
        t2.join(5)
        self.assertTrue(out.get("cancelled"))
        self.assertEqual(len(p.workers[0].waiting), 1)  # (only the running one)
        t1.join(5)
        self.assertEqual(out["slow"]["n"], "slow")
        self.assertEqual(len(p.workers[0].waiting), 0)
        self.assertNotIn("w", [x["n"] for _, _, x in log])

    def test_jobs_listed_and_stopped_while_waiting(self):
        """The jobs list: each job waiting or running with its kind, part name, process and time; ✕ Stop of a waiting
        one ends it as cancelled (the running one goes on); a finished job is gone from the list."""
        p, log = self.pool(1)
        out = {}

        def slow():
            progress.begin_request("Plate", "q1")
            out["slow"] = p.run("rebuild", {"n": "slow", "t": 0.6}, key="A")

        def waiting():
            progress.begin_request("Bracket", "q2")
            try:
                p.run("sheet", {"n": "w", "t": 0}, key="A")
            except progress.Cancelled:
                out["stopped"] = True

        t1, t2 = threading.Thread(target=slow), threading.Thread(target=waiting)
        t1.start()
        time.sleep(0.05)
        t2.start()
        time.sleep(0.1)
        jobs = p.list_jobs()
        self.assertEqual([(j["kind"], j["what"], j["state"], j["worker"], j["req"]) for j in jobs],
                         [("Building a part", "Plate", "running", 1, "q1"), ("Making a drawing", "Bracket", "waiting", 1, "q2")])
        self.assertGreater(jobs[0]["elapsed"], 0)
        self.assertTrue(p.cancel(jobs[1]["id"]))
        t2.join(5)
        self.assertTrue(out.get("stopped"))
        self.assertEqual([j["what"] for j in p.list_jobs()], ["Plate"])
        t1.join(5)
        self.assertEqual(out["slow"]["n"], "slow")
        self.assertEqual(p.list_jobs(), [])
        self.assertFalse(p.cancel(jobs[0]["id"]))  # (ended)
        self.assertNotIn("w", [x["n"] for _, _, x in log])


@unittest.skipUnless(OCC, "OCP not installed")
class TestPoolProcesses(unittest.TestCase):
    """Real kernel processes: two of them."""

    def setUp(self):
        self.pool = W.Pool(2)

    def tearDown(self):
        self.pool.close()

    def warm(self):
        """Parts A and B built, each on its own process -> (worker of A, worker of B)."""
        a, b = block(40, "SA"), block(30, "SB")
        self.assertAlmostEqual(self.pool.run("rebuild", a)["body"]["volume"], 8000, delta=1e-3)
        self.assertAlmostEqual(self.pool.run("rebuild", b)["body"]["volume"], 6000, delta=1e-3)
        wa, wb = self.pool.worker_for("rebuild", a), self.pool.worker_for("rebuild", b)
        self.assertIsNot(wa, wb)
        return a, b, wa, wb

    def test_crash_restarts_only_that_worker(self):
        """A process that dies mid-job: that job fails clearly, the jobs waiting for it too; the other process keeps
        running (the same pid); the part's next job starts a new one."""
        a, b, wa, wb = self.warm()
        pid_b, pid_a = wb.proc.pid, wa.proc.pid
        out = {}

        def first():
            try:
                self.pool.run("rebuild", holes(40), key=W.part_key("rebuild", a))
            except W.KernelFailed as e:
                out["first"] = str(e)

        def second():
            try:
                self.pool.run("rebuild", a)
            except W.KernelFailed as e:
                out["second"] = str(e)

        t1 = threading.Thread(target=first)
        t1.start()
        time.sleep(0.3)
        t2 = threading.Thread(target=second)
        t2.start()
        time.sleep(0.2)
        wa.proc.kill()  # (OpenCASCADE crashing mid-job)
        t1.join(30)
        t2.join(30)
        self.assertIn("stopped unexpectedly", out.get("first", ""))
        self.assertIn("another job", out.get("second", ""))
        self.assertTrue(wb.proc.is_alive())
        self.assertEqual(wb.proc.pid, pid_b)
        self.assertAlmostEqual(self.pool.run("rebuild", a)["body"]["volume"], 8000, delta=1e-3)
        self.assertNotEqual(wa.proc.pid, pid_a)

    def test_timeout_kills_only_that_worker(self):
        a, b, wa, wb = self.warm()
        pid_b = wb.proc.pid
        with self.assertRaises(W.KernelFailed) as e:
            self.pool.run("rebuild", holes(60), timeout=0.5, key=W.part_key("rebuild", a))
        self.assertIn("longer than", str(e.exception))
        self.assertIsNone(wa.proc)
        self.assertEqual(wb.proc.pid, pid_b)
        self.assertTrue(wb.proc.is_alive())
        self.assertAlmostEqual(self.pool.run("rebuild", a)["body"]["volume"], 8000, delta=1e-3)

    def test_cancel_kills_only_that_worker(self):
        """Cancel mid-job (the request's rid): the job ends Cancelled at once, its process is killed (the other one
        keeps its pid and its job's answer), nothing waits behind it, and the part's next job runs on a new process."""
        a, b, wa, wb = self.warm()
        pid_a, pid_b = wa.proc.pid, wb.proc.pid
        out = {}

        def heavy():
            try:
                with progress.operation("pool-cancel"):
                    self.pool.run("rebuild", holes(60), key=W.part_key("rebuild", a))
            except progress.Cancelled:
                out["cancelled"] = time.perf_counter()

        t = threading.Thread(target=heavy)
        t.start()
        time.sleep(0.5)
        self.assertTrue(wa.proc.is_alive())
        other = threading.Thread(target=lambda: out.__setitem__("b", self.pool.run("rebuild", b)))
        other.start()
        t0 = time.perf_counter()
        progress.cancel("pool-cancel")
        t.join(10)
        self.assertIn("cancelled", out)
        self.assertLess(out["cancelled"] - t0, 1.0)  # (at once, not when the job would have ended)
        self.assertIsNone(wa.proc)  # (killed)
        self.assertFalse(wa.waiting)
        other.join(30)
        self.assertAlmostEqual(out["b"]["body"]["volume"], 6000, delta=1e-3)
        self.assertEqual(wb.proc.pid, pid_b)
        self.assertAlmostEqual(self.pool.run("rebuild", a)["body"]["volume"], 8000, delta=1e-3)
        self.assertNotEqual(wa.proc.pid, pid_a)

    def test_stop_from_the_jobs_list_kills_only_that_worker(self):
        """✕ Stop of a running job (by its id, no rid): its process is killed at once, the job ends cancelled, the other
        process is untouched, the next job runs."""
        a, b, wa, wb = self.warm()
        pid_b = wb.proc.pid
        out = {}

        def heavy():
            progress.begin_request("Heavy plate", None)
            try:
                self.pool.run("rebuild", holes(60), key=W.part_key("rebuild", a))
            except progress.Cancelled:
                out["cancelled"] = time.perf_counter()

        t = threading.Thread(target=heavy)
        t.start()
        time.sleep(0.5)
        job = next(j for j in self.pool.list_jobs() if j["what"] == "Heavy plate")
        self.assertEqual((job["state"], job["worker"]), ("running", wa.index))
        t0 = time.perf_counter()
        self.assertTrue(self.pool.cancel(job["id"]))
        t.join(10)
        self.assertLess(out["cancelled"] - t0, 1.0)
        self.assertIsNone(wa.proc)
        self.assertEqual(wb.proc.pid, pid_b)
        self.assertEqual(self.pool.list_jobs(), [])
        self.assertAlmostEqual(self.pool.run("rebuild", a)["body"]["volume"], 8000, delta=1e-3)

    def test_memory_limit_restarts_between_jobs(self):
        """A process grown past the limit finishes its job (the answer comes) and is restarted for the next one."""
        a, _, wa, _ = self.warm()
        self.assertGreater(W.rss(wa.proc.pid) or 0, 10 << 20, "the process' memory is not readable here")
        n = wa.restarts
        with mock.patch.object(W, "MEMORY_LIMIT", 1):
            self.assertAlmostEqual(self.pool.run("rebuild", a)["body"]["volume"], 8000, delta=1e-3)
        self.assertIsNone(wa.proc)
        self.assertAlmostEqual(self.pool.run("rebuild", a)["body"]["volume"], 8000, delta=1e-3)
        self.assertEqual(wa.restarts, n + 1)

    def test_two_heavy_parts_at_once(self):
        """Two threads, each rebuilding its own heavy part: on two processes at the same time — the same results as
        one process gives one after the other, in less time."""
        parts = [holes(14, 1.0, "SA"), holes(14, 1.2, "SB")]

        def both(pool):
            out, ths = [None, None], []
            for i, part in enumerate(parts):
                ths.append(threading.Thread(target=lambda i=i, part=part: out.__setitem__(i, pool.run("rebuild", part))))
            t0 = time.perf_counter()
            for t in ths:
                t.start()
            for t in ths:
                t.join(120)
            return out, time.perf_counter() - t0

        one = W.Pool(1)
        try:
            one.run("rebuild", block(10))  # (started: the processes' start is not timed)
            self.pool.run("rebuild", block(10, "SA"))
            self.pool.run("rebuild", block(10, "SB"))
            serial, t1 = both(one)
            parallel, t2 = both(self.pool)
        finally:
            one.close()
        for s, p in zip(serial, parallel):
            self.assertEqual(p["body"]["volume"], s["body"]["volume"])
            self.assertEqual([f.get("name") for f in p["body"]["faces"]], [f.get("name") for f in s["body"]["faces"]])
            self.assertEqual(p["body"]["positions"], s["body"]["positions"])
        self.assertIsNot(self.pool.worker_for("rebuild", parts[0]), self.pool.worker_for("rebuild", parts[1]))
        print(f"\n  two heavy parts: one kernel process {t1:.2f} s, two {t2:.2f} s")
        self.assertLess(t2, t1)


@unittest.skipUnless(OCC, "OCP not installed")
class TestCancelRoutes(unittest.TestCase):
    """Every kernel route the page can Cancel answers it clearly (its rid cancelled before the job got its turn)."""

    def setUp(self):
        import server
        self.c = server.app.test_client()

    def test_clash_check_and_rebuild_cancelled(self):
        inst = [{"id": "I1", "part": block(40), "matrix": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]},
                {"id": "I2", "part": block(30), "matrix": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 5, 0, 0, 1]}]
        progress.cancel("test-clash-cancel")
        r = self.c.post("/api/assembly/clashes", json={"instances": inst, "rid": "test-clash-cancel"})
        self.assertEqual((r.status_code, r.get_json().get("cancelled")), (409, True))
        r = self.c.post("/api/assembly/clashes", json={"instances": inst})  # (the next one runs)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.get_json()["clashes"]), 1)
        progress.cancel("test-rebuild-cancel")
        r = self.c.post("/api/model/rebuild", json={"part": block(40), "rid": "test-rebuild-cancel"})
        self.assertTrue(r.get_json()["cancelled"])

    def test_jobs_route(self):
        """GET /api/jobs: a slow request outside the kernel (its rid) is listed with its kind and part name (the tab's,
        from X-A3D-Tab); POST /api/jobs/r<rid>/cancel cancels it; an ended job answers 404."""
        progress.begin_request("Velký díl", "q9")
        with progress.operation("test-jobs-route", "Building a quick part"):
            progress.report("Slicing", 3, 10)
            jobs = self.c.get("/api/jobs").get_json()["jobs"]
            mine = [j for j in jobs if j["rid"] == "test-jobs-route"]
            self.assertEqual([(j["id"], j["kind"], j["what"], j["req"], j["stage"], j["total"]) for j in mine],
                             [("rtest-jobs-route", "Building a quick part", "Velký díl", "q9", "Slicing", 10)])
            self.assertEqual(self.c.post("/api/jobs/rtest-jobs-route/cancel").status_code, 200)
            with self.assertRaises(progress.Cancelled):
                progress.check()
        self.assertFalse([j for j in self.c.get("/api/jobs").get_json()["jobs"] if j["rid"] == "test-jobs-route"])
        self.assertEqual(self.c.post("/api/jobs/rtest-jobs-route/cancel").status_code, 404)
        self.assertEqual(self.c.post("/api/jobs/k999999/cancel").status_code, 404)
        r = self.c.post("/api/model/rebuild", json={"part": block(40)}, headers={"X-A3D-Tab": "Bracket%20%C4%8D"})
        self.assertEqual(r.status_code, 200)

    def test_print_split_cancelled(self):
        progress.cancel("test-print-cancel")
        r = self.c.post("/api/print/plan", json={"model": {}, "rid": "test-print-cancel"})
        self.assertEqual((r.status_code, r.get_json().get("cancelled")), (409, True))


if __name__ == "__main__":
    unittest.main()
