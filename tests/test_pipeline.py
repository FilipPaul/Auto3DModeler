"""End-to-end tests: PDF -> parametric model -> solve -> export.

Run:  python -m unittest discover -s tests -v
"""
import math
import struct
import unittest
from pathlib import Path

import fitz

from auto3d.export import build_solid, to_step, to_stl
from auto3d.sketch import build_model
from auto3d.solver import solve

SAMPLE = Path(__file__).resolve().parent.parent / "initial draft.pdf"


# --------------------------------------------------------------------------- synthetic drawings
class Drawing:
    """Tiny helper that writes drawings in the same style as the sample PDF (not to scale on purpose)."""

    def __init__(self):
        self.doc = fitz.open()
        self.page = self.doc.new_page(width=600, height=400)

    def outline(self, pts, closed=True):
        sh = self.page.new_shape()
        seq = pts + [pts[0]] if closed else pts
        for a, b in zip(seq, seq[1:]):
            sh.draw_line(a, b)
        sh.finish(width=0.9, color=(0.2, 0.2, 0.2), closePath=closed)
        sh.commit()

    def _arrow(self, tip, d):
        L, W = 6, 3.4
        bx, by = tip[0] - d[0] * L, tip[1] - d[1] * L
        px, py = -d[1] * W, d[0] * W
        sh = self.page.new_shape()
        sh.draw_polyline([tip, (bx + px, by + py), (bx - px, by - py), tip])
        sh.finish(width=0.2, color=(0.2, 0.2, 0.2), fill=(0.2, 0.2, 0.2), closePath=True)
        sh.commit()

    def dim(self, a, b, label):
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy)
        d = (dx / n, dy / n)
        sh = self.page.new_shape()
        sh.draw_line(a, b)
        sh.finish(width=0.225, color=(0.2, 0.2, 0.2))
        sh.commit()
        self._arrow(b, d)
        self._arrow(a, (-d[0], -d[1]))
        if label is not None:
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            if abs(d[0]) > 0.5:
                self.page.insert_text((mx - 8, my - 3), label, fontsize=6)
            else:
                self.page.insert_text((mx + 3, my + 2), label, fontsize=6)

    def text(self, at, s):
        self.page.insert_text(at, s, fontsize=6)

    def bytes(self):
        return self.doc.tobytes()


def plate(labels=("100mm", "40mm"), extra=None):
    """A 100 x 40 plate drawn at 200 x 60 pt (i.e. not to scale)."""
    dr = Drawing()
    dr.outline([(100, 100), (300, 100), (300, 160), (100, 160)])
    if labels[0] is not False:
        dr.dim((100, 175), (300, 175), labels[0])
    if labels[1] is not False:
        dr.dim((85, 160), (85, 100), labels[1])
    if extra:
        extra(dr)
    return dr.bytes()


def codes(model):
    return {i["code"] for i in model["issues"]}


def named(model, name):
    return next(p for p in model["params"] if p["name"] == name)


