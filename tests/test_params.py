"""𝑥 Project parameters (auto3d/modeler/params.py; web/js/params.js is the same in the browser): the parser —
precedence, references, units, errors —, every parameter worked out in order with circles found, a part's numbers
put in from its expressions (an extrude d = L / 2 and a sketch's locked size W follow L / W: the volumes follow),
the sketch solved again on the server with a size from a parameter, a project file's numbers made to agree with its
parameters on opening (project.migrate), STEP round trip. tests/param_cases.json: the cases the browser checks too
(tools/e2e_parameters.py).

Run:  py -m unittest tests.test_params -v
"""
import json
import unittest
from pathlib import Path

from auto3d import project
from auto3d.modeler import available
from auto3d.modeler import params as P
from test_modeler_kernel import watertight

OCC = available("occ")
if OCC:
    from auto3d.modeler import doc, kernel as K
    from test_modeler_features import box, vol

CASES = json.loads((Path(__file__).parent / "param_cases.json").read_text(encoding="utf-8"))


def plist(pairs):
    return [{"name": n, "expr": e} for n, e in pairs]


class TestParser(unittest.TestCase):
    def test_values(self):
        """Numbers, + - * / with the usual precedence (left to right), brackets, unary minus, references, units."""
        for text, values, want in CASES["values"]:
            with self.subTest(text=text):
                self.assertAlmostEqual(P.eval_text(text, values), want, places=9)

    def test_errors(self):
        """Each mistake its own code and a plain message; nothing raised but ParamError."""
        for text, values, code in CASES["errors"]:
            with self.subTest(text=text):
                with self.assertRaises(P.ParamError) as cm:
                    P.eval_text(text, values)
                self.assertEqual(cm.exception.code, code, str(cm.exception))
                self.assertTrue(str(cm.exception))

    def test_lists(self):
        """Parameters in any order (t = L / 20 before L), a circle a → b → a and one through a bad parameter: an error
        for each of them, the others worked out."""
        for pairs, want, bad in CASES["lists"]:
            with self.subTest(pairs=pairs):
                values, errors = P.evaluate_all(plist(pairs))
                self.assertEqual(sorted(errors), sorted(bad))
                for k, v in want.items():
                    self.assertAlmostEqual(values[k], v, places=9)

    def test_cycle_message(self):
        _, errors = P.evaluate_all(plist([["a", "b + 1"], ["b", "a + 1"]]))
        self.assertEqual(errors["a"].code, "cycle")
        self.assertIn("a → b → a", str(errors["a"]))

    def test_no_eval(self):
        """Not Python: attribute access, calls and the like are refused, not run."""
        for text in ("__import__('os')", "L.real", "abs(L)", "L ** 2", "[1]"):
            with self.subTest(text=text):
                with self.assertRaises(P.ParamError):
                    P.eval_text(text, {"L": 1})

    def test_resolve(self):
        """Numbers with an expression get its value (deep: a sketch's dims, an assembly's joints); a size shown as a
        radius ({x, k: 0.5}) the expression's / k; an expression that cannot be worked out keeps its number."""
        part = {"features": [{"id": "E1", "d": 1, "expr": {"d": "L / 2"}},
                             {"id": "S1", "dims": [{"id": "d1", "v": 3, "expr": {"v": {"x": "D", "k": 0.5}}},
                                                   {"id": "d2", "v": 7, "expr": {"v": "Q"}}]}]}
        n = P.resolve(part, {"L": 100, "D": 4})
        self.assertEqual(n, 2)
        self.assertEqual(part["features"][0]["d"], 50)
        self.assertEqual(part["features"][1]["dims"][0]["v"], 8)
        self.assertEqual(part["features"][1]["dims"][1]["v"], 7)
        self.assertEqual(P.resolve(part, {"L": 100, "D": 4}), 0)

    def test_migrate(self):
        """A project file whose numbers do not match its parameters (edited by hand): opened, they do; an older file
        gets an empty list."""
        proj = {"app": "Auto3DModeler", "version": 3, "parameters": plist([["L", "80"]]),
                "parts": [{"id": "P1", "kind": "model", "name": "A", "model": {"features": [{"id": "E1", "type": "extrude", "d": 10, "expr": {"d": "L / 4"}}]}},
                          {"id": "P2", "kind": "assembly", "name": "S", "assembly": {"instances": [], "mates": [{"id": "J1", "gap": 0, "expr": {"gap": "L / 40"}}]}}]}
        out = project.migrate(proj)
        self.assertEqual(out["parts"][0]["model"]["features"][0]["d"], 20)
        self.assertEqual(out["parts"][1]["assembly"]["mates"][0]["gap"], 2)
        self.assertEqual(project.migrate({"app": "Auto3DModeler", "version": 3, "parts": [{"id": "P1", "kind": "model", "model": {}}]})["parameters"], [])
        with self.assertRaises(project.ProjectError):
            project.migrate({**proj, "parameters": {"L": 1}})


