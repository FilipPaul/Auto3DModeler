"""🔌 Cable harnesses (the assembly's 🔌 Cable harness, web/js/assembly/harness.js): the route through the clicked
points shaped to the minimum bend radius — a polyline with each corner an arc of that radius (straight lines + arcs;
two corners too close for it moved apart along their outer legs; only a corner that nothing makes fit gets the
largest radius that does and is reported) —, its length, a bundle's outer Ø from its wires' circle packing, its ends
leaving their faces square and its detours round other bodies (leads, avoid), and the solid for STEP / GLB / the
drawing: a circle (one per wire, a ribbon's rectangle) swept along the route (kernel.pipe_body). The browser does the same math for its live preview.

A harness as a step of a part (an assembly's export makes one part per harness, placed where it is):
  {"id": "H1", "type": "harness", "kind": "cable" | "wires" | "ribbon" | "sleeve", "points": [[x, y, z], …] (the
   route's centre line), "d": Ø of a cable / sleeve, "wires": [{"d": 1.5, "color": "brown"}] (loose wires, a ribbon's
   count), "pitch": 1.27 (a ribbon's wire spacing), "r_min": 15, "length": 400 (🔒 its locked length: the slack sags,
   see shape), "spans": [{"from", "length"}] (➰ a span's own length), "still": [legs the slack leaves straight: the
   ends' leads]}
"""
import math

import numpy as np

from . import kernel as K

# the smallest circle round n equal circles of Ø 1 (packomania): n -> its Ø; up to 9 the wires lie as in harness.js
PACKING = {1: 1.0, 2: 2.0, 3: 1 + 2 / math.sqrt(3), 4: 1 + math.sqrt(2), 5: 1 + 1 / math.sin(math.pi / 5), 6: 3.0, 7: 3.0,
           8: 1 + 1 / math.sin(math.pi / 7), 9: 1 + 1 / math.sin(math.pi / 8)}
KINDS = ("cable", "wires", "ribbon", "sleeve")
EPS = 1e-9


def wire_layout(n, d):
    """n wires of Ø d side by side in a round bundle -> their centres [(x, y)] in its cross-section: one in the middle
    (7 … 9: one in the middle and a ring), a ring (3 … 6), two rings from 10 on."""
    n = max(1, int(n))
    ring = lambda k, r, a0=0.0: [(r * math.cos(a0 + 2 * math.pi * i / k), r * math.sin(a0 + 2 * math.pi * i / k)) for i in range(k)]  # noqa: E731
    if n == 1:
        return [(0.0, 0.0)]
    if n == 2:
        return [(-d / 2, 0.0), (d / 2, 0.0)]
    if n <= 6:
        return ring(n, d / (2 * math.sin(math.pi / n)))
    if n <= 9:
        return [(0.0, 0.0)] + ring(n - 1, max(d, d / (2 * math.sin(math.pi / (n - 1)))))
    m = max(3, round(n / 3.2))
    ri = d / (2 * math.sin(math.pi / m))
    ro = max(ri + d, d / (2 * math.sin(math.pi / (n - m))))
    return ring(m, ri) + ring(n - m, ro, math.pi / (n - m))


def bundle_d(n, d):
    """The outer Ø of n wires of Ø d laid in a round bundle: 1, 3, 7 wires -> 1, 2.155, 3 × d."""
    n = max(1, int(n))
    if n in PACKING:
        return PACKING[n] * d
    return 2 * max(math.hypot(x, y) for x, y in wire_layout(n, d)) + d


def outer_d(f):
    """A harness's outer size: Ø of a cable / sleeve, of a bundle of wires; a ribbon: its width."""
    kind, wires = f.get("kind") or "cable", f.get("wires") or []
    if kind == "wires":
        return bundle_d(len(wires) or 1, max([float(w.get("d") or 1.5) for w in wires] or [1.5]))
    if kind == "ribbon":
        return max(1, len(wires)) * float(f.get("pitch") or 1.27)
    return float(f.get("d") or 6)


