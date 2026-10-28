// Snapping a spot on a flat face of the part (a hole's centre, where a text / picture goes), like Sketcher.snap: onto
// the face's corners, edge midpoints, round edges' centres, its own centre, • reference points and other holes; onto
// its edges; else in line with one of those along the face's x / y, or on an edge's extension (dashed green guides),
// both: where they cross. The snap filters (suggest.js snapKinds) say which; Shift (or Alt) = no snapping.
import { snapPoints } from './view.js';
import { snapKinds } from '../suggest.js';
import { t } from '../i18n.js';

const GUIDE = 0x7ee787;
const dot = (p, q) => p[0] * q[0] + p[1] * q[1] + p[2] * q[2];
const NAMES = { corner: 'corner', midpoint: 'midpoint', centre: 'centre', quadrant: 'quadrant', face: 'centre of the face', hole: 'hole centre',
  edge: 'on the edge of the part', ext: "on the edge's extension", line: 'in line', cross: 'where the lines cross' };

/** A face frame's axes as arrays: {o, x, y, n} (y = n × x). */
function basis(fr) {
  const { o, x, n } = fr;
  return { o, x, n, y: [n[1] * x[2] - n[2] * x[1], n[2] * x[0] - n[0] * x[2], n[0] * x[1] - n[1] * x[0]] };
}

/** A 3D point ([x, y, z] or a THREE vector) in the face's coordinates -> [u, v]. */
export function toFace(fr, p) {
  const { o, x, y } = basis(fr), d = Array.isArray(p) ? [p[0] - o[0], p[1] - o[1], p[2] - o[2]] : [p.x - o[0], p.y - o[1], p.z - o[2]];
  return [dot(d, x), dot(d, y)];
}

/** What a spot on the face can snap to: keys [{uv, kind, name?, hole?, round?}] (round: a round edge's ref {a, b, fp}
 *  — a hole of an earlier step) and the face's edges as polylines in [u, v] (straight: true for a line). skip: a name
 *  prefix whose edges are left out (the step being placed); extra: more keys (this step's holes). */
export function faceKeys(view, face, fr, { skip = '', extra = [], kinds = snapKinds() } = {}) {
  const b = view.body, keys = [...extra], edges = [];
  if (!b || !face) return { keys, edges };
  for (const e of b.edges) {
    if (!e.faces.includes(face.id)) continue;
    if (skip && e.faces.some((k) => (b.faces[k]?.name || '').startsWith(skip))) continue;
    const pts = [];
    for (let i = 0; i + 2 < e.pts.length; i += 3) pts.push(toFace(fr, [e.pts[i], e.pts[i + 1], e.pts[i + 2]]));
    edges.push({ pts, straight: e.pts.length === 6 });
    const names = e.faces.map((k) => b.faces[k]?.name);
    for (const q of snapPoints([e], null, kinds)) {
      const k = { uv: toFace(fr, q.point), kind: q.kind };
      if (q.kind === 'centre' && names.length === 2 && names.every(Boolean)) k.round = { a: names[0], b: names[1], fp: e.mid };
      keys.push(k);
    }
  }
  const sp = kinds.centre ? view.faceSpan(face.name, fr) : null;
  if (sp) keys.push({ uv: [(sp[0] + sp[1]) / 2, (sp[2] + sp[3]) / 2], kind: 'face' });
  for (const p of view.refPoints || []) keys.push({ uv: toFace(fr, p.point), kind: 'point', name: p.name }); // (• reference points, also off the face: in line with them)
  return { keys, edges };
}

/** The spot uv on the face snapped -> {uv, kind, name, guides: [[from, to]], keys: {x, y}} — keys: the key point each
 *  coordinate came from (a hole placed on it keeps that meaning). Not near anything: uv on the grid (mm), kind null.
 *  mpp: mm per screen pixel; free: no snapping at all. */
