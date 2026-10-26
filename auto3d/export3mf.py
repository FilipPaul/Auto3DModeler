"""3MF with colours, for multi-material printing (Bambu AMS, Prusa MMU, …): one object per colour of the part (or of
each placed part of an assembly), each with its colour as a base material — the slicer shows them coloured and each
can get its filament. Standard library only.

groups: [{name, color: "#rrggbb", positions: [x, y, z, …] (triangles, mm)}]
"""
from __future__ import annotations

import io
import re
import zipfile
from xml.sax.saxutils import escape

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
</Types>"""
RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>"""


def _mesh(positions):
    """Triangles (flat list of coordinates) -> (vertices, triangles as index triples), equal vertices shared."""
    index, verts, tris = {}, [], []
    for t in range(0, len(positions) - 8, 9):
        ids = []
        for k in range(3):
            p = tuple(round(float(positions[t + 3 * k + i]), 5) for i in range(3))
            if p not in index:
                index[p] = len(verts)
                verts.append(p)
            ids.append(index[p])
        if len(set(ids)) == 3:  # (no degenerate triangles)
            tris.append(ids)
    return verts, tris


def to_3mf(groups, title="Auto3DModeler") -> bytes:
    """Coloured groups of triangles -> a 3MF file (bytes)."""
    groups = [g for g in groups or [] if len(g.get("positions") or []) >= 9]
    if not groups:
        raise ValueError("Nothing to export — the part has no solid.")
    colours = []
    for g in groups:
        c = str(g.get("color") or "#d9dee6")
        if not re.match(r"^#[0-9a-fA-F]{6}$", c):
            c = "#d9dee6"
        g["_c"] = c.upper()
        if g["_c"] not in colours:
            colours.append(g["_c"])
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">',
           f' <metadata name="Title">{escape(title)}</metadata>', ' <metadata name="Application">Auto3DModeler</metadata>',
           ' <resources>', '  <basematerials id="1">']
    out += [f'   <base name="{c}" displaycolor="{c}FF"/>' for c in colours]
    out.append('  </basematerials>')
    for k, g in enumerate(groups, start=2):
        verts, tris = _mesh(g["positions"])
        out.append(f'  <object id="{k}" type="model" name="{escape(str(g.get("name") or f"part {k - 1}"))}" pid="1" pindex="{colours.index(g["_c"])}">')
        out.append('   <mesh><vertices>')
        out += [f'    <vertex x="{x:g}" y="{y:g}" z="{z:g}"/>' for x, y, z in verts]
        out.append('   </vertices><triangles>')
        out += [f'    <triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in tris]
        out.append('   </triangles></mesh>')
        out.append('  </object>')
    out.append(' </resources>')
    out.append(' <build>')
    out += [f'  <item objectid="{k}"/>' for k in range(2, len(groups) + 2)]
    out.append(' </build>')
    out.append('</model>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("3D/3dmodel.model", "\n".join(out))
    return buf.getvalue()
