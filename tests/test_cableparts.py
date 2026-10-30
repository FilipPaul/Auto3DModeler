"""📎 ⛓ Cable clips, ties and energy chains in the parts library (library/cableparts.json, auto3d/cableparts.py — the
same math as web/js/library/cableparts.js): every clip has its cable Ø range and its frames (the cable's axis across
its mounting normal, above its mounting face, inside the loop of a P-clamp); the clips for a bundle Ø are the snug
ones; the catalogue numbers as the makers give them; an energy chain laid out as a U is 2 × run + πR long with its
ends where they belong, for two travels; every part builds to its catalogue sizes (OCP)."""
import math
import unittest
from pathlib import Path

from auto3d import cableparts as C
from auto3d import library as L
from auto3d.modeler import available

APP = Path(__file__).resolve().parent.parent / "library"
OCC = available("occ")


def items():
    return [it for it in L.load(APP, Path("/nonexistent"))["items"] if it["file"] == "cableparts.json"]


def by_id():
    return {it["id"]: it for it in items()}


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


class TestClipData(unittest.TestCase):
    def test_fields_and_sources(self):
        its = items()
        kinds = {it["kind"] for it in its}
        self.assertEqual(kinds, {"clip", "tie mount", "tie", "chain"})
        for it in its:
            self.assertNotIn("problems", it, it["id"])
            top, maker, _ = it["category"].split(" / ")
            self.assertEqual(maker, it["maker"])
            self.assertEqual(top, {"clip": "Cable clips", "tie mount": "Cable clips", "tie": "Cable ties", "chain": "Energy chains"}[it["kind"]])
            self.assertEqual(it["accuracy"], "catalogue")
            self.assertTrue(it["name_cs"] and it["description_cs"] and "ozměry podle katalogu" in it["description_cs"], it["id"])
            for k in it["sizes"]:
                v = C.vars_of(it, k)
                page = it["page"].replace("{page}", str(v.get("page", "")))
                self.assertTrue(page.startswith("https://") and it["datasheet"].replace("{page}", str(v.get("page", ""))).startswith("https://"), (it["id"], k))
            self.assertNotIn(".step", str(it).lower())  # (links only: no maker's CAD files copied)

    def test_every_clip_has_its_range_and_frames(self):
        n = 0
        for it in items():
            if it["kind"] not in C.CLIP_KINDS:
                continue
            last = 0
            for k in it["sizes"]:
                f = C.clip_frames(it, k)
                v = C.vars_of(it, k)
                self.assertTrue(0 <= f["dmin"] < f["dmax"], (it["id"], k, f))
                self.assertGreaterEqual(f["dmax"], last)  # (the sizes in order: the smallest first)
                last = f["dmax"]
                ax, mo = f["axis"], f["mount"]
                self.assertAlmostEqual(math.hypot(*ax["d"]), 1, places=9)
                self.assertAlmostEqual(math.hypot(*mo["n"]), 1, places=9)
                self.assertAlmostEqual(dot(ax["d"], mo["n"]), 0, places=9, msg=(it["id"], k))  # (the cable runs along the face)
                rel = [a - b for a, b in zip(ax["o"], mo["o"])]
                height = -dot(rel, mo["n"])  # how far above its mounting face the cable's axis is
                self.assertGreaterEqual(height, f["dmax"] / 2 - 1e-9, (it["id"], k))  # (the cable clears the face)
                self.assertIn(mo["kind"], ("screw", "adhesive"))
                thread = float(mo["screw"].lstrip("M"))
                self.assertTrue(thread + 0.1 <= mo["hole"] + 1e-9, (it["id"], k, mo))  # the screw passes its hole
                if it["kind"] == "clip":  # a P-clamp: the cable's axis is the loop's centre, Ø D inside
                    self.assertAlmostEqual(height, v["WT"] + v["D"] / 2, places=9)
                    self.assertAlmostEqual(math.hypot(rel[0], rel[1]), v["F"], places=9)  # the screw hole F from the loop's centre
                    self.assertAlmostEqual(mo["seat"], 2 * v["WT"], places=9)
                else:  # a tie mount: the cable lies on top of it (Ø dc), 4-way
                    for dc in (f["dmin"], f["dmax"]):
                        g = C.clip_frames(it, k, dc)
                        self.assertAlmostEqual(-dot([a - b for a, b in zip(g["axis"]["o"], g["mount"]["o"])], g["mount"]["n"]), v["H"] + dc / 2, places=9)
                    self.assertAlmostEqual(dot(ax["d"], ax["d2"]), 0, places=9)
                    self.assertEqual(len(mo["holes"]), 2)
                    self.assertAlmostEqual(abs(mo["holes"][0][0] - mo["holes"][1][0]), v["F"], places=9)
                n += 1
        self.assertGreaterEqual(n, 11)

    def test_catalogue_numbers(self):
        """As HellermannTyton and igus give them."""
        its = by_id()
        h4 = its["ht-hp-pclamp"]["sizes"]["H4P"]
        self.assertEqual((h4["art"], h4["D"], h4["F"], h4["WT"]), ("211-60049", 8.0, 10.0, 1.2))
        self.assertEqual((its["ht-hp-pclamp"]["vars"]["W"], its["ht-hp-pclamp"]["vars"]["FH"]), (10.0, 4.2))
        mb3 = its["ht-mb-mount"]["sizes"]["MB3A"]
        self.assertEqual((mb3["art"], mb3["L"], mb3["H"], mb3["G"], mb3["F"], mb3["FH"]), ("151-28349", 19.0, 3.8, 4.1, 13.2, 3.1))
        t50 = its["ht-t-tie"]["sizes"]["T50R"]
        self.assertEqual((t50["art"], t50["L"], t50["W"], t50["T"], t50["dmax"]), ("111-00525", 202.0, 4.6, 1.2, 50.0))
        e215 = its["igus-e2-15"]
        self.assertEqual((e215["vars"]["p"], e215["vars"]["hi"], e215["vars"]["ha"]), (20.0, 14.4, 19.3))
        self.assertEqual(e215["sizes"]["Bi 10"]["Ba"], 17.8)  # (the published article E2.15.10.028.0)
        self.assertEqual(e215["lengths"]["values"], [28, 38, 48])
        self.assertEqual(its["igus-14"]["sizes"]["Bi 15"]["Ba"], 26.0)
        self.assertEqual(its["igus-10"]["sizes"]["Bi 80"]["Ba"], 94.0)
        self.assertEqual(its["igus-e2-10"]["sizes"]["Bi 10"]["Ba"], 17.4)
        for it in its.values():
            if it["kind"] == "chain":  # the side walls the same at every width
                self.assertEqual({round(s["Ba"] - s["Bi"], 6) for s in it["sizes"].values()}, {it["vars"]["side"]}, it["id"])

    def test_clips_for_a_bundle(self):
        its = items()
        got = C.clips_for(its, 6.0)
        self.assertEqual((got[0]["item"], got[0]["size"]), ("ht-hp-pclamp", "H3P"))  # (Ø6 in the 6.5 P-clamp: the snug one)
        self.assertEqual((got[1]["item"], got[1]["size"]), ("ht-mb-mount", "MB3A"))
        self.assertEqual([c["size"] for c in C.clips_for(its, 5.0) if c["item"] == "ht-hp-pclamp"], ["H2P"])  # (5.0 is H2P's own)
        self.assertEqual([c["item"] for c in C.clips_for(its, 20.0)], ["ht-mb-mount"])  # (larger than any P-clamp)
        self.assertEqual([c["size"] for c in C.clips_for(its, 40.0)], ["MB4A"])
        self.assertEqual(C.clips_for(its, 60.0), [])
        self.assertEqual(C.clips_for(its, 0), [])

    def test_pairs(self):
        its = {it["id"]: it for it in L.load(APP, Path("/nonexistent"))["items"]}
        screw = next(p for p in its["ht-hp-pclamp"]["pairs"] if p["role"] == "screw")
        self.assertEqual((screw["ref"], screw["size"]), ("iso7045", "M4"))  # (FH 4.2: an M4 pan head)
        self.assertTrue(any(q["ref"] == "ht-hp-pclamp" and q["from_size"] == "M4" for q in its["iso7045"]["pairs"]))
        tie = next(p for p in its["ht-mb-mount"]["pairs"] if p["role"] == "tie")
        self.assertEqual(tie["size"], "T18R")
        self.assertTrue(all(its["ht-t-tie"]["sizes"]["T18R"]["W"] <= s["G"] for s in its["ht-mb-mount"]["sizes"].values()))  # (the strap fits every mount)


