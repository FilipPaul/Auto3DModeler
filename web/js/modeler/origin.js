// A sketch's (or a hole step's) 0, 0 on a face — plane.origin: none = the face's centre (where it was when picked),
// "corner" = the face's ⌜ corner with the smallest u and v (followed when the part changes), "world" = ⊕ the part's
// origin seen square onto the face (fixed), {point: <id>} = a • reference point. The kernel finds it again on each
// rebuild (doc._origin); the browser moves it at once here, and shifts what is drawn so it keeps its place.

export const ORIGINS = [['centre', '◎ Face centre', 'Measure from the middle of the face'],
  ['corner', '⌜ Corner', 'Measure from the face\'s lower-left corner — it follows that corner when the part changes'],
  ['world', '⊕ Part origin', 'Measure from the part\'s origin (0, 0, 0): the X / Y / Z you see in the view']];

const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const yOf = (fr) => { const { x, n } = fr; return [n[1] * x[2] - n[2] * x[1], n[2] * x[0] - n[0] * x[2], n[0] * x[1] - n[1] * x[0]]; };

/** A plane's origin as a key: "centre", "corner", "world" or "point:<id>". */
export const originKey = (o) => (o && typeof o === 'object' ? `point:${o.point}` : o || 'centre');

/** Is frame `fr` (a rebuild's) measured from this plane's origin? (A just-switched origin: not yet.) */
export const sameOrigin = (fr, plane) => originKey(fr?.origin) === originKey(plane?.origin);

/** Where origin `how` is (3D) on the plane of frame `fr` (the one shown now), or null when it cannot be told here.
 *  span(fr) -> the face's [u0, u1, v0, v1] from fr.o (ModelView.faceSpan), centre: the face's centre (3D) now,
 *  points: {id: [x, y, z]} (the rebuild's reference points). */
export function originAt(how, fr, { span, centre, points } = {}) {
  const o = fr.o, x = fr.x, y = yOf(fr), n = fr.n;
  let p = null;
  if (how === 'world') p = [0, 0, 0];
  else if (how === 'corner') { const s = span?.(fr); if (s) p = o.map((v, i) => v + s[0] * x[i] + s[2] * y[i]); }
  else if (how && typeof how === 'object') p = points?.[how.point] || null;
  else p = centre || null;
  if (!p) return null;
  const w = dot(o.map((v, i) => v - p[i]), n);
  return p.map((v, i) => +(v + w * n[i]).toFixed(9)); // (in the plane: only along it)
}

/** How far 3D point p lies from frame fr's origin, along its x and y: [du, dv]. */
export function shiftOf(fr, p) {
  const d = p.map((v, i) => v - fr.o[i]);
  return [dot(d, fr.x), dot(d, yOf(fr))];
}

/** A sketch's origin moved by (du, dv): its shapes keep their place — their points, fixed references, a block's place
 *  and fixed points shift by −(du, dv); a distance to the origin measures from the new one. */
export function shiftSketch(f, du, dv) {
  const mv = (p) => [+(p[0] - du).toFixed(6), +(p[1] - dv).toFixed(6)];
  for (const [k, p] of Object.entries(f.points || {})) f.points[k] = mv(p);
  for (const e of f.entities || []) if (Array.isArray(e.at)) e.at = mv(e.at);
  for (const k of f.constraints || []) if (Array.isArray(k.at)) k.at = mv(k.at);
  const P = (end) => (end === 'O' ? [0, 0] : typeof end === 'string' ? f.points[end] : Array.isArray(end?.ref) ? end.ref : null);
  for (const d of f.dims || []) {
    for (const k of ['a', 'b']) if (Array.isArray(d[k]?.ref)) d[k] = { ...d[k], ref: mv(d[k].ref) };
    if (d.a !== 'O' && d.b !== 'O') continue;
    const a = P(d.a), b = P(d.b);
    if (!a || !b) continue;
    if (d.t === 'dx') d.v = +(b[0] - a[0]).toFixed(6);
    else if (d.t === 'dy') d.v = +(b[1] - a[1]).toFixed(6);
    else if (d.t === 'dist') d.v = +Math.hypot(b[0] - a[0], b[1] - a[1]).toFixed(6);
  }
  return f;
}

/** Holes' places [[u, v]] moved the same way. */
export const shiftPoints = (pts, du, dv) => pts.map((p) => [+(p[0] - du).toFixed(6), +(p[1] - dv).toFixed(6)]);

// holes: each from its nearest edges (as clicked), or all from one origin
export const HOLE_ORIGINS = [['edges', '⇤ Edges', 'Each hole from the nearest edges of the face (⇄ / 🎯 choose others)'], ORIGINS[1],
  ['world', '⊕ Origin', ORIGINS[2][2]]]; // (short: the panel is narrow)
export const FROM_TEXT = { centre: 'from the face\'s centre', corner: 'from the corner', world: 'from the part\'s origin' };

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

/** The Origin choice as a .seg after its label (a sketch / holes on a face; '' elsewhere): its buttons carry data-origin. */
export function originSeg(plane, cur, label = 'Origin', options = ORIGINS) {
  if (!plane?.face) return '';
  return `${label ? `<span class="m-say">${label}</span>` : ''}<div class="seg m-origin">${options.map(([k, l, tip]) =>
    `<button type="button" data-origin="${k}" class="${cur === k ? 'on' : ''}" title="${esc(tip)}">${l}</button>`).join('')}</div>`;
}

/** The plane (and the shift of what is on it) with its 0, 0 moved to `how` ("centre", "corner", "world"), seen from
 *  frame fr (the one shown now); null when it cannot be told here (the face is not in the view). */
export function moveOrigin(m, plane, fr, how) {
  const name = plane.face?.name, faces = (m.result?.body?.faces || []).filter((g) => g.name === name || (g.names || []).includes(name));
  const centre = faces.sort((a, b) => b.area - a.area)[0]?.centroid;
  const p = originAt(how === 'centre' ? null : how, fr, { span: (q) => m.view.faceSpan(name, q), centre, points: m.result?.points });
  if (!p) return null;
  const [du, dv] = shiftOf(fr, p), next = { ...plane, frame: { o: p, x: [...fr.x], n: [...fr.n] } };
  if (how === 'centre') delete next.origin; else next.origin = how;
  return { plane: next, du, dv };
}

/** World coordinates on a face (the AI's origin "world"): [a, b] along the two world axes in the face's plane (top /
 *  bottom: X, Y; front / back: X, Z; sides: Y, Z — on a slanted face: along its x and y) or [x, y, z] -> the frame's
 *  [u, v] from the world origin seen square onto it. flip: v runs against the world axis (an arc's turn reverses). */
export function worldToUV(fr) {
  const y = yOf(fr), big = (v) => v.map(Math.abs).indexOf(Math.max(...v.map(Math.abs)));
  const sv = Math.sign(y[big(y)]) || 1;
  const o = originAt('world', fr);
  return {
    flip: sv < 0,
    uv: (p) => (p.length === 3 ? shiftOf({ ...fr, o }, p).map((v) => +v.toFixed(6)) : [+p[0], +(sv * p[1]).toFixed(6)]),
  };
}
