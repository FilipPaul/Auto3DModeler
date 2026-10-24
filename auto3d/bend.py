"""Bending the flat part: folds (roof shapes, U / Z profiles) and rolls (arcs, tubes).

The part is modelled flat (2.5D); bends are applied last as a deformation of the
triangle mesh. Each bend is a cylindrical zone across the part:

    axis    'x' -> the part curves along x (fold line parallel to y); 'y' the other way
    pos     centre of the bend zone along that axis (flat model coordinates)
    angle   bend angle in degrees (> 0)
    radius  inner bend radius (model units); ignored for mode 'roll'
    toward  'front' (front face ends up inside the bend) or 'back'
    mode    'bend' | 'roll' (the whole length becomes one arc of `angle`)

Length is preserved on the neutral axis (mid-thickness), like real sheet bending.
The mesh is first split across the bend zone (one facet every few degrees) so the
curve is smooth; splitting is deterministic per edge, so the mesh stays watertight.
"""
from __future__ import annotations

import math

import numpy as np

FACET_DEG = 3.0  # angular resolution of bent zones


def _fmt(v: float) -> str:
    return f"{v:.3f}".rstrip("0").rstrip(".")


def plan_bends(bends, solid, unit):
    """Normalise and validate the user's bends. Returns (ops, axis, issues)."""
    issues = []
    active = [b for b in bends or [] if b.get("visible", True)]
    if not active:
        return [], None, issues
    axes = {b.get("axis", "x") for b in active}
    if len(axes) > 1:
        issues.append({"severity": "error", "code": "bend", "params": [],
                       "message": "All bends must run in the same direction (a flat sheet cannot be bent around two "
                                  "crossing axes) — change or hide one of them."})
        return [], None, issues
    axis = axes.pop()
    k = 0 if axis == "x" else 1
    x0, y0, x1, y1 = solid.xy_bounds()
    lo, hi = (x0, x1) if axis == "x" else (y0, y1)
    t = solid.t
    z_lo, z_hi = solid.z_range()
    ops = []
    for b in active:
        name = b.get("name") or "Bend"
        ang = float(b.get("angle") or 0)
        toward = b.get("toward", "front")

        def err(msg):
            issues.append({"severity": "error", "code": "bend", "params": [], "bend": b.get("id"),
                           "message": f"{name}: {msg}"})

        if not 0 < ang < 360:
            err("the angle must be between 0 and 360°.")
            continue
        theta = math.radians(ang)
        if b.get("mode") == "roll":
            length = hi - lo
            rn = length / theta
            r_in = rn - t / 2
            s, e = lo, hi
        else:
            r_in = float(b.get("radius") or 0)
            rn = r_in + t / 2
            length = theta * rn
            c = float(b.get("pos", (lo + hi) / 2))
            s, e = c - length / 2, c + length / 2
        # material on the inside of the bend must not fold through the centre
        inside = (z_hi - t) if toward == "front" else (-z_lo)  # embossed height on the inner face
        if r_in <= max(inside, 0) + 1e-9 or r_in <= 1e-6:
            need = max(inside, 0)
            err(f"the inner radius ({_fmt(r_in)} {unit}) is too small"
                + (f" — it must exceed the {_fmt(need)} {unit} embossed design on the inner face" if need > 0 else "")
                + (" (roll angle too large for this length/thickness)" if b.get("mode") == "roll" else "") + ".")
            continue
        if s < lo - 1e-9 or e > hi + 1e-9:
            err(f"the bend zone ({_fmt(s)}–{_fmt(e)} {unit}) runs past the end of the part — move it or use a "
                "smaller radius / angle.")
            continue
        ops.append({"s": s, "e": e, "theta": theta, "r": r_in, "rn": rn, "front": toward == "front",
                    "name": name, "id": b.get("id")})
    ops.sort(key=lambda o: o["s"])
    for a, b in zip(ops, ops[1:]):
        if b["s"] < a["e"] - 1e-9:
            issues.append({"severity": "error", "code": "bend", "params": [],
                           "message": f"{a['name']} and {b['name']} overlap — move them apart."})
            return [], axis, issues
    return ops, axis, issues