class TestTools(unittest.TestCase):
    def test_ai_tools(self):
        """get_parameters / set_parameter go to the page; a step's numbers and a sketch size take an expression."""
        from auto3d.agent_tools import BROWSER_TOOLS, SYSTEM_PROMPT, TOOLS
        self.assertTrue({"get_parameters", "set_parameter"} <= BROWSER_TOOLS)
        tool = {t["name"]: t for t in TOOLS}
        self.assertIn("string", tool["add_feature"]["inputSchema"]["properties"]["d"]["type"])
        self.assertIn("string", tool["sketch_dim"]["inputSchema"]["properties"]["value"]["type"])
        self.assertIn("set_parameter", SYSTEM_PROMPT)
        skill = (Path(__file__).parent.parent / "agent_plugin" / "skills" / "model-a-part" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("set_parameter", skill)


def rect(w, h, dims=True, expr=None):
    """A w × h rectangle from the origin, its sides locked (W / H: expressions of its lengths), extruded."""
    pts = {"p1": [0, 0], "p2": [w, 0], "p3": [w, h], "p4": [0, h]}
    lines = [{"id": f"l{i + 1}", "t": "line", "a": f"p{i + 1}", "b": f"p{(i + 1) % 4 + 1}", "g": "r1"} for i in range(4)]
    cons = [{"id": "k1", "t": "h", "e": "l1"}, {"id": "k2", "t": "v", "e": "l2"}, {"id": "k3", "t": "h", "e": "l3"}, {"id": "k4", "t": "v", "e": "l4"},
            {"id": "k5", "t": "fix", "p": "p1"}]
    ds = [{"id": "d1", "t": "len", "e": "l1", "v": w, **({"expr": {"v": expr}} if expr else {})}, {"id": "d2", "t": "len", "e": "l2", "v": h}] if dims else []
    return {"id": "S1", "type": "sketch", "plane": {"datum": "XY"}, "points": pts, "entities": lines, "constraints": cons, "dims": ds}


@unittest.skipUnless(OCC, "OCP not installed")
class TestPartFollows(unittest.TestCase):
    def test_extrude_follows(self):
        """d = L / 2 on a 40 × 20 box: L = 100 -> 40 × 20 × 50; L = 60 -> × 30; watertight; STEP round trip."""
        part = {"features": [box()[0], {**box()[1], "d": 10, "expr": {"d": "L / 2"}}]}
        for L, h in ((100, 50), (60, 30)):
            P.resolve(part, {"L": L})
            r, v = vol(*part["features"])
            self.assertTrue(r["ok"], r["features"])
            self.assertAlmostEqual(v, 40 * 20 * h, delta=1e-6)
            self.assertTrue(watertight(r["body"]))
        self.assertAlmostEqual(K.volume(K.from_step(doc.export(part, "step"))), 40 * 20 * 30, delta=0.05)

    @unittest.skipUnless(available("planegcs"), "planegcs not installed")
    def test_sketch_size_follows(self):
        """A locked width W of a 40 × 20 rectangle: W = 70 puts 70 in the size; the server solves the sketch again
        (its points follow — handed back as the step's update) and the extrude is 70 × 20 × 10."""
        part = {"features": [rect(40, 20, expr="W"), {"id": "E1", "type": "extrude", "sketch": "S1", "op": "add", "d": 10}]}
        self.assertEqual(P.resolve(part, {"W": 70}), 1)
        r, v = vol(*part["features"])
        self.assertTrue(r["ok"], r["features"])
        self.assertAlmostEqual(v, 70 * 20 * 10, delta=1e-4)
        self.assertTrue(watertight(r["body"]))
        up = next(s for s in r["features"] if s["id"] == "S1")["update"]
        self.assertAlmostEqual(up["points"]["p2"][0], 70, places=5)
        self.assertAlmostEqual(up["points"]["p3"][1], 20, places=5)

    @unittest.skipUnless(available("planegcs"), "planegcs not installed")
    def test_sketch_without_change(self):
        """The sketch as its sizes say already: no update (nothing to hand back)."""
        r, v = vol(rect(40, 20, expr="W"), {"id": "E1", "type": "extrude", "sketch": "S1", "op": "add", "d": 10})
        self.assertAlmostEqual(v, 8000, delta=1e-6)
        self.assertNotIn("update", next(s for s in r["features"] if s["id"] == "S1"))


if __name__ == "__main__":
    unittest.main()