def _fit(P, r_min):
    """The corners of the polyline P rounded with r_min where its legs leave room, else with the largest radius that
    fits (a leg shared by two corners split by what each wants) -> (L, U, turn, want, T: how far each corner's arc
    reaches along its legs, R: its radius)."""
    L = [float(np.linalg.norm(P[k + 1] - P[k])) for k in range(len(P) - 1)]
    U = [(P[k + 1] - P[k]) / L[k] for k in range(len(P) - 1)]
    turn = [0.0] + [math.acos(max(-1.0, min(1.0, float(U[i - 1] @ U[i])))) for i in range(1, len(P) - 1)] + [0.0]
    want = [r_min * math.tan(a / 2) if a > 1e-9 and a < math.pi - 1e-9 else (math.inf if a >= math.pi - 1e-9 else 0.0) for a in turn]

    def room(i, k):  # how much of segment k corner i may take (corner i is one of its two ends)
        j = k + 1 if i == k else k  # the other end
        a, b = want[i], want[j]
        if b <= 0 or a + b <= L[k]:
            return L[k] if b <= 0 else min(a, L[k])
        return L[k] * (a / (a + b)) if math.isfinite(a + b) else (L[k] / 2 if math.isinf(a) and math.isinf(b) else (L[k] if math.isinf(a) else 0.0))

    T, R = [0.0] * len(P), [0.0] * len(P)
    for i in range(1, len(P) - 1):
        if turn[i] > 1e-9:
            T[i] = min(want[i], room(i, i - 1), room(i, i))
            R[i] = T[i] / math.tan(turn[i] / 2) if turn[i] < math.pi - 1e-9 else 0.0
    return L, U, turn, want, T, R


def _spread(P, r_min):
    """Two corners too close for r_min (the leg between them too short for both arcs: an S or a double bend) moved
    apart along their outer legs — the middle leg longer, both arcs r_min — as little as that needs and as far as the
    corners beyond leave room; when no move makes them fit, the move that bends them least tight (a U turn: none, its
    radius is half the gap whatever). The ends stay. -> the points the arcs are fitted to."""
    P = [p.copy() for p in P]
    tight = r_min * (1 - 1e-6)
    for i in range(1, len(P) - 2):
        L, U, turn, want, T, R = _fit(P, r_min)
        if not (1e-9 < turn[i] < math.pi - 1e-9 and 1e-9 < turn[i + 1] < math.pi - 1e-9) or min(R[i], R[i + 1]) >= tight:
            continue
        if T[i] + T[i + 1] < L[i] * (1 - 1e-9):  # (not the leg between them that is short)
            continue
        smax = min(L[i - 1] - (want[i - 1] if i > 1 else 0.0), L[i + 1] - (want[i + 2] if i + 2 < len(P) - 1 else 0.0)) * (1 - 1e-9)
        if not smax > 1e-9:
            continue
        a0, b0, ua, ub = P[i].copy(), P[i + 1].copy(), U[i - 1], U[i + 1]

        def worst(s):  # the tighter of the two arcs with both corners moved s apart
            Q = list(P)
            Q[i], Q[i + 1] = a0 - ua * s, b0 + ub * s
            R2 = _fit(Q, r_min)[5]
            return min(R2[i], R2[i + 1])

        n = 32
        f = [worst(smax * k / n) for k in range(n + 1)]
        k = next((k for k in range(1, n + 1) if f[k] >= tight), None)
        if k is not None:  # the least move that fits, bisected (to where both arcs are r_min to the last digits)
            lo, hi = smax * (k - 1) / n, smax * k / n
            for _ in range(60):
                mid = (lo + hi) / 2
                lo, hi = (lo, mid) if worst(mid) >= r_min * (1 - 1e-13) else (mid, hi)
            s = hi
        else:
            k = max(range(n + 1), key=lambda k: f[k])
            s = smax * k / n if f[k] > f[0] * (1 + 1e-3) else 0.0
        P[i], P[i + 1] = a0 - ua * s, b0 + ub * s
    return P


