"""PCB manufacturing data as 2D drawings: Gerber (RS-274X, X2), Excellon drill files and ODB++ -> the drawing JSON of
auto3d/drawing2d.py (layers, entities in mm). Traces keep their width ("w"), pads and copper areas are filled
("fill": true), clear polarity is marked ("clear": true). A .zip holds a Gerber set or an ODB++ job (also as a .tgz).

Written here (no Gerber library): the parts of the formats that boards use — apertures C / R / O / P and aperture
macros (primitives 1, 4, 5, 20, 21, 7), interpolation G01 / G02 / G03 (G74 / G75), regions G36 / G37, LP polarity,
step & repeat; Excellon tools, hits and G85 slots; ODB++ matrix, features (L / P / A / S records, standard symbols)
and the step's profile, also compressed (.Z).
"""
from __future__ import annotations

import io
import math
import re
import tarfile
import zipfile

from .importers import ImportError_

INCH = 25.4

# ------------------------------------------------------------------ which layer a file is, and its colour
COLORS = {"copper_top": "#d24b3c", "copper_bottom": "#3c78d2", "copper_inner": "#c8a032", "silk_top": "#f0f0f0",
          "silk_bottom": "#b4b4ff", "mask_top": "#2e9e5b", "mask_bottom": "#2e7e9e", "paste_top": "#9a9a9a",
          "paste_bottom": "#7a7a7a", "outline": "#f2cc60", "drill": "#ffffff", "other": "#8b95a3", "assembly": "#c78fff"}
# shown when the board opens (the rest: a click on 👁)
SHOWN = {"copper_top", "outline", "drill", "silk_top"}
# drawn first .. last
ORDER = ["other", "assembly", "paste_bottom", "mask_bottom", "silk_bottom", "copper_bottom", "copper_inner",
         "copper_top", "mask_top", "paste_top", "silk_top", "outline", "drill"]

_EXT = {".gtl": "copper_top", ".cmp": "copper_top", ".top": "copper_top", ".gbl": "copper_bottom", ".sol": "copper_bottom",
        ".bot": "copper_bottom", ".gto": "silk_top", ".plc": "silk_top", ".gbo": "silk_bottom", ".pls": "silk_bottom",
        ".gts": "mask_top", ".stc": "mask_top", ".gbs": "mask_bottom", ".sts": "mask_bottom", ".gtp": "paste_top",
        ".crc": "paste_top", ".gbp": "paste_bottom", ".crs": "paste_bottom", ".gko": "outline", ".gm1": "outline",
        ".gml": "outline", ".dim": "outline", ".gm": "outline", ".oln": "outline", ".drl": "drill", ".xln": "drill",
        ".drd": "drill", ".exc": "drill", ".ncd": "drill", ".tap": "drill"}
_EXT.update({".smt": "mask_top", ".smb": "mask_bottom", ".sst": "silk_top", ".ssb": "silk_bottom", ".spt": "paste_top", ".spb": "paste_bottom",
             ".ast": "assembly", ".asb": "assembly", ".gp1": "copper_inner", ".gp2": "copper_inner", ".gdo": "other", ".off": "other"})
_NAME = [(r"componentmask|\.front.?mask|topmask", "mask_top"), (r"soldermask|\.back.?mask|bottommask", "mask_bottom"),
         (r"componentsilk|\.frontsilk|topsilk|silk.?top", "silk_top"), (r"soldersilk|\.backsilk|bottomsilk", "silk_bottom"),
         (r"componentpaste|\.frontpaste", "paste_top"), (r"solderpaste|\.backpaste", "paste_bottom"),
         (r"\.front\.|\bfront\b|\bcomponent\b|etch.*top", "copper_top"), (r"\.back\.|\bback\b|\bsolder\b|etch.*bot", "copper_bottom"),
         (r"\.group\d+\.|output_group\d|etchlayer\d", "copper_inner"), (r"\.fab\.", "assembly"),
         (r"f[._-]cu|copper.*top|top.*copper|toplayer|\btop\b", "copper_top"), (r"b[._-]cu|copper.*bot|bottom.*copper|bottomlayer|\bbottom\b", "copper_bottom"),
         (r"in\d+[._-]cu|inner|copper_signal_\d|signal.*\d|\.g\d+$|gp\d", "copper_inner"),
         (r"f[._-]silk|silk.*top|top.*(silk|overlay|legend)|legend.*top", "silk_top"), (r"b[._-]silk|silk.*bot|bottom.*(silk|overlay|legend)|legend.*bot", "silk_bottom"),
         (r"f[._-]mask|mask.*top|top.*mask|soldermask.*top", "mask_top"), (r"b[._-]mask|mask.*bot|bottom.*mask", "mask_bottom"),
         (r"f[._-]paste|paste.*top|top.*paste", "paste_top"), (r"b[._-]paste|paste.*bot|bottom.*paste", "paste_bottom"),
         (r"edge[._-]cuts|outline|profile|board[._ -]?shape|border|mechanical\s*1|keep.?out|\.gm\d*$|dimension", "outline"),
         (r"drill|\.drl$|\.xln$|nc_?drill|plated|npth|pth", "drill"), (r"assy|assembly|fab", "assembly")]


def _kind_x2(function):
    """Gerber X2 %TF.FileFunction,…*% -> a kind."""
    f = [x.strip().lower() for x in function.split(",")]
    head = f[0] if f else ""
    side = next((x for x in f if x in ("top", "bot")), None)
    if head == "copper":
        return "copper_top" if side == "top" else "copper_bottom" if side == "bot" else "copper_inner"
    if head in ("legend", "silkscreen"):
        return "silk_bottom" if side == "bot" else "silk_top"
    if head == "soldermask":
        return "mask_bottom" if side == "bot" else "mask_top"
    if head == "paste":
        return "paste_bottom" if side == "bot" else "paste_top"
    if head in ("profile", "keepout") or head.startswith("mechanical"):
        return "outline" if head == "profile" else "other"
    if head in ("plated", "nonplated", "drillmap"):
        return "drill"
    if head in ("assemblydrawing", "fabricationdrawing"):
        return "assembly"
    return None


