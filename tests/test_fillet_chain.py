"""⛓ Tangent chains for fillet / chamfer: a box with rounded corners has two chains of 8 edges (its top and bottom
outlines); one picked edge of a chain rounds the whole chain (OpenCASCADE's way) — the volume against Pappus, every
new face named, watertight, read back from STEP; ⛓ off (chain: false) warns that the rounding goes on.

Run:  py -m unittest tests.test_fillet_chain -v
"""
import math
import unittest

from auto3d.modeler import available
from test_modeler_kernel import watertight

OCC = available("occ")
if OCC:
    from auto3d.modeler import doc, kernel as K
    from test_modeler_features import box, vol

R = 3  # the box's corners rounded R 3 (40 x 20 x 10)
CORNERS = {"id": "C", "type": "fillet", "r": R, "edges": [
    {"a": f"E1:side:l{i}", "b": f"E1:side:l{i % 4 + 1}", "fp": p} for i, p in zip(range(1, 5), ([40, 0, 5], [40, 20, 5], [0, 20, 5], [0, 0, 5]))]}
TOP_FRONT = {"a": "E1:end", "b": "E1:side:l1", "fp": [20, 0, 10]}
BASE = 8000 - 4 * (R * R - math.pi * R * R / 4) * 10


def removed(area, xbar):
    """What a rounding / bevel of the rounded box's top outline takes: its cross-section along the straight sides
    (2 × 34 + 2 × 14) and turned round the four corners (Pappus: at R − its centroid's distance from the wall)."""
    return area * (2 * (40 - 2 * R) + 2 * (20 - 2 * R) + 2 * math.pi * (R - xbar))


