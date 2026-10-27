"""ISO 286 fits — the deviations of the usual tolerance classes (holes H6 … H9, shafts f7 … p6) for nominal sizes up to
120 mm, and the ISO 2768 general tolerance classes — for the 2D drawing (a hole step's `fit`, a part's `tolerance`)."""
from __future__ import annotations

# the upper ends of the size ranges (mm): over 0 to 3, over 3 to 6 … over 80 to 120
RANGES = (3, 6, 10, 18, 30, 50, 80, 120)
# (upper, lower) deviations in µm, one pair per range
TABLE = {
    "H6": [(6, 0), (8, 0), (9, 0), (11, 0), (13, 0), (16, 0), (19, 0), (22, 0)],
    "H7": [(10, 0), (12, 0), (15, 0), (18, 0), (21, 0), (25, 0), (30, 0), (35, 0)],
    "H8": [(14, 0), (18, 0), (22, 0), (27, 0), (33, 0), (39, 0), (46, 0), (54, 0)],
    "H9": [(25, 0), (30, 0), (36, 0), (43, 0), (52, 0), (62, 0), (74, 0), (87, 0)],
    "f7": [(-6, -16), (-10, -22), (-13, -28), (-16, -34), (-20, -41), (-25, -50), (-30, -60), (-36, -71)],
    "g6": [(-2, -8), (-4, -12), (-5, -14), (-6, -17), (-7, -20), (-9, -25), (-10, -29), (-12, -34)],
    "h6": [(0, -6), (0, -8), (0, -9), (0, -11), (0, -13), (0, -16), (0, -19), (0, -22)],
    "k6": [(6, 0), (9, 1), (10, 1), (12, 1), (15, 2), (18, 2), (21, 2), (25, 3)],
    "m6": [(8, 2), (12, 4), (15, 6), (18, 7), (21, 8), (25, 9), (30, 11), (35, 13)],
    "p6": [(12, 6), (20, 12), (24, 15), (29, 18), (35, 22), (42, 26), (51, 32), (59, 37)],
}
HOLE_FITS = ("H6", "H7", "H8", "H9")
GENERAL = {"f": "fine", "m": "medium", "c": "coarse"}  # ISO 2768-1


def deviation(fit: str, d: float):
    """The (upper, lower) deviation in mm of a size `d` in tolerance class `fit`, or None (unknown class / size)."""
    rows = TABLE.get(str(fit))
    if not rows or not 0 < d <= RANGES[-1]:
        return None
    k = next(i for i, top in enumerate(RANGES) if d <= top)
    up, lo = rows[k]
    return up / 1000, lo / 1000


def label(d: float, fit: str) -> str:
    """'Ø8 H7 (+0.015 / 0)' — the size with its class and deviations (just 'Ø8 H7' when the size is out of the table)."""
    dev = deviation(fit, d)
    s = lambda v: "0" if v == 0 else f"{v:+.3f}".rstrip("0").rstrip(".")  # noqa: E731
    return f"Ø{d:g} {fit}" + (f" ({s(dev[0])} / {s(dev[1])})" if dev else "")