_SHORT = {"tl": "copper_top", "top": "copper_top", "bl": "copper_bottom", "bot": "copper_bottom", "ts": "mask_top", "bs": "mask_bottom",
          "to": "silk_top", "bo": "silk_bottom", "tp": "paste_top", "bp": "paste_bottom", "ko": "outline", "gko": "outline",
          "drl": "drill", "drill": "drill", "sk": "silk_top"}


def kind_of(name: str, text: str = "") -> str:
    m = re.search(r"%TF\.FileFunction,([^*]*)\*%", text[:5000])
    if m and (k := _kind_x2(m.group(1))):
        return k
    low = name.lower()
    stem = low.rsplit("/", 1)[-1]
    if stem in _SHORT:
        return _SHORT[stem]
    if re.fullmatch(r"l\d+", stem):
        return "copper_inner"
    for ext, k in _EXT.items():
        if low.endswith(ext) and k != "other":
            # a "bottom" in the name wins over the extension (e.g. Eagle's "silk bot.plc")
            return k.replace("_top", "_bottom") if k.endswith("_top") and re.search(r"\bbot(tom)?\b", stem) else k
    for rx, k in _NAME:
        if re.search(rx, low):
            return k
    return "other"


# ------------------------------------------------------------------ geometry helpers
def _circle_pts(c, r, n=None):
    n = n or max(16, min(96, int(r * 40) + 16))
    return [[c[0] + r * math.cos(2 * math.pi * i / n), c[1] + r * math.sin(2 * math.pi * i / n)] for i in range(n)]


def _rot(p, deg, about=(0.0, 0.0)):
    if not deg:
        return [p[0], p[1]]
    a = math.radians(deg)
    x, y = p[0] - about[0], p[1] - about[1]
    return [about[0] + x * math.cos(a) - y * math.sin(a), about[1] + x * math.sin(a) + y * math.cos(a)]


def _rect_pts(cx, cy, w, h, deg=0.0):
    return [_rot([cx + dx, cy + dy], deg, (cx, cy)) for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))]


def _obround_pts(cx, cy, w, h, deg=0.0):
    r = min(w, h) / 2
    pts = []
    if w >= h:  # round ends left / right
        for a0, ox in ((-90, w / 2 - r), (90, -(w / 2 - r))):
            pts += [[cx + ox + r * math.cos(math.radians(a0 + 180 * i / 12)), cy + r * math.sin(math.radians(a0 + 180 * i / 12))] for i in range(13)]
    else:
        for a0, oy in ((0, h / 2 - r), (180, -(h / 2 - r))):
            pts += [[cx + r * math.cos(math.radians(a0 + 180 * i / 12)), cy + oy + r * math.sin(math.radians(a0 + 180 * i / 12))] for i in range(13)]
    return [_rot(p, deg, (cx, cy)) for p in pts]


def _arc_pts(c, r, a0, a1, ccw):
    """Points of an arc from angle a0 to a1 (radians) about c, counter-clockwise or clockwise."""
    sw = (a1 - a0) % (2 * math.pi) if ccw else -((a0 - a1) % (2 * math.pi))
    if abs(sw) < 1e-12:
        sw = 2 * math.pi if ccw else -2 * math.pi
    n = max(4, int(abs(sw) / (math.pi / 24)) + 1)
    return [[c[0] + r * math.cos(a0 + sw * i / n), c[1] + r * math.sin(a0 + sw * i / n)] for i in range(1, n + 1)]


def _r6(p):
    return [round(p[0], 6), round(p[1], 6)]


# ------------------------------------------------------------------ Gerber
class _Expr:
    """Aperture macro arithmetic: + - x / ( ) and $n."""

    @staticmethod
    def ev(s, var):
        s = re.sub(r"\s+", "", s)
        s = re.sub(r"\$(\d+)", lambda m: repr(float(var.get(int(m.group(1)), 0.0))), s)
        s = s.replace("x", "*").replace("X", "*")
        if not re.fullmatch(r"[0-9.eE+\-*/()]*", s):
            raise ValueError(f"bad macro expression {s!r}")
        return float(eval(s, {"__builtins__": {}}, {})) if s else 0.0  # noqa: S307 — only numbers and + - * / ( )