class Bender:
    """Maps flat (x, y, z) to bent coordinates for a sequence of bends along one axis."""

    def __init__(self, ops, axis, t):
        self.ops, self.axis, self.t = ops, axis, t
        self.k = 0 if axis == "x" else 1
        # walk along the axis, recording the frame (origin O at flat coord a, tangent T, normal N)
        a0 = ops[0]["s"]
        O, T, N = np.array([a0, 0.0]), np.array([1.0, 0.0]), np.array([0.0, 1.0])
        self.flat = [(-math.inf, a0, a0, O.copy(), T.copy(), N.copy())]  # (from, to, a_ref, O, T, N)
        self.zones = []
        for i, op in enumerate(ops):
            sgn = 1.0 if op["front"] else -1.0
            Os = O + (op["s"] - a0) * T
            C = Os + (t + op["r"]) * N if op["front"] else Os - op["r"] * N
            self.zones.append((op["s"], op["e"], C, T.copy(), N.copy(), sgn, op))
            th = op["theta"] * sgn
            T, N = _rot(T, th), _rot(N, th)
            O = C - (t + op["r"]) * N if op["front"] else C + op["r"] * N
            a0 = op["e"]
            nxt = ops[i + 1]["s"] if i + 1 < len(ops) else math.inf
            self.flat.append((op["e"], nxt, a0, O.copy(), T.copy(), N.copy()))
        self.total = sum(op["theta"] * (1 if op["front"] else -1) for op in ops)

    def tangent_angle(self, a):
        """Direction of the bent part at flat coordinate a (radians, + = towards the front)."""
        ang = 0.0
        for s, e, C, T, N, sgn, op in self.zones:
            if a >= e:
                ang += sgn * op["theta"]
            elif a > s:
                ang += sgn * (a - s) / op["rn"]
        return ang

    def planes(self):
        """Axis positions where the mesh must be split so bent zones are smooth."""
        out = []
        for s, e, *_ in self.zones:
            op = _[-1]
            n = max(2, math.ceil(math.degrees(op["theta"]) / FACET_DEG))
            out += [s + (e - s) * i / n for i in range(n + 1)]
        return sorted(set(out))

    def map(self, pts: np.ndarray) -> np.ndarray:
        """pts: (n, 3) flat coordinates -> bent coordinates."""
        a = pts[:, self.k]
        z = pts[:, 2]
        A = np.empty_like(a)
        Z = np.empty_like(z)
        done = np.zeros(len(a), bool)
        for s, e, C, T, N, sgn, op in self.zones:
            m = (a >= s) & (a <= e) & ~done
            if m.any():
                phi = (a[m] - s) / op["rn"] * sgn
                cs, sn = np.cos(phi), np.sin(phi)
                Nr = np.stack([N[0] * cs - N[1] * sn, N[0] * sn + N[1] * cs], axis=1)
                if op["front"]:
                    P = C - ((self.t + op["r"]) - z[m])[:, None] * Nr
                else:
                    P = C + (op["r"] + z[m])[:, None] * Nr
                A[m], Z[m] = P[:, 0], P[:, 1]
                done |= m
        for lo, hi, aref, O, T, N in self.flat:
            m = (a >= lo) & (a <= hi) & ~done
            if m.any():
                d = a[m] - aref
                A[m] = O[0] + d * T[0] + z[m] * N[0]
                Z[m] = O[1] + d * T[1] + z[m] * N[1]
                done |= m
        out = pts.copy()
        out[:, self.k] = A
        out[:, 2] = Z
        return out


def _rot(v, ang):
    c, s = math.cos(ang), math.sin(ang)
    return np.array([v[0] * c - v[1] * s, v[0] * s + v[1] * c])


# --------------------------------------------------------------------------- mesh
def _split_all(V, tags, planes, k):
    """Split triangles V (n, 3, 3) by every axis-plane x_k = c they straddle.

    Vectorised per plane. A crossing edge is always cut from its lower (along k) endpoint, so the two
    triangles sharing an edge get bit-identical new points and the mesh stays watertight.
    """
    eps = 1e-12
    for c in planes:
        d = V[:, :, k] - c
        sg = np.where(d < -eps, -1, np.where(d > eps, 1, 0))
        cross = (sg.min(axis=1) < 0) & (sg.max(axis=1) > 0)
        if not cross.any():
            continue
        Vc, sc, tc = V[cross], sg[cross], tags[cross]
        V, tags = V[~cross], tags[~cross]
        zero = sc == 0
        has_zero = zero.any(axis=1)
        lone_sign = -np.sign(sc.sum(axis=1))  # without zeros: the vertex whose sign differs
        special = np.where(has_zero, np.argmax(zero, axis=1), np.argmax(sc == lone_sign[:, None], axis=1))
        idx = (special[:, None] + np.arange(3)[None, :]) % 3
        R = np.take_along_axis(Vc, idx[:, :, None], axis=1)  # special vertex first, winding kept
        A, B, C = R[:, 0], R[:, 1], R[:, 2]

        def cut(P, Q):
            lo = np.where((P[:, k] < Q[:, k])[:, None], P, Q)
            hi = np.where((P[:, k] < Q[:, k])[:, None], Q, P)
            t = (c - lo[:, k]) / (hi[:, k] - lo[:, k])
            m = lo + t[:, None] * (hi - lo)
            m[:, k] = c
            return m

        z = has_zero
        new, new_tags = [], []
        if z.any():  # special vertex on the plane: two triangles
            a, b, cc = A[z], B[z], C[z]
            m = cut(b, cc)
            new += [np.stack([a, b, m], 1), np.stack([a, m, cc], 1)]
            new_tags += [tc[z], tc[z]]
        n = ~z
        if n.any():  # special vertex alone on its side: three triangles
            a, b, cc = A[n], B[n], C[n]
            m1, m2 = cut(a, b), cut(a, cc)
            new += [np.stack([a, m1, m2], 1), np.stack([m1, b, cc], 1), np.stack([m1, cc, m2], 1)]
            new_tags += [tc[n]] * 3
        V = np.concatenate([V] + new)
        tags = np.concatenate([tags] + new_tags)
    return V, tags


