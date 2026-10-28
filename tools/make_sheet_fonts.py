"""Make web/fonts/: the title-block styles' fonts (OFL), static weights cut down to the letters a drawing needs.

The drawing sheet's title-block and parts-list styles A–E (web/js/sheet/tbstyles.js) use IBM Plex Sans Condensed,
IBM Plex Sans, Barlow and Inter. The browser shows them through web/fonts/fonts.css; the PDF (auto3d/modeler/sheet.py
pdf) embeds the same files. Google Fonts keeps IBM Plex Sans and Inter as variable fonts only — PyMuPDF writes a
font's default instance — so their weights are cut out here (fontTools' instancer), and every file is subset to
Latin, Latin Extended-A (Czech) and the drawing symbols (Ø × ° ± · Σ …). Run once; the files are kept in the repo.

  py tools/make_sheet_fonts.py
"""
import io
import sys
import urllib.request
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

OUT = Path(__file__).resolve().parent.parent / "web" / "fonts"
RAW = "https://raw.githubusercontent.com/google/fonts/main/ofl/"
WEIGHTS = {400: "Regular", 500: "Medium", 600: "SemiBold", 700: "Bold"}
# family file stem -> (google fonts folder, static files | variable file + its axes, weights)
FAMILIES = {
    "IBMPlexSansCondensed": ("ibmplexsanscondensed", None, (400, 600, 700)),
    "IBMPlexSans": ("ibmplexsans", ("IBMPlexSans[wdth,wght].ttf", {"wdth": 100}), (400, 500, 600, 700)),
    "Barlow": ("barlow", None, (400, 600, 700)),
    "Inter": ("inter", ("Inter[opsz,wght].ttf", {"opsz": 14}), (400, 500, 600, 700)),
}
UNICODES = [*range(0x20, 0x7F), *range(0xA0, 0x180), 0x2C6, 0x2C7, 0x2D8, 0x2D9, 0x2DA, 0x2DB, 0x2DC, 0x2DD, 0x3A3, 0x3A9,
            0x3BC, 0x3C0, *range(0x2010, 0x2028), 0x2030, 0x2039, 0x203A, 0x20AC, 0x2116, 0x2122, 0x2190, 0x2191, 0x2192,
            0x2193, 0x2212, 0x2215, 0x2219, 0x221E, 0x2248, 0x2260, 0x2264, 0x2265, 0x2300, 0x25C7, 0x2316]


def get(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()


def cut(font: TTFont, path: Path):
    opts = subset.Options()
    opts.layout_features = ["kern", "liga", "calt", "tnum", "lnum", "case", "ccmp", "locl", "mark", "mkmk"]
    opts.name_IDs = ["*"]
    opts.notdef_outline = True
    opts.glyph_names = False
    sub = subset.Subsetter(opts)
    sub.populate(unicodes=UNICODES)
    sub.subset(font)
    font.save(path)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for stem, (folder, var, weights) in FAMILIES.items():
        (OUT / f"OFL-{stem}.txt").write_bytes(get(f"{RAW}{folder}/OFL.txt"))
        data = get(f"{RAW}{folder}/{var[0]}") if var else None
        for w in weights:
            if var:
                f = instancer.instantiateVariableFont(TTFont(io.BytesIO(data)), {**var[1], "wght": w}, updateFontNames=False)
            else:
                f = TTFont(io.BytesIO(get(f"{RAW}{folder}/{stem}-{WEIGHTS[w]}.ttf")))
            path = OUT / f"{stem}-{WEIGHTS[w]}.ttf"
            cut(f, path)
            print(path.name, path.stat().st_size // 1024, "kB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
