"""⚖ Mass properties of a model part: volume, surface area, centre of mass (kernel.centre, the mesh's `cog` / `area`)
and mass = volume × density — against analytic values: a block's centre in its middle, an L's by the area formula, a
hole cut off-centre moving it away, two separate solids weighted by their volumes, the centre kept through a STEP write
-> read. Skipped without the CAD kernel (the mass formula is not).

Run:  python -m unittest discover -s tests -p "test_mass_props.py" -v
"""
import math
import unittest

from auto3d.modeler import available
from auto3d.modeler.materials import DENSITY, mass_g

OCC = available("occ")
if OCC:
    from auto3d.modeler import doc, packed
    from auto3d.modeler import kernel as K
    from test_modeler_kernel import watertight


def profile(pts, d, sid="S1", eid="E1", z=0):
    """A closed polygon on XY (offset z) extruded d up."""
    keys = [f"p{i + 1}" for i in range(len(pts))]
    lines = [{"id": f"l{i + 1}", "t": "line", "a": keys[i], "b": keys[(i + 1) % len(pts)]} for i in range(len(pts))]
    plane = {"datum": "XY", **({"offset": z} if z else {})}
    return [{"id": sid, "type": "sketch", "plane": plane, "points": dict(zip(keys, pts)), "entities": lines},
            {"id": eid, "type": "extrude", "sketch": sid, "op": "add", "d": d}]


L_PTS = [[0, 0], [40, 0], [40, 10], [10, 10], [10, 30], [0, 30]]  # an L: a 40 × 10 foot and a 10 × 20 upright on it


class TestMassFormula(unittest.TestCase):
    def test_mass_is_volume_times_density(self):
        self.assertAlmostEqual(mass_g(8000, "PLA"), 8 * 1.24)  # 8 cm³ of PLA
        self.assertAlmostEqual(mass_g(8000, "steel"), 8 * 7.85)
        self.assertAlmostEqual(mass_g(8000), mass_g(8000, "PLA"))  # none chosen: PLA
        self.assertAlmostEqual(mass_g(8000, "unobtainium"), 8 * DENSITY["PLA"])
        self.assertEqual(mass_g(0, "brass"), 0)


@unittest.skipUnless(OCC, "OCP not installed")
class TestMassProps(unittest.TestCase):
    def body(self, features):
        r = doc.rebuild({"features": features})
        self.assertTrue(r["ok"], r["features"])
        return r["body"]

    def test_block_centre_in_its_middle(self):
        b = self.body(profile([[0, 0], [40, 0], [40, 20], [0, 20]], 10))
        self.assertAlmostEqual(b["volume"], 8000, delta=1e-6)
        self.assertEqual(b["cog"], [20, 10, 5])
        self.assertAlmostEqual(b["area"], 2 * (40 * 20 + 40 * 10 + 20 * 10), delta=1e-6)
        self.assertTrue(watertight(b))
        # a block away from the origin: its centre moves with it
        b = self.body(profile([[-30, 5], [-10, 5], [-10, 45], [-30, 45]], 6, z=12))
        for got, want in zip(b["cog"], [-20, 25, 15]):
            self.assertAlmostEqual(got, want, delta=1e-6)

    def test_l_shape_centre_by_formula(self):
        """x̄ = Σ Aᵢ·xᵢ / Σ Aᵢ over the foot (400 mm² at 20, 5) and the upright (200 mm² at 5, 20)."""
        b = self.body(profile(L_PTS, 5))
        parts = [(40 * 10, 20, 5), (10 * 20, 5, 20)]
        A = sum(a for a, _, _ in parts)
        self.assertAlmostEqual(b["volume"], A * 5, delta=1e-6)
        self.assertAlmostEqual(b["cog"][0], sum(a * x for a, x, _ in parts) / A, delta=1e-4)  # 15
        self.assertAlmostEqual(b["cog"][1], sum(a * y for a, _, y in parts) / A, delta=1e-4)  # 10
        self.assertAlmostEqual(b["cog"][2], 2.5, delta=1e-4)
        self.assertAlmostEqual(b["area"], 2 * A + 140 * 5, delta=1e-6)  # both ends and the sides (perimeter 140)
        self.assertAlmostEqual(mass_g(b["volume"], "aluminium"), 3 * 2.7, delta=1e-6)

    def test_hole_moves_the_centre_away(self):
        """A Ø10 through hole at x 30 of the 40 × 20 × 10 block: x̄ = (8000·20 − π·25·10·30) / (8000 − π·25·10)."""
        top = {"face": {"name": "E1:end"}, "frame": {"o": [20, 10, 10], "x": [1, 0, 0], "n": [0, 0, 1]}}
        hole = {"id": "H1", "type": "hole", "plane": top, "points": [[10, 0]], "d": 10, "through": True}
        b = self.body([*profile([[0, 0], [40, 0], [40, 20], [0, 20]], 10), hole])
        vh = math.pi * 25 * 10
        self.assertAlmostEqual(b["volume"], 8000 - vh, delta=1e-3)
        self.assertAlmostEqual(b["cog"][0], (8000 * 20 - vh * 30) / (8000 - vh), delta=1e-3)
        self.assertAlmostEqual(b["cog"][1], 10, delta=1e-4)
        self.assertAlmostEqual(b["cog"][2], 5, delta=1e-4)
        self.assertTrue(watertight(b))

    def test_two_solids_weighted_by_volume(self):
        """Two blocks not touching (one part, two bodies): their centres weighted by their volumes."""
        b = self.body([*profile([[0, 0], [10, 0], [10, 10], [0, 10]], 10),
                       *profile([[30, 0], [50, 0], [50, 10], [30, 10]], 10, sid="S2", eid="E2")])
        self.assertEqual(b["solids"], 2)
        self.assertAlmostEqual(b["volume"], 3000, delta=1e-6)
        self.assertAlmostEqual(b["cog"][0], (1000 * 5 + 2000 * 40) / 3000, delta=1e-4)
        self.assertAlmostEqual(b["cog"][1], 5, delta=1e-4)

    def test_centre_through_step(self):
        st, _ = doc.evaluate([*profile(L_PTS, 5)])
        c0 = K.centre(st.body.shape)
        back = K.from_step(K.to_step(st.body.shape))
        self.assertAlmostEqual(K.volume(back), 3000, delta=3000 * 1e-6)
        for a, b in zip(K.centre(back), c0):
            self.assertAlmostEqual(a, b, delta=1e-4)

    def test_centre_comes_with_the_volume(self):
        """centre() after volume() of the same shape integrates nothing again (kept with it)."""
        st, _ = doc.evaluate([*profile(L_PTS, 5)])
        shape = st.body.shape
        K.volume(shape)
        self.assertTrue(any(s is shape for s, _ in K._volumes))
        self.assertEqual(K._mass_props(shape)[1], K.centre(shape))

    def test_packed_message_carries_them(self):
        """The binary rebuild answer (packed) has the body's cog and area for the browser."""
        r = doc.rebuild({"features": profile(L_PTS, 5)})
        back = packed.unpack(packed.pack(r))
        self.assertEqual(back["body"]["cog"], r["body"]["cog"])
        self.assertAlmostEqual(back["body"]["area"], 1900, delta=1e-6)


if __name__ == "__main__":
    unittest.main()
