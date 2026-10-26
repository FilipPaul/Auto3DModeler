"""PCB data -> 2D drawings: Gerber (apertures, macros, arcs, regions, polarity), Excellon (number formats, slots,
fitted onto the board), ODB++ (matrix, features, the job's own symbols, compressed .Z), and the DXF export."""
import io
import math
import tarfile
import unittest
import zipfile

from auto3d import pcb
from auto3d.drawing2d import read_drawing, to_dxf


def lzw_compress(data: bytes, maxbits=16) -> bytes:
    """Unix compress (.Z), block mode — to make test files (gzip -d reads them)."""
    out_bits, bitpos, n_bits, group = [], 0, 9, 0
    table = {bytes([i]): i for i in range(256)}
    free = 257
    buf = bytearray()

    def put(code):
        nonlocal bitpos
        for k in range(n_bits):
            if (code >> k) & 1:
                while len(buf) <= (bitpos + k) // 8:
                    buf.append(0)
                buf[(bitpos + k) // 8] |= 1 << ((bitpos + k) % 8)
        bitpos += n_bits
        while len(buf) < (bitpos + 7) // 8:
            buf.append(0)

    w = b""
    for ch in data:
        wc = w + bytes([ch])
        if wc in table:
            w = wc
            continue
        put(table[w])
        if free < (1 << maxbits):
            table[wc] = free
            free += 1
            if free > (1 << n_bits) and n_bits < maxbits:  # the next code is wider: the group of 8 codes is padded
                pad = (n_bits * 8 - (bitpos - group) % (n_bits * 8)) % (n_bits * 8)
                bitpos += pad
                while len(buf) < (bitpos + 7) // 8:
                    buf.append(0)
                group = bitpos
                n_bits += 1
        w = bytes([ch])
    if w:
        put(table[w])
    del out_bits
    return b"\x1f\x9d" + bytes([0x80 | maxbits]) + bytes(buf[: (bitpos + 7) // 8])


GERBER = """G04 a test board*
%FSLAX36Y36*%
%MOMM*%
%TF.FileFunction,Copper,L1,Top*%
%AMROUNDRECT*
0 a rectangle 2 x 1 and four circles*
21,1,$1,$2,0,0,0*
1,1,0.5,$3,0*%
%ADD10C,0.250*%
%ADD11R,2.000X1.000*%
%ADD12O,3.000X1.000*%
%ADD13P,2.000X6X0*%
%ADD14ROUNDRECT,2.0X1.0X0.75*%
%ADD15C,1.000*%
D10*
X0Y0D02*
X10000000Y0D01*
G03X0Y10000000I-10000000J0D01*
D11*
X20000000Y5000000D03*
D12*
X25000000Y5000000D03*
D13*
X30000000Y5000000D03*
D14*
X35000000Y5000000D03*
G36*
X40000000Y0D02*
G01X50000000Y0D01*
X50000000Y10000000D01*
X40000000Y10000000D01*
X40000000Y0D01*
G37*
%LPC*%
D15*
X45000000Y5000000D03*
%LPD*%
M02*
"""


class TestGerber(unittest.TestCase):
    def test_board(self):
        ents, issues = pcb.parse_gerber(GERBER, "top")
        self.assertEqual(issues, [])
        kinds = [(e["t"], bool(e.get("fill")), bool(e.get("clear"))) for e in ents]
        line, arc = ents[0], ents[1]
        self.assertEqual((line["t"], line["a"], line["b"], line["w"]), ("line", [0, 0], [10, 0], 0.25))
        # a quarter arc from (10, 0) round the origin to (0, 10), counter-clockwise
        self.assertEqual((arc["t"], arc["c"], arc["r"], arc["a0"], arc["a1"]), ("arc", [0, 0], 10, 0, 90))
        rect = ents[2]
        xs, ys = [p[0] for p in rect["pts"]], [p[1] for p in rect["pts"]]
        self.assertEqual((min(xs), max(xs), min(ys), max(ys)), (19, 21, 4.5, 5.5))
        obround, hexagon = ents[3], ents[4]
        self.assertAlmostEqual(max(p[0] for p in obround["pts"]) - min(p[0] for p in obround["pts"]), 3, places=5)
        self.assertEqual(len(hexagon["pts"]), 6)
        # the macro: its rectangle (2 x 1) and its circle (Ø0.5 at x 0.75), around (35, 5)
        macro = [e for e in ents[5:7]]
        self.assertEqual(macro[0]["t"], "poly")
        self.assertEqual(macro[1]["t"], "circle")
        self.assertAlmostEqual(macro[1]["c"][0], 35.75)
        self.assertAlmostEqual(macro[1]["r"], 0.25)
        region = ents[7]
        self.assertEqual((region["t"], region["fill"], len(region["pts"]) >= 4), ("poly", True, True))
        self.assertEqual(kinds[-1], ("circle", True, True))  # the clear (LPC) pad
        self.assertEqual(pcb.kind_of("x.gbr", GERBER), "copper_top")

    def test_inch_and_trailing_zeros(self):
        g = "%FSTAX24Y24*%%MOIN*%%ADD10C,0.01*%D10*X01Y0D02*X02Y0D01*M02*"  # trailing zeros dropped: X01 = 01.0000 in (X1 = 10 in)
        ents, _ = pcb.parse_gerber(g, "l")
        self.assertAlmostEqual(ents[0]["a"][0], 25.4)
        self.assertAlmostEqual(ents[0]["b"][0], 50.8)
        self.assertAlmostEqual(ents[0]["w"], 0.254)

    def test_missing_x_in_an_aperture(self):
        ents, _ = pcb.parse_gerber("%FSLAX24Y24*%%MOMM*%%ADD10R,0.03260.326*%D10*X0Y0D03*M02*", "l")
        xs = [p[0] for p in ents[0]["pts"]]
        self.assertAlmostEqual(max(xs) - min(xs), 0.0326, places=5)

    def test_step_and_repeat(self):
        g = "%FSLAX24Y24*%%MOMM*%%ADD10C,1*%%SRX3Y2I10J20*%D10*X0Y0D03*%SR*%M02*"
        ents, _ = pcb.parse_gerber(g, "l")
        self.assertEqual(sorted(tuple(e["c"]) for e in ents), sorted((10.0 * i, 20.0 * j) for i in range(3) for j in range(2)))


class TestExcellon(unittest.TestCase):
    def test_formats_and_slots(self):
        e, _ = pcb.parse_excellon("M48\nMETRIC,LZ,000.000\nT1C0.8\n%\nT1\nX010000Y020000\nX030000Y020000G85X040000Y020000\nM30\n", "drill")
        self.assertEqual((e[0]["t"], e[0]["c"], e[0]["r"]), ("circle", [10, 20], 0.4))
        self.assertEqual((e[1]["t"], e[1]["a"], e[1]["b"], e[1]["w"]), ("line", [30, 20], [40, 20], 0.8))
        e, _ = pcb.parse_excellon("M48\nINCH,TZ\nT1C0.0394\n%\nT1\nX10000Y5000\nM30\n", "drill")  # leading zeros dropped, 2:4
        self.assertAlmostEqual(e[0]["c"][0], 25.4)
        self.assertAlmostEqual(e[0]["r"], 0.0394 * 25.4 / 2)

    def test_fitted_onto_the_board(self):
        board = "%FSLAX24Y24*%%MOMM*%%ADD10C,0.1*%D10*X0Y0D02*X1000000Y0D01*X1000000Y500000D01*M02*"  # 100 x 50 mm
        drill = "M48\nM72\nT1C0.03\n%\nT1\nX1968500Y984250\nM30\n"  # 3 decimals not said: read as 196.85 in
        d = pcb.read_gerber_set([("b/top.gtl", board.encode()), ("b/board.drd", drill.encode())])
        hole = next(e for e in d["entities"] if e["t"] == "circle")
        self.assertTrue(0 <= hole["c"][0] <= 100 and 0 <= hole["c"][1] <= 50, hole)
        self.assertTrue(any("scaled" in i for i in d["issues"]))


def odb_job(compress=False):
    feats = """UNITS=MM
$0 r200
$1 rect1000x500
$2 my_pad
L 0 0 10 0 0 P 0
P 20 5 1 P 0 1
P 30 5 2 P 0 0
S P 0
OB 40 0 I
OS 50 0
OS 50 10
OS 40 10
OE
SE
"""
    profile = "UNITS=MM\nS P 0\nOB 0 0 I\nOS 60 0\nOS 60 20\nOS 0 20\nOE\nSE\n"
    sym = "UNITS=MM\n$0 r100\nP 0 0 0 P 0 0\nP 1 0 0 P 0 0\n"
    files = {
        "job/matrix/matrix": b"LAYER {\n ROW=1\n CONTEXT=BOARD\n TYPE=SIGNAL\n NAME=TOP\n POLARITY=POSITIVE\n}\n",
        "job/steps/pcb/profile": profile.encode(),
        "job/symbols/my_pad/features": sym.encode(),
    }
    if compress:
        files["job/steps/pcb/layers/top/features.Z"] = lzw_compress(feats.encode() * 3)
    else:
        files["job/steps/pcb/layers/top/features"] = feats.encode()
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


class TestODB(unittest.TestCase):
    def test_job(self):
        d = pcb.read_pcb(odb_job(), "job.tgz")
        self.assertEqual([(l["name"], l["kind"]) for l in d["layers"]], [("TOP", "copper_top"), ("profile", "outline")])
        top = [e for e in d["entities"] if e["layer"] == "TOP"]
        self.assertEqual((top[0]["t"], top[0]["b"], top[0]["w"]), ("line", [10, 0], 0.2))
        # rect 1 x 0.5 mm turned 90° (orient 1): 0.5 wide, 1 tall
        r = top[1]
        self.assertAlmostEqual(max(p[0] for p in r["pts"]) - min(p[0] for p in r["pts"]), 0.5)
        # the job's own symbol: its two pads, at (30, 5) and (31, 5)
        own = [e for e in top if e["t"] == "circle"]
        self.assertEqual(sorted(tuple(e["c"]) for e in own), [(30, 5), (31, 5)])
        self.assertTrue(any(e["t"] == "poly" and e.get("fill") and len(e["pts"]) == 4 for e in top))
        self.assertEqual(d["issues"], [])

    def test_compressed_features(self):
        data = b"UNITS=MM\nL 0 0 10 0 0 P 0\n" * 400
        self.assertEqual(pcb.unlzw(lzw_compress(data)), data)
        d = pcb.read_pcb(odb_job(compress=True), "job.tgz")
        self.assertEqual(len([e for e in d["entities"] if e["layer"] == "TOP"]), 3 * 5)  # 3 copies x (a line, a pad, the own symbol's 2, a surface)

    def test_in_a_zip(self):
        z = io.BytesIO()
        with zipfile.ZipFile(z, "w") as zf:
            zf.writestr("out/job.tgz", odb_job())
        self.assertEqual(read_drawing(z.getvalue(), "board.zip")["pcb"], "odb")


class TestDXF(unittest.TestCase):
    def test_round_trip(self):
        ents, _ = pcb.parse_gerber(GERBER, "Top copper")
        d = {"layers": [{"name": "Top copper", "color": "#d24b3c", "visible": True}], "entities": [{**e, "id": f"e{i}"} for i, e in enumerate(ents)]}
        back = read_drawing(to_dxf(d), "board.dxf")
        names = {l["name"] for l in back["layers"]}
        self.assertTrue({"Top copper", "Top copper_CLEAR"} <= names, names)
        self.assertEqual(sum(1 for e in back["entities"] if e["t"] == "arc"), 0)  # the wide arc is a polyline of its width
        self.assertTrue(any(e["t"] == "poly" for e in back["entities"]))


if __name__ == "__main__":
    unittest.main()
