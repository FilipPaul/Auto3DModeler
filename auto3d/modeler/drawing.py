"""A 2D drawing of a model part (PDF, A4 landscape): three views — front, top and right — with the visible edges
(solid) and the hidden ones (dashed), an iso view, the overall sizes dimensioned, the round faces listed (Ø; a hole
with a fit as "Ø8 H7", its deviations in the title block), the general tolerance (ISO 2768) and a title block. The views come from the kernel's hidden-line removal (kernel.project_edges, in the worker); drawn with
PyMuPDF.
"""
from __future__ import annotations

import datetime as _dt
import math

import numpy as np

from . import fits as FITS
from . import kernel as K

MM = 72 / 25.4  # PDF points per mm
SCALES = [(5, 1), (2, 1), (1, 1), (1, 2), (1, 5), (1, 10), (1, 20), (1, 50)]
VIEWS = {  # (looking along, the drawing's right, the drawing's up) — first-angle names in the title block
    "Front": ((0, 1, 0), (1, 0, 0), (0, 0, 1)),
    "Top": ((0, 0, -1), (1, 0, 0), (0, 1, 0)),
    "Right": ((-1, 0, 0), (0, 1, 0), (0, 0, 1)),
}


def _project(shape, look, right, up):
    return K.project_edges(shape, look, right, up)


def _iso(shape):
    v, _ = _project(shape, (-1, 1, -1), (1 / math.sqrt(2), 1 / math.sqrt(2), 0), (0, 0, 1))
    return v


def _extent(polys):
    pts = [p for pl in polys for p in pl]
    if not pts:
        return 0, 0, 1, 1
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _round_faces(body):
    """The cylinders of the part -> ({diameter: how many}, [(diameter, centre x, centre y)] of those upright)."""
    out, upright, seen = {}, [], set()
    for f in K.tessellate(body)["faces"]:
        if f.get("type") != "cylinder" or not f.get("radius"):
            continue
        d = round(2 * f["radius"], 3)
        ax = f.get("axis") or {}
        o, v = ax.get("o"), ax.get("d") or [0, 0, 0]
        key = (d, round(o[0], 3), round(o[1], 3)) if o and abs(abs(v[2]) - 1) < 1e-6 else None
        if key and key in seen:  # a cylinder split in two halves: once
            continue
        out[d] = out.get(d, 0) + 1
        if key:
            seen.add(key)
            upright.append(key)
    return dict(sorted(out.items())), sorted(upright, key=lambda q: (q[2], q[1]))