def _macro_shapes(body, params, at, unit):
    """An aperture macro flashed at `at` -> [(poly points | ("circle", c, r)), exposure]."""
    var = {i + 1: v for i, v in enumerate(params)}
    out = []
    for prim in body:
        prim = re.sub(r"\s+", "", prim)
        if not prim or prim.startswith("0"):
            continue
        if re.match(r"^\$\d+=", prim):
            k, ex = prim.split("=", 1)
            var[int(k[1:])] = _Expr.ev(ex, var)
            continue
        args = [a for a in prim.split(",")]
        code = int(float(args[0]))
        v = [_Expr.ev(a, var) for a in args[1:]]
        try:
            if code == 1:  # circle: exposure, Ø, x, y[, rot]
                rot = v[4] if len(v) > 4 else 0.0
                c = _rot([v[2] * unit, v[3] * unit], rot)
                out.append((("circle", [at[0] + c[0], at[1] + c[1]], v[1] * unit / 2), v[0] >= 0.5))
            elif code in (20, 2):  # vector line: exposure, width, x1, y1, x2, y2, rot
                ex, w, x1, y1, x2, y2, rot = v[:7]
                dx, dy = x2 - x1, y2 - y1
                L = math.hypot(dx, dy) or 1e-9
                nx, ny = -dy / L * w / 2, dx / L * w / 2
                pts = [[x1 + nx, y1 + ny], [x2 + nx, y2 + ny], [x2 - nx, y2 - ny], [x1 - nx, y1 - ny]]
                out.append(([[at[0] + q[0] * unit, at[1] + q[1] * unit] for q in (_rot(p, rot) for p in pts)], ex >= 0.5))
            elif code == 21:  # centre line: exposure, w, h, cx, cy, rot
                ex, w, h, cx, cy, rot = v[:6]
                out.append(([[at[0] + q[0] * unit, at[1] + q[1] * unit] for q in (_rot(p, rot) for p in _rect_pts(cx, cy, w, h))], ex >= 0.5))
            elif code == 22:  # lower-left line (old): exposure, w, h, x, y, rot
                ex, w, h, x, y, rot = v[:6]
                out.append(([[at[0] + q[0] * unit, at[1] + q[1] * unit] for q in (_rot(p, rot) for p in _rect_pts(x + w / 2, y + h / 2, w, h))], ex >= 0.5))
            elif code == 4:  # outline: exposure, n, x0, y0, … xn, yn, rot
                ex, n = v[0], int(v[1])
                xy = v[2:2 + 2 * (n + 1)]
                rot = v[2 + 2 * (n + 1)] if len(v) > 2 + 2 * (n + 1) else 0.0
                pts = [_rot([xy[2 * i], xy[2 * i + 1]], rot) for i in range(n + 1)]
                out.append(([[at[0] + p[0] * unit, at[1] + p[1] * unit] for p in pts[:-1]], ex >= 0.5))
            elif code == 5:  # polygon: exposure, vertices, cx, cy, Ø, rot
                ex, n, cx, cy, d, rot = v[0], int(v[1]), v[2], v[3], v[4], v[5] if len(v) > 5 else 0.0
                pts = [_rot([cx + d / 2 * math.cos(2 * math.pi * i / n), cy + d / 2 * math.sin(2 * math.pi * i / n)], rot) for i in range(n)]
                out.append(([[at[0] + p[0] * unit, at[1] + p[1] * unit] for p in pts], ex >= 0.5))
            elif code == 7:  # thermal: cx, cy, outer Ø, inner Ø, gap, rot -> its ring
                cx, cy, od, idia = v[0], v[1], v[2], v[3]
                c = [at[0] + cx * unit, at[1] + cy * unit]
                out.append((("circle", c, od * unit / 2), True))
                out.append((("circle", c, idia * unit / 2), False))
            elif code == 6:  # moiré: its outer ring
                out.append((("circle", [at[0] + v[0] * unit, at[1] + v[1] * unit], v[2] * unit / 2), True))
        except (IndexError, ValueError, ZeroDivisionError):
            continue
    return out