def route(points, r_min):
    """The route through `points` ([x, y, z] each), shaped to the minimum bend radius: each corner an arc of r_min
    tangent to both legs; two corners too close for that moved apart along their outer legs until they fit (_spread);
    only where nothing fits (a short end leg, a U turn narrower than 2 × r_min) the largest radius that does — reported
    -> {"segments": [("line", a, b) | ("arc", a, m, b, centre, r, angle)], "length", "bends": [{"at": corner index,
    "r", "ok", "angle" (degrees turned)}]}."""
    P = [np.asarray(p, float) for p in points]
    P = [p for k, p in enumerate(P) if k == 0 or np.linalg.norm(p - P[k - 1]) > 1e-6]  # (a point twice: once)
    if len(P) < 2:
        return {"segments": [], "length": 0.0, "bends": [], "start": None}
    r_min = max(0.0, float(r_min or 0))
    if r_min > 0:
        P = _spread(P, r_min)
    L, U, turn, want, Ts, Rs = _fit(P, r_min)
    segs, bends, at, length, station = [], [], P[0], 0.0, [0.0] * len(P)
    for i in range(1, len(P) - 1):
        a = turn[i]
        if a <= 1e-9:
            station[i] = length + float(np.linalg.norm(P[i] - at))
            continue
        T, r = Ts[i], Rs[i]
        ok = r >= r_min * 0.97  # (3 % under it: within what a bend of a cable is made to — not worth a note)
        bends.append({"at": i, "r": r, "ok": ok, "angle": math.degrees(a)})
        A, B = P[i] - U[i - 1] * T, P[i] + U[i] * T
        if np.linalg.norm(A - at) > 1e-9:
            segs.append(("line", at, A))
            length += float(np.linalg.norm(A - at))
        station[i] = length + r * a / 2  # (a corner's place along the cable: its arc's middle)
        if r > 1e-9:
            w = U[i] - U[i - 1]
            w /= np.linalg.norm(w)
            c = P[i] + w * (r / math.cos(a / 2))
            m = c + (P[i] - c) / np.linalg.norm(P[i] - c) * r
            segs.append(("arc", A, m, B, c, r, a))
            length += r * a
        at = B
    if np.linalg.norm(P[-1] - at) > 1e-9:
        segs.append(("line", at, P[-1]))
        length += float(np.linalg.norm(P[-1] - at))
    station[-1] = length
    return {"segments": segs, "length": length, "bends": bends, "start": U[0], "station": station}


def _sag(a, b, before=None, after=None):
    """Which way a span's slack bows (square to it): out of the corners at its ends — the way the cable comes in
    (before: the leg before it), away from where it goes on (after: the leg after it) —, so the bow leaves its ends
    without a sharp turn; its corners turning opposite ways (an S: out of one is into the other), square to their
    plane, the downward side; with little of that (an end span, a straight run), down (−z) as it hangs; a vertical span
    with nothing to go by: along x."""
    u = (b - a) / np.linalg.norm(b - a)
    sq = lambda g: g - (g @ u) * u  # noqa: E731  (the part of g square to the span)
    n = np.zeros(3)
    if before is not None:
        n += sq(before / np.linalg.norm(before))
    if after is not None:
        n -= sq(after / np.linalg.norm(after))
    if before is not None and after is not None and np.linalg.norm(n) < 0.5 and np.linalg.norm(sq(before / np.linalg.norm(before))) > 0.5:
        side = np.cross(u, sq(before / np.linalg.norm(before)))
        if np.linalg.norm(side) > 1e-6:
            side /= np.linalg.norm(side)
            return -side if side[2] > 0 else side
    n += 0.25 * sq(np.array([0, 0, -1.0]))
    if np.linalg.norm(n) > 0.05:
        return n / np.linalg.norm(n)
    for g in (np.array([0, 0, -1.0]), np.array([1.0, 0, 0]), np.array([0, 1.0, 0])):
        n = sq(g)
        if np.linalg.norm(n) > 1e-3:
            return n / np.linalg.norm(n)


