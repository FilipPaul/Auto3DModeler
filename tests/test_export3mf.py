"""Exports the server writes from the page's data: a 3MF in colours (an object per colour, each with its colour as a base
material; shared vertices), and an assembly's BOM as CSV for Excel; the server's own tool is not offered to the AI."""
import io
import unittest
import zipfile
import xml.etree.ElementTree as ET

from auto3d.export3mf import to_3mf

NS = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
CUBE_TOP = [0, 0, 1, 1, 0, 1, 1, 1, 1, 0, 0, 1, 1, 1, 1, 0, 1, 1]  # two triangles sharing an edge


class Test3MF(unittest.TestCase):
    def test_objects_per_colour(self):
        data = to_3mf([{"name": "body", "color": "#ffd400", "positions": CUBE_TOP}, {"name": "beak", "color": "#FF8800", "positions": CUBE_TOP},
                       {"name": "eye", "color": "#ffd400", "positions": CUBE_TOP[:9]}], "Duck")
        z = zipfile.ZipFile(io.BytesIO(data))
        self.assertEqual(sorted(z.namelist()), ["3D/3dmodel.model", "[Content_Types].xml", "_rels/.rels"])
        root = ET.fromstring(z.read("3D/3dmodel.model"))
        self.assertEqual(root.get("unit"), "millimeter")
        bases = [b.get("displaycolor") for b in root.findall(".//m:basematerials/m:base", NS)]
        self.assertEqual(bases, ["#FFD400FF", "#FF8800FF"])  # each colour once
        objs = root.findall(".//m:object", NS)
        self.assertEqual([(o.get("name"), o.get("pindex")) for o in objs], [("body", "0"), ("beak", "1"), ("eye", "0")])
        self.assertEqual(len(objs[0].findall(".//m:vertex", NS)), 4)  # the shared edge's vertices once
        self.assertEqual(len(objs[0].findall(".//m:triangle", NS)), 2)
        self.assertEqual(len(root.findall(".//m:build/m:item", NS)), 3)

    def test_nothing(self):
        with self.assertRaises(ValueError):
            to_3mf([{"color": "#fff000", "positions": []}])


class TestDownloadName(unittest.TestCase):
    """A download's name may hold Czech letters or a dash: the header stays Latin-1 (it failed with —)."""

    def test_header(self):
        import server
        from urllib.parse import unquote
        h = server.attachment("Kačenka — 3D model.stl")
        h.encode("latin-1")  # (raised before)
        self.assertIn('filename="Kacenka - 3D model.stl"', h)
        self.assertEqual(unquote(h.split("filename*=UTF-8''")[1]), "Kačenka — 3D model.stl")
        self.assertNotIn('"', h.split("filename=")[1].split(";")[0].strip('"'))


class TestBomCsv(unittest.TestCase):
    def test_rows(self):
        import server
        csv = server.bom_csv([{"qty": 2, "name": "ISO 4762 M3×10", "maker": "", "pn": "ISO 4762 M3x10", "description": "Socket; head", "material": "steel",
                               "mass_g": 1.11, "library": True, "order": {}},
                              {"qty": 1, "name": "SICK IME12", "maker": "SICK", "pn": "IME12-04BPSZC0K", "order": {"sick": "1040763"}, "material": "brass", "mass_g": None, "library": True},
                              {"qty": 1, "name": "Bracket", "material": "PLA", "mass_g": 12.5}], ["sick"])
        self.assertTrue(csv.startswith("﻿".encode("utf-8")))
        lines = csv.decode("utf-8-sig").split("\r\n")
        self.assertEqual(lines[0], "Pos;Qty;Name;Maker;Part number;Order (sick);Description;Material;Mass each (g);Bought / made")
        self.assertEqual(lines[1], '1;2;ISO 4762 M3×10;;ISO 4762 M3x10;;"Socket; head";steel;1,11;bought')
        self.assertIn(";1040763;", lines[2])
        self.assertTrue(lines[3].endswith(";PLA;12,5;made (3D print)"))

    def test_hidden_tool(self):
        from auto3d.agent_tools import TOOL_NAMES, mcp_tool_list
        names = {t["name"] for t in mcp_tool_list()}
        self.assertIn("export_data", TOOL_NAMES)
        self.assertNotIn("export_data", names)
        for want in ("get_drawing", "drawing_find", "drawing_layers", "drawing_set_size", "drawing_use", "edit_joint", "remove_joint", "measure",
                     "set_view", "rename_part", "delete_part"):
            self.assertIn(want, names)
        self.assertTrue(all("hidden" not in t and "where" not in t for t in mcp_tool_list()))


if __name__ == "__main__":
    unittest.main()
