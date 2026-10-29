"""📚 Test probes (pogo pins) and their receptacles in the parts library (library/probes.json): every probe and
receptacle builds (the same steps web/js/library/build.js makes: its half-section revolved, cuts), and its built
sizes are its catalogue sizes within 0.01 mm — total length, barrel Ø, plunger Ø; a receptacle's length, outer Ø and
collar; the categories (Test probes / maker / series, Receptacles / maker), the search fields and the links between a
probe and its receptacle; a few catalogue numbers checked as the datasheets give them."""
import math
import re
import unittest
from pathlib import Path

from auto3d import library as L
from auto3d.modeler import available

APP = Path(__file__).resolve().parent.parent / "library"
OCC = available("occ")
FN = {"pi": math.pi, "tan": math.tan, "sin": math.sin, "cos": math.cos, "sqrt": math.sqrt, "min": min, "max": max, "abs": abs}


def items():
    return [it for it in L.load(APP, Path("/nonexistent"))["items"] if it["file"] == "probes.json"]


def value(expr, vars_):
    """A number or a formula of the values (as build.js evaluate)."""
    if isinstance(expr, (int, float)):
        return float(expr)
    names = {k: value(v, vars_) for k, v in vars_.items() if re.match(r"^\w+$", k) and re.search(rf"\b{k}\b", expr)}
    return float(eval(expr.replace("^", "**"), {"__builtins__": {}}, {**FN, **names}))  # noqa: S307 (the app's own data)


def vars_of(it, size):
    return {**(it.get("vars") or {}), **it["sizes"][size]}


def steps(it, size):
    """The 3D model steps for a choice, as build.js makes them (revolve: a sketch on XZ turned about its y axis = Z;
    extrude: a sketch on its plane, pushed h along the normal)."""
    v, out, n = vars_of(it, size), [], 0
    for st in it["shape"]:
        if "when" in st and not value(st["when"], v) > 0:
            continue
        pts = [[value(r, v), value(z, v)] for r, z in (st.get("revolve") or st["extrude"]["polyline"])]
        keys = [f"p{i + 1}" for i in range(len(pts))]
        ents = [{"id": f"l{i + 1}", "t": "line", "a": keys[i], "b": keys[(i + 1) % len(pts)]} for i in range(len(pts))]
        sk, n = f"F{n + 1}", n + 2
        if "revolve" in st:
            out += [{"id": sk, "type": "sketch", "plane": {"datum": "XZ"}, "points": dict(zip(keys, pts)), "entities": ents},
                    {"id": f"F{n}", "type": "revolve", "sketch": sk, "axis": "y", "angle": 360, "op": st.get("op", "add")}]
        else:
            h, z = value(st["h"], v), value(st.get("z", 0), v)
            out += [{"id": sk, "type": "sketch", "plane": {"datum": st.get("plane", "XY"), **({"offset": z} if z else {})}, "points": dict(zip(keys, pts)), "entities": ents},
                    {"id": f"F{n}", "type": "extrude", "sketch": sk, "op": st.get("op", "add"), "d": abs(h), "through": False, "symmetric": False,
                     "flip": h > 0 if st.get("op") == "cut" else h < 0}]
    return out