def _bowed(P, h, r_min):
    """The points with each span k bowed h[k] mm (0: straight): two points put in, in the middle of its straight part
    (between the arcs of its end corners) ± a quarter of that + h / 2 (no more than r_min: a deep loop on a short span
    reaches out past it) and h off it the way it hangs (_sag) — a flat-bottomed bow the corners round at r_min; a
    shallow bow leaves the end corners as they were (its length grows smoothly with h) -> (points, where each point of
    P went)."""
    out, where = [P[0]], [0]
    T = _fit(P, r_min)[4] if r_min > 0 and len(P) > 2 else [0.0] * len(P)
    for k in range(len(P) - 1):
        a, b = P[k], P[k + 1]
        if h[k] > 1e-9:
            L, n = float(np.linalg.norm(b - a)), _sag(a, b, P[k] - P[k - 1] if k > 0 else None, P[k + 2] - P[k + 1] if k + 2 < len(P) else None)
            s0, s1 = (T[k], L - T[k + 1]) if L - T[k] - T[k + 1] > 1e-6 else (0.0, L)  # (its straight part)
            m, f = (s0 + s1) / 2, s1 - s0
            u, w = (b - a) / L, min(r_min, f / 4 + h[k] / 2) if r_min > 0 else f / 4
            out += [a + u * (m - w) + n * h[k], a + u * (m + w) + n * h[k]]
        out.append(b)
        where.append(len(out) - 1)
    return out, where


def shape(points, r_min, spans=None, total=None, still=()):
    """The route with slack: a span (the cable between points k and k + 1) given its own length gets a bow that hangs
    the way gravity pulls (_bowed), as deep as makes it that long (its length: from corner to corner, each corner's
    place the middle of its arc — they add up to the whole); the whole cable given a length (total) bows all its spans
    alike (each as deep as it is long) — the spans' own lengths win when both are given. Too short for its ends: the
    span (the cable) straight, taut, reported with how much it is short.
    spans: {k: length}; still: legs the whole cable's slack leaves straight (an end's lead) -> route(…) + {"spans":
    [length of each span], "taut": [{"span": k | None, "short": mm}],
    "total_ignored": spans and total both given}."""
    P = [np.asarray(p, float) for p in points]
    keep = [k for k, p in enumerate(P) if k == 0 or np.linalg.norm(p - P[k - 1]) > 1e-6]
    P = [P[k] for k in keep]
    r_min = max(0.0, float(r_min or 0))
    if len(P) < 2:
        return dict(route(P, r_min), spans=[], taut=[], total_ignored=False)
    want = {keep.index(k): float(v) for k, v in (spans or {}).items() if k in keep and keep.index(k) < len(P) - 1 and v and float(v) > 0}

    def run(h):
        Q, where = _bowed(P, h, r_min)
        r = route(Q, r_min)
        st = r.get("station") or [0.0] * len(Q)
        r["spans"] = [st[where[k + 1]] - st[where[k]] for k in range(len(P) - 1)] if len(Q) > 1 else []
        r["where"] = where
        return r

    h, taut = [0.0] * max(0, len(P) - 1), []
    if len(P) >= 2 and want:
        base = run(h)["spans"]
        for k, v in want.items():
            if base[k] > v + 0.5:
                taut.append({"span": keep[k], "short": base[k] - v})
        for _ in range(4):  # (a span's bow turns its ends' corners, the next span's length with them: again)
            for k, v in want.items():
                if base[k] > v + 0.5:
                    continue
                h[k] = _solve(lambda x: run(h[:k] + [x] + h[k + 1:])["spans"][k], v, float(np.linalg.norm(P[k + 1] - P[k])))
    elif len(P) >= 2 and total and float(total) > 0:
        legs = [0.0 if k in still else float(np.linalg.norm(P[k + 1] - P[k])) for k in range(len(P) - 1)]
        L0 = run(h)["length"]
        if L0 > float(total) + 0.5:
            taut.append({"span": None, "short": L0 - float(total)})
        else:
            lam = _solve(lambda x: run([x * g for g in legs])["length"], float(total), 1.0)
            h = [lam * g for g in legs]
    r = run(h)
    r["bends"] = [dict(b, at=keep[max(i for i, w in enumerate(r["where"]) if w <= b["at"])]) for b in r["bends"]]
    r["taut"], r["total_ignored"] = taut, bool(want and total)
    return r