class TestChainLayout(unittest.TestCase):
    def setUp(self):
        self.it = by_id()["igus-e2-15"]
        self.c = C.chain_of(self.it, "Bi 20", 38, links=30)

    def test_numbers(self):
        c = self.c
        self.assertEqual((c["pitch"], c["Bi"], c["Ba"], c["hi"], c["ha"], c["R"], c["dmax"], c["links"]), (20.0, 20.0, 27.8, 14.4, 19.3, 38.0, 12.5, 30))
        self.assertEqual(C.default_links({**c}), math.ceil((250 + math.pi * 38 + 40) / 20))
        lo, hi = C.travel_range(c)
        self.assertAlmostEqual(hi, 600 - math.pi * 38, places=9)
        self.assertAlmostEqual(lo, -hi, places=9)

    def test_u_layout_at_two_travels(self):
        c, R, L = self.c, 38.0, 600.0
        for travel in (0.0, 150.0):
            p = C.chain_path(c, travel)
            run = (L - math.pi * R) / 2
            self.assertTrue(p["ok"])
            self.assertAlmostEqual(p["lower"], run + travel / 2, places=9)
            self.assertAlmostEqual(p["upper"], run - travel / 2, places=9)
            self.assertAlmostEqual(p["length"], p["lower"] + p["upper"] + math.pi * R, places=9)
            self.assertAlmostEqual(p["length"], L, places=9)  # (always links × pitch)
            if travel == 0:
                self.assertAlmostEqual(p["length"], 2 * p["lower"] + math.pi * R, places=9)  # 2 × run + πR
            self.assertEqual(p["fixed"]["o"], [0.0, 0.0, 0.0])
            self.assertAlmostEqual(p["moving"]["o"][0], travel, places=9)
            self.assertAlmostEqual(p["moving"]["o"][2], 2 * R, places=9)  # (on the upper run, 2R up)
            self.assertEqual(p["moving"]["d"], [-1.0, 0.0, 0.0])
            # the polyline: its pieces add up to the length (the bend sampled: a hair shorter)
            pts = p["points"]
            poly = sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
            self.assertAlmostEqual(poly, L, delta=math.pi * R * (1 - math.sin(math.pi / 72) / (math.pi / 72)) + 1e-6)
            # the centre line s along: the moving end at its length, the bend's top at lower + πR/2
            self.assertTrue(all(abs(a - b) < 1e-9 for a, b in zip(C.point_at(c, travel, L)[0], p["moving"]["o"])))
            top, d = C.point_at(c, travel, p["lower"] + math.pi * R / 2)
            self.assertAlmostEqual(top[0], p["lower"] + R, places=9)
            self.assertAlmostEqual(top[2], R, places=9)
            self.assertAlmostEqual(d[2], 1, places=9)

    def test_out_of_reach(self):
        p = C.chain_path(self.c, 10_000)
        self.assertFalse(p["ok"])
        self.assertAlmostEqual(p["upper"], 0, places=9)  # (clamped: the upper run used up)
        self.assertAlmostEqual(p["length"], 600, places=9)


