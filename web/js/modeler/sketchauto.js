// What 🪄 Auto-dimension and the suggestions read off a sketch, as plain functions of the sketch JSON (f) and its
// points (P: point id -> [u, v]): the relations it nearly has already (H / V, tangent, equal radius), plain names for
// its shapes (to say which one is still free), nice rounded values, and the standard shapes drawn from single lines
// and arcs (a slot, a rectangle, a circle) that can become the real thing.

import { t } from '../i18n.js';

const NEAR_DEG = 0.5;  // a line this close to H / V, a joint this close to smooth, counts as meant
const NEAR_R = 0.005;  // two radii within 0.5 % count as meant to be equal
const fmt = (v) => (+(+v).toFixed(2)).toString();
const sub = (a, b) => [a[0] - b[0], a[1] - b[1]];
const len = (a) => Math.hypot(a[0], a[1]);

/** The radius of an arc / circle. */
export const radiusOf = (e, P) => (e.t === 'circle' ? e.r : len(sub(P(e.a), P(e.c))));

/** The relations the sketch nearly has but does not hold yet -> [{t, …}] (as f.constraints takes them), likeliest
 *  first: H / V of lines within NEAR_DEG, a line and an arc meeting smoothly (tan at their point), arcs / circles of
 *  the same radius (eq, chained: each to the first of its size). Construction shapes are left out. */
export function nearRelations(f, P) {
  const out = [], ks = f.constraints || [], ents = (f.entities || []).filter((e) => !e.construction);
  const has = (fn) => ks.some(fn);
  const sinNear = Math.sin((NEAR_DEG * Math.PI) / 180);
  for (const e of ents.filter((x) => x.t === 'line')) {
    if (has((k) => k.e === e.id && (k.t === 'h' || k.t === 'v'))) continue;
    const d = sub(P(e.b), P(e.a)), L = len(d);
    if (!(L > 1e-9)) continue;
    if (Math.abs(d[1]) / L < sinNear) out.push({ t: 'h', e: e.id });
    else if (Math.abs(d[0]) / L < sinNear) out.push({ t: 'v', e: e.id });
  }
  for (const a of ents.filter((x) => x.t === 'arc')) {
    for (const p of [a.a, a.b]) {
      for (const l of ents.filter((x) => x.t === 'line' && (x.a === p || x.b === p))) {
        if (has((k) => (k.t === 'tan' && k.e === l.id && k.arc === a.id) || (k.t === 'tang' && [k.e, k.e2].includes(l.id) && [k.e, k.e2].includes(a.id)))) continue;
        const along = sub(P(l.a === p ? l.b : l.a), P(p)), rad = sub(P(p), P(a.c)), L = len(along) * len(rad);
        if (L > 1e-12 && Math.abs(along[0] * rad[0] + along[1] * rad[1]) / L < sinNear) out.push({ t: 'tan', e: l.id, arc: a.id, p });
      }
    }
  }
  const round = ents.filter((x) => x.t === 'arc' || x.t === 'circle'), firsts = [];
  for (const e of round) {
    const r = radiusOf(e, P), like = firsts.find((g) => Math.abs(radiusOf(g, P) - r) <= NEAR_R * Math.max(r, 1e-9));
    if (!like) { firsts.push(e); continue; }
    const linked = (x, y) => has((k) => k.t === 'eq' && [k.e, k.e2].includes(x.id) && [k.e, k.e2].includes(y.id));
    if (!linked(like, e) && !(f.dims || []).some((d) => !d.free && (d.t === 'rad' || d.t === 'dia') && d.e === e.id)) out.push({ t: 'eq', e: like.id, e2: e.id, user: true });
  }
  return out;
}