def pdf(body, name="part", material="PLA", mass_g=None, fits=None, tolerance=None):
    """fits: {diameter: "H7"} (the holes with a fit), tolerance: "f" | "m" | "c" (ISO 2768) or None."""
    import fitz

    shape = body.shape
    bb = K.bbox(shape)
    size = (bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2])
    views = {k: _project(shape, *v) for k, v in VIEWS.items()}
    iso = _iso(shape)

    page_w, page_h = 297 * MM, 210 * MM
    doc = fitz.open()
    page = doc.new_page(width=page_w, height=page_h)
    margin, title_h = 10 * MM, 27 * MM
    fits = {round(float(d), 3): f for d, f in (fits or {}).items() if f}
    fit_of = lambda d: fits.get(round(d, 3))  # noqa: E731
    # the sheet: front top-left, right beside it, top below the front (labelled), iso bottom-right
    cell_w, cell_h = (page_w - 2 * margin) / 2, (page_h - 2 * margin - title_h) / 2
    need_w = max(size[0] + size[1], 1)
    need_h = max(size[2] + size[1], 1)
    scale = next(((a, b) for a, b in SCALES if a / b * need_w * MM <= (page_w - 2 * margin) * 0.7
                  and a / b * need_h * MM <= (page_h - 2 * margin - title_h) * 0.7), SCALES[-1])
    k = scale[0] / scale[1] * MM

    def draw_view(polys, hidden, cx, cy, label, dims=None, notes=None):
        x0, y0, x1, y1 = _extent(polys + hidden)
        ox, oy = cx - (x0 + x1) / 2 * k, cy + (y0 + y1) / 2 * k
        P = lambda p: fitz.Point(ox + p[0] * k, oy - p[1] * k)  # noqa: E731
        for pl in hidden:
            page.draw_polyline([P(p) for p in pl], color=(0.45, 0.45, 0.45), width=0.35, dashes="[2 1.5] 0")
        for pl in polys:
            page.draw_polyline([P(p) for p in pl], color=(0, 0, 0), width=0.7)
        page.insert_text(fitz.Point(cx - len(label) * 2.4, oy - y0 * k + 44), label, fontsize=9, color=(0.2, 0.2, 0.6))
        for (a, b, value, side) in dims or []:
            _dimension(page, P(a), P(b), value, side)
        for (at, r, text) in notes or []:
            q = P(at)
            page.insert_text(fitz.Point(q.x + r * k * 0.75 + 2, q.y - r * k * 0.75 - 2), text, fontsize=7, color=(0.15, 0.3, 0.6))

    fx, fy = margin + cell_w / 2, margin + cell_h / 2
    fv, fh = views["Front"]
    x0, y0, x1, y1 = _extent(fv + fh)
    draw_view(fv, fh, fx, fy, "Front", [((x0, y0), (x1, y0), size[0], "below"), ((x1, y0), (x1, y1), size[2], "right")])
    rv, rh = views["Right"]
    rx0, ry0, rx1, ry1 = _extent(rv + rh)
    draw_view(rv, rh, margin + cell_w * 1.5, fy, "Right", [((rx0, ry0), (rx1, ry0), size[1], "below")])
    rounds, upright = _round_faces(body)
    tv, th = views["Top"]
    tx0, ty0, tx1, ty1 = _extent(tv + th)
    draw_view(tv, th, fx, margin + cell_h * 1.5, "Top", [((tx1, ty0), (tx1, ty1), size[1], "right")],
              [((x, y), d / 2, f"Ø{d:g} {fit_of(d)}" if fit_of(d) else f"Ø{d:g}") for d, x, y in upright[:20]])
    if iso:
        ix0, iy0, ix1, iy1 = _extent(iso)
        ki = min(cell_w * 0.6 / max(ix1 - ix0, 1e-6), cell_h * 0.6 / max(iy1 - iy0, 1e-6))
        cx, cy = margin + cell_w * 1.5, margin + cell_h * 1.5
        for pl in iso:
            page.draw_polyline([fitz.Point(cx + (p[0] - (ix0 + ix1) / 2) * ki, cy - (p[1] - (iy0 + iy1) / 2) * ki) for p in pl], color=(0.25, 0.25, 0.25), width=0.5)

    # the title block
    tx, ty = margin, page_h - margin - title_h
    page.draw_rect(fitz.Rect(tx, ty, page_w - margin, page_h - margin), color=(0, 0, 0), width=0.8)
    lines = [f"{name}", f"Size {size[0]:.6g} × {size[1]:.6g} × {size[2]:.6g} mm   Material {material}" + (f"   Mass {mass_g:.1f} g" if mass_g else ""),
             "Round: " + (", ".join(f"Ø{d:g}" + (f" {fit_of(d)}" if fit_of(d) else "") + (f" ×{n}" if n > 1 else "") for d, n in rounds.items()) if rounds else "—")
             + ("   Holes from the lower-left (x, y): " + ", ".join(f"({x - bb[0]:.4g}, {y - bb[1]:.4g})" for _, x, y in upright[:8])
                + (" …" if len(upright) > 8 else "") if upright else "")]
    page.insert_text(fitz.Point(tx + 4 * MM, ty + 7 * MM), lines[0], fontsize=13)
    page.insert_text(fitz.Point(tx + 4 * MM, ty + 13 * MM), lines[1], fontsize=9)
    page.insert_text(fitz.Point(tx + 4 * MM, ty + 18 * MM), lines[2], fontsize=9)
    fitted = [FITS.label(d, f) for d, f in sorted(fits.items()) if d in rounds]
    tol = f"General tolerances ISO 2768-{tolerance} ({FITS.GENERAL[tolerance]})" if tolerance in FITS.GENERAL else ""
    if fitted or tol:
        page.insert_text(fitz.Point(tx + 4 * MM, ty + 23 * MM), "   ".join(x for x in (("Fits: " + ", ".join(fitted)) if fitted else "", tol) if x), fontsize=9)
    page.insert_text(fitz.Point(page_w - margin - 70 * MM, ty + 7 * MM), f"Scale {scale[0]}:{scale[1]}   Units mm", fontsize=9)
    page.insert_text(fitz.Point(page_w - margin - 70 * MM, ty + 13 * MM), f"{_dt.date.today().isoformat()}   Auto3DModeler", fontsize=9)
    page.insert_text(fitz.Point(page_w - margin - 70 * MM, ty + 18 * MM), "Hidden edges dashed", fontsize=8, color=(0.4, 0.4, 0.4))
    data = doc.tobytes()
    doc.close()
    return data


def _dimension(page, a, b, value, side):
    """A dimension line beside the edge a–b (side "below" or "right"), with arrows and the value."""
    import fitz
    off = 8 * MM
    if side == "below":
        a2, b2 = fitz.Point(a.x, a.y + off), fitz.Point(b.x, b.y + off)
    else:
        a2, b2 = fitz.Point(a.x + off, a.y), fitz.Point(b.x + off, b.y)
    grey = (0.15, 0.3, 0.6)
    page.draw_line(a, a2, color=grey, width=0.3)
    page.draw_line(b, b2, color=grey, width=0.3)
    page.draw_line(a2, b2, color=grey, width=0.4)
    d = np.array([b2.x - a2.x, b2.y - a2.y])
    L = float(np.linalg.norm(d)) or 1.0
    u = d / L
    for p, s in ((a2, 1), (b2, -1)):
        n = np.array([-u[1], u[0]])
        tip = np.array([p.x, p.y])
        back = tip + s * u * 2.2 * MM
        page.draw_polyline([fitz.Point(*(back + n * 0.7 * MM)), fitz.Point(*tip), fitz.Point(*(back - n * 0.7 * MM))], color=grey, width=0.4)
    text = f"{value:.6g}"
    mid = fitz.Point((a2.x + b2.x) / 2, (a2.y + b2.y) / 2)
    if side == "below":
        page.insert_text(fitz.Point(mid.x - len(text) * 2.2, mid.y - 1.5), text, fontsize=8, color=grey)
    else:
        page.insert_text(fitz.Point(mid.x + 2, mid.y + 3), text, fontsize=8, color=grey)