def _solve(f, target, scale):
    """The x ≥ 0 that makes f(x) = target (f growing from f(0) ≤ target): doubled until past it, then bisected."""
    lo, hi = 0.0, max(scale, 1e-3) * 0.05
    for _ in range(60):
        if f(hi) >= target:
            break
        lo, hi = hi, hi * 2
    for _ in range(50):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if f(mid) < target else (lo, mid)
        if hi - lo < 1e-6 * scale:
            break
    return (lo + hi) / 2


def leads(points, normals=None, r_min=0.0, d=0.0):
    """An end of the cable on a face leaves it square: a point out along that face's normal (normals: one per point,
    None where it is not on a face) put in after the first point / before the last, as far out as the bend towards the
    next point needs at r_min (lead_of) -> (points, where each given point went)."""
    P = [np.asarray(p, float) for p in points]
    out, where = list(P), list(range(len(P)))
    if len(P) < 2 or not normals:
        return out, where
    n0, n1 = normals[0], normals[-1]
    if n1 is not None and np.linalg.norm(n1) > 1e-9:
        n = np.asarray(n1, float) / np.linalg.norm(n1)
        out.insert(len(out) - 1, P[-1] + n * lead_of(r_min, d, P[-1], n, P[-2]))
        where[-1] += 1
    if n0 is not None and np.linalg.norm(n0) > 1e-9:
        n = np.asarray(n0, float) / np.linalg.norm(n0)
        out.insert(1, P[0] + n * lead_of(r_min, d, P[0], n, P[1]))
        where = [0] + [w + 1 for w in where[1:]]
    return out, where


def lead_of(r_min, d, p=None, n=None, nxt=None):
    """How far an end goes straight out of its face (at p, its normal n) before it bends towards nxt: room for that
    bend at r_min (r_min · tan of half its turn, the turn at most 160°; at least a right angle's), + Ø."""
    r_min, d = float(r_min or 0), float(d)
    L = max(r_min, d) + d
    if p is None or nxt is None:
        return L
    for _ in range(3):  # (further out, the turn towards nxt changes a little: again)
        v = np.asarray(nxt, float) - (p + n * L)
        if np.linalg.norm(v) < 1e-9:
            break
        turn = math.acos(max(-1.0, min(1.0, float(n @ v / np.linalg.norm(v)))))
        L = max(max(r_min, d), r_min * math.tan(min(turn, math.radians(160)) / 2)) + d
    return L


def samples(r, step):
    """Points every ~step mm along a route's segments -> [np.array]."""
    out = []
    for s in r["segments"]:
        a = np.asarray(s[1], float)
        if s[0] == "line":
            b = np.asarray(s[2], float)
            n = max(1, int(math.ceil(np.linalg.norm(b - a) / step)))
            out += [a + (b - a) * (k / n) for k in range(n)]
        else:
            c, rad, ang, b = np.asarray(s[4], float), s[5], s[6], np.asarray(s[3], float)
            x = (a - c) / rad
            y = (b - c) - ((b - c) @ x) * x
            y /= np.linalg.norm(y)
            n = max(2, int(math.ceil(rad * ang / step)))
            out += [c + rad * (x * math.cos(ang * k / n) + y * math.sin(ang * k / n)) for k in range(n)]
    if r["segments"]:
        last = r["segments"][-1]
        out.append(np.asarray(last[3] if last[0] == "arc" else last[2], float))
    return out


