"""A rebuilt part for the browser as one binary message: a JSON header and the meshes' arrays as they are — no base64
(a quarter smaller, nothing to decode: the browser views the bytes as Float32Array / Uint32Array), and a big body
encoded once (`Mesh`, kept by doc while the body does not change).

  b"A3DM" | the header's length (uint32, little-endian) | the header (JSON, UTF-8, padded with spaces to 4 bytes) | arrays

header: {"arrays": [{"at": [path], "off": bytes after the header, "n": bytes, "type": "f32" | "u32" | "u8"}],
"result": the result without its arrays}. Each array starts at a multiple of 4 (a Float32Array view needs it).
web/js/modeler/packed.js reads it; unpack() here is the same in Python (tests).
"""
from __future__ import annotations

import json
import re
import struct

MAGIC = b"A3DM"
TYPES = {"positions": "f32", "face_ids": "u32"}  # (any other bytes: u8)
_MARK = re.compile(rb'"\\u0000a3dm(\d+)\\u0000"')


class Mesh:
    """A mesh (kernel.tessellate's dict) encoded once: its JSON without the arrays, and the arrays."""
    __slots__ = ("json", "arrays")

    def __init__(self, mesh):
        self.arrays = [(k, bytes(v)) for k, v in mesh.items() if isinstance(v, (bytes, bytearray))]
        self.json = json.dumps({k: v for k, v in mesh.items() if not isinstance(v, (bytes, bytearray))}, sort_keys=True).encode()


def _strip(v, path, found):
    """v with its meshes marked and its arrays left out (null); found gets (path, Mesh | bytes)."""
    if isinstance(v, Mesh):
        found.append((path, v))
        return _Mark(len(found) - 1)
    if isinstance(v, (bytes, bytearray)):
        found.append((path, bytes(v)))
        return None
    if isinstance(v, dict):
        return {k: _strip(x, path + [k], found) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_strip(x, path + [i], found) for i, x in enumerate(v)]
    return v


class _Mark:
    __slots__ = ("i",)

    def __init__(self, i):
        self.i = i


def pack(res) -> bytes:
    """A result (dicts, lists, numbers, strings; meshes as Mesh or with bytes arrays) -> the message."""
    found = []
    result = _strip(res, [], found)
    arrays, data, off = [], [], 0
    for path, v in found:
        for k, b in (v.arrays if isinstance(v, Mesh) else [(None, v)]):
            at = path + [k] if k is not None else path
            arrays.append({"at": at, "off": off, "n": len(b), "type": TYPES.get(at[-1] if at else None, "u8")})
            data.append(b + b"\0" * (-len(b) % 4))
            off += len(b) + (-len(b) % 4)
    head = json.dumps({"arrays": arrays, "result": result}, sort_keys=True,
                      default=lambda m: f"\0a3dm{m.i}\0" if isinstance(m, _Mark) else _no(m)).encode()
    if found:  # each mesh's JSON, made once, put in its place
        head = _MARK.sub(lambda m: found[int(m.group(1))][1].json, head)
    head += b" " * (-len(head) % 4)
    return b"".join([MAGIC, struct.pack("<I", len(head)), head, *data])


def _no(o):
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


def unpack(data: bytes):
    """The message -> the result, its arrays as bytes again (as pack got them; meshes as dicts)."""
    if data[:4] != MAGIC:
        raise ValueError("Not a packed model.")
    (n,) = struct.unpack_from("<I", data, 4)
    head = json.loads(data[8:8 + n])
    res, base = head["result"], 8 + n
    for a in head["arrays"]:
        o = res
        for k in a["at"][:-1]:
            o = o[k]
        o[a["at"][-1]] = bytes(data[base + a["off"]: base + a["off"] + a["n"]])
    return res
