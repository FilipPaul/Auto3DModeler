// Faces painted on their own: a part's `paint` is [{name, fp: [x, y, z], color}] — the face's name and where it was.
// Several faces can share a name (two blocks from one extrude): the one of that name nearest fp is painted, so the
// colour stays on its face when the part changes.

/** faces of a body (tessellate output) -> Map(face id -> {color, i}) (i: the paint entry). */
export function paintedFaces(faces, paint = []) {
  const out = new Map();
  (paint || []).forEach((e, i) => {
    const c = faces.filter((f) => f.name === e.name || (f.names || []).includes(e.name));
    if (!c.length) return;
    const dist = (f) => Math.hypot(...f.centroid.map((v, k) => v - (e.fp?.[k] ?? 0)));
    const f = c.length === 1 ? c[0] : c.reduce((b, x) => (dist(x) < dist(b) ? x : b));
    out.set(f.id, { color: e.color, i });
  });
  return out;
}

/** The paint with these faces (ids) given `color` (null: their own colour taken off). */
export function repaint(faces, paint = [], ids, color) {
  const now = paintedFaces(faces, paint), drop = new Set([...ids].map((id) => now.get(id)?.i).filter((i) => i !== undefined));
  const out = (paint || []).filter((_, i) => !drop.has(i));
  if (color) for (const id of ids) { const f = faces.find((x) => x.id === id); if (f) out.push({ name: f.name, fp: f.centroid.map((v) => +(+v).toFixed(4)), color }); }
  return out;
}