def _sketch(shapes, plane, offset):
    """Library shapes (rect / circle, as build.js shapesOf) -> a sketch feature's points and entities."""
    pts, ents = {}, []
    for s in shapes:
        if "circle" in s:
            c = s["circle"]
            k = f"p{len(pts) + 1}"
            pts[k] = [c.get("x", 0), c.get("y", 0)]
            ents.append({"id": f"c{len(ents) + 1}", "t": "circle", "c": k, "r": c["d"] / 2})
        else:
            r = s["rect"]
            x0, y0 = r.get("x", 0) - r["w"] / 2, r.get("y", 0) - r["h"] / 2
            ks = []
            for u, v in ((x0, y0), (x0 + r["w"], y0), (x0 + r["w"], y0 + r["h"]), (x0, y0 + r["h"])):
                ks.append(f"p{len(pts) + 1}")
                pts[ks[-1]] = [u, v]
            ents += [{"id": f"l{len(ents) + i + 1}", "t": "line", "a": ks[i], "b": ks[(i + 1) % 4]} for i in range(4)]
    return {"type": "sketch", "plane": {"datum": plane, **({"offset": offset} if offset else {})}, "points": pts, "entities": ents}


def steps(it, size, length=None):
    """The extrude steps of a cable part as build.js makes them (shapes with their numbers worked out)."""
    v, out = C.vars_of(it, size, length), []
    def ev(shape):
        k = "circle" if "circle" in shape else "rect"
        return {k: {a: C.num(b, v) for a, b in shape[k].items()}}
    for st in it["shape"]:
        if "when" in st and not C.num(st["when"], v) > 0:
            continue
        h, z = C.num(st["h"], v), C.num(st.get("z", 0), v)
        sk = _sketch([ev(st["extrude"])] + [ev(x) for x in st.get("holes", [])], st.get("plane", "XY"), z)
        n = len(out)
        sk["id"] = f"F{n + 1}"
        out += [sk, {"id": f"F{n + 2}", "type": "extrude", "sketch": sk["id"], "op": st.get("op", "add"), "d": abs(h), "through": False, "symmetric": False,
                     "flip": h > 0 if st.get("op") == "cut" else h < 0}]
    return out