def _leg_of(E, p):
    """The leg of the polyline E nearest to p (its index: from E[k] to E[k + 1])."""
    best, bd = 0, math.inf
    for k in range(len(E) - 1):
        a, b = E[k], E[k + 1]
        ab = b - a
        t = 0.0 if ab @ ab < 1e-12 else max(0.0, min(1.0, float((p - a) @ ab / (ab @ ab))))
        dd = float(np.linalg.norm(a + ab * t - p))
        if dd < bd:
            best, bd = k, dd
    return best


def avoid(points, r_min, d, probe, normals=None, spans=None, total=None, clear=0.5, rounds=6):
    """The route kept clear of the other bodies: the ends on a face leave it square (leads), then the shaped route
    sampled and every sample too near a body (probe(p, rad) -> how far and which way to move p so that a tube of
    radius rad there is clear, or None) pushed out: for each leg the deepest one becomes a point of its own, the
    route shaped again — a few rounds. The clicked points stay as they are (anchors). A span with its own length that
    gets a point put in keeps none (said in "dropped"). -> shape(…) of the points + {"points": the points it runs
    through, "where": where each given point went, "clashes": [spots still too near], "spans" per given span,
    "dropped": [spans whose own length could not be kept]}."""
    rad = float(d) / 2 + clear
    E, where = leads(points, normals, r_min, d)
    detour = [False] * len(E)  # (the points put in round a body: they may move further out)

    def hits(r):
        out = []
        for p in samples(r, max(0.5, rad / 3)):
            push = probe(p, float(d) / 2 + clear / 2)  # (lying on a face, Ø/2 + clear off it, is fine: only nearer than Ø/2 + clear/2 counts)
            if push is not None and np.linalg.norm(push) > 1e-9:
                out.append((p, np.asarray(push, float)))
        return out

    for _ in range(rounds):
        r = shape(E, r_min)  # (round the bodies as it runs taut: a locked length's slack then sags in the room left)
        best = {}
        for p, push in hits(r):
            k = _leg_of(E, p)
            if any(where[j] <= k < where[j + 1] for j in (spans or {}) if j + 1 < len(where)):
                continue  # (a leg of a span with its own length: that length wins, a hit there is told)
            if k not in best or np.linalg.norm(push) > np.linalg.norm(best[k][1]):
                best[k] = (p, push)
        if not best:
            break
        for k in sorted(best, reverse=True):
            p, push = best[k]
            out = push / np.linalg.norm(push) * (np.linalg.norm(push) + rad / 2)  # (half a radius to spare: the arcs cut in)
            near = [j for j in (k, k + 1) if detour[j] and np.linalg.norm(E[j] - p) < 2 * r_min + rad]
            if near:  # (by a detour point of its own: that one further out — one corner round the body, not a cluster)
                j = min(near, key=lambda j: np.linalg.norm(E[j] - p))
                E[j] = E[j] + out
                continue
            E.insert(k + 1, p + out)
            detour.insert(k + 1, True)
            where = [w + 1 if w > k else w for w in where]
    still = ([0] if normals and normals[0] is not None else []) + ([len(E) - 2] if normals and normals[-1] is not None else [])
    leg_of, own = {}, {}
    for k, v in (spans or {}).items():  # (a span of several legs — a lead in it: its slack on its longest other leg)
        legs = [j for j in range(where[k], where[k + 1]) if j not in still] if k + 1 < len(where) else []
        if legs:
            leg_of[k] = max(legs, key=lambda j: np.linalg.norm(E[j + 1] - E[j]))
            own[leg_of[k]] = float(v)
    r = shape(E, r_min, own, total, still)  # (its leads stay straight)
    for _ in range(4):  # (that leg's length set so that the whole span is its length: its other legs' share taken off)
        off = 0
        for k, j in leg_of.items():
            dl = float(spans[k]) - sum(r["spans"][where[k]:where[k + 1]])
            if abs(dl) > 0.05 and own[j] + dl > 0 and not any(t["span"] == j for t in r["taut"]):
                own[j] += dl
                off += 1
        if not off:
            break
        r = shape(E, r_min, own, total, still)
    back = lambda i: max(k for k, w in enumerate(where) if w <= i)  # noqa: E731  (a point of E -> the given point before it)
    r["bends"] = [dict(b, at=back(b["at"])) for b in r["bends"]]
    r["taut"] = [dict(t, span=None if t["span"] is None else back(t["span"])) for t in r["taut"]]
    r["points"], r["where"] = E, where
    r["clashes"] = [p for p, _ in hits(r)]
    r["spans"] = [sum(r["spans"][where[k]:where[k + 1]]) for k in range(len(where) - 1)] if len(E) > 1 else []
    r["dropped"] = [k for k in (spans or {}) if k not in leg_of]
    r["own"] = own
    r["detours"] = sum(detour)
    return r