def deform(tris, tags, bender: Bender):
    """Split the mesh across the bend zones and map it to the bent shape.

    Returns (triangles, tags, place) where place(points) maps any further flat points (e.g. dimension
    labels) exactly like the mesh, including the final levelling / placement.
    """
    V = np.array(tris, dtype=float).reshape(-1, 3, 3)
    V, tg = _split_all(V, np.array(tags, dtype=np.uint8), bender.planes(), bender.k)
    pts = V.reshape(-1, 3)
    mapped = bender.map(pts)
    k = bender.k
    # level the result at its middle (a single roof / roll comes out symmetric), rest it on z = 0
    ang = -bender.tangent_angle((pts[:, k].min() + pts[:, k].max()) / 2)
    c, sn = math.cos(ang), math.sin(ang)
    ca, cz = (mapped[:, k].min() + mapped[:, k].max()) / 2, (mapped[:, 2].min() + mapped[:, 2].max()) / 2

    def level(P):
        P = P.copy()
        A, Z = P[:, k] - ca, P[:, 2] - cz
        P[:, k], P[:, 2] = ca + A * c - Z * sn, cz + A * sn + Z * c
        return P

    leveled = level(mapped)
    dz = -leveled[:, 2].min()
    da = (pts[:, k].min() + pts[:, k].max()) / 2 - (leveled[:, k].min() + leveled[:, k].max()) / 2

    def place(P):
        Q = level(bender.map(np.asarray(P, dtype=float).reshape(-1, 3)))
        Q[:, 2] += dz
        Q[:, k] += da
        return Q

    leveled[:, 2] += dz
    leveled[:, k] += da
    M = leveled.reshape(-1, 3, 3)
    return [tuple(map(tuple, t)) for t in M.tolist()], tg.tolist(), place


def bend_info(ops, unit):
    """Human-readable summary (derived radius for rolls, zone length)."""
    return [{"id": op["id"], "radius": op["r"], "length": op["e"] - op["s"], "start": op["s"], "end": op["e"]}
            for op in ops]


class BentSolid:
    """A solid after bending. Offers the subset of the Solid interface used by export/printing;
    faces are the (planar) mesh triangles, so STEP output is a faceted solid."""

    def __init__(self, tris, tags, t, issues=None):
        self._tris, self._tags, self.t = tris, tags, t
        self.issues = issues or []
        self.bent = True

    @classmethod
    def of(cls, solid, bender):
        tris, tags = solid.triangles()
        bt, bg, place = deform(tris, tags, bender)
        out = cls(bt, bg, solid.t, solid.issues)
        out.place = place
        return out

    def triangles(self):
        return self._tris, self._tags

    def _pts(self):
        return np.array([p for tri in self._tris for p in tri], dtype=float).reshape(-1, 3)

    def xy_bounds(self):
        p = self._pts()
        return (p[:, 0].min(), p[:, 1].min(), p[:, 0].max(), p[:, 1].max())

    def z_range(self):
        p = self._pts()
        return (p[:, 2].min(), p[:, 2].max())

    def volume(self):
        v = 0.0
        for a, b, c in self._tris:
            v += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0])
                  + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6
        return v

    def faces(self):
        for (a, b, c), tag in zip(self._tris, self._tags):
            u = np.subtract(b, a)
            w = np.subtract(c, a)
            n = np.cross(u, w)
            ln = np.linalg.norm(n)
            if ln < 1e-18:
                continue  # degenerate sliver, carries no area
            yield "wall", None, [[a, b, c], 3], tuple(n / ln), tag

    def _moved(self, fn):
        tris = [tuple(tuple(fn(p)) for p in tri) for tri in self._tris]
        return BentSolid(tris, self._tags, self.t)

    def at_origin(self):
        x0, y0, _, _ = self.xy_bounds()
        z0 = self.z_range()[0]
        return self._moved(lambda p: (p[0] - x0, p[1] - y0, p[2] - z0))

    def flipped(self):
        return self._moved(lambda p: (p[0], -p[1], -p[2]))


def bend_solid(solid, bends, unit):
    """Apply the bends to a Solid. Returns (solid_or_bent, bender_or_None, issues)."""
    ops, axis, issues = plan_bends(bends, solid, unit)
    if not ops or any(i["severity"] == "error" for i in issues):
        return solid, None, issues
    bender = Bender(ops, axis, solid.t)
    return BentSolid.of(solid, bender), bender, issues