def parse_gerber(text: str, layer: str):
    """RS-274X -> (entities on `layer`, issues)."""
    ents, issues = [], []
    unit = 1.0  # mm per file unit (MOMM; MOIN -> 25.4)
    fmt = {"dec": 6, "int": 3, "zeros": "L"}
    apertures, macros = {}, {}
    cur_ap = None
    x = y = 0.0
    mode, quadrant = "G01", "multi"
    region, contour, contours = False, [], []
    clear = False
    sr = None  # step & repeat: (nx, ny, dx, dy, start index)
    skipped = set()

    def num(s, axis_dec=None):
        if "." in s:
            return float(s) * unit
        neg = s.startswith("-")
        s = s.lstrip("+-")
        if fmt["zeros"] == "T":  # trailing zeros omitted: pad to the full width
            s = s.ljust(fmt["int"] + fmt["dec"], "0")
        v = int(s or "0") / 10 ** fmt["dec"]
        return (-v if neg else v) * unit

    def add(e):
        if clear:
            e["clear"] = True
        ents.append({"layer": layer, **e})

    def flash(ap, at):
        if ap is None:
            return
        kind, prm = ap
        if kind == "C":
            add({"t": "circle", "c": _r6(at), "r": round(prm[0] / 2, 6), "fill": True})
        elif kind == "R":
            add({"t": "poly", "pts": [_r6(p) for p in _rect_pts(at[0], at[1], prm[0], prm[1] if len(prm) > 1 else prm[0])], "closed": True, "fill": True})
        elif kind == "O":
            add({"t": "poly", "pts": [_r6(p) for p in _obround_pts(at[0], at[1], prm[0], prm[1] if len(prm) > 1 else prm[0])], "closed": True, "fill": True})
        elif kind == "P":
            d, n, rot = prm[0], int(prm[1]), prm[2] if len(prm) > 2 else 0.0
            add({"t": "poly", "pts": [_r6(_rot([at[0] + d / 2 * math.cos(2 * math.pi * i / n), at[1] + d / 2 * math.sin(2 * math.pi * i / n)], rot, at)) for i in range(n)], "closed": True, "fill": True})
        elif kind == "M":
            name, params = prm
            for shape, on in _macro_shapes(macros.get(name, []), params, at, unit):
                e = {"t": "circle", "c": _r6(shape[1]), "r": round(shape[2], 6), "fill": True} if isinstance(shape, tuple) and shape[0] == "circle" \
                    else {"t": "poly", "pts": [_r6(p) for p in shape], "closed": True, "fill": True}
                if not on:
                    e["clear"] = True
                ents.append({"layer": layer, **e})

    def width(ap):
        if ap is None:
            return 0.0
        kind, prm = ap
        if kind in ("C", "P"):
            return prm[0]
        if kind in ("R", "O"):
            return min(prm[0], prm[1] if len(prm) > 1 else prm[0])
        return 0.0

    # the file: %…% extended blocks and *-ended words
    pos, n = 0, len(text)
    while pos < n:
        ch = text[pos]
        if ch in " \r\n\t":
            pos += 1
            continue
        if ch == "%":
            end = text.find("%", pos + 1)
            if end < 0:
                break
            # (spaces and line breaks inside a %…% block mean nothing — a file may break an aperture over lines)
            blocks = [b for b in (re.sub(r"\s+", "", x) if not x.lstrip().startswith(("TF", "TA", "TO", "TD")) else x.strip() for x in text[pos + 1:end].split("*")) if b]
            pos = end + 1
            if not blocks:
                continue
            b0 = blocks[0]
            if b0.startswith("FS"):
                m = re.match(r"FS([LTD]?)([AI]?)(?:N\d+)?(?:G\d+)?X(\d)(\d)Y(\d)(\d)", b0)
                if m:
                    fmt = {"zeros": m.group(1) or "L", "int": int(m.group(3)), "dec": int(m.group(4))}
            elif b0.startswith("MO"):
                unit = INCH if "IN" in b0 else 1.0
            elif b0.startswith("AD"):
                m = re.match(r"ADD(\d+)([^,]+),?(.*)", b0)
                if m:
                    d, shape, rest = int(m.group(1)), m.group(2), m.group(3)
                    # numbers split by X — also when the X is missing ("0.03260.326": 0.0326 and 0.326, as other viewers read it)
                    vals = [float(v) for v in re.findall(r"[+-]?(?:\d+\.?\d*|\.\d+)", rest)] if rest else []
                    if shape in ("C", "R", "O", "P"):
                        apertures[d] = (shape, [v * unit if (shape != "P" or i == 0) else v for i, v in enumerate(vals)])
                    else:
                        apertures[d] = ("M", (shape, vals))
            elif b0.startswith("AM"):
                macros[b0[2:]] = blocks[1:]
            elif b0.startswith("LP"):
                clear = b0 == "LPC"
            elif b0.startswith("SR"):
                if sr:  # the block before: repeat it
                    nx, ny, dx, dy, start = sr
                    block = ents[start:]
                    for i in range(nx):
                        for j in range(ny):
                            if i == 0 and j == 0:
                                continue
                            ents.extend(_moved(e, i * dx, j * dy) for e in block)
                    sr = None
                m = re.match(r"SRX(\d+)Y(\d+)I([\d.]+)J([\d.]+)", b0)
                if m and (int(m.group(1)) > 1 or int(m.group(2)) > 1):
                    sr = (int(m.group(1)), int(m.group(2)), float(m.group(3)) * unit, float(m.group(4)) * unit, len(ents))
            elif b0[:2] in ("LM", "LR", "LS"):
                skipped.add(b0[:2])
            continue
        end = text.find("*", pos)
        if end < 0:
            break
        word = text[pos:end].strip()
        pos = end + 1
        if not word:
            continue
        for g in re.findall(r"G0*(\d+)", word):
            g = int(g)
            if g in (1, 2, 3):
                mode = f"G0{g}"
            elif g == 74:
                quadrant = "single"
            elif g == 75:
                quadrant = "multi"
            elif g == 36:
                region, contour, contours = True, [], []
            elif g == 37:
                if len(contour) > 2:
                    contours.append(contour)
                for c in contours:
                    add({"t": "poly", "pts": [_r6(p) for p in c], "closed": True, "fill": True})
                region, contour, contours = False, [], []
            elif g == 70:
                unit = INCH
            elif g == 71:
                unit = 1.0
        if word.startswith("G04") or word.startswith("M02") or word.startswith("M00"):
            continue
        coords = dict(re.findall(r"([XYIJ])([+-]?[\d.]+)", word))
        dm = re.search(r"D0*(\d+)$", word)
        d = int(dm.group(1)) if dm else None
        if d is not None and d >= 10:
            cur_ap = apertures.get(d)
            continue
        if not coords and d is None:
            continue
        nx_ = num(coords["X"]) if "X" in coords else x
        ny_ = num(coords["Y"]) if "Y" in coords else y
        if d is None:
            d = 1 if coords else None  # (modal D01, deprecated but met)
        if d == 2:
            if region and len(contour) > 2:
                contours.append(contour)
            if region:
                contour = [[nx_, ny_]]
            x, y = nx_, ny_
        elif d == 3:
            x, y = nx_, ny_
            flash(cur_ap, (x, y))
        elif d == 1:
            if mode == "G01":
                if region:
                    if not contour:
                        contour = [[x, y]]
                    contour.append([nx_, ny_])
                else:
                    w = width(cur_ap)
                    add({"t": "line", "a": _r6([x, y]), "b": _r6([nx_, ny_]), **({"w": round(w, 6)} if w else {})})
            else:
                i = num(coords["I"]) if "I" in coords else 0.0
                j = num(coords["J"]) if "J" in coords else 0.0
                ccw = mode == "G03"
                if quadrant == "single":  # I / J without a sign: the centre that fits best
                    cands = [(x + si * abs(i), y + sj * abs(j)) for si in (1, -1) for sj in (1, -1)]
                    c = min(cands, key=lambda q: abs(math.hypot(x - q[0], y - q[1]) - math.hypot(nx_ - q[0], ny_ - q[1])))
                else:
                    c = (x + i, y + j)
                r = math.hypot(x - c[0], y - c[1])
                a0, a1 = math.atan2(y - c[1], x - c[0]), math.atan2(ny_ - c[1], nx_ - c[0])
                if region:
                    if not contour:
                        contour = [[x, y]]
                    contour += _arc_pts(c, r, a0, a1, ccw)
                else:
                    w = width(cur_ap)
                    full = math.hypot(nx_ - x, ny_ - y) < 1e-9 and quadrant == "multi"
                    if full:
                        add({"t": "circle", "c": _r6(c), "r": round(r, 6), **({"w": round(w, 6)} if w else {})})
                    else:
                        s, e = (a0, a1) if ccw else (a1, a0)
                        add({"t": "arc", "c": _r6(c), "r": round(r, 6), "a0": round(math.degrees(s), 6), "a1": round(math.degrees(e), 6), **({"w": round(w, 6)} if w else {})})
            x, y = nx_, ny_
    if skipped:
        issues.append(f"{layer}: mirrored / rotated / scaled objects ({', '.join(sorted(skipped))}) are shown as they are.")
    return ents, issues


def _bbox(es):
    ps = [p for e in es for p in ([e["a"], e["b"]] if e["t"] == "line" else [e["c"]] if "c" in e else e.get("pts", []))]
    if not ps:
        return None
    xs, ys = [p[0] for p in ps], [p[1] for p in ps]
    return [min(xs), min(ys), max(xs), max(ys)]


