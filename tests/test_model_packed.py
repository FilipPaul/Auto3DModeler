"""The binary rebuild answer (auto3d/modeler/packed.py): the same result as the JSON one, its arrays byte for byte, a
body encoded once; the faster tessellation gives every triangle to its own face."""
import base64
import json
import struct
import unittest
from unittest import mock

import numpy as np

from auto3d.modeler import available, packed

OCC = available("occ")
if OCC:
    from auto3d.modeler import doc, kernel as K

from test_modeler_kernel import RECT, extrude, sketch, watertight


def plain(x):
    """As JSON would give it back (tuples as lists …), bytes kept."""
    if isinstance(x, dict):
        return {k: plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [plain(v) for v in x]
    return x if isinstance(x, bytes) else json.loads(json.dumps(x))


class TestPacked(unittest.TestCase):
    RES = {"ok": True, "features": [{"id": "E1", "ok": True, "issues": [], "bbox": (0, 0, 0, 1.5, 2, 3)}],
           "frames": {"S1": {"o": [0, 0, 0]}}, "points": {},
           "body": {"positions": np.arange(18, dtype=np.float32).tobytes() + np.float32([1e-7, -3.25, 1e30]).tobytes() * 3,
                    "face_ids": np.uint32([0, 7, 2**32 - 1]).tobytes(), "faces": [{"id": 0, "name": "E1:end", "area": 0.1 + 0.2}],
                    "edges": [{"pts": [0, 1.000001, 2], "faces": [0, 7]}], "bbox": [0, 0, 0, 1, 1, 1], "volume": 1 / 3},
           "refs": [{"id": "R1", "positions": b"", "face_ids": b"", "faces": [], "edges": []}],
           "odd": b"\x01\x02\x03"}

    def test_round_trip(self):
        """The arrays exactly as they were (also an empty one, odd bytes), the rest as JSON gives it."""
        data = packed.pack(self.RES)
        self.assertEqual(data[:4], b"A3DM")
        self.assertEqual(packed.unpack(data), plain(self.RES))

    def test_meshes_encoded_once(self):
        """A packed.Mesh gives the same message as its dict; each array where a Float32Array / Uint32Array view
        can start (a multiple of 4 from the message's start), with its type."""
        res = {**self.RES, "body": packed.Mesh(self.RES["body"]), "refs": [packed.Mesh(self.RES["refs"][0])]}
        data = packed.pack(res)
        self.assertEqual(packed.unpack(data), plain(self.RES))
        (n,) = struct.unpack_from("<I", data, 4)
        head = json.loads(data[8:8 + n])
        self.assertEqual({tuple(a["at"]): a["type"] for a in head["arrays"]},
                         {("body", "positions"): "f32", ("body", "face_ids"): "u32", ("refs", 0, "positions"): "f32",
                          ("refs", 0, "face_ids"): "u32", ("odd",): "u8"})
        self.assertTrue(all((8 + n + a["off"]) % 4 == 0 for a in head["arrays"]))
        self.assertIsNone(head["result"]["body"].get("positions"))  # (not in the JSON: only after it)

    def test_not_json(self):
        with self.assertRaises(TypeError):
            packed.pack({"x": object()})
        with self.assertRaises(ValueError):
            packed.unpack(b"{}")


@unittest.skipUnless(OCC, "OCP not installed")
class TestPackedRebuild(unittest.TestCase):
    def part(self, d=10):
        box = K.to_step(doc.body_of({"features": [sketch("S9", [RECT]), extrude("E9", "S9", 4)]}).body.shape)
        ref = {"id": "R1", "type": "solid", "step": base64.b64encode(box).decode(), "op": "ref"}
        return {"features": [sketch("S1", [RECT]), extrude("E1", "S1", d), ref]}

    def test_same_as_json(self):
        """rebuild(part, binary) packed -> unpacked: what rebuild(part) gives, the body and the reference solid."""
        part = self.part()
        got = packed.unpack(packed.pack(doc.rebuild(part, True)))
        self.assertEqual(got, plain(doc.rebuild(part)))
        self.assertAlmostEqual(got["body"]["volume"], 8000, delta=1e-3)
        self.assertEqual(got["refs"][0]["id"], "R1")
        self.assertTrue(watertight(got["body"]))

    def test_body_encoded_once(self):
        """An unchanged body (another sketch added) keeps its encoded mesh; a changed one is encoded anew."""
        part = self.part()
        a = doc.rebuild(part, True)
        b = doc.rebuild({"features": [*part["features"], sketch("S2", [RECT])]}, True)
        self.assertIs(a["body"], b["body"])
        self.assertIs(a["refs"][0], b["refs"][0])
        c = doc.rebuild(self.part(12), True)
        self.assertIsNot(c["body"], a["body"])
        self.assertAlmostEqual(packed.unpack(packed.pack(c))["body"]["volume"], 9600, delta=1e-3)

    def test_triangles_on_their_faces(self):
        """Each triangle lies in its flat face's plane (the face ids follow the triangles); a big part's face areas
        and middles from its triangles: the box's 2800 mm², its top's middle."""
        body = doc.body_of({"features": [sketch("S1", [RECT]), extrude("E1", "S1", 10)]}).body
        m = K.tessellate(body)
        tri = np.frombuffer(m["positions"], np.float32).reshape(-1, 3, 3).astype(float)
        ids = np.frombuffer(m["face_ids"], np.uint32)
        for f in m["faces"]:
            n, o = np.asarray(f["normal"]), np.asarray(f["frame"]["o"])
            t = tri[ids == f["id"]]
            self.assertGreater(len(t), 0)
            self.assertLess(np.abs((t - o) @ n).max(), 1e-4)
            # (each triangle wound outwards)
            self.assertTrue((np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]) @ n > 0).all())
        with mock.patch.object(K, "HEAVY_FACES", 0):
            heavy = K.tessellate(body)
        self.assertEqual(heavy["positions"], m["positions"])
        self.assertAlmostEqual(sum(f["area"] for f in heavy["faces"]), 2800, delta=1e-6)
        top = next(f for f in heavy["faces"] if f.get("name") == "E1:end")
        self.assertEqual(top["centroid"], [20, 10, 10])

    def test_server_binary_answer(self):
        """/api/model/rebuild {bin: true}: application/octet-stream, the JSON answer's data (its base64 arrays
        decoded); a part without a solid packed too (body null)."""
        import server
        c = server.app.test_client()
        part = self.part()
        j = c.post("/api/model/rebuild", json={"part": part}).get_json()
        r = c.post("/api/model/rebuild", json={"part": part, "bin": True})
        self.assertEqual(r.mimetype, "application/octet-stream")
        for m in [j["body"], *j["refs"]]:
            m["positions"], m["face_ids"] = base64.b64decode(m["positions"]), base64.b64decode(m["face_ids"])
        self.assertEqual(packed.unpack(r.data), j)
        empty = packed.unpack(c.post("/api/model/rebuild", json={"part": {"features": []}, "bin": True}).data)
        self.assertIsNone(empty["body"])
