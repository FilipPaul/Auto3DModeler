"""Sketch clean-up: many small shapes -> few, as a person would draw them (a DXF exporter's fragments, a curve
flattened into hundreds of short lines). Pure functions of the sketch JSON (constraints.py describes it); the input
is not changed. Each returns (sketch parts {points, entities, constraints, dims}, report).

  from_drawing(drawing, tol)   a 2D drawing (drawing2d.py: DXF / DWG / PDF) -> a sketch, cleaned as simplify does: a
                               smooth curve of the file (a SPLINE / ELLIPSE, flattened) becomes one `spline` entity
  simplify(sketch, ids, tol)   🧹 Simplify: ends within tol welded into one point, pieces shorter than tol absorbed by
                               their neighbours, collinear lines joined, arcs on one circle joined (a full turn: a
                               circle), a run of short lines that follows a curve -> arcs, or one spline when that is
                               fewer points; shapes with relations / sizes of their own are left as they are
  join(sketch, ids, tol)       ⛓ Join into one curve: each connected chain of the picked lines / arcs / splines -> one
                               spline through it (within tol), split where it turns sharply (a real corner stays one);
                               a straight run stays a line
  outline(sketch, ids)         ◆ One outline: the picked closed loops -> one rigid `block` entity (holes kept)

The report: {"before": {points, entities, constraints}, "after": {...}, "area": [before, after] (the closed regions,
mm²), "dropped": relations / sizes that went with merged shapes, "issues": [...]}.
"""
from __future__ import annotations

import math

import numpy as np

ORIGIN = "O"
TOL_MIN, TOL_MAX = 1e-4, 1.0
SMOOTH_DEG = 12.0   # two pieces meeting within this turn continue one another (a run that may become one spline)
CORNER_DEG = 25.0   # ⛓ Join: a turn sharper than this is a corner (the spline is split there)
TAN_DEG = 0.05      # a line and an arc this near to tangent get a tangent relation
TAN_MAX_SHAPES = 60  # ... in a sketch of at most this many shapes (in a big import they slow every solve down several times)
SPAN = 16           # spline samples between two fit points (as web/js/modeler/sketcher.js splinePts)


def default_tol(size):
    """The tolerance for a sketch / drawing this big (mm): 0.01 mm, a little more for big ones (1e-4 of the size)."""
    return float(min(0.1, max(0.01, 1e-4 * float(size or 0))))


def _tol(tol, size):
    if tol in (None, "", 0):
        return default_tol(size)
    try:
        v = float(tol)
    except (TypeError, ValueError):
        raise ValueError("The tolerance must be a number (mm).") from None
    if not math.isfinite(v) or v <= 0:
        raise ValueError("The tolerance must be greater than zero.")
    return min(TOL_MAX, max(TOL_MIN, v))


# ------------------------------------------------------------------ curves
def spline_eval(F, per=SPAN):
    """A natural cubic spline over the chord length through points F (n, 2) -> points along it, per between two fit
    points (the sketcher's splinePts; the kernel's B-spline through the same points is within a hair of it)."""
    F = np.asarray(F, float)
    n = len(F)
    if n < 3:
        return F.copy()
    t = np.concatenate([[0.0], np.cumsum(np.maximum(np.hypot(*(F[1:] - F[:-1]).T), 1e-9))])
    out = []
    h = t[1:] - t[:-1]
    s = np.arange(per) / per
    a, b = 1 - s, s
    for k in range(2):
        y = F[:, k]
        m, u = np.zeros(n), np.zeros(n)
        for i in range(1, n - 1):
            sig = (t[i] - t[i - 1]) / (t[i + 1] - t[i - 1])
            q = sig * m[i - 1] + 2
            m[i] = (sig - 1) / q
            u[i] = ((6 * ((y[i + 1] - y[i]) / (t[i + 1] - t[i]) - (y[i] - y[i - 1]) / (t[i] - t[i - 1]))) / (t[i + 1] - t[i - 1]) - sig * u[i - 1]) / q
        for i in range(n - 2, -1, -1):
            m[i] = m[i] * m[i + 1] + u[i]
        v = (a[None, :] * y[:-1, None] + b[None, :] * y[1:, None]
             + ((a ** 3 - a)[None, :] * m[:-1, None] + (b ** 3 - b)[None, :] * m[1:, None]) * (h * h)[:, None] / 6)
        out.append(np.concatenate([v.reshape(-1), [y[-1]]]))
    return np.stack(out, axis=1)


def _to_poly(Q, S):
    """The distance of each point of Q (m, 2) to the polyline S (k, 2)."""
    Q, S = np.asarray(Q, float), np.asarray(S, float)
    if len(S) == 1:
        return np.hypot(*(Q - S[0]).T)
    A, B = S[:-1], S[1:]
    d = B - A
    L = np.maximum((d * d).sum(1), 1e-30)
    w = Q[:, None, :] - A[None, :, :]
    t = np.clip((w * d[None]).sum(2) / L[None], 0, 1)
    near = A[None] + t[..., None] * d[None]
    return np.hypot(*(Q[:, None, :] - near).transpose(2, 0, 1)).min(1)