def _fit_drills(layers, ents):
    """Excellon files rarely say their number format: a drill file whose holes fall outside the board drawn by the
    Gerber files of its folder gets its positions scaled by the power of ten that puts them on the board."""
    issues = []
    by_layer = {}
    for e in ents:
        by_layer.setdefault(e["layer"], []).append(e)
    for ly in layers:
        if not ly.get("drill"):
            continue
        board = _bbox([e for o in layers if not o.get("drill") and o["folder"] == ly["folder"] for e in by_layer.get(o["name"], [])])
        holes = by_layer.get(ly["name"], [])
        hb = _bbox(holes)
        if not board or not hb:
            continue
        w = max(board[2] - board[0], board[3] - board[1], 1e-6)
        inside = lambda b, k: b[0] * k >= board[0] - 0.05 * w and b[1] * k >= board[1] - 0.05 * w and b[2] * k <= board[2] + 0.05 * w and b[3] * k <= board[3] + 0.05 * w  # noqa: E731
        if inside(hb, 1.0):
            continue
        fits = [k for k in (10.0 ** -i for i in range(1, 6)) if inside(hb, k)] + [k for k in (10.0, 100.0) if inside(hb, k)]
        if not fits:
            continue
        k = max(fits, key=lambda q: (hb[2] - hb[0]) * q)  # the biggest that still fits: the holes spread over the board
        for e in holes:
            for key in ("a", "b", "c"):
                if key in e:
                    e[key] = _r6([e[key][0] * k, e[key][1] * k])
        issues.append(f"{ly['name']}: its number format is not in the file — its holes were scaled ×{k:g} to sit on the board.")
    return issues


def _moved(e, dx, dy):
    m = dict(e)
    for k in ("a", "b", "c"):
        if k in m:
            m[k] = _r6([m[k][0] + dx, m[k][1] + dy])
    if "pts" in m:
        m["pts"] = [_r6([p[0] + dx, p[1] + dy]) for p in m["pts"]]
    return m


# ------------------------------------------------------------------ Excellon (drill)
def parse_excellon(text: str, layer: str):
    ents, issues = [], []
    unit, zeros, dig = INCH, "T", (2, 4)  # (not said: leading zeros dropped, as most tools write; the scale is fitted later)
    tools, tool = {}, None
    x = y = 0.0
    header = False
    m = re.search(r";\s*FILE_FORMAT\s*=\s*(\d+):(\d+)", text)
    if m:
        dig = (int(m.group(1)), int(m.group(2)))

    def num(s):
        if "." in s:
            return float(s) * unit
        neg = s.startswith("-")
        s = s.lstrip("+-")
        if zeros == "L":  # leading zeros kept, trailing ones dropped: pad to the full width
            s = s.ljust(dig[0] + dig[1], "0")
            v = int(s) / 10 ** dig[1]
        else:  # trailing zeros kept
            v = int(s) / 10 ** dig[1]
        return (-v if neg else v) * unit

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith("M48"):
            header = True
            continue
        if line in ("%", "M95"):
            header = False
            continue
        if line.startswith(("METRIC", "INCH")):
            unit = 1.0 if line.startswith("METRIC") else INCH
            if "TZ" in line:
                zeros = "T"
            elif "LZ" in line:
                zeros = "L"
            if not m:
                dig = (3, 3) if unit == 1.0 else (2, 4)
            mm = re.search(r",(\d+)\.(\d+)", line)  # METRIC,LZ,000.000
            if mm:
                dig = (len(mm.group(1)), len(mm.group(2)))
            continue
        if line.startswith(("M71", "M72")):
            unit = 1.0 if line.startswith("M71") else INCH
            continue
        tm = re.match(r"T(\d+)(?:.*?C([\d.]+))?", line)
        if tm and not line.startswith(("X", "Y")):
            t, c = int(tm.group(1)), tm.group(2)
            if c is not None:
                tools[t] = float(c) * unit
            if not header or c is None:
                tool = t
            continue
        if line.startswith(("X", "Y")) or "G85" in line:
            parts = line.split("G85")
            pts = []
            for part in parts:
                co = dict(re.findall(r"([XY])([+-]?[\d.]+)", part))
                x = num(co["X"]) if "X" in co else x
                y = num(co["Y"]) if "Y" in co else y
                pts.append([x, y])
            dia = tools.get(tool, 0.5)
            if len(pts) == 2:  # a slot
                ents.append({"layer": layer, "t": "line", "a": _r6(pts[0]), "b": _r6(pts[1]), "w": round(dia, 6)})
            else:
                ents.append({"layer": layer, "t": "circle", "c": _r6(pts[0]), "r": round(dia / 2, 6), "fill": True})
    return ents, issues


# ------------------------------------------------------------------ a Gerber set
NOT_PCB = (".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".eps", ".ps", ".svg", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".htm", ".html",
           ".zip", ".tgz", ".gz", ".step", ".stp", ".dxf", ".dwg", ".pcbdoc", ".schdoc", ".prjpcb", ".brd", ".sch", ".kicad_pcb", ".rep", ".log")


def _looks_gerber(text):
    return bool(re.search(r"%FS[LTD]?[AI]", text[:20000]) or re.search(r"%MO(MM|IN)\*%", text[:20000])) or (bool(re.search(r"D0?1\*", text)) and bool(re.search(r"D0?2\*", text)) and "ADD" in text)


def _looks_excellon(text):
    return "M48" in text[:2000] or bool(re.search(r"^T\d+C[\d.]+", text[:5000], re.M))