def _start_frame(t):
    """The route's first direction t and two directions across it (x: the most level one)."""
    x = np.cross(t, [0, 0, 1.0])
    if np.linalg.norm(x) < 1e-6:
        x = np.cross(t, [1.0, 0, 0])
    x /= np.linalg.norm(x)
    return t, x, np.cross(t, x)


def solid(f, fid):
    """A harness step -> its body: a cable / sleeve one round solid, loose wires one per wire side by side, a ribbon a
    flat one (its width along the most level direction across the route at its start)."""
    kind = f.get("kind") or "cable"
    if kind not in KINDS:
        raise K.KernelError("A harness is a cable, loose wires, a ribbon cable or a sleeve.")
    pts = f.get("points") or []
    if len(pts) < 2:
        raise K.KernelError("A harness needs at least two points.")
    spans = {int(s["from"]): float(s["length"]) for s in f.get("spans") or [] if s.get("length")}
    r = shape(pts, f.get("r_min") or 0, spans, f.get("length"), f.get("still") or ())
    if any(b["r"] <= 1e-9 for b in r["bends"]):
        raise K.KernelError("The harness turns back on itself at a point — move that point.")
    if not r["segments"] or r["length"] < 1e-6:
        raise K.KernelError("A harness needs at least two points.")
    a0 = np.asarray(r["segments"][0][1], float)
    t, x, y = _start_frame(r["start"])
    wires = f.get("wires") or []
    if kind == "wires":
        n, dw = max(1, len(wires)), max([float(w.get("d") or 1.5) for w in wires] or [1.5])
        profiles = [("circle", a0 + x * u + y * v, t, float((wires[k] if k < len(wires) else {}).get("d") or dw) / 2)
                    for k, (u, v) in enumerate(wire_layout(n, dw))]
    elif kind == "ribbon":
        w, h = outer_d(f), max(0.3, float(f.get("d") or 1.0))
        profiles = [("rect", a0, t, x, w, h)]
    else:
        d = float(f.get("d") or 0)
        if d <= 0:
            raise K.KernelError("The cable's Ø must be more than 0.")
        profiles = [("circle", a0, t, d / 2)]
    if any(b["r"] < outer_d(f) / 2 for b in r["bends"]):
        raise K.KernelError("A bend of the harness is tighter than half its Ø — it cannot be made solid; spread the points out.")
    return K.pipe_body([s[:4] if s[0] == "arc" else s for s in r["segments"]], profiles, fid)