class TestProbeData(unittest.TestCase):
    def test_categories_and_fields(self):
        its = items()
        probes = [it for it in its if it["kind"] == "probe"]
        recs = [it for it in its if it["kind"] == "receptacle"]
        self.assertGreaterEqual(len(probes), 15)
        self.assertGreaterEqual(len(recs), 2)
        for it in its:
            self.assertNotIn("problems", it, it["id"])
            top, maker, series = it["category"].split(" / ")
            self.assertEqual(top, "Test probes" if it["kind"] == "probe" else "Receptacles")
            self.assertEqual(maker, it["maker"])
            self.assertTrue(series.startswith(it["series"]), (series, it["series"]))
            self.assertEqual(it["accuracy"], "catalogue")
            self.assertTrue(it["datasheet"] and it["description"] and it["description_cs"] and it["name_cs"], it["id"])
            self.assertIn("ozměry podle katalogu", it["description_cs"])
            for k, s in it["sizes"].items():
                v = vars_of(it, k)
                self.assertTrue(re.match(r"^https://", (s.get("ds") or it["datasheet"])), (it["id"], k))
                if it["kind"] == "probe":
                    self.assertTrue(v["ws"] < v["ms"] and v["F"] > 0, (it["id"], k))
                    self.assertAlmostEqual(v.get("k", v["F"] / v["ws"]), v["F"] / v["ws"], places=3)
        makers = {it["maker"] for it in probes}
        self.assertEqual(makers, {"INGUN", "KESACON"})
        grids = {it["vars"]["grid"] for it in probes}
        self.assertEqual(grids, {2.54, 1.91, 1.27})

    def test_catalogue_numbers(self):
        """As the datasheets say them (INGUN GKS-100 214 130 A 2000 = GKS-100-0008; KS-100 30; KESACON MPI100)."""
        its = {it["id"]: it for it in items()}
        s = its["ingun-gks100-214"]["sizes"]["Ø1.3 · 2 N"]
        self.assertEqual((s["pn"], s["art"], s["F"], s["F0"], s["a"]), ("GKS-100 214 130 A 2000", "GKS-100-0008", 2, 0.66, 87))
        v = its["ingun-gks100-214"]["vars"]
        self.assertEqual((v["L"], v["D"], v["d"], v["Lb"], v["ws"], v["ms"], v["grid"]), (33.4, 1.37, 0.9, 25.0, 4.3, 6.35, 2.54))
        self.assertTrue(s["cad"].endswith("INGUN_GKS-100_214_130_A_xx00.STEP"))
        k = its["ingun-ks100"]["sizes"]["KS-100 30"]
        self.assertEqual((k["art"], k["L"], k["Do"], k["Dc"], k["hc"], k["H"]), ("KS-10030", 32, 1.67, 1.8, 5.5, 16.0))
        self.assertEqual(its["ingun-gks050-201"]["vars"]["L"], 43.2)
        self.assertEqual(its["ingun-gks075-201"]["vars"]["D"], 1.02)
        m = its["kesacon-mpi100-f"]
        self.assertEqual((m["vars"]["L"], m["vars"]["Lb"], m["vars"]["D"], m["vars"]["d"]), (33.3, 25.0, 1.37, 0.9))
        self.assertEqual(m["pn"].replace("{Fc}", "200"), "MPI100-F-090-200-BG")

    def test_probe_knows_its_receptacle(self):
        its = {it["id"]: it for it in items()}
        for it in its.values():
            if it["kind"] != "probe" or it["maker"] != "INGUN" or it["series"] == "GKS-075":
                continue
            rec = [p["ref"] for p in it.get("pairs", []) if p["role"] == "receptacle"]
            self.assertEqual(len(rec), 1, it["id"])
            r = its[rec[0]]
            self.assertEqual(r["kind"], "receptacle")
            self.assertAlmostEqual(r["vars"]["rb"] * 2, it["vars"]["D"], places=3)  # (the bore is the probe's barrel)
            self.assertAlmostEqual(r["vars"]["Lp"], it["vars"]["L"], places=3)
            for k in r["sizes"]:
                zp = value(r["vars"]["zp"], vars_of(r, k))
                v = vars_of(r, k)
                self.assertAlmostEqual(zp + it["vars"]["L"], v["L"] - v["hc"] + v["H"], places=6)  # its tip H above the plate
                self.assertGreater(zp, v["lcup"])

    def test_search(self):
        """The words a user types find them: the grid, the maker, the head style, an order code (as matchScore)."""
        def find(q):
            words = q.lower().split()
            out = []
            for it in items():
                hay = " ".join(str(x) for x in [it["name"], it["name_cs"], it["category"], it["maker"], it["series"], it["pn"], it["description"],
                                                  it["description_cs"], it["id"], *[f"{k} {s.get('pn', '')} {s.get('art', '')}" for k, s in it["sizes"].items()]]).lower()
                if all(w in hay for w in words):
                    out.append(it["id"])
            return out
        fifty = find("1.27")
        self.assertTrue(fifty and all(i.startswith(("ingun-gks050", "ingun-ks050", "kesacon-mpi050")) for i in fifty), fifty)
        self.assertIn("ingun-gks100-214", find("GKS-100-0008"))
        self.assertIn("ingun-gks100-214", find("crown 2.54"))
        self.assertIn("ingun-gks100-214", find("korunka"))
        self.assertEqual(set(find("kesacon")), {"kesacon-mpi100-f", "kesacon-mpi075-f", "kesacon-mpi050-f"})
        self.assertIn("ingun-ks100", find("KS-100 30 05"))


@unittest.skipUnless(OCC, "OCP not installed")
class TestProbeBuilds(unittest.TestCase):
    def test_every_entry_builds_to_its_sizes(self):
        from auto3d.modeler import doc
        for it in items():
            keys = list(it["sizes"])
            for k in {keys[0], keys[-1]}:
                v = vars_of(it, k)
                r = doc.rebuild({"features": steps(it, k)})
                self.assertTrue(r["ok"] and r["body"], (it["id"], k, r.get("features")))
                warn = [w for f in r["features"] for w in f.get("warnings", [])]
                self.assertFalse([w for w in warn if "removes nothing" in w], (it["id"], k, warn))
                b = r["body"]["bbox"]
                radii = sorted({round(f["radius"] * 2, 4) for f in r["body"]["faces"] if f["type"] == "cylinder"})
                if it["kind"] == "probe":
                    self.assertAlmostEqual(b[5] - b[2], v["L"], delta=0.01, msg=(it["id"], k))
                    self.assertAlmostEqual(b[3] - b[0], max(v["D"], v.get("t", 0)), delta=0.01, msg=(it["id"], k))
                    for want in (v["D"], v["d"]):  # the barrel, the plunger
                        self.assertTrue(any(abs(x - want) <= 0.01 for x in radii), (it["id"], k, want, radii))
                else:
                    self.assertAlmostEqual(b[5] - b[2], v["L"], delta=0.01, msg=(it["id"], k))
                    self.assertAlmostEqual(b[3] - b[0], v["Dc"], delta=0.01, msg=(it["id"], k))
                    for want in (v["Do"], v["rb"] * 2):  # its outside, the bore the probe sits in
                        self.assertTrue(any(abs(x - want) <= 0.01 for x in radii), (it["id"], k, want, radii))


if __name__ == "__main__":
    unittest.main()