def read_gerber_set(files):
    """[(name, bytes)] -> the drawing JSON (one layer per file)."""
    layers, ents, issues = [], [], []
    folders = {n.replace("\\", "/").rsplit("/", 1)[0] if "/" in n.replace("\\", "/") else "" for n, _ in files}
    many = len(folders) > 1
    for name, data in files:
        if b"\x00" in data[:4096]:
            continue  # a binary file (a program, a picture): not a Gerber or drill file
        text = data.decode("latin-1", "ignore")
        path = name.replace("\\", "/")
        base = path.rsplit("/", 1)[-1]
        folder = path.rsplit("/", 1)[0] if "/" in path else ""
        if _looks_gerber(text):
            kind = kind_of(base, text)
            parser = parse_gerber
        elif _looks_excellon(text):
            kind = "drill"
            parser = parse_excellon
        else:
            continue
        label = f"{folder.rsplit('/', 1)[-1]} / {base}" if many and folder else base
        try:
            got, iss = parser(text, label)
        except Exception as exc:  # noqa: BLE001 — one odd file: skip it, read the rest
            issues.append(f"{base}: could not be read ({exc}).")
            continue
        if not got:
            continue
        layers.append({"name": label, "color": COLORS[kind], "visible": kind in SHOWN, "kind": kind, "folder": folder, "drill": parser is parse_excellon})
        ents += got
        issues += iss
    if not layers:
        raise ImportError_("no Gerber or drill files in it")
    issues += _fit_drills(layers, ents)
    for ly in layers:
        ly.pop("folder", None)
        ly.pop("drill", None)
    layers.sort(key=lambda l: ORDER.index(l["kind"]))
    for i, e in enumerate(ents):
        e["id"] = f"e{i + 1}"
    return {"unit": "mm", "file_units": "mm", "units_declared": True, "layers": layers, "entities": ents, "issues": issues, "pcb": "gerber"}


# ------------------------------------------------------------------ ODB++
def unlzw(data: bytes) -> bytes:
    """Unix compress (.Z) data -> its bytes (a port of Mark Adler's unlzw: codes of 9..maxbits bits, CLEAR = 256 in
    block mode; at each change of the code size the rest of the current group of 8 codes is skipped)."""
    if len(data) < 3 or data[:2] != bytes((0x1F, 0x9D)):
        return data
    flags = data[2]
    maxbits, block = flags & 0x1F, flags & 0x80
    if not 9 <= maxbits <= 16:
        raise ImportError_("a damaged compressed (.Z) file")
    n = len(data)
    if n < 5:
        return b""
    prefix, suffix = [0] * 65536, bytearray(65536)
    bits, mask, end = 9, 0x1FF, 256 if block else 255
    buf = data[3] | (data[4] << 8)
    final = prev = buf & mask
    buf >>= bits
    left = 16 - bits
    if prev > 255:
        raise ImportError_("a damaged compressed (.Z) file")
    out = bytearray([final])
    mark, nxt = 3, 5
    while True:
        if end >= mask and bits < maxbits:  # a wider code from now on: skip to the end of this group of codes
            rem = (nxt - mark) % bits
            if rem:
                nxt += bits - rem
            buf = left = 0
            mark = nxt
            bits += 1
            mask = (mask << 1) | 1
        if nxt >= n:
            break
        buf |= data[nxt] << left
        nxt += 1
        left += 8
        if left < bits:
            if nxt >= n:
                break
            buf |= data[nxt] << left
            nxt += 1
            left += 8
        code = buf & mask
        buf >>= bits
        left -= bits
        if code == 256 and block:  # CLEAR: start the table again
            rem = (nxt - mark) % bits
            if rem:
                nxt += bits - rem
            buf = left = 0
            mark = nxt
            bits, mask, end = 9, 0x1FF, 255
            continue
        temp, stack = code, bytearray()
        if code > end:  # the code being made right now
            if code != end + 1 or prev > end:
                raise ImportError_("a damaged compressed (.Z) file")
            stack.append(final)
            code = prev
        while code >= 256:
            stack.append(suffix[code])
            code = prefix[code]
        stack.append(code)
        final = code
        if end < mask:
            end += 1
            prefix[end] = prev
            suffix[end] = final
        prev = temp
        stack.reverse()
        out += stack
    return bytes(out)


_ODB_KIND = {"signal": "copper", "power_ground": "copper", "mixed": "copper", "solder_mask": "mask", "solder_paste": "paste",
             "silk_screen": "silk", "drill": "drill", "rout": "outline", "document": "other", "component": "assembly"}


def _odb_matrix(text):
    rows = []
    for blk in re.findall(r"LAYER\s*\{(.*?)\}", text, re.S):
        kv = dict(re.findall(r"(\w+)\s*=\s*([^\n]*)", blk))
        rows.append({k.upper(): v.strip() for k, v in kv.items()})
    rows.sort(key=lambda r: int(r.get("ROW", 0) or 0))
    return rows


def _symbol(name, scale):
    """A standard ODB++ symbol -> ("round", d) | ("rect", w, h) | ("oval", w, h) | ("donut", od, id) | ("diamond", w, h) | ("oct", w, h); sizes mm."""
    nm = name.lower()
    nums = [float(v) for v in re.findall(r"[\d.]+", nm)]
    k = lambda v: v * scale  # noqa: E731
    if nm.startswith("r") and re.fullmatch(r"r[\d.]+", nm):
        return ("round", k(nums[0]))
    if re.fullmatch(r"s[\d.]+", nm):
        return ("rect", k(nums[0]), k(nums[0]))
    if re.fullmatch(r"rect[\d.]+x[\d.]+(x[rc][\d.]+(x\d+)?)?", nm):
        return ("rect", k(nums[0]), k(nums[1]))
    if re.fullmatch(r"oval[\d.]+x[\d.]+", nm):
        return ("oval", k(nums[0]), k(nums[1]))
    if re.fullmatch(r"donut_r[\d.]+x[\d.]+", nm):
        return ("donut", k(nums[0]), k(nums[1]))
    if re.fullmatch(r"donut_s[\d.]+x[\d.]+", nm):
        return ("rect", k(nums[0]), k(nums[0]))
    if re.fullmatch(r"di[\d.]+x[\d.]+", nm):
        return ("diamond", k(nums[0]), k(nums[1]))
    if re.fullmatch(r"(oct|hex_[ls])[\d.]+(x[\d.]+)*", nm):
        return ("oct", k(nums[0]), k(nums[1]) if len(nums) > 1 else k(nums[0]))
    if re.fullmatch(r"el[\d.]+x[\d.]+", nm):
        return ("oval", k(nums[0]), k(nums[1]))
    return None  # the job's own symbol (symbols/<name>/features), or one not drawn