@unittest.skipUnless(OCC, "OCP not installed")
class TestBuilds(unittest.TestCase):
    """Each part built by the kernel to its catalogue sizes (the same steps build.js makes)."""

    def build(self, it, k, length=None):
        from auto3d.modeler import doc
        r = doc.rebuild({"features": steps(it, k, length)})
        self.assertTrue(r["ok"] and r["body"], (it["id"], k, [f.get("issues") for f in r.get("features", [])]))
        warn = [w for f in r["features"] for w in f.get("warnings", [])]
        self.assertFalse([w for w in warn if "removes nothing" in w], (it["id"], k, warn))
        b = r["body"]["bbox"]
        return r["body"], [b[3] - b[0], b[4] - b[1], b[5] - b[2]]

    def test_clips_ties_and_links(self):
        its = by_id()
        for k in ("H1P", "H8P"):
            it = its["ht-hp-pclamp"]
            v = C.vars_of(it, k)
            body, size = self.build(it, k)
            self.assertAlmostEqual(size[1], v["W"], delta=0.01)  # the band's width
            self.assertAlmostEqual(size[2], v["D"] + 2 * v["WT"], delta=0.01)  # the loop's outside
            self.assertAlmostEqual(size[0], v["F"] + v["D"] / 2 + v["WT"] + v["W"] / 2, delta=0.01)
            dias = {round(2 * f["radius"], 3) for f in body["faces"] if f["type"] == "cylinder"}
            self.assertTrue({v["D"], v["FH"]} <= dias, (k, dias))  # the cable's bore, the screw hole
        for k in ("MB3A", "MB5A"):
            it = its["ht-mb-mount"]
            v = C.vars_of(it, k)
            body, size = self.build(it, k)
            self.assertAlmostEqual(body["volume"], v["L"] * v["W"] * v["H"] - 2 * math.pi * (v["FH"] / 2) ** 2 * v["H"], delta=0.05)
            self.assertEqual([round(x, 3) for x in size], [v["L"], v["W"], v["H"]])
        for k in ("T18R", "T30R", "T50R"):
            it = its["ht-t-tie"]
            v = C.vars_of(it, k)
            body, size = self.build(it, k)
            head = v["hl"] * v["hw"] * v["hh"]
            self.assertAlmostEqual(body["volume"], v["L"] * v["W"] * v["T"] + head, delta=0.05, msg=k)
        for cid in ("igus-e2-10", "igus-e2-15", "igus-14", "igus-10"):
            it = its[cid]
            for k in (list(it["sizes"])[0], list(it["sizes"])[-1]):
                v = C.vars_of(it, k)
                body, size = self.build(it, k)
                self.assertAlmostEqual(body["volume"], (v["Ba"] * v["ha"] - v["Bi"] * v["hi"]) * v["p"], delta=0.05, msg=(cid, k))
                self.assertEqual([round(x, 3) for x in size], [v["p"], v["Ba"], v["ha"]])


if __name__ == "__main__":
    unittest.main()