def fit_spline(D, tol, closed=False):
    """Fit points (a subset of the dense points D, ends kept) whose spline stays within tol of the polyline D both
    ways. -> (k, 2) array."""
    D = np.asarray(D, float)
    n = len(D)
    if n <= 3:
        return D.copy()
    idx = sorted({0, n - 1, *((n // 3, 2 * n // 3) if closed else (n // 2,))})
    for _ in range(80):
        S = spline_eval(D[idx])
        add = []
        for i in range(len(idx) - 1):
            ia, ib = idx[i], idx[i + 1]
            if ib - ia < 2:
                continue
            seg, dense = S[i * SPAN:(i + 1) * SPAN + 1], D[ia:ib + 1]
            d1 = _to_poly(dense, seg)
            if max(d1.max(), _to_poly(seg, dense).max()) > tol:
                k = int(np.argmax(d1))
                add.append(ia + k if 0 < k < ib - ia else (ia + ib) // 2)
        if not add:
            break
        idx = sorted(set(idx) | set(add))
    return D[idx]


def _fits_line(V, tol):
    p, q = V[0], V[-1]
    return len(V) < 3 or _to_poly(V[1:-1], np.array([p, q])).max() <= tol


def _arc_through(V, tol):
    """A circle arc from V[0] to V[-1] through the points between (within tol; its centre on their bisector, so both
    ends are exactly on it) -> (c, r, a0, sweep) or None."""
    p, q = V[0], V[-1]
    m, d = (p + q) / 2, q - p
    L = math.hypot(*d)
    if L < 1e-12:
        return None
    nrm = np.array([-d[1], d[0]]) / L
    W = V[1:-1] - p
    a = 2 * W @ nrm
    b = (V[1:-1] ** 2).sum(1) - (p ** 2).sum() - 2 * W @ m
    if (a * a).sum() < 1e-24:
        return None
    s = float((a * b).sum() / (a * a).sum())
    c = m + s * nrm
    r = float(math.hypot(*(p - c)))
    if r > 1e4 * max(L, tol) or r < tol:
        return None
    mids = (V[1:] + V[:-1]) / 2
    if max(np.abs(np.hypot(*(V - c).T) - r).max(), np.abs(np.hypot(*(mids - c).T) - r).max()) > tol:
        return None
    ang = np.arctan2(V[:, 1] - c[1], V[:, 0] - c[0])
    step = (np.diff(ang) + math.pi) % (2 * math.pi) - math.pi
    if not (np.all(step > 0) or np.all(step < 0)):
        return None
    sw = float(step.sum())
    if abs(sw) >= 2 * math.pi - 1e-6:
        return None
    return c, r, float(ang[0]), sw


def _gallop(i, n, ok):
    """The farthest j (i < j < n) with ok(j) true, assuming it holds up to some j and not after (doubling, then
    halving) -> j, or i when not even ok(i + 1)."""
    if i + 1 >= n or not ok(i + 1):
        return i
    lo, step = i + 1, 1
    while lo + step < n and ok(lo + step):
        lo += step
        step *= 2
    hi = min(n, lo + step)
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if ok(mid):
            lo = mid
        else:
            hi = mid
    return lo


class Piece:
    """A line, arc, spline or polyline between two nodes (ends welded), in the order it is walked."""
    __slots__ = ("k", "V", "c", "r", "a0", "sw", "src", "ends", "smooth", "ckey", "rev")

    def __init__(self, k, V=None, c=None, r=None, a0=None, sw=None, src=None, smooth=False, ckey=None):
        self.k, self.V, self.c, self.r, self.a0, self.sw = k, None if V is None else np.asarray(V, float), c, r, a0, sw
        self.src, self.smooth, self.ckey, self.ends, self.rev = src, smooth, ckey, [None, None], False

    def end(self, i):
        if self.k == "arc":
            a = self.a0 + (self.sw if i else 0.0)
            return np.array([self.c[0] + self.r * math.cos(a), self.c[1] + self.r * math.sin(a)])
        return self.V[-1 if i else 0]

    def length(self):
        if self.k == "arc":
            return abs(self.sw) * self.r
        return float(np.hypot(*np.diff(self.V, axis=0).T).sum()) if len(self.V) > 1 else 0.0

    def reversed(self):
        p = Piece(self.k, None if self.V is None else self.V[::-1], self.c, self.r, None, None, self.src, self.smooth, self.ckey)
        if self.k == "arc":
            p.a0, p.sw = self.a0 + self.sw, -self.sw
        p.ends, p.rev = self.ends[::-1], not self.rev
        return p

    def tangent(self, i):
        """The direction it goes at its start (i = 0) / end (i = 1)."""
        if self.k == "arc":
            a = self.a0 + (self.sw if i else 0.0)
            s = 1.0 if self.sw > 0 else -1.0
            return np.array([-math.sin(a) * s, math.cos(a) * s])
        V = self.V
        if self.k == "spline" and len(V) > 2:
            S = spline_eval(V[:2 + 1] if not i else V[-3:], per=8)
            d = S[1] - S[0] if not i else S[-1] - S[-2]
        else:
            d = V[1] - V[0] if not i else V[-1] - V[-2]
        L = math.hypot(*d)
        return d / L if L > 1e-15 else np.array([1.0, 0.0])

    def dense(self, tol, step=None):
        """Points along it, start to end: arcs within tol / 4, lines cut every `step` (when given)."""
        if self.k == "arc":  # (at most 10° a step: a small arc does not look like a corner)
            da = min(math.radians(10), 2 * math.acos(max(-1.0, 1 - min(1.0, tol / 4 / max(self.r, 1e-12)))))
            n = int(min(720, max(2, math.ceil(abs(self.sw) / max(da, 1e-6)))))
            a = self.a0 + self.sw * np.arange(n + 1) / n
            return np.stack([self.c[0] + self.r * np.cos(a), self.c[1] + self.r * np.sin(a)], 1)
        V = spline_eval(self.V, per=8) if self.k == "spline" else self.V
        if step and len(V) > 1:
            out = [V[:1]]
            for p, q in zip(V[:-1], V[1:]):
                k = int(min(64, max(1, math.ceil(math.hypot(*(q - p)) / step))))
                out.append(p + (q - p) * (np.arange(1, k + 1) / k)[:, None])
            V = np.concatenate(out)
        return V


def _turn(t0, t1):
    """Degrees between two directions."""
    return math.degrees(math.acos(max(-1.0, min(1.0, float(t0 @ t1)))))


# ------------------------------------------------------------------ welding and chains
class _Nodes:
    """Ends welded within tol: union-find over end keys (sketch point ids, or one per end) and a grid by place."""

    def __init__(self, tol):
        self.tol, self.par, self.pos, self.pinned = tol, {}, {}, {}

    def add(self, key, p, pinned=False):
        if key not in self.par:
            self.par[key] = key
            self.pos[key] = np.asarray(p, float)
        if pinned:
            self.pinned[key] = True
        return key

    def find(self, k):
        while self.par[k] != k:
            self.par[k] = self.par[self.par[k]]
            k = self.par[k]
        return k

    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        if a != b:
            if self.pinned.get(b) and not self.pinned.get(a):
                a, b = b, a
            self.par[b] = a

    def weld(self):
        cell, tol = {}, self.tol
        for k, p in self.pos.items():
            g = (int(math.floor(p[0] / tol)), int(math.floor(p[1] / tol)))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for o in cell.get((g[0] + dx, g[1] + dy), ()):
                        if math.hypot(*(self.pos[o] - p)) <= tol:
                            self.union(o, k)
            cell.setdefault(g, []).append(k)

    def groups(self):
        out = {}
        for k in self.par:
            out.setdefault(self.find(k), []).append(k)
        return out

    def place(self):
        """Each group's place: its pinned point's (the first), else the middle of its ends."""
        at = {}
        for root, ks in self.groups().items():
            pin = [k for k in ks if self.pinned.get(k)]
            at[root] = self.pos[pin[0]] if pin else np.mean([self.pos[k] for k in ks], axis=0)
        return at


def _chains(pieces, breaks):
    """Pieces joined end to end through nodes with exactly two pieces (and not in `breaks`) -> [(oriented pieces,
    closed)]."""
    at = {}
    for i, p in enumerate(pieces):
        for e in (0, 1):
            at.setdefault(p.ends[e], []).append((i, e))
    through = lambda n: len(at.get(n, ())) == 2 and n not in breaks  # noqa: E731
    used, out = set(), []

    def walk(i, rev):
        chain, node = [], None
        while i is not None and i not in used:
            used.add(i)
            p = pieces[i].reversed() if rev else pieces[i]
            chain.append(p)
            node = p.ends[1]
            if not through(node):
                break
            nxt = [(j, e) for j, e in at[node] if j not in used]
            if not nxt:
                break
            i, rev = nxt[0][0], nxt[0][1] == 1
        return chain, node

    for i, p in enumerate(pieces):  # from the ends of open chains first
        if i in used:
            continue
        for e in (0, 1):
            if not through(p.ends[e]):
                chain, _ = walk(i, e == 1)
                out.append((chain, False))
                break
    for i in range(len(pieces)):  # what is left goes round (closed loops)
        if i not in used:
            chain, _ = walk(i, False)
            out.append((chain, chain[0].ends[0] == chain[-1].ends[1]))
    return out


# ------------------------------------------------------------------ simplifying a chain
def _segment(V, tol):
    """A polyline (n, 2) -> pieces of lines and arcs along it, each as long as fits within tol (greedy, the longer of
    the two at each step)."""
    out, i, n = [], 0, len(V)
    while i < n - 1:
        lj = _gallop(i, n, lambda j: _fits_line(V[i:j + 1], tol))
        aj = _gallop(i + 2, n, lambda j: _arc_through(V[i:j + 1], tol) is not None) if i + 3 < n else i
        if aj >= i + 3 and aj > lj + 1:
            c, r, a0, sw = _arc_through(V[i:aj + 1], tol)
            out.append(Piece("arc", V=V[[i, aj]], c=c, r=r, a0=a0, sw=sw))
            i = aj
        else:
            j = max(lj, i + 1)
            out.append(Piece("line", V=V[[i, j]]))
            i = j
    return out


def _runs_to_splines(prims, V, tol):
    """Runs of three or more lines / arcs that continue one another -> one spline each, when that is fewer points."""
    out, i = [], 0
    while i < len(prims):
        j = i
        while j + 1 < len(prims) and _turn(prims[j].tangent(1), prims[j + 1].tangent(0)) < SMOOTH_DEG:
            j += 1
        run = prims[i:j + 1]
        if len(run) >= 3:
            D = np.concatenate([run[0].dense(tol, 20 * tol)] + [p.dense(tol, 20 * tol)[1:] for p in run[1:]])
            F = fit_spline(D, tol)
            cost = (len(run) - 1) + sum(p.k == "arc" for p in run)  # the points the lines / arcs need (inner ends, centres)
            if len(F) - 2 <= cost:
                out.append(Piece("spline", V=F))
                i = j + 1
                continue
        out.extend(run)
        i = j + 1
    return out


def _poly_pieces(V, tol, smooth):
    """A polyline -> lines / arcs / splines: a smooth curve of the file (split at sharp turns) -> a line, an arc or one
    spline; else lines and arcs, runs of them that follow a curve -> a spline."""
    V = np.asarray(V, float)
    keep = np.concatenate([[True], np.hypot(*np.diff(V, axis=0).T) > 1e-12])
    V = V[keep]
    if len(V) < 2:
        return []
    if smooth:
        cut = [0]
        for k in range(1, len(V) - 1):
            a, b = V[k] - V[k - 1], V[k + 1] - V[k]
            if _turn(a / math.hypot(*a), b / math.hypot(*b)) > 35:
                cut.append(k)
        cut.append(len(V) - 1)
        out = []
        for a, b in zip(cut[:-1], cut[1:]):
            W = V[a:b + 1]
            if _fits_line(W, tol):
                out.append(Piece("line", V=W[[0, -1]]))
                continue
            arc = _arc_through(W, tol) if len(W) >= 4 else None
            if arc:
                out.append(Piece("arc", V=W[[0, -1]], c=arc[0], r=arc[1], a0=arc[2], sw=arc[3]))
                continue
            F = fit_spline(Piece("line", V=W).dense(tol, 20 * tol), tol)
            out.append(Piece("spline", V=F) if len(F) > 2 else Piece("line", V=W[[0, -1]]))
        return out
    return _runs_to_splines(_segment(V, tol), V, tol)


def _circle_of(V, tol):
    """Points all round one circle (within tol; an even spread round it) -> (centre, radius) or None."""
    if len(V) < 6:
        return None
    A = np.column_stack([2 * V, np.ones(len(V))])
    sol, *_ = np.linalg.lstsq(A, (V ** 2).sum(1), rcond=None)
    c = sol[:2]
    r = math.sqrt(max(sol[2] + c @ c, 0.0))
    if r < tol:
        return None
    mids = (V + np.roll(V, -1, axis=0)) / 2
    if max(np.abs(np.hypot(*(V - c).T) - r).max(), np.abs(np.hypot(*(mids - c).T) - r).max()) > tol:
        return None
    ang = np.arctan2(V[:, 1] - c[1], V[:, 0] - c[0])
    step = (np.diff(np.concatenate([ang, ang[:1]])) + math.pi) % (2 * math.pi) - math.pi
    return (c, r) if (np.all(step > 0) or np.all(step < 0)) and abs(abs(step.sum()) - 2 * math.pi) < 1e-6 else None


def _same_circle(p, q, tol):
    return p.k == q.k == "arc" and math.hypot(*(np.asarray(p.c) - q.c)) <= tol and abs(p.r - q.r) <= tol and (p.sw > 0) == (q.sw > 0)


def _simplify_chain(chain, closed, tol, nodes_at):
    """One chain (oriented pieces) -> simpler pieces, each with .ends set (the chain's own nodes kept at its ends,
    inner ones dropped where pieces merge; new inner ones as ("new", place))."""
    groups = []  # [kind, [pieces]]: polylines (lines and polys walked together), arcs, others kept
    for p in chain:
        kind = "poly" if p.k in ("line", "poly") else p.k
        if groups and kind == "poly" == groups[-1][0] and not p.smooth and not groups[-1][1][-1].smooth:
            groups[-1][1].append(p)
        elif groups and kind == "arc" == groups[-1][0] and _same_circle(groups[-1][1][-1], p, tol):
            groups[-1][1].append(p)
        else:
            groups.append([kind, [p]])
    if closed and len(groups) > 1 and groups[0][0] == groups[-1][0] and (
            (groups[0][0] == "arc" and _same_circle(groups[-1][1][-1], groups[0][1][0], tol))
            or (groups[0][0] == "poly" and not groups[0][1][0].smooth and not groups[-1][1][-1].smooth)):
        groups[0][1][:0] = groups.pop()[1]  # (round the loop's start)
    out = []
    for kind, ps in groups:
        start, end = ps[0].ends[0], ps[-1].ends[1]
        if kind == "arc":
            if len(ps) == 1:
                out.append(ps[0])
                continue
            q = ps[0]
            sw = sum(p.sw for p in ps)
            if abs(abs(sw) - 2 * math.pi) < 1e-6 or (start == end and abs(sw) > math.pi):
                c = Piece("circle", c=np.asarray(q.c), r=float(np.mean([p.r for p in ps])), ckey=q.ckey)
                c.ends = [start, end]
                out.append(c)
                continue
            m = Piece("arc", c=q.c, r=q.r, a0=q.a0, sw=sw, ckey=q.ckey)
            m.ends = [start, end]
            out.append(m)
        elif kind == "poly":
            if len(ps) == 1 and ps[0].k == "line":
                out.append(ps[0])
                continue
            V = np.concatenate([ps[0].V] + [p.V[1:] for p in ps[1:]])
            V[0], V[-1] = nodes_at[start], nodes_at[end]
            smooth = any(p.smooth for p in ps)
            if closed and len(groups) == 1 and len(V) > 4:  # a closed polyline alone: a circle? else start at its sharpest corner
                ring = _circle_of(V[:-1], tol)
                if ring:
                    c = Piece("circle", c=ring[0], r=ring[1])
                    c.ends = [start, end]
                    out.append(c)
                    continue
                k = int(np.argmax(_turns(V, True)))
                if k:
                    V = np.concatenate([V[k:], V[1:k + 1]])
                    start = end = ("new", tuple(float(x) for x in V[0]))
            news = _poly_pieces(V, tol, smooth=smooth)
            if not news:
                continue
            if len(ps) == len(news) and all(p.k == q.k == "line" for p, q in zip(ps, news)):
                out.extend(ps)  # (nothing joined: the lines stay as they were)
                continue
            for i, p in enumerate(news):
                p.ends = [start if i == 0 else ("new", tuple(float(x) for x in p.V[0])),
                          end if i == len(news) - 1 else ("new", tuple(float(x) for x in p.V[-1]))]
            out.extend(news)
        else:
            out.extend(ps)
    return out


def _turns(D, closed):
    """The turn (degrees) at each point of a polyline (its ends 0; a closed one's start between its last and first sides)."""
    d = np.diff(D, axis=0)
    u = d / np.maximum(np.hypot(*d.T), 1e-15)[:, None]
    out = np.zeros(len(D))
    out[1:-1] = np.degrees(np.arccos(np.clip((u[:-1] * u[1:]).sum(1), -1, 1)))
    if closed and len(u) > 1:
        out[0] = math.degrees(math.acos(max(-1.0, min(1.0, float(u[-1] @ u[0])))))
    return out


def _dense_chain(chain, tol, at):
    """A chain's pieces as one polyline (each piece's ends where its nodes are; no two points in one place)."""
    D = []
    for n, p in enumerate(chain):
        d = p.dense(tol, 20 * tol)
        d[0], d[-1] = at[p.ends[0]], at[p.ends[1]]
        D.extend((d if not n else d[1:]).tolist())
    D = np.array(D)
    keep = np.concatenate([[True], np.hypot(*np.diff(D, axis=0).T) > 1e-12])
    return D[keep]


def _join_chain(chain, closed, tol, at):
    """⛓ One chain -> one spline per run between sharp corners (a straight run: a line). Its end nodes stay; a corner
    keeps the node that was there."""
    D = _dense_chain(chain, tol, at)
    if len(D) < 2:
        return []
    closed = closed and len(D) > 3 and math.hypot(*(D[0] - D[-1])) < 1e-9
    corner = [int(i) for i in np.where(_turns(D, closed) > CORNER_DEG)[0]]
    if closed and corner:  # (start the loop at a corner, so no run goes round its seam)
        c0 = corner[0]
        D = np.concatenate([D[c0:], D[1:c0 + 1]])
        corner = [c - c0 for c in corner]
    cuts = sorted(set([0, len(D) - 1] + [c for c in corner if 0 < c < len(D) - 1]))
    known = {}
    for p in chain:
        for k in p.ends:
            known.setdefault(tuple(np.round(at[k], 9)), k)
    node = lambda v: known.get(tuple(np.round(v, 9)), ("new", tuple(float(x) for x in v)))  # noqa: E731
    out = []
    for a, b in zip(cuts[:-1], cuts[1:]):
        W = D[a:b + 1]
        p = Piece("line", V=W[[0, -1]]) if _fits_line(W, tol) and not (closed and len(cuts) == 2) else Piece(
            "spline", V=fit_spline(W, tol, closed=closed and len(cuts) == 2))
        p.ends = [node(W[0]), node(W[-1])]
        out.append(p)
    if not closed:
        out[0].ends[0], out[-1].ends[1] = chain[0].ends[0], chain[-1].ends[1]
    return out


# ------------------------------------------------------------------ sketch in, sketch out
def _counts(sk):
    return {"points": len(sk.get("points") or {}), "entities": len(sk.get("entities") or []), "constraints": len(sk.get("constraints") or [])}


def _refs_of(x):
    """The point ids a constraint / dimension names."""
    out = []
    for k in ("p", "p2", "a", "b", "c"):
        v = x.get(k)
        if isinstance(v, str):
            out.append(v)
    for pr in x.get("pairs") or []:
        for v in pr:
            if isinstance(v, str):
                out.append(v)
            elif isinstance(v, list):
                out.extend(q for q in v if isinstance(q, str))
    return out


def _ents_of(x):
    out = [x.get(k) for k in ("e", "e2", "arc") if isinstance(x.get(k), str)]
    out += list(x.get("lines") or []) + list(x.get("src") or []) + list(x.get("copies") or [])
    for pr in (x.get("pairs") or []) if x.get("t") == "off" else []:
        out += [v for v in pr[:2] if isinstance(v, str)]
    for pr in x.get("circles") or []:
        for v in pr:
            out += [v] if isinstance(v, str) else list(v)
    return out


class _Ids:
    def __init__(self, sk):
        self.used = set(sk.get("points") or {}) | {e.get("id") for e in sk.get("entities") or []} | {
            c.get("id") for c in sk.get("constraints") or []} | {d.get("id") for d in sk.get("dims") or []} | {
            e.get("g") for e in sk.get("entities") or [] if e.get("g")}
        self.n = {}

    def __call__(self, pre):
        n = self.n.get(pre, 0)
        while True:
            n += 1
            if f"{pre}{n}" not in self.used:
                break
        self.n[pre] = n
        self.used.add(f"{pre}{n}")
        return f"{pre}{n}"


def _size_of(pts):
    if not pts:
        return 0.0
    a = np.asarray(list(pts), float)
    return float(max(a[:, 0].max() - a[:, 0].min(), a[:, 1].max() - a[:, 1].min()))


def _pieces_of_sketch(sk, chosen, splines_whole):
    """The chosen shapes of a sketch -> pieces (ends keyed by their point ids)."""
    P = {k: np.asarray(v, float) for k, v in (sk.get("points") or {}).items()}
    P[ORIGIN] = np.zeros(2)
    out = []
    for e in sk.get("entities") or []:
        if e.get("id") not in chosen:
            continue
        t = e.get("t")
        if t == "line" and e.get("a") in P and e.get("b") in P:
            p = Piece("line", V=[P[e["a"]], P[e["b"]]], src=e)
            p.ends = [e["a"], e["b"]]
        elif t == "arc" and all(e.get(k) in P for k in ("c", "a", "b")):
            c, a, b = P[e["c"]], P[e["a"]], P[e["b"]]
            r = float(math.hypot(*(a - c)))
            if r <= 1e-12:
                continue
            a0 = math.atan2(a[1] - c[1], a[0] - c[0])
            sw = (math.atan2(b[1] - c[1], b[0] - c[0]) - a0) % (2 * math.pi) or 2 * math.pi
            p = Piece("arc", c=c, r=r, a0=a0, sw=sw, src=e, ckey=e["c"])
            p.ends = [e["a"], e["b"]]
        elif t == "spline" and splines_whole and len(e.get("pts") or []) >= 2 and all(q in P for q in e["pts"]):
            p = Piece("spline", V=[P[q] for q in e["pts"]], src=e)
            p.ends = [e["pts"][0], e["pts"][-1]]
        else:
            continue
        out.append(p)
    return out, P


def _rebuild(sk, chosen, pieces_out, nodes, at, ids, tol, removed_ok=True):
    """The sketch with the chosen shapes replaced by pieces_out -> new sketch parts, dropped (constraints + dims)."""
    pts = {k: list(v) for k, v in (sk.get("points") or {}).items()}
    # a node -> the point id it keeps: a pinned one, else a point it had, else a new one
    node_id, rename = {}, {}
    for root, ks in nodes.groups().items():
        own = [k for k in ks if isinstance(k, str) and (k == ORIGIN or k in pts)]
        pin = [k for k in own if nodes.pinned.get(k)]
        keep = (pin or own or [None])[0]
        if keep is None:
            keep = ids("p")
        node_id[root] = keep
        for k in own:
            if k != keep:
                rename[k] = keep
    new_pts, centres = {}, {}

    def pid(node):
        if isinstance(node, tuple) and node and node[0] == "new":
            key = tuple(round(v, 9) for v in node[1])
            if key not in new_pts:
                new_pts[key] = ids("p")
                pts[new_pts[key]] = [float(node[1][0]), float(node[1][1])]
            return new_pts[key]
        root = nodes.find(node)
        k = node_id[root]
        if k != ORIGIN:
            pts[k] = [float(at[root][0]), float(at[root][1])]
        return k

    def cid(p):
        key = (round(float(p.c[0]) / tol), round(float(p.c[1]) / tol))
        if p.ckey and p.ckey in pts and math.hypot(pts[p.ckey][0] - p.c[0], pts[p.ckey][1] - p.c[1]) <= tol:
            return p.ckey
        if key not in centres:
            centres[key] = ids("p")
            pts[centres[key]] = [float(p.c[0]), float(p.c[1])]
        return centres[key]

    ents = [e for e in sk.get("entities") or [] if e.get("id") not in chosen]
    for e in ents:
        for k in ("a", "b", "c"):
            if isinstance(e.get(k), str) and e[k] in rename:
                e[k] = rename[e[k]]
        if e.get("pts"):
            e["pts"] = [rename.get(q, q) for q in e["pts"]]
    added, tans = [], []
    for p in pieces_out:
        a, b = pid(p.ends[0]), pid(p.ends[1])
        # (a piece with a src is a shape that stayed as it was: its id, relations and sizes stay too; walked the
        # other way, its ends are swapped back)
        if p.k == "line":
            if a == b:
                continue
            if p.rev:
                a, b = b, a
            e = {**p.src, "a": a, "b": b} if p.src is not None else {"id": ids("l"), "t": "line", "a": a, "b": b}
        elif p.k == "arc":
            if a == b:
                continue
            if p.sw < 0:  # (arcs go counter-clockwise from a to b)
                a, b = b, a
            e = {**p.src} if p.src is not None else {"id": ids("a"), "t": "arc"}
            e.update({"c": cid(p), "a": a, "b": b})
        elif p.k == "circle":
            e = {"id": ids("c"), "t": "circle", "c": cid(p), "r": round(float(p.r), 6)}
        elif p.k == "spline":
            if p.src is not None:
                if p.rev:
                    a, b = b, a
                e = {**p.src, "pts": [a, *p.src["pts"][1:-1], b]}
            else:
                inner = []
                for v in p.V[1:-1]:
                    q = ids("p")
                    pts[q] = [float(v[0]), float(v[1])]
                    inner.append(q)
                e = {"id": ids("s"), "t": "spline", "pts": [a, *inner, b], "fit": True}
        else:
            continue
        added.append((e, p))
    # where a line meets an arc tangentially (as drawn): a tangent relation keeps it so
    by_pt = {}
    for e, p in added:
        if e["t"] in ("line", "arc"):
            for q in (e["a"], e["b"]):
                by_pt.setdefault(q, []).append(e)
    for q, es in by_pt.items():
        if len(es) != 2 or {x["t"] for x in es} != {"line", "arc"}:
            continue
        ln, arc = es if es[0]["t"] == "line" else es[::-1]
        L = np.asarray(pts[ln["b"]]) - np.asarray(pts[ln["a"]])
        R = np.asarray(pts[q]) - np.asarray(pts[arc["c"]])
        if math.hypot(*L) > 1e-12 and math.hypot(*R) > 1e-12:
            cos = abs(float(L @ R)) / math.hypot(*L) / math.hypot(*R)
            if cos < math.sin(math.radians(TAN_DEG)):
                tans.append({"id": ids("k"), "t": "tan", "e": ln["id"], "arc": arc["id"], "p": q})
    entities = ents + [e for e, _ in added]
    if len(entities) > TAN_MAX_SHAPES:
        tans = []
    alive = {e["id"] for e in entities}
    used = {q for e in entities for q in (e.get("a"), e.get("b"), e.get("c"), *(e.get("pts") or [])) if isinstance(q, str)}
    cons, dims, dropped = [], [], 0
    for k in sk.get("constraints") or []:
        k = _renamed(k, rename)
        if all(x in alive for x in _ents_of(k)) and all(q == ORIGIN or q in used or (k.get("t") == "corner" and q in pts) for q in _refs_of(k)):
            cons.append(k)
        else:
            dropped += 1
    for d in sk.get("dims") or []:
        d = _renamed(d, rename)
        ends_ok = all(not isinstance(d.get(x), str) or d[x] == ORIGIN or d[x] in used for x in ("a", "b"))
        mids_ok = all(not isinstance(d.get(x), dict) or "mid" not in d[x] or d[x]["mid"] in alive for x in ("a", "b"))
        if (not d.get("e") or d["e"] in alive) and (not d.get("e2") or d["e2"] in alive) and ends_ok and mids_ok:
            dims.append(d)
        else:
            dropped += 1
    corner_pts = {k["p"] for k in cons if k.get("t") == "corner"}
    points = {k: [round(v[0], 6), round(v[1], 6)] for k, v in pts.items() if k in used or k in corner_pts}
    return {"points": points, "entities": entities, "constraints": cons + tans, "dims": dims}, dropped


def _src_sweep(e, pts):
    c, a, b = (np.asarray(pts[e[k]], float) for k in ("c", "a", "b"))
    a0 = math.atan2(a[1] - c[1], a[0] - c[0])
    return (math.atan2(b[1] - c[1], b[0] - c[0]) - a0) % (2 * math.pi) or 2 * math.pi


def _renamed(x, rename):
    x = dict(x)
    for k in ("p", "p2", "a", "b", "c"):
        if isinstance(x.get(k), str) and x[k] in rename:
            x[k] = rename[x[k]]
    if x.get("pairs") and x.get("t") in ("mir", "pat"):
        x["pairs"] = [[rename.get(v, v) if isinstance(v, str) else [rename.get(q, q) for q in v] for v in pr] for pr in x["pairs"]]
    return x


def region_area(sk, loops_too=False):
    """The area the sketch's closed outlines enclose (even-odd, as the kernel nests them), mm² — sampled, for checks
    (loops_too: -> (area, how many closed loops))."""
    from shapely.geometry import LineString, Polygon
    from shapely.ops import polygonize, unary_union
    P = {k: np.asarray(v, float) for k, v in (sk.get("points") or {}).items()}
    P[ORIGIN] = np.zeros(2)
    lines, loops = [], []
    for e in sk.get("entities") or []:
        if e.get("construction"):
            continue
        t = e.get("t")
        try:
            if t == "line":
                lines.append(LineString([P[e["a"]], P[e["b"]]]))
            elif t == "arc":
                c, a, b = P[e["c"]], P[e["a"]], P[e["b"]]
                r = math.hypot(*(a - c))
                a0 = math.atan2(a[1] - c[1], a[0] - c[0])
                sw = (math.atan2(b[1] - c[1], b[0] - c[0]) - a0) % (2 * math.pi) or 2 * math.pi
                n = max(8, int(math.degrees(sw)))
                V = [c + r * np.array([math.cos(a0 + sw * i / n), math.sin(a0 + sw * i / n)]) for i in range(n + 1)]
                V[0], V[-1] = a, b
                lines.append(LineString(V))
            elif t == "spline":
                lines.append(LineString(spline_eval([P[q] for q in e["pts"]])))
            elif t == "circle":
                c, r = P[e["c"]], float(e["r"])
                loops.append(Polygon([(c[0] + r * math.cos(2 * math.pi * i / 720), c[1] + r * math.sin(2 * math.pi * i / 720)) for i in range(720)]))
            elif t == "block":
                at, k = e.get("at") or (0, 0), float(e.get("scale") or 1)
                for poly in e.get("polys") or []:
                    for ring in poly:
                        if len(ring) >= 3:
                            loops.append(Polygon([(at[0] + k * x, at[1] + k * y) for x, y in ring]))
        except (KeyError, TypeError, ValueError):
            continue
    if lines:
        loops += [Polygon(p.exterior) for p in polygonize(unary_union(lines)) if p.area > 1e-12]  # (each loop whole, as the kernel takes it)
    # even-odd: a loop inside an odd number of others is a hole
    loops.sort(key=lambda p: -p.area)
    area = 0.0
    for i, p in enumerate(loops):
        depth = sum(1 for q in loops[:i] if q.buffer(1e-9).contains(p))
        area += p.area if depth % 2 == 0 else -p.area
    return (float(area), len(loops)) if loops_too else float(area)


def _locked(sk):
    """The shapes that have relations or sizes of their own (🧹 Simplify leaves them as they are)."""
    out = set()
    for x in (sk.get("constraints") or []) + (sk.get("dims") or []):
        if x.get("t") == "tan":
            continue
        out.update(_ents_of(x))
        for v in (x.get("a"), x.get("b")):
            if isinstance(v, dict) and "mid" in v:
                out.add(v["mid"])
    return out


def _run(sk, ids, tol, op):
    sk = {"points": dict(sk.get("points") or {}), "entities": [dict(e) for e in sk.get("entities") or []],
          "constraints": [dict(c) for c in sk.get("constraints") or []], "dims": [dict(d) for d in sk.get("dims") or []]}
    allowed = {e["id"] for e in sk["entities"] if e.get("t") in ("line", "arc", "spline") and not e.get("construction")}
    chosen = (set(ids) & allowed) if ids else allowed
    if op == "simplify":
        chosen -= _locked(sk)
    tol = _tol(tol, _size_of((sk["points"]).values()))
    before = _counts(sk)
    pieces, P = _pieces_of_sketch(sk, chosen, splines_whole=True)
    if op == "simplify":  # (a spline is already one shape: its ends weld, its points stay)
        for p in pieces:
            if p.k == "spline":
                p.k = "keep"
    nodes = _Nodes(tol)
    others = [e for e in sk["entities"] if e["id"] not in chosen]
    ext = {q for e in others for q in (e.get("a"), e.get("b"), e.get("c"), *(e.get("pts") or [])) if isinstance(q, str)}
    for x in sk["constraints"] + sk["dims"]:  # (what holds a point stays; ⛓ Join: not what goes with the joined shapes)
        if not (op == "join" and any(e in chosen for e in _ents_of(x))):
            ext.update(_refs_of(x))
    for p in pieces:
        for e in (0, 1):
            nodes.add(p.ends[e], P[p.ends[e]], pinned=p.ends[e] in ext or p.ends[e] == ORIGIN)
    nodes.weld()
    pieces, nodes = _absorb(pieces, nodes, tol)
    at = nodes.place()
    for p in pieces:
        p.ends = [nodes.find(k) for k in p.ends]
    pieces = [p for p in pieces if not (p.k == "line" and p.ends[0] == p.ends[1])]
    breaks = {nodes.find(k) for k in nodes.par if nodes.pinned.get(k)}
    out = []
    for chain, closed in _chains(pieces, breaks):
        out += (_join_chain if op == "join" else _simplify_chain)(chain, closed, tol, at)
    for p in out:  # ("keep": a spline as it was)
        if p.k == "keep":
            p.k = "spline"
    new, dropped = _rebuild(sk, chosen, out, nodes, at, _Ids(sk), tol)
    return new, before, dropped, tol


def _absorb(pieces, nodes, tol):
    """Pieces shorter than tol (an exporter's crumbs) go: their two ends become one point."""
    keep = []
    for p in pieces:
        if p.k != "keep" and p.length() < tol and nodes.find(p.ends[0]) != nodes.find(p.ends[1]):
            nodes.union(p.ends[0], p.ends[1])
        elif p.k != "keep" and p.length() < tol:
            continue
        else:
            keep.append(p)
    return keep, nodes


def _report(sk_before, new, before, dropped, tol, extra=None):
    (a0, n0), (a1, n1) = region_area(sk_before, True), region_area(new, True)
    issues = []
    if a0 > 1e-9 and n0 == n1 and abs(a1 - a0) > 0.005 * a0:  # (other loops: gaps closed — the area is meant to change)
        issues.append({"severity": "warning", "code": "area_changed", "message": f"The enclosed area changed by {100 * (a1 - a0) / a0:+.2f} %.",
                       "params": {"before": a0, "after": a1}})
    return {"before": before, "after": _counts(new), "area": [round(a0, 6), round(a1, 6)], "dropped": dropped, "tol": tol,
            "issues": issues, **(extra or {})}


def simplify(sketch, ids=None, tol=None):
    """🧹 Simplify the picked shapes (ids; None = the whole sketch) -> (sketch parts, report)."""
    new, before, dropped, tol = _run(sketch, ids, tol, "simplify")
    return new, _report(sketch, new, before, dropped, tol)


def join(sketch, ids, tol=None):
    """⛓ Join the picked lines / arcs / splines into one curve per connected chain -> (sketch parts, report)."""
    if not ids:
        raise ValueError("Pick the shapes to join first.")
    new, before, dropped, tol = _run(sketch, ids, tol, "join")
    return new, _report(sketch, new, before, dropped, tol)


def outline(sketch, ids, name="Outline", tol=None):
    """◆ The picked closed loops (lines, arcs, splines, circles) -> one rigid block entity, holes kept ->
    (sketch parts, report). What is picked but not on a closed loop stays."""
    from shapely.geometry import LineString, Point, Polygon
    from shapely.geometry.polygon import orient
    from shapely.ops import polygonize, unary_union
    if not ids:
        raise ValueError("Pick the closed outline first.")
    sk = {"points": dict(sketch.get("points") or {}), "entities": [dict(e) for e in sketch.get("entities") or []],
          "constraints": [dict(c) for c in sketch.get("constraints") or []], "dims": [dict(d) for d in sketch.get("dims") or []]}
    tol = _tol(tol, _size_of(sk["points"].values()))
    before = _counts(sk)
    picked = [e for e in sk["entities"] if e.get("id") in set(ids) and e.get("t") in ("line", "arc", "spline", "circle") and not e.get("construction")]
    pieces, P = _pieces_of_sketch(sk, {e["id"] for e in picked}, splines_whole=True)
    segs, owner = [], []
    for p in pieces:
        segs.append(LineString(p.dense(tol)))
        owner.append(p.src["id"])
    rings = [p for p in polygonize(unary_union(segs)) if p.area > 1e-9] if segs else []
    for e in picked:
        if e["t"] == "circle" and e.get("c") in P:
            c, r = P[e["c"]], float(e["r"])
            n = int(min(720, max(24, math.ceil(math.pi / math.acos(max(-1.0, 1 - min(1.0, tol / max(r, 1e-9))))))))
            rings.append(Polygon([(c[0] + r * math.cos(2 * math.pi * i / n), c[1] + r * math.sin(2 * math.pi * i / n)) for i in range(n)]))
            owner.append(e["id"])
            segs.append(rings[-1].exterior)
    if not rings:
        raise ValueError("The picked shapes do not close into an outline.")
    # the shapes on a loop go into the block; others stay
    used = set()
    edges = unary_union([r.exterior for r in rings])
    for s, o in zip(segs, owner):
        if s.length > 0 and s.interpolate(0.5, normalized=True).distance(edges) < 1e-6:
            used.add(o)
    # even-odd nesting: shells and their holes
    rings.sort(key=lambda p: -p.area)
    polys = []
    for i, r in enumerate(rings):
        inside = [j for j in range(i) if rings[j].buffer(1e-9).contains(r)]
        if len(inside) % 2 == 0:
            polys.append([orient(r, 1.0), []])
        else:
            parent = next((pp for pp in reversed(polys) if pp[0].buffer(1e-9).contains(r)), None)
            if parent is not None:
                parent[1].append(r)
    xs = [x for pp in polys for x, _ in pp[0].exterior.coords]
    ys = [y for pp in polys for _, y in pp[0].exterior.coords]
    x0, y0 = min(xs), min(ys)
    ring = lambda g: [[round(x - x0, 6), round(y - y0, 6)] for x, y in list(g.coords)[:-1]]  # noqa: E731
    out_polys = [[ring(sh.exterior)] + [ring(Polygon(h.exterior).exterior) for h in holes] for sh, holes in polys]
    ids_ = _Ids(sk)
    block = {"id": ids_("b"), "t": "block", "name": name, "polys": out_polys, "w0": round(max(xs) - x0, 6), "h0": round(max(ys) - y0, 6),
             "scale": 1, "at": [round(x0, 6), round(y0, 6)]}
    ents = [e for e in sk["entities"] if e["id"] not in used] + [block]
    alive = {e["id"] for e in ents}
    left = {q for e in ents for q in (e.get("a"), e.get("b"), e.get("c"), *(e.get("pts") or [])) if isinstance(q, str)}
    cons = [k for k in sk["constraints"] if all(x in alive for x in _ents_of(k)) and all(q == ORIGIN or q in left for q in _refs_of(k))]
    dims = [d for d in sk["dims"] if (not d.get("e") or d["e"] in alive) and all(not isinstance(d.get(x), str) or d[x] == ORIGIN or d[x] in left for x in ("a", "b"))]
    new = {"points": {k: v for k, v in sk["points"].items() if k in left}, "entities": ents, "constraints": cons, "dims": dims}
    dropped = len(sk["constraints"]) - len(cons) + len(sk["dims"]) - len(dims)
    return new, _report(sketch, new, before, dropped, tol, {"block": block["id"]})


# ------------------------------------------------------------------ 2D drawings
def naive_counts(drawing):
    """What the drawing gave as a sketch before the clean-up (each polyline side a line, ends joined when equal to
    5 decimals) — for the before / after report."""
    keys, ents = set(), 0
    k = lambda p: (round(p[0], 5), round(p[1], 5))  # noqa: E731
    for e in drawing.get("entities") or []:
        t = e.get("t")
        if t == "line":
            keys |= {k(e["a"]), k(e["b"])}
            ents += 1
        elif t == "circle":
            keys.add(k(e["c"]))
            ents += 1
        elif t == "arc":
            a0, a1 = math.radians(e["a0"]), math.radians(e["a1"])
            keys |= {k(e["c"]), k((e["c"][0] + e["r"] * math.cos(a0), e["c"][1] + e["r"] * math.sin(a0))),
                     k((e["c"][0] + e["r"] * math.cos(a1), e["c"][1] + e["r"] * math.sin(a1)))}
            ents += 1
        elif t == "poly":
            q = e["pts"] + ([e["pts"][0]] if e.get("closed") else [])
            keys |= {k(p) for p in q}
            ents += max(0, len(q) - 1)
    return {"points": len(keys), "entities": ents, "constraints": 0}


def from_drawing(drawing, tol=None):
    """A 2D drawing's shapes (texts left out) -> (sketch parts {points, entities, constraints, dims}, report)."""
    ents = [e for e in drawing.get("entities") or [] if e.get("t") in ("line", "arc", "circle", "poly")]
    allp = [p for e in ents for p in ([e["a"], e["b"]] if e["t"] == "line" else e.get("pts") or [])] + [
        [e["c"][0] + s * e["r"], e["c"][1] + s * e["r"]] for e in ents if e["t"] == "circle" for s in (-1, 1)] + [
        [e["c"][0] + e["r"] * math.cos(math.radians(e[k])), e["c"][1] + e["r"] * math.sin(math.radians(e[k]))] for e in ents if e["t"] == "arc" for k in ("a0", "a1")]
    tol = _tol(tol, _size_of(allp))
    nodes, pieces, circles = _Nodes(tol), [], []
    for i, e in enumerate(ents):
        t = e["t"]
        if t == "circle":
            if float(e.get("r") or 0) > tol:
                circles.append(e)
            continue
        if t == "line":
            p = Piece("line", V=[e["a"], e["b"]])
        elif t == "arc":
            a0 = math.radians(e["a0"])
            sw = math.radians(e["a1"] - e["a0"]) % (2 * math.pi)
            if sw <= 1e-12:
                sw = 2 * math.pi
            if abs(sw - 2 * math.pi) < 1e-9:
                circles.append({"c": e["c"], "r": e["r"]})
                continue
            p = Piece("arc", c=np.asarray(e["c"], float), r=float(e["r"]), a0=a0, sw=sw)
        else:
            V = list(e["pts"]) + ([e["pts"][0]] if e.get("closed") else [])
            if len(V) < 2:
                continue
            p = Piece("poly", V=V, smooth=bool(e.get("smooth")))
        p.ends = [nodes.add(("e", i, 0), p.end(0)), nodes.add(("e", i, 1), p.end(1))]
        pieces.append(p)
    nodes.weld()
    pieces, nodes = _absorb(pieces, nodes, tol)
    at = nodes.place()
    for p in pieces:
        p.ends = [nodes.find(k) for k in p.ends]
    pieces = [p for p in pieces if not (p.k == "line" and p.ends[0] == p.ends[1])]
    out = []
    for chain, closed in _chains(pieces, set()):
        out += _simplify_chain(chain, closed, tol, at)
    seen = []
    for e in circles:  # (the same circle twice: once)
        c, r = np.asarray(e["c"], float), float(e["r"])
        if any(math.hypot(*(c - c2)) <= tol and abs(r - r2) <= tol for c2, r2 in seen):
            continue
        seen.append((c, r))
        p = Piece("circle", c=c, r=r)
        p.ends = [None, None]
        out.append(p)
    new, _ = _rebuild_drawing(out, nodes, at, tol)
    before = naive_counts(drawing)
    try:
        from .. import drawing2d
        polys, _iss = drawing2d.outline_of({**drawing, "layers": [{**ly, "visible": True} for ly in drawing.get("layers") or []] or [{"name": e.get("layer"), "visible": True} for e in ents]})
        from shapely.geometry import Polygon
        a0 = float(sum(Polygon(p[0], p[1:]).area for p in polys))
    except Exception:  # noqa: BLE001 — no closed outline: nothing to compare
        a0 = 0.0
    a1 = region_area(new)
    issues = []
    if a0 > 1e-9 and abs(a1 - a0) > 0.005 * a0:
        issues.append({"severity": "warning", "code": "area_changed", "message": f"The enclosed area changed by {100 * (a1 - a0) / a0:+.2f} %.",
                       "params": {"before": a0, "after": a1}})
    return new, {"before": before, "after": _counts(new), "area": [round(a0, 6), round(a1, 6)], "dropped": 0, "tol": tol, "issues": issues}


def _rebuild_drawing(out, nodes, at, tol):
    """Pieces of a drawing -> sketch parts (all points new; a lone circle: just its centre)."""
    base = {"points": {}, "entities": [], "constraints": [], "dims": []}
    lone = [p for p in out if p.k == "circle" and p.ends == [None, None]]
    new, dropped = _rebuild(base, set(), [p for p in out if p not in lone], nodes, at, _Ids(base), tol)
    ids = _Ids(new)
    for p in lone:
        c = ids("p")
        new["points"][c] = [round(float(p.c[0]), 6), round(float(p.c[1]), 6)]
        new["entities"].append({"id": ids("c"), "t": "circle", "c": c, "r": round(float(p.r), 6)})
    return new, dropped