@unittest.skipUnless(OCC, "OCP not installed")
class TestTangentChain(unittest.TestCase):
    def test_chains_in_the_mesh(self):
        """The rounded box's edges: two chains of 8 (top and bottom outlines); a plain box has none."""
        r, v = vol(*box(), CORNERS)
        self.assertAlmostEqual(v, BASE, delta=1e-4)
        ch = [e["chain"] for e in r["body"]["edges"] if "chain" in e]
        self.assertEqual(sorted(ch.count(k) for k in set(ch)), [8, 8])
        r, _ = vol(*box())
        self.assertFalse(any("chain" in e for e in r["body"]["edges"]))

    def test_one_edge_rounds_its_chain(self):
        """A fillet R1 on one top edge rounds all 8 edges of the top outline: (1 − π/4) swept round it; every face of
        it named F:round:0; the same with all 8 edges picked (the ⛓ click); watertight; STEP round trip."""
        fil = {"id": "F", "type": "fillet", "edges": [TOP_FRONT], "r": 1}
        r, v = vol(*box(), CORNERS, fil)
        self.assertTrue(r["ok"], r["features"])
        want = BASE - removed(1 - math.pi / 4, (10 - 3 * math.pi) / (12 - 3 * math.pi))
        self.assertAlmostEqual(v, want, delta=1e-3)
        self.assertTrue(watertight(r["body"]))
        self.assertEqual(sum(1 for f in r["body"]["faces"] if f.get("name") == "F:round:0"), 8)
        self.assertTrue(all(f.get("name") for f in r["body"]["faces"]), [f.get("name") for f in r["body"]["faces"]])
        self.assertEqual(r["features"][-1]["warnings"], [])
        self.assertAlmostEqual(K.volume(K.from_step(doc.export({"features": [*box(), CORNERS, fil]}, "step"))), v, delta=0.05)
        # all the chain's edges picked (as the panel's ⛓ click stores them): the same part
        rc, _ = vol(*box(), CORNERS)
        b = rc["body"]
        k = next(e["chain"] for e in b["edges"] if e["mid"] == [20, 0, 10])
        refs = [{"a": b["faces"][e["faces"][0]]["name"], "b": b["faces"][e["faces"][1]]["name"], "fp": e["mid"]} for e in b["edges"] if e.get("chain") == k]
        self.assertEqual(len(refs), 8)
        r2, v2 = vol(*box(), CORNERS, {**fil, "edges": refs})
        self.assertTrue(r2["ok"], r2["features"])
        self.assertAlmostEqual(v2, v, delta=1e-6)

    def test_chamfer_chain_and_chain_off(self):
        """A chamfer 1 on one top edge bevels the top outline: ½ swept round it (centroid 1/3 in). ⛓ off: the same
        part, and a warning that it goes on along 7 more edges."""
        ch = {"id": "B", "type": "chamfer", "edges": [TOP_FRONT], "d": 1}
        r, v = vol(*box(), CORNERS, ch)
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, BASE - removed(0.5, 1 / 3), delta=1e-3)
        self.assertTrue(watertight(r["body"]))
        r, v2 = vol(*box(), CORNERS, {**ch, "chain": False})
        self.assertAlmostEqual(v2, v, delta=1e-6)
        self.assertIn("7 more edge(s)", r["features"][-1]["warnings"][0])
        # a sharp box edge (no chain): ⛓ off says nothing
        r, _ = vol(*box(), {**ch, "chain": False})
        self.assertEqual(r["features"][-1]["warnings"], [])

    def test_a_disc_and_its_hole_are_not_one_chain(self):
        """The AI's report: a Ø70 × 10 disc with a Ø9.5 hole through at (6, 13) — the top outer circle and the hole's
        top rim are not joined, so neither is in a chain; R2 on the outer edge rounds that edge alone: (4 − π) turned
        round the axis at 35 − its centroid's distance from the wall (Pappus); one face F:round:0, watertight, no
        warning with ⛓ off either, STEP round trip. The rounded box's top outline still is one chain of 8."""
        disc = [{"id": "S1", "type": "sketch", "plane": {"datum": "XY"}, "points": {"c": [0, 0]}, "entities": [{"id": "k", "t": "circle", "c": "c", "r": 35}]},
                {"id": "E1", "type": "extrude", "sketch": "S1", "op": "add", "d": 10},
                {"id": "H", "type": "hole", "plane": {"face": {"name": "E1:end"}, "frame": {"o": [0, 0, 10], "x": [1, 0, 0], "n": [0, 0, 1]}},
                 "points": [[6, 13]], "d": 9.5, "through": True}]
        r, v0 = vol(*disc)
        self.assertAlmostEqual(v0, math.pi * (35 ** 2 - 4.75 ** 2) * 10, delta=1e-3)
        self.assertFalse([e for e in r["body"]["edges"] if "chain" in e])
        fil = {"id": "F", "type": "fillet", "edges": [{"a": "E1:end", "b": "E1:side:k", "fp": [-35, 0, 10]}], "r": 2}
        r, v = vol(*disc, fil)
        self.assertTrue(r["ok"], r["features"])
        xbar = 2 * (10 - 3 * math.pi) / (12 - 3 * math.pi)
        self.assertAlmostEqual(v, v0 - (4 - math.pi) * 2 * math.pi * (35 - xbar), delta=1e-2)
        self.assertEqual(sum(1 for f in r["body"]["faces"] if f.get("name") == "F:round:0"), 1)
        self.assertTrue(watertight(r["body"]))
        self.assertEqual(r["features"][-1]["warnings"], [])
        r, _ = vol(*disc, {**fil, "chain": False})
        self.assertEqual(r["features"][-1]["warnings"], [])
        self.assertAlmostEqual(K.volume(K.from_step(doc.export({"features": [*disc, fil]}, "step"))), v, delta=0.05)
        r, _ = vol(*box(), CORNERS)
        top = [e for e in r["body"]["edges"] if "chain" in e and abs(e["mid"][2] - 10) < 1e-6]
        self.assertEqual(len(top), 8)
        self.assertEqual(len({e["chain"] for e in top}), 1)

    def test_chains_as_the_fillet_builder_finds_them(self):
        """tangent_chains gives the fillet builder only the edges that meet another nearly in line (_smooth_ends) —
        the same chains as giving it every edge: the rounded box with a hole through it, and with a bevelled top."""
        from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
        from OCP.TopoDS import TopoDS

        def every_edge(shape, em, adj):
            mk = BRepFilletAPI_MakeFillet(shape)
            for ei in range(1, em.Extent() + 1):
                e = TopoDS.Edge(em.FindKey(ei))
                if len(adj.get(ei, ())) == 2 and not mk.Contour(e):
                    try:
                        mk.Add(1.0, e)
                    except Exception:  # noqa: BLE001 — (a smooth edge)
                        pass
            return [sorted(em.FindIndex(mk.Edge(ic, j)) for j in range(1, mk.NbEdges(ic) + 1)) for ic in range(1, mk.NbContours() + 1) if mk.NbEdges(ic) > 1]

        def groups(ch):
            out = {}
            for ei, k in ch.items():
                out.setdefault(k, []).append(ei)
            return sorted(sorted(g) for g in out.values())

        top = {"face": {"name": "E1:end"}, "frame": {"o": [20, 10, 10], "x": [1, 0, 0], "n": [0, 0, 1]}}
        parts = [box() + [CORNERS, {"id": "H", "type": "hole", "plane": top, "points": [[8, 0]], "d": 5, "through": True}],
                 box() + [CORNERS, {"id": "B", "type": "chamfer", "edges": [TOP_FRONT], "d": 1}]]
        for features in parts:
            st, _ = doc.evaluate(features)
            _, em, adj = K._adjacency(st.body.shape)
            got = groups(K.tangent_chains(st.body.shape, em, adj))
            self.assertTrue(got)
            self.assertEqual(got, sorted(every_edge(st.body.shape, em, adj)))


if __name__ == "__main__":
    unittest.main()