/** A shape in plain words (where it is), to say which one is still free: "arc R23.2 at (45, 8.94)". */
export function shapeName(e, P) {
  if (!e) return '';
  const say = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k]);
  const xy = (p) => `(${fmt(P(p)[0])}, ${fmt(P(p)[1])})`;
  if (e.t === 'line') return say('line {a} – {b}', { a: xy(e.a), b: xy(e.b) });
  if (e.t === 'arc') return say('arc R{r} at {c}', { r: fmt(radiusOf(e, P)), c: xy(e.c) });
  if (e.t === 'circle') return say('circle Ø{d} at {c}', { d: fmt(2 * e.r), c: xy(e.c) });
  if (e.t === 'spline') return say('curve from {a}', { a: xy(e.pts[0]) });
  return e.t;
}

/** A nice value near v for a locked size: whole millimetres (half for small sizes), whole degrees; a value that
 *  would round to nothing stays as it is. */
export function roundValue(v, t) {
  if (t === 'ang') return Math.round(v) || v;
  const step = Math.abs(v) < 5 ? 0.5 : 1, r = Math.round(v / step) * step;
  return Math.abs(r) < 1e-9 && ['len', 'dia', 'rad', 'dist', 'pl'].includes(t) ? v : +r.toFixed(3);
}

/** Standard shapes drawn from single lines and arcs -> [{kind: 'slot', ids, c1, c2, r} | {kind: 'rect', ids} |
 *  {kind: 'circle', ids, c, r}]: a closed loop of two lines and two half arcs of one radius (a slot), four lines at
 *  right angles not yet a rectangle (no H / V on them), two arcs on one centre making a full turn (a circle). */
export function standardShapes(f, P) {
  const out = [], ents = (f.entities || []).filter((e) => !e.construction && (e.t === 'line' || e.t === 'arc'));
  const loops = [], seen = new Set();
  for (const e of ents) {
    if (seen.has(e.id)) continue;
    const loop = [e], ids = new Set([e.id]);
    let at = e.b, ok = true;
    while (at !== e.a) {
      const next = ents.filter((x) => !ids.has(x.id) && (x.a === at || x.b === at));
      if (next.length !== 1 || loop.length > 8) { ok = false; break; }
      loop.push(next[0]);
      ids.add(next[0].id);
      at = next[0].a === at ? next[0].b : next[0].a;
    }
    loop.forEach((x) => seen.add(x.id));
    if (ok) loops.push(loop);
  }
  for (const loop of loops) {
    const arcs = loop.filter((x) => x.t === 'arc'), lines = loop.filter((x) => x.t === 'line'), ids = loop.map((x) => x.id);
    if (loop.length === 4 && arcs.length === 2 && lines.length === 2 && f.entities.indexOf(arcs[0]) >= 0) {
      const [r1, r2] = arcs.map((a) => radiusOf(a, P));
      const half = arcs.every((a) => Math.abs(len(sub(P(a.a), P(a.b))) - 2 * radiusOf(a, P)) < 0.01 * radiusOf(a, P));
      if (half && Math.abs(r1 - r2) < 0.01 * r1 && len(sub(P(arcs[0].c), P(arcs[1].c))) > 1e-6) out.push({ kind: 'slot', ids, c1: P(arcs[0].c), c2: P(arcs[1].c), r: (r1 + r2) / 2 });
    } else if (loop.length === 4 && lines.length === 4 && !lines.every((l) => (f.constraints || []).some((k) => k.e === l.id && (k.t === 'h' || k.t === 'v')))) {
      const dir = (l) => { const d = sub(P(l.b), P(l.a)); return d.map((v) => v / (len(d) || 1)); };
      const square = lines.every((l, i) => { const u = dir(l), w = dir(lines[(i + 1) % 4]); return Math.abs(u[0] * w[0] + u[1] * w[1]) < 0.01 && Math.min(Math.abs(u[0]), Math.abs(u[1])) < Math.sin(Math.PI / 60); });
      if (square) out.push({ kind: 'rect', ids });
    } else if (loop.length === 2 && arcs.length === 2 && arcs[0].c === arcs[1].c) {
      out.push({ kind: 'circle', ids, c: arcs[0].c, r: radiusOf(arcs[0], P) });
    }
  }
  return out;
}
