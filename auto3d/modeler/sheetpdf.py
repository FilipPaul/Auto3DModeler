"""A drawing sheet's SVG (mm, as web/js/sheet/sheet.js draws it) -> PDF pages, with the title-block styles' own fonts.

MuPDF's SVG reader draws every text in its base fonts (Helvetica …), whatever the SVG asks for. The title-block and
parts-list styles A–E (web/js/sheet/tbstyles.js) are set in IBM Plex Sans (Condensed), Barlow and Inter — each of
their texts says its font (data-ff) and weight. Those texts are taken out of the SVG before it is converted and
written on the page afterwards with the same font files the browser uses (web/fonts, OFL), at the same baseline,
anchor (start / middle / end), size, colour and letter spacing. A letter a font lacks (◇, ⌀) is written in
Helvetica, else MuPDF's fallback font.
"""
from __future__ import annotations

import html
import re
from functools import lru_cache
from pathlib import Path

FONTS = Path(__file__).resolve().parents[2] / "web" / "fonts"
FACES = {"plexc": ("IBMPlexSansCondensed", (400, 600, 700)), "plex": ("IBMPlexSans", (400, 500, 600, 700)),
         "barlow": ("Barlow", (400, 600, 700)), "inter": ("Inter", (400, 500, 600, 700))}
WEIGHT = {400: "Regular", 500: "Medium", 600: "SemiBold", 700: "Bold"}
TEXT = re.compile(r'<text\b([^>]*\bdata-ff="(\w+)"[^>]*)>(.*?)</text>', re.S)
ATTR = re.compile(r'([\w:-]+)="([^"]*)"')
MM = 72 / 25.4


@lru_cache(maxsize=None)
def font(ff: str, weight: int):
    """The style's font file nearest the weight (fitz.Font), or None (no such font: Helvetica)."""
    import fitz
    face = FACES.get(ff)
    if not face:
        return None
    w = min(face[1], key=lambda x: (abs(x - weight), -x))
    path = FONTS / f"{face[0]}-{WEIGHT[w]}.ttf"
    return fitz.Font(fontfile=str(path)) if path.exists() else None


@lru_cache(maxsize=None)
def _fallback(bold: bool):
    import fitz
    return fitz.Font("hebo" if bold else "helv"), fitz.Font("cjk")


def styled_texts(svg: str):
    """The SVG without its styled texts, and those texts [{x, y, s, size, ff, weight, fill, anchor, ls}] (mm)."""
    out = []

    def take(m):
        a = dict(ATTR.findall(m.group(1)))
        try:
            out.append({"x": float(a.get("x", 0)), "y": float(a.get("y", 0)), "s": html.unescape(re.sub(r"<[^>]+>", "", m.group(3))),
                        "size": float(a.get("font-size", 3)), "ff": m.group(2), "weight": int(float(a.get("font-weight", 400) or 400)),
                        "fill": a.get("fill", "#000"), "anchor": a.get("text-anchor", "start"), "ls": float(a.get("letter-spacing", 0) or 0)})
        except ValueError:
            return m.group(0)  # (one it cannot read: left to MuPDF)
        return ""

    return TEXT.sub(take, svg), out


def _rgb(c: str):
    c = (c or "#000").strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    try:
        return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return (0, 0, 0)


def _runs(s: str, f, bold: bool):
    """The text in runs of one font each: the style's, else Helvetica / the fallback where it has no letter."""
    runs = []
    for ch in s:
        use = f
        if f is None or not f.has_glyph(ord(ch)):
            helv, cjk = _fallback(bold)
            use = helv if helv.has_glyph(ord(ch)) else cjk
        if runs and runs[-1][0] is use:
            runs[-1][1] += ch
        else:
            runs.append([use, ch])
    return runs


def write_texts(page, texts, k: float):
    """The styled texts on a PDF page (k: points per SVG unit)."""
    import fitz
    writers = {}
    for t in texts:
        if not t["s"].strip():
            continue
        f, size = font(t["ff"], t["weight"]), t["size"] * k
        runs, ls = _runs(t["s"], f, t["weight"] >= 600), t["ls"] * k
        width = sum(r[0].text_length(r[1], fontsize=size) for r in runs) + ls * len(t["s"])
        x = t["x"] * k - (width if t["anchor"] == "end" else width / 2 if t["anchor"] == "middle" else 0)
        y = t["y"] * k
        tw = writers.setdefault(t["fill"], fitz.TextWriter(page.rect))
        for use, part in runs:
            if ls:
                for ch in part:
                    tw.append((x, y), ch, font=use, fontsize=size)
                    x += use.text_length(ch, fontsize=size) + ls
            else:
                tw.append((x, y), part, font=use, fontsize=size)
                x += use.text_length(part, fontsize=size)
    for fill, tw in writers.items():
        tw.write_text(page, color=_rgb(fill))


def pdf(svg) -> bytes:
    """The sheet as the browser drew it (SVG, mm) -> a PDF; several SVGs (a drawing set) -> one PDF, a page each."""
    import fitz
    out = fitz.open()
    for one in [svg] if isinstance(svg, str) else list(svg):
        plain, texts = styled_texts(str(one))
        page_doc = fitz.open("pdf", fitz.open(stream=plain.encode("utf-8"), filetype="svg").convert_to_pdf())
        if texts:
            vb = re.search(r'viewBox="\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)', plain)
            page = page_doc[0]
            write_texts(page, texts, page.rect.width / float(vb.group(1)) if vb else MM)
        out.insert_pdf(page_doc)
    try:
        out.subset_fonts()  # (only the letters used: a small file)
    except Exception:  # noqa: BLE001 — without fontTools: the whole (already small) fonts
        pass
    return out.tobytes(garbage=3, deflate=True)