# --------------------------------------------------------------------------- sample drawing
class SampleDrawingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model, _, _ = build_model(SAMPLE.read_bytes())
        cls.sol = solve(cls.model)

    def test_reads_all_twelve_dimensions(self):
        drawn = sorted((p["name"], p["value"]) for p in self.model["params"] if p["source"] == "drawing")
        self.assertEqual(drawn, sorted([
            ("Overall length", 78.7), ("Overall height", 11.0), ("Outline width 1", 14.5),
            ("Outline height 1", 1.5),
            ("Cutout 1 width", 4.0), ("Cutout 1 height", 1.5), ("Cutout 1 from left edge", 10.0),
            ("Cutout 1 from bottom edge", 0.5),
            ("Cutout 2 width", 4.0), ("Cutout 2 height", 1.5), ("Cutout 2 from right edge", 10.0),
            ("Cutout 2 from bottom edge", 0.5),
        ]))
        self.assertEqual(self.model["unit"], "cm")

    def test_geometry_follows_dimensions_not_drawing_scale(self):
        self.assertTrue(self.sol["ok"])
        self.assertEqual(self.sol["bbox"], [0.0, 0.0, 78.7, 11.0])
        outer, c1, c2 = (l["points"] for l in self.sol["loops"])
        self.assertIn([14.5, 9.5], outer)  # notch: 14.5 from left, 1.5 deep
        xs = lambda pts: sorted({round(p[0], 6) for p in pts})
        ys = lambda pts: sorted({round(p[1], 6) for p in pts})
        self.assertEqual(xs(c1), [10.0, 14.0])
        self.assertEqual(ys(c1), [0.5, 2.0])
        self.assertEqual(xs(c2), [64.7, 68.7])
        self.assertEqual(ys(c2), [0.5, 2.0])

    def test_reports_missing_notch_width_and_thickness(self):
        c = codes(self.model)
        self.assertIn("missing_dimension", c)
        self.assertIn("missing_thickness", c)
        self.assertIn("not_to_scale", c)
        self.assertFalse(any(i["severity"] == "error" for i in self.model["issues"]))
        notch = next(p for p in self.model["params"] if p["source"] == "estimated")
        self.assertTrue(20 < notch["value"] < 40)

    def test_parametric_change_propagates(self):
        p = named(self.model, "Overall length")
        sol = solve(self.model, {p["id"]: 100})
        self.assertTrue(sol["ok"])
        c2 = sol["loops"][2]["points"]
        # cutout 2 is dimensioned from the right edge, so it follows it
        self.assertEqual(sorted({round(q[0], 6) for q in c2}), [86.0, 90.0])

    def test_invalid_change_is_rejected_with_reason(self):
        w = named(self.model, "Cutout 1 width")
        sol = solve(self.model, {w["id"]: 80})
        self.assertFalse(sol["ok"])
        self.assertTrue(any("outer profile" in i["message"] for i in sol["issues"]))
        sol = solve(self.model, {w["id"]: -1})
        self.assertFalse(sol["ok"])

    def test_stl_is_watertight_and_in_mm(self):
        data = to_stl(build_solid(self.sol, self.model["unit"]), self.model["unit"])
        n = struct.unpack("<I", data[80:84])[0]
        edges, vol = {}, 0.0
        for i in range(n):
            v = struct.unpack("<9f", data[84 + 50 * i + 12: 84 + 50 * i + 48])
            tri = [tuple(round(c, 3) for c in v[k:k + 3]) for k in (0, 3, 6)]
            a, b, c = tri
            vol += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0])
                    + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6
            for k in range(3):
                e = (tri[k], tri[(k + 1) % 3])
                edges[e] = edges.get(e, 0) + 1
        self.assertTrue(all(edges.get((b, a)) == cnt for (a, b), cnt in edges.items()))
        expected = (787 * 110 - 298 * 15 - 2 * 40 * 15) * 10  # mm^3 at 1 cm thickness
        self.assertAlmostEqual(vol, expected, delta=expected * 1e-4)

    def test_step_structure(self):
        text = to_step(build_solid(self.sol, self.model["unit"]), self.model["unit"]).decode()
        self.assertTrue(text.startswith("ISO-10303-21;"))
        self.assertIn("MANIFOLD_SOLID_BREP", text)
        self.assertIn("SI_UNIT(.MILLI.,.METRE.)", text)
        # 2 caps + 8 outer sides + 2*4 cutout sides
        self.assertEqual(text.count("ADVANCED_FACE("), 18)