def _odb_features(text, layer, unit_default, user=None):
    """An ODB++ features file -> (entities on `layer`, the names of symbols not drawn). user(name) -> the job's own
    symbol as entities around (0, 0), or None."""
    ents, missing = [], set()
    unit = unit_default
    m = re.search(r"^\s*(?:UNITS\s*=\s*|U\s+)(MM|INCH)", text, re.M | re.I)
    if m:
        unit = 1.0 if m.group(1).upper() == "MM" else INCH
    syms = {}
    for sm in re.finditer(r"^\$(\d+)\s+(\S+)(?:\s+([IM]))?", text, re.M):
        su = sm.group(3)
        scale = (0.001 if su == "M" else INCH / 1000) if su else (0.001 if unit == 1.0 else INCH / 1000)  # microns / mils
        syms[int(sm.group(1))] = (sm.group(2), _symbol(sm.group(2), scale))
    P = lambda a, b: [round(float(a) * unit, 6), round(float(b) * unit, 6)]  # noqa: E731

    def pad(sym, at, deg, neg):
        if sym is None:
            return
        kind = sym[0]
        e = None
        if kind == "round":
            e = {"t": "circle", "c": at, "r": round(sym[1] / 2, 6), "fill": True}
        elif kind == "rect":
            e = {"t": "poly", "pts": [_r6(p) for p in _rect_pts(at[0], at[1], sym[1], sym[2], -deg)], "closed": True, "fill": True}
        elif kind == "oval":
            e = {"t": "poly", "pts": [_r6(p) for p in _obround_pts(at[0], at[1], sym[1], sym[2], -deg)], "closed": True, "fill": True}
        elif kind == "diamond":
            w, h = sym[1] / 2, sym[2] / 2
            e = {"t": "poly", "pts": [_r6(_rot(p, -deg, at)) for p in ([at[0] + w, at[1]], [at[0], at[1] + h], [at[0] - w, at[1]], [at[0], at[1] - h])], "closed": True, "fill": True}
        elif kind == "oct":
            r = sym[1] / 2
            e = {"t": "poly", "pts": [_r6(_rot([at[0] + r * math.cos(math.pi / 8 + i * math.pi / 4), at[1] + r * math.sin(math.pi / 8 + i * math.pi / 4)], -deg, at)) for i in range(8)], "closed": True, "fill": True}
        elif kind == "donut":
            e = {"t": "circle", "c": at, "r": round((sym[1] + sym[2]) / 4, 6), "w": round((sym[1] - sym[2]) / 2, 6)}
        if e:
            if neg:
                e["clear"] = True
            ents.append({"layer": layer, **e})

    surface, contour = None, None
    for raw in text.splitlines():
        line = raw.split(";", 1)[0].strip()
        if not line or line[0] in "#$@&":
            continue
        f = line.split()
        tag = f[0]
        try:
            if tag == "L":
                a, b = P(f[1], f[2]), P(f[3], f[4])
                s = syms.get(int(f[5]), (None, None))[1]
                w = s[1] if s else 0.0
                e = {"t": "line", "a": a, "b": b, **({"w": round(w, 6)} if w else {})}
                if f[6] == "N":
                    e["clear"] = True
                ents.append({"layer": layer, **e})
            elif tag == "P":
                at = P(f[1], f[2])
                sid, neg = int(f[3]), f[4] == "N"
                orient = int(f[6]) if len(f) > 6 else 0
                deg = float(f[7]) if orient in (8, 9) and len(f) > 7 else (orient % 4) * 90.0
                name, s = syms.get(sid, (None, None))
                if s is None and name:
                    own = user(name) if user else None
                    if own is None:
                        missing.add(name)
                    else:  # the job's own symbol: its shapes, turned (and mirrored, orient 4..7 / 9) and moved to the pad
                        mirror = orient in (4, 5, 6, 7, 9)
                        for e in own:
                            ents.append({**_placed(e, at, -deg, mirror), "layer": layer, **({"clear": True} if neg != bool(e.get("clear")) else {})})
                pad(s, at, deg, neg)
            elif tag == "A":
                a, b, c = P(f[1], f[2]), P(f[3], f[4]), P(f[5], f[6])
                s = syms.get(int(f[7]), (None, None))[1]
                cw = f[10].upper() == "Y" if len(f) > 10 else True
                r = math.hypot(a[0] - c[0], a[1] - c[1])
                a0, a1 = math.degrees(math.atan2(a[1] - c[1], a[0] - c[0])), math.degrees(math.atan2(b[1] - c[1], b[0] - c[0]))
                s0, s1 = (a1, a0) if cw else (a0, a1)
                e = {"t": "arc", "c": c, "r": round(r, 6), "a0": round(s0, 6), "a1": round(s1, 6), **({"w": round(s[1], 6)} if s else {})}
                if math.hypot(a[0] - b[0], a[1] - b[1]) < 1e-9:
                    e = {"t": "circle", "c": c, "r": round(r, 6), **({"w": round(s[1], 6)} if s else {})}
                if f[8] == "N":
                    e["clear"] = True
                ents.append({"layer": layer, **e})
            elif tag == "S":
                surface = {"neg": f[1] == "N", "contours": []}
            elif tag == "OB" and surface is not None:
                contour = {"pts": [P(f[1], f[2])], "hole": len(f) > 3 and f[3].upper() == "H"}
            elif tag == "OS" and contour is not None:
                contour["pts"].append(P(f[1], f[2]))
            elif tag == "OC" and contour is not None:
                e, c = P(f[1], f[2]), P(f[3], f[4])
                s = contour["pts"][-1]
                r = math.hypot(s[0] - c[0], s[1] - c[1])
                cw = f[5].upper() == "Y" if len(f) > 5 else True
                contour["pts"] += [_r6(p) for p in _arc_pts(c, r, math.atan2(s[1] - c[1], s[0] - c[0]), math.atan2(e[1] - c[1], e[0] - c[0]), not cw)]
            elif tag == "OE" and contour is not None:
                surface["contours"].append(contour)
                contour = None
            elif tag == "SE" and surface is not None:
                for cnt in surface["contours"]:
                    if len(cnt["pts"]) < 3:
                        continue
                    e = {"t": "poly", "pts": cnt["pts"][:-1] if cnt["pts"][0] == cnt["pts"][-1] else cnt["pts"], "closed": True, "fill": True}
                    if surface["neg"] != cnt["hole"]:
                        e["clear"] = True
                    ents.append({"layer": layer, **e})
                surface = None
        except (IndexError, ValueError):
            continue
    return ents, missing