export function snapOnFace(view, { face, fr, uv, mpp, skip = '', extra = [], free = false, grid = 0.5 }) {
  const round = (p) => p.map((v) => +v.toFixed(6));
  if (free) return { uv: round(uv), kind: null, guides: [], keys: {} };
  const kinds = snapKinds(), tol = mpp * 10;
  const { keys, edges } = faceKeys(view, face, fr, { skip, extra: extra.filter((k) => kinds.centre || k.kind !== 'hole'), kinds });
  const named = (k) => k.name || NAMES[k.kind] || '';
  // onto a key point (a corner, a midpoint, a centre, a hole, a reference point)
  let best = null;
  for (const k of keys) {
    const d = Math.hypot(k.uv[0] - uv[0], k.uv[1] - uv[1]);
    if (d < tol && (!best || d < best.d)) best = { d, k };
  }
  if (best) {
    const k = best.k, p = round(k.uv), guides = [];
    if (k.kind === 'face') { // the face's centre: what it lines up with shown (the edges' midpoints)
      for (const j of [0, 1]) {
        const q = keys.filter((m) => m.kind === 'midpoint' && Math.abs(m.uv[j] - p[j]) < 1e-6).sort((a, c) => Math.abs(a.uv[1 - j] - p[1 - j]) - Math.abs(c.uv[1 - j] - p[1 - j]))[0];
        if (q) guides.push([[...q.uv], p]);
      }
    }
    return { uv: p, kind: k.kind, name: named(k), guides, keys: { x: k, y: k } };
  }
  // onto the face's edge (the nearest place on it)
  const foot = (a, c) => {
    const dx = c[0] - a[0], dy = c[1] - a[1], L = dx * dx + dy * dy || 1, s = Math.max(0, Math.min(1, ((uv[0] - a[0]) * dx + (uv[1] - a[1]) * dy) / L));
    return [a[0] + s * dx, a[1] + s * dy];
  };
  for (const e of edges) {
    for (let i = 0; i + 1 < e.pts.length; i++) {
      const p = foot(e.pts[i], e.pts[i + 1]), d = Math.hypot(p[0] - uv[0], p[1] - uv[1]);
      if (d < tol * 0.8 && (!best || d < best.d)) best = { d, p };
    }
  }
  if (best) return { uv: round(best.p), kind: 'edge', name: NAMES.edge, guides: [], keys: {} };
  const g = [Math.round(uv[0] / grid) * grid, Math.round(uv[1] / grid) * grid];
  if (kinds.guides === false) return { uv: round(g), kind: null, guides: [], keys: {} };
  // guides: level with a key point along the face's x or y, or on a straight edge's extension (beyond its ends)
  let gx = null, gy = null;
  for (const k of keys) {
    const dx = Math.abs(k.uv[0] - uv[0]), dy = Math.abs(k.uv[1] - uv[1]);
    if (dx < tol && dy > tol && (!gx || dx < gx.d)) gx = { d: dx, v: k.uv[0], k };
    if (dy < tol && dx > tol && (!gy || dy < gy.d)) gy = { d: dy, v: k.uv[1], k };
  }
  let ext = null;
  for (const e of edges) {
    if (!e.straight) continue;
    const [a, c] = e.pts, dx = c[0] - a[0], dy = c[1] - a[1], L2 = dx * dx + dy * dy;
    if (L2 < 1e-12) continue;
    const s = ((uv[0] - a[0]) * dx + (uv[1] - a[1]) * dy) / L2;
    if (s >= 0 && s <= 1) continue; // (beside the edge itself: snapped onto it above)
    const p = [a[0] + s * dx, a[1] + s * dy], d = Math.hypot(p[0] - uv[0], p[1] - uv[1]);
    if (d < tol * 0.8 && (!ext || d < ext.d)) ext = { d, a, dir: [dx, dy], from: s < 0 ? a : c, p };
  }
  const cut = (x, y) => { // where the edge's extension meets x = … or y = …
    if (x !== null && Math.abs(ext.dir[0]) > 1e-9) { const s = (x - ext.a[0]) / ext.dir[0]; return [x, ext.a[1] + s * ext.dir[1]]; }
    if (y !== null && Math.abs(ext.dir[1]) > 1e-9) { const s = (y - ext.a[1]) / ext.dir[1]; return [ext.a[0] + s * ext.dir[0], y]; }
    return null;
  };
  let at = null, from = [], kind = 'line', keyed = {};
  if (gx && gy) { at = [gx.v, gy.v]; from = [gx.k.uv, gy.k.uv]; kind = 'cross'; keyed = { x: gx.k, y: gy.k }; }
  else if (ext && (gx || gy)) { at = cut(gx ? gx.v : null, gy ? gy.v : null) || ext.p; from = [ext.from, (gx || gy).k.uv]; kind = 'cross'; keyed = gx ? { x: gx.k } : { y: gy.k }; }
  else if (ext) { at = ext.p; from = [ext.from]; kind = 'ext'; }
  else if (gx) { at = [gx.v, g[1]]; from = [gx.k.uv]; keyed = { x: gx.k }; }
  else if (gy) { at = [g[0], gy.v]; from = [gy.k.uv]; keyed = { y: gy.k }; }
  if (!at) return { uv: round(g), kind: null, guides: [], keys: {} };
  const p = round(at);
  return { uv: p, kind, name: NAMES[kind], guides: from.map((q) => [[...q], p]), keys: keyed };
}

/** A snap drawn on the face (for ModelView.setSketch): the guides dashed green from what they line up with, the spot
 *  ringed, its name beside it -> {lines, dots, circles, labels}. */
export function snapDrawing(s, mpp) {
  const lines = [], dots = [], circles = [], labels = [];
  if (!s) return { lines, dots, circles, labels };
  for (const [p, q] of s.guides || []) { lines.push([p, q, GUIDE, true]); dots.push([p, GUIDE]); circles.push([p, mpp * 4, GUIDE]); }
  if (s.kind) {
    circles.push([s.uv, mpp * 6, GUIDE]);
    dots.push([s.uv, GUIDE]);
    const el = document.createElement('div');
    el.className = 'm-snap face-snap';
    el.textContent = t(s.name);
    labels.push({ el, u: s.uv[0] + mpp * 14, v: s.uv[1] + mpp * 12 });
  }
  return { lines, dots, circles, labels };
}