# --------------------------------------------------------------------------- failure modes
class ValidationTest(unittest.TestCase):
    def test_clean_plate(self):
        m, _, _ = build_model(plate())
        s = solve(m)
        self.assertEqual(m["unit"], "mm")
        self.assertEqual(s["bbox"], [0.0, 0.0, 100.0, 40.0])
        self.assertEqual(codes(m) & {"missing_dimension", "invalid_dimension", "conflicting_dimension"}, set())

    def test_invalid_label_is_reported_and_estimated(self):
        m, _, _ = build_model(plate(labels=("abc", "40mm")))
        err = [i for i in m["issues"] if i["code"] == "invalid_dimension"]
        self.assertEqual(len(err), 1)
        self.assertIn("abc", err[0]["message"])
        self.assertEqual(err[0]["severity"], "error")
        self.assertTrue(solve(m)["ok"])  # still produces a usable (estimated) model

    def test_missing_label(self):
        m, _, _ = build_model(plate(labels=(None, "40mm")))
        self.assertTrue(any(i["code"] == "invalid_dimension" and "no value label" in i["message"] for i in m["issues"]))

    def test_missing_dimension_estimated_from_proportions(self):
        m, _, _ = build_model(plate(labels=(False, "40mm")))
        est = [p for p in m["params"] if p["source"] == "estimated"]
        self.assertEqual(len(est), 1)
        # drawn 200 pt wide vs 60 pt high for 40 mm -> ~133 mm
        self.assertAlmostEqual(est[0]["value"], 133, delta=1)
        self.assertIn("missing_dimension", codes(m))

    def test_zero_value(self):
        m, _, _ = build_model(plate(labels=("0mm", "40mm")))
        self.assertIn("invalid_dimension", codes(m))

    def test_unattached_dimension(self):
        # the middle arrow tips (x=200) do not point at any edge of the plate
        m, _, _ = build_model(plate(extra=lambda d: (d.dim((100, 90), (200, 90), "60mm"),
                                                      d.dim((200, 90), (300, 90), "30mm"))))
        self.assertIn("unattached_dimension", codes(m))

    def test_conflicting_dimensions(self):
        # a step at x=220: 60 + 30 chained, but overall says 100
        dr = Drawing()
        dr.outline([(100, 100), (220, 100), (220, 120), (300, 120), (300, 160), (100, 160)])
        dr.dim((100, 175), (300, 175), "100mm")
        dr.dim((85, 160), (85, 100), "40mm")
        dr.dim((100, 90), (220, 90), "60mm")
        dr.dim((220, 110), (300, 110), "30mm")
        dr.dim((310, 160), (310, 120), "20mm")
        m, _, _ = build_model(dr.bytes())
        conflict = [i for i in m["issues"] if i["code"] == "conflicting_dimension"]
        self.assertEqual(len(conflict), 1, m["issues"])
        self.assertEqual(conflict[0]["severity"], "error")
        self.assertTrue(solve(m)["ok"])

    def test_redundant_consistent_dimension_is_reference(self):
        dr = Drawing()
        dr.outline([(100, 100), (220, 100), (220, 120), (300, 120), (300, 160), (100, 160)])
        dr.dim((100, 175), (300, 175), "100mm")
        dr.dim((85, 160), (85, 100), "40mm")
        dr.dim((100, 90), (220, 90), "60mm")
        dr.dim((220, 110), (300, 110), "40mm")
        dr.dim((310, 160), (310, 120), "20mm")
        m, _, _ = build_model(dr.bytes())
        self.assertNotIn("conflicting_dimension", codes(m))
        self.assertEqual(len([p for p in m["params"] if p["role"] == "reference"]), 1)

    def test_open_outline(self):
        dr = Drawing()
        dr.outline([(100, 100), (300, 100), (300, 160), (100, 160), (100, 110)], closed=False)
        m, _, _ = build_model(dr.bytes())
        self.assertIn("open_outline", codes(m))
        self.assertIn("no_geometry", codes(m))

    def test_no_dimensions(self):
        m, _, _ = build_model(plate(labels=(False, False)))
        self.assertIn("no_dimensions", codes(m))
        self.assertTrue(solve(m)["ok"])

    def test_thickness_note(self):
        m, _, _ = build_model(plate(extra=lambda d: d.text((120, 140), "t=18mm")))
        t = next(p for p in m["params"] if p["id"] == "thickness")
        self.assertEqual((t["value"], t["source"]), (18.0, "drawing"))
        self.assertNotIn("missing_thickness", codes(m))

    def test_not_a_pdf(self):
        with self.assertRaises(Exception):
            build_model(b"hello")


if __name__ == "__main__":
    unittest.main()