def _placed(e, at, deg, mirror):
    """A shape of a symbol (around 0, 0) at a pad: mirrored in x, turned by deg, moved to at."""
    def tr(q):
        x, y = (-q[0] if mirror else q[0]), q[1]
        return _r6([at[0] + r[0], at[1] + r[1]]) if (r := _rot([x, y], deg)) else None
    m = {k: v for k, v in e.items() if k not in ("layer", "id", "clear")}
    for key in ("a", "b", "c"):
        if key in m:
            m[key] = tr(m[key])
    if "pts" in m:
        m["pts"] = [tr(q) for q in m["pts"]]
    if m.get("t") == "arc":
        a0, a1 = m["a0"], m["a1"]
        if mirror:
            a0, a1 = 180 - a1, 180 - a0
        m["a0"], m["a1"] = round(a0 + deg, 6), round(a1 + deg, 6)
    return m


def read_odb(files: dict):
    """{path: bytes} of an ODB++ job (unpacked) -> the drawing JSON."""
    def low(p):
        return p.replace("\\", "/").lower()
    paths = {low(p): p for p in files}
    roots = [p[: -len("matrix/matrix")] for p in paths if p.endswith("matrix/matrix")]
    if not roots:
        raise ImportError_("no ODB++ job in it (matrix/matrix not found)")
    root = roots[0]
    rows = _odb_matrix(files[paths[root + "matrix/matrix"]].decode("latin-1", "ignore"))
    steps = sorted({p[len(root) + len("steps/"):].split("/", 1)[0] for p in paths if p.startswith(root + "steps/")})
    step = next((s for s in steps if s in ("pcb", "pcb1", "board")), None) or next((s for s in steps if any(q.startswith(f"{root}steps/{s}/layers/") for q in paths)), steps[0] if steps else None)
    if not step:
        raise ImportError_("the ODB++ job has no step")

    def get(rel):
        for name in (rel, rel + ".z"):
            p = paths.get(root + name)
            if p:
                return unlzw(files[p]).decode("latin-1", "ignore")
        return None

    own_syms = {}

    def user(name):
        """The job's own symbol (symbols/<name>/features) as shapes around (0, 0), read once."""
        key = name.lower()
        if key not in own_syms:
            text = get(f"symbols/{key}/features")
            own_syms[key] = _odb_features(text, "", INCH)[0] if text else None
        return own_syms[key]

    layers, ents, missing = [], [], set()
    prof = get(f"steps/{step}/profile")
    if prof:
        got, _ = _odb_features(prof, "profile", INCH)
        got = [{**e, "fill": False} if e["t"] == "poly" else e for e in got]
        if got:
            layers.append({"name": "profile", "color": COLORS["outline"], "visible": True, "kind": "outline"})
            ents += got
    signals = [r for r in rows if _ODB_KIND.get(r.get("TYPE", "").lower()) == "copper" and r.get("CONTEXT", "").upper() == "BOARD"]
    for r in rows:
        name = r.get("NAME", "").lower()
        text = get(f"steps/{step}/layers/{name}/features")
        if not text:
            continue
        base = _ODB_KIND.get(r.get("TYPE", "").lower(), "other")
        if r.get("CONTEXT", "").upper() != "BOARD" and base != "assembly":
            base = "other"
        side = "top" if "top" in name or (signals and base == "copper" and r is signals[0]) else "bottom" if "bot" in name or (signals and base == "copper" and r is signals[-1]) else None
        kind = {"copper": f"copper_{side or 'inner'}", "mask": f"mask_{side or 'top'}", "paste": f"paste_{side or 'top'}",
                "silk": f"silk_{side or 'top'}"}.get(base, base)
        got, miss = _odb_features(text, r.get("NAME", name), INCH, user)
        missing |= miss
        if not got:
            continue
        layers.append({"name": r.get("NAME", name), "color": COLORS.get(kind, COLORS["other"]), "visible": kind in SHOWN, "kind": kind})
        ents += got
    if not layers:
        raise ImportError_("the ODB++ job has no layers with features")
    layers.sort(key=lambda l: ORDER.index(l["kind"]) if l["kind"] in ORDER else 0)
    for i, e in enumerate(ents):
        e["id"] = f"e{i + 1}"
    issues = [f"{len(missing)} pad shape(s) of the job's own ({', '.join(sorted(missing)[:5])}…) are not drawn."] if missing else []
    return {"unit": "mm", "file_units": "mm", "units_declared": True, "layers": layers, "entities": ents, "issues": issues, "pcb": "odb", "step": step}


# ------------------------------------------------------------------ archives
def _tar_files(data):
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tf:
        return {m.name: tf.extractfile(m).read() for m in tf.getmembers() if m.isfile()}


def read_pcb(data: bytes, name: str):
    """A .zip / .tgz / single Gerber or drill file -> the drawing JSON, or None when it is no PCB data."""
    low = name.lower()
    if low.endswith((".tgz", ".tar.gz", ".tar")):
        return read_odb(_tar_files(data))
    if low.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names = [n for n in z.namelist() if not n.endswith("/")]
            if any(n.lower().endswith("matrix/matrix") for n in names):
                return read_odb({n: z.read(n) for n in names})
            tgz = [n for n in names if n.lower().endswith((".tgz", ".tar.gz"))]
            gerb = [(n, z.read(n)) for n in names if not n.lower().endswith(NOT_PCB)]
            got = [(n, d) for n, d in gerb if len(d) < 200_000_000]
            if any(_looks_gerber(d[:20000].decode("latin-1", "ignore")) for _, d in got):
                return read_gerber_set(got)
            for t in tgz:  # an ODB++ job packed inside
                try:
                    return read_odb(_tar_files(z.read(t)))
                except ImportError_:
                    continue
        return None
    return read_gerber_set([(name, data)])
