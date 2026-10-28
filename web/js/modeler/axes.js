// The axes of the part's round faces (a shaft, a cross hole, a boss) seen square onto a sketch's or a hole step's
// plane: references to measure from. Square to the plane an axis is a point there, else a line. A distance stores
// it as {axis: {face, fp}} (the round face's name and its middle); the kernel finds the face again on each rebuild
// (doc._axis_of), so the distance follows the part.

const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const yOf = (fr) => { const { x, n } = fr; return [n[1] * x[2] - n[2] * x[1], n[2] * x[0] - n[0] * x[2], n[0] * x[1] - n[1] * x[0]]; };

/** The round faces' axes on frame fr's plane: [{ref: {face, fp}, face: its index, r, c: [u, v] (a point of it), dir:
 *  [du, dv] (null: square to the plane, a point), a, b: the ends of the line, as far as the face reaches along it}].
 *  Roundings and bevels are left out (each corner would bring one); skip(name) leaves out more (a step's own). */
export function roundAxes(body, fr, skip = null) {
  if (!body || !fr) return [];
  const x = fr.x, y = yOf(fr), uv = (p) => { const d = p.map((v, i) => v - fr.o[i]); return [+dot(d, x).toFixed(5), +dot(d, y).toFixed(5)]; };
  const reach = new Map(); // a face -> its edges' points (how far along its axis it reaches)
  for (const e of body.edges || []) for (const fi of e.faces) (reach.get(fi) || reach.set(fi, []).get(fi)).push(e.pts);
  const byName = new Map();
  body.faces.forEach((f, fi) => {
    if (!f.axis || !f.name || /:(round|bevel):/.test(f.name) || skip?.(f.name)) return;
    const o = f.axis.o, d = f.axis.d, L = Math.hypot(dot(d, x), dot(d, y));
    const ref = { face: f.name, fp: f.centroid };
    if (L < 1e-6) {
      if (!byName.has(f.name)) byName.set(f.name, { ref, face: fi, r: f.radius, c: uv(o), dir: null });
      return;
    }
    let t0 = Infinity, t1 = -Infinity;
    for (const pl of reach.get(fi) || []) {
      for (let i = 0; i < pl.length; i += 3) {
        const t = (pl[i] - o[0]) * d[0] + (pl[i + 1] - o[1]) * d[1] + (pl[i + 2] - o[2]) * d[2];
        t0 = Math.min(t0, t); t1 = Math.max(t1, t);
      }
    }
    if (!(t1 >= t0)) t0 = t1 = dot(f.centroid.map((v, i) => v - o[i]), d);
    const had = byName.get(f.name); // (a round face in two halves: one axis, as far as both reach)
    if (had?.t) { t0 = Math.min(t0, had.t[0]); t1 = Math.max(t1, had.t[1]); }
    const a = uv(o.map((v, i) => v + d[i] * t0)), b = uv(o.map((v, i) => v + d[i] * t1));
    byName.set(f.name, { ref: had?.ref || ref, face: had?.face ?? fi, r: f.radius, c: a, a, b, dir: [dot(d, x) / L, dot(d, y) / L], t: [t0, t1] });
  });
  return [...byName.values()];
}

/** The axis that ref ({face, fp}) names, of the ones on the plane now (the nearest of that name), or null. */
export function axisOf(axes, ref) {
  let best = null, bd = Infinity;
  for (const q of axes) {
    if (q.ref.face !== ref?.face) continue;
    const d = ref.fp ? Math.hypot(...q.ref.fp.map((v, i) => v - ref.fp[i])) : 0;
    if (d < bd) { bd = d; best = q; }
  }
  return best;
}
